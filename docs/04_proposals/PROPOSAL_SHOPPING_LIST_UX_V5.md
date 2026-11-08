# Shopping List UX v5: one active list

**Status:** BUILT 2026-11-08. D1 to D4 decided (§2); Q1 to Q10 accepted as recommended (§7). Built as
specified, with these notes: the last-tick prompt is the finish dialog itself (its cancel reads "Not yet",
or "Go back" when deferred-by-budget lines remain); on a phone the which-one picker clamps to two lines,
since the name column is narrow once tick, quantity, price and delete share its line. ADR-103 records the
decision.
**Supersedes:** the draft/shopping split from UX-v2 (`PROPOSAL_SHOPPING_LIST_UX_V2.md`), and the
Simple mode shipped in commits `8e6e17e5` / `ab3ae700` (unreleased).
**Keeps:** the v3 overview card and the v4 surface (row grid, slabs, type scale). This changes what
the page *does*, then trims the row; it does not restyle it.

---

## 0. Feedback being addressed (owner, 2026-11-08)

| # | Bullet |
|---|---|
| S1 | "the simple mode is lacking a lot and the flow mode is too cumbersome. simple mode was invented due to poor design of flow mode" |
| S2 | "draft and shopping should be merged (the only difference between them is being able to tick things off or not)" |
| S3 | "done is just the state of 'i've ticked everything off' (can pop up confirmation of done on last item being ticked and cancelling undoes that tick)" |
| S4 | "reordering and custom order is not really that useful and is just noise" |
| S5 | "default sort should be by shop" |
| S6 | "remove the reordering buttons from rows" |
| S7 | "+/- for the quantity can be removed (the quantity box is enough)" |
| S8 | "full row tap will need to be reduced to a big tick button area instead" |
| S9 | "in desktop the buy verdict is a bit oddly placed, could be with the delete button on the side" |
| S10 | "in mobile view the right buttons should inline with the item name (not on the next row down)" |
| S11 | "the drag and drop is maybe redundant now? can remove that handle?" |
| S12 | "other aspects can automatically transition such as 'estimated cost' -> 'left to spend'" |
| S13 | "some things that appear/disappear between states we may need to discuss" |

---

## 1. What the split costs today (audit, 2026-11-08)

The list has three statuses (`draft`, `shopping`, `done`) and the page renders a different *face*
for each. Draft and shopping differ in far more than ticking. Every face-specific element:

| Element | Draft (plan face) | Shopping (run face) | Done (receipt) |
|---|---|---|---|
| Tick a line | no | yes, whole row is the target | no |
| Quantity | tile + hover stepper | "2x" text | editable when amending |
| Name "which one" picker | yes | no (caption shows the hint) | no |
| Planned store dropdown | yes | no (resolved store in caption) | no |
| Price | estimate as text | tap-to-capture button | editable when amending |
| Buy verdict badge | yes | no | no |
| Auto-added mark | yes | no | no |
| Reorder arrows + drag | yes, manual order only | no | no |
| Delete | yes | no | no |
| Group by | store / none (manual) | location / group / store / none | none |
| Collected section + progress bar | no | yes | no |
| Dora suggestions card | yes | no | no |
| Trim-to-budget banner, deferred section | yes | no | no |
| Toolbar: Shop day | yes | no | no |
| Toolbar: Log price | no | yes | no |
| Rename | yes | no | no |
| Receipt photos | no (server refuses) | yes | yes |
| Overview figures | Estimated cost, Shop day, Items | Left to spend, Shop day | Shopped, Items bought |
| Overview actions | Shop | Back to draft, Finish | Amend, Put away |
| Wake lock, space/u keys | no | yes | no |
| Cart button / quick add target | drafts only | never | never |

So "start shopping" switches off curation (delete, picker, store, verdict) at the exact moment you
discover in the aisle that something is out, the wrong size, or at another shop. That is the
cumbersome part of S1, and Simple mode was a workaround for it.

---

## 2. Decisions (owner, 2026-11-08)

- **D1 Restock on tick.** Ticking a line sets its item to Stocked immediately; unticking restores
  the level it had. A list that never fully finishes still keeps the pantry true.
- **D2 Keep a Finish action for leftovers.** Ticking the last line asks "Done?"; Cancel unticks that
  line (S3). A Finish action also stays on the overview card for a shop that ends with items left,
  opening today's move-or-discard dialog.
- **D3 Remove Simple mode.** The toggle, `User.shopping_simple_mode`, `POST .../buy` and
  `POST .../unbuy` go. The merged list does the job Simple mode was patching.
