<template>
    <!-- The stock-item page's Products tab (FU-934 split): linked products,
         cheapest first, each with its own Add-to-list, plus the Find & link
         entry. The sparklines are fetched with the detail by the page
         (`useStockItemDetail`). Multi-root on purpose: the panel's DOM is
         exactly what it was before the split. -->
    <template v-if="detail">
        <div v-if="detail.products.length > 0" class="row items-center q-mb-sm q-gutter-sm">
            <div class="text-subtitle1">Linked products</div>
            <q-space />
            <BaseButton
                v-if="canFindProducts"
                variant="ghost"
                :icon="ICONS.add"
                label="Link another"
                @click="onFindAndLink"
            />
        </div>

        <div v-if="detail.products.length === 0" class="column items-center q-py-xl q-gutter-md">
            <q-icon :name="ICONS.local_offer" size="48px" class="dora-text-secondary" />
            <div class="text-subtitle1">No products linked yet</div>
            <div class="dora-text-secondary text-caption text-center stock-detail__empty-copy">
                Link a product to surface live deals and price
                history for this stock item.
            </div>
            <BaseButton
                v-if="canFindProducts"
                variant="primary"
                :icon="ICONS.local_offer"
                label="Find &amp; link a product"
                @click="onFindAndLink"
            />
        </div>

        <div v-else class="row q-col-gutter-md">
            <div
                v-for="prod in sortedProducts"
                :key="prod.product_id"
                class="col-12 col-md-6"
            >
                <!-- cheapest card carries a "Cheapest"
                     chip + a subtle highlight class so the
                     cheaper option pops without needing a
                     separate "Add cheapest" button (§2.4). -->
                <q-card
                    bordered
                    flat
                    :class="{ 'dora-product-card--cheapest': isCheapest(prod) }"
                >
                    <q-card-section class="row items-center no-wrap q-pb-xs">
                        <StoreLogo
                            :name="prod.store_name"
                            :store-id="prod.store_id"
                            :height="20"
                            :width="34"
                            class="q-mr-sm"
                        />
                        <div class="col">
                            <div class="ellipsis text-weight-medium">{{ prod.name }}</div>
                            <div class="text-caption dora-text-muted">
                                {{ prod.store_name }}
                                <span v-if="prod.size"> · {{ prod.size }}</span>
                            </div>
                        </div>
                        <q-chip
                            v-if="isCheapest(prod)"
                            dense
                            class="dora-chip--tint-positive"
                        >
                            Cheapest
                        </q-chip>
                        <DiscountChip
                            :price-now="prod.price_now"
                            :price-was="prod.price_was"
                        />
                    </q-card-section>

                    <q-card-section class="row items-center q-py-xs">
                        <div>
                            <span v-if="prod.price_now !== null" class="text-h6">
                                {{ formatMoney(prod.price_now) }}
                            </span>
                            <span
                                v-if="isOnSpecial(prod)"
                                class="text-caption dora-text-muted strike q-ml-xs"
                            >
                                {{ formatMoney(prod.price_was) }}
                            </span>
                        </div>
                        <q-space />
                        <TrendSparkline :values="priceHistory.get(prod.product_id) ?? []" />
                    </q-card-section>

                    <q-separator />
                    <q-card-actions align="right">
                        <!-- MP-6 / L196 — the componentised cart
                             button, finally on the third product
                             surface. This was a hand-rolled button
                             that silently added to the primary list
                             (or fell back to the generic add), so
                             it was the only place a product could
                             reach a list *without* the cart-state
                             UX the rest of the app has: the picker
                             on 2+ lists, smart-remove on exactly
                             one, and the on-a-list state showing on
                             the control itself. -->
                        <AddToListButton
                            variant="row"
                            :stock-item-id="stockItemId"
                            :selected-product-id="prod.product_id"
                            @click.stop
                        />
                        <BaseButton
                            :aria-label="`Open on ${prod.store_name}`"
                            v-if="isWebLink(prod.web_url)"
                            variant="icon"
                            :icon="ICONS.open_in_new"
                            :href="prod.web_url"
                            target="_blank"
                            rel="noopener"
                        >
                            <BaseTooltip>Open on {{ prod.store_name }}</BaseTooltip>
                        </BaseButton>
                        <BaseButton :aria-label="`Unlink ${prod.name}`" variant="icon" :icon="ICONS.link_off" class="text-negative" @click="onUnlink(prod.product_id)">
                            <BaseTooltip>Unlink</BaseTooltip>
                        </BaseButton>
                    </q-card-actions>
                </q-card>
            </div>
        </div>
    </template>
