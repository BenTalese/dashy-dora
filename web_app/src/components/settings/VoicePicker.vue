<template>
    <div role="radiogroup" aria-label="Dora's voice">
        <!-- Device default (browser) voice — always available, no download.
             Selecting it switches Dora to the browser/device engine.
             It is a different *kind* of thing from the neural voices (a
             different engine, not a different voice), so it sits on its own
             above them rather than as one more card in their grid. -->
        <div class="voice-picker__group-label">Built-in</div>
        <div
            class="voice-card voice-card--basic voice-card--selectable"
            :class="{ 'voice-card--active': deviceDefaultActive }"
            role="radio"
            :aria-checked="deviceDefaultActive === true"
            tabindex="0"
            @click="onDeviceDefaultClick"
            @keydown.enter.prevent="onDeviceDefaultClick"
            @keydown.space.prevent="onDeviceDefaultClick"
        >
            <div class="voice-card__head">
                <q-icon :name="ICONS.phone_iphone" size="18px" class="voice-card__kind-icon" />
                <span class="voice-card__name">Device default voice</span>
                <q-icon
                    v-if="deviceDefaultActive"
                    :name="ICONS.check_circle"
                    size="18px"
                    class="voice-card__check"
                />
            </div>
            <div class="voice-card__desc">
                Uses your device or browser's built-in text-to-speech.
            </div>
            <!-- "Always available" was the old copy and it wasn't true: a
                 browser can expose SpeechSynthesis and hold zero voices, in
                 which case both this card and its Preview button are dead
                 controls that fail silently (owner feedback 2026-08-27 —
                 Firefox). Say so, and hide the Preview rather than offering a
                 button that does nothing. -->
            <div v-if="!deviceVoiceUsable" class="voice-card__desc voice-card__desc--warn">
                No text-to-speech voices are installed in this browser. Dora will
                use her neural voice instead.
            </div>
            <div v-if="canPreviewDevice" class="voice-card__actions">
                <button
                    type="button"
                    class="voice-card__btn voice-card__btn--ghost"
                    :disabled="disabled"
                    :aria-label="'Preview device default voice'"
                    @click.stop="onDeviceDefaultPreview"
                >
                    <q-icon :name="ICONS.play_arrow" size="16px" />
                    <span>{{ browserPreviewing ? 'Playing…' : 'Preview' }}</span>
                </button>
            </div>
        </div>

        <!-- Owner 2026-08-29: the "Natural-sounding, run on your server" hint
             was dropped — each card already describes its own voice, and the
             page's lede covers the engine. -->
        <div class="voice-picker__group-label voice-picker__group-label--neural">
            Neural voices
        </div>
        <div class="voice-picker">
        <div
            v-for="voice in voices"
            :key="voice.id"
            class="voice-card"
            :class="{
                'voice-card--active': !deviceDefaultActive && voice.id === modelValue && voice.status === 'ready',
                'voice-card--selectable': voice.status === 'ready',
            }"
            :role="voice.status === 'ready' ? 'radio' : undefined"
            :aria-checked="voice.status === 'ready' ? (!deviceDefaultActive && voice.id === modelValue) : undefined"
            :tabindex="voice.status === 'ready' ? 0 : undefined"
            @click="onCardClick(voice)"
            @keydown.enter.prevent="onCardClick(voice)"
            @keydown.space.prevent="onCardClick(voice)"
        >
            <div class="voice-card__head">
                <span class="voice-card__name">{{ voice.label }}</span>
                <span class="voice-card__gender">{{ genderLabel(voice.gender) }}</span>
                <q-icon
                    v-if="!deviceDefaultActive && voice.id === modelValue && voice.status === 'ready'"
                    :name="ICONS.check_circle"
                    size="18px"
                    class="voice-card__check"
                />
            </div>
            <div class="voice-card__desc">{{ voice.description }}</div>

            <!-- Ready: preview + (implicit) select-by-clicking-the-card -->
            <div v-if="voice.status === 'ready'" class="voice-card__actions">
                <button
                    type="button"
                    class="voice-card__btn voice-card__btn--ghost"
                    :disabled="!piperAvailable || disabled"
                    :aria-label="`Preview ${voice.label}`"
                    @click.stop="onPreview(voice)"
                >
                    <AppSpinner v-if="loadingId === voice.id" size="14px" />
                    <q-icon v-else :name="ICONS.play_arrow" size="16px" />
                    <span>{{ playingId === voice.id ? 'Playing…' : 'Preview' }}</span>
                    <BaseTooltip v-if="!piperAvailable">
                        The neural voice engine isn't installed on this server yet.
                    </BaseTooltip>
                </button>
            </div>

            <!-- Downloadable: fetch the model -->
            <div v-else-if="voice.status === 'downloadable'" class="voice-card__actions">
                <button
                    type="button"
                    class="voice-card__btn"
                    :disabled="disabled"
                    :aria-label="`Download ${voice.label}`"
                    @click.stop="emit('download', voice.id)"
                >
                    <q-icon :name="ICONS.download" size="16px" />
                    <span>Download · {{ sizeMb(voice.size_bytes) }}</span>
                </button>
            </div>

            <!-- Downloading: real bytes where the server can report them.
                 A voice is 60–110MB, and the old spinner-plus-catalogue-size
                 said the same thing at second 1 and minute 3 (B10). The bar
                 falls back to indeterminate when the origin sent no
                 Content-Length rather than inventing a denominator. -->
            <div v-else-if="voice.status === 'downloading'" class="voice-card__download">
                <div class="voice-card__actions voice-card__actions--muted">
                    <AppSpinner v-if="downloadFraction(voice) === null" size="16px" />
                    <span>{{ downloadLabel(voice) }}</span>
                </div>
                <q-linear-progress
                    class="voice-card__bar"
                    rounded
                    size="4px"
                    color="primary"
                    :indeterminate="downloadFraction(voice) === null"
                    :value="downloadFraction(voice) ?? 0"
                />
            </div>

            <!-- Error: retry -->
            <div v-else-if="voice.status === 'error'" class="voice-card__actions">
                <button
                    type="button"
                    class="voice-card__btn voice-card__btn--error"
                    :disabled="disabled"
                    :aria-label="`Retry downloading ${voice.label}`"
                    @click.stop="emit('download', voice.id)"
                >
                    <q-icon :name="ICONS.replay" size="16px" />
                    <span>Retry download</span>
                </button>
                <span v-if="voice.error" class="voice-card__error">{{ voice.error }}</span>
            </div>
        </div>
        </div>
    </div>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { computed, onBeforeUnmount, ref } from 'vue';
    import { useQuasar } from 'quasar';
    import AppSpinner from 'src/components/AppSpinner.vue';
    import { ICONS } from 'src/style/icons';
    import TtsApiService, { type TtsVoice } from 'src/services/api/ttsApiService';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { primeAudioForGesture } from 'src/utils/audioUnlock';

    const props = defineProps<{
        // The selected neural voice id (only meaningful when a neural voice is
        // active). Device-default selection is signalled separately via
        // `deviceDefaultActive` so this component never has to invent a
        // sentinel id for the browser engine.
        modelValue: string;
        voices: TtsVoice[];
        piperAvailable: boolean;
        // True when the user is on the browser/device voice (engine = browser).
        deviceDefaultActive?: boolean;
        /** Whether the device voice can actually make a sound here. Owned by
         *  `useSpeechOutput` (one probe, one answer — R-003); this component
         *  renders it rather than re-testing `'speechSynthesis' in window`,
         *  which is the check that reported Firefox as working. */
        deviceVoiceUsable?: boolean;
        disabled?: boolean;
    }>();
    const emit = defineEmits<{
        (e: 'update:modelValue', value: string): void;
        (e: 'select-device-default'): void;
        (e: 'download', voiceId: string): void;
    }>();

    const $q = useQuasar();
    const ttsApi = new TtsApiService();

    // A short, on-brand line so the user hears the voice's character.
    const SAMPLE = "Hi, I'm Dora. I'll help you keep your kitchen stocked and your dinners sorted.";

    const loadingId = ref<string | null>(null);
    const playingId = ref<string | null>(null);
    let audio: HTMLAudioElement | null = null;
    let audioUrl: string | null = null;

    // Browser/device-voice preview uses the Web Speech API (gesture-safe on
    // mobile), separate from the neural <audio> path below.
    const browserTtsAvailable =
        typeof window !== 'undefined' && 'speechSynthesis' in window;
    /** The API being present is necessary but not sufficient — the caller's
     *  probe decides. Left permissive when the prop is absent so an existing
     *  caller that doesn't pass it behaves as before. */
    const canPreviewDevice = computed(
        () => browserTtsAvailable && props.deviceVoiceUsable !== false,
    );
    const browserPreviewing = ref(false);

    function onDeviceDefaultClick() {
        if (props.disabled || props.deviceDefaultActive) return;
        emit('select-device-default');
    }

    function onDeviceDefaultPreview() {
        if (!canPreviewDevice.value) return;
        const synth = window.speechSynthesis;
        if (browserPreviewing.value) {
            synth.cancel();
            browserPreviewing.value = false;
            return;
        }
        stopPlayback(); // stop any neural preview first
        synth.cancel();
        const utter = new SpeechSynthesisUtterance(SAMPLE);
        utter.onend = () => { browserPreviewing.value = false; };
        utter.onerror = () => { browserPreviewing.value = false; };
        browserPreviewing.value = true;
        synth.speak(utter);
    }

    function genderLabel(gender: TtsVoice['gender']): string {
        if (gender === 'female') return 'Female';
        if (gender === 'male') return 'Male';
        return 'Neutral';
    }

    function sizeMb(bytes: number): string {
        return `${Math.round(bytes / (1024 * 1024))} MB`;
    }

    /** Fraction 0–1 of the model downloaded, or null when the server can't
     *  say and the bar should run indeterminate. `downloaded_bytes_total` is
     *  0 both before the first chunk lands and when the origin declared no
     *  size, so it is checked rather than divided by. */
    function downloadFraction(voice: TtsVoice): number | null {
        const total = voice.downloaded_bytes_total ?? 0;
        if (total <= 0) return null;
        return Math.min(1, (voice.downloaded_bytes ?? 0) / total);
    }

    function downloadLabel(voice: TtsVoice): string {
        const done = voice.downloaded_bytes ?? 0;
        const total = voice.downloaded_bytes_total ?? 0;
        if (total > 0) return `Downloading ${sizeMb(done)} of ${sizeMb(total)}`;
        // No total to quote, so fall back to the catalogue's advertised size,
        // which is what this card showed before the counters existed.
        if (done > 0) return `Downloading ${sizeMb(done)} of ~${sizeMb(voice.size_bytes)}`;
        return `Downloading… (${sizeMb(voice.size_bytes)})`;
    }

    function onCardClick(voice: TtsVoice) {
        if (props.disabled || voice.status !== 'ready') return;
        // Bail only when this card is *actually* the live selection. Selecting
        // the device default keeps `voice_id` (so switching back remembers the
        // voice), which means a bare `voice.id === modelValue` test also
        // swallowed the click on the very voice you were last using — the one
        // neural card you could never get back to, while every other one
        // worked. Same condition the template uses for `voice-card--active`.
        if (!props.deviceDefaultActive && voice.id === props.modelValue) return;
        emit('update:modelValue', voice.id);
    }

    function stopPlayback() {
        if (audio) {
            audio.onended = null;
            audio.onerror = null;
            audio.pause();
            audio = null;
        }
        if (audioUrl) {
            URL.revokeObjectURL(audioUrl);
            audioUrl = null;
        }
        playingId.value = null;
    }

    async function onPreview(voice: TtsVoice) {
        if (props.disabled || !props.piperAvailable) return;
        if (playingId.value === voice.id) { stopPlayback(); return; }
        stopPlayback();
        loadingId.value = voice.id;

        // Create + prime the audio element INSIDE the click gesture, before the
        // synth `await`. Mobile browsers (Android Chrome/Firefox, iOS) block a
        // play() that first runs after an await because the user-activation is
        // gone by then — which is why the preview worked on the server's own
        // desktop browser but errored on a phone. Priming the same element now
        // grants it activation; we swap in the real src once the blob arrives.
        const el = new Audio();
        audio = el;
        primeAudioForGesture(el);

        try {
            const blob = await ttsApi.synthesizeAsync(SAMPLE, voice.id);
            if (loadingId.value !== voice.id || audio !== el) return; // superseded
            audioUrl = URL.createObjectURL(blob);
            el.src = audioUrl;
            el.onended = stopPlayback;
            el.onerror = stopPlayback;
            playingId.value = voice.id;
            await el.play();
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: `Could not preview ${voice.label}.`,
                caption: toastCaption(err),
            });
            stopPlayback();
        } finally {
            if (loadingId.value === voice.id) loadingId.value = null;
        }
    }

    onBeforeUnmount(() => {
        stopPlayback();
        if (browserTtsAvailable) window.speechSynthesis.cancel();
    });
