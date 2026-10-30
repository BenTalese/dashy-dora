<template>
    <!-- The router guard owns "signed in"; this only waits for the user row. -->
    <div v-if="currentUser" class="settings-page">
        <SettingsPageHeader title="Assistant" :icon="ICONS.smart_toy">
            <template #description>
                Settings to control D.O.R.A., your personal assistant in the
                kitchen. Learn more about using her capabilities
                <router-link to="/help/dora" class="settings-page__link">here</router-link>.
            </template>
        </SettingsPageHeader>

        <!-- Owner regroup 2026-08-17: the page now reads chat → providers →
             pantry inference. "Assistant chat" owns the two settings about
             the chat itself (show it; which brain answers); the long
             explanation of Basic-vs-model moved into a (?) chip so the
             section stays scannable. -->
        <SettingsSection>
            <template #title>Assistant chat</template>
            <!-- Owner 2026-09-03: the section description went — the two row
                 labels beneath it already say what the section is. -->

            <SettingsRow inline label="Show digital assistant chat bubble">
                <q-toggle
                    :model-value="currentUser.show_assistant !== false"
                    @update:model-value="onShowAssistantChange"
                />
            </SettingsRow>

            <SettingsRow inline>
                <template #label>
                    Mode
                    <InfoTip label="Mode">
                        Choose between basic mode and configured providers for
                        AI mode for your assistant chat. See help for more
                        information.
                    </InfoTip>
                </template>
                <q-select
                    :model-value="modeValue"
                    :options="modeOptions"
                    emit-value
                    map-options
                    outlined
                    dense
                    class="assistant-mode-select"
                    @update:model-value="onModeChange"
                />
            </SettingsRow>
        </SettingsSection>

        <hr class="settings-divider" />

        <SettingsSection>
            <template #title>Providers</template>
            <template #description>
                Connect one or more language models. <strong>Ollama</strong>
                runs locally (no key needed); <strong>OpenAI</strong>,
                <strong>Anthropic</strong>, and <strong>Google Gemini</strong>
                are paid hosted APIs.
            </template>

            <!-- Warns (and offers to generate a key) when the install hasn't
                 set DORA_SECRET_ENCRYPTION_KEY — a paid-provider API key can't
                 be stored encrypted without it, so saving one would be
                 refused. Sits inside Providers (owner, 2026-08-17): at the top
                 of the page it read as a whole-page failure, when the only
                 thing it gates is pasting a paid provider's key. -->
            <EncryptionKeyBanner secret-label="a paid provider's API key" />

            <!-- Each provider is a minimised card — name + connection state —
                 that opens on click (owner, 2026-08-17). Four always-expanded
                 forms buried the one you'd actually configured. -->
            <div
                v-for="provider in PROVIDERS"
                :key="provider"
                class="provider-card"
                :class="`provider-card--${statusTone(provider)}`"
            >
                <button
                    type="button"
                    class="provider-card__head"
                    :aria-expanded="expanded === provider"
                    :aria-controls="`provider-body-${provider}`"
                    @click="toggleProvider(provider)"
                >
                    <q-icon
                        :name="expanded === provider ? ICONS.collapse : ICONS.expand"
                        size="18px"
                        class="provider-card__chevron"
                    />
                    <h3 class="provider-card__name">{{ providerDisplayName(provider) }}</h3>
                    <div class="provider-card__status">
                        <q-spinner
                            v-if="state[provider].status === 'checking'"
                            size="14px"
                            color="primary"
                        />
                        <q-icon
                            v-else
                            :name="statusIcon(provider)"
                            :color="statusColor(provider)"
                            size="16px"
                        />
                        <span :class="`text-${statusColor(provider)}`">
                            {{ statusLabel(provider) }}
                        </span>
                    </div>
                </button>

                <q-slide-transition>
                <div
                    v-show="expanded === provider"
                    :id="`provider-body-${provider}`"
                    class="provider-card__body"
                >
                    <!-- Ollama: base URL + model (model becomes a picker of
                         installed models once a probe succeeds). No API key. -->
                    <template v-if="provider === 'ollama'">
                        <SettingsRow label="Base URL" stacked>
                            <q-input
                                v-model="state.ollama.base_url"
                                outlined
                                dense
                                placeholder="http://localhost:11434"
                                @blur="onOllamaBaseUrlBlur"
                                @keydown.enter.prevent="onOllamaBaseUrlBlur"
                            />
                        </SettingsRow>
                        <SettingsRow label="Model" stacked>
                            <q-select
                                v-if="state.ollama.models.length"
                                v-model="state.ollama.model"
                                :options="state.ollama.models"
                                outlined
                                dense
                                use-input
                                fill-input
                                hide-selected
                                new-value-mode="add-unique"
                                input-debounce="0"
                                placeholder="qwen2.5:7b"
                                @update:model-value="onOllamaModelCommit"
                                @blur="onOllamaModelBlur"
                            />
                            <q-input
                                v-else
                                v-model="state.ollama.model"
                                outlined
                                dense
                                placeholder="qwen2.5:7b"
                                hint="Enter your Ollama base URL first to list installed models."
                                @blur="onOllamaModelBlur"
                                @keydown.enter.prevent="onOllamaModelBlur"
                            />
                        </SettingsRow>
                    </template>

                    <!-- Paid providers: API key (write-only) + model + optional
                         base URL (a self-hosted relay or proxy).

                         Owner 2026-08-29: *"Why does anthropic and openai have
                         base url optional, and gemini has nothing?"* No reason
                         — `GeminiClient` has taken a `base_url` since it was
                         written (defaulting to generativelanguage.googleapis
                         .com) and `factory.py` passes it through, so the field
                         was the only part missing. All three paid providers
                         offer it now. -->
                    <template v-else>
                        <SettingsRow label="API key" stacked>
                            <q-input
                                v-model="state[provider].api_key"
                                outlined
                                dense
                                type="password"
                                autocomplete="off"
                                :placeholder="state[provider].has_api_key ? '••••••••• (saved)' : 'Paste your key here'"
                                @blur="onApiKeyBlur(provider)"
                                @keydown.enter.prevent="onApiKeyBlur(provider)"
                            />
                            <BaseButton
                                v-if="state[provider].has_api_key"
                                variant="danger-ghost"
                                :icon="ICONS.delete"
                                label="Remove key"
                                @click="onClearApiKey(provider)"
                            />
                        </SettingsRow>
                        <SettingsRow label="Model" stacked>
                            <q-input
                                v-model="state[provider].model"
                                outlined
                                dense
                                :placeholder="state[provider].example_model"
                                @blur="onPaidModelBlur(provider)"
                                @keydown.enter.prevent="onPaidModelBlur(provider)"
                            />
                        </SettingsRow>
                        <SettingsRow label="Base URL (optional)" stacked>
                            <q-input
                                v-model="state[provider].base_url"
                                outlined
                                dense
                                :placeholder="state[provider].default_base_url"
                                @blur="onPaidBaseUrlBlur(provider)"
                                @keydown.enter.prevent="onPaidBaseUrlBlur(provider)"
                            />
                        </SettingsRow>
                    </template>

                    <!-- Re-check lives with the fields it re-checks, now that
                         the header is the disclosure control. -->
                    <div v-if="canTest(provider)" class="provider-card__actions">
                        <BaseButton
                            variant="ghost"
                            :icon="ICONS.wifi_tethering"
                            label="Test connection"
                            :disable="state[provider].status === 'checking'"
                            @click="onTest(provider)"
                        />
                    </div>
                </div>
                </q-slide-transition>
            </div>
        </SettingsSection>

        <hr class="settings-divider" />

        <SettingsSection>
            <template #title>Zero-Input Pantry</template>
            <!-- Owner 2026-08-29: the last two sentences went. They restated
                 the same reassurance twice ("your recorded level stays the
                 source of truth" / "what she thinks never changes what the app
                 does") and the per-surface rows below already say where each
                 opinion shows up. The dash after "rhythm" went with them —
                 the clause reads as a plain sentence now. -->
            <template #description>
                Dora can infer each item's stock level from your shopping,
                cooking, and buying rhythm, showing what it thinks beside the
                level you last recorded, and asking a quick check only when it's
                unsure.
                <router-link
                    :to="{ path: '/help', query: { q: 'Dora thinks' } }"
                    class="settings-page__link"
                >Learn more</router-link>.
            </template>

            <!-- Owner 2026-09-03: each row is named "<area> hints" and its
                 explanation moved into an InfoTip, so the section reads as a
                 short list of switches rather than five paragraphs. -->
            <SettingsRow inline>
                <template #label>
                    Stock overview hints
                    <InfoTip label="Stock overview hints">
                        Dora shows an inferred level (with a reason and
                        confidence) alongside the recorded one, and can ask a
                        targeted quick-check. Turn off for purely manual levels.
                    </InfoTip>
                </template>
                <q-toggle
                    :model-value="currentUser.inferred_pantry_enabled"
                    @update:model-value="onInferredPantryChange"
                />
            </SettingsRow>

            <!-- FU-653 — the same belief, on the pages where stock items turn
                 up rather than where they're managed. Separate toggles because
                 they annotate three different jobs; all default off, since
                 they add remarks to pages you opened to do something else. -->
            <SettingsRow inline>
                <template #label>
                    Cookbook hints
                    <InfoTip label="Cookbook hints">
                        Flags a recipe as at risk when Dora believes an
                        ingredient has run out, and points out one you may be
                        able to cook after all.
                    </InfoTip>
                </template>
                <q-toggle
                    :model-value="currentUser.inference_recipes_enabled"
                    @update:model-value="(v: boolean) => onSurfaceChange('recipes', v)"
                />
            </SettingsRow>

            <SettingsRow inline>
                <template #label>
                    Shopping list hints
                    <InfoTip label="Shopping list hints">
                        Suggests items Dora believes you've run out of, beside
                        the list. Nothing is added for you.
                    </InfoTip>
                </template>
                <q-toggle
                    :model-value="currentUser.inference_shopping_enabled"
                    @update:model-value="(v: boolean) => onSurfaceChange('shopping', v)"
                />
            </SettingsRow>

            <SettingsRow inline>
                <template #label>
                    Meal planner hints
                    <InfoTip label="Meal planner hints">
                        Flags a planned meal whose ingredient Dora believes has
                        run out since you planned it. Your plan and its shopping
                        figures are unchanged.
                    </InfoTip>
                </template>
                <q-toggle
                    :model-value="currentUser.inference_meal_plan_enabled"
                    @update:model-value="(v: boolean) => onSurfaceChange('meal_plan', v)"
                />
            </SettingsRow>

            <!-- D-12 (2026-08-19): moved here from Admin — Features, where it
                 was an install-wide setting despite only changing what one
                 person sees. It belongs with the other "Dora's opinions"
                 toggles above. -->
            <!-- Money is a prerequisite, not a co-equal toggle (owner call
                 2026-08-27): the verdict reasons in money end-to-end, so with
                 money off there is nothing honest for it to say. Disabled
                 rather than hidden, per the `emailSmtpConfigured` precedent on
                 Notifications — a toggle that vanishes leaves the dependency
                 undiscoverable, and the user's own preference is preserved
                 underneath for whenever money comes back on. -->
            <SettingsRow inline>
                <template #label>
                    "Should I buy this?"
                    <InfoTip label="Should I buy this?">
                        On a stock item and on your shopping list, Dora gives a
                        buy / wait / skip verdict from your own price, cadence
                        and waste history.
                    </InfoTip>
                </template>
                <!-- The money prerequisite stays inline rather than moving into
                     the tip: it is live state explaining why the switch is
                     dead, not a description of the feature. -->
                <template v-if="!moneyEnabled" #help>
                    <strong>
                        Needs money features, which are off for this
                        install{{ isAdmin ? '' : '. Ask an admin to turn them on' }}.
                    </strong>
                </template>
                <q-toggle
                    :model-value="currentUser.buy_verdict_enabled"
                    :disable="!moneyEnabled"
                    @update:model-value="onBuyVerdictChange"
                />
            </SettingsRow>
        </SettingsSection>
    </div>
</template>

<script lang="ts" setup>
    import BaseButton from 'src/components/BaseButton.vue';
    import { ICONS } from 'src/style/icons';
    import { storeToRefs } from 'pinia';
    import AssistantApiService, {
        type LlmProviderName,
        type ProviderConfig,
    } from 'src/services/api/assistantApiService';
    import { useAuthStore } from 'src/stores/authStore';
    import { computed, onMounted, reactive, ref } from 'vue';
    import { useQuasar } from 'quasar';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { usePantryBeliefs } from 'src/composables/usePantryBeliefs';
    import { useSettingsSave } from 'src/composables/useSettingsSave';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import EncryptionKeyBanner from 'src/components/settings/EncryptionKeyBanner.vue';
    import InfoTip from 'src/components/help/InfoTip.vue';

    const authStore = useAuthStore();
    const { currentUser } = storeToRefs(authStore);
    const $q = useQuasar();
    const assistantApi = new AssistantApiService();
    const { update } = useSettingsSave();

    // Prerequisite for the "Should I buy this?" toggle below — install-wide,
    // so a non-admin can't clear it themselves and the hint says who can.
    const { moneyEnabled } = useMoneyEnabled();
    const isAdmin = computed(() => currentUser.value?.is_admin === true);

    const PROVIDERS: LlmProviderName[] = ['ollama', 'openai', 'anthropic', 'gemini'];

    // 'empty' — nothing entered; 'unverified' — details saved but no successful
    // probe yet; 'checking' — probe in flight; 'connected' — probe succeeded;
    // 'error' — last probe failed. Only 'connected' providers are selectable as
    // a Mode (mirrors the server-side guard on `llm_enabled`).
    type ProviderStatus = 'empty' | 'unverified' | 'checking' | 'connected' | 'error';

    interface ProviderUiState {
        base_url: string;
        model: string;
        api_key: string;       // draft plaintext; cleared once saved
        has_api_key: boolean;  // a key is on file server-side
        verified: boolean;
        status: ProviderStatus;
        reason: string | null;
        models: string[];      // Ollama models discovered by the last probe
        /** Placeholders from the server (`/assistant/providers`, 11-R16). */
        default_base_url: string;
        example_model: string;
    }

    function emptyState(): ProviderUiState {
        return {
            base_url: '',
            model: '',
            api_key: '',
            has_api_key: false,
            verified: false,
            status: 'empty',
            reason: null,
            models: [],
            default_base_url: '',
            example_model: '',
        };
    }

    const state = reactive<Record<LlmProviderName, ProviderUiState>>({
        ollama: emptyState(),
        openai: emptyState(),
        anthropic: emptyState(),
        gemini: emptyState(),
    });

    function providerDisplayName(p: LlmProviderName): string {
        switch (p) {
            case 'openai': return 'OpenAI';
            case 'anthropic': return 'Anthropic';
            case 'gemini': return 'Google Gemini';
            default: return 'Ollama';
        }
    }

    function seedFrom(configs: ProviderConfig[]) {
        for (const cfg of configs) {
            const s = state[cfg.provider];
            if (!s) continue;
            s.base_url = cfg.base_url ?? '';
            s.model = cfg.model ?? '';
            s.has_api_key = cfg.has_api_key;
            s.verified = cfg.verified;
            s.default_base_url = cfg.default_base_url;
            s.example_model = cfg.example_model;
            const configured = !!(cfg.base_url || cfg.model || cfg.has_api_key);
            s.status = cfg.verified ? 'connected' : configured ? 'unverified' : 'empty';
        }
    }

    onMounted(async () => {
        try {
            const { providers } = await assistantApi.getProvidersAsync();
            seedFrom(providers);
        } catch (err) {
            // Non-fatal — the page still renders with empty fields the user
            // can fill; the toast explains the fetch failure. (`toastCaption`
            // only formats — calling it for effect showed nothing, 11-R5.)
            $q.notify({
                type: 'negative',
                message: "Couldn't load your provider settings.",
                caption: toastCaption(err),
            });
        }
    });

    // ----- status chip -----

    function statusLabel(p: LlmProviderName): string {
        const s = state[p];
        switch (s.status) {
            case 'checking': return 'Checking…';
            case 'connected': return 'Connected';
            case 'error': return s.reason ?? "Couldn't connect";
            case 'unverified': return 'Not tested';
            default: return 'Not configured';
        }
    }

    function statusColor(p: LlmProviderName): string {
        switch (state[p].status) {
            case 'connected': return 'positive';
            case 'error': return 'negative';
            case 'unverified': return 'warning';
            default: return 'grey';
        }
    }

    // Owner feedback 2026-08-29 — *"Why is there info chip icons used in the
    // provider cards for when they aren't configured? It gives the impression
    // they will tell you something but I think it's just to show there's no
    // connection."* Exactly right: both the empty and untested states drew the
    // same `help_outline` glyph the rest of the app uses for "hover me for an
    // explanation", so a status readout was wearing the costume of a control.
    // Each state gets a glyph that only reports state now — an empty ring for
    // nothing-configured, an alert for details we haven't been able to
    // confirm.
    function statusIcon(p: LlmProviderName): string {
        switch (state[p].status) {
            case 'connected': return ICONS.check_circle;
            case 'error': return ICONS.warning;
            case 'unverified': return ICONS.warning_amber;
            default: return ICONS.circle_outline;
        }
    }

    // Card tint: neutral when nothing is configured, green when it's working,
    // red when the last probe failed. "Configured but never tested" keeps its
    // own amber — calling it green would claim a connection nobody has
    // verified, and calling it red would accuse a provider that may be fine.
    function statusTone(p: LlmProviderName): string {
        switch (state[p].status) {
            case 'connected': return 'ok';
            case 'error': return 'bad';
            case 'unverified': return 'warn';
            default: return 'neutral';
        }
    }

    // One card open at a time — a disclosure list, not four accordions; null
    // means all minimised, which is how the page loads.
    const expanded = ref<LlmProviderName | null>(null);
    function toggleProvider(p: LlmProviderName) {
        expanded.value = expanded.value === p ? null : p;
    }

    function canTest(p: LlmProviderName): boolean {
        // A manual re-check is useful once details exist (e.g. the server
        // came back up). Nothing to test on an empty provider.
        return state[p].status !== 'empty' && state[p].status !== 'checking';
    }

    // ----- save + probe -----

    async function saveProvider(p: LlmProviderName, patch: Record<string, unknown>): Promise<boolean> {
        try {
            const cfg = await assistantApi.updateProviderAsync(p, patch);
            state[p].has_api_key = cfg.has_api_key;
            state[p].verified = false;
            return true;
        } catch (err) {
            state[p].status = 'error';
            state[p].reason = toastCaption(err) ?? 'Save failed.';
            return false;
        }
    }

    async function probe(p: LlmProviderName) {
        state[p].status = 'checking';
        state[p].reason = null;
        try {
            const r = await assistantApi.probeAsync({
                provider: p,
                base_url: state[p].base_url.trim() || null,
                model: state[p].model.trim() || null,
                // Plaintext (just typed) takes precedence; null falls back to
                // the saved key server-side.
                api_key: state[p].api_key.trim() || null,
            });
            if (r.available) {
                state[p].status = 'connected';
                state[p].verified = true;
                if (r.models) state[p].models = r.models;
            } else {
                state[p].status = 'error';
                state[p].reason = r.reason ?? "Couldn't connect";
                state[p].verified = false;
            }
        } catch (err) {
            state[p].status = 'error';
            state[p].reason = toastCaption(err) ?? "Couldn't reach the server.";
            state[p].verified = false;
        }
        // Keep the Mode dropdown + DoraChat's readiness in sync with the new
        // verified state.
        await authStore.refreshAsync();
    }

    async function onTest(p: LlmProviderName) {
        await probe(p);
    }

    // Ollama handlers
    async function onOllamaBaseUrlBlur() {
        if (await saveProvider('ollama', { base_url: state.ollama.base_url.trim() || null })) {
            if (state.ollama.base_url.trim()) await probe('ollama');
            else state.ollama.status = state.ollama.model ? 'unverified' : 'empty';
        }
    }
    async function onOllamaModelBlur() {
        if (await saveProvider('ollama', { model: state.ollama.model.trim() || null })) {
            if (state.ollama.base_url.trim() && state.ollama.model.trim()) await probe('ollama');
        }
    }
    async function onOllamaModelCommit() {
        // q-select add-unique commits without a blur; persist + probe.
        await onOllamaModelBlur();
    }

    // Paid-provider handlers
    async function onApiKeyBlur(p: LlmProviderName) {
        const next = state[p].api_key.trim();
        if (!next) return;
        if (await saveProvider(p, { api_key: next })) {
            state[p].api_key = '';  // masked; placeholder now shows "(saved)"
            await probe(p);
        }
    }
    async function onClearApiKey(p: LlmProviderName) {
        if (await saveProvider(p, { clear_api_key: true })) {
            state[p].api_key = '';
            state[p].status = state[p].model ? 'unverified' : 'empty';
            await authStore.refreshAsync();
        }
    }
    async function onPaidModelBlur(p: LlmProviderName) {
        if (await saveProvider(p, { model: state[p].model.trim() || null })) {
            if (state[p].has_api_key && state[p].model.trim()) await probe(p);
        }
    }
    async function onPaidBaseUrlBlur(p: LlmProviderName) {
        if (await saveProvider(p, { base_url: state[p].base_url.trim() || null })) {
            if (state[p].has_api_key && state[p].model.trim()) await probe(p);
        }
    }

    // ----- Mode -----

    const modeOptions = computed(() => {
        const opts: { label: string; value: LlmProviderName | null }[] = [
            { label: 'Basic (built-in)', value: null },
        ];
        for (const p of PROVIDERS) {
            if (state[p].verified) opts.push({ label: providerDisplayName(p), value: p });
        }
        return opts;
    });

    const modeValue = computed<LlmProviderName | null>(() =>
        currentUser.value?.llm_enabled ? (currentUser.value.llm_provider ?? null) : null,
    );

    async function onModeChange(value: LlmProviderName | null) {
        if (value === null) {
            await update('Switched to Basic mode.', () =>
                authStore.updateMeAsync({ llm_enabled: false }),
            );
        } else {
            await update(`AI mode on (${providerDisplayName(value)}).`, () =>
                authStore.updateMeAsync({ llm_provider: value, llm_enabled: true }),
            );
        }
    }

    async function onShowAssistantChange(value: boolean) {
        await update(
            value ? 'Dora helper shown.' : 'Dora helper hidden.',
            () => authStore.updateMeAsync({ show_assistant: value }),
        );
    }

    // Zero-Input Pantry opt-out (moved here from Appearance). Default true on
    // a fresh account. Same shared-toast shape as the toggles above.
    async function onInferredPantryChange(value: boolean) {
        await update(
            value
                ? 'Dora will infer your stock levels.'
                : 'Inference off.',
            () => authStore.updateMeAsync({ inferred_pantry_enabled: value }),
        );
        // The beliefs endpoint answers `enabled` from this pref.
        usePantryBeliefs().invalidate();
    }

    // D-12 — "should I buy this?", per-user since 2026-08-19 (it was an
    // install-wide AppSetting an admin set for everybody).
    async function onBuyVerdictChange(value: boolean) {
        await update(
            value
                ? '"Should I buy this?" shown.'
                : '"Should I buy this?" hidden.',
            () => authStore.updateMeAsync({ buy_verdict_enabled: value }),
        );
    }

    // FU-653 — the three per-surface overlays. One handler: the three differ
    // only in which field they write and what the toast calls the place.
    const SURFACE_FIELDS = {
        recipes: 'inference_recipes_enabled',
        shopping: 'inference_shopping_enabled',
        meal_plan: 'inference_meal_plan_enabled',
    } as const;
    const SURFACE_LABELS: Record<keyof typeof SURFACE_FIELDS, string> = {
        recipes: 'recipes',
        shopping: 'shopping lists',
        meal_plan: 'the meal planner',
    };

    async function onSurfaceChange(surface: keyof typeof SURFACE_FIELDS, value: boolean) {
        const where = SURFACE_LABELS[surface];
        await update(
            value
                ? `Dora will share what she thinks on ${where}.`
                : `Dora will stay quiet on ${where}.`,
            () => authStore.updateMeAsync({ [SURFACE_FIELDS[surface]]: value }),
        );
    }
</script>

<style scoped lang="scss">
    /* Owner 2026-09-03: the mode picker stays on the right at every width, so
       it can't carry a fixed 220px floor — that would overflow the row's
       control column on a 375px viewport. */
    .assistant-mode-select {
        width: 220px;
        max-width: 100%;
    }
    .settings-page__link { color: var(--brand-primary); font-weight: 600; }
    .provider-card {
        border: 1px solid color-mix(in srgb, var(--text-primary) 10%, transparent);
        border-radius: 12px;
        overflow: hidden;
    }
    /* State tint on the card edge — deliberately a border + soft wash, not a
       filled card: the card is a control, and a saturated fill would compete
       with the page's own surfaces (D-002). */
    .provider-card--ok {
        border-color: color-mix(in srgb, var(--semantic-positive) 55%, transparent);
    }
    .provider-card--bad {
        border-color: color-mix(in srgb, var(--semantic-negative) 55%, transparent);
    }
    .provider-card--warn {
        border-color: color-mix(in srgb, var(--semantic-warning) 50%, transparent);
    }
    .provider-card__head {
        /* The whole header is the disclosure control, so it's a real <button>
           (keyboard + screen-reader for free) reset back to a row. */
        all: unset;
        box-sizing: border-box;
        width: 100%;
        cursor: pointer;
        /* `all: unset` makes every *inherited* property inherit — including a
           line-height that resolves to ~51px here (measured), which stretched
           the row to 71px tall. Pin it. */
        line-height: 1.3;
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
        /* D-004 — 44px minimum touch target for the tap-to-open row. */
        min-height: 44px;
        padding: 10px 14px;
    }
    .provider-card__head:hover {
        background: color-mix(in srgb, var(--text-primary) 4%, transparent);
    }
    .provider-card__head:focus-visible {
        outline: 2px solid var(--ring-focus);
        outline-offset: -2px;
    }
    .provider-card__chevron {
        flex: 0 0 auto;
        color: var(--text-secondary);
    }
    .provider-card__actions {
        display: flex;
        justify-content: flex-start;
        padding-top: 2px;
    }
    .provider-card__name {
        margin: 0;
        flex: 1 1 auto;
        min-width: 0;
        font-size: 0.9375rem;
        font-weight: 700;
        /* Quasar's typography gives a bare <h3> `line-height: 3.125rem`, which
           made this row 71px tall (measured) for one line of text. */
        line-height: 1.3;
        color: var(--text-primary);
    }
    .provider-card__status {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.8125rem;
        /* An error reason can be a sentence; keep it from shoving the name
           off the row on a narrow screen. */
        max-width: 100%;
        text-align: right;
    }
    .provider-card__body {
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding: 4px 14px 14px;
        border-top: 1px solid color-mix(in srgb, var(--text-primary) 8%, transparent);
    }
</style>
