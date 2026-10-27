# Engineering Standards & ADR Log

**Status:** Living. Seeded 2026-06-06; grows by ADR.
**Scope:** The code/architecture rubric every agent obeys on **every** task —
features, fixes, *and tidy-ups*. This is the engineering counterpart to the
**Dora Decision Charter** (`DASHY_DORA_CHAMPION_PLAN.md` Part II): the Charter
governs *product/UX* decisions; this doc governs *how the code is built* so the
same cleanup never has to be done twice.

> **Why this exists.** Repeated audits (theme-token compliance, `q-btn` →
> `BaseButton`, dialog-chrome unification, server/client state duplication,
> filter-bar standardisation) keep finding the *same* drift re-introduced by
> later work that didn't know the rule. A rule that lives only in a finished
> proposal doc is invisible to the next agent. These rules are loaded into every
> session (via `CLAUDE.md`) so they are seen *before* the code is written, not
> discovered in the next audit.

---

## How to use this doc (MANDATORY — every task)

1. **Before building / tidying:** read the standing rules (§ Rules). State, in
   your plan or worklog, that the approach honours them — or which one it bends
   and why.
2. **While building:** prefer the compliant option. Do not take the shortcut that
   creates future cleanup. *No lazy code. Do it properly, do it consistently.*
3. **When you find an existing violation** (yours or pre-existing), you have
   exactly two honest exits — never a silent third:
   - **Explain it in place** — an inline comment stating *why* the rule is bent
     here (a real constraint, an approved carve-out, a deliberate exception). The
     comment must name the rule (e.g. `// R-002 carve-out: brand logo hex`).
   - **Flag it** — log a `DORA_FOLLOWUPS.md` item (`[OPEN]`, type `finding`) with
     the rule id, the location, and a recommended resolution point.
   A violation that is neither fixed, explained, nor flagged **blocks the work
   unit from closing.** This is enforced in the `CLAUDE.md` end-of-work ritual.
4. **At end of work:** run the **ADR evaluation** (§ ADR process) — did this task
   surface a recurring decision worth promoting into a new rule? If yes, write the
   ADR.

A reviewer (human or agent) should be able to read a diff and see, for every
deviation, either a fix, a self-explaining comment, or a follow-up. Nothing
unexplained.

---

## Rules

Each rule: **Rule** (the imperative) · **Why** · **Apply** (when/how) ·
**Violation signal** (how to grep/spot it) · **Carve-outs** (the legitimate
exceptions, which still must be commented) · **Source** (where it was established).

### R-001 — Componentisation first
- **Rule:** Build UI from the shared base components (`BaseButton`, `BaseDialog`,
  `FilterBar`, the `dora-*` primitives). Do **not** hand-roll a raw `q-btn` /
  `q-dialog` / bespoke filter or multi-select chrome when a base component exists
  or should. If a pattern recurs (≈2–3 uses), extract a component rather than
  copy it a third time.
- **Why:** Hand-rolled chrome is the single biggest source of "make it consistent"
  cleanup (button styling, dialog headers/actions, filter containers all drifted).
- **Apply:** New or touched UI uses the base primitive. When you touch a file
  still on raw `q-btn`/`q-dialog`, migrate the bits you touch (don't rewrite the
  whole file — that's R-007 scope), and leave the rest flagged.
- **Violation signal:** new `q-btn`/`q-dialog` in a diff; a second copy of a
  layout/interaction that a component already owns.
- **Carve-outs:** a genuinely one-off primitive a base component can't express —
  comment it.
- **Source:** `DORA_FOLLOWUPS.md` FU-005/006/008/009/011/012/013.

### R-002 — Theme tokens only; no hardcoded colour
- **Rule:** All colour rides semantic CSS tokens (`var(--text-*)`,
  `var(--surface-*)`, `var(--semantic-*)`) or the `dora-*` helper classes, or
  theme-aware Quasar semantics (`color="primary"`, `text-positive`). **Never**
  hex, `rgb()/rgba()/hsl()`, Quasar *numbered* palette classes (`text-grey-7`,
  `bg-red-1`), or palette `color=`/`text-color=`/`track-color=` props with a
  numbered/named palette value.
- **Why:** Hardcoded colour breaks every dark theme and has regressed *repeatedly*
  after each paint pass (see FU-046).
- **Apply:** For a chip/badge with a neutral state, route the neutral branch
  through `dora-bg-sunken dora-text-secondary` / `dora-text-muted` and keep only
  the saturated semantic branch (`positive`/`negative`/`warning`) on its
  `color=`/`text-color="white"` props (white-on-saturated is theme-stable).
- **Violation signal:**
  `grep -nE "#[0-9a-f]{3,8}|rgba?\(|text-(grey|red|green|amber|blue)-[0-9]|bg-\w+-[0-9]|'grey-[0-9]'"`
  — **plus the JS-config surface**, which the pattern above misses because it
  looks for template classes and numbered swatches:
  `grep -rnE "(color|textColor|iconColor|trackColor):\s*'(red|pink|purple|indigo|blue|light-blue|cyan|teal|green|lime|yellow|amber|orange|brown|grey|blue-grey|white|black)'" web_app/src`
  Plugin registrations and options objects (`Notify.registerType`, `Dialog.create`,
  chart/option builders) take the same palette names as a template prop and are
  the same violation — `themeService` re-points `--q-*` per theme and a literal
  never consults it. Found 2026-08-28: the `info` toast had shipped as
  `color: 'blue'` + `iconColor: 'amber'`, firing from 24 call sites as the one
  surface in the app that ignored the theme. Bare `'blue'` (no numeric suffix)
  is what slipped past every prior sweep.
- **Carve-outs (must be commented):** brand-logo hex (Aldi/Coles/IGA),
  deterministic hash swatches (`ProductSearchCard` DEC-8), `ScanOverlay` rings
  (DEC-4), `MerchantLogo` placeholder (DEC-9), settings theme-picker swatches
  (DEC-10), the `read('--token', '#hexfallback')` canvas pattern. The colour-value
  source files are exempt: `tokens.scss`, `themes.scss`, `colours.scss`,
  `quasar.variables.scss`, `themeService.ts`, `motion.scss`.
- **Source:** `web_app/THEME_AUDIT.md`, `prompts/A1_theme_compliance.md`, FU-046.

### R-003 — Single source of truth for domain logic & constants
- **Rule:** A domain rule, threshold, or constant lives in **exactly one place**.
  The **server owns derived domain facts and cross-entity aggregates**; the
  **client owns presentation and ephemeral view state**. No domain constant (a
  stock-level name, a "7-day" window, a status sequence) or cross-entity rule (e.g.
  "cookable") exists in two languages.
- **Why:** Duplicated logic silently diverges; the `"Out of Stock"` literal alone
  was found in ~28 spots, each guarding against the others drifting.
- **Apply:** A client computing a cross-entity rule, summing across a fetched
  collection, or hardcoding a domain constant is a smell → push it to the server
  and expose it on the DTO; don't copy it a fourth time. Reuse the one existing
  helper (e.g. `helpers/offerLogic.ts`) rather than re-deriving.
- **Violation signal:** the same constant string/number on both sides of the wire;
  a `.find(l => l.name === '…')` domain match in a component; a client re-sum of a
  total the server already computes.
- **Carve-outs:** pure *display* math on server-provided values is fine on the
  client (discount %, unit price) — do **not** over-correct these to the server.
  See the "already clean — do not relocate" list.
- **Source:** `STATE_OWNERSHIP_REFACTOR_PROPOSAL.md` §8.4 (the standing principle),
  mirrored in `CLAUDE.md`.

### R-004 — Stay on the existing framework
- **Rule:** Flask / Quasar / Vue 3. Productionize what exists; do not introduce a
  new framework, language, or parallel stack (no FastAPI, no C#, no rewrite).
- **Why:** A solo-dev finishing project; framework churn is unbounded scope.
- **Apply:** Solve within the current stack's idioms.
- **Violation signal:** a new web framework / second backend appearing.
- **Carve-outs:** none without an ADR.
- **Source:** `CLAUDE.md` Don'ts; Charter Part III cross-cutting build rules.

### R-005 — Portable data access & distribution posture
- **Rule:** Data access is **repository-routed**; the DB layer stays portable
  across **SQLite *and* Postgres** (Postgres is the standard target, SQLite the
  lightweight self-host option); cloud-vs-self-host differences are env/config
  driven (no build forks); auth sits behind an interface with a local default;
  **no speculative `tenant_id`** (single-tenant = tenancy of size 1); managed
  conveniences degrade gracefully.
- **Why:** Keeps the "one codebase, SaaS-style, self-hostable" (GitLab-way) trunk
  reachable without paying for multi-tenancy now.
- **Apply:** On any task touching data access, auth, config, or deployment, run the
  `RECONCILED_FINISHING_PLAN.md` §7.5 checklist. Prefer the Postgres-native path
  where SQLite forces a wrinkle (e.g. the UUID/`text()` binding), but keep both
  working.
- **Violation signal:** raw SQL bypassing the repository layer; an engine-specific
  feature with no portable fallback; a `tenant_id` added speculatively;
  `server_default=sa.text('0')` / `sa.text('1')` on Boolean columns (SQLite-only
  literal, breaks on Postgres) — use `sa.false()` / `sa.true()` instead, which
  render portably to `0`/`1` on SQLite and `false`/`true` on Postgres; raw-SQL
  boolean comparisons of the form `WHERE flag = 1` (use the bare column —
  `WHERE flag` — or `= TRUE`).
- **Carve-outs:** documented in §7.5 / Decision 5.
- **Source:** `RECONCILED_FINISHING_PLAN.md` Decision 5 + §7.5; `CLAUDE.md`; FU-045
  (Postgres-default switch landed 2026-06-26).

### R-006 — Clean migrations & explicit dev resets
- **Rule:** Alembic migrations are clean and forward-only — **no idempotent
  guards** (`IF NOT EXISTS` defensiveness) papering over a messy history. Dev
  schema resets go through `drop_all`, gated by `DORA_ALLOW_DESTRUCTIVE`.
- **Why:** Guarded migrations hide drift and make the history un-trustworthy.
- **Apply:** When changing schema, write a clean migration; reset dev data via the
  destructive flag, not by hand-editing.
- **Violation signal:** `IF NOT EXISTS` / try-except guards inside a migration;
  ad-hoc schema mutation outside Alembic.
- **Carve-outs:** none without an ADR.
- **Source:** memory `feedback_migrations_schema`.

### R-007 — Scope discipline / anti-creep
- **Rule:** Do exactly the task. No features, refactors, or abstractions beyond
  what it requires; no premature abstraction (three similar lines beat a wrong
  helper); no half-finished implementations; **pre-release means no
  backwards-compat shims** (no renamed `_unused` vars, re-export stubs, "removed"
  comments — just change the code). Adjacent rough code is **flagged, not fixed
  inline.**
- **Why:** Creep is how a finishing project never finishes (Charter P10).
- **Apply:** Spot something out of scope → `DORA_FOLLOWUPS.md` finding with a
  recommended resolution point, and move on.
- **Violation signal:** a diff touching far more than the task; a new abstraction
  with one caller; a compat shim in pre-release code.
- **Carve-outs:** a fix genuinely required to make the task work — note it.
- **Source:** `CLAUDE.md` Don'ts; Charter P10; memory `feedback_working_style`.

### R-008 — Code-style minimalism
- **Rule:** Minimal comments — only the non-obvious *why* (a constraint, a subtle
  invariant, a workaround, an R-00x/ADR carve-out). **A comment must be useful to a
  reader who has no memory of how the code got here.** No WHAT-comments (they
  restate what the code already says). No task/PR/prompt/FU-ID references in code
  — those live in `DORA_WORKLOG.md` / `CHANGELOG.md` / commit messages, not the
  source. No multi-paragraph docstrings. No emojis in code. No AI self-references.
  No gratuitous `.md` files.
- **Why:** Comments that restate the code rot; prompt/FU-ID prefixes have zero
  value once the prompt is closed and clutter every skim; the user has repeatedly
  asked for this.
- **Apply:** Default to zero comments; add one only when a future reader would
  otherwise be confused. If the substance of a comment *is* real WHY, keep the
  substance but drop the prompt-ID / FU-ID prefix (e.g. `# P8-05 — buy-verdict
  defaults on because ...` → `# Buy-verdict defaults on because ...`).
- **Violation signal / close-gate greps** (run before closing any unit that
  touched code):
  ```
  rg -nE '(#|//) +(P[0-9]|C-[0-9]|B[0-9]|INV-[0-9]|FU-[0-9])' \
     dora_api/ tests/ web_app/src/
  ```
  Expected output: **nothing outside test-only setup helpers**. Any hit is a
  fix-in-place before close. Standing R-0NN / ADR-0NN references are allowed
  (`# R-003 —`, `# ADR-014 —` etc.) — the numeric pattern above deliberately
  excludes them.
- **Violation signal (WHAT-comments):** a comment that could be deleted without
  a future reader losing information — because it just names what the next line
  does — is a WHAT-comment. Delete it. Signals: `# Set X to Y`, `// Loop through
  items`, `# Handler for /foo endpoint` directly above `def foo():`.
- **Carve-outs:** the explain-in-place comments R-00x enforcement *requires* (an
  R-0NN or ADR-0NN reference that names the rule) — those are wanted. A one-line
  reference to a live FU that is *currently open* and load-bearing on this exact
  code (e.g. `# workaround for FU-045 — remove when Postgres migration lands`)
  is a carve-out; delete it when the FU closes.
- **Source:** memory `feedback_code_style` + FU-462 close-out (2026-07-07).

### R-009 — Safe mutations: preview → approve → commit
- **Rule:** No silent writes. User-facing mutations are previewable, undoable, and
  explainable (show *why*). Never log secrets or PII.
- **Why:** Charter P7 + P3 (self-correcting & honest).
- **Apply:** A new write path surfaces what it will do before doing it where the
  UX allows; destructive/irreversible actions confirm first.
- **Violation signal:** a fire-and-forget mutation with no preview/undo; secrets in
  logs.
- **Carve-outs:** trivially reversible, low-blast-radius writes.
- **Source:** Charter P7/P8/P12.

### R-010 — Strong types over stringly-typed matching
- **Rule:** Where the language permits, model values with the strongest type
  available and let the compiler/type-checker enforce correctness. Prefer enums,
  typed IDs, and proper types to bare strings; prefer typed comparisons to
  string-coerced ones. Don't side-step the type system (no `any`, no `# type:
  ignore`, no `str()`-both-sides to make a comparison "work") to silence a checker
  that is correctly objecting.
- **Why:** The compiler/type-checker is free, always-on review. Stringly-typed
  code pushes whole classes of bugs to runtime: this branch shipped a guard that
  compared a `UUID` to a `str` path param and so **always** mismatched (line
  tick/delete silently 404'd, FU-059) — a typed comparison or a coerced-at-the-
  boundary `UUID` would have made it impossible. A `str(...) != str(...)` patch
  fixes the symptom but keeps the values weakly typed; the root fix is to carry the
  strong type.
- **Apply:** New code carries the strong type end-to-end. Coerce external input
  (HTTP path/query params, JSON, env) to its real type **once at the boundary**,
  not by stringifying the strong side at each comparison. Reach for an enum/literal
  union over free strings when the value has a known closed set. On the frontend,
  prefer discriminated unions + exhaustive `switch` over string equality scattered
  across call sites; never reintroduce `any` to dodge a `vue-tsc` error.
- **Violation signal:** `str(x) != str(y)` (or `String(x) === String(y)`) bridging
  two differently-typed values; comparing a domain object to a raw string; a path
  param used as an id without coercion; `any` / `@ts-ignore` / `# type: ignore`
  added to quiet the checker rather than fix the type.
- **Carve-outs:** Values that are *genuinely* strings end-to-end (a name, a free-text
  note) stay strings. Plain-string **status sentinels backed by a closed
  `*_VALUES` set + a single validation point** (as in the shopping-list `status`
  model) are an accepted lightweight stand-in for a DB enum **only** while every
  read goes through the named constants and writes are validated against the set —
  don't let raw status literals leak across the codebase. The boundary coercion
  itself (one `UUID(raw)` / `int(raw)` at an edge) is the correct shape, not a
  violation.
- **Source:** ADR-003; this session's UUID-vs-str guard bug (FU-059).

### R-011 — Use the framework's idiomatic, current-recommended pattern
- **Rule:** Solve problems with the framework's first-party feature, not a
  hand-rolled workaround — and use the *current-recommended* version of that
  feature for the framework version pinned in `package.json` / `pyproject.toml`.
  For Vue 3.4+ that means `defineModel()` over manual `modelValue` prop +
  `update:modelValue` emit pairs; `<script setup>` over Options API; composables
  + `provide/inject` over ad-hoc global state. For Quasar that means using its
  plugins (`Screen`, `Dark`, `Dialog`, `Notify`) and **activating them per
  Quasar's docs** (e.g. `Screen.setDebounce()` in a boot file) before relying
  on their reactivity. For Flask/SQLAlchemy that means the ORM patterns the
  installed major version recommends, not pre-2.0 query idioms.
- **Why:** Hand-rolled equivalents drift from the framework's evolution,
  miss bug fixes shipped upstream, and produce subtle bugs that only show up
  at runtime. This session caught two at once in `FilterBar`: a manual
  controlled/uncontrolled `modelValue` computed silently failed because Vue
  coerces unset Boolean props to `false` (defeating the `=== undefined`
  sentinel), and `$q.screen.gt.sm` was being read without the Screen plugin
  ever being activated, so every viewport check returned `false`. The
  idiomatic patch — `defineModel()` + a `Screen.setDebounce()` boot file —
  is shorter, type-safer, and tracks Quasar/Vue upstream.
- **Apply:** Before writing custom state-sync, lifecycle, reactivity, or
  responsive code, check whether the framework already ships the primitive.
  When using a Quasar plugin that requires activation (`Screen`, `AddressbarColor`,
  etc.), wire the activation in `src/boot/` and register it in
  `quasar.config.ts`. When the framework has multiple ways to do a thing,
  pick the one the current major-version docs recommend.
- **Violation signal:** manual `modelValue` + `update:modelValue` plumbing in
  new code; reading `$q.screen.*` without a Screen activation boot file;
  custom resize listeners replicating Quasar's; Options API in a new
  component; a hand-rolled `ref` pattern that mirrors `defineModel` /
  `useTemplateRef` / `toRefs`; SQLAlchemy 1.x-style `Query.filter_by` in new
  code on a 2.x install.
- **Carve-outs:** A framework primitive that genuinely doesn't fit (rare —
  document with an inline comment + ADR). Legacy code that pre-dates the
  framework version bump can stay until it's next touched (no opportunistic
  rewrites).
- **Source:** ADR-004; this session's FilterBar bug (FU-087).

### R-012 — Discoverability: working features stay visible
- **Rule:** A feature the user is expected to *use* must be visibly reachable
  on the surface where it applies — a labelled button, a toolbar action, an
  inline control. Overflow/ellipsis menus ("⋮", "More") are reserved for
  actions that are **rare or destructive** (delete, clear-all, export/print,
  one-a-month housekeeping). Never bury a working action three taps deep to
  save visual space; if the toolbar is crowded, that's a design problem to
  solve with hierarchy, not with hiding.
- **Why:** If it's hidden, the user is less likely to find out it exists.
  The shopping-list surface proved it repeatedly: group-by/refresh-deals/
  move/export all sat behind one unlabelled ellipsis, the per-row actions sat
  behind a second one, the price editor hid behind an unstyled text chip and
  the shop-day setter behind an unstyled text link — the user reported
  *missing the existence* of several of these (UX-v2 feedback S5/S12/S14/S17).
- **Apply:** When adding an action, default it to a visible labelled control
  on the page toolbar (`PageToolbar` actions slot) or directly on the row it
  affects. Move it into a "More" overflow only if it is rare or destructive —
  and label that dropdown "More", never a bare icon. Buttons that *look* like
  text (links with no affordance) count as hidden.
- **Violation signal:** a new q-menu/ellipsis holding everyday actions; an
  action only reachable from a kebab when there's row/toolbar space; a
  clickable element styled as plain text; a feature whose only entry point is
  inside another feature's dialog.
- **Carve-outs:** dense list rows (e.g. a virtualised rail) may keep per-item
  housekeeping behind a kebab — the row's *primary* action (select/open) must
  still be direct. Document anything else inline with the rule id.
- **Source:** ADR-006; shopping-list UX-v2 session (user: "keep features
  visible/easily reachable as much as possible — this should be an
  engineering rule").

---

### R-013 — E2E API tests dispatch in-process via the Flask test client
- **Rule:** API-level e2e tests drive the app through Flask's
  `app.test_client()` (in-process WSGI dispatch), never a real socket server
  booted in a background thread. The `tests/e2e/dora_api/conftest.py` `api`
  fixture owns this: it runs `startup(is_test_env=True)`, logs in once, and
  rebinds the module-level `requests.*` helpers **and** `requests.Session` to
  thin adapters over the test client — so test bodies keep calling
  `requests.get(...)` unchanged.
- **Why:** The old harness ran a werkzeug dev server on `localhost:5170` and
  hit it over the loopback TCP stack — ~2.7s/test (real connection setup plus
  the Windows `localhost` IPv6-fallback penalty, compounded by the dev
  server's `Connection: close`), ~13.5 min for ~300 tests. In-process dispatch
  is the same coverage with no socket: the suite dropped to **~6s (~95×)**, and
  the fail/pass set was byte-identical the moment it landed.
- **Apply:** New e2e tests just use `requests.*` / `requests.Session()` as
  before — the fixture is `autouse`, so the rebind is always active and tests
  no longer depend on some *other* test having triggered it first. The adapter
  covers `json=`/`params=`/`headers=` and multipart (`files=`/`data=`); extend
  it there if a test needs a new transport feature, don't reintroduce a live
  server.
- **Violation signal:** a test spinning up `app.run(...)` in a thread; a
  `time.sleep(N)` waiting for a server to boot; a bare `requests.get` against a
  hardcoded `localhost:<port>` that assumes a real listener.
- **Carve-outs:** a genuine cross-process / network-boundary test (CORS
  preflight, real WSGI server behaviour, nginx interplay) legitimately needs a
  live server — isolate it and document the rule id inline. Pure API contract
  tests do not.
- **Source:** ADR-008; FU-166 (legacy e2e suite triage).

### R-015 — Every DB constraint has a deterministic name (SQLite batch-mode compatibility)
- **Rule:** Every `UNIQUE`, `CHECK`, `FOREIGN KEY`, `PRIMARY KEY`, and `INDEX`
  in the schema **must end up with a deterministic name**. We get this by
  attaching the project `NAMING_CONVENTION` (defined in `dora_api/app.py`) to
  the SQLAlchemy `MetaData`, threading it into the Alembic context in
  `migrations/env.py`, and wrapping `op.batch_alter_table` there so every
  batch operation inherits the convention without each call having to pass it.
  When a migration writes a constraint with an explicit `name=`/literal, give
  it the **bare suffix** (e.g. `'shopping_list_line_anchor'`) and let the
  convention add the type prefix — never hard-code `ck_*`/`uq_*`/`fk_*`
  yourself (that double-prefixes under the convention).
- **Why:** SQLite has no `ALTER TABLE ADD/DROP CONSTRAINT`, so Alembic's
  batch mode rebuilds the table by copying rows into a fresh one — and to do
  that it has to re-emit every constraint. An **unnamed** constraint can't be
  reproduced, and the chain dies (`ValueError: Constraint must have a name`).
  Bit us twice already (FU-178: full-chain `flask db upgrade` died at
  `d7c9e4a8c2b1`; two-machine sessions where the second machine couldn't
  bootstrap a SQLite DB).
- **Apply:** All new constraints (on models and in migrations) inherit the
  convention automatically; you just need to **stop hand-writing `ck_*`-style
  literal names** in migrations — write the suffix only. New batch migrations
  need no per-call boilerplate; the `env.py` wrapper injects the convention.
  Postgres deploys benefit too — deterministic names make ops grep-able.
- **Violation signal:** a model `UniqueConstraint(...)` / `CheckConstraint(...)`
  with no `name=` **and no MetaData convention**; a migration adding an
  unnamed constraint inline (e.g. `db.UniqueConstraint('x','y')` with no
  name); a migration literal that re-prefixes its type
  (`'ck_<table>_<suffix>'`) and so double-prefixes under the convention;
  `flask db upgrade` from base failing with `ValueError: Constraint must
  have a name` or `ValueError: No such constraint: 'ck_<table>_ck_<suffix>'`.
- **Carve-outs (must be commented):** none — the convention covers all
  practical cases.
- **Source:** ADR-010; FU-178 (resolved 2026-06-17).

### R-014 — Reveal-and-disable: show a feature exists even when it isn't set up
> **⚠️ SUPERSEDED 2026-07-06 by [R-029](#r-029--respect-the-off-state-hide-dont-nag) / ADR-025.** The reveal-and-disable directive is retired: if a user or the household admin has *disabled or not configured* an optional feature, hide it — don't advertise it as a nag. The rule text below is preserved for audit trail only; do not follow it in new work. Empty-state "calm placeholder instead of vanishing" usages (the dashboard, meal-plan week banner, etc.) are unaffected — they're a separate pattern that was mistakenly labelled R-014 in some comments and lives on its own footing.

- **Rule:** Prefer to **surface a feature's entry point even when the feature
  is not yet configured/enabled**, rendered in an obvious **disabled / "not set
  up" state** (a `:disable`d control + a tooltip/hint that says how to enable
  it), rather than `v-if`-removing it. The goal is discovery — users should
  learn a capability exists so they can choose to turn it on. Applies **where
  it makes sense** (judgement, not a blanket reveal of everything gated).
- **Why:** A hidden feature is one the user never discovers and never adopts.
  The product should advertise its own capabilities (show the email/scan
  affordance, disabled, with "Set up emailing in Settings" — not a blank
  space). Distinct from ADR-002, which gates *functionality* behind the flag;
  this rule governs the **presentation of the off/unconfigured state** —
  visible-disabled, not absent. It therefore partially revisits ADR-002's
  hide-when-off presentation.
- **Apply:** When gating an action on a config/enable flag (SMTP configured,
  `scanning_enabled`, an integration set up), render the control disabled with
  a one-line reason + a path to enable it, instead of removing it. The disabled
  affordance must read "available, not yet set up", **not** "broken"; the action
  must not fire while disabled.
- **Violation signal:** a `v-if="featureEnabled"` that removes an *adoptable*
  feature's only entry point (vs `:disable` + a hint); a blank toolbar where a
  setup-able action could advertise itself.
- **Carve-outs (must be commented):** features genuinely inapplicable to the
  install (not merely unconfigured); surfaces where a disabled control would
  mislead or clutter; security-sensitive surfaces that shouldn't advertise
  their existence.
- **Source:** ADR-009; meal-plans impl review (user: builder Email button
  disabled-not-hidden; "we want to SHOW features exist … but obvious it's not
  set up"; scanning button should now show disabled instead of hidden).

### R-016 — Lazy store hydration; boot files don't block app mount
- **Rule:** Pinia stores hydrate **lazily, on demand**, via an
  `ensureLoadedAsync()` method that no-ops if the collection is already
  populated and dedupes concurrent first-time loads. **Pages own their own
  data hydration** — call `ensureLoadedAsync()` in `onMounted` /
  `beforeRouteEnter` for what the page actually needs. The Quasar `boot/`
  layer must **never** `await` collection fetches at the top level — in
  practice this means no `boot/` file should be doing data hydration at all
  (Dora's `boot/stores.ts` was deleted, not just rewritten). Use the bare
  `getXAsync()` only as a **force refetch** (after a mutation,
  pull-to-refresh, manual reload button).
- **Why:** A top-level `await` in a boot file blocks the entire shell from
  rendering until every queued fetch resolves — on a cold backend that is a
  blank-screen second or two, the opposite of "smooth navigation". And as
  stores accrete, the boot list drifts: ours preloaded `productStore` long
  after Phase D moved products to an overlay, paying for a fetch nothing on
  the cold path needed. Lazy hydration means each page only pays for what
  it reads, while the boot warmup still primes the most-used collections in
  the background so navigation feels instant.
- **Apply:** New stores expose `getXAsync` (refetch) **and**
  `ensureLoadedAsync` (load-if-missing). The two-flag pattern is:
  ```ts
  let hydrated = false;
  let inflight: Promise<void> | null = null;
  const ensureLoadedAsync = (): Promise<void> => {
      if (hydrated) return Promise.resolve();
      inflight ??= getXAsync().finally(() => { inflight = null; });
      return inflight;
  };
  ```
  Pages: call `ensureLoadedAsync()` in `onMounted`. Don't gate on
  `length === 0` at the call site — that's what the store guard is for.
  Don't add new top-level `await`s in `boot/`.
- **Violation signal:** a `boot/` file with `await use…Store().getX…()`
  at module scope; a page that branches on `store.items.length === 0`
  around a `getXAsync()` call (the guard belongs in the store); a new
  store exposing only `getXAsync()` with no `ensureLoadedAsync`.
- **Carve-outs (must be commented):** post-mutation refresh after a
  save/move/delete (force the refetch via `getXAsync` and explain it's
  picking up server-derived fields); pull-to-refresh; explicit "reload"
  affordances. Stores whose state is purely client-local (no fetch) don't
  need the helper.
- **Source:** ADR-011; user query 2026-06-18 about boot-time preloading
  vs best practice (this work unit). Earlier inlined `length === 0`
  checks across DoraChat / QuickAddSheet / RecipeCookMode /
  ShoppingListDetail / MyProductsPage / BarcodesQR / ShoppingListTemplates
  were the recurring shape that prompted the rule.

### R-017 — Seed-data discipline: features land with seed coverage
- **Rule:** any code change that **adds, modifies, or removes a feature**
  MUST also update `dora_api/persistence/seed.py` in the same unit of work,
  so a fresh `DORA_ALLOW_DESTRUCTIVE` reset yields plentiful, varied test
  data that exercises the new/changed feature's **state matrix**. New
  entities → seed rows covering edge cases (empty / threshold / over).
  Modified entities → updated seed values (no orphan rows the new code
  can't render). Removed entities/columns → cleaned references. Pure
  refactors, non-feature tidy-ups, and shared-helper extractions are
  carve-outs (no behaviour change → no seed movement).
- **Why:** Repeatedly a feature has landed, code-reviewed clean, but a fresh
  dev env produced no row that triggered the new code path — the next agent
  (or the user, on browser walk) had to hand-click their way through the app
  to manufacture the state. The "Your prices" widget is the canonical
  example: without the FU-227 chunk-2 observation seed (3+ obs / 1 above-1.15× /
  count-dim / store-tagged / < MIN_SAMPLES variants), the widget renders the
  empty state on every item and the above-usual chip is invisible. Seed-data
  reviews then *also* drift behind code reviews. Move them together.
- **Apply:** When the diff touches a feature surface (new endpoint, new
  entity field, changed read shape, new conditional render), open `seed.py`
  in the same commit and ask "does the fresh seed surface this end-to-end?".
  Add rows that cover **(a)** the happy path, **(b)** at least one edge — the
  threshold, the empty state, the < min-samples branch, whatever the feature
  has. Use the existing helper functions when present (`make_item`,
  `make_product`, `price_obs`, …); extract one if a third use appears.
  Re-run the seed locally (`DORA_ALLOW_DESTRUCTIVE=1` + restart) and verify
  the new state renders before closing the work unit.
- **Violation signal:** a chunk's diff touches a feature but `seed.py` is
  untouched; the worklog entry doesn't mention seed updates; the close-gate
  browser walk requires hand-clicking through the app to manufacture a state
  the new code is supposed to render; a future PR adds seed rows "to test
  a feature that landed three chunks ago".
- **Carve-outs (must be commented):** pure refactors that don't change a
  user-visible shape (extracting a helper, renaming an internal symbol);
  bug fixes that don't introduce a new state (a one-line null-check); chunks
  that explicitly **remove** a feature without adding a replacement (the
  seed clean-up is the action, not new rows). For each carve-out, the
  worklog says "no seed change needed because…".
- **Source:** FU-227 chunk 1 → chunk 8 (the pricing-system reassessment).
  The handoff doc spelled out the matrix the widget needed to render —
  baseline-ready, above-1.15×, count-dim, store-tagged, < MIN_SAMPLES — and
  chunk 2 shipped exactly those seed rows in the same unit. Without that
  discipline the visible widget would have looked broken on every item in
  the dev env. The user asked for this to be a standing rule across every
  prompt, and chunk 8 promotes it here.

### R-019 — No magic: explicit, verbose, consistent
- **Rule:** Prefer **explicit, verbose, locally-readable** code over clever,
  implicit, or auto-discovered behaviour. A reader walking a file top-to-bottom
  must be able to see *what runs and in what order* without consulting a
  separate convention, framework annotation, or "everyone knows we do it this
  way" tribal rule. And when the codebase already has an established pattern
  for a problem, **follow it** — don't introduce a parallel approach in one
  spot "because it felt right here". One pattern, applied consistently, even
  when a one-off variant looks marginally tidier in isolation.
- **Why:** Magic — auto-mappers, decorator chains that mutate behaviour,
  convention-over-configuration past what the framework requires, "smart"
  defaults that vary per-entity, conditional loading that's invisible at the
  call site — moves understanding *away* from the code and into the reader's
  head. The reader has to remember the convention; if they're wrong, the bug
  is silent. The user has named this as a top-line value ("this is exactly why
  I absolutely hate AutoMapper in C# code") — the AutoMapper shape is the
  archetype: a field maps because the names happen to align, and a rename
  three files away silently breaks the mapping with no compile error and no
  obvious site to grep. Inconsistent local patterns ("most of the codebase
  does X but here we did Y because it felt right") force every future reader
  to memorise the exception list — the *consistency* is the value, even when
  the alternative is marginally nicer.
- **Apply:**
  - **Write explicit mappers** between layers (entity ↔ DTO, request ↔
    handler input). One named function per direction; every field listed.
    Verbose, greppable, type-checked end-to-end. No reflection, no name-based
    auto-population, no "*Mapper" libraries.
  - **Avoid decorator/metaclass magic** that hides what runs. A decorator
    that *only* annotates is fine; one that mutates behaviour, rewrites
    signatures, or pulls in side-effects belongs in framework code, not in
    feature code we own.
  - **Don't lean on "convention over configuration"** past what the
    framework already requires. If the framework needs a filename pattern
    or attribute name, fine — that's the framework's contract. Don't invent
    new conventions on top.
  - **Match the codebase's established pattern** for the problem you're
    solving. If 90% of the handlers spell out the entity assignment field
    by field, the 91st does too — even if `dataclasses.replace(...)` or a
    dict-spread would save four lines. Consistency > local cleverness.
  - **No implicit eager-load shortcuts.** When a relationship needs to be
    loaded, the *call site* declares it (`.include(...)` /
    `selectinload(...)` per query) rather than the entity quietly
    auto-loading it. The relationship's default loading stays the
    codebase-wide default (currently `noload`).
- **Violation signal:** auto-mapping libraries (`automapper`,
  reflection-based field copy, `**dataclass_dict`-shaped converters
  between layers); decorators that wrap business logic (`@retry`-style
  decorators that change control flow); per-entity SQLAlchemy
  `lazy="..."` overrides that opt one relationship into a different
  loading strategy than the codebase default; a function that
  short-circuits or transforms based on a name-string match
  ("if it's called 'special_*' then …"); two handlers in the same
  feature folder solving the same shape two different ways; a
  comment of the form "*usually we do X, but here we do Y because …*"
  that isn't documenting a rule's carve-out.
- **Carve-outs:**
  - The framework's *own* idiomatic patterns (R-011) are not magic — using
    `@RECIPE_ROUTER.route(...)`, `@dataclass`, or Vue's `<script setup>` is
    using the framework as documented.
  - A genuinely one-off real-world constraint (a third-party API quirk,
    a regulatory exception) may require a local divergence — explain it in
    place with a comment naming this rule and the reason, *not* just
    "felt right".
- **Source:** ADR-014; user message 2026-06-28 promoting FU-084 from a
  narrow "selectin loading" recommendation into this broader rule.

### R-018 — Optional engines degrade gracefully and never hard-block install or boot
- **Rule:** any feature backed by an **optional external/native engine** — a
  separate binary, a bring-your-own service, or a platform-specific native
  wheel — MUST (a) **degrade gracefully** when the engine is absent (the app
  still boots; the surface hides, disables, or falls back to a built-in
  alternative), and (b) **not** be added as a hard dependency in
  `requirements.txt` when it can't install cleanly on **every** supported
  platform — notably the Windows desktop build. Gate it behind a runtime
  availability probe (binary on PATH / endpoint reachable / model file present)
  and document the per-platform install instead of pinning it.
- **Why:** `piper-tts` (Dora's neural voice) can't be pip-installed on Windows —
  its `piper-phonemize` dependency ships no Windows wheel — so pinning it would
  break `pip install -r requirements.txt` for the desktop target, the opposite
  of "properly added". The LLM assistant is the prior instance of the same
  shape: bring-your-own Ollama, `llm_enabled` off by default, never bundled or
  auto-downloaded. Both are optional, runtime-detected, and fall back (TTS →
  browser speech; assistant → rule-based intents) so the standard artifact
  always boots.
- **Apply:** wiring an engine = add the probe + a graceful empty/503 + a client
  fallback path. Ship the engine automatically where you cleanly can (Docker
  `RUN pip install …`; bundle the binary into the desktop build via the spec —
  guard the bundle so a missing artifact doesn't fail the build) and document
  the optional install for the paths you can't (the 503 hint / README). Large
  data assets the engine needs (e.g. Piper voice models, ~60 MB each) are **not**
  committed to git — provision them at runtime into the data dir (download on
  demand from a pinned, checksum-verified source), so a clone stays lean and the
  asset rides the persistent data volume / backups.
- **Violation signal:** a heavy/native/platform-specific package pinned in the
  main `requirements.txt`; an engine surface that 500s or blocks boot when the
  engine is missing instead of degrading; an availability check that assumes the
  engine is always present.
- **Source:** Piper TTS wiring (2026-06-23) — the near-miss of pinning
  `piper-tts` and breaking the Windows install; generalised from the existing
  BYO-LLM posture. Promotes ADR-013.

### R-021 — Calendar-day logic runs in the household timezone
- **Rule:** Any code that decides "what calendar day is it" — "today",
  "tomorrow", "N days ago / until", a date-boundary window — MUST evaluate
  in the **household timezone** (`AppSetting.timezone`, IANA) on the server,
  via `dora_api.features.app_settings.clock.household_today(repository)`.
  **Never `date.today()`** in feature code: that returns the server-local
  date, which has nothing to do with the household and silently desyncs by
  ±1 day for any household whose offset crosses midnight relative to the
  server. Wall-clock events (created_at, audit log, last_login) stay UTC
  via `datetime.now(UTC)`; **calendar boundaries** route through
  `household_today`. The two are different concerns; mixing them is the
  bug.
- **Why:** The product is a household pantry — every "today" the user sees
  is *their* today, not the server's. Once we run on Postgres in
  Frankfurt (or a managed single-tenant deploy anywhere), every
  `date.today()` quietly becomes wrong. The mechanism (household
  timezone in `AppSetting`, `clock.py` helpers) shipped with C-2.K for
  the meal-plan boundary; FU-174 was the followup to spread it
  everywhere. Without the rule, the next feature touches `date.today()`
  again because that's what Python developers reach for. The rule pins
  the convention: there's exactly one entry point for "what day is it"
  and it always knows the timezone.
- **Apply:**
  - **Server, calendar boundary:** `today = household_today(repository)`.
    Repository plumbing is already on every feature handler; pass it
    through.
  - **Server, wall-clock event:** `datetime.now(UTC)` (Python 3.12+
    canonical form). Storage: `DateTime(timezone=True)` column.
  - **Calendar columns** stay `Date` (no time, no tz). The day this
    expires / was opened / was scheduled is a calendar concept; tz
    semantics live in the *boundary check*, not in the value.
  - **Client:** the server is authoritative for "today". The client
    fetches the boundary (e.g. `mealPlanStore.todayIso`,
    `meal-plans/today`); never computes it from `new Date()` for any
    decision that affects state. A *display-only* fallback before the
    server response arrives (e.g. `localTodayIso()` to seed the calendar
    cursor for a frame) is allowed when commented as such — the data
    binding flips the moment the server response lands.
  - **Display path:** absolute datetimes still render via
    `toLocaleDateString()` (browser-local) — that's user-friendly for
    "when did this happen". Calendar dates (Date type) render as the
    day they represent, no timezone conversion (their semantics are
    timezone-free; `new Date("2026-07-01").toLocaleDateString()` parses
    to local midnight which is fine for read-only display).
- **Violation signal:**
  - `from datetime import date` followed by `date.today()` anywhere in
    `dora_api/features/` or `dora_api/domain/` (other than seed data).
  - `datetime.now()` with no `tz=` argument in feature/domain code.
  - Client `new Date()` / `Date.now()` used to build a date string that
    drives state (route filter, calendar navigation that's persisted,
    server payload). Display-only diffs (`relativeTime`) are OK.
  - A handler that needs a household date but doesn't take a repository
    argument — plumb the repository instead of falling back to
    `date.today()`.
- **Carve-outs (must be commented):**
  - **Seed data / fixtures** — `tests/`, `dora_api/persistence/seed.py`
    — `date.today()` is acceptable; the test environment owns its own
    notion of "now" and there's no household to respect.
  - **Pre-server-response display fallback** — a client-side
    `localTodayIso()` used purely to seed a cursor or highlight a cell
    on the first paint, before the server's boundary value arrives.
    Comment naming this rule.
- **Source:** ADR-016; FU-174 (raised 2026-06-14 during C-2.K design;
  swept 2026-06-29). The C-2.K work introduced
  `AppSetting.timezone` + `clock.household_today` for the meal-plan
  past-day rule; FU-174 extended the rule app-wide and promoted it
  here.

### R-020 — Deferred-save surfaces wire the unsaved-changes guard
- **Rule:** **Any page** that lets the user accumulate edits in local state
  and only persists them when a **dedicated Save action** is invoked **MUST**
  wire `useUnsavedChangesGuard(isDirtyRef)`
  (`web_app/src/composables/useUnsavedChangesGuard.ts`) so that any
  navigation away (router push, sidebar link, browser back, refresh, close)
  prompts to confirm discard while edits are pending. Equivalently: if the
  page has a Save / Update / Apply button gated by an `unchanged` or
  `isDirty` computed, it has a draft window — and that draft window must
  be guarded.
- **Why:** Silent discard of typed edits is a top-tier UX failure — the
  user did the work, the work disappeared, and there was no warning. The
  guard composable exists (one place, one confirm-dialog policy, covers
  `onBeforeRouteLeave` + `onBeforeRouteUpdate` + `beforeunload` at once);
  the only failure mode left is **forgetting to wire it on a new editor
  page**. The pattern recurred during FU-098: even after the composable
  shipped via FU-156 wired into the two large editor pages, the audit
  found two settings pages still silently discarding (account
  username/email, install AI-config). The rule prevents the third recurrence.
- **Apply:**
  - Build a `Ref<boolean>` / `ComputedRef<boolean>` that is `true` iff any
    draft on the page diverges from its last-persisted value. For
    multi-field pages, combine the per-field `unchanged` computeds:
    `computed(() => !aUnchanged.value || !bUnchanged.value)`.
  - Call `useUnsavedChangesGuard(isDirtyRef)` once near the top of
    `<script setup>`. The save path doesn't need any extra wiring — just
    flip the underlying drafts to match `saved.value` on successful save
    and the next nav passes through.
  - The standard discard-dialog copy ("Discard unsaved changes? — Your
    edits will be lost." + Cancel / Discard) lives inside the composable.
    Do **not** re-implement the prompt per-page; do **not** wire a
    page-specific `onBack` handler that bypasses the route-level guard
    (FU-156's exact root cause).
- **What does NOT need the guard (with reasons, so the audit is repeatable):**
  - **Inline / auto-save surfaces** — every edit fires the API on
    `@blur` / `@update:model-value` / toggle. No draft window exists.
    Examples: `ShoppingListDetail` line edits, every settings page that
    saves-on-change (theme, notifications, alert thresholds, timezone,
    money, voice, etc.).
  - **Real-time session state with no Save action** — a "Done" / "Finish"
    action that persists *derived* facts (not raw drafts). Cook mode is
    the canonical example: ticked-off ingredients aren't a draft; they're
    transient session state the user expects to lose on reload.
  - **Save buttons inside dialogs / drawers / popovers** — dialog state
    is intentionally transient (Cancel closes; route nav closes the
    parent and the dialog goes with it). Modal-close is not the same
    risk as silent discard on full-page nav. (If a future report says
    otherwise, a dialog-level guard is its own follow-up.)
  - **Password fields** — browsers expect typed passwords to be lost on
    nav; guarding here works against user expectation.
- **Violation signal:**
  - A page-level form with a `label="Save"` (or "Update"/"Apply") button
    + an `unchanged` / `isDirty` computed and no `useUnsavedChangesGuard`
    call in the same `<script setup>`.
  - A page-specific `onBack` / `confirmLeave` handler reimplementing the
    dialog locally (route-level guard not wired, only the back button
    is protected — FU-156's exact bug).
- **Carve-outs (must be commented):** the four categories above are
  the standing exclusions — if you're skipping the guard, the comment
  should name the category ("save-on-blur", "real-time session",
  "dialog-only", "password field") so the next audit can ratify or
  reject quickly.
- **Source:** ADR-015; FU-098 (2026-06-29) — sweep that promoted the
  pattern after FU-156 (2026-06-12) shipped the composable and wired
  the first two pages. Recurrence (recipe + stock-item detail in
  FU-156, then account + assistant settings in FU-098) is the
  rule-worthy signal.

### R-022 — DnD reorderable lists go through `useDragDropList`
- **Rule:** Any list whose rows are HTML5 drag-and-drop reorderable
  **MUST** plumb through the shared
  `web_app/src/composables/useDragDropList.ts` composable and the
  shared affordance classes in `web_app/src/css/dnd.scss`. Don't
  hand-roll `@dragstart` / `@dragover` / `@drop` listeners on a new
  surface, don't reinvent the dragging-row dim / drop-target ring
  CSS, and don't copy the state-machine pattern from another DnD
  surface into a fresh one.
- **Why:** Three DnD surfaces (shopping-list lines, recipe steps,
  recipe ingredients) independently grew ~80 lines of nearly-identical
  drag state + CSS, each diverging slightly on affordance details
  (outline vs box-shadow; opacity 0.4 vs 0.5; bespoke handle styles).
  Two of those used a sibling-only constraint; one used a cross-
  section reassignment effect; the *shape* of "guard the drag, light
  the drop target, dim the source, persist on drop" was the same in
  every case. Centralising the state machine + affordances behind
  the composable means a new DnD surface is ~10 lines, every list
  feels the same to the user, and accessibility/keyboard improvements
  land everywhere at once.
- **Apply:**
  - Import the composable:
    `import { useDragDropList } from 'src/composables/useDragDropList';`.
  - Construct one per list, supplying:
    - `mime` — a unique payload type (`application/x-dora-<thing>`)
      so a drag in this list never satisfies a drop check in another.
    - `getId(item)` — stable per-row id (UUID, `client_id`, etc.).
      Return null/undefined to mark the row non-draggable.
    - `onDrop({ id, item }, { id, item })` — the per-drop effect.
      The composable has already cleared its drag state by the time
      this fires.
    - **Optional:** `canDragStart(item)` (per-row drag gate; also
      use for a global "is reorder allowed at all?" predicate that
      reads a captured ref), `canDropOn(source, target)` (per-pair
      drop-target gate — defaults to "anything but self"; layer
      siblings-only / type-compat rules here).
  - In the template, spread `bind(item).rowProps` on the row body
    (drop target), `bind(item).handleProps` on the drag handle (icon
    button) **OR** the row body itself for whole-row mode (rows
    without inline editors). Apply `bind(item).rowClass` to the row.
  - Use `class="dora-dnd-handle"` on the handle wrapper to inherit
    the grab/grabbing cursor + sunken hover treatment.
- **What does NOT use this (with reasons, so the audit is
  repeatable):**
  - **Reordering via up/down arrow buttons.** Buttons are fine — DnD
    is the affordance upgrade, not the only valid pattern. The
    rule is "*if* the list uses HTML5 DnD, use the composable", not
    "every reorderable list must be DnD."
  - **External-drop targets (file uploads, image drops from outside
    the page).** Those use the platform's native `File` /
    `DataTransfer` paths, not the row-to-row reorder shape this
    composable solves.
- **Violation signal:**
  - A `.vue` file with a top-level `@dragstart` / `@dragover` /
    `@drop` listener and no `useDragDropList` import.
  - A component-scoped CSS rule that defines `opacity: 0.5` on a
    `*--dragging` class, or an outline / box-shadow on a
    `*--drop-over` class — the shared `.dora-dnd-row--dragging` /
    `.dora-dnd-row--drop-over` rules already do this.
  - A hardcoded `application/x-dora-…` MIME string outside the
    composable.
- **Carve-outs (must be commented):** none expected. If a new
  surface genuinely needs a different drag model (multi-row drag,
  reorder *and* nesting in one gesture, off-row drop zones for
  empty buckets), that's its own ADR — extend the composable
  rather than re-rolling state in the consumer.
- **Source:** ADR-018; FU-326 (2026-06-29) — extraction once three
  hand-rolled DnD surfaces (shopping-list lines [P6-01 Chunk 6],
  recipe steps [FU-094], recipe ingredients [FU-118]) made the
  duplication obvious.

### R-023 — Test naming + shared response matchers
- **Rule:** Tests follow the behavioural pattern
  `test__<unit>__<condition>__<result>` (two-underscore separators,
  greppable, readable in the failure summary). Router tests asserting
  RFC-7807 problem-detail bodies or `{items,total,page,limit}` list
  envelopes use the **shared matchers** in `tests/support.py`
  (`assert_problem`, `assert_envelope`) — never inline the dicts.
  Source-of-truth for the contract lives in one place; one update
  there propagates when the shape moves.
- **Why:** Two reasons fused into one rule. (1) The suite carried two
  naming conventions side-by-side
  (`test__get_x__Condition__Result` vs `test_create_with_…_roundtrips`),
  which made the failure summary jagged and prevented consistent
  grep / parametrize patterns. (2) FU-166 spent days re-aligning ~40
  inline problem-detail assertions when the error contract moved; the
  matchers reduce that to one fix in one file. Both are R-001 (single
  shared primitive) applied to tests.
- **Apply:**
  - New tests: name `test__<unit_under_test>__<condition>__<result>`.
    Examples: `test__create_product__OnZeroPrice__Returns400`,
    `test__get_recipes__WhenCookableFilterOn__OnlyReturnsFullyStocked`.
  - Use `assert_problem(resp, 400, field="name")` instead of writing
    `assert resp.status_code == 400; assert resp.headers['Content-Type']
    == 'application/problem+json'; assert 'name' in resp.json()['errors']`.
  - Use `items = assert_envelope(resp)` instead of re-parsing the
    `{items,total,page,limit}` shape. Pass `expect_total=N` to also
    assert the count.
  - Don't migrate green tests blindly — touch the matcher when you're
    already in the file editing that test. Standing inline assertions
    are flagged but not failure-blocking.
- **Violation signal:**
  - A new test using camelCase or `test_create_with_…` shape.
  - An inline
    `assert resp.headers['Content-Type'] == 'application/problem+json'`
    in a new test.
  - A list test re-asserting the `{items,total}` keys by hand.
- **Carve-outs (must be commented):** legacy tests using the older
  naming may stay until they're next touched. When you edit one, rename
  it. Don't open a "rename all tests" PR — the migration is per-edit.
- **Source:** ADR-019; FU-169 / PROPOSAL_TEST_SUITE_IMPROVEMENTS Phase 1
  (2026-06-29). The naming-convention split + the ~40 inline
  problem-detail assertions were both surfaced during FU-166's
  test-client conversion.

### R-025 — Session-mutating writes need both proof-of-possession and CSRF
- **Rule:** Any HTTP endpoint that mutates a session-bearing user's
  authentication identity (password, email, MFA factors, primary
  recovery channel) or that issues credentials usable to take over the
  account (API key, recovery code, OAuth grant on behalf of the user)
  must require **re-proof of the current password** in the request body
  *and* be gated by the CSRF double-submit defence in
  [`dora_api/infrastructure/csrf.py`](../../dora_api/infrastructure/csrf.py).
  The two layers are independent — neither is sufficient alone, and
  there is no asymmetry between sensitive flows (e.g. "change-password
  needs the password, change-email doesn't" is the bug R-025 exists to
  prevent).
- **Why:** FU-197 found that the email-change endpoint required no
  password proof while the password-change endpoint did. Combined with
  the then-absent CSRF token, that was a complete account-takeover
  chain: a victim browsing an attacker page while logged in could be
  silently switched to the attacker's email + reset link, all without
  the attacker knowing or guessing the victim's password. Both gaps
  fixed at once; the rule keeps them fixed by making asymmetry between
  sensitive flows a violation rather than a judgement call.
- **Apply:**
  - New auth-identity write endpoints: add `current_password: str` to
    the request model, verify with `werkzeug.security.check_password_hash`
    against the loaded `User.password_hash`, return
    `business_rule_violation("Current password is incorrect.")` on
    mismatch. Mirror the shape of
    [`ChangePasswordRequest`](../../dora_api/features/auth/change_password.py)
    /
    [`ChangeEmailRequest`](../../dora_api/features/auth/email_flows.py).
  - Side-effect notification: when the change is async (token-confirmed
    email change, recovery-code regeneration), send a heads-up to the
    address the user **currently** controls before kicking off the new
    flow — see `email_change_notice.html`.
  - CSRF is automatic: the middleware in
    [`dora_api/infrastructure/middleware.py`](../../dora_api/infrastructure/middleware.py)
    gates every mutating call on `/api/*` unless the endpoint name is
    in `PUBLIC_ENDPOINTS` or `CSRF_EXEMPT_ENDPOINTS`. **Do not** add new
    endpoints to those lists without a written rationale (bearer auth,
    pre-session bootstrap, etc.).
  - Audit emit on both success (`SEVERITY_AUDIT`) and password-mismatch
    (`SEVERITY_WARN`) so a brute-force attempt against the password gate
    is visible in the audit log.
- **Violation signal:**
  - A new `@AUTH_ROUTER.route(...)` mutator without `current_password`
    in its request schema.
  - A new endpoint added to `PUBLIC_ENDPOINTS` or `CSRF_EXEMPT_ENDPOINTS`
    without a comment explaining why.
  - SPA wiring that posts an auth-identity change without prompting for
    the current password.
  - An "admin-side" path that lets an authenticated user change their
    own auth identity without re-prove (admin acting on **other** users
    is a separate flow — those go through the audited admin endpoints,
    which require admin role, not password re-prove).
- **Carve-outs (must be commented):**
  - The token-driven recovery flows (`reset-password`,
    `confirm-email-change`, `verify-email`) are exempt because the
    one-shot token IS the proof-of-possession; the user clicking the
    link is the equivalent of re-prove.
  - Bearer-authenticated machine endpoints (currently only
    `submit_ingestion_batch`) skip CSRF because the long-lived API key
    is never browser-ambient.
- **Source:** FU-197 (2026-06-30). Promoted to a rule because the
  asymmetry between password-change and email-change shipped without
  triggering a review — the gap was invisible until a security pass
  spotted it. Codifying "both sensitive flows or neither" makes the
  next asymmetry impossible to ship silently.

### R-024 — Image upload UX goes through `ImageSourcePicker`
- **Rule:** Every site that lets the user upload an image renders its
  source-pick affordance via the shared
  [`web_app/src/components/ImageSourcePicker.vue`](../../web_app/src/components/ImageSourcePicker.vue)
  primitive. The picker owns the **Take photo / Choose image** split,
  the touch-device detection that decides whether to show the camera
  button, the hidden `<input type="file">` elements (with/without
  `capture="environment"`), and the call into `processImageFile` (R-003).
  Consumers receive a `ProcessedImage` (or an `error` message) and only
  decide what to do with the data URL. No bespoke `<input type="file">`
  or `<q-file>` in feature code.
- **Why:** The first cut of receipt-photo upload (FU-334) used a single
  `<input accept="image/*" capture="environment">`. That biased Android
  Chrome straight to the camera with no gallery option — exactly the
  opposite of "let me also pick a photo I already took". The audit that
  followed found three different upload shapes across the SPA
  (`ImageUploadField`, `RecipeStepImagesEditor`, `StoresSettings`,
  `ShoppingListDetail`), each making its own camera-vs-gallery choice
  silently. R-003 already centralised resize/encode; the *pick UX* needs
  the same chokepoint or the same bug appears N times.
- **Apply:**
  - New upload sites: drop `ImageSourcePicker` in directly, listen for
    `@pick="(image) => ..."` (a `ProcessedImage`) and `@error`.
  - Sites with chrome around the picker (preview + Remove button):
    compose `ImageUploadField` (which now delegates to the picker
    internally) rather than reinventing the wrapper.
  - Bulk-upload (recipe step images, receipt batches if it ever
    arrives) pass `multiple` — the picker emits one `pick` per file in
    order; coalesce in the parent if needed.
  - Don't pass `capture="environment"` on a bespoke input — that's the
    primitive's job and it varies by platform.
- **Violation signal:**
  - A new `<input type="file" accept="image/*">` in feature code.
  - A new `<q-file>` for image upload.
  - A handler that calls `processImageFile` directly from a bespoke
    `change` listener.
  - A site that has *only* a camera button or *only* a file button when
    both make sense.
- **Carve-outs (must be commented):**
  - `StoresSettings.vue` retains its `q-file` until FU-335 migrates it
    (drag-drop visual + clearable affordance need a measured swap).
- **Source:** FU-334 follow-on (2026-06-30). The single-`capture`
  receipt-upload button surfaced the gap; the standards rule turns the
  fix into a one-time decision.

### R-026 — Nav-state on list pages: persist within session, reset on full reload
- **Rule:** Any list page whose user has spent effort dialing in filters,
  search text, sort, or scroll position must preserve that shape when
  they navigate away (to a detail page, another route) and back within
  the same SPA session. A full browser reload should feel like a clean
  slate — no restored filters, no restored scroll. Persistence goes
  through the shared
  [`useListState(scope, factory)`](../../web_app/src/composables/useListState.ts)
  composable (module-level Map, gone on hard reload); scroll uses Vue
  Router's `savedPosition` via the app's `scrollBehavior`. No
  `localStorage`, no `sessionStorage`, no Pinia store slice for these
  refs.
- **Why:** Before A8 §3 the app was inconsistent — a couple of pages
  kept their state via ad-hoc mechanisms (product search URL, filter
  panel expanded), most didn't. Users reported the "click a stock item,
  hit back, lose your filters" tax. Full-reload persistence via
  `localStorage` was rejected because a stale filter that survives a
  browser restart traps users on an empty list they don't remember
  configuring; the session boundary is the honest one.
- **Apply:**
  - New list page: wrap filter / search / sort refs in a single
    `useListState('<page-key>', () => ({ ... }))` call and destructure.
    Non-persisted state (loading, in-flight fetches, hover, dialog
    open) stays as regular `ref()`.
  - Existing list page: migrate its refs into the composable using a
    stable scope key; keep the same defaults so first-visit UX doesn't
    shift.
  - Filter-composables that back multiple pages (`useStockFilters`)
    take an optional `persistScope` — callers pass their page key,
    the composable wires the refs through `useListState`.
  - The router's `scrollBehavior` already honours `savedPosition`; do
    NOT override per-page unless there's a genuine reason (e.g. the
    detail page anchors to a heading), and if so, document it inline.
- **Violation signal:**
  - A list page with `ref('')` search text bound to `v-model` and no
    `useListState` wrapper.
  - `sessionStorage`/`localStorage` used to persist a filter (except
    the FU-121 filter-panel-expanded preference, which is
    intentionally cross-session because it's a display preference
    rather than a filter value).
  - A per-page `scrollBehavior` override in `router/index.ts`.
- **Carve-outs (must be commented):**
  - `useFilterPanelExpanded` (FU-121) uses `localStorage` on purpose —
    it's an ambient display preference, not a filter value.
  - `useProductSearchUrl` mirrors state into the URL for
    deep-linking / share; that's a different contract and is
    intentionally not migrated.
- **Source:** A8 §3 landed 2026-07-01. Round-trip pattern established
  via `useStockFilters`, `RecipesOverview`, `MyProductsPage`; remaining
  list pages migrate opportunistically (tracked in `DORA_FOLLOWUPS`).

### R-027 — Styling encapsulation: component owns intrinsic appearance; parent owns layout context
- **Rule:** A shared component owns its **intrinsic appearance** — size,
  padding, border-radius, colours, hover, transitions, disabled-state
  styling — and callers must not re-declare or fudge them at the call
  site. The **parent** owns **layout context** — position in a flex row,
  spacing between siblings, alignment with surrounding chrome. A
  component **must not introduce a wrapper DOM element that fights the
  parent's layout scheme**. If a shared component renders multiple
  children (a paired button set, a label + control), the children
  render as top-level siblings via a Vue 3 multi-root template — never
  wrapped in an inner `<div>` that carries `q-gutter-*` or any other
  spacing scheme that collides with the parent container's own.
- **Why:** Two failure modes recur when the rule is broken.
  1. **Wrapper vs parent gutter collision.** Quasar's `q-gutter-*`
     classes are the negative-margin trick — the container gets
     `margin-top: -8px` and each direct child gets `margin-top: +8px`.
     If a component wraps its own children in a `<div class="row
     q-gutter-sm">` and that wrapper is placed inside a parent
     `q-gutter-sm` toolbar row, the wrapper receives `+8px` from
     outside AND `−8px` from its own inner gutter. Net displacement
     zero — but sibling `BaseButton`s (direct children of the outer
     row) only get the outer `+8px`, so they sit 8px lower than the
     wrapper. **This is the FilterToggleButton bug that surfaced
     2026-07-02.**
  2. **Call-site style fudge.** When the component underdelivers,
     each caller adds a `class="q-mt-xs"` or a `:style="{ marginTop:
     '-3px' }"` locally to nudge alignment. Every page drifts a
     different fudge. Consistency is destroyed silently.
- **Apply:**
  - Composite components (a Clear + Filters pair, a label + control,
    a search + action group) render children as top-level siblings.
    In Vue 3 the SFC `<template>` root can contain multiple nodes;
    use that instead of a wrapper `<div>`.
  - If a wrapper genuinely IS needed (e.g. the component needs a
    positioning context or a focus ring), it uses **flexbox `gap`**
    for inter-child spacing (`display: flex; gap: 8px`) — `gap`
    doesn't use margins, so there's no negative-margin dance to
    collide with the parent.
  - Callers do **not** re-declare intrinsic styling. If a caller
    wants to nudge alignment, the fix is in the component, not the
    caller.
  - Prefer a component prop over a call-site `class="..."` when the
    caller has a *legitimate* variant need (e.g. `size="sm"`).
    Variant proliferation is fine; call-site fudge is not.
- **Violation signal:**
  - A component's root is `<div class="row q-gutter-*">` wrapping
    other Base primitives, and it's meant to drop into a page toolbar.
  - A page toolbar contains a call-site inline `class` or `style`
    prop tweaking margin/padding/alignment of a shared button.
  - `git grep 'q-gutter' web_app/src/components/` returns shared
    components whose root wrapper carries a `q-gutter-*` class.
    Each hit is a candidate for the collision above; audit whether
    the component is used inside a parent that also carries a
    Quasar gutter class.
- **Carve-outs (must be commented, naming the rule):**
  - A component that is only ever used **standalone** (never dropped
    into a shared-gutter toolbar) may still use `q-gutter-*` — the
    collision only happens when it's a direct child of another
    `q-gutter-*` container. If you carve out, add an inline
    comment: `<!-- R-027 carve-out: only ever mounted at page root,
    no parent gutter -->` so a future author knows why the wrapper
    is safe there but not elsewhere.
- **Source:** ADR-023; FilterToggleButton misalignment surfaced
  2026-07-02 during a toolbar-parity review. The fix was a Vue 3
  multi-root template on FilterToggleButton itself; the rule was
  promoted because the same mistake is easy to make on any future
  paired-primitive component.

### R-028 — Domain inference = pure decision core + thin repo-gather
- **Rule:** A feature that *derives a domain judgement* (a verdict, a belief,
  a score, a prediction) splits into two pieces: a **pure function** that takes
  an already-gathered inputs dataclass and returns the result — no repository,
  no HTTP, no clock reads passed in as an arg — and a **thin gather layer**
  that does the repo access and calls the pure core. The endpoint calls the
  gather layer; unit tests call the pure core directly with fixture inputs.
- **Why:** Domain judgements are where the subtle rules live (cadence cuts,
  confidence decay, override precedence) and where regressions hide. A pure
  core is exhaustively unit-testable without a DB or Flask, so the rules get
  pinned cheaply; mixing repo access into the logic forces slow, brittle e2e
  setup for what is really arithmetic. It also keeps the judgement **server-
  owned** (R-003) with one obvious home.
- **Apply:** New derivation features follow `get_buy_verdict.compose_verdict`
  / `pantry_belief.compute_belief`: an `XInputs` dataclass, a pure
  `compute_x(inputs)`, a `gather_x_inputs(repo, …)` (batched — no N+1 for
  list overlays), and a `tests/test_x.py` that drives the pure fn with
  fixtures. Pass `today`/clock values *into* the inputs so time-dependent
  logic is deterministic in tests.
- **Violation signal:** a handler that queries the repo and computes the
  judgement inline; a domain-judgement test that needs the Flask test client
  or a seeded DB to assert a branch.
- **Carve-outs:** trivial one-line derivations don't need the split — the rule
  is for judgements with ≥2 interacting rules.
- **Source:** established from `get_buy_verdict` (P8-05) and re-applied in
  `pantry_belief` (P8-07); promoted 2026-07-03 (ADR-024) once the second use
  confirmed the pattern.

### R-029 — Respect the off-state: hide, don't nag
- **Rule:** When a user or the household admin has **disabled** an optional
  feature — via a per-user preference, a household `AppSetting` flag, or by
  never configuring the required backend (SMTP, VAPID, LLM, scanning, etc.) —
  its **entry points elsewhere in the app are hidden**, not shown-disabled with
  a "not set up" hint. Respect the off-state; don't advertise a capability the
  household has opted out of. The one place the disabled control legitimately
  appears is **the settings screen that owns its configuration** (Admin →
  System, Preferences, etc.) — that surface exists precisely to enable it.
- **Why:** A disabled-with-hint control everywhere the feature *would* attach
  is a nag: it takes up space and attention advertising something the user
  already said no to (or the household hasn't set up). The Dora product
  posture is calm, effortless, anti-nag — the settings screens are the front
  door for enabling features; the rest of the app respects the current state.
  This supersedes R-014 (reveal-and-disable), which optimised for discovery at
  the cost of nagging. It aligns with ADR-002 (a single flag, respected
  everywhere) and R-012 (working features stay visible — the inverse: *not-
  working / opted-out* features stay hidden).
- **Apply:** Gate the entry point on the same capability flag the functionality
  uses (`useFeatureFlags().hasEmail`, `useScanningEnabled()`, etc.) with `v-if`
  — not `:disable`. The settings screen that configures the feature still
  renders (that's where enabling happens); nowhere else advertises the
  unavailable state.
- **Violation signal:** a `:disable`d button with a "Set up X in Settings"
  tooltip appearing in a workflow surface (a builder, a dialog, a page action
  bar); a comment referencing R-014 on a gated entry point outside the
  feature's own settings screen.
- **Carve-outs (must be commented):** the settings screen that *owns* the
  feature's config obviously shows its own disabled state so it can be turned
  on. Calm empty-state placeholders (dashboard "all clear", empty-week banner,
  score-row explainer) are a different pattern — they're not gating a feature
  the user disabled, they're describing "no data yet". Those stay.
- **Source:** ADR-025; user directive 2026-07-06 walking back R-014 ("if a
  user has disabled something either personally or for the household it should
  not be in their face").

### R-030 — Operational config lives on `AppSetting`, not env
- **Rule:** Install-wide *operational* config — the values an admin would
  tweak after deploy without redeploying (SMTP host / password / port, VAPID
  keys, Piper paths, retention windows, feature toggles, public URL, etc.)
  — lives as columns on the singleton `AppSetting` row, edited from
  **Settings → Admin → System**. **Env vars are reserved for bootstrap**:
  values the app has to read before the DB is reachable (`DORA_SECRET_KEY`,
  `DORA_ENV`, `DORA_SPA_DIR`, storage-path overrides) or root wrapping keys
  the DB ciphertext depends on (`DORA_SECRET_ENCRYPTION_KEY`). Everything
  else — including secrets — belongs on the row, with real secrets stored
  as Fernet ciphertext wrapped by `DORA_SECRET_ENCRYPTION_KEY`.
- **Why:** Bootstrap-vs-runtime is the canonical split in every well-built
  self-hosted app (GitLab `gitlab.rb` vs application_settings; Discourse env
  vs site_settings; Mattermost `config.json` vs admin UI). Blurring it grows
  a long env-var table for operators and — on desktop — makes a
  double-click install untenable. Keeping this on `AppSetting` also honours
  R-005 (portable data access; the row travels with backups; a SaaS tenant
  gets one via the same code path). Real secrets on the row need the FU-153
  Fernet helper so a DB dump doesn't leak them — that's cheap given the
  helper already exists.
- **Apply:** New install-wide config gets an `AppSetting` column + a
  Settings → Admin → System page, not an env var. If the value is a
  bootstrap-time input (read before the DB) OR a wrapping key that decrypts
  the row itself, keep it env. If it's a runtime secret (an API key, an
  SMTP password) it goes on the row *encrypted*, with the response DTO
  surfacing a `<field>_configured: bool` instead of the ciphertext.
- **Violation signal:** a new `DORA_<X>` env read for something an admin
  would want to change post-deploy; a plaintext secret column on
  `AppSetting`; a settings page that reads env directly instead of the
  operational-config resolver.
- **Carve-outs (must be commented):** the seven bootstrap vars listed in
  ADR-026; a genuinely install-location value the desktop bootstrap
  detects at boot and *seeds into* the row (see `desktop_app._seed_desktop_paths`).
- **Source:** ADR-026; FU-333 close-out (2026-07-06) — Buckets B (12 vars),
  C (2 encrypted secrets), D (desktop first-run) shipped end-to-end. Env
  footprint went from 19 → 2 on server self-host and 0 on desktop.

### R-031 — Constructor injection via Protocols; no DI container
- **Rule:** Handlers (and other collaborators-owning classes) declare their
  dependencies as constructor parameters typed against **structural**
  Protocols in `dora_api/infrastructure/ports.py` — not against
  `I`-prefixed ABCs, not by resolving them from a container at call time.
  Wiring happens explicitly at the router / app-factory edge: `Handler(
  repository=SqlAlchemyRepository()).handle(...)`. No reflection-based
  auto-wiring. No `get_container().inject(X)`.
- **Why:** In Python, a Protocol + explicit constructor call gives you the
  entire testability + composability payoff of DI with a fraction of the
  ceremony a container brings. Handler tests substitute a fake by passing
  it to the constructor — no `patch.object`, no framework registration.
  A container earns its keep when you have deep dependency graphs,
  layered lifetimes, and many swappable implementations decided at boot;
  this app has none of that. The prior `dependency_injector`-based
  `DependencyContainer` was reflection over 175 handlers whose only real
  dependency was `SqlAlchemyRepository`, and the container was used as
  a service locator (`get_container().inject(X)`) rather than as real
  DI — a .NET habit imported where it doesn't fit. See ADR-027 for the
  full walk-back.
- **Apply:** New handler → `def __init__(self, repository: Repository) ->
  None: self.repository = repository`. New collaborator that's genuinely
  swappable (email transport, push transport, LLM client, clock, blob
  storage) → add a Protocol to `ports.py`, take it in the ctor, wire the
  concrete at the router or in the app factory. When a real swap surface
  arrives (auth per R-005, email transport, etc.), do it by adding a
  Protocol + a small wiring step in `create_app` — do not reintroduce a
  container.
- **Violation signal:** any new file importing a "container" or a
  registration API; any handler that constructs its own `SqlAlchemyRepository()`
  inside `__init__` instead of receiving one; any `I`-prefix nominal
  interface used as a DI seam.
- **Carve-outs (must be commented):** a handler that legitimately needs
  no repository (e.g. `AskAssistantHandler`, which builds an LLM client
  per-user from Flask session context) skips the parameter — that's
  fine, and the `__init__`'s absence is self-documenting. Never
  synthesise a fake ctor arg just for uniformity.
- **Source:** ADR-027; user directive 2026-07-08 ("is this app just not
  in need of DI, or is the code not written well enough to make use of
  it?") — resolved as "constructor injection yes, container no."

---

### R-032 — Never read a `lazy="noload"` relationship off an un-included load
- **Rule:** If code reads a relationship that is mapped `lazy="noload"`
  (the app's default for most FK relationships), the entity **must** have
  been loaded with that relationship `.include(...)`d on the *same* query.
  A plain `.by_id()` / `.all()` load followed by a relationship read returns
  `None`/empty **silently** — no error, just wrong data. Corollary: within
  one request, build any relationship-dependent map (cookability, expiring
  counts, etc.) *before* the plain id-universe load of the same entity, so
  the identity map doesn't hand back already-loaded noload-empty instances.
  When you only need the FK *value* (an id, for bucketing/comparison), read
  the underscore-prefixed FK property (`item._stock_group_id`) directly — no
  relationship load required — rather than `.include`-ing the whole object.
- **Why:** `noload` is a performance default (don't auto-fetch), but it turns
  every un-guarded relationship read into a silent correctness bug. This is
  the single most recurrent defect class in the codebase — six distinct
  production bugs in two weeks, all the same shape: cookbook filters no-op'd,
  the keeps-running-out report dropped items, stock-group counts read 0, and
  three PATCH bugs including **silent loss of every cook-mode ConsumptionEvent**.
  None raised; all shipped; all were caught by tests, not review.
- **Apply:** Reading `x.some_relationship`? Confirm the query that loaded `x`
  has `.include(SomeEntity.Fields.SOME_RELATIONSHIP)`. Only need its id? Read
  `x._some_fk_id`. Clearing an FK on a noload relationship? Write the
  underscore FK column directly (`x._cuisine_id = None`) — a relationship-side
  `= None` doesn't dirty the column. Add a query-count guard (FU-534) on hot
  read paths so an accidental per-row lazy load also fails loudly.
- **Violation signal:** any `.by_id(...)` / `.all(...)` immediately followed
  by a read of a relationship attribute on the result, without a matching
  `.include` on that same query; any relationship-side `= None` assignment
  used to clear an FK.
- **Source:** ADR-028; recurrent noload family (cookbook identity-map fix
  2026-07-10, FU-527, FU-533, FU-684). FU-684 is the one to read if you think an
  `.include()` settles it: `/stock-items/<id>/buy-verdict` *included* the level
  and still read `None` (the session already tracked the instance with the
  relationship unset), so every verdict the endpoint ever returned was
  `unsure/low`. The FK-value corollary above is the fix.

### R-033 — Entity-id path params use the `uuid` converter; handlers never receive an unvalidated `str` id
- **Rule:** Flask routes whose path param is an entity UUID declare it with
  the `uuid` converter — `@ROUTER.route("/<uuid:stock_item_id>")` — never the
  default string converter (`<stock_item_id>`). With the converter, Flask
  parses the segment to a real `uuid.UUID` before the handler runs and 404s a
  malformed value at routing time; the handler's `id: UUID` annotation is then
  honest. Without it the param arrives as a **`str`** despite the annotation,
  so `entity.id == param` silently fails, `dict[UUID]` lookups miss, and a
  non-UUID segment reaches a query and 500s.
- **Why:** Same root cause, many faces — this str/UUID mismatch produced the
  taxonomy delete-count-always-0 bugs, the product-unlink-always-404 bug, the
  rename-to-own-name-rejected bug at five surfaces, and **82 routes returning
  500 instead of 404** on a non-UUID path segment. The converter fixes the
  entire class at the routing edge and removes the need for per-handler
  `str(...)`/`UUID(...)` coercion workarounds.
- **Apply:** New route with an entity-id param → `<uuid:foo_id>`. The handler
  receives a `uuid.UUID`; compare/kick it around as one. Existing per-site
  `str(id)`/`UUID(str(id))` coercions added before this rule are harmless
  (defensive) and may be removed opportunistically once the route uses the
  converter. Path params that are legitimately **not** UUIDs (tokens, slugs,
  external codes) keep their appropriate converter — this rule is for entity
  ids only.
- **Violation signal:** a route decorator with a bare `<..._id>` segment that
  the handler treats as a UUID; any `str(entity.id) != path_param` workaround
  on a route that could instead use `<uuid:...>`.
- **Source:** ADR-029; str/UUID family (FU-528, FU-532).

### R-034 — The ORM model is the source of truth for the *whole* schema, indexes included; a migration is not a place to hold schema the model doesn't declare
- **Rule:** Every index, unique constraint, and FK covering index that exists in
  the production (migrated) schema must also be **declared in the ORM model**
  (`table_mappings.py`), so `create_all()` (dev + the e2e suite) builds the same
  schema `flask_migrate.upgrade()` builds. A migration adds the DDL to existing
  installs; it never *owns* a schema object the model is silent about. Foreign-key
  columns get a covering index by default (neither SQLite nor Postgres auto-indexes
  them — an unindexed FK full-scans the child table on a parent delete and leaves
  every join on that key unindexed).
- **Why:** For a long time every secondary index lived *only* in the Alembic chain
  and was never mirrored back, so dev + the entire e2e suite ran on a near-unindexed
  schema (1 index) that didn't match production (32) — behaviour depending on an
  index or a `UNIQUE` couldn't be exercised where the model didn't declare it, and
  42 FK columns were unindexed in prod (FU-393 sweep, Findings 1–2). Two build paths
  that disagree is drift by construction; the model being the single source of truth
  (R-003) has to include indexes, not just tables + columns.
- **Apply:** New index/unique/FK → declare it on the model (an `Index(...)` in
  `table_mappings.py`, or `index=True`/`unique=True` on the `Column`) **and** write
  the additive migration. Adding a table? Every FK column on it gets a covering index
  in the same change. The `test__migrations__migrated_schema_matches_orm_metadata`
  gate compares tables + columns + nullability + index/unique colsets + FK `ondelete`
  rules between the two build paths and fails on any undocumented difference; a
  genuinely-intentional divergence goes in that test's allowlist with an owner, never
  silently.
- **Violation signal:** an `op.create_index` in a migration with no matching
  `Index(...)`/`index=True` in `table_mappings.py`; a new FK column with no covering
  index; the schema-match test flipping red without an allowlist entry explaining why.
- **Source:** ADR-030; FU-563 (from the FU-393 data-model sanity sweep).

### R-035 — UI-affecting work is checked against the Design Style Guide (D-rules)
- **Rule:** Any task that adds or changes something a user sees is checked against
  `docs/01_charter/DESIGN_STYLE_GUIDE.md` exactly like the R-rules: fix, explain
  in place (`// D-00N carve-out: …`), or log a `DORA_FOLLOWUPS.md` finding. R-002
  owns the tokens-only *mechanics*; the Design Style Guide owns *usage* — which
  token, what size, how much space, what shape, and what the finished thing must
  look like. It is **prescriptive**: **Part A** (Foundations) maps every role to
  an exact token (colour/type/spacing/radius/elevation/border/icon/breakpoint),
  **Part B** gives per-component specs (buttons, chips, inputs, cards, list rows,
  dialogs, toasts, menus, empty states, skeletons, tables, the floating layer),
  and **Part C** is the enforceable checklist **D-001..D-019** (level-colour
  semantics, contrast floors, type floor, tap targets, icon naming, one
  date/number formatter, skeleton loading, dialog conventions, toast/floating
  placement, micro-feedback, page composition, data-density, state legends, copy
  voice, pattern reuse, full interactive-state coverage, snap-to-scale/no-off-token
  values, alignment/rhythm consistency, no transient-disable on focusable
  controls). When Part A/B states a value, use it
  exactly — an off-token literal is a carve-out, not a judgement call.
- **Why:** the 2026-07-18 UX audit (FU-578, 54 findings +
  `docs/05_investigations/UX_DESIGN_CRITIQUE_2026-07-18.md`) showed a strong
  token architecture leaking Quasar defaults and drifting per-surface (three
  date formats, casing drift, semantically-inverted level colours, sub-AA muted
  text) precisely because no usage-level rubric existed for the close-gate to
  check. Same failure mode ADR-001 fixed for engineering — rules that live only
  in finished audit docs get re-violated by the next session that never read them.
- **Apply:** existing-screen violations are backlog, not licence —
  `docs/04_proposals/DESIGN_REMEDIATION_PLAN.md` tracks them (DR-1..DR-16); new
  work complies from the start. New recurring design decisions get promoted to a
  new D-rule at close-gate, same lifecycle as R-rules/ADRs.
- **Violation signal:** off-scale spatial/type literals in a component
  (`padding: 5px`, `border-radius: 8px`, `font-size: 13px`, hand-mixed
  `box-shadow`) instead of `--space-*`/`--radius-*`/`--font-size-*`/`--elevation-*`
  (D-017); literal `ms` durations; `toLocaleDateString`/hand-formatted dates
  (D-006); "Loading…" strings instead of skeletons (D-007); default-caps `q-btn`
  in dialogs (D-008); icon-only buttons without `aria-label`+tooltip (D-005);
  `outline: none` without a replacement focus ring (A6/D-016); text on a `-soft`
  token using the soft (not full-strength) colour (A1/D-002); any new
  colour-to-meaning mapping not derived from the semantic/severity tokens.
- **Source:** ADR-031; FU-578 audit + owner directive 2026-07-18; strengthened to
  the prescriptive Part A/B spec 2026-07-19 (owner: "leave less guess-work").

---

### R-036 — A `MainLayout`-hosted route component roots on `<q-page>`; never hardcode the layout offset
- **Rule:** every route rendered inside `MainLayout`'s `<q-page-container>` roots on
  `<q-page>`, not a bare `<div>`. `<q-page>` is the only thing that gives a page a
  **height contract** — it sets `min-height: viewport − layoutOffset` from *live*
  layout state (header size, and a footer if one ever lands). Two shapes, pick by
  scroll model:
  - **Document-scroll page** (a growing list/grid; the window scrolls): bare
    `<q-page class="q-pa-md">`, no `:style-fn`. The default min-height is what makes
    a `position: sticky` footer (`PageCountsFooter`) pin to the viewport bottom even
    when the content is shorter than the viewport. **Reference: `RecipesOverview.vue`.**
  - **Fixed-height app-shell** (chrome + an internally-scrolling pane, e.g. a virtual
    list that caps its own height): `<q-page :style-fn>` returning
    `height: height === 0 ? calc(100vh − ${offset}px) : ${height − offset}px`.
    **Reference: `StockOverview.vue` (`pageStyleFn`).**
  Never hardcode the offset (`calc(100dvh − 64px)`, a magic `64`): it silently rots
  when chrome changes (e.g. `OfflineBanner` adds 48px when the API is unreachable) —
  take the live `offset` from `:style-fn`.
- **Why:** a bare-`<div>` page has no height contract, so anything height-dependent —
  a sticky footer, a fill-the-viewport shell, an internally-scrolling pane — must
  hand-roll the offset with a pixel guess that drifts from reality. This is exactly
  how the Stock Overview scroll/footer bugs happened (a self-capping virtual list
  defeated document scroll; the first patch hardcoded a 64px offset that was already
  wrong). At R-036's introduction only 10 of ~29 top-level pages used `<q-page>`.
- **Apply:** the initial `MainLayout` inventory is now **fully converted** (FU-609
  closed 2026-08-11) — new pages comply from the start. `pages/settings/*` mount inside
  `SettingsShell`'s own scroller (not the layout) and stay plain divs (`SettingsShell`
  itself is now `<q-page :style-fn>` with a `!important` mobile override back to
  window-scroll); auth/setup/error pages render outside `q-page-container` where
  `<q-page>` can't resolve a layout, so they're correctly exempt. `StockItemDetailPage`
  is dual-host (also embedded in the Stock Overview peek) — it roots on `<component :is>`
  that resolves to `QPage` when routed and a plain `<div>` when embedded, so it stays
  layout-agnostic in the peek. Shapes chosen: **document-scroll** (bare `<q-page>`) for
  Dashboard, Meal-Plan Templates, Price History, Cook Mode, Reports, Shop-Now
  redirect, Stock Item detail; **app-shell** (`<q-page :style-fn>`) for the two runner
  shells (Meal Reconcile, Stocktake), SettingsShell + **Meal Plans**.
  **Meal Plans moved document-scroll → app-shell on 2026-08-29** (Unit 1 of
  `BRIEF_MEAL_PLANNER_RAIL_AND_SHELL.md`; an *application* of ADR-032, not a new
  ADR). It is the worked example of the failure this rule's "never hardcode the
  offset" clause exists for: its `.planner-sticky` side columns used
  `max-height: calc(100vh - 32px)` and accounted for neither the 64px header nor
  a rendered `OfflineBanner`, so both rails overhung the viewport by about a
  header's height. Taking the live `offset` removed it — measured after the
  conversion, all three pane bottoms land at 884px in a 900px viewport.
  A page converting to app-shell must also neutralise the inline height below
  its shell breakpoint (`height: auto !important`), since `:style-fn` is a prop
  and applies at every width — see `SettingsShell.vue` and now `MealPlansOverview.vue`.
- **Violation signal:** a `<div class="q-pa-md">` (or any bare root) as the top
  element of a `pages/*.vue` routed under `MainLayout`; a `calc(100vh − <literal>px)`
  / `height: calc(100dvh − 64px)` in a page or shell; a `position: sticky` footer on
  a page with no `<q-page>` ancestor.
- **Source:** ADR-032; FU-609 (from the 2026-08-04 Stock Overview scroll-model
  rebuild); `RecipesOverview` converted as the document-scroll worked example 2026-08-11;
  the remaining 11-page inventory converted + FU-609 closed 2026-08-11.

### R-037 — `MainLayout`'s router-view transition is a plain cross-fade, never `mode="out-in"`
- **Rule:** the `<router-view>` inside `MainLayout` wraps its pages in a plain
  cross-fade transition (both the leaving and entering page animate at once). It must
  **not** use `<transition mode="out-in">` (nor a `<transition-group>` equivalent) once
  every route root is a `<q-page>` (R-036). `mode="out-in"` fully unmounts the old page
  before mounting the new one; combined with a `<q-page>` root that registers itself with
  the parent `QLayout` on mount, the swap can wedge and paint a **blank screen on
  navigation**.
- **Why:** `out-in` looks like the "clean swap" default (no visual overlap), so it's the
  intuitive thing a future dev re-adds. But `<q-page>` participates in the layout's
  height/offset contract at mount time; sequencing the unmount fully before the mount
  leaves a frame where no page is registered with the layout, and under real timing the
  new page's `<q-page>` failed to resolve its container and rendered nothing. This is the
  blank-nav regression that landed the moment R-036 made every page root a `<q-page>`.
- **Apply:** `MainLayout`'s router-view uses the default simultaneous cross-fade. If a
  page-swap animation ever needs reworking, keep it modeless; never reach for `out-in` on
  a layout that hosts `<q-page>` roots.
- **Violation signal:** `mode="out-in"` on the `<router-view>` transition in `MainLayout`
  (or any layout whose routes root on `<q-page>`); a blank content area after a nav that
  only recovers on reload.
- **Source:** ADR-033; the blank-screen-on-nav regression fix that followed the R-036
  rollout (FU-619, 2026-08-11).

---

### R-038 — Settings that operate over shared/household data live install-wide (AppSetting), not per-user
- **Rule:** a setting whose effect is computed over **shared/household data** — data that
  isn't scoped to a `user_id` (stock, shopping lists, recipes, meal plans) — belongs on the
  install-wide `AppSetting` singleton, not as a `User` column. If two members holding
  different values for the setting would produce a **contradictory or whose-value-wins**
  result over that shared data, it is a household concept and must be install-wide. Read it
  via `/api/health` (a `*_policy` block) so every client sees one answer; edit it via a
  dedicated endpoint (admin `PATCH /app-settings`, or an any-member endpoint when the
  setting is kitchen-setup-grade shared config).
- **Why:** the app is single-household; its domain data is shared. A per-user *behavioural*
  setting layered over shared data means the outcome depends on **who triggered the
  computation** — e.g. a per-user grocery budget compared against a spend total summed
  across every shared shopping list: "is the household over budget?" resolved differently
  per member, and (worse) a per-user budget silently changed what got written into the
  shared meal plan. This has now bitten three times (`household_headcount`,
  `batch_features_enabled`, `budget_amount`/`budget_period`) — each was put on `User` only
  as a convenient home and had to be relocated.
- **Apply:** before adding a `User` column, ask "does this change what the system computes
  or writes over shared data?" If yes → `AppSetting` + `/api/health` read. Reserve `User`
  for genuine **presentation / view / per-device / identity** preferences (theme, fonts,
  voice, image-display, dashboard layout, email-digest timing) — those legitimately differ
  per person and suppress only that person's own view, never mutating shared state.
- **Violation signal:** a `User` column read inside a handler that sums/derives/writes over
  a shared entity (no `user_id` filter); a "policy" value fetched from `currentUser` rather
  than `/api/health`; two members able to hold conflicting values for something that has one
  physical truth (the household's budget, headcount, cook-style).
- **Source:** ADR-034; the grocery-budget relocation (2026-08-12). Extends R-003
  (state ownership) and mirrors R-030 (operational config on `AppSetting`).

---

### R-039 — Quasar `$q.dialog` buttons must set `noCaps`
- **Rule:** any `$q.dialog({...})` call that renders native `ok`/`cancel`
  buttons must pass each as an **object with `noCaps: true`**
  (`ok: { label: '…', noCaps: true }`, `cancel: { noCaps: true }`). Never use
  the `cancel: true` shorthand or a string-shorthand `ok: '…'` / `cancel: '…'`
  — those render the button **ALL-CAPS**, breaking the app's sentence-case
  voice (D-005). Component dialogs (`{ component }`) are exempt: they render
  their own `BaseButton`s, which are already `no-caps`.
- **Why:** `BaseButton` (the app's standard) hard-codes `no-caps`, but the
  `$q.dialog` **plugin** is a separate render path whose buttons default to
  uppercase. Every dialog author has to remember to opt out, one button at a
  time — the DR-3 audit found ~15 files that hadn't, shouting "CANCEL" / "SKIP"
  / "GOT IT".
- **Apply:** when writing a confirm/prompt dialog, spell out `ok`/`cancel` as
  objects with `noCaps: true`. Grep-tell for a violation: `cancel: true`,
  `ok: '`, `cancel: '` inside a `.dialog(` block.
- **Violation signal:** an uppercase button in a running dialog; a `cancel: true`
  or string-shorthand `ok`/`cancel` in a `$q.dialog` call.
- **Source:** ADR-035; the DR-3 dialog-casing sweep (2026-08-12). A `$q.dialog`
  wrapper that injects the default is the proper single-source enforcement,
  deferred as FU-623.

---

### R-040 — A side effect gated by a dialog is a *product* of the dialog's outcome, never eager-then-confirm
- **Rule:** when a mutation (PATCH/POST, navigation, delete) depends on a user's
  answer in a dialog, do **not** perform it before the dialog resolves and then
  let the dialog "adjust" it. Compute the action from the dialog's *result*:
  confirm ⇒ act, dismissal (Cancel button **and** Escape **and** backdrop) ⇒ do
  nothing. If the dialog has more than two outcomes (e.g. "confirm A" / "confirm
  B" / "abort"), a native two-button `$q.dialog` **cannot** express it —
  Cancel/Escape/backdrop all collapse into one `onCancel` — so use a
  `useDialogPluginComponent` component dialog with explicit buttons, resolved as
  a promise. Prefer returning a pure "plan" (the patch body, or `null` for
  abort) that the caller executes, so the decision→effect mapping is unit-
  testable without mounting.
- **Why:** eager-mutate-then-confirm silently commits on dismissal — the exact
  FU-578 #2 trap, where marking an item "open" PATCHed first and Escape/backdrop
  left it opened with no undo. It also contradicts the A3/D-008 dialog contract
  ("dismissal is always a cancel — never a commit"). Making the write a product
  of the outcome means there is one commit path and it fires only on an explicit
  yes.
- **Apply:** the shape is `const plan = await promptX(); if (!plan) return;
  await mutate(plan);`. Pin the mapping with a Vitest over the pure planner
  (abort ⇒ no write). Reference: `openToggle.ts` / `planOpenToggle` /
  `MarkOpenExpiryDialog.vue`.
- **Violation signal:** a store mutation before an `await $q.dialog(...)`; a
  dialog whose `onDismiss`/`onCancel` path leaves already-written state; a
  three-outcome decision forced through native `ok`/`cancel`.
- **Source:** ADR-036; DR-5 open-toggle trap (2026-08-12). Complements the D-008
  design rule; distinct from R-039 (casing).

---

### R-041 — A derived aggregate ships with its coverage; a partial total never renders bare
- **Rule:** any server-computed figure summed over a collection whose members
  can each fail to contribute (unpriced ingredient, unlinked food, unconvertible
  amount) must return **the count it was built from, the count it could have
  been built from, and — where the reasons differ — a per-reason breakdown**,
  in the same DTO as the number. The client renders the coverage **whenever it
  renders the number**, not only when something is missing. A member that can't
  be resolved is reported as a named gap; it is never approximated, defaulted to
  zero, or silently dropped. When the divisor of a per-unit figure (servings,
  headcount) is unknown, report the undivided total and say which basis it is —
  never divide by a guess.
- **Why:** a partial sum presented as a clean number is a confident lie, and the
  reader has no way to tell "from 12 of 12" from "from 2 of 12" — the two are
  different claims. Charter P3 (Honest) / P12 (No-invent) in code form. Both
  existing aggregates arrived at this shape independently (`estimated_cost` +
  `priced/total`; the nutrition rollup + `counted/total` + `uncounted`), which is
  what makes it a rule rather than a coincidence.
- **Apply:** shape the result dataclass as `value | None` + `counted` + `total`
  (+ `reasons: dict[str, int]` when failures have distinct causes, keyed by a
  closed set of ids per R-010 — copy for each id lives client-side). `None`, not
  `0`, when nothing contributed: zero is a measurement. Pin the failure taxonomy
  in tests — one case per reason. **If any surface then *acts* on the aggregate**
  — filters, sorts, ranks, or alerts on it — the server also ships a boolean
  saying whether coverage is good enough to act (`is_reliable`), derived from a
  threshold that exists in exactly one place. Displaying a thin figure with its
  coverage is honest; *hiding* a row on the strength of one is not, and a
  coverage threshold duplicated in the SPA is R-003 drift waiting to happen.
- **Violation signal:** an aggregate DTO carrying a bare number; a client
  rendering a total with the coverage hidden behind a tooltip or an
  `v-if="incomplete"`; a fallback constant standing in for a value the server
  couldn't resolve; a per-serving figure computed with an assumed serving count.
- **Source:** ADR-037; FU-635 chunk 6 recipe nutrition rollup (2026-08-14),
  generalising the C-4/DEC-5 cost-estimate shape. The act-on-it clause was added
  the same day by FU-637, when the cookbook's kcal filter needed to know which
  estimates it was allowed to judge.

---

### R-042 — `repository.add()` assigns the id; never capture an entity's id before adding it
- **Rule:** `SqlAlchemyRepository.add()` sets `entity.id = uuid4()` **unconditionally** —
  the repository owns identity, and whatever id an entity was constructed with is
  discarded. So any cross-reference between two new entities must be resolved
  **after** the parent has been added: add the parents, `save_changes()`, then read
  `parent.id` to build the children. When a pure/parsing layer must express the link
  before any repository exists, carry the **natural key** (the source's own id) and
  resolve it to a real `id` at persist time — never a pre-generated UUID.
- **Why:** the alternative fails *silently at the type level and loudly at the
  database*: the code reads perfectly, every id is a valid UUID, and the FK simply
  points at a row that was never stored. The nutrition dataset importer built 14,449
  `NutritionPortion` rows against parse-time food ids; every one dangled, and the
  import died on a foreign-key violation after downloading and parsing the whole
  dataset. Tests missed it for the subtlest possible reason — the fixtures read
  `food.id` *after* `repo.add(food)`, which is the correct order by accident, and the
  parser's own tests never touch a database.
- **Apply:** two-phase write — parents added and saved, then children built from the
  saved ids. Pin it with a test that drives the **real repository** and asserts each
  child resolves to its own parent (not merely that some rows landed). A pure parser
  should return a natural-key-linked DTO (e.g. `ParsedPortion(fdc_id=…)`), not a
  half-built entity carrying a fictional FK.
- **Violation signal:** an entity constructed with `id=uuid4()` whose id is then read
  into another entity before `add()`; a `for … repository.add(child)` loop in the same
  block as its parents; any FK value sourced from an object that hasn't been saved.
- **Source:** ADR-038; the FU-639 nutrition-import investigation (2026-08-15). Applies
  to every plain-UUID FK — which, per R-032, is most of them.

---

### R-043 — An inferred match is offered, never applied; its confidence is the server's and travels with it
- **Rule:** When Dora guesses which entity another one refers to — a stock item's
  nutrition food, an imported ingredient's stock item, a scanned barcode's product —
  the guess is a **suggestion object** returned on a read, never a write. It carries
  the score that produced it *and* the pre-computed band the UI renders
  (`confidence` + `is_strong`), so the threshold exists once, on the server. Any bulk
  "accept them all" verb takes only the top band, and **recomputes** the matches
  itself rather than accepting a list of links from the client. Every surface that
  shows a suggestion also offers the two other honest answers: search it yourself,
  and never ask about this one again (a persisted opt-out, always reversible).
- **Why:** matching is where a plausible-looking wrong answer is most expensive and
  least visible — a mis-linked food quietly poisons every recipe rollup and per-day
  calorie total downstream, and nothing on screen ever looks broken. The charter's
  P12 No-invent is not "don't guess"; it's "don't *save* a guess". Keeping the
  threshold server-side matters for the same reason as any other domain constant
  (R-003): the band decides what a one-click bulk action is allowed to touch, so a
  client that re-derived it could widen the blast radius by drifting.
- **Apply:** compute in a dedicated module with a readable formula, not a fuzzy-match
  library (R-019) — the reason a row scored 0.62 has to be explainable to whoever is
  deciding whether to trust it. Set the floor to reject rather than offer a weak
  match: most of a pantry is things a food catalogue *should* answer nothing for, and
  a suggestion feed that cries wolf gets ignored wholesale. Pin the false positives
  in tests as hard as the true positives.
- **Violation signal:** a matcher that writes an FK; a threshold constant in a `.vue`
  or `.ts` file; a bulk-accept endpoint whose request body names the links to make;
  a suggestion surface with no "don't ask again"; a UI that renders a guess
  indistinguishably from a confirmed value.
- **Source:** ADR-039; the nutrition auto-matcher (2026-08-15). The existing
  precedents it generalises are the recipe-importer bulk-linker and the OFF barcode
  resolve path.

---

### R-044 — Read the app setting before you load the entity; a mid-handler commit expires `noload` relationships to None
- **Rule:** In a read handler, resolve every `AppSetting` / config value **before**
  loading the entities you are about to project into a DTO. `get_or_create_app_setting`
  can commit, a commit expires every object in the SQLAlchemy session, and a
  relationship mapped `lazy="noload"` (which is most of ours, per R-032/ADR-028)
  re-reads as **None** instead of reloading.
- **Why:** the failure is silent and total. Adding a mode check partway down
  `get_stock_item_detail` — a change that reads as obviously safe — blanked
  `stock_level` and `stock_location` on *every* stock-item detail response, including
  ones that had nothing to do with the new feature. Nothing raised; the DTO just went
  quietly hollow. It was caught only because `test_patch_semantics` compares a whole
  before/after DTO rather than the field under test, which is the argument for that
  test shape.
- **Apply:** hoist the setting read to the top of `handle()` into a local, and use the
  local downstream. If a lazily-evaluated gate is genuinely wanted, say so in a
  comment naming this rule — the laziness is the trap, not the cost.
- **Violation signal:** `get_or_create_app_setting(...)`, or any `save_changes()`,
  appearing *after* an entity load inside a read/projection handler; a DTO field that
  is None in production but populated in a unit test that never commits.
- **Source:** ADR-040; the nutrition auto-matcher (2026-08-15). Sibling of ADR-028 —
  same `noload` landmine, reached by a different route.

---

### R-045 — Never reach an authenticated endpoint from `<img src>` or `window.open`; fetch through the client and hand the browser a blob
- **Rule:** Every request to `/api/*` goes through `AxiosHttpClient`. If the result
  is a PNG/HTML/CSV rather than JSON, use `getBlob` (or `fetch` with
  `credentials: 'include'`), then give the browser an object URL. A bare
  `<img :src="apiUrl">`, `window.open(apiUrl)` or `<a :href="apiUrl" download>` is a
  violation.
- **Why:** those three are unauthenticated by construction — they carry the session
  cookie only if the *browser* volunteers it, which depends on SameSite, on the SPA
  and the API being same-site, and on the platform. All three assumptions hold on a
  dev box and fail in real deployments: a split `app.` / `api.` host makes the
  subresource cross-site (Lax declines), and the Capacitor shell serves the SPA from
  an origin that is never the API's. The failure is silent and looks like a broken
  feature, not an auth problem — the stock-item QR dialog rendered empty and "Print
  one" died, with nothing in the console naming a session.
- **Apply:** `http.getBlob(path)` → `URL.createObjectURL` → revoke on a timer. If the
  fetched document itself references other API resources, the **server** must inline
  them (data: URI), because relative URLs cannot resolve from a blob origin.
- **Violation signal:** a template binding or `window.open` whose value is built from
  `resolveBaseURL()` / `getBackendBaseUrl()`.
- **Source:** ADR-041; the QR-label fix (2026-08-16).

### R-046 — Open the window inside the click; navigate it after the await
- **Rule:** `window.open` runs **synchronously in the event handler's own call
  stack**, before any `await`. Hold the returned handle, fetch, then
  `handle.location.replace(objectUrl)`. Never `await` first and open second.
- **Why:** every browser blocks a `window.open` it can't attribute to a user
  gesture, and the gesture does not survive a network round-trip. Mobile Safari
  and Chrome-on-Android block it unconditionally — which is why the reported
  symptom was "I *tap* Print one and get an error" while the same button
  behaved on a desktop dev box. This is the exact trap R-045 walks you into: the
  fix for "don't `window.open` an API URL" is to fetch first, and fetching first
  is what breaks the open.
- **Apply:** open with `_blank` and **not** `noopener` — with `noopener` the call
  returns `null` by spec and there is no handle to navigate; sever `win.opener`
  by hand instead. Write a one-line placeholder into the fresh tab so a slow
  fetch doesn't read as a dead window, `location.replace` (not `href`) so Back
  doesn't return to the placeholder, and `close()` the tab if the fetch throws.
  A null return means the browser blocked it: say so in the UI — "allow pop-ups"
  is a different instruction from "something went wrong".
- **Violation signal:** `window.open` appearing after an `await` in the same
  function, or a `void someAsyncOpen()` call with no `catch`.
- **Source:** ADR-042; the QR "Print one" fix (2026-08-17), FU-648.

### R-047 — An HTTP call that bypasses `AxiosHttpClient` must re-attach what the interceptor would have
- **Rule:** any mutating request to `/api/*` issued with raw `fetch`, bare
  `axios`, `navigator.sendBeacon` or anything else that isn't an
  `AxiosHttpClient` instance **must** spread
  [`csrfHeader()`](../../web_app/src/services/api/axiosHttpClient.ts) and set
  `withCredentials` / `credentials: 'include'`. If the CSRF cookie isn't
  readable yet, **defer the call** — do not send it and treat the 403 as a
  permanent failure.
- **Why:** the FU-197 double-submit defence 403s every mutating call whose
  `X-CSRF-Token` header doesn't match the `dora_csrf` cookie, and the header is
  attached by an *interceptor on the client instance*. Bypass the instance and
  you silently lose it. This has now bitten twice: FU-571 swept the raw-`fetch`
  callers (uploads, import/backup, client logs, TTS), and the offline queue's
  replay — bare `axios`, added before that sweep — was missed and 403'd **every**
  drain from the day it shipped. Worse, the failure is invisible in tests
  (axios is mocked, so CSRF is never enforced) and self-concealing at runtime
  (403 is a non-network error, so the queue classified it as a conflict and
  discarded it).
- **Apply:** prefer the client. When you genuinely can't use it, put the call
  next to the others in the FU-571 comment block so the list stays a real
  inventory, and pin it with a test that asserts the header is present — a
  mocked transport will never catch its absence on its own.
- **Violation signal:** `axios.request(` / `fetch(` with a `method` of POST,
  PATCH, PUT or DELETE and no `csrfHeader()` in the same object literal.
- **Source:** ADR-043; the offline-replay fix (2026-08-17), following FU-571.

---

### R-048 — A control that sits among framework primitives IS one, not a lookalike
- **Rule:** When a bespoke control has to live in a row/group alongside a
  framework primitive (`q-field`/`q-select`/`q-input` in a filter row, `q-item`s
  in a list, `q-tab`s in a tab bar), build it **on that primitive** and put the
  bespoke part in the primitive's own slots. Do **not** build it from a different
  primitive and chase visual parity with CSS. If several pages need the same
  composition, the primitive-plus-slots wrapper is a shared base component and
  the pages consume it — the row's *layout* (scroll behaviour, track widths,
  control height) is likewise one shared component, not a class copied per page.
- **Why:** Visual parity by CSS is unbounded and silently incomplete. A
  `q-field` has a resting border, a focused border on a *separate* `::after`
  layer, a floating label, a stacked-label state, a right-edge append zone, a
  clear affordance, a disabled state, and a dark-theme variant. A
  `q-btn-dropdown` styled to look like one reproduces whichever of those the
  author happened to notice, and the rest surface later as separate bug reports.
  The cookbook filter row proved this over **three rounds of the same feedback**:
  round 1 said the sizes differed (patched with a page-level height/width
  override), round 2 said the colours and focus behaviour differed and the caret
  was in the wrong place. The page's own comment had already named the cause —
  "a button pretending to be a field" — while continuing to patch the symptoms.
  Rebuilding the trigger *as* a `q-field` fixed colour, focus, caret glyph, caret
  position and clear affordance in one change, and deleted the override CSS
  instead of adding to it.
- **Apply:**
  - Reach for the primitive first. `q-field` (the generic one) exists precisely
    to host a custom `#control`; `q-select` is `q-field` plus a menu.
  - Take framework values from the framework: the caret glyph is
    `$q.iconSet.arrow.dropdown`, the clear glyph is `$q.iconSet.field.clear` —
    not a similar-looking entry from our own `ICONS` map.
  - When a state can't be delegated (QField exposes `focused` only as slot
    scope, never as a prop), paint **the layer the framework paints** — measure
    it live rather than inventing a treatment.
  - Extract the row/group layout too. `FilterRow` owns the sideways-scroll, the
    hidden scrollbar, the control height and the width tracks; `RecipesOverview`
    and `StockOverview` had each grown a copy, which is how the two rows drifted
    to different heights in the first place.
- **Violation signal:**
  - A page style block contains `:deep()` overrides that force one component to
    match the height, width, border or label colour of its neighbours.
  - A comment in the codebase describes a control as "pretending to be" or
    "matching" another primitive.
  - The same feedback about one row arrives more than once, each time about a
    different visual attribute.
  - Two pages hold near-identical layout CSS for the same kind of control row.
- **Carve-outs (must be commented, naming the rule):**
  - A control that is genuinely a *button* and reads as one beside fields
    (an icon-only action at the end of a row) stays a button — the rule is about
    controls that are meant to read as peers of the primitive, not about every
    element that happens to be nearby.
- **Source:** ADR-044; cookbook filter row, 2026-08-19 (third round of the same
  report). Fix was `components/filters/BaseFilterField.vue` +
  `components/filters/FilterRow.vue`; ~4.5kB of page-level override CSS deleted
  across two pages.

### R-049 — An always-editable surface owns its commit
- **Rule:** A surface that edits values in place (no read/edit mode) must
  provide **all four** of: a dirty flag; an explicit **Save** the user presses,
  plus a way to discard; a **navigation and unload guard** while dirty; and
  cleanup, on unmount, of every timer or listener it started. **Debounced
  autosave is banned** on such a surface. Never re-hydrate the edit model from
  the server except on a load or on a save the user asked for — a background
  refresh landing mid-edit rebinds open editors to orphaned objects and drops
  the edit with no error. Validation that can refuse the save must also mark the
  **specific row or field** responsible, not just report a count.
- **Why:** all four came off one page (`RecipeDetailNext.vue`, ADR-045), where
  the missing pieces produced three distinct silent-data-loss paths. Autosave
  looks like the user-friendly option and is the opposite: it makes every save
  failure a notification the user may not be looking at, and every unrelated
  edit hostage to the one incomplete row. Pairs with **D-019** — that rule says
  don't inert the fields while saving; this one says the save must therefore be
  something the user chose.

### R-050 — Never sequence app state behind a paint callback
- **Rule:** `requestAnimationFrame` may only *drive* an animation, never gate a
  state change, a class write, a cleanup, or an unmount. Anything that must
  still happen when the tab is backgrounded, throttled, or never composited goes
  on `nextTick` / `setTimeout` / an event. The same applies to waiting on
  `transitionend` / `animationend` as the *only* path out of a state — pair it
  with a timeout, or drive the unmount from the timer and let the transition be
  decoration. A rule of thumb: if the code would leave the user stuck, or leave a
  class stuck on, when no frame is ever painted, it's wrong.
- **Why:** it has now bitten twice from opposite directions. The boot splash was
  dismissed by a `<Transition>` whose `done` hook assumed paint, so a throttled
  tab wedged full-screen behind a z-9000 overlay (DR-8, FU-578 #23/26). Then
  DR-15's micro-feedback composable scheduled its class write inside `rAF`,
  where the failure is silent instead of fatal — the feedback simply never
  happens and nothing says so. Fatal or silent, the cause is the same
  assumption, and rAF genuinely does not fire in a backgrounded tab or in the
  verify pane. Extends D-007/B10, which state the same thing for *dismissal* of
  a blocking surface; this rule generalises it to all state.

### R-051 — A bulk endpoint loops the single-item handler; it removes round-trips, not rules
- **Rule:** when a client is looping an API call over a selection, the fix is a
  bulk endpoint — and that endpoint **calls the existing single-item handler**
  once per item, in-process, rather than re-deriving the operation as a set
  query. Write the set query only when the operation is a bare field assignment
  with **no** history rows, timestamps, derived events or hooks. Never duplicate
  a rule that already has an owner just to make a batch faster (this is R-003
  applied to the bulk case). Where undoing the batch needs to know what changed,
  the endpoint **echoes that state back**; the client does not snapshot it.
  Cap the id list explicitly (`Field(min_length=1, max_length=N)`), report
  per-item misses as data (`missing_ids` / `failed_ids`) rather than failing the
  batch, and fail the whole request only for an error that is the same answer for
  every item (an unknown target list, an unknown level).
- **Why:** the slowness a user reports is **latency** — N sequential HTTP
  round-trips, each with its own await — not the database work, which is
  invisible to them. Collapsing the round-trips fixes what was reported; rewriting
  the rules as set queries risks the semantics for a win nobody asked for. Bulk
  waste was the worst case: three requests per item, so a 20-item selection sent
  60 serial requests, and the "obvious" set-shaped rewrite would have needed its
  own copy of expiry-event classification, level-change history, consumption
  recording and the auto-add hook.
- **Violation signal:**
  - A `for` loop in a `.vue` file or composable with an `await api.…` inside it.
  - A bulk handler that reads or writes columns the single-item handler manages
    (a timestamp, a history table, an event row).
  - A bulk endpoint that returns only a count when its caller needs to undo it.
- **Carve-outs (must be commented, naming the rule):**
  - A pure set write with no side effects — `bulk-move` (one FK), `bulk-tick`
    (one boolean), `stocktake/bulk-check` (a single `UPDATE … WHERE id IN`).
  - A caller whose per-item command is richer than the bulk request model keeps
    looping until the model is widened; do **not** branch inside the caller on
    "is this batch simple enough" (R-019).
- **Source:** ADR-047; stock-overview bulk bar, 2026-08-22. Six endpoints added
  (`stock-items/bulk-move`, `stock-items/bulk-set-level`, `waste/events/bulk`,
  `waste/events/bulk-delete`, `shopping-lists/<id>/lines/bulk-add`,
  `shopping-lists/<id>/lines/bulk-remove-by-stock-item`); commits-per-item
  remains open as FU-713.

### R-052 — Offline is read-only: cache reads, never buffer writes
- **Rule:** when the server is unreachable, the client may serve **cached reads**
  and must **refuse writes**. A failed mutation surfaces as a failure — the
  optimistic UI rolls back and the user is told — and is never stored for later
  replay. Do not add a mutation queue, a pending-changes ledger, client-generated
  entity ids for offline creates, or client-side conflict resolution. Copy must
  not promise syncing: the banner says what is true ("you can look around, but
  not make changes") and nothing more. A cache that holds user content is
  **evicted on sign-out and on 401**, because it is keyed by URL and knows
  nothing about who it belonged to.
- **Why:** the queue this replaced was 372 lines plus 649 lines of tests serving
  **three** call sites, and it carried hazards none of those three needed:
  replay was at-least-once with no server-side idempotency (the
  `X-Request-Id: replay-…` header was sent and ignored), the conflict pile was
  invisible to the user, and it had already failed silently once — `replayOnce`
  used bare axios without the CSRF header, so every drain 403'd, was
  misclassified as non-network, and burned the queue into conflicts that nothing
  surfaced. Reads are a different risk class entirely: no conflict semantics, and
  the worst case is staleness. So keep the half with no downside and delete the
  half that can lose data. This is also the Anti-creep tiebreak applied to a real
  case — the honest small feature beat the impressive one.
- **Violation signal:**
  - A `catch` that swallows a network error and reports success to the UI.
  - Any localStorage/IndexedDB key holding pending mutations, deltas or conflicts.
  - Copy containing "will sync", "queued", or "when you're back online".
  - A retry/backoff policy applied to POST/PATCH/PUT/DELETE (a write that may
    already have landed must not be replayed blind — see `axiosHttpClient`).
- **Carve-outs (must be commented, naming the rule):**
  - **Read caching is explicitly in scope**, not a carve-out: the `NetworkFirst`
    rule over `/api/**` GETs in `quasar.config.ts` is the offline story.
  - Genuinely idempotent, user-invisible telemetry (client logs) may retry.
  - If a future surface truly needs offline writes, it needs server-side
    idempotency keys **first**, plus its own ADR reversing this one — not a
    quiet queue reintroduced beside it.
- **Source:** owner decision 2026-08-23, after a measurement of the existing
  queue (see ADR-048). Removed `useOfflineQueue.ts`, both its spec files, the
  three `tryWithQueue` call sites and the banner's queued-count; added
  `apiResponseCache.clearApiResponseCache()` on logout/401. Reversed FU-718
  ("widen the offline queue"), which had been logged in the opposite direction
  before the code was counted.

### R-053 — A derived display value ships with its provenance, and is resolved once, server-side
- **Rule:** when a displayed value is chosen by a **ladder** (try A, else B, else
  C — a "prefill", "estimate", "resolved store", "effective date", "display
  name"), the server resolves it and returns **both the value and a field naming
  which rung produced it**. The client renders; it does not re-run the ladder,
  and it does not infer the source by testing which input happens to be non-null.
  Aggregates over those values are server-owned too (R-003) — a client that sums
  a ladder it did not compute cannot be trusted to agree with the server that did.
- **Why:** ladders are domain rules, so a client copy is a second definition that
  drifts (R-003). Two concrete costs, both real here. First, the client's copy of
  the shopping-line ladder was `actual → offer`, which **hard-required product
  data**: a user who had never linked a product saw `$0.00` totals even though
  Dora had recorded exactly what they last paid — the rule's *inputs* silently
  became a feature gate. Second, without a source field the UI cannot be honest:
  "$5.50" and "~$5.50, what you last paid" are different claims, and a client
  reduced to guessing from `actual_unit_price != null` will get it wrong the
  moment a rung is inserted. Provenance is also what lets a *later* rung be added
  without touching a single call site.
- **Violation signal:**
  - A client function whose body is an `if/else-if` chain over DTO fields
    reproducing a precedence the server already applied.
  - A DTO exposing every rung's raw input but no resolved value (the client is
    being asked to decide), or a resolved value with no source (the UI is being
    asked to guess).
  - UI copy that states a number's origin based on a null-check rather than a
    field the server set.
- **Carve-outs (must be commented, naming the rule):**
  - **Pure display math on an already-resolved value stays on the client** —
    `estimated_unit_price × quantity` is formatting, not a domain rule
    (state-ownership Type C). The line is: choosing *which* number, server;
    multiplying or formatting *that* number, client.
- **Established by:** the shopping-list money ladder
  (`actual → last paid → offer`) and store ladder
  (`purchased → usual → last-paid's store → offer's store`), 2026-08-23. Note the
  two ladders order intent and history **oppositely** on purpose — history beats
  intent for money ("what you really paid" outranks an advertised price), intent
  beats history for store ("where I plan to buy" outranks where I last did) —
  which is exactly the kind of decision that cannot survive being re-derived in a
  second place. See ADR-049.

### R-054 — A lifecycle phase that changes what the user *does* gets its own composition, not the same surface with controls disabled
- **Rule:** when an entity has phases (draft / shopping / done, planning / cooking,
  review / walk / sweep) and the user's **task** differs per phase, render a
  different component per phase. Do not render one all-purpose surface and reach
  for `:disable`, `v-if` on individual controls, or a size/colour swap to
  approximate the others. A phase that only changes *policy* (who may edit) and
  not *task* is not covered by this rule — that is what `:disable` is for.
- **Why:** disabling is a statement about permission; a phase change is a statement
  about purpose. Conflating them produces the two defects this rule was written
  from. A "shopping mode" that only enlarged the checkbox and added a footer was a
  **costume**: eleven interactive zones per row survived into an aisle where the
  user has one hand and one intention. And a finished list rendered as the plan
  face with everything greyed out showed a screen full of inert steppers, drag
  handles and delete buttons — it read as broken, and it *hid a real feature*,
  because the data for a proper receipt (what was bought, what it cost, where
  from, what was skipped) was already on the DTO and simply never rendered. The
  cost of the wrong shape is not just clutter: it is that nobody notices the
  missing surface, because something is already there.
- **Violation signal:**
  - `:disable="status === 'x'"` appearing on more than a handful of controls in
    one template, or bound to the same status expression throughout.
  - A phase branch that changes only `size`, `color` or a class, while the set of
    affordances stays identical.
  - A read-only phase that renders editing chrome at all.
  - One component whose template length is dominated by phase branching.
- **Carve-outs (must be commented, naming the rule):**
  - **Shared, phase-agnostic machinery stays shared.** Sectioning, the money
    ladder, the mutations and the page chrome are the *same* in every face; only
    the composition differs. Duplicating those per face trades one problem for a
    worse one.
  - **A destructive or historical phase may still expose a narrow edit mode** —
    but as an explicit, announced mode (an "Amend" toggle with a banner saying
    what it does *not* do), never as the default state.
- **Established by:** the shopping-list three-face redesign (plan / run / receipt),
  2026-08-23. See ADR-050.

### R-055 — The edit affordance belongs to a block, not to every field
- **Rule:** when a region of a page holds several editable values (a masthead's
  identity + facts, a list of ingredients), give the **region** one explicit
  read↔edit switch. Do not hang a summon-a-field affordance
  (`q-popup-edit`/click-to-reveal) on each value. The rule is about *editing*
  chrome specifically; a single value that is genuinely the only editable thing
  in its region may still edit in place.
- **Why:** a summoned field costs two interactions before the control does its
  job — the first click builds the input, the second opens it — which is
  measurable on every dropdown and unavoidable on touch, where there is no hover
  to preview the target. It also sizes each control to its own content, so an
  empty field renders as a sliver and a full one as a slab, and neighbouring
  values never line up. A block that flips whole keeps one grid across both
  states: the controls are the same width as each other in edit, and the values
  sit where the inputs were.
- **What still holds:** the read face must read as a *document*, not a wall of
  inputs (that is what the block switch buys), and the commit stays explicit
  (D-019 — inline editing is fine, silent autosave is not).
- **The prose carve-out was retired 2026-08-27.** It read "an editor over the
  paragraph you are reading is the right shape, and the recipe method keeps
  it", and it was written when the method's editor was a `q-popup-edit`. What
  actually shipped behind it was a *modal*, which is neither of the two shapes
  this rule is about — and the owner rejected it on sight ("adopt the header
  edit style, where it is read-only entirely until you press the edit button,
  and then it swaps in-place"). The method is now a block switch like the rest
  (`RecipeStructuredMethod.vue` renders both faces off one `editing` prop, so
  the geometry cannot drift between them). The rule has no carve-outs.
- **Corollary — one component, both faces.** When a region flips, the read face
  and the edit face belong in the *same* component off an `editing` prop, not in
  a viewer plus a separate editor. Two components drift: the numbering, the
  indent and the spacing get maintained twice and the block visibly changes
  character mid-edit, which is the thing the switch existed to prevent.
- **Violation signal:** two or more `q-popup-edit`s in one section; a select that
  needs a click to appear before it can be clicked to open; a row of values whose
  widths change as their content does.
- **Established by:** the recipe-page feedback batch, 2026-08-23. See ADR-051
  and ADR-052, and D-015 in the design guide (whose retired clause this
  partially restores, at block rather than page granularity).
- **⚠️ The ingredient half of ADR-051 was lost in the 2026-08-24 merge and
  restored 2026-08-27.** The surviving page kept its editing chrome permanently
  on — tap-a-row-to-edit, reorder arrows and a delete button on every row, in
  read mode — and the owner reported it again from scratch three days later
  ("I want the pencil edit style for ingredients, same as header and method").
  Worth knowing when reading ADR-051: it describes a decision that was made,
  then silently un-made by a merge that had no way to know it was choosing.
- **Reference implementation, after the 2026-08-24 merge.** The 08-23 block-pencil
  build and a second agent's 08-24 rebuild of `RecipeDetailNext.vue` were written
  in parallel on two machines. The merge kept the 08-24 page (browser-verified,
  and the only one carrying the cost modal, method editor and shopping-list
  awareness) and then **re-applied this rule on top of it**: the masthead is one
  pencil over a read face and a `minmax(160px, 1fr)` field grid, and the
  ingredient row opens one editor for the whole row instead of the quantity and
  the name each owning a target. The page went from **25 `q-popup-edit`s to 2**,
  both of which are the rule's own carve-outs — a section's name (the only
  editable thing in its region) and the step text (prose).


### R-056 — One regional convention, one setting, one axis
- **Rule:** an install-wide *convention* — how money is written, which units are
  measured in, which day counts as today — gets **one** setting on **one** axis,
  published to every session on `/api/health`, with the vocabulary it implies
  derived from it server-side. Do not add a second setting that answers a
  narrower version of the same question, and do not restate the mapping from the
  setting to its consequences on the client: the client filters a generated
  mirror of the server's table, it does not carry its own copy of which unit
  belongs to which system.
- **Why:** two settings for one fact do not stay in agreement, and the failure is
  silent in the worst direction — the user changes the one they can see and the
  other keeps quietly deciding something. Dora had exactly this: an
  `unit_pricing_locale` on an "AU"/"US" axis, which decided the denominator a
  shelf price was quoted in, was never surfaced in the UI at all. The moment a
  units picker arrived, "which units do we use?" and "which denominator do we
  price in?" were plainly the same question, and keeping both would have let an
  install offer grams in every dropdown while quoting `/lb` on the price beside
  them.
- **The axis has to be able to express the real cases.** "AU or US" could not
  tell the UK apart from the US, because both use pounds and ounces and only one
  prices by the quart. The replacement is metric / imperial / US customary, where
  imperial is deliberately *metric plus* imperial — which is what a UK shelf
  actually looks like. Choosing an axis that collapses two real answers into one
  is the same defect as holding the fact twice, arriving earlier.
- **Where it goes:** `/api/health`, not the admin `/app-settings` payload, when
  every session needs it and only admins can read settings. Currency and locale
  already worked this way; the measurement system joined them.
- **Violation signal:** two settings whose values are in bijection; a client-side
  `if (system === 'us')` that decides which units, colours, or formats to show;
  a setting with no UI (that is usually the second copy, not the first).
- **Established by:** the units-config feedback item, 2026-08-27. See ADR-053.


### R-057 — Replacing a server-orchestrated action relocates its reporting; a guarantee is a migration item, not a casualty
- **Rule:** when a one-shot server endpoint is replaced by a client-composed flow
  over smaller endpoints, inventory what the old **response** told the user and
  give every one of those facts a new home *in the same change*. If a fact can't
  ride on any of the new calls, extend one of them to carry it. "The new flow
  doesn't have anywhere to put that" is a reason to make somewhere, not a reason
  to drop it.
- **Why:** a guarantee that lives in a response body is invisible in a diff that
  deletes the call. Nothing fails, no test goes red, and the loss surfaces months
  later as a bug report about something the app used to say. Dora's meal-plan
  "generate the week's list" endpoint returned `unlinked_skipped` — the recipe
  ingredients that were never matched to a pantry item and therefore *silently
  didn't make it onto your list* (FU-505, itself raised because they were being
  dropped). Swapping that button for the shared picker would have deleted the
  only place the app ever mentioned them.
- **Apply:** the fix is usually a small server change, not client cleverness —
  the old endpoint knew this because it had the domain in hand. Here the
  ingredient aggregate became an envelope (`{items, unlinked}`) so the picker
  could name what it couldn't take, which is strictly better than the dialog it
  replaced: it says so *before* you commit rather than after.
- **Also inventory:** provenance the server stamped (`added_via`), names it
  generated (an auto-named list), and navigation the response implied. Each is
  either reproduced, deliberately dropped **with the owner's agreement**, or
  logged. Two of those three were reproduced here; the `added_via` chip was
  dropped on an explicit owner call, which is the shape this rule expects — a
  decision, not an oversight.
- **Violation signal:** a diff that deletes an API call and adds UI, with no
  change to the endpoints the new UI calls; a response field that becomes unused
  in the same commit as a new flow.
- **Established by:** the meal-plan add-to-list unification, 2026-08-27. See ADR-054.

### R-058 — A feature that *reasons* in a gated domain is gated by that domain, not stripped of it
- **Rule:** when a surface's reasoning depends on a feature-flagged domain
  (money, nutrition, products, scanning), decide **prerequisite or independent**
  — and gate the whole surface when it's a prerequisite. Do not ship the surface
  with the gated domain's *output* suppressed while its *input* still moves the
  answer. Apply the test: with the flag off, is what remains (a) still correct,
  and (b) not already said better by an adjacent surface? Both must hold, or the
  feature is a prerequisite.
- **Why:** partial gating fails silently and in the direction nobody develops in.
  Dora's buy verdict is the case: the price axis reasons entirely in money, the
  `wait` direction is only reachable from a price signal, and price modulates
  `strength`. With money off, the card still rendered — dollar glyph, "$3.85 last
  shop", "N price samples" — and, worse, still *ranked* items using price data the
  household had opted out of. Every developer runs with money on, so nothing looks
  wrong; only the money-off install sees it, and it can't tell the numbers are
  weighted by something it disabled. Suppressing just the visible dollar strings
  would have left that half intact and looked like a fix.
- **Apply:** gate at three seams, not one — the **endpoint** refuses (403 with a
  named reason), the **render** composable folds the flag into its enabled
  computed, and the **settings toggle** disables with a caption naming the
  prerequisite. The endpoint gate is what makes it a real gate rather than a
  render trick; the toggle caption is what makes the dependency discoverable
  instead of a feature that mysteriously vanished. Preserve the user's own
  preference underneath — the prerequisite returning must restore their setting,
  not reset it.
- **Prefer disabled-with-caption over hidden** for the dependent toggle, per the
  `emailSmtpConfigured` precedent on Notifications: a control that vanishes leaves
  the user unable to discover why. (This is the R-029 carve-out — a disabled
  control is legitimate on the settings screen that *owns* the preference, and
  only there. Other surfaces `v-if`.)
- **Violation signal:** a component whose gated-domain flag appears nowhere in it
  but whose strings contain that domain's vocabulary; a composer that computes a
  score from an axis the install disabled; a "hide the price line" commit that
  doesn't touch the ranking.
- **Established by:** the buy-verdict money gate, 2026-08-27. See ADR-055.

### R-059 — A transcribed external standard cites its primary source and is pinned by that source's own worked examples
- **Rule:** when code reproduces a published external standard — a scoring
  algorithm, a threshold table, a classification scheme — it must (a) name the
  document, **version**, and table it came from, in place; (b) be transcribed
  from the **primary** source, never a secondary write-up; and (c) be pinned by
  test cases taken from the source's *own* worked examples, not from expectations
  computed by hand or by the implementation being tested. Where the standard has
  revisions, state which revision this is and list the specific values where the
  revisions disagree.
- **Why:** a mis-typed threshold does not crash, does not fail review, and does
  not look wrong on screen — it just quietly returns a defensible-looking answer
  that is not the standard's answer. Nutri-Score is the case. A widely-cited
  third-party methodology page gives the grade-A cut-off as `< 1`; another gives
  `< 0`. Both are "correct" — for different generations of the algorithm, which
  the pages do not say. The official workbook computes the 2017 and 2023 versions
  side by side **on the same sheet**, so even the primary source will hand you the
  wrong number if you read the wrong columns, which is exactly what happened once
  during this build before the worked examples caught it. Hand-computed test
  expectations cannot catch this class of error, because they are derived from the
  same misreading as the code.
- **Apply:** obtain the primary document (and its calculator/tool, if one is
  published — a tool encodes tie-breaks and carve-outs that prose omits, and it is
  what the industry actually runs). Cite the table beside each constant. Lift the
  source's worked examples verbatim into tests, inputs *and* outputs. Add one test
  that asserts the values where revisions differ, so a future edit that reaches for
  the wrong generation fails loudly. Where the standard cannot be honestly applied
  to Dora's data, say so in the module docstring with the reason and the direction
  of the error — never silently approximate.
- **Violation signal:** a threshold table with no citation; a test whose expected
  value was produced by running the function; a module that reproduces a national
  or international standard without naming its version; a "cleanup" commit that
  smooths an irregular published series into a regular one.
- **Established by:** the Nutri-Score 2023 transcription, 2026-08-27, generalising
  the practice the Health Star Rating module set informally. See ADR-056.

### R-060 — Only reference design tokens that `tokens.scss` actually declares
- **Rule:** every `var(--token)` in a component must name a custom property
  declared in `css/tokens.scss` (or `themes.scss` / `motion.scss`). Do not invent
  a token name that "looks like" the scale — the spacing scale is
  `--space-1..--space-12`, not `--space-sm`; the card surface is
  `--surface-component`, not `--surface-card`. If a genuinely new token is needed,
  add it to `tokens.scss` (both themes) in the same change. A bare
  `var(--maybe-defined)` with no fallback is not permitted; where a fallback is
  the honest intent, write it (`var(--x, 8px)`).
- **Why:** an undefined custom property with no fallback makes the **whole
  declaration invalid at computed-value time**, so the property silently falls
  back to its initial value. It does not warn, does not fail the build, does not
  fail lint, and does not fail `vue-tsc`. `gap: var(--space-sm)` is not "roughly
  8px" — it is **zero**, and it looks exactly like a layout you never wrote
  spacing for. Cook mode's header was reported three separate times as "squished",
  "no margin from other elements" and "looks like a 5 year old did it" across two
  feedback rounds; two rounds of layout work went into it before anyone checked
  whether the six gap declarations in the file resolved to anything at all. They
  did not. The layout was fine; the tokens were fiction.
- **Apply:** when writing a token you have not personally used before,
  `grep -- '--token-name:' web_app/src/css/` before using it. When touching a file
  that already uses one, check it the same way — this class of bug is invisible in
  review because the *code* reads correctly. Colour tokens fail more quietly still
  (an invalid `background` just inherits), so they are worth the same check.
- **Violation signal:** a `var(--…)` whose name appears nowhere in `css/`; a
  spacing/surface/colour token in a diff that matches no entry in the scale; a
  "the gap isn't applying and I can't see why" debugging session.
- **Established by:** the cook-mode header rebuild, 2026-08-28. See ADR-057.

### R-061 — A stored price is not evidence a purchase happened
- **Rule:** any aggregate that means *money actually spent* — a budget, a
  spend report, purchase history, a price sample, a value-at-risk figure — must
  filter on the flag that records **the purchase event** (`ShoppingListLine.
  is_ticked`, plus `deferred_by_budget` for lines the trim optimiser set aside).
  Never infer "this was bought" from the mere presence of a price. Where a
  feature needs "what this line actually cost, if anything", it goes through a
  named chokepoint in `_line_price.py` that encodes the rule once — not an
  inline `if price is not None` in each caller.
- **Why:** `picked_offer_price` is snapshotted at **add** time
  (`snapshot_offer_price`, State-ownership Chunk 6), deliberately, so historic
  reporting stays honest if a price moves before you shop. The side effect is
  that *every* line with a linked offer carries a price from the moment it lands
  on the list. So `price is not None` reads as "was bought" and is wrong for
  exactly the lines a real shop leaves behind. `period_spent` had this bug twice
  (current period and history): a $60 shop with $40 of leftovers reported **$100
  spent**, and `period_headroom` then fed that figure to the trim-to-budget
  optimiser, which trimmed a *future* list to fit money nobody spent. The list's
  own receipt was right the whole time (`compute_list_totals` applies
  `spent_only`), which is what made the surfaces disagree rather than fail.
- **Apply:** when reading `ShoppingListLine` for anything money-shaped, ask "does
  this figure claim a purchase happened?" If yes, filter on `is_ticked`. Mirror
  `compute_list_totals`' `spent_only` rather than inventing a second rule. Note
  that a comment asserting the fallback is safe is not evidence — `generators.py`
  carries one and it is false.
- **Violation signal:** a query over `ShoppingListLine` filtered only by list id
  or list status; `line_paid_unit_price(line)` called without an adjacent
  `is_ticked` check; two surfaces reporting different totals for the same shop.
- **Established by:** the shopping-list batch-1 budget fix, 2026-08-28. Four more
  call sites remain open as FU-768. See ADR-058.

### R-062 — A lazily-hydrated collection carrying derived facts is invalidated by the writes those facts derive from
- **Rule:** an `ensureLoadedAsync`-style store (R-016) is a cache with **no
  expiry** — it holds for the whole SPA session. If its DTOs carry fields
  computed from *another* entity, the store that writes that other entity must
  mark this one stale. Put the invalidation in the **writing store's**
  mutations, not in each consuming page, and invalidate on the whole entity
  rather than on a hand-picked list of "fields that matter".
- **Why:** R-016 was written to stop redundant refetches, and it does — but a
  list DTO is rarely just its own row. `RecipeDto` carries `cookable`,
  `missing_count`, `expiring_ingredient_count`, the Zero-Input hint, and in
  complex nutrition mode the whole rollup behind `kcal_per_serving` and the
  front-of-pack rating. Every one of those moves when a **stock item** does, and
  none of it is visible in a diff of the recipe. The owner hit this as "the
  cookbook filters don't work": he linked nutrition data to a stock item, walked
  to the cookbook, and got the payload fetched before the edit — no rating, no
  kcal, and thresholds filtering figures that were no longer true. The filters
  were fine. Note the failure mode is *silent and plausible*: stale derived data
  renders perfectly, so it reads as a logic bug in whatever consumed it.
- **Apply:** when adding a server-derived field to a list DTO, ask "which entity
  is this derived from, and does that entity's store invalidate mine?" Set a
  `stale` flag rather than clearing the `hydrated` one — consumers that
  distinguish "still hydrating" from "hydrated and genuinely absent" (FU-109's
  deep-link chip) will report a missing row mid-refetch otherwise. Invalidate a
  flag, never fire a refetch: a stocktake run must not cost one request per item.
  Endpoints that bypass the store (bulk verbs, server-side batch links) have to
  invalidate at their own call site — they never reach the store's mutations.
- **Violation signal:** an `ensureLoadedAsync` whose store has no `invalidate*`;
  a DTO field computed from a foreign entity with no corresponding invalidation;
  "it fixes itself if I reload" in a bug report; per-feature ad-hoc caches each
  inventing their own invalidation (`invalidateBuyVerdict`,
  `usePantryBeliefs.invalidate`, `invalidateReconcileQueue` — three copies of
  this idea before it was named); **a page that calls an api service directly
  for an entity some store also caches** (below).
- **Extended 2026-09-01 — the simplest case is a page writing the store's OWN
  entity behind its back.** `mealSlotStore` cached the household meal-slot
  vocabulary with an `ensureLoadedAsync` short-circuit, and
  `RecipeMealSlotsSettings.vue` did its CRUD straight against
  `MealSlotApiService` — a deliberate choice, commented as "the settings page
  talks to the api service directly (CRUD); this store is read-mostly". Nothing
  derived, no foreign entity: the writer simply was not the store, so the cache
  held the pre-edit vocabulary for the rest of the session. Two owner-reported
  bugs came out of that one seam — the planner's "which slot?" list not honouring
  settings until a refresh, and *"getting errors 'could not update the plan'
  after fiddling with the meal slot settings"* (the planner armed a deleted slot
  and the server's write-time slot check refused it). "Read-mostly" is not a
  carve-out; it is the exact condition under which the staleness lasts longest.
  **A store that caches an entity owns every write to that entity** — give it
  `createAsync` / `renameAsync` / `removeAsync` / `reorderAsync` that call the
  service and then refresh, and have the settings page call those.
- **Established by:** the cookbook nutrition-filter batch, 2026-08-28. See
  ADR-059. Extended by the meal-planner batch, 2026-09-01.


### R-063 — A field that records what happened must not double as the field that states what is intended
- **Rule:** intent and record are two facts, so they get two fields. A column
  whose name is past-tense (`purchased_store_id`, `actual_unit_price`,
  `completed_at`) may only be written when the thing has actually happened. When
  a surface needs to express the *plan* — where I mean to buy this, what I expect
  it to cost — add the intent field rather than pre-filling the record. Relate
  them as a **prefill chain**, each rung the default for the next and never a
  write-back, and order the chain by specificity (a choice made for *this* list
  outranks a standing preference for the item).
- **Why:** a record field written early is indistinguishable from one written
  honestly, and everything downstream reads it as fact. The shopping list had
  this twice on one surface. `purchased_store_id` was the only writable store on
  the plan face, so "get this at Aldi this week" and "I got this at Aldi" were
  the same edit — and because that field is rung 1 of the store ladder, the
  conflation *worked*, which is why it survived. Meanwhile the draft face's price
  control wrote `actual_unit_price` — "what you actually paid" — on a list where
  nothing had been bought. Both look harmless until you notice who reads those
  fields: price observations, purchase history, the money ladder's `historic`
  rung, spend reports. Compare ADR-058, where a snapshot taken for *provenance*
  was read as *proof of purchase* by five call sites; same class, different
  direction.
- **Apply:** when a UI needs to write a past-tense field on an entity that hasn't
  reached that state, stop — that is the signal. Ask what the *third* scope is,
  too: the alternative to a per-line planned store was the item's standing
  `usual_store_id`, which is a habit spanning every list, and using it would have
  made a one-off plan rewrite a preference. Per-occurrence, per-entity and
  per-install intents are different fields, not the same one at different
  altitudes. Prefer NULL-means-inherit over copying a value down the chain: a
  copy freezes a live inference into a stale literal, which is also why the
  matching migration should not backfill.
- **Violation signal:** a past-tense column written from a create/draft/plan
  surface; a form labelled "planned" or "target" bound to a field named
  `actual_*` / `purchased_*`; a migration that backfills an intent column from a
  record column; a feature request phrased as "we can only record where we
  actually got it, not where we want to get it".
- **Established by:** shopping-list feedback batch 3, 2026-08-28
  (`planned_store_id`). See ADR-060.

### R-064 — Flush ORM mutations before a Core-level access helper reads them
- **Rule:** a handler that mutates mapped entities (`repository.add`, assigning a
  relationship, `repository.remove`) and then calls one of the `*_access.py`
  helpers must `repository.flush()` first. Those helpers reach the DB through
  Core statements — `db.session.execute(select(db.metadata.tables[...]))` — and
  **a Core statement does not autoflush**, unlike an ORM query. Pending inserts
  and deletes are invisible to them until you flush.
- **Why:** the two access styles look interchangeable and are not. `create_recipe`
  already flushed and said why in a comment; `update_recipe`, doing the same
  replace-then-write-steps dance, did not — so `replace_steps_for_recipe`'s
  "do these ingredients belong to this recipe?" check compared the resolved *new*
  ingredient ids against the *old* rows still sitting in the table, and every save
  of a recipe with a step-to-ingredient link 400'd. The failure mode is the worst
  shape available: it is not a crash, it is a **validation error blaming the
  user's data**, on a save the user cannot avoid making, and it survives review
  because the resolution map it depends on is demonstrably correct.
- **Apply:** the trigger is the *pairing*, not the size of the change — ORM write
  followed by any Core read or write in the same request. Flush at the seam, once,
  with a comment naming what downstream reader needs it. Don't push the flush
  inside the helper: the helper cannot know whether its caller has finished
  mutating, and a flush in the middle of a half-built graph is its own bug (which
  is why `seed.py` explicitly turns autoflush *off*).
- **Violation signal:** a `*_access.py` call in the same block as
  `repository.add` / an entity-collection assignment with no intervening flush; a
  "references X not on this Y" error whose ids provably were resolved from the
  request; a per-recipe/per-list validation that passes on a create and fails on
  the equivalent update.
- **Established by:** recipe-view feedback, 2026-08-29 (step ingredient links
  could not be saved). See ADR-061.

### R-065 — A preference governs everything its name claims, or it gets cut
- **Rule:** when a surface stops honouring a user preference — because a better
  control took the job, or because the surface was rebuilt and never wired it —
  that is a decision about the **preference**, not just about the surface. Either
  re-wire it, or cut it. What is not allowed is leaving it in Settings with its
  original name and narrowing the help text until the text has to say where the
  setting *doesn't* apply.
- **Why:** preferences decay silently, because nothing fails. `show_recipe_images`
  was designed to govern every recipe photo in the app so a user could run a
  text-dense, low-bandwidth UI. Its stock-image twin was deleted; the cookbook
  took photos over via cards/compact; cook mode, print and the planner rail never
  honoured it. Each of those was individually reasonable and none of them looked
  like a change to the preference — so it survived, in Appearance, governing one
  hero image, and the owner's reaction on finding it was *"what is this even
  for??"*. Worse than useless: switching it off left a same-sized "Photo hidden"
  box, so it did not even deliver the density its existence implied. This is the
  second instance (FU-508 dropped `show_stock_images` for the adjacent reason),
  which is what makes it a rule rather than a one-off tidy.
- **Apply:** the trigger is **removing a consumer**, not adding one. When you
  delete or rewire the last-but-one reader of a preference, count the readers that
  are left and ask whether the preference still means what it says. Two specific
  smells, both cheap to check: (a) the help text has to name a surface the setting
  excludes; (b) the *write* surface and the *read* surfaces have drifted apart
  (this one's write button left the cookbook in 2026-08-18 precisely because the
  cookbook had stopped reading it). And when the answer is "cut", cut the column
  too — a dead boolean on `User` is a future reader's trap.
- **Violation signal:** a settings row whose help text contains "except", "the X
  decides its own", or a surface name; a preference with one remaining consumer; a
  toggle that suppresses content without reclaiming its space; a `User` column
  read by nothing.
- **Established by:** the `show_recipe_images` cut, 2026-08-29 (owner: *"I'm
  thoroughly confused about the recipe photos toggle"*). See ADR-062.


### R-066 — A chip's look is a shared class, not per-component CSS
- **Rule:** the visual identity of a chip — ground, hairline, ink, radius, tap
  height, and how its semantic tone is expressed — lives as a `.dora-chip--*`
  class in `css/colours.scss`. A component picks a class and supplies the label,
  the icon and the tone; it does not re-declare the look in its own scoped block,
  and it does not reach for a bare Quasar `q-chip` `color=` / `text-color=` pair
  to express a state.
- **Why:** chips are the app's densest carrier of state and they appear side by
  side, so a divergence is not subtle — it reads as two different systems on one
  line. Two rounds in two days made that concrete. On 2026-09-01 the cookbook's
  dietary tag and belief chip were the *same* outline chip declared twice, and
  the restyle had to be applied in both files; later the same day the recipe
  row's "Use soon" chip (a solid `q-chip` with `text-color="dark"`) sat directly
  beside the tinted missing chip and the owner asked for them to *"be styled the
  same"*. In both cases the look had been written privately inside a component,
  so nothing made the second copy visible. There is a second-order cost: the
  D-002 contrast carve-out these chips depend on was measured once, and a
  privately-declared copy inherits the tint without inheriting the reasoning.
- **Apply:** before styling a chip, grep `colours.scss` for `dora-chip`. If a
  class fits, use it. If none does, add one there — with the contrast note
  attached — rather than in the component. Where the chip is a *behavioural*
  object too (a menu, a button), the shared class carries the look and the
  component's scoped block carries only hover / focus / menu rules; that split is
  what `RecipeMissingIngredientChip` now demonstrates. A chip label never wraps
  inside its own tint: keep `white-space: nowrap` on the shared class so a chip
  breaks *around* rather than growing taller than its neighbour.
- **Violation signal:** `background: var(--semantic-*-soft)` or
  `border-radius: var(--radius-pill)` inside a component's scoped styles; a
  `q-chip` with `color`/`text-color` encoding a domain state; two chips on one
  row with different heights, radii or font weights.
- **Established by:** the missing / "Use soon" chip unification, 2026-09-01
  (owner: *"ensure missing and use soon chips are styled the same"*). See ADR-063.

### R-067 — A full-page surface follows the theme; "mood" is not a reason to pin a palette token
- **Rule:** a route-level surface takes its ground and its ink from the semantic
  surface tokens (`--surface-page` / `--surface-component` / `--text-primary`).
  It does not pin itself to a raw `--palette-*` value to force an atmosphere,
  and its children do not paint themselves `--text-inverse` to survive a parent
  that did. Raw palette tokens stay where they belong: inside the theme
  definitions, and in genuinely inverted *components* (a toast, a tooltip, a
  scrim) that are inverted against the page in every theme by design.
- **Why:** `--palette-neutral-900` is a token, so R-002 reads as satisfied — but
  a page that is black under a light theme is not theme-aware, it is hard-coded
  with extra steps. It reads to the user as a bug (*"why is stocktake suddenly
  dark?"*), and the cost compounds downward: the stocktake runner's phase
  components each had to hard-code `--text-inverse` on their headings to stay
  legible against it, which is three more places that break the moment the shell
  changes. The design intent was real — the contrast was meant to say "you're
  concentrating" — but a focus mode is carried by *layout*: the full-bleed shell,
  one card, no nav. Not by inverting the palette.
- **Apply:** ground and ink on a `q-page` root come from surface tokens. If a
  surface genuinely needs more separation than `--surface-page` gives it, reach
  for `--surface-elevated` / `--surface-sunken`, or add a theme-resolved token to
  `themes.scss` for every theme family — never a single palette literal that
  every theme then shares.
- **Violation signal:** `background: var(--palette-*)` in a component's scoped
  block; `color: var(--text-inverse)` on anything that isn't sitting on a
  semantic fill; a comment in the file explaining why this one screen ignores
  the theme.
- **Established by:** the stocktake runner, 2026-09-01 (owner: *"Why is the
  initial screen … dark/black background all of a sudden when I'm driving in
  light mode"*). See ADR-064.


### R-068 — Record the fact; don't parse it back out of prose. If you must infer, say so in the UI
- **Rule:** where a schema can hold a domain fact, hold it — do not recover it by
  running a regex or a keyword match over free text the user typed for a human
  reader. Where the payload genuinely has nowhere to put it (a prose blob, an
  imported page, an image), inference is legitimate, but the surface must **label
  the inferred value as inferred** rather than presenting it beside recorded facts
  in the same voice.
- **Why:** parsed prose is a guess wearing a fact's clothes. Cook mode read
  `"Simmer for 20 minutes"` and offered a 20-minute countdown, which is useful
  right up until it reads `"48 hours in the fridge"` off a cold-prove note and
  offers a 2880-minute timer beside the Start button, indistinguishable from a
  timer the cook set. The user can't tell which they're looking at, so they can't
  tell whether to trust it, and there is no way to *correct* it — the only lever
  is to rewrite the recipe text, which changes what the recipe says to make the
  app behave. It also silently varies by wording: "fifteen minutes" gets nothing,
  "15 minutes" gets a timer.
- **Apply:** add the column. It is nearly always a nullable scalar and one editor
  control, and NULL keeps the old inference as an honest fallback for the payloads
  that can't carry it — so the change is additive rather than a migration of
  behaviour. Then make the two visually distinguishable: a recorded value renders
  plain, an inferred one carries a short attributive caption ("from this step's
  wording").
- **Violation signal:** a regex over user-authored prose feeding anything other
  than search or highlight; a computed that derives a domain quantity from
  `.text` / `.notes` / `.instructions`; a UI that shows a parsed value with no
  indication it was parsed.
- **Non-goal:** this is not a ban on text matching. Highlighting, searching and
  the importer's first-pass parse are all fine — they either propose (and the
  user confirms) or they only affect presentation. The rule is about a parsed
  value that *drives behaviour* and reads as recorded.
- **Established by:** cook-mode step timers, 2026-09-01 (owner: *"How does the
  timer function get added? Is it guessing? … for structured I feel a tickable box
  option should be added"*). See ADR-065.


### R-069 — A palette colour tuned as a *fill* is not automatically usable as *ink*; give the ink strength its own token
- **Rule:** before painting text, an icon, a hairline or an active-state indicator
  in a brand token (`--brand-accent`, `--brand-primary`, a semantic fill), check
  its contrast against the **whole surface ladder of every theme that inherits
  it** — component, page, elevated, sunken. Where the fill tone fails D-002's
  floor as ink, do not fork the rule per theme and do not fall back to neutral
  ink: add a sibling **ink-strength token** (`--<role>-ink`), define it in
  `tokens.scss` with the measured ratios in the comment, and override it in every
  `[data-theme]` block — pointing it straight back at the fill token in the
  families that already clear the floor.
- **Why:** a brand colour is picked to look right *behind* dark text. The same
  hue as *the text* is a different job with a different floor, and nothing warns
  you: `--brand-accent` measured **1.25–2.0:1** as ink in all five light families
  while looking perfectly healthy as a toolbar and a badge. Because one token
  served both jobs, a single rule (`color: var(--q-accent)`) shipped legible in
  the dark themes and unreadable in the light ones — which is how the stock-item
  detail tabs, the settings page-header icons, the nav indicators and two Help
  buttons all became invisible at once without any of them being individually
  wrong. `--brand-secondary-strong` already existed for the mirror-image case
  (a surface-grade tone that sinks when used as a mark); this is the same
  decision, and it should not have to be rediscovered a third time.
- **Apply:** keep hue and saturation, move lightness until the *worst* surface in
  the ladder clears 4.5:1 (a graphic-only token may sit at D-002's 3:1, but pick
  4.5 when the token is shared with text — one token, one floor). Record the
  binding ratios in the token comment so the next person changing a surface knows
  what they are about to break. Then split the call sites by ground, not by
  component: ink token on page/component surfaces, raw fill token on the toolbar,
  in glows, and inside `color-mix()` tints — a tint wants the bright tone.
- **Violation signal:** `color:`, `border-color:` or a 2–3px indicator
  `background:` reading `--brand-accent` / `--q-accent` / a semantic fill;
  a `.body--dark` (or `[data-theme]`) fork that exists only to drop a brand
  colour in light mode; `color="accent"` on a *flat* Quasar button.
- **Non-goal:** not a ban on brand colour as ink — the point is to keep the hue
  and make it legible, not to retreat to `--text-primary`. And not every fill
  needs an ink sibling: add one when a real call site needs it.
- **Established by:** the accent-ink sweep, 2026-09-01 (owner: *"The yellow in
  pesto is too bright for where it is used… this is an issue across the board
  with the light themes. It's hard to see some of the text such as the tabs in
  the stock item details page"*). See ADR-066.


### R-070 — Write-time vocabulary checks validate new *values*, not whole payloads
- **Rule:** when an update endpoint validates a field against a closed vocabulary
  that the user can edit, the allowed set is *the vocabulary plus whatever the
  record being updated already holds*. A value the record is merely **carrying
  forward** is not a new write and must pass; only a genuinely new off-vocabulary
  value is refused. Create paths pass no allowance — a record that does not exist
  yet has no history to preserve.
- **Why:** the two halves of "deleting a vocabulary row is non-destructive" have
  to agree. `MealPlanEntry.slot` and `Recipe.time_of_day` hold slot *names* as
  free text with no FK precisely so that deleting a meal slot leaves existing
  labels intact — there is a test asserting it, and the delete dialog promises it
  ("2 entries use this meal slot; they'll keep the label"). But both update
  endpoints then validated their **entire payload** against the live vocabulary,
  and both of their clients resend the whole record on every edit: the planner
  resends every forward entry, the recipe editor resends `time_of_day`. So a
  preserved label survived exactly until the next save, at which point the record
  became permanently unsaveable — and unsaveable in the cruellest way, because
  the request that would have *fixed* the slot was refused for carrying it. The
  owner saw only "Could not update the plan." on a week he had not touched.
- **Apply:** `allowed_slot_names(valid, already_stored)` in
  `slot_validation.py` is the shape — the caller loads the record first anyway,
  so pass what it holds. Keep the *error message* naming the live vocabulary, not
  the allowance: listing a deleted value under "Allowed:" reads as an invitation
  to keep using it. Any new user-editable vocabulary guarding a free-text column
  gets the same treatment.
- **Violation signal:** a `get_valid_*` call in an update handler whose result
  goes straight into the check with no reference to the loaded entity; a delete
  endpoint documented as "preserves existing labels" with no test that the
  bearing record can still be *saved* afterwards; a bug report of the shape "it
  worked until I changed a setting, now this record won't save".
- **Non-goal:** not a licence to accept anything. A new entry on a deleted slot
  is still refused, and the record's own history is the only allowance — it does
  not leak across records.
- **Established by:** the meal-planner batch, 2026-09-01 (owner: *"getting errors
  'could not update the plan' after fiddling with the meal slot settings"*). See
  ADR-067.

### R-071 — A comparative figure carries its baseline in its label, and one word never spans two baselines
- **Rule:** any number that means "better/worse/cheaper/saved **than something**"
  ships the baseline it was measured against, and that baseline appears in the
  **label the user reads** — not only in a tooltip, a doc comment or the DTO. Where
  one product word legitimately covers two baselines, each surface names its own
  ("$4 under shelf price" vs "$4 less than you usually pay"); a bare "saved $4" is
  not permitted on either. A baseline that is snapshotted at event time stays
  snapshotted: never recompute a historical comparative from today's data, and
  never sum two baselines into one total, chart or trend.
- **Why:** "saved" was doing two incompatible jobs. The retrospective report
  (`SavingsCapturedHandler`) computed `list_price_at_pick − picked_offer_price` —
  savings against the *retailer's advertised* RRP — while the live shopping-list
  figure computed savings against the chosen offer's `price_was`. Both rendered as
  "saved vs RRP", both were correct for their own question, and neither said which
  question it was answering, so the dashboard could claim "You've saved $128" on a
  number that measures how good the specials were rather than how little the
  household spent. It is the metric equivalent of R-041's partial total: a
  comparative with an unstated baseline is a confident claim about an unnamed
  thing. The tense split is the fix, and it only works if both halves are labelled
  — otherwise the app has two definitions of one word and the reader picks whichever
  they assume.
- **Apply:** name the baseline in the DTO field, not just the copy
  (`savings_vs_usual_price`, not `savings`), so the seam is visible at the API. When
  the baseline is an event-time fact, give it its own snapshot column written on the
  same path that writes the compared value (`usual_price_at_pick` beside
  `list_price_at_pick`) — deriving it later makes past figures move, which is the
  failure R-063's planning/recording split is also about. If a period contains
  records from before the baseline existed, report `None` for that period or reseed;
  do not backfill and do not mix.
- **Violation signal:** a field named `savings` / `delta` / `difference` with no
  baseline in its name; a comparative whose "what it's measured against" lives only
  in a `<q-tooltip>` (this is also the R-041 signal); the same noun rendered from two
  different computations on two screens; a "just recompute the baseline from current
  data" fix on a historical series.
- **Non-goal:** not a demand that every number be comparative. An absolute figure
  (spend, count, pantry value) has no baseline to name — this rule fires only once a
  number claims a comparison.
- **Established by:** the savings-baseline decision, 2026-09-02, out of
  `DASHBOARD_PAGE_REVIEW.md` §3.5/§3.11 and `REPORTS_PAGE_REVIEW.md` §3.7 (owner:
  keep the card, change the baseline; split by tense and label both). See ADR-068.


### R-072 — A Definition of Done outlives the follow-up that deferred it
- **Rule:** when a plan's Definition of Done item is deferred into a
  `DORA_FOLLOWUPS.md` entry, that FU becomes a *pointer* to the DoD row, not a
  replacement for it. Resolving the FU **partially** does not satisfy the DoD row.
  So: an FU spun off a DoD **names the plan + the DoD row it stands for**, and its
  resolution note must state, explicitly, **which DoD rows it closed and which
  remain open** — spawning a fresh FU for each remainder before it is archived. A
  DoD row is only closed by something that says it closed *that row*.
- **Why:** `IMPL_PLAN_DASHBOARD_REBUILD.md` §6 promised *"`DashboardPage.vue` is a
  thin composition over `components/dashboard/*` widgets (R-001 — the 1964-line
  monolith is gone)"*, and Phase 0 called the extraction *"the single most
  important structural move"*. [[FU-293]] was spun off to do it, resolved honestly
  after extracting the card **shell** (`DashboardCard.vue`) — its own note even
  records the carve-out, *"card BODY SCSS stays in the page"* — and was archived.
  Nothing then tracked the fourteen bodies. Two months later the page was **3126
  lines, 59% larger than the monolith the rebuild set out to dissolve**, and the
  DoD row still read as satisfied because the FU standing in for it was in the
  resolved file. The failure is not that the partial was wrong — a shell-first
  extraction is the right order — it is that the *residue was invisible*. A
  resolved FU is read as an ending; a DoD row is read as a promise; nobody
  re-reads a two-month-old impl plan to check whether the promise survived its
  proxy.
- **Apply:** in the FU title or `What`, cite the plan and row (*"…the DoD it stood
  for is still open"* is the shape). On resolution, write a
  **`DoD rows: closed / still open`** line naming each, and open the remainder FU
  in the same edit — the remainder must exist in `DORA_FOLLOWUPS.md` before the
  parent moves to `DORA_FOLLOWUPS_RESOLVED.md`. Same discipline for a plan phase,
  a review's chunk list, or a proposal's acceptance criteria; the mechanism is
  identical wherever a durable checklist is worked through disposable tickets.
- **Violation signal:** a resolved FU whose note contains "stays in the page /
  for now / follow-up later" with no FU id beside it; a DoD row with no live FU
  and no evidence in `CHANGELOG.md`; a plan whose §6 checklist is entirely ticked
  while the artifact it describes is bigger than when the plan was written; the
  phrase "resolved at the shell level" (or any level) without a statement of what
  the other levels are.
- **Non-goal:** not a ban on partial resolution, and not a demand that FUs never
  close until the whole plan does — the opposite. It exists precisely so a partial
  *can* be closed cleanly, by making its remainder a first-class object rather
  than an absence. Nor does it apply to a follow-up that was never spun off a
  written DoD; a free-standing finding is closed when the finding is gone.
- **Established by:** the dashboard de-monolith, 2026-09-02 ([[FU-829]]) — the
  fifth sighting of componentisation-not-finished and the first where the goal
  had been written into a Definition of Done and closed by a partial. See
  ADR-069.


### R-073 — A shared visual primitive takes neutral data; the payload's meaning lives in an adapter
- **Rule:** a component that *draws* (a chart, a bar, a sparkline, a heatmap) takes
  a shape expressed in its own vocabulary — lines, segments, values, labels — and
  knows nothing about the endpoint that produced them. The translation from a
  domain payload into that vocabulary lives in **one adapter module** beside the
  types, not inside the component and not copied into each caller. A drawing
  component must never carry a flag whose name comes from the domain
  (`offersAsContext`, `isProductView`, `showObservations`).
- **Why:** the same drawing code always ends up serving a second payload, and the
  cost of the domain leak is paid at that moment. `PriceHistoryChart.vue` took
  `PriceHistorySeries[]` — the *product* DTO — and held the interpretation inside
  the drawing: an `offersAsContext` boolean, an `hasOffers()` fallback deciding
  whether the user's own observations were drawn at all, and a reach into
  `your_prices.baseline`. It drew one thing well and could not draw a stock
  item's history without either a fake product DTO (which is exactly what
  `PriceHistoryBottomSheet.vue` built: a `product_id` that was a stock-item id, a
  `store: ''`, two `null` blocks) or a second component. Meanwhile the app carried
  **ECharts, 549 KB inlined into one route**, to draw a chart it already owned in
  8 KB. The same shape had just been settled one unit earlier: `ProportionBar`
  takes `value` and lets the caller decide whether a segment is weighed by spend
  or by item count — *"a question about the data, not about the bar"*.
- **Apply:** name the neutral type after the drawing (`PriceChartSeries`,
  `ProportionSegment`), keep it in the adapter module, and give the component
  presentation-only props (`legend`, `contextLabel`, `emptyLine`, `ariaLabel`). One
  exported function per payload (`productSeriesToChart`,
  `stockItemHistoryToChart`, `trendSeriesToChart`) — those are the natural unit
  test, since the mapping is pure and a wrong mapping is silent: the chart still
  draws, it just draws the wrong line. The **empty state stays with the caller**:
  only the caller knows what the reader should do about it (B9).
- **Violation signal:** a drawing component importing from `services/api/`; a prop
  or local named after a domain concept; a caller assembling a DTO it never
  received in order to satisfy a chart; the same payload reshaped in two callers;
  a charting dependency whose only consumer is one widget.
- **Corollary — the a11y dividend:** an SVG primitive can carry `role="img"`, a
  generated `aria-label`, and a `<desc>` summarising each series; a canvas
  renderer cannot carry any of it. Consolidating onto one owned primitive is
  therefore also how a "charts have no text alternative" finding becomes fixable
  at all, and the summary belongs *in* the primitive, where every consumer gets
  it — see D-001's channel argument.
- **Established by:** FU-833, 2026-09-02 — ECharts dropped and
  `PriceHistoryChart` promoted to the app's one chart, one unit after the same
  decision was made for `ProportionBar`. Two sightings, one week, two different
  primitives. See ADR-070.

### R-074 — Two questions get two modules, even when they share a surface
- **Rule:** when a request arrives as *"add X to the Y signal"*, first ask whether
  X answers the **same question** Y does. If it doesn't, it is a **sibling signal**
  — its own module, its own endpoint, its own client cache — rendered *beside* Y
  rather than folded into it. Signals may be read together; they may not be
  averaged together.
- **Why:** folding a second question into an existing signal corrupts the first
  one silently. Nothing throws, no test fails, and the signal keeps producing
  numbers — they just stop meaning what the module's docstring says they mean.
  Owner, 2026-09-03: *"is one of the dora belief metrics based on how many
  planned meals a stock item is involved in?"* Read literally, that puts planned
  meals into `compute_belief`, whose entire job is estimating **what is on the
  shelf right now** from purchases, cooks and elapsed time. Planning to cook rice
  on Thursday is evidence about *demand*, not about the cupboard — feeding it in
  would have made a well-planned week read as an emptier pantry, and every
  downstream consumer (the stocktake queue rank, the "Dora thinks" chip, the
  buy verdict's need axis) would have inherited the distortion with no way to see
  it. The same boundary was drawn once already, from the other side:
  `inference_overlay.py` exists precisely so the belief can be *remarked* on
  other surfaces without being merged into their answers — *"the overlay never
  changes an answer, it only ever adds a remark"*.
- **Apply:** name the question in the new module's first paragraph, and say
  explicitly what it is **not**. Give it its own confidence/urgency vocabulary
  rather than borrowing the neighbour's. Share the *inputs* aggressively — the
  cooked-batch allocation is one function both `planned_demand` and
  `get_shortfall` call (R-003) — and share the *outputs* never. On the client,
  mirror the neighbour's composable and endpoint shape so two overlays are one
  pattern to learn, but keep them two caches.
- **Violation signal:** a new term appearing inside an existing scoring function
  whose docstring doesn't mention it; a confidence number that now blends two
  kinds of evidence; a field named for one question sitting in a DTO named for
  another; "just add a weight for it" in a design discussion.
- **Established by:** the planned-demand signal, 2026-09-03. See ADR-071.

### R-075 — A layout fix is not done until the running app is measured
- **Rule:** when the fix for a visual defect is a **style declaration**, prove it
  landed by reading the *computed* value or the element's geometry in the running
  app. A CSS rule that parses cleanly and does nothing is invisible in a diff, in
  review, in the type-checker and in the test suite — the only place it shows up
  is on screen, and only if someone looks.
- **Why:** this codebase has now shipped the same class of bug twice from two
  different causes. (1) **An undefined custom property drops the whole
  declaration.** Cook mode's header used `var(--space-sm)` / `var(--space-xs)`,
  neither of which exists (the scale is `--space-1..--space-12`), so *every gap in
  the header was zero* — the mechanical half of the owner's "everything is
  squished badly" report, live for weeks (FU-764). (2) **A framework prop that
  writes an inline style outranks any stylesheet.** Quasar's `size="lg"` on
  `q-btn` emits an inline `font-size`, so the `font-size` added inside a media
  query to fit Previous/Repeat/Next on one phone row was **inert** — measured at
  `20px` on a 375px viewport after the "fix". Both read as correct code.
- **Apply:** drive the surface and assert on `getComputedStyle(el)` /
  `getBoundingClientRect()` — the number, not the screenshot; a screenshot at one
  width hides the boundary case. If a declaration turns out to be outranked by an
  inline style, **change the prop, don't escalate the selector** — hand the
  framework a different value (`:size="isPhone ? 'md' : 'lg'"`) rather than
  reaching for `!important`. If a custom property might not exist, it needs a
  fallback or the linting gate (FU-834/FU-764).
- **Violation signal:** a styling commit whose evidence is "it looks right in the
  diff"; a `var(--…)` that grep can't find a declaration for; a new `!important`
  next to a framework component; a media query that restates a value the
  component already sets as a prop.
- **Established by:** the cook-mode nav row, 2026-09-03 — the second sighting of
  "the CSS was fine and did nothing", one week after FU-764. See ADR-072.

### R-076 — A derived figure never rests on a fact the data does not record
- **Rule:** when a calculation needs a quantity nobody stored, it does **not** get
  to assume a plausible value. Return "unknown", give the gap a reason code, and
  surface it — a coverage ratio, an explanatory chip, a blank where a number would
  have been. Fill the gap properly by *recording the missing fact* (a real column,
  set from real data), not by picking a default that is right on the example in
  front of you.
- **Why:** an unknown rendered as a confident number is undetectable. It passes
  review, it passes the type-checker, it passes the tests written by whoever made
  the assumption, and the only person who can catch it is a user who happens to
  know the right answer. Recipe costing has now produced three of these from one
  root cause. (1) "$4.20 per bottle" × "200 ml" billed **$840**, and a
  two-ingredient seed recipe reported **$1590**. (2) The fix converted units but
  kept the counted side pass-through, so `pack_amount` claimed every pack holds
  exactly one countable thing — true of a tin, false of the seed's *Free Range
  Eggs 12pk*, and "3 yolks" was billed as three whole 700 g cartons at **$16.50**
  off a $7.86/kg shelf price (owner, 2026-09-03). (3) The same code sold a `dozen`
  for the price of one. Each was a different guess standing in for "how many of
  these are in there?", which nothing in the schema answered.
- **Apply:** name the missing quantity out loud and ask whether a column holds it.
  If one does (`Product.pack_count`, a count-dimension `size_unit`), read it — and
  **backfill the data** where the fact was only ever written in prose, as the eggs
  product had "12pk" in its *name* and nowhere queryable. If nothing holds it,
  return `None` and a reason the UI can render. Prefer narrowing coverage to
  widening error: "Priced 3 of 5" is a smaller failure than a wrong total, because
  the reader can see it.
- **Violation signal:** a default that happens to be right for the row you tested;
  a magic `1` standing in for a count; a comment that says "assume"; two sibling
  code paths where one reports a gap and the other guesses (the price-observation
  branch got this right in 2026-08-19 and the offer branch beside it did not,
  which is how the bug survived a fix aimed straight at it).
- **Established by:** the recipe cost estimator, 2026-09-03. See ADR-073.

### R-077 — An unavailable capability names the condition that blocks it, not the browser
- **Rule:** when the UI reports that something can't be done here, the message
  must name the **actual blocking condition** it tested. If the check was "did
  `beforeinstallprompt` fire?", the honest answer is not "this browser doesn't
  support installing" — it is whichever of *not a secure context*, *already
  installed*, or *this browser genuinely lacks it* is true. Test for the
  distinguishable causes and branch the copy; where a cause can't be
  distinguished, say what you actually know rather than the most likely story.
- **Why:** a wrong cause is worse than no cause, because it sends the user to fix
  the wrong thing. Dora has now produced three of these, one per page. (1)
  Settings → Voice told Firefox users the app "doesn't expose the Web Speech API",
  which reads as a bug report about Dora when speech *recognition* is a browser
  capability Firefox has never shipped. (2) The device-voice card said "always
  available" when a browser can expose `SpeechSynthesis` and hold zero voices — a
  dead control failing silently. (3) About → *Install as an app* said "Install
  isn't available in this browser. Try Chrome on Android" to an owner already in
  Chrome; the real cause was that a self-hosted Dora served over plain `http://`
  on the LAN is not a **secure context**, so `beforeinstallprompt` never fires in
  *any* browser (owner, 2026-09-03). The copy sent him to a browser that would
  behave identically.
- **Apply:** before writing "not supported here", enumerate what could make the
  check fail and test the ones you can (`window.isSecureContext`, a feature's own
  presence, an empty result from a present API, an install-wide flag). Give each
  distinguishable cause its own sentence, and say what to *do*, not just what
  isn't happening. Fold the check into a named helper beside the capability
  (`installUnavailableReason()`) so the branch is testable and the next surface
  reuses it rather than re-deriving it.
- **Violation signal:** copy naming a browser or a platform where the code tested
  neither; a "try X instead" that would fail the same way; a single `v-else`
  carrying the message for several unrelated failure modes; any sentence of the
  form "your browser doesn't support…" written from a check that never asked the
  browser anything.

### R-078 — A component sized by its container never branches on the viewport
- **Rule:** a component's responsive behaviour keys off **the space it is
  actually given**, not off `window`. If a component can render inside a dialog,
  a rail, a drawer, a card column or a bottom sheet, then `@media (max-width: …)`
  and `$q.screen.lt.*` are the wrong instruments: they describe the browser
  window, which in those hosts is unrelated to the component's width. Use a
  layout that needs no breakpoint (wrap, `flex-basis` with `min-width: 0`, a
  stacked shape at every width), or take an **explicit prop** from the host that
  names the situation, or a real container query. A viewport query is only
  honest in a component that is always full-bleed.
- **Why:** the app keeps producing the same defect from this one confusion, and it
  is always invisible to the person who wrote it, because the width they tested
  at is the width where it happens to work. Recorded instances: the meal-plan
  builder's review row stacked under `@media (max-width: 599px)` while living in
  a ~600px dialog, so a 1280px desktop kept the full ~400px control cluster and a
  long recipe name ("Pizza dough (60% hydration)") painted straight through the
  day/slot selects — the owner's diagnosis was exact: *"seems better on mobile,
  so an edit to make mobile better stuffed up desktop"* (FU-852, fixed
  2026-09-03). `RecipeRow.vue`'s `compact` derives from `$q.screen.lt.sm`, which
  is why it cannot be reused in a 340px rail on a desktop and why
  `MealPlanRecipeRow` had to exist at all. `MealPlanRecipePicker` once capped
  itself at `max-height: 65vh` inside a pane that was already correctly sized.
  Each was found by looking, not by testing.
- **Apply:** ask "can this component be narrow while the window is wide?" If yes,
  delete the breakpoint. Prefer the shape that needs no branch — the builder row
  is stacked at *every* width now, because there was no width at which one line
  was working. Where a genuine mode difference exists, pass it: `MealPlanRecipeRow`
  takes an explicit `mode` prop precisely so the rail's width has nothing to do
  with the window's. Reserve viewport queries for page-level chrome and for
  things that really are about the device (touch targets under
  `@media (hover: none)`, a phone's scroll regions).
- **Violation signal:** a media query or `$q.screen` read inside a component that
  a dialog, drawer, sheet, rail or side column also renders; a fix described as
  "better on mobile" that made desktop worse (or the reverse); two breakpoints in
  one component that disagree about what "narrow" means; a `vh`/`vw` size on a
  child of a container that already has a definite size.

### R-079 — A display formatter owns its own rounding
- **Rule:** the function that decides how a value is *written* also decides how
  many digits it is written to. A call site must never have to remember to round
  before formatting, and must never carry its own private `round()` beside a
  shared formatter.
- **Why:** the alternative diverges immediately, and silently. `formatQuantity`
  was the single authority for unit spacing (DEC-3) but not for precision, so it
  did `String(quantity)` — and aggregated meal-plan demand is a sum of scaled
  per-recipe quantities, i.e. binary floats. The meal planner's right rail read
  *"needs 31.333333333333332 tbsp"* (owner, 2026-09-03) while the auto builder's
  preview of the same figures looked fine, because the builder had grown a local
  `function round(n)` and the rail had not. Two call sites, one formatter, two
  answers — which is R-003's failure mode wearing a decimal point. The
  every-call-site-remembers approach cannot be enforced and cannot be tested in
  one place.
- **Apply:** put the rounding inside the formatter, pin it with tests that include
  the float artefacts (`94/3`, `0.1 + 0.2`) and the values that must survive
  untouched (`0.25`, `0.5`, `2.0` → `"2"`, not `"2.00"`); use
  `Number(v.toFixed(n)).toString()` rather than `Math.round(v * 100) / 100`,
  which produces artefacts of its own. Then delete the call sites' local rounders
  — leaving one in place is the divergence, dormant. Guard non-finite input so a
  `NaN` renders as nothing rather than the word.
- **Violation signal:** a `round`/`toFixed`/`Math.round` immediately beside a call
  to a shared formatter; a formatter that takes an already-formatted string in one
  place and a raw number in another; a rendered figure with more than a handful of
  decimal places anywhere in the UI.

### R-080 — When the framework paints from its own variable, feed that variable
- **Rule:** where a third-party framework applies a style from a variable it owns
  (`--q-dark-page`, `--q-primary`, …), the fix is to **sync that variable from our
  token**, in the one place that already bridges the two systems. Never out-specify
  the framework's selector with a competing rule, and never leave our token
  authored-but-unpainted next to the framework's default.
- **Why:** `css/app.scss` set `body { background-color: var(--q-page) }`, but Quasar
  ships `body.body--dark { background: var(--q-dark-page) }` — a *class* selector,
  so it wins on specificity, and nothing ever set `--q-dark-page`. For months every
  dark theme painted Quasar's `$dark-page` grey while each theme block's authored
  `--surface-page` (Pesto Dark `#00120B`, Cherry Cola `#2E0014`, Lemon Tart Dark's
  charcoal) was **dead code** — invisible until a sticky header happened to paint
  the token directly and read as a deliberate green band (FU-709). The failure mode
  is the dangerous kind: no error, no visual break, and a whole design dimension
  silently inert. Escalating specificity instead (`body.body--dark { … }` of our
  own, or `!important`) would have "fixed" the page while leaving every *other*
  Quasar-owned paint of the same variable disagreeing with us — two sources of
  truth for one colour, which is R-003 with a vendor prefix.
- **Apply:** find the framework's own bridge (here `syncQuasarPaletteFromCssVars`
  in `themeService`) and set the framework variable from the semantic token there,
  so the token stays the single source (R-003). Then **delete the workarounds the
  old behaviour spawned** — the `body.body--dark` fork in `StockOverview`'s peek
  header existed only to match Quasar's grey, and would have become a second
  divergence the moment the sync landed. When you author a token, check it actually
  paints: `getComputedStyle(document.body).backgroundColor` in the running app, not
  the value of the custom property (R-075).
- **Violation signal:** a rule whose only job is to beat a vendor selector; a
  `!important` on a colour; a `.body--dark` / `[data-theme]` fork in a component
  that restates what a token should already say; a theme token that no screenshot
  can be found to show.
### R-081 — A switch is owned by the surface it governs, and it must actually govern it
- **Rule:** an install-wide or per-user switch lives on the page whose behaviour
  it changes, not on a general "features" page that collects switches by virtue
  of their being switches. And every switch must gate something a reader can be
  shown: if you cannot name the surface it hides or the behaviour it changes,
  it is not a setting — delete it, column and all.
- **Why:** a page of switches is organised by the *shape* of its contents rather
  than by what the reader came to do, so it grows into a junk drawer and every
  item on it is one click further from its own context. Dora's Features page ran
  that course: it held meal planning, money, companion ingestion and the weekly
  deals email — four unrelated concerns — while a fifth switch (the buy-verdict
  oracle) had already escaped to Assistant under D-12 for exactly this reason.
  The junk drawer also hides dead switches, because nothing on the page invites
  you to ask what any one of them does. `meal_planning_enabled` shipped in
  C-cross Chunk 1 with the caption *"Hides the meal-plans surface when off"* and
  never did: the nav entry and the `/meal-plans` route were unconditional and no
  component read the flag. It survived three months because it looked plausible
  next to four real ones, and because the health flag it published made it look
  load-bearing from the API side. The owner spotted it by asking the only
  question the page could not answer — *"what does this toggle actually do?"*
  (2026-09-03).
- **Apply:** put the switch where its effect is — scanning on Stock, money on
  Money, ingestion with the data it lets in, a scheduled mail on the page that
  configures mail. When adding a flag, write down the surface it gates *and the
  test that proves it* before the toggle; when you find one you can't explain,
  trace every reader (`grep` the column, the DTO field, the health flag and the
  composable) and either wire it up or drop it with a migration.
- **Violation signal:** a page whose title is a category of control rather than a
  concern ("Features", "Options", "Toggles"); a flag whose only readers are its
  own settings page, its API field and a help paragraph; caption copy asserting
  a gate that no `v-if`, route guard or query filter implements.

## ADR process (evaluate every task)

At the end of each work unit, ask: **did this task make or rely on a decision that
a future agent will face again?** If yes, it deserves an ADR — and if the decision
is a *general engineering rule*, promote it into a new `R-0NN` above.

Write an ADR when: a recurring pattern got a canonical answer; a rule was bent for a
real reason (record the carve-out so it's not "fixed" later); a tooling/architecture
choice was made that constrains future work. Do **not** write one for routine,
one-off, or purely product/UX decisions (those go to the Charter check + worklog).

**ADR entry shape:**

```
### ADR-0NN — <short title>
- **Date / task:** YYYY-MM-DD (prompt id or task)
- **Status:** accepted | superseded by ADR-0MM | proposed
- **Context:** what forced the decision.
- **Decision:** what we chose.
- **Consequences:** what this commits us to; what it rules out.
- **Promotes rule:** R-0NN (or "none").
```

---

## ADR Log

### R-082 — An eager `include()` cannot be trusted to populate a `lazy="noload"` relationship
- **Rule:** when a helper's answer depends on a relationship declared
  `lazy="noload"` (`StockItem.stock_level` and friends), resolve it **explicitly**
  — the shared `resolve_levels_by_item` / `_level_access.py` idiom, or a direct
  read of the mapped FK — rather than relying on an `.include().then_include()`
  chain to have filled it in. A helper whose correctness depends on *what else
  the session has already loaded* is not a helper; it is a trap with a return
  value. If you must depend on load order, the ordering constraint goes in a
  comment at both ends, and the finding goes in the ledger.
- **Why:** SQLAlchemy's identity map returns the instance it already has. An
  eager include issued *after* something has pulled the same rows in plainly
  does not backfill the noload relationship — and nothing raises. The read
  returns `None`, which every one of these relationships spells as a legitimate
  domain answer: "this item has no recorded level". So the failure is a **200
  with a confident wrong number**, not an error.
  This has now bitten three times in the same codebase. It produced
  "unsure" for every buy verdict (the reason `_level_access.py` exists at all);
  it read as "this item has no level" in the pantry-belief overlay; and on
  2026-09-04 it made Kitchen health's new `plan_coverage` component announce
  *"None of your 6 planned meals can be cooked right now"* on a dashboard whose
  neighbouring card was offering to cook five of them — because the freshness
  block above it had already loaded every `StockItem` with a bare
  `get(StockItem).all()`, so `load_recipe_cookability`'s eager
  `RecipeIngredient → StockItem → StockLevel` chain populated nothing and every
  linked ingredient read as unstocked.
- **How to comply:** prefer the explicit resolver. Where a hoist is the
  pragmatic fix (as it was for `get_dora_score._gather_inputs`), say *why the
  order matters* in a comment a reordering edit cannot miss, and log the proper
  fix — here, [[FU-872]].
- **Established:** 2026-09-04 (dashboard feedback batch). See ADR-079.

### R-083 — A per-entry exception to an install-wide policy must be neutral in both directions
- **Rule:** when a per-row flag exempts one entity from a household-wide policy,
  work out what the policy does *to* the entity **and** what the entity does *to*
  the shared pool, and neutralise both. Then walk every verb that touches the
  pool — including the background sweeps — and state the exemption once, in the
  place that owns the resolution, rather than teaching each helper the flag.
- **Why:** an exception implemented in one direction only is worse than no
  exception, because it silently destroys shared state. `MealPlanEntry.cook_fresh`
  is the case: a meal cooked fresh in a batch household must not *demand* a
  portion from the cooked pool (or the shortfall inflates and you batch-cook food
  you don't need) **and** must not *spend* one (or the auto-drain sweep quietly
  consumes a portion the household still has in the freezer). Only the first half
  is obvious from the feature request; the owner had to say both —
  *"it should not take a meal, and it should also not demand a meal from the
  pool"* — and the second half is the one that loses data.
- **How to comply:** enumerate the pool's readers and writers before writing the
  flag. For `cook_fresh` that was `allocate_pool`, `recipe_shortfalls`,
  `reconcile_consumed_meals` and every resolution verb in `reconcile.py`, plus a
  mutual-exclusion check against cook batches on both write paths.
- **Established:** 2026-09-04 (carried over from the 09-04 fresh-cooking unit,
  which flagged the shape and did not promote it). See ADR-080.


### R-084 — Only a navigation may blank the page; an in-place edit refreshes quietly
- **Rule:** a loader that nulls the page's data before re-fetching belongs to
  *navigation* — arriving at a different record. Any mutation of the record the
  user is already looking at (add a line, remove a line, clear, trim, toggle a
  field) re-reads through a **quiet** refresh that assigns the new payload over
  the old one and never passes through the empty state. When both are needed,
  the two paths are separate named functions and the difference is documented on
  the quiet one.
- **Why:** blanking re-renders the page through its skeleton branch, so a
  one-row edit flashes the whole screen. It reads as a bug even when the data is
  correct, and it costs the user their scroll position and any expanded
  section. This is now the third report of the same defect on the same page —
  the shop-date save (2026-08-29) and then *"hate that the shopping list flashes
  every time you remove an item"* (owner, 2026-09-04), which the 08-29 fix had
  already built the quiet path for but only wired to the list-level edits.
- **How to comply:** when you add a mutation handler, look at what its refresh
  call does *before* its first `await` — if it sets the page's data to `null`,
  it is the navigation loader and you want the quiet sibling instead. Adding the
  quiet path without sweeping the sibling handlers on the same page is what left
  this open for a week; sweep them.
- **Established:** 2026-09-04 (`ShoppingListDetail.vue` — `onRemoveLine`,
  `onAddSuggestion`, `onClearAll`, `addLineBackToActive`, `applyTrim`). See
  ADR-081.


### R-085 — Touch affordances key off the pointer, never off the viewport width
- **Rule:** any style whose purpose is *"a finger is using this"* — tap-target
  floors, hit areas, menu row heights, drag handles, hover-only reveals — is
  written under `@media (pointer: coarse)` (or `hover: none`), never under a
  `max-width` breakpoint. Width breakpoints stay for what they actually
  describe: how much room the layout has. When one element needs both, the two
  queries are written separately and each is commented with which question it
  answers.
- **Why:** they are different questions with different answers, and the app has
  already been bitten by conflating them. A desktop window dragged to 375px is
  still a mouse; a tablet at 1024px is still a finger. `ShoppingListPlanRow`
  produced a 375px overlap by keying the grip's hiding to `hover: none` while
  the column count keyed to `max-width` — at that width the two disagreed and
  the row collapsed onto itself. The same conflation is why the D-004 tap-target
  gap sat open from August (FU-678, FU-641): both were scoped as *"raise every
  button in the app"*, which re-flows desktop toolbars and is correctly scary,
  when D-004 was only ever a rule about touch surfaces and says so.
- **How to comply:** before writing the query, ask what the rule is *for*. If
  the answer contains the word "finger", "tap", "thumb" or "touch", it is
  `pointer: coarse`. If it contains "fits", "wraps", "columns" or "room", it is
  a width breakpoint. Scoping a touch rule to the pointer also means it does not
  need to be justified against the desktop layout at all, which is usually what
  makes the change shippable.
- **Established:** 2026-09-05 (the app-wide tap-target sweep — `BaseButton`'s
  44px touch floor, `app.scss`'s menu-row floor, `StockLevelPicker`,
  `StockItemRow`, `RecipeRow`). Prior art it now generalises:
  `ImageSourcePicker`, `NutritionFoodPicker`, `LocationAddChip`,
  `LocationSectionChip`. See ADR-082.


### R-086 — A list row that hosts a popup is keyed on content identity, not a churning server id
- **Rule:** when a `v-for` row owns something with its own lifetime — an open
  `q-menu`, an inline editor, a focused field, an expansion — its `:key` must be
  derived from the fields that identify *the thing*, not from a database id the
  write path re-mints. Where the natural content key can legitimately repeat,
  disambiguate with an occurrence suffix rather than falling back to the id.
- **Why:** a remount destroys whatever the row was hosting, and the user reads
  that as the control closing under them. Dora has at least one write path that
  replaces rather than updates — `PATCH /meal-plans/{id}` deletes every forward
  entry and inserts new rows, deliberately, because the cook-batch rebuild is
  written on top of that shape — so every planned meal's
  `meal_plan_entry_id` changes on *any* edit to the week, including one to a
  different meal on a different day. Keyed on it, the entry menu's servings
  stepper closed itself after each tap: owner report 2026-09-05, *"to increase
  by 3 you have to tap 6 times."* Nothing about the row looked wrong, which is
  what makes this expensive to find — the defect lives in the key, one line
  away from the symptom.
- **How to comply:** before keying a list, ask whether the endpoint that writes
  it *updates* rows or *replaces* them. If it replaces (a whole-collection PUT/
  PATCH is the tell), the id is a rendering hazard. Keep using the id for
  writes, membership and navigation — this is a rendering concern only, and
  saying so in the key helper is what stops someone "fixing" it back.
- **Established:** 2026-09-05 (`mealPlanEntryKey.ts`, consumed by
  `MealPlanWeekDayCard` and `MealPlanMobileFocus`). See ADR-083.

### R-087 — An external client gets its own authenticated door onto the *same* handler, never a parallel implementation
- **Rule:** when a capability the SPA already has must also be reachable by a
  non-session caller (an ingestion source, a future CLI, any bearer-key client),
  add a thin route that authenticates differently and calls **the same handler**.
  The new route may do auth, argument parsing and logging; it must not contain
  behaviour. Two doors, one room.
- **Why:** the two callers differ only in how they prove who they are — the SPA
  presents a `dora_session` cookie, an external client presents
  `Authorization: Bearer <key>` against `IngestionSource`. Nothing about the
  *work* differs, so duplicating it means two cascade policies, two sets of
  edge cases, and a guarantee that a fix lands on one and not the other. Dora's
  product delete is the sharp example: its cascade decides what happens to
  finished shopping lists, price alerts and barcodes. A second implementation
  for the companion would inevitably drift, and the drift would be silent data
  loss on somebody's receipt.
- **How to comply:** put the behaviour in a handler class that takes a
  repository and knows nothing about auth (`DeleteProductHandler`,
  `GetIngestableProductsHandler`). Session routes live under their feature's
  router; bearer routes live under `INGEST_ROUTER` and must be listed in
  `middleware.PUBLIC_ENDPOINTS` (which exempts them from the *session* gate —
  they still authenticate, just in the handler). Keep the response
  **source-agnostic**: never echo the caller's identity back (R-005). If you
  find yourself copying a handler body to change its auth, stop.
- **Established:** 2026-09-06, on the third instance — `ingest_link_status`
  (read), `ingest_delete_product` (write, sharing `DeleteProductHandler` with
  the SPA's `DELETE /api/products/<id>`), and `ingest_list_products` (list).
  Deliberately not promoted at the first or second. See ADR-084.


### R-088 — A cross-cutting interaction default is owned by a wrapper, never repeated or patched
- **Rule:** when a framework component's *default behaviour* is wrong for this
  app on every surface (a delay, a transition, a dismiss policy, a position),
  fix it by routing every call site through a thin `Base*` wrapper that sets the
  default and passes the rest through. Do **not** set the prop at each call site,
  and do **not** mutate the vendor component's `props.*.default` at boot.
- **Why:** per-call-site is how you get 313 tooltips of which 2 have a delay —
  the default is then whatever the last author happened to type, and the next
  one silently reverts it. Boot-time patching fixes it in one place but makes
  `<q-tooltip>` behave differently from its own documentation with nothing in the
  template to say so; that is the reflection-shaped magic R-019 exists to keep
  out. A wrapper is explicit at every call site (`<BaseTooltip>` is visibly not
  `<q-tooltip>`), greppable, and overridable by a prop where one site genuinely
  differs.
- **How to comply:** wrapper renders the vendor component, declares only the
  props whose defaults it is changing, and lets `$attrs` carry everything else
  (so `anchor` / `self` / `class` keep working untouched). Sweep the call sites
  in the same change — a wrapper that only new code uses is not a default, it is
  a second convention. Then delete the now-redundant per-site overrides, or the
  single source is a lie.
- **Violation signal:** a new raw `q-tooltip` in a diff; the same prop set to the
  same value at more than ~3 call sites; anything assigning to a vendor
  component's `.props` outside its own package.
- **Established:** 2026-09-09 (`BaseTooltip`, 313 call sites across 81 files).
  Prior art it now generalises: `BaseButton`, `BaseDialog`, `BaseSelect`. See
  ADR-085.
- **Amendment, 2026-09-13 — a wrapper default is a default, not a law.** The
  wrapper's job is to make the *common* case right without 313 authors having to
  think; it is not a ban on the prop. A call site may override it when the
  control's semantics genuinely differ, and the override carries a comment
  saying why. Worked example: `BaseTooltip`'s 500 ms dwell exists so a tap on a
  **button** doesn't flash its label on the way to doing the button's job —
  but `InfoTip`'s (?) chip has no other job, so the dwell is pure latency on the
  only gesture the control has, and it sets `:delay="0"`. The signal that this
  is a legitimate override rather than drift: it is set **in a shared component**
  (so it is still one decision in one place), not sprayed across pages. The
  violation signal above stands unchanged — "the same prop set to the same value
  at more than ~3 call sites" is what distinguishes drift from a reasoned
  exception.


### R-089 — A domain convention the client must apply *before* a round-trip is codegen-mirrored, never restated
- **Rule:** when the server owns a rule (R-003) but a client surface has to apply
  it to a value the server has never seen — a live preview, an offline path, a
  figure being typed — do **not** hand-write a second copy of the rule, and do
  **not** contort the UI into a round-trip it can't afford. Make the rule *data*
  on the Python side and emit it into `web_app/src/generated/` via the dump
  script, then write a thin client reader over the generated constants.
- **Why:** the two obvious options are both wrong. A hand-written copy is R-003
  drift by construction and it *will* diverge — the recipe cost dialog's private
  "flip to /kg below $0.05" threshold and the price-entry widget's no-flip-at-all
  were two different answers to a question `units.display_denominator_for` had
  already answered, and neither followed the install's measurement system. A
  forced round-trip is worse UX for no correctness gain: you cannot ask the
  server what a price you haven't logged yet should be quoted per.
- **How to comply:** restructure the Python so the rule is a table plus a thin
  function over it (branches can't be emitted; data can). Extend
  `scripts/dump_units.py` — or the equivalent generator — with an emitter, and
  re-run it; the output is checked in. The client reader lives in `helpers/`,
  names the Python function it mirrors, and states in its header that it is a
  reader and not a second copy. Sweep the existing hand-rolled copies in the same
  change, or you have added a third convention rather than removed two.
- **Violation signal:** a threshold, factor, or unit label typed into a `.vue`
  or `.ts` file that also appears in `dora_api/domain/`; a client helper whose
  comment explains a *domain* rule rather than pointing at one; a `src/generated/`
  file edited by hand.
- **Established:** 2026-09-13 (shelf-denominator convention: "$0.01 per g" →
  "$0.70 per 100g"). Prior art it now generalises: the `units_table.ts` mirror
  itself (B2), which had the mechanism but never stated the rule. See ADR-086.


### R-090 — A reserved grid track is computed from what it holds, never typed as a number
- **Rule:** when a CSS grid reserves a fixed track for a known set of controls —
  an action cell, a quantity cell, an icon gutter — express its width as
  arithmetic over the control's own size token (`calc(var(--btn) * 3 + gap * 2)`),
  not as the literal that happened to be right the day it was written. If the
  control's size varies by media query, the *token* varies and the track follows.
- **Why:** a typed literal is a snapshot of an invisible calculation, and nothing
  re-runs it when the inputs move. `ShoppingListPlanRow` reserved `104px` for
  three 36px buttons and two 4px gaps — 116px of content — so the first reorder
  arrow rendered 12px outside its own column, on top of the money. It was
  invisible on a desktop only because those buttons are `opacity: 0` until hover.
  Then `BaseButton` grew its `pointer: coarse` floor (D-004, 36px → 44px) and the
  same cell needed 140px on exactly the device where the arrows are never hidden:
  the phone overlap the owner reported was the desktop bug, twice as bad, on the
  surface that couldn't mask it. Neither change was wrong; the literal simply
  could not hear about either.
- **Also:** `grid-row: 1 / -1` is not "span every row" on a grid with no
  `grid-template-rows`. Negative line numbers resolve against the *explicit*
  grid, which for an all-implicit grid is one line long, so the declaration
  collapses to a single row — pinning that row to the tallest spanning item and
  padding every other cell with dead air (18px per row, here). Use
  `grid-row: 1 / span N` past the row count; empty implicit rows have no height.
- **How to comply:** name the control metric as a custom property on the row
  (`--sl-act-btn`), redefine it in the media query that changes the control, and
  derive every track that holds one from it. One place to change, one place to be
  wrong.
- **Violation signal:** a `px` literal in a `grid-template-columns` that is
  divisible by a button size; a fixed track width and a `@media (pointer: coarse)`
  block in the same stylesheet that don't reference each other; `grid-row` or
  `grid-column` using `-1` on an axis with no explicit template.
- **Established:** 2026-09-17 (shopping-list plan row: money printed over the
  reorder arrows at 375px and, unseen, at 1440px). See ADR-087.


### R-091 — A box being size-animated carries no padding, border or min-height
- **Rule:** when a transition animates an element's `height` (or `max-height`)
  to zero — `q-slide-transition`, a hand-rolled disclosure, an accordion — that
  element must own **no** padding, border or `min-height`. Put them on an inner
  wrapper. A caller styling the animated box instead of the inner one is the
  violation, so the shared component should ship an inner element and say so.
- **Why:** an element's height cannot go below its own padding and borders, so
  the animation lands on the padding box and the remaining pixels disappear in
  one frame when `display: none` arrives. Traced on the shopping list's overview
  card: 199px → **29px** over ~250ms, a hold, then 29 → 0 instantly — and 29px
  is exactly `padding-top: 12px + padding-bottom: 16px + 1px border`. The owner
  had reported it three times as "a snap at the end which looks ugly… this keeps
  recurring", which is what it looks like from the outside: every disclosure in
  the app that a caller had padded did it, and none of them looked broken in
  code review.
- **How to comply:** `CollapsibleCard` renders `.collapsible-card__inner` inside
  the animated `.collapsible-card__body`, and pins the body to `padding: 0;
  border: none`. Style the inner. For a new component, animate a bare box and
  give the slot its own padded wrapper.
- **Violation signal:** padding or a border on the same element as a
  `v-show`/`v-if` inside a slide/collapse transition; a disclosure that visibly
  jumps at the end of its close; a caller's `:deep()` rule targeting the
  animated node.
- **Established:** 2026-09-17 (shopping-list overview card; the fix is in the
  shared component so every caller inherits it). See ADR-088.


### R-092 — A provenance stamp records how something arrived; it never stands in for current state
- **Rule:** a column recording *how* or *why* a row came to exist — `added_via`,
  `source`, `created_by`, `imported_from` — may be read to explain history. It
  must **not** be read as a proxy for a fact that can change after the row is
  written. If a decision asks "is this item low?", "is this needed soon?", "does
  the user buy this often?", it reads the live signal, even when a stamp
  correlates with the answer today.
- **Why:** the stamp is frozen at insert; the fact it correlates with is not.
  `trim_to_budget` decided three of its five tiers from `added_via`: a line
  stamped `auto_low_stock` was offered as "N days' cover left" however long ago
  that was and whatever the item's band is now, and "For <Recipe> on <Day>"
  required the line be stamped `auto_recipe`/`auto_meal_plan` even though the
  meal-demand map — right there in the same context object — is what actually
  answers it. The gate quietly *excluded* correct candidates: a hand-added line
  for a dinner five days out was never offered as a trim. Nothing looked wrong
  in review, because the stamp names the same concept as the live signal.
- **How to comply:** derive from the entity's current state or from the server's
  own aggregate. Where no live signal exists, build one and share it rather than
  reaching for the stamp — the habit ranking in
  `features/shopping_lists/_frequently_added.py` was extracted for exactly this
  (and de-duplicated `auto_generate`'s copy of the same query, R-003).
- **Violation signal:** a comparison against a provenance constant inside logic
  that also has the entity in hand; a conditional whose comment explains what
  the stamp "means about" the item now; a stamp consulted anywhere outside a
  history/audit read.
- **Established:** 2026-09-19 (shopping-line provenance collapse; the enum the
  stamps came from was deleted in the same unit). See ADR-089.

### R-093 — A derived alert's key names the episode that started it
- **Rule:** an alert that is computed from live state rather than stored (the
  bell's kinds, push, any future channel) is identified by its subject **and**
  the fact that began the current occurrence of its condition: the expiry date,
  the day the level changed, the planned shop date, the price observation. Two
  occurrences of the same condition must produce two keys; one occurrence must
  produce the same key on every evaluation. Each alert also states when its
  episode began (`started_on`), from that same fact.
- **Why:** per-user decisions (snooze, dismiss) are stored against the key. With
  a key of just `stock:<id>:expiring_soon`, dismissing this week's apples
  silenced every later pack of apples for good, and `shopping_day` reused one key
  for "your shop is in two days" and "your shop was two days ago", so dismissing
  the reminder also hid the missed-shop nudge (owner 2026-10-15). A key that
  carries a day count has the opposite fault: it re-fires every morning.
- **How to comply:** build keys with `alert_key.py`'s helpers and put the
  episode in the discriminator (`f"expiring_soon:{expiry_date}"`). A new kind
  that has no natural episode (a weekly nudge) uses the window it is about.
  Set `started_on` from the same fact; the discard window measures it.
- **Violation signal:** a discriminator that is only the kind name; a key built
  from a value that changes daily; a kind split from another that still shares
  its key.
- **Established:** 2026-10-15 (alerts rework). See ADR-090.

### R-094 — A token built from themeable tokens is re-declared on every themed subtree
- **Rule:** a design token whose value is `var(...)` of a token a theme sets
  (`--seg-active-bg: var(--brand-primary)`) is declared on `:root` **and** in the
  `[data-theme]` block in `tokens.scss`, so it resolves against the nearest
  theme, not the document's. Only tokens no theme block overrides go in that
  block (it sits before `themes.scss` and would clobber a theme's own value).
- **Why:** custom properties resolve where they are declared. Declared only on
  `:root`, the derived value is fixed to the document theme and *inherited* as
  that resolved colour, so a subtree pinned to another theme (onboarding's
  WelcomeLayout is always Pesto Dark) painted the segmented control with the
  light theme's track (2026-10-17, onboarding batch).
- **How to comply:** when adding a derived token to `:root`, add it to the
  `[data-theme]` block too, unless a theme overrides it. To paint a preview in
  another theme, put `data-theme="<key>"` on the element and use tokens.
- **Violation signal:** a light control on the dark onboarding canvas; a
  `var()`-valued token in `:root` that the `[data-theme]` block lacks.
- **Established:** 2026-10-17 (onboarding batch). See ADR-091.

### R-095: Live data is preserved: every migration carries existing rows forward
- **Rule:** a household uses the production deploy for real, so a schema change
  must keep the data already in it. A migration that renames, splits, moves or
  retypes a column backfills the new shape from the old one in the same
  migration; dropping a column or table is allowed only when its data is truly
  dead (derived, unused, or moved elsewhere by that migration). "Reseed, don't
  backfill" is a dev-data tactic, never a migration strategy.
- **Why:** until 2026-10-20 the posture was pre-release with no real users, so
  non-preserving migrations were allowed and several open follow-ups planned
  them. From 2026-10-20 the owner's household runs on the production server,
  where the DB is kept across deploys and upgraded by Alembic on boot. A
  migration that drops data there loses real records, and the in-app backups
  sit in the same volume.
- **How to comply:** write the backfill into the migration (SQL that works on
  both SQLite and Postgres, R-005); give the downgrade a real inverse where the
  data allows it; run the upgrade against a copy of a populated DB, not only a
  fresh one. Dev resets with `drop_all` (R-006) are unaffected. R-007's "no
  compat shims" still applies to code; it never licenses dropping stored data.
- **Violation signal:** a migration that drops or recreates a column with no
  `UPDATE`/`INSERT ... SELECT` carrying values across; a plan or follow-up that
  says "no back-fill", "non-preserving", or "pre-release, no real users".
- **Established:** 2026-10-21 (household starts using the production deploy).
  See ADR-092.

### R-096: A shared component's style rule is scoped to the variant that needed it
- **Rule:** a style rule added to a shared `Base*` component (or any component
  used across surfaces) to fix one variant is conditioned on that variant, by a
  modifier class or prop-driven class (`.base-select--chips`), not written
  against the component's root or a `:deep()` Quasar internal for every use.
- **Why:** `BaseSelect` gained `:deep(.q-field__native) { flex-wrap: nowrap }`
  on 2026-08-21 so a single-value select would truncate. It applied to every
  select in the app, and on the chip variant (chips can't ellipsis) it pushed
  the chips off the side and scrolled the whole page sideways (fixed
  2026-08-31, FU-794).
- **How to comply:** name the variant the fix is for, give it a class bound to
  the prop or state that defines it, and scope the rule to that class. If the
  rule really is for every variant, check each one renders correctly and say
  so in the comment.
- **Violation signal:** an unconditioned `:deep(.q-*)` rule in a shared
  component whose comment names one use ("so the single select truncates");
  a fix on one page that changes layout on another.
- **Established:** 2026-10-22 (FU-794, from the 2026-08-31 recipe-view batch).
  See ADR-093.

### R-097: A create and update pair shares one write module
- **Rule:** when a feature has a create handler and an update handler over the
  same child rows, the parts they share live in one private module beside them
  (`_entry_writes.py`, `_recipe_errors.py` + `recipe_requests.py`): the child
  request model (the update one subclasses it), the pre-write checks, the
  resolve/build helpers, an outcome dataclass the two response types extend,
  and one function mapping an outcome to its HTTP response. Each handler keeps
  only its own orchestration.
- **Why:** the recipe and meal-plan writers each carried two copies of the same
  validation, the same entity construction and the same error-to-HTTP chain,
  and the copies drifted (finalisation 01-R12/R13: the recipe update reported a
  bad tool as a bad tag; 02-R7: the meal-plan pair repeated slot, cook-batch,
  past-date and recipe checks line for line).
- **How to comply:** add the new check or field once, in the shared module;
  routes call `<feature>_write_error_response(outcome, …)` and handle only
  what is theirs (not-found, a confirmation guard) before it.
- **Violation signal:** the same `if _Response.<flag>: return bad_request(…)`
  ladder in two routes; two request models that differ by one id field.
- **Established:** 2026-10-24 (finalisation 01-R12/R13, 02-R7/R8). See ADR-094.

### R-098: A stored instant read back is made aware through `as_utc`, never inline
- **Rule:** comparing a `DateTime(timezone=True)` value read from the database
  against an aware bound goes through `persistence/aware.as_utc(dt)`. No module
  writes its own `dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt`.
- **Why:** SQLite drops tzinfo on read, so every comparison against
  `datetime.now(UTC)` needs the coercion, and the finalisation review found
  eight hand-written copies (stocktake ×2, the sweep, reconcile, buy verdict,
  reports, deal quality, suggestions), each with its own comment explaining the
  same SQLite fact (05-R9). A missed one is a 500 (FU-526 was exactly that).
- **How to comply:** `as_utc(item.snoozed_until) > now`. Converting to a
  household *date* is a different job (`household_timezone`), not this one.
- **Violation signal:** `tzinfo is None` next to `replace(tzinfo=` in a feature
  module.
- **Established:** 2026-10-24 (finalisation 05-R9). See ADR-095.

### R-099: A spend figure is built from `spend_lines`, never its own list-and-line query
- **Rule:** any total of what the household spent over finished shopping lists
  (budget period, budget history, every Reports spend card, a count of bought
  items) reads `shopping_lists/_line_price.spend_lines(session, since, until)`
  and sums `SpendLine.spent`. The lifetime single-number aggregate is
  `lifetime_spend`, which applies the same rule in SQL. No module writes its
  own "done lists in the window, ticked lines, actual-then-picked price" query.
- **Why:** the rule was written seven times (five Core SQL, two through the
  repository) and had already drifted: only the budget skipped lines deferred
  by trim-to-budget, quantity 0 counted as 1 in two reports and as nothing in
  two others, so the budget card and Reports could disagree on one week
  (finalisation 12-R10).
- **How to comply:** `sum(line.spent for line in spend_lines(repo.session, start, end))`;
  bucket by `line.completed_at` for a series. A new filter (a new kind of
  not-really-bought line) goes into `spend_lines` once. The parity test
  `test__spend_totals_agree_across_budget_and_reports` pins the agreement.
- **Violation signal:** `SHOPPING_LIST_STATUS_DONE` beside `is_ticked == True`
  in a feature module other than `_line_price.py`.
- **Established:** 2026-10-27 (finalisation 12-R10). See ADR-096.


### ADR-001 — Adopt engineering standards + mandatory explain-or-flag gate
- **Date / task:** 2026-06-06 (user request after repeated theme/component regressions)
- **Status:** accepted
- **Context:** The same architectural/style cleanups (themes, `BaseButton`, dialog
  chrome, server/client state duplication) kept being re-introduced by later work
  that never saw the rule, because the rules lived only in finished proposal docs.
- **Decision:** Establish this doc as the standing engineering rubric, loaded into
  every session via `CLAUDE.md`. Seed R-001..R-009 from the Charter, the
  state-ownership proposal, the theme audit, the followups backlog, and memory.
  Every task is checked against the rules; any violation must be fixed, explained
  in place (comment naming the rule), or flagged in `DORA_FOLLOWUPS.md` — an
  unexplained violation **blocks the work unit from closing.** Each task is
  evaluated for whether a new rule/ADR is warranted.
- **Consequences:** A small per-task overhead (the check + the close-gate) buys
  consistency and stops re-cleanup. Rules grow only through ADRs, keeping the set
  grounded. The seed set is deliberately partial — more rules accrete as decisions
  recur, rather than from an exhaustive up-front sweep.
- **Promotes rule:** R-001 through R-009 (seed set).

### ADR-002 — Optional features gate on a server-owned flag surfaced via health capabilities
- **Date / task:** 2026-06-07 (P6-02 barcode/QR cleanup)
- **Status:** accepted
- **Context:** Optional/off-by-default surfaces (the LLM assistant, now scanning &
  QR labels) need one authoritative on/off switch that both the server and every
  client entry point respect, without the client hardcoding the policy or each
  feature inventing its own toggle mechanism. Two instances now share the shape
  (`AppSetting.llm_enabled`, `AppSetting.scanning_enabled`).
- **Decision:** An optional feature is gated by a single boolean on the
  install-wide `AppSetting` singleton (default `false`), exposed to clients through
  the health capability endpoint as `features.<name>`, and consumed by a tiny
  composable (e.g. `useScanningEnabled()`) — **not** a new Pinia store. The admin
  toggle lives in Settings → System and PATCHes the setting. One flag gates the
  whole surface (anti-creep), not per-control toggles.
- **Consequences:** Adding a gated feature is a known recipe (AppSetting field →
  health flag → composable → admin toggle). Distribution-posture-correct: the same
  artifact self-hosts or runs managed; the difference is config, not a build fork.
  Rules out scattering feature policy across client code or spinning up a store per
  flag. Health flags are the single read path — keep `_feature_flags()` honest
  (this task fixed a latent bug where `assistant` never reflected the real setting).
  **Presentation:** when the flag is off, entry points **hide** — this is the
  R-029 rule (ADR-025). The 2026-06-14 ADR-009 / R-014 "reveal-and-disable"
  detour that partially revisited this presentation was walked back on
  2026-07-06; ADR-002's original hide-when-off is the whole story again.
- **Promotes rule:** none (a pattern/recipe, not a new standing rule; R-003
  state-ownership already covers "server owns domain facts").
- **See also:** R-029 / ADR-025 (the presentation rule this ADR relies on).

### ADR-003 — Strong types over stringly-typed matching
- **Date / task:** 2026-06-07 (P6-01 Chunk 1; user request)
- **Status:** accepted
- **Context:** The new shopping-list lifecycle e2e surfaced a guard that compared a
  `ShoppingList`/`ShoppingListLine` `UUID` against a Flask path param (always a
  `str`); with no uuid converter registered the comparison never matched, so every
  line tick/delete silently 404'd (FU-059). The expedient patch — `str(x) != str(y)`
  — works but keeps both sides weakly typed and side-steps the type system rather
  than carrying the real type. The user asked to make "prefer strong types, don't
  side-step the compiler" a standing rule.
- **Decision:** Adopt R-010. Model values with the strongest available type; coerce
  external input to its real type once at the boundary; prefer enums/literal unions
  and typed comparisons over scattered string matching; never add
  `any`/`@ts-ignore`/`# type: ignore` to silence a checker that is correctly
  objecting. Closed-set status sentinels backed by a `*_VALUES` set + single
  validation point remain an accepted lightweight enum stand-in.
- **Consequences:** Pushes a class of runtime bugs back to compile/type-check time
  (free, always-on review). Costs a little up-front discipline (boundary coercion,
  defining enums/unions) and means future cleanup may *strengthen* the `str()`-patched
  line guards to typed ids rather than leave them. Rules out "stringify both sides to
  make it pass" as an acceptable fix.
- **Promotes rule:** R-010.

### ADR-004 — Use the framework's idiomatic, current-recommended pattern
- **Date / task:** 2026-06-09 (FU-087 FilterBar bug; user request)
- **Status:** accepted
- **Context:** `FilterBar.vue` shipped a hand-rolled controlled/uncontrolled
  `modelValue` pattern (manual prop + `update:modelValue` emit + a `computed`
  getter/setter), and read `$q.screen.gt.sm` without the Quasar Screen plugin
  being activated in any boot file. Two latent bugs collided in production:
  Vue 3 coerces an unset Boolean prop to `false`, so the `props.modelValue ===
  undefined` sentinel that distinguished controlled-vs-uncontrolled never
  fired (every consumer got `false`, the panel never opened, clicks went to
  a dead getter); and `$q.screen` returns `width: 0` until `setSizes()` /
  `setDebounce()` activates the listener, so the "open on desktop" default
  silently failed on every viewport. Both regressions were invisible to
  static type-checking and produced no console output. Vue 3.4 ships
  `defineModel()` (the recommended v-model macro) and Quasar 2.x documents
  Screen activation in a boot file; using both fixes the bugs and shortens
  the code.
- **Decision:** Adopt R-011. When the framework ships a primitive for the
  problem, use it; when a plugin needs activation per the framework docs
  (Quasar Screen, etc.), wire it in `src/boot/` and register in
  `quasar.config.ts`. Prefer current-recommended patterns for the pinned
  framework version (Vue 3.4+ → `defineModel`, `<script setup>`;
  Quasar 2.x → its plugin activation conventions).
- **Consequences:** New code tracks Vue/Quasar/Flask upstream and benefits
  from upstream bug fixes automatically. Reviewers can spot violations
  quickly (manual `update:modelValue` plumbing, unactivated plugin reads).
  Legacy hand-rolled equivalents stay until next touched — no opportunistic
  rewrite sweep.
- **Promotes rule:** R-011.

### ADR-005 — Opt-in / capability flag reads go through one composable per family
- **Date / task:** 2026-06-11 (C-cross Chunk 1)
- **Status:** accepted
- **Context:** C-cross's install-wide feature flags (proposal §2.6) plus
  the per-user opt-ins (money, nutrition, image display) need a uniform
  client read path. Without one, every new flag risks a new Pinia store
  + a new health probe + a new read site convention. The
  `useScanningEnabled` / `llm_enabled` pair already shipped under
  ADR-002 with a single-flag composable each — that's fine for one or
  two flags, but C-cross is bringing in five install flags + two per-user
  flags + a reserved nutrition seam. Multiplying single-flag
  composables is the wrong path.
- **Decision:** **One composable per feature *family***, not per flag.
  Install-wide flags live behind **`useFeatureFlags()`** which reads
  `/api/health features.*` once per session and exposes a named
  computed per flag (`features.money`, `features.nutrition`, etc.).
  Per-user flags live behind tiny family composables —
  `useMoneyEnabled()` / `useNutritionMode()` / `useImagePrefs()` — that
  layer the install bool from `useFeatureFlags()` with the per-user
  value read from `/api/users/me`, returning a single ready-to-render
  boolean or enum. Consumers never read AppSetting or User columns
  directly; they call the composable. The composable owns the cache
  refresh (`refresh()` after an admin PATCH; user-flag composables
  refresh after `authStore.updateMeAsync()`).
- **Consequences:** Adding a flag is a known recipe (column → DTO →
  `_feature_flags()` map → composable key → consumer). Eliminates a
  class of "two surfaces read the same flag and one misses a
  refresh" bugs. Costs one indirection between consumer and store,
  but the indirection is the point — the layering rule (install AND
  per-user) lives in one place.
- **Promotes rule:** none directly; reinforces R-001 (single shared
  primitive) + R-003 (server owns the fact, client doesn't shadow it)
  + ADR-002 (this is the consolidated form of the per-flag composable
  pattern ADR-002 seeded).

### ADR-006 — Working features stay visible; overflow menus only for rare/destructive actions
- **Date / task:** 2026-06-12 (shopping-list UX v2 build, user directive)
- **Status:** accepted
- **Context:** The shopping-list surface hid its everyday actions behind two
  layers of unlabelled ellipsis menus, styled its price editor as a tiny text
  chip and its shop-day setter as a plain text link. The user repeatedly
  failed to discover features that existed (their words: "If it's hidden,
  the user is less likely to find it exists … keep features visible/easily
  reachable as much as possible — this should be an engineering rule").
- **Decision:** Adopt R-012. Everyday actions get visible labelled controls
  (toolbar / on-row); overflow menus are reserved for rare or destructive
  actions and are labelled "More"; clickable things must look clickable.
- **Consequences:** Toolbars carry more visible buttons (acceptable — that's
  what the toolbar is for); audits of a surface now include "is anything
  load-bearing hidden in a kebab?". Rules out the reflex of shoving new
  actions into an existing ⋮ to avoid layout work. Dense-list rows keep a
  narrow carve-out for per-item housekeeping.
- **Promotes rule:** R-012.

### ADR-007 — API JSON serialises dates/datetimes as ISO 8601
- **Date / task:** 2026-06-12 (shopping-list UX v2 build)
- **Status:** accepted
- **Context:** Flask's default JSON provider emits `date`/`datetime` as
  RFC 1123 ("Tue, 01 Sep 2026 00:00:00 GMT"). Every client-side string
  comparison against ISO dates silently failed — the route guard's
  `planned_shop_date === '2026-09-01'` never matched (so today's-list
  landing never worked), and the Chunk-7 e2e tests that asserted ISO had
  never passed. Found while adding `effective_date` / `next_up_list_id`.
- **Decision:** `DoraJSONProvider` on the Flask app (`dora_api/app.py`):
  `datetime` → `isoformat()` (offset included), `date` → `YYYY-MM-DD`.
  New API fields assume ISO; client code may compare/sort date strings
  lexicographically (ISO sorts correctly; RFC never did).
- **Consequences:** Every date/datetime in every response changed format —
  one-off risk absorbed now (JS `new Date()` parses ISO at least as well as
  RFC), in exchange for date equality/sorting working at all. Rules out
  per-endpoint string formatting of dates in DTOs.
- **Promotes rule:** none — it's one global setting, not a recurring
  decision; R-003/R-010 already cover "don't stringly-type domain values".

---

### ADR-008 — E2E API tests run through the Flask test client, not a live server
- **Date / task:** 2026-06-13 (FU-166 legacy e2e suite triage)
- **Status:** accepted
- **Context:** The e2e suite booted a werkzeug dev server in a background
  thread and drove it with `requests` over loopback TCP. ~300 tests took
  ~13.5 min (~2.7s each) — real connection setup, the Windows `localhost`
  IPv6-fallback penalty, and the dev server's `Connection: close` defeating
  keep-alive. The slow fix→verify loop made the suite a maintenance liability,
  and ~40% of it had silently drifted off the current API contract.
- **Decision:** Adopt R-013. The `api` fixture dispatches in-process via
  `app.test_client()` and rebinds `requests.*` + `requests.Session` to thin
  adapters, so test bodies are untouched. Fixture made `autouse` to remove the
  latent ordering dependency (tests that didn't request `api` only worked when
  another test had already triggered the global rebind).
- **Consequences:** Suite runs in ~6s (~95× faster), behaviour-preserving
  (identical fail/pass set on the swap). Loses the literal network/WSGI
  boundary from the default path — acceptable for API contract tests; a real
  cross-process test must opt back into a live server and say so (R-013
  carve-out). Adapter must grow to cover any new transport feature
  (multipart already handled).
- **Promotes rule:** R-013.

---

### ADR-010 — Deterministic constraint names everywhere (SQLite batch-mode)
- **Date / task:** 2026-06-17 (resolving FU-178)
- **Status:** accepted
- **Context:** Fresh-SQLite `flask db upgrade base→head` was broken: chain
  died at `d7c9e4a8c2b1_20260612_shopping_list_line_product_anchor` with
  `ValueError: Constraint must have a name`. SQLite has no
  `ALTER TABLE ADD/DROP CONSTRAINT`; Alembic batch mode therefore rebuilds
  the table, and an unnamed constraint can't be re-emitted on the rebuild.
  Several historical tables were defined with anonymous UNIQUE/CHECK/FK
  constraints, so any later `batch_alter_table` against them tripped. Tests
  bypass this (they use `drop_all + create_all`), but a real prod boot from
  base would not.
- **Decision:** Adopt a project-wide naming convention on the SQLAlchemy
  `MetaData` (`fk_/uq_/ck_/ix_/pk_` + table + column0); thread it into
  Alembic's context in `migrations/env.py`; wrap `op.batch_alter_table` in
  `env.py` so every batch operation inherits it without each call site
  having to pass `naming_convention=`. Hard cutover: no compat shims, the
  project is pre-release. Constraint *literals* in migrations use the bare
  suffix (`'shopping_list_line_anchor'`); the convention adds the type prefix.
- **Consequences:** Base→head `flask db upgrade` is clean. Downgrade-from-head
  to base trips on a small number of legacy migrations that hard-coded
  `ck_*`-style literals (double-prefix under the convention); accepted —
  downgrade-from-head is not a product flow, dev resets go through
  `drop_all`/`DORA_ALLOW_DESTRUCTIVE`. Anyone hand-writing future migrations
  must follow the bare-suffix rule (R-015). Postgres path also benefits:
  constraint names become deterministic and grep-able.
- **Promotes rule:** R-015.

### ADR-009 — Reveal-and-disable unconfigured features instead of hiding them
- **Date / task:** 2026-06-14 (IMPL_PLAN_MEAL_PLANS review, user directive)
- **Status:** superseded by ADR-025 (2026-07-06)
- **Context:** Gating discussion for the meal-plan sequential builder's Email
  button — SMTP may be unconfigured per install (INV-4). The user wants
  features advertised so users get interested and adopt them, but with the
  off/unconfigured state obvious. This refines ADR-002, which hid off-by-default
  gated surfaces entirely; the user's example is that the `scanning_enabled`
  button should now show **disabled**, not vanish.
- **Decision:** Adopt R-014. Surface an adoptable feature's entry point in a
  visible disabled "not set up" state with a path to enable, rather than hiding
  it; gate *functionality* (not visibility) on the flag. Apply with judgement —
  inapplicable or security-sensitive surfaces may still be hidden.
- **Consequences:** Gated features become discoverable; each gated surface now
  needs a disabled-state affordance + reason. Partially revisits ADR-002's
  hide-when-off *presentation* (the functionality gating is unchanged).
  App-wide application (the scanning button, any other hidden gated surfaces)
  is a follow-up sweep, not a blanket immediate change.
- **Promotes rule:** R-014.

### ADR-011 — Lazy store hydration; boot doesn't block app mount
- **Date / task:** 2026-06-18 (user query: boot-time preloading vs best practice)
- **Status:** accepted
- **Context:** `web_app/src/boot/stores.ts` had been a top-level `await` of an
  API health check + three collection fetches (`productStore`,
  `stockItemStore`, `stockLevelStore`). That blocked the router/app mount
  until everything resolved — exactly the wrong shape for perceived speed —
  and the file had drifted: `productStore` was still being preloaded long
  after Phase D moved products to an overlay, so every cold start paid for a
  fetch that almost no surface read. Several pages had also grown a private
  inline guard (`if (store.items.length === 0) await getXAsync()`) that
  duplicated the same intent across files.
- **Decision:** Adopt R-016. Stores hydrate lazily via `ensureLoadedAsync()`
  (cached + in-flight dedupe). Pages own their data hydration on mount.
  `boot/stores.ts` was **deleted outright** (and removed from
  `quasar.config.ts`); the API-reachability surface that the old boot
  health-check covered is already owned by `authStore.bootstrapAsync()` in
  `App.vue`, which sets `bootstrapError` and is rendered by `SplashScreen`
  with a Retry button — that is the canonical "backend is down" affordance.
  `getXAsync()` remains the explicit force-refetch for mutations /
  pull-to-refresh / reload affordances.
- **Consequences:** App shell mounts instantly; pages opt into the data
  they need; there is no longer a drift-prone "what to preload" list in a
  boot file. The cold-path landing page (typically the dashboard) pays a
  small first-fetch cost on first visit instead of paying it for every cold
  start regardless of where the user lands. Stores grow one extra method
  each. Remaining pages still calling `getXAsync()` unconditionally in
  `onMounted` (MealPlans / RecipeDetail / RecipesOverview / StockItemDetail
  / StockOverview) are an opportunistic follow-up — they work today, but
  each re-fetches on every visit instead of trusting the cache.
- **Promotes rule:** R-016.

### ADR-012 — Seed-data discipline: feature changes carry seed updates
- **Date / task:** 2026-06-22 (FU-227 chunk 8; user request raised in the
  pricing-system reassessment, locked in §9 of the handoff doc).
- **Status:** accepted
- **Context:** Repeatedly a feature has landed clean (vue-tsc + lint + tests
  green) but a fresh `DORA_ALLOW_DESTRUCTIVE` reset produced no row that
  triggered the new code path. The next agent — or the user, doing a browser
  walk — had to manually fabricate state to see the feature render. The
  "Your prices" widget made this acute: without the chunk-2 observation
  seed (3+ obs / 1 above-1.15× / count dimension / store-tagged / <
  MIN_SAMPLES variants), the widget renders the empty state on every item
  and the above-usual chip is invisible. Seed reviews lagged code reviews
  by a chunk, then two, then a whole feature pack. The user asked for this
  to be a standing rule.
- **Decision:** Adopt R-017. Every feature-touching diff opens `seed.py` in
  the same unit of work and ensures the **state matrix** the feature renders
  is exercised in the fresh seed — happy path + the obvious edges (empty,
  threshold, below-minimum, error-y). Pure refactors, bug fixes that don't
  introduce a new state, and explicit removals are carve-outs but must be
  named in the worklog. Existing seed helpers (`make_item`, `make_product`,
  `price_obs`, ...) are the preferred extension point — extract a new helper
  on the third use.
- **Consequences:** Marginal per-chunk overhead (open the seed; add a few
  rows; verify with a fresh reset). Big payoff: the close-gate browser walk
  becomes a real walk (every state matrix visible without hand-clicking),
  the dev env stays honest, future agents picking up cold see the feature
  the same way the user does. Rules out the lazy "I'll seed it later" path
  that always drifts. Doesn't replace e2e tests — seed is the *visible*
  surface; tests are the *correctness* surface.
- **Promotes rule:** R-017.

### ADR-013 — Optional engines degrade gracefully; never hard-pin a cross-platform-breaking dependency
- **Date / task:** 2026-06-23 (Piper TTS wiring — chat + cook mode + voice
  settings).
- **Status:** accepted
- **Context:** Wiring Dora's neural voice meant depending on Piper. The obvious
  move — add `piper-tts` to `requirements.txt` — turned out to break the install
  on Windows: `piper-tts`'s `piper-phonemize` has no Windows wheel, so
  `pip install -r requirements.txt` fails outright, and Dora ships as a Windows
  desktop app. The feature is also inherently optional: without Piper the app
  can still speak via the browser's Web Speech API. This is the same shape the
  LLM assistant already has (BYO Ollama, off by default, rule-based fallback).
- **Decision:** Adopt R-018. Optional external/native engines (a) must degrade
  gracefully when absent — app still boots; surface hides/disables/falls back —
  and (b) must not be hard-pinned in `requirements.txt` when they can't install
  cleanly on every supported platform. Gate behind a runtime availability probe
  (`/api/tts` checks for the `piper` binary + the selected voice model; returns
  503 with a setup hint; the SPA's `useSpeechOutput` then uses browser speech).
  Ship the engine automatically where clean — the **Docker image** installs
  `piper-tts` in a `RUN` step, the **desktop bundle** ships the prebuilt binary
  (fetched by `packaging/fetch_piper.py`, bundled by `dora.spec`, pointed to by
  `desktop_app.py`); document the install for bare source/pip runs. **Voice
  models are not in git** — they're downloaded on demand into the data dir
  (`voice_provision.py`, checksum-verified) when the user picks one in
  onboarding / Settings → Voice. No manual end-user steps; no repo bloat.
- **Consequences:** `requirements.txt` keeps installing everywhere; the neural
  voice is a progressive enhancement, not a gate, and "works out of the box" on
  the shipped artifacts without bloating the repo or forcing manual setup. Cost:
  the engine isn't guaranteed present on bare source runs, so every call site
  needs the probe + fallback (already the pattern for the LLM); the desktop
  binary-bundling is per-OS build wiring that can't be verified without a build
  runner (flag it as a build/browser-walk item, not "tested"). Runtime model
  download adds a one-time per-voice fetch + a checksum/atomic-rename path to
  get right (a partial download must never read as "ready").
- **Promotes rule:** R-018.

### ADR-014 — No magic: explicit, verbose, consistent
- **Date / task:** 2026-06-28 (user message promoting FU-084 from its
  original narrow scope into a top-line engineering value).
- **Status:** accepted
- **Context:** FU-084 originally proposed promoting the SQLAlchemy
  `lazy="selectin"` shortcut (added on `Recipe.cuisine`/`.category` so the
  ~10 read sites didn't each need an explicit `.include()`) into a
  standing rule for "small always-wanted lookups". The user pushed back
  on the *meta*-shape rather than the specifics: that kind of "this
  relationship loads itself, but only because we picked it; the others
  don't" is exactly the **magic** they want the codebase to avoid. They
  reframed it as a broader rule: prefer **verbose, explicit code** with
  **no guess-work**; reject "*most times it's done this way, but in
  these few places we decided to do it another way because it felt
  right*" inconsistency; explicitly cited C# AutoMapper as the
  archetypal misfeature.
- **Decision:** Adopt R-019. Explicit, verbose, locally-readable code
  beats clever / implicit / auto-discovered behaviour. When the codebase
  has an established pattern for a problem, *follow it* — don't introduce
  a parallel approach in one spot because the alternative looks tidier
  in isolation. Auto-mapping libraries (AutoMapper-shaped reflection
  between layers) are banned; mappers are hand-written, one named
  function per direction, every field listed. Decorator/metaclass magic
  that *mutates* behaviour stays in framework code, not feature code we
  own. SQLAlchemy relationship loading defaults stay codebase-wide
  (`noload`); per-entity `lazy="selectin"` overrides are themselves a
  flavour of magic (the read site no longer reflects what it loads) and
  should be retired in favour of explicit `.include()` / `selectinload()`
  at the call site. Existing per-entity `selectin` opt-ins from before
  this rule (`Recipe.cuisine`, `.category`) are grandfathered for
  R-007's scope-discipline reasons — flagged as a follow-up cleanup,
  not refactored this session.
- **Consequences:** New mapper code is more verbose (one named function
  per direction, every field listed) — that verbosity *is* the value:
  greppable, type-checked end-to-end, no silent breakage when a field
  is renamed three files away. New SQLAlchemy queries always declare
  what they load at the call site; the entity stays a passive shape.
  Reviewers can read a diff and check rule-fit with no convention to
  consult. Cost: short-term, more lines for hand-written mappers + a
  recurring nag against the temptation to reach for a "smart" decorator
  / convention / auto-loader.
- **Promotes rule:** R-019.

### ADR-018 — DnD reorderable lists go through `useDragDropList`
- **Date / task:** 2026-06-29 (FU-326 extraction).
- **Status:** accepted
- **Context:** Three reorderable-list surfaces in the web app
  (shopping-list lines [P6-01 Chunk 6], structured recipe steps
  [FU-094], recipe ingredients [FU-118]) had each grown its own
  hand-rolled HTML5 DnD plumbing: `dragLineId` / `draggingClientId` /
  `draggingIngredientClientId` refs that all meant the same thing;
  near-identical `@dragstart` / `@dragover` / `@dragleave` / `@drop`
  handlers; and three slightly-different CSS treatments for "source
  being dragged" (opacity 0.4 vs 0.5) and "active drop target"
  (outline-dashed vs box-shadow ring). The shape was always: guard
  the drag with a MIME token, light the drop target, dim the source,
  call a per-list "insert source at target's slot" effect on drop.
  Only two things genuinely differed: the drop-target predicate
  (anything / siblings-only / per-row guarded) and the per-drop
  effect (server reorder API / local reorder / local reorder +
  section reassignment). The shared surface area is exactly what
  an abstraction should own.
- **Decision:** Extract `web_app/src/composables/useDragDropList.ts`
  (state machine + per-row bindings) and `web_app/src/css/dnd.scss`
  (`.dora-dnd-row` / `--dragging` / `--drop-over` / `.dora-dnd-handle`).
  All three existing surfaces refactor onto it. New DnD lists go
  through it from day one. Two row shapes are supported:
  **handle mode** (small drag-grip icon is the only draggable
  element; row body keeps default cursor so inline editors stay
  interactive — used by both recipe editors) and **whole-row mode**
  (the whole row is grabbable — used by shopping-list lines where
  rows have no inline editors). The composable doesn't care which;
  it's a matter of where the consumer spreads `handleProps`.
- **Consequences:**
  - **Removed code** (~190 lines net): ~50-line drag block in
    `RecipeStepsEditor.vue` + ~50-line block in `RecipeStepRow.vue`,
    ~75-line block in `RecipeDetailPage.vue`, ~70-line block in
    `ShoppingListDetail.vue`, plus three near-duplicate CSS rule
    sets — replaced by one composable (~190 lines incl. JSDoc) and
    one shared stylesheet (~50 lines). The composable is bigger
    than any single removed block, but the *aggregate* shrinks and
    every future DnD surface is ~10 lines.
  - **Visual consistency**: source dim, drop-target ring, and
    handle treatment now identical app-wide (one shared `--motion-
    fast` transition, `--brand-primary` ring, 0.5 opacity). A user
    who learns one DnD list reads the next correctly.
  - **One MIME convention**: `application/x-dora-<thing>` enforced
    by the composable's `mime` option, so cross-list drops can
    never accidentally satisfy a dragover check.
  - **Plumbing cost**: the composable's `bind(item)` returns
    fresh closure objects on each call, so calling it 3× per row
    in a template (rowClass, rowProps, handleProps) re-allocates
    on every render. For the lists we have (10-50 rows) this is
    negligible; if a much larger DnD list ever ships, the obvious
    optimization is a memoizing wrapper keyed on the item id.
  - **Future**: multi-row drag, drop into off-row zones (e.g.
    "drop here to put into an empty section"), and keyboard
    reordering for accessibility are all extensions to this one
    composable rather than three parallel implementations.
- **Promotes rule:** R-022.

### ADR-019 — Test naming + shared response matchers
- **Date / task:** 2026-06-29 (FU-169 Phase 1 —
  `PROPOSAL_TEST_SUITE_IMPROVEMENTS.md` §C / §F).
- **Status:** accepted.
- **Context:** FU-166 spent days realigning ~40 inline RFC-7807
  problem-detail assertions across the router suite when the error
  contract moved (the same `assert resp.status_code == 400;
  assert resp.headers['Content-Type'] == 'application/problem+json';
  assert 'errors' in resp.json()` triplet, written out every time).
  The same audit found two naming conventions running in parallel —
  `test__get_x__Condition__Result` (older router tests) and
  `test_create_with_..._roundtrips` (newer suites) — which made the
  failure summary jagged and prevented uniform parametrize / grep
  patterns. Both are duplication-of-contract problems: the test
  suite is asserting the same shape (or naming the same thing) in
  many places, so a contract or convention move ripples through ~40
  files instead of one.
- **Decision:** Adopt **`assert_problem` + `assert_envelope`** in
  `tests/support.py` as the canonical matchers for the two repeated
  shapes; the proposal's §C names exactly these two. Adopt the
  behavioural naming convention
  `test__<unit>__<condition>__<result>` for new tests, with a
  per-edit migration policy for existing names (don't open a
  rename-all PR; rename when you're already editing the file).
  Codified as R-023.
- **Consequences:**
  - **Future contract moves are a one-file fix.** When the
    problem-detail shape changes again, `assert_problem` is the
    single update site; ditto for the list envelope.
  - **Per-edit migration** keeps the rename cost amortised — every
    PR that touches a test brings it into line, no big-bang
    cleanup needed.
  - The shared matchers add ~80 lines to `tests/support.py`; this
    pays back the moment more than ~6 callers exist, which is
    already true.
  - **Doesn't ban inline assertions in non-router tests.** Domain
    unit tests assert plain objects; the matchers are for the
    HTTP-contract surfaces only.
- **Promotes rule:** R-023.

### ADR-016 — Calendar-day boundaries run in the household timezone
- **Date / task:** 2026-06-29 (FU-174 close-out sweep; mechanism shipped
  with C-2.K on 2026-06-14).
- **Status:** accepted
- **Context:** Python's `date.today()` returns the server-local date.
  For a self-hostable household app (R-005 distribution posture), the
  server can be anywhere — a managed deploy in Frankfurt with a
  Sydney household crosses midnight by 9–11 hours, and every
  "expiring today" / "next 7 days" / "scheduled for today" decision
  silently desyncs ±1 day. The meal-plan past-day-drop bug (F29 from
  the feedback round) was the surface — fixed locally in C-2.K with
  `AppSetting.timezone` (IANA string), `clock.resolve_timezone`, and
  `household_today(repository)`. The FU-174 audit found 15+ other
  `date.today()` sites in alerts / dashboard / suggestions /
  assistant tools / budget / waste / location attention / shopping
  lists / recipes / stock items, each one a latent F29-shape bug.
- **Decision:** Adopt R-021. `clock.household_today(repository)` is
  the single entry point for "what calendar day is it". Every
  feature handler that gates on "today" uses it; `date.today()` is
  reserved for seeds/fixtures. Wall-clock events keep
  `datetime.now(UTC)` (different concern: when, not which day).
  Storage stays mixed by intent — `DateTime(timezone=True)` for
  events, `Date` for calendar values — and the boundary check is
  where the timezone lives, not the value.
- **Consequences:** Every new feature with a date boundary now
  has one canonical path and reviewers have a one-line grep target
  (`date.today()` in feature code = violation). The household
  timezone lives in one column, set once per install; changing it
  cascades through the app correctly. Cost: handlers that compute
  "today" must take a repository argument so the helper can read
  `AppSetting`. The few that didn't have one already (a handful in
  budget / waste / location attention) gain one — minor plumbing.
  The client is intentionally not authoritative: it reads
  `mealPlanStore.todayIso` (or the equivalent server-fetched
  boundary); any client-side "today" computation is a display
  fallback, never a decision.
- **Promotes rule:** R-021.

### ADR-015 — Deferred-save surfaces must wire the unsaved-changes guard
- **Date / task:** 2026-06-29 (FU-098 close-out sweep).
- **Status:** accepted
- **Context:** `useUnsavedChangesGuard` shipped on 2026-06-12 (FU-156)
  after the user repro'd silently-discarded recipe edits — root cause
  was a per-handler `onBack` confirm that didn't fire on sidebar
  navigation. The composable wraps `onBeforeRouteLeave` +
  `onBeforeRouteUpdate` + `beforeunload` and was wired into
  `RecipeDetailPage` + `StockItemDetailPage` at that time. FU-098 then
  asked for the broader sweep. The audit found exactly two additional
  pages that fit the shape (account settings, install AI-config
  settings) and ~22 surfaces that *looked* like candidates but
  legitimately don't need the guard (save-on-blur settings, dialog
  Saves, cook-mode session state, etc.). The recurrence — two
  separate "we built another deferred-save page and forgot the
  guard" events six weeks apart — is the rule-worthy signal: without
  a standing rule, the audit will need to run again every time
  another draft-state page lands.
- **Decision:** Adopt R-020. Every page with a dedicated Save action
  and locally-mutable draft state wires `useUnsavedChangesGuard` with
  a dirty predicate derived from the same `unchanged` / `isDirty`
  computed that gates the Save button itself. The four exclusion
  categories (inline-save, real-time session, dialog-only, password
  fields) are documented in the rule so future audits can ratify or
  reject quickly. No reinvention of the discard-prompt copy or the
  route-level wiring — both live in the composable.
- **Consequences:** New editor pages cost one additional one-line
  call (`useUnsavedChangesGuard(...)`) plus the dirty-predicate
  expression they already need for the Save button's `:disable`.
  Reviewers can grep for "Save" + missing `useUnsavedChangesGuard` to
  catch the violation in a diff. The rule's exclusion list doubles
  as an audit checklist — re-running the FU-098 sweep on a new
  candidate page is now a five-minute "which category does this fit?"
  check, not a 30-minute file-by-file read.
- **Promotes rule:** R-020.

### ADR-020 — One image-source picker for the SPA (Take photo / Choose image)
- **Date / task:** 2026-06-30 (FU-334 follow-on).
- **Status:** accepted
- **Context:** The first cut of receipt-photo upload for shopping lists
  used a single `<input accept="image/*" capture="environment">` button.
  On Android Chrome that biases straight to the rear camera with no
  gallery option, defeating the common "let me pick a receipt photo my
  partner already took" path. An audit of the existing image-upload
  surfaces (recipe hero, recipe step images, stock item image, user
  avatar, store logo, product image, recipes detail) found three
  different upload shapes: `ImageUploadField` (4 consumers), a bespoke
  `<input>` in `RecipeStepImagesEditor`, and a Quasar `q-file` in
  `StoresSettings` — each made its own camera-vs-gallery choice
  silently, and none offered both consistently. R-003 already pinned the
  resize/encode chokepoint at `processImageFile`; the *pick UX* was the
  matching gap.
- **Decision:** Adopt R-024. A single SPA-wide
  `ImageSourcePicker.vue` primitive renders the two-affordance
  picker (Take photo + Choose image), detects touch-primary devices via
  `pointer: coarse` to decide whether to surface the camera button, owns
  the hidden inputs (one with `capture="environment"`, one without), and
  calls `processImageFile` internally. Consumers receive a
  `ProcessedImage` via `@pick`. `ImageUploadField` composes the
  primitive internally so its 4 existing consumers (stock item, recipe
  edit, recipe detail, user avatar) gain the camera affordance with no
  per-site change. `RecipeStepImagesEditor` and the new receipts UI use
  the primitive directly.
- **Consequences:** Camera-vs-gallery becomes one platform-aware
  decision instead of N per-site decisions. The "Take photo" button
  appears only where it makes sense (mobile / touch tablet), so desktop
  isn't cluttered with a no-op control. Multi-file flows compose the
  primitive with `multiple` — each file emits its own `pick` in order;
  the parent decides batching. Cost: one indirection layer; the
  primitive is ~100 lines and small enough to read end-to-end. The
  scanning case (iOS Files → Scan Documents) reaches users via the
  Choose-image path on iOS — no dedicated scan button needed.
  `StoresSettings.q-file` stays as a single carve-out tracked under
  FU-335.
- **Promotes rule:** R-024.

### ADR-021 — Session-mutating auth writes need password re-proof + CSRF
- **Date / task:** 2026-06-30 (FU-197).
- **Status:** accepted
- **Context:** A senior security review flagged two coupled gaps in the
  authentication surface that, together, formed a full account-takeover
  chain: (a) `request_email_change` required no `current_password`
  proof (asymmetric with `change_password`, which did) and (b) no CSRF
  defence existed at all (`SameSite=Lax` alone, no token / Origin
  check). Investigation surfaced a third gap: the SPA's
  Settings → Email "Save" actually called `PATCH /auth/me` with
  `{"email": …}`, which the backend silently accepted — the verified
  flow at `POST /auth/me/email` existed but was never reached. Three
  asymmetries (between flows, between defences, between intended and
  actual code paths) compounding.
- **Decision:** Adopt **R-025**. Close every asymmetry at once: remove
  `email` from `UpdateMeRequest` (`extra="forbid"` then rejects the
  legacy path with 400); require `current_password` on `ChangeEmailRequest`
  and verify in the handler; notify the **old** address before issuing
  the confirmation token to the new one; introduce double-submit CSRF
  in `dora_api/infrastructure/csrf.py` + `middleware.py` (cookie
  auto-issued on every response without one, header required on every
  mutating call against a non-public, non-bearer endpoint, constant-time
  compare). SPA axios interceptor reads the cookie and attaches the
  header. Public endpoints (login/register/forgot/reset/verify/
  bootstrap) are exempt so a cold client can authenticate; bearer-auth
  `submit_ingestion_batch` exempt because Bearer tokens aren't
  browser-ambient. Dev-only `DORA_CSRF_DISABLED=1` escape hatch refuses
  to weaken production. Test conftest mirrors the axios interceptor so
  the existing suite stays transparent; explicit CSRF tests bypass that
  helper by passing `X-CSRF-Token: ""` to confirm the gate fires.
- **Consequences:**
  - Every future auth-identity write (password, email, recovery
    channel, API key) is now expected to ship both halves of R-025.
    Asymmetry between sensitive flows becomes a violation rather than
    a judgement call.
  - SPA `requestEmailChangeAsync(newEmail, currentPassword)` signature is
    a breaking change for any caller — currently only `AccountSettings.vue`.
  - The `dora_csrf` cookie's `httponly=False` is deliberate; the
    defence relies on the SPA reading it. A future XSS would still let
    an attacker read the token (the defence stops cross-site, not
    in-page-script attacks). XSS-hardening is its own sweep (FU-196
    security-headers / CSP item) — R-025 doesn't claim to fix that.
  - `PUBLIC_ENDPOINTS` and `CSRF_EXEMPT_ENDPOINTS` are now load-bearing
    lists; additions need a written rationale (R-025 violation signal).
- **Promotes rule:** R-025.

### ADR-022 — Nav-state on list pages: session-scoped, no full-reload persistence
- **Date:** 2026-07-01
- **Context:** A8 §3 called for one consistent rule for filter / search /
  sort / scroll on list pages. Before this, the app was inconsistent
  (some pages persisted via URL, most reset on every mount). The
  question was persist-across-reload (localStorage) vs
  persist-within-session (in-memory) vs always-reset.
- **Decision:** Persist within the SPA session, reset on full reload.
  Filters/search/sort go through a module-level Map keyed by page
  scope (`useListState`). Scroll goes through the router's
  `savedPosition`. Neither uses `localStorage` or `sessionStorage`.
- **Alternatives considered:**
  - **localStorage-backed persistence across reloads.** Rejected: a
    stale filter that survives a browser restart traps users on a
    filter set they don't remember configuring; the session boundary
    is honest.
  - **Vue Router `<keep-alive>` on list routes.** Rejected: caches
    every route indefinitely (memory spike), and re-mount-on-visit
    is what stores rely on for fresh data.
  - **Pinia store slice per list page.** Rejected as over-engineered
    for what is view-only state; stores own domain data, not
    per-page UI knobs.
- **Consequences:**
  - New primitive `useListState` is now the standard for list-page
    view state; two existing patterns (`useFilterPanelExpanded`,
    `useProductSearchUrl`) survive as explicit carve-outs with
    different contracts.
  - Remaining list pages (MealPlansOverview, ShoppingListsOverview,
    Stocktake, settings-list surfaces) migrate opportunistically;
    tracked as an open follow-up.
  - Sign-out should call `clearAllListState()` when it's wired, so a
    second user on a shared device doesn't inherit the previous
    user's filter shape. Currently a full reload happens on sign-out
    anyway, so this is a nice-to-have rather than a defect.
- **Promotes rule:** R-026.

### ADR-023 — Styling encapsulation: component owns intrinsic appearance; parent owns layout context
- **Date / task:** 2026-07-02 (toolbar-parity review — user spotted the Filters button sitting 8px above its BaseButton siblings on Stock Overview).
- **Status:** accepted
- **Context:** The Filters button and the other toolbar buttons (New item / Scan / Stocktake / Bulk select / Export) all share the same base (`BaseButton`). But the Filters button visually sat higher than the rest. Root cause was not the base component — it was the `FilterToggleButton` wrapper: `<div class="row items-center q-gutter-sm no-wrap">` around the (Clear + Filters) pair. `q-gutter-*` is Quasar's negative-margin trick (`margin-top: -8px` on the container, `+8px` on each direct child). When the wrapper sat inside the parent toolbar's own `q-gutter-sm`, it received `+8px` from the parent AND applied `-8px` to itself internally — net displacement zero. Sibling `BaseButton`s that were direct children of the outer container only got the outer `+8px`, so they sat 8px lower than the wrapper. Every other composite component that wraps children in its own `q-gutter-*` `<div>` has the same latent bug — the failure mode isn't specific to FilterToggleButton, it's a class of collision.
- **Decision:** Adopt R-027. Component owns intrinsic appearance (size / padding / border / colour / hover); parent owns layout context (position in a flex row, spacing between siblings). A composite component that renders multiple children uses a **Vue 3 multi-root template** so the children participate directly in the parent's layout — no wrapper `<div>` that carries a spacing scheme colliding with the parent. Where a wrapper is genuinely needed, it uses flexbox `gap` (no negative-margin trick) so it can't collide. Callers never re-declare intrinsic styling or fudge alignment with call-site `class="q-mt-xs"` — the fix is in the component.
- **Alternatives considered:**
  - **Fix the specific FilterToggleButton bug and log the general lesson as an FU.** Rejected — the class of collision recurs anywhere a shared component wraps children in a gutter-carrying div, and the R-001 componentisation rule doesn't cover it explicitly. Promoting to a rule now means it's on the close-gate checklist for every future paired-primitive component.
  - **Wrap children in a `<div style="display: flex; gap: 8px">`.** Valid alternative for the specific fix and worked as a fallback. Rejected as the *primary* pattern because it introduces an extra DOM node with no semantic purpose; the multi-root template is one less element and clearer intent.
  - **Push the Clear button up to the caller.** Rejected — Clear and Filters are logically paired (they appear/disappear together as a unit; FU-121 encoded that pairing). Splitting them means every caller re-implements the appear/disappear + ordering rules.
- **Consequences:**
  - The `q-gutter-*` negative-margin scheme is now considered *hazardous inside shared components*. Toolbar rows on pages can still use it freely — the hazard is only when a *component wraps children* in it.
  - Existing paired-button components get an audit: `git grep 'q-gutter' web_app/src/components/` surfaces candidates. Each hit is checked against "is this component ever mounted inside a parent that also carries a Quasar gutter class?" — if yes, migrate to multi-root or `gap`.
  - The rule extends R-001 (componentise first) — R-001 said *create the primitive*; R-027 adds *and don't sabotage it with wrapper DOM that fights the caller's layout*.
- **Promotes rule:** R-027.

### ADR-024 — Domain inference = pure decision core + thin repo-gather
- **Date / task:** 2026-07-03 (P8-07 Zero-Input Pantry belief service).
- **Status:** accepted
- **Context:** P8-07 needed a per-item belief (band + confidence + reason) derived from four interacting signals (intake, cadence, cooking, time decay) with subtle rules — override precedence, confidence decay, coarse-band cuts. This is the same *shape* as the P8-05 buy-verdict, which had already split into a pure `compose_verdict(_AxisInputs)` + a thin `_gather_inputs` repo walk, and whose rules are pinned by `tests/test_buy_verdict.py` with zero DB. Building the belief the same way (pure `compute_belief(BeliefInputs)` + `gather_beliefs_for_items`) meant the tricky logic got a fast fixture-driven unit suite (`tests/test_pantry_belief.py`) while the repo access stayed a thin, separately-verified layer. Two independent uses of the pattern = the "don't do it twice differently" bar.
- **Decision:** Adopt R-028. Domain-judgement features split into a pure function over an inputs dataclass (no repo / HTTP / ambient clock) + a thin gather layer that the endpoint calls; tests drive the pure core with fixtures. Time values are passed *into* the inputs for determinism. Keeps the judgement server-owned (R-003) with one testable home.
- **Alternatives considered:**
  - **Compute inline in the endpoint handler.** Rejected — forces slow, brittle e2e setup to exercise arithmetic branches, and buries the domain rules in repo plumbing.
  - **Leave it as a one-off (don't promote).** Rejected — two independent uses (buy_verdict, pantry_belief) is exactly when a pattern should become a rule so the next derivation feature (e.g. P8-08 Dora Score) follows it by default rather than re-discovering it.
- **Consequences:**
  - P8-08 Dora Score and any future prediction/score feature start from this shape.
  - The gather layer must still batch for list overlays (no N+1) — called out in R-028's Apply.
- **Promotes rule:** R-028.

### ADR-025 — Respect the off-state: hide disabled/unconfigured features outside their own settings screen
- **Date / task:** 2026-07-06 (user directive walking back R-014).
- **Status:** accepted; supersedes ADR-009
- **Context:** ADR-009 / R-014 (2026-06-14) established "reveal-and-disable" — showing gated feature entry points as visible-disabled with a "not set up" hint, so users would discover capabilities. In practice this reads as nagging: a disabled Email button sitting in the meal-plan builder for a household that has no SMTP configured, a scanning button greyed-out for a household where the admin turned it off, etc. The user's directive is unambiguous — "if a user has disabled something (either personally or for the household) it should not be in their face". This applies whether the off-state is an explicit toggle (`scanning_enabled=false`), a per-user preference, or an unconfigured backend (SMTP/VAPID/LLM never set up = the household implicitly opted out).
- **Decision:** Adopt R-029. Gate optional-feature entry points with `v-if` on the same capability flag the functionality uses; hide them when off. The settings screen that owns the config still renders the disabled control (that's where enabling happens). Calm empty-state placeholders ("no data yet") are a different pattern and stay.
- **Alternatives considered:**
  - **Keep R-014 with per-surface judgement.** Rejected — the user explicitly wants the principle inverted, not softened. "Show disabled everywhere" was the wrong default.
  - **Split "explicitly disabled" vs "never configured".** Rejected — the household not setting up SMTP *is* an opt-out; treating unconfigured as "discoverable-nag" is exactly what the user is walking back. One consistent rule.
- **Consequences:**
  - The FU-176 sweep flips direction: any place currently rendering a disabled-with-hint gated control outside its config screen becomes a `v-if` hide. A fresh follow-up ([[FU-500]]) tracks the inverse sweep — most visibly the scanning button, the meal-plan builder Email button (C-2.J), and the notification/push/LLM controls that appear outside their settings screen.
  - ADR-002's original hide-when-off presentation is restored — it no longer needs the "R-014 revisits it" note.
  - Empty-state usages (dashboard "all clear", meal-plan empty week, `DoraScoreCard` explainer) are unaffected — they're a distinct pattern that some code comments mislabelled as R-014. They stay; the R-014 comment references on those sites can be re-labelled opportunistically.
- **Promotes rule:** R-029.
- **Supersedes:** ADR-009 (R-014).

### ADR-026 — Operational config lives on `AppSetting`, not env
- **Date / task:** 2026-07-06 (FU-333 close-out — Buckets B + C + D shipped end-to-end).
- **Status:** accepted
- **Context:** Dora accumulated 19 `DORA_*` env vars at boot — every optional feature (SMTP, VAPID, TTS, audit retention, public URL, etc.) added one or more. Operators self-hosting had to configure a long environment table before the app was useful; desktop end-users would never see one at all. The FU-333 audit split the vars into three buckets — Bucket A (7 vars, genuine bootstrap: read before the DB or root wrapping keys), Bucket B (12 operational vars — SMTP host/port/username/from/use-TLS, VAPID public+subject, Piper paths, email_enabled, audit_retention_days, public_url), Bucket C (2 real secrets — SMTP password, VAPID private key). Bucket B shipped 2026-07-05 as `AppSetting` columns with an env-fallback lane. This ADR closes out Buckets C + D and drops the fallback (pre-release; no operators to preserve — user directive 2026-07-06).
- **Decision:** Adopt **R-030**. `AppSetting` is the single source of truth for install-wide operational config; env vars are reserved for the 7 bootstrap values and the wrapping key (`DORA_SECRET_ENCRYPTION_KEY`). Real secrets live on the row *encrypted-at-rest* with the FU-153 Fernet helper. The response DTO surfaces a `<field>_configured: bool` for every secret; ciphertext never leaves the DB. Desktop bundles auto-generate the two remaining bootstrap keys on first launch (Bucket D), so end-users see no env var at all.
- **Alternatives considered:**
  - **Keep the Bucket-B env fallbacks for one release.** Rejected — pre-release, no operators to preserve. Fallback code is dead weight and hides the strict-AppSetting contract from future readers.
  - **Store SMTP password + VAPID private key in a JSON keychain file.** Rejected — makes backups + Postgres migrations harder (a second data location); doesn't compose with SaaS's shared-DB story. `AppSetting` + Fernet is the same pattern per-user LLM keys already use.
  - **Auto-generate `DORA_SECRET_ENCRYPTION_KEY` on server self-host too.** Rejected for the server path — operators want an explicit "I made a choice" signal about the wrapping key (matches the FU-153 rationale). Desktop is the odd one out because the "operator" *is* the end user.
- **Consequences:**
  - Env footprint: 19 → **2** on server self-host (`DORA_SECRET_KEY` + `DORA_SECRET_ENCRYPTION_KEY`); **0** on desktop bundles. The `.env.example` block for the promoted vars is gone.
  - New pattern for any future "where should this config live?" call: default to `AppSetting` unless it's read pre-DB or is a wrapping key.
  - Rotating `DORA_SECRET_ENCRYPTION_KEY` invalidates the two operational secrets + every per-user LLM API key; the resolver degrades to dry-run (with a warning log) rather than crashing. Admin re-enters secrets in Settings — documented in `key_encryption.py` and `.env.example`.
  - Desktop bundle: `desktop_app._detect_bundled_piper_paths()` + `_seed_desktop_paths()` write detected `piper_bin` / `piper_bundled_voice_dir` into the row *post-init*; no env fallback path to lose in the resolver.
- **Promotes rule:** R-030.

### ADR-027 — Constructor injection via Protocols; no DI container
- **Date / task:** 2026-07-08 (rip-out of the `dependency_injector`-based `DependencyContainer`).
- **Status:** accepted
- **Context:** The codebase had a `DependencyContainer` (a ~215-line wrapper around `dependency_injector.containers.DynamicContainer`) that auto-registered every `*Handler` under `dora_api/features/` via reflection, then routers resolved handlers with `get_container().inject(FooHandler)` at 200+ callsites. An audit found: **175 of 179 handlers** just constructed `self.repository = SqlAlchemyRepository()` in `__init__` — no injected params, no interfaces exercised, no lifetime rules beyond `Factory`. The container's own example lines for interface-based registration (`IRepository[Merchant]`, `IConfigurationManager`) were commented out. Zero tests used the container. In practice it was a fancy service-locator around a zero-arg constructor call, plus a boot-time reflection surface that spawned its own hardening FU ([[FU-457]] — boot-time resolved-route assertion). The whole shape (`I`-prefix nominal interfaces, generic-alias name mangling, `SqlAlchemyGateway[T]`) read as C#/.NET conventions ported into a language that doesn't need them.
- **Decision:** Adopt **R-031**. Delete the container; delete `service_wiring.py`; delete the `get_container()` accessor; remove `dependency_injector` from requirements. Introduce `dora_api/infrastructure/ports.py` with a `Repository` Protocol (structural typing — any object with the right method surface satisfies it, no ABC inheritance). Rewrite every handler `__init__(self)` → `__init__(self, repository: Repository)`. Rewrite every `get_container().inject(X)` callsite → `X(SqlAlchemyRepository())`. Three handlers that legitimately don't need a repository (`RestoreBackupHandler`, `InspectSpreadsheetHandler`, `GetShortfallHandler`) stay parameter-less; `AskAssistantHandler` remains as the "no repo, per-user LLM client" carve-out it already was.
- **Alternatives considered:**
  - **Keep the container, add the boot-time assertion FU-457 wants.** Rejected — the assertion protects a reflection surface we can just delete. Cheaper to remove the fragility than to shore it up.
  - **Handler ctor with `repository: Repository | None = None` defaulting to `SqlAlchemyRepository()`.** Rejected — pragmatic but dishonest. Hides the dependency and lets callers keep the old service-locator habit indefinitely. Force the caller to pass it.
  - **Move to `I`-prefix ABCs + a hand-rolled DI without the container.** Rejected — `typing.Protocol` is the Python-native, structural way to say "this shape". Any nominal hierarchy is unnecessary ceremony.
- **Consequences:**
  - `-215` LOC (`dependency_container.py`), `-21` LOC (`service_wiring.py`), `-1` runtime dep (`dependency_injector`). ~200 callsites became a direct constructor call.
  - Testability payoff realised immediately — 3 tests that previously did `patch.object(handler, "repository", stub)` now pass the stub through the constructor and are 3-5 lines shorter each.
  - **FU-457 dissolved by construction.** No reflection-based handler-wiring surface left to protect. Router discovery (`get_attributes_ending_with('router', ...)`) is a separate reflection surface; if it needs the same boot-time assertion, that's a much smaller FU to reopen.
  - The 4 files in `dora_api/features/data/` that didn't already import `SqlAlchemyRepository` got the import added.
  - When a genuine swap surface arrives (R-005 auth interface; email transport per FU-500 sweep; push transport; LLM client per-tenant), the pattern is: **add a Protocol to `ports.py`, take it in the ctor, wire the concrete at the router edge or on `app.services` in `create_app`.** No container.
  - The .NET-flavoured naming (`I`-prefix generic interfaces, `SqlAlchemyGateway[T]`) is now discouraged for new work — this ADR is the reference for "why we don't do that here."
- **Promotes rule:** R-031.

### ADR-028 — Reading a `noload` relationship without including it is a silent-correctness bug; make it a rule
- **Date / task:** 2026-07-12 (test-suite hardening passes; user confirmed promotion)
- **Status:** accepted
- **Context:** Six distinct production bugs in two weeks shared one root cause:
  code loaded an entity (plain `.by_id()`/`.all()`), then read a `lazy="noload"`
  relationship off it, which returns `None`/empty **silently**. Instances:
  cookbook `?cookable`/`?expiring` filters were no-ops (identity-map poisoning);
  the keeps-running-out report dropped history-less items (FU-527); stock-group
  `item_count` was always 0 (FU-527); PATCH appended phantom stock-level history,
  lost every cook-mode `ConsumptionEvent`, and no-op'd recipe FK null-clears
  (FU-533). None raised an error; all were caught by tests, never by review.
  FU-527's original note set the trigger "one more incident → promote a rule";
  it fired repeatedly.
- **Decision:** Promote **R-032**. Every read of a `noload` relationship must
  sit behind an `.include` on the same query; relationship-dependent maps load
  before any plain entity load in the same request; read the underscore FK
  property when only the id is needed; clear FKs by writing the underscore
  column, not a relationship-side `= None`.
- **Consequences:** New relationship reads carry an explicit `.include`
  (marginally more verbose, always correct). Pairs with the FU-534 query-count
  guards, which catch the inverse failure (an accidental per-row lazy load).
  Does **not** mandate changing the `noload` default itself — that's a
  deliberate perf posture; the rule governs how you *read* under it.
- **Promotes rule:** R-032.

### ADR-029 — Entity-id path params use Flask's `uuid` converter
- **Date / task:** 2026-07-12 (test-suite hardening passes; user confirmed promotion)
- **Status:** accepted
- **Context:** Routes declared entity-id params with the default string
  converter (`<stock_item_id>`) while handlers annotated them `UUID`. Flask
  delivers a `str`, so `entity.id == param` silently failed and UUID-keyed
  dict lookups missed — producing the taxonomy delete-count-always-0 bugs, the
  product-unlink-always-404 bug, and the rename-to-own-name-rejected bug across
  five surfaces (all FU-528). Worse, a non-UUID segment flowed into a UUID query
  and 500'd — **82 routes** return 500 instead of 404 on garbage input (FU-532).
  The handler-level instances were fixed with per-site `str(...)` coercion, but
  that papers over the class.
- **Decision:** Promote **R-033**. Entity-id path params use `<uuid:id>`; Flask
  parses to `uuid.UUID` and 404s malformed values at routing time before the
  handler runs. This fixes the whole class at the edge and lets the per-site
  coercion workarounds be retired.
- **Consequences:** FU-532 becomes a mechanical sweep of route decorators
  (`<foo_id>` → `<uuid:foo_id>`) for the entity-id routes, verified by the
  existing `test_api_fuzz.py` path-param pin flipping from xfail to pass.
  Non-UUID path params (tokens, slugs) are explicitly out of scope. Handlers
  now receive a real `UUID`, so defensive coercions become no-ops (harmless;
  removable opportunistically).
- **Promotes rule:** R-033.

### ADR-030 — The ORM model owns the whole schema (indexes included); reconcile the model↔migration drift and gate it with a schema-match test
- **Date / task:** 2026-07-15 (FU-563, from the FU-393 data-model sanity sweep)
- **Status:** accepted
- **Context:** `table_mappings.py` declared almost no secondary indexes — 1, vs
  the 32 the Alembic chain builds. Every other index (and 4 unique constraints)
  lived only in migrations, so `create_all()` (dev + the whole e2e suite) built a
  near-unindexed schema that didn't match production, and behaviour depending on an
  index/UNIQUE couldn't be exercised where the model was silent. Separately, 43 FK
  columns had no covering index in prod (parent-delete full-scans + unindexed joins).
  The guard that should have caught it — `test__migrations__migrated_schema_matches_orm_metadata`
  — only compared table *names*, so all of it passed CI blind.
- **Decision:** Promote **R-034**. The model is the single source of truth for the
  entire schema, indexes and unique constraints included; FK columns are indexed by
  default. Mirrored all 32 pre-existing prod indexes/uniques into `table_mappings.py`
  (names copied from the migrations so autogenerate stays a no-op on them), added the
  43 FK covering indexes to both the model and one additive forward-only migration
  (`b9d4f2a7c3e1`), and rewrote the schema-match test to compare tables + columns +
  nullability + index/unique colsets with a small documented allowlist.
- **Consequences:** dev/test now build the same schema as prod (drift went from 31
  missing indexes + 4 missing uniques to zero). The additive index migration is
  portable (pure `CREATE INDEX`, no table rewrite — SQLite + Postgres, R-005/R-006).
  Two classes of drift needing risky batch table rebuilds were split off from this
  additive change and finished in follow-on migrations the same day: the 4 nullability
  drifts (3 `Product` cols reconciled + the `User.username` deferral documented —
  **FU-564**, migration `c1e8a5f3d9b2`) and the 6 FK `ondelete` mismatches (model
  declares CASCADE/SET NULL/RESTRICT, prod had none — **FU-565**, migration
  `d3f8b1a6c4e2`). The schema-match gate was extended each time (it now also compares
  nullability + FK `ondelete`), so the whole FU-393 sweep is closed and every class it
  found is now enforced, not just detected. Batch-mode fragility (this repo's
  double-render trap) was navigated with `batch.f(...)`-wrapped constraint names; the
  rebuilds preserved all other FKs + the covering indexes.
- **Promotes rule:** R-034.

### ADR-031 — Adopt a Design Style Guide (D-rules) as a standing usage rubric beside the R-rules
- **Date / task:** 2026-07-18 (owner directive after the FU-578 UX audit + design critique)
- **Status:** accepted
- **Context:** Seven real-pixel UX passes (FU-578, 54 findings;
  `docs/05_investigations/UX_DESIGN_CRITIQUE_2026-07-18.md`) found the token/theme
  architecture strong but per-surface execution drifting: three simultaneous date
  formats, dialog-casing drift (Quasar uppercase defaults), a semantically inverted
  stock-level colour scale (Out = grey reading calmer than Low = red), sub-AA muted
  text in light mode, unlabelled icon-only controls, and inconsistent loading
  treatments. R-002 policed token *mechanics* but nothing policed token *usage*, so
  each surface re-decided visual questions locally — the exact rules-only-in-
  finished-docs failure ADR-001 fixed for engineering.
- **Decision:** Author `docs/01_charter/DESIGN_STYLE_GUIDE.md` (D-001..D-015) as the
  authoritative look-and-feel rubric — colour semantics, contrast floors, type/tap
  minimums, icon naming/metaphors, single format authority, loading/skeleton rules,
  dialog/toast conventions, motion usage, composition, legends, copy voice, pattern
  reuse — and promote **R-035** so UI-affecting tasks check D-rules at the same
  close-gate as R-rules (fix / explain-in-place / log). Existing violations are
  backlog in `docs/04_proposals/DESIGN_REMEDIATION_PLAN.md` (DR-1..DR-16), not
  licence to copy. D-rules share the R-rule lifecycle (propose at close-gate).
- **Consequences:** UI diffs carry a second, cheap rubric check; design decisions
  get recorded as D-rules instead of re-argued per surface; the remediation plan
  gives the backlog a home so new work is never blocked on old debt. Rules out
  surface-local conventions (per-page date formats, ad-hoc status colours) without
  a commented carve-out.
- **Promotes rule:** R-035.

### ADR-032 — A `MainLayout`-hosted route roots on `<q-page>` for the layout height contract; never hardcode the offset
- **Date / task:** 2026-08-11 (FU-609, from the 2026-08-04 Stock Overview scroll-model rebuild)
- **Status:** accepted
- **Context:** `<q-page>` is the only element that gives a routed page a height
  contract — `min-height: viewport − layoutOffset`, computed from live layout state.
  Only 10 of ~29 top-level pages used it; the rest rooted on a bare `<div>` and, when
  they needed a height (sticky footer, fill-the-viewport shell, internal scroll),
  hand-rolled the offset with a hardcoded pixel guess. That guess rots: the Stock
  Overview rebuild found a magic `64px` that was already wrong when `OfflineBanner`
  adds 48px. `RecipesOverview` shares Stock Overview's `PageCountsFooter` but as a
  bare div, so its footer floats mid-screen on a short list (no min-height to pin to).
- **Decision:** Promote **R-036**. A `MainLayout`-hosted route roots on `<q-page>`;
  document-scroll pages use a bare `<q-page>` (default min-height pins the sticky
  footer), fixed-height app-shells use `<q-page :style-fn>` reading the live `offset`;
  never hardcode the offset. Converted `RecipesOverview` to a bare `<q-page>` as the
  document-scroll worked example (StockOverview is the app-shell reference). The
  remaining pages are **opportunistic per-page conversions**, not a blind sweep — the
  inventory + per-page notes stay in FU-609; several need a document-scroll-vs-shell
  call and `SettingsShell`'s own hardcoded offset is a separate fix.
- **Consequences:** the sticky-footer-on-short-content bug is fixed on the one page
  that shared Stock Overview's footer, and the pattern is now enforced at the
  close-gate so new pages don't reintroduce bare-div roots or magic offsets — without
  taking on the regression risk of converting 11 unreported surfaces at once.
- **Promotes rule:** R-036.

### ADR-033 — Page-root route transitions cross-fade, never `mode="out-in"` (paired with ADR-032/R-036)
- **Date / task:** 2026-08-11 (FU-619, blank-screen-on-nav regression that followed the R-036 rollout)
- **Status:** accepted
- **Context:** the moment R-036 (ADR-032) made every `MainLayout` route root a
  `<q-page>`, navigation started painting a **blank screen** — the content area went
  empty and only recovered on a reload. Root cause: `MainLayout`'s router-view wrapped
  its pages in `<FadeTransition mode="out-in">`. `out-in` fully unmounts the leaving page
  before mounting the entering one; a `<q-page>` registers with its parent `QLayout` at
  mount, so sequencing the unmount fully ahead of the mount left a frame with no page
  registered, and the new `<q-page>` failed to resolve its container and rendered nothing.
  Dropping `out-in` (plain simultaneous cross-fade) fixed it. This is a recurring-shaped
  trap: `out-in` is the intuitive "clean swap" default a future dev will re-add, and it
  only breaks in combination with `<q-page>` roots — exactly the combination R-036 now
  mandates everywhere.
- **Decision:** Promote **R-037**. `MainLayout`'s router-view transition stays a modeless
  cross-fade; never use `mode="out-in"` (or a `transition-group` equivalent) on a layout
  whose routes root on `<q-page>`.
- **Consequences:** the blank-nav regression can't be reintroduced silently — the rule
  names the exact anti-pattern and its violation signal, so a future transition rework is
  steered away from `out-in`. Pairs with ADR-032: R-036 forces `<q-page>` roots, R-037
  guards the one page-swap footgun that mandate created.
- **Promotes rule:** R-037.

---

### ADR-034 — The grocery budget is a household concept: install-wide, not per-user (promotes R-038)
- **Date / task:** 2026-08-12 (owner call on Settings → Money; "the budget affects everyone via the shopping list — why is it on the user row?")
- **Status:** accepted
- **Context:** the grocery `budget_amount` / `budget_period` lived on `User`, but the
  budget engine sums "spent" across **every shared shopping list** in the period (the
  schema is single-household; `budget.period_spent` even carried the comment *"Not
  per-user because the schema is single-household"*). So the household spend total was
  compared against whichever member's personal budget row happened to be loaded, and the
  meal-plan auto-build / swap-defence read the *triggering* user's budget to decide the cap
  applied to the **shared** week — "is the week over budget?" depended on who pressed the
  button, and a per-user budget silently changed what got written into shared data. This is
  the exact shape FU-615 already fixed twice (`household_headcount`, `batch_features_enabled`
  moved User → AppSetting: "a household has one headcount, not one per person"). The
  per-user `money_features_enabled` opt-in was removed in the same pass (owner: money is
  "kitchen setup, not personal" — one install flag, no per-user layer).
- **Decision:** Move `budget_amount` / `budget_period` to `AppSetting`; surface via
  `/api/health.budget_policy`; edit via a new **any-authenticated-member**
  `PATCH /api/budget/settings` (kitchen-setup-grade shared config, same access class as
  shared stores/locations — the first non-admin write to an `AppSetting` field, deliberately
  so). Value-driven: amount null/0 ⇒ off (no separate enabled flag — which also removed the
  "toggle on with no amount, change period, toggle flips off" bug, since there was no longer
  a derived-enabled state to stomp). Promote the general lesson to **R-038**.
- **Consequences:** the household budget now has one physical truth; meal-plan budget-defence
  and the dashboard read the same shared value regardless of which member is signed in.
  Establishes that AppSetting can carry an any-member-editable field (not only admin config).
  Pre-release hard migration — the three `User` columns dropped, no data preserved.
- **Promotes rule:** R-038.

### ADR-035 — Quasar Dialog-plugin buttons must set `noCaps` (promotes R-039)
- **Date / task:** 2026-08-12 (DR-3 de-Quasar detail audit — dialog casing)
- **Status:** accepted
- **Context:** the app standardised on sentence-case buttons everywhere via
  `BaseButton` (which hard-codes `no-caps`), but the **`$q.dialog(...)` plugin**
  is a separate render path: its `ok`/`cancel` buttons default to **ALL-CAPS**
  unless each is passed as an object with `noCaps: true`. The DR-3 audit found
  ~15 files where confirm/prompt dialogs still shouted ("CANCEL", "SKIP", "GOT
  IT") — every `cancel: true` shorthand and every string-shorthand
  `ok: 'Label'` renders uppercase. This is pure drift: nothing enforces the
  app-wide casing on the one button surface that isn't `BaseButton`.
- **Decision:** Promote **R-039**. Any `$q.dialog({...})` call that renders
  native `ok`/`cancel` buttons must pass them as objects with `noCaps: true`
  (never `cancel: true` or `ok: '…'` string shorthand). Component dialogs
  (`{ component }`) are exempt — they render their own `BaseButton`s.
  *Enforcement is by-convention today (matching the ~15 existing explicit
  `noCaps` sites).* A thin `$q.dialog` wrapper that injects the default is the
  proper single-source fix and is logged as **FU-623** (opportunistic) rather
  than retrofitted mid-audit — a half-migrated wrapper would be worse than the
  consistent explicit pattern.
- **Consequences:** dialog buttons match the app's sentence-case voice (D-005);
  new dialogs that forget `noCaps` are a reviewable R-039 violation.
- **Promotes rule:** R-039.

### ADR-036 — Dialog-gated side effects are a product of the outcome, not eager-then-confirm (promotes R-040)
- **Date / task:** 2026-08-12 (DR-5 open-toggle mutation trap — FU-578 #2)
- **Status:** accepted
- **Context:** the stock-row "mark as open" flow PATCHed `is_open=true`
  *immediately* on click, then opened a prompt that only governed the effective
  expiry. So "Skip", Escape, and backdrop-click **all** left the item opened,
  with no way to abort and no undo — a silent commit on dismissal. The clean fix
  was blocked by a Quasar constraint: native `$q.dialog` collapses the Cancel
  button, Escape, and backdrop into a single `onCancel`, so a two-button prompt
  cannot distinguish "Skip (confirm-open, keep expiry)" from "abort".
- **Decision:** Promote **R-040**. Gate the side effect on the dialog's outcome:
  replace the two-button prompt with a promise-based `useDialogPluginComponent`
  component dialog (`MarkOpenExpiryDialog.vue`) exposing three explicit buttons
  (Cancel / Skip / Update expiry); Escape/backdrop resolve as abort. The
  decision→PATCH mapping is a pure helper (`openToggle.ts buildOpenTogglePatch`)
  returning `null` on abort so the caller writes nothing; shared orchestration
  (`useStockItemActions.planOpenToggle`) is reused by the row and detail page
  (removing the duplicated FU-507 prompt — R-003). Pinned by
  `test/unit/openToggle.spec.ts` (abort ⇒ no mutation). Introduces the
  `useDialogPluginComponent` pattern to the repo for promise-based shared prompts.
- **Consequences:** one commit path that fires only on explicit confirmation;
  dialog dismissal never mutates. The decision logic is unit-testable without
  mounting. Sets the template for any future multi-outcome confirm dialog.
- **Promotes rule:** R-040.

---

### ADR-037 — Derived aggregates carry their coverage (promotes R-041)
- **Date / task:** 2026-08-14 (FU-635 chunk 6 — recipe nutrition rollup)
- **Status:** accepted
- **Context:** the recipe nutrition rollup sums per-100g figures over ingredients
  whose chain (ingredient → stock item → food → gram conversion) can break at
  four separate links. Every option that hides a break — skipping the ingredient
  silently, assuming a gram weight from a similar portion row, defaulting a
  missing macro to 0, dividing by an assumed 4 servings — produces a number that
  *looks* complete and is wrong in a way the reader cannot detect. The cost
  estimate (DEC-5) had already reached the same conclusion for pricing, shipping
  `priced_count`/`total_count` so the UI could say "based on N of M".
- **Decision:** Promote **R-041**. The rollup returns `counted_count`,
  `total_count`, and an `uncounted` map keyed by a closed set of reason ids
  (`not_linked` / `no_food` / `no_quantity` / `no_conversion` / `no_data`);
  nutrient fields are `None` rather than `0` when nothing supplied them; the
  basis is explicit (`serving` when servings are typed in, `recipe` otherwise).
  The card renders the coverage line **unconditionally**, gaps as a named list.
  Gram conversion refuses rather than guesses: mass converts outright, volume
  prefers the food's own measured USDA portion row over the modelled density
  table, counts require a whole-item portion row.
- **Consequences:** every future aggregate (waste totals, plan-level nutrition,
  budget projections) owes the same shape, and the failure taxonomy has to be
  enumerated up front — which is the useful pressure: it forces the author to
  name what can go wrong instead of letting it vanish into the sum. Costs a
  slightly wider DTO and a coverage line the reader must parse even at full
  coverage; judged the right trade, since a number whose basis is invisible
  reads as complete whether it is or not.
- **Promotes rule:** R-041.

---

### ADR-038 — Identity is the repository's to assign; links between new entities resolve after the parent is saved (promotes R-042)
- **Date / task:** 2026-08-15 (FU-639 — nutrition dataset import failed in production)
- **Status:** accepted
- **Context:** `SqlAlchemyRepository.add()` overwrites `entity.id` with a fresh UUID
  by design. The USDA importer parsed foods and portions in one pure pass, linking
  portions to `food.id` as generated during parsing; `add()` then replaced every
  food's id, leaving all 14,449 portions pointing at ids that were never written. The
  failure surfaced only against the real 7,793-row dataset, after a successful
  download and parse, as `FOREIGN KEY constraint failed`. Three test layers missed it:
  the parser's unit tests are database-free, the seeded e2e fixtures happen to read
  `food.id` after adding, and the endpoint test asserted a status code without
  checking why.
- **Decision:** Promote **R-042**. The parse layer now returns `ParsedPortion`, keyed
  by USDA's own `fdc_id` (a natural key that cannot go stale), and `_replace_dataset`
  commits foods first, then builds portions from `{source_ref: saved_id}`. An e2e
  drives the real repository and asserts each portion lands against *its own* food.
- **Consequences:** any bulk import that writes a parent/child pair owes the same
  two-phase shape and the same natural-key link — slightly more ceremony in exchange
  for a class of silent dangling-FK bug being impossible to express. Does **not**
  change `add()` itself: repository-owned identity is a long-standing convention and
  rewriting it would ripple through every feature; the rule documents the contract
  instead.
- **Promotes rule:** R-042.

---

### ADR-039 — A guess is surfaced, not saved; the confidence band is server-owned (promotes R-043)
- **Date / task:** 2026-08-15 (owner ask — auto-suggest a nutrition food for unlinked
  stock items)
- **Status:** accepted
- **Context:** complex-mode nutrition required a human to open a picker and search,
  once per stock item, before any calorie figure existed anywhere. The owner's read
  was blunt: people won't do that, so the feature may as well not exist. The obvious
  fix — auto-link the best name match — is precisely what the picker's own comment
  had ruled out, because a mis-linked food silently corrupts every recipe rollup and
  per-day total that reads through it, and nothing on screen looks wrong.
- **Decision:** split "match" from "link". `features/nutrition/suggestions.py` scores
  candidates and returns a `FoodSuggestion` on the read; `StockItem.nutrition_food_id`
  is still written only by an explicit human action. The suggestion carries both its
  raw score and `is_strong`, so the band lives once on the server, and the bulk
  accept-all verb recomputes matches server-side and touches only the strong band.
  A persisted, reversible `nutrition_ignored` gives "never ask about this again".
- **Consequences:** every future inferred-match surface owes this shape rather than a
  quiet write. Costs a per-entity opt-out column and a visibly-hedged UI state; buys
  a feature that can be wrong without being harmful. Tuning is now a testable
  artifact — the recall floor exists because "Toilet paper" matched "Toilet" at
  exactly 0.50 in calibration, and that case is pinned.
- **Promotes rule:** R-043.

---

### ADR-040 — Config reads belong at the top of a read handler (promotes R-044)
- **Date / task:** 2026-08-15 (same unit — gating the suggestion on complex mode)
- **Status:** accepted
- **Context:** the suggestion is only worth computing in complex mode, so the handler
  gained a mode check next to the code that used it — the placement that reads best.
  `get_or_create_app_setting` commits, the commit expired the session, and the
  already-loaded `StockItem`'s `lazy="noload"` relationships re-read as None. Every
  stock-item detail response lost its level and location. No exception, no log line.
- **Decision:** hoist the setting read above the entity load and pass a local down.
  The docstring on `_nutrition_is_complex` states the ordering constraint in place, so
  the next person to "tidy" it back down has been told why not.
- **Consequences:** a small ordering convention in read handlers, and one more reason
  to keep whole-DTO before/after assertions in the suite — a field-scoped test would
  have stayed green through this.
- **Promotes rule:** R-044.

---

### ADR-041 — Binary/document endpoints are fetched, not linked (promotes R-045)
- **Date / task:** 2026-08-16 (stock-item detail feedback — "QR button currently
  doesn't work: empty modal and a 404 when trying the print one button")
- **Status:** accepted
- **Context:** three call sites reached the QR endpoints by URL rather than through
  the http client — the detail page's `<img :src>` and "Print one", the Kitchen-setup
  QR-labels page, and the stock-overview bulk sheet. All of them depend on the browser
  attaching `dora_session` to a request the app never made. That holds on a same-site
  dev box and stops holding the moment the SPA and API are on different hosts, or the
  app runs in the Capacitor shell. There is no honest way to make the linked form
  reliable, because the caller cannot attach a credential to it.
- **Decision:** one auth path. `AxiosHttpClient` grew `getBlob`; a single
  `useQrLabels` module owns both QR URLs; the print sheet's per-label images are
  inlined by the server as data: URIs so the page is self-contained and prints
  correctly when saved. The alternative considered and rejected was making the QR
  endpoints public — a QR payload is an item id, and unauthenticated enumeration of
  a household's stock ids is not a trade worth making for a print button.
- **Consequences:** binary/document endpoints cost a fetch + an object URL instead of
  a URL string, and a server-rendered document that references other API resources has
  to inline them. In exchange, "does this work?" stops depending on deployment shape.
  Note the sibling call sites this did NOT convert: `print-view` and the CSV export
  still build URLs (CSV via `fetch` with credentials, which is fine; `print-view` via
  `window.open`, which is the same latent bug) — tracked as a follow-up.
- **Promotes rule:** R-045.

### ADR-042 — The pop-up is opened by the gesture, not by the response (promotes R-046)
- **Date / task:** 2026-08-17 (stock-item detail feedback — "QR codes still seem to
  be having issues… print one gives me an error")
- **Status:** accepted
- **Context:** ADR-041 removed the URL-linked form of the print sheet and replaced it
  with fetch-then-`window.open(blobUrl)`. That fixed the auth problem and introduced a
  new one in the same line: the open now happens after an `await`, so the browser no
  longer attributes it to the click. Desktop Chrome is lenient enough that a dev box
  shows nothing wrong; the owner reported it from a tap, where it is blocked outright.
  Two rounds of investigation had by then failed to explain the failure, because both
  were static reads — this round proved the server half green with an e2e pin (7 tests,
  including that the sheet contains no `/api` back-reference) and a live cross-origin
  browser probe, which is what left the client gesture as the only place to look.
- **Decision:** open the tab first, synchronously, and navigate it when the fetch
  lands. `noopener` is dropped (it forces a `null` return) and `opener` is severed by
  hand. Rejected: rendering the sheet in a same-tab route (loses the print affordance
  and the browser's own print chrome), and triggering a download instead (the sheet is
  meant to be printed, and a download is worse on mobile, not better).
- **Consequences:** every "fetch a document then show it" flow now has a required
  shape, and the two sites FU-647 tracks (`print-view`, CSV export) inherit it when
  they're converted. A blocked pop-up is now a distinct, named outcome the UI reports
  as such rather than a generic failure.
- **Also decided (not a rule):** the detail page's QR errors now carry the HTTP status
  and the correlation-id prefix instead of a flat sentence. The reason FU-648 survived
  two fixes is that the only person who could observe it had nothing to report back
  but our own copy. When a defect is reported from an install you can't reach,
  instrumenting the error path is part of the fix, not a follow-up.
- **Promotes rule:** R-046.

### ADR-043 — Cross-cutting request concerns are the client's, so leaving the client forfeits them (promotes R-047)
- **Context:** `AxiosHttpClient` attaches four things via interceptors —
  correlation id, CSRF double-submit header, retry/backoff, and the 401
  handler. A handful of callers can't use it (streaming responses, chunked
  uploads, and the offline queue, which must replay *without* being
  re-enqueued by its own wrapper) and reach for raw `fetch` / bare `axios`.
  Each such caller silently opts out of all four.
- **Decision:** treat "not using the client" as a checklist, not a shortcut.
  The mandatory item is CSRF + credentials; the rest are judgement. Record
  each bypassing caller in one place (the `csrfHeader()` comment block) and
  pin it with a test.
- **Alternatives considered:** *(a)* make the offline replay go through
  `AxiosHttpClient` — rejected: `tryWithQueue` wraps the client, so a replay
  through it re-enqueues itself on failure, which is the reason it used bare
  axios in the first place. *(b)* Exempt replays from CSRF server-side via an
  `X-Offline-Replay` header — rejected outright: a header an attacker can set
  is not a defence, and it would hand any cross-site form a CSRF bypass.
  *(c)* Move the header attachment into a shared `buildRequest()` helper both
  paths call — the right long-term shape, deferred as unnecessary for three
  callers; R-047 plus the test is enough for now.
- **Consequence:** the bypass list stays small and visible. The cost is that
  every new bypassing caller needs its own header test, because mocked
  transports can't catch a missing one.
- **Promotes rule:** R-047.

---

### ADR-044 — Match by construction, not by CSS (promotes R-048)
- **Date / task:** 2026-08-19 (cookbook feedback batch 2)
- **Status:** accepted
- **Context:** The cookbook filter row drew the same owner complaint three times
  in three days — first that the controls were different sizes, then that they
  were different colours, didn't brighten on focus, and put their dropdown caret
  in a different place. Every round was patched with more page-level `:deep()`
  CSS aimed at making a `q-btn-dropdown` resemble a `q-field`. The page's own
  style comment had already diagnosed it ("a button pretending to be a field")
  without acting on the diagnosis. The owner's third report asked the right
  question directly: "can we not achieve uniformity via base components?"
- **Decision:** When a control must read as a peer of a framework primitive,
  build it **on** that primitive and use its slots, rather than approximating it.
  Extract the composition (and the row layout around it) as shared base
  components. Take framework-owned values (icon-set glyphs, the layer a focused
  field paints) from the framework rather than re-picking them.
- **Consequences:** Commits us to preferring a wrapper over per-page CSS even
  when the wrapper is more upfront work — `BaseFilterField` is ~170 lines against
  a ~10-line CSS patch, but it retired ~4.5kB of override CSS across two pages
  and closed four separate reported symptoms at once. It also means bespoke
  controls inherit framework behaviour changes for free, and that a state the
  framework won't delegate (QField's `focused` is slot scope only) must be
  matched by painting the framework's own layer — verified by measurement, not
  by eye. Rules out "just add a class to make it look the same" as an acceptable
  answer to a consistency report.
- **Promotes rule:** R-048.

### ADR-045 — Inline editing needs an explicit commit; retires D-015's read-view clause (promotes R-049)
- **Date / task:** 2026-08-20 (recipe-view redesign, parity pass)
- **Status:** accepted
- **Context:** The redesigned recipe page (`RecipeDetailNext.vue`) replaced the
  read-view/edit-mode detail pattern with values that edit in place, and paired
  it with a **500 ms debounced autosave** behind every commit — no Save button,
  a transient pill as the only feedback. Three defects followed from the
  autosave, not from the inline editing: (1) each save ended in a re-fetch that
  re-hydrated the form, so a save firing while a second popup-edit was open
  rebound that popup to an orphaned row object and silently dropped the edit;
  (2) a newly-added ingredient row failed the server's anchor check, which
  refused *every unrelated* save until it was filled — with no button to retry
  from; (3) navigating inside the debounce window sent the PATCH from a
  component that was being torn down, so a failure had nowhere to report. The
  page also had no `onUnmounted`, no route guard and no dirty flag. Separately,
  **D-015** forbade always-editable detail pages — a clause written against the
  *old* recipe page, which this one replaces.
- **Decision:** Inline editing is an accepted detail-page anatomy. The
  **commit** is not optional: an editable surface owns a dirty flag, an explicit
  Save (and a Discard), a route/unload guard, and cleanup of any timer it
  starts. Never re-hydrate a form from the server except at a moment the user
  asked for — a load, or a save they pressed. Validation that can refuse a save
  is reported **on the offending row**, not only as a count in a message.
  D-015's read-view clause is retired (deleted, not carved out) because its only
  named counterexample no longer exists.
- **Consequences:** Costs a visible Save button on a surface whose pitch was
  "no modes" — accepted, because the alternative was a page that could lose an
  edit without saying so. Makes D-019's ban on autosave-plus-disabled-fields the
  general case rather than a field-level footnote: if the fields can't be
  inerted mid-edit, the commit has to be a deliberate act. Any future
  inline-edit surface inherits the same four obligations, which is what R-049
  makes checkable.
- **Promotes rule:** R-049.

### ADR-046 — Paint is decoration, never a step in a sequence (promotes R-050)
- **Date / task:** 2026-08-20 (DR-15 micro-motion pass)
- **Status:** accepted
- **Context:** DR-15 added a composable that applies a one-shot CSS class for a
  single animation cycle. Its first draft cleared and re-applied the class
  across a `requestAnimationFrame` — the textbook trick for restarting a CSS
  animation. Verifying it exposed the flaw: rAF never fires in a backgrounded or
  throttled tab (nor in the verify pane, which doesn't composite), so the class
  was scheduled and never written. Unlike the DR-8 splash wedge — the same
  assumption, but fatal and therefore found immediately — this failure is
  invisible: motion is polish, so nothing breaks, nothing logs, and the feature
  is just quietly absent for some users forever.
- **Decision:** rAF drives animation frames and nothing else. State writes,
  class writes, cleanups and unmounts sequence on `nextTick`, `setTimeout`, or a
  user event. Where a transition/animation end event is the natural signal, it
  gets a timeout fallback, or the timer owns the transition and the event is
  ignored.
- **Consequences:** Gives up the exact-frame animation restart, so a second
  change landing inside one 120ms cycle may not restart the animation — accepted:
  the cost is one missed polish frame, against a whole feature silently not
  running. Every future motion helper inherits the constraint, which is what
  R-050 makes checkable. Does not change the reduced-motion kill-switch, which
  is already CSS-only and paint-independent.
- **Promotes rule:** R-050.

### ADR-047 — A bulk endpoint orchestrates the single-item handlers; it buys round-trips, not commits (promotes R-051)
- **Date / task:** 2026-08-22 (stock-overview bulk-action work)
- **Status:** accepted
- **Context:** Owner feedback — "bulk actions seem to be performed one item at a
  time and it can be slow. noticed this on log waste." Every action on the stock
  overview's bulk bar was an N-request loop issued from the browser, sequentially
  awaited; bulk waste was three requests per item (log, PATCH the expiry away,
  re-read the row), so twenty items cost sixty serial round-trips. The obvious
  fix — a bulk endpoint that writes the set directly — was the wrong one for most
  of these actions. A level change is not a column write: it stamps
  `stock_level_last_updated` and `last_checked_at`, appends a `StockLevelChange`,
  may record a `ConsumptionEvent`, and may fire the auto-add hook. Clearing an
  expiry emits a classified `StockItemExpiryEvent`. Removing a list line cascades
  nested product lines. A set-shaped rewrite would have been a second copy of
  every one of those rules, and the copies drift the first time either side moves.
- **Decision:** a bulk endpoint's job is to remove **round-trips**, not to
  re-derive the domain. It loops the existing single-item handler in-process
  unless the operation is genuinely a bare field write with no history, no
  timestamps and no hooks — `bulk-move` qualifies and is two queries and one
  commit; `bulk-set-level`, `bulk-add`, `bulk-remove-by-stock-item` and the two
  waste endpoints do not, and delegate. Where the client needs state back to undo
  the batch (each item's cleared expiry), the endpoint echoes it rather than the
  client snapshotting it — the server is the one that knows what it changed.
- **Consequences:** the latency win is real and complete (N round-trips → 1),
  the database work is not — a 40-item bulk restock is still 40 commits, logged
  as FU-713 with the fix named (an explicit `commit: bool` on the inner handlers,
  never an implicit unit-of-work). Behaviour is identical to the per-item path by
  construction, so the existing per-item tests remain the coverage for the rules
  and the bulk tests only pin the new contract (counts, echoed ids, undo payload).
  Callers that pass richer per-item commands than the bulk request model accepts
  keep looping until the model is widened — see FU-714; branching on "is this
  batch simple enough" was rejected as the implicit cleverness R-019 forbids.
- **Promotes rule:** R-051.

### ADR-048 — Offline is read-only; the write queue is deleted, not widened (promotes R-052)
- **Date / task:** 2026-08-23 (owner feedback: "can we make the majority of
  actions work offline?")
- **Status:** accepted. **Reverses the direction of FU-718.**
- **Context:** the owner asked to *widen* offline support so the banner could
  promise that most actions sync on reconnect. Costing that out first is what
  changed the answer. The existing `useOfflineQueue` was **372 lines plus 649
  lines of spec for three call sites** (two in `stockItemStore`, one in
  `ShoppingListDetail`) — six declared mutation kinds, three used. Widening it
  meant taking on server-side idempotency keys, client-generated entity ids so
  creates could queue, chained create-then-edit replay, and a conflict UI. And
  the existing queue was not merely unfinished, it was hazardous: replay was
  at-least-once against a server that ignored the `X-Request-Id` it was already
  sending, the conflict pile had no UI at all, and it had already failed
  silently once (bare axios without the CSRF header → every drain 403'd →
  misclassified as non-network → the whole queue burned into invisible
  conflicts). Meanwhile the *read* side — a `NetworkFirst` Workbox rule over
  `/api/**` GETs — was quietly doing the valuable work with no conflict
  semantics at all. The two halves had opposite risk profiles.
- **Decision:** offline is **read-only**. Keep and own the read cache; delete
  the write queue entirely. Writes fail loudly with rollback. The banner states
  the constraint and promises nothing. Because the read cache now *is* the
  offline story, its cross-user leak stopped being theoretical and was fixed in
  the same unit (evict on sign-out and on 401).
- **Consequences:** loses mid-shop ticking without signal — the one genuinely
  valuable offline write, and the reason the queue existed. Accepted: it only
  ever worked in a narrow window (already in the app, page data loaded, no
  reload), the honest alternative was a promise the code could not keep, and the
  dominant real-world failure here is *seconds* of VPN intermittency, which
  retry and a read cache absorb without a queue. Also deletes the "which
  mutation kinds are queueable?" question that every new write surface used to
  have to answer. Anyone reversing this needs idempotency keys first and an ADR
  superseding this one — not a queue quietly reintroduced beside it.
- **Promotes rule:** R-052.

### ADR-049 — Price and store are resolved by a server-side ladder that ships its own provenance (promotes R-053)
- **Date:** 2026-08-23. **Context:** the shopping-list redesign needed a per-line
  price and a per-line store for a new "where you'll spend it" breakdown. Both
  had more than one possible source, and the owner's constraint was that
  **product offers are a power-user feature most installs will never populate** —
  so a design that only worked with scraped product data was not acceptable.
- **Decision:** resolve both on the server as explicit ladders, and return the
  resolved value *plus* the rung that produced it.
  - **Money:** `actual_unit_price` → the item's **last actual purchase** →
    the chosen offer → nothing. Exposed as `estimated_unit_price` +
    `estimate_source`.
  - **Store:** `purchased_store_id` → the item's **`usual_store_id`** → the
    **store of the last purchase** → the chosen offer's store → nothing. Exposed
    as `resolved_store_id` / `resolved_store_name`.
  - `by_store[]` (the aggregate) is server-owned, and reports `line_count` and
    `priced_line_count` separately so the UI can admit an unpriced remainder
    rather than showing a total that is quietly short.
- **Why this shape:** two pieces of the domain already existed and were being
  wasted. `StockItemPriceObservation` carries a `store_id` and is **auto-harvested
  from every finished list**, so two shops give any user their own
  store-attributed price history with no products involved; and
  `StockItem.usual_store_id` already existed with a comment saying it drives
  shopping-list grouping. The existing till prefill *already* ranked "from your
  last receipt" above "from {store} offer" — history-first was established
  precedent, so the ladders extend it rather than inventing a rule.
- **Why the two ladders disagree about intent vs history:** money asks "what will
  this cost me", where what you actually paid beats an advertised price; store
  asks "where do I *plan* to buy this", where an explicit tag beats where you
  happened to shop last time. The orders are opposite **on purpose**, which is
  the strongest argument for resolving them in exactly one place.
- **Offers are never the line's displayed price.** They render as their own
  *"Online offer: $2.90 at Coles"* chip and contribute to no total, so the store
  card and budget stay in one currency: money the user has actually spent. The
  offer survives only as the ladder's **last resort** when there is no purchase
  history at all — without it, a products-only user with no history would see
  zero totals.
- **Consequences:** `priceOfLine` (client) and `_line_price` (server) both stopped
  re-deriving the ladder and now read `estimated_unit_price`; three test suites
  that pinned the old `actual → offer` precedence at the client/aggregate layer
  were rewritten rather than patched, because the rule moved rather than changed.
  Adding a rung later (a recency guard on history, say) is now a one-file change
  with no call-site churn. **Amending a finished list must also update the
  harvested observation** (joined by `shopping_list_line_id`) or a corrected typo
  keeps poisoning every future estimate — done 2026-08-23 (FU-726, resolved): the
  line PATCH re-syncs the joined observation whenever price / store / quantity
  change on a `done` list, and removes it if the price is cleared.
- **Promotes rule:** R-053.

### ADR-050 — A lifecycle phase is a change of composition, not a disabled copy of one surface
- **Date / task:** 2026-08-23 (shopping-list run + receipt faces, FU-727)
- **Status:** accepted
- **Context:** `ShoppingListDetail.vue` rendered all three phases of a list from
  one template. "Start shopping" enlarged the checkbox and added a sticky footer
  and changed nothing else, so a row still carried eleven interactive zones in an
  aisle; and `done` rendered the same editing surface with `:disable` on every
  control, which both looked broken and quietly hid a receipt the DTO could
  already have supplied. Both defects have the same cause: status was being used
  as a permission flag when it is really a statement about what the user is
  trying to do.
- **Decision:** Each phase gets its own component. `ShoppingListRunFace` renders
  whole-row tap targets, per-section progress, a collapsed "all N picked" line
  and a thumb-height price sheet, with every curation affordance removed.
  `ShoppingListReceiptFace` renders a read-only itemised receipt with the store
  split and a "didn't buy" tail, and puts corrections behind an explicit **Amend**
  mode that states the restock is not re-applied. The page keeps the plan face,
  owns every mutation, and passes lines down — the faces are presentational.
  Sectioning, the money ladder and the section iconography stay shared
  (`useLineSections`, now also exporting `sectionIconFor`).
- **Consequences:** Adding an affordance to one face no longer leaks into the
  others, and the run face can be tuned for a thumb without arguing with the plan
  face's density. The cost is a prop/emit seam per face, and a discipline: shared
  *behaviour* must go into the composable rather than being copied into the second
  face. Two adjacent surfaces already fit this shape — cook mode and Stocktake's
  three phases — and should be read against it when next touched. The reload
  discipline also surfaced `refreshDetailQuietly()`: `load()` blanks the page by
  design (right for navigation, wrong for the run face's per-tick reconcile of
  server-owned totals).
- **Promotes rule:** R-054.

### ADR-051 — Block-level edit toggles on the recipe page, not per-field popups
- **Date / task:** 2026-08-23 (recipe-view feedback batch)
- **Status:** accepted
- **Context:** `RecipeDetailNext.vue` shipped with every masthead value behind a
  `q-popup-edit`, and the owner reported the consequence directly: "you need to
  click once for the input to show, then again to get the options to show", plus
  inputs that "take the width of their option text", so an empty Difficulty was a
  narrow box. The same page put the list's *shape* (sections, order) in an
  "Organise ingredients" disclosure at the bottom, separated from the list it
  reorganised. Two candidate fixes were on the table — reveal the inputs on hover,
  or a pencil that flips the block — and hover fails outright on touch and still
  leaves the control sized to its content.
- **Decision:** two block-level pencils. The masthead flips identity + facts to a
  fixed `auto-fit minmax(160px, 1fr)` grid of real inputs and back; the
  ingredients section flips to an edit face carrying ↑/↓ (which also move a row
  *between* sections, including into an empty one), delete, per-section and
  global add, section rename/reorder/remove, and whole-row tap-to-edit. Leaving
  either mode commits, so the pencil reads as Done; a failed save keeps the block
  open. The read face keeps exactly one affordance — the shopping-list button on
  a missing ingredient. The "Organise ingredients" disclosure and the bottom
  "Recipe photo" disclosure are both deleted; their jobs moved to the thing they
  were about.
- **Consequences:** D-015's retired "read-view + explicit edit mode" clause comes
  back at *block* granularity — the page as a whole still reads as a document,
  which is what the retirement was protecting. The method's inline prose editing
  is deliberately untouched. Because leaving a mode saves, the Save button and
  the pencils are now three doors to one commit, and all three close both blocks.
  Any future detail page that grows a second `q-popup-edit` in one region should
  reach for this shape instead — that is R-055.
- **Promotes rule:** R-055.

### ADR-052 — A region that flips read↔edit renders both faces from one component
- **Date / task:** 2026-08-27 (recipe-view feedback batch)
- **Status:** accepted
- **Context:** R-055 says a region gets one edit toggle; it says nothing about
  how the two faces are built. The recipe method was built as two — a read view
  inline on the page, and `RecipeStepsEditor` + `RecipeStepRow` inside
  `RecipeMethodEditorDialog`. The result was three separate problems the owner
  reported as four separate items: the numbered-bullet geometry existed twice
  and had drifted (the read view's sub-step rule did not line up with its
  parent's numeral, and could not be made to without editing two stylesheets);
  the edit face was a *dialog*, which is neither of the shapes R-055 is about
  and which he rejected outright ("adopt the header edit style… it swaps
  in-place"); and the block visibly changed character mid-edit, which is the
  exact failure the block switch was introduced to prevent.
- **Decision:** the read face and the edit face belong in **one component,
  selected by an `editing` prop**. `RecipeStructuredMethod.vue` renders the same
  `<ol>`, the same bullets and the same indent in both modes, and swaps only what
  sits in the content column — a paragraph, or a field. The geometry that both
  depend on is declared once as CSS custom properties (`--rsm-num`, `--rsm-gap`)
  because three things read it: the bullet, the content column, and the sub-step
  rule that must run through the bullet's centre.
- **Consequences:** `RecipeStepsEditor`, `RecipeStepRow` and
  `RecipeMethodEditorDialog` were deleted (all three single-consumer). Controls
  that do not fit the read face's width move to a per-item dialog rather than
  forcing the shared layout wider — for the method that is
  `RecipeStepLinksDialog` (a step's ingredients, tools and section), which was
  also the fix for "serious lack of use of the horizontal space". The cost is a
  component with two template branches, which is real; the alternative is two
  components that agree only as long as someone remembers to change both, and
  this one had already stopped agreeing.
- **Not generalised to every pair of read/edit components.** This is about a
  region whose two faces must share a *visual structure* a reader carries across
  the flip. A form that replaces the page it edits has no such structure to
  preserve.

### ADR-053 — A regional convention is one setting on an axis wide enough to be true (promotes R-056)
- **Context:** the owner asked for a units config in Region & locale: *"Locale
  and region settings should also include units config, which then determines
  what units appear throughout the app … for universal ones, e.g. 'dash', always
  include those."* An `AppSetting.unit_pricing_locale` already existed on an
  "AU"/"US" axis, deciding whether a per-unit price read `/100g` or `/lb`. It had
  no UI anywhere and nothing but `your_prices.py` read it.
- **Decision:** replace it rather than sit beside it.
  `AppSetting.measurement_system` holds `metric` | `imperial` | `us`, drives both
  the picker vocabulary and the price denominator, and rides `/api/health`
  alongside currency and locale. The unit→system mapping lives once, keyed by
  canonical form, in `dora_api/domain/units.py` (`UNIT_SYSTEMS` +
  `UNIVERSAL_CANONICAL_UNITS` + `units_for_system`), and is emitted into
  `web_app/src/generated/units_table.ts` by the existing dump script, so the SPA
  filters a mirror rather than restating the table.
- **Why three values, not two.** The old axis could not express the UK: it uses
  pounds, ounces and the 568 ml pint in the kitchen while pricing in metric on
  the shelf, so it is neither "AU" nor "US". `imperial` therefore resolves to the
  *metric* pricing convention while offering imperial cooking units — the two
  questions have different answers for one real country, which is precisely why
  one setting can serve them both only if the axis is honest.
- **Why universal units are a first-class concept.** `pinch`, `dash`, `smidgen`,
  `tsp` and the count units belong to no system, and a filter that dropped them
  would be obviously wrong in a way the owner pre-empted in the request. They are
  a named set rather than an accident of the mapping.
- **Consequence — an off-system unit already on a row survives.** `useUnitOptions`
  takes an optional `includeValue` getter and keeps that one unit offered. An
  imported US recipe on a metric install must not have its saved `lb` disappear
  from its own dropdown; a closed list that silently drops a stored value is data
  loss dressed as a filter.
- **Migration:** `e4c7a2b9f1d3` maps `AU → metric`, `US → us`, and drops the old
  column. The downgrade folds `imperial → AU`, which is lossy in the picker but
  exact in the pricing behaviour — the honest direction to lose information in.
- **Promotes rule:** R-056.


### ADR-054 — A replaced endpoint's response is an inventory, not a casualty list (promotes R-057)
- **Date / task:** 2026-08-27 (owner feedback: meal-plan add-to-list unification)
- **Status:** accepted
- **Context:** The owner asked for the meal planner's one-shot "Generate shopping
  list for this week" to become the recipe page's reviewable "Add to list" flow.
  The two buttons look interchangeable, but the old one was a single call to
  `POST /shopping-lists/auto-generate`, whose response carried four things the
  new client-composed flow had nowhere to put: the unlinked-ingredient report
  (FU-505), the `auto_meal_plan` provenance stamped on each line, the generated
  list name, and the navigation into the new list.
- **Decision:** treat the old response as an inventory to be walked item by item
  before the call is deleted. Unlinked ingredients moved **server-side** into the
  ingredient aggregate as an envelope field, so the picker names them up front;
  the list name became the picker's pre-filled "+ New list" value; the navigation
  was kept for the create-new branch only. Provenance was the one deliberate
  drop — put to the owner as a named cost and accepted, because preserving it
  would have meant either a client asserting a server-owned fact or a new
  endpoint shape for one chip.
- **Consequences:** commits us to a small server change whenever a client-composed
  flow replaces an orchestrated one — which is the right side to pay on, since the
  endpoint had the domain in hand and the client doesn't. Rules out the quiet
  version of this refactor, where a flow gets friendlier and loses a safety net in
  the same commit. Does **not** require preserving everything: it requires each
  item to be a decision with a name on it.
- **Promotes rule:** R-057.


### ADR-055 — A gated domain a feature reasons in is a prerequisite, not a suppression (promotes R-058)
- **Date / task:** 2026-08-27 (owner question: "how useful is buy verdict with money turned off?")
- **Status:** accepted
- **Context:** The owner noticed the buy verdict rendering price prose on an
  install with money features off, and asked whether it should be properly gated
  or not shown at all. The audit found the leak was wider than the visible
  strings: `_price_axis` reasoned entirely in money, the `wait` direction was
  reachable *only* via `above_usual` / `fake_markdown`, and
  `_PRICE_STRENGTH_MODIFIER` shifted the verdict's strength. Neither the endpoint
  nor any of the three render sites referenced `money_enabled` at all — the only
  gate was the per-user display opt-out. What survived money-off was need + waste,
  both of which `PantryBeliefCard` (directly above it on the same page) and
  `stock_attention` already state in the same words.
- **Decision:** money is a **prerequisite** for the whole surface. The two
  endpoints refuse with 403 when the install has money off; `useBuyVerdictEnabled`
  ANDs the install flag with the per-user preference; the Assistant settings
  toggle disables with a caption naming the prerequisite (and the per-user
  preference survives underneath). Rejected the alternative — per-reason
  suppression — because it is strictly more work (a money-free headline
  vocabulary, a non-dollar icon, a rewritten footer, a dead `wait` branch) for a
  weaker result that still duplicates its own neighbour, and because it would
  have left the strength modulation silently in place.
- **Consequences:** commits us to answering "prerequisite or independent?" for
  every flag-adjacent surface, and to gating at all three seams when the answer is
  prerequisite. Costs a real capability on money-off installs — accepted, on the
  Charter's Anti-creep tiebreak: two cards saying one thing is worse than one card
  saying it. Rules out the pattern where a feature keeps reasoning over data the
  install disabled as long as it doesn't print it. Does **not** mean every flag is
  a prerequisite — `useMoneyEnabled`'s existing render gates on Stock Overview and
  Shopping List Detail are the independent case, where hiding a column leaves the
  rest correct.
- **Promotes rule:** R-058.

### ADR-056 — A transcribed standard is only as trustworthy as its citation and its worked examples (promotes R-059)
- **Date / task:** 2026-08-27 (adding Nutri-Score alongside the Health Star Rating)
- **Status:** accepted
- **Context:** Dora needed a second national front-of-pack rating. The first one
  (HSR) had been transcribed carefully from the FSANZ guide with per-table
  citations, but that was a habit rather than a rule, and nothing in the repo
  said how to do it again. Scoping Nutri-Score surfaced how easily it goes
  wrong: the algorithm was revised in 2023, most third-party write-ups blend the
  two generations without saying so, and the two generations disagree on values
  that change a food's letter — sugars 0–10 vs 0–15, sodium(mg) vs salt(g),
  protein 0–5 vs 0–7, grade-A at `< 0` vs `< 1`, and a protein carve-out that
  exists only in the original. The official workbook is authoritative but
  computes **both** generations on one sheet, so it will also hand you the wrong
  answer if you read the wrong columns — which happened once during this build,
  and produced both a confidently-wrong statement to the owner and a phantom
  "the docs contradict the tool" conclusion. What caught it was replaying the
  three worked examples that ship inside the workbook.
- **Decision:** transcription of an external standard is a distinct kind of work
  with its own bar: primary source only, version named, table cited beside each
  constant, revisions' disagreements asserted explicitly, and tests built from
  the source's own worked examples rather than hand-computed or
  implementation-derived expectations. Where the standard cannot be honestly
  applied to Dora's data (a recipe is not a packaged product), the departure is
  documented in the module docstring with its direction of error rather than
  quietly approximated.
- **Consequences:** transcription tasks cost more up front — obtaining a
  primary document and its calculator is real work, and this one meant reading
  an official `.xlsx`'s formulas. Accepted: the alternative failure is silent,
  survives review and manual testing, and mis-scores users' food under the name
  of a government scheme, which is the specific kind of wrong this product
  cannot afford. Also commits us to re-checking these modules when a standard
  revises, and gives that check a cheap trigger — the revision-disagreement test
  fails the moment someone reaches for the wrong generation. Does **not** apply
  to internal domain constants (a "7-day window" is Dora's own choice, governed
  by R-003) — only to arithmetic we are reproducing from someone else's
  published authority.
- **Promotes rule:** R-059.

### ADR-057 — A design token that does not exist is worse than a hardcoded value (promotes R-060)
- **Date:** 2026-08-28.
- **Context:** the cook-mode header was rebuilt for mobile on 2026-08-27 in
  response to *"it just squishes in the desktop UI"*. The owner came back on
  2026-08-28 with the same complaint, wider: *"Everything is squished badly on
  desktop too"*, *"no margin from other elements"*, *"Cooking for input looks god
  awful. All squished together."* The obvious reading is that the layout was
  wrong twice. It wasn't. Every gap in the file — `.cook-header`,
  `.cook-header__identity`, `.cook-header__cooking-for` — was written as
  `var(--space-sm)` or `var(--space-xs)`, and neither token has ever existed;
  Dora's spacing scale is numeric (`--space-1..--space-12`). Those declarations
  were invalid, so the gaps were **zero**. The same file also had
  `background: var(--surface-card)` (also undefined), and the image view had four
  more against `--c-line` / `--c-surface-2`. A repo-wide grep found the two
  cook-mode files were the *only* users of the fictional spacing aliases — the
  bug was introduced once and copied once.
- **Decision:** treat "token exists" as a checkable precondition, not an
  assumption (R-060). Grep `css/` before using an unfamiliar token; add real
  tokens to `tokens.scss` rather than inventing names at the call site; never
  ship a bare `var()` whose fallback is not either present or verified.
- **Consequences:** costs one grep per unfamiliar token. Buys the thing this
  session actually needed: the ability to tell "my layout is wrong" apart from
  "my CSS never ran". Note the failure mode is *asymmetric* — a hardcoded `8px`
  is a token violation (R-002) that reviewers catch and that at least renders;
  an undefined token passes review, passes lint, passes typecheck, and renders
  nothing. The cheap-to-catch mistake is the safe one.
- **Alternative considered:** a stylelint rule or a build-time check that fails
  on unknown custom properties. Correct long-term and worth doing when the CSS
  surface is next worked on — logged as FU-764 — but it is a tooling change with
  its own rollout, and it should not gate a feedback fix.
- **Promotes rule:** R-060.

### ADR-058 — A stored price is not evidence a purchase happened (promotes R-061)
- **Date:** 2026-08-28.
- **Context:** the owner asked, during the shopping-list feedback batch, whether
  unticked items were "polluting/poisoning receipt money amounts and reporting".
  The receipt was clean — `compute_list_totals` has applied `spent_only` on done
  lists all along. `period_spent` was not: it summed every line on an archived
  list, in both the current-period and the history path. The reason this is a
  real defect rather than a theoretical one is a *deliberate* design decision
  made elsewhere: `snapshot_offer_price` freezes the offer price when a line is
  **added**, so historic reporting stays honest if prices move before the shop.
  Correct on its own terms — and it means an unticked line reliably carries a
  price it never cost. A $60 shop with $40 of leftovers reported $100 spent, and
  `period_headroom` passed that to the trim-to-budget optimiser. Auditing the
  rest of the codebase found the same "has a price ⇒ was bought" inference in
  four more places (suggestions, pantry belief, buy verdict, waste), one of them
  carrying a comment explicitly asserting the opposite — logged as FU-768.
- **Decision:** make the purchase *event* the filter, never the price's presence
  (R-061), and mirror `compute_list_totals`' existing rule rather than inventing
  a second one.
- **Consequences:** one predicate per money query. The wider value is naming the
  trap: a snapshot taken for provenance and a snapshot taken as proof-of-purchase
  look identical in the schema, and only the *write path* distinguishes them —
  which is invisible at every read site. Anywhere two features disagree about the
  same shop, this is the first thing to check.
- **Alternative considered:** clearing `picked_offer_price` on unticked lines at
  finish time, so the data itself could not lie. Rejected — it destroys the
  planning-time provenance the snapshot exists to preserve, and it would fix the
  five known readers by corrupting the record for every future one.
- **Testing note:** the regression test uses a **real** repository against a
  throwaway SQLite engine, not the codebase's usual fake-repo pattern, because
  the unit under test *is* a query predicate — a fake that ignores the filter
  passes with the bug intact. It was mutation-checked (revert the filter → $95
  against an expected $30) before being trusted. Worth repeating whenever a test
  covers a filter rather than a calculation.
- **Promotes rule:** R-061.

### ADR-059 — A lazy-hydration cache is invalidated by the writes its derived fields depend on (promotes R-062)
- **Date:** 2026-08-28 (cookbook nutrition-filter batch).
- **Context:** the owner reported that the cookbook's health-star and kcal
  filters didn't work. Three causes sat underneath, and the dominant one was
  not the filters: `recipeStore.ensureLoadedAsync` returned early forever once
  `recipesHydrated` flipped, so linking nutrition data to a stock item and then
  navigating to the cookbook rendered the pre-edit payload. Nothing in the
  codebase invalidated the recipe list on a stock write, even though a recipe
  DTO carries five distinct stock-derived fields. Three features had already
  each invented a private cache-invalidation helper for their own version of
  this problem, which is the signal that the idea deserved a name.
- **Decision:** the writing store owns the invalidation (R-062). `stockItemStore`
  marks recipes stale on create/update/level-change/delete; the two paths that
  bypass it — `bulkSetLevelAsync` and the server-side bulk food link — do it at
  their call sites.
- **Consequences:** one flag per store rather than a subscription mechanism. It
  deliberately over-invalidates (a rename marks the list stale too) because the
  alternative is a per-field allow-list that is a second copy of server
  knowledge (R-003) and goes wrong the first time a DTO gains a field. Cost is
  one extra list fetch after a stock write, and only on the next visit.
- **Alternative considered:** dropping the lazy cache and refetching on every
  cookbook mount. Rejected — it re-creates exactly the redundant-fetch problem
  R-016 exists to prevent, and the cookbook pages until exhausted (500 rows).
- **Verification note:** proven by driving the running app twice in one page
  session — revisit with no stock write issued no `/api/recipes` request;
  revisit after a real `PATCH /api/stock-items/...` issued one. A page reload
  between visits would have refetched regardless and proved nothing; any future
  test of this must stay inside a single SPA session.
- **Promotes rule:** R-062.

### ADR-060 — Planning and recording are two fields, chained by prefill (promotes R-063)
- **Date:** 2026-08-28.
- **Context:** owner, on the shopping list: *"I noticed changing the store for
  the item does not move it between store groupings… the way I interpret this is
  this field is only for stamping at the end. The gap I then see is people are
  unable to change which store they want to get the item from on the list before
  shopping, they can only mark where they actually got it from at the end."* The
  diagnosis was right. `ShoppingListLine.purchased_store_id` was the only
  writable store on the plan face, and it is rung 1 of the store ladder — so
  setting it *did* re-group the line, which is precisely why nobody had noticed
  that planning and recording were sharing a field. The same surface had the
  same bug in money: the draft price editor wrote `actual_unit_price`.
- **Decision:** add `planned_store_id` per line (R-063). Chain it
  `usual → planned → purchased` as *defaults only*; insert it into the store
  ladder between bought-from and the item's usual store.
- **Consequences:** one column, one migration, one extra ladder rung. Buys the
  ability to plan a shop that differs from habit without rewriting the habit, and
  it makes the store breakdown answer "where am I about to spend" honestly rather
  than by reading a field that means something else.
- **Why not `StockItem.usual_store_id`:** wrong scope. It is a standing
  preference; setting it from one list silently changes every future list. The
  scope ladder (per-occurrence → per-entity → per-install) is a real distinction
  and collapsing two of its rungs is the same mistake as collapsing intent and
  record.
- **Why no backfill and no write-back:** a NULL planned store already falls
  through to the usual store, so copying values in would freeze a live inference
  into a stale literal — and buying somewhere once is not a change of plan, just
  as it is not a change of habit (`usual_store_id` has never had a write-back
  either; ADR-058's sibling concern).
- **Side effect worth noting:** the ladder reached five rungs as an if/elif chain
  inline in the detail handler, where nothing could test its ordering. It moved
  to `_line_price.resolve_store_id`, beside the money ladder, and is now pinned
  by `tests/test_store_ladder.py` — including the two orderings that are
  counter-intuitive (intent beats history; the more specific intent wins).
- **Promotes rule:** R-063.

### ADR-061 — The ORM session and the Core access helpers are one transaction with two visibility rules (promotes R-064)
- **Date:** 2026-08-29.
- **Context:** owner, on the recipe page: *"Bug: linking ingredients to step is
  broken (cannot save)."* Reproduced at the API in one PATCH: the server answered
  400 *"Step references ingredients not on this recipe"*, naming two ids — and
  those ids were neither what the request sent nor wrong. They were the correct
  post-replace ids, resolved by a map that worked exactly as designed. The rows
  simply were not in the table yet: `update_recipe` had added them to the ORM
  session, and `_validate_link_targets` looked for them with a Core
  `select(RecipeIngredient)`, which does not autoflush.
- **Decision:** the caller flushes at the seam (R-064), matching what
  `create_recipe` had already been doing for the same reason since FU-456.
- **Consequences:** one `repository.flush()` and a comment. The blast radius was
  larger than the report suggested: because the page re-sends `steps` on every
  save of a structured recipe, a single linked step made *every* subsequent edit
  to that recipe unsaveable — which is almost certainly the "an error was
  encountered" in the owner's unrelated unit-change report in the same batch.
- **Why not fix it inside the access helper:** a helper that flushes on entry
  cannot know whether its caller is mid-way through building an object graph, and
  flushing a half-built graph is a worse bug than the one being fixed —
  `seed.py` disables autoflush outright for exactly that reason. Visibility is
  the caller's concern because only the caller knows when its mutations are
  complete.
- **Why not convert the helpers to ORM queries:** the Core style is deliberate
  (portable, no lazy-load surprises, one place per table) and R-005's
  portability posture leans on it. The rule is cheaper than the rewrite.
- **Covered by:** `tests/e2e/dora_api/test_recipe_step_ingredient_links.py` — two
  tests, both confirmed red before the fix and green after.
- **Promotes rule:** R-064.

### ADR-062 — `show_recipe_images` is cut; the cookbook's view switch is the only photo control (promotes R-065)
- **Date:** 2026-08-29.
- **Context:** owner, on Settings → Appearance: *"I'm thoroughly confused about
  the recipe photos toggle in appearance settings. What is this even for??"* The
  honest answer was "almost nothing". PROPOSAL_CONFIG_AND_OPTINS §2.8 designed
  `User.show_recipe_images` to govern recipe cards, the detail header, the edit
  preview, cook mode and print/export — so a user could *"run a text-dense, fast,
  low-bandwidth UI without losing the underlying data"* — written from an inline
  cookbook-toolbar button, with an explicit "No Settings page entry". By 08-29 it
  governed the recipe page's hero image and the recipe cards on the stock-item
  detail page, and it lived in the settings page the proposal ruled out.
- **Decision:** cut it — the flag, the composable, the `RecipeCard.showImage`
  prop, and the `User` column (migration `e3b1d7f5a904`). Recipe photos render
  unconditionally; photo density on the cookbook is the cards/compact switch.
- **How it decayed, because that's the transferable part:** FU-508 deleted the
  `show_stock_images` half; the 2026-08-18 owner call gave the cookbook's
  cards/compact switch ownership of photos *there* (which is why the write button
  left the toolbar — the write surface moved while the read surfaces evaporated);
  and cook mode, print/export and the meal-planner rail never consulted it at all.
  Each step was locally reasonable. None looked like a change to the preference.
- **The tell that it was already dead:** the help text had become *"The cookbook
  decides its own — cards show photos, compact rows don't."* A setting that has to
  name where it doesn't apply has already lost its meaning (R-065).
- **Consequences:** one fewer settings row, one fewer column, one fewer prop, and
  `hasPhoto`/`photoUrl` on the recipe page collapse into each other — they only
  ever differed to express "a photo exists but you asked not to see it". The
  low-bandwidth use case is genuinely lost on the recipe page; it was already lost
  everywhere else, and the cookbook — the grid of many photos, i.e. the actual
  bandwidth — has the better control for it.
- **Why not re-wire it to its original scope:** that rebuilds a feature the owner
  already replaced on the cookbook, and would put two competing photo controls on
  the same page. The offered alternative was declined in favour of the cut.
- **Why drop the column rather than leave it:** a boolean nothing reads is a trap
  for the next person, and it would show up in `/auth/me` forever. Dropping it
  also makes `PATCH /auth/me {show_recipe_images}` a 400 rather than a silent
  no-op, which is the honest answer to a stale client (verified).
- **Promotes rule:** R-065.


---

## Known fixes / things to try

A non-binding cookbook of solutions to recurring problems. Not rules — just a
"if you're chasing X, here are previously-found answers worth trying first."

### A `q-select` dropdown only offers the value already selected
- **Symptom:** opening a `use-input` select on a row that already has a value
  shows one option — its own current value — or "No results" if that value isn't
  in the option list. Clearing the input by hand reveals the real list.
- **Cause:** `fill-input` parks the selected label in the input, and
  `QSelect.showPopup` re-runs your `@filter` handler with the input's current
  text every time the menu opens. So the vocabulary is filtered by the selection
  before you can see it.
- **Try first:** drop `fill-input` + `hide-selected`. They earn their place on an
  *open* typeahead (hundreds of rows, free-text creation — the "apple apple" fix
  on the ingredient item picker) and cost you the whole list on a *closed*
  vocabulary, where the selection should render as the field's value and the
  input should start empty. Found on the recipe ingredient editor's Unit picker,
  2026-08-29; the substitute dialog's identical picker had always been right.
- **If you must keep them:** clear the input on `@popup-show` via a ref
  (`updateInputValue('', true)`); `fill-input`'s own watcher restores the label
  when the menu closes.

### A `q-select` stores `{label, value}` instead of the value
- **Symptom:** picking an option "works" visually, then something downstream
  throws on the model — classically `x.trim is not a function` — and the error
  boundary tears down the dialog.
- **Cause:** `:options` are objects but the select has no `emit-value` +
  `map-options`, so QSelect writes the whole option into the model. Nothing in
  `vue-tsc` catches it: the v-model target is typed `string | null`, and the
  write happens through QSelect's untyped `update:model-value`.
- **Try first:** add `emit-value map-options` wherever `:options` is an array of
  objects and the model is a scalar. Found on the recipe ingredient editor's Unit
  picker, 2026-08-29 — its sibling in `SubstituteMetadataDialog` had both props
  and worked, which is the fastest way to spot the omission.

### Snap / jump at the end of a `q-slide-transition` close
- **Symptom:** The collapsing panel slides smoothly, then a small gap
  disappears in one frame at the very end (or appears, on open).
- **Cause:** `q-slide-transition` animates the element's `height`. Any
  margin/padding that contributes to layout *outside* the animated height
  doesn't shrink with the animation — it's still there at `height: 0`, and
  then `v-if` removes it instantly. `box-sizing: content-box` makes
  `padding` part of this problem too: `height: 0` + `padding-top: 8px`
  still occupies 8px until removal.
- **Try first:** put **all** vertical spacing on the *non-transitioning*
  parent (`q-py-md` on the outer wrapper, etc.) and leave the
  height-animating element with **zero margin/padding** of its own. Fixed
  on FilterBar 2026-06-09.
- **If that's not viable:** `box-sizing: border-box` + `padding` (no
  `margin`) on the transitioning element can also work, but the parent-padding
  approach is simpler and has been the reliable answer.
### ADR-063 — Chip styling belongs to `colours.scss`, not to whichever component drew it first (promotes R-066)
- **Context:** the recipe page's ingredient rows carry two state chips side by
  side. "Missing / Swap ready" was reworked on 2026-08-31 into a soft-tinted
  pill — semantic tint, semantic hairline, coloured glyph, neutral ink, 28px
  tap target — with a measured D-002 carve-out explaining why the ink stays
  neutral. That whole look was declared inside `RecipeMissingIngredientChip`'s
  scoped block. The "Use soon" / "Expired" chip beside it was a Quasar `q-chip`
  with `color="warning" text-color="dark"`: a solid square badge with dark ink.
  The owner, reading one row: *"ensure missing and use soon chips are styled the
  same (recently improved the missing one)"*. The day before, the same shape had
  produced the same complaint on the cookbook, where the dietary tag and the
  belief chip were one outline chip declared in two components.
- **Options:** (a) copy the tint block into the page's scoped styles — the third
  copy of a look whose contrast reasoning lives in a comment somewhere else;
  (b) wrap the expiring chip in its own component so the two are siblings — but
  they are not siblings, one owns a substitutes menu and the other is inert, so
  the shared thing would be a styling base class in component clothing;
  (c) promote the look to a shared class in `colours.scss` and let each component
  keep only its own behaviour.
- **Decision:** (c) — `.dora-chip--tint` plus `--tint-negative` / `--tint-warning`
  / `--tint-positive` in `colours.scss` (R-066), carrying the D-002 carve-out note
  with them. `RecipeMissingIngredientChip` composes the class and keeps its
  hover / focus / menu rules; the page's expiring chip stops being a `q-chip`
  and becomes a span wearing the same classes. This matches `.dora-chip--neutral`,
  added the previous day for the cookbook pair, which is what turns it from a
  tidy into a pattern.
- **Consequences:** the two chips are now provably identical — measured live at
  the same 28px height, radius, padding, font size and weight, differing only in
  tone. A third state chip on any surface has a class to reach for. The cost is
  one more global class in `colours.scss`, and the discipline of grepping it
  before styling a chip. One real bug surfaced only because the two were finally
  measured together: the two-word label "Use soon" was wrapping *inside* its own
  tint, making that chip 37px next to a 28px neighbour — fixed with
  `white-space: nowrap` on the shared class, which now protects every chip that
  wears it.
- **Promotes rule:** R-066.


### ADR-064 — The stocktake runner follows the theme; focus mode is layout, not an inverted palette (promotes R-067)
- **Context:** the runner shell was written to stay dark under every theme —
  `background: var(--palette-neutral-900)`, with a comment saying the contrast
  *is* the "you're concentrating" affordance, and with each phase component
  painting its heading `--text-inverse` to survive it. Driving the app in a light
  theme, the owner hit stocktake and read the black screen as a defect rather
  than as an affordance.
- **Decision:** the shell takes `--surface-page` / `--text-primary` like every
  other route, and the phase headings drop `--text-inverse`. Focus mode keeps
  everything that actually made it one: the full-bleed page, the single card, no
  nav, the close X and the progress strip.
- **Consequences:** stocktake now looks like the rest of the app under all theme
  families instead of like a different product under the light ones. The
  dark-theme experience is unchanged in kind — the shell was already dark there;
  what's gone is the light-theme surprise. Generalised as R-067, because the same
  "pin a palette token to set a mood" instinct is available to any full-page
  surface — cook mode and the shopping-list run face are the nearest candidates
  and should be checked against it opportunistically.
- **Promotes rule:** R-067.


### ADR-065 — A structured step records its own timer; the text sniff survives as a labelled fallback (promotes R-068)
- **Context:** cook mode's timer card was driven entirely by a regex over the
  current step's text — `/(\d+)\s*(minutes?|mins?)/` then hours — for all three
  step faces. The owner asked whether it was guessing: *"I feel this might be
  okay for free text but for structured I feel a tickable box option should be
  added"*. The distinction is exactly right and it is a payload distinction, not
  a preference: a free-text method is one prose blob with nowhere to record
  "this step is timed", while a structured step is a row that can carry a column.
- **Decision:** add `RecipeStep.timer_minutes` (nullable Integer, 1..1440
  validated at the request boundary). The structured method editor toggles it per
  step and sub-step with the same `null`-vs-value two-state the `hint` field
  already uses — one flag, no second `showTimer` ref that can disagree with the
  data. Cook mode prefers a declared timer and falls back to the sniff, which now
  captions itself "from this step's wording" so a guess never reads as a
  recorded fact. Free-text and photo recipes are unchanged in behaviour, and
  gain the caption.
- **Consequences:** the change is additive — NULL means "nothing declared", so
  every existing recipe keeps exactly the behaviour it had. The dense seed now
  carries two declared timers (15 min, 3 hr) so the surface has a fixture, and
  the 70%-hydration pizza dough remains an unimproved sniff case (a 2880-minute
  countdown off "48 hours in the fridge") — which is the honest demonstration of
  why the caption exists. Generalised as R-068: the same "parse it back out of
  the prose" instinct is available anywhere the schema is thinner than the
  feature, and the importer's serving/time parsing is the nearest neighbour
  worth checking against it.
- **Promotes rule:** R-068.

### ADR-066 — Accent gets an ink-strength sibling token rather than a per-theme fork (promotes R-069)
- **Date / task:** 2026-09-01 (owner feedback: pesto yellow unreadable as text)
- **Status:** accepted
- **Context:** `--brand-accent` is the app's identity colour and doubles as the
  active-state colour for tabs, segmented controls, settings nav indicators,
  page-header icons, theme cards, the voice picker and two Help buttons. It is
  tuned as a **fill** — it is the toolbar in pesto and the ground under
  `--text-on-accent`. As ink it measures 1.39:1 on white in pesto and 1.25–2.04:1
  across all five light families; every light theme was therefore shipping
  invisible active-tab labels. `DoraChat` had already hit this and worked around
  it locally with a `.body--dark` fork that dropped the accent entirely in light
  mode — a fix that solves one component and loses the brand colour to do it.
- **Decision:** add `--accent-ink` beside `--brand-accent`, defined in
  `tokens.scss` and overridden in all ten `[data-theme]` blocks. Light families
  keep hue + saturation and drop lightness to 24–30% (measured 4.5–5.7:1 across
  component/page/elevated/sunken); `pesto-dark`, `lemon-tart-dark` and
  `cherry-cola-dark` lift theirs a few points to clear the floor on `elevated`;
  `blueberry-dark` and `sourdough-dark` point straight at `var(--brand-accent)`,
  which already measures 5.9:1 and 9.1:1. Call sites split by **ground**: ink on
  page/component surfaces, the raw accent kept on the toolbar (main-menu buttons,
  the wordmark), in glows, and inside `color-mix()` tints. `.dora-text-accent`
  in `colours.scss` covers template-side use where Quasar's `color="accent"` on a
  flat button would paint the fill tone.
- **Consequences:** one declaration now covers both modes, so the `.body--dark`
  fork in `DoraChat` is gone and light themes keep the accent identity instead of
  falling back to plain ink. The token is a standing contract: a theme that
  changes its accent must re-measure its ink. Deliberately **not** done here — a
  matching `--primary-ink`. `--brand-primary` fails the same test as ink in the
  light families (lemon-tart 1.63:1, sourdough 2.34:1, pesto 3.89:1), but it is
  consumed overwhelmingly through Quasar's `color="primary"` rather than through
  CSS vars, so the sweep is a different (larger) job — logged as a follow-up
  rather than half-done alongside this one.
- **Promotes rule:** R-069.


### ADR-067 — A preserved off-vocabulary label is allowed back in on update, per record (promotes R-070)
- **Date / task:** 2026-09-01 (meal-planner owner batch)
- **Status:** accepted
- **Context:** meal slots are a household-editable vocabulary, and deleting one
  is deliberately non-cascading: `MealPlanEntry.slot` and `Recipe.time_of_day`
  keep their label string (there is a test, and the delete dialog says so). But
  `update_meal_plan` and `update_recipe` validated their payloads against the
  live vocabulary with no reference to what the record already held, while both
  of their clients resend the whole record on every edit. Deleting "Snack" left
  the week rendering fine and then rejecting every subsequent save with
  `Invalid meal slot 'Snack'`. Measured live: 400 on a PATCH the user triggered
  by adding an unrelated breakfast four days later.
- **Decision:** the allowed set on an *update* is the vocabulary **plus the
  labels that record currently carries** — `allowed_slot_names(valid,
  already_stored)`, a single shared helper in `slot_validation.py` rather than
  the same expression written twice. Create paths are untouched (no history to
  preserve). Three alternatives were rejected: (a) cascade the delete — reverses
  a settled decision and destroys history the user was promised would survive;
  (b) have the client stop resending unchanged entries — it cannot know which
  are unchanged without diffing server state, and it would leave the API still
  refusing a legitimate payload; (c) drop the write-time check — the vocabulary
  would stop meaning anything and free-text slots would creep back.
- **Consequences:** a record can carry its own history forward indefinitely, and
  the off-vocab label keeps surfacing in the planner's "Other" row, which is
  where the user notices and fixes it. The allowance is per-record, so it cannot
  spread: a *different* plan still cannot adopt "Snack". The error message
  deliberately continues to list only the live vocabulary. `new_recipe_version`
  copies `time_of_day` without validating, so it was already correct.
- **Promotes rule:** R-070.

### ADR-068 — "Saved" splits by tense: vs shelf price while shopping, vs your own usual price in the report (promotes R-071)
- **Date / task:** 2026-09-02 (owner decisions on the dashboard + reports page reviews)
- **Status:** accepted
- **Context:** both page reviews landed on the same metric from different sides.
  `SavingsCapturedHandler` (`reports.py:774-843`) sums
  `list_price_at_pick − picked_offer_price` over ticked lines of archived lists —
  i.e. **savings against the retailer's advertised RRP**, snapshotted at pick time
  — and renders as "You've saved $X vs RRP" on both the Reports card and the
  dashboard's Money-zone flagship. The reviews' objection (REPORTS §3.7, DASHBOARD
  §3.5) was that this measures *how good the specials were*, not *how little the
  household spent*: it rises when you buy a heavily-discounted thing you did not
  need, which is the opposite of what Dora is for. Meanwhile three other surfaces
  render a **different** computation under the same words — the primary-list card
  stat (`DashboardPage.vue:396`), `ShoppingListOverviewCard.vue:496`, and the
  per-line model (`shoppingList.ts:282`), all live in-list savings against the
  chosen offer's `price_was`. Two computations, one word, neither labelled.
- **Decision:** *(owner, 2026-09-02)* **split by tense.**
  1. **Live, in-list** savings stay **vs shelf price (RRP)** — while standing in
     the aisle, "what this offer is under the ticket" is the honest question, and
     it is the only baseline available for an item with no price history.
  2. **Retrospective** savings — the "Savings captured" card on both surfaces —
     move to **the household's own historical unit price** for that item, so the
     number means "money you kept versus what you normally pay".
  3. **Both are labelled.** Neither renders a bare "saved $X"; each names its
     baseline in the copy *and* in the DTO field name (R-071).
  4. **Spend becomes the headline** on the retrospective card, with savings as the
     supporting line — the card answers "what did this cost" first.
  5. The own-price baseline gets its **own snapshot column** (`usual_price_at_pick`
     or equivalent) written on the finish-shop path beside `list_price_at_pick`.
     Deriving it retroactively is rejected: it would make every past shop's savings
     move each time a new price is logged, which is precisely what the existing
     snapshot design prevents.
  6. **Existing archived lists are reseeded, not backfilled** *(owner)* — the
     column is added, nothing is back-filled, and the dev/demo dataset is
     regenerated so the metric is coherent from its first row. Consistent with the
     standing pre-release posture (no real users; clean non-preserving migrations
     are allowed). The three rejected alternatives: backfill from today's
     observations (dishonest per (5)); null savings before a cutover date (honest
     but opens the chart on a dead region); keep pre-cutover lists on the old
     metric (one chart summing two baselines — the exact thing R-071 forbids).
- **Consequences:** "saved" becomes two named figures rather than one ambiguous
  one, and the retrospective number stops rewarding advertised discounts. The
  Money-zone consolidation (DASHBOARD §3.5 — budget folded into savings) is
  downstream of this and inherits the spend-first hierarchy. Cutting "Best deals"
  (FU-819) removes the last *card* whose ranking rested on the vs-RRP baseline;
  `discountPercent` survives as a per-offer display helper, which is legitimate —
  a single offer's % off the ticket is a shelf-price question. A stock item with no
  price history has no own-price baseline, so the retrospective figure must report
  its coverage per R-041 rather than treating unpriced lines as zero savings (the
  current handler's RRP-missing fallback does exactly that and will need the same
  treatment).
- **Promotes rule:** R-071.

### ADR-069 — A deferred DoD row keeps its own tracking; the follow-up is a pointer, not a substitute (promotes R-072)
- **Date / task:** 2026-09-02 (dashboard review Chunk 5 — the de-monolith, FU-829)
- **Status:** accepted
- **Context:** componentisation-not-finished has now been found **five** times
  (`ShoppingListDetail.vue` at 3,784 lines — [[FU-780]], still open; the reports
  page's inline card bodies; two earlier sweeps flagged for promotion at the
  2026-09-01 close-gate; and this one). R-001 already says componentise, so a
  sixth restatement of R-001 would not have helped — every one of those sightings
  happened in a codebase that already had R-001 and whose authors had read it. The
  dashboard instance is the diagnostic one because the goal was not merely implied
  by a rule, it was **written down as a Definition of Done** and assigned to a
  follow-up: `IMPL_PLAN_DASHBOARD_REBUILD.md` §6 promised the monolith was gone,
  [[FU-293]] was spun off to make it so, FU-293 extracted the card shell,
  documented its own carve-out (*"card BODY SCSS stays in the page"*), resolved,
  and moved to the archive. From that moment the DoD row had no tracker, the impl
  plan read as complete, and the page grew from 1,964 to 3,126 lines — with the
  three cards that *had* been extracted drifting to three different token
  conventions ([[FU-822]]) and `.dora-deal-row` duplicated by two cards 400 lines
  apart. So the recurring decision is not "should we componentise" but **"where
  does a deferred promise live once its ticket is closed?"**
- **Decision:** the DoD row is the durable object; the FU is a pointer to it.
  1. An FU spun off a written DoD **cites the plan and the row** it stands for.
  2. A partial resolution is allowed and encouraged — but its resolution note
     carries a **`DoD rows: closed / still open`** statement, and the remainder
     FU must be **open in `DORA_FOLLOWUPS.md` before** the parent is archived.
  3. A DoD row is closed only by something that says it closed *that row*.
  4. This generalises past DoDs to any durable checklist worked through
     disposable tickets: plan phases, a review's chunk list, a proposal's
     acceptance criteria.
  Rejected: **(a)** re-verifying every impl plan's DoD at each close-gate —
  unbounded work, and the reason the retired `STATUS.md` audit went stale;
  **(b)** forbidding partial resolution — shell-before-bodies was the *right*
  order here, and a rule that made it inexpressible would have produced a
  worse refactor or a stalled FU; **(c)** leaving the parent FU open until the
  whole DoD lands — an FU that stays open for two months across five phases
  stops being read, which is the same invisibility by a different route.
- **Consequences:** commits every future DoD-derived FU to naming its parent row
  and enumerating its residue at close — a few lines of bookkeeping per
  resolution, paid by whoever is already writing the note. It does **not**
  introduce a new ledger or a periodic audit; the invariant is local to the
  moment of archiving, which is the one moment someone is definitely looking. The
  four other componentisation sightings are *not* retroactively covered by this —
  they were never DoD-derived, so they remain plain R-001 findings ([[FU-780]] is
  the live one). Two consequences fall out immediately: this session's own Chunk 5
  close must state which `IMPL_PLAN_DASHBOARD_REBUILD.md` §6 rows it closed (the
  thin-composition row — now genuinely closed at 1,775 lines with all fourteen
  bodies extracted) and which it did not (the token rows, still [[FU-828]]); and
  the residue this refactor itself deferred — the page-local `--c-*` alias layer
  ([[FU-747]]) — is named rather than left as a comment.
- **Promotes rule:** R-072.

### ADR-070 — The chart is a drawing primitive, not a product-history widget (promotes R-073)
- **Context:** `/reports` needed two charts — the product price-trends line it
  already had, and a new own-item trend for chunk 4 — while carrying ECharts at
  **549 KB inlined into the Reports route chunk** for the first of them. The app
  also owned `PriceHistoryChart.vue`: 488 lines of inline SVG doing multi-series
  polylines, y-ticks, x-labels and a hover crosshair, in **8 KB**, already
  drawing exactly that chart. It could not be reused as it stood, because its
  props were the *product* price-history DTO and its drawing logic branched on
  `offersAsContext` / `hasOffers()`. The evidence that this was a real cost, not
  a theoretical one: `PriceHistoryBottomSheet.vue` had already resorted to
  fabricating a product DTO out of a stock item's history to get a chart out of
  it, with a `product_id` holding a stock-item id.
- **Options:** (a) keep ECharts and add a second ECharts chart for chunk 4 — the
  inertia option, and it makes the 549 KB serve two widgets instead of one;
  (b) build a second SVG chart for stock items — two chart components, guaranteed
  to drift; (c) generalise the owned chart to a neutral series shape and move
  payload interpretation into an adapter module.
- **Decision: (c).** `PriceChartSeries` (`key`, `name`, `points`,
  `contextPoints`, `baseline`) is the chart's vocabulary; `usePriceChartSeries.ts`
  holds one adapter per payload; the chart's remaining props are presentation
  (`legend`, `contextLabel`, `emptyLine`, `ariaLabel`). Four consumers now share
  it — `/price-history`, the stock item's full-history sheet, Reports' Price
  trends and Reports' Price changes — and `echarts` + `vue-echarts` are out of
  `package.json`. **Measured: the Reports route chunk went 549 KB → 24 KB**, plus
  an 8.5 KB shared chart chunk.
- **Consequences, including the ones that cost something:** the line is no longer
  smoothed and a gap in a series is now a gap — both make the chart claim less
  than ECharts did, which is the point, but they are visible changes. ECharts'
  `autoresize` is gone, so each host measures its own box and passes a width; that
  is now the same three-line pattern in four places and is a candidate for a
  `useMeasuredWidth()` if a fifth appears. Touch interaction is still absent
  ([[FU-705]]) — the swap neither fixed nor worsened it. In exchange the chart
  gained a legend (two of three consumers had none; the third hand-rolled one
  above it) and a text alternative, which is what finally made
  `REPORTS_PAGE_REVIEW.md` §4.9's "charts with no accessible alternative"
  fixable: canvas could not carry one.
- **Promotes rule:** R-073.

### ADR-071 — Planned demand is a sibling of the pantry belief, not an input to it (promotes R-074)
- **Context:** the owner asked whether the belief engine counted how many planned
  meals a stock item appears in, noting it *"would be a good indicator if a stock
  item is out or low"*, and described the batch-cooking variant: *"3 planned fried
  rice in the coming week(s) and 2 have been allocated a meal"*. The literal
  reading is a new term in `compute_belief`.
- **Options:** (a) add a planned-meals term to the belief's `progress` — one
  number, one chip, no new surface; (b) a separate signal computed beside the
  belief and rendered next to it; (c) compute it in the client from the plan the
  planner page already holds.
- **Decision: (b).** (a) corrupts a well-specified estimator: belief answers
  *what is on the shelf*, and a plan is evidence about the future, so the two are
  not commensurable — a fortnight of planned dinners would have read as an emptier
  cupboard. (c) fails R-003 twice over: the allocation rule and the urgency
  grading would both live in TypeScript, and neither the stock pages nor the
  shopping list holds a plan. So: `features/stock_items/planned_demand.py` +
  `GET /stock-items/planned-demand`, shaped like the beliefs endpoint, cached by
  a composable shaped like `usePantryBeliefs`, rendered as a third card in the
  same column as `PantryBeliefCard` and `BuyVerdictCard`.
- **Two things it shares rather than duplicates.** The cooked-batch allocation is
  the *same* pool-and-queue walk the shortfall report needs, so it moved into
  `meal_plans/planned_meals.py` and `get_shortfall.py` was rewritten onto it —
  deleting a raw-SQL second copy of the rule. And the urgency grading (**Out
  outranks Low**, the owner's *"Out would be higher confidence than low"*) is
  computed server-side rather than left as `level + count` arithmetic for each
  caller to redo.
- **Consequences:** two overlay fetches on the stock surfaces rather than one —
  accepted, both are cached module-level and shared across the overview and the
  detail page. The card is on the stock-item detail page only, following D-10's
  precedent that a derived signal belongs on *"the surfaces the user opens to
  ask"* rather than on the overview row; the shopping list is the other such
  surface and is [[FU-849]]. Coverage is all-or-nothing per entry, so a 4-serving
  meal against a 3-serving pool still counts as demand — deliberately
  conservative, because the alternative goes quiet exactly when a batch is nearly
  out.
- **Promotes rule:** R-074.

### ADR-072 — Style fixes are verified by measurement, not by review (promotes R-075)
- **Context:** the owner asked for Previous / Repeat / Next to share one row on a
  phone. The first attempt was pure CSS: flex the three buttons from a zero basis
  and step the type down inside `@media (max-width: 599px)`. It looked right in
  the diff and the row did collapse to one line — but driving it and reading
  `getComputedStyle` showed the buttons still at **20px**: the single-line win had
  come entirely from `flex-wrap: nowrap` on `.q-btn__content`, and the `font-size`
  rule had never applied at all, because Quasar's `size="lg"` writes font-size as
  an **inline style**. The labels were fitting by ~0px of margin and crowding
  "Next" at 375px.
- **Options:** (a) `!important` on the media-query rule; (b) drop `size="lg"` and
  reproduce the desktop scale in CSS; (c) make the size prop responsive.
- **Decision: (c)** — `:size="navButtonSize"`, `'md'` below the phone breakpoint
  and `'lg'` above it, off the same `$q.screen.lt.sm` computed the Sous Chef
  button already uses. (a) starts a specificity fight with a framework component
  the codebase has deliberately avoided elsewhere; (b) copies a scale Quasar
  already owns, which is R-004's whole complaint. The inert rule was deleted
  rather than left in place — dead CSS carrying a comment that explains a reason
  that isn't real is worse than no comment.
- **The measurement also deleted a rule that was only needed because of the bug.**
  A `@media (max-width: 359px)` block hid the button icons, added after 320px
  showed "Repeat" painting over "Next". At the corrected 14px that overflow is
  gone — content is 74.7px inside a 90.7px button — so the special case went with
  it. A workaround built on top of an un-measured fix outlives the fix.
- **Consequences:** verification of a visual change now means reading numbers out
  of the running app, not just capturing a screenshot: a screenshot at 375px would
  have passed this, and did. Costs one extra `page.evaluate` per layout claim.
- **Promotes rule:** R-075.

### ADR-073 — Unpriceable is a result, not a number to invent (promotes R-076)
- **Date / task:** 2026-09-03 (owner feedback batch — recipe view item 13)
- **Status:** accepted
- **Context:** The owner asked how "3 yolks" of an ingredient shown at $7.86/kg
  came to **$16.50**. The arithmetic was sound and the premise was not: a counted
  ingredient is multiplied by `UnitPrice.pack_amount`, which the offer path set to
  the shelf price for *every* product regardless of how it is sized. So a 700 g
  carton of eggs was modelled as one countable egg, and three of them cost three
  cartons. The price-observation path twenty lines above had already reached the
  opposite conclusion for the same question — it only sets a per-item price when
  the observed unit is a count — so the codebase held both answers at once.
- **Decision:** One helper, `_item_price`, owns "what does one of these cost?" and
  is allowed to answer **no**. It reads `pack_count` first, then a sizeless
  product, then a count-dimension size (dividing by the unit's own factor, so a
  `dozen` is twelve); a pack measured in mass or volume with no recorded count is
  `None`, and the ingredient is reported `unit_mismatch` rather than billed. Both
  price paths use it. Separately, the seeds now record `pack_count = 12` on the
  eggs product, so the owner's case resolves to a *correct* $0.46 an egg rather
  than merely to a gap.
- **Consequences:** Coverage narrows where the data is thin: "2 tins" of a product
  sized `400 g` with no `pack_count` is now unpriced where it used to (correctly,
  by luck) bill two packs. That is the deliberate trade — the same data shape
  cannot distinguish a tin from a carton, and the visible failure is the safer
  one. It also creates a real follow-up: `pack_count` is not on
  `CreateProductRequest`, so there is currently no way to record the fact that
  restores that coverage through the API (**FU-856**).
- **Promotes rule:** R-076.

### ADR-074 — "Not supported in this browser" is a diagnosis, and it has to be earned (promotes R-077)
- **Date / task:** 2026-09-03 (owner feedback batch — settings)
- **Status:** accepted
- **Context:** The owner reported that About → *Install as an app* "always says
  unavailable even in chrome, when testing on mobile with docker install on
  server". The page rendered that line from a single `v-else`: no deferred
  `beforeinstallprompt` event, therefore "this browser can't". But that event is
  gated on a **secure context**, and a Docker install reached at
  `http://192.168.x.x:8080` is not one — so the check had never asked anything
  about the browser, and its advice ("try Chrome on Android, Edge on Windows")
  pointed at browsers that would do exactly the same thing. This is the third
  capability message in the app to blame the browser for something else; the two
  Voice ones were corrected the same way on 2026-08-27/29 without the lesson
  being written down, which is why it recurred.
- **Decision:** `installUnavailableReason()` sits beside the PWA lifecycle hooks
  and returns `'insecure-context' | 'browser'`; `PwaInstallPrompt` branches on it,
  and the insecure-context copy names HTTPS and a reverse proxy as the fix. The
  generalised rule is R-077 — an unavailable-capability message names the
  condition the code actually tested.
- **Consequences:** One more branch per capability message, and a helper to keep
  in step with the browser's own install-eligibility rules (a manifest or
  service-worker problem still lands in `'browser'`, which is honest but coarse).
  The payoff is that the self-host story stops looking broken: the single most
  likely reason a self-hosted Dora can't be installed is now stated, with the fix,
  instead of being misattributed to the user's browser choice.
- **Promotes rule:** R-077.

### ADR-075 — A dialog is not a viewport; responsive components take the space they are given (promotes R-078)
- **Date / task:** 2026-09-03 (meal-planner owner batch, ~35 items — FU-852)
- **Status:** accepted
- **Context:** the meal-plan builder's review row overlapped its own controls on
  a 1280px desktop while looking correct on a 375px phone. The row stacked under
  `@media (max-width: 599px)` but lives in a `min(640px, 94vw)` dialog, so the
  query never fired on desktop and a ~400px control cluster fought a long recipe
  name for a ~560px line. The owner had already reasoned his way to the cause
  from the outside: *"seems better on mobile (no overlapping), so it seems an
  edit to make it better on mobile stuffed up desktop."* The same confusion had
  produced `RecipeRow`'s unusable-in-a-rail `compact`, and the recipe picker's
  `max-height: 65vh` inside an already-sized pane. Three instances, one cause,
  no rule.
- **Decision:** components that can be hosted in a constrained container do not
  read the viewport. Where the two shapes differ only by available width, pick
  the shape that works at every width and drop the branch entirely — the review
  row is now stacked unconditionally, and the `@media (max-width: 599px)` block
  that remains covers only genuinely device-level concerns (scroll regions,
  full-width action buttons). Where a real mode difference exists, the host
  passes it as a prop.
- **Consequences:** one more thing to check in review ("can this be narrow while
  the window is wide?"), and a small cost in density — the stacked row is taller
  than a working single-line row would have been at 1280px. That is the right
  trade: a layout that is correct everywhere beats one that is tighter at one
  width and broken at another. It also removes the temptation to "fix" a
  component by adding a second, disagreeing breakpoint. Container queries are
  now the sanctioned instrument where a genuine width branch is unavoidable;
  none was needed here. Related: R-075 (measure the running app) is how all
  three instances were actually found.
- **Promotes rule:** R-078.

### ADR-076 — Precision is part of formatting, not the caller's job (promotes R-079)
- **Date / task:** 2026-09-03 (meal-planner owner batch, ~35 items)
- **Status:** accepted
- **Context:** the planner's right rail rendered *"needs 31.333333333333332
  tbsp"*. `formatQuantity` was the app's single authority for the number/unit
  spacing convention (DEC-3) but stringified the number as-is, so the decision
  about precision had quietly devolved to every call site. The auto builder had
  grown its own `function round(n)`; the rail had nothing; the two rendered the
  same aggregate differently.
- **Decision:** rounding moves into `formatQuantity` (two decimals, trailing
  zeros stripped, non-finite input renders as nothing), and the builder's local
  rounder is deleted. Pinned by unit tests covering the float artefacts and the
  fractions that must survive.
- **Consequences:** commits us to one precision for every quantity Dora writes;
  a surface that genuinely needs more digits must extend the formatter (an
  argument), not bypass it. Pre-formatted fraction strings from `scaleQuantity`
  ("1½") still pass through untouched, so the two formatters compose as before.
  This is R-003 applied to presentation: it says the shared formatter owns the
  *whole* convention, not the half that happened to be extracted first.
- **Promotes rule:** R-079.

### ADR-077 — A vendor's variable is the seam; sync it, don't out-specify it (promotes R-080)
- **Date / task:** 2026-09-03 (owner misc batch — theme neutrality + the invisible menu bar; resolves FU-709)
- **Status:** accepted
- **Context:** every dark theme's authored `--surface-page` had never painted.
  `app.scss` styles `body` from `--q-page`; Quasar styles `body.body--dark` from
  `--q-dark-page`, a variable nothing in Dora set. The class selector wins, so all
  seven dark variants rendered Quasar's `$dark-page` (#14171a) and their authored
  page colours were dead code. It surfaced only sideways — a sticky header that
  *did* read `--surface-page` looked like a deliberate dark-green band — and was
  parked as FU-709 because honouring the colours changes the whole app in dark
  mode: an owner-visible design call, not a bug fix to slip in. The owner made the
  call in this batch: *"Did we stop colouring everything in the app like the
  background? Could adjust the background with each theme to have a tint of the
  main colour of that theme."*
- **Decision:** `themeService.syncQuasarPaletteFromCssVars` now also sets
  `--q-dark-page` from `--surface-page`, so the dark page paints the theme's own
  colour and one token feeds both modes. Generalised as R-080: where a framework
  paints from a variable it owns, sync that variable from our semantic token in the
  existing bridge — never fight its selector. The workaround the old behaviour
  spawned (`StockOverview`'s `body.body--dark` peek-header fork) was deleted in the
  same change.
- **Consequences:** commits us to checking, for any framework-owned paint, whether
  the framework has a variable we should be feeding — and to verifying a new token
  actually paints in the running app rather than trusting that it is declared.
  Costs us the freedom to let Quasar's defaults quietly stand in for our tokens;
  every dark theme's page colour is now a real design decision that has to hold up
  against card and row contrast, which is the honest position. Two themes needed
  work the moment the colours became visible (Lemon Tart Dark's page hue and its
  toolbar), which is the evidence the tokens were never being reviewed.
- **Promotes rule:** R-080.
### ADR-078 — The Features page is dissolved; a switch goes where its effect is (promotes R-081)
- **Date / task:** 2026-09-03 (owner feedback batch — admin settings)
- **Status:** accepted
- **Context:** The owner read the admin area end to end and said the organisation
  felt *"really weird/unintuitive"*: Users was a group of one above everything,
  Features sat under Install holding four unrelated switches, Messaging split
  Email/Push/Voice off from the install they belong to, and Hosting was two
  settings with nothing in common. Of the four Features switches, one
  (`meal_planning_enabled`) gated nothing at all — see R-081 — and the owner's own
  instinct ("I feel like this was added accidentally") was right.
- **Decision:** the Features page and the Hosting page are both dissolved, and the
  admin nav collapses from five groups to three (Install · Kitchen features ·
  Data & access), with Users leading Install. Every surviving switch moved to the
  surface it governs: scanning → Stock, money → a new Money page under Kitchen
  features, companion ingestion → renamed **Product data ingestion** under Data &
  access with the product-search URL beside it, the weekly deals email → the
  Email page (where its independence from `email_enabled` is finally visible),
  audit retention → the Audit log it prunes, the public URL → Email, where the
  links it builds are sent from. `meal_planning_enabled` is gone entirely
  (migration `a7c3e5d19f2b`). Retired routes redirect rather than 404.
- **Consequences:** More pages, each smaller, and two of them (Money, Product data
  ingestion) hold a single row — deliberately, because a one-row page you can
  find beats a four-row page you can't parse. Deep links to
  `admin/system/features` and `admin/system/hosting` still resolve. The cost is
  that "where is the install switch for X?" is now answered by knowing what X is,
  rather than by one page that lists everything; the nav's three groups carry
  that.
- **Promotes rule:** R-081.
### ADR-079 — Explicit level resolution beats an eager include (promotes R-082)
- **Date / task:** 2026-09-04 (owner feedback batch — dashboard)
- **Status:** accepted
- **Context:** Kitchen health gained a `plan_coverage` component: of the meals
  planned for the next 7 days, how many the pantry can cook. It read the shared
  `load_recipe_cookability` map, which is the same authority the dashboard
  summary's per-entry `missing_count` uses — the correct, R-003 choice. It
  nevertheless returned 0 cookable out of 6, on a dataset where the summary
  endpoint simultaneously reported 5 of those 6 as `missing_count: 0`. Same
  request, same session, same map, opposite answers. The cause was position:
  `_gather_inputs` computes freshness with `get(StockItem).all()`, and the
  cookability map was being built *after* that, so its eager
  `StockItem → StockLevel` include hit an identity map already holding those
  rows with `stock_level` unloaded.
- **Decision:** treat "did an eager include actually populate this noload
  relationship?" as an unanswerable question at the call site, and resolve such
  relationships explicitly. The immediate fix hoists the cookability load to the
  top of `_gather_inputs` with a comment stating the constraint; the durable fix
  — making `load_recipe_cookability` order-independent via `_level_access` — is
  [[FU-872]], because it changes a rule four recipe surfaces read and wants its
  own unit.
- **Consequences:** one more ordering constraint recorded in a comment, which is
  a fix a reordering edit can undo — hence the rule and the FU rather than
  calling the hoist done. On the other side: the third occurrence of this trap
  is now written down as a *class* rather than a third one-off, and
  `_level_access.py`'s existence finally has a rule pointing at it.
- **Rule promoted:** R-082.

### ADR-080 — A per-entry exemption is neutralised in both directions (promotes R-083)
- **Date / task:** 2026-09-04 (carried from the fresh-cooking unit of the same day)
- **Status:** accepted
- **Context:** `batch_features_enabled` was install-wide and binary, so a
  household that batch-cooks had no way to say "this one meal is cooked on the
  day". `MealPlanEntry.cook_fresh` (migration `b8d2f4a6c091`) is that exception.
  The naive implementation — skip fresh entries when computing the shortfall —
  is half a feature: the entry would still be *drained* from the cooked pool by
  the reconcile sweep when its day passed, silently consuming a portion the
  household still had frozen.
- **Decision:** an exemption is specified as a pair of neutralities, not a
  filter. `cook_fresh` stands outside the pool in both directions: it is never
  covered by the pool and never spends from it. Stated once per resolution point
  (`allocate_pool`, `recipe_shortfalls`, `reconcile_consumed_meals`, and
  `reconcile.py`'s verbs via `current_drained = target_drained = 0`) rather than
  teaching both drain helpers the flag, and made mutually exclusive with a cook
  batch — a batch *is* the pool — on both write paths.
- **Consequences:** more places to touch when the pool model changes, and a
  mutual-exclusion rule the client has to mirror (the toggle hides on a linked
  meal; `setCookDays` strips `cook_fresh` when reusing a fresh entry). Accepted:
  the alternative loses food.
- **Rule promoted:** R-083.

### ADR-081 — The blanking loader is the navigation path, and only that (promotes R-084)
- **Date / task:** 2026-09-04 (owner feedback: the shopping list flashes on every
  item removal)
- **Status:** accepted
- **Context:** `ShoppingListDetail.load()` nulls `detail` before re-fetching so a
  *navigation* between lists shows a skeleton rather than the previous list's
  rows. Every mutation handler on the page reused it, so editing the list you
  were already looking at flashed the entire page through the skeleton. The
  2026-08-29 shop-date report produced the right fix — `refreshDetailQuietly()` /
  `refreshAllQuietly()` — but wired it only to the list-level edits, leaving the
  line-level ones (the far more frequent action) on the blanking path.
- **Decision:** classify the refresh by what changed, not by how much. The
  blanking loader is reserved for navigation; every in-place edit goes through the
  quiet pair. Applied here to `onRemoveLine`, `onAddSuggestion`, `onClearAll`,
  `addLineBackToActive` and `applyTrim`. The remaining `load()` calls are either
  the route watcher or paths where the page's identity really does change.
- **Consequences:** a quiet refresh doesn't re-prime the shared buy-verdict cache
  (`primeVerdicts` runs only in `load()`), so a line added by the suggestions
  strip fetches its own verdict rather than riding the list's batched one — one
  extra request, versus re-priming the whole list and flashing every badge back
  through its spinner. Accepted.
- **Rule promoted:** R-084.


### ADR-082 — Touch sizing is a pointer question, not a width question (promotes R-085)
- **Date / task:** 2026-09-05 (owner feedback: *"on mobile the dropdown options
  are a bit narrow for the stock level picker. Good for desktop, bit
  thicker/bigger for mobile would be better"* + *"the row buttons need to be
  slightly bigger on mobile"*, flagged by the owner as *"could be a more
  widespread UX issue"* — it was)
- **Status:** accepted
- **Context:** D-004 (44×44 tap targets) and B8 (44px menu rows) had been
  violated app-wide since the beginning: `BaseButton` ran every variant at 36px,
  38 `q-list dense` menus across 26 files ran 32px rows, and the stock and
  recipe rows shrank their icon buttons to 30px to win back width. Two
  follow-ups — **FU-678** and **FU-641** — had diagnosed this correctly in
  August and both deferred it for the same stated reason: raising the floor
  "re-flows every toolbar, table row and card action in the app". That reasoning
  was sound but rested on an unexamined assumption, that the fix had to apply
  everywhere.
- **Decision:** scope touch affordances to the pointer. D-004's own text is
  "on any surface a finger uses" and B1 grants 36px explicitly for
  "desktop-dense chrome", so the rule was never app-wide to begin with — it was
  device-wide, and the codebase had no way to say that. Under
  `@media (pointer: coarse)` the floor lifts in `BaseButton` (all variants) and
  in `app.scss` (`.q-menu .q-item`, plus the horizontal padding `dense` also
  strips), which fixes the 38 menus and every `.dora-btn` in one place rather
  than 60+ edits (R-001). Call sites that pin their own size at higher
  specificity — `StockItemRow`, `RecipeRow` — were swept individually, since a
  global rule cannot reach them.
- **Consequences:**
  - Desktop is provably unchanged, which is what made this shippable and is also
    exactly what the owner asked for. Measured under Playwright in both
    contexts: touch 44/44/260×44, mouse 32/36/200×32.
  - `StockLevelPicker` is the one control whose *visual weight* changes, not
    just its hit area — it is a colour chip, so a bigger target is a bigger
    block. It could not use the invisible-hit-area trick because `::after`
    carries the uncertainty ring and Quasar's QBtn owns `::before`. Flagged for
    the owner's eye in `DORA_VERIFY.md` rather than assumed.
  - Rows pay ~42px of width for three 44px buttons; the row gap tightened 8→6px
    and the name (which already truncates) absorbs the rest. A clipped word is
    recoverable by tapping the row; a missed target isn't.
  - Controls that are neither menus nor icon buttons and sit at 38–40px
    (`DoraTabs`, `BaseSelect`, `SortControl`, `DoraSegmented`) were **not**
    swept — each is a deliberate documented size and wants an eye on the result.
    Logged as FU-877 rather than changed blind.
- **Rule promoted:** R-085. **Resolves:** FU-678, FU-641.


### ADR-083 — Rendering identity is not database identity (promotes R-086)
- **Date / task:** 2026-09-05 (owner meal-planner batch — *"tapping increase or
  decrease servings on mobile once hides the dropdown for a meal slot"*)
- **Status:** accepted
- **Context:** the planner's servings stepper lives inside the entry menu, and
  every tap saves the week. `update_meal_plan.py` replaces the whole forward
  portion of a plan on each save — it deletes the future entries and inserts new
  rows — so the ids the client had just rendered were gone by the time the
  refresh landed. Vue saw a list of entirely new keys and remounted every card,
  taking the open menu with it. The same trap sits under the desktop chip; the
  owner met it on mobile first because a phone makes you tap more.
- **Decision:** key those lists on `scheduled_for | slot | recipe_id` (plus an
  occurrence suffix for a genuine duplicate), in one shared helper both call
  sites import, with the reasoning written at the helper rather than at the
  call sites.
- **Alternatives considered:**
  - *Make the endpoint preserve entry ids.* The honest fix, and rejected for
    this batch on risk: the replace-the-forward-week shape is load-bearing for
    the cook-batch rebuild (which deletes and re-attaches batches around
    preserved past entries, and carries its own 2026-09-03 defect history).
    Changing it to match-and-update is a real refactor with a blast radius
    across reconcile, batches and the past-entry guard — worth doing on its own
    terms, not as a side effect of a UI fix. Logged as FU-878.
  - *Move the stepper out of the menu.* Fixes the symptom for one control and
    leaves the trap armed for the next thing put inside a row.
- **Rule promoted:** R-086.


### ADR-084 — External clients get an authenticated door onto the same handler (promotes R-087)
- **Date / task:** 2026-09-06 (products program, batches B–D)
- **Status:** accepted
- **Context:** The standalone companion has to reach capabilities Dora's own SPA
  reaches, but it cannot present a `dora_session` cookie — it authenticates as an
  `IngestionSource` with a bearer key (products program PF-9). Three of these
  arrived in one day: reading which products Dora already holds
  (`ingest_link_status`, 2026-07-12), deleting a product the user unsaved
  (`ingest_delete_product`), and listing the saved products to refresh
  (`ingest_list_products`). Batch C is where the tension became explicit: the
  program's own rule PF-4 said unsave must use "the same **endpoint**" as the
  SPA, which is impossible across two auth schemes. The rule's intent was right
  and its wording wasn't.
- **Decision:** one *behaviour*, N authenticated front doors. The behaviour lives
  in an auth-ignorant handler; each route does auth + parsing + logging and
  delegates. Bearer routes sit on `INGEST_ROUTER` and are listed in
  `middleware.PUBLIC_ENDPOINTS` — which exempts them from the session gate, not
  from authentication. Responses stay source-agnostic per R-005. PF-4 reworded to
  "same behaviour".
- **Alternatives considered:**
  - *Let the companion hold a user session.* Rejected: it would make the
    companion a privileged insider rather than an ordinary external client,
    contradicting PF-9, and would hand a scraper a human's credentials.
  - *Duplicate the logic behind the bearer route.* Rejected on the concrete
    risk, not on principle: product delete's cascade decides the fate of
    finished shopping lists, price alerts and barcodes. Two copies drift, and
    this drift is silent loss of somebody's purchase history.
  - *Wait for a fourth instance before promoting.* Considered — the first two
    instances were deliberately left unpromoted. Three is enough to see the
    shape (read / write / list all take it), and D was about to add a fourth
    without the rule written down.
- **Consequences:** a small amount of route boilerplate per capability, in
  exchange for the guarantee that the SPA and any external client can never
  diverge in behaviour. The pattern also gives a natural home for future
  non-session callers (a CLI, a second companion) without re-litigating auth.
- **Rule promoted:** R-087.


### ADR-085 — App-wide component defaults live in a wrapper, not at the call site or in a monkey-patch (promotes R-088)
- **Date / task:** 2026-09-09 (owner feedback: *"I don't like how everywhere
  through the app you immediately see the tooltip on mobile for all UI elements
  when interacting with them. There should be a delay. Otherwise you see
  tooltips flashing as you use the app."*)
- **Status:** accepted
- **Context:** QTooltip defaults `delay` to 0, and on mobile it binds show to
  `touchstart` and hide to `touchend`/`click`. Every tap on every icon button in
  the app therefore flashed its tooltip up and straight back down. D-005 requires
  a tooltip on every icon-only control, so this was not a few bad call sites — it
  was 313 tooltips across 81 files, of which exactly two (`PreferencesSettings`,
  `DoraModeSlider`) had ever set a delay, each a local patch of the same global
  problem. Quasar's `framework.config` has no QTooltip entry, so there is no
  supported one-line global.
- **Decision:** add `BaseTooltip` — a wrapper declaring `delay` (500ms) and
  `hideDelay`, passing all other attrs through — and sweep every call site onto
  it, deleting the two ad-hoc overrides. 500ms is one number for both pointers:
  on touch the show timer is cleared by `touchend` before it fires, so a tap is
  silent and a deliberate long-press still surfaces the label; on mouse it is a
  conventional hover dwell. That avoids a `pointer: coarse` split (R-085 would
  have permitted one, but two numbers to keep in sync buys nothing here).
- **Alternatives considered:**
  - *Set `:delay` at each call site.* Rejected — that is the state that produced
    the bug, and it degrades the moment someone adds tooltip 314.
  - *Patch `QTooltip.props.delay.default` in a boot file.* Rejected. One line and
    zero churn, but it makes `<q-tooltip>` silently disobey its own docs with
    nothing in the template to hint at it — exactly the invisible-action-at-a-
    distance R-019 rules out. The 81-file sweep is mechanical and reviewable;
    the magic is neither.
- **Consequences:**
  - A large but purely mechanical diff (tag rename + one import per file).
    `vue-tsc`, `eslint`, `quasar build` and 720 vitest specs all green; the
    existing specs that assert tooltip text through a `QTooltip` stub
    (`doraModeSlider`, `alertRow`, `recipeRatingChip`, `addToListButton`) pass
    unchanged, which is the runtime evidence that the wrapper resolves and
    forwards its slot correctly inside real component trees.
  - `.q-tooltip` styling in `app.scss` is untouched — the wrapper still renders a
    real QTooltip.
  - The 500ms value is a first guess at the feel and is the one thing here that
    wants the owner's eye on a real phone. Logged in `DORA_VERIFY.md`.
- **Rule promoted:** R-088.

### ADR-086 — A convention the client must apply live is generated, not retyped (promotes R-089)
- **Date / task:** 2026-09-13 (owner feedback: *"Log price and possibly other
  areas I can't recall — shouldn't be displaying in such low amounts e.g.
  '≈ $0.01 per g'. Stores always show per 100g, or per 100ml. Ensure we match
  logical displays of pricing and units compared to real store websites."*)
- **Status:** accepted
- **Context:** the convention the owner is describing already existed and was
  already correct: `units.display_denominator_for` quotes per 100g/100ml below a
  full kilo or litre and per kg/L at or above it, switching to lb/oz and qt/fl oz
  on a US install. Four server-rendered surfaces read it (the YourPrices widget,
  the price chart axis, the offers sidecar, reports). The two surfaces the owner
  was looking at did not, and they could not: `PriceEntry.vue` previews a per-unit
  price *while you type*, and `RecipeCostDialog.vue` renders a price the cost DTO
  ships in the linked product's own raw `size_unit`. Both had grown a private
  answer instead — the entry widget divided straight through and printed
  "$0.01 per g"; the cost dialog flipped to /kg below a $0.05 threshold of its
  own, so the same product could read "/kg" in one place and "/100g" in another,
  and neither followed the measurement system.
- **Decision:** restructure the Python rule into a data table
  (`PRICE_DISPLAY_RULES`, keyed convention × dimension, each row a full/sub
  denominator pair plus the pack size at which the full one takes over) with the
  existing function as a thin read over it; emit that table, `CANONICAL_PRICE_UNIT`
  and the system→convention map into `units_table.ts` from `scripts/dump_units.py`;
  add `helpers/unitPriceDisplay.ts` as a reader; point both surfaces at it and
  delete the two private rules. Behaviour of `display_denominator_for` is byte-for-
  byte unchanged — verified across both conventions, both dimensions and the flip
  boundaries before and after.
- **Alternatives considered:**
  - *Hand-write the convention in TypeScript.* Rejected — R-003 drift by
    construction, and the two rules being replaced are the evidence for what that
    costs.
  - *Add display fields to the recipe cost DTO and fix the dialog server-side.*
    Genuinely correct for that one surface, and tempting because `unit_price` is
    load-bearing for the cost math so it would have needed new fields rather than
    a changed meaning. Rejected because it does nothing for the price-entry
    preview — which is the surface the owner actually named — so the client would
    still have needed the rule, and we'd have paid for both.
  - *Round-trip the preview to the server on each keystroke.* Rejected; a
    debounced network call to render a number we already have every input for.
- **Consequences:**
  - One convention, two languages, one source. A US install now gets /lb and /oz
    in the entry preview and the cost breakdown, which it never did.
  - The recipe cost dialog's numbers move: "$0.00 / g" spaghetti became
    "$0.30 / 100g", and lines already quoted per kg / L / ea are untouched.
    Confirmed against 27 real cost lines in the dense seed.
  - `scripts/dump_units.py` gains an emitter; `units_table.ts` is regenerated and
    stays checked in. Any later change to the convention is a Python edit plus a
    re-run, and a stale mirror shows up as a diff.
- **Rule promoted:** R-089.


### ADR-087 — Reserved grid tracks are derived from their contents (promotes R-090)
- **Date / task:** 2026-09-17 (owner feedback on the shopping list: *"UI elements
  overlapping terribly on mobile"*, *"in draft mode on mobile, price is on top of
  the reorder controls"*, *"buttons looking too small for the elements around
  them ... something is up"*)
- **Status:** accepted
- **Context:** three separate symptoms turned out to be one cause. The plan row's
  action cell was `--sl-act-w: 104px`, holding three 36px icon buttons and two 4px
  gaps: 116px. Measured on the seed at 1440px, the *Move up* arrow sat at x=968
  against a cell starting at x=980 — already 12px outside its column, printing on
  the money, and invisible only because the reveal-on-approach rule keeps those
  buttons at `opacity: 0` until hover. A phone has no hover and `BaseButton` gives
  it the D-004 44px floor, which takes the same cell to 140px in a 76px track. The
  owner was seeing the honest version of a bug the desktop was hiding.
  The third symptom — "buttons too small for the rows" — was the same arithmetic
  read from the other end: the rows were tall because the cells inside them were
  being pinned to the tallest spanning item by a `grid-row: 1 / -1` that silently
  collapses to one row when a grid declares no `grid-template-rows`.
- **Decision:** widths that hold controls are computed from the control's own size
  token, and spanning uses `span N` rather than a negative line on an implicit
  axis. Promoted to R-090 rather than fixed in place, because the same shape is
  latent anywhere a row reserves an icon gutter and a media query resizes icons —
  which, since the tap-target sweep, is every list row in the app.
- **Consequences:** the plan row's action track is now
  `calc(var(--sl-act-btn) * 3 + var(--space-1) * 2)` with `--sl-act-btn` redefined
  under `pointer: coarse`, so the D-004 floor and the layout can no longer
  disagree. A sweep of the other `/ -1` uses found six, all on the *column* axis
  of grids that declare `grid-template-columns` — where negative lines are
  well-defined — so no further changes were needed. The plan row also lost its
  `.sl-row__main` wrapper: a single cell holding three stacked children cannot
  hand any of them to a different column, which is why the phone layout could not
  be fixed by resizing tracks alone.


### ADR-088 — The animated box is bare; padding lives inside it (promotes R-091)
- **Date / task:** 2026-09-17 (owner: *"This dropdown card has the same issue
  most dropdowns have had in this app. There's a snap at the end which looks
  ugly and not smooth (when collapsing). This keeps recurring."*)
- **Status:** accepted
- **Context:** measured rather than guessed, because "feels snappy" is exactly
  the kind of report that gets fixed by changing an easing curve and staying
  broken. Sampling the overview card's collapse frame by frame showed a clean
  ease from 199px down to 29px and then a single-frame drop to zero. 29px is the
  body's own `padding: 12px/16px` plus its 1px top border — `q-slide-transition`
  animates `height`, and `height` cannot go below the padding box, so the last
  29px were never animated at all; they vanished when `v-show` set
  `display: none`. Every disclosure whose caller had padded the body had the
  same defect, which is why the owner kept meeting it.
- **Decision:** the animated element owns nothing with a size. `CollapsibleCard`
  gained `.collapsible-card__inner`, pinned its `__body` to `padding: 0; border:
  none`, and its one padding-applying caller moved its rule inward. Promoted to
  R-091 rather than fixed locally: the trap is invisible in review, it recurs
  per caller rather than per component, and the shared component is the only
  place that can make it unreachable.
- **Consequences:** the same collapse now eases 199 → 165 → … → 3 → 2 → 1 → 0
  with no terminal jump. Callers that need a border on the disclosure edge (the
  overview card does) put it on the inner element, which also means the border
  fades with the content instead of surviving until the last frame.


### ADR-089 — A per-row "why is this here" label is only worth storing when the user didn't cause it (promotes R-092)
- **Date / task:** 2026-09-19 (owner, on seeing the shopping-list row: *"we don't
  care for the source. that whole source thing needs to die. the only one i think
  we care about is the manual vs auto-add from stock level change"*)
- **Status:** accepted
- **Context:** `ShoppingListLine.added_via` carried seven values — `manual` plus
  six naming which auto-generate source produced the line — and the row rendered
  each as a caption ("auto: low stock", "auto: recipe"). Two machines wrote them:
  the `/auto-generate` endpoint, which runs because the user ticked sources in the
  New list dialog, and the low-stock hook in `update_stock_item`, which fires on
  its own. Both wrote `auto_low_stock`, so the field could not distinguish them.
  On a generated list most rows carried a caption, each restating a choice the
  user had made seconds earlier; two of the six values (`auto_recipe`,
  `auto_meal_plan`) were unreachable from the UI entirely, and two more
  (`auto_essential`, `auto_flagged`) were the same `is_essential` predicate under
  two names.
- **Decision:** keep the distinction the user cannot already see — "no action of
  mine put this here" — and delete the rest. `added_via` becomes
  `is_auto_added: bool`, written in exactly one place. The UI renders one mark
  (Dora's burger) on those lines and nothing on any other. The dedupe priority
  ladder that existed solely to arbitrate which caption won goes with it.
- **Alternatives considered:**
  - *Keep the enum with one auto value.* Rejected by the owner as keeping a shape
    for its own sake. A two-state field is a boolean.
  - *Keep per-source captions but reword them.* Rejected — the wording was never
    the problem; the problem is that a generated list is mostly auto rows, so the
    caption is noise at exactly the moment it is most frequent.
  - *Keep `auto_recipe`/`auto_meal_plan` and render the recipe name.* Genuinely
    the most useful label of the six, and considered at length — but no UI path
    sets those sources (the dialog pre-seeds via `bulkAddToList`, which writes
    `manual`), and the `detail` field carrying the name was never persisted. It
    would have meant building a feature, not preserving one.
- **Consequences:** three `trim_to_budget` tiers lost their input and were moved
  onto live signals, which is the general lesson promoted as R-092 — and which
  broadened tier 5 to catch hand-added lines for far-off meals that it had been
  silently excluding. The stock-item history timeline drops its provenance prefix
  and reads "Added to <list>"; nothing is lost, since the two informative values
  were never written. Historical rows collapse to `False` in migration
  `a1c7e4b9d2f6`: the ambiguity between the two writers is not recoverable, and
  pre-release a wrong mark is worse than an absent one.

### ADR-090 — Alerts are episodes: keyed by what started them, discarded by age (promotes R-093)
- **Date / task:** 2026-10-15 (owner: *"there should be well defined points when
  alerts will appear and not appear so we don't have hundreds of alerts
  constantly churning"*, alongside "discard alerts older than X days")
- **Status:** accepted
- **Context:** alerts are derived on every read and never stored; only the user's
  decisions are, keyed by a stable string. The keys named the subject and kind
  only, so a decision outlived the occurrence it was made about. There was no
  notion of an alert's age, so nothing could be discarded by it.
- **Decision:** every key carries its episode (R-093) and every alert reports
  `started_on`. A per-user `alert_discard_after_days` (7 / 14 / 30 / never,
  default 14) drops alerts whose episode began earlier. Read state was removed:
  dismiss is the one way to put an alert away. The missed shop day became its own
  kind (`shopping_overdue`), and the long-unused `PriceAlert` rows now fire as
  `price_drop`, keyed by the offer that crossed the threshold.
- **Alternatives considered:**
  - *Persist alerts as rows with first/last-seen.* Gives true ages, but turns a
    read into a write and needs a sweeper to resolve rows. Every kind already has
    a fact that dates its episode, so the derived model holds.
  - *Clear decisions when the condition drops out.* Works for dismissal, but only
    if something evaluates at the moment it drops out; the push job runs hourly,
    the bell on demand. Keys that differ per episode need no clean-up to be right.
- **Consequences:** interactions recorded against the old keys stop matching
  (pre-release, left in place). Ledger rows for finished episodes accumulate; a
  prune is logged as a follow-up rather than built.

### ADR-091 — Derived tokens resolve per themed subtree (promotes R-094)
- **Date / task:** 2026-10-17 (owner onboarding batch; the font picker on the
  rebuilt welcome step drew a light track on the dark wizard)
- **Status:** accepted
- **Context:** themes are `[data-theme]` blocks, and two surfaces pin a theme
  below `<html>`: WelcomeLayout (always Pesto Dark) and the welcome step's
  theme-preview cards. Base tokens follow; derived ones (`--seg-*`,
  `--lifecycle-cleared`, `--neutral-muted`) did not.
- **Decision:** re-declare derived tokens in a `[data-theme]` block in
  `tokens.scss` (R-094).
- **Alternatives considered:** move every `:root` declaration to
  `:root, [data-theme]`. That reorders the cascade so the defaults would beat
  `themes.scss` blocks of equal specificity; rejected.
- **Consequences:** a new derived token has to be added in two places; R-094
  names the signal.

### ADR-092: The production deploy holds real data; migrations preserve it (promotes R-095)
- **Date / task:** 2026-10-21 (owner: the household starts using the app)
- **Status:** accepted
- **Context:** the deploy script now runs the production profile with the DB
  kept across deploys (`WIPE_DB=false`), so every deploy upgrades a live
  database through Alembic. The standing pre-release posture allowed clean
  non-preserving migrations, and some open follow-ups were planned on that basis.
- **Decision:** end that posture for stored data. Every migration preserves
  existing rows (R-095). The code-level "no compat shims" rule (R-007) stands.
- **Alternatives considered:** keep the posture and reset the household's data
  when a migration needs it. Rejected: it makes the app unusable for real
  tracking, which is the reason to start using it.
- **Consequences:** schema changes cost a backfill each. Open follow-ups that
  plan a non-preserving migration are revisited against R-095 when picked up.

### ADR-093: Shared-component style fixes are variant-scoped (promotes R-096)
- **Date / task:** 2026-10-22 (owner approved FU-794)
- **Status:** accepted
- **Context:** the page-level horizontal scroll fixed in the 2026-08-31
  recipe-view batch came from a `BaseSelect` rule written for one variant and
  applied to all of them. The fix introduced the `base-select--chips` class.
- **Decision:** style rules in shared components are scoped to the variant
  they were written for (R-096). Existing scoped rules stand; no restyle.
- **Alternatives considered:** leave it to review. Rejected: the bug only
  showed on a surface nobody was working on, so review of the change that
  caused it could not have seen it.
- **Consequences:** one extra class per variant-specific fix. No visual change.

### ADR-094: Create and update share one write module (promotes R-097)
- **Date / task:** 2026-10-24 (finalisation Stage 2, chunks 1 and 2)
- **Status:** accepted
- **Context:** two features had duplicated create/update write paths whose
  copies had already drifted; both were consolidated the same way in one day.
- **Decision:** a create/update pair keeps its shared request shape, checks,
  builders, outcome and outcome-to-HTTP mapping in one private module (R-097).
- **Alternatives considered:** a generic write base class. Rejected: the two
  features share the shape, not the logic, and the codebase prefers explicit
  per-feature modules over inheritance machinery (R-019).
- **Consequences:** two small modules exist; other create/update pairs adopt
  it when next touched, not as a sweep.

### ADR-095: One helper makes stored instants aware (promotes R-098)
- **Date / task:** 2026-10-24 (finalisation Stage 2, chunk 5)
- **Status:** accepted
- **Context:** SQLite returns naive datetimes for timezone-aware columns; eight
  modules had their own coercion.
- **Decision:** `persistence/aware.as_utc` is the one coercion (R-098); the
  eight copies were replaced. The Postgres move (FU-045) makes it a no-op, not
  a removal: values stay aware either way.
- **Alternatives considered:** a SQLAlchemy `TypeDecorator` that re-attaches UTC
  on read. Deferred: it changes every timezone-aware column at once and wants
  the Postgres work alongside it.
- **Consequences:** one import per comparing module.

### ADR-096: One read defines "spent" (promotes R-099)
- **Date / task:** 2026-10-27 (finalisation Stage 2, chunk 12)
- **Status:** accepted
- **Context:** seven spend readers had drifted on deferred lines and zero
  quantities, so the budget and Reports could report different totals for one
  window.
- **Decision:** `_line_price.spend_lines` returns the bought lines of a window
  as `SpendLine` rows (paid price on the actual-then-picked ladder, store
  rungs, list price at pick); every windowed spend figure sums it, and
  `lifetime_spend` mirrors its filter in SQL (R-099).
- **Alternatives considered:** one SQL `SUM` per report. Rejected: the store
  ladder and the category lookup need the rows, and seven SQL sums is the
  shape that drifted.
- **Consequences:** a report reads rows and aggregates in Python, which is
  O(lines in the window): fine at household scale, revisit if a report ever
  spans many households (Path A).
