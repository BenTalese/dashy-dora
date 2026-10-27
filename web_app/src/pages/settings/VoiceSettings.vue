<template>
    <!-- The router guard owns "signed in"; this only waits for the user row. -->
    <div v-if="currentUser" class="settings-page">
        <SettingsPageHeader
            title="Voice"
            :icon="ICONS.record_voice_over"
            description="Talk to Dora and let her talk back. Speech recognition uses your browser's built-in support, so it only works where the browser supports it and will ask for microphone permission the first time. For Dora's replies you can choose her natural neural voice or your browser's built-in one."
        />

        <SettingsSection>
            <template #title>Enable microphone voice input</template>
            <template #actions>
                <q-toggle
                    :model-value="currentUser.voice_input_enabled"
                    :disable="!voiceInputAvailable"
                    aria-label="Enable microphone voice input"
                    @update:model-value="onVoiceInputChange"
                />
            </template>
            <!--
                Owner feedback 2026-08-29 — *"Still seeing 'Your browser doesn't
                expose the Web Speech API for recognition' on Firefox. What
                browsers can we really support?"*

                The honest answer, and the reason the old line felt like a bug
                report: speech *recognition* is not ours to fix from the client.
                It is the browser's `SpeechRecognition` API, which Chrome, Edge,
                Safari and the other Chromium browsers ship and Firefox has
                never shipped — there is no flag, and no polyfill that works
                without shipping audio to a third party. So the card names the
                browsers that do work rather than implying the user has
                misconfigured something. Making this work everywhere needs
                server-side transcription (FU-788), which is a real feature, not
                a copy fix.
            -->
            <SettingsNotice
                v-if="!voiceInputAvailable"
                title="Not available in this browser"
            >
                Speaking to Dora uses your browser's own speech-recognition
                engine, and this browser doesn't have one. It works in
                <strong>Chrome</strong>, <strong>Edge</strong>,
                <strong>Safari</strong> and other Chromium-based browsers.
            </SettingsNotice>
        </SettingsSection>

        <hr class="settings-divider" />

        <SettingsSection>
            <template #title>Let Dora speak her replies</template>
            <template #actions>
                <q-toggle
                    :model-value="currentUser.voice_output_enabled"
                    :disable="!voiceOutputAvailable"
                    aria-label="Let Dora speak her replies"
                    @update:model-value="onVoiceOutputChange"
                />
            </template>
            <!-- Owner feedback 2026-08-27: *"TTS isn't supported on Firefox
                 for some reason? What browsers can we support?"* Three
                 different situations used to collapse into one line about
                 SpeechSynthesis, and the Firefox one — API present, zero
                 voices installed — was the one it described worst. Each now
                 says what is actually true and what to do about it. -->
            <SettingsNotice v-if="!voiceOutputAvailable" title="Nothing here can speak">
                Your browser reports no installed text-to-speech voices, and
                Dora's own neural voice isn't installed on this server either,
                so nothing can read her replies. See "Dora's voice" below.
            </SettingsNotice>
            <SettingsNotice
                v-else-if="!browserVoiceUsable"
                tone="info"
                title="Using Dora's neural voice"
            >
                Your browser has no text-to-speech voices installed, so Dora
                uses her own neural voice.
            </SettingsNotice>
        </SettingsSection>

        <hr class="settings-divider" />

        <SettingsSection>
            <template #title>Dora's voice</template>

            <!--
                Owner feedback 2026-08-29 — *"I'm confused by 'Dora's
                neural-voice engine isn't installed on this server'. In what
                situations does this happen? I'd expect it to always work. Also
                if the neural voice engine isn't available then why let people
                download voices at all?"*

                Both fair. The situation is narrow and nameable: Piper is
                deliberately NOT a hard dependency (R-018 / ADR-013 — its
                `piper-phonemize` wheel won't build on Windows), so the Docker
                image installs it and the desktop bundle ships it, but an
                install running from source on a machine without it has no
                engine. That is now what the card says, instead of leaving the
                reader to guess.

                And the download cards are gone in that state rather than
                explained: offering a 60–110MB model for an engine that cannot
                run it is a dead control with a rationalisation attached. There
                is nothing to choose between while Piper is missing — replies
                fall back to the device voice automatically — so the picker only
                appears once there is a real choice to make.

                R-029 (hide, don't nag) rather than its settings-screen
                carve-out: that carve-out is for the surface that *owns* the
                config, and this page doesn't own Piper's installation — the
                binary is an operator/packaging concern whose setting lives on
                Admin → Voice, which is where the card points.
            -->
            <SettingsNotice
                v-if="!loadingVoices && !piperAvailable"
                title="No neural voice on this install"
            >
                Dora's neural voice runs as a separate engine (Piper) alongside
                the server, and this install doesn't have it. The
                <strong>Docker image</strong> and the <strong>desktop app</strong>
                both include it and need no setup; an install running from
                source doesn't, because the engine can't be installed from
                Python on Windows and so isn't a required dependency.
                <template v-if="isAdmin">
                    An admin can install it and point Dora at it under
                    Admin → Voice.
                </template>
                <template v-else>
                    Ask an admin to install it if you'd like the natural voice.
                </template>
                Until then Dora speaks with your device's built-in voice.
                <template #actions>
                    <BaseButton
                        v-if="isAdmin"
                        variant="secondary"
                        :icon="ICONS.settings"
                        label="Voice engine setup"
                        to="/settings/admin/system/voice"
                    />
                </template>
            </SettingsNotice>

            <template v-else-if="!loadingVoices">
                <p class="settings-page__lede">
                    Choose how Dora sounds when she speaks her replies and reads
                    cook-mode steps. Download a neural voice you like and select
                    it, or use your device's built-in text-to-speech voice.
                </p>

                <SettingsNotice v-if="!anyVoiceReady" tone="info">
                    Download a voice below to start using Dora's neural voice.
                </SettingsNotice>

                <div class="settings-page__voices">
                    <VoicePicker
                        :model-value="currentUser.voice_id"
                        :voices="voices"
                        :piper-available="piperAvailable"
                        :device-default-active="currentUser.voice_engine === 'browser'"
                        :device-voice-usable="browserVoiceUsable"
                        @update:model-value="onVoiceChange"
                        @select-device-default="onSelectDeviceDefault"
                        @download="onDownload"
                    />
                </div>
            </template>
        </SettingsSection>
    </div>
</template>

<script lang="ts" setup>
    import { storeToRefs } from 'pinia';
    import { useAuthStore } from 'src/stores/authStore';
    import { useSpeechOutput } from 'src/composables/useSpeechOutput';
    import { useVoiceInput } from 'src/composables/useVoiceInput';
    import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
    import { useSettingsSave } from 'src/composables/useSettingsSave';
    import TtsApiService, { type TtsVoice } from 'src/services/api/ttsApiService';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import { ICONS } from 'src/style/icons';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import VoicePicker from 'src/components/settings/VoicePicker.vue';
    import SettingsNotice from 'src/components/settings/SettingsNotice.vue';
    import BaseButton from 'src/components/BaseButton.vue';

    const authStore = useAuthStore();
    const { currentUser } = storeToRefs(authStore);
    const ttsApi = new TtsApiService();

    // Decides whether the "no neural voice" card offers the setup page or
    // "ask an admin" — same split ChannelSetupNote makes on Notifications.
    const isAdmin = computed(() => currentUser.value?.is_admin === true);

    // R-003 / FU-601 — shared save-toast helper (see useSettingsSave).
    const { notifySuccess, notifyError, update } = useSettingsSave();
    const loadingVoices = ref(true);
    const voices = ref<TtsVoice[]>([]);
    const piperAvailable = ref(false);

    const anyVoiceReady = computed(() => voices.value.some((v) => v.status === 'ready'));

    const voiceProbeInput = useVoiceInput();
    const voiceProbeOutput = useSpeechOutput();
    const voiceInputAvailable = computed(() => voiceProbeInput.available.value);
    const voiceOutputAvailable = computed(() => voiceProbeOutput.available.value);
    /** Whether the *device* voice specifically can make a sound here — a
     *  separate question from `voiceOutputAvailable`, which is true whenever
     *  either engine works. See `useSpeechOutput`. */
    const browserVoiceUsable = computed(() => voiceProbeOutput.browserVoiceUsable.value);

    async function onVoiceInputChange(value: boolean) {
        await update(
            value ? 'Voice input enabled.' : 'Voice input disabled.',
            () => authStore.updateMeAsync({ voice_input_enabled: value }),
        );
    }
    async function onVoiceOutputChange(value: boolean) {
        if (!value) voiceProbeOutput.cancel();
        await update(
            value ? 'Dora will speak her replies.' : 'Dora\'s voice muted.',
            () => authStore.updateMeAsync({ voice_output_enabled: value }),
        );
    }
    // Picking a neural voice card both selects it AND switches Dora onto the
    // neural engine — the standalone engine toggle was removed, so selection is
    // the one place engine intent is expressed (owner feedback). Both fields go
    // in one save.
    async function onVoiceChange(value: string) {
        await update(
            'Voice updated.',
            () => authStore.updateMeAsync({ voice_id: value, voice_engine: 'piper' }),
        );
    }
    // "Device default voice" card → the browser/device engine.
    async function onSelectDeviceDefault() {
        await update(
            'Using your device voice.',
            () => authStore.updateMeAsync({ voice_engine: 'browser' }),
        );
    }

    async function refreshVoices() {
        const res = await ttsApi.getVoicesAsync();
        voices.value = res.voices;
        piperAvailable.value = res.piper_available;
    }

    // Poll while any voice is mid-download, so the cards flip to Ready when the
    // server-side fetch finishes.
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    function stopPolling() {
        if (pollTimer !== null) { clearInterval(pollTimer); pollTimer = null; }
    }
    async function pollOnce() {
        try {
            await refreshVoices();
        } catch { /* transient; keep polling */ }
        if (!voices.value.some((v) => v.status === 'downloading')) stopPolling();
    }
    function ensurePolling() {
        if (pollTimer !== null) return;
        pollTimer = setInterval(() => { void pollOnce(); }, 2500);
    }

    async function onDownload(voiceId: string) {
        const voice = voices.value.find((v) => v.id === voiceId);
        try {
            await ttsApi.downloadVoiceAsync(voiceId);
            await refreshVoices();
            ensurePolling();
            notifySuccess(`Downloading ${voice?.label ?? 'voice'}…`);
        } catch (err) {
            notifyError(`Could not start downloading ${voice?.label ?? 'voice'}.`, err);
        }
    }

    onMounted(async () => {
        try {
            await refreshVoices();
            if (voices.value.some((v) => v.status === 'downloading')) ensurePolling();
        } catch {
            // Catalog unreachable — leave Piper disabled; replies fall back to
            // the browser voice. The section notes cover the why.
            voices.value = [];
            piperAvailable.value = false;
        } finally {
            loadingVoices.value = false;
        }
    });

    onBeforeUnmount(stopPolling);
</script>

<style scoped lang="scss">
    .settings-page__note {
        font-size: 0.8125rem;
        line-height: 1.4;
        margin-top: 4px;
    }
    .settings-page__lede {
        margin: 0;
        max-width: 60ch;
        color: var(--text-secondary);
        font-size: 0.875rem;
        line-height: 1.4;
    }
    .settings-page__voices { margin-top: 12px; }
</style>
