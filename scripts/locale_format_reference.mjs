// Reference output for `dora_api/domain/locale_format.py`, straight from Intl.
//
// The server's locale tables were derived from Node's full-ICU Intl
// (FU-969 (6)). This prints what Intl itself writes for a set of samples so
// `scripts/check_locale_format.py` can compare the Python tables against it and
// catch drift (a locale or currency added on the Region page, or a hand edit).
//
// Input: one JSON argument {locales, currencies, dates, times, amounts}, where
// dates are "YYYY-MM-DD", times "HH:MM" and amounts numbers. Output: JSON on
// stdout keyed by locale. Every instant is built and formatted in UTC so the
// device's zone never leaks in. The options mirror the SPA's formatters
// (`useDateFormat.ts`, `useMoney.ts`), which pin money to two decimals.
//
// Run through the checker: `python scripts/check_locale_format.py`.

const spec = JSON.parse(process.argv[2]);

function instant(dateIso, timeHm = '00:00') {
    const [y, m, d] = dateIso.split('-').map(Number);
    const [hh, mm] = timeHm.split(':').map(Number);
    return new Date(Date.UTC(y, m - 1, d, hh, mm));
}

const out = { icu: process.versions.icu, node: process.version, locales: {} };
for (const locale of spec.locales) {
    const date = new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeZone: 'UTC' });
    const time = new Intl.DateTimeFormat(locale, { timeStyle: 'short', timeZone: 'UTC' });
    const dateTime = new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' });
    const day = new Intl.DateTimeFormat(locale, { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' });
    const weekday = new Intl.DateTimeFormat(locale, { weekday: 'short', timeZone: 'UTC' });
    const money = {};
    for (const currency of spec.currencies) {
        const fmt = new Intl.NumberFormat(locale, {
            style: 'currency', currency, minimumFractionDigits: 2, maximumFractionDigits: 2,
        });
        money[currency] = spec.amounts.map((a) => fmt.format(a));
    }
    out.locales[locale] = {
        date: spec.dates.map((d) => date.format(instant(d))),
        day: spec.dates.map((d) => day.format(instant(d))),
        weekday: spec.dates.map((d) => weekday.format(instant(d))),
        time: spec.times.map((t) => time.format(instant('2026-10-30', t))),
        datetime: spec.times.map((t) => dateTime.format(instant('2026-10-30', t))),
        money,
    };
}
process.stdout.write(JSON.stringify(out));
