import type { Product } from 'src/models/product';
import type { CreatedResponse } from './axiosHttpClient';
import AxiosHttpClient from './axiosHttpClient';
import { FilterOperator, SortOrder, createQueryString, fetchAllPages, type Page } from './queryStringBuilder';

export default class ProductApiService {
    private httpClient = new AxiosHttpClient();

    createAsync = async (productToCreate: CreateProductCommand): Promise<CreatedResponse> =>
        await this.httpClient.post<CreatedResponse>('/products', productToCreate);

    /** Every saved product, paged: My products, Price history and the list
     *  page all filter client-side over the store, so one default page of 50
     *  silently hid product 51 onward. */
    getAllPagesAsync = async (): Promise<Product[]> =>
        await fetchAllPages((page, limit) =>
            this.httpClient.get<Page<Product>>(`/products${createQueryString([], undefined, { page, limit })}`),
        );

    /** Name search, resolved server-side.
     *
     *  FU-668 — a picker that hydrates through `getAllAsync()` and then filters
     *  in the browser can only ever see the first page (`DEFAULT_LIMIT` is 50),
     *  so product 51 onward is unsearchable and nothing on screen says so.
     *  Third confirmed instance of that trap after stock items and the cookbook.
     */
    searchAsync = async (needle: string, limit = 20): Promise<Page<Product>> =>
        await this.httpClient.get<Page<Product>>(
            `/products${createQueryString(
                needle.trim()
                    ? [{ field: 'name', operator: FilterOperator.CONTAINS, value: needle.trim() }]
                    : [],
                { field: 'name', order: SortOrder.ASCENDING },
                { page: 1, limit },
            )}`,
        );


    /** Hard delete (feedback L197). Takes the product's offers, price history,
     *  alerts, barcode and stock-item link with it; lines on *finished*
     *  shopping lists survive, naming the product from the snapshot frozen
     *  when the list was finished (FU-883). */
    deleteAsync = async (productId: string): Promise<void> =>
        await this.httpClient.delete(`/products/${productId}`);

    updateAsync = async (productToUpdate: UpdateProductCommand): Promise<Product> => {
        const { product_id, ...payload } = productToUpdate;
        return await this.httpClient.patch<Product>(`/products/${product_id}`, payload);
    };
}

export type CreateProductCommand = {
    brand: string | null;
    // `data:image/...;base64,...` string.
    image: string | null;
    is_active: boolean;
    is_available: boolean;
    store_name: string;
    /** Nullable: the API has always accepted `null` (a hand-entered product
     *  has no merchant SKU). The type said otherwise. */
    merchant_stockcode: string | null;
    name: string;
    pack_count?: number | null;
    price_now: number;
    /** Optional (OD-2): a hand-entered product usually has no "was" price.
     *  Omitted means "no markdown" — the server defaults it to `price_now`. */
    price_was?: number;
    size: string;
    size_unit: string;
    size_value: number;
    /** Nullable, same as `merchant_stockcode` — a butcher has no product page. */
    web_url: string | null;
};

export type UpdateProductCommand = {
    is_active?: boolean;
    is_available?: boolean;
    price_now?: number;
    price_was?: number;
    product_id: string;
    /** Custom products only — the API 422s on an ingested one. A
     *  `data:image/...;base64,...` string from `processImageFile`. */
    image?: string;
    /** Custom products only. Wins over `image`. */
    clear_image?: boolean;
    /** Any product. `null` clears it. */
    pack_count?: number | null;
};
