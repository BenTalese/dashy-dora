import type { Recipe } from 'src/models/recipe';

/**
 * The recipe rail's filter chips, in one place.
 *
 * **Replaces `recipeTrays.ts`** (deleted 2026-08-30, Unit 2 of
 * BRIEF_MEAL_PLANNER_RAIL_AND_SHELL §4.3). The rail used to be four collapsible
 * accordions built by `buildRecipeTrays`; it is now one flat list plus a row of
 * mutually-exclusive filter chips, which is what F21 asked for — *"it should be
 * filterable and vertical because it's a list, and it can hold hundreds of
 * recipes."*
 *
 * **FU-578 #47 is superseded here, not regressed.** The tray builder went out of
 * its way to give each recipe exactly ONE tray: a favourite appeared under both
 * `Favourites` and `All recipes`, rendering two checkboxes in the wizard, so
 * every recipe was claimed by the highest-priority tray it qualified for. As
 * *filters* that dedupe is actively wrong — `Regulars` should list every
 * frequently-planned recipe, favourites included, because you asked for
 * regulars. Filters solve the double-render inherently: one active filter, one
 * list, so a recipe can never appear twice on screen. These are therefore
 * **independent predicates over the same fields**, with no claiming and no caps.
 *
 * R-003 — every predicate reads a **server-computed** field. `not_made_recently`
 * is the server's own 21-day household window; `plan_count` and `is_favourite`
 * are stored. The client decides nothing about what qualifies.
 *
 * The old builder also sorted its "haven't had in a while" tray by
 * `last_made_on` on the client (a `madeMs()` helper) while the server already
 * shipped the `not_made_recently` flag it selected on — an R-003 leak the brief
 * called out. That client-side recency computation is **gone**: selection uses
 * the server flag and the ordering is by name. Do not reintroduce a client
 * recency sort; if a recency *order* is wanted, the server should ship it.
 */
export type RecipeFilterKey =
    | 'suggests' | 'all' | 'cookable' | 'favourites' | 'not_lately' | 'regulars';

/**
 * The rail's SECOND filter axis (owner, 2026-09-01: "some useful filters feel
 * like they're missing from the left rail — time of day, difficulty").
 *
 * Deliberately not more chips. The chip row is one mutually-exclusive
 * *shortlist* — "which slice of my cookbook am I browsing" — and folding two
 * more independent dimensions into it would break both its radio semantics and
 * B2a's 2-4 option guidance. These narrow whatever the chip produced, the same
 * way the search box does (L99), so they compose with it rather than compete.
 *
 * `null` on either axis means "don't narrow on this". A recipe with no
 * `time_of_day` / `difficulty` recorded is EXCLUDED once that axis is set: the
 * user asked for breakfasts, and "we don't know what this is" is not a
 * breakfast. Both fields are stored server-side against closed vocabularies —
 * `time_of_day` against the household `MealSlot` table, `difficulty` against
 * `ALLOWED_DIFFICULTY_VALUES` — so the client is matching stored strings, not
 * deciding anything (R-003).
 */
export type RecipeAxisFilters = {
    timeOfDay: string | null;
    difficulty: string | null;
};

export const NO_AXIS_FILTERS: RecipeAxisFilters = { timeOfDay: null, difficulty: null };

export type RecipeFilterChip = {
    key: RecipeFilterKey;
    label: string;
    /** How many recipes this chip would show. Drives the disabled state. */
    count: number;
    /**
     * B2a — an empty chip stays in place, disabled and tooltip'd, rather than
     * being filtered out. The old trays hid themselves when empty, so the row
     * reflowed as a cookbook grew and the user lost their spatial memory of
     * where a control was.
     */
    disabled: boolean;
    /** Tooltip text, present only when disabled (explains why it can't be used). */
    disabledReason?: string;
};

/**
 * `suggests` is deliberately in this list but is NOT a predicate — it is a
 * server-ranked ordering with a reason line per row (§4.4), so it changes what
 * order you see and what each row says, not which recipes exist. It rides in
 * the chip row because that is where the user looks, and it is marked out
 * visually so the semantic difference is legible.
 */
const PREDICATES: Record<
    Exclude<RecipeFilterKey, 'suggests'>,
    (r: Recipe) => boolean
> = {
    all: () => true,
    // Owner 2026-09-12 — *"add quick filter for ingredients all available
    // (cookable now)"*. `cookable` is the server's own tri-state (§3.2): only
    // an explicit `true` qualifies, so a recipe with unlinked ingredients —
    // where the app admits it doesn't know — is not offered as cookable.
    cookable: (r) => r.cookable === true,
    favourites: (r) => r.is_favourite,
    not_lately: (r) => r.not_made_recently,
    regulars: (r) => r.plan_count > 0,
};

