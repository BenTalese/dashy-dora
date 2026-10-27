// BRIEF_MEAL_PLANNER_RAIL_AND_SHELL §4.3 — the recipe rail's filter contract.
//
// Replaces `recipeTrays.spec.ts`, deleted with the tray builder on 2026-08-30.
// Worth an automated test under the lean verification stance (DORA_VERIFY
// banner): these are pure predicates with no pinia and no network, they are
// shared by three pickers (planner rail, mobile sheet, build-my-week wizard),
// and re-checking them by hand means constructing a cookbook with exactly the
// right mix of favourites/history/plan-counts every single time.
//
// The headline case is the one that INVERTS the old contract: trays gave each
// recipe exactly one home (FU-578 #47), filters deliberately do not.
import { describe, expect, it } from 'vitest';

import {
    NO_AXIS_FILTERS, buildFilterChips, filterRecipes,
    matchesAxes,
} from 'src/helpers/recipeRailFilters';
import type { Recipe } from 'src/models/recipe';

function recipe(over: Partial<Recipe> & { recipe_id: string; name: string }): Recipe {
    return {
        is_favourite: false,
        not_made_recently: false,
        plan_count: 0,
        last_made_on: null,
        ...over,
    } as Recipe;
}

const FAV_AND_REGULAR = recipe({
    recipe_id: 'a', name: 'Aglio e Olio', is_favourite: true, plan_count: 5,
});
const STALE = recipe({ recipe_id: 'b', name: 'Bolognese', not_made_recently: true });
const PLAIN = recipe({ recipe_id: 'c', name: 'Congee' });
const ALL = [FAV_AND_REGULAR, STALE, PLAIN];

describe('filterRecipes', () => {
    it('lets one recipe qualify for several chips (supersedes the FU-578 #47 dedupe)', () => {
        // The tray builder claimed each recipe for exactly one tray, so a
        // favourite that was also frequently planned vanished from "Regulars".
        // As filters that is wrong: you asked for regulars, so every regular
        // shows — and it cannot double-render because only one filter is ever
        // active.
        expect(filterRecipes(ALL, 'favourites').map((r) => r.recipe_id)).toEqual(['a']);
        expect(filterRecipes(ALL, 'regulars').map((r) => r.recipe_id)).toEqual(['a']);
    });

    it('selects on the server flag, never a client recency computation', () => {
        // `not_made_recently` is the server's 21-day household window. The old
        // builder additionally sorted by `last_made_on` client-side, which was
        // the R-003 leak this replacement removes.
        const withDates = [
            recipe({ recipe_id: 'x', name: 'Xacuti', not_made_recently: true, last_made_on: '2020-01-01' }),
            recipe({ recipe_id: 'y', name: 'Ayam', not_made_recently: true, last_made_on: '2026-01-01' }),
            recipe({ recipe_id: 'z', name: 'Zuppa', not_made_recently: false, last_made_on: null }),
        ];
        const out = filterRecipes(withDates, 'not_lately');
        expect(out.map((r) => r.recipe_id)).toEqual(['y', 'x']); // by NAME, not by date
    });

    it('orders regulars by plan_count, most-planned first', () => {
        const many = [
            recipe({ recipe_id: 'low', name: 'Aaa', plan_count: 1 }),
            recipe({ recipe_id: 'high', name: 'Zzz', plan_count: 9 }),
        ];
        expect(filterRecipes(many, 'regulars').map((r) => r.recipe_id)).toEqual(['high', 'low']);
    });

    it('narrows the active chip by search rather than replacing it', () => {
        // L99 — search is separate from the chips, so it applies ON TOP of the
        // filter. "Bolognese" matches the query but is not a favourite.
        expect(filterRecipes(ALL, 'favourites', 'bolog')).toEqual([]);
        expect(filterRecipes(ALL, 'all', 'bolog').map((r) => r.recipe_id)).toEqual(['b']);
    });

    it('matches search case-insensitively', () => {
        expect(filterRecipes(ALL, 'all', 'AGLIO').map((r) => r.recipe_id)).toEqual(['a']);
    });

    it('treats the suggests chip as unfiltered — the caller supplies the ranking', () => {
        expect(filterRecipes(ALL, 'suggests')).toHaveLength(3);
    });
});

describe('buildFilterChips', () => {
    it('keeps an empty chip in place, disabled and explained (B2a)', () => {
        // The old trays hid themselves when empty, so the row reflowed as the
        // cookbook grew and the user lost their spatial memory of the controls.
        const chips = buildFilterChips([PLAIN]);
        const favourites = chips.find((c) => c.key === 'favourites');

        expect(favourites).toBeDefined();
        expect(favourites?.disabled).toBe(true);
        expect(favourites?.disabledReason).toBeTruthy();
    });

    it('never disables All, so at least one chip is always usable', () => {
        expect(buildFilterChips([]).find((c) => c.key === 'all')?.disabled).toBe(false);
    });

    it('puts Dora suggests first, since the brief requires it be marked out', () => {
        expect(buildFilterChips(ALL)[0]?.key).toBe('suggests');
    });

    it('counts each chip independently of the others', () => {
        const counts = Object.fromEntries(
            buildFilterChips(ALL).map((c) => [c.key, c.count]),
        );
        expect(counts.all).toBe(3);
        expect(counts.favourites).toBe(1);
        expect(counts.not_lately).toBe(1);
        expect(counts.regulars).toBe(1);
    });
});

