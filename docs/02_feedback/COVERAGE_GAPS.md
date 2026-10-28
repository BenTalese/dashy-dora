# Feedback coverage gaps

A living list of bullets in
`02_feedback/Feedback _ Fixes - as of [06-Jun-2026].md` (and any later
revisions) that **do not yet have a home** in the prompt set
(`03_prompts/`), a proposal (`04_proposals/`), or an investigation
report (`05_investigations/`).

**How to use this:**
- Add an item here when a feedback bullet is identified during audit
  and no existing brief covers it.
- Strike through / mark `[RESOLVED]` when the bullet gets folded into
  a brief or proposal. Don't delete — the trail matters.
- When writing a new Wave-C brief or INV report, scan this file first;
  every bullet you cover here moves to the brief's coverage table.

The CLAUDE.md "Cross-checking against the original feedback" rule
points at this file.

---

## Bucket A — Whole surfaces with no dedicated brief

### A-1 STOCK ITEM DETAIL polish

> **Update 2026-06-15:** this cluster now HAS a design home —
> `04_proposals/PROPOSAL_STOCK_ITEM_DETAIL.md` (C-1b) + `IMPL_PLAN_STOCK_ITEM_DETAIL.md`.
> The §8 coverage table there maps every L112-140 bullet.
>
> **Update 2026-06-16:** the C-1b stack (`.1 → .5`) is **built**; the design home is now
> the running surface. Cluster flipped to **[COVERED]**; remaining open work is
> browser-verification, tracked under **FU-202** (extended for each .1–.5 chunk). The
> per-bullet status table stays below for the audit trail.

Feedback `§STOCK ITEM DETAIL` has ~30 bullets. The bug-shaped ones were covered by
B-prompts (B3 PATCH, B4 cascade, B8 dead actions); the **layout / button-placement /
open-design** bullets are now all addressed in the C-1b chunks:

- [COVERED] Clear-expiry button affordance (cross mark next to expiry) — **C-1b.1** (× button + ±1/+7/+14).
- [COVERED] No way to set "essential" — **C-1b.1** (toggle row in the inline-edit overview).
- [COVERED] No way to set stock group — **C-1b.1** (DTO thread + inline picker row).
- [COVERED] Split-view at 50% default; sensible min/max splitter distance — **C-1b.2**.
- [COVERED] Tabs hardly visible in some themes — **C-1b.1** (theme-token routing, R-002).
- [COVERED] Stock-level shown twice — **C-1b.1** (header chip is the editor; duplicate row gone).
- [COVERED] Move delete button — **C-1b.1** (top-right, danger-ghost).
- [COVERED] Restock here makes no sense — **C-1b.1** (button + handler removed; belongs to list finalisation).
- [COVERED] Move "Opened" button next to opened info; same for expiry — **C-1b.1** (open toggle + "since" on the row; expiry value + × + quick-set on the row).
- [COVERED] "Find deals" placement — **C-1b.3** (contextual: empty-state CTA + "Link another" in the Products tab; toolbar Find-deals removed in C-1b.1).
- [COVERED] Overview single column tidier — **C-1b.1**.
- [COVERED] Location updated inline without a separate dropdown — **C-1b.1** (searchable path picker inline) / focused FU-202 pass earlier.
- [COVERED] Notes value — **C-1b.1** (kept, de-emphasised at the bottom).
- [COVERED] Add product-of-choice to shopping list (not just cheapest); per-product list-add buttons — already exists (C-7); **C-1b.3** removed the "Get cheapest" toolbar shortcut and emphasises the cheapest card via style, per §2.4.
- [COVERED] Preferred merchant/product behaviour — **FU-180** removed it; **C-1b.3** confirms nothing to design.
- [COVERED] Shopping-lists tab — "(primary)" plain text feels unimaginative; arrow icon non-clickable — **C-1b.4** (styled `q-badge` for Primary; dead arrow removed).
- [COVERED] History tab worth — **C-1b.5** (rebuilt as a unified lifecycle timeline merging level + waste + list-add provenance + synthesised Opened/Checked rows; INV-7).
- [COVERED] Substitute swap-into-list weirdness — **C-1b.4** removed the swap from this surface; relocation owned by **INV-8** (Shop Mode).

