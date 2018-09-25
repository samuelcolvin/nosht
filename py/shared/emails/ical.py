from datetime import datetime, timedelta

from shared.settings import Settings

PREFIX = (
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//nosht//events//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
)
DT_FMT = '%Y%m%dT%H%M%S'


def _ical_escape(text):
    """
    Format value according to iCalendar TEXT escaping rules.
    from https://github.com/collective/icalendar/blob/4.0.2/src/icalendar/parser.py#L20
    """
    return (
        text
        .replace(r'\N', '\n')
        .replace('\\', '\\\\')
        .replace(';', r'\;')
        .replace(',', r'\,')
        .replace('\r\n', r'\n')
        .replace('\n', r'\n')
    )


def _foldline(line, limit=75, fold_sep='\r\n '):
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
        return fold_sep.join(
            line[i:i + limit - 1] for i in range(0, len(line), limit - 1)
        )

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
    data = await conn.fetchrow(
        """
        SELECT e.id, e.name, e.start_ts, e.duration, e.short_description,
          cat.slug || '/' || e.slug as ref,
          e.location_name, e.location_lat, e.location_lng,
          event_link(cat.slug, e.slug, e.public, $3) as link, co.domain 
        FROM events AS e
        JOIN categories AS cat ON e.category = cat.id
        JOIN companies AS co on cat.company = co.id
        WHERE e.id = $1 AND co.id = $2
        """,
        event_id,
        company_id,
        settings.auth_key,
    )
    if not data:
        raise RuntimeError(f'event {event_id} on company {company_id} not found')

    url = 'https://{domain}{link}'.format(**data)
    start, duration = data['start_ts'], data['duration']
    if duration:
        finish = start + duration
    else:
        start = start.date()
        finish = start + timedelta(days=1)

    lines = list(PREFIX) + [
        'BEGIN:VEVENT',
        _foldline('SUMMARY:' + _ical_escape(data['name'])),
        'DTSTART:' + start.strftime(DT_FMT) + 'Z',
        'DTEND:' + finish.strftime(DT_FMT) + 'Z',
        'DTSTAMP:' + dt_stamp() + 'Z',
        'UID:@nosht|' + data['ref'],
        _foldline('DESCRIPTION:' + _ical_escape('{name}\n\n{short_description}\n\n{url}'.format(url=url, **data))),
        _foldline('URL:' + _ical_escape(url)),
    ]

    if data['location_name']:
        location = data['location_name']
        if data['location_lat'] and data['location_lng']:
            location += ' ({location_lat:0.6f},{location_lng:0.6f})'.format(**data)

        lines.append(
            _foldline('LOCATION:' + _ical_escape(location))
        )

    lines += [
        'END:VEVENT',
        'END:VCALENDAR\r\n',
    ]
    from .plumbing import Attachment
    return Attachment(
        content='\r\n'.join(lines),
        mime_type='text/calendar',
        filename='event.ics'
    )