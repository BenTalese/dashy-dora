import { onBeforeUnmount, ref } from 'vue';
import { currentLocale } from 'src/composables/useMoney';
import SttApiService, { type SttStatus } from 'src/services/api/sttApiService';

/**
 * P2-13 — Web Speech API wrapper for speech-to-text.
 *
 * Two callsites today: Dora chat (push-to-talk: start on mic press,
 * stop on press-again or final result), and Cook mode (continuous:
 * stays listening so the user can keep saying "next" / "previous"
 * hands-free). The `continuous` option flips between the two; defaults
 * to false (push-to-talk) so the cheaper / less-permission-anxious
 * mode is the default.
 *
 * Browser support: Chrome desktop + Chrome Android have it natively.
 * Safari/iOS exposes `webkitSpeechRecognition` but emits final results
 * less reliably; the page should fall back to typing when
 * `available.value === false`. We never throw on missing API support —
 * the caller just sees `available=false` and can choose to hide the UI.
 *
 * Permission failures (user denies the mic prompt) are surfaced through
 * `error.value`; the caller can render a friendly message rather than
 * a silent failure.
 *
 * FU-788 — where the browser has no recognizer (Firefox), Dora's server can
 * listen instead when its speech engine is set up (Settings → Voice): the mic
 * is recorded with `MediaRecorder`, a clip ends after a beat of silence, and
 * the server's Whisper turns it into text. Same callbacks, no interim text.
 */

type SpeechRecognitionLike = {
    continuous: boolean;
    interimResults: boolean;
    lang: string;
    start: () => void;
    stop: () => void;
    onresult: ((event: SpeechResultEvent) => void) | null;
    onend: (() => void) | null;
    onerror: ((event: { error?: string }) => void) | null;
};

