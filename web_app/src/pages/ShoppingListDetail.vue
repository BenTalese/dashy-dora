<template>
    <q-page padding>
        <!-- UX-v2 layout: main column + (desktop) lists rail. The rail and
             the mobile dropdown render the same server-ordered continuum
             (effective date ascending — past at top, future at bottom). -->
        <div class="row no-wrap q-col-gutter-md">
            <div class="col" style="min-width: 0">
                <!-- The picker sits **above** the toolbar on a phone
                     (2026-09-17). The band below it acts on *this* list — add
                     an item to it, set its shop day, save it as a template —
                     so the control that chooses which list you are looking at
                     has to come first; underneath, it read as one more list
                     action. On a desktop the question is answered by the rail
                     on the right, which is why this block is `lt-md` only. -->
                <!-- Mobile list switcher (UX-v2 §3.2): same date-ordered
                     continuum as the desktop rail, as a dropdown at the top
                     of the page. It is now *only* a switcher — "New list" and
                     "Manage templates…" were bookended around this menu, which
                     is how both ended up hidden on the surface where they
                     matter most; both are toolbar buttons now.

                     Always rendered, including mid-shop. It used to vanish on
                     the run face and be replaced by a "Switch list" toolbar
                     button — the same capability wearing a different shape, in
                     a different place, at the one moment the user is least able
                     to go hunting for it. On mobile this dropdown is also the
                     only place the list's name appears (the page title is
                     desktop-only), so renaming lives here too — as part of the
                     same control rather than a loose icon next to it
                     (2026-09-17: *"the button element itself looks a bit meh
                     and the edit pencil button doesn't feel like it belongs to
                     it"*). One bordered field, the name reading from the left
                     where a value belongs, the pencil a segment inside the
                     same edge.

                     "New list" came back into this menu on 2026-08-29 — but as
                     a pinned first entry, not the bookend it used to be. The
                     2026-08-26 removal was right that it was hidden here; what
                     it got wrong was moving it next to "Add item", where the
                     two reads as two ways to do one thing. This is the list of
                     lists, so this is where you make one. -->
                <div class="lt-md sld-picker q-mb-md">
                    <BaseDropdown
                        class="col sld-picker__pick"
                        flat
                        align="left"
                        :icon="pickerIcon"
                        :label="pickerLabel"
                    >
                        <!-- Not `dense`, for the same reason as the "Older
                             lists" dialog: these are the rail's rows. -->
                        <q-list class="scroll" style="max-height: 60vh">
                            <q-item clickable v-close-popup class="sld-picker-new" @click="newListOpen = true">
                                <q-item-section avatar>
                                    <q-icon :name="ICONS.add" color="primary" />
                                </q-item-section>
                                <q-item-section class="text-primary text-weight-medium">
                                    New list
                                </q-item-section>
                            </q-item>
                            <q-separator />
                            <ShoppingListRailItem
                                v-for="s in railEntries"
                                :key="s.shopping_list_id"
                                :summary="s"
                                :active="s.shopping_list_id === listId"
                                v-close-popup
                                @select="switchToList(s.shopping_list_id)"
                            />
                            <q-item
                                v-if="olderDoneSummaries.length > 0"
                                clickable
                                v-close-popup
                                @click="openOlderLists"
                            >
                                <q-item-section avatar>
                                    <q-icon :name="ICONS.history" />
                                </q-item-section>
                                <q-item-section>
                                    See older ({{ olderDoneSummaries.length }})
                                </q-item-section>
                            </q-item>
                        </q-list>
                    </BaseDropdown>
                    <!-- Draft-only, same rule as the card's pencil: naming a
                         list is part of writing it, not part of shopping it or
                         of reading the receipt afterwards. -->
                    <BaseButton
                        v-if="planFace"
                        variant="icon"
                        class="sld-picker__rename"
                        :icon="ICONS.edit"
                        aria-label="Rename list"
                        @click="startNameEdit"
                    >
                        <BaseTooltip>Rename</BaseTooltip>
                    </BaseButton>
                </div>

                <!-- Toolbar. 2026-08-26 feedback rebuilt this to the Stock
                     overview shape, because "consistency is important" and
                     these two pages are the app's two list surfaces:

                     - **No page title.** "Shopping lists" was a heading that
                       told you nothing you couldn't see from the nav, sitting
                       directly above the list's *actual* name.
                     - **No "More" ellipsis.** Every action is on the band; the
                       band scrolls sideways rather than wrapping or hiding
                       behind a menu (same rule as `.stock-toolbar__actions`
                       and `FilterRow`). The one surviving menu is Export, and
                       that groups variants of a single action rather than
                       acting as a catch-all.
                     - **Labels drop on phones**, tooltips carry the name
                       (`compactToolbar`), so the row doesn't eat the viewport.
                     - **Templates is here**, not buried at the bottom of the
                       rail behind an ellipsised "Manage templates…" link.

                     Destructive actions (Clear all items, Delete list)
                     deliberately did NOT come with them — they live in a
                     footer under the list, past everything they'd destroy.

                     2026-08-29 feedback rebalanced what belongs here at all:

                     - **New list left** for the lists picker (rail + mobile
                       dropdown). Sitting next to "Add item" it read as a second
                       way to add *to this list*; the two verbs are one word
                       apart and act on different things.
                     - **Add item inherits the primary styling** New list
                       vacated — on this page it is the add.
                     - **Set shop day arrived**, out of the header meta row,
                       where a control and a fact were sharing one slot.
                     - **Export split** into its two members. It was a menu
                       wrapping exactly two items, i.e. one extra tap to reach
                       either of them.
                     - **The four lifecycle buttons left** for the overview
                       card. They occupied one mutually-exclusive slot here and
                       are the one action each face exists for, so they belong
                       with the face's own summary, not in a band of utilities. -->
                <div class="row items-center q-gutter-sm sld-toolbar">
                    <div class="row items-center no-wrap sld-toolbar__actions">
                        <BaseButton
                            variant="primary"
                            :icon="ICONS.add_shopping_cart"
                            :label="compactToolbar ? undefined : 'Add item'"
                            aria-label="Add item"
                            :disable="!detail || detail.status === 'done'"
                            @click="onOpenQuickAdd"
                        >
                            <BaseTooltip>Search every stock item and drop it onto this list</BaseTooltip>
                        </BaseButton>
                        <!-- Draft only. Once you are standing in the shop the
                             day it was planned for is a fact, not a decision —
                             the overview card still reports it. -->
                        <BaseButton
                            v-if="planFace"
                            variant="secondary"
                            :icon="ICONS.event"
                            :label="compactToolbar ? undefined : 'Shop day'"
                            aria-label="Set shop day"
                        >
                            <!-- Hidden while the calendar is open: the cursor is
                                 still on the button, so the tip would sit over
                                 the calendar's own title. -->
                            <BaseTooltip v-if="!plannedDateOpen">
                                Set the day you plan to shop this list. Helps Dora pick
                                which list is your active one, and drives shop-day reminders.
                            </BaseTooltip>
                            <!-- Owner feedback 2026-10-17: "the plan this shop for
                                 modal slows the process down — just make the
                                 calendar appear immediately". The calendar now
                                 hangs straight off the button (q-popup-proxy: a
                                 menu on desktop, a dialog on phones), and picking a
                                 day commits it — the same pick-to-save shape as the
                                 stock row's expiry popup. Clear lives inside the
                                 calendar so un-planning is one tap too. -->
                            <q-popup-proxy
                                v-model="plannedDateOpen"
                                transition-show="scale"
                                transition-hide="scale"
                            >
                                <q-date
                                    :model-value="detail?.planned_shop_date ?? null"
                                    mask="YYYY-MM-DD"
                                    title="Shop day"
                                    @update:model-value="onPickPlannedDate"
                                >
                                    <div class="row items-center justify-end q-gutter-sm">
                                        <BaseButton
                                            v-if="detail?.planned_shop_date"
                                            variant="danger-ghost"
                                            label="Clear"
                                            @click="clearPlannedDate"
                                        />
                                        <BaseButton variant="ghost" label="Cancel" v-close-popup />
                                    </div>
                                </q-date>
                            </q-popup-proxy>
                        </BaseButton>
                        <!-- Bulk select is gone. Of its four actions, Tick and
                             Untick went with draft ticking, and "Move to list"
                             was only ever needed for leftovers — which the
                             finish dialog now demands a decision on. That left
                             a mode whose whole cost was paid for one action
                             available in a better place. -->
                        <!-- Shop mode only. This is for the price you notice on
                             the shelf for something that *isn't* on the list —
                             the per-line price capture already covers everything
                             that is. Same `useLogPrice()` sheet Stock overview
                             and the dashboard open, so there is one flow rather
                             than a third (R-003). Money-gated, like every other
                             price surface on this page. -->
                        <BaseButton
                            v-if="runFace && moneyEnabled"
                            variant="secondary"
                            :icon="ICONS.cash_plus"
                            :label="compactToolbar ? undefined : 'Log price'"
                            aria-label="Log a price"
                            @click="openLogPrice()"
                        >
                            <BaseTooltip>
                                Record a price you spotted for something that isn't on
                                this list
                            </BaseTooltip>
                        </BaseButton>
                        <BaseButton
                            variant="secondary"
                            :icon="ICONS.bookmarks"
                            :label="compactToolbar ? undefined : 'Templates'"
                            aria-label="Manage templates"
                            to="/shopping-lists/templates"
                        >
                            <BaseTooltip>Reusable lists you can start a shop from</BaseTooltip>
                        </BaseButton>
                        <!-- "Refresh deals" was here, products-gated, until
                             2026-09-17. It never fetched anything: it
                             re-validated each line's stored offer selection
                             and cleared the dead ones. But the detail read
                             resolves every line's offer from the *currently
                             linked* products and falls back to the cheapest,
                             so an active list already shows current deals and
                             this button changed nothing a user could see —
                             while its name promised a scrape. The bookkeeping
                             it did now happens when the link is actually
                             broken (`unlink_product_from_stock_item`), which
                             needs nobody to press anything. -->
                        <BaseButton
                            variant="secondary"
                            :icon="ICONS.print"
                            :label="compactToolbar ? undefined : 'Print'"
                            aria-label="Print or save as PDF"
                            :disable="!detail || detail.lines.length === 0"
                            @click="onPrint"
                        >
                            <BaseTooltip>Print or save as PDF</BaseTooltip>
                        </BaseButton>
                        <BaseButton
                            variant="secondary"
                            :icon="ICONS.bookmark_add"
                            :label="compactToolbar ? undefined : 'Save as template'"
                            aria-label="Save as template"
                            :disable="!detail || detail.lines.length === 0"
                            @click="onSaveAsTemplate"
                        >
                            <BaseTooltip>Keep these items as a reusable snapshot</BaseTooltip>
                        </BaseButton>
                    </div>
                </div>

                <q-banner v-if="loadError" class="text-negative q-mb-4 sl-panel sl-panel--error" dense>
                    <strong>Couldn't load this list.</strong>
                    {{ loadError }}
                    <template #action>
                        <BaseButton variant="ghost" label="Retry" @click="load" />
                    </template>
                </q-banner>

                <FadeTransition mode="out-in">
                <div v-if="loading && !detail" key="sld-loading">
                    <!-- Skeleton mirrors the info area + a few rows. `loading`
                         starts true so this branch (never the empty-state
                         fallback) is the first frame — kills the
                         flash-of-"no lists" (S6). -->
                    <div class="q-mb-lg">
                        <AppSkeleton type="line" width="240px" height="2rem" />
                        <AppSkeleton type="line" width="60%" height="1rem" class="q-mt-sm" />
                    </div>
                    <div v-for="n in 5" :key="n" class="row items-center q-gutter-sm q-py-sm">
                        <AppSkeleton type="circle" width="24px" height="24px" />
                        <AppSkeleton type="line" width="40%" height="1rem" />
                        <q-space />
                        <AppSkeleton type="line" width="64px" height="1rem" />
                    </div>
                </div>

                <div v-else-if="detail" key="sld-content">
                    <!-- The overview card (UX-v3). One card on every face,
                         replacing five stacked blocks: a header cluster, a trip
                         card, a store card, an "Order by" bar and — mid-shop —
                         a sticky footer that repeated the money and the primary
                         action. It owns the name, the status, the figure, the
                         shop day, the sort control and the face's primary
                         action; everything you'd only ask once is behind its
                         caret. See the component for the reasoning. -->
                    <ShoppingListOverviewCard
                        :detail="detail"
                        :lines="baseLines"
                        :mode="groupBy"
                        :amending="amending"
                        :starting="togglingProgress"
                        :finishing="finishing"
                        @rename="startNameEdit"
                        @update:mode="groupBy = $event"
                        @update:amending="amending = $event"
                        @start-shopping="onStartShopping"
                        @back-to-draft="onBackToDraft"
                        @finish="openFinishReview"
                        @put-away="putAwayOpen = true"
                    />


                    <!-- Budget-aware trim banner (money-gated + budget-set).
                         Fires when the projected active-list total exceeds the
                         user's period-remaining budget for this list's shop
                         date. Never mutates on load; every mutation is a user
                         tap. -->
                    <q-banner
                        v-if="planFace && trimBanner.visible"
                        class="q-mb-4 sl-panel sl-panel--warn"
                        dense
                    >
                        <template #avatar>
                            <q-icon :name="ICONS.savings" color="warning" />
                        </template>
                        <div v-if="trimBanner.state === 'applied'" class="text-body2">
                            Trimmed
                            <strong>{{ fmtMoney(trimBanner.savedApplied) }}</strong>
                            to fit.
                            <a
                                href="#deferred-by-budget"
                                class="text-primary"
                                @click.prevent="scrollToDeferred"
                            >
                                see deferred ({{ deferredLines.length }})
                            </a>
                        </div>
                        <div v-else class="text-body2">
                            <strong>
                                Projected {{ fmtMoney(trimBanner.projectedTotal) }} ·
                                budget remaining {{ fmtMoney(trimBanner.budgetTarget) }}
                            </strong>.
                            Trim
                            <strong>{{ fmtMoney(trimBanner.overshoot) }}</strong>
                            to fit.
                            <div
                                v-if="trimBanner.state === 'previewed' && trimBanner.stillOver > 0"
                                class="text-caption text-negative q-mt-xs"
                            >
                                Trimmed everything safe. Still
                                {{ fmtMoney(trimBanner.stillOver) }} over.
                            </div>
                        </div>
                        <template #action>
                            <BaseButton
                                v-if="trimBanner.state === 'idle'"
                                variant="ghost"
                                label="Show what would be cut"
                                :loading="trimBanner.busy"
                                @click="previewTrim"
                            />
                            <BaseButton
                                v-if="trimBanner.state !== 'applied' && trimBanner.canApply"
                                :label="trimBanner.state === 'previewed' ? 'Apply trim' : 'Trim to fit'"
                                :loading="trimBanner.busy"
                                @click="applyTrim"
                            />
                            <BaseButton
                                v-if="trimBanner.state !== 'applied'"
                                variant="ghost"
                                label="Dismiss"
                                @click="dismissTrim"
                            />
                        </template>
                    </q-banner>

                    <!-- Preview: which lines would go, each with a "Keep" opt-out. -->
                    <q-card
                        v-if="planFace && trimBanner.state === 'previewed' && trimBanner.previewLines.length > 0"
                        flat
                        class="q-mb-4 sl-panel"
                    >
                        <q-card-section class="q-py-sm">
                            <div class="text-caption dora-text-muted q-mb-xs">
                                Would trim {{ trimBanner.previewLines.length }} line{{ trimBanner.previewLines.length === 1 ? '' : 's' }}
                            </div>
                            <!-- Same shape as the deferred rows below, and for
                                 the same reason: a reason chip is a sentence,
                                 and `q-item-section side` will not wrap for
                                 it. -->
                            <div
                                v-for="p in trimBanner.previewLines"
                                :key="p.line_id"
                                class="sld-deferred-row"
                            >
                                <div class="sld-deferred-row__main">
                                    <div>{{ p.name }}</div>
                                    <div class="text-caption dora-text-muted">
                                        <span class="sld-deferred-reason">{{ p.reason_chip }}</span>
                                        {{ fmtMoney(p.saved) }} saved
                                    </div>
                                </div>
                                <BaseButton
                                    variant="subtle"
                                    label="Keep"
                                    class="sld-deferred-row__action"
                                    @click="keepFromTrim(p.line_id)"
                                />
                            </div>
                        </q-card-section>
                    </q-card>

                    <!-- FU-653 — Dora's suggestions, above the list and
                         visibly not part of it: chips you may tap to add,
                         never lines that appeared on their own. Empty (and so
                         absent) unless the user opted the shopping surface in.

                         No dismiss (2026-09-17). The strip only exists because
                         the household turned inference on for this surface, so
                         a cross was a control for half-undoing a preference
                         they set on purpose — and one that forgot by the next
                         visit, since the hide was session-only. The switch in
                         Settings is the real control; this is the feature
                         doing what it was asked to do.
                    -->
                    <q-card
                        v-if="planFace && visibleSuggestions.length > 0"
                        flat
                        class="q-mb-5 inferred-suggestions sl-panel"
                    >
                        <q-card-section class="q-pb-xs row items-center no-wrap q-gutter-xs">
                            <q-icon :name="ICONS.dora_voice" size="18px" />
                            <span class="text-subtitle2">Dora thinks you may be out of…</span>
                        </q-card-section>
                        <q-card-section class="q-pt-none">
                            <div class="row q-gutter-xs">
                                <q-chip
                                    v-for="s in visibleSuggestions"
                                    :key="s.stock_item_id"
                                    clickable
                                    outline
                                    color="primary"
                                    :icon="ICONS.add"
                                    :disable="addingSuggestionId === s.stock_item_id"
                                    @click="onAddSuggestion(s)"
                                >
                                    {{ s.name }}
                                    <BaseTooltip v-if="s.reason" max-width="280px">
                                        {{ s.reason }}
                                    </BaseTooltip>
                                </q-chip>
                            </div>
                        </q-card-section>
                    </q-card>

                    <!-- One list, three faces. "Start shopping" changes the
                         page's *composition*, not just its status — that was
                         the structural defect the redesign set out to fix
                         ("shopping mode is a costume"; "DONE is DRAFT with
                         everything disabled"). The run and receipt faces are
                         their own components rather than more branches in this
                         template: they share the list, the sectioning and the
                         mutations, and nothing else.

                         Below is the plan face. Curating a list is the only
                         thing this composition is for, so every affordance on
                         a row (drag, delete, steppers, buy hints, offers,
                         provenance) belongs to it and to no other face. -->
                    <q-card v-if="planFace && detail.lines.length === 0" flat class="sl-panel">
                        <q-card-section class="text-center dora-text-muted">
                            No items yet. Add using the toolbar here, or add from your
                            stock list.
                        </q-card-section>
                    </q-card>

                    <!-- The "Order by" bar used to sit here, and a second copy
                         of it inside `ShoppingListRunFace`. Both moved into the
                         overview card's control row: it is one view preference,
                         so it should be one control, and two copies were free
                         to drift. -->
                    <template v-else-if="planFace">
                        <div
                            v-for="section in lineSections"
                            :key="section.key"
                            class="q-mb-md"
                        >
                            <!-- Section headers read as headers now: the old
                                 muted `text-subtitle2` floated above a bordered
                                 box and looked like an afterthought rather than
                                 the thing structuring the page. -->
                            <div v-if="section.label" class="sl-section__head">
                                <q-icon :name="sectionIcon" size="16px" />
                                <span class="sl-section__title">{{ section.label }}</span>
                                <span class="sl-section__count">{{ section.lines.length }}</span>
                            </div>
                            <!-- One soft slab, not `q-list bordered separator`
                                 inside a bordered page. The rows own their own
                                 dividers, inset to the content column. -->
                            <div class="sl-list">
                                <ShoppingListPlanRow
                                    v-for="line in section.lines"
                                    :key="line.line_id"
                                    :line="line"
                                    :line-done="detail.status === 'done'"
                                    :can-reorder="canReorder"
                                    :is-first="isFirstLine(line)"
                                    :is-last="isLastLine(line)"
                                    :focused="focusedLineId === line.line_id"
                                    :nested="isNestedChild(line)"
                                    :product-only="isProductOnly(line)"
                                    :price="priceForLine(line)"
                                    :store-options="plannedStoreOptionsFor(line)"
                                    :class="lineDnd.bind(line).rowClass"
                                    v-bind="{
                                        ...lineDnd.bind(line).handleProps,
                                        ...lineDnd.bind(line).rowProps,
                                    }"
                                    @move="moveLine(line, $event)"
                                    @remove="onRemoveLine(line.line_id)"
                                    @adjust-quantity="onAdjustQuantity(line, $event)"
                                    @set-quantity="setLineQuantity(line, $event)"
                                    @planned-store="onPlannedStoreChange(line, $event)"
                                    @pick-offer="onPickOffer(line.line_id, $event)"
                                    @pick-hint="onPickHint(line.line_id, $event)"
                                    @verdict-action="onLineVerdictAction(line, $event)"
                                />
                            </div>
                        </div>
                    </template>

                    <ShoppingListRunFace
                        v-else-if="runFace"
                        :lines="baseLines"
                        :mode="groupBy"
                        :picked-total="detail.totals.picked_price"
                        @update:mode="groupBy = $event"
                        @tick="onRunTick"
                        @untick="onRunUntick"
                        @capture-price="openPriceSheet"
                    />
                    <ShoppingListReceiptFace
                        v-else-if="receiptFace"
                        :detail="detail"
                        :amending="amending"
                        @stop-amend="amending = false"
                        @edit-price="openPriceSheet"
                        @adjust-quantity="onAdjustQuantity"
                    />

                    <!-- Deferred-to-fit-budget section
                         (PROPOSAL_BUDGET_AWARE_LISTS §6.3). Renders when the
                         list has any lines with `deferred_by_budget=true`.
                         Collapsible; each row shows the frozen reason chip
                         and a one-tap "Add back" that flips the flag off
                         via PATCH /lines/<id>. -->
                    <q-expansion-item
                        v-if="planFace && deferredLines.length > 0"
                        id="deferred-by-budget"
                        :label="`Deferred to fit budget (${deferredLines.length})`"
                        :caption="`${fmtMoney(deferredTotal)} saved`"
                        default-opened
                        class="q-mt-md sl-panel sl-panel--sunken"
                    >
                        <!-- Hand-rolled rather than `q-item` + `q-item-section
                             side` (2026-09-17). The side section doesn't wrap:
                             at 375px the frozen reason is a full sentence
                             ("Would put the week $12 over; the tin can wait.")
                             and "Add back" printed straight across it. A row
                             that can't fit its own contents on one line has to
                             be allowed to become two. -->
                        <div
                            v-for="line in deferredLines"
                            :key="line.line_id"
                            class="sld-deferred-row"
                        >
                            <div class="sld-deferred-row__main">
                                <div>{{ line.stock_item_name }}</div>
                                <div class="text-caption dora-text-muted">
                                    <span v-if="line.deferred_reason" class="sld-deferred-reason">
                                        {{ line.deferred_reason }}
                                    </span>
                                    {{ fmtMoney(priceOfLine(line)) }}
                                </div>
                            </div>
                            <BaseButton
                                variant="subtle"
                                label="Add back"
                                class="sld-deferred-row__action"
                                :loading="addingBackLineIds.has(line.line_id)"
                                @click="addLineBackToActive(line.line_id)"
                            />
                        </div>
                    </q-expansion-item>

                    <!-- receipt-photo record-keeping. Visible only
                         once the list is being shopped or finished; pure
                         record-keeping (no OCR, no parsing). Multi-photo;
                         tap to zoom, trash to remove. Source-pick UX
                         (Take photo vs Choose image) is delegated to the
                         shared ImageSourcePicker primitive (R-0NN). -->
                    <div
                        v-if="attachmentSectionVisible"
                        class="sld-receipts q-mt-lg"
                    >
                        <div class="row items-center q-mb-sm">
                            <div class="text-subtitle2 text-weight-medium">
                                Receipts
                            </div>
                            <q-space />
                            <ImageSourcePicker
                                variant="ghost"
                                take-photo-label="Take photo"
                                pick-label="Choose receipt"
                                :loading="attachmentUploading"
                                @pick="onAttachmentPicked"
                                @error="onAttachmentError"
                            />
                        </div>
                        <div
                            v-if="(detail.attachments?.length ?? 0) === 0"
                            class="text-caption dora-text-muted"
                        >
                            No receipts yet.
                        </div>
                        <div v-else class="sld-receipt-strip row q-gutter-sm">
                            <div
                                v-for="att in detail.attachments"
                                :key="att.attachment_id"
                                class="sld-receipt-thumb"
                            >
                                <img
                                    :src="attachmentSrc(att.attachment_id)"
                                    alt="Receipt"
                                    @click="attachmentZoomId = att.attachment_id"
                                />
                                <BaseButton
                                    variant="ghost"
                                    :icon="ICONS.delete"
                                    class="sld-receipt-delete"
                                    dense
                                    @click="onDeleteAttachment(att.attachment_id)"
                                >
                                    <BaseTooltip>Remove receipt</BaseTooltip>
                                </BaseButton>
                            </div>
                        </div>
                    </div>

                    <!-- Full-screen receipt viewer (lightbox). Tap thumb to
                         open; tap the dialog backdrop or hit Esc to close. -->
                    <BaseDialog
                        :model-value="attachmentZoomId !== null"
                        max-width="900px"
                        @update:model-value="(v) => { if (!v) attachmentZoomId = null }"
                    >
                        <img
                            v-if="attachmentZoomId"
                            :src="attachmentSrc(attachmentZoomId)"
                            alt="Receipt"
                            class="sld-receipt-zoom"
                        />
                    </BaseDialog>

                    <!-- Destructive footer. 2026-08-26 feedback moved "Clear
                         all items" out of the More menu; it landed here
                         rather than on the toolbar deliberately, and "Delete
                         list" came with it for the same reason: you reach
                         both only by scrolling past everything they'd
                         destroy, and neither sits in the thumb path next to
                         "Add item". Both still confirm.

                         Delete list also lives on each list's own ⋮ menu in
                         the rail / switcher — this is the one for the list
                         you're currently looking at. -->
                    <div class="sld-danger-footer row items-center justify-center q-mt-lg q-pt-md">
                        <BaseButton
                            variant="ghost"
                            :icon="ICONS.playlist_remove"
                            label="Clear all items"
                            class="text-negative"
                            :disable="detail.lines.length === 0"
                            @click="onClearAll"
                        >
                            <BaseTooltip>Remove every line. The list itself stays.</BaseTooltip>
                        </BaseButton>
                        <BaseButton
                            variant="ghost"
                            :icon="ICONS.delete"
                            label="Delete list"
                            class="text-negative"
                            :disable="!currentSummary"
                            @click="onDeleteCurrentList"
                        >
                            <BaseTooltip>Delete this list and everything on it.</BaseTooltip>
                        </BaseButton>
                    </div>

                    <!-- The mid-shop sticky footer used to live here, carrying
                         the ring, the remaining spend and the finish CTA. All
                         three moved into the overview card at the top of the
                         page, and the footer is gone rather than reduced.

                         It was `position: sticky; bottom: 8px` as the *last*
                         child of this column, with no spacer and no
                         `padding-bottom` on anything above it — so it floated
                         over the last rows of the list and over the destructive
                         footer for the entire scroll, not merely at the end.
                         It also had no `env(safe-area-inset-bottom)`, and at
                         `z-index: 3` it sat under `DoraBubble`'s fixed 3000,
                         which put the mascot squarely on top of the finish
                         button on a phone (FU-784 tracks that placement budget
                         generally). Reproducing all of that in a slimmer footer
                         was never the goal; one card was. -->
                </div>

                <!-- Fallback so the content area is never blank — e.g. when
                     load() fails (loadError banner above carries the message)
                     or the listId in the URL doesn't resolve. -->
                <div v-else key="sld-empty" class="text-center dora-text-muted q-py-xl">
                    <q-icon :name="ICONS.shopping_cart" size="60px" class="q-mb-sm" />
                    <div v-if="loadError" class="text-h6">Couldn't open this list.</div>
                    <div v-else class="text-h6">This list isn't available.</div>
                    <div class="q-mt-md">
                        Pick another list from the panel, or create a new one.
                    </div>
                    <div class="q-mt-md">
                        <BaseButton
                            variant="primary"
                            :icon="ICONS.add"
                            label="New list"
                            @click="newListOpen = true"
                        />
                    </div>
                </div>
                </FadeTransition>
            </div>

            <!-- Desktop lists rail (UX-v2 §3.1): every list, active and done,
                 one continuum ordered by effective date (server-owned order),
                 virtualised because it accretes forever, auto-scrolled to the
                 selection. -->
            <!-- Kept mid-shop as of 2026-08-28. It used to disappear on the run
                 face in favour of a toolbar button, which meant the control for
                 "which list am I on" changed shape at the exact moment the
                 answer matters most. It is a `gt-sm` column, so it was never
                 competing with a phone's screen anyway. -->
            <div class="col-auto gt-sm">
                <div class="sld-rail column">
                    <!-- Primary as of 2026-08-29, taking the styling "New list"
                         had in the toolbar before it moved here. It is the only
                         creation surface on this page now, so it can't also be
                         the quietest control on it. -->
                    <BaseButton
                        variant="primary"
                        :icon="ICONS.add"
                        label="New list"
                        class="full-width q-mb-sm"
                        @click="newListOpen = true"
                    />
                    <!-- A plain list, sized to its contents. It was a
                         `q-virtual-scroll` filling the column's full height,
                         which is what stranded "See older" at the bottom of a
                         tall empty rail instead of under the lists it belongs
                         to. Virtualising is also dead weight now: the picker is
                         capped at drafts + shopping + 5 done, so it renders
                         about eight rows, not the 29 it used to. -->
                    <ShoppingListRailItem
                        v-for="s in railEntries"
                        :key="s.shopping_list_id"
                        :summary="s"
                        :active="s.shopping_list_id === listId"
                        @select="switchToList(s.shopping_list_id)"
                    />
                    <BaseButton
                        v-if="olderDoneSummaries.length > 0"
                        variant="ghost"
                        dense
                        :icon="ICONS.history"
                        :label="`See older (${olderDoneSummaries.length})`"
                        class="full-width q-mt-sm"
                        @click="openOlderLists"
                    />
                    <!-- "Manage templates…" is gone from here. The toolbar's
                         **Templates** button goes to the same route, and its own
                         comment says it was promoted there *because* this link
                         buried it — the link just never got removed. -->
                </div>
            </div>
        </div>

        <!-- the New-list dialog lives on the detail page now
             that Detail is the canonical surface. The router landing page
             also mounts this dialog for the no-lists empty state. -->
        <NewListDialog
            v-model="newListOpen"
            @created="onListCreated"
        />

        <PutAwayDialog
            v-if="detail && detail.status === 'done'"
            v-model="putAwayOpen"
            :lines="detail.lines"
            @assigned="onPutAwayAssigned"
        />

        <!-- "See older" — the finished lists the picker doesn't keep inline.
             Searchable rather than merely scrollable: the whole reason they're
             behind a door is that there are too many to scan, so a longer
             scroller would have moved the problem rather than solved it. -->
        <BaseDialog v-model="olderListsOpen" title="Older lists" closable>
            <q-input
                v-model="olderFilter"
                dense
                outlined
                clearable
                autofocus
                placeholder="Search finished lists"
                class="q-mb-sm"
            >
                <template #prepend><q-icon :name="ICONS.search" /></template>
            </q-input>
            <!-- Not `dense` (2026-09-17). `q-list dense` tightens every
                 `q-item` inside it, so the same rail row rendered at one height
                 in the rail and a squashed one here — the rows are the same
                 component and should read the same wherever they are shown. -->
            <q-list class="scroll" style="max-height: 60vh; min-width: 280px">
                <ShoppingListRailItem
                    v-for="s in filteredOlderSummaries"
                    :key="s.shopping_list_id"
                    :summary="s"
                    :active="s.shopping_list_id === listId"
                    @select="olderListsOpen = false; switchToList(s.shopping_list_id)"
                />
                <div
                    v-if="filteredOlderSummaries.length === 0"
                    class="text-center dora-text-muted q-pa-md"
                >
                    No finished list matches "{{ olderFilter }}".
                </div>
            </q-list>
        </BaseDialog>

        <!-- Renaming is a dialog on every width (2026-08-29 feedback).
             It was an inline input that replaced the title in place, and it
             had two problems the owner reported separately: it shoved the page
             around as it appeared and disappeared ("the input looks awkward
             when it pops up and moves UI"), and it lived inside a
             `v-if="!editingName"` that also wrapped the status pill and the
             pencil — so the list's state vanished for the duration of a rename
             ("why does the state disappear when editing the list name?").

             A dialog answers both structurally rather than by rearranging the
             same swap: nothing behind it moves, and the pill is never inside
             the thing being replaced. The desktop half could have kept an
             inline input now that the card gives it a stable row to sit in,
             but one editor beats two for a control used this rarely.

             The old placeholder hint is gone too — it was a second line of
             text under a field that had just pushed the layout, which is
             exactly what the complaint was about. The rule it explained is
             stated in the dialog's own body copy, where it costs nothing. -->
        <BaseDialog v-model="editingName" title="Rename list" closable card-style="min-width: 300px">
            <q-card-section>
                <q-input
                    v-model="nameDraft"
                    outlined
                    dense
                    autofocus
                    clearable
                    label="List name"
                    @keydown.enter.prevent="saveName"
                />
            </q-card-section>
            <q-card-section class="q-pt-none">
                <div class="text-caption dora-text-muted">
                    Leave it blank to use
                    <strong>{{ dateFallbackName }}</strong>.
                </div>
            </q-card-section>
            <template #actions>
                <BaseButton variant="ghost" label="Cancel" @click="cancelName" />
                <BaseButton variant="primary" label="Save" @click="saveName" />
            </template>
        </BaseDialog>


        <!-- The line editor for the run and receipt faces. A bottom sheet, not
             a popover: mid-shop the phone is one-handed and the keyboard eats
             the top half of the screen, so the fields have to sit where a thumb
             already is. One editor, both faces — the receipt's Amend reuses it
             rather than growing a second form.

             2026-08-28: it now carries **quantity** too. It was price-only, so
             the one thing you routinely discover at the shelf — "they only had
             the 2-pack", "grab three while they're on special" — could not be
             recorded without leaving shop mode. -->
        <BaseDialog
            v-model="priceSheetOpen"
            position="bottom"
            card-class="sld-price-sheet"
            card-style="width: 100%; max-width: 520px"
            :title="priceSheetLine?.stock_item_name ?? 'Price'"
            closable
        >
            <q-card-section class="sld-price-sheet__body">
                <!-- "Price each", not "Price per unit" (owner, 2026-09-17:
                     *"What unit? I haven't told you and I can't see what
                     you're assuming"*). The honest answer is that it was never
                     a measurement unit: this value is the price of **one of
                     them**, and the line total is it × quantity. Nothing here
                     needs a gram or a litre — which is exactly why this sheet
                     looks different from the *log a price* form, where the
                     number becomes a price-per-100g observation in the item's
                     history and a measure is unavoidable. Two records, two
                     shapes; the label was the only thing lying about it. -->
                <q-input
                    v-model.number="priceEditorDraft.price"
                    autofocus
                    outlined
                    type="number"
                    inputmode="decimal"
                    step="0.01"
                    min="0"
                    label="Price each"
                    :prefix="currencySymbol"
                    input-class="sld-price-sheet-input"
                    @keydown.enter.prevent="savePriceSheet"
                />
                <!-- The arithmetic said out loud, so "each" needs no
                     explaining once you have typed a quantity above one. -->
                <div v-if="priceSheetLineTotal" class="text-caption dora-text-muted sld-price-sheet__total">
                    {{ priceEditorDraft.quantity ?? 1 }} × {{ fmtMoney(priceEditorDraft.price ?? 0) }}
                    = <strong>{{ priceSheetLineTotal }}</strong>
                </div>

                <!-- Pulling an offer in is an *act*, not an assumption
                     (2026-09-17). Offers stopped prefilling prices anywhere —
                     an advertised number is the shop's claim, not your money —
                     so this is the one place one becomes a price, by tapping
                     it, at the shelf, where you can see whether it's true. -->
                <div v-if="priceSheetOffers.length > 0" class="sld-price-sheet__offers">
                    <div class="text-caption dora-text-muted">Seen at</div>
                    <div class="row q-gutter-xs">
                        <q-chip
                            v-for="offer in priceSheetOffers"
                            :key="offer.product_id"
                            clickable
                            outline
                            dense
                            @click="useOfferPrice(offer)"
                        >
                            <StoreLogo
                                :name="offer.store_name"
                                :store-id="offer.store_id"
                                :height="16"
                                :width="24"
                                inline
                            />
                            {{ fmtMoney(offer.price_now ?? 0) }} at {{ offer.store_name }}
                            <BaseTooltip>Use this as the price each</BaseTooltip>
                        </q-chip>
                    </div>
                </div>

                <!-- Stepper rather than a number field: a second keyboard on a
                     sheet that already has one open is a worse target than two
                     44px buttons (D-004), and quantities here are ±1 in
                     practice. -->
                <div class="row items-center q-gutter-sm">
                    <span class="col dora-text-secondary">Quantity</span>
                    <BaseButton
                        variant="icon"
                        :icon="ICONS.remove"
                        aria-label="One fewer"
                        :disable="(priceEditorDraft.quantity ?? 1) <= 1"
                        @click="priceEditorDraft.quantity = Math.max(1, (priceEditorDraft.quantity ?? 1) - 1)"
                    />
                    <span class="sld-sheet-qty">{{ priceEditorDraft.quantity ?? 1 }}</span>
                    <BaseButton
                        variant="icon"
                        :icon="ICONS.add"
                        aria-label="One more"
                        @click="priceEditorDraft.quantity = (priceEditorDraft.quantity ?? 1) + 1"
                    />
                </div>
                <BaseSelect
                    v-if="allStoreOptions.length > 0"
                    v-model="priceEditorDraft.store_id"
                    :options="allStoreOptions"
                    emit-value
                    map-options
                    clearable
                    label="Bought from"
                >
                    <template #option="{ opt, itemProps }">
                        <q-item v-bind="itemProps">
                            <q-item-section avatar style="min-width: 0; padding-right: 8px">
                                <StoreLogo :name="opt.label" :store-id="opt.value" :height="20" :width="34" />
                            </q-item-section>
                            <q-item-section>{{ opt.label }}</q-item-section>
                        </q-item>
                    </template>
                </BaseSelect>
            </q-card-section>
            <template #actions>
                <BaseButton
                    v-if="priceSheetLine && priceSheetLine.actual_unit_price != null"
                    variant="danger-ghost"
                    label="Clear"
                    @click="clearPriceSheet"
                />
                <BaseButton variant="ghost" label="Cancel" v-close-popup />
                <BaseButton variant="primary" label="Save" @click="savePriceSheet" />
            </template>
        </BaseDialog>

        <!-- UX-v2 M12 — restock review. One-click "Restock & finish" with
             every ticked item listed and individually adjustable (default
             Stocked). Replaces the old text-only confirm dialog. -->
        <!-- Finish & restock. 2026-08-26 feedback: the dialog *"asks if you
             want to move unticked/unpurchased items to another list for
             later, UI changes based on whether all items are ticked or not"*.

             So it has two shapes. Clean finish: a confirmation of what's
             about to be restocked. Finishing early: the same, plus the
             leftovers promoted from a passive grey footnote ("copy or move
             them later if they're still wanted" — which nobody ever did,
             because the list was archived by then and the items were
             stranded) into an actual decision made at the only moment the
             user is thinking about it.

             This is where the old More → "Move unticked to another list"
             went. Same server call, offered at the right time instead of
             hidden in a menu you'd have to think to open.

             The title is a fixed "Finish shopping" as of 2026-08-29, having
             been "Finish early & restock" / "Finish & restock". Both halves
             went for the same reason — a heading that narrates back what the
             user already knows. *"People will understand this also involves
             restocking"*, and *"people know if they are finishing early or
             not"*. Neither word is lost: the body lists every item about to be
             restocked, and the leftovers section below appears precisely when
             you are finishing early, which is the honest signal — a section
             you must act on rather than an adjective in a heading. -->
        <BaseDialog
            v-model="finishReviewOpen"
            title="Finish shopping"
            closable
            card-style="min-width: 320px; max-width: 480px"
        >
            <q-card-section>
                <div class="text-body2 dora-text-muted">
                    {{
                        finishEntries.length === 0
                            ? 'No items are ticked, so nothing is restocked.'
                            : 'These ticked items will be restocked:'
                    }}
                </div>
            </q-card-section>
            <q-card-section v-if="finishEntries.length > 0" class="q-pt-none scroll" style="max-height: 34vh">
                <q-list separator dense>
                    <q-item v-for="entry in finishEntries" :key="entry.line_id">
                        <q-item-section>
                            <q-item-label>{{ entry.name }}</q-item-label>
                        </q-item-section>
                        <q-item-section v-if="!entry.stock_item_id" side>
                            <span class="text-caption dora-text-muted">
                                Not stock-tracked
                            </span>
                        </q-item-section>
                    </q-item>
                </q-list>
            </q-card-section>

            <q-card-section v-if="untickedCount > 0" class="q-pt-none">
                <q-banner class="dora-bg-warning-soft q-mb-sm" dense rounded>
                    <template #avatar>
                        <q-icon :name="ICONS.warning" color="warning" />
                    </template>
                    <span class="text-body2">
                        <strong>
                            {{ untickedCount }} item{{ untickedCount === 1 ? '' : 's' }}
                        </strong>
                        {{ untickedCount === 1 ? "isn't" : "aren't" }} ticked.
                        A finished list is a receipt, so
                        {{ untickedCount === 1 ? 'it' : 'they' }}
                        can't stay on it.
                    </span>
                </q-banner>
                <q-option-group
                    v-model="leftoverAction"
                    :options="leftoverOptions"
                    color="primary"
                    dense
                />
                <!-- Only rendered for the "move to an existing list" branch,
                     and that branch only exists when there is somewhere to
                     move to. -->
                <BaseSelect
                    v-if="leftoverAction === 'move-existing'"
                    v-model="leftoverTargetListId"
                    class="q-mt-sm"
                    label="Move to"
                    :options="otherActiveListOptions"
                    emit-value
                    map-options
                />
                <div
                    v-if="leftoverAction === 'move-existing' || leftoverAction === 'move-new'"
                    class="text-caption dora-text-muted q-mt-sm"
                >
                    Anything already on that list is skipped.
                </div>
                <div
                    v-else-if="leftoverAction === 'discard'"
                    class="text-caption dora-text-muted q-mt-sm"
                >
                    Removed from the list for good. Your pantry and purchase
                    history aren't touched.
                </div>
            </q-card-section>

            <template #actions>
                <BaseButton
                    variant="ghost"
                    :label="untickedCount > 0 ? 'Go back' : 'Cancel'"
                    v-close-popup
                />
                <BaseButton
                    variant="positive"
                    :icon="ICONS.check"
                    :label="finishCtaLabel"
                    :disable="finishBlocked"
                    :loading="finishing"
                    @click="confirmFinish"
                />
            </template>
        </BaseDialog>
    </q-page>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import { formatDate as formatLocaleDate } from 'src/composables/useDateFormat';
    import AppSkeleton from 'src/components/AppSkeleton.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDropdown from 'src/components/BaseDropdown.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import ShoppingListOverviewCard from 'src/components/shoppingList/ShoppingListOverviewCard.vue';
    import ShoppingListPlanRow from 'src/components/shoppingList/ShoppingListPlanRow.vue';
    import ShoppingListRunFace from 'src/components/shoppingList/ShoppingListRunFace.vue';
    import ShoppingListReceiptFace from 'src/components/shoppingList/ShoppingListReceiptFace.vue';
    import {
        PLAN_SECTION_MODES, useLineSections, isNestedChild,
        isProductOnly, sectionIconFor, type SectionMode,
    } from 'src/composables/useLineSections';
    import FadeTransition from 'src/components/transitions/FadeTransition.vue';
    import NewListDialog from 'src/components/dialogs/NewListDialog.vue';
    import PutAwayDialog from 'src/components/dialogs/PutAwayDialog.vue';
    import ShoppingListRailItem from 'src/components/shoppingList/ShoppingListRailItem.vue';
    import StoreLogo from 'src/components/StoreLogo.vue';
    import BuyVerdictApiService from 'src/services/api/buyVerdictApiService';
    import {
        invalidateBuyVerdict, primeBuyVerdicts,
    } from 'src/composables/useBuyVerdict';
    import { useBuyVerdictEnabled } from 'src/composables/useBuyVerdictEnabled';
    import { useBuyVerdictActions } from 'src/composables/useBuyVerdictActions';
    import { useQuasar } from 'quasar';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { useMoney, formatMoney } from 'src/composables/useMoney';
    const { currencySymbol } = useMoney();
    import { useDragDropList } from 'src/composables/useDragDropList';
    import { useQuickAdd } from 'src/composables/useQuickAdd';
    import { useShoppingListExport } from 'src/composables/useShoppingListExport';
    import { useShortcut } from 'src/composables/useShortcut';
    import { useWakeLock } from 'src/composables/useWakeLock';
    import {
        chosenOfferFor,
        listStatusIcon,
        priceOfLine,
        type InferredSuggestion,
        type LineProductOffer,
        type ShoppingListDetail,
        type ShoppingListLine,
        type ShoppingListSummary
    } from 'src/models/shoppingList';
    import ShoppingListApiService, {
        shoppingListAttachmentUrl,
        type TrimToBudgetResult,
        type UpdateLineCommand,
    } from 'src/services/api/shoppingListApiService';
    import ImageSourcePicker from 'src/components/ImageSourcePicker.vue';
    import type { ProcessedImage } from 'src/services/files/imageService';
    import ShoppingListTemplateApiService from 'src/services/api/shoppingListTemplateApiService';
    import { useProductStore } from 'src/stores/productStore';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { useStoresStore } from 'src/stores/storesStore';
    import { useLogPrice } from 'src/composables/useLogPrice';
    import { useListState } from 'src/composables/useListState';
    import { computed, onMounted, reactive, ref, watch } from 'vue';
    import { useRoute, useRouter } from 'vue-router';
    import { describeApiError, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useConfirm } from 'src/composables/useConfirm';

    const route = useRoute();
    const router = useRouter();
    const $q = useQuasar();
    const { confirm, prompt } = useConfirm();
    const api = new ShoppingListApiService();
    const templateApi = new ShoppingListTemplateApiService();
    const store = useShoppingListStore();
    const stockItemStore = useStockItemStore();
    const stockLevelStore = useStockLevelStore();
    const productStore = useProductStore();
    const { moneyEnabled } = useMoneyEnabled();
    // Phones drop every toolbar label and ride the icon alone, tooltip
    // carrying the name — same breakpoint and same reason as Stock overview's
    // `compactToolbar` (the row was eating a quarter of the screen).
    const compactToolbar = computed(() => $q.screen.lt.sm);
    // Per-user display opt-out (D-12). Gates the bulk verdict prefetch below;
    // `BuyVerdictBadgeInline` checks it again for the render.
    const { buyVerdictEnabled } = useBuyVerdictEnabled();
    const { openQuickAdd, isOpen: quickAddOpen } = useQuickAdd();

    const listId = computed(() => String(route.params.id ?? ''));
    const detail = ref<ShoppingListDetail | null>(null);

    // shop-mode wake lock. Holds the screen on while the list is
    // in 'shopping' status so the phone doesn't blank between aisles. The
    // computed reads `detail.value?.status` so entering / leaving shop
    // mode toggles the lock without any explicit acquire/release call.
    const shopModeActive = computed(() => detail.value?.status === 'shopping');
    useWakeLock(shopModeActive);

    // Which face is on screen. Named rather than compared inline because the
    // three compositions gate a couple of dozen blocks between them, and
    // `status === 'draft'` scattered through the template reads as an
    // implementation detail where "the plan face" reads as the design.
    const planFace = computed(() => detail.value?.status === 'draft');
    const runFace = computed(() => detail.value?.status === 'shopping');
    const receiptFace = computed(() => detail.value?.status === 'done');

    // Amend is off every time the receipt is opened — a historical record
    // should never come up already unlocked, and the mode must not survive a
    // switch to a different list.
    const amending = ref(false);
    watch([listId, receiptFace], () => { amending.value = false; });
    // Starts true: the first painted frame must be the skeleton, never the
    // "list isn't available" fallback (the S6 flash) — onMounted's load()
    // hasn't had a chance to set it yet on that first frame.
    const loading = ref(true);
    const loadError = ref<string | null>(null);
    const editingName = ref(false);
    const nameDraft = ref('');

    // Group lines by nothing, by stock location or by chosen merchant.
    // UX-v2 M2 revision: grouping is a *user-chosen* view preference only —
    // shopping does NOT default to location (stock location is where the
    // item lives at home, not where it sits on a shelf).
    //
    // FU-354 — wrapped in `useListState` so the picked grouping survives
    // navigate-away-and-back within the session (A8 §3 nav-state
    // policy). Full reload / sign-out (via `clearAllListState` from
    // FU-355) still resets to `'none'`. Single scope, not per-list — the
    // groupBy is a *view* preference the user re-uses across lists; a
    // per-list scope would silently reset the moment they open a new
    // list, defeating the point.
    // Four peer modes (Location / Group / Store / None) — see
    // `useLineSections`. The ungrouped mode was called "Manual" until
    // 2026-09-17: it named the *mechanism* (your own sequence order) while
    // every other member named what you're grouped by, so it read as a fourth
    // grouping rather than the absence of one. Store moved here from the old
    // toolbar segmented control; the auto-disable rule means a single-store
    // list greys it out rather than showing one pointless section.
    const { groupBy } = useListState('shopping-list-detail', () => ({
        groupBy: ref<SectionMode>('none'),
    }));

    // ── Lifecycle: start / finish ────────────────────────────────────
    const togglingProgress = ref(false);

    async function onStartShopping() {
        togglingProgress.value = true;
        try {
            await api.startShoppingAsync(listId.value);
            // UX-v2: no separate shop page — the page itself flips into the
            // shopping state (sticky footer, big ticks, Finish CTA).
            await refreshAll();
            $q.notify({
                type: 'positive',
                message: 'Shopping started.',
            });
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not start shopping.',
                caption: toastCaption(err),
            });
        } finally {
            togglingProgress.value = false;
        }
    }

    // ── Finish & restock ────────────────────────────────────────────
    // The dialog previously let you pick a per-item stock level (in case
    // you'd only partly topped something up). With levels simplified, every
    // ticked item just restocks to Stocked — the server default when no
    // overrides are sent.
    const finishReviewOpen = ref(false);
    const finishing = ref(false);
    type FinishEntry = {
        line_id: string;
        stock_item_id: string | null;
        name: string;
    };
    const finishEntries = ref<FinishEntry[]>([]);

    /** What to do with lines that were never ticked. There is deliberately no
     *  "leave them here" option and no default selection: a finished list is a
     *  receipt, and a receipt doesn't record what you didn't buy. Leaving them
     *  stranded them on an archived list forever and kept them counted in the
     *  dashboard's "queued" card. The fourth way out is Cancel — go back and
     *  tick them off after all. */
    type LeftoverAction = 'discard' | 'move-existing' | 'move-new';
    const leftoverAction = ref<LeftoverAction | null>(null);
    const leftoverTargetListId = ref<string | null>(null);

    const otherActiveListOptions = computed(() =>
        otherActiveLists.value.map((s) => ({
            label: s.display_name,
            value: s.shopping_list_id,
        }))
    );

    const leftoverOptions = computed(() => {
        const options = [];
        // Only offered when there is somewhere to move to. An empty radio
        // that opens an empty select is worse than not offering the choice.
        if (otherActiveLists.value.length > 0) {
            options.push({ label: 'Move them to another list', value: 'move-existing' });
        }
        options.push({ label: 'Move them to a new list', value: 'move-new' });
        options.push({ label: 'Discard them', value: 'discard' });
        return options;
    });

    /** Two states where "finish" is ambiguous: nothing chosen for the
     *  leftovers yet, or move-to-an-existing-list picked with no target. */
    const finishBlocked = computed(() => {
        if (untickedCount.value === 0) return false;
        if (leftoverAction.value === null) return true;
        return leftoverAction.value === 'move-existing' && !leftoverTargetListId.value;
    });

    const finishCtaLabel = computed(() => {
        if (untickedCount.value === 0) return 'Restock & finish';
        if (leftoverAction.value === 'discard') return 'Discard & finish';
        return 'Move & finish';
    });

    function openFinishReview() {
        if (!detail.value) return;
        // Reset the leftover decision each time the dialog opens — it is a
        // choice about *this* finish, not a remembered preference, and it
        // starts unmade so the dialog can't be confirmed past it.
        leftoverAction.value = null;
        leftoverTargetListId.value =
            otherActiveLists.value[0]?.shopping_list_id ?? null;
        const seen = new Set<string>();
        finishEntries.value = detail.value.lines
            .filter((l) => l.is_ticked)
            .filter((l) => {
                // One row per stock item — duplicate anchors (nested
                // product lines) collapse into the parent's entry.
                if (!l.stock_item_id) return true;
                if (seen.has(l.stock_item_id)) return false;
                seen.add(l.stock_item_id);
                return true;
            })
            .map((l) => ({
                line_id: l.line_id,
                stock_item_id: l.stock_item_id,
                name: l.stock_item_name,
            }));
        finishReviewOpen.value = true;
    }

    /** Clears the unticked lines off this list per the dialog's choice, before
     *  the finish archives it. Returns how many moved and how many were
     *  discarded, so the toast can say which happened.
     *
     *  Order matters: this has to happen *first*. `finishAsync` archives the
     *  list, and the server refuses to move lines onto (or, once done,
     *  meaningfully off) an archived list. */
    async function disposeLeftoversBeforeFinish(): Promise<{
        moved: number;
        discarded: number;
    }> {
        const none = { moved: 0, discarded: 0 };
        if (untickedCount.value === 0 || leftoverAction.value === null) return none;

        if (leftoverAction.value === 'discard') {
            const result = await api.discardUntickedAsync(listId.value);
            return { moved: 0, discarded: result.removed_count };
        }

        let targetId = leftoverTargetListId.value;
        if (leftoverAction.value === 'move-new') {
            // Two calls rather than one, and deliberately not a per-item
            // loop: create the list, then move the whole leftover set into
            // it in a single request.
            const created = await api.createAsync({
                name: `Leftovers from ${detail.value?.display_name ?? 'last shop'}`,
            });
            targetId = created.shopping_list_id;
        }
        if (!targetId) return none;

        const result = await api.moveUntickedToAsync(listId.value, targetId);
        return { moved: result.moved_count, discarded: 0 };
    }

    async function confirmFinish() {
        if (finishBlocked.value) return;
        finishing.value = true;
        try {
            const { moved, discarded } = await disposeLeftoversBeforeFinish();
            const result = await api.finishAsync(listId.value);
            finishReviewOpen.value = false;
            if (moved > 0) {
                $q.notify({
                    type: 'positive',
                    message: `${moved} unticked item${
                        moved === 1 ? '' : 's'
                    } moved for later.`,
                });
            }
            if (discarded > 0) {
                $q.notify({
                    type: 'positive',
                    message: `${discarded} unticked item${
                        discarded === 1 ? '' : 's'
                    } discarded.`,
                });
            }
            await Promise.all([
                refreshAll(),
                stockItemStore.getStockItemsAsync(),
            ]);
            $q.notify({
                type: 'positive',
                message: `Shopping finished. ${result.items_restocked} item${
                    result.items_restocked === 1 ? '' : 's'
                } restocked.`,
            });
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not finish shopping.',
                caption: toastCaption(err),
            });
        } finally {
            finishing.value = false;
        }
    }

    // ── Drag-to-reorder ───────────────────────────────────────────────
    // Reordering only means something when grouping is off: in every other
    // mode the section order is derived from a field, so dragging a row would
    // either be ignored or silently rewrite a sequence the user can't see.
    // `effectiveMode` rather than `groupBy`, so a stored preference pointing at
    // an empty field (which falls back to ungrouped) still gets the affordance.
    const canReorder = computed(() =>
        !!detail.value
            && detail.value.status !== 'done'
            && detail.value.status !== 'shopping'
            && effectiveMode.value === 'none'
    );

    // R-022 — whole-row DnD via `useDragDropList`. `canDragStart` is gated
    // on `canReorder` (list not done/shopping, no grouping, not in bulk
    // mode), so the `draggable` attribute reactively turns off the
    // browser's drag affordance when reorder isn't allowed. The drop
    // effect mirrors the historical insert-at-target's-slot pattern
    // (fixed the off-by-one in P6-01 Chunk 6 / feedback L414).
    const lineDnd = useDragDropList<ShoppingListLine>({
        mime: 'application/x-dora-shopping-line',
        getId: (line) => line.line_id,
        canDragStart: () => canReorder.value,
        onDrop: ({ id: draggedId }, { id: targetLineId }) => {
            if (!detail.value) return;
            const lines = detail.value.lines;
            const ids = lines.map((l) => l.line_id);
            const fromIdx = ids.indexOf(draggedId);
            const toIdx = ids.indexOf(targetLineId);
            if (fromIdx < 0 || toIdx < 0) return;
            ids.splice(fromIdx, 1);
            ids.splice(toIdx, 0, draggedId);
            applyLineOrder(ids);
        },
    });

    /** Optimistically apply a new line order and persist it. Shared by the
     *  drag handler and the up/down arrows so there is one definition of what
     *  reordering does — and one place a failure reloads canonical state. */
    function applyLineOrder(ids: string[]): void {
        if (!detail.value) return;
        const lookup = new Map(detail.value.lines.map((l) => [l.line_id, l]));
        detail.value.lines = ids
            .map((id, idx) => {
                const line = lookup.get(id);
                if (!line) return null;
                line.sequence = idx;
                return line;
            })
            .filter((l): l is NonNullable<typeof l> => l !== null);

        void (async () => {
            try {
                await api.reorderLinesAsync(listId.value, ids);
            } catch (err) {
                await load();
                $q.notify({
                    type: 'negative',
                    message: 'Could not reorder.',
                    caption: toastCaption(err),
                });
            }
        })();
    }

    // deferred-by-budget lines render under their own collapsible
    // section, not the active list. Server-side totals already skip them.
    const baseLines = computed(() =>
        (detail.value?.lines ?? []).filter((l) => !l.deferred_by_budget),
    );

    // Sectioning for both faces. Mid-shop, ticked lines leave their section
    // entirely so the list shrinks as you shop; on the plan face they stay put
    // and dim. `effectiveMode` falls back to ungrouped when the stored
    // preference points at a field this list doesn't populate.
    // `availableModes` is no longer read here: the overview card owns the
    // "Group by" control and resolves availability for whichever face is
    // showing. This instance only sections.
    const {
        sections: lineSections,
        orderedLines: sectionOrderedLines,
        effectiveMode,
    } = useLineSections(baseLines, groupBy, {
        hideTicked: computed(() => detail.value?.status === 'shopping'),
        // Plan face: store + ungrouped only. The run face renders through
        // `ShoppingListRunFace`, which keeps all four.
        allowedModes: PLAN_SECTION_MODES,
    });

    // Arrow reordering. Moves within the *visible* ungrouped run rather than the
    // raw `detail.lines` array, so a deferred-by-budget line sitting between
    // two visible rows can't swallow a press and make the row appear stuck.
    function isFirstLine(line: ShoppingListLine): boolean {
        return sectionOrderedLines.value[0]?.line_id === line.line_id;
    }
    function isLastLine(line: ShoppingListLine): boolean {
        return sectionOrderedLines.value.at(-1)?.line_id === line.line_id;
    }
    function moveLine(line: ShoppingListLine, delta: -1 | 1): void {
        const visible = sectionOrderedLines.value;
        const from = visible.findIndex((l) => l.line_id === line.line_id);
        const to = from + delta;
        if (from < 0 || to < 0 || to >= visible.length) return;
        // Reorder the visible run, then splice it back over the full line
        // order so hidden lines keep their relative positions.
        const movedIds = visible.map((l) => l.line_id);
        movedIds.splice(from, 1);
        movedIds.splice(to, 0, line.line_id);
        const visibleSet = new Set(movedIds);
        let cursor = 0;
        const ids = (detail.value?.lines ?? []).map((l) =>
            visibleSet.has(l.line_id) ? movedIds[cursor++]! : l.line_id
        );
        applyLineOrder(ids);
    }

    const deferredLines = computed(() =>
        (detail.value?.lines ?? []).filter((l) => l.deferred_by_budget),
    );
    const deferredTotal = computed(() =>
        deferredLines.value.reduce((sum, l) => sum + priceOfLine(l), 0),
    );
    const addingBackLineIds = ref<Set<string>>(new Set());

    async function addLineBackToActive(lineId: string): Promise<void> {
        if (addingBackLineIds.value.has(lineId)) return;
        addingBackLineIds.value = new Set(addingBackLineIds.value).add(lineId);
        try {
            await api.updateLineAsync(listId.value, lineId, {
                deferred_by_budget: false,
            });
            // Quiet — see `onRemoveLine`; the line moves section, the page stays.
            await refreshAllQuietly();
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: describeApiError(err) ?? 'Could not add that line back.',
            });
        } finally {
            const next = new Set(addingBackLineIds.value);
            next.delete(lineId);
            addingBackLineIds.value = next;
        }
    }

    // ── FU-448 trim-to-budget banner (PROPOSAL_BUDGET_AWARE_LISTS §6) ──

    type TrimState = 'idle' | 'previewed' | 'applied';
    type TrimPreviewLine = {
        line_id: string;
        name: string;
        reason_chip: string;
        saved: number;
    };
    const trimState = reactive({
        state: 'idle' as TrimState,
        busy: false,
        loaded: false,                    // true once we've fetched the initial preview
        projectedTotal: 0,
        budgetTarget: 0,
        overshoot: 0,
        stillOver: 0,
        savedApplied: 0,
        previewLines: [] as TrimPreviewLine[],
        excluded: new Set<string>(),
        dismissed: false,
    });

    function fmtMoney(v: number | null | undefined): string {
        return formatMoney(v ?? 0);
    }

    const trimBanner = computed(() => {
        // Money features off, no budget set, list not auto-generated,
        // dismissed, or nothing to trim → banner stays hidden.
        const anyDeferredAlready = deferredLines.value.length > 0;
        const applied = trimState.state === 'applied' && anyDeferredAlready;
        const hasOvershoot = trimState.overshoot > 0;
        return {
            visible: moneyEnabled.value
                && !trimState.dismissed
                && trimState.loaded
                && (hasOvershoot || applied),
            state: trimState.state,
            busy: trimState.busy,
            projectedTotal: trimState.projectedTotal,
            budgetTarget: trimState.budgetTarget,
            overshoot: trimState.overshoot,
            stillOver: trimState.stillOver,
            savedApplied: trimState.savedApplied,
            previewLines: trimState.previewLines,
            canApply: trimState.overshoot > 0 && trimState.previewLines.length > 0,
        };
    });

    async function refreshTrimStatus(): Promise<void> {
        // Only fetch when money features are on and the list has active lines
        // — the endpoint gracefully returns overshoot=0 when there's no budget,
        // but skipping the call altogether keeps a fresh install quiet.
        if (!moneyEnabled.value || !detail.value) return;
        if (baseLines.value.length === 0) {
            trimState.loaded = true;
            trimState.overshoot = 0;
            return;
        }
        try {
            const result = await api.trimToBudgetAsync(listId.value, {
                mode: 'preview',
                exclude_line_ids: [...trimState.excluded],
            });
            applyTrimResult(result);
        } catch {
            // Non-fatal; the banner just stays hidden.
            trimState.loaded = true;
        }
    }

    function applyTrimResult(result: TrimToBudgetResult): void {
        trimState.loaded = true;
        trimState.projectedTotal = result.projected_total;
        trimState.budgetTarget = result.budget_target ?? 0;
        trimState.overshoot = result.overshoot;
        trimState.stillOver = result.still_over;
        // Freeze display names + saved amounts so the preview card doesn't
        // desync from the server (the SPA has all the info it needs).
        const nameByLine = new Map<string, string>();
        for (const l of detail.value?.lines ?? []) nameByLine.set(l.line_id, l.stock_item_name);
        trimState.previewLines = result.trimmed.map((t) => ({
            line_id: t.line_id,
            name: nameByLine.get(t.line_id) ?? 'Item',
            reason_chip: t.reason_chip,
            saved: t.saved,
        }));
    }

    async function previewTrim(): Promise<void> {
        if (trimState.busy) return;
        trimState.busy = true;
        try {
            const result = await api.trimToBudgetAsync(listId.value, {
                mode: 'preview',
                exclude_line_ids: [...trimState.excluded],
            });
            applyTrimResult(result);
            trimState.state = 'previewed';
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: describeApiError(err) ?? 'Could not preview the trim.',
            });
        } finally {
            trimState.busy = false;
        }
    }

    async function applyTrim(): Promise<void> {
        if (trimState.busy) return;
        trimState.busy = true;
        try {
            const result = await api.trimToBudgetAsync(listId.value, {
                mode: 'apply',
                exclude_line_ids: [...trimState.excluded],
            });
            trimState.savedApplied = result.trimmed.reduce((s, t) => s + t.saved, 0);
            trimState.state = 'applied';
            trimState.previewLines = [];
            // Quiet — see `onRemoveLine`; trimming edits the list in place.
            await refreshDetailQuietly();
            // After apply the list has fewer active lines and totals shift;
            // re-check whether we still overshoot so the banner updates
            // ("still over" fallback vs. done).
            await refreshTrimStatus();
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: describeApiError(err) ?? 'Could not trim to fit.',
            });
        } finally {
            trimState.busy = false;
        }
    }

    function keepFromTrim(lineId: string): void {
        trimState.excluded = new Set(trimState.excluded).add(lineId);
        // Re-preview so the totals + cut set update in-place.
        void previewTrim();
    }

    function dismissTrim(): void {
        trimState.dismissed = true;
    }

    function scrollToDeferred(): void {
        document.getElementById('deferred-by-budget')?.scrollIntoView({
            behavior: 'smooth',
            block: 'start',
        });
    }

    // Sectioning, nesting and the ticked-line policy all moved into
    // `useLineSections` so the plan and run faces share one implementation
    // (R-001). The old version lived here as `lineGroups` + `nestedLinesFor`
    // and sank ticked rows to the bottom of their group mid-shop; the run face
    // now removes them from view entirely, which is the point of the redesign.

    const untickedCount = computed(() =>
        (detail.value?.lines ?? []).filter((l) => !l.is_ticked).length
    );
    // The list-level money (`remaining_price`, `total_price`, `total_savings`),
    // the progress percentage and the status pill's label all moved into
    // `ShoppingListOverviewCard`, which is the only thing that rendered them.
    // They stay server-owned there (state-ownership Type B) — read off
    // `detail.totals`, never re-summed. What's left here are the two counts the
    // *finish* flow needs, which is a different question from what the header
    // shows.

    function priceForLine(line: ShoppingListLine): number {
        return priceOfLine(line);
    }

    function formatDate(iso: string): string {
        try {
            return formatLocaleDate(iso) || iso;
        } catch {
            return iso;
        }
    }

    // ── Planned shop date (Chunk 7 / UX-v2 §4) ───────────────────────
    // The page owns *setting* the date (a toolbar button pops a calendar);
    // the overview card owns *reading* it, including the today/overdue/tomorrow
    // wording and the tone. They were one control before — a button whose label
    // was the fact — and splitting them is what let the fact stay visible
    // mid-shop while the control disappears with the decision.
    const plannedDateOpen = ref(false);

    const sectionIcon = computed(() => sectionIconFor(effectiveMode.value));

    // Picking a day saves it. A null pick is q-date's "tap the selected day
    // again to deselect" — ignored rather than read as a clear, because the
    // explicit Clear button is the one way to un-plan and a stray re-tap
    // shouldn't silently drop the date.
    async function onPickPlannedDate(value: string | null) {
        if (!detail.value || !value || value === detail.value.planned_shop_date) return;
        const next = value;
        try {
            await api.updateAsync(listId.value, { planned_shop_date: next });
            await refreshAllQuietly();
            plannedDateOpen.value = false;
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not save shop day.',
                caption: toastCaption(err),
            });
        }
    }

    async function clearPlannedDate() {
        if (!detail.value) return;
        try {
            await api.updateAsync(listId.value, { planned_shop_date: null });
            await refreshAllQuietly();
            plannedDateOpen.value = false;
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not clear shop day.',
                caption: toastCaption(err),
            });
        }
    }

    // ── Lists rail / mobile dropdown (UX-v2 §3) ──────────────────────
    // One continuum, server-ordered by effective date ascending (R-003:
    // the ordering rule lives in get_shopping_lists.py, not here) — the
    // client renders the payload order verbatim.
    const newListOpen = ref(false);
    const putAwayOpen = ref(false);

    /** How many finished lists the picker keeps inline. The rest go behind
     *  "See older" — a household accretes done lists forever (this dev seed
     *  alone carries 26), and a picker you have to scroll past a year of
     *  history to reach today's list is not a picker. */
    const RECENT_DONE_LIMIT = 5;

    const doneSummaries = computed(() =>
        store.summaries.filter((s) => s.status === 'done'),
    );

    /** Done lists *not* shown inline — the "See older" modal's contents. The
     *  server orders **descending** by effective date (newest first, 2026-08-28),
     *  so the most recent finished lists are the head of this slice and the
     *  older ones are everything after it. */
    const olderDoneSummaries = computed(() =>
        doneSummaries.value.slice(RECENT_DONE_LIMIT),
    );

    /** The picker's inline set: every draft, every list being shopped, and the
     *  most recent few finished ones — still in the server's own order, so the
     *  date continuum reads the same as it always did, just shorter. The list
     *  currently open is always included even if it's an old one, so opening a
     *  list from "See older" doesn't leave the picker pointing at nothing. */
    const railEntries = computed(() => {
        const olderIds = new Set(
            olderDoneSummaries.value.map((s) => s.shopping_list_id),
        );
        return store.summaries.filter(
            (s) => !olderIds.has(s.shopping_list_id) || s.shopping_list_id === listId.value,
        );
    });

    // ── "See older" — every finished list, searchable ────────────────
    const olderListsOpen = ref(false);
    const olderFilter = ref('');

    const filteredOlderSummaries = computed(() => {
        const needle = olderFilter.value.trim().toLowerCase();
        if (!needle) return olderDoneSummaries.value;
        return olderDoneSummaries.value.filter(
            (s) => s.display_name.toLowerCase().includes(needle),
        );
    });

    function openOlderLists() {
        olderFilter.value = '';
        olderListsOpen.value = true;
    }
    const currentSummary = computed(() =>
        store.summaries.find((s) => s.shopping_list_id === listId.value) ?? null,
    );

    /** The picker reads the rail's summary while the next list's detail is in
     *  flight (`load` clears `detail`), so switching lists shows the target's
     *  glyph and name straight away instead of flashing a stand-in. */
    const pickerIcon = computed(() => {
        const status = detail.value?.status ?? currentSummary.value?.status;
        return status ? listStatusIcon(status) : ICONS.list_alt;
    });
    const pickerLabel = computed(
        () => detail.value?.display_name ?? currentSummary.value?.display_name ?? 'Pick a list',
    );

    // No auto-scroll-to-selection any more: the rail is a plain list of about
    // eight rows that fits without scrolling, so there is nothing to scroll to.

    function switchToList(id: string) {
        if (id === listId.value) return;
        void router.push(`/shopping-lists/${id}`);
    }

    function onListCreated({ listId: newId }: { listId: string }) {
        void store.refreshAsync();
        switchToList(newId);
    }

    async function deleteSummary(s: ShoppingListSummary) {
        const ok = await confirm({
            title: `Delete "${s.display_name}"?`,
            message: 'This permanently removes the list and all its items.',
            okLabel: 'Delete',
            destructive: true,
        });
        if (!ok) return;
        try {
            await api.deleteAsync(s.shopping_list_id);
            await store.refreshAsync();
            // If we deleted the list we're currently viewing, bounce to the
            // landing — it'll pick the next sensible target.
            if (s.shopping_list_id === listId.value) {
                void router.replace('/shopping-lists');
                return;
            }
            $q.notify({
                type: 'positive',
                message: 'List deleted.',
            });
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not delete.',
                caption: toastCaption(err),
            });
        }
    }

    function onDeleteCurrentList() {
        if (currentSummary.value) void deleteSummary(currentSummary.value);
    }

    async function load() {
        if (!listId.value) return;
        loading.value = true;
        loadError.value = null;
        // Clear the previous list's data so the user sees a loading spinner
        // — not stale rows from the list they navigated away from —
        // while the new list's detail is in flight.
        detail.value = null;
        try {
            detail.value = await api.getDetailAsync(listId.value);
            primeVerdicts(listId.value);
        } catch (err) {
            loadError.value = `Could not load list: ${describeApiError(err)}`;
        } finally {
            loading.value = false;
        }
        // refresh the trim-to-budget banner state as soon as the
        // list is available. Own try/catch inside; failures never bubble.
        void refreshTrimStatus();
    }

    /** Re-read the list without blanking the page.
     *
     *  `load()` deliberately nulls `detail` so switching lists shows a skeleton
     *  rather than the previous list's rows — right for a navigation, wrong for
     *  a refresh: mid-shop it would flash the whole page to a skeleton on every
     *  tick. This exists for the "I already painted the change optimistically,
     *  now reconcile the server-owned aggregates" case, and it stays silent on
     *  failure because the optimistic state is still the user's best guess and
     *  the next action will re-read anyway. */
    async function refreshDetailQuietly(): Promise<void> {
        if (!listId.value) return;
        try {
            detail.value = await api.getDetailAsync(listId.value);
        } catch {
            // Intentionally silent — see above.
        }
    }

    // B6 — one request for the whole list's verdicts, marked in-flight before
    // the lines paint so each `BuyVerdictBadgeInline` reads the shared answer
    // instead of asking for its own. Called synchronously after `detail` is
    // assigned (Vue renders on the next tick, so the marks land first).
    // Fire-and-forget: `primeBuyVerdicts` swallows its own failure, and a list
    // that can't fetch verdicts still shows its items.
    function primeVerdicts(shoppingListId: string): void {
        if (!buyVerdictEnabled.value) return;
        const ids = (detail.value?.lines ?? [])
            .map((line) => line.stock_item_id)
            .filter((id): id is string => !!id);
        void primeBuyVerdicts(
            ids,
            () => new BuyVerdictApiService().getForListAsync(shoppingListId),
        );
    }

    async function refreshAll() {
        // Refresh detail + the store-level summaries/membership in
        // parallel so the rail order, next-up marker and cart-button
        // state elsewhere stay accurate.
        await Promise.all([load(), store.refreshAsync()]);
    }

    /** The quiet counterpart to `refreshAll()`, for edits to the list *itself*.
     *
     *  It re-reads everything a list-level edit can move — the detail, the
     *  rail's names and ordering, and the trim-to-budget state (the shop date
     *  decides which budget period applies) — but goes through
     *  `refreshDetailQuietly()` rather than `load()`.
     *
     *  That is the whole difference, and it matters: `load()` nulls `detail`
     *  first so a *navigation* shows a skeleton instead of the list you just
     *  left. Renaming a list or setting its shop day is not a navigation — you
     *  are still looking at the list you meant to look at — so blanking it
     *  flashed the entire page through the skeleton branch and back on every
     *  save (the 2026-08-29 *"why does the whole page refresh when I pick a
     *  shop date?"* report). */
    async function refreshAllQuietly(): Promise<void> {
        await Promise.all([refreshDetailQuietly(), store.refreshAsync()]);
        void refreshTrimStatus();
    }

    async function onPutAwayAssigned(): Promise<void> {
        // The dialog just persisted a new stock_location for one line's
        // item. Reload the list detail so the line's breadcrumb + group
        // membership move with it — the dialog re-reads via v-model on
        // detail.lines.
        await load();
    }

    // ── Name editing (UX-v2 §5: clearable custom name) ────────────────
    // The fallback chain (custom > shop day > created) is server-owned
    // (`display_name`); this only edits the raw custom `name`.
    const dateFallbackName = computed(() => {
        const d = detail.value?.planned_shop_date;
        if (d) return formatDate(`${d}T00:00:00`);
        return detail.value ? formatDate(detail.value.created_at) : '';
    });

    function startNameEdit() {
        nameDraft.value = detail.value?.name ?? '';
        editingName.value = true;
    }

    function cancelName() {
        editingName.value = false;
    }

    async function saveName() {
        if (!detail.value) return;
        const next = (nameDraft.value ?? '').trim();
        const current = detail.value.name ?? '';
        if (next === current) {
            editingName.value = false;
            return;
        }
        try {
            // Blank = clear the custom name (explicit null on the wire); the
            // list re-labels itself from its dates.
            await api.updateAsync(listId.value, { name: next === '' ? null : next });
            await refreshAllQuietly();
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not rename.',
                caption: toastCaption(err),
            });
        } finally {
            editingName.value = false;
        }
    }

    function onOpenQuickAdd() {
        // Pre-target this list so the sheet skips its list picker default.
        openQuickAdd({ listId: listId.value });
    }

    // ── Keyboard shortcuts ────────────────────────────────────────────
    // Focus walks render order, so it reads from the same sectioned list the
    // template draws — including the run face's hidden-when-ticked filtering,
    // which keeps arrow-key focus from landing on a row that isn't on screen.
    const orderedLines = sectionOrderedLines;
    const focusedLineId = ref<string | null>(null);
    // Shop-mode merge (M14): 'u' unticks the most recent tick from this
    // session — the in-store "oops, wrong item" key.
    const recentTickStack = ref<string[]>([]);

    function moveLineFocus(delta: number) {
        const lines = orderedLines.value;
        if (lines.length === 0) return;
        const current = lines.findIndex((l) => l.line_id === focusedLineId.value);
        const next = current < 0 ? 0 : Math.max(0, Math.min(lines.length - 1, current + delta));
        focusedLineId.value = lines[next]?.line_id ?? null;
    }
    // Both keys are shop-mode only. They used to guard on 'done', which let
    // them tick a draft line from the keyboard — a back door into the state
    // the plan face no longer has a control for.
    function tickFocusedLine() {
        if (detail.value?.status !== 'shopping') return;
        const line = orderedLines.value.find((l) => l.line_id === focusedLineId.value);
        if (line) void onToggleTicked(line.line_id, !line.is_ticked);
    }
    function untickLastTicked() {
        if (detail.value?.status !== 'shopping') return;
        while (recentTickStack.value.length > 0) {
            const lineId = recentTickStack.value.pop()!;
            const line = detail.value?.lines.find((l) => l.line_id === lineId);
            if (line?.is_ticked) {
                void onToggleTicked(lineId, false);
                return;
            }
        }
    }

    useShortcut([
        { keys: 'n', scope: 'Shopping list', description: 'Add an item', handler: onOpenQuickAdd },
        { keys: 'space', scope: 'Shopping list', description: 'Tick / untick the focused line', handler: tickFocusedLine },
        { keys: 'u', scope: 'Shopping list', description: 'Untick the last item you ticked', handler: untickLastTicked },
        { keys: 'arrowdown', scope: 'Shopping list', description: 'Focus next line', handler: () => moveLineFocus(1) },
        { keys: 'arrowup', scope: 'Shopping list', description: 'Focus previous line', handler: () => moveLineFocus(-1) },
    ]);

    // QuickAddSheet writes via shoppingListStore.refreshAsync but the
    // per-list detail isn't part of that refresh — re-read it locally
    // whenever the sheet closes so a freshly-added line shows up.
    //
    // Quietly (2026-09-17). This was `load()`, which nulls `detail` so a
    // *navigation* shows a skeleton instead of the list you just left — so
    // adding an item flashed the whole page through the skeleton branch and
    // the `FadeTransition` and back, for a change that adds one row to a list
    // already on screen. That is the same defect `refreshAllQuietly()` was
    // written for in August, when picking a shop day did it; the fix just
    // never reached the sheet next to it.
    watch(quickAddOpen, (open, wasOpen) => {
        if (wasOpen && !open) void refreshAllQuietly();
    });

    // react to URL list-id changes. The merged overview-into-
    // detail design means switching lists (rail, dropdown, rail kebab)
    // only changes `route.params.id` without unmounting this component,
    // so `onMounted` doesn't re-fire.
    watch(listId, () => { void load(); });

    // ── FU-653: Dora's inferred suggestions ───────────────────────────
    // No dismissal state any more (2026-09-17) — the strip is either something
    // the household opted into or it isn't rendered at all, and a session-only
    // hide was a third state in between that nothing remembered.
    const addingSuggestionId = ref<string | null>(null);

    const visibleSuggestions = computed<InferredSuggestion[]>(
        () => detail.value?.inferred_suggestions ?? [],
    );

    async function onAddSuggestion(suggestion: InferredSuggestion) {
        addingSuggestionId.value = suggestion.stock_item_id;
        try {
            await api.addLineAsync(listId.value, {
                stock_item_id: suggestion.stock_item_id,
            });
            // Quiet — see `onRemoveLine`; adding a suggested line is an in-place
            // edit, not a navigation.
            await refreshAllQuietly();
            $q.notify({
                type: 'positive',
                message: `Added ${suggestion.name}.`,
            });
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: `Could not add ${suggestion.name}.`,
                caption: toastCaption(err),
            });
        } finally {
            addingSuggestionId.value = null;
        }
    }

    /** @returns whether the tick reached the server — the run face only
     *  promises an undo for a change that actually landed. */
    async function onToggleTicked(lineId: string, value: boolean): Promise<boolean> {
        // Optimistic flip so the checkbox feels instant; if the request
        // fails we re-load the canonical state. Offline is read-only
        // (2026-08-23), so a network failure is a plain failure here — the
        // tick is undone and said so, rather than being buffered and
        // promised.
        const line = detail.value?.lines.find((l) => l.line_id === lineId);
        if (line) line.is_ticked = value;
        if (value) recentTickStack.value.push(lineId);
        try {
            await api.updateLineAsync(listId.value, lineId, { is_ticked: value });
            // The counts are ours to flip optimistically, but the money isn't:
            // `remaining_price` and the store breakdown are server-owned
            // aggregates (R-003), and the run face's footer puts "Remaining"
            // in front of the user on every single tick. Re-read rather than
            // re-derive — the optimistic flip above already paid for the feel.
            await refreshDetailQuietly();
            return true;
        } catch (err) {
            await load();
            $q.notify({
                type: 'negative',
                message: 'Could not update line.',
                caption: toastCaption(err),
            });
            return false;
        }
    }

    /** Run-face tick. One gesture, and the row leaves the list — so the undo
     *  has to travel with it. The toast is the only place a mis-tap is
     *  recoverable now that the row is gone from the section, and it reuses
     *  the same untick path as the `u` shortcut rather than a second one.
     *
     *  It waits for the tick to land before offering the undo: on a failure
     *  `onToggleTicked` reloads and says so, and a cheerful "Picked X · UNDO"
     *  sitting next to "Could not update line" would be offering to undo
     *  something that never happened. */
    async function onRunTick(line: ShoppingListLine) {
        if (line.is_ticked) return;
        const ok = await onToggleTicked(line.line_id, true);
        if (!ok) return;
        $q.notify({
            type: 'positive',
            position: 'bottom',
            timeout: 4000,
            message: `Picked ${line.stock_item_name}`,
            actions: [{
                label: 'Undo',
                color: 'white',
                handler: () => { void onToggleTicked(line.line_id, false); },
            }],
        });
    }

    /** Put a picked line back, from the run face's Picked section. No undo
     *  toast: this *is* the undo, and the row reappears in its section where
     *  you can see it land. */
    async function onRunUntick(line: ShoppingListLine) {
        if (!line.is_ticked) return;
        await onToggleTicked(line.line_id, false);
    }

    // ── P2-02: actual price + merchant override ─────────────────────────
    // A small popover sits behind the price button on each line. Users tap
    // it mid-shop or at finish time to type what the till actually charged
    // and (optionally) confirm which merchant they bought from. Both flow
    // into the assistant's purchase-history stats.
    const priceEditorDraft = reactive<{
        line_id: string | null;
        price: number | null;
        store_id: string | null;
        quantity: number | null;
    }>({ line_id: null, price: null, store_id: null, quantity: null });

    function onOpenPriceEditor(line: ShoppingListLine) {
        priceEditorDraft.line_id = line.line_id;
        // Seed with the existing override, else the server-resolved prefill
        // (D3: prior receipt, else chosen offer — source-labelled), so the
        // common case is "confirm one number".
        // The server's money ladder (actual → picked offer → what you last
        // paid) already names the best number, so the sheet reads it rather
        // than re-ranking. The old `?? chosenOfferFor(line)` fallback let the
        // *cheapest* offer prefill a price nobody picked, which 2026-09-17 had
        // ruled out everywhere else.
        priceEditorDraft.price = line.estimated_unit_price ?? null;
        // Seed from the server-resolved store, not just the offer's: since the
        // picker below widened to the resolved / last-paid stores, seeding only
        // from an offer left a products-free user looking at an option list with
        // nothing selected.
        // Prefill chain, per the store ladder: bought-from wins, else whatever
        // the ladder resolved (which is now the list's planned store before the
        // item's usual one), else the offer's. Each rung is a *default* for the
        // next — nothing is written back up the chain, so buying somewhere once
        // never rewrites where you plan or usually shop.
        priceEditorDraft.store_id =
            line.purchased_store_id
            ?? line.resolved_store_id
            ?? chosenOfferFor(line)?.store_id
            ?? null;
        priceEditorDraft.quantity = line.quantity ?? 1;
    }

    /** Every store the household has, for the plan face's "where do you plan to
     *  buy this" picker.
     *
     *  Deliberately *not* `storeOptionsFor` (below), which lists only stores
     *  already touching the line — right for "where did you buy it", since the
     *  answer is almost always one of them, and wrong here: planning to shop
     *  somewhere new is the whole point of the control, and a picker that can't
     *  name Aldi until you have already bought there is useless. R-016 lazy
     *  hydration, so an install that never opens this control pays nothing. */
    const storesStore = useStoresStore();
    const { openLogPrice } = useLogPrice();
    const allStoreOptions = computed(() =>
        storesStore.stores.map((s) => ({ value: s.store_id, label: s.name })),
    );

    /** The store options for one line: every store, with the item's standing
     *  choice marked.
     *
     *  The empty option is **always "Any store"** (2026-09-17). It used to
     *  rename itself to "<resolved store> (default)", which is exactly the
     *  confusion the owner reported: the option that means *no store* was
     *  displaying a store's name, so "Any store" and "the usual store" looked
     *  like one setting with two names. The ladder still resolves a store for a
     *  line that hasn't chosen one — but a line added for an item with a usual
     *  store now carries it as a real `planned_store_id` (set server-side at
     *  add time), so the picker has something true to show instead of
     *  describing an inheritance. "(usual)" marks the standing choice in the
     *  list, where it is a fact about the item rather than about this line. */
    function plannedStoreOptionsFor(line: ShoppingListLine) {
        return allStoreOptions.value.map((o) => ({
            ...o,
            // `name` for the row's caption, `label` for the menu — see the
            // row's `storeLabel`.
            name: o.label,
            label: o.value === line.usual_store_id ? `${o.label} (usual)` : o.label,
        }));
    }

    /** Writes the plan face's target store. Optimistic with a rollback, like
     *  the other row mutations — and it refetches, because the store ladder is
     *  server-owned (R-003): changing this rung can move the line into a
     *  different section under Order-by → Store, and only the server knows
     *  what it resolved to. */
    async function onPlannedStoreChange(line: ShoppingListLine, value: string | null) {
        const previousId = line.planned_store_id;
        const previousName = line.planned_store_name;
        line.planned_store_id = value;
        line.planned_store_name =
            allStoreOptions.value.find((o) => o.value === value)?.label ?? null;
        try {
            await api.updateLineAsync(listId.value, line.line_id, value
                ? { planned_store_id: value }
                : { clear_planned_store: true });
            await refreshDetailQuietly();
        } catch (err) {
            line.planned_store_id = previousId;
            line.planned_store_name = previousName;
            $q.notify({
                type: 'negative',
                message: 'Could not set the store.',
                caption: toastCaption(err),
            });
        }
    }

    function storeOptionsFor(line: ShoppingListLine) {
        const seen = new Map<string, string>();
        // Offers are the power-user case. Someone who has never linked a
        // product still has a resolved store (their usual, or where they last
        // bought it), and without these the picker was empty for them — which
        // made "Bought from" invisible on exactly the installs the money ladder
        // was rebuilt to serve.
        const candidates: [string | null, string | null][] = [
            [line.purchased_store_id, line.purchased_store_name],
            [line.resolved_store_id, line.resolved_store_name],
            [line.last_paid_store_id, line.last_paid_store_name],
            ...line.offers.map(
                (o) => [o.store_id, o.store_name] as [string | null, string | null]
            ),
        ];
        for (const [id, name] of candidates) {
            if (id && name && !seen.has(id)) seen.set(id, name);
        }
        return Array.from(seen, ([value, label]) => ({ value, label }));
    }

    async function savePriceEditor(line: ShoppingListLine) {
        if (priceEditorDraft.line_id !== line.line_id) return;
        const nextPrice = priceEditorDraft.price;
        const nextStore = priceEditorDraft.store_id;
        // Empty/zero/negative input clears the *price* rather than storing a
        // meaningless number. The backend rejects negatives anyway; this saves
        // the round-trip.
        if (nextPrice == null || Number.isNaN(nextPrice) || nextPrice <= 0) {
            // ...but only the price. This used to call `clearPriceOverride`,
            // which clears the price *and* the store — so picking "Bought
            // from" on a line you hadn't priced saved nothing at all, and the
            // row stayed in its old bucket under Order-by → Store. That is
            // FU-769, reported in August as a refresh gap and confirmed live
            // on 2026-09-17 to be this: the store never reached the server.
            // Two fields, two decisions; a blank price is not an instruction
            // about the store.
            if (nextStore) {
                await saveStoreOnly(line, nextStore);
            } else {
                await clearPriceOverride(line);
            }
            return;
        }
        await writeLinePurchase(
            line,
            { price: nextPrice, storeId: nextStore ?? null },
            {
                actual_unit_price: nextPrice,
                ...(nextStore
                    ? { purchased_store_id: nextStore }
                    : { clear_purchased_store: true }),
            },
            'Could not save the price.',
        );
    }

    /** The one optimistic write for a line's price and bought-from store:
     *  show the new pair, send `command`, and put the old pair back (with
     *  `failMessage`) if the server refuses (03-R19). */
    async function writeLinePurchase(
        line: ShoppingListLine,
        next: { price: number | null; storeId: string | null },
        command: UpdateLineCommand,
        failMessage: string,
    ) {
        const previous = {
            price: line.actual_unit_price,
            storeId: line.purchased_store_id,
            storeName: line.purchased_store_name,
        };
        line.actual_unit_price = next.price;
        line.purchased_store_id = next.storeId;
        line.purchased_store_name = next.storeId
            ? storeOptionsFor(line).find((o) => o.value === next.storeId)?.label ?? null
            : null;
        try {
            await api.updateLineAsync(listId.value, line.line_id, command);
        } catch (err) {
            line.actual_unit_price = previous.price;
            line.purchased_store_id = previous.storeId;
            line.purchased_store_name = previous.storeName;
            $q.notify({ type: 'negative', message: failMessage, caption: toastCaption(err) });
        }
    }

    // ── Price capture sheet (run + receipt faces) ───────────────────────
    // Same draft and the same save path as the plan face's popover — only the
    // container differs, because the ergonomics do. Both faces then reload:
    // the money ladder and the store breakdown are server-owned (R-003), so
    // after a price lands the client asks for the new numbers rather than
    // guessing which rung the server would now pick.
    const priceSheetLine = ref<ShoppingListLine | null>(null);
    const priceSheetOpen = ref(false);

    function openPriceSheet(line: ShoppingListLine) {
        onOpenPriceEditor(line);
        priceSheetLine.value = line;
        priceSheetOpen.value = true;
    }

    async function savePriceSheet() {
        const line = priceSheetLine.value;
        if (!line) return;
        priceSheetOpen.value = false;
        // Quantity first and separately: it is the one field here that is not
        // part of the price/store pair, and `savePriceEditor` short-circuits to
        // `clearPriceOverride` when the price is blank — which would silently
        // drop a quantity edit made on a line the user never priced.
        const nextQuantity = priceEditorDraft.quantity;
        if (nextQuantity != null && nextQuantity !== (line.quantity ?? 1)) {
            await setLineQuantity(line, nextQuantity);
        }
        await savePriceEditor(line);
        await refreshDetailQuietly();
    }

    /** Record where a line was bought without claiming what it cost.
     *
     *  The honest state for "I picked this up at Aldi but didn't note the
     *  price": the store is a fact the user gave, the price is one they
     *  didn't, and a price the user never typed must not survive as an
     *  override. Optimistic like its siblings, and rolled back the same way.
     */
    async function saveStoreOnly(line: ShoppingListLine, storeId: string) {
        await writeLinePurchase(
            line,
            { price: null, storeId },
            { clear_actual_unit_price: true, purchased_store_id: storeId },
            'Could not save the store.',
        );
    }

    /** The line's offers, only while they can still be acted on. A receipt is
     *  a record: what a shop is advertising today has nothing to say about a
     *  trip that already happened. */
    const priceSheetOffers = computed(() => {
        if (!priceSheetLine.value || detail.value?.status !== 'shopping') return [];
        return priceSheetLine.value.offers.filter((o) => o.price_now != null);
    });

    /** Only once there is more than one of them — at quantity 1 the line total
     *  and the price each are the same number, and printing it twice explains
     *  nothing. */
    const priceSheetLineTotal = computed(() => {
        const price = priceEditorDraft.price;
        const qty = priceEditorDraft.quantity ?? 1;
        if (price == null || Number.isNaN(price) || price <= 0 || qty <= 1) return null;
        return fmtMoney(price * qty);
    });

    function useOfferPrice(offer: LineProductOffer): void {
        if (offer.price_now == null) return;
        priceEditorDraft.price = offer.price_now;
        // The offer names a store as surely as it names a price, and the two
        // arriving together is the point — you are recording one purchase.
        priceEditorDraft.store_id = offer.store_id;
    }

    async function clearPriceSheet() {
        const line = priceSheetLine.value;
        if (!line) return;
        priceSheetOpen.value = false;
        await clearPriceOverride(line);
        await refreshDetailQuietly();
    }

    async function clearPriceOverride(line: ShoppingListLine) {
        if (line.actual_unit_price == null && line.purchased_store_id == null) return;
        await writeLinePurchase(
            line,
            { price: null, storeId: null },
            { clear_actual_unit_price: true, clear_purchased_store: true },
            'Could not clear the price.',
        );
    }

    async function setLineQuantity(line: ShoppingListLine, next: number | null) {
        const previous = line.quantity;
        if (previous === next) return;
        line.quantity = next;
        try {
            await api.updateLineAsync(listId.value, line.line_id, { quantity: next });
        } catch (err) {
            line.quantity = previous;
            $q.notify({
                type: 'negative',
                message: 'Could not update quantity.',
                caption: toastCaption(err),
            });
        }
    }

    async function onAdjustQuantity(line: ShoppingListLine, delta: number) {
        const current = line.quantity ?? 1;
        const next = Math.max(1, current + delta);
        await setLineQuantity(line, next);
        // On the receipt face the quantity is part of the money: it multiplies
        // the line total, the store split and the harvested observation the
        // server has just rewritten. Re-read rather than re-derive (R-003).
        if (receiptFace.value) await refreshDetailQuietly();
    }

    async function onPickHint(lineId: string, preferredBuyId: string | null) {
        const line = detail.value?.lines.find((l) => l.line_id === lineId);
        if (!line) return;
        const previous = line.preferred_buy_id ?? null;
        // Toggle: re-picking the chosen hint clears it.
        const next = preferredBuyId === previous ? null : preferredBuyId;
        line.preferred_buy_id = next;
        try {
            if (next === null) {
                await api.updateLineAsync(listId.value, lineId, { clear_preferred_buy: true });
            } else {
                await api.updateLineAsync(listId.value, lineId, { preferred_buy_id: next });
            }
        } catch (err) {
            line.preferred_buy_id = previous;
            $q.notify({
                type: 'negative',
                message: 'Could not set the hint.',
                caption: toastCaption(err),
            });
        }
    }

    async function onPickOffer(lineId: string, productId: string) {
        const line = detail.value?.lines.find((l) => l.line_id === lineId);
        if (!line) return;
        const previous = line.selected_product_id;
        // Toggle: clicking the chosen offer clears the selection (falls
        // back to "cheapest" auto-selection).
        const next = previous === productId ? null : productId;
        line.selected_product_id = next;
        // Sync `is_selected` flags on the in-memory offers so chips repaint
        // without waiting for the round-trip.
        for (const offer of line.offers) {
            offer.is_selected = offer.product_id === next;
        }
        try {
            if (next === null) {
                await api.updateLineAsync(listId.value, lineId, {
                    clear_selected_product: true,
                });
            } else {
                await api.updateLineAsync(listId.value, lineId, {
                    selected_product_id: next,
                });
            }
            // Picking an offer moves the line to the offer's store and prices
            // its estimate; un-picking puts the old figure back. Both are the
            // server's ladders (R-003), so re-read rather than guess.
            await refreshDetailQuietly();
        } catch (err) {
            line.selected_product_id = previous;
            $q.notify({
                type: 'negative',
                message: 'Could not set offer.',
                caption: toastCaption(err),
            });
        }
    }

    // buy-verdict action for an in-shop line.
    // - `remove_from_list` targets THIS specific line (line-level intent).
    // - `mark_stocked` closes FU-454: routes through the shared
    //   `useBuyVerdictActions.markStocked` seam so the item flips to the
    //   Well-Stocked band and the verdict cache refreshes.
    // - `add_to_list` / `skip` / `none` are no-ops here — the line is
    //   already on this list; no meaningful mutation.
    const verdictActions = useBuyVerdictActions();
    async function onLineVerdictAction(
        line: ShoppingListLine,
        kind: 'add_to_list' | 'skip' | 'mark_stocked'
            | 'remove_from_list' | 'none',
    ) {
        if (kind === 'remove_from_list') {
            await onRemoveLine(line.line_id);
            if (line.stock_item_id) invalidateBuyVerdict(line.stock_item_id);
            return;
        }
        if (kind === 'mark_stocked' && line.stock_item_id) {
            await verdictActions.markStocked(line.stock_item_id);
            return;
        }
        // `add_to_list` / `skip` / `none` — no mutation. Silent by design.
    }

    async function onRemoveLine(lineId: string) {
        const before = detail.value?.lines.find((l) => l.line_id === lineId);

        // removing a product-only line (no
        // stock_item_id) prompts to also remove the *linked* stock-item
        // line, if one is also on this list. The user added the product
        // intent; removing it usually implies the stock-item placeholder
        // goes too, but they may want to keep the generic line.
        let alsoRemoveStockItemId: string | null = null;
        if (before && !before.stock_item_id && before.product_id) {
            const linkedStockItemId = productStore.products?.find(
                (p) => p.product_id === before.product_id,
            )?.linked_stock_item_id ?? null;
            if (linkedStockItemId) {
                const parentLine = detail.value?.lines.find(
                    (l) =>
                        l.stock_item_id === linkedStockItemId
                        && l.line_id !== lineId,
                );
                if (parentLine) {
                    // Yes → remove both; No/dismiss → just the product. The
                    // product line is going regardless (the user already
                    // clicked Remove); the prompt is purely about whether the
                    // generic stock-item placeholder rides along.
                    const removeBoth = await confirm({
                        title: 'Also remove the stock item?',
                        message: `${parentLine.stock_item_name} is on this list as its own line. Remove it too?`,
                        okLabel: 'Yes, remove both',
                        cancelLabel: 'No, just the product',
                    });
                    if (removeBoth) alsoRemoveStockItemId = linkedStockItemId;
                }
            }
        }

        try {
            await api.deleteLineAsync(listId.value, lineId);
            if (alsoRemoveStockItemId) {
                await api.removeByStockItemFromListAsync(
                    listId.value,
                    alsoRemoveStockItemId,
                );
            }
            // Quiet, not `refreshAll()`: removing a line is an edit to the list
            // you are already looking at, not a navigation, so blanking `detail`
            // flashed the whole page through the skeleton on every remove
            // (owner, 2026-09-04 — same defect as the 08-29 shop-date report).
            await refreshAllQuietly();
            // UX-v2 §12 Q4: no undo toast — re-adding is one quick-add away,
            // and the app-wide undo posture is under review (FU-163).
            if (before) {
                $q.notify({
                    type: 'positive',
                    message: `Removed ${before.stock_item_name}.`,
                });
            }
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not remove line.',
                caption: toastCaption(err),
            });
        }
    }

    // ── Detail-page extra actions ─────────────────────────────────────

    const otherActiveLists = computed(() =>
        store.summaries.filter(
            (s) => s.status !== 'done' && s.shopping_list_id !== listId.value
        )
    );

    // Print pulls from the shared composable so every caller stays in
    // lockstep on URL shape. (CSV export was removed app-wide — §12 Q1.)
    const exportActions = useShoppingListExport();

    function onPrint() {
        exportActions.openPrintView(listId.value);
    }

    /** Undo for "I pressed Start shopping by accident" (2026-09-17).
     *
     *  Names the cost up front rather than in a toast afterwards: a draft has
     *  no tick model, so going back clears every tick, and the count is the one
     *  fact that decides whether the user wants to. With nothing ticked the
     *  dialog is a plain confirmation instead of a warning about nothing.
     */
    async function onBackToDraft() {
        const ticked = detail.value?.lines.filter((l) => l.is_ticked).length ?? 0;
        const ok = await confirm({
            title: 'Back to draft?',
            message: ticked > 0
                ? `This list goes back to being a draft, and the ${ticked} item${ticked === 1 ? '' : 's'} you've ticked off ${ticked === 1 ? 'is' : 'are'} unticked. Nothing else changes.`
                : 'This list goes back to being a draft. Nothing else changes.',
            okLabel: 'Back to draft',
        });
        if (!ok) return;
        togglingProgress.value = true;
        try {
            await api.backToDraftAsync(listId.value);
            await refreshAllQuietly();
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not go back to draft.',
                caption: toastCaption(err),
            });
        } finally {
            togglingProgress.value = false;
        }
    }

    async function onClearAll() {
        const ok = await confirm({
            title: 'Clear all items?',
            message: 'Every line on this list will be removed. The list stays.',
            okLabel: 'Clear',
            destructive: true,
        });
        if (!ok) return;
        try {
            const result = await api.clearListAsync(listId.value);
            // Quiet — see `onRemoveLine`. The list stays; only its lines go.
            await refreshAllQuietly();
            $q.notify({
                type: 'positive',
                message: `Cleared ${result.removed_count} line${result.removed_count === 1 ? '' : 's'}.`,
            });
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not clear.',
                caption: toastCaption(err),
            });
        }
    }

    async function onSaveAsTemplate() {
        if (!detail.value) return;
        // Ask for a name and whether to include ticked items.
        const name = await prompt({
            title: 'Save as template',
            message: 'Snapshots the items on this list as a reusable template. ' +
                'Quantities and selected merchant offers are reset on each use.',
            initial: `Template from ${detail.value.display_name}`,
            isValid: (val: string) => val.trim().length > 0,
        });
        if (!name) return;
        // Include ticked items only when the list isn't archived and has
        // them — otherwise the default ("only unticked") is fine.
        const ticked = detail.value.lines.filter((l) => l.is_ticked).length;
        let includeTicked = false;
        if (ticked > 0) {
            includeTicked = await confirm({
                title: `Include ${ticked} ticked item${ticked === 1 ? '' : 's'}?`,
                message: 'Ticked items are usually one-offs.',
                okLabel: 'Include ticked',
                cancelLabel: 'Skip ticked',
            });
        }
        try {
            const result = await templateApi.snapshotFromListAsync(listId.value, {
                name,
                include_ticked: includeTicked,
            });
            $q.notify({
                type: 'positive',
                message: `Saved as template with ${result.line_count} item${
                    result.line_count === 1 ? '' : 's'
                }.`,
                actions: [
                    {
                        label: 'Open',
                        color: 'white',
                        handler: () => { void router.push('/shopping-lists/templates'); },
                    },
                ],
            });
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not save template.',
                caption: toastCaption(err),
            });
        }
    }

    // ── Moving items to another list ──────────────────────────────────
    // Two entry points, one flow (2026-08-26 feedback). The standalone
    // "Move unticked to another list" hidden in the More menu is gone: you
    // now either select exactly what you want moved (bulk bar → "Move to
    // list…") or you're told about the leftovers on the way out of the shop
    // (the finish dialog). Both land here.

    /** Quasar's built-in radio `options` dialog rather than a hand-rolled
     *  picker — the user is choosing one of a short list of names. Resolves
     *  null on cancel/dismiss. */
    // ── Receipt attachments (FU-334) ────────────────────────────────────
    // Pure record-keeping: attach 1..N receipt photos to a `shopping` or
    // `done` list; tap to zoom; trash to remove. No OCR. ImageSourcePicker
    // owns the source-pick UX (Take photo vs Choose image) AND the
    // `processImageFile` chokepoint (R-003) — this handler just receives
    // a `ProcessedImage` and POSTs the data URL.
    const attachmentUploading = ref(false);
    const attachmentZoomId = ref<string | null>(null);

    const attachmentSectionVisible = computed(
        () => !!detail.value && detail.value.status !== 'draft',
    );

    function attachmentSrc(attachmentId: string): string {
        if (!listId.value) return '';
        return shoppingListAttachmentUrl(listId.value, attachmentId);
    }

    async function onAttachmentPicked(image: ProcessedImage) {
        if (!detail.value || !listId.value) return;
        attachmentUploading.value = true;
        try {
            await api.addAttachmentAsync(listId.value, image.dataUrl);
            // Re-fetch to pick up the server-assigned id + sequence.
            await load();
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not attach receipt.',
                caption: toastCaption(err),
            });
        } finally {
            attachmentUploading.value = false;
        }
    }

    function onAttachmentError(message: string) {
        // ImageSourcePicker has already surfaced the inline error caption;
        // mirror it as a toast so the failure is visible even if the user
        // scrolled past the picker.
        $q.notify({
            type: 'negative',
            message: 'Could not read that image.',
            caption: message,
        });
    }

    async function onDeleteAttachment(attachmentId: string) {
        if (!detail.value) return;
        try {
            await api.deleteAttachmentAsync(listId.value, attachmentId);
            // Optimistic local removal so the strip updates without a re-fetch
            // round-trip; load() runs anyway to stay authoritative.
            detail.value.attachments = (detail.value.attachments ?? []).filter(
                (a) => a.attachment_id !== attachmentId,
            );
            if (attachmentZoomId.value === attachmentId) {
                attachmentZoomId.value = null;
            }
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not remove receipt.',
                caption: toastCaption(err),
            });
            await load();
        }
    }

    onMounted(async () => {
        await stockItemStore.ensureLoadedAsync();
        // Levels power the inline StockLevelDot on shopping-list rows.
        await stockLevelStore.ensureLoadedAsync();
        // needed to resolve a product-only line's
        // linked stock item for the rule-4 modal and for nested-display
        // grouping.
        await productStore.ensureLoadedAsync();
        // Stores power the plan face's "where do you plan to buy this" picker.
        await storesStore.ensureLoadedAsync();
        await store.ensureLoadedAsync();
        await load();
    });
