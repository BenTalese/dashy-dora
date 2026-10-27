<template>
    <DashboardCard :icon="ICONS.expiry" title="Use it up">
        <CardLoadError
            v-if="failed"
            line="I couldn't work out what needs using up."
            @retry="emit('retry')"
        />

        <template v-else-if="items.length > 0">
            <ul class="dora-cook-list">
                <li v-for="item in items" :key="item.stock_item_id" class="dora-cook-row">
                    <router-link class="dora-cook-name" :to="`/stock/${item.stock_item_id}`">
                        {{ item.name }}
                    </router-link>
                    <!-- D-014: the state is a word, not a colour. `is_expired`
                         does earn the negative token — it is the one state here
                         that is already a loss rather than a deadline. -->
                    <span
                        class="dora-cook-meta"
                        :class="{ 'dora-use-meta--gone': item.is_expired }"
                    >
                        {{ whenLabel(item) }}
                    </span>
                </li>
            </ul>

            <!-- The half that makes this a card rather than a restatement of
                 the expiry alert: what you can cook with the above, right now.
                 Absent when nothing in the cookbook uses any of it, which is a
                 real and common state — the list above still stands on its
                 own. -->
            <div v-if="recipes.length > 0" class="dora-use-recipes">
                <div class="dora-use-recipes__head">
                    <span>Recipes using these</span>
                    <!-- Owner 2026-09-08 — *"Add a 'see more' button inline with
                         the 'recipes using these' heading."* It lands on the
                         cookbook's own **Uses expiring ingredients** filter,
                         which already exists (`?expiring_within_days=14`
                         server-side) and simply was not reachable by link — so
                         this is a deep link, not a new filter. The card shows at
                         most three; the filter shows the rest, ranked and
                         badged, on the surface that owns recipes.

                         Not `dora-card-link`: that is the header-action look
                         this batch just deleted from every card. This is a
                         control inside the body beside the heading it belongs
                         to, which is the distinction the owner drew. -->
                    <BaseButton
                        variant="ghost"
                        dense
                        size="sm"
                        :icon-right="ICONS.east"
                        label="See more"
                        to="/cookbook?expiring=1"
                        aria-label="See more recipes that use your expiring items"
                    />
                </div>
                <router-link
                    v-for="recipe in recipes"
                    :key="recipe.recipe_id"
                    class="dora-use-recipe"
                    :to="`/cookbook/${recipe.recipe_id}`"
                >
                    <span class="dora-use-recipe__name">{{ recipe.name }}</span>
                    <span class="dora-use-recipe__uses">{{ usesLabel(recipe) }}</span>
                </router-link>
            </div>
        </template>

        <!-- R-014's inversion: an actionable card renders a *positive* empty
             state rather than vanishing, so a calm dashboard reads as
             reassuring instead of broken. -->
        <div v-else class="dora-empty dora-empty-ok">
            <q-icon :name="ICONS.check_circle" size="20px" class="q-mr-sm" />
            Nothing's about to go off. Good pantry.
        </div>
    </DashboardCard>
</template>

