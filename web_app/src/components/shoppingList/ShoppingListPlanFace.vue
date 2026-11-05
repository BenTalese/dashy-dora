<template>
    <!-- Budget-aware trim banner (money-gated + budget-set).
         Fires when the projected active-list total exceeds the
         user's period-remaining budget for this list's shop
         date. Never mutates on load; every mutation is a user
         tap. -->
    <q-banner
        v-if="trimBanner.visible"
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
        v-if="trimBanner.state === 'previewed' && trimBanner.previewLines.length > 0"
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

    <!-- FU-653 — Dora's suggestions, above the list and
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
        v-if="visibleSuggestions.length > 0"
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

    <!-- The "Order by" bar used to sit here, and a second copy
         of it inside `ShoppingListRunFace`. Both moved into the
         overview card's control row: it is one view preference,
         so it should be one control, and two copies were free
         to drift. -->
    <template v-else>
        <div
            v-for="section in lineSections"
            :key="section.key"
            class="q-mb-md"
        >
            <!-- Section headers read as headers now: the old
                 muted `text-subtitle2` floated above a bordered
                 box and looked like an afterthought rather than
                 the thing structuring the page. -->
            <div v-if="section.label" class="sl-section__head">
                <q-icon :name="sectionIcon" size="16px" />
                <span class="sl-section__title">{{ section.label }}</span>
                <span class="sl-section__count">{{ section.lines.length }}</span>
            </div>
            <!-- One soft slab, not `q-list bordered separator`
                 inside a bordered page. The rows own their own
                 dividers, inset to the content column. -->
            <div class="sl-list">
                <ShoppingListPlanRow
                    v-for="line in section.lines"
                    :key="line.line_id"
                    :line="line"
                    :line-done="detail?.status === 'done'"
                    :can-reorder="canReorder"
                    :is-first="isFirstLine(line)"
                    :is-last="isLastLine(line)"
                    :focused="focusedLineId === line.line_id"
                    :nested="isNestedChild(line)"
                    :product-only="isProductOnly(line)"
                    :price="priceForLine(line)"
                    :store-options="plannedStoreOptionsFor(line)"
                    :class="lineDnd.bind(line).rowClass"
                    v-bind="{
                        ...lineDnd.bind(line).handleProps,
                        ...lineDnd.bind(line).rowProps,
                    }"
                    @move="moveLine(line, $event)"
                    @remove="onRemoveLine(line.line_id)"
                    @adjust-quantity="onAdjustQuantity(line, $event)"
                    @set-quantity="setLineQuantity(line, $event)"
                    @planned-store="onPlannedStoreChange(line, $event)"
                    @pick-offer="onPickOffer(line.line_id, $event)"
                    @pick-hint="onPickHint(line.line_id, $event)"
                    @verdict-action="onLineVerdictAction(line, $event)"
                />
            </div>
        </div>
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
     * The plan face — the list as it is written, before anyone goes shopping.
     *
     * Extracted from `ShoppingListDetail.vue` (FU-780), following the shape of
     * `ShoppingListRunFace`: the page decides which face is showing and owns
     * the view preference (`mode`) and keyboard focus; this face owns every
     * affordance that exists to *curate* a list — the trim-to-budget banner,
     * Dora's suggestions, the sectioned rows with their drag, arrows, delete,
     * quantity, store, offer and buy-hint controls, and the deferred-to-fit
     * section. None of it is a thing you do while holding a trolley, so none
     * of it is on the other two faces.
     *
     * The list itself, its re-reads and the trim state come from
     * `useShoppingListDetail()` rather than ~20 props and emits: the trim
     * banner's state has to survive this face being unmounted mid-shop, and
     * the row mutations are optimistic writes onto the page's own `detail`.
     */
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import ShoppingListPlanRow from 'src/components/shoppingList/ShoppingListPlanRow.vue';
    import { ICONS } from 'src/style/icons';
    import {
        PLAN_SECTION_MODES, useLineSections, isNestedChild,
        isProductOnly, sectionIconFor, type SectionMode,
    } from 'src/composables/useLineSections';
    import { invalidateBuyVerdict } from 'src/composables/useBuyVerdict';
    import { useBuyVerdictActions } from 'src/composables/useBuyVerdictActions';
    import { useConfirm } from 'src/composables/useConfirm';
    import { useDragDropList } from 'src/composables/useDragDropList';
    import { formatMoney } from 'src/composables/useMoney';
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
        setLineQuantity, onAdjustQuantity,
        addingBackLineIds, addingSuggestionId,
    } = useShoppingListDetail();

    const modeRef = computed(() => props.mode);

    function fmtMoney(v: number | null | undefined): string {
        return formatMoney(v ?? 0);
    }

    // Sectioning. On the plan face ticked lines stay put and dim.
    // `effectiveMode` falls back to ungrouped when the stored preference points
    // at a field this list doesn't populate. `availableModes` is not read here:
    // the overview card owns the "Group by" control and resolves availability
    // for whichever face is showing. This instance only sections. (The page
    // keeps a twin with the same options for its keyboard-focus order.)
    const {
        sections: lineSections,
        orderedLines: sectionOrderedLines,
        effectiveMode,
    } = useLineSections(baseLines, modeRef, {
        hideTicked: computed(() => detail.value?.status === 'shopping'),
        // Plan face: store + ungrouped only. The run face renders through
        // `ShoppingListRunFace`, which keeps all four.
        allowedModes: PLAN_SECTION_MODES,
    });

    const sectionIcon = computed(() => sectionIconFor(effectiveMode.value));

    // ── Drag-to-reorder ───────────────────────────────────────────────
    // Reordering only means something when grouping is off: in every other
    // mode the section order is derived from a field, so dragging a row would
    // either be ignored or silently rewrite a sequence the user can't see.
    // `effectiveMode` rather than `groupBy`, so a stored preference pointing at
    // an empty field (which falls back to ungrouped) still gets the affordance.
    const canReorder = computed(() =>
        !!detail.value
            && detail.value.status !== 'done'
            && detail.value.status !== 'shopping'
            && effectiveMode.value === 'none'
    );

    // R-022 — whole-row DnD via `useDragDropList`. `canDragStart` is gated
    // on `canReorder` (list not done/shopping, no grouping, not in bulk
    // mode), so the `draggable` attribute reactively turns off the
    // browser's drag affordance when reorder isn't allowed. The drop
    // effect mirrors the historical insert-at-target's-slot pattern
    // (fixed the off-by-one in P6-01 Chunk 6 / feedback L414).
    const lineDnd = useDragDropList<ShoppingListLine>({
        mime: 'application/x-dora-shopping-line',
        getId: (line) => line.line_id,
        canDragStart: () => canReorder.value,
        onDrop: ({ id: draggedId }, { id: targetLineId }) => {
            if (!detail.value) return;
            const lines = detail.value.lines;
            const ids = lines.map((l) => l.line_id);
            const fromIdx = ids.indexOf(draggedId);
            const toIdx = ids.indexOf(targetLineId);
            if (fromIdx < 0 || toIdx < 0) return;
            ids.splice(fromIdx, 1);
            ids.splice(toIdx, 0, draggedId);
            applyLineOrder(ids);
        },
    });

    /** Optimistically apply a new line order and persist it. Shared by the
     *  drag handler and the up/down arrows so there is one definition of what
     *  reordering does — and one place a failure reloads canonical state. */
    function applyLineOrder(ids: string[]): void {
        if (!detail.value) return;
        const lookup = new Map(detail.value.lines.map((l) => [l.line_id, l]));
        detail.value.lines = ids
            .map((id, idx) => {
                const line = lookup.get(id);
                if (!line) return null;
                line.sequence = idx;
                return line;
            })
            .filter((l): l is NonNullable<typeof l> => l !== null);

        void (async () => {
            try {
                await api.reorderLinesAsync(listId.value, ids);
            } catch (err) {
                await refreshDetailQuietly();
                if (!isAlreadyNotified(err)) {
                    $q.notify({
                        type: 'negative',
                        message: 'Could not reorder.',
                        caption: toastCaption(err),
                    });
                }
            }
        })();
    }

    // Arrow reordering. Moves within the *visible* ungrouped run rather than the
    // raw `detail.lines` array, so a deferred-by-budget line sitting between
    // two visible rows can't swallow a press and make the row appear stuck.
    function isFirstLine(line: ShoppingListLine): boolean {
        return sectionOrderedLines.value[0]?.line_id === line.line_id;
    }
    function isLastLine(line: ShoppingListLine): boolean {
        return sectionOrderedLines.value.at(-1)?.line_id === line.line_id;
    }
    function moveLine(line: ShoppingListLine, delta: -1 | 1): void {
        const visible = sectionOrderedLines.value;
        const from = visible.findIndex((l) => l.line_id === line.line_id);
        const to = from + delta;
        if (from < 0 || to < 0 || to >= visible.length) return;
        // Reorder the visible run, then splice it back over the full line
        // order so hidden lines keep their relative positions.
        const movedIds = visible.map((l) => l.line_id);
        movedIds.splice(from, 1);
        movedIds.splice(to, 0, line.line_id);
        const visibleSet = new Set(movedIds);
        let cursor = 0;
        const ids = (detail.value?.lines ?? []).map((l) =>
            visibleSet.has(l.line_id) ? movedIds[cursor++]! : l.line_id
        );
        applyLineOrder(ids);
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

    function priceForLine(line: ShoppingListLine): number {
        return priceOfLine(line);
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

    /** Every store the household has, for the plan face's "where do you plan to
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

    /** Writes the plan face's target store. Optimistic with a rollback, like
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
       run face from `src/css/shoppingList.scss`; the rows own their own grid
       (`ShoppingListPlanRow`, R-090). The page's `.q-mb-4` is repeated here
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
    /* R-022 — DnD affordances live in src/css/dnd.scss
       (.dora-dnd-row / --dragging / --drop-over). The decorative
       handle icon-section is non-interactive (whole-row mode), so
       the grab/grabbing cursors aren't needed here. */
</style>
