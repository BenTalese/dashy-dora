import AxiosHttpClient from './axiosHttpClient';

/** Server speech-to-text (FU-788), the fallback for browsers with no Web
 *  Speech API. `unavailable` = the engine isn't installed on this server;
 *  `downloadable` = installed, model not fetched yet; `ready` = usable. */
export type SttStatus = 'unavailable' | 'downloadable' | 'downloading' | 'ready' | 'error';

export type SttStatusResponse = {
    status: SttStatus;
    model_size_bytes: number;
    error: string | null;
};

export default class SttApiService {
    private httpClient = new AxiosHttpClient();

    getStatusAsync = async (): Promise<SttStatusResponse> =>
        await this.httpClient.get<SttStatusResponse>('/stt');

    downloadAsync = async (): Promise<{ status: SttStatus }> =>
        await this.httpClient.post<{ status: SttStatus }>('/stt/download', {});

    /** One recorded clip → its text. */
    transcribeAsync = async (clip: Blob): Promise<string> => {
        const form = new FormData();
        form.append('audio', clip, 'clip.webm');
        const res = await this.httpClient.post<{ text: string }, FormData>(
            '/stt/transcribe', form, { timeoutMs: 60_000 },
        );
        return res.text;
    };
}
