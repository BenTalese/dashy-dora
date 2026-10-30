<template>
    <BaseDialog
        :model-value="modelValue"
        :title="recipe ? 'Edit Recipe' : 'New Recipe'"
        closable
        card-style="width: 480px; max-width: 95vw"
        @update:model-value="$emit('update:modelValue', $event)"
    >
        <q-card-section>
            <q-form @submit.prevent="onSubmit" class="q-gutter-md">
                <FormErrorSummary :message="generalError" />

                <!-- the modal creates a
                     stub — Name + the two primary organisational axes
                     (Cuisine + Category, which drive the overview
                     filters + card grouping) + Collection. Ingredients,
                     steps, image, tools, dietary tags, times, servings,
                     difficulty, time-of-day, instructions all live on
                     the detail page — this dialog closes and navigates
                     there after a create so the user can flesh it out
                     without hunting the list. Edit-from-overview keeps
                     the same shape (a quick rename/reclassify shortcut);
                     deeper edits happen on the detail page. -->
                <q-input
                    outlined
                    label="Name *"
                    v-model="form.name"
                    :error="!!fieldErrors.name"
                    :error-message="fieldErrors.name"
                    @update:model-value="clearField('name')"
                    :rules="[(v: string) => !!v || 'Name is required']"
                    autofocus
                />

                <q-select
                    outlined
                    label="Cuisine"
                    v-model="form.cuisine_id"
                    :options="cuisineOptions"
                    emit-value
                    map-options
                    clearable
                />

                <q-select
                    outlined
                    label="Category"
                    v-model="form.category_id"
                    :options="categoryOptions"
                    emit-value
                    map-options
                    clearable
                />

                <q-select
                    outlined
                    label="Collection"
                    v-model="form.recipe_collection_id"
                    :options="collectionOptions"
                    emit-value
                    map-options
                    clearable
                />
            </q-form>
        </q-card-section>
        <template #actions>
            <BaseButton variant="ghost" label="Cancel" @click="$emit('update:modelValue', false)" />
            <BaseButton
                variant="primary"
                :label="recipe ? 'Save' : 'Create & open'"
                :loading="saving"
                @click="onSubmit"
            />
        </template>
    </BaseDialog>
</template>

<script lang="ts" setup>
    import { storeToRefs } from 'pinia';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import FormErrorSummary from 'src/components/FormErrorSummary.vue';
    import type { Recipe } from 'src/models/recipe';
    import { useFormErrors } from 'src/composables/useFormErrors';
    import { useRecipeStore } from 'src/stores/recipeStore';
    import { useRecipeVocabStore } from 'src/stores/recipeVocabStore';
    import { onMounted, reactive, ref, watch } from 'vue';

    const props = defineProps<{ modelValue: boolean; recipe: Recipe | null }>();
    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
        (e: 'created', recipeId: string): void;
        (e: 'updated'): void;
    }>();

    const recipeStore = useRecipeStore();
    const recipeVocabStore = useRecipeVocabStore();
    const { collectionOptions } = storeToRefs(recipeStore);
    const { cuisineOptions, categoryOptions } = storeToRefs(recipeVocabStore);

    type RecipeForm = {
        name: string;
        cuisine_id: string | null;
        category_id: string | null;
        recipe_collection_id: string | null;
    };

    const emptyForm = (): RecipeForm => ({
        name: '',
        cuisine_id: null,
        category_id: null,
        recipe_collection_id: null,
    });

    const form = reactive<RecipeForm>(emptyForm());
    const saving = ref(false);
    const { fieldErrors, generalError, handleSaveError, reset: resetFormErrors } = useFormErrors();

    function clearField(field: string) {
        if (fieldErrors.value[field]) {
            const next = { ...fieldErrors.value };
            delete next[field];
            fieldErrors.value = next;
        }
    }


    onMounted(() => {
        recipeVocabStore.ensureLoadedAsync().catch(() => undefined);
    });

    watch(
        () => props.modelValue,
        (open) => {
            if (!open) return;
            Object.assign(form, emptyForm());
            resetFormErrors();
            if (props.recipe) {
                form.name = props.recipe.name;
                form.cuisine_id = props.recipe.cuisine_id;
                form.category_id = props.recipe.category_id;
                form.recipe_collection_id = props.recipe.recipe_collection_id;
            }
        }
    );

    async function onSubmit() {
        // Enter can resubmit while the first save is in flight.
        if (saving.value || !form.name.trim()) return;
        saving.value = true;
        resetFormErrors();
        try {
            if (props.recipe) {
                await recipeStore.updateRecipeAsync({
                    recipe_id: props.recipe.recipe_id,
                    name: form.name,
                    cuisine_id: form.cuisine_id,
                    category_id: form.category_id,
                    recipe_collection_id: form.recipe_collection_id,
                });
                emit('updated');
            } else {
                // the modal is a stub-creator; everything else is
                // filled on the detail page. Pass the required-typed fields
                // as their seeded defaults so the create DTO is satisfied.
                const created = await recipeStore.createRecipeAsync({
                    name: form.name,
                    cuisine_id: form.cuisine_id,
                    category_id: form.category_id,
                    recipe_collection_id: form.recipe_collection_id,
                    cook_time_minutes: null,
                    prep_time_minutes: null,
                    difficulty: null,
                    servings: null,
                    time_of_day: null,
                    instructions: null,
                    ingredients: [],
                });
                emit('created', created.recipe_id);
            }
        } catch (err) {
            handleSaveError(err, 'Could not save the recipe. Please review the form.');
        } finally {
            saving.value = false;
        }
    }
</script>
