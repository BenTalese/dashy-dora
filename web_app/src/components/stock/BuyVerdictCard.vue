<template>
    <!-- Feedback 2026-08-16: collapsed by default. The header alone answers
         the question ("Worth buying now") with the one action worth taking;
         the reasons, the wait hint and the data-provenance footer are the
         "why", and only open when asked for.
         Feedback 2026-08-21: this used to be a card-inside-a-card — an
         elevated shell wrapping a tinted header block. It now wears the same
         single-surface shape as `PantryBeliefCard` (the "Dora thinks" card it
         sits under): the verdict tint lives on the card itself, the summary
         line is the disclosure, and the one-tap action is an icon-only button
         sitting to the RIGHT of the caret, exactly where the belief card's
         chevron ends. Two cards, one idiom. -->
    <div v-if="verdict" :class="['dora-signal-card', 'dora-buy-verdict-card', toneClass]">
        <div class="dora-buy-verdict-card__header">
            <button
                type="button"
                class="dora-buy-verdict-card__summary"
                :aria-expanded="expanded"
                @click="expanded = !expanded"
            >
                <!-- Always the dollar glyph. A per-verdict icon meant `unsure`
                     drew a question-mark bubble, which read as an info chip
                     rather than as "this card is about money". -->
                <q-icon
                    :name="ICONS.currency_usd"
                    size="18px"
                    class="dora-signal-card__icon"
                />
                <span class="dora-buy-verdict-card__headline">
                    {{ headline }}
                    <!-- The planned-meals card's sentence, folded in (owner
                         2026-10-15). Said in the header so it isn't hidden
                         behind the caret: the plan is the reason that tends
                         to matter most. -->
                    <span v-if="planReason" class="dora-buy-verdict-card__plan">
                        <q-icon :name="ICONS.event" size="14px" />
                        {{ planReason.label }}
                    </span>
                </span>
            </button>
            <!-- Feedback 2026-09-01: the cart action used to be a plain
                 primary button that always read "add", so a card on an item
                 already sitting on a list still offered to add it again. It
                 now routes through the same `AddToListButton` the stock
                 overview row uses, so on/off-list state (and the toggle-off +
                 multi-list popover) reads identically in both places. -->
            <AddToListButton
                v-if="verdict.one_tap_action.kind === 'add_to_list'"
                variant="row"
                :stock-item-id="stockItemId"
            />
            <!-- Icon-only, and outside the disclosure button so a tap on the
                 action can't toggle the card. The name survives as the tooltip
                 + aria-label (D-rule: icon-only controls are still named). -->
            <BaseButton
                v-else-if="verdict.one_tap_action.kind !== 'none'"
                variant="primary"
                dense
                :icon="actionIcon"
                :aria-label="actionLabel"
                @click="onActionClick"
            >
                <BaseTooltip>{{ actionLabel }}</BaseTooltip>
            </BaseButton>
            <!-- Feedback 2026-08-23: the caret used to live inside the summary
                 button, which put it LEFT of the action — so it sat in a
                 different place depending on whether the verdict had a one-tap
                 action. It's now the last control in the row, always the same
                 spot; it toggles the same disclosure the summary line does. -->
            <button
                type="button"
                class="dora-buy-verdict-card__caret"
                :aria-expanded="expanded"
                :aria-label="expanded ? 'Hide details' : 'Show details'"
                @click="expanded = !expanded"
            >
                <q-icon
                    :name="expanded ? ICONS.collapse : ICONS.expand"
                    size="18px"
                    class="dora-text-muted"
                />
            </button>
        </div>

        <div v-if="expanded" class="dora-buy-verdict-card__body">
        <!-- Named "data confidence" since 2026-08-24: with strength carrying
             "how much you should care", this number is only ever about the
             evidence, and a bare "high confidence" under "No strong buy
             signal" read as a contradiction. -->
        <div class="text-caption dora-text-muted">
            Data confidence: {{ verdict.confidence }}
        </div>

        <!-- time-boxed hint on `wait` verdicts. Server only sends
             this when a confident cycle was detected; the reason string
             is authoritative, the friendly "in ~N days" is a client-side
             formatting nicety. -->
        <div v-if="verdict.wait_hint" class="dora-buy-verdict-card__wait-hint">
            <div class="row items-center q-mb-xs">
                <q-icon
                    :name="ICONS.event_repeat"
                    size="18px"
                    class="q-mr-sm"
                />
                <strong>{{ waitHintTargetLabel }}</strong>
            </div>
            <div class="text-caption dora-text-muted" style="margin-left: 26px">
                {{ verdict.wait_hint.reason }}
            </div>
        </div>

        <ul v-if="verdict.reasons.length > 0" class="dora-buy-verdict-card__reasons">
            <li v-for="(reason, i) in verdict.reasons" :key="i">
                <div class="row items-center">
                    <q-icon
                        :name="axisIcon(reason.axis)"
                        size="18px"
                        class="q-mr-sm dora-text-muted"
                    />
                    <strong>{{ reason.label }}</strong>
                </div>
                <div
                    v-if="reasonDetail(reason)"
                    class="text-caption dora-text-muted dora-buy-verdict__detail"
                >
                    {{ reasonDetail(reason) }}
                </div>
            </li>
        </ul>

        <div class="text-caption dora-text-muted dora-buy-verdict-card__footer">
            {{ dataUsedLine(verdict.data_used) }}
        </div>
        </div>
    </div>
</template>