type SpeechResultEvent = {
    /** Index of the first result that changed in this event. */
    resultIndex: number;
    results: ArrayLike<
        ArrayLike<{ transcript: string }> & { isFinal: boolean }
    >;
};

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getRecognitionCtor(): SpeechRecognitionCtor | null {
    if (typeof window === 'undefined') return null;
    const w = window as unknown as {
        SpeechRecognition?: SpeechRecognitionCtor;
        webkitSpeechRecognition?: SpeechRecognitionCtor;
    };
    return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export type UseVoiceInputOptions = {
    /** When true, keep listening across pauses (Cook mode). When false,
     *  one shot — auto-stops after the first final result (push-to-talk
     *  on the Dora mic). */
    continuous?: boolean;
    /** BCP-47 tag. When omitted, falls back to the install-wide locale
     *  from `useMoney()`'s money policy — which is the same setting the
     *  admin chose for currency/dates. That keeps voice input in the
     *  household's tongue on non-AU installs instead of a hardcoded
     *  `en-AU` default (FU-043 Layer B). */
    lang?: string;
    /** Fires for every result (interim or final) so the caller can
     *  render a live transcript. */
    onInterim?: (text: string) => void;
    /** Fires once per final result. The caller decides what to do with
     *  it (append to a prompt, dispatch a command, etc.). */
    onFinal?: (text: string) => void;
    /** Continuous mode only. When this returns true, hold off the automatic
     *  `onend` restart until it goes false (or the safety cap elapses).
     *
     *  Cook mode passes speech-output's `busy` (FU-723): on Android, *opening*
     *  the mic shifts audio focus, and a recognizer restart landing in the same
     *  moment a clip starts playing can eat the front of that clip. Deferring
     *  the restart — rather than stopping the recognizer while Dora talks —
     *  keeps **barge-in** working: an already-open mic still hears "next" over
     *  the top of her narration, which is the whole point of hands-free. Only
     *  the re-open is deferred. */
    deferRestartWhile?: () => boolean;
};

/** Safety cap on `deferRestartWhile`. If a caller's predicate never goes false
 *  (a stuck utterance, a promise that never settles), restart anyway rather
 *  than leaving the user's mic dead for the rest of the session. */
const RESTART_DEFER_MAX_MS = 10_000;
const RESTART_DEFER_POLL_MS = 150;

// ── Server recognizer (FU-788) ───────────────────────────────────────────
const sttApi = new SttApiService();
let sttStatusPromise: Promise<SttStatus> | null = null;

/** Whether this server can transcribe, asked once per page load. `refresh`
 *  re-asks (Settings → Voice after a model download). */
export function serverSttStatus(refresh = false): Promise<SttStatus> {
    if (refresh || !sttStatusPromise) {
        sttStatusPromise = sttApi.getStatusAsync()
            .then((r) => r.status)
            .catch(() => 'unavailable' as const);
    }
    return sttStatusPromise;
}

function canRecord(): boolean {
    return typeof window !== 'undefined'
        && typeof window.MediaRecorder !== 'undefined'
        && !!navigator.mediaDevices?.getUserMedia;
}

/** Loudness (RMS of the waveform, 0–1) above which the mic counts as speech. */
const SPEECH_RMS = 0.02;
/** Quiet after speech that ends a clip. */
const CLIP_END_SILENCE_MS = 1200;
/** A clip is cut here even mid-sentence; a spoken command is a few seconds. */
const CLIP_MAX_MS = 15_000;
/** Push-to-talk gives up when nothing is said for this long. */
const NO_SPEECH_TIMEOUT_MS = 8_000;
const MONITOR_MS = 100;

export function useVoiceInput(options: UseVoiceInputOptions = {}) {
    const continuous = options.continuous ?? false;
    // default the recognition locale from the install-
    // wide locale setting, falling back to the browser's own locale, then
    // to en-AU as the ultimate safety net. Never a hardcoded `en-AU` when
    // the admin has chosen otherwise.
    const lang = options.lang
        ?? currentLocale()
        ?? (typeof navigator !== 'undefined' ? navigator.language : null)
        ?? 'en-AU';

    const ctor = getRecognitionCtor();
    const available = ref<boolean>(ctor !== null);
    // No recognizer in this browser: the server can listen if it's set up.
    const useServer = ctor === null && canRecord();
    if (useServer) {
        void serverSttStatus().then((status) => { available.value = status === 'ready'; });
    }
    const listening = ref<boolean>(false);
    const transcript = ref<string>('');
    const error = ref<string | null>(null);

    let recognition: SpeechRecognitionLike | null = null;
    // `intentionalStop` distinguishes a user-requested stop from a
    // browser-side `onend` (which we restart in continuous mode).
    let intentionalStop = false;

    // Pending deferred-restart timer, so a user-requested stop (or a teardown)
    // can cancel a restart that hasn't fired yet.
    let restartTimer: ReturnType<typeof setTimeout> | null = null;

    function clearRestartTimer() {
        if (restartTimer !== null) {
            clearTimeout(restartTimer);
            restartTimer = null;
        }
    }

    /** Poll `deferRestartWhile` until it clears, then restart the recognizer.
     *  Gives up (and restarts anyway) after RESTART_DEFER_MAX_MS. */
    function deferredRestart(r: SpeechRecognitionLike, waitedMs = 0) {
        clearRestartTimer();
        restartTimer = setTimeout(() => {
            restartTimer = null;
            // The user stopped listening, or moved on, while we waited.
            if (intentionalStop || !listening.value) {
                listening.value = false;
                intentionalStop = false;
                return;
            }
            const next = waitedMs + RESTART_DEFER_POLL_MS;
            if (options.deferRestartWhile?.() && next < RESTART_DEFER_MAX_MS) {
                deferredRestart(r, next);
                return;
            }
            try {
                r.start();
            } catch {
                listening.value = false;
            }
        }, RESTART_DEFER_POLL_MS);
    }

    function buildRecognition(): SpeechRecognitionLike | null {
        if (!ctor) return null;
        const r = new ctor();
        r.continuous = continuous;
        r.interimResults = true;
        r.lang = lang;
        r.onresult = (event) => {
            // Walk the results: emit interim text for the live caption,
            // and fire `onFinal` per final result. Web Speech delivers
            // a cumulative result list across the session, so start at
            // `resultIndex` (the first changed result) — iterating from 0
            // re-fired every earlier final command in continuous mode.
            let interim = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const res = event.results[i];
                if (!res) continue;
                const alt = res[0];
                if (!alt) continue;
                if (res.isFinal) {
                    const text = alt.transcript.trim();
                    if (text) {
                        transcript.value = text;
                        options.onFinal?.(text);
                    }
                } else {
                    interim += alt.transcript;
                }
            }
            if (interim) {
                transcript.value = interim.trim();
                options.onInterim?.(interim.trim());
            }
        };
        r.onend = () => {
            // In continuous mode the browser may stop after a long
            // silence. Restart unless the user asked to stop.
            if (continuous && !intentionalStop && listening.value) {
                if (options.deferRestartWhile?.()) {
                    // Dora is mid-utterance — wait her out, then restart.
                    // Keeps the mic closed only across the moment that would
                    // clip her audio, not for as long as she is talking.
                    deferredRestart(r);
                    return;
                }
                try {
                    r.start();
                    return;
                } catch {
                    // Some browsers throw when start() is called too
                    // quickly after stop; fall through to "stopped".
                }
            }
            listening.value = false;
            intentionalStop = false;
        };
        r.onerror = (e) => {
            error.value = e.error ?? 'unknown';
            listening.value = false;
        };
        return r;
    }

    // ── Server recognizer: record, cut on silence, transcribe ──────────
    let stream: MediaStream | null = null;
    let recorder: MediaRecorder | null = null;
    let audioCtx: AudioContext | null = null;
    let monitor: ReturnType<typeof setInterval> | null = null;

    function stopMonitor() {
        if (monitor !== null) { clearInterval(monitor); monitor = null; }
    }

    function releaseMic() {
        stopMonitor();
        stream?.getTracks().forEach((t) => t.stop());
        stream = null;
        void audioCtx?.close().catch(() => undefined);
        audioCtx = null;
        recorder = null;
    }

    function beginClip() {
        if (!stream || !audioCtx) return;
        const chunks: Blob[] = [];
        const rec = new MediaRecorder(stream);
        recorder = rec;
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 1024;
        audioCtx.createMediaStreamSource(stream).connect(analyser);
        const samples = new Float32Array(analyser.fftSize);
        const startedAt = Date.now();
        let heard = false;
        let quietSince: number | null = null;

        rec.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
        rec.onstop = () => {
            stopMonitor();
            void finishClip(heard ? new Blob(chunks, { type: rec.mimeType }) : null);
        };
        rec.start();
        monitor = setInterval(() => {
            analyser.getFloatTimeDomainData(samples);
            let sum = 0;
            for (const v of samples) sum += v * v;
            const rms = Math.sqrt(sum / samples.length);
            const now = Date.now();
            if (rms > SPEECH_RMS) {
                heard = true;
                quietSince = null;
            } else if (heard) {
                quietSince ??= now;
            }
            const spokeThenPaused = heard && quietSince !== null && now - quietSince >= CLIP_END_SILENCE_MS;
            const tooLong = now - startedAt >= CLIP_MAX_MS;
            // Continuous mode keeps an idle mic open; push-to-talk gives up.
            const nothingSaid = !heard && !continuous && now - startedAt >= NO_SPEECH_TIMEOUT_MS;
            // `tooLong` also rolls an idle continuous-mode clip over, so a long
            // silence never grows one huge recording.
            if (spokeThenPaused || tooLong || nothingSaid) {
                stopMonitor();
                if (rec.state !== 'inactive') rec.stop();
            }
        }, MONITOR_MS);
    }

    async function finishClip(clip: Blob | null) {
        if (clip && clip.size > 0) {
            try {
                const text = (await sttApi.transcribeAsync(clip)).trim();
                if (text) {
                    transcript.value = text;
                    options.onFinal?.(text);
                }
            } catch {
                error.value = 'transcription-failed';
            }
        }
        if (continuous && listening.value && !intentionalStop) {
            nextClipWhenClear();
            return;
        }
        listening.value = false;
        intentionalStop = false;
        releaseMic();
    }

    /** Continuous mode: open the next clip, waiting out Dora's own speech
     *  (`deferRestartWhile`) so she isn't transcribed back at herself. */
    function nextClipWhenClear(waitedMs = 0) {
        clearRestartTimer();
        if (!options.deferRestartWhile?.() || waitedMs >= RESTART_DEFER_MAX_MS) {
            beginClip();
            return;
        }
        restartTimer = setTimeout(() => {
            restartTimer = null;
            if (intentionalStop || !listening.value) return;
            nextClipWhenClear(waitedMs + RESTART_DEFER_POLL_MS);
        }, RESTART_DEFER_POLL_MS);
    }

    async function startServer() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch (e) {
            error.value = e instanceof DOMException && e.name === 'NotAllowedError'
                ? 'not-allowed' : 'audio-capture';
            listening.value = false;
            return;
        }
        audioCtx = new AudioContext();
        beginClip();
    }

    function stopServer() {
        clearRestartTimer();
        if (recorder && recorder.state !== 'inactive') {
            // `onstop` sends what was said so far, then releases the mic.
            recorder.stop();
        } else {
            releaseMic();
        }
    }

    function start() {
        if (useServer) {
            if (!available.value || listening.value) return;
            error.value = null;
            transcript.value = '';
            intentionalStop = false;
            listening.value = true;
            void startServer();
            return;
        }
        if (!ctor) return;
        if (listening.value) return;
        error.value = null;
        transcript.value = '';
        intentionalStop = false;
        recognition = buildRecognition();
        if (!recognition) return;
        try {
            recognition.start();
            listening.value = true;
        } catch (e) {
            // Most commonly "InvalidStateError" — a prior session
            // hadn't fully torn down. Wait a tick and retry once.
            setTimeout(() => {
                try {
                    recognition?.start();
                    listening.value = true;
                } catch {
                    error.value = e instanceof Error ? e.message : 'failed';
                    listening.value = false;
                }
            }, 100);
        }
    }

    function stop() {
        intentionalStop = true;
        // Kill any pending deferred restart, or the mic would reopen moments
        // after the user asked it to stop.
        clearRestartTimer();
        if (useServer) {
            stopServer();
            listening.value = false;
            return;
        }
        if (recognition) {
            try {
                recognition.stop();
            } catch {
                /* ignore — stop after start race */
            }
        }
        listening.value = false;
    }

    function toggle() {
        if (listening.value) stop();
        else start();
    }

    // Defensive cleanup — if the component is unmounted mid-listen we
    // don't want a dangling recognition holding the mic indicator on
    // in the browser chrome.
    onBeforeUnmount(() => {
        if (listening.value) stop();
        clearRestartTimer();
        releaseMic();
        recognition = null;
    });

    return {
        available,
        /** True when this browser's voice input goes through Dora's server. */
        viaServer: useServer,
        listening,
        transcript,
        error,
        start,
        stop,
        toggle,
    };
}
