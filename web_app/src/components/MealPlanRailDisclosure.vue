<template>
    <!-- Owner feedback 2026-09-05 — the rail's two ingredient lists had two
         different disclosure shapes: "What's needed (N)" wore Quasar's raw
         `q-expansion-item` label, and "All ingredients" wore a hand-built
         header slot in a bordered card. The owner asked for the first to take
         the second's look ("the same size as the all ingredients text… put the
         shopping cart there to match"), which makes it one component with two
         call sites rather than a CSS copy (R-001).

         It is hand-rolled rather than another `q-expansion-item` for one
         reason the owner stated: the add-to-list CTA sits BETWEEN the header
         and the rows, always visible, and an expansion item has nowhere to put
         a sibling that survives collapse. `#actions` is that place. -->
    <q-card flat bordered class="rail-disc">
        <button
            type="button"
            class="rail-disc__header"
            :aria-expanded="open"
            @click="open = !open"
        >
            <q-icon :name="icon" size="18px" class="rail-disc__icon" />
            <span class="rail-disc__label">{{ label }}</span>
            <span class="rail-disc__badges"><slot name="badges" /></span>
            <!-- One glyph rotated rather than two, because `expand_less` isn't
                 in the icon set and adding a second chevron for a state the
                 first can express is how an icon table grows synonyms. -->
            <q-icon
                :name="ICONS.expand_more"
                size="20px"
                class="rail-disc__chevron"
                :class="{ 'rail-disc__chevron--open': open }"
            />
        </button>

        <div v-if="$slots.actions" class="rail-disc__actions">
            <slot name="actions" />
        </div>

        <q-slide-transition>
            <div v-show="open" class="rail-disc__body">
                <slot />
            </div>
        </q-slide-transition>
    </q-card>
</template>

<script lang="ts" setup>
    import { ICONS } from 'src/style/icons';
    import { ref } from 'vue';

    defineProps<{
        icon: string;
        label: string;
    }>();

    // Collapsed on arrival, both call sites — the rail is a summary first
    // ("collapsed by default… with the 'add x to list' always visible").
    const open = ref(false);
</script>

<style scoped>
    /* D-004 — the header is a tap target on a phone, and the owner's read of
       the old one was that it sat too thin to hit ("make it a tad thicker").
       44px is the floor the app-wide sweep settled on. */
    .rail-disc__header {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        width: 100%;
        min-height: 44px;
        padding: var(--space-2);
        background: transparent;
        border: 0;
        border-radius: var(--radius-md);
        color: var(--text-primary);
        cursor: pointer;
        font: inherit;
        text-align: left;
    }
    .rail-disc__header:hover,
    .rail-disc__header:focus-visible {
        background: var(--surface-sunken);
        outline: none;
    }
    .rail-disc__header:focus-visible {
        box-shadow: inset 0 0 0 2px var(--brand-primary);
    }
    .rail-disc__icon {
        flex: 0 0 auto;
    }
    .rail-disc__label {
        flex: 1 1 auto;
        min-width: 0;
        font-size: var(--font-size-md);
        font-weight: 500;
        line-height: 1.3;
    }
    .rail-disc__badges {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        flex: 0 0 auto;
    }
    .rail-disc__chevron {
        flex: 0 0 auto;
        color: var(--text-secondary);
        transition: transform var(--motion-fast) var(--motion-ease);
    }
    .rail-disc__chevron--open {
        transform: rotate(180deg);
    }
    .rail-disc__actions {
        padding: 0 var(--space-2) var(--space-2);
    }
    .rail-disc__body {
        padding: 0 var(--space-2) var(--space-2);
    }
</style>
