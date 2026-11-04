<template>
    <!--
        Generalised tri-state include/exclude filter. Each option cycles
        through +/-/neutral on click; the dropdown stays open while
        cycling so the user can flip several in one pass.

        Generalised in three axes:
        - `options[].category?` — when present, options are grouped under a
          header (matches the original DietaryTagFilter shape). When all
          options omit it, the list renders flat.
        - `options[].dotColour?` — renders a coloured dot in the avatar
          slot alongside the +/- state icon. Used by surfaces that need
          a quick at-a-glance signal per row (e.g. stock-level on the
          "Uses ingredients" filter).
        - `searchable` — adds a typeahead `q-input` at the top of the
          dropdown that case-insensitively filters by label. Essential
          for options lists with more than ~30 rows.

        Single component, multiple consumers (R-001).

        2026-08-19 — the trigger is a `BaseFilterField` (a real `q-field`), not
        the `q-btn-dropdown` it used to be. Owner feedback was that these
        filters read as a different colour to their `q-select` neighbours, never
        brightened on focus, and put their caret mid-control instead of at the
        field's right edge. All three were symptoms of one cause: it was a
        button sitting in a row of fields. See `BaseFilterField` for why the fix
        belongs there rather than in each page's style block.
    -->
    <BaseFilterField
        :label="label"
        :icon="icon ?? ICONS.tune"
        :summary="selectionSummary"
        :active="activeCount > 0"
        @clear="clearAll"
    >
        <div :style="{ minWidth: '260px', maxWidth: '320px' }">
            <SearchInput
                v-if="searchable"
                v-model="searchText"
                :placeholder="searchPlaceholder ?? 'Search…'"
                class="q-ma-sm"
                autofocus
            />
            <!-- Optional sort axis selector. Renders only when the caller
                 hands in `sortOptions`. A `BaseSegmented`
                 radiogroup, compact to fit the narrow panel. -->
            <div
                v-if="sortOptionsList.length > 0"
                class="tri-state-filter__sort row items-center q-px-sm q-py-xs q-gutter-sm"
            >
                <span class="text-caption dora-text-muted">Sort by</span>
                <BaseSegmented
                    v-model="activeSort"
                    :options="sortToggleOptions"
                    dense
                    aria-label="Sort by"
                />
            </div>
            <q-separator v-if="sortOptionsList.length > 0" />

            <q-list dense>
                <template v-for="group in visibleGroups" :key="group.category ?? '__flat__'">
                    <q-item-label
                        v-if="group.category"
                        header
                        class="q-pb-none"
                    >
                        {{ group.category }}
                    </q-item-label>
                    <q-item
                        v-for="opt in group.options"
                        :key="opt.value"
                        clickable
                        @click="cycle(opt.value)"
                    >
                        <q-item-section avatar>
                            <div class="row items-center q-gutter-xs no-wrap">
                                <q-icon
                                    v-if="opt.dotColour !== undefined"
                                    name="circle"
                                    size="10px"
                                    :color="opt.dotColour ?? undefined"
                                    :class="{ 'dora-text-muted': !opt.dotColour }"
                                />
                                <q-icon
                                    :name="stateIcon(opt.value)"
                                    :color="stateColour(opt.value)"
                                />
                            </div>
                        </q-item-section>
                        <q-item-section>{{ opt.label }}</q-item-section>
                    </q-item>
                </template>
                <q-item v-if="visibleGroups.length === 0 && searchText">
                    <q-item-section class="dora-text-muted">
                        No matches for "{{ searchText }}".
                    </q-item-section>
                </q-item>
                <q-item v-else-if="options.length === 0">
                    <q-item-section class="dora-text-muted">
                        Nothing to filter by yet.
                    </q-item-section>
                </q-item>
                <q-separator v-if="activeCount > 0" />
                <q-item v-if="activeCount > 0" clickable @click="clearAll">
                    <q-item-section avatar><q-icon :name="ICONS.filter_alt_off" /></q-item-section>
                    <q-item-section>Clear</q-item-section>
                </q-item>
            </q-list>
        </div>
    </BaseFilterField>
</template>

