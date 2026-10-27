<template>
    <button
        type="button"
        class="entry-chip"
        :class="[
            `entry-chip--trim-${status.trim}`,
            {
                'entry-chip--consumed': !!entry.consumed_at,
                'entry-chip--highlight': highlight,
            },
        ]"
        :aria-label="accessibleLabel"
        :disabled="!!entry.consumed_at"
    >
        <div class="entry-chip__body">
            <div v-if="showSlot" class="entry-chip__slot">{{ entry.slot }}</div>
            <!-- Owner 2026-09-12 — provenance (where this meal's food comes
                 from) reads as a labelled chip rather than loose eyebrow text:
                 *"cook cards for multi-linked days should say 'cook day - N
                 servings' in a chip"*. It carries NO verdict colour — it is a
                 fact about the plan, and the two status glyphs beside the name
                 are what say whether anything is wrong. That separation is the
                 whole point of the 2026-09-12 assessment: one axis per channel.
                 Owner 2026-09-04: the fresh marker takes the same position,
                 because it answers the same question and the two can never both
                 be true. Icon + word, never colour alone (D-014). -->
            <div v-if="linked || fresh" class="entry-chip__marks">
                <span
                    v-if="linked"
                    class="meal-chip"
                    :class="entry.is_cook_day ? 'meal-chip--cook' : 'meal-chip--leftover'"
                >
                    <q-icon :name="ICONS.link" size="12px" />
                    {{ cookMarkerLabel }}
                </span>
                <span v-else-if="fresh" class="meal-chip">
                    <q-icon :name="ICONS.cookFresh" size="12px" />
                    Fresh
                </span>
            </div>
            <div class="entry-chip__main">
                <span class="entry-chip__name">{{ entry.recipe_name }}</span>
                <!-- Owner 2026-09-12 — *"dislike the UI moving around too much:
                     put items that are always shown to the RIGHT of items that
                     show and hide."* So the row reads rarest-first:
                     Dora's hunch (rare) → the two status glyphs (conditional) →
                     cook time (usually) → price (usually) → servings (always).
                     The always-there servings pill therefore holds one column
                     down the day whatever the meals above it are doing, which
                     is the 2026-09-03 alignment ask generalised. -->
                <MealEntryGlyphs
                    :entry="entry"
                    :status="status"
                    :price-label="priceLabel"
                    :inference-tooltip="inferenceTooltip"
                    :shortfall="!!shortfall"
                />
                <span class="entry-chip__pill">×{{ entry.servings }}</span>
            </div>
        </div>

        <!-- The menu is shared with `MealPlanRichCard` (R-001) — see
             `MealPlanEntryMenu.vue`. -->
        <MealPlanEntryMenu
            v-if="!entry.consumed_at"
            :entry="entry"
            @view="emit('view')"
            @cook="emit('cook')"
            @lighter="emit('lighter')"
            @remove="emit('remove')"
            @adjust="(d: number) => emit('adjust', d)"
            @link="emit('link')"
            @unlink="emit('unlink')"
            @fresh="emit('fresh')"
        />
    </button>
</template>

<script lang="ts" setup>
    import { ICONS } from 'src/style/icons';
    import MealEntryGlyphs from 'src/components/MealEntryGlyphs.vue';
    import MealPlanEntryMenu from 'src/components/MealPlanEntryMenu.vue';
    import { useMealEntryPresentation } from 'src/composables/useMealEntryPresentation';
    import type { MealPlanEntry } from 'src/models/mealPlan';

    const props = withDefaults(
        defineProps<{
            entry: MealPlanEntry;
            shortfall?: boolean;
            showSlot?: boolean;
            highlight?: boolean;
        }>(),
        { shortfall: false, showSlot: true, highlight: false },
    );

    const emit = defineEmits<{
        (e: 'view'): void;
        (e: 'cook'): void;
        (e: 'remove'): void;
        (e: 'adjust', delta: number): void;
        (e: 'link'): void;
        (e: 'unlink'): void;
        (e: 'lighter'): void;
        (e: 'fresh'): void;
    }>();

    const {
        inferenceTooltip, linked, fresh, cookMarkerLabel, status, priceLabel, accessibleLabel,
    } = useMealEntryPresentation(() => props.entry, () => props.shortfall);
</script>

<style scoped>
    /*
        §7 colour discipline — chip is a content-forward card, not a saturated
        fill. Status reads through the border-left accent + icons + the
        aria-label's text alternative: three channels, so WCAG 1.4.1 is met
        without colour-only signalling.

        Owner assessment 2026-09-12 — the trim is now a ROLL-UP of the two
        status glyphs rather than a fourth opinion:
            green  — all good, and there's still something to do (you'll cook it)
            grey   — nothing is required of you (a leftovers day, or cooked)
            amber  — one of the glyphs is amber
        It therefore cannot contradict the icons, which is what "this one says
        okay and this one says not okay" was. The rule lives in
        `mealPlanEntryStatus`, shared with the phone card.
    */
    /* Owner 2026-09-12 — *"the text/elements in the middle area of the page
       feel too tiny compared with other areas of the app. Compare with stock
       overview."* They were: the meal name was inherited body at ~0.875rem
       inside a 28px chip, where the stock row gives its name 1.05rem in 64px.
       The chip is the thing you actually read on this page, so it now sits on
       the app's own scale — name at `--font-size-md`, a 36px floor, and the
       three status glyphs at 22px. */
    .entry-chip {
        display: flex;
        align-items: stretch;
        width: 100%;
        text-align: left;
        padding: 8px 10px;
        margin-bottom: var(--space-1);
        background: var(--surface-elevated);
        border: 1px solid var(--border-default);
        border-left: 3px solid var(--brand-primary);
        border-radius: 8px;
        color: var(--text-primary);
        cursor: pointer;
        transition: background var(--motion-fast) var(--motion-ease), border-color var(--motion-fast) var(--motion-ease);
        min-height: 36px;
        font: inherit;
    }
    .entry-chip:hover,
    .entry-chip:focus-visible {
        background: var(--surface-sunken);
        outline: none;
    }
    .entry-chip:focus-visible {
        border-color: var(--brand-primary);
    }
    .entry-chip--trim-alert {
        border-left-color: var(--semantic-warning);
    }
    .entry-chip--trim-idle {
        border-left-color: var(--border-strong);
    }
    .entry-chip--consumed {
        opacity: 0.55;
        cursor: default;
    }
    .entry-chip--highlight {
        outline: 2px solid var(--brand-primary);
        outline-offset: 1px;
    }
    .entry-chip__body {
        width: 100%;
        min-width: 0;
    }
    .entry-chip__slot {
        font-size: var(--font-size-xs);
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        color: var(--text-muted);
    }
    /* The provenance + price row. These are facts about the plan, so they wear
       the app's quiet chip shape and never a verdict colour — the two glyphs
       beside the name own the verdict. */
    .entry-chip__marks {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 3px;
        margin-bottom: 2px;
    }
    .entry-chip__main {
        display: flex;
        align-items: center;
        gap: 6px;
        width: 100%;
    }
    .entry-chip__name {
        flex: 1 1 auto;
        white-space: normal;
        word-break: break-word;
        line-height: 1.25;
        font-size: var(--font-size-md);
        font-weight: 600;
    }
    .entry-chip__pill {
        flex: 0 0 auto;
        background: var(--surface-sunken);
        color: var(--text-secondary);
        border-radius: var(--radius-md);
        padding: 2px 8px;
        font-weight: 700;
        font-size: var(--font-size-sm);
    }
</style>
