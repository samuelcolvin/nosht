import asyncio
import base64
import hashlib
import hmac
import logging
import re
from binascii import hexlify
from datetime import datetime
from email.message import EmailMessage
from email.policy import SMTP
from functools import reduce
from pathlib import Path
from typing import List
from urllib.parse import urlencode

import chevron
import sass
from aiohttp import ClientSession, ClientTimeout
from arq import Actor, concurrent
from buildpg import asyncpg
from misaka import Markdown, HtmlRenderer, SaferHtmlRenderer

from shared.misc import unsubscribe_sig
from ..settings import Settings
from ..utils import RequestError
from .defaults import EMAIL_DEFAULTS, Triggers

logger = logging.getLogger('nosht.email')

THIS_DIR = Path(__file__).parent
DEFAULT_EMAIL_TEMPLATE = (THIS_DIR / 'default_template.html').read_text()
STYLES = (THIS_DIR / 'styles.scss').read_text()
STYLES = sass.compile(string=STYLES, output_style='compressed', precision=10).strip('\n')

_AWS_SERVICE = 'ses'
_AWS_AUTH_REQUEST = 'aws4_request'
_CONTENT_TYPE = 'application/x-www-form-urlencoded'
_SIGNED_HEADERS = 'content-type', 'host', 'x-amz-date'
_CANONICAL_REQUEST = """\
POST
/

{canonical_headers}
{signed_headers}
{payload_hash}"""
_AUTH_ALGORITHM = 'AWS4-HMAC-SHA256'
_CREDENTIAL_SCOPE = '{date_stamp}/{region}/{service}/{auth_request}'
_STRING_TO_SIGN = """\
{algorithm}
{x_amz_date}
{credential_scope}
{canonical_request_hash}"""
_AUTH_HEADER = (
    '{algorithm} Credential={access_key}/{credential_scope},SignedHeaders={signed_headers},Signature={signature}'
)

flags = ('hard-wrap',)
extensions = ('no-intra-emphasis',)
markdown = Markdown(
    HtmlRenderer(flags=flags),
    extensions=extensions
)
safe_markdown = Markdown(
    SaferHtmlRenderer(flags=flags),
    extensions=extensions
)

strip_markdown_re = [
    (re.compile(r'\<.*?\>', flags=re.S), ''),
    (re.compile(r'_(\S.*?\S)_'), r'\1'),
    (re.compile(r'\[(.+?)\]\(.+?\)'), r'\1'),
    (re.compile(r'\*\*'), ''),
    (re.compile('^#+ ', flags=re.M), ''),
    (re.compile('`'), ''),
    (re.compile('\n+'), ' '),
]


def strip_markdown(s):
    for regex, p in strip_markdown_re:
        s = regex.sub(p, s)
    return s


