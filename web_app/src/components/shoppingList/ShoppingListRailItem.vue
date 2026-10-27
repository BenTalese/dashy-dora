<template>
    <q-item
        clickable
        :active="active"
        active-class="dora-bg-info-soft"
        class="rounded-borders sl-rail-item"
        :class="{ 'sl-rail-item-done': summary.status === 'done' }"
        @click="emit('select')"
    >
        <q-item-section avatar>
            <q-icon
                :name="statusIcon"
                :color="statusColour ?? undefined"
                :class="{ 'dora-text-muted': !statusColour }"
            />
        </q-item-section>
        <!-- The name and nothing under it (owner, 2026-09-27: *"just show list
             name in the list picker"*). The date caption repeated what a
             self-labelled list's name already is, and the "next up" marker
             went entirely; the picker opens on that list anyway. -->
        <q-item-section class="sl-rail-item__main">
            <q-item-label class="ellipsis sl-rail-item__name">
                {{ summary.display_name }}
            </q-item-label>
        </q-item-section>
        <!-- The size of the list, as a count at the row's end. Absent on an
             empty list: a "0" chip is a badge for nothing. -->
        <q-item-section v-if="summary.line_count > 0" side>
            <span
                class="sl-rail-item__count"
                :aria-label="`${summary.line_count} item${summary.line_count === 1 ? '' : 's'}`"
            >
                {{ summary.line_count }}
            </span>
        </q-item-section>
    </q-item>
</template>

<script lang="ts" setup>
    /**
     * One row of the shopping-lists rail / mobile dropdown (UX-v2 §3.1):
     * status icon, server-resolved display name and the item count.
     *
     * The kebab is gone (2026-08-28). It carried copy-to-new and delete, and
     * both were already reachable from the list you're looking at — so it put
     * two uncommon, one of them destructive, actions on every row of a picker
     * whose only job is "take me to that list". Copy went entirely: **Save as
     * template** is the same idea with a better name, and the rest of the app
     * had no second way to copy a list you weren't looking at. Delete stayed
     * on the open list's footer, where you can see what you're deleting.
     */
    import { listStatusIcon, type ShoppingListSummary } from 'src/models/shoppingList';
    import { computed } from 'vue';

    const props = defineProps<{
        summary: ShoppingListSummary;
        active: boolean;
    }>();

    const emit = defineEmits<{ select: [] }>();

    /** Shared with the overview card's pill and the phone's picker. */
    const statusIcon = computed(() => listStatusIcon(props.summary.status));
    // R-002: "done" is the neutral / finished state — null lets the
    // template apply `dora-text-muted` rather than a `grey-N` literal.
    const statusColour = computed<string | null>(() => {
        switch (props.summary.status) {
            case 'shopping':
                return 'positive';
            case 'done':
                return null;
            default:
                return 'primary';
        }
    });

</script>

<style scoped>
    /* The row truncates its own name rather than relying on whatever contains
       it. It used to sit in a width-pinned `q-virtual-scroll`; that scroller was
       removed on 2026-08-28 so the rail could size to its contents, and without
       it the names were hard-clipped by the rail's `overflow-x` instead of
       ellipsised — the flex chain defaults to `min-width: auto`, so nothing
       agreed to shrink and `.ellipsis` had no width to work against. Owning it
       here means the row behaves the same in the rail, the mobile dropdown and
       the "See older" dialog. */
    /* Every link in the chain, because one `min-width: 0` in the middle does
       nothing while the ends still refuse to shrink. Measured at 1280px inside
       the 300px rail before the fix: the `q-item` root was 433px and the name
       span 341px, both still `min-width: auto`, so the row overflowed and was
       hard-clipped by the rail's `overflow-x` rather than ellipsised. */
    .sl-rail-item {
        min-width: 0;
        max-width: 100%;
    }
    .sl-rail-item__main {
        min-width: 0;
    }
    .sl-rail-item__name {
        min-width: 0;
    }
    .sl-rail-item-done {
        opacity: 0.6;
    }
    /* A count, not a status: neutral ink on the sunken tone, sized to the
       D-003 chip floor. */
    .sl-rail-item__count {
        display: inline-block;
        min-width: 24px;
        padding: 2px var(--space-2);
        border-radius: var(--radius-pill);
        background: var(--surface-sunken);
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        text-align: center;
    }
</style>
