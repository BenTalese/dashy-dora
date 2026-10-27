import { storeToRefs } from 'pinia';
import { colourForSequence } from 'src/helpers/stockLevelLogic';
import {
    isLowStockSequence, isOutOfStockSequence, needsRestockSequence,
} from 'src/helpers/stockStatus';
import { useStockItemStore } from 'src/stores/stockItemStore';
import { useStockLevelStore } from 'src/stores/stockLevelStore';
import { computed } from 'vue';

// Shared stock-status glue (R-003): resolves a stock item to its level
// sequence + the app-wide label/colour, and the "needs buying" predicate. Used
// by the meal planner sidebar and the sequential builder so the rule lives once.
export function useStockStatus() {
    const { stockItems } = storeToRefs(useStockItemStore());
    const stockLevelStore = useStockLevelStore();

    const stockItemById = computed(() => {
        const map = new Map<string, typeof stockItems.value[number]>();
        stockItems.value.forEach((s) => map.set(s.stock_item_id, s));
        return map;
    });

    // Resolves by sequence (renaming a level in the UI doesn't shift buckets).
    function levelSequenceForItem(stockItemId: string): number | null {
        const item = stockItemById.value.get(stockItemId);
        if (!item) return null;
        if (typeof item.stock_level_sequence === 'number') return item.stock_level_sequence;
        return stockLevelStore.levelById.get(item.stock_level_id ?? '')?.sequence ?? null;
    }

    function stockStatusLabel(stockItemId: string): string {
        const item = stockItemById.value.get(stockItemId);
        if (!item) return 'Not tracked';
        return stockLevelStore.levelById.get(item.stock_level_id ?? '')?.name ?? 'Not tracked';
    }

    function stockStatusColour(stockItemId: string): string | null {
        return colourForSequence(levelSequenceForItem(stockItemId));
    }

    // Untracked (no sequence) OR low/out → still needs buying.
    function needsBuying(stockItemId: string): boolean {
        const seq = levelSequenceForItem(stockItemId);
        return seq === null || needsRestockSequence(seq);
    }

    // Owner feedback 2026-08-27 — the shared add-to-list picker needs the two
    // bands separately (missing sorts above low, and "Select missing" means
    // both). A recipe ingredient carries these as server-derived booleans; a
    // meal-plan aggregate doesn't, so they're resolved from the level here
    // rather than re-derived per surface (R-003).
    function isMissing(stockItemId: string): boolean {
        const seq = levelSequenceForItem(stockItemId);
        return seq === null || isOutOfStockSequence(seq);
    }
    function isLowStock(stockItemId: string): boolean {
        return isLowStockSequence(levelSequenceForItem(stockItemId));
    }

    return {
        levelSequenceForItem, stockStatusLabel, stockStatusColour, needsBuying,
        isMissing, isLowStock,
    };
}
