import asyncio
import base64
import datetime
import hashlib
import hmac
import json
import logging
import re
from binascii import hexlify
from email.message import EmailMessage
from email.policy import SMTP
from functools import reduce
from pathlib import Path
from textwrap import shorten
from typing import Any, Dict, List, NamedTuple, Optional
from urllib.parse import urlencode

import chevron
import sass
from aiohttp import ClientSession, ClientTimeout
from arq import concurrent
from buildpg import Values
from cryptography import fernet
from misaka import HtmlRenderer, Markdown
from pydantic.datetime_parse import parse_datetime

from ..actor import BaseActor
from ..utils import RequestError, format_dt, format_duration, unsubscribe_sig
from .defaults import EMAIL_DEFAULTS, Triggers
from .ical import ical_attachment
from .utils import Attachment

logger = logging.getLogger('nosht.emails')

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
safe_markdown = Markdown(HtmlRenderer(flags=flags), extensions=extensions)  # maybe should use SaferHtmlRenderer
DEBUG_PRINT_REGEX = re.compile(r'{{ ?__debug_context__ ?}}')


class UserEmail(NamedTuple):
    id: int
    ctx: Dict[str, Any] = {}
    ticket_id: int = None


class BaseEmailActor(BaseActor):
    def __init__(self, *, http_client=None, **kwargs):
        super().__init__(**kwargs)
        self.client = http_client or ClientSession(timeout=ClientTimeout(total=10), loop=self.loop)
        self._host = self.settings.aws_ses_host.format(region=self.settings.aws_region)
        self._endpoint = self.settings.aws_ses_endpoint.format(host=self._host)
        self.auth_fernet = fernet.Fernet(self.settings.auth_key)
        self.send_via_aws = self.settings.aws_access_key and not self.settings.print_emails

    def _aws_headers(self, data):
        n = datetime.datetime.utcnow()
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
        ctx.update(credential_scope=_CREDENTIAL_SCOPE.format(**ctx))
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
        return {'Content-Type': _CONTENT_TYPE, 'X-Amz-Date': x_amz_date, 'Authorization': authorization_header}

    async def aws_send(self, *, e_from: str, email_msg: EmailMessage, to: List[str]):
        data = {
            'Action': 'SendRawEmail',
            'Source': e_from,
            'RawMessage.Data': base64.b64encode(email_msg.as_string().encode()),
        }
        data.update({f'Destination.ToAddresses.member.{i + 1}': t.encode() for i, t in enumerate(to)})
        # data.update({f'Destination.BccAddresses.member.{i + 1}': t.encode() for i, t in enumerate(bcc)})
        data = urlencode(data).encode()

        headers = self._aws_headers(data)
        async with self.client.post(self._endpoint, data=data, headers=headers, timeout=5) as r:
            text = await r.text()
        if r.status != 200:
            raise RequestError(r.status, self._endpoint, text=text)
        return re.search('<MessageId>(.+?)</MessageId>', text).group(1)

    async def print_email(self, *, e_from: str, email_msg: EmailMessage, to: List[str]):  # pragma: no cover
        if self.settings.print_emails_verbose:
            d = dict(email_msg)
            d['AWS-Source'] = e_from
            d['AWS-To'] = ', '.join(to)

            print('=' * 80)
            for f in ('AWS-Source', 'AWS-To', 'Subject', 'From', 'To', 'List-Unsubscribe'):
                print(f'{f:>30}: {d[f]}')

            for part in email_msg.walk():
                payload = part.get_payload(decode=True)
                if payload:
                    print('-' * 80)
                    print(f'{part.get_content_type()}:')
                    print(payload.decode().replace('\r\n', '\n').strip(' \n'))

            print('=' * 80)
        else:
            logger.info('"%s" %s -> %s', email_msg["subject"], e_from, to)
        return '-'

    async def send_email(
        self,
        *,
        user: Dict[str, Any],
        user_ctx: Dict[str, Any],
        subject: str,
        title: str,
        body: str,
        template: str,
        e_from: str,
        reply_to: Optional[str],
        global_ctx: Dict[str, Any],
        attachment: Optional[Attachment],
        tags: Dict[str, str],
        company_id: int,
    ):
        base_url = global_ctx['base_url']

        full_name = '{first_name} {last_name}'.format(
            first_name=user['first_name'] or '', last_name=user['last_name'] or '',
        ).strip(' ')
        user_email = user['email']
        extra_ctx = dict(
            first_name=user['first_name'] or user['last_name'] or '',
            full_name=full_name or 'user',
            unsubscribe_link=f'/api/unsubscribe/{user["id"]}/?sig={unsubscribe_sig(user["id"], self.settings)}',
        )
        ctx = clean_ctx({**global_ctx, **extra_ctx, **user_ctx}, base_url)
        markup_data = ctx.pop('markup_data', None)

        e_msg = EmailMessage(policy=SMTP)
        subject = chevron.render(subject, data=ctx)
        e_msg['Subject'] = subject
        e_msg['From'] = e_from
        if reply_to:
            e_msg['Reply-To'] = reply_to
        e_msg['To'] = f'{full_name} <{user_email}>' if full_name else user_email
        e_msg['List-Unsubscribe'] = '<{unsubscribe_link}>'.format(**ctx)
        e_msg['X-SES-CONFIGURATION-SET'] = 'nosht'
        e_msg['X-SES-MESSAGE-TAGS'] = ', '.join(f'{k}={v}' for k, v in tags.items())

        if DEBUG_PRINT_REGEX.search(body):
            ctx['__debug_context__'] = f'```{json.dumps(ctx, indent=2)}```'

        body = apply_macros(body)
        body = chevron.render(body, data=ctx)
        raw_body = re.sub(r'\n{3,}', '\n\n', body).strip('\n')
        e_msg.set_content(raw_body, cte='quoted-printable')

        ctx.update(
            styles=STYLES,
            main_message=safe_markdown(raw_body),
            message_preview=shorten(strip_markdown(raw_body), 60, placeholder='…'),
        )
        if markup_data:
            ctx['markup_data'] = json.dumps(markup_data, separators=(',', ':'))
        html_body = chevron.render(template, data=ctx, partials_dict={'title': title})
        e_msg.add_alternative(html_body, subtype='html', cte='quoted-printable')
        if attachment:
            maintype, subtype = attachment.mime_type.split('/')
            e_msg.add_attachment(
                attachment.content.encode(), maintype=maintype, subtype=subtype, filename=attachment.filename,
            )

        if self.send_via_aws and user_email.endswith('example.com'):
            logger.info('email not sent "%s" to "%s" because it ends "example.com"', subject, user_email)
            return

        send_method = self.aws_send if self.send_via_aws else self.print_email
        msg_id = await send_method(e_from=e_from, to=[user_email], email_msg=e_msg)

        await self.pg.execute(
            """
            insert into emails (company, user_id, ext_id, trigger, subject, address)
            values ($1, $2, $3, $4, $5, $6)
            """,
            company_id,
            user['id'],
            msg_id,
            tags['trigger'],
            subject,
            user_email,
        )

    @concurrent
    async def send_emails(
        self, company_id: int, trigger: str, users_emails: List[UserEmail], *, force_send=False, attached_event_id=None
    ):
        trigger = Triggers(trigger)

        dft = EMAIL_DEFAULTS[trigger]
        subject, title, body = dft['subject'], dft['title'], dft['body']
        attachment = None

        async with self.pg.acquire() as conn:
            company_name, company_slug, e_from, reply_to, template, company_logo, company_domain = await conn.fetchrow(
                'SELECT name, slug, email_from, email_reply_to, email_template, logo, domain '
                'FROM companies WHERE id=$1',
                company_id,
            )
            e_from = e_from or self.settings.default_email_address
            template = template or DEFAULT_EMAIL_TEMPLATE

            r = await conn.fetchrow(
                """
                SELECT active, subject, title, body
                FROM email_definitions
                WHERE company=$1 AND trigger=$2
                """,
                company_id,
                trigger.value,
            )
            if r:
                if not r['active']:
                    logger.info('not sending email %s (%d), email definition inactive', trigger.value, company_id)
                    return
                subject = r['subject'] or subject
                title = r['title'] or title
                body = r['body'] or body

            sql = """
            SELECT id, first_name, last_name, email
            FROM users
            WHERE
              company=$1 AND
              email IS NOT NULL AND
              id=ANY($2) AND
              status!='suspended'
            """
            sql += '' if force_send else 'AND receive_emails=TRUE'
            user_data = await conn.fetch(sql, company_id, [u[0] for u in users_emails])

            ticket_name_lookup = {}
            ticket_ids = [ue[2] for ue in users_emails if ue[2]]
            if ticket_ids:
                ticket_name_lookup = {
                    r['ticket_id']: r
                    for r in await conn.fetch(
                        'SELECT id AS ticket_id, first_name, last_name FROM tickets WHERE id=ANY($1)', ticket_ids
                    )
                }

            if attached_event_id:
                attachment = await ical_attachment(attached_event_id, company_id, conn=conn, settings=self.settings)

        global_ctx = dict(company_name=company_name, company_logo=company_logo, base_url=f'https://{company_domain}')
        coros = []
        tags = {
            'company': company_slug,
            'trigger': trigger.value,
        }
        user_data_lookup = {u['id']: u for u in user_data}
        for user_id, ctx, ticket_id in users_emails:
            try:
                user_data_ = user_data_lookup[user_id]
            except KeyError:
                # this user has receive_emails = FALSE or status = 'suspended'
                continue

            ticket_data = ticket_id and ticket_name_lookup.get(ticket_id)
            if ticket_data:
                user_data_ = dict(user_data_)
                user_data_['first_name'] = user_data_['first_name'] or ticket_data['first_name']
                user_data_['last_name'] = user_data_['last_name'] or ticket_data['last_name']
            coros.append(
                self.send_email(
                    user=user_data_,
                    user_ctx=ctx,
                    subject=subject,
                    title=title,
                    body=body,
                    template=template,
                    e_from=e_from,
                    reply_to=reply_to,
                    global_ctx=global_ctx,
                    attachment=attachment,
                    tags=tags,
                    company_id=company_id,
                )
            )

        await asyncio.gather(*coros)
        logger.info(
            '%d emails sent for trigger %s, company %s (%d)', len(user_data), trigger, company_domain, company_id
        )

    @concurrent('low')  # noqa: C901 (ignore complexity)
    async def record_email_event(self, raw_message: str):  # noqa: C901
        """
        record email events
        """
        message = json.loads(raw_message)
        msg_id = message['mail']['messageId']
        r = await self.pg.fetchrow('select id, user_id, update_ts from emails where ext_id=$1', msg_id)
        if not r:
            return
        email_id, user_id, last_updated = r

        event_type = message.get('eventType')
        extra = None
        data = message.get(event_type.lower()) or {}
        if event_type == 'Send':
            data = message['mail']
        elif event_type == 'Delivery':
            extra = {
                'delivery_time': data.get('processingTimeMillis'),
            }
        elif event_type == 'Open':
            extra = {
                'ip': data.get('ipAddress'),
                'ua': data.get('userAgent'),
            }
        elif event_type == 'Click':
            extra = {
                'link': data.get('link'),
                'ip': data.get('ipAddress'),
                'ua': data.get('userAgent'),
            }
        elif event_type == 'Bounce':
            extra = {
                'bounceType': data.get('bounceType'),
                'bounceSubType': data.get('bounceSubType'),
                'reportingMTA': data.get('reportingMTA'),
                'feedbackId': data.get('feedbackId'),
                'unsubscribe': data.get('bounceType') == 'Permanent',
            }
        elif event_type == 'Complaint':
            extra = {
                'complaintFeedbackType': data.get('complaintFeedbackType'),
                'feedbackId': data.get('feedbackId'),
                'ua': data.get('userAgent'),
                'unsubscribe': True,
            }
        else:
            logger.warning('unknown aws webhooks %s', event_type, extra={'data': {'message': message}})

        values = dict(email=email_id, status=event_type)
        ts = None
        if data.get('timestamp'):
            ts = parse_datetime(data['timestamp'])
            values['ts'] = ts
        if extra:
            values['extra'] = json.dumps({k: v for k, v in extra.items() if v})

        async with self.pg.acquire() as conn:
            await conn.execute_b('insert into email_events (:values__names) values :values', values=Values(**values))
            if not ts:
                await conn.execute(
                    'update emails set status=$1, update_ts=CURRENT_TIMESTAMP where id=$2', event_type, email_id
                )
            elif last_updated < ts:
                await conn.execute('update emails set status=$1, update_ts=$2 where id=$3', event_type, ts, email_id)

            if extra and extra.get('unsubscribe'):
                await conn.execute('update users set receive_emails=false where id=$1', user_id)

        return event_type


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


