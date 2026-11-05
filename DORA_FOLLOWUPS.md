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

## [OPEN] FU-917 — `PriceAlert` carries a dead column and a misleading name
- **Raised:** 2026-10-15 (price watches now fire as the `price_drop` alert)
- **Type:** leftover
- **What:** `last_fired_at` was meant for a worker that never existed and is
  still written by nothing (the alert's episode key does the "fire once" job
  now). `threshold_unit_price` is compared with the product's shelf
  `price_now`, which is what both the explorer and the new watch dialog ask
  for, so the column name says "unit" when it means "shelf price". Drop the
  first and rename the second (see FU-911 / FU-914 for the unit-price muddle).
- **Why deferred:** a schema change outside the batch's scope.
- **Recommended resolution:** with FU-914.
- **Progress (2026-10-24):** the dead `last_fired_at` column is dropped (migration `b8d2f4a6c1e3`, finalisation 10-R39). The `threshold_unit_price` rename remains, with FU-911/914.

## [OPEN] FU-916 — Alert interaction rows for finished episodes are never pruned
- **Raised:** 2026-10-15 (alerts rework, ADR-090)
- **Type:** deferred job
- **What:** alert keys now carry their episode (R-093), so every expiry date,
  level change and shop date that a user snoozed or dismissed leaves an
  `AlertInteraction` row that will never match again. Harmless for correctness,
  unbounded over years. A nightly job could delete rows whose key no longer
  matches any live alert and that are older than the longest discard window.
- **Why deferred:** no measurable cost yet.
- **Recommended resolution:** opportunistic, or when the table passes ~10k rows.

## [OPEN] FU-911 — `unit_price` on the product price axis is a *pack* price
- **Raised:** 2026-09-13 (shelf-denominator batch)
- **Type:** finding
- **What:** on the product side, `unit_price` is `ProductOffer.price_now` — the
  price of the pack, not a price per measure. It flows to
  `PriceHistoryPage`'s headline and all-time-low figures (rendered with no
  denominator, which is correct for a pack price) and, more consequentially, to
  `threshold_unit_price`: a "tell me when it drops below $X" alert reads as a
  per-unit threshold by its name and is a per-pack one in fact. Nothing renders
  wrongly today; the name says something the value isn't, on the one axis where
  per-unit and per-pack prices sit next to each other.
- **Why deferred:** out of scope — the owner's report was about *displayed*
  denominators, and these display correctly. Renaming crosses the DTO, the SPA
  service types, the alert entity and a migration-backed column, which is its
  own unit.
- **Recommended resolution:** opportunistic — fold into the next piece of work
  on the prices surface (it is naturally part of the **FU-703** keep/cut call).

## [OPEN] FU-909 — two implementations of the typeable count tile
- **Raised:** 2026-09-12 (meal-planner feedback batch, sixth pass)
- **Type:** finding
- **What:** `NumberStepper` gained an `editable` tile so the meal menu's servings
  control could be typed into; `MealPlanRecipeRow`'s cooked-count
  (`.mp-row__tile` + `.mp-row__step`) has had its own since 2026-09-03. Same
  control, same commit-on-Enter/blur behaviour, two stylesheets — exactly the
  shape R-001 exists to stop.
