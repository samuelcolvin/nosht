import datetime
import json
import logging
from typing import Optional

from arq import concurrent

from shared.misc import display_cash, iso_timedelta, static_map_link

from .defaults import Triggers
from .setup import BaseEmailActor, UserEmail

logger = logging.getLogger('nosht.email')


class EmailActor(BaseEmailActor):
    @concurrent
    async def send_event_conf_emails(self, paid_action_id: int):
        async with self.pg.acquire() as conn:
            data = await conn.fetchrow(
                """
                SELECT t.user_id,
                  coalesce(u.first_name || ' ' || u.last_name, u.first_name, u.last_name, u.email) AS user_name,
                  e.slug, cat.slug as cat_slug, e.name, e.short_description,
                  e.location, e.location_lat, e.location_lng,
                  e.start_ts, e.duration, e.price, cat.company, co.currency, a.extra
                FROM tickets AS t
                JOIN actions AS a ON t.paid_action = a.id
                JOIN users AS u ON t.user_id = u.id
                JOIN events AS e ON t.event = e.id
                JOIN categories AS cat ON e.category = cat.id
                JOIN companies co on cat.company = co.id
                WHERE t.paid_action=$1
                LIMIT 1
                """,
                paid_action_id
            )
            buyer_user_id = data['user_id']

            user_data = await conn.fetch(
                """
                SELECT t.user_id, t.id AS ticket_id,
                  coalesce(first_name || ' ' || last_name, first_name, last_name, email) as user_name
                FROM tickets AS t
                JOIN users u on t.user_id = u.id
                WHERE t.paid_action=$1
                """,
                paid_action_id)

        duration: Optional[datetime.timedelta] = data['duration']
        ctx = {
            'event_link': '/{cat_slug}/{slug}/'.format(**data),
            'event_name': data['name'],
            'event_short_description': data['short_description'],
            'event_start': data['start_ts'] if duration else data['start_ts'].date(),
            'event_duration': int(duration.total_seconds()) if duration else 'All day',
            'event_location': data['location'],
            'ticket_price': display_cash(data['price'], data['currency']),
            'buyer_name': data['user_name']
        }
        lat, lng = data['location_lat'], data['location_lng']
        if lat and lng:
            ctx.update(
                static_map=static_map_link(lat, lng, settings=self.settings),
                google_maps_url=f'https://www.google.com/maps/place/{lat},{lng}/@{lat},{lng},13z',
            )
        ticket_count = len(user_data)
        buyer_user_data = next(u for u in user_data if u['user_id'] == buyer_user_id)

        ctx_buyer = {
            **ctx,
            'markup_data': get_event_schema(data, buyer_user_data),
            'ticket_count': ticket_count,
            'ticket_count_plural': ticket_count > 1,
            'total_price': display_cash(data['price'] * ticket_count, data['currency']),
        }
        if data['extra']:
            action_extra = json.loads(data['extra'])
            ctx_buyer['card_details'] = '{card_expiry} - ending {card_last4}'.format(**action_extra)

        await self.send_emails.direct(
            data['company'],
            Triggers.ticket_buyer,
            [UserEmail(id=buyer_user_id, ctx=ctx_buyer)]
        )
        other_user_emails = [
            UserEmail(id=u['id'], ctx={'markup_data': get_event_schema(data, u), **ctx})
            for u in user_data if u['user_id'] != buyer_user_id
        ]
        if other_user_emails:
            await self.send_emails.direct(
                data['company'],
                Triggers.ticket_other,
                other_user_emails,
            )


def get_event_schema(event_data, user_data):
    lat, lng = event_data['location_lat'], event_data['location_lng']
    return {
        '@context': 'http://schema.org',
        '@type': 'EventReservation',
        'reservationNumber': 'T{ticket_id}'.format(**user_data),
        'ticketNumber': 'T{ticket_id}'.format(**user_data),
        'ticketToken': 'code:{ticket_id}'.format(**user_data),  # TODO I guess needs signature
        'reservationStatus': 'http://schema.org/Confirmed',
        'underName': {
            '@type': 'Person',
            'name': user_data['user_name']
        },
        'reservationFor': {
            '@type': 'Event',
            'name': event_data['name'],
            'startDate': event_data['start_ts'].isoformat(),
            'duration': iso_timedelta(event_data['duration']),
            'location': {
                '@type': 'Place',
                'name': event_data['location'],
                'geo': lat and lng and {
                    '@type': 'GeoCoordinates',
                    'latitude': f'{lat:0.7f}',
                    'longitude': f'{lng:0.7f}',
                },
            }
        },
    }