- **D4 Hold v2.0.0 for this.** The `v2.0.0` tag (on `ab3ae700`, unreleased) moves to the commit that
  lands v5, so Simple mode never ships.

---

## 3. The model: two states

`ShoppingList.status` becomes **`active`** or **`done`**.

- **Active:** everything is available at once: add, delete, pick, set store, set quantity, enter a
  price, tick, untick. No mode, no Start, no Back to draft.
- **Done:** the receipt, unchanged from today (read-only rows, Amend, Put away, photos).

Transitions:

- Ticking the **last unticked** active line opens a confirm: *"All ticked. Finish this shop?"*
  Finish runs today's `/finish` (minus the restock, already done by D1). **Cancel unticks the line**
  and restores its level (S3, owner's wording).
- **Finish** on the overview card (secondary, shown once at least one line is ticked) opens the
  existing leftovers dialog: move the unticked lines to another list, or discard them (D2).
- No way back from done (unchanged).

### 3.1 Server

- Migration: `draft` and `shopping` rows become `active`; ticks are kept. Closed set updated in
  `SHOPPING_LIST_STATUS_VALUES`.
- `PATCH .../lines/<id>` with `is_ticked` restocks on true and restores on false. The pre-tick level
  and timestamp are stored on the line (`restock_from_level_id`, `restock_from_level_updated_at`) so
  the untick is exact and survives a reload. Same `_restock` helper as today.
- `/finish` stops restocking (lines are already restocked) and keeps the rest: price harvest, RRP
  and usual-price snapshots, frozen names. The claim-by-UPDATE guard stays.
- Removed: `POST /start`, `POST /back-to-draft`, `POST .../buy`, `POST .../unbuy`,
  `User.shopping_simple_mode` (drop column in the same migration).
- Quick-add / cart-button target: **active** lists (was drafts). FU-603's "prefer a draft over the
  shop in progress" has nothing left to prefer between; with two or more active lists it asks, as
  it does for two drafts today.
- Receipt photos: allowed on active lists (the refusal on `draft` goes).
- Seeds, assistant tools and the inference overlay are updated to the two statuses.

---

## 4. The row

One row for an active list. Grid, left to right:

**Desktop (>= 600px), one line:**

```
[ tick ] [ qty ] Name (which-one picker)  · store ▾          [ ~$4.50 ] [ verdict ] [ delete ]
```

**Phone, two lines, controls on the name line (S10):**

```
[ tick ] [ qty ] Name ▾ ························  [ ~$4.50 ] [ delete ]
                 Coles ▾ · verdict
```

- **Tick button (S8):** a 48px target at the left edge, the only thing that ticks. The rest of the
  row is free for its own controls, so the name picker, store and price no longer fight a row-sized
  click handler.
- **Quantity (S7):** the tile alone; tap to type. Stepper buttons removed everywhere, including the
  receipt amend.
- **Reorder (S4, S6, S11):** arrows, drag handle, whole-row drag and manual order are removed.
  `ShoppingListLine.sequence` stays as the add order (it is the stable tiebreak inside a section) but
  nothing edits it. The reorder endpoint goes.
- **Verdict (S9):** moves from the end of the name line to the action cluster beside delete on
  desktop. On a phone it stays on the caption line, because the name line has no room for a chip.
- **Price:** one control for both jobs. Shows the estimate (`~$4.50`) until you enter what you
  paid, then the actual; tap opens the existing price sheet on any active line (today run-face
  only). Money-gated as now.
- **Ticked rows:** leave their section for a **Collected** section at the bottom (today's run-face
  behaviour), collapsed, struck through, tick button unticks. Their controls stay live so a price
  can still be entered after the fact.
- **Auto-added mark, product-only and nested lines:** unchanged.

---

## 5. The page

### 5.1 Overview card (S12)

| | Nothing ticked | Some ticked | Done |
|---|---|---|---|
| Lead figure (money on) | Estimated cost | **Left to spend** | Shopped (date) |
| Lead figure (money off) | Items to buy | **N left** | Items bought |
| Progress bar | hidden | shown | hidden |
| Shop day | shown | shown if set | hidden |
| Action | none | **Finish** (secondary) | Amend, Put away |
| Status pill | none (an active list doesn't need one) | none | Done / Receipt |

The transitions are automatic: the first tick turns Estimated cost into Left to spend and brings in
the bar; there is no button that does it.

### 5.2 Sorting (S5)

Group-by defaults to **Store** on every list. The menu keeps Store, Location and Group (all three
make sense in the aisle) and **None becomes A to Z** instead of manual order. The choice stays a
per-tab view preference as today.

### 5.3 Toolbar

Add item, Shop day, Log price (money on), Templates, Print, Save as template. All visible on any
active list. The Simple/Flow toggle goes (D3).

---

## 6. Removed

Simple mode (toggle, setting, buy/unbuy, `ShoppingListSimpleFace.vue`), Start shopping, Back to
draft, the run face as a separate component (its Collected section and progress move into the one
active face), reorder arrows, drag handle and drag-and-drop, the quantity stepper, the reorder
endpoint, the `none` = manual sort, the `draft`-only refusal on photos.

---

## 7. Things that appeared or disappeared between states (S13): recommendations

These were face-specific and needed one answer each. **All ten accepted as recommended (owner,
2026-11-08).**

| # | Element | Recommendation | Why |
|---|---|---|---|
| Q1 | Dora suggestions card ("you may be out of...") | Show until the first tick, then hide | It's for building the list. Mid-aisle it pushes the list down. |
| Q2 | Trim-to-budget banner | Show until the first tick | Trimming a shop you're halfway through spends money you've half-spent. |
| Q3 | Deferred-to-fit section | Always shown (collapsed) when it has lines | "Add back" is still useful in the shop if there's money left. |
| Q4 | Receipt photos | Show once anything is ticked | That's when there is a receipt to photograph. |
| Q5 | Wake lock | On while the page shows an active list with at least one tick | Ticking is the signal you're in the shop. |
| Q6 | Space / u keyboard shortcuts | Always on for active lists | No reason to gate them now. |
| Q7 | Collected section | Collapsed by default, count in the header | As the run face today. |
| Q8 | Rename | Always (active and done) | Naming isn't a planning-only act. |
| Q9 | Cart button with several active lists | Ask once, remember per tab (today's draft rule) | Same rule, wider set. |
| Q10 | Shop Now redirect (`/shop-now`) | The server's next-up list (today's by shop day, else the earliest open) when it's open, else the overview | It used to prefer a `shopping` list, which no longer exists. Built on the existing next-up pick rather than a second rule. |

---

## 8. Build plan

1. **Server:** migration (status merge, restock columns, drop simple-mode column), tick restocks and
   untick restores, `/finish` without restock, remove start/back-to-draft/buy/unbuy/reorder, quick-add
   and attachment rules. Backend test for the tick/untick restock contract (stable, money-adjacent).
2. **Active face:** merge plan and run faces into one, Collected + progress, last-tick confirm with
   Cancel = untick, overview card per §5.1, Finish leftovers path.
3. **Row:** tick button, tile-only quantity, verdict beside delete, phone name-line controls, no
   reorder/drag.
4. **Cleanup:** delete Simple mode, help entries, CHANGELOG `[2.0.0]` rewritten, move the `v2.0.0`
   tag (D4).
5. **Drive it live** at 1440 and 375; walk a whole shop including Cancel-on-last-tick and leftovers.

---

## 9. From the original spec (2026-era Feature Board, pre-implementation)

- *"I can 'start shopping' from the shopping list view to enable editing of the items (e.g. checking
  off)"* / *"I can 'finish shopping' once I have 'started shopping'"*: **superseded** by §3. The start
  step is what v5 removes.
- *"I can sort my shopping list items by my own defined order"*: **superseded** by S4.
- *"I can tick on/off multiple stock items on my shopping list in one go"*: **consider**, not in v5.
  The tick button makes single ticks fast; bulk tick stays out unless asked for.
- *"I can see the total price ... including ticked off items" / "... excluding ticked off items
  (remainder)"*: **keep**, it is §5.1's Estimated cost to Left to spend transition.

---

## 10. Coverage

| Bullet | Where |
|---|---|
| S1 | §1, §2 D3, §3 |
| S2 | §3 |
| S3 | §3 transitions |
| S4 | §4 Reorder, §5.2 |
| S5 | §5.2 |
| S6 | §4 Reorder |
| S7 | §4 Quantity |
| S8 | §4 Tick button |
| S9 | §4 Verdict |
| S10 | §4 phone layout |
| S11 | §4 Reorder |
| S12 | §5.1 |
| S13 | §7 Q1-Q10 |

The June feedback file's shopping-list bullets were covered by v2 to v4 and are not reopened here.

## Open decisions

D1 to D4 decided (§2). Q1 to Q10 accepted as recommended (§7). Open decisions: closed.
