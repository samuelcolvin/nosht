import json
import logging
from pathlib import Path

from buildpg import V
from buildpg.clauses import Join, Where
from pydantic import BaseModel, condecimal, confloat, constr

from shared.actions import ActionTypes
from shared.images import delete_image, upload_other
from web.actions import record_action_id
from web.auth import check_session, is_admin, is_auth
from web.bread import Bread
from web.stripe import stripe_payment_intent
from web.utils import JsonErrors, json_response, raw_json_response, request_image

from .booking import UpdateViewAuth

logger = logging.getLogger('nosht.booking')


@is_auth
async def donation_after_prepare(request):
    donation_option_id = int(request.match_info['don_opt_id'])
    event_id = int(request.match_info['event_id'])
    conn = request['conn']
    r = await conn.fetchrow(
        """
        SELECT opt.name, opt.amount, cat.id
        FROM donation_options AS opt
        JOIN categories AS cat ON opt.category = cat.id
        WHERE opt.id = $1 AND opt.live AND cat.company = $2
        """,
        donation_option_id,
        request['company_id'],
    )
    if not r:
        raise JsonErrors.HTTPBadRequest(message='donation option not found')

    name, amount, cat_id = r
    event = await conn.fetchval('SELECT 1 FROM events WHERE id=$1 AND category=$2', event_id, cat_id)
    if not event:
        raise JsonErrors.HTTPBadRequest(message='event not found on the same category as donation_option')

    user_id = request['session']['user_id']
    action_id = await record_action_id(
        request, user_id, ActionTypes.donate_prepare, event_id=event_id, donation_option_id=donation_option_id
    )

    client_secret = await stripe_payment_intent(
        user_id=user_id,
        price_cents=int(amount * 100),
        description=f'donation to {name} ({donation_option_id}) after booking',
        metadata={'purpose': 'donate', 'event_id': event_id, 'reserve_action_id': action_id, 'user_id': user_id},
        company_id=request['company_id'],
        idempotency_key=f'idempotency-donate-{action_id}',
        app=request.app,
        conn=conn,
    )
    return json_response(client_secret=client_secret, action_id=action_id)


class PrepareDirectDonation(UpdateViewAuth):
    class Model(BaseModel):
        custom_amount: confloat(ge=1, le=1000)

    async def execute(self, m: Model):
        ticket_type_id = int(self.request.match_info['tt_id'])
        user_id = self.session['user_id']

        r = await self.conn.fetchrow(
            """
            SELECT tt.price, tt.custom_amount, e.id, e.name
            FROM ticket_types tt
            JOIN events e ON tt.event = e.id
            WHERE tt.active=TRUE AND tt.mode='donation' AND tt.id=$1 AND status = 'published' AND
              external_ticket_url IS NULL AND external_donation_url IS NULL
            """,
            ticket_type_id,
        )
        if not r:
            raise JsonErrors.HTTPBadRequest(message='Ticket type not found')
        donation_amount, custom_amount_tt, event_id, event_name = r

        if custom_amount_tt:
            donation_amount = m.custom_amount

        action_id = await record_action_id(
            self.request,
            user_id,
            ActionTypes.donate_direct_prepare,
            event_id=event_id,
            ticket_type_id=ticket_type_id,
            donation_amount=float(donation_amount),
        )

        client_secret = await stripe_payment_intent(
            user_id=user_id,
            price_cents=int(donation_amount * 100),
            description=f'donation to {event_name} (id {event_id}, ticket type {ticket_type_id})',
            metadata={
                'purpose': 'donate-direct',
                'event_id': event_id,
                'reserve_action_id': action_id,
                'user_id': user_id,
            },
            company_id=self.request['company_id'],
            idempotency_key=f'idempotency-donate-direct-{action_id}',
            app=self.request.app,
            conn=self.conn,
        )
        return dict(client_secret=client_secret, action_id=action_id)


class DonationGiftAid(UpdateViewAuth):
    class Model(BaseModel):
        title: constr(max_length=31)
        first_name: constr(max_length=255)
        last_name: constr(max_length=255)
        address: constr(max_length=255)
        city: constr(max_length=255)
        postcode: constr(max_length=31)

    async def execute(self, m: Model):
        action_id = int(self.request.match_info['action_id'])
        v = await self.conn.execute(
            'update actions set extra=extra || $3 where id=$1 and user_id=$2',
            action_id,
            self.session['user_id'],
            json.dumps({'gift_aid': m.dict()}),
        )
        if v != 'UPDATE 1':
            raise JsonErrors.HTTPNotFound(message='action not found')


