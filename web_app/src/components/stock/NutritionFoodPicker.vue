<template>
    <BaseDialog
        v-model="open"
        :title="`Link ${itemName} to a food`"
        closable
        card-class="food-picker"
        card-style="width: 560px; max-width: 95vw"
        @cancel="onHide"
    >
            <q-card-section class="food-picker__head">
                <div class="food-picker__sub dora-text-muted">
                    Search by name, or type a barcode.
                </div>
            </q-card-section>

            <q-card-section class="q-pt-none">
                <q-input
                    v-model="query"
                    dense
                    outlined
                    autofocus
                    clearable
                    debounce="300"
                    placeholder="e.g. banana, or 9300675024235"
                    @update:model-value="onQueryChange"
                >
                    <template #prepend>
                        <q-icon :name="searchIcon" />
                    </template>
                    <template #append>
                        <AppSpinner v-if="searching" size="18px" />
                    </template>
                </q-input>

                <div v-if="isBarcode" class="food-picker__hint dora-text-muted">
                    Looking that up as a barcode.
                </div>
            </q-card-section>

            <q-card-section class="food-picker__results q-pt-none">
                <div v-if="failedSources.length" class="food-picker__warning">
                    <q-icon :name="ICONS.warning" size="16px" />
                    <span>
                        Couldn't reach {{ failedSources.join(', ') }}. Try again in a
                        moment, or install the offline food databases.
                    </span>
                </div>

                <div
                    v-if="!searching && query && query.length >= 2 && results.length === 0"
                    class="food-picker__empty dora-text-muted"
                >
                    Nothing found for "{{ query }}".
                    <template v-if="!anySourceReady">
                        No food source is set up yet. An admin can add one under
                        System → Nutrition.
                    </template>
                </div>

                <button
                    v-for="result in results"
                    :key="`${result.source}:${result.source_ref}`"
                    type="button"
                    class="food-row"
                    :disabled="saving"
                    @click="onPick(result)"
                >
                    <div class="food-row__main">
                        <div class="food-row__name">
                            {{ result.name }}
                            <span v-if="result.brand" class="food-row__brand dora-text-muted">
                                {{ result.brand }}
                            </span>
                        </div>
                        <div class="food-row__meta dora-text-muted">
                            <span v-if="result.kcal_per_100g !== null">
                                {{ Math.round(result.kcal_per_100g) }} kcal / 100g
                            </span>
                            <span v-if="result.match === 'barcode'" class="food-row__exact">
                                barcode match
                            </span>
                        </div>
                    </div>
                    <span class="food-row__source">{{ result.source_label }}</span>
                </button>
            </q-card-section>

        <template #actions>
            <BaseButton variant="ghost" label="Cancel" @click="open = false" />
        </template>
    </BaseDialog>
</template>

