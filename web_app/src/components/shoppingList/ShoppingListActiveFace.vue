<template>
    <!-- Budget-aware trim banner (money-gated + budget-set).
         Fires when the projected active-list total exceeds the
         user's period-remaining budget for this list's shop
         date. Never mutates on load; every mutation is a user
         tap. -->
    <q-banner
        v-if="trimBanner.visible && !hasTicks"
        class="q-mb-4 sl-panel sl-panel--warn"
        dense
    >
        <template #avatar>
            <q-icon :name="ICONS.savings" color="warning" />
        </template>
        <div v-if="trimBanner.state === 'applied'" class="text-body2">
            Trimmed
            <strong>{{ fmtMoney(trimBanner.savedApplied) }}</strong>
            to fit.
            <a
                href="#deferred-by-budget"
                class="text-primary"
                @click.prevent="scrollToDeferred"
            >
                see deferred ({{ deferredLines.length }})
            </a>
        </div>
        <div v-else class="text-body2">
            <strong>
                Projected {{ fmtMoney(trimBanner.projectedTotal) }} ·
                budget remaining {{ fmtMoney(trimBanner.budgetTarget) }}
            </strong>.
            Trim
            <strong>{{ fmtMoney(trimBanner.overshoot) }}</strong>
            to fit.
            <div
                v-if="trimBanner.state === 'previewed' && trimBanner.stillOver > 0"
                class="text-caption text-negative q-mt-xs"
            >
                Trimmed everything safe. Still
                {{ fmtMoney(trimBanner.stillOver) }} over.
            </div>
        </div>
        <template #action>
            <BaseButton
                v-if="trimBanner.state === 'idle'"
                variant="ghost"
                label="Show what would be cut"
                :loading="trimBanner.busy"
                @click="previewTrim"
            />
            <BaseButton
                v-if="trimBanner.state !== 'applied' && trimBanner.canApply"
                :label="trimBanner.state === 'previewed' ? 'Apply trim' : 'Trim to fit'"
                :loading="trimBanner.busy"
                @click="applyTrim"
            />
            <BaseButton
                v-if="trimBanner.state !== 'applied'"
                variant="ghost"
                label="Dismiss"
                @click="dismissTrim"
            />
        </template>
    </q-banner>

    <!-- Preview: which lines would go, each with a "Keep" opt-out. -->
    <q-card
        v-if="!hasTicks && trimBanner.state === 'previewed' && trimBanner.previewLines.length > 0"
        flat
        class="q-mb-4 sl-panel"
    >
        <q-card-section class="q-py-sm">
            <div class="text-caption dora-text-muted q-mb-xs">
                Would trim {{ trimBanner.previewLines.length }} line{{ trimBanner.previewLines.length === 1 ? '' : 's' }}
            </div>
            <!-- Same shape as the deferred rows below, and for
                 the same reason: a reason chip is a sentence,
                 and `q-item-section side` will not wrap for
                 it. -->
            <div
                v-for="p in trimBanner.previewLines"
                :key="p.line_id"
                class="sld-deferred-row"
            >
                <div class="sld-deferred-row__main">
                    <div>{{ p.name }}</div>
                    <div class="text-caption dora-text-muted">
                        <span class="sld-deferred-reason">{{ p.reason_chip }}</span>
                        {{ fmtMoney(p.saved) }} saved
                    </div>
                </div>
                <BaseButton
                    variant="subtle"
                    label="Keep"
                    class="sld-deferred-row__action"
                    @click="keepFromTrim(p.line_id)"
                />
            </div>
        </q-card-section>
    </q-card>

    <!-- Planning panels (trim, suggestions) step aside at the first tick:
         mid-aisle they push the list down (UX v5 Q1, Q2).

         FU-653: Dora's suggestions, above the list and
         visibly not part of it: chips you may tap to add,
         never lines that appeared on their own. Empty (and so
         absent) unless the user opted the shopping surface in.

         No dismiss (2026-09-17). The strip only exists because
         the household turned inference on for this surface, so
         a cross was a control for half-undoing a preference
         they set on purpose — and one that forgot by the next
         visit, since the hide was session-only. The switch in
         Settings is the real control; this is the feature
         doing what it was asked to do.
    -->
    <q-card
        v-if="visibleSuggestions.length > 0 && !hasTicks"
        flat
        class="q-mb-5 inferred-suggestions sl-panel"
    >
        <q-card-section class="q-pb-xs row items-center no-wrap q-gutter-xs">
            <q-icon :name="ICONS.dora_voice" size="18px" />
            <span class="text-subtitle2">Dora thinks you may be out of…</span>
        </q-card-section>
        <q-card-section class="q-pt-none">
            <div class="row q-gutter-xs">
                <q-chip
                    v-for="s in visibleSuggestions"
                    :key="s.stock_item_id"
                    clickable
                    outline
                    color="primary"
                    :icon="ICONS.add"
                    :disable="addingSuggestionId === s.stock_item_id"
                    @click="onAddSuggestion(s)"
                >
                    {{ s.name }}
                    <BaseTooltip v-if="s.reason" max-width="280px">
                        {{ s.reason }}
                    </BaseTooltip>
                </q-chip>
            </div>
        </q-card-section>
    </q-card>

    <q-card v-if="detail?.lines.length === 0" flat class="sl-panel">
        <q-card-section class="text-center dora-text-muted">
            No items yet. Add using the toolbar here, or add from your
            stock list.
        </q-card-section>
    </q-card>

    <template v-else>
        <div
            v-for="section in sections"
            :key="section.key"
            class="sl-section"
        >
            <div v-if="section.label && !section.cleared" class="sl-section__head">
                <q-icon :name="sectionIcon" size="16px" />
                <span class="sl-section__title">{{ section.label }}</span>
                <span class="sl-section__count">
                    {{ hasTicks ? `${section.picked}/${section.total}` : section.total }}
                </span>
            </div>
            <div v-if="section.lines.length > 0" class="sl-list">
                <ShoppingListRow
                    v-for="line in section.lines"
                    :key="line.line_id"
                    v-bind="rowProps(line)"
                    v-on="rowHandlers(line)"
                />
            </div>
            <!-- A cleared section collapses to one line rather than
                 vanishing, so the list doesn't feel like it lost your work. -->
            <div v-else-if="section.label" class="sl-run-cleared row items-center q-gutter-xs">
                <q-icon :name="ICONS.check_circle" color="positive" size="18px" />
                <span class="text-body2">{{ section.label }}: all {{ section.total }} collected</span>
            </div>
        </div>

        <div v-if="allTicked" class="text-center q-py-lg dora-text-muted">
            <q-icon :name="ICONS.check_circle" color="positive" size="40px" />
            <div class="text-subtitle1 q-mt-sm">That's everything.</div>
        </div>

        <!-- Ticked lines land here, collapsed: a record, not the job (Q7).
             Their controls stay live so a price can still be entered. -->
        <q-expansion-item
            v-if="tickedLines.length > 0"
            class="q-mt-md sl-panel sl-panel--sunken"
        >
            <template #header>
                <q-item-section avatar>
                    <q-icon :name="ICONS.check_circle" />
                </q-item-section>
                <q-item-section>
                    <q-item-label>Collected</q-item-label>
                    <q-item-label v-if="moneyEnabled" caption>
                        {{ fmtMoney(detail?.totals.picked_price) }} in the trolley
                    </q-item-label>
                </q-item-section>
                <q-item-section side>
                    <CountBadge
                        :count="tickedLines.length"
                        :label="`${tickedLines.length} collected`"
                    />
                </q-item-section>
            </template>
            <ShoppingListRow
                v-for="line in tickedLines"
                :key="line.line_id"
                v-bind="rowProps(line)"
                v-on="rowHandlers(line)"
            />
        </q-expansion-item>
    </template>

    <!-- Deferred-to-fit-budget section
         (PROPOSAL_BUDGET_AWARE_LISTS §6.3). Renders when the
         list has any lines with `deferred_by_budget=true`.
         Collapsible; each row shows the frozen reason chip
         and a one-tap "Add back" that flips the flag off
         via PATCH /lines/<id>. -->
    <q-expansion-item
        v-if="deferredLines.length > 0"
        id="deferred-by-budget"
        :label="`Deferred to fit budget (${deferredLines.length})`"
        :caption="`${fmtMoney(deferredTotal)} saved`"
        default-opened
        class="q-mt-md sl-panel sl-panel--sunken"
    >
        <!-- Hand-rolled rather than `q-item` + `q-item-section
             side` (2026-09-17). The side section doesn't wrap:
             at 375px the frozen reason is a full sentence
             ("Would put the week $12 over; the tin can wait.")
             and "Add back" printed straight across it. A row
             that can't fit its own contents on one line has to
             be allowed to become two. -->
        <div
            v-for="line in deferredLines"
            :key="line.line_id"
            class="sld-deferred-row"
        >
            <div class="sld-deferred-row__main">
                <div>{{ line.stock_item_name }}</div>
                <div class="text-caption dora-text-muted">
                    <span v-if="line.deferred_reason" class="sld-deferred-reason">
                        {{ line.deferred_reason }}
                    </span>
                    {{ fmtMoney(priceOfLine(line)) }}
                </div>
            </div>
            <BaseButton
                variant="subtle"
                label="Add back"
                class="sld-deferred-row__action"
                :loading="addingBackLineIds.has(line.line_id)"
                @click="addLineBackToActive(line.line_id)"
            />
        </div>
    </q-expansion-item>
