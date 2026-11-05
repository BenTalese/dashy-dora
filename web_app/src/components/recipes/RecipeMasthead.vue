<template>
    <!-- ═══ Masthead — photo, identity, facts ═══════════════════
         One unit replacing the old page's breadcrumb row, heading row,
         toolbar row, hero image and 11-field meta card. -->
    <div class="rn__masthead">
        <!-- Every photo control lives on the photo itself. The page used
             to carry a second, fuller uploader in a disclosure at the
             very bottom — the last place you look for the picture at the
             top. With no photo the tile opens the file picker on the
             first tap; with one it offers Change / Remove first, which
             is what `manual` is for. -->
        <ImageEditTile
            ref="photoTile"
            class="rn__photo"
            :class="{ 'rn__photo--empty': !photoUrl }"
            :label="hasPhoto ? 'Change the recipe photo' : 'Add a recipe photo'"
            shape="rounded"
            fill
            :manual="hasPhoto"
            @activate="photoDialogOpen = true"
            @pick="onPickPhoto"
        >
            <img v-if="photoUrl" :src="photoUrl" alt="" class="rn__photoimg" />
            <div v-else class="rn__photoplaceholder">
                <q-icon :name="ICONS.photo_camera" size="28px" />
                <span>Add a photo</span>
            </div>
        </ImageEditTile>

        <div class="rn__identity">
            <div class="rn__backrow">
                <BaseButton
                    variant="icon"
                    class="dora-text-secondary"
                    :icon="ICONS.arrow_back"
                    to="/cookbook"
                    aria-label="Back to cookbook"
                />
                <h1 v-if="!headerEditing" class="rn__title">{{ form.name || 'Untitled recipe' }}</h1>
                <h1 v-else class="rn__title rn__title--edit">
                    <q-input
                        v-model="form.name"
                        dense
                        outlined
                        autofocus
                        maxlength="255"
                        aria-label="Recipe name"
                        @update:model-value="markDirty"
                    />
                </h1>
                <BaseButton
                    class="rn__pencil"
                    :variant="headerEditing ? 'secondary' : 'icon'"
                    :icon="headerEditing ? ICONS.check : ICONS.edit"
                    :label="headerEditing ? 'Done' : undefined"
                    :aria-label="headerEditing ? 'Finish editing the recipe details' : 'Edit the recipe details'"
                    :aria-pressed="headerEditing"
                    :loading="headerEditing && saveState === 'saving'"
                    @click="onToggleHeaderEdit"
                >
                    <BaseTooltip v-if="!headerEditing">Edit the recipe details</BaseTooltip>
                </BaseButton>
            </div>

            <!-- Read: a sentence. Edit: three fields on the same grid
                 the facts use, so the block keeps its shape across the
                 flip instead of every control resizing to its own
                 longest option (R-055 / ADR-051). -->
            <!-- Owner feedback 2026-08-26 — every axis in this block
                 already has a glyph on the cookbook page's filter row,
                 and the header was the one place naming them in bare
                 words. Same icon, same meaning, both modes (D-005). The
                 "·" separators went with them: a leading glyph already
                 marks where one fact stops and the next starts, and
                 dot-plus-icon reads as punctuation noise. -->
            <div v-if="!headerEditing" class="rn__eyebrow">
                <span class="rn__brow">
                    <q-icon :name="ICONS.collection" size="15px" />
                    {{ collectionName || 'No collection' }}
                </span>
                <span class="rn__brow">
                    <q-icon :name="ICONS.public" size="15px" />
                    {{ cuisineName || 'Any cuisine' }}
                </span>
                <span class="rn__brow">
                    <q-icon :name="ICONS.category" size="15px" />
                    {{ categoryName || 'No category' }}
                </span>
            </div>
            <div v-else class="rn__fields">
                <BaseSelect
                    v-model="form.recipe_collection_id"
                    label="Collection"
                    :options="collectionOptions"
                    emit-value map-options clearable
                    @update:model-value="markDirty"
                >
                    <template #prepend><q-icon :name="ICONS.collection" size="18px" /></template>
                </BaseSelect>
                <BaseSelect
                    v-model="form.cuisine_id"
                    label="Cuisine"
                    :options="cuisineOptions"
                    emit-value map-options clearable
                    @update:model-value="markDirty"
                >
                    <template #prepend><q-icon :name="ICONS.public" size="18px" /></template>
                </BaseSelect>
                <BaseSelect
                    v-model="form.category_id"
                    label="Category"
                    :options="categoryOptions"
                    emit-value map-options clearable
                    @update:model-value="markDirty"
                >
                    <template #prepend><q-icon :name="ICONS.category" size="18px" /></template>
                </BaseSelect>
            </div>

            <div v-if="!headerEditing" class="rn__facts">
                <div class="rn__fact">
                    <span class="rn__factk"><q-icon :name="ICONS.people" size="14px" />Serves</span>
                    <span class="rn__factv">{{ form.servings ?? '–' }}</span>
                </div>
                <div class="rn__fact">
                    <span class="rn__factk"><q-icon :name="ICONS.prepTime" size="14px" />Prep</span>
                    <span class="rn__factv">{{ form.prep_time_minutes ? form.prep_time_minutes + ' min' : '–' }}</span>
                </div>
                <div class="rn__fact">
                    <span class="rn__factk"><q-icon :name="ICONS.cookTime" size="14px" />Cook</span>
                    <span class="rn__factv">{{ form.cook_time_minutes ? form.cook_time_minutes + ' min' : '–' }}</span>
                </div>
                <div v-if="totalTimeMinutes !== null" class="rn__fact">
                    <span class="rn__factk"><q-icon :name="ICONS.timer" size="14px" />Total</span>
                    <span class="rn__factv">{{ totalTimeMinutes }} min</span>
                </div>
                <div class="rn__fact">
                    <span class="rn__factk"><q-icon :name="ICONS.difficulty" size="14px" />Difficulty</span>
                    <span class="rn__factv">{{ form.difficulty || '–' }}</span>
                </div>
                <div class="rn__fact">
                    <span class="rn__factk"><q-icon :name="ICONS.schedule" size="14px" />When</span>
                    <span class="rn__factv">{{ form.time_of_day || '–' }}</span>
                </div>
                <div v-if="headlineKcal !== null" class="rn__fact">
                    <span class="rn__factk">
                        <q-icon :name="ICONS.local_fire_department" size="14px" />Per serving
                    </span>
                    <span class="rn__factv">{{ headlineKcal }} kcal</span>
                </div>
            </div>
            <!-- Total and Per serving are derived, so they have no field
                 here — there is nothing to type into them. -->
            <div v-else class="rn__fields">
                <q-input
                    v-model.number="form.servings"
                    dense outlined type="number" min="1" label="Serves"
                    @update:model-value="markDirty"
                >
                    <template #prepend><q-icon :name="ICONS.people" size="18px" /></template>
                </q-input>
                <q-input
                    v-model.number="form.prep_time_minutes"
                    dense outlined type="number" min="0" label="Prep (min)"
                    @update:model-value="markDirty"
                >
                    <template #prepend><q-icon :name="ICONS.prepTime" size="18px" /></template>
                </q-input>
                <q-input
                    v-model.number="form.cook_time_minutes"
                    dense outlined type="number" min="0" label="Cook (min)"
                    @update:model-value="markDirty"
                >
                    <template #prepend><q-icon :name="ICONS.cookTime" size="18px" /></template>
                </q-input>
                <BaseSelect
                    v-model="form.difficulty"
                    label="Difficulty"
                    :options="DIFFICULTY_OPTIONS"
                    clearable
                    @update:model-value="markDirty"
                >
                    <template #prepend><q-icon :name="ICONS.difficulty" size="18px" /></template>
                </BaseSelect>
                <BaseSelect
                    v-model="form.time_of_day"
                    label="When"
                    :options="timeOfDayOptions"
                    clearable
                    @update:model-value="markDirty"
                >
                    <template #prepend><q-icon :name="ICONS.schedule" size="18px" /></template>
                </BaseSelect>
            </div>
        </div>

        <!-- No preview here: you opened this by tapping the photo, so you have
             just looked at it. Two buttons, nothing else. -->
        <BaseDialog v-model="photoDialogOpen" title="Recipe photo" closable card-style="min-width: 300px">
            <q-card-section class="rn__photoacts">
                <BaseButton
                    variant="primary"
                    :icon="ICONS.photo_camera"
                    label="Change photo"
                    @click="onChangePhoto"
                />
                <BaseButton
                    variant="danger-ghost"
                    :icon="ICONS.delete"
                    label="Remove photo"
                    @click="onRemovePhoto"
                />
            </q-card-section>
        </BaseDialog>
    </div>
