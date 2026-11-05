<template>
    <!-- ═══ Details — everything administrative ═════════════════
         Owner feedback 2026-08-27 — these panels' labels read as body
         text sitting on top of body text, so they now wear the same
         uppercase section title Ingredients and Method wear, and the
         captions are gone with them: a caption that lists what is
         inside a drawer you are about to open is a summary of a thing
         one tap away. Tools left this list entirely — they belong to
         the method now, derived from the steps that use them. -->
    <div v-if="recipe" class="rn__details">
        <q-expansion-item v-model="detailOpen.extra" dense-toggle>
            <template #header>
                <q-item-section>
                    <h2 class="rn__sectitle">Additional details</h2>
                </q-item-section>
            </template>
            <div class="rn__disc">
                <!-- Owner feedback 2026-08-29 — the nutrition drawer's
                     card treatment, shared via `RecipeInfoCard`, so
                     the three details panels read as one family. -->
                <RecipeInfoCard :icon="ICONS.notes">
                    <BaseSelect
                        v-model="form.dietary_tag_ids"
                        label="Dietary tags"
                        :options="dietaryTagOptions"
                        emit-value map-options multiple use-chips clearable
                        class="q-mb-sm"
                        @update:model-value="markDirty"
                    />
                    <q-input
                        v-model="form.source"
                        dense outlined clearable
                        class="q-mb-sm"
                        label="Source URL"
                        @update:model-value="markDirty"
                    />
                    <q-input
                        v-model="form.notes"
                        dense outlined type="textarea" autogrow
                        label="Notes"
                        @update:model-value="markDirty"
                    />
                </RecipeInfoCard>
            </div>
        </q-expansion-item>

        <q-expansion-item
            v-if="isComplex && recipe.nutrition"
            v-model="detailOpen.nutrition"
            dense-toggle
        >
            <!-- Owner feedback 2026-09-08: no caption at all. The
                 figure and its basis are one tap away and are stated
                 properly there; restating the number on the collapsed
                 row only raises the question of what it's per. -->
            <template #header>
                <q-item-section>
                    <div class="row items-center no-wrap">
                        <h2 class="rn__sectitle">Nutrition</h2>
                        <!-- .stop: a tap on the (?) opens the guide, not the drawer. -->
                        <span @click.stop><HelpHint topic="Nutrition: off, simple, complex" /></span>
                    </div>
                </q-item-section>
            </template>
            <div class="rn__disc">
                <!-- Linking a food from the gap list changes the
                     server's rollup, so the recipe is re-fetched
                     rather than patched in place (R-003). -->
                <RecipeNutritionCard
                    :nutrition="recipe.nutrition"
                    @linked="loadRecipe"
                    @edit-ingredient="onEditGapIngredient"
                />
            </div>
        </q-expansion-item>

        <!-- The simple-mode "Calories" drawer went to the masthead's edit
             face (FU-735): per-serving kcal is a masthead fact, so it is
             typed where the other facts are, not in a second place. -->

        <!-- Version information. Renders even for a singleton, because
             created/updated are facts about every recipe. -->
        <q-expansion-item v-model="detailOpen.versions" dense-toggle>
            <template #header>
                <q-item-section>
                    <div class="row items-center no-wrap">
                        <h2 class="rn__sectitle">Version information</h2>
                        <!-- .stop: a tap on the (?) opens the guide, not the drawer. -->
                        <span @click.stop><HelpHint topic="Versions of a recipe" /></span>
                    </div>
                </q-item-section>
            </template>
            <div class="rn__disc">
                <RecipeInfoCard :icon="ICONS.history">
                    <div class="rn__vfacts">
                        <div class="rn__vfact">
                            <span class="rn__cellk">Created</span>
                            <span>{{ recipe.created_at ? formatDate(recipe.created_at) : 'Unknown' }}</span>
                        </div>
                        <div class="rn__vfact">
                            <span class="rn__cellk">Last updated</span>
                            <span>
                                {{ recipe.updated_at
                                    ? formatDate(recipe.updated_at)
                                    : '–' }}
                            </span>
                        </div>
                    </div>

                    <!-- The count is a pill on the sub-heading rather than
                         a caption on the panel above, and the explanation
                         of what "New version" does is gone: the button is
                         right here now, which is a better explanation than
                         the sentence was (owner feedback 2026-08-27). -->
                    <div class="rn__vhead">
                        <span class="rn__discsub">Versions of this recipe</span>
                        <q-badge rounded class="rn__vcount" :label="versionSiblings.length + 1" />
                        <BaseButton
                            variant="ghost"
                            dense
                            class="rn__vnew"
                            :icon="ICONS.content_copy"
                            label="New version"
                            aria-label="Make a new version of this recipe"
                            :loading="newVersionLoading"
                            @click="onNewVersion"
                        >
                            <BaseTooltip>
                                Makes a copy you can change without losing this one.
                            </BaseTooltip>
                        </BaseButton>
                    </div>

                    <q-list v-if="versionSiblings.length > 0" dense separator>
                        <q-item class="rn__vthis">
                            <q-item-section>
                                <q-item-label>{{ recipe.name }}</q-item-label>
                                <q-item-label caption>
                                    {{ recipe.created_at ? `Created ${formatDate(recipe.created_at)}` : 'Created date unknown' }}
                                </q-item-label>
                            </q-item-section>
                            <q-item-section side>
                                <q-badge outline color="primary" label="You're here" />
                            </q-item-section>
                        </q-item>
                        <q-item
                            v-for="sib in versionSiblings"
                            :key="sib.recipe_id"
                            clickable
                            @click="goToSibling(sib.recipe_id)"
                        >
                            <q-item-section>
                                <q-item-label>{{ sib.name }}</q-item-label>
                                <q-item-label caption>
                                    {{ sib.created_at ? `Created ${formatDate(sib.created_at)}` : 'Created date unknown' }}
                                </q-item-label>
                            </q-item-section>
                            <q-item-section side>
                                <q-icon :name="ICONS.chevron_right" />
                            </q-item-section>
                        </q-item>
                    </q-list>
                </RecipeInfoCard>
            </div>
        </q-expansion-item>
    </div>
