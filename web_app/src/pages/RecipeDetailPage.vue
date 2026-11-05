<template>
    <q-page padding class="rn">
        <!-- Loading shell. Mirrors the real layout (D-007) rather than
             announcing itself in words. -->
        <div v-if="loading && !recipe">
            <div class="rn__masthead">
                <AppSkeleton type="rect" width="100%" height="200px" />
                <div>
                    <AppSkeleton type="line" width="60%" height="2rem" class="q-mb-sm" />
                    <AppSkeleton type="line" width="40%" height="1rem" />
                </div>
            </div>
            <AppSkeleton type="rect" width="100%" height="64px" class="q-mt-md" />
            <AppSkeleton type="rect" width="100%" height="320px" class="q-mt-md" />
        </div>

        <!-- Load failed (QA2-19): a heading in Dora's words and a way back,
             never the server's raw string on its own. The ref id stays as
             small print for a bug report. -->
        <div v-else-if="loadError" class="text-center dora-text-muted q-py-xl" role="alert">
            <q-icon :name="ICONS.recipe" size="60px" class="q-mb-sm" />
            <h1 class="text-h6 q-my-none">{{ loadError.heading }}</h1>
            <div v-if="loadError.detail" class="q-mt-xs text-caption">{{ loadError.detail }}</div>
            <div class="q-mt-md row justify-center q-gutter-sm">
                <BaseButton variant="primary" :icon="ICONS.arrow_back" label="Back to cookbook" to="/cookbook" />
                <BaseButton v-if="loadError.retry" variant="secondary" label="Retry" @click="loadRecipe" />
            </div>
        </div>

        <template v-else-if="recipe">
            <RecipeMasthead />

            <!-- ═══ Actions — their own full-width row ═══════════════════
                 Save and Discard only exist while there is something to save,
                 so a recipe being *read* still leads with Cook mode. While
                 they're present Save is the primary and Cook mode steps back —
                 two primaries in one row is no primary at all. -->
            <div class="rn__actions">
                <!-- Icon-only on a phone, like every other button in this
                     row (owner feedback 2026-08-27) — it was the one that kept
                     its label, which is what pushed the rest off-screen. -->
                <BaseButton
                    v-if="dirty"
                    variant="primary"
                    :icon="ICONS.save"
                    :label="compact ? undefined : 'Save'"
                    aria-label="Save changes"
                    :loading="saveState === 'saving'"
                    :disable="!canSave"
                    @click="onSave"
                >
                    <BaseTooltip v-if="compact">Save changes</BaseTooltip>
                </BaseButton>
                <BaseButton
                    v-if="dirty"
                    variant="ghost"
                    :icon="ICONS.undo"
                    :label="compact ? undefined : 'Discard'"
                    aria-label="Discard changes"
                    :disable="saveState === 'saving'"
                    @click="onDiscard"
                >
                    <BaseTooltip v-if="compact">Discard changes</BaseTooltip>
                </BaseButton>
                <BaseButton
                    :variant="dirty ? 'secondary' : 'primary'"
                    :icon="ICONS.chef_hat"
                    :label="compact ? undefined : 'Cook mode'"
                    aria-label="Cook mode"
                    @click="onStartCookMode"
                >
                    <BaseTooltip v-if="compact">Cook mode</BaseTooltip>
                </BaseButton>
                <BaseButton
                    variant="ghost"
                    :icon="recipe.is_favourite ? 'favorite' : 'favorite_border'"
                    :label="compact ? undefined : (recipe.is_favourite ? 'Favourited' : 'Favourite')"
                    :class="{ 'text-negative': recipe.is_favourite }"
                    :aria-label="recipe.is_favourite ? 'Remove from favourites' : 'Add to favourites'"
                    @click="onToggleFavourite"
                >
                    <BaseTooltip v-if="compact">{{ recipe.is_favourite ? 'Favourited' : 'Favourite' }}</BaseTooltip>
                </BaseButton>
                <BaseButton
                    variant="ghost"
                    :icon="ICONS.content_copy"
                    :label="compact ? undefined : 'New version'"
                    aria-label="New version"
                    :loading="newVersionLoading"
                    @click="onNewVersion"
                >
                    <BaseTooltip v-if="compact">New version</BaseTooltip>
                </BaseButton>
                <BaseButton
                    variant="ghost"
                    :icon="ICONS.print"
                    :label="compact ? undefined : 'Print'"
                    aria-label="Print"
                    @click="onPrint"
                >
                    <BaseTooltip v-if="compact">Print</BaseTooltip>
                </BaseButton>
                <BaseButton
                    variant="danger-ghost"
                    class="rn__delete"
                    :icon="ICONS.delete"
                    :label="compact ? undefined : 'Delete'"
                    aria-label="Delete recipe"
                    @click="onDelete"
                >
                    <BaseTooltip v-if="compact">Delete recipe</BaseTooltip>
                </BaseButton>
            </div>

            <RecipeStatusStrip />

            <!-- ═══ Body — ingredients rail + method ════════════════════ -->
            <div class="rn__body">
                <RecipeIngredientRail />

                <section aria-labelledby="rnMet">
                    <!-- Owner feedback 2026-08-27, three asks with one answer:
                         the step-style switch and the pencil belong *in* the
                         heading rather than on a row of their own below it;
                         the method should be read-only until the pencil is
                         pressed; and pressing it should swap the block in
                         place rather than open a dialog. The style switch only
                         renders while editing, because picking how the method
                         is stored is an edit — a reader has nothing to do with
                         it, and a control you can't use is a control you have
                         to read past. -->
                    <div class="rn__sechead">
                        <!-- Owner feedback 2026-09-08: the step/photo count came
                             off the heading. The steps are numbered on screen
                             directly below it, so the count restated something
                             the reader can already see. -->
                        <h2 class="rn__sectitle" id="rnMet">Method</h2>
                        <HelpHint topic="Three ways to write a method" />
                        <BaseSegmented
                            v-if="methodEditing"
                            v-model="form.steps_mode"
                            dense
                            :spread="$q.screen.lt.md"
                            class="rn__modes"
                            aria-label="Step style"
                            :options="[
                                { label: 'Structured', value: 'structured' },
                                { label: 'Free text', value: 'freeform' },
                                { label: 'Photos', value: 'image' },
                            ]"
                            @update:model-value="markDirty"
                        />
                        <BaseButton
                            class="rn__secedit"
                            :variant="methodEditing ? 'secondary' : 'icon'"
                            dense
                            :icon="methodEditing ? ICONS.check : ICONS.edit"
                            :label="methodEditing ? 'Done' : undefined"
                            :aria-label="methodEditing ? 'Finish editing the method' : methodEditLabel"
                            :aria-pressed="methodEditing"
                            :loading="methodEditing && saveState === 'saving'"
                            @click="onToggleMethodEdit"
                        >
                            <BaseTooltip v-if="!methodEditing">{{ methodEditLabel }}</BaseTooltip>
                        </BaseButton>
                    </div>

                    <div class="rn__pane">
                        <!-- Structured - the only mode that can tie a step to
                             its ingredients, because it's the only one that
                             stores the link. Both faces live in one component
                             so the geometry can't drift between them. -->
                        <RecipeStructuredMethod
                            v-if="form.steps_mode === 'structured'"
                            :steps="form.steps"
                            :editing="methodEditing"
                            :ingredient-options="ingredientOptions"
                            :tool-options="toolOptions"
                            :section-options="sectionOptions"
                            :selected-step-id="selectedStepId"
                            :highlighted-step-ids="highlightedStepIds"
                            :show-empty-errors="stepErrorsShown"
                            @update:steps="onStepsChanged"
                            @update:selected-step-id="onSelectStep"
                        />

                        <!-- Free text - one block. Read it as paragraphs; edit
                             it as the one field it actually is. -->
                        <template v-else-if="form.steps_mode === 'freeform'">
                            <q-input
                                v-if="methodEditing"
                                v-model="form.instructions"
                                type="textarea"
                                outlined
                                autogrow
                                autofocus
                                label="Instructions"
                                hint="Separate steps onto their own lines."
                                @update:model-value="markDirty"
                            />
                            <!-- Owner 2026-09-03: *"I don't see why we can't
                                 style free text steps the same as structured
                                 in view mode. Just needs the numbers in the
                                 circles added."* The chrome is the shared
                                 `.dora-steps*` in `css/recipeSteps.scss`, so
                                 this really is the same step the structured
                                 method draws rather than a lookalike (R-001).
                                 What it deliberately doesn't get is the tap
                                 affordance: a free-text line has no stored
                                 ingredient links, so there is nothing to
                                 light up. -->
                            <ol v-else-if="freeformLines.length > 0" class="dora-steps">
                                <li
                                    v-for="(line, i) in freeformLines"
                                    :key="`f-${i}`"
                                    class="dora-steps__item"
                                >
                                    <span class="dora-steps__num">{{ i + 1 }}</span>
                                    <p class="dora-steps__body dora-steps__text">{{ line }}</p>
                                </li>
                            </ol>
                            <p v-else class="rn__empty">No instructions yet.</p>
                        </template>

                        <!-- Photo steps. Both faces read the *form's* list, not
                             the last-loaded recipe's: a photo picked in this
                             session has no saved id yet, and rendering only the
                             saved ones is why they "weren't showing" (owner,
                             2026-08-27). -->
                        <template v-else>
                            <RecipeStepImagesEditor
                                v-if="methodEditing"
                                :model-value="form.step_images"
                                :recipe-id="recipeId"
                                @update:model-value="onStepImagesChanged"
                            />
                            <RecipeStepImagesViewer
                                v-else
                                :images="form.step_images"
                                :recipe-id="recipeId"
                            />
                        </template>

                        <!-- Tools. In structured mode they are *derived* from
                             the steps that use them (server-side, on save) and
                             have no home outside a step - which is the owner's
                             call, and the only one that keeps the cookbook's
                             tool filter honest without asking for the same
                             facts twice. Free-text and photo recipes have no
                             steps to derive from, so they keep a real field -
                             here, inside the method, rather than in a
                             general-purpose drawer at the bottom of the page. -->
                        <!-- Owner 2026-09-03: *"show the tools in view mode for
                             structured steps, same as free text and image"*.
                             Structured tools are derived, not authored, which
                             is why there is no field for them here - but that
                             is an argument against the *editor*, not against
                             the answer. Reading a structured recipe you still
                             want to know it needs a blender, and the derived
                             list is exactly that answer. So the block renders
                             in every mode; only the editor stays mode-bound. -->
                        <div
                            v-if="form.steps_mode !== 'structured' || !methodEditing"
                            class="rn__tools"
                        >
                            <span class="rn__toolk">
                                <q-icon :name="ICONS.blender" size="14px" />Tools
                            </span>
                            <BaseSelect
                                v-if="methodEditing && form.steps_mode !== 'structured'"
                                v-model="form.tool_ids"
                                label="Tools this recipe needs"
                                :options="toolOptions"
                                emit-value map-options multiple use-chips clearable
                                @update:model-value="markDirty"
                            />
                            <template v-else-if="toolNames.length > 0">
                                <q-chip
                                    v-for="name in toolNames"
                                    :key="name"
                                    dense square size="sm"
                                    class="rn__chip"
                                >{{ name }}</q-chip>
                            </template>
                            <span v-else class="rn__empty">None set</span>
                        </div>
                    </div>
                </section>
            </div>

            <RecipeDetailsDrawers />
        </template>

        <!-- Two different jobs, deliberately not merged. The dirty pill is a
             standing statement of fact ("there is unsaved work here") and has
             to survive until it stops being true; the bar below is a transient
             outcome. One element doing both is how the old autosave indicator
             ended up being the only feedback channel for either. -->
        <div v-if="dirty && saveState !== 'saving'" class="rn__dirty" role="status">
            <q-icon :name="ICONS.edit" size="14px" />
            <span>Unsaved changes</span>
        </div>

        <div v-if="saveState !== 'idle'" class="rn__savebar" :class="`rn__savebar--${saveState}`" role="status">
            <q-spinner v-if="saveState === 'saving'" size="16px" />
            <q-icon v-else-if="saveState === 'saved'" :name="ICONS.check" />
            <q-icon v-else :name="ICONS.error" />
            <span>{{ saveMessage }}</span>
        </div>

        <!-- With an explicit save there is a real answer to "you have unsaved
             changes, cook anyway?", so the guard is wired to it instead of the
             hardcoded `false` the autosave version had to pass. -->
        <CookModeGuardDialog
            v-model="cookGuardOpen"
            :recipe="recipe"
            :dirty="dirty"
            :saving="saveState === 'saving'"
            :substitutable="substitutableNames"
            @start="goToCookMode"
            @save-and-start="onSaveAndCook"
        />
    </q-page>
