from typing import NamedTuple

import pytz


class Attachment(NamedTuple):
    content: str
    mime_type: str
    filename: str


def start_tz_duration(data):
    """
    Set the timezone correctly on start_ts, return it as a date if duration is None.

    This assumes e.start_ts, e.timezone and e.timezone are taken vanilla from the DB.
    """
    start_ts_, duration, tz = data['start_ts'], data['duration'], data['timezone']
    start_ts = start_ts_.astimezone(pytz.timezone(tz))
    if duration:
        return start_ts, duration
    else:
        return start_ts.date(), duration
