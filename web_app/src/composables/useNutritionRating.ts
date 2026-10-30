// The recipe front-of-pack rating — whether this install shows one, which one,
// and how to read a recipe's (owner ask 2026-08-27).
//
// Was `useHealthStarRating`. It became scheme-aware the same week, because a
// single-scheme composable forced every caller to say "health stars" in its
// UI copy, which is how the whole feature ended up looking like it was for
// Australia only.
//
// Two conditions, and both are the server's answer rather than ours:
//
//   * `nutrition_rating_scheme` — the install-wide choice: 'none' (the default
//     everywhere), 'health_star' (AU/NZ) or 'nutri_score' (Europe). Settings →
//     Region's "Match this device" offers the locally recognised one; the
//     picker in Settings → Nutrition takes any of them anywhere.
//   * complex nutrition mode — a rating is computed from the foods the
//     ingredients link to, so simple mode (a typed kcal and nothing else) has
//     nothing to score. A scheme selected in simple mode is a no-op, not an
//     error.
//
// Nothing here re-derives a rating. Both sets of published tables live
// server-side (`dora_api/domain/health_star_rating.py`, `.../nutri_score.py`)
// and transcribing either a second time in TypeScript is exactly the drift
// R-003 exists to prevent. What this file *does* own is presentation: how to
// rank two recipes against each other and what the threshold control offers,
// which are view concerns and belong here rather than in the API.

import { computed } from 'vue';

import { useFeatureFlags } from 'src/composables/useFeatureFlags';
import { useNutritionMode } from 'src/composables/useNutritionMode';
import { formatNumber } from 'src/composables/useMoney';
import type {
    Recipe,
    RecipeHealthStarRating,
    RecipeNutriScore,
} from 'src/models/recipe';

/** Best to worst. Index doubles as the rank, so it must stay in this order. */
export const NUTRI_SCORE_GRADES = ['A', 'B', 'C', 'D', 'E'] as const;

export type RatingScheme = 'none' | 'health_star' | 'nutri_score';

export type RecipeRating = {
    /** The Health Star Rating, when that is the install's scheme. */
    stars: RecipeHealthStarRating | null;
    /** The Nutri-Score, when that is the install's scheme. */
    nutriScore: RecipeNutriScore | null;
    /** Whether the rating may be used to *judge* the recipe — rank it, or
     *  exclude it from a threshold filter. */
    judgeable: boolean;
};

