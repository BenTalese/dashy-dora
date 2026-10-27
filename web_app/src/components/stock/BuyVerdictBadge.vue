<template>
    <q-chip
        v-if="verdict"
        :class="['dora-buy-verdict-badge', `is-${verdict.verdict}`]"
        dense
        :icon="badgeIcon"
        clickable
        square
        :aria-label="`Dora's verdict: ${badgeLabel}`"
    >
        {{ badgeLabel }}
        <q-menu
            anchor="bottom left"
            self="top left"
            :offset="[0, 4]"
            transition-show="jump-down"
            transition-hide="jump-up"
            content-class="dora-buy-verdict-popover"
        >
            <div class="dora-buy-verdict-popover__inner q-pa-md">
                <div class="row items-center q-mb-sm">
                    <span :class="['dora-buy-verdict-dot', `is-${verdict.verdict}`]" />
                    <strong>{{ headline }}</strong>
                    <q-space />
                    <span class="text-caption dora-text-muted">
                        {{ confidenceLabel }} confidence
                    </span>
                </div>
                <ul v-if="verdict.reasons.length > 0" class="dora-buy-verdict-reasons">
                    <li v-for="(reason, i) in verdict.reasons" :key="i">
                        <div class="row items-center">
                            <q-icon
                                :name="axisIcon(reason.axis)"
                                size="16px"
                                class="q-mr-sm dora-text-muted"
                            />
                            <span>{{ reason.label }}</span>
                        </div>
                        <div
                            v-if="reasonDetail(reason)"
                            class="text-caption dora-text-muted dora-buy-verdict__detail"
                        >
                            {{ reasonDetail(reason) }}
                        </div>
                    </li>
                </ul>
                <div
                    v-if="verdict.data_used"
                    class="text-caption dora-text-muted q-mt-sm"
                >
                    {{ dataUsedLine(verdict.data_used) }}
                </div>
                <div
                    v-if="verdict.one_tap_action.kind !== 'none'"
                    class="q-mt-md"
                >
                    <BaseButton
                        variant="primary"
                        :label="verdict.one_tap_action.label"
                        @click="onActionClick"
                    />
                </div>
            </div>
        </q-menu>
    </q-chip>
</template>

<script setup lang="ts">
    import BaseButton from 'src/components/BaseButton.vue';
    import {
        axisIcon, dataUsedLine, headlineFor, reasonDetail,
    } from 'src/components/stock/buyVerdictDisplay';
    import type { BuyVerdict } from 'src/services/api/buyVerdictApiService';
    import { ICONS } from 'src/style/icons';
    import { computed } from 'vue';

    const props = defineProps<{
        verdict: BuyVerdict | null;
    }>();
    const emit = defineEmits<{
        (e: 'action', kind: BuyVerdict['one_tap_action']['kind']): void;
    }>();

    // Verdict → glance-level metaphor. Kept intentionally boring:
    // the badge is a signal, the popover is the explanation.
    const BADGE_META = {
        buy:    { label: 'Buy',    icon: ICONS.shopping_cart },
        wait:   { label: 'Wait',   icon: ICONS.schedule },
        skip:   { label: 'Skip',   icon: ICONS.close },
        unsure: { label: 'Unsure', icon: ICONS.help },
    } as const;

    const badgeLabel = computed(() =>
        props.verdict ? BADGE_META[props.verdict.verdict].label : '',
    );
    const badgeIcon = computed(() =>
        props.verdict ? BADGE_META[props.verdict.verdict].icon : undefined,
    );

    const headline = computed(() => (props.verdict ? headlineFor(props.verdict) : ''));

    const confidenceLabel = computed(() =>
        props.verdict?.confidence ?? '',
    );

    function onActionClick(): void {
        if (props.verdict) emit('action', props.verdict.one_tap_action.kind);
    }
</script>

<style scoped>
    /* Semantic-token-only per R-002. `-soft` variants for the chip
       background, base tokens for the accent border + icon. */
    .dora-buy-verdict-badge {
        font-weight: 600;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        font-size: var(--font-size-xs);
        padding: 0 8px;
        height: 22px;
        border: 1px solid transparent;
        /* DR-8 (#52): the verdict loads async — fade it in rather than
           hard-popping into the row. --motion-fast is ~0 under
           prefers-reduced-motion (motion.scss). */
        animation: buy-verdict-in var(--motion-fast) var(--motion-ease);
    }
    @keyframes buy-verdict-in {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    /* DR-1b (FU-578 #7 / D-002): the label used the full-strength semantic ink
       on its soft chip, but that ink is too light on the pale tint (WAIT hit
       1.98:1). The label now uses --text-primary (dark in light themes / light
       in dark) so it's AA in every theme; the coloured border + soft tint + the
       word itself carry the Buy/Wait/Skip semantic. */
    .dora-buy-verdict-badge.is-buy {
        background: var(--semantic-positive-soft);
        color: var(--text-primary);
        border-color: var(--semantic-positive);
    }
    .dora-buy-verdict-badge.is-wait {
        background: var(--semantic-warning-soft);
        color: var(--text-primary);
        border-color: var(--semantic-warning);
    }
    .dora-buy-verdict-badge.is-skip {
        background: var(--semantic-negative-soft);
        color: var(--text-primary);
        border-color: var(--semantic-negative);
    }
    .dora-buy-verdict-badge.is-unsure {
        background: var(--surface-sunken);
        color: var(--text-secondary);
        border-color: var(--surface-sunken);
    }

    .dora-buy-verdict-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .dora-buy-verdict-dot.is-buy    { background: var(--semantic-positive); }
    .dora-buy-verdict-dot.is-wait   { background: var(--semantic-warning); }
    .dora-buy-verdict-dot.is-skip   { background: var(--semantic-negative); }
    .dora-buy-verdict-dot.is-unsure { background: var(--text-muted); }
</style>

<style>
    /* Popover sits outside the scoped template — style unscoped so
       Quasar's teleported menu picks it up. Kept narrow: R-002 tokens
       only, no hex, no hardcoded dark/light. */
    .dora-buy-verdict-popover {
        max-width: 320px;
        background: var(--surface-elevated);
        color: var(--text-primary);
        border-radius: 8px;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.15);
    }
    .dora-buy-verdict-popover .dora-buy-verdict-reasons {
        list-style: none;
        padding: 0;
        margin: 0;
    }
    .dora-buy-verdict-popover .dora-buy-verdict-reasons li + li {
        margin-top: 8px;
    }
</style>
