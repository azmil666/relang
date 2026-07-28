"""
duration.py - port of duration.go / fortio.org/duration

Parses durations with extra "d" (day = 24h) and "w" (week = 7d) units on
top of the usual ones (ns/us/ms/s/m/h), and parses simple date/time strings
for the "-until" flag.
"""
import re
from datetime import datetime, timedelta, time as dtime

DAY = timedelta(days=1)
WEEK = timedelta(days=7)

_UNIT_SECONDS = {
    "ns": 1e-9,
    "us": 1e-6,
    "µs": 1e-6,
    "ms": 1e-3,
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 86400 * 7,
}

_TOKEN_RE = re.compile(r"([0-9]*\.?[0-9]+)\s*(ns|us|µs|ms|s|m|h|d|w)")


class DurationParseError(ValueError):
    pass


def parse(s: str) -> timedelta:
    """Parse a duration string like '3w2d10h', '5m', '90s', '1h30m'."""
    s = s.strip()
    if not s:
        raise DurationParseError("empty duration string")
    neg = False
    if s.startswith("-"):
        neg = True
        s = s[1:]
    elif s.startswith("+"):
        s = s[1:]
    total_seconds = 0.0
    pos = 0
    matched_any = False
    while pos < len(s):
        m = _TOKEN_RE.match(s, pos)
        if not m:
            raise DurationParseError(f"invalid duration token at: {s[pos:]!r}")
        value, unit = m.groups()
        total_seconds += float(value) * _UNIT_SECONDS[unit]
        matched_any = True
        pos = m.end()
    if not matched_any:
        raise DurationParseError(f"could not parse duration: {s!r}")
    if neg:
        total_seconds = -total_seconds
    return timedelta(seconds=total_seconds)


_DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
]


def _parse_kitchen(s: str):
    """Parse '3:05 pm' / '3:05pm' / '15:05' style times, return a time object."""
    s = s.strip()
    for fmt in ("%I:%M %p", "%I:%M%p", "%I %p", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None


def next_time(now: datetime, target_time: dtime) -> datetime:
    """Return the next datetime (today or tomorrow) matching target_time, after now."""
    candidate = now.replace(
        hour=target_time.hour,
        minute=target_time.minute,
        second=target_time.second,
        microsecond=0,
    )
    if candidate <= now:
        candidate += DAY
    return candidate


class DateTimeParseError(ValueError):
    pass


def parse_datetime(now: datetime, s: str) -> datetime:
    """
    Parse one of:
      - "YYYY-MM-DD HH:MM:SS"
      - "YYYY-MM-DD" (time defaults to 00:00:00, may be in the past)
      - "HH:MM:SS" / "H:MM AM/PM" style (next occurrence after now)
    """
    s = s.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    t = _parse_kitchen(s)
    if t is not None:
        return next_time(now, t)
    raise DateTimeParseError(f"could not parse date/time: {s!r}")