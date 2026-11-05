// FU-746: the Region page's "Match this device" nudge reads the IANA zone first
// (an Australian machine can report en-GB) and the BCP-47 region second.
import { describe, expect, it } from 'vitest';
import { isAustralasian, localRatingScheme } from 'src/helpers/localRatingScheme';

describe('isAustralasian', () => {
    it.each([
        ['en-GB', 'Australia/Sydney', true],
        ['en-AU', 'UTC', true],
        ['mi-NZ', 'UTC', true],
        ['en-GB', 'Pacific/Auckland', true],
        ['en-GB', 'Europe/London', false],
        ['en-US', 'Pacific/Fiji', false],
        ['', '', false],
    ])('%s in %s -> %s', (language, zone, expected) => {
        expect(isAustralasian(language, zone)).toBe(expected);
    });
});

describe('localRatingScheme', () => {
    it('offers Health Stars in Australasia, Nutri-Score in its adopters, nothing elsewhere', () => {
        expect(localRatingScheme('en-GB', 'Australia/Perth')).toBe('health_star');
        expect(localRatingScheme('fr-FR', 'UTC')).toBe('nutri_score');
        expect(localRatingScheme('en-GB', 'Europe/Berlin')).toBe('nutri_score');
        expect(localRatingScheme('pl-PL', 'Europe/Warsaw')).toBeNull();
        expect(localRatingScheme('en-US', 'America/New_York')).toBeNull();
    });
});
