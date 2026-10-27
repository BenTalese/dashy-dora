<template>
    <CollapsibleCard
        class="sl-overview"
        :class="`sl-overview--${face}`"
        reveals="list details"
    >
        <template #header>
            <!-- Owner 2026-10-15: slimmer. The figures move up to sit level
                 with the caret, the status pill drops to the bottom-left, the
                 lifecycle buttons go side by side, the ring becomes a bar and
                 "Group by" becomes one dropdown. Three rows at most. -->
            <div class="sl-overview__head">
                <!-- Row 1: the facts, label over value. -->
                <div class="sl-overview__figures">
                    <div
                        v-for="fig in figures"
                        :key="fig.key"
                        class="sl-overview__figure"
                    >
                        <div class="sl-overview__label">{{ fig.label }}</div>
                        <div class="sl-overview__amount" :class="fig.tone">
                            <!-- The tilde is the same honesty marker
                                 `StoreSpendCard` already uses on a short
                                 bucket, raised to the figure it qualifies. -->
                            <span v-if="fig.partial" class="sl-overview__approx">~</span>{{ fig.value }}
                        </div>
                        <div v-if="fig.partial" class="sl-overview__partial">
                            <q-icon :name="ICONS.info" size="13px" />
                            {{ unpricedCount }} item{{ unpricedCount === 1 ? '' : 's' }}
                            with no price yet
                            <BaseTooltip>
                                This total only counts what Dora has a price
                                for, so the real figure is higher.
                            </BaseTooltip>
                        </div>
                    </div>
                </div>

                <!-- Row 2, mid-shop only: progress as a bar, count inside. -->
                <div
                    v-if="face === 'run'"
                    class="sl-overview__progress"
                    role="progressbar"
                    :aria-valuenow="tickedCount"
                    :aria-valuemin="0"
                    :aria-valuemax="detail.lines.length"
                    :aria-label="`${tickedCount} of ${detail.lines.length} collected`"
                >
                    <div class="sl-overview__progress-fill" :style="{ width: `${progressPct}%` }" />
                    <span class="sl-overview__progress-text">
                        {{ tickedCount }}/{{ detail.lines.length }}
                    </span>
                </div>

                <!-- Row 3: identity on the left, controls on the right. -->
                <div class="sl-overview__foot">
                    <div class="sl-overview__identity">
                        <span class="sl-status-pill" :class="`sl-status-pill--${detail.status}`">
                            <q-icon :name="statusIcon" size="14px" />
                            {{ statusLabel }}
                        </span>
                        <!-- Desktop only: on a phone the list picker directly
                             above this card already shows the name. Renaming
                             is draft-only (2026-09-17). -->
                        <span class="text-subtitle1 text-weight-medium ellipsis gt-sm sl-overview__name">
                            {{ detail.display_name }}
                        </span>
                        <BaseButton
                            v-if="face === 'plan'"
                            variant="icon"
                            class="gt-sm"
                            :icon="ICONS.edit"
                            aria-label="Rename list"
                            @click="emit('rename')"
                        >
                            <BaseTooltip>Rename</BaseTooltip>
                        </BaseButton>
                    </div>

                    <div class="sl-overview__actions">
                        <!-- One dropdown for the grouping (was a labelled
                             four-segment control). It names the current mode
                             with its glyph; the menu says why a mode is
                             unavailable. -->
                        <BaseButton
                            v-if="sortModes.length > 1"
                            variant="secondary"
                            class="sl-overview__group"
                            :icon="sectionIconFor(effectiveMode)"
                            :label="$q.screen.gt.xs ? SECTION_MODE_LABELS[effectiveMode] : undefined"
                            icon-right="mdi-menu-down"
                            :aria-label="`Grouped by ${SECTION_MODE_LABELS[effectiveMode].toLowerCase()}`"
                        >
                            <BaseTooltip>Group by</BaseTooltip>
                            <q-menu auto-close anchor="bottom right" self="top right">
                                <q-list dense style="min-width: 180px">
                                    <q-item
                                        v-for="opt in sortOptions"
                                        :key="opt.value"
                                        clickable
                                        :disable="opt.disable"
                                        :active="opt.value === effectiveMode"
                                        @click="emit('update:mode', opt.value)"
                                    >
                                        <q-item-section avatar>
                                            <q-icon :name="sectionIconFor(opt.value)" size="18px" />
                                        </q-item-section>
                                        <q-item-section>{{ opt.label }}</q-item-section>
                                    </q-item>
                                    <q-item v-if="unavailableLabel" class="dora-text-muted text-caption">
                                        <q-item-section>{{ unavailableLabel }}</q-item-section>
                                    </q-item>
                                </q-list>
                            </q-menu>
                        </BaseButton>

                        <!-- Mid-shop's escape hatch, beside the step it undoes. -->
                        <BaseButton
                            v-if="face === 'run'"
                            variant="secondary"
                            :icon="draftIcon"
                            :label="$q.screen.lt.sm ? undefined : 'Draft'"
                            aria-label="Back to draft"
                            @click="emit('back-to-draft')"
                        >
                            <BaseTooltip>
                                Started this by accident? Goes back to a draft and
                                unticks anything you've picked up.
                            </BaseTooltip>
                        </BaseButton>
                        <!-- A finished list is a record, so correcting it is an
                             explicit mode rather than the default state. -->
                        <BaseButton
                            v-else-if="face === 'receipt'"
                            variant="secondary"
                            :icon="ICONS.edit"
                            :label="$q.screen.lt.sm ? undefined : (amending ? 'Done' : 'Amend')"
                            :aria-label="amending ? 'Done amending' : 'Amend'"
                            :aria-pressed="amending"
                            @click="emit('update:amending', !amending)"
                        >
                            <BaseTooltip>
                                Correct the price, store or quantity on a line.
                                Your pantry isn't restocked again.
                            </BaseTooltip>
                        </BaseButton>

                        <!-- The step forward, always last. -->
                        <BaseButton
                            v-if="face === 'plan'"
                            variant="primary"
                            :icon="shopIcon"
                            label="Shop"
                            aria-label="Start shopping"
                            :disable="detail.lines.length === 0"
                            :loading="starting"
                            @click="emit('start-shopping')"
                        >
                            <BaseTooltip>
                                Tick items off as you grab them
                            </BaseTooltip>
                        </BaseButton>
                        <!-- Always "Finish", never "Finish early" (2026-08-29). -->
                        <BaseButton
                            v-else-if="face === 'run'"
                            variant="positive"
                            :icon="doneIcon"
                            label="Finish"
                            :loading="finishing"
                            @click="emit('finish')"
                        >
                            <BaseTooltip>
                                Marks this shop as done: every ticked item moves
                                back to Stocked in your pantry, and the list is
                                archived. Anything you didn't buy can move to
                                another list on the way out.
                            </BaseTooltip>
                        </BaseButton>
                        <BaseButton
                            v-else
                            variant="primary"
                            :icon="ICONS.inventory_2"
                            label="Put away"
                            @click="emit('put-away')"
                        >
                            <BaseTooltip>
                                Ephemeral checklist grouped by kitchen location so
                                you don't forget a corner. Doesn't save.
                            </BaseTooltip>
                        </BaseButton>
                    </div>
                </div>
            </div>
        </template>

        <!-- The review half. Everything here answers a question you ask once,
             not one you ask at a glance — which is the whole reason it is
             behind a caret rather than stacked on the page. -->
        <div class="sl-overview__detail">
            <!-- On every face, in the same place (2026-09-17). It used to be
                 skipped here on a receipt and rendered as a standalone card
                 below the sheet instead, so the same information moved to a
                 different part of the page depending on the list's status —
                 which is the one thing a summary card must not do. -->
            <StoreSpendCard
                :buckets="detail.totals.by_store"
                :tense="storeSpendTense"
                :collapsible="false"
                flush
            />

            <!-- "Created <date>", "From what you last paid · 3 items" and the
                 plan face's "Saving" all went on 2026-09-27 (owner: *"these
                 lines feel useless"*). The first is a fact nobody plans a shop
                 by; the second narrated where numbers came from; the third was
                 an advertised RRP gap on a list you hadn't bought yet. What
                 remains is the trip total mid-shop and the saving on a
                 receipt, both about money that actually moved. -->
            <div v-if="secondaryFigures.length > 0" class="sl-overview__secondary">
                <div v-for="fig in secondaryFigures" :key="fig.label" class="sl-overview__stat">
                    <span class="dora-text-muted">{{ fig.label }}</span>
                    <span :class="fig.tone">{{ fig.value }}</span>
                </div>
            </div>

        </div>
    </CollapsibleCard>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    /**
     * The shopping list's overview card — one component across all three faces.
     *
     * It replaces a top section that had accreted into five separate blocks: a
     * header cluster (name, pill, pencil, a meta row carrying the item count,
     * the shop day and the creation date), a `TripCard`, a `StoreSpendCard`, an
     * "Order by" bar, and — mid-shop — a sticky footer repeating the money and
     * the primary action. Five containers, no hierarchy, and the same numbers
     * in two of them.
     *
     * The shape is a disclosure, because the information genuinely splits in
     * two: **one figure and one action** you want at a glance, and a review you
     * want once. Collapsed, the card answers "what is this, what will it cost,
     * when am I going, what do I do next". Expanded, it answers "where is the
     * money going, how much am I saving, how firm are these numbers".
     *
     * Every figure it shows is read from `detail.totals`, which the server owns
     * (R-003). Nothing here re-sums a line.
     */
    import { computed } from 'vue';
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';
    import CollapsibleCard from 'src/components/CollapsibleCard.vue';
    import StoreSpendCard from 'src/components/shoppingList/StoreSpendCard.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { formatDate as formatLocaleDate, formatRelativeDay } from 'src/composables/useDateFormat';
    import { daysFromToday } from 'src/helpers/weekDates';
    import {
        PLAN_SECTION_MODES, SECTION_MODES, SECTION_MODE_LABELS, sectionIconFor,
        useLineSections, type SectionMode,
    } from 'src/composables/useLineSections';
    import {
        listStatusIcon, type ShoppingListDetail, type ShoppingListLine,
    } from 'src/models/shoppingList';

    const props = defineProps<{
        detail: ShoppingListDetail;
        /** Active lines only (deferred-by-budget excluded) — the same set the
         *  server's totals describe, and the set the sort control sorts. */
        lines: ShoppingListLine[];
        mode: SectionMode;
        amending: boolean;
        starting: boolean;
        finishing: boolean;
    }>();

    const emit = defineEmits<{
        rename: [];
        'start-shopping': [];
        'back-to-draft': [];
        finish: [];
        'put-away': [];
        'update:amending': [value: boolean];
        'update:mode': [mode: SectionMode];
    }>();

    const { moneyEnabled } = useMoneyEnabled();

    const face = computed<'plan' | 'run' | 'receipt'>(() => {
        switch (props.detail.status) {
            case 'shopping': return 'run';
            case 'done': return 'receipt';
            default: return 'plan';
        }
    });

    // ── Identity ──────────────────────────────────────────────────────
    const statusLabel = computed(() => {
        switch (props.detail.status) {
            case 'shopping':
                return 'Shopping';
            case 'done':
                // I1 — a finished list is the receipt of the shop when money
                // surfaces are on. Pure label swap; status stays 'done'.
                return moneyEnabled.value ? 'Receipt' : 'Done';
            default:
                return 'Draft';
        }
    });

    /** The pill carries a glyph as well as a colour, so the three states are
     *  still three states in greyscale (D-013 — colour never alone). */
    const statusIcon = computed(() => listStatusIcon(props.detail.status));

    /** The lifecycle buttons wear the glyph of the face they lead to. */
    const draftIcon = listStatusIcon('draft');
    const shopIcon = listStatusIcon('shopping');
    const doneIcon = listStatusIcon('done');

    // ── The headline figure ───────────────────────────────────────────
    // Server-owned totals, read not derived (R-003).
    //
    // Tier-aware (v4 §3, closing §7.3). Both `money` and `products` default to
    // **false** in `health_check.py`, so the no-money install is not an edge
    // case — it is what a fresh install looks like, and the card has to lead
    // with something real there rather than a consolation. It used to print
    // the raw line count under "items on this list" on every face, which says
    // the same flat thing whether you are planning, mid-aisle or done. Each
    // face has a number it is actually about, and money only changes *which*
    // number, never whether there is one.
    type Figure = { key: string; value: string; label: string; tone: string; partial: boolean };

    /** The card's lead figures, per face and tier. Both `money` and `products`
     *  default to **false**, so the no-money install is what a fresh install
     *  looks like: it leads with a count, and the count never appears twice. */
    const figures = computed<Figure[]>(() => {
        const out: Figure[] = [];
        const money = moneyEnabled.value;
        const totals = props.detail.totals;
        const count = props.detail.lines.length;
        const plural = (n: number, one: string, many: string) => (n === 1 ? one : many);

        if (face.value === 'plan') {
            if (money) {
                out.push({
                    key: 'cost', value: formatMoney(totals.total_price),
                    label: 'Estimated cost', tone: '', partial: headlineIsPartial.value,
                });
            } else {
                out.push({
                    key: 'count', value: String(count),
                    label: plural(count, 'Item to buy', 'Items to buy'), tone: '', partial: false,
                });
            }
            out.push(shopDayFigure.value);
            if (money) {
                out.push({
                    key: 'count', value: String(count),
                    label: plural(count, 'Item', 'Items'), tone: '', partial: false,
                });
            }
            return out;
        }

        if (face.value === 'run') {
            // The progress bar carries the count mid-shop, so the only figure
            // beside it is the money, and with money off, nothing.
            if (money) {
                out.push({
                    key: 'left', value: formatMoney(totals.remaining_price),
                    label: 'Left to spend', tone: '', partial: headlineIsPartial.value,
                });
            }
            if (props.detail.planned_shop_date) out.push(shopDayFigure.value);
            return out;
        }

        // A receipt's money is the sheet's TOTAL row below it; the card keeps
        // when it happened and how much came home.
        if (props.detail.completed_at) {
            out.push({
                key: 'shopped', value: formatDate(props.detail.completed_at),
                label: 'Shopped', tone: '', partial: false,
            });
        }
        out.push({
            key: 'count', value: String(tickedCount.value),
            label: plural(tickedCount.value, 'Item bought', 'Items bought'), tone: '', partial: false,
        });
        return out;
    });

    /** How many lines carry no price at all. The server already publishes this
     *  per store bucket precisely so the UI can admit a total is short — but it
     *  was only ever read inside `StoreSpendCard`, which lives *inside* this
     *  card's disclosure. So the headline could be quietly incomplete while the
     *  top level said nothing (baseline §1.5 / S7). It says something now. */
    const unpricedCount = computed(() => props.detail.totals.by_store.reduce(
        (sum, b) => sum + (b.line_count - b.priced_line_count), 0,
    ));

    const headlineIsPartial = computed(
        () => moneyEnabled.value && unpricedCount.value > 0,
    );

    const tickedCount = computed(() => props.detail.lines.filter((l) => l.is_ticked).length);
    /** Pure display math over server-owned counts — the sanctioned Type-C case. */
    const progressPct = computed(() => {
        const count = props.detail.lines.length;
        return count === 0 ? 0 : (tickedCount.value / count) * 100;
    });

    // ── The shop day ──────────────────────────────────────────────────
    // A fact, not a control — setting it is the toolbar's job while it is
    // still settable.
    function formatDate(iso: string): string {
        try {
            return formatLocaleDate(iso) || iso;
        } catch {
            return iso;
        }
    }

    /** "Today" / "Tomorrow" / the weekday inside a week / the date — the
     *  shared relative-day wording, which compares *local* midnights (the old
     *  `toISOString()` comparison named the wrong day before 10am in AEST).
     *  No "(overdue)" suffix (2026-09-27): a past date already says it, and
     *  the figure's ink carries the emphasis. */
    const shopDayFigure = computed<Figure>(() => {
        const d = props.detail.planned_shop_date;
        if (!d) {
            return { key: 'shopday', value: 'Not set', label: 'Shop day', tone: 'dora-text-muted', partial: false };
        }
        const diff = daysFromToday(d);
        const tone = diff === 0 ? 'text-positive' : diff !== null && diff < 0 ? 'text-negative' : '';
        return { key: 'shopday', value: formatRelativeDay(d), label: 'Shop day', tone, partial: false };
    });

    // ── The sort control ──────────────────────────────────────────────
    // Was two identical bars — one on the plan face, one inside
    // `ShoppingListRunFace` — which is how they were free to drift. The mode
    // lists still differ by face (curating a list is a different job from
    // walking a shop), so that difference is stated here rather than duplicated.
    /** Plan / shop / receipt — the card's face *is* the tense. */
    const storeSpendTense = computed<'plan' | 'shop' | 'receipt'>(() => {
        switch (face.value) {
            case 'run': return 'shop';
            case 'receipt': return 'receipt';
            default: return 'plan';
        }
    });

    const sortModes = computed<SectionMode[]>(() => {
        if (face.value === 'run') return SECTION_MODES;
        // A receipt is a record. There is nothing to reorder for, and an empty
        // list means the control never renders.
        if (face.value === 'receipt') return [];
        return PLAN_SECTION_MODES;
    });

    const linesRef = computed(() => props.lines);
    const modeRef = computed(() => props.mode);
    const { availableModes, effectiveMode } = useLineSections(linesRef, modeRef, {
        allowedModes: sortModes,
    });

    const sortOptions = computed(() => sortModes.value.map((m) => ({
        label: SECTION_MODE_LABELS[m],
        value: m,
        disable: !availableModes.value[m],
    })));

    /** Names the modes this list can't offer, so a greyed-out segment still
     *  says why — the per-button tooltips it replaces carried that. */
    const unavailableLabel = computed(() => {
        const missing = sortModes.value.filter((m) => !availableModes.value[m]);
        if (missing.length === 0) return null;
        const names = missing.map((m) => SECTION_MODE_LABELS[m].toLowerCase());
        const list = names.length === 1
            ? names[0]
            : `${names.slice(0, -1).join(', ')} or ${names.at(-1)}`;
        return `Nothing on this list has ${list === names[0] ? 'a ' : ''}${list} set`;
    });

    // ── The review half ───────────────────────────────────────────────
    /** The figures that don't earn the lead row. */
    const secondaryFigures = computed(() => {
        const figures: { label: string; value: string; tone: string }[] = [];
        if (!moneyEnabled.value) return figures;
        const totals = props.detail.totals;

        // Mid-shop the lead figure is what's *left*, so the whole trip's figure
        // moves down here rather than disappearing.
        if (face.value === 'run') {
            figures.push({
                label: 'Trip total',
                value: formatMoney(totals.total_price),
                tone: '',
            });
        }
        if (face.value === 'receipt' && totals.total_savings > 0) {
            figures.push({
                label: 'You saved',
                value: formatMoney(totals.total_savings),
                tone: 'text-positive',
            });
        }
        return figures;
    });
