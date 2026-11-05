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

## [OPEN] FU-960 — Onboarding seed endpoint has no first-user gate server-side; companion contract tightened
- **Raised:** 2026-10-30 (autonomous QA round 2)
- **Type:** finding
- **What:** (1) the wizard no longer seeds default groups/locations for non-first users (client fix this round), but
  `POST /onboarding/seed` and the pack-item seed still accept the call from any signed-in user, so a stale client can
  re-create defaults the admin deleted. Gate on `first_user` (or admin) in `onboarding.py`, with a test. (2) The ingest
  API now normalises `observed_at` to UTC (an offset is honoured; a naive value is read as UTC, as it always was) and
  degrades a `web_url` that is not http(s) or is over 255 chars to "no link" instead of storing it — the companion
  should send an offset-carrying timestamp and a full URL; its guide (`docs/04_proposals/…ingestion…`) should say so.
- **Why deferred:** (1) changes an endpoint contract; (2) lives in the other repo.
- **Recommended resolution:** (1) next onboarding touch; (2) next companion release.
- **Progress (2026-11-05):** (1) done: `/onboarding/finish` returns 403 for `seed`, `items` or `seed_demo` unless the caller is the install's first account, with a test. (2) remains (companion repo).

## [OPEN] FU-924 — Companion has a few pre-existing UI debts (companion repo)
- **Raised:** 2026-10-17 (owner batch, companion dark theme)
- **Type:** finding
- **What:** (a) dark-mode `q-card`s paint Quasar's `$dark` grey rather than
  `--surface-component` (same in Dora; set `--q-dark` in both); (b) the
  "OUT OF STOCK" banner is white on `--semantic-negative`, about 2.6:1 on Pesto
  Dark (D-002 floor); (c) batch save doesn't fill the hearts on saved cards, only
  single save does; (d) `PROPOSAL_INGESTION_API` §2.2 doesn't list the new
  optional `products[].image` field.
- **Why deferred:** outside the asks; found while building them.
- **Recommended resolution:** opportunistic (next companion pass).
- **2026-10-23 (finalisation Stage 1):** two more companion-side notes from CHUNK_16 §E: `dora_ingest.fetch_saved_products` docstring still says the list is filtered to mapped stores (Dora stopped filtering 2026-10-15); `IngestResult.has_pending_store_mappings` only knows `store_not_mapped`, not `store_unknown`. (d) is fixed on Dora's side by 16-R1.

## [OPEN] FU-922 — Product photo can only be set from the cards view
- **Raised:** 2026-10-17 (owner batch, My products)
- **Type:** leftover
- **What:** the compact `ProductRow.vue` has no overflow menu, so a custom
  product's photo is only reachable from the cards view or at creation.
  Sibling stock-detail cards `PlannedDemandCard.vue` / `PantryBeliefCard.vue`
  also still use off-scale spacing (D-017).
- **Why deferred:** outside the ask.
- **Recommended resolution:** opportunistic.

## [OPEN] FU-907 — the auto builder's budget cap assumes a uniform meals-per-pick
- **Raised:** 2026-09-12 (meal-planner feedback batch)
- **Type:** finding
- **What:** `apply_budget_cap` now counts a pick at
  `per_serving × servings × meals_per_pick`, where `meals_per_pick` is one
  scalar for the whole build (1, the number of days when repeating, or the batch
  span). A batch week whose last chunk is shorter than the span therefore rounds
  that pick **up**. The cap runs before placement, so the exact per-pick count
  isn't knowable where it is applied.
- **Why deferred:** fixing it properly means applying the cap *after* placement
  (swap entries rather than picks), which is a real restructure of
  `compute_auto_build` and was outside this batch's scope. The cap is
  documented best-effort and errs toward under-spending.
- **Recommended resolution:** opportunistic — if the budget cap is revisited.

