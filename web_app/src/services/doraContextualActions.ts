import { ICONS } from 'src/style/icons';
// Screen-aware quick actions for the Dora assistant (P14).
//
// `contextualActionsFor` returns a list of actions tailored to the current
// route and its params — e.g. on `/stock/:id` the assistant offers "Find
// cheaper alternatives", "Add to list", and "Find substitutes" wired to
// that specific item. Handlers are dispatched by kind in DoraChat so the
// composables (P0) stay in `setup` scope where Vue requires them.
//
// We keep this list short on purpose — the assistant should suggest the
// 2-3 *most likely* next moves, not every possible action. If a screen
// already has the action one click away (e.g. the cart button on every
// stock row), the assistant doesn't need to duplicate it.

export type ContextualAction =
    // Plain route push. Used when the destination page already implements
    // the action better than the assistant could (e.g. /meal-plans for
    // scheduling a recipe).
    | { kind: 'navigate'; label: string; icon: string; path: string; query?: Record<string, string> }
    // "Add this stock item to the user's open draft list" — goes through
    // useStockItemActions so notify/error handling matches the rest of
    // the app.
    | { kind: 'add_to_list'; label: string; icon: string; stockItemId: string }
    // Pop the QuickAddSheet, optionally pre-targeting a list (used on
    // shopping list detail to drop a fresh item onto the current list).
    | { kind: 'quick_add'; label: string; icon: string; listId?: string }
    // Recipe-specific helpers. The chat handles the "what's missing"
    // computation inline so we don't have to drag the recipe store
    // through this module.
    | { kind: 'whats_missing'; label: string; icon: string; recipeId: string }
    | { kind: 'add_missing'; label: string; icon: string; recipeId: string }
    // Open the external Product Search companion (FU-186 retired the in-app
    // `/product-search` route). Carries no path — the destination is the
    // admin-configured URL, resolved at dispatch time, with a fallback to the
    // Features setup page when unset. See openProductSearch (FU-581).
    | { kind: 'product_search'; label: string; icon: string };

// Route-aware contextual action lookup. The function takes the path and
// the resolved `:id` param (when present) — we don't need the whole
// `useRoute` object here, which keeps this testable.
export function contextualActionsFor(
    path: string,
    params: { id?: string | undefined },
): ContextualAction[] {
    // ── Stock item detail ───────────────────────────────────────────
    if (path.startsWith('/stock/') && params.id) {
        const id = params.id;
        return [
            {
                kind: 'product_search',
                label: 'Find cheaper alternatives',
                icon: ICONS.price_check,
            },
            {
                kind: 'add_to_list',
                label: 'Add to my list',
                icon: ICONS.add_shopping_cart,
                stockItemId: id,
            },
            {
                kind: 'navigate',
                label: 'Find substitutes',
                icon: ICONS.swap_horiz,
                path: `/stock/${id}`,
                query: { section: 'substitutes' },
            },
        ];
    }

    // ── Recipe detail / edit ────────────────────────────────────────
    if (
        path.startsWith('/cookbook/')
        && params.id
        && !path.endsWith('/cook')
    ) {
        const id = params.id;
        return [
            {
                kind: 'whats_missing',
                label: "What's missing?",
                icon: ICONS.fact_check,
                recipeId: id,
            },
            {
                // The planner is slot-first (arm a day's slot, then pick the
                // recipe) and has no recipe preselect to hand off to, so this
                // only opens it — it used to say "Plan this for a day" and pass
                // a `recipe_id` the planner never read.
                kind: 'navigate',
                label: 'Open Meal Plans',
                icon: ICONS.event_note,
                path: '/meal-plans',
            },
            {
                kind: 'add_missing',
                label: 'Add missing to a list',
                icon: ICONS.add_shopping_cart,
                recipeId: id,
            },
        ];
    }

    // ── Stock overview ──────────────────────────────────────────────
    if (path === '/stock') {
        return [
            {
                kind: 'navigate',
                label: "Items needing attention",
                icon: ICONS.priority_high,
                path: '/stock',
                query: { attention: 'true' },
            },
            {
                kind: 'quick_add',
                label: 'Quick-add to my list',
                icon: ICONS.add_shopping_cart,
            },
        ];
    }

    // ── Cookbook overview ───────────────────────────────────────────
    if (path === '/cookbook') {
        return [
            {
                kind: 'navigate',
                label: 'Cookable now',
                icon: ICONS.check_circle,
                path: '/cookbook',
                query: { cookable: 'true' },
            },
        ];
    }

    // ── Shopping list detail ────────────────────────────────────────
    if (path.startsWith('/shopping-lists/') && params.id) {
        return [
            {
                kind: 'quick_add',
                label: 'Quick-add an item',
                icon: ICONS.add,
                listId: params.id,
            },
        ];
    }

    // ── Shopping lists overview ─────────────────────────────────────
    if (path === '/shopping-lists') {
        return [
            {
                kind: 'navigate',
                label: 'Find a recipe to cook',
                icon: ICONS.menu_book,
                path: '/cookbook',
                query: { cookable: 'true' },
            },
        ];
    }

    // ── My products ─────────────────────────────────────────────────
    if (path === '/my-products') {
        return [
            {
                kind: 'product_search',
                label: 'Hunt for fresh deals',
                icon: ICONS.search,
            },
        ];
    }

    // ── Dashboard ───────────────────────────────────────────────────
    if (path === '/' || path === '') {
        return [
            {
                kind: 'navigate',
                label: 'See what needs attention',
                icon: ICONS.priority_high,
                path: '/stock',
                query: { attention: 'true' },
            },
        ];
    }

    // Nothing specific — caller falls back to the generic QUICK_ACTIONS.
    return [];
}
