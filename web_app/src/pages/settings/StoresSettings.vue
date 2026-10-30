<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Stores"
            description="The retail stores you actually shop at. Upload a logo so each store is recognisable on cards and lines."
            :icon="ICONS.store"
        >
            <template #actions>
                <BaseButton
                    :icon="ICONS.add"
                    label="New store"
                    :loading="saving"
                    @click="onCreate"
                />
            </template>
        </SettingsPageHeader>

        <q-banner
            v-if="loadError"
            class="dora-bg-negative-soft text-negative q-mb-md"
            dense
            rounded
        >
            {{ loadError }}
        </q-banner>

        <!--
            Owner 2026-09-03: this page used to open a create/edit dialog for
            both the name and the logo, which made it the odd one out among its
            neighbours. It now borrows the two affordances the rest of the app
            already uses: rename in place (VocabListEditor / stock groups) and
            click-the-picture-to-change-it (ImageEditTile — Account's profile
            picture, the recipe masthead). Row + list styling matches
            VocabListEditor so the two pages read as one surface.
        -->
        <q-list v-if="stores.length > 0" class="settings-list" separator>
            <q-item v-for="s in stores" :key="s.store_id" class="settings-list__item">
                <q-item-section avatar>
                    <ImageEditTile
                        :label="s.has_image ? `Change ${s.name}'s logo` : `Add a logo for ${s.name}`"
                        shape="rounded"
                        :width="64"
                        :height="40"
                        :busy="imageBusyId === s.store_id"
                        accept="image/png,image/jpeg,image/webp"
                        @pick="(img) => onPickImage(s, img)"
                        @error="onPickError"
                    >
                        <StoreLogo
                            :name="s.name"
                            :store-id="s.store_id"
                            :has-image="s.has_image"
                            :height="40"
                            :width="64"
                        />
                    </ImageEditTile>
                </q-item-section>
                <q-item-section>
                    <q-item-label v-if="editingId !== s.store_id">{{ s.name }}</q-item-label>
                    <q-input
                        v-else
                        v-model="renameDraft"
                        dense
                        outlined
                        autofocus
                        @blur="saveRename(s)"
                        @keydown.enter.prevent="saveRename(s)"
                        @keydown.esc.prevent="editingId = null"
                    />
                </q-item-section>
                <q-item-section side>
                    <div class="row q-gutter-xs items-center">
                        <BaseButton
                            :aria-label="`Remove logo for ${s.name}`"
                            v-if="s.has_image"
                            variant="icon"
                            :icon="ICONS.image_not_supported"
                            @click="onRemoveImage(s)"
                        >
                            <BaseTooltip>Remove logo</BaseTooltip>
                        </BaseButton>
                        <BaseButton
                            :aria-label="`Rename ${s.name}`"
                            variant="icon"
                            :icon="ICONS.edit"
                            @click="startRename(s)"
                        >
                            <BaseTooltip>Rename</BaseTooltip>
                        </BaseButton>
                        <BaseButton
                            :aria-label="`Delete ${s.name}`"
                            variant="icon"
                            :icon="ICONS.delete_outline"
                            @click="onDelete(s)"
                        >
                            <BaseTooltip>Delete</BaseTooltip>
                        </BaseButton>
                    </div>
                </q-item-section>
            </q-item>
        </q-list>

        <div v-else-if="!loading" class="text-center q-pa-lg dora-text-muted">
            <q-icon :name="ICONS.store" size="48px" class="q-mb-sm" />
            <div>No stores yet. Add the ones you actually shop at.</div>
        </div>

        <div v-if="pickError" class="text-caption text-negative q-mt-sm">
            {{ pickError }}
        </div>
    </div>
</template>