- **Why deferred:** converging them means porting the rail row's hover-hiding
  (a list affordance the menu deliberately doesn't want) and its 30/44px sizing
  into the shared component, i.e. re-skinning a control on a different surface
  in the middle of a batch scoped to the planner's cards.
- **Recommended resolution:** opportunistic — next time either control is
  touched, or as a small unit of its own.

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

## [OPEN] FU-901 — no test pins the recipe-DTO cache against the flags that change what the server puts in it
- **Raised:** 2026-09-09 (cookbook + recipe-view feedback batch)
- **Type:** finding
- **What:** the "health stars don't appear until I refresh" defect was a cache
  the flag refresh didn't reach: `nutrition_rating_scheme` and `nutrition_mode`
  change **what the server computes into every recipe DTO**, so the flag map
  and the cached recipe list have to be dropped together. Fixed at both call
  sites (Nutrition settings, Region's nudge) by adding
  `recipeStore.invalidateRecipes()` beside the existing `refreshFlags()`. That
  pairing is a convention held by hand in two files, and the next writer of a
  recipe-affecting setting has nothing telling them about it — which is exactly
  how these two came to be missing it.
- **Why deferred:** the durable fix is structural, not a test: either the
  recipe store watches the flags it depends on (rejected today as the kind of
  action-at-a-distance R-019 exists to prevent), or `useFeatureFlags.refresh()`
  grows a documented list of caches it drops (a layering inversion — the flags
  composable would import the stores). Both want a design call rather than a
  patch inside a feedback batch.
- **Recommended resolution:** opportunistic — next time either `recipeStore`
  or `useFeatureFlags` is open for other work.

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

## [OPEN] FU-890 — four money inputs are still hand-rolled after `MoneyInput` landed
- **Raised:** 2026-09-06 (products program, batch G)
- **Type:** finding — half-finished migration
- **What:** batch G introduced `components/MoneyInput.vue` (currency symbol as a
  `prefix`, value settles to 2dp on blur, symbol from the money policy per
  D-006) to answer feedback PH-4, and adopted it on **Price History only** —
  that being G's surface. The other money fields are untouched and still
  disagree with each other:
  `components/dora/PriceEntry.vue` (uses `prefix`, no rounding),
  `components/shoppingList/ShoppingListPlanRow.vue` (bare `type="number"`),
  and the money inputs on `DashboardPage` and `settings/MoneySettings.vue`.
- **Why deferred:** those live on shopping-list, dashboard and settings
  surfaces, outside the products program. Migrating them blind inside a UI
  batch — `PriceEntry` in particular carries validation rules and a
  multipack mode — is how a refactor turns into a regression.
- **Known limitation to carry into the sweep:** an `<input type="number">`
  cannot *display* trailing zeros, so the value normalises to 2dp (3.999 → 4)
  but renders "4", not "4.00". Showing "4.00" needs a text input with masking,
  which is a bigger decision than this component should make alone.
- **Recommended resolution:** opportunistic — next time any of those four
  surfaces is touched, or as a deliberate small sweep. Cross-ref R-001/R-002
  (componentisation-first) and D-006.

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

## [OPEN] FU-863 — A cook batch straddling today loses its link when only one forward day is left
- **Raised:** 2026-09-03 (meal-planner owner batch — found during the multi-day QA walk)
- **Type:** finding
- **What:** a cook batch whose **cook day is in the past** keeps its leftover days
  linked, and this batch fixed the case where an unrelated edit split it in two
  (the reattach in `update_meal_plan`). But if the batch is left with a *single*
  forward leftover day, that day silently becomes a standalone meal. Walked live:
  a Wed-cooked Sunday Ragu with Thu + Fri leftovers, Thursday stepped to zero
  servings — Friday came back with its "Leftovers" marker gone.
- **Why it happens, and why it isn't simply a bug in the new code:** past entries
  are immutable and the client never resends them (FU-595), so a payload can only
  ever carry the *forward* members of a straddling batch. When that is one entry,
  the client's `dissolveOrphanCookKeys` strips the `cook_key` — because the server
  refuses a one-member group (`validate_cook_groups`: "a cook batch must cover at
  least two days"), and it is right to for a batch that is genuinely one day. The
  two rules are individually correct and jointly wrong for this shape.
- **Fix shape:** the server is the only party that can see both halves. Have the
  update handler count a group's *preserved* members alongside the payload's
  before validating, and let a one-member payload group survive when the same
  batch has a preserved entry. That means the client must stop stripping the key
  in that case, which it cannot detect — so the honest version is for the client
  to always send the key and let the server decide, i.e. move the orphan-dissolve
  rule server-side. That is a contract change to the write path, not a patch.
- **Impact:** cosmetic and small — a leftovers day loses an eyebrow. Nothing is
  double-cooked and no ingredient demand changes (the pool model already treats
  a lone entry as its own cook).
- **Recommended resolution:** later, with any pass over the meal-plan write path.

## [OPEN] FU-858 — Nutrition-matching badge fetches for every user in complex mode
- **Raised:** 2026-09-03 (owner feedback batch — settings/Nutrition matching)
- **Type:** finding
- **What:** the new sidebar count (owner ask: *"count of unmatched items same as
  unlinked ingredients would be good"*) hydrates from
  `GET /api/nutrition/unmatched-items`, which on this seed returns the full 41
  rows — the whole unmatched list — to render one integer. `unlinkedIngredients`
  has exactly the same shape and the same cost, so this is consistent rather than
  novel, but it now happens twice per settings mount.
- **Why deferred:** it's a real but small waste, and fixing it properly means a
  count-only endpoint (or a `?count_only=1` on both), which is server work beyond
  a settings-polish batch. R-003 stays satisfied either way — the server owns the
  number; the client just over-fetches to read it.
- **Recommended resolution:** opportunistic, when either endpoint is next touched.

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

## [OPEN] FU-851 — Planned demand goes stale after a plan edit anywhere but the stock detail page
- **Raised:** 2026-09-03 (owner batch — planned-demand signal)
- **Type:** finding
- **What:** `usePlannedDemand` is a module-level cache, like `usePantryBeliefs`.
  It is invalidated on a level change from `StockItemDetailPage`, because that
  changes the urgency grade. It is **not** invalidated when the thing it is
  actually derived from changes: adding, moving, deleting or consuming a meal
  plan entry, or bumping a recipe's cooked pool. Within one SPA session, a user
  who plans three meals and then opens a stock item sees the pre-edit counts.
- **Why deferred:** the same exposure the belief cache has had since P8-07 (a
  finished shop changes a belief and nothing invalidates it either), so it is a
  pattern to fix once rather than a bug to patch here. The honest fix is
  probably an invalidation bus the meal-plan and cook mutations publish to,
  which both caches subscribe to — that is its own unit.
- **Recommended resolution:** opportunistic, with any pass over the overlay
  caches. Cross-ref: R-074, ADR-071.
- **Progress (2026-10-24, finalisation 07-R6):** `usePantryBeliefs` and `usePlannedDemand` are now one shape, `composables/createOverlayCache.ts` (+ spec), so an invalidation bus has one subscriber type.

## [OPEN] FU-847 — Four hosts now measure their own box to size the SVG chart
- **Raised:** 2026-09-02 (FU-833 — dropping ECharts)
- **Type:** finding (R-001)
- **What:** `PriceHistoryChart` is sized in **px**, not by CSS, so every host
  measures its own content box with a `ResizeObserver` and passes `:width`.
  ECharts' `autoresize` did this internally; losing it is the one thing the swap
  cost. The same ~12 lines (`measure()` + observer + `onBeforeUnmount` cleanup)
  now exist in **four** places: `PriceHistoryPage.vue`,
  `PriceHistoryBottomSheet.vue`, `reports/PriceTrendsCard.vue` and
  `reports/ItemPriceMoversCard.vue`. Two of them differ slightly and for real
  reasons (one subtracts card padding, one re-attaches when the host appears as
  the card leaves its empty state), which is exactly how a fourth copy becomes a
  fifth that is subtly wrong.
- **Two ways out, and the second is better:** extract `useMeasuredWidth(elRef)`;
  or teach the chart to fill its container (a `viewBox` + `width: 100%` and
  internal coordinates in a fixed space), which deletes the prop and the
  observers together. The second is a change to the chart's coordinate handling
  and wants its own unit, since `preserveAspectRatio="none"` currently means a
  CSS-scaled SVG would distort (already noted in
  `PRICES_SURFACE_UX_ASSESSMENT.md` §5.5).
- **Why deferred:** ADR-070 called it at the third and fourth copies and chose to
  ship the swap rather than widen it. Not urgent: the copies work, and they were
  driven live on all four surfaces.
- **Recommended resolution:** opportunistic — with [[FU-705]] (the chart's
  missing touch interaction), since both are changes to the same interaction
  layer. Cross-ref: ADR-070, R-073, R-001.

## [OPEN] FU-846 — `/price-history`'s per-product cards still read `seriesColour(i)` by list position
- **Raised:** 2026-09-02 (FU-833)
- **Type:** finding
- **What:** the chart assigns a series' colour by its index in the array it is
  handed; `PriceHistoryPage.vue` colours its picker chips and comparison cards by
  calling `seriesColour(i)` with the index of *its own* `series` array. Those
  agree today only because `productSeriesToChart` preserves order 1:1. The moment
  the chart drops a series with no plottable points — which it already does,
  `plottable` filters them — the chart's index and the page's index diverge, and
  a chip is painted the colour of a different product's line. Not currently
  reachable: the page only lists products the API returned series for, and a
  series with zero points still renders a card. It is a latent off-by-one, not a
  live defect.
- **The fix is to key the colour, not the position:** have the adapter stamp each
  `PriceChartSeries` with its resolved colour, and let both the chart and the
  page read `series.colour`. That also kills the "call it inside a reactive
  scope" caveat on `seriesColour`, since the value would be computed once where
  the array is built.
- **Why deferred:** it is not reachable from the current UI, and the fix touches
  the colour contract for all four consumers — worth doing deliberately rather
  than inside the ECharts removal.
- **Recommended resolution:** opportunistic, or with [[FU-843]] item 1 (the
  categorical ramp's collision), which is the same "who owns a series' colour"
  question. Cross-ref: R-073, `useThemePalette.seriesColour`.

## [OPEN] FU-844 — Two pages have now shipped the same feature-flag race; the guard should be the composable's job
- **Raised:** 2026-09-02 (Reports chunk 1 — found by driving it live)
- **Type:** finding (R-003-adjacent)
- **What:** a gated loader written as `if (!moneyEnabled.value) return;` is a
  **race**, not a gate. `useFeatureFlags` reads `/api/health` once per document
  and the map is empty until that resolves, so on a cold load every gated loader
  early-returns and nothing re-runs it — the card then renders its *empty* state
  forever, which is the honesty failure the whole error-state chunk exists to
  kill. The dashboard hit this and fixed it with per-gate `watch`ers (**FU-586**,
  and the comment there explains it well); `ReportsPage.vue` reproduced it
  verbatim on its first live run — only the three ungated reports fetched, and
  the six money cards said "no completed shopping lists" on a seed with five
  stores of spend. Fixed the same way, so there are now **two** copies of the
  workaround and any third gated page will write a third.
- **The shape of the fix:** `useFeatureFlags()` already tracks `flagsLoaded`.
  Either expose the load promise (`await flagsReady()`) so a page can simply not
  fetch until the answer exists, or give the composable a `whenEnabled(flag, fn)`
  that owns the watcher. Either way the knowledge — *"a false flag might mean
  'not yet'"* — stops living in each caller.
- **Why deferred:** it is a small refactor across two pages plus the composable,
  and both call sites are correct today; doing it inside a defect chunk would
  widen the diff for no user-visible change.
- **Recommended resolution:** opportunistic — with [[FU-832]] (the shared card
  catalogue + `useCardLayout()`), which is already touching exactly this seam on
  both pages. Cross-ref: FU-586, `DashboardPage.vue:1629`, `ReportsPage.vue`.
- **Progress (2026-10-27, finalisation 12-R23):** the per-card failure half both pages shared is now
  `composables/useSlotLoader.ts` (+ spec). The flag-race watchers this FU is about are still two copies.

## [OPEN] FU-843 — Reports' categorical colour ramp collides at six entries, and the no-store bucket has no hatch
- **Raised:** 2026-09-02 (Reports chunk 2 — measured live)
- **Type:** finding (D-001)
- **PARTIALLY DONE 2026-09-02 (Reports chunk 3). Item (2) is closed; item (1)
  survives but is smaller than it was.**
  - **(2) done** — the donut is gone and both spend axes render
    `ProportionBar`, **extracted from `StoreSpendCard.vue`** so the hatch, the
    zero-value floor and the unassigned bucket are one implementation rather
    than a second copy (R-001). Verified live: the no-store segment computes
    `repeating-linear-gradient(...)` over `--border-strong`, and its legend
    swatch is hatched to match — parity with the shopping list, not a lookalike.
  - **(1) still open, and downgraded** — `colourFor` still hashes into a sealed
    `--chart-1..6`, so two stock groups can still share a hue. What changed is
    that **colour is no longer the channel that ties a value to a name**: the
    donut it labelled is gone, and each group is now a labelled row carrying its
    own name, dollar figure and share. The collision went from misleading to
    cosmetic. The fix is still to rank-assign rather than hash.
- **What:** two related colour problems on the two legends, both visible on the
  dense seed at :5171.
  1. **`colourFor` hashes into `--chart-1..6`, so with more than a handful of
     buckets two adjacent rows share a hue.** Measured: "Pantry staples" and
     "Fruit & Veg" both render `rgb(249,208,6)` in the spend-by-category legend.
     Harmless-looking, but the legend's whole job is to tie a slice to a name.
     Stock groups routinely run to eight or more, which is also §4.6's argument
     for killing the donut outright.
  2. **The "No store set" bucket is drawn as a flat colour.** The shopping list
     solves the same bucket with a **hatched** themed grey, precisely because no
     flat grey can be guaranteed to separate from a logo-derived brand colour
     (D-001 — never distinguish by hue alone). Chunk 2 stopped it being handed a
     *store identity* colour (it was drawing the same slate as the farmers market
     directly above it) and gave it `--text-muted`, which is honest but is not
     parity.
- **Why deferred:** the real fix for both is §4.6's — replace the donut + legend
  with the shopping list's own `.sl-store-bar`, which already solves the
  zero-value bucket, the unassigned bucket **and** the hatch. Building a second
  hatch here would be the third copy of a component the review wants shared.
- **Recommended resolution (amended):** item (1) opportunistically, with
  chunk 5's colour sweep, or [[FU-846]] — which is the same "who owns a series'
  colour" question, and the better home now that [[FU-833]] has shipped. It is a
  cosmetic ranking change, not a legibility defect. Cross-ref:
  `REPORTS_PAGE_REVIEW.md` §4.6, `components/ProportionBar.vue`.
- **Progress (2026-10-27, finalisation 12-R13):** the hash now lives in one place, `useThemePalette.categoricalColour(key)`
  over the `seriesColour` ramp (Reports' six hex fallbacks went). Rank-assigning instead of hashing is still the fix
  for the collision, and now changes one function.

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

## [OPEN] FU-802 — the planner's rail row is still the third copy of the list-row chrome (see FU-791)
- **Raised:** 2026-09-01 (meal-planner owner batch)
- **Type:** finding
- **What:** not a new problem — a note that this batch touched
  `MealPlanRecipeRow.vue` (removed its meta line and the log-cook button,
  restyled the pool controls) **without** taking the `.dora-list-row` extraction
  [[FU-791]] asks for. The R-001 carve-out comment in that file is still accurate
  and still the third copy.
- **Why deferred:** same reason as FU-791 — the extraction re-skins `StockItemRow`
  and `RecipeRow`, two surfaces the owner has signed off visually, and this unit's
  scope was the planner.
- **Recommended resolution:** opportunistic, with FU-791 — this entry exists only
  so the next reader of FU-791 knows the file moved since it was written.

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

## [OPEN] FU-798 — sweep the other full-page surfaces for a pinned-palette shell (R-067)
- **Raised:** 2026-09-01 (stocktake feedback batch)
- **Type:** follow-up
- **What:** the stocktake runner pinned its shell to `--palette-neutral-900`
  under every theme; that's now fixed and generalised as **R-067**. The same
  instinct is available to any other route-level "focus mode". Grep
  `background: var(--palette-` across `web_app/src/pages` + `src/components`
  and check each hit against R-067 — cook mode and the shopping-list run face
  are the named candidates.
- **Why deferred:** out of scope for a stocktake feedback batch, and each hit
  needs its own look at whether the surface is genuinely inverted-by-design (a
  scrim, a toast) or just hard-coded.
- **Recommended resolution:** opportunistic — next time either surface is open.

---

## [OPEN] FU-795 — two chip selects bypass `BaseSelect` and so miss every rule it owns
- **Raised:** 2026-08-31 (recipe-view feedback batch)
- **Type:** finding
- **What:** `ReportsPage.vue` (the price-picker) and
  `settings/AuditLogSettings.vue` (the severity filter) use a raw `q-select`
  with `multiple use-chips` rather than `BaseSelect`. They therefore miss
  everything BaseSelect exists to decide — the menu-vs-dialog rule on mobile,
  the dialog close bar, the empty-text handling — and they're outside the
  chip-wrap fix landed this round, so they may still run chips off the side of
  their field. (Not confirmed either way: the audit-log route 404'd from
  `/settings/audit-log`, so it wasn't reachable to measure.)
- **Why deferred:** out of scope for a recipe-page batch, and it's a
  conversion, not a patch.
- **Recommended resolution:** opportunistic — when either page is next touched.

## [OPEN] FU-793 — the dense seed has no missing ingredient that also carries substitutes
- **Raised:** 2026-08-31 (recipe-view feedback batch)
- **Type:** finding
- **What:** the recipe row's missing chip has three states, and **two of them
  have no fixture in either seed**: every missing ingredient in `seed_dense.py`
  (Pecorino Romano, Sourdough Loaf, Tasty Cheese, Orange Juice) has zero
  recorded substitutes, so `Missing · N swaps` and `Swap ready` can only be seen
  by faking the API response. Same class of gap as FU-754 (no structured/image
  cook-mode fixture): a surface that can't be reached from the seed is a surface
  nobody looks at. `Extra Virgin Olive Oil` has a substitute but is stocked.
- **Why deferred:** a seed change is its own unit, and this batch was verified
  by intercepting the `/stock-items/:id/detail` response instead.
- **Recommended resolution:** later — next time `seed_dense.py` is touched.
  Cheapest fix: give one already-missing item a substitute that's in stock and
  another a substitute that isn't.

## [OPEN] FU-791 — the list-row chrome is now a third private copy (bordered card + accent hover)
- **Raised:** 2026-08-30 (meal-planner rail, Unit 2)
- **Type:** finding
- **What:** the "bordered flat surface, accent-tinted hover, no lift" list-row
  look exists three times now. It originated on `StockItemRow.vue`, was copied
  to `RecipeRow.vue`, and `MealPlanRecipeRow.vue` (new) is the third. The rail
  brief's §4.5 explicitly asked for it to be **promoted to a shared class**
  rather than copied again, citing the `.dora-subbar` extraction as precedent
  (R-022 / ADR-018).
- **Why deferred:** doing it properly means re-skinning `StockItemRow` and
  `RecipeRow` — two heavily-used surfaces the owner has signed off visually —
  inside a work unit whose scope was the meal-planner rail. That is exactly the
  adjacent-surface creep R-007 exists to stop, and a silent re-skin of the stock
  row is how you get a "why does my pantry look different" report. The
  duplication is commented in place in `MealPlanRecipeRow.vue` naming R-001.
- **Fix shape:** extract a `.dora-list-row` class (border, radius, surface,
  hover tint, focus ring) into `app.scss`, then have all three rows compose it
  and keep only their own layout. Diff the three current declarations first —
  they are *not* byte-identical, so the extraction has to pick a winner per
  property and that choice is visible on the stock row.
- **Recommended resolution:** opportunistic — pairs naturally with [[FU-691]]'s
  off-token stylesheet sweep or the next design-remediation chunk, since all
  three are the same class of drift. Not urgent; nothing is broken.

---

## [OPEN] FU-784 — `DoraBubble` has no placement budget against page-level bottom chrome
- **Raised:** 2026-08-29 (shopping-list UX v3 audit)
- **Type:** finding
- **What:** `components/dora/DoraBubble.vue:396-406` is `position: fixed; bottom:
  18px + safe-area; z-index: 3000`, ~88px tall, bottom-right. Any page-level
  bottom chrome lands underneath it. Today's concrete collision is the shopping
  list's `.sld-shop-footer` (`ShoppingListDetail.vue:3574`, z-index **3**), whose
  "Finish & restock" CTA sits exactly there on narrow screens. Quasar toasts were
  already lifted 112px for the same reason (`css/app.scss:54`) — a one-off patch,
  not a rule. D-009 ("toasts & floating chrome respect a placement budget") says
  this should be systematic.
- **Why deferred:** v3 shipped 2026-08-29 and deleted `.sld-shop-footer`
  outright, so **the instance is gone** — the shopping list has no bottom chrome
  left for the mascot to sit on. The *class* of bug survives for the next page
  that grows some.
- **Recommended resolution:** when another page adds fixed/sticky bottom chrome —
  at that point define the budget once (a `--bottom-chrome-offset` token or a
  shared composable) rather than patching a third caller.

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

## [OPEN] FU-750 — Existing installs have no `food_category`, so every Health Star Rating scores 0% fvnl until a re-import
- **Raised:** 2026-08-27 (Health Star Rating build)
- **Type:** finding.
- **What:** `NutritionFood.food_category` is populated by the dataset importer
  from `food_category.csv`. It cannot be backfilled — the value lives in the
  source archive, not in anything already stored — so foods imported before
  migration `d1e5b8c3f7a2` keep NULL, `is_fvnl_category` returns False for all
  of them, and every recipe scores **0 fvnl points**. That is not neutral: on a
  dish with ≥13 baseline points it *also* locks out the protein credit (the
  FSANZ gate), so an unmigrated install's ratings are systematically pessimistic
  in exactly the wrong direction.
- **Why deferred:** the fix is "re-run the import", which is a user action, not
  a code change. What's missing is the *prompt* — the admin nutrition page says
  nothing about it, so an existing install has no way to know its ratings are
  thin.
- **Recommended resolution:** now-ish, and small — a banner on
  `AdminSystemNutritionSettings.vue` when `health_star_rating_enabled` is on and
  some non-zero share of `NutritionFood` rows have a NULL `food_category`.
  Needs one count endpoint or an extra field on the existing dataset-status
  response.

## [OPEN] FU-749 — Fruit *juices* and fried potato products score full fvnl points
- **Raised:** 2026-08-27 (Health Star Rating build)
- **Type:** finding.
- **What:** the fvnl test keys off USDA's food-group description, and two of the
  five qualifying groups contain members HSR would treat differently.
  *Measured* on SR Legacy: "Fruits and Fruit Juices" is 355 rows of which **88
  are juices/nectars**, and "Vegetables and Vegetable Products" is 814 rows of
  which **36 are fried/chip-shaped** (french fries, crisps, tempura). The guide
  does allow juice to score, so that half is arguably correct for a recipe; the
  fried-potato half is the clearer miss.
- **Why deferred:** it moves a rating by at most one V-point band on a recipe
  built mostly of chips, and the fix is a name-level exclusion list, which is
  the kind of heuristic that wants a real example to justify it rather than
  being written speculatively.
- **Recommended resolution:** opportunistic — revisit if a real recipe rates
  visibly wrong. The place to fix it is `features/nutrition/food_categories.py`,
  which already owns the vocabulary.

## [OPEN] FU-744 — Recipe tool derivation has no migration for existing structured recipes
- **Raised:** 2026-08-27 (recipe-view feedback batch)
- **Type:** finding.
- **What:** a structured recipe's `tool_ids` is now the union of its steps'
  tools, re-derived on every create/update. Recipes last saved *before* this
  keep whatever tool set was typed by hand until something PATCHes them — so
  the cookbook's tool filter can disagree with what the steps say, in either
  direction, on untouched recipes.
- **Why deferred:** pre-release, no real users, and the drift self-heals on the
  next save of each recipe. A one-shot data migration over every structured
  recipe is more risk than the inconsistency is worth right now.
- **Recommended resolution:** opportunistic — a data migration calling
  `sync_recipe_tools_from_steps` for every recipe with `steps_mode='structured'`
  would close it in about ten lines, if the filter ever misbehaves visibly.

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
## [OPEN] FU-714 — `useShoppingListActions.addItems` still loops; the bulk endpoint exists now
- **Raised:** 2026-08-22 (bulk-endpoint work)
- **Type:** leftover.
- **What:** the stock overview's bulk paths were moved onto
  `POST /api/shopping-lists/<id>/lines/bulk-add`, but `addItems`
  (`useShoppingListActions.ts:41`) still `await`s `addLineAsync` per item. It has
  ~16 call sites and several pass genuinely multi-item arrays — "add all missing
  ingredients" on both recipe pages, `DoraChat`'s matched-items add, the
  stock-item detail substitutes/related adds, `StocktakeRunner`, `QuickAddSheet`.
  Those surfaces still pay one round-trip per item.
- **Why deferred:** out of the reported scope (stock overview), and `addItems`
  accepts full `AddLineCommand`s — product-anchored lines, quantities,
  `selected_product_id` — which the bulk endpoint doesn't take. Doing it properly
  means either widening the endpoint's request model or branching on "is every
  command a bare stock_item_id", and the branch is the kind of implicit
  cleverness R-019 warns about.
- **Recommended resolution:** opportunistic — next time shopping-list adds are
  touched. Widening `bulk-add` to accept the same line shape as `AddLineHandler`
  is the cleaner of the two options.
- **Progress (2026-10-24, finalisation 03-R33):** `NewListDialog` adds through `bulkAddLinesAsync` and merges a template server-side (`instantiate` takes `merge_into_list_id`). `addItems` itself still loops; widening `bulk-add` to the `AddLineRequest` shape is still the fix.

## [OPEN] FU-713 — bulk set-level and bulk add/remove commit once per item
- **Raised:** 2026-08-22 (bulk-endpoint work)
- **Type:** finding.
- **What:** `bulk-set-level`, `bulk-add` and `bulk-remove-by-stock-item` loop the
  existing single-item handlers server-side, and each of those ends in its own
  `save_changes()`. So a 40-item bulk restock is 1 HTTP round-trip but 40 commits.
  That was a deliberate trade — a level change stamps two timestamps, appends a
  `StockLevelChange`, may record a `ConsumptionEvent` and may fire the auto-add
  hook, and a second implementation of that would drift (R-003) — but it means
  the win is latency, not database work. `bulk-move` does not have this shape; it
  is two queries and one commit.
- **Why deferred:** correctness first, and the reported symptom was latency.
- **Recommended resolution:** when <a bulk action is measurably slow on a real
  pantry>. The fix is to let the inner handlers defer their commit (an explicit
  `commit: bool` argument, not an implicit unit-of-work), not to inline the rules.
- **Progress (2026-10-24, finalisation 03-R34):** `bulk-add` and `bulk-remove-by-stock-item` now commit once (`AddLineHandler` / `RemoveLineByStockItemHandler` take `commit=False`). `bulk-set-level` still commits per item; that is what is left.

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

## [OPEN] FU-700 — the stocktake install switch isn't gated on the dashboard / help copy
- **Raised:** 2026-08-20 (stock-overview feedback batch).
- **Type:** leftover.
- **What:** `AppSetting.stocktake_enabled` now hides the Stock-overview button,
  the "Needs check" filter, the per-item mute toggle and the runner, and empties
  the server-side overdue map. Three surfaces still speak as if the feature is
  always on: `DoraScoreCard`'s "Do a stocktake" action (`/stock?stocktake=1`),
  `AttentionRulesDialog` + `StockRowLegend` ("due for a stocktake check"), and
  `AlertsPage`'s copy about the default stocktake reminder.
- **Why deferred:** the reported items were the overview and the per-item
  toggle; the Dora-Score action in particular needs a call on whether the score
  should still *carry* a staleness component when stocktake is off (server-side
  question), not just whether to hide a link.
- **Recommended resolution:** later, alongside FU-182's app-wide feature-gate
  sweep — or now if the owner intends to actually run with stocktake off.

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

## [OPEN] FU-693 — the two compact-list row names sit off the D-003 type scale
- **Raised:** 2026-08-20 (cookbook feedback batch 3).
- **Type:** finding.
- **What:** `StockItemRow.vue`'s `.stock-row__name` is `font-size: 1.05rem` — a
  raw size, not one of the `--font-size-*` ratios D-003 requires (`md` = 1,
  `lg` = 1.125; 1.05 is neither). `RecipeRow.vue`'s `.recipe-row__name` now
  carries the same raw value, because the owner's ask this session was
  explicitly *parity with the stock row* and the only way to match a
  tokenless value is to repeat it. Carve-out is commented in place in
  `RecipeRow.vue` naming the rule.
- **Why deferred:** it has to be done as a **pair or not at all** — tokenising
  one breaks the parity the request created, and tokenising both moves the Stock
  Overview name type the owner signed off on days ago (24ca1786 / 8073ac04). So
  it's a small deliberate design call, not a mechanical sweep.
- **Fix shape:** decide whether a list-row name is `--font-size-md` (16, back
  down a step) or earns a new `--font-size-md-plus` ratio, then change both
  declarations in the same commit. Check any other `.…__name` in a list row for
  the same value while there.
- **2026-08-30 update — a third site was AVOIDED, not created.** The meal
  planner's new rail row (`MealPlanRecipeRow.vue`, Unit 2 of the rail brief)
  would have been the third `.…__name` at `1.05rem`; the brief's §4.5 asked for
  a decision either way and the recommendation was to tokenise. It uses
  `--font-size-md`, on the grounds that a 280px rail is not where a 0.05rem
  parity with a full-width stock row is legible. So the pair described above is
  unchanged and still has to move together — but the rail is already on the
  scale and must NOT be "brought back into line" with them if they stay raw.
- **Recommended resolution:** opportunistic — pairs with the next design-
  remediation chunk, or with [[FU-691]] since both are D-rule type/token drift.

## [OPEN] FU-691 — the recipe page's stylesheet is off-token throughout (D-017)
- **Raised:** 2026-08-20 (recipe-view parity pass).
- **Type:** finding.
- **What:** the page's ~350-line `<style scoped>` block predates any D-017 check
  on it. Two patterns, both throughout: **token fallbacks**
  (`var(--space-2, 8px)` — ~40 occurrences, so the literal is what a missing
  token would actually render) and **off-scale literals** for font-size
  (`0.8125rem`, `0.75rem`, `0.875rem` where `--font-size-xs/sm` exist), padding
  (`padding: 0 3px`) and shadow (`0 2px 10px var(--overlay-dim)` against
  `--elevation-*`). D-017 bans exactly these. The new CSS added in this pass
  matches the file's existing style deliberately rather than leaving two
  conventions in one stylesheet — flagged here instead, per the explain-or-flag
  rule, because a half-converted stylesheet is worse than either end state.
- **Why deferred:** it is a mechanical sweep of one file with no behaviour
  change. Its original blocker — the old page and the masthead question — cleared
  on 2026-08-26 when [[FU-688]] resolved, and the file is now
  `web_app/src/pages/RecipeDetailPage.vue`. The owner was offered it as part of
  that swap and **chose to defer**: the merged page still has no browser walk
  behind it, so a whole-stylesheet rewrite would tangle any spacing regression up
  with the swap and the icon work in one diff. The 2026-08-26 batch's new CSS
  (`.rn__brow`, the `.rn__factk` icon rules) again matches the file's existing
  style rather than leaving two conventions in one stylesheet.
- **Recommended resolution:** **after the `DORA_VERIFY` walk of the merged recipe
  page**, as a standalone tidy with nothing else in the diff.

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

## [OPEN] FU-669 — The cookbook's at-risk horizon still lives in two languages
- **Raised:** 2026-08-17 (expiring-ingredient chips).
- **Type:** finding (R-003).
- **What:** `EXPIRING_HORIZON_DAYS = 14` is now the server's constant and the
  per-ingredient chips read it. The **filter** still takes the horizon as a request
  param, and `RecipesOverview.vue` passes its own `EXPIRING_FILTER_HORIZON_DAYS = 14`
  — so the number is declared twice and they agree only by hand. Change one and the
  filter silently stops matching the chips, which is the exact confusion this work was
  reported to fix. Documented in place as an R-003 carve-out at both sites.
- **Why deferred:** unifying it means an explicit API change (a `uses_expiring=true`
  param the server resolves the horizon for, replacing the client-supplied number).
  That's a deliberate contract decision, not a bug fix, and a blank-value-means-default
  shortcut was rejected as magic.
- **Recommended resolution:** when the recipes filter API is next touched — or now, if
  you'd rather not carry the hand-sync risk. Needs a call on whether
  `expiring_within_days` stays for other callers.

## [OPEN] FU-668 — Audit every list store for the unpaged-first-page trap
- **Raised:** 2026-08-17 (cookbook truncation bug).
- **Type:** finding.
- **What:** the cookbook bug (recipes past the 50th invisible because the store took
  one default page and filtered client-side) is the *second* instance of this exact
  defect — stock items had it as FU-035. The shape is: a store hydrates via a bare
  `getAllAsync()`, and a page filters/searches over that collection in the browser.
  Any such surface silently caps at `DEFAULT_LIMIT` (50) and misreports its own
  counts. Recipes and stock items now page; **meal plans, shopping lists, shopping-list
  templates, locations, stock groups and stores have not been checked.** Grep for
  `getAllAsync()` with no args in `web_app/src/stores/`.
- **Why deferred:** out of scope for the reported bug; fixing recipes was the ask.
- **Recommended resolution:** now-ish — it's a read of ~8 stores, and each hit is a
  user-visible "my data vanished" bug waiting for the install to grow past 50 rows.

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

## [OPEN] FU-662 — `attempts` is counted on queued mutations but never acted on
- **Raised:** 2026-08-17 (offline-sync audit).
- **Type:** finding.
- **What:** `QueuedMutation.attempts` is incremented on every failed replay and read
  nowhere. There's no cap, so a mutation that keeps failing retries forever, and no
  staleness check, so a level set three days ago can replay over a newer value with
  last-write-wins and no warning — `createdAt` is recorded but unused. Neither has bitten
  yet (the queue could never drain at all until today's fix), which is precisely why it's
  worth deciding now rather than after it does.
- **Why deferred:** picking a cap and a staleness window is a product call, not a
  mechanical fix — "drop it", "conflict it", and "replay it anyway" are all defensible.
- **Recommended resolution:** with FU-660 — the answer to "too old / too many tries"
  is "it goes in the conflict pile", so the two want designing together.

## [OPEN] FU-656 — The password-strength rule is asserted in two languages
- **Raised:** 2026-08-17 (admin-settings rework).
- **Type:** finding.
- **Why it matters (R-003):** `auth_helpers.validate_password` is the authority — length
  **plus** a common-password blocklist — and it's the only thing that can reject a save.
  But three forms need to say "at least 8 characters" *before* the round-trip, so the
  number is now also a frontend constant (`web_app/src/models/password.ts`
  `MIN_PASSWORD_LENGTH`). That's one copy on each side of the wire; raising the server
  rule would silently leave the forms hinting the old number, and the blocklist half is
  invisible to the client entirely (you only learn "that's a common password" after
  submitting).
- **What:** publish the policy from the server — `min_length` (and ideally a
  `rules` blurb, `PASSWORD_RULES_DOC` already exists) on `GET /auth/capabilities`,
  which is already unauthenticated and already read on the login screen — then delete
  the literal and have `password.ts` read the published value with the current number
  as a boot fallback.
- **Why deferred:** the duplication is a hint string, not a security boundary — the
  server still rejects anything weak — and doing it properly means a small policy store
  + fallback on the client, which is more than the admin-settings unit should carry.
- **Recommended resolution:** opportunistic — natural pairing with any future auth or
  capabilities work.

## [OPEN] FU-647 — `print-view` and the CSV export still build API URLs by hand (R-045)
- **Raised:** 2026-08-16 (QR fix — noticed in the same composable).
- **Type:** finding.
- **What:** `useStockOverviewExport.openPrintView` still does
  `window.open(`${baseUrl}/stock-items/print-view…`)`, which is the exact pattern
  R-045 now forbids and the exact pattern that broke the QR sheet. `downloadCsv` uses
  `fetch(..., { credentials: 'include' })`, which is *correct* but is a second
  hand-rolled auth path next to `AxiosHttpClient`. Other server-rendered print views
  (shopping list, recipe) likely have the same shape — not surveyed.
- **Why deferred:** out of scope for a stock-item-detail feedback batch, and the QR
  path was the one actually reported broken. Converting print-view needs the same
  server-side treatment (any `/api/...` asset it references must be inlined), so it's
  its own small unit.
- **Recommended resolution:** opportunistic — grep for `resolveBaseURL` /
  `getBackendBaseUrl` in templates and `window.open` calls, convert the document
  endpoints to the `useQrLabels` shape, and route `downloadCsv` through the client.

## [OPEN] FU-646 — The recipe nutrition rollup still aggregates only the original four nutrients
- **Raised:** 2026-08-16 (nutrition macros+ build).
- **Type:** deferred job.
- **What:** `NutritionFood` now stores sugars, saturated fat, fibre and sodium, and the
  stock-item detail page displays them. `features/nutrition/recipe_rollup.py` still sums
  only kcal/protein/carbs/fat, so a recipe's nutrition card can't show the new four.
- **Why deferred:** the feedback was about the stock-item detail page. The rollup has
  its own coverage/uncounted contract (R-041) that every added nutrient has to satisfy,
  and it feeds the meal planner's per-day figures — a bigger blast radius than this
  unit was scoped for.
- **Recommended resolution:** when the recipe nutrition card is next touched. Note the
  data caveat: existing catalogue rows have NULL for all four until the dataset is
  re-imported, so the rollup would report them as uncounted for a while.
- **Widened 2026-08-17:** the gap is now four nutrients plus fifteen — the
  vitamins-and-minerals block (migration `b6e04c9a2f18`) is likewise stock-item-detail
  only. This does **not** mean the rollup should grow all nineteen: a per-recipe
  potassium total is a different (and much more caveated) claim than a per-100g
  catalogue figure. Decide the scope deliberately when the card is next opened.

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

## [OPEN] FU-645 — Existing nutrition catalogue rows have no sugars/saturates/fibre/sodium until re-import
- **Raised:** 2026-08-16 (nutrition macros+ build).
- **Type:** follow-up.
- **What:** migration `d3a7f2b91c60` adds four nullable columns with no backfill —
  correct, because the values were never downloaded and inventing them would be a lie
  (P12). Any install that imported a USDA dataset before today shows blanks in the new
  Details table until it re-runs the import under System → Nutrition. Nothing in the UI
  currently says so.
- **Why deferred:** needs a product call on how loud to be — a one-line hint on the
  admin Nutrition page ("re-import to pick up newly-tracked nutrients") is probably
  enough; a banner would be over-nagging for a display-only gap.
- **Recommended resolution:** now-ish, alongside any next visit to the admin Nutrition
  page. Cheap either way.
- **Widened 2026-08-17:** migration `b6e04c9a2f18` adds fifteen more on the same terms
  (the vitamins-and-minerals block), so a pre-today install now shows an *empty*
  optional section rather than a partial one — which reads as "this food has no
  vitamins" instead of "we haven't downloaded them". That makes the one-line hint on
  the admin Nutrition page more worth doing, not less.

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

## [OPEN] FU-623 — Centralise `$q.dialog` behind a `noCaps`-injecting wrapper (enforce R-039)
- **Raised:** 2026-08-12 (FU-578 DR-3 dialog-casing sweep).
- **Type:** deferred job (tidy / single-source).
- **What:** DR-3 fixed ~15 files where `$q.dialog` buttons rendered ALL-CAPS by converting every `cancel: true` / string-shorthand `ok:`/`cancel:` to `{ label, noCaps: true }`. That matches the ~15 sites that already spelled `noCaps` out, but the app now has **~30 hand-rolled `$q.dialog` calls each re-stating `noCaps`** — R-039 is enforced by convention, not code. A thin composable (e.g. `useDoraDialog()` returning a wrapper that injects `noCaps: true` into `ok`/`cancel` unless already set, passing `{ component }` dialogs straight through, and preserving the returned `DialogChainObject` so `.onOk().onCancel().onDismiss()` chains are untouched) would make R-039 structural.
- **Why deferred / not done in-audit:** a **half-migrated** wrapper (some sites through it, some raw) is worse than the current consistent explicit pattern; migrating all ~30 sites — including `options`/`prompt`/`component` dialogs and chained resolvers — is its own unit with real regression surface, out of scope for a casing detail-audit.
- **Recommended resolution:** opportunistic — when next touching dialog code in bulk, or as a dedicated tidy. Cross-ref: R-039 / ADR-035 in `ENGINEERING_STANDARDS.md`, `DESIGN_REMEDIATION_PLAN.md` DR-3.

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

