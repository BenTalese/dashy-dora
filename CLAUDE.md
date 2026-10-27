# Claude session instructions — Dashy Dora

The repo is being finished against the planning library at `docs/` inside this
repo. Multiple Claude sessions may be working on this concurrently from
different computers — because `docs/` is versioned with the code, every
machine has the same copy automatically.

To keep handoffs clean:

## On session start — ALWAYS

0. **Open `PROJECT_STATE.md` (repo root) first.** It is the single
   human-readable front door — where every phase and workstream is up to, what
   needs the user's attention, what shipped recently. Read it to orient before
   diving into the deeper logs below. It is a *living* doc, regenerated at each
   work-unit close-gate (see "Regenerating PROJECT_STATE.md" below); if it looks
   out of date, that's a signal the last session skipped its close-gate — trust
   `DORA_WORKLOG.md` + `CHANGELOG.md` over it and regenerate it. Its bottom half
   is the **document register** — the per-doc verified state of the whole library.
1. **Read the last entry in `DORA_WORKLOG.md`** (at this repo's root). It tells
   you what was just done, what decisions were made, and what's next. If the
   last entry says "Next up: X", that's your starting point unless the user
   redirects.
2. **Planning docs live at `docs/` in this repo, organised by lifecycle.**
   `PROJECT_STATE.md` (front door + document register) is the map of what
   exists and where it stands — start there, not a separate index. Folders:
   - **Anti-drift rule (before running any `03_prompts/` prompt):** assemble its
     required reading yourself — the governing proposal/impl-plan in
     `04_proposals/`, the relevant charter anchors + engineering rules
     (`01_charter/`), the feedback bullets it targets (`02_feedback/`), and any
     open follow-ups on that surface. Skipping this is how prompts ship in
     isolation and silently violate the charter. (`docs/00_DOC_GRAPH.md` is a
     legacy stub of this map, known stale — don't rely on it.)
   - `docs/01_charter/` — vision + governance
     (`DASHY_DORA_CHAMPION_PLAN.md`, `RECONCILED_FINISHING_PLAN.md`,
     `ENGINEERING_STANDARDS.md` — the code/architecture rules
     `R-001..` + ADR log; checked on **every** task, see section below —
     and `DESIGN_STYLE_GUIDE.md` — the prescriptive look-&-feel spec
     (Part A token/role tables + Part B component specs + rules `D-001..D-025`),
     checked on every **UI-affecting** task via R-035; its remediation
     backlog is `docs/04_proposals/DESIGN_REMEDIATION_PLAN.md`).
     The old `STATUS.md` audit was retired to `06_legacy_prompt_plans/`
     on 2026-06-12; for "what's built right now?" use the **top entry
     of `DORA_WORKLOG.md`** + `CHANGELOG.md` instead.
   - `docs/02_feedback/` — user input (source of truth):
     `Feedback _ Fixes - as of [DATE].md`, `FEEDBACK_TRIAGE_AND_PLAN.md`,
     `COVERAGE_GAPS.md`.
   - `docs/03_prompts/` — executable prompts (`00_INDEX.md` +
     `A*.md` / `B*.md` / `C_*.md` / `INV_*.md`).
   - `docs/04_proposals/` — outputs of Wave-C design briefs (no-code
     design docs).
   - `docs/05_investigations/` — outputs of INV prompts + ad-hoc audits.
   - `docs/06_legacy_prompt_plans/` — original `PROMPT_PLAN_PART_*`
     (historical reference; the active set lives in `03_prompts/`).
   - `docs/00_original_spec/` — the author's **very first spec** (Feature
     Boards + ~125 "I can …" Feature Notes + original PROMPT_PLAN), written
     *before* this branch's ~100k LOC. **Historical, NOT authoritative** — it
     pre-dates the charter/feedback, so where it disagrees, those win; it never
     auto-overrides. Mine it for dropped intent, half-built features, or a
     cleaner original framing — see the cross-check rule below.
   - `docs/99_scratch/` — raw notes awaiting triage.

   Read from there directly — don't search the filesystem and don't
   reconstruct from memory. If a path a prompt references is genuinely
   missing under `docs/`, ask the user.
3. **Verify state before acting.** The planning docs (esp. `STATUS.md`) are
   known stale; the code is the source of truth. Read the actual code paths
   the prompt references before assuming they exist.
4. **Read `CHANGELOG.md`** for the most recent product-level changes — context
   for what the code looks like now vs. what older docs describe.
5. **Scan `DORA_FOLLOWUPS.md`.** This file holds **only open items** — the
   stateful backlog of deferred jobs, leftovers, and findings from past prompts
   that the user may have missed in a long session summary. Surface the items
   whose *recommended resolution point* is "now" or matches the work you're
   about to start, then **ask the user whether they want to review/resolve
   those now or defer them** before you dive into the main task. Don't silently
   work around an open item that's relevant to what you're doing. Resolved
   items live in a separate archive (`DORA_FOLLOWUPS_RESOLVED.md`) — only
   consult that if you need history on a specific FU id.
6. **Do NOT pre-scan `DORA_VERIFY.md`** at session start. It is the user's
   personal **QA pile** — a catch-all checklist for every kind of manual
   verification he wants to walk on his own time (browser observations, but
   also boot-time log checks, operator sanity checks, container-runtime
   spot-checks, anything that needs eyes-on-the-running-thing to confirm).
   Only read it if (a) the user explicitly references a verify item, or (b)
   the current task touches the same surface and you want to fold a new
   verify step into an existing section. Never list verify items as "open
   work" in your start-of-session summary; that's not the file's purpose.

## On ending a work unit — ALWAYS

Append a new entry to `DORA_WORKLOG.md` using the template at the top of that
file. Do this even if the unit was partial or blocked — the next session needs
to know where you stopped and why.

**Refresh `PROJECT_STATE.md`** (the human-readable front door). For a substantive
unit, spawn the regeneration agent (see "Regenerating PROJECT_STATE.md" below) so
the dashboard is rebuilt from ground truth; for a trivial unit, hand-edit just the
affected row(s) + the "Recently shipped" and "Regenerated:" lines. This is what
stops it going stale — do not skip it. If your unit changed nothing about where any
workstream stands (e.g. a pure doc tidy), no refresh is needed.

**Also update the follow-ups ledger** with anything the current job spun off.
**There are two separate ledgers — pick the right one for each item:**

- **`DORA_VERIFY.md`** — the **user's QA pile**. Any check whose outstanding
  work is "look at the running thing and confirm it behaves" goes here — not
  just browser observations. Also fair game: boot-time log lines, container
  startup behaviour, CLI/desktop-app launch smoke checks, migration
  round-trips inspected by hand, cron/scheduled-task fires, any operator-
  facing sanity check the user wants eyes on. Append a tight checklist under
  the relevant surface heading (Cookbook / Cook mode / Meal plans / Shopping
  lists / Stock / Dashboard / Alerts / Settings / Onboarding / Build /
  Operator / Cross-cutting — add a heading if none fits). One verb-first
  checkbox per check; end the heading with `— origin FU-NNN` (or omit if not
  spun from an FU). Prefix the heading with `⚠️` only if the verify blocks
  other work. **Do not open a new FU-NNN for a pure verify item** — those
  clutter the followups ledger and the user manages this file by deleting
  items as he walks through them. No archive needed; no two-way links.
- **`DORA_FOLLOWUPS.md`** — everything else: deferred jobs, leftovers, design
  questions, findings, real bugs that need a fix, decisions that need a
  call. `[OPEN]` items only, newest at the top, each with a **recommended
  resolution point** ("now", "later during Phase X / prompt Y",
  "when <trigger>", or "opportunistic").
- **`DORA_FOLLOWUPS_RESOLVED.md`** — archive of `[RESOLVED]` items. When you
  resolve an open follow-up this session, **move the entry** from
  `DORA_FOLLOWUPS.md` to the top of this file, flip `[OPEN]` → `[RESOLVED]`,
  and append a one-line state note (date + brief mechanism). Don't leave
  resolved items in the open file; don't delete them — the trail matters.

**Picking the right ledger — quick rule:**
- "Verify the friendly error toast renders with a ref-id suffix." →
  **DORA_VERIFY** (browser observation).
- "Boot the app with `DORA_ENV=production` and confirm the stderr banner
  fires." → **DORA_VERIFY** (operator smoke check — same shape, just not a
  browser).
