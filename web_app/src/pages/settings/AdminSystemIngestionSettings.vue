<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Product data ingestion"
            description="Where the outside tool that pushes product and offer data into Dora lives. Access itself is controlled by the keys you mint on the API access page."
            :icon="ICONS.cloud_upload"
        />

        <template v-if="ready">
            <!-- Deliberately NOT gated on the `products` data-presence flag
                 the way it was on the old Features page: that made the setup
                 control appear only once the data it produces already existed.
                 (The ingestion toggle that used to sit above this was removed
                 2026-09-07 — minting a key IS the switch; see
                 migration `e7a2c4f9b361`.) -->
            <SettingsSection>
                <template #title>Product search</template>
                <template #description>
                    The URL of your product search / importer tool. When set, a
                    "Product Search" entry appears in the main menu that opens it
                    in a new tab; leave blank to hide it.
                </template>

                <SettingsRow stacked>
                    <q-input
                        v-model="draft.product_search_url"
                        placeholder="https://your-search.example/"
                        outlined
                        dense
                        :loading="saving"
                        :error="!!productSearchUrlError"
                        :error-message="productSearchUrlError ?? undefined"
                        @blur="onSaveProductSearchUrl"
                    />
                </SettingsRow>
            </SettingsSection>
        </template>
    </div>
</template>

<script lang="ts" setup>
    // Owner 2026-09-03: was "Companion ingestion", a row on the dissolved
    // Features page. Renamed to what it is (any external source, not just the
    // Dora companion) and moved to Data & access, where the rest of "data
    // entering and leaving this install" lives.
    import { ICONS } from 'src/style/icons';
    import { useAppSettingDrafts } from 'src/composables/useAppSettingDrafts';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import { ref } from 'vue';
    import { useProductSearchUrl } from 'src/composables/useProductSearchUrl';

    const { draft, ready, saving, save } = useAppSettingDrafts({ product_search_url: '' });
    const productSearch = useProductSearchUrl();
    const productSearchUrlError = ref<string | null>(null);

    function onSaveProductSearchUrl() {
        const trimmed = draft.product_search_url.trim();
        productSearchUrlError.value = null;
        if (trimmed && !(trimmed.startsWith('http://') || trimmed.startsWith('https://'))) {
            productSearchUrlError.value = 'Must start with http:// or https://.';
            return;
        }
        void save({ product_search_url: trimmed }, 'Product search URL saved.', productSearch.refresh);
    }
</script>

<style scoped lang="scss">
</style>
