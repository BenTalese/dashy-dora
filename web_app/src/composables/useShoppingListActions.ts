import { useQuasar } from 'quasar';
// FU-572: list membership feeds the buy-verdict one-tap action
// (add_to_list vs remove_from_list), so every add/remove seam here
// drops the item's cached verdict.
import { invalidateBuyVerdict } from 'src/composables/useBuyVerdict';
import type { LineChoicePick } from 'src/components/shoppingList/addToListTypes';
import type { AddLineCommand } from 'src/services/api/shoppingListApiService';
import ShoppingListApiService from 'src/services/api/shoppingListApiService';
import { useShoppingListStore } from 'src/stores/shoppingListStore';

const api = new ShoppingListApiService();

/**
 * Cross-feature actions for a shopping list. Screens compose these so
 * add-items / finish-shopping behave identically wherever they are triggered
 * (lists overview, list detail, QuickAddSheet, cook mode).
 *
 * Call from a component `setup`.
 *
 * Chunk 2: `setPrimary` is gone — "primary" is now inferred from DRAFT-count
 * by the server resolver and the client's sessionStorage pick.
 */
export function useShoppingListActions() {
    const $q = useQuasar();
    const shoppingListStore = useShoppingListStore();

    const notifyOk = (message: string) =>
        $q.notify({ type: 'positive', message });
    const notifyErr = (message: string, caption?: string) =>
        $q.notify({
            type: 'negative',
            message,
            ...(caption ? { caption } : {}),
        });

    /**
     * Add one or more stock items to a list. Each entry may carry a quantity
     * and a pre-selected merchant offer. Returns counts so callers can phrase
     * their own messaging if they want.
     */
    async function addItems(
        listId: string,
        items: AddLineCommand[],
    ): Promise<{ added: number; already: number }> {
        let added = 0;
        let already = 0;
        try {
            for (const item of items) {
                const result = await api.addLineAsync(listId, item);
                if (result.already_on_list) already++;
                else added++;
                if (item.stock_item_id) invalidateBuyVerdict(item.stock_item_id);
            }
            await shoppingListStore.refreshAsync();
            notifyOk(
                `${added} added${already > 0 ? `, ${already} already on list` : ''}.`,
            );
        } catch (err) {
            notifyErr('Could not add all items.', String(err));
        }
        return { added, already };
    }

    /**
     * Owner feedback 2026-08-27 — the commit half of the shared add-to-list
     * flow (`AddToListDialog`). The dialog can offer "+ New list", so the
     * target may not exist yet; creating it here keeps both callers from
     * hand-rolling create-then-add in slightly different orders.
     *
     * `choices` gives an item the preferred buy or product its recipe picked.
     *
     * Returns the list the items landed on, so a caller can navigate to it.
     */
    async function addStockItemsToList(
        targetListId: string | null,
        stockItemIds: string[],
        newListName: string,
        choices?: Map<string, LineChoicePick>,
    ): Promise<string | null> {
        let listId = targetListId;
        if (listId === null) {
            try {
                const created = await api.createAsync({ name: newListName });
                listId = created.shopping_list_id;
            } catch (err) {
                notifyErr('Could not create the list.', String(err));
                return null;
            }
        }
        await addItems(listId, stockItemIds.map((id) => ({ stock_item_id: id, ...choices?.get(id) })));
        return listId;
    }

    /**
     * C-7 Chunk 1 — remove a stock item from a single list. Returns true on
     * success, false on failure. The caller composes higher-level UX
     * (toast, multi-list popover); this helper handles the API round-trip
     * + store refresh in one place so every consumer reads the same
     * membership state afterward.
     */
    async function removeFromList(
        listId: string,
        stockItemId: string,
    ): Promise<boolean> {
        try {
            await api.removeByStockItemFromListAsync(listId, stockItemId);
            await shoppingListStore.refreshAsync();
            invalidateBuyVerdict(stockItemId);
            return true;
        } catch (err) {
            notifyErr('Could not remove from list.', String(err));
            return false;
        }
    }

    /**
     * C-7 Chunk 1 — remove a stock item from every unticked list it's on.
     * One summary toast at the end (decision 6 — even for the "remove from
     * all" branch in the multi-list popover). Returns the count actually
     * removed.
     *
     * FU-573: `listIds` may include lists the item isn't on (callers fan out
     * over every open list), and the endpoint is an idempotent no-op there.
     * We count only responses where the server actually removed a line, so the
     * toast can't over-report (item on 1 list no longer says "Removed from 3").
     */
    async function removeFromAllLists(
        stockItemId: string,
        listIds: string[],
    ): Promise<number> {
        let removed = 0;
        let failed = 0;
        for (const listId of listIds) {
            try {
                const result = await api.removeByStockItemFromListAsync(listId, stockItemId);
                if (result.removed) removed++;
            } catch {
                // Continue; one bad list shouldn't block the others.
                failed++;
            }
        }
        if (removed > 0) {
            await shoppingListStore.refreshAsync();
            invalidateBuyVerdict(stockItemId);
            notifyOk(`Removed from ${removed} list${removed === 1 ? '' : 's'}.`);
        } else if (failed > 0) {
            notifyErr('Could not remove from any list.');
        } else if (listIds.length > 0) {
            notifyOk('It was already off your lists.');
        }
        return removed;
    }

    return {
        addItems, addStockItemsToList, removeFromList,
        removeFromAllLists,
    };
}
