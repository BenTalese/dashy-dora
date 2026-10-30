import AxiosHttpClient, { type CreatedResponse } from './axiosHttpClient';
import { createQueryString, fetchAllPages, type Page } from './queryStringBuilder';

export type StockLocation = {
    name: string;
    stock_location_id: string;
};

export type CreateStockLocationCommand = { name: string };
export type UpdateStockLocationCommand = { stock_location_id: string; name: string };

export default class StockLocationApiService {
    private httpClient: AxiosHttpClient;

    constructor() {
        this.httpClient = new AxiosHttpClient();
    }

    getAllAsync = async (
        pagination?: { page: number; limit: number },
    ): Promise<Page<StockLocation>> =>
        await this.httpClient.get<Page<StockLocation>>(
            `/stock-locations${createQueryString(undefined, undefined, pagination)}`,
        );

    /** Every location: the store is the whole tree, not its first page. */
    getAllPagesAsync = async (): Promise<StockLocation[]> =>
        await fetchAllPages((page, limit) => this.getAllAsync({ page, limit }));

    createAsync = async (command: CreateStockLocationCommand): Promise<CreatedResponse> =>
        await this.httpClient.post<CreatedResponse>('/stock-locations', command);

    updateAsync = async (command: UpdateStockLocationCommand): Promise<void> => {
        const { stock_location_id, ...payload } = command;
        await this.httpClient.patch<void>(`/stock-locations/${stock_location_id}`, payload);
    };

    deleteAsync = async (stockLocationId: string): Promise<void> =>
        await this.httpClient.delete<void>(`/stock-locations/${stockLocationId}`);
}
