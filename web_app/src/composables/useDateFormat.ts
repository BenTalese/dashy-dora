import { ref } from 'vue';
import {
    currentLocale,
    ensureLocalePolicy,
} from 'src/composables/useMoney';
import {
    daysFromToday,
    householdTimezone,
    onHouseholdTimezoneChange,
    parseLocalIso,
    shiftDays,
} from 'src/helpers/weekDates';

// DR-14 / D-006 — the single date/time formatting authority. Every
// user-facing date goes through here so the whole app renders in the
// household's locale (e.g. 'en-AU' → "17/07/2026", not the browser's US
// "7/17/2026" — FU-578 #9). It reuses the ONE locale source already owned by
// `useMoney` (the install's `locale_policy.locale`), so money and dates can
// never drift apart (R-003). Templates never call `.toLocaleDateString()` /
// `.toLocaleString()` directly.
//
// Timezone: date-only values (the vast majority of Dora's renders — expiry,
// planned-for, effective dates) are tz-independent *as data*, but they must be
// PARSED as local midnight to render as the calendar day they name — see
// `toDate` below, and R-021's client-side counterpart. Instants (a string that
// carries a time, or an epoch number — audit `occurred_at`, `created_at`)
// render in the **household** timezone once `locale_policy.timezone` is known
// (`householdTimezone()`), so every member sees the household's wall clock
// rather than their device's; before that, the browser tz. `Date` objects are
// left in the browser tz: callers build them from local parts, and re-zoning
// them would shift the day they meant.

type DateInput = string | number | Date | null | undefined;

// Reactive mirror of the household zone. `weekDates.ts` holds the zone in a
// plain (Vue-free) variable; this version ref is bumped whenever it changes and
// read by the formatters below, so a template that rendered "Tomorrow" (or an
// instant) before `/health` landed re-renders once the zone is known.
const tzVersion = ref(0);
onHouseholdTimezoneChange(() => {
    tzVersion.value++;
});

/** The household zone, read through the reactive version so callers track it. */
function reactiveHouseholdTimezone(): string | null {
    void tzVersion.value;
    return householdTimezone();
}

/** True when `value` names an instant (rather than a calendar day or a
 *  caller-built local `Date`) and so should render in the household zone. */
function isInstant(value: DateInput): boolean {
    if (typeof value === 'number') return true;
    return typeof value === 'string' && parseLocalIso(value) === null;
}

function toDate(value: DateInput): Date | null {
    if (value === null || value === undefined || value === '') return null;
    if (value instanceof Date) {
        return Number.isFinite(value.getTime()) ? value : null;
    }
    if (typeof value === 'string') {
        // A bare YYYY-MM-DD names a calendar day, not an instant. `new Date()`
        // parses that form as **UTC** midnight per spec, and Intl then formats
        // in the *local* zone — so west of Greenwich every date-only value
        // rendered one day early. Measured in America/New_York before this fix:
        // `formatDate('2026-09-03')` → "02/09/2026".
        //
        // Parse it as local midnight instead, so the rendered day is the day the
        // string names in every timezone. Strings that carry a time (or an
        // explicit offset) fall through untouched — those ARE instants and must
        // not be shifted.
        const localDay = parseLocalIso(value);
        if (localDay) return localDay;
    }
    const d = new Date(value);
    return Number.isFinite(d.getTime()) ? d : null;
}

// Cache one Intl.DateTimeFormat per (locale | options) — construction isn't
// free and date-heavy pages (history, alerts, reports) hit it a lot. Rebuilt
// implicitly when the locale changes because the key includes it.
const formatterCache = new Map<string, Intl.DateTimeFormat>();

function getFormatter(opts: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
    const locale = currentLocale();
    const key = `${locale}|${JSON.stringify(opts)}`;
    let fmt = formatterCache.get(key);
    if (!fmt) {
        fmt = new Intl.DateTimeFormat(locale, opts);
        formatterCache.set(key, fmt);
    }
    return fmt;
}

