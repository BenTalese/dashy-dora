import type { StockLevel } from 'src/models/stockLevel';
import AxiosHttpClient from './axiosHttpClient';
import { fetchAllPages, type Page } from './queryStringBuilder';

export default class StockLevelApiService {
    private httpClient: AxiosHttpClient;

    constructor() {
        this.httpClient = new AxiosHttpClient();
    }

    getAllAsync = async (
        pagination: { page: number; limit: number } = { page: 1, limit: 50 },
    ): Promise<Page<StockLevel>> =>
        await this.httpClient.get<Page<StockLevel>>(
            `/stock-levels?page=${pagination.page}&limit=${pagination.limit}`,
        );

    /** Every level, not the first page (FU-668: the only paged endpoint a
     *  store hydrated from page one). */
    getAllPagesAsync = async (): Promise<StockLevel[]> =>
        await fetchAllPages((page, limit) => this.getAllAsync({ page, limit }));
}