describe('the "Can cook now" chip', () => {
    // Owner 2026-09-12 — a quick filter for "ingredients all available".
    const COOKABLE = recipe({ recipe_id: 'd', name: 'Dal', cookable: true });
    const SHORT = recipe({ recipe_id: 'e', name: 'Eggs Benedict', cookable: false });
    const UNKNOWN = recipe({ recipe_id: 'f', name: 'Focaccia', cookable: null });

    it('takes only recipes the server calls cookable', () => {
        const names = filterRecipes([COOKABLE, SHORT, UNKNOWN], 'cookable').map((r) => r.name);
        expect(names).toEqual(['Dal']);
    });

    it("excludes the tri-state unknown — \"we don't know\" is not \"you can\"", () => {
        expect(filterRecipes([UNKNOWN], 'cookable')).toEqual([]);
        expect(buildFilterChips([UNKNOWN]).find((c) => c.key === 'cookable')?.disabled).toBe(true);
    });
});

// ── The second axis: time of day + difficulty (owner, 2026-09-01) ─────────
//
// These narrow whatever the chip row produced, the way the search box does —
// so the interesting cases are all about COMPOSITION, plus one deliberate
// asymmetry: the chip counts follow the axes but deliberately do not follow
// the search box.

const BREAKFAST_EASY = recipe({
    recipe_id: 'p', name: 'Porridge', time_of_day: 'Breakfast', difficulty: 'Easy',
});
const DINNER_HARD_FAV = recipe({
    recipe_id: 'l', name: 'Lasagne', time_of_day: 'Dinner', difficulty: 'Hard', is_favourite: true,
});
const LUNCH_EASY_FAV = recipe({
    recipe_id: 's', name: 'Soup', time_of_day: 'Lunch', difficulty: 'Easy', is_favourite: true,
});
const UNCLASSIFIED_FAV = recipe({ recipe_id: 'm', name: 'Mystery', is_favourite: true });
const AXIS_ALL = [BREAKFAST_EASY, DINNER_HARD_FAV, LUNCH_EASY_FAV, UNCLASSIFIED_FAV];

describe('matchesAxes', () => {
    it('an unset axis matches everything, including a recipe with no value', () => {
        expect(AXIS_ALL.every((r) => matchesAxes(r, NO_AXIS_FILTERS))).toBe(true);
    });

    it('excludes a recipe with no value once that axis is set', () => {
        // "We don't know what this is" is not a breakfast. Including unknowns
        // would make the filter useless the moment a cookbook has any.
        expect(matchesAxes(UNCLASSIFIED_FAV, { timeOfDay: 'Dinner', difficulty: null })).toBe(false);
        expect(matchesAxes(UNCLASSIFIED_FAV, { timeOfDay: null, difficulty: 'Easy' })).toBe(false);
    });

    it('ANDs the two axes together', () => {
        expect(matchesAxes(LUNCH_EASY_FAV, { timeOfDay: 'Lunch', difficulty: 'Easy' })).toBe(true);
        expect(matchesAxes(LUNCH_EASY_FAV, { timeOfDay: 'Lunch', difficulty: 'Hard' })).toBe(false);
    });
});

describe('filterRecipes with the axes', () => {
    it("narrows the chip's result rather than replacing it", () => {
        const favouriteEasies = filterRecipes(
            AXIS_ALL, 'favourites', '', { timeOfDay: null, difficulty: 'Easy' },
        );
        // Lasagne is a favourite but Hard; Porridge is Easy but not a favourite.
        expect(favouriteEasies.map((r) => r.recipe_id)).toEqual(['s']);
    });

    it('composes with the search box as well as the chip', () => {
        expect(
            filterRecipes(AXIS_ALL, 'all', 'so', { timeOfDay: null, difficulty: 'Easy' })
                .map((r) => r.recipe_id),
        ).toEqual(['s']);
        expect(
            filterRecipes(AXIS_ALL, 'all', 'so', { timeOfDay: 'Dinner', difficulty: null }),
        ).toEqual([]);
    });

    it('defaults to no axis narrowing when the argument is omitted', () => {
        expect(filterRecipes(AXIS_ALL, 'all')).toHaveLength(AXIS_ALL.length);
    });
});

describe('buildFilterChips under the axes', () => {
    it('counts within the active axes', () => {
        // A chip reads "how much is behind this filter", so with Easy selected
        // the honest answer to Favourites is how many easy favourites exist.
        const chips = buildFilterChips(AXIS_ALL, { timeOfDay: null, difficulty: 'Easy' });
        expect(chips.find((c) => c.key === 'favourites')?.count).toBe(1);
        expect(chips.find((c) => c.key === 'all')?.count).toBe(2);
    });

    it('disables a chip the axes have emptied, and still never disables All', () => {
        const chips = buildFilterChips(AXIS_ALL, { timeOfDay: 'Breakfast', difficulty: null });
        expect(chips.find((c) => c.key === 'favourites')?.disabled).toBe(true);
        expect(chips.find((c) => c.key === 'all')?.disabled).toBe(false);
    });
});
