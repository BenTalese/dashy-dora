<template>
    <q-page padding>
        <div class="row items-center q-mb-md">
            <BaseButton variant="icon" :icon="ICONS.arrow_back" aria-label="Back to shopping lists" @click="goBack" />
            <q-space />
            <BaseButton
                variant="primary"
                :icon="ICONS.add"
                label="New template"
                @click="onCreate"
            />
        </div>

        <q-banner v-if="loadError" class="dora-bg-negative-soft text-negative q-mb-md" dense rounded>
            {{ loadError }}
        </q-banner>

        <div v-if="loading && templates.length === 0" class="text-center q-py-xl">
            <AppSpinner size="48px" />
        </div>

        <div v-else-if="templates.length === 0" class="text-center dora-text-muted q-py-xl">
            <q-icon :name="ICONS.bookmarks" size="60px" class="q-mb-sm" />
            <div>
                No templates yet. Create one to capture a recurring shop pattern
                (e.g. "Weekly essentials").
            </div>
        </div>

        <div v-else class="row q-col-gutter-md">
            <div
                v-for="template in templates"
                :key="template.template_id"
                class="col-12 col-sm-6 col-md-4"
            >
                <!-- Tapping a card shows what's on it; using it is the button
                     beside the menu, one tap from the grid (2026-10-14). -->
                <q-card
                    flat
                    bordered
                    class="template-card"
                    role="button"
                    tabindex="0"
                    :aria-label="`Show what's on ${template.name}`"
                    @click="openPreview(template)"
                    @keydown.enter.self="openPreview(template)"
                >
                    <q-card-section class="row items-center no-wrap q-gutter-x-sm">
                        <div class="col" style="min-width: 0">
                            <div class="text-h6 ellipsis">
                                <span v-if="editingId !== template.template_id">
                                    {{ template.name }}
                                </span>
                                <q-input
                                    v-else
                                    v-model="renameDraft"
                                    dense
                                    outlined
                                    autofocus
                                    @click.stop
                                    @blur="saveRename(template)"
                                    @keydown.enter.prevent="saveRename(template)"
                                    @keydown.esc.prevent="editingId = null"
                                />
                            </div>
                            <div class="text-caption dora-text-muted">
                                {{ template.line_count }} item{{ template.line_count === 1 ? '' : 's' }}
                                · updated {{ formatDate(template.updated_at) }}
                            </div>
                        </div>
                        <BaseButton
                            variant="secondary"
                            :icon="ICONS.playlist_add_check"
                            label="Use"
                            :aria-label="`Use ${template.name}`"
                            @click.stop="onUse(template)"
                        >
                            <BaseTooltip>Start a new list from this template</BaseTooltip>
                        </BaseButton>
                        <BaseButton
                            variant="icon"
                            :icon="ICONS.more_vert"
                            aria-label="More actions"
                            @click.stop
                        >
                            <q-menu transition-show="jump-down" transition-hide="jump-up">
                                <q-list dense style="min-width: 200px">
                                    <q-item
                                        clickable
                                        v-close-popup
                                        @click="startRename(template)"
                                    >
                                        <q-item-section avatar>
                                            <q-icon :name="ICONS.edit" />
                                        </q-item-section>
                                        <q-item-section>Rename</q-item-section>
                                    </q-item>
                                    <q-item
                                        clickable
                                        v-close-popup
                                        @click="openEditor(template)"
                                    >
                                        <q-item-section avatar>
                                            <q-icon :name="ICONS.open_in_new" />
                                        </q-item-section>
                                        <q-item-section>Edit items</q-item-section>
                                    </q-item>
                                    <q-item
                                        clickable
                                        v-close-popup
                                        @click="onDelete(template)"
                                    >
                                        <q-item-section avatar>
                                            <q-icon :name="ICONS.delete" color="negative" />
                                        </q-item-section>
                                        <q-item-section class="text-negative">
                                            Delete template
                                        </q-item-section>
                                    </q-item>
                                </q-list>
                            </q-menu>
                        </BaseButton>
                    </q-card-section>
                </q-card>
            </div>
        </div>

        <!-- Preview: what's on the template, read-only, with the way to use it. -->
        <BaseDialog
            v-model="previewOpen"
            :title="previewTemplate?.name ?? ''"
            closable
            card-style="width: 520px; max-width: 95vw"
        >
            <q-card-section v-if="previewDetail" class="tpl-dialog__body">
                <q-list v-if="previewDetail.lines.length > 0" separator>
                    <q-item v-for="line in previewDetail.lines" :key="line.line_id" dense class="q-px-none">
                        <q-item-section style="min-width: 0">
                            <q-item-label class="ellipsis">{{ choiceLabel(line) }}</q-item-label>
                            <q-item-label
                                v-if="choiceLabel(line) !== line.stock_item_name"
                                caption
                                class="ellipsis"
                            >
                                {{ line.stock_item_name }}
                            </q-item-label>
                        </q-item-section>
                        <q-item-section side class="tpl-preview__qty">
                            {{ line.quantity == null ? '–' : `× ${line.quantity}` }}
                        </q-item-section>
                    </q-item>
                </q-list>
                <div v-else class="dora-text-muted text-center q-py-md">
                    No items on this template yet.
                </div>
            </q-card-section>
            <q-card-section v-else class="text-center q-py-lg">
                <AppSpinner size="32px" />
            </q-card-section>

            <template #actions>
                <BaseButton
                    variant="ghost"
                    :icon="ICONS.edit"
                    label="Edit items"
                    :disable="!previewTemplate"
                    @click="onEditFromPreview"
                />
                <BaseButton
                    variant="primary"
                    :icon="ICONS.playlist_add_check"
                    label="Use template"
                    :disable="!previewTemplate"
                    :loading="using"
                    @click="onUseFromPreview"
                />
            </template>
        </BaseDialog>

        <!-- Edit-items dialog. A fixed width capped to the viewport rather than
             a 480px floor, which overran a phone. -->
        <BaseDialog
            v-model="editorOpen"
            :title="editingDetail?.name ?? 'Loading…'"
            closable
            card-style="width: 640px; max-width: 95vw"
        >
                <q-card-section v-if="editingDetail" class="tpl-dialog__body">
                    <div class="text-caption dora-text-muted q-mb-md">
                        {{ editingDetail.lines.length }} item{{
                            editingDetail.lines.length === 1 ? '' : 's'
                        }}
                    </div>
                    <q-select
                        v-model="lineAddSelection"
                        use-input
                        input-debounce="200"
                        :options="addableStockItems"
                        option-value="stock_item_id"
                        option-label="name"
                        emit-value
                        map-options
                        outlined
                        dense
                        clearable
                        label="Add a stock item…"
                        @filter="onLineFilter"
                        @update:model-value="onAddTemplateLine"
                    >
                        <template #no-option>
                            <q-item>
                                <q-item-section class="dora-text-muted">
                                    No matching stock items.
                                </q-item-section>
                            </q-item>
                        </template>
                    </q-select>

                    <q-list bordered separator class="q-mt-md">
                        <div
                            v-for="line in editingDetail.lines"
                            :key="line.line_id"
                            class="tpl-line"
                        >
                            <!-- The list row's picker, so a template's "which
                                 one" is chosen the same way a list's is. -->
                            <div class="tpl-line__name">
                                <LineChoicePicker
                                    v-if="hasLineChoices(choiceFor(line), productsEnabled)"
                                    :choice="choiceFor(line)"
                                    @pick-offer="setLineChoice(line, { selected_product_id: $event })"
                                    @pick-hint="setLineChoice(line, { preferred_buy_id: $event })"
                                />
                                <span v-else class="ellipsis">{{ line.stock_item_name }}</span>
                            </div>
                            <div class="row items-center no-wrap tpl-line__qty">
                                <BaseButton
                                    variant="icon"
                                    size="sm"
                                    :icon="ICONS.remove"
                                    aria-label="Decrease quantity"
                                    :disable="(line.quantity ?? 0) <= 0"
                                    @click="adjustLineQuantity(line, -1)"
                                />
                                <q-input
                                    :model-value="line.quantity ?? ''"
                                    dense
                                    borderless
                                    type="number"
                                    :min="0"
                                    input-class="text-center"
                                    style="width: 36px"
                                    placeholder="–"
                                    aria-label="Quantity"
                                    @blur="onTemplateQtyBlur(line, $event)"
                                    @keydown.enter.prevent="
                                        ($event.target as HTMLInputElement).blur()
                                    "
                                />
                                <BaseButton
                                    variant="icon"
                                    size="sm"
                                    :icon="ICONS.add"
                                    aria-label="Increase quantity"
                                    @click="adjustLineQuantity(line, 1)"
                                />
                            </div>
                            <BaseButton
                                variant="icon"
                                class="tpl-line__remove"
                                :icon="ICONS.delete_outline"
                                aria-label="Remove"
                                @click="onRemoveLine(line.line_id)"
                            />
                        </div>
                        <q-item v-if="editingDetail.lines.length === 0">
                            <q-item-section class="dora-text-muted text-center">
                                No items on this template yet.
                            </q-item-section>
                        </q-item>
                    </q-list>
                </q-card-section>

                <template #actions>
                    <BaseButton variant="ghost" label="Done" v-close-popup />
                </template>
        </BaseDialog>
    </q-page>
