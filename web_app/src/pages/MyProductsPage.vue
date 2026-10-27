<template>
    <!-- `q-pa-md`, not `padding`: `PageCountsFooter` outdents a hardcoded
         -16px to sit flush with the page edges, which assumes a 16px parent.
         Quasar's `padding` prop is responsive (8px at xs), so the footer
         over-outdented by 16px and the page scrolled sideways 8px at 375
         (D-011). Pre-existing — this page was the only one of the four using
         the footer that didn't already say `q-pa-md`; found by driving it. -->
    <q-page class="q-pa-md">
        <!-- ── Toolbar ──────────────────────────────────────────────────
             Adopts the standard list-page shape (StockOverview /
             RecipesOverview): a sideways-scrolling action band, then the
             filter toggle + search, which wrap to their own full-width line
             on phones. My Products had never taken it — it was one ad-hoc row
             with full-width labels that crushed at 375px. Feedback said little
             about this toolbar in June because the standard didn't exist yet;
             MP-20 ("bulk select button should be part of the toolbar") is the
             bullet that does point here. -->
        <div class="row items-center q-gutter-sm products-toolbar">
            <div class="row items-center no-wrap products-toolbar__actions">
                <!-- MP-18: "could be more obvious when there's more than zero.
                     Should grab attention, not be obscured." `attention` (the
                     glow BaseButton gained after this feedback) fires only
                     when there IS something to fix, which is the condition
                     that keeps a glow from becoming wallpaper (D-14 as amended
                     2026-08-20). -->
                <BaseButton
                    variant="secondary"
                    :icon="ICONS.link_off"
                    :label="compactToolbar ? undefined : orphansLabel"
                    :aria-label="orphansLabel"
                    :disable="stockItemsMissingProducts.length === 0"
                    :attention="stockItemsMissingProducts.length > 0"
                    @click="orphansOpen = true"
                >
                    <q-badge
                        v-if="compactToolbar && stockItemsMissingProducts.length > 0"
                        color="primary"
                        class="q-ml-xs"
                    >
                        {{ stockItemsMissingProducts.length }}
                    </q-badge>
                    <BaseTooltip v-if="compactToolbar">{{ orphansLabel }}</BaseTooltip>
                </BaseButton>

                <!-- OD-2 — hand-enter a product for a shop no scraper
                     covers. `PreferredBuy` can't: it is a label with no price,
                     store or history. -->
                <BaseButton
                    variant="secondary"
                    :icon="ICONS.add"
                    :label="compactToolbar ? undefined : 'Add custom'"
                    aria-label="Add a custom product"
                    @click="customOpen = true"
                >
                    <BaseTooltip v-if="compactToolbar">Add a custom product</BaseTooltip>
                </BaseButton>

                <BaseButton
                    v-if="!bulkMode"
                    variant="secondary"
                    :icon="ICONS.checklist"
                    :label="compactToolbar ? undefined : 'Bulk select'"
                    aria-label="Bulk select"
                    @click="enterBulkMode"
                >
                    <BaseTooltip v-if="compactToolbar">Bulk select</BaseTooltip>
                </BaseButton>
                <BaseButton
                    v-else
                    variant="secondary"
                    :icon="ICONS.close"
                    :label="compactToolbar ? undefined : 'Cancel'"
                    aria-label="Cancel bulk select"
                    @click="exitBulkMode"
                >
                    <BaseTooltip v-if="compactToolbar">Cancel bulk select</BaseTooltip>
                </BaseButton>

                <!-- D-10 — the two view modes, on the cookbook's existing
                     toggle machinery rather than a second implementation. -->
                <BaseButton
                    variant="secondary"
                    :icon="viewMode === 'grid' ? ICONS.view_list : ICONS.view_module"
                    :label="compactToolbar ? undefined : (viewMode === 'grid' ? 'Compact' : 'Cards')"
                    :aria-label="viewMode === 'grid'
                        ? 'Switch to compact rows'
                        : 'Switch to cards, with photos'"
                    @click="toggleViewMode"
                >
                    <BaseTooltip>
                        {{ viewMode === 'grid' ? 'Compact rows, no photos' : 'Card grid with photos' }}
                    </BaseTooltip>
                </BaseButton>

                <!-- MP-19 / C16: the Refresh button is gone. "I can't think of
                     anywhere in the app I'd need a refresh button. This isn't
                     the type of app to be kept open in long sessions." The
                     store already refetches on mount and after every mutation. -->
            </div>

            <q-space class="gt-xs" />
            <div class="row items-center q-gutter-sm no-wrap products-toolbar__find">
                <FilterToggleButton
                    v-model="filtersExpanded"
                    :active-count="activeFilterCount"
                    :compact="compactToolbar"
                    @clear="clearFilters"
                />
                <q-input
                    v-model="searchText"
                    class="col"
                    dense
                    outlined
                    clearable
                    debounce="200"
                    placeholder="Search products"
                >
                    <template #prepend><q-icon :name="ICONS.search" /></template>
                </q-input>
            </div>
        </div>

        <!-- ── Bulk-select bar ──────────────────────────────────────────
             Was a `q-banner` carrying a sentence of instructions; now the
             shared `dora-subbar` that stock and the shopping list already use
             (MP-13: "bulk select button and area is different in styling to
             other screens. Should be consistent."). The explanatory prose is
             gone with it — MP-20's point was that it's "info that is learnt
             then not needed to be shown again". -->
        <div class="bulk-bar q-py-xs">
            <q-slide-transition>
                <div v-if="bulkMode" class="dora-subbar">
                    <div class="dora-subbar__inner">
                        <div class="row items-center q-gutter-sm no-wrap products-bulk">
                            <q-icon :name="ICONS.checklist" />
                            <span class="text-weight-medium no-wrap">
                                {{ selectedIds.size }} selected
                            </span>

                            <!-- The owner asked for four more select-helpers
                                 (MP-14..MP-17) and then "Are my buttons making
                                 sense? Better way to do it?" — six select
                                 buttons plus four actions is a bar nobody can
                                 scan. They collapse into one menu; the
                                 *actions* stay inline, because those are what
                                 the mode exists to do. -->
                            <BaseButton
                                variant="ghost"
                                dense
                                :icon="ICONS.checklist"
                                label="Select…"
                            >
                                <q-menu auto-close>
                                    <q-list dense style="min-width: 240px">
                                        <q-item clickable @click="selectAllVisible">
                                            <q-item-section>All visible</q-item-section>
                                        </q-item>
                                        <q-item clickable @click="selectWhere(onSpecial)">
                                            <q-item-section>On deal</q-item-section>
                                        </q-item>
                                        <q-item clickable @click="selectWhere((p) => !p.is_active)">
                                            <q-item-section>Inactive</q-item-section>
                                        </q-item>
                                        <q-separator />
                                        <!-- MP-15/16/17. These cross product
                                             state with *stock* state, so they
                                             read the server-owned
                                             `is_low_stock` / `is_out_of_stock`
                                             / `is_essential` rather than
                                             re-deriving from level names or
                                             sequences (R-003). -->
                                        <q-item clickable @click="selectWhere(isLowStockOnDeal)">
                                            <q-item-section>Low stock, on deal</q-item-section>
                                        </q-item>
                                        <q-item clickable @click="selectWhere(isOutOfStockOnDeal)">
                                            <q-item-section>Out of stock, on deal</q-item-section>
                                        </q-item>
                                        <q-item clickable @click="selectWhere(isEssentialLowOnDeal)">
                                            <q-item-section>Essential, low, on deal</q-item-section>
                                        </q-item>
                                        <q-separator />
                                        <!-- MP-12: "No way to deselect all in
                                             bulk select mode." -->
                                        <q-item clickable @click="selectedIds = new Set()">
                                            <q-item-section>Deselect all</q-item-section>
                                        </q-item>
                                    </q-list>
                                </q-menu>
                            </BaseButton>

                            <q-separator vertical />

                            <BaseButton
                                variant="ghost"
                                dense
                                :icon="ICONS.add_shopping_cart"
                                :label="`Add ${onDealSelectedCount} on-deal to list`"
                                :disable="onDealSelectedCount === 0"
                                :loading="bulkBusy"
                                @click="onBulkAddOnDeal"
                            />
                            <BaseButton
                                variant="ghost"
                                dense
                                :icon="ICONS.link_off"
                                label="Unlink"
                                :disable="selectedIds.size === 0"
                                :loading="bulkBusy"
                                @click="onBulkUnlink"
                            />
                            <BaseButton
                                variant="ghost"
                                dense
                                :icon="ICONS.visibility_off"
                                label="Stop tracking"
                                :disable="selectedIds.size === 0"
                                :loading="bulkBusy"
                                @click="onBulkInactive"
                            />
                            <q-space />
                            <BaseButton
                                variant="danger-ghost"
                                dense
                                :icon="ICONS.delete"
                                label="Delete"
                                :disable="selectedIds.size === 0"
                                :loading="bulkBusy"
                                @click="onBulkDelete"
                            />
                            <BaseButton variant="ghost" dense label="Done" @click="exitBulkMode" />
                        </div>
                    </div>
                </div>
            </q-slide-transition>
        </div>

        <!-- ── Filters ──────────────────────────────────────────────────── -->
        <FilterBar
            v-model="filtersExpanded"
            :toolbar="false"
            :active-count="activeFilterCount"
            @clear="clearFilters"
        >
            <template #filters>
                <FilterRow variant="fields">
                    <q-toggle v-model="onDealOnly" label="On deal now" dense />
                    <BaseSelect
                        v-model="storeFilter"
                        :options="storeOptions"
                        emit-value
                        map-options
                        clearable
                        label="Store"
                        empty-text="Any store"
                        dialog-title="Store"
                    />
                    <q-select
                        v-model="linkedStockItemFilter"
                        outlined
                        dense
                        emit-value
                        map-options
                        clearable
                        use-input
                        input-debounce="150"
                        :options="linkedStockItemOptions"
                        label="Linked stock item"
                        style="min-width: 240px"
                        @filter="onLinkedFilter"
                    />
                    <q-toggle v-model="includeInactive" label="Show untracked" dense />
                </FilterRow>
            </template>
        </FilterBar>

        <!-- ── Results ──────────────────────────────────────────────────── -->
        <FadeTransition mode="out-in">
            <div
                v-if="loading && products.length === 0"
                key="prod-loading"
                class="text-center q-py-xl"
            >
                <AppSpinner size="48px" />
            </div>

            <q-banner
                v-else-if="loadError"
                key="prod-error"
                class="dora-bg-negative-soft text-negative"
                dense
                rounded
            >
                {{ loadError }}
            </q-banner>

            <div
                v-else-if="filteredProducts.length === 0"
                key="prod-empty"
                class="text-center dora-text-muted q-py-xl"
            >
                <q-icon :name="ICONS.shopping_bag" size="60px" class="q-mb-sm" />
                <div v-if="products.length === 0">
                    You haven't saved any products yet. {{ emptyHint }}
                </div>
                <div v-else>No products match the current filters.</div>
                <BaseButton
                    v-if="products.length === 0 && productSearchLabel"
                    variant="primary"
                    :icon="ICONS.search"
                    :label="productSearchLabel"
                    class="q-mt-md"
                    @click="openProductSearch(router)"
                />
                <BaseButton
                    v-else-if="hasAnyFilter"
                    variant="ghost"
                    color="primary"
                    label="Clear filters"
                    class="q-mt-md"
                    @click="clearFilters"
                />
            </div>

            <!-- Two shapes, one data path — the compact branch is the same
                 `filteredProducts` the grid renders (the cookbook's shape). -->
            <div v-else-if="viewMode === 'grid'" key="prod-grid" class="row q-col-gutter-md">
                <!-- Owner 2026-10-15: two to a row on a phone (one card was the
                     whole screen). -->
                <!-- The key carries a photo version so a replaced custom-product
                     photo refetches: the card's thumb only reloads when the id
                     or has-image flag changes, and a re-upload changes neither. -->
                <div
                    v-for="product in filteredProducts"
                    :key="`${product.product_id}:${photoVersion.get(product.product_id) ?? 0}`"
                    class="col-6 col-md-4"
                >
                    <ProductCard
                        :product="product"
                        :bulk-mode="bulkMode"
                        :selected="selectedIds.has(product.product_id)"
                        :watch-threshold="watchByProduct.get(product.product_id)?.threshold_unit_price ?? null"
                        @watch-price="openWatch(product)"
                        @toggle-select="toggleSelect(product.product_id)"
                        @open-stock-item="goToStockItem"
                        @link="openLinkDialog(product)"
                        @unlink="onUnlinkSingle(product)"
                        @toggle-active="onToggleActive(product)"
                        @price-history="onViewPriceHistory(product.product_id)"
                        @photo="openPhoto(product)"
                        @pack-count="openPackCount(product)"
                        @delete="onDeleteSingle(product)"
                    />
                </div>
            </div>

            <!-- `no-wrap`: Quasar's `.column` wraps, and in a wrapping column
                 each row sizes to its content, which pushed a long name's row
                 past a phone's edge (owner 2026-10-15). -->
            <div v-else key="prod-rows" class="column no-wrap q-gutter-sm">
                <ProductRow
                    v-for="product in filteredProducts"
                    :key="product.product_id"
                    :product="product"
                    :bulk-mode="bulkMode"
                    :selected="selectedIds.has(product.product_id)"
                    @toggle-select="toggleSelect(product.product_id)"
                    @link="openLinkDialog(product)"
                    @unlink="onUnlinkSingle(product)"
                />
            </div>
        </FadeTransition>

        <PageCountsFooter v-if="products.length > 0" :counts="footerCounts" />

        <!-- ── Bulk-add target-list picker ──────────────────────────────── -->
        <BaseDialog
            v-model="bulkAddOpen"
            title="Add to which list?"
            closable
            card-style="min-width: 380px"
        >
            <q-card-section>
                <div class="text-caption dora-text-muted">
                    {{ bulkAddCandidates.length }} stock item{{
                        bulkAddCandidates.length === 1 ? '' : 's'
                    }} from on-deal products in your selection.
                </div>
            </q-card-section>
            <q-card-section class="q-pt-none">
                <q-select
                    v-model="bulkAddTargetListId"
                    outlined
                    dense
                    emit-value
                    map-options
                    :options="activeListOptions"
                    label="Active list"
                />
            </q-card-section>
            <template #actions>
                <BaseButton variant="ghost" label="Cancel" v-close-popup />
                <BaseButton
                    variant="primary"
                    label="Add"
                    :loading="bulkBusy"
                    :disable="!bulkAddTargetListId"
                    @click="confirmBulkAdd"
                />
            </template>
        </BaseDialog>

        <!-- ── Stock items without products ─────────────────────────────── -->
        <BaseDialog
            v-model="orphansOpen"
            title="Stock items without products"
            closable
            :maximized="$q.screen.lt.sm"
            card-style="width: 560px; max-width: 100vw; height: 90vh"
            card-class="column"
        >
            <q-card-section class="q-pb-sm">
                <div class="text-caption dora-text-muted">
                    {{ stockItemsMissingProducts.length }} item{{
                        stockItemsMissingProducts.length === 1 ? '' : 's'
                    }} that no product in My Products is linked to.
                    <template v-if="productSearch.configured.value">Hop into Product Search to find one.</template>
                </div>
            </q-card-section>
            <q-card-section class="col scroll">
                <q-list separator>
                    <q-item
                        v-for="item in stockItemsMissingProducts"
                        :key="item.stock_item_id"
                    >
                        <q-item-section avatar>
                            <q-avatar
                                :color="levelColourFor(item) ?? undefined"
                                :text-color="levelColourFor(item) ? 'white' : undefined"
                                :class="{ 'dora-bg-sunken dora-text-secondary': !levelColourFor(item) }"
                                size="32px"
                            >
                                <q-icon :name="ICONS.inventory_2" size="16px" />
                            </q-avatar>
                        </q-item-section>
                        <q-item-section>
                            <q-item-label>{{ item.name }}</q-item-label>
                            <q-item-label caption>
                                {{ levelNameFor(item) ?? 'No level' }}
                            </q-item-label>
                        </q-item-section>
                        <q-item-section v-if="productSearch.configured.value" side>
                            <BaseButton
                                variant="icon"
                                color="primary"
                                :icon="ICONS.search"
                                aria-label="Find a product"
                                @click="searchForOrphan()"
                            >
                                <BaseTooltip>Find a product</BaseTooltip>
                            </BaseButton>
                        </q-item-section>
                    </q-item>
                </q-list>
            </q-card-section>
        </BaseDialog>

        <CustomProductDialog v-model="customOpen" @created="refreshProducts" />

        <ProductPhotoDialog
            v-model="photoOpen"
            :product="photoTarget"
            @saved="onPhotoSaved"
        />

        <ProductPackCountDialog
            v-model="packCountOpen"
            :product="packCountTarget"
            @saved="refreshProducts"
        />

        <ProductPriceWatchDialog
            v-model="watchOpen"
            :product="watchTarget"
            :watch="watchTarget ? (watchByProduct.get(watchTarget.product_id) ?? null) : null"
            @saved="loadWatches"
        />

        <!-- ── Link-to-stock-item dialog ────────────────────────────────── -->
        <BaseDialog
            v-model="linkOpen"
            title="Link to a stock item"
            closable
            card-style="min-width: 420px"
        >
            <q-card-section>
                <div class="text-caption dora-text-muted">{{ linkTarget?.name }}</div>
            </q-card-section>
            <q-card-section class="q-pt-none">
                <q-select
                    v-model="linkChoiceStockItemId"
                    outlined
                    dense
                    use-input
                    input-debounce="150"
                    :options="linkStockItemOptions"
                    emit-value
                    map-options
                    clearable
                    label="Stock item"
                    @filter="onLinkPickerFilter"
                />
            </q-card-section>
            <template #actions>
                <BaseButton variant="ghost" label="Cancel" v-close-popup />
                <BaseButton
                    variant="primary"
                    label="Link"
                    :loading="linkBusy"
                    :disable="!linkChoiceStockItemId"
                    @click="confirmLink"
                />
            </template>
        </BaseDialog>
    </q-page>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import AppSpinner from 'src/components/AppSpinner.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import FilterBar from 'src/components/FilterBar.vue';
    import FilterRow from 'src/components/filters/FilterRow.vue';
    import FilterToggleButton from 'src/components/FilterToggleButton.vue';
    import PageCountsFooter from 'src/components/PageCountsFooter.vue';
    import CustomProductDialog from 'src/components/products/CustomProductDialog.vue';
    import ProductCard from 'src/components/products/ProductCard.vue';
    import ProductPackCountDialog from 'src/components/products/ProductPackCountDialog.vue';
    import ProductPhotoDialog from 'src/components/products/ProductPhotoDialog.vue';
    import ProductRow from 'src/components/products/ProductRow.vue';
    import ProductPriceWatchDialog from 'src/components/products/ProductPriceWatchDialog.vue';
    import PriceHistoryApiService, { type PriceAlert } from 'src/services/api/priceHistoryApiService';
    import FadeTransition from 'src/components/transitions/FadeTransition.vue';
    import { useFilterPanelExpanded } from 'src/composables/useFilterPanelExpanded';
    import { useListState } from 'src/composables/useListState';
    import { useListViewMode } from 'src/composables/useListViewMode';
    import { openProductSearch, useProductSearchUrl } from 'src/composables/useProductSearchUrl';
    import { useShoppingListActions } from 'src/composables/useShoppingListActions';
    import { colourForSequence } from 'src/helpers/stockLevelLogic';
    import type { Product } from 'src/models/product';
    import type { StockItem } from 'src/models/stockItem';
    import ProductApiService from 'src/services/api/productApiService';
    import StockItemApiService from 'src/services/api/stockItemApiService';
    import { describeApiError, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useAuthStore } from 'src/stores/authStore';
    import { useProductStore } from 'src/stores/productStore';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { ICONS } from 'src/style/icons';
    import { storeToRefs } from 'pinia';
    import { useQuasar } from 'quasar';
    import { computed, onMounted, ref } from 'vue';
    import { useRouter } from 'vue-router';
    import { isOnSpecial } from 'src/helpers/offerLogic';
    import { useConfirm } from 'src/composables/useConfirm';

    const $q = useQuasar();

    const { confirm } = useConfirm();
    const router = useRouter();
    const productApi = new ProductApiService();
    const stockItemApi = new StockItemApiService();
    const productStore = useProductStore();
    const shoppingListStore = useShoppingListStore();
    const stockItemStore = useStockItemStore();
    const stockLevelStore = useStockLevelStore();
    const { addItems } = useShoppingListActions();

    const { products } = storeToRefs(productStore);
    const { stockItems } = storeToRefs(stockItemStore);

    const loading = ref(false);
    const loadError = ref<string | null>(null);

    const compactToolbar = computed(() => $q.screen.lt.sm);
    // D-10 — remembered across visits, same machinery as the cookbook.
    const viewMode = useListViewMode('my-products');
    function toggleViewMode() {
        viewMode.value = viewMode.value === 'grid' ? 'compact' : 'grid';
    }

    const orphansLabel = computed(
        () => `Stock items without products (${stockItemsMissingProducts.value.length})`,
    );

    // Everything the page reads, once on mount. A mutation refreshes only what
    // it changed: `refreshProducts` / `refreshLinks` below.
    async function loadAll() {
        loading.value = true;
        loadError.value = null;
        try {
            await Promise.all([
                productStore.getProductsAsync(),
                stockItemStore.ensureLoadedAsync(),
                stockLevelStore.ensureLoadedAsync(),
                shoppingListStore.refreshAsync(),
                loadWatches(),
            ]);
        } catch (err) {
            loadError.value = `Could not load: ${describeApiError(err)}`;
        } finally {
            loading.value = false;
        }
    }

    async function refreshProducts(): Promise<void> {
        await productStore.getProductsAsync();
    }
    /** A link lives on the stock item, so both sides refresh. */
    async function refreshLinks(): Promise<void> {
        await Promise.all([productStore.getProductsAsync(), stockItemStore.getStockItemsAsync()]);
    }

    // ── Price watches (owner 2026-10-15) ────────────────────────────────
    // The user's own watches, keyed by product so each card can say whether
    // it has one. The bell only fires a watch with money features on
    // (`get_alerts._price_drop_alerts`); setting one is not gated.
    const priceHistoryApi = new PriceHistoryApiService();
    const watches = ref<PriceAlert[]>([]);
    const watchByProduct = computed(
        () => new Map(watches.value.map((w) => [w.product_id, w])),
    );
    const watchOpen = ref(false);
    const watchTarget = ref<Product | null>(null);
    async function loadWatches(): Promise<void> {
        try {
            watches.value = (await priceHistoryApi.listAlertsAsync()).items;
        } catch {
            // Non-critical: cards just show no watch.
            watches.value = [];
        }
    }
    function openWatch(product: Product): void {
        watchTarget.value = product;
        watchOpen.value = true;
    }

    // ── Filters ─────────────────────────────────────────────────────────
    const myProductsState = useListState('my-products', () => ({
        searchText: ref(''),
        onDealOnly: ref(false),
        includeInactive: ref(false),
        storeFilter: ref<string | null>(null),
        linkedStockItemFilter: ref<string | null>(null),
        linkedStockItemPickerText: ref(''),
    }));
    const {
        searchText, onDealOnly, includeInactive, storeFilter,
        linkedStockItemFilter, linkedStockItemPickerText,
    } = myProductsState;

    function onLinkedFilter(value: string, update: (cb: () => void) => void) {
        update(() => { linkedStockItemPickerText.value = value; });
    }

    const onSpecial = (product: Product): boolean => isOnSpecial(product);

    const storeOptions = computed(() => {
        const names = [...new Set(products.value.map((p) => p.store_name).filter(Boolean))];
        return names.sort().map((n) => ({ label: n, value: n }));
    });

    const linkedStockItemOptions = computed(() => {
        const linkedIds = new Set(
            products.value
                .map((p) => p.linked_stock_item_id)
                .filter((id): id is string => Boolean(id)),
        );
        const q = linkedStockItemPickerText.value.trim().toLowerCase();
        return stockItems.value
            .filter((s) => linkedIds.has(s.stock_item_id))
            .filter((s) => !q || s.name.toLowerCase().includes(q))
            .map((s) => ({ label: s.name, value: s.stock_item_id }));
    });

    const filteredProducts = computed(() =>
        products.value.filter((p) => {
            if (!includeInactive.value && !p.is_active) return false;
            if (onDealOnly.value && !onSpecial(p)) return false;
            // A4: explicit "empty = off" — a null selection skips the predicate.
            if (storeFilter.value !== null && p.store_name !== storeFilter.value) return false;
            if (
                linkedStockItemFilter.value !== null
                && p.linked_stock_item_id !== linkedStockItemFilter.value
            ) return false;
            if (searchText.value) {
                const q = searchText.value.toLowerCase();
                const haystack = [
                    p.name, p.brand, p.store_name, p.linked_stock_item_name ?? '', p.size,
                ].filter(Boolean).join(' ').toLowerCase();
                if (!haystack.includes(q)) return false;
            }
            return true;
        }),
    );

    const footerCounts = computed(() => [
        { label: 'Shown', value: filteredProducts.value.length },
        {
            label: 'On deal',
            value: filteredProducts.value.filter(onSpecial).length,
            tone: 'positive' as const,
        },
        {
            label: 'Unlinked',
            value: filteredProducts.value.filter((p) => !p.linked_stock_item_id).length,
            tone: 'warning' as const,
        },
    ]);

    const hasAnyFilter = computed(
        () => searchText.value !== ''
            || onDealOnly.value
            || includeInactive.value
            || storeFilter.value !== null
            || linkedStockItemFilter.value !== null,
    );
    const activeFilterCount = computed(() => {
        let n = 0;
        if (onDealOnly.value) n++;
        if (includeInactive.value) n++;
        if (storeFilter.value !== null) n++;
        if (linkedStockItemFilter.value !== null) n++;
        return n;
    });
    const filtersExpanded = useFilterPanelExpanded(
        'my-products',
        () => activeFilterCount.value > 0,
    );
    function clearFilters() {
        searchText.value = '';
        onDealOnly.value = false;
        includeInactive.value = false;
        storeFilter.value = null;
        linkedStockItemFilter.value = null;
    }

    // ── Bulk-select ─────────────────────────────────────────────────────
    const bulkMode = ref(false);
    const selectedIds = ref<Set<string>>(new Set());
    const bulkBusy = ref(false);

    function enterBulkMode() {
        bulkMode.value = true;
        selectedIds.value = new Set();
    }
    function exitBulkMode() {
        bulkMode.value = false;
        selectedIds.value = new Set();
    }
    function toggleSelect(productId: string) {
        const next = new Set(selectedIds.value);
        if (next.has(productId)) next.delete(productId);
        else next.add(productId);
        selectedIds.value = next;
    }
    function selectAllVisible() {
        selectedIds.value = new Set(filteredProducts.value.map((p) => p.product_id));
    }
    /** Every select-helper is this one function with a different predicate —
     *  six near-identical bodies is how they'd drift. */
    function selectWhere(predicate: (product: Product) => boolean) {
        selectedIds.value = new Set(
            filteredProducts.value.filter(predicate).map((p) => p.product_id),
        );
    }

    // MP-15/16/17 cross product state with stock state. `is_low_stock`,
    // `is_out_of_stock` and `is_essential` are server-derived (R-003) — the
    // client must not re-decide what "low" means from a level name or
    // sequence, which is the trap `useStockFilters.hasAlert` fell into.
    const stockItemsById = computed(
        () => new Map(stockItems.value.map((s) => [s.stock_item_id, s])),
    );
    function linkedItem(product: Product): StockItem | undefined {
        return product.linked_stock_item_id
            ? stockItemsById.value.get(product.linked_stock_item_id)
            : undefined;
    }
    function isLowStockOnDeal(product: Product): boolean {
        return onSpecial(product) && !!linkedItem(product)?.is_low_stock;
    }
    function isOutOfStockOnDeal(product: Product): boolean {
        return onSpecial(product) && !!linkedItem(product)?.is_out_of_stock;
    }
    function isEssentialLowOnDeal(product: Product): boolean {
        const item = linkedItem(product);
        return onSpecial(product) && !!item?.is_essential && !!item?.is_low_stock;
    }

    const onDealSelectedCount = computed(
        () => products.value.filter(
            (p) => selectedIds.value.has(p.product_id) && onSpecial(p),
        ).length,
    );

    function selectedProducts(): Product[] {
        return products.value.filter((p) => selectedIds.value.has(p.product_id));
    }

    // ── Bulk add on-deal to a list ──────────────────────────────────────
    const bulkAddOpen = ref(false);
    const bulkAddTargetListId = ref<string | null>(null);

    const activeListOptions = computed(() =>
        shoppingListStore.summaries
            .filter((s) => s.status !== 'done')
            .map((s) => ({ label: s.name, value: s.shopping_list_id })),
    );

    const bulkAddCandidates = computed(() =>
        products.value.filter(
            (p) => selectedIds.value.has(p.product_id)
                && onSpecial(p)
                && Boolean(p.linked_stock_item_id),
        ),
    );

    async function onBulkAddOnDeal() {
        if (bulkAddCandidates.value.length === 0) {
            $q.notify({
                type: 'info',
                message: 'Nothing to add. Those products need a linked stock item.',
            });
            return;
        }
        bulkAddTargetListId.value =
            shoppingListStore.quickAddTargetListId ?? activeListOptions.value[0]?.value ?? null;
        if (!bulkAddTargetListId.value) {
            const go = await confirm({
                title: 'No active shopping list',
                message: 'Create or unarchive one first.',
                okLabel: 'Open lists',
            });
            if (go) void router.push('/shopping-lists');
            return;
        }
        bulkAddOpen.value = true;
    }

    async function confirmBulkAdd() {
        if (!bulkAddTargetListId.value) return;
        bulkBusy.value = true;
        try {
            await addItems(
                bulkAddTargetListId.value,
                bulkAddCandidates.value.map((p) => ({
                    stock_item_id: p.linked_stock_item_id!,
                    selected_product_id: p.product_id,
                })),
            );
            bulkAddOpen.value = false;
            exitBulkMode();
        } finally {
            bulkBusy.value = false;
        }
    }

    // ── Bulk unlink ─────────────────────────────────────────────────────
    async function onBulkUnlink() {
        const targets = selectedProducts().filter((p) => p.linked_stock_item_id);
        if (targets.length === 0) {
            $q.notify({
                type: 'info',
                message: 'None of the selected products are linked.',
            });
            return;
        }
        const ok = await confirm({
            title: `Unlink ${targets.length} product${targets.length === 1 ? '' : 's'}?`,
            message: 'They stay in My Products, but stop showing on the stock items they were linked to.',
            okLabel: 'Unlink',
            destructive: true,
        });
        if (!ok) return;
        bulkBusy.value = true;
        try {
            for (const product of targets) {
                await stockItemApi.unlinkProductAsync(
                    product.linked_stock_item_id!, product.product_id,
                );
            }
            await refreshLinks();
            $q.notify({
                type: 'positive',
                message: `Unlinked ${targets.length} product${targets.length === 1 ? '' : 's'}.`,
            });
            exitBulkMode();
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not unlink everything.',
                caption: toastCaption(err),
            });
        } finally {
            bulkBusy.value = false;
        }
    }

    // ── Bulk stop tracking ──────────────────────────────────────────────
    async function onBulkInactive() {
        const targets = selectedProducts().filter((p) => p.is_active);
        if (targets.length === 0) {
            $q.notify({
                type: 'info',
                message: 'None of those are being tracked.',
            });
            return;
        }
        bulkBusy.value = true;
        try {
            for (const product of targets) {
                await productApi.updateAsync({
                    product_id: product.product_id, is_active: false,
                });
            }
            await refreshProducts();
            $q.notify({
                type: 'positive',
                message: `Stopped tracking ${targets.length} product${targets.length === 1 ? '' : 's'}.`,
            });
            exitBulkMode();
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not update.',
                caption: toastCaption(err),
            });
        } finally {
            bulkBusy.value = false;
        }
    }

    // ── Delete (L197 / batch C) ─────────────────────────────────────────
    // Names what goes with it, because the endpoint really does take the
    // price history: a confirm that only says "are you sure?" is not consent.
    const DELETE_CONSEQUENCE =
        'This also removes its price history and any price alerts on it. '
        + 'Finished shopping lists keep their record of it.';

    async function onDeleteSingle(product: Product) {
        const ok = await confirm({
            title: `Delete ${product.name}?`,
            message: DELETE_CONSEQUENCE,
            okLabel: 'Delete',
            destructive: true,
        });
        if (!ok) return;
        try {
            await productStore.deleteProductAsync(product.product_id);
            await loadWatches();
            $q.notify({
                type: 'positive', message: 'Product deleted.',
            });
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not delete the product.',
                caption: toastCaption(err),
            });
        }
    }

    async function onBulkDelete() {
        const targets = selectedProducts();
        if (targets.length === 0) return;
        const ok = await confirm({
            title: `Delete ${targets.length} product${targets.length === 1 ? '' : 's'}?`,
            message: DELETE_CONSEQUENCE,
            okLabel: 'Delete',
            destructive: true,
        });
        if (!ok) return;
        bulkBusy.value = true;
        try {
            for (const product of targets) {
                await productApi.deleteAsync(product.product_id);
            }
            await Promise.all([refreshProducts(), loadWatches()]);
            $q.notify({
                type: 'positive',
                message: `Deleted ${targets.length} product${targets.length === 1 ? '' : 's'}.`,
            });
            exitBulkMode();
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not delete everything.',
                caption: toastCaption(err),
            });
        } finally {
            bulkBusy.value = false;
        }
    }

    // ── Per-product actions ─────────────────────────────────────────────
    async function onUnlinkSingle(product: Product) {
        if (!product.linked_stock_item_id) return;
        try {
            await stockItemApi.unlinkProductAsync(
                product.linked_stock_item_id, product.product_id,
            );
            await refreshLinks();
            $q.notify({ type: 'positive', message: 'Unlinked.' });
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not unlink.',
                caption: toastCaption(err),
            });
        }
    }

    async function onToggleActive(product: Product) {
        try {
            await productStore.updateProductAsync({
                product_id: product.product_id, is_active: !product.is_active,
            });
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not update.',
                caption: toastCaption(err),
            });
        }
    }

    // ── Items in the pack (FU-856) ──────────────────────────────────────
    const packCountOpen = ref(false);
    const packCountTarget = ref<Product | null>(null);

    function openPackCount(product: Product): void {
        packCountTarget.value = product;
        packCountOpen.value = true;
    }

    // ── Custom-product photo (owner 2026-10-17) ─────────────────────────
    const photoOpen = ref(false);
    const photoTarget = ref<Product | null>(null);
    const photoVersion = ref(new Map<string, number>());

    function openPhoto(product: Product): void {
        photoTarget.value = product;
        photoOpen.value = true;
    }

    async function onPhotoSaved(): Promise<void> {
        const id = photoTarget.value?.product_id;
        if (id) photoVersion.value.set(id, (photoVersion.value.get(id) ?? 0) + 1);
        await refreshProducts();
    }

    function goToStockItem(stockItemId: string) {
        void router.push(`/stock/${stockItemId}`);
    }

    function onViewPriceHistory(productId: string) {
        void router.push({ path: '/price-history', query: { product_id: productId } });
    }

    // ── Link-to-stock-item dialog ───────────────────────────────────────
    const linkOpen = ref(false);
    const linkTarget = ref<Product | null>(null);
    const linkChoiceStockItemId = ref<string | null>(null);
    const linkPickerText = ref('');
    const linkBusy = ref(false);

    function onLinkPickerFilter(value: string, update: (cb: () => void) => void) {
        update(() => { linkPickerText.value = value; });
    }

    const linkStockItemOptions = computed(() => {
        const q = linkPickerText.value.trim().toLowerCase();
        return stockItems.value
            .filter((s) => !q || s.name.toLowerCase().includes(q))
            .slice(0, 50)
            .map((s) => ({ label: s.name, value: s.stock_item_id }));
    });

    function openLinkDialog(product: Product) {
        linkTarget.value = product;
        linkChoiceStockItemId.value = null;
        linkPickerText.value = '';
        linkOpen.value = true;
    }

    async function confirmLink() {
        if (!linkTarget.value || !linkChoiceStockItemId.value) return;
        linkBusy.value = true;
        try {
            // The stock item owns the product m2m — link directly there.
            await stockItemApi.linkProductAsync(
                linkChoiceStockItemId.value, linkTarget.value.product_id,
            );
            linkOpen.value = false;
            await refreshLinks();
            $q.notify({
                type: 'positive', message: 'Product linked.',
            });
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not link the product.',
                caption: toastCaption(err),
            });
        } finally {
            linkBusy.value = false;
        }
    }

    // ── Stock items without products ────────────────────────────────────
    const orphansOpen = ref(false);
    const customOpen = ref(false);

    const stockItemsMissingProducts = computed<StockItem[]>(() => {
        const linkedIds = new Set(
            products.value
                .filter((p) => p.is_active && p.linked_stock_item_id)
                .map((p) => p.linked_stock_item_id as string),
        );
        return stockItems.value.filter((s) => !linkedIds.has(s.stock_item_id));
    });

    function levelFor(item: StockItem) {
        return item.stock_level_id ? stockLevelStore.levelById.get(item.stock_level_id) : undefined;
    }
    function levelNameFor(item: StockItem): string | null {
        return levelFor(item)?.name ?? null;
    }
    function levelColourFor(item: StockItem): string | null {
        // sequence-keyed, not name-keyed (R-003).
        const seq = levelFor(item)?.sequence;
        return typeof seq === 'number' ? colourForSequence(seq) : null;
    }

    // Product Search is the companion app (R-029, hide when off): a configured
    // URL opens it; an admin without one is offered the setup page; a member
    // without one gets no button, since they can't set it up.
    const productSearch = useProductSearchUrl();
    const authStore = useAuthStore();
    const productSearchLabel = computed(() => {
        if (productSearch.configured.value) return 'Open Product Search';
        return authStore.isAdmin ? 'Set up Product Search' : null;
    });
    const emptyHint = computed(() => {
        if (productSearch.configured.value) {
            return 'Find and save them with Product Search, or add one with Add custom.';
        }
        if (authStore.isAdmin) return 'Set up Product Search to find them, or add one with Add custom.';
        return 'Add one with Add custom, or ask your admin to set up Product Search.';
    });

    function searchForOrphan() {
        // FU-186/FU-581 — the in-app `/product-search` route is gone; open the
        // external companion instead. Products found there are linked back via
        // the per-product link button on this page.
        orphansOpen.value = false;
        openProductSearch(router);
    }

    onMounted(loadAll);
