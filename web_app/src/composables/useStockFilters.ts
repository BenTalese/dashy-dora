import { isOutOfStockSequence } from 'src/helpers/stockStatus';
import { colourForSequence } from 'src/helpers/stockLevelLogic';
import { useLocationOptions } from 'src/composables/useLocationOptions';
import { nameCollator } from 'src/composables/useMoney';
import type { PageCount } from 'src/components/PageCountsFooter.vue';
import { cartStateFor, type CartState, type Membership } from 'src/models/shoppingList';
import type { Recipe } from 'src/models/recipe';
import type { StockGroup } from 'src/models/stockGroup';
import type { StockItem } from 'src/models/stockItem';
import type { LocationNode } from 'src/models/location';
import type { StockLevel } from 'src/models/stockLevel';
import { computed, ref, type DeepReadonly } from 'vue';
import { useListState } from 'src/composables/useListState';
import type { SortAxisFor } from 'src/components/filters/SortControl.vue';

/**
 * Sort AXES, not axis+direction pairs. This list used to be six options where
 * four were really two axes with the direction baked into the label ("Name
 * (A-Z)" / "Name (Z-A)", "lowest first" / "highest first") — so the page had
 * two different grammars for one concept, and the cookbook's separate
 * direction toggle made three across the app. Owner feedback 2026-08-18:
 * direction is always the attached toggle (`SortControl`), never an option.
 */
export type StockSortKey = 'attention' | 'name' | 'level' | 'updated' | 'expiry';

export type StockSortDir = 'asc' | 'desc';

export type StockCartFilter = 'all' | 'on_list' | 'off_list';

export const STOCK_SORT_OPTIONS: SortAxisFor<StockSortKey>[] = [
    // D-9 (Chunk 4) — the default. Sorts on the SAME three-band ramp the row
    // treatments paint (D-8), so position and appearance agree instead of
    // arguing: outlined rows on top, ordinary rows next, dimmed
    // "out-but-you-never-flagged-it" rows at the bottom.
    {
        value: 'attention', label: 'Needs attention',
        ascLabel: 'Most urgent first', descLabel: 'Least urgent first',
        defaultDir: 'asc',
    },
    {
        value: 'name', label: 'Name',
        ascLabel: 'A → Z', descLabel: 'Z → A', defaultDir: 'asc',
    },
    {
        value: 'level', label: 'Stock level',
        ascLabel: 'Lowest first', descLabel: 'Highest first', defaultDir: 'asc',
    },
    {
        value: 'updated', label: 'Last updated',
        ascLabel: 'Least recent first', descLabel: 'Most recent first',
    },
    {
        value: 'expiry', label: 'Expiry date',
        ascLabel: 'Expires soonest', descLabel: 'Expires latest', defaultDir: 'asc',
    },
];

/**
 * Stock sort is persisted per user, so installs carry the old combined keys
 * ('name_desc', 'level_lowest', …). Map them onto the axis+direction pair they
 * meant rather than silently resetting someone's saved sort to Name.
 */
const LEGACY_SORT_KEYS: Record<string, { sortBy: StockSortKey; sortDir: StockSortDir }> = {
    name_asc: { sortBy: 'name', sortDir: 'asc' },
    name_desc: { sortBy: 'name', sortDir: 'desc' },
    level_lowest: { sortBy: 'level', sortDir: 'asc' },
    level_highest: { sortBy: 'level', sortDir: 'desc' },
    updated_recent: { sortBy: 'updated', sortDir: 'desc' },
    expiry_asc: { sortBy: 'expiry', sortDir: 'asc' },
};

/** Reads a stored value that may be either shape. Exported for the test. */
export function migrateStockSort(
    stored: string | null | undefined,
): { sortBy: StockSortKey; sortDir: StockSortDir } {
    if (stored && stored in LEGACY_SORT_KEYS) return LEGACY_SORT_KEYS[stored]!;
    if (stored && STOCK_SORT_OPTIONS.some((o) => o.value === stored)) {
        const axis = STOCK_SORT_OPTIONS.find((o) => o.value === stored)!;
        return { sortBy: stored as StockSortKey, sortDir: axis.defaultDir ?? 'desc' };
    }
    // D-9: junk or nothing stored lands on the new default, not Name.
    return { sortBy: 'attention', sortDir: 'asc' };
}

/** Mirrors `RANK_NONE` in `stock_attention.py` — "nothing fired", sorting
 *  below every real rank. Only used as the fallback for a DTO from an older
 *  server that predates the field. */
export const ATTENTION_RANK_NONE = 9;

