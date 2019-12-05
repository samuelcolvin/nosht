import re
from datetime import datetime

from shared.settings import Settings

from .utils import Attachment, start_tz_duration

DT_FMT = '%Y%m%dT%H%M%S'
DATE_FMT = '%Y%m%d'


def _ical_escape(text):
    """
    Format value according to iCalendar TEXT escaping rules.
    from https://github.com/collective/icalendar/blob/4.0.2/src/icalendar/parser.py#L20
    """
    return (
        text.replace(r'\N', '\n')
        .replace('\\', '\\\\')
        .replace(';', r'\;')
        .replace(',', r'\,')
        .replace('\r\n', r'\n')
        .replace('\n', r'\n')
    )


def foldline(line, limit=75, fold_sep='\r\n '):
    """
    Make a string folded as defined in RFC5545
    Lines of text SHOULD NOT be longer than 75 octets, excluding the line
    break.  Long content lines SHOULD be split into a multiple line
    representations using a line "folding" technique.  That is, a long
    line can be split between any two characters by inserting a CRLF
    immediately followed by a single linear white-space character (i.e.,
    SPACE or HTAB).
    https://github.com/collective/icalendar/blob/4.0.2/src/icalendar/parser.py#L65
    """
    assert '\n' not in line

    # Use a fast and simple variant for the common case that line is all ASCII.
    try:
        line.encode('ascii')
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    else:
        return fold_sep.join(line[i : i + limit - 1] for i in range(0, len(line), limit - 1))

    ret_chars = []
    byte_count = 0
    for char in line:
        char_byte_len = len(char.encode('utf-8'))
        byte_count += char_byte_len
        if byte_count >= limit:
            ret_chars.append(fold_sep)
            byte_count = char_byte_len
        ret_chars.append(char)

    return ''.join(ret_chars)


def dt_stamp():
    """
    for easy mocking
    """
    return datetime.utcnow().strftime(DT_FMT)


async def ical_attachment(event_id, company_id, *, conn, settings: Settings):
    """
    Generate iCal data for an event, see https://tools.ietf.org/html/rfc5545.
    """
    data = await conn.fetchrow(
        """
        SELECT e.id, e.name, e.duration, e.short_description,
          e.start_ts, e.timezone,
          cat.slug || '/' || e.slug as ref,
          e.location_name, e.location_lat, e.location_lng,
          event_link(cat.slug, e.slug, e.public, $3) as link, co.domain,
          full_name(host.first_name, host.last_name) AS host_name,
          co.name as company_name, coalesce(co.email_reply_to, co.email_from) as company_email
        FROM events AS e
        JOIN categories AS cat ON e.category = cat.id
        JOIN companies AS co ON cat.company = co.id
        JOIN users AS host ON e.host = host.id
        WHERE e.id = $1 AND co.id = $2
        """,
        event_id,
        company_id,
        settings.auth_key,
    )
    if not data:
        raise RuntimeError(f'event {event_id} on company {company_id} not found')

    url = 'https://{domain}{link}'.format(**data)
    email = data['company_email'] or settings.default_email_address

    extra_email = re.search('<(.*?)>', email)
    if extra_email:
        email = extra_email.group(1)

    hosted_by = '{host_name} on behalf of {company_name}'.format(**data)
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//nosht//events//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        foldline('SUMMARY:' + _ical_escape(data['name'])),
        'DTSTAMP:' + dt_stamp() + 'Z',
        'UID:@nosht|' + data['ref'],
        foldline(
            'DESCRIPTION:'
            + _ical_escape(
                '{name}\n\n'
                '{short_description}\n\n'
                'Hosted by {hosted_by}\n\n'
                'For more information: {url}'.format(url=url, hosted_by=hosted_by, **data)
            )
        ),
        foldline('URL:' + _ical_escape(url)),
        foldline(f'ORGANIZER;CN={_ical_escape(hosted_by)}:MAILTO:{email}'),
    ]

    start, duration = start_tz_duration(data)
    if duration:
        tz = data['timezone']
        finish = start + duration
        if data['timezone'] in {'GMT', 'UTC'}:
            lines += [
                f'DTSTART:{start.strftime(DT_FMT)}Z',
                f'DTEND:{finish.strftime(DT_FMT)}Z',
            ]
        else:
            lines += [
                f'DTSTART;TZID={tz}:{start.strftime(DT_FMT)}',
                f'DTEND;TZID={tz}:{finish.strftime(DT_FMT)}',
            ]
    else:
        lines.append('DTSTART:' + start.strftime(DATE_FMT))

    if data['location_name']:
        lines.append(foldline('LOCATION:' + _ical_escape(data['location_name'])))

    if data['location_lat'] and data['location_lng']:
        lines.append('GEO:{location_lat:0.6f};{location_lng:0.6f}'.format(**data))

    lines += [
        'END:VEVENT',
        'END:VCALENDAR\r\n',
    ]
    return Attachment(content='\r\n'.join(lines), mime_type='text/calendar', filename='event.ics')