</template>

<script lang="ts" setup>
    import { ICONS } from 'src/style/icons';
    import { formatDate as formatLocaleDate } from 'src/composables/useDateFormat';
    import AppSpinner from 'src/components/AppSpinner.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import LineChoicePicker from 'src/components/shoppingList/LineChoicePicker.vue';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import { hasLineChoices, pickedLineChoice, type LineChoice } from 'src/models/shoppingList';
    import { useQuasar } from 'quasar';
    import type {
        TemplateDetail,
        TemplateLine,
        TemplateSummary,
        UpdateTemplateLineCommand,
    } from 'src/models/shoppingListTemplate';
    import ShoppingListTemplateApiService from 'src/services/api/shoppingListTemplateApiService';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { computed, onMounted, ref } from 'vue';
    import { useRouter } from 'vue-router';
    import { describeApiError, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useConfirm } from 'src/composables/useConfirm';

    const $q = useQuasar();

    const { confirm, prompt } = useConfirm();
    const router = useRouter();
    const shoppingListStore = useShoppingListStore();
    const api = new ShoppingListTemplateApiService();
    const stockItemStore = useStockItemStore();
    const { products: productsEnabled } = useFeatureFlags();

    const templates = ref<TemplateSummary[]>([]);
    const loading = ref(false);
    const loadError = ref<string | null>(null);

    const editingId = ref<string | null>(null);
    const renameDraft = ref('');

    const previewOpen = ref(false);
    const previewTemplate = ref<TemplateSummary | null>(null);
    const previewDetail = ref<TemplateDetail | null>(null);
    const using = ref(false);

    const editorOpen = ref(false);
    const editingDetail = ref<TemplateDetail | null>(null);
    const lineAddSelection = ref<string | null>(null);
    const lineFilter = ref('');

    const addableStockItems = computed(() => {
        const existing = new Set(
            (editingDetail.value?.lines ?? []).map((l) => l.stock_item_id)
        );
        const q = lineFilter.value.toLowerCase();
        return stockItemStore.stockItems
            .filter((si) => !existing.has(si.stock_item_id))
            .filter((si) => !q || si.name.toLowerCase().includes(q))
            .map((si) => ({ stock_item_id: si.stock_item_id, name: si.name }));
    });

    function formatDate(iso: string): string {
        try {
            return formatLocaleDate(iso) || iso;
        } catch {
            return iso;
        }
    }

    function goBack() {
        void router.push('/shopping-lists');
    }

    async function load() {
        loading.value = true;
        loadError.value = null;
        try {
            templates.value = await api.getAllAsync();
        } catch (err) {
            loadError.value = `Could not load templates: ${describeApiError(err)}`;
        } finally {
            loading.value = false;
        }
    }

    async function onCreate() {
        const name = await prompt({
            title: 'New template',
            message: 'What is this template called? (e.g. "Weekly essentials")',
        });
        if (!name) return;
        try {
            const { template_id } = await api.createAsync({ name });
            await load();
            const created = templates.value.find((t) => t.template_id === template_id);
            if (created) await openEditor(created);
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not create template.',
                caption: toastCaption(err),
            });
        }
    }

    function startRename(template: TemplateSummary) {
        editingId.value = template.template_id;
        renameDraft.value = template.name;
    }

    async function saveRename(template: TemplateSummary) {
        const next = renameDraft.value.trim();
        if (!next || next === template.name) {
            editingId.value = null;
            return;
        }
        try {
            await api.updateAsync(template.template_id, { name: next });
            await load();
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not rename.',
                caption: toastCaption(err),
            });
        } finally {
            editingId.value = null;
        }
    }

    async function onDelete(template: TemplateSummary) {
        const ok = await confirm({
            title: `Delete "${template.name}"?`,
            message: 'This removes the template. Shopping lists previously created from it are unaffected.',
            okLabel: 'Delete',
            destructive: true,
        });
        if (!ok) return;
        try {
            await api.deleteAsync(template.template_id);
            await load();
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not delete.',
                caption: toastCaption(err),
            });
        }
    }

    async function onUse(template: TemplateSummary) {
        using.value = true;
        try {
            const result = await api.instantiateAsync(template.template_id, {});
            // The lists picker reads the shared store, which is already
            // hydrated, so without this the new list was missing from it
            // until a reload (owner 2026-10-15).
            await shoppingListStore.refreshAsync();
            $q.notify({
                type: 'positive',
                message: `Created list with ${result.line_count} item${
                    result.line_count === 1 ? '' : 's'
                }.`,
            });
            if (result.shopping_list_id) {
                void router.push(`/shopping-lists/${result.shopping_list_id}`);
            }
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not create list.',
                caption: toastCaption(err),
            });
        } finally {
            using.value = false;
        }
    }

    async function openPreview(template: TemplateSummary) {
        if (editingId.value === template.template_id) return;
        previewTemplate.value = template;
        previewDetail.value = null;
        previewOpen.value = true;
        try {
            previewDetail.value = await api.getDetailAsync(template.template_id);
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not load template.',
                caption: toastCaption(err),
            });
            previewOpen.value = false;
        }
    }

    function onEditFromPreview() {
        const template = previewTemplate.value;
        if (!template) return;
        previewOpen.value = false;
        void openEditor(template);
    }

    function onUseFromPreview() {
        if (previewTemplate.value) void onUse(previewTemplate.value);
    }

    function choiceFor(line: TemplateLine): LineChoice {
        return {
            itemName: line.stock_item_name,
            offers: line.offers,
            preferredBuys: line.preferred_buys,
            selectedProductId: line.selected_product_id,
            preferredBuyId: line.preferred_buy_id,
        };
    }

    /** What the line will be called on the list: the picked offer or
     *  preferred buy, else the item. */
    function choiceLabel(line: TemplateLine): string {
        return pickedLineChoice(choiceFor(line), productsEnabled.value)?.label ?? line.stock_item_name;
    }

    async function setLineChoice(
        line: TemplateLine,
        command: Pick<UpdateTemplateLineCommand, 'selected_product_id' | 'preferred_buy_id'>,
    ) {
        if (!editingDetail.value) return;
        const previous = { product: line.selected_product_id, preferredBuy: line.preferred_buy_id };
        if ('selected_product_id' in command) line.selected_product_id = command.selected_product_id ?? null;
        if ('preferred_buy_id' in command) line.preferred_buy_id = command.preferred_buy_id ?? null;
        try {
            await api.updateLineAsync(editingDetail.value.template_id, line.line_id, command);
        } catch (err) {
            line.selected_product_id = previous.product;
            line.preferred_buy_id = previous.preferredBuy;
            $q.notify({
                type: 'negative',
                message: 'Could not update the item.',
                caption: toastCaption(err),
            });
        }
    }

    async function openEditor(template: TemplateSummary) {
        editingDetail.value = null;
        editorOpen.value = true;
        try {
            editingDetail.value = await api.getDetailAsync(template.template_id);
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not load template.',
                caption: toastCaption(err),
            });
            editorOpen.value = false;
        }
    }

    function onLineFilter(value: string, update: (cb: () => void) => void) {
        update(() => {
            lineFilter.value = value;
        });
    }

    async function onAddTemplateLine(stockItemId: string | null) {
        if (!stockItemId || !editingDetail.value) return;
        lineAddSelection.value = null;
        try {
            await api.addLineAsync(editingDetail.value.template_id, {
                stock_item_id: stockItemId,
            });
            // Reload detail and refresh summary count.
            await Promise.all([
                api.getDetailAsync(editingDetail.value.template_id).then((d) => {
                    editingDetail.value = d;
                }),
                load(),
            ]);
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not add item.',
                caption: toastCaption(err),
            });
        }
    }

    async function setLineQuantity(line: TemplateLine, next: number | null) {
        if (!editingDetail.value || line.quantity === next) return;
        const previous = line.quantity;
        line.quantity = next;
        try {
            await api.updateLineAsync(editingDetail.value.template_id, line.line_id, {
                quantity: next,
            });
        } catch (err) {
            line.quantity = previous;
            $q.notify({
                type: 'negative',
                message: 'Could not update quantity.',
                caption: toastCaption(err),
            });
        }
    }

    async function adjustLineQuantity(line: TemplateLine, delta: number) {
        const current = line.quantity ?? 0;
        await setLineQuantity(line, Math.max(0, current + delta));
    }

    function onTemplateQtyBlur(line: TemplateLine, event: Event) {
        // Mirrors the shopping-list quantity input behaviour: blank ⇒ null,
        // valid integer ⇒ persist, garbage ⇒ revert.
        const target = event.target as HTMLInputElement;
        const raw = target.value.trim();
        if (raw === '') {
            void setLineQuantity(line, null);
            return;
        }
        const parsed = Number.parseInt(raw, 10);
        if (Number.isFinite(parsed) && parsed >= 0) {
            void setLineQuantity(line, parsed);
        } else {
            // Reset the visible value back to the canonical one.
            const current = line.quantity;
            line.quantity = null;
            void Promise.resolve().then(() => {
                line.quantity = current;
            });
        }
    }

    async function onRemoveLine(lineId: string) {
        if (!editingDetail.value) return;
        try {
            await api.deleteLineAsync(editingDetail.value.template_id, lineId);
            await Promise.all([
                api.getDetailAsync(editingDetail.value.template_id).then((d) => {
                    editingDetail.value = d;
                }),
                load(),
            ]);
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not remove item.',
                caption: toastCaption(err),
            });
        }
    }

    onMounted(async () => {
        await load();
        await stockItemStore.ensureLoadedAsync();
    });
