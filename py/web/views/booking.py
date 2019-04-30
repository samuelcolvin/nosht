import logging
from time import time
from typing import List

from asyncpg import CheckViolationError
from buildpg import MultipleValues, Values
from buildpg.asyncpg import BuildPgConnection
from pydantic import BaseModel, EmailStr, constr, validator

from web.actions import ActionTypes, record_action, record_action_id
from web.auth import check_session, is_auth
from web.bread import UpdateView
from web.stripe import BookFreeModel, Reservation, StripeBuyModel, book_free, stripe_buy
from web.utils import JsonErrors, decrypt_json, encrypt_json, json_response

from .events import check_event_sig

logger = logging.getLogger('nosht.booking')


class UpdateViewAuth(UpdateView):
    async def check_permissions(self):
        await check_session(self.request, 'admin', 'host', 'guest')


@is_auth
async def booking_info(request):
    event_id = await check_event_sig(request)

    conn: BuildPgConnection = request['conn']
    settings = request.app['settings']
    tickets_remaining = await conn.fetchval('SELECT check_tickets_remaining($1, $2)', event_id, settings.ticket_ttl)
    existing_tickets = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM tickets
        JOIN actions AS a ON tickets.reserve_action = a.id
        WHERE tickets.event=$1 AND a.user_id=$2 AND status='booked'
        """,
        event_id,
        request['session']['user_id']
    )
    ticket_types = await conn.fetch('SELECT id, name, price::float FROM ticket_types WHERE event=$1', event_id)
    return json_response(
        tickets_remaining=tickets_remaining if (tickets_remaining and tickets_remaining < 10) else None,
        existing_tickets=existing_tickets or 0,
        ticket_types=[dict(tt) for tt in ticket_types],
    )


class TicketModel(BaseModel):
    t: bool
    first_name: constr(max_length=255) = None
    last_name: constr(max_length=255) = None
    email: EmailStr = None
    extra_info: str = None
    allow_marketing: bool = None
    cover_costs: bool = False


class ReserveTickets(UpdateViewAuth):
    class Model(BaseModel):
        tickets: List[TicketModel]
        ticket_type: int

        @validator('tickets', whole=True)
        def check_ticket_count(cls, v):
            if not v:
                raise ValueError('at least one ticket must be purchased')
            return v

    async def execute(self, m: Model):
        event_id = int(self.request.match_info['id'])
        ticket_count = len(m.tickets)

        if ticket_count > self.settings.max_tickets:
            raise JsonErrors.HTTPBadRequest(message='Too many tickets reserved')

        user_id = self.session['user_id']

        status, external_ticket_url, event_name, cover_costs_percentage = await self.conn.fetchrow(
            """
            SELECT e.status, e.external_ticket_url, e.name, c.cover_costs_percentage
            FROM events AS e
            JOIN categories c on e.category = c.id
            WHERE c.company=$1 AND e.id=$2
            """,
            self.request['company_id'], event_id
        )

        if status != 'published':
            raise JsonErrors.HTTPBadRequest(message='Event not published')

        if external_ticket_url is not None:
            raise JsonErrors.HTTPBadRequest(message='Cannot reserve ticket for an externally ticketed event')

        r = await self.conn.fetchrow('SELECT price FROM ticket_types WHERE event=$1 AND id=$2',
                                     event_id, m.ticket_type)
        if not r:
            raise JsonErrors.HTTPBadRequest(message='Ticket type not found')
        item_price, *_ = r

        if self.settings.ticket_reservation_precheck:  # should only be false during CheckViolationError tests
            tickets_remaining = await self.conn.fetchval(
                'SELECT check_tickets_remaining($1, $2)', event_id, self.settings.ticket_ttl
            )
            if tickets_remaining is not None and ticket_count > tickets_remaining:
                raise JsonErrors.HTTP470(message=f'only {tickets_remaining} tickets remaining',
                                         tickets_remaining=tickets_remaining)

        total_price, item_extra_donated = None, None
        if item_price:
            total_price = item_price * ticket_count
            if cover_costs_percentage and m.tickets[0].cover_costs:
                item_extra_donated = item_price * cover_costs_percentage / 100
                total_price += item_extra_donated * ticket_count

        try:
            async with self.conn.transaction():
                update_user_preferences = await self.create_users(m.tickets)

                action_id = await record_action_id(self.request, user_id, ActionTypes.reserve_tickets,
                                                   event_id=event_id)
                ticket_values = [
                    Values(
                        email=t.email and t.email.lower(),
                        first_name=t.first_name,
                        last_name=t.last_name,
                        extra_info=t.extra_info or None,
                    )
                    for t in m.tickets
                ]

                await self.conn.execute_b(
                    """
                    WITH v (email, first_name, last_name, extra_info) AS (VALUES :values)
                    INSERT INTO tickets (event, reserve_action, ticket_type, price, extra_donated, user_id,
                      first_name, last_name, extra_info)
                    SELECT :event, :reserve_action, :ticket_type, :price, :extra_donated, u.id,
                      v.first_name, v.last_name, v.extra_info FROM v
                    LEFT JOIN users AS u ON v.email=u.email AND u.company=:company_id
                    """,
                    event=event_id,
                    reserve_action=action_id,
                    ticket_type=m.ticket_type,
                    price=item_price,
                    extra_donated=item_extra_donated,
                    company_id=self.request['company_id'],
                    values=MultipleValues(*ticket_values),
                )
                await self.conn.execute('SELECT check_tickets_remaining($1, $2)', event_id, self.settings.ticket_ttl)
        except CheckViolationError as exc:
            if exc.constraint_name != 'ticket_limit_check':  # pragma: no branch
                raise  # pragma: no cover
            logger.warning('CheckViolationError: %s', exc)
            raise JsonErrors.HTTPBadRequest(message='insufficient tickets remaining')

        res = Reservation(
            user_id=user_id,
            action_id=action_id,
            price_cent=total_price and int(total_price * 100),
            event_id=event_id,
            ticket_count=ticket_count,
            event_name=event_name,
        )
        if update_user_preferences:
            # has to happen after the transactions is finished
            await self.app['donorfy_actor'].update_user(self.request['session']['user_id'], update_user=False)
        return {
            'booking_token': encrypt_json(self.app, res.dict()),
            'ticket_count': ticket_count,
            'item_price': item_price and float(item_price),
            'extra_donated': item_extra_donated and float(item_extra_donated * ticket_count),
            'total_price': total_price and float(total_price),
            'timeout': int(time()) + self.settings.ticket_ttl,
        }

    async def create_users(self, tickets: List[TicketModel]):
        user_values = [
            Values(
                company=self.request['company_id'],
                role='guest',
                email=t.email.lower(),
            ) for t in tickets if t.email
        ]
        if not user_values:
            return

        await self.conn.execute_b(
            """
            INSERT INTO users AS u (:values__names) VALUES :values
            ON CONFLICT (company, email) DO NOTHING
            """,
            values=MultipleValues(*user_values)
        )
        if tickets[0].allow_marketing is not None and tickets[0].email == await self._user_email():
            await self.conn.execute(
                'UPDATE users SET allow_marketing=$1 WHERE id=$2',
                tickets[0].allow_marketing, self.request['session']['user_id']
            )
            return True

    async def _user_email(self):
        return await self.conn.fetchval('SELECT email FROM users WHERE id=$1', self.request['session']['user_id'])


class CancelReservedTickets(UpdateView):
    class Model(BaseModel):
        booking_token: bytes

    async def execute(self, m: Model):
        # no ttl since a user may try to cancel a reservation after it has expired
        res = Reservation(**decrypt_json(self.app, m.booking_token))
        async with self.conn.transaction():
            user_id = await self.conn.fetchval('SELECT user_id FROM actions WHERE id=$1', res.action_id)
            v = await self.conn.execute(
                "DELETE FROM tickets WHERE reserve_action=$1 AND status='reserved'",
                res.action_id
            )
            if v == 'DELETE 0':
                # no tickets were deleted
                raise JsonErrors.HTTPBadRequest(message='no tickets deleted')
            await self.conn.execute('SELECT check_tickets_remaining($1, $2)', res.event_id, self.settings.ticket_ttl)
            await record_action(self.request, user_id, ActionTypes.cancel_reserved_tickets, event_id=res.event_id)


class BuyTickets(UpdateView):
    Model = StripeBuyModel

    async def execute(self, m: StripeBuyModel):
        booked_action_id, source_hash = await stripe_buy(m, self.request['company_id'], self.session.get('user_id'),
                                                         self.app, self.conn)
        await self.app['donorfy_actor'].tickets_booked(booked_action_id)
        await self.app['email_actor'].send_event_conf(booked_action_id)
        return {'source_hash': source_hash}


class BookFreeTickets(UpdateView):
    Model = BookFreeModel

    async def execute(self, m: BookFreeModel):
        booked_action_id = await book_free(m, self.request['company_id'], self.session, self.app, self.conn)
        await self.app['donorfy_actor'].tickets_booked(booked_action_id)
        await self.app['email_actor'].send_event_conf(booked_action_id)
