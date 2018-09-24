from datetime import datetime, timedelta

PREFIX = (
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//tutorcruncher.com//Appointments//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
)
SUFFIX = 'END:VCALENDAR\r\n'
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


async def ical_content(conn):

    data = await conn.fetchrow(
        """
        SELECT e.id, e.name, e.start_ts, e.duration, e.short_description,
          e.location_name, e.location_lat, e.location_lng,
          event_link(cat.slug, e.slug, e.public, $2) as link, co.domain 
        FROM events AS e
        JOIN categories AS cat ON e.category = cat.id
        JOIN companies AS co on cat.company = co.id
        WHERE e.id=$1
        """
    )
    url = 'https://{domain}{link}'.format(**data)
    start, duration = data['start_ts'], data['duration']
    if duration:
        finish = start + duration
    else:
        finish = start + timedelta(days=1)
    lines = list(PREFIX) + [
        'BEGIN:VEVENT',
        _foldline('SUMMARY:' + _ical_escape(data['name'])),
        'DTSTART:' + start.strftime(DT_FMT) + 'Z',
        'DTEND:' + finish.strftime(DT_FMT) + 'Z',
        'DTSTAMP:' + datetime.utcnow().strftime(DT_FMT) + 'Z',
        'UID:@nosht|{id}'.format(**data),
        _foldline('DESCRIPTION:' + _ical_escape('{name}\n\n{short_description}\n\n{url}'.format(url=url, **data))),
        _foldline('URL:' + _ical_escape(url)),
        _foldline('LOCATION:' + _ical_escape('{location_name} ({location_lat}, {location_lng})'.format(**data))),
        'END:VEVENT',
        SUFFIX,
    ]
    return '\r\n'.join(lines)
