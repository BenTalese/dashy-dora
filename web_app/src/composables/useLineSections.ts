import { computed, type ComputedRef, type Ref } from 'vue';
import { ICONS } from 'src/style/icons';
import type { ShoppingListLine } from 'src/models/shoppingList';

/**
 * Sectioning for the shopping list's active face.
 *
 * Four peer modes. Three of them read a field that plenty of installs never
 * populate, which drives the two rules that matter here:
 *
 * 1. Lines with no value for the active mode fall into a trailing **Unsorted**
 *    section rather than vanishing or inventing a bucket.
 * 2. A mode whose field is empty on *every* line is reported as unavailable, so
 *    the UI can disable it with a reason instead of offering a control that
 *    silently does nothing. This is also what lets `store` be a peer mode
 *    everywhere instead of a run-face special case — on a single-store list it
 *    collapses to one section and disables itself.
 *
 * `none` is always available: one ungrouped run, A to Z. It was the user's own
 * `sequence` order until UX v5 removed custom ordering (owner, 2026-11-08:
 * *"reordering and custom order is not really that useful and is just noise"*).
 * Store is the default (*"default sort should be by shop"*).
 */
export type SectionMode = 'location' | 'group' | 'store' | 'none';

export const SECTION_MODES: SectionMode[] = ['location', 'group', 'store', 'none'];

export const DEFAULT_SECTION_MODE: SectionMode = 'store';

export const SECTION_MODE_LABELS: Record<SectionMode, string> = {
    location: 'Location',
    group: 'Group',
    store: 'Store',
    none: 'A to Z',
};

/** The glyph that names what a section header is grouping by. Lives here
 *  rather than on each surface so the list and its overview card can't drift
 *  into using different icons for the same mode (D-003 one-glyph-one-meaning). */
export function sectionIconFor(mode: SectionMode): string {
    switch (mode) {
        case 'location': return ICONS.place;
        case 'store': return ICONS.storefront;
        case 'group': return ICONS.category;
        case 'none': return ICONS.sort_alpha;
    }
}

export type LineSection = {
    key: string;
    /** `null` only when grouping is off, where the list is one unlabelled run. */
    label: string | null;
    lines: ShoppingListLine[];
    /** The trailing catch-all for lines with no value in this mode. */
    isUnsorted: boolean;
};

const UNSORTED_KEY = '__unsorted__';

/** The zone the location breadcrumb names — the top crumb, not the leaf.
 *  "Kitchen › Fridge › Door" sections under "Kitchen", because that is the
 *  granularity someone actually walks. */
function locationKeyFor(line: ShoppingListLine): string | null {
    return line.stock_location_breadcrumb[0] ?? null;
}

function keyFor(line: ShoppingListLine, mode: SectionMode): string | null {
    switch (mode) {
        case 'location':
            return locationKeyFor(line);
        case 'group':
            return line.stock_group_name;
        case 'store':
            // The resolved store, not the offer's — so this works for someone
            // who has never linked a product but tags items with a usual store.
            return line.resolved_store_name;
        case 'none':
            return null;
    }
}

/** A nested product line sits under its stock-item parent; a product-only line
 *  stands alone. Both must survive sectioning, so children are re-attached to
 *  their parent after bucketing. */
export function isNestedChild(line: ShoppingListLine): boolean {
    return !!(line.stock_item_id && line.product_id);
}

export function isProductOnly(line: ShoppingListLine): boolean {
    return !line.stock_item_id && !!line.product_id;
}

/** Re-order a bucket so each parent is immediately followed by its nested
 *  product children. Stable: everything else keeps its incoming order. */
