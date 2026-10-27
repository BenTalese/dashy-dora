<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Stock locations"
            description="Where things live. Zones (e.g. Pantry), areas inside them (e.g. Top shelf), and sections inside those (e.g. Left). Items can go at any level."
            :icon="ICONS.place"
        >
            <template #actions>
                <BaseButton
                    :icon="ICONS.add"
                    label="New zone"
                    @click="onAddChild(null, 'zone')"
                />
            </template>
        </SettingsPageHeader>

        <q-banner v-if="loadError" class="dora-bg-negative-soft text-negative q-mb-md" dense rounded>
            {{ loadError }}
        </q-banner>

        <q-input
            v-if="tree.length > 0"
            v-model="search"
            dense
            outlined
            clearable
            debounce="150"
            placeholder="Find a zone, area or section"
            class="q-mb-md"
        >
            <template #prepend>
                <q-icon :name="ICONS.search" />
            </template>
        </q-input>

        <div class="zone-list">
            <LocationZoneCard
                v-for="zone in visibleTree"
                :key="zone.location_id"
                :node="zone"
                :expanded="isExpanded(zone.location_id)"
                :filtered="isSearching"
                @toggle="toggleExpanded"
                @rename="onRename"
                @delete="onDelete"
                @add-child="onAddChild"
                @view-items="onViewItems"
            />
        </div>

        <div v-if="!loading && tree.length === 0" class="settings-empty">
            <q-icon :name="ICONS.place" size="40px" class="settings-empty__icon" />
            <p class="settings-empty__line">
                Nothing mapped out yet. Start with a zone, like a room, cupboard or fridge.
            </p>
            <BaseButton :icon="ICONS.add" label="New zone" @click="onAddChild(null, 'zone')" />
        </div>

        <div
            v-else-if="!loading && tree.length > 0 && visibleTree.length === 0"
            class="settings-empty"
        >
            <p class="settings-empty__line">Nothing here matches "{{ search }}".</p>
        </div>

        <q-inner-loading :showing="loading && tree.length === 0">
            <AppSpinner size="48px" />
        </q-inner-loading>
    </div>
</template>

