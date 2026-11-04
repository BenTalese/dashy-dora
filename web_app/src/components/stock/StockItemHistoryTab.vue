<template>
    <!-- The stock-item page's History tab (FU-934 split). C-1b.5 / INV-7 /
         L139: one lifecycle timeline merging level changes, waste, list adds,
         purchases, cooks and expiry edits, plus synthetic Opened / Checked
         rows — built by `helpers/lifecycleTimeline`. Date-sorted, newest
         first; entries colour-keyed by event kind. Multi-root on purpose:
         the panel's DOM is exactly what it was before the split. -->
    <div v-if="lifecycleEvents.length === 0" class="dora-text-muted text-caption q-pa-md">
        Nothing logged for this item yet.
    </div>
    <q-timeline v-else color="primary">
        <q-timeline-entry
            v-for="ev in lifecycleEvents"
            :key="ev.id"
            :title="ev.title"
            :subtitle="formatEventAt(ev.at)"
            :icon="ev.icon"
            :color="ev.color"
        >
            <div v-if="ev.body" class="dora-text-secondary">
                {{ ev.body }}
            </div>
        </q-timeline-entry>
    </q-timeline>
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
    import { computed } from 'vue';
    import { useStockItemDetail } from 'src/composables/useStockItemDetail';
    import {
        buildLifecycleTimeline,
        formatEventAt,
        type LifecycleEvent,
    } from 'src/helpers/lifecycleTimeline';

    const { detail } = useStockItemDetail();

    const lifecycleEvents = computed<LifecycleEvent[]>(() =>
        detail.value ? buildLifecycleTimeline(detail.value) : [],
    );
</script>