- "Friendly error rollout missed the inline-product Axis-B picker." →
  **DORA_FOLLOWUPS** (real bug, needs a fix).
- "Reported defect that didn't reproduce in static read; confirm in
  browser it's actually fixed." → **DORA_FOLLOWUPS** as `type=finding`
  (see the mandatory reported-defect rule below). The verify *itself* can
  also be added to DORA_VERIFY for clean tracking, but the FU stays as
  the stateful record until the bug is confirmed gone.

If the unit produced no new loops and no new verify checks, no edit is needed.

## Regenerating PROJECT_STATE.md

`PROJECT_STATE.md` (repo root) is the single human-readable front door + the
document register. It's a *living* doc — **regenerated in place, never re-dated or
re-created under a new filename** (the retired `99_scratch/PROGRESS_REPORT_*` /
`FEEDBACK_AUDIT_*` went stale precisely because the date was in the filename and
nothing refreshed them — don't repeat that). Keep the top half skimmable (~2-min
read); summarise and let detail live in the logs.

**Two halves, different refresh cadences:**

- **Dashboard (top)** — refresh at every substantive close-gate. Spawn a
  `general-purpose` agent with this brief: *"Compile the current state of Dashy
  Dora. Read, newer-wins: `DORA_WORKLOG.md` top ~10 entries; `CHANGELOG.md`
  `[Unreleased]`; `docs/04_proposals/PRODUCTS_OVERLAY_RUNBOOK.md` live-status;
  `DORA_FOLLOWUPS.md` (count open; extract only the ~15 that need a decision or a
  running-app check now); `RECONCILED_FINISHING_PLAN.md` §5 for the phase frame.
  Return tight markdown for: Where-we-are (3-5 sentences) · Phase board · Major
  workstreams · ⚠️ Needs-attention (top ~15). Synthesise, don't dump."* Drop the
  output into the dashboard sections, preserving order. **Do NOT add a
  "Recently-shipped" / changelog-diary section** (owner directive 2026-08-12 —
  removed as diary clutter; this doc shows milestone *progress*, not a ship log —
  shipped history lives in `CHANGELOG.md` + `DORA_WORKLOG.md`). Likewise keep the
  top intro to a one-line "Last reviewed" stamp, never a running "Regenerated:"
  narrative that accretes prior-refresh paragraphs.