</template>

<script lang="ts" setup>
    import { stripLeadingOrdinal } from 'src/helpers/stepOrdinal';
    import HelpHint from 'src/components/help/HelpHint.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    /**
     * The recipe page — the 2026-08-20 redesign, and since 2026-08-26 the only
     * one.
     *
     * It ran in parallel with the original at `/cookbook/:id/new` while the two
     * were compared on the same recipe. The owner picked this one (FU-688) and
     * the original — 2,727 lines, its own duplicate form model, both hatch
     * buttons and the `/new` route — was deleted with the swap. It kept the
     * bespoke masthead over the shared `PageToolbar` every other detail page
     * uses; that was the one piece explicitly reserved, and the same feedback
     * batch asked for the masthead to be *enriched*, so it stays. Import is
     * deliberately absent (FU-689 closed won't-do — importing over an existing
     * recipe was never wanted here).
     *
     * Since FU-934 (finalisation 01-R36) the page is a shell plus four blocks
     * in `components/recipes/`: `RecipeMasthead` (photo, identity, facts),
     * `RecipeStatusStrip` (right now / worth cooking / cost / last cooked),
     * `RecipeIngredientRail` (the list, its sections and the row editor) and
     * `RecipeDetailsDrawers` (additional details, nutrition, versions). What
     * they share — the loaded recipe, the form, the dirty flag and the save,
     * the three block switches, the step ↔ ingredient highlight, the pantry
     * facts — is `useRecipeDetail`, provided here and injected there, rather
     * than ~20 props and handler emits. The page keeps loading, the action
     * row, the method, the save/dirty indicators and the leave guards.
     *
     * Three things made it different from the page it replaced:
     *
     * 1. **Three blocks that flip, and an explicit save.** The masthead, the
     *    ingredient rail and the method each own one pencil that swaps that
     *    region between reading and editing *in place* (R-055). The last two
     *    arrived 2026-08-27: the rail had shipped with its editing chrome
     *    permanently on, and the method's pencil opened a modal over the very
     *    thing you were reading. What is *not* gone is the commit — edits mark
     *    the form dirty, a Save button appears, and leaving any pencil
     *    commits. The first cut autosaved on a 500ms debounce and the owner
     *    reversed it; see the save block in `useRecipeDetail` for the three
     *    ways that failed.
     *    D-015's "read-view + explicit edit mode for detail pages" clause was
     *    retired when this page won the comparison (FU-688) — it had been
     *    written against the old page's form-as-detail, which no longer
     *    exists. The block switches are that clause's intent arriving by a
     *    different route: the page reads as a recipe until you say otherwise.
     * 2. **Nothing edits somewhere else.** No disclosure holds structural
     *    edits any more. Steps reorder, gain sub-steps and take their
     *    ingredient/tool links where they are rendered
     *    (`RecipeStructuredMethod`, one component for both faces); a tool
     *    belongs to a step, so in structured mode the recipe's tool list is
     *    *derived* server-side from its steps and has no field at all, and in
     *    the two modes that have no steps it lives inside the method rather
     *    than in a drawer at the bottom of the page.
     * 3. **No business logic of its own.** The form model, hydrate and PATCH
     *    build all come from `useRecipeEditor` (R-003); everything else reads
     *    server-derived values off the loaded recipe exactly as the old page
     *    does.
     *
     * All three step modes are supported. Only `structured` can highlight the
     * ingredients a step uses, because it's the only mode that stores the
     * link — and since 2026-08-27 that highlight runs both ways off a *tap*
     * rather than one way off a hover a phone cannot perform.
     */
    import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
    import { onBeforeRouteLeave, onBeforeRouteUpdate, useRouter } from 'vue-router';
    import { useQuasar } from 'quasar';
    import { storeToRefs } from 'pinia';

    import AppSkeleton from 'src/components/AppSkeleton.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseSegmented from 'src/components/BaseSegmented.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import RecipeMasthead from 'src/components/recipes/RecipeMasthead.vue';
    import RecipeStatusStrip from 'src/components/recipes/RecipeStatusStrip.vue';
    import RecipeIngredientRail from 'src/components/recipes/RecipeIngredientRail.vue';
    import RecipeDetailsDrawers from 'src/components/recipes/RecipeDetailsDrawers.vue';
    import RecipeStepImagesViewer from 'src/components/recipes/RecipeStepImagesViewer.vue';
    import RecipeStepImagesEditor from 'src/components/recipes/RecipeStepImagesEditor.vue';
    import RecipeStructuredMethod from 'src/components/recipes/RecipeStructuredMethod.vue';
    import CookModeGuardDialog from 'src/components/recipes/CookModeGuardDialog.vue';

    import { ICONS } from 'src/style/icons';
    import { needsCookGuard } from 'src/helpers/cookModeGuard';
    import { isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useRecipeExport } from 'src/composables/useRecipeExport';
    import { hydrateRecipeForm } from 'src/composables/useRecipeEditor';
    import { provideRecipeDetail } from 'src/composables/useRecipeDetail';

    import { useRecipeStore } from 'src/stores/recipeStore';
    import { useRecipeVocabStore } from 'src/stores/recipeVocabStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useMealSlotStore } from 'src/stores/mealSlotStore';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import type { EditableStep } from 'src/components/recipes/recipeStepEditorTypes';
    import type { EditableStepImage } from 'src/components/recipes/recipeStepImageEditorTypes';
    import { useConfirm } from 'src/composables/useConfirm';

    const $q = useQuasar();

    const { confirm } = useConfirm();
    const router = useRouter();

    const recipeStore = useRecipeStore();
    const stockItemStore = useStockItemStore();
    const recipeVocabStore = useRecipeVocabStore();
    const shoppingListStore = useShoppingListStore();
    const mealSlotStore = useMealSlotStore();
    const stockLevelStore = useStockLevelStore();
    const { tools, toolOptions } = storeToRefs(recipeVocabStore);
    const recipeExport = useRecipeExport();

    const {
        compact, recipeId, recipe, form, loading, loadError, loadRecipe,
        newVersionLoading, onNewVersion,
        imageDirty, stepImagesDirty, stepErrorsShown,
        saveState, saveMessage, dirty, canSave, onSave, markDirty,
        methodEditing, closeEditRegions, toggleEditRegion,
        selectedStepId, selectedIngredientId, clearHighlight, onSelectStep,
        ingredientLabel, substitutableNames,
    } = provideRecipeDetail();

    const onToggleMethodEdit = () => toggleEditRegion(methodEditing);

    /** Discard: re-hydrate from the last loaded recipe. No refetch — the point
     *  is to undo local edits, and `recipe.value` is what they departed from. */
    async function onDiscard() {
        const src = recipe.value;
        if (!src) return;
        const ok = await confirm({
            title: 'Discard changes',
            message: 'Throw away every change you’ve made since the last save?',
            okLabel: 'Discard',
            destructive: true,
        });
        if (ok) {
            hydrateRecipeForm(form, src);
            imageDirty.value = false;
            stepImagesDirty.value = false;
            stepErrorsShown.value = false;
            dirty.value = false;
            closeEditRegions();
            saveState.value = 'idle';
        }
    }

    // ── Method ──────────────────────────────────────────────────────────
    // The author's own "1. " is dropped beside the drawn numeral
    // (helpers/stepOrdinal; the 2026-09-03 Carbonara walk, R-075).
    const freeformLines = computed(() => (form.instructions ?? '')
        .split('\n')
        .map((l) => l.trim())
        .filter((l) => l.length > 0)
        .map(stripLeadingOrdinal));

    /** The other direction of the rail's highlight: steps lit by the
     *  currently selected ingredient. Structured-only, because it's the only
     *  mode that stores the link. */
    const highlightedStepIds = computed<string[]>(() => {
        const target = selectedIngredientId.value;
        if (!target) return [];
        return form.steps
            .filter((s) => s.ingredient_client_ids.includes(target))
            .map((s) => s.client_id);
    });

    // The steps editor's option shape is {value,label} for all three lists.
    const ingredientOptions = computed(() =>
        form.ingredients.map((i) => ({ value: String(i.client_id), label: ingredientLabel(i) })));
    const sectionOptions = computed(() =>
        form.sections.map((s) => ({ value: s.client_id, label: s.name || 'Untitled section' })));

    /** One pencil, three styles — so the label has to say which one it will
     *  open (owner feedback 2026-08-24). */
    const methodEditLabel = computed(() => {
        switch (form.steps_mode) {
            case 'structured': return 'Edit steps';
            case 'image': return 'Edit step photos';
            default: return 'Edit instructions';
        }
    });

    /** Read-side tool names for the free-text / photo method. Structured
     *  recipes don't render this at all — their tools live on the steps and
     *  the recipe-level set is derived from them server-side. */
    const toolNames = computed(() =>
        form.tool_ids
            .map((id) => tools.value.find((t) => t.tool_id === id)?.name)
            .filter((n): n is string => !!n));

    function onStepsChanged(steps: EditableStep[]) {
        form.steps = steps;
        markDirty();
    }
    function onStepImagesChanged(images: EditableStepImage[]) {
        form.step_images = images;
        stepImagesDirty.value = true;
        markDirty();
    }

    // ── Actions ─────────────────────────────────────────────────────────
    async function onToggleFavourite() {
        if (!recipe.value) return;
        try {
            await recipeStore.toggleFavouriteAsync(recipe.value);
            await loadRecipe();
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({ type: 'negative', message: "Couldn't update favourite.", caption: toastCaption(err) });
            }
        }
    }

    const cookGuardOpen = ref(false);

    function onStartCookMode() {
        if (!recipe.value) return;
        // `dirty` is a real guard reason now — the shared helper has always
        // taken it, and the autosave page had nothing truthful to pass.
        if (needsCookGuard(recipe.value, dirty.value)) {
            cookGuardOpen.value = true;
            return;
        }
        goToCookMode();
    }
    function goToCookMode() {
        void router.push(`/cookbook/${recipeId.value}/cook`);
    }
    /** The guard's "save and start" branch. Cook mode reads the *server's*
     *  recipe, so starting without committing would cook the old version. */
    async function onSaveAndCook() {
        await onSave();
        if (saveState.value === 'error') return;
        goToCookMode();
    }

    function onPrint() {
        if (!recipeId.value) return;
        recipeExport.openPrintView(recipeId.value);
    }

    async function onDelete() {
        if (!recipe.value) return;
        const ok = await confirm({
            title: 'Delete recipe',
            message: `Delete "${recipe.value.name}"? This can't be undone.`,
            okLabel: 'Delete',
            destructive: true,
        });
        if (ok) await doDelete();
    }
    async function doDelete() {
        if (!recipe.value) return;
        try {
            await recipeStore.deleteRecipeAsync(recipe.value.recipe_id);
            await router.push('/cookbook');
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({ type: 'negative', message: "Couldn't delete.", caption: toastCaption(err) });
            }
        }
    }

    // ── Mount / unmount / leaving ───────────────────────────────────────
    onMounted(async () => {
        await Promise.all([
            recipeStore.ensureCollectionsLoadedAsync(),
            stockItemStore.ensureLoadedAsync(),
            stockLevelStore.ensureLoadedAsync(),
            recipeVocabStore.ensureLoadedAsync(),
            shoppingListStore.ensureLoadedAsync(),
            mealSlotStore.ensureLoadedAsync(),
        ]);
        await loadRecipe();
        window.addEventListener('beforeunload', onBeforeUnload);
    });

    onBeforeUnmount(() => {
        // The page shipped without this (the save timer's cleanup is in
        // `useRecipeDetail`, registered from this setup).
        window.removeEventListener('beforeunload', onBeforeUnload);
    });

    /** Tab close / reload. The browser shows its own generic prompt; the
     *  string is ignored by every current engine but `preventDefault` is what
     *  actually arms it. */
    function onBeforeUnload(e: BeforeUnloadEvent) {
        if (!dirty.value) return;
        e.preventDefault();
        e.returnValue = '';
    }

    /** Shared by both route guards below: let the user keep or drop
     *  unsaved work before the page shows something else (R-020). */
    async function confirmLeaveIfDirty(): Promise<boolean> {
        if (!dirty.value) return true;
        return await confirm({
            title: 'Unsaved changes',
            message: 'You have changes that haven’t been saved yet.',
            okLabel: 'Leave without saving',
            cancelLabel: 'Stay',
            destructive: true,
        });
    }

    // In-app navigation away from the page — the Back arrow, cook mode.
    onBeforeRouteLeave(confirmLeaveIfDirty);

    // `/cookbook/A` → `/cookbook/B` (a sibling version, a new version)
    // reuses this component, so the leave guard never fires for it.
    onBeforeRouteUpdate(async (to, from) => {
        if (to.params.id === from.params.id) return true;
        return await confirmLeaveIfDirty();
    });

    // Switching recipes in place (a sibling version) is a fresh load; the
    // update guard above has already dealt with any unsaved work. Leaving to
    // `/cookbook` empties the id on the way out — nothing to load.
    watch(recipeId, (id) => {
        if (!id) return;
        dirty.value = false;
        closeEditRegions();
        clearHighlight();
        saveState.value = 'idle';
        void loadRecipe();
    });