</template>

<script lang="ts" setup>
    import HelpHint from 'src/components/help/HelpHint.vue';
    /**
     * The recipe page's details drawers: additional details (dietary tags,
     * source, notes), nutrition (complex mode) or calories (simple mode), and
     * version information with the new-version action and sibling list.
     * Split out of `RecipeDetailPage` (FU-934); the form, dirty flag, reload
     * and new-version action are the page's, via `useRecipeDetail`.
     */
    import { computed, reactive } from 'vue';
    import { useRouter } from 'vue-router';
    import { storeToRefs } from 'pinia';

    import BaseButton from 'src/components/BaseButton.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import RecipeInfoCard from 'src/components/recipes/RecipeInfoCard.vue';
    import RecipeNutritionCard from 'src/components/recipes/RecipeNutritionCard.vue';

    import { ICONS } from 'src/style/icons';
    import { formatDate } from 'src/composables/useDateFormat';
    import { useNutritionMode } from 'src/composables/useNutritionMode';
    import { useRecipeDetail } from 'src/composables/useRecipeDetail';
    import { useRecipeVocabStore } from 'src/stores/recipeVocabStore';
    import type { RecipeNutritionGapIngredient } from 'src/models/recipe';

    const router = useRouter();
    const {
        recipe, form, markDirty, loadRecipe, newVersionLoading, onNewVersion, requestIngredientEdit,
    } = useRecipeDetail();
    const { dietaryTagOptions } = storeToRefs(useRecipeVocabStore());
    const { isComplex } = useNutritionMode();

    // ── Captions for the collapsed Details rows ─────────────────────────
    // `extraCaption` and `versionsCaption` went with the captions they fed
    // (owner feedback 2026-08-27): a caption listing what is inside a drawer
    // one tap away is a summary of nothing. The version *count* survived as a
    // pill inside the panel, next to the list it counts.
    // `nutritionCaption` went with the caption it fed (owner, 2026-09-08) — see
    // the panel's header comment.
    const detailOpen = reactive({
        extra: false, nutrition: false, versions: false,
    });

    /** FU-895 — a nutrition gap fixed on the ingredient row: the server
     *  names the row (an existing row's client id is its recipe_ingredient_id),
     *  so hand it to the rail's editor. A row edited away since the rollup
     *  just opens the list. */
    function onEditGapIngredient(gap: RecipeNutritionGapIngredient) {
        const row = form.ingredients.find((r) => r.client_id === gap.recipe_ingredient_id);
        requestIngredientEdit(row?.client_id ?? null);
    }

    const versionSiblings = computed(() => recipe.value?.version_siblings ?? []);

    function goToSibling(id: string) {
        void router.push(`/cookbook/${id}`);
    }
</script>

<style scoped lang="scss">
    // `.rn__sectitle` / `.rn__seccount` (the heading the rest of the page
    // wears) and `.rn__cellk` (the status strip's key label) are shared.
    @use '../../css/recipeDetail';

    .rn__details { margin-top: var(--space-8); border-top: 1px solid var(--divider); }
    /* The expansion headers wear the Ingredients/Method treatment now, so the
       page has one voice for "this is a section" (owner feedback 2026-08-27).
       Quasar's own header padding stays; only the label changes. */
    .rn__details :deep(.q-expansion-item__toggle-icon) { color: var(--text-muted); }
    .rn__disc { padding: var(--space-3) var(--space-2) var(--space-4); }
    .rn__vfacts {
        display: flex; flex-wrap: wrap; gap: var(--space-2) var(--space-6);
        margin-bottom: var(--space-3);
    }
    .rn__vfact { display: flex; flex-direction: column; gap: 2px; }
    .rn__vthis { background: var(--surface-sunken); }
    /* The count is a pill beside the list it counts, and "New version" is a
       button in the panel that talks about versions rather than only an icon
       in the page-wide action row (owner feedback 2026-08-27). */
    .rn__vhead {
        display: flex; align-items: center; gap: var(--space-2);
        margin: var(--space-5) 0 var(--space-2);
        flex-wrap: wrap;
    }
    .rn__vhead .rn__discsub { margin: 0; }
    .rn__vcount {
        background: var(--surface-sunken);
        color: var(--text-secondary);
        font-weight: 700;
        font-variant-numeric: tabular-nums;
    }
    .rn__vnew { margin-left: auto; }

    .rn__discsub {
        font-size: var(--font-size-xs); font-weight: 700; letter-spacing: 0.06em;
        text-transform: uppercase; color: var(--text-muted);
        margin: var(--space-5) 0 var(--space-2);
    }
</style>
