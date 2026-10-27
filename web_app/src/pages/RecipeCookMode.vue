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
                 every gap in here was `var(--space-sm)` / `var(--space-xs)`,
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
                                            <q-item v-for="cmd in sousChefCommands" :key="cmd.label">
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
                            {{ formatTimer(timerRemaining ?? stepTimerMinutes * 60) }}
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
                            v-if="!timerRunning"
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
                            v-if="timerRemaining !== null"
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
                        v-if="timerTotal !== null && timerTotal > 0"
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

            <!-- ingredients grouped by base stock location.
                 Stock-level chips intentionally removed mid-cook: the
                 decision to cook this recipe is already made; visual noise
                 about what's low/out only belongs on the finish surface
                 (Chunk 1). The expansion stays for collapse, but the
                 inner list is a card per location group rather than one
                 long flat list. -->
            <q-expansion-item
                default-opened
                class="cook-section"
                header-class="cook-section__head"
            >
                <template #header>
                    <q-item-section avatar>
                        <q-icon :name="ICONS.ingredients" color="primary" />
                    </q-item-section>
                    <q-item-section class="cook-section__title">Ingredients</q-item-section>
                </template>
                <div class="q-pt-sm">
                    <q-card
                        v-for="group in ingredientGroups"
                        :key="group.key"
                        flat
                        bordered
                        class="q-mb-sm cook-card"
                    >
                        <q-card-section class="q-pb-xs">
                            <div class="row items-center q-gutter-xs">
                                <q-icon :name="ICONS.place" size="16px" class="dora-text-muted" />
                                <span class="text-subtitle2">{{ group.label }}</span>
                            </div>
                        </q-card-section>
                        <q-list dense>
                            <q-item
                                v-for="row in group.rows"
                                :key="row.ingredient.recipe_ingredient_id"
                                :class="{
                                    'cook-row--highlighted': highlightedIngredientIds.has(row.ingredient.recipe_ingredient_id),
                                    'ingredient-row--optional': row.ingredient.is_optional,
                                }"
                            >
                                <q-item-section>
                                    <div class="row items-center q-gutter-xs no-wrap">
                                        <span class="text-caption dora-text-muted ingredient-quantity">
                                            {{ displayQuantity(row.ingredient.quantity, row.ingredient.unit) }}
                                        </span>
                                        <!-- IMPL_PLAN_RECIPE_IMPORTER §Chunk 4:
                                             unlinked ingredients (stock_item_id === null) render
                                             as read-only raw_text — no substitute machinery, no
                                             swap chip, since there's no stock item to swap FROM.

                                             Owner feedback 2026-09-03: *"Remove 'unlinked' chip
                                             in cook mode for ingredients — we don't care at this
                                             point"*. Right: linkage is an authoring concern, and
                                             mid-cook the only question is what to put in the
                                             bowl. The chip also used a hardcoded `grey-6` /
                                             `grey-8` pair (R-002), so it leaves nothing behind. -->
                                        <template v-if="row.ingredient.stock_item_id === null">
                                            <span class="ingredient-name">{{ row.ingredient.raw_text ?? 'Unlinked ingredient' }}</span>
                                        </template>
                                        <template v-else-if="sessionSwaps.has(row.ingredient.stock_item_id)">
                                            <!-- R-002: no --text-on-secondary token yet, so
                                                 this chip keeps white ink; FU-671 / FU-652. -->
                                            <q-chip
                                                dense
                                                color="secondary"
                                                text-color="white"
                                                :icon="ICONS.swap_horiz"
                                            >
                                                {{ sessionSwaps.get(row.ingredient.stock_item_id)!.substituteName }}
                                            </q-chip>
                                            <span class="text-caption dora-text-muted">
                                                instead of {{ row.ingredient.label ?? row.ingredient.stock_item_name }}
                                            </span>
                                            <BaseButton
                                                variant="icon"
                                                size="sm"
                                                :icon="ICONS.undo"
                                                aria-label="Undo substitute"
                                                @click="clearSwap(row.ingredient.stock_item_id!)"
                                            >
                                                <BaseTooltip>Undo substitute</BaseTooltip>
                                            </BaseButton>
                                        </template>
                                        <template v-else>
                                            <span class="ingredient-name">{{ row.ingredient.label ?? row.ingredient.stock_item_name }}</span>
                                            <span
                                                v-if="row.ingredient.is_optional"
                                                class="text-caption dora-text-muted"
                                            >
                                                (optional)
                                            </span>
                                            <!-- Owner feedback 2026-09-01:
                                                 *"Only show the substitute
                                                 button for items that are
                                                 genuinely in need of it (low
                                                 or out)"*. A swap offered
                                                 against a full jar is an
                                                 affordance answering a
                                                 question nobody asked, on
                                                 every row of the list. -->
                                            <BaseButton
                                                v-if="needsSubstitute(row)"
                                                variant="icon"
                                                size="sm"
                                                :icon="ICONS.swap_horiz"
                                                :aria-label="`Use a substitute for ${row.ingredient.stock_item_name}`"
                                                @click="openSwapPicker(row.ingredient.stock_item_id!, row.ingredient.stock_item_name!)"
                                            >
                                                <BaseTooltip>Use a substitute for this cook</BaseTooltip>
                                            </BaseButton>
                                        </template>
                                    </div>
                                    <!-- Owner 2026-10-15: the note read as a second quantity
                                         (same caption grey, same size). Italic behind a note
                                         glyph, so it reads as an aside about the ingredient. -->
                                    <q-item-label
                                        v-if="row.ingredient.notes"
                                        caption
                                        class="ingredient-note"
                                    >
                                        <q-icon :name="ICONS.notes" size="14px" />
                                        <span>{{ row.ingredient.notes }}</span>
                                    </q-item-label>
                                    <!-- Owner feedback 2026-09-01: *"If there's
                                         a note or conversion info for a
                                         substitute can we display that
                                         meaningfully when a substitute is
                                         picked?"* The picker showed both and
                                         then threw them away on selection —
                                         which is the moment they start
                                         mattering, because you're now holding
                                         the other jar. -->
                                    <q-item-label
                                        v-if="swapHintFor(row.ingredient.stock_item_id)"
                                        caption
                                        class="ingredient-swaphint"
                                    >
                                        <q-icon :name="ICONS.swap_horiz" size="14px" />
                                        {{ swapHintFor(row.ingredient.stock_item_id) }}
                                    </q-item-label>
                                </q-item-section>
                            </q-item>
                        </q-list>
                    </q-card>
                </div>
            </q-expansion-item>

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

        <!-- cook-session substitute picker (temporary; never edits recipe) -->
        <BaseDialog v-model="swapPickerOpen" :title="`Substitute for ${swapForName}`" closable card-style="min-width: 360px; max-width: 520px">
            <q-card-section v-if="loadingSwapOptions" class="text-center q-py-lg">
                <AppSpinner size="32px" />
            </q-card-section>
            <q-card-section v-else-if="swapOptions.length === 0" class="dora-text-muted">
                No substitutes recorded for {{ swapForName }}. Add some on the
                stock item's detail page.
            </q-card-section>
            <q-card-section v-else class="q-pt-sm">
                <div class="text-caption dora-text-muted q-mb-sm">
                    Just for this cook.
                </div>
                <!-- when the substitute carries a note or ratio,
                     surface it next to the chip so the cook has the hint
                     in front of them at swap time. Mirrors the detail-page
                     layout so the same shape reads the same in both
                     places. Ratios are shown as "1 tsp → 1 tsp"; the
                     "from" side is the recipe's ingredient. -->
                <q-list separator>
                    <q-item
                        v-for="opt in swapOptions"
                        :key="opt.stock_item_id"
                        clickable
                        @click="applySwap(opt)"
                    >
                        <q-item-section>
                            <q-item-label>{{ opt.name }}</q-item-label>
                            <q-item-label
                                v-if="formatSubstituteRatio(opt)"
                                caption
                                class="dora-text-secondary"
                            >
                                {{ formatSubstituteRatio(opt) }}
                            </q-item-label>
                            <q-item-label v-if="opt.notes" caption class="dora-text-muted">
                                {{ opt.notes }}
                            </q-item-label>
                        </q-item-section>
                        <q-item-section side>
                            <q-icon :name="ICONS.arrow_forward" class="dora-text-muted" />
                        </q-item-section>
                    </q-item>
                </q-list>
            </q-card-section>
            <template #actions>
                <BaseButton variant="ghost" label="Close" v-close-popup />
            </template>
        </BaseDialog>

        <!-- Finish flow. Owner feedback 2026-09-01: *"The finished cooking
             modal looks genuinely terrible."*

             It was a `q-list` of rows each stacking four things vertically — a
             name, a coloured level chip, a three-way segmented control, and
             then a full-width "Override to a specific level" select beside a
             labelled cart button. Two controls said the same thing in
             different vocabularies (an *action* — down one / out / unchanged —
             and a *destination* level), and the chip was a third reading of
             the same fact.

             So the row is the destination and nothing else: the household's
             stock levels as one segmented control per ingredient, with the
             item's **current** level preselected. Leaving a row alone is
             therefore "unchanged" — which is what actually happens most cooks,
             and the old default of "down one" quietly wrote a level change to
             every ingredient of every recipe you finished. The dot goes with
             the chip and the select: the selected segment already *is* the
             level indicator, and a dot beside it would be the same fact twice
             (owner's call). Name, states and cart sit on one line.

             Owner feedback 2026-09-03: *"The level picker looks horrible,
             let's move to showing the stock level picker from the overview
             rows. Would look better and consistent."* The segmented control
             was a *second vocabulary* for a question the app already asks one
             way everywhere else — the coloured square + level menu on a stock
             row. It also scaled badly: a household with five levels put five
             labelled segments on every ingredient line. Same control now,
             extracted as `StockLevelPicker`. The level *name* the segments
             used to print comes back as the row's own caption, because a
             colour alone is not a legible answer in a list you read top to
             bottom. -->
        <BaseDialog v-model="finishDialogOpen" title="Finished cooking?" closable card-style="min-width: 360px; max-width: 720px">
            <q-card-section v-if="finishRows.length === 0" class="dora-text-muted">
                This recipe has no ingredients to adjust.
            </q-card-section>
            <q-card-section v-else class="q-pt-none">
                <div class="text-body2 q-mb-sm">
                    Update stock levels of the ingredients you used.
                </div>
                <div class="finish-list">
                    <div
                        v-for="row in finishRows"
                        :key="row.targetStockItemId"
                        class="finish-row"
                    >
                        <StockLevelPicker
                            :level-id="row.selectedLevelId"
                            :label="`Stock level for ${row.targetName}`"
                            @select="row.selectedLevelId = $event"
                        />
                        <div class="finish-row__name">
                            <div>{{ row.targetName }}</div>
                            <div class="finish-row__level text-caption">
                                {{ levelNameFor(row.selectedLevelId) }}
                            </div>
                        </div>
                        <!-- Owner feedback 2026-09-03: *"incorrect old shopping
                             cart button in use… it doesn't add to a list when
                             one actually does exist, and it tells me to set up
                             a primary list"*. It was a hand-rolled button
                             reading `quickAddTargetListId`, which is non-null
                             only when exactly ONE draft list exists — every
                             other case fell into a bail-out toast naming
                             "primary lists", a concept retired in C-7 Chunk 2.
                             The shared `AddToListButton` is the sanctioned
                             path: it resolves the target (prompting on 2+
                             drafts), shows on-list state, and toggles back
                             off. -->
                        <AddToListButton
                            variant="row"
                            :stock-item-id="row.targetStockItemId"
                        />
                    </div>
                </div>
            </q-card-section>
            <!-- The meal count only exists in a batch-cooking household
                 (FU-615 — `batch_features_enabled`). In a "fresh" household
                 there is no pool to add to, so the field was asking a question
                 with no consequence. Owner: *"fix the wording (I previously in
                 some commit got it reworded from pool because I hated that
                 wording)"* — so this says leftovers, and it is a stepper
                 rather than a bare number field, which is the shape the rest
                 of the app uses for a small count you nudge.

                 Owner feedback 2026-09-03: *"could be styled consistently with
                 how this sort of input is done in the meal planner"*. The
                 meal-plan builder's servings control is the compact inline
                 shape; this was a bordered 44px pill, which is the right
                 weight for cook mode's header (wet hands, mid-cook) but not
                 for a settled row inside a dialog. Both are now the shared
                 `NumberStepper` and differ only by which shape they ask for. -->
            <q-card-section v-if="batchEnabled" class="q-pt-md">
                <div class="finish-meals">
                    <div class="finish-meals__copy">
                        <div class="text-body2">Extra servings for later</div>
                        <div class="text-caption dora-text-muted">
                            Leave at 0 if you ate the lot.
                        </div>
                    </div>
                    <NumberStepper
                        v-model="finishMealsCooked"
                        :min="0"
                        decrement-label="One fewer serving"
                        increment-label="One more serving"
                    >
                        <BaseTooltip>Servings kept for later</BaseTooltip>
                    </NumberStepper>
                </div>
            </q-card-section>
            <template #actions>
                <BaseButton variant="ghost" label="Cancel" @click="finishDialogOpen = false" />
                <BaseButton variant="primary" label="Done" :loading="finishing" @click="confirmFinish" />
            </template>
        </BaseDialog>
    </q-page>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import AppSpinner from 'src/components/AppSpinner.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import AddToListButton from 'src/components/AddToListButton.vue';
    import NumberStepper from 'src/components/NumberStepper.vue';
    import StockLevelPicker from 'src/components/stock/StockLevelPicker.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import CookStepProgress from 'src/components/recipes/CookStepProgress.vue';
    import CookImageView from 'src/components/recipes/CookImageView.vue';
    import CookNavRow from 'src/components/recipes/CookNavRow.vue';
    import { formatTimer, useCookTimer } from 'src/composables/useCookTimer';
    import CookNotesSection from 'src/components/recipes/CookNotesSection.vue';
    import { useQuasar } from 'quasar';
    import { useCookingPolicy } from 'src/composables/useCookingPolicy';
    import { formatQuantity } from 'src/helpers/formatQuantity';
    import { formatSubstituteRatio } from 'src/helpers/substituteRatio';
    import { scaleQuantity } from 'src/helpers/scaleQuantity';
    // extracted browser-speech composables. Cook mode opts into
    // continuous listening so the user can keep their hands in the
    // mixing bowl while saying "next" / "start timer".
    import { useSpeechOutput } from 'src/composables/useSpeechOutput';
    import { useVoiceInput } from 'src/composables/useVoiceInput';
    import { useWakeLock } from 'src/composables/useWakeLock';
    import type { Recipe } from 'src/models/recipe';
    import type { StockItem } from 'src/models/stockItem';
    import type { Substitute } from 'src/models/stockItemDetail';
    import RecipeApiService from 'src/services/api/recipeApiService';
    import StockItemApiService from 'src/services/api/stockItemApiService';
    import { useAuthStore } from 'src/stores/authStore';
    import { useLocationStore } from 'src/stores/locationStore';
    import { useRecipeStore } from 'src/stores/recipeStore';
    import { useRecipeVocabStore } from 'src/stores/recipeVocabStore';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
    import { useShortcut } from 'src/composables/useShortcut';
    import { useRoute, useRouter } from 'vue-router';

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
    const stockItemApi = new StockItemApiService();
    const authStore = useAuthStore();

    // hold the screen awake for the whole cook session (both the
    // running timer and the read-along steps assume a visible screen the
    // user isn't tapping). Released automatically on unmount.
    const wakeLockWanted = ref(true);
    useWakeLock(wakeLockWanted);


    // Resolve location_id → breadcrumb names using the locations tree.
    // We hit the location store lazily on mount so cook mode keeps working
    // even when the tree hasn't been opened yet.
    function breadcrumbFor(locationId: string): string[] {
        return locationStore.breadcrumb(locationId);
    }

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

    /** Owner feedback 2026-08-27 — *"how does cook mode pick which steps it
     *  will follow? I've got all 3 filled out and it's picking structured when
     *  I've got free text picked on the recipe view."*
     *
     *  It picked structured because it only ever branched on `'image'` and
     *  otherwise preferred `steps[]` whenever the array was non-empty. Mode
     *  switching is deliberately **non-destructive** (all three payloads coexist
     *  — see `useRecipeEditor`), so "structured steps exist" says nothing about
     *  which face the user chose. `steps_mode` is the single source of truth for
     *  that (R-003), and cook mode now reads it rather than re-deriving an
     *  answer from the payloads.
     *
     *  The one fallback that remains is honest rather than a guess: a recipe in
     *  `structured` mode with an empty `steps[]` has nothing to render, so we
     *  fall back to the free-text split instead of showing a single
     *  "No instructions provided." card over instructions that do exist. */
    const useStructuredSteps = computed(
        () => recipe.value?.steps_mode === 'structured'
            && (recipe.value?.steps?.length ?? 0) > 0,
    );

    // session-only headcount. Seeds from the install-wide
    // `household_headcount` (FU-615 — set in Settings → System → Cooking,
    // read via /api/health) when present, otherwise the recipe's own
    // `servings`. Never writes back to the saved recipe — matches the
    // B8-substitute discipline of "this cook only".
    const { householdHeadcount, batchEnabled } = useCookingPolicy();
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

    /** Format a recipe ingredient's quantity for display, rescaled to the
     *  current headcount and routed through `formatQuantity` for unit
     *  spacing. The two helpers are deliberately separate — `scaleQuantity`
     *  owns the rounding (DEC-4), `formatQuantity` owns the spacing (DEC-3).
     *  Returns an empty string when both quantity and unit are null. */
    function displayQuantity(quantity: number | null | undefined, unit: string | null | undefined): string {
        const baseServings = recipe.value?.servings ?? null;
        const scaled = scaleQuantity(quantity, baseServings, cookingFor.value, unit);
        return formatQuantity(scaled, unit);
    }


    // ── P2-13 voice (extracted into composables) ────────────────────────
    // The user's persisted preference seeds the local toggle; subsequent
    // in-page taps flip the session view and persist back via authStore
    // (declared above with the other stores).
    const speechOut = useSpeechOutput();
    const speechEnabled = ref<boolean>(
        authStore.currentUser?.voice_output_enabled ?? false,
    );
    /** Below the phone breakpoint the voice controls go icon-only; above it
     *  Sous Chef gets its label back (owner feedback 2026-08-28: *"I prefer the
     *  sous chef big button for desktop, the icon only version can stay for
     *  mobile only"*). Reactive via Quasar's Screen plugin, activated in
     *  `boot/quasarScreen.ts`. */
    const isPhone = computed(() => $q.screen.lt.sm);
    const sousChefVariant = computed(() => {
        if (isPhone.value) return speechEnabled.value ? 'filled-icon' : 'icon';
        return speechEnabled.value ? 'primary' : 'secondary';
    });

    /** Owner feedback 2026-09-03 — the three step buttons have to share one
     *  row on a phone. `size="lg"` is where the width goes: Quasar writes it as
     *  an INLINE font-size, so no stylesheet rule can shrink it (a CSS
     *  `font-size` in the media query below was tried, measured, and found
     *  inert). The framework-level answer is to hand it a different size, not
     *  to fight the inline style with `!important`. */
    const navButtonSize = computed(() => (isPhone.value ? 'md' : 'lg'));

    const voiceInput = useVoiceInput({
        continuous: true,
        // Cook mode bypasses the chat draft entirely — the transcript is
        // interpreted as a command and dispatched immediately. Wrapping
        // the dispatcher in onFinal keeps the composable agnostic of
        // cook-mode-specific verbs.
        onFinal(text) {
            handleVoiceCommand(text);
        },
        // FU-723 — don't let the recognizer re-open the mic while Dora is
        // mid-utterance; on Android that steals audio focus and can clip the
        // front of what she's saying. Barge-in is unaffected: an already-open
        // mic keeps hearing "next" over the top of her.
        deferRestartWhile: () => speechOut.busy.value,
    });
    const listening = computed(() => voiceInput.listening.value);
    const speechRecognitionAvailable = computed(() => voiceInput.available.value);

    const {
        remaining: timerRemaining,
        running: timerRunning,
        total: timerTotal,
        progress: timerProgress,
        start: startTimer,
        pause: pauseTimer,
        reset: resetTimer,
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

    // Sous Chef voice command list, surfaced via the help
    // popover so users discover the verbs without trial and error.
    const sousChefCommands: ReadonlyArray<{ label: string; does: string }> = [
        { label: '"Next"', does: 'advance to the next step' },
        { label: '"Previous" / "Back"', does: 'go to the previous step' },
        { label: '"Repeat"', does: 'read the current step again' },
        // Owner feedback 2026-09-03 — the three added verbs. "Ingredients"
        // and "Tools" answer the two questions you have with both hands full
        // and the panel scrolled off the bottom of a phone; "Stop" is the
        // one word anybody says to something that is talking at them.
        { label: '"Ingredients"', does: "read this step's ingredients aloud" },
        { label: '"Tools"', does: "read this step's tools aloud" },
        { label: '"Stop"', does: 'stop Sous Chef talking, or pause a running timer' },
        { label: '"Start timer"', does: 'start the step timer (uses detected duration, or 5 min)' },
        { label: '"Pause timer"', does: 'pause the running timer' },
        { label: '"Reset timer"', does: 'clear the timer' },
        { label: '"Exit"', does: 'leave cook mode' },
    ];

    // step model. Structured recipes (Chunk 4) carry a
    // flat `recipe.steps[]` with optional parent_step_id for one level of
    // sub-steps and per-step ingredient/tool references; we flatten that to
    // a linear sequence (top, its subs, next top, …) for navigation.
    // Unstructured recipes fall back to splitting `instructions` on newline.
    type CookStep = {
        text: string;
        hint: string | null;
        ingredientIds: string[]; // references RecipeIngredient.recipe_ingredient_id
        toolIds: string[];       // references Tool.tool_id
        isSubStep: boolean;
        // name of the section this step belongs to (the
        // sub-step inherits its parent's section so the header doesn't
        // flicker mid-group). Null when the step is unsectioned.
        sectionName: string | null;
        // Owner feedback 2026-09-01 — the timer the cook *declared* on this
        // step, in minutes. Only a structured step can carry one; free-text
        // and photo faces leave it null and fall back to the text sniff.
        timerMinutes: number | null;
    };

    const cookSteps = computed<CookStep[]>(() => {
        const structured = recipe.value?.steps ?? [];
        const sectionById = new Map(
            (recipe.value?.sections ?? []).map((s) => [s.section_id, s]),
        );
        const sectionName = (id: string | null) =>
            id ? (sectionById.get(id)?.name ?? null) : null;
        // `useStructuredSteps`, not `structured.length > 0` — the recipe's
        // chosen `steps_mode` decides, not which payloads happen to be filled in.
        if (useStructuredSteps.value) {
            const flat: CookStep[] = [];
            const tops = structured
                .filter((s) => s.parent_step_id === null)
                .sort((a, b) => a.sequence - b.sequence);
            for (const top of tops) {
                flat.push({
                    text: top.text,
                    hint: top.hint,
                    ingredientIds: [...top.ingredient_ids],
                    toolIds: [...top.tool_ids],
                    isSubStep: false,
                    sectionName: sectionName(top.section_id),
                    timerMinutes: top.timer_minutes ?? null,
                });
                const subs = structured
                    .filter((s) => s.parent_step_id === top.step_id)
                    .sort((a, b) => a.sequence - b.sequence);
                for (const sub of subs) {
                    flat.push({
                        text: sub.text,
                        hint: sub.hint,
                        ingredientIds: [...sub.ingredient_ids],
                        toolIds: [...sub.tool_ids],
                        isSubStep: true,
                        sectionName: sectionName(top.section_id),
                        timerMinutes: sub.timer_minutes ?? null,
                    });
                }
            }
            return flat;
        }
        // Unstructured fallback — same shape, empty refs.
        const raw = recipe.value?.instructions;
        if (!raw) {
            return [{
                text: 'No instructions provided.',
                hint: null,
                ingredientIds: [],
                toolIds: [],
                isSubStep: false,
                sectionName: null,
                timerMinutes: null,
            }];
        }
        const parts = raw
            .split(/\r?\n+/)
            .map((s) => s.replace(/^\s*\d+[.)]\s*/, '').trim())
            .filter((s) => s.length > 0);
        const lines = parts.length > 0 ? parts : [raw];
        return lines.map((t) => ({
            text: t,
            hint: null,
            ingredientIds: [],
            toolIds: [],
            isSubStep: false,
            sectionName: null,
            timerMinutes: null,
        }));
    });

    // Linear step text (consumed by the speech / nav / timer code that
    // existed before structured steps landed).
    const steps = computed(() => cookSteps.value.map((s) => s.text));

    const currentStep = computed(() => steps.value[currentStepIndex.value] ?? '');
    const currentStepObject = computed<CookStep | null>(
        () => cookSteps.value[currentStepIndex.value] ?? null,
    );
    type IngredientRow = { ingredient: Recipe['ingredients'][number]; stockItem: StockItem | null };
    const ingredientRows = computed<IngredientRow[]>(() =>
        (recipe.value?.ingredients ?? []).map((ingredient) => ({
            ingredient,
            stockItem: ingredient.stock_item_id
                ? stockItemStore.byId.get(ingredient.stock_item_id) ?? null
                : null,
        })),
    );

    // group ingredients by their *base* stock location (the
    // top-level node of the breadcrumb). Sub-areas collapse into their parent
    // — "Pantry > Spice Rack" reads as "Pantry" — keeping the mid-cook view
    // calm. Ingredients with no location land in a final "No location" group.
    //
    // when the recipe defines named sections, sections win as
    // the top-level grouping (their semantic intent — "this is the sauce" —
    // is stronger than where the ingredient lives). Falls back to location
    // grouping for flat recipes so existing recipes render unchanged.
    type IngredientGroup = { key: string; label: string; rows: IngredientRow[] };
    const ingredientGroups = computed<IngredientGroup[]>(() => {
        const sections = recipe.value?.sections ?? [];
        if (sections.length > 0) {
            // Section grouping. Order follows `sequence` (server already
            // sorted); unsectioned ingredients drop into "Main" at the end.
            const sectionById = new Map(sections.map((s) => [s.section_id, s]));
            const groups = new Map<string, IngredientGroup>();
            const orderedKeys: string[] = [];
            const ensure = (key: string, label: string) => {
                if (!groups.has(key)) {
                    groups.set(key, { key, label, rows: [] });
                    orderedKeys.push(key);
                }
                return groups.get(key)!;
            };
            for (const s of sections) {
                ensure(`s:${s.section_id}`, s.name);
            }
            for (const row of ingredientRows.value) {
                const sid = row.ingredient.section_id;
                const sec = sid ? sectionById.get(sid) : null;
                if (sec) {
                    ensure(`s:${sec.section_id}`, sec.name).rows.push(row);
                } else {
                    ensure('__main__', 'Main').rows.push(row);
                }
            }
            return orderedKeys
                .map((k) => groups.get(k)!)
                .filter((g) => g.rows.length > 0);
        }
        const groups = new Map<string, IngredientGroup>();
        const orderedKeys: string[] = [];
        for (const row of ingredientRows.value) {
            const locId = row.ingredient.stock_location_id;
            let key: string;
            let label: string;
            if (locId) {
                const breadcrumb = breadcrumbFor(locId);
                label = breadcrumb[0] ?? row.ingredient.stock_location_name ?? 'Other';
                key = label;
            } else {
                key = '__none__';
                label = 'No location';
            }
            if (!groups.has(key)) {
                groups.set(key, { key, label, rows: [] });
                orderedKeys.push(key);
            }
            groups.get(key)!.rows.push(row);
        }
        // Push the "No location" bucket to the bottom so the cook reads the
        // located groups in order first.
        const ordered = orderedKeys.map((k) => groups.get(k)!).filter(Boolean);
        ordered.sort((a, b) => {
            if (a.key === '__none__') return 1;
            if (b.key === '__none__') return -1;
            return 0;
        });
        return ordered;
    });

    // per-step highlight. Structured recipes use the step's
    // own `ingredient_ids` / `tool_ids` lists; unstructured recipes fall
    // back to matching ingredient names inside the step text (same logic
    // as the pre-Chunk-5 auto-mark behaviour, repurposed for visual
    // highlight rather than tick state).
    const highlightedIngredientIds = computed<Set<string>>(() => {
        const step = currentStepObject.value;
        if (!step) return new Set();
        if (step.ingredientIds.length > 0) {
            return new Set(step.ingredientIds);
        }
        // Unstructured fallback — text match.
        const text = step.text.toLowerCase();
        const matched = new Set<string>();
        for (const ing of recipe.value?.ingredients ?? []) {
            // Chunk 4 — unlinked ingredients have no stock_item_name.
            // Fall back to raw_text for matching so paste-imported
            // recipes still get highlighted where possible.
            // A recipe that calls its cheese "cheddar" says "cheddar" in
            // its steps, so the chosen name is tried as well as the item's.
            const names = [ing.label, ing.stock_item_name ?? ing.raw_text];
            if (names.some((n) => n && text.includes(n.toLowerCase()))) {
                matched.add(ing.recipe_ingredient_id);
            }
        }
        return matched;
    });

    const highlightedToolIds = computed<Set<string>>(() => {
        const step = currentStepObject.value;
        if (!step) return new Set();
        return new Set(step.toolIds);
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
    // Picking a substitute here applies ONLY to this cook: it never edits the
    // saved recipe. It changes what gets decremented / added-to-list on finish.
    // Keyed by the recipe ingredient's original stock_item_id.
    type SessionSwap = {
        substituteId: string;
        substituteName: string;
        /** Owner feedback 2026-09-01 — the conversion ("1 tsp → 1 tsp") and
         *  the free-text note the substitute was recorded with. Both were
         *  shown in the picker and then dropped on selection, which is the
         *  moment they start mattering. Null when the substitute carries
         *  neither. */
        hint: string | null;
    };
    const sessionSwaps = ref(new Map<string, SessionSwap>());
    const swapPickerOpen = ref(false);
    const swapForId = ref<string | null>(null);
    const swapForName = ref('');
    const swapOptions = ref<Substitute[]>([]);
    const loadingSwapOptions = ref(false);

    async function openSwapPicker(stockItemId: string, name: string) {
        swapForId.value = stockItemId;
        swapForName.value = name;
        swapOptions.value = [];
        swapPickerOpen.value = true;
        loadingSwapOptions.value = true;
        try {
            swapOptions.value = await stockItemApi.getSubstitutesAsync(stockItemId);
        } catch {
            swapOptions.value = [];
        } finally {
            loadingSwapOptions.value = false;
        }
    }
    function applySwap(substitute: Substitute) {
        if (!swapForId.value) return;
        const ratio = formatSubstituteRatio(substitute);
        const note = substitute.notes?.trim() || null;
        sessionSwaps.value.set(swapForId.value, {
            substituteId: substitute.stock_item_id,
            substituteName: substitute.name,
            hint: [ratio, note].filter(Boolean).join(' · ') || null,
        });
        sessionSwaps.value = new Map(sessionSwaps.value);
        swapPickerOpen.value = false;
    }

    /** The swapped-in substitute's conversion + note, for the ingredient row.
     *  Keyed by the *original* ingredient's stock item, which is how
     *  `sessionSwaps` is keyed. */
    function swapHintFor(stockItemId: string | null): string | null {
        if (!stockItemId) return null;
        return sessionSwaps.value.get(stockItemId)?.hint ?? null;
    }

    /** Owner feedback 2026-09-01 — a substitute is worth offering when the
     *  thing you'd substitute *for* is low or out. Anything already stocked
     *  gets no button: the swap is still reachable from the stock item, and
     *  a row per ingredient offering to replace a full jar is noise on the
     *  one screen that should be calm.
     *
     *  An ingredient whose stock item hasn't loaded (or isn't linked) reads as
     *  "no reason to think it needs one" — the same conservative default the
     *  rest of the page takes. */
    function needsSubstitute(row: IngredientRow): boolean {
        return row.stockItem?.needs_restock === true;
    }
    function clearSwap(stockItemId: string) {
        sessionSwaps.value.delete(stockItemId);
        sessionSwaps.value = new Map(sessionSwaps.value);
    }

    /** The old whole-app behaviour: read a duration out of the step's prose.
     *  Kept, because it is the only thing a free-text or photo method can
     *  offer — there is nowhere on a line of prose to record "this step is
     *  timed". Now a *fallback*, not the mechanism.
     */
    const sniffedTimerMinutes = computed<number | null>(() => {
        const text = currentStep.value.toLowerCase();
        const minMatch = text.match(/(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|m\b)/);
        if (minMatch) return parseFloat(minMatch[1]!);
        const hourMatch = text.match(/(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h\b)/);
        if (hourMatch) return parseFloat(hourMatch[1]!) * 60;
        return null;
    });

    /** Owner feedback 2026-09-01: *"How does the timer function get added? Is
     *  it guessing? … for structured I feel a tickable box option should be
     *  added"*. A structured step can now declare `timer_minutes`, and a
     *  declared timer always wins over the sniff — including where the step's
     *  wording disagrees with it ("reduce by half, about 20 minutes" on a step
     *  the cook actually timed at 25).
     */
    const timerIsDeclared = computed(() => currentStepObject.value?.timerMinutes != null);

    const stepTimerMinutes = computed<number | null>(
        () => currentStepObject.value?.timerMinutes ?? sniffedTimerMinutes.value,
    );

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

    function speak(text: string) {
        if (!speechEnabled.value) return;
        speechOut.speak(text);
    }

    function speakCurrent() {
        speak(currentStep.value);
    }

    async function toggleSpeech() {
        const next = !speechEnabled.value;
        speechEnabled.value = next;
        if (next) speakCurrent();
        else speechOut.cancel();
        // Persist the preference back to the user row. Silent failure
        // is fine — the session-local toggle still applies.
        try {
            await authStore.updateMeAsync({ voice_output_enabled: next });
        } catch {
            /* leave local state as-is */
        }
    }

    function nextStep() {
        resetTimer();
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
            resetTimer();
            currentStepIndex.value -= 1;
        }
    }

    function goToStep(idx: number) {
        resetTimer();
        currentStepIndex.value = idx;
    }

    // ── Finish flow ──────────────────────────────────────────────────────
    // Owner feedback 2026-09-01 — a row is now just "which level is this at
    // now?", with the item's current level preselected. The old shape carried
    // an *action* (`down_one` / `out` / `unchanged`) **and** a destination
    // override select **and** a colour chip: three vocabularies for one fact,
    // which is what made the modal read as packed. Selecting the level the
    // item is already on is the no-op, so "unchanged" needs no option of its
    // own — and it is the default, where the old flow defaulted to writing a
    // level drop onto every ingredient of every recipe you finished.
    type FinishRow = {
        // After session swaps: the stock item whose level we actually
        // touch on finish (the substitute, not the original recipe item).
        targetStockItemId: string;
        targetName: string;
        /** Where the item sits now — the write is skipped when the selection
         *  still matches this. `undefined` when the stock item hasn't loaded. */
        currentLevelId: string | undefined;
        selectedLevelId: string | undefined;
    };
    const finishDialogOpen = ref(false);
    const finishing = ref(false);
    const finishMealsCooked = ref<number>(0);
    const finishRows = ref<FinishRow[]>([]);

    /** The selected level's name, printed under the ingredient name. The
     *  picker itself is a colour swatch, and a colour on its own is not an
     *  answer in a list you read row by row — the segments it replaced said
     *  the word, so the row has to. */
    function levelNameFor(levelId: string | undefined): string {
        if (!levelId) return 'No level set';
        return stockLevelStore.levelById.get(levelId)?.name ?? '';
    }

    function buildFinishRows(): FinishRow[] {
        // finish ranges over every ingredient on the recipe,
        // applying any session swaps. The user no longer ticks ingredients
        // mid-cook; cooking the recipe implies using all of them.
        //
        // IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — unlinked ingredients
        // (stock_item_id === null) can't participate in the finish flow
        // (no stock item to decrement). They're skipped here; the cook
        // still succeeds for the linked ingredients.
        const rows: FinishRow[] = [];
        for (const ing of recipe.value?.ingredients ?? []) {
            if (ing.stock_item_id === null) continue;
            const swap = sessionSwaps.value.get(ing.stock_item_id);
            const targetId = swap?.substituteId ?? ing.stock_item_id;
            const item = stockItemStore.byId.get(targetId);
            const fallbackName = swap?.substituteName ?? ing.stock_item_name ?? ing.raw_text ?? '';
            rows.push({
                targetStockItemId: targetId,
                targetName: item?.name ?? fallbackName,
                currentLevelId: item?.stock_level_id,
                selectedLevelId: item?.stock_level_id,
            });
        }
        return rows;
    }

    function openFinish() {
        pauseTimer();
        finishRows.value = buildFinishRows();
        finishDialogOpen.value = true;
    }

    async function confirmFinish() {
        finishing.value = true;
        try {
            // Fan out per-row level updates with fail-soft semantics: one
            // failed item doesn't take down the rest of the batch.
            // tag each finish-driven level change as a
            // `cook` consumption so the server persists a ConsumptionEvent
            // (the depletion leg of the loop). The server only records one
            // when the level actually drops, so an "unchanged"/manual-up row
            // that slips through carries no false consumption signal.
            const recipeId = recipe.value?.recipe_id;
            const updates = finishRows.value
                .map((row) => {
                    // A row still sitting on the level it arrived at is the
                    // "unchanged" case — no write, and so no ConsumptionEvent.
                    const target = row.selectedLevelId;
                    if (!target || target === row.currentLevelId) return null;
                    return {
                        stock_item_id: row.targetStockItemId,
                        stock_level_id: target,
                        consumption_source: 'cook' as const,
                        ...(recipeId ? { consumption_recipe_id: recipeId } : {}),
                    };
                })
                .filter((u): u is NonNullable<typeof u> => u !== null);
            const settled = await Promise.allSettled(
                updates.map((u) => stockItemStore.updateStockLevelAsync(u)),
            );
            const failed = settled.filter((r) => r.status === 'rejected').length;
            if (failed > 0) {
                // Fail-soft is right for the batch, silent is not: say which
                // part didn't land before the celebration (finalisation 04-R5).
                $q.notify({
                    type: 'negative',
                    message: `Couldn't update ${failed} stock level${failed === 1 ? '' : 's'}.`,
                    caption: 'Check them on the Stock page.',
                });
            }

            let mealsCooked = 0;
            if (recipe.value) {
                mealsCooked = Math.max(0, Math.floor(finishMealsCooked.value || 0));
                await recipeStore.cookAsync(recipe.value.recipe_id, mealsCooked);
            }

            // Celebration. Copy reads off `meals_cooked` per L337 / DEC-5.
            $q.notify({
                type: 'positive',
                timeout: 4000,
                // A fresh household never sets aside meals, so "all eaten" only
                // makes sense where saving some was an option.
                message: !batchEnabled.value
                    ? 'Enjoy your meal.'
                    : mealsCooked === 0
                        ? 'All eaten. Hope it was good.'
                        : `You saved ${mealsCooked} meal${mealsCooked === 1 ? '' : 's'}.`,
                icon: ICONS.check_circle,
            });
            finishDialogOpen.value = false;
            exitCookMode();
        } finally {
            finishing.value = false;
        }
    }

    function exitCookMode() {
        pauseTimer();
        // Through the composable (R-003) so a Piper `<audio>` stops with the
        // Web Speech voice — a raw `speechSynthesis.cancel()` left it playing
        // until unmount (finalisation 04-R3).
        speechOut.cancel();
        stopListening();
        // L298 — exit returns to the recipe's detail page (where the user
        // came from), not all the way back to the cookbook overview.
        const id = route.params.id as string;
        void router.push(id ? `/cookbook/${id}` : '/cookbook');
    }

    // ── P2-13 voice command dispatcher ──────────────────────────────────
    // Called by `useVoiceInput.onFinal` whenever the browser hands us a
    // finalised utterance. Each branch maps to a hands-free action that
    // mirrors a visible button in the UI — we deliberately don't expose
    // voice-only side effects, so the user can always verify what we
    // think they said by spotting the corresponding click.
    /** Speak an *answer* to something the cook asked out loud.
     *
     *  Deliberately not routed through `speak()`, which honours the Sous Chef
     *  narration toggle: that toggle governs whether Dora reads each step
     *  *unbidden*, and a direct spoken question deserves a spoken answer
     *  whichever way it is set (the mic is independent of narration by
     *  design — see the mic tooltip). Where no voice can produce sound at all
     *  the answer falls back to a toast, so the command is never a no-op.
     *  R-078: the message names the real condition rather than a generic
     *  "nothing to say". */
    function speakAnswer(text: string) {
        if (speechOut.available.value) {
            speechOut.speak(text);
            return;
        }
        $q.notify({ type: 'info', message: text, icon: ICONS.record_voice_over });
    }

    /** The name to *say* for an ingredient: the substitute when one is swapped
     *  in for this cook, because that is what's going in the bowl. */
    function spokenIngredientName(ingredient: Recipe['ingredients'][number]): string {
        const stockItemId = ingredient.stock_item_id;
        const swap = stockItemId !== null ? sessionSwaps.value.get(stockItemId) : undefined;
        if (swap) return swap.substituteName;
        return ingredient.label ?? ingredient.stock_item_name ?? ingredient.raw_text ?? 'an unnamed ingredient';
    }

    /** "Ingredients" — read the current step's ingredients, quantities scaled
     *  to the headcount exactly as the panel shows them. */
    function speakStepIngredients() {
        const recipeIngredients = recipe.value?.ingredients ?? [];
        if (recipeIngredients.length === 0) {
            speakAnswer("This recipe doesn't list any ingredients.");
            return;
        }
        const ids = highlightedIngredientIds.value;
        const rows = recipeIngredients.filter((ing) => ids.has(ing.recipe_ingredient_id));
        if (rows.length === 0) {
            speakAnswer('No ingredients are linked to this step.');
            return;
        }
        const parts = rows.map((ing) => {
            const quantity = displayQuantity(ing.quantity, ing.unit);
            const name = spokenIngredientName(ing);
            const optional = ing.is_optional ? ', optional' : '';
            return quantity ? `${quantity} ${name}${optional}` : `${name}${optional}`;
        });
        speakAnswer(`For this step: ${parts.join('; ')}.`);
    }

    /** "Tools" — same shape as the ingredients answer. Only a structured step
     *  carries tool links, so a free-text method says so rather than guessing
     *  (there is no text-match fallback for tools — see `highlightedToolIds`). */
    function speakStepTools() {
        if (recipeTools.value.length === 0) {
            speakAnswer("This recipe doesn't list any tools.");
            return;
        }
        const ids = highlightedToolIds.value;
        const names = recipeTools.value.filter((tool) => ids.has(tool.tool_id)).map((tool) => tool.name);
        if (names.length === 0) {
            speakAnswer('No tools are linked to this step.');
            return;
        }
        speakAnswer(`For this step: ${names.join('; ')}.`);
    }

    /** "Stop" — the one word people say to a thing that is talking at them.
     *
     *  It used to exit cook mode (grouped with "exit"/"quit"), which is the
     *  most destructive reading of an ambiguous word: say it to shut Dora up
     *  mid-sentence and you lose your place in the recipe. Owner feedback
     *  2026-09-03 fixes the mapping — stop talking, or stop the timer. Speech
     *  wins when both are live, so a second "stop" gets the timer; exiting now
     *  needs "exit" / "quit", which nobody says by accident. */
    function handleStopCommand() {
        if (speechOut.busy.value) {
            speechOut.cancel();
        } else if (timerRunning.value) {
            pauseTimer();
        }
        // Nothing talking and no timer running — nothing to stop, and
        // silence is the right answer (see the tail comment below).
    }

    function handleVoiceCommand(rawTranscript: string) {
        const transcript = rawTranscript.toLowerCase();
        if (/(^|\s)(next|forward|continue)(\s|$)/.test(transcript)) {
            nextStep();
        } else if (/(^|\s)(previous|back|go back)(\s|$)/.test(transcript)) {
            prevStep();
        } else if (/(^|\s)(repeat|again|say it again)(\s|$)/.test(transcript)) {
            speakCurrent();
        } else if (/(^|\s)(ingredients?|what do i need)(\s|$)/.test(transcript)) {
            speakStepIngredients();
        } else if (/(^|\s)(tools?|equipment|what tools)(\s|$)/.test(transcript)) {
            speakStepTools();
        } else if (/(^|\s)(start timer|begin timer|set timer)(\s|$)/.test(transcript)) {
            // "start timer" → use whatever duration the current step
            // implies; fall back to 5 minutes when nothing's detectable.
            const minutes = stepTimerMinutes.value ?? 5;
            startTimer(minutes * 60);
            if (speechEnabled.value) speak(`Timer set for ${minutes} minutes.`);
        } else if (/(^|\s)(pause timer|stop timer)(\s|$)/.test(transcript)) {
            pauseTimer();
            if (speechEnabled.value) speak('Timer paused.');
        } else if (/(^|\s)(reset timer|clear timer)(\s|$)/.test(transcript)) {
            resetTimer();
            if (speechEnabled.value) speak('Timer reset.');
        } else if (/(^|\s)(exit|quit)(\s|$)/.test(transcript)) {
            exitCookMode();
        } else if (/(^|\s)(stop|quiet|hush|shush|be quiet)(\s|$)/.test(transcript)) {
            handleStopCommand();
        }
        // Unrecognised commands are deliberately ignored — silence is
        // less annoying than a "I didn't understand that" interjection
        // every time the user talks to someone else in the kitchen.
    }

    function stopListening() { voiceInput.stop(); }
    function toggleListening() { voiceInput.toggle(); }

    watch(currentStepIndex, () => {
        if (speechEnabled.value) speakCurrent();
    });

    // Step 1 used to be silent. `currentStepIndex` starts at 0 and the watcher
    // above only fires on *change*, so entering cook mode with Sous Chef already
    // on announced nothing until you pressed Next — the one step you'd most want
    // read to you while your hands are busy. `immediate: true` on that watcher
    // wouldn't do it either: the steps arrive from an async fetch in onMounted,
    // so at mount `currentStep` is still ''. Fire off the arrival of the steps
    // instead, once, and only if we're still sitting on the first one (a fast
    // tap to step 2 before the fetch lands must not be talked over).
    let announcedFirstStep = false;
    watch(steps, (next) => {
        if (announcedFirstStep || next.length === 0) return;
        announcedFirstStep = true;
        if (speechEnabled.value && currentStepIndex.value === 0) speakCurrent();
    }, { immediate: true });

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
        announcedFirstStep = false;
        finishDialogOpen.value = false;
        try {
            await recipeStore.ensureLoadedAsync();
            // the list endpoint doesn't return `steps[]`
            // (only `has_structured_steps`), and cook mode needs structured
            // steps for per-step highlights / hints. Always fetch detail so
            // `recipe.value.steps` is present when the recipe has them.
            recipe.value = await recipeApiService.getAsync(recipeId);
        } catch {
            recipe.value = null;
        } finally {
            loading.value = false;
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
    const overlayOpen = () => finishDialogOpen.value || swapPickerOpen.value;
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
        speechOut.cancel();
    });
