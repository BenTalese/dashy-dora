<template>
    <!-- Owner feedback 2026-08-27 — the one bulk "add these to a list" surface.
         Was `RecipeIngredientPickerDialog` (recipes only); meal plans had a
         one-shot "Generate shopping list" button that showed you nothing and
         let you veto nothing. Both now render this, so the flow can't drift
         (R-001/R-003). Two enrichments landed with the move: every row can say
         how much is needed and *what requires it*, and ingredients that never
         got linked to a pantry item are named in the footer instead of being
         dropped in silence. -->
    <BaseDialog
        v-model="open"
        :title="titleText"
        closable
        card-style="min-width: 0; width: min(560px, 92vw)"
    >
        <q-card-section>
            <q-select
                v-model="targetListId"
                :options="listOptions"
                emit-value
                map-options
                outlined
                dense
                label="Add to"
            />
            <q-input
                v-if="targetListId === NEW_LIST"
                v-model="newListName"
                outlined
                dense
                class="q-mt-sm"
                label="New list name"
                :error="newListNameTouched && !newListName.trim()"
                error-message="Give the list a name."
                @blur="newListNameTouched = true"
            />
        </q-card-section>

        <q-separator />

        <!-- Owner feedback 2026-09-08: the rows ran together as one block of
             text — a dense list of two-line items with nothing between them.
             They're separated now, and no longer dense: each row is a tap
             target carrying a name, a caption and a state chip, which is more
             than a dense row's height can hold legibly (D-004). -->
        <q-card-section class="q-pt-sm add-to-list__list">
            <q-list separator>
                <AddToListRowItem
                    v-for="row in requiredRows"
                    :key="row.stockItemId"
                    :row="row"
                    :checked="selected[row.stockItemId] ?? false"
                    :on-list-label="onListLabel(row.stockItemId)"
                    @toggle="toggle(row.stockItemId)"
                />

                <!-- Cookbook revision §1.9 — optional ingredients section.
                     Unchecked by default regardless of stock level. A section
                     heading rather than the old em-dash-padded fake rule: it
                     reads as a heading at any width, and it can't be mistaken
                     for a row you're meant to tick. -->
                <div v-if="optionalRows.length > 0" class="add-to-list__grouphead">
                    Optional
                </div>
                <AddToListRowItem
                    v-for="row in optionalRows"
                    :key="row.stockItemId"
                    :row="row"
                    :checked="selected[row.stockItemId] ?? false"
                    :on-list-label="onListLabel(row.stockItemId)"
                    @toggle="toggle(row.stockItemId)"
                />

                <q-item v-if="rows.length === 0">
                    <q-item-section class="dora-text-muted text-center">
                        No ingredients to add.
                    </q-item-section>
                </q-item>
            </q-list>
        </q-card-section>

        <!-- FU-505's guarantee, kept alive now that the picker (not the
             auto-generate endpoint) does the adding. Hide-when-empty, R-029. -->
        <q-card-section v-if="unlinkedRows.length > 0" class="q-pt-none">
            <div class="add-to-list__unlinked">
                <q-icon :name="ICONS.info" size="18px" class="add-to-list__unlinked-icon" />
                <div>
                    {{ unlinkedRows.length }}
                    ingredient{{ unlinkedRows.length === 1 ? " isn't" : "s aren't" }}
                    linked to your pantry, so
                    {{ unlinkedRows.length === 1 ? 'it' : 'they' }}
                    can't go on a list. Add
                    {{ unlinkedRows.length === 1 ? 'it' : 'them' }}
                    by hand, or link
                    {{ unlinkedRows.length === 1 ? 'it' : 'them' }}
                    from the recipe.
                    <ul class="add-to-list__unlinked-items">
                        <li v-for="(u, i) in unlinkedRows" :key="`${u.sourceName}-${u.ingredientName}-${i}`">
                            {{ u.ingredientName }}
                            <span class="dora-text-muted">· {{ u.sourceName }}</span>
                        </li>
                    </ul>
                </div>
            </div>
        </q-card-section>

        <template #actions>
            <BaseButton variant="subtle" label="Select all" @click="selectAll" />
            <BaseButton variant="subtle" label="Select missing" @click="selectMissing" />
            <q-space />
            <BaseButton variant="ghost" label="Cancel" v-close-popup />
            <BaseButton
                label="Add"
                :loading="busy"
                :disable="!canConfirm"
                @click="onConfirm"
            />
        </template>
    </BaseDialog>
