<template>
    <!-- The header's "My products →" link went with every other card's on
         2026-09-08 (owner: *"Remove them all I reckon"*). This card is opt-in
         and products-gated, so it was the easiest one to miss in the sweep —
         noting it here so a future reader doesn't reinstate it as an oversight.
         The nav's own My products entry is the way there. -->
    <DashboardCard :icon="ICONS.trending_down" title="Price drops">
        <CardLoadError
            v-if="failed"
            line="I couldn't check for price drops just now."
            @retry="emit('retry')"
        />
        <ul v-else-if="rows.length > 0" class="dora-deal-list">
            <li v-for="row in rows" :key="row.product_id" class="dora-deal-row">
                <!-- FU-827 / R-045: the image is fetched through the
                     authenticated HTTP client, not a bare `<img src="/api/…">`
                     (which failed silently on a split host and in the Capacitor
                     shell). -->
                <ProductThumb
                    class="dora-deal-img"
                    :product-id="row.product_id"
                    :has-image="row.has_image"
                    :alt="row.name"
                />
                <div class="dora-deal-text">
                    <div class="dora-deal-name">{{ row.name }}</div>
                    <div class="dora-deal-meta">
                        <StoreLogo :name="row.store_name" :height="16" :width="24" inline />{{ row.store_name }}
                        <span v-if="row.linked_stock_item_id">
                            ·
                            <router-link
                                class="dora-text-accent"
                                :to="`/stock/${row.linked_stock_item_id}`"
                            >
                                {{ row.linked_stock_item_name }}
                            </router-link>
                        </span>
                    </div>
                </div>
                <div class="dora-deal-price">
                    <span class="dora-deal-now">{{ formatMoney(row.price_now) }}</span>
                    <span class="dora-deal-was">was {{ formatMoney(row.previous_low) }}</span>
                </div>
                <span class="dora-deal-badge dora-chip--tint dora-chip--tint-negative">
                    {{ row.drop_percent }}% off
                </span>
            </li>
        </ul>
        <div v-else class="dora-empty">
            Nothing at a new low right now.
        </div>
    </DashboardCard>
</template>

<script lang="ts" setup>
    /**
     * Tracked products at a **server-verified new low** (FU-296). The honesty
     * constraint is the whole point of the card: it only claims "price drop"
     * when the price is genuinely lower than anything previously seen, which is
     * why it survived FU-819's cut and "Best deals" — ranked on % off the
     * retailer's own ticket — did not.
     *
     * Extracted from `DashboardPage.vue` (FU-829). Products-gated, so this
     * component is only ever mounted when product data exists (§2.4).
     */
    import { ICONS } from 'src/style/icons';
    import { formatMoney } from 'src/composables/useMoney';
    import DashboardCard from 'src/components/dashboard/DashboardCard.vue';
    import CardLoadError from 'src/components/dashboard/CardLoadError.vue';
    import ProductThumb from 'src/components/products/ProductThumb.vue';
    import StoreLogo from 'src/components/StoreLogo.vue';
    import type { PriceDropRow } from 'src/services/api/reportsApiService';

    withDefaults(
        defineProps<{
            rows: PriceDropRow[];
            failed?: boolean;
        }>(),
        { failed: false },
    );

    const emit = defineEmits<{ (e: 'retry'): void }>();
</script>

<style scoped lang="scss">
    /* Moved with the card (R-027). These were shared with "Best deals" until
       FU-819 cut it, so they belong to this card alone now. The `img` fit rules
       live in `ProductThumb`, which owns the thumbnail's own appearance. */
    .dora-deal-list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
    }
    .dora-deal-row {
        display: grid;
        grid-template-columns: 36px minmax(0, 1fr) auto auto;
        align-items: center;
        gap: var(--space-3);
        padding: var(--space-2) var(--space-3);
        /* A1: nested rows are inset wells inside a card — `--surface-sunken`.
           `--surface-elevated` is for surfaces floating ABOVE a card. */
        background: var(--surface-sunken);
        border-radius: var(--radius-md);
    }
    .dora-deal-text {
        min-width: 0;
    }
    .dora-deal-name {
        font-weight: 600;
        color: var(--text-primary);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .dora-deal-meta {
        font-size: calc(var(--font-size-xs) * 1rem);
        color: var(--text-secondary);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .dora-deal-price {
        text-align: right;
        white-space: nowrap;
    }
    .dora-deal-now {
        font-weight: 700;
        color: var(--text-primary);
    }
    .dora-deal-was {
        font-size: calc(var(--font-size-xs) * 1rem);
        color: var(--text-secondary);
        text-decoration: line-through;
        margin-left: var(--space-1);
    }
    .dora-deal-badge {
        font-weight: 700;
    }

    @media (max-width: 600px) {
        .dora-deal-row {
            grid-template-columns: auto minmax(0, 1fr) auto;
            grid-template-rows: auto auto;
        }
        .dora-deal-price,
        .dora-deal-badge {
            grid-column: 1 / -1;
            text-align: left;
        }
    }
</style>