export function withNestedChildren(lines: ShoppingListLine[]): ShoppingListLine[] {
    const parentByStockItem = new Map<string, ShoppingListLine>();
    for (const l of lines) {
        if (l.stock_item_id && !l.product_id) parentByStockItem.set(l.stock_item_id, l);
    }
    const childrenByParent = new Map<string, ShoppingListLine[]>();
    const rest: ShoppingListLine[] = [];
    for (const l of lines) {
        if (isNestedChild(l)) {
            const parent = parentByStockItem.get(l.stock_item_id!);
            if (parent) {
                const bucket = childrenByParent.get(parent.line_id) ?? [];
                bucket.push(l);
                childrenByParent.set(parent.line_id, bucket);
                continue;
            }
        }
        rest.push(l);
    }
    const out: ShoppingListLine[] = [];
    for (const l of rest) {
        out.push(l);
        const kids = childrenByParent.get(l.line_id);
        if (kids) out.push(...kids);
    }
    return out;
}

export type UseLineSectionsOptions = {
    /** The active face: a ticked line leaves its section for Collected (the
     *  list shrinks as you shop). The receipt and the overview card count
     *  every line. */
    hideTicked?: boolean;
};

/** A to Z by the name the row shows. The one in-section order since custom
 *  ordering went (UX v5). */
function byName(lines: ShoppingListLine[]): ShoppingListLine[] {
    return [...lines].sort((a, b) => a.stock_item_name.localeCompare(b.stock_item_name));
}

export function useLineSections(
    lines: Ref<ShoppingListLine[]> | ComputedRef<ShoppingListLine[]>,
    mode: Ref<SectionMode> | ComputedRef<SectionMode>,
    options: UseLineSectionsOptions = {},
) {
    /** Which modes have any data to section by. `none` is always in. */
    const availableModes = computed<Record<SectionMode, boolean>>(() => {
        const source = lines.value;
        return {
            location: source.some((l) => locationKeyFor(l) !== null),
            group: source.some((l) => l.stock_group_name !== null),
            store: source.some((l) => l.resolved_store_name !== null),
            none: true,
        };
    });

    /** The mode actually in force. Falls back to ungrouped when the chosen mode
     *  has no data — a stored preference must not strand the user on an empty
     *  control after they clear the field it depended on. */
    const effectiveMode = computed<SectionMode>(() =>
        availableModes.value[mode.value] ? mode.value : 'none'
    );

    const sections = computed<LineSection[]>(() => {
        const active = lines.value;
        const visible = options.hideTicked ? active.filter((l) => !l.is_ticked) : active;

        if (effectiveMode.value === 'none') {
            return [{
                key: 'all',
                label: null,
                lines: withNestedChildren(byName(visible)),
                isUnsorted: false,
            }];
        }

        const buckets = new Map<string, LineSection>();
        for (const line of visible) {
            const value = keyFor(line, effectiveMode.value);
            const key = value ?? UNSORTED_KEY;
            let bucket = buckets.get(key);
            if (!bucket) {
                bucket = {
                    key,
                    label: value ?? 'Unsorted',
                    lines: [],
                    isUnsorted: value === null,
                };
                buckets.set(key, bucket);
            }
            bucket.lines.push(line);
        }
        for (const bucket of buckets.values()) {
            bucket.lines = withNestedChildren(byName(bucket.lines));
        }
        return [...buckets.values()].sort((a, b) => {
            if (a.isUnsorted !== b.isUnsorted) return a.isUnsorted ? 1 : -1;
            return (a.label ?? '').localeCompare(b.label ?? '');
        });
    });

    /** Every line in render order — the flat list the keyboard/focus helpers
     *  and the "next unticked" logic walk. */
    const orderedLines = computed(() => sections.value.flatMap((s) => s.lines));

    return { sections, orderedLines, availableModes, effectiveMode };
}

/** Per-section progress for the active face: how many are picked, and whether the
 *  whole section is cleared (which collapses it to a single line). Counts come
 *  from the unfiltered list so a section that has emptied still knows its size. */
export function sectionProgress(
    allLines: ShoppingListLine[],
    section: LineSection,
    mode: SectionMode,
): { total: number; picked: number; cleared: boolean } {
    const members = mode === 'none'
        ? allLines
        : allLines.filter((l) => (keyFor(l, mode) ?? UNSORTED_KEY) === section.key);
    const picked = members.filter((l) => l.is_ticked).length;
    return { total: members.length, picked, cleared: members.length > 0 && picked === members.length };
}
