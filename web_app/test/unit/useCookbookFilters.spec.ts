import { beforeEach, describe, expect, it } from 'vitest';
import { clearAllListState } from 'src/composables/useListState';
import { useCookbookFilters } from 'src/composables/useCookbookFilters';

// FU-934 — the cookbook page and its filter panel each call this and must get
// the same refs; Clear all must reset every filter and the search, not the sort.
describe('useCookbookFilters', () => {
    beforeEach(() => clearAllListState());

    it('hands the page and the panel the same session refs', () => {
        const page = useCookbookFilters();
        const panel = useCookbookFilters();
        panel.favouritesOnly.value = true;
        panel.toolsInclude.value = ['wok'];
        panel.sortBy.value = 'kcal';
        expect(page.favouritesOnly.value).toBe(true);
        expect(page.toolsInclude.value).toEqual(['wok']);
        expect(page.sortBy.value).toBe('kcal');
        expect(page.activeFilterCount.value).toBe(2);
    });

    it('counts every filter, ignores search and sort, and clears filters plus search', () => {
        const f = useCookbookFilters();
        f.searchText.value = 'soup';
        f.sortBy.value = 'difficulty';
        expect(f.activeFilterCount.value).toBe(0);
        expect(f.hasAnyFilter.value).toBe(true);

        f.plannedFilterState.value = 'exclude';
        f.servesMin.value = Number.NaN; // a cleared numeric input is not a bound
        f.kcalMax.value = 600;
        f.collectionFilter.value = '__none__';
        f.excludesStockItemIds.value = ['x'];
        f.dietaryTagsExclude.value = ['nuts'];
        expect(f.activeFilterCount.value).toBe(5);

        f.clearFilters();
        expect(f.activeFilterCount.value).toBe(0);
        expect(f.hasAnyFilter.value).toBe(false);
        expect(f.searchText.value).toBe('');
        expect(f.plannedFilterState.value).toBe('off');
        expect(f.servesMin.value).toBeNull();
        expect(f.sortBy.value).toBe('difficulty');
    });
});
