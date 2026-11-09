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

## [OPEN] FU-996 — Route changes briefly stack the old page above the new one
- **Raised:** 2026-11-09 (found during FU-995)
- **Type:** finding
- **What:** `MainLayout.vue`'s route `<FadeTransition>` has no `mode="out-in"` (its own comment recommends it), so for the length of the fade both pages are in the document, the leaving one above the entering one. Measured on cookbook back navigation: document height 9740 during the overlap vs 8139 after. FU-995 works around it in `scrollBehavior`; it may also show as a brief flash of the new page lower down.
- **Why deferred:** changes the feel of every page transition; not reported.
- **Recommended resolution:** opportunistic; decide `out-in` (or absolute-positioned leave) with the owner

## [OPEN] FU-992 — Cookbook loads and renders every recipe at once; no list should
- **Raised:** 2026-11-09 (owner feedback)
- **Type:** follow-up
- **What:** The cookbook is slow to open. `RecipesOverview.vue` waits on `recipeStore.ensureLoadedAsync()` (every page of `/recipes` via `getAllPagesAsync`) plus all stock items, shopping lists, collections, vocab and meal slots, then renders every card (`v-for="recipe in sortedRecipes"`, no windowing). Owner: nowhere should load a whole list in one go; use pagination or virtualised / infinite scroll.
- **Notes for the build:** two separate costs. (1) Rendering: window the grid (`q-infinite-scroll` in chunks, or `q-virtual-scroll`) so only what's on screen mounts; cheap and likely most of the felt slowness. (2) Fetching: true paging needs the cookbook's filters, sort and search to run server-side, since today they filter the full client-side list. Other whole-list loaders to audit: `getAllPagesAsync` in `stockItemStore`, `productStore`, `mealPlanStore`, `recipeStore` (collections), `stockLevelStore` (tiny, fine). Stock overview already virtualises above 50 rows. Candidate new R-rule: list surfaces window their rendering and page their fetch.
- **Why deferred:** feedback logged; (2) is a design decision (server-side filtering) worth scoping before building.
- **Recommended resolution:** next performance pass; do (1) first, measure, then decide (2)
- **Progress (2026-11-09):** step 1 done: the grid and compact list render 24 at a time via `useIncrementalRender` (R-106), resetting only on search/filter/sort. At 72 recipes first-card time was unchanged (~1.3s), so fetching dominates: `/recipes` is 366KB for 72 recipes (about 5KB each, ingredients 170KB of it, used by the client-side filters) and `/stock-items` 421KB for 500 items. Step 2 is slimming the list payload / moving those filters server-side.
- **Progress (2026-11-09, step 2):** the API served JSON uncompressed (gunicorn direct; only the SPA went through nginx's gzip). New `GzipMiddleware` (`infrastructure/compression.py`, wrapped in `app.py`): `/recipes` 365KB to 30KB, `/stock-items` 398KB to 24KB on the wire, server time unchanged (~70-80ms). Pinned by `tests/test_gzip_middleware.py`. Server-side paging of the cookbook was not built: every filter and sort (cookable, kcal, cost, rating, expiring, planned) runs on the client over the shared recipe list, which 23 files read; at ~30KB gzipped the whole-list fetch is no longer the cost.
- **Recommended resolution (updated):** when a household's cookbook or pantry is slow again with gzip on (measure first); then design server-side paging + filters for the cookbook
