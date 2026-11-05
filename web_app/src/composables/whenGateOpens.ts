import { watch } from 'vue';

/**
 * Re-run a gated loader when its gate opens after mount (FU-586, FU-844).
 *
 * The money / products gates read the once-per-document `/api/health` probe,
 * so on a cold load a false gate usually means "not known yet", not "off": a
 * loader that early-returned on it would leave its card on the empty state for
 * good. A page loads normally at mount and calls this for each gated loader;
 * on a warm navigation the gate is already open and this never fires.
 */
export function whenGateOpens(gate: () => boolean, load: () => unknown): void {
    watch(gate, (open) => {
        if (open) void load();
    });
}
