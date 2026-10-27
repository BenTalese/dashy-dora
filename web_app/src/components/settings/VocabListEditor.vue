<template>
    <div class="settings-page">
        <SettingsPageHeader :title="title" :description="description" :icon="icon">
            <template #actions>
                <BaseButton
                    :icon="ICONS.add"
                    :label="`New ${noun}`"
                    :loading="busy"
                    @click="onCreate"
                />
            </template>
        </SettingsPageHeader>

        <q-list class="vocab-list" separator>
            <q-item v-for="(item, index) in items" :key="item.id" class="vocab-list__item">
                <q-item-section>
                    <!-- Name and usage tally sit on one line at the same type
                         size (owner call 2026-08-17) — the tally is context on
                         the name, not a second-tier caption. -->
                    <q-item-label v-if="editingId !== item.id" class="vocab-row">
                        <span>{{ item.name }}</span>
                        <span class="dora-text-muted">{{ usageText(item) }}</span>
                    </q-item-label>
                    <q-input
                        v-else
                        v-model="renameDraft"
                        dense
                        outlined
                        autofocus
                        @blur="saveRename(item)"
                        @keydown.enter.prevent="saveRename(item)"
                        @keydown.esc.prevent="editingId = null"
                    />
                </q-item-section>
                <q-item-section side>
                    <div class="row q-gutter-xs items-center">
                        <template v-if="reorderable">
                            <BaseButton
                                variant="icon"
                                :icon="ICONS.arrow_upward"
                                :disable="index === 0"
                                @click="emit('reorder', item.id, 'up')"
                            >
                                <BaseTooltip>Move up</BaseTooltip>
                            </BaseButton>
                            <BaseButton
                                variant="icon"
                                :icon="ICONS.arrow_downward"
                                :disable="index === items.length - 1"
                                @click="emit('reorder', item.id, 'down')"
                            >
                                <BaseTooltip>Move down</BaseTooltip>
                            </BaseButton>
                        </template>
                        <BaseButton variant="icon" :icon="ICONS.edit" @click="startRename(item)">
                            <BaseTooltip>Rename</BaseTooltip>
                        </BaseButton>
                        <BaseButton variant="icon" :icon="ICONS.delete_outline" @click="onDelete(item)">
                            <BaseTooltip>Delete</BaseTooltip>
                        </BaseButton>
                    </div>
                </q-item-section>
            </q-item>
            <q-item v-if="!loading && items.length === 0">
                <q-item-section class="dora-text-muted text-center">
                    No {{ nounPlural }} yet. {{ emptyAction }}
                </q-item-section>
            </q-item>
        </q-list>

        <q-inner-loading :showing="loading && items.length === 0">
            <AppSpinner size="48px" />
        </q-inner-loading>
    </div>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import AppSpinner from 'src/components/AppSpinner.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import { ICONS } from 'src/style/icons';
    import { ref } from 'vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import type { VocabItem } from 'src/components/settings/TaxonomyManagerPage.vue';
    import { useConfirm } from 'src/composables/useConfirm';

    const props = withDefaults(
        defineProps<{
            title: string;
            description: string;
            /** Heading icon — must match this page's sidebar entry in SettingsShell. */
            icon: string;
            noun: string;
            nounPlural: string;
            items: VocabItem[];
            loading: boolean;
            busy: boolean;
            reorderable?: boolean;
            usageLabel?: string;
            preservesLabel?: boolean;
            emptyAction?: string;
            /** Optional example shown in the create prompt, e.g. `"Dairy", "Snacks"`. */
            createHint?: string;
        }>(),
        {
            reorderable: false,
            usageLabel: 'recipe',
            preservesLabel: false,
            emptyAction: 'Create one to start tagging recipes.',
            createHint: '',
        },
    );

    const emit = defineEmits<{
        (e: 'create', name: string): void;
        (e: 'rename', id: string, name: string): void;
        (e: 'delete', id: string): void;
        (e: 'reorder', id: string, direction: 'up' | 'down'): void;
    }>();

    // "entry" → "entries", not "entrys". Only the -y rule is worth encoding:
    // the usage labels are a closed set (recipe / item / entry) and a general
    // pluraliser would be a library-sized answer to a three-word problem.
    function plural(word: string, count: number): string {
        if (count === 1) return word;
        return /[^aeiou]y$/.test(word) ? `${word.slice(0, -1)}ies` : `${word}s`;
    }

    function usageText(item: VocabItem): string {
        const count = item.usage_count ?? 0;
        return `${count} ${plural(props.usageLabel, count)}`;
    }


    const { confirm, prompt } = useConfirm();
    const editingId = ref<string | null>(null);
    const renameDraft = ref('');

    async function onCreate() {
        const name = await prompt({
            title: `New ${props.noun}`,
            message: `What is this ${props.noun} called?${
                props.createHint ? ` (e.g. ${props.createHint})` : ''
            }`,
        });
        if (name) emit('create', name);
    }

    function startRename(item: VocabItem) {
        editingId.value = item.id;
        renameDraft.value = item.name;
    }

    function saveRename(item: VocabItem) {
        const next = renameDraft.value.trim();
        editingId.value = null;
        if (next && next !== item.name) emit('rename', item.id, next);
    }

    async function onDelete(item: VocabItem) {
        const count = item.usage_count ?? 0;
        const used = `${count} ${plural(props.usageLabel, count)}`;
        const usageMessage = props.preservesLabel
            ? `${used} use this ${props.noun}; they'll keep the label.`
            : `${used} using this ${props.noun} will lose it. The ${plural(props.usageLabel, 2)} themselves stay.`;
        const ok = await confirm({
            title: `Delete "${item.name}"?`,
            message: count > 0
                    ? usageMessage
                    : `Nothing currently uses this ${props.noun}.`,
            okLabel: 'Delete',
            destructive: true,
        });
        if (ok) emit('delete', item.id);
    }
</script>

<style scoped lang="scss">
    .settings-page {
        position: relative;
    }
    .vocab-list {
        border-top: 1px solid color-mix(in srgb, var(--text-primary) 8%, transparent);
        border-bottom: 1px solid color-mix(in srgb, var(--text-primary) 8%, transparent);
    }
    .vocab-list__item {
        padding: 10px 4px;
    }
    // Name + tally on one line, same size; the tally wraps under the name
    // rather than squeezing it when the row runs out of width.
    .vocab-row {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        gap: var(--space-2, 8px);
    }
</style>
