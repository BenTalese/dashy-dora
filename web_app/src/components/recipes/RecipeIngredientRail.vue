<template>
    <div class="rn__rail">
        <section aria-labelledby="rnIng">
            <!-- Owner feedback 2026-08-27 - the ingredient list is
                 a *list* until you press the pencil. It shipped
                 with every editing affordance permanently on: a
                 row that opened an edit dialog on tap, reorder
                 arrows, a delete button. Reading a recipe and
                 rewriting one are different jobs, and the header
                 already had the shape that separates them
                 (R-055), so the rail wears it too. -->
            <div class="rn__sechead">
                <h2 class="rn__sectitle" id="rnIng">Ingredients</h2>
                <HelpHint topic="Ingredients and the pantry" />
                <span class="rn__seccount">{{ form.ingredients.length }}</span>
                <BaseButton
                    class="rn__secedit"
                    :variant="ingredientsEditing ? 'secondary' : 'icon'"
                    dense
                    :icon="ingredientsEditing ? ICONS.check : ICONS.edit"
                    :label="ingredientsEditing ? 'Done' : undefined"
                    :aria-label="ingredientsEditing ? 'Finish editing the ingredients' : 'Edit the ingredients'"
                    :aria-pressed="ingredientsEditing"
                    :loading="ingredientsEditing && saveState === 'saving'"
                    @click="onToggleIngredientsEdit"
                >
                    <BaseTooltip v-if="!ingredientsEditing">Edit the ingredients</BaseTooltip>
                </BaseButton>
            </div>

            <div class="rn__pane">
                <!-- A section is a container, so it looks like one:
                     a card holding its own name, its own rows and
                     (while editing) its own add button. -->
                <div
                    v-for="group in ingredientGroups"
                    :key="group.key"
                    class="rn__group"
                    :class="{ 'rn__group--card': group.sectionId !== null }"
                >
                    <div v-if="group.sectionId !== null" class="rn__grouphead">
                        <!-- "Look pretty for view mode, be a proper
                             input for edit mode" (owner, 2026-08-27).
                             The `q-popup-edit` this replaced was the
                             middle thing that is neither: a heading
                             you had to discover was clickable, which
                             then opened a field somewhere else. -->
                        <h3 v-if="!ingredientsEditing" class="rn__groupname">
                            {{ group.name }}
                        </h3>
                        <q-input
                            v-else
                            :model-value="sectionNameOf(group.sectionId)"
                            dense outlined
                            class="rn__groupfield"
                            label="Section name"
                            placeholder="For the sauce"
                            @update:model-value="(v) => renameSection(String(group.sectionId), String(v ?? ''))"
                        />
                        <span class="rn__groupcount">{{ group.rows.length }}</span>
                        <BaseButton
                            v-if="ingredientsEditing"
                            variant="icon"
                            dense
                            :icon="ICONS.more_vert"
                            :aria-label="`Section options for ${group.name}`"
                        >
                            <q-menu auto-close>
                                <q-list dense style="min-width: 190px">
                                    <q-item
                                        clickable
                                        :disable="sectionIndexOf(group.sectionId) === 0"
                                        @click="moveSection(String(group.sectionId), -1)"
                                    >
                                        <q-item-section avatar>
                                            <q-icon :name="ICONS.arrow_upward" />
                                        </q-item-section>
                                        <q-item-section>Move section up</q-item-section>
                                    </q-item>
                                    <q-item
                                        clickable
                                        :disable="sectionIndexOf(group.sectionId) === form.sections.length - 1"
                                        @click="moveSection(String(group.sectionId), 1)"
                                    >
                                        <q-item-section avatar>
                                            <q-icon :name="ICONS.arrow_downward" />
                                        </q-item-section>
                                        <q-item-section>Move section down</q-item-section>
                                    </q-item>
                                    <q-separator />
                                    <q-item clickable @click="removeSection(String(group.sectionId))">
                                        <q-item-section avatar>
                                            <q-icon :name="ICONS.delete" color="negative" />
                                        </q-item-section>
                                        <q-item-section>
                                            Remove section
                                            <q-item-label caption>
                                                Its ingredients move to the main list
                                            </q-item-label>
                                        </q-item-section>
                                    </q-item>
                                </q-list>
                            </q-menu>
                        </BaseButton>
                    </div>

                    <ul class="rn__ing">
                        <li
                            v-for="(row, rowIndex) in group.rows"
                            :key="row.client_id"
                            class="rn__ing--target"
                            :class="{ 'rn__ing--lit': litIngredients.has(String(row.client_id)) }"
                            role="button"
                            tabindex="0"
                            :aria-pressed="!ingredientsEditing && selectedIngredientId === row.client_id"
                            :aria-label="ingredientsEditing
                                ? `Edit ${ingredientLabel(row)}`
                                : `${ingredientLabel(row)} - highlight the steps that use it`"
                            @click="onIngredientRowActivate(String(row.client_id))"
                            @keydown.enter.prevent="onIngredientRowActivate(String(row.client_id))"
                            @keydown.space.prevent="onIngredientRowActivate(String(row.client_id))"
                        >
                            <span class="rn__qty">
                                {{ formatQuantity(row.quantity, row.unit) || '–' }}
                            </span>
                            <span class="rn__ingname">
                                <span class="rn__ingtext">{{ ingredientLabel(row) }}</span>
                                <span v-if="ingredientItemCaption(row)" class="rn__ingitem">{{ ingredientItemCaption(row) }}</span>
                                <q-chip v-if="row.is_optional" dense square size="sm" class="rn__chip">Optional</q-chip>
                                <!-- A row with neither an item nor text is
                                     the one thing that can refuse the save,
                                     so it says so on the row instead of only
                                     in the save message. -->
                                <q-chip
                                    v-if="isHalfBuilt(row)"
                                    dense square size="sm"
                                    color="warning"
                                    text-color="dark"
                                    class="rn__chip"
                                    clickable
                                    @click.stop="openRowEditor(String(row.client_id))"
                                >
                                    Needs an item
                                </q-chip>
                                <q-chip
                                    v-else-if="!row.stock_item_id"
                                    dense square size="sm"
                                    class="rn__chip rn__chip--unlinked"
                                >
                                    Free text
                                    <BaseTooltip>
                                        Not linked to a pantry item, so Dora
                                        can't tell whether you have it.
                                    </BaseTooltip>
                                </q-chip>
                                <span v-if="row.notes" class="rn__ingnote">{{ row.notes }}</span>
                            </span>

                            <!-- Pantry state, in its own column.
                                 Owner 2026-09-03: *"swappable/missing/etc
                                 chip is too close to the ingredient name.
                                 Perhaps put it to the left of the shopping
                                 button with some margin?"* These two are the
                                 only chips on the row that are facts about
                                 the *pantry* rather than about the
                                 ingredient line you're reading, and they are
                                 the two the cart button acts on - so they
                                 belong beside it, at a fixed x, not tacked
                                 onto the end of a name whose length varies
                                 row to row. The authoring chips (Optional /
                                 Free text / Needs an item) stay with the
                                 name, because that is what they describe.
                                 `v-if`'d as a whole rather than left
                                 to collapse: an empty flex span is
                                 still a box, and measuring the running
                                 page showed the column costing its 8px
                                 margin on all twelve rows of a recipe
                                 with nothing to report (R-075). -->
                            <span v-if="hasPantryState(row)" class="rn__ingstate" @click.stop>
                                <!-- "Missing" and "missing, but you have
                                     something you could use instead" are
                                     different answers to tonight's
                                     question, and since 2026-08-31 they are
                                     one chip rather than two sitting side
                                     by side (owner: *"can missing and
                                     swappable be combined into one ui
                                     element somehow?"*). The chip owns the
                                     swaps menu too. Editing the list, none
                                     of this is relevant - what's in the
                                     pantry is not what you came to change
                                     (owner, same round) - so it doesn't
                                     render at all in edit mode. -->
                                <RecipeMissingIngredientChip
                                    v-if="!ingredientsEditing
                                        && row.stock_item_id
                                        && isIngredientMissing(row.stock_item_id)"
                                    :entries="substitutesForRow(row)"
                                    :ingredient-name="ingredientLabel(row)"
                                />
                                <!-- Owner feedback 2026-09-01 — *"ensure
                                     missing and use soon chips are styled
                                     the same"*. This was a solid `q-chip`
                                     with dark ink sitting immediately beside
                                     the tinted missing-chip: two systems on
                                     one line. Both now wear the shared
                                     `.dora-chip--tint` from `colours.scss`. -->
                                <span
                                    v-if="expiringChipFor(row.stock_item_id)"
                                    class="dora-chip--tint"
                                    :class="`dora-chip--tint-${expiringChipFor(row.stock_item_id)!.tone}`"
                                >
                                    <q-icon
                                        :name="expiringChipFor(row.stock_item_id)!.icon"
                                        size="14px"
                                    />
                                    <span>{{ expiringChipFor(row.stock_item_id)!.label }}</span>
                                    <BaseTooltip>{{ expiringChipFor(row.stock_item_id)!.tooltip }}</BaseTooltip>
                                </span>
                            </span>
                            <!-- Per-row actions, split by mode. Reading a
                                 recipe, the only thing you want to *do* to
                                 a row is put it on a list - and that has to
                                 be visible, not hover-revealed, because a
                                 thumb has no hover. Editing one, the cart
                                 is noise and the structural controls are
                                 the point (owner feedback 2026-08-27). -->
                            <span class="rn__ingact" @click.stop>
                                <template v-if="ingredientsEditing">
                                    <BaseButton
                                        variant="icon" dense
                                        :icon="ICONS.arrow_upward"
                                        :disable="rowIndex === 0"
                                        :aria-label="`Move ${ingredientLabel(row)} up`"
                                        @click="moveIngredientWithin(group.rows, rowIndex, -1)"
                                    />
                                    <BaseButton
                                        variant="icon" dense
                                        :icon="ICONS.arrow_downward"
                                        :disable="rowIndex === group.rows.length - 1"
                                        :aria-label="`Move ${ingredientLabel(row)} down`"
                                        @click="moveIngredientWithin(group.rows, rowIndex, 1)"
                                    />
                                    <BaseButton
                                        variant="danger-icon" dense
                                        :icon="ICONS.delete"
                                        :aria-label="`Remove ${ingredientLabel(row)}`"
                                        @click="removeIngredient(String(row.client_id))"
                                    />
                                </template>
                                <AddToListButton
                                    v-else-if="row.stock_item_id && isIngredientMissing(row.stock_item_id)"
                                    :stock-item-id="row.stock_item_id"
                                    variant="row"
                                />
                            </span>
                        </li>
                    </ul>

                    <!-- The unsectioned group always exists (it owns "Add
                         ingredient" while editing); in view mode an empty
                         one is nothing to say, not an empty section. -->
                    <p
                        v-if="group.rows.length === 0 && (ingredientsEditing || group.sectionId !== null)"
                        class="rn__ingsecempty"
                    >
                        Nothing in this section yet.
                    </p>

                    <BaseButton
                        v-if="ingredientsEditing"
                        variant="subtle"
                        class="rn__add"
                        :icon="ICONS.add"
                        :label="group.sectionId === null ? 'Add ingredient' : `Add to ${group.name}`"
                        @click="addIngredient(group.sectionId)"
                    />
                </div>
            </div>

            <!-- Same variant, same width, same icon as "Add
                 ingredient" - the owner picked that one when he
                 asked for the two to match. -->
            <BaseButton
                v-if="ingredientsEditing"
                variant="subtle"
                class="rn__add rn__addsec"
                :icon="ICONS.add"
                label="Add section"
                @click="addSection"
            >
                <BaseTooltip>
                    Sections group the list under headings - "For the
                    sauce", "To serve".
                </BaseTooltip>
            </BaseButton>
        </section>

        <RecipeIngredientRowEditor
            v-model="rowEditorOpen"
            :row="rowEditorRow"
            :sections="form.sections"
            @save="onRowEditorSave"
            @cancel="onRowEditorCancel"
        />
    </div>
</template>

<script lang="ts" setup>
    import HelpHint from 'src/components/help/HelpHint.vue';
    /**
     * The recipe page's ingredient rail: the list, grouped into section
     * cards, with one pencil that flips it between reading (tap a row to
     * light the steps that use it; put a missing row on a list) and editing
     * (tap a row to open its editor; reorder, remove, add rows and sections)
     * in place — R-055. Split out of `RecipeDetailPage` (FU-934). It owns the
     * row editor and every ingredient/section mutation; the form, the dirty
     * flag, the save and the highlight are the page's, via `useRecipeDetail`.
     */
    import { computed, ref } from 'vue';

    import AddToListButton from 'src/components/AddToListButton.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import RecipeIngredientRowEditor from 'src/components/recipes/RecipeIngredientRowEditor.vue';
    import RecipeMissingIngredientChip from 'src/components/recipes/RecipeMissingIngredientChip.vue';

    import { ICONS } from 'src/style/icons';
    import { formatQuantity } from 'src/helpers/formatQuantity';
    import { newClientId } from 'src/helpers/clientId';
    import { useRecipeDetail } from 'src/composables/useRecipeDetail';
    import type { IngredientForm, IngredientPatch } from 'src/composables/useRecipeEditor';

    const {
        form, saveState, ingredientsEditing, toggleEditRegion, markDirty,
        selectedStepId, selectedIngredientId, clearHighlight,
        ingredientLabel, stockItemName, isIngredientMissing, expiringChipFor, substitutesForRow,
    } = useRecipeDetail();

    /** Entering ingredient edit mode drops any read-mode highlight: the rows
     *  are about to mean "tap to edit", and a leftover "these are the ones
     *  step 3 uses" tint would be read as part of that. */
    const onToggleIngredientsEdit = async () => {
        clearHighlight();
        await toggleEditRegion(ingredientsEditing);
    };

    /** The pantry item under a chosen name, shown beside it so "Bega Tasty"
     *  still says it is the Cheese the pantry tracks. Null when the label
     *  already is the item's name. */
    function ingredientItemCaption(row: IngredientForm): string | null {
        const item = stockItemName(row);
        if (!row.label || !item) return null;
        return row.label.trim().toLowerCase() === item.trim().toLowerCase() ? null : item;
    }

    /** Does this row have anything to say about the pantry? Mirrors the two
     *  `v-if`s inside `.rn__ingstate` — they stay the authority on *which*
     *  chip; this only decides whether the column exists at all. */
    function hasPantryState(row: IngredientForm): boolean {
        const id = row.stock_item_id;
        if (!id) return false;
        if (!ingredientsEditing.value && isIngredientMissing(id)) return true;
        return expiringChipFor(id) !== null;
    }

    /** True for a row that would block the save — used to point at the row
     *  rather than only naming a count in the message. */
    function isHalfBuilt(row: IngredientForm): boolean {
        return !row.stock_item_id && !row.raw_text;
    }

    // ── Highlight ───────────────────────────────────────────────────────
    /** Ingredient rows lit by the currently selected step. */
    const litIngredients = computed(() => {
        const ids = new Set<string>();
        if (!selectedStepId.value) return ids;
        const step = form.steps.find((s) => s.client_id === selectedStepId.value);
        for (const id of step?.ingredient_client_ids ?? []) ids.add(id);
        return ids;
    });

    /** One row, two meanings, decided by the pencil: editing opens the row's
     *  editor, reading toggles the highlight. Tapping the lit row again
     *  clears it — the only way back on a phone, where there is nothing else
     *  to click "off" onto. */
    function onIngredientRowActivate(clientId: string) {
        if (ingredientsEditing.value) {
            openRowEditor(clientId);
            return;
        }
        selectedStepId.value = null;
        selectedIngredientId.value = selectedIngredientId.value === clientId ? null : clientId;
    }

    // ── Groups ──────────────────────────────────────────────────────────
    /** Ingredients bucketed by section, in section order, with the unsectioned
     *  rows first under no heading — matching how the list reads on paper.
     *
     *  Sections with no rows are rendered too. Skipping them (which this page
     *  shipped doing) made a brand-new section invisible the moment it was
     *  created, so there was no visible place to move anything into and the
     *  feature read as broken. An empty section shows its own hint instead. */
    type IngredientGroup = {
        key: string;
        /** Null for the unsectioned rows — the group that renders bare. */
        sectionId: string | null;
        name: string;
        rows: IngredientForm[];
    };

    const ingredientGroups = computed<IngredientGroup[]>(() => {
        const flat = form.ingredients.filter((i) => !i.section_client_id);
        const groups: IngredientGroup[] = [];
        // The main group always renders, even empty: it owns the "Add
        // ingredient" button, and a recipe whose every row sits in a section
        // would otherwise have no way back to an unsectioned one.
        groups.push({ key: 'main', sectionId: null, name: '', rows: flat });
        for (const sec of [...form.sections].sort((a, b) => a.sequence - b.sequence)) {
            groups.push({
                key: sec.client_id,
                sectionId: sec.client_id,
                name: sec.name || 'Untitled section',
                rows: form.ingredients.filter((i) => i.section_client_id === sec.client_id),
            });
        }
        return groups;
    });

    function sectionNameOf(clientId: string | null): string {
        if (!clientId) return '';
        return form.sections.find((sec) => sec.client_id === clientId)?.name ?? '';
    }
    function sectionIndexOf(clientId: string | null): number {
        if (!clientId) return -1;
        return [...form.sections]
            .sort((a, b) => a.sequence - b.sequence)
            .findIndex((sec) => sec.client_id === clientId);
    }
    function renameSection(clientId: string, name: string) {
        const sec = form.sections.find((x) => x.client_id === clientId);
        if (!sec) return;
        sec.name = name;
        markDirty();
    }

    // ── Ingredient mutations ────────────────────────────────────────────
    /** `sectionId` is the card the button lives in, so a row lands where it
     *  was asked for rather than in the flat list every time. */
    function addIngredient(sectionId: string | null = null) {
        form.ingredients.push({
            client_id: newClientId(),
            stock_item_id: null,
            raw_text: null,
            quantity: null,
            unit: null,
            notes: null,
            section_client_id: sectionId,
            is_optional: false,
        } as IngredientForm);
        markDirty();
        // A fresh row has no anchor yet, so open the editor on it straight
        // away rather than leaving a blank line the user has to discover is
        // clickable — and which would block the save if they didn't.
        const added = form.ingredients[form.ingredients.length - 1];
        if (added?.client_id) openRowEditor(String(added.client_id));
    }
    function removeIngredient(clientId: string) {
        const idx = form.ingredients.findIndex((i) => i.client_id === clientId);
        if (idx < 0) return;
        form.ingredients.splice(idx, 1);
        // A step that pointed at this row would otherwise keep a dangling
        // reference, which survives the PATCH as a step that "uses" nothing.
        for (const step of form.steps) {
            step.ingredient_client_ids = step.ingredient_client_ids.filter((id) => id !== clientId);
        }
        markDirty();
    }

    /** Ingredient order is array order — there is no `sequence` on the wire,
     *  and arrays are sent with replace semantics — so a move is a splice.
     *
     *  Moves are *within a section card*: the visible neighbours are the
     *  section's rows, not the whole recipe's, so swapping array positions
     *  with the row directly above/below in that group is what makes ↑ and ↓
     *  mean what they look like they mean. Changing which section a row is in
     *  is a different act, done in the row editor. */
    function moveIngredientWithin(rows: IngredientForm[], index: number, delta: -1 | 1) {
        const target = rows[index + delta];
        const source = rows[index];
        if (!target || !source) return;
        const from = form.ingredients.findIndex((i) => i.client_id === source.client_id);
        const to = form.ingredients.findIndex((i) => i.client_id === target.client_id);
        if (from < 0 || to < 0) return;
        const [moved] = form.ingredients.splice(from, 1);
        if (moved) form.ingredients.splice(to, 0, moved);
        markDirty();
    }

    // ── The row editor ──────────────────────────────────────────────────
    const rowEditorOpen = ref(false);
    const rowEditorFor = ref<string | null>(null);
    const rowEditorRow = computed(
        () => form.ingredients.find((i) => i.client_id === rowEditorFor.value) ?? null);

    function openRowEditor(clientId: string) {
        rowEditorFor.value = clientId;
        rowEditorOpen.value = true;
    }

    /** Backed out of a row that was never anchored — `addIngredient` pushed
     *  it before opening the editor, so "add, change your mind" would
     *  otherwise leave a blank row that blocks the next save (owner: adding an
     *  ingredient "is not fluid enough", 2026-08-27). */
    function onRowEditorCancel() {
        const id = rowEditorFor.value;
        if (id) removeIngredient(id);
    }

    /** The editor hands back a whole patch rather than mutating the row, so
     *  Cancel is a real cancel (R-006 safe mutations). */
    function onRowEditorSave(patch: IngredientPatch) {
        const row = form.ingredients.find((i) => i.client_id === rowEditorFor.value);
        if (!row) return;
        Object.assign(row, patch);
        markDirty();
    }

    // ── Sections ────────────────────────────────────────────────────────
    /** `sequence` is what the server sorts on, so it is kept dense and
     *  0-based after every structural change rather than left with gaps. */
    function resequenceSections() {
        [...form.sections]
            .sort((a, b) => a.sequence - b.sequence)
            .forEach((sec, i) => { sec.sequence = i; });
    }
    function addSection() {
        form.sections.push({ client_id: newClientId(), sequence: form.sections.length, name: '' });
        resequenceSections();
        markDirty();
    }
    function removeSection(clientId: string) {
        const idx = form.sections.findIndex((s) => s.client_id === clientId);
        if (idx < 0) return;
        form.sections.splice(idx, 1);
        // Rows in a deleted section fall back to the flat list, mirroring the
        // server's ON DELETE SET NULL.
        for (const ing of form.ingredients) {
            if (ing.section_client_id === clientId) ing.section_client_id = null;
        }
        // Steps carry a section reference too (C-4 Chunk 10), and a stale one
        // would point at a section the PATCH no longer contains.
        for (const step of form.steps) {
            if (step.section_client_id === clientId) step.section_client_id = null;
        }
        resequenceSections();
        markDirty();
    }
    function moveSection(clientId: string, delta: -1 | 1) {
        const ordered = [...form.sections].sort((a, b) => a.sequence - b.sequence);
        const from = ordered.findIndex((s) => s.client_id === clientId);
        const to = from + delta;
        if (from < 0 || to < 0 || to >= ordered.length) return;
        const [sec] = ordered.splice(from, 1);
        if (sec) ordered.splice(to, 0, sec);
        ordered.forEach((s, i) => { s.sequence = i; });
        markDirty();
    }
</script>

<style scoped lang="scss">
    // Section heading row, pane, chip — shared with the page's method.
    @use '../../css/recipeDetail';

    /* The rail follows the method down a long recipe (owner ask); the pane
       inside it scrolls on its own (`.rn__pane`, shared). */
    .rn__rail { position: sticky; top: var(--space-4); }

    /* A section is a container, so it is drawn as one (owner feedback
       2026-08-24). The unsectioned group deliberately gets no card: a box
       around "the rest of the ingredients" is a box around nothing. */
    .rn__group { margin-bottom: var(--space-3); }
    .rn__group--card {
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        background: var(--surface-component);
        padding: var(--space-2);
    }
    .rn__grouphead {
        display: flex; align-items: center; gap: var(--space-2);
        padding: var(--space-1) var(--space-1) var(--space-2);
        border-bottom: 1px solid var(--divider);
        margin-bottom: var(--space-1);
    }
    .rn__groupname {
        font-size: var(--font-size-sm); font-weight: 700; letter-spacing: 0.06em;
        text-transform: uppercase; color: var(--primary-ink);
        min-width: 0;
        margin: 0;
    }
    /* Edit face of the same name: a real field, sized to the card rather than
       to its own content (owner feedback 2026-08-27). */
    .rn__groupfield { flex: 1 1 auto; min-width: 0; }
    .rn__groupcount {
        margin-left: auto;
        font-size: var(--font-size-sm); color: var(--text-muted);
        font-variant-numeric: tabular-nums;
    }
    .rn__addsec { margin-top: var(--space-2); }
    .rn__ing { list-style: none; margin: 0; padding: 0; }
    .rn__ing li {
        display: grid;
        grid-template-columns: auto 1fr auto auto;
        gap: var(--space-3);
        /* Centred, not baseline-aligned. A 36px round icon button has no text
           baseline worth aligning to, so `baseline` pinned it to the *first*
           line of the name column: on a row whose name wrapped, the cart ended
           up stranded at the top-right with empty space under it and read as a
           second row rather than part of this one (owner, 2026-08-31). It also
           made the button jump vertically between its two icon glyphs. */
        align-items: center;
        padding: var(--space-2);
        border-bottom: 1px solid var(--divider);
        border-radius: var(--radius-sm);
    }
    .rn__ing li:hover { background: var(--overlay-hover); }
    /* The whole row is the edit target, so it carries the affordance — the
       quantity and the name are plain text inside it. */
    .rn__ing--target { cursor: pointer; }
    .rn__ing--target:focus-visible {
        outline: 2px solid var(--brand-primary);
        outline-offset: -2px;
    }
    .rn__ing--lit {
        background: var(--brand-primary-soft) !important;
        box-shadow: inset 3px 0 0 0 var(--brand-primary);
    }
    .rn__qty {
        font-variant-numeric: tabular-nums; font-weight: 700;
        white-space: nowrap; min-width: 58px;
    }
    .rn__ingname { min-width: 0; }
    .rn__ingnote { display: block; font-size: var(--font-size-sm); color: var(--text-muted); }
    /* The pantry item under a chosen name: same line, quieter. */
    .rn__ingitem { margin-left: var(--space-1); font-size: var(--font-size-sm); color: var(--text-muted); }
    /* The row's one severity signal is `RecipeMissingIngredientChip`, which
       owns its own weight; the wrapper here only spaces it off the name and
       stops the row's click handler from reaching it. */
    /* The pantry-state column. Its own grid cell, so the chips land at the
       same x on every row instead of trailing a name of unpredictable width,
       and `margin-right` is the gap the owner asked for between them and the
       cart button. Empty on most rows, and an empty grid cell takes no space,
       so nothing shifts. */
    .rn__ingstate {
        display: flex; align-items: center; flex-wrap: wrap;
        justify-content: flex-end;
        gap: var(--space-1);
        margin-right: var(--space-2);
    }
    .rn__chip--unlinked { background: var(--surface-sunken); color: var(--text-muted); }
    /* No hover-reveal any more. In read mode the only thing in here is the
       cart button, which the owner asked to be permanently visible; in edit
       mode everything in here is the point of the mode. Hiding either behind
       a gesture a thumb doesn't have was the old compromise (2026-08-27). */
    .rn__ingact {
        display: flex; align-items: center; gap: var(--space-1);
        border-radius: var(--radius-sm);
    }
    .rn__add { margin-top: var(--space-3); width: 100%; }

    .rn__ingsecempty {
        color: var(--text-muted);
        font-size: var(--font-size-sm);
        margin: 0;
        padding: var(--space-2);
    }

    /* ── Phone ────────────────────────────────────────────────────────── */
    @media (max-width: 1023px) {
        .rn__rail { position: static; }
    }
</style>