</script>

<style scoped>
    /* Same toolbar rules as StockOverview/RecipesOverview: the action band
       scrolls sideways rather than wrapping (the buttons running off the edge
       IS the affordance), and `__find` takes its own full-width line on
       phones so the search box isn't a sliver. `gap` rather than
       `q-gutter-sm` because the gutter's negative margins fight overflow-x. */
    .products-toolbar {
        margin-bottom: var(--space-4);
    }
    .products-toolbar__actions {
        gap: var(--space-2);
        overflow-x: auto;
        overflow-y: hidden;
        min-width: 0;
        padding-bottom: 2px;
        scrollbar-width: none;
    }
    .products-toolbar__actions::-webkit-scrollbar {
        display: none;
    }
    .products-toolbar__actions > * {
        flex: 0 0 auto;
    }
    .products-toolbar__find {
        flex: 1 1 auto;
        min-width: 280px;
    }
    @media (max-width: 599px) {
        .products-toolbar__find {
            flex-basis: 100%;
            min-width: 0;
        }
    }

    /* The bulk bar scrolls for the same reason the action band does — it now
       carries four actions plus a select menu. */
    .products-bulk {
        overflow-x: auto;
        scrollbar-width: none;
    }
    .products-bulk::-webkit-scrollbar {
        display: none;
    }
    .products-bulk > * {
        flex: 0 0 auto;
    }
</style>
