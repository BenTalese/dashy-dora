export type Product = {
    brand: string | null;
    // Image bytes never travel in list/detail JSON. Render the photo with
    // `<ProductThumb :product-id :has-image>`, which fetches through the
    // authenticated HTTP client and hands the browser an object URL. Do NOT
    // bind the API path into an `<img src>` — that is unauthenticated by
    // construction and fails silently on a split host and in the Capacitor
    // shell (R-045; three surfaces did exactly that until FU-827).
    has_image: boolean;
    is_active: boolean;
    /** Hand-entered rather than scraped (OD-2). Never refreshed by the
     *  scheduled sync and never overwritten by ingestion, so the UI marks it —
     *  a price Dora maintains and a price you typed are different promises. */
    is_custom: boolean;
    is_available: boolean;
    store_id: string;
    store_name: string;
    // producer's SKU code, retained verbatim.
    merchant_stockcode: string | null;
    name: string;
    /** How many countable things the pack holds (12 eggs in a 700 g carton).
     *  Null for a single pack or free weight. */
    pack_count: number | null;
    price_now: number;
    price_was: number;
    product_id: string;
    size: string;
    size_unit: string;
    size_value: number;
    web_url: string | null;
    // Set when the product is linked to a stock item via the
    // StockItemProduct m2m. Null for orphaned/unlinked products.
    linked_stock_item_id: string | null;
    linked_stock_item_name: string | null;
};