</script>

<style scoped>
    /* The surface pass (v4 §4.2). This card used `--radius-md` (6px, the
       squarest non-trivial rung) and a flat 1px border with no elevation at
       all — the same treatment as the line list, the empty state and
       `StoreSpendCard`, so nothing on the page receded and the whole thing
       read as a stack of equal grey boxes. `--radius-xl`, `--elevation-card`
       and `--hero-gradient` were all already in `tokens.scss`, unused here.

       The hairline carries the dark themes. `--elevation-card` is a shadow,
       and a shadow does nothing on `pesto-dark`'s near-black page (5%
       lightness) — but there `--surface-component` is *lighter* than the page,
       so the card separates by luminance and the border draws its edge. In
       the light themes it is the other way round: the shadow does the work and
       the hairline is barely visible. One declaration, correct in both, and no
       `prefers-color-scheme` query — which would have been wrong anyway, since
       Dora's themes are `data-theme` attributes, not a media state. */
    .sl-overview {
        border: 1px solid var(--border-default);
        border-radius: var(--radius-xl);
        background: var(--surface-component);
        box-shadow: var(--elevation-card), var(--elevation-2);
        margin-bottom: var(--space-5);
        overflow: hidden;
    }
    /* The band. Gradient on the faces where the list is still happening, flat
       on the receipt (owner call 2026-08-31) — so the surface itself carries
       state: a live list is a coloured band, a finished one is paper. The
       three faces end up differently *material*, not merely differently
       arranged, which is a stronger signal than the status pill alone. */
    /* Trimmed 2026-09-17 (owner: the card is *"oversized … could be a bit
       slimmer"*). It measured 225px at 1440 and 390px on a phone for a draft
       carrying one figure, one date and two controls. Every cut here is
       padding, leading or a min-height — no fact left the card. */
    .sl-overview > :deep(.collapsible-card__header) {
        padding: var(--space-3) var(--space-3) var(--space-3) var(--space-4);
    }
    /* Direct child only. `:deep(.collapsible-card__header)` matched *any*
       header underneath, and `StoreSpendCard` is itself a `CollapsibleCard` —
       so the gradient band, and the header padding with it, were being painted
       a second time inside this card's own body. That second band is most of
       what made the store breakdown read as a card within a card. */
    .sl-overview--plan > :deep(.collapsible-card__header),
    .sl-overview--run > :deep(.collapsible-card__header) {
        background: var(--hero-gradient);
    }
    /* On `__inner`, not `__body`: the body is the box `q-slide-transition`
       animates, and padding or a border there is height the animation can't
       collapse — which is the closing snap. See `CollapsibleCard`. */
    .sl-overview > :deep(.collapsible-card__body) {
        background: var(--surface-component);
    }
    .sl-overview > :deep(.collapsible-card__body) > .collapsible-card__inner {
        padding: var(--space-3) var(--space-4) var(--space-4);
        border-top: 1px solid var(--divider);
    }
    /* The caret sits *over* the header's top-right corner rather than taking a
       column beside it (2026-09-17). `CollapsibleCard`'s default is a flex row
       — lead, then caret — which is right for a card whose header is a single
       title line, but this header is a stack of full-width blocks: the column
       shortened every one of them by 44px, so the figure, the dateline and the
       controls all stopped 44px short of the card's right edge while the rows
       below ran the full width. Only the identity row, which the caret is
       actually beside, reserves room for it. */
    .sl-overview > :deep(.collapsible-card__header) {
        position: relative;
        display: block;
    }
    .sl-overview > :deep(.collapsible-card__header) > .collapsible-card__caret {
        position: absolute;
        top: var(--space-2);
        right: var(--space-2);
    }
    .sl-overview__head {
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
        min-width: 0;
    }
    /* Row 1 sits level with the caret, so it reserves the caret's width. */
    .sl-overview__figures {
        display: flex;
        align-items: flex-start;
        flex-wrap: wrap;
        gap: var(--space-2) var(--space-6);
        min-width: 0;
        padding-right: 44px;
    }
    .sl-overview__label {
        font-size: calc(var(--font-size-xs) * 1rem);
        color: var(--text-secondary);
        line-height: 1.3;
    }
    .sl-overview__amount {
        font-size: calc(var(--font-size-2xl) * 1rem);
        font-weight: 700;
        line-height: 1.1;
        letter-spacing: -0.02em;
        font-variant-numeric: tabular-nums;
    }
    @media (max-width: 599px) {
        .sl-overview__figures {
            gap: var(--space-2) var(--space-5);
        }
        .sl-overview__amount {
            font-size: calc(var(--font-size-xl) * 1rem);
        }
    }
    .sl-overview__approx {
        font-weight: 500;
        opacity: 0.65;
    }
    .sl-overview__partial {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        margin-top: 2px;
        font-size: calc(var(--font-size-xs) * 1rem);
        color: var(--text-secondary);
    }
    /* Mid-shop progress: a bar the width of the card with the count inside it.
       R-002 carve-out (carried over from the segmented control it replaces):
       the track is a white veil over the gradient band, so it belongs to the
       band in every theme rather than sitting on it as a grey patch. */
    .sl-overview__progress {
        position: relative;
        height: 24px;
        border-radius: var(--radius-pill);
        background: hsla(0, 0%, 100%, 0.55);
        border: 1px solid var(--border-default);
        overflow: hidden;
    }
    .sl-overview__progress-fill {
        position: absolute;
        inset: 0 auto 0 0;
        background: var(--semantic-positive);
        transition: width var(--motion-slow) var(--motion-ease-out);
    }
    @media (prefers-reduced-motion: reduce) {
        .sl-overview__progress-fill {
            transition: none;
        }
    }
    .sl-overview__progress-text {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
        font-size: calc(var(--font-size-sm) * 1rem);
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        color: var(--text-primary);
    }
    /* Row 3: pill (and, on desktop, the name) left; controls right. Wraps
       rather than overflowing if a long name meets three buttons. */
    .sl-overview__foot {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: var(--space-2);
        min-width: 0;
    }
    .sl-overview__identity {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        min-width: 0;
        flex: 1 1 auto;
    }
    .sl-overview__name {
        min-width: 0;
    }
    .sl-overview__actions {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        flex: none;
        margin-left: auto;
    }
    /* Icon and caret only on a phone, so the pill and three controls share
       one row at 375px. */
    @media (max-width: 599px) {
        .sl-overview__foot,
        .sl-overview__actions {
            gap: var(--space-1);
        }
        .sl-overview__actions > .q-btn {
            padding-left: var(--space-3);
            padding-right: var(--space-3);
        }
        .sl-overview__group :deep(.q-btn__content) {
            gap: 0;
        }
        .sl-overview__actions > .sl-overview__group {
            padding-left: var(--space-2);
            padding-right: var(--space-1);
        }
    }
    .sl-overview__detail {
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
        padding-top: var(--space-3);
    }
    .sl-overview__secondary {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-1) var(--space-4);
    }
    .sl-overview__stat {
        display: flex;
        align-items: baseline;
        gap: var(--space-1);
        font-size: calc(var(--font-size-sm) * 1rem);
        font-variant-numeric: tabular-nums;
    }

    /* B2 status pill. Bigger and better-dressed than the bare text pill it
       replaces (2026-08-29 feedback): a glyph, a real chip height, and
       `--font-size-sm` — D-003's floor for a chip carrying a value. Soft
       background + full-strength semantic ink, never the soft token on both
       (the D-002 badge failure). */
    .sl-status-pill {
        display: inline-flex;
        align-items: center;
        gap: var(--space-1);
        flex: none;
        border-radius: var(--radius-pill);
        padding: var(--space-1) var(--space-3);
        min-height: 28px;
        font-size: calc(var(--font-size-sm) * 1rem);
        font-weight: 600;
        line-height: 1.2;
        white-space: nowrap;
        border: 1px solid transparent;
    }
    /* A draft hasn't happened yet — neutral, and quiet enough not to compete
       with the "Start shopping" button on the row below it. */
    .sl-status-pill--draft {
        background: var(--surface-sunken);
        color: var(--text-secondary);
        border-color: var(--border-default);
    }
    /* Mid-shop is a state you're in, not an achievement. */
    .sl-status-pill--shopping {
        background: var(--semantic-info-soft);
        color: var(--semantic-info);
        border-color: var(--semantic-info);
    }
    /* Finishing the shop is the success in this lifecycle, so this is the one
       that earns the positive token. */
    .sl-status-pill--done {
        background: var(--semantic-positive-soft);
        color: var(--semantic-positive);
        border-color: var(--semantic-positive);
    }

</style>