**Outstanding gates:** FU-202 browser-verification across all five chunks; everything code-level
+ tsc/eslint/e2e is green.

### A-2 DATA page

Feedback `§DATA` has 10 bullets. Currently zero coverage in the
prompts or proposals.

- [OPEN] Move under Settings → "My Data" (not a top-level nav item).
- [OPEN] Multiple export formats (json, csv, …).
- [OPEN] Page formatting overhaul — margins, alignment, headings, font/type.
- [OPEN] Card layout with checkboxes.
- [OPEN] Drop the breadcrumb fluff ("Data / Backup & restore — Backup, import, export and barcode tools for your Dora data").
- [OPEN] Schema-driven import templates (download, fill, upload).
- [OPEN] Export & print tab utility — drop or rework.
- [COVERED] "Scan" tab under QR codes — useful here vs only on stock overview? → `PROPOSAL_BARCODE_SCANNING.md` §6 (open question; action-scan leans to C-1 Stock Overview, Data tab keeps label printing).
- [COVERED] "Barcodes & QR" → "QR codes" rename → `PROPOSAL_BARCODE_SCANNING.md` §4 (renamed "Scanning & QR labels"; kept "scanning" because real-barcode→navigate survives via ProductBarcode).
- [OPEN] Decide whether the optional/collapsed section should be the main view.

**Recommended home:** new Wave-C brief `C-DATA — Data Management
redesign`.

### A-3 DORA BOT (assistant chat) polish

Feedback `§DORA BOT` has 6 bullets, scattered across multiple owners:

- [OPEN] Text size not honouring user settings (a bug).
- [OPEN] Basic/AI chip squished/small.
- [OPEN] Make basic/AI chip a toggle slider (slanted thick, glow on slide).
- [OPEN] DS4 animation flashing on hover — regression to investigate.
- [OPEN] Don't show "Hi I'm Dora, click me…" every login (once-per-user acknowledge).
- [OPEN] Turn the bot off completely in settings.
- ~~[RESOLVED] D.O.R.A. acronym — covered by the 2026-06-05 acronym pass.~~

**Recommended home:** a small Wave-C brief or fold into the existing
`DORA_ASSISTANT_ARCHITECTURE_PROPOSAL.md` as a UI-polish appendix.

### A-4 HELP content

Feedback `§HELP` has 5 bullets — all about content (detailed help per
feature, guides, FAQ, navigability, diagrams). No brief.

- [COVERED 2026-10-29] Help content overhaul: 166 short guides in 14 topics
  (one page each), search, Common questions, and cropped screenshots of the
  running app — `web_app/src/help/helpContent.ts` + the `components/help/`
  set. Diagrams were not asked for beyond screenshots. The DoraBot corpus half
  is FU-946.

**Home:** built (the 20-D4 decision, worklog 2026-10-29).

### A-5 SETTINGS deferred bullets

Deferred area per master plan, but the bullets are actionable.

- [RESOLVED 2026-07-13] Theme **type** (system / light / dark) separated
  from theme **identity** (pesto, lemon, …) — two dropdowns, not coloured
  light/dark buttons on each theme card. Verified shipped in
  `web_app/src/pages/settings/PreferencesSettings.vue`: independent
  "Mode" segmented control + "Theme" palette-picker grid. See FU-362 in
  `DORA_FOLLOWUPS_RESOLVED.md`.
- [RESOLVED 2026-06-23] Profile picture — set/update; surface on the
  menu-bar avatar. Shipped in `IMPL_PLAN_SETTINGS_REBUILD.md` Phase 4:
  `User.image` column + migration `a4f7c2e9b6d1`, `GET /users/<id>/image`
  bytes endpoint, `image`/`clear_image` on `PATCH /auth/me` (+ admin
  update), `has_image` on the me/list DTOs, and a shared SPA `UserAvatar`
  adopted at the menu bar (fallback icon), the Account header + the Users
  admin rows (fallback initials), with the upload picker on Account.
  Backend static-only this session (no Python env) — pytest round-trip
  added; run + browser walk pending (see `DORA_FOLLOWUPS.md`).

