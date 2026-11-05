<template>
    <TaxonomyManagerPage
        title="Tools"
        description="Kitchen tools recipes can require. Useful for filtering."
        noun="tool"
        noun-plural="tools"
        :load="load"
        :create="create"
        :rename="rename"
        :remove="remove"
    />
</template>

<script lang="ts" setup>
    import TaxonomyManagerPage, { type VocabItem } from 'src/components/settings/TaxonomyManagerPage.vue';
    import ToolApiService from 'src/services/api/toolApiService';

    const api = new ToolApiService();

    const load = async (): Promise<VocabItem[]> =>
        (await api.getAllAsync()).map((t) => ({ id: t.tool_id, name: t.name, usage_count: t.recipe_count ?? 0 }));
    const create = (name: string) => api.createAsync({ name });
    const rename = (id: string, name: string) => api.updateAsync(id, { name });
    const remove = (id: string) => api.deleteAsync(id).then(() => undefined);
</script>
