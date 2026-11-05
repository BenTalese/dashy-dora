import { useFeatureFlags } from 'src/composables/useFeatureFlags';
import { useRecipeStore } from 'src/stores/recipeStore';

/**
 * After anything that changes what the server computes into a recipe — the
 * nutrition mode, the rating scheme, a dataset import landing — the flag map
 * and the cached recipe list go stale together: the DTO carries no rating
 * while the scheme is 'none', and the complex-mode rollup reads the catalogue.
 * Refreshing only the flags left the chip blank until a page reload (owner
 * 2026-09-09). One function owns the pairing so the next setting that moves a
 * recipe's figures can't miss half of it (FU-901, FU-771).
 */
export function useNutritionSettingsSync() {
    const { refresh: refreshFlags } = useFeatureFlags();
    const recipeStore = useRecipeStore();
    async function syncAfterNutritionChange(): Promise<void> {
        await refreshFlags();
        recipeStore.invalidateRecipes();
    }
    return { syncAfterNutritionChange };
}
