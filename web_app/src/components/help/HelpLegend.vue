<template>
    <!-- The live stock-row legend inside the "Reading a stock row" guide: it
         draws the household's real level rows, so the guide cannot drift from
         the rows it explains (R-003). The full rules table stays a dialog. -->
    <div class="help-legend">
        <StockRowLegend :levels="stockLevels" />
        <BaseButton
            variant="subtle"
            :icon="ICONS.list_alt"
            label="See the full rules"
            @click="rulesOpen = true"
        />
        <AttentionRulesDialog v-model="rulesOpen" />
    </div>
</template>

<script setup lang="ts">
    import { onMounted, ref } from 'vue';
    import { storeToRefs } from 'pinia';
    import BaseButton from 'src/components/BaseButton.vue';
    import AttentionRulesDialog from 'src/components/help/AttentionRulesDialog.vue';
    import StockRowLegend from 'src/components/stock/StockRowLegend.vue';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { ICONS } from 'src/style/icons';

    const stockLevelStore = useStockLevelStore();
    const { stockLevels } = storeToRefs(stockLevelStore);
    const rulesOpen = ref(false);
    onMounted(() => {
        void stockLevelStore.ensureLoadedAsync();
    });
</script>

<style scoped lang="scss">
    .help-legend {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: var(--space-3);
        margin-top: var(--space-2);
    }
    /* The legend's own top rule doubles the card's; drop it here. */
    .help-legend :deep(.stock-row-legend) {
        margin-top: 0;
        padding-top: 0;
        border-top: 0;
    }
</style>
