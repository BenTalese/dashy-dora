<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Nutrition"
            description="How much nutrition detail Dora tracks, for the whole household."
            :icon="ICONS.monitor_heart"
        />

        <SettingsSection>
            <template #title>Mode</template>
            <template #description>
                <strong>Off</strong> hides nutrition everywhere.
                <strong>Simple</strong> adds one kcal number you type in per recipe.
                <strong>Complex</strong> links stock items to a food catalogue and
                works recipe nutrition out from those links.
            </template>

            <SettingsRow label="Nutrition mode">
                <DoraSegmented
                    :model-value="mode"
                    :options="modeOptions"
                    :disabled="saving"
                    @update:model-value="onModeChange"
                />
            </SettingsRow>

            <div
                v-if="mode === 'complex' && !anyAvailable"
                class="settings-page__note dora-text-muted"
            >
                Complex is on, but there's no food source yet. Download a
                dataset below, or allow Open Food Facts.
            </div>
            <!-- Deliberately a *separate* condition from the one above. Open
                 Food Facts alone satisfies "something can answer a lookup", so
                 that banner goes quiet while auto-matching is still dead —
                 matching reads the local catalogue only. Without this, the one
                 state that looks like a bug is the one state we say nothing
                 about. -->
            <div
                v-else-if="mode === 'complex' && !hasLocalDataset"
                class="settings-page__note dora-text-muted"
            >
                Manual search works, but Dora can't <em>suggest</em> foods until
                a dataset is downloaded below.
            </div>
        </SettingsSection>

        <template v-if="mode === 'complex'">
            <hr class="settings-divider" />

            <SettingsSection>
                <template #title>Food datasets</template>
                <template #description>
                    Downloaded once and searched offline. Best for generic
                    ingredients like "banana" and "flour".
                    <br /><br />
                    <!-- Stated here because this is the only screen that can
                         fix it: auto-matching reads the local catalogue and
                         nothing else, so without a dataset it silently suggests
                         nothing and reads as broken. -->
                    <strong>Auto-matching and suggestions need this.</strong>
                    Dora suggests foods by matching names against data held here.
                    Until a dataset is installed,
                    <router-link
                        to="/settings/kitchen-setup/nutrition-matching"
                        class="settings-page__link"
                    >Nutrition matching</router-link>
                    stays empty and no suggestions appear on stock items.
                </template>

                <div v-if="loading" class="settings-page__note dora-text-muted">
                    Checking what's installed…
                </div>

                <div v-for="source in datasetSources" :key="source.id" class="dataset-row">
                    <div class="dataset-row__main">
                        <div class="dataset-row__head">
                            <span class="dataset-row__label">{{ source.label }}</span>
                            <q-chip
                                v-if="source.available"
                                dense
                                square
                                size="sm"
                                class="dora-bg-positive-soft text-positive"
                            >
                                {{ source.food_count.toLocaleString() }} foods
                            </q-chip>
                        </div>
                        <div class="dataset-row__status dora-text-muted">
                            {{ statusLine(source) }}
                        </div>
                        <!-- B10 — an SR Legacy import runs for minutes, and a
                             bare spinner over that span reads as "wedged". The
                             bar is determinate only while the server can name
                             a denominator; the parsing phase has none, so it
                             stays indeterminate under a live row count rather
                             than faking a percentage. -->
                        <q-linear-progress
                            v-if="isBusy(source)"
                            class="dataset-row__bar"
                            rounded
                            size="4px"
                            color="primary"
                            :indeterminate="progressOf(source) === null"
                            :value="progressOf(source) ?? 0"
                        />
                    </div>
                    <BaseButton
                        :variant="source.available ? 'ghost' : 'secondary'"
                        :label="source.available ? 'Re-download' : 'Download'"
                        :disable="isBusy(source)"
                        :loading="isBusy(source)"
                        @click="onImport(source)"
                    />
                </div>
            </SettingsSection>

            <hr class="settings-divider" />

            <SettingsSection>
                <template #title>Recipe rating</template>
                <template #description>
                    An at-a-glance verdict on a recipe, using one of the
                    front-of-pack schemes you'd see on a package. Pick whichever
                    you recognise. Needs complex nutrition.
                </template>

                <SettingsRow
                    label="Rating scheme"
                    help="Ratings are estimates. Both schemes were written for packaged products and score per 100 g of the finished food; Dora works from the raw weight of your ingredients, so a dish that reduces down or is made with water you haven't listed will read differently."
                >
                    <!-- No `mode !== 'complex'` guard: this whole section is
                         already inside that condition. The old toggle carried
                         one, plus a "switch to complex" banner that could
                         never render — dropped rather than carried forward. -->
                    <DoraSegmented
                        :model-value="ratingScheme"
                        :options="ratingSchemeOptions"
                        :disabled="saving"
                        @update:model-value="onRatingSchemeChange"
                    />
                </SettingsRow>

                <!-- Provenance per scheme. Whose rating this is matters: these
                     are national programmes with real authorities behind them,
                     and a reader deciding whether to trust a letter on their
                     dinner deserves to know who wrote the rules. -->
                <div
                    v-if="ratingScheme !== 'none'"
                    class="settings-page__note dora-text-muted"
                >
                    <template v-if="ratingScheme === 'health_star'">
                        The <strong>Health Star Rating</strong> is the Australian
                        and New Zealand scheme, published by FSANZ. Half a star
                        to five; more stars is better.
                    </template>
                    <template v-else>
                        <strong>Nutri-Score</strong> is the European scheme,
                        published by Santé publique France and used in France,
                        Germany, Belgium, the Netherlands, Spain, Luxembourg and
                        Switzerland. A to E; A is best. Dora uses the updated
                        2023 algorithm and draws its own badge rather than the
                        official logo.
                    </template>
                </div>

            </SettingsSection>

            <hr class="settings-divider" />

            <SettingsSection>
                <template #title>Other sources</template>
                <template #description>
                    Optional extras searched alongside the datasets. Every result
                    in the picker is labelled with where it came from.
                </template>

                <SettingsRow
                    label="Open Food Facts"
                    help="Looks up packaged products by barcode over the internet."
                >
                    <q-toggle
                        :model-value="offLookupEnabled"
                        :disable="saving"
                        @update:model-value="onOffLookupChange"
                    />
                </SettingsRow>

                <SettingsRow
                    label="USDA API key"
                    help="Optional. Query USDA live instead of holding the dataset on disk. Free from api.data.gov; about 1,000 lookups an hour."
                >
                    <q-input
                        v-model="usdaKeyDraft"
                        dense
                        outlined
                        type="password"
                        placeholder="Paste a key"
                        style="min-width: 240px"
                        :disable="saving"
                        @blur="onUsdaKeySave"
                        @keydown.enter.prevent="onUsdaKeySave"
                    />
                </SettingsRow>
            </SettingsSection>
        </template>
    </div>