</script>

<style scoped>
    .template-card {
        cursor: pointer;
        transition: transform var(--motion-fast) var(--motion-ease), box-shadow var(--motion-fast) var(--motion-ease);
    }
    .template-card:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    .template-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 14px var(--overlay-active);
    }
    /* Name | quantity stepper | remove. The name takes what's left and
       truncates, so the row fits a phone. */
    .tpl-line {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto auto;
        grid-template-areas: "name qty del";
        align-items: center;
        gap: var(--space-1);
        padding: var(--space-1) var(--space-1) var(--space-1) var(--space-3);
        min-height: 48px;
    }
    /* On a phone the name gets its own line, so it isn't cut to a few
       letters by the stepper. */
    @media (max-width: 599px) {
        .tpl-line {
            grid-template-areas:
                "name name name"
                ".    qty  del";
            row-gap: 0;
            padding-top: var(--space-2);
        }
    }
    .tpl-line + .tpl-line {
        border-top: 1px solid var(--divider);
    }
    .tpl-line__name {
        grid-area: name;
        min-width: 0;
        display: flex;
        font-size: var(--font-size-md);
    }
    /* The picker is sized for a list row; here it reads at the same size as
       a plain name beside it. */
    .tpl-line__name .line-choice {
        font-size: inherit;
    }
    .tpl-line__qty {
        grid-area: qty;
    }
    .tpl-line__remove {
        grid-area: del;
    }
    .tpl-dialog__body {
        max-height: 70vh;
        overflow-y: auto;
    }
    .tpl-preview__qty {
        font-variant-numeric: tabular-nums;
        color: var(--text-secondary);
    }
</style>
