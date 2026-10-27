import AxiosHttpClient from './axiosHttpClient';

/** The chunked-upload staging area (`/api/data/uploads/*`). Through the
 *  client, so the CSRF header, request id and timeout policy apply — the
 *  composable used to hand-roll each call (FU-571 / FU-716, finalisation
 *  18-R7). */
export default class UploadsApiService {
    private httpClient = new AxiosHttpClient();

    startAsync = async (expectedSize: number): Promise<{ upload_id: string; chunk_size: number }> =>
        await this.httpClient.post<{ upload_id: string; chunk_size: number }, { expected_size: number }>(
            '/data/uploads/start', { expected_size: expectedSize },
        );

    chunkAsync = async (uploadId: string, offset: number, chunk: Blob): Promise<void> => {
        const form = new FormData();
        form.append('upload_id', uploadId);
        form.append('offset', String(offset));
        form.append('chunk', chunk);
        await this.httpClient.post<unknown, FormData>('/data/uploads/chunk', form);
    };

    finishAsync = async (uploadId: string): Promise<void> => {
        await this.httpClient.post<unknown, { upload_id: string }>('/data/uploads/finish', { upload_id: uploadId });
    };

    abortAsync = async (uploadId: string): Promise<void> => {
        await this.httpClient.delete<void>(`/data/uploads/${encodeURIComponent(uploadId)}`);
    };
}
