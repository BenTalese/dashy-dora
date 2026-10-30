/**
 * Stage a file to /api/data/uploads/* in 8 MB chunks with per-chunk retry.
 * Returns the upload_id and exposes a reactive progress (0..1) so callers
 * can render a progress bar without wiring their own state.
 *
 * Used by both BackupRestore and DataImport — both flows upload once and
 * then reference the staged file via upload_id in subsequent inspect /
 * commit calls. Calls go through `UploadsApiService` (finalisation 18-R7:
 * they were raw `fetch`es with their own CSRF header and error reader);
 * `inFlight` / `lastUploadId` were dropped — neither page read them
 * (18-R17).
 */
import { ref } from 'vue';
import UploadsApiService from 'src/services/api/uploadsApiService';
import { NormalisedApiError } from 'src/services/api/axiosHttpClient';

// Defaults match the server-side constants in
// dora_api/features/data/uploads.py — overrideable per-call.
const DEFAULT_CHUNK_BYTES = 8 * 1024 * 1024;
const DEFAULT_MAX_ATTEMPTS = 3;

export interface ChunkedUploadOptions {
    chunkSize?: number;
    maxAttempts?: number;
}

const uploads = new UploadsApiService();

export function useChunkedUpload() {
    // 0..1 inclusive. Stays at 0 until the first chunk lands.
    const progress = ref(0);

    async function upload(file: File, options: ChunkedUploadOptions = {}): Promise<string> {
        const chunkSize = options.chunkSize ?? DEFAULT_CHUNK_BYTES;
        const maxAttempts = options.maxAttempts ?? DEFAULT_MAX_ATTEMPTS;

        progress.value = 0;
        const started = await uploads.startAsync(file.size);
        // The server can dictate a larger chunk size than the caller
        // suggested; honour whichever is larger to avoid extra round-trips.
        const effectiveChunkSize = Math.max(started.chunk_size, chunkSize);

        // The server says where the next chunk starts, so a retry that finds
        // the bytes already landed (or only partly landed) carries on from
        // there instead of re-sending from a stale offset.
        let offset = 0;
        while (offset < file.size) {
            const end = Math.min(offset + effectiveChunkSize, file.size);
            offset = await uploadChunkWithRetry(started.upload_id, offset, file.slice(offset, end), maxAttempts);
            progress.value = offset / file.size;
        }

        await uploads.finishAsync(started.upload_id);
        return started.upload_id;
    }

    /** Best-effort abort. Safe to call with a stale id (the server returns
     *  204 either way). */
    async function abort(uploadId: string | null): Promise<void> {
        if (!uploadId) return;
        try {
            await uploads.abortAsync(uploadId);
        } catch {
            // Ignored — TTL sweep will catch it eventually.
        }
    }

    function reset() {
        progress.value = 0;
    }

    return { progress, upload, abort, reset };
}

/** Send one chunk; resolves with the offset the next chunk starts at. */
async function uploadChunkWithRetry(
    id: string,
    offset: number,
    chunk: Blob,
    maxAttempts: number,
): Promise<number> {
    const chunkEnd = offset + chunk.size;
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        try {
            await uploads.chunkAsync(id, offset, chunk);
            return chunkEnd;
        } catch (err) {
            // The server rejects an offset that isn't its staged size and says
            // how many bytes it holds. A retry of a chunk that landed after the
            // client timed out reads exactly `chunkEnd` — that chunk is done.
            // Fewer bytes means resume from there. Anything else is out of
            // sync for real, so the user restarts rather than hammering it.
            if (err instanceof NormalisedApiError && err.status === 400) {
                const errors = err.details?.errors as Record<string, { msg?: string }[]> | undefined;
                const mismatch = errors?.received?.[0]?.msg;
                if (mismatch) {
                    const received = Number(mismatch);
                    if (Number.isInteger(received) && received >= 0 && received <= chunkEnd) return received;
                    throw new Error(`Chunk offset mismatch (server has ${mismatch} bytes). Retry the upload.`);
                }
            }
            if (attempt >= maxAttempts) throw err;
            await new Promise((resolve) => setTimeout(resolve, 250 * attempt));
        }
    }
    // Unreachable: the last attempt either returns or throws.
    throw new Error('Chunk upload failed.');
}