</script>

<style scoped lang="scss">
    .cook-mode {
        max-width: 900px;
        margin: 0 auto;
    }
    .step-card {
        min-height: 200px;
    }
    .step-text {
        line-height: 1.4;
        font-weight: 400;
    }
    // Owner feedback 2026-09-01: *"should we aim for consistency across the 3
    // sections ingredients, tools and steps?"* — yes. One header treatment and
    // one card/row treatment, shared by all three, so the panels read as three
    // views of the same recipe. The per-section counts ("6 total") are gone
    // with them: the list is right there, and the number was the only thing
    // making the three headers different shapes.
    .cook-section__head {
        font-size: var(--font-size-md);
        font-weight: 600;
    }
    .cook-section__title {
        color: var(--text-primary);
    }
    // Owner feedback 2026-09-13: *"Add some gap between ingredients, tools and
    // steps areas"*. The three expansion items were flush against each other,
    // so three separate panels read as one striped block — which undercut the
    // 09-01 pass that gave them a shared shape in the first place. Shared
    // shape, separated objects.
    .cook-section {
        margin-bottom: var(--space-4);
    }
    // calm cards for the section bodies. No mid-cook stock-level colour noise;
    // just legible names + quantities.
    .cook-card {
        // `--surface-card` does not exist (FU-764); the card surface token is
        // `--surface-component`. Until now this declaration was invalid and the
        // group cards inherited q-card's own background.
        background: var(--surface-component);
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
    .ingredient-quantity {
        min-width: 64px;
    }
    .ingredient-name {
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
    // Finish rows: [level swatch] name + level name ... [cart]. One line at
    // every width now — the segmented control that used to wrap under the name
    // on a phone is a 32px square, so the row no longer needs a wrap rule.
    .finish-list {
        max-height: 50vh;
        overflow-y: auto;
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
    }
    .finish-row {
        display: flex;
        align-items: center;
        gap: var(--space-3);
        // The level swatch wears a dashed uncertainty ring that bleeds 5px
        // past the button; the vertical padding keeps it off the divider.
        padding: var(--space-3);
        border-bottom: 1px solid var(--divider);
    }
    .finish-row:last-child {
        border-bottom: none;
    }
    .finish-row__name {
        flex: 1 1 auto;
        min-width: 0;
        font-weight: 500;
        overflow-wrap: anywhere;
    }
    .finish-row__level {
        font-weight: 400;
        color: var(--text-secondary);
    }
    .finish-meals {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--space-4);
        flex-wrap: wrap;
    }
    // per-step highlight. A soft tint + accented border on
    // ingredient rows / tool chips that the current step references; the
    // unhighlighted neighbours dim slightly when at least one highlight is
    // active, so the eye lands where it should.
    .cook-row--highlighted {
        background: var(--semantic-info-soft, color-mix(in srgb, var(--brand-primary) 12%, transparent));
        border-left: 3px solid var(--brand-primary);
    }
    .cook-row--dim {
        opacity: 0.55;
    }
    // Cookbook revision §1.9 — optional ingredients render dimmed so the
    // eye lands on what's required to cook.
    .ingredient-row--optional {
        opacity: 0.65;
    }
    .all-steps-row--sub {
        padding-left: var(--space-8);
    }
    // The swapped-in substitute's conversion + note, under the row it applies
    // to. Secondary ink rather than muted: it is an instruction you act on,
    // not a footnote.
    .ingredient-note {
        display: flex;
        align-items: baseline;
        gap: var(--space-1);
        font-style: italic;
        color: var(--text-secondary);
        .q-icon {
            align-self: center;
            flex: 0 0 auto;
        }
    }
    .ingredient-swaphint {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        color: var(--text-secondary);
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
