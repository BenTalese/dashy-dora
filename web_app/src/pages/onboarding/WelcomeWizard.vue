<template>
    <q-page padding>
        <div class="wizard-shell q-mx-auto">
            <!-- ── Slim top row: mascot · progress rail · skip escape ────
                 The three elements sit inline with generous horizontal
                 spacing. The persistent "Skip onboarding" hatch lives here
                 (it replaced the old sign-out button in the layout header),
                 except on the finish step where the Finish action takes
                 over. ────────────────────────────────────────────────── -->
            <div class="wizard-topbar q-mb-lg">
                <q-avatar square size="40px" class="wizard-mascot">
                    <img src="../../assets/logo-mascot.png" alt="Dora" />
                </q-avatar>
                <OnboardingStepRail
                    class="wizard-topbar-rail"
                    :sections="railSections"
                    :active-section="view"
                    :active-index="railActiveIndex"
                    @jump="onRailJump"
                />
                <BaseButton
                    v-if="!(view === 'setup' && isLastStep)"
                    variant="ghost"
                    dense
                    class="wizard-skip dora-text-secondary"
                    :icon="ICONS.skip_next"
                    label="Skip onboarding"
                    :loading="completing"
                    @click="onSkipEverything"
                />
            </div>

            <!-- ══ STORY — cinematic intro + the hero loop ══════════════ -->
            <OnboardingStory
                v-if="view === 'story'"
                v-model:scene-index="storySceneIndex"
                @enter-setup="enterSetup"
            />

            <!-- ══ SETUP — the steps (draft-until-finish; applied on Finish) ══ -->
            <template v-else>
            <q-banner v-if="loadError" class="dora-bg-negative-soft text-negative q-mb-md" dense rounded>
                {{ loadError }}
            </q-banner>

            <!-- ── Step 1: Welcome — say hello, pick a face, pick a look ──
                 Owner 2026-10-17: the old card (mascot + blurb over two bare
                 selects) "looks absolutely horrible". Rebuilt as a hero that
                 previews the user's own avatar, a profile-picture picker
                 (upload or one of the pre-made food pictures), and visual
                 theme cards in place of the Theme select (each card paints a
                 mock-up in its own theme's tokens; the wizard itself stays on
                 WelcomeLayout's pinned dark canvas, so there's no live
                 preview). Everything is still a draft applied on Finish (L35). ──────────────────────────────── -->
            <div v-show="currentStep?.id === 'welcome'" class="welcome-step q-mb-md">
                <section class="welcome-hero">
                    <div class="welcome-hero__avatar">
                        <ImageEditTile
                            :label="hasDraftAvatar || currentUser?.has_image
                                ? 'Change your profile picture'
                                : 'Upload a profile picture'"
                            :width="104"
                            :height="104"
                            @pick="onUploadAvatar"
                            @error="(m) => (avatarError = m)"
                        >
                            <q-avatar v-if="hasDraftAvatar" size="104px">
                                <img :src="form.avatarDataUrl ?? ''" alt="Your profile picture" />
                            </q-avatar>
                            <UserAvatar
                                v-else-if="currentUser"
                                :user-id="currentUser.user_id"
                                :has-image="currentUser.has_image"
                                size="104px"
                                fallback="initials"
                                :username="currentUser.username"
                                color="accent"
                                text-color="dark"
                            />
                        </ImageEditTile>
                        <img
                            src="../../assets/logo-mascot.png"
                            alt=""
                            class="welcome-hero__mascot"
                            aria-hidden="true"
                        />
                    </div>
                    <div class="welcome-hero__copy">
                        <div class="welcome-hero__kicker">Hi, I'm Dora</div>
                        <h1 class="welcome-hero__title">
                            Nice to meet you{{ currentUser?.username ? `, ${currentUser.username}` : '' }}.
                        </h1>
                        <p class="welcome-hero__blurb">
                            I keep your pantry, shopping and cooking in one place so
                            the weekly shop stops feeling like detective work. Let's
                            make Dora yours. It takes about a minute.
                        </p>
                    </div>
                </section>

                <section class="welcome-panel">
                    <div class="welcome-panel__head">
                        <div class="welcome-panel__title">Pick a profile picture</div>
                        <div class="welcome-panel__sub">
                            Tap one of ours, or tap your avatar above to upload a photo.
                        </div>
                    </div>
                    <PresetAvatarPicker
                        :selected-key="form.avatarPresetKey"
                        @pick="onPickPresetAvatar"
                        @error="(m) => (avatarError = m)"
                    />
                    <div v-if="avatarError || hasDraftAvatar" class="welcome-panel__foot">
                        <span v-if="avatarError" class="text-caption text-negative">{{ avatarError }}</span>
                        <q-space />
                        <BaseButton
                            v-if="hasDraftAvatar"
                            variant="ghost"
                            dense
                            :icon="ICONS.undo"
                            label="Undo"
                            @click="clearDraftAvatar"
                        />
                    </div>
                </section>

                <section class="welcome-panel">
                    <div class="welcome-panel__head">
                        <div class="welcome-panel__title">Look &amp; feel</div>
                        <div class="welcome-panel__sub">
                            More themes live in Settings → Appearance.
                        </div>
                    </div>
                    <div class="welcome-themes" role="radiogroup" aria-label="Theme">
                        <button
                            v-for="opt in THEME_OPTIONS"
                            :key="opt.value"
                            type="button"
                            role="radio"
                            class="welcome-theme"
                            :class="{ 'welcome-theme--active': form.theme === opt.value }"
                            :aria-checked="form.theme === opt.value"
                            @click="form.theme = opt.value"
                        >
                            <span class="welcome-theme__preview" aria-hidden="true">
                                <span
                                    v-for="themeKey in opt.previews"
                                    :key="themeKey"
                                    class="welcome-theme__half"
                                    :data-theme="themeKey"
                                >
                                    <span class="welcome-theme__bar" />
                                    <span class="welcome-theme__line" />
                                    <span class="welcome-theme__line welcome-theme__line--short" />
                                    <span class="welcome-theme__dot" />
                                </span>
                            </span>
                            <span class="welcome-theme__label">
                                <q-icon :name="opt.icon" size="18px" />
                                {{ opt.label }}
                            </span>
                            <q-icon
                                v-if="form.theme === opt.value"
                                :name="ICONS.check_circle"
                                size="20px"
                                class="welcome-theme__badge"
                            />
                        </button>
                    </div>
                    <div class="welcome-font">
                        <div class="welcome-font__label">Font</div>
                        <DoraSegmented
                            :model-value="form.fontFamily"
                            :options="FONT_OPTIONS"
                            @update:model-value="(v) => (form.fontFamily = v)"
                        />
                    </div>
                    <!-- FU-615 — household headcount + cook-style ("I batch-cook")
                         are install-wide settings (Settings → System → Cooking);
                         batch cooking is offered on the features step instead. -->
                </section>
            </div>

            <!-- ── Step: Build your Dora experience (first user only) ──────
                 Owner 2026-10-17. The install-wide features as cards; a tap
                 flips one on or off. Seeded from the install's current
                 settings and applied on Finish with the rest of the draft
                 (L35), so a bail changes nothing. Every card is a real admin
                 toggle that also lives in Settings → System. ──────────── -->
            <div v-show="currentStep?.id === 'features'" class="features-step q-mb-md">
                <div class="features-step__head">
                    <div class="text-h6">Build your Dora experience</div>
                    <div class="text-body2 dora-text-secondary">
                        Switch on the parts your household wants. You can change
                        any of these later.
                    </div>
                </div>
                <section class="welcome-panel q-mb-md">
                    <div class="welcome-panel__head">
                        <div class="welcome-panel__title">Your household</div>
                        <div class="welcome-panel__sub">
                            Shared by everyone in Dora. Settings → System has the rest.
                        </div>
                    </div>
                    <!-- `dark` on each field: see OnboardingPickPanel. -->
                    <div class="household-fields">
                        <label class="household-field">
                            <span class="household-field__label">People you cook for</span>
                            <q-input
                                dark
                                v-model.number="household.headcount"
                                outlined
                                dense
                                type="number"
                                :min="1"
                                :max="99"
                                placeholder="Per recipe"
                                clearable
                                :disable="!featuresLoaded"
                                class="household-field__headcount"
                            />
                        </label>
                        <label class="household-field household-field--grow">
                            <span class="household-field__label">Timezone</span>
                            <q-select
                                dark
                                v-model="household.timezone"
                                :options="timezoneOptions"
                                outlined
                                dense
                                use-input
                                hide-selected
                                fill-input
                                input-debounce="0"
                                options-dense
                                :disable="!featuresLoaded"
                                @filter="onTimezoneFilter"
                            />
                        </label>
                    </div>
                    <div class="welcome-font household-units">
                        <div class="welcome-font__label">Units</div>
                        <DoraSegmented
                            :model-value="household.measurementSystem"
                            :options="UNIT_OPTIONS"
                            :disabled="!featuresLoaded"
                            @update:model-value="(v) => (household.measurementSystem = v)"
                        />
                    </div>
                </section>
                <div class="feature-grid">
                    <button
                        v-for="feature in FEATURE_CARDS"
                        :key="feature.key"
                        type="button"
                        role="switch"
                        class="feature-card"
                        :class="{ 'feature-card--on': featurePicks[feature.key] }"
                        :aria-checked="featurePicks[feature.key]"
                        :disabled="!featuresLoaded"
                        @click="featurePicks[feature.key] = !featurePicks[feature.key]"
                    >
                        <span class="feature-card__icon" aria-hidden="true">
                            <q-icon :name="feature.icon" size="24px" />
                        </span>
                        <span class="feature-card__body">
                            <span class="feature-card__title">{{ feature.title }}</span>
                            <span class="feature-card__desc">{{ feature.description }}</span>
                        </span>
                        <span class="feature-card__state">
                            <q-icon
                                :name="featurePicks[feature.key] ? ICONS.check_circle : ICONS.circle_outline"
                                size="22px"
                            />
                            <span class="feature-card__state-label">
                                {{ featurePicks[feature.key] ? 'On' : 'Off' }}
                            </span>
                        </span>
                    </button>
                </div>
                <div v-if="!featuresLoaded" class="text-caption dora-text-muted q-mt-sm">
                    Loading your install's current settings…
                </div>
            </div>

            <!-- ── Step: Your stock (first user only) ─────────────────────
                 Owner 2026-10-21: one page for where things live, how they're
                 grouped, and what you usually keep. Each panel ticks Dora's
                 defaults on or off and takes your own; all of it is drafted
                 and created on Finish (L35). -->
            <div v-show="currentStep?.id === 'stock'" class="stock-step q-mb-md">
                <div class="features-step__head">
                    <div class="text-h6">Set up your stock</div>
                    <div class="text-body2 dora-text-secondary">
                        Where you keep things, how you group them, and what you
                        usually have. Untick what doesn't fit and add your own.
                    </div>
                </div>
                <OnboardingPickPanel
                    title="Stock locations"
                    sub="The places in your home where things are kept."
                    :icon="ICONS.place"
                    :sections="locationSections"
                    :model-value="locationPicks"
                    add-placeholder="Add a location, e.g. Garage"
                    @update:model-value="(v) => Object.assign(locationPicks, v)"
                    @add="(name) => addOwnName('locations', name)"
                    @remove="(key) => removeOwnName('locations', key)"
                />
                <OnboardingPickPanel
                    title="Stock groups"
                    sub="How items are sorted on your stock page."
                    :icon="ICONS.category"
                    :sections="groupSections"
                    :model-value="groupPicks"
                    add-placeholder="Add a group, e.g. Baking"
                    @update:model-value="(v) => Object.assign(groupPicks, v)"
                    @add="(name) => addOwnName('groups', name)"
                    @remove="(key) => removeOwnName('groups', key)"
                />
                <OnboardingPickPanel
                    title="Stock items"
                    sub="Things you usually keep. Each starts as fully stocked."
                    :icon="ICONS.inventory_2"
                    :sections="itemSections"
                    :model-value="packItemSelected"
                    add-placeholder="Add an item, e.g. Coffee"
                    @update:model-value="(v) => Object.assign(packItemSelected, v)"
                    @add="addOwnItem"
                    @remove="removeOwnItem"
                >
                    <template #add-fields>
                        <q-select
                            dark
                            v-model="ownItem.group_name"
                            :options="groupNameOptions"
                            outlined
                            dense
                            clearable
                            label="Group"
                            class="stock-step__own-select"
                        />
                        <q-select
                            dark
                            v-model="ownItem.location_name"
                            :options="locationNameOptions"
                            outlined
                            dense
                            clearable
                            label="Location"
                            class="stock-step__own-select"
                        />
                    </template>
                </OnboardingPickPanel>
            </div>

            <!-- ── Step: Finish — celebrate, recap, first steps ─────────
                 Owner 2026-10-17: "make the finishing page as useful and
                 polished as you can". Three parts: a hero that greets the
                 user with the face they just picked; a recap of exactly what
                 Finish will apply (the wizard is draft-until-finish, so this
                 is the last look before it lands); and "first steps" tiles,
                 each of which finishes and opens that screen. The loop recap
                 stays out — the hero loop already plays in Story. -->
            <div
                v-show="currentStep?.id === 'finish'"
                class="finish-step q-mb-md"
            >
                <OnboardingConfetti v-if="currentStep?.id === 'finish'" />
                <section class="finish-hero">
                    <div class="finish-hero__faces" aria-hidden="true">
                        <q-avatar v-if="hasDraftAvatar" size="72px" class="finish-hero__avatar">
                            <img :src="form.avatarDataUrl ?? ''" alt="" />
                        </q-avatar>
                        <UserAvatar
                            v-else-if="currentUser"
                            class="finish-hero__avatar"
                            :user-id="currentUser.user_id"
                            :has-image="currentUser.has_image"
                            size="72px"
                            fallback="initials"
                            :username="currentUser.username"
                            color="accent"
                            text-color="dark"
                        />
                        <DoraMascot mood="super_excited" :size="84" class="finish-hero__mascot" />
                    </div>
                    <div class="finish-hero__title">
                        You're all set{{ currentUser?.username ? `, ${currentUser.username}` : '' }}!
                    </div>
                    <div class="finish-hero__sub">
                        Tap Finish to save everything, or jump straight into one of
                        the first steps below.
                    </div>
                </section>

                <section v-if="finishRecap.length > 0" class="finish-panel">
                    <div class="finish-panel__title">What Finish will set up</div>
                    <ul class="finish-recap">
                        <li v-for="row in finishRecap" :key="row.key" class="finish-recap__row">
                            <span class="finish-recap__icon" aria-hidden="true">
                                <q-icon :name="row.icon" size="18px" />
                            </span>
                            <span class="finish-recap__text">{{ row.text }}</span>
                            <BaseButton
                                v-if="row.step !== undefined"
                                variant="ghost"
                                dense
                                size="sm"
                                class="dora-text-secondary"
                                label="Change"
                                @click="stepIndex = row.step"
                            />
                        </li>
                    </ul>
                </section>

                <section v-if="state?.first_user" class="finish-panel">
                    <div class="finish-panel__title">Extras</div>
                    <button
                        type="button"
                        role="switch"
                        class="feature-card"
                        :class="{ 'feature-card--on': form.seedDemo }"
                        :aria-checked="form.seedDemo"
                        @click="form.seedDemo = !form.seedDemo"
                    >
                        <span class="feature-card__icon" aria-hidden="true">
                            <q-icon :name="ICONS.restaurant_menu" size="24px" />
                        </span>
                        <span class="feature-card__body">
                            <span class="feature-card__title">Add a demo recipe</span>
                            <span class="feature-card__desc">
                                Spaghetti Aglio e Olio on this week's meal plan, so the
                                cookbook and planner aren't empty. Delete it any time.
                            </span>
                        </span>
                        <span class="feature-card__state">
                            <q-icon
                                :name="form.seedDemo ? ICONS.check_circle : ICONS.circle_outline"
                                size="22px"
                            />
                            <span class="feature-card__state-label">
                                {{ form.seedDemo ? 'On' : 'Off' }}
                            </span>
                        </span>
                    </button>
                </section>

                <section class="finish-panel">
                    <div class="finish-panel__title">First steps</div>
                    <div class="finish-tiles">
                        <button
                            v-for="(card, i) in flowCards"
                            :key="card.path"
                            type="button"
                            class="finish-tile"
                            :disabled="completing"
                            @click="onShowMe(card.path)"
                        >
                            <span class="finish-tile__icon" aria-hidden="true">
                                <q-icon :name="card.icon" size="22px" />
                            </span>
                            <span class="finish-tile__body">
                                <span class="finish-tile__title">
                                    <span v-if="card.numbered" class="finish-tile__num">{{ i + 1 }}</span>
                                    {{ card.title }}
                                </span>
                                <span class="finish-tile__desc">{{ card.description }}</span>
                            </span>
                            <q-icon :name="ICONS.chevron_right" size="20px" class="finish-tile__chevron" />
                        </button>
                    </div>
                </section>

                <section class="finish-tip">
                    <q-icon :name="ICONS.chat_bubble_outline" size="20px" class="finish-tip__icon" />
                    <span>
                        Stuck? Dora's help bubble follows you around the app, and the
                        <router-link to="/help" class="text-primary" @click.prevent="onShowMe('/help')">guides</router-link>
                        explain each area in depth.
                    </span>
                </section>
            </div>

            <!-- ── Footer: Back / Next ──────────────────────────────── -->
            <div class="row items-center q-mt-md">
                <BaseButton
                    variant="ghost"
                    :icon="ICONS.arrow_back"
                    :label="stepIndex === 0 ? 'Back to intro' : 'Back'"
                    @click="onBack"
                />
                <q-space />
                <BaseButton
                    variant="primary"
                    :icon-right="isLastStep ? 'check' : 'arrow_forward'"
                    :label="isLastStep ? 'Finish' : 'Next'"
                    :loading="completing"
                    @click="advance"
                />
            </div>
            </template>
        </div>
    </q-page>