<script lang="ts" setup>
    /**
     * "Use it up" — near-expiry stock, and the recipes that would use it.
     *
     * One of the two cards that replaced "Needs your attention" and "Dora
     * suggests" (owner, 2026-09-04). The bar those two failed was *"I don't
     * think we need the overlap … these are all saying the exact same thing"*,
     * so the test for this one is that it says something the alerts bell
     * doesn't: the bell states an expiry, this answers what to do about it
     * tonight.
     *
     * Everything rendered here is server-computed (`/dashboard/use-it-up`):
     * the expiry window is the household's own setting, the days-remaining
     * arithmetic runs against the household's today (R-021), and the
     * recipe→item join is the server's. This file picks words and shapes
     * (R-003).
     */
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';
    import DashboardCard from 'src/components/dashboard/DashboardCard.vue';
    import CardLoadError from 'src/components/dashboard/CardLoadError.vue';
    import type {
        UseItUpItem,
        UseItUpRecipe,
    } from 'src/services/api/dashboardApiService';

    withDefaults(
        defineProps<{
            items: UseItUpItem[];
            recipes: UseItUpRecipe[];
            failed?: boolean;
        }>(),
        { failed: false },
    );

    const emit = defineEmits<{ (e: 'retry'): void }>();

    /**
     * The deadline in words. Deliberately not `formatRelativeDay` — that
     * formatter answers "which day is this" ("Tomorrow", "Sat 6 Sep"), and the
     * question on this card is "how long have I got", which is a different
     * sentence for the same date. An item four days out reads "4 days left",
     * not "Sat 6 Sep": the number is the urgency.
     */
    function whenLabel(item: UseItUpItem): string {
        const days = item.days_remaining;
        if (days < 0) return days === -1 ? 'expired yesterday' : `expired ${-days} days ago`;
        if (days === 0) return 'today';
        if (days === 1) return '1 day left';
        return `${days} days left`;
    }

    /**
     * "uses 2 expiring" — the count, not the names (owner, 2026-09-08: *"swap
     * the 'uses <ingredient name>' for 'uses # expiring'"*).
     *
     * This reverses a deliberate earlier call, and rightly. The original
     * reasoning was that "uses spinach and ricotta" is a *reason* to cook it
     * while a count is merely a statistic — true in isolation, but the names
     * are already printed in the items list three lines above. So the row was
     * repeating them, at a length that wrapped on a phone, to say something the
     * count says in two words: this recipe clears **more** of that list than the
     * one under it. Which is the actual question, because the rows are ranked on
     * exactly that number.
     *
     * `recipe.uses.length`, not a new server field: the array is already on the
     * wire and its length is not a domain rule — the server still decides which
     * items count as expiring, which ingredients are required, and how the rows
     * rank (R-003).
     */
    function usesLabel(recipe: UseItUpRecipe): string {
        return `uses ${recipe.uses.length} expiring`;
    }
</script>

<style scoped lang="scss">
    /* The row primitive (`.dora-cook-*`) and the empty states come from
       `css/dashboardCards.scss`, shared with Next to cook and Restock radar.
       These are this card's own. */

    /* An item already past its date is a loss, not a deadline — the one state
       on this card that earns the negative token (D-001). */
    .dora-use-meta--gone {
        color: var(--semantic-negative);
        font-weight: 600;
    }

    .dora-use-recipes {
        margin-top: var(--space-4);
        display: flex;
        flex-direction: column;
        gap: var(--space-1);
    }
    /* The heading and its See-more button share one line (owner: *"inline with
       the heading"*). `space-between` rather than an auto margin, so the button
       keeps its own hit area at the card's trailing edge at any width. */
    .dora-use-recipes__head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--space-2);
        font-size: var(--font-size-xs);
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-secondary);
        margin-bottom: var(--space-1);
    }
    /* The button carries its own type scale from `BaseButton`; the heading's
       uppercase + letter-spacing must not leak into it. */
    .dora-use-recipes__head :deep(.dora-btn) {
        text-transform: none;
        letter-spacing: normal;
        font-weight: 600;
    }
    .dora-use-recipe {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        gap: var(--space-2);
        padding: var(--space-2) var(--space-3);
        /* D-017 — a row nested in a card is a row: `--radius-md`. */
        border-radius: var(--radius-md);
        text-decoration: none;
        /* D-004 — a tap target on a touch row needs the 44px floor, and these
           are links, not buttons, so nothing else supplies it. */
        min-height: 44px;
    }
    .dora-use-recipe:hover {
        background: var(--surface-sunken);
    }
    .dora-use-recipe__name {
        color: var(--accent-ink);
        font-weight: 600;
    }
    /* Right-aligned (owner, 2026-09-08). Now that the label is a short fixed
       shape ("uses 2 expiring") rather than a run of names, the counts line up
       into a column you can read down — which is the point of ranking the rows
       on that number.
       `nowrap` on the row goes with it: the row allowed wrapping for the old
       long label, and a wrapped count would sit left-aligned on its own line,
       which is worse than truncating the name. */
    .dora-use-recipe {
        flex-wrap: nowrap;
    }
    .dora-use-recipe__name {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .dora-use-recipe__uses {
        margin-inline-start: auto;
        white-space: nowrap;
        font-size: var(--font-size-xs);
        color: var(--text-secondary);
    }
</style>