- **Document register (bottom)** — rebuild only when docs are **added, superseded,
  or materially change state** (not every chunk; a periodic re-verify is enough).
  Fan out ~5 parallel `general-purpose` agents over gap-free slices of
  `Glob docs/**/*.md` (partition by folder; split the large `04_proposals/`;
  exclude the 157 historical `00_original_spec/` files as one bucket). Each reads
  worklog-top + CHANGELOG once, opens every doc in its slice, and returns one row
  per doc: `Doc | Type | State | Purpose | Evidence`. Consolidate, then reconcile
  any dashboard row the per-doc reality contradicts.

**Shared status key:** ✅ done-clean · ➗ done-with-carve-outs · 🟡 active/in-progress
· 🔵 designed-not-built · ⚪ not-started · 🔴 needs-a-decision · 🕸 stale · 📦 superseded
· 🗄 historical.

**MANDATORY — reported defects you conclude are "non-issues" still get a
follow-up.** When a prompt (or the user) reports a bug and your investigation
finds it *doesn't reproduce / already fixed / can't be found in the code*, you
must NOT silently drop it. The report came from real usage; a static code read
is not proof it's fixed (it may fail only at runtime, on a specific path, or you
may have misread). Log it as `[OPEN]` with type `finding`, note that it didn't
reproduce in a static read, and set the recommended resolution to **"confirm in
browser"**. Only flip it to `[RESOLVED]` once it's actually been verified
not-broken in the running app. This applies per-defect — don't bury several
reported items as one vague "all fine" note.

