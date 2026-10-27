<template>
    <!-- The shared dashboard card shell (R-001 — extracted from DashboardPage so
         each card is composed, not inlined). The header is icon + title + an optional
         `#action` slot (a link/text/control on the right); the body is the
         default slot. Card BODY styling stays in the parent page — slotted
         content keeps the parent's scope — so this component only owns the
         shell chrome. -->
    <article class="dora-card">
        <header class="dora-card-head">
            <q-icon v-if="icon" :name="icon" size="22px" class="dora-card-icon" />
            <h3 class="dora-card-title"><slot name="title">{{ title }}</slot></h3>
            <slot name="action" />
        </header>
        <slot />
    </article>
</template>

<script lang="ts" setup>
    // `title` is the common case; pass the `#title` slot instead for a rich
    // title (e.g. a trailing count). `#action` is the header's right-side
    // content. (The whole-card link `to` prop had no caller and went with
    // FU-899.)
    defineProps<{
        icon?: string;
        title?: string;
    }>();
</script>

<style scoped lang="scss">
    /* Self-contained: references the GLOBAL theme tokens directly (not the
       dashboard page's private `--c-*` aliases), so the shell is correct even
       though scoped styles don't inherit the page's custom-property aliases. */
    .dora-card {
        display: block;
        background: var(--surface-component);
        border: 1px solid var(--border-default);
        /* FU-811 / FU-814 item 4, owner-decided 2026-09-02: the shared card
           radius was 18px — off A4's 4/6/10/16/22 ladder, and against 10px at
           41 other card sites app-wide. A card is `--radius-lg`. The padding
           was `18px 20px 20px`, three values, none on the spacing scale; D-017
           wants one inner padding value for one element type. Reports inherits
           both corrections through this component, which is the point. */
        border-radius: var(--radius-lg);
        padding: var(--space-4);
        height: 100%;
        box-shadow: var(--elevation-card);
    }
    .dora-card-head {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        margin-bottom: var(--space-4);
    }
    .dora-card-icon {
        /* A1 reserves the brand accent for the ONE primary CTA in a view. On a
           dashboard of ~15 cards it was painting 15 decorative head icons, so
           the quick-action bar and "Draft my shop" — the actual calls to
           action — competed with a field of green that carried no meaning.
           Owner-decided 2026-09-02 (§4.5 #3); Reports inherits the same fix
           from this component. */
        color: var(--text-secondary);
    }
    .dora-card-title {
        margin: 0;
        font-size: calc(var(--font-size-md) * 1rem);
        font-weight: 600;
        flex: 1;
        letter-spacing: 0.005em;
    }
    /* The `#action` slot stays: Reports' `SpendCard` puts a `BaseSegmented`
       in it, a control rather than navigation. The whole-card link (`to`), its
       hover lift and the `.dora-card-action` / `.dora-card-link` looks had no
       consumer and went (FU-899; owner 2026-09-08 removed the links out of
       cards). With no motion left, the card needs no reduced-motion rule. */
</style>