class DonationOptionBread(Bread):
    class Model(BaseModel):
        category: int
        name: constr(max_length=255)
        amount: condecimal(ge=1, max_digits=6, decimal_places=2)
        live: bool = True
        short_description: str
        long_description: str
        sort_index: int = None

    browse_enabled = True
    retrieve_enabled = True
    edit_enabled = True
    add_enabled = True
    delete_enabled = True

    model = Model
    table = 'donation_options'
    table_as = 'opt'
    browse_order_by_fields = 'opt.category', 'opt.sort_index', 'opt.amount'
    browse_fields = (
        'opt.id',
        'opt.name',
        V('cat.name').as_('category_name'),
        'opt.live',
        'opt.amount',
    )
    retrieve_fields = browse_fields + (
        'opt.category',
        'opt.sort_index',
        'opt.short_description',
        'opt.long_description',
        'opt.image',
    )

    async def check_permissions(self, method):
        await check_session(self.request, 'admin')

    def where(self):
        return Where(V('cat.company') == self.request['company_id'])

    def join(self):
        return Join(V('categories').as_('cat').on(V('cat.id') == V('opt.category')))


IMAGE_SIZE = 640, 480


@is_admin
async def donation_image_upload(request):
    co_id = request['company_id']
    don_opt_id = int(request.match_info['pk'])
    r = await request['conn'].fetchrow(
        """
        SELECT co.slug, cat.slug, d.image
        FROM donation_options AS d
        JOIN categories AS cat ON d.category = cat.id
        JOIN companies AS co ON cat.company = co.id
        WHERE d.id = $1 AND cat.company = $2
        """,
        don_opt_id,
        co_id,
    )
    if not r:
        raise JsonErrors.HTTPNotFound(message='donation option not found')

    co_slug, cat_slug, old_image = r
    content = await request_image(request, expected_size=IMAGE_SIZE)

    upload_path = Path(co_slug) / cat_slug / str(don_opt_id)
    image_url = await upload_other(
        content, upload_path=upload_path, settings=request.app['settings'], req_size=IMAGE_SIZE, thumb=True,
    )

    await request['conn'].execute('UPDATE donation_options SET image=$1 WHERE id=$2', image_url, don_opt_id)

    if old_image:
        await delete_image(old_image, request.app['settings'])
    return json_response(status='success')


donation_options_sql = """
SELECT json_build_object(
  'donation_options', donation_options,
  'post_booking_message', post_booking_message
)
FROM (
  SELECT post_booking_message
  FROM categories
  WHERE company = $1 AND id = $2
) AS post_booking_message,
(
  SELECT coalesce(array_to_json(array_agg(row_to_json(t))), '[]') AS donation_options FROM (
    SELECT d.id, d.name, d.amount, d.image, d.short_description, d.long_description
    FROM donation_options AS d
    JOIN categories AS CAT ON d.category = cat.id
    WHERE cat.company = $1 AND d.category = $2 AND d.live = TRUE
    ORDER BY d.sort_index, d.amount, d.id
  ) AS t
) AS donation_options;
"""


async def donation_options(request):
    company_id = request['company_id']
    json_str = await request['conn'].fetchval(donation_options_sql, company_id, int(request.match_info['cat_id']))
    return raw_json_response(json_str)


donations_sql = """
SELECT json_build_object('donations', donations)
FROM (
  SELECT coalesce(array_to_json(array_agg(row_to_json(t))), '[]') AS donations FROM (
    SELECT
      d.id, d.amount,
      d.first_name, d.last_name, d.address, d.city, d.postcode, d.gift_aid,
      u.id AS user_id, u.first_name AS user_first_name, u.last_name AS user_last_name, u.email AS user_email,
      a.ts, a.event as event_id, e.name AS event_name
    FROM donations AS d
    JOIN actions AS a ON d.action = a.id
    JOIN users AS u ON a.user_id = u.id
    LEFT JOIN events AS e ON a.event = e.id
    JOIN donation_options AS opts ON d.donation_option = opts.id
    JOIN categories AS cat ON opts.category = cat.id
    WHERE d.donation_option = $1 AND cat.company = $2
    ORDER BY d.id DESC
  ) AS t
) AS donations
"""


@is_admin
async def opt_donations(request):
    donation_opt_id = int(request.match_info['pk'])
    json_str = await request['conn'].fetchval(donations_sql, donation_opt_id, request['company_id'])
    return raw_json_response(json_str)
