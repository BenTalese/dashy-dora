import type { Store } from 'src/models/store';
import type { CreatedResponse } from './axiosHttpClient';
import AxiosHttpClient from './axiosHttpClient';
import { createQueryString, fetchAllPages, type Page } from './queryStringBuilder';

/** FU-189 — client for `/api/stores` (CRUD + image upload). Zero pre-seeded
 *  stores ship; users curate the list themselves. */
export default class StoresApiService {
    private httpClient = new AxiosHttpClient();

    listAsync = async (pagination?: { page: number; limit: number }): Promise<Page<Store>> =>
        await this.httpClient.get<Page<Store>>(`/stores${createQueryString(undefined, undefined, pagination)}`);

    /** Every store: the pickers hold the whole list, so a store past the
     *  server's default page would otherwise be missing from them. */
    listAllAsync = async (): Promise<Store[]> =>
        await fetchAllPages((page, limit) => this.listAsync({ page, limit }));

    createAsync = async (cmd: CreateStoreCommand): Promise<CreatedResponse> =>
        await this.httpClient.post<CreatedResponse>('/stores', cmd);

    updateAsync = async (cmd: UpdateStoreCommand): Promise<void> => {
        const { store_id, ...payload } = cmd;
        await this.httpClient.patch<void>(`/stores/${store_id}`, payload);
    };

    deleteAsync = async (
        storeId: string,
    ): Promise<{ items_affected: number; lines_affected: number }> =>
        await this.httpClient.delete<{
            items_affected: number;
            lines_affected: number;
        }>(`/stores/${storeId}`);
}

export type CreateStoreCommand = {
    name: string;
    /** Optional `data:image/...;base64,...` data-URL. */
    image?: string | null;
};

export type UpdateStoreCommand = {
    store_id: string;
    name?: string;
    image?: string | null;
    clear_image?: boolean;
};
