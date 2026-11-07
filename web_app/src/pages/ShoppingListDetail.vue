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
                        v-if="planFace || simpleFace"
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
                    <!-- Simple or flow (owner, 2026-11-07). Simple is one
                         endless list where a tick means bought; flow is plan,
                         shop, finish. Per user, saved on the account. Not on a
                         receipt: a finished list reads the same either way. -->
                    <BaseSegmented
                        v-if="!receiptFace"
                        class="sld-mode"
                        dense
                        aria-label="Shopping mode"
                        :model-value="simpleMode"
                        :options="modeOptions"
                        @update:model-value="onSetSimpleMode"
                    />
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
                        v-if="!simpleFace"
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


                    <!-- One list, three faces. "Start shopping" changes the
                         page's *composition*, not just its status — that was
                         the structural defect the redesign set out to fix
                         ("shopping mode is a costume"; "DONE is DRAFT with
                         everything disabled"). Each face is its own component
                         rather than more branches in this template: they share
                         the list, the sectioning and the mutations (through
                         `useShoppingListDetail`), and nothing else.

                         The plan face carries everything that exists to curate
                         a list — the trim-to-budget banner, Dora's suggestions,
                         the rows with their drag, delete, steppers, buy hints,
                         offers and provenance, and the deferred-to-fit
                         section — and no other face has any of it (FU-780). -->
                    <ShoppingListSimpleFace
                        v-if="simpleFace"
                        :lines="detail.lines"
                        @buy="onSimpleBuy"
                    />
                    <ShoppingListPlanFace
                        v-else-if="planFace"
                        :mode="groupBy"
                        :focused-line-id="focusedLineId"
                    />
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

                    <ShoppingListReceiptPhotos />

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
                         about eight rows, not the 29 it used to. The `q-list`
                         wrapper is the `role="list"` its `q-item` rows need. -->
                    <q-list>
                        <ShoppingListRailItem
                            v-for="s in railEntries"
                            :key="s.shopping_list_id"
                            :summary="s"
                            :active="s.shopping_list_id === listId"
                            @select="switchToList(s.shopping_list_id)"
                        />
                    </q-list>
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

        <ShoppingListPriceSheet ref="priceSheet" />

        <ShoppingListFinishDialog ref="finishDialog" v-model:finishing="finishing" />
    </q-page>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import { formatDate as formatLocaleDate } from 'src/composables/useDateFormat';
    import AppSkeleton from 'src/components/AppSkeleton.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDropdown from 'src/components/BaseDropdown.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import ShoppingListOverviewCard from 'src/components/shoppingList/ShoppingListOverviewCard.vue';
    import ShoppingListPlanFace from 'src/components/shoppingList/ShoppingListPlanFace.vue';
    import ShoppingListSimpleFace from 'src/components/shoppingList/ShoppingListSimpleFace.vue';
    import BaseSegmented from 'src/components/BaseSegmented.vue';
    import ShoppingListRunFace from 'src/components/shoppingList/ShoppingListRunFace.vue';
    import ShoppingListReceiptFace from 'src/components/shoppingList/ShoppingListReceiptFace.vue';
    import ShoppingListReceiptPhotos from 'src/components/shoppingList/ShoppingListReceiptPhotos.vue';
    import ShoppingListPriceSheet from 'src/components/shoppingList/ShoppingListPriceSheet.vue';
    import ShoppingListFinishDialog from 'src/components/shoppingList/ShoppingListFinishDialog.vue';
    import {
        PLAN_SECTION_MODES, useLineSections, type SectionMode,
    } from 'src/composables/useLineSections';
    import FadeTransition from 'src/components/transitions/FadeTransition.vue';
    import NewListDialog from 'src/components/dialogs/NewListDialog.vue';
    import PutAwayDialog from 'src/components/dialogs/PutAwayDialog.vue';
    import ShoppingListRailItem from 'src/components/shoppingList/ShoppingListRailItem.vue';
    import { useQuasar } from 'quasar';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { useQuickAdd } from 'src/composables/useQuickAdd';
    import { provideShoppingListDetail } from 'src/composables/useShoppingListDetail';
    import { useShoppingListExport } from 'src/composables/useShoppingListExport';
    import { useShortcut } from 'src/composables/useShortcut';
    import { useWakeLock } from 'src/composables/useWakeLock';
    import {
        listStatusIcon,
        type ShoppingListLine,
        type ShoppingListSummary
    } from 'src/models/shoppingList';
    import ShoppingListTemplateApiService from 'src/services/api/shoppingListTemplateApiService';
    import type { BoughtLine } from 'src/services/api/shoppingListApiService';
    import { useAuthStore } from 'src/stores/authStore';
    import { useProductStore } from 'src/stores/productStore';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { useStoresStore } from 'src/stores/storesStore';
    import { useLogPrice } from 'src/composables/useLogPrice';
    import { useListState } from 'src/composables/useListState';
    import { computed, onMounted, ref, useTemplateRef, watch } from 'vue';
    import { useRouter } from 'vue-router';
    import { isAlreadyNotified, toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useConfirm } from 'src/composables/useConfirm';

    const router = useRouter();
    const $q = useQuasar();
    const { confirm, prompt } = useConfirm();

    // The list, its faces, its re-reads and the trim banner's state are shared
    // with the face components below — see `useShoppingListDetail` (FU-780).
    const {
        api, listId, detail, simpleMode, simpleFace, planFace, runFace, receiptFace, loading, loadError,
        baseLines, resetTrim, load, refreshAll, refreshDetailQuietly,
        refreshAllQuietly, onAdjustQuantity,
    } = provideShoppingListDetail();
    const templateApi = new ShoppingListTemplateApiService();
    const store = useShoppingListStore();
    const stockItemStore = useStockItemStore();
    const authStore = useAuthStore();
    const stockLevelStore = useStockLevelStore();
    const productStore = useProductStore();
    const { moneyEnabled } = useMoneyEnabled();
    // Phones drop every toolbar label and ride the icon alone, tooltip
    // carrying the name — same breakpoint and same reason as Stock overview's
    // `compactToolbar` (the row was eating a quarter of the screen).
    const compactToolbar = computed(() => $q.screen.lt.sm);
    const { openQuickAdd, isOpen: quickAddOpen } = useQuickAdd();

    // shop-mode wake lock. Holds the screen on while the list is
    // in 'shopping' status so the phone doesn't blank between aisles. The
    // computed reads `detail.value?.status` so entering / leaving shop
    // mode toggles the lock without any explicit acquire/release call.
    const shopModeActive = computed(() => runFace.value);
    useWakeLock(shopModeActive);

    // Amend is off every time the receipt is opened — a historical record
    // should never come up already unlocked, and the mode must not survive a
    // switch to a different list.
    const amending = ref(false);
    watch([listId, receiptFace], () => { amending.value = false; });
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
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not start shopping.',
                    caption: toastCaption(err),
                });
            }
        } finally {
            togglingProgress.value = false;
        }
    }

    // ── Finish & restock ────────────────────────────────────────────
    // `ShoppingListFinishDialog` owns the flow; the page only opens it and
    // shares `finishing` with the overview card's Finish button.
    const finishing = ref(false);
    const finishDialog = useTemplateRef<InstanceType<typeof ShoppingListFinishDialog>>('finishDialog');

    function openFinishReview() {
        finishDialog.value?.show();
    }

    // Render order for the keyboard shortcuts below. The plan face sections
    // its own rows (same options, its own `useLineSections`); this instance
    // exists only so arrow-key focus walks the same order the page draws.
    // Mid-shop, ticked lines leave their section entirely so the list shrinks
    // as you shop; on the plan face they stay put and dim.
    const { orderedLines: sectionOrderedLines } = useLineSections(baseLines, groupBy, {
        hideTicked: computed(() => detail.value?.status === 'shopping'),
        // Plan face: store + ungrouped only. The run face renders through
        // `ShoppingListRunFace`, which keeps all four.
        allowedModes: PLAN_SECTION_MODES,
    });

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
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not save shop day.',
                    caption: toastCaption(err),
                });
            }
        }
    }

    async function clearPlannedDate() {
        if (!detail.value) return;
        try {
            await api.updateAsync(listId.value, { planned_shop_date: null });
            await refreshAllQuietly();
            plannedDateOpen.value = false;
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not clear shop day.',
                    caption: toastCaption(err),
                });
            }
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
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not delete.',
                    caption: toastCaption(err),
                });
            }
        }
    }

    function onDeleteCurrentList() {
        if (currentSummary.value) void deleteSummary(currentSummary.value);
    }

    async function onPutAwayAssigned(): Promise<void> {
        // The dialog just persisted a new stock_location for one line's
        // item. Reload the list detail so the line's breadcrumb + group
        // membership move with it — the dialog re-reads via v-model on
        // detail.lines. Quietly (R-084): `load()` nulls `detail`, which
        // unmounts this `v-if`-gated dialog and loses its local ticks.
        await refreshDetailQuietly();
    }

    // ── Name editing (UX-v2 §5: clearable custom name) ────────────────
    // The fallback chain (custom > shop day > created) is server-owned
    // (`display_name`); this only edits the raw custom `name`.
    const dateFallbackName = computed(() => {
        const d = detail.value?.planned_shop_date;
        if (d) return formatDate(d);
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
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not rename.',
                    caption: toastCaption(err),
                });
            }
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
        if (!runFace.value) return;
        const line = orderedLines.value.find((l) => l.line_id === focusedLineId.value);
        if (line) void onToggleTicked(line.line_id, !line.is_ticked);
    }
    function untickLastTicked() {
        if (!runFace.value) return;
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
        // Ticking is the run face's (FU-808), so the two keys are off elsewhere.
        { keys: 'space', scope: 'Shopping list', description: 'Tick / untick the focused line', handler: tickFocusedLine, enabled: () => runFace.value },
        { keys: 'u', scope: 'Shopping list', description: 'Untick the last item you ticked', handler: untickLastTicked, enabled: () => runFace.value },
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
    watch(listId, () => {
        resetTrim();
        void load();
    });

    /** @returns whether the tick reached the server — the run face only
     *  promises an undo for a change that actually landed. */
    async function onToggleTicked(
        lineId: string,
        value: boolean,
        forListId: string = listId.value,
    ): Promise<boolean> {
        // Optimistic flip so the checkbox feels instant; if the request
        // fails we re-load the canonical state. Offline is read-only
        // (2026-08-23), so a network failure is a plain failure here — the
        // tick is undone and said so, rather than being buffered and
        // promised.
        const line = detail.value?.lines.find((l) => l.line_id === lineId);
        if (line) line.is_ticked = value;
        if (value) recentTickStack.value.push(lineId);
        try {
            await api.updateLineAsync(forListId, lineId, { is_ticked: value });
            // The counts are ours to flip optimistically, but the money isn't:
            // `remaining_price` and the store breakdown are server-owned
            // aggregates (R-003), and the run face's footer puts "Remaining"
            // in front of the user on every single tick. Re-read rather than
            // re-derive — the optimistic flip above already paid for the feel.
            await refreshDetailQuietly();
            return true;
        } catch (err) {
            // Undo the optimistic flip, then re-read quietly: a full `load()`
            // flashed the skeleton over the list being shopped (FU-953, R-084).
            if (forListId === listId.value) {
                if (line) line.is_ticked = !value;
                if (value) recentTickStack.value = recentTickStack.value.filter((id) => id !== lineId);
                await refreshDetailQuietly();
            }
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not update line.',
                    caption: toastCaption(err),
                });
            }
            return false;
        }
    }

    /** Run-face tick. One gesture, and the row leaves the list — so the undo
     *  has to travel with it. The toast is the only place a mis-tap is
     *  recoverable now that the row is gone from the section, and it reuses
     *  the same untick path as the `u` shortcut rather than a second one.
     *
     *  It waits for the tick to land before offering the undo: on a failure
     *  `onToggleTicked` undoes the flip and says so, and a cheerful "Picked X · UNDO"
     *  sitting next to "Could not update line" would be offering to undo
     *  something that never happened. */
    async function onRunTick(line: ShoppingListLine) {
        if (line.is_ticked) return;
        // The toast outlives a list switch, so its Undo must untick the line
        // on the list it was picked from, not whichever list is open by then.
        const id = listId.value;
        const ok = await onToggleTicked(line.line_id, true, id);
        if (!ok) return;
        $q.notify({
            type: 'positive',
            timeout: 4000,
            message: `Picked ${line.stock_item_name}`,
            actions: [{
                label: 'Undo',
                color: 'white',
                handler: () => { void onToggleTicked(line.line_id, false, id); },
            }],
        });
    }

    // ── Simple mode ─────────────────────────────────────────────────────
    const modeOptions = [
        { label: 'Simple', value: true },
        { label: 'Flow', value: false },
    ] as const;

    async function onSetSimpleMode(value: boolean) {
        if (value === simpleMode.value) return;
        try {
            await authStore.updateMeAsync({ shopping_simple_mode: value });
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not switch mode.',
                    caption: toastCaption(err),
                });
            }
        }
    }

    /** Simple-mode tick: bought. The server restocks the item and removes the
     *  line in one request, and echoes what the undo needs to put both back.
     *  The row leaves straight away; on a failure the list is re-read. Like
     *  `onRunTick`, the undo is offered only once the buy has landed, and it
     *  targets the list the item was bought from. */
    async function onSimpleBuy(line: ShoppingListLine) {
        const current = detail.value;
        if (!current) return;
        const id = listId.value;
        current.lines = current.lines.filter((l) => l.line_id !== line.line_id);
        let bought: BoughtLine;
        try {
            ({ bought } = await api.buyLineAsync(id, line.line_id));
        } catch (err) {
            await refreshDetailQuietly();
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: `Could not mark ${line.stock_item_name} as bought.`,
                    caption: toastCaption(err),
                });
            }
            return;
        }
        afterSimpleBuy(line.stock_item_id);
        $q.notify({
            type: 'positive',
            timeout: 4000,
            message: `Bought ${line.stock_item_name}`,
            actions: [{
                label: 'Undo',
                color: 'white',
                handler: () => { void undoSimpleBuy(id, bought, line.stock_item_id); },
            }],
        });
    }

    async function undoSimpleBuy(id: string, bought: BoughtLine, stockItemId: string | null) {
        try {
            await api.unbuyLineAsync(id, bought);
        } catch (err) {
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not undo.',
                    caption: toastCaption(err),
                });
            }
            return;
        }
        if (id === listId.value) await refreshDetailQuietly();
        afterSimpleBuy(stockItemId);
    }

    /** The buy wrote the item's level and the list's membership server-side,
     *  past the stores that would otherwise know. */
    function afterSimpleBuy(stockItemId: string | null) {
        void store.refreshAsync();
        if (stockItemId) void stockItemStore.refreshItemAsync(stockItemId).catch(() => {});
    }

    /** Put a picked line back, from the run face's Picked section. No undo
     *  toast: this *is* the undo, and the row reappears in its section where
     *  you can see it land. */
    async function onRunUntick(line: ShoppingListLine) {
        if (!line.is_ticked) return;
        await onToggleTicked(line.line_id, false);
    }

    // ── Price capture sheet (run + receipt faces) ───────────────────────
    // `ShoppingListPriceSheet` owns the draft and the save path; both faces
    // open it with the line to edit.
    const priceSheet = useTemplateRef<InstanceType<typeof ShoppingListPriceSheet>>('priceSheet');

    function openPriceSheet(line: ShoppingListLine) {
        priceSheet.value?.show(line);
    }

    // Stores power the plan face's "where do you plan to buy this" picker and
    // the sheet's "Bought from"; both read the store, the page loads it.
    const storesStore = useStoresStore();
    const { openLogPrice } = useLogPrice();

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
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not go back to draft.',
                    caption: toastCaption(err),
                });
            }
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
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not clear.',
                    caption: toastCaption(err),
                });
            }
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
            if (!isAlreadyNotified(err)) {
                $q.notify({
                    type: 'negative',
                    message: 'Could not save template.',
                    caption: toastCaption(err),
                });
            }
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
    .sld-mode {
        flex: 0 0 auto;
        margin-left: auto;
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
</style>
