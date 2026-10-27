<template>
    <button
        type="button"
        class="rich-card"
        :class="[
            `rich-card--trim-${status.trim}`,
            entry.consumed_at ? 'rich-card--consumed' : '',
            highlight ? 'rich-card--highlight' : '',
        ]"
        :disabled="!!entry.consumed_at"
        :aria-label="accessibleLabel"
    >
        <div class="rich-card__thumb" :class="{ 'rich-card__thumb--mono': !entry.has_image }">
            <img
                v-if="entry.has_image"
                :src="thumbUrl"
                :alt="entry.recipe_name"
                loading="lazy"
            />
            <span v-else class="rich-card__mono-letter">{{ monogramLetter }}</span>
        </div>
        <div class="rich-card__body">
            <div class="rich-card__name">{{ entry.recipe_name }}</div>
            <div class="rich-card__meta">
                <!-- Owner 2026-09-05 — the slot tag is gone. It was the card's
                     only statement of which meal this was, and the owner's read
                     of it was that *"a chip on the meal row is not very obvious
                     or easy to read for groupings of meals (based on slot)"*.
                     Its one caller groups the day under slot headings
                     (`MealPlanMobileFocus`), so the tag was restating the
                     heading two lines above it. The slot is still in
                     `accessibleLabel`, where a screen reader has no heading to
                     have just passed.

                     Owner 2026-09-12 — provenance is a CHIP and carries no
                     verdict colour (it is a fact about the plan), and the rest
                     of the row runs rarest-shown → always-shown, left to right,
                     so the servings count holds a column whatever its
                     neighbours are doing. `mealChips.scss` +
                     `helpers/mealPlanEntryStatus.ts`. -->
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
                <MealEntryGlyphs
                    :entry="entry"
                    :status="status"
                    :price-label="priceLabel"
                    :inference-tooltip="inferenceTooltip"
                    :shortfall="!!shortfall"
                />
                <span v-if="entry.cook_time_minutes" class="rich-card__cook-time">
                    <q-icon :name="ICONS.timer" size="12px" />
                    {{ entry.cook_time_minutes }}m
                </span>
                <!-- A batch's cook day prices the whole cook (the servings its
                     own chip states); its leftover days price nothing, because
                     the money is spent once. -->
                <span class="rich-card__servings">×{{ entry.servings }}</span>
            </div>
        </div>

        <!-- The menu is shared with `MealPlanEntryChip` (R-001) — see
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
    import { recipeImageUrl } from 'src/services/api/recipeApiService';
    import { useMealEntryPresentation } from 'src/composables/useMealEntryPresentation';
    import type { MealPlanEntry } from 'src/models/mealPlan';
    import { computed } from 'vue';

    const props = withDefaults(
        defineProps<{
            entry: MealPlanEntry;
            shortfall?: boolean;
            highlight?: boolean;
        }>(),
        { shortfall: false, highlight: false },
    );

    const emit = defineEmits<{
        (e: 'view'): void;
        (e: 'cook'): void;
        (e: 'lighter'): void;
        (e: 'remove'): void;
        (e: 'adjust', delta: number): void;
        (e: 'link'): void;
        (e: 'unlink'): void;
        (e: 'fresh'): void;
    }>();

    const {
        inferenceTooltip, linked, fresh, cookMarkerLabel, status, priceLabel, accessibleLabel,
    } = useMealEntryPresentation(() => props.entry, () => props.shortfall);

    const thumbUrl = computed(() => recipeImageUrl(props.entry.recipe_id));
    const monogramLetter = computed(
        () => (props.entry.recipe_name?.trim().charAt(0) || '?').toUpperCase(),
    );
</script>

<style scoped>
    .rich-card {
        display: flex;
        align-items: stretch;
        gap: var(--space-2);
        padding: 6px 8px;
        background: var(--surface-elevated);
        border: 1px solid var(--border-default);
        border-left: 3px solid var(--brand-primary);
        border-radius: 8px;
        cursor: pointer;
        transition: background var(--motion-fast) var(--motion-ease), border-color var(--motion-fast) var(--motion-ease), transform var(--motion-fast) var(--motion-ease);
        position: relative;
        color: var(--text-primary);
        text-align: left;
        font: inherit;
        width: 100%;
        min-height: 44px;
    }
    .rich-card:disabled {
        cursor: default;
    }
    .rich-card:hover,
    .rich-card:focus-visible {
        background: var(--surface-sunken);
        outline: none;
    }
    .rich-card:focus-visible {
        border-color: var(--brand-primary);
    }
    /* The trim rolls up the two status glyphs (see `mealPlanEntryStatus`):
       green = all good and something still to do, grey = nothing required of
       you (leftovers, or cooked), amber = one of the glyphs is amber. */
    .rich-card--consumed {
        opacity: 0.55;
    }
    .rich-card--trim-alert {
        border-left-color: var(--semantic-warning);
    }
    .rich-card--trim-idle {
        border-left-color: var(--border-strong);
    }
    .rich-card--highlight {
        outline: 2px solid var(--brand-primary);
        outline-offset: 1px;
    }
    .rich-card__thumb {
        flex: 0 0 auto;
        width: 48px;
        height: 48px;
        border-radius: var(--radius-md);
        overflow: hidden;
        background: var(--surface-sunken);
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .rich-card__thumb img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }
    .rich-card__thumb--mono {
        background: var(--surface-elevated);
        border: 1px dashed var(--border-default);
    }
    .rich-card__mono-letter {
        font-size: 1.2rem;
        font-weight: 700;
        color: var(--text-secondary);
        line-height: 1;
    }
    .rich-card__body {
        flex: 1 1 auto;
        min-width: 0;
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 2px;
    }
    .rich-card__name {
        font-weight: 600;
        font-size: var(--font-size-md);
        line-height: 1.25;
        word-break: break-word;
    }
    /* Owner 2026-09-12 — the whole middle pane was reading a size or two under
       the rest of the app (see `MealPlanEntryChip`); the phone card's meta line
       was 0.72rem. */
    .rich-card__meta {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 6px 8px;
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
    }
    .rich-card__servings {
        font-weight: 600;
    }
    /* The provenance + price chips are `mealChips.scss`, shared with the
       desktop week chip. */
    .rich-card__cook-time {
        display: inline-flex;
        align-items: center;
        gap: 2px;
    }
    /* Owner 2026-09-12 — this used to be `margin-left: auto`, which pushed the
       status glyph to the right edge and took the servings, time and money with
       it. Only the meals that HAVE a glyph did that, so a day's cards read
       left-aligned or right-aligned depending on whether they were short —
       *"green meals have the text on the left, shortfall meals have it on the
       right. Inconsistent."* The meta line reads left-to-right for every card
       now; the glyph keeps its place immediately before the servings count,
       which is the column the 2026-09-03 alignment feedback established. */
</style>
