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

        <q-banner v-else-if="loadError" class="dora-bg-negative-soft text-negative" dense rounded>
            {{ loadError }}
        </q-banner>

        <template v-else-if="recipe">
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
            </div>

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

            <!-- ═══ Status strip — replaces seven sidebar cards ══════════
                 Severity lives in a 3px edge stripe rather than a washed cell
                 (D-013): it stays legible on both grounds and doesn't shout.
                 Cells that have nothing to say don't render. -->
            <div class="rn__status">
                <div
                    class="rn__cell rn__cell--split"
                    :class="missingIngredients.length > 0 ? 'rn__cell--bad' : (cookableNow ? 'rn__cell--ok' : '')"
                >
                    <div class="rn__cellbody">
                        <span class="rn__cellk">Right now</span>
                        <span class="rn__cellv">{{ cookableHeadline }}</span>
                        <!-- One line, and only one. The swap count and the
                             already-on-a-list state both used to be spelled out
                             here as well, and both are visible per-row a few
                             centimetres below — on the chip and on the cart
                             button's own state (owner, 2026-08-31: *"it may be
                             enough to just say the main line"*). The count the
                             button still needs is in the button's label, where
                             it's about what pressing it will do. -->
                    </div>
                    <!-- The cell's action, at the cell's edge — a real button on
                         the right rather than a text link buried under the copy
                         it belongs to. It disappears (rather than going inert)
                         once everything missing is already on a list. -->
                    <BaseButton
                        v-if="missingIngredients.length > 0 && missingNotOnListCount > 0"
                        variant="secondary"
                        :icon="ICONS.add_shopping_cart"
                        :label="compact ? undefined : addMissingLabel"
                        :aria-label="`${addMissingLabel}: the ingredients you're missing`"
                        @click="onAddMissingToList"
                    >
                        <BaseTooltip v-if="compact">{{ addMissingLabel }}</BaseTooltip>
                    </BaseButton>
                </div>

                <div v-if="atRiskCount > 0" class="rn__cell rn__cell--warn">
                    <span class="rn__cellk">Worth cooking</span>
                    <span class="rn__cellv">{{ atRiskHeadline }}</span>
                    <span class="rn__cellsub">Uses it up</span>
                </div>

                <div v-if="moneyEnabled && showCostCell" class="rn__cell">
                    <span class="rn__cellk">Estimated cost</span>
                    <span class="rn__cellv">
                        {{ recipe.estimated_cost !== null ? formatMoney(recipe.estimated_cost) : 'Not enough price info' }}
                    </span>
                    <span class="rn__cellsub">
                        {{ recipe.estimated_cost_priced_count }} of
                        {{ recipe.estimated_cost_total_count }} priced
                    </span>
                    <!-- Feedback 2026-08-24 — the breakdown was a section on
                         the page reached by a text link; it's a question with
                         an answer, so it's a button and a modal. -->
                    <BaseButton
                        variant="subtle"
                        dense
                        class="rn__cellbtn"
                        :icon="ICONS.receipt_long"
                        label="Details"
                        @click="costDialogOpen = true"
                    />
                </div>

                <div class="rn__cell">
                    <span class="rn__cellk">Last cooked</span>
                    <span class="rn__cellv">
                        {{ recipe.last_made_on ? formatDate(recipe.last_made_on) : 'Never' }}
                    </span>
                    <!-- The meal pool merged in here rather than owning a card
                         of its own. Batch-cooking households only. -->
                    <span v-if="batchEnabled" class="rn__pool">
                        <MealStepper
                            :available="recipe.available_meals"
                            :busy="adjusting"
                            size="sm"
                            @adjust="onAdjustMeals"
                        />
                        <!-- Owner feedback 2026-09-01 — "N free of M" alone is
                             a riddle: add one to the pool and it can still read
                             "0 free of 1", because the meal plan already
                             claimed it. The line now says *why* whenever
                             something is spoken for, so the number moving (or
                             not) is explainable without opening the planner. -->
                        <span v-if="poolLabel" class="rn__cellsub">
                            {{ poolLabel }}
                            <BaseTooltip v-if="poolTooltip">{{ poolTooltip }}</BaseTooltip>
                        </span>
                    </span>
                </div>
            </div>

            <!-- ═══ Body — ingredients rail + method ════════════════════ -->
            <div class="rn__body">
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

                                <p v-if="group.rows.length === 0" class="rn__ingsecempty">
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
                </div>

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
                        <BaseSegmented
                            v-if="methodEditing"
                            v-model="form.steps_mode"
                            dense
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
                                @update:model-value="onStepImagesChanged"
                            />
                            <RecipeStepImagesViewer v-else :images="form.step_images" />
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

            <!-- ═══ Details — everything administrative ═════════════════
                 Owner feedback 2026-08-27 — these panels' labels read as body
                 text sitting on top of body text, so they now wear the same
                 uppercase section title Ingredients and Method wear, and the
                 captions are gone with them: a caption that lists what is
                 inside a drawer you are about to open is a summary of a thing
                 one tap away. Tools left this list entirely — they belong to
                 the method now, derived from the steps that use them. -->
            <div class="rn__details">
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
                            <h2 class="rn__sectitle">Nutrition</h2>
                        </q-item-section>
                    </template>
                    <div class="rn__disc">
                        <!-- Linking a food from the gap list changes the
                             server's rollup, so the recipe is re-fetched
                             rather than patched in place (R-003). -->
                        <RecipeNutritionCard
                            :nutrition="recipe.nutrition"
                            @linked="loadRecipe"
                        />
                    </div>
                </q-expansion-item>

                <q-expansion-item
                    v-if="!isComplex && nutritionEnabled"
                    v-model="detailOpen.kcal"
                    dense-toggle
                >
                    <template #header>
                        <q-item-section>
                            <h2 class="rn__sectitle">Calories</h2>
                        </q-item-section>
                        <q-item-section side>
                            <span class="rn__seccount">
                                {{ form.kcal ? `${form.kcal} kcal per serving` : 'Not set' }}
                            </span>
                        </q-item-section>
                    </template>
                    <div class="rn__disc">
                        <q-input
                            v-model.number="form.kcal"
                            dense outlined type="number" min="0"
                            label="kcal per serving"
                            style="max-width: 220px"
                            @update:model-value="markDirty"
                        />
                    </div>
                </q-expansion-item>

                <!-- Version information. Renders even for a singleton, because
                     created/updated are facts about every recipe. -->
                <q-expansion-item v-model="detailOpen.versions" dense-toggle>
                    <template #header>
                        <q-item-section>
                            <h2 class="rn__sectitle">Version information</h2>
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

        <RecipeCostDialog
            v-if="recipe"
            v-model="costDialogOpen"
            :lines="recipe.estimated_cost_lines ?? []"
            :total="recipe.estimated_cost"
            :priced-count="recipe.estimated_cost_priced_count"
            :total-count="recipe.estimated_cost_total_count"
            :per-serving="recipe.estimated_cost_per_serving"
        />

        <RecipeIngredientRowEditor
            v-model="rowEditorOpen"
            :row="rowEditorRow"
            :sections="form.sections"
            @save="onRowEditorSave"
            @cancel="onRowEditorCancel"
        />

        <!-- Owner feedback 2026-08-27 — shared with meal plans (R-001); the
             recipe-only picker component is gone. -->
        <AddToListDialog
            ref="pickerRef"
            v-model="pickerOpen"
            title="Add ingredients to a list"
            :rows="pickerRows"
            :unlinked="pickerUnlinked"
            :default-new-list-name="recipe ? `Shopping: ${recipe.name}` : 'Shopping list'"
            :initial-checked-ids="pickerInitialCheckedIds"
            @confirm="onPickerConfirm"
        />

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
    </q-page>
