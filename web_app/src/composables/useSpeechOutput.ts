import { onBeforeUnmount, ref } from 'vue';
import { useAuthStore } from 'src/stores/authStore';
import TtsApiService from 'src/services/api/ttsApiService';
import { SILENT_WAV_DATA_URL } from 'src/utils/audioUnlock';

/**
 * Speech output for Dora — used by Cook mode (announces the current step) and
 * Dora chat (speaks her replies when the user has output enabled).
 *
 * Two engines, chosen per-user (`voice_engine`):
 *   - `piper`   — POST /api/tts for a natural neural voice, played back through
 *                 an <audio> element. The user's `voice_id` picks the voice.
 *   - `browser` — the built-in Web SpeechSynthesis API (the original path).
 *
 * Piper is preferred when selected, but if it isn't configured/installed
 * server-side (the endpoint 503s) or the request otherwise fails, we fall back
 * to the browser voice for that utterance — so Dora is never silent. `speak()`
 * is idempotent: calling it again (or `cancel()`) supersedes any in-flight or
 * playing utterance, including a slow Piper fetch that hasn't resolved yet.
 *
 * `available.value` is true when *any* output path is usable: browser
 * SpeechSynthesis OR a server-configured Piper. It starts at the synchronous
 * browser-only answer; the per-session Piper probe (deduped across
 * composable instances) flips it true async if Piper alone would work, so the
 * Settings → Voice toggle and the chat mute button appear on browsers without
 * SpeechSynthesis (FU-289).
 */
/**
 * Does the *browser* voice actually work here?
 *
 * `'speechSynthesis' in window` is not the question. Firefox ships the API
 * object on every platform but only has voices where the OS gives it some:
 *   - Firefox/Windows speaks through SAPI5, which is usually populated;
 *   - Firefox/Linux needs `speech-dispatcher` installed, and reports **zero
 *     voices** without it;
 *   - Firefox/Android has no synthesis backend at all;
 *   - Firefox honours `media.webspeech.synth.enabled`, which some hardened
 *     profiles and forks ship off.
 * In every one of those cases `speechSynthesis.speak()` is accepted and then
 * silently does nothing — no error, no `onerror`, just silence. That is the
 * reported *"TTS isn't supported on Firefox for some reason"* (owner feedback
 * 2026-08-27): not a missing API, an empty voice list.
 *
 * So the real test is "are there voices?". They also load asynchronously —
 * `getVoices()` returns `[]` on first call in Firefox and Chrome alike, and
 * only fills in when `voiceschanged` fires — so this resolves rather than
 * answering synchronously, with a timeout for the browsers that never fire the
 * event at all. Cached per session: the voice list is an OS fact, not a
 * per-utterance one.
 *
 * The answer to "what browsers can we support?" follows from this: Dora's own
 * **Piper** engine is a `POST /api/tts` returning a WAV played through an
 * `<audio>` element, so it works in *every* browser that can play audio —
 * Firefox included, and identically on all of them. The browser voice is the
 * fallback, not the floor. Where Piper is configured, Firefox is fully
 * supported; where it isn't, we now say so plainly instead of being mute.
 */
const VOICE_LIST_TIMEOUT_MS = 2000;
let browserVoicesProbe: Promise<boolean> | null = null;
function probeBrowserVoices(): Promise<boolean> {
    browserVoicesProbe ??= new Promise<boolean>((resolve) => {
        if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
            resolve(false);
            return;
        }
        const synth = window.speechSynthesis;
        if (synth.getVoices().length > 0) {
            resolve(true);
            return;
        }
        let settled = false;
        const finish = () => {
            if (settled) return;
            settled = true;
            synth.removeEventListener('voiceschanged', finish);
            window.clearTimeout(timer);
            resolve(synth.getVoices().length > 0);
        };
        const timer = window.setTimeout(finish, VOICE_LIST_TIMEOUT_MS);
        synth.addEventListener('voiceschanged', finish);
    });
    return browserVoicesProbe;
}

const ttsProbe = new TtsApiService();
// Cached per session — `configured` is install-time server state, not
// per-request. Resolves true when Piper would handle a `speak()`.
let piperConfiguredProbe: Promise<boolean> | null = null;
function probePiperConfigured(): Promise<boolean> {
    piperConfiguredProbe ??= ttsProbe
        .getVoicesAsync()
        .then((r) => r.configured === true)
        .catch(() => false);
    return piperConfiguredProbe;
}

