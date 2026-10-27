import { onBeforeUnmount, ref } from 'vue';
import { currentLocale } from 'src/composables/useMoney';

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
            // a cumulative result list across the session, so we
            // iterate from 0 and trust `isFinal` to gate emissions.
            let interim = '';
            for (let i = 0; i < event.results.length; i++) {
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

    function start() {
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
        recognition = null;
    });

    return {
        available,
        listening,
        transcript,
        error,
        start,
        stop,
        toggle,
    };
}
