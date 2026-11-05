<template>
    <!-- FU-609 / R-036 — root on <q-page> for the layout height contract.
         Document-scroll page (normal padding + an internally-scrolling
         ingredients pane); no :style-fn. -->
    <q-page class="q-pa-md cook-mode">
        <div v-if="!recipe" class="text-center q-pa-xl">
            <AppSpinner v-if="loading" size="40px" />
            <q-banner v-else class="dora-bg-sunken">Recipe not found.</q-banner>
        </div>

        <template v-else>
            <!-- Cook-mode header. Owner feedback 2026-08-28: *"Everything is
                 squished badly on desktop too for the header (sous chef, info
                 button, cooking for #)"* / *"Cooking for input looks god awful.
                 All squished together."* / *"In mobile mode, the layout at the
                 top looks a bit odd."*

                 The squish had a mechanical cause on top of the layout one:
                 every gap in here was `--space-sm` / `--space-xs`,
                 and **neither token exists** in `css/tokens.scss` (the scale is
                 `--space-1..--space-12`). An undefined custom property with no
                 fallback makes the whole declaration invalid, so `gap` fell
                 back to its initial value — zero. The controls were literally
                 touching. Fixed to real tokens throughout; the app-wide sweep
                 for the same class of silent failure is FU-764.

                 Owner feedback 2026-09-03: *"Could Sous chef and its info
                 button be moved inline on the right of the recipe name? On
                 mobile it pushes to its own line, and the cooking for control
                 is its own entire row. We're halfway down the page on mobile
                 before we read the step text."* Fair — the 08-28 fix bought
                 breathing room by spending vertical space, which on a phone is
                 the scarcer of the two. So the bands collapse: the voice
                 cluster rides the identity line (the recipe name ellipsises
                 rather than the row growing — it's the page you navigated to,
                 so truncating it costs nothing), and only the headcount pill
                 wraps below on a phone. One band on desktop, two on a phone,
                 where it used to be two and three. -->
            <div class="cook-header q-mb-md">
                <!-- Icon-only, matching the stocktake runner and the stock
                     item detail page (owner feedback 2026-08-27) — the
                     label was the widest thing competing with the recipe
                     name for the top line. -->
                <BaseButton
                    variant="icon"
                    :icon="ICONS.arrow_back"
                    aria-label="Exit cook mode"
                    @click="exitCookMode"
                >
                    <BaseTooltip>Exit cook mode</BaseTooltip>
                </BaseButton>
                <div class="text-h6 ellipsis cook-header__name">{{ recipe.name }}</div>
                <HelpHint topic="Cook mode" />

                <div class="cook-header__voice">
                        <!-- Sous Chef. Owner feedback 2026-08-28: *"I prefer the
                             sous chef big button for desktop, the icon only version
                             can stay for mobile only"* and *"could be a bit bigger
                             in mobile view for fingers"*. So: a labelled button
                             above the phone breakpoint, an icon-only one below it,
                             and a 44px floor on the icon form (D-004) rather than
                             BaseButton's 36px desktop-chrome default.

                             On/off is still carried by the button's own styling —
                             filled when live, outlined when not — rather than by
                             appending "on" to the label (owner feedback
                             2026-08-27). `aria-pressed` carries the same state for
                             screen readers, which a purely visual treatment
                             otherwise drops. -->
                        <BaseButton
                            :variant="sousChefVariant"
                            :icon="ICONS.record_voice_over"
                            :label="isPhone ? undefined : 'Sous Chef'"
                            :aria-pressed="speechEnabled ? 'true' : 'false'"
                            aria-label="Sous Chef voice"
                            @click="toggleSpeech"
                        >
                            <!-- Owner feedback 2026-09-03: *"Remove 'tap to turn it
                                 on/off' - we know… just need 'Sous Chef reads each
                                 step…'"*. The on/off state is already carried twice
                                 over — filled vs outlined styling for the eye,
                                 `aria-pressed` for a screen reader — so spelling it
                                 out in the tooltip was a third copy of one fact, and
                                 the half of the tooltip that actually teaches
                                 something is what Sous Chef *does*. -->
                            <BaseTooltip>Sous Chef reads each step aloud as you go, hands-free.</BaseTooltip>
                        </BaseButton>
                        <BaseButton
                            v-if="speechRecognitionAvailable"
                            :variant="listening ? 'filled-icon' : 'icon'"
                            :icon="listening ? ICONS.mic : ICONS.mic_off"
                            :class="{ 'dora-text-muted': !listening }"
                            :aria-pressed="listening ? 'true' : 'false'"
                            aria-label="Listen for hands-free commands"
                            @click="toggleListening"
                        >
                            <!-- extended tooltip explains the mic is independent
                                 of Sous Chef narration. -->
                            <BaseTooltip>
                                {{ listening ? 'Stop listening.' : 'Listen for hands-free commands.' }}
                                Turns on the mic so next / previous / repeat / pause navigate
                                cook mode without touching the screen.
                            </BaseTooltip>
                        </BaseButton>
                        <!-- Owner feedback 2026-08-28: *"Would it be better to only
                             show the info button for sous chef if sous chef is
                             active?"* Yes — the popover lists spoken commands and
                             names the engine that spoke, both of which are answers
                             to questions you only have once something is listening
                             or talking. Silent cook mode gets one less control. -->
                        <BaseButton
                            v-if="speechEnabled || listening"
                            variant="icon"
                            :icon="ICONS.help_outline"
                            aria-label="Sous Chef commands"
                        >
                            <BaseTooltip>What can I say?</BaseTooltip>
                            <q-menu>
                                <q-card class="sous-chef-help" flat>
                                    <q-card-section>
                                        <div class="text-subtitle1 q-mb-sm">Sous Chef commands</div>
                                        <!-- Owner feedback 2026-09-03 — reworded; the
                                             old copy spent two clauses reassuring you
                                             that kitchen chatter is ignored, which is
                                             the unremarkable default. -->
                                        <div class="text-caption dora-text-muted q-mb-sm">
                                            With voice input enabled, say any of these to interact with your Sous Chef.
                                        </div>
                                        <q-list dense>
                                            <q-item v-for="cmd in SOUS_CHEF_COMMANDS" :key="cmd.label">
                                                <q-item-section>
                                                    <div class="row items-baseline q-gutter-xs">
                                                        <span class="text-weight-medium">{{ cmd.label }}</span>
                                                        <span class="text-caption dora-text-muted">{{ cmd.does }}</span>
                                                    </div>
                                                </q-item-section>
                                            </q-item>
                                        </q-list>
                                        <!-- (FU-722's "Voice: Piper (server)" line was
                                             removed on owner feedback 2026-09-03 — which
                                             engine spoke is a debugging fact, and this
                                             popover is a mid-cook command reference.
                                             `useSpeechOutput().lastEngine` still carries
                                             it for whoever needs it next.) -->
                                    </q-card-section>
                                </q-card>
                            </q-menu>
                        </BaseButton>
                </div>

                <!-- Headcount. Session-only; the saved recipe stays at
                     `recipe.servings`.

                     Owner feedback 2026-08-28: *"Cooking for input looks god
                     awful. All squished together."* It was a bare label + a
                     72px-wide `q-input[type=number]` at zero gap, so the
                     words, the box and its native spinner arrows all ran
                     together and the only touch target was a ~10px browser
                     arrow. It is a stepper in a bordered pill now — one
                     object with a label and two 44px targets (D-004). Typing
                     is deliberately gone: the value seeds from the
                     install-wide household headcount and is nudged by one or
                     two from there, and a keyboard opening over the hob is
                     the thing a cook least wants. -->
                <NumberStepper
                    v-model="cookingFor"
                    variant="pill"
                    :min="1"
                    :icon="ICONS.group"
                    label="Cooking for"
                    decrement-label="Cook for one fewer"
                    increment-label="Cook for one more"
                    class="cook-header__headcount"
                >
                    <!-- Owner feedback 2026-09-03: *"Trim text '- the saved
                         recipe stays at X servings'"*. "for this cook only"
                         already says it. -->
                    <BaseTooltip>Rescales quantities for this cook only.</BaseTooltip>
                </NumberStepper>
            </div>

            <!-- PROPOSAL_RECIPE_IMAGE_STEPS — image-mode replaces the step-
                 by-step navigation with a scrollable image gallery. The
                 ingredients panel, finish flow, and substitute swaps still
                 render below (same as the other modes). -->
            <CookImageView
                v-if="isImageMode"
                :recipe-id="recipe.recipe_id"
                :images="recipe.step_images ?? []"
                :nav-size="navButtonSize"
                @finish="openFinish"
            />

            <!-- The bar and the count are one component now (owner feedback
                 2026-08-28 — the count was tiny caption text floating above an
                 unrelated bar). Shared with the image face so both read the
                 same. -->
            <CookStepProgress
                v-if="!isImageMode"
                :current="currentStepIndex"
                :total="steps.length"
                class="q-mb-md"
                jumpable
                @select="goToStep"
            />

            <!-- FU-943: a timer keeps running when you move on (a 40-minute
                 braise outlives the steps after it). Off its own step it
                 shows here, with a way back to the step that set it. -->
            <div v-if="timerElsewhere" class="cook-timer-band row items-center q-gutter-sm q-mb-md">
                <q-icon :name="ICONS.timer" size="22px" color="primary" />
                <span class="text-body1">
                    Step {{ (timerStepIndex ?? 0) + 1 }} timer
                    <strong class="timer-text">{{ formatTimer(timerRemaining ?? 0) }}</strong>
                </span>
                <q-space />
                <BaseButton
                    v-if="timerRunning"
                    variant="ghost"
                    :icon="ICONS.pause"
                    label="Pause"
                    @click="pauseTimer"
                />
                <BaseButton
                    v-else-if="(timerRemaining ?? 0) > 0"
                    variant="ghost"
                    :icon="ICONS.play_arrow"
                    label="Resume"
                    @click="resumeTimer"
                />
                <BaseButton
                    variant="ghost"
                    label="Go to step"
                    @click="goToStep(timerStepIndex ?? 0)"
                />
            </div>

            <q-card v-if="!isImageMode" flat bordered class="step-card q-mb-md">
                <q-card-section>
                    <div class="row items-center q-gutter-xs q-mb-xs">
                        <!-- section header for the current step. -->
                        <q-chip
                            v-if="currentStepObject?.sectionName"
                            dense
                            outline
                            color="primary"
                            :icon="ICONS.list"
                        >
                            {{ currentStepObject.sectionName }}
                        </q-chip>
                        <q-chip
                            v-if="currentStepObject?.isSubStep"
                            dense
                            color="primary"
                            class="dora-text-on-primary"
                            :icon="ICONS.subdirectory_arrow_right"
                        >
                            Sub-step
                        </q-chip>
                    </div>
                    <div class="text-h4 step-text">{{ currentStep }}</div>
                    <div
                        v-if="currentStepObject?.hint"
                        class="step-hint q-mt-sm dora-text-muted text-body2"
                    >
                        <q-icon :name="ICONS.lightbulb" size="16px" class="q-mr-xs" />
                        {{ currentStepObject.hint }}
                    </div>
                </q-card-section>

                <q-card-section v-if="stepTimerMinutes !== null" class="dora-bg-sunken">
                    <div class="row items-center q-gutter-sm">
                        <q-icon :name="ICONS.timer" size="32px" color="primary" />
                        <div class="text-h6 timer-text">
                            {{ formatTimer(timerOnThisStep ? (timerRemaining ?? stepTimerMinutes * 60) : stepTimerMinutes * 60) }}
                        </div>
                        <!-- Owner feedback 2026-09-01: *"How does the timer
                             function get added? Is it guessing?"* It was, for
                             every recipe. A structured step can now declare a
                             timer outright, and where one hasn't been declared
                             the old text sniff still runs — but says so, rather
                             than presenting a guess as a fact. -->
                        <span v-if="!timerIsDeclared" class="text-caption dora-text-muted">
                            from this step's wording
                        </span>
                        <q-space />
                        <BaseButton
                            v-if="!timerRunning || !timerOnThisStep"
                            variant="primary"
                            :icon="ICONS.play_arrow"
                            label="Start"
                            @click="startTimer(stepTimerMinutes * 60)"
                        />
                        <!-- Warning tone via BaseButton's `color` override
                             (no dedicated variant) — keeps the app-wide
                             no-caps + button language (R-001/DR-3). -->
                        <BaseButton
                            v-else
                            variant="primary"
                            color="warning"
                            :icon="ICONS.pause"
                            label="Pause"
                            @click="pauseTimer"
                        />
                        <BaseButton
                            v-if="timerOnThisStep && timerRemaining !== null"
                            variant="ghost"
                            :icon="ICONS.restart_alt"
                            label="Reset"
                            @click="resetTimer"
                        />
                    </div>
                    <!-- fill-bar that empties as time passes.
                         Tone shifts to negative when finished so the bar
                         itself confirms the toast/audio. -->
                    <q-linear-progress
                        v-if="timerOnThisStep && timerTotal !== null && timerTotal > 0"
                        :value="timerProgress"
                        :color="timerRemaining === 0 ? 'negative' : 'primary'"
                        rounded
                        size="10px"
                        class="q-mt-sm timer-bar"
                    />
                </q-card-section>

                <!-- Owner feedback 2026-09-13: the notes belong to the step
                     text, not to the gap below the nav buttons. Last band on
                     the card, after the timer — the timer is about *this*
                     step, the notes are about the recipe, so the step-specific
                     thing stays closest to the step. -->
                <CookNotesSection v-if="cookNotes" :notes="cookNotes" />
            </q-card>

            <CookNavRow
                v-if="!isImageMode"
                class="q-mb-lg"
                :size="navButtonSize"
                :can-prev="currentStepIndex > 0"
                :is-last="currentStepIndex === steps.length - 1"
                show-repeat
                :repeat-disabled="!speechEnabled"
                @prev="prevStep"
                @repeat="speakCurrent"
                @next="nextStep"
            />

            <!-- RD-29 — image mode has no step card for the notes band to hang
                 off, so this is the one call site that supplies its own card.
                 Step mode renders the same component inside `.step-card`. -->
            <q-card v-if="isImageMode && cookNotes" flat bordered class="q-mb-md">
                <CookNotesSection :notes="cookNotes" />
            </q-card>

            <!-- Ingredients + the B8 cook-session substitute picker (FU-942).
                 The swaps are this page's: the finish flow and the spoken
                 "Ingredients" answer read them too. -->
            <CookIngredientsPanel
                ref="ingredientsPanel"
                v-model:swaps="sessionSwaps"
                :recipe="recipe"
                :cooking-for="cookingFor"
                :highlighted-ingredient-ids="highlightedIngredientIds"
            />

            <!-- Tools. Owner feedback 2026-09-01: *"Can tools be styled
                 better? Looks so bad alongside the ingredients"* and *"should
                 we aim for consistency across the 3 sections ingredients,
                 tools and steps?"*

                 The three panels were three different objects: ingredients
                 were location-grouped cards of list rows, tools were a bare
                 wrap of `q-chip`s on a padded div, steps were an undecorated
                 `q-list`. They now share one shape — a bordered card holding
                 list rows — so the eye reads them as three views of the same
                 recipe rather than three widgets. `.cook-section` carries the
                 header treatment; `.cook-card` the body.

                 The per-step highlight is *kept* here and given the same
                 treatment ingredient rows wear (accent rule + tint, neighbours
                 dimmed). It works because structured steps register their
                 tools the same way they register ingredients; a free-text
                 method has no per-step tool links, so `highlightedToolIds` is
                 empty there and every row renders plain — no dimming, which is
                 the honest answer rather than a guess. -->
            <q-expansion-item
                v-if="recipeTools.length > 0"
                default-opened
                class="cook-section"
                header-class="cook-section__head"
            >
                <template #header>
                    <q-item-section avatar>
                        <q-icon :name="ICONS.blender" color="primary" />
                    </q-item-section>
                    <q-item-section class="cook-section__title">Tools</q-item-section>
                </template>
                <div class="q-pt-sm">
                    <q-card flat bordered class="cook-card">
                        <q-list dense>
                            <q-item
                                v-for="tool in recipeTools"
                                :key="tool.tool_id"
                                :class="{
                                    'cook-row--highlighted': highlightedToolIds.has(tool.tool_id),
                                    'cook-row--dim': highlightedToolIds.size > 0 && !highlightedToolIds.has(tool.tool_id),
                                }"
                            >
                                <q-item-section avatar class="cook-row__avatar">
                                    <q-icon :name="ICONS.blender" size="18px" class="dora-text-muted" />
                                </q-item-section>
                                <q-item-section class="tool-name">{{ tool.name }}</q-item-section>
                            </q-item>
                        </q-list>
                    </q-card>
                </div>
            </q-expansion-item>

            <q-expansion-item
                v-if="!isImageMode"
                class="cook-section"
                header-class="cook-section__head"
            >
                <template #header>
                    <q-item-section avatar>
                        <q-icon :name="ICONS.list" color="primary" />
                    </q-item-section>
                    <q-item-section class="cook-section__title">All steps</q-item-section>
                </template>
                <div class="q-pt-sm">
                <q-card flat bordered class="cook-card">
                <q-list>
                    <!-- Owner feedback 2026-09-13: *"Match highlight styling
                         for current step from the all steps area with the
                         ingredients and tools highlight. Prefer ingredients
                         and tools highlight look."* This was Quasar's `active`
                         prop, which only recolours the text — a fourth way of
                         saying "this row is the one" on a surface that already
                         had one. It wears `.cook-row--highlighted` now, the
                         same tint-plus-accent-rule the ingredient and tool
                         rows use.

                         What it does NOT borrow is `.cook-row--dim`. Dimming
                         the neighbours is right there — the highlight answers
                         "which of these does this step need?", so the rest are
                         noise. Here every other step is still something you
                         read ahead to or back at, so dimming them would be
                         dimming the list's whole purpose. `aria-current`
                         carries what the `active` prop used to imply. -->
                    <q-item
                        v-for="(step, idx) in cookSteps"
                        :key="idx"
                        clickable
                        :aria-current="idx === currentStepIndex ? 'step' : undefined"
                        @click="goToStep(idx)"
                        :class="{
                            'all-steps-row--sub': step.isSubStep,
                            'cook-row--highlighted': idx === currentStepIndex,
                        }"
                    >
                        <q-item-section avatar class="cook-row__avatar">
                            <!-- Owner feedback 2026-09-13: *"Use same number
                                 circles styling as on the recipe view."* The
                                 numeral chrome already lives in the shared
                                 `css/recipeSteps.scss` for exactly this reason
                                 (R-001) — cook mode was the one numbered step
                                 list still drawing its own. -->
                            <span class="dora-steps__num">{{ idx + 1 }}</span>
                        </q-item-section>
                        <q-item-section>
                            <!-- show the section header at the
                                 first step of each section in the overview. -->
                            <div
                                v-if="step.sectionName && (idx === 0 || cookSteps[idx - 1]?.sectionName !== step.sectionName)"
                                class="text-caption text-primary q-mb-xs"
                            >
                                {{ step.sectionName }}
                            </div>
                            {{ step.text }}
                        </q-item-section>
                    </q-item>
                </q-list>
                </q-card>
                </div>
            </q-expansion-item>
        </template>

        <!-- Finish flow (FU-942) — opened through `show()` so its rows are
             built from the recipe and this cook's swaps at that moment. -->
        <CookFinishDialog
            ref="finishDialog"
            v-model="finishDialogOpen"
            :recipe="recipe"
            :swaps="sessionSwaps"
            @finished="exitCookMode"
        />
    </q-page>
