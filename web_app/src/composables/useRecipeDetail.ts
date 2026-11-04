/**
 * The recipe page's shared state (FU-934 / finalisation 01-R36).
 *
 * `RecipeDetailPage.vue` was one ~2,700-line file. It is now a page plus four
 * blocks — `RecipeMasthead`, `RecipeStatusStrip`, `RecipeIngredientRail`,
 * `RecipeDetailsDrawers` — and the state those blocks *share* lives here
 * rather than being prop-drilled through ~20 props and handler emits: the
 * loaded recipe, the edit form, the dirty flag and the explicit save, the
 * three block switches, the step ↔ ingredient highlight, and the pantry facts
 * read off the server's recipe (missing, expiring, substitutes).
 *
 * The page calls `provideRecipeDetail()` once in its setup; each block calls
 * `useRecipeDetail()` (R-011: composables + provide/inject, not a global
 * store — this is one page's view state, and two recipe pages would each want
 * their own). What only one block reads stays in that block.
 *
 * No business logic of its own: the form model, hydrate and PATCH build come
 * from `useRecipeEditor` (R-003), and every pantry fact is the server's
 * verdict on the saved recipe, read rather than recomputed.
 */
import { computed, inject, onBeforeUnmount, provide, ref, type InjectionKey, type Ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useQuasar } from 'quasar';