const LABELS: Record<RecipeFilterKey, string> = {
    suggests: 'Dora suggests',
    all: 'All',
    cookable: 'Cookable now',
    favourites: 'Favourites',
    not_lately: 'Not lately',
    regulars: 'Regulars',
};

const DISABLED_REASONS: Record<Exclude<RecipeFilterKey, 'suggests' | 'all'>, string> = {
    cookable: "Nothing's cookable from stock right now.",
    favourites: 'No favourites yet.',
    not_lately: "You've cooked everything recently.",
    regulars: "Nothing's been planned more than once yet.",
};

/** Case-insensitive name match. Search is deliberately SEPARATE from the chips
 *  (L99: "keep search filter separate to other filters") — it narrows whatever
 *  the active chip produced rather than replacing it. */
function matchesSearch(recipe: Recipe, query: string): boolean {
    return recipe.name.toLowerCase().includes(query);
}

/** Both axes are AND-ed with each other and with everything else. An unset
 *  axis matches everything; a set one requires the stored value to equal it. */
export function matchesAxes(recipe: Recipe, axes: RecipeAxisFilters): boolean {
    if (axes.timeOfDay !== null && recipe.time_of_day !== axes.timeOfDay) return false;
    if (axes.difficulty !== null && recipe.difficulty !== axes.difficulty) return false;
    return true;
}

function byName(a: Recipe, b: Recipe): number {
    return a.name.localeCompare(b.name);
}

/**
 * The recipes one chip shows, after the search box narrows them.
 *
 * `suggests` is handled by the caller (it needs the server's ranked ids), so
 * asking for it here returns the unfiltered set in name order — the caller
 * re-orders. Everything else is a plain predicate.
 */
export function filterRecipes(
    recipes: Recipe[],
    key: RecipeFilterKey,
    searchTerm = '',
    axes: RecipeAxisFilters = NO_AXIS_FILTERS,
): Recipe[] {
    const query = searchTerm.trim().toLowerCase();
    const predicate = key === 'suggests' ? PREDICATES.all : PREDICATES[key];

    const matched = recipes.filter(
        (r) => predicate(r) && matchesAxes(r, axes) && (!query || matchesSearch(r, query)),
    );

    // Regulars is the one chip with an inherent order: you asked for what you
    // cook most, so most-planned first. `plan_count` is a stored server field —
    // ordering by a shipped number is display, not a domain computation.
    if (key === 'regulars') {
        return matched.sort((a, b) => b.plan_count - a.plan_count || byName(a, b));
    }
    return matched.sort(byName);
}

/**
 * The chip row's state. Counts ignore the search box: a chip reads "how much is
 * behind this filter", and having the counts shift under a search would make
 * the row twitch on every keystroke (D-010 forbids motion on per-keystroke
 * churn; the same reasoning applies to numbers).
 */
export function buildFilterChips(
    recipes: Recipe[],
    axes: RecipeAxisFilters = NO_AXIS_FILTERS,
): RecipeFilterChip[] {
    // The axis filters DO move the counts, unlike the search box. The reason
    // is the same in both directions: a chip reads "how much is behind this
    // filter", and with "Breakfast" selected the honest answer to "Favourites"
    // is how many favourite breakfasts there are. Search churns per keystroke
    // and would make the row twitch; picking an axis is one deliberate act.
    const inScope = recipes.filter((r) => matchesAxes(r, axes));
    const countFor = (key: Exclude<RecipeFilterKey, 'suggests'>) =>
        inScope.filter(PREDICATES[key]).length;

    const chips: RecipeFilterChip[] = [
        // Suggests carries the whole-cookbook count only so the row doesn't
        // show a bare label; it is disabled when there is nothing to rank.
        {
            key: 'suggests',
            label: LABELS.suggests,
            count: inScope.length,
            disabled: inScope.length === 0,
            ...(inScope.length === 0
                ? { disabledReason: 'Add a recipe and Dora can suggest from it.' }
                : {}),
        },
    ];

    // `all` is never disabled — an empty cookbook is handled by the rail's own
    // "no recipes yet" state, and a disabled `All` would leave no chip usable.
    chips.push({ key: 'all', label: LABELS.all, count: countFor('all'), disabled: false });

    for (const key of ['cookable', 'favourites', 'not_lately', 'regulars'] as const) {
        const count = countFor(key);
        const disabled = count === 0;
        chips.push({
            key,
            label: LABELS[key],
            count,
            disabled,
            ...(disabled ? { disabledReason: DISABLED_REASONS[key] } : {}),
        });
    }

    return chips;
}
