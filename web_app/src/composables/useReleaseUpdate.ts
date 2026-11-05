/**
 * "Is there a newer Dora release than this server runs?" (FU-626).
 *
 * One fetch of `/api/help/version` per page load, shared by every reader (the
 * header's account button and the Settings notice), so neither asks twice.
 * The server owns the comparison and the GitHub call; a failed or disabled
 * check reads as "no update", never as an error.
 */
import { computed, ref } from 'vue';
import HelpApiService, { type VersionInfo } from 'src/services/api/helpApiService';

const info = ref<VersionInfo | null>(null);
let pending: Promise<void> | null = null;

async function ensureReleaseInfo(): Promise<void> {
    if (info.value || pending) return pending ?? undefined;
    pending = new HelpApiService().getVersionAsync()
        .then((v) => { info.value = v; })
        .catch(() => { /* a courtesy check; silence is the right failure */ })
        .finally(() => { pending = null; });
    return pending;
}

export function useReleaseUpdate() {
    const available = computed(() => info.value?.update_available === true);
    return { info, available, ensureReleaseInfo };
}
