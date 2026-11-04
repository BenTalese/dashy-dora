/**
 * Cook mode's voice layer (FU-942, split out of `RecipeCookMode.vue`): the
 * Sous Chef narration toggle, the hands-free mic and the spoken-command
 * dispatcher. The transcript → command mapping is pure and exported
 * (`parseCookVoiceCommand`) so the owner-specified semantics — "stop"
 * precedence, "exit" vs "stop", the timer verbs, ignored noise — can be
 * pinned by a spec (`test/unit/cookVoiceCommands.spec.ts`).
 *
 * Everything a command *does* is the page's (step navigation, the timer,
 * leaving); this composable only decides which of those a transcript asked
 * for and owns the speech engines both directions.
 */
import { useQuasar } from 'quasar';
import { computed, ref, watch, type Ref } from 'vue';

// extracted browser-speech composables. Cook mode opts into
// continuous listening so the user can keep their hands in the
// mixing bowl while saying "next" / "start timer".
import { useSpeechOutput } from 'src/composables/useSpeechOutput';
import { useVoiceInput } from 'src/composables/useVoiceInput';
import { useAuthStore } from 'src/stores/authStore';
import { ICONS } from 'src/style/icons';

export type CookVoiceCommand =
    | 'next'
    | 'previous'
    | 'repeat'
    | 'ingredients'
    | 'tools'
    | 'startTimer'
    | 'pauseTimer'
    | 'resetTimer'
    | 'exit'
    | 'stop';

// Sous Chef voice command list, surfaced via the help
// popover so users discover the verbs without trial and error.
export const SOUS_CHEF_COMMANDS: ReadonlyArray<{ label: string; does: string }> = [
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

/** Map a finalised utterance onto a cook-mode command, or null for anything
 *  else. Order matters: the first matching branch wins, so "stop timer" is
 *  the timer verb, not the bare "stop", and "exit" is checked before "stop".
 *
 *  Unrecognised commands are deliberately ignored — silence is
 *  less annoying than a "I didn't understand that" interjection
 *  every time the user talks to someone else in the kitchen. */
export function parseCookVoiceCommand(rawTranscript: string): CookVoiceCommand | null {
    const transcript = rawTranscript.toLowerCase();
    if (/(^|\s)(next|forward|continue)(\s|$)/.test(transcript)) return 'next';
    if (/(^|\s)(previous|back|go back)(\s|$)/.test(transcript)) return 'previous';
    if (/(^|\s)(repeat|again|say it again)(\s|$)/.test(transcript)) return 'repeat';
    if (/(^|\s)(ingredients?|what do i need)(\s|$)/.test(transcript)) return 'ingredients';
    if (/(^|\s)(tools?|equipment|what tools)(\s|$)/.test(transcript)) return 'tools';
    if (/(^|\s)(start timer|begin timer|set timer)(\s|$)/.test(transcript)) return 'startTimer';
    if (/(^|\s)(pause timer|stop timer)(\s|$)/.test(transcript)) return 'pauseTimer';
    if (/(^|\s)(reset timer|clear timer)(\s|$)/.test(transcript)) return 'resetTimer';
    if (/(^|\s)(exit|quit)(\s|$)/.test(transcript)) return 'exit';
    if (/(^|\s)(stop|quiet|hush|shush|be quiet)(\s|$)/.test(transcript)) return 'stop';
    return null;
}

/** What a voice command can ask the page to do. Each one mirrors a visible
 *  button — we deliberately don't expose voice-only side effects, so the user
 *  can always verify what we think they said by spotting the corresponding
 *  click. The two `*Answer` callbacks return the sentence to say. */
export type CookVoiceActions = {
    next: () => void;
    previous: () => void;
    startTimer: (seconds: number) => void;
    pauseTimer: () => void;
    resetTimer: () => void;
    exit: () => void;
    ingredientsAnswer: () => string;
    toolsAnswer: () => string;
};

export function useCookVoice(options: {
    currentStep: Ref<string>;
    currentStepIndex: Ref<number>;
    steps: Ref<string[]>;
    /** False while the recipe is loading, when `steps` is only the
     *  "No instructions provided." placeholder (FU-982). */
    ready: Ref<boolean>;
    stepTimerMinutes: Ref<number | null>;
    timerRunning: Ref<boolean>;
    actions: CookVoiceActions;
}) {
    const $q = useQuasar();
    const authStore = useAuthStore();
    const { currentStep, currentStepIndex, steps, ready, stepTimerMinutes, timerRunning, actions } = options;

    // ── P2-13 voice (extracted into composables) ────────────────────────
    // The user's persisted preference seeds the local toggle; subsequent
    // in-page taps flip the session view and persist back via authStore.
    const speechOut = useSpeechOutput();
    const speechEnabled = ref<boolean>(
        authStore.currentUser?.voice_output_enabled ?? false,
    );

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

    function speak(text: string) {
        if (!speechEnabled.value) return;
        speechOut.speak(text);
    }

    function speakCurrent() {
        speak(currentStep.value);
    }

    function cancelSpeech() {
        speechOut.cancel();
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

    // ── P2-13 voice command dispatcher ──────────────────────────────────
    // Called by `useVoiceInput.onFinal` whenever the browser hands us a
    // finalised utterance.
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
            actions.pauseTimer();
        }
        // Nothing talking and no timer running — nothing to stop, and
        // silence is the right answer (see `parseCookVoiceCommand`).
    }

    function handleVoiceCommand(rawTranscript: string) {
        switch (parseCookVoiceCommand(rawTranscript)) {
            case 'next':
                actions.next();
                break;
            case 'previous':
                actions.previous();
                break;
            case 'repeat':
                speakCurrent();
                break;
            case 'ingredients':
                speakAnswer(actions.ingredientsAnswer());
                break;
            case 'tools':
                speakAnswer(actions.toolsAnswer());
                break;
            case 'startTimer': {
                // "start timer" → use whatever duration the current step
                // implies; fall back to 5 minutes when nothing's detectable.
                const minutes = stepTimerMinutes.value ?? 5;
                actions.startTimer(minutes * 60);
                if (speechEnabled.value) speak(`Timer set for ${minutes} minutes.`);
                break;
            }
            case 'pauseTimer':
                actions.pauseTimer();
                if (speechEnabled.value) speak('Timer paused.');
                break;
            case 'resetTimer':
                actions.resetTimer();
                if (speechEnabled.value) speak('Timer reset.');
                break;
            case 'exit':
                actions.exit();
                break;
            case 'stop':
                handleStopCommand();
                break;
            case null:
                break;
        }
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
    watch([steps, ready], ([next, isReady]) => {
        if (announcedFirstStep || !isReady || next.length === 0) return;
        announcedFirstStep = true;
        if (speechEnabled.value && currentStepIndex.value === 0) speakCurrent();
    }, { immediate: true });

    /** A freshly loaded recipe is a new cook: its first step gets announced
     *  again (FU-765). */
    function rearmFirstStepAnnouncement() {
        announcedFirstStep = false;
    }

    return {
        speechEnabled,
        listening,
        speechRecognitionAvailable,
        speak,
        speakCurrent,
        cancelSpeech,
        toggleSpeech,
        stopListening,
        toggleListening,
        rearmFirstStepAnnouncement,
        handleVoiceCommand,
    };
}
