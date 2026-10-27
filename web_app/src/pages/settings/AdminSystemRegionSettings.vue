<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Region & locale"
            description="Where this household lives. Sets how money and dates are written, which units you measure in, and which day counts as today."
            :icon="ICONS.language"
        />

        <template v-if="!loading">
            <!-- Preview first. The three fields below are abstractions
                 (ISO code, BCP-47 tag, IANA zone) whose only observable effect
                 is this line — so it leads, and it updates as you pick rather
                 than after a save round-trip. -->
            <div class="region-preview">
                <div class="region-preview__row">
                    <span class="region-preview__label">Money</span>
                    <span class="region-preview__value">{{ previewMoney }}</span>
                </div>
                <div class="region-preview__row">
                    <span class="region-preview__label">Dates</span>
                    <span class="region-preview__value">{{ previewDate }}</span>
                </div>
                <div class="region-preview__row">
                    <span class="region-preview__label">Today is</span>
                    <span class="region-preview__value">{{ previewToday }}</span>
                </div>
                <div class="region-preview__row">
                    <span class="region-preview__label">Units</span>
                    <span class="region-preview__value">{{ previewUnits }}</span>
                </div>
                <!-- One button replaces the two "Use this device" buttons that
                     used to sit in separate sections doing overlapping jobs.
                     It fills in everything the browser can actually tell us —
                     zone and locale — and leaves currency alone, because a
                     device in Australia can be spending in USD. -->
                <BaseButton
                    variant="secondary"
                    :icon="ICONS.place"
                    label="Match this device"
                    :disable="saving"
                    class="region-preview__detect"
                    @click="onMatchDevice"
                />
            </div>

            <SettingsSection>
                <SettingsRow
                    label="Currency"
                    help="What your prices are in."
                >
                    <q-select
                        :model-value="currencyDraft"
                        :options="currencyOptions"
                        outlined
                        dense
                        use-input
                        hide-selected
                        fill-input
                        emit-value
                        map-options
                        input-debounce="0"
                        options-dense
                        new-value-mode="add-unique"
                        class="region-field"
                        :error="currencyError !== null"
                        :error-message="currencyError ?? ''"
                        @filter="onCurrencyFilter"
                        @update:model-value="onPickCurrency"
                        @new-value="onPickCurrency"
                        @input-value="currencyTyped = $event"
                        @keydown.enter="onCurrencyEnter"
                        @blur="onCurrencyBlur"
                    />
                </SettingsRow>

                <SettingsRow
                    label="Language & format"
                    help="Decides symbol placement, decimal marks and date order."
                >
                    <q-select
                        :model-value="localeDraft"
                        :options="localeOptions"
                        outlined
                        dense
                        use-input
                        hide-selected
                        fill-input
                        emit-value
                        map-options
                        input-debounce="0"
                        options-dense
                        new-value-mode="add-unique"
                        class="region-field"
                        :error="localeError !== null"
                        :error-message="localeError ?? ''"
                        @filter="onLocaleFilter"
                        @update:model-value="onPickLocale"
                        @new-value="onPickLocale"
                        @input-value="localeTyped = $event"
                        @keydown.enter="onLocaleEnter"
                        @blur="onLocaleBlur"
                    />
                </SettingsRow>

                <!-- Owner feedback 2026-08-27: *"Locale and region settings
                     should also include units config, which then determines
                     what units appear throughout the app."* It belongs beside
                     currency and language for the same reason those two sit
                     together — all three are "where does this household
                     live?", expressed as conventions rather than as a country.
                     A plain radio-style select: three options, all visible, no
                     free text (an unlisted measurement system does not exist
                     the way an unlisted currency does). -->
                <SettingsRow
                    label="Units"
                    help="Which units the app offers when you enter a quantity or a price."
                >
                    <q-select
                        :model-value="systemDraft"
                        :options="MEASUREMENT_SYSTEM_CHOICES"
                        outlined
                        dense
                        emit-value
                        map-options
                        options-dense
                        class="region-field"
                        :disable="saving"
                        @update:model-value="onPickSystem"
                    />
                </SettingsRow>

                <SettingsRow
                    label="Timezone"
                    help="Fixes the &quot;today&quot; boundary, wherever the server runs."
                >
                    <q-select
                        :model-value="timezoneDraft"
                        :options="timezoneOptions"
                        outlined
                        dense
                        use-input
                        hide-selected
                        fill-input
                        input-debounce="0"
                        options-dense
                        class="region-field"
                        @filter="onTimezoneFilter"
                        @update:model-value="onSaveTimezone"
                    />
                </SettingsRow>
            </SettingsSection>
        </template>
    </div>
