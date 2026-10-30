/**
 * The cook-mode step timer (finalisation 04-R8). It counts against a deadline,
 * not by decrementing once per tick: a backgrounded tab throttles intervals
 * (Chrome to one a second and then one a minute, iOS suspends them), so a
 * per-tick countdown ran slow exactly when the cook had switched apps. Each
 * tick, and every return to the tab, recomputes what is left from the clock.
 */
import { computed, onBeforeUnmount, ref } from 'vue';

const TICK_MS = 1000;

export function formatTimer(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

export function useCookTimer(options: { onFinish: () => void }) {
    const remaining = ref<number | null>(null);
    const running = ref(false);
    /** Captured at start so the fill bar keeps a stable denominator through
     *  pause and resume. */
    const total = ref<number | null>(null);
    let deadlineMs: number | null = null;
    let intervalId: ReturnType<typeof setInterval> | null = null;

    const progress = computed<number>(() => {
        if (total.value === null || total.value <= 0) return 0;
        if (remaining.value === null) return 1;
        return Math.max(0, Math.min(1, remaining.value / total.value));
    });

    function stopTicking() {
        if (intervalId) {
            clearInterval(intervalId);
            intervalId = null;
        }
    }

    function sync() {
        if (deadlineMs === null) return;
        remaining.value = Math.max(0, Math.ceil((deadlineMs - Date.now()) / 1000));
        if (remaining.value === 0) {
            pause();
            options.onFinish();
        }
    }

    function onVisibility() {
        if (document.visibilityState === 'visible') sync();
    }

    function start(seconds: number) {
        // A finished timer sits at 0, not null — restarting it is a fresh
        // countdown, not a resume of nothing.
        if (remaining.value === null || remaining.value <= 0) {
            remaining.value = seconds;
            total.value = seconds;
        }
        deadlineMs = Date.now() + remaining.value * 1000;
        running.value = true;
        stopTicking();
        intervalId = setInterval(sync, TICK_MS);
        document.addEventListener('visibilitychange', onVisibility);
    }

    function pause() {
        if (deadlineMs !== null && remaining.value !== null && remaining.value > 0) {
            remaining.value = Math.max(0, Math.ceil((deadlineMs - Date.now()) / 1000));
        }
        deadlineMs = null;
        running.value = false;
        stopTicking();
        document.removeEventListener('visibilitychange', onVisibility);
    }

    function reset() {
        pause();
        remaining.value = null;
        total.value = null;
    }

    onBeforeUnmount(pause);

    return { remaining, running, total, progress, start, pause, reset };
}
