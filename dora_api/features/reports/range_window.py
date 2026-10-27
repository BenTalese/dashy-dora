"""GET /api/reports/range-window: the dates a range token resolves to."""

from flask import request

from dora_api.features.app_settings.clock import household_today
from dora_api.features.routers import REPORTS_ROUTER
from dora_api.infrastructure.api_response import ok
from dora_api.persistence.sqlalchemy_repository import SqlAlchemyRepository
from dora_api.features.reports._common import (
    earliest_activity, parse_range, range_days)


@REPORTS_ROUTER.route("/range-window", methods=["GET"])
def range_window():
    """The dates a range token actually resolves to, plus its length in days.

    FU-845 #2 / §4.10.2 — the picker said "30 days" and the page left the reader
    to guess which thirty. It now shows "2 Aug – 2 Sep" beside the control, and
    the dates come from here rather than being re-derived in the browser.

    Not a field on the nine report responses: the window is a property of the
    **range parameter**, not of any one report, and shipping it nine times per
    page load would be nine copies of one fact. Ungated on purpose — the range
    control is page chrome and exists on a money-off install.

    It also removes a real R-003 duplication rather than adding one: the client
    carried its own `RANGE_TO_DAYS` table — a second copy of `_RANGE_DAYS`, in a
    second language — purely to convert the picked range into the day count the
    waste endpoint takes. `days` here replaces it.
    """
    raw = request.args.get("range", "30d")
    repository = SqlAlchemyRepository()
    since = parse_range(raw, repository)
    # "All time" starts at the household's earliest record, so the label can
    # name real dates on every range (owner, 2026-09-27: "just show the dates
    # it covers always so the UI doesn't shift around"). None only on an
    # install with no history at all.
    start = since if since is not None else earliest_activity(repository)
    return ok({
        "range": raw,
        "start": start.date().isoformat() if start is not None else None,
        "end": household_today(repository).isoformat(),
        # `range_days` returns None for "all"; the waste report clamps to 365
        # itself and reports the window it actually used, so the client hands it
        # a wide number and renders whatever comes back.
        "days": range_days(raw),
    })
