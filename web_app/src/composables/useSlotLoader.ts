/**
 * Per-card failure for a page of independently loaded cards. Each
 * card's fetch runs through `loadSlot(id, run)`: it never throws, so one bad
 * card cannot take the page down, and a failure is recorded against the id so
 * the card renders `CardLoadError` instead of its empty state. A later retry
 * that succeeds clears the flag, so the card recovers without a reload.
 *
 * One id-keyed set rather than an `error` ref per card: the cards ask "did
 * *this* slot fail" and a banner asks "did *anything* fail", and one structure
 * answers both (R-003).
 */
import { shallowRef } from 'vue';

export function useSlotLoader<Id extends string>(options: {
    /** Names the page in the console warning, e.g. "dashboard slot". */
    label: string;
    /** Per-slot in-flight flags, set for the duration of each run. */
    loading?: Partial<Record<Id, boolean>>;
}) {
    // Replaced, never mutated, so a shallow ref is enough to trigger.
    const slotErrors = shallowRef(new Set<Id>());

    function slotFailed(id: Id): boolean {
        return slotErrors.value.has(id);
    }

    function setFailed(id: Id, failed: boolean): void {
        if (slotErrors.value.has(id) === failed) return;
        const next = new Set(slotErrors.value);
        if (failed) next.add(id);
        else next.delete(id);
        slotErrors.value = next;
    }

    async function loadSlot(id: Id, run: () => Promise<void>): Promise<void> {
        if (options.loading) options.loading[id] = true;
        try {
            await run();
            setFailed(id, false);
        } catch (err) {
            // Logged, not swallowed: the console is how a self-hosting owner
            // finds out which endpoint is unhappy.
            console.warn(`${options.label} "${id}" failed to load`, err);
            setFailed(id, true);
        } finally {
            if (options.loading) options.loading[id] = false;
        }
    }

    return { slotFailed, loadSlot };
}
