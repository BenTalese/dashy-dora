<template>
    <!-- New-backup dialog: section picker with a sensitive-data warning. -->
    <BaseDialog v-model="open" card-style="min-width: 480px; max-width: 640px">
        <q-card-section>
            <div class="text-h6">New backup</div>
            <div class="text-caption dora-text-muted q-mt-xs">
                Pick which sections to include. Passwords are never included.
            </div>
        </q-card-section>
        <q-separator />
        <q-card-section class="q-pb-none">
            <q-banner
                v-if="sensitiveLabel"
                class="dora-bg-warning-soft q-mb-md text-caption"
                dense
                rounded
            >
                <template #avatar>
                    <q-icon :name="ICONS.warning" color="warning" />
                </template>
                This backup will include {{ sensitiveLabel }}.
            </q-banner>
            <q-expansion-item
                v-for="(group, idx) in groups"
                :key="group.category"
                :label="group.category"
                :caption="`${countSelectedInGroup(group)} of ${group.sections.length} selected`"
                :default-opened="idx === 0"
                dense
                header-class="q-px-none"
            >
                <div class="row items-center q-gutter-x-sm q-mb-xs">
                    <BaseButton
                        variant="subtle"
                        dense
                        label="All"
                        @click="toggleGroup(group, true)"
                    />
                    <BaseButton
                        variant="subtle"
                        dense
                        label="None"
                        @click="toggleGroup(group, false)"
                    />
                </div>
                <q-checkbox
                    v-for="section in group.sections"
                    :key="section.key"
                    v-model="selected[section.key]"
                    dense
                    :label="section.label"
                    class="block"
                />
            </q-expansion-item>
        </q-card-section>
        <template #actions>
            <BaseButton variant="ghost" label="Cancel" v-close-popup />
            <BaseButton
                variant="primary"
                :icon="ICONS.cloud_download"
                label="Generate"
                :loading="generating"
                :disable="generating || selectedKeys.length === 0"
                @click="emit('generate', selectedKeys)"
            />
        </template>
    </BaseDialog>
</template>

<script lang="ts" setup>
    import { computed, ref, watch } from 'vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import { sensitiveSectionsLabel } from 'src/helpers/backupSections';
    import type { BackupSection } from 'src/services/api/dataApiService';
    import { ICONS } from 'src/style/icons';

    const open = defineModel<boolean>({ required: true });
    const props = defineProps<{
        sections: BackupSection[];
        generating: boolean;
    }>();
    const emit = defineEmits<{ generate: [keys: string[]] }>();

    // Seeded from the server's defaults whenever the catalogue arrives.
    const selected = ref<Record<string, boolean>>({});
    watch(() => props.sections, (sections) => {
        selected.value = Object.fromEntries(sections.map((s) => [s.key, s.default_on]));
    }, { immediate: true });

    interface SectionGroup {
        category: string;
        sections: BackupSection[];
    }
    const groups = computed<SectionGroup[]>(() => {
        const byCategory = new Map<string, BackupSection[]>();
        for (const s of props.sections) {
            const bucket = byCategory.get(s.category) ?? [];
            bucket.push(s);
            byCategory.set(s.category, bucket);
        }
        return Array.from(byCategory.entries()).map(([category, sections]) => ({
            category,
            sections,
        }));
    });

    function countSelectedInGroup(group: SectionGroup): number {
        return group.sections.filter((s) => selected.value[s.key]).length;
    }

    function toggleGroup(group: SectionGroup, on: boolean) {
        for (const s of group.sections) {
            selected.value[s.key] = on;
        }
    }

    const selectedKeys = computed(() =>
        props.sections.filter((s) => selected.value[s.key]).map((s) => s.key),
    );
    const sensitiveLabel = computed(() => sensitiveSectionsLabel(props.sections, selectedKeys.value));
</script>
