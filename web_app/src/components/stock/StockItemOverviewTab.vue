<template>
    <!-- The stock-item page's Overview tab (FU-934 split): Dora's belief, the
         buy verdict (or planned demand), the inline-edit fact list, preferred
         buys and Your prices, plus the two dialogs only this tab opens. The
         loaded item, the edit form and the save/reload pair are the page's
         (`useStockItemDetail`). Multi-root on purpose: the panel's DOM is
         exactly what it was before the split. -->
    <template v-if="detail">
        <!-- the buy-verdict oracle (row/line
             badges elsewhere; the full detail card here per
             FU-437). The card no-ops when the composable hasn't
             resolved yet or the install-wide flag is off, so
             the overview stays quiet on thin data. -->
        <!-- Feedback 2026-08-16: Dora's opinion sits above the buy
             verdict, both as collapsed coloured cards. -->
        <PantryBeliefCard :belief="belief" class="q-mb-md" />
        <!-- Owner, 2026-09-03 — "what will I need?", between
             "what does Dora think I have?" and "should I buy it?".
             Silent unless the upcoming plan actually wants this
             item; see the card for why it is here and not on the
             overview row. -->
        <!-- Owner 2026-10-15: planned meals are a reason to buy, so
             they live inside the verdict. The card stands alone only
             where there is no verdict (money features off). -->
        <PlannedDemandCard v-if="!buyVerdict" :demand="plannedDemand" class="q-mb-md" />
        <BuyVerdictCard
            v-if="buyVerdict"
            :verdict="buyVerdict"
            :stock-item-id="stockItemId"
            class="q-mb-md"
            @action="onBuyVerdictAction"
        />
        <div class="row q-col-gutter-md items-start">
            <div class="col-12">
                <q-list separator class="dora-inline-edit">
                    <q-item>
                        <q-item-section class="dora-text-secondary text-weight-bold dora-inline-edit__label">Name</q-item-section>
                        <q-item-section>
                            <q-input
                                v-model="form.name"
                                dense
                                borderless
                                placeholder="Name this item"
                                :rules="[(v: string) => (!!v && v.length > 0) || 'Name required']"
                                hide-bottom-space
                                @blur="saveNameIfDirty"
                                @keyup.enter="saveNameIfDirty"
                            />
                        </q-item-section>
                    </q-item>

                    <!-- Feedback 2026-06-18: level picker moved out
                         of the header into the second overview row,
                         combined with the level-updated timestamp
                         to its right. The picker uses the same
                         stock-level palette as the row buttons. -->
                    <q-item>
                        <q-item-section class="dora-text-secondary text-weight-bold dora-inline-edit__label">Level</q-item-section>
                        <q-item-section>
                            <!-- Feedback 2026-08-23: the picker used to be
                                 an intrinsically-sized button sharing its
                                 row with the timestamp, so it was narrower
                                 than every other editor in the list (and
                                 cramped on mobile). It now fills the row
                                 like the q-fields do, and the timestamp
                                 drops underneath as a caption. -->
                            <div class="column">
                                <!-- Round 9: render the level
                                     colour as a coloured swatch
                                     INSIDE the button (matching
                                     the menu items' avatars)
                                     rather than as the button's
                                     own `color=` prop. The
                                     outline + filled swatch
                                     patterns rendered the same
                                     Quasar palette name very
                                     differently — looked like
                                     a colour mismatch. With the
                                     swatch approach both the
                                     trigger and the menu rows
                                     render the colour the same
                                     way. -->
                                <BaseDropdown
                                    flat
                                    dense
                                    class="dora-level-picker"
                                >
                                    <template #label>
                                        <span class="dora-level-picker__label">
                                            <StockLevelDot
                                                :sequence="detailLevelSequence"
                                                dot-class="q-mr-sm"
                                            />
                                            {{ detail.stock_level_name ?? '–' }}
                                        </span>
                                    </template>
                                    <q-list dense>
                                        <q-item
                                            v-for="level in stockLevelStore.stockLevels"
                                            :key="level.stock_level_id"
                                            clickable
                                            v-close-popup
                                            @click="onChangeStockLevel(level.stock_level_id)"
                                        >
                                            <q-item-section avatar>
                                                <StockLevelDot :sequence="level.sequence" />
                                            </q-item-section>
                                            <q-item-section>{{ level.name }}</q-item-section>
                                        </q-item>
                                    </q-list>
                                </BaseDropdown>
                                <span class="dora-text-secondary text-caption q-mt-xs">
                                    Updated {{ relativeTime(detail.stock_level_last_updated) }}
                                </span>
                            </div>
                            <!-- The inferred-level hint moved out of this
                                 row into `PantryBeliefCard` at the top of
                                 the tab (feedback 2026-08-16), where it can
                                 show the reasoning for agreeing as well as
                                 for disagreeing. The row form (the level
                                 picker's ring + menu header) is what the stock
                                 overview uses. -->
                        </q-item-section>
                    </q-item>

                    <q-item>
                        <q-item-section class="dora-text-secondary text-weight-bold dora-inline-edit__label">Location</q-item-section>
                        <q-item-section>
                            <BaseSelect
                                aria-label="Location"
                                v-model="form.stock_location_id"
                                :options="locationOptions"
                                emit-value
                                map-options
                                use-input
                                fill-input
                                hide-selected
                                input-debounce="200"
                                clearable
                                borderless
                                placeholder="–"
                                @filter="filterLocations"
                                @clear="onClearLocation"
                                @update:model-value="onChangeLocation"
                            />
                        </q-item-section>
                    </q-item>

                    <!-- Empty-state dash via BaseSelect's `empty-text`,
                         which shows it only while nothing is picked. -->
                    <q-item>
                        <q-item-section class="dora-text-secondary text-weight-bold dora-inline-edit__label">Stock group</q-item-section>
                        <q-item-section>
                            <BaseSelect
                                aria-label="Stock group"
                                v-model="form.stock_group_id"
                                :options="groupOptions"
                                emit-value
                                map-options
                                clearable
                                borderless
                                empty-text="–"
                                @clear="onClearGroup"
                                @update:model-value="onChangeGroup"
                            />
                        </q-item-section>
                    </q-item>

                    <q-item>
                        <q-item-section class="dora-text-secondary text-weight-bold dora-inline-edit__label">Usual store</q-item-section>
                        <q-item-section>
                            <BaseSelect
                                aria-label="Usual store"
                                v-model="form.usual_store_id"
                                :options="storeOptions"
                                emit-value
                                map-options
                                clearable
                                borderless
                                empty-text="–"
                                @update:model-value="onChangeUsualStore"
                            >
                                <!-- Feedback 2026-08-08: show each store's logo
                                     (real image when uploaded, deterministic
                                     swatch otherwise) in the option list. -->
                                <template #option="{ opt, itemProps }">
                                    <q-item v-bind="itemProps">
                                        <q-item-section avatar class="stock-detail__store-logo">
                                            <StoreLogo
                                                :name="opt.label"
                                                :store-id="opt.value"
                                                :has-image="opt.has_image"
                                                :height="20"
                                                :width="34"
                                            />
                                        </q-item-section>
                                        <q-item-section>
                                            <q-item-label>{{ opt.label }}</q-item-label>
                                        </q-item-section>
                                    </q-item>
                                </template>
                            </BaseSelect>
                        </q-item-section>
                    </q-item>

                    <!-- Nutrition complex-mode only. In simple mode
                         kcal is typed per-recipe and stock items
                         have nothing to link, so the row is hidden
                         rather than shown disabled (R-029). -->
                    <q-item v-if="nutritionIsComplex">
                        <q-item-section class="dora-text-secondary text-weight-bold dora-inline-edit__label">Nutrition</q-item-section>
                        <q-item-section>
                            <!-- Feedback 2026-08-16: the full nutrient table
                                 would push every section below it off the
                                 screen, so it lives behind a disclosure on
                                 the summary line. Collapsed shows the one
                                 number that matters (kcal) and where it came
                                 from. -->
                            <div v-if="detail.nutrition_food">
                                <div class="row items-center q-gutter-xs">
                                    <div class="column items-start stock-detail__shrink">
                                        <span class="dora-text-primary ellipsis">
                                            {{ detail.nutrition_food.name }}
                                        </span>
                                        <span class="dora-text-muted stock-detail__caption">
                                            <template v-if="detail.nutrition_food.kcal_per_100g !== null">
                                                {{ Math.round(detail.nutrition_food.kcal_per_100g) }} kcal / 100g ·
                                            </template>
                                            {{ detail.nutrition_food.source_label }}
                                        </span>
                                    </div>
                                    <q-space />
                                    <BaseButton
                                        variant="ghost"
                                        dense
                                        size="sm"
                                        :icon="nutritionExpanded ? ICONS.collapse : ICONS.expand"
                                        label="Details"
                                        @click="nutritionExpanded = !nutritionExpanded"
                                    />
                                    <BaseButton
                                        variant="ghost"
                                        dense
                                        size="sm"
                                        :icon="ICONS.search"
                                        :disable="busy"
                                        aria-label="Search for a different food"
                                        @click="foodPickerOpen = true"
                                    >
                                        <BaseTooltip>Link a different food</BaseTooltip>
                                    </BaseButton>
                                    <BaseButton
                                        variant="danger-icon"
                                        size="sm"
                                        :icon="ICONS.close"
                                        :disable="busy"
                                        aria-label="Unlink food"
                                        @click="onUnlinkFood"
                                    >
                                        <BaseTooltip>Unlink</BaseTooltip>
                                    </BaseButton>
                                </div>
                                <NutritionFactsList
                                    v-if="nutritionExpanded"
                                    :food="detail.nutrition_food"
                                    class="q-mt-sm"
                                />
                            </div>
                            <!-- Unlinked, but the matcher found something.
                                 Framed as a question with the guess visibly
                                 marked "Suggested" rather than pre-filled into
                                 the row: the user must be able to tell at a
                                 glance that nothing has been saved yet
                                 (P12 No-invent). -->
                            <div
                                v-else-if="detail.nutrition_suggestion"
                                class="nutrition-suggestion"
                            >
                                <div class="row items-center q-gutter-xs no-wrap">
                                    <q-badge
                                        class="nutrition-suggestion__tag"
                                        :label="detail.nutrition_suggestion.is_strong
                                            ? 'Suggested' : 'Possible match'"
                                    />
                                    <span class="dora-text-primary ellipsis">
                                        {{ detail.nutrition_suggestion.name }}
                                    </span>
                                </div>
                                <div class="dora-text-muted nutrition-suggestion__meta">
                                    <template v-if="detail.nutrition_suggestion.kcal_per_100g !== null">
                                        {{ Math.round(detail.nutrition_suggestion.kcal_per_100g) }} kcal / 100g ·
                                    </template>
                                    {{ detail.nutrition_suggestion.source_label }} ·
                                    matched on the name, not saved yet
                                </div>
                                <div class="row items-center q-gutter-xs q-mt-xs">
                                    <BaseButton
                                        variant="primary"
                                        dense
                                        size="sm"
                                        label="Use this"
                                        :disable="busy"
                                        @click="onAcceptSuggestion"
                                    />
                                    <BaseButton
                                        variant="ghost"
                                        dense
                                        size="sm"
                                        :icon="ICONS.search"
                                        :disable="busy"
                                        aria-label="Search for a food"
                                        @click="foodPickerOpen = true"
                                    >
                                        <BaseTooltip>Search for a food yourself</BaseTooltip>
                                    </BaseButton>
                                    <q-space />
                                    <BaseButton
                                        variant="ghost"
                                        dense
                                        size="sm"
                                        label="Not a food"
                                        :disable="busy"
                                        @click="onIgnoreNutrition"
                                    >
                                        <BaseTooltip>
                                            Stop suggesting a food for this item
                                        </BaseTooltip>
                                    </BaseButton>
                                </div>
                            </div>
                            <!-- Feedback 2026-08-16: the search affordance is
                                 always present and is just the icon; "Not a
                                 food" is gone from this state because it's an
                                 answer to a question Dora hasn't asked here —
                                 it belongs on the suggestion above, and in
                                 bulk under Kitchen setup → Nutrition matching.
                                 Searching from the ignored state and linking
                                 something un-ignores the item server-side, so
                                 there's no order to get wrong. -->
                            <div v-else class="row items-center q-gutter-xs">
                                <span class="dora-text-muted">
                                    <template v-if="detail.nutrition_ignored">
                                        Ignored
                                    </template>
                                    <template v-else>Not linked</template>
                                </span>
                                <q-space />
                                <!-- Feedback 2026-08-17: no explicit "Track
                                     again" button. Linking a food from the
                                     search dialog un-ignores the item
                                     server-side, so the search affordance
                                     beside it already *is* the un-ignore —
                                     and it's the one that leaves the item in
                                     a useful state rather than back at
                                     "Not linked". -->
                                <BaseButton
                                    variant="ghost"
                                    dense
                                    size="sm"
                                    :icon="ICONS.search"
                                    :disable="busy"
                                    aria-label="Search for a food"
                                    @click="foodPickerOpen = true"
                                >
                                    <BaseTooltip>Search for a food to link</BaseTooltip>
                                </BaseButton>
                            </div>
                        </q-item-section>
                    </q-item>

                    <q-item>
                        <q-item-section class="dora-text-secondary text-weight-bold dora-inline-edit__label">Expiry</q-item-section>
                        <q-item-section>
                            <!-- Feedback 2026-08-16: the set-expiry control leads
                                 the row, ahead of the date, and carries the same
                                 expiry glyph the overview row uses (shared via
                                 `helpers/expiryIndicator`) so the state reads the
                                 same in both places. It stays a plain button —
                                 the overview's is a dropdown, which this row
                                 doesn't need since the push shortcuts are already
                                 spelled out beside it.
                                 Feedback 2026-08-17: the "Set" label is dropped —
                                 the glyph plus the date sitting next to it carry
                                 the meaning, and the word competed with the
                                 +1d/+7d/+14d verbs for the same row. The label
                                 moves to `aria-label` so the button keeps an
                                 accessible name (D-rule: icon-only controls are
                                 still named). -->
                            <div class="row items-center q-gutter-xs">
                                <BaseButton
                                    variant="ghost"
                                    dense
                                    size="sm"
                                    :icon="expiryIndicator.icon"
                                    :color="expiryIndicator.colour ?? undefined"
                                    :class="expiryIndicator.cssClass ?? undefined"
                                    aria-label="Set expiry date"
                                    @click="expiryDialogOpen = true"
                                >
                                    <BaseTooltip>{{ expiryIndicator.tooltip }}</BaseTooltip>
                                </BaseButton>
                                <!-- Feedback 2026-08-21: the date (or the
                                     dash standing in for it) is the thing the
                                     eye lands on, so it opens the same picker
                                     the glyph button does rather than being
                                     dead text next to a live icon. A real
                                     <button>, so it's keyboard-reachable and
                                     named — styled to stay reading as text. -->
                                <button
                                    type="button"
                                    class="stock-detail__expiry-text dora-text-primary"
                                    :disabled="busy"
                                    aria-label="Set expiry date"
                                    @click="expiryDialogOpen = true"
                                >
                                    {{ detail.expiry_date ? formatDate(detail.expiry_date) : '–' }}
                                </button>
                                <q-space />
                                <!-- Feedback 2026-08-08: Clear sits at the left
                                     edge of the right-aligned cluster so showing/
                                     hiding it (it only exists when there's a date)
                                     doesn't nudge the +Nd buttons — those stay
                                     anchored to the right. -->
                                <BaseButton
                                    aria-label="Clear expiry"
                                    v-if="detail.expiry_date"
                                    variant="danger-icon"
                                    size="sm"
                                    :icon="ICONS.close"
                                    :disable="busy"
                                    @click="clearExpiry"
                                >
                                    <BaseTooltip>Clear expiry</BaseTooltip>
                                </BaseButton>
                                <BaseButton variant="subtle" dense label="+1d" :disable="busy" @click="shiftExpiry(1)" />
                                <BaseButton variant="subtle" dense label="+7d" :disable="busy" @click="shiftExpiry(7)" />
                                <BaseButton variant="subtle" dense label="+14d" :disable="busy" @click="shiftExpiry(14)" />
                            </div>
                        </q-item-section>
                    </q-item>

                    <q-item>
                        <!-- Feedback 2026-08-21: "Open / in-use" plus a
                             tooltip that opened on what opening *doesn't*
                             do read as a puzzle. One word for the row, one
                             sentence for the note (owner-picked wording). -->
                        <q-item-section class="dora-text-secondary text-weight-bold dora-inline-edit__label">Opened</q-item-section>
                        <q-item-section>
                            <div class="row items-center q-gutter-sm">
                                <q-toggle
                                    :model-value="detail.is_open"
                                    :disable="busy"
                                    @update:model-value="onToggleOpen"
                                />
                                <span v-if="detail.is_open && detail.opened_on" class="dora-text-secondary text-caption">
                                    Opened {{ formatDate(detail.opened_on) }}
                                </span>
                                <q-icon :name="ICONS.info_outline" size="16px" class="dora-text-secondary">
                                    <BaseTooltip max-width="320px">
                                        Flags this item as
                                        opened. Set a shorter
                                        expiry above if it's
                                        perishable.
                                    </BaseTooltip>
                                </q-icon>
                            </div>
                        </q-item-section>
                    </q-item>

                    <q-item>
                        <q-item-section class="dora-text-secondary text-weight-bold dora-inline-edit__label">Essential</q-item-section>
                        <q-item-section>
                            <div class="row items-center q-gutter-sm">
                                <q-toggle
                                    :model-value="detail.is_essential"
                                    :disable="busy"
                                    @update:model-value="onToggleFlagged"
                                />
                                <q-icon :name="ICONS.info_outline" size="16px" class="dora-text-secondary">
                                    <!-- Word-identical to the add-item
                                         dialog's copy (2026-08-21,
                                         owner-approved) — one
                                         explanation of Essential,
                                         not two. -->
                                    <BaseTooltip max-width="320px">
                                        Something you always want in
                                        the house. Dora chases it up
                                        as soon as it runs low,
                                        instead of waiting until
                                        it's gone.
                                    </BaseTooltip>
                                </q-icon>
                            </div>
                        </q-item-section>
                    </q-item>

                    <!-- Feedback 2026-08-16: stocktake mode's
                         Mute action tells the user they can
                         un-mute "from the item's detail page",
                         but the detail page never carried the
                         control. This row is that control — and
                         the only place the flag can be turned
                         back on. -->
                    <!-- 2026-08-20 feedback: gone entirely when
                         the install has stocktake switched off —
                         a per-item opt-in to a feature that
                         doesn't exist is just a confusing switch. -->
                    <q-item v-if="stocktakeEnabled">
                        <q-item-section class="dora-text-secondary text-weight-bold dora-inline-edit__label">Stocktake</q-item-section>
                        <q-item-section>
                            <div class="row items-center q-gutter-sm">
                                <q-toggle
                                    :model-value="detail.stocktake_alerts_are_enabled"
                                    :disable="busy"
                                    @update:model-value="onToggleStocktakeAlerts"
                                />
                                <!-- Feedback 2026-08-17: the running
                                     commentary beside the toggle is
                                     gone — the toggle's own position
                                     already says which way it's set —
                                     and the (?) is trimmed to the one
                                     sentence that says what the toggle
                                     does. -->
                                <q-icon :name="ICONS.info_outline" size="16px" class="dora-text-secondary">
                                    <BaseTooltip max-width="320px">
                                        Controls whether this item
                                        ever joins the stocktake
                                        queue.
                                    </BaseTooltip>
                                </q-icon>
                            </div>
                        </q-item-section>
                    </q-item>

                    <!-- FU-511 — per-item "Auto-add when low"
                         toggle removed. Auto-add is now a
                         single install-wide setting managed at
                         Settings → Admin → System → Stock
                         (off / essential-only / all), which
                         branches on this item's Essential flag
                         above. Rationale: the per-item toggle
                         was redundant with `is_essential` for
                         the "staple you never want to run
                         out of" use it was designed for. -->

                    <!-- Feedback 2026-06-18 (round 3): notes
                         gets a real outlined input so the
                         empty state reads as "type here"
                         rather than a dash. Autogrow lets the
                         row expand vertically as the user
                         types. -->
                    <q-item>
                        <q-item-section class="dora-text-secondary text-weight-bold dora-inline-edit__label">Notes</q-item-section>
                        <q-item-section>
                            <q-input
                                v-model="form.notes"
                                dense
                                outlined
                                type="textarea"
                                autogrow
                                placeholder="Things to remember..."
                                @blur="saveNotesIfDirty"
                            />
                        </q-item-section>
                    </q-item>
                </q-list>

                <!-- Preferred buys (FU-211) — free-text "what I
                     actually buy" reminders: not a product/SKU,
                     just a personal memory aid (and a future
                     shopping-list hint).

                     Owner 2026-11-03: shown and used as normal
                     unless this item has a linked product, which
                     then answers "which one do I buy?" with real
                     SKUs and prices (`usesOffers`). Rows already
                     stored are kept; unlinking brings them back. -->
                <template v-if="!usesOffers(detail.products.length, productsEnabled)">
                <!-- Feedback 2026-06-18 (round 4): the explainer
                     ("What you actually buy for this — e.g.
                     Vitasoy Oat Milky 1L") moves to an info-hover
                     next to the heading. Same pattern as the
                     toggle rows in the basics list. -->
                <div class="q-mt-md dora-text-secondary text-weight-bold q-mb-sm row items-center q-gutter-xs">
                    <span>Preferred buys</span>
                    <q-icon :name="ICONS.info_outline" size="14px" class="dora-text-muted">
                        <BaseTooltip max-width="320px">
                            What you actually buy for this, e.g.
                            “Vitasoy Oat Milky 1L”.
                        </BaseTooltip>
                    </q-icon>
                </div>
                <!-- Feedback 2026-06-18 (round 3): the manual
                     reorder buttons are gone — these reminders
                     are scanned alphabetically more often than
                     they're ranked. Backend still stores a
                     position (kept so historical data isn't
                     disturbed), but the UI sorts the list
                     A-Z client-side. -->
                <q-list
                    v-if="preferredBuys.length"
                    separator
                    bordered
                    class="rounded-borders q-mb-sm"
                >
                    <q-item
                        v-for="pb in preferredBuys"
                        :key="pb.preferred_buy_id"
                    >
                        <q-item-section>
                            <q-input
                                v-if="editingBuyId === pb.preferred_buy_id"
                                v-model="editingBuyLabel"
                                dense
                                outlined
                                autofocus
                                maxlength="255"
                                @blur="saveBuyRename(pb)"
                                @keydown.enter.prevent="saveBuyRename(pb)"
                                @keydown.esc.prevent="editingBuyId = null"
                            />
                            <q-item-label v-else>{{ pb.label }}</q-item-label>
                        </q-item-section>
                        <q-item-section side>
                            <div class="row items-center no-wrap">
                                <BaseButton
                                    :aria-label="`Rename ${pb.label}`"
                                    variant="icon"
                                    :icon="ICONS.edit"
                                    :disable="busy"
                                    @click="startBuyRename(pb)"
                                >
                                    <BaseTooltip>Rename</BaseTooltip>
                                </BaseButton>
                                <BaseButton
                                    :aria-label="`Remove ${pb.label}`"
                                    variant="icon"
                                    :icon="ICONS.delete_outline"
                                    :disable="busy"
                                    @click="deleteBuy(pb)"
                                >
                                    <BaseTooltip>Remove</BaseTooltip>
                                </BaseButton>
                            </div>
                        </q-item-section>
                    </q-item>
                </q-list>
                <div class="row items-center no-wrap q-gutter-sm">
                    <q-input
                        v-model="newBuyLabel"
                        dense
                        outlined
                        class="col"
                        maxlength="255"
                        placeholder="Add a preferred buy"
                        @keydown.enter.prevent="addBuy"
                    />
                    <BaseButton
                        variant="primary"
                        :icon="ICONS.add"
                        label="Add"
                        :disable="!newBuyLabel.trim() || busy"
                        @click="addBuy"
                    />
                </div>
                </template>

                <!-- "Your prices" widget: baseline, latest
                     price, [Log a price] (the shared PriceEntry
                     dialog) and Full history. -->
                <template v-if="moneyEnabled">
                    <!-- q-mt-lg: owner 2026-10-17, "a bit more
                         top margin" — it sat tight under the
                         basics list / preferred buys. -->
                    <YourPricesWidget
                        class="q-mt-lg"
                        :your-prices="detail.your_prices ?? null"
                        :prefill="detail.price_entry_prefill ?? null"
                        :stores="storesList"
                        :busy="busy"
                        :stock-item-id="stockItemId"
                        :item-name="detail.name"
                        @submit="addObservation"
                    >
                    <!-- Owner 2026-10-17 restyle: a labelled
                         section, amounts in one right-hand column
                         (D-018), the measure + when/where as the
                         row's text. -->
                    <div v-if="priceObservations.length" class="dora-your-prices__recent">
                        <div class="dora-your-prices__label dora-your-prices__recent-label">Recent prices</div>
                        <q-list separator class="dora-your-prices__list">
                            <q-item
                                v-for="obs in shownObservations"
                                :key="obs.observation_id"
                            >
                                <q-item-section>
                                    <q-item-label>{{ formatObsMeasure(obs) }}</q-item-label>
                                    <q-item-label caption>
                                        {{ relativeTime(obs.observed_at) }}
                                        <span v-if="obs.store_name"> · {{ obs.store_name }}</span>
                                        <span v-if="obs.shopping_list_name"> · from {{ obs.shopping_list_name }}</span>
                                    </q-item-label>
                                </q-item-section>
                                <q-item-section side class="dora-your-prices__price">
                                    {{ formatMoney(obs.total_price) }}
                                </q-item-section>
                                <q-item-section side>
                                    <div class="row no-wrap">
                                        <BaseButton
                                            variant="icon"
                                            :icon="ICONS.edit"
                                            :disable="busy"
                                            aria-label="Edit price"
                                            @click="editingObservation = obs"
                                        >
                                            <BaseTooltip>Edit</BaseTooltip>
                                        </BaseButton>
                                        <BaseButton
                                            variant="icon"
                                            :icon="ICONS.delete_outline"
                                            :disable="busy"
                                            aria-label="Remove price"
                                            @click="deleteObservation(obs)"
                                        >
                                            <BaseTooltip>Remove</BaseTooltip>
                                        </BaseButton>
                                    </div>
                                </q-item-section>
                            </q-item>
                        </q-list>
                        <BaseButton
                            v-if="priceObservations.length > RECENT_PRICES_SHOWN"
                            variant="subtle"
                            class="q-mt-xs"
                            :label="showAllObservations ? 'Show fewer' : `Show all ${priceObservations.length}`"
                            @click="showAllObservations = !showAllObservations"
                        />
                    </div>
                    </YourPricesWidget>
                </template>
            </div>
        </div>
    </template>

    <BaseDialog
        :model-value="editingObservation !== null"
        title="Edit price"
        closable
        @update:model-value="(open: boolean) => { if (!open) editingObservation = null; }"
    >
        <q-card-section v-if="editingObservation">
            <PriceEntry
                mode="shelf"
                :initial="editingObservation"
                :stores="storesList"
                :busy="busy"
                @submit="updateObservation"
                @cancel="editingObservation = null"
            />
        </q-card-section>
    </BaseDialog>

    <BaseDialog v-model="expiryDialogOpen" title="Set expiry" closable card-style="min-width: 320px">
        <q-card-section>
            <q-date v-model="expiryDraft" mask="YYYY-MM-DD" />
        </q-card-section>
        <template #actions>
            <BaseButton variant="danger-ghost" label="Clear" @click="onSetExpiry(null)" />
            <BaseButton variant="ghost" label="Cancel" v-close-popup />
            <BaseButton variant="primary" label="Save" :loading="busy" @click="onSetExpiry(expiryDraft)" />
        </template>
    </BaseDialog>

    <NutritionFoodPicker
        v-if="nutritionIsComplex && detail"
        v-model="foodPickerOpen"
        :item-name="detail.name"
        @picked="onFoodPicked"
    />
</template>

<script lang="ts" setup>
    import { computed, ref, watch } from 'vue';
    import { useQuasar } from 'quasar';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseDropdown from 'src/components/BaseDropdown.vue';
    import StoreLogo from 'src/components/StoreLogo.vue';
    import BuyVerdictCard from 'src/components/stock/BuyVerdictCard.vue';
    import NutritionFactsList from 'src/components/stock/NutritionFactsList.vue';
    import NutritionFoodPicker from 'src/components/stock/NutritionFoodPicker.vue';
    import PantryBeliefCard from 'src/components/stock/PantryBeliefCard.vue';
    import PlannedDemandCard from 'src/components/stock/PlannedDemandCard.vue';
    import StockLevelDot from 'src/components/stock/StockLevelDot.vue';
    import PriceEntry from 'src/components/dora/PriceEntry.vue';
    import YourPricesWidget from 'src/components/dora/YourPricesWidget.vue';
    import { useBuyVerdictActions } from 'src/composables/useBuyVerdictActions';
    import { useConfirm } from 'src/composables/useConfirm';
    import { formatDate } from 'src/composables/useDateFormat';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import { useLocationOptions } from 'src/composables/useLocationOptions';
    import { formatMoney } from 'src/composables/useMoney';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { useNutritionMode } from 'src/composables/useNutritionMode';
    import { usePantryBeliefs } from 'src/composables/usePantryBeliefs';
    import { usePlannedDemand } from 'src/composables/usePlannedDemand';
    import { useStockItemActions } from 'src/composables/useStockItemActions';
    import { useStockItemDetail } from 'src/composables/useStockItemDetail';
    import { expiryIndicatorFor } from 'src/helpers/expiryIndicator';
    import { formatQuantity } from 'src/helpers/formatQuantity';
    import { relativeTime } from 'src/helpers/relativeTime';
    import { usesOffers } from 'src/models/shoppingList';
    import type {
        PreferredBuy,
        PriceEntryValue,
        PriceObservation,
    } from 'src/models/stockItemDetail';
    import { isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useLocationStore } from 'src/stores/locationStore';
    import { useStockGroupStore } from 'src/stores/stockGroupStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { useStoresStore } from 'src/stores/storesStore';
    import { ICONS } from 'src/style/icons';

    const {
        stockItemApi,
        stockItemId,
        detail,
        busy,
        form,
        buyVerdict,
        nutritionExpanded,
        newBuyLabel,
        editingBuyId,
        editingBuyLabel,
        loadDetail,
        saveField,
        withBusyReload,
    } = useStockItemDetail();

    const $q = useQuasar();
    const stockItemStore = useStockItemStore();
    const stockLevelStore = useStockLevelStore();
    const stockGroupStore = useStockGroupStore();
    const locationStore = useLocationStore();
    // Stores picker. Hydrated lazily by the page (R-016 ensureLoadedAsync);
    // the dropdown shows whatever the user has curated under Settings →
    // Stores.
    const storesStore = useStoresStore();
    const actions = useStockItemActions();
    // shared handlers for the BuyVerdictCard's mark_stocked +
    // remove_from_list actions. Same seams the row card uses.
    const verdictActions = useBuyVerdictActions();

    // 2026-08-20 — install-wide stocktake switch; hides the per-item mute
    // toggle when the household doesn't use stocktake at all.
    const { products: productsEnabled, stocktake: stocktakeEnabled } = useFeatureFlags();
    const { moneyEnabled } = useMoneyEnabled();
    // Only complex mode gives stock items a food to link; simple mode's kcal
    // is typed on the recipe, so the row is hidden entirely below that (R-029).
    const { isComplex: nutritionIsComplex } = useNutritionMode();
    const foodPickerOpen = ref(false);

    // inferred belief for this item (shared cache; the page loads it).
    const pantryBeliefs = usePantryBeliefs();
    const belief = computed(() =>
        detail.value ? pantryBeliefs.beliefFor(detail.value.stock_item_id) : null,
    );
    // What the upcoming plan wants of this item (shared cache, same shape).
    const plannedDemandCache = usePlannedDemand();
    const plannedDemand = computed(() =>
        detail.value ? plannedDemandCache.demandFor(detail.value.stock_item_id) : null,
    );

    // Full-path, searchable location options, like every location picker.
    const { locationOptions, filterLocations } = useLocationOptions(() => locationStore.tree);

    // Stock groups — loaded once by the page for the inline picker. (Owned
    // locally rather than via a store; this is the only consumer and the
    // list is small.)
    const groupOptions = computed(() =>
        stockGroupStore.stockGroups.map((g) => ({ label: g.name, value: g.stock_group_id })),
    );
    const storeOptions = computed(() =>
        storesStore.stores.map((s) => ({
            label: s.name,
            value: s.store_id,
            has_image: s.has_image,
        })),
    );
    // resolve the level *sequence* (StockLevelDot maps it to a
    // colour, or the sunken fallback when null). Untracked items (no
    // level_id) get null → muted bg via the component's internal
    // fallback.
    const detailLevelSequence = computed<number | null>(() => {
        const levelId = detail.value?.stock_level_id;
        if (!levelId) return null;
        const seq = stockLevelStore.levelById.get(levelId)?.sequence;
        return typeof seq === 'number' ? seq : null;
    });

    // ── Inline-edit field savers (C-1b.1) ───────────────────────────────
    async function saveNameIfDirty() {
        if (!detail.value) return;
        const next = form.name.trim();
        if (!next || next === detail.value.name) return;
        await saveField({ name: next });
    }
    async function saveNotesIfDirty() {
        if (!detail.value) return;
        const next = form.notes ?? '';
        if (next === (detail.value.notes ?? '')) return;
        await saveField({ notes: next.length > 0 ? next : null });
    }
    async function onChangeLocation(value: string | null) {
        if (!detail.value || value === detail.value.stock_location_id) return;
        // Route null through the explicit clear flag — the relationship is
        // mapped `lazy="noload"` so a present-but-null FK can silently
        // no-op server-side, leaving the picker rebounding to its prior
        // value after refresh.
        if (value === null) {
            await saveField({ clear_stock_location: true });
        } else {
            await saveField({ stock_location_id: value });
        }
    }
    async function onClearLocation() {
        if (!detail.value || detail.value.stock_location_id === null) return;
        await saveField({ clear_stock_location: true });
    }
    async function onChangeGroup(value: string | null) {
        if (!detail.value || value === detail.value.stock_group_id) return;
        if (value === null) {
            await saveField({ clear_stock_group: true });
        } else {
            await saveField({ stock_group_id: value });
        }
    }
    async function onClearGroup() {
        if (!detail.value || detail.value.stock_group_id === null) return;
        await saveField({ clear_stock_group: true });
    }
    async function onChangeUsualStore(value: string | null) {
        if (!detail.value || value === detail.value.usual_store_id) return;
        if (value === null) {
            await saveField({ clear_usual_store: true });
        } else {
            await saveField({ usual_store_id: value });
        }
    }
    async function onToggleFlagged(value: boolean) {
        await saveField({ is_essential: value });
    }
    async function onToggleStocktakeAlerts(value: boolean) {
        await saveField({ stocktake_alerts_are_enabled: value });
    }

    // Nutrition complex-mode link. The picker has already persisted the food
    // (resolving a live suggestion server-side if needed) and hands back its
    // id; all that's left here is binding it to this item.
    async function onFoodPicked(foodId: string) {
        await saveField({ nutrition_food_id: foodId });
    }
    async function onUnlinkFood() {
        await saveField({ clear_nutrition_food: true });
    }

    // Accepting a suggestion is the same write as picking one by hand — the
    // suggestion was only ever a candidate on screen, and this button press is
    // the human confirmation that turns it into a link (P12 No-invent).
    async function onAcceptSuggestion() {
        const suggested = detail.value?.nutrition_suggestion;
        if (!suggested) return;
        await saveField({ nutrition_food_id: suggested.nutrition_food_id });
    }
    async function onIgnoreNutrition() {
        await saveField({ nutrition_ignored: true });
    }
    // Feedback 2026-08-17: the "Track again" button that called an
    // `onUnignoreNutrition` here is gone. Un-ignoring now happens implicitly —
    // `update_stock_item` clears `nutrition_ignored` whenever a food is linked,
    // so picking one from the search dialog is the un-ignore. The bulk
    // Settings → Kitchen setup → Nutrition matching screen keeps an explicit
    // control for the "I mis-tagged a batch" case.
    // The row's "+N days" rule, server-side (one rule, household today).
    function shiftExpiry(days: number) {
        void withBusyReload(() => actions.pushExpiry(stockItemId.value, days));
    }
    function clearExpiry() {
        void saveField({ expiry_date: null });
    }

    // ── Preferred buys (FU-211) — free-text "what I actually buy" reminders.
    // Separate from the Product overlay; always available. Mutations reuse
    // withBusyReload so the list reflects the server after each change. The
    // server sends them A–Z (R-003: it owns the order).
    const preferredBuys = computed(() => detail.value?.preferred_buys ?? []);

    async function addBuy() {
        const label = newBuyLabel.value.trim();
        if (!label) return;
        await withBusyReload(() => stockItemApi.addPreferredBuyAsync(stockItemId.value, label));
        newBuyLabel.value = '';
    }
    function startBuyRename(pb: PreferredBuy) {
        editingBuyId.value = pb.preferred_buy_id;
        editingBuyLabel.value = pb.label;
    }
    async function saveBuyRename(pb: PreferredBuy) {
        if (editingBuyId.value !== pb.preferred_buy_id) return;
        const label = editingBuyLabel.value.trim();
        editingBuyId.value = null;
        if (!label || label === pb.label) return;
        await withBusyReload(() =>
            stockItemApi.updatePreferredBuyAsync(stockItemId.value, pb.preferred_buy_id, label),
        );
    }
    async function deleteBuy(pb: PreferredBuy) {
        await withBusyReload(() =>
            stockItemApi.deletePreferredBuyAsync(stockItemId.value, pb.preferred_buy_id),
        );
    }

    // ── Prices (FU-227 chunk 3) — YourPricesWidget owns the entry UX via
    // the shared PriceEntry component. This tab just exposes the list (with
    // delete) and a submit handler that talks to the API. R-003: server
    // derives per-unit cost; we never divide here.
    const priceObservations = computed(() => detail.value?.price_observations ?? []);
    // FU-706: a frequently logged item ran to hundreds of rows mid-tab.
    const RECENT_PRICES_SHOWN = 5;
    const showAllObservations = ref(false);
    const shownObservations = computed(() => (
        showAllObservations.value
            ? priceObservations.value
            : priceObservations.value.slice(0, RECENT_PRICES_SHOWN)
    ));
    const editingObservation = ref<PriceObservation | null>(null);
    const { confirm } = useConfirm();

    // Stores list for the optional store picker in PriceEntry (A2). Reuses
    // the `storesStore` instance above (FU-189 — usual store picker).
    const storesList = computed(() => storesStore.stores);

    async function addObservation(value: PriceEntryValue, done: () => void) {
        try {
            await withBusyReload(() => stockItemApi.addPriceObservationAsync(stockItemId.value, value));
        } catch (err) {
            // FU-976 — the rejection used to escape to the global handler, so
            // a 5xx showed the http client's toast *and* the "oopsie": two
            // toasts for one failure. One now; the dialog stays open.
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: "Couldn't log the price.",
                    caption: toastCaption(err),
                });
            }
            return;
        }
        stockItemStore.invalidatePriceFacts(stockItemId.value);
        // Only close the widget's dialog once the save landed (a throw above
        // keeps it open with the typed values).
        done();
    }
    // Multipack (FU-227 follow-up): "4 × 125g" instead of "500g flat" when
    // the observation carries a pack count. Per-pack = total / count.
    function formatObsMeasure(obs: PriceObservation): string {
        if (obs.pack_count != null && obs.pack_count > 1) {
            return `${obs.pack_count} × ${formatQuantity(obs.total_measure / obs.pack_count, obs.unit)}`;
        }
        return formatQuantity(obs.total_measure, obs.unit);
    }

    async function updateObservation(value: PriceEntryValue) {
        const obs = editingObservation.value;
        if (!obs) return;
        try {
            await withBusyReload(() => stockItemApi.updatePriceObservationAsync(
                stockItemId.value, obs.observation_id, value,
            ));
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: "Couldn't save the price.",
                    caption: toastCaption(err),
                });
            }
            return;
        }
        editingObservation.value = null;
        stockItemStore.invalidatePriceFacts(stockItemId.value);
    }

    async function deleteObservation(obs: PriceObservation) {
        const ok = await confirm({
            title: 'Remove this price?',
            message: `${formatMoney(obs.total_price)} for ${formatObsMeasure(obs)}, ${relativeTime(obs.observed_at)}.`,
            okLabel: 'Remove',
            destructive: true,
        });
        if (!ok) return;
        await withBusyReload(() =>
            stockItemApi.deletePriceObservationAsync(stockItemId.value, obs.observation_id),
        );
        stockItemStore.invalidatePriceFacts(stockItemId.value);
    }
    async function onToggleOpen() {
        if (!detail.value) return;
        // DR-5 (FU-578 #2) — mirrors StockItemRow.onToggleOpen. Opening
        // prompts for the effective expiry; a null plan means the prompt was
        // dismissed/cancelled, so we write nothing (the toggle snaps back
        // since its model is bound one-way to `detail.is_open`).
        const patch = await actions.planOpenToggle(detail.value);
        if (!patch) return;
        await withBusyReload(() => stockItemStore.updateStockItemAsync(patch));
    }
    // closes FU-437 (add_to_list) and FU-454 (mark_stocked +
    // remove_from_list). Delegates to the shared `useBuyVerdictActions`
    // composable so the same math runs from every card mount (row card,
    // detail-page card, shopping-list card).
    // `add_to_list` never reaches here: the card renders that action as an
    // `AddToListButton`, which owns the add/toggle-off itself (2026-09-01).
    async function onBuyVerdictAction(
        kind: 'add_to_list' | 'skip' | 'mark_stocked' | 'remove_from_list' | 'none',
    ) {
        if (kind === 'mark_stocked') {
            const ok = await verdictActions.markStocked(stockItemId.value);
            if (ok) await loadDetail();  // reload so the level chip repaints
            return;
        }
        if (kind === 'remove_from_list') {
            await verdictActions.removeFromAllOpenLists(stockItemId.value);
            return;
        }
        // `skip` / `none` — nothing to do.
    }
    // The store's level write refreshes the verdict, belief and demand overlays.
    async function onChangeStockLevel(stockLevelId: string) {
        await withBusyReload(() =>
            stockItemStore.updateStockLevelAsync({
                stock_item_id: stockItemId.value,
                stock_level_id: stockLevelId,
            }),
        );
    }

    // ── Expiry ───────────────────────────────────────────────────────────
    // Same indicator the overview row draws (R-002 — one helper, two callers).
    const expiryIndicator = computed(() =>
        expiryIndicatorFor(detail.value?.expiry_date ?? null),
    );
    const expiryDialogOpen = ref(false);
    const expiryDraft = ref<string | null>(null);
    watch(expiryDialogOpen, (open) => {
        if (open) expiryDraft.value = detail.value?.expiry_date ?? null;
    });
    async function onSetExpiry(value: string | null) {
        await withBusyReload(() =>
            stockItemStore.updateStockItemAsync({ stock_item_id: stockItemId.value, expiry_date: value }),
        );
        expiryDialogOpen.value = false;
    }