</template>

<script lang="ts" setup>
    /**
     * The recipe page's masthead: the photo (and every photo control), the
     * name, the collection / cuisine / category line and the facts row, with
     * one pencil that flips the whole block between reading and editing in
     * place (R-055 / ADR-051). Split out of `RecipeDetailPage` (FU-934); the
     * form, the dirty flag and the save are the page's, via `useRecipeDetail`.
     */
    import { computed, ref } from 'vue';
    import { storeToRefs } from 'pinia';

    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import ImageEditTile from 'src/components/ImageEditTile.vue';

    import { ICONS } from 'src/style/icons';
    import { totalMinutes } from 'src/helpers/recipeTime';
    import { DIFFICULTY_OPTIONS } from 'src/helpers/recipeVocabulary';
    import { useNutritionMode } from 'src/composables/useNutritionMode';
    import { useRecipeDetail } from 'src/composables/useRecipeDetail';
    import { recipeImagePath } from 'src/services/api/recipeApiService';
    import { useAuthedImage } from 'src/composables/useAuthedImage';
    import { useRecipeStore } from 'src/stores/recipeStore';
    import { useRecipeVocabStore } from 'src/stores/recipeVocabStore';
    import { useMealSlotStore } from 'src/stores/mealSlotStore';

    const {
        recipe, form, saveState, headerEditing, toggleEditRegion, markDirty,
        imageDirty, imageVersion,
    } = useRecipeDetail();

    const { recipeCollections, collectionOptions } = storeToRefs(useRecipeStore());
    const { cuisines, categories, cuisineOptions, categoryOptions } = storeToRefs(useRecipeVocabStore());
    // `time_of_day` reads the household's own meal-slot names.
    const { slotNamesOrDefault: timeOfDayOptions } = storeToRefs(useMealSlotStore());
    const { isComplex } = useNutritionMode();

    const onToggleHeaderEdit = () => toggleEditRegion(headerEditing);

    // ── Derived display ─────────────────────────────────────────────────
    const collectionName = computed(
        () => recipeCollections.value.find((c) => c.recipe_collection_id === form.recipe_collection_id)?.name ?? '',
    );
    const cuisineName = computed(() => cuisines.value.find((c) => c.cuisine_id === form.cuisine_id)?.name ?? '');
    const categoryName = computed(() => categories.value.find((c) => c.category_id === form.category_id)?.name ?? '');

    const totalTimeMinutes = computed(() => totalMinutes(form.prep_time_minutes, form.cook_time_minutes));
    const headlineKcal = computed(() => {
        if (isComplex.value && recipe.value?.nutrition?.kcal) return Math.round(recipe.value.nutrition.kcal);
        return form.kcal ?? null;
    });

    // ── Photo ───────────────────────────────────────────────────────────
    // Every photo control lives on the photo itself, so the tile is the only
    // uploader on the page; the dialog just picks which of the two things you
    // meant when a photo already exists.
    const photoTile = ref<InstanceType<typeof ImageEditTile> | null>(null);
    const photoDialogOpen = ref(false);

    // The saved photo through the HTTP client (R-045, FU-931); a photo picked
    // in this edit shows its data URL until it is saved.
    const savedPhoto = useAuthedImage(() => (
        !imageDirty.value && recipe.value?.has_image
            ? recipeImagePath(recipe.value.recipe_id, imageVersion.value)
            : null
    ));
    const photoUrl = computed(() => (imageDirty.value ? form.image : savedPhoto.value));
    // Owner call 2026-08-29 — a photo that exists is a photo that renders. Read
    // from the record rather than the fetched bytes, so the tile doesn't
    // flash its empty "add a photo" face while the saved photo loads.
    const hasPhoto = computed(() => (
        imageDirty.value ? form.image !== null : !!recipe.value?.has_image
    ));

    function onPickPhoto(image: { dataUrl: string }) {
        form.image = image.dataUrl;
        imageDirty.value = true;
        markDirty();
    }
    function onChangePhoto() {
        photoDialogOpen.value = false;
        photoTile.value?.openPicker();
    }
    function onRemovePhoto() {
        photoDialogOpen.value = false;
        form.image = null;
        imageDirty.value = true;
        markDirty();
    }
