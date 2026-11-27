"""Temporal integrity audits for USGS continuous observations."""
import hashlib
from collections import defaultdict
from datetime import date, timedelta

from .historical import windows
from .readiness import parse_timestamp


def verify_historical_hash(path, expected):
    """Match the original SHA, explicitly allowing ONLY reversible EOL changes.

    Never accept a content mismatch; report how the recorded digest matched.
    Old Windows artifacts were often normalized to LF by Git.
    """
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual == expected:
        return {"actual_sha256": actual, "recorded_sha256": expected,
                "match": "exact"}
    lf = raw.replace(b"\r\n", b"\n")
    for name, candidate in (("lf", lf), ("crlf", lf.replace(b"\n", b"\r\n"))):
        if hashlib.sha256(candidate).hexdigest() == expected:
            return {"actual_sha256": actual, "recorded_sha256": expected,
                    "match": "reconstructed_" + name}
    raise ValueError(f"source SHA-256 mismatch: {path}")


def days_between(start, end):
    cursor, stop = date.fromisoformat(start), date.fromisoformat(end)
    while cursor <= stop:
        yield cursor.isoformat()
        cursor += timedelta(days=1)


def window_coverage(task, rows):
    """Report actual raw UTC instants, including empty and partial days.

    Counts do not certify instrument uptime or source approval.
    """
    by_day = defaultdict(set)
    for row in rows:
        ts = parse_timestamp(row["timestamp_utc"])
        if ts is None or ts.date().isoformat() != row["sample_date"]:
            raise ValueError("invalid observed UTC date")
        by_day[row["sample_date"]].add(ts)
    output = []
    for first, last in windows(task["start_date"], task["end_date"]):
        daily = []
        for day in days_between(first, last):
            values = by_day[day]
            daily.append({"date": day, "n_distinct_instants": len(values),
                          "span_hours": ((max(values)-min(values)).total_seconds()/3600
                                         if values else 0)})
        output.append({"start": first, "end": last, "days": daily})
    return output
