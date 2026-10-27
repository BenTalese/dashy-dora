import { ref } from 'vue';

// Module-level state so any screen can pop the QuickAddSheet without the
// caller owning the component. <QuickAddSheet> is mounted once in MainLayout
// and reads this state; openQuickAdd() flips it open.

export type QuickAddOptions = {
    /** Pre-select a stock item: it is added and the sheet closes. */
    stockItemId?: string | null;
    /** Pre-select the target list; defaults to the inferred quick-add target. */
    listId?: string | null;
};

const isOpen = ref(false);
const presetStockItemId = ref<string | null>(null);
const presetListId = ref<string | null>(null);

export function useQuickAdd() {
    function openQuickAdd(options: QuickAddOptions = {}) {
        presetStockItemId.value = options.stockItemId ?? null;
        presetListId.value = options.listId ?? null;
        isOpen.value = true;
    }

    function closeQuickAdd() {
        isOpen.value = false;
    }

    return {
        isOpen,
        presetStockItemId,
        presetListId,
        openQuickAdd,
        closeQuickAdd,
    };
}
