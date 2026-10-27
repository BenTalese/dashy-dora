<template>
    <!--
        P8-07 — Dora's inferred pantry belief, as a card.

        The *row* form of this is the level picker's dashed ring + menu
        header (`StockItemRow`), which stays deliberately silent when Dora
        agrees with the recorded level: on a list of 200 items, "Dora agrees"
        200 times is noise.

        The stock-item detail page is the opposite case. The owner asked
        (2026-08-16) to "always show Dora's opinion so we can see the
        reasoning for agreeing with the level" — you came to this page for
        one item, and on one item the agreement *and* its reasoning are the
        point. So this card always renders when a belief exists, collapsed to
        the same pill the row shows, and opens to the full reasoning.
    -->
    <!-- Feedback 2026-08-24: this card's chevron didn't line up in a column
         with the buy-verdict card's directly below it. Both were centred in
         their own row; the difference was structural — this one was an 18px
         glyph flush to the card's padding, that one is centred inside a 44px
         tap target. `CollapsibleCard` now owns that shape for every disclosure
         in the app, so the two chevrons share an x by construction rather than
         by two components happening to agree. -->
    <CollapsibleCard
        v-if="belief"
        :class="['dora-signal-card', toneClass]"
        header-toggles
        reveals="details"
    >
        <template #header>
            <div class="dora-signal-card__summary">
                <q-icon :name="ICONS.dora_voice" size="18px" class="dora-signal-card__icon" />
                <span class="dora-signal-card__headline">{{ headline }}</span>
            </div>
        </template>

        <div class="dora-signal-card__body">
            <div>{{ belief.reason }}</div>
            <div class="dora-signal-card__meta dora-text-muted">
                Confidence: {{ belief.confidence_band }}
            </div>
            <div class="dora-signal-card__meta dora-text-muted">
                <template v-if="belief.differs_from_recorded">
                    This differs from your recorded level.
                </template>
                <template v-else>
                    This agrees with your recorded level.
                </template>
            </div>
        </div>
    </CollapsibleCard>
</template>

<script setup lang="ts">
    import { computed } from 'vue';
    import { ICONS } from 'src/style/icons';
    import CollapsibleCard from 'src/components/CollapsibleCard.vue';
    import type { PantryBelief } from 'src/models/pantryBelief';

    const props = defineProps<{
        belief: PantryBelief | null;
    }>();

    // Amber only when Dora disagrees — that's the case worth pulling the eye.
    // Agreement is information, not an alert, so it sits on a neutral surface.
    const toneClass = computed(() => (props.belief?.differs_from_recorded ? 'is-warning' : ''));

    const headline = computed(() => (props.belief ? `Dora thinks ${props.belief.believed_band}` : ''));
</script>