<script setup lang="ts">
    import { computed, ref } from 'vue';
    import { ICONS } from 'src/style/icons';
    import BaseFilterField from 'src/components/filters/BaseFilterField.vue';
    import BaseSegmented from 'src/components/BaseSegmented.vue';
    import SearchInput from 'src/components/SearchInput.vue';

    import type {
        TriStateOption,
        TriStateSort,
    } from 'src/components/filters/triStateFilterTypes';

    const props = withDefaults(
        defineProps<{
            options: TriStateOption[];
            include: string[];
            exclude: string[];
            /** Required: this renders as a form field's label, and B3 wants a
             *  label on every field. The old `'Filter'` default was a
             *  placeholder that said nothing, and every call site already
             *  passes a real one. */
            label: string;
            /** Trigger-button glyph. Defaults to the generic `tune` slider;
             *  callers pass the icon their concept carries elsewhere in the
             *  app (ingredients, dietary tags, tools …). */
            icon?: string;
            searchable?: boolean;
            searchPlaceholder?: string;
            sortOptions?: TriStateSort[];
            defaultSort?: string;
        }>(),
        {
            searchable: false,
            sortOptions: () => [],
        },
    );

    const emit = defineEmits<{
        (e: 'update:include', value: string[]): void;
        (e: 'update:exclude', value: string[]): void;
    }>();

    const searchText = ref('');
    // Local convenience refs so the template never accesses the optional
    // `sortOptions` prop directly (exactOptionalPropertyTypes — the type
    // resolves to `TriStateSort[] | undefined` in template scope even
    // with the `() => []` default).
    const sortOptionsList = computed<TriStateSort[]>(() => props.sortOptions ?? []);
    const sortToggleOptions = computed(() =>
        sortOptionsList.value.map((s) => ({ label: s.label, value: s.value })),
    );
    const activeSort = ref<string>(
        props.defaultSort ?? sortOptionsList.value[0]?.value ?? '',
    );

    const activeCount = computed(() => props.include.length + props.exclude.length);

    /** The value line under the field's label. Splits include from exclude
     *  because "2 selected" reads as agreement when one of them is a
     *  *ban* — the old button label collapsed both into one count. */
    const selectionSummary = computed(() => {
        const inc = props.include.length;
        const exc = props.exclude.length;
        if (inc > 0 && exc > 0) return `${inc} in · ${exc} out`;
        if (inc > 0) return `${inc} selected`;
        if (exc > 0) return `${exc} excluded`;
        return '';
    });

    const activeSortFn = computed(() => {
        const list = sortOptionsList.value;
        if (list.length === 0) return null;
        return list.find((s) => s.value === activeSort.value) ?? list[0] ?? null;
    });

    /** Sort → filter → group. Selected items always render even if they
     *  don't match the search, so the user can find what they've already
     *  picked to clear it without dropping the query. Sort runs first
     *  so categorised lists honour the chosen axis within each header. */
    const visibleGroups = computed(() => {
        const query = searchText.value.trim().toLowerCase();
        const matches = (opt: TriStateOption) => {
            if (props.include.includes(opt.value)) return true;
            if (props.exclude.includes(opt.value)) return true;
            if (!query) return true;
            return opt.label.toLowerCase().includes(query);
        };

        const sorted = activeSortFn.value
            ? [...props.options].sort(activeSortFn.value.compare)
            : props.options;

        const buckets = new Map<string | undefined, TriStateOption[]>();
        for (const opt of sorted) {
            if (!matches(opt)) continue;
            const key = opt.category;
            if (!buckets.has(key)) buckets.set(key, []);
            buckets.get(key)!.push(opt);
        }
        return [...buckets.entries()].map(([category, opts]) => ({
            category,
            options: opts,
        }));
    });

    function stateOf(value: string): 'include' | 'exclude' | 'neutral' {
        if (props.include.includes(value)) return 'include';
        if (props.exclude.includes(value)) return 'exclude';
        return 'neutral';
    }

    function stateIcon(value: string): string {
        const s = stateOf(value);
        if (s === 'include') return 'mdi-plus-circle';
        if (s === 'exclude') return 'mdi-minus-circle';
        return 'mdi-circle-outline';
    }

    function stateColour(value: string): string {
        const s = stateOf(value);
        if (s === 'include') return 'positive';
        if (s === 'exclude') return 'negative';
        return 'grey';
    }

    // neutral → include → exclude → neutral.
    function cycle(value: string) {
        const s = stateOf(value);
        const include = props.include.filter((v) => v !== value);
        const exclude = props.exclude.filter((v) => v !== value);
        if (s === 'neutral') {
            include.push(value);
        } else if (s === 'include') {
            exclude.push(value);
        }
        emit('update:include', include);
        emit('update:exclude', exclude);
    }

    function clearAll() {
        emit('update:include', []);
        emit('update:exclude', []);
    }
</script>

<style scoped lang="scss">
    // Sort row sits between the search input and the options list — give
    // it a subtle background to read as its own band rather than floating
    // in the panel padding.
    .tri-state-filter__sort {
        background: var(--surface-sunken);
        border-radius: var(--radius-md);
        margin: 0 8px 4px;
    }
    // The track, the segment shape, the active fill and the compact size are
    // all BaseSegmented's (`dense`) — nothing left to override here.
</style>