def clean_ctx(context, base_url):
    context = context or {}
    for key, value in context.items():
        if key.endswith('link') and isinstance(value, str):
            value = value or '/'
            assert value.startswith('/'), f'link field found which doesn\'t start "/". {key}: {value}'
            context[key] = base_url + value
        elif isinstance(value, datetime.datetime) or isinstance(value, datetime.date):
            context[key] = format_dt(value)
        elif isinstance(value, datetime.timedelta):
            context[key] = format_duration(value)
        elif isinstance(value, dict):
            context[key] = clean_ctx(value, base_url=base_url)
        elif isinstance(value, list):
            context[key] = [clean_ctx(v, base_url=base_url) for v in value]
    return context


markdown_macros = [
    {
        'name': 'primary_button',
        'args': ('text', 'link'),
        'body': '<div class="button">\n  <a href="{{ link }}"><span>{{ text }}</span></a>\n</div>\n',
    },
    {
        'name': 'secondary_button',
        'args': ('text', 'link'),
        'body': (
            '<div class="button">\n  <a href="{{ link }}"><span class="secondary">{{ text }}</span></a>\n</div>\n'
        ),
    },
]


def apply_macros(s):
    for macro in markdown_macros:

        def replace_macro(m):
            arg_values = [a.strip(' ') for a in m.group(1).split('|') if a.strip(' ')]
            if len(macro['args']) != len(arg_values):
                raise RuntimeError(f'invalid macro call "{m.group()}"')
            else:
                return chevron.render(macro['body'], data=dict(zip(macro['args'], arg_values)))

        s = re.sub(r'{{ ?%s\((.*?)\) ?}}' % macro['name'], replace_macro, s)
    return s