<script lang="ts" setup>
    // Nutrition complex-mode — the search-and-confirm picker.
    //
    // The interaction is deliberately "search, look, pick": results are
    // *suggestions* and nothing is written until the user taps one (P12
    // No-invent). Food matching is exactly where silent auto-matching produces
    // confidently wrong calories, so there is no auto-*link* path — the
    // name-based matcher added 2026-08-15 (`features/nutrition/suggestions.py`)
    // only ever puts a labelled candidate on screen for a human to accept, and
    // this dialog stays the "search it yourself" escape hatch from it.
    //
    // Every row is badged with the catalogue it came from, because three
    // sources can disagree about a banana and the user should be able to tell
    // a curated USDA entry from a crowd-sourced supermarket product (P3).
    import AppSpinner from 'src/components/AppSpinner.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import { useQuasar } from 'quasar';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { ICONS } from 'src/style/icons';
    import { computed, ref, watch } from 'vue';
    import NutritionApiService, {
        type NutritionFoodResult,
    } from 'src/services/api/nutritionApiService';

    const props = defineProps<{
        modelValue: boolean;
        itemName: string;
    }>();

    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
        // Emits the persisted food id — the caller saves the link.
        (e: 'picked', foodId: string, foodName: string): void;
    }>();

    const api = new NutritionApiService();
    const $q = useQuasar();
    function notifyError(message: string, err: unknown): void {
        $q.notify({ type: 'negative', message, caption: toastCaption(err) });
    }

    const query = ref('');
    const results = ref<NutritionFoodResult[]>([]);
    const failedSources = ref<string[]>([]);
    const anySourceReady = ref(true);
    const isBarcode = ref(false);
    const searching = ref(false);
    const saving = ref(false);

    const open = computed({
        get: () => props.modelValue,
        set: (value: boolean) => emit('update:modelValue', value),
    });

    const searchIcon = computed(() => (isBarcode.value ? ICONS.qr_code : ICONS.search));

    // Each search stamps a token; a slow response from an earlier keystroke is
    // discarded rather than overwriting fresher results.
    let searchToken = 0;

    async function onQueryChange(raw: string | number | null) {
        // Trim for the search only — never write the trimmed value back into
        // `query`. Doing so ate the trailing space of every word, so a
        // two-word search ("greek yoghurt") collapsed to "greekyoghurt".
        const text = String(raw ?? '').trim();
        if (text.length < 2) {
            results.value = [];
            failedSources.value = [];
            isBarcode.value = false;
            return;
        }

        const token = ++searchToken;
        searching.value = true;
        try {
            const res = await api.lookupAsync(text);
            if (token !== searchToken) return;
            results.value = res.results;
            isBarcode.value = res.is_barcode;
            failedSources.value = res.sources_failed.map((f) => f.source_label ?? f.source);
            anySourceReady.value = res.sources_queried.length > 0;
        } catch (err) {
            if (token === searchToken) notifyError('Could not search for foods.', err);
        } finally {
            if (token === searchToken) searching.value = false;
        }
    }

    async function onPick(result: NutritionFoodResult) {
        saving.value = true;
        try {
            // Local rows already have an id; a live suggestion has to be
            // persisted first, which the server does by re-fetching it.
            const foodId = result.id
                ?? (await api.resolveFoodAsync(result.source, result.source_ref)).id;
            emit('picked', foodId, result.name);
            open.value = false;
        } catch (err) {
            notifyError(`Could not link ${result.name}.`, err);
        } finally {
            saving.value = false;
        }
    }

    function onHide() {
        query.value = '';
        results.value = [];
        failedSources.value = [];
        isBarcode.value = false;
    }

    // Reset when reopened so a previous search doesn't linger.
    watch(() => props.modelValue, (isOpen) => { if (isOpen) onHide(); });
</script>

<style scoped lang="scss">
    .food-picker__head { padding-bottom: var(--space-2); }
    .food-picker__sub {
        font-size: calc(var(--font-size-sm) * 1rem);
        line-height: 1.4;
        margin-top: 2px;
    }
    .food-picker__hint {
        font-size: calc(var(--font-size-xs) * 1rem);
        margin-top: var(--space-1);
    }
    .food-picker__results {
        display: flex;
        flex-direction: column;
        gap: var(--space-1);
        max-height: 46vh;
        overflow-y: auto;
    }
    .food-picker__warning {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        font-size: calc(var(--font-size-sm) * 1rem);
        color: var(--text-warning);
        padding: var(--space-2) 0;
    }
    .food-picker__empty {
        font-size: calc(var(--font-size-sm) * 1rem);
        line-height: 1.5;
        padding: var(--space-3) 0;
    }
    .food-row {
        display: flex;
        align-items: center;
        gap: var(--space-3);
        width: 100%;
        text-align: left;
        padding: var(--space-3);
        border: 1px solid transparent;
        border-radius: var(--radius-md);
        background: none;
        font: inherit;
        cursor: pointer;
        transition: background-color var(--motion-fast) var(--motion-ease),
            border-color var(--motion-fast) var(--motion-ease);
    }
    .food-row:hover:not(:disabled) {
        background: var(--surface-sunken);
        border-color: var(--border-strong);
    }
    .food-row:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: -2px;
    }
    .food-row:disabled { opacity: 0.6; cursor: default; }
    .food-row__main { flex: 1 1 auto; min-width: 0; }
    .food-row__name {
        color: var(--text-primary);
        font-size: calc(var(--font-size-md) * 1rem);
        line-height: 1.3;
    }
    .food-row__brand { font-size: calc(var(--font-size-sm) * 1rem); margin-left: var(--space-1); }
    .food-row__meta {
        display: flex;
        gap: var(--space-2);
        font-size: calc(var(--font-size-xs) * 1rem);
        margin-top: 2px;
    }
    // --text-accent was never defined — the declaration was invalid and the
    // row simply inherited. Points at the accent ink token now (2026-09-01).
    .food-row__exact { color: var(--accent-ink); }
    .food-row__source {
        flex: 0 0 auto;
        font-size: calc(var(--font-size-xs) * 1rem);
        padding: 2px 8px;
        border-radius: var(--radius-sm);
        background: var(--surface-sunken);
        color: var(--text-secondary);
        white-space: nowrap;
    }
    @media (pointer: coarse) {
        .food-row { min-height: 56px; }
    }
</style>
