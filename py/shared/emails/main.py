import json
import logging
from datetime import date, timedelta
from itertools import groupby
from operator import itemgetter
from typing import Optional

from arq import concurrent, cron
from buildpg import MultipleValues, Values

from ..actions import ActionTypes
from ..utils import display_cash, display_cash_free, format_duration, password_reset_link, static_map_link, ticket_ref
from .defaults import Triggers
from .plumbing import BaseEmailActor, UserEmail, date_fmt, datetime_fmt

logger = logging.getLogger('nosht.email.main')


class EmailActor(BaseEmailActor):
    @concurrent
    async def send_event_conf(self, booked_action_id: int):
        async with self.pg.acquire() as conn:
            data = await conn.fetchrow(
                """
                SELECT t.user_id,
                  full_name(u.first_name, u.last_name, u.email) AS user_name,
                  '/' || cat.slug || '/' || e.slug || '/' as event_link, e.name, e.short_description,
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
            r = await conn.fetch(
                'SELECT user_id, id FROM tickets WHERE booked_action=$1 AND user_id IS NOT NULL',
                booked_action_id
            )
            other_user_ids = {r_[0] for r_ in r}
            other_user_ids.remove(buyer_user_id)

            ticket_id_lookup = {u_id: t_id for u_id, t_id in r}

        duration: Optional[timedelta] = data['duration']
        ctx = {
            'event_link': data['event_link'],
            'event_name': data['name'],
            'event_short_description': data['short_description'],
            'event_start': data['start_ts'] if duration else data['start_ts'].date(),
            'event_duration': duration or 'All day',
            'event_location': data['location_name'],
            'ticket_price': display_cash_free(data['price'], data['currency']),
            'buyer_name': data['user_name'],
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
            [self._ue_with_ref(buyer_user_id, ctx_buyer, ticket_id_lookup[buyer_user_id])]
        )
        if other_user_ids:
            await self.send_emails.direct(
                data['company'],
                Triggers.ticket_other,
                [self._ue_with_ref(user_id, ctx, ticket_id_lookup[user_id]) for user_id in other_user_ids]
            )

    def _ue_with_ref(self, user_id, ctx, ticket_id):
        ctx_ = {**ctx, 'ticket_ref': ticket_ref(ticket_id, self.settings)}
        return UserEmail(id=user_id, ctx=ctx_, ticket_id=ticket_id)

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
                SELECT a.company, full_name(u.first_name, u.last_name, u.email), u.role,
                 e.name, cat.name, '/' || cat.slug || '/' || e.slug || '/'
                FROM actions AS a
                JOIN users AS u ON a.user_id = u.id
                JOIN events AS e ON a.event = e.id
                JOIN categories AS cat ON e.category = cat.id
                WHERE a.id=$1
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

    @concurrent
    async def send_event_update(self, action_id):
        async with self.pg.acquire() as conn:
            company_id, event_id, sender_name, event_name, subject, message, event_link = await conn.fetchrow(
                """
                SELECT a.company, e.id, full_name(u.first_name, u.last_name, u.email), e.name,
                  a.extra->>'subject', a.extra->>'message', '/' || cat.slug || '/' || e.slug || '/'
                FROM actions AS a
                JOIN users AS u ON a.user_id = u.id
                JOIN events AS e ON a.event = e.id
                JOIN categories AS cat ON e.category = cat.id
                WHERE a.id=$1
                """,
                action_id
            )
            user_tickets = await conn.fetch(
                """
                SELECT DISTINCT user_id, id AS ticket_id
                FROM tickets
                WHERE status='booked' AND event=$1 AND user_id IS NOT NULL
                """, event_id
            )

        ctx = {
            'event_link': event_link,
            'event_name': event_name,
            'subject': subject,
            'message': message,
        }
        users = [UserEmail(id=user_id, ctx=ctx, ticket_id=ticket_id) for user_id, ticket_id in user_tickets]
        await self.send_emails.direct(company_id, Triggers.event_update, users)

    @cron(minute=30)
    async def send_event_reminders(self):
        async with self.pg.acquire() as conn:
            # get events for which reminders need to be send
            events = await conn.fetch(
                """
                SELECT
                  e.id, e.name, e.short_description, e.start_ts, e.duration,
                  e.location_name, e.location_lat, e.location_lng,
                  cat.company AS company_id,
                  '/' || cat.slug || '/' || e.slug || '/' as event_link
                FROM events AS e
                JOIN categories AS cat ON e.category = cat.id
                WHERE e.status='published' AND
                      e.start_ts BETWEEN now() AND now() + '24 hours'::interval AND
                      e.id NOT IN (
                        SELECT event
                        FROM actions
                        WHERE type='event-guest-reminder' AND
                              ts > now() - '25 hours'::interval
                      )
                ORDER BY cat.company
                """
            )
            if not events:
                return 0
            # create the 'event-guest-reminder' action so the events won't receive multiple reminders
            await conn.execute_b(
                'INSERT INTO actions (:values__names) VALUES :values',
                values=MultipleValues(*[
                    Values(
                        company=e['company_id'],
                        event=e['id'],
                        type=ActionTypes.event_guest_reminder.value,
                    ) for e in events
                ]),
            )
            # get all users expecting the email for all events
            r = await conn.fetch(
                """
                SELECT DISTINCT event, user_id, id AS ticket_id
                FROM tickets
                WHERE status='booked' AND event=ANY($1)
                ORDER BY event
                """, {e['id'] for e in events}
            )
            # group the users by event
            users = {
                event_id: {(t['user_id'], t['ticket_id']) for t in g}
                for event_id, g in groupby(r, itemgetter('event'))
            }

        user_emails = 0
        for company_id, g in groupby(events, itemgetter('company_id')):
            user_ctxs = []
            for d in g:
                event_users = users.get(d['id'])
                if not event_users:
                    continue
                duration = d['duration']
                ctx = {
                    'event_link': d['event_link'],
                    'event_name': d['name'],
                    'event_short_description': d['short_description'],
                    'event_start': (
                        d['start_ts'].strftime(datetime_fmt) if duration else d['start_ts'].strftime(date_fmt)
                    ),
                    'event_duration': format_duration(duration) if duration else 'All day',
                    'event_location': d['location_name'],
                }
                lat, lng = d['location_lat'], d['location_lng']
                if lat and lng:
                    ctx.update(
                        static_map=static_map_link(lat, lng, settings=self.settings),
                        google_maps_url=f'https://www.google.com/maps/place/{lat},{lng}/@{lat},{lng},13z',
                    )
                user_ctxs.extend([
                    UserEmail(id=user_id, ctx=ctx, ticket_id=ticket_id) for user_id, ticket_id in event_users
                ])
            user_emails += len(user_ctxs)
            await self.send_emails(company_id, Triggers.event_reminder.value, user_ctxs)
        return user_emails

    @cron(hour=7, minute=30)
    async def send_event_host_updates(self):
        async with self.pg.acquire() as conn:
            # get events for which updates need to be sent
            events = await conn.fetch(
                """
                SELECT
                  e.id, e.name, e.short_description, e.start_ts::date AS event_date, e.host AS host_user_id,
                  '/' || cat.slug || '/' || e.slug || '/' as link,
                  cat.company AS company_id, co.currency AS currency,
                  t_all.tickets_booked, e.ticket_limit, t_all.total_income, t_recent.tickets_booked_24h
                FROM events AS e
                JOIN categories AS cat ON e.category = cat.id
                JOIN companies AS co ON cat.company = co.id
                LEFT JOIN (
                  -- TODO I think this subquery will be called for ALL tickets, could filter the subquery
                  -- same as the main query is filtered
                  SELECT event, count(id) AS tickets_booked, sum(price) AS total_income
                  FROM tickets
                  WHERE status = 'booked'
                  GROUP BY event
                ) AS t_all ON e.id = t_all.event
                LEFT JOIN (
                  SELECT event, COUNT(id) AS tickets_booked_24h
                  FROM tickets
                  WHERE created_ts > now() - '1 day'::interval AND
                        status = 'booked'
                  GROUP BY event
                ) AS t_recent ON e.id = t_recent.event
                WHERE e.status = 'published' AND
                      e.start_ts BETWEEN now() AND now() + '30 days'::interval
                ORDER BY cat.company
                """
            )

        if not events:
            return 0

        today = date.today()
        user_emails = 0
        for company_id, g in groupby(events, itemgetter('company_id')):
            user_ctxs = []
            for e in g:
                if e['event_date'] == today:
                    # don't send an update on the day of an event, that's event_host_final_update
                    continue
                ctx = dict(
                    link=e['link'],
                    name=e['name'],
                    ticket_limit=e['ticket_limit'],
                    fully_booked=e['tickets_booked'] == e['ticket_limit'],
                    event_date=e['event_date'].strftime(date_fmt),
                    days_to_go=(e['event_date'] - today).days,
                    total_income=display_cash(e['total_income'], e['currency']) if e['total_income'] else None,
                    tickets_booked=e['tickets_booked'] or 0,
                    tickets_booked_24h=e['tickets_booked_24h'] or 0,
                )
                user_ctxs.append(UserEmail(id=e['host_user_id'], ctx=ctx))

            if user_ctxs:
                user_emails += len(user_ctxs)
                await self.send_emails.direct(company_id, Triggers.event_host_update.value, user_ctxs)
        return user_emails
