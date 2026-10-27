# Finalisation Plan — Dashy Dora

**Status:** 🟡 Stage 1 in progress (overnight run started 2026-10-22; see §8)
**Owner:** the last stretch of the project, before Phase 4 launch readiness closes out.
**Companion register:** [FINALISATION_COVERAGE.md](FINALISATION_COVERAGE.md) — the
per-chunk × per-track status matrix. Update it every session; it's what makes
"nothing was skipped" auditable.

---

## 1. Why this exists

Several late-game jobs share the same shape: **walk the entire codebase feature-
by-feature, and from that walk produce a small set of end deliverables.** Doing
each one as its own separate cross-cutting pass duplicates the walk and lets
things fall through the cracks between passes. This plan bundles them into one
disciplined sweep so each chunk of the code is read once, deeply, and every
track is advanced from the same reading.

> **Governing objective (added 2026-07-13, owner directive).** The app must be
> **maintainable by one person — the owner — by hand, if AI ever becomes
> inaccessible**: neat, non-redundant, logically organised, industry-standard,
> legible and changeable by a single competent developer with no generation
> assistance.
>
> **Delivered as a strict two-stage effort — analysis fully precedes execution:**
>
> - **Stage 1 — Analysis (this plan's code-walk).** Put *all* effort into reading
>   the code in detail, **file by file**, and writing every finding down. The
>   senior-review track (§3.3) is the record, and it must be **execution-ready**:
>   each finding names the exact file(s) + line(s) and the exact change to make,
>   so Stage 2 needs **zero further investigation**. **No code is changed in
>   Stage 1** — the deliverables are the written track docs.
> - **Stage 2 — Execution (§3.5).** Working *purely from the written findings*,
>   make the exact, efficient changes — DRY, dead-code removal, componentisation,
>   relocation, renaming, standards fixes, and the verified bug fixes — guarded by
>   the test suite. No re-reading the code to decide *what* to do; the Stage-1
>   record already says. Pure, mechanical, precise application.
>
> The whole point of the split: analyse everything exactly first, so the change
> phase is unambiguous and efficient — no investigate-while-you-edit, no
> half-measures, no second-guessing mid-change. (Verified bugs still get an urgent
> FU at discovery — don't wait for Stage 2. Findings needing *design* become a new
> proposal, not a tidy — see §2.)

The four analysis tracks built up in parallel per chunk during Stage 1 (all four
produce a written deliverable; **none changes code** — that's Stage 2):

1. **Full Systems Test (FST) procedure** — a manual walkthrough document the
   user follows to verify the whole app end-to-end from multiple perspectives,
   living at [../04_proposals/FULL_SYSTEMS_TEST.md](../04_proposals/FULL_SYSTEMS_TEST.md)
   (to be created on first chunk).
2. **In-app help & guides content** — plain-English behaviour docs for every
   feature, landing on `HelpPage.vue` + the `(?)` help chips + DoraBot answers.
   Resolves [[FU-361]] + [[FU-320]].
3. **Senior code review findings — the execution-ready change record.** A running
   assessment doc capturing bugs, **redundancy/DRY, dead code, componentisation
   opportunities, misplaced modules, naming/idiom, inefficiency**, refactors worth
   the churn, standards drift, and library-vs-hand-rolled verdicts. Every entry
   records the **exact file:line + the exact change to make** so Stage 2 applies
   it without re-reading the code. Resolves [[FU-395]] and **fully absorbs
   [[FU-510]]** (hand-rolled-vs-library — both phases; the FU was retired into
   this plan, see §3.3 + §6). Lives at
   [../05_investigations/FINALISATION_REVIEW.md](../05_investigations/FINALISATION_REVIEW.md)
   (created on first chunk). This track is the heart of the north-star.
4. **Test plan** — for every chunk, list the unit / integration / e2e tests
   that *should* exist to protect the surface long-term. **Do not write the
   tests** in this pass; capture enough that they can be written cold later.
   Feeds [[FU-519]] / [[FU-520]].

Each chunk also cross-checks the tracks against the shipped `(?)` help
chips (FU-503/044), the state-ownership audit
(`STATE_OWNERSHIP_REFACTOR_PROPOSAL.md`), and the engineering standards
(`ENGINEERING_STANDARDS.md`).

---

## 2. Scope discipline (what this plan is not)

- **Not** a code-change pass *(Stage 1)*. The code-walk **analyses and writes
  findings; it does not edit code**. All editing happens in **Stage 2 (§3.5)**,
  which applies the exact changes from the written record. The separation is the
  point — analyse everything precisely first, then change it mechanically.
- **Not** a fresh design pass. Anything that would rewrite a feature, change a
  contract / DTO shape, or touch a data model is **not a tidy-up** — it belongs
  in a new proposal doc + `FU-NNN`, sequenced separately by risk, and is out of
  Stage 2's scope. If a senior-review finding is large enough to need design, log
  it and keep walking. Stage 2 executes the maintainability class
  (DRY / dead-code / componentisation / placement / naming / standards) + verified
  bugs — not redesigns. The test suite (`FU-371`, done) is the guard: a change
  that can't be test-covered cheaply is large-blast-radius → new proposal/FU.
- **Not** the browser-verify pile. `DORA_VERIFY.md` stays the user's manual
  walk list; the FST doc is different — it's the *reproducible protocol* the
  user (or a fresh collaborator) follows on a near-final build to certify
  release-readiness. FST rows will *become* verify items when picked up.
- **Not** a documentation project for internal architecture. The Help track
  is user-facing copy only. Architecture stays in the charter + proposal docs.

---

## 3. The four output tracks — formatting rules

### 3.1 FST document (`04_proposals/FULL_SYSTEMS_TEST.md`)

The document is a **persona × surface × condition** matrix, rendered as
walkthrough scripts the user can follow with the app open.

**Personas** (all covered before we ship):

| Persona | Represents |
|---|---|
| **Fresh install / first-time user** | Empty DB, onboarding not run, no data, no prefs. Cold discovery. |
| **Dense / long-tenure user** | ~1 year of data — many stock items, several open lists, hundreds of recipes, full price history. Perf + information density under load. |
| **Minimal user** | Runs the loop but ignores optional features (no LLM, no scanning, no email/push, no substitutes recorded). Tests hide-when-off (R-029) is real. |
| **Power user** | Everything on — LLM configured, notifications wired, all opt-ins enabled, using shortcuts (`g s`, `?`, etc.). Tests advanced surfaces don't collide. |
| **Admin** | The only user in a household who edits install-wide settings (Currency/locale, Stocktake, Reconcile, Notifications, LLM master, Image compression, Import templates, Backup library, Kitchen setup, QR labels). |
| **Multi-user household** | Two accounts on the same install with separate `AppSetting` where the setting is per-user; shared where install-wide. Tests per-user vs install-wide boundaries. |
| **Self-host operator** | Docker/desktop-bundle deployment; walks the `2` remaining env vars, backup/restore, migration up/down. |
| **Managed / Path-B** | Runs the same artifact behind a managed URL; auth flows, redirects, PWA install path. |

**Devices / conditions** (applied as row-modifiers, not their own personas):

- Android PWA (Chrome, installed from banner) + native Capacitor build (P8-10).
- Desktop installer (Linux `.deb`, Windows `.msi`, macOS `.dmg`, per `packaging/`).
- iOS PWA (Safari, Add to Home Screen) — voice-unlock gotcha (FU-287).
- Bad network — throttled to slow-3G / offline (read-only offline per R-052:
  cached reads via the service worker, writes refused with the banner; no
  queue, no sync-when-back).
- Small viewport (360×640) vs desktop wide (1920+).
- All five themes × light/dark toggle (feeds FU-010 ride-along).
- Reduced-motion + high-contrast OS preference on.

**Surface sections** — one per feature chunk (§4). Each section:

1. **Preconditions** — what state the persona/device must be in.
2. **Golden path** — steps + expected result, with the persona named.
3. **Edge cases** — one bullet per known edge (permission denial, empty state,
   validation failures, race conditions, offline mid-write, session expiry).
4. **Persona coverage matrix** — a tick-table showing which of the 8 personas
   this section applies to (some surfaces are admin-only; some don't render
   for minimal users).
5. **Condition matrix** — which device/condition modifiers are load-bearing
   for this surface.

The document ends with a **release-gate checklist**: the small set of "before
tagging a release, tick these" rows — the outputs of the FST used as a launch
tollgate. This is what fulfils [[FU-395]] and the FST portion of [[FU-406]].

### 3.2 Help content (`HelpPage.vue` / `(?)` chips / DoraBot corpus)

Content per feature chunk follows the same shape everywhere:

1. **What it does** — one plain sentence.
2. **When it fires / how to trigger it** — user action or auto-trigger.
3. **What controls it** — link to the exact setting toggle (relative
   `/settings/...` URL). **Never** "the app does this" with no escape hatch —
   FU-320 rule.
4. **What it costs / what it might get wrong** — honesty about limits (P3
   Honest tie-break).
5. **Related** — cross-links to adjacent help rows.

For every auto-behaviour catalogued in
`docs/05_investigations/MAGIC_BEHAVIOUR_AUDIT.md`, the chunk that owns the
surface writes the corresponding help entry. The completed set is the
receipt that closes [[FU-320]].

FAQ / navigation / screenshots (the other 4 bullets in `COVERAGE_GAPS.md`
A-4) land as their own sub-passes after the per-feature content is written.

### 3.3 Senior review (`05_investigations/FINALISATION_REVIEW.md`)

Per chunk, one section with these buckets:

- **Bugs** (verified reproducible or high-confidence latent). Each gets a
  new `FU-NNN` opened immediately with an "urgent" recommended resolution.
- **Refactors worth doing** — non-load-bearing improvements. Log to
  `DORA_FOLLOWUPS.md` with a state note "sequence after finalisation review
  closes". Do not action inline.
- **Dead code / unused fields** — kept as a running list; action as one
  batch at plan close (cheaper than per-chunk tidy).
- **Hand-rolled-vs-library verdicts** (ex-[[FU-510]] — the FU was retired
  2026-07-15 and its full scope now lives here; this plan is the sole owner, and
  §7 DoD step 5 is the hard gate that discharges Phase 2). For each hand-rolled
  site a chunk walks
  past, record: what it is · what library would replace it · verdict
  `keep` / `replace` / `wrap-thin-adapter` · effort/risk. Charter tie-breaks
  (Effortless + Anti-creep) are **load-bearing — don't default to "prefer
  library"**: sometimes the hand-rolled thing is right because it's smaller, has
  no supply-chain risk, and stays coupled to our domain. Two phases: **Phase 1
  (assessment)** is this per-chunk record; **Phase 2 (action)** executes the
  swaps — the small / low-risk / test-covered ones inline at Stage 2, the
  large-blast-radius ones (many call sites, a dependency add, not cheaply
  test-covered) as per-swap follow-on FUs spawned at close (see §6/§7). The
  plan's close-out consolidates the verdicts into
  `docs/05_investigations/HANDROLLED_VS_LIBRARIES.md`.
  Non-exhaustive sites to check as chunks touch them:
  - **Security-adjacent:** custom CSRF double-submit vs Flask-WTF / Flask-SeaSurf;
    hand-rolled Fernet key handling vs `cryptography` recipes; the hand-rolled
    security headers (FU-459) vs Flask-Talisman; session/cookie hardening;
    password-hashing choices.
  - **HTTP / API surface:** pagination + query-string parsing
    (`queryStringBuilder.ts`, `parse_query_options`) vs Flask-Smorest / API-spec
    libs; response envelope + error translation vs a marshalling lib;
    audit-retention + audit hooks.
  - **Data access:** the generic repository (`SqlAlchemyRepository`),
    `EntityField`, `include` / `then_include` chains vs plain SQLAlchemy 2.0
    selectinload/joinedload — is the wrapper carrying its weight or fighting the ORM?
  - **Domain infra:** unit conversion (`units.py`), locale display denominators,
    currency + locale formatting, timezone / calendar-day helpers
    (`household_today`), fuzzy-matching wrappers around RapidFuzz.
  - **Frontend:** drag-drop composables (`useDragDropList`) vs vue-draggable /
    dnd-kit; toast/notify wrappers; the shortcut registry (`useShortcut`); the
    read-only offline cache (`useNetworkStatus` + the `dora-api` NetworkFirst rule — the write queue was removed 2026-08-23, R-052) vs Workbox background sync; the rollback
    registry vs a proper undo/redo stack lib.
  - **Ops:** log rotation (time-based already), scheduling (APScheduler in place),
    rate limiting (flag if hand-rolled), config layering (`ConfigurationManager`)
    vs pydantic-settings.
- **Standards drift** — every `R-0NN` violation found becomes an inline
  comment (fix), a rule-cited exception (explain), or a follow-up (defer),
  per the standards close-gate rule in `CLAUDE.md`.
- **Ride-along signals for [[FU-010]] / [[FU-224]]** — anything about
  theme / colour / visual polish gets logged against those FUs so the
  eventual look-and-feel pass has a starting shortlist. Do not resolve
  either FU from here (they need eyes-on-app judgement, not a code walk).

### 3.4 Test plan (`04_proposals/TEST_PLAN_INVENTORY.md`)

Per chunk, one table with:

| Test | Layer | Priority | Trigger to write it |
|---|---|---|---|
| e.g. `test__cook_recipe__decrements_pool_via_bump_pool` | e2e | **must-write-before-ship** | The pool R-003 invariant is critical for FU-317. |
| e.g. `test__useCookMode__preserves_step_position_across_reload` | vitest | nice-to-have | Cook mode has no vitest coverage; low blast-radius. |
| e.g. property `cookable ⇒ every ingredient in stock` | hypothesis | nice-to-have | Feeds [[FU-520]]. |

**Priority cap:** the "must-write-before-ship" bucket is expected to be
small — regression tests for the loop spine + anything the senior review
flags as fragile. Everything else is "nice-to-have"; that's the honest
bucket. Do not padre the must-write list.

At close, "must-write-before-ship" rows are opened as their own FUs and
sequenced into [[FU-519]]; "nice-to-have" rows accumulate against
[[FU-520]] as a menu.

### 3.5 Stage 2 — Execution (apply the findings; only after Stage-1 analysis is complete)

Stage 2 is a **separate pass that changes code**, run *after* the Stage-1 analysis
for its scope is fully written. It is deliberately **not** interleaved with
reading: by the time Stage 2 starts, the senior-review record (§3.3) already says
*exactly* what to change and where, so Stage 2 does **no fresh investigation** — it
reads the finding, makes the prescribed change, and moves on. This is what makes
the change phase fast, unambiguous, and half-measure-free.

**What Stage 2 executes** (the maintainability class + verified bugs — the exact
categories the review must have already pinned per finding):

- **Redundancy / DRY (R-001, R-003)** — collapse duplicated logic/values to one
  source (client recomputing a server-owned fact, a constant duplicated across
  files, two functions doing the same thing → one).
- **Dead code** — remove the unused functions, fields, imports, branches, styles,
  routes, commented-out blocks the review catalogued.
- **Componentisation (R-001)** — extract the repeated markup/logic the review
  flagged into one component/composable; single-responsibility, legible tree; no
  inline copy of a shared thing. Backend: shared helpers over copy-paste.
- **Logical placement** — move each misplaced module to its prescribed home; fix
  layering (server owns derived facts, client owns view — R-003).
- **Naming & idiom** — apply the prescribed renames; one canonical idiom per
  pattern across the surface.
- **Efficiency** — the cheap wins the review noted (redundant passes, needless
  recompute; N+1s already have the FU-534 guards).
- **Verified bugs** — the fixes for bugs the review confirmed (each already has
  its urgent FU from discovery).

**Discipline (non-negotiable):**
- **No re-analysis.** If Stage 2 finds it *needs* to re-investigate to know what to
  do, that finding was under-specified — kick it back to Stage 1, sharpen the
  written record, then execute. The record is the contract.
- **Test-guarded.** Every change compiles + passes the relevant tests before it's
  done. A change not cheaply test-coverable is large-blast-radius → it should have
  been logged as a proposal/FU in Stage 1, not sitting in the execution list (§2).
- **Scoping** — sequence Stage 2 by risk/blast-radius, smallest-safest first. It
  can run per-chunk (execute chunk N's findings once its analysis is signed off)
  or batched across several analysed chunks — owner's call at the time; either way
  analysis for a given scope is 100% done before its execution starts.
- **Recorded** — each executed finding ticks in the coverage register's **Applied**
  column + a worklog note.

---

## 4. Feature chunks (walk order)

Ordering is **loop spine → adjacent surfaces → infrastructure**. This gets
FST persona scripts hanging off the surfaces the personas actually spend
time on first.

| # | Chunk | Rough scope |
|---|---|---|
| 1 | **Cookbook** | Recipes CRUD, import (paste + share target), Recipe Detail, tags, favourites, cookability, meals-worth, cost estimate. |
| 2 | **Meal Plans** | Board / Calendar / Templates, Shortfall, Reconcile (FU-317), Suggestions signposts. |
| 3 | **Shopping Lists** | DRAFT→SHOPPING→DONE, auto-add hooks (FU-315), remembered-list, cheapest chip (FU-318 pending), substitute swap (FU-407), templates, copy, batch actions. |
| 4 | **Cook Mode** | Sous Chef, hands-free, wake-lock, personal notes (FU-432), consume-on-finish (FU-449). |
| 5 | **Stock Overview + Stocktake** | 3-band level, buy-verdict badges, filters, `Needs check`, Stocktake runner + Push/Mute, waste log. |
| 6 | **Stock-Item Detail** | Overview, prices, offers, expiry, substitutes, images, history, per-item settings. |
| 7 | **Zero-Input Pantry (P8-07)** | Belief chip, quick-checks, per-user opt-out, `/beliefs`. |
| 8 | **Dashboard** | Kitchen zone (Dora Score / Reconcile chip / stocktake pulse / draft-shop), Money zone (Budget / Deals / Price Drops / Log price), quick actions. |
| 9 | **Alerts + Suggestions** | ALERT_ROUTER, digest, push, snooze, alert prefs, suggestions generator + snooze prune (FU-513). |
| 10 | **Products / History / Deals** | Products overlay, Product Search, Product History, offers, price entry, Your Prices. |
| 11 | **Assistant (Dora)** | Basic + AI paths, tool registry, mode toggle (FU-360), rate limits, prompt-injection defence (FU-515), eval suite (FU-390). |
| 12 | **Reports / Memory (P8-09)** | `/reports` sections, meals cooked, spend-by-category, YoY, ranges (2y/5y). |
| 13 | **Settings shell** | Account, Kitchen setup, Admin (Currency/locale, Stocktake, Meal reconciliation, Assistant, Notifications, Email, Import, Backup & restore, System features, Theme). |
| 14 | **Onboarding** | Fresh-install flow, per-name picks, paste-rows, seed-items (FU-514 fix). |
| 15 | **Auth shell** | Login / register / reset / setup-admin / change-email / password policy (FU-442), CSRF (FU-197), rate limits. |
| 16 | **Ingestion API + companion seam** | `/api/ingest` bearer lane, admin keys page, standalone companion round-trip. |
| 17 | **Offline / PWA / native** | Service worker (FU-336 — first!), install banner, read-only offline cache (R-052), wake-lock, Capacitor Android/iOS shells, backend-URL runtime picker. |
| 18 | **Backup & restore + Import** | Library, restore-preview, credential exclusion (FU-387), CSV templates (FU-343/348), the two data pages' shared design language (FU-359). |
| 19 | **Ops / self-host** | The `2` env vars, migrations up/down (SQLite + Postgres), desktop first-run, log rotation, APScheduler jobs, security-audit.sh. |
| 20 | **Cross-cutting concerns** | i18n/locale/currency (FU-043), text-scale + component-internal text (FU-025), theme system (feeds FU-010), color-usage patterns (feeds FU-224), keyboard shortcuts + cheatsheet, PWA shortcuts. |

Chunk numbering is stable — the coverage register uses it. New chunks
added later (e.g. Phase 4 tenancy) become 21+, they don't renumber.

---

## 5. How to run a chunk — Stage 1 Analysis (per-session recipe)

**This recipe is Stage-1 analysis only — it produces written findings, it does
not change code.** Execution is Stage 2 (§3.5), run later from the record.

1. **Open [FINALISATION_COVERAGE.md](FINALISATION_COVERAGE.md).** Pick the
   top unstarted chunk. Confirm with the user before starting.
2. **Assemble the reading list** (anti-drift rule from `CLAUDE.md`):
   - The relevant proposal/impl-plan under `04_proposals/`.
   - The relevant `01_charter/` anchors (Champion Plan, Reconciled §5,
     Engineering Standards).
   - The relevant `02_feedback/` bullets for the surface.
   - Any open FU on that surface.
3. **Read the code in detail, file by file**, for the chunk. Backend features
   first, then SPA components/pages, then tests. Grep every entry point. This is
   where *all* the effort goes — the depth here is what lets Stage 2 be mechanical.
4. **Advance the four analysis tracks in the same read** — don't split them;
   follow §3. The senior-review track (Track 3) must come out **execution-ready**:
   every maintainability finding (redundancy, dead code, componentisation,
   placement, naming, inefficiency, standards) records the **exact file:line + the
   exact change** so Stage 2 needs no re-investigation. **Write, don't fix** — the
   only inline action allowed in Stage 1 is opening an urgent FU for a verified
   bug.
5. **Update the coverage register** — set the chunk's **FST / Help / Review /
   Tests** cells to ✅ (Applied stays ⬜ until Stage 2) and the date; one-line
   "what came out of it" note linking the sections added.
6. **Standards close-gate** (per `CLAUDE.md`) — every `R-0NN` violation is
   *recorded* in the review track with its prescribed fix (fixing happens in
   Stage 2; a genuinely trivial in-file exception may still be commented inline).
7. **Worklog entry** on session end.

Expect **one chunk per session** at most for the loop spine chunks
(1-9) and Assistant/Settings (11/13). The smaller chunks (5→6 sub-splits,
7, 14, 16, 18) may pair up. Do not batch more than two chunks in a session
— the review track loses depth.

**Stage 2 execution** is run as its own work unit(s) per §3.5 — once a chunk's (or
a batch of chunks') analysis is signed off, apply its findings from the record,
tick the **Applied** column, and worklog it. Do not start a chunk's execution
before its analysis cell is ✅.

---

## 6. Followups rolled into this plan

Marked here as **fully rolled in**, **partially rolled in**, or
**ride-along**.

**Fully rolled in — closed 2026-07-10, plan is the sole tracker:**

- **FU-361 A-4 Help content overhaul** → Track 2 (Help & guides).
  Moved to `DORA_FOLLOWUPS_RESOLVED.md` 2026-07-10.
- **FU-320 Document every auto-behaviour + link its setting** →
  Track 2 formatting rule §3.2. Moved to `DORA_FOLLOWUPS_RESOLVED.md`
  2026-07-10.
- **FU-395 P5-11 Production readiness review** → Track 3 (Senior
  review) + the FST release-gate checklist. Moved to
  `DORA_FOLLOWUPS_RESOLVED.md` 2026-07-10.

**Fully absorbed — FU retired, this plan is the sole owner:**

- **[[FU-510]] hand-rolled vs library sweep** — the whole sweep now lives in
  this plan (§3.3 "Hand-rolled-vs-library verdicts" holds the two-phase method,
  the Charter "don't default to library" caveat, and the full focus-area
  checklist). Phase 1 (assessment) runs per-chunk in Track 3; **Stage 2 executes
  the small / low-risk / test-covered swaps** from the record; the
  large-blast-radius ones (many call sites, a dependency add, anything not
  cheaply test-covered) become **per-swap follow-on FUs spawned at plan close**
  (see the follow-on list below + §7 DoD step 5 — a hard close-gate). The FU-510
  ledger entry was retired 2026-07-15; there is **no standing tracker** — this
  plan carries it, and the DoD guarantees the Phase-2 FUs get opened.

**Partially rolled in — cross-referenced, corresponding FU stays open:**

- **[[FU-406]] P7-10 Launch readiness** — the FST doc + release-gate
  checklist cover the *QA half*. Marketing / legal / on-call / incident
  channels do not fit code-traversal; those stay in FU-406.
- **[[FU-404]] P7-08 Compliance** — the FST persona flows will *exercise*
  the privacy policy, DSAR export, and delete surfaces (multi-user + admin
  personas). Legal drafting + the compliance contract itself do not fit
  here.

**Ride-along — not resolved, but every chunk feeds them:**

- **[[FU-010]] Late-game holistic theme / colour review** — Track 3
  captures every theme/color anomaly against this FU. Actual resolution
  needs eyes-on-the-running-app at close.
- **[[FU-224]] App-wide colour-usage assessment** — same treatment;
  Track 3 collects every `color="secondary" | info | accent` site
  worth reconsidering as we walk.

Follow-on FUs opened by this plan (opened at plan close, not before):

- Every "must-write-before-ship" test row → new FU each, sequenced into
  [[FU-519]].
- Every large-blast-radius "replace" verdict from Track 3 → new per-swap FU
  (this plan's Phase-2 output, ex-[[FU-510]]; sequence by risk + blast radius).
  **This is a hard close-gate — see §7 DoD step 5.**
- Every bug found → new urgent FU at discovery (don't wait for close).

---

## 7. Definition of done for the plan

This plan closes when:

1. **Stage 1 complete:** every chunk in §4 shows ✅ in
   [FINALISATION_COVERAGE.md](FINALISATION_COVERAGE.md) across the four analysis
   tracks (FST / Help / Review / Tests) — some cells may be `N/A` (e.g. ops chunks
   with no in-app help), but every cell has an explicit value, and the Review
   record is execution-ready (exact file:line + change per finding).
1a. **Stage 2 complete:** the **Applied** column is ✅ for every chunk — every
   maintainability finding from the Review record has been executed (or explicitly
   waived in the doc with reasoning, or promoted to a proposal/FU as too-large).
2. The FST document has been walked once end-to-end by the user on a
   near-final build, and the release-gate checklist is green.
3. The Help content is deployed and the `(?)` chips + HelpPage + DoraBot
   corpus reflect it.
4. The senior review has been triaged: every `replace` / refactor /
   dead-code item is either executed (Stage 2), opened as an FU with a resolution
   point, or explicitly waived with reasoning in the doc.
4a. **Maintainability north-star met.** With Stage 2 done across every chunk: no
   dead code, no redundant duplication, shared UI componentised, modules in their
   logical homes, and `ENGINEERING_STANDARDS.md` satisfied on the *existing*
   codebase — not just new work. The acceptance test: a single competent developer
   can open the repo cold, find any feature's code where they'd expect it, read it
   without generation assistance, change it in one place, and trust green tests to
   catch regressions.
5. **Hand-rolled-vs-library Phase 2 discharged (ex-FU-510 — hard gate).**
   The Track-3 verdicts are consolidated into
   `docs/05_investigations/HANDROLLED_VS_LIBRARIES.md`, and **every
   large-blast-radius `replace` verdict not executed at Stage 2 has been opened
   as its own per-swap FU** (sequenced by risk + blast radius; pair the
   sequencing with [[FU-412]] COMMERCIALIZATION_REPORT + [[FU-409]] auth security
   re-audit + [[FU-424]] senior-review Tier-2 delta). FU-510 was retired into the
   plan on 2026-07-15 and has **no standing ledger entry** — so this step is the
   *only* thing that guarantees the Phase-2 work isn't dropped. The plan does not
   close until this list is either executed or spawned as FUs; a `replace` verdict
   left with no home blocks close.
5a. FU-361 / FU-320 / FU-395 are already in `DORA_FOLLOWUPS_RESOLVED.md`
   (closed 2026-07-10 when this plan was drafted; the plan is their sole tracker).
   FU-406 + FU-404 get state notes ("finalisation plan covered the FST/exercise
   portion; remaining scope: X").
6. The plan doc itself gets a "Closed" banner + a link from
   `PROJECT_STATE.md` moves from the workstreams table to the
   "recently shipped" section.

---

## 8. Execution notes — 2026-10-22 overnight run

Owner directive (2026-10-22): *"work through the finalisation plan overnight;
do as much as you can on your own."* Context given with it: the owner has
walked every page at least once as product owner and is **≥90 % happy with the
app as it is**. Consequences for how the plan is run:

- **Per-chunk analysis files.** Stage 1 runs as parallel analysts, one per
  chunk, each writing `docs/05_investigations/finalisation/CHUNK_NN_<slug>.md`
  to the contract in `_CHUNK_TEMPLATE.md` there. The four master documents
  named in §3 (`FULL_SYSTEMS_TEST.md`, `FINALISATION_REVIEW.md`,
  `TEST_PLAN_INVENTORY.md`, plus `HELP_CONTENT.md` for Track 2) are
  **assembled from the chunk files** — the chunk files are the source; the
  masters are regenerated, not hand-edited. The §5 "one chunk per session"
  pacing was written for a single sequential session and does not apply to a
  parallel run; the depth guard is the template's evidence rules instead.
- **Track 4 amended to the 2026-07-20 testing stance.** Tests are listed only
  where they pin a stable, low-churn contract that is expensive to re-check by
  hand; backend pytest + Vitest only; **no Playwright feature-flow specs**
  (the e2e layer stays a 3-spec smoke layer). The §3.4 e2e example row is
  therefore historical.
- **No redesigns.** With the owner ≥90 % happy, §C of each chunk executes the
  maintainability class + verified bugs only; design-level observations are
  recorded (§C8) and stop there.
- **Stage 2 sequencing.** Per §3.5's "owner's call": execution runs per chunk
  once that chunk's analysis is written, smallest-blast-radius first,
  test-guarded against the baseline recorded at run start (pytest 2429 passed /
  2 order-dependent flakes that pass in isolation; vitest 747/66; `vue-tsc`
  and `eslint` clean). Findings marked **FU** or **waive** are not executed.
- **FU ids are allocated by the orchestrator**, not by analysts, so parallel
  chunks cannot collide on numbering.
