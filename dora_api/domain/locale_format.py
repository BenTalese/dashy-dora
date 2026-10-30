"""Locale-aware dates and money for text the *server* renders: print views and
mail. The SPA formats through `Intl` (`composables/useMoney.ts`,
`composables/useDateFormat.ts`); this is the server's counterpart, so a printed
sheet reads the way the same figure reads on screen (D-006, R-003).

No new dependency (no Babel / ICU binding). The tables below cover exactly the
locales the Region settings page offers (`web_app/src/models/regionChoices.ts`
`LOCALE_CHOICES`) and the currencies it offers (`CURRENCY_CHOICES`). They were
**derived from Intl itself**, not written by hand (R-089 spirit): Node's
full-ICU `Intl.DateTimeFormat(locale, {dateStyle: 'medium', timeStyle:
'short'})`, `{weekday: 'short', day: 'numeric', month: 'short'}` and
`Intl.NumberFormat(locale, {style: 'currency', currency, 2 fraction digits})`
were taken apart with `formatToParts` (Node 24 / ICU 77, 2026-10-30), so
"30 Oct 2026, 4:50 pm" (en-AU), "Oct 30, 2026, 4:50 PM" (en-US),
"30.10.2026, 16:50" (de-DE), "$7.99" (en-AU, AUD) and "7,99 €" (de-DE, EUR)
are what the browser prints too. Re-derive the same way if a locale or
currency is added to the Region page; a locale not in the table falls back to
another of its language, then to en-AU (Dora's shipping default), the same
default `useMoney.ts` uses.

Known simplifications against Intl: a negative amount always leads with "-";
JPY keeps two decimals (the SPA pins two as well).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from datetime import date, datetime, time

DEFAULT_LOCALE = "en-AU"
# A tag the table doesn't list falls back to its language's home locale where
# the table has more than one ("fr-BE" reads like fr-FR, not fr-CA).
_LANGUAGE_FALLBACK = {"en": "en-AU", "fr": "fr-FR", "pt": "pt-PT", "es": "es-ES"}


@dataclass(frozen=True)
class _LocaleSpec:
    """One locale's patterns. Tokens: {d}/{dd} day, {M}/{MM} numeric month,
    {MMM} month name, {y} year, {EEE} weekday, {h}/{hh} 12-hour,
    {H}/{HH} 24-hour, {mm} minute, {a} am/pm marker."""
    date: str
    time: str
    joiner: str
    day: str
    am: str
    pm: str
    months: tuple[str, ...]
    weekdays: tuple[str, ...]
    group: str
    decimal: str
    # 2 ⇒ a four-digit amount is not grouped ("1234,50 €" in es-ES).
    min_grouping: int
    # en-IN groups lakhs/crores: 12,34,567.50.
    indian_grouping: bool
    currency_affixes: dict[str, tuple[str, str]]
    # The month form inside the weekday heading, where it differs from the
    # date's (de-DE prints "30.10.2026" but "Fr., 30. Okt.").
    day_months: tuple[str, ...] | None = field(default=None)


def _spec(locale: str | None) -> _LocaleSpec:
    tag = (locale or "").strip()
    if tag in _LOCALES:
        return _LOCALES[tag]
    lowered = tag.lower()
    for known, spec in _LOCALES.items():
        if known.lower() == lowered:
            return spec
    language = lowered.split("-")[0]
    if language in _LANGUAGE_FALLBACK:
        return _LOCALES[_LANGUAGE_FALLBACK[language]]
    for known, spec in _LOCALES.items():
        if known.split("-")[0] == language:
            return spec
    return _LOCALES[DEFAULT_LOCALE]


def _date_values(spec: _LocaleSpec, value: date, months: tuple[str, ...]) -> dict[str, str]:
    return {
        "d": str(value.day), "dd": f"{value.day:02d}",
        "M": str(value.month), "MM": f"{value.month:02d}",
        "MMM": months[value.month - 1], "y": str(value.year),
        "EEE": spec.weekdays[value.weekday()],
    }


def format_date(value: date, locale: str | None) -> str:
    """The locale's medium date: "30 Oct 2026", "Oct 30, 2026", "30.10.2026"."""
    spec = _spec(locale)
    return spec.date.format(**_date_values(spec, value, spec.months))


def format_day(value: date, locale: str | None) -> str:
    """A weekday heading: "Fri, 30 Oct", "Fri, Oct 30", "Fr., 30. Okt."."""
    spec = _spec(locale)
    return spec.day.format(**_date_values(spec, value, spec.day_months or spec.months))


def format_time(value: time | datetime, locale: str | None) -> str:
    """The locale's short time: "4:50 pm", "4:50 PM", "16:50"."""
    spec = _spec(locale)
    hour12 = value.hour % 12 or 12
    return spec.time.format(
        h=str(hour12), hh=f"{hour12:02d}",
        H=str(value.hour), HH=f"{value.hour:02d}",
        mm=f"{value.minute:02d}",
        a=spec.am if value.hour < 12 else spec.pm,
    )


