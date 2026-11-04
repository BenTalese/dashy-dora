<template>
    <!-- FU-609 / R-036 — <q-page> when routed, plain <div> when embedded in the
         Stock Overview peek (see rootTag). class + padding apply to both. -->
    <component :is="rootTag" class="q-pa-md">
        <!-- Header — back/close · name · spacer · (Show QR) · Delete top-right.
             Feedback 2026-06-18: the level chip moves down to the overview
             (under the name field, combined with "Level updated"); the top
             Mark-open / Set-expiry / Add-to-list trio is gone because all
             three actions live inline on the page already. Show QR stays
             since it's not reachable elsewhere. -->
        <div class="row items-center no-wrap q-mb-md q-gutter-sm stock-detail__header">
            <BaseButton aria-label="Back" v-if="!embedded" variant="icon" :icon="ICONS.arrow_back" @click="goBack" />
            <BaseButton aria-label="Close panel" v-else variant="icon" :icon="ICONS.close" @click="emit('close')">
                <BaseTooltip>Close panel</BaseTooltip>
            </BaseButton>
            <!-- 2026-08-24 feedback: a long name used to wrap, which pushed the
                 buttons to a third line and left the back arrow alone on the
                 first. The row no longer wraps at all — the name takes the
                 slack and truncates, the controls keep their intrinsic width,
                 and the full name is still readable on the overview card
                 below. `min-width: 0` is what lets a flex child shrink far
                 enough to ellipsis. -->
            <div class="text-h5 q-mr-sm stock-detail__name">
                <AppSkeleton v-if="loading && !detail" type="line" width="180px" height="1.6rem" />
                <template v-else>{{ detail?.name || 'Stock item' }}</template>
            </div>
            <!-- Feedback 2026-08-16: on a phone the labelled Delete button
                 wrapped the header onto a second line. Below `sm` it drops to
                 icon-only so it sits on the item-name line; the label survives
                 as the tooltip, so nothing is lost.
                 Feedback 2026-08-24: the "Show QR" button that used to sit here
                 is gone — the code itself now renders in the Scanning tab
                 rather than behind a modal, so a header button for it was a
                 second route to something already on the page. -->
            <BaseButton
                v-if="detail"
                variant="danger-ghost"
                :icon="ICONS.delete"
                :label="compactHeader ? undefined : 'Delete'"
                @click="confirmDelete"
            >
                <BaseTooltip v-if="compactHeader">Delete</BaseTooltip>
            </BaseButton>
        </div>

        <q-banner v-if="loadError" class="dora-bg-negative-soft text-negative q-mb-md" dense rounded>
            {{ loadError }}
        </q-banner>

        <FadeTransition mode="out-in">
        <div v-if="loading && !detail" key="sid-loading">
            <!-- Skeleton mirrors the toolbar row + content cards below. -->
            <div class="row q-gutter-sm q-mb-md">
                <AppSkeleton type="rect" width="120px" height="36px" />
                <AppSkeleton type="rect" width="110px" height="36px" />
                <AppSkeleton type="rect" width="130px" height="36px" />
            </div>
            <AppSkeleton type="rect" width="100%" height="160px" class="q-mb-md" />
            <AppSkeleton type="rect" width="100%" height="220px" />
        </div>

        <div v-else-if="detail" key="sid-content">
            <!-- Feedback 2026-06-18: replaced q-tabs with DoraTabs so the
                 active-tab underline uses the same sliding accent indicator
                 as the main menu (shrunk to tab-row scale). The per-tab
                 colour saturation is gone — the indicator carries the colour. -->
            <DoraTabs v-model="tab" :tabs="tabDefinitions" class="q-mb-sm" />

            <q-tab-panels v-model="tab" animated>
                <!-- ── Overview ───────────────────────────────────────────
                     C-1b.1: single-column inline-edit fact list. Each row
                     IS its editor; toggles/selects/dates save immediately
                     on change, text rows save on blur. No separate q-form
                     + Save/Reset (the old 2-col "facts | edit form" split
                     is what L127 called "messy"). Level dedupe (L121): the
                     header chip is the only level editor.
                -->
                <!-- Feedback 2026-06-18 (round 2): q-pa-md on every
                     q-tab-panel so the inner content (image, list of
                     editors, all per-tab content) has consistent
                     breathing room on every side. The outer wrapper
                     keeps q-pa-md too for the header/toolbar row. -->
                <q-tab-panel name="overview" class="q-pa-md">
                    <StockItemOverviewTab />
                </q-tab-panel>

                <!-- ── Linked products ──────────────────────────────────
                     C-1b.3 (L125, L130, L131): Find-deals lives here now,
                     not in the toolbar. Empty state = a primary CTA; when
                     products exist, header carries a quieter "Link another"
                     that goes to the same place. The "Get cheapest" button
                     is gone — cheaper option is emphasised via card style
                     and each product carries its own Add-to-list (per §2.4).
                     Hidden entirely when `products` is off (§2.5). -->
                <q-tab-panel v-if="productsEnabled" name="products">
                    <StockItemProductsTab />
                </q-tab-panel>

                <!-- ── Recipes using this ─────────────────────────────── -->
                <q-tab-panel name="recipes">
                    <div v-if="recipesForDetail.length === 0" class="dora-text-muted text-caption q-pa-md">
                        Not used in any saved recipe.
                    </div>
                    <!-- Feedback 2026-08-08: reflow by column count, not by
                         stretching a fixed 3-up breakpoint grid. An auto-fill
                         grid keeps each card near its natural width and adds/
                         removes a whole column as the window resizes, instead
                         of the cards continuously growing/shrinking. -->
                    <div v-else class="stock-detail__recipe-grid">
                        <div
                            v-for="r in recipesForDetail"
                            :key="r.recipe_id"
                        >
                            <!-- wire the
                                 favourite-toggle + add-all-to-list events
                                 RecipeCard emits. Previously dropped, so
                                 "remove from favourites does nothing" and
                                 "every recipe action except Cook is dead"
                                 (feedback L132 / L134) were live defects
                                 on this surface. -->
                            <RecipeCard
                                :recipe="r"
                                :show-filter-by-ingredients="true"
                                @open="goToRecipe"
                                @cook="goToCook"
                                @toggle-favourite="onToggleFavourite"
                                @add-missing="onAddMissing"
                                @add-all-to-list="onAddAllToList"
                                @filter-by-ingredients="onFilterStockByRecipe"
                            />
                        </div>
                    </div>
                </q-tab-panel>

                <!-- ── Substitutes ──────────────────────────────────────
                     Round-17: row redesign per feedback —
                     • dot-only level indicator on the LEFT (no "OK/Mid"
                       short labels);
                     • name in default text colour, not text-primary;
                     • whole row is clickable; opens in the same peek
                       panel (when embedded) or navigates full-page
                       (`open-detail` event from the page lets
                       StockOverview redirect the peek's id without
                       losing the splitter context). -->
                <q-tab-panel name="substitutes">
                    <StockItemSubstitutesTab @open-substitute="onOpenSubstitute" />
                </q-tab-panel>

                <!-- ── Scanning ─────────────────────────────────────────
                     Feedback 2026-08-21: barcodes used to live at the bottom of
                     the Substitutes tab, where nobody would look for them.
                     Feedback 2026-08-24: the tab is now "Scanning" and owns
                     both halves of the scanning story — Dora's own QR label for
                     this item (previously a header button opening a modal) on
                     top, the product's real barcodes underneath. The explainer
                     prose both halves used to carry now lives in Help; the (?)
                     next to each heading goes there.
                     Still gated on the install-wide scanning flag (R-029:
                     when off, the surface stays hidden — scanning isn't an
                     active capability on this install). The tab itself is
                     hidden by the same flag, so this panel only renders when
                     scanning is on. Barcodes show direct registrations +
                     via-Product derivations; Add/Remove available for direct
                     rows only (via-Product live on the Product). -->
                <q-tab-panel name="scanning" class="q-pa-md">
                    <StockItemScanningTab />
                </q-tab-panel>

                <!-- ── On shopping lists ──────────────────────────────────
                     Round-17: dropped the bright primary-coloured
                     "Primary" pill; the quick-add target now reads as a
                     small warning-toned star icon (same idiom as
                     favourites elsewhere). Rows use the cart icon in the
                     avatar slot, default text colour everywhere. -->
                <q-tab-panel name="lists">
                    <div v-if="onLists.length === 0" class="column items-start q-gutter-sm q-pa-md">
                        <div class="dora-text-muted text-caption">
                            Not on any active shopping list.
                        </div>
                        <BaseButton
                            variant="ghost"
                            :icon="ICONS.add_shopping_cart"
                            label="Add to a list"
                            @click="onAddToList"
                        />
                    </div>
                    <q-list v-else separator>
                        <q-item
                            v-for="l in onLists"
                            :key="l.shopping_list_id"
                            clickable
                            @click="goToList(l.shopping_list_id)"
                        >
                            <q-item-section avatar>
                                <q-icon :name="ICONS.shopping_cart" />
                            </q-item-section>
                            <q-item-section>{{ l.name }}</q-item-section>
                            <q-item-section
                                v-if="l.shopping_list_id === primaryListId"
                                side
                            >
                                <q-icon :name="ICONS.star" color="warning" size="18px">
                                    <BaseTooltip>Quick-add target list</BaseTooltip>
                                </q-icon>
                            </q-item-section>
                        </q-item>
                    </q-list>
                </q-tab-panel>

                <!-- ── History (lifecycle timeline) ────────────────────────
                     C-1b.5 / INV-7 / L139: rework the level-only log into a
                     unified item lifecycle. Merges level changes, waste
                     events, list-add provenance, and synthesises Opened /
                     Checked rows from current state. Date-sorted, newest
                     first; entries colour-keyed by event kind. -->
                <!-- Round-17: left padding so the q-timeline's left-positioned
                     icons aren't flush against the inner panel edge.
                     Feedback 2026-09-01: q-pl-md still read as cramped against
                     the panel edge — q-pl-lg gives the icon column real air. -->
                <q-tab-panel name="history" class="q-pl-lg">
                    <StockItemHistoryTab />
                </q-tab-panel>
            </q-tab-panels>
        </div>
        </FadeTransition>

        <BlockedByRecipesDialog :recipe-names="blockedByRecipes" @close="blockedByRecipes = []" />
    </component>