// iOS / WKWebView audio-unlock primer.
//
// iOS Safari (and the macOS WKWebView the desktop bundle uses on Mac)
// enforce a strict user-gesture rule for `HTMLAudioElement.play()`. The
// gesture-permission "credit" is consumed the first time `play()` is
// called after user interaction, and it can be REVOKED by an intervening
// `await` that spans more than ~a few hundred ms. Two flows this bites:
//   - Dora chat reply: LLM round-trip (`await`) → Piper synth fetch
//     (`await`) → new `<audio>` → `audio.play()`. On iOS, by the time
//     we call `play()` the gesture is often gone.
//   - Cook-mode timer-fired narration: no gesture at all (timer callback
//     is not a user activation). This can't be fixed by a primer alone;
//     documented at the caller.
//
// Fix: on the first user interaction in the tab session, play a very-
// short silent muted audio blob to prime the browser's autoplay policy.
// Subsequent `Audio.play()` calls in the same session inherit the
// credit — including calls that happen across `await`s. On every other
// platform this is a harmless no-op (Chrome/Firefox/Android don't gate
// on gesture-per-play for muted audio).
//
// The silent-WAV primer + the per-element primitive both live in
// `utils/audioUnlock` now (R-003 — the settings Preview reuses them). This
// primer plays the silent blob once per session on the first gesture to prime
// iOS's per-session credit; `AudioContext.resume()` was rejected as it hits the
// same iOS gesture wall for a heavier dep.
let audioUnlocked = false;
let audioUnlockRegistered = false;
function unlockAudioOnFirstGesture(): void {
    if (audioUnlockRegistered || typeof document === 'undefined') return;
    audioUnlockRegistered = true;

    const events: Array<keyof DocumentEventMap> =
        ['pointerdown', 'touchstart', 'keydown', 'click'];
    const cleanup = (): void => {
        for (const type of events) document.removeEventListener(type, primer, true);
    };
    const primer = (): void => {
        // One-shot: drop listeners immediately so subsequent gestures
        // don't re-run this no-op. The listeners survive `once: false`
        // because we register on multiple event types — cleanup removes
        // them from all types together.
        cleanup();
        if (audioUnlocked) return;
        try {
            const audio = new Audio(SILENT_WAV_DATA_URL);
            audio.muted = true;
            const p = audio.play();
            if (p != null && typeof p.then === 'function') {
                p.then(() => {
                    audioUnlocked = true;
                    // Stop immediately — we only needed the play() call
                    // itself to claim the gesture credit.
                    audio.pause();
                }).catch(() => {
                    // A play() rejection here means the gesture didn't
                    // count (e.g. programmatic dispatch, unusual browser
                    // state). We accept the one-shot cost — trying every
                    // gesture would leak listeners on non-iOS platforms
                    // that never needed the primer in the first place.
                });
            } else {
                // Legacy browsers where play() returned undefined.
                audioUnlocked = true;
            }
        } catch {
            // Some environments throw before returning a promise —
            // treat the same as a rejected promise (one-shot done).
        }
    };
    for (const type of events) {
        document.addEventListener(type, primer, {
            passive: true,
            capture: true,
        });
    }
}

// How long to let a `speechSynthesis.cancel()` settle before queueing the next
// utterance (see `speakBrowser`). Long enough for Chrome's internal cancel to
// land, short enough that a "next step" tap still feels immediate.
const BROWSER_CANCEL_SETTLE_MS = 120;
// Cap on waiting for a decoded blob to become playable (see `whenPlayable`).
// The blob is already fully in memory, so this should resolve in a frame or
// two; the timeout only stops a browser that never fires the event from
// leaving Dora mute.
const AUDIO_READY_TIMEOUT_MS = 1500;

/**
 * Resolve once `audio` has buffered enough to play from its true start.
 *
 * Calling `play()` on a freshly constructed element can begin playback before
 * the decoder is ready, and some mobile builds drop the leading samples rather
 * than waiting — the reported "beginning of the sentence is cut off, random how
 * much". The blob is already complete in memory (the server buffers the whole
 * WAV and `res.blob()` awaits the full body), so this is a decode wait, not a
 * network one, and normally costs a frame.
 *
 * Resolves rather than rejects on `error`/timeout: the caller's `play()` is a
 * better place to surface a real failure, and a browser that never fires
 * `canplay` must not leave Dora silent.
 */
