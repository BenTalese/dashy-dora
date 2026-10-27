<template>
    <!-- The card chrome is `RecipeInfoCard` (R-001) — shared with the version
         and additional-details panels so the three read as one family.

         Owner feedback 2026-09-08, two asks with one answer: the panel "just
         looks like a blob of text in a box", and there was no way to fix an
         ingredient the rollup couldn't count from here. So the figures are laid
         out as a headline plus a stat grid rather than run-on sentences, the
         coverage gets the same bar the cost breakdown wears, and each gap is
         named with the food search offered against the pantry item behind it.

         No `heading` — the expansion header this sits inside already says
         "Nutrition", and the basis is a pill on the figure it qualifies. -->
    <RecipeInfoCard :icon="ICONS.monitor_heart">
        <div class="rnut__head">
            <div v-if="nutrition.kcal !== null" class="rnut__figure">
                <span class="rnut__kcal">{{ Math.round(nutrition.kcal) }}</span>
                <span class="rnut__unit">kcal</span>
            </div>
            <div v-else class="rnut__figure rnut__figure--empty">
                Nothing to add up yet
            </div>
            <span class="rnut__basis">{{ basisLabel }}</span>
            <InfoTip label="Nutrition basis">
                Summed from the foods your ingredients are linked
                to, converted to grams. Link more ingredients to a
                food on their stock item to fill the gaps.
            </InfoTip>
        </div>

        <!-- One cell per figure the rollup actually knew. The macros and the
             rating's four nutrients sit in one grid rather than two rows: they
             are the same kind of fact at the same basis, and splitting them
             would imply a difference that isn't there. -->
        <dl v-if="nutrients.length" class="rnut__grid">
            <div v-for="row in nutrients" :key="row.label" class="rnut__cell">
                <dt class="rnut__k">{{ row.label }}</dt>
                <dd class="rnut__v">{{ row.value }}<span class="rnut__vu">{{ row.unit }}</span></dd>
            </div>
        </dl>

        <!-- Health Star Rating (owner ask 2026-08-27). Renders only
             when the install has it on; the server simply omits the
             field otherwise, so there is no second gate here. -->
        <div v-if="rating" class="dora-hsr">
            <div class="dora-hsr__row">
                <RecipeHealthStars :stars="rating.stars" qualifier="estimated" />
                <BaseButton
                    variant="subtle"
                    dense
                    :icon="ICONS.help_outline"
                    :label="breakdownOpen ? 'Hide working' : 'How this was scored'"
                    :aria-expanded="breakdownOpen"
                    @click="breakdownOpen = !breakdownOpen"
                />
            </div>
            <div class="text-caption dora-text-muted">{{ ratingCaption }}</div>

            <q-slide-transition>
                <div v-show="breakdownOpen" class="dora-hsr__working text-caption">
                    <!-- The point ledger, in the order the FSANZ
                         method computes it. A star count nobody can
                         interrogate is the one thing this feature
                         must not be. -->
                    <div class="dora-hsr__ledger">
                        <span
                            v-for="row in breakdown"
                            :key="row.label"
                            class="dora-hsr__cell"
                        >
                            <span class="dora-hsr__k">{{ row.label }}</span>
                            <span class="dora-hsr__v">{{ row.value }}</span>
                        </span>
                    </div>
                    <p class="dora-hsr__note">
                        Score {{ rating.score }}: {{ rating.baseline_points }} baseline
                        point{{ s(rating.baseline_points) }} less
                        {{ rating.baseline_points - rating.score }} for what the dish
                        has going for it. Lower scores earn more stars.
                    </p>
                    <p v-if="!rating.protein_counted" class="dora-hsr__note">
                        Protein didn't count towards this rating. The scheme only
                        credits protein on an energy-dense dish when at least 80%
                        of it is fruit, vegetables, nuts or legumes.
                    </p>
                    <p v-if="thinNutrients.length" class="dora-hsr__note">
                        Scored without a full picture:
                        {{ thinNutrients.join(', ') }}. A missing figure here scores
                        nothing, which flatters the rating rather than lowering it.
                    </p>
                    <p class="dora-hsr__note">
                        Health Star Rating, calculated the way FSANZ publishes it,
                        from the raw weight of the ingredients.
                    </p>
                </div>
            </q-slide-transition>
        </div>

        <!-- Nutri-Score, when that is the install's scheme. Never
             rendered alongside the block above — the server sends one
             or the other, never both. Deliberately a sibling rather
             than the same block parameterised: the two schemes weight
             different things and their explanations have to say
             different things, and collapsing them would produce copy
             that is vague about both. -->
        <div v-if="nutriScore" class="dora-hsr">
            <div class="dora-hsr__row">
                <RecipeNutriScore :grade="nutriScore.grade" qualifier="estimated" />
                <BaseButton
                    variant="subtle"
                    dense
                    :icon="ICONS.help_outline"
                    :label="nsBreakdownOpen ? 'Hide working' : 'How this was scored'"
                    :aria-expanded="nsBreakdownOpen"
                    @click="nsBreakdownOpen = !nsBreakdownOpen"
                />
            </div>
            <div class="text-caption dora-text-muted">{{ nutriScoreCaption }}</div>

            <q-slide-transition>
                <div v-show="nsBreakdownOpen" class="dora-hsr__working text-caption">
                    <div class="dora-hsr__ledger">
                        <span
                            v-for="row in nutriScoreBreakdown"
                            :key="row.label"
                            class="dora-hsr__cell"
                        >
                            <span class="dora-hsr__k">{{ row.label }}</span>
                            <span class="dora-hsr__v">{{ row.value }}</span>
                        </span>
                    </div>
                    <p class="dora-hsr__note">
                        Score {{ nutriScore.score }}:
                        {{ nutriScore.negative_points }} point{{
                            s(nutriScore.negative_points) }} against, less
                        {{ nutriScore.negative_points - nutriScore.score }} for what
                        the dish has going for it. Lower scores earn better grades.
                    </p>
                    <p v-if="!nutriScore.protein_counted" class="dora-hsr__note">
                        Protein didn't count towards this grade. Once a dish reaches
                        11 points against, the scheme stops crediting protein and
                        counts only fibre and produce.
                    </p>
                    <p v-if="thinNutrients.length" class="dora-hsr__note">
                        Scored without a full picture:
                        {{ thinNutrients.join(', ') }}. A missing figure here scores
                        nothing, which flatters the grade rather than lowering it.
                    </p>
                    <p class="dora-hsr__note">
                        Nutri-Score, calculated the way Santé publique France
                        publishes the 2023 algorithm, from the raw weight of the
                        ingredients.
                    </p>
                </div>
            </q-slide-transition>
        </div>

        <!-- The coverage line is always visible, even at full coverage: a
             number whose basis is invisible reads as complete whether it is or
             not. The bar is the cost breakdown's, deliberately — the two
             "how much of this could we work out?" statements in the recipe
             page should not be two different shapes. -->
        <div class="rnut__coverage">
            <div class="rnut__bar" role="img" :aria-label="coverageLine">
                <div class="rnut__barfill" :style="{ width: coveragePct + '%' }"></div>
            </div>
            <span class="rnut__cov">{{ coverageLine }}</span>
        </div>

        <!-- The gaps, named. Grouped by reason so eight unlinked rows read as
             one heading rather than eight sentences, and each row that can be
             fixed from here carries the button that fixes it. -->
        <template v-for="group in gapGroups" :key="group.reason">
            <div class="rnut__grouphead">{{ group.title }}</div>
            <ul class="rnut__gaps">
                <li v-for="(row, i) in group.rows" :key="`${row.stock_item_id}-${i}`">
                    <span class="rnut__gapname">{{ row.name ?? 'Unnamed ingredient' }}</span>
                    <BaseButton
                        v-if="group.canLink && row.stock_item_id"
                        variant="ghost"
                        dense
                        size="sm"
                        :icon="ICONS.search"
                        :label="group.actionLabel"
                        :loading="linkingId === row.stock_item_id"
                        :disable="linkingId !== null"
                        @click="onFindFood(row)"
                    />
                </li>
            </ul>
        </template>

        <NutritionFoodPicker
            v-model="pickerOpen"
            :item-name="pickerItemName"
            @picked="onFoodPicked"
        />
    </RecipeInfoCard>
