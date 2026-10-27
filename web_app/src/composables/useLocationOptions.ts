/**
 * Path-labelled location options ("Pantry › Middle shelf") for a searchable
 * q-select, with Quasar's local-filter narrowing. One copy for every location
 * picker (finalisation 05-R25).
 */
import { computed, ref, watch } from 'vue';
import type { LocationNode } from 'src/models/location';

export type LocationOption = { label: string; value: string };

type ReadList<T> = readonly T[] | T[];
type TreeNode = Pick<LocationNode, 'location_id' | 'name'> & { children: ReadList<TreeNode> };

export function locationPathOptions(tree: ReadList<TreeNode>): LocationOption[] {
    const out: LocationOption[] = [];
    const walk = (nodes: ReadList<TreeNode>, prefix: string) => {
        for (const n of nodes) {
            const path = prefix ? `${prefix} › ${n.name}` : n.name;
            out.push({ label: path, value: n.location_id });
            walk(n.children, path);
        }
    };
    walk(tree, '');
    return out.sort((a, b) => a.label.localeCompare(b.label));
}

export function useLocationOptions(tree: () => ReadList<TreeNode>) {
    const allLocationOptions = computed(() => locationPathOptions(tree()));
    // The bound list narrows on type and resets to the full set when the
    // query is cleared.
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
    return { allLocationOptions, locationOptions, filterLocations };
}
