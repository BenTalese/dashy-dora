// @vitest-environment jsdom
/**
 * The install picks *one* front-of-pack rating scheme (owner call 2026-08-27),
 * and this composable is the only place the SPA knows which. Two things here
 * are worth pinning:
 *
 *  1. **The Nutri-Score scale inverts.** More stars is better; a *later*
 *     letter is worse. `rankOf` normalises both onto one higher-is-better
 *     number so the cookbook's sort can stay scheme-agnostic — and an
 *     inversion bug would silently sort the worst dinners to the top, which
 *     looks plausible enough on screen to survive a manual pass.
 *  2. **The filter judges the figure that was displayed** (owner decision
 *     2026-08-28). Thin coverage dims the chip; it no longer exempts the
 *     recipe from the threshold. Only a recipe with *no* rating passes
 *     unconditionally. The original rule — exempt anything under
 *     `RELIABLE_COVERAGE_RATIO` — made the control filter nothing at all on a
 *     pantry whose foods mostly aren't linked yet, which is every new install.
 *
 * The arithmetic of either scheme is emphatically *not* tested here — it lives
 * server-side and is pinned against the published tables in
 * `tests/test_nutri_score.py` / `tests/test_health_star_rating.py`.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type * as ModuleUnderTest from 'src/composables/useNutritionRating';
import { ref, type Ref } from 'vue';

let scheme: Ref<string>;
vi.mock('src/composables/useFeatureFlags', () => ({
    useFeatureFlags: () => ({ nutritionRatingScheme: scheme }),
}));

let complex: Ref<boolean>;
vi.mock('src/composables/useNutritionMode', () => ({
    useNutritionMode: () => ({ isComplex: complex }),
}));

type Mod = typeof ModuleUnderTest;

async function load(): Promise<Mod> {
    vi.resetModules();
    return await import('src/composables/useNutritionRating');
}

/** Only the fields the composable reads. */
function recipeWith(nutrition: Record<string, unknown> | null): never {
    return { nutrition } as never;
}

function withStars(stars: number, isReliable = true) {
    return recipeWith({
        is_reliable: isReliable,
        health_star_rating: { stars },
        nutri_score: null,
    });
}

/** The common case on a young install: nothing linked, so nothing to score. */
function withNoRating() {
    return recipeWith({
        is_reliable: false,
        health_star_rating: null,
        nutri_score: null,
    });
}

function withGrade(grade: string, isReliable = true) {
    return recipeWith({
        is_reliable: isReliable,
        health_star_rating: null,
        nutri_score: { grade },
    });
}

