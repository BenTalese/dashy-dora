<template>
    <TaxonomyManagerPage
        title="Collections"
        description="Your own groupings for recipes. Pick one on a recipe, then filter the cookbook by it."
        noun="collection"
        noun-plural="collections"
        create-hint='"Weeknight dinners", "Baking"'
        :load="load"
        :create="create"
        :rename="rename"
        :remove="remove"
    />
</template>

<script lang="ts" setup>
    /*
     * Create, rename and delete recipe collections. The API and the store
     * have had the three writes since collections shipped; nothing in the
     * app called them, so a collection could be picked but never made
     * (owner 2026-11-16).
     *
     * Everything goes through the recipe store, not the API service: the
     * cookbook's filter and the recipe page's picker read the store's list,
     * and a recipe carries its collection's name, so a rename or delete also
     * marks the recipe list stale.
     */
    import TaxonomyManagerPage, { type VocabItem } from 'src/components/settings/TaxonomyManagerPage.vue';
    import { useRecipeStore } from 'src/stores/recipeStore';

    const recipeStore = useRecipeStore();

    const load = async (): Promise<VocabItem[]> => {
        await recipeStore.getRecipeCollectionsAsync();
        return recipeStore.recipeCollections.map((c) => ({
            id: c.recipe_collection_id,
            name: c.name,
            usage_count: c.recipe_count ?? 0,
        }));
    };
    const create = (name: string) => recipeStore.createRecipeCollectionAsync({ name });
    const rename = async (id: string, name: string) => {
        await recipeStore.updateRecipeCollectionAsync({ recipe_collection_id: id, name });
        recipeStore.invalidateRecipes();
    };
    const remove = async (id: string) => {
        await recipeStore.deleteRecipeCollectionAsync(id);
        recipeStore.invalidateRecipes();
    };
</script>
