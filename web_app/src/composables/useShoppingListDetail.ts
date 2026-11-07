/**
 * The shopping-list page's shared state (FU-780).
 *
 * `ShoppingListDetail.vue` was one ~3,250-line file. The run and receipt faces
 * were already their own components; the plan face, the line editor sheet, the
 * finish dialog and the receipt photos are now too — and the state those
 * blocks *share* lives here rather than being prop-drilled through a couple of
 * dozen handlers: the loaded list, which face it is showing, the quiet and
 * loud re-reads, the trim-to-budget banner (which every re-read refreshes, and
 * which must outlive the plan face being unmounted mid-shop), and the one
 * quantity write every face uses.
 *
 * The page calls `provideShoppingListDetail()` once in its setup; each block
 * calls `useShoppingListDetail()` (R-011: composables + provide/inject, not a
 * global store — this is one page's view state). What only one block reads
 * stays in that block. Same shape as `useRecipeDetail`.
 *
 * No business logic of its own: totals, the money ladder and the store ladder
 * are the server's (R-003) and are re-read, never re-derived.
 */
import { computed, inject, provide, reactive, ref, type InjectionKey } from 'vue';
import { useRoute } from 'vue-router';
import { useQuasar } from 'quasar';

import BuyVerdictApiService from 'src/services/api/buyVerdictApiService';
import { primeBuyVerdicts } from 'src/composables/useBuyVerdict';
import { useBuyVerdictEnabled } from 'src/composables/useBuyVerdictEnabled';
import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
import type { ShoppingListDetail, ShoppingListLine } from 'src/models/shoppingList';
import ShoppingListApiService, {
    type TrimToBudgetResult,
} from 'src/services/api/shoppingListApiService';
import { useAuthStore } from 'src/stores/authStore';
import { useShoppingListStore } from 'src/stores/shoppingListStore';
import { describeApiError, isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';

function createShoppingListDetail() {
    const route = useRoute();
    const $q = useQuasar();
    const api = new ShoppingListApiService();
    const store = useShoppingListStore();
    const authStore = useAuthStore();
    const { moneyEnabled } = useMoneyEnabled();
    // Per-user display opt-out (D-12). Gates the bulk verdict prefetch below;
    // `BuyVerdictBadgeInline` checks it again for the render.
    const { buyVerdictEnabled } = useBuyVerdictEnabled();

    const listId = computed(() => String(route.params.id ?? ''));
    const detail = ref<ShoppingListDetail | null>(null);

    // Which face is on screen. Named rather than compared inline because the
    // three compositions gate a couple of dozen blocks between them, and
    // `status === 'draft'` scattered through the template reads as an
    // implementation detail where "the plan face" reads as the design.
    //
    // Simple mode (owner, 2026-11-07) is a fourth face over the same list:
    // no lifecycle, and a tick means bought. It replaces the plan and run
    // faces on any list that isn't finished; a done list is still a receipt.
    const simpleMode = computed(() => authStore.currentUser?.shopping_simple_mode === true);
    const simpleFace = computed(
        () => simpleMode.value && !!detail.value && detail.value.status !== 'done',
    );
    const planFace = computed(() => !simpleFace.value && detail.value?.status === 'draft');
    const runFace = computed(() => !simpleFace.value && detail.value?.status === 'shopping');
    const receiptFace = computed(() => detail.value?.status === 'done');

    // Starts true: the first painted frame must be the skeleton, never the
    // "list isn't available" fallback (the S6 flash) — onMounted's load()
    // hasn't had a chance to set it yet on that first frame.
    const loading = ref(true);
    const loadError = ref<string | null>(null);

    // deferred-by-budget lines render under their own collapsible
    // section, not the active list. Server-side totals already skip them.
    const baseLines = computed(() =>
        (detail.value?.lines ?? []).filter((l) => !l.deferred_by_budget),
    );
    const deferredLines = computed(() =>
        (detail.value?.lines ?? []).filter((l) => l.deferred_by_budget),
    );

    // ── FU-448 trim-to-budget banner (PROPOSAL_BUDGET_AWARE_LISTS §6) ──

    type TrimState = 'idle' | 'previewed' | 'applied';
    type TrimPreviewLine = {
        line_id: string;
        name: string;
        reason_chip: string;
        saved: number;
    };
    function initialTrimState() {
        return {
            state: 'idle' as TrimState,
            busy: false,
            loaded: false,                    // true once we've fetched the initial preview
            projectedTotal: 0,
            budgetTarget: 0,
            overshoot: 0,
            stillOver: 0,
            savedApplied: 0,
            previewLines: [] as TrimPreviewLine[],
            excluded: new Set<string>(),
            dismissed: false,
        };
    }
    const trimState = reactive(initialTrimState());

    const trimBanner = computed(() => {
        // Money features off, no budget set, list not auto-generated,
        // dismissed, or nothing to trim → banner stays hidden.
        const anyDeferredAlready = deferredLines.value.length > 0;
        const applied = trimState.state === 'applied' && anyDeferredAlready;
        const hasOvershoot = trimState.overshoot > 0;
        return {
            visible: moneyEnabled.value
                && !trimState.dismissed
                && trimState.loaded
                && (hasOvershoot || applied),
            state: trimState.state,
            busy: trimState.busy,
            projectedTotal: trimState.projectedTotal,
            budgetTarget: trimState.budgetTarget,
            overshoot: trimState.overshoot,
            stillOver: trimState.stillOver,
            savedApplied: trimState.savedApplied,
            previewLines: trimState.previewLines,
            canApply: trimState.overshoot > 0 && trimState.previewLines.length > 0,
        };
    });

    async function refreshTrimStatus(): Promise<void> {
        // Only fetch when money features are on and the list has active lines
        // — the endpoint gracefully returns overshoot=0 when there's no budget,
        // but skipping the call altogether keeps a fresh install quiet.
        if (!moneyEnabled.value || !detail.value) return;
        if (baseLines.value.length === 0) {
            trimState.loaded = true;
            trimState.overshoot = 0;
            return;
        }
        const id = listId.value;
        try {
            const result = await api.trimToBudgetAsync(id, {
                mode: 'preview',
                exclude_line_ids: [...trimState.excluded],
            });
            // A list switch mid-flight must not paint A's banner onto B.
            if (id === listId.value) applyTrimResult(result);
        } catch {
            // Non-fatal; the banner just stays hidden.
            if (id === listId.value) trimState.loaded = true;
        }
    }

    function applyTrimResult(result: TrimToBudgetResult): void {
        trimState.loaded = true;
        trimState.projectedTotal = result.projected_total;
        trimState.budgetTarget = result.budget_target ?? 0;
        trimState.overshoot = result.overshoot;
        trimState.stillOver = result.still_over;
        // Freeze display names + saved amounts so the preview card doesn't
        // desync from the server (the SPA has all the info it needs).
        const nameByLine = new Map<string, string>();
        for (const l of detail.value?.lines ?? []) nameByLine.set(l.line_id, l.stock_item_name);
        trimState.previewLines = result.trimmed.map((t) => ({
            line_id: t.line_id,
            name: nameByLine.get(t.line_id) ?? 'Item',
            reason_chip: t.reason_chip,
            saved: t.saved,
        }));
    }

    async function previewTrim(): Promise<void> {
        if (trimState.busy) return;
        trimState.busy = true;
        try {
            const result = await api.trimToBudgetAsync(listId.value, {
                mode: 'preview',
                exclude_line_ids: [...trimState.excluded],
            });
            applyTrimResult(result);
            trimState.state = 'previewed';
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: describeApiError(err) ?? 'Could not preview the trim.',
                });
            }
        } finally {
            trimState.busy = false;
        }
    }

    async function applyTrim(): Promise<void> {
        if (trimState.busy) return;
        trimState.busy = true;
        try {
            const result = await api.trimToBudgetAsync(listId.value, {
                mode: 'apply',
                exclude_line_ids: [...trimState.excluded],
            });
            trimState.savedApplied = result.trimmed.reduce((s, t) => s + t.saved, 0);
            trimState.state = 'applied';
            trimState.previewLines = [];
            // Quiet — see `onRemoveLine`; trimming edits the list in place.
            await refreshDetailQuietly();
            // After apply the list has fewer active lines and totals shift;
            // re-check whether we still overshoot so the banner updates
            // ("still over" fallback vs. done).
            await refreshTrimStatus();
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: describeApiError(err) ?? 'Could not trim to fit.',
                });
            }
        } finally {
            trimState.busy = false;
        }
    }

    function keepFromTrim(lineId: string): void {
        trimState.excluded = new Set(trimState.excluded).add(lineId);
        // Re-preview so the totals + cut set update in-place.
        void previewTrim();
    }

    function dismissTrim(): void {
        trimState.dismissed = true;
    }


    /** The trim banner is per-list: a dismissal, an "applied" summary or a
     *  kept-line exclusion on list A must not carry over to list B. */
    function resetTrim(): void {
        Object.assign(trimState, initialTrimState());
    }

    async function load() {
        // The id this read is for: a list switch mid-flight starts another
        // load, and this one's late answer must not paint over it.
        const id = listId.value;
        if (!id) return;
        loading.value = true;
        loadError.value = null;
        // Clear the previous list's data so the user sees a loading spinner
        // — not stale rows from the list they navigated away from —
        // while the new list's detail is in flight.
        detail.value = null;
        try {
            const result = await api.getDetailAsync(id);
            if (id !== listId.value) return;
            detail.value = result;
            primeVerdicts(id);
        } catch (err) {
            if (id !== listId.value) return;
            loadError.value = `Could not load list: ${describeApiError(err)}`;
        } finally {
            if (id === listId.value) loading.value = false;
        }
        // refresh the trim-to-budget banner state as soon as the
        // list is available. Own try/catch inside; failures never bubble.
        void refreshTrimStatus();
    }

    /** Re-read the list without blanking the page.
     *
     *  `load()` deliberately nulls `detail` so switching lists shows a skeleton
     *  rather than the previous list's rows — right for a navigation, wrong for
     *  a refresh: mid-shop it would flash the whole page to a skeleton on every
     *  tick. This exists for the "I already painted the change optimistically,
     *  now reconcile the server-owned aggregates" case, and it stays silent on
     *  failure because the optimistic state is still the user's best guess and
     *  the next action will re-read anyway. */
    async function refreshDetailQuietly(): Promise<void> {
        const id = listId.value;
        if (!id) return;
        try {
            const result = await api.getDetailAsync(id);
            // A list switch mid-flight: the new list's load owns `detail`.
            if (id === listId.value) detail.value = result;
        } catch {
            // Intentionally silent — see above.
        }
    }

    // B6 — one request for the whole list's verdicts, marked in-flight before
    // the lines paint so each `BuyVerdictBadgeInline` reads the shared answer
    // instead of asking for its own. Called synchronously after `detail` is
    // assigned (Vue renders on the next tick, so the marks land first).
    // Fire-and-forget: `primeBuyVerdicts` swallows its own failure, and a list
    // that can't fetch verdicts still shows its items.
    function primeVerdicts(shoppingListId: string): void {
        if (!buyVerdictEnabled.value) return;
        const ids = (detail.value?.lines ?? [])
            .map((line) => line.stock_item_id)
            .filter((id): id is string => !!id);
        void primeBuyVerdicts(
            ids,
            () => new BuyVerdictApiService().getForListAsync(shoppingListId),
        );
    }

    async function refreshAll() {
        // Refresh detail + the store-level summaries/membership in
        // parallel so the rail order, next-up marker and cart-button
        // state elsewhere stay accurate.
        await Promise.all([load(), store.refreshAsync()]);
    }

    /** The quiet counterpart to `refreshAll()`, for edits to the list *itself*.
     *
     *  It re-reads everything a list-level edit can move — the detail, the
     *  rail's names and ordering, and the trim-to-budget state (the shop date
     *  decides which budget period applies) — but goes through
     *  `refreshDetailQuietly()` rather than `load()`.
     *
     *  That is the whole difference, and it matters: `load()` nulls `detail`
     *  first so a *navigation* shows a skeleton instead of the list you just
     *  left. Renaming a list or setting its shop day is not a navigation — you
     *  are still looking at the list you meant to look at — so blanking it
     *  flashed the entire page through the skeleton branch and back on every
     *  save (the 2026-08-29 *"why does the whole page refresh when I pick a
     *  shop date?"* report). */
    async function refreshAllQuietly(): Promise<void> {
        await Promise.all([refreshDetailQuietly(), store.refreshAsync()]);
        void refreshTrimStatus();
    }

    async function setLineQuantity(line: ShoppingListLine, next: number | null) {
        const previous = line.quantity;
        if (previous === next) return;
        line.quantity = next;
        try {
            await api.updateLineAsync(listId.value, line.line_id, { quantity: next });
        } catch (err) {
            line.quantity = previous;
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not update quantity.',
                    caption: toastCaption(err),
                });
            }
        }
    }

    async function onAdjustQuantity(line: ShoppingListLine, delta: number) {
        const current = line.quantity ?? 1;
        const next = Math.max(1, current + delta);
        await setLineQuantity(line, next);
        // On the receipt face the quantity is part of the money: it multiplies
        // the line total, the store split and the harvested observation the
        // server has just rewritten. Re-read rather than re-derive (R-003).
        if (receiptFace.value) await refreshDetailQuietly();
    }

    // In-flight row actions on the plan face, kept here rather than in the
    // face so a face switch mid-save doesn't re-enable the button (FU-981 (13)).
    const addingBackLineIds = ref<Set<string>>(new Set());
    const addingSuggestionId = ref<string | null>(null);

    return {
        api,
        listId,
        detail,
        addingBackLineIds,
        addingSuggestionId,
        simpleMode,
        simpleFace,
        planFace,
        runFace,
        receiptFace,
        loading,
        loadError,
        baseLines,
        deferredLines,
        trimBanner,
        previewTrim,
        applyTrim,
        keepFromTrim,
        dismissTrim,
        resetTrim,
        load,
        refreshDetailQuietly,
        refreshAll,
        refreshAllQuietly,
        setLineQuantity,
        onAdjustQuantity,
    };
}

export type ShoppingListDetailContext = ReturnType<typeof createShoppingListDetail>;

const SHOPPING_LIST_DETAIL_KEY: InjectionKey<ShoppingListDetailContext> = Symbol('shoppingListDetail');

/** Called once, in `ShoppingListDetail`'s setup. */
export function provideShoppingListDetail(): ShoppingListDetailContext {
    const ctx = createShoppingListDetail();
    provide(SHOPPING_LIST_DETAIL_KEY, ctx);
    return ctx;
}

/** Called by the shopping-list page's blocks. Throws outside the page: a block
 *  mounted without its page has no list to show, and a silent `undefined`
 *  would surface as a template error somewhere less obvious. */
export function useShoppingListDetail(): ShoppingListDetailContext {
    const ctx = inject(SHOPPING_LIST_DETAIL_KEY, null);
    if (!ctx) throw new Error('useShoppingListDetail() must be used inside ShoppingListDetail (provideShoppingListDetail).');
    return ctx;
}
