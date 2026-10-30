import { acceptHMRUpdate, defineStore } from 'pinia';
import type { Product } from 'src/models/product';
import type { UpdateProductCommand } from 'src/services/api/productApiService';
import ProductApiService from 'src/services/api/productApiService';
import { useFeatureFlags } from 'src/composables/useFeatureFlags';
import { useRecipeStore } from 'src/stores/recipeStore';
import { readonly, ref } from 'vue';

const productApiService = new ProductApiService();

/**
 * Post-Phase-D shape: only what surfaces today reading `Product` rows out of
 * Dora's catalogue need. The in-app live product search + its filter / sort
 * state moved to the companion app along with the scraper itself.
 */
export const useProductStore = defineStore('product', () => {
    // initialised to `[]` (not `undefined`) so consumers reading
    // `productStore.products.value` before the first hydration get a stable
    // empty array instead of an "is it undefined yet?" tri-state.
    const products = ref<Product[]>([]);
    let hydrated = false;
    let inflight: Promise<void> | null = null;

    const getProductsAsync = (): Promise<void> =>
        productApiService.getAllPagesAsync().then((items) => {
            products.value = items;
            hydrated = true;
        });

    /** R-016 — lazy hydration. See sibling stores. */
    const ensureLoadedAsync = (): Promise<void> => {
        if (hydrated) return Promise.resolve();
        inflight ??= getProductsAsync().finally(() => { inflight = null; });
        return inflight;
    };

    // Mutations refresh the product list only (R-074): a link change also
    // touches stock items, which the caller refreshes in its own store.
    const updateProductAsync = (command: UpdateProductCommand): Promise<void> =>
        productApiService.updateAsync(command).then(() => getProductsAsync());

    /** Deleting a product drops its price history, which moves recipe costs,
     *  and the `products` feature flag is data-presence (any product at all),
     *  so the last delete can switch the surface off. */
    const deleteProductsAsync = async (productIds: string[]): Promise<void> => {
        try {
            for (const productId of productIds) {
                await productApiService.deleteAsync(productId);
            }
        } finally {
            useRecipeStore().invalidateRecipes();
            void useFeatureFlags().refresh();
            await getProductsAsync();
        }
    };

    const deleteProductAsync = (productId: string): Promise<void> =>
        deleteProductsAsync([productId]);

    return {
        products: readonly(products),
        getProductsAsync,
        ensureLoadedAsync,
        updateProductAsync,
        deleteProductAsync,
        deleteProductsAsync,
    };
});

if (import.meta.hot) {
    import.meta.hot.accept(acceptHMRUpdate(useProductStore, import.meta.hot));
}