class EmailActor(Actor):
    def __init__(self, *, settings: Settings, http_client=None, pg=None, **kwargs):
        self.redis_settings = settings.redis_settings
        super().__init__(**kwargs)
        self.settings = settings
        self.client = http_client or ClientSession(timeout=ClientTimeout(total=10), loop=kwargs.get('loop'))
        self.pg = pg

        self._host = self.settings.aws_ses_host.format(region=self.settings.aws_region)
        self._endpoint = self.settings.aws_ses_endpoint.format(host=self._host)

    async def startup(self):
        self.pg = self.pg or await asyncpg.create_pool_b(dsn=self.settings.pg_dsn, min_size=2)

    async def shutdown(self):
        await self.client.close()
        await self.pg.close()

    def _aws_headers(self, data):
        n = datetime.utcnow()
        x_amz_date = n.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = n.strftime('%Y%m%d')
        ctx = dict(
            access_key=self.settings.aws_access_key,
            algorithm=_AUTH_ALGORITHM,
            x_amz_date=x_amz_date,
            auth_request=_AWS_AUTH_REQUEST,
            content_type=_CONTENT_TYPE,
            date_stamp=date_stamp,
            host=self._host,
            payload_hash=hashlib.sha256(data).hexdigest(),
            region=self.settings.aws_region,
            service=_AWS_SERVICE,
            signed_headers=';'.join(_SIGNED_HEADERS),
        )
        ctx.update(
            credential_scope=_CREDENTIAL_SCOPE.format(**ctx),
        )
        canonical_headers = ''.join('{}:{}\n'.format(h, ctx[h.replace('-', '_')]) for h in _SIGNED_HEADERS)

        canonical_request = _CANONICAL_REQUEST.format(canonical_headers=canonical_headers, **ctx).encode()

        s2s = _STRING_TO_SIGN.format(canonical_request_hash=hashlib.sha256(canonical_request).hexdigest(), **ctx)

        key_parts = (
            b'AWS4' + self.settings.aws_secret_key.encode(),
            date_stamp,
            self.settings.aws_region,
            _AWS_SERVICE,
            _AWS_AUTH_REQUEST,
            s2s,
        )
        signature = reduce(lambda key, msg: hmac.new(key, msg.encode(), hashlib.sha256).digest(), key_parts)

        authorization_header = _AUTH_HEADER.format(signature=hexlify(signature).decode(), **ctx)
        return {
            'Content-Type': _CONTENT_TYPE,
            'X-Amz-Date': x_amz_date,
            'Authorization': authorization_header
        }

    async def aws_send(self, *, e_from: str, email_msg: EmailMessage, to: List[str], bcc: List[str]=None):
        data = {
            'Action': 'SendRawEmail',
            'Source': e_from,
            'RawMessage.Data': base64.b64encode(email_msg.as_string().encode())
        }
        data.update({f'Destination.ToAddresses.member.{i + 1}': t.encode() for i, t in enumerate(to)})
        if bcc:
            data.update({f'Destination.BccAddresses.member.{i + 1}': t.encode() for i, t in enumerate(bcc)})
        data = urlencode(data).encode()

        headers = self._aws_headers(data)
        async with self.client.post(self._endpoint, data=data, headers=headers, timeout=5) as r:
            status_code = r.status
            text = await r.text()
        if status_code != 200:
            raise RequestError(status_code, self._endpoint, info=text)
        msg_id = re.search('<MessageId>(.+?)</MessageId>', text).groups()[0]
        return msg_id + f'@{self.settings.aws_region}.amazonses.com'

    async def send_email(self, user, subject, title, body, e_from, template, base_url, ctx):
        ctx = dict(ctx)
        full_name = '{first_name} {last_name}'.format(**user).strip(' ')

        unsubscribe_link = f'{base_url}/api/unsubscribe/{user["id"]}/?sig={unsubscribe_sig(user["id"], self.settings)}'

        ctx.update(
            first_name=user['first_name'] or user['email'],
            full_name=full_name or user['email'],
            unsubscribe_link=unsubscribe_link
        )
        # TODO deal with links
        raw_body = chevron.render(body, data=ctx)

        e_msg = EmailMessage(policy=SMTP)
        subject = chevron.render(subject, data=ctx)
        e_msg['Subject'] = subject
        e_msg['From'] = e_from
        user_email = user['email']
        e_msg['To'] = f'{full_name} <{user_email}>' if full_name else user_email
        e_msg['List-Unsubscribe'] = f'<{unsubscribe_link}>'

        e_msg.set_content(raw_body, cte='quoted-printable')

        ctx.update(
            main_message=safe_markdown(raw_body),
            message_preview=strip_markdown(raw_body),
        )
        html_body = chevron.render(template, data=ctx, partials_dict={'title': title})
        e_msg.add_alternative(html_body, subtype='html', cte='quoted-printable')

        msg_id = await self.aws_send(e_from=e_from, to=[user_email], email_msg=e_msg)
        logger.info('email sent "%s", id %0.12s...', subject, msg_id)

    @concurrent
    async def send_emails(self, company_id: int, trigger: str, user_ids: List[int], ctx: dict=None):
        trigger = Triggers(trigger)

        async with self.pg.acquire() as conn:
            company_name, e_from, template, company_logo, company_domain = await conn.fetchrow(
                'SELECT name, email_from, email_template, logo, domain FROM companies WHERE id=$1', company_id
            )
            e_from = e_from or self.settings.default_email_address
            template = template or DEFAULT_EMAIL_TEMPLATE

            r = await conn.fetchrow(
                """
                SELECT active, subject, title, body
                FROM email_definitions
                WHERE company=$1 AND trigger=$2
                """,
                company_id, trigger.value
            )
            if r:
                active, subject, title, body = r
                if not active:
                    logger.info('not sending email %s (%d), email definition inactive', trigger.value, company_id)
                    return
            else:
                dft = EMAIL_DEFAULTS[trigger]
                subject, title, body = dft['subject'], dft['title'], dft['body']

            users = await conn.fetch(
                """
                SELECT id, first_name, last_name, email
                FROM users
                WHERE company=$1 AND status!='suspended' AND receive_emails=TRUE AND email IS NOT NULL AND id=ANY($2)
                """,
                company_id, user_ids
            )

        ctx = ctx or {}
        ctx.update(
            styles=STYLES,
            company_name=company_name,
            company_logo=company_logo,
        )
        base_url = f'https://{company_domain}'
        ctx['styles'] = STYLES
        await asyncio.gather(*[
            self.send_email(user, subject, title, body, e_from, template, base_url, ctx)
            for user in users
        ])
        logger.info('%d emails sent for trigger %s, company %s (%d)', len(users), trigger, company_domain, company_id)
