import { onBeforeUnmount } from 'vue';
import type { ComputedRef, Ref } from 'vue';
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router';
import { useConfirm } from 'src/composables/useConfirm';

// Module-level bypass: when true, every mounted guard silently allows
// navigation and the beforeunload handler is a no-op. Sign-out flips this
// on so the user isn't asked to "discard unsaved changes" on a nav they
// explicitly chose — and, more importantly, so drafts that go stale the
// moment `currentUser` clears (e.g. AccountSettings' username/email drafts
// diffed against a now-null user) don't produce a false-positive prompt
// that, on Cancel, would strand the app on a settings page while
// logged-out.
let bypass = false;
export function suppressUnsavedChangesGuard<T>(fn: () => T | Promise<T>): Promise<T> {
    bypass = true;
    return Promise.resolve()
        .then(fn)
        .finally(() => { bypass = false; });
}

/**
 * FU-156 — prompt "Discard unsaved changes?" whenever the user tries
 * to navigate away from the current page while `isDirty` is true.
 *
 * Covers every nav surface at once (so a new nav route — sidebar link,
 * router-link, `router.push`, browser back, browser refresh/close —
 * doesn't silently bypass the guard):
 * - Intra-app navigation goes through Vue Router → `onBeforeRouteLeave`
 *   intercepts and awaits a Quasar confirm dialog.
 * - Browser refresh / close / address-bar nav fires `beforeunload` →
 *   the native browser prompt fires while `isDirty` is true.
 *
 * Wire once at the top of `<script setup>`:
 *     useUnsavedChangesGuard(isDirty)
 *
 * The save path doesn't need any special handling — just flip
 * `isDirty` to false before / on successful save (as the pages already
 * do), and the next nav will pass straight through.
 */
export function useUnsavedChangesGuard(
    isDirty: Ref<boolean> | ComputedRef<boolean>,
): void {
    const { confirm } = useConfirm();

    const confirmDiscard = (): Promise<boolean> =>
        confirm({
            title: 'Discard unsaved changes?',
            message: 'Your edits will be lost.',
            okLabel: 'Discard',
            destructive: true,
        });

    onBeforeRouteLeave(async () => bypass || !isDirty.value ? true : await confirmDiscard());
    // Catches same-component param changes (e.g. clicking a related
    // recipe while editing the current one — both routes match the
    // same `/cookbook/:id` component, so `onBeforeRouteLeave` doesn't
    // fire; `onBeforeRouteUpdate` does).
    onBeforeRouteUpdate(async () => bypass || !isDirty.value ? true : await confirmDiscard());

    // Browser-level guard for refresh / close / address-bar nav. The
    // dialog text is ignored on modern browsers — setting `returnValue`
    // is what causes the native "Leave site?" prompt to fire.
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
        if (bypass || !isDirty.value) return;
        event.preventDefault();
        event.returnValue = '';
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    onBeforeUnmount(() => {
        window.removeEventListener('beforeunload', onBeforeUnload);
    });
}
