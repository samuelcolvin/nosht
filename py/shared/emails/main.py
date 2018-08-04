import datetime
import json
import logging
from typing import Optional

from arq import concurrent

from ..utils import display_cash_free, password_reset_link, static_map_link
from .defaults import Triggers
from .plumbing import BaseEmailActor, UserEmail

logger = logging.getLogger('nosht.email.main')


class EmailActor(BaseEmailActor):
    @concurrent
    async def send_event_conf(self, booked_action_id: int):
        async with self.pg.acquire() as conn:
            data = await conn.fetchrow(
                """
                SELECT t.user_id,
                  full_name(u.first_name, u.last_name, u.email) AS user_name,
                  e.slug, cat.slug as cat_slug, e.name, e.short_description,
                  e.location_name, e.location_lat, e.location_lng,
                  e.start_ts, e.duration, tt.price, cat.company, co.currency, a.extra
                FROM tickets AS t
                JOIN actions AS a ON t.booked_action = a.id
                JOIN users AS u ON t.user_id = u.id
                JOIN ticket_types AS tt ON t.ticket_type = tt.id
                JOIN events AS e ON t.event = e.id
                JOIN categories AS cat ON e.category = cat.id
                JOIN companies co on cat.company = co.id
                WHERE t.booked_action=$1
                LIMIT 1
                """,
                booked_action_id
            )
            buyer_user_id = data['user_id']
            r = await conn.fetch('SELECT user_id FROM tickets WHERE booked_action=$1', booked_action_id)
            other_user_ids = {r_[0] for r_ in r}
            other_user_ids.remove(buyer_user_id)

        duration: Optional[datetime.timedelta] = data['duration']
        ctx = {
            'event_link': '/{cat_slug}/{slug}/'.format(**data),
            'event_name': data['name'],
            'event_short_description': data['short_description'],
            'event_start': data['start_ts'] if duration else data['start_ts'].date(),
            'event_duration': duration or 'All day',
            'event_location': data['location_name'],
            'ticket_price': display_cash_free(data['price'], data['currency']),
            'buyer_name': data['user_name']
        }
        lat, lng = data['location_lat'], data['location_lng']
        if lat and lng:
            ctx.update(
                static_map=static_map_link(lat, lng, settings=self.settings),
                google_maps_url=f'https://www.google.com/maps/place/{lat},{lng}/@{lat},{lng},13z',
            )

        ticket_count = len(other_user_ids) + 1
        ctx_buyer = {
            **ctx,
            'ticket_count': ticket_count,
            'ticket_count_plural': ticket_count > 1,
            'total_price': display_cash_free(data['price'] and data['price'] * ticket_count, data['currency']),
        }
        if data['extra']:
            action_extra = json.loads(data['extra'])
            ctx_buyer['card_details'] = '{card_expiry} - ending {card_last4}'.format(**action_extra)

        await self.send_emails.direct(
            data['company'],
            Triggers.ticket_buyer,
            [UserEmail(id=buyer_user_id, ctx=ctx_buyer)]
        )
        if other_user_ids:
            await self.send_emails.direct(
                data['company'],
                Triggers.ticket_other,
                [UserEmail(id=user_id, ctx=ctx) for user_id in other_user_ids]
            )

    @concurrent
    async def send_account_created(self, user_id: int, created_by_admin=False):
        async with self.pg.acquire() as conn:
            company_id, status, role = await conn.fetchrow(
                'SELECT company, status, role FROM users WHERE id=$1',
                user_id
            )
        ctx = dict(
            events_link='/dashboard/events/',
            created_by_admin=created_by_admin,
            is_admin=role == 'admin',
        )
        if status == 'pending':
            ctx['confirm_email_link'] = password_reset_link(user_id, auth_fernet=self.auth_fernet)

        await self.send_emails.direct(company_id, Triggers.account_created, [UserEmail(id=user_id, ctx=ctx)])

    @concurrent
    async def send_event_created_note(self, action_id: int):
        async with self.pg.acquire() as conn:
            company_id, host_name, host_role, event_name, cat_name, link = await conn.fetchrow(
                """
                SELECT actions.company, full_name(u.first_name, u.last_name, u.email), u.role,
                 e.name, cat.name, '/' || cat.slug || '/' || e.slug || '/'
                FROM actions
                JOIN users AS u ON actions.user_id = u.id
                JOIN events AS e ON (extra->>'event_id')::int = e.id
                JOIN categories AS cat ON e.category = cat.id
                WHERE actions.id=$1
                """,
                action_id
            )

            ctx = dict(
                summary='Event Created',
                details=(
                    f'Event "{event_name}" ({cat_name}) created by "{host_name}" ({host_role}), '
                    f'click the link below to view the event.'
                ),
                action_label='View Event',
                action_link=link,
            )
            users = [
                UserEmail(id=r['id'], ctx=ctx) for r in
                await conn.fetch("SELECT id FROM users WHERE role='admin' AND company=$1", company_id)
            ]
        await self.send_emails.direct(company_id, Triggers.admin_notification, users)