**MANDATORY — engineering-standards close-gate.** Before closing the work unit,
confirm the change was checked against the standing rules in
`docs/01_charter/ENGINEERING_STANDARDS.md`. Every rule violation you introduced or
touched must be either (a) fixed, (b) explained in place with an inline comment that
names the rule (e.g. `// R-002 carve-out: …`), or (c) logged as a `DORA_FOLLOWUPS.md`
finding citing the rule id + location. An unexplained violation **blocks the unit from
closing** — do not hand off with silent drift. Then run the **ADR evaluation**: did
this task make/rely on a recurring decision worth promoting into a new rule? If so,
add an ADR (and a new `R-0NN`) to that doc. See the next section.

The logs, each with one purpose — keep them separate:
- **`CHANGELOG.md`** = product/code changes (user-visible, "the app now does
  X"). Updated per the master plan's rule that every prompt updates it.
- **`DORA_WORKLOG.md`** = process/handoff log (which prompt ran, decisions
  made, what's next, open questions). Internal — for agent-to-agent handoff.
- **`DORA_FOLLOWUPS.md`** = **open** loops only (deferred work, leftovers,
  findings) that outlive a single session, each with a recommended resolution
  point. The session-start scan reads from here.
- **`DORA_FOLLOWUPS_RESOLVED.md`** = archive of resolved items moved out of
  the open ledger. Audit trail only — not part of the session-start scan.
- **`DORA_VERIFY.md`** = the user's browser-verify checklist, grouped by
  surface. The user walks it and deletes items as he confirms them — there
  is no archive. **Not** scanned at session start. New verify checks land
  here, not in `DORA_FOLLOWUPS.md`. **Delete-on-pass (owner delegation
  2026-07-18):** when a session verifies an item itself — walked live in the
  running app and passed (the default), or covered by an existing green test —
  **delete the line from this file in the same session** (rewording
  neighbouring bullets so survivors still stand alone). Record what was
  verified + the evidence in `DORA_VERIFY_TRIAGE.md` and the worklog. Failed or
  partially-covered items stay.
  **⚠️ VERIFICATION STANCE (owner, 2026-07-20) — LEAN, manual-first.** Do NOT
  try to convert checks into automated tests wholesale ("test everything that
  COULD have a test" was reversed as foolish for this app). Verify by **driving
  the running app once** (agent or owner) and deleting the line. Write an
  automated test ONLY when it pins a **stable, low-churn contract** that's
  expensive to re-check by hand (prefer backend/Vitest — fast + reliable).
  **Playwright is a minimal smoke layer only** (`auth.setup`+`login`+`smoke`:
  does the built SPA boot/route/authenticate) — the feature-flow specs were
  deleted 2026-07-20 (slow + flaky; things "subject to change"). Do NOT add
  feature-flow Playwright specs. Full rationale + the disposition rule:
  `DORA_VERIFY_TRIAGE.md` top banner.

## Governing documents (read on demand, not every session)

All paths below are *inside* `docs/` in this repo.

The master is `docs/01_charter/RECONCILED_FINISHING_PLAN.md`. It owns
order and scope. Inside it:

- **§5** — phased plan (Phase 0 foundations → Phase 1 loop → Phase 2 ingestion
  API → Phase 3 champion → Phase 4 commercialize).
- **§7** — resolved decisions. Scraper → standalone companion; recipe
  comparison gets INV-6'd before keep/cut; nutrition off+simple only;
  gamification → someday.

The **Dora Decision Charter** (12 principles, tiebreak: Effortless + Anti-creep)
lives in `docs/01_charter/DASHY_DORA_CHAMPION_PLAN.md` Part II. Every
design call is checked against it.

The executable prompts live in `docs/03_prompts/`. Each one is
self-contained — read its "Impact & decisions" block first, resolve any
choices with the user, then run it. After running, log it.

## Cross-checking against the original feedback — MANDATORY

Every design brief, proposal, assessment, or implementation plan that
targets a specific app surface (Wave-C briefs, INV reports,
implementation plans, design proposals) **MUST end with a flat coverage
table** mapping each feedback bullet for that surface — from
`docs/02_feedback/Feedback _ Fixes - as of [DATE].md` — to a section in
the proposal, OR explicitly mark it out-of-scope with a one-line reason.

A reviewer should be able to audit "is anything missing?" at a glance.
The `F1..F49` table at the end of
`docs/04_proposals/PROPOSAL_MEAL_PLANS.md` is the reference shape.

For cross-cutting work (Wave A) rather than per-surface, the table maps
each feedback bullet that motivated the work — not every bullet across
the app.

A proposal without this table is incomplete. Open
`docs/02_feedback/COVERAGE_GAPS.md` after writing one to flip any
bullets that now have a home from gap → covered.

## Closing out a proposal / brief — MANDATORY

Before marking a Wave-C brief, INV report, implementation plan, or design
proposal as "done", walk its **"Open decisions"** (or equivalent) section and
close it out — every entry must be either **(a)** answered inline with the
decision recorded in the doc, or **(b)** spawned as a `DORA_FOLLOWUPS.md`
entry with a recommended resolution point, and the doc updated to reference
that FU id. No proposal ships with a live "Open decisions" block still
holding undecided items — that's the pattern FU-364 called out (proposals
looked done but had unresolved forks buried in them). Add a short "Open
decisions — closed" (or "spawned as FUs") line at the bottom of that section
so a reviewer can confirm the sweep happened at a glance.

## Consulting the original spec — for briefs/investigations

When a brief, proposal, or investigation targets a specific surface, **also skim
the matching Feature Board / Feature Notes under `docs/00_original_spec/`** for
that surface (it's the author's first spec, pre-~100k-LOC). It is **historical
and non-authoritative** — the charter, reconciled plan, and current feedback
override it, and it never silently changes a decision. Use it only to *extract*
dropped intent, half-built features, or a cleaner original framing. When you do
pull something in, add it to the doc in its own clearly-labelled section, tagged
**keep / consider / superseded**, noting how old the source is. The reference
shape is `PROPOSAL_CART_BUTTON.md §9` ("From the original spec"). If nothing
there is worth extracting, that's fine — no section needed.

## Removed features — do not reintroduce

- Substitute **graph** — the standalone visual graph *page* (the old N7
  `/substitutes` route / `SubstitutesGraph.vue`). That page is deleted; don't
  rebuild it. **NOT removed:** the basic per-stock-item substitutes — the
  substitutes list on a stock item's detail page, surfaced in recipes and as a
  *temporary, cook-session-only* swap in cook mode (B8). Keep those. (The old
  docs conflated the two by writing "Substitute graph (stock-item substitutes)";
  they are different things.)
- Stock map / spatial layout. Locations is a simple tree, never spatial.
- Real-world barcode **deal lookup** (P6-02) — scanning never looks up live
  prices; it is a navigation aid only. **NOT removed:** `ProductBarcode` (a
  real EAN/UPC links to a *Product*, then resolves to a linked stock item) and
  Dora's own per-item QR labels — both kept, but the whole scanning + QR-label
  surface is gated behind the install-wide `scanning_enabled` flag (off by
  default). The old `StockItem.barcode` column was dropped: a real barcode
  identifies a Product, never a stock item directly. The register-against-product
  UI + scan-unknown rework are deferred to Phase 2 (ingestion).
- Central retailer scraping as a hosted service (P7-01). It survives only as
  a self-hosted, off-by-default module / the standalone companion.
- **Command palette** (the Ctrl/Cmd-K modal that opened `CommandPalette.vue`
  driven by `useCommands` + `useRecents`). Retired 2026-06-12 after the
  INV-9 assessment recommended SHRINK and the user escalated to CUT —
  audience for Dora is pantry / mobile, not keyboard-power-user. **NOT
  removed:** the `useShortcut` + `useShortcutRegistry` keyboard layer
  (`?` cheatsheet, `/` focus, `g s`/`g l`/`g r`/`g d`/`g h` nav, page-
  specific `n`/`a` etc.) and `ShortcutsCheatsheet.vue` — all kept. If
  power-user discoverability becomes a real ask later, the cheatsheet is
  the place to surface it, not a hidden Ctrl-K modal.

## Naming

Product is **Dashy Dora** (renamed via P8-01, landed 2026-07-01). The GitHub
repo is `BenTalese/dashy-dora` (`version_info.GITHUB_REPO` is the one place
the slug lives); only the local checkout folder is still `DiscountDora/`. Internal identifiers
(`dashy-dora` package name, `dashy_dora` container, `DashyDora-*` User-Agents,
Docker image ref, PWA appId) are already flipped; don't reintroduce
"Discount Dora" / "DiscountDora" in new code, copy, or comments. When
adding new UI copy, prefer just "Dora" — the app-name form only where it
actually belongs (About / Help / titles).

## Engineering standards & ADRs — MANDATORY, every task

`docs/01_charter/ENGINEERING_STANDARDS.md` is the **code/architecture rubric**
(the engineering counterpart to the Charter's product rubric). It holds the
standing rules `R-001..R-0NN` — componentisation-first, theme-tokens-only,
single-source-of-truth/state-ownership, framework discipline, portable data
access, clean migrations, scope discipline, code-style, safe mutations — each
established from a recurring cleanup so it never has to be done twice.

On **every** task (feature, fix, *or tidy-up*):
1. **Check the work against the standing rules** before and while building. Take
   the proper path, not the shortcut that creates future cleanup. No lazy code; do
   it properly and consistently.
2. **Explain-or-flag any violation** (yours or pre-existing) — never a silent
   third option: fix it, OR comment it in place naming the rule, OR log a
   `DORA_FOLLOWUPS.md` finding citing the rule id. Enforced at the end-of-work
   close-gate above; an unexplained violation blocks the unit.
3. **Evaluate for a new rule/ADR** at end of work — promote recurring decisions
   into a new `R-0NN` + ADR entry in that doc.

The two sections below (state-ownership, distribution posture) are `R-003` / `R-005`
expanded — they remain authoritative for their detail; the standards doc indexes
them. **UI-affecting tasks additionally check
`docs/01_charter/DESIGN_STYLE_GUIDE.md` (D-rules, enforced via R-035)** — colour
semantics, contrast floors, tap targets, formatting authority, dialog/toast
conventions, copy voice. Same explain-or-flag discipline as the R-rules.

## State-ownership principle (check new work against it)

**Server owns derived domain facts and cross-entity aggregates; the client owns
presentation and ephemeral view state. No domain constant or threshold lives in
two languages.** A client computing a cross-entity rule (e.g. "cookable"), summing
across a fetched collection, or hardcoding a domain constant (a stock-level name, a
"7-day" window) is a smell — push it to the server, don't copy it a fourth time.
The full triage + app-wide audit is in
`docs/04_proposals/STATE_OWNERSHIP_REFACTOR_PROPOSAL.md` (§8 addendum); but the
"already clean — do not relocate" list there is equally binding (don't
over-correct fine client display math into the API).

## Distribution & tenancy posture (check new work against it)

The product is built the **GitLab way: one codebase, SaaS-style, self-hostable** —
the *same artifact* runs as a self-hosted single instance, a managed single-tenant
instance (Path B), or a multi-tenant SaaS (Path A, deferred). SaaS and self-host are
**not conflicting architectures**; only deployment/tenancy/managed-conveniences
differ. Don't dig a self-hosted-only hole, and don't pre-build multi-tenancy. Run
the **§7.5 distribution-posture checklist** in
`docs/01_charter/RECONCILED_FINISHING_PLAN.md` (repository-routed data access;
**Postgres is the standard datastore target, SQLite still supported** for lightweight
self-host, so keep the DB layer portable both ways; env/config-driven differences;
auth behind an interface with a local default; no speculative `tenant_id`; managed
conveniences degrade gracefully) on any prompt touching data access, auth, config, or
deployment. Full rationale: that doc's **Decision 5** (§7). Postgres migration is
tracked as `DORA_FOLLOWUPS.md` FU-045.

## Don'ts

- Don't rewrite the framework. Stay on Flask / Quasar / Vue 3.
- Don't add features beyond the prompt's scope, even if adjacent code looks
  rough. Log it as a finding in `DORA_FOLLOWUPS.md` instead (with a state and a
  recommended resolution point).
- Don't silently skip the worklog entry at end of work, even for tiny tasks.
  The whole point is that the *other* agent can pick up cold.
