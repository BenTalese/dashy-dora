<template>
    <!--
        Compact My Products row — one line per product, mirroring the cookbook's
        `RecipeRow` (which itself mirrors `StockItemRow`), so the three list
        surfaces share one compact shape. Same data and the same primary
        actions as `ProductCard`; only the layout and the action *count* differ.

        Left → right:
          Name · · ·  [% off] [store] [$price] [🔗] [🛒]
          brand · size
    -->
    <q-card
        bordered
        flat
        class="product-row"
        :class="{
            'product-row--selected': selected,
            'product-row--inactive': !product.is_active,
            'cursor-pointer': bulkMode,
        }"
        @click="onRowClick"
    >
        <q-card-section class="row items-center no-wrap product-row__body">
            <q-checkbox
                v-if="bulkMode"
                :model-value="selected"
                dense
                class="q-mr-sm"
                @click.stop
                @update:model-value="emit('toggle-select')"
            />

            <component
                :is="linkTag"
                class="col product-row__identity"
                v-bind="linkAttrs"
            >
                <div class="product-row__name ellipsis">{{ product.name }}</div>
                <div class="text-caption dora-text-muted ellipsis">
                    <span v-if="product.brand">{{ product.brand }}</span>
                    <span v-if="product.brand && product.size"> · </span>
                    <span v-if="product.size">{{ product.size }}</span>
                    <span v-if="!product.is_available" class="text-negative">
                        · Out of stock
                    </span>
                    <!-- OD-2 — a hand-entered price is a different promise
                         from a maintained one; say so here too. -->
                    <span v-if="product.is_custom" class="text-secondary">
                        · Custom
                    </span>
                </div>
            </component>

            <DiscountChip
                class="q-ml-sm"
                size="sm"
                :price-now="product.price_now"
                :price-was="product.price_was"
            />

            <StoreLogo
                v-if="product.store_name"
                :name="product.store_name"
                :store-id="product.store_id"
                :height="14"
                :width="24"
                class="q-ml-sm gt-xs"
            />

            <span class="product-row__price q-ml-sm">
                {{ formatMoney(product.price_now) }}
            </span>

            <!-- OD-1: the row carries the two *safe* everyday actions only.
                 Delete, the active toggle and price history live on the
                 expanded card — a dense row is the wrong place for a
                 destructive control, and cramming five targets in here would
                 undo the compactness that is the mode's whole point. -->
            <ProductLinkButton
                class="q-ml-sm"
                :linked="!!product.linked_stock_item_id"
                :stock-item-name="product.linked_stock_item_name"
                @link="emit('link')"
                @unlink="emit('unlink')"
            />
            <AddToListButton
                v-if="product.linked_stock_item_id"
                variant="row"
                :stock-item-id="product.linked_stock_item_id"
                :selected-product-id="product.product_id"
                @click.stop
            />
            <AddToListButton
                v-else
                variant="inline-product"
                :product-id="product.product_id"
                @click.stop
            />
        </q-card-section>
    </q-card>
</template>

<script setup lang="ts">
    /** Compact ("rows") view of a saved product — the second of the two modes
     *  the owner asked for (D-10), paired with `ProductCard`.
     *
     *  Drawn from `recipes/RecipeRow.vue` per the owner's steer that the
     *  compact design should take after the cookbook. The row opens the
     *  store's product page on click, same as the card's top half (OD-1).
     */
    import AddToListButton from 'src/components/AddToListButton.vue';
    import DiscountChip from 'src/components/chips/DiscountChip.vue';
    import ProductLinkButton from 'src/components/products/ProductLinkButton.vue';
    import StoreLogo from 'src/components/StoreLogo.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import type { Product } from 'src/models/product';
    import { useProductStoreLink } from 'src/composables/useProductStoreLink';

    const props = defineProps<{
        product: Product;
        bulkMode: boolean;
        selected: boolean;
    }>();

    const emit = defineEmits<{
        (e: 'toggle-select'): void;
        (e: 'link'): void;
        (e: 'unlink'): void;
    }>();

    // The identity block is the store link; in bulk mode a tap anywhere selects.
    const { tag: linkTag, attrs: linkAttrs } = useProductStoreLink(
        () => props.product, () => props.bulkMode,
    );

    function onRowClick(): void {
        if (props.bulkMode) emit('toggle-select');
    }
</script>

<style scoped>
    .product-row {
        border-radius: var(--radius-sm);
        transition: background-color var(--motion-fast) var(--motion-ease), outline-color var(--motion-fast) var(--motion-ease);
        outline: 2px solid transparent;
        outline-offset: -2px;
    }
    .product-row:hover {
        background: var(--overlay-hover);
    }
    .product-row--selected {
        outline-color: var(--q-primary);
    }
    .product-row--inactive {
        opacity: 0.6;
    }
    .product-row__body {
        padding: var(--space-2) var(--space-3);
        gap: 0;
    }
    /* Matches RecipeRow/StockItemRow's name treatment so the three compact
       lists read as one shape (2026-08-20 owner call). */
    .product-row__name {
        font-size: var(--font-size-md);
        font-weight: 500;
    }
    .product-row__identity {
        min-width: 0;
        color: inherit;
        text-decoration: none;
    }
    .product-row__price {
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
    }
</style>