</template>

<script lang="ts" setup>
    /**
     * FU-635 — complex-mode recipe nutrition.
     *
     * Renders the server's rollup verbatim: no summing, no unit maths, no
     * rounding decisions beyond display (R-003 / the state-ownership rule —
     * the figure and its coverage are domain facts the server owns).
     *
     * The coverage line never hides. The owner's call was "partials shown and
     * marked", and a per-serving figure built from 5 of 12 ingredients is a
     * different claim from one built from 12 — the reader has to be able to
     * tell them apart at a glance (P3 Honest).
     */
    import { computed, ref } from 'vue';

    import BaseButton from 'src/components/BaseButton.vue';
    import NutritionFoodPicker from 'src/components/stock/NutritionFoodPicker.vue';
    import RecipeHealthStars from 'src/components/recipes/RecipeHealthStars.vue';
    import RecipeInfoCard from 'src/components/recipes/RecipeInfoCard.vue';
    import RecipeNutriScore from 'src/components/recipes/RecipeNutriScore.vue';
    import type {
        RecipeNutrition, RecipeNutritionGap, RecipeNutritionGapIngredient,
    } from 'src/models/recipe';
    import { ICONS } from 'src/style/icons';
    import InfoTip from 'src/components/help/InfoTip.vue';
    import { useSettingsSave } from 'src/composables/useSettingsSave';
    import { useStockItemStore } from 'src/stores/stockItemStore';

    const props = defineProps<{ nutrition: RecipeNutrition }>();

    /** Fired once a food has been linked to one of the gap rows, so the page
     *  can re-fetch the recipe — the rollup that produced everything on this
     *  card is the server's, and it has just changed (R-003). */
    const emit = defineEmits<{ (e: 'linked'): void }>();

    const s = (count: number) => (count === 1 ? '' : 's');

    const basisLabel = computed(() =>
        props.nutrition.basis === 'serving' ? 'per serving' : 'whole recipe',
    );

    /** Every figure the rollup knew, in the order a label reads them. Nulls
     *  are dropped rather than shown as 0 — "nobody told us" and "there is
     *  none of it" are different claims (the same rule the server applies). */
    const NUTRIENTS: { key: keyof RecipeNutrition; label: string; unit: string }[] = [
        { key: 'protein_g', label: 'Protein', unit: 'g' },
        { key: 'carbs_g', label: 'Carbs', unit: 'g' },
        { key: 'fat_g', label: 'Fat', unit: 'g' },
        { key: 'saturated_fat_g', label: 'Sat fat', unit: 'g' },
        { key: 'sugars_g', label: 'Sugars', unit: 'g' },
        { key: 'fibre_g', label: 'Fibre', unit: 'g' },
        { key: 'sodium_mg', label: 'Sodium', unit: 'mg' },
    ];

    const nutrients = computed(() =>
        NUTRIENTS
            .map((row) => ({ ...row, value: props.nutrition[row.key] }))
            .filter((row): row is typeof row & { value: number } => typeof row.value === 'number'),
    );

    const coverageLine = computed(() => {
        const { counted_count: counted, total_count: total, basis } = props.nutrition;
        if (total === 0) return 'This recipe has no ingredients yet';
        if (counted === 0) return `From 0 of ${total} ingredient${s(total)}`;
        const suffix = basis === 'recipe' ? ' · add servings for a per-serving figure' : '';
        return `From ${counted} of ${total} ingredient${s(total)}${suffix}`;
    });

    const coveragePct = computed(() => {
        const { counted_count: counted, total_count: total } = props.nutrition;
        if (total <= 0) return 0;
        return Math.round((counted / total) * 100);
    });

    // ── The gaps, named ─────────────────────────────────────────────────
    /** Copy per gap reason, plus whether a food link is the fix. `canLink` is
     *  the two reasons that live on the *stock item* — the other three are
     *  fixed by editing the ingredient row, which is the page behind this
     *  drawer, so offering a search here would be pointing at the wrong thing.
     *  The ids themselves are the server's closed set. */
    const GAP_GROUPS: Record<RecipeNutritionGap, {
        title: string; canLink: boolean; actionLabel: string;
    }> = {
        not_linked: {
            title: 'Not linked to a pantry item',
            canLink: false,
            actionLabel: '',
        },
        no_food: {
            title: 'No food linked',
            canLink: true,
            actionLabel: 'Find a food',
        },
        no_data: {
            title: 'Linked food carries no calorie figure',
            canLink: true,
            actionLabel: 'Find another',
        },
        no_quantity: { title: 'No amount given', canLink: false, actionLabel: '' },
        no_conversion: {
            title: "Amount can't be converted to a weight",
            canLink: false,
            actionLabel: '',
        },
    };

    /** Reason order is this list's, not the server's dict order — it runs from
     *  "we know nothing about this row" to "we nearly had it". */
    const GAP_ORDER: RecipeNutritionGap[] = [
        'no_food', 'no_data', 'not_linked', 'no_quantity', 'no_conversion',
    ];

    const gapGroups = computed(() => {
        const rows = props.nutrition.uncounted_ingredients ?? [];
        return GAP_ORDER
            .map((reason) => ({
                reason,
                ...GAP_GROUPS[reason],
                rows: rows.filter((row) => row.reason === reason),
            }))
            .filter((group) => group.rows.length > 0);
    });

    // ── Linking a food from here ────────────────────────────────────────
    // The picker is the pantry page's, unchanged (R-001): the same search, the
    // same "nothing is saved until you tap a row" contract (P12 No-invent).
    // All this surface adds is the anchor — which pantry item the pick lands on.
    const stockItemStore = useStockItemStore();
    const { notifyError, notifySuccess } = useSettingsSave();

    const pickerOpen = ref(false);
    const pickerRow = ref<RecipeNutritionGapIngredient | null>(null);
    const linkingId = ref<string | null>(null);
    const pickerItemName = computed(() => pickerRow.value?.name ?? 'this ingredient');

    function onFindFood(row: RecipeNutritionGapIngredient) {
        pickerRow.value = row;
        pickerOpen.value = true;
    }

    async function onFoodPicked(foodId: string, foodName: string) {
        const stockItemId = pickerRow.value?.stock_item_id;
        if (!stockItemId) return;
        linkingId.value = stockItemId;
        try {
            await stockItemStore.updateStockItemAsync({
                stock_item_id: stockItemId,
                nutrition_food_id: foodId,
            });
            notifySuccess(`Linked ${pickerRow.value?.name ?? 'the ingredient'} to ${foodName}.`);
            emit('linked');
        } catch (err) {
            notifyError('Could not link that food.', err);
        } finally {
            linkingId.value = null;
        }
    }

    // ── Health Star Rating ──────────────────────────────────────────────
    const breakdownOpen = ref(false);
    const rating = computed(() => props.nutrition.health_star_rating);

    const ratingCaption = computed(() => {
        const value = rating.value;
        if (!value) return '';
        const fvnl = value.fvnl_percent;
        // The fvnl figure is the one input worth stating outright: it is what
        // separates two dishes with the same calories, and it is the number a
        // cook can actually act on.
        const produce = fvnl === null
            ? ''
            : ` · ${Math.round(fvnl)}% fruit, veg, nuts or legumes`;
        return `Health Star Rating (estimated)${produce}`;
    });

    /** The point ledger. Baseline points count against the recipe and
     *  modifying points count for it, so the signs are shown rather than left
     *  to the reader to infer from the label. */
    const breakdown = computed(() => {
        const value = rating.value;
        if (!value) return [];
        return [
            { label: 'Energy', value: `+${value.energy_points}` },
            { label: 'Sat fat', value: `+${value.saturated_fat_points}` },
            { label: 'Sugars', value: `+${value.total_sugars_points}` },
            { label: 'Sodium', value: `+${value.sodium_points}` },
            { label: 'Fruit & veg', value: `−${value.v_points}` },
            { label: 'Protein', value: `−${value.protein_points}` },
            { label: 'Fibre', value: `−${value.fibre_points}` },
        ];
    });

    // ── Nutri-Score ─────────────────────────────────────────────────────
    // Its own state and its own computeds rather than a shared "rating"
    // abstraction: the two schemes name different components (salt vs sodium,
    // fruit-veg-legumes vs fruit-veg-nuts-legumes) with different ceilings,
    // and the only thing a shared shape would buy is copy that is imprecise
    // about both.
    const nsBreakdownOpen = ref(false);
    const nutriScore = computed(() => props.nutrition.nutri_score);

    const nutriScoreCaption = computed(() => {
        const value = nutriScore.value;
        if (!value) return '';
        const fvl = value.fvl_percent;
        // Nuts are excluded from this figure where the Health Star Rating
        // includes them, so the wording has to differ from the caption above —
        // saying "nuts" here would misdescribe the number.
        const produce = fvl === null
            ? ''
            : ` · ${Math.round(fvl)}% fruit, veg or legumes`;
        return `Nutri-Score (estimated)${produce}`;
    });

    /** The point ledger. Negative points count against the recipe and positive
     *  ones count for it, so the signs are shown rather than left to the
     *  reader to infer from the label. */
    const nutriScoreBreakdown = computed(() => {
        const value = nutriScore.value;
        if (!value) return [];
        return [
            { label: 'Energy', value: `+${value.energy_points}` },
            { label: 'Sat fat', value: `+${value.saturated_fat_points}` },
            { label: 'Sugars', value: `+${value.total_sugars_points}` },
            { label: 'Salt', value: `+${value.salt_points}` },
            { label: 'Fruit & veg', value: `−${value.fvl_points}` },
            { label: 'Protein', value: `−${value.protein_points}` },
            { label: 'Fibre', value: `−${value.fibre_points}` },
        ];
    });

    // Which of the rating's four penalty nutrients were known for less than
    // most of the recipe's weight. Named individually rather than rolled into
    // one percentage because "we didn't know the sugar" and "we didn't know
    // the sodium" lead a cook to different conclusions.
    //
    // The threshold is a *display* choice — below this the figure is thin
    // enough to be worth mentioning — not the server's judge/don't-judge gate,
    // which is `is_reliable` and lives in the rollup (R-003).
    const THIN_COVERAGE = 0.9;
    const COVERAGE_LABELS: Record<string, string> = {
        kcal: 'energy',
        saturated_fat_g: 'saturated fat',
        sugars_g: 'sugars',
        sodium_mg: 'sodium',
    };

    const thinNutrients = computed(() => {
        const coverage = props.nutrition.nutrient_coverage ?? {};
        return Object.entries(COVERAGE_LABELS)
            .map(([key, label]) => ({ label, ratio: coverage[key] ?? 0 }))
            .filter((row) => row.ratio < THIN_COVERAGE)
            .map((row) => `${row.label} known for ${Math.round(row.ratio * 100)}% of it`);
    });
