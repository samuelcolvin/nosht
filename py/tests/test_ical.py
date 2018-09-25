import pytest

from shared.emails.ical import ical_attachment

from .conftest import Factory


async def test_simple(factory: Factory, db_conn, settings, mock):
    await factory.create_company(domain='events.example.com')
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(short_description='This is the event short description')

    m = mock.patch('shared.emails.ical.dt_stamp')
    m.return_value = '20200101T212233'

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
        'DTSTART:20200128T190000Z\r\n'
        'DTEND:20200128T200000Z\r\n'
        'DTSTAMP:20200101T212233Z\r\n'
        'UID:@nosht|supper-clubs/the-event-name\r\n'
        'DESCRIPTION:The Event Name\\n\\nThis is the event short description\\n\\nhttps\r\n'
        ' ://events.example.com/supper-clubs/the-event-name/\r\n'
        'URL:https://events.example.com/supper-clubs/the-event-name/\r\n'
        'END:VEVENT\r\n'
        'END:VCALENDAR\r\n'
    )


async def test_with_location(factory: Factory, db_conn, settings):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(location_name='The House, Testing Street', location_lat=12.3, location_lng=45.6)

    attachment = await ical_attachment(factory.event_id, factory.company_id, conn=db_conn, settings=settings)
    assert 'LOCATION:The House\\, Testing Street (12.300000\\,45.600000)\r\n' in attachment.content


async def test_with_partial_location(factory: Factory, db_conn, settings):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(location_name='The House, Testing Street')

    attachment = await ical_attachment(factory.event_id, factory.company_id, conn=db_conn, settings=settings)
    assert 'LOCATION:The House\\, Testing Street\r\n' in attachment.content


async def test_no_duration(factory: Factory, db_conn, settings):
    await factory.create_company()
    await factory.create_cat()
    await factory.create_user()
    await factory.create_event(duration=None)

    attachment = await ical_attachment(factory.event_id, factory.company_id, conn=db_conn, settings=settings)
    assert (
        'DTSTART:20200128T000000Z\r\n'
        'DTEND:20200129T000000Z\r\n'
    ) in attachment.content


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
    assert (
        'SUMMARY:文文文文文文文文文文文文文文文文文文文文文文\r\n'
        ' 文文文文文文文文文文文文文文文文文文\r\n'
    ) in attachment.content