</template>

<script lang="ts" setup>
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
     *    reversed it; see the save block below for the three ways that failed.
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
    import { computed, onBeforeUnmount, onMounted, reactive, ref, watch, type Ref } from 'vue';
    import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router';
    import { useQuasar } from 'quasar';
    import { storeToRefs } from 'pinia';

    import AppSkeleton from 'src/components/AppSkeleton.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseSegmented from 'src/components/BaseSegmented.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import ImageEditTile from 'src/components/ImageEditTile.vue';
    import MealStepper from 'src/components/recipes/MealStepper.vue';
    import RecipeInfoCard from 'src/components/recipes/RecipeInfoCard.vue';
    import RecipeNutritionCard from 'src/components/recipes/RecipeNutritionCard.vue';
    import RecipeStepImagesViewer from 'src/components/recipes/RecipeStepImagesViewer.vue';
    import RecipeStepImagesEditor from 'src/components/recipes/RecipeStepImagesEditor.vue';
    import RecipeStructuredMethod from 'src/components/recipes/RecipeStructuredMethod.vue';
    import RecipeCostDialog from 'src/components/recipes/RecipeCostDialog.vue';
    import CookModeGuardDialog from 'src/components/recipes/CookModeGuardDialog.vue';
    import AddToListDialog from 'src/components/shoppingList/AddToListDialog.vue';
    import type { AddToListConfirm } from 'src/components/shoppingList/addToListTypes';
    import { lineChoicesFromRecipe, rowsFromRecipe, unlinkedFromRecipe } from 'src/helpers/addToListRows';
    import RecipeIngredientRowEditor from 'src/components/recipes/RecipeIngredientRowEditor.vue';
    import RecipeMissingIngredientChip from 'src/components/recipes/RecipeMissingIngredientChip.vue';
    import AddToListButton from 'src/components/AddToListButton.vue';

    import { ICONS } from 'src/style/icons';
    import { ingredientDisplayName } from 'src/helpers/recipeIngredientLabel';
    import { formatQuantity } from 'src/helpers/formatQuantity';
    import { formatDate } from 'src/composables/useDateFormat';
    import { formatMoney } from 'src/composables/useMoney';
    import { needsCookGuard } from 'src/helpers/cookModeGuard';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useBatchEnabled } from 'src/composables/useBatchEnabled';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { useNutritionMode } from 'src/composables/useNutritionMode';
    import { useRecipeExport } from 'src/composables/useRecipeExport';
    import { newClientId } from 'src/helpers/clientId';
    import { totalMinutes } from 'src/helpers/recipeTime';
    import { DIFFICULTY_OPTIONS } from 'src/helpers/recipeVocabulary';
    import { useShoppingListActions } from 'src/composables/useShoppingListActions';
    import {
        buildUpdateCommand,
        hydrateRecipeForm,
        useRecipeForm,
        type IngredientForm,
        type IngredientPatch,
    } from 'src/composables/useRecipeEditor';

    import RecipeApiService, { recipeImageUrl } from 'src/services/api/recipeApiService';
    import { useRecipeStore } from 'src/stores/recipeStore';
    import { useRecipeVocabStore } from 'src/stores/recipeVocabStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useMealSlotStore } from 'src/stores/mealSlotStore';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { cartStateFor, type Membership } from 'src/models/shoppingList';
    import StockItemApiService from 'src/services/api/stockItemApiService';
    import type { Recipe } from 'src/models/recipe';
    import type { SubstituteOption } from 'src/components/recipes/recipeSubstituteTypes';
    import type { EditableStep } from 'src/components/recipes/recipeStepEditorTypes';
    import type { EditableStepImage } from 'src/components/recipes/recipeStepImageEditorTypes';
    import { useConfirm } from 'src/composables/useConfirm';

    // Domain vocabulary, not a page constant: the same three values rank
    // recipes in the cookbook's sort. R-003 — one home, four readers.

    const $q = useQuasar();

    const { confirm } = useConfirm();
    const route = useRoute();
    const router = useRouter();

    const recipeStore = useRecipeStore();
    const stockItemStore = useStockItemStore();
    const recipeVocabStore = useRecipeVocabStore();
    const shoppingListStore = useShoppingListStore();
    const mealSlotStore = useMealSlotStore();
    const stockLevelStore = useStockLevelStore();
    const recipeApi = new RecipeApiService();
    const stockItemApi = new StockItemApiService();
    const { recipeCollections, collectionOptions } = storeToRefs(recipeStore);
    const {
        cuisines, categories, tools,
        cuisineOptions, categoryOptions, dietaryTagOptions, toolOptions,
    } = storeToRefs(recipeVocabStore);
    // `time_of_day` reads the household's own meal-slot names.
    const { slotNamesOrDefault: timeOfDayOptions } = storeToRefs(mealSlotStore);
    // Shopping-list membership, read from the same place every cart button
    // reads it (R-003) so the page and the buttons can't disagree about
    // whether something is already on a list.
    const { membership: listMembership } = storeToRefs(shoppingListStore);
    const membership = computed<Membership | null>(
        () => (listMembership.value as Membership | null) ?? null,
    );

    const { moneyEnabled } = useMoneyEnabled();

    /* The cooked-meals pool, in words.
     *
     * Owner feedback 2026-09-01: *"when there's a shortfall add text to
     * explain this to the user so there's no confusion when they add 1 to the
     * pool and it still says '0 free of 1'"*.
     *
     * "Free" is `unallocated_meals` — what's in the pool minus what future
     * meal-plan entries have already claimed — so the two numbers move
     * independently and the old phrasing never said what ate the difference.
     *
     * Owner 2026-09-03 trimmed it further: *"no need to restate what the
     * counter shows … in a case where there's nothing planned we don't
     * care"*. The stepper beside this line already shows the pool count, so
     * "2 in the pool" was the number read out loud, and it was the state the
     * line appeared in most often. The line now exists only when the meal
     * plan has a claim on this recipe — which is the only thing the stepper
     * can't tell you:
     *   nothing planned → no line at all;
     *   partly claimed  → name the claim, so 0-free-with-1-in-the-pool has a
     *     visible cause;
     *   short           → the plan wants more than exists; say how many more,
     *     which is the number you'd cook.
     * Display phrasing only — every number here is server-derived (R-003). */
    const poolLabel = computed(() => {
        const r = recipe.value;
        if (!r || r.committed_meals === 0) return '';
        const shortfall = r.committed_meals - r.available_meals;
        if (shortfall > 0) return `Your meal plan needs ${shortfall} more`;
        return `${r.unallocated_meals} free · ${r.committed_meals} planned`;
    });

    const poolTooltip = computed(() => {
        const r = recipe.value;
        if (!r || r.committed_meals === 0) return null;
        const meals = `${r.committed_meals} meal${r.committed_meals === 1 ? '' : 's'}`;
        return `${meals} of this recipe ${r.committed_meals === 1 ? 'is' : 'are'} already on your meal plan, so ${r.committed_meals === 1 ? "it isn't" : "they aren't"} counted as free. Cooking more covers those first.`;
    });
    const { nutritionEnabled, isComplex } = useNutritionMode();
    const { batchEnabled } = useBatchEnabled();
    const { addStockItemsToList } = useShoppingListActions();
    const recipeExport = useRecipeExport();

    const compact = computed(() => $q.screen.lt.sm);
    const recipeId = computed(() => String(route.params.id ?? ''));

    const recipe = ref<Recipe | null>(null);
    const form = useRecipeForm();
    const loading = ref(false);
    const loadError = ref<string | null>(null);
    const adjusting = ref(false);
    const newVersionLoading = ref(false);
    const cookGuardOpen = ref(false);
    const photoDialogOpen = ref(false);
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
    const costDialogOpen = ref(false);
    const detailOpen = reactive({
        extra: false, nutrition: false, kcal: false, versions: false,
    });

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
    type SaveState = 'idle' | 'saving' | 'saved' | 'error';
    const saveState = ref<SaveState>('idle');
    const saveMessage = ref('');
    const dirty = ref(false);
    let idleTimer: ReturnType<typeof setTimeout> | null = null;

    // ── Masthead edit mode (R-055 / ADR-051) ────────────────────────────
    // One pencil for the whole block, replacing the per-field `q-popup-edit`s
    // that used to sit on the name, collection, cuisine, category and every
    // fact. Those cost two clicks on every dropdown (one to summon the field,
    // one to open it) and sized each control to its own longest option, so an
    // empty Difficulty was a sliver. A block that flips whole keeps one grid
    // across both states, and a select is a select.
    //
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
    const onToggleHeaderEdit = () => toggleEditRegion(headerEditing);
    const onToggleMethodEdit = () => toggleEditRegion(methodEditing);
    /** Entering ingredient edit mode drops any read-mode highlight: the rows
     *  are about to mean "tap to edit", and a leftover "these are the ones
     *  step 3 uses" tint would be read as part of that. */
    const onToggleIngredientsEdit = async () => {
        clearHighlight();
        await toggleEditRegion(ingredientsEditing);
    };

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
            headerEditing.value = false;
            ingredientsEditing.value = false;
            methodEditing.value = false;
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
            headerEditing.value = false;
            ingredientsEditing.value = false;
            methodEditing.value = false;
            saveState.value = 'idle';
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
            loadError.value = toastCaption(err) || "Couldn't load this recipe.";
        } finally {
            if (id === recipeId.value) loading.value = false;
        }
        // After the form is hydrated, so `missingIngredients` is current.
        // Deliberately not awaited by callers: the page is fully usable while
        // the chips fill in.
        void loadSubstitutes();
    }

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

    const photoUrl = computed(() => {
        if (imageDirty.value) return form.image;
        if (recipe.value?.has_image) {
            return recipeImageUrl(recipe.value.recipe_id, imageVersion.value);
        }
        return null;
    });
    // Owner call 2026-08-29 — `hasPhoto` used to mean "a photo exists even
    // though you've asked not to see photos", which was the only reason it
    // differed from `photoUrl`. With the `show_recipe_images` preference cut,
    // a photo that exists is a photo that renders, so the two collapse.
    const hasPhoto = computed(() => photoUrl.value !== null);

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

    /** The pantry item under a chosen name, shown beside it so "Bega Tasty"
     *  still says it is the Cheese the pantry tracks. Null when the label
     *  already is the item's name. */
    function ingredientItemCaption(row: IngredientForm): string | null {
        const item = stockItemName(row);
        if (!row.label || !item) return null;
        return row.label.trim().toLowerCase() === item.trim().toLowerCase() ? null : item;
    }

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

    // ── What's already on a shopping list ───────────────────────────────
    // Server-owned membership, not a client guess: the same map the cart
    // buttons read. Missing rows split into "still to buy" and "already
    // handled" so the status strip stops offering to add both.
    const missingOnListCount = computed(() =>
        missingIngredients.value.filter(
            (i) => cartStateFor(i.stock_item_id, membership.value) !== 'none',
        ).length);
    const missingNotOnListCount = computed(
        () => missingIngredients.value.length - missingOnListCount.value);

    // Names the button by what it will actually do. When some of the missing
    // rows are already handled the count has to be explicit ("Add 2 to a list"),
    // because "add them" would otherwise read as all of them.
    const addMissingLabel = computed(() => {
        const left = missingNotOnListCount.value;
        if (left === missingIngredients.value.length) {
            return left === 1 ? 'Add it to a list' : 'Add them to a list';
        }
        return `Add ${left} to a list`;
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
    const atRiskCount = computed(() => expiringItems.value.size);
    const atRiskHeadline = computed(() => {
        const names = [...expiringItems.value.keys()]
            .map((id) => stockItemStore.byId.get(id)?.name)
            .filter(Boolean);
        if (names.length === 1) return `${names[0]} needs using`;
        return `${atRiskCount.value} ingredients need using`;
    });

    const missingIngredients = computed(() => {
        const r = recipe.value;
        if (!r) return [];
        return r.ingredients
            .filter((i): i is typeof i & { stock_item_id: string; stock_item_name: string } =>
                i.is_missing && i.stock_item_id !== null)
            .filter((i, idx, arr) => arr.findIndex((x) => x.stock_item_id === i.stock_item_id) === idx);
    });
    const cookableNow = computed<boolean | null>(() => recipe.value?.cookable ?? false);
    const unlinkedCount = computed(() => recipe.value?.unlinked_ingredient_count ?? 0);
    const cookableHeadline = computed(() => {
        if (unlinkedCount.value > 0 && missingIngredients.value.length === 0) {
            return `${unlinkedCount.value} ingredient${unlinkedCount.value === 1 ? '' : 's'} to link`;
        }
        if (missingIngredients.value.length === 0) return 'Everything in stock';
        return `${missingIngredients.value.length} ingredient${missingIngredients.value.length === 1 ? '' : 's'} missing`;
    });
    // Owner feedback 2026-08-29 — no "You can cook this now" sub-line: the
    // cell's own headline ("Everything in stock") plus its green edge already
    // say it, and it was the one caption that had to repeat itself.

    const showCostCell = computed(() => {
        const r = recipe.value;
        if (!r) return false;
        return r.estimated_cost !== null
            || (r.estimated_cost_lines ?? []).some((l) => l.reason !== 'no_link');
    });

    const versionSiblings = computed(() => recipe.value?.version_siblings ?? []);

    // ── Method ──────────────────────────────────────────────────────────
    /* A leading ordinal the author typed themselves — "1. ", "2) ", "3: ".
     * Free text is where people number their own steps, and the read face now
     * draws a numeral in a circle beside each line (owner 2026-09-03), so left
     * alone every step reads "(1) 1. Render the pancetta" — which is what
     * driving the seed's Carbonara showed the moment the circles went in
     * (R-075: measure it, don't assume).
     * Deliberately narrow: the digits must be followed by real punctuation and
     * a space, so an ingredient-ish line like "2 eggs, beaten" keeps its 2. */
    const LEADING_ORDINAL = /^\d{1,3}\s*[.):]\s+/;

    const freeformLines = computed(() => (form.instructions ?? '')
        .split('\n')
        .map((l) => l.trim())
        .filter((l) => l.length > 0)
        .map((l) => {
            const stripped = l.replace(LEADING_ORDINAL, '');
            // Never strip a line down to nothing — a lone "1." is all the
            // content that line has, odd as it is.
            return stripped.length > 0 ? stripped : l;
        }));
    /** Ingredient rows lit by the currently selected step. */
    const litIngredients = computed(() => {
        const ids = new Set<string>();
        if (!selectedStepId.value) return ids;
        const step = form.steps.find((s) => s.client_id === selectedStepId.value);
        for (const id of step?.ingredient_client_ids ?? []) ids.add(id);
        return ids;
    });

    /** The other direction: steps lit by the currently selected ingredient.
     *  Structured-only, because it's the only mode that stores the link. */
    const highlightedStepIds = computed<string[]>(() => {
        const target = selectedIngredientId.value;
        if (!target) return [];
        return form.steps
            .filter((s) => s.ingredient_client_ids.includes(target))
            .map((s) => s.client_id);
    });

    function clearHighlight() {
        selectedStepId.value = null;
        selectedIngredientId.value = null;
    }

    function onSelectStep(clientId: string | null) {
        selectedIngredientId.value = null;
        selectedStepId.value = clientId;
    }

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

    // ── Captions for the collapsed Details rows ─────────────────────────
    // `extraCaption` and `versionsCaption` went with the captions they fed
    // (owner feedback 2026-08-27): a caption listing what is inside a drawer
    // one tap away is a summary of nothing. The version *count* survived as a
    // pill inside the panel, next to the list it counts.
    // `nutritionCaption` went with the caption it fed (owner, 2026-09-08) — see
    // the panel's header comment.

    // ── Ingredient + section mutations ──────────────────────────────────
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

    // ── Photo ───────────────────────────────────────────────────────────
    // Every photo control lives on the photo itself, so the tile is the only
    // uploader on the page; the dialog just picks which of the two things you
    // meant when a photo already exists.
    const photoTile = ref<InstanceType<typeof ImageEditTile> | null>(null);

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

    // ── Actions ─────────────────────────────────────────────────────────
    async function onToggleFavourite() {
        if (!recipe.value) return;
        try {
            await recipeStore.toggleFavouriteAsync(recipe.value);
            await loadRecipe();
        } catch (err) {
            $q.notify({ type: 'negative', message: "Couldn't update favourite.", caption: toastCaption(err) });
        }
    }

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
            $q.notify({ type: 'negative', message: "Couldn't delete.", caption: toastCaption(err) });
        }
    }

    async function onAdjustMeals(delta: number) {
        if (!recipe.value) return;
        adjusting.value = true;
        try {
            await recipeStore.adjustMealsAsync(recipe.value.recipe_id, delta);
            await loadRecipe();
        } catch (err) {
            $q.notify({ type: 'negative', message: 'Could not update meals.', caption: toastCaption(err) });
        } finally {
            adjusting.value = false;
        }
    }

    // Reuses the shared picker (and its list-target step) rather than a
    // second, thinner add path — same flow the old page runs (R-001).
    const pickerOpen = ref(false);
    const pickerRef = ref<{ setBusy: (v: boolean) => void; newListName: string } | null>(null);
    const pickerInitialCheckedIds = ref<string[] | undefined>(undefined);
    const pickerRows = computed(() => rowsFromRecipe(recipe.value));
    const pickerUnlinked = computed(() => unlinkedFromRecipe(recipe.value));

    function onAddMissingToList() {
        if (missingIngredients.value.length === 0) return;
        // The "no active shopping list" bounce is gone (2026-08-27) — the
        // shared dialog offers "+ New list", so the first list gets made
        // here rather than on a page you were sent to.
        pickerInitialCheckedIds.value = missingIngredients.value.map((i) => i.stock_item_id);
        pickerOpen.value = true;
    }

    async function onPickerConfirm(payload: AddToListConfirm) {
        pickerRef.value?.setBusy(true);
        try {
            await addStockItemsToList(
                payload.targetListId,
                payload.stockItemIds,
                pickerRef.value?.newListName ?? 'Shopping list',
                lineChoicesFromRecipe(recipe.value),
            );
            pickerOpen.value = false;
            pickerInitialCheckedIds.value = undefined;
        } finally {
            pickerRef.value?.setBusy(false);
        }
    }

    function goToSibling(id: string) {
        void router.push(`/cookbook/${id}`);
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
        // The page shipped with neither of these. The autosave timer it had
        // outlived the component, so a PATCH could land with nothing mounted
        // to report its failure to.
        if (idleTimer) clearTimeout(idleTimer);
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
        headerEditing.value = false;
        ingredientsEditing.value = false;
        methodEditing.value = false;
        clearHighlight();
        saveState.value = 'idle';
        void loadRecipe();
    });
