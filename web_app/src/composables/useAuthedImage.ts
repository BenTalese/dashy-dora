import { onBeforeUnmount, ref, watch, type Ref } from 'vue';
import AxiosHttpClient from 'src/services/api/axiosHttpClient';

const http = new AxiosHttpClient();

/**
 * An API image as an object URL, fetched through the HTTP client (R-045).
 *
 * A bare `<img :src="…/api/…/image">` is unauthenticated by construction: it
 * carries the session cookie only when the browser volunteers it, which fails
 * on a split `app.`/`api.` host and in the Capacitor shell, and the failure is
 * a silent broken image. Fetching the bytes through `AxiosHttpClient` (which
 * the interceptor authenticates) and handing the `<img>` an object URL works on
 * every deployment.
 *
 * `path` returns the API path to load, or null for "no image" (the caller's
 * fallback is then the correct render, not a failure). A failed fetch also
 * yields null. The object URL lives until the path changes or the component
 * unmounts, so a long-lived avatar never points at a revoked URL.
 */
export function useAuthedImage(path: () => string | null): Ref<string | null> {
    const src = ref<string | null>(null);
    // The path whose fetch is in flight, so a row recycled onto a different
    // record can't paint the previous record's image when a slower response lands.
    let inFlightFor: string | null = null;

    function release(): void {
        if (src.value) URL.revokeObjectURL(src.value);
        src.value = null;
    }

    async function load(target: string | null): Promise<void> {
        release();
        inFlightFor = target;
        if (!target) return;
        try {
            const blob = await http.getBlob(target);
            if (inFlightFor !== target) return;
            // A→B→A in quick succession leaves two fetches for A that both
            // pass the check above; the second must not orphan the first's URL.
            release();
            src.value = URL.createObjectURL(blob);
        } catch {
            // A missing image is not worth a toast; the caller's fallback shows.
        }
    }

    watch(path, (target) => void load(target), { immediate: true });

    onBeforeUnmount(() => {
        inFlightFor = null;
        release();
    });

    return src;
}
