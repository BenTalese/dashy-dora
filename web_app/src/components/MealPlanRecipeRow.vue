<template>
    <!-- BRIEF_MEAL_PLANNER_RAIL_AND_SHELL §4.5 — the meal planner rail's row.
         Text-first by settled decision, not preference: `RecipeRow.vue:23-27`
         records the owner call of 2026-08-18 folding the show-photos toggle into
         the cards/compact switch, so compact IS the without-photos shape; and
         `seed_builders.py` sets `image=None` on every seeded recipe, so a fresh
         install has zero recipe photos anyway. A thumbnail proposal must answer
         that seed-coverage problem first.

         Why not reuse `RecipeRow.vue`: four blockers, all structural. Its
         `compact` is derived from the VIEWPORT (`$q.screen.lt.sm`), so in a
         280px rail on a desktop it believes it has full width; its trailing
         action cluster is `flex: 0 0 auto` at ~180-200px, so only the name zone
         shrinks and the name gets ~60px; the squeeze that would fix that is
         behind `@media (max-width: 599px)`, another viewport query that never
         fires here; and its four actions are cookbook verbs, where the rail has
         exactly one — add to the targeted slot.

         What IS shared is the arithmetic: `useRecipeDisplay` is the single
         authority for the meta figures both cookbook views use, so the rail
         cannot drift from them (R-003). This component decides layout only. -->
    <div
        class="mp-row dora-list-row dora-press"
        :class="{
            'mp-row--targeting': mode === 'targeting',
            'mp-row--suggesting': mode === 'suggesting',
        }"
        role="button"
        tabindex="0"
        :aria-label="ariaLabel"
        @click="emit('pick', recipe.recipe_id)"
        @keydown.enter.prevent="emit('pick', recipe.recipe_id)"
        @keydown.space.prevent="emit('pick', recipe.recipe_id)"
    >
        <div class="mp-row__body">
            <div class="mp-row__name">{{ recipe.name }}</div>

            <!-- The meta line is now reserved for what the rail is DOING.
                 Browsing shows nothing: the "35m / 620 kcal" figures were
                 deleted 2026-09-01 (owner: "remove the extra row of info from
                 the recipe rows"). They are cookbook facts — you pick a meal
                 for a slot here, and the recipe page and the cookbook both
                 carry them properly. Suggesting carries Dora's reason.

                 Targeting used to name the destination on EVERY row ("→
                 Breakfast"), which the owner asked for on 2026-09-03 to be
                 removed: *"I don't like the '→ Breakfast' text on every
                 recipe."* One armed slot has one destination, so repeating it
                 down forty rows is the same fact forty times — it is named once
                 now, in the picker's target line above the list (which the same
                 batch made a single inline row rather than a banner). -->
            <div v-if="mode === 'suggesting' && reasonText" class="mp-row__meta mp-row__meta--reason">
                <q-icon :name="ICONS.dora_voice" size="14px" />
                {{ reasonText }}
            </div>
            <!-- Owner 2026-09-05 — cost appears ONLY while the rail is ranked
                 by it. The meta line was emptied on 2026-09-01 ("remove the
                 extra row of info from the recipe rows") because time and
                 calories are cookbook facts you don't pick a slot on; that
                 stands. But a list ordered cheapest-first with no figure on it
                 asks you to take the order on trust, and "what the rail is
                 doing" is exactly what this line is reserved for. -->
            <div v-else-if="costText" class="mp-row__meta">{{ costText }}</div>
        </div>

        <!-- F26 / F42 / FU-088 — the cooked-pool controls for batch households,
             wearing the shopping-list row's quantity shape (owner 2026-09-01:
             "I like the style of the +/- count for quantity on shopping lists.
             Make a mini version of that here"). Same contract as
             the old shopping-list plan row's: a tile at rest, steppers on approach, the
             buttons always in the layout so revealing them cannot reflow the
             row. Mini because a 44px tile in a rail row would out-weigh the
             recipe name; the tile is 30px.

             The third button — "Log a cook…", which opened a count dialog —
             is gone with its dialog (owner: "log a cook on the left rail feels
             unnecessary; remove the button to get back horizontal space and
             delete the modal"). Nothing is lost: `+` logs one cooked meal,
             which is the common case, and the recipe page owns a real cook.

             The cluster stops both click and keydown: the row itself answers a
             click, Enter and Space with "add this recipe to the armed slot", so
             a key typed into the count must not reach it. -->
        <div
            v-if="batchEnabled"
            class="mp-row__pool"
            :class="{ 'mp-row__pool--armed': poolArmed }"
            @click.stop
            @keydown.stop
        >
            <!-- The shared count control (FU-909); the rail hides its ± until
                 the row is hovered or the tile is focused (styles below). -->
            <NumberStepper
                editable
                :model-value="recipe.available_meals"
                :min="0"
                :value-label="`Cooked meals ready to eat - ${recipe.name}`"
                decrement-label="One fewer cooked"
                increment-label="One more cooked"
                @focusin="poolArmed = true"
                @update:model-value="onPoolSet"
            />
        </div>
    </div>
</template>

<script setup lang="ts">
    import NumberStepper from 'src/components/NumberStepper.vue';
    import type { Recipe } from 'src/models/recipe';
    import { ICONS } from 'src/style/icons';
    import { computed, ref } from 'vue';

    const props = withDefaults(
        defineProps<{
            recipe: Recipe;
            /** Drives what the meta line says. Explicit prop, never a viewport
             *  sniff or a container query (R-019 / ADR-014) — the rail's width
             *  has nothing to do with the window's. */
            mode?: 'browsing' | 'targeting' | 'suggesting' | undefined;
            /** Destination slot name. Named only in this row's accessible
             *  label now — the visible "→ Breakfast" line was removed
             *  2026-09-03 (see the meta-line comment in the template). */
            targetSlot?: string | undefined;
            /** Dora's reason phrase, shown in `suggesting` mode. */
            reasonText?: string | undefined;
            batchEnabled?: boolean | undefined;
            /** Cost per serving, already formatted, shown only when the rail is
             *  sorted by cost (the host decides — this row renders what it's
             *  handed). Empty for every other ordering. */
            costText?: string | undefined;
        }>(),
        { mode: 'browsing', batchEnabled: false },
    );

    const emit = defineEmits<{
        (e: 'pick', recipeId: string): void;
        (e: 'poolAdjust', recipeId: string, delta: number): void;
    }>();

    /** The touch equivalent of hover for the pool stepper — CSS reveals the
     *  ± buttons on `:hover`/`:focus-within`, which a phone has neither of, so
     *  focusing the count arms them. Same escape hatch, same reason, as
     *  the old shopping-list plan row's `armed`. Per-row and never reset: an armed row
     *  that disarmed itself would move controls out from under a thumb. */
    const poolArmed = ref(false);

    // ── The pool count as a typed value ───────────────────────────────────
    // The API takes a DELTA (`adjustMealsAsync(id, delta)`), which is the right
    // shape for the ± buttons and for concurrent edits; typing an absolute
    // count is expressed against it rather than by adding a second endpoint
    // that could disagree with the first (R-003).
    // The ± buttons and a typed count both arrive as the new total; the API
    // takes the difference.
    function onPoolSet(next: number) {
        const delta = next - props.recipe.available_meals;
        if (delta !== 0) emit('poolAdjust', props.recipe.recipe_id, delta);
    }

    const ariaLabel = computed(() => {
        if (props.mode === 'targeting' && props.targetSlot) {
            return `Add ${props.recipe.name} to ${props.targetSlot}`;
        }
        return props.recipe.name;
    });
</script>

<style scoped>
    /* Border, radius, surface, hover: `.dora-list-row` (app.scss), shared
       with the stock row and the cookbook row (FU-791 / FU-802). */
    .mp-row {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        width: 100%;
        padding: var(--space-2);
        cursor: pointer;
        text-align: left;
    }
    .mp-row + .mp-row {
        margin-top: var(--space-1);
    }
    /* D-016 / A6 — a real focus ring. `RecipeRow` is a q-card with a click
       handler and no focus state, so it misses this today; the brief is
       explicit that the rail must not inherit that gap. */
    .mp-row:focus-visible {
        outline: 2px solid var(--brand-primary);
        outline-offset: 2px;
    }

    .mp-row__body {
        flex: 1 1 auto;
        min-width: 0;
    }

    /* On the D-003 scale, like the stock and cookbook row names (FU-693). */
    .mp-row__name {
        font-size: var(--font-size-md);
        font-weight: 500;
        line-height: 1.3;
        /* Name may take two lines, then clamps — a long recipe name must not
           push the row to four lines and break the picker's fixed 64px
           item height. */
        display: -webkit-box;
        -webkit-line-clamp: 2;
        line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }

    .mp-row__meta {
        margin-top: 2px;
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
        display: flex;
        align-items: center;
        gap: var(--space-1);
        min-width: 0;
    }
    .mp-row__meta--reason {
        color: var(--primary-ink);
    }

    /* The mini quantity cluster. Mirrors `.sl-row__qty` on the shopping list:
       steppers hold their place in the layout and only fade, so the row cannot
       reflow when they appear. */
    .mp-row__pool {
        flex: 0 0 auto;
        display: flex;
        align-items: center;
        gap: 2px;
    }
    /* Owner feedback 2026-09-03 - *"don't like that you can see the minus
       button always for recipes that have no meals in the pool (disabled minus)
       when every other +/- button is hidden till the row is hovered."* A real
       bug, not a styling choice: Quasar's `.q-btn--disable { opacity: .6
       !important }` beat this rule's `opacity: 0`, so the ONE state where the
       minus is disabled — an empty pool, i.e. most rows — was the one state
       where it showed. `visibility` carries the hiding instead; nothing in
       Quasar's disabled styling touches it, and it keeps the button's box in
       the layout so revealing it still cannot reflow the row. */
    .mp-row__pool :deep(.num-stepper__step) {
        visibility: hidden;
        opacity: 0;
        transition: opacity var(--motion-fast) var(--motion-ease);
    }
    @media (hover: hover) {
        .mp-row:hover .mp-row__pool :deep(.num-stepper__step),
        .mp-row:focus-within .mp-row__pool :deep(.num-stepper__step) {
            visibility: visible;
            opacity: 1;
        }
    }
    /* Touch has no hover, so the tile arms the row instead. */
    .mp-row__pool--armed :deep(.num-stepper__step) {
        visibility: visible;
        opacity: 1;
    }
    @media (hover: none) {
        .mp-row__pool :deep(.num-stepper__step) {
            visibility: visible;
            opacity: 1;
        }
    }
    /* F42 — the row's one numeric figure wears the count tile; the rail's
       is a size smaller than the menu's (34 x 30). */
    .mp-row__pool :deep(.num-stepper__input) {
        width: 34px;
        height: 30px;
    }
    /* D-004 — 30px is a "dense control in desktop-only chrome" size, and this
       row is NOT desktop-only: `MealPlanPickerSheet` renders the same component
       on a phone. So the whole cluster goes back to full targets wherever a
       finger is doing the tapping. The shopping list's own tile is 44px for
       exactly this reason. */
    @media (hover: none) {
        .mp-row__pool :deep(.num-stepper__input) {
            width: 48px;
            height: 44px;
        }
        .mp-row__pool :deep(.num-stepper__step) {
            min-width: 44px;
            min-height: 44px;
        }
    }

    @media (prefers-reduced-motion: reduce) {
        .mp-row__pool :deep(.num-stepper__step) {
            transition: none;
        }
    }
</style>
