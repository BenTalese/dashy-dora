"""The `range=` tokens the report and price-history endpoints accept.

`1y`/`2y`/`5y` are flat 365-day multiples rather than calendar years so a chart
axis is stable. A window opens at the household's midnight (R-021).
"""
from datetime import datetime, timedelta, timezone

from dora_api.features.app_settings.clock import household_timezone, household_today
from dora_api.infrastructure.ports import Repository

RANGE_DAYS = {
    "30d": 30,
    "90d": 90,
    "1y": 365,
    "2y": 730,
    "5y": 1825,
}


def range_start(days: int | None, repository: Repository) -> datetime | None:
    """The UTC instant of the household's midnight `days` calendar days before
    the household's today, or None (all time) when `days` is None."""
    if days is None:
        return None
    start_day = household_today(repository) - timedelta(days=days)
    return datetime.combine(
        start_day, datetime.min.time(), tzinfo=household_timezone(repository),
    ).astimezone(timezone.utc)
