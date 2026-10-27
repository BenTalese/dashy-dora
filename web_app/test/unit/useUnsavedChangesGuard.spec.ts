// @vitest-environment jsdom
// FU-539 / FU-156 — useUnsavedChangesGuard. Guards every nav surface against
// losing unsaved edits: intra-app nav (onBeforeRouteLeave / onBeforeRouteUpdate
// → confirm dialog) and browser refresh/close (beforeunload → native prompt).
// A guard that fails open silently discards the user's work.
//
// The router guard hooks and Quasar's Dialog plugin (which `useConfirm` wraps)
// are mocked at the module boundary so no real router instance is needed — we
// capture the registered guard callback and invoke it directly with a dirty /
// clean predicate.
import { enableAutoUnmount, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { defineComponent, h, ref } from 'vue';

type Guard = () => boolean | Promise<boolean>;
const g = vi.hoisted(() => ({
    leaveGuard: null as Guard | null,
    updateGuard: null as Guard | null,
    dialog: vi.fn(),
    dialogResult: 'ok' as 'ok' | 'cancel' | 'dismiss',
}));

vi.mock('vue-router', () => ({
    onBeforeRouteLeave: (cb: Guard) => { g.leaveGuard = cb; },
    onBeforeRouteUpdate: (cb: Guard) => { g.updateGuard = cb; },
}));
vi.mock('quasar', () => ({
    Dialog: {
        create: g.dialog.mockImplementation(() => {
            const chain = {
                onOk: (cb: () => void) => { if (g.dialogResult === 'ok') cb(); return chain; },
                onCancel: (cb: () => void) => { if (g.dialogResult === 'cancel') cb(); return chain; },
                onDismiss: (cb: () => void) => { if (g.dialogResult === 'dismiss') cb(); return chain; },
            };
            return chain;
        }),
    },
}));

import { useUnsavedChangesGuard } from 'src/composables/useUnsavedChangesGuard';

function mountWithGuard(isDirty = ref(false)) {
    const Host = defineComponent({
        setup() {
            useUnsavedChangesGuard(isDirty);
            return () => h('div');
        },
    });
    const wrapper = mount(Host);
    return { wrapper, isDirty };
}

// Every mounted host attaches a real beforeunload listener; auto-unmount after
// each test so a dirty host from one test doesn't preventDefault in the next.
enableAutoUnmount(afterEach);

beforeEach(() => {
    g.leaveGuard = null;
    g.updateGuard = null;
    g.dialogResult = 'ok';
    g.dialog.mockClear();
});

describe('useUnsavedChangesGuard — route leave', () => {
    it('registers both onBeforeRouteLeave and onBeforeRouteUpdate', () => {
        mountWithGuard();
        expect(g.leaveGuard).toBeTypeOf('function');
        expect(g.updateGuard).toBeTypeOf('function');
    });

    it('passes straight through (no dialog) when clean', async () => {
        mountWithGuard(ref(false));
        await expect(g.leaveGuard!()).resolves.toBe(true);
        expect(g.dialog).not.toHaveBeenCalled();
    });

    it('prompts when dirty and allows nav when the user confirms discard', async () => {
        mountWithGuard(ref(true));
        g.dialogResult = 'ok';
        await expect(g.leaveGuard!()).resolves.toBe(true);
        expect(g.dialog).toHaveBeenCalledTimes(1);
    });

    it('prompts when dirty and blocks nav when the user cancels', async () => {
        mountWithGuard(ref(true));
        g.dialogResult = 'cancel';
        await expect(g.leaveGuard!()).resolves.toBe(false);
    });

    it('treats a dismissed dialog as "stay" (blocks nav)', async () => {
        mountWithGuard(ref(true));
        g.dialogResult = 'dismiss';
        await expect(g.leaveGuard!()).resolves.toBe(false);
    });

    it('the same-component param-change guard also prompts when dirty', async () => {
        mountWithGuard(ref(true));
        g.dialogResult = 'cancel';
        await expect(g.updateGuard!()).resolves.toBe(false);
        expect(g.dialog).toHaveBeenCalledTimes(1);
    });
});

describe('useUnsavedChangesGuard — beforeunload', () => {
    it('prevents unload while dirty', () => {
        mountWithGuard(ref(true));
        const event = new Event('beforeunload', { cancelable: true });
        window.dispatchEvent(event);
        expect(event.defaultPrevented).toBe(true);
    });

    it('does not prevent unload when clean', () => {
        mountWithGuard(ref(false));
        const event = new Event('beforeunload', { cancelable: true });
        window.dispatchEvent(event);
        expect(event.defaultPrevented).toBe(false);
    });

    it('removes the beforeunload listener on unmount', () => {
        const { wrapper } = mountWithGuard(ref(true));
        wrapper.unmount();
        const event = new Event('beforeunload', { cancelable: true });
        window.dispatchEvent(event);
        expect(event.defaultPrevented).toBe(false);
    });
});
