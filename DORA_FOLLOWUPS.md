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
- **Progress (2026-11-06):** part (1) was already in code: /onboarding/finish refuses seed / items / seed_demo with 403 unless the install has exactly one user (test__finish__a_later_member_cannot_seed_defaults). Correction to the earlier note: the gate is 'only one user exists', not 'the caller is the first account', so once a second member exists nobody can re-seed, the admin included; matches the client today. Still open: part (2), the companion release.

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

