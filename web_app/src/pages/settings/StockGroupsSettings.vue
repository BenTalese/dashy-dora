<template>
    <!-- R-001 — stock groups are a name-only vocabulary with a usage tally,
         exactly the shape TaxonomyManagerPage/VocabListEditor already own.
         The page kept a hand-rolled copy of that list until 2026-08-17, which
         is how its row styling drifted from the five Recipe* pages; it is now
         a thin caller like the rest. Only `usageLabel` differs (items, not
         recipes). -->
    <TaxonomyManagerPage
        title="Stock groups"
        description="Tag your stock items so they're easier to filter on the overview."
        :icon="ICONS.tag_multiple"
        noun="stock group"
        noun-plural="stock groups"
        usage-label="item"
        create-hint="&quot;Dairy&quot;, &quot;Snacks&quot;"
        empty-action="Create one to start tagging stock items."
        :load="load"
        :create="create"
        :rename="rename"
        :remove="remove"
    />
</template>

<script lang="ts" setup>
    import { ICONS } from 'src/style/icons';
    import TaxonomyManagerPage, { type VocabItem } from 'src/components/settings/TaxonomyManagerPage.vue';
    import { useStockGroupStore } from 'src/stores/stockGroupStore';

    const stockGroupStore = useStockGroupStore();

    // Always refetched here: the page shows live usage counts.
    const load = async (): Promise<VocabItem[]> => {
        await stockGroupStore.refreshAsync();
        return stockGroupStore.stockGroups.map((g) => ({
            id: g.stock_group_id,
            name: g.name,
            usage_count: g.item_count ?? 0,
        }));
    };
    const create = (name: string) => stockGroupStore.createAsync(name);
    const rename = (id: string, name: string) => stockGroupStore.renameAsync(id, name);
    const remove = (id: string) => stockGroupStore.deleteAsync(id).then(() => undefined);
</script>
