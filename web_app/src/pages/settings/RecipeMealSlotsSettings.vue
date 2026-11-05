<template>
    <TaxonomyManagerPage
        title="Meal slots"
        description="The meal slot options shown in meal plans and on recipes."
        noun="meal slot"
        noun-plural="meal slots"
        usage-label="planned meal"
        empty-action="Create one to schedule meals against."
        :preserves-label="true"
        :reorderable="true"
        :load="load"
        :create="create"
        :rename="rename"
        :remove="remove"
        :reorder="reorder"
    />
</template>

<script lang="ts" setup>
    import TaxonomyManagerPage, { type VocabItem } from 'src/components/settings/TaxonomyManagerPage.vue';
    import { useMealSlotStore } from 'src/stores/mealSlotStore';

    // R-003 — this page edits a vocabulary the planner and both recipe
    // `time_of_day` pickers read from `mealSlotStore`, so every write goes
    // through the store rather than the api service. Talking to the service
    // directly (what this page did until 2026-09-01) left the store's cache
    // holding the pre-edit vocabulary for the rest of the session: the planner
    // kept offering a deleted slot, and arming it produced "Could not update
    // the plan" because the server's write-time slot check rejected a name that
    // no longer existed.
    const store = useMealSlotStore();

    // Slots come back sorted (sequence, then name) from the list endpoint; the
    // up/down controls rely on that order. `usage_count` carries the tally the
    // generic editor renders.
    const load = async (): Promise<VocabItem[]> => {
        await store.getMealSlotsAsync();
        return store.mealSlots.map(
            (s) => ({ id: s.meal_slot_id, name: s.name, usage_count: s.usage_count }),
        );
    };
    const create = (name: string) => store.createAsync(name);
    const rename = (id: string, name: string) => store.renameAsync(id, name);
    const remove = (id: string) => store.removeAsync(id).then(() => undefined);

    // Swap the moved slot's position with its up/down neighbour, then persist
    // the new ordering in one reorder call. `items` is already in display
    // order from the wrapper.
    const reorder = (id: string, direction: 'up' | 'down', items: VocabItem[]) => {
        const ordered = [...items];
        const index = ordered.findIndex((s) => s.id === id);
        const target = direction === 'up' ? index - 1 : index + 1;
        if (index < 0 || target < 0 || target >= ordered.length) return Promise.resolve();
        [ordered[index], ordered[target]] = [ordered[target]!, ordered[index]!];
        const slots = ordered.map((s, i) => ({ meal_slot_id: s.id, sequence: i }));
        return store.reorderAsync({ slots });
    };
</script>
