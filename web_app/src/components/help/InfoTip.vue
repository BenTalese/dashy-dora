<template>
    <!--
        Owner feedback 2026-08-29 — *"The info chip for mode feels a bit small.
        Are the other info chips this size? Consistency!"* They weren't: the
        same (?)-with-a-tooltip shape had been hand-rolled at 14px on the
        Assistant page, the meal-plan week status and the Dora score card, and
        at 16px on the stock-row legend. One component, one size, one tooltip
        width — so the next one can't drift either.

        Distinct from `HelpHint`, which *navigates* to a Help guide. This one
        just says the thing inline; reach for HelpHint when the explanation is
        long enough to want its own page.
    -->
    <!-- `role="button"`: it is focusable and opening the tip is its action
         (on touch, the tap that shows it), and a bare span may not carry an
         `aria-label` (axe `aria-prohibited-attr`). Being a button, it honours
         Enter/Space (toggle the tip, Escape closes it), and the tip text is
         tied to it by `aria-describedby` — the tooltip itself is teleported
         and only mounted while open, so the description points at a visually
         hidden copy that is always in the tree. -->
    <span
        class="info-tip"
        role="button"
        :aria-label="`More information: ${label}`"
        :aria-describedby="descriptionId"
        :aria-expanded="open"
        tabindex="0"
        @keydown.enter.prevent="toggle"
        @keydown.space.prevent="toggle"
        @keydown.esc="open = false"
    >
        <q-icon :name="ICONS.help_outline" size="18px" />
        <span :id="descriptionId" class="info-tip__sr"><slot /></span>
        <!-- Owner feedback 2026-09-13: *"the longer tooltip delay is good but
             it's been applied too broadly. For info (?) chips specifically,
             I'd expect those to be instant."* The 500 ms default exists so a
             tap on a *button* doesn't flash its label on the way to doing the
             thing the button does (see BaseTooltip). A (?) chip does nothing
             else — reading the tip is the only reason to touch it — so there
             is no action for a flash to interfere with, and the dwell is pure
             latency on the one gesture the control is for. -->
        <!-- `v-model` falls through to the root QTooltip (BaseTooltip has a
             single root), so hover/focus still drive it as before and the
             keyboard toggle above shares the same state. -->
        <BaseTooltip
            v-model="open"
            :delay="0"
            max-width="340px"
            :offset="[0, 6]"
            class="info-tip__tooltip"
        >
            <slot />
        </BaseTooltip>
    </span>
</template>

<script setup lang="ts">
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import { ref, useId } from 'vue';

    defineProps<{
        /** What the tip is about — screen-reader label, never rendered. */
        label: string;
    }>();

    const descriptionId = `info-tip-${useId()}`;
    const open = ref(false);

    function toggle() {
        open.value = !open.value;
    }
</script>

<style scoped lang="scss">
    .info-tip {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        /* D-004 — the icon is 18px, but a bare 18px target is unhittable on a
           phone (where the tooltip opens on long-press). Padding takes the box
           to 26px without changing how big the glyph looks. */
        padding: 4px;
        margin: -4px 0 -4px 2px;
        vertical-align: middle;
        color: var(--text-muted);
        cursor: help;
    }
    .info-tip:hover,
    .info-tip:focus-visible {
        color: var(--text-secondary);
    }
    .info-tip:focus-visible {
        outline: 2px solid var(--ring-focus);
        outline-offset: 1px;
        border-radius: 50%;
    }
    /* Visually hidden, still read by assistive tech (no app-wide utility
       class exists; scoped here until a second consumer appears). */
    .info-tip__sr {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
    }
    .info-tip__tooltip {
        font-size: 0.8125rem;
        line-height: 1.45;
    }
</style>
