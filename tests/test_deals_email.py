"""Weekly deals digest — policy + wording unit tests (FU-789, built 2026-08-29).

Every test drives the module-level pure functions with plain fixtures — no DB,
no clock, no SMTP — mirroring `test_daily_brief.py`. The job around them is a
repo walk; its gate chain is documented in `send_deals_email.py` and exercised
by the e2e suite.

What's pinned:
  • the weekday convention, because getting it wrong mails on the wrong day
    rather than failing
  • the ledger key is ISO-week-scoped, so moving your send day mid-week can't
    produce a second copy, and a year boundary doesn't collide
  • a product that isn't genuinely cheaper than its RRP never reaches the
    template, even if the ranked pool hands one over
  • money formatting falls back to the ISO code rather than guessing a symbol
  • the subject leads with the discount only when the discount is worth leading
    with
"""
from datetime import date

from dora_api.features.deals.deals_digest import (MAX_DEALS_COMPACT,
                                                  MAX_DEALS_EXPANDED,
                                                  WEEKLY_DEALS_HOUR,
                                                  build_deal_lines,
                                                  build_digest,
                                                  deals_ledger_key,
                                                  format_money, is_deals_hour,
                                                  is_send_day, subject_line)


class _Dto:
    """The `ProductDto` fields `build_deal_lines` reads. A stand-in keeps the
    fixture free of the real DTO's many page-only fields."""
    def __init__(self, name="Milk", price_now=2.0, price_was=4.0,
                 store_name="Coles", size="2L", brand=None, web_url=None):
        self.name = name
        self.price_now = price_now
        self.price_was = price_was
        self.store_name = store_name
        self.size = size
        self.brand = brand
        self.web_url = web_url


# ── Send-day convention ─────────────────────────────────────────────────

def test__is_send_day__zero_means_monday():
    # 2026-08-31 is a Monday. `User.send_deals_on_day` is 0=Mon, matching
    # date.weekday() — the whole point of the helper.
    assert is_send_day(date(2026, 8, 31), 0) is True


def test__is_send_day__six_means_sunday():
    assert is_send_day(date(2026, 9, 6), 6) is True


def test__is_send_day__is_false_on_every_other_day():
    monday = date(2026, 8, 31)
    assert [d for d in range(7) if is_send_day(monday, d)] == [0]


def test__is_deals_hour__matches_only_the_send_hour():
    assert is_deals_hour(WEEKLY_DEALS_HOUR) is True
    assert is_deals_hour(WEEKLY_DEALS_HOUR - 1) is False
    assert is_deals_hour(WEEKLY_DEALS_HOUR + 1) is False


# ── Ledger key ──────────────────────────────────────────────────────────

def test__ledger_key__is_stable_across_a_week():
    """Two different days in the same ISO week share a key — that is what
    stops a user who moves their send day from getting a second copy."""
    monday = deals_ledger_key(date(2026, 8, 31))
    friday = deals_ledger_key(date(2026, 9, 4))
    assert monday == friday


def test__ledger_key__differs_between_consecutive_weeks():
    assert deals_ledger_key(date(2026, 8, 31)) != deals_ledger_key(date(2026, 9, 7))


def test__ledger_key__does_not_collide_across_a_year_boundary():
    """2027-01-01 is a Friday, so it belongs to ISO week 53 of 2026. A naive
    key would call it week 00 of 2027 and a `%Y-%W` key would collide with the
    following January — the ISO year is why it doesn't."""
    late_2026 = deals_ledger_key(date(2026, 12, 31))
    early_2027 = deals_ledger_key(date(2027, 1, 1))
    mid_2027 = deals_ledger_key(date(2027, 1, 11))
    assert late_2026 == early_2027       # same ISO week
    assert mid_2027 != late_2026


# ── Money ───────────────────────────────────────────────────────────────

def test__format_money__uses_a_symbol_for_a_known_currency():
    assert format_money(4.5, "AUD") == "$4.50"
    assert format_money(4.5, "GBP") == "£4.50"


