import { computed, type ComputedRef, type Ref } from 'vue';

/** One filter on a list page: whether it narrows the list right now, and how
 *  to switch it off. A page declares its filters once and derives the count,
 *  the "anything filtered?" check and Clear from that one list (finalisation
 *  01-R22), so adding a filter is one line rather than three. */
export type FilterEntry = { isActive: () => boolean; reset: () => void };

export const toggleFilter = (value: Ref<boolean>): FilterEntry => ({
    isActive: () => value.value,
    reset: () => { value.value = false; },
});

/** A single pick (or any value) that is "off" when null. */
export const choiceFilter = <T>(value: Ref<T | null>): FilterEntry => ({
    isActive: () => value.value !== null,
    reset: () => { value.value = null; },
});

/** A numeric threshold that is "off" when null or not a finite number. */
export const numberFilter = (value: Ref<number | null>): FilterEntry => ({
    isActive: () => value.value !== null && Number.isFinite(value.value),
    reset: () => { value.value = null; },
});

export const listFilter = <T>(value: Ref<T[]>): FilterEntry => ({
    isActive: () => value.value.length > 0,
    reset: () => { value.value = []; },
});

/** A tri-state (or wider) filter with a named "off" value. */
export const stateFilter = <T>(value: Ref<T>, off: T): FilterEntry => ({
    isActive: () => value.value !== off,
    reset: () => { value.value = off; },
});

export function useFilterRegistry(filters: FilterEntry[]): {
    activeCount: ComputedRef<number>;
    clearAll: () => void;
} {
    return {
        activeCount: computed(() => filters.filter((f) => f.isActive()).length),
        clearAll: () => filters.forEach((f) => f.reset()),
    };
}
