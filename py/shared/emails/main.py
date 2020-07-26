import json
import logging
from datetime import date
from itertools import groupby
from operator import itemgetter

from arq import concurrent, cron
from buildpg import MultipleValues, Values

from shared.emails.utils import start_tz_duration

from ..actions import ActionTypes
from ..utils import (
    display_cash,
    display_cash_free,
    format_dt,
    format_duration,
    password_reset_link,
    static_map_link,
    ticket_id_signed,
    waiting_list_sig,
)
from .defaults import Triggers
from .plumbing import BaseEmailActor, UserEmail

logger = logging.getLogger('nosht.emails.main')


class EmailActor(BaseEmailActor):
    @concurrent
    async def send_event_conf(self, booked_action_id: int):
        """
        Send emails to buyer and other guests when someone books tickets.
        """
        async with self.pg.acquire() as conn:
            data = await conn.fetchrow(
                """
                SELECT a.user_id, e.id as event_id,
                  full_name(ub.first_name, ub.last_name) AS buyer_name,
                  full_name(uh.first_name, uh.last_name) AS host_name,
                  event_link(cat.slug, e.slug, e.public, $2) AS event_link, e.name, e.short_description,
                  cat.name AS cat_name, cat.slug AS cat_slug,
                  cat.ticket_extra_title AS ticket_extra_title,
                  e.location_name, e.location_lat, e.location_lng,
                  e.start_ts, e.duration, e.timezone, cat.company, co.currency, a.extra
                FROM actions AS a
                JOIN users AS ub ON a.user_id = ub.id
                JOIN events AS e ON a.event = e.id
                JOIN users AS uh ON e.host = uh.id
                JOIN categories AS cat ON e.category = cat.id
                JOIN companies co on cat.company = co.id
                WHERE a.id = $1
                """,
                booked_action_id,
                self.settings.auth_key,
            )
            tickets = await conn.fetch(
                """
                SELECT id, user_id, trim(BOTH FROM extra_info) as extra_info, price
                FROM tickets
                WHERE booked_action = $1 and user_id is not null
                """,
                booked_action_id,
            )
            # use max to get the price as they should all be the same
            ticket_count, total_ticket_price, extra_donated, price = await conn.fetchrow(
                'select count(*), sum(price), sum(extra_donated), max(price) from tickets where booked_action=$1',
                booked_action_id,
            )
            total_price = total_ticket_price and total_ticket_price + (extra_donated or 0)
        start, duration = start_tz_duration(data)
        ctx = {
            'event_link': data['event_link'],
            'event_name': data['name'],
            'event_short_description': data['short_description'],
            'event_start': start,
            'event_duration': duration or 'All day',
            'event_location': data['location_name'],
            'ticket_price': display_cash_free(price, data['currency']),
            'buyer_name': data['buyer_name'],
            'host_name': data['host_name'],
            'ticket_extra_title': data['ticket_extra_title'] or 'Extra Information',
            'category_name': data['cat_name'],
            is_cat(data['cat_slug']): True,
        }
        lat, lng = data['location_lat'], data['location_lng']
        if lat and lng:
            ctx.update(
                static_map=static_map_link(lat, lng, settings=self.settings),
                google_maps_url=f'https://www.google.com/maps/place/{lat},{lng}/@{lat},{lng},13z',
            )

        ctx_buyer = {
            **ctx,
            'ticket_count': ticket_count,
            'ticket_count_plural': ticket_count > 1,
            'extra_donated': extra_donated and display_cash_free(extra_donated, data['currency']),
            'total_price': display_cash_free(total_price, data['currency']),
        }
        if data['extra']:
            action_extra = json.loads(data['extra'])
            ctx_buyer['card_details'] = '{brand} {card_expiry} - ending {card_last4}'.format(**action_extra)

        buyer_user_id = data['user_id']
        buyer_emails = None
        other_emails = []
        for ticket_id, user_id, extra_info, _ in tickets:
            if buyer_user_id == user_id:
                ctx_buyer.update(
                    ticket_id=ticket_id_signed(ticket_id, self.settings), extra_info=extra_info,
                )
                buyer_emails = [UserEmail(user_id, ctx_buyer, ticket_id)]
            else:
                ctx_other = dict(**ctx, ticket_id=ticket_id_signed(ticket_id, self.settings), extra_info=extra_info)
                other_emails.append(UserEmail(user_id, ctx_other, ticket_id))

        if not buyer_emails:
            # unusual case where the buyer is not an attendee
            user_id = await self.pg.fetchval('select user_id from actions where id=$1', booked_action_id)
            buyer_emails = [UserEmail(user_id, ctx_buyer)]

        await self.send_emails.direct(
            data['company'], Triggers.ticket_buyer, buyer_emails, attached_event_id=data['event_id']
        )

        if other_emails:
            await self.send_emails.direct(
                data['company'], Triggers.ticket_other, other_emails, attached_event_id=data['event_id']
            )
        return len(other_emails) + 1

    @concurrent
    async def send_donation_thanks(self, action_id):
        async with self.pg.acquire() as conn:
            amount, gift_aid, user_id, extra, don_option_id, ticket_type_id = await conn.fetchrow(
                """
                SELECT
                  don.amount, don.gift_aid, a.user_id, a.extra, don.donation_option, don.ticket_type
                FROM donations AS don
                JOIN actions AS a ON don.action = a.id
                WHERE a.id = $1 and a.type = 'donate'
                """,
                action_id,
            )
            if don_option_id:
                donation_name, category_name, company_id, currency = await conn.fetchrow(
                    """
                    SELECT opt.name, cat.name, co.id, co.currency
                    FROM donation_options AS opt
                    JOIN categories cat ON opt.category = cat.id
                    JOIN companies co ON cat.company = co.id
                    WHERE opt.id=$1
                    """,
                    don_option_id,
                )
            else:
                donation_name, category_name, company_id, currency = await conn.fetchrow(
                    """
                    SELECT e.name, cat.name, co.id, co.currency
                    FROM ticket_types AS tt
                    JOIN events e ON tt.event = e.id
                    JOIN categories cat ON e.category = cat.id
                    JOIN companies co ON cat.company = co.id
                    WHERE tt.id=$1
                    """,
                    ticket_type_id,
                )
        action_extra = json.loads(extra)
        ctx = {
            'donation_option_name': donation_name,
            'gift_aid_enabled': gift_aid,
            'category_name': category_name,
            'amount_donated': display_cash_free(amount, currency),
            'card_details': '{brand} {card_expiry} - ending {card_last4}'.format(**action_extra),
        }
        await self.send_emails.direct(company_id, Triggers.donation_thanks, [UserEmail(user_id, ctx)])

    @concurrent
    async def send_account_created(self, user_id: int, created_by_admin=False):
        """
        Send an email to new user when their account is created (either by themselves or an admin).
        """
        async with self.pg.acquire() as conn:
            company_id, status, role = await conn.fetchrow(
                'SELECT company, status, role FROM users WHERE id=$1', user_id
            )
        ctx = dict(events_link='/dashboard/events/', created_by_admin=created_by_admin, is_admin=role == 'admin')
        if status == 'pending':
            ctx['confirm_email_link'] = password_reset_link(user_id, auth_fernet=self.auth_fernet)

        await self.send_emails.direct(company_id, Triggers.account_created, [UserEmail(id=user_id, ctx=ctx)])

    @concurrent
    async def send_event_created(self, action_id: int):
        """
        Send an email to all admins when an event is created and also an email to the event host.
        """
        async with self.pg.acquire() as conn:
            data = await conn.fetchrow(
                """
                SELECT a.company AS company_id, u.role AS host_role, u.id AS host_user_id,
                full_name(u.first_name, u.last_name, u.email) AS host_name,
                 e.id AS event_id, e.name AS event_name,
                 (e.start_ts AT TIME ZONE e.timezone)::date AS event_date,
                 cat.name AS cat_name, cat.slug AS cat_slug,
                 event_link(cat.slug, e.slug, e.public, $2) AS event_link
                FROM actions AS a
                JOIN users AS u ON a.user_id = u.id
                JOIN events AS e ON a.event = e.id
                JOIN categories AS cat ON e.category = cat.id
                WHERE a.id=$1
                """,
                action_id,
                self.settings.auth_key,
            )

            link = f'/dashboard/events/{data["event_id"]}/'
            ctx = dict(
                summary='{host_name} created an event "{event_name}"'.format(**data),
                details=(
                    'Event "{event_name}" ({cat_name}) created by "{host_name}" ({host_role}), '
                    'click the link below to view the event.'
                ).format(**data),
                action_label='View Event',
                action_link=link,
            )
            users = [
                UserEmail(id=r['id'], ctx=ctx)
                for r in await conn.fetch("SELECT id FROM users WHERE role='admin' AND company=$1", data['company_id'])
            ]
        await self.send_emails.direct(data['company_id'], Triggers.admin_notification, users)
        if data['host_role'] != 'admin':
            ctx = {
                'event_link': data['event_link'],
                'event_dashboard_link': link,
                'event_name': data['event_name'],
                'event_date': format_dt(data['event_date']),
                'category_name': data['cat_name'],
                is_cat(data['cat_slug']): True,
            }
            await self.send_emails.direct(
                data['company_id'], Triggers.event_host_created, [UserEmail(data['host_user_id'], ctx)]
            )

    @concurrent
    async def send_event_update(self, action_id):
        """
        Send an email to guests of an event as prompted by the host or an admin.
        """
        async with self.pg.acquire() as conn:
            data = await conn.fetchrow(
                """
                SELECT a.company AS company_id, e.id AS event_id, e.name AS event_name,
                  full_name(u.first_name, u.last_name, u.email) AS sender_name,
                  a.extra->>'subject' AS subject, a.extra->>'message' AS message,
                  event_link(cat.slug, e.slug, e.public, $2) AS event_link,
                  cat.name AS cat_name, cat.slug AS cat_slug
                FROM actions AS a
                JOIN users AS u ON a.user_id = u.id
                JOIN events AS e ON a.event = e.id
                JOIN categories AS cat ON e.category = cat.id
                WHERE a.id=$1
                """,
                action_id,
                self.settings.auth_key,
            )
            user_tickets = await conn.fetch(
                """
                SELECT DISTINCT user_id, id AS ticket_id
                FROM tickets
                WHERE status='booked' AND event=$1 AND user_id IS NOT NULL
                """,
                data['event_id'],
            )

        ctx = {
            'event_link': data['event_link'],
            'event_name': data['event_name'],
            'subject': data['subject'],
            'message': data['message'],
            'category_name': data['cat_name'],
            is_cat(data['cat_slug']): True,
        }
        users = [UserEmail(id=user_id, ctx=ctx, ticket_id=ticket_id) for user_id, ticket_id in user_tickets]
        await self.send_emails.direct(
            data['company_id'], Triggers.event_update, users, attached_event_id=data['event_id']
        )

    @concurrent
    async def send_tickets_available(self, event_id: int) -> str:
        """
        Send an email to those on the waiting list about an event
        """
        async with self.pg.acquire() as conn:
            tickets_remaining = await conn.fetchval(
                'SELECT check_tickets_remaining($1, $2)', event_id, self.settings.ticket_ttl
            )
            if tickets_remaining == 0:
                return 'no tickets remaining'

            user_ids = await conn.fetchval(
                """
                select array_agg(user_id) from waiting_list
                where event=$1 and now() - last_notified > '1 day'
                """,
                event_id,
            )
            if not user_ids:
                return 'no users in waiting list'

            data = await conn.fetchrow(
                """
                SELECT
                  c.company AS company_id,
                  e.name AS event_name,
                  event_link(c.slug, e.slug, e.public, $2) AS event_link,
                  e.start_ts > now() AS in_future
                FROM events AS e
                JOIN categories AS c ON e.category = c.id
                WHERE e.id=$1
                """,
                event_id,
                self.settings.auth_key,
            )
            if not data['in_future']:
                # don't send the email if the event is in the past
                return 'event in the past'

            await conn.execute_b(
                'INSERT INTO actions (:values__names) VALUES :values',
                values=Values(company=data['company_id'], event=event_id, type=ActionTypes.email_waiting_list.value),
            )
            # do this before sending emails so even if something fails we don't send lots of emails
            await conn.execute(
                'update waiting_list set last_notified=now() where event=$1 and user_id=any($2)', event_id, user_ids
            )
        ctx = {
            'event_link': data['event_link'],
            'event_name': data['event_name'],
        }

        def remove_link(user_id):
            return (
                f'/api/events/{event_id}/waiting-list/remove/{user_id}/'
                f'?sig={waiting_list_sig(event_id, user_id, self.settings)}'
            )

        users = [UserEmail(uid, {'remove_link': remove_link(uid), **ctx}) for uid in user_ids]
        await self.send_emails.direct(data['company_id'], Triggers.event_tickets_available, users)
        return f'emailed {len(user_ids)} users'

    @concurrent
    async def waiting_list_add(self, waiting_list_id: int):
        """
        Send an email to a user when they get added to the waiting list.
        """
        company_id, event_name, event_link, event_id, user_id = await self.pg.fetchrow(
            """
            select
              c.company,
              e.name,
              event_link(c.slug, e.slug, e.public, $2),
              e.id,
              w.user_id
            from waiting_list w
            join events e on w.event = e.id
            join categories AS c ON e.category = c.id
            where w.id=$1
            """,
            waiting_list_id,
            self.settings.auth_key,
        )

        sig = waiting_list_sig(event_id, user_id, self.settings)
        ctx = {
            'event_link': event_link,
            'event_name': event_name,
            'remove_link': f'/api/events/{event_id}/waiting-list/remove/{user_id}/?sig={sig}',
        }
        await self.send_emails.direct(company_id, Triggers.waiting_list_add, [UserEmail(user_id, ctx)])

    @cron(minute=30)
    async def send_event_reminders(self):
        """
        Send emails to guest of an event 24(ish) hours before the event is expected to start.
        """
        async with self.pg.acquire() as conn:
            # get events for which reminders need to be send
            events = await conn.fetch(
                """
                SELECT
                  e.id, e.name, e.short_description, e.start_ts, e.timezone, e.duration,
                  e.location_name, e.location_lat, e.location_lng,
                  cat.name AS cat_name, cat.slug AS cat_slug, cat.company AS company_id,
                  event_link(cat.slug, e.slug, e.public, $1) AS event_link,
                  full_name(uh.first_name, uh.last_name) AS host_name
                FROM events AS e
                JOIN users AS uh on e.host = uh.id
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
                """,
                self.settings.auth_key,
            )
            if not events:
                return 0
            # create the 'event-guest-reminder' action so the events won't receive multiple reminders
            await conn.execute_b(
                'INSERT INTO actions (:values__names) VALUES :values',
                values=MultipleValues(
                    *[
                        Values(company=e['company_id'], event=e['id'], type=ActionTypes.event_guest_reminder.value)
                        for e in events
                    ]
                ),
            )
            # get all users expecting the email for all events
            r = await conn.fetch(
                """
                SELECT DISTINCT event, user_id, id AS ticket_id
                FROM tickets
                WHERE status='booked' AND event=ANY($1)
                ORDER BY event
                """,
                {e['id'] for e in events},
            )
            # group the users by event
            users = {
                event_id: {(t['user_id'], t['ticket_id']) for t in g} for event_id, g in groupby(r, itemgetter('event'))
            }

        user_emails = 0
        for d in events:
            event_users = users.get(d['id'])
            if not event_users:
                continue
            start, duration = start_tz_duration(d)
            ctx = {
                'event_link': d['event_link'],
                'event_name': d['name'],
                'host_name': d['host_name'],
                'event_short_description': d['short_description'],
                'event_start': format_dt(start),
                'event_duration': format_duration(duration) if duration else 'All day',
                'event_location': d['location_name'],
                'category_name': d['cat_name'],
                is_cat(d['cat_slug']): True,
            }
            lat, lng = d['location_lat'], d['location_lng']
            if lat and lng:
                ctx.update(
                    static_map=static_map_link(lat, lng, settings=self.settings),
                    google_maps_url=f'https://www.google.com/maps/place/{lat},{lng}/@{lat},{lng},13z',
                )
            user_ctxs = [UserEmail(id=user_id, ctx=ctx, ticket_id=ticket_id) for user_id, ticket_id in event_users]
            await self.send_emails(
                d['company_id'], Triggers.event_reminder.value, user_ctxs, attached_event_id=d['id'],
            )
            user_emails += len(event_users)
        return user_emails

    @cron(hour=7, minute=30)
    async def send_event_host_updates(self):
        """
        Send emails to hosts of events every day before the event with details of bookings.
        """
        async with self.pg.acquire() as conn:
            # get events for which updates need to be sent
            events = await conn.fetch(
                """
                SELECT
                  e.id, e.name, (e.start_ts AT TIME ZONE e.timezone)::date AS event_date, e.host AS host_user_id,
                  event_link(cat.slug, e.slug, e.public, $1) AS event_link,
                  cat.name AS cat_name, cat.slug AS cat_slug,
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
                """,
                self.settings.auth_key,
            )

        if not events:
            return 0

        today = date.today()
        user_emails = 0
        pool = await self.get_redis()
        cache_time = 23 * 3600
        with await pool as redis:
            for company_id, g in groupby(events, itemgetter('company_id')):
                user_ctxs = []
                for e in g:
                    if e['event_date'] == today:
                        # don't send an update on the day of an event, that's event_host_final_update
                        continue
                    days_to_go = (e['event_date'] - today).days
                    if days_to_go > 14 and not e['tickets_booked_24h']:
                        continue
                    key = 'event-host-update:{}'.format(e['id'])
                    if await redis.get(key):
                        continue
                    await redis.setex(key, cache_time, 1)
                    ctx = {
                        'event_link': e['event_link'],
                        'event_dashboard_link': f'/dashboard/events/{e["id"]}/',
                        'event_name': e['name'],
                        'ticket_limit': e['ticket_limit'],
                        'fully_booked': e['tickets_booked'] == e['ticket_limit'],
                        'event_date': format_dt(e['event_date']),
                        'days_to_go': days_to_go,
                        'total_income': display_cash(e['total_income'], e['currency']) if e['total_income'] else None,
                        'tickets_booked': e['tickets_booked'] or 0,
                        'tickets_booked_24h': e['tickets_booked_24h'] or 0,
                        'category_name': e['cat_name'],
                        is_cat(e['cat_slug']): True,
                    }
                    user_ctxs.append(UserEmail(id=e['host_user_id'], ctx=ctx))

                if user_ctxs:
                    user_emails += len(user_ctxs)
                    await self.send_emails.direct(company_id, Triggers.event_host_update.value, user_ctxs)
        return user_emails

    @cron(minute={5, 35})  # run twice per hour to make sure of sending if something is wrong at one send time
    async def send_event_host_updates_final(self):
        """
        Send an email to the host of an event 4-5 hours before the event is scheduled to start.
        """
        async with self.pg.acquire() as conn:
            # get events for which updates need to be sent
            events = await conn.fetch(
                """
                SELECT
                  e.id, e.name, e.host AS host_user_id,
                  event_link(cat.slug, e.slug, e.public, $1) AS event_link,
                  cat.name AS cat_name, cat.slug AS cat_slug,
                  cat.company AS company_id
                FROM events AS e
                JOIN categories AS cat ON e.category = cat.id
                WHERE e.status = 'published' AND
                      e.start_ts BETWEEN now() + '4 hours'::interval AND now() + '5 hours'::interval
                ORDER BY cat.company
                """,
                self.settings.auth_key,
            )
            if not events:
                return 0

            user_emails = 0
            pool = await self.get_redis()
            cache_time = 24 * 3600
            booked_stmt = await conn.prepare("SELECT count(*) FROM tickets WHERE status='booked' AND event=$1")
            with await pool as redis:
                for company_id, g in groupby(events, itemgetter('company_id')):
                    user_ctxs = []
                    for e in g:
                        key = 'event-host-final-update:{}'.format(e['id'])
                        if await redis.get(key):
                            continue
                        await redis.setex(key, cache_time, 1)
                        # better to do this as a single query here when required than call it every time
                        tickets_booked = await booked_stmt.fetchval(e['id'])
                        ctx = {
                            'event_link': e['event_link'],
                            'event_dashboard_link': f'/dashboard/events/{e["id"]}/',
                            'event_name': e['name'],
                            'tickets_booked': tickets_booked or 0,
                            'category_name': e['cat_name'],
                            is_cat(e['cat_slug']): True,
                        }
                        user_ctxs.append(UserEmail(id=e['host_user_id'], ctx=ctx))

                    if user_ctxs:
                        user_emails += len(user_ctxs)
                        await self.send_emails.direct(company_id, Triggers.event_host_final_update.value, user_ctxs)
        return user_emails


def is_cat(slug):
    return 'is_category_{}'.format(slug.replace('-', '_'))
