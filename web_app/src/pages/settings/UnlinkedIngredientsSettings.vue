<template>
    <!-- IMPL_PLAN_RECIPE_IMPORTER §Chunk 6 — bulk-linker for unlinked
         recipe ingredients. Chunk 5's paste importer produces
         `stock_item_id=null` rows when RapidFuzz can't match; this page
         is where the user resolves them in one sitting instead of
         page-by-page editing. Grouped by normalised raw_text
         (server-owned) with count + affected-recipe list; picking a
         StockItem links every row in the group with one request. -->
    <div class="settings-page q-gutter-md">
        <SettingsPageHeader
            title="Unlinked ingredients"
            description="Recipe ingredients that couldn't be matched to a stock item when you imported them via the recipe importer. Linking these ingredients allows Dora to determine the cookable state of a recipe."
            :icon="ICONS.link"
        />

        <div v-if="loading" class="row items-center q-gutter-sm">
            <q-spinner-dots size="24px" color="primary" />
            <span class="text-caption dora-text-muted">Loading…</span>
        </div>

        <div v-else-if="groups.length === 0" class="settings-card">
            <p class="settings-card__empty">
                No unlinked ingredients right now. Every recipe ingredient is
                linked to a stock item.
            </p>
        </div>

        <!-- Owner 2026-09-03: was a bare `q-card flat bordered` wrapping a
             `q-list`, whose side sections stay beside the label at every
             width — on a phone that squeezed the picker into a sliver and
             overlapped the buttons. `.settings-card__row` is a flex row that
             stacks below 600px, and the panel now speaks the app's card
             language rather than Quasar's default. -->
        <div v-else class="settings-card">
            <div class="settings-card__rows">
                <div
                    v-for="group in groups"
                    :key="group.raw_text"
                    class="settings-card__row unlinked-row"
                >
                    <div class="settings-card__row-main">
                        <span class="settings-card__row-name">{{ group.raw_text }}</span>
                        <span class="settings-card__row-meta">
                            Used in {{ group.count }}
                            recipe<template v-if="group.count !== 1">s</template>
                        </span>
                    </div>
                    <div class="settings-card__row-aux unlinked-row__aux">
                        <BaseSelect
                            v-model="picks[group.raw_text]"
                            :options="stockItemOptions(group.raw_text)"
                            emit-value
                            map-options
                            use-input
                            fill-input
                            hide-selected
                            input-debounce="80"
                            label="Link to stock item"
                            class="unlinked-row__picker"
                            @filter="(value: string, update: FilterUpdate) => onFilter(group.raw_text, value, update)"
                        >
                            <template #no-option>
                                <q-item>
                                    <q-item-section class="text-caption dora-text-muted">
                                        No matches. Use "Create new".
                                    </q-item-section>
                                </q-item>
                            </template>
                        </BaseSelect>
                        <BaseButton
                            variant="primary"
                            :label="linkingKey === group.raw_text ? 'Linking…' : 'Link'"
                            :loading="linkingKey === group.raw_text"
                            :disable="!picks[group.raw_text]"
                            @click="onLink(group)"
                        />
                        <BaseButton
                            variant="ghost"
                            label="Create new"
                            @click="onCreateNew(group)"
                        />
                    </div>
                </div>
            </div>
        </div>

        <!-- "Create new" opens the app's real add-item dialog seeded with the
             raw text, rather than silently POSTing a name + a guessed level.
             The silent path gave a bare "Could not create + link" toast for
             every server-side rejection — including the common one, a stock
             item of that name already existing (owner 2026-09-03). The dialog
             shows the field error and lets the name be adjusted. -->
        <CreateStockItemDialog
            v-model="createDialogOpen"
            :prefill="createPrefill"
            @created="onCreatedStockItem"
        />
    </div>
</template>

