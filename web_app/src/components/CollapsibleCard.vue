<template>
    <div class="collapsible-card" :class="{ 'collapsible-card--open': expanded }">
        <div class="collapsible-card__header">
            <!-- The lead is a plain container by default. It becomes a button
                 only when `headerToggles` is set, because a header that holds
                 its own controls (the shopping list's overview card holds a
                 sort control and the face's primary action) cannot also be one
                 big click target — the outer button would swallow their taps. -->
            <component
                :is="leadIsButton ? 'button' : 'div'"
                :type="leadIsButton ? 'button' : undefined"
                class="collapsible-card__lead"
                :class="{ 'collapsible-card__lead--button': leadIsButton }"
                :aria-expanded="leadIsButton ? expanded : undefined"
                @click="onLeadClick"
            >
                <slot name="header" :expanded="expanded" />
            </component>

            <!-- Controls that act rather than disclose (the buy verdict's one-tap
                 action), between the lead and the caret and outside both, so a
                 tap on one never toggles the card (FU-950 (1)). -->
            <div v-if="$slots.actions" class="collapsible-card__actions">
                <slot name="actions" />
            </div>

            <!-- Always its own control, even when the header toggles too. It is
                 the only affordance that *says* there is more here, and it is
                 the one that can be given a 44px target (D-004) without
                 stretching the header's own layout. -->
            <button
                v-if="collapsible"
                type="button"
                class="collapsible-card__caret"
                :aria-expanded="expanded"
                :aria-label="caretLabel"
                @click="toggle"
            >
                <q-icon :name="expanded ? ICONS.collapse : ICONS.expand" size="18px" />
                <BaseTooltip>{{ caretLabel }}</BaseTooltip>
            </button>
        </div>

        <!-- The one-line stand-in for the body. Optional: a card whose header
             already says enough when closed simply doesn't pass this slot. -->
        <div v-if="collapsible && !expanded && $slots.collapsed" class="collapsible-card__collapsed">
            <slot name="collapsed" />
        </div>

        <!-- `v-show`, not `v-if`: the body stays in the DOM so the caret's
             `aria-expanded` refers to something that exists, and so the slide
             transition has a box to animate.

             A non-collapsible card skips the transition entirely: it never
             opens or closes, so animating it is a measurement with nothing to
             measure — and `q-slide-transition` measures its content on every
             layout pass, including while nested inside a closed parent.

             **The padding lives on `__inner`, never on `__body`.** That is the
             whole fix for the closing snap (2026-09-17). `q-slide-transition`
             animates `height`, and an element's height cannot go below its own
             padding and borders — so a body padded 12px/16px with a 1px rule
             slid smoothly down to **29px**, sat there, and then lost the last
             29px in a single frame when `v-show` set `display: none`. Traced
             frame by frame on the overview card: 199 → 29px over ~250ms, then
             29 → 0 instantly. Anything the animation can't collapse has to sit
             *inside* the box being animated. -->
        <q-slide-transition v-if="collapsible">
            <div v-show="expanded" class="collapsible-card__body">
                <div class="collapsible-card__inner">
                    <slot />
                </div>
            </div>
        </q-slide-transition>
        <div v-else class="collapsible-card__body">
            <div class="collapsible-card__inner">
                <slot />
            </div>
        </div>
    </div>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    /**
     * The shared disclosure card.
     *
     * Four hand-rolled versions of this existed before it — `StoreSpendCard`,
     * `PantryBeliefCard`, `RecipeNutritionCard` and `RecipeDetailPage`'s four
     * `detailOpen` toggles — each re-deciding the same four things: where the
     * caret goes, whether it has a real tap target, what its accessible name is,
     * and whether the body animates. They did not agree, which is how a chevron
     * ended up misaligned between two stacked cards (the 2026-08-24 report that
     * `PantryBeliefCard`'s header comment still records).
     *
     * So this owns the *structure and the behaviour* — header, caret, collapsed
     * stand-in, body — and deliberately owns none of the *surface*. Its callers
     * look nothing like each other (a bordered `q-card`, a warning-tinted panel,
     * a page-width overview), and flattening them into one look would have been
     * a worse trade than the duplication it replaces. Attributes fall through to
     * the root, so a caller styles it with its own class.
     *
     * Expansion is `v-model:expanded` but binding it is optional — left
     * unbound, `defineModel` keeps the state locally, which is what every
     * caller that has no reason to know does.
     */
    import { computed, watchEffect } from 'vue';
    import { ICONS } from 'src/style/icons';

    const props = withDefaults(defineProps<{
        /** Whether the card can close at all. `false` renders it permanently
         *  open with no caret — for a card already sitting inside someone
         *  else's disclosure, where a second tap would be a tax, not a choice. */
        collapsible?: boolean | undefined;
        /** Make the whole header a toggle in addition to the caret. Only safe
         *  when the header holds no controls of its own. */
        headerToggles?: boolean | undefined;
        /** What the caret is hiding, in the caller's own words — "store
         *  breakdown", "details". Becomes "Show/Hide {this}" (D-005: an
         *  icon-only control needs a name that says what it acts on). */
        reveals?: string | undefined;
    }>(), { collapsible: true, headerToggles: false, reveals: 'details' });

    /** Collapsed on mount, every time, and never persisted — the app-wide
     *  default (the one localStorage exception, `StockLocationsSettings`, is a
     *  tree whose shape *is* the user's place in it). A card that remembers
     *  being open is a card that opens for a reason the user has forgotten. */
    const expanded = defineModel<boolean>('expanded', { default: false });

    const caretLabel = computed(() =>
        `${expanded.value ? 'Hide' : 'Show'} ${props.reveals}`
    );

    /** A card that can't close has nothing for its header to toggle, so the
     *  header stays a plain `div`. It was rendering a `<button aria-expanded>`
     *  whose handler returned immediately — a control announced to a screen
     *  reader that does nothing when pressed. */
    const leadIsButton = computed(() => props.headerToggles && props.collapsible);

    /** The lead renders as a `div` when it isn't a toggle, and a `div`'s click
     *  still fires — so the guard lives here rather than in the binding. */
    function onLeadClick(): void {
        if (props.headerToggles) toggle();
    }

    function toggle(): void {
        // A non-collapsible card renders no caret, but the header may still be
        // a button; without this it would toggle a body that has no way back.
        if (!props.collapsible) return;
        expanded.value = !expanded.value;
    }

    // A non-collapsible card is open by definition, whatever the model says.
    // Kept as a watcher rather than a computed wrapper so `v-model:expanded`
    // stays a plain two-way binding for the callers that do use it.
    watchEffect(() => {
        if (!props.collapsible && !expanded.value) expanded.value = true;
    });
</script>

<style scoped>
    .collapsible-card__header {
        display: flex;
        align-items: flex-start;
        gap: var(--space-2);
    }
    .collapsible-card__lead {
        flex: 1 1 auto;
        min-width: 0;
    }
    /* Button reset — the lead is a button for semantics, not for looks. */
    .collapsible-card__lead--button {
        padding: 0;
        border: none;
        background: none;
        font: inherit;
        color: inherit;
        text-align: left;
        cursor: pointer;
    }
    .collapsible-card__actions {
        display: flex;
        align-items: center;
        flex: 0 0 auto;
        min-height: 44px;
    }
    /* D-004: an 18px glyph inside a 44px target. */
    .collapsible-card__caret {
        display: flex;
        align-items: center;
        justify-content: center;
        flex: 0 0 auto;
        min-width: 44px;
        min-height: 44px;
        padding: 0;
        border: none;
        background: none;
        color: var(--text-secondary);
        cursor: pointer;
    }
    /* The animated box owns nothing that has a size of its own — no padding, no
       border, no min-height — so `height: 0` really is zero. A caller that needs
       either puts it on `__inner` (or on its own content); one that puts it back
       here reintroduces the snap. */
    .collapsible-card__body {
        padding: 0;
        border: none;
    }
    .collapsible-card__lead--button:focus-visible,
    .collapsible-card__caret:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
        border-radius: var(--radius-sm, 4px);
    }
</style>
