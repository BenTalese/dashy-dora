"""SQLite drops tzinfo on `DateTime(timezone=True)` reads. Every stored instant
is written as UTC, so a naive value read back *is* UTC; this re-attaches it so
it compares against aware bounds (finalisation 05-R9)."""
from datetime import datetime, timezone


def as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