</script>

<style scoped>
    /* The title, the name input, the status pill, the meta row, the "Order by"
       bar and the mid-shop sticky footer all had rules here. Every one of them
       moved into `ShoppingListOverviewCard` (or, for the name input, into a
       dialog) — the styles went with the markup rather than being left behind
       as orphans, which is how `.sld-group-toggle` survived unreferenced until
       this pass. */
    /* Toolbar action band. Same rule (and same reasoning) as
       `.stock-toolbar__actions` on Stock overview: one no-wrap row that
       scrolls sideways, the controls running off the edge being the
       affordance. `gap` rather than `q-gutter-sm` because the gutter's
       negative margins fight `overflow-x`; children can't shrink past their
       own width or the row would squash the labels instead of scrolling. */
    /* The phone's list picker: one field, two segments. It was an `outline`
       dropdown with a centred label sitting beside a bare icon button, so the
       name floated in the middle of a wide button and the pencil read as
       unrelated chrome parked next to it. */
    .sld-picker {
        display: flex;
        align-items: stretch;
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        background: var(--surface-component);
        overflow: hidden;
    }
    .sld-picker__pick {
        flex: 1 1 auto;
        min-width: 0;
        border-radius: 0;
        min-height: 44px;
    }
    /* The label is the list's *name* — a value, not a button caption, so it
       reads from the left and truncates rather than centring and ellipsising
       from both ends. */
    .sld-picker__pick :deep(.q-btn__content) {
        justify-content: flex-start;
        flex-wrap: nowrap;
        min-width: 0;
    }
    .sld-picker__pick :deep(.block) {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        min-width: 0;
        flex: 1 1 auto;
        text-align: left;
    }
    /* The chevron sits at the field's right edge, beside the rename segment,
       rather than trailing the name wherever it happens to end (2026-09-27). */
    .sld-picker__pick :deep(.q-btn-dropdown__arrow) {
        margin-left: auto;
    }
    /* Inside the same edge, divided by a hairline: a second segment of one
       control rather than a second control. */
    .sld-picker__rename {
        flex: 0 0 auto;
        border-radius: 0;
        border-left: 1px solid var(--divider);
        min-width: 48px;
    }
    .sld-toolbar {
        margin-bottom: var(--space-4);
    }
    .sld-toolbar__actions {
        gap: var(--space-2);
        overflow-x: auto;
        overflow-y: hidden;
        min-width: 0;
        flex: 1 1 auto;
        padding-bottom: 2px;
        scrollbar-width: none;
    }
    .sld-toolbar__actions::-webkit-scrollbar {
        display: none;
    }
    .sld-toolbar__actions > * {
        flex: 0 0 auto;
    }
    /* ── The list, v4 chunk 1 ─────────────────────────────────────────
       The rows moved to `ShoppingListPlanRow.vue` and took their layout with
       them. What stays here is the *container* rhythm: a section is a header
       plus one soft slab, rather than a muted caption floating above a
       `q-list bordered separator` nested inside an already-bordered page.
       Every container on this surface used the same 1px border and the same
       6px radius, so nothing receded — the slab is the first step out of that
       (the page canvas itself is chunk 2). */
    /* The panel slab, the section header and the list slab moved to
       `src/css/shoppingList.scss` in chunk 5, so the run face's own containers
       could use them — a child component can't reach a page's scoped rule,
       which is the whole reason the shop face was still wearing bordered
       q-lists after chunks 1-3. */
    .q-mb-4 {
        margin-bottom: var(--space-4);
    }
    .q-mb-5 {
        margin-bottom: var(--space-5);
    }

    .sld-rail {
        width: 300px;
        min-width: 0;
        position: sticky;
        top: 60px;
        /* `max-height`, not `height`: the rail is now only as tall as its rows,
           so "See older" sits directly under the last list instead of being
           pushed to the floor of a full-height column. The ceiling keeps a rail
           that somehow grows (many drafts) inside the viewport. */
        max-height: calc(100vh - 110px);
        overflow-y: auto;
        overflow-x: hidden;
    }
    /* The 300px above holds because of `min-width: 0`: a flex item defaults to
       `min-width: auto`, so the rail refused to shrink below the intrinsic width
       of its widest row — and at 1280px measured 421px inside its 300px parent, pushing
       ~105px of horizontal scroll onto the whole page (the FU-578 #40 family).
       The row carries `.ellipsis` on the name, so it truncates once allowed to.
       `overflow-x: hidden` above is the second belt: the old `.sld-rail-scroll`
       pinned the width on the virtual scroller itself, and that scroller is
       gone. */
    /* Separated from the list by a rule rather than a card — these are exits,
       not content, and a bordered box would give them more presence than two
       destructive actions should have. */
    /* Centred (2026-09-27), with `gap` rather than `q-gutter-sm`: the gutter
       indents every child by a left margin, which pushed the pair 8px right
       of centre. */
    .sld-danger-footer {
        border-top: 1px solid var(--divider);
        gap: var(--space-2);
    }
    /* Plan-face row money: read-only, so it is type rather than a control —
       same size as the row's other captions, with the estimate's tilde carried
       in the markup rather than implied by styling. */
    .sld-plan-price__value {
        font-variant-numeric: tabular-nums;
        font-weight: 500;
    }
    /* Narrow enough that the row keeps its horizontal room; the select's own
       menu is full width when opened. */
    .sld-plan-store {
        min-width: 132px;
    }
    /* Deferred-to-fit-budget rows. Wraps at a phone's width instead of
       printing the action over the reason. */
    .sld-deferred-row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: var(--space-2);
        padding: var(--space-2) var(--space-4);
    }
    .sld-deferred-row + .sld-deferred-row {
        border-top: 1px solid var(--divider);
    }
    .sld-deferred-row__main {
        min-width: 0;
        flex: 1 1 200px;
    }
    .sld-deferred-row__action {
        flex: 0 0 auto;
    }
    /* Dora's frozen reason is a whole sentence — "Would put the week $12 over;
       the tin can wait." It was inside a `q-chip`, and a chip does not wrap:
       the text simply ran out of its own pill and printed underneath the
       button beside it. Tinted text that wraps says the same thing and can be
       as long as the sentence it is. */
    .sld-deferred-reason {
        color: var(--semantic-warning);
        margin-right: var(--space-1);
    }
    /* One rhythm down the sheet. It had none: `q-card-section` brought its own
       16px top padding which the field's own `q-pt-none` then cancelled, so the
       price input sat flush against the title, then `q-mt-md` opened a 16px gap
       before Quantity and `q-mt-sm` left 8px before the store — three different
       spacings, none of them chosen. One gap, stated once. */
    .sld-price-sheet__body {
        display: flex;
        flex-direction: column;
        gap: var(--space-4);
        padding-top: var(--space-2);
    }
    /* Hangs off the field it describes rather than starting a new block. */
    .sld-price-sheet__total {
        margin-top: calc(var(--space-4) * -1 + var(--space-1));
    }
    .sld-price-sheet__offers {
        display: flex;
        flex-direction: column;
        gap: var(--space-1);
    }
    .sld-sheet-qty {
        min-width: 2ch;
        text-align: center;
        font-variant-numeric: tabular-nums;
        font-size: 1.1rem;
    }
    /* FU-334 — receipt thumb strip + lightbox viewer. */
    .sld-receipt-strip {
        flex-wrap: wrap;
    }
    .sld-receipt-thumb {
        position: relative;
        width: 96px;
        height: 96px;
        border-radius: 6px;
        overflow: hidden;
        background: var(--surface-component);
        box-shadow: 0 1px 3px var(--overlay-pressed, rgba(0, 0, 0, 0.15));
    }
    .sld-receipt-thumb img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        cursor: zoom-in;
        display: block;
    }
    .sld-receipt-delete {
        position: absolute;
        top: 2px;
        right: 2px;
        background: var(--surface-component);
        border-radius: 50%;
    }
    .sld-receipt-zoom {
        max-width: 100%;
        max-height: 80vh;
        display: block;
        margin: 0 auto;
    }
    /* R-022 — DnD affordances live in src/css/dnd.scss
       (.dora-dnd-row / --dragging / --drop-over). The decorative
       handle icon-section is non-interactive (whole-row mode), so
       the grab/grabbing cursors aren't needed here. */
    /* The bar itself is `.dora-subbar` from the shared `src/css/subbar.scss`
       now (2026-08-26); this wrapper only exists to give
       `q-slide-transition` a stable 4px buffer to measure against, exactly as
       on Stock overview. The old `.bulk-bar-active` primary-soft tint went
       with the old banner — a whole-width brand wash for "you are selecting
       things" was louder than the state warranted, and it was the one visible
       difference between the two pages' bars. */
    .bulk-bar {
        min-height: 0;
    }
</style>
