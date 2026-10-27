"""Household clock — "today" in the install's configured timezone.

The household timezone (`AppSetting.timezone`, IANA) decides the date boundary
so a household is correct regardless of where the server is hosted. Used by the
meal-plan past-day rules, the reconcile sweep, `GET /meal-plans/today` and
every household-date window (R-021).
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dora_api.features.app_settings.access import get_or_create_app_setting
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository


def resolve_timezone(tz_name: str | None) -> ZoneInfo:
    # An unknown/blank zone falls back to UTC rather than raising, so the
    # date boundary stays defined even if the stored value is somehow invalid.
    try:
        return ZoneInfo(tz_name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def is_valid_timezone(tz_name: str) -> bool:
    try:
        ZoneInfo(tz_name)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def today_in_timezone(tz_name: str | None) -> date:
    return datetime.now(resolve_timezone(tz_name)).date()


def household_today(repository: SqlAlchemyRepository) -> date:
    return today_in_timezone(get_or_create_app_setting(repository).timezone)


def household_timezone(repository: SqlAlchemyRepository) -> ZoneInfo:
    """The install's configured zone, resolved. Callers that bucket UTC
    timestamps into calendar days must do so in this zone so the day
    boundary agrees with `household_today` (R-021)."""
    return resolve_timezone(get_or_create_app_setting(repository).timezone)
