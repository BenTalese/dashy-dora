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
                                        <q-select
                                            v-model="form.stock_location_id"
                                            :options="locationOptions"
                                            emit-value
                                            map-options
                                            use-input
                                            fill-input
                                            hide-selected
                                            input-debounce="200"
                                            clearable
                                            dense
                                            borderless
                                            placeholder="–"
                                            @filter="filterLocations"
                                            @clear="onClearLocation"
                                            @update:model-value="onChangeLocation"
                                        />
                                    </q-item-section>
                                </q-item>

                                <!-- Empty-state dash via `display-value`:
                                     q-select's `placeholder` only renders
                                     under `use-input`, which these don't
                                     need. `display-value=undefined` lets
                                     q-select pick the normal label when a
                                     value is set; a string forces that
                                     string into the field. -->
                                <q-item>
                                    <q-item-section class="dora-text-secondary text-weight-bold dora-inline-edit__label">Stock group</q-item-section>
                                    <q-item-section>
                                        <q-select
                                            v-model="form.stock_group_id"
                                            :options="groupOptions"
                                            emit-value
                                            map-options
                                            clearable
                                            dense
                                            borderless
                                            :display-value="form.stock_group_id ? undefined : '–'"
                                            @clear="onClearGroup"
                                            @update:model-value="onChangeGroup"
                                        />
                                    </q-item-section>
                                </q-item>

                                <q-item>
                                    <q-item-section class="dora-text-secondary text-weight-bold dora-inline-edit__label">Usual store</q-item-section>
                                    <q-item-section>
                                        <q-select
                                            v-model="form.usual_store_id"
                                            :options="storeOptions"
                                            emit-value
                                            map-options
                                            clearable
                                            dense
                                            borderless
                                            :display-value="form.usual_store_id ? undefined : '–'"
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
                                        </q-select>
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
                                            <BaseButton variant="ghost" dense size="sm" label="+1d" :disable="busy" @click="shiftExpiry(1)" />
                                            <BaseButton variant="ghost" dense size="sm" label="+7d" :disable="busy" @click="shiftExpiry(7)" />
                                            <BaseButton variant="ghost" dense size="sm" label="+14d" :disable="busy" @click="shiftExpiry(14)" />
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

                                 Feedback 2026-08-16: hidden entirely when the
                                 Products overlay is on. The two answer the
                                 same question ("which one do I actually buy?")
                                 and Products answers it with real SKUs, prices
                                 and deals — showing both invites the user to
                                 maintain the same fact twice. Rows already
                                 stored are kept, not deleted; turning Products
                                 back off brings them straight back. -->
                            <template v-if="!productsEnabled">
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
                                            v-for="obs in priceObservations"
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
                                                <BaseButton
                                                    variant="icon"
                                                    :icon="ICONS.delete_outline"
                                                    :disable="busy"
                                                    aria-label="Remove price"
                                                    @click="deleteObservation(obs)"
                                                >
                                                    <BaseTooltip>Remove</BaseTooltip>
                                                </BaseButton>
                                            </q-item-section>
                                        </q-item>
                                    </q-list>
                                </div>
                                </YourPricesWidget>
                            </template>
                        </div>
                    </div>
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
                    <div v-if="detail.products.length > 0" class="row items-center q-mb-sm q-gutter-sm">
                        <div class="text-subtitle1">Linked products</div>
                        <q-space />
                        <BaseButton
                            variant="ghost"
                            :icon="ICONS.add"
                            label="Link another"
                            @click="onFindAndLink"
                        />
                    </div>

                    <div v-if="detail.products.length === 0" class="column items-center q-py-xl q-gutter-md">
                        <q-icon :name="ICONS.local_offer" size="48px" class="dora-text-secondary" />
                        <div class="text-subtitle1">No products linked yet</div>
                        <div class="dora-text-secondary text-caption text-center stock-detail__empty-copy">
                            Link a product to surface live deals and price
                            history for this stock item.
                        </div>
                        <BaseButton
                            variant="primary"
                            :icon="ICONS.local_offer"
                            label="Find &amp; link a product"
                            @click="onFindAndLink"
                        />
                    </div>

                    <div v-else class="row q-col-gutter-md">
                        <div
                            v-for="prod in sortedProducts"
                            :key="prod.product_id"
                            class="col-12 col-md-6"
                        >
                            <!-- cheapest card carries a "Cheapest"
                                 chip + a subtle highlight class so the
                                 cheaper option pops without needing a
                                 separate "Add cheapest" button (§2.4). -->
                            <q-card
                                bordered
                                flat
                                :class="{ 'dora-product-card--cheapest': isCheapest(prod) }"
                            >
                                <q-card-section class="row items-center no-wrap q-pb-xs">
                                    <StoreLogo
                                        :name="prod.store_name"
                                        :store-id="prod.store_id"
                                        :height="20"
                                        :width="34"
                                        class="q-mr-sm"
                                    />
                                    <div class="col">
                                        <div class="ellipsis text-weight-medium">{{ prod.name }}</div>
                                        <div class="text-caption dora-text-muted">
                                            {{ prod.store_name }}
                                            <span v-if="prod.size"> · {{ prod.size }}</span>
                                        </div>
                                    </div>
                                    <q-chip
                                        v-if="isCheapest(prod)"
                                        dense
                                        class="dora-chip--tint-positive"
                                    >
                                        Cheapest
                                    </q-chip>
                                    <DiscountChip
                                        :price-now="prod.price_now"
                                        :price-was="prod.price_was"
                                    />
                                </q-card-section>

                                <q-card-section class="row items-center q-py-xs">
                                    <div>
                                        <span v-if="prod.price_now !== null" class="text-h6">
                                            {{ formatMoney(prod.price_now) }}
                                        </span>
                                        <span
                                            v-if="isOnSpecial(prod)"
                                            class="text-caption dora-text-muted strike q-ml-xs"
                                        >
                                            {{ formatMoney(prod.price_was) }}
                                        </span>
                                    </div>
                                    <q-space />
                                    <TrendSparkline :values="priceHistory.get(prod.product_id) ?? []" />
                                </q-card-section>

                                <q-separator />
                                <q-card-actions align="right">
                                    <!-- MP-6 / L196 — the componentised cart
                                         button, finally on the third product
                                         surface. This was a hand-rolled button
                                         that silently added to the primary list
                                         (or fell back to the generic add), so
                                         it was the only place a product could
                                         reach a list *without* the cart-state
                                         UX the rest of the app has: the picker
                                         on 2+ lists, smart-remove on exactly
                                         one, and the on-a-list state showing on
                                         the control itself. -->
                                    <AddToListButton
                                        variant="row"
                                        :stock-item-id="stockItemId"
                                        :selected-product-id="prod.product_id"
                                        @click.stop
                                    />
                                    <BaseButton
                                        :aria-label="`Open on ${prod.store_name}`"
                                        v-if="isWebLink(prod.web_url)"
                                        variant="icon"
                                        :icon="ICONS.open_in_new"
                                        :href="prod.web_url"
                                        target="_blank"
                                        rel="noopener"
                                    >
                                        <BaseTooltip>Open on {{ prod.store_name }}</BaseTooltip>
                                    </BaseButton>
                                    <BaseButton :aria-label="`Unlink ${prod.name}`" variant="icon" :icon="ICONS.link_off" class="text-negative" @click="onUnlink(prod.product_id)">
                                        <BaseTooltip>Unlink</BaseTooltip>
                                    </BaseButton>
                                </q-card-actions>
                            </q-card>
                        </div>
                    </div>
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
                    <div class="row items-center q-mb-sm">
                        <div class="text-subtitle1">Substitutes</div>
                        <HelpHint topic="Substitutes" />
                        <q-space />
                        <BaseButton variant="primary" dense :icon="ICONS.add" label="Add substitute" @click="openSubstitutePicker" />
                    </div>

                    <div v-if="detail.substitutes.length === 0" class="dora-text-muted text-caption q-pa-md">
                        No substitutes yet. Add items that can stand in for this one.
                    </div>

                    <q-list v-else separator>
                        <q-item
                            v-for="sub in detail.substitutes"
                            :key="sub.stock_item_id"
                            clickable
                            @click="onOpenSubstitute(sub.stock_item_id)"
                        >
                            <q-item-section avatar class="stock-detail__sub-dot">
                                <StockLevelDot :sequence="sub.stock_level_sequence" size="12px">
                                    <BaseTooltip>{{ sub.stock_level_name ?? 'No level set' }}</BaseTooltip>
                                </StockLevelDot>
                            </q-item-section>
                            <q-item-section>
                                <q-item-label>{{ sub.name }}</q-item-label>
                                <!-- optional ratio shown above
                                     notes; cook-mode picker mirrors this
                                     same layout so the user reads the
                                     swap the same way in both places. -->
                                <q-item-label v-if="formatSubstituteRatio(sub)" caption class="dora-text-secondary">
                                    {{ formatSubstituteRatio(sub) }}
                                </q-item-label>
                                <q-item-label v-if="sub.notes" caption class="dora-text-muted">
                                    {{ sub.notes }}
                                </q-item-label>
                            </q-item-section>
                            <q-item-section side>
                                <!-- pencil icon opens the metadata
                                     edit dialog (notes + ratio). Sits next
                                     to the unlink action so the substitute
                                     row carries both lifecycle controls
                                     without the row getting cluttered. -->
                                <div class="row no-wrap items-center">
                                    <BaseButton
                                        :aria-label="`Edit note or ratio for ${sub.name}`"
                                        variant="icon"
                                        :icon="ICONS.edit"
                                        @click.stop="onEditSubstituteMetadata(sub)"
                                    >
                                        <BaseTooltip>Edit note / ratio</BaseTooltip>
                                    </BaseButton>
                                    <BaseButton
                                        :aria-label="`Remove substitute ${sub.name}`"
                                        variant="icon"
                                        :icon="ICONS.link_off"
                                        class="text-negative"
                                        @click.stop="onRemoveSubstitute(sub.stock_item_id)"
                                    >
                                        <BaseTooltip>Remove substitute</BaseTooltip>
                                    </BaseButton>
                                </div>
                            </q-item-section>
                        </q-item>
                    </q-list>

                    <!-- metadata edit dialog. v-model-controlled
                         open state + a snapshot of the substitute being
                         edited (driven by `onEditSubstituteMetadata`). -->
                    <SubstituteMetadataDialog
                        v-if="editingSubstitute"
                        v-model="substituteMetadataOpen"
                        :from-name="detail.name"
                        :to-name="editingSubstitute.name"
                        :initial-notes="editingSubstitute.notes"
                        :initial-ratio-quantity-in="editingSubstitute.ratio_quantity_in"
                        :initial-ratio-unit-in="editingSubstitute.ratio_unit_in"
                        :initial-ratio-quantity-out="editingSubstitute.ratio_quantity_out"
                        :initial-ratio-unit-out="editingSubstitute.ratio_unit_out"
                        :saving="substituteMetadataSaving"
                        @save="onSaveSubstituteMetadata"
                    />

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
                    <!-- Dora's own QR label. Fetched through the authenticated
                         http client (see useQrLabels) the first time this tab
                         is opened, not on page load — most visits never come
                         here. -->
                    <div class="q-mb-lg">
                        <div class="row items-center q-mb-sm">
                            <!-- D-008 carve-out (owner, 2026-09-01): asked for
                                 "QR Label" title-cased here. It's a section
                                 heading, not an interactive control, so the
                                 sentence-case rule for buttons/labels doesn't
                                 bind it; the Help topic key stays lowercase. -->
                            <div class="text-subtitle1">QR Label</div>
                            <HelpHint topic="QR label" />
                            <q-space />
                            <BaseButton
                                variant="secondary"
                                dense
                                :icon="ICONS.print"
                                label="Print"
                                @click="openSingleQrSheet"
                            />
                        </div>
                        <div class="row items-start">
                            <AppSkeleton
                                v-if="qrLoading"
                                type="rect"
                                width="256px"
                                height="256px"
                            />
                            <img
                                v-else-if="qrSrc"
                                :src="qrSrc"
                                alt="QR code"
                                class="stock-detail__qr"
                            />
                        </div>
                        <!-- The error sits BELOW the image rather than in place
                             of it: Print can fail (blocked pop-up) after the
                             code itself loaded fine, and swapping the loaded QR
                             out for that message would read as the code having
                             broken too. -->
                        <div v-if="qrError" class="text-negative text-caption q-mt-sm">
                            {{ qrError }}
                        </div>
                    </div>

                    <div>
                        <div class="row items-center q-mb-sm">
                            <div class="text-subtitle1">Barcodes</div>
                            <HelpHint topic="Barcodes" />
                            <q-space />
                            <BaseButton
                                variant="primary"
                                dense
                                :icon="ICONS.add"
                                label="Add barcode"
                                @click="onAddBarcodeClick"
                            />
                        </div>
                        <div
                            v-if="detail.barcodes.length === 0"
                            class="dora-text-muted text-caption q-pa-md"
                        >
                            No barcodes yet.
                        </div>
                        <q-list v-else separator>
                            <q-item
                                v-for="bc in detail.barcodes"
                                :key="bc.barcode_id"
                            >
                                <q-item-section>
                                    <q-item-label class="dora-text-monospace">
                                        {{ bc.barcode }}
                                    </q-item-label>
                                    <!-- Feedback 2026-08-24: the `direct` rows
                                         used to be captioned "direct", which is
                                         what most people see and says nothing
                                         on its own. Only the exception is
                                         annotated now — a code that came along
                                         with a linked Product, and so isn't
                                         removable here. -->
                                    <q-item-label
                                        v-if="bc.source === 'via_product'"
                                        caption
                                        class="dora-text-muted"
                                    >
                                        (from product: {{ bc.product_name ?? '–' }})
                                    </q-item-label>
                                </q-item-section>
                                <q-item-section side>
                                    <BaseButton
                                        :aria-label="`Remove barcode ${bc.barcode}`"
                                        v-if="bc.source === 'direct'"
                                        variant="icon"
                                        :icon="ICONS.delete"
                                        class="text-negative"
                                        @click="onRemoveBarcode(bc.barcode_id)"
                                    >
                                        <BaseTooltip>Remove barcode</BaseTooltip>
                                    </BaseButton>
                                </q-item-section>
                            </q-item>
                        </q-list>

                        <!-- Add-barcode dialog. Textbox by default;
                             a future polish slot could add a "scan" button
                             when the camera is available. -->
                        <BaseDialog
                            v-model="addBarcodeOpen"
                            title="Add a barcode"
                            closable
                            card-style="min-width: 320px; max-width: 420px"
                        >
                            <q-card-section>
                                <div class="text-caption dora-text-muted q-mb-sm">
                                    Scanning this code will open
                                    <strong>{{ detail.name }}</strong>.
                                </div>
                                <q-input
                                    v-model="addBarcodeValue"
                                    outlined
                                    dense
                                    autofocus
                                    placeholder="e.g. 9300675001120"
                                    label="Barcode (EAN / UPC)"
                                    :error="!!addBarcodeError"
                                    :error-message="addBarcodeError ?? undefined"
                                    @keydown.enter.prevent="onConfirmAddBarcode"
                                />
                            </q-card-section>
                            <template #actions>
                                <BaseButton variant="ghost" label="Cancel" v-close-popup />
                                <BaseButton
                                    variant="primary"
                                    label="Add"
                                    :loading="addBarcodeSaving"
                                    :disable="addBarcodeValue.trim().length === 0"
                                    @click="onConfirmAddBarcode"
                                />
                            </template>
                        </BaseDialog>
                    </div>
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
                    <div v-if="lifecycleEvents.length === 0" class="dora-text-muted text-caption q-pa-md">
                        Nothing logged for this item yet.
                    </div>
                    <q-timeline v-else color="primary">
                        <q-timeline-entry
                            v-for="ev in lifecycleEvents"
                            :key="ev.id"
                            :title="ev.title"
                            :subtitle="formatLocaleDateTime(ev.at)"
                            :icon="ev.icon"
                            :color="ev.color"
                        >
                            <div v-if="ev.body" class="dora-text-secondary">
                                {{ ev.body }}
                            </div>
                        </q-timeline-entry>
                    </q-timeline>
                    <!-- 2026-06-30 — honest truncation footer. Server caps
                         each event kind at HISTORY_PER_KIND_CAP (50) and
                         reports what got dropped as `history_older_count`.
                         When the number is 0 the footer is silent; the old
                         behaviour was a silent client-side slice(0, 60)
                         which hid arbitrary truncation. -->
                    <div
                        v-if="detail && (detail.history_older_count ?? 0) > 0"
                        class="dora-text-muted text-caption q-pa-md q-pl-none text-center"
                    >
                        {{ detail.history_older_count }} older event{{ (detail.history_older_count ?? 0) === 1 ? '' : 's' }} not shown
                    </div>
                </q-tab-panel>
            </q-tab-panels>
        </div>
        </FadeTransition>

        <!-- ── Set-expiry dialog ──────────────────────────────────────── -->
        <BlockedByRecipesDialog :recipe-names="blockedByRecipes" @close="blockedByRecipes = []" />

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

        <!-- ── Add-substitute picker dialog ───────────────────────────── -->
        <BaseDialog v-model="subPickerOpen" title="Add a substitute" closable card-style="width: 560px; max-width: 95vw">
                <q-card-section>
                    <SearchInput v-model="subSearch" autofocus :debounce="150" placeholder="Search stock items" />
                </q-card-section>
                <q-card-section class="q-pt-none stock-detail__picker-list">
                    <q-list separator>
                        <!-- Feedback 2026-08-21: no leading box glyph — every row
                             in a stock-item picker is a stock item, so the icon
                             said nothing and just indented the names. The action
                             is a link, not an addition: the green chain reads as
                             "tie this to that". -->
                        <q-item v-for="si in substituteCandidates" :key="si.stock_item_id" clickable @click="onAddSubstitute(si.stock_item_id)">
                            <q-item-section>{{ si.name }}</q-item-section>
                            <q-item-section side>
                                <BaseButton
                                    variant="icon"
                                    :icon="ICONS.add_link"
                                    color="positive"
                                    :aria-label="`Link ${si.name} as a substitute`"
                                >
                                    <BaseTooltip>Link as a substitute</BaseTooltip>
                                </BaseButton>
                            </q-item-section>
                        </q-item>
                        <q-item v-if="substituteCandidates.length === 0">
                            <q-item-section class="dora-text-muted">No matching items.</q-item-section>
                        </q-item>
                    </q-list>
                </q-card-section>
        </BaseDialog>

        <NutritionFoodPicker
            v-if="nutritionIsComplex && detail"
            v-model="foodPickerOpen"
            :item-name="detail.name"
            @picked="onFoodPicked"
        />
    </component>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import { formatDate, formatDateTime as formatLocaleDateTime } from 'src/composables/useDateFormat';
    import SearchInput from 'src/components/SearchInput.vue';
    import AppSkeleton from 'src/components/AppSkeleton.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import BaseDropdown from 'src/components/BaseDropdown.vue';
    import BuyVerdictCard from 'src/components/stock/BuyVerdictCard.vue';
    import HelpHint from 'src/components/help/HelpHint.vue';
    import StockLevelDot from 'src/components/stock/StockLevelDot.vue';
    import BlockedByRecipesDialog from 'src/components/stock/BlockedByRecipesDialog.vue';
    import PantryBeliefCard from 'src/components/stock/PantryBeliefCard.vue';
    import { usePantryBeliefs } from 'src/composables/usePantryBeliefs';
    import PlannedDemandCard from 'src/components/stock/PlannedDemandCard.vue';
    import { usePlannedDemand } from 'src/composables/usePlannedDemand';
    import { formatMoney } from 'src/composables/useMoney';
    import SubstituteMetadataDialog from 'src/components/stock/SubstituteMetadataDialog.vue';
    import DoraTabs, { type DoraTab } from 'src/components/DoraTabs.vue';
    import FadeTransition from 'src/components/transitions/FadeTransition.vue';
    import { storeToRefs } from 'pinia';
    import { QPage, useQuasar } from 'quasar';
    import AddToListButton from 'src/components/AddToListButton.vue';
    import DiscountChip from 'src/components/chips/DiscountChip.vue';
    import StoreLogo from 'src/components/StoreLogo.vue';
    import NutritionFoodPicker from 'src/components/stock/NutritionFoodPicker.vue';
    import NutritionFactsList from 'src/components/stock/NutritionFactsList.vue';
    import { useNutritionMode } from 'src/composables/useNutritionMode';
    import RecipeCard from 'src/components/RecipeCard.vue';
    import TrendSparkline from 'src/components/TrendSparkline.vue';
    import YourPricesWidget from 'src/components/dora/YourPricesWidget.vue';
    import { formatSubstituteRatio } from 'src/helpers/substituteRatio';
    import { relativeTime } from 'src/helpers/relativeTime';
    import { humaniseWasteReason } from 'src/helpers/wasteReasons';
    import { useBuyVerdict } from 'src/composables/useBuyVerdict';
    import { useBuyVerdictActions } from 'src/composables/useBuyVerdictActions';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { useScanningEnabled } from 'src/composables/useScanningEnabled';
    import { openProductSearch } from 'src/composables/useProductSearchUrl';
    import { describeQrFailure, fetchQrImageUrlAsync, openQrSheetAsync } from 'src/composables/useQrLabels';
    import { useShoppingListActions } from 'src/composables/useShoppingListActions';
    import { useStockItemActions } from 'src/composables/useStockItemActions';
    import { useUnsavedChangesGuard } from 'src/composables/useUnsavedChangesGuard';
    import { expiryIndicatorFor } from 'src/helpers/expiryIndicator';
    import { useStockGroupStore } from 'src/stores/stockGroupStore';
    import type { Recipe } from 'src/models/recipe';
    import type { LinkedProduct, PreferredBuy, PriceObservation, StockItemDetail, Substitute } from 'src/models/stockItemDetail';
    import { LOW_STOCK_SEQUENCE } from 'src/helpers/stockStatus';
    import { formatQuantity } from 'src/helpers/formatQuantity';
    import PriceHistoryApiService from 'src/services/api/priceHistoryApiService';
    import { NormalisedApiError } from 'src/services/api/axiosHttpClient';
    import StockItemApiService from 'src/services/api/stockItemApiService';
    import BarcodeApiService from 'src/services/api/barcodeApiService';
    import { useRecipeStore } from 'src/stores/recipeStore';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { useLocationOptions } from 'src/composables/useLocationOptions';
    import { useLocationStore } from 'src/stores/locationStore';
    import { useStoresStore } from 'src/stores/storesStore';
    import { computed, onMounted, reactive, ref, watch } from 'vue';
    import { useRoute, useRouter } from 'vue-router';
    import { describeApiError, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { isOnSpecial } from 'src/helpers/offerLogic';
    import { useConfirm } from 'src/composables/useConfirm';

    const props = defineProps<{ idOverride?: string; embedded?: boolean }>();

    // FU-609 / R-036 — dual-host root. Routed under MainLayout it must root on
    // <q-page> for the layout height contract; embedded inside Stock Overview's
    // peek splitter it is NOT in a q-page-container, so <q-page> can't resolve a
    // layout — fall back to a plain <div> there. Document-scroll either way.
    const rootTag = computed(() => (props.embedded ? 'div' : QPage));

    // The server validates the scheme on write; this guards older rows so a
    // stored `javascript:` (or any non-web) URL never becomes a live link.
    function isWebLink(url: string | null | undefined): url is string {
        return !!url && /^https?:\/\//i.test(url.trim());
    }
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
    // Recipe photos on the "Recipes using this" cards follow the user's own
    // preference — this isn't the cookbook, so the cookbook's cards/compact
    // switch has no say here.
    // Phones drop the header buttons to icon-only so the name, QR and Delete
    // fit on one line (feedback 2026-08-16).
    const compactHeader = computed(() => $q.screen.lt.sm);

    const stockItemApi = new StockItemApiService();
    const barcodeApi = new BarcodeApiService();
    const stockGroupStore = useStockGroupStore();

    const stockItemStore = useStockItemStore();
    const stockLevelStore = useStockLevelStore();
    // inferred belief for this item (shared cache).
    const pantryBeliefs = usePantryBeliefs();
    const belief = computed(() =>
        detail.value ? pantryBeliefs.beliefFor(detail.value.stock_item_id) : null,
    );
    // What the upcoming plan wants of this item (shared cache, same shape).
    const plannedDemandCache = usePlannedDemand();
    const plannedDemand = computed(() =>
        detail.value ? plannedDemandCache.demandFor(detail.value.stock_item_id) : null,
    );
    const locationStore = useLocationStore();
    const recipeStore = useRecipeStore();
    const shoppingListStore = useShoppingListStore();

    const { stockItems } = storeToRefs(stockItemStore);
    const { recipes } = storeToRefs(recipeStore);

    const actions = useStockItemActions();
    const slActions = useShoppingListActions();
    // shared handlers for the BuyVerdictCard's mark_stocked +
    // remove_from_list actions. Same seams the row card uses.
    const verdictActions = useBuyVerdictActions();

    const stockItemId = computed(() => props.idOverride ?? (route.params.id as string));

    // buy-verdict oracle (row/line badges elsewhere; the full
    // card renders on the overview tab, per FU-437). The composable
    // fetches on mount, caches for 5 min, and yields a computed we can
    // v-if in the template.
    // 2026-08-21 feedback ("the verdicts don't update when switching between
    // items in desktop view"): this used to pass `stockItemId.value` — a
    // snapshot taken at setup. The id is NOT stable for the page's lifetime:
    // the Stock Overview peek swaps `idOverride` on a mounted instance, so the
    // card kept rendering the first item's verdict. Pass the ref itself and the
    // composable's own watcher re-fetches per id.
    const { verdict: buyVerdict, invalidate: buyVerdictInvalidate } =
        useBuyVerdict(stockItemId);

    const detail = ref<StockItemDetail | null>(null);
    const loading = ref(false);
    const loadError = ref<string | null>(null);
    const busy = ref(false);

    // ── QR labels (gated by the install-wide scanning flag) ──────────
    const { scanningEnabled } = useScanningEnabled();
    // when `products` is off the Products tab + per-product
    // surfaces disappear entirely; FU-182 owns the app-wide sweep, this
    // page just consumes the flag.
    // 2026-08-20 — install-wide stocktake switch; hides the per-item mute
    // toggle when the household doesn't use stocktake at all.
    const { products: productsEnabled, stocktake: stocktakeEnabled } = useFeatureFlags();
    const { moneyEnabled } = useMoneyEnabled();
    // Only complex mode gives stock items a food to link; simple mode's kcal
    // is typed on the recipe, so the row is hidden entirely below that (R-029).
    const { isComplex: nutritionIsComplex } = useNutritionMode();
    const foodPickerOpen = ref(false);
    // The full per-100g table is behind a disclosure so it can't bury the
    // sections under it (feedback 2026-08-16).
    const nutritionExpanded = ref(false);
    // The QR PNG and the print sheet are fetched through the authenticated
    // http client and handed to the browser as blobs (see useQrLabels). The
    // previous `<img :src="apiUrl">` / `window.open(apiUrl)` pair relied on
    // the browser volunteering the session cookie on an unauthenticated
    // request, which is why the code rendered empty and "Print one" died.
    const qrSrc = ref<string | null>(null);
    const qrLoading = ref(false);
    const qrError = ref<string | null>(null);

    // Feedback 2026-08-24: the code renders inside the Scanning tab rather than
    // behind a header button + modal, so the fetch is keyed to that tab opening.
    // Still lazy — most visits to this page never open Scanning, and this is a
    // network round-trip per item.
    // Bumped on every fetch and on an id swap (peek panel), so a response for
    // the previous item can't land under the new one.
    let qrRequest = 0;
    async function ensureQrLoadedAsync() {
        if (qrSrc.value || qrLoading.value) return;
        const token = ++qrRequest;
        qrLoading.value = true;
        qrError.value = null;
        try {
            // size 512 looks crisp on retina; the box clamps to 256.
            const src = await fetchQrImageUrlAsync(stockItemId.value, 512);
            if (token === qrRequest) qrSrc.value = src;
        } catch (error) {
            // The reason, not just the fact. This used to be a bare sentence
            // with the error discarded, which is why the reported failure
            // (FU-648) survived two investigations unexplained — there was
            // nothing for the one person who could see it to report back.
            if (token === qrRequest) qrError.value = describeQrFailure(error);
        } finally {
            if (token === qrRequest) qrLoading.value = false;
        }
    }

    // "Print" opens a tab, so it must stay synchronous into
    // `openQrSheetAsync` — see the pop-up note there. Failures used to be
    // dropped on the floor by a bare `void`; they now land in the tab's own
    // error slot, next to the button that caused them.
    async function openSingleQrSheet() {
        qrError.value = null;
        try {
            await openQrSheetAsync({ ids: [stockItemId.value] });
        } catch (error) {
            qrError.value = describeQrFailure(error);
        }
    }

    const tab = ref<string>(
        typeof route.query.section === 'string' ? route.query.section : 'overview',
    );
    // Dora's "Find substitutes" pushes `?section=substitutes` onto this same
    // page, which reuses the component — follow the query after mount too.
    const TAB_NAMES = ['overview', 'products', 'recipes', 'substitutes', 'scanning', 'lists', 'history'];
    watch(
        () => route.query.section,
        (section) => {
            if (typeof section === 'string' && TAB_NAMES.includes(section)) tab.value = section;
        },
    );
    // if the URL pointed at ?section=products but products
    // is off (or the admin flips it off later), fall back to Overview so
    // we don't strand the user on an invisible tab.
    watch(
        [productsEnabled, tab],
        ([enabled, current]) => {
            if (!enabled && current === 'products') tab.value = 'overview';
        },
        { immediate: true },
    );
    // Same guard for the Scanning tab, which is gated on the scanning flag.
    watch(
        [scanningEnabled, tab],
        ([enabled, current]) => {
            if (!enabled && current === 'scanning') tab.value = 'overview';
        },
        { immediate: true },
    );
    // Opening Scanning is what fetches the QR label — see `ensureQrLoadedAsync`.
    watch(tab, (current) => {
        if (current === 'scanning') void ensureQrLoadedAsync();
    }, { immediate: true });

    // Full-path, searchable location options, like every location picker.
    const { locationOptions, filterLocations } = useLocationOptions(() => locationStore.tree);

    // ── Inline-edit state (C-1b.1) ──────────────────────────────────────
    // Text rows (name/notes) live in `form` and save on blur if changed;
    // toggles/selects/dates save immediately on change (see handlers
    // below). The Save/Reset coupling from the old 2-col form is gone —
    // each row IS its editor.
    type BasicsForm = {
        name: string;
        notes: string;
        stock_location_id: string | null;
        stock_group_id: string | null;
        usual_store_id: string | null;
    };
    const emptyBasics = (): BasicsForm => ({
        name: '', notes: '', stock_location_id: null, stock_group_id: null,
        usual_store_id: null,
    });
    const form = reactive<BasicsForm>(emptyBasics());

    /** `keepDrafts` holds an unsaved name / notes edit across a reload of the
     *  same item (a toggle saved elsewhere on the page reloads the detail). */
    function hydrateForm(d: StockItemDetail, keepDrafts = false) {
        if (!keepDrafts) {
            form.name = d.name;
            form.notes = d.notes ?? '';
        }
        form.stock_location_id = d.stock_location_id;
        form.stock_group_id = d.stock_group_id;
        form.usual_store_id = d.usual_store_id;
    }
    // The unsaved-changes guard now only covers text rows — selects/toggles/
    // dates persist on change, so they can never be "dirty but not saved."
    const isDirty = computed(() => {
        if (!detail.value) return false;
        return (
            form.name.trim() !== detail.value.name ||
            (form.notes ?? '') !== (detail.value.notes ?? '')
        );
    });
    // R-020 — deferred-save surface, must wire the unsaved-changes guard.
    useUnsavedChangesGuard(isDirty);

    // Stock groups — loaded once for the inline picker. (Owned locally
    // rather than via a store; this is the only consumer on this page
    // and the list is small.)
    const groupOptions = computed(() =>
        stockGroupStore.stockGroups.map((g) => ({ label: g.name, value: g.stock_group_id })),
    );

    // Stores picker. Hydrate lazily via R-016 ensureLoadedAsync; the
    // store dropdown shows whatever the user has curated under Settings →
    // Stores. Empty list ⇒ the picker reads "no stores set up yet" and the
    // user is invited to add some.
    const storesStore = useStoresStore();
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
    // Each row's editor calls one of these; the partial PATCH already
    // supports per-field updates so we don't need a Save button. Reloads
    // detail to pick up any server-derived state changes (e.g. auto-add
    // hook firing when level transitions).
    type FieldPatch = {
        name?: string;
        notes?: string | null;
        stock_location_id?: string | null;
        stock_group_id?: string | null;
        is_essential?: boolean;
        stocktake_alerts_are_enabled?: boolean;
        expiry_date?: string | null;
        usual_store_id?: string | null;
        clear_usual_store?: boolean;
        // Explicit clear flags — see `update_stock_item.py` for why the
        // relationship-only null assignment doesn't dirty the FK column.
        clear_stock_location?: boolean;
        clear_stock_group?: boolean;
        // Nutrition complex-mode link, same clear-vs-unset shape as the store.
        nutrition_food_id?: string;
        clear_nutrition_food?: boolean;
        // "Never suggest a food for this one." A plain bool, not a clear flag —
        // unlike the FK there's no difference between false and absent.
        nutrition_ignored?: boolean;
    };
    async function saveField(patch: FieldPatch) {
        if (!detail.value) return;
        busy.value = true;
        try {
            await stockItemStore.updateStockItemAsync({
                stock_item_id: detail.value.stock_item_id,
                ...patch,
            });
            await loadDetail();
        } catch (err) {
            notifyErr('Save failed.', err);
        } finally {
            busy.value = false;
        }
    }
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

    // ── Toolbar actions ──────────────────────────────────────────────────
    async function withBusyReload(fn: () => Promise<void>) {
        busy.value = true;
        try {
            await fn();
            await loadDetail();
        } finally {
            busy.value = false;
        }
    }

    // ── Preferred buys (FU-211) — free-text "what I actually buy" reminders.
    // Separate from the Product overlay; always available. Mutations reuse
    // withBusyReload so the list reflects the server after each change. The
    // server sends them A–Z (R-003: it owns the order).
    const preferredBuys = computed(() => detail.value?.preferred_buys ?? []);
    const newBuyLabel = ref('');
    const editingBuyId = ref<string | null>(null);
    const editingBuyLabel = ref('');

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
    // the shared PriceEntry component. This page just exposes the list (with
    // delete) and a submit handler that talks to the API. R-003: server
    // derives per-unit cost; we never divide here.
    const priceObservations = computed(() => detail.value?.price_observations ?? []);

    // Stores list for the optional store picker in PriceEntry (A2). Reuses
    // the existing `storesStore` instance declared above (FU-189 — usual
    // store picker). Lazy-hydration triggered earlier on this page.
    const storesList = computed(() => storesStore.stores);

    async function addObservation(value: {
        total_price: number;
        total_measure: number;
        unit: string;
        store_id: string | null;
        pack_count: number | null;
    }, done: () => void) {
        await withBusyReload(() => stockItemApi.addPriceObservationAsync(stockItemId.value, {
            total_price: value.total_price,
            total_measure: value.total_measure,
            unit: value.unit,
            store_id: value.store_id ?? null,
            pack_count: value.pack_count ?? null,
        }));
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

    async function deleteObservation(obs: PriceObservation) {
        await withBusyReload(() =>
            stockItemApi.deletePriceObservationAsync(stockItemId.value, obs.observation_id),
        );
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
    async function onAddToList() {
        await withBusyReload(async () => { await actions.addToList(stockItemId.value); });
        // the verdict's stock-band + open-list state both
        // changed. Invalidate so a re-render fetches a fresh answer.
        buyVerdictInvalidate();
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

    // ── Linked products ──────────────────────────────────────────────────
    const priceHistory = ref<Map<string, number[]>>(new Map());
    const priceSeriesApi = new PriceHistoryApiService();
    const PRICE_SERIES_BATCH = 5;

    // `discountPct` moved into `DiscountChip` (FU-885) — it was one of four
    // copies of the same rule, rendered three different ways.

    // Cheapest first, then by name.
    const sortedProducts = computed(() =>
        [...(detail.value?.products ?? [])].sort((a, b) => {
            const priceDiff = (a.price_now ?? Infinity) - (b.price_now ?? Infinity);
            if (priceDiff !== 0) return priceDiff;
            return a.name.localeCompare(b.name);
        }),
    );
    const cheapestProduct = computed<LinkedProduct | null>(() => {
        const withPrice = (detail.value?.products ?? []).filter((p) => p.price_now != null);
        if (withPrice.length === 0) return null;
        return withPrice.reduce((min, p) => (p.price_now! < min.price_now! ? p : min));
    });

    /** Sparkline series for the linked products, from the batched
     *  `/price-history` read (it takes up to five products a call). */
    async function loadPriceHistories(products: LinkedProduct[]) {
        const ids = products.map((p) => p.product_id);
        const batches: string[][] = [];
        for (let i = 0; i < ids.length; i += PRICE_SERIES_BATCH) batches.push(ids.slice(i, i + PRICE_SERIES_BATCH));
        const map = new Map<string, number[]>();
        await Promise.all(batches.map(async (batch) => {
            try {
                const { series } = await priceSeriesApi.seriesAsync(batch, '90d');
                for (const s of series) {
                    map.set(s.product_id, s.points.map((pt) => pt.unit_price ?? 0).filter((n) => n > 0));
                }
            } catch {
                // Sparklines just render empty if history can't be loaded.
            }
        }));
        priceHistory.value = map;
    }

    // the cheapest product gets a chip + highlight
    // style rather than a separate "Add cheapest" button — each product
    // carries its own Add-to-list.
    function isCheapest(p: LinkedProduct): boolean {
        return cheapestProduct.value?.product_id === p.product_id;
    }

    // Find-deals now lives only inside the Products tab (empty-state CTA +
    // "Link another" when products exist). FU-186 retired the in-app
    // `/product-search` route; both entry points now open the external
    // Product Search companion (or the Features setup page when unset).
    function onFindAndLink() {
        openProductSearch(router);
    }

    // `onAddProductToList` removed 2026-09-06 — `AddToListButton` owns this
    // flow now (MP-6 / L196).

    // ── Recipes ──────────────────────────────────────────────────────────
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
    const subPickerOpen = ref(false);
    const subSearch = ref('');
    const substituteCandidates = computed(() => {
        const existing = new Set((detail.value?.substitutes ?? []).map((s) => s.stock_item_id));
        const q = subSearch.value.trim().toLowerCase();
        return stockItems.value
            .filter(
                (si) =>
                    si.stock_item_id !== stockItemId.value &&
                    !existing.has(si.stock_item_id) &&
                    (!q || si.name.toLowerCase().includes(q)),
            )
            .slice(0, 30);
    });
    function openSubstitutePicker() {
        subSearch.value = '';
        subPickerOpen.value = true;
    }
    async function onAddSubstitute(substituteId: string) {
        subPickerOpen.value = false;
        await withBusyReload(() => stockItemApi.addSubstituteAsync(stockItemId.value, substituteId));
    }
    async function onRemoveSubstitute(substituteId: string) {
        await withBusyReload(() => stockItemApi.removeSubstituteAsync(stockItemId.value, substituteId));
    }

    // ── FU-034: substitute metadata edit dialog ─────────────────────────
    const substituteMetadataOpen = ref(false);
    const substituteMetadataSaving = ref(false);
    const editingSubstitute = ref<Substitute | null>(null);

    function onEditSubstituteMetadata(sub: Substitute) {
        editingSubstitute.value = sub;
        substituteMetadataOpen.value = true;
    }
    async function onSaveSubstituteMetadata(payload: {
        notes: string | null;
        ratio_quantity_in: number | null;
        ratio_unit_in: string | null;
        ratio_quantity_out: number | null;
        ratio_unit_out: string | null;
    }) {
        const sub = editingSubstitute.value;
        if (!sub) return;
        substituteMetadataSaving.value = true;
        try {
            await withBusyReload(() =>
                stockItemApi.updateSubstituteAsync(
                    stockItemId.value,
                    sub.stock_item_id,
                    payload,
                ),
            );
            substituteMetadataOpen.value = false;
            editingSubstitute.value = null;
        } finally {
            substituteMetadataSaving.value = false;
        }
    }

    // ── FU-056: barcode add / remove ────────────────────────────────────
    const addBarcodeOpen = ref(false);
    const addBarcodeValue = ref('');
    const addBarcodeError = ref<string | null>(null);
    const addBarcodeSaving = ref(false);

    function onAddBarcodeClick() {
        addBarcodeValue.value = '';
        addBarcodeError.value = null;
        addBarcodeOpen.value = true;
    }
    async function onConfirmAddBarcode() {
        const raw = addBarcodeValue.value.trim();
        if (!raw) return;
        addBarcodeError.value = null;
        addBarcodeSaving.value = true;
        try {
            await withBusyReload(() => barcodeApi.registerAsync({
                barcode: raw,
                stock_item_id: stockItemId.value,
            }).then(() => undefined));
            addBarcodeOpen.value = false;
            $q.notify({
                type: 'positive',
                message: 'Barcode added.',
            });
        } catch (err) {
            // 2026-08-21 feedback: pasting an EAN answered "endpoint was not
            // found", which reads as our bug in the barcode itself. It isn't a
            // validation failure at all — it's the API not carrying
            // POST /api/data/barcodes, which is registered in the same module
            // as the QR endpoint the owner also gets a 404 from. Both were
            // proven green over real HTTP on 2026-08-21 (including the exact
            // ISBN-13 he tried), so translate the route miss into the thing he
            // can act on instead of echoing the server's wording.
            addBarcodeError.value = describeBarcodeFailure(err);
        } finally {
            addBarcodeSaving.value = false;
        }
    }
    /** Route-miss 404s get named as such; everything else keeps the server's
     *  own message (already friendly — duplicates, blank values, …). */
    function describeBarcodeFailure(err: unknown): string {
        if (err instanceof NormalisedApiError && err.status === 404) {
            const detail = err.details as { title?: string } | null;
            const title = typeof detail?.title === 'string' ? detail.title : '';
            if (title.toLowerCase().startsWith('endpoint')) {
                return `This server has no barcode endpoint at ${err.url}. Update the Dora server.`;
            }
        }
        return describeApiError(err) || 'Could not add barcode.';
    }

    async function onRemoveBarcode(barcodeId: string) {
        try {
            await withBusyReload(() => barcodeApi.deleteAsync(barcodeId));
            $q.notify({
                type: 'positive',
                message: 'Barcode removed.',
            });
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not remove barcode.',
                caption: toastCaption(err),
            });
        }
    }
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

    // ── Lifecycle timeline (C-1b.5 / INV-7) ─────────────────────────────
    // Merge the per-kind event lists into one date-sorted timeline. Each
    // entry carries its own colour + icon so the user can scan an item's
    // purchase → use → waste → restock loop at a glance (P5).
    type LifecycleEvent = {
        id: string;
        at: string;
        title: string;
        body?: string;
        icon: string;
        color: string;
    };
    const lifecycleEvents = computed<LifecycleEvent[]>(() => {
        const d = detail.value;
        if (!d) return [];
        const out: LifecycleEvent[] = [];

        // Level history — newest level at top of `level_history` already.
        // Walk *forwards in time* (older→newer) so we can infer "restocked"
        // vs "dropped to X" by comparing to the previous level's sequence.
        const levels = [...d.level_history].sort(
            (a, b) => new Date(a.changed_at).getTime() - new Date(b.changed_at).getTime(),
        );
        for (let i = 0; i < levels.length; i++) {
            const cur = levels[i]!;
            const prev = i > 0 ? levels[i - 1] : null;
            const name = cur.stock_level_name ?? 'Level changed';
            let title = `Level → ${name}`;
            if (prev && prev.stock_level_sequence != null && cur.stock_level_sequence != null) {
                // A move from low/out to stocked reads as "restocked"; the
                // opposite as "dropped to X". Otherwise just the destination.
                const wasShort = prev.stock_level_sequence >= LOW_STOCK_SEQUENCE;
                const nowShort = cur.stock_level_sequence >= LOW_STOCK_SEQUENCE;
                if (wasShort && !nowShort) title = `Restocked → ${name}`;
                else if (!wasShort && nowShort) title = `Dropped to ${name}`;
            }
            out.push({
                id: `level-${cur.changed_at}-${i}`,
                at: cur.changed_at,
                title,
                icon: ICONS.refresh,
                color: 'primary',
            });
        }

        // Waste events. C-waste slim: reason-only — no quantity / value /
        // note. The timeline entry is a single line.
        for (const w of d.waste_events ?? []) {
            const reason = humaniseWasteReason(w.reason);
            out.push({
                id: `waste-${w.occurred_at}-${reason}`,
                at: w.occurred_at,
                title: `Wasted: ${reason}`,
                icon: ICONS.delete_outline,
                color: 'negative',
            });
        }

        // Past list-adds — which list, and when.
        for (const a of d.recent_list_adds ?? []) {
            out.push({
                id: `add-${a.added_at}-${a.shopping_list_id}`,
                at: a.added_at,
                title: `Added to ${a.shopping_list_name}`,
                icon: ICONS.shopping_cart,
                color: 'accent',
            });
        }

        // Purchase events (2026-06-30) — every ticked line on a
        // finished shopping list. Answers "when did I last actually
        // buy this and for how much?" — a question the list-add
        // entries can't. Price + store are both optional; render
        // whichever the /finish flow captured.
        for (const p of d.purchase_events ?? []) {
            const bits: string[] = [];
            if (p.quantity && p.quantity !== 1) bits.push(`${p.quantity}×`);
            if (p.actual_unit_price != null) {
                bits.push(`${formatMoney(p.actual_unit_price)}${p.quantity > 1 ? '/ea' : ''}`);
            }
            if (p.store_name) bits.push(`at ${p.store_name}`);
            const entry: LifecycleEvent = {
                id: `bought-${p.occurred_at}-${p.shopping_list_id}`,
                at: p.occurred_at,
                title: `Bought · ${p.shopping_list_name}`,
                icon: ICONS.shopping_bag,
                // was 'teal-8'; now theme-aware via --lifecycle-bought.
                color: 'lifecycle-bought',
            };
            if (bits.length > 0) entry.body = bits.join(' · ');
            out.push(entry);
        }

        // Cook events (2026-06-30) — every recipe you cooked that
        // uses this ingredient. `meals_cooked > 1` badges the entry
        // as a batch cook. Recipe id may be null (SET NULL on delete);
        // denormalised name still renders.
        for (const c of d.cook_events ?? []) {
            const badge = c.meals_cooked > 1 ? ` · ${c.meals_cooked} meals` : '';
            out.push({
                id: `cook-${c.occurred_at}-${c.recipe_id ?? 'unknown'}`,
                at: c.occurred_at,
                title: `Used in ${c.recipe_name}${badge}`,
                icon: ICONS.local_fire_department,
                // was 'deep-orange-6'; reuses the severity-high
                // token (same visual weight as the essential-low alert kind).
                color: 'severity-high',
            });
        }

        // Expiry events (2026-06-30) — set / pushed / cleared trail.
        // Repeat pushes tell the user "this is stale in your fridge".
        for (const e of d.expiry_events ?? []) {
            let title: string;
            let body: string | null = null;
            let color: string;
            // D-006 — install-locale dates, not raw ISO (finalisation 06-R2).
            const fmt = (iso: string | null) => (iso ? formatDate(iso) : '–');
            if (e.kind === 'cleared') {
                title = 'Cleared expiry';
                body = e.previous_expiry_date
                    ? `Was ${fmt(e.previous_expiry_date)}`
                    : null;
                // was 'grey-7'; theme-aware --lifecycle-cleared
                // (a muted neutral, distinct from severity-*). Cleared
                // is a "wound-down" state, not part of the severity ladder.
                color = 'lifecycle-cleared';
            } else if (e.kind === 'pushed') {
                const delta = e.delta_days ?? 0;
                title = delta >= 0 ? `Pushed expiry +${delta} day${delta === 1 ? '' : 's'}`
                                   : `Expiry moved ${delta} day${delta === -1 ? '' : 's'}`;
                body = `${fmt(e.previous_expiry_date)} → ${fmt(e.new_expiry_date)}`;
                // was 'orange-8'; theme-aware --lifecycle-expiry-changed.
                color = 'lifecycle-expiry-changed';
            } else {
                title = 'Set expiry';
                body = fmt(e.new_expiry_date);
                color = 'lifecycle-expiry-changed';
            }
            const entry: LifecycleEvent = {
                id: `expiry-${e.occurred_at}-${e.kind}`,
                at: e.occurred_at,
                title,
                icon: ICONS.event,
                color,
            };
            if (body) entry.body = body;
            out.push(entry);
        }

        // Synthetic "Opened" — single entry derived from current state.
        // opened_on is a date; widen to start-of-day for ordering.
        if (d.is_open && d.opened_on) {
            out.push({
                id: `opened-${d.opened_on}`,
                at: `${d.opened_on}T00:00:00`,
                title: 'Opened',
                icon: ICONS.lock_open,
                // was 'amber-9'; reuses the --severity-attention
                // token (same visual weight as the AddToList "on multiple
                // lists" hint — both grabby-but-not-urgent).
                color: 'severity-attention',
            });
        }

        // Synthetic "Checked" — only if last_checked_at differs from the
        // most recent level change (otherwise it's the same event).
        const lastLevelAt = levels.length > 0
            ? levels[levels.length - 1]!.changed_at
            : null;
        if (d.last_checked_at && d.last_checked_at !== lastLevelAt) {
            out.push({
                id: `checked-${d.last_checked_at}`,
                at: d.last_checked_at,
                title: 'Checked (still correct)',
                icon: ICONS.event,
                color: 'positive',
            });
        }

        // Sort newest first. Truncation is server-owned now (per-kind
        // cap in get_stock_item_detail.py, reported via
        // `history_older_count`); we render everything the server
        // sends and surface the drop count in the timeline footer.
        out.sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime());
        return out;
    });

    // ── Unlink products ──────────────────────────────────────────────────
    // The saved-products picker dialog was retired; the Find-&-link CTA
    // opens the external Product Search companion (FU-186), and products are
    // linked back from the My Products "Link to stock item…" dialog.
    async function onUnlink(productId: string) {
        await withBusyReload(() => stockItemApi.unlinkProductAsync(stockItemId.value, productId));
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
            else void router.push('/stock');
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

    // ── Helpers ──────────────────────────────────────────────────────────
    function notifyErr(message: string, err: unknown) {
        $q.notify({ type: 'negative', message, caption: toastCaption(err) });
    }
    // relativeTime extracted to src/helpers/relativeTime.ts (R-003) — see
    // imports at the top of the script block.

    function goBack() {
        if (window.history.length > 1) router.back();
        else void router.push('/stock');
    }

    async function loadDetail() {
        const id = stockItemId.value;
        loading.value = true;
        loadError.value = null;
        try {
            const d = await stockItemApi.getDetailAsync(id);
            // The peek panel can swap ids mid-flight — drop a stale response.
            if (id !== stockItemId.value) return;
            const keepDrafts = detail.value?.stock_item_id === d.stock_item_id && isDirty.value;
            detail.value = d;
            hydrateForm(d, keepDrafts);
            void loadPriceHistories(d.products);
            // List membership (the "on lists" tab) comes from the shopping-list
            // store, loaded on mount and refreshed by the list actions themselves.
        } catch (err) {
            if (id !== stockItemId.value) return;
            loadError.value = 'Could not load this stock item.';
            console.warn('stock-item detail load failed', err);
        } finally {
            if (id === stockItemId.value) loading.value = false;
        }
    }

    watch(stockItemId, (id) => {
        // Leaving the page empties the id; keep the old detail up through the
        // layout cross-fade rather than blanking it (R-037).
        if (!id) return;
        // The peek panel swaps ids in place — drop the previous item's detail
        // (so a failed load can't leave it on screen for saveField to patch)
        // and its cached QR, invalidating any in-flight QR fetch, then re-fetch
        // the label if it's the tab we're currently looking at.
        detail.value = null;
        qrRequest++;
        qrLoading.value = false;
        qrSrc.value = null;
        qrError.value = null;
        if (tab.value === 'scanning') void ensureQrLoadedAsync();
        if (stockItemId.value) void loadDetail();
    });

    // when the row's expiry / open / flag / level toggles fire
    // while this page is open as a peek, the store's StockItem updates
    // but `detail.value` (loaded as a one-shot) goes stale. Sync the
    // handful of fields the row can mutate from the store version onto
    // detail.value so the peek reflects external edits without a
    // refresh. The store always re-fetches the canonical row after a
    // mutation (stockItemStore.updateStockItemAsync /
    // updateStockLevelAsync), so the assignments here are authoritative.
    // Self-triggered edits on the detail page also flow through the
    // store, but the value already matches by the time the watcher
    // fires — the assignment is a no-op, not a loop.
    const storeItem = computed(() => stockItemStore.byId.get(stockItemId.value) ?? null);
    watch(storeItem, (si) => {
        if (!si || !detail.value || detail.value.stock_item_id !== si.stock_item_id) return;
        if (si.expiry_date !== undefined && si.expiry_date !== detail.value.expiry_date) {
            detail.value.expiry_date = si.expiry_date;
        }
        if (si.is_open !== undefined && si.is_open !== detail.value.is_open) {
            detail.value.is_open = si.is_open;
        }
        if (si.opened_on !== undefined && si.opened_on !== detail.value.opened_on) {
            detail.value.opened_on = si.opened_on;
        }
        if (si.is_essential !== undefined && si.is_essential !== detail.value.is_essential) {
            detail.value.is_essential = si.is_essential;
        }
        if (si.stock_level_id && si.stock_level_id !== detail.value.stock_level_id) {
            detail.value.stock_level_id = si.stock_level_id;
            detail.value.stock_level_name = stockLevelStore.levelById.get(si.stock_level_id)?.name ?? null;
        }
    });

    onMounted(async () => {
        // Stock groups are page-local (only consumer); load alongside the
        // other dropdowns so the inline picker has options on first paint.
        void stockGroupStore.ensureLoadedAsync();
        // populate the usual-store picker. R-016 ensureLoaded.
        void storesStore.ensureLoadedAsync();
        await Promise.all([
            stockLevelStore.ensureLoadedAsync(),
            locationStore.ensureLoadedAsync(),
            stockItemStore.ensureLoadedAsync(),
            recipeStore.ensureLoadedAsync(),
            shoppingListStore.ensureLoadedAsync(),
            // load inferred beliefs (shared cache; idempotent when
            // the overview already loaded them).
            pantryBeliefs.loadAsync(),
            plannedDemandCache.loadAsync(),
        ]);
        await loadDetail();
    });
</script>

<style scoped>
    .strike {
        text-decoration: line-through;
    }

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
    /* C-1b.3 — emphasise the cheapest linked product per §2.4 (style, not a
       separate "Add cheapest" button). Subtle outline + tinted background
       via the brand-primary token so it follows the active theme. */
    .dora-product-card--cheapest {
        border-color: var(--brand-primary) !important;
        background: color-mix(in srgb, var(--brand-primary) 8%, transparent);
    }

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

    /* Feedback 2026-08-08: recipe cards reflow by column count rather than
       stretching within a Quasar breakpoint grid. auto-fill keeps each card
       within a bounded width band and drops/adds a whole column on resize. */
    .stock-detail__sub-dot {
        min-width: 28px;
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
    .stock-detail__qr {
        width: 256px;
        height: 256px;
        max-width: 100%;
    }
    .stock-detail__empty-copy {
        max-width: 360px;
    }
    .stock-detail__picker-list {
        max-height: 60vh;
        overflow: auto;
    }
    .stock-detail__recipe-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
        gap: 16px;
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
        background: var(--surface-raised);
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
