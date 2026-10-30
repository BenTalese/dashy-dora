import { computed, ref } from 'vue';
import HealthApiService, { invalidateHealthInfo } from 'src/services/api/healthApiService';
import { setHouseholdTimezone } from 'src/helpers/weekDates';

// install-wide currency + locale
// for every money render in the app. R-003: one source of truth, one
// formatter. Templates never hardcode `$` or `.toFixed(2)` for money —
// they call `formatMoney(x)` (or the plain-getter `currentMoneyPolicy()`
// for non-Vue callers) so an admin flipping currency in Settings takes
// effect app-wide.
//
// Mirrors `useImagePolicy`: module-level state so the health probe runs
// once per session, a single inflight promise, plain-getter for non-Vue
// callers. This module (with `useDateFormat`) IS the locale authority —
// direct `Intl` wrappers; vue-i18n was removed in finalisation 20-R2.

export interface MoneyPolicy {
    /** ISO 4217 currency code, e.g. 'AUD', 'USD', 'EUR'. */
    currency: string;
    /** BCP-47 display locale, e.g. 'en-AU'. Drives symbol placement,
     *  decimal + grouping separators. */
    locale: string;
}

// Dora's shipping AU defaults. Kept in one place so the null-policy
// path (health probe fails or field absent) can't diverge.
const DEFAULTS: MoneyPolicy = { currency: 'AUD', locale: 'en-AU' };

const policy = ref<MoneyPolicy>({ ...DEFAULTS });
const loaded = ref(false);
let inflight: Promise<void> | null = null;

// Cache the formatter — Intl.NumberFormat construction is not free
// and every money render hits it. Rebuilt when policy changes.
let cachedFormatter: Intl.NumberFormat | null = null;
let cachedFor: string = '';