</script>

<style scoped lang="scss">
    .voice-picker {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
        gap: 10px;
        width: 100%;
    }
    // Section labels separating the built-in engine from the neural catalogue.
    // Matches the settings side-nav eyebrow (11px / uppercase / muted).
    .voice-picker__group-label {
        display: flex;
        align-items: baseline;
        flex-wrap: wrap;
        gap: 8px;
        font-size: 0.6875rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-muted);
        margin-bottom: 6px;
    }
    .voice-picker__group-label--neural { margin-top: 18px; }
    // The built-in voice is a different kind of thing from the neural ones, so
    // it reads as a full-width sunken row rather than a peer tile in their grid.
    .voice-card--basic {
        background: var(--surface-sunken);
        border-style: dashed;
    }
    .voice-card--basic.voice-card--active {
        border-style: solid;
    }
    .voice-card__kind-icon {
        color: var(--text-muted);
        flex: 0 0 auto;
    }
    .voice-card {
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding: 12px 14px;
        border-radius: 10px;
        border: 2px solid color-mix(in srgb, var(--text-primary) 10%, transparent);
        background: var(--surface-card, transparent);
        transition: border-color 0.18s ease, background-color 0.18s ease;
    }
    .voice-card--selectable { cursor: pointer; }
    .voice-card--selectable:hover {
        border-color: color-mix(in srgb, var(--accent-mark) 45%, transparent);
    }
    .voice-card--selectable:focus-visible {
        outline: 2px solid var(--ring-focus);
        outline-offset: 2px;
    }
    .voice-card--active {
        border-color: var(--accent-mark);
        background: var(--brand-primary-soft, var(--surface-sunken));
    }
    .voice-card__head {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .voice-card__name {
        font-weight: 700;
        color: var(--text-primary);
    }
    .voice-card__gender {
        font-size: 0.6875rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        color: var(--text-secondary);
        padding: 2px 6px;
        border-radius: 999px;
        background: color-mix(in srgb, var(--text-primary) 8%, transparent);
    }
    .voice-card__check {
        margin-left: auto;
        color: var(--accent-mark);
    }
    .voice-card__desc {
        font-size: 0.8125rem;
        line-height: 1.35;
        color: var(--text-secondary);
    }

    /* The "this control is dead here" note on the device-voice card. Muted
       rather than alarming — nothing is broken, this device just can't do it. */
    .voice-card__desc--warn {
        color: var(--semantic-warning, var(--text-secondary));
    }
    .voice-card__actions {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 2px;
    }
    .voice-card__actions--muted {
        font-size: 0.8125rem;
        color: var(--text-secondary);
    }
    .voice-card__download {
        display: flex;
        flex-direction: column;
        gap: var(--space-1);
    }
    .voice-card__bar {
        // Tracks the label above it rather than the full card width.
        max-width: 260px;
    }
    .voice-card__btn {
        // Native <button> — reset UA chrome (border, font, etc.) so the chip
        // styling below carries the look. `disabled` is the real attribute, so
        // we drop the prior `pointer-events: none` trick.
        appearance: none;
        border: 0;
        font-family: inherit;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        // Ink for the label, the raw accent for the tint behind it — a 12%
        // wash of the fill tone is the pale-yellow ground this chip wants.
        color: var(--accent-ink);
        background: color-mix(in srgb, var(--brand-accent) 12%, transparent);
        cursor: pointer;
    }
    .voice-card__btn:hover:not(:disabled) {
        background: color-mix(in srgb, var(--brand-accent) 20%, transparent);
    }
    .voice-card__btn:focus-visible { outline: 2px solid var(--ring-focus); outline-offset: 2px; }
    .voice-card__btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
    .voice-card__btn--ghost {
        color: var(--text-secondary);
        background: color-mix(in srgb, var(--text-primary) 6%, transparent);
    }
    .voice-card__btn--error {
        color: var(--semantic-negative);
        background: color-mix(in srgb, var(--semantic-negative) 10%, transparent);
    }
    .voice-card__error {
        font-size: 0.75rem;
        color: var(--text-secondary);
        flex-basis: 100%;
    }
</style>
