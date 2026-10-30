<template>
    <q-dialog
        v-model="modelOpen"
        persistent
        maximized
        transition-show="fade"
        transition-hide="fade"
    >
        <div class="scan-overlay">
            <!-- ── Camera viewport ──────────────────────────────────── -->
            <video ref="videoRef" class="scan-video" muted playsinline autoplay />

            <!-- ── Dim overlay + crosshair box ──────────────────────── -->
            <!-- Suppressed when the camera can't run at all: a viewfinder
                 crosshair over a black rectangle promises a camera that is
                 never going to arrive. -->
            <div v-if="!cameraUnavailable" class="scan-mask">
                <div class="scan-target" :class="{ flash: flashKind }" :data-flash="flashKind" />
            </div>

            <!-- Camera-unavailable explainer. Only after a start attempt found
                 no camera API; the manual barcode box below stays usable. -->
            <div v-if="cameraUnavailable" class="scan-unavailable">
                <div class="scan-unavailable__card">
                    <q-icon :name="ICONS.info_outline" size="28px" class="q-mb-sm" />
                    <div class="scan-unavailable__title">
                        {{ cameraUnavailable.kind === 'insecure-context'
                            ? 'The camera needs a secure connection'
                            : 'Camera not available here' }}
                    </div>
                    <div class="scan-unavailable__body">{{ cameraUnavailable.message }}</div>
                </div>
            </div>

            <!-- ── Recent-decode banner (auto-fades) ────────────────── -->
            <transition name="fade">
                <div v-if="lastDecodeBanner" class="scan-banner">
                    <q-icon :name="ICONS.check_circle" size="18px" class="q-mr-xs" />
                    Decoded
                    <code class="q-ml-xs">{{ truncate(lastDecodeBanner) }}</code>
                </div>
            </transition>

            <!-- ── Action-result banner (FU-378) ────────────────────────
                 In action mode the parent applies the scan (e.g. set a
                 level) and calls pushResult() with the per-item outcome, so
                 the banner shows "<item> → <level>" or the failure reason
                 rather than the raw barcode value. -->
            <transition name="fade">
                <div
                    v-if="actionBanner"
                    class="scan-banner"
                    :class="actionBanner.ok ? 'scan-banner--ok' : 'scan-banner--bad'"
                >
                    <q-icon
                        :name="actionBanner.ok ? ICONS.check_circle : ICONS.error"
                        size="18px"
                        class="q-mr-xs"
                    />
                    {{ actionBanner.text }}
                </div>
            </transition>

            <!-- ── Top bar ──────────────────────────────────────────── -->
            <div class="scan-topbar">
                <div class="scan-status">
                    <!-- The unavailable case owns the centre panel, so the top
                         bar just names it rather than repeating the paragraph. -->
                    <span v-if="cameraUnavailable">Type a barcode below</span>
                    <span v-else-if="cameraError" class="scan-error">{{ cameraError }}</span>
                    <span v-else-if="!cameraReady">Starting camera…</span>
                    <span v-else>Point at a barcode or QR</span>
                    <div v-if="cameraWarning && !cameraReady && !cameraUnavailable" class="scan-warning">
                        {{ cameraWarning }}
                    </div>
                </div>
                <div class="scan-actions">
                    <BaseButton
                        :aria-label="torchOn ? 'Turn torch off' : 'Turn torch on'"
                        v-if="torchSupported"
                        variant="icon"
                        :icon="torchOn ? 'flashlight_on' : 'flashlight_off'"
                        color="white"
                        @click="toggleTorch"
                    />
                    <BaseButton
                        aria-label="Close scanner"
                        variant="icon"
                        :icon="ICONS.close"
                        color="white"
                        @click="onClose"
                    />
                </div>
            </div>

            <!-- ── Manual entry escape hatch ────────────────────────── -->
            <div class="scan-bottombar">
                <!-- FU-378 — caller-owned control zone (e.g. the current-action
                     switcher). Kept above the manual-entry box so it's always
                     visible while scanning and clear of the centred target. -->
                <div v-if="$slots.controls" class="scan-controls">
                    <slot name="controls" />
                </div>
                <q-input
                    v-model="manualValue"
                    dense
                    dark
                    standout="dora-bg-sunken text-white"
                    label="Or type a barcode"
                    label-color="grey-4"
                    @keyup.enter="onManualSubmit"
                >
                    <template #append>
                        <BaseButton
                            variant="ghost"
                            dense
                            color="white"
                            label="Submit"
                            :disable="!manualValue.trim()"
                            @click="onManualSubmit"
                        />
                    </template>
                </q-input>
            </div>
        </div>
    </q-dialog>
