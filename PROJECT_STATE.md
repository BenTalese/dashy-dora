# Dashy Dora — Project State

**Last reviewed: 2026-11-05.**

This is the single front door: where every phase and workstream is up
to, and what needs your attention. For *where things stand* this doc
wins; for *how/why* a decision was made, follow the linked planning
doc. Regenerated after each substantive close-gate (see
`CLAUDE.md → Regenerating PROJECT_STATE.md`); if it looks out of date,
the last session skipped its close-gate — trust `DORA_WORKLOG.md` +
`CHANGELOG.md` over it.

Status key: ✅ done-clean · ➗ done-with-carve-outs · 🟡 active/in-progress ·
🔵 designed-not-built · ⚪ not-started · 🔴 needs-a-decision · 🕸 stale ·
📦 superseded · 🗄 historical.

---

## Where we are right now

**Dora 1.0.0 is deployed to Altair (Dora and the companion); you want every FU resolved before launch.** 11-05: the stray `1.0.0` tag deleted; CI workflows back in the repo (Actions off until you switch them on); warning ink (FU-986); then your batch 2: item history groups repeats (DR-13), loose vs boxed prices kept apart (FU-983), admins hear about new releases (FU-626), Reports cards can be hidden and reordered (FU-832), savings measured against your usual price (FU-831), and Firefox can talk to Dora through server speech recognition (FU-788). All uncommitted. Then batch 3: "Use soon", good-news price chips, Price watches, one essentials option, touch sizes, the burger QR mark; FU-648/638 confirmed fine. Then batch 4: FU-578 closed out, AU/UK food names in nutrition matching, System theme follows the device live, release notes fix, Discussions linked. Then a leftovers sweep: one toast per server error, named segmented controls, sign-out drops push alerts, `test/` linted. 108 FUs open, all leftovers I can do alone (donation links done: FU-608).

**11-01 to 11-04: every open owner decision was answered and built.** Highlights: Dora's AI reads the Help guides; configuration is env-only; onboarding finishes in one all-or-nothing request; preferred buys coexist with products; the colour-board picks are applied; cook timers persist; templates keep batches and product lines; lists name themselves; server dates follow the region; one "bought" rule; stores in backups; cooking-word units; current Claude models.

**11-04 (later): the remaining backlog was cleared.** Pack pricing and the per-unit buy verdict (FU-978), the dashboard leftovers, the "Email enabled" switch dropped, region decimals, faster My Products and QR printing, the big pages split, one focus ring and a token sweep, one segmented control and one select. The Help What's new page is gone. 43 FUs closed; the new small leftovers are FU-980 to FU-986.

**Your decisions today:** FU-965 and FU-918 closed (not worried); iOS is won't-do; every device and browser check up to 11-04 counts as done, so the 10-23 to 11-04 DORA_VERIFY sections were deleted. Three new lines remain there for what the drives couldn't reach.

**Tests:** full pytest passes, vitest 924, vue-tsc and eslint clean. Alembic head `a4d9e2b7c5f1`. The 11-05 work is uncommitted.

---

## Phase board

| Phase | Scope | Status | Remaining |
|---|---|---|---|
| **0 — Foundations & truth** | Theming, filters, modals, loading, text, renames (P8-01), Wave-B bugs, config/opt-ins | ✅ | Colour picks applied 11-03; token debt (FU-834/764/941/850/839) closed 11-04. Warning ink added 11-05 (FU-986). Residual: FU-865, FU-224/FU-010 (late look review). |
| **1 — Close the loop** | Shopping lists, cook mode, stock, cookbook, meal planner, suggestions, costing, stocktake | ✅ | Nothing unbuilt. Three QA rounds (10-29/30), the FU-971 walks and the 11-04 sweep are done, and you count the browser walks done. Left: minor leftover FUs per workstream below. |
| **2 — Ingestion API + companion** | `/api/ingest` seam, standalone companion, Merchant→Store | ➗ | Products program complete (all 8 batches; FU-884 Aldi rewrite resolved). 11-01: `is_available` on the ingest wire, so deploy the companion with Dora. Open: FU-960 (contract notes), companion debts FU-886/887/891/924. |
| **3 — Champion** | Zero-Input Pantry, buy/wait oracles, barcode-add, Dora Score, culinary memory, native app | ➗ | P8-01..P8-10 built. Android cleartext built (FU-962); iOS is won't-do. Native FCM push parked until Phase 4 (FU-465). |
| **4 — Open-source release** *(was Commercialize)* | README/showcase, release process, support channel, ops/CI | 🟡 1.0.0 deployed | Deployed to Altair; CI workflows back 11-05 (Actions off until you switch them on). Unanswered: FU-557 (support channel). Later: FU-608/FU-406 (OSS infra, showcase), FU-405 (ops). |

---

## Major workstreams