</template>

<script lang="ts" setup>
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';
    import ImageEditTile from 'src/components/ImageEditTile.vue';
    import PresetAvatarPicker from 'src/components/PresetAvatarPicker.vue';
    import UserAvatar from 'src/components/UserAvatar.vue';
    import DoraMascot from 'src/components/dora/DoraMascot.vue';
    import DoraSegmented from 'src/components/settings/DoraSegmented.vue';
    import OnboardingConfetti from 'src/components/onboarding/OnboardingConfetti.vue';
    import OnboardingPickPanel, { type PickSection } from 'src/components/onboarding/OnboardingPickPanel.vue';
    import OnboardingStepRail from 'src/components/onboarding/OnboardingStepRail.vue';
    import OnboardingStory from 'src/pages/onboarding/OnboardingStory.vue';
    import { storeToRefs } from 'pinia';
    import { fontFamilyOptions, coalesceFontFamily } from 'src/services/themeService';
    import type { ProcessedImage } from 'src/services/files/imageService';
    import type { AppSettings, UpdateAppSettingsCommand } from 'src/services/api/appSettingsApiService';
    import { useAppSettingsStore } from 'src/stores/appSettingsStore';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import { refreshCookingPolicy } from 'src/composables/useCookingPolicy';
    import { useMeasurementSystem } from 'src/composables/useMeasurementSystem';
    import type { DoraSegmentedOption } from 'src/components/settings/DoraSegmented.vue';
    import { MEASUREMENT_SYSTEM_CHOICES, TIMEZONE_CHOICES } from 'src/models/regionChoices';
    import type { MeasurementSystem } from 'src/generated/units_table';
    import type { FontFamilyPreference, ThemePreference } from 'src/models/auth';
    import type {
        OnboardingCatalog,
        OnboardingState,
        StarterPackItem,
    } from 'src/models/onboarding';
    import { NARRATIVE_SCENES } from 'src/pages/onboarding/onboardingContent';
    import OnboardingApiService from 'src/services/api/onboardingApiService';
    import { useStockGroupStore } from 'src/stores/stockGroupStore';
    import { extractFieldErrors } from 'src/services/errorHandling/apiErrorHandler';
    import { useAuthStore } from 'src/stores/authStore';
    import { useStockLocationStore } from 'src/stores/stockLocationStore';
    import { computed, onMounted, reactive, ref, watch } from 'vue';
    import { useRouter } from 'vue-router';

    const router = useRouter();
    const onboardingApi = new OnboardingApiService();
    const stockGroupStore = useStockGroupStore();
    const appSettingsStore = useAppSettingsStore();
    const { refresh: refreshFeatureFlags, money: moneyFlag } = useFeatureFlags();
    const { reload: reloadMeasurementSystem } = useMeasurementSystem();
    const authStore = useAuthStore();
    const stockLocationStore = useStockLocationStore();

    const { currentUser } = storeToRefs(authStore);

    // Refetched, not ensure-loaded: onboarding seeds groups mid-flow.
    const stockGroups = computed(() => stockGroupStore.stockGroups);
    async function loadStockGroups() {
        await stockGroupStore.refreshAsync().catch(() => undefined);
    }

    // ── Static option lists ──────────────────────────────────────────
    // L28 — onboarding offers only System / Light / Dark. Light maps to the
    // brand light theme (Pesto) and Dark to Pesto Dark; the rest of the
    // palette catalogue (lemon-tart, blueberry, …) is pickable later in
    // Preferences. Values are real ThemePreference keys so we persist the
    // resolved theme rather than the legacy 'light'/'dark' aliases.
    //
    // 2026-10-17 — drawn as cards rather than a select. `previews` names the
    // theme(s) each card's mini mock-up is painted in: the halves carry a
    // `data-theme` attribute, so they read that theme's real tokens rather
    // than a copied palette (R-002). System shows both, split.
    const THEME_OPTIONS: {
        label: string;
        value: ThemePreference;
        icon: string;
        previews: string[];
    }[] = [
        { label: 'System', value: 'system', icon: ICONS.brightness_auto, previews: ['pesto', 'pesto-dark'] },
        { label: 'Light', value: 'pesto', icon: ICONS.light_mode, previews: ['pesto'] },
        { label: 'Dark', value: 'pesto-dark', icon: ICONS.dark_mode, previews: ['pesto-dark'] },
    ];
    // Font options + the `coalesceFontFamily` fold are the shared FU-614 source
    // in themeService (R-003). The wizard uses the full "Plus Jakarta Sans" label
    // (it has room), so no override.
    const FONT_OPTIONS = fontFamilyOptions();
    // ── Wizard step state ────────────────────────────────────────────
    type StepId = 'welcome' | 'features' | 'stock' | 'finish';
    type Step = { id: StepId; title: string };

    const state = ref<OnboardingState | null>(null);
    const loadError = ref<string | null>(null);
    const stepIndex = ref(0);
    const completing = ref(false);

    // ── Story / Setup view model (C-5.2) ─────────────────────────────
    // Two sections with instant, non-linear cross-jump via the shared rail.
    const view = ref<'story' | 'setup'>('story');
    const storySceneIndex = ref(0);

    // Two tracks. First user of an install (fresh self-host or first user in a
    // new SaaS household) walks the full setup: household + features, then
    // the household-scoped locations, groups and starting stock.
    // Every subsequent user joins an already-configured household, so they only
    // set personal prefs (display name / theme / font / headcount on the
    // welcome step) and land in the app.
    const visibleSteps = computed<Step[]>(() => {
        const steps: Step[] = [{ id: 'welcome', title: 'Welcome' }];
        if (state.value?.first_user) {
            steps.push({ id: 'features', title: 'Build your Dora' });
            steps.push({ id: 'stock', title: 'Your stock' });
        }
        steps.push({ id: 'finish', title: "You're all set" });
        return steps;
    });

    // ── Finish "first steps" (C-5.6, rebuilt 2026-10-17) ─────────────
    // The loop in the order a new household walks it, numbered, then the
    // optional extras. Each tile finishes onboarding and lands on its screen.
    // Price history only shows when spend tracking will be on — after Finish
    // it'd be a dead end otherwise (P3 Honest).
    const flowCards = computed(() => {
        const cards: {
            path: string;
            title: string;
            description: string;
            icon: string;
            numbered: boolean;
        }[] = [
            { path: '/stock', title: 'Stock your pantry', numbered: true,
              description: 'Add what you keep, with levels, locations and expiry.',
              icon: ICONS.inventory_2 },
            { path: '/cookbook', title: 'Fill your cookbook', numbered: true,
              description: 'See what you can cook from what’s in, then cook it step by step.',
              icon: ICONS.menu_book },
            { path: '/meal-plans', title: 'Plan the week', numbered: true,
              description: 'Plan meals and turn the week into a shopping list.',
              icon: ICONS.event },
            { path: '/shopping-lists', title: 'Go shopping', numbered: true,
              description: 'Lists build themselves from what’s low or out; finishing a shop restocks you.',
              icon: ICONS.shopping_cart },
        ];
        if (willHaveMoney.value) {
            cards.push({
                path: '/price-history', title: 'Watch your prices', numbered: false,
                description: 'See how what you pay moves over time.',
                icon: ICONS.savings,
            });
        }
        cards.push({
            path: '/settings/voice', title: "Pick Dora's voice", numbered: false,
            description: "A voice for Dora's chat replies and cook mode.",
            icon: ICONS.record_voice_over,
        });
        return cards;
    });

    const currentStep = computed<Step | null>(
        () => visibleSteps.value[stepIndex.value] ?? null,
    );
    const isLastStep = computed(
        () => stepIndex.value === visibleSteps.value.length - 1,
    );

    // ── Shared rail model (Story scenes + Setup steps) ───────────────
    // Nothing is gated — every dot is a jump target across both sections.
    const railSections = computed(() => [
        {
            key: 'story',
            label: 'Story',
            dots: NARRATIVE_SCENES.map((s) => ({
                key: s.id,
                label: s.kicker ?? s.headline,
            })),
        },
        {
            key: 'setup',
            label: 'Setup',
            dots: visibleSteps.value.map((s) => ({ key: s.id, label: s.title })),
        },
    ]);
    const railActiveIndex = computed(() =>
        view.value === 'story' ? storySceneIndex.value : stepIndex.value,
    );
    function onRailJump(sectionKey: string, index: number) {
        if (sectionKey === 'story') {
            view.value = 'story';
            storySceneIndex.value = index;
        } else {
            view.value = 'setup';
            stepIndex.value = index;
        }
    }
    function enterSetup() {
        view.value = 'setup';
    }

    // ── Form state (persists to localStorage so refresh resumes) ─────
    type WizardDraft = {
        theme: ThemePreference;
        fontFamily: FontFamilyPreference;
        // FU-615 — headcount + batch cook-style are install-wide settings now
        // (Settings → System → Cooking), no longer collected per-user here.
        // the seed-catalogue master booleans are gone; the
        // per-name pick sets below carry the same signal. A card is
        // effectively "on" when any name in it is picked, "off" when
        // none. See groupPicks / locationPicks below.
        // optional demo dataset (one recipe + a current-week meal
        // plan). Default off because it inserts plain rows the user then
        // has to clean up if they didn't actually want demo content.
        seedDemo: boolean;
        stepIndex: number;
        // 2026-10-17 — profile picture, drafted like everything else and
        // saved on Finish. `avatarDataUrl` is the encoded picture (an upload
        // or a rendered preset); `avatarPresetKey` only drives the picker's
        // selected ring and is null for an upload.
        avatarDataUrl: string | null;
        avatarPresetKey: string | null;
    };

    // A stock item the user added themselves: created on Finish (L35), never
    // on each Add, so a mid-wizard bail leaves nothing behind.
    type DraftItem = {
        name: string;
        group_name: string | null;
        location_name: string | null;
    };

    const DRAFT_KEY = (userId: string) =>
        `dora.onboarding.draft.${userId || 'anonymous'}`;

    const form = reactive<WizardDraft>({
        theme: 'system',
        fontFamily: 'default',
        seedDemo: false,
        stepIndex: 0,
        avatarDataUrl: null,
        avatarPresetKey: null,
    });

    // ── Profile picture (welcome step) ───────────────────────────────
    const avatarError = ref<string | null>(null);
    const hasDraftAvatar = computed(() => !!form.avatarDataUrl);
    function onUploadAvatar(processed: ProcessedImage) {
        avatarError.value = null;
        form.avatarDataUrl = processed.dataUrl;
        form.avatarPresetKey = null;
    }
    function onPickPresetAvatar({ key, dataUrl }: { key: string; dataUrl: string }) {
        avatarError.value = null;
        form.avatarDataUrl = dataUrl;
        form.avatarPresetKey = key;
    }
    function clearDraftAvatar() {
        form.avatarDataUrl = null;
        form.avatarPresetKey = null;
    }

    // ── Build your Dora experience (features step, first user only) ──
    // Each card is one install-wide AppSetting the admin can also flip in
    // Settings → System. The pick is the plain on/off the card shows; the
    // mapping onto the setting lives in `apply`, so a richer stored value
    // (nutrition 'complex', auto-add 'all') that reads as "on" survives an
    // untouched card — `changedFeatureSettings` only sends what moved.
    type FeatureKey = 'money' | 'nutrition' | 'stocktake' | 'batch' | 'auto_add' | 'scanning';
    type FeatureCard = {
        key: FeatureKey;
        title: string;
        description: string;
        icon: string;
        read: (s: AppSettings) => boolean;
        apply: (on: boolean) => UpdateAppSettingsCommand;
    };
    const FEATURE_CARDS: readonly FeatureCard[] = [
        {
            key: 'money', title: 'Spend tracking', icon: ICONS.savings,
            description: 'Prices, budgets and what each meal costs.',
            read: (s) => s.money_enabled,
            apply: (on) => ({ money_enabled: on }),
        },
        {
            key: 'nutrition', title: 'Nutrition', icon: ICONS.monitor_heart,
            description: 'Calories and macros on your recipes and meal plans.',
            read: (s) => s.nutrition_mode !== 'off',
            apply: (on) => ({ nutrition_mode: on ? 'simple' : 'off' }),
        },
        {
            key: 'stocktake', title: 'Stocktakes', icon: ICONS.fact_check,
            description: 'Gentle reminders to check what’s really in the cupboard.',
            read: (s) => s.stocktake_enabled,
            apply: (on) => ({ stocktake_enabled: on }),
        },
        {
            key: 'auto_add', title: 'Auto-add essentials', icon: ICONS.add_shopping_cart,
            description: 'Essentials go on the shopping list the moment they run low.',
            read: (s) => s.auto_add_mode !== 'off',
            apply: (on) => ({ auto_add_mode: on ? 'essential_only' : 'off' }),
        },
        {
            key: 'batch', title: 'Batch cooking', icon: ICONS.mealsPrepared,
            description: 'Cook once, eat for days: Dora tracks the leftovers.',
            read: (s) => s.batch_features_enabled,
            apply: (on) => ({ batch_features_enabled: on }),
        },
        {
            key: 'scanning', title: 'Barcodes & QR labels', icon: ICONS.qr_code_scanner,
            description: 'Scan products and print QR labels for your shelves.',
            read: (s) => s.scanning_enabled,
            apply: (on) => ({ scanning_enabled: on }),
        },
    ];
    const featurePicks = reactive<Record<FeatureKey, boolean>>({
        money: false, nutrition: false, stocktake: true,
        auto_add: true, batch: false, scanning: false,
    });
    // What the install says right now — the baseline `featurePicks` is
    // diffed against on Finish. Null until loaded (non-admins never load it).
    const featureBaseline = ref<Record<FeatureKey, boolean> | null>(null);

    // ── Your household (features step) ───────────────────────────────
    // Three install-wide values every household should set once. Diffed
    // against `householdBaseline` on Finish like the feature cards. A fresh
    // install's timezone is UTC, which puts "today" on the wrong day for most
    // people, so it starts on this device's timezone instead.
    type HouseholdDraft = {
        headcount: number | null;
        timezone: string;
        measurementSystem: MeasurementSystem;
    };
    const household = reactive<HouseholdDraft>({
        headcount: null, timezone: 'UTC', measurementSystem: 'metric',
    });
    const householdBaseline = ref<HouseholdDraft | null>(null);
    let savedHousehold: Partial<HouseholdDraft> | null = null;
    const UNIT_OPTIONS: DoraSegmentedOption<MeasurementSystem>[] =
        MEASUREMENT_SYSTEM_CHOICES.map((c) => ({ label: c.short, value: c.value }));
    const timezoneOptions = ref<string[]>([...TIMEZONE_CHOICES]);
    function onTimezoneFilter(val: string, update: (cb: () => void) => void) {
        update(() => {
            const needle = val.toLowerCase();
            timezoneOptions.value = needle
                ? TIMEZONE_CHOICES.filter((t) => t.toLowerCase().includes(needle))
                : [...TIMEZONE_CHOICES];
        });
    }
    function deviceTimezone(): string {
        try {
            return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
        } catch {
            return 'UTC';
        }
    }
    function normaliseHeadcount(value: number | null): number | null {
        if (value === null || value === undefined || !Number.isFinite(value) || value < 1) {
            return null;
        }
        return Math.min(99, Math.floor(value));
    }
    const changedHouseholdSettings = computed<UpdateAppSettingsCommand>(() => {
        const base = householdBaseline.value;
        if (!base) return {};
        const out: UpdateAppSettingsCommand = {};
        const headcount = normaliseHeadcount(household.headcount);
        if (headcount !== base.headcount) out.household_headcount = headcount;
        if (household.timezone && household.timezone !== base.timezone) {
            out.timezone = household.timezone;
        }
        if (household.measurementSystem !== base.measurementSystem) {
            out.measurement_system = household.measurementSystem;
        }
        return out;
    });
    const featuresLoaded = computed(() => featureBaseline.value !== null);
    // Picks restored from a saved draft win over the install's values.
    let savedFeaturePicks: Partial<Record<FeatureKey, boolean>> | null = null;

    async function loadFeatureBaseline() {
        if (!state.value?.first_user || !currentUser.value?.is_admin) return;
        try {
            const settings = await appSettingsStore.loadAsync();
            const baseline = {} as Record<FeatureKey, boolean>;
            for (const card of FEATURE_CARDS) baseline[card.key] = card.read(settings);
            featureBaseline.value = baseline;
            Object.assign(featurePicks, baseline, savedFeaturePicks ?? {});
            const householdNow: HouseholdDraft = {
                headcount: settings.household_headcount,
                timezone: settings.timezone,
                measurementSystem: settings.measurement_system,
            };
            householdBaseline.value = householdNow;
            Object.assign(household, householdNow, {
                timezone: settings.timezone === 'UTC' ? deviceTimezone() : settings.timezone,
            }, savedHousehold ?? {});
        } catch {
            // Leave the step unloaded (cards disabled); Finish then sends
            // nothing for it and the admin can use Settings instead.
        }
    }
    const changedFeatureSettings = computed<UpdateAppSettingsCommand>(() => {
        const base = featureBaseline.value;
        if (!base) return {};
        const out: UpdateAppSettingsCommand = {};
        for (const card of FEATURE_CARDS) {
            if (featurePicks[card.key] !== base[card.key]) {
                Object.assign(out, card.apply(featurePicks[card.key]));
            }
        }
        return out;
    });
    const willHaveMoney = computed(() =>
        featureBaseline.value ? featurePicks.money : moneyFlag.value,
    );

    // ── Finish recap — what Finish is about to apply ─────────────────
    // Built from the same draft `applyDraft` reads, so it can't promise
    // something Finish won't do. `step` lets each row jump back to change it.
    function stepIndexOf(id: StepId): number | undefined {
        const i = visibleSteps.value.findIndex((st) => st.id === id);
        return i >= 0 ? i : undefined;
    }
    function plural(n: number, one: string, many = `${one}s`): string {
        return `${n} ${n === 1 ? one : many}`;
    }
    const finishRecap = computed(() => {
        const rows: { key: string; icon: string; text: string; step?: number | undefined }[] = [];
        if (hasDraftAvatar.value) {
            rows.push({ key: 'avatar', icon: ICONS.person, text: 'Your new profile picture',
                step: stepIndexOf('welcome') });
        }
        const themeLabel = THEME_OPTIONS.find((o) => o.value === form.theme)?.label;
        if (themeLabel) {
            rows.push({ key: 'look', icon: ICONS.palette, step: stepIndexOf('welcome'),
                text: `${themeLabel} theme, ${FONT_OPTIONS.find((o) => o.value === form.fontFamily)?.label ?? 'default'} font` });
        }
        if (householdBaseline.value) {
            const headcount = normaliseHeadcount(household.headcount);
            rows.push({ key: 'household', icon: ICONS.people, step: stepIndexOf('features'),
                text: `${headcount ? plural(headcount, 'person', 'people') : 'Recipe servings'}, ${household.timezone}, ${UNIT_OPTIONS.find((o) => o.value === household.measurementSystem)?.label ?? ''} units` });
        }
        if (featureBaseline.value) {
            const on = FEATURE_CARDS.filter((c) => featurePicks[c.key]).map((c) => c.title);
            rows.push({ key: 'features', icon: ICONS.tune, step: stepIndexOf('features'),
                text: on.length > 0 ? `Features on: ${on.join(', ')}` : 'All optional features off' });
        }
        const seedParts: string[] = [];
        const groupCount = groupPickCount.value + customGroups.value.length;
        const locationCount = locationPickCount.value + customLocations.value.length;
        if (groupCount > 0) seedParts.push(plural(groupCount, 'stock group'));
        if (locationCount > 0) seedParts.push(plural(locationCount, 'location'));
        if (seedParts.length > 0) {
            rows.push({ key: 'seed', icon: ICONS.category, step: stepIndexOf('stock'),
                text: seedParts.join(' and ') });
        }
        const itemCount = selectedPackItemsList.value.length + draftItems.value.length;
        if (itemCount > 0) {
            rows.push({ key: 'items', icon: ICONS.inventory_2, step: stepIndexOf('stock'),
                text: plural(itemCount, 'stock item') });
        }
        if (form.seedDemo) {
            rows.push({ key: 'demo', icon: ICONS.restaurant_menu,
                text: 'A demo recipe on this week’s meal plan' });
        }
        return rows;
    });

    // per-name picks over the bundled catalogues. Keys are
    // lowercased (name for groups; "zone" or "zone/child" path for
    // locations). Default state (populated on catalog load) has every
    // name ticked — matches the pre-FU-195 "seedGroups=true" behaviour.
    const groupPicks = reactive<Record<string, boolean>>({});
    const locationPicks = reactive<Record<string, boolean>>({});

    // honoured when the catalogue lands + the
    // pick maps get seeded, so a pre-FU-195 "seedGroups=false" resumes as
    // "no groups picked".
    let legacyGroupsOff = false;
    let legacyLocationsOff = false;

    // The user's own entries on the stock step, created on Finish.
    const customGroups = ref<string[]>([]);
    const customLocations = ref<string[]>([]);
    const draftItems = ref<DraftItem[]>([]);
    const ownItem = reactive({
        group_name: null as string | null,
        location_name: null as string | null,
    });

    // starter catalogue (default groups/locations + packs), fetched on
    // mount, and the pack items the user has ticked (keyed by item name).
    const catalog = ref<OnboardingCatalog | null>(null);
    const packItemSelected = reactive<Record<string, boolean>>({});
    async function loadCatalog() {
        try {
            catalog.value = await onboardingApi.getCatalogAsync();
            seedDefaultPicks();
        } catch {
            catalog.value = null;
        }
    }

    // after the catalogue lands, seed the pick maps with every
    // name ticked by default (preserving the pre-FU-195 default of
    // "seed everything"). A pick key already present in the map (from a
    // resumed draft) is left alone so the user's choice survives reload.
    function seedDefaultPicks() {
        if (!catalog.value) return;
        const groupsDefault = legacyGroupsOff ? false : true;
        const locationsDefault = legacyLocationsOff ? false : true;
        for (const name of catalog.value.groups) {
            const key = name.toLowerCase();
            if (!(key in groupPicks)) groupPicks[key] = groupsDefault;
        }
        for (const path of locationLeafPaths.value) {
            const key = path.toLowerCase();
            if (!(key in locationPicks)) locationPicks[key] = locationsDefault;
        }
    }

    function saveDraft() {
        try {
            const userId = currentUser.value?.user_id ?? '';
            localStorage.setItem(
                DRAFT_KEY(userId),
                JSON.stringify({
                    ...form,
                    stepIndex: stepIndex.value,
                    draftItems: draftItems.value,
                    view: view.value,
                    storySceneIndex: storySceneIndex.value,
                    packItemSelected: { ...packItemSelected },
                    groupPicks: { ...groupPicks },
                    locationPicks: { ...locationPicks },
                    featurePicks: { ...featurePicks },
                    household: { ...household },
                    customGroups: customGroups.value,
                    customLocations: customLocations.value,
                }),
            );
        } catch {
            // localStorage may be unavailable.
        }
    }
    function loadDraft() {
        try {
            const userId = currentUser.value?.user_id ?? '';
            const raw = localStorage.getItem(DRAFT_KEY(userId));
            if (!raw) return;
            const parsed = JSON.parse(raw) as Partial<WizardDraft> & {
                stepIndex?: number;
                draftItems?: DraftItem[];
                view?: 'story' | 'setup';
                storySceneIndex?: number;
                packItemSelected?: Record<string, boolean>;
                groupPicks?: Record<string, boolean>;
                locationPicks?: Record<string, boolean>;
                featurePicks?: Partial<Record<FeatureKey, boolean>>;
                household?: Partial<HouseholdDraft>;
                customGroups?: string[];
                customLocations?: string[];
                // Legacy pre-FU-195 draft booleans — folded into the pick
                // maps once the catalogue lands (seedDefaultPicks respects
                // whatever the pick maps already say).
                seedGroups?: boolean;
                seedLocations?: boolean;
            };
            const {
                stepIndex: savedIndex,
                draftItems: savedItems,
                view: savedView,
                storySceneIndex: savedScene,
                packItemSelected: savedPacks,
                groupPicks: savedGroupPicks,
                locationPicks: savedLocationPicks,
                featurePicks: savedFeatures,
                household: savedHouseholdDraft,
                customGroups: savedCustomGroups,
                customLocations: savedCustomLocations,
                seedGroups: legacySeedGroups,
                seedLocations: legacySeedLocations,
                ...formFields
            } = parsed;
            Object.assign(form, formFields);
            if (typeof savedIndex === 'number') {
                stepIndex.value = Math.max(0, savedIndex);
            }
            if (Array.isArray(savedItems)) {
                draftItems.value = savedItems;
            }
            if (savedView === 'story' || savedView === 'setup') {
                view.value = savedView;
            }
            if (typeof savedScene === 'number') {
                storySceneIndex.value = Math.max(0, savedScene);
            }
            if (savedPacks) {
                Object.assign(packItemSelected, savedPacks);
            }
            if (savedGroupPicks) {
                Object.assign(groupPicks, savedGroupPicks);
            }
            if (savedLocationPicks) {
                Object.assign(locationPicks, savedLocationPicks);
            }
            if (savedFeatures) {
                savedFeaturePicks = savedFeatures;
                Object.assign(featurePicks, savedFeatures);
            }
            if (savedHouseholdDraft) {
                savedHousehold = savedHouseholdDraft;
                Object.assign(household, savedHouseholdDraft);
            }
            if (Array.isArray(savedCustomGroups)) customGroups.value = savedCustomGroups;
            if (Array.isArray(savedCustomLocations)) customLocations.value = savedCustomLocations;
            // Legacy pre-FU-195: the booleans became pick maps. If the
            // legacy master was explicitly off, honour that by defaulting
            // any not-yet-populated pick to false (seedDefaultPicks fills
            // absent keys with true; overriding it after mount would race
            // the catalogue fetch).
            legacyGroupsOff = legacySeedGroups === false;
            legacyLocationsOff = legacySeedLocations === false;
        } catch {
            // Bad draft — ignore.
        }
    }
    function clearDraft() {
        try {
            const userId = currentUser.value?.user_id ?? '';
            localStorage.removeItem(DRAFT_KEY(userId));
        } catch {
            // Best effort.
        }
    }
    // Auto-save the draft on any form change so a refresh resumes.
    watch(
        [
            form, stepIndex, draftItems, view, storySceneIndex,
            packItemSelected, groupPicks, locationPicks, featurePicks,
            household, customGroups, customLocations,
        ],
        saveDraft,
        { deep: true },
    );

    // ── Stock step: picks, own entries, and the panels' sections ─────
    function uniqueSorted(values: (string | null | undefined)[]): string[] {
        const set = new Set<string>();
        for (const v of values) {
            const name = (v ?? '').trim();
            if (name) set.add(name);
        }
        return [...set].sort((a, b) => a.localeCompare(b));
    }
    // The pack items the user has ticked (catalog packs ∩ packItemSelected),
    // deduped by name (the server dedupes again on create).
    const selectedPackItemsList = computed<StarterPackItem[]>(() => {
        const out: StarterPackItem[] = [];
        const seen = new Set<string>();
        for (const pack of catalog.value?.packs ?? []) {
            for (const item of pack.items) {
                if (packItemSelected[item.name] && !seen.has(item.name)) {
                    seen.add(item.name);
                    out.push(item);
                }
            }
        }
        return out;
    });

    // A location pick is a leaf: a zone's children ("Kitchen/Fridge"), or the
    // zone itself when it has none. Picking a child creates its zone too
    // (the server does that), so a zone is never a separate tick.
    const locationLeafPaths = computed<string[]>(() => {
        const out: string[] = [];
        for (const zone of catalog.value?.locations ?? []) {
            if (zone.children.length === 0) out.push(zone.name);
            for (const child of zone.children) out.push(`${zone.name}/${child.name}`);
        }
        return out;
    });
    const pickedLocationPaths = computed<string[]>(() =>
        locationLeafPaths.value.filter((path) => locationPicks[path.toLowerCase()]),
    );
    const locationPickCount = computed(() => pickedLocationPaths.value.length);
    const pickedLocationNames = computed<string[]>(() =>
        pickedLocationPaths.value.flatMap((path) => path.split('/')),
    );
    const pickedGroupNames = computed<string[]>(() =>
        (catalog.value?.groups ?? []).filter((n) => groupPicks[n.toLowerCase()]),
    );
    const groupPickCount = computed(() => pickedGroupNames.value.length);

    // Item group/location pickers offer NAMES (resolved server-side on
    // Finish, FU-191): what the user picked or added on this step, plus
    // whatever already exists.
    const groupNameOptions = computed(() =>
        uniqueSorted([
            ...pickedGroupNames.value,
            ...customGroups.value,
            ...stockGroups.value.map((g) => g.name),
        ]),
    );
    const locationNameOptions = computed(() =>
        uniqueSorted([
            ...pickedLocationNames.value,
            ...customLocations.value,
            ...stockLocationStore.stockLocations.map((l) => l.name),
        ]),
    );

    const OWN_SECTION_LABEL = 'Your own';
    const locationSections = computed<PickSection[]>(() => {
        const sections: PickSection[] = (catalog.value?.locations ?? []).map((zone) => ({
            key: zone.name,
            label: zone.name,
            options: zone.children.length === 0
                ? [{ key: zone.name.toLowerCase(), label: zone.name }]
                : zone.children.map((child) => ({
                    key: `${zone.name}/${child.name}`.toLowerCase(),
                    label: child.name,
                })),
        }));
        if (customLocations.value.length > 0) {
            sections.push({
                key: 'own',
                label: OWN_SECTION_LABEL,
                options: customLocations.value.map((name) => ({ key: name, label: name, removable: true })),
            });
        }
        return sections;
    });
    const groupSections = computed<PickSection[]>(() => [{
        key: 'defaults',
        options: [
            ...(catalog.value?.groups ?? []).map((name) => ({ key: name.toLowerCase(), label: name })),
            ...customGroups.value.map((name) => ({ key: name, label: name, removable: true })),
        ],
    }]);
    const itemSections = computed<PickSection[]>(() => {
        const sections: PickSection[] = (catalog.value?.packs ?? []).map((pack) => ({
            key: pack.key,
            label: pack.label,
            options: pack.items.map((item) => ({ key: item.name, label: item.name })),
        }));
        if (draftItems.value.length > 0) {
            sections.push({
                key: 'own',
                label: OWN_SECTION_LABEL,
                options: draftItems.value.map((item) => {
                    const caption = [item.group_name, item.location_name].filter(Boolean).join(' · ');
                    return {
                        key: item.name, label: item.name, removable: true,
                        ...(caption ? { caption } : {}),
                    };
                }),
            });
        }
        return sections;
    });

    function hasName(names: string[], name: string): boolean {
        const needle = name.toLowerCase();
        return names.some((n) => n.toLowerCase() === needle);
    }
    type OwnKind = 'groups' | 'locations';
    function ownList(kind: OwnKind) {
        return kind === 'groups' ? customGroups : customLocations;
    }
    function addOwnName(kind: OwnKind, name: string) {
        const list = ownList(kind);
        if (!hasName(list.value, name)) list.value.push(name);
    }
    function removeOwnName(kind: OwnKind, name: string) {
        const list = ownList(kind);
        list.value = list.value.filter((n) => n !== name);
    }
    function addOwnItem(name: string) {
        if (hasName(draftItems.value.map((d) => d.name), name)) return;
        draftItems.value.push({
            name,
            group_name: ownItem.group_name,
            location_name: ownItem.location_name,
        });
    }
    function removeOwnItem(name: string) {
        draftItems.value = draftItems.value.filter((d) => d.name !== name);
    }

    // ── Navigation ───────────────────────────────────────────────────
    function onBack() {
        // On the first setup step, "Back" returns the user to the story
        // section instead of being a dead-end disabled button.
        if (stepIndex.value === 0) {
            view.value = 'story';
            return;
        }
        stepIndex.value--;
    }

    // Next / Finish. Advancing a step has NO side effects now — every
    // choice (prefs, seeds, queued items) is applied once, in complete(),
    // so a mid-wizard bail leaves the account untouched (L35). The final
    // step triggers that one-shot apply.
    function advance() {
        if (isLastStep.value) {
            void finish('/');
            return;
        }
        stepIndex.value++;
    }

    // Finish (or "Show me X") = apply the draft, then navigate. On a failed
    // apply we stay put with the error shown so the user can fix + retry.
    async function finish(destination: string) {
        if (await complete()) void router.push(destination);
    }

    // Apply everything the user chose, once, in dependency order: prefs →
    // persona → seed catalogues → stock items (pack picks + queued first
    // items), so the items resolve against the groups/locations just seeded.
    async function applyDraft() {
        await persistPreferences();
        // Features before seeding so anything the seed or items pass reads
        // (e.g. stocktake defaults) sees the household's choice.
        const featureUpdates = changedFeatureSettings.value;
        const householdUpdates = changedHouseholdSettings.value;
        if (Object.keys(featureUpdates).length > 0 || Object.keys(householdUpdates).length > 0) {
            const saved = await appSettingsStore.saveAsync({ ...featureUpdates, ...householdUpdates });
            featureBaseline.value = { ...featurePicks };
            householdBaseline.value = {
                headcount: saved.household_headcount,
                timezone: saved.timezone,
                measurementSystem: saved.measurement_system,
            };
            await Promise.all([refreshFeatureFlags(), refreshCookingPolicy(), reloadMeasurementSystem()]);
        }
        // send the actual picked names/paths. Master bool is
        // implicit: it's true whenever any pick under it survives.
        const groupsWanted = groupPickCount.value > 0;
        const locationsWanted = locationPickCount.value > 0;
        if (groupsWanted || locationsWanted) {
            const totalGroups = catalog.value?.groups.length ?? 0;
            const totalLocations = locationLeafPaths.value.length;
            const allGroupsPicked = groupPickCount.value === totalGroups;
            const allLocationsPicked = locationPickCount.value === totalLocations;
            await onboardingApi.seedAsync({
                groups: groupsWanted,
                locations: locationsWanted,
                // Null when the user wants everything → matches the "seed
                // all defaults" semantic on the server (and keeps the wire
                // payload tiny in the common case).
                group_names: groupsWanted && !allGroupsPicked
                    ? pickedGroupNames.value : null,
                location_paths: locationsWanted && !allLocationsPicked
                    ? pickedLocationPaths.value : null,
            });
        }
        await createOwnGroupsAndLocations();
        // Pack picks + own items, created by NAME (server resolves group /
        // location against the just-seeded catalogues — FU-191 — and dedupes).
        const items = [
            ...selectedPackItemsList.value.map((it) => ({
                name: it.name,
                group_name: it.group,
                location_name: it.location,
            })),
            ...draftItems.value.map((d) => ({
                name: d.name,
                group_name: d.group_name,
                location_name: d.location_name,
            })),
        ];
        if (items.length > 0) {
            await onboardingApi.seedItemsAsync({ items });
        }
        // optional demo dataset. After the items pass so the demo
        // can reuse a starter-pack "Spaghetti pasta" / "Garlic" / "Olive oil"
        // if the user picked them; otherwise the demo creates its own. The
        // server is idempotent (`seeded: false` when the demo recipe already
        // exists) so a re-finish never duplicates.
        if (form.seedDemo) {
            await onboardingApi.seedDemoAsync();
        }
    }

    // The user's own groups and locations, through the same create endpoints
    // the stock pages use. Runs after the defaults are seeded so a name that
    // now exists (seeded, or there from before) is skipped, not duplicated.
    async function createOwnGroupsAndLocations() {
        if (customGroups.value.length > 0) {
            await loadStockGroups();
            const existing = stockGroups.value.map((g) => g.name);
            for (const name of customGroups.value) {
                if (!hasName(existing, name)) await stockGroupStore.createAsync(name);
            }
        }
        if (customLocations.value.length > 0) {
            await stockLocationStore.getStockLocationsAsync();
            const existing = stockLocationStore.stockLocations.map((l) => l.name);
            for (const name of customLocations.value) {
                if (!hasName(existing, name)) {
                    await stockLocationStore.createStockLocationAsync({ name });
                }
            }
        }
    }

    function handleApplyError(err: unknown) {
        const extracted = extractFieldErrors(err);
        const remainingFields = Object.values(extracted.fieldErrors).filter(Boolean);
        loadError.value =
            [extracted.generalError, ...remainingFields].filter(Boolean).join(' ') ||
            "Couldn't finish setting up. Please try again.";
    }

    async function persistPreferences() {
        // Display name is no longer collected here — it's fixed at account
        // creation (the username picked at register time). Onboarding only
        // touches personal look (theme + font); household cooking config
        // (headcount + cook-style) is install-wide now (FU-615).
        const updates: Record<string, unknown> = {};
        if (form.theme !== currentUser.value?.theme) {
            updates.theme = form.theme;
        }
        if (form.fontFamily !== currentUser.value?.font_family) {
            updates.font_family = form.fontFamily;
        }
        if (form.avatarDataUrl) {
            updates.image = form.avatarDataUrl;
        }
        if (Object.keys(updates).length === 0) return;
        await authStore.updateMeAsync(updates);
    }

    function onShowMe(path: string) {
        // "Show me X" = finish onboarding (applying the draft), then land on
        // that screen.
        void finish(path);
    }

    async function onSkipEverything() {
        completing.value = true;
        try {
            // Persist the timestamp + drop a flag so the dashboard can
            // show a 24h "finish setting up" banner.
            await onboardingApi.completeAsync();
            // Refresh the cached user so the router guard sees the new
            // `onboarding_completed_at`. Without this, the guard reads the
            // stale (null) value and bounces the user straight back to
            // /welcome — making the button look dead until a hard refresh.
            await authStore.refreshAsync();
            try {
                localStorage.setItem(
                    'dora.onboarding.skipped_at',
                    new Date().toISOString(),
                );
            } catch {
                // Ignore — banner just won't fire.
            }
            clearDraft();
            void router.push('/');
        } catch (err) {
            const extracted = extractFieldErrors(err);
            loadError.value =
                extracted.generalError ?? "Couldn't skip onboarding. Please try again.";
        } finally {
            completing.value = false;
        }
    }

    // Apply the collected draft + stamp completion. Returns true on success;
    // the caller navigates (Finish → '/', Show-me → the chosen path) so a
    // failed apply keeps the user in the wizard with the error shown.
    async function complete(): Promise<boolean> {
        completing.value = true;
        loadError.value = null;
        try {
            await applyDraft();
            await onboardingApi.completeAsync();
            // Refresh the cached user so the router guard sees the new
            // `onboarding_completed_at`. Without this, Finish / Show-me-X
            // navigations bounce straight back to /welcome on the first
            // attempt (the guard reads stale null); user only escapes
            // after a hard refresh re-bootstraps the auth state.
            await authStore.refreshAsync();
            // The picture is saved now; drop the draft copy so a re-run of
            // the wizard doesn't re-upload it.
            form.avatarDataUrl = null;
            form.avatarPresetKey = null;
            clearDraft();
            // Clear any stale "skipped" flag so the dashboard banner
            // doesn't reappear after a proper completion.
            try {
                localStorage.removeItem('dora.onboarding.skipped_at');
            } catch {
                // Ignore.
            }
            return true;
        } catch (err) {
            handleApplyError(err);
            return false;
        } finally {
            completing.value = false;
        }
    }

    onMounted(async () => {
        try {
            state.value = await onboardingApi.getStateAsync();
        } catch (err) {
            const extracted = extractFieldErrors(err);
            loadError.value =
                extracted.generalError ?? "Couldn't load onboarding state. Please refresh.";
        }
        // Seed theme/font from the user's saved values, then layer the saved
        // draft on top. Display name is set at account creation; household
        // cooking config is install-wide (FU-615) — neither is collected here.
        if (currentUser.value) {
            // Pre-fill from the user's saved prefs. If their stored theme
            // isn't one of the three onboarding options (e.g. they picked a
            // richer palette in Preferences on a re-run), the select shows
            // blank and persistPreferences leaves it untouched — we never
            // clobber a real choice.
            form.theme = currentUser.value.theme ?? 'system';
            form.fontFamily = coalesceFontFamily(currentUser.value.font_family);
        }
        loadDraft();
        stepIndex.value = Math.min(stepIndex.value, visibleSteps.value.length - 1);
        void loadFeatureBaseline();

        // Pre-load existing groups/locations (so the first-item name pickers
        // include what's already there) + the starter catalogue (default
        // names + packs to preview and pick from).
        await Promise.all([
            loadStockGroups(),
            stockLocationStore.stockLocations.length === 0
                ? stockLocationStore.getStockLocationsAsync()
                : Promise.resolve(),
            loadCatalog(),
        ]);
    });