<script lang="ts" setup>
    // The location tree is fixed at exactly three levels — zone → area →
    // section — so this page renders each level with the visual that suits it
    // (card → row → chip) rather than as one uniform recursive indented list.
    // See LocationZoneCard for the rationale.
    import { useSettingsSave } from 'src/composables/useSettingsSave';
    import AppSpinner from 'src/components/AppSpinner.vue';
    import { ICONS } from 'src/style/icons';
    import { useQuasar } from 'quasar';
    import { computed, onMounted, ref, watch } from 'vue';
    import { useRouter } from 'vue-router';
    import type { LocationKind, LocationNode } from 'src/models/location';
    import { useLocationStore } from 'src/stores/locationStore';
    import { useListState } from 'src/composables/useListState';
    import { filterLocationTree } from 'src/helpers/locationDisplay';
    import BaseButton from 'src/components/BaseButton.vue';
    import LocationZoneCard from 'src/components/settings/LocationZoneCard.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';

    // Which zones the user left open. Presentation state, so it belongs to the
    // client (R-003).
    //
    // R-026 carve-out: this persists across a full reload via `localStorage`,
    // which the rule normally forbids for list-page state. It qualifies under
    // the documented exception — same shape as `useFilterPanelExpanded`
    // (FU-121): an ambient display preference, not a filter value. Nothing is
    // hidden by a collapsed zone (the card, its name and its counts all still
    // render), so a stale saved value can't strand anyone on an empty list,
    // which is the failure mode the rule exists to prevent. The search text
    // below — which *is* a filter value — goes through `useListState` as the
    // rule requires.
    const EXPANDED_STORAGE_KEY = 'dora.settings.stockLocations.expandedZones';

    const $q = useQuasar();
    const router = useRouter();
    const locationStore = useLocationStore();

    const tree = computed(() => locationStore.tree);
    const loading = computed(() => locationStore.loading);
    const loadError = computed(() => locationStore.loadError);

    // R-026 — search text survives navigating to a zone's items and back, and
    // resets on a full reload.
    const { search } = useListState('settings-stock-locations', () => ({
        search: ref(''),
    }));
    const expanded = ref<Set<string>>(loadExpanded());

    // Searching implies "show me what you found", so matches expand regardless
    // of the persisted collapse state — but we don't write that back, so
    // clearing the box restores what the user actually chose.
    const visibleTree = computed(() =>
        filterLocationTree(tree.value, search.value ?? ''),
    );
    const isSearching = computed(() => (search.value ?? '').trim().length > 0);

    function isExpanded(id: string): boolean {
        return isSearching.value || expanded.value.has(id);
    }

    function loadExpanded(): Set<string> {
        try {
            const raw = localStorage.getItem(EXPANDED_STORAGE_KEY);
            const parsed: unknown = raw ? JSON.parse(raw) : null;
            if (Array.isArray(parsed)) {
                return new Set(parsed.filter((v): v is string => typeof v === 'string'));
            }
        } catch {
            // Corrupt or unavailable storage is not worth a toast — the page
            // just opens collapsed.
        }
        return new Set();
    }

    function persistExpanded() {
        try {
            localStorage.setItem(
                EXPANDED_STORAGE_KEY,
                JSON.stringify([...expanded.value]),
            );
        } catch {
            // Private-mode / quota — expansion just won't survive the reload.
        }
    }

    function toggleExpanded(id: string) {
        // While searching every card is forced open, so the chevron's job is to
        // set the state the user returns to once the box is cleared.
        if (expanded.value.has(id)) expanded.value.delete(id);
        else expanded.value.add(id);
        persistExpanded();
    }

    const { notifyError } = useSettingsSave();

    /** Prompt for a name. Matches the create/rename convention the sibling
     *  taxonomy pages use (VocabListEditor) — one anatomy per job, D-015. */
    function promptForName(title: string, message: string, initial = ''): Promise<string | null> {
        return new Promise((resolve) => {
            $q.dialog({
                title,
                message,
                prompt: { model: initial, type: 'text' },
                cancel: { noCaps: true },
            })
                .onOk((v: string) => resolve(v.trim()))
                .onCancel(() => resolve(null))
                .onDismiss(() => resolve(null));
        });
    }

    function childKind(parentKind: LocationKind | null): LocationKind | null {
        if (parentKind === null) return 'zone';
        if (parentKind === 'zone') return 'area';
        if (parentKind === 'area') return 'section';
        return null;
    }

    async function onAddChild(parent: LocationNode | null, forcedKind?: LocationKind) {
        const kind = forcedKind ?? childKind(parent?.kind ?? null);
        if (!kind) return;
        const name = await promptForName(`New ${kind}`, `What's this ${kind} called?`);
        if (!name) return;
        try {
            await locationStore.createAsync({
                name,
                kind,
                parent_id: parent?.location_id ?? null,
            });
            // Open the container you just added to, and the new zone itself —
            // otherwise the thing you created is invisible behind a chevron.
            const openId = kind === 'area' ? parent?.location_id : null;
            if (openId) {
                expanded.value.add(openId);
                persistExpanded();
            }
        } catch (err) {
            notifyError(`Could not add ${kind}.`, err);
        }
    }

    async function onRename(node: LocationNode) {
        // Explicit dialog rather than the old inline field: that one saved on
        // blur, so clicking any other control on the page silently committed
        // whatever was typed.
        const next = await promptForName(
            `Rename ${node.kind}`,
            `What should "${node.name}" be called?`,
            node.name,
        );
        if (!next || next === node.name) return;
        try {
            await locationStore.updateAsync(node.location_id, { name: next });
        } catch (err) {
            notifyError('Could not rename.', err);
        }
    }

    async function onDelete(node: LocationNode) {
        const subtreeItems = node.descendant_item_count;
        const hasChildren = node.children.length > 0;
        const messageParts: string[] = [];
        if (hasChildren) {
            messageParts.push(
                `Everything under "${node.name}" (areas, sections) will also be removed.`
            );
        }
        if (subtreeItems > 0) {
            messageParts.push(
                `${subtreeItems} item${subtreeItems === 1 ? '' : 's'} stored here will become unassigned. The items stay in your stock.`
            );
        }
        if (messageParts.length === 0) {
            messageParts.push('Nothing is stored here.');
        }

        const ok = await new Promise<boolean>((resolve) => {
            $q.dialog({
                title: `Delete "${node.name}"?`,
                message: messageParts.join(' '),
                cancel: { noCaps: true },
                ok: { label: 'Delete', color: 'negative', noCaps: true },
            })
                .onOk(() => resolve(true))
                .onCancel(() => resolve(false))
                .onDismiss(() => resolve(false));
        });
        if (!ok) return;
        try {
            await locationStore.deleteAsync(node.location_id);
            expanded.value.delete(node.location_id);
            persistExpanded();
        } catch (err) {
            notifyError('Could not delete.', err);
        }
    }

    function onViewItems(node: LocationNode) {
        void router.push({ path: '/stock', query: { location_id: node.location_id } });
    }

    // A single zone has nothing to choose between — open it rather than making
    // the first visit a click.
    watch(tree, (next) => {
        if (next.length === 1 && expanded.value.size === 0) {
            const only = next[0];
            if (only) {
                expanded.value.add(only.location_id);
                persistExpanded();
            }
        }
    }, { immediate: true });

    onMounted(() => {
        void locationStore.ensureLoadedAsync();
    });
</script>

<style scoped lang="scss">
    .settings-page { display: flex; flex-direction: column; position: relative; }
    .zone-list {
        display: flex;
        flex-direction: column;
        gap: var(--space-4);
    }
    .settings-empty {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--space-3);
        padding: var(--space-10) var(--space-4);
        text-align: center;
    }
    .settings-empty__icon { color: var(--text-muted); }
    .settings-empty__line {
        margin: 0;
        max-width: 46ch;
        color: var(--text-secondary);
        font-size: 0.875rem;
        line-height: 1.5;
    }
</style>
