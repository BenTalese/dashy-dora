<template>
    <!-- The favourite / cook / add-to-list buttons a recipe card and a compact
         recipe row share (R-001, finalisation 01-R19). Presentational: the
         host page handles each emit. `spread` pushes the cart to the far end
         (the card's footer); the row keeps the buttons together. -->
    <BaseButton
        variant="icon"
        :icon="recipe.is_favourite ? ICONS.favorite : ICONS.favorite_border"
        :color="recipe.is_favourite ? 'negative' : undefined"
        @click.stop="emit('toggle-favourite', recipe.recipe_id)"
    >
        <BaseTooltip>
            {{ recipe.is_favourite ? 'Remove from favourites' : 'Mark favourite' }}
        </BaseTooltip>
    </BaseButton>
    <BaseButton
        v-if="showFilterByIngredients"
        variant="icon"
        :icon="ICONS.filter_list"
        @click.stop="emit('filter-by-ingredients', recipe.recipe_id)"
    >
        <BaseTooltip>Filter stock to this recipe's ingredients</BaseTooltip>
    </BaseButton>
    <BaseButton
        variant="filled-icon"
        :icon="ICONS.chef_hat"
        :color="cookButtonColor"
        @click.stop="emit('cook', recipe.recipe_id)"
    >
        <BaseTooltip>{{ cookButtonTooltip }}</BaseTooltip>
    </BaseButton>
    <q-space v-if="spread" />
    <BaseButton
        variant="icon"
        :icon="cookable === true ? ICONS.add_shopping_cart : ICONS.remove_shopping_cart"
        :color="cookable === false ? 'warning' : undefined"
        :disable="recipe.ingredients.length === 0"
        @click.stop="onAddToList"
    >
        <BaseTooltip>{{ addListTooltip }}</BaseTooltip>
    </BaseButton>
</template>

<script lang="ts" setup>
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { useRecipeDisplay } from 'src/composables/useRecipeDisplay';
    import type { Recipe } from 'src/models/recipe';
    import { ICONS } from 'src/style/icons';

    const props = withDefaults(
        defineProps<{
            recipe: Recipe;
            showFilterByIngredients?: boolean | undefined;
            spread?: boolean | undefined;
        }>(),
        { showFilterByIngredients: false, spread: false },
    );

    const emit = defineEmits<{
        (e: 'cook', recipeId: string): void;
        (e: 'toggle-favourite', recipeId: string): void;
        (e: 'add-missing', recipeId: string, stockItemIds: string[]): void;
        (e: 'add-all-to-list', recipeId: string): void;
        (e: 'filter-by-ingredients', recipeId: string): void;
    }>();

    const {
        missingIds, cookable, cookButtonColor, cookButtonTooltip, addListTooltip,
    } = useRecipeDisplay(() => props.recipe);

    function onAddToList() {
        if (cookable.value) emit('add-all-to-list', props.recipe.recipe_id);
        else emit('add-missing', props.recipe.recipe_id, missingIds.value);
    }
</script>