</template>
<script lang="ts" setup>
    // FU-934 (finalisation 06-R32): this page was one ~2,800-line file. The
    // Overview, Products, Substitutes, Scanning and History tabs are their own
    // components now (`components/stock/StockItem*Tab.vue`) and the state they
    // share — the loaded item, busy, the save / reload pair, the edit form,
    // the open tab, the QR label — is `useStockItemDetail`, provided here once.
    // The page keeps the header, the tab strip, the two small panels (Recipes,
    // Lists) and delete.
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import AppSkeleton from 'src/components/AppSkeleton.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BlockedByRecipesDialog from 'src/components/stock/BlockedByRecipesDialog.vue';
    import StockItemHistoryTab from 'src/components/stock/StockItemHistoryTab.vue';
    import StockItemOverviewTab from 'src/components/stock/StockItemOverviewTab.vue';
    import StockItemProductsTab from 'src/components/stock/StockItemProductsTab.vue';
    import StockItemScanningTab from 'src/components/stock/StockItemScanningTab.vue';
    import StockItemSubstitutesTab from 'src/components/stock/StockItemSubstitutesTab.vue';
    import DoraTabs, { type DoraTab } from 'src/components/DoraTabs.vue';
    import FadeTransition from 'src/components/transitions/FadeTransition.vue';
    import { storeToRefs } from 'pinia';
    import { QPage, useQuasar } from 'quasar';
    import RecipeCard from 'src/components/RecipeCard.vue';
    import { useShoppingListActions } from 'src/composables/useShoppingListActions';
    import { useStockItemActions } from 'src/composables/useStockItemActions';
    import { provideStockItemDetail } from 'src/composables/useStockItemDetail';
    import type { Recipe } from 'src/models/recipe';
    import { NormalisedApiError } from 'src/services/api/axiosHttpClient';
    import { useRecipeStore } from 'src/stores/recipeStore';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { computed, ref } from 'vue';
    import { useRoute, useRouter } from 'vue-router';
    import { useConfirm } from 'src/composables/useConfirm';

    const props = defineProps<{ idOverride?: string; embedded?: boolean }>();

    // FU-609 / R-036 — dual-host root. Routed under MainLayout it must root on
    // <q-page> for the layout height contract; embedded inside Stock Overview's
    // peek splitter it is NOT in a q-page-container, so <q-page> can't resolve a
    // layout — fall back to a plain <div> there. Document-scroll either way.
    const rootTag = computed(() => (props.embedded ? 'div' : QPage));

    const emit = defineEmits<{
        (e: 'close'): void;
        /** Round-17: emitted when the user clicks a substitute inside the
         *  embedded peek panel. The parent (StockOverview) listens and
         *  switches the peek's id rather than letting the row routerlink
         *  the user out to a full-page view, which breaks the splitter
         *  context. In full-page mode the handler falls back to router. */
        (e: 'open-detail', stockItemId: string): void;
    }>();

    const route = useRoute();
    const router = useRouter();
    const $q = useQuasar();
    const { confirm } = useConfirm();
    // Phones drop the header buttons to icon-only so the name, QR and Delete
    // fit on one line (feedback 2026-08-16).
    const compactHeader = computed(() => $q.screen.lt.sm);

    // The page's shared state, provided to the tabs. The id is the peek's
    // `idOverride` when embedded, else the route param — and the peek swaps it
    // on a mounted instance, so the context keys everything off this getter.
    const {
        stockItemId,
        detail,
        loading,
        loadError,
        busy,
        buyVerdictInvalidate,
        scanningEnabled,
        productsEnabled,
        tab,
        notifyErr,
        withBusyReload,
    } = provideStockItemDetail(() => props.idOverride ?? (route.params.id as string));

    const stockItemStore = useStockItemStore();
    const recipeStore = useRecipeStore();
    const shoppingListStore = useShoppingListStore();
    const { recipes } = storeToRefs(recipeStore);

    const actions = useStockItemActions();
    const slActions = useShoppingListActions();

    async function onAddToList() {
        await withBusyReload(async () => { await actions.addToList(stockItemId.value); });
        // the verdict's stock-band + open-list state both
        // changed. Invalidate so a re-render fetches a fresh answer.
        buyVerdictInvalidate();
    }

    // ── Recipes ──────────────────────────────────────────────────────────
    // Recipe photos on the "Recipes using this" cards follow the user's own
    // preference — this isn't the cookbook, so the cookbook's cards/compact
    // switch has no say here.
    const recipesForDetail = computed<Recipe[]>(() => {
        const ids = new Set((detail.value?.recipes ?? []).map((r) => r.recipe_id));
        return recipes.value.filter((r) => ids.has(r.recipe_id));
    });
    function goToRecipe(recipeId: string) {
        void router.push(`/cookbook/${recipeId}`);
    }
    function goToCook(recipeId: string) {
        void router.push(`/cookbook/${recipeId}/cook`);
    }
    async function onAddMissing(_recipeId: string, stockItemIds: string[]) {
        await addIdsToPrimary(stockItemIds.length ? stockItemIds : [stockItemId.value]);
    }
    // Shared by the recipe-card "add missing" / "add all" actions. With no
    // single quick-add target (0 or 2+ drafts), the first id goes through
    // `addToList`, which resolves the list interactively and returns where it
    // landed; the rest follow it there (StockOverview's bulkAddToPrimary shape).
    async function addIdsToPrimary(ids: string[]) {
        busy.value = true;
        try {
            let listId = shoppingListStore.quickAddTargetListId;
            let rest = ids;
            if (!listId) {
                listId = await actions.addToList(ids[0]!);
                rest = ids.slice(1);
            }
            if (listId && rest.length > 0) {
                await slActions.addItems(listId, rest.map((id) => ({ stock_item_id: id })));
            }
        } finally {
            busy.value = false;
        }
    }
    // Jump back to the stock overview pre-filtered to the recipe's
    // ingredient set. The query param is read by StockOverview on mount;
    // the filter chip surfaces a removable "Ingredients of: <recipe>"
    // pill so the user can clear it without round-tripping.
    function onFilterStockByRecipe(recipeId: string) {
        void router.push({ path: '/stock', query: { recipe: recipeId } });
    }

    // the favourite toggle on this surface
    // was wired to a dead listener. Mirror RecipesOverview's handler shape
    // (toggle on the recipe store; the card re-renders via the store).
    function onToggleFavourite(recipeId: string) {
        const r = recipes.value.find((x) => x.recipe_id === recipeId);
        if (r) void recipeStore.toggleFavouriteAsync(r);
    }
    // Cookable card → "Add all" pushes every ingredient onto the primary
    // draft. Matches the existing onAddMissing pattern (no picker dialog
    // on this surface — RecipesOverview's richer picker is overkill here).
    async function onAddAllToList(recipeId: string) {
        const recipe = recipes.value.find((r) => r.recipe_id === recipeId);
        if (!recipe || recipe.ingredients.length === 0) return;
        const ids = recipe.ingredients
            .map((ing) => ing.stock_item_id)
            .filter((id): id is string => !!id);
        if (ids.length === 0) return;
        await addIdsToPrimary(ids);
    }

    // ── Substitutes ──────────────────────────────────────────────────────
    /** Click on a substitute row. When the detail page is hosted inside
     *  the splitter peek (embedded mode), emit up so the parent can flip
     *  the peek id in-place — preserves the splitter context. In
     *  full-page mode, fall back to a normal router navigation. */
    function onOpenSubstitute(substituteId: string) {
        if (props.embedded) {
            emit('open-detail', substituteId);
        } else {
            actions.openDetail(substituteId);
        }
    }

    // ── On shopping lists ────────────────────────────────────────────────
    // Round-18: defensively drop any 'done' lists. `unticked_list_ids`
    // shouldn't include finished lists in the first place (items there
    // are ticked off), but the client-side guard means a stray
    // historical id never shows up in the Lists tab as a phantom row.
    const onLists = computed(() => {
        const m = shoppingListStore.membership;
        const entry = m?.items.find((i) => i.stock_item_id === stockItemId.value);
        const ids = entry?.unticked_list_ids ?? [];
        const lookup = new Map((m?.active_lists ?? []).map((l) => [l.shopping_list_id, l]));
        return ids
            .map((lid) => lookup.get(lid))
            .filter((l): l is NonNullable<typeof l> => !!l && l.status !== 'done');
    });
    // the server-inferred primary draft list (R-003) — the
    // Lists tab decorates that row with a styled "Primary" badge instead
    // of plain text.
    const primaryListId = computed(() => shoppingListStore.quickAddTargetListId);

    // Tab definitions for DoraTabs — counts re-evaluate as detail loads /
    // mutates. Products tab is gated by the install-wide feature flag.
    const tabDefinitions = computed<DoraTab[]>(() => {
        const d = detail.value;
        const out: DoraTab[] = [{ name: 'overview', label: 'Overview', icon: ICONS.info }];
        if (productsEnabled.value) {
            out.push({ name: 'products', label: `Products (${d?.products.length ?? 0})`, icon: ICONS.local_offer });
        }
        out.push({ name: 'recipes', label: `Recipes (${d?.recipes.length ?? 0})`, icon: ICONS.menu_book });
        out.push({ name: 'substitutes', label: `Substitutes (${d?.substitutes.length ?? 0})`, icon: ICONS.swap_horiz });
        // Feedback 2026-08-21: barcodes were buried at the bottom of the
        // Substitutes tab. Own tab, same install-wide gate as the rest of the
        // scanning surface.
        // Feedback 2026-08-24: renamed "Scanning" — it now holds this item's QR
        // label as well as its barcodes.
        //
        // Owner 2026-09-05: it carries a barcode count anyway. The 08-24 call
        // was that a barcode count would be "counting half of what's in
        // there" — but the other half is the QR label, of which there is
        // always exactly one, for every item, forever. A constant is not
        // information, so counting it adds nothing and the barcodes are the
        // only part of this tab whose size actually varies. Consistency with
        // the four sibling tabs wins.
        if (scanningEnabled.value) {
            out.push({
                name: 'scanning',
                label: `Scanning (${d?.barcodes.length ?? 0})`,
                icon: ICONS.barcode,
            });
        }
        out.push({ name: 'lists', label: `Lists (${onLists.value.length})`, icon: ICONS.shopping_cart });
        out.push({ name: 'history', label: 'History', icon: ICONS.history });
        return out;
    });
    function goToList(listId: string) {
        void router.push(`/shopping-lists/${listId}`);
    }

    // ── Delete ───────────────────────────────────────────────────────────
    const blockedByRecipes = ref<string[]>([]);
    async function confirmDelete() {
        if (!detail.value) return;
        const item = detail.value;
        const ok = await confirm({
            title: 'Delete stock item',
            message: `Delete "${item.name}"? This can't be undone.`,
            okLabel: 'Delete',
            destructive: true,
        });
        if (ok) await doDelete(item.stock_item_id);
    }
    async function doDelete(id: string) {
        try {
            await stockItemStore.deleteStockItemAsync(id);
            // The item is gone — drop the form's reference so the
            // unsaved-changes guard (FU-156) doesn't prompt about edits
            // to a now-deleted row on the way out.
            detail.value = null;
            if (props.embedded) emit('close');
            // Replace, not push: a pushed /stock left the deleted item's page in
            // history, so a later Back re-mounted it and fetched a 404 detail
            // (FU-969 (8)).
            else void router.replace('/stock');
        } catch (err) {
            // backend refuses delete when the item is still on a recipe,
            // returning 422 with a structured `blocked_by_recipes` list.
            // Surface the recipe names in a dialog rather than a vague toast
            // so the user knows where to act.
            if (err instanceof NormalisedApiError) {
                const blocked = err.details?.blocked_by_recipes;
                if (Array.isArray(blocked) && blocked.length > 0) {
                    blockedByRecipes.value = (blocked as Array<{ name: string }>).map((r) => r.name);
                    return;
                }
            }
            notifyErr('Could not delete this stock item.', err);
        }
    }

    function goBack() {
        if (window.history.length > 1) router.back();
        else void router.push('/stock');
    }
</script>

<style scoped>
    /* Header row: name takes the slack and ellipsises, controls keep their
       intrinsic width. `min-width: 0` overrides the flex default that stops a
       child shrinking below its content. */
    .stock-detail__name {
        flex: 1 1 auto;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .stock-detail__header > :not(.stock-detail__name) {
        flex: 0 0 auto;
    }
    /* Feedback 2026-08-08: recipe cards reflow by column count rather than
       stretching within a Quasar breakpoint grid. auto-fill keeps each card
       within a bounded width band and drops/adds a whole column on resize. */
    .stock-detail__recipe-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
        gap: 16px;
    }
</style>