</script>

<style scoped>
    .wizard-shell {
        max-width: 720px;
    }
    /* Slim top row — mascot · progress rail · skip escape — with generous
       horizontal spacing between the three so it reads as one clean band. */
    .wizard-topbar {
        display: flex;
        align-items: center;
        gap: var(--space-5);
    }
    .wizard-topbar-rail {
        flex: 1 1 auto;
        min-width: 0;
    }
    .wizard-mascot,
    .wizard-skip {
        flex: 0 0 auto;
    }
    /* Bounds the absolutely-positioned finish confetti to the step. */
    .finish-step {
        position: relative;
    }
    /* ── Welcome step (2026-10-17 rebuild) ─────────────────────────── */
    .welcome-step {
        display: flex;
        flex-direction: column;
        gap: var(--space-4);
    }
    .welcome-hero {
        display: flex;
        align-items: center;
        gap: var(--space-5);
        padding: var(--space-5);
        border-radius: var(--radius-lg);
        background: var(--hero-gradient);
        border: 1px solid var(--border-default);
    }
    .welcome-hero__avatar {
        position: relative;
        flex: 0 0 auto;
    }
    .welcome-hero__avatar :deep(.image-edit-tile) {
        box-shadow: 0 0 0 4px var(--surface-component), 0 8px 24px var(--overlay-active);
        border-radius: 50%;
    }
    .welcome-hero__mascot {
        position: absolute;
        right: -14px;
        bottom: -10px;
        width: 44px;
        height: 44px;
        pointer-events: none;
        filter: drop-shadow(0 2px 4px var(--overlay-active));
    }
    .welcome-hero__copy {
        min-width: 0;
    }
    .welcome-hero__kicker {
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--brand-secondary);
    }
    .welcome-hero__title {
        margin: 2px 0 6px;
        font-size: 1.6rem;
        line-height: 1.2;
        font-weight: 700;
        color: var(--text-primary);
        overflow-wrap: anywhere;
    }
    .welcome-hero__blurb {
        margin: 0;
        font-size: 0.95rem;
        line-height: 1.5;
        color: var(--text-secondary);
    }
    .welcome-panel {
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
        padding: var(--space-4) var(--space-5);
        border-radius: var(--radius-lg);
        background: var(--surface-component);
        border: 1px solid var(--border-default);
    }
    .welcome-panel__title {
        font-size: 1rem;
        font-weight: 700;
        color: var(--text-primary);
    }
    .welcome-panel__sub {
        font-size: 0.85rem;
        color: var(--text-muted);
    }
    .welcome-panel__foot {
        display: flex;
        align-items: center;
        min-height: 32px;
    }
    .welcome-themes {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: var(--space-3);
    }
    .welcome-theme {
        position: relative;
        appearance: none;
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
        padding: var(--space-2);
        border: 1.5px solid var(--border-default);
        border-radius: var(--radius-md);
        background: var(--surface-component);
        color: var(--text-primary);
        cursor: pointer;
        text-align: left;
        transition: border-color var(--motion-fast) var(--motion-ease),
            transform var(--motion-fast) var(--motion-ease);
    }
    .welcome-theme:hover {
        border-color: var(--border-strong);
        transform: translateY(-1px);
    }
    .welcome-theme:focus-visible {
        outline: 2px solid var(--accent-mark);
        outline-offset: 2px;
    }
    .welcome-theme--active {
        border-color: var(--accent-mark);
        border-width: 2px;
    }
    .welcome-theme__preview {
        display: flex;
        height: 64px;
        border-radius: var(--radius-sm);
        overflow: hidden;
        border: 1px solid var(--border-default);
    }
    /* Each half is painted in its own theme's tokens via `data-theme`. */
    .welcome-theme__half {
        flex: 1 1 0;
        display: flex;
        flex-direction: column;
        gap: 5px;
        padding: 0 0 6px;
        background: var(--surface-page);
        position: relative;
    }
    .welcome-theme__bar {
        height: 12px;
        background: var(--brand-primary);
    }
    .welcome-theme__line {
        height: 6px;
        margin: 0 8px;
        border-radius: 3px;
        background: var(--surface-component);
    }
    .welcome-theme__line--short {
        width: 45%;
    }
    .welcome-theme__dot {
        position: absolute;
        right: 8px;
        bottom: 6px;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: var(--brand-accent);
    }
    .welcome-theme__label {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 0.875rem;
        font-weight: 600;
    }
    .welcome-theme__badge {
        position: absolute;
        top: 4px;
        right: 4px;
        color: var(--accent-mark);
        background: var(--surface-component);
        border-radius: 50%;
    }
    .welcome-font {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    .welcome-font__label {
        font-size: 0.85rem;
        font-weight: 600;
        color: var(--text-secondary);
    }

    /* ── Features step ─────────────────────────────────────────────── */
    .features-step__head {
        margin-bottom: var(--space-4);
    }
    .feature-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr));
        gap: var(--space-3);
    }
    .feature-card {
        appearance: none;
        display: flex;
        align-items: center;
        gap: var(--space-3);
        padding: var(--space-3) var(--space-4);
        border: 1.5px solid var(--border-default);
        border-radius: var(--radius-lg);
        background: var(--surface-component);
        color: var(--text-primary);
        text-align: left;
        cursor: pointer;
        transition: border-color var(--motion-fast) var(--motion-ease),
            background var(--motion-fast) var(--motion-ease),
            transform var(--motion-fast) var(--motion-ease);
    }
    .feature-card:hover:not(:disabled) {
        border-color: var(--border-strong);
        transform: translateY(-1px);
    }
    .feature-card:focus-visible {
        outline: 2px solid var(--accent-mark);
        outline-offset: 2px;
    }
    .feature-card:disabled {
        cursor: default;
        opacity: 0.6;
    }
    .feature-card--on {
        border-color: var(--brand-primary);
        background: color-mix(in srgb, var(--brand-primary-soft) 45%, var(--surface-component));
    }
    .feature-card__icon {
        flex: 0 0 auto;
        width: 44px;
        height: 44px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: color-mix(in srgb, var(--text-muted) 16%, var(--surface-component));
        color: var(--text-secondary);
        transition: background var(--motion-fast) var(--motion-ease),
            color var(--motion-fast) var(--motion-ease);
    }
    .feature-card--on .feature-card__icon {
        background: var(--brand-primary-soft);
        color: var(--brand-primary);
    }
    .feature-card__body {
        flex: 1 1 auto;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .feature-card__title {
        font-size: 0.95rem;
        font-weight: 700;
    }
    .feature-card__desc {
        font-size: 0.82rem;
        line-height: 1.4;
        color: var(--text-secondary);
    }
    .feature-card__state {
        flex: 0 0 auto;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        color: var(--text-muted);
    }
    .feature-card--on .feature-card__state {
        color: var(--brand-primary);
    }
    .feature-card__state-label {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    .household-fields {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-3);
    }
    .household-field {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    .household-field--grow {
        flex: 1 1 220px;
        min-width: 0;
    }
    .household-field__label {
        font-size: 0.85rem;
        font-weight: 600;
        color: var(--text-secondary);
    }
    .household-units {
        align-items: flex-start;
    }
    .household-field__headcount {
        width: 140px;
    }

    /* ── Stock step ────────────────────────────────────────────────── */
    .stock-step {
        display: flex;
        flex-direction: column;
        gap: var(--space-4);
    }
    .stock-step .features-step__head {
        margin-bottom: 0;
    }
    .stock-step__own-select {
        flex: 1 1 140px;
        min-width: 0;
    }

    /* ── Finish step ───────────────────────────────────────────────── */
    .finish-step {
        display: flex;
        flex-direction: column;
        gap: var(--space-4);
    }
    .finish-hero {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        gap: var(--space-2);
        padding: var(--space-5) var(--space-4);
        border-radius: var(--radius-lg);
        background: var(--hero-gradient);
        border: 1px solid var(--border-default);
    }
    .finish-hero__faces {
        display: flex;
        align-items: flex-end;
        justify-content: center;
    }
    .finish-hero__avatar {
        box-shadow: 0 0 0 4px var(--surface-component), 0 8px 24px var(--overlay-active);
        z-index: 1;
    }
    .finish-hero__mascot {
        margin-left: -18px;
    }
    .finish-hero__title {
        font-size: 1.6rem;
        font-weight: 700;
        line-height: 1.2;
        color: var(--text-primary);
        overflow-wrap: anywhere;
    }
    .finish-hero__sub {
        max-width: 30rem;
        font-size: 0.95rem;
        color: var(--text-secondary);
    }
    .finish-panel {
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
    }
    .finish-panel__title {
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-muted);
    }
    .finish-recap {
        list-style: none;
        margin: 0;
        padding: var(--space-1) var(--space-4);
        border-radius: var(--radius-lg);
        background: var(--surface-component);
        border: 1px solid var(--border-default);
    }
    .finish-recap__row {
        display: flex;
        align-items: center;
        gap: var(--space-3);
        min-height: 44px;
        padding: 4px 0;
    }
    .finish-recap__row + .finish-recap__row {
        border-top: 1px solid var(--divider);
    }
    .finish-recap__icon {
        flex: 0 0 auto;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--brand-primary-soft);
        color: var(--brand-primary);
    }
    .finish-recap__text {
        flex: 1 1 auto;
        min-width: 0;
        font-size: 0.9rem;
        color: var(--text-primary);
    }
    .finish-tiles {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr));
        gap: var(--space-3);
    }
    .finish-tile {
        appearance: none;
        display: flex;
        align-items: center;
        gap: var(--space-3);
        padding: var(--space-3) var(--space-4);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        background: var(--surface-component);
        color: var(--text-primary);
        text-align: left;
        cursor: pointer;
        transition: border-color var(--motion-fast) var(--motion-ease),
            transform var(--motion-fast) var(--motion-ease),
            box-shadow var(--motion-fast) var(--motion-ease);
    }
    .finish-tile:hover:not(:disabled) {
        border-color: var(--brand-primary);
        transform: translateY(-2px);
        box-shadow: 0 6px 16px var(--overlay-active);
    }
    .finish-tile:focus-visible {
        outline: 2px solid var(--accent-mark);
        outline-offset: 2px;
    }
    .finish-tile:disabled {
        cursor: default;
        opacity: 0.6;
    }
    .finish-tile__icon {
        flex: 0 0 auto;
        width: 44px;
        height: 44px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--brand-primary-soft);
        color: var(--brand-primary);
    }
    .finish-tile__body {
        flex: 1 1 auto;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .finish-tile__title {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 0.95rem;
        font-weight: 700;
    }
    .finish-tile__num {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        font-size: 0.7rem;
        background: var(--brand-primary);
        color: var(--text-on-primary);
    }
    .finish-tile__desc {
        font-size: 0.82rem;
        line-height: 1.4;
        color: var(--text-secondary);
    }
    .finish-tile__chevron {
        flex: 0 0 auto;
        color: var(--text-muted);
    }
    .finish-tip {
        display: flex;
        align-items: flex-start;
        gap: var(--space-2);
        padding: var(--space-3) var(--space-4);
        border-radius: var(--radius-md);
        background: var(--surface-sunken);
        font-size: 0.875rem;
        color: var(--text-secondary);
    }
    .finish-tip__icon {
        flex: 0 0 auto;
        color: var(--brand-secondary);
    }

    @media (max-width: 599px) {
        .welcome-hero {
            flex-direction: column;
            text-align: center;
            padding: var(--space-4);
        }
        .welcome-panel {
            padding: var(--space-3) var(--space-4);
        }
        .welcome-themes {
            gap: var(--space-2);
        }
    }
</style>
