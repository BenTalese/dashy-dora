<template>
    <q-card
        flat
        bordered
        class="product-card column no-wrap full-height"
        :class="{
            'product-card--selected': selected,
            'product-card--inactive': !product.is_active,
        }"
        @click="onCardClick"
    >
        <!-- ── Top half: opens the store's own product page (OD-1) ──────
             The whole media + identity block is the link, which is what let
             the separate "Open at store" icon go. Suppressed in bulk mode,
             where a card tap means "select". -->
        <component
            :is="topHalfTag"
            class="product-card__top"
            :class="{ 'product-card__top--linked': isTopHalfLink }"
            v-bind="topHalfAttrs"
            @click="onTopHalfClick"
        >
            <div class="product-card__media">
                <ProductThumb
                    fill
                    :product-id="product.product_id"
                    :has-image="product.has_image"
                    :alt="product.name"
                    icon-size="48px"
                />
                <DiscountChip
                    class="product-card__discount"
                    :price-now="product.price_now"
                    :price-was="product.price_was"
                />
                <!-- D-001: out of stock is the escalation state, so it takes
                     the red the discount badge used to be wearing. -->
                <div v-if="!product.is_available" class="product-card__oos">
                    Out of stock
                </div>
                <q-checkbox
                    v-if="bulkMode"
                    :model-value="selected"
                    class="product-card__select"
                    dense
                    @click.stop
                    @update:model-value="emit('toggle-select')"
                />
            </div>

            <q-card-section class="q-py-sm col">
                <div class="product-card__name ellipsis-2-lines">{{ product.name }}</div>
                <div class="text-caption dora-text-muted">
                    <span v-if="product.brand">{{ product.brand }}</span>
                    <span v-if="product.brand && product.size"> · </span>
                    <span v-if="product.size">{{ product.size }}</span>
                </div>
                <div class="row items-baseline q-gutter-xs q-mt-xs">
                    <span class="text-h6">{{ formatMoney(product.price_now) }}</span>
                    <span
                        v-if="hasDiscount"
                        class="text-caption dora-text-muted product-card__was"
                    >
                        {{ formatMoney(product.price_was) }}
                    </span>
                </div>
                <div v-if="watchThreshold != null" class="product-card__watch">
                    <q-icon :name="ICONS.price_check" size="14px" />
                    Alert at {{ formatMoney(watchThreshold) }}
                </div>
                <div class="text-caption dora-text-muted row items-center">
                    <StoreLogo
                        v-if="product.store_name"
                        :name="product.store_name"
                        :store-id="product.store_id"
                        :height="14"
                        :width="24"
                        class="q-mr-xs"
                    />
                    {{ product.store_name || '–' }}
                </div>
            </q-card-section>
        </component>

        <!-- ── Linked stock item ──────────────────────────────────────── -->
        <q-card-section class="q-py-none">
            <q-chip
                v-if="product.linked_stock_item_id"
                dense
                clickable
                color="primary"
                text-color="white"
                :icon="ICONS.link"
                @click.stop="emit('open-stock-item', product.linked_stock_item_id!)"
            >
                {{ product.linked_stock_item_name ?? 'Stock item' }}
                <BaseTooltip>Open stock item</BaseTooltip>
            </q-chip>
            <span v-else class="text-caption dora-text-muted">Not linked</span>
            <!-- OD-2 — say which prices Dora maintains and which the user
                 typed. A custom product is never refreshed, so without this
                 its price would silently look as current as a scraped one. -->
            <q-chip
                v-if="product.is_custom"
                dense
                outline
                color="secondary"
                :icon="ICONS.edit"
                class="q-ml-xs"
            >
                Custom
                <BaseTooltip>
                    You added this by hand, so Dora won't refresh it.
                </BaseTooltip>
            </q-chip>
        </q-card-section>

        <q-separator class="q-mt-sm" />
        <!-- Owner 2026-10-15: two cards to a row on a phone. Five 44px targets
             no longer fit a half-width card, so the two everyday actions stay
             on the face and the rest sit behind one overflow (D-004 holds for
             every target that remains). -->
        <q-card-actions class="product-card__actions items-center">
            <ProductLinkButton
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
            <q-space />
            <BaseButton
                variant="icon"
                :icon="ICONS.more_vert"
                :aria-label="`More for ${product.name}`"
                @click.stop
            >
                <q-menu auto-close anchor="bottom right" self="top right">
                    <q-list dense style="min-width: 200px">
                        <q-item clickable @click="emit('toggle-active')">
                            <q-item-section avatar>
                                <q-icon :name="ICONS.search" size="18px" />
                            </q-item-section>
                            <q-item-section>
                                {{ product.is_active ? 'Stop tracking prices' : 'Track prices' }}
                            </q-item-section>
                        </q-item>
                        <q-item clickable @click="emit('watch-price')">
                            <q-item-section avatar>
                                <q-icon :name="ICONS.price_check" size="18px" />
                            </q-item-section>
                            <q-item-section>
                                {{ watchThreshold != null ? 'Change price alert' : 'Alert me on a price drop' }}
                            </q-item-section>
                        </q-item>
                        <q-item clickable @click="emit('price-history')">
                            <q-item-section avatar>
                                <q-icon :name="ICONS.show_chart" size="18px" />
                            </q-item-section>
                            <q-item-section>Price history</q-item-section>
                        </q-item>
                        <q-item clickable @click="emit('pack-count')">
                            <q-item-section avatar>
                                <q-icon :name="ICONS.inventory_2" size="18px" />
                            </q-item-section>
                            <q-item-section>
                                {{ product.pack_count != null ? `Items in pack: ${product.pack_count}` : 'Set items in pack' }}
                            </q-item-section>
                        </q-item>
                        <!-- Owner 2026-10-17: photos for custom products
                             only. An ingested product's picture comes from
                             its source (and the API refuses a change). -->
                        <q-item v-if="product.is_custom" clickable @click="emit('photo')">
                            <q-item-section avatar>
                                <q-icon :name="ICONS.photo_camera" size="18px" />
                            </q-item-section>
                            <q-item-section>
                                {{ product.has_image ? 'Change photo' : 'Add photo' }}
                            </q-item-section>
                        </q-item>
                        <q-separator />
                        <q-item clickable @click="emit('delete')">
                            <q-item-section avatar>
                                <q-icon :name="ICONS.delete_outline" size="18px" color="negative" />
                            </q-item-section>
                            <q-item-section class="text-negative">Delete product</q-item-section>
                        </q-item>
                    </q-list>
                </q-menu>
            </BaseButton>
        </q-card-actions>
    </q-card>