</template>

<script lang="ts" setup>
    import HelpHint from 'src/components/help/HelpHint.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import AppSpinner from 'src/components/AppSpinner.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import NumberStepper from 'src/components/NumberStepper.vue';
    import CookStepProgress from 'src/components/recipes/CookStepProgress.vue';
    import CookImageView from 'src/components/recipes/CookImageView.vue';
    import CookNavRow from 'src/components/recipes/CookNavRow.vue';
    import CookIngredientsPanel, { type SessionSwap } from 'src/components/recipes/CookIngredientsPanel.vue';
    import CookFinishDialog from 'src/components/recipes/CookFinishDialog.vue';
    import { formatTimer, useCookTimer } from 'src/composables/useCookTimer';
    import { cookQuantityLabel, useCookSteps } from 'src/composables/useCookSteps';
    import { SOUS_CHEF_COMMANDS, useCookVoice } from 'src/composables/useCookVoice';
    import CookNotesSection from 'src/components/recipes/CookNotesSection.vue';
    import { useQuasar } from 'quasar';
    import { useCookingPolicy } from 'src/composables/useCookingPolicy';
    import { useWakeLock } from 'src/composables/useWakeLock';
    import type { Recipe } from 'src/models/recipe';
    import RecipeApiService from 'src/services/api/recipeApiService';
    import { useLocationStore } from 'src/stores/locationStore';
    import { useRecipeStore } from 'src/stores/recipeStore';
    import { useRecipeVocabStore } from 'src/stores/recipeVocabStore';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
    import { useShortcut } from 'src/composables/useShortcut';
    import { useRoute, useRouter } from 'vue-router';

    // FU-942: this page keeps the route, the load, the header, the step face,
    // the timer UI and the tools / all-steps panels. The step model is
    // `useCookSteps`, the voice layer `useCookVoice`, the timer
    // `useCookTimer`; the ingredients panel (with the swap picker) and the
    // finish dialog are their own components.

    const route = useRoute();
    const router = useRouter();
    const $q = useQuasar();
    const recipeStore = useRecipeStore();
    const recipeVocabStore = useRecipeVocabStore();
    const locationStore = useLocationStore();
    const stockItemStore = useStockItemStore();
    const stockLevelStore = useStockLevelStore();
    const shoppingListStore = useShoppingListStore();
    const recipeApiService = new RecipeApiService();

    // hold the screen awake for the whole cook session (both the
    // running timer and the read-along steps assume a visible screen the
    // user isn't tapping). Released automatically on unmount.
    const wakeLockWanted = ref(true);
    useWakeLock(wakeLockWanted);

    const recipe = ref<Recipe | null>(null);
    const loading = ref(true);
    const currentStepIndex = ref(0);

    // PROPOSAL_RECIPE_IMAGE_STEPS — image mode swaps the step-by-step
    // navigation for a scrollable image gallery. Other surfaces
    // (ingredients, finish flow, B8 swaps, sous-chef speech) stay shared.
    const isImageMode = computed(
        () => recipe.value?.steps_mode === 'image',
    );

    /** The cook's own notes, or null. Both call sites gate on this, so the
     *  "is there anything to show?" test is written once. */
    const cookNotes = computed(() => recipe.value?.notes?.trim() || null);

    // session-only headcount. Seeds from the install-wide
    // `household_headcount` (FU-615 — set in Settings → System → Cooking,
    // read via /api/health) when present, otherwise the recipe's own
    // `servings`. Never writes back to the saved recipe — matches the
    // B8-substitute discipline of "this cook only".
    const { householdHeadcount } = useCookingPolicy();
    // Owner 2026-09-04 — *"When clicking cook now from a meal slot, auto adjust
    // the servings based on what the meal plan says for that slot… I expect it
    // to be adjusted to 6 when I get to cook mode."* `?for=N` is that request,
    // and it outranks the household headcount: a caller who names a number
    // knows something this page doesn't (the planner passes the slot's
    // servings, or a linked batch's total yield). Still session-only and still
    // freely adjustable here — it only decides what the pill opens at.
    const requestedServings = computed<number | null>(() => {
        const raw = Number(route.query.for);
        return Number.isFinite(raw) && raw > 0 ? Math.floor(raw) : null;
    });
    const cookingFor = ref<number>(
        requestedServings.value
        ?? (householdHeadcount.value && householdHeadcount.value > 0
            ? householdHeadcount.value
            : 1),
    );
    watch(recipe, (next) => {
        const headcount = householdHeadcount.value;
        if (requestedServings.value) {
            cookingFor.value = requestedServings.value;
        } else if (headcount && headcount > 0) {
            cookingFor.value = headcount;
        } else if (next?.servings && next.servings > 0) {
            cookingFor.value = next.servings;
        }
    }, { immediate: true });

    /** Below the phone breakpoint the voice controls go icon-only; above it
     *  Sous Chef gets its label back (owner feedback 2026-08-28: *"I prefer the
     *  sous chef big button for desktop, the icon only version can stay for
     *  mobile only"*). Reactive via Quasar's Screen plugin, activated in
     *  `boot/quasarScreen.ts`. */
    const isPhone = computed(() => $q.screen.lt.sm);

    /** Owner feedback 2026-09-03 — the three step buttons have to share one
     *  row on a phone. `size="lg"` is where the width goes: Quasar writes it as
     *  an INLINE font-size, so no stylesheet rule can shrink it (a CSS
     *  `font-size` in the media query below was tried, measured, and found
     *  inert). The framework-level answer is to hand it a different size, not
     *  to fight the inline style with `!important`. */
    const navButtonSize = computed(() => (isPhone.value ? 'md' : 'lg'));

    const {
        cookSteps,
        steps,
        currentStep,
        currentStepObject,
        highlightedIngredientIds,
        highlightedToolIds,
        timerIsDeclared,
        stepTimerMinutes,
    } = useCookSteps(recipe, currentStepIndex);

    const {
        remaining: timerRemaining,
        running: timerRunning,
        total: timerTotal,
        progress: timerProgress,
        start: startCookTimer,
        pause: pauseTimer,
        reset: resetCookTimer,
    } = useCookTimer({
        // On iOS / macOS WKWebView a timer callback is not a user activation,
        // so `speak()` and `playTimerFinishTone()` are subject to the autoplay
        // gate; `useSpeechOutput` primes audio on the first gesture, which
        // covers most timers. The toast is the load-bearing "done" signal;
        // audio and narration are best-effort.
        onFinish: () => {
            $q.notify({ type: 'positive', message: 'Timer finished!', icon: ICONS.timer });
            if (speechEnabled.value) speak('Timer finished');
            playTimerFinishTone();
        },
    });

    // tools panel. Resolves the recipe's `tool_ids` against
    // the vocab store so the panel can render `{tool_id, name}` rows; only
    // shown when the recipe references any tools at all.
    type CookTool = { tool_id: string; name: string };
    const recipeTools = computed<CookTool[]>(() => {
        const ids = recipe.value?.tool_ids ?? [];
        if (ids.length === 0) return [];
        const vocab = recipeVocabStore.tools;
        return ids
            .map((id) => {
                const match = vocab.find((t) => t.tool_id === id);
                return match ? { tool_id: id, name: match.name } : null;
            })
            .filter((t): t is CookTool => t !== null);
    });

    // ── B8 — temporary, cook-session-only substitutions ─────────────────
    // Owned here, edited by `CookIngredientsPanel` (v-model:swaps), read by
    // the finish flow and the spoken "Ingredients" answer. Keyed by the
    // recipe ingredient's original stock_item_id.
    const sessionSwaps = ref(new Map<string, SessionSwap>());
    const ingredientsPanel = ref<InstanceType<typeof CookIngredientsPanel> | null>(null);
    const finishDialog = ref<InstanceType<typeof CookFinishDialog> | null>(null);
    const finishDialogOpen = ref(false);

    // generated beep via WebAudio. Stays silent if the
    // browser denies audio (PWA / iOS may require a user gesture before any
    // sound plays; we ignore the failure rather than spam the console). The
    // toast + voice prompt keep the user informed regardless.
    function playTimerFinishTone() {
        try {
            const AudioCtor: typeof AudioContext | undefined =
                typeof window !== 'undefined'
                    ? (window.AudioContext
                        ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext)
                    : undefined;
            if (!AudioCtor) return;
            const ctx = new AudioCtor();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.value = 880; // a brief A5
            gain.gain.setValueAtTime(0.0001, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.5);
            osc.connect(gain).connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.55);
            osc.onended = () => { void ctx.close(); };
        } catch {
            // Silent fallback — see comment above.
        }
    }

    // FU-943: the one timer belongs to the step that started it and keeps
    // running across step changes. Starting another step's timer replaces it.
    const timerStepIndex = ref<number | null>(null);
    const timerOnThisStep = computed(() => timerStepIndex.value === currentStepIndex.value);
    const timerElsewhere = computed(() =>
        timerStepIndex.value !== null && !timerOnThisStep.value && timerRemaining.value !== null,
    );

    function startTimer(seconds: number) {
        if (!timerOnThisStep.value) resetCookTimer();
        timerStepIndex.value = currentStepIndex.value;
        startCookTimer(seconds);
    }

    function resumeTimer() {
        startCookTimer(timerRemaining.value ?? 0);
    }

    function resetTimer() {
        resetCookTimer();
        timerStepIndex.value = null;
    }

    function nextStep() {
        // no more per-step tick state; advancing just navigates
        // (or opens the finish flow when we've run out of steps).
        if (currentStepIndex.value < steps.value.length - 1) {
            currentStepIndex.value += 1;
        } else {
            openFinish();
        }
    }

    function prevStep() {
        if (currentStepIndex.value > 0) {
            currentStepIndex.value -= 1;
        }
    }

    function goToStep(idx: number) {
        currentStepIndex.value = idx;
    }

    function openFinish() {
        pauseTimer();
        finishDialog.value?.show();
    }

    function exitCookMode() {
        pauseTimer();
        // Through the composable (R-003) so a Piper `<audio>` stops with the
        // Web Speech voice — a raw `speechSynthesis.cancel()` left it playing
        // until unmount (finalisation 04-R3).
        cancelSpeech();
        stopListening();
        // L298 — exit returns to the recipe's detail page (where the user
        // came from), not all the way back to the cookbook overview.
        const id = route.params.id as string;
        void router.push(id ? `/cookbook/${id}` : '/cookbook');
    }

    /** The name to *say* for an ingredient: the substitute when one is swapped
     *  in for this cook, because that is what's going in the bowl. */
    function spokenIngredientName(ingredient: Recipe['ingredients'][number]): string {
        const stockItemId = ingredient.stock_item_id;
        const swap = stockItemId !== null ? sessionSwaps.value.get(stockItemId) : undefined;
        if (swap) return swap.substituteName;
        return ingredient.label ?? ingredient.stock_item_name ?? ingredient.raw_text ?? 'an unnamed ingredient';
    }

    /** "Ingredients" — the current step's ingredients, quantities scaled
     *  to the headcount exactly as the panel shows them. */
    function stepIngredientsAnswer(): string {
        const recipeIngredients = recipe.value?.ingredients ?? [];
        if (recipeIngredients.length === 0) {
            return "This recipe doesn't list any ingredients.";
        }
        const ids = highlightedIngredientIds.value;
        const rows = recipeIngredients.filter((ing) => ids.has(ing.recipe_ingredient_id));
        if (rows.length === 0) {
            return 'No ingredients are linked to this step.';
        }
        const parts = rows.map((ing) => {
            const quantity = cookQuantityLabel(ing.quantity, ing.unit, recipe.value?.servings ?? null, cookingFor.value);
            const name = spokenIngredientName(ing);
            const optional = ing.is_optional ? ', optional' : '';
            return quantity ? `${quantity} ${name}${optional}` : `${name}${optional}`;
        });
        return `For this step: ${parts.join('; ')}.`;
    }

    /** "Tools" — same shape as the ingredients answer. Only a structured step
     *  carries tool links, so a free-text method says so rather than guessing
     *  (there is no text-match fallback for tools — see `highlightedToolIds`). */
    function stepToolsAnswer(): string {
        if (recipeTools.value.length === 0) {
            return "This recipe doesn't list any tools.";
        }
        const ids = highlightedToolIds.value;
        const names = recipeTools.value.filter((tool) => ids.has(tool.tool_id)).map((tool) => tool.name);
        if (names.length === 0) {
            return 'No tools are linked to this step.';
        }
        return `For this step: ${names.join('; ')}.`;
    }

    const {
        speechEnabled,
        listening,
        speechRecognitionAvailable,
        speak,
        speakCurrent,
        cancelSpeech,
        toggleSpeech,
        stopListening,
        toggleListening,
        rearmFirstStepAnnouncement,
    } = useCookVoice({
        currentStep,
        currentStepIndex,
        steps,
        ready: computed(() => recipe.value !== null),
        stepTimerMinutes,
        timerRunning,
        actions: {
            next: nextStep,
            previous: prevStep,
            startTimer,
            pauseTimer,
            resetTimer,
            exit: exitCookMode,
            ingredientsAnswer: stepIngredientsAnswer,
            toolsAnswer: stepToolsAnswer,
        },
    });

    const sousChefVariant = computed(() => {
        if (isPhone.value) return speechEnabled.value ? 'filled-icon' : 'icon';
        return speechEnabled.value ? 'primary' : 'secondary';
    });

    /** Load (or re-load) the recipe for a route id, resetting the cook
     *  session — step position, timer, swaps, the first-step announcement
     *  and a latched "not found" (FU-765 / finalisation 04-R1). Vue reuses
     *  this component across `/cookbook/A/cook` → `/cookbook/B/cook`, so
     *  fetching only in `onMounted` kept recipe A on screen under B's URL. A
     *  different recipe id *is* a different cook, so resetting is the honest
     *  behaviour rather than mutating a live session. */
    async function loadRecipe(recipeId: string) {
        loading.value = true;
        recipe.value = null;
        currentStepIndex.value = 0;
        resetTimer();
        sessionSwaps.value = new Map();
        rearmFirstStepAnnouncement();
        finishDialogOpen.value = false;
        try {
            await recipeStore.ensureLoadedAsync();
            // the list endpoint doesn't return `steps[]`
            // (only `has_structured_steps`), and cook mode needs structured
            // steps for per-step highlights / hints. Always fetch detail so
            // `recipe.value.steps` is present when the recipe has them.
            const fresh = await recipeApiService.getAsync(recipeId);
            // A slow response for a recipe we've since moved off must not
            // land under the new route's id.
            if (recipeId !== route.params.id) return;
            recipe.value = fresh;
        } catch {
            if (recipeId !== route.params.id) return;
            recipe.value = null;
        } finally {
            if (recipeId === route.params.id) loading.value = false;
        }
    }

    watch(() => route.params.id, (id, previous) => {
        if (typeof id === 'string' && id && id !== previous) void loadRecipe(id);
    });

    // Keyboard through the shared layer (finalisation 04-R7): the raw
    // `window` listener kept stepping the recipe underneath the finish
    // dialog and the swap picker, and the keys never reached the `?`
    // cheatsheet. Blocked while either overlay is open — the overlay owns
    // Escape and the arrows then.
    const overlayOpen = () => finishDialogOpen.value || (ingredientsPanel.value?.pickerOpen ?? false);
    useShortcut([
        { keys: 'arrowright', scope: 'Cook mode', description: 'Next step', handler: (e) => { if (overlayOpen()) return; e.preventDefault(); nextStep(); } },
        { keys: 'space', scope: 'Cook mode', description: 'Next step', handler: (e) => { if (overlayOpen()) return; e.preventDefault(); nextStep(); } },
        { keys: 'arrowleft', scope: 'Cook mode', description: 'Previous step', handler: (e) => { if (overlayOpen()) return; e.preventDefault(); prevStep(); } },
        { keys: 'r', scope: 'Cook mode', description: 'Read this step again', handler: () => { if (!overlayOpen()) speakCurrent(); } },
        { keys: 'escape', scope: 'Cook mode', description: 'Exit cook mode', handler: () => { if (!overlayOpen()) exitCookMode(); } },
    ]);

    onMounted(async () => {
        await loadRecipe(route.params.id as string);

        // Warm the locations tree so ingredient breadcrumbs render without
        // a flash. Fire-and-forget — cook mode is usable without it.
        void locationStore.ensureLoadedAsync();

        // Stock items + levels back the ingredient chips and the finish flow;
        // membership/primary feed the "add ran-out items" step; tools vocab
        // (Chunk 5) feeds the per-step tools panel.
        await Promise.all([
            stockItemStore.ensureLoadedAsync(),
            stockLevelStore.ensureLoadedAsync(),
            shoppingListStore.ensureLoadedAsync(),
            recipeVocabStore.ensureLoadedAsync(),
        ]);
    });

    onBeforeUnmount(() => {
        pauseTimer();
        stopListening();
        cancelSpeech();
    });