/**
 * The three-band treatment ramp (D-8), as a sortable number. One function so
 * the row's CSS classes and this comparator cannot disagree about which band
 * an item is in — the whole point of the ramp is that position and appearance
 * say the same thing.
 *
 *   0 — outlined: the server's attention rule fired. Needs you.
 *   1 — normal: fine.
 *   2 — dimmed: out of stock, but never flagged essential. FYI only.
 */
export function attentionBand(
    item: { needs_attention?: boolean; is_essential?: boolean },
    outOfStock: boolean,
): 0 | 1 | 2 {
    if (item.needs_attention === true) return 0;
    if (outOfStock && item.is_essential !== true) return 2;
    return 1;
}

/**
 * All filter / sort / summary state for the pantry. Reusable wherever a list
 * of stock items needs the canonical filter UI — currently StockOverview but
 * intended to power any future "find a stock item" picker too.
 */
// Sources are passed as getter functions so the composable stays decoupled
// from where the data lives (pinia stores, props, fixtures in tests). Each
// computed re-reads the getter on track, preserving reactivity. We accept
// DeepReadonly because that's the shape Pinia's storeToRefs exposes.
type ReadList<T> = ReadonlyArray<DeepReadonly<T>>;

export function useStockFilters(sources: {
    stockItems: () => ReadList<StockItem>;
    stockLevels: () => ReadList<StockLevel>;
    locationTree: () => ReadList<LocationNode>;
    recipes: () => ReadList<Recipe>;
    stockGroups: () => ReadList<StockGroup>;
    membership: () => Membership | null;
    // `needsCheckIds` (the stocktake queue) was a source here only to back the
    // retired "Needs check" chip. The queue is still fetched by StockOverview
    // for the row's dashed marker — it just isn't a filter axis any more.
}, options: { persistScope?: string } = {}) {
    // ── Raw filter state ────────────────────────────────────────────────
    // Wrapped via useListState so filters/search/sort survive nav-away
    // and back within the session (A8 §3). Reset on full reload.
    const state = options.persistScope
        ? useListState(`stockFilters:${options.persistScope}`, () => ({
            searchText: ref(''),
            levelFilter: ref<string | null>(null),
            locationFilter: ref<string | null>(null),
            groupFilter: ref<string | null>(null),
            essentialsOnly: ref(false),
            openOnly: ref(false),
            hasAlertOnly: ref(false),
            // "Expiring soon or already expired" — the Dora Score freshness
            // action deep-links here via ?expiring=1 (FU-583).
            expiringSoonOnly: ref(false),
            cartFilter: ref<StockCartFilter>('all'),
            // Deep-link from stock-item detail page's "Recipes using this".
            recipeFilter: ref<string | null>(null),
            // D-9 — "Needs attention" is the default axis (was Name).
            sortBy: ref<StockSortKey>('attention'),
            sortDir: ref<StockSortDir>('asc'),
        }))
        : {
            searchText: ref(''),
            levelFilter: ref<string | null>(null),
            locationFilter: ref<string | null>(null),
            groupFilter: ref<string | null>(null),
            essentialsOnly: ref(false),
            openOnly: ref(false),
            hasAlertOnly: ref(false),
            expiringSoonOnly: ref(false),
            cartFilter: ref<StockCartFilter>('all'),
            recipeFilter: ref<string | null>(null),
            // D-9 — "Needs attention" is the default axis (was Name).
            sortBy: ref<StockSortKey>('attention'),
            sortDir: ref<StockSortDir>('asc'),
        };
    const {
        searchText, levelFilter, locationFilter, groupFilter, essentialsOnly,
        openOnly, hasAlertOnly, expiringSoonOnly, cartFilter,
        recipeFilter, sortBy, sortDir,
    } = state;

    // A session persisted before the axis/direction split holds a combined key
    // ('level_lowest'); translate it in place so the saved intent survives.
    {
        const migrated = migrateStockSort(sortBy.value as string);
        if (migrated.sortBy !== (sortBy.value as string)) {
            sortBy.value = migrated.sortBy;
            sortDir.value = migrated.sortDir;
        }
    }

    // ── Lookup maps ─────────────────────────────────────────────────────
    const levelSequenceById = computed(() => {
        const map = new Map<string, number>();
        for (const l of sources.stockLevels())
            map.set(l.stock_level_id, l.sequence ?? 0);
        return map;
    });
    function levelSequence(id: string | null): number {
        if (!id) return -1;
        return levelSequenceById.value.get(id) ?? -1;
    }

    const cartStateById = computed(() => {
        const map = new Map<string, CartState>();
        const m = sources.membership();
        for (const item of sources.stockItems()) {
            map.set(item.stock_item_id, cartStateFor(item.stock_item_id, m));
        }
        return map;
    });

    // ── Per-item attention: READ, never derive ──────────────────────────
    // The rule lives on the server (`features/stock_items/stock_attention.py`)
    // and arrives on the DTO. This used to be a local `hasAlert` that restated
    // it — an essential/low/out check plus a hardcoded 7-day expiry window —
    // and the two copies disagreed four ways (B1–B4): the admin's configurable
    // window moved the bell and not the rows; a disabled alert kind silenced
    // the bell and not the rows; the alerts page deep-linked to a filter
    // running the other rule; and non-essential-out was "act on this" here and
    // "ignore this" there. Don't reintroduce a local predicate — if a new
    // condition should count, add it to `stock_attention.py`.
    function hasAlert(item: StockItem): boolean {
        return item.needs_attention === true;
    }
    /** Expired or expiring-soon, as the server judged it against the
     *  household's configured window. */
    function isExpiryFlagged(item: StockItem): boolean {
        const kinds = item.attention_kinds ?? [];
        return kinds.includes('expired') || kinds.includes('expiring_soon');
    }

    // ── Dropdown option lists ───────────────────────────────────────────
    // Full-path location labels ("Pantry › Middle shelf › Left side"), built
    // once from the tree. `allLocationOptions` is the canonical full list
    // (consumers that need the unfiltered set — e.g. the bulk-move dialog —
    // read this); `locationOptions` is the narrowing ref bound to the
    // searchable q-select via `filterLocations` (same UX as the detail page).
    const { allLocationOptions, locationOptions, filterLocations } = useLocationOptions(sources.locationTree);
    const groupOptions = computed(() =>
        sources.stockGroups().map((g) => ({
            label: g.name,
            value: g.stock_group_id,
        })),
    );

    // Resolve the active recipe filter into a (recipe-name, ingredient-id-set)
    // pair. Returns null when nothing's filtered, or the recipe can't be found
    // — the predicate below treats null as "off" so an orphaned id silently
    // disables the filter rather than emptying the list.
    const recipeFilterContext = computed<{ name: string; ids: Set<string> } | null>(() => {
        const id = recipeFilter.value;
        if (!id) return null;
        const recipe = sources.recipes().find((r) => r.recipe_id === id);
        if (!recipe) return null;
        const ids = new Set<string>();
        for (const ing of recipe.ingredients) {
            if (ing.stock_item_id) ids.add(ing.stock_item_id);
        }
        return { name: recipe.name, ids };
    });

    // ── Filtered + sorted output ────────────────────────────────────────
    const filteredStockItems = computed(() => {
        const tokens = (searchText.value ?? '')
            .trim()
            .toLowerCase()
            .split(/\s+/)
            .filter((t) => t.length > 0);

        const matches = sources.stockItems().filter((item) => {
            // A4: explicit "empty = off". A blank/null selection must skip the
            // predicate entirely, never exclude rows. (Was relying on
            // truthiness, which would break if a default were ever non-null.)
            if (levelFilter.value !== null && item.stock_level_id !== levelFilter.value)
                return false;
            if (locationFilter.value !== null && item.stock_location_id !== locationFilter.value)
                return false;
            if (groupFilter.value !== null && item.stock_group_id !== groupFilter.value)
                return false;
            if (essentialsOnly.value && !item.is_essential) return false;
            if (openOnly.value && !item.is_open) return false;
            if (hasAlertOnly.value && !hasAlert(item)) return false;
            if (expiringSoonOnly.value && !isExpiryFlagged(item)) return false;
            if (tokens.length > 0) {
                const haystack = item.name.toLowerCase();
                if (!tokens.some((t) => haystack.includes(t))) return false;
            }
            if (recipeFilterContext.value && !recipeFilterContext.value.ids.has(item.stock_item_id))
                return false;
            if (cartFilter.value !== 'all') {
                const state = cartStateById.value.get(item.stock_item_id) ?? 'none';
                const onList = state !== 'none';
                if (cartFilter.value === 'on_list' && !onList) return false;
                if (cartFilter.value === 'off_list' && onList) return false;
            }
            return true;
        });

        // Locale-aware collation from the locale authority (finalisation 20-R7).

        const collator = { compare: (a: string, b: string) => nameCollator().compare(a, b) };
        const sorted = [...matches];
        // One comparator per AXIS, written in its ascending sense; the
        // direction toggle flips the result. Previously each direction was its
        // own `case` with the comparison hand-reversed, which is how
        // `level_lowest` ended up subtracting in the opposite order to
        // `level_highest` and only the tie-break stayed identical.
        //
        // "Ascending" per axis means: name A→Z · stock level lowest-first ·
        // last-updated least-recent-first · expiry soonest-first.
        const dir = sortDir.value === 'asc' ? 1 : -1;
        const outOfStock = (item: DeepReadonly<StockItem>): boolean =>
            item.is_out_of_stock
            ?? isOutOfStockSequence(
                item.stock_level_sequence ?? levelSequence(item.stock_level_id),
            );
        sorted.sort((a, b) => {
            switch (sortBy.value) {
                case 'attention': {
                    // D-9. Primary: the three-band ramp (D-8). Secondary:
                    // the server's urgency RANK, but ONLY inside the outlined
                    // band — rank is 9 everywhere else, so comparing it across
                    // bands would be comparing nothing.
                    //
                    // Rank, not severity (owner, 2026-08-21: "what is the
                    // ordering within attention sort? seems a bit random").
                    // It was: severity, then name. But `expired` and
                    // `essential_low` are both severity `high`, so the band
                    // sorted alphabetically in practice and an expired jar
                    // could sit below an essential that was merely low.
                    // `attention_rank` orders expired → essential-out →
                    // expiring-soon → essential-low; the meaning lives in
                    // `stock_attention.py` (R-003) and this only compares ints.
                    //
                    // Tiebreak inside a rank: soonest expiry first, so a
                    // fortnight of expiring-soon items reads as a countdown
                    // rather than an alphabet. Then name, so the list is stable
                    // and doesn't reshuffle as levels change under it.
                    const ab = attentionBand(a, outOfStock(a));
                    const bb = attentionBand(b, outOfStock(b));
                    if (ab !== bb) return dir * (ab - bb);
                    if (ab === 0) {
                        const ar = a.attention_rank ?? ATTENTION_RANK_NONE;
                        const br = b.attention_rank ?? ATTENTION_RANK_NONE;
                        if (ar !== br) return dir * (ar - br);
                        const ae = a.expiry_date ?? '';
                        const be = b.expiry_date ?? '';
                        if (ae !== be && ae && be) return dir * ae.localeCompare(be);
                        if (ae !== be) return ae ? -1 : 1;
                    }
                    return collator.compare(a.name, b.name);
                }
                case 'level':
                    // levelSequence runs high→low as stock increases, so the
                    // ascending ("lowest first") sense subtracts b from a.
                    return (
                        dir * (levelSequence(b.stock_level_id) - levelSequence(a.stock_level_id))
                        || collator.compare(a.name, b.name)
                    );
                case 'updated':
                    return (
                        dir * (a.stock_level_last_updated ?? '').localeCompare(
                            b.stock_level_last_updated ?? '',
                        )
                        || collator.compare(a.name, b.name)
                    );
                case 'expiry': {
                    // C-waste W2: items without an expiry date always fall to
                    // the bottom — nulls-last is a property of the data, not of
                    // the direction, so it is deliberately NOT flipped by `dir`.
                    // Ties break on last-updated (least-recently touched is the
                    // "stalest") then name, so the order is fully deterministic.
                    const ae = a.expiry_date ?? '';
                    const be = b.expiry_date ?? '';
                    if (ae && !be) return -1;
                    if (!ae && be) return 1;
                    if (ae !== be) return dir * ae.localeCompare(be);
                    const au = a.stock_level_last_updated ?? '';
                    const bu = b.stock_level_last_updated ?? '';
                    if (au !== bu) return au.localeCompare(bu);
                    return collator.compare(a.name, b.name);
                }
                case 'name':
                default:
                    return dir * collator.compare(a.name, b.name);
            }
        });
        return sorted;
    });

    // ── Active-filter count (for the FilterBar badge; excludes search) ──
    const activeFilterCount = computed(() => {
        let n = 0;
        if (levelFilter.value !== null) n++;
        if (locationFilter.value !== null) n++;
        if (groupFilter.value !== null) n++;
        if (essentialsOnly.value) n++;
        if (openOnly.value) n++;
        if (hasAlertOnly.value) n++;
        if (expiringSoonOnly.value) n++;
        if (cartFilter.value !== 'all') n++;
        if (recipeFilter.value !== null) n++;
        return n;
    });

    // ── Sticky-footer counts (A7) — reflect the FILTERED view ───────────
    // R-003: the footer level palette *derives* from the one colour
    // authority (`stockLevelLogic.colourForSequence`) rather than
    // hand-copying it — so the D-001 escalation (Stocked green, Low amber,
    // Out red; grey = unknown only) can never drift between the row squares
    // and the footer counts. `colourForSequence` returns a Quasar semantic
    // name or `null` for unknown; the null case maps to the footer's
    // `muted` tone. The names it returns ('positive'|'warning'|'negative')
    // are all valid `PageCount['tone']` values.
    function toneForLevelSequence(seq: number): NonNullable<PageCount['tone']> {
        return (colourForSequence(seq) as PageCount['tone']) ?? 'muted';
    }
    const footerCounts = computed<PageCount[]>(() => {
        const items = filteredStockItems.value;
        const byLevel = new Map<string, number>();
        const cartMap = cartStateById.value;
        let flagged = 0;
        let attention = 0;
        let onAnyList = 0;
        for (const it of items) {
            if (it.stock_level_id)
                byLevel.set(it.stock_level_id, (byLevel.get(it.stock_level_id) ?? 0) + 1);
            if (it.is_essential) flagged++;
            if (hasAlert(it)) attention++;
            // Round-10: count items present on at least one active shopping
            // list — once per item, not per line/list. Anything other than
            // `none` qualifies (on_target / on_other / on_multiple).
            if ((cartMap.get(it.stock_item_id) ?? 'none') !== 'none') onAnyList++;
        }
        // minified labels; matches the plan's order:
        // Shown · Stocked · Low · Out · Essential · Needs-attention.
        // Level names are shortened for the chip ("Low Stock" → "Low",
        // "Out of Stock" → "Out") so they fit in a single sticky row.
        // FU-511 — "Auto-add" per-item count dropped; auto-add is now a
        // single install-wide setting (Settings → Admin → Stock),
        // nothing to count per-item.
        const shortLabel = (name: string): string =>
            name
                .replace(/\bLow Stock\b/i, 'Low')
                .replace(/\bOut of Stock\b/i, 'Out');
        // `hideOnMobile: true` on the level + essential stats: narrow
        // viewports get only Shown + Needs attention so the sticky
        // footer doesn't eat vertical space (round-6 feedback).
        const levelStats: PageCount[] = sources.stockLevels().map((l) => ({
            label: shortLabel(l.name),
            value: byLevel.get(l.stock_level_id) ?? 0,
            tone: toneForLevelSequence(l.sequence),
            group: 'levels' as const,
            hideOnMobile: true,
        }));
        // Feedback 2026-06-18 (round 2):
        //   • "Shown" stays neutral (default text colour).
        //   • Essential rides the secondary tone (FU-365 round 2) —
        //     matches the row's left-edge stripe + the Essential filter
        //     chip so the concept reads as one visual family.
        //   • Label is "Essential" (not "Flagged") so the wording stays
        //     consistent with the field on the detail page + the row's
        //     tooltip + the filter chip.
        // `group` drives PageCountsFooter's three-cluster justify-evenly
        // layout: [Shown] · [stock levels] · [other counts]. The right
        // cluster is Essential / On a list; Auto-add was retired here
        // by FU-511 (no per-item value to count).
        return [
            { label: 'Shown', value: items.length, group: 'shown' as const },
            { label: 'Needs attention', value: attention, tone: 'negative' as const, group: 'shown' as const },
            ...levelStats,
            { label: 'Essential', value: flagged, tone: 'secondary' as const, group: 'other' as const, hideOnMobile: true },
            { label: 'On a list', value: onAnyList, group: 'other' as const, hideOnMobile: true },
        ];
    });

    // ── Imperative helpers ──────────────────────────────────────────────
    function clearFilters() {
        searchText.value = '';
        levelFilter.value = null;
        locationFilter.value = null;
        groupFilter.value = null;
        essentialsOnly.value = false;
        openOnly.value = false;
        hasAlertOnly.value = false;
        expiringSoonOnly.value = false;
        cartFilter.value = 'all';
        recipeFilter.value = null;
    }

    return {
        // state
        searchText,
        levelFilter,
        locationFilter,
        groupFilter,
        essentialsOnly,
        openOnly,
        hasAlertOnly,
        expiringSoonOnly,
        cartFilter,
        recipeFilter,
        recipeFilterContext,
        sortBy,
        sortDir,
        // option lists
        locationOptions,
        allLocationOptions,
        filterLocations,
        groupOptions,
        // derived
        filteredStockItems,
        activeFilterCount,
        footerCounts,
        // helpers
        clearFilters,
    };
}
