<template>
    <DashboardCard :icon="ICONS.restaurant_menu" title="Next to cook">
        <!-- FU-976 (3) — the summary call that feeds this card failed. Its own
             error, not the empty state ("Nothing planned") and not the page's. -->
        <CardLoadError
            v-if="failed"
            line="I couldn't load your planned meals."
            @retry="emit('retry')"
        />
        <ul v-else-if="entries.length > 0" class="dora-cook-list">
            <li
                v-for="entry in entries"
                :key="`${entry.recipe_id}-${entry.scheduled_for}-${entry.slot}`"
                class="dora-cook-row dora-cook-row--meal"
                :class="{ 'dora-cook-row--with-badge': badgeLabel(entry) !== null }"
            >
                <router-link class="dora-cook-name" :to="`/cookbook/${entry.recipe_id}`">
                    {{ entry.recipe_name }}
                </router-link>
                <!-- The day, and only the day (owner, 2026-09-08). See the
                     block comment below for what came out and why. -->
                <span class="dora-cook-meta">{{ whenLabel(entry) }}</span>
                <q-badge
                    v-if="badgeLabel(entry) !== null"
                    :color="badgeColour(entry)"
                    :label="badgeLabel(entry) ?? undefined"
                    class="dora-cook-badge"
                />
                <!-- Owner 2026-09-08 — *"a proper cook button that is icon only
                     on mobile"*. `variant="primary"` rather than the ghost it
                     was: this is the row's verb and the only thing on the card
                     you press. Icon-only below `sm`, which is the rule the
                     hero's Cards button and Settings' sign-out already follow;
                     D-005 requires an icon-only control keep its accessible
                     name and gain a tooltip. -->
                <BaseButton
                    variant="primary"
                    dense
                    size="sm"
                    :icon="ICONS.chef_hat"
                    :label="$q.screen.lt.sm ? undefined : 'Cook'"
                    aria-label="Cook"
                    @click="emit('cook', entry)"
                >
                    <BaseTooltip v-if="$q.screen.lt.sm">Cook this</BaseTooltip>
                </BaseButton>
            </li>
        </ul>
        <!-- Two empty states, and telling them apart is the point. An empty
             list means "nothing planned" in a fresh household and "the freezer
             has the week covered" in a batch one — same absence, opposite
             news, and rendering the first at a batch household that has just
             cooked a fortnight of dinners would read as broken. -->
        <div v-else-if="batchEnabled && hasPlannedMeals" class="dora-empty dora-empty-ok">
            <q-icon :name="ICONS.check_circle" size="20px" class="q-mr-sm" />
            Nothing to cook. You have ready servings for what's planned.
        </div>
        <div v-else class="dora-empty">
            Nothing planned for the next week.
            <router-link class="dora-empty-cta" to="/meal-plans">Plan a meal →</router-link>
        </div>
    </DashboardCard>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    /**
     * The next few meals worth cooking, each flagged missing-N when it isn't
     * cookable (feedback L272, FU-298).
     *
     * **Which meals those are depends on how the household cooks** (owner,
     * 2026-09-04). The page selects; this renders. In a fresh household plan
     * day is cook day, so the selection is the next planned meals in order. In
     * a batch one the plan is not a cook schedule — one batch covers many
     * planned days — so the selection is the meals somebody actually has to
     * cook: the pool's shortfall, plus meals marked cook-fresh, which stand
     * outside the pool in both directions.
     *
     * **2026-09-08 — the row lost three of its five channels.** The owner:
     * *"Next to cook is too dense especially on mobile. Reduce it to recipe
     * name, the day (today/tomorrow/Wednesday/etc) only, missing ingredients
     * chip, a proper cook button that is icon only on mobile. This removes text
     * like 'dinner - serves 2 to cook <chef hat icon>'."* So:
     *
     *   · **the slot** came off the when-label. It read "Tomorrow dinner"; the
     *     day is what tells you whether this is urgent, and the slot is the one
     *     word on the row that changes nothing about what you'd do next.
     *   · **`serves N`** went. It was added on 09-05 so the row couldn't promise
     *     a number cook mode then contradicted — but the honest fix for that was
     *     making `cookPlannedMeal` open at the same figure, which it does. The
     *     number is stated on the screen that uses it.
     *   · **the pool state** (`to cook` / `fresh` / `already cooked`) went. It
     *     was already redundant by construction after the same 09-04 batch
     *     taught the *page* to filter on those flags: a batch household only
     *     ever sees rows that are `needs_cooking` or `cook_fresh`, so the label
     *     was the row's own premise printed back at it — the same reasoning that
     *     retired the "Ready" badge on 09-05. `useBatchEnabled` is still read,
     *     because the two empty states genuinely differ.
     *
     * What survives is the row's three real channels: what it is, when it is,
     * and whether you can actually cook it. The badge answers the third, and
     * since 09-05 only when the answer is "not yet".
     *
     * The header's "Meal plan →" link went in the same batch — *"Leaning towards
     * removing the links to open relevant pages on the dashboard cards. Doesn't
     * look so clean and you can just click the main menu buttons. Remove them
     * all I reckon."* The empty state's "Plan a meal →" stays: an empty card
     * with no way out is a dead end, not a clean one.
     *
     * Extracted from `DashboardPage.vue` (FU-829). The row anatomy comes from
     * `css/dashboardCards.scss`, shared with Restock radar.
     */
    import { ICONS } from 'src/style/icons';
    import { formatRelativeDay } from 'src/composables/useDateFormat';
    import BaseButton from 'src/components/BaseButton.vue';
    import DashboardCard from 'src/components/dashboard/DashboardCard.vue';
    import CardLoadError from 'src/components/dashboard/CardLoadError.vue';
    import { useBatchEnabled } from 'src/composables/useBatchEnabled';
    import type { UpcomingMealPlanEntry } from 'src/models/dashboard';

    withDefaults(
        defineProps<{
            /** Already selected by the page: chronological in a fresh
             *  household, the pool's shortfall (plus fresh-marked meals) in a
             *  batch one. See `nextToCook` in `DashboardPage.vue`.
             *
             *  Chronological now means what it says: the server sorts by day
             *  then by the household's own **slot sequence**, not by slot name,
             *  which is why a dessert no longer precedes a breakfast (owner,
             *  2026-09-08 — `get_dashboard_summary.py`). */
            entries: UpcomingMealPlanEntry[];
            /** Whether the week holds any planned meal at all — what separates
             *  "nothing planned" from "planned, and already cooked". */
            hasPlannedMeals?: boolean;
            /** The summary call failed — show `CardLoadError`, not an empty state. */
            failed?: boolean;
        }>(),
        { hasPlannedMeals: false, failed: false },
    );

    const emit = defineEmits<{
        (e: 'cook', entry: UpcomingMealPlanEntry): void;
        (e: 'retry'): void;
    }>();

    /** Read only for the two empty states now — the per-row pool label came off
     *  in the 09-08 density pass (see the block comment above). */
    const { batchEnabled } = useBatchEnabled();

    /** "Today" / "Tomorrow" / "Wednesday" — the day, nothing else. */
    function whenLabel(entry: UpcomingMealPlanEntry): string {
        return formatRelativeDay(entry.scheduled_for);
    }

    /**
     * IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — a null `missing_count` has **two**
     * flavours, and conflating them is why this reads the unlinked count first:
     * "empty recipe" (nothing to evaluate) and "unlinked" (ingredients exist but
     * aren't linked to stock items, so cookability is genuinely unknown). The
     * second is actionable — link them and the answer appears — so it gets its
     * own label rather than the ambiguous "No ingredients".
     */
    function badgeLabel(entry: UpcomingMealPlanEntry): string | null {
        if (entry.unlinked_ingredient_count > 0) {
            return `${entry.unlinked_ingredient_count} to link`;
        }
        if (entry.missing_count === null) return 'No ingredients';
        // Owner 2026-09-05 — no "Ready" badge. A row on this card is already a
        // meal somebody has to cook, so the cookable case is the expected one
        // and printing it costs a phone the horizontal space the name and the
        // Cook button need. The badge survives only for the states that change
        // what you do next: shop for N, or link N.
        if (entry.missing_count === 0) return null;
        return `Missing ${entry.missing_count}`;
    }

    function badgeColour(entry: UpcomingMealPlanEntry): string {
        // No `positive` arm — a cookable meal renders no badge at all now, so
        // the only colours left are "unknown" and "work to do".
        // `neutral-muted` (a real registered colour, see colours.scss) rather
        // than Quasar's `grey-6`, which R-002 forbids: "no signal yet / not
        // applicable" must be theme-aware, and D-001 reserves grey for exactly
        // this unknown state.
        if (entry.unlinked_ingredient_count > 0) return 'neutral-muted';
        if (entry.missing_count === null) return 'neutral-muted';
        return 'warning';
    }
</script>