def test__format_money__falls_back_to_the_iso_code_rather_than_guessing():
    assert format_money(24.9, "SEK") == "SEK 24.90"


def test__format_money__renders_a_missing_price_as_a_dash_not_zero():
    assert format_money(None, "AUD") == "–"


# ── Deal lines ──────────────────────────────────────────────────────────

def test__build_deal_lines__computes_the_saving_in_money():
    lines = build_deal_lines([_Dto(price_now=2.5, price_was=4.0)], "AUD", 10)
    assert lines[0].saving == "$1.50"
    assert lines[0].discount_percent == 38


def test__build_deal_lines__drops_a_product_that_is_not_actually_cheaper():
    """The ranked pool is the dashboard's query first; this module must not
    inherit a silent dependency on it always filtering. A full-price item in a
    deals email is the worst thing this feature could send."""
    lines = build_deal_lines(
        [_Dto(name="Full price", price_now=4.0, price_was=4.0),
         _Dto(name="Real deal", price_now=2.0, price_was=4.0)],
        "AUD", 10,
    )
    assert [line.name for line in lines] == ["Real deal"]


def test__build_deal_lines__drops_a_product_with_no_rrp():
    lines = build_deal_lines([_Dto(price_now=2.0, price_was=None)], "AUD", 10)
    assert lines == []


def test__build_deal_lines__honours_the_limit():
    lines = build_deal_lines([_Dto() for _ in range(30)], "AUD", 5)
    assert len(lines) == 5


def test__build_digest__compact_carries_more_deals_than_expanded():
    pool = [_Dto() for _ in range(50)]
    compact = build_digest(pool, "AUD", compact=True)
    expanded = build_digest(pool, "AUD", compact=False)
    assert len(compact.lines) == MAX_DEALS_COMPACT
    assert len(expanded.lines) == MAX_DEALS_EXPANDED
    assert len(compact.lines) > len(expanded.lines)


def test__digest__is_empty_when_nothing_is_on_special():
    """The silence branch — the job reads this to decide not to send at all,
    so an "empty" digest must not be merely falsy-ish."""
    digest = build_digest([_Dto(price_now=4.0, price_was=4.0)], "AUD", compact=False)
    assert digest.is_empty is True


# ── Subject ─────────────────────────────────────────────────────────────

def test__subject__leads_with_the_discount_when_it_is_worth_leading_with():
    digest = build_digest([_Dto(price_now=2.0, price_was=4.0)], "AUD", compact=False)
    assert subject_line(digest) == "Up to 50% off this week"


def test__subject__falls_back_to_the_count_on_an_unremarkable_week():
    """"Save 5% this week" is an argument against opening the mail; the count
    at least says there is something to look at."""
    digest = build_digest(
        [_Dto(price_now=3.8, price_was=4.0), _Dto(price_now=3.9, price_was=4.0)],
        "AUD", compact=False,
    )
    assert subject_line(digest) == "2 deals this week"


def test__subject__is_singular_for_one_deal():
    digest = build_digest([_Dto(price_now=3.8, price_was=4.0)], "AUD", compact=False)
    assert subject_line(digest) == "1 deal this week"


def test__mail_links__target_declared_spa_routes():
    """The "See all deals" button used to link `/products`, a route the SPA
    never had, so every weekly mail landed on the 404 page."""
    import re
    from pathlib import Path

    from dora_api.features.deals.send_deals_email import DEALS_ROUTE, UNSUBSCRIBE_ROUTE

    routes = (Path(__file__).resolve().parents[1] / "web_app" / "src" / "router" / "routes.ts").read_text(encoding="utf-8")
    segments = {
        seg for raw in re.findall(r"path:\s*'([^']*)'", routes)
        for seg in raw.strip("/").split("/") if seg and not seg.startswith(":")
    }
    for route in (DEALS_ROUTE, UNSUBSCRIBE_ROUTE):
        for seg in route.strip("/").split("/"):
            assert seg in segments, f"{route}: '{seg}' is not a declared SPA route segment"
