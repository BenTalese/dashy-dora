<template>
    <!-- Dietary tags carry a grouping label, so they keep a bespoke editor
         (the shared TaxonomyManagerPage covers the name-only types). §2.11:
         create/rename now use one DietaryTagFormDialog instead of two
         sequential prompts. -->
    <div class="settings-page">
        <SettingsPageHeader
            title="Dietary tags"
            description="Dietary / allergen / nutritional tags recipes can be tagged with. Useful for filtering."
            :icon="ICONS.eco"
        >
            <template #actions>
                <BaseButton
                    :icon="ICONS.add"
                    label="New tag"
                    :loading="busy"
                    @click="onCreateDietaryTag"
                />
            </template>
        </SettingsPageHeader>

        <q-list class="settings-list" separator>
            <q-item v-for="tag in dietaryTags" :key="tag.dietary_tag_id" class="q-py-sm">
                <q-item-section>
                    <!-- Same one-line treatment as VocabListEditor (owner call
                         2026-08-17): name, then its grouping + tally inline at
                         the same type size. -->
                    <q-item-label class="vocab-row">
                        <span>{{ tag.name }}</span>
                        <span class="dora-text-muted">
                            {{ tag.category }} ·
                            {{ tag.recipe_count ?? 0 }} recipe{{ (tag.recipe_count ?? 0) === 1 ? '' : 's' }}
                        </span>
                    </q-item-label>
                </q-item-section>
                <q-item-section side>
                    <div class="row q-gutter-xs">
                        <BaseButton variant="icon" :icon="ICONS.edit" @click="onRenameDietaryTag(tag)">
                            <BaseTooltip>Rename</BaseTooltip>
                        </BaseButton>
                        <BaseButton variant="icon" :icon="ICONS.delete_outline" @click="onDeleteDietaryTag(tag)">
                            <BaseTooltip>Delete</BaseTooltip>
                        </BaseButton>
                    </div>
                </q-item-section>
            </q-item>
            <q-item v-if="!loading && dietaryTags.length === 0">
                <q-item-section class="dora-text-muted text-center">
                    No dietary tags yet.
                </q-item-section>
            </q-item>
        </q-list>

        <q-inner-loading :showing="loading && dietaryTags.length === 0">
            <AppSpinner size="48px" />
        </q-inner-loading>

        <DietaryTagFormDialog
            v-model="dialogOpen"
            :tag="editingTag"
            :busy="busy"
            @confirm="onDialogConfirm"
        />
    </div>
</template>

<script lang="ts" setup>
    import { useSettingsSave } from 'src/composables/useSettingsSave';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import AppSpinner from 'src/components/AppSpinner.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import { ICONS } from 'src/style/icons';
    import DietaryTagFormDialog from 'src/components/settings/DietaryTagFormDialog.vue';
    import type { DietaryTag } from 'src/models/recipeVocab';
    import DietaryTagApiService from 'src/services/api/dietaryTagApiService';
    import { onMounted, ref } from 'vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import { useConfirm } from 'src/composables/useConfirm';


    const { confirm } = useConfirm();
    const dietaryTagApi = new DietaryTagApiService();

    const dietaryTags = ref<DietaryTag[]>([]);
    const loading = ref(false);
    const busy = ref(false);

    // Dialog state — `editingTag` null means create, populated means rename.
    const dialogOpen = ref(false);
    const editingTag = ref<DietaryTag | null>(null);

    const { notifyError } = useSettingsSave();

    async function load() {
        loading.value = true;
        try {
            dietaryTags.value = await dietaryTagApi.getAllAsync();
        } catch (err) {
            notifyError('Could not load dietary tags.', err);
        } finally {
            loading.value = false;
        }
    }

    async function run(action: () => Promise<unknown>) {
        busy.value = true;
        try {
            await action();
            await load();
        } catch (err) {
            notifyError('Could not save the change.', err);
        } finally {
            busy.value = false;
        }
    }

    function onCreateDietaryTag() {
        editingTag.value = null;
        dialogOpen.value = true;
    }

    function onRenameDietaryTag(tag: DietaryTag) {
        editingTag.value = tag;
        dialogOpen.value = true;
    }

    async function onDialogConfirm(payload: { name: string; category: string }) {
        const target = editingTag.value;
        await run(() =>
            target
                ? dietaryTagApi.updateAsync(target.dietary_tag_id, payload)
                : dietaryTagApi.createAsync(payload),
        );
        dialogOpen.value = false;
    }

    async function onDeleteDietaryTag(tag: DietaryTag) {
        const count = tag.recipe_count ?? 0;
        const ok = await confirm({
            title: `Delete "${tag.name}"?`,
            message: count > 0
                    ? `${count} recipe${count === 1 ? '' : 's'} tagged with this will lose the tag.`
                    : 'Nothing currently uses this tag.',
            okLabel: 'Delete',
            destructive: true,
        });
        if (ok) await run(() => dietaryTagApi.deleteAsync(tag.dietary_tag_id).then(() => undefined));
    }

    onMounted(load);
</script>

<style scoped lang="scss">
    .settings-page { position: relative; }
    .vocab-row {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        gap: var(--space-2, 8px);
    }
</style>
