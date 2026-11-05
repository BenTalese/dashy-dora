<template>
    <!-- Cook mode's ingredients panel + the B8 cook-session substitute picker
         (FU-942, split out of `RecipeCookMode.vue`). The swaps themselves are
         the page's (`v-model:swaps`): the finish flow and the spoken
         "Ingredients" answer read them too.

         ingredients grouped by base stock location.
         Stock-level chips intentionally removed mid-cook: the
         decision to cook this recipe is already made; visual noise
         about what's low/out only belongs on the finish surface
         (Chunk 1). The expansion stays for collapse, but the
         inner list is a card per location group rather than one
         long flat list. -->
    <q-expansion-item
        default-opened
        class="cook-section"
        header-class="cook-section__head"
    >
        <template #header>
            <q-item-section avatar>
                <q-icon :name="ICONS.ingredients" color="primary" />
            </q-item-section>
            <q-item-section class="cook-section__title">Ingredients</q-item-section>
        </template>
        <div class="q-pt-sm">
            <q-card
                v-for="group in ingredientGroups"
                :key="group.key"
                flat
                bordered
                class="q-mb-sm cook-card"
            >
                <q-card-section class="q-pb-xs">
                    <div class="row items-center q-gutter-xs">
                        <q-icon :name="ICONS.place" size="16px" class="dora-text-muted" />
                        <span class="text-subtitle2">{{ group.label }}</span>
                    </div>
                </q-card-section>
                <q-list dense>
                    <q-item
                        v-for="row in group.rows"
                        :key="row.ingredient.recipe_ingredient_id"
                        :class="{
                            'cook-row--highlighted': highlightedIngredientIds.has(row.ingredient.recipe_ingredient_id),
                            'ingredient-row--optional': row.ingredient.is_optional,
                        }"
                    >
                        <q-item-section>
                            <div class="row items-center q-gutter-xs no-wrap">
                                <span class="text-caption dora-text-muted ingredient-quantity">
                                    {{ displayQuantity(row.ingredient.quantity, row.ingredient.unit) }}
                                </span>
                                <!-- IMPL_PLAN_RECIPE_IMPORTER §Chunk 4:
                                     unlinked ingredients (stock_item_id === null) render
                                     as read-only raw_text — no substitute machinery, no
                                     swap chip, since there's no stock item to swap FROM.

                                     Owner feedback 2026-09-03: *"Remove 'unlinked' chip
                                     in cook mode for ingredients — we don't care at this
                                     point"*. Right: linkage is an authoring concern, and
                                     mid-cook the only question is what to put in the
                                     bowl. The chip also used a hardcoded `grey-6` /
                                     `grey-8` pair (R-002), so it leaves nothing behind. -->
                                <template v-if="row.ingredient.stock_item_id === null">
                                    <span class="ingredient-name">{{ row.ingredient.raw_text ?? 'Unlinked ingredient' }}</span>
                                </template>
                                <template v-else-if="sessionSwaps.has(row.ingredient.stock_item_id)">
                                    <!-- A filled chip, so the surface-grade secondary
                                         (D-020 is for marks, FU-652); white ink
                                         until a --text-on-secondary token exists (FU-671). -->
                                    <q-chip
                                        dense
                                        color="secondary"
                                        text-color="white"
                                        :icon="ICONS.swap_horiz"
                                    >
                                        {{ sessionSwaps.get(row.ingredient.stock_item_id)!.substituteName }}
                                    </q-chip>
                                    <span class="text-caption dora-text-muted">
                                        instead of {{ row.ingredient.label ?? row.ingredient.stock_item_name }}
                                    </span>
                                    <BaseButton
                                        variant="icon"
                                        size="sm"
                                        :icon="ICONS.undo"
                                        aria-label="Undo substitute"
                                        @click="clearSwap(row.ingredient.stock_item_id!)"
                                    >
                                        <BaseTooltip>Undo substitute</BaseTooltip>
                                    </BaseButton>
                                </template>
                                <template v-else>
                                    <span class="ingredient-name">{{ row.ingredient.label ?? row.ingredient.stock_item_name }}</span>
                                    <span
                                        v-if="row.ingredient.is_optional"
                                        class="text-caption dora-text-muted"
                                    >
                                        (optional)
                                    </span>
                                    <!-- Owner feedback 2026-09-01:
                                         *"Only show the substitute
                                         button for items that are
                                         genuinely in need of it (low
                                         or out)"*. A swap offered
                                         against a full jar is an
                                         affordance answering a
                                         question nobody asked, on
                                         every row of the list. -->
                                    <BaseButton
                                        v-if="needsSubstitute(row)"
                                        variant="icon"
                                        size="sm"
                                        :icon="ICONS.swap_horiz"
                                        :aria-label="`Use a substitute for ${row.ingredient.stock_item_name}`"
                                        @click="openSwapPicker(row.ingredient.stock_item_id!, row.ingredient.stock_item_name!)"
                                    >
                                        <BaseTooltip>Use a substitute for this cook</BaseTooltip>
                                    </BaseButton>
                                </template>
                            </div>
                            <!-- Owner 2026-10-15: the note read as a second quantity
                                 (same caption grey, same size). Italic behind a note
                                 glyph, so it reads as an aside about the ingredient. -->
                            <q-item-label
                                v-if="row.ingredient.notes"
                                caption
                                class="ingredient-note"
                            >
                                <q-icon :name="ICONS.notes" size="14px" />
                                <span>{{ row.ingredient.notes }}</span>
                            </q-item-label>
                            <!-- Owner feedback 2026-09-01: *"If there's
                                 a note or conversion info for a
                                 substitute can we display that
                                 meaningfully when a substitute is
                                 picked?"* The picker showed both and
                                 then threw them away on selection —
                                 which is the moment they start
                                 mattering, because you're now holding
                                 the other jar. -->
                            <q-item-label
                                v-if="swapHintFor(row.ingredient.stock_item_id)"
                                caption
                                class="ingredient-swaphint"
                            >
                                <q-icon :name="ICONS.swap_horiz" size="14px" />
                                {{ swapHintFor(row.ingredient.stock_item_id) }}
                            </q-item-label>
                        </q-item-section>
                    </q-item>
                </q-list>
            </q-card>
        </div>
    </q-expansion-item>

    <!-- cook-session substitute picker (temporary; never edits recipe).
         A sibling of the panel rather than inside it, so collapsing the
         panel can't take the dialog with it. -->
    <BaseDialog v-model="swapPickerOpen" :title="`Substitute for ${swapForName}`" closable card-style="min-width: 360px; max-width: 520px">
        <q-card-section v-if="loadingSwapOptions" class="text-center q-py-lg">
            <AppSpinner size="32px" />
        </q-card-section>
        <q-card-section v-else-if="swapOptions.length === 0" class="dora-text-muted">
            No substitutes recorded for {{ swapForName }}. Add some on the
            stock item's detail page.
        </q-card-section>
        <q-card-section v-else class="q-pt-sm">
            <div class="text-caption dora-text-muted q-mb-sm">
                Just for this cook.
            </div>
            <!-- when the substitute carries a note or ratio,
                 surface it next to the chip so the cook has the hint
                 in front of them at swap time. Mirrors the detail-page
                 layout so the same shape reads the same in both
                 places. Ratios are shown as "1 tsp → 1 tsp"; the
                 "from" side is the recipe's ingredient. -->
            <q-list separator>
                <q-item
                    v-for="opt in swapOptions"
                    :key="opt.stock_item_id"
                    clickable
                    @click="applySwap(opt)"
                >
                    <q-item-section>
                        <q-item-label>{{ opt.name }}</q-item-label>
                        <q-item-label
                            v-if="formatSubstituteRatio(opt)"
                            caption
                            class="dora-text-secondary"
                        >
                            {{ formatSubstituteRatio(opt) }}
                        </q-item-label>
                        <q-item-label v-if="opt.notes" caption class="dora-text-muted">
                            {{ opt.notes }}
                        </q-item-label>
                    </q-item-section>
                    <q-item-section side>
                        <q-icon :name="ICONS.arrow_forward" class="dora-text-muted" />
                    </q-item-section>
                </q-item>
            </q-list>
        </q-card-section>
        <template #actions>
            <BaseButton variant="ghost" label="Close" v-close-popup />
        </template>
    </BaseDialog>
