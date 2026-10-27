"""Weekly deals digest — *what* the email says (FU-789).

Split from `send_deals_email.py` on the same seam as
`meal_plans/daily_brief.py` / `alerts/send_daily_brief.py`: this module owns
the content and the policy (which deals qualify, how they're worded, when a
send is due), the job module owns delivery. Everything here is a pure function
over plain values so the policy can be tested without a DB, a clock or an SMTP
server.

Three decisions worth stating, because each one is a place the feature could
have quietly misled someone:

  * **Silence is a feature**, same as the evening brief. A week with no active
    specials sends nothing rather than an empty "no deals this week" mail. An
    automated email that arrives regardless of whether it has anything to say
    is one you stop opening, which costs us the weeks it mattered.
  * **No images.** Product images are served from an authenticated endpoint
    (`GET /products/<id>/image`), and an email client has no session — an
    `<img>` pointing at it renders a broken box for every recipient, forever.
    The expanded format earns its name with layout and detail (store, size,
    both prices, the saving), not pictures. The settings copy says so.
  * **Every price is the install's own ingested data.** Dora does not look
    anything up to build this; if the companion tool stops pushing product
    data, the digest goes quiet on its own rather than mailing stale specials,
    because a product with no current offer never scores.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from dora_api.domain.money import format_money
from dora_api.domain.product_offer import discount_percent


# 07:00 household-local. Early enough to be read before a weekend shop and to
# sit clear of the 03:00 audit sweep (whose comment in `startup.py` has been
# promising this schedule since long before it existed). Fixed rather than
# configurable for the same reason the evening brief's hour is: the day is the
# choice that matters to a shopper, and the hour has one sensible answer
# (Charter P1 Effortless).
WEEKLY_DEALS_HOUR = 7

# How many deals ride in each format. The compact list is one line per deal, so
# it can carry more before it stops being scannable; the expanded cards are
# several lines each and a mail that needs three screens of scrolling is a mail
# nobody finishes. Both are a *cap*, not a target — a quiet week sends fewer.
MAX_DEALS_EXPANDED = 10
MAX_DEALS_COMPACT = 20

# Symbols for the currencies an install is realistically set to. Anything else
# falls back to the ISO code, which is unambiguous and never wrong — better a
# plain "SEK 24.90" than a symbol we guessed at. Deliberately a flat table
# rather than a locale library: this is the only server-side money formatting
# in the app (the SPA owns the rest via Intl.NumberFormat, R-003), and one
# email's worth of prices does not justify a dependency.


@dataclass(frozen=True)
class DealLine:
    """One product on special, flattened to exactly what the template renders.

    A view model rather than the `ProductDto` itself: the template must not
    reach for a field that only exists because the products *page* needed it
    (`has_image`, `merchant_stockcode`), and the saving is computed once here
    rather than in Jinja.
    """
    name: str
    brand: str | None
    store_name: str
    size: str
    price_now: str
    price_was: str
    saving: str
    discount_percent: int
    url: str | None


@dataclass(frozen=True)
class DealsDigest:
    lines: list[DealLine]
    currency: str

    @property
    def is_empty(self) -> bool:
        return not self.lines


def is_deals_hour(hour: int, deals_hour: int = WEEKLY_DEALS_HOUR) -> bool:
    """Named for the same reason `is_brief_hour` is — the job should read as
    intent, and the boundary deserves its own test."""
    return hour == deals_hour


def is_send_day(today: date, send_on_day: int) -> bool:
    """`User.send_deals_on_day` is 0=Monday … 6=Sunday, which is exactly
    `date.weekday()`. Stated explicitly because the two other weekday
    conventions in circulation (`isoweekday`, Sunday-first) both silently
    produce an email on the wrong day rather than an error."""
    return today.weekday() == send_on_day


def deals_ledger_key(today: date) -> str:
    """`AlertInteraction.alert_key` for the week `today` falls in.

    Week-scoped, not date-scoped like the daily brief's: users choose their own
    send day, so a user who moves theirs from Friday to Monday mid-week must
    not receive a second copy of the same week's deals. ISO week also rolls
    over correctly across a year boundary, which a `%Y-%W` string does not.
    """
    iso_year, iso_week, _ = today.isocalendar()
    return f"deals:weekly_email:{iso_year}-W{iso_week:02d}"


def build_deal_lines(product_dtos, currency: str, limit: int) -> list[DealLine]:
    """Flatten ranked `ProductDto`s into template rows, dropping any that
    aren't genuinely on special.

    The drop is not paranoia about the caller: `GetBestDealsHandler` already
    filters on `discount_percent`, but it is the dashboard's query first and
    this module must not inherit a silent dependency on that staying true. A
    "deal" in an email that isn't cheaper than its RRP is the single worst
    thing this feature could send.
    """
    lines: list[DealLine] = []
    for dto in product_dtos:
        pct = discount_percent(dto.price_now, dto.price_was)
        if pct is None:
            continue
        lines.append(DealLine(
            name=dto.name,
            brand=dto.brand,
            store_name=dto.store_name,
            size=dto.size,
            price_now=format_money(dto.price_now, currency),
            price_was=format_money(dto.price_was, currency),
            saving=format_money(dto.price_was - dto.price_now, currency),
            discount_percent=pct,
            url=dto.web_url,
        ))
        if len(lines) >= limit:
            break
    return lines


def build_digest(product_dtos, currency: str, compact: bool) -> DealsDigest:
    limit = MAX_DEALS_COMPACT if compact else MAX_DEALS_EXPANDED
    return DealsDigest(
        lines=build_deal_lines(product_dtos, currency, limit),
        currency=currency,
    )


def subject_line(digest: DealsDigest) -> str:
    """Leads with the best discount, because that is the one fact that decides
    whether the mail is worth opening. Falls back to the count when the top
    deal is unremarkable — "18 deals this week" is still a reason to look,
    where "Save 4% this week" is an argument against it."""
    if digest.is_empty:
        return "Your weekly deals"
    best = max(line.discount_percent for line in digest.lines)
    count = len(digest.lines)
    if best >= 20:
        return f"Up to {best}% off this week"
    return f"{count} deal{'s' if count != 1 else ''} this week"