</script>

<style scoped lang="scss">
    // `.rn__masthead`'s grid is shared with the page's loading skeleton.
    @use '../../css/recipeDetail';

    /* No display face. The page shipped with Fraunces on the title and the
       section labels; the owner's verdict 2026-08-24 was that it "just
       doesn't feel like the same app" — which is the right call, because a
       page-specific typeface is a second brand nobody asked for. Everything
       here inherits the user's chosen font (Settings → Appearance,
       themeService FONT_FAMILY_CSS), like every other page. */
    .rn__photo {
        width: 100%;
        aspect-ratio: 1 / 1;
        border-radius: var(--radius-lg);
        overflow: hidden;
        border: 1px solid var(--border-default);
    }
    .rn__photoimg { width: 100%; height: 100%; object-fit: cover; display: block; }
    .rn__photoplaceholder {
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        gap: var(--space-2);
        width: 100%; height: 100%;
        color: var(--text-muted);
        font-size: var(--font-size-sm);
    }
    .rn__photoacts { display: flex; flex-direction: column; gap: var(--space-2); }
    /* The empty state is the tile itself now, not a separate <button>, so this
       only has to tint the well — `.rn__photoplaceholder` centres the content. */
    .rn__photo--empty { background: var(--surface-sunken); }
    .rn__photo--empty:hover { border-color: var(--brand-primary); }

    .rn__identity { min-width: 0; }
    .rn__pencil { flex: none; }

    /* One grid for both halves of the edit face, so a select is as wide as
       the cell it sits in rather than as wide as its longest option. */
    .rn__fields {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: var(--space-3);
        margin-top: var(--space-3);
    }
    .rn__backrow { display: flex; align-items: center; gap: var(--space-2); }
    .rn__title {
        font-size: 2rem;
        font-weight: 600;
        line-height: 1.15;
        letter-spacing: -0.01em;
        margin: 0;
        /* The h1 sits in a flex row; without `flex: 1` it is sized to its own
           text and wraps with half the row still empty. `text-wrap: balance`
           made that worse by splitting evenly across the lines it chose, so it
           goes too — the title should fill the row and only wrap when it must. */
        flex: 1;
        min-width: 0;
    }
    /* In edit mode the h1 is a wrapper around an input, so it drops the
       display sizing it uses when it is actually a heading. */
    .rn__title--edit { font-size: 1rem; font-weight: 400; }
    .rn__eyebrow {
        display: flex; flex-wrap: wrap; align-items: center;
        /* Wider than the old dot-separated gap — the glyphs are doing the
           separating now, so the space between facts has to read as bigger
           than the space inside one. */
        gap: var(--space-2) var(--space-4);
        margin-top: var(--space-2);
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
    }
    .rn__brow { display: inline-flex; align-items: center; gap: var(--space-1); }

    .rn__facts {
        display: flex; flex-wrap: wrap;
        gap: var(--space-2) var(--space-6);
        margin-top: var(--space-4);
    }
    .rn__fact { display: flex; flex-direction: column; gap: 2px; min-width: 60px; flex: 0 0 auto; }
    .rn__factk {
        display: inline-flex; align-items: center; gap: var(--space-1);
        font-size: var(--font-size-xs); font-weight: 700; letter-spacing: 0.07em;
        text-transform: uppercase; color: var(--text-muted);
    }
    /* The letter-spacing above is set for capitals; on the glyph it just
       pushes it off its word. */
    .rn__factk .q-icon { letter-spacing: normal; }
    .rn__factv { font-size: 1rem; font-weight: 600; font-variant-numeric: tabular-nums; }

    /* ── Phone ────────────────────────────────────────────────────────── */
    @media (max-width: 1023px) {
        .rn__photo { aspect-ratio: 16 / 9; }
        .rn__title { font-size: 1.5rem; }
        /* One line that scrolls, rather than three rows of facts pushing the
           method off the first screen (owner feedback 2026-08-24; D-011 —
           wide content scrolls inside its own container, never the page). */
        .rn__facts {
            flex-wrap: nowrap;
            overflow-x: auto;
            scrollbar-width: none;
        }
        .rn__facts::-webkit-scrollbar { display: none; }
    }
</style>