</script>

<style scoped>
    .rnut__head {
        display: flex;
        align-items: baseline;
        flex-wrap: wrap;
        gap: var(--space-2, 8px);
    }
    .rnut__figure { display: flex; align-items: baseline; gap: var(--space-1, 4px); }
    .rnut__kcal {
        font-size: 1.75rem;
        font-weight: 700;
        line-height: 1.1;
        font-variant-numeric: tabular-nums;
    }
    .rnut__unit { color: var(--text-muted); font-size: 0.875rem; }
    .rnut__figure--empty { color: var(--text-muted); font-size: 0.875rem; }
    /* The basis is a qualifier on the figure, not a heading — it sits on the
       number it describes so the two can't be read apart. */
    .rnut__basis {
        padding: 2px 8px;
        border-radius: var(--radius-pill, 999px);
        background: var(--surface-sunken);
        color: var(--text-secondary);
        font-size: calc(var(--font-size-xs) * 1rem);
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }

    /* auto-fit rather than a fixed column count: seven nutrients on a phone
       and three on a desktop both want the row filled, not padded out. */
    .rnut__grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(5.5rem, 1fr));
        gap: var(--space-2, 8px) var(--space-3, 12px);
        margin: var(--space-3, 12px) 0 0;
        padding: var(--space-3, 12px) 0 0;
        border-top: 1px solid var(--divider);
    }
    .rnut__cell { min-width: 0; }
    .rnut__k {
        font-size: calc(var(--font-size-xs) * 1rem);
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--text-muted);
    }
    .rnut__v {
        margin: 0;
        font-size: 1rem;
        font-weight: 700;
        font-variant-numeric: tabular-nums;
    }
    .rnut__vu {
        margin-left: 2px;
        font-size: 0.75rem;
        font-weight: 400;
        color: var(--text-muted);
    }

    .rnut__coverage {
        display: flex;
        align-items: center;
        gap: var(--space-3, 12px);
        margin-top: var(--space-3, 12px);
        padding-top: var(--space-3, 12px);
        border-top: 1px solid var(--divider);
    }
    .rnut__bar {
        flex: 1;
        height: 6px;
        border-radius: var(--radius-pill, 999px);
        background: var(--surface-sunken);
        overflow: hidden;
    }
    .rnut__barfill { height: 100%; background: var(--brand-primary); }
    .rnut__cov {
        font-size: 0.8125rem;
        color: var(--text-muted);
        white-space: nowrap;
    }

    .rnut__grouphead {
        margin-top: var(--space-3, 12px);
        font-size: calc(var(--font-size-xs) * 1rem);
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--text-muted);
    }
    .rnut__gaps {
        list-style: none;
        margin: var(--space-1, 4px) 0 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .rnut__gaps > li {
        display: flex;
        align-items: center;
        gap: var(--space-2, 8px);
        padding: var(--space-1, 4px) var(--space-3, 12px);
        border-radius: var(--radius-sm, 4px);
        background: var(--surface-sunken);
        font-size: 0.875rem;
        color: var(--text-primary);
        min-height: 36px;
    }
    .rnut__gapname { flex: 1; min-width: 0; }
    /* The action inside is a `BaseButton`, which lifts to the 44px floor on a
       touch device — the row has to make room for it rather than clip it. */
    @media (pointer: coarse) {
        .rnut__gaps > li { min-height: 52px; }
    }

    .dora-hsr {
        margin-top: var(--space-3, 12px);
        padding-top: var(--space-3, 12px);
        border-top: 1px solid var(--divider);
    }
    .dora-hsr__row {
        display: flex;
        align-items: center;
        gap: var(--space-2, 8px);
        flex-wrap: wrap;
    }
    .dora-hsr__working { margin-top: var(--space-2, 8px); }
    .dora-hsr__ledger {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(5.5rem, 1fr));
        gap: var(--space-1, 4px) var(--space-3, 12px);
    }
    .dora-hsr__cell {
        display: flex;
        flex-direction: column;
        min-width: 0;
    }
    .dora-hsr__k { color: var(--text-muted); }
    .dora-hsr__v {
        font-weight: 700;
        font-variant-numeric: tabular-nums;
    }
    .dora-hsr__note {
        margin: var(--space-2, 8px) 0 0;
        color: var(--text-muted);
        max-width: 62ch;
    }
</style>