import { ICONS } from 'src/style/icons';
import { ingredientDisplayName } from 'src/helpers/recipeIngredientLabel';
import { formatDate } from 'src/composables/useDateFormat';
import { correlationSuffix, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
import { NormalisedApiError } from 'src/services/api/axiosHttpClient';
import {
    buildUpdateCommand,
    hydrateRecipeForm,
    useRecipeForm,
    type IngredientForm,
} from 'src/composables/useRecipeEditor';
import RecipeApiService from 'src/services/api/recipeApiService';
import StockItemApiService from 'src/services/api/stockItemApiService';
import { useRecipeStore } from 'src/stores/recipeStore';
import { useStockItemStore } from 'src/stores/stockItemStore';
import { useStockLevelStore } from 'src/stores/stockLevelStore';
import type { Recipe } from 'src/models/recipe';
import type { SubstituteOption } from 'src/components/recipes/recipeSubstituteTypes';

export type SaveState = 'idle' | 'saving' | 'saved' | 'error';

export type RecipeLoadError = { heading: string; detail: string; retry: boolean };

function createRecipeDetail() {
    const $q = useQuasar();
    const route = useRoute();
    const router = useRouter();

    const recipeStore = useRecipeStore();
    const stockItemStore = useStockItemStore();
    const stockLevelStore = useStockLevelStore();
    const recipeApi = new RecipeApiService();
    const stockItemApi = new StockItemApiService();

    const compact = computed(() => $q.screen.lt.sm);
    const recipeId = computed(() => String(route.params.id ?? ''));

    const recipe = ref<Recipe | null>(null);
    const form = useRecipeForm();
    const loading = ref(false);
    const loadError = ref<RecipeLoadError | null>(null);
    const newVersionLoading = ref(false);
    const imageDirty = ref(false);
    const stepImagesDirty = ref(false);
    const imageVersion = ref(0);
    // Owner feedback 2026-08-27 — the step→ingredient highlight used to be
    // driven by hover, which a phone can't do, and it only ran one way. It is
    // a *selection* now: tap a step to light its ingredients, tap an
    // ingredient to light the steps that use it. One selection at a time —
    // two would produce two sets of lit rows with nothing saying which
    // highlight belongs to which tap.
    const selectedStepId = ref<string | null>(null);
    const selectedIngredientId = ref<string | null>(null);

    // ── Save ────────────────────────────────────────────────────────────
    // Inline editing, explicit commit. The page shipped with a 500ms debounced
    // autosave behind every popup-edit, which had three failure modes the
    // owner reversed it over: (1) each save ended in `loadRecipe()`, which
    // re-hydrates `form` — so a save firing while a second popup was open
    // rebound that popup to an orphaned row object and dropped the edit;
    // (2) a fresh, not-yet-linked ingredient row failed the anchor check, so
    // every *unrelated* save was refused until it was filled or deleted, with
    // no button to retry from; (3) navigating inside the debounce window sent
    // the PATCH into a torn-down component, so a failure had nowhere to show.
    // An explicit Save fixes all three by construction: nothing re-hydrates
    // mid-edit, validation is reported when the user asks to commit, and the
    // dirty flag is what the route guard reads.
    //
    // D-019 is why the *fields* are never disabled while saving — only the
    // Save button is, which is that rule's stated carve-out.
    const saveState = ref<SaveState>('idle');
    const saveMessage = ref('');
    const dirty = ref(false);
    let idleTimer: ReturnType<typeof setTimeout> | null = null;

    // ── Block edit modes (R-055 / ADR-051) ──────────────────────────────
    // One pencil for the whole masthead, replacing the per-field
    // `q-popup-edit`s that used to sit on the name, collection, cuisine,
    // category and every fact. Those cost two clicks on every dropdown (one
    // to summon the field, one to open it) and sized each control to its own
    // longest option, so an empty Difficulty was a sliver. A block that flips
    // whole keeps one grid across both states, and a select is a select.
    const headerEditing = ref(false);
    // Owner feedback 2026-08-27 extended the same shape to the other two
    // regions. The ingredient list and the method were the two places still
    // wearing their editing affordances permanently — a row that opened a
    // dialog on tap, and a pencil that opened a modal over the method you
    // were reading. Both now read as what they are until the pencil says
    // otherwise, and both swap **in place** (R-055; the method's dialog
    // carve-out in that rule is retired with the dialog).
    const ingredientsEditing = ref(false);
    const methodEditing = ref(false);

    /** Every region back to reading — after a save, a discard, or a switch
     *  to another recipe. */
    function closeEditRegions() {
        headerEditing.value = false;
        ingredientsEditing.value = false;
        methodEditing.value = false;
    }

    /** Leaving any of the three edit modes commits, because the pencil reads
     *  as "done" — see the Done label it wears while open. A failed save keeps
     *  the block open so the error has something to point at. */
    async function toggleEditRegion(flag: Ref<boolean>): Promise<void> {
        if (!flag.value) {
            flag.value = true;
            return;
        }
        if (dirty.value) {
            await onSave();
            if (saveState.value === 'error') return;
        }
        flag.value = false;
    }

    /** Every edit path lands here. It records that there is something to
     *  save; it never saves. */
    function markDirty() {
        dirty.value = true;
        // A previous failure is no longer describing the current form.
        if (saveState.value === 'error') saveState.value = 'idle';
    }

    /** Steps with nothing written in them. Only counted in structured mode,
     *  where they are the rows that get sent. */
    const emptySteps = computed(() => (form.steps_mode === 'structured'
        ? form.steps.filter((st) => !st.text.trim())
        : []));

    /** Set once a save has been blocked by an empty step, so the editor can
     *  mark the offending rows. Cleared when the save goes through. */
    const stepErrorsShown = ref(false);

    /** Mirrors the server's `recipe_ingredient_anchor` CHECK, the name
     *  requirement and `UpdateRecipeStepRequest.text`'s `min_length=1`, as
     *  human sentences. Empty = safe to send.
     *
     *  The step clause is owner-reported, 2026-09-03: adding one structured
     *  step and pressing Done produced *"Couldn't save. Couldn't save — check
     *  the highlighted fields."* with nothing highlighted. Two faults, and
     *  this is the real one — the request went to the server, which rejected
     *  `steps.0.text` on a length rule the page had no local copy of, so all
     *  the client could do was relay a generic field-error caption and then
     *  fail to honour it. A blocker keeps the whole exchange local, names the
     *  rows in the same voice as the ingredient one, and `stepErrorsShown`
     *  makes "highlighted" true. */
    const saveBlockers = computed(() => {
        const out: string[] = [];
        if (!form.name.trim()) out.push('the recipe needs a name');
        const halfBuilt = form.ingredients.filter((i) => !i.stock_item_id && !i.raw_text).length;
        if (halfBuilt > 0) {
            out.push(halfBuilt === 1
                ? '1 ingredient has no item or text yet'
                : `${halfBuilt} ingredients have no item or text yet`);
        }
        const blank = emptySteps.value.length;
        if (blank > 0) {
            out.push(blank === 1
                ? '1 step has nothing written in it yet'
                : `${blank} steps have nothing written in them yet`);
        }
        return out;
    });

    const canSave = computed(() => dirty.value && saveState.value !== 'saving');

    async function onSave() {
        const src = recipe.value;
        if (!src || saveState.value === 'saving') return;
        if (saveBlockers.value.length > 0) {
            stepErrorsShown.value = emptySteps.value.length > 0;
            saveState.value = 'error';
            saveMessage.value = `Not saved: ${saveBlockers.value.join(', and ')}.`;
            return;
        }
        stepErrorsShown.value = false;
        saveState.value = 'saving';
        saveMessage.value = 'Saving…';
        try {
            const command = buildUpdateCommand(form, src, {
                image: imageDirty.value,
                stepImages: stepImagesDirty.value,
            });
            const didImageChange = imageDirty.value;
            await recipeStore.updateRecipeAsync(command);
            // Safe to re-hydrate here in a way autosave never was: the user
            // asked to commit, so nothing is mid-edit. This is what picks up
            // the server-derived values the page reads (cost, cookability,
            // per-ingredient expiry) rather than recomputing them.
            await loadRecipe();
            if (didImageChange) imageVersion.value++;
            dirty.value = false;
            // A save is the end of an edit: every region goes back to
            // reading, whichever button asked for it (the Save button in the
            // action row, or one of the three pencils).
            closeEditRegions();
            saveState.value = 'saved';
            saveMessage.value = 'Saved';
            if (idleTimer) clearTimeout(idleTimer);
            idleTimer = setTimeout(() => { saveState.value = 'idle'; }, 1600);
        } catch (err) {
            // `toastCaption` already opens with "Couldn't save — …", so the
            // old prefix here produced the owner-reported *"Couldn't save.
            // Couldn't save — check the highlighted fields."* Its own copy is
            // only the fallback for an error it can say nothing about.
            saveState.value = 'error';
            saveMessage.value = toastCaption(err) || "Couldn't save.";
        }
    }

    async function loadRecipe() {
        // Captured so a slow response for a recipe we've since navigated away
        // from (sibling version link) can't overwrite the current one.
        const id = recipeId.value;
        loading.value = true;
        loadError.value = null;
        try {
            const fresh = await recipeApi.getAsync(id);
            if (id !== recipeId.value) return;
            recipe.value = fresh;
            hydrateRecipeForm(form, fresh);
            imageDirty.value = false;
            stepImagesDirty.value = false;
        } catch (err) {
            if (id !== recipeId.value) return;
            // A missing recipe (unknown id, or a malformed one the router
            // can't match) isn't worth retrying; anything else might be.
            const missing = err instanceof NormalisedApiError && err.status === 404;
            loadError.value = missing
                ? { heading: "This recipe isn't available.", detail: 'It may have been deleted.', retry: false }
                : { heading: "Couldn't open this recipe.",
                    detail: correlationSuffix(err).replace(/^\s·\s/, ''), retry: true };
        } finally {
            if (id === recipeId.value) loading.value = false;
        }
        // After the form is hydrated, so `missingIngredients` is current.
        // Deliberately not awaited by callers: the page is fully usable while
        // the chips fill in.
        void loadSubstitutes();
    }

    // ── Ingredient names ────────────────────────────────────────────────
    function stockItemName(row: IngredientForm): string | null {
        if (!row.stock_item_id) return null;
        return stockItemStore.byId.get(row.stock_item_id)?.name ?? null;
    }

    /** The recipe's own name for the row when it has chosen one ("Bega
     *  Tasty" under Cheese), else the pantry item's. */
    // Shared precedence (finalisation 01-R1): `label` → item name → raw text.
    function ingredientLabel(row: IngredientForm): string {
        if (row.stock_item_id) {
            return ingredientDisplayName({
                label: row.label, stock_item_name: stockItemName(row), raw_text: row.raw_text,
            });
        }
        return ingredientDisplayName({ raw_text: row.raw_text });
    }

    // ── Pantry facts (server-owned, R-003) ──────────────────────────────
    const missingIngredients = computed(() => {
        const r = recipe.value;
        if (!r) return [];
        return r.ingredients
            .filter((i): i is typeof i & { stock_item_id: string; stock_item_name: string } =>
                i.is_missing && i.stock_item_id !== null)
            .filter((i, idx, arr) => arr.findIndex((x) => x.stock_item_id === i.stock_item_id) === idx);
    });

    /** A substitute's stock state, from the store (substitutes aren't on the
     *  recipe DTO). */
    function isMissingItem(stockItemId: string | null | undefined): boolean {
        if (!stockItemId) return false;
        const item = stockItemStore.byId.get(stockItemId);
        return !item || Boolean(item.is_out_of_stock);
    }
    /** An ingredient row's "missing": the server's verdict on the saved
     *  recipe (R-003); a row added since the last save falls back to the
     *  store. */
    const missingByStockItem = computed(() => new Map(
        (recipe.value?.ingredients ?? [])
            .filter((i) => i.stock_item_id !== null)
            .map((i) => [i.stock_item_id as string, i.is_missing]),
    ));
    function isIngredientMissing(stockItemId: string): boolean {
        return missingByStockItem.value.get(stockItemId) ?? isMissingItem(stockItemId);
    }

    // Server's per-ingredient expiry verdict, read off the loaded recipe so the
    // chips and the cookbook's expiring filter share one horizon (as the old
    // page does). Keyed by stock item, not row.
    const expiringItems = computed(() => {
        const map = new Map<string, { expired: boolean; date: string | null }>();
        for (const ing of recipe.value?.ingredients ?? []) {
            if (!ing.stock_item_id || !ing.is_expiring) continue;
            map.set(ing.stock_item_id, { expired: ing.is_expired, date: ing.expiry_date });
        }
        return map;
    });
    function expiringChipFor(stockItemId: string | null | undefined) {
        if (!stockItemId) return null;
        const hit = expiringItems.value.get(stockItemId);
        if (!hit) return null;
        const when = hit.date ? formatDate(hit.date) : null;
        return hit.expired
            ? { label: 'Expired', tone: 'negative', icon: ICONS.error, tooltip: when ? `Expired ${when}` : 'Past its expiry date' }
            : { label: 'Use soon', tone: 'warning', icon: ICONS.event_busy, tooltip: when ? `Expires ${when}` : 'Expiring soon' };
    }

    // ── Substitutes ─────────────────────────────────────────────────────
    // Fetched per missing ingredient, because "what could I use instead" is
    // only a question when something is actually absent. N is the number of
    // missing rows — small, and the fan-out is the same shape the old page
    // used for its bulk dialog.
    const substitutesFor = ref(new Map<string, SubstituteOption[]>());

    async function loadSubstitutes() {
        const targets = missingIngredients.value.map((i) => i.stock_item_id);
        if (targets.length === 0) {
            substitutesFor.value = new Map();
            return;
        }
        const next = new Map<string, SubstituteOption[]>();
        const results = await Promise.allSettled(
            targets.map((id) => stockItemApi.getSubstitutesAsync(id)),
        );
        results.forEach((res, i) => {
            const id = targets[i]!;
            // A single failed lookup shouldn't cost the others their chip, and
            // it isn't worth a toast: substitutes are an enhancement to a row
            // that already reads "Missing" correctly without them.
            if (res.status !== 'fulfilled') return;
            const entries = res.value.map((sub) => {
                // Resolved here, not in the chip: the store is the page's one
                // source of truth about stock (R-003), and the menu renders
                // the verdict it was handed.
                const item = stockItemStore.byId.get(sub.stock_item_id);
                return {
                    sub,
                    inStock: !isMissingItem(sub.stock_item_id),
                    levelSequence: item?.stock_level_sequence ?? sub.stock_level_sequence,
                    levelLabel: (item ? stockLevelStore.levelById.get(item.stock_level_id)?.name : undefined)
                        ?? sub.stock_level_name
                        ?? 'Out of stock or untracked',
                };
            });
            if (entries.length > 0) next.set(id, entries);
        });
        substitutesFor.value = next;
    }

    function substitutesForRow(row: IngredientForm): SubstituteOption[] {
        if (!row.stock_item_id) return [];
        return substitutesFor.value.get(row.stock_item_id) ?? [];
    }

    /** Missing rows that a substitute you already have would cover. This is
     *  the fact that changes tonight's answer, so the status strip says it —
     *  and, since 2026-08-24, so do the ingredient row and the cook-mode
     *  guard, which is the last place it can still change the decision. */
    const coverableIngredients = computed(() =>
        missingIngredients.value.filter(
            (i) => (substitutesFor.value.get(i.stock_item_id) ?? []).some((e) => e.inStock),
        ));
    const substitutableNames = computed(() =>
        coverableIngredients.value.map(
            (i) => (i.stock_item_id ? stockItemStore.byId.get(i.stock_item_id)?.name : undefined)
                ?? i.stock_item_name,
        ));

    // ── Step ↔ ingredient highlight ─────────────────────────────────────
    function clearHighlight() {
        selectedStepId.value = null;
        selectedIngredientId.value = null;
    }

    function onSelectStep(clientId: string | null) {
        selectedIngredientId.value = null;
        selectedStepId.value = clientId;
    }

    // ── New version ─────────────────────────────────────────────────────
    // Two buttons reach it — the page's action row and the versions drawer —
    // so it lives with the state they share rather than in either.
    async function onNewVersion() {
        if (!recipe.value) return;
        newVersionLoading.value = true;
        try {
            const created = await recipeApi.createNewVersionAsync(recipe.value.recipe_id);
            const newId = created.recipe_id;
            await recipeStore.getRecipesAsync();
            $q.notify({
                type: 'positive',
                message: 'New version created.',
                caption: 'Pick either one when planning.',
            });
            if (newId) void router.push(`/cookbook/${newId}`);
        } catch (err) {
            $q.notify({ type: 'negative', message: "Couldn't create a new version.", caption: toastCaption(err) });
        } finally {
            newVersionLoading.value = false;
        }
    }

    // The page shipped without this. The autosave timer it had outlived the
    // component, so a PATCH could land with nothing mounted to report its
    // failure to. Registered from the page's setup, so it runs on the page's
    // unmount.
    onBeforeUnmount(() => {
        if (idleTimer) clearTimeout(idleTimer);
    });

    return {
        compact,
        recipeId,
        recipe,
        form,
        loading,
        loadError,
        newVersionLoading,
        imageDirty,
        stepImagesDirty,
        imageVersion,
        selectedStepId,
        selectedIngredientId,
        saveState,
        saveMessage,
        dirty,
        headerEditing,
        ingredientsEditing,
        methodEditing,
        closeEditRegions,
        toggleEditRegion,
        markDirty,
        stepErrorsShown,
        canSave,
        onSave,
        loadRecipe,
        ingredientLabel,
        stockItemName,
        missingIngredients,
        isIngredientMissing,
        expiringItems,
        expiringChipFor,
        substitutesForRow,
        substitutableNames,
        clearHighlight,
        onSelectStep,
        onNewVersion,
    };
}

export type RecipeDetailContext = ReturnType<typeof createRecipeDetail>;

const RECIPE_DETAIL_KEY: InjectionKey<RecipeDetailContext> = Symbol('recipeDetail');

/** Called once, in `RecipeDetailPage`'s setup. */
export function provideRecipeDetail(): RecipeDetailContext {
    const ctx = createRecipeDetail();
    provide(RECIPE_DETAIL_KEY, ctx);
    return ctx;
}

/** Called by the recipe page's blocks. Throws outside the page: a block
 *  mounted without its page has no recipe to show, and a silent `undefined`
 *  would surface as a template error somewhere less obvious. */
export function useRecipeDetail(): RecipeDetailContext {
    const ctx = inject(RECIPE_DETAIL_KEY, null);
    if (!ctx) throw new Error('useRecipeDetail() must be used inside RecipeDetailPage (provideRecipeDetail).');
    return ctx;
}