export function useNutritionRating() {
    const { nutritionRatingScheme } = useFeatureFlags();
    const { isComplex } = useNutritionMode();

    /** Narrowed here as well as in `useFeatureFlags`, deliberately. This
     *  composable decides whether whole surfaces render, and "anything that
     *  isn't the string 'none'" is the wrong test for that — a scheme this
     *  build has no badge for would light up the chip, the filter and the sort
     *  axis and then render nothing into them. Recognised-or-none is the
     *  honest question, and it costs one array lookup. */
    const RENDERABLE: readonly RatingScheme[] = ['health_star', 'nutri_score'];

    const scheme = computed<RatingScheme>(() => {
        const raw = nutritionRatingScheme.value as RatingScheme;
        return RENDERABLE.includes(raw) ? raw : 'none';
    });

    /** Whether the rating axis exists at all on this install. Every surface —
     *  the recipe panel, the cookbook chip, the filter and the sort axis —
     *  gates on this one computed rather than each re-assembling the pair. */
    const ratingAvailable = computed(
        () => scheme.value !== 'none' && isComplex.value);

    /** What to call it in UI copy. The schemes are national programmes with
     *  actual names; calling either one "the health rating" would be both
     *  vaguer and less honest about whose rating it is. */
    const ratingLabel = computed(() => (
        scheme.value === 'nutri_score' ? 'Nutri-Score' : 'Health Star Rating'
    ));

    /** A recipe's rating and whether it may be used to judge the recipe.
     *
     *  `judgeable` is the rollup's own `is_reliable` — the same coverage gate
     *  the kcal axis uses (R-041). Since 2026-08-28 it drives **presentation
     *  only**: a thin rating is drawn dimmed and says so in its tooltip. It no
     *  longer exempts the recipe from `meetsThreshold` or from ranking — see
     *  the note there for why that exemption made the filter look dead.
     *
     *  Note this gate is about *ingredient coverage*, not about which
     *  nutrients were known. The second gap — sugars is known for only ~77% of
     *  USDA foods, and a missing penalty nutrient makes a recipe rate better —
     *  is reported per nutrient in the panel instead of collapsing into this
     *  boolean, which was the owner's call. */
    function ratingOf(recipe: Recipe): RecipeRating {
        const nutrition = recipe.nutrition ?? null;
        return {
            stars: nutrition?.health_star_rating ?? null,
            nutriScore: nutrition?.nutri_score ?? null,
            judgeable: nutrition?.is_reliable === true,
        };
    }

    /** A recipe's quality on one comparable scale, **higher is better**, or
     *  null when it has no rating.
     *
     *  Only ever compared against other recipes on the *same* install, so the
     *  two schemes never have to be commensurable with each other — which is
     *  fortunate, because they are not. Nutri-Score's letters invert (A is the
     *  best grade and index 0), hence the subtraction. */
    function rankOf(recipe: Recipe): number | null {
        const { stars, nutriScore } = ratingOf(recipe);
        if (scheme.value === 'health_star') return stars?.stars ?? null;
        if (scheme.value === 'nutri_score' && nutriScore) {
            const index = NUTRI_SCORE_GRADES.indexOf(
                nutriScore.grade as typeof NUTRI_SCORE_GRADES[number]);
            return index < 0 ? null : NUTRI_SCORE_GRADES.length - index;
        }
        return null;
    }

    /** Options for the cookbook's "at least this good" filter, best first.
     *  `value` is on the same scale as `rankOf`. */
    const thresholdOptions = computed<{ label: string; value: number }[]>(() => {
        if (scheme.value === 'health_star') {
            return [5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5, 1]
                .map(v => ({ label: `${formatNumber(v, { digits: 1, minDigits: 1 })} stars`, value: v }));
        }
        if (scheme.value === 'nutri_score') {
            return NUTRI_SCORE_GRADES.map((grade, index) => ({
                label: `${grade} or better`,
                value: NUTRI_SCORE_GRADES.length - index,
            }));
        }
        return [];
    });

    /** The label the filter control itself carries. */
    const thresholdLabel = computed(() => (
        scheme.value === 'nutri_score' ? 'Nutri-Score at least' : 'Health stars ≥'
    ));

    /** Whether a recipe survives a threshold filter.
     *
     *  **The filter judges the figure it displayed** (owner decision
     *  2026-08-28). A recipe showing 0.5 stars fails "3 stars or better",
     *  thin coverage or not.
     *
     *  This reverses the original rule, which kept any recipe whose coverage
     *  was below `RELIABLE_COVERAGE_RATIO` on the grounds that excluding it
     *  asserted a rating we'd just said we didn't trust. Defensible, and
     *  unusable: on a pantry where most foods aren't linked yet, *every*
     *  recipe is unjudgeable, so the control filtered nothing and read as
     *  broken. Between a filter that is subtle and one that does what its
     *  label says, the label wins — the partial styling and the tooltip are
     *  where the doubt is expressed, not in silently ignoring the user.
     *
     *  A recipe with **no** rating at all still passes: there is no figure to
     *  judge, and hiding untouched recipes the moment a threshold is set
     *  would empty the cookbook rather than narrow it. */
    function meetsThreshold(recipe: Recipe, minimum: number | null): boolean {
        if (minimum === null || !Number.isFinite(minimum)) return true;
        const rank = rankOf(recipe);
        return rank === null || rank >= minimum;
    }

    return {
        scheme,
        ratingAvailable,
        ratingLabel,
        ratingOf,
        rankOf,
        thresholdOptions,
        thresholdLabel,
        meetsThreshold,
    };
}
