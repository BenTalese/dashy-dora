<template>
    <q-btn-toggle
        class="dora-segmented-btn"
        rounded
        unelevated
        :model-value="modelValue"
        :options="options"
        no-caps
        toggle-color="primary"
        @update:model-value="(v: T) => emit('update:modelValue', v)"
    />
</template>

<script setup lang="ts" generic="T">
    /*
     * Thin wrapper around q-btn-toggle so every single-select row of buttons
     * in the app shares one anatomy: a pill-shaped sunken track with the
     * active segment as a brand-primary pill inside it. Pass dense / spread /
     * size etc. through as normal attrs — Vue's default inheritAttrs forwards
     * them onto the root.
     *
     * **The pill used to be opt-in and is now the only shape** (owner,
     * 2026-09-03: *"I've found a couple instances of single select option rows
     * of buttons that are inconsistent with the latest designs … update [them]
     * to be styled like recipe view's step style picker"*). It arrived as a
     * `pill` prop on 2026-08-31 for that one call site; four of the nineteen
     * consumers had since adopted it and the rest hadn't, which is exactly the
     * split the owner walked into. A shape prop with a clear winner is not a
     * variant, it's a migration that never finished — so the prop is gone and
     * the squared block with it (D-015).
     *
     * `rounded` + `unelevated` are set here rather than at the call sites for
     * the same reason: they are part of the anatomy, not a per-site choice.
     * Call sites that used to pass `flat`, `color="grey"`, `text-color` or
     * `toggle-text-color` had those removed in the same pass — `flat`
     * suppresses the active fill (which is why two of them then hand-painted
     * it back), and the grey/white pair is a hardcoded palette R-002 forbids.
     *
     * The anatomy's values are tokens (`--seg-*` in tokens.scss), shared with
     * `settings/DoraSegmented.vue`, which is the same control drawn as a
     * hand-rolled radiogroup. Two mechanisms, one anatomy; merging them is
     * FU-848.
     */
    defineProps<{
        modelValue: T;
        options: {
            label?: string;
            icon?: string;
            value: T;
            [k: string]: unknown;
        }[];
    }>();
    const emit = defineEmits<{ (e: 'update:modelValue', value: T): void }>();
</script>

<style scoped lang="scss">
    /*
     * The track. `rounded` on QBtnToggle rounds the *group's* outer ends; the
     * segments inside stay square, so the selected one reads as a block
     * clipped by a curve. Rounding each segment to the pill radius makes the
     * active fill a pill sitting in a pill-shaped track.
     *
     * The track needs its own outline for the unselected segments to sit *in*
     * something — without it a pill-shaped fill floats on the page with
     * nothing to be a segment of.
     */
    .dora-segmented-btn {
        border: 1px solid var(--seg-track-border);
        border-radius: var(--seg-radius);
        background: var(--seg-track-bg);
        padding: var(--seg-track-pad);
        max-width: 100%;
    }
    .dora-segmented-btn :deep(.q-btn) {
        border-radius: var(--seg-radius);
        color: var(--seg-ink);
    }
    /* Quasar draws the inter-segment divider as a right border on every button
       but the last. Between two pills it reads as a stray tick. */
    .dora-segmented-btn :deep(.q-btn::before),
    .dora-segmented-btn :deep(.q-btn-group > .q-btn:not(:last-child)) {
        border-right: 0;
    }
    .dora-segmented-btn :deep(.q-btn:not([aria-pressed='true']):hover) {
        color: var(--seg-ink-hover);
    }

    /*
     * Active-segment ink (D-002). `toggle-color="primary"` makes Quasar emit
     * its `.text-primary` utility on the selected button — and that utility
     * carries `!important`, so it beat every attempt to set readable ink from
     * a call site. In `flat` mode, where the caller painted its own brand-
     * primary fill, the result was primary-on-primary: measured at
     * rgb(53,151,102) text on rgb(53,151,102) background in pesto-dark — a
     * 1:1 ratio, i.e. an invisible label (reported 2026-08-18 on the cookbook
     * Ingredients filter's sort toggle).
     *
     * `--seg-active-ink` resolves to `--text-on-primary`, the token that
     * exists for exactly this job, and every theme defines it against its own
     * brand-primary. Matching Quasar's `!important` is the only thing that
     * beats `!important` — specificity alone can't — hence the flag here
     * rather than a deeper selector.
     */
    .dora-segmented-btn :deep(.q-btn[aria-pressed='true']) {
        color: var(--seg-active-ink) !important;
    }

    /*
     * Label floor (D-003 / B2). Quasar's `size` prop sets the button's
     * font-size directly — `sm` is **10px**, `xs` is 8px — so every call site
     * passing `size="sm"` (most of them, to get a compact control) was
     * rendering its label under the 12px hard floor, on an *interactive*
     * element where B2 asks for 14. Measured live on the dashboard at chunk 6:
     * "7 days" / "14 days" / "Month" / "Year" / "All" all came back at 10px.
     *
     * Fixed here rather than at the call sites: the size prop is doing real
     * work (padding, height, density) and only its type scale is wrong, so
     * pinning the label alone keeps the compact control and makes the label
     * legible. One place, so the nineteen consumers can't drift (D-015).
     */
    .dora-segmented-btn :deep(.q-btn__content) {
        font-size: var(--font-size-sm);
    }
</style>