</template>

<script lang="ts" setup>
    import { computed } from 'vue';
    import { useRouter } from 'vue-router';
    import AddToListButton from 'src/components/AddToListButton.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import StoreLogo from 'src/components/StoreLogo.vue';
    import TrendSparkline from 'src/components/TrendSparkline.vue';
    import DiscountChip from 'src/components/chips/DiscountChip.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import { openProductSearch, useProductSearchUrl } from 'src/composables/useProductSearchUrl';
    import { useStockItemDetail } from 'src/composables/useStockItemDetail';
    import { isOnSpecial } from 'src/helpers/offerLogic';
    import type { LinkedProduct } from 'src/models/stockItemDetail';
    import { useAuthStore } from 'src/stores/authStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { ICONS } from 'src/style/icons';

    const { stockItemApi, stockItemId, detail, priceHistory, withBusyReload } = useStockItemDetail();
    const router = useRouter();
    const stockItemStore = useStockItemStore();

    // The server validates the scheme on write; this guards older rows so a
    // stored `javascript:` (or any non-web) URL never becomes a live link.
    function isWebLink(url: string | null | undefined): url is string {
        return !!url && /^https?:\/\//i.test(url.trim());
    }

    // `discountPct` moved into `DiscountChip` (FU-885) — it was one of four
    // copies of the same rule, rendered three different ways.

    // Cheapest first, then by name.
    const sortedProducts = computed(() =>
        [...(detail.value?.products ?? [])].sort((a, b) => {
            const priceDiff = (a.price_now ?? Infinity) - (b.price_now ?? Infinity);
            if (priceDiff !== 0) return priceDiff;
            return a.name.localeCompare(b.name);
        }),
    );
    const cheapestProduct = computed<LinkedProduct | null>(() => {
        const withPrice = (detail.value?.products ?? []).filter((p) => p.price_now != null);
        if (withPrice.length === 0) return null;
        return withPrice.reduce((min, p) => (p.price_now! < min.price_now! ? p : min));
    });

    // the cheapest product gets a chip + highlight
    // style rather than a separate "Add cheapest" button — each product
    // carries its own Add-to-list.
    function isCheapest(p: LinkedProduct): boolean {
        return cheapestProduct.value?.product_id === p.product_id;
    }

    // Find-deals now lives only inside the Products tab (empty-state CTA +
    // "Link another" when products exist). FU-186 retired the in-app
    // `/product-search` route; both entry points now open the external
    // Product Search companion (or the Features setup page when unset).
    // Product Search opens when a URL is set; without one only an admin has
    // somewhere to go (the setup page), as on My products.
    const productSearch = useProductSearchUrl();
    const authStore = useAuthStore();
    const canFindProducts = computed(() => productSearch.configured.value || authStore.isAdmin);

    function onFindAndLink() {
        openProductSearch(router);
    }

    // `onAddProductToList` removed 2026-09-06 — `AddToListButton` owns this
    // flow now (MP-6 / L196).

    // ── Unlink products ──────────────────────────────────────────────────
    // The saved-products picker dialog was retired; the Find-&-link CTA
    // opens the external Product Search companion (FU-186), and products are
    // linked back from the My Products "Link to stock item…" dialog.
    async function onUnlink(productId: string) {
        await withBusyReload(() => stockItemApi.unlinkProductAsync(stockItemId.value, productId));
        stockItemStore.invalidatePriceFacts(stockItemId.value);
    }
</script>

<style scoped>
    .strike {
        text-decoration: line-through;
    }

    /* C-1b.3 — emphasise the cheapest linked product per §2.4 (style, not a
       separate "Add cheapest" button). Subtle outline + tinted background
       via the brand-primary token so it follows the active theme. */
    .dora-product-card--cheapest {
        border-color: var(--brand-primary) !important;
        background: color-mix(in srgb, var(--brand-primary) 8%, transparent);
    }

    .stock-detail__empty-copy {
        max-width: 360px;
    }
</style>