</template>

<script lang="ts" setup>
    import BaseButton from 'src/components/BaseButton.vue';
    import {
        explainCameraFailure, insecureContextWarning,
        type CameraUnavailable,
    } from 'src/helpers/cameraAvailability';
    import { ICONS } from 'src/style/icons';
    import type { BrowserMultiFormatReader, IScannerControls } from '@zxing/browser';
    import { ref, watch, onBeforeUnmount, computed } from 'vue';

    interface Props {
        modelValue: boolean;
        /** Close the overlay automatically after the first successful
         *  decode. Useful for "scan to navigate" flows; off by default so
         *  the user can keep scanning. */
        closeOnDecode?: boolean;
        /** FU-378 — suppress the built-in "Decoded <code>" banner + success
         *  chime on decode, letting the parent report the real per-item
         *  outcome via pushResult() once its async apply resolves. Keeps the
         *  debounce; only the feedback is deferred. */
        deferFeedback?: boolean;
    }
    const props = withDefaults(defineProps<Props>(), {
        closeOnDecode: false,
        deferFeedback: false,
    });
    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
        (e: 'decoded', value: string): void;
    }>();

    const modelOpen = computed({
        get: () => props.modelValue,
        set: (v) => emit('update:modelValue', v),
    });

    const videoRef = ref<HTMLVideoElement | null>(null);
    const cameraReady = ref(false);
    const cameraError = ref<string | null>(null);
    // Set when a start attempt found no camera API at all (usually plain http).
    // Kept separate from `cameraError` so it gets the explainer panel rather
    // than a one-line fault.
    const cameraUnavailable = ref<CameraUnavailable | null>(null);
    const cameraWarning = insecureContextWarning();
    const flashKind = ref<'' | 'good' | 'bad'>('');
    const manualValue = ref('');
    const torchSupported = ref(false);
    const torchOn = ref(false);
    // Short-lived banner content; reset by a timer 1.5 s after the last
    // successful decode.
    const lastDecodeBanner = ref<string | null>(null);
    let bannerTimer: ReturnType<typeof setTimeout> | null = null;
    // FU-378 — action-mode result banner, pushed by the parent after it
    // applies a scan (distinct from the raw-decode banner so the two never
    // collide: defer mode uses this one, the legacy jump flow uses the other).
    const actionBanner = ref<{ text: string; ok: boolean } | null>(null);
    let actionBannerTimer: ReturnType<typeof setTimeout> | null = null;

    // The active reader + media stream so we can clean them up on close.
    // Lazy-loaded so the chunk only ships when the dialog opens.
    let codeReader: BrowserMultiFormatReader | null = null;
    let controls: IScannerControls | null = null;
    let stream: MediaStream | null = null;
    let audioCtx: AudioContext | null = null;
    // Bumped by every start and stop. A start still awaiting the camera (the
    // permission prompt) when the overlay closes sees a newer generation, shuts
    // down what it opened, and its decode callback goes quiet.
    let scanGeneration = 0;

    // Debounce identical decodes for 2 seconds. Without this, holding a
    // code in front of the camera fires the lookup once per frame.
    const DEBOUNCE_MS = 2000;
    let lastDecoded: string | null = null;
    let lastDecodedAt = 0;

    watch(modelOpen, async (open) => {
        if (open) {
            await startScanner();
        } else {
            stopScanner();
            // Clear any lingering result banner so a reopen starts fresh.
            if (actionBannerTimer) clearTimeout(actionBannerTimer);
            actionBanner.value = null;
        }
    });

    onBeforeUnmount(() => {
        if (bannerTimer) clearTimeout(bannerTimer);
        if (actionBannerTimer) clearTimeout(actionBannerTimer);
        void stopScanner();
    });

    async function startScanner() {
        const generation = ++scanGeneration;
        const isStale = () => generation !== scanGeneration;
        cameraError.value = null;
        cameraReady.value = false;
        torchOn.value = false;
        cameraUnavailable.value = null;
        try {
            const { BrowserMultiFormatReader } = await import('@zxing/browser');
            if (isStale()) return;
            codeReader = new BrowserMultiFormatReader();

            // Pick a back-facing camera when one is exposed; otherwise just
            // use whatever the browser hands us first.
            const devices = await (
                await import('@zxing/browser')
            ).BrowserCodeReader.listVideoInputDevices().catch(() => []);
            const preferred =
                devices.find((d) => /back|rear|environment/i.test(d.label))
                ?? devices[0];

            if (isStale() || !codeReader) return;
            const started = await codeReader.decodeFromVideoDevice(
                preferred?.deviceId,
                videoRef.value ?? undefined,
                (result) => {
                    if (!result || isStale()) return;
                    const text = result.getText?.() ?? String(result);
                    handleDecoded(text);
                },
            );
            if (isStale()) {
                try { started.stop(); } catch { /* ignore */ }
                return;
            }
            controls = started;
            cameraReady.value = true;
            // Capture the live MediaStream so we can probe the video track
            // for torch capability.
            stream = (videoRef.value?.srcObject as MediaStream) ?? null;
            const track = stream?.getVideoTracks?.()[0];
            const caps = track?.getCapabilities?.() as
                | (MediaTrackCapabilities & { torch?: boolean })
                | undefined;
            torchSupported.value = Boolean(caps?.torch);
        } catch (err) {
            if (isStale()) return;
            const unavailable = explainCameraFailure();
            if (unavailable) {
                cameraUnavailable.value = unavailable;
                return;
            }
            const message = err instanceof Error ? err.message : String(err);
            // NotAllowedError / NotFoundError land here. Surface a friendly
            // hint rather than the raw browser exception name.
            if (/permission|notallowed/i.test(message)) {
                cameraError.value =
                    'Camera permission denied. Enable it in your browser settings to scan.';
            } else if (/notfound|nomatch/i.test(message)) {
                cameraError.value =
                    'No camera available. Try the manual-entry box below.';
            } else {
                cameraError.value = `Couldn't start the camera: ${message}`;
            }
        }
    }

    function stopScanner() {
        scanGeneration++;
        try {
            controls?.stop?.();
        } catch { /* ignore */ }
        controls = null;
        try {
            stream?.getTracks?.().forEach((t) => t.stop());
        } catch { /* ignore */ }
        stream = null;
        codeReader = null;
        torchOn.value = false;
        torchSupported.value = false;
        cameraReady.value = false;
        cameraUnavailable.value = null;
    }

    function handleDecoded(text: string) {
        const now = Date.now();
        if (text === lastDecoded && now - lastDecodedAt < DEBOUNCE_MS) return;
        lastDecoded = text;
        lastDecodedAt = now;
        // In defer mode the parent owns the feedback (pushResult) once its
        // async apply resolves — don't flash a premature green.
        if (!props.deferFeedback) {
            showBanner(text);
            void flashAndChime('good');
        }
        emit('decoded', text);
        if (props.closeOnDecode) modelOpen.value = false;
    }

    function showBanner(text: string) {
        lastDecodeBanner.value = text;
        if (bannerTimer) clearTimeout(bannerTimer);
        bannerTimer = setTimeout(() => { lastDecodeBanner.value = null; }, 1500);
    }

    function truncate(value: string): string {
        return value.length > 28 ? `${value.slice(0, 28)}…` : value;
    }

    function onManualSubmit() {
        const value = manualValue.value.trim();
        if (!value) return;
        manualValue.value = '';
        // Don't dedup manual entries — the user typed it on purpose.
        lastDecoded = null;
        if (!props.deferFeedback) {
            showBanner(value);
            void flashAndChime('good');
        }
        emit('decoded', value);
        if (props.closeOnDecode) modelOpen.value = false;
    }

    /** Short visual + audio cue. Tone uses Web Audio so we don't ship a
     *  bundled .wav. `kind` picks pitch (good = high, bad = low). */
    function flashAndChime(kind: 'good' | 'bad') {
        flashKind.value = kind;
        setTimeout(() => { flashKind.value = ''; }, 250);
        try {
            if (!audioCtx) {
                const Ctor =
                    window.AudioContext ??
                    (window as unknown as { webkitAudioContext?: typeof AudioContext })
                        .webkitAudioContext;
                if (!Ctor) return;
                audioCtx = new Ctor();
            }
            const ctx = audioCtx;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.type = 'sine';
            osc.frequency.value = kind === 'good' ? 880 : 240;
            gain.gain.setValueAtTime(0.0001, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.15, ctx.currentTime + 0.015);
            gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.15);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.18);
        } catch {
            // Browsers without WebAudio (or with autoplay blocks) — silent.
        }
    }

    /** Public method for callers (e.g. unknown-barcode flow) to signal a
     *  problem without closing the overlay. */
    function flashBad() {
        void flashAndChime('bad');
    }

    /** FU-378 — action-mode result feedback. The parent applies the scan
     *  (set level, etc.) and calls this with the outcome so the overlay
     *  shows "<item> → <level>" (green) or the reason it couldn't act (red),
     *  and chimes to match. Stays open so the user keeps scanning. */
    function pushResult(message: string, kind: 'good' | 'bad') {
        actionBanner.value = { text: message, ok: kind === 'good' };
        if (actionBannerTimer) clearTimeout(actionBannerTimer);
        actionBannerTimer = setTimeout(() => { actionBanner.value = null; }, 2000);
        void flashAndChime(kind);
    }

    async function toggleTorch() {
        if (!torchSupported.value || !stream) return;
        const track = stream.getVideoTracks?.()[0];
        if (!track) return;
        try {
            torchOn.value = !torchOn.value;
            await track.applyConstraints({
                advanced: [{ torch: torchOn.value }],
            } as unknown as MediaTrackConstraints);
        } catch {
            // Some Android cameras lie about torch capability. Don't fail
            // the whole overlay; just flip the toggle back.
            torchOn.value = !torchOn.value;
        }
    }

    function onClose() {
        modelOpen.value = false;
    }

    defineExpose({ flashBad, pushResult });
