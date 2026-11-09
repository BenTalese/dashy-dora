# Dora Follow-ups Ledger — Open

Stateful backlog of **open follow-ups, deferred jobs, leftovers, and findings**
surfaced while running prompts — the stuff that's easy for the user to miss in a
long session summary. Distinct from the other logs:

- `CHANGELOG.md` = product/code changes that shipped.
- `DORA_WORKLOG.md` = per-session handoff narrative.
- `DORA_FOLLOWUPS.md` (this file) = **open loops** that outlive a single session.
- `DORA_FOLLOWUPS_RESOLVED.md` = the archive of items that have been resolved
  (kept for the trail — never delete).

## How to use this file

- **On session start:** scan for items here. Surface the ones whose *recommended
  resolution point* is "now" or matches the work about to start, and **ask the
  user** whether they want to review/resolve them now or defer.
- **On ending a work unit:** add any new follow-ups/leftovers/findings you
  generated. If you actually resolved an item, **move its entry from this file
  to `DORA_FOLLOWUPS_RESOLVED.md`**, flip the heading from `[OPEN]` to
  `[RESOLVED]`, and add a one-line state note on how. Do not leave resolved
  items in this file, and do not delete them either — the trail matters.
- **Reported defect that "doesn't reproduce" → still log it here** as `[OPEN]`
  type `finding`, resolution "confirm in browser". A static code read is not
  proof a user-reported bug is fixed. Track each reported item individually;
  never bury several as one "all fine" note.
- Keep the newest items at the top.

## Entry template

```
## [OPEN] FU-NNN — short title
- **Raised:** YYYY-MM-DD (prompt id / task)
- **Type:** follow-up | deferred job | leftover | finding
- **What:** one or two lines.
- **Why deferred:** the reason it wasn't done in-line.
- **Recommended resolution:** now | later during <Phase/Prompt X> | when <trigger> | opportunistic
```

---

## [RESOLVED] FU-NNN — short title
- **Raised:** YYYY-MM-DD (prompt id / task)
- **Type:** follow-up | deferred job | leftover | finding
- **What:** one or two lines.
- **Why deferred:** the reason it wasn't done in-line.
- **Recommended resolution:** now | later during <Phase/Prompt X> | when <trigger> | opportunistic
- **State note:** (filled in when resolved — date + how)
```

---

# Open

## [OPEN] FU-989 — Shopping list overview card: whole card toggles, no caret, no help icon
- **Raised:** 2026-11-09 (owner feedback)
- **Type:** follow-up
- **What:** On `ShoppingListOverviewCard.vue`, drop the expand caret and make the whole card tap to expand; remove the `HelpHint` ("One list, from first item to receipt", ~L67) so the card is shorter.
- **Notes for the build:** `CollapsibleCard` always renders the caret and its `headerToggles` makes the lead a `<button>`, which this header can't use because it holds its own controls (Group by menu, Finish, Amend, Put away, Rename). Needs a `CollapsibleCard` option to hide the caret, plus a lead toggle that ignores taps landing on those controls and still has keyboard/aria-expanded support (D-004/D-005). On phones the foot row still holds the Group by/Finish buttons after the help icon goes, so check the height actually drops; it may need those buttons moved up into the figures row.
- **Why deferred:** feedback logged, not yet built.
- **Recommended resolution:** next shopping list pass (with FU-988)

## [OPEN] FU-988 — Shopping list quick-add can't create a missing stock item
- **Raised:** 2026-11-09 (owner feedback)
- **Type:** follow-up
- **What:** On the shopping list page, the add dialog (`QuickAddSheet.vue`) only lists existing stock items; a search with no hit dead-ends at "No matches." Owner wants to add a missing stock item from there (create it, then add it to the list) without leaving the list.
- **Why deferred:** feedback logged, not yet built. Reuse the existing create-stock-item path (R-001), don't add a second one.
- **Recommended resolution:** next shopping list pass

## [OPEN] FU-987 — Stock item nutrition box causes horizontal scroll on phones
- **Raised:** 2026-11-09 (owner feedback)
- **Type:** finding
- **What:** On the stock item detail page (phone width), the Nutrition row in `StockItemOverviewTab.vue` (~L210-268: linked-food summary row with Details / search / unlink buttons, plus the expanded `NutritionFactsList`) pushes the page wider than the viewport and enables horizontal scroll. Suspects: the button row not wrapping beside the food name, or the facts table not shrinking inside the `q-item-section`.
- **Why deferred:** feedback logged, not yet fixed.
- **Recommended resolution:** now / next stock detail pass; confirm at 375px after the fix