</script>

<style scoped lang="scss">
    /* No display face. The page shipped with Fraunces on the title and the
       section labels; the owner's verdict 2026-08-24 was that it "just
       doesn't feel like the same app" — which is the right call, because a
       page-specific typeface is a second brand nobody asked for. Everything
       here inherits the user's chosen font (Settings → Appearance,
       themeService FONT_FAMILY_CSS), like every other page. */

    /* ── Masthead ─────────────────────────────────────────────────────── */
    .rn__masthead {
        display: grid;
        grid-template-columns: 220px 1fr;
        gap: var(--space-5, 20px);
        align-items: start;
    }
    .rn__photo {
        width: 100%;
        aspect-ratio: 1 / 1;
        border-radius: var(--radius-lg, 10px);
        overflow: hidden;
        border: 1px solid var(--border-default);
    }
    .rn__photoimg { width: 100%; height: 100%; object-fit: cover; display: block; }
    .rn__photoplaceholder {
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        gap: var(--space-2, 8px);
        width: 100%; height: 100%;
        color: var(--text-muted);
        font-size: 0.875rem;
    }
    .rn__photoacts { display: flex; flex-direction: column; gap: var(--space-2, 8px); }
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
        gap: var(--space-3, 12px);
        margin-top: var(--space-3, 12px);
    }
    .rn__backrow { display: flex; align-items: center; gap: var(--space-2, 8px); }
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
        gap: var(--space-2, 8px) var(--space-4, 16px);
        margin-top: var(--space-2, 8px);
        color: var(--text-secondary);
        font-size: 0.875rem;
    }
    .rn__brow { display: inline-flex; align-items: center; gap: var(--space-1, 4px); }


    .rn__facts {
        display: flex; flex-wrap: wrap;
        gap: var(--space-2, 8px) var(--space-6, 24px);
        margin-top: var(--space-4, 16px);
    }
    .rn__fact { display: flex; flex-direction: column; gap: 2px; min-width: 60px; flex: 0 0 auto; }
    .rn__factk {
        display: inline-flex; align-items: center; gap: var(--space-1, 4px);
        font-size: 0.6875rem; font-weight: 700; letter-spacing: 0.07em;
        text-transform: uppercase; color: var(--text-muted);
    }
    /* The letter-spacing above is set for capitals; on the glyph it just
       pushes it off its word. */
    .rn__factk .q-icon { letter-spacing: normal; }
    .rn__factv { font-size: 1rem; font-weight: 600; font-variant-numeric: tabular-nums; }

    /* ── Actions ──────────────────────────────────────────────────────── */
    .rn__actions {
        display: flex; align-items: center; gap: var(--space-2, 8px);
        margin-top: var(--space-5, 20px);
        padding-top: var(--space-4, 16px);
        border-top: 1px solid var(--divider);
        flex-wrap: wrap;
    }
    .rn__delete { margin-left: auto; }

    /* ── Status strip ─────────────────────────────────────────────────── */
    .rn__status {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1px;
        margin-top: var(--space-5, 20px);
        background: var(--border-default);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg, 10px);
        overflow: hidden;
    }
    .rn__cell {
        background: var(--surface-component);
        padding: var(--space-3, 12px) var(--space-4, 16px);
        display: flex; flex-direction: column; gap: 2px;
        position: relative;
    }
    /* A cell that carries an action: copy on the left, the action on the
       right edge where it can be reached without reading past it. */
    .rn__cell--split {
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
        gap: var(--space-3, 12px);
    }
    .rn__cellbody { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    /* Severity as an edge stripe rather than a washed cell: it survives both
       themes and doesn't drown the text it's qualifying (D-002/D-013). */
    .rn__cell--bad::before,
    .rn__cell--warn::before,
    .rn__cell--ok::before {
        content: '';
        position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
    }
    .rn__cell--bad::before { background: var(--semantic-negative); }
    .rn__cell--warn::before { background: var(--semantic-warning); }
    .rn__cell--ok::before { background: var(--semantic-positive); }
    .rn__cellk {
        font-size: 0.6875rem; font-weight: 700; letter-spacing: 0.07em;
        text-transform: uppercase; color: var(--text-muted);
    }
    .rn__cellv { font-weight: 600; }
    .rn__cellsub { font-size: 0.8125rem; color: var(--text-muted); }
    .rn__pool { display: flex; align-items: center; gap: var(--space-2, 8px); flex-wrap: wrap; }
    .rn__cellbtn { align-self: flex-start; margin-top: var(--space-1, 4px); }
    /* ── Body ─────────────────────────────────────────────────────────── */
    .rn__body {
        display: grid;
        grid-template-columns: minmax(280px, 34%) 1fr;
        gap: var(--space-8, 32px);
        margin-top: var(--space-6, 24px);
        align-items: start;
    }
    /* D-011 — a grid item's default `min-width: auto` lets it be sized by its
       widest indivisible content instead of by its track, and a wrapping chip
       field is exactly that content: every tool added to the free-text
       method's Tools select pushed the column, the column pushed the page, and
       the page scrolled sideways (owner, 2026-08-31). The track owns the width;
       what's inside it wraps or scrolls in its own box. */
    .rn__body > * { min-width: 0; }
    /* The rail follows the method down a long recipe, and each pane scrolls
       inside itself rather than the page (owner ask). */
    .rn__rail { position: sticky; top: var(--space-4, 16px); }
    .rn__pane {
        max-height: calc(100vh - 220px);
        overflow-y: auto;
        overscroll-behavior: contain;
    }
    .rn__sechead {
        display: flex; align-items: center; gap: var(--space-3, 12px);
        padding-bottom: var(--space-2, 8px);
        margin-bottom: var(--space-3, 12px);
        border-bottom: 1px solid var(--border-default);
    }
    .rn__sectitle {
        font-size: 0.9375rem; font-weight: 700;
        letter-spacing: 0.08em; text-transform: uppercase;
        color: var(--text-secondary);
        margin: 0;
    }
    .rn__seccount {
        font-size: 0.8125rem; color: var(--text-muted);
        font-variant-numeric: tabular-nums;
    }
    /* The heading row owns the section's controls now (owner feedback
       2026-08-27): title, count, then everything you can do to the section,
       pushed to the right edge. */
    .rn__sechead > .rn__seccount { margin-right: auto; }
    .rn__secedit { flex: none; }
    .rn__modes { min-width: 0; }

    /* A section is a container, so it is drawn as one (owner feedback
       2026-08-24). The unsectioned group deliberately gets no card: a box
       around "the rest of the ingredients" is a box around nothing. */
    .rn__group { margin-bottom: var(--space-3, 12px); }
    .rn__group--card {
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg, 10px);
        background: var(--surface-component);
        padding: var(--space-2, 8px);
    }
    .rn__grouphead {
        display: flex; align-items: center; gap: var(--space-2, 8px);
        padding: var(--space-1, 4px) var(--space-1, 4px) var(--space-2, 8px);
        border-bottom: 1px solid var(--divider);
        margin-bottom: var(--space-1, 4px);
    }
    .rn__groupname {
        font-size: 0.8125rem; font-weight: 700; letter-spacing: 0.06em;
        text-transform: uppercase; color: var(--brand-primary);
        min-width: 0;
        margin: 0;
    }
    /* Edit face of the same name: a real field, sized to the card rather than
       to its own content (owner feedback 2026-08-27). */
    .rn__groupfield { flex: 1 1 auto; min-width: 0; }
    .rn__groupcount {
        margin-left: auto;
        font-size: 0.8125rem; color: var(--text-muted);
        font-variant-numeric: tabular-nums;
    }
    .rn__addsec { margin-top: var(--space-2, 8px); }
    .rn__ing { list-style: none; margin: 0; padding: 0; }
    .rn__ing li {
        display: grid;
        grid-template-columns: auto 1fr auto auto;
        gap: var(--space-3, 12px);
        /* Centred, not baseline-aligned. A 36px round icon button has no text
           baseline worth aligning to, so `baseline` pinned it to the *first*
           line of the name column: on a row whose name wrapped, the cart ended
           up stranded at the top-right with empty space under it and read as a
           second row rather than part of this one (owner, 2026-08-31). It also
           made the button jump vertically between its two icon glyphs. */
        align-items: center;
        padding: var(--space-2, 8px);
        border-bottom: 1px solid var(--divider);
        border-radius: var(--radius-sm, 4px);
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
    .rn__ingnote { display: block; font-size: 0.8125rem; color: var(--text-muted); }
    /* The pantry item under a chosen name: same line, quieter. */
    .rn__ingitem { margin-left: var(--space-1, 4px); font-size: 0.8125rem; color: var(--text-muted); }
    .rn__chip { margin-left: var(--space-1, 4px); }
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
        gap: var(--space-1, 4px);
        margin-right: var(--space-2, 8px);
    }
    .rn__chip--unlinked { background: var(--surface-sunken); color: var(--text-muted); }
    /* No hover-reveal any more. In read mode the only thing in here is the
       cart button, which the owner asked to be permanently visible; in edit
       mode everything in here is the point of the mode. Hiding either behind
       a gesture a thumb doesn't have was the old compromise (2026-08-27). */
    .rn__ingact {
        display: flex; align-items: center; gap: var(--space-1, 4px);
        border-radius: var(--radius-sm, 4px);
    }
    .rn__add { margin-top: var(--space-3, 12px); width: 100%; }

    /* The structured method's own rules — the numbered bullets, the sub-step
       indent, the lit state — moved into `RecipeStructuredMethod.vue` with
       the markup, so the read and edit faces can't drift apart (owner
       feedback 2026-08-27). What's left here is the free-text face. */
    /* The free-text read face is `.dora-steps*` now (owner 2026-09-03) — its
       measure and spacing come from `css/recipeSteps.scss` with the structured
       method's, so the old `.rn__free` rule has nothing left to say. */
    .rn__empty { color: var(--text-muted); font-size: 0.875rem; }

    /* Tools, for the two modes that have no steps to derive them from. Inside
       the method, because that is what a tool belongs to — not a
       general-purpose drawer at the bottom of the page (owner call
       2026-08-27). */
    .rn__tools {
        display: flex; align-items: center; flex-wrap: wrap;
        gap: var(--space-2, 8px);
        margin-top: var(--space-6, 24px);
        padding-top: var(--space-3, 12px);
        border-top: 1px solid var(--divider);
    }
    .rn__toolk {
        display: inline-flex; align-items: center; gap: var(--space-1, 4px);
        font-size: 0.6875rem; font-weight: 700; letter-spacing: 0.07em;
        text-transform: uppercase; color: var(--text-muted);
        flex: none;
    }
    .rn__toolk .q-icon { letter-spacing: normal; }
    .rn__tools .q-select { flex: 1 1 240px; min-width: 0; }

    .rn__details { margin-top: var(--space-8, 32px); border-top: 1px solid var(--divider); }
    /* The expansion headers wear the Ingredients/Method treatment now, so the
       page has one voice for "this is a section" (owner feedback 2026-08-27).
       Quasar's own header padding stays; only the label changes. */
    .rn__details :deep(.q-expansion-item__toggle-icon) { color: var(--text-muted); }
    .rn__disc { padding: var(--space-3, 12px) var(--space-2, 8px) var(--space-4, 16px); }
    .rn__vfacts {
        display: flex; flex-wrap: wrap; gap: var(--space-2, 8px) var(--space-6, 24px);
        margin-bottom: var(--space-3, 12px);
    }
    .rn__vfact { display: flex; flex-direction: column; gap: 2px; }
    .rn__vthis { background: var(--surface-sunken); }
    /* The count is a pill beside the list it counts, and "New version" is a
       button in the panel that talks about versions rather than only an icon
       in the page-wide action row (owner feedback 2026-08-27). */
    .rn__vhead {
        display: flex; align-items: center; gap: var(--space-2, 8px);
        margin: var(--space-5, 20px) 0 var(--space-2, 8px);
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
    .rn__savebar {
        position: fixed; bottom: var(--space-5, 20px); left: 50%;
        transform: translateX(-50%); z-index: 6000;
        display: flex; align-items: center; gap: var(--space-2, 8px);
        padding: var(--space-2, 8px) var(--space-4, 16px);
        border-radius: var(--radius-pill, 999px);
        background: var(--surface-elevated);
        border: 1px solid var(--border-default);
        box-shadow: 0 2px 10px var(--overlay-dim);
        font-size: 0.875rem;
        color: var(--text-secondary);
    }
    .rn__savebar--error { border-color: var(--semantic-negative); color: var(--semantic-negative); }

    /* The standing "there is unsaved work" statement. Sits above the transient
       savebar's slot so the two never occupy the same space. */
    .rn__dirty {
        position: fixed; bottom: var(--space-5, 20px); left: 50%;
        transform: translateX(-50%); z-index: 6000;
        display: flex; align-items: center; gap: var(--space-2, 8px);
        padding: var(--space-2, 8px) var(--space-4, 16px);
        border-radius: var(--radius-pill, 999px);
        background: var(--surface-elevated);
        border: 1px solid var(--semantic-warning);
        box-shadow: 0 2px 10px var(--overlay-dim);
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-secondary);
    }


    .rn__ingsecempty {
        color: var(--text-muted);
        font-size: 0.8125rem;
        margin: 0;
        padding: var(--space-2, 8px);
    }


    .rn__discsub {
        font-size: 0.75rem; font-weight: 700; letter-spacing: 0.06em;
        text-transform: uppercase; color: var(--text-muted);
        margin: var(--space-5, 20px) 0 var(--space-2, 8px);
    }


    /* ── Phone ────────────────────────────────────────────────────────── */
    @media (max-width: 1023px) {
        /* At 375px the method heading holds a title, a count, a three-way
           switch and a Done button. Squeezed onto one line the switch got
           144px and wrapped every label, so the heading grew to 71px of
           stacked words. It takes its own full-width line instead, where the
           three options are readable and evenly sized. */
        .rn__sechead { flex-wrap: wrap; }
        .rn__secedit { order: 2; }
        .rn__modes { order: 3; flex: 1 1 100%; }
        .rn__modes :deep(.q-btn-group) { width: 100%; }
        .rn__modes :deep(.q-btn-group > .q-btn) { flex: 1 1 0; min-width: 0; }

        .rn__masthead { grid-template-columns: 1fr; }
        .rn__photo { aspect-ratio: 16 / 9; }
        .rn__body { grid-template-columns: 1fr; gap: var(--space-6, 24px); }
        .rn__rail { position: static; }
        /* A phone scrolls the page, not two nested panes. */
        .rn__pane { max-height: none; overflow: visible; }
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
