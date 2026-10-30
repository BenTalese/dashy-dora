import { ref } from 'vue';
import AuthApiService from 'src/services/api/authApiService';

// Demo / sellable-showcase mode (FU-392). Surfaced to the client via the
// pre-auth `demo_mode` flag on GET /api/auth/capabilities. When on, the SPA
// renders a persistent "this is a demo, it resets periodically" banner. The
// flag is an operator/deployment decision (env `DORA_DEMO_MODE`), never an
// in-app setting, so it's stable for the whole session.
//
// Module-level so the capabilities probe runs once per backend address and
// every caller shares the same reactive answer.
const enabled = ref(false);
const loaded = ref(false);
let inflight: Promise<void> | null = null;
// R-101 — the address can change while a probe is in flight; only the latest
// request may write the shared answer, so a late reply from the old server
// can't overwrite the new one.
let requestToken = 0;

function load(): Promise<void> {
    if (!inflight) {
        const token = ++requestToken;
        inflight = new AuthApiService()
            .getCapabilitiesAsync()
            .then((caps) => {
                if (token === requestToken) enabled.value = caps.demoMode;
            })
            .catch(() => {
                // Probe failure → assume not a demo (hide the banner).
                if (token === requestToken) enabled.value = false;
            })
            .finally(() => {
                if (token === requestToken) loaded.value = true;
            });
    }
    return inflight;
}

/** Ask the (new) backend again — called when the backend address changes,
 *  since the session-wide answer came from the old one. */
export function refreshDemoMode(): Promise<void> {
    inflight = null;
    return load();
}

export function useDemoMode() {
    void load();
    return { demoMode: enabled, demoModeLoaded: loaded };
}
