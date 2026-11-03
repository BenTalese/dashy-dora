<template>
    <!--
        "Uses N expiring" chip, coloured by URGENCY rather than by count.

        Owner feedback 2026-08-18: with one flat amber, a recipe using 4
        ingredients that go off next week looked exactly as pressing as one
        using 2 that go off today — and sorted above it. The cookbook now ranks
        on the soonest date (server-derived, `expiring_soonest_date`), and this
        chip shows the same fact so the ordering is legible rather than
        mysterious.

        One chip, not a card-only detail panel: the compact rows need the same
        signal, and a shape that only works in one view would put the two
        cookbook layouts back out of step. The breakdown that a panel would
        have shown lives in the tooltip.
    -->
    <q-chip dense :color="tone.color" :text-color="tone.textColor" :class="tone.classes" :icon="tone.icon">
        {{ label }}
        <BaseTooltip max-width="260px">{{ tooltip }}</BaseTooltip>
    </q-chip>
</template>

<script setup lang="ts">
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { computed } from 'vue';
    import { ICONS } from 'src/style/icons';
    import { expiryToneFor } from 'src/helpers/expiryIndicator';

    const props = withDefaults(
        defineProps<{
            count: number;
            /** ISO date of the soonest at-risk ingredient, or null if unknown. */
            soonestDate: string | null | undefined;
            /** Number only, no wording — the compact row's figure cluster is
             *  already tight and every other chip there is abbreviated too.
             *  The tooltip is identical either way, so nothing is lost. */
            compact?: boolean;
        }>(),
        { compact: false },
    );

    const label = computed(() =>
        props.compact ? String(props.count) : `Uses ${props.count} expiring`,
    );

    /**
     * Colour comes from the SHARED expiry-tone helper — the same one the stock
     * row and the stock-item detail page use — so "red" means the same thing
     * here as everywhere else and there's no second 7-day threshold to drift
     * (R-002/R-003).
     *
     * D-002: dark ink on the saturated warning/negative fills. The neighbouring
     * chips still use `text-color="white"` on the same palette entries, which
     * measures 1.7–3.0:1 and is tracked app-wide as FU-671; this chip is not
     * going to add a 18th call site to that backlog.
     */
    const tone = computed(() => {
        switch (expiryToneFor(props.soonestDate)) {
            case 'expired':
                return { color: 'negative', textColor: 'dark', icon: ICONS.error, classes: undefined };
            case 'soon':
                return { color: 'warning', textColor: 'dark', icon: ICONS.wasteExpired, classes: undefined };
            // 'ok' = inside the filter's 14-day horizon but outside the 7-day
            // "soon" band; 'none' = at-risk for a reason other than a date.
            // Both are real but not urgent, so they take the soft warm tint the
            // recipe row's "Use soon" chip wears rather than the saturated
            // fill that means "act now" (FU-777, owner pick 2026-11-03; was a
            // fixed `grey-7` that ignored the theme, R-002).
            default:
                return { color: undefined, textColor: undefined, icon: ICONS.schedule, classes: 'dora-chip--tint-warning' };
        }
    });

    const tooltip = computed(() => {
        const n = props.count;
        const noun = n === 1 ? 'ingredient' : 'ingredients';
        if (!props.soonestDate) {
            return `${n} ${noun} in this recipe ${n === 1 ? 'is' : 'are'} at risk.`;
        }
        switch (expiryToneFor(props.soonestDate)) {
            case 'expired':
                return `${n} at-risk ${noun}. The soonest already expired (${props.soonestDate}).`;
            case 'soon':
                return `${n} at-risk ${noun}. The soonest goes off ${props.soonestDate}.`;
            default:
                return `${n} at-risk ${noun}. The soonest goes off ${props.soonestDate}.`;
        }
    });
</script>