</template>

<script lang="ts" setup>
    /**
     * The active face (UX v5): the list as it is built, ticked and priced, all
     * in one place. It merged the plan face (curation: trim, suggestions, the
     * row controls, deferred-to-fit) and the run face (sections that empty as
     * you shop, Collected). The page owns ticking, since a tick carries the
     * undo toast and the last-tick finish prompt.
     */
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import CountBadge from 'src/components/CountBadge.vue';
    import ShoppingListRow from 'src/components/shoppingList/ShoppingListRow.vue';
    import { ICONS } from 'src/style/icons';
    import {
        useLineSections, isNestedChild, isProductOnly, sectionIconFor,
        sectionProgress, type SectionMode,
    } from 'src/composables/useLineSections';
    import { invalidateBuyVerdict } from 'src/composables/useBuyVerdict';
    import { useBuyVerdictActions } from 'src/composables/useBuyVerdictActions';
    import { useConfirm } from 'src/composables/useConfirm';
    import { formatMoney } from 'src/composables/useMoney';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { useShoppingListDetail } from 'src/composables/useShoppingListDetail';
    import {
        priceOfLine,
        type InferredSuggestion,
        type ShoppingListLine,
    } from 'src/models/shoppingList';
    import { useProductStore } from 'src/stores/productStore';
    import { useStoresStore } from 'src/stores/storesStore';
    import { describeApiError, isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useQuasar } from 'quasar';
    import { computed } from 'vue';

    const emit = defineEmits<{
        /** Tick or untick. The page owns it (toast, undo, finish prompt). */
        toggle: [line: ShoppingListLine];
        'capture-price': [line: ShoppingListLine];
    }>();

    const props = defineProps<{
        /** The page's "Group by" preference. Read-only here: the overview card
         *  owns the control that sets it. */
        mode: SectionMode;
        /** Keyboard focus. The page owns the arrow-key shortcuts, so it owns
         *  which line they landed on. */
        focusedLineId: string | null;
    }>();

    const $q = useQuasar();
    const { confirm } = useConfirm();
    const productStore = useProductStore();
    const {
        api, listId, detail, baseLines, deferredLines,
        trimBanner, previewTrim, applyTrim, keepFromTrim, dismissTrim,
        refreshDetailQuietly, refreshAllQuietly,
        setLineQuantity,
        addingBackLineIds, addingSuggestionId, hasTicks,
    } = useShoppingListDetail();
    const { moneyEnabled } = useMoneyEnabled();

    const modeRef = computed(() => props.mode);

    function fmtMoney(v: number | null | undefined): string {
        return formatMoney(v ?? 0);
    }

    // Sectioning. Ticked lines leave their section for Collected, so a
    // section empties as you shop; its header counts what's collected once
    // anything is.
    const { sections: lineSections, effectiveMode } = useLineSections(
        baseLines, modeRef, { hideTicked: true },
    );

    const sections = computed(() =>
        lineSections.value.map((section) => ({
            ...section,
            ...sectionProgress(baseLines.value, section, effectiveMode.value),
        })),
    );

    const sectionIcon = computed(() => sectionIconFor(effectiveMode.value));

    const tickedLines = computed(() => baseLines.value.filter((l) => l.is_ticked));
    const allTicked = computed(
        () => baseLines.value.length > 0 && baseLines.value.every((l) => l.is_ticked),
    );

    function rowProps(line: ShoppingListLine) {
        return {
            line,
            focused: props.focusedLineId === line.line_id,
            nested: isNestedChild(line),
            productOnly: isProductOnly(line),
            storeOptions: plannedStoreOptionsFor(line),
        };
    }

    function rowHandlers(line: ShoppingListLine) {
        return {
            toggle: () => emit('toggle', line),
            remove: () => onRemoveLine(line.line_id),
            'set-quantity': (value: number) => setLineQuantity(line, value),
            'planned-store': (value: string | null) => onPlannedStoreChange(line, value),
            'pick-offer': (productId: string) => onPickOffer(line.line_id, productId),
            'pick-hint': (id: string | null) => onPickHint(line.line_id, id),
            'verdict-action': (kind: Parameters<typeof onLineVerdictAction>[1]) =>
                onLineVerdictAction(line, kind),
            'capture-price': () => emit('capture-price', line),
        };
    }

    const deferredTotal = computed(() =>
        deferredLines.value.reduce((sum, l) => sum + priceOfLine(l), 0),
    );

    async function addLineBackToActive(lineId: string): Promise<void> {
        if (addingBackLineIds.value.has(lineId)) return;
        addingBackLineIds.value = new Set(addingBackLineIds.value).add(lineId);
        try {
            await api.updateLineAsync(listId.value, lineId, {
                deferred_by_budget: false,
            });
            // Quiet — see `onRemoveLine`; the line moves section, the page stays.
            await refreshAllQuietly();
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: describeApiError(err) ?? 'Could not add that line back.',
                });
            }
        } finally {
            const next = new Set(addingBackLineIds.value);
            next.delete(lineId);
            addingBackLineIds.value = next;
        }
    }

    function scrollToDeferred(): void {
        document.getElementById('deferred-by-budget')?.scrollIntoView({
            behavior: 'smooth',
            block: 'start',
        });
    }

    // ── FU-653: Dora's inferred suggestions ───────────────────────────
    // No dismissal state any more (2026-09-17) — the strip is either something
    // the household opted into or it isn't rendered at all, and a session-only
    // hide was a third state in between that nothing remembered.

    const visibleSuggestions = computed<InferredSuggestion[]>(
        () => detail.value?.inferred_suggestions ?? [],
    );

    async function onAddSuggestion(suggestion: InferredSuggestion) {
        addingSuggestionId.value = suggestion.stock_item_id;
        try {
            await api.addLineAsync(listId.value, {
                stock_item_id: suggestion.stock_item_id,
            });
            // Quiet — see `onRemoveLine`; adding a suggested line is an in-place
            // edit, not a navigation.
            await refreshAllQuietly();
            $q.notify({
                type: 'positive',
                message: `Added ${suggestion.name}.`,
            });
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: `Could not add ${suggestion.name}.`,
                    caption: toastCaption(err),
                });
            }
        } finally {
            addingSuggestionId.value = null;
        }
    }

    /** Every store the household has, for the row's "where do you plan to
     *  buy this" picker.
     *
     *  Deliberately *not* `storeOptionsFor` (below), which lists only stores
     *  already touching the line — right for "where did you buy it", since the
     *  answer is almost always one of them, and wrong here: planning to shop
     *  somewhere new is the whole point of the control, and a picker that can't
     *  name Aldi until you have already bought there is useless. R-016 lazy
     *  hydration, so an install that never opens this control pays nothing. */
    const storesStore = useStoresStore();
    const allStoreOptions = computed(() =>
        storesStore.stores.map((s) => ({ value: s.store_id, label: s.name })),
    );

    /** The store options for one line: every store, with the item's standing
     *  choice marked.
     *
     *  The empty option is **always "Any store"** (2026-09-17). It used to
     *  rename itself to "<resolved store> (default)", which is exactly the
     *  confusion the owner reported: the option that means *no store* was
     *  displaying a store's name, so "Any store" and "the usual store" looked
     *  like one setting with two names. The ladder still resolves a store for a
     *  line that hasn't chosen one — but a line added for an item with a usual
     *  store now carries it as a real `planned_store_id` (set server-side at
     *  add time), so the picker has something true to show instead of
     *  describing an inheritance. "(usual)" marks the standing choice in the
     *  list, where it is a fact about the item rather than about this line. */
    function plannedStoreOptionsFor(line: ShoppingListLine) {
        return allStoreOptions.value.map((o) => ({
            ...o,
            // `name` for the row's caption, `label` for the menu — see the
            // row's `storeLabel`.
            name: o.label,
            label: o.value === line.usual_store_id ? `${o.label} (usual)` : o.label,
        }));
    }

    /** Writes the row's target store. Optimistic with a rollback, like
     *  the other row mutations — and it refetches, because the store ladder is
     *  server-owned (R-003): changing this rung can move the line into a
     *  different section under Order-by → Store, and only the server knows
     *  what it resolved to. */
    async function onPlannedStoreChange(line: ShoppingListLine, value: string | null) {
        const previousId = line.planned_store_id;
        const previousName = line.planned_store_name;
        line.planned_store_id = value;
        line.planned_store_name =
            allStoreOptions.value.find((o) => o.value === value)?.label ?? null;
        try {
            await api.updateLineAsync(listId.value, line.line_id, value
                ? { planned_store_id: value }
                : { clear_planned_store: true });
            await refreshDetailQuietly();
        } catch (err) {
            line.planned_store_id = previousId;
            line.planned_store_name = previousName;
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not set the store.',
                    caption: toastCaption(err),
                });
            }
        }
    }

    async function onPickHint(lineId: string, preferredBuyId: string | null) {
        const line = detail.value?.lines.find((l) => l.line_id === lineId);
        if (!line) return;
        const previous = line.preferred_buy_id ?? null;
        // Toggle: re-picking the chosen hint clears it.
        const next = preferredBuyId === previous ? null : preferredBuyId;
        line.preferred_buy_id = next;
        try {
            if (next === null) {
                await api.updateLineAsync(listId.value, lineId, { clear_preferred_buy: true });
            } else {
                await api.updateLineAsync(listId.value, lineId, { preferred_buy_id: next });
            }
        } catch (err) {
            line.preferred_buy_id = previous;
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not set the hint.',
                    caption: toastCaption(err),
                });
            }
        }
    }

    async function onPickOffer(lineId: string, productId: string) {
        const line = detail.value?.lines.find((l) => l.line_id === lineId);
        if (!line) return;
        const previous = line.selected_product_id;
        // Toggle: clicking the chosen offer clears the selection (falls
        // back to "cheapest" auto-selection).
        const next = previous === productId ? null : productId;
        line.selected_product_id = next;
        // Sync `is_selected` flags on the in-memory offers so chips repaint
        // without waiting for the round-trip.
        for (const offer of line.offers) {
            offer.is_selected = offer.product_id === next;
        }
        try {
            if (next === null) {
                await api.updateLineAsync(listId.value, lineId, {
                    clear_selected_product: true,
                });
            } else {
                await api.updateLineAsync(listId.value, lineId, {
                    selected_product_id: next,
                });
            }
            // Picking an offer moves the line to the offer's store and prices
            // its estimate; un-picking puts the old figure back. Both are the
            // server's ladders (R-003), so re-read rather than guess.
            await refreshDetailQuietly();
        } catch (err) {
            line.selected_product_id = previous;
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not set offer.',
                    caption: toastCaption(err),
                });
            }
        }
    }

    // buy-verdict action for an in-shop line.
    // - `remove_from_list` targets THIS specific line (line-level intent).
    // - `mark_stocked` closes FU-454: routes through the shared
    //   `useBuyVerdictActions.markStocked` seam so the item flips to the
    //   Well-Stocked band and the verdict cache refreshes.
    // - `add_to_list` / `skip` / `none` are no-ops here — the line is
    //   already on this list; no meaningful mutation.
    const verdictActions = useBuyVerdictActions();
    async function onLineVerdictAction(
        line: ShoppingListLine,
        kind: 'add_to_list' | 'skip' | 'mark_stocked'
            | 'remove_from_list' | 'none',
    ) {
        if (kind === 'remove_from_list') {
            await onRemoveLine(line.line_id);
            return;
        }
        if (kind === 'mark_stocked' && line.stock_item_id) {
            await verdictActions.markStocked(line.stock_item_id);
            return;
        }
        // `add_to_list` / `skip` / `none` — no mutation. Silent by design.
    }

    async function onRemoveLine(lineId: string) {
        const before = detail.value?.lines.find((l) => l.line_id === lineId);

        // removing a product-only line (no
        // stock_item_id) prompts to also remove the *linked* stock-item
        // line, if one is also on this list. The user added the product
        // intent; removing it usually implies the stock-item placeholder
        // goes too, but they may want to keep the generic line.
        let alsoRemoveStockItemId: string | null = null;
        if (before && !before.stock_item_id && before.product_id) {
            const linkedStockItemId = productStore.products?.find(
                (p) => p.product_id === before.product_id,
            )?.linked_stock_item_id ?? null;
            if (linkedStockItemId) {
                const parentLine = detail.value?.lines.find(
                    (l) =>
                        l.stock_item_id === linkedStockItemId
                        && l.line_id !== lineId,
                );
                if (parentLine) {
                    // Yes → remove both; No/dismiss → just the product. The
                    // product line is going regardless (the user already
                    // clicked Remove); the prompt is purely about whether the
                    // generic stock-item placeholder rides along.
                    const removeBoth = await confirm({
                        title: 'Also remove the stock item?',
                        message: `${parentLine.stock_item_name} is on this list as its own line. Remove it too?`,
                        okLabel: 'Yes, remove both',
                        cancelLabel: 'No, just the product',
                    });
                    if (removeBoth) alsoRemoveStockItemId = linkedStockItemId;
                }
            }
        }

        try {
            await api.deleteLineAsync(listId.value, lineId);
            if (alsoRemoveStockItemId) {
                await api.removeByStockItemFromListAsync(
                    listId.value,
                    alsoRemoveStockItemId,
                );
                invalidateBuyVerdict(alsoRemoveStockItemId);
            }
            // The verdict ("already on a list") depends on list membership.
            if (before?.stock_item_id) invalidateBuyVerdict(before.stock_item_id);
            // Quiet, not `refreshAll()`: removing a line is an edit to the list
            // you are already looking at, not a navigation, so blanking `detail`
            // flashed the whole page through the skeleton on every remove
            // (owner, 2026-09-04 — same defect as the 08-29 shop-date report).
            await refreshAllQuietly();
            // UX-v2 §12 Q4: no undo toast — re-adding is one quick-add away,
            // and the app-wide undo posture is under review (FU-163).
            if (before) {
                $q.notify({
                    type: 'positive',
                    message: `Removed ${before.stock_item_name}.`,
                });
            }
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not remove line.',
                    caption: toastCaption(err),
                });
            }
        }
    }
