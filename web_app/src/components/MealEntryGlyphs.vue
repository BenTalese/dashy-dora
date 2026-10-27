<template>
    <!-- Owner 2026-09-12 — ordered by how often each is there: Dora's hunch
         (rarest), the price, then the status glyphs, so the host's
         always-present servings hold one column. `chef_hat` = can you make it,
         `mealsPrepared` (the fridge) = is it already made; green fine, amber
         not, and an axis that doesn't apply renders nothing
         (`mealPlanEntryStatus`). FU-653 — the hunch is a remark, not a state:
         it keeps its own glyph rather than tinting either axis. -->
    <q-icon
        v-if="entry.inference_hint"
        :name="ICONS.dora_voice"
        size="22px"
        class="meal-glyph"
        :class="`dora-glyph--${inferenceTone(entry.inference_hint)}`"
    >
        <BaseTooltip max-width="280px">{{ inferenceTooltip }}</BaseTooltip>
    </q-icon>
    <span v-if="priceLabel" class="meal-chip meal-chip--price">{{ priceLabel }}</span>
    <q-icon v-if="entry.consumed_at" :name="ICONS.check" size="22px" class="meal-glyph">
        <BaseTooltip>Cooked</BaseTooltip>
    </q-icon>
    <template v-else>
        <q-icon
            v-if="status.supply"
            :name="ICONS.chef_hat"
            size="22px"
            class="meal-glyph"
            :class="statusToneClass(status.supply)"
        >
            <BaseTooltip>{{ supplyTooltip(entry) }}</BaseTooltip>
        </q-icon>
        <q-icon
            v-if="status.readiness"
            :name="ICONS.mealsPrepared"
            size="22px"
            class="meal-glyph"
            :class="statusToneClass(status.readiness)"
        >
            <BaseTooltip>{{ readinessTooltip(entry, shortfall) }}</BaseTooltip>
        </q-icon>
    </template>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import {
        readinessTooltip, statusToneClass, supplyTooltip, type MealCardStatus,
    } from 'src/helpers/mealPlanEntryStatus';
    import { inferenceTone } from 'src/helpers/inferenceHint';
    import type { MealPlanEntry } from 'src/models/mealPlan';

    defineProps<{
        entry: MealPlanEntry;
        status: MealCardStatus;
        priceLabel: string;
        inferenceTooltip: string;
        shortfall: boolean;
    }>();
</script>

<style scoped>
    .meal-glyph {
        flex: 0 0 auto;
    }
</style>