</template>

<script setup lang="ts">
    /** Expanded ("cards") view of a saved product — the richer of the two
     *  modes the owner asked for (D-10), paired with `ProductRow`.
     *
     *  Draws on the companion's own `ProductSearchCard`: a square image with
     *  the discount overlaid, an out-of-stock overlay, name + size, price with
     *  the struck-through was-price, and the store logo. The owner's note was
     *  that Dora's card sat "half way between what exists in the companion app
     *  and a compact row design" — this commits to the companion end, and
     *  `ProductRow` commits to the other.
     */
    import { computed } from 'vue';
    import AddToListButton from 'src/components/AddToListButton.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import DiscountChip from 'src/components/chips/DiscountChip.vue';
    import ProductLinkButton from 'src/components/products/ProductLinkButton.vue';
    import ProductThumb from 'src/components/products/ProductThumb.vue';
    import StoreLogo from 'src/components/StoreLogo.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import { ICONS } from 'src/style/icons';
    import type { Product } from 'src/models/product';
    import { isOnSpecial } from 'src/helpers/offerLogic';
    import { useProductStoreLink } from 'src/composables/useProductStoreLink';

    const props = defineProps<{
        product: Product;
        bulkMode: boolean;
        selected: boolean;
        /** The user's price-watch threshold on this product, if they set one. */
        watchThreshold?: number | null;
    }>();

    const emit = defineEmits<{
        (e: 'toggle-select'): void;
        (e: 'open-stock-item', stockItemId: string): void;
        (e: 'link'): void;
        (e: 'unlink'): void;
        (e: 'toggle-active'): void;
        (e: 'price-history'): void;
        (e: 'watch-price'): void;
        (e: 'photo'): void;
        (e: 'pack-count'): void;
        (e: 'delete'): void;
    }>();

    const hasDiscount = computed(() => isOnSpecial(props.product));

    const {
        isLink: isTopHalfLink, tag: topHalfTag, attrs: topHalfAttrs,
    } = useProductStoreLink(() => props.product, () => props.bulkMode);

    function onTopHalfClick(event: MouseEvent): void {
        // In bulk mode the tap belongs to selection, not navigation.
        if (props.bulkMode) {
            event.preventDefault();
            event.stopPropagation();
            emit('toggle-select');
        }
    }

    function onCardClick(): void {
        if (props.bulkMode) emit('toggle-select');
    }
