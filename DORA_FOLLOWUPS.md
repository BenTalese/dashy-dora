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

## [OPEN] FU-993 — Nutrition food search: row text overlaps, unreadable
- **Raised:** 2026-11-09 (owner feedback)
- **Type:** finding
- **What:** In the food search for linking nutrition (`NutritionFoodPicker.vue`), each result row's text spills past the row and overlaps the next. Suspect: `.food-picker__results` is a flex column with `max-height: 46vh; overflow-y: auto`, and the `.food-row` buttons have the default `flex-shrink: 1`, so with many results they get squashed below their content height. Likely fix: `flex: 0 0 auto` on `.food-row`. Not reproduced yet (needs live USDA / Open Food Facts results).
- **Why deferred:** feedback logged, not yet fixed.
- **Recommended resolution:** now (small); confirm at phone width with a real search

## [OPEN] FU-992 — Cookbook loads and renders every recipe at once; no list should
- **Raised:** 2026-11-09 (owner feedback)
- **Type:** follow-up
- **What:** The cookbook is slow to open. `RecipesOverview.vue` waits on `recipeStore.ensureLoadedAsync()` (every page of `/recipes` via `getAllPagesAsync`) plus all stock items, shopping lists, collections, vocab and meal slots, then renders every card (`v-for="recipe in sortedRecipes"`, no windowing). Owner: nowhere should load a whole list in one go; use pagination or virtualised / infinite scroll.
- **Notes for the build:** two separate costs. (1) Rendering: window the grid (`q-infinite-scroll` in chunks, or `q-virtual-scroll`) so only what's on screen mounts; cheap and likely most of the felt slowness. (2) Fetching: true paging needs the cookbook's filters, sort and search to run server-side, since today they filter the full client-side list. Other whole-list loaders to audit: `getAllPagesAsync` in `stockItemStore`, `productStore`, `mealPlanStore`, `recipeStore` (collections), `stockLevelStore` (tiny, fine). Stock overview already virtualises above 50 rows. Candidate new R-rule: list surfaces window their rendering and page their fetch.
- **Why deferred:** feedback logged; (2) is a design decision (server-side filtering) worth scoping before building.
- **Recommended resolution:** next performance pass; do (1) first, measure, then decide (2)

## [OPEN] FU-991 — Stock overview still snaps when scrolling on a phone
- **Raised:** 2026-11-09 (owner feedback)
- **Type:** finding
- **What:** Scrolling the stock overview on mobile still has a jarring snap. The 2026-08-15 fix (`StockItemRow.vue` ~L691, `StockOverview.vue` ~L815) made rows a fixed height equal to `q-virtual-scroll`'s item size so the scroller stops re-measuring mid-scroll. Either a phone row no longer matches `STOCK_ROW_HEIGHT_MOBILE` (content wrapping, group headers, a changed row), or the snap is the hand-off between the ListTransition path and `q-virtual-scroll` (threshold 50), or something else (sticky chrome, `scroll-behavior`).
- **Why deferred:** feedback logged; needs measuring on a phone-width drive (row heights vs the metric, scroll position over time).
- **Recommended resolution:** now / next stock overview pass; confirm on a phone