<script setup lang="ts">
    /**
     * IMPL_PLAN_RECIPE_IMPORTER §Chunk 6 — the whole page is a
     * one-request-per-group workflow:
     *
     *   1. GET /api/recipes/unlinked-ingredients → grouped rows (the
     *      server owns the normalisation, so what the SPA calls "one
     *      group" is exactly what the linker updates).
     *   2. User picks a StockItem from the autocomplete (or creates
     *      one seeded from the raw_text).
     *   3. POST /api/recipes/unlinked-ingredients/bulk-link with the
     *      raw_text + stock_item_id → server atomically flips the FK
     *      on every matching row. Cookability re-derives on the next
     *      recipe read (R-003 — server-owned).
     *   4. Refresh the list so the linked group disappears.
     *
     * Charter P1 Effortless: no per-recipe walkthrough. Charter P12
     * No-invent: only shows the actual unlinked set — nothing is
     * fabricated for the user to link.
     */
    import { computed, onMounted, reactive, ref, watch } from 'vue';
    import { useQuasar } from 'quasar';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import CreateStockItemDialog from 'src/components/stock/CreateStockItemDialog.vue';
    import type { CreateStockItemPrefill } from 'src/components/stock/createStockItemPrefill';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import { ICONS } from 'src/style/icons';
    import RecipeApiService, {
        type UnlinkedIngredientGroup,
    } from 'src/services/api/recipeApiService';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { useUnlinkedIngredientsStore } from 'src/stores/unlinkedIngredientsStore';
    import { storeToRefs } from 'pinia';

    const $q = useQuasar();
    const recipeApi = new RecipeApiService();

    const stockItemStore = useStockItemStore();
    const { stockItems } = storeToRefs(stockItemStore);
    // Still hydrated on mount: CreateStockItemDialog reads the level list.
    const stockLevelStore = useStockLevelStore();
    const unlinkedStore = useUnlinkedIngredientsStore();

    const groups = ref<UnlinkedIngredientGroup[]>([]);
    const loading = ref(false);
    const linkingKey = ref<string | null>(null);

    // Keyed by group.raw_text — the picker's selected stock_item_id.
    const picks = reactive<Record<string, string | null>>({});
    // Per-group q-select filter text (autocomplete input). We keep
    // an independent filter buffer per group so typing in one row
    // doesn't reset another row's options.
    const filters = reactive<Record<string, string>>({});

    const stockItemsSorted = computed(() =>
        [...stockItems.value].sort((a, b) => a.name.localeCompare(b.name)),
    );

    function stockItemOptions(rawText: string) {
        const q = (filters[rawText] ?? '').trim().toLowerCase();
        const src = stockItemsSorted.value;
        const filtered = q
            ? src.filter((si) => si.name.toLowerCase().includes(q))
            : src;
        return filtered.slice(0, 50).map((si) => ({
            label: si.name,
            value: si.stock_item_id,
        }));
    }

    type FilterUpdate = (cb: () => void) => void;
    function onFilter(
        rawText: string,
        value: string,
        update: FilterUpdate,
    ) {
        // Quasar's use-input picker hands us (value, update) — value is
        // the current text, update is a commit callback so the filtered
        // options render in the same tick as the input keys. We store
        // the value keyed by group and let stockItemOptions() re-derive.
        update(() => {
            filters[rawText] = value;
        });
    }

    // The store's stockItems can start empty on first mount; hydrate.
    onMounted(async () => {
        await Promise.all([
            stockItemStore.ensureLoadedAsync(),
            stockLevelStore.ensureLoadedAsync(),
            refresh(),
        ]);
    });

    // If the stock-item list refreshes mid-page (rare — e.g. after
    // "Create new" adds one), re-derive the picker options.
    watch(stockItems, () => { /* computed picks it up */ });

    async function refresh() {
        loading.value = true;
        try {
            const dto = await recipeApi.getUnlinkedIngredientsAsync();
            groups.value = dto.unlinked;
            // Keep the sidebar attention badge in sync (reuses this fetch
            // rather than a second round-trip).
            unlinkedStore.setCount(dto.unlinked.length);
        } catch (err) {
            console.warn('Failed to load unlinked ingredients', err);
            $q.notify({
                type: 'negative',
                message: 'Could not load unlinked ingredients.',
            });
        } finally {
            loading.value = false;
        }
    }

    async function onLink(group: UnlinkedIngredientGroup) {
        const stockItemId = picks[group.raw_text];
        if (!stockItemId) return;
        linkingKey.value = group.raw_text;
        try {
            const result = await recipeApi.bulkLinkUnlinkedIngredientsAsync(
                group.raw_text,
                stockItemId,
            );
            $q.notify({
                type: 'positive',
                message:
                    result.linked_count === 1
                        ? `Linked "${group.raw_text}" in 1 recipe.`
                        : `Linked "${group.raw_text}" in ${result.linked_count} recipes.`,
            });
            delete picks[group.raw_text];
            delete filters[group.raw_text];
            await refresh();
        } catch (err) {
            console.warn('Bulk-link failed', err);
            $q.notify({
                type: 'negative',
                message: 'Could not link. Try again in a moment.',
            });
        } finally {
            linkingKey.value = null;
        }
    }

    // ── "Create new" → the app's add-item dialog, prefilled ───────────
    const createDialogOpen = ref(false);
    const createPrefill = ref<CreateStockItemPrefill | null>(null);
    /** The group the open dialog was launched from, so the new item can be
     *  linked back to it once the dialog reports a successful create. */
    const createForGroup = ref<UnlinkedIngredientGroup | null>(null);

    function onCreateNew(group: UnlinkedIngredientGroup) {
        const name = group.raw_text.trim();
        if (!name) return;
        createForGroup.value = group;
        createPrefill.value = { name };
        createDialogOpen.value = true;
    }

    async function onCreatedStockItem(stockItemId: string) {
        const group = createForGroup.value;
        createForGroup.value = null;
        createPrefill.value = null;
        if (!group) return;
        // Link straight away — creating the item from this page only ever
        // means "this is what that ingredient is".
        linkingKey.value = group.raw_text;
        try {
            const result = await recipeApi.bulkLinkUnlinkedIngredientsAsync(
                group.raw_text,
                stockItemId,
            );
            $q.notify({
                type: 'positive',
                message:
                    result.linked_count === 1
                        ? `Linked "${group.raw_text}" in 1 recipe.`
                        : `Linked "${group.raw_text}" in ${result.linked_count} recipes.`,
            });
            delete picks[group.raw_text];
            delete filters[group.raw_text];
            await refresh();
        } catch (err) {
            console.warn('Link after create failed', err);
            $q.notify({
                type: 'negative',
                message: 'Item created, but it could not be linked. Pick it above and press Link.',
            });
        } finally {
            linkingKey.value = null;
        }
    }
</script>

<style scoped lang="scss">
    /* The picker is the widest thing in the row, so it owns the growth and
       the two buttons stay their natural size. Below 600px the shared
       `.settings-card__row-aux` rule stacks the whole group to full width. */
    .unlinked-row__aux {
        flex-wrap: wrap;
        justify-content: flex-end;
        max-width: 60%;
    }
    .unlinked-row__picker {
        flex: 1 1 240px;
        min-width: 0;
        max-width: 360px;
    }
    @media (max-width: 599px) {
        .unlinked-row__aux {
            max-width: 100%;
        }
        .unlinked-row__picker {
            flex-basis: 100%;
            max-width: 100%;
        }
    }
</style>