describe('useNutritionRating', () => {
    beforeEach(() => {
        scheme = ref('health_star');
        complex = ref(true);
    });

    describe('availability', () => {
        it('is off when the install picked no scheme', async () => {
            scheme.value = 'none';
            const { useNutritionRating } = await load();
            expect(useNutritionRating().ratingAvailable.value).toBe(false);
        });

        it('is off in simple nutrition mode, even with a scheme picked', async () => {
            complex.value = false;
            const { useNutritionRating } = await load();
            expect(useNutritionRating().ratingAvailable.value).toBe(false);
        });

        it('is on with a scheme and complex nutrition', async () => {
            const { useNutritionRating } = await load();
            expect(useNutritionRating().ratingAvailable.value).toBe(true);
        });

        it('treats an unrecognised scheme string as none', async () => {
            scheme.value = 'sparkle_rating';
            const { useNutritionRating } = await load();
            // The flag computed narrows unknown values; the composable must not
            // light up a rating surface it has no badge for.
            expect(useNutritionRating().ratingAvailable.value).toBe(false);
        });
    });

    describe('rankOf', () => {
        it('reads health stars directly — more is better', async () => {
            const { useNutritionRating } = await load();
            const { rankOf } = useNutritionRating();
            expect(rankOf(withStars(4.5))).toBeGreaterThan(rankOf(withStars(2)) as number);
        });

        it('inverts Nutri-Score letters so that A outranks E', async () => {
            scheme.value = 'nutri_score';
            const { useNutritionRating } = await load();
            const { rankOf } = useNutritionRating();

            const ranks = ['A', 'B', 'C', 'D', 'E'].map(g => rankOf(withGrade(g)) as number);
            // Strictly descending: A is the best grade and must rank highest.
            expect(ranks).toEqual([...ranks].sort((a, b) => b - a));
            expect(ranks[0]).toBeGreaterThan(ranks[4] as number);
        });

        it('is null when the recipe carries no rating', async () => {
            const { useNutritionRating } = await load();
            expect(useNutritionRating().rankOf(recipeWith(null))).toBeNull();
        });

        it('is null for a grade outside A-E rather than guessing a rank', async () => {
            scheme.value = 'nutri_score';
            const { useNutritionRating } = await load();
            expect(useNutritionRating().rankOf(withGrade('Z'))).toBeNull();
        });

        it('ignores the other scheme\'s payload', async () => {
            // Belt and braces: the server only sends the chosen scheme, but a
            // stale cached page could carry the other one.
            scheme.value = 'nutri_score';
            const { useNutritionRating } = await load();
            expect(useNutritionRating().rankOf(withStars(5))).toBeNull();
        });
    });

    describe('meetsThreshold', () => {
        it('keeps everything when no threshold is set', async () => {
            const { useNutritionRating } = await load();
            expect(useNutritionRating().meetsThreshold(withStars(1), null)).toBe(true);
        });

        it('excludes a judgeable recipe below the threshold', async () => {
            const { useNutritionRating } = await load();
            expect(useNutritionRating().meetsThreshold(withStars(2), 4)).toBe(false);
        });

        it('keeps a judgeable recipe at the threshold exactly', async () => {
            const { useNutritionRating } = await load();
            expect(useNutritionRating().meetsThreshold(withStars(4), 4)).toBe(true);
        });

        it('excludes a thinly-covered recipe on the figure it displayed', async () => {
            const { useNutritionRating } = await load();
            // Owner decision 2026-08-28, reversing the original rule. Coverage
            // is too thin to stand behind these 2 stars, but 2 stars is what
            // the card showed — so "4 or better" has to hide it. The old
            // exemption meant that on a pantry with few linked foods the
            // filter excluded nothing at all and read as broken.
            expect(useNutritionRating().meetsThreshold(withStars(2, false), 4)).toBe(false);
        });

        it('keeps a recipe with no rating at all', async () => {
            const { useNutritionRating } = await load();
            // Nothing to judge. Hiding untouched recipes the moment a
            // threshold is set would empty the cookbook rather than narrow it.
            expect(useNutritionRating().meetsThreshold(withNoRating(), 4)).toBe(true);
        });

        it('applies the same rule to Nutri-Score grades', async () => {
            scheme.value = 'nutri_score';
            const { useNutritionRating } = await load();
            const { meetsThreshold, rankOf } = useNutritionRating();
            const bBar = rankOf(withGrade('B')) as number;

            expect(meetsThreshold(withGrade('A'), bBar)).toBe(true);
            expect(meetsThreshold(withGrade('B'), bBar)).toBe(true);
            expect(meetsThreshold(withGrade('D'), bBar)).toBe(false);
        });
    });

    describe('presentation', () => {
        it('names the scheme rather than calling it "the health rating"', async () => {
            const { useNutritionRating } = await load();
            expect(useNutritionRating().ratingLabel.value).toBe('Health Star Rating');

            scheme.value = 'nutri_score';
            const second = await load();
            expect(second.useNutritionRating().ratingLabel.value).toBe('Nutri-Score');
        });

        it('offers star thresholds for HSR and letter thresholds for Nutri-Score', async () => {
            const { useNutritionRating } = await load();
            expect(useNutritionRating().thresholdOptions.value[0]?.label).toContain('stars');

            scheme.value = 'nutri_score';
            const second = await load();
            const options = second.useNutritionRating().thresholdOptions.value;
            expect(options).toHaveLength(5);
            expect(options[0]?.label).toBe('A or better');
        });

        it('offers no thresholds when there is no scheme', async () => {
            scheme.value = 'none';
            const { useNutritionRating } = await load();
            expect(useNutritionRating().thresholdOptions.value).toEqual([]);
        });
    });
});
