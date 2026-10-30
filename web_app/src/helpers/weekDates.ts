// Week/date helpers shared by the meal planner page + its calendar widget
// (R-003: one source for the week-date logic). Every function builds a
// YYYY-MM-DD string from explicit calendar parts and uses UTC math — never
// `toISOString()` on a *local* Date, which is UTC-shifted and drifts a day in
// positive-offset zones near midnight (the C-2.K bug class).

/** Normalise any date/datetime string to a YYYY-MM-DD date string. */
export function isoDate(value: string): string {
    return new Date(value).toISOString().slice(0, 10);
}

// ── Household timezone (R-021) ────────────────────────────────────────────
// The household's IANA zone, from `/api/health` `locale_policy.timezone`.
// `useMoney` (the locale authority, which already reads `locale_policy`) pushes
// it in here once the probe lands; this module stays Vue-free so the pure date
// helpers keep running in a node test environment (`useDateFormat` subscribes
// via `onHouseholdTimezoneChange` to make templates re-render). `null` = not
// known (or an older backend, or not configured) ⇒ fall back to the device
// clock, exactly as before.
let householdTz: string | null = null;
const tzListeners = new Set<() => void>();

// `AppSetting.timezone` is NOT NULL with a server default of 'UTC', and
// `/health` always sends a zone — so the server can't tell "the household chose
// UTC" from "nobody ever set it" (installs set up before the wizard's timezone
// step, or "Skip everything"). Adopting the default would render every instant
// in UTC wall-clock and shift "Today" before ~10 am in Australia. So UTC is read
// as "not configured" ⇒ device clock. A household that genuinely lives in UTC
// loses nothing: its devices' clocks are UTC too.
const UNCONFIGURED_ZONES = new Set(['UTC', 'ETC/UTC']);

/** Set (or clear, with `null`/empty/'UTC') the household timezone. An
 *  unrecognised zone name is ignored rather than thrown on: a bad setting must
 *  degrade to the device clock, not break every date render. */
export function setHouseholdTimezone(tz: string | null | undefined): void {
    const name = (tz ?? '').trim();
    let next: string | null = null;
    if (name && !UNCONFIGURED_ZONES.has(name.toUpperCase())) {
        try {
            new Intl.DateTimeFormat('en-CA', { timeZone: name });
            next = name;
        } catch {
            next = null;
        }
    }
    if (next === householdTz) return;
    householdTz = next;
    tzListeners.forEach((fn) => fn());
}

/** Subscribe to household-timezone changes (returns an unsubscribe). Lets a
 *  reactive layer re-render without this module importing Vue. */
export function onHouseholdTimezoneChange(fn: () => void): () => void {
    tzListeners.add(fn);
    return () => tzListeners.delete(fn);
}

/** The household IANA timezone, or `null` when it isn't known. */
export function householdTimezone(): string | null {
    return householdTz;
}

const zoneDayFormatters = new Map<string, Intl.DateTimeFormat>();

/** YYYY-MM-DD of `instant` on the household's calendar (device-local when the
 *  household zone is unknown). 'en-CA' is used purely because its short date IS
 *  YYYY-MM-DD; it is a data shape here, never a display locale. */
function calendarDayIso(instant: Date): string {
    const tz = householdTz;
    if (tz) {
        let fmt = zoneDayFormatters.get(tz);
        if (!fmt) {
            fmt = new Intl.DateTimeFormat('en-CA', {
                timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit',
            });
            zoneDayFormatters.set(tz, fmt);
        }
        const parts = fmt.formatToParts(instant);
        const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
        return `${get('year')}-${get('month')}-${get('day')}`;
    }
    const month = String(instant.getMonth() + 1).padStart(2, '0');
    const day = String(instant.getDate()).padStart(2, '0');
    return `${instant.getFullYear()}-${month}-${day}`;
}

