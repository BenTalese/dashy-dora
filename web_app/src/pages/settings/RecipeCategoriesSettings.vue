<template>
    <TaxonomyManagerPage
        title="Categories"
        description="The category options shown on recipes. Useful for filtering."
        noun="category"
        noun-plural="categories"
        :load="load"
        :create="create"
        :rename="rename"
        :remove="remove"
    />
</template>

<script lang="ts" setup>
    import TaxonomyManagerPage, { type VocabItem } from 'src/components/settings/TaxonomyManagerPage.vue';
    import CategoryApiService from 'src/services/api/categoryApiService';

    const api = new CategoryApiService();

    const load = async (): Promise<VocabItem[]> =>
        (await api.getAllAsync()).map((c) => ({ id: c.category_id, name: c.name, usage_count: c.recipe_count ?? 0 }));
    const create = (name: string) => api.createAsync({ name });
    const rename = (id: string, name: string) => api.updateAsync(id, { name });
    const remove = (id: string) => api.deleteAsync(id).then(() => undefined);
</script>
