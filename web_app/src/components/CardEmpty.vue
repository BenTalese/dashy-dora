<template>
    <div class="card-empty">
        <q-icon :name="icon" size="32px" class="card-empty__icon" />
        <p class="card-empty__line"><slot /></p>
        <slot name="action" />
    </div>
</template>

<script lang="ts" setup>
    /**
     * `B9`'s empty-state anatomy, once: **feature icon (32–48px, muted) ·
     * one-line what-goes-here · optional one primary action.**
     *
     * ## Why a component rather than a class
     *
     * `.dora-empty` (in `css/dashboardCards.scss`) gives an empty state its
     * container — the sunken well, the padding, the muted `--font-size-sm`. It
     * cannot give it the **icon**, because that is markup, so every consumer
     * shipped the container without the anatomy and B9 was two-thirds unbuilt
     * wherever it was used. Ten of those consumers are on `/reports` alone.
     *
     * ## What it does not do
     *
     * It takes no default copy. B9's own example is *"Once you've restocked the
     * same things a few times, I'll flag what to keep an eye on"* — specific to
     * the surface, in Dora's voice (D-014), and a shared component that supplied
     * a fallback would invite exactly the bare "No data" the rule forbids. The
     * caller must say what goes here.
     *
     * The `#action` slot is optional and stays optional: B9's second clause says
     * **don't offer an action that lands on another empty or data-gated
     * surface** on a fresh account (FU-578 #39) — on a report, that is usually
     * every action you could think of, so most consumers here pass none and let
     * the copy carry the "fills in as you use Dora" caption instead.
     */
    defineProps<{ icon: string }>();
</script>

<style scoped lang="scss">
    .card-empty {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        gap: var(--space-2);
        padding: var(--space-4);
        margin-bottom: var(--space-4);
        /* A1: an inset region inside a card sits on `--surface-sunken` — the
           same well `.dora-empty` uses, so the two read as one treatment while
           the dashboard's nine consumers migrate across. */
        background: var(--surface-sunken);
        border-radius: var(--radius-md);
        color: var(--text-secondary);
    }
    .card-empty__icon {
        /* Muted, per B9 — an empty state is not an alert, and A1 reserves the
           brand accent for the one primary CTA in a view. */
        color: var(--text-muted);
    }
    .card-empty__line {
        margin: 0;
        max-width: 46ch;
        font-size: var(--font-size-sm);
        line-height: 1.4;
    }
</style>