</template>

<script lang="ts" setup>
    // Owner call 2026-08-17 — the page was three stacked essays around four
    // bare text inputs, explaining ISO 4217 and BCP-47 to someone who just
    // wants dollars and DD/MM. Rebuilt around what the settings actually *do*:
    // a live preview at the top, then three labelled pickers with one line of
    // help each. Currency and locale became searchable selects of real
    // options (free text still accepted, for anything not on the list), and
    // the two scattered "Use this device" buttons collapsed into one.
    import { ICONS } from 'src/style/icons';
    import { useQuasar } from 'quasar';
    import BaseButton from 'src/components/BaseButton.vue';
    import { useAppSettingsStore } from 'src/stores/appSettingsStore';
    import { computed, onMounted, ref } from 'vue';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import { refreshMoneyPolicy } from 'src/composables/useMoney';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import {
        CURRENCY_CHOICES, LOCALE_CHOICES, MEASUREMENT_SYSTEM_CHOICES, TIMEZONE_CHOICES,
    } from 'src/models/regionChoices';
    import { unitsForSystem, useMeasurementSystem } from 'src/composables/useMeasurementSystem';
    import type { MeasurementSystem } from 'src/generated/units_table';
    import { useRecipeStore } from 'src/stores/recipeStore';
    import { useConfirm } from 'src/composables/useConfirm';

    const $q = useQuasar();

    const { confirm } = useConfirm();
    // Reads and writes go through the shared settings row (13-R9). The page
    // keeps its own save handlers: picks save silently, with inline errors
    // and double-submit guards the generic draft loop doesn't have.
    const settingsStore = useAppSettingsStore();
    // The Health Star Rating nudge flips an install-wide flag that /api/health
    // publishes, so the cached map has to be re-read or the cookbook and recipe
    // page keep running on the stale answer until a reload.
    const { refresh: refreshFlags } = useFeatureFlags();
    const { reload: reloadMeasurementSystem } = useMeasurementSystem();

    const loading = ref(true);
    const saving = ref(false);

    const timezoneDraft = ref<string>('UTC');
    const systemDraft = ref<MeasurementSystem>('metric');
    let lastSavedSystem: MeasurementSystem = 'metric';

    const currencyDraft = ref<string>('AUD');
    const localeDraft = ref<string>('en-AU');
    const currencyError = ref<string | null>(null);
    const localeError = ref<string | null>(null);

    // Last-saved values, so a re-pick of the same option is a no-op instead of
    // a redundant PATCH.
    let lastSavedCurrency = 'AUD';
    let lastSavedLocale = 'en-AU';

    // What's currently *typed* into each combobox, tracked so leaving the
    // field commits it. `@new-value` alone only fires on Enter-with-the-popup-
    // open; someone who types "USD" and clicks away would otherwise be left
    // looking at a field that says USD while the install is still on AUD —
    // silently ignoring input is worse than rejecting it.
    const currencyTyped = ref('');
    const localeTyped = ref('');

    /** True when the text is one of the list's display labels rather than
     *  something the user typed. `fill-input` writes the label into the input
     *  after a pick ("AUD — Australian dollar"), so a commit path that didn't
     *  check this would try to save a display string. */
    function isChoiceLabel(choices: readonly { label: string }[], text: string): boolean {
        return choices.some((c) => c.label === text);
    }

    // Free text (a currency or language the shortlist doesn't carry) commits on
    // BOTH Enter and blur. Quasar's own `new-value-mode` Enter handling only
    // runs while the options popup is open, so typing a code and tabbing away
    // would otherwise be silently dropped — and an install in an unlisted
    // country would have no way to set its currency at all.
    //
    // Committing twice is harmless: `pendingCurrency` / `pendingLocale` below
    // swallow the duplicate, and the label guard means the post-pick reset
    // (`fill-input` rewrites the field to "AUD — Australian dollar") is never
    // mistaken for input. Both event orderings are therefore safe.
    //
    // The shape checks are deliberately silent rather than error-raising: a
    // half-typed "US" abandoned on blur should just be dropped, not shouted at.
    function onCurrencyEnter() { commitCurrency(); }
    function onCurrencyBlur() { commitCurrency(); }
    function onLocaleEnter() { commitLocale(); }
    function onLocaleBlur() { commitLocale(); }

    function commitCurrency() {
        const typed = currencyTyped.value.trim();
        if (!typed || isChoiceLabel(CURRENCY_CHOICES, typed)) return;
        if (!/^[A-Za-z]{3}$/.test(typed)) return;
        void onPickCurrency(typed);
    }

    function commitLocale() {
        const typed = localeTyped.value.trim();
        if (!typed || isChoiceLabel(LOCALE_CHOICES, typed)) return;
        try {
            new Intl.Locale(typed);
        } catch {
            return;
        }
        void onPickLocale(typed);
    }

    // ── Preview ───────────────────────────────────────────────────────
    // Built here from the *draft* values with plain Intl, not via
    // useMoney/useDateFormat: those two read the install's saved policy (they
    // are the authority for every real render in the app, R-003), which is
    // exactly the wrong thing for a preview of a choice you haven't committed.
    // Pure display maths on values already in hand — no server round-trip.
    function safeFormat(build: () => string, fallback: string): string {
        // An unsaved free-text entry can be a not-yet-valid tag/code, and Intl
        // throws on those. The preview should go quiet, not blow up the page.
        try {
            return build();
        } catch {
            return fallback;
        }
    }

    const previewMoney = computed(() => safeFormat(
        () => {
            const fmt = new Intl.NumberFormat(localeDraft.value, {
                style: 'currency', currency: currencyDraft.value,
            });
            return `${fmt.format(12.5)}  ·  ${fmt.format(1234.56)}`;
        },
        '–',
    ));

    const previewDate = computed(() => safeFormat(
        () => {
            const sample = new Date(2026, 11, 31);
            const short = new Intl.DateTimeFormat(localeDraft.value).format(sample);
            const long = new Intl.DateTimeFormat(localeDraft.value, {
                dateStyle: 'medium',
            }).format(sample);
            return `${short}  ·  ${long}`;
        },
        '–',
    ));

    const previewToday = computed(() => safeFormat(
        () => new Intl.DateTimeFormat(localeDraft.value, {
            weekday: 'long', day: 'numeric', month: 'long',
            timeZone: timezoneDraft.value,
        }).format(new Date()),
        '–',
    ));

    /** A handful of representative units from the chosen system, so the effect
     *  of the setting is visible in the preview block alongside money and
     *  dates rather than only discoverable by opening a dropdown elsewhere.
     *  Drawn from the same generated mapping the pickers use (R-003), then cut
     *  to a readable sample — this is a preview, not the vocabulary. */
    const PREVIEW_UNIT_ORDER = ['ml', 'L', 'fl oz', 'pt', 'qt', 'g', 'kg', 'oz', 'lb', 'cup', 'US cup'];
    const previewUnits = computed(() => {
        const offered = unitsForSystem(systemDraft.value);
        return PREVIEW_UNIT_ORDER.filter((u) => offered.has(u)).join(' · ');
    });

    // ── Option lists ──────────────────────────────────────────────────
    const currencyOptions = ref([...CURRENCY_CHOICES]);
    function onCurrencyFilter(val: string, update: (cb: () => void) => void) {
        update(() => {
            const needle = val.toLowerCase();
            currencyOptions.value = needle
                ? CURRENCY_CHOICES.filter((c) => c.label.toLowerCase().includes(needle))
                : [...CURRENCY_CHOICES];
        });
    }

    const localeOptions = ref([...LOCALE_CHOICES]);
    function onLocaleFilter(val: string, update: (cb: () => void) => void) {
        update(() => {
            const needle = val.toLowerCase();
            localeOptions.value = needle
                ? LOCALE_CHOICES.filter((l) => l.label.toLowerCase().includes(needle))
                : [...LOCALE_CHOICES];
        });
    }

    const timezoneOptions = ref<string[]>([...TIMEZONE_CHOICES]);
    function onTimezoneFilter(val: string, update: (cb: () => void) => void) {
        update(() => {
            const needle = val.toLowerCase();
            timezoneOptions.value = needle
                ? TIMEZONE_CHOICES.filter((t) => t.toLowerCase().includes(needle))
                : [...TIMEZONE_CHOICES];
        });
    }

    // ── Saving ────────────────────────────────────────────────────────
    async function onSaveTimezone(value: string) {
        if (!value || value === timezoneDraft.value) return;
        const previous = timezoneDraft.value;
        timezoneDraft.value = value;   // preview follows the pick immediately
        saving.value = true;
        try {
            const result = await settingsStore.saveAsync({ timezone: value });
            timezoneDraft.value = result.timezone;
        } catch (err) {
            timezoneDraft.value = previous;
            $q.notify({
                type: 'negative', 
                message: 'Could not save the timezone.',
                caption: toastCaption(err),
            });
        } finally {
            saving.value = false;
        }
    }

    // Guards a double-submit: with the popup open, Quasar's own `new-value`
    // handling and the explicit Enter handler both fire for the same
    // keystroke, and `lastSaved*` doesn't update until the PATCH resolves.
    let pendingCurrency: string | null = null;
    let pendingLocale: string | null = null;

    async function onPickCurrency(raw: string | null) {
        const value = String(raw ?? '').trim().toUpperCase();
        if (!value || value === lastSavedCurrency || value === pendingCurrency) return;
        pendingCurrency = value;
        currencyDraft.value = value;
        if (!/^[A-Z]{3}$/.test(value)) {
            currencyError.value = 'Must be a 3-letter code, like AUD or USD.';
            pendingCurrency = null;
            return;
        }
        currencyError.value = null;
        saving.value = true;
        try {
            const result = await settingsStore.saveAsync({ currency: value });
            currencyDraft.value = result.currency;
            lastSavedCurrency = result.currency;
            await refreshMoneyPolicy();
        } catch (err) {
            currencyError.value = 'Could not save the currency.';
            $q.notify({
                type: 'negative', 
                message: 'Could not save the currency.',
                caption: toastCaption(err),
            });
        } finally {
            saving.value = false;
            pendingCurrency = null;
        }
    }

    async function onPickLocale(raw: string | null) {
        const value = String(raw ?? '').trim();
        if (!value || value === lastSavedLocale || value === pendingLocale) return;
        pendingLocale = value;
        localeDraft.value = value;
        // Ask the browser's own Intl.Locale to parse it before the round-trip
        // — same BCP-47 check the server runs, without the latency.
        try {
            new Intl.Locale(value);
        } catch {
            localeError.value = 'Not a valid language tag, like en-AU.';
            pendingLocale = null;
            return;
        }
        localeError.value = null;
        saving.value = true;
        try {
            const result = await settingsStore.saveAsync({ locale: value });
            localeDraft.value = result.locale;
            lastSavedLocale = result.locale;
            await refreshMoneyPolicy();
        } catch (err) {
            localeError.value = 'Could not save the language.';
            $q.notify({
                type: 'negative', 
                message: 'Could not save the language.',
                caption: toastCaption(err),
            });
        } finally {
            saving.value = false;
            pendingLocale = null;
        }
    }

    async function onPickSystem(value: MeasurementSystem) {
        if (!value || value === lastSavedSystem) return;
        const previous = systemDraft.value;
        systemDraft.value = value;   // preview follows the pick immediately
        saving.value = true;
        try {
            const result = await settingsStore.saveAsync({ measurement_system: value });
            systemDraft.value = result.measurement_system;
            lastSavedSystem = result.measurement_system;
            // Same reason the currency save calls `refreshMoneyPolicy`: the
            // value the rest of the app reads is the cached /api/health copy,
            // so without this every unit dropdown keeps offering the old
            // system's units until a page reload.
            await reloadMeasurementSystem();
        } catch (err) {
            systemDraft.value = previous;
            $q.notify({
                type: 'negative', 
                message: 'Could not save the unit system.',
                caption: toastCaption(err),
            });
        } finally {
            saving.value = false;
        }
    }

    async function onMatchDevice() {
        const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        const language = (typeof navigator !== 'undefined' && navigator.language) || '';
        if (zone) await onSaveTimezone(zone);
        if (language) await onPickLocale(language);
        const detected = systemForRegion(language);
        if (detected) await onPickSystem(detected);
        $q.notify({
            type: 'positive', 
            message: 'Matched to this device. Currency is unchanged.',
        });
        void offerRatingScheme(language, zone);
    }

    /** The measurement system implied by a device's BCP-47 region subtag, or
     *  null when we can't tell and shouldn't guess.
     *
     *  Only three regions get a non-metric answer, and the list is short
     *  because it is genuinely short: the United States (and its territories
     *  that follow it) use US customary; the UK uses metric-plus-imperial;
     *  everywhere else is metric. Unlike the timezone-first rule the Health
     *  Star nudge needed, this reads the *language tag* — an en-GB machine in
     *  Sydney is telling us which conventions its user reads in, which is
     *  exactly the question here, whereas the HSR prompt was asking where the
     *  device physically is.
     *
     *  Returning null rather than 'metric' for an unparseable tag matters:
     *  "Match this device" should leave a deliberately-chosen setting alone
     *  when it learns nothing, not reset it. */
    function systemForRegion(language: string): MeasurementSystem | null {
        if (!language) return null;
        let region: string | undefined;
        try {
            region = new Intl.Locale(language).region ?? undefined;
        } catch {
            region = undefined;
        }
        if (!region) {
            const upper = language.toUpperCase();
            const match = /-([A-Z]{2})$/.exec(upper);
            region = match?.[1];
        }
        if (!region) return null;
        if (region === 'US' || region === 'PR' || region === 'GU') return 'us';
        if (region === 'GB') return 'imperial';
        return 'metric';
    }

    /** Owner's call 2026-08-27 — a recipe rating ships off everywhere, because
     *  both schemes are national programmes and no install should be handed
     *  one as though it were universal. But that leaves the people each was
     *  designed for hunting for a setting they have no reason to know exists,
     *  so detecting the device's region is the one moment where offering the
     *  locally recognised scheme is useful rather than presumptuous.
     *
     *  Offers *one* scheme — whichever matches the device — rather than
     *  presenting the menu. Someone in Lyon does not need to be asked to
     *  choose between the Australian scheme and the European one; they need to
     *  be told the European one exists. The full picker is in Settings →
     *  Nutrition for anyone who wants the other.
     *
     *  Offered, never applied: this asks, and a "No thanks" is remembered by
     *  simply leaving the setting at `none`. Nothing here nags again — the
     *  prompt is attached to an explicit button press, not to page load. */
    async function offerRatingScheme(language: string, zone: string) {
        const scheme = localRatingScheme(language, zone);
        if (scheme === null) return;
        // The row is current: every save on this page wrote through the store.
        // Already chosen something, including deliberately choosing one
        // scheme in the other's region: not our place to second-guess it.
        if (settingsStore.settings?.nutrition_rating_scheme !== 'none') return;

        const copy = scheme === 'health_star'
            ? {
                title: 'Turn on Health Star Ratings?',
                where: 'in Australia or New Zealand, where the Health Star '
                    + 'Rating is the standard front-of-pack guide',
            }
            : {
                title: 'Turn on Nutri-Score?',
                where: 'somewhere Nutri-Score is the standard front-of-pack '
                    + 'guide',
            };

        const ok = await confirm({
            title: copy.title,
            message:
                `This device looks like it's ${copy.where}. Dora `
                + 'can work one out for your recipes. '
                + 'It needs nutrition set to complex, and ratings are estimates.',
            okLabel: 'Turn it on',
            cancelLabel: 'No thanks',
        });
        if (ok) await enableRatingScheme(scheme);
    }

    /** The countries currently using Nutri-Score, by BCP-47 region subtag:
     *  France, Belgium, Germany, the Netherlands, Luxembourg, Spain and
     *  Switzerland. Kept as an explicit list rather than "Europe" — most of
     *  Europe has not adopted it, and offering it to an install in Warsaw
     *  would be exactly the presumption this whole design avoids. */
    const NUTRI_SCORE_REGIONS = ['FR', 'BE', 'DE', 'NL', 'LU', 'ES', 'CH'];

    /** IANA zones for the same set, for the timezone-first read below. */
    const NUTRI_SCORE_ZONES = [
        'Europe/Paris', 'Europe/Brussels', 'Europe/Berlin', 'Europe/Busingen',
        'Europe/Amsterdam', 'Europe/Luxembourg', 'Europe/Madrid',
        'Atlantic/Canary', 'Africa/Ceuta', 'Europe/Zurich',
    ];

    /** Which scheme, if any, this device's region recognises. Null means "no
     *  local scheme" — most of the world — and nothing is offered. */
    function localRatingScheme(
        language: string, zone: string,
    ): 'health_star' | 'nutri_score' | null {
        if (isAustralasian(language, zone)) return 'health_star';
        if (NUTRI_SCORE_ZONES.includes(zone)) return 'nutri_score';
        if (NUTRI_SCORE_REGIONS.includes(regionOf(language))) return 'nutri_score';
        return null;
    }

    /** The BCP-47 region subtag, uppercased, or '' when it can't be read. */
    function regionOf(language: string): string {
        if (!language) return '';
        try {
            return new Intl.Locale(language).region ?? '';
        } catch {
            const parts = language.toUpperCase().split('-');
            return parts.length > 1 ? (parts[parts.length - 1] ?? '') : '';
        }
    }

    /** Is this device in Australia or New Zealand?
     *
     *  **Timezone first, language second** — found the hard way while testing
     *  this: the machine reported `navigator.language === 'en-GB'` with
     *  `timeZone === 'Australia/Sydney'`. Plenty of Australians run their OS
     *  in en-GB, so a language-only test would have silently never fired for
     *  exactly the people the prompt exists for. The timezone is a statement
     *  about *where the device is*; the language tag is a statement about
     *  which words it prefers, and only sometimes about geography.
     *
     *  Either signal is enough. Over-offering costs one dismissable prompt
     *  behind a button the user pressed on purpose; under-offering means the
     *  feature is never found. */
    function isAustralasian(language: string, zone: string): boolean {
        return isAustralasianZone(zone) || isAustralasianLanguage(language);
    }

    /** IANA zone ids are `Area/Location`. Australia has its own area; New
     *  Zealand sits under `Pacific/` alongside a great many places that are
     *  not New Zealand, so those are named rather than prefix-matched. */
    function isAustralasianZone(zone: string): boolean {
        if (!zone) return false;
        if (zone.startsWith('Australia/')) return true;
        return ['Pacific/Auckland', 'Pacific/Chatham'].includes(zone);
    }

    /** By the BCP-47 tag's *region* subtag, not by a substring match: `en-AU`
     *  and `mi-NZ` both qualify, and a tag that merely contains those letters
     *  does not. Falls back to a suffix read when `Intl.Locale` can't parse
     *  what the browser handed us. */
    function isAustralasianLanguage(language: string): boolean {
        if (!language) return false;
        try {
            const region = new Intl.Locale(language).region;
            if (region) return region === 'AU' || region === 'NZ';
        } catch {
            // fall through to the textual read below
        }
        const upper = language.toUpperCase();
        return upper.endsWith('-AU') || upper.endsWith('-NZ');
    }

    async function enableRatingScheme(scheme: 'health_star' | 'nutri_score') {
        try {
            await settingsStore.saveAsync({ nutrition_rating_scheme: scheme });
            await refreshFlags();
            // Same reason as the Nutrition settings page: the rating is
            // computed per request and is absent from every recipe DTO fetched
            // while the scheme was 'none', so the cached list has to be dropped
            // or the chip stays blank until a full page reload.
            useRecipeStore().invalidateRecipes();
            $q.notify({
                type: 'positive', 
                message: scheme === 'health_star'
                    ? 'Health Star Ratings on.'
                    : 'Nutri-Score on.',
                caption: 'They show on recipes once nutrition is set to complex.',
            });
        } catch (err) {
            $q.notify({
                type: 'negative', 
                message: "Couldn't turn on Health Star Ratings.",
                caption: toastCaption(err),
            });
        }
    }

    onMounted(async () => {
        try {
            await settingsStore.ensureLoadedAsync();
            const s = settingsStore.settings;
            if (!s) return;
            if (s.timezone) timezoneDraft.value = s.timezone;
            if (s.currency) {
                currencyDraft.value = s.currency;
                lastSavedCurrency = s.currency;
            }
            if (s.locale) {
                localeDraft.value = s.locale;
                lastSavedLocale = s.locale;
            }
            if (s.measurement_system) {
                systemDraft.value = s.measurement_system;
                lastSavedSystem = s.measurement_system;
            }
            // FU-600: with money features off, no money surface mounts to
            // trigger the policy read lazily — so force one, or the rest of
            // the app keeps rendering the AUD/en-AU defaults after a change
            // made here.
            await refreshMoneyPolicy();
        } catch {
            // Leave the AU / UTC defaults; admin can retry once the DB is reachable.
        } finally {
            loading.value = false;
        }
    });
</script>

<style scoped lang="scss">

    .region-preview {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding: 16px 18px;
        margin-bottom: 20px;
        border-radius: 10px;
        background: var(--surface-sunken);
        border: 1px solid color-mix(in srgb, var(--text-primary) 8%, transparent);
    }
    .region-preview__row {
        display: flex;
        align-items: baseline;
        gap: 12px;
        flex-wrap: wrap;
    }
    .region-preview__label {
        flex: 0 0 72px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--text-muted);
    }
    .region-preview__value {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-primary);
    }
    .region-preview__detect {
        align-self: flex-start;
        margin-top: 4px;
    }

    .region-field {
        width: 100%;
        min-width: 200px;
    }
</style>