</script>

<style scoped lang="scss">
    // The masthead grid (the loading skeleton mirrors it) and the section
    // heading / pane / chip the method shares with the ingredient rail. The
    // blocks' own rules moved into their components (FU-934).
    @use '../css/recipeDetail';

    /* No display face. The page shipped with Fraunces on the title and the
       section labels; the owner's verdict 2026-08-24 was that it "just
       doesn't feel like the same app" — which is the right call, because a
       page-specific typeface is a second brand nobody asked for. Everything
       here inherits the user's chosen font (Settings → Appearance,
       themeService FONT_FAMILY_CSS), like every other page. */

    /* ── Actions ──────────────────────────────────────────────────────── */
    .rn__actions {
        display: flex; align-items: center; gap: var(--space-2);
        margin-top: var(--space-5);
        padding-top: var(--space-4);
        border-top: 1px solid var(--divider);
        flex-wrap: wrap;
    }
    .rn__delete { margin-left: auto; }

    /* ── Body ─────────────────────────────────────────────────────────── */
    .rn__body {
        display: grid;
        grid-template-columns: minmax(280px, 34%) 1fr;
        gap: var(--space-8);
        margin-top: var(--space-6);
        align-items: start;
    }
    /* D-011 — a grid item's default `min-width: auto` lets it be sized by its
       widest indivisible content instead of by its track, and a wrapping chip
       field is exactly that content: every tool added to the free-text
       method's Tools select pushed the column, the column pushed the page, and
       the page scrolled sideways (owner, 2026-08-31). The track owns the width;
       what's inside it wraps or scrolls in its own box. */
    .rn__body > * { min-width: 0; }
    .rn__modes { min-width: 0; }

    /* The structured method's own rules — the numbered bullets, the sub-step
       indent, the lit state — moved into `RecipeStructuredMethod.vue` with
       the markup, so the read and edit faces can't drift apart (owner
       feedback 2026-08-27). What's left here is the free-text face. */
    /* The free-text read face is `.dora-steps*` now (owner 2026-09-03) — its
       measure and spacing come from `css/recipeSteps.scss` with the structured
       method's, so the old `.rn__free` rule has nothing left to say. */
    .rn__empty { color: var(--text-muted); font-size: var(--font-size-sm); }

    /* Tools, for the two modes that have no steps to derive them from. Inside
       the method, because that is what a tool belongs to — not a
       general-purpose drawer at the bottom of the page (owner call
       2026-08-27). */
    .rn__tools {
        display: flex; align-items: center; flex-wrap: wrap;
        gap: var(--space-2);
        margin-top: var(--space-6);
        padding-top: var(--space-3);
        border-top: 1px solid var(--divider);
    }
    .rn__toolk {
        display: inline-flex; align-items: center; gap: var(--space-1);
        font-size: var(--font-size-xs); font-weight: 700; letter-spacing: 0.07em;
        text-transform: uppercase; color: var(--text-muted);
        flex: none;
    }
    .rn__toolk .q-icon { letter-spacing: normal; }
    .rn__tools .q-select { flex: 1 1 240px; min-width: 0; }

    .rn__savebar {
        position: fixed; bottom: var(--space-5); left: 50%;
        transform: translateX(-50%); z-index: 6000;
        display: flex; align-items: center; gap: var(--space-2);
        padding: var(--space-2) var(--space-4);
        border-radius: var(--radius-pill);
        background: var(--surface-elevated);
        border: 1px solid var(--border-default);
        box-shadow: var(--elevation-3);
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
    }
    .rn__savebar--error { border-color: var(--semantic-negative); color: var(--semantic-negative); }

    /* The standing "there is unsaved work" statement. Sits above the transient
       savebar's slot so the two never occupy the same space. */
    .rn__dirty {
        position: fixed; bottom: var(--space-5); left: 50%;
        transform: translateX(-50%); z-index: 6000;
        display: flex; align-items: center; gap: var(--space-2);
        padding: var(--space-2) var(--space-4);
        border-radius: var(--radius-pill);
        background: var(--surface-elevated);
        border: 1px solid var(--semantic-warning);
        box-shadow: var(--elevation-3);
        font-size: var(--font-size-sm);
        font-weight: 600;
        color: var(--text-secondary);
    }

    /* ── Phone ────────────────────────────────────────────────────────── */
    @media (max-width: 1023px) {
        /* The method heading's three-way switch takes its own full-width
           line (see `.rn__sechead` in `css/recipeDetail.scss`). */
        /* Its segments share that line via BaseSegmented's `spread`, bound to
           the same < 1024px breakpoint (`$q.screen.lt.md`). */
        .rn__modes { order: 3; flex: 1 1 100%; }

        .rn__body { grid-template-columns: 1fr; gap: var(--space-6); }
        /* Actions scroll sideways rather than stacking three deep (D-011:
           wide content scrolls inside its own container, never the page). */
        .rn__actions {
            flex-wrap: nowrap;
            overflow-x: auto;
            scrollbar-width: none;
        }
        .rn__actions::-webkit-scrollbar { display: none; }
        .rn__delete { margin-left: 0; }
    }
</style>