def format_datetime(value: datetime, locale: str | None) -> str:
    """Medium date + short time, as `useDateFormat.formatDateTime` renders it.
    `value` must already be on the household clock; this only spells it."""
    spec = _spec(locale)
    return f"{format_date(value.date(), locale)}{spec.joiner}{format_time(value, locale)}"


def _group_digits(digits: str, spec: _LocaleSpec) -> str:
    if len(digits) < 4 or (spec.min_grouping == 2 and len(digits) < 5) or not spec.group:
        return digits
    if spec.indian_grouping:
        head, tail = digits[:-3], digits[-3:]
        pairs = []
        while len(head) > 2:
            pairs.insert(0, head[-2:])
            head = head[:-2]
        if head:
            pairs.insert(0, head)
        return spec.group.join(pairs + [tail])
    groups = []
    while len(digits) > 3:
        groups.insert(0, digits[-3:])
        digits = digits[:-3]
    groups.insert(0, digits)
    return spec.group.join(groups)


def format_locale_money(amount: float, currency: str, locale: str | None) -> str:
    """`amount` in `currency`, written the way `locale` writes money: "$7.99"
    (en-AU, AUD), "A$7.99" (en-US, AUD), "7,99 €" (de-DE, EUR). A currency the
    table doesn't know prints its ISO code where the locale puts a symbol."""
    if amount != amount or amount in (float("inf"), float("-inf")):
        return "–"
    spec = _spec(locale)
    code = (currency or "").upper()
    affixes = spec.currency_affixes.get(code)
    if affixes is None:
        symbol_first = bool(spec.currency_affixes["EUR"][0])
        affixes = (f"{code} ", "") if symbol_first else ("", f" {code}")
    # Half away from zero on ties, like the SPA's Intl output.
    whole, fraction = str(Decimal(abs(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)).split(".")
    number = f"{_group_digits(whole, spec)}{spec.decimal}{fraction}"
    sign = "-" if round(amount, 2) < 0 else ""
    return f"{sign}{affixes[0]}{number}{affixes[1]}"


# ── Tables (derived from Intl, see the module docstring) ───────────────

_LOCALES: dict[str, _LocaleSpec] = {
    'en-AU': _LocaleSpec(
        date='{d} {MMM} {y}', time='{h}:{mm}\u202f{a}', joiner=', ',
        day='{EEE}, {d} {MMM}', am='am', pm='pm',
        months=('Jan', 'Feb', 'Mar', 'Apr', 'May', 'June', 'July', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec'),
        weekdays=('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'),
        group=',', decimal='.', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('$', ''),
            'NZD': ('NZD\xa0', ''),
            'USD': ('USD\xa0', ''),
            'GBP': ('GBP\xa0', ''),
            'EUR': ('EUR\xa0', ''),
            'CAD': ('CAD\xa0', ''),
            'BRL': ('BRL\xa0', ''),
            'CHF': ('CHF\xa0', ''),
            'CNY': ('CNY\xa0', ''),
            'DKK': ('DKK\xa0', ''),
            'HKD': ('HKD\xa0', ''),
            'INR': ('INR\xa0', ''),
            'JPY': ('JPY\xa0', ''),
            'MXN': ('MXN\xa0', ''),
            'NOK': ('NOK\xa0', ''),
            'PLN': ('PLN\xa0', ''),
            'SEK': ('SEK\xa0', ''),
            'SGD': ('SGD\xa0', ''),
            'ZAR': ('ZAR\xa0', ''),
        },
    ),
    'en-NZ': _LocaleSpec(
        date='{d} {MMM} {y}', time='{h}:{mm}\u202f{a}', joiner=', ',
        day='{EEE}, {d} {MMM}', am='am', pm='pm',
        months=('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec'),
        weekdays=('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'),
        group=',', decimal='.', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('A$', ''),
            'NZD': ('$', ''),
            'USD': ('US$', ''),
            'GBP': ('\xa3', ''),
            'EUR': ('\u20ac', ''),
            'CAD': ('CA$', ''),
            'BRL': ('R$', ''),
            'CHF': ('CHF\xa0', ''),
            'CNY': ('CN\xa5', ''),
            'DKK': ('DKK\xa0', ''),
            'HKD': ('HK$', ''),
            'INR': ('\u20b9', ''),
            'JPY': ('JP\xa5', ''),
            'MXN': ('MX$', ''),
            'NOK': ('NOK\xa0', ''),
            'PLN': ('PLN\xa0', ''),
            'SEK': ('SEK\xa0', ''),
            'SGD': ('SGD\xa0', ''),
            'ZAR': ('ZAR\xa0', ''),
        },
    ),
    'en-GB': _LocaleSpec(
        date='{d} {MMM} {y}', time='{HH}:{mm}', joiner=', ',
        day='{EEE} {d} {MMM}', am='', pm='',
        months=('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec'),
        weekdays=('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'),
        group=',', decimal='.', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('A$', ''),
            'NZD': ('NZ$', ''),
            'USD': ('US$', ''),
            'GBP': ('\xa3', ''),
            'EUR': ('\u20ac', ''),
            'CAD': ('CA$', ''),
            'BRL': ('R$', ''),
            'CHF': ('CHF\xa0', ''),
            'CNY': ('CN\xa5', ''),
            'DKK': ('DKK\xa0', ''),
            'HKD': ('HK$', ''),
            'INR': ('\u20b9', ''),
            'JPY': ('JP\xa5', ''),
            'MXN': ('MX$', ''),
            'NOK': ('NOK\xa0', ''),
            'PLN': ('PLN\xa0', ''),
            'SEK': ('SEK\xa0', ''),
            'SGD': ('SGD\xa0', ''),
            'ZAR': ('ZAR\xa0', ''),
        },
    ),
    'en-US': _LocaleSpec(
        date='{MMM} {d}, {y}', time='{h}:{mm}\u202f{a}', joiner=', ',
        day='{EEE}, {MMM} {d}', am='AM', pm='PM',
        months=('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'),
        weekdays=('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'),
        group=',', decimal='.', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('A$', ''),
            'NZD': ('NZ$', ''),
            'USD': ('$', ''),
            'GBP': ('\xa3', ''),
            'EUR': ('\u20ac', ''),
            'CAD': ('CA$', ''),
            'BRL': ('R$', ''),
            'CHF': ('CHF\xa0', ''),
            'CNY': ('CN\xa5', ''),
            'DKK': ('DKK\xa0', ''),
            'HKD': ('HK$', ''),
            'INR': ('\u20b9', ''),
            'JPY': ('\xa5', ''),
            'MXN': ('MX$', ''),
            'NOK': ('NOK\xa0', ''),
            'PLN': ('PLN\xa0', ''),
            'SEK': ('SEK\xa0', ''),
            'SGD': ('SGD\xa0', ''),
            'ZAR': ('ZAR\xa0', ''),
        },
    ),
    'en-CA': _LocaleSpec(
        date='{MMM} {d}, {y}', time='{h}:{mm}\u202f{a}', joiner=', ',
        day='{EEE}, {MMM} {d}', am='a.m.', pm='p.m.',
        months=('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'),
        weekdays=('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'),
        group=',', decimal='.', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('A$', ''),
            'NZD': ('NZ$', ''),
            'USD': ('US$', ''),
            'GBP': ('\xa3', ''),
            'EUR': ('\u20ac', ''),
            'CAD': ('$', ''),
            'BRL': ('R$', ''),
            'CHF': ('CHF\xa0', ''),
            'CNY': ('CN\xa5', ''),
            'DKK': ('DKK\xa0', ''),
            'HKD': ('HK$', ''),
            'INR': ('\u20b9', ''),
            'JPY': ('JP\xa5', ''),
            'MXN': ('MX$', ''),
            'NOK': ('NOK\xa0', ''),
            'PLN': ('PLN\xa0', ''),
            'SEK': ('SEK\xa0', ''),
            'SGD': ('SGD\xa0', ''),
            'ZAR': ('ZAR\xa0', ''),
        },
    ),
    'en-IE': _LocaleSpec(
        date='{d} {MMM} {y}', time='{HH}:{mm}', joiner=', ',
        day='{EEE}, {d} {MMM}', am='', pm='',
        months=('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec'),
        weekdays=('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'),
        group=',', decimal='.', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('A$', ''),
            'NZD': ('NZ$', ''),
            'USD': ('US$', ''),
            'GBP': ('\xa3', ''),
            'EUR': ('\u20ac', ''),
            'CAD': ('CA$', ''),
            'BRL': ('R$', ''),
            'CHF': ('CHF\xa0', ''),
            'CNY': ('CN\xa5', ''),
            'DKK': ('DKK\xa0', ''),
            'HKD': ('HK$', ''),
            'INR': ('\u20b9', ''),
            'JPY': ('JP\xa5', ''),
            'MXN': ('MX$', ''),
            'NOK': ('NOK\xa0', ''),
            'PLN': ('PLN\xa0', ''),
            'SEK': ('SEK\xa0', ''),
            'SGD': ('SGD\xa0', ''),
            'ZAR': ('ZAR\xa0', ''),
        },
    ),
    'en-IN': _LocaleSpec(
        date='{d} {MMM} {y}', time='{h}:{mm}\u202f{a}', joiner=', ',
        day='{EEE}, {d} {MMM}', am='am', pm='pm',
        months=('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec'),
        weekdays=('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'),
        group=',', decimal='.', min_grouping=1, indian_grouping=True,
        currency_affixes={
            'AUD': ('A$', ''),
            'NZD': ('NZ$', ''),
            'USD': ('$', ''),
            'GBP': ('\xa3', ''),
            'EUR': ('\u20ac', ''),
            'CAD': ('CA$', ''),
            'BRL': ('R$', ''),
            'CHF': ('CHF\xa0', ''),
            'CNY': ('CN\xa5', ''),
            'DKK': ('DKK\xa0', ''),
            'HKD': ('HK$', ''),
            'INR': ('\u20b9', ''),
            'JPY': ('JP\xa5', ''),
            'MXN': ('MX$', ''),
            'NOK': ('NOK\xa0', ''),
            'PLN': ('PLN\xa0', ''),
            'SEK': ('SEK\xa0', ''),
            'SGD': ('SGD\xa0', ''),
            'ZAR': ('ZAR\xa0', ''),
        },
    ),
    'en-SG': _LocaleSpec(
        date='{d} {MMM} {y}', time='{h}:{mm}\u202f{a}', joiner=', ',
        day='{EEE}, {d} {MMM}', am='am', pm='pm',
        months=('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec'),
        weekdays=('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'),
        group=',', decimal='.', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('A$', ''),
            'NZD': ('NZ$', ''),
            'USD': ('US$', ''),
            'GBP': ('\xa3', ''),
            'EUR': ('\u20ac', ''),
            'CAD': ('CA$', ''),
            'BRL': ('R$', ''),
            'CHF': ('CHF\xa0', ''),
            'CNY': ('CN\xa5', ''),
            'DKK': ('DKK\xa0', ''),
            'HKD': ('HK$', ''),
            'INR': ('\u20b9', ''),
            'JPY': ('JP\xa5', ''),
            'MXN': ('MX$', ''),
            'NOK': ('NOK\xa0', ''),
            'PLN': ('PLN\xa0', ''),
            'SEK': ('SEK\xa0', ''),
            'SGD': ('$', ''),
            'ZAR': ('ZAR\xa0', ''),
        },
    ),
    'en-ZA': _LocaleSpec(
        date='{dd} {MMM} {y}', time='{HH}:{mm}', joiner=', ',
        day='{EEE}, {dd} {MMM}', am='', pm='',
        months=('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sept', 'Oct', 'Nov', 'Dec'),
        weekdays=('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'),
        group='\xa0', decimal=',', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('A$', ''),
            'NZD': ('NZ$', ''),
            'USD': ('US$', ''),
            'GBP': ('\xa3', ''),
            'EUR': ('\u20ac', ''),
            'CAD': ('CA$', ''),
            'BRL': ('R$', ''),
            'CHF': ('CHF\xa0', ''),
            'CNY': ('CN\xa5', ''),
            'DKK': ('DKK\xa0', ''),
            'HKD': ('HK$', ''),
            'INR': ('\u20b9', ''),
            'JPY': ('JP\xa5', ''),
            'MXN': ('MX$', ''),
            'NOK': ('NOK\xa0', ''),
            'PLN': ('PLN\xa0', ''),
            'SEK': ('SEK\xa0', ''),
            'SGD': ('SGD\xa0', ''),
            'ZAR': ('R\xa0', ''),
        },
    ),
    'da-DK': _LocaleSpec(
        date='{d}. {MMM} {y}', time='{HH}.{mm}', joiner=', ',
        day='{EEE} {d}. {MMM}', am='', pm='',
        months=('jan.', 'feb.', 'mar.', 'apr.', 'maj', 'jun.', 'jul.', 'aug.', 'sep.', 'okt.', 'nov.', 'dec.'),
        weekdays=('man.', 'tirs.', 'ons.', 'tors.', 'fre.', 'l\xf8r.', 's\xf8n.'),
        group='.', decimal=',', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('', '\xa0AU$'),
            'NZD': ('', '\xa0NZ$'),
            'USD': ('', '\xa0US$'),
            'GBP': ('', '\xa0\xa3'),
            'EUR': ('', '\xa0\u20ac'),
            'CAD': ('', '\xa0CA$'),
            'BRL': ('', '\xa0R$'),
            'CHF': ('', '\xa0CHF'),
            'CNY': ('', '\xa0CN\xa5'),
            'DKK': ('', '\xa0kr.'),
            'HKD': ('', '\xa0HK$'),
            'INR': ('', '\xa0\u20b9'),
            'JPY': ('', '\xa0JP\xa5'),
            'MXN': ('', '\xa0MX$'),
            'NOK': ('', '\xa0NOK'),
            'PLN': ('', '\xa0PLN'),
            'SEK': ('', '\xa0SEK'),
            'SGD': ('', '\xa0SGD'),
            'ZAR': ('', '\xa0ZAR'),
        },
    ),
    'nl-NL': _LocaleSpec(
        date='{d} {MMM} {y}', time='{HH}:{mm}', joiner=', ',
        day='{EEE} {d} {MMM}', am='', pm='',
        months=('jan', 'feb', 'mrt', 'apr', 'mei', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec'),
        weekdays=('ma', 'di', 'wo', 'do', 'vr', 'za', 'zo'),
        group='.', decimal=',', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('AU$\xa0', ''),
            'NZD': ('NZ$\xa0', ''),
            'USD': ('US$\xa0', ''),
            'GBP': ('\xa3\xa0', ''),
            'EUR': ('\u20ac\xa0', ''),
            'CAD': ('C$\xa0', ''),
            'BRL': ('R$\xa0', ''),
            'CHF': ('CHF\xa0', ''),
            'CNY': ('CN\xa5\xa0', ''),
            'DKK': ('DKK\xa0', ''),
            'HKD': ('HK$\xa0', ''),
            'INR': ('\u20b9\xa0', ''),
            'JPY': ('JP\xa5\xa0', ''),
            'MXN': ('MX$\xa0', ''),
            'NOK': ('NOK\xa0', ''),
            'PLN': ('PLN\xa0', ''),
            'SEK': ('SEK\xa0', ''),
            'SGD': ('SGD\xa0', ''),
            'ZAR': ('ZAR\xa0', ''),
        },
    ),
    'fr-CA': _LocaleSpec(
        date='{d} {MMM} {y}', time='{HH} h {mm}', joiner=', ',
        day='{EEE} {d} {MMM}', am='', pm='',
        months=('janv.', 'f\xe9vr.', 'mars', 'avr.', 'mai', 'juin', 'juill.', 'ao\xfbt', 'sept.', 'oct.', 'nov.', 'd\xe9c.'),
        weekdays=('lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.', 'dim.'),
        group='\xa0', decimal=',', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('', '\xa0$\xa0AU'),
            'NZD': ('', '\xa0$\xa0NZ'),
            'USD': ('', '\xa0$\xa0US'),
            'GBP': ('', '\xa0\xa3'),
            'EUR': ('', '\xa0\u20ac'),
            'CAD': ('', '\xa0$'),
            'BRL': ('', '\xa0R$'),
            'CHF': ('', '\xa0CHF'),
            'CNY': ('', '\xa0CN\xa5'),
            'DKK': ('', '\xa0DKK'),
            'HKD': ('', '\xa0$\xa0HK'),
            'INR': ('', '\xa0INR'),
            'JPY': ('', '\xa0\xa5'),
            'MXN': ('', '\xa0MXN'),
            'NOK': ('', '\xa0NOK'),
            'PLN': ('', '\xa0PLN'),
            'SEK': ('', '\xa0SEK'),
            'SGD': ('', '\xa0$\xa0SG'),
            'ZAR': ('', '\xa0ZAR'),
        },
    ),
    'fr-FR': _LocaleSpec(
        date='{d} {MMM} {y}', time='{HH}:{mm}', joiner=', ',
        day='{EEE} {d} {MMM}', am='', pm='',
        months=('janv.', 'f\xe9vr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'ao\xfbt', 'sept.', 'oct.', 'nov.', 'd\xe9c.'),
        weekdays=('lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.', 'dim.'),
        group='\u202f', decimal=',', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('', '\xa0$AU'),
            'NZD': ('', '\xa0$NZ'),
            'USD': ('', '\xa0$US'),
            'GBP': ('', '\xa0\xa3GB'),
            'EUR': ('', '\xa0\u20ac'),
            'CAD': ('', '\xa0$CA'),
            'BRL': ('', '\xa0R$'),
            'CHF': ('', '\xa0CHF'),
            'CNY': ('', '\xa0CNY'),
            'DKK': ('', '\xa0DKK'),
            'HKD': ('', '\xa0HKD'),
            'INR': ('', '\xa0\u20b9'),
            'JPY': ('', '\xa0JPY'),
            'MXN': ('', '\xa0$MX'),
            'NOK': ('', '\xa0NOK'),
            'PLN': ('', '\xa0PLN'),
            'SEK': ('', '\xa0SEK'),
            'SGD': ('', '\xa0$SG'),
            'ZAR': ('', '\xa0ZAR'),
        },
    ),
    'de-DE': _LocaleSpec(
        date='{dd}.{MM}.{y}', time='{HH}:{mm}', joiner=', ',
        day='{EEE}, {d}. {MMM}', am='', pm='',
        months=('01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'),
        day_months=('Jan.', 'Feb.', 'M\xe4rz', 'Apr.', 'Mai', 'Juni', 'Juli', 'Aug.', 'Sept.', 'Okt.', 'Nov.', 'Dez.'),
        weekdays=('Mo.', 'Di.', 'Mi.', 'Do.', 'Fr.', 'Sa.', 'So.'),
        group='.', decimal=',', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('', '\xa0AU$'),
            'NZD': ('', '\xa0NZ$'),
            'USD': ('', '\xa0$'),
            'GBP': ('', '\xa0\xa3'),
            'EUR': ('', '\xa0\u20ac'),
            'CAD': ('', '\xa0CA$'),
            'BRL': ('', '\xa0R$'),
            'CHF': ('', '\xa0CHF'),
            'CNY': ('', '\xa0CN\xa5'),
            'DKK': ('', '\xa0DKK'),
            'HKD': ('', '\xa0HK$'),
            'INR': ('', '\xa0\u20b9'),
            'JPY': ('', '\xa0\xa5'),
            'MXN': ('', '\xa0MX$'),
            'NOK': ('', '\xa0NOK'),
            'PLN': ('', '\xa0PLN'),
            'SEK': ('', '\xa0SEK'),
            'SGD': ('', '\xa0SGD'),
            'ZAR': ('', '\xa0ZAR'),
        },
    ),
    'it-IT': _LocaleSpec(
        date='{d} {MMM} {y}', time='{HH}:{mm}', joiner=', ',
        day='{EEE} {d} {MMM}', am='', pm='',
        months=('gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic'),
        weekdays=('lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom'),
        group='.', decimal=',', min_grouping=2, indian_grouping=False,
        currency_affixes={
            'AUD': ('', '\xa0A$'),
            'NZD': ('', '\xa0NZ$'),
            'USD': ('', '\xa0USD'),
            'GBP': ('', '\xa0\xa3'),
            'EUR': ('', '\xa0\u20ac'),
            'CAD': ('', '\xa0CA$'),
            'BRL': ('', '\xa0BRL'),
            'CHF': ('', '\xa0CHF'),
            'CNY': ('', '\xa0CN\xa5'),
            'DKK': ('', '\xa0DKK'),
            'HKD': ('', '\xa0HKD'),
            'INR': ('', '\xa0INR'),
            'JPY': ('', '\xa0JPY'),
            'MXN': ('', '\xa0MXN'),
            'NOK': ('', '\xa0NOK'),
            'PLN': ('', '\xa0PLN'),
            'SEK': ('', '\xa0SEK'),
            'SGD': ('', '\xa0SGD'),
            'ZAR': ('', '\xa0ZAR'),
        },
    ),
    'ja-JP': _LocaleSpec(
        date='{y}/{MM}/{dd}', time='{H}:{mm}', joiner=' ',
        day='{MMM}\u6708{d}\u65e5({EEE})', am='', pm='',
        months=('01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'),
        day_months=('1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'),
        weekdays=('\u6708', '\u706b', '\u6c34', '\u6728', '\u91d1', '\u571f', '\u65e5'),
        group=',', decimal='.', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('A$', ''),
            'NZD': ('NZ$', ''),
            'USD': ('$', ''),
            'GBP': ('\xa3', ''),
            'EUR': ('\u20ac', ''),
            'CAD': ('CA$', ''),
            'BRL': ('R$', ''),
            'CHF': ('CHF\xa0', ''),
            'CNY': ('\u5143\xa0', ''),
            'DKK': ('DKK\xa0', ''),
            'HKD': ('HK$', ''),
            'INR': ('\u20b9', ''),
            'JPY': ('\uffe5', ''),
            'MXN': ('MX$', ''),
            'NOK': ('NOK\xa0', ''),
            'PLN': ('PLN\xa0', ''),
            'SEK': ('SEK\xa0', ''),
            'SGD': ('SGD\xa0', ''),
            'ZAR': ('ZAR\xa0', ''),
        },
    ),
    'nb-NO': _LocaleSpec(
        date='{d}. {MMM} {y}', time='{HH}:{mm}', joiner=', ',
        day='{EEE} {d}. {MMM}', am='', pm='',
        months=('jan.', 'feb.', 'mars', 'apr.', 'mai', 'juni', 'juli', 'aug.', 'sep.', 'okt.', 'nov.', 'des.'),
        weekdays=('man.', 'tir.', 'ons.', 'tor.', 'fre.', 'l\xf8r.', 's\xf8n.'),
        group='\xa0', decimal=',', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('', '\xa0AUD'),
            'NZD': ('', '\xa0NZD'),
            'USD': ('', '\xa0USD'),
            'GBP': ('', '\xa0\xa3'),
            'EUR': ('', '\xa0\u20ac'),
            'CAD': ('', '\xa0CAD'),
            'BRL': ('', '\xa0BRL'),
            'CHF': ('', '\xa0CHF'),
            'CNY': ('', '\xa0CNY'),
            'DKK': ('', '\xa0DKK'),
            'HKD': ('', '\xa0HKD'),
            'INR': ('', '\xa0INR'),
            'JPY': ('', '\xa0JPY'),
            'MXN': ('', '\xa0MXN'),
            'NOK': ('', '\xa0kr'),
            'PLN': ('', '\xa0PLN'),
            'SEK': ('', '\xa0SEK'),
            'SGD': ('', '\xa0SGD'),
            'ZAR': ('', '\xa0ZAR'),
        },
    ),
    'pl-PL': _LocaleSpec(
        date='{d} {MMM} {y}', time='{HH}:{mm}', joiner=', ',
        day='{EEE}, {d} {MMM}', am='', pm='',
        months=('sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz', 'pa\u017a', 'lis', 'gru'),
        weekdays=('pon.', 'wt.', '\u015br.', 'czw.', 'pt.', 'sob.', 'niedz.'),
        group='\xa0', decimal=',', min_grouping=2, indian_grouping=False,
        currency_affixes={
            'AUD': ('', '\xa0AUD'),
            'NZD': ('', '\xa0NZD'),
            'USD': ('', '\xa0USD'),
            'GBP': ('', '\xa0GBP'),
            'EUR': ('', '\xa0\u20ac'),
            'CAD': ('', '\xa0CAD'),
            'BRL': ('', '\xa0R$'),
            'CHF': ('', '\xa0CHF'),
            'CNY': ('', '\xa0CNY'),
            'DKK': ('', '\xa0DKK'),
            'HKD': ('', '\xa0HKD'),
            'INR': ('', '\xa0INR'),
            'JPY': ('', '\xa0JPY'),
            'MXN': ('', '\xa0MXN'),
            'NOK': ('', '\xa0NOK'),
            'PLN': ('', '\xa0z\u0142'),
            'SEK': ('', '\xa0SEK'),
            'SGD': ('', '\xa0SGD'),
            'ZAR': ('', '\xa0ZAR'),
        },
    ),
    'pt-BR': _LocaleSpec(
        date='{d} de {MMM} de {y}', time='{HH}:{mm}', joiner=', ',
        day='{EEE}, {d} de {MMM}', am='', pm='',
        months=('jan.', 'fev.', 'mar.', 'abr.', 'mai.', 'jun.', 'jul.', 'ago.', 'set.', 'out.', 'nov.', 'dez.'),
        weekdays=('seg.', 'ter.', 'qua.', 'qui.', 'sex.', 's\xe1b.', 'dom.'),
        group='.', decimal=',', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('AU$\xa0', ''),
            'NZD': ('NZ$\xa0', ''),
            'USD': ('US$\xa0', ''),
            'GBP': ('\xa3\xa0', ''),
            'EUR': ('\u20ac\xa0', ''),
            'CAD': ('CA$\xa0', ''),
            'BRL': ('R$\xa0', ''),
            'CHF': ('CHF\xa0', ''),
            'CNY': ('CN\xa5\xa0', ''),
            'DKK': ('DKK\xa0', ''),
            'HKD': ('HK$\xa0', ''),
            'INR': ('\u20b9\xa0', ''),
            'JPY': ('JP\xa5\xa0', ''),
            'MXN': ('MX$\xa0', ''),
            'NOK': ('NOK\xa0', ''),
            'PLN': ('PLN\xa0', ''),
            'SEK': ('SEK\xa0', ''),
            'SGD': ('SGD\xa0', ''),
            'ZAR': ('ZAR\xa0', ''),
        },
    ),
    'pt-PT': _LocaleSpec(
        date='{dd}/{MM}/{y}', time='{HH}:{mm}', joiner=', ',
        day='{EEE}, {d}/{MMM}', am='', pm='',
        months=('01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'),
        weekdays=('segunda', 'ter\xe7a', 'quarta', 'quinta', 'sexta', 's\xe1bado', 'domingo'),
        group='\xa0', decimal=',', min_grouping=2, indian_grouping=False,
        currency_affixes={
            'AUD': ('', '\xa0AU$'),
            'NZD': ('', '\xa0NZ$'),
            'USD': ('', '\xa0US$'),
            'GBP': ('', '\xa0\xa3'),
            'EUR': ('', '\xa0\u20ac'),
            'CAD': ('', '\xa0CA$'),
            'BRL': ('', '\xa0R$'),
            'CHF': ('', '\xa0CHF'),
            'CNY': ('', '\xa0CN\xa5'),
            'DKK': ('', '\xa0DKK'),
            'HKD': ('', '\xa0HK$'),
            'INR': ('', '\xa0\u20b9'),
            'JPY': ('', '\xa0JP\xa5'),
            'MXN': ('', '\xa0MX$'),
            'NOK': ('', '\xa0NOK'),
            'PLN': ('', '\xa0PLN'),
            'SEK': ('', '\xa0SEK'),
            'SGD': ('', '\xa0SGD'),
            'ZAR': ('', '\xa0ZAR'),
        },
    ),
    'es-ES': _LocaleSpec(
        date='{d} {MMM} {y}', time='{H}:{mm}', joiner=', ',
        day='{EEE}, {d} {MMM}', am='', pm='',
        months=('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sept', 'oct', 'nov', 'dic'),
        weekdays=('lun', 'mar', 'mi\xe9', 'jue', 'vie', 's\xe1b', 'dom'),
        group='.', decimal=',', min_grouping=2, indian_grouping=False,
        currency_affixes={
            'AUD': ('', '\xa0AUD'),
            'NZD': ('', '\xa0NZD'),
            'USD': ('', '\xa0US$'),
            'GBP': ('', '\xa0GBP'),
            'EUR': ('', '\xa0\u20ac'),
            'CAD': ('', '\xa0CAD'),
            'BRL': ('', '\xa0BRL'),
            'CHF': ('', '\xa0CHF'),
            'CNY': ('', '\xa0CNY'),
            'DKK': ('', '\xa0DKK'),
            'HKD': ('', '\xa0HKD'),
            'INR': ('', '\xa0INR'),
            'JPY': ('', '\xa0JPY'),
            'MXN': ('', '\xa0MXN'),
            'NOK': ('', '\xa0NOK'),
            'PLN': ('', '\xa0PLN'),
            'SEK': ('', '\xa0SEK'),
            'SGD': ('', '\xa0SGD'),
            'ZAR': ('', '\xa0ZAR'),
        },
    ),
    'es-MX': _LocaleSpec(
        date='{d} {MMM} {y}', time='{h}:{mm}\u202f{a}', joiner=', ',
        day='{EEE} {d} de {MMM}', am='a.m.', pm='p.m.',
        months=('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'),
        weekdays=('lun', 'mar', 'mi\xe9', 'jue', 'vie', 's\xe1b', 'dom'),
        group=',', decimal='.', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('AUD\xa0', ''),
            'NZD': ('NZD\xa0', ''),
            'USD': ('USD\xa0', ''),
            'GBP': ('GBP\xa0', ''),
            'EUR': ('EUR\xa0', ''),
            'CAD': ('CAD\xa0', ''),
            'BRL': ('BRL\xa0', ''),
            'CHF': ('CHF\xa0', ''),
            'CNY': ('CNY\xa0', ''),
            'DKK': ('DKK\xa0', ''),
            'HKD': ('HKD\xa0', ''),
            'INR': ('INR\xa0', ''),
            'JPY': ('JPY\xa0', ''),
            'MXN': ('$', ''),
            'NOK': ('NOK\xa0', ''),
            'PLN': ('PLN\xa0', ''),
            'SEK': ('SEK\xa0', ''),
            'SGD': ('SGD\xa0', ''),
            'ZAR': ('ZAR\xa0', ''),
        },
    ),
    'sv-SE': _LocaleSpec(
        date='{d} {MMM} {y}', time='{HH}:{mm}', joiner=' ',
        day='{EEE} {d} {MMM}', am='', pm='',
        months=('jan.', 'feb.', 'mars', 'apr.', 'maj', 'juni', 'juli', 'aug.', 'sep.', 'okt.', 'nov.', 'dec.'),
        weekdays=('m\xe5n', 'tis', 'ons', 'tors', 'fre', 'l\xf6r', 's\xf6n'),
        group='\xa0', decimal=',', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('', '\xa0AUD'),
            'NZD': ('', '\xa0NZD'),
            'USD': ('', '\xa0US$'),
            'GBP': ('', '\xa0GBP'),
            'EUR': ('', '\xa0\u20ac'),
            'CAD': ('', '\xa0CA$'),
            'BRL': ('', '\xa0BR$'),
            'CHF': ('', '\xa0CHF'),
            'CNY': ('', '\xa0CNY'),
            'DKK': ('', '\xa0Dkr'),
            'HKD': ('', '\xa0HKD'),
            'INR': ('', '\xa0INR'),
            'JPY': ('', '\xa0JPY'),
            'MXN': ('', '\xa0MX$'),
            'NOK': ('', '\xa0Nkr'),
            'PLN': ('', '\xa0PLN'),
            'SEK': ('', '\xa0kr'),
            'SGD': ('', '\xa0SGD'),
            'ZAR': ('', '\xa0ZAR'),
        },
    ),
    'zh-CN': _LocaleSpec(
        date='{y}\u5e74{M}\u6708{d}\u65e5', time='{HH}:{mm}', joiner=' ',
        day='{MMM}\u6708{d}\u65e5{EEE}', am='', pm='',
        months=('1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'),
        weekdays=('\u5468\u4e00', '\u5468\u4e8c', '\u5468\u4e09', '\u5468\u56db', '\u5468\u4e94', '\u5468\u516d', '\u5468\u65e5'),
        group=',', decimal='.', min_grouping=1, indian_grouping=False,
        currency_affixes={
            'AUD': ('AU$', ''),
            'NZD': ('NZ$', ''),
            'USD': ('US$', ''),
            'GBP': ('\xa3', ''),
            'EUR': ('\u20ac', ''),
            'CAD': ('CA$', ''),
            'BRL': ('R$', ''),
            'CHF': ('CHF\xa0', ''),
            'CNY': ('\xa5', ''),
            'DKK': ('DKK\xa0', ''),
            'HKD': ('HK$', ''),
            'INR': ('\u20b9', ''),
            'JPY': ('JP\xa5', ''),
            'MXN': ('MX$', ''),
            'NOK': ('NOK\xa0', ''),
            'PLN': ('PLN\xa0', ''),
            'SEK': ('SEK\xa0', ''),
            'SGD': ('SGD\xa0', ''),
            'ZAR': ('ZAR\xa0', ''),
        },
    ),
}
