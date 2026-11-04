<template>
    <!--
        RD-29's "Your notes", rebuilt as a band rather than a card.

        Owner feedback 2026-09-13: *"Make 'your notes' an extension visually of
        the step text area. Possibly collapsed?"* It used to be its own bordered
        card floating below the Prev/Repeat/Next row, which read as a fourth
        widget between the step and the three section panels. The step card
        already has the idiom for this — the timer is a sunken band hanging off
        the bottom of the same card — so the notes are now a second one.

        Collapsed by default, and that is the substantive half of the change:
        notes are a *recipe*-level aside that does not change as you step
        through, so an open one pushes the step text (the entire point of the
        surface) further down the screen on every single step. The header stays
        visible so you always know they are there.

        No outer card of its own: in step mode it sits inside `.step-card` and
        borrows that border. Image mode has no step card, so that call site
        wraps it — which is why this renders a bare band and not a card.
    -->
    <div class="cook-notes">
        <button
            type="button"
            class="cook-notes__head"
            :aria-expanded="open"
            @click="open = !open"
        >
            <q-icon :name="ICONS.notes" size="18px" color="primary" />
            <span class="text-subtitle2">Your notes</span>
            <q-space />
            <q-icon
                :name="open ? ICONS.collapse : ICONS.expand"
                size="18px"
                class="dora-text-muted"
            />
        </button>
        <!-- `v-show`, not `v-if`, so `aria-expanded` refers to a box that
             exists and the slide has something to measure — same reasoning as
             `CollapsibleCard`. -->
        <q-slide-transition>
            <div v-show="open" class="cook-notes__body">{{ notes }}</div>
        </q-slide-transition>
    </div>
</template>

<script setup lang="ts">
    import { ref } from 'vue';
    import { ICONS } from 'src/style/icons';

    defineProps<{
        /** The recipe's own notes. Callers render nothing when there are none. */
        notes: string;
    }>();

    const open = ref(false);
</script>

<style scoped lang="scss">
    .cook-notes {
        border-top: 1px solid var(--divider);
        background: var(--surface-sunken);
    }
    .cook-notes__head {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        width: 100%;
        padding: var(--space-3);
        background: none;
        border: 0;
        color: var(--text-primary);
        text-align: left;
        cursor: pointer;
        font: inherit;
    }
    // D-004 — cook mode is the surface most likely to be tapped with a floury
    // finger, so the one control this band has clears the floor.
    @media (pointer: coarse) {
        .cook-notes__head {
            min-height: 44px;
        }
    }
    .cook-notes__head:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: -2px;
    }
    // Preserve the cook's own line breaks.
    .cook-notes__body {
        padding: 0 var(--space-3) var(--space-3);
        white-space: pre-wrap;
        line-height: 1.5;
    }
</style>
