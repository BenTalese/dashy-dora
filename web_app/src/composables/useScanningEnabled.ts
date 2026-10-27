import { ref } from 'vue';
import HealthApiService, { invalidateHealthInfo } from 'src/services/api/healthApiService';

// Scanning + QR labels are one opt-in surface gated by the install-wide
// `scanning_enabled` AppSetting, surfaced to the client as the `scanning`
// flag on GET /api/health. Off by default.
//
// Module-level so the health probe runs once per session and every caller
// shares the same reactive answer.
const enabled = ref(false);
const loaded = ref(false);
let inflight: Promise<void> | null = null;

function load(): Promise<void> {
    if (!inflight) {
        inflight = new HealthApiService()
            .getInfoAsync()
            .then((info) => {
                enabled.value = !!info.features.scanning;
            })
            .catch(() => {
                // Network/probe failure → keep the surface hidden. An admin
                // who has enabled it can retry by reloading.
                enabled.value = false;
            })
            .finally(() => {
                loaded.value = true;
            });
    }
    return inflight;
}

export function useScanningEnabled() {
    void load();
    function refresh(): Promise<void> {
        loaded.value = false;
        inflight = null;
        invalidateHealthInfo();
        return load();
    }
    return { scanningEnabled: enabled, scanningLoaded: loaded, refreshScanning: refresh };
}