</script>

<style scoped>
    /* The panel slab, the section header and the list slab are shared with the
       receipt face from `src/css/shoppingList.scss`; the rows own their own
       grid (`ShoppingListRow`, R-090). The page's `.q-mb-4` is repeated here
       because a scoped rule can't reach a child's markup. */
    .q-mb-4 {
        margin-bottom: var(--space-4);
    }
    .q-mb-5 {
        margin-bottom: var(--space-5);
    }
    /* Deferred-to-fit-budget rows. Wraps at a phone's width instead of
       printing the action over the reason. */
    .sld-deferred-row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: var(--space-2);
        padding: var(--space-2) var(--space-4);
    }
    .sld-deferred-row + .sld-deferred-row {
        border-top: 1px solid var(--divider);
    }
    .sld-deferred-row__main {
        min-width: 0;
        flex: 1 1 200px;
    }
    .sld-deferred-row__action {
        flex: 0 0 auto;
    }
    /* Dora's frozen reason is a whole sentence — "Would put the week $12 over;
       the tin can wait." It was inside a `q-chip`, and a chip does not wrap:
       the text simply ran out of its own pill and printed underneath the
       button beside it. Tinted text that wraps says the same thing and can be
       as long as the sentence it is. */
    .sld-deferred-reason {
        color: var(--semantic-warning-ink);
        margin-right: var(--space-1);
    }
    /* A section whose lines are all collected, folded to one line. */
    .sl-run-cleared {
        padding: var(--space-3) var(--space-4);
        border-radius: var(--radius-lg);
        background: var(--surface-sunken);
        color: var(--text-secondary);
    }
</style>
