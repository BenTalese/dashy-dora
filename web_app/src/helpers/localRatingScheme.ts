// Which front-of-pack rating this device's region uses, for the Region page's
// "Match this device" nudge. Lifted out of AdminSystemRegionSettings so it can
// be pinned by a table test (FU-746). Display-side only: it decides whether to
// *offer* a scheme; the install's choice is the server's setting.

/** The countries currently using Nutri-Score, by BCP-47 region subtag:
 *  France, Belgium, Germany, the Netherlands, Luxembourg, Spain and
 *  Switzerland. Kept as an explicit list rather than "Europe" — most of
 *  Europe has not adopted it, and offering it to an install in Warsaw
 *  would be exactly the presumption this whole design avoids. */
const NUTRI_SCORE_REGIONS = ['FR', 'BE', 'DE', 'NL', 'LU', 'ES', 'CH'];

/** IANA zones for the same set, for the timezone-first read below. */
const NUTRI_SCORE_ZONES = [
    'Europe/Paris', 'Europe/Brussels', 'Europe/Berlin', 'Europe/Busingen',
    'Europe/Amsterdam', 'Europe/Luxembourg', 'Europe/Madrid',
    'Atlantic/Canary', 'Africa/Ceuta', 'Europe/Zurich',
];

/** Which scheme, if any, this device's region recognises. Null means "no
 *  local scheme" — most of the world — and nothing is offered. */
export function localRatingScheme(
    language: string, zone: string,
): 'health_star' | 'nutri_score' | null {
    if (isAustralasian(language, zone)) return 'health_star';
    if (NUTRI_SCORE_ZONES.includes(zone)) return 'nutri_score';
    if (NUTRI_SCORE_REGIONS.includes(regionOf(language))) return 'nutri_score';
    return null;
}

/** The BCP-47 region subtag, uppercased, or '' when it can't be read. */
function regionOf(language: string): string {
    if (!language) return '';
    try {
        return new Intl.Locale(language).region ?? '';
    } catch {
        const parts = language.toUpperCase().split('-');
        return parts.length > 1 ? (parts[parts.length - 1] ?? '') : '';
    }
}

/** Is this device in Australia or New Zealand?
 *
 *  **Timezone first, language second** — found the hard way while testing
 *  this: the machine reported `navigator.language === 'en-GB'` with
 *  `timeZone === 'Australia/Sydney'`. Plenty of Australians run their OS
 *  in en-GB, so a language-only test would have silently never fired for
 *  exactly the people the prompt exists for. The timezone is a statement
 *  about *where the device is*; the language tag is a statement about
 *  which words it prefers, and only sometimes about geography.
 *
 *  Either signal is enough. Over-offering costs one dismissable prompt
 *  behind a button the user pressed on purpose; under-offering means the
 *  feature is never found. */
export function isAustralasian(language: string, zone: string): boolean {
    return isAustralasianZone(zone) || isAustralasianLanguage(language);
}

/** IANA zone ids are `Area/Location`. Australia has its own area; New
 *  Zealand sits under `Pacific/` alongside a great many places that are
 *  not New Zealand, so those are named rather than prefix-matched. */
function isAustralasianZone(zone: string): boolean {
    if (!zone) return false;
    if (zone.startsWith('Australia/')) return true;
    return ['Pacific/Auckland', 'Pacific/Chatham'].includes(zone);
}

/** By the BCP-47 tag's *region* subtag, not by a substring match: `en-AU`
 *  and `mi-NZ` both qualify, and a tag that merely contains those letters
 *  does not. Falls back to a suffix read when `Intl.Locale` can't parse
 *  what the browser handed us. */
function isAustralasianLanguage(language: string): boolean {
    if (!language) return false;
    try {
        const region = new Intl.Locale(language).region;
        if (region) return region === 'AU' || region === 'NZ';
    } catch {
        // fall through to the textual read below
    }
    const upper = language.toUpperCase();
    return upper.endsWith('-AU') || upper.endsWith('-NZ');
}
