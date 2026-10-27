/**
 * Pickable currency + language options for Settings → Admin → Region & locale.
 *
 * These are a **convenience shortlist, not a whitelist**: the page's selects
 * accept free text, and the server validates the real thing (ISO 4217 shape for
 * currency, BCP-47 via `Intl.Locale` for the tag). So an install in a country
 * that isn't listed here is never blocked — it just has to type the code. The
 * point of the list is that nobody should have to know what "ISO 4217" means to
 * choose dollars.
 *
 * Ordering is deliberate: the markets Dora is actually used in first, then the
 * rest alphabetically by label.
 */
import type { MeasurementSystem } from 'src/generated/units_table';

export interface RegionChoice {
    /** What gets saved — the bare code / tag. */
    value: string;
    /** What's shown; includes the code so a search on "AUD" still hits. */
    label: string;
}

export const CURRENCY_CHOICES: readonly RegionChoice[] = [
    { value: 'AUD', label: 'AUD (Australian dollar)' },
    { value: 'NZD', label: 'NZD (New Zealand dollar)' },
    { value: 'USD', label: 'USD (US dollar)' },
    { value: 'GBP', label: 'GBP (Pound sterling)' },
    { value: 'EUR', label: 'EUR (Euro)' },
    { value: 'CAD', label: 'CAD (Canadian dollar)' },
    { value: 'BRL', label: 'BRL (Brazilian real)' },
    { value: 'CHF', label: 'CHF (Swiss franc)' },
    { value: 'CNY', label: 'CNY (Chinese yuan)' },
    { value: 'DKK', label: 'DKK (Danish krone)' },
    { value: 'HKD', label: 'HKD (Hong Kong dollar)' },
    { value: 'INR', label: 'INR (Indian rupee)' },
    { value: 'JPY', label: 'JPY (Japanese yen)' },
    { value: 'MXN', label: 'MXN (Mexican peso)' },
    { value: 'NOK', label: 'NOK (Norwegian krone)' },
    { value: 'PLN', label: 'PLN (Polish złoty)' },
    { value: 'SEK', label: 'SEK (Swedish krona)' },
    { value: 'SGD', label: 'SGD (Singapore dollar)' },
    { value: 'ZAR', label: 'ZAR (South African rand)' },
];

export const LOCALE_CHOICES: readonly RegionChoice[] = [
    { value: 'en-AU', label: 'English (Australia), en-AU' },
    { value: 'en-NZ', label: 'English (New Zealand), en-NZ' },
    { value: 'en-GB', label: 'English (United Kingdom), en-GB' },
    { value: 'en-US', label: 'English (United States), en-US' },
    { value: 'en-CA', label: 'English (Canada), en-CA' },
    { value: 'en-IE', label: 'English (Ireland), en-IE' },
    { value: 'en-IN', label: 'English (India), en-IN' },
    { value: 'en-SG', label: 'English (Singapore), en-SG' },
    { value: 'en-ZA', label: 'English (South Africa), en-ZA' },
    { value: 'da-DK', label: 'Danish (Denmark), da-DK' },
    { value: 'nl-NL', label: 'Dutch (Netherlands), nl-NL' },
    { value: 'fr-CA', label: 'French (Canada), fr-CA' },
    { value: 'fr-FR', label: 'French (France), fr-FR' },
    { value: 'de-DE', label: 'German (Germany), de-DE' },
    { value: 'it-IT', label: 'Italian (Italy), it-IT' },
    { value: 'ja-JP', label: 'Japanese (Japan), ja-JP' },
    { value: 'nb-NO', label: 'Norwegian (Norway), nb-NO' },
    { value: 'pl-PL', label: 'Polish (Poland), pl-PL' },
    { value: 'pt-BR', label: 'Portuguese (Brazil), pt-BR' },
    { value: 'pt-PT', label: 'Portuguese (Portugal), pt-PT' },
    { value: 'es-ES', label: 'Spanish (Spain), es-ES' },
    { value: 'es-MX', label: 'Spanish (Mexico), es-MX' },
    { value: 'sv-SE', label: 'Swedish (Sweden), sv-SE' },
    { value: 'zh-CN', label: 'Chinese (Simplified), zh-CN' },
];

/** The three systems, described by what you'll actually see rather than by
 *  their names: "imperial" and "US customary" are the same word to most
 *  people, and the difference that matters here is the pint and the cup.
 *  `short` is for a segmented control with no room for the description. */
export const MEASUREMENT_SYSTEM_CHOICES: ReadonlyArray<{
    value: MeasurementSystem;
    label: string;
    short: string;
}> = [
    { value: 'metric', label: 'Metric (ml, L, g, kg, 250 ml cup)', short: 'Metric' },
    { value: 'imperial', label: 'Imperial (UK): metric plus oz, lb, fl oz, pint', short: 'Imperial (UK)' },
    { value: 'us', label: 'US customary (fl oz, qt, oz, lb, 240 ml cup)', short: 'US' },
];

type IntlWithSupported = typeof Intl & { supportedValuesOf?: (key: string) => string[] };
const supportedValuesOf = (Intl as IntlWithSupported).supportedValuesOf;
/** Every IANA timezone this browser knows, or just UTC on one that can't list them. */
/** The device's IANA zone, 'UTC' when the runtime can't say (finalisation
 *  14-R9 — was copied in the wizard and the Region settings page). */
export function deviceTimezone(): string {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    } catch {
        return 'UTC';
    }
}

/** The zone picker's filter: a case-insensitive substring over every choice. */
export function filterTimezones(needle: string): string[] {
    const q = needle.trim().toLowerCase();
    return q ? TIMEZONE_CHOICES.filter((t) => t.toLowerCase().includes(q)) : [...TIMEZONE_CHOICES];
}

export const TIMEZONE_CHOICES: readonly string[] = supportedValuesOf
    ? supportedValuesOf('timeZone')
    : ['UTC'];
