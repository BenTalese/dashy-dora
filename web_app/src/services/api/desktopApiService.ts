import AxiosHttpClient from './axiosHttpClient';

/** The desktop app only (`desktop_app.py`); a server install answers 404. */
export default class DesktopApiService {
    private httpClient = new AxiosHttpClient();

    quitAsync = async (): Promise<void> =>
        await this.httpClient.post<void, Record<string, never>>('/desktop/quit', {});
}
