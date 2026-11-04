/**
 * Per-character reveal for a chat reply, so the talking face has something to
 * sync against (finalisation 11-R30, split out of DoraChat.vue). 22ms/char
 * feels fluid; very long replies speed up so the full text lands within ~3s.
 * Talking stays on for TALK_TAIL_MS after the last char so the lip-flap shows
 * even on short replies.
 */
const TYPE_CHAR_MS = 22;
const TYPE_MAX_TOTAL_MS = 3000;
const TALK_TAIL_MS = 600;

export type TypewriterTarget = { text: string; displayText?: string };

export function useTypewriter(options: {
    onTalking: (talking: boolean) => void;
    /** Called every few characters and at the end, e.g. to keep the newest
     *  line in view. */
    onProgress: () => void;
}) {
    let active: { cancel: () => void } | null = null;

    function start(message: TypewriterTarget) {
        active?.cancel();
        const full = message.text;
        message.displayText = '';
        if (!full) {
            options.onTalking(false);
            return;
        }
        const charMs = Math.max(8, Math.min(TYPE_CHAR_MS, Math.floor(TYPE_MAX_TOTAL_MS / full.length)));
        let i = 0;
        let cancelled = false;
        options.onTalking(true);
        const tick = () => {
            if (cancelled) return;
            i += 1;
            message.displayText = full.slice(0, i);
            if (i % 6 === 0) options.onProgress();
            if (i >= full.length) {
                message.displayText = full;
                options.onProgress();
                setTimeout(() => {
                    if (!cancelled) options.onTalking(false);
                }, TALK_TAIL_MS);
                active = null;
                return;
            }
            timer = setTimeout(tick, charMs);
        };
        let timer = setTimeout(tick, charMs);
        active = {
            cancel: () => {
                cancelled = true;
                clearTimeout(timer);
                message.displayText = full;
                options.onTalking(false);
                active = null;
            },
        };
    }

    /** Finish the reveal in flight, if any, showing its full text. */
    function cancel() {
        active?.cancel();
    }

    return { start, cancel };
}