| Workstream | Status | Where it's at | Governing doc |
|---|---|---|---|
| **Finalisation sweep** | ✅ | Stage 1 (20 chunks, 729 findings) and Stage 2 (all 20 chunks applied, FU-929) closed 10-23 to 10-27. QA rounds 1–3 (10-29/30) fixed about 150 bugs; the FU-971 walks B–E (11-01/02) deleted about 160 checks on pass. 11-01 to 11-04: every owner decision in FINALISATION_REVIEW §0 answered and built, then the whole "work I can do alone" backlog (43 FUs closed). Leftovers: FU-981 (13 small parts), FU-983, FU-984, FU-985, FU-951..953, FU-959. | [FINALISATION_REVIEW](docs/05_investigations/FINALISATION_REVIEW.md) · [COVERAGE](docs/01_charter/FINALISATION_COVERAGE.md) |
| **Meal planner** | ➗ | The 09-05 to 09-13 owner batches (cost on card/day/rail, one signal per channel on the card, cards-per-meal builder, over-budget banner, *Apply template* dialog) stand, and you count them walked. QA: every week is fetched; add/adjust go through a promise queue (R-101). Since 11-01: the two-device lost update (FU-967), swap inside a batch (FU-956), slot rename (FU-957), entry-id churn (FU-878) and scoped cookability (FU-908) resolved; Build my week flags an over-budget week; templates keep batches (migration `c8f3a6e2d9b4`). Open: FU-953, FU-907, FU-863, FU-802, FU-935, FU-937. | [PROPOSAL_MEAL_PLANS](docs/04_proposals/PROPOSAL_MEAL_PLANS.md) · R-086 |
| **Settings & admin IA** | ➗ | Three nav groups since 09-03 (Install · Kitchen features · Data & access). Config is env-only (11-01). 11-04: the "Email enabled" switch is gone (FU-906, migration `d5a9c3e7f2b1`); Dora mails once SMTP is set, and Settings → Email warns when the public URL is missing. Open: FU-867, FU-858, FU-859. | `CHANGELOG [Unreleased]` · R-081 |
| **Feature flags & opt-ins** | ✅ | `scanning_enabled` is hide-only by decision (FU-954, 11-01); the ingest flag is enforced (FU-866); 11-04 swept the remaining install flags for "gates nothing" and dropped `email_enabled` (FU-906). | `ENGINEERING_STANDARDS` R-081 |
| **Cook mode / Sous Chef** | ✅ | The 09-13 batch (shared step-list look, notes on the step card) and the voice batch stand. 11-04: cook timers persist, the page is split along its seams (FU-942), the placeholder step is no longer spoken (FU-982). FU-853 (chime vs CSP) and FU-763 resolved. No open FUs of its own. | `RecipeCookMode.vue` |
| **Theming & design tokens** | ✅ | 11-03: colour-board picks applied (`--primary-ink`, `--brand-wordmark`, deeper Pesto/Blueberry, new dark secondaries). 11-04: undeclared and duplicate tokens fixed, one focus ring readable in every theme (FU-941). 11-05: warning ink tier (FU-986). Open: FU-865. | [board](https://claude.ai/artifact/39cAkaYr2TXUpEgxeAum25) |
| **Zero-Input Pantry / inference** | 🟡 | Extended to recipes, lists and the planner, each behind its own off-by-default opt-in; planned demand is a sibling signal (R-074/ADR-071). Open: FU-851 (stale after a plan edit elsewhere), FU-849 (not on the shopping list yet). | [PROPOSAL](docs/04_proposals/PROPOSAL_ZERO_INPUT_PANTRY.md) |
| **Products-as-overlay** | ✅ | Phases 0–E code-complete; the Phase-F tail is superseded by the products program. FU-178 resolved. Single Alembic head, now `d5a9c3e7f2b1`. | [RUNBOOK](docs/04_proposals/PRODUCTS_OVERLAY_RUNBOOK.md) |
| **Products program (Dora + companion)** | ✅ complete | All eight batches and four decisions closed 09-06 to 09-08 (R-087/ADR-084); custom products built. 11-01: the companion sends `is_available`. 11-03: preferred buys coexist with products per item, and Product Search shows whenever its link is set. | [PLAN](docs/04_proposals/IMPL_PLAN_PRODUCTS_PROGRAM.md) |
| **Prices surface** | ➗ | FU-703 decided **keep** (10-21): `/price-history` and My Products stay. Polish still open: FU-704..708, FU-911, FU-732. | [ASSESSMENT](docs/05_investigations/PRICES_SURFACE_UX_ASSESSMENT.md) |
| **Email & notifications** | ✅ | FU-860 decided (10-21): no scheduled mail with products off is fine. The deals mail is skipped without a public URL, and Settings → Email now warns about it (FU-969, 11-04). Open: FU-627, FU-626. | `CHANGELOG [Unreleased]` |
| **Recipes & cookbook** | ➗ | One `_item_price` (R-076), one `household_measures` grams resolver, one shelf denominator (R-089). 11-04: a "pack" bought off a list prices as the whole pack (FU-978), a recipe not-found page, "/ serve" cost chips, cooking-word units, majority price baseline (FU-876), filters fit two lines at 1280px (FU-773); recipe CSV export removed; pages split (FU-934). Open: FU-983, FU-895, FU-900, FU-901, FU-855, FU-857, FU-680. | `recipe_cost.py` · [INVESTIGATION](docs/05_investigations/RECIPE_PRICE_UNIT_MISMATCH.md) |
| **Shopping lists (v4)** | ✅ | Built end to end, all three faces on one row skeleton (R-090/R-091/R-092). 11-04: lists name themselves from the date and region, one "bought" rule app-wide, templates keep product lines (migration `b6e1d9c4a2f7`); list copy and template clone removed; the detail page is split (FU-780). FU-958/966 resolved. Open: FU-913, FU-808, FU-740, FU-757, FU-714. | [SHOPPING_LIST_UX_V2](docs/04_proposals/SHOPPING_LIST_UX_V2.md) · R-090 |
| **Dashboard** | ➗ | Nine cards since the 19-item sweep; the 09-05 hero grid stands. 11-04: restock radar hides items already on a list (FU-897), the greeting follows the household timezone (FU-970), one `/health` call on cold load (FU-974), per-card errors (FU-976). Open: FU-985 (cookability loads the whole cookbook), FU-868, FU-870, FU-871, FU-837, FU-832, FU-831. | [IMPL_PLAN_DASHBOARD_REBUILD](docs/04_proposals/IMPL_PLAN_DASHBOARD_REBUILD.md) |
| **Reports** | ✅ | Five chunks, money-gated (R-058); you confirmed the four-card shape (FU-947 (3)); savings `lists[]` dropped. Open: FU-843..847, FU-947 (1)(4). | [REVIEW](docs/05_investigations/REPORTS_PAGE_REVIEW.md) |
| **Shared component anatomy** | ✅ | 11-04: `BaseSegmented` and `DoraSegmented` merged into one keyboard-accessible radiogroup (FU-848), every `q-select` on `BaseSelect` (FU-675), the `subtle` button at small-action sites (FU-677); the page splits share state through provide/inject (R-011). Open: FU-980 (unnamed radiogroups), FU-909, FU-920, FU-795. | `BaseSegmented.vue` |
| **Touch affordances / tap targets** | ➗ | 44px on touch via `@media (pointer: coarse)` (R-085/ADR-082), segmented controls included since 11-04; `InfoTip` shows at once (R-088). Open: FU-877 (the 36–40px tier). | `BaseButton.vue` · `css/app.scss` |
| **Assistant / voice / offline** | ➗ | Dora's AI looks up Help through `app_help` (11-01); 11-04 moved to current Claude models (no `temperature`, thinking replayed on tool turns). Hosted-LLM tool calls and voice download fixed 10-30. Offline: an unvisited page keeps the shell and banner (11-03). FU-722/751/724 closed. Open: FU-788 (Firefox voice input), FU-787 (Piper packaging). | `useOfflineQueue.ts` |
| **Design remediation (DR)** | ✅ | DR-1..15 done or done-with-carve-outs (DR-13 built 11-05); DR-16 skipped by you 11-05. | [DESIGN_REMEDIATION_PLAN](docs/04_proposals/DESIGN_REMEDIATION_PLAN.md) |
| **Build & deploy** | ✅ deployed | 1.0.0: one version source, build id on About, PUID/PGID, README quick start, Secure cookies by default, env-only config, migrations on boot; the deploy script ships the companion too. FU-965 closed (you're not worried); FU-955 (cross-install restore) and FU-719 resolved; Android cleartext built, iOS won't-do. Deployed to Altair; the old `1.0.0` tag deleted 11-05; CI workflows uncommented (FU-721 closed). Open: FU-720 (route-map check). | `README.md` |
| **Verify tooling** | ✅ | Scratch backend + Playwright drives are the default; FU-758 resolved. 11-04: `DORA_TEST_DB_FILE` lets parallel pytest runs use separate DBs (part of FU-952). DORA_VERIFY lost its 10-23 to 11-04 sections on your word; three new lines remain. | `DORA_VERIFY_TRIAGE.md` |
| **Postgres portability & migrations** | ✅ | The whole chain runs on an empty Postgres (fixed 10-30, R-102/ADR-099); FU-045 and FU-965 closed. Single head `d5a9c3e7f2b1`. Open: FU-888 (a NUL byte in a nutrition search 500s on Postgres). | `ENGINEERING_STANDARDS` R-102 |
| **Security** | ✅ | 10-30 hardening (14 fixes, SEC-2/3/4, R-104/ADR-101); sign-ups closed by default; FU-964 accepted risk; FU-973 (split-host CSRF) closed. Open: FU-655, FU-575. | `CHANGELOG [Unreleased]` |
| **Regional formats & rendered documents** | ✅ | Print views, CSVs and emails follow the household region through `locale_format.py`. 11-04 closed FU-969: server-built dates and list names follow the region, and quantities use the regional decimal mark. | `locale_format.py` |
| **Accessibility** | ➗ | Axe rules fixed 10-30; contrast settled by the colour picks (FU-963). Warning text contrast fixed 11-05 (FU-986). Open: FU-980 (radiogroups without a name). | FU-980 |

---

## ⚠️ Needs your attention now

**Total open backlog: 108 items in `DORA_FOLLOWUPS.md`.** None blocks the release. The list below is what needs you now.

1. 🟢 **Commit** the 11-05 work, then deploy (three new migrations run on boot; the image now installs faster-whisper).
2. 🟢 **After deploy:** the "Finish-off sweep" and "Voice from Firefox" lines at the top of `DORA_VERIFY.md`.
3. 🟢 **CI:** workflows are back (FU-721 closed); switch Actions on when you want them.
4. 🟡 **Leftovers I can do alone:** FU-981 (13 small parts), FU-984 (double toasts), FU-985 (dashboard speed on a big cookbook), FU-980 (radiogroup names) and about 110 more.

---

## Where the detail lives

- **`DORA_WORKLOG.md`** — per-session handoff narrative (what ran, decisions, what's next).
- **`CHANGELOG.md`** — product/code changes that shipped.
- **`DORA_FOLLOWUPS.md`** — the full ~108-item open backlog (this dashboard shows only the top).
- **`DORA_VERIFY.md`** — your browser-verify checklist (walk + delete as you confirm).
- **The full per-doc register is below** — every planning doc's verified state.
- **Charter / how & why:** `docs/01_charter/` (vision, standards, master plan).
- **To refresh this doc:** see the regeneration routine in `CLAUDE.md`.

**Do not trust as current** (kept for history only): the old `STATUS.md`
(retired to `06_legacy_prompt_plans/`), `99_scratch/PROGRESS_REPORT_2026-06-12.md`
and `FEEDBACK_AUDIT_2026-06-12.md` (June snapshots — say Phase 2/3 = 0%, both wrong
now), `docs/00_DOC_GRAPH.md` (stale stub, FU-428), and `00_original_spec/` (historical,
pre-dates the current codebase).

---

# Document register

Complete per-doc state map — every active planning doc opened, classified, and
cross-checked against `DORA_WORKLOG.md` + `CHANGELOG.md` + code reality (verified
2026-08-12 via a 5-agent fan-out). This is the "everything accounted for" backing
for the dashboard above; the dashboard is the rollup, this is the per-doc truth.
**You don't need to read this** — it's the audit trail. **127 active docs** across 8
folders; the 157 `docs/00_original_spec/` files are charter-designated historical
(one bucket, see end).

State key: ✅ done-clean · ➗ done-with-carve-outs · 🟡 active · 🔵 designed-not-built ·
⚪ not-started · 🕸 stale · 📦 superseded (successor named) · 🗄 historical.
Investigations: ✅ closed-actioned · 🟡 open · 🔵 informational · 🕸 stale.

## Systemic findings (from the 2026-08-12 re-audit)

21. **✅ Security thread closed.** `AUTH_ASSISTANT_SECURITY_FINDINGS` is now a triaged standing register — the HIGH CSRF + MEDIUM email-change were fixed under FU-197 (2026-06-30); the 8 residual Medium/Low findings went to FU-515 (resolved); the orphan audit-follow-up FU-447 was reconciled + closed. A.5/A.6/A.7 are accepted risks (A.6 → Phase-4). Nothing open.
22. **🕸 Stale "no code yet" / "designed-not-built" headers on ~15 shipped docs (FU-445).** Bodies are accurate records; only the top status line lies (e.g. IMPL_PLAN_ALERTS, IMPL_PLAN_MEAL_RECONCILE). Judge by this register, not the header.
23. **🕸 `docs/00_DOC_GRAPH.md` is a retired stub (FU-428).** Superseded by this doc + the CLAUDE.md anti-drift rule.
24. **Backlog right-sized.** The old dashboard cited "~60 open items"; the ledger actually holds **17**. Most of the prior attention list had long since moved to `_RESOLVED`.

## 01_charter — governance (6)

| Doc | Type | State | Purpose | Evidence |
|---|---|---|---|---|
| DASHY_DORA_CHAMPION_PLAN.md | Charter / vision | 🟢 authoritative | Part 8 vision + 12-principle Decision Charter + operating procedure | Governing rubric cited across CLAUDE.md |
| RECONCILED_FINISHING_PLAN.md | Master plan | 🟢 authoritative | Phases 0–4, resolved decisions §7, scope arbiter | "Active — all decisions resolved"; owns order/scope |
| ENGINEERING_STANDARDS.md | Rules / ADR log | 🟢 authoritative | R-001..R-088 code rubric + ADR-001..085 log, checked every task | Living; R-088 + ADR-085 (app-wide component defaults live in a `Base*` wrapper) added 2026-09-09. Row previously read "R-001..R-040" — stale since August |
| DESIGN_STYLE_GUIDE.md | Design spec | 🟢 authoritative | Prescriptive D-rules token/component spec, enforced via R-035 | Authoritative since 2026-07-18; D-020 (indicator tokens) + **D-021 (nav is one flat level)** added 2026-08-16/17 |
| FINALISATION_PLAN.md | Late-game plan | 🟡 active — Stage 1 ✅, Stage 2 in progress | Two-stage code-walk sweep (FST/Help/Review/Tests, then test-guarded execution) | Stage 1 closed 2026-10-23: 20 chunk files + 5 master docs; §3.3 hand-rolled list consolidated in `HANDROLLED_VS_LIBRARIES.md` |
| FINALISATION_COVERAGE.md | Coverage register | 🟡 active | Per-chunk × per-track status matrix for the sweep | All 20 rows FST/Help/Review/Tests ✅ (2026-10-23); **Applied ✅ chunks 1–5, 7, 8, 11, ➗ the other 12** (2026-10-27) |

## 02_feedback — inputs (3)

| Doc | State | Purpose | Evidence |
|---|---|---|---|
| Feedback _ Fixes - as of [06-Jun-2026].md | 🟢 authoritative | Raw user feedback — source of truth for coverage tables | Named SoT in CLAUDE.md |
| COVERAGE_GAPS.md | 🟡 active-living | Tracker: feedback bullets lacking a brief/proposal home | Living; entries flip gap→covered as briefs land |
| FEEDBACK_TRIAGE_AND_PLAN.md | 📦 superseded (RECONCILED_FINISHING_PLAN) | Feedback→work map | Superseded for sequencing/strategy; retains what/why map |

## docs/ root — navigation & guides (2)

| Doc | State | Purpose | Notes |
|---|---|---|---|
| 00_DOC_GRAPH.md | 📦 superseded → stub | Former per-prompt required-reading map | Retired (FU-428); CLAUDE.md calls it a legacy stub |
| INGESTION_GUIDE.md | ✅ done-clean | Power-user guide: sourcing data via `POST /api/ingest` | Matches shipped ingestion API (C-10.5) |

## 03_prompts — executable prompts (19)

The whole pack is a historical execution map — live state lives here in
PROJECT_STATE.md. Index banner (verified 2026-07-02): all Wave-A + Wave-B
prompts shipped; every Wave-C brief produced its proposal (most now built via
IMPL_PLAN_*); INV prompts produced their reports.

| Doc | State | Evidence |
|---|---|---|
| 00_INDEX.md | 🗄 historical (banner added) | "Status column is stale… read as historical execution map" |
| A1 / A1b / A2 / A3 / A4 / A5 / A6 / A7 / A8 | 🗄 historical | Wave-A foundation sweeps (tokens, button/modal/filter, skeletons, text-scale, footer, renames) — all shipped |
| B1 / B3 / B4 / B5 / B7 / B8 / B9 | 🗄 historical | Wave-B bug clusters — all shipped (B2/B6 folded); B9 item 4 (command palette) cancelled |
| C_big_rock_design_briefs.md | 🗄 historical | Big-rock briefs → proposals → IMPL_PLANs; C-6/C-8 companion-scope |
| INV_investigations.md | 🗄 historical | INV-1..10 → reports; INV-9 (palette) superseded |

## 04_proposals — designs, impl-plans, runbook (66)

**IMPL plans & runbook (A–M):**

| Doc | Type | State | Purpose | Evidence |
|---|---|---|---|---|
| FULL_SYSTEMS_TEST | QA walk document | 🔵 designed-not-built (walk pending) | Per-surface golden paths, edges, personas, release-gate roll-up | Assembled 2026-10-23 from `finalisation/CHUNK_*` §A; walked by the owner on a near-final build |
| TEST_PLAN_INVENTORY | Test plan | 🟡 active | 35 must-write rows + nice-to-haves, lean stance | Assembled 2026-10-23; rows land with their Stage-2 change |
| DESIGN_REMEDIATION_PLAN | Design backlog | 🟡 active | Action the 2026-07-18 UX/design audit (DR-1…16) | DR-1/1b/2/3/4/5/6/8/10/11 done (10=owner leave-as-is), DR-7 ➗ (FU-624), DR-9 ➗ (FU-631), DR-14 ➗ (FU-632), DR-15 ➗ (FU-694); remaining: DR-13/16 + the **Alerts half** of DR-12 (its meal-plans mini-month was overruled by D7 and built as a month grid 2026-08-30) |
| DORA_ASSISTANT_ARCHITECTURE_PROPOSAL | Proposal | ➗ carve-outs | Unify assistant capability model + LLM config | §2.2 registry deliberately not built; §7 multi-provider shipped |
| IMPL_PLAN_ALERTS | Impl plan | ✅ done | Alerts control-centre (C-9) | Digest+push+prefs shipped; header stale |
| IMPL_PLAN_AUTH_SHELL | Impl plan | ✅ done | Extract shared AuthShell + AuthButton (C-19) | `AuthShell.vue`/`AuthButton.vue` exist |
| IMPL_PLAN_CART_BUTTON | Impl plan | ✅ done | Unify add-to-list into one cart control (C-7) | `AddToListButton` in use |
| IMPL_PLAN_CONFIG_AND_OPTINS | Impl plan | ✅ done | Feature-flag/opt-in spine (C-cross) | `useFeatureFlags`/health flags shipped |
| IMPL_PLAN_COOKBOOK | Impl plan | ✅ done | Recipe domain rebuild (C-4) | Structured steps/tags shipped |
| IMPL_PLAN_COOK_MODE | Impl plan | ✅ done | Cook-mode rebuild (C-3) | `RecipeCookMode.vue` live |
| IMPL_PLAN_DASHBOARD_REBUILD | Rebuild brief | ✅ done | Rebuild DashboardPage around savings | Phases 0-7 shipped; the **two commitments the 2026-09-02 re-audit found unmet are now both met**: §2.2's card census is encoded at 14 registered / 11 default-on with `dashboardCards.spec.ts` holding it (FU-830), and §6's DoD "thin composition over `components/dashboard/*` — the 1964-line monolith is gone" closed for real at chunk 5 — all 14 card bodies extracted, page 3,258 → 1,888 lines (FU-829, R-072/ADR-069) |
| IMPL_PLAN_ENV_TO_APPSETTING | Impl plan | ✅ done | Promote 12 env vars to AppSetting (FU-333B) | Header "SHIPPED 2026-07-05/06" |
| IMPL_PLAN_ERROR_HANDLING | Impl plan | ➗ carve-outs | App-wide error-message polish (FU-099) | `apiErrorHandler.ts` live; full 166-catch sweep unconfirmed |
| IMPL_PLAN_HELP_CHIPS | Impl plan | ✅ done | Add (?) hover-help chips (FU-044) | `help_outline` tooltip pattern across pages |
| IMPL_PLAN_INGESTION_API | Impl plan | ➗ carve-outs | Ingestion `/api/ingest` + Your-Prices (C-10) | Built; browser-verify pending |
| IMPL_PLAN_MEAL_PLANS | Impl plan | ✅ done | Build meal-plans surface (C-2) | Rebuild doc: all F1–F49 shipped |
| IMPL_PLAN_MEAL_PLANS_REBUILD | Critique+rebuild | ✅ done | Re-critique + rebuild the C-2 result | `useMealPlanner.ts` + components exist |
| IMPL_PLAN_MEAL_RECONCILE | Impl plan | 🟡 in-progress | Manual meal-plan reconcile (FU-317) | Chunks 1–5 shipped; Chunk 6 pending; header stale |
| IMPL_PLAN_ONBOARDING | Impl plan | ✅ done | Onboarding redesign + de-persona (C-5/FU-210) | Onboarding pages live |
| IMPL_PLAN_PRODUCTS_AS_OVERLAY | Impl plan | ➗ carve-outs | Chunk detail for products overlay | Phases 0–E done; Phase-F tail superseded by IMPL_PLAN_PRODUCTS_PROGRAM |
| IMPL_PLAN_PRODUCTS_PROGRAM | Impl plan | 🔵 designed-not-built | Governing doc for the reopened products area across Dora + companion: data-flow contract PF-1..PF-9, batches A–G + C2, decisions D-1..D-11, feedback coverage MP/PH | Written 2026-09-06, owner-agreed, no code |
| IMPL_PLAN_RECIPE_IMPORTER | Impl plan | ✅ done | Paste-based recipe importer (FU-104/199/396) | Importer machinery present |
| IMPL_PLAN_SETTINGS_REBUILD | Rebuild brief | ✅ done | Rebuild settings shell + sections | "COMPLETE (Phases 1–5 landed)"; reworked since |
| IMPL_PLAN_SHOPPING_LISTS | Impl plan | ✅ done | Shopping-list status-model rebuild (P6-01) | Cited "landed" across surfaces |
| IMPL_PLAN_SHOPPING_LIST_RECEIPTS | Impl plan | ✅ done | Attach receipt photos (FU-334) | "Built 2026-06-30" |
| IMPL_PLAN_STATE_OWNERSHIP | Impl plan | ✅ done | Server-owned derived facts refactor | cookable/missing/allocation SSOT landed |
| IMPL_PLAN_STOCK_ITEM_DETAIL | Impl plan | ✅ done | Stock-item detail polish (C-1b) | Detail page live |
| IMPL_PLAN_STOCK_OVERVIEW | Impl plan | ✅ done | Stock overview redesign (C-1) | `StockOverview.vue`/`StockItemRow.vue` |
| IMPL_PLAN_STOCK_SIGNAL_CONSOLIDATION | Impl plan | 🟡 active | Collapse the stock row's 9 competing signals → 4; one attention rule, one cadence engine | Written 2026-08-19; **Chunks 1–4 landed** — C1: one cadence engine, D-11 belief→verdict, bulk verdicts endpoint, + the FU-684 bug that made the verdict inert; C2: verdict off the row (D-10), `buy_verdict_enabled` AppSetting→User (D-12/B7, migration `d9f4b2c7e803`), shopping list on the bulk endpoint (B6), all three walked live; C3: Step-0 cuts (3 alert kinds + the digest lane, migration `e4b1c7a95d20`) and one server-owned attention rule; C4: sort + row treatments, 9 channels → 4. **Chunks 5–6 open** (queue ranking, runner rebuild), neither blocked; FU-683 |
| IMPL_PLAN_WASTE_MINIMISATION | Impl plan | ✅ done | Waste-minimisation cluster (C-waste) | `wasteApiService.ts` + mark-as-wasted |
| IMPL_PLAN_YOUR_PRICES | Impl plan | ➗ done-with-carve-outs | "Your prices" intelligence (Phase F) | All 8 chunks landed (FU-227/425) — but the **reading** side never grew a stock-item twin: PRICES_SURFACE_UX_ASSESSMENT (2026-08-21) found compare/range/alerts still product-only; FU-703 |
| OPTIONAL_SAAS_AND_MANAGED_DEPLOYMENT | Option doc | 🔵 deferred | Parked multi-tenant SaaS / managed-host option | Deferred 2026-07-14; kept parked post-pivot |
| PLAY_STORE_LISTING | Listing draft | 🔵 designed | Play Store copy + screenshot plan | "Draft copy; no submission yet" |
| PRODUCTS_OVERLAY_RUNBOOK | Runbook/status | 🟡 active | Drive products-overlay end-to-end | Phases 0–E done, Phase F in progress |

**Proposals (N–Z):**

| Doc | Type | State | Purpose | Evidence |
|---|---|---|---|---|
| PROPOSAL_ALERTS | Proposal (C-9) | ✅ done | Design the alerts control-centre | Realized by IMPL_PLAN_ALERTS |
| PROPOSAL_AUTH_SHELL | Design brief (C-19) | ➗ carve-outs | Shared AuthShell for pre-auth pages | Built; header "no code" stale |
| PROPOSAL_BARCODE_SCANNING | Proposal (P6-02) | ➗ carve-outs | Fix scan data model, gate off-by-default | Implemented; §5.2 ingestion auto-populate deferred |
| PROPOSAL_BUDGET_AWARE_LISTS | Proposal (P2-05 tail) | 🔵 designed | Budget-aware auto shopping-list optimizer | Header "Draft"; no budget logic in `auto_generate.py` |
| PROPOSAL_BUDGET_DEFENSE_SWAPS | Design brief (FU-451/450) | ➗ carve-outs | Over-budget swaps + deal-quality signal | `swap_suggestions.py`/`deal_quality.py` shipped; good_deal alert + product swaps CUT |
| BRIEF_BUY_VERDICT_PLAN_AXIS | Design brief (2026-08-28) | ➗ built without the section 5 adherence gate (2026-10-21) | A fourth `plan` axis feeding the buy verdict from planned meals | No code; blocked on FU-774 (collides with the 2026-08-17 "shortfall is unchanged" directive). FU-775/776 downstream |
| PROPOSAL_BUY_VERDICT_ORACLE | Proposal (P8-05) | ✅ done | In-aisle "should I buy this?" verdict | Leaned on as shipped by adjacent docs |
| PROPOSAL_CART_BUTTON | Proposal (C-7) | ✅ done | Unify all add-to-list controls | `IMPL_PLAN_CART_BUTTON.md` |
| PROPOSAL_CONFIG_AND_OPTINS | Design brief (C-cross) | ➗ carve-outs | Cross-cutting config/opt-in editors | Chunks shipped; chunk 6 verify-only |
| PROPOSAL_COOKBOOK | Proposal (C-4) | ✅ done | Recipe/cookbook domain redesign | `IMPL_PLAN_COOKBOOK.md`; comparison cut per INV-6 |
| PROPOSAL_COOKBOOK_CARD_REVISION | Proposal (FU-088) | ✅ done | Recipe card redesign + optional ingredients | "BUILT — A+B+C shipped" |
| PROPOSAL_COOK_MODE | Proposal (C-3) | ✅ done | Cook mode / finish-loop redesign | `IMPL_PLAN_COOK_MODE.md` |
| PROPOSAL_HELP_OVERLAY | Design brief (C-help) | 📦 superseded (IMPL_PLAN_HELP_CHIPS) | Opt-in contextual help overlay | Superseded 2026-07-06 → help chips |
| PROPOSAL_INGESTION_API | Proposal (C-10) | ➗ carve-outs | Inbound ingest endpoint + "your prices" | Built; register-against-product deferred Phase 2 |
| PROPOSAL_LOCALE_I18N | Design brief (C-locale) | ➗ carve-outs | De-AU currency/format neutrality | Region/currency shipped; full translation out-of-scope |
| PROPOSAL_MEAL_PLANS | Proposal (C-2) | ✅ done | Meal-plan surface redesign | `IMPL_PLAN_MEAL_PLANS(_REBUILD).md` |
| PROPOSAL_MEAL_PLANS_PART_2 | Proposal (FU-617) | ✅ built | Cook batches (one cook, several days) | CHANGELOG "cook batches" 2026-08-11 |
| PROPOSAL_MEAL_RECONCILE | Proposal | ✅ done | Manual meal-plan reconcile | `MealReconcilePage.vue`; header stale |
| PROPOSAL_ONBOARDING | Proposal (C-5) | ✅ done | First-run on-ramp redesign | `IMPL_PLAN_ONBOARDING.md`; personas cut |
| PROPOSAL_PRODUCTS_AS_OVERLAY | Proposal | 🟡 active | Products as data-presence-gated overlay | Runbook-tracked; Phase-F tail |
| PROPOSAL_RECIPE_IMAGE_STEPS | Proposal (C-4 add-on) | ✅ done | Photo-based recipe steps mode | "BUILT 2026-06-25" |
| PROPOSAL_SHOPPING_LIST_UX_V2 | Proposal | ➗ superseded in part | Single-page shopping experience | "BUILT 2026-06-12"; the rail + status enum survive, but its toolbar, header cluster and row anatomy are replaced by the 2026-08-23 three-face redesign (worklog) and now by v3's overview card |
| PROPOSAL_SHOPPING_LIST_UX_V3 | Proposal | ✅ done | The overview card — replaces the detail page's header block, TripCard, plan StoreSpendCard, order-by bar and shop-mode sticky footer with one collapsible card across all three faces; toolbar recomposition (Export splits, shop date arrives, New list leaves for the rail, lifecycle actions leave for the card) | Written **and built** 2026-08-29 from an 11-bullet owner batch; all 11 decisions closed in §7, three build deviations in §10. New shared `CollapsibleCard.vue` (adopted by `StoreSpendCard` + `PantryBeliefCard`), new `ShoppingListOverviewCard.vue`, `TripCard.vue` deleted, sticky footer deleted, "Order by" deduped across faces, rename became a dialog on every width. Three reported bugs fixed (page-blanking `load()` on every list-level edit, chip vanishing while renaming, footer overlap). Driven live on all three faces at 1280/375. FU-783 resolved, FU-784 narrowed, **FU-785 new** (pre-existing: a benign ResizeObserver warning fires an "Oops" toast *and* `executeRollbacks()`) |
| PROPOSAL_SHOPPING_LIST_UX_V4 | Proposal | ✅ done | The surface pass — v3's information architecture is kept intact; this changes containers, grid, type scale and control density. Direction B (two-tier surface + row diet) for plan/run, direction A (document) for the receipt face; direction C (dense table) deferred as an evolution of the same row. **Chunk 0 is a blocking behavioural baseline** (`05_investigations/SHOPPING_LIST_BASELINE.md`) — every affordance, flag combination and edge state catalogued before any markup changes, so the cutover is auditable rather than assumed | Written 2026-08-31 from a 12-bullet owner batch (W1–W12). Findings: the surface uses `--radius-md` + a flat border everywhere and **zero** elevation tokens while `--radius-lg/xl/2xl`, `--elevation-card` and `--hero-gradient` sit unused; the row has **no grid** (flex + four competing `min-width`s), which is the mechanical cause of the reported misalignment; savings is **offer-only** (`_line_savings` returns 0 without an offer carrying `price_was`) while prices resolve actual→historic, so the two have different audiences; **both `money` and `products` default to `False`**, making the no-money tier the design baseline. Four open decisions; **7.1 and 7.2 closed 2026-08-31 by owner call** — quantity is a tile at rest that becomes a stepper on hover/focus, and the `--hero-gradient` band runs on plan+run but the receipt face is **flat**, which promotes the band from decoration to a state channel (gradient = still happening, flat paper = finished record). 7.3/7.4 resolve out of chunk 0. **Chunk 0 complete** — `05_investigations/SHOPPING_LIST_BASELINE.md`, 79 affordances catalogued from source (toolbar, both picker renderings, page furniture, overview card, three row variants, eight dialogs, keyboard/DnD/responsive, thirteen edge states, T0/T1/T2 matrix); destination/decision columns fill during chunks 1-3 and **chunk 4 is blocked until none read TBD**. Two findings amended the proposal: the mockups omitted six live page surfaces entirely (trim banner + preview, suggestions strip, deferred section, receipts strip, danger footer), and the "nine always-visible affordances" claim was an overstatement (reorder is already gated on manual sort; most of the rest is data-conditional). **Chunk 1 (the row) built and driven live** — new `ShoppingListPlanRow.vue`, `q-item` dropped for a CSS grid, always-on set cut to name/quantity/money, store select + three chip variants folded into one caption line, reorder arrows joined delete, name raised above the price. Alignment verified *numerically* (one distinct x per column across six rows) and the no-reflow constraint likewise (money x and row height identical across a hover). **Three defects the static suites missed and the running-app gate caught**: an import path `vue-tsc`+`eslint` both passed but the bundler rejected; a 375px overlap from keying the grip's hiding to `hover:none` while the column count keyed to `max-width`; and 483px phone rows from an auto-sized money column starved by its own caption. Baseline §5.1 filled — 16/16 kept-or-moved, **nothing cut**. **Chunk 2 (card + page furniture) built and driven live** on all three faces, in pesto-dark and at 375px. Card on `--radius-xl` + `--elevation-card`, headline off a magic `1.9rem` onto `--font-size-3xl`, `--hero-gradient` band on plan+run and **flat on the receipt** so the surface encodes state. **The §1.6 dark-theme worry dissolved**: `--surface-component` is already lighter than the page in dark and darker than white in light, so one declaration is correct both ways. **§7.3 closed** — the money-off headline is per-face (items-to-buy / left-to-pick / items-bought) instead of one flat count, which matters because money is the *default* install. **New C19** closes the §1.5 concealment: the total now carries `~` + "n items with no price yet" instead of burying it in the disclosure. Order-by is `BaseSegmented pill`, reusing the owner's 2026-08-31 shape (D-015). All ten furniture panels share one `.sl-panel`. Baseline §3+§4 filled; **still nothing CUT anywhere**. **Chunk 3 (receipt face) built and driven live** — the done list is a document: multiplier, name, dotted leader, amount, with `TOTAL` under the itemisation above a dashed rule and **no gradient band** (`bandIsGradient: false` against the other two faces' `true`). The §4.3 constraint was met by extracting the shared skeleton to **`src/css/shoppingRow.scss`** — grid shell, name/caption/money type scale, inset divider — consumed by both faces, rather than a `face` prop putting two mutually-exclusive control sets behind `v-if` in one component (R-001); this is the third application of the `dnd.scss`/`subbar.scss` precedent, so **no new ADR**. **A T0 carve-out came out of the running app**: with money off (the default install) the leader ran to the sheet edge and read as a number that failed to load — it is now suppressed when there is nothing at the end of it. The sheet's own header was removed as verbatim duplication of the overview card 40px above (E2 `moved`, not cut — count and date still on the card, total and unpriced-count in the footer). Plan face re-verified after the CSS extraction (single x per column, zero hover reflow). Baseline §5.3 filled; **still nothing CUT anywhere across chunks 1-3**. **Chunk 4 — the blocking cutover audit — PASSED 2026-09-01.** All 79 affordances carry a decision; **nothing was CUT across chunks 1-4**, so no owner sign-off is outstanding. §1/§2/§6/§5.2 were untouched by the rebuild and confirmed rendering live rather than assumed from a diff; all thirteen edge states rendered (five from seeded data, eight by rewriting the API payload in flight, stated as such). Three catches nothing else would have made: **P8 never existed** (the census recorded a picker kebab removed three days before it was written), **chunk 1 orphaned 165 lines of dead CSS** (`ShoppingListDetail.vue` 3,273 → 3,108 — neither `vue-tsc` nor `eslint` can see an unused class), and **the shop face is now the odd one out**, still `bordered` + `--radius-md` + `q-item` while the other two faces moved on. **K2 resolved**: `space`/`u` are guarded on `status !== 'shopping'` and verified inert on a draft — but advertised in the cheatsheet on every face (FU-808). **Chunk 5 closed FU-807 the same day** (owner: *"consistency matters"*), completing §4's "direction B for plan/run". Root cause was structural: `.sl-panel` / `.sl-list` / `.sl-section*` lived in the page's **scoped** block, so the run face *could not reach them* — a shared visual language in a page's scoped styles silently excludes every child component. They moved into the shared sheet (renamed `shoppingRow.scss` → `shoppingList.scss`), and a new `ShoppingListRunRow.vue` joined the plan and receipt rows on one skeleton. The row is a `role="button"` div (it contains the price button, and a button inside a button is invalid), so Enter/Space were wired explicitly and **re-verified live** — `q-item clickable` had been providing them for free. All three faces now measure the same slab radius, elevation and 18.5625px name; tick verified by click and by Enter; the price button opens the sheet without ticking. **v4 is built end to end.** Owed: `DORA_VERIFY` D8 (receipt lightbox — needs an attachment the seed doesn't ship); open FU-808, FU-805 |
| PROPOSAL_SIMPLE_MODE | Proposal | 📦 superseded (PRODUCTS_AS_OVERLAY) | Minimal-user workflow / pricing substrate | Spine superseded; substrate shipped |
| PROPOSAL_STOCKTAKE_MODE | Proposal (FU-430) | ✅ done | Walk-the-pantry stocktake redesign | Decisions locked + shipped end-to-end |
| PROPOSAL_STOCK_ITEM_DETAIL | Proposal (C-1b) | ✅ done | Stock-item detail polish/timeline | `IMPL_PLAN_STOCK_ITEM_DETAIL.md` |
| PROPOSAL_STOCK_OVERVIEW | Proposal (C-1) | ✅ done | Stock overview redesign | Reconciled against shipped reality |
| PROPOSAL_SUPPORT_CHANNEL | Action plan | ➗ built (dormant) | In-app support/feedback channel | Built off-by-default (FU-370); admin-editor half won't-build; stand-up = FU-557 |
| PROPOSAL_TEST_SUITE_IMPROVEMENTS | Engineering proposal | ➗ carve-outs | Test coverage/quality/cleanup | Built across ~8 sessions; Postgres CI carve-out open (FU-405) |
| PROPOSAL_USAGE_TELEMETRY | Proposal | 📦 superseded (OPTIONAL_SAAS) | Privacy-first usage analytics | Parked hosted-only; self-host won't-do |
| PROPOSAL_WASTE_MINIMISATION | Proposal (C-waste) | ✅ done | Dissolve waste page, keep signal | `IMPL_PLAN_WASTE_MINIMISATION.md` |
| PROPOSAL_ZERO_INPUT_PANTRY | Proposal (P8-07) | ✅ built (verify pending) | Inferred inventory / confidence beliefs | "Built 2026-07-03 server+SPA" |
| SELF_HOST_COMMERCIALIZATION_PLAN | Plan | 📦 superseded | Sequence to sell self-hosted Dora | Reversed 2026-07-31 → donation/OSS (FU-562/567 won't-do) |
| SHOPPING_LIST_REDESIGN_PROPOSAL | Proposal (v1) | 📦 superseded (SHOPPING_LIST_UX_V2) | Shopping-list lifecycle redesign | Structural work shipped as P6-01 |
| STATE_OWNERSHIP_REFACTOR_PROPOSAL | Proposal | ➗ carve-outs | Server-vs-client state ownership refactor | `IMPL_PLAN_STATE_OWNERSHIP.md`; §8 addendum binding |

## 05_investigations — reports (26)

| Doc | Type | State | Purpose/Notes | Evidence |
|---|---|---|---|---|
| FINALISATION_REVIEW | Senior review record | 🟡 active | 729 `NN-Rk` findings across 20 chunks; §0 = cross-chunk consolidation + Stage-2 opening order + owner decisions | Assembled 2026-10-23 from `finalisation/CHUNK_*`; FU-929 |
| HELP_CONTENT | Help drafts | ✅ landed 2026-10-29 | 100 help entries + DoraBot deltas, per surface | Built as `web_app/src/help/helpContent.ts` (166 guides, 14 topics, 17 screenshots); DoraBot half → FU-946; was gated on 20-D4 (Help IA) + 11-D1 |
| HANDROLLED_VS_LIBRARIES | Library audit | ✅ Stage 1 done | 127 verdicts (6 replace/wrap) — PLAN §7 DoD step 5 | Assembled 2026-10-23 from each chunk's §C9 |
| finalisation/CHUNK_01…20 | Per-chunk analyses | ✅ Stage 1 / 🟡 Stage 2 (1–5, 7, 8, 11 ✅) | FST · help · review · tests · §E · §F per surface | 20 files, 2026-10-23 |
| DASHBOARD_PAGE_REVIEW | PO+eng review | ✅ all 6 chunks built | The dashboard as a **drift audit**, not a design pass — the surface was designed properly (`IMPL_PLAN_DASHBOARD_REBUILD`, 7 phases) and it is the plan's *structural* commitments that lapsed: curated 8-card default → 13 of 17; DoD "monolith is gone" → 3,258 lines. Also re-opens feedback D2 (dark mode) and L254 (money opt-in) | Written 2026-09-02; 13 FUs (817-829); all 8 §8 decisions closed. All 6 chunks shipped 2026-09-02 — both structural commitments met and the design-rule sweep done (FU-828/829/830/840 resolved). Spin-offs still open: FU-835/837/838/839/841 |
| REPORTS_PAGE_REVIEW | PO+eng review | 🟡 active/in-progress | `/reports` first-ever review — stands in for the empty REPORTS feedback section. **Chunks 1–4 of §7 built and driven live 2026-09-02**; only chunk 5 (the design sweep) remains | Written 2026-09-02; 8 FUs (809-816). §7 carries a live build-status block. FU-809/810/811/812 answered by the owner; FU-816/815/813/814/833 **resolved**; FU-843 item 2 closed, item 1 downgraded; FU-844/845/846/847 spun off; FU-703 D3’s trend half built. One item corrected by `DASHBOARD_PAGE_REVIEW` §3.10: the `themeTick` bug originated on the dashboard, so FU-824 superseded half of FU-814 |
| DATA_MODEL_SANITY_SWEEP_FU393 | Schema sweep | ✅ closed-actioned | Whole-schema sanity; remediation spawned FU-563/564/565 | Fully remediated 2026-07-15; schema-match test enforces (R-034) |
| PERF_SCALE_SWEEP_FU388 | Perf sweep | ✅ closed-clean | Query-scale at 500/2000 items — no N+1s | "DB/query-scale pass done (clean)" |
| AUTH_ASSISTANT_SECURITY_FINDINGS | Security audit | ➗ closed-with-carve-outs | Auth+assistant register; re-audited 2026-07-13 | HIGH/MED fixed (FU-197/442/515); A.5/A.6/A.7 accepted |
| EMAIL_SETUP_FINDINGS (INV-4) | INV memo | ✅ closed-actioned | Password-reset flow + admin email-setup | Shipped via R-030/FU-413 |
| LOGGING_AND_DATA_LAYOUT (INV-3) | INV memo | ✅ closed-actioned | Time-based rotation + data/cache split | `logging_setup.py` uses TimedRotatingFileHandler (FU-027) |
| ESSENTIAL_FLAG_FINDINGS (INV-10) | INV memo | ✅ closed-actioned | `is_flagged`→`is_essential` wire-up + rename | CHANGELOG 2026-08-08 (migration `f4a2c7e9b1d3`) |
| RECIPE_COMPARISON_ASSESSMENT (INV-6) | INV memo | ✅ closed-actioned | Compare tool — verdict CUT | Comparison UI gone from RecipesOverview; §4 cut |
| COMMAND_PALETTE_ASSESSMENT (INV-9) | INV memo | ✅ closed-actioned | Ctrl-K palette — SHRINK→CUT | Palette/registry/recents removed (FU-029) |
| CROWD_PRICES_ASSESSMENT (INV-11) | INV memo | ✅ closed-actioned | P8-04 crowd price graph — verdict CUT | RECONCILED §7 Decision 6; unblocked FU-438 |
| PRICES_SURFACE_UX_ASSESSMENT | INV memo | 🟡 open (FU-703 keep, 2026-10-21) | "My prices" + price-history UX; the product/stock axis split | 2026-08-21; D2/D3/D4 answered, D1 open as FU-703; defects FU-704..708 |
| MAGIC_BEHAVIOUR_AUDIT (FU-092) | Audit | ✅ closed-actioned | All implicit "magic" behaviours; spun FU-315..319 | "Complete; verdicts gathered 2026-06-28" |
| ORPHANED_FIELDS_AUDIT (INV-1) | Audit | ➗ closed-with-carve-outs | Fields set-but-unread; delta-checked FU-416 | Feeds DATA_MODEL_SANITY_SWEEP |
| STOCK_OVERVIEW_PERF (INV-2) | INV memo | ➗ closed-with-carve-outs | Mount cost + latent page-1-only fetch bug (logged FU) | Broader scale cleared by FU-388 |
| PLATFORM_BUILDS_AUDIT (FU-327) | Report | ➗ closed-with-carve-outs | Delivery-target audit; real blocker = dead CI | Report-only; gaps spun as FUs; FU-327 scoped-open |
| UX_DESIGN_CRITIQUE_2026-07-18 | Design critique | ➗ closed-with-carve-outs | Synthesis of FU-578 UX passes; system-vs-screens gap | Feeds DESIGN_STYLE_GUIDE + DESIGN_REMEDIATION_PLAN |
| FEATURE_CLARIFICATIONS (INV-5) | INV memo | 🔵 informational | QR vs register-barcode, product-search, expiry↔open | Partly superseded by barcode-on-Product (FU-373) |
| HISTORY_TAB_ASSESSMENT (INV-7) | INV memo | 🟡 open | Stock-item History tab weak → REWORK | No matching CHANGELOG entry found |
| SUBSTITUTE_SWAP_ASSESSMENT (INV-8) | INV memo | 🟡 open | List-level substitute swap → REWORK (move to Shop Mode) | Swap still lives in list ⋮ menu |
| FU_512_UNIT_OF_WORK_SWEEP_RUNBOOK | Runbook | 🟡 open (analysis-only) | Mechanical UoW refactor guide (10 handlers) | "Analysis-only, no code changes yet" |
| Distribution Spec - Desktop & Mobile Client | Spec/plan | 🔵 designed (partial) | Desktop (PyInstaller) + mobile packaging plan | Desktop/gunicorn shipped (FU-397); mobile Capacitor scaffolded |
| MULTI_USER_READINESS | Pre-flight checklist | 🔵 informational | Single-tenant assumptions to dismantle before multi-user | "Draft for discussion"; Phase-4; ties FU-045 |
| COMMERCIALIZATION_REPORT | Strategy report | 🗄 historical / 📦 partly superseded | Monetization analysis; selling reversed 2026-07-31 | Productionization findings (§3–4) shipped; monetization thread historical |

## 06_legacy_prompt_plans — historical (9)

All 🗄 historical — the original pre-charter plan library, retired 2026-06-12;
superseded by `docs/03_prompts/` (active prompts) and, for state, `CHANGELOG.md`
+ `DORA_WORKLOG.md`. Files: `PROMPT_PLAN.md`, `PROMPT_PLAN_PART_2..4.md`,
`PROMPT_PLAN_PART_5_OPTIONAL.md`, `PROMPT_PLAN_PART_6_POLISH.md`,
`PROMPT_PLAN_PART_7_COMMERCIALIZATION.md`, `STATUS.md` (🕸 stale, last regen
2026-05-27, self-labelled non-authoritative), and
`PRICING_SYSTEM_REASSESSMENT_HANDOFF.md` (✅ fully executed via
IMPL_PLAN_YOUR_PRICES — FU-227, delta-checked FU-425).

## 99_scratch — raw notes (4)

| Doc | State | Recommendation |
|---|---|---|
| MINIMAL_USER_PRODUCTS_OFF_FRICTION | 🗒 untriaged | Fuss-free (products-off) talk-time audit; promote or keep (FU-181) |
| SENIOR_REVIEW_2026-06-16 | 🗄 historical | "Is it sellable?" static review; findings already spun to FUs; LOC metrics dated |
| PROGRESS_REPORT_2026-06-12 | 🕸 stale / 🗄 historical | Point-in-time snapshot; superseded by this doc — safe to delete |
| FEEDBACK_AUDIT_2026-06-12 | 🕸 stale / 🗄 historical | 309-bullet snapshot, stale as of 2026-07-01; evidence pointers only |

## docs/00_original_spec — historical bucket (157 files)

The author's first spec (Feature Boards + ~125 "I can …" notes + original plan).
Charter-designated **historical / non-authoritative** — pre-dates the current
codebase; overridden by charter/plan/feedback. Mined opportunistically when writing
a brief. Treat the whole folder as 🗄 historical; not verified per-file.
