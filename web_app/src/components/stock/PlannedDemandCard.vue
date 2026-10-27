<template>
    <!--
        Planned demand (owner, 2026-09-03) — *"you've got 3 planned fried rice
        in the coming week(s) and they need rice and you're low/out of rice"*.

        Sits directly under `PantryBeliefCard` and above `BuyVerdictCard`,
        wearing the same `CollapsibleCard` anatomy, because the three answer
        the three questions this page exists to answer, in order:

            what do I have?      → the recorded level (above)
            what does Dora think? → PantryBeliefCard
            what will I need?     → this card
            should I buy it?      → BuyVerdictCard

        **Why this page and not the overview row.** D-10 (2026-08-19) pulled
        the buy verdict off the stock row "in any form" — it was a derived
        signal decorating a row that already carries the level, the essential
        marker, the expiry and the attention outline, and it survives only on
        "the two surfaces the user opens *to ask*". Planned demand is exactly
        the same kind of signal, so it lands in exactly the same place rather
        than re-litigating a decision the owner already reversed once. The
        shopping list is the other of those two surfaces and is a fair home
        for this too — FU-849.

        **Tone follows urgency, and Out outranks Low** (the owner's grading,
        implemented server-side so it can't drift): `blocking` means the
        cupboard says Out and a planned meal needs it — the meal cannot be
        cooked. `watch` means Low: it might not stretch. Anything else is
        information, not an alert, and sits on the neutral surface.
    -->
    <CollapsibleCard
        v-if="demand && demand.planned_meals > 0"
        :class="['dora-signal-card', toneClass]"
        header-toggles
        reveals="details"
    >
        <template #header>
            <div class="dora-signal-card__summary">
                <q-icon :name="ICONS.event" size="18px" class="dora-signal-card__icon" />
                <span class="dora-signal-card__headline">{{ headline }}</span>
            </div>
        </template>

        <div class="dora-signal-card__body">
            <div>{{ demand.reason }}</div>
            <div v-if="demand.covered_meals > 0" class="dora-signal-card__meta dora-text-muted">
                {{ demand.needed_meals }} still to cook, so
                {{ demand.needed_meals === 1 ? 'that meal needs' : 'those meals need' }}
                this on hand.
            </div>
            <div class="dora-signal-card__meta dora-text-muted">
                <template v-if="demand.urgency === 'blocking'">
                    You've recorded this as out.
                </template>
                <template v-else-if="demand.urgency === 'watch'">
                    You've recorded this as low, so it may not stretch that far.
                </template>
                <template v-else>
                    You've got this in.
                </template>
            </div>
        </div>
    </CollapsibleCard>
</template>

<script setup lang="ts">
    import { computed } from 'vue';
    import { ICONS } from 'src/style/icons';
    import CollapsibleCard from 'src/components/CollapsibleCard.vue';
    import type { PlannedDemand } from 'src/models/plannedDemand';

    const props = defineProps<{
        demand: PlannedDemand | null;
    }>();

    const TONE_BY_URGENCY: Record<string, string> = { blocking: 'is-negative', watch: 'is-warning' };
    const toneClass = computed(() => (props.demand ? TONE_BY_URGENCY[props.demand.urgency] ?? '' : ''));

    // The headline counts the meals that still have to be *cooked*, not the
    // ones merely planned: a week whose every meal is already in the freezer
    // needs nothing bought, and saying "3 planned meals need this" there would
    // be true and useless. The full 3-vs-1 split is in the body.
    const headline = computed(() => {
        const d = props.demand;
        if (!d) return '';
        const n = d.needed_meals > 0 ? d.needed_meals : d.planned_meals;
        const noun = n === 1 ? 'meal' : 'meals';
        return d.needed_meals > 0
            ? `${n} planned ${noun} need this`
            : `${n} planned ${noun}, all covered`;
    });
</script>