<script setup lang="ts">
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import AddToListButton from 'src/components/AddToListButton.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import {
        axisIcon, dataUsedLine, headlineFor, reasonDetail,
    } from 'src/components/stock/buyVerdictDisplay';
    import { formatDate as formatLocaleDate } from 'src/composables/useDateFormat';
    import type { BuyVerdict } from 'src/services/api/buyVerdictApiService';
    import { ICONS } from 'src/style/icons';
    import { computed, ref } from 'vue';

    const props = defineProps<{
        verdict: BuyVerdict | null;
        /** The item this verdict is about. `AddToListButton` keys its
         *  on/off-list state off it, so the cart action can only render
         *  state-aware when the id is in hand. */
        stockItemId: string;
    }>();

    const expanded = ref(false);

    const emit = defineEmits<{
        (e: 'action', kind: BuyVerdict['one_tap_action']['kind']): void;
    }>();

    const actionLabel = computed(() => props.verdict?.one_tap_action.label ?? '');

    const planReason = computed(
        () => props.verdict?.reasons.find((r) => r.axis === 'plan') ?? null,
    );

    // The action is icon-only now, so every kind needs a glyph. `add_to_list`
    // is rendered by `AddToListButton` (which picks its own cart glyph from
    // list state); its entry stays so the map is total over the action union.
    const ACTION_ICONS: Record<BuyVerdict['one_tap_action']['kind'], string> = {
        add_to_list: ICONS.add_shopping_cart,
        mark_stocked: ICONS.inventory_2,
        remove_from_list: ICONS.playlist_remove,
        skip: ICONS.close,
        none: ICONS.check,
    };
    const actionIcon = computed(
        () => ACTION_ICONS[props.verdict?.one_tap_action.kind ?? 'none'],
    );

    // Feedback 2026-08-24: "Worth buying now" fired for any item you'd marked
    // low, essential or not, so it filtered out as noise. A buy now grades off
    // the server's `strength` (essential x band, modulated by price + waste) —
    // same axis `stock_attention` ranks shortages on, so the two can't
    // contradict each other about the same item.
    const headline = computed(() => (props.verdict ? headlineFor(props.verdict, { graded: true }) : ''));
    const TONE_BY_VERDICT: Record<string, string> = {
        buy: 'is-positive', wait: 'is-warning', skip: 'is-negative',
    };
    const toneClass = computed(() => (props.verdict ? TONE_BY_VERDICT[props.verdict.verdict] ?? '' : ''));

    // Friendly relative-date headline for the P8-06 wait-hint. The full
    // "why" string from the server sits underneath as the sub-caption.
    const waitHintTargetLabel = computed(() => {
        const hint = props.verdict?.wait_hint;
        if (!hint) return '';
        const target = new Date(`${hint.until}T00:00:00`);
        if (Number.isNaN(target.getTime())) return '';
        // Counted server-side from the household's today (R-021).
        const days = hint.days_until;
        const dateLabel = formatLocaleDate(target, {
            month: 'short', day: 'numeric',
        });
        if (days <= 0) return `Expect a dip around ${dateLabel}`;
        if (days === 1) return `Expect a dip tomorrow (${dateLabel})`;
        if (days <= 14) return `Expect a dip in ~${days} days (${dateLabel})`;
        return `Expect a dip around ${dateLabel}`;
    });

    function onActionClick(): void {
        if (props.verdict) emit('action', props.verdict.one_tap_action.kind);
    }
</script>

<style scoped>
    /* Shell and tones: `.dora-signal-card` (css/signalCards.scss). */
    .dora-buy-verdict-card__header {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .dora-buy-verdict-card__body {
        margin-top: 6px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        font-size: var(--font-size-sm);
        line-height: 1.45;
    }
    .dora-buy-verdict-card__headline {
        font-weight: 600;
        font-size: var(--font-size-md);
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        text-align: left;
    }
    .dora-buy-verdict-card__plan {
        display: inline-flex;
        align-items: center;
        gap: var(--space-1);
        font-weight: 400;
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
    }
    /* The whole summary line is the disclosure control, so it has to be a
       real button: keyboard-reachable, and wide enough that a thumb lands on
       it (D-004). Chrome is stripped back to the surrounding card. */
    .dora-buy-verdict-card__summary {
        display: flex;
        align-items: center;
        gap: 6px;
        /* Takes the row; the action button keeps its intrinsic width. */
        flex: 1 1 auto;
        min-width: 0;
        min-height: 44px;
        padding: 0;
        border: none;
        background: none;
        font: inherit;
        color: inherit;
        text-align: left;
        cursor: pointer;
    }
    .dora-buy-verdict-card__summary:focus-visible,
    .dora-buy-verdict-card__caret:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
        border-radius: 4px;
    }
    /* 44px tap target (D-004) for a control that's only an 18px glyph. */
    .dora-buy-verdict-card__caret {
        display: flex;
        align-items: center;
        justify-content: center;
        flex: 0 0 auto;
        min-width: 44px;
        min-height: 44px;
        padding: 0;
        border: none;
        background: none;
        color: inherit;
        cursor: pointer;
    }

    /* P8-06 — the wait-hint block sits between header and reasons. It used
       to carry its own warm fill, which on a now-already-warm `wait` card was
       both invisible and one more nested box — the exact "card inside a card"
       the 2026-08-21 feedback called out. A rule down the left edge marks it
       out instead. */
    .dora-buy-verdict-card__wait-hint {
        padding-left: 8px;
        border-left: 3px solid var(--semantic-warning);
    }

    .dora-buy-verdict-card__reasons {
        list-style: none;
        padding: 0;
        margin: 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .dora-buy-verdict-card__footer {
        border-top: 1px solid var(--surface-sunken);
        padding-top: 8px;
    }
</style>