</script>

<style scoped>
    .scan-overlay {
        position: relative;
        width: 100vw;
        height: 100vh;
        background: #000;
        overflow: hidden;
    }
    .scan-video {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    .scan-mask {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: radial-gradient(
            ellipse 38% 28% at center,
            transparent 0%,
            transparent 60%,
            var(--overlay-scrim) 60%
        );
        pointer-events: none;
    }
    .scan-target {
        width: min(70vw, 320px);
        height: min(40vh, 220px);
        border: 2px solid rgba(255, 255, 255, 0.85);
        border-radius: 12px;
        box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.35);
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .scan-target.flash[data-flash='good'] {
        border-color: #4caf50;
        box-shadow: 0 0 0 9999px rgba(0, 80, 0, 0.45);
    }
    .scan-target.flash[data-flash='bad'] {
        border-color: #ef5350;
        box-shadow: 0 0 0 9999px rgba(80, 0, 0, 0.45);
    }
    /* Camera-unavailable explainer. Occupies the viewfinder area (the video
       element behind it is black — no stream ever starts), centred and
       readable, sitting above the manual-entry bar which remains the working
       path. Text is inverse-on-scrim like the rest of this overlay's chrome. */
    .scan-unavailable {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
        pointer-events: none;
    }
    .scan-unavailable__card {
        max-width: 420px;
        text-align: center;
        color: var(--text-inverse);
        background: var(--overlay-scrim);
        border-radius: 12px;
        padding: 20px 22px;
    }
    .scan-unavailable__title {
        font-weight: 600;
        font-size: 16px;
        margin-bottom: 8px;
    }
    .scan-unavailable__body {
        font-size: 14px;
        line-height: 1.5;
        opacity: 0.92;
    }
    .scan-topbar {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        padding: 10px 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
        color: var(--text-inverse);
        background: linear-gradient(var(--overlay-scrim), transparent);
    }
    .scan-status {
        font-size: 14px;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.6);
    }
    .scan-warning {
        margin-top: 4px;
        font-size: 12px;
        color: var(--semantic-warning);
    }
    .scan-error { color: #ffb4ab; }
    .scan-actions { display: flex; gap: 4px; }
    .scan-bottombar {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        padding: 12px;
        background: linear-gradient(transparent, var(--overlay-scrim));
    }
    .scan-banner {
        position: absolute;
        top: 56px;
        left: 50%;
        transform: translateX(-50%);
        padding: 6px 14px;
        background: rgba(76, 175, 80, 0.92);
        color: var(--text-inverse);
        border-radius: 999px;
        font-size: 13px;
        display: flex;
        align-items: center;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        max-width: 90vw;
    }
    /* FU-378 — action-result banner colours mirror the good/bad flash. */
    .scan-banner--ok { background: rgba(76, 175, 80, 0.92); }
    .scan-banner--bad { background: rgba(239, 83, 80, 0.94); }
    /* FU-378 — caller-owned control zone (current-action switcher). Centred
       above the manual-entry box. */
    .scan-controls {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        margin-bottom: 12px;
    }
    .fade-enter-active, .fade-leave-active { transition: opacity 0.18s ease; }
    .fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
