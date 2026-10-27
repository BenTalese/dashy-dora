<template>
    <!-- No `to`, and no `#action`. The whole card used to be a router-link to
         /settings/money with a "Settings →" / "Set a budget →" caption in the
         header; both went on 2026-09-08 with every other card's link out
         (owner: *"you can just click the main menu buttons"*). The no-target
         body below still names where the budget is set, in a sentence rather
         than as chrome — because that one is not navigation, it is the answer
         to "why is this card empty". -->
    <DashboardCard :icon="ICONS.savings" title="My budget">
        <CardLoadError
            v-if="budgetFailed"
            line="I couldn't load your spend for this period."
            @retry="emit('retry-budget')"
        />
        <div v-else-if="budget" class="dora-budget-body">
            <div class="dora-budget-headline">
                <span
                    class="dora-budget-spent"
                    :class="{ 'text-negative': budget.over_budget }"
                >
                    {{ formatMoney(budget.spent) }}
                </span>
                <span class="dora-budget-of">
                    {{ budget.enabled
                        ? `of ${formatMoney(budget.amount!)} this ${periodWord}`
                        : `spent this ${periodWord}` }}
                </span>
                <span
                    v-if="budget.enabled"
                    class="dora-budget-remaining"
                    :class="budget.over_budget ? 'text-negative' : 'dora-text-muted'"
                >
                    {{
                        budget.over_budget
                            ? `${formatMoney(Math.abs(budget.remaining ?? 0))} over`
                            : `${formatMoney(budget.remaining ?? 0)} left`
                    }}
                </span>
            </div>
            <q-linear-progress
                v-if="budget.enabled"
                :value="Math.min(1, budget.spent / (budget.amount || 1))"
                :color="budget.over_budget ? 'negative' : 'primary'"
                class="q-mt-sm"
                size="8px"
                rounded
            />
            <!-- Owner 2026-09-08 — *"The '+$## in active lists' text is not very
                 obvious."* It wasn't: a bare "+$34.20 in active lists" in caption
                 grey under a progress bar reads as an addendum to the number
                 above it, and the reader has to work out that the plus means
                 *not yet spent* rather than *also spent*. Same figure, said as a
                 sentence, on its own tinted row with a cart icon — so it reads
                 as a separate, forward-looking fact about the open lists rather
                 than an adjustment to this period's spend. -->
            <div v-if="budget.projected_active > 0" class="dora-budget-pending">
                <q-icon :name="ICONS.shopping_cart" size="16px" />
                <span>
                    <strong>{{ formatMoney(budget.projected_active) }}</strong>
                    still to buy on your open lists
                </span>
            </div>
        </div>

        <!-- With the savings half gone, `budget === null` would otherwise render
             an empty card. It is a brief state (the page fetches budget in
             parallel with the summary the grid waits on) but not an impossible
             one, and a card with nothing in it reads as broken rather than as
             loading. -->
        <div v-else class="dora-text-muted text-caption">Loading…</div>
    </DashboardCard>
</template>

<script lang="ts" setup>
    /**
     * "My budget" — spend against the household's budget period, and nothing
     * else.
     *
     * This was `MoneyCard` / "Grocery spend", and the 2026-09-08 owner batch cut
     * it down to what its title claims:
     *
     *   · **"Kept vs RRP" is gone** — *"remove the bottom part 'kept vs RRP',
     *     product data is a niche area of the app"*. That half carried its own
     *     range toggle, its own window (which R-071 then required be labelled,
     *     because it never matched the budget period above it), an `InfoTip`
     *     explaining what RRP meant, and an `AnimatedNumber`. All of it to state
     *     a figure that only exists on installs whose lines carry captured deal
     *     prices — i.e. the products path. It is still on `/reports`, which is
     *     the surface for a retrospective money question.
     *   · **the swaps bullet is gone** — *"what's with the 'save $$$ this week #
     *     swaps ready'? Substitutes are for cooking when you must use one, not
     *     to get a cheaper shop."* He is right about the semantics, and the
     *     bullet was also a third window on one card (the current *plan* week,
     *     which is neither of the other two). FU-451's swap panel keeps its
     *     home in the planner, where the swap is actually made.
     *   · **the active-lists line was reworded** — see the template.
     *
     * What that leaves is one window, one question, one number, which is what
     * ADR-068's "spend is the headline" was reaching for; the supporting line it
     * kept was simply the wrong support.
     *
     * ⚠️ **`savings` / `SavingsCapturedResponse` no longer has a dashboard
     * caller.** It is NOT orphaned — `/reports` still calls it — but per R-057 a
     * replaced surface's contracts are an inventory to check: see FU-898.
     *
     * Extracted from `DashboardPage.vue` (FU-829). The page keeps the fetch.
     */
    import { computed } from 'vue';
    import { ICONS } from 'src/style/icons';
    import { formatMoney } from 'src/composables/useMoney';
    import DashboardCard from 'src/components/dashboard/DashboardCard.vue';
    import CardLoadError from 'src/components/dashboard/CardLoadError.vue';
    import type { BudgetStatus } from 'src/services/api/budgetApiService';
    import type { BudgetPeriod } from 'src/models/auth';

    const props = withDefaults(
        defineProps<{
            budget: BudgetStatus | null;
            budgetFailed?: boolean;
        }>(),
        { budgetFailed: false },
    );

    const emit = defineEmits<{ (e: 'retry-budget'): void }>();

    /** "weekly" → "week", "monthly" → "month" — the period read as a noun. */
    const PERIOD_WORD: Record<BudgetPeriod, string> = { weekly: 'week', monthly: 'month' };
    const periodWord = computed(() => (props.budget ? PERIOD_WORD[props.budget.period] : ''));
</script>

<style scoped lang="scss">
    /* Moved with the card (R-027). Was on the page's `--c-*` aliases, which are
       declared on `.dora-dash` and resolve to nothing from a component (R-060);
       on the real tokens now.

       The `.dora-money-savings*` block went with the savings half, and
       `.dora-swap-bullet*` with the swaps line (owner, 2026-09-08). Neither had
       another consumer — grepped before deleting. */
    .dora-budget-body {
        padding: var(--space-1) var(--space-1) var(--space-2);
    }
    .dora-budget-headline {
        display: flex;
        align-items: baseline;
        gap: var(--space-2);
        flex-wrap: wrap;
    }
    .dora-budget-spent {
        font-size: calc(var(--font-size-2xl) * 1rem);
        font-weight: 700;
    }
    .dora-budget-of {
        font-size: calc(var(--font-size-md) * 1rem);
        color: var(--text-secondary);
    }
    .dora-budget-remaining {
        margin-left: auto;
        font-size: calc(var(--font-size-sm) * 1rem);
        font-weight: 600;
    }
    /* The reworded active-lists row. A tinted well with its own icon, not a
       caption: the point of the rework is that this is a *different* fact from
       the headline, and a caption directly under a progress bar reads as a
       footnote to it. `--surface-sunken` + `--text-secondary` keeps it quieter
       than the headline while still being a row you notice — the `<strong>`
       money figure carries the emphasis (D-002: the readable secondary token,
       never a muted grey for a number that matters). */
    .dora-budget-pending {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        margin-top: var(--space-3);
        padding: var(--space-2) var(--space-3);
        border-radius: var(--radius-md);
        background: var(--surface-sunken);
        color: var(--text-secondary);
        font-size: calc(var(--font-size-sm) * 1rem);
    }
    .dora-budget-pending .q-icon {
        color: var(--text-secondary);
        flex-shrink: 0;
    }
    .dora-budget-pending strong {
        color: var(--text-primary);
        font-weight: 700;
    }
</style>