/** Format a date value in the household locale. Pass Intl options exactly as
 *  you would to `toLocaleDateString` (the second arg) — the only difference is
 *  the locale is the install's, not the browser's. Invalid/empty input renders
 *  as an empty string, so guard with `formatDate(x) || fallback` where a raw
 *  echo is wanted. Default (no opts) is the locale's short numeric date. */
export function formatDate(value: DateInput, opts: Intl.DateTimeFormatOptions = {}): string {
    // Fire-and-forget so any call site that imports `formatDate` directly
    // (without the composable) still triggers the one-per-session locale
    // probe. Idempotent; until it resolves we render the AU default, which is
    // already correct for the shipping market — never the browser's US format.
    void ensureLocalePolicy();
    const d = toDate(value);
    if (!d) return '';
    const tz = isInstant(value) ? reactiveHouseholdTimezone() : null;
    return getFormatter(tz && !opts.timeZone ? { ...opts, timeZone: tz } : opts).format(d);
}

/** Date + time, in the household locale (replaces bare `.toLocaleString()`).
 *  Medium date + short time reads cleanly and consistently ("17 Jul 2026,
 *  12:15 pm") — no seconds, no US-vs-ISO mixing (FU-578 #32). */
export function formatDateTime(value: DateInput): string {
    return formatDate(value, { dateStyle: 'medium', timeStyle: 'short' });
}

/** Name a calendar day the way a person would: "Today", "Tomorrow", the weekday
 *  if it's inside the coming week, otherwise the locale's short date.
 *
 *  Takes a YYYY-MM-DD string (the shape every `scheduled_for` / expiry / planned
 *  date has). Lifted out of `DashboardPage.vue`, where it was doing
 *  `new Date(iso)` and therefore naming the **wrong day** for every user west of
 *  Greenwich — tomorrow's dinner read "Today". It now runs on
 *  `daysFromToday`, which compares local midnights.
 *
 *  `now` is injectable for tests only. */
export function formatRelativeDay(value: string, now: Date = new Date()): string {
    // Track the household zone: "Today"/"Tomorrow" don't pass through
    // `formatDate`, so without this they'd never recompute when it lands.
    void reactiveHouseholdTimezone();
    const diff = daysFromToday(value, now);
    // Not a bare calendar date — fall back to the plain formatter rather than
    // guessing at a relative label for an instant.
    if (diff === null) return formatDate(value);
    if (diff === 0) return 'Today';
    if (diff === 1) return 'Tomorrow';
    if (diff === -1) return 'Yesterday';
    // Inside the coming week, the weekday alone is the most readable form
    // ("Thursday"); beyond that it stops being unambiguous.
    if (diff > 1 && diff < 7) return formatDate(value, { weekday: 'long' });
    return formatDate(value);
}

/** "October 2026" / "Oktober 2026" for the month containing a YYYY-MM-DD date —
 *  the calendar heading. Parsed as that calendar day (never `Date.UTC`, which
 *  rendered October as "September" west of Greenwich). */
export function formatMonthYear(value: string): string {
    return formatDate(value, { month: 'long', year: 'numeric' });
}

// 2024-01-01 is a Monday; the seven days from it give Mon..Sun in order.
const A_MONDAY = '2024-01-01';

/** Narrow weekday letters Monday-first in the household locale — en "M T W T F
 *  S S", de "M D M D F S S". Keyed so a template can `v-for` them even though
 *  letters repeat. */
export function weekdayLetters(): { key: string; letter: string }[] {
    return Array.from({ length: 7 }, (_, i) => {
        const iso = shiftDays(A_MONDAY, i);
        return { key: iso, letter: formatDate(iso, { weekday: 'narrow' }) };
    });
}

export function useDateFormat() {
    void ensureLocalePolicy();
    return {
        formatDate,
        formatDateTime,
        formatRelativeDay,
        formatMonthYear,
        weekdayLetters,
    };
}