## [OPEN] FU-895 — the nutrition panel's other three gap reasons have no way out
- **Raised:** 2026-09-08 (recipe view feedback batch)
- **Type:** follow-up
- **What:** the nutrition panel now names every uncounted ingredient, but only
  `no_food` and `no_data` carry an action ("Find a food") — those two are fixed
  by a write against the **stock item**, which the panel can do. The other
  three are fixed by editing the **ingredient row**: `not_linked` wants the row
  bound to a pantry item, `no_quantity` wants an amount typed, `no_conversion`
  wants a unit the rollup can weigh ("2 sprigs" can't be). Today the reader sees
  the name and the reason and has to scroll up, find the row, and press the
  pencil themselves.
- **Why deferred:** the fix is a jump into the ingredients editor (open the
  region, scroll to the row, focus the right field), which is a different
  interaction from "open a dialog and pick" and wants its own design pass — the
  ingredient rows are keyed by `client_id`, and the panel only holds
  `stock_item_id`, so `not_linked` rows have no anchor to jump to at all
  without also shipping the ingredient id.
- **Recommended resolution:** opportunistic — next time the recipe ingredients
  editor is open for other work.

## [OPEN] FU-891 — a never-checked scraper reports "healthy" (companion repo)
- **Raised:** 2026-09-07 (products program, batch E)
- **Type:** finding
- **Repo:** `../dora-companion/`
- **What:** `MerchantDataProvider._is_healthy` defaults to `True`, and the health
  check runs on a **daily** interval trigger — so for up to 24 hours after boot
  every provider claims health on no evidence. Batch E made this *visible*
  (`GET /api/health/data-providers` now returns `last_checked_at: null`
  alongside `is_healthy: true`) but did not change it.
- **Why not fixed here:** flipping the default to `False` is not safe.
  `get_healthy_providers()` gates whether a provider is used at all, so a
  pessimistic default would disable **all scraping** until the first check —
  turning a cosmetic inaccuracy into an outage. The right fix is a third state
  (`unknown`) that `get_healthy_providers()` treats as usable while the health
  endpoint reports honestly, and possibly a check on boot rather than only on
  the interval.
- **Recommended resolution:** opportunistic — alongside the Aldi selector
  rewrite (the rest of [[FU-884]]), since that work is already in this file and
  wants a trustworthy health signal to verify against.

## [OPEN] FU-887 — companion has no eslint config and its cross-repo roundtrip test can't run (companion repo)
- **Raised:** 2026-09-06 (products program, batch B)
- **Type:** finding — gates
- **Repo:** `../dora-companion/`
- **What:** two gaps found while gating batch B.
  1. **`npm run lint` fails outright**: the script is
     `eslint "src/**/*.{ts,vue}"` but there is no eslint config anywhere in
     `web_app/` or its ancestors, so ESLint 8.57 exits with "couldn't find a
     configuration file". The companion SPA has therefore never been linted.
     `npx vue-tsc --noEmit` **is** clean, so typechecking is the only frontend
     gate that currently exists.
  2. **`tests/test_integration_dora_roundtrip.py` cannot run in this
     environment.** It imports Dora's app from the sibling checkout, so it needs
     Dora's dependencies in the companion venv (`flask_migrate` is missing).
     Running it with Dora's venv gets further but then fails in DB setup:
     against the dev Postgres `drop_all` errors (`cannot drop table "Product"
     because other objects depend on it` — `fk_ProductBarcode_product_id_Product`),
     and against a throwaway SQLite it gets a **403 minting the ingestion
     source**, so the admin fixture isn't granting admin. Three distinct
     failures, all in setup, none reaching a push.
- **Why deferred:** batch B's own contract is covered by
  `tests/test_push_contract.py` (16 tests) plus a real-HTTP end-to-end against a
  stub Dora, and the roundtrip test exercises `push_offers` directly rather than
  the route that changed — so it is orthogonal to B, not a gap in it. Fixing it
  means either vendoring Dora's deps into the companion venv or reworking the
  fixture's admin bootstrap, which is test-infra work in its own right.
- **Recommended resolution:** opportunistic, and a natural fit for **batch E**
  (which is the batch that wants reliable companion gates for scraper fixture
  tests anyway). Note the Postgres `drop_all` ordering failure may be a **Dora**
  bug worth confirming separately — if `startup()`'s destructive reset can't drop
  a schema it created, that affects Dora's own dev resets too.

## [OPEN] FU-886 — companion 500s on a malformed request body instead of returning a 4xx (companion repo)
- **Raised:** 2026-09-06 (products program, batch B)
- **Type:** finding
- **Repo:** `../dora-companion/`
- **What:** the companion registers **no global pydantic `ValidationError`
  handler** (nothing in `merchant_api/infrastructure/middleware.py` or the app
  factory). Feature routes call `Model.model_validate(request.get_json())`
  directly, so any request that fails validation raises out of the view and
  Flask returns a **500**. Pinned as current behaviour in
  `tests/test_push_contract.py::test__push_route__rejects_the_retired_search_query_shape`.
- **Why it matters now:** batch B changed `/api/push`'s contract, so a **stale
  SPA bundle** (cached in a browser, or a companion frontend deployed ahead of
  its backend) sends the retired search-query shape and gets an opaque 500 with
  no indication that the client is out of date. The rejection itself is correct
  and deliberate — the status code and message are what's poor.
- **Why deferred:** pre-existing, not a regression (the previous
  `PushToDoraRequest` was equally strict — `extra="forbid"` plus a `min_length`
  — so a malformed body already 500'd). Adding an app-wide error handler is a
  cross-cutting change to the companion's Flask setup, not part of B's scope.
  Dora solved the same problem with a shared `api_response` layer; the companion
  has no equivalent.
- **Recommended resolution:** opportunistic — fold into **batch A** (which is
  already touching companion configuration/plumbing) or batch E. Cross-ref
  [[FU-887]].

## [OPEN] FU-857 — Free-text steps are numbered twice unless we strip the author's own ordinal
- **Raised:** 2026-09-03 (recipe-view owner batch, item 10)
- **Type:** finding
- **What:** giving free-text steps the structured face's numbered circles made
  the seed's Carbonara read "(1) 1. Render the pancetta" — the author had typed
  their own "1. " prefixes, which is what people do in a free-text box. The read
  view now strips a leading ordinal (`/^\d{1,3}\s*[.):]\s+/`) for display only;
  the stored text and the editor are untouched. Two loose ends: (a) the strip is
  display-side, so the *editor* still shows "1. Render…" and an author who
  renumbers by hand gets no help; (b) the pattern is deliberately narrow and will
  miss "Step 1 — " or "(1) ".
- **Why deferred:** the owner asked for the circles, not for a numbering
  authority. Deciding whether free text should be *normalised on save* (strip the
  ordinals for real, since the app now draws them) is a data-shape call.
- **Recommended resolution:** opportunistic — or now, if the doubled numbering
  turns up in a recipe the strip doesn't catch.
- **Progress (2026-11-06):** (b) done in pt2: helpers/stepOrdinal.stripLeadingOrdinal handles '1.', '2)', '3:', 'Step 4 —', '(5)' and leaves '2 eggs' / '1.5 cups'; it is the one implementation for the recipe page and cook mode (stepOrdinal.spec, 9 cases). Still open: (a) whether to normalise the stored text on save or keep the strip display-only (the helper currently treats it as display-only). Owner call.

## [OPEN] FU-837 — A short dashboard card stretches to its tall row-mate, which reads as dead space
- **Raised:** 2026-09-02 (dashboard chunk 2 — seen in the verification screenshot)
- **Type:** finding (design)
- **What:** cards in a row stretch to the tallest (the default `align-items:
  stretch`, plus `DashboardCard`'s own `height: 100%`). Measured at 1440px on the
  dense dataset, "Draft this week's shop" — three lines of copy and a button — is
  stretched to match "Needs your attention" beside it, leaving roughly **180px of
  empty card** below its button. This is *not* the D-011 dead-grid air chunk 2
  fixed (that row is 100% used); it is empty space *inside* a card, which arguably
  reads worse because the card's border draws a box around it.
- **Why it isn't just "set `align-items: flex-start`":** equal-height cards are
  what makes the zone bands read as tidy rows; natural heights give a ragged
  bottom edge on every row. Both are defensible, so it is a design call — and it
  interacts with [[FU-830]], which changes who sits next to whom. There is also a
  middle option: centre the short card's *content* vertically instead of
  top-aligning it, filling the box without touching the grid.
- **Recommended resolution:** later, with `DASHBOARD_PAGE_REVIEW.md` §7 Chunk 6
  (the design sweep), once Chunk 3 has settled the card pairs. Cross-ref: B4,
  D-011, [[FU-631]] #3.

## [OPEN] FU-799 — sweep the other prose-parsed domain facts (R-068)
- **Raised:** 2026-09-01 (cook-mode feedback batch)
- **Type:** follow-up
- **What:** cook mode's step timer was recovered by regex from the step's text;
  it now reads a real `RecipeStep.timer_minutes` and labels the fallback as
  inferred. Generalised as **R-068**. The same instinct is available anywhere
  the schema is thinner than the feature — the nearest neighbour is the recipe
  importer's serving/time/quantity parsing (`_parse_recipe_from_text.py`), which
  is arguably *fine* under R-068's non-goal (it proposes, the user confirms),
  but has never been checked against it. Grep for regexes over `.text` /
  `.notes` / `.instructions` and confirm each one either only affects
  presentation, or proposes-and-confirms, or is labelled.
- **Why deferred:** out of scope for a cook-mode feedback batch, and each hit
  needs its own read of whether it drives behaviour or just presentation.
- **Recommended resolution:** opportunistic — next time the importer is open.

---

## [OPEN] FU-771 — Nutrition mode/scheme changes don't invalidate the recipe list
- **Raised:** 2026-08-28 (cookbook rating + kcal batch)
- **Type:** finding
- **What:** R-062's invalidation covers stock writes, which is where the owner's
  bug was. Two install-wide levers move every recipe's rollup and are **not**
  covered: switching nutrition mode / rating scheme on
  `AdminSystemNutritionSettings.vue`, and a dataset import completing. Both
  currently rely on the user reloading — plausible for a settings change, less so
  for an import that finishes while they're on another page.
- **Why deferred:** both also change cached *feature flags*, which the SPA reads
  once per session, so a store invalidation alone wouldn't make the surfaces
  correct — it needs the flag-refresh seam thought through, which is wider than
  this batch.
- **Recommended resolution:** opportunistic — next time the health-flag caching
  or the admin nutrition page is open. Cites **R-062**.
- **Progress (2026-11-06):** mode/scheme and import-finished invalidation go through useNutritionSettingsSync. Still open: the import half only fires while the admin page is mounted (onBeforeUnmount stops the poll), so an import that finishes after navigating away leaves the recipe list stale; other devices are the known flag-refresh seam.

## [OPEN] FU-792 — `seed_showcase.py` has no structured- or image-mode recipe
- **Raised:** 2026-08-31 (dense-seed unit; the surviving half of the now-resolved FU-754)
- **Type:** finding
- **What:** The dense dev seed now carries both faces — a ten-step structured
  recipe with sub-steps, sections and per-step links, and a five-photo image
  recipe — so the *dev* half of FU-754 is closed. `seed_showcase.py` (the demo
  dataset) is still 100% `steps_mode: 'freeform'`, so the public demo shows only
  one of cook mode's three faces.
- **Why deferred:** R-007 — the ask was a dev dataset. The showcase is a
  different audience with a different bar: its photos are the ones strangers
  see, so it wants real food photography rather than the drawn step cards the
  dev seed uses (`scripts/generate_seed_dense_images.py`), which is a content
  decision, not a code one.
- **Recommended resolution:** opportunistic — next time the showcase dataset or
  the demo instance is touched. The mechanism is already proven: build the
  recipe, then call `replace_sections_for_recipe` / `replace_steps_for_recipe` /
  `replace_step_images_for_recipe` after a `save_changes()` (R-064), exactly as
  `seed_dense.py` does.
- **Progress (2026-11-06):** Spaghetti Aglio e Olio is now a structured recipe (three steps, linked ingredients, tools, hints, timers); reset_showcase run against a scratch SQLite DB 2026-11-06 succeeds (1 structured recipe, 3 steps, 2 step tools). Still open: an image-mode recipe needs real food photos (owner content call).

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

## [OPEN] FU-735 — per-serving `kcal` is a masthead fact but isn't in the masthead edit grid
- **Raised:** 2026-08-23 (recipe-view feedback batch)
- **Type:** leftover.
- **What:** the masthead's edit face carries name, collection, cuisine, category,
  serves, prep, cook, difficulty and when. **Per-serving kcal** is displayed as a
  fact but is still only editable from the "Calories" disclosure below (and in
  complex nutrition mode it's server-derived, so it isn't editable at all) — so
  one visible fact doesn't flip with its neighbours.
- **Why deferred:** scope — the owner's batch didn't name it, and the right
  answer depends on whether simple-mode kcal should live in the masthead at all
  now that the disclosure list is shorter.
- **Recommended resolution:** opportunistic — next time the recipe masthead or
  the nutrition mode split is touched.

## [OPEN] FU-730 — `Recipe.updated_at` is stamped by the PATCH handler only
- **Raised:** 2026-08-24 (recipe-view feedback batch).
- **Type:** finding.
- **What:** the new edit stamp is written in `update_recipe.handle`. Deliberate
  — cooking, favouriting and meal-pool adjustments change what *happened* to a
  recipe, not what it is, and the version panel would be useless if "last
  updated" moved every time you cooked. But two writers do change the recipe's
  content and don't stamp it: the **URL/text importer**
  (`import_recipe_from_content.py`) when it writes into an existing recipe, and
  any future bulk/vocabulary migration that rewrites recipe rows in place.
- **Why deferred:** the importer's overwrite path isn't reachable from the
  recipe page (FU-689 closed won't-do), so nothing user-visible is wrong today.
- **Recommended resolution:** opportunistic — whenever a second recipe write
  path is added, stamp it there too (or lift the stamp into the repository's
  save path for `Recipe`).
## [OPEN] FU-705 — `PriceHistoryChart` has no touch interaction
- **Raised:** 2026-08-21 (prices-surface UX investigation)
- **Type:** finding
- **What:** The chart binds `@mousemove` / `@mouseleave` only
  (`PriceHistoryChart.vue:2`), so on a phone it is a static picture — the
  crosshair and value tooltip are unreachable and no number can be read off it.
  Fix is pointer events (`@pointerdown` / `@pointermove`) or an explicit
  "no chart below `sm`" decision. Same component, secondary issues: no y-axis
  unit label (nothing stops $/L and $/kg sharing one axis), 5 series draw 5
  dashed baselines in the same faint style with 5 labels stacked in the same
  right gutter, and `preserveAspectRatio="none"` will distort if the SVG is ever
  CSS-scaled.
- **Why deferred:** read-only investigation.
- **Recommended resolution:** now — it is shared by the widget sheet and the page,
  so it pays off under either FU-703 outcome.
- **Progress (2026-11-06):** PriceHistoryChart binds pointer events, a tapped reading stays (only a mouse leave clears) and the host has touch-action: pan-y. Still open, the secondary issues: no y-axis unit label; multiple baselines share one style and stack their labels; preserveAspectRatio='none' is redundant while viewBox equals the measured size.

## [OPEN] FU-694 — route-change transitions: the last critique §6 bullet, deliberately deferred
- **Raised:** 2026-08-20 (DR-15 micro-motion pass).
- **Type:** deferred job.
- **What:** the UX critique §6 asked for route changes to stop being instant
  swaps. DR-15 covered everything else in that section — the four
  high-frequency gestures (D-010), and DR-8 had already handled the belief-chip
  reflow and the dashboard loading→content swap via the shared skeletons — but
  page-level transitions are not built.
- **Why deferred:** the app has now been bitten **twice** by sequencing state
  behind paint (the DR-8 splash wedge; DR-15's own first-draft rAF class write),
  which is what R-050/ADR-046 were written for this session. A route transition
  is precisely where that failure goes fatal rather than silent — a wedged
  `<Transition>` leaves the user on a blank or half-left page. It also has to
  co-exist with scroll restoration and the per-page skeletons. That's its own
  unit with its own risk, not a ride-along on a 120ms-feedback pass. (The verify
  pane already demonstrates the failure: its route transitions wedge in
  `dora-fade-leave-active` and never complete.)
- **Recommended resolution:** opportunistic — and only with a non-paint timeout
  driving the unmount (R-050), never `transitionend` alone.

## [OPEN] FU-684 — ~20 more `item.stock_level` readers carry the same R-032 exposure the buy verdict just proved live
- **Raised:** 2026-08-19 (stock-signal consolidation, Chunk 1).
- **Type:** finding.
- **What:** `GET /api/stock-items/<id>/buy-verdict` included `STOCK_LEVEL` on its
  load and *still* read `item.stock_level is None`, so `_stock_level_band` returned
  `"unknown"`, the `need` axis collapsed to thin-data, and the endpoint answered
  **`unsure/low` for every item** — including an out-of-stock one, which is its
  most confident `buy`. That is R-032's identity-map corollary biting with the
  `.include()` present: the session already tracked the instance with the
  relationship unset, and `contains_eager` didn't repopulate it. Belief's
  `recorded_sequence` read the same relationship and had the same exposure (it
  would have silently fallen through to its no-data path). Both now resolve the
  level by FK through the new
  `dora_api/features/stock_items/_level_access.py::resolve_levels_by_item`.
  **Not swept:** every other reader of the relationship — `alerts/get_alerts.py:215`
  (the attention engine — a silent `None` there suppresses the out/low alerts
  Chunk 3 is about to consolidate onto), `domain/recipe_cookability.py:62,109`,
  `assistant/confirm_actions.py:87,159,661`, `assistant/shopping_actions.py:39`,
  `assistant/tools.py:1012,1146,1454,1514,1515`, `alerts/act_on_alert.py:78`.
  Each needs the same question asked: is the instance guaranteed fresh on this
  query, or could the session hand back a noload-empty one?
- **Why deferred:** scope. The chunk's job was the cadence/constant consolidation;
  the verdict bug was found because D-11 made belief read the same field. Sweeping
  a dozen unrelated features unasked is the drive-by the standards warn against.
- **Fix shape:** audit the list above; where the read isn't provably safe, resolve
  by FK (`item._stock_level_id`) via `resolve_levels_by_item` rather than adding
  more `.include()`s — an include is what failed here. `get_alerts.py` is the
  highest-value one and Chunk 3 opens that file anyway.
- **Recommended resolution:** the alerts reader **with Chunk 3** (same file, same
  rebuild); the rest opportunistically. If several turn out to be live bugs, R-032
  needs a stronger "don't trust `.include()` alone" clause.
- **Progress (2026-11-06):** GetAlertsHandler.raw_alerts and stock_attention resolve levels by FK (resolve_levels_by_item); the assistant expires the session before each read-only tool; shopping_actions / act_on_alert no longer read .stock_level. Still open: confirm_actions.py ~152 and ~642 trust .include(); recipe_cookability.missing_stock_item_names_for has no levels_by_item (callers get_recipes.py ~614, tools.py ~1174); and the expire_all in run_tool is only safe while every tool is read-only.

## [OPEN] FU-671 — `text-color="white"` on semantic chips fails the D-002 contrast floor
- **Raised:** 2026-08-17 (expiring-ingredient chips).
- **Type:** finding (D-002 / R-035).
- **What:** measured against the actual theme tokens, white text on the **warning** chip
  is **1.7–3.0:1** and on the **negative** chip **2.96–3.9:1**. D-002's floor for text
  this size is **4.5:1**. `text-color="dark"` clears it everywhere (warning 5.5–9.5,
  negative 4.3–5.6). **17 call sites** app-wide (`color="warning"` + white ×9,
  `color="negative"` + white ×8) — including the "Uses N expiring" badge on the cookbook
  card and compact row, and the **Missing** chip sitting directly beside the new at-risk
  chips on the recipe page.
- **Why deferred:** the owner asked for an ingredient chip; flipping 17 chips across
  eight surfaces is a design sweep that wants one decision and one screenshot pass.
  The new chips were built correct (`dark`), so until the sweep lands the recipe
  ingredient row shows a white-ink Missing chip next to dark-ink at-risk chips.
- **Recommended resolution:** now-ish — it's mechanical, and the mixed treatment on the
  recipe page is visible. Worth deciding at the same time whether B2's prescribed
  "`-soft` background + semantic ink" replaces solid semantic chips generally.
- **2026-10-23 (finalisation Stage 1):** now **24 sites / 16 files** — `AlertKindAvatar, AlertsBell, chips/DiscountChip, dashboard/PriceDropsCard, dora/DoraChat, dora/PriceHistoryBottomSheet, products/ProductCard, recipes/ExpiringChip, DoraHelpPage, PriceHistoryPage, RecipeCookMode, settings/AdminDataBackupRestore, settings/ApiAccessSettings, settings/AuditLogSettings, StockItemDetailPage, StockOverview` (CHUNK_20 §0 table). Pairs with FU-674's `--text-on-*` tokens.
- **2026-10-27 (finalisation 20-R11 sweep, unit 30):** six more sites flipped to `dark` (price history above-baseline chip, backup duplicate chip, API-access pending + unmapped badges, audit-log severity chips ×2). Left on purpose: primary/accent/secondary + white (`--text-on-primary` is the sanctioned pairing; `RecipeCookMode` carries its own note), `DiscountChip` positive + white, `PriceHistoryPage` series colours, `AlertKindAvatar` (decorative icon). The tint-vs-solid question above is still the owner's.
- **Progress (2026-11-06):** the mechanical part is done: no warning/negative chip pairs text-color white; what remains with white ink is primary (sanctioned), DiscountChip, CookIngredientsPanel's secondary chip (commented), the AlertsBell badge and AlertKindAvatar. Still open: only the owner's 'tint vs solid semantic chips' question.

## [OPEN] FU-667 — Client-side filtering over a fully-hydrated collection is the real
  design smell behind FU-668
- **Raised:** 2026-08-17 (cookbook truncation bug).
- **Type:** finding.
- **What:** paging-until-exhausted fixes the correctness bug but keeps the underlying
  posture: the cookbook downloads every recipe (with ingredients, stock levels and
  locations eager-loaded) to filter and search 20-odd axes in the browser. That's a
  growing payload and it sits awkwardly against R-003 — the server already owns
  `cookable` / `max_missing` / `expiring_within_days` as query params, and the client
  re-implements the rest. Not urgent at personal-cookbook scale (68 recipes today);
  worth a decision before it's 500.
- **Why deferred:** moving 20 filter axes server-side is a design job, not a bug fix,
  and the charter's anti-creep principle says fix the reported defect first.
- **Recommended resolution:** later — when a cookbook/pantry gets big enough to feel
  it, or opportunistically alongside any other recipes-list work.

## [OPEN] FU-664 — Handler call sites can drift from entity signatures silently
- **Raised:** 2026-08-17 (first-setup onboarding bug).
- **Type:** finding.
- **What:** `SeedDemoHandler` was still passing `image=None` to `StockItem` long after
  the entity dropped the field. Nothing caught it because the only path that constructs
  those rows is gated behind an idempotency check that's already satisfied on every
  seeded/dev/e2e database — so a genuine first install was the *only* way to hit it.
  Worth a sweep for other "only runs once, on a truly empty DB" branches (the rest of
  the onboarding seeders, `seed_showcase`, the demo-reset path) that no test reaches.
- **Why deferred:** out of scope for a bug fix; the reported defect itself is fixed and
  now covered by `tests/e2e/dora_api/test_onboarding_seed_demo.py`.
- **Recommended resolution:** opportunistic — or now, if a fresh-install smoke test is
  wanted before the next release.

## [OPEN] FU-657 — The new micronutrients' Open Food Facts scale factors are unverified against a real response
- **Raised:** 2026-08-17 (nutrition micronutrients build).
- **Type:** finding.
- **What:** the fifteen new nutrients carry OFF `off_scale` values derived from OFF's
  documented convention that every non-energy `*_100g` nutriment is normalised to
  **grams** — so minerals are ×1000 (g→mg) and the µg-declared vitamins are ×1,000,000.
  That's the same reasoning the existing (and correct) sodium ×1000 rests on, and the
  USDA side of all fifteen is exercised by the importer's own `(name, unit)` matching.
  But **no test and no live OFF response** covers the new keys, so a mis-scaled vitamin
  would read as a 1000× error on a number people watch — the exact hazard the sodium
  comment in `nutrients.py` warns about.
- **Why deferred:** verifying it properly means hitting the live OFF API (the suite
  deliberately keeps network sources off, and the local catalogue is USDA), so it's a
  live-lookup check rather than a unit test.
- **Recommended resolution:** opportunistic — next time OFF lookup is switched on, scan
  a packaged good with a rich panel and sanity-check calcium/vitamin C against the pack.
  A wrong order of magnitude is obvious at a glance.

## [OPEN] FU-636 — USDA Foundation dataset URL carries a release date and will eventually 404
- **Raised:** 2026-08-14 (nutrition complex-mode build).
- **Type:** finding.
- **What:** FDC bulk-download filenames embed the release date
  (`FoodData_Central_foundation_food_csv_2026-04-30.zip`). SR Legacy is frozen
  so its URL is stable forever, but Foundation ships a couple of times a year,
  so the built-in default will 404 after the next release.
- **Why deferred:** handled defensively rather than solved — the import endpoint
  accepts a `url` override, and a 404 is caught and rewritten to "that release
  has probably been superseded; paste the current CSV link". No schema column
  was added for it (R-007).
- **Recommended resolution:** opportunistic — if it bites, either expose the
  override in the admin UI (the API already supports it) or scrape the current
  link from the downloads page at import time.
- **Update 2026-08-15 (FU-639):** still open, but the *host* was wrong too and is
  now fixed (`www.usda.gov` 403s automated downloads; `fdc.nal.usda.gov` serves
  them). The 2026-04-30 Foundation release is currently live on the correct host,
  so this is still a future-dated risk rather than a present break, and the 404
  path now has an actionable message pointing at the downloads page.

---

## [OPEN] FU-579 — `quasar dev` vite-checker overlay: pre-existing type errors block fresh-browser interaction
- **Raised:** 2026-07-18 (building the drive.mjs app driver)
- **Type:** finding
- **What:** `quasar dev` runs vue-tsc in watch mode via vite-plugin-checker, and its
  full-screen error overlay intercepts ALL pointer events in any fresh browser session.
  The errors are pre-existing: `e2e/bulk-waste.spec.ts` ×12 `noUncheckedIndexedAccess`
  ("Object is possibly 'undefined'" on `items[name]` index access) + `src-pwa/*` ×5
  (workbox module types / `ServiceWorkerGlobalScope` not in the SPA-mode tsconfig lib).
  The tree's standalone `vue-tsc` task has been reported clean in past sessions, so the
  dev-watch config evidently checks a wider file set than the CI task — worth aligning.
  `drive.mjs` works around it by CSS-hiding the overlay; a human dev opening `quasar
  dev` fresh sees the overlay too.
- **Why deferred:** driver-tooling unit; fixing spec types + tsconfig scoping is its own
  small change (R-008).
- **Recommended resolution:** opportunistic — null-guard the index accesses in
  bulk-waste.spec.ts, exclude `src-pwa` from the SPA-mode checker (or add webworker lib),
  and confirm dev-watch and the `vue-tsc` task check the same set.
- **Update 2026-07-18 (verify Batch 3 session):** the **bulk-waste half is FIXED** —
  the ×12 index-access errors turned out to hard-fail `npx quasar build` too (exit 2,
  no `dist/spa`), breaking `npm run test:e2e` from a clean tree; `itemsByName` now
  returns a throwing accessor and `vue-tsc --noEmit` is clean. Note the earlier "not
  visible in the vue-tsc task" observation was wrong — plain `vue-tsc --noEmit` did
  report them. **Still open:** the `src-pwa/*` ×5 workbox-type errors in the dev-watch
  checker only (they do NOT appear in `vue-tsc --noEmit` or `quasar build`), so the
  overlay problem in `quasar dev` may persist — re-test `quasar dev` fresh and scope
  the checker if it still trips.
- **Progress (2026-11-06):** src-pwa no longer has custom-service-worker.ts and src-pwa/tsconfig.json sets the WebWorker lib, so the five workbox errors should be gone. Not confirmed: run `quasar dev` in a fresh browser and check no checker overlay appears, then close.

## [OPEN] FU-363 — Cross-cutting / niche feedback (Bucket C in COVERAGE_GAPS) — 4 of 8 actioned
- **Raised:** 2026-07-01 (COVERAGE_GAPS sweep).
- **Type:** deferred job (bundle — 8 sub-items; **items 2, 5, 6, 7 actioned 2026-07-15, 4 remain**).
- **What:** `COVERAGE_GAPS.md` Bucket C cross-cutting items with no per-surface home:
  1. **[OPEN]** Full systems QA test doc (final regression walkthrough of every feature). User wants done LAST to capture the final product.
  2. **[ACTIONED — design, then WON'T-DO for self-host 2026-07-16]** Usage analytics / telemetry. Designed in [`PROPOSAL_USAGE_TELEMETRY.md`](docs/04_proposals/PROPOSAL_USAGE_TELEMETRY.md), then owner decided **not to build for self-host** — the ask is the maintainer's and only pays off as hosted aggregate analytics; the self-host efficiency lens was dropped as not useful to the operator. Whole topic **relocated to `OPTIONAL_SAAS_AND_MANAGED_DEPLOYMENT.md`** (hosted-only). FU-566 resolved WON'T-DO (see `_RESOLVED`).
  3. **[OPEN]** UI uniqueness / polish design pass — "looks just okay, not polished/unique."
  4. **[OPEN]** Push notifications between users (share a shopping list via notify).
  5. **[ACTIONED 2026-07-15 — decided: CUT]** Kivy P2P sync branch — no home in the current client-server architecture; recorded in [`MULTI_USER_READINESS.md`](docs/05_investigations/MULTI_USER_READINESS.md) §5.1.
  6. **[ACTIONED 2026-07-15 — shipped]** Main menu bottom border — removed the `q-header bordered` border per the feedback lean (`MainLayout.vue`); browser-verify queued.
  7. **[ACTIONED 2026-07-15 — declined]** Real ALDI/IGA logos — WON'T-DO (trademark/licensing risk; Dora ships zero logos by design per `StoreLogo.vue`). Existing workaround: per-store logo **upload** already exists (`StoresSettings.vue`). Recorded in `DORA_FOLLOWUPS_RESOLVED.md`.
  8. **[OPEN]** General UI consistency — cross-cutting.
- **Why deferred:** no per-surface home; the 4 remaining are Phase 3/4-timed or design-only.
- **Recommended resolution:** split into per-item FUs *only when picked up*. Remaining: items 1 (QA test doc) + 3 (polish pass) + 8 (UI consistency) are natural Phase-4 gates; item 4 (push notifications) is a Phase-3-ish feature build. Close this bundle once those four are picked up.