</script>

<style scoped lang="scss">
    // The section / card / highlighted-row treatment shared with
    // `CookIngredientsPanel` (FU-942) — tools and all steps wear it here.
    @use '../css/cookSections';

    .cook-mode {
        max-width: 900px;
        margin: 0 auto;
    }
    .cook-timer-band {
        padding: 0.5rem 0.75rem;
        background: var(--surface-sunken);
        border: 1px solid var(--border-default);
        border-radius: 8px;
    }

    .step-card {
        min-height: 200px;
    }
    .step-text {
        line-height: 1.4;
        font-weight: 400;
    }
    // Fixed avatar column so an ingredient quantity, a tool glyph and a step
    // number all start their text at the same x. Sized to the shared numeral
    // circle (34px) since 2026-09-13 — it is the widest of the three, and the
    // column has to hold it without squashing it.
    .cook-row__avatar {
        min-width: 34px;
        padding-right: var(--space-2);
    }
    .tool-name {
        font-weight: 500;
    }
    // fill-bar visually echoes the MM:SS countdown.
    .timer-bar {
        transition: opacity var(--motion-normal) var(--motion-ease);
    }
    .timer-text {
        font-variant-numeric: tabular-nums;
    }
    .sous-chef-help {
        min-width: 300px;
        max-width: 360px;
    }
    // Tool rows the current step doesn't use dim, so the eye lands on the
    // highlighted ones (see `.cook-row--highlighted` in `cookSections.scss`).
    .cook-row--dim {
        opacity: 0.55;
    }
    .all-steps-row--sub {
        padding-left: var(--space-8);
    }
    .step-hint {
        line-height: 1.4;
    }
    // Cook-mode header (owner feedback 2026-08-27, 08-28 and 09-03).
    //
    // ONE wrapping row: exit, name, voice cluster, headcount pill. The 08-28
    // fix stacked these into bands to kill the squish, and 09-03 reported the
    // bill for that — three bands push the step text (the entire point of the
    // surface) below the fold on a phone. So the name absorbs the pressure
    // instead: it is `flex: 1 1 0` with `min-width: 0`, which is what actually
    // lets the ellipsis engage, and the controls beside it never shrink. The
    // headcount is the only thing allowed to wrap, and only below 600px.
    //
    // Note for anyone editing the gaps: `--space-sm` / `--space-xs` do NOT
    // exist (the scale is `--space-1..--space-12`). Every gap in this block was
    // one of those once, which invalidated the declaration and collapsed them
    // all to 0 — the mechanical half of the original "everything is squished"
    // report. See FU-764.
    .cook-header {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        flex-wrap: wrap;
    }
    .cook-header__name {
        min-width: 0;
        flex: 1 1 0;
    }
    .cook-header__voice {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        flex: 0 0 auto;
    }
    // D-004 — the voice cluster is the one thing in cook mode you reach for
    // with a wet or floury finger, so its buttons clear the 44px floor rather
    // than sitting at BaseButton's 36px desktop-chrome default.
    .cook-header__voice :deep(.dora-btn) {
        min-height: 44px;
    }
    .cook-header__voice :deep(.dora-btn--icon),
    .cook-header__voice :deep(.dora-btn--filled-icon) {
        min-width: 44px;
    }
    .cook-header__headcount {
        margin-left: var(--space-2);
    }
    @media (max-width: 599px) {
        // A phone has room for the name + the voice icons on line one, and
        // nothing else; the headcount takes the full second line rather than
        // squeezing the name to three characters.
        .cook-header__headcount {
            flex: 1 1 100%;
            margin-left: 0;
            justify-content: space-between;
        }
    }
</style>