</template>

<script lang="ts" setup>
    import AddToListRowItem from 'src/components/shoppingList/AddToListRowItem.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import { ICONS } from 'src/style/icons';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { cartStateFor, type Membership } from 'src/models/shoppingList';
    import type {
        AddToListConfirm, AddToListRow, AddToListUnlinked,
    } from 'src/components/shoppingList/addToListTypes';
    import { storeToRefs } from 'pinia';
    import { computed, ref, watch } from 'vue';

    /** Sentinel for the "start a fresh list" option. The caller creates it —
     *  the dialog only reports which target was chosen. */
    const NEW_LIST = '__new_list__';

    const props = withDefaults(
        defineProps<{
            modelValue: boolean;
            title?: string;
            rows: AddToListRow[];
            unlinked?: AddToListUnlinked[];
            /** Default name offered when "New list" is picked ("Meals: week of
             *  25 Aug"). The old one-shot generate button named the week's list
             *  for you; keeping that name here is why nothing was lost when it
             *  was replaced. */
            defaultNewListName?: string;
            /** When provided, these ids start checked (minus anything already
             *  on a list). Otherwise the default policy applies. */
            initialCheckedIds?: string[] | undefined;
        }>(),
        {
            title: 'Add to a list',
            unlinked: () => [],
            defaultNewListName: 'Shopping list',
            initialCheckedIds: undefined,
        },
    );

    const emit = defineEmits<{
        (e: 'update:modelValue', v: boolean): void;
        (e: 'confirm', payload: AddToListConfirm): void;
    }>();

    const busy = ref(false);
    const open = computed({
        get: () => props.modelValue,
        set: (v) => emit('update:modelValue', v),
    });

    const shoppingListStore = useShoppingListStore();
    const { membership: storeMembership } = storeToRefs(shoppingListStore);
    const membership = computed<Membership | null>(
        () => (storeMembership.value as Membership | null) ?? null,
    );

    // `exactOptionalPropertyTypes` makes an optional prop `T | undefined` in
    // the template even with a `withDefaults` default, so both defaulted props
    // are read through a computed rather than dotted directly.
    const titleText = computed(() => props.title ?? 'Add to a list');
    const unlinkedRows = computed(() => props.unlinked ?? []);

    const rows = computed(() => props.rows);
    const requiredRows = computed(() => rows.value.filter((r) => !r.isOptional));
    const optionalRows = computed(() => rows.value.filter((r) => r.isOptional));

    // Owner feedback 2026-08-27 — "New list" is a first-class option here.
    // The recipe page used to dead-end with a "no active shopping list, go
    // make one" dialog, which is three taps and a navigation to do the thing
    // you already asked for.
    const listOptions = computed(() => [
        ...shoppingListStore.summaries
            .filter((s) => s.status !== 'done')
            .map((s) => ({ label: s.display_name, value: s.shopping_list_id })),
        { label: '+ New list', value: NEW_LIST },
    ]);
    const targetListId = ref<string | null>(null);
    const newListName = ref('');
    const newListNameTouched = ref(false);

    function isOnList(stockItemId: string): boolean {
        return cartStateFor(stockItemId, membership.value) !== 'none';
    }

    /** The single unticked list an item is on, by name — null when it's on
     *  none, and a generic label when it's on several. */
    function onListLabel(stockItemId: string): string | null {
        const entry = membership.value?.items.find((i) => i.stock_item_id === stockItemId);
        if (!entry || entry.unticked_list_ids.length === 0) return null;
        if (entry.unticked_list_ids.length > 1) return 'On several lists';
        const id = entry.unticked_list_ids[0];
        const name = shoppingListStore.summaries
            .find((s) => s.shopping_list_id === id)?.display_name;
        return name ? `On ${name}` : 'On a list';
    }

    const selected = ref<Record<string, boolean>>({});

    function applyDefaults() {
        const next: Record<string, boolean> = {};
        const initialSet = props.initialCheckedIds ? new Set(props.initialCheckedIds) : null;
        for (const row of rows.value) {
            // Owner feedback 2026-08-24 — never *propose* adding something
            // that's already on a list. The checkbox stays live, so the user
            // can still choose to add a second line; we just don't ask for it.
            if (isOnList(row.stockItemId)) {
                next[row.stockItemId] = false;
                continue;
            }
            if (initialSet) {
                next[row.stockItemId] = initialSet.has(row.stockItemId);
                continue;
            }
            if (row.isOptional) {
                next[row.stockItemId] = false;
                continue;
            }
            next[row.stockItemId] = row.isMissing || row.isLowStock;
        }
        selected.value = next;
    }

    watch(
        () => props.modelValue,
        (isOpen) => {
            if (!isOpen) return;
            targetListId.value =
                shoppingListStore.quickAddTargetListId
                ?? listOptions.value[0]?.value
                ?? NEW_LIST;
            newListName.value = props.defaultNewListName;
            newListNameTouched.value = false;
            applyDefaults();
        },
        { immediate: true },
    );

    // Rows can arrive after the dialog opens (the meal-plan aggregate is
    // fetched), so re-apply the tick policy when the set changes rather than
    // leaving every row unticked.
    watch(() => props.rows, () => { if (props.modelValue) applyDefaults(); });

    const checkedCount = computed(
        () => rows.value.filter((r) => selected.value[r.stockItemId]).length,
    );
    const canConfirm = computed(() => {
        if (checkedCount.value === 0 || !targetListId.value) return false;
        if (targetListId.value === NEW_LIST) return newListName.value.trim().length > 0;
        return true;
    });

    function toggle(id: string) {
        selected.value = { ...selected.value, [id]: !selected.value[id] };
    }

    function selectAll() {
        // §1.9 — "all" still excludes optional rows; users opt into those
        // individually. Rows already on a list are excluded for the same
        // reason they start unticked.
        const next: Record<string, boolean> = {};
        for (const row of rows.value) {
            next[row.stockItemId] = !row.isOptional && !isOnList(row.stockItemId);
        }
        selected.value = next;
    }

    function selectMissing() {
        const next: Record<string, boolean> = {};
        for (const row of rows.value) {
            if (row.isOptional || isOnList(row.stockItemId)) {
                next[row.stockItemId] = false;
                continue;
            }
            next[row.stockItemId] = row.isMissing || row.isLowStock;
        }
        selected.value = next;
    }

    function onConfirm() {
        if (!canConfirm.value) return;
        const ids = rows.value
            .filter((r) => selected.value[r.stockItemId])
            .map((r) => r.stockItemId);
        emit('confirm', {
            stockItemIds: ids,
            targetListId: targetListId.value === NEW_LIST ? null : targetListId.value,
        });
    }

    defineExpose({
        setBusy: (v: boolean) => { busy.value = v; },
        /** The name to give the list when `targetListId` came back null. */
        newListName: computed(() => newListName.value.trim()),
    });
</script>

<style scoped>
    .add-to-list__list {
        max-height: 360px;
        overflow-y: auto;
    }
    /* Same treatment the cost breakdown's group heads wear, so the two
       recipe-side dialogs label their groups the same way. */
    .add-to-list__grouphead {
        margin-top: var(--space-3, 12px);
        padding: var(--space-2, 8px) var(--space-4, 16px) var(--space-1, 4px);
        font-size: calc(var(--font-size-xs) * 1rem);
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--text-muted);
    }
    /* Says "here's what we couldn't take" — informational, so it borrows the
       hint treatment rather than a warning colour (D-013). */
    .add-to-list__unlinked {
        display: flex;
        align-items: flex-start;
        gap: 0.5rem;
        padding: 0.5rem 0.65rem;
        background: var(--surface-sunken);
        border: 1px solid var(--border-default);
        border-radius: 8px;
        font-size: calc(var(--font-size-sm) * 1rem);
        color: var(--text-secondary);
        line-height: 1.35;
    }
    .add-to-list__unlinked-icon {
        flex: 0 0 auto;
        margin-top: 1px;
        color: var(--text-secondary);
    }
    .add-to-list__unlinked-items {
        margin: 0.35rem 0 0;
        padding-left: 1.1rem;
    }
</style>
