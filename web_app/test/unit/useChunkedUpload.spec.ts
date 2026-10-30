// @vitest-environment jsdom
// A chunk that lands after the client timed out is retried at the same
// offset; the server answers 400 with the bytes it holds. That reply means
// "done" (or "resume from here"), not a failed upload.
import { beforeEach, describe, expect, it, vi } from 'vitest';

const calls: number[] = [];
const chunkAsync = vi.fn();

vi.mock('src/services/api/uploadsApiService', () => ({
    default: class {
        startAsync = () => Promise.resolve({ upload_id: 'u1', chunk_size: 4 });
        chunkAsync = (_id: string, offset: number, chunk: Blob) => {
            calls.push(offset);
            return chunkAsync(offset, chunk);
        };
        finishAsync = () => Promise.resolve();
        abortAsync = () => Promise.resolve();
    },
}));

import { NormalisedApiError } from 'src/services/api/axiosHttpClient';
import { useChunkedUpload } from 'src/composables/useChunkedUpload';

function offsetMismatch(received: number): NormalisedApiError {
    return new NormalisedApiError({
        status: 400,
        code: 'bad_request',
        message: 'offset mismatch',
        details: { errors: { received: [{ msg: String(received) }] } },
        correlationId: 'c1',
        isNetworkError: false,
        method: 'POST',
        url: '/data/uploads/chunk',
    });
}

beforeEach(() => {
    calls.length = 0;
    chunkAsync.mockReset();
});

describe('useChunkedUpload', () => {
    it('treats a retried chunk the server already holds as sent', async () => {
        chunkAsync
            .mockRejectedValueOnce(new Error('timeout'))
            .mockRejectedValueOnce(offsetMismatch(4))
            .mockResolvedValue(undefined);
        const { upload, progress } = useChunkedUpload();

        await upload(new File(['abcdefgh'], 'f.bin'), { chunkSize: 4 });

        expect(calls).toEqual([0, 0, 4]);
        expect(progress.value).toBe(1);
    });

    it('resumes from the server offset when only part of the file landed', async () => {
        chunkAsync
            .mockRejectedValueOnce(offsetMismatch(2))
            .mockResolvedValue(undefined);
        const { upload } = useChunkedUpload();

        await upload(new File(['abcdefgh'], 'f.bin'), { chunkSize: 4 });

        expect(calls).toEqual([0, 2, 6]);
    });

    it('fails when the server holds more than this chunk would explain', async () => {
        chunkAsync.mockRejectedValueOnce(offsetMismatch(99));
        const { upload } = useChunkedUpload();

        await expect(upload(new File(['abcdefgh'], 'f.bin'), { chunkSize: 4 })).rejects.toThrow(/offset mismatch/);
    });
});