function buildFormatter(p: MoneyPolicy): Intl.NumberFormat {
    // If the locale is unrecognised, Intl falls back to the default
    // locale silently — surfaces a browser-locale render rather than
    // throwing, which is the failure mode we want.
    return new Intl.NumberFormat(p.locale, {
        style: 'currency',
        currency: p.currency,
        // Pin to 2 fractional digits — Dora's price surfaces already
        // assumed 2 (`.toFixed(2)` scattered everywhere). Currencies
        // with 0 fractional digits (JPY, KRW) can override later if
        // demand appears; for now, uniform 2 matches the AU baseline.
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function getFormatter(): Intl.NumberFormat {
    const key = `${policy.value.locale}|${policy.value.currency}`;
    if (cachedFormatter && cachedFor === key) return cachedFormatter;
    cachedFormatter = buildFormatter(policy.value);
    cachedFor = key;
    return cachedFormatter;
}

function load(): Promise<void> {
    if (!inflight) {
        inflight = new HealthApiService()
            .getInfoAsync()
            .then((info) => {
                const server = info.locale_policy;
                if (!server) return;
                const currency = (server.currency || '').trim().toUpperCase() || DEFAULTS.currency;
                const locale = (server.locale || '').trim() || DEFAULTS.locale;
                policy.value = { currency, locale };
                // R-021 — the household zone rides on the same policy. Handed
                // to the date helpers (which own "what day is it"); absent on
                // older backends, in which case they keep the device clock.
                // The server-default 'UTC' also means "not configured" and
                // keeps the device clock — see `setHouseholdTimezone`.
                setHouseholdTimezone(server.timezone);
            })
            .catch(() => {
                // Health probe failure ⇒ keep the defaults; money still
                // renders (in AUD/en-AU), no user-visible break.
            })
            .finally(() => {
                loaded.value = true;
            });
    }
    return inflight;
}

/** Format an amount as a money string using the install's currency +
 *  locale. `null`/`undefined`/`NaN` render as a dash so templates don't
 *  need to guard the common "no price yet" case. */
export function formatMoney(amount: number | null | undefined): string {
    if (amount === null || amount === undefined || !Number.isFinite(amount)) {
        return '–';
    }
    return getFormatter().format(amount);
}

/** Return just the currency symbol for the install (e.g. '$', '€', '£').
 *  Used by `q-input` `prefix=` — Quasar's input takes a plain string, not
 *  a formatted value. Derived from the same formatter so a currency flip
 *  changes both display *and* input decoration atomically. */
export function currencySymbol(): string {
    // `formatToParts` gives us the symbol as-emitted, so we get whatever
    // the locale actually uses for this currency ('US$' in en-AU for USD,
    // etc.) rather than a hardcoded map.
    const parts = getFormatter().formatToParts(0);
    return parts.find((p) => p.type === 'currency')?.value ?? '';
}

// ── Plain numbers (D-006) ──────────────────────────────────────────────────
// Counts, ratings, percentages and file sizes go through the same household
// locale as money, so de-DE reads "1.208" / "4,5" / "12,5 %" everywhere instead
// of the browser's (or JavaScript's) English shape. Each formatter owns its own
// rounding (R-079): call sites pass the raw number, never a pre-`toFixed` one.

const numberFormatters = new Map<string, Intl.NumberFormat>();

function numberFormatter(opts: Intl.NumberFormatOptions): Intl.NumberFormat {
    const locale = currentLocale();
    const key = `${locale}|${JSON.stringify(opts)}`;
    let fmt = numberFormatters.get(key);
    if (!fmt) {
        fmt = new Intl.NumberFormat(locale, opts);
        numberFormatters.set(key, fmt);
    }
    return fmt;
}

export interface NumberFormatOptions {
    /** Most fractional digits to show (default 2). */
    digits?: number;
    /** Fewest fractional digits to show (default 0) — `1` keeps "4.0" for a
     *  star rating where the trailing zero is part of the reading. */
    minDigits?: number;
}

/** A plain number in the household locale, grouped ("1,208" / "1.208").
 *  Non-finite input renders as a dash, like `formatMoney`. */
export function formatNumber(
    value: number | null | undefined,
    { digits = 2, minDigits = 0 }: NumberFormatOptions = {},
): string {
    if (value === null || value === undefined || !Number.isFinite(value)) return '–';
    return numberFormatter({
        minimumFractionDigits: Math.min(minDigits, digits),
        maximumFractionDigits: digits,
    }).format(value);
}

export interface PercentFormatOptions {
    /** Prefix a `+` on positive values ("+200.4%"); zero stays unsigned. */
    signed?: boolean;
    /** Most fractional digits (default 1). */
    digits?: number;
}

/** A percentage in the household locale. Takes **percentage points** — the
 *  shape every API `*_pct` field already has (`139.5` → "139.5%" / "139,5 %"),
 *  not a 0–1 fraction. */
export function formatPercent(
    value: number | null | undefined,
    { signed = false, digits = 1 }: PercentFormatOptions = {},
): string {
    if (value === null || value === undefined || !Number.isFinite(value)) return '–';
    return numberFormatter({
        style: 'percent',
        minimumFractionDigits: 0,
        maximumFractionDigits: digits,
        signDisplay: signed ? 'exceptZero' : 'auto',
    }).format(value / 100);
}

/** A byte count as B / KB / MB / GB (binary multiples, one decimal; GB two),
 *  in the household locale. One copy — three pages each carried their own. */
export function formatFileSize(bytes: number | null | undefined): string {
    if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) return '–';
    if (bytes < 1024) return `${formatNumber(bytes, { digits: 0 })} B`;
    const kb = bytes / 1024;
    if (kb < 1024) return `${formatNumber(kb, { digits: 1, minDigits: 1 })} KB`;
    const mb = kb / 1024;
    if (mb < 1024) return `${formatNumber(mb, { digits: 1, minDigits: 1 })} MB`;
    return `${formatNumber(mb / 1024, { digits: 2, minDigits: 2 })} GB`;
}

/** A per-unit price, "$1.89 / qt" — the app's one spacing convention for a
 *  money-over-unit figure (the stock item's price lines, the cost dialog,
 *  reports). Templates that style the two halves differently keep the same
 *  " / " separator by hand. */
export function formatUnitPrice(amount: number | null | undefined, unit: string): string {
    return `${formatMoney(amount)} / ${unit}`;
}

/** Read-only access for non-Vue callers. */
export function currentMoneyPolicy(): MoneyPolicy {
    return policy.value;
}

/** The install's BCP-47 display locale (e.g. 'en-AU'). Shared source of
 *  truth for both money and DATE formatting — `useDateFormat` reads this so
 *  a household never has two disagreeing locales (R-003 / D-006). Reads the
 *  reactive ref, so a template calling it re-renders when the policy loads. */
export function currentLocale(): string {
    return policy.value.locale;
}

let cachedCollator: Intl.Collator | null = null;
let collatorFor = '';

/** Name-sorting collator in the install's locale, cached per locale. Five
 *  stores and the stock filters each built `new Intl.Collator('en', …)` —
 *  harmless for the shipped `en-*` locales, but a second opinion about the
 *  household's locale (R-003; finalisation 20-R7). Read it at sort time, not
 *  at module load, so a late-loading policy is honoured. */
export function nameCollator(): Intl.Collator {
    const locale = currentLocale();
    if (!cachedCollator || collatorFor !== locale) {
        cachedCollator = new Intl.Collator(locale, { sensitivity: 'base' });
        collatorFor = locale;
    }
    return cachedCollator;
}

/** Kick the shared locale/currency probe (idempotent). `useDateFormat` calls
 *  this so date rendering doesn't need its own health round-trip. */
export function ensureLocalePolicy(): Promise<void> {
    return load();
}

/** Force-reload from the server. The admin UI calls this after saving
 *  a new currency/locale so subsequent renders pick it up without a
 *  full page reload. */
export function refreshMoneyPolicy(): Promise<void> {
    loaded.value = false;
    inflight = null;
    invalidateHealthInfo();
    cachedFormatter = null;
    cachedFor = '';
    return load();
}

export function useMoney() {
    void load();
    return {
        moneyPolicy: policy,
        moneyPolicyLoaded: loaded,
        formatMoney,
        currencySymbol: computed(() => currencySymbol()),
        refreshMoneyPolicy,
    };
}