/** Today as YYYY-MM-DD — on the **household's** calendar when its timezone is
 *  known (`setHouseholdTimezone`), else from the browser's local parts.
 *
 *  R-021 carve-out — display-only, pre-server-response fallback. The
 *  household "today" is owned by the server (`AppSetting.timezone` →
 *  `household_today()` → `mealPlanStore.todayIso`); state and decisions
 *  must use that. This helper exists so the calendar can paint a "today"
 *  cell on the very first frame before the store has hydrated — once the
 *  server response lands, the binding flips and any one-day discrepancy
 *  resolves automatically. Reading the household zone here means a device
 *  whose clock sits on a different calendar day from the household (a
 *  traveller, a remote admin) no longer labels the household's today
 *  "Yesterday". Never use this to gate persisted state, build a server
 *  payload, or decide which day a value belongs to.
 *
 *  `now` is injectable for tests only. */
export function localTodayIso(now: Date = new Date()): string {
    return calendarDayIso(now);
}

/** A YYYY-MM-DD date string, matched exactly (no time part). */
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

/** True when `value` is a bare YYYY-MM-DD calendar date with no time part. */
export function isDateOnly(value: string): boolean {
    return DATE_ONLY.test(value);
}

/** Parse a YYYY-MM-DD string into a Date at **local** midnight of that
 *  calendar day.
 *
 *  Use this instead of `new Date(iso)` for every date-only value. Per spec,
 *  `new Date('2026-09-03')` parses the *date-only* form as **UTC** midnight, so
 *  the resulting instant lands on the previous local day for any negative UTC
 *  offset — and anything that then reads local parts (`getDate()`,
 *  `Intl.DateTimeFormat`, which defaults to the local zone) reports the wrong
 *  day. Measured in America/New_York: `new Date('2026-09-03')` renders as
 *  **02/09/2026**.
 *
 *  East of Greenwich the two forms agree, which is why this survived so long —
 *  Australia is the shipping default and every developer runs there.
 *
 *  Returns `null` for anything that isn't a bare YYYY-MM-DD, so callers can
 *  fall through to normal Date parsing for real datetimes (which carry their own
 *  offset and must NOT be shifted). */
export function parseLocalIso(value: string): Date | null {
    if (!DATE_ONLY.test(value)) return null;
    const [y, m, d] = value.split('-').map(Number);
    // The regex above guarantees three numeric parts, so these are defined;
    // `Date`'s constructor accepts them without assertion.
    const parsed = new Date(y!, m! - 1, d);
    return Number.isFinite(parsed.getTime()) ? parsed : null;
}

/** Whole-day delta from *today* to a YYYY-MM-DD date. 0 = today, 1 = tomorrow,
 *  -1 = yesterday. "Today" is the household's calendar day when its timezone is
 *  known, else the device's (see `localTodayIso`). Both sides are reduced to
 *  calendar dates and compared with UTC arithmetic, so the result is a
 *  calendar-day count — never an elapsed-hours division, and immune to DST. */
export function daysFromToday(value: string, now: Date = new Date()): number | null {
    if (!parseLocalIso(value)) return null;
    return dayNumber(value) - dayNumber(calendarDayIso(now));
}

/** Days since the epoch for a YYYY-MM-DD string (UTC math — exact). */
function dayNumber(iso: string): number {
    const [y, m, d] = iso.split('-').map(Number);
    return Math.round(Date.UTC(y!, m! - 1, d) / 86_400_000);
}

/** Shift a YYYY-MM-DD date by N days (may be negative). */
export function shiftDays(iso: string, days: number): string {
    const [y, m, d] = iso.split('-').map(Number);
    return new Date(Date.UTC(y!, m! - 1, d! + days)).toISOString().slice(0, 10);
}

/** The Monday (ISO week start) of the week containing the given date. */
export function mondayOf(value: string): string {
    const [y, m, d] = isoDate(value).split('-').map(Number);
    const dt = new Date(Date.UTC(y!, m! - 1, d));
    const dow = dt.getUTCDay(); // 0=Sun … 6=Sat
    return shiftDays(dt.toISOString().slice(0, 10), dow === 0 ? -6 : 1 - dow);
}
