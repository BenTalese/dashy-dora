<template>
    <BaseDialog
        :model-value="modelValue"
        title="Put away"
        closable
        card-style="min-width: 320px; max-width: 560px"
        @update:model-value="$emit('update:modelValue', $event)"
    >
        <q-card-section class="q-pb-none">
            <div class="text-caption dora-text-muted">
                Tick a group once you've put those items away. Nothing here is
                saved.
            </div>
        </q-card-section>

        <q-card-section v-if="tickedLines.length === 0">
            <q-banner rounded class="bg-grey-2">
                Nothing to put away.
            </q-banner>
        </q-card-section>

        <q-card-section v-else class="q-gutter-sm">
            <div
                v-for="group in orderedGroups"
                :key="group.key"
                class="put-away-group"
                :class="{ 'put-away-group--done': isDone(group.key) }"
            >
                <div
                    class="row items-center no-wrap put-away-group__header"
                    :class="{ 'cursor-pointer': group.locationId !== null }"
                    @click="group.locationId !== null && toggle(group.key)"
                >
                    <q-icon
                        :name="group.locationId !== null && isDone(group.key) ? ICONS.check_box : ICONS.check_box_outline_blank"
                        :color="isDone(group.key) ? 'positive' : undefined"
                        size="20px"
                        class="q-mr-sm"
                        :class="{ 'invisible': group.locationId === null }"
                    />
                    <div class="col text-weight-medium">{{ group.label }}</div>
                    <q-chip
                        dense
                        square
                        :color="isDone(group.key) ? 'positive' : 'grey-4'"
                        :text-color="isDone(group.key) ? 'white' : 'grey-8'"
                    >
                        {{ group.items.length }}
                    </q-chip>
                </div>
                <div
                    v-if="!isDone(group.key)"
                    class="put-away-group__items"
                >
                    <div
                        v-for="line in group.items"
                        :key="line.line_id"
                        class="row items-center no-wrap put-away-item"
                    >
                        <div class="col ellipsis">{{ line.stock_item_name }}</div>
                        <BaseButton
                            v-if="group.locationId === null && line.stock_item_id"
                            variant="ghost"
                            dense
                            size="sm"
                            :icon="ICONS.place"
                            label="Assign"
                            :loading="assigning[line.line_id] === true"
                            @click="openAssign(line)"
                        />
                    </div>
                </div>
            </div>
        </q-card-section>

        <template #actions="{ cancel }">
            <BaseButton variant="primary" label="Done" @click="cancel" />
        </template>

        <!-- Inline location picker for a single unsorted item. Kept inside the
             put-away dialog rather than opening the full edit-stock-item flow
             because the whole point is a fast one-tap sort. -->
        <q-dialog v-model="assignOpen" @hide="onAssignHide">
            <q-card style="min-width: 300px; max-width: 400px">
                <q-card-section>
                    <div class="text-subtitle1">Assign a location</div>
                    <div v-if="assignTarget" class="text-caption dora-text-muted">
                        {{ assignTarget.stock_item_name }}
                    </div>
                </q-card-section>
                <q-card-section class="q-pt-none">
                    <q-select
                        v-model="assignChoice"
                        :options="locationOptions"
                        emit-value
                        map-options
                        use-input
                        fill-input
                        hide-selected
                        input-debounce="200"
                        clearable
                        outlined
                        dense
                        label="Location"
                        autofocus
                        @filter="filterLocations"
                    />
                </q-card-section>
                <q-card-actions align="right">
                    <BaseButton variant="ghost" label="Cancel" v-close-popup />
                    <BaseButton
                        variant="primary"
                        label="Save"
                        :disable="!assignChoice"
                        :loading="assignSaving"
                        @click="commitAssign"
                    />
                </q-card-actions>
            </q-card>
        </q-dialog>
    </BaseDialog>
</template>

