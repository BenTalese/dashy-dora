<template>
    <!-- The stock-item page's History tab (FU-934 split). C-1b.5 / INV-7 /
         L139: one lifecycle timeline merging level changes, waste, list adds,
         purchases, cooks and expiry edits, plus synthetic Opened / Checked
         rows — built by `helpers/lifecycleTimeline`. Date-sorted, newest
         first; entries colour-keyed by event kind. DR-13: a run of the same
         event collapses into one row that opens in place, and chips filter by
         kind. Multi-root on purpose: the panel's DOM is what it was before
         the split. -->
    <div v-if="lifecycleEvents.length === 0" class="dora-text-muted text-caption q-pa-md">
        Nothing logged for this item yet.
    </div>
    <div v-else-if="presentKinds.length > 1" class="history-filters q-px-md q-pt-md" role="group" aria-label="Show events">
        <FilterChip
            v-for="kind in presentKinds"
            :key="kind"
            :model-value="selectedKinds.has(kind)"
            @update:model-value="toggleKind(kind)"
        >
            {{ LIFECYCLE_KIND_LABELS[kind] }}
        </FilterChip>
    </div>
    <q-timeline v-if="rows.length > 0" color="primary">
        <template v-for="row in rows" :key="row.type === 'run' ? row.id : row.event.id">
            <q-timeline-entry
                v-if="row.type === 'event'"
                :title="row.event.title"
                :subtitle="formatEventAt(row.event.at)"
                :icon="row.event.icon"
                :color="row.event.color"
            >
                <div v-if="row.event.body" class="dora-text-secondary">
                    {{ row.event.body }}
                </div>
            </q-timeline-entry>
            <q-timeline-entry
                v-else
                :title="`${row.title} ×${row.events.length}`"
                :subtitle="formatRunSpan(row.events)"
                :icon="row.events[0]!.icon"
                :color="row.events[0]!.color"
            >
                <BaseButton
                    variant="subtle"
                    dense
                    :label="openRuns.has(row.id) ? 'Hide' : 'Show all'"
                    :aria-expanded="openRuns.has(row.id) ? 'true' : 'false'"
                    @click="toggleRun(row.id)"
                />
                <ul v-if="openRuns.has(row.id)" class="history-run">
                    <li v-for="ev in row.events" :key="ev.id">
                        <span class="dora-text-muted">{{ formatEventAt(ev.at) }}</span>
                        <span>{{ ev.title }}</span>
                        <span v-if="ev.body" class="dora-text-secondary">{{ ev.body }}</span>
                    </li>
                </ul>
            </q-timeline-entry>
        </template>
    </q-timeline>
    <div
        v-else-if="lifecycleEvents.length > 0"
        class="dora-text-muted text-caption q-pa-md"
    >
        Nothing of that kind logged.
    </div>
    <!-- 2026-06-30 — honest truncation footer. Server caps
         each event kind at HISTORY_PER_KIND_CAP (50) and
         reports what got dropped as `history_older_count`.
         When the number is 0 the footer is silent; the old
         behaviour was a silent client-side slice(0, 60)
         which hid arbitrary truncation. -->
    <div
        v-if="detail && (detail.history_older_count ?? 0) > 0"
        class="dora-text-muted text-caption q-pa-md q-pl-none text-center"
    >
        {{ detail.history_older_count }} older event{{ (detail.history_older_count ?? 0) === 1 ? '' : 's' }} not shown
    </div>
</template>

<script lang="ts" setup>
    import { computed, ref } from 'vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import FilterChip from 'src/components/chips/FilterChip.vue';
    import { useStockItemDetail } from 'src/composables/useStockItemDetail';
    import {
        buildLifecycleTimeline,
        formatEventAt,
        formatRunSpan,
        groupLifecycleEvents,
        LIFECYCLE_KIND_LABELS,
        type LifecycleEvent,
        type LifecycleKind,
    } from 'src/helpers/lifecycleTimeline';

    const { detail } = useStockItemDetail();

    const lifecycleEvents = computed<LifecycleEvent[]>(() =>
        detail.value ? buildLifecycleTimeline(detail.value) : [],
    );

    // Chip order follows the label table, showing only kinds this item has.
    const presentKinds = computed<LifecycleKind[]>(() => {
        const present = new Set(lifecycleEvents.value.map((e) => e.kind));
        return (Object.keys(LIFECYCLE_KIND_LABELS) as LifecycleKind[]).filter((k) => present.has(k));
    });

    // None selected means every kind.
    const selectedKinds = ref(new Set<LifecycleKind>());
    function toggleKind(kind: LifecycleKind) {
        const next = new Set(selectedKinds.value);
        if (next.has(kind)) next.delete(kind);
        else next.add(kind);
        selectedKinds.value = next;
    }

    const rows = computed(() => {
        const picked = selectedKinds.value;
        const shown = picked.size === 0
            ? lifecycleEvents.value
            : lifecycleEvents.value.filter((e) => picked.has(e.kind));
        return groupLifecycleEvents(shown);
    });

    const openRuns = ref(new Set<string>());
    function toggleRun(id: string) {
        const next = new Set(openRuns.value);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        openRuns.value = next;
    }
</script>

<style scoped>
    .history-filters {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
    }
    .history-run {
        list-style: none;
        margin: 8px 0 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    .history-run li {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        font-size: var(--font-size-sm);
    }
</style>