<script lang="ts" setup>
    import { useSettingsSave } from 'src/composables/useSettingsSave';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import ImageEditTile from 'src/components/ImageEditTile.vue';
    import StoreLogo from 'src/components/StoreLogo.vue';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useStoresStore } from 'src/stores/storesStore';
    import { ICONS } from 'src/style/icons';
    import type { ProcessedImage } from 'src/services/files/imageService';
    import { storeToRefs } from 'pinia';
    import { onMounted, ref } from 'vue';
    import type { Store } from 'src/models/store';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import { useConfirm } from 'src/composables/useConfirm';


    const { confirm, prompt } = useConfirm();
    const { notifySuccess, notifyError } = useSettingsSave();
    const storesStore = useStoresStore();
    const { stores } = storeToRefs(storesStore);

    const loading = ref(false);
    const loadError = ref<string | null>(null);
    const saving = ref(false);
    const pickError = ref<string | null>(null);

    const editingId = ref<string | null>(null);
    const renameDraft = ref('');
    /** Store whose logo round-trip is in flight — drives that tile's spinner. */
    const imageBusyId = ref<string | null>(null);

    onMounted(() => {
        // R-016 ensureLoaded. There is no manual refresh control — every
        // mutation on this page already refreshes the store, so a refresh
        // button was a no-op affordance.
        loading.value = true;
        storesStore
            .ensureLoadedAsync()
            .catch((e) => {
                loadError.value = toastCaption(e);
            })
            .finally(() => {
                loading.value = false;
            });
    });

    // ── Create — name only, same prompt shape as the vocabulary pages ──
    async function onCreate(): Promise<void> {
        const name = await prompt({
            title: 'New store',
            message: 'What is this store called? (e.g. "Woolworths", "Aldi")',
        });
        if (!name) return;
        saving.value = true;
        try {
            await storesStore.createAsync({ name });
            notifySuccess(`Added ${name}.`);
        } catch (e) {
            notifyError("Couldn't add the store.", e);
        } finally {
            saving.value = false;
        }
    }

    // ── Rename in place ────────────────────────────────────────────────
    function startRename(store: Store): void {
        editingId.value = store.store_id;
        renameDraft.value = store.name;
    }

    async function saveRename(store: Store): Promise<void> {
        const next = renameDraft.value.trim();
        editingId.value = null;
        if (!next || next === store.name) return;
        try {
            await storesStore.updateAsync({ store_id: store.store_id, name: next });
            notifySuccess(`Updated ${next}.`);
        } catch (e) {
            notifyError("Couldn't update the store.", e);
        }
    }

    // ── Logo — click the tile, immediate save ──────────────────────────
    async function onPickImage(store: Store, image: ProcessedImage): Promise<void> {
        // ImageEditTile → processImageFile() already resized + re-encoded to
        // JPEG using the install-wide image policy (R-003). We just hand the
        // data URL to the update round-trip; the backend stores the bytes
        // verbatim and serves them via `GET /stores/<id>/image`.
        pickError.value = null;
        imageBusyId.value = store.store_id;
        try {
            await storesStore.updateAsync({
                store_id: store.store_id,
                name: store.name,
                image: image.dataUrl,
            });
        } catch (e) {
            notifyError(`Couldn't update ${store.name}'s logo.`, e);
        } finally {
            imageBusyId.value = null;
        }
    }

    function onPickError(message: string): void {
        pickError.value = message;
    }

    async function onRemoveImage(store: Store): Promise<void> {
        pickError.value = null;
        imageBusyId.value = store.store_id;
        try {
            await storesStore.updateAsync({
                store_id: store.store_id,
                name: store.name,
                clear_image: true,
            });
        } catch (e) {
            notifyError(`Couldn't remove ${store.name}'s logo.`, e);
        } finally {
            imageBusyId.value = null;
        }
    }

    async function onDelete(store: Store): Promise<void> {
        const ok = await confirm({
            title: `Delete ${store.name}?`,
            message:
                "Stock items and shopping-list lines using this store will have it cleared. A store with linked products can't be deleted.",
            okLabel: 'Delete',
            destructive: true,
        });
        if (!ok) return;
        try {
            const result = await storesStore.deleteAsync(store.store_id);
            const tail =
                result.items_affected || result.lines_affected
                    ? ` (${result.items_affected} stock item(s) and ${result.lines_affected} shopping line(s) had their store reference cleared.)`
                    : '';
            notifySuccess(`Deleted ${store.name}.${tail}`);
        } catch (e) {
            notifyError(`Couldn't delete ${store.name}.`, e);
        }
    }
</script>

<style scoped lang="scss">
    .settings-list__item {
        padding: 10px 4px;
    }
</style>
