<template>
    <div class="settings-page q-gutter-md">
        <SettingsPageHeader
            title="Nutrition matching"
            description="Stock items that aren't linked to a food yet. Dora suggests a match from the installed food data where it can."
        />

        <div v-if="loading" class="row items-center q-gutter-sm">
            <q-spinner-dots size="24px" color="primary" />
            <span class="text-caption dora-text-muted">Loading…</span>
        </div>

        <template v-else>
            <!-- The matcher is local-catalogue-only by design (it runs over the
                 whole pantry, so a live lookup per item isn't viable). With no
                 food data installed it therefore suggests nothing — which looks
                 exactly like a broken feature unless we say otherwise. Checked
                 before the "nothing to match" line below, because that line is
                 the lie in this state. -->
            <div v-if="catalogueSize === 0" class="settings-card match-notice">
                <q-icon :name="ICONS.info_outline" size="22px" class="match-notice__icon" />
                <div class="match-notice__body">
                    <div class="text-weight-medium dora-text-primary">
                        No offline food data is installed, so Dora can't suggest
                        matches.
                    </div>
                    <div class="text-caption dora-text-secondary q-mt-xs">
                        Suggestions need the food database downloaded on this
                        install.
                        <template v-if="!isAdmin">
                            Ask an admin to set it up under Settings → Admin →
                            System → Nutrition.
                        </template>
                    </div>
                </div>
                <BaseButton
                    v-if="isAdmin"
                    variant="primary"
                    label="Set up food data"
                    to="/settings/admin/system/nutrition"
                    class="match-notice__action"
                />
            </div>

            <div v-else-if="items.length === 0" class="settings-card">
                <p class="settings-card__empty">
                    Every stock item is either linked to a food or set aside.
                    Nothing to match.
                </p>
            </div>

            <!-- One tap for the whole confident set. Only near-certain matches
                 are swept up: the weaker ones are exactly the rows that need a
                 human to look, and bulk-accepting those is how a pantry fills
                 up with quietly wrong calories. -->
            <div v-if="strongCount > 0" class="settings-card">
                <div class="settings-card__row">
                    <div class="settings-card__row-main">
                        <div class="dora-text-primary text-weight-medium">
                            {{ strongCount }} confident
                            match<template v-if="strongCount !== 1">es</template>
                            ready
                        </div>
                        <div class="dora-text-muted text-caption">
                            Names that match the food data almost exactly. Accept
                            them together, or go through them one at a time below.
                        </div>
                    </div>
                    <div class="settings-card__row-aux">
                        <BaseButton
                            variant="primary"
                            :label="acceptingAll ? 'Accepting…' : `Accept all ${strongCount}`"
                            :loading="acceptingAll"
                            :disable="busy"
                            @click="onAcceptAll"
                        />
                    </div>
                </div>
            </div>

            <div v-if="items.length" class="settings-card">
                <div class="settings-card__rows">
                    <div
                        v-for="item in items"
                        :key="item.stock_item_id"
                        class="settings-card__row"
                    >
                        <div class="settings-card__row-main">
                            <span class="settings-card__row-name">{{ item.name }}</span>
                            <span v-if="item.suggestion" class="settings-card__row-meta">
                                <q-badge
                                    class="match-tag"
                                    :label="item.suggestion.is_strong
                                        ? 'Suggested' : 'Possible match'"
                                />
                                <span class="dora-text-primary q-ml-xs">
                                    {{ item.suggestion.name }}
                                </span>
                                <span class="dora-text-muted">
                                    ·
                                    <template v-if="item.suggestion.kcal_per_100g !== null">
                                        {{ Math.round(item.suggestion.kcal_per_100g) }} kcal / 100g ·
                                    </template>
                                    {{ item.suggestion.source_label }}
                                </span>
                            </span>
                        </div>

                        <!-- Owner 2026-09-03: "Search" and "Not a food" were
                             `ghost`, which on this row read as two more lines
                             of prose rather than the two actions that resolve
                             it. They are `secondary` now — still subordinate to
                             "Use this", but unmistakably controls. -->
                        <div class="settings-card__row-aux">
                            <BaseButton
                                v-if="item.suggestion"
                                variant="primary"
                                dense
                                size="sm"
                                label="Use this"
                                :disable="busy"
                                :loading="workingId === item.stock_item_id"
                                @click="onAccept(item)"
                            />
                            <BaseButton
                                variant="secondary"
                                dense
                                size="sm"
                                label="Search"
                                :disable="busy"
                                @click="onSearch(item)"
                            />
                            <BaseButton
                                variant="secondary"
                                dense
                                size="sm"
                                label="Not a food"
                                :disable="busy"
                                @click="onIgnore(item)"
                            >
                                <BaseTooltip>
                                    Stop asking about {{ item.name }}
                                </BaseTooltip>
                            </BaseButton>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Set-aside items are hidden by default but never unreachable:
                 waving something off by mistake has to be undoable, and a
                 permanent flag with no way back is a trap. -->
            <div v-if="ignoredCount > 0">
                <BaseButton
                    variant="secondary"
                    dense
                    size="sm"
                    :label="showIgnored
                        ? 'Hide set-aside items'
                        : `Show ${ignoredCount} set-aside item${ignoredCount === 1 ? '' : 's'}`"
                    :disable="busy"
                    @click="onToggleIgnored"
                />
                <div v-if="showIgnored" class="settings-card q-mt-sm">
                    <div class="settings-card__rows">
                        <div
                            v-for="item in ignoredItems"
                            :key="item.stock_item_id"
                            class="settings-card__row"
                        >
                            <div class="settings-card__row-main">
                                <span class="settings-card__row-name dora-text-muted">
                                    {{ item.name }}
                                </span>
                            </div>
                            <div class="settings-card__row-aux">
                                <BaseButton
                                    variant="secondary"
                                    dense
                                    size="sm"
                                    label="Track again"
                                    :disable="busy"
                                    @click="onUnignore(item)"
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </template>

        <NutritionFoodPicker
            v-if="searchingItem"
            v-model="pickerOpen"
            :item-name="searchingItem.name"
            @picked="onPicked"
        />
    </div>
</template>

<script setup lang="ts">
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    /**
     * Bulk nutrition matching — the "unlinked ingredients" of complex mode.
     *
     * Owner ask (2026-08-15): manual setup is the thing people won't do. In
     * complex mode every stock item needs a food link before any calorie
     * number exists, and doing that through the per-item picker means opening
     * a dialog once per pantry item. This page does the searching up front and
     * turns the job into a column of one-tap decisions.
     *
     * Three things it must not do, all learned from the same principle:
     *
     * 1. **Never save a guess.** Every suggestion is labelled and inert until
     *    accepted (P12 No-invent). The bulk verb only touches near-certain
     *    matches; anything needing judgement keeps needing a tap.
     * 2. **Never trap the user.** "Not a food" is reversible from the
     *    set-aside list at the bottom.
     * 3. **Never re-derive server facts.** Counts, ordering, scoring and the
     *    confident/possible band all arrive from the API (R-003) — this file
     *    renders them and nothing else.
     */
    import { onMounted, ref } from 'vue';
    import { storeToRefs } from 'pinia';
    import { useQuasar } from 'quasar';
    import BaseButton from 'src/components/BaseButton.vue';
    import NutritionFoodPicker from 'src/components/stock/NutritionFoodPicker.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import { ICONS } from 'src/style/icons';
    import NutritionApiService, {
        type UnmatchedStockItem,
    } from 'src/services/api/nutritionApiService';
    import { useAuthStore } from 'src/stores/authStore';
    import { useNutritionMatchingStore } from 'src/stores/nutritionMatchingStore';
    import { useRecipeStore } from 'src/stores/recipeStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';

    const $q = useQuasar();
    const nutritionApi = new NutritionApiService();
    // Via the store, not the API service directly — it carries the offline
    // queue and keeps the cached stock-item list in step, exactly as the
    // stock-item detail page's edits do.
    const recipeStore = useRecipeStore();
    const stockItemStore = useStockItemStore();

    const items = ref<UnmatchedStockItem[]>([]);
    const ignoredItems = ref<UnmatchedStockItem[]>([]);
    const strongCount = ref(0);
    const ignoredCount = ref(0);
    // How many foods the matcher had to choose from. Zero means "no food data
    // installed", which is a different page than "nothing left to match" —
    // server-owned so the threshold for that judgement isn't in two languages.
    const catalogueSize = ref(0);
    const showIgnored = ref(false);
    const { isAdmin } = storeToRefs(useAuthStore());
    const matchingStore = useNutritionMatchingStore();

    const loading = ref(false);
    const busy = ref(false);
    const acceptingAll = ref(false);
    const workingId = ref<string | null>(null);

    const pickerOpen = ref(false);
    const searchingItem = ref<UnmatchedStockItem | null>(null);

    function notifyError(message: string, err: unknown) {
        console.warn(message, err);
        $q.notify({ type: 'negative', message });
    }

    async function refresh() {
        try {
            const dto = await nutritionApi.getUnmatchedItemsAsync(showIgnored.value);
            items.value = dto.items;
            strongCount.value = dto.strong_count;
            ignoredCount.value = dto.ignored_count;
            ignoredItems.value = dto.ignored_items;
            catalogueSize.value = dto.catalogue_size;
            matchingStore.setCount(dto.items.length);
        } catch (err) {
            notifyError('Could not load nutrition matches.', err);
        }
    }

    onMounted(async () => {
        loading.value = true;
        await refresh();
        loading.value = false;
    });

    /** Every row action is the same shape: one PATCH, then re-read the list so
     *  the counts and ordering stay the server's answer rather than a local
     *  guess at what changed. */
    async function patchItem(item: UnmatchedStockItem, patch: Record<string, unknown>, failure: string) {
        busy.value = true;
        workingId.value = item.stock_item_id;
        try {
            await stockItemStore.updateStockItemAsync({
                stock_item_id: item.stock_item_id,
                ...patch,
            });
            await refresh();
        } catch (err) {
            notifyError(failure, err);
        } finally {
            busy.value = false;
            workingId.value = null;
        }
    }

    async function onAccept(item: UnmatchedStockItem) {
        if (!item.suggestion) return;
        await patchItem(
            item,
            { nutrition_food_id: item.suggestion.nutrition_food_id },
            `Could not link ${item.name}.`,
        );
    }

    async function onIgnore(item: UnmatchedStockItem) {
        await patchItem(item, { nutrition_ignored: true }, `Could not set aside ${item.name}.`);
    }

    async function onUnignore(item: UnmatchedStockItem) {
        await patchItem(item, { nutrition_ignored: false }, `Could not restore ${item.name}.`);
    }

    async function onAcceptAll() {
        acceptingAll.value = true;
        busy.value = true;
        try {
            const result = await nutritionApi.acceptAllSuggestionsAsync();
            $q.notify({
                type: 'positive',
                message: result.linked_count === 1
                    ? 'Linked 1 item to its suggested food.'
                    : `Linked ${result.linked_count} items to their suggested foods.`,
            });
            // Server-side bulk link, so it never touches `stockItemStore` and
            // never trips its invalidation. Every recipe using one of those
            // items now has a different rollup — kcal, and the front-of-pack
            // rating — so the cookbook's cached list is out of date.
            recipeStore.invalidateRecipes();
            await refresh();
        } catch (err) {
            notifyError('Could not accept the suggestions.', err);
        } finally {
            acceptingAll.value = false;
            busy.value = false;
        }
    }

    function onSearch(item: UnmatchedStockItem) {
        searchingItem.value = item;
        pickerOpen.value = true;
    }

    async function onPicked(foodId: string) {
        const item = searchingItem.value;
        searchingItem.value = null;
        if (!item) return;
        await patchItem(item, { nutrition_food_id: foodId }, `Could not link ${item.name}.`);
    }

    async function onToggleIgnored() {
        showIgnored.value = !showIgnored.value;
        // The set-aside rows are only fetched when they're about to be shown —
        // the common case is a user who never opens this.
        if (showIgnored.value) await refresh();
    }
</script>

<style scoped lang="scss">
    /* Matches the suggestion tag on the stock-item detail page — the same
       "Dora is asking, nothing is saved" signal has to look the same on both
       surfaces. */
    /* The "no food data installed" notice — the settings card, laid out as
       icon / prose / action, tinted with the warning-soft surface so it reads
       as a state of the page rather than a row of work. */
    .match-notice {
        display: flex;
        align-items: flex-start;
        gap: var(--space-3);
        padding: var(--space-4);
        background: var(--semantic-warning-soft);
    }
    .match-notice__icon {
        flex: 0 0 auto;
        color: var(--semantic-warning-ink);
        margin-top: 2px;
    }
    .match-notice__body { flex: 1 1 auto; min-width: 0; }
    .match-notice__action { flex: 0 0 auto; }
    @media (max-width: 599px) {
        .match-notice { flex-wrap: wrap; }
        .match-notice__action { width: 100%; }
    }
    .match-tag {
        background: var(--surface-sunken);
        color: var(--text-secondary);
        font-size: 0.6875rem;
        font-weight: 600;
        padding: 1px 6px;
    }
</style>
