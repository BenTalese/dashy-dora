"""Drift check for ``dora_api/domain/locale_format.py`` against Node's Intl.

The server's locale tables were derived from Node's full-ICU ``Intl`` (FU-969
(6)). This runs ``scripts/locale_format_reference.mjs`` over every locale and
currency in the tables, then compares what ``format_date`` / ``format_day`` /
``format_weekday`` / ``format_time`` / ``format_datetime`` /
``format_locale_money`` write with what Intl writes for the same samples.

Run from the repo root: ``python scripts/check_locale_format.py [--strict]``
Exit 0 when they agree, 1 with a list of differences otherwise.

By default a space, no-break space and narrow no-break space count as the same
character: ICU moves between them across versions (ICU 77 writes "4:50 pm" with U+202F
for en-AU, ICU 78 with a plain space), and browsers ship different ICUs, so that is not
drift the tables can fix. ``--strict`` compares exactly.

Use it after adding a locale or currency to the Region page
(``web_app/src/models/regionChoices.ts``) or editing the tables. Needs ``node``
on PATH. Intl output moves with the ICU version (the tables were taken from
Node 24 / ICU 77), so a difference after a Node upgrade can be ICU's change
rather than a table bug; the report prints both versions.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dora_api.domain import locale_format as lf  # noqa: E402

# Every month and weekday, single- and double-digit days.
DATES = [date(2026, 1, 5).fromordinal(date(2026, 1, 5).toordinal() + 31 * k) for k in range(12)] + [
    date(2026, 10, 30), date(2027, 3, 1),
]
TIMES = [time(0, 5), time(9, 7), time(12, 0), time(16, 50), time(23, 59)]
# Non-negative only: the module documents that a negative always leads with "-".
AMOUNTS = [0, 7.99, 1234.5, 12345.67, 1234567.5]


def _reference(locales: list[str], currencies: list[str]) -> dict:
    payload = json.dumps({
        "locales": locales,
        "currencies": currencies,
        "dates": [d.isoformat() for d in DATES],
        "times": [t.strftime("%H:%M") for t in TIMES],
        "amounts": AMOUNTS,
    })
    script = REPO_ROOT / "scripts" / "locale_format_reference.mjs"
    result = subprocess.run(
        ["node", str(script), payload], capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return json.loads(result.stdout)


_SPACES = str.maketrans({"\u202f": " ", "\xa0": " "})


def main() -> int:
    strict = "--strict" in sys.argv[1:]
    locales = list(lf._LOCALES)
    currencies = list(lf._LOCALES[lf.DEFAULT_LOCALE].currency_affixes)
    ref = _reference(locales, currencies)
    diffs: list[str] = []

    def check(locale: str, what: str, ours: str, theirs: str) -> None:
        same = ours == theirs if strict else ours.translate(_SPACES) == theirs.translate(_SPACES)
        if not same:
            diffs.append(f"{locale} {what}: python {ours!r} != intl {theirs!r}")

    for locale in locales:
        r = ref["locales"][locale]
        for i, d in enumerate(DATES):
            check(locale, f"date {d}", lf.format_date(d, locale), r["date"][i])
            check(locale, f"day {d}", lf.format_day(d, locale), r["day"][i])
            check(locale, f"weekday {d}", lf.format_weekday(d, locale), r["weekday"][i])
        for i, t in enumerate(TIMES):
            check(locale, f"time {t}", lf.format_time(t, locale), r["time"][i])
            dt = datetime.combine(date(2026, 10, 30), t)
            check(locale, f"datetime {t}", lf.format_datetime(dt, locale), r["datetime"][i])
        for currency in currencies:
            for i, amount in enumerate(AMOUNTS):
                check(
                    locale, f"money {currency} {amount}",
                    lf.format_locale_money(amount, currency, locale), r["money"][currency][i],
                )

    print(f"node {ref['node']}, ICU {ref['icu']}: {len(locales)} locales x {len(currencies)} currencies")
    if diffs:
        print(f"{len(diffs)} difference(s):")
        for line in diffs:
            print("  " + line)
        return 1
    print("locale_format tables match Intl.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