</template>

<script lang="ts" setup>
    // Nutrition is install-wide (owner call 2026-08-14) — this page replaces
    // the per-user Settings → Nutrition page, which mostly existed to tell you
    // to go ask an admin. Mode + complex-mode source config in one place.
    import { ICONS } from 'src/style/icons';
    import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
    import { useSettingsSave } from 'src/composables/useSettingsSave';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import type { UpdateAppSettingsCommand } from 'src/services/api/appSettingsApiService';
    import { useAppSettingsStore } from 'src/stores/appSettingsStore';
    import NutritionApiService, {
        type NutritionSourceStatus,
    } from 'src/services/api/nutritionApiService';
    import BaseButton from 'src/components/BaseButton.vue';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import type { RatingScheme } from 'src/composables/useNutritionRating';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import DoraSegmented, { type DoraSegmentedOption } from 'src/components/settings/DoraSegmented.vue';
    import { useRecipeStore } from 'src/stores/recipeStore';

    type NutritionMode = 'off' | 'simple' | 'complex';

    const nutritionApi = new NutritionApiService();
    const appSettingsStore = useAppSettingsStore();
    const { update, notifyError } = useSettingsSave();
    const { refresh: refreshFlags } = useFeatureFlags();
    const recipeStore = useRecipeStore();

    // Short enough for a segmented control; the provenance line under it
    // carries the detail that would not fit here.
    const ratingSchemeOptions: DoraSegmentedOption<RatingScheme>[] = [
        { label: 'None', value: 'none' },
        { label: 'Health stars', value: 'health_star' },
        { label: 'Nutri-Score', value: 'nutri_score' },
    ];
    const modeOptions: DoraSegmentedOption<NutritionMode>[] = [
        { label: 'Off', value: 'off' },
        { label: 'Simple', value: 'simple' },
        { label: 'Complex', value: 'complex' },
    ];

    const mode = ref<NutritionMode>('off');
    const sources = ref<NutritionSourceStatus[]>([]);
    const anyAvailable = ref(false);
    const offLookupEnabled = ref(true);
    // Owner ask 2026-08-27. Off by default everywhere; Settings →
    // Region's "Match this device" is what offers it on an AU/NZ locale.
    const ratingScheme = ref<RatingScheme>('none');
    const usdaKeyDraft = ref('');
    const savedUsdaKey = ref('');
    const loading = ref(true);
    const saving = ref(false);

    const datasetSources = computed(() =>
        sources.value.filter((s) => s.kind === 'dataset'),
    );
    // A dataset reports `available` exactly when it holds rows, so this is
    // "is there anything for the name-matcher to read?". Distinct from
    // `anyAvailable`, which a live source alone satisfies.
    const hasLocalDataset = computed(() =>
        datasetSources.value.some((s) => s.available),
    );

    function isBusy(source: NutritionSourceStatus): boolean {
        return ['downloading', 'parsing', 'saving'].includes(source.phase ?? '');
    }

    /** Fraction 0–1 for the progress bar, or null when nothing honest can be
     *  computed and the bar should run indeterminate.
     *
     *  Only `downloading` has a real denominator (`Content-Length`), and even
     *  then the server sends `bytes_total: 0` when the origin declined to give
     *  one — so the zero check is load-bearing, not defensive noise. */
    function progressOf(source: NutritionSourceStatus): number | null {
        if (source.phase !== 'downloading') return null;
        const total = source.bytes_total ?? 0;
        if (total <= 0) return null;
        return Math.min(1, (source.bytes_done ?? 0) / total);
    }

    function formatMb(bytes: number): string {
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    function statusLine(source: NutritionSourceStatus): string {
        switch (source.phase) {
            case 'downloading': {
                const done = source.bytes_done ?? 0;
                const total = source.bytes_total ?? 0;
                // Before the first chunk lands there is nothing to report, and
                // "0.0 MB of 3.7 MB" reads worse than the plain verb.
                if (done <= 0) return 'Downloading…';
                return total > 0
                    ? `Downloading ${formatMb(done)} of ${formatMb(total)}`
                    : `Downloading, ${formatMb(done)} so far`;
            }
            case 'parsing': {
                const rows = source.rows_done ?? 0;
                // No total to offer; the count alone is what proves it's moving.
                return rows > 0
                    ? `Reading the data, ${rows.toLocaleString()} rows`
                    : 'Reading the data…';
            }
            case 'saving': {
                const foods = source.foods ?? 0;
                return foods > 0
                    ? `Saving ${foods.toLocaleString()} foods…`
                    : 'Saving foods…';
            }
            case 'error': return source.error ?? 'That download failed.';
            default:
                return source.available
                    ? 'Installed and searchable.'
                    : 'Not downloaded yet.';
        }
    }

    async function refreshSources() {
        try {
            const res = await nutritionApi.getSourcesAsync();
            mode.value = res.mode;
            sources.value = res.sources;
            anyAvailable.value = res.any_available;
        } catch (err) {
            notifyError('Could not read the nutrition sources.', err);
        } finally {
            loading.value = false;
        }
    }

    // Poll only while an import is actually running, so an idle admin page
    // isn't hitting the server every couple of seconds.
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    function stopPolling() {
        if (pollTimer !== null) { clearInterval(pollTimer); pollTimer = null; }
    }
    function ensurePolling() {
        if (pollTimer !== null) return;
        pollTimer = setInterval(() => {
            void refreshSources().then(() => {
                if (!datasetSources.value.some(isBusy)) stopPolling();
            });
        }, 2500);
    }

    async function loadSettings() {
        try {
            const settings = await appSettingsStore.loadAsync();
            offLookupEnabled.value = settings.nutrition_off_lookup_enabled;
            ratingScheme.value = (settings.nutrition_rating_scheme ?? 'none') as RatingScheme;
            savedUsdaKey.value = settings.nutrition_usda_api_key ?? '';
            usdaKeyDraft.value = savedUsdaKey.value;
        } catch (err) {
            notifyError('Could not read the nutrition settings.', err);
        }
    }

    // R-010 — typed against the real command shape, not a loose record, so a
    // renamed setting fails here rather than silently no-op'ing at runtime.
    async function patch(message: string, body: UpdateAppSettingsCommand) {
        saving.value = true;
        try {
            await update(message, () => appSettingsStore.saveAsync(body));
            // The mode drives /api/health gates all over the app; refresh the
            // cached flag map so other surfaces don't run on a stale answer.
            await refreshFlags();
            // Refreshing the flags is only half of it. The rating and the whole
            // complex-mode rollup are *server-computed per request* — the DTO
            // carries no rating at all while the scheme is 'none' — so a recipe
            // list fetched before this write stays ratingless even once the flag
            // says the chip should render. That read as "health stars don't
            // appear until I refresh the page" (owner 2026-09-09).
            recipeStore.invalidateRecipes();
        } finally {
            saving.value = false;
        }
    }

    async function onModeChange(value: NutritionMode) {
        const previous = mode.value;
        mode.value = value;
        try {
            await patch(`Nutrition set to ${value}.`, { nutrition_mode: value });
            await refreshSources();
        } catch {
            mode.value = previous;
        }
    }

    const RATING_SCHEME_NAMES: Record<RatingScheme, string> = {
        none: 'No recipe rating.',
        health_star: 'Health Star Rating on.',
        nutri_score: 'Nutri-Score on.',
    };

    async function onRatingSchemeChange(value: RatingScheme) {
        const previous = ratingScheme.value;
        ratingScheme.value = value;
        try {
            await patch(
                RATING_SCHEME_NAMES[value],
                { nutrition_rating_scheme: value },
            );
        } catch {
            ratingScheme.value = previous;
        }
    }

    async function onOffLookupChange(value: boolean) {
        const previous = offLookupEnabled.value;
        offLookupEnabled.value = value;
        try {
            await patch(
                value ? 'Open Food Facts lookups on.' : 'Open Food Facts lookups off.',
                { nutrition_off_lookup_enabled: value },
            );
            await refreshSources();
        } catch {
            offLookupEnabled.value = previous;
        }
    }

    async function onUsdaKeySave() {
        const next = usdaKeyDraft.value.trim();
        if (next === savedUsdaKey.value) return;
        try {
            await patch('USDA API key saved.', { nutrition_usda_api_key: next });
            savedUsdaKey.value = next;
            await refreshSources();
        } catch {
            usdaKeyDraft.value = savedUsdaKey.value;
        }
    }

    async function onImport(source: NutritionSourceStatus) {
        try {
            const res = await nutritionApi.startDatasetImportAsync(source.id);
            sources.value = res.sources;
            anyAvailable.value = res.any_available;
            ensurePolling();
        } catch (err) {
            notifyError(`Could not start the ${source.label} download.`, err);
        }
    }

    onMounted(async () => {
        await Promise.all([refreshSources(), loadSettings()]);
        if (datasetSources.value.some(isBusy)) ensurePolling();
    });

    onBeforeUnmount(stopPolling);
</script>

<style scoped lang="scss">
    .settings-page { display: flex; flex-direction: column; }
    .settings-page__note {
        font-size: 0.8125rem;
        line-height: 1.4;
        margin-top: 4px;
    }
    .dataset-row {
        display: flex;
        align-items: center;
        gap: var(--space-3);
        padding: var(--space-3) 0;
    }
    .dataset-row + .dataset-row {
        border-top: 1px solid var(--divider);
    }
    .dataset-row__main { flex: 1 1 auto; min-width: 0; }
    .dataset-row__head {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        flex-wrap: wrap;
    }
    .dataset-row__label {
        font-size: 0.9375rem;
        color: var(--text-primary);
    }
    .dataset-row__status {
        font-size: 0.8125rem;
        line-height: 1.4;
        margin-top: 2px;
    }

    .dataset-row__bar {
        margin-top: var(--space-2);
        // Capped so the bar tracks the status text it belongs to rather than
        // stretching the width of a wide settings pane.
        max-width: 320px;
    }
</style>