</script>

<style scoped>
    .product-card {
        transition: outline-color var(--motion-fast) var(--motion-ease), box-shadow var(--motion-fast) var(--motion-ease);
        outline: 2px solid transparent;
        outline-offset: -2px;
    }
    .product-card:hover {
        box-shadow: 0 4px 14px var(--overlay-active);
    }
    .product-card--selected {
        outline-color: var(--q-primary);
    }
    .product-card--inactive {
        opacity: 0.6;
    }

    .product-card__top {
        display: flex;
        flex-direction: column;
        text-decoration: none;
        color: inherit;
        flex: 1 1 auto;
        min-height: 0;
    }
    .product-card__top--linked {
        cursor: pointer;
    }
    .product-card__top--linked:hover .product-card__name {
        text-decoration: underline;
    }
    /* Owner 2026-10-15: a step up from subtitle2, which read small once the
       card stopped spanning the phone's full width. */
    .product-card__name {
        font-size: calc(var(--font-size-md) * 1rem);
        font-weight: 600;
        line-height: 1.3;
    }
    .product-card__watch {
        display: flex;
        align-items: center;
        gap: var(--space-1);
        font-size: calc(var(--font-size-xs) * 1rem);
        color: var(--text-secondary);
    }

    /* `flex: 0 0 auto` keeps the square media out of the card's height
       negotiation: the card is `full-height` and stretches to the tallest in
       its row, and without this the flex layout tries to distribute that
       forced height into a box whose height comes from its own WIDTH
       (`aspect-ratio`). */
    .product-card__media {
        position: relative;
        flex: 0 0 auto;
        aspect-ratio: 1 / 1;
        background: var(--surface-sunken);
    }
    .product-card__discount {
        position: absolute;
        top: var(--space-2);
        left: var(--space-2);
    }
    .product-card__select {
        position: absolute;
        top: var(--space-1);
        right: var(--space-1);
        background: var(--surface-component);
        border-radius: var(--radius-sm);
    }
    .product-card__oos {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        text-align: center;
        padding: var(--space-1) 0;
        font-size: calc(var(--font-size-xs) * 1rem);
        font-weight: 600;
        color: white;
        background: var(--semantic-negative);
    }
    .product-card__was {
        text-decoration: line-through;
    }

    /* One row, no wrapping: a control band that reflows changes the card's
       height, and in a grid of equal-height cards that ripples to every
       sibling. Three 44px targets fit a half-width card at 375px. */
    .product-card__actions {
        flex-wrap: nowrap;
        gap: var(--space-1);
    }

    .ellipsis-2-lines {
        display: -webkit-box;
        -webkit-line-clamp: 2;
        line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
</style>
