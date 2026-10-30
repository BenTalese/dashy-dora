<template>
    <q-dialog
        :model-value="modelValue"
        position="bottom"
        transition-show="slide-up"
        transition-hide="slide-down"
        @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    >
        <q-card class="picker-sheet column">
            <!-- Owner 2026-09-12 — the title names the destination when there
                 is one. "Pick a recipe" is what the sheet obviously is; the
                 slot and day are what you need to hold in your head while you
                 scroll, and putting them here buys back the line the picker's
                 own target row was spending inside a 80vh sheet. -->
            <q-card-section class="row items-center q-py-sm">
                <div class="text-subtitle1 picker-sheet__title"
                     :class="{ 'picker-sheet__title--target': !!focusedTarget }">
                    <template v-if="focusedTarget">
                        <q-icon :name="ICONS.arrow_forward" size="16px" />
                        {{ focusedTarget.slot }} · {{ formatDate(focusedTarget.dayIso) }}
                    </template>
                    <template v-else>Pick a recipe</template>
                </div>
                <q-space />
                <BaseButton aria-label="Close" variant="icon" :icon="ICONS.close" @click="emit('update:modelValue', false)">
                    <BaseTooltip>Close</BaseTooltip>
                </BaseButton>
            </q-card-section>
            <q-separator />
            <q-card-section class="col q-pa-sm picker-sheet__body">
                <MealPlanRecipePicker
                    :recipe-search="recipeSearch"
                    :suggestions="suggestions"
                    :recipes="recipes"
                    :focused-target="focusedTarget"
                    :show-target="false"
                    :format-date="formatDate"
                    @update:recipe-search="(v: string) => emit('update:recipeSearch', v)"
                    @cancel-target="emit('cancelTarget')"
                    @recipe-pick="onRecipePicked"
                    @palette-meal-adjust="(id: string, d: number) => emit('paletteMealAdjust', id, d)"
                    @suggestions-requested="emit('suggestionsRequested')"
                />
            </q-card-section>
        </q-card>
    </q-dialog>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import MealPlanRecipePicker from 'src/components/MealPlanRecipePicker.vue';
    import { ICONS } from 'src/style/icons';
    import type { Recipe } from 'src/models/recipe';
    import type { MealPlanSuggestion } from 'src/models/mealPlan';

    defineProps<{
        modelValue: boolean;
        recipeSearch: string;
        suggestions: MealPlanSuggestion[];
        recipes: Recipe[];
        focusedTarget: { dayIso: string; slot: string } | null;
        formatDate: (iso: string) => string;
    }>();

    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
        (e: 'update:recipeSearch', value: string): void;
        (e: 'cancelTarget'): void;
        (e: 'recipePick', recipeId: string): void;
        (e: 'paletteMealAdjust', recipeId: string, delta: number): void;
        /** §4.8 — the sheet gets the same chips and the same "Dora suggests" as
         *  the desktop rail, so both breakpoints teach one model. It is a thin
         *  wrapper, so this comes almost free: forward the request and the
         *  host's existing lazy loader serves both. */
        (e: 'suggestionsRequested'): void;
    }>();

    function onRecipePicked(recipeId: string) {
        emit('recipePick', recipeId);
        // Auto-close after a pick on mobile — Tesler. The pinned-drawer
        // pattern is desktop-only.
        emit('update:modelValue', false);
    }
</script>

<style scoped>
    .picker-sheet {
        width: 100vw;
        max-width: 100vw;
        height: 80vh;
        border-top-left-radius: 16px;
        border-top-right-radius: 16px;
        margin: 0 !important;
    }
    .picker-sheet__body {
        overflow-y: auto;
    }
    /* Accent ink when it is naming a destination — the same signal the desktop
       picker's target row carries. */
    .picker-sheet__title {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        min-width: 0;
    }
    .picker-sheet__title--target {
        color: var(--accent-ink);
    }
</style>