**Recommended home:** small additions to a deferred-Settings polish
prompt (or fold into Wave A theme work).

---

## Bucket B — Open assessment-style questions

Bullets phrased "is this worth it / should we keep / let's assess".
These map cleanly to INV prompts.

- [OPEN] **History tab worth** on stock item detail. Added as `INV-7`.
- [OPEN] **Substitute swap-into-list** behaviour. Added as `INV-8`.
- [OPEN] **Command palette assess** — "How useful really? Let's assess." Added as `INV-9`.
- [OPEN] **`essential` flag** on stock items — UI + value. Added as `INV-10`.

---

## Bucket C — Cross-cutting / niche / future

No clean per-surface home; mostly future or "nice-to-have".

- [OPEN] **Full systems QA test document** — manual walkthrough of every feature for final regression. The user wants this done last so it captures the final product. No plan yet; add when the implementation waves are mostly done.
- [DEFERRED → hosted-only] **Usage analytics / telemetry** — "I'd like to know how people are using my app." Designed in `PROPOSAL_USAGE_TELEMETRY.md`, but **decided 2026-07-16 (owner): don't build for self-host.** The ask is the *maintainer's* (which features earn their keep), which only makes sense as hosted aggregate analytics; a local self-host "efficiency lens" was considered and dropped as not useful to the operator. The whole topic is **relocated to `OPTIONAL_SAAS_AND_MANAGED_DEPLOYMENT.md`** (hosted-only), to revisit if a hosted offering opens. FU-566 resolved (WON'T-DO self-host). (FU-363 item 2, 2026-07-15 → parked 2026-07-16.)
- [OPEN] **UI uniqueness / polish design pass** — "looks just okay, not polished/unique." Cross-cutting.
- [OPEN] **Push notifications between users** (new-feature idea — alert another user, share a shopping list via notify).
- [RESOLVED] **Kivy P2P sync branch** — CUT: no home in the current client-server architecture. → `MULTI_USER_READINESS.md` §5.1 (FU-363 item 5, 2026-07-15).
- [RESOLVED] **Main menu bottom border** — removed the `q-header` border per the feedback lean (`MainLayout.vue`). (FU-363 item 6, 2026-07-15.)
- [COVERED] **QR codes with the Dora logo in the middle** (D/D simple one). → `PROPOSAL_BARCODE_SCANNING.md` §6 (noted nice-to-have, opportunistic during label-render work).
- [RESOLVED] **Real ALDI / IGA logos** — WON'T-DO: trademark/licensing risk; Dora ships zero logos by design (`StoreLogo.vue`), and per-store logo **upload** already covers the need (`StoresSettings.vue`). (FU-363 item 7, 2026-07-15.)
- [COVERED] **QR scanning → quick-actions modal** for the scanned item. → `PROPOSAL_BARCODE_SCANNING.md` §5.3 (deferred to C-1 Stock Overview overhaul, where item context exists; today scan → result dialog → open detail).
- [OPEN] **General UI consistency** — cross-cutting Wave A and the design-pass above.

---

## Bucket D — Bullets covered elsewhere (recorded so the audit is reproducible)

Surfaces verified covered by existing prompts/proposals — listed so the
next reviewer can fast-skip them.

- SPLASH, CANNOT CONNECT, LOGIN/REGISTER/FORGOT — `04_proposals/PROPOSAL_AUTH_SHELL.md`
  (C-19, written 2026-07-02; maps the shared-styling, register-button, and Forgot-match
  bullets — coverage table in §10). Password policy (§LOGIN "8 chars, admin toggle") stays
  out of C-19, still uncovered → tracks as a separate follow-up. B9.8 covered the
  mascot-hidden-on-mobile bug; A1 handled other theme drift; INV-4 remains the audit
  reference.
- ONBOARDING — `04_proposals/PROPOSAL_ONBOARDING.md` (C-5, written 2026-06-06;
  maps L24-46); dead-nav was B5; feature-flags → `04_proposals/PROPOSAL_CONFIG_AND_OPTINS.md`
  §2.6 (C-cross); headcount → C-3. **Update 2026-06-17:** personas + the `products_enabled` flag
  are retired and L46 (stock-vs-product explainer) is dropped — onboarding is one un-personalized
  "show everything" path. See `04_proposals/PROPOSAL_PRODUCTS_AS_OVERLAY.md` §5.
- DASHBOARD — `04_proposals/IMPL_PLAN_DASHBOARD_REBUILD.md` (written 2026-06-23
  after a `/design-critique` pass; maps §DASHBOARD L48-61 + strays L176/L272/L480
  in its §5 coverage table). Supersedes the prior "deferred per master plan" hold —
  the user pulled the dashboard forward. L480 (cross-app undo) marked out-of-scope
  there → tracked as a follow-up for the undo/toast owner.
  **Re-verified 2026-09-02 → `05_investigations/DASHBOARD_PAGE_REVIEW.md` §10.**
  Eleven of the fourteen bullets are genuinely shipped; **two are re-opened**:
  **D2** ("dark mode not working", L56) — `DoraScoreCard` renders hard-coded
  light-theme hex in all ten themes on undeclared `--dora-*` tokens, and the stock
  donut freezes its palette on a theme switch (FU-822, FU-824); and **L254**
  (money features switchable off) — the *cards* gate correctly, but the Kitchen
  health composite is weighted by budget data on a money-off install and the hint
  pool advertises money features (FU-823). L471 (heading type usage) is
  **uncovered** on this surface: 44 raw font-sizes, zero tokens, zone labels at
  11.5px (FU-828). Also unmet, and not feedback bullets but the plan's own
  commitments: §2.2's curated 8-card default set (now 13 of 17 — FU-817) and §6's
  DoD "thin composition over `components/dashboard/*`" (page is 3126 lines, 14
  cards inline — FU-829).
- STOCK OVERVIEW — `04_proposals/PROPOSAL_STOCK_OVERVIEW.md` (C-1, written
  2026-06-06; maps L63-99). Cart bullets → C-7; planned-meals metric → C-2;
  location display → `04_proposals/PROPOSAL_CONFIG_AND_OPTINS.md` §2.5 (C-cross);
  images → FU-033.
- STOCKTAKE MODE — B9 fixes.
- PRODUCT SEARCH — `C_big_rock_design_briefs.md §C-6` (companion-scope, not
  written as Dora-core). The Dora-core seam it targets is
  `04_proposals/PROPOSAL_INGESTION_API.md` (C-10, written 2026-06-06).
- MY PRODUCTS / CART BUTTON — `04_proposals/PROPOSAL_CART_BUTTON.md` (C-7,
  written 2026-06-06: unified button, decision tree, standalone-product rule).
  Note: My-Products link affordance (L195) + custom products (L192) still its own
  scope; the cart/standalone-product bullets (L83-84,108,130,154,191,196,288,
  380-382) are now covered. **Update 2026-06-17:** My Products + Price History + the stock-item
  Products tab **stay in Dora, data-gated**; only Product Search moves to the companion. Custom
  products (L192) was **by-design refused**; **REVERSED and BUILT 2026-09-08** (OD-2) — the everyday substitute was
  `PreferredBuy`. The My-Products link affordance is repaired (FU-208). See
  `04_proposals/PROPOSAL_PRODUCTS_AS_OVERLAY.md` §4.
  **Update 2026-09-06 — every MY PRODUCTS bullet now has a home.**
  `04_proposals/IMPL_PLAN_PRODUCTS_PROGRAM.md` §8 carries the full coverage table
  (MP-1..MP-23). Notable flips: **L197 "no way to remove a saved product" →
  COVERED** (hard delete, decision D-1, batch C — no longer an open fork);
  **L205/206 bulk-select variants → COVERED** (batch F; they were the one real
  GAP); the My-Products **link affordance → COVERED** (batch F). Two bullets are
  marked **superseded, not covered** — the filter-clear-consistency and
  filter-default-open ones, both answered differently by later owner calls
  (`FilterToggleButton` / `useFilterPanelExpanded`, 2026-08-20). Custom products
  (L192) is **BUILT 2026-09-08**: `PreferredBuy` is a label with no price, store or history, so it could never substitute. Custom products are marked `is_custom` and excluded from the scheduled sync and from ingest dedupe.
- PRODUCT HISTORY — B9.6. **Update 2026-09-06:** all ten PRODUCT HISTORY bullets
  are dispositioned in `04_proposals/IMPL_PLAN_PRODUCTS_PROGRAM.md` §8
  (PH-1..PH-10) — four appear already fixed and await a browser confirm under
  FU-214, four are batch G, one (the %off chip inconsistency, PH-6) is confirmed
  real and becomes a shared `DiscountChip` in batch F, and the bottom-sheet idea
  (PH-10) is opportunistic.
- RECIPES OVERVIEW / RECIPE DETAIL — `04_proposals/PROPOSAL_COOKBOOK.md` (C-4,
  written 2026-06-06; maps L228-315). Comparison CUT per INV-6; cost/nutrition/
  tag-taxonomy settings → `04_proposals/PROPOSAL_CONFIG_AND_OPTINS.md` (C-cross);
  cart → C-7; allocation → C-2/B6.
- COOK MODE — `04_proposals/PROPOSAL_COOK_MODE.md` (C-3, written 2026-06-06;
  maps L317-338). Tools/structured-steps → C-4; headcount → C-5; finish add-to-
  list → C-7.
- MEAL PLANS — `04_proposals/PROPOSAL_MEAL_PLANS.md` (F1..F49 table).
  > **Update 2026-08-28:** the flat "covered" pointer above was stale.
  > `IMPL_PLAN_MEAL_PLANS_REBUILD.md` §13 (2026-06-25) re-graded **13 bullets 🟡
  > regressed/new-concern** once all 49 shipped ideas were live together, and its
  > §15 instructed a flip here that never happened. The 🟡 set is
  > **F9, F16, F20, F22, F41, F42, F44, F46** (+ the layout/scroll group) — i.e.
  > the recipe rail, the page's scroll model and the calendar. All of them now
  > have a *second* home in
  > `04_proposals/BRIEF_MEAL_PLANNER_RAIL_AND_SHELL.md` §11, which re-covers
  > them and marks the rest of F1–F49 out-of-scope-with-a-reason.
  > **Four are [OPEN] again rather than covered**, because the brief revises the
  > owner's own earlier feedback and the revisions are unconfirmed (FU-782 §9):
  > **F13** (the calendar widget the owner specified is the one he now dislikes),
  > **F17** (the requested down-arrow-below moves into the toolbar), **F9**
  > (offer both drag and tap — the brief recommends retiring drag), and **F43**
  > (cookable-now doesn't belong on the planner — the brief proposes a
  > `cookable_now` suggestion reason). **F41** (conflicting colour/iconography)
  > is [OPEN] as a standing risk: the brief *adds* accent surfaces and owes a
  > count against it before its unit can close.
- MEAL PLANS — rail / scroll model / calendar — `04_proposals/BRIEF_MEAL_PLANNER_RAIL_AND_SHELL.md`
  (2026-08-28; narrows `IMPL_PLAN_MEAL_PLANS_REBUILD.md`, supersedes its sticky-
  column and calendar-popover moves, does not reopen its Q1 — already closed by
  FU-304). Also gives **L271** ("planned in" recipe filter) its first home, as a
  logged candidate rail chip rather than a recommendation, and records that
  **L93/L212/L231**'s app-wide sticky-footer-counts directive is *diverged from*
  by its toolbar status strip (FU-782 D8). Designed, not built.
- SHOPPING LISTS / DETAILS / MODE — `04_proposals/SHOPPING_LIST_REDESIGN_PROPOSAL.md`
  + `04_proposals/IMPL_PLAN_SHOPPING_LISTS.md` (C-impl phased plan, written
  2026-06-06; maps L401-422), B9.1. **UX layer superseded 2026-06-12 by
  `04_proposals/PROPOSAL_SHOPPING_LIST_UX_V2.md`** (S1-S18 session bullets +
  re-maps L402-421; shop-mode page merged away, rail/dropdown, chip axe).
- REPORTS — feedback empty (the section holds a literal `?`) and deferred by the
  owner in `FEEDBACK_TRIAGE_AND_PLAN.md` §6. **Reviewed 2026-09-02 —
  `05_investigations/REPORTS_PAGE_REVIEW.md`** stands in for the missing feedback; finalisation sweep 2026-10-23: `05_investigations/finalisation/CHUNK_12_reports_memory.md` (32 findings, 10 help entries)
  pass: owner-supplied bullets captured verbally, mapped in that doc's §10. No
  `F`/`L` bullets flip here (there were none to flip); the cross-cutting bullets
  it *does* land on are **L254** (money switchable off) and **L467/L471** (export
  formats, heading type sizes). **L254 is now covered (2026-09-02):** chunks 1+2
  shipped, FU-816 resolved — the six dollar-answering reports are gated on the
  client *and* refuse with 403 at the endpoint, while the four count-based ones
  keep the page worth a nav entry. L467 (export) and L471 (heading sizes) remain
  gaps, addressed by chunks 3 and 5 respectively.
- WASTE — `04_proposals/PROPOSAL_WASTE_MINIMISATION.md` (C-waste, written 2026-06-24). Feedback was empty; this is charter-/scope-discipline driven. The `/waste` page is dissolved into a StockItemRow capture (Mark as wasted + Undo), a Cookbook filter (Uses expiring ingredients, 14d), a StockOverview sort (Expires soonest), and a simplified `waste_insights` Dora tool. Dora Score waste-as-pillar reassessment deferred → **FU-302**.
- ALERTS — `04_proposals/PROPOSAL_ALERTS.md` (C-9, written 2026-06-06; maps
  L437-441 + dashboard alert bullets L57/L60). Dashboard card = contract only
  (deferred); price/back-in-stock subscriptions folded into central management.
- SETTINGS / CONFIG (cross-cutting) — `04_proposals/PROPOSAL_CONFIG_AND_OPTINS.md`
  (C-cross, written 2026-06-06): money opt-in (L254), nutrition off/simple/complex
  (L262-263,287), tag/cuisine/category/tools taxonomy editors (L235,238,255,260,
  264,283-284,310), location-display zone policy (L81,107,321), feature-flag panel
  (L42). Settings-shell redesign itself stays deferred.
- MOBILE VIEW — empty in feedback.
- NO AREA / MISC — most bullets covered by B9 + INV-3; the unresolved
  ones are itemised in Bucket C above.
- Technical Considerations — `04_proposals/STATE_OWNERSHIP_REFACTOR_PROPOSAL.md`
  covers the "single source of truth, more backend" bullet.

---

## Audit log

| Date | Pass | Notes |
|---|---|---|
| 2026-06-06 | Initial pass | Created this file as part of the docs reorg. Buckets A/B/C reflect a full walk of `Feedback _ Fixes - as of [06-Jun-2026].md`. INV-7..10 added to `03_prompts/INV_investigations.md`. |
| 2026-06-06 | C-cross written | `PROPOSAL_CONFIG_AND_OPTINS.md` (C-cross) lands the cross-cutting config layer. Flipped money/nutrition/tag-taxonomy/location/feature-flag bullets from "→ C-cross (TBD)" to a written home. Completes the Wave-C design briefs (companion C-6/C-8 remain out of Dora-core scope). |
| 2026-06-17 | Products-as-overlay pivot | Wrote `04_proposals/PROPOSAL_PRODUCTS_AS_OVERLAY.md` (Products gated on data-presence not a flag; new `PreferredBuy` everyday construct; onboarding personas removed; Product Search → companion behind a configured URL). Superseded the spine of `PROPOSAL_SIMPLE_MODE.md`; reshaped `PROPOSAL_INGESTION_API.md` + onboarding docs + RECONCILED §7. Re-homed L42/L45/L46/L84/L131/L191/L192/L226/L254. |
| 2026-06-22 | FU-227 "Your prices" landed | `04_proposals/IMPL_PLAN_YOUR_PRICES.md` shipped all 8 chunks (unit-conversion helper → observation model reshape → shared `PriceEntry` + row button + widget → baseline math → shopping-line prefill + harvest + Receipt relabel → bottom-sheet history + per-product observation overlay → ingest-obs path removal → close-gate + R-017). Flipped L226 (bottom-sheet for Price History — ADDRESSED, `PriceHistoryBottomSheet.vue`); L419 (shopping line price entry as receipt — ADDRESSED, prefill-and-persist + I1 Receipt relabel); L420 (close the loop / list-becomes-receipt — ADDRESSED, harvest-on-/finish + LC-1 idempotent + E3 dead-branch removal). Also addressed implicit "what does this usually cost me" + "warn me when something jumped" (the C5 widget + above-1.15× chip, observations-only baseline per LC-2). L225 (Price-History box-fit bug) stays OUT OF SCOPE → FU-214. |
| 2026-07-07 | Budget-defense swaps brief written | `04_proposals/PROPOSAL_BUDGET_DEFENSE_SWAPS.md` — Wave-C design brief for FU-451 (P6-09 negotiator) + FU-450 (P6-03 deal-quality surviving pieces). Provides a *solution* home (not just re-homing) for the recipe-cost-→-meal-plan-→-budget integration facet of **L254** — swap ranker on the meal-plan week + summary bullet on the Dashboard budget card, `cost_per_week` computed server-side on-the-fly, both surfaces gated on the same money-features opt-in the bullet demanded. Partial for **L341** (sequential meal-plan builder → shopping-list flow — the swap surface sits inside the meal-plan week context L341 wanted more usefulness around; the full sequential builder is separate work). L342 (templates + auto-add) stays untouched — deliberately orthogonal so a template can still be swap-negotiated per-week without contaminating the template row itself. |
| 2026-08-28 | Meal-planner rail/shell/calendar brief written | `04_proposals/BRIEF_MEAL_PLANNER_RAIL_AND_SHELL.md` — owner feedback that the recipe-picker rail and the week calendar both look and feel wrong, after a round of nine drawn options. Cleared the **stale MEAL PLANS pointer in Bucket D**: `IMPL_PLAN_MEAL_PLANS_REBUILD.md` §13 re-graded 13 bullets 🟡 in June and its §15's instruction to flip them here was never carried out, so this file has read "covered" for two months over a set the predecessor doc itself marked regressed. Re-covered F9/F16/F20/F22/F41/F42/F44/F46 in the brief's §11; **re-opened F13, F17, F9 and F43** because the brief revises the owner's own earlier feedback on each and the revisions are unconfirmed (FU-782 §9 D1/D6/D7/D8); left **F41** open as a standing risk the brief must measure itself against, since it adds accent surfaces to a page already reported as visually conflicting. Gave **L271** its first home. Recorded that the toolbar status strip **diverges** from L93/L212/L231's app-wide componentised-sticky-footer directive rather than claiming consistency. Designed, not built — build gated on FU-782. |
| 2026-09-06 | Products program planned (Dora + companion) | `04_proposals/IMPL_PLAN_PRODUCTS_PROGRAM.md` — the owner reopened the whole products area and widened it to the companion (scraper robustness, an Aldi rewrite, an explicit data-flow contract, product hard-delete, a two-mode card/row redesign). Its §8 gives **every MY PRODUCTS (MP-1..MP-23) and PRODUCT HISTORY (PH-1..PH-10) bullet** a batch or an explicit out-of-scope reason, so the June review feedback parked under FU-214 finally has a full home. Flipped: **L197** hard-delete → COVERED (decision D-1, batch C) after being an open fork since June; **L205/206** bulk-select variants → COVERED (batch F) — they were the one true GAP; the My-Products link affordance → COVERED. Marked **superseded rather than covered**: the filter-clear-consistency and filter-default-open bullets, both answered differently by the owner's own 2026-08-20 calls. Confirmed **PH-6 real** (the %off chip *is* coloured inconsistently — `discountPct` exists 4× and renders 3 ways, FU-885) and four PH bullets as already-fixed-pending-browser-confirm. Recorded the original spec's *inactive means do-not-scrape* intent as rule PF-8, and its unsave-tombstone requirement as **superseded** by the new push model. Planned only — **no code written**. |
