<template>
    <!-- Owner feedback 2026-08-27 — "the auto builder modal doesn't fit
         properly on mobile". `min-width: 560px` won against `max-width: 95vw`
         (a min-width is a floor, not a suggestion), so on a 375px phone the
         card was ~185px wider than the viewport and the review step's controls
         ran off the right edge. Same fix the ingredient picker already
         carries: no floor, and a width that can't exceed the viewport. -->
    <BaseDialog
        :model-value="modelValue"
        title="Build my week"
        closable
        card-style="min-width: 0; width: min(640px, 94vw)"
        @update:model-value="emit('update:modelValue', $event)"
    >
        <q-card-section class="q-pt-none">
            <!-- `alternative-labels` puts the step name under its dot rather
                 than beside it, which is what stops the three-step header
                 clipping on a phone. -->
            <q-stepper
                v-model="step"
                flat
                animated
                :alternative-labels="$q.screen.lt.sm"
                class="builder-stepper"
            >
                <!-- ── Step 1 — Setup ─────────────────────────────────────── -->
                <!-- Owner 2026-09-12: was "Guide". You are setting the week's
                     parameters here, not being guided through anything. -->
                <q-step :name="1" title="Setup" :icon="ICONS.dora_voice" :done="step > 1">
                    <div class="text-caption dora-text-muted q-mb-md">
                        Tell Dora what you're after and she'll build a plan. You can
                        tweak everything before it's saved.
                    </div>

                    <div class="builder-field">
                        <BaseToggleGroup
                            v-model="selectedDays"
                            label="Which days"
                            :options="dayToggleOptions"
                        />
                    </div>

                    <div class="builder-field">
                        <BaseToggleGroup
                            v-model="selectedSlots"
                            label="Which meals"
                            :options="slotToggleOptions"
                        />
                    </div>

                    <div v-if="selectedDays.length > 1" class="builder-field">
                        <q-checkbox
                            v-model="repeatSameDay"
                            dense
                            label="Same meals every day"
                        />
                        <div class="text-caption dora-text-muted q-mt-xs">
                            Builds one day's meals and repeats them across the days you picked.
                        </div>
                    </div>

                    <div class="builder-field">
                        <div class="builder-field__label">Emphasis</div>
                        <BaseSegmented v-model="emphasis" :options="emphasisOptions" dense />
                        <div class="text-caption dora-text-muted q-mt-xs">
                            {{ emphasisHint }}
                        </div>
                    </div>

                    <!-- Owner feedback 2026-09-03 — *"the auto builder should
                         have affordance for setting default servings for each
                         entry, and we default that to the how-many-people-we-
                         cook-for number from the settings page."* Every
                         proposal used to arrive at one serving each, so a
                         four-person household re-stepped every row in the
                         review step. The seed is the install's household
                         headcount (Settings → System → Cooking, server-owned
                         via `useCookingPolicy`); with none set it falls back to
                         1, which is what the builder always did. -->
                    <!-- Owner 2026-09-12: the stepper stretched to the dialog's
                         right edge on a phone — `NumberStepper` fills whatever
                         box it is given, and a `builder-field` div is
                         full-width. It sits in an inline-flex wrapper now, so
                         it is as wide as its own three controls at every
                         width. -->
                    <div class="builder-field">
                        <div class="builder-field__label">Servings per meal</div>
                        <div class="builder-stepper-wrap">
                            <NumberStepper
                                v-model="defaultServings"
                                :min="1"
                                :max="99"
                                variant="pill"
                                :icon="ICONS.people"
                                decrement-label="One fewer serving per meal"
                                increment-label="One more serving per meal"
                            />
                        </div>
                        <div class="text-caption dora-text-muted q-mt-xs">
                            {{ servingsHint }}
                        </div>
                    </div>

                    <!-- Owner 2026-09-05 — *"only affordance is in the auto
                         builder to keep under budget, but what's that based on?
                         Ingredients to buy or cost of the meal?"* It is the
                         cost of the meals: `apply_budget_cap` sums each chosen
                         recipe's full ingredient value, pantry or not, and
                         swaps the dearest for something cheaper until the week
                         fits what's left of the budget period. Owner kept that
                         basis and asked for it to be stated, which is what the
                         caption does — the control was answering a question it
                         never asked out loud.

                         Re-assessed 2026-09-12 against the alternative (count
                         only what you'd have to buy) and the owner kept the
                         meal-value basis, with the to-buy figure *shown*
                         instead: the review step now states both, so the
                         number the cap works to is no longer the only number
                         you can see. The cap itself stopped comparing whole
                         pots against the budget on the same date — it counts
                         the servings you're actually planning. -->
                    <div v-if="moneyEnabled" class="builder-field">
                        <q-toggle
                            v-model="budgetCap"
                            dense
                            label="Keep the week under budget"
                        />
                        <div class="text-caption dora-text-muted q-mt-xs">
                            Counts the full cost of the meals, including what's
                            already in your pantry, against what's left of this
                            period's budget.
                        </div>
                    </div>

                    <!-- Owner 2026-09-12 — *"put 'Dora will plan # meals' above
                         the build button, and put it in an info box"*. It was
                         a bare label at the bottom of a column of fields,
                         reading as the caption of whatever sat above it. It is
                         the summary of everything on this step and the last
                         thing you read before tapping Build, so it gets the
                         step's own info-box shape and sits directly above the
                         action row. -->
                    <div class="builder-hint builder-hint--summary">
                        <q-icon :name="ICONS.info" size="18px" class="builder-hint__icon" />
                        <div>{{ plannedCountHint }}</div>
                    </div>
                </q-step>

                <!-- ── Step 2 — Review ────────────────────────────────────── -->
                <q-step :name="2" title="Review" :icon="ICONS.restaurant" :done="step > 2">

                    <div v-if="showShortfallHint" class="builder-hint">
                        <q-icon :name="ICONS.info" size="18px" class="builder-hint__icon" />
                        <div>
                            Dora planned {{ lastBuildPlaced }} of the {{ lastBuildRequested }}
                            meals you picked. Each meal uses a different recipe, and there
                            weren’t enough to fill them all, so some days are still empty.
                            Add more recipes, choose fewer days or meals, or tick
                            <strong>Same meals every day</strong> to reuse recipes.
                        </div>
                    </div>

                    <div v-if="proposed.length === 0" class="dora-text-muted text-center q-py-md text-caption">
                        No meals yet. Reshuffle, or add your own below.
                    </div>

                    <template v-for="group in groupedByDay" :key="group.iso">
                        <div v-if="group.entries.length" class="builder-day">
                            <!-- Owner 2026-09-12 — a centred divider in the
                                 recipe page's section-heading voice (uppercase,
                                 tracked, secondary ink), with a rule running
                                 out to both edges. It was left-aligned bold
                                 text that read as another row. -->
                            <div class="builder-day__label">
                                <span>{{ group.label }}</span>
                            </div>
                            <!-- FU-852 / owner feedback 2026-09-03 — *"UI isn't
                                 fitting in the auto planner modal, UI is
                                 overlapping other UI… perhaps the recipe name
                                 could replace the swap button? Update: seems
                                 better on mobile, so an edit to make mobile
                                 better stuffed up desktop."* Exactly the
                                 diagnosis: the row stacked under
                                 `@media (max-width: 599px)`, which keys off the
                                 VIEWPORT while the row lives in a ~600px
                                 dialog, so a 1280px desktop kept the ~400px
                                 horizontal control cluster and left the name
                                 column whatever remained — a long name then
                                 painted straight through the selects.

                                 The row is stacked at EVERY width now: the name
                                 owns its own line, the controls own theirs. A
                                 dialog is not a viewport and there is no width
                                 at which cramming both onto one line was
                                 working. That also frees the swap button, per
                                 the owner's suggestion — the name IS the swap
                                 control (a button, so it is focusable and
                                 announced), which is one fewer 36px cell in the
                                 cluster that was overflowing.

                                 Owner 2026-09-12 — the row became a card and
                                 lost a line. The swap glyph beside the name is
                                 gone (the name is still the swap control, and
                                 the tooltip still says so); the servings
                                 stepper and the delete button moved up onto the
                                 name's line, which is the row's only spare
                                 horizontal space; and the two selects keep the
                                 line below. "Cook once" reads as "Cook day" —
                                 the marker names the day, not a restriction. -->
                            <div
                                v-for="entry in group.entries"
                                :key="entry._key"
                                class="builder-row"
                            >
                                <div class="builder-row__head">
                                    <button
                                        type="button"
                                        class="builder-row__name"
                                        @click="openSwap(entry)"
                                    >
                                        {{ entry.recipe_name }}
                                        <BaseTooltip>Swap for another recipe</BaseTooltip>
                                    </button>
                                    <NumberStepper
                                        v-model="entry.servings"
                                        :min="1"
                                        decrement-label="One fewer serving"
                                        increment-label="One more serving"
                                        class="builder-servings"
                                    >
                                        <BaseTooltip>Servings</BaseTooltip>
                                    </NumberStepper>
                                    <BaseButton
                                        variant="icon" dense
                                        :icon="ICONS.delete_outline"
                                        @click="removeEntry(entry)"
                                    >
                                        <BaseTooltip>Remove</BaseTooltip>
                                    </BaseButton>
                                </div>
                                <div class="builder-row__meta">
                                    <span
                                        v-if="cookMarker(entry)"
                                        class="builder-cook"
                                        :class="{ 'builder-cook--leftover': cookMarker(entry) === 'leftover' }"
                                    >
                                        <q-icon :name="ICONS.link" size="12px" />
                                        {{ cookMarker(entry) === 'cook' ? 'Cook day' : 'Leftovers' }}
                                    </span>
                                    <!-- Owner 2026-09-12 — a chip only when
                                         Dora has a reason of her own. A meal
                                         you added yourself said "Added", which
                                         you knew, and "You have everything" was
                                         restating the ingredient list below. -->
                                    <q-chip
                                        v-if="reasonLabel(entry.reason_chip)"
                                        dense square class="builder-reason"
                                    >
                                        {{ reasonLabel(entry.reason_chip) }}
                                    </q-chip>
                                    <!-- The dollar figure is null unless the
                                         install has money on — the server
                                         stopped sending it otherwise (R-058),
                                         so this is no longer a render gate over
                                         data that arrived anyway.
                                         `moneyEnabled` stays as the belt to
                                         that braces. -->
                                    <span
                                        v-if="entry.estimated_cost != null && moneyEnabled"
                                        class="dora-text-muted text-caption"
                                    >
                                        {{ money(entry.estimated_cost) }}
                                    </span>
                                </div>
                                <div class="builder-row__controls">
                                    <q-select
                                        v-if="dayOptions.length > 1"
                                        v-model="entry.scheduled_for"
                                        outlined dense options-dense emit-value map-options
                                        class="builder-day-select"
                                        :options="dayOptions"
                                    >
                                        <BaseTooltip>Move to another day</BaseTooltip>
                                    </q-select>
                                    <q-select
                                        v-model="entry.slot"
                                        outlined dense options-dense
                                        class="builder-slot-select"
                                        :options="slotNames"
                                    >
                                        <BaseTooltip>Which meal slot</BaseTooltip>
                                    </q-select>
                                </div>
                            </div>
                        </div>
                    </template>

                    <!-- Owner 2026-09-12 — the meal count went (the list is
                         right there, and the Setup step already said how many
                         it would plan), and Reshuffle came down here to sit
                         opposite "Add a meal": both are "change what's in this
                         proposal", so they belong on one row rather than at
                         opposite ends of the step. -->
                    <div class="row items-center q-mt-sm">
                        <BaseButton
                            variant="secondary" dense
                            :icon="ICONS.add"
                            label="Add a meal"
                            @click="openAdd"
                        />
                        <q-space />
                        <BaseButton
                            variant="ghost" dense
                            :icon="ICONS.refresh"
                            label="Reshuffle"
                            :loading="generatingProposal"
                            @click="generate"
                        />
                    </div>

                    <!-- What you'll need (aggregate ingredient demand) -->
                    <q-separator class="q-my-md" />
                    <div class="text-subtitle2">What you'll need</div>
                    <div v-if="previewLoading" class="text-caption dora-text-muted">Calculating…</div>
                    <template v-else>
                        <!-- Was "N to buy · M in stock", then just "N to buy".
                             Owner 2026-09-12 — *"we don't necessarily need to
                             buy low items"*, so the two bands are counted
                             separately rather than summed into a shopping
                             figure that overstates the trip. And the two
                             numbers that actually decide whether this week is
                             affordable are here now: what the low/out items
                             would cost, and what the meals are worth. Both are
                             server-priced (R-003 — the same ladder the recipe
                             and cookbook costs come from) and absent entirely
                             when money is off. -->
                        <div class="builder-need">
                            <span class="builder-need__bands">
                                {{ previewLowCount }} low · {{ previewOutCount }} out
                            </span>
                            <template v-if="moneyEnabled">
                                <span v-if="previewToBuyCost !== null" class="builder-need__figure">
                                    {{ money(previewToBuyCost) }} to buy
                                </span>
                                <span v-if="previewMealsCost !== null" class="builder-need__figure">
                                    {{ money(previewMealsCost) }} of meals
                                </span>
                            </template>
                        </div>
                        <div v-if="previewUnlinked.length" class="builder-hint">
                            <q-icon :name="ICONS.info" size="18px" class="builder-hint__icon" />
                            <div>
                                {{ previewUnlinked.length }}
                                ingredient{{ previewUnlinked.length === 1 ? '' : 's' }}
                                in these recipes
                                {{ previewUnlinked.length === 1 ? "isn't" : "aren't" }}
                                linked to your pantry, so
                                {{ previewUnlinked.length === 1 ? 'it' : 'they' }}
                                can't go on a shopping list.
                            </div>
                        </div>
                        <!-- FU-803 / owner feedback 2026-09-03 — *"'What you'll
                             need' is inconsistently styled with the new right
                             rail styling."* It was the shape `MealPlanIngredientRow`
                             was extracted to replace: a `q-item` with a
                             saturated status chip on the right, in colours the
                             two rail lists stopped using on 2026-09-01. Same
                             data, same question, so the same row (R-001) — the
                             level reads as the app's standard left-hand dot,
                             and the quantity is the caption.
                             This was the last consumer of the
                             `stockStatusLabel` / `stockStatusColour` pair here,
                             so the builder no longer reaches for them. -->
                        <div class="builder-list">
                            <MealPlanIngredientRow
                                v-for="ing in previewIngredients"
                                :key="ing.stock_item_id"
                                :ingredient="ing"
                                :show-cart="false"
                            />
                            <div
                                v-if="previewIngredients.length === 0"
                                class="dora-text-muted text-center text-caption q-py-sm"
                            >
                                These meals don't list any ingredients.
                            </div>
                        </div>
                    </template>
                </q-step>

                <!-- ── Step 3 — Done ──────────────────────────────────────── -->
                <q-step :name="3" title="Done" :icon="ICONS.check">
                    <div v-if="!doneState">
                        <div class="text-subtitle2">
                            Ready to save {{ proposed.length }} meal{{ proposed.length === 1 ? '' : 's' }}.
                        </div>
                        <div class="text-caption dora-text-muted q-mt-xs">
                            They'll be added to {{ targetLabel }}.
                            You can generate the shopping list straight after.
                        </div>
                    </div>
                    <div v-else class="column q-gutter-sm items-start">
                        <div class="text-subtitle2">All set: {{ proposed.length }} meal(s) planned.</div>
                        <!-- Owner feedback 2026-08-27 — hands off to the same
                             picker the planner and the recipe page use, rather
                             than sweeping the week into a new list unseen. -->
                        <div class="row q-gutter-sm builder-done-actions">
                            <BaseButton
                                :icon="ICONS.add_shopping_cart"
                                label="Add to a shopping list"
                                @click="onAddToList"
                            />
                            <BaseButton variant="secondary" :icon="ICONS.print" label="Print this week" @click="printWeek" />
                        </div>
                    </div>
                </q-step>
            </q-stepper>
        </q-card-section>

        <template #actions>
            <BaseButton v-if="!doneState" variant="ghost" label="Cancel" v-close-popup />
            <q-space />
            <BaseButton v-if="step > 1 && !doneState" variant="ghost" label="Back" @click="step = step - 1" />
            <!-- "I'll pick myself" was removed 2026-09-03 (owner: *"I don't see
                 the point of the 'pick myself' pathway in the auto builder.
                 Remove?"*). It jumped to an empty review step, which is a
                 worse way to hand-pick meals than the thing the user closed to
                 get here: the planner's own rail, where you arm a slot and
                 click a recipe. The escape it offered survives inside the
                 review step as "Add a meal", which is where you actually want
                 it — beside a proposal you are already editing. -->
            <BaseButton
                v-if="step === 1"
                :icon="ICONS.dora_voice"
                label="Build my week"
                :loading="generatingProposal"
                :disable="!canGenerate"
                @click="generate"
            />
            <BaseButton
                v-if="step === 2"
                label="Next"
                :disable="proposed.length === 0"
                @click="step = 3"
            />
            <BaseButton
                v-if="step === 3 && !doneState"
                label="Save plan"
                :loading="building"
                :disable="proposed.length === 0"
                @click="onBuild"
            />
            <BaseButton v-if="doneState" label="Done" v-close-popup />
        </template>
    </BaseDialog>

    <!-- Add / swap recipe picker (click-add) ─────────────────────────────── -->
    <BaseDialog
        v-model="pickerOpen"
        :title="pickerMode === 'swap' ? 'Swap this meal' : 'Add a meal'"
        closable
        card-style="min-width: 0; width: min(460px, 92vw)"
    >
        <q-card-section class="q-pt-none">
            <div class="builder-picker">
                <MealPlanRecipePicker
                    v-model:recipe-search="recipeSearch"
                    :recipes="recipes"
                    :focused-target="null"
                    :format-date="formatDate"
                    @recipe-pick="onPickRecipe"
                />
            </div>
        </q-card-section>
    </BaseDialog>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';
    import NumberStepper from 'src/components/NumberStepper.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseSegmented from 'src/components/BaseSegmented.vue';
    import BaseToggleGroup, { type ToggleOption } from 'src/components/BaseToggleGroup.vue';
    import MealPlanIngredientRow from 'src/components/MealPlanIngredientRow.vue';
    import MealPlanRecipePicker from 'src/components/MealPlanRecipePicker.vue';
    import { useCookingPolicy } from 'src/composables/useCookingPolicy';
    import { formatMoney } from 'src/composables/useMoney';
    import type {
        AutoBuildEmphasis, AutoBuildReason, MealPlanIngredient, ProposedEntry,
        UnlinkedIngredient,
    } from 'src/models/mealPlan';
    import type { MealPlanEntryCommand } from 'src/services/api/mealPlanApiService';
    import type { Recipe } from 'src/models/recipe';
    import MealPlanApiService from 'src/services/api/mealPlanApiService';
    import { useQuasar } from 'quasar';
    import { computed, ref, watch } from 'vue';

    const props = defineProps<{
        modelValue: boolean;
        recipes: Recipe[];
        /** Household meal-slot vocabulary (ordered). */
        slotNames: string[];
        /** Days of the focused week (`{ label, iso }`). */
        weekDays: { label: string; iso: string }[];
        currentDayIso: string;
        isPastDay: (iso: string) => boolean;
        formatDate: (iso: string) => string;
        moneyEnabled: boolean;
        /** Persists the (edited) proposal onto the focused week. */
        buildPlan: (entries: MealPlanEntryCommand[]) => Promise<void>;
        /** Generates the shopping list; scoped to `recipeIds` when given. */
        /** Opens the planner's shared add-to-list picker, seeded with the
         *  saved week's aggregated demand. */
        openAddToList: () => void;
        printWeek: () => void;
    }>();
    const emit = defineEmits<{ (e: 'update:modelValue', value: boolean): void }>();

    const api = new MealPlanApiService();
    const $q = useQuasar();
    const { householdHeadcount } = useCookingPolicy();

    // ── Local editable copy of a proposed entry (adds a stable render key) ──
    type DraftEntry = ProposedEntry & { _key: string };

    const step = ref(1);
    const proposed = ref<DraftEntry[]>([]);
    const generatingProposal = ref(false);
    const building = ref(false);
    const doneState = ref(false);
    const previewIngredients = ref<MealPlanIngredient[]>([]);
    // FU-505 — ingredients with no linked pantry item can't become list
    // lines. The aggregate reports them now (2026-08-27) so the review
    // step can say so before you commit to the week.
    const previewUnlinked = ref<UnlinkedIngredient[]>([]);
    const previewLoading = ref(false);
    const previewLowCount = ref(0);
    const previewOutCount = ref(0);
    const previewToBuyCost = ref<number | null>(null);
    const previewMealsCost = ref<number | null>(null);

    // FU-611 — the ranker only ever picks *distinct* recipes, so a day×slot
    // grid larger than the cookbook fills days in order and then stops, leaving
    // later days silently blank (the review list just omits empty days). Capture
    // what the last build asked for vs. what it could place so the review step
    // can explain the gap. Both 0 for a manual ("I'll pick myself") start.
    const lastBuildRequested = ref(0);
    const lastBuildPlaced = ref(0);
    // Only surface the hint when the *build* genuinely fell short, and keep it up
    // only until the user fills the missing cells by hand — so it never fires
    // just because someone deleted a meal from an otherwise-full plan. Scoped to
    // the non-repeat case (repeat-same-day is the mitigation we point them at).
    const showShortfallHint = computed(() =>
        !repeatSameDay.value
        && lastBuildRequested.value > 0
        && lastBuildPlaced.value < lastBuildRequested.value
        && proposed.value.length < lastBuildRequested.value,
    );

    // ── Guidance inputs ─────────────────────────────────────────────────────
    // Two independent toggle sets — the days to plan and the meal slots to fill
    // — whose cross-product is the plan (one meal per day × slot). There is no
    // separate meal-count control: the toggles *are* the count.
    const selectedDays = ref<string[]>([]);
    const selectedSlots = ref<string[]>([]);
    const repeatSameDay = ref(false);
    const emphasis = ref<AutoBuildEmphasis>('use_up_stock');
    const budgetCap = ref(false);
    /** Servings every proposed meal arrives at. Seeded from the household
     *  headcount on each open (see the reset watcher). */
    const defaultServings = ref(1);

    const emphasisOptions = [
        { label: 'Use up stock', value: 'use_up_stock' as AutoBuildEmphasis },
        { label: 'Variety', value: 'variety' as AutoBuildEmphasis },
        { label: 'Favourites', value: 'favourites' as AutoBuildEmphasis },
        { label: 'Surprise me', value: 'surprise' as AutoBuildEmphasis },
    ];
    const emphasisHints: Record<AutoBuildEmphasis, string> = {
        use_up_stock: 'Leans on meals you can cook now and stock that’s expiring soon.',
        variety: 'Spreads cuisines and picks things you haven’t had in a while.',
        favourites: 'Favourites and meals you cook often.',
        surprise: 'A mixed bag, mostly things you haven’t had lately.',
    };
    const emphasisHint = computed(() => emphasisHints[emphasis.value]);

    // Owner 2026-09-12 — the headcount sentence went. The number is already in
    // the stepper beside it, and it was reciting a setting back at the person
    // who set it; what they need to know is that it isn't final.
    const servingsHint = computed(() => (
        householdHeadcount.value === null
            ? 'Set how many people you cook for in Settings to seed this automatically.'
            : 'You can adjust servings in the next step.'
    ));

    const upcomingDays = computed(() => props.weekDays.filter((d) => !props.isPastDay(d.iso)));
    // All seven weekdays always render in the same positions so the row never
    // reflows mid-week; days already gone are inert with an explaining tooltip.
    const dayToggleOptions = computed<ToggleOption[]>(() =>
        props.weekDays.map((d) => {
            const past = props.isPastDay(d.iso);
            return {
                label: d.label,
                value: d.iso,
                caption: props.formatDate(d.iso),
                ...(past ? { disable: true, tooltip: 'That day has already been and gone.' } : {}),
            };
        }),
    );
    const slotToggleOptions = computed<ToggleOption[]>(
        () => props.slotNames.map((s) => ({ label: s, value: s })),
    );
    // The review step still lets the user move a meal to another day, but only
    // to a day that can actually hold one.
    const dayOptions = computed(() =>
        upcomingDays.value.map((d) => ({ label: `${d.label}, ${props.formatDate(d.iso)}`, value: d.iso })),
    );

    const canGenerate = computed(
        () => selectedDays.value.length > 0 && selectedSlots.value.length > 0,
    );
    // One meal per cell either way — "same meals every day" changes *which*
    // recipes land, not how many.
    const plannedMealCount = computed(
        () => selectedDays.value.length * selectedSlots.value.length,
    );
    const plannedCountHint = computed(() => {
        if (selectedDays.value.length === 0) return 'Pick at least one day.';
        if (selectedSlots.value.length === 0) return 'Pick at least one meal.';
        const n = plannedMealCount.value;
        return `Dora will plan ${n} meal${n === 1 ? '' : 's'}.`;
    });

    // Every household slot starts selected; the vocabulary is the household's
    // own, so the builder never guesses which names are "main meals" (R-003).
    const defaultSlots = computed<string[]>(() => [...props.slotNames]);

    /** Where the Done step says the meals are landing. */
    const targetLabel = computed(() => {
        const days = [...new Set(proposed.value.map((e) => e.scheduled_for))].sort();
        if (days.length !== 1) return 'the current week';
        const iso = days[0]!;
        const day = props.weekDays.find((d) => d.iso === iso);
        return day ? `${day.label}, ${props.formatDate(iso)}` : props.formatDate(iso);
    });

    // ── Reason chips ────────────────────────────────────────────────────────
    // Owner 2026-09-12 — two of these stopped earning their row. `picked` said
    // "Added" on a meal the user had just added themselves, and `cookable_now`
    // said "You have everything", which the ingredient list below the rows
    // answers properly for the whole week. An empty label renders no chip.
    const REASON_LABELS: Record<AutoBuildReason, string> = {
        uses_expiring: 'Uses expiring stock',
        cookable_now: '',
        favourite: 'Favourite',
        not_made_recently: 'Haven’t had lately',
        variety: 'Adds variety',
        budget_friendly: 'Budget-friendly',
        picked: '',
    };
    function reasonLabel(r: AutoBuildReason): string {
        return REASON_LABELS[r] ?? '';
    }

    // A cookability marker lived on these rows for a few hours on 2026-09-12
    // and was cut the same day (owner: *"I think it's just noise in the
    // builder"*). It belongs on the planner's own cards, where you are looking
    // at a committed week; here the "What you'll need" list below already
    // aggregates exactly what the whole proposal is short of.

    // ── The add/swap picker's search ────────────────────────────────────────
    // The tray builder this used to call was retired on 2026-08-30 (Unit 2 of
    // BRIEF_MEAL_PLANNER_RAIL_AND_SHELL): the picker now owns its own filter
    // chips, so the wizard gets the same five-chip model as the rail without
    // passing anything. Its checkboxes still work — the chips narrow the list,
    // the checkboxes select within it, and because exactly one filter is active
    // at a time a recipe can no longer render twice (which is what FU-578 #47's
    // dedupe existed to prevent; see `helpers/recipeRailFilters.ts`).
    const recipeSearch = ref('');

    // ── Ingredient preview (aggregate demand) ───────────────────────────────
    // The bands and both figures are read off the envelope rather than counted
    // here: which items need buying is a read of the stock levels behind the
    // aggregate, and a price is the server's to quote (R-003). The client used
    // to count the to-buy rows itself through `useStockStatus`.
    // Money renders through the formatting authority (R-003 / D-006 /
    // FU-043) — this was the one hand-rolled `$x.xx` left (finalisation 20-R5).
    const money = formatMoney;
    async function refreshPreview() {
        if (proposed.value.length === 0) {
            previewIngredients.value = [];
            previewUnlinked.value = [];
            previewLowCount.value = 0;
            previewOutCount.value = 0;
            previewToBuyCost.value = null;
            previewMealsCost.value = null;
            return;
        }
        previewLoading.value = true;
        try {
            const payload = await api.previewIngredientsAsync(
                proposed.value.map((e) => ({ recipe_id: e.recipe_id, servings: e.servings })),
            );
            previewIngredients.value = payload.items;
            previewUnlinked.value = payload.unlinked;
            previewLowCount.value = payload.low_count;
            previewOutCount.value = payload.out_count;
            previewToBuyCost.value = payload.to_buy_cost;
            previewMealsCost.value = payload.meals_cost;
        } finally {
            previewLoading.value = false;
        }
    }
    // Recompute the buy list whenever the reviewed set changes (recipe or
    // servings), but only while the review step is visible.
    watch(
        () => proposed.value.map((e) => `${e.recipe_id}:${e.servings}`).join(','),
        () => { if (step.value === 2) void refreshPreview(); },
    );

    // ── Grouping for the review list ────────────────────────────────────────
    const groupedByDay = computed(() =>
        props.weekDays.map((d) => ({
            iso: d.iso,
            label: `${d.label} · ${props.formatDate(d.iso)}`,
            entries: proposed.value.filter((e) => e.scheduled_for === d.iso),
        })),
    );

    let keySeq = 0;
    function toDraft(e: ProposedEntry): DraftEntry {
        keySeq += 1;
        return { ...e, _key: `d${keySeq}` };
    }

    // ── Generate (server auto-build) ────────────────────────────────────────
    async function generate() {
        if (!canGenerate.value) return;
        generatingProposal.value = true;
        try {
            const res = await api.autoBuildAsync({
                days: [...selectedDays.value],
                emphasis: emphasis.value,
                slot_names: [...selectedSlots.value],
                repeat_same_day: repeatSameDay.value,
                budget_cap: budgetCap.value,
                default_servings: defaultServings.value,
            });
            proposed.value = res.entries.map(toDraft);
            // Cells the toggles asked for vs. what the ranker could place (FU-611).
            lastBuildRequested.value = res.days_used.length * res.slots_used.length;
            lastBuildPlaced.value = res.entries.length;
            step.value = 2;
            await refreshPreview();
        } catch {
            // Stay on the Guide step; the axios layer already normalised the
            // error — surface a friendly toast rather than crashing the dialog.
            $q.notify({
                type: 'negative',
                message: "Couldn't build a plan. Try again.",
            });
        } finally {
            generatingProposal.value = false;
        }
    }

    // ── Review-step editing ─────────────────────────────────────────────────
    function removeEntry(entry: DraftEntry) {
        proposed.value = proposed.value.filter((e) => e._key !== entry._key);
    }

    const pickerOpen = ref(false);
    const pickerMode = ref<'add' | 'swap'>('add');
    const swapTargetKey = ref<string | null>(null);

    function openAdd() {
        pickerMode.value = 'add';
        swapTargetKey.value = null;
        recipeSearch.value = '';
        pickerOpen.value = true;
    }
    function openSwap(entry: DraftEntry) {
        pickerMode.value = 'swap';
        swapTargetKey.value = entry._key;
        recipeSearch.value = '';
        pickerOpen.value = true;
    }

    /** Chosen day with the fewest meals so a manual add spreads too. Falls back
     *  to any upcoming day when the user skipped the toggles ("I'll pick
     *  myself" jumps straight to the review step). */
    function leastLoadedDay(): string {
        const days = selectedDays.value.length
            ? selectedDays.value
            : upcomingDays.value.map((d) => d.iso);
        if (!days.length) return props.currentDayIso;
        const load = (iso: string) => proposed.value.filter((e) => e.scheduled_for === iso).length;
        return days.reduce((best, iso) => (load(iso) < load(best) ? iso : best), days[0]!);
    }
    function slotFor(recipe: Recipe): string {
        const pool = selectedSlots.value.length ? selectedSlots.value : props.slotNames;
        if (recipe.time_of_day && pool.includes(recipe.time_of_day)) return recipe.time_of_day;
        // A household with no slots has nowhere to plan; the server's
        // vocabulary check names the problem.
        return pool[0] ?? '';
    }

    function onPickRecipe(recipeId: string) {
        const recipe = props.recipes.find((r) => r.recipe_id === recipeId);
        if (!recipe) return;
        if (pickerMode.value === 'swap' && swapTargetKey.value) {
            // Swapping a recipe breaks its cook batch's one-recipe rule — unlink it.
            proposed.value = proposed.value.map((e) =>
                e._key === swapTargetKey.value
                    ? { ...e, recipe_id: recipe.recipe_id, recipe_name: recipe.name,
                        reason_chip: 'picked', cookable: recipe.cookable,
                        missing_stock_item_names: [], estimated_cost: null, cook_key: null }
                    : e,
            );
        } else {
            proposed.value = [...proposed.value, toDraft({
                recipe_id: recipe.recipe_id,
                recipe_name: recipe.name,
                scheduled_for: leastLoadedDay(),
                slot: slotFor(recipe),
                servings: defaultServings.value,
                reason_chip: 'picked',
                cookable: recipe.cookable,
                missing_stock_item_names: [],
                estimated_cost: null,
                cook_key: null,
            })];
        }
        pickerOpen.value = false;
    }

    // PROPOSAL_MEAL_PLANS_PART_2 §9 — a proposed cook batch only survives to the
    // commit if it's still a valid group after any review-step edits: >=2 rows,
    // one recipe, one slot, distinct days. Otherwise the entry commits standalone
    // (the server would reject a malformed group). Also powers the review marker.
    function validCookKey(entry: DraftEntry): string | null {
        if (!entry.cook_key) return null;
        const group = proposed.value.filter((e) => e.cook_key === entry.cook_key);
        if (group.length < 2) return null;
        const recipes = new Set(group.map((e) => e.recipe_id));
        const slots = new Set(group.map((e) => e.slot));
        const days = group.map((e) => e.scheduled_for);
        if (recipes.size > 1 || slots.size > 1 || new Set(days).size !== days.length) return null;
        return entry.cook_key;
    }
    // Cook-day = the earliest day of a (valid) batch; that row shows "Cook", the
    // rest "Leftovers".
    function cookMarker(entry: DraftEntry): 'cook' | 'leftover' | null {
        const key = validCookKey(entry);
        if (!key) return null;
        const days = proposed.value.filter((e) => e.cook_key === key).map((e) => e.scheduled_for);
        return entry.scheduled_for === days.reduce((a, b) => (a < b ? a : b)) ? 'cook' : 'leftover';
    }

    // ── Commit + follow-ups ─────────────────────────────────────────────────
    async function onBuild() {
        building.value = true;
        try {
            await props.buildPlan(proposed.value.map((e) => ({
                recipe_id: e.recipe_id,
                scheduled_for: e.scheduled_for,
                servings: e.servings,
                slot: e.slot,
                ...(validCookKey(e) ? { cook_key: validCookKey(e) as string } : {}),
            })));
            doneState.value = true;
        } finally {
            building.value = false;
        }
    }

    // Closes the builder first: the picker is the planner page's dialog, and
    // stacking two modals on a phone leaves you tapping through layers to get
    // back. The week is already saved by this point, so its aggregate is what
    // the picker loads.
    function onAddToList() {
        emit('update:modelValue', false);
        props.openAddToList();
    }

    // ── Reset on (re)open ────────────────────────────────────────────────────
    watch(() => props.modelValue, (open) => {
        if (!open) return;
        step.value = 1;
        proposed.value = [];
        previewIngredients.value = [];
        previewUnlinked.value = [];
        lastBuildRequested.value = 0;
        lastBuildPlaced.value = 0;
        doneState.value = false;
        recipeSearch.value = '';
        emphasis.value = 'use_up_stock';
        repeatSameDay.value = false;
        budgetCap.value = false;
        // Re-read on every open rather than once at mount: the cooking policy
        // arrives from `/api/health` asynchronously, and an admin can change
        // the headcount mid-session (the settings page refreshes it).
        defaultServings.value = householdHeadcount.value ?? 1;
        // Open on the obvious default: every day still ahead in this week, and
        // every slot. One tap gets you a week; the rest is fine-tuning.
        selectedDays.value = upcomingDays.value.map((d) => d.iso);
        selectedSlots.value = [...defaultSlots.value];
    });
</script>

<style scoped>
    .builder-field {
        margin-bottom: 1rem;
    }
    /* Quasar's step padding is sized for a desktop stepper; on a phone it
       costs 48px of an already-narrow content column. */
    .builder-stepper :deep(.q-stepper__step-inner) {
        padding-left: var(--space-3);
        padding-right: var(--space-3);
    }
    .builder-field__label {
        font-size: var(--font-size-sm);
        font-weight: 500;
        margin-bottom: 0.35rem;
    }
    .builder-hint {
        display: flex;
        align-items: flex-start;
        gap: 0.5rem;
        margin: 0.25rem 0 0.5rem;
        padding: 0.5rem 0.65rem;
        background: var(--surface-sunken);
        border: 1px solid var(--border-default);
        border-radius: 8px;
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
        line-height: 1.35;
    }
    .builder-hint__icon {
        flex: 0 0 auto;
        margin-top: 1px;
        color: var(--text-secondary);
    }
    /* The step's closing summary, so it sits against the action row rather
       than floating between two fields. */
    .builder-hint--summary {
        margin: 0.75rem 0 0;
    }
    /* Shrink-to-fit: the stepper otherwise takes the whole dialog width. */
    .builder-stepper-wrap {
        display: inline-flex;
    }
    .builder-day {
        margin-top: var(--space-3);
    }
    /* The recipe page's section-heading voice (`.rn__sectitle`), centred, with
       the rule running out to both edges — this separates days, where the row
       beneath it names a meal. */
    .builder-day__label {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        margin-bottom: var(--space-2);
        font-size: 0.8125rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-secondary);
    }
    .builder-day__label::before,
    .builder-day__label::after {
        content: '';
        flex: 1 1 auto;
        height: 1px;
        background: var(--divider);
    }
    /* FU-852 — stacked at every width. See the template comment: the previous
       single-line layout was only ever un-broken below a 599px VIEWPORT, which
       says nothing about the ~600px dialog the row actually lives in. */
    /* Owner 2026-09-12 — a card per meal, tighter than the divider-separated
       rows it replaces. A day's meals are separate objects you move, re-serve
       and delete individually; a divider between two of them read as one
       continuous list, and the day heading above them read as another row in
       it. Same shape on desktop: the dialog is ~600px there too. */
    .builder-row {
        display: flex;
        flex-direction: column;
        align-items: stretch;
        gap: var(--space-1);
        padding: var(--space-2);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-sm);
        background: var(--surface-component);
    }
    .builder-row + .builder-row {
        margin-top: var(--space-1);
    }
    /* Name, servings and delete on one line — the row's only spare horizontal
       space, and it saves a line per meal on a phone. */
    .builder-row__head {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        min-width: 0;
    }
    /* The name is the swap control, so it is a real button — but it reads as
       the row's title, not as a button: no fill, no border. The swap glyph
       that used to sit beside it is gone (owner 2026-09-12); the tooltip still
       says what clicking does. */
    .builder-row__name {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        flex: 1 1 auto;
        min-width: 0;
        padding: 0;
        border: none;
        background: none;
        font: inherit;
        font-weight: 500;
        color: var(--text-primary);
        text-align: left;
        cursor: pointer;
    }
    .builder-row__name:hover {
        color: var(--accent-ink);
    }
    .builder-row__name:focus-visible {
        outline: 2px solid var(--brand-primary);
        outline-offset: 2px;
        border-radius: var(--radius-sm);
    }
    .builder-row__meta {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: var(--space-1) var(--space-2);
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
    }
    .builder-reason {
        background: var(--surface-sunken);
        color: var(--text-secondary);
    }
    /* PROPOSAL_MEAL_PLANS_PART_2 §9 — proposed cook-batch marker (icon + text). */
    .builder-cook {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        font-size: var(--font-size-sm);
        font-weight: 600;
        color: var(--brand-primary);
    }
    /* Leftovers are grey, never a verdict colour (owner 2026-09-12): a day you
       eat from a cook you've already made is neither a warning nor an
       all-clear, and painting it either way puts two contradictory-looking
       states side by side in the same day. */
    .builder-cook--leftover {
        color: var(--text-muted);
        font-weight: 500;
    }
    /* Wraps rather than overflows: the two selects take a line of their own on
       a narrow dialog, and the stepper + remove keep the right edge. */
    .builder-row__controls {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--space-2);
    }
    /* `flex-basis` rather than `min-width`: a floor is what put the cluster off
       the row's right edge in the first place (same lesson as the dialog's own
       `min-width: 0`). */
    .builder-slot-select {
        flex: 1 1 7rem;
        min-width: 0;
    }
    .builder-day-select {
        flex: 1 1 9rem;
        min-width: 0;
    }
    .builder-servings {
        flex: 0 0 auto;
    }
    /* The week's two figures beside the two band counts, wrapping on a phone
       rather than squeezing. */
    .builder-need {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        gap: var(--space-1) var(--space-3);
        margin-bottom: var(--space-1);
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
    }
    .builder-need__figure {
        color: var(--text-primary);
        font-variant-numeric: tabular-nums;
    }
    .builder-picker {
        max-height: 55vh;
        overflow-y: auto;
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
    }
    .builder-list {
        max-height: 40vh;
        overflow-y: auto;
    }
    /* Owner feedback 2026-08-27 — the controls cluster alone wants ~400px
       (two 120–130px selects, a servings stepper and two icon buttons), so on
       a phone it can only work stacked under the meal name. The selects go
       full-width there; below them the servings stepper and the two actions
       sit on one line with the actions pushed to the right edge, which is
       where a thumb is. */
    /* The viewport-keyed row-stacking block that used to live here is gone —
       the row stacks unconditionally now (FU-852), so this media query was
       re-stating the default on a phone. What remains is genuinely about the
       viewport: a phone's scroll regions and its full-width action buttons. */
    @media (max-width: 599px) {
        /* One scroll region, not three: nested max-heights inside a dialog
           that is itself scrolling turns the review step into a set of tiny
           windows on a phone. */
        .builder-list,
        .builder-picker {
            max-height: none;
        }
        .builder-done-actions {
            width: 100%;
        }
        .builder-done-actions > * {
            flex: 1 1 100%;
        }
    }
</style>