function whenPlayable(audio: HTMLAudioElement): Promise<void> {
    // HAVE_FUTURE_DATA or better — already safe to start.
    if (audio.readyState >= 3) return Promise.resolve();
    return new Promise<void>((resolve) => {
        let settled = false;
        const finish = () => {
            if (settled) return;
            settled = true;
            audio.removeEventListener('canplaythrough', finish);
            audio.removeEventListener('canplay', finish);
            audio.removeEventListener('error', finish);
            window.clearTimeout(timer);
            resolve();
        };
        const timer = window.setTimeout(finish, AUDIO_READY_TIMEOUT_MS);
        audio.addEventListener('canplaythrough', finish);
        audio.addEventListener('canplay', finish);
        audio.addEventListener('error', finish);
    });
}

export function useSpeechOutput() {
    // register the iOS audio-unlock primer once per session on
    // the first `useSpeechOutput()` instantiation (which is early — the
    // MainLayout mounts Dora chat + cook mode both consume this).
    // Idempotent across composable instances.
    unlockAudioOnFirstGesture();

    // The API is present. Says nothing about whether it can make a sound —
    // see `probeBrowserVoices`. Used only to decide whether it is worth
    // *trying* the browser path; `browserVoiceUsable` decides whether to
    // count on it.
    const browserApiPresent =
        typeof window !== 'undefined' && 'speechSynthesis' in window;
    /** True once the browser has been confirmed to hold at least one voice.
     *  Starts pessimistic and is corrected by the async probe below, because
     *  the optimistic answer is the one that leaves Dora silently mute. */
    const browserVoiceUsable = ref<boolean>(false);
    /** True when Dora's own neural engine is configured server-side. */
    const piperConfigured = ref<boolean>(false);
    const available = ref<boolean>(false);
    const speaking = ref<boolean>(false);
    // `speaking` is only true once audio is actually coming out. `busy` also
    // covers the gap before that — the Piper fetch, and the browser path's
    // cancel-settle delay — because callers that need to keep out of the way
    // (cook mode holds the mic's auto-restart, FU-723) must do so for the whole
    // utterance, not just its audible part. Cleared by cancel() and by every
    // terminal outcome, with a caller-side timeout as the backstop.
    const busy = ref<boolean>(false);
    // Which engine last actually produced sound. The Piper→browser fallback is
    // otherwise invisible, and the two engines have different failure
    // modes — without this you cannot tell which one you are debugging
    // (FU-722). Surfaced in cook mode's Sous Chef popover.
    // FU-722 diagnostic: no reader since the 2026-09-03 popover went; kept
    // until the clipping investigation closes (finalisation 04-R16).
    const lastEngine = ref<'piper' | 'browser' | null>(null);

    // Both probes always run, and `available` is their OR. The old code short-
    // circuited the Piper probe whenever `'speechSynthesis' in window` was
    // true, which is exactly the Firefox case: the API was present, the answer
    // was "available", and nothing ever came out. Knowing which of the two
    // paths is live is also what lets Settings explain the situation rather
    // than just hiding a toggle (FU-289 kept: the toggle still appears when
    // Piper alone would work).
    void probeBrowserVoices().then((ok) => {
        browserVoiceUsable.value = ok;
        if (ok) available.value = true;
    });
    void probePiperConfigured().then((ok) => {
        piperConfigured.value = ok;
        if (ok) available.value = true;
    });

    const authStore = useAuthStore();
    const ttsApi = new TtsApiService();

    let currentAudio: HTMLAudioElement | null = null;
    let currentUrl: string | null = null;
    // Monotonic token bumped by every speak()/cancel(). A Piper fetch that
    // resolves after a newer call is discarded instead of talking over the
    // current utterance.
    let seq = 0;

    function stopAudio() {
        if (currentAudio) {
            currentAudio.onplay = null;
            currentAudio.onended = null;
            currentAudio.onpause = null;
            currentAudio.onerror = null;
            currentAudio.pause();
            currentAudio = null;
        }
        if (currentUrl) {
            URL.revokeObjectURL(currentUrl);
            currentUrl = null;
        }
    }

    function speakBrowser(text: string, token: number) {
        if (!browserApiPresent) { releaseBusy(token); return; }
        const synth = window.speechSynthesis;
        const utter = new SpeechSynthesisUtterance(text);
        utter.onstart = () => {
            speaking.value = true;
            lastEngine.value = 'browser';
        };
        utter.onend = () => { speaking.value = false; busy.value = false; };
        utter.onerror = () => { speaking.value = false; busy.value = false; };

        // `cancel()` has already run (every path into here goes through
        // `speak()` → `cancel()`), so the redundant second `synth.cancel()`
        // that used to sit here is gone. It mattered: Chrome — Android
        // especially — treats `cancel()` as asynchronous internally, and an
        // utterance queued in the *same task* as the cancel that preceded it
        // is clipped or dropped outright, by a varying amount. That is the
        // signature of the reported "start of the sentence is missing, random
        // how much" (candidate fix — see FU-722; the fallback path is silent
        // about which engine spoke, so this is unconfirmed).
        const start = () => {
            // A newer speak()/cancel() while we were waiting wins.
            if (token !== seq) return;
            synth.speak(utter);
        };
        if (synth.speaking || synth.pending) {
            window.setTimeout(start, BROWSER_CANCEL_SETTLE_MS);
        } else {
            start();
        }
    }

    /** Clear `busy` unless a newer utterance has already claimed it. */
    function releaseBusy(token: number) {
        if (token === seq) busy.value = false;
    }

    /** Returns true when Piper handled the utterance (played, or was
     * superseded by a newer call); false when it failed and the caller should
     * fall back to the browser voice. */
    async function playPiper(text: string, voiceId: string, token: number): Promise<boolean> {
        try {
            const blob = await ttsApi.synthesizeAsync(text, voiceId);
            if (token !== seq) return true; // superseded — don't play or fall back
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            // `preload` is 'metadata' by default on some mobile builds, which is
            // not enough to start cleanly from sample zero.
            audio.preload = 'auto';
            currentAudio = audio;
            currentUrl = url;
            audio.onplay = () => {
                speaking.value = true;
                lastEngine.value = 'piper';
            };
            audio.onended = () => {
                speaking.value = false;
                releaseBusy(token);
                if (currentAudio === audio) stopAudio();
            };
            audio.onpause = () => { speaking.value = false; };
            audio.onerror = () => { speaking.value = false; releaseBusy(token); };
            // Wait for the decoder before starting. There is already an `await`
            // (the synth fetch) between the user's gesture and this point, so
            // this adds no new iOS gesture-credit exposure — that is what the
            // silent-WAV primer above exists for.
            await whenPlayable(audio);
            if (token !== seq) return true; // superseded while decoding
            await audio.play();
            return true;
        } catch {
            return false;
        }
    }

    function speak(text: string) {
        const trimmed = text.trim();
        if (!trimmed) return;
        cancel(); // bumps seq, stops any audio + synthesis
        const token = seq;
        busy.value = true;
        const user = authStore.currentUser;
        const chosen = user?.voice_engine ?? 'piper';
        const voiceId = user?.voice_id ?? 'amy';
        // A user who picked the device voice on a browser that has none gets
        // Piper instead of silence. The reverse already existed (Piper failing
        // falls back to the browser); this closes the other direction, which is
        // the one Firefox lands in.
        const engine = chosen === 'browser' && !browserVoiceUsable.value && piperConfigured.value
            ? 'piper'
            : chosen;
        if (engine === 'piper') {
            void playPiper(trimmed, voiceId, token).then((handled) => {
                // Only fall back if Piper failed AND we're still the current
                // utterance (a newer speak()/cancel() would have bumped seq).
                if (!handled && token === seq) speakBrowser(trimmed, token);
                // Superseded-while-decoding returns `handled` with nothing
                // playing, so `busy` would otherwise never clear. The newer
                // utterance owns `seq`, so this is a no-op in that case.
                else if (handled && !speaking.value && token === seq) {
                    releaseBusy(token);
                }
            });
            return;
        }
        speakBrowser(trimmed, token);
    }

    function cancel() {
        seq += 1;
        stopAudio();
        if (browserApiPresent) window.speechSynthesis.cancel();
        speaking.value = false;
        busy.value = false;
    }

    // Stop talking when the component using us tears down — a Dora chat that
    // closes mid-reply should not keep narrating into an empty page.
    onBeforeUnmount(() => {
        cancel();
    });

    return {
        available,
        /** Whether the *device/browser* voice can actually produce sound here.
         *  Settings reads this to explain a browser that exposes the API but
         *  has no voices installed, rather than offering a dead choice. */
        browserVoiceUsable,
        /** Whether Dora's own neural engine is configured server-side. */
        piperConfigured,
        speaking,
        busy,
        lastEngine,
        speak,
        cancel,
    };
}
