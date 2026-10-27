import { describe, expect, it } from 'vitest';
import { ref } from 'vue';
import {
    choiceFilter, listFilter, numberFilter, stateFilter, toggleFilter, useFilterRegistry,
} from 'src/composables/useFilterRegistry';

describe('useFilterRegistry', () => {
    it('counts the filters that narrow the list and clears them all', () => {
        const favourites = ref(true);
        const cuisine = ref<string | null>('thai');
        const kcalMax = ref<number | null>(Number.NaN);
        const tags = ref<string[]>(['vegan']);
        const planned = ref<'off' | 'planned' | 'unplanned'>('planned');
        const registry = useFilterRegistry([
            toggleFilter(favourites), choiceFilter(cuisine), numberFilter(kcalMax),
            listFilter(tags), stateFilter(planned, 'off'),
        ]);

        // NaN is not a threshold, so it doesn't count.
        expect(registry.activeCount.value).toBe(4);
        registry.clearAll();
        expect(registry.activeCount.value).toBe(0);
        expect([favourites.value, cuisine.value, kcalMax.value, tags.value, planned.value])
            .toEqual([false, null, null, [], 'off']);
    });
});
