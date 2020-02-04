from datetime import datetime

import pytest
import pytz

from shared.emails.ical import ical_attachment

from .conftest import Factory, london


async def test_ical(factory: Factory, db_conn, settings, mock):
    await factory.create_company(domain='events.example.com')
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(
        short_description='This is the event short description', start_ts=london.localize(datetime(2032, 6, 1, 10, 0)),
    )

    m = mock.patch('shared.emails.ical.dt_stamp')
    m.return_value = '20320101T212233'

    attachment = await ical_attachment(factory.event_id, factory.company_id, conn=db_conn, settings=settings)
    # debug(attachment)
    assert attachment.mime_type == 'text/calendar'
    assert attachment.filename == 'event.ics'
    assert attachment.content == (
        'BEGIN:VCALENDAR\r\n'
        'VERSION:2.0\r\n'
        'PRODID:-//nosht//events//EN\r\n'
        'CALSCALE:GREGORIAN\r\n'
        'METHOD:PUBLISH\r\n'
        'BEGIN:VEVENT\r\n'
        'SUMMARY:The Event Name\r\n'
        'DTSTAMP:20320101T212233Z\r\n'
        'UID:@nosht|supper-clubs/the-event-name\r\n'
        'DESCRIPTION:The Event Name\\n\\nThis is the event short description\\n\\nHoste\r\n'
        ' d by Frank Spencer on behalf of Testing\\n\\nFor more information: https://e\r\n'
        ' vents.example.com/supper-clubs/the-event-name/\r\n'
        'URL:https://events.example.com/supper-clubs/the-event-name/\r\n'
        'ORGANIZER;CN=Frank Spencer on behalf of Testing:MAILTO:nosht@scolvin.com\r\n'
        'DTSTART;TZID=Europe/London:20320601T100000\r\n'
        'DTEND;TZID=Europe/London:20320601T110000\r\n'
        'END:VEVENT\r\n'
        'END:VCALENDAR\r\n'
    )


async def test_with_location(factory: Factory, db_conn, settings):
    await factory.create_company(email_reply_to='foobar@example.com')
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(location_name='The House, Testing Street', location_lat=12.3, location_lng=45.6)

    attachment = await ical_attachment(factory.event_id, factory.company_id, conn=db_conn, settings=settings)
    assert 'LOCATION:The House\\, Testing Street\r\n' in attachment.content
    assert 'GEO:12.300000;45.600000\r\n' in attachment.content


async def test_with_partial_location(factory: Factory, db_conn, settings):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(location_name='The House, Testing Street')

    attachment = await ical_attachment(factory.event_id, factory.company_id, conn=db_conn, settings=settings)
    assert 'LOCATION:The House\\, Testing Street\r\n' in attachment.content
    assert 'ORGANIZER;CN=Frank Spencer on behalf of Testing:MAILTO:nosht@scolvin.com\r\n' in attachment.content


async def test_utc(factory: Factory, db_conn, settings):
    await factory.create_company(domain='events.example.com')
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(
        short_description='This is the event short description',
        start_ts=pytz.utc.localize(datetime(2032, 6, 1, 10, 0)),
        timezone=str(pytz.utc),
    )

    attachment = await ical_attachment(factory.event_id, factory.company_id, conn=db_conn, settings=settings)
    assert 'DTSTART:20320601T100000Z\r\nDTEND:20320601T110000Z\r\n' in attachment.content


async def test_no_duration(factory: Factory, db_conn, settings):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(duration=None)

    attachment = await ical_attachment(factory.event_id, factory.company_id, conn=db_conn, settings=settings)
    assert 'DTSTART:20320628\r\n' in attachment.content
    assert 'DTEND' not in attachment.content


async def test_no_apt(factory: Factory, db_conn, settings):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()

    with pytest.raises(RuntimeError):
        await ical_attachment(123, factory.company_id, conn=db_conn, settings=settings)


async def test_unicode_wrap(factory: Factory, db_conn, settings):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(name='文' * 40)

    attachment = await ical_attachment(factory.event_id, factory.company_id, conn=db_conn, settings=settings)
    assert 'SUMMARY:文文文文文文文文文文文文文文文文文文文文文文\r\n 文文文文文文文文文文文文文文文文文文\r\n' in attachment.content
