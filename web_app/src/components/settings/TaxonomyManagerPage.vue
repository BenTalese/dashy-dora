<template>
    <!--
        Settings rebuild Phase 2 (R-001 extraction) — page-level wrapper for a
        single recipe-taxonomy type. Owns the load + busy state and the
        create/rename/delete/reorder round-trips; delegates the list + dialogs
        to the existing `VocabListEditor`. The five Recipe* pages under
        Kitchen setup are thin callers of this, parameterised by API calls.
    -->
    <VocabListEditor
        :title="title"
        :description="description"
        :icon="icon"
        :noun="noun"
        :noun-plural="nounPlural"
        :usage-label="usageLabel ?? 'recipe'"
        :preserves-label="preservesLabel ?? false"
        :reorderable="reorderable ?? false"
        :create-hint="createHint ?? ''"
        v-bind="emptyActionBinding"
        :items="items"
        :loading="loading"
        :busy="busy"
        @create="onCreate"
        @rename="onRename"
        @delete="onDelete"
        @reorder="onReorder"
    />
</template>

<script lang="ts" setup>
    import { useSettingsSave } from 'src/composables/useSettingsSave';
    import VocabListEditor from 'src/components/settings/VocabListEditor.vue';
    import { computed, onMounted, ref } from 'vue';

    export type VocabItem = { id: string; name: string; usage_count?: number };

    const props = withDefaults(
        defineProps<{
            title: string;
            description: string;
            /** Heading icon — must match this page's sidebar entry in SettingsShell. */
            icon: string;
            noun: string;
            nounPlural: string;
            usageLabel?: string;
            preservesLabel?: boolean;
            reorderable?: boolean;
            // Empty-state tail shown under "No {nounPlural} yet." Optional —
            // VocabListEditor falls back to the recipe-shaped default when
            // unset.
            emptyAction?: string;
            // Example names shown in the create prompt, e.g. `"Dairy", "Snacks"`.
            createHint?: string;
            // Data access is injected by the caller so this wrapper stays
            // service-agnostic (R-003: each type already owns its CRUD
            // endpoints; we don't duplicate that knowledge here).
            load: () => Promise<VocabItem[]>;
            create: (name: string) => Promise<unknown>;
            rename: (id: string, name: string) => Promise<unknown>;
            remove: (id: string) => Promise<unknown>;
            // Only supplied by the reorderable type (meal slots). Receives the
            // moved id, the direction, and the current ordered item list so the
            // caller can recompute sequence.
            reorder?: (id: string, direction: 'up' | 'down', items: VocabItem[]) => Promise<unknown>;
        }>(),
        { usageLabel: 'recipe', preservesLabel: false, reorderable: false },
    );

    const items = ref<VocabItem[]>([]);
    const loading = ref(false);
    const busy = ref(false);
    // Only forward `emptyAction` when the caller set it, so VocabListEditor's
    // `withDefaults` keeps the recipe-shaped fallback for the four pages that
    // don't override (exactOptionalPropertyTypes is on).
    const emptyActionBinding = computed(() =>
        props.emptyAction !== undefined ? { emptyAction: props.emptyAction } : {},
    );

    const { notifyError } = useSettingsSave();

    async function reload() {
        loading.value = true;
        try {
            items.value = await props.load();
        } catch (err) {
            notifyError(`Could not load ${props.nounPlural}.`, err);
        } finally {
            loading.value = false;
        }
    }

    async function run(action: () => Promise<unknown>) {
        busy.value = true;
        try {
            await action();
            await reload();
        } catch (err) {
            notifyError('Could not save the change.', err);
        } finally {
            busy.value = false;
        }
    }

    const onCreate = (name: string) => run(() => props.create(name));
    const onRename = (id: string, name: string) => run(() => props.rename(id, name));
    const onDelete = (id: string) => run(() => props.remove(id));
    const onReorder = (id: string, direction: 'up' | 'down') => {
        if (!props.reorder) return;
        return run(() => props.reorder!(id, direction, items.value));
    };

    onMounted(reload);
</script>