</script>

<style scoped>
    /* Mobile overflow — every field in this list is capped to its column so a
       long value can't push the row sideways. The `use-input` case (Location)
       is the loud one and is handled globally in `css/app.scss`
       (`.q-select--with-input`); this covers the rest of the list, e.g. Stock
       group, which overflowed by a smaller 23px for the same reason: `.q-field`
       has `max-width: none` and sizes to content inside `q-item-section`'s
       column flex layout. Measured at 375px — see app.scss for the full note. */
    .dora-inline-edit :deep(.q-field) {
        width: 100%;
        max-width: 100%;
    }

    /* Round-13: the level picker's `outline` prop drew the border in
       `currentColor` (full-strength text) which read as a glaring
       bright-white box against the other softer outlined inputs on the
       page. Switched to `flat` + this custom border that mirrors the
       q-field--outlined treatment (muted text-tint, primary on
       focus-within) so the picker sits visually alongside the other
       fields. */
    .dora-level-picker {
        border: 1px solid color-mix(in srgb, var(--text-primary) 22%, transparent);
        border-radius: 4px;
        transition: border-color 0.2s ease;
        /* Matches `.dora-inline-edit :deep(.q-field)` above so the picker is
           the same width as every other editor in the fact list. */
        width: 100%;
    }
    /* q-btn centres its content; with a full-width trigger that would float
       the level name in the middle and park the caret next to it. The label
       takes the slack instead, so the text sits left (like a q-field's value)
       and the caret pins to the right edge. */
    .dora-level-picker :deep(.q-btn__content) {
        flex-wrap: nowrap;
    }
    .dora-level-picker__label {
        display: flex;
        align-items: center;
        flex: 1 1 auto;
        min-width: 0;
        text-align: left;
    }
    .dora-level-picker:hover,
    .dora-level-picker:focus-within {
        border-color: var(--brand-primary);
    }

    /* The expiry date reads as text but behaves as the picker trigger
       (2026-08-21 feedback). Chrome stripped back to the row; the hover
       underline is the only affordance it needs sitting beside a button that
       does the same thing. Padding rather than a min-height so it doesn't
       stretch the row it shares with the +Nd shortcuts. */
    .stock-detail__expiry-text {
        padding: 6px 4px;
        border: none;
        background: none;
        font: inherit;
        color: inherit;
        cursor: pointer;
    }
    .stock-detail__expiry-text:hover:not(:disabled) {
        text-decoration: underline;
    }
    .stock-detail__expiry-text:disabled {
        cursor: default;
    }
    .stock-detail__expiry-text:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
        border-radius: 4px;
    }

    /* The label column of the inline-edit list. */
    .dora-inline-edit__label {
        max-width: 160px;
    }
    .stock-detail__store-logo {
        min-width: 0;
        padding-right: var(--space-2);
    }
    .stock-detail__shrink {
        min-width: 0;
    }
    .stock-detail__caption {
        font-size: var(--font-size-xs);
    }

    /* An unaccepted nutrition match. Deliberately set apart from the linked
       state above it — a dashed edge and a tag, so the row reads as "Dora is
       asking" rather than "this is set". Accent rather than a semantic colour:
       a suggestion is neither a warning nor a success. */
    .nutrition-suggestion {
        border: 1px dashed var(--border-strong);
        border-radius: var(--radius-md);
        padding: var(--space-2);
        background: var(--surface-sunken);
    }
    .nutrition-suggestion__tag {
        background: var(--surface-elevated);
        color: var(--text-secondary);
        font-size: var(--font-size-xs);
        font-weight: 600;
        padding: 1px var(--space-2);
    }
    .nutrition-suggestion__meta {
        font-size: var(--font-size-xs);
        line-height: 1.35;
        margin-top: 2px;
    }
</style>