</template>

<script lang="ts">
    // ── B8 — temporary, cook-session-only substitutions ─────────────────
    // Picking a substitute here applies ONLY to this cook: it never edits the
    // saved recipe. It changes what gets decremented / added-to-list on finish.
    // Keyed by the recipe ingredient's original stock_item_id.
    export type SessionSwap = {
        substituteId: string;
        substituteName: string;
        /** Owner feedback 2026-09-01 — the conversion ("1 tsp → 1 tsp") and
         *  the free-text note the substitute was recorded with. Both were
         *  shown in the picker and then dropped on selection, which is the
         *  moment they start mattering. Null when the substitute carries
         *  neither. */
        hint: string | null;
    };
</script>

<script lang="ts" setup>
    import { computed, ref } from 'vue';

    import AppSpinner from 'src/components/AppSpinner.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { cookQuantityLabel } from 'src/composables/useCookSteps';
    import { formatSubstituteRatio } from 'src/helpers/substituteRatio';
    import type { Recipe } from 'src/models/recipe';
    import type { StockItem } from 'src/models/stockItem';
    import type { Substitute } from 'src/models/stockItemDetail';
    import StockItemApiService from 'src/services/api/stockItemApiService';
    import { useLocationStore } from 'src/stores/locationStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { ICONS } from 'src/style/icons';

    const props = defineProps<{
        recipe: Recipe;
        /** Session headcount the quantities are rescaled to. */
        cookingFor: number;
        /** The current step's ingredients (`useCookSteps`). */
        highlightedIngredientIds: Set<string>;
    }>();

    const sessionSwaps = defineModel<Map<string, SessionSwap>>('swaps', { required: true });

    const locationStore = useLocationStore();
    const stockItemStore = useStockItemStore();
    const stockItemApi = new StockItemApiService();

    function displayQuantity(quantity: number | null | undefined, unit: string | null | undefined): string {
        return cookQuantityLabel(quantity, unit, props.recipe.servings ?? null, props.cookingFor);
    }

    // Resolve location_id → breadcrumb names using the locations tree.
    // The page warms the location store on mount so cook mode keeps working
    // even when the tree hasn't been opened yet.
    function breadcrumbFor(locationId: string): string[] {
        return locationStore.breadcrumb(locationId);
    }

    type IngredientRow = { ingredient: Recipe['ingredients'][number]; stockItem: StockItem | null };
    const ingredientRows = computed<IngredientRow[]>(() =>
        (props.recipe.ingredients ?? []).map((ingredient) => ({
            ingredient,
            stockItem: ingredient.stock_item_id
                ? stockItemStore.byId.get(ingredient.stock_item_id) ?? null
                : null,
        })),
    );

    // group ingredients by their *base* stock location (the
    // top-level node of the breadcrumb). Sub-areas collapse into their parent
    // — "Pantry > Spice Rack" reads as "Pantry" — keeping the mid-cook view
    // calm. Ingredients with no location land in a final "No location" group.
    //
    // when the recipe defines named sections, sections win as
    // the top-level grouping (their semantic intent — "this is the sauce" —
    // is stronger than where the ingredient lives). Falls back to location
    // grouping for flat recipes so existing recipes render unchanged.
    type IngredientGroup = { key: string; label: string; rows: IngredientRow[] };
    const ingredientGroups = computed<IngredientGroup[]>(() => {
        const sections = props.recipe.sections ?? [];
        if (sections.length > 0) {
            // Section grouping. Order follows `sequence` (server already
            // sorted); unsectioned ingredients drop into "Main" at the end.
            const sectionById = new Map(sections.map((s) => [s.section_id, s]));
            const groups = new Map<string, IngredientGroup>();
            const orderedKeys: string[] = [];
            const ensure = (key: string, label: string) => {
                if (!groups.has(key)) {
                    groups.set(key, { key, label, rows: [] });
                    orderedKeys.push(key);
                }
                return groups.get(key)!;
            };
            for (const s of sections) {
                ensure(`s:${s.section_id}`, s.name);
            }
            for (const row of ingredientRows.value) {
                const sid = row.ingredient.section_id;
                const sec = sid ? sectionById.get(sid) : null;
                if (sec) {
                    ensure(`s:${sec.section_id}`, sec.name).rows.push(row);
                } else {
                    ensure('__main__', 'Main').rows.push(row);
                }
            }
            return orderedKeys
                .map((k) => groups.get(k)!)
                .filter((g) => g.rows.length > 0);
        }
        const groups = new Map<string, IngredientGroup>();
        const orderedKeys: string[] = [];
        for (const row of ingredientRows.value) {
            const locId = row.ingredient.stock_location_id;
            let key: string;
            let label: string;
            if (locId) {
                const breadcrumb = breadcrumbFor(locId);
                label = breadcrumb[0] ?? row.ingredient.stock_location_name ?? 'Other';
                key = label;
            } else {
                key = '__none__';
                label = 'No location';
            }
            if (!groups.has(key)) {
                groups.set(key, { key, label, rows: [] });
                orderedKeys.push(key);
            }
            groups.get(key)!.rows.push(row);
        }
        // Push the "No location" bucket to the bottom so the cook reads the
        // located groups in order first.
        const ordered = orderedKeys.map((k) => groups.get(k)!).filter(Boolean);
        ordered.sort((a, b) => {
            if (a.key === '__none__') return 1;
            if (b.key === '__none__') return -1;
            return 0;
        });
        return ordered;
    });

    const swapPickerOpen = ref(false);
    const swapForId = ref<string | null>(null);
    const swapForName = ref('');
    const swapOptions = ref<Substitute[]>([]);
    const loadingSwapOptions = ref(false);

    async function openSwapPicker(stockItemId: string, name: string) {
        swapForId.value = stockItemId;
        swapForName.value = name;
        swapOptions.value = [];
        swapPickerOpen.value = true;
        loadingSwapOptions.value = true;
        try {
            swapOptions.value = await stockItemApi.getSubstitutesAsync(stockItemId);
        } catch {
            swapOptions.value = [];
        } finally {
            loadingSwapOptions.value = false;
        }
    }
    function applySwap(substitute: Substitute) {
        if (!swapForId.value) return;
        const ratio = formatSubstituteRatio(substitute);
        const note = substitute.notes?.trim() || null;
        // A new Map rather than mutating the bound one in place — the swaps
        // are the page's (v-model), and the reassignment is what tells it.
        const next = new Map(sessionSwaps.value);
        next.set(swapForId.value, {
            substituteId: substitute.stock_item_id,
            substituteName: substitute.name,
            hint: [ratio, note].filter(Boolean).join(' · ') || null,
        });
        sessionSwaps.value = next;
        swapPickerOpen.value = false;
    }

    /** The swapped-in substitute's conversion + note, for the ingredient row.
     *  Keyed by the *original* ingredient's stock item, which is how
     *  `sessionSwaps` is keyed. */
    function swapHintFor(stockItemId: string | null): string | null {
        if (!stockItemId) return null;
        return sessionSwaps.value.get(stockItemId)?.hint ?? null;
    }

    /** Owner feedback 2026-09-01 — a substitute is worth offering when the
     *  thing you'd substitute *for* is low or out. Anything already stocked
     *  gets no button: the swap is still reachable from the stock item, and
     *  a row per ingredient offering to replace a full jar is noise on the
     *  one screen that should be calm.
     *
     *  An ingredient whose stock item hasn't loaded (or isn't linked) reads as
     *  "no reason to think it needs one" — the same conservative default the
     *  rest of the page takes. */
    function needsSubstitute(row: IngredientRow): boolean {
        return row.stockItem?.needs_restock === true;
    }
    function clearSwap(stockItemId: string) {
        const next = new Map(sessionSwaps.value);
        next.delete(stockItemId);
        sessionSwaps.value = next;
    }

    /** The page's keyboard shortcuts stand down while the picker is open —
     *  the dialog owns Escape and the arrows then (04-R7). */
    const pickerOpen = computed(() => swapPickerOpen.value);
    defineExpose({ pickerOpen });
</script>

<style scoped lang="scss">
    @use '../../css/cookSections';

    .ingredient-quantity {
        min-width: 64px;
    }
    .ingredient-name {
        font-weight: 500;
    }
    // Cookbook revision §1.9 — optional ingredients render dimmed so the
    // eye lands on what's required to cook.
    .ingredient-row--optional {
        opacity: 0.65;
    }
    // The ingredient's own note — an italic aside behind a note glyph.
    .ingredient-note {
        display: flex;
        align-items: baseline;
        gap: var(--space-1);
        font-style: italic;
        color: var(--text-secondary);
        .q-icon {
            align-self: center;
            flex: 0 0 auto;
        }
    }
    // The swapped-in substitute's conversion + note, under the row it applies
    // to. Secondary ink rather than muted: it is an instruction you act on,
    // not a footnote.
    .ingredient-swaphint {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        color: var(--text-secondary);
    }
</style>