<script lang="ts" setup>
    import { computed, onMounted, reactive, ref, watch } from 'vue';
    import { useQuasar } from 'quasar';
    import { ICONS } from 'src/style/icons';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import { useLocationStore } from 'src/stores/locationStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import type { LocationNode } from 'src/models/location';
    import type { ShoppingListLine } from 'src/models/shoppingList';

    const props = defineProps<{
        modelValue: boolean;
        lines: ShoppingListLine[];
    }>();
    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
        (e: 'assigned', payload: { line_id: string; stock_item_id: string; stock_location_id: string }): void;
    }>();

    const $q = useQuasar();
    const stockItemStore = useStockItemStore();
    const locationStore = useLocationStore();

    onMounted(() => { void locationStore.ensureLoadedAsync(); });
    // Reload the tree each time the dialog opens so a location the user
    // added in another tab shows up in the picker without a page reload.
    watch(() => props.modelValue, (open) => {
        if (open) void locationStore.ensureLoadedAsync();
        else resetLocalState();
    });

    const tickedLines = computed(() =>
        props.lines.filter((l) => l.is_ticked && l.stock_item_id),
    );

    // Groups are keyed by stock_location_id, with `null` reserved for the
    // "(No location)" bucket. The label uses the line's server-supplied
    // breadcrumb so the group heading matches the rest of the app.
    type Group = {
        key: string;
        locationId: string | null;
        label: string;
        items: ShoppingListLine[];
    };

    const orderedGroups = computed<Group[]>(() => {
        const byLocation = new Map<string, Group>();
        for (const line of tickedLines.value) {
            const locId = line.stock_location_id;
            const key = locId ?? '__unsorted__';
            let group = byLocation.get(key);
            if (!group) {
                const label = locId
                    ? (line.stock_location_breadcrumb.join(' › ') || 'Unnamed location')
                    : '(No location)';
                group = { key, locationId: locId, label, items: [] };
                byLocation.set(key, group);
            }
            group.items.push(line);
        }
        const out = Array.from(byLocation.values());
        // Sort by label; unsorted always at the end so a tidy pantry doesn't
        // hide the "you still need to sort these" items above real groups.
        out.sort((a, b) => {
            if (a.locationId === null) return 1;
            if (b.locationId === null) return -1;
            return a.label.localeCompare(b.label);
        });
        return out;
    });

    const doneGroups = reactive(new Set<string>());
    const assigning = reactive<Record<string, boolean>>({});

    function isDone(key: string): boolean {
        return doneGroups.has(key);
    }
    function toggle(key: string): void {
        if (doneGroups.has(key)) doneGroups.delete(key);
        else doneGroups.add(key);
    }

    function resetLocalState(): void {
        doneGroups.clear();
        for (const k of Object.keys(assigning)) delete assigning[k];
        assignOpen.value = false;
        assignTarget.value = null;
        assignChoice.value = null;
    }

    // Reuses the same walked-tree path options the stock filter + create
    // dialog use, so the label shape is consistent across the app.
    type LocationOption = { label: string; value: string };
    const allLocationOptions = computed<LocationOption[]>(() => {
        const out: LocationOption[] = [];
        const walk = (nodes: LocationNode[], prefix: string) => {
            for (const n of nodes) {
                const path = prefix ? `${prefix} › ${n.name}` : n.name;
                out.push({ label: path, value: n.location_id });
                walk(n.children, path);
            }
        };
        walk(locationStore.tree, '');
        return out.sort((a, b) => a.label.localeCompare(b.label));
    });
    const locationOptions = ref<LocationOption[]>([]);
    watch(allLocationOptions, (v) => { locationOptions.value = v; }, { immediate: true });
    function filterLocations(val: string, update: (cb: () => void) => void) {
        update(() => {
            const needle = val.toLowerCase();
            locationOptions.value = needle
                ? allLocationOptions.value.filter((o) => o.label.toLowerCase().includes(needle))
                : allLocationOptions.value;
        });
    }

    const assignOpen = ref(false);
    const assignTarget = ref<ShoppingListLine | null>(null);
    const assignChoice = ref<string | null>(null);
    const assignSaving = ref(false);

    function openAssign(line: ShoppingListLine): void {
        assignTarget.value = line;
        assignChoice.value = null;
        assignOpen.value = true;
    }

    function onAssignHide(): void {
        if (!assignSaving.value) {
            assignTarget.value = null;
            assignChoice.value = null;
        }
    }

    async function commitAssign(): Promise<void> {
        const target = assignTarget.value;
        const locationId = assignChoice.value;
        if (!target?.stock_item_id || !locationId) return;

        assignSaving.value = true;
        assigning[target.line_id] = true;
        try {
            await stockItemStore.updateStockItemAsync({
                stock_item_id: target.stock_item_id,
                stock_location_id: locationId,
            });
            emit('assigned', {
                line_id: target.line_id,
                stock_item_id: target.stock_item_id,
                stock_location_id: locationId,
            });
            $q.notify({ type: 'positive', message: `Sorted ${target.stock_item_name}` });
            assignOpen.value = false;
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Couldn\'t save the location. Try again.',
                caption: String(err),
            });
        } finally {
            assignSaving.value = false;
            delete assigning[target.line_id];
        }
    }
</script>

<style scoped>
    .put-away-group {
        border: 1px solid var(--surface-border);
        border-radius: 8px;
        padding: 8px 12px;
    }
    .put-away-group--done {
        opacity: 0.55;
    }
    .put-away-group__header {
        min-height: 32px;
    }
    .put-away-group__items {
        margin-top: 6px;
        padding-left: 28px;
        border-left: 2px solid var(--surface-border);
        margin-left: 10px;
    }
    .put-away-item {
        min-height: 30px;
    }
</style>
