<template>
    <!-- FU-609 / R-036 — root on <q-page> for the layout height contract.
         Document-scroll page (the window scrolls the dashboard); no :style-fn. -->
    <q-page class="dora-dash">
        <!-- ───── Hero band ─────────────────────────────────────────────── -->
        <!-- Owner 2026-09-04 — "Dora says" was a separate dismissible band
             directly under this one, with its own 40px mascot. Two problems,
             both his: the band repeated the mascot standing right beside it
             ("Dora is literally right there. Seeing double feels a bit odd"),
             and it was a second card saying a softer version of what the hero
             already said. So the message moved *into* the hero and the band is
             gone — which also retires the per-day dismissal (`dashboard_welcome_
             dismissed_day` + `epochDay`): you can't dismiss half a header, and a
             message that rotates daily never needed a hide button.

             The factual line under the greeting went with it. It read
             "N items are out of stock", which the owner called out as pretty
             useless text to read — the alerts bell and the stock card both
             already answer that, better. Dora's message is the line now. -->
        <section class="dora-hero">
            <q-avatar size="72px" square class="dora-hero-mascot">
                <img src="../assets/logo-mascot.png" alt="Dashy Dora" />
            </q-avatar>
            <!-- Owner 2026-09-05 — greeting + message sit beside the mascot at
                 every width (the old flex hero wrapped the whole text column
                 under it on mobile), and the hint drops to its own row that
                 stops at the actions column, so it wraps before the Cards
                 button rather than running under it. That's a grid, not a
                 flex row: the two claims are "same row as the mascot" and
                 "spans only the first two columns", which flex can't state. -->
            <div class="dora-hero-text">
                <div class="dora-hero-greeting">
                    {{ greeting }}<span v-if="firstName">, {{ firstName }}</span>
                </div>
                <div class="dora-hero-line">{{ welcomeMessage }}</div>
            </div>

            <div class="dora-hero-actions">
                <!-- D3 / feedback C16: the manual refresh button was removed —
                     `onMounted(loadAll)` already refreshes on every navigation
                     to the dashboard, so the button earned nothing. `loadAll`
                     itself stays (alert actions re-fetch through it). -->
                <!-- Icon-only below `sm`, the same rule Settings' sign-out
                     follows — the label is what pushed the greeting's line
                     into an early wrap on a phone. D-005: an icon-only
                     control keeps its accessible name and a tooltip. -->
                <BaseButton
                    variant="ghost"
                    dense
                    :icon="ICONS.tune"
                    :label="$q.screen.lt.sm ? undefined : 'Cards'"
                    aria-label="Cards"
                >
                    <BaseTooltip v-if="$q.screen.lt.sm">Show &amp; order cards</BaseTooltip>
                    <q-menu anchor="bottom right" self="top right" transition-show="jump-down" transition-hide="jump-up">
                        <q-list dense class="dashboard-cards-menu">
                            <q-item-label header>Show & order cards</q-item-label>
                            <!-- One flat list since the owner cut the zones
                                 (2026-09-04): reorder now spans every card
                                 rather than being trapped inside a band. The
                                 up/down buttons are C13's tap-mandatory
                                 alternative — they work on mobile and from the
                                 keyboard; drag is the desktop extra. -->
                            <q-item
                                v-for="card in menuCards"
                                :key="card.id"
                                :class="cardDnd.bind(card.id).rowClass"
                                v-bind="cardDnd.bind(card.id).rowProps"
                            >
                                <!-- desktop-only drag handle. The
                                     up/down buttons remain (C13's
                                     tap-mandatory alternative); drag is
                                     the power-user extra. The handle's
                                     `draggable` attribute is gated by
                                     `$q.platform.is.mobile` so touch
                                     devices keep tap-only. -->
                                <q-item-section
                                    v-if="cardDragEnabled"
                                    avatar
                                    class="dora-dnd-handle"
                                    v-bind="cardDnd.bind(card.id).handleProps"
                                >
                                    <q-icon :name="ICONS.drag_indicator" />
                                    <BaseTooltip>Drag to reorder</BaseTooltip>
                                </q-item-section>
                                <q-item-section avatar>
                                    <q-icon :name="card.icon" />
                                </q-item-section>
                                <q-item-section>{{ card.label }}</q-item-section>
                                <q-item-section side>
                                    <div class="row items-center no-wrap">
                                        <BaseButton
                                            :aria-label="`Move ${card.label} up`"
                                            variant="icon"
                                            size="sm"
                                            :icon="ICONS.arrow_upward"
                                            :disable="!canMove(card.id, 'up')"
                                            @click="moveCard(card.id, 'up')"
                                        >
                                            <BaseTooltip>Move up</BaseTooltip>
                                        </BaseButton>
                                        <BaseButton
                                            :aria-label="`Move ${card.label} down`"
                                            variant="icon"
                                            size="sm"
                                            :icon="ICONS.arrow_downward"
                                            :disable="!canMove(card.id, 'down')"
                                            @click="moveCard(card.id, 'down')"
                                        >
                                            <BaseTooltip>Move down</BaseTooltip>
                                        </BaseButton>
                                        <q-toggle
                                            :model-value="isCardVisible(card.id)"
                                            @update:model-value="toggleCard(card.id)"
                                        />
                                    </div>
                                </q-item-section>
                            </q-item>
                        </q-list>
                    </q-menu>
                </BaseButton>
            </div>

            <!-- Owner 2026-09-08 — *"Put the hint from the hero card into an
                 info box with an info icon at the front, like how you'd see it
                 in markdown/obsidian styling. Gives it some visual separation
                 and makes it look nice. It should still be within the hero
                 card."* It was a bare grey line under the greeting, which read
                 as a third sentence of the same paragraph rather than as a
                 different *kind* of thing — Dora's message of the day is voice,
                 the hint is a tip about the app.

                 An Obsidian-style callout is exactly the right borrow: a tinted
                 well, a leading rule in the accent tone, and an icon that
                 declares the genre before you read a word. The app already had
                 this shape once — `.dora-welcome`'s `border-left: 4px` band —
                 so this is the house pattern, not a new one.

                 Left inline rather than extracted to a component: this is its
                 only consumer. The moment a second callout appears anywhere
                 (Help, Settings, an empty state) it becomes a `BaseCallout` and
                 this markup moves into it (R-001 — two consumers is a pattern,
                 one is a card). -->
            <aside class="dora-hero-hint" role="note">
                <q-icon :name="ICONS.info" size="18px" class="dora-hero-hint__icon" />
                <span>{{ welcomeHint }}</span>
            </aside>
        </section>

        <!-- The Phase 5 quick-action bar (Add item · Add to list · Log price)
             was removed on the owner's call, 2026-09-04. §9's "the home screen
             *does*, not just routes" is still right, but these three were not
             how it does it: each opened a dialog reachable from the surface
             that actually owns the object, and none of them was the thing you
             came to the dashboard to do. The cards below all carry their own
             verbs (Cook, Add to list, Use it up), which is doing-not-routing
             attached to a reason. The dialogs themselves are untouched — the
             global QuickAddSheet and LogPriceSheet keep every other caller. -->

        <!-- FU-840 / §3.13 — the banner carries its own Retry. Its copy used to
             say "Try refreshing", which pointed at the manual refresh button that
             D3 deliberately removed; and when the summary fails the whole grid
             renders nothing (every card reads off `summary`), so this banner was
             the only thing on the page with no way forward. -->
        <q-banner v-if="loadError" class="dora-bg-negative-soft text-negative q-mb-md" dense rounded>
            {{ loadError }}
            <template #action>
                <BaseButton
                    variant="ghost"
                    dense
                    :icon="ICONS.refresh"
                    label="Try again"
                    :loading="loading"
                    @click="loadAll"
                />
            </template>
        </q-banner>

        <!-- D1's second band — the rotating "Dora says" welcome — merged into
             the hero above (see the note there). What survives here is the
             *first* band: the 24h skip-reminder (F1), which owns the
             not-yet-finished-onboarding window. It stays because it is not a
             greeting — it's a one-off state with two verbs, and it genuinely
             disappears once you finish or hide it.

             Its 40px mascot went the way of the welcome band's, for the same
             reason: the 72px one is ~60px above it. -->
        <transition name="fade">
            <aside
                v-if="showSkipReminder"
                class="dora-welcome dora-welcome--warn q-mb-md"
                role="note"
                aria-label="Finish setup"
            >
                <div class="dora-welcome-body">
                    <div class="dora-welcome-line">
                        <strong>Welcome.</strong> You skipped the setup wizard.
                        It takes about two minutes.
                    </div>
                    <div class="dora-welcome-actions">
                        <BaseButton
                            variant="ghost"
                            dense
                            :icon="ICONS.east"
                            label="Continue"
                            :loading="continuingOnboarding"
                            @click="onContinueOnboarding"
                        />
                        <BaseButton
                            variant="ghost"
                            dense
                            :icon="ICONS.close"
                            label="Hide"
                            @click="dismissSkipReminder"
                        />
                    </div>
                </div>
            </aside>
        </transition>

        <FadeTransition mode="out-in">
        <!-- D-007 (DR-8): a content-shaped skeleton of the card grid, not a
             lone centred spinner — the dashboard settles into its own shape
             rather than flashing empty then popping. Reuses the real
             DashboardCard shell so the placeholders match the loaded cards by
             construction. -->
        <div
            v-if="loading && !summary"
            key="dash-loading"
            class="row q-col-gutter-lg dora-cards"
            aria-hidden="true"
        >
            <!-- Skeleton placeholders take the same half-width shape the real
                 cards do, so the loading grid settles into the loaded one
                 rather than reflowing (D-007). Four is an even count, so it
                 needs no parity fix of its own. -->
            <div v-for="n in 4" :key="n" :class="CARD_COL_HALF">
                <DashboardCard>
                    <template #title>
                        <AppSkeleton type="line" width="45%" />
                    </template>
                    <AppSkeleton type="line" width="92%" class="dash-skel-line" />
                    <AppSkeleton type="line" width="78%" class="dash-skel-line" />
                    <AppSkeleton type="line" width="64%" class="dash-skel-line" />
                </DashboardCard>
            </div>
        </div>

        <!-- `q-col-gutter-lg` is 24px = `--space-6`, which is what B4 specifies
             between sibling cards; this grid was on `-md` (16px). -->
        <div v-else-if="summary" key="dash-content" class="row q-col-gutter-lg dora-cards">
            <!-- The zone band headers (Phase 2) are gone with the zones
                 themselves — owner, 2026-09-04. They were full-width flex items
                 whose CSS `order` forced a line break before each band; with one
                 flat user-owned order there is no band to label, and the grid is
                 a plain run of cards whose parity is computed once. -->

            <!-- ───── Next to cook (FU-298; batch-aware since 2026-09-04) ─── -->
            <div
                v-if="cardRendered('next_to_cook')"
                :class="cardCol('next_to_cook')"
                :style="{ order: cardCssOrder('next_to_cook') }"
            >
                <NextToCookCard
                    :entries="nextToCook"
                    :has-planned-meals="hasPlannedMeals"
                    @cook="cookPlannedMeal"
                />
            </div>

            <!-- ───── Use it up (owner 2026-09-04) ────────────────────────── -->
            <!-- One of the two cards that replaced "Needs your attention" and
                 "Dora suggests". Answers "what's about to go off, and what can
                 I cook with it *right now*" by joining near-expiry stock to the
                 recipes that use it — a question neither the alerts bell (which
                 states the expiry and stops) nor the chat (which has to be
                 asked) answers on its own.

                 C-waste W5 note: this is also where the retired "Use soon" card
                 landed. PROPOSAL_WASTE_MINIMISATION §4.5 cut it and sent
                 near-expiry items to the attention card's `expired` /
                 `expiring_soon` alert kinds; that card is now gone too, and this
                 one carries the signal with the cook action §4.5 never had. -->
            <div
                v-if="cardRendered('use_it_up')"
                :class="cardCol('use_it_up')"
                :style="{ order: cardCssOrder('use_it_up') }"
            >
                <UseItUpCard
                    :items="useItUp?.items ?? []"
                    :recipes="useItUp?.recipes ?? []"
                    :failed="slotFailed('use_it_up')"
                    @retry="loadUseItUp"
                />
            </div>

            <!-- "Before you shop" and "Shopping lists" were cut here (owner,
                 2026-09-08). Before-you-shop overlapped Restock radar — *"I'm
                 inclined to axe before you shop and chuck 'planned' as a chip
                 on the rows for restock radar"* — and its `is_planned` signal
                 is now that chip. Shopping lists was *"useless, axe it"*; the
                 nav's own entry is the way there. Both endpoints
                 (`/dashboard/before-you-shop`, `/dashboard/lists`) were deleted
                 with them: the dashboard was each one's only consumer, checked
                 before deleting per R-057. -->

            <!-- ───── Kitchen health (P8-08 Dora Score) ─────────────────── -->
            <div
                v-if="cardRendered('dora_score')"
                :class="cardCol('dora_score')"
                :style="{ order: cardCssOrder('dora_score') }"
            >
                <DoraScoreCard />
            </div>

            <!-- FU-317's "Reconcile past meals" chip card is gone (owner,
                 2026-09-04): *"that's quite odd … instead put that metric as the
                 link to go do meal reconciliation"*. A card whose whole body was
                 one button had to assert its own importance; the same queue is
                 reached from the nudge on the meal-plans header, where it's in
                 context. -->

            <!-- ───── Stock card (with donut) ────────────────────────────── -->
            <div
                v-if="cardRendered('stock_items')"
                :class="cardCol('stock_items')"
                :style="{ order: cardCssOrder('stock_items') }"
            >
                <StockDonutCard
                    :total="summary.stock_items.total"
                    :in-stock="stockInStockCount"
                    :low="summary.stock_items.low_stock"
                    :out="summary.stock_items.out_of_stock"
                    :segments="stockSegments"
                    :low-link="stockLowLink"
                    :out-link="stockOutLink"
                    @open="goTo"
                />
            </div>

            <!-- ───── What's coming (FU-818: the week strip + the fortnight
                 calendar, merged) ────────────────────────────────────────────
                 These were two cards rendering the same days from two DIFFERENT
                 endpoints — the strip from `/dashboard/summary`'s 7-day
                 `upcoming_entries`, the grid from `/alerts/upcoming`'s 14 — so
                 the overlapping week could disagree on one screen with no way
                 to tell which was right (R-003). Now one card, one source, with
                 a 7/14-day range toggle; 7 is the default because a week is the
                 planning unit.
                 D-012 also applies: a 7-day pip strip and a 14-day dot grid are
                 the same widget at two zoom levels, so they were never two
                 cards' worth of information.
                 The old "Next up" callout is gone with them — it restated the
                 hero line verbatim (§3.2), which is where that sentence lives.
                 Fed by `/alerts/upcoming`, the strip also gains expiry and
                 shopping dots, which it never had. -->
            <div
                v-if="cardRendered('meal_plan')"
                :class="cardCol('meal_plan')"
                :style="{ order: cardCssOrder('meal_plan') }"
            >
                <WhatsComingCard
                    :cells="calendarCells"
                    :selected="effectiveCalDate"
                    :selected-day="selectedCalDay"
                    :failed="slotFailed('upcoming')"
                    @select="selectCalDate"
                    @retry="loadUpcoming"
                />
            </div>

            <!-- ───── Restock radar (Phase 5) ─────────────────────────────── -->
            <div
                v-if="cardRendered('restock')"
                :class="cardCol('restock')"
                :style="{ order: cardCssOrder('restock') }"
            >
                <RestockRadarCard
                    :rows="restockRadar?.rows ?? []"
                    :window-days="restockRadar?.window_days ?? 30"
                    :failed="slotFailed('restock')"
                    @retry="loadRestockRadar"
                />
            </div>

            <!-- ───── My budget (Phase 4 — the Money zone's one card) ─────── -->
            <!-- Was "Grocery spend" / `MoneyCard`, carrying a kept-vs-RRP half
                 and a budget-defense swaps bullet. The 09-08 batch cut both —
                 *"remove the bottom part 'kept vs RRP', product data is a niche
                 area of the app"* and *"Substitutes are for cooking when you
                 must use one, not to get a cheaper shop"* — so the card, its
                 title and its registry id are all just the budget now. -->
            <div
                v-if="cardRendered('my_budget')"
                :class="cardCol('my_budget')"
                :style="{ order: cardCssOrder('my_budget') }"
            >
                <BudgetCard
                    :budget="budgetStatus"
                    :budget-failed="slotFailed('budget')"
                    @retry-budget="loadBudget"
                />
            </div>

            <!-- "Spend by store" and "Pantry value" were cut here (owner,
                 2026-09-04). Spend-by-store is a report and Reports has it —
                 *"there shouldn't be overlap between the dashboard and the
                 report page"* — and pantry value is the same call the reports
                 review already made about stock valuation. Both endpoints stay;
                 the reports page is their caller. -->

            <!-- ───── Price drops (Phase 4 — products-gated) ─────────────── -->
            <div
                v-if="cardRendered('price_drops')"
                :class="cardCol('price_drops')"
                :style="{ order: cardCssOrder('price_drops') }"
            >
                <PriceDropsCard
                    :rows="priceDropRows"
                    :failed="slotFailed('price_drops')"
                    @retry="loadPriceDrops"
                />
            </div>

            <!-- §2.6: the `recipes`, `meals`, `shopping_lists` and `products`
                 counter cards were cut — raw totals answer no question the user
                 has. `shopping_lists` merged into the list card above
                 (the "+N other lists" footer); cookable-tonight + the week-ahead
                 cover the recipe questions; product totals → the Money zone
                 widgets (Phase 4). -->

            <div v-if="visibleCardCount === 0" class="col-12">
                <q-banner class="dora-bg-sunken">
                    All cards are hidden. Use the <q-icon :name="ICONS.tune" /> Cards menu above to show some.
                </q-banner>
            </div>
        </div>
        </FadeTransition>
    </q-page>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    // FU-820 — dates come from the shared date authority (D-006/R-003); the
    // page's own copies parsed `YYYY-MM-DD` as UTC midnight.
    import { formatDate, formatRelativeDay } from 'src/composables/useDateFormat';
    import { buildCalendarCells } from 'src/helpers/dashboardCalendar';
    import FadeTransition from 'src/components/transitions/FadeTransition.vue';
    import AppSkeleton from 'src/components/AppSkeleton.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import DashboardCard from 'src/components/dashboard/DashboardCard.vue';
    // FU-829 chunk 5 — cards extracted out of this page. Data stays owned here
    // (the parallel load, the per-slot error tracking and the post-action
    // refresh are page concerns); each card takes what it renders and emits what
    // it wants doing.
    import BudgetCard from 'src/components/dashboard/BudgetCard.vue';
    import PriceDropsCard from 'src/components/dashboard/PriceDropsCard.vue';
    import RestockRadarCard from 'src/components/dashboard/RestockRadarCard.vue';
    import StockDonutCard, {
        type DonutSegment,
    } from 'src/components/dashboard/StockDonutCard.vue';
    import NextToCookCard from 'src/components/dashboard/NextToCookCard.vue';
    import UseItUpCard from 'src/components/dashboard/UseItUpCard.vue';
    import WhatsComingCard, {
        type CalendarCell,
    } from 'src/components/dashboard/WhatsComingCard.vue';
    import DoraScoreCard from 'src/components/dashboard/DoraScoreCard.vue';
    import { storeToRefs } from 'pinia';
    // `AttentionCard` and its alert presentation helpers went with the card
    // (owner, 2026-09-04 — the alerts bell says the same thing one row above).
    // The `Upcoming` types stay: the merged calendar still reads
    // `/alerts/upcoming`, which is a dated-events feed, not the alert list.
    import {
        type Upcoming,
        type UpcomingDay,
    } from 'src/models/alert';
    import type { DashboardSummary, UpcomingMealPlanEntry } from 'src/models/dashboard';
    import { pickWelcome, pickHint } from 'src/helpers/dashboardMessages';
    import AlertApiService from 'src/services/api/alertApiService';
    import BudgetApiService, {
        type BudgetStatus,
    } from 'src/services/api/budgetApiService';
    import DashboardApiService, {
        type UseItUpResponse,
        type RestockRadarResponse,
    } from 'src/services/api/dashboardApiService';
    import OnboardingApiService from 'src/services/api/onboardingApiService';
    // `SavingsCapturedResponse` / `ReportRange` went with the savings half of
    // the money card (owner, 2026-09-08). `/reports` is that endpoint's only
    // consumer now — an inventory note, not an orphan (R-057 / FU-898).
    import ReportsApiService, {
        type PriceDropsResponse,
    } from 'src/services/api/reportsApiService';
    import { useAuthStore } from 'src/stores/authStore';
    import { onboardingSkippedAt, clearOnboardingSkipped } from 'src/helpers/onboardingSkip';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import {
        LOW_STOCK_SEQUENCE,
        OUT_OF_STOCK_SEQUENCE,
        findLevelBySequence,
    } from 'src/helpers/stockStatus';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { useBatchEnabled } from 'src/composables/useBatchEnabled';
    // The page refreshes Kitchen health with everything else in `loadAll` — see
    // the comment there for the staleness bug that made it necessary.
    import { useDoraScore } from 'src/composables/useDoraScore';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import { useDragDropList } from 'src/composables/useDragDropList';
    import { computed, onMounted, ref, watch } from 'vue';
    import { useQuasar } from 'quasar';
    import { useRouter } from 'vue-router';
    // FU-824 — reactive token reads for the SVG donut (see `stockSegments`).
    import { paletteToken } from 'src/composables/useThemePalette';
    import { useSlotLoader } from 'src/composables/useSlotLoader';
    // FU-631 #3 — column classes that never leave a card beside dead air.
    import { CARD_COL_HALF } from 'src/helpers/dashboardGrid';
    // FU-830 — the card registry, extracted so its default-visible count (a
    // decision §2.2 owns) can be held by a test rather than by nothing.
    import type { CardId } from 'src/helpers/dashboardCards';
    import { useCardLayout } from 'src/composables/useCardLayout';

    // FU-821 — every money render goes through `formatMoney`, including the
    // tweened <AnimatedNumber> ones (via its `format` prop). The old
    // `currencySymbol` prefix is gone: it returned the symbol only, so it lost
    // `formatMoney`'s decimals, grouping and locale-correct symbol *placement*
    // (D-006 — one formatting authority, not a symbol plus a guess). Those
    // renders now live in the extracted cards, which is why this page no longer
    // imports the formatter at all.

    // Card registry (ids, zones, gates, default visibility) + the zone list
    // now live in `helpers/dashboardCards.ts` — extracted in FU-830 so the
    // default-visible count, which is a decision §2.2 owns, can be asserted by
    // a test instead of drifting unnoticed. Read that file before adding a card.

    const authStore = useAuthStore();
    const router = useRouter();
    const $q = useQuasar();
    const { currentUser } = storeToRefs(authStore);

    // Feature gates for the Money/Products cards (Phase 4). `moneyEnabled`
    // layers install + per-user money opt-in (ADR-005); `productsEnabled` is the
    // install-wide products feature flag — which is what the owner asked Price
    // drops to be gated on (2026-09-04), and what it was already reading; the
    // registry comment calling it "data-presence" was simply wrong. Read by
    // `cardAvailable`.
    const { moneyEnabled } = useMoneyEnabled();
    const { products: productsEnabled } = useFeatureFlags();
    // Cook style — the install-wide batch switch. "Next to cook" selects
    // different rows under it (see `nextToCook`), and the card labels them.
    const { batchEnabled } = useBatchEnabled();
    // Only `refresh` — the card itself calls `useDoraScore()` for the value.
    // Both reach the same module-level singleton, so there is one fetch, one
    // cache and no second copy of the score on the page (R-003).
    const { refresh: refreshDoraScore } = useDoraScore();
    const dashboardApiService = new DashboardApiService();
    const alertApi = new AlertApiService();
    const budgetApi = new BudgetApiService();
    const reportsApi = new ReportsApiService();

    const shoppingListStore = useShoppingListStore();
    // donut segments deep-link to /stock?level_id=<id>. The stock
    // overview already reads `level_id` from the query; we just need the two
    // level ids (low / out) that match the canonical status sequences.
    const stockLevelStore = useStockLevelStore();
    const { stockLevels } = storeToRefs(stockLevelStore);

    const summary = ref<DashboardSummary | null>(null);
    const loading = ref(false);
    const loadError = ref<string | null>(null);

    // FU-825's per-day dismissal (`dora.dashboard.welcome_dismissed_day` +
    // `epochDay`) is gone with the welcome band: the message lives in the hero
    // now, and a header is not dismissible. The `localStorage` key is simply
    // abandoned — it was only ever read by the code above, so a stale value on
    // an existing install has nothing left to hide.

    // ── 24h "you skipped the wizard" reminder (F1) ───────────────────
    // The wizard stamps the skip (per user) on Skip-everything;
    // we surface a soft banner on the dashboard for 24 hours after that
    // moment. Dismissing it sets a session-scoped flag so the banner
    // stays hidden for this tab.
    const SKIP_REMINDER_WINDOW_MS = 24 * 60 * 60 * 1000;
    const skipReminderDismissed = ref(false);
    const showSkipReminder = computed(() => {
        if (skipReminderDismissed.value) return false;
        const stamped = onboardingSkippedAt(currentUser.value?.user_id);
        if (!stamped) return false;
        return Date.now() - stamped.getTime() < SKIP_REMINDER_WINDOW_MS;
    });
    function dismissSkipReminder() {
        skipReminderDismissed.value = true;
    }
    // Continue → re-open the wizard. The Skip-everything path stamps
    // `onboarding_completed_at` on the backend so subsequent visits don't
    // get bounced to /welcome. To re-enter we need that timestamp cleared
    // (POST /onboarding/restart) AND the cached auth state refreshed,
    // otherwise the router guard sees the stale non-null value and
    // bounces straight back here. Same shape as About → "Run the welcome
    // tour again".
    const onboardingApi = new OnboardingApiService();
    const continuingOnboarding = ref(false);
    async function onContinueOnboarding() {
        if (continuingOnboarding.value) return;
        continuingOnboarding.value = true;
        try {
            await onboardingApi.restartAsync();
            await authStore.refreshAsync();
            clearOnboardingSkipped(currentUser.value?.user_id);
            void router.push('/welcome');
        } finally {
            continuingOnboarding.value = false;
        }
    }

    // ── Per-slot failure tracking (FU-840) ──────────────────────────────
    // Every loader below used to `catch { thing.value = null }`, so the card
    // then rendered its **empty** state. A 500 on savings told a household that
    // had shopped for months "finish a shop and I'll tally what you kept"; a
    // failed alerts fetch said "all clear — nothing needs your attention".
    // Failure was indistinguishable from absence, in the direction that
    // reassures — Honesty inverted, eleven times (`DASHBOARD_PAGE_REVIEW.md`
    // §4.7 / finding 10).
    //
    // So each slot now records whether it failed (`useSlotLoader`), and its
    // card renders <CardLoadError> instead of "nothing here yet".
    type SlotId =
        | 'use_it_up'
        | 'budget'
        | 'price_drops'
        | 'restock'
        | 'upcoming';

    const { slotFailed, loadSlot } = useSlotLoader<SlotId>({ label: 'dashboard slot' });

    // Independent slot loaders. Each card surfaces a small chunk of data
    // beyond what the bulk dashboard summary endpoint returns. They live
    // in parallel and never block each other — one slow response shouldn't
    // gate the rest of the dashboard.
    //
    // `use-it-up` is a server-computed join — the client renders rows and emits
    // verbs (R-003); it does not decide what is expiring or what a recipe
    // covers. Its 09-04 sibling `beforeYouShop` and the `dashboardLists` ref
    // went with their cards on 09-08.
    const useItUp = ref<UseItUpResponse | null>(null);
    // Feeds the budget half of the merged Money card. Always loads (so the
    // passive "spent this period" figure works for users who haven't set a
    // target), and the block is `v-if`'d out when the loader errors so a failed
    // slot never blocks the rest of the card — the savings half still renders.
    const budgetStatus = ref<BudgetStatus | null>(null);
    // Phase 4 — money widgets backed by the reports API. Only loaded when money
    // is enabled (the cards are gated on it anyway). `spendByStore` and
    // `pantryValue` went with their cards on 2026-09-04 — both were reports on
    // the dashboard, and Reports is where they live. `savings` + its range and
    // FU-451's `swapSummary` went the same way on 09-08 when the owner cut the
    // money card down to the budget: the savings figure is retrospective and
    // product-dependent, and the swaps bullet was selling substitutes as a way
    // to shop cheaper, which is not what they are for.
    const priceDrops = ref<PriceDropsResponse | null>(null);
    // Restock radar — what just ran out and what just went low. Reworked on
    // the owner's ask (2026-09-04) off `/dashboard/restock-radar`; the old
    // `/reports/keeps-running-out` lifetime ranking stays on the reports page,
    // which still calls it.
    const restockRadar = ref<RestockRadarResponse | null>(null);
    // Phase 6 — the fortnight calendar's server-aggregated dated events + the
    // currently-expanded day.
    const upcoming = ref<Upcoming | null>(null);
    const selectedCalDate = ref<string | null>(null);

    // DR-4 (FU-578 #21): present the username capitalised so the greeting reads
    // "Good afternoon, Dora" not the raw lowercase handle "dora".
    const firstName = computed(() => {
        const name = currentUser.value?.username ?? '';
        return name ? name.charAt(0).toUpperCase() + name.slice(1) : '';
    });

    const greeting = computed(() => {
        const h = new Date().getHours();
        if (h < 5) return 'Up late';
        if (h < 12) return 'Good morning';
        if (h < 17) return 'Good afternoon';
        return 'Good evening';
    });

    // ── Dashboard layout prefs (server-persisted, §2.1) ──────────────────
    const {
        applyStored: applyLayoutFromUser, cardRendered, isCardVisible, toggleCard,
        visibleCardCount, cardCol, cardCssOrder, canMove, moveCard, dropCardOn, menuCards,
    } = useCardLayout({
        stored: () => currentUser.value?.dashboard_layout ?? null,
        persist: (layout) => {
            void authStore.updateMeAsync({ dashboard_layout: JSON.stringify(layout) });
        },
        moneyEnabled: () => moneyEnabled.value,
        productsEnabled: () => productsEnabled.value,
    });
    // Reload on user switch (or another device's update landing via refresh).
    watch(() => currentUser.value?.user_id, applyLayoutFromUser);

    // Drag-handle reorder for the Cards menu: the desktop extra on top of the
    // tap up/down (C13). Off on touch (`$q.platform.is.mobile` includes
    // tablets) so touch-first surfaces keep the tap path uncluttered.
    const cardDragEnabled = computed(() => !$q.platform.is.mobile);
    const cardDnd = useDragDropList<CardId>({
        mime: 'application/x-dora-dashboard-card',
        getId: (id) => id,
        canDragStart: () => cardDragEnabled.value,
        onDrop: ({ id: sourceId }, { id: targetId }) => dropCardOn(sourceId as CardId, targetId as CardId),
    });

    // ── Derived data for stock donut ─────────────────────────────────────
    const stockInStockCount = computed(() => {
        if (!summary.value) return 0;
        const s = summary.value.stock_items;
        // "In stock" = anything not low/out. Items with no stock level
        // (shouldn't happen with the seeded levels) fall into this bucket;
        // the alternative is a fourth "unknown" slice for an edge case.
        return Math.max(0, s.total - s.low_stock - s.out_of_stock);
    });

    // pre-computed deep-link targets for each donut bucket. Falls
    // back to the un-filtered `/stock` when the levels aren't loaded yet, so
    // clicks never dead-end.
    const stockLowLink = computed(() => {
        const lvl = findLevelBySequence(stockLevels.value, LOW_STOCK_SEQUENCE);
        return lvl ? `/stock?level_id=${lvl.stock_level_id}` : '/stock';
    });
    const stockOutLink = computed(() => {
        const lvl = findLevelBySequence(stockLevels.value, OUT_OF_STOCK_SEQUENCE);
        return lvl ? `/stock?level_id=${lvl.stock_level_id}` : '/stock';
    });

    // `DonutSegment` is the card's own shape, so it lives with the card and is
    // imported above. The *building* of the segments stays here: it needs the
    // stock-level ids for the deep links and the theme-token reads.
    const stockSegments = computed<DonutSegment[]>(() => {
        if (!summary.value || summary.value.stock_items.total === 0) return [];
        const total = summary.value.stock_items.total;
        const inStock = stockInStockCount.value;
        const low = summary.value.stock_items.low_stock;
        const out = summary.value.stock_items.out_of_stock;
        const pct = (n: number) => (n / total) * 100;

        // The SVG is rotated -90deg in CSS so the first segment starts at the
        // 12-o'clock position. stroke-dashoffset walks clockwise.
        let cursor = 0;
        const segs: DonutSegment[] = [];
        const push = (label: string, count: number, colour: string, link: string | null) => {
            if (count <= 0) return;
            const p = pct(count);
            segs.push({ label, percent: p, offset: cursor, colour, link });
            // Negative offsets walk clockwise around the circle.
            cursor = (cursor - p + 100) % 100;
        };
        // Read the semantic-* tokens off the document so the donut recolours
        // when the user switches theme without a full reload.
        //
        // FU-824: that comment was a lie until now. The read was a bare
        // `getComputedStyle`, which is not reactive, so this computed had no
        // dependency on the theme and the palette was sampled once and frozen —
        // switch light→dark on the dashboard and the donut kept its old colours
        // until the summary refetched. `paletteToken` touches a version ref that
        // `themeService.applyThemeKey` bumps, so the dependency is real now.
        const okColour = paletteToken('--semantic-positive', '#6ba368');
        const warnColour = paletteToken('--semantic-warning', '#e89a45');
        const badColour = paletteToken('--semantic-negative', '#c85a4f');
        // "In stock" has no bucket-filter — it's the residual; clicking the
        // segment does nothing (would need `?level_id != low/out`, which the
        // page doesn't model). Low + out link to their filtered view.
        push('in stock', inStock, okColour, null);
        push('low', low, warnColour, stockLowLink.value);
        push('out', out, badColour, stockOutLink.value);
        return segs;
    });

    // FU-818 — `weekStrip` is gone. It built its own 7 days from
    // `summary.meal_plan.upcoming_entries` while the fortnight calendar built 14
    // from `/alerts/upcoming`, so the overlapping week was answered twice from
    // two queries that could disagree (R-003). The merged card renders both
    // spans from `calendarCells`, i.e. from `/alerts/upcoming` alone — which
    // also gives the week view the expiry and shopping dots it never had.
    //
    // `nextEntry` went with the hero's factual line on 2026-09-04 — that
    // sentence was its only reader. The next meal is still stated, in the one
    // place that also says whether you can cook it: the "Next to cook" card.

    // ── Welcome + hint of the day (D1c/d/e) ──────────────────────────────
    // A day-of-week-flavoured welcome plus a day-agnostic hint, both stable
    // per calendar day (see helpers/dashboardMessages).
    //
    // These are the hero's two lines now (owner, 2026-09-04). They used to sit
    // in a dismissible band below it, under a second mascot, beneath a factual
    // "N items are out of stock" line — three separate things saying hello. The
    // factual line is gone (the owner: *"that feels like pretty useless text to
    // read"*), and with it `heroLine`, `plural` and `capitalise`, which nothing
    // else on the page used.
    //
    // The old `showWelcome` gate is gone too. It suppressed the greeting while
    // the skip-reminder banner was up, on the reasoning that the banner *was*
    // the message; that only made sense while both were bands competing for the
    // same slot. A header does not compete with a banner underneath it.
    const welcomeMessage = computed(() => pickWelcome());
    // FU-823 — the hint pool is filtered by the install's feature gates, so a
    // money-off household is never told to set a grocery budget and a
    // product-less one isn't sold the deals card (feedback L254 / ADR-005).
    const welcomeHint = computed(() =>
        pickHint({ money: moneyEnabled.value, products: productsEnabled.value })
    );

    // ── Helpers ──────────────────────────────────────────────────────────

    function goTo(path: string) {
        void router.push(path);
    }

    /**
     * Owner 2026-09-04 — *"When clicking cook now from a meal slot, auto adjust
     * the servings based on what the meal plan says for that slot."* The
     * planner's chips do this too (`useMealPlanner.cookRecipe`); this card is
     * the other place a planned meal opens cook mode, and opening it at the
     * household headcount when the plan says six is the same surprise.
     *
     * Owner 2026-09-05 — and it opens at the *batch's* yield where there is
     * one, which is the half this was missing: the summary endpoint now
     * carries `cook_batch_total_servings`, so the expression below is the same
     * one `useMealPlanner.cookRecipe` evaluates. Two surfaces, one figure.
     */
    function cookPlannedMeal(entry: UpcomingMealPlanEntry) {
        const serves = entry.cook_batch_total_servings ?? entry.servings;
        const query = serves > 0 ? `?for=${serves}` : '';
        goTo(`/cookbook/${entry.recipe_id}/cook${query}`);
    }

    // The alerts fetch and the alert-action handler went with `AttentionCard`
    // (owner, 2026-09-04). `alertApi` stays — the merged calendar below still
    // reads `/alerts/upcoming`, which is a different endpoint answering a
    // different question (dated events, not the alert list). The alert list
    // itself has one consumer now: the bell in the app header, which owns it.

    // ── Next to cook ────────────────────────────────────────────────────
    // Meal-plan-driven (feedback L272): upcoming entries from
    // `summary.meal_plan.upcoming_entries`, deduped by recipe so the same
    // recipe scheduled twice in the week only shows once (earliest slot wins),
    // capped at 3, each tagged with a ready / missing-N badge from the
    // server-derived `missing_count`.
    //
    // **Two selection strategies, keyed on cook style** (owner, 2026-09-04).
    // The 09-04 batch taught this card the pool model, but only as *labels* —
    // it still listed the next few days in order, which is the wrong question
    // for a household that batch-cooks. There, the plan is not a cook schedule:
    // one batch covers many planned days, so most of what's coming needs
    // nobody to cook it, and listing it is noise.
    //
    //   fresh household → the next planned meals, chronologically. Plan day is
    //                     cook day, so the calendar *is* the answer.
    //   batch household → the meals somebody actually has to cook: the ones the
    //                     pool is short of (`needs_cooking`), plus fresh-marked
    //                     entries (`cook_fresh`), which stand outside the pool
    //                     in both directions and are cooked on their own day.
    //
    // Both flags are server-owned and never both true (`_cook_verdicts` in
    // `get_dashboard_summary.py`) — this filters on the server's verdict, it
    // doesn't re-derive coverage (R-003). Chronological order is already "when
    // the shortfall bites", since the entries arrive sorted by date.
    const nextToCook = computed<UpcomingMealPlanEntry[]>(() => {
        const entries = summary.value?.meal_plan.upcoming_entries ?? [];
        const worthCooking = batchEnabled.value
            ? entries.filter((e) => e.needs_cooking || e.cook_fresh)
            : entries;
        const seen = new Set<string>();
        const picks: UpcomingMealPlanEntry[] = [];
        for (const e of worthCooking) {
            if (seen.has(e.recipe_id)) continue;
            seen.add(e.recipe_id);
            picks.push(e);
            if (picks.length >= 3) break;
        }
        return picks;
    });

    // Whether the week holds any planned meal at all — the card needs to tell
    // "nothing planned" apart from "planned, and the freezer already covers it",
    // which are the same empty list but opposite messages.
    const hasPlannedMeals = computed(
        () => (summary.value?.meal_plan.upcoming_entries.length ?? 0) > 0,
    );

    // The when-label and the ready/missing/to-link badge moved into
    // `NextToCookCard.vue` with the card (FU-829) — they are presentation of the
    // entry, and the tri-state badge logic is easier to follow next to the
    // markup that renders it.


    // The "Shopping lists" card and its `/dashboard/lists` endpoint were cut on
    // 2026-09-08 (*"useless, axe it"*), taking `shoppingListCards`,
    // `loadShoppingListCards` and the `quickAddTargetListId` watch that
    // refetched them with it. `shoppingListStore` still loads in `loadAll` —
    // `AddToListButton` on the Restock radar rows reads it.

    // ── Use it up (owner, 2026-09-04) ────────────────────────────────────
    // A server-computed join: near-expiry stock and the recipes that use it.
    // It could not be assembled client-side without the SPA re-implementing the
    // household's expiry window and the ingredient links — the exact "client
    // computing a cross-entity rule" smell the state-ownership principle names.
    // Its `before-you-shop` sibling was cut on 09-08; the plan-demand half of
    // that signal now rides on the Restock radar rows as `is_planned`.
    async function loadUseItUp() {
        await loadSlot('use_it_up', async () => {
            useItUp.value = await dashboardApiService.getUseItUpAsync();
        });
    }

    // No page-level add wrapper: both row-bearing cards render the shared
    // `AddToListButton` themselves, which is what the owner asked for — *"should
    // use the same shopping cart button from the stock overview rows"* — and is
    // the R-011 answer anyway. That component owns the target-list decision, the
    // already-on-a-list toggle and the toast, none of which the dashboard should
    // be re-deciding on the way past.

    async function loadSummary() {
        loading.value = true;
        loadError.value = null;
        try {
            summary.value = await dashboardApiService.getSummaryAsync();
        } catch (err) {
            // This one is fatal to the grid — every card reads off `summary`, so
            // the banner is the whole page's state. The copy no longer says "try
            // refreshing": D3 deliberately removed the refresh button, so that
            // sentence pointed at a control that doesn't exist. The banner now
            // carries its own Retry (§3.13).
            loadError.value = "I couldn't load your dashboard.";
            console.warn('dashboard summary failed', err);
        } finally {
            loading.value = false;
        }
    }

    async function loadBudget() {
        // budget is money-gated; skip the fetch when money is off.
        if (!moneyEnabled.value) { budgetStatus.value = null; return; }
        await loadSlot('budget', async () => {
            budgetStatus.value = await budgetApi.getStatusAsync();
        });
    }

    // ── Money zone loaders (Phase 4) ─────────────────────────────────────
    // Guarded on `moneyEnabled` — the cards are gated on it, so there's no point
    // fetching dollar reports when money is off. Each records its own failure
    // through `loadSlot` so the card can say "couldn't load this" rather than
    // "nothing here yet". The reports endpoints already aggregate server-side
    // (state-ownership) — we just render.
    //
    // `loadSavings` + `RANGE_LABEL` + `SAVINGS_RANGES` + the range watch, and
    // FU-451's `loadSwapSummary`, were all deleted on 2026-09-08 with the two
    // halves of the money card the owner cut. `loadSwapSummary` is worth a
    // note: it fetched `getTodayAsync` + `getAllAsync` + `getSwapSuggestions`
    // — three requests on every dashboard load — to decide whether to render
    // one bullet, and it did that client-side week arithmetic to find "the
    // current plan", which was a cross-entity rule living in the browser
    // (R-003). Cutting the bullet removes the smell with it. The swap panel
    // itself is untouched in the planner, which is where a swap is made.

    // `loadSpendByStore` and `loadPantryValue` went with their cards (owner,
    // 2026-09-04). `reportsApi.getSpendByStoreAsync` keeps its caller on the
    // reports page; the stock-value endpoint had none left and was deleted
    // (finalisation 12-R1).

    // price-drops is products-gated (not money-gated); still cheap to
    // load, hides itself when empty.
    async function loadPriceDrops() {
        if (!productsEnabled.value) { priceDrops.value = null; return; }
        await loadSlot('price_drops', async () => {
            priceDrops.value = await reportsApi.getPriceDropsAsync(5);
        });
    }
    const priceDropRows = computed(() => priceDrops.value?.rows ?? []);

    // ── Restock radar ────────────────────────────────────────────────────
    async function loadRestockRadar() {
        await loadSlot('restock', async () => {
            restockRadar.value = await dashboardApiService.getRestockRadarAsync();
        });
    }

    // `onStockItemCreated` went with the quick-action "Add item" dialog. The
    // dialog itself is untouched; every other caller opens it from the surface
    // that owns stock items.

    // ── Fortnight calendar (Phase 6 / D7) ────────────────────────────────
    // The server aggregates dated events (C-9.6 /alerts/upcoming); the client
    // only builds the grid + renders per-category dots (R-003 — no client-side
    // joining of three sources). `dates` carries non-empty days only, so we
    // walk the full window and look each date up.
    async function loadUpcoming() {
        await loadSlot('upcoming', async () => {
            upcoming.value = await alertApi.getUpcomingAsync(CALENDAR_DAYS);
        });
    }

    // FU-818's 7/14 range toggle is gone (owner, 2026-09-08 — *"Just show 14
    // days always, remove the toggle option"*), and with it `CALENDAR_SPANS`,
    // `calendarSpan`, `calendarSpanLabel` and the `CalendarSpan` type. It was
    // always slicing an already-fetched fortnight, so the control spent a
    // header widget hiding half of a payload the card had already paid for.
    // `CalendarCell` is still the card's own type, imported above.

    /** The fortnight the card shows, and the number `/alerts/upcoming` is asked
     *  for below — one constant, so the fetch and the grid can't disagree. */
    const CALENDAR_DAYS = 14;

    const calendarCells = computed<CalendarCell[]>(() =>
        buildCalendarCells(upcoming.value, CALENDAR_DAYS, {
            relativeDay: (iso) => formatRelativeDay(iso),
            weekdayShort: (day) => formatDate(day, { weekday: 'short' }),
        }),
    );
    /** A day is always shown, starting on today (owner, 2026-09-27). Tapping
     *  a day moves the selection; there is no "nothing selected" state to
     *  toggle back into. */
    const effectiveCalDate = computed<string | null>(() =>
        selectedCalDate.value ?? calendarCells.value.find((c) => c.isToday)?.iso ?? null
    );
    const selectedCalDay = computed<UpcomingDay | null>(() =>
        upcoming.value?.dates.find((d) => d.date === effectiveCalDate.value) ?? null
    );
    function selectCalDate(iso: string) {
        selectedCalDate.value = iso;
    }
    // FU-818 — `/alerts/upcoming` used to be lazy-loaded only when the opt-in
    // fortnight card was switched on (R-016). It is now the merged card's only
    // data source and that card is default-on, so it loads with everything else
    // in `loadAll` and the visibility watch is gone. Net request count is
    // unchanged for a user who had the calendar enabled, and +1 for everyone
    // else — who in exchange get expiry and shopping dots on their week view,
    // and one card instead of two rendering the same days.

    // The spend-by-store and pantry-value display slices went with their cards
    // (owner, 2026-09-04), as did `acceptSuggestion` / `dismissSuggestion` and
    // the `suggestionStore` refresh — the suggestion store keeps its other
    // consumers (the Dora launcher badge and the chat panel), which is where
    // the owner said this content belongs: *"we're keeping the Dora chat"*.

    async function loadAll() {
        // Fire everything in parallel — the hero/card shells render off the
        // bulk summary, each card has its own slot loader. Stores are deduped,
        // so calling getX() when already populated is ~free.
        await Promise.all([
            loadSummary(),
            loadUseItUp(),
            loadBudget(),
            loadPriceDrops(),
            loadRestockRadar(),
            // FU-818 — the merged "What's coming" card is default-on and this is
            // its only source, so it is no longer conditional.
            loadUpcoming(),
            // Owner 2026-09-08 — *"Noticed when testing the budget widget, the
            // budget health indicator stayed the same. For example, $20 over
            // budget with a monthly budget of $10 with the current seed data,
            // but the widget is on 100 'under budget this period'."*
            //
            // Nothing was wrong with the score's budget maths. The card's data
            // was simply **stale**: `useDoraScore` is a module-level singleton
            // with a 5-minute stale window, and the staleness is only tested
            // when the composable is *called* — i.e. when the card mounts.
            // Change your budget in Settings, come back inside five minutes,
            // and every other card refetches (this page calls `loadAll` on
            // every navigation, which is why D3 could delete the manual refresh
            // button) while Kitchen health re-renders the number it fetched
            // before the change. With the budget period switched weekly →
            // monthly, that number was computed against a *different window* —
            // hence "under budget" beside a card saying $20 over. Two windows,
            // one screen, no way to tell.
            //
            // So the dashboard refreshes the score with everything else. The
            // 5-minute window keeps doing its real job (a second consumer of
            // the composable, or a remount inside one navigation, doesn't
            // refetch); it just no longer decides what a deliberate page load
            // shows you. `refreshDoraScore` bypasses it outright — a `loadAll`
            // is the user asking for current numbers.
            refreshDoraScore(),
            shoppingListStore.ensureLoadedAsync(),
            // the donut's low/out segments deep-link to
            // /stock?level_id=<id>; the store hydrates those ids.
            stockLevelStore.ensureLoadedAsync(),
        ]);
    }

    // FU-586: the money/products cards gate on the once-per-document
    // `/api/health` flags probe (and, for money, on `currentUser`'s per-user
    // opt-in). On a cold load — a hard reload or a PWA cold start — those
    // usually haven't resolved when the dashboard mounts, so the gated loaders
    // above early-return and, with nothing re-running them when the flags land,
    // the money/deal card bodies stay blank until the user navigates away and
    // back. Re-fire just the gated loaders when a gate transitions on. On a warm
    // navigation the gate is already true at mount, `loadAll` fetches normally,
    // and these never fire.
    watch(moneyEnabled, (on) => {
        if (!on) return;
        void loadBudget();
        // The score's budget component is gated server-side on the same flag
        // (R-058), so a gate that lands late leaves Kitchen health scoring four
        // signals where it should score five.
        void refreshDoraScore();
    });
    watch(productsEnabled, (on) => {
        if (!on) return;
        void loadPriceDrops();
    });

    onMounted(loadAll);
</script>

<style scoped lang="scss">
    .dashboard-cards-menu {
        min-width: 300px;
    }
    /* ───── Page root ───────────────────────────────────────────────────
       FU-747 / chunk 6: the page-local `--c-*` alias layer that used to be
       declared here is **gone**. It mapped 14 global tokens to page-local
       names, which cost a second vocabulary for no behaviour (every alias
       resolved to exactly one global token), and it could not be seen by the
       scoped blocks of the card components — the file's own Cards-menu comment
       said as much. Everything below references the global tokens directly.
    */
    .dora-dash {
        min-height: 100%;
        /* The bottom value is 2 × --space-12: clearance for the mobile bottom
           bar, kept on the scale rather than the old off-scale 96px (A3). */
        padding: var(--space-6) var(--space-6) calc(var(--space-12) * 2);
        /* Dashboard reads the active theme's signature hero gradient as its
           page background — the "special touch" per theme. Every other surface
           reference here goes through the global tokens so the dashboard
           reskins automatically with the rest of the app. */
        background: var(--hero-gradient);
        color: var(--text-primary);
    }

    /* ───── Hero ─────────────────────────────────────────────────────── */
    /* Three columns — mascot · text · actions — and two rows, the second one
       stopping short of the actions column so the hint wraps before the Cards
       button instead of sliding under it (owner, 2026-09-05). Identical at
       every width: the greeting stays beside the mascot on a phone too, which
       is what the old `flex-wrap` mobile rule broke. */
    .dora-hero {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr) auto;
        align-items: center;
        column-gap: var(--space-4);
        row-gap: var(--space-2);
        padding: var(--space-6);
        margin-bottom: var(--space-6);
        background: var(--surface-component);
        border: 1px solid var(--border-default);
        /* A4/D-017: a card is `--radius-lg`. This was 18px, off-scale, and
           shared its value with `DashboardCard` — corrected together, per the
           owner's FU-811 decision (10px is the app's card radius at 41 sites,
           18px at 3). */
        border-radius: var(--radius-lg);
        box-shadow: var(--elevation-card);
    }
    .dora-hero-mascot {
        /* Same radius as `.dora-welcome-mascot` — one element type, one
           radius (D-017). Was 14px here and 10px there for the same thing. */
        border-radius: var(--radius-lg);
        background: var(--brand-primary-soft);
        /* R-002 / A3 carve-out — do NOT round this to `--space-1` (4px).
           The mascot artwork is not centred within its own bounding box, so
           the padding that makes it *look* centred in the square is optical,
           not spatial: it was tuned by hand to 2px in commit 12229346
           ("Properly centre the dora mascot on dashboard"). The chunk-6 scale
           sweep put it on the token and silently doubled it, pushing the glyph
           off centre again. A token here would be wrong for the same reason a
           token is wrong inside an SVG viewBox — the number isn't spacing. */
        padding: 2px;
        grid-area: 1 / 1;
    }
    .dora-hero-text {
        grid-area: 1 / 2;
        min-width: 0;
    }
    /* Owner 2026-09-04 — the greeting is brand voice, not a heading: one token
       step down (2xl → xl), the Cute Dino face, and the theme's accent colour.
       Same treatment `PageTitle` gives a page name, which is the "title" the
       owner pointed at.

       `--accent-ink`, not `--brand-primary`: R-069 — the brand tone is a *fill*
       and misses the contrast floor as text; `--accent-ink` is its ink-strength
       sibling and is what every other accent-coloured string on this page uses.

       The font stack is spelled out rather than reusing `DoraBrand` — that
       component renders the literal words "Dashy Dora" and centralises the
       *mark*, not the face. Wrapping a greeting in it would be borrowing a
       component for its stylesheet (R-001). If a third caller ever wants the
       face on arbitrary text, that's the moment for a token. */
    .dora-hero-greeting {
        font-family: 'Cute Dino', 'Nunito Variable', 'Nunito', sans-serif;
        font-size: var(--font-size-xl);
        font-weight: 600;
        line-height: 1.2;
        color: var(--accent-ink);
    }
    /* Dora's message of the day — the hero's main line since the "Dora says"
       band merged in. `--text-primary`, not the old `--text-secondary`: it is
       the sentence you actually read here now, not a caption under a heading. */
    .dora-hero-line {
        margin-top: var(--space-1);
        color: var(--text-primary);
        font-size: var(--font-size-md);
        line-height: 1.35;
    }
    /* The hint that used to be `.dora-welcome-hint` in the merged band, then a
       bare line of secondary text, and since 2026-09-08 an Obsidian-style
       callout (owner). Its own row, spanning columns 1-2 so it wraps before the
       Cards button rather than sliding under it.

       The 4px leading rule + tinted ground is `.dora-welcome`'s band, which is
       the app's existing callout shape — reused rather than invented. The tint
       is `--brand-primary-soft` and the rule `--brand-primary`, i.e. an
       informational callout in the theme's own voice; a `-soft` token is a
       background only, so the text on it stays on `--text-secondary` per A1's
       soft-token rule rather than taking the brand tone (R-069). */
    .dora-hero-hint {
        grid-area: 2 / 1 / 3 / 3;
        display: flex;
        align-items: flex-start;
        gap: var(--space-2);
        /* Asymmetric, exactly as `.dora-welcome` is: the wider inline-start pad
           sits behind the 4px rule so the text keeps an even optical inset. */
        padding: var(--space-2) var(--space-3) var(--space-2) var(--space-4);
        background: var(--brand-primary-soft);
        border-inline-start: 4px solid var(--brand-primary);
        /* D-017 — a box nested inside a card is `--radius-md`. Only the trailing
           corners: the leading edge is the rule, and rounding it would leave a
           sliver of card showing through the notch. */
        border-start-end-radius: var(--radius-md);
        border-end-end-radius: var(--radius-md);
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
        line-height: 1.4;
    }
    /* The icon takes the accent ink, not the fill tone — R-069, same rule the
       greeting follows. `margin-top` optically seats an 18px glyph against a
       `sm` first line rather than hanging above it. */
    .dora-hero-hint__icon {
        flex-shrink: 0;
        margin-top: 1px;
        color: var(--accent-ink);
    }
    .dora-hero-actions {
        grid-area: 1 / 3;
        display: flex;
        align-items: center;
        gap: var(--space-1);
    }

    /* ───── Cards ────────────────────────────────────────────────────── */
    .dora-cards {
        animation: dora-fade-up var(--motion-slow) var(--motion-ease-out) both;
    }
    /* The zone band header and the Cards-menu zone sub-header are gone with
       the zones (owner, 2026-09-04). Their §4.3 rationale — "the zones ARE the
       page's information architecture" — was true of seventeen cards and isn't
       of nine; the order the user chooses is the architecture now. */
    /* The card shell (`.dora-card`, head, icon, title, action, link, clickable
       + hover) lives in `components/dashboard/DashboardCard.vue`.

       FU-829 chunk 5 — the card BODY styles that used to sit here are gone too,
       now that every card is its own component:

         · shared by several cards  → `css/dashboardCards.scss`
           (`.dora-empty*`, `.dora-cook-*`, `.dora-stat-*`, `.dash-skel-line`)
         · used by exactly one card → that card's own scoped block (R-027)

       What remains below is the page's own chrome: the root, the hero, the
       onboarding skip-reminder band, and the grid's fade transition. The
       quick-action bar, the zone band labels and the "Dora says" welcome band
       were all removed on 2026-09-04. All of it on global tokens — chunk 6 retired
       the `--c-*` alias layer this block used to declare (FU-747). */

    /* The deal-row styles (`.dora-deal-*`) and their mobile reflow moved into
       `components/dashboard/PriceDropsCard.vue`, the only card that still uses
       them now that FU-819 cut "Best deals" (R-027). */

    /* ───── Dora welcome / message banner (D1) ───────────────────────────
       Inline, top-of-dashboard greeting that replaced the old fixed
       bottom-right tip bubble — keeps the warm "Dora says" treatment. The
       `--warn` modifier is the skip-reminder variant. */
    .dora-welcome {
        display: flex;
        align-items: center;
        gap: var(--space-3);
        /* Asymmetric on purpose: the wider inline-start pad sits behind the
           4px accent rule so the text keeps an even optical inset. */
        padding: var(--space-3) var(--space-3) var(--space-3) var(--space-4);
        background: var(--surface-component);
        border: 1px solid var(--border-default);
        border-left: 4px solid var(--brand-primary);
        border-radius: var(--radius-lg);
        box-shadow: var(--elevation-card);
    }
    .dora-welcome--warn {
        border-left-color: var(--semantic-warning);
        background: var(--semantic-warning-soft);
    }
    /* `.dora-welcome-mascot` went with the second mascot itself. The radius
       cross-reference on `.dora-hero-mascot` above is kept as written — it
       records *why* both were `--radius-lg`, which is still the reason the
       surviving one is. */
    .dora-welcome-body {
        min-width: 0;
        flex: 1;
    }
    .dora-welcome-line {
        font-size: var(--font-size-md);
        line-height: 1.35;
        color: var(--text-primary);
    }
    .dora-welcome-line strong {
        /* R-069: accent as *text* is `--accent-ink`, not the fill tone. */
        color: var(--accent-ink);
        font-weight: 700;
    }
    .dora-welcome--warn .dora-welcome-line strong {
        color: var(--semantic-warning);
    }
    .dora-welcome-hint {
        margin-top: var(--space-1);
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
    }
    .dora-welcome-actions {
        margin-top: var(--space-2);
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-2);
    }


    .fade-enter-active,
    .fade-leave-active {
        transition: opacity var(--motion-normal) var(--motion-ease), transform var(--motion-normal) var(--motion-ease);
    }
    .fade-enter-from,
    .fade-leave-to {
        opacity: 0;
        transform: translateY(8px);
    }

    @keyframes dora-fade-up {
        from {
            opacity: 0;
            transform: translateY(6px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* Respect the user's motion preference — no animation or transitions. */
    @media (prefers-reduced-motion: reduce) {
        /* The donut segments' motion is guarded inside the donut card; a
           scoped rule can't reach into a child component. */
        .dora-cards,
        .fade-enter-active,
        .fade-leave-active {
            animation: none !important;
            transition: none !important;
        }
    }

    @media (max-width: 600px) {
        /* The hero's old mobile rule wrapped the actions onto their own
           full-width row, which also pushed the text column under the mascot.
           The grid keeps all three side by side; what buys back the width is
           the Cards button going icon-only below `sm`, not a reflow. Only the
           column gap tightens. */
        .dora-hero {
            padding: var(--space-4);
            column-gap: var(--space-3);
        }
        /* Keeping the greeting beside the mascot at 375px only works if the
           mascot gives some width back — at 72px the text column is ~160px and
           "Good afternoon, Ben" wraps to three lines. 56px is the same square,
           read smaller; the 2px optical padding above is unaffected because it
           was tuned to the artwork's offset, not to the box. */
        .dora-hero-mascot {
            width: 56px;
            height: 56px;
            font-size: 56px;
        }
        .dora-dash {
            padding: var(--space-4) var(--space-4) calc(var(--space-12) * 2);
        }
        /* Phase 7 mobile pass. The card grid already stacks (cards are
           col-12 below sm). The quick-action bar's thumb-target rules went
           with the bar itself (owner, 2026-09-04). */
        /* The savings range toggle's mobile tap-height rule is gone with the
           hand-rolled chips — `BaseSegmented` carries its own sizing (FU-830).
           Whether its `dense size="sm"` clears the D-004 44px floor on touch is
           a real question, and it belongs to the chunk-6 tap-target pass rather
           than a patch here. */
        /* The alert summary chips' mobile padding moved into
           `AttentionCard.vue`. */
    }
</style>
