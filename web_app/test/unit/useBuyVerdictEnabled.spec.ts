// @vitest-environment jsdom
/**
 * Money is a **prerequisite** for the buy-verdict surface, not a co-equal
 * toggle (owner call 2026-08-27). The verdict reasons in money end-to-end —
 * the price axis is money, `wait` is only reachable from a price signal, and
 * price modulates strength — so with money off there is no honest verdict,
 * only need + waste, which PantryBeliefCard already says.
 *
 * Pinned here because it is exactly the kind of gate a later refactor undoes
 * by accident: both inputs are booleans from unrelated composables, and the
 * failure mode (dollar prose on a money-off install) is invisible to anyone
 * developing with money on.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type * as ModuleUnderTest from 'src/composables/useBuyVerdictEnabled';
import { ref, type Ref } from 'vue';

let money: Ref<boolean>;
vi.mock('src/composables/useMoneyEnabled', () => ({
    useMoneyEnabled: () => ({ moneyEnabled: money, installEnabled: money }),
}));

let user: Ref<{ buy_verdict_enabled: boolean } | null>;
vi.mock('src/stores/authStore', () => ({ useAuthStore: () => ({}) }));
vi.mock('pinia', () => ({ storeToRefs: () => ({ currentUser: user }) }));

type Mod = typeof ModuleUnderTest;

async function load(): Promise<Mod> {
    vi.resetModules();
    return await import('src/composables/useBuyVerdictEnabled');
}

describe('useBuyVerdictEnabled', () => {
    beforeEach(() => {
        money = ref(true);
        user = ref({ buy_verdict_enabled: true });
    });

    it('is on when the install has money and the user has not opted out', async () => {
        const { useBuyVerdictEnabled } = await load();
        expect(useBuyVerdictEnabled().buyVerdictEnabled.value).toBe(true);
    });

    it('is off when money is off, even though the user opted in', async () => {
        money.value = false;
        const { useBuyVerdictEnabled } = await load();
        expect(useBuyVerdictEnabled().buyVerdictEnabled.value).toBe(false);
    });

    it('is off when the user opted out, even though money is on', async () => {
        user.value = { buy_verdict_enabled: false };
        const { useBuyVerdictEnabled } = await load();
        expect(useBuyVerdictEnabled().buyVerdictEnabled.value).toBe(false);
    });

    it('does not default the user half on into a money-off install', async () => {
        // The per-user half defaults true while `/auth/me` is in flight, so
        // that default must not be able to switch the surface on by itself.
        money.value = false;
        user.value = null;
        const { useBuyVerdictEnabled } = await load();
        expect(useBuyVerdictEnabled().buyVerdictEnabled.value).toBe(false);
    });

    it('reacts to money being turned off mid-session', async () => {
        const { useBuyVerdictEnabled } = await load();
        const { buyVerdictEnabled } = useBuyVerdictEnabled();
        expect(buyVerdictEnabled.value).toBe(true);
        money.value = false;
        expect(buyVerdictEnabled.value).toBe(false);
    });
});
