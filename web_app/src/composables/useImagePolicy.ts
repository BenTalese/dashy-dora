import { ref } from 'vue';
import HealthApiService, { invalidateHealthInfo } from 'src/services/api/healthApiService';

// install-wide image compression policy. Every upload site
// funnels through `processImageFile`, which reads these values so
// admins can tune quality / max-dimension in one place and every
// surface (stock items, recipes, products, avatars, receipts, store
// logos) picks it up.
//
// Module-level state so the health probe runs once per session and
// every caller shares the same reactive answer — mirrors
// `useScanningEnabled` / `useFeatureFlags`.
//
// The values are also exported as plain getters so non-Vue callers
// (like `processImageFile`, which is a plain module function) can
// read the current policy without a composable.

export interface ImagePolicy {
    /** JPEG/WebP quality 0..1 fed to canvas.toDataURL. */
    quality: number;
    /** Longest-edge cap in px; images above are scaled down first. */
    maxLongEdge: number;
}

// Conservative defaults matching the backend + the old hard-coded
// constants: quality 85 (visually indistinguishable from "original")
// and 1920px cap (Full-HD's long edge). Kept in one place so the
// null-policy path can't diverge.
const DEFAULTS: ImagePolicy = {
    quality: 0.85,
    maxLongEdge: 1920,
};

const policy = ref<ImagePolicy>({ ...DEFAULTS });
const loaded = ref(false);
let inflight: Promise<void> | null = null;

function load(): Promise<void> {
    if (!inflight) {
        inflight = new HealthApiService()
            .getInfoAsync()
            .then((info) => {
                const server = info.image_policy;
                if (!server) return;
                // Clamp to the same range the backend enforces so a
                // malformed value doesn't blow the canvas encode.
                const q = clamp(server.quality, 30, 100) / 100;
                const dim = clamp(server.max_dimension, 512, 8192);
                policy.value = { quality: q, maxLongEdge: dim };
            })
            .catch(() => {
                // Health probe failure ⇒ keep the defaults. The
                // upload path still works; no user-visible break.
            })
            .finally(() => {
                loaded.value = true;
            });
    }
    return inflight;
}

function clamp(value: number, lo: number, hi: number): number {
    if (!Number.isFinite(value)) return lo;
    return Math.min(hi, Math.max(lo, value));
}

/** Read-only access for `processImageFile` and any other non-Vue
 *  caller that needs the current policy at a given moment. */
export function currentImagePolicy(): ImagePolicy {
    return policy.value;
}

/** Force-reload the policy from the server. The admin UI calls this
 *  after saving a new value so subsequent uploads pick it up without
 *  a full page reload. */
export function refreshImagePolicy(): Promise<void> {
    loaded.value = false;
    inflight = null;
    invalidateHealthInfo();
    return load();
}

export function useImagePolicy() {
    void load();
    return { imagePolicy: policy, imagePolicyLoaded: loaded, refreshImagePolicy };
}
