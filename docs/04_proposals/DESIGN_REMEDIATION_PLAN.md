# Design Remediation Plan — actioning the 2026-07-18 UX/design audit

**Status:** 🔵 approved-to-action (owner directive 2026-07-18: "add all this to a
report to be actioned"). Work units below are sized for one agent session each
unless noted. **Sources:** `DORA_FOLLOWUPS.md` FU-578 (54 itemised findings) +
FU-582, and `docs/05_investigations/UX_DESIGN_CRITIQUE_2026-07-18.md` (synthesis).
**Standing rules:** every unit must land compliant with
`docs/01_charter/DESIGN_STYLE_GUIDE.md` (D-rules) — that doc is the contract;
this plan is the backlog that brings existing screens up to it.

**Verification vehicle:** each unit re-runs the relevant `web_app/e2e/drive.mjs`
screenshot plan (session scratchpad plans are the recipes; store new plans under
`web_app/e2e/plans/` as they're recreated) + the existing Vitest/Playwright
suites. Contrast checks use the ratio-probe eval from the audit session.

---

## Wave 1 — token & convention passes (small diffs, app-wide lift)

### DR-1 · Contrast token pass (D-002) — ➗ RAMP DONE 2026-08-12; DR-1b component spots remain
Retune `--text-muted` / `--text-secondary` (light variants especially) and
soft-chip text colours to AA; fix the alerts-badge (3.0:1), "New item" button
(3.6:1), Essential footer stat (2.3:1), BUY badge (2.5:1@11px), and audit the
wordmark treatment (2.8:1). **Files:** `tokens.scss`, `themes.scss` (all 10
variants), `colours.scss`. **Accept:** ratio probe passes D-002 floors on stock
overview, dashboard, shopping list detail in all 5 families × light/dark.
**Refs:** FU-578 #7/43.
**Shipped (the app-wide ramp — the highest-leverage part):** `--text-muted`
retuned across all 10 themes + the `:root` fallback in `tokens.scss` so it clears
**≥4.5:1 on every surface** (worst was Pesto 3.0:1 → 4.62:1; light themes darkened
~10pt L, Lemon-Tart-Dark + Blueberry-Dark lifted 2pt). `--text-secondary` already
passed everywhere (probe-verified) — left unchanged. Verified with a WCAG
contrast probe over every text×surface pair in all 10 themes (all ≥4.5); scss
compiles clean. Hierarchy preserved (muted stays lighter than secondary).
**DR-1b — component spots (diagnosed with a per-theme ratio probe 2026-08-12):**
- **✅ Alerts count badge** (`AlertsBell.vue`): was `color="negative"`, but
  `--semantic-negative` is *lightened* in dark themes so white-on-it hit ~2.96:1.
  **Fixed** — the badge now uses `color-mix(in srgb, var(--semantic-negative) 65%,
  black)`, white stays ≥6.2:1 in all 10 themes (probe-verified).
- **✅ Buy/Wait/Skip verdict badge** (`BuyVerdictBadge.vue`): full-strength
  semantic ink on the pale soft chip failed (WAIT 1.98:1). **Fixed** (owner chose
  neutral ink 2026-08-12) — label now `--text-primary` (AA both modes, 13.6:1);
  coloured border + soft tint + word carry the semantic. The 11px size is a
  separate DR-3/D-003 item, not blocking legibility now.
- **↪ "New item" / primary buttons** (brand-primary × text-on-primary): 3.89
  (Pesto) – 12+. Button labels sit between the 3:1 UI floor and the 4.5:1 text
  floor; darkening brand-primary changes every primary button + toolbar.
  **Owner call: leave** (revisit only as a deliberate brand-darkening).
- **↪ Wordmark** (yellow-on-green, ~2.8:1): **leave** — WCAG 1.4.3 exempts
  logotypes/brand names from contrast requirements.
- **⟳ Essential stat + brand-secondary rethink → [[FU-621]].** The Essential
  footer count renders in **brand-secondary as text**, invisible on dark themes
  (Cherry-Cola-Dark 1.10:1). Root cause = the dark-theme `--brand-secondary`
  values are near-black mud (e.g. `hsl(2 16% 19%)` on a `hsl(2 16% 16%)` card),
  and secondary is asked to be both a dark toolbar bg (light themes) AND a
  legible accent — incompatible in one value. Owner (2026-08-12) opened this as a
  brand rethink ("secondary has felt off"). Tracked as **FU-621** (lift the
  dark-theme secondaries into legible accents; give the Essential stat a proper
  ink); to be driven with a visual options board, not a blind edit.

### DR-2 · Stock-level scale + row legend (D-001, D-013) — ✅ DONE 2026-08-13
Out of stock → negative red; Low → warning amber; grey reserved for
unknown/disabled. Add the row-state legend (filter panel section or edge
tooltips): on-list edge, attention outline, expiring tint, open/sealed. Explain
or remove the undecodable states (dimmed row, cream tint — first *identify*
them in code). **Accept:** every row visual state is either self-labelled or in
the legend; both-theme screenshots. **Refs:** FU-578 #33/44, critique §3.1.
**Shipped.** **D-001 (the core bug)** — the level colour map was *inverted*:
`stockLevelLogic.colourForSequence` had Low → `negative` (red) and Out → `null`
(grey), so "out" read calmer than "low" and grey squares were
indistinguishable from disabled rows (FU-578 #33). Retuned to the D-001 ramp:
Stocked → positive, **Low → warning (amber)**, **Out → negative (red)**; `null`
now means *unknown/not-set only*. This map is the single authority behind ~10
surfaces (stock rows, detail, pickers, cook mode, quick-add, stocktake runner,
recipes), so the one edit fixes them all; the neutral-token fallback (`R-002`
`dora-bg-neutral` / `dora-text-muted`) now fires only for genuinely-unknown
levels. The **footer counts** (`useStockFilters.toneForLevelSequence`) held a
hand-copied second copy of the same (wrong) mapping — rewired to *derive* from
`colourForSequence` (`R-003`, one authority) so it can never drift again.
`stockStatus.spec.ts` re-pinned to the D-001 ramp (10 green). **D-013 legend** —
new `StockRowLegend.vue` (R-001) placed in the Stock-overview filter panel,
documenting the whole row colour language: the level squares (derived from the
household's real level rows + `colourForSequence`, so renamed seeds stay
accurate) and the row highlights — essential left-stripe, amber "attention soon"
outline, red "attention now" outline, the **dimmed row** (the undecodable state
from #33, now labelled "out of stock, not marked essential"), and the stocktake
pulse. No "cream tint" / "on-list edge" state exists in current code (audit
mis-read); the dim was the only undecodable one. **Verified live** (seeded verify
backend, DOM + computed-style probe): footer Stocked `rgb(53,151,102)` green /
Low `rgb(251,174,81)` amber / Out `rgb(235,112,96)` red; legend swatches match by
construction. vue-tsc + eslint clean. Cross-theme pixel walk queued in
DORA_VERIFY (row buttons are virtual-scrolled + the pane couldn't composite —
see the DR-8 splash-wedge note).

### DR-3 · De-Quasar detail audit (D-005, D-008) — ✅ DONE 2026-08-12
`no-caps` app-wide (audit every dialog for casing); replace the padlock
open/sealed glyph with a domain metaphor; aria-label + tooltip sweep over
icon-only buttons (the open-toggle first); disambiguate the two cart glyphs;
style the bulk-bar disabled state. **Accept:** zero uppercase dialog buttons;
no icon-only control without name+tooltip (axe/a11y spec extended to pin).
**Refs:** FU-578 #3/15c/34/53, critique §9.
**Shipped:** **Casing** — swept every `$q.dialog` for uppercase buttons:
converted all `cancel: true` / string-shorthand `ok:`/`cancel:` to
`{ label, noCaps: true }` objects across ~15 files (settings CRUD, meal
planner, shopping list, stocktake, stock overview/detail, vocab editor); the
one raw uppercase template button (`RecipeCookMode` "Pause") became a
`BaseButton` (`variant="primary"` + `color="warning"` override) — also closing
the R-001 componentisation gap its inline comment flagged. New rule **R-039**
(dialog buttons must set `noCaps`) added so this can't drift back. **#15c/#3
glyph + a11y** — new `ICONS.sealed`/`ICONS.opened` (`package-variant-closed` →
`package-variant`) replace `lock`/`lock_open` on the stock-row open toggle;
added the missing `aria-label` (was tooltip-only). **#34** — cart glyphs were
already resolved (distinct icon + colour + tooltip + aria per state); no change.
**#53** — disabled state for flat/outline `BaseButton` variants now pins
`--text-muted` (Quasar's opacity-only dim left ghost buttons reading near-white
on the bulk bar); filled variants keep white-on-fill + opacity. vue-tsc +
eslint clean. Running-app visual walk queued in DORA_VERIFY.

### DR-4 · Copy & leakage sweep (D-014, D-006) — ✅ DONE 2026-08-12
Fix "expires expired" (`generators.py:113`); "(s)" plurals in alerts; "Add
(file)" labels; raw UUID off the Account page; display-name greeting
("Good afternoon, dora"); "$1 saves vs rrp"; dedupe "Dessert · Dessert" chips;
batch-cook onboarding explainer in plain words. **Accept:** grep-able tells
gone; copy reads in Dora's register. **Refs:** FU-578 #1/10/12/13/14/21/22/38.
**Shipped:** #1 (each expiry branch carries its own verb); #10 (new shared
`dora_api.infrastructure.utils.pluralize` — routed `get_alerts.py`,
`generators.py`, `confirm_actions.py`; `test_pluralize.py` pins it); #12
(`ImageUploadField`/`StoresSettings`/`RecipeStepImagesEditor` now "Take a photo"
+ natural pick labels); #13 already fixed by the 2026-08-11 account redesign (no
UUID rendered); #14 (`RecipeCard.metaLine` case-insensitive dedupe); #17
(essential-out alert copy made action-neutral); #21 (`DashboardPage.firstName`
capitalises); #22 ("saved vs RRP"); #38 (`AdminSystemCookingSettings` Batch
explainer de-jargoned). Backend 36 tests green, vue-tsc + eslint clean. Live
browser walk queued in DORA_VERIFY. **#49 (uneven `/settings/stores` alias) —
won't-do (owner, 2026-08-12):** the finding was "one legacy path redirects, the
sibling 404s". Pre-release has no real bookmarks/back-compat obligation, so the
correct direction is *no* back-compat redirects, not adding one. Left both dead
legacy paths 404-ing; a wholesale strip of the existing legacy-redirect block is
a separate call (see FU-578 note).

## Wave 2 — interaction correctness

### DR-5 · Open-toggle mutation trap (D-008) — ✅ DONE 2026-08-12
Defer the `is_open` PATCH until dialog resolution (Skip/Update both confirm;
add Cancel + Escape close = no mutation), or keep eager-mutate but add Cancel
that reverts + an Undo toast. Pick the defer option unless code archaeology
shows a reason. **Accept:** backdrop/Escape dismissal leaves server state
untouched (extend the FU-507 e2e spec to pin). **Refs:** FU-578 #2.
**Shipped (defer option).** The mutation is now a *product* of the dialog, not
a precursor to it. The old two-button `$q.dialog` prompt couldn't express the
needed three outcomes — native `$q.dialog` collapses the Cancel button, Escape
and backdrop-click all into one `onCancel`, so "Skip" and "abort" were
indistinguishable. Replaced with a promise-based component dialog
(`MarkOpenExpiryDialog.vue`, via `useDialogPluginComponent`) with three explicit
buttons: **Cancel** / **Skip** (open, keep expiry) / **Update expiry** (open +
set); Escape/backdrop resolve as abort. The decision → PATCH mapping is a pure
helper (`src/composables/openToggle.ts` `buildOpenTogglePatch`) that returns
`null` on abort ⇒ caller writes nothing; the shared orchestration
(`useStockItemActions.planOpenToggle`) is reused by both the row and the detail
page (killed the duplicated FU-507 prompt logic — R-003). **Pinned by Vitest**
(`test/unit/openToggle.spec.ts`, 7 cases: abort ⇒ no mutation, skip/update/seal
mappings) rather than a Playwright spec, per the repo's manual-first stance
(no FU-507 frontend e2e existed — the FU-507 refs are backend router tests).
vue-tsc + eslint clean; full unit suite 419 green. Interaction walk queued in
DORA_VERIFY. **Refs:** FU-578 #2.

### DR-6 · Finish-modal restock review (FU-582) — ✅ CLOSED 2026-07-22, cut confirmed
**Do not build the per-item level picker.** Owner cut it deliberately in commit
`a3b82644` (2026-07-13); FU-582 only existed because that removal went
undocumented. Rationale: someone who just bought an item would never mark it
anything but Stocked, so the picker was ceremony over a foregone conclusion (a
part-used item is corrected on the stock item itself). The `level_overrides`
contract has since been removed server-side too, and a test now pins that a
stale override body is rejected rather than ignored. **Refs:** FU-582 (resolved,
see `DORA_FOLLOWUPS_RESOLVED.md`).

### DR-7 · Toast & helper-bubble placement budget (D-009) — ➗ DONE-with-carve-out 2026-08-12
Single toast column; toasts die on route change; dock the mascot/tip bubble so
nothing overlaps content (safe-area aware on mobile); explain or remove the
"6" badge; tip auto-dismisses. **Accept:** screenshots on stock/detail/reports/
alerts/cook-mode show zero overlap; toast gone after navigation.
**Refs:** FU-578 #6/31/35/41.
**Shipped.** **#41 congestion** — Quasar toasts default to the bottom-right
corner, the same corner as the Dora launcher, so they piled on the mascot. A
global rule lifts `.q-notifications__list--bottom-right` clear of the launcher
(safe-area aware), so toasts stack in one clean column above Dora. **#6/#31
tip** — the first-time "Hi! I'm Dora" hint now **auto-dismisses** after ~9s
(transient; the X is still the permanent ack) instead of lingering over content;
the launcher root now uses `env(safe-area-inset-*)` so it clears the mobile home
indicator. **#35 copy** — the greeting **capitalises the username**
(`doraIntents.ts`, `runIntent` — "Hi, Dora!" not "Hi, dora!", pinned by 2 new
`doraIntents.spec` cases) and the cryptic "Burger online" line became "Dora
reporting for pantry duty". **"6" badge** — already carries an explanatory
tooltip ("Dora has N suggestions for you"); the disabled AI segment already
surfaces a reason via `modeSliderDisabledReason` ("Pick a provider in Settings →
Assistant first" etc.) — both left as-is. vue-tsc + eslint clean; full unit
suite 421 green.
**Carve-out → [[FU-624]]:** the other half of #41 — a toast fired just before
navigation still **persists onto the next route**. The robust fix (a single
`notify()` wrapper tracking dismiss handles + a `router.afterEach` clear) needs
migrating ~296 `$q.notify` call sites, so it's its own unit. A boot-level
`Notify.create` monkeypatch was rejected (`$q.notify` binds the original
reference at install, before boot files run, so the wrapper is bypassed).
**Verify:** placement walk queued in DORA_VERIFY.

### DR-8 · Loading-state unification (D-007) — ✅ DONE 2026-08-13
Dashboard cards get skeletons (kill "Loading…" strings); reserve belief-chip /
verdict-badge space (or reflow-free fade-in); investigate the >2s warm splash
(what does it await?) + give splash dismissal a non-paint-gated fallback
(fixes the background-tab wedge risk). **Refs:** FU-578 #15/23/26/52.
**Shipped.** **#23 (the wedge — headline).** Root cause found: `App.vue` faded the
splash with a Vue `<Transition>`, and Vue toggles the `-leave-to` class inside a
`requestAnimationFrame`. A backgrounded / occluded / throttled tab never composites
a frame, so rAF never fires — the leave wedges at full opacity (`z-9000`,
`pointer-events:auto`), covering the app **and eating clicks** (observed first-hand
last unit — the DR-2 verify pane couldn't composite and the splash stuck at
`splash-fade-leave-active`). Replaced the `<Transition>` with a plain
`splashVisible` flag + a CSS transition: the fade rides `--motion-slow`, but unmount
is driven by a **`setTimeout` (paint-independent)**, and the `--leaving` class drops
`pointer-events` immediately so a lingering node can never block the app.
**Live-verified**: in the same non-compositing pane that wedged the old build, the
new `splash-host` is *removed* on handoff (`setTimeout` fires where rAF didn't).
**#15 (dashboard skeletons).** The main load state was a lone centred `AppSpinner`
and the primary-list card showed a literal **"Loading totals…"** string. Both now
render **content-shaped skeletons** (`AppSkeleton`, the B10 primitive): the load
branch is a 4-card grid reusing the real `DashboardCard` shell (title line + 3 body
lines each), and the totals slot is a skeleton stat-grid that reserves the same
space the numbers fade into. **Live-verified**: dashboard renders 4 skeleton cards +
16 pulsing blocks, **zero "Loading…" strings**. **#52 (belief-chip / verdict
reflow).** The stock-row second line (location + async belief chip) now reserves a
`min-height` so a late-arriving belief pill can't grow the row after paint, and both
`PantryBeliefChip` and `BuyVerdictBadge` **fade in** (`--motion-fast`, ~0 under
reduced-motion) instead of hard-popping. **#26 (>2s warm splash) — investigated, no
code change.** The boot awaits exactly two lightweight probes (`bootstrapRequired`
COUNT → `/auth/me`); the >2s warm-*reload* delay is Vite recompilation + backend
cold-start, **not app work** — a production build doesn't pay it. Documented; the
actionable half of #26 (the wedge) is the #23 fix above. vue-tsc + eslint clean.
Belief-chip/verdict visual + the authenticated dashboard skeleton transition queued
in DORA_VERIFY (virtual-scroll rows + the harness's cross-origin session need a
painting browser).

## Wave 3 — layout

### DR-9 · Toolbar & grid composition pass (D-011) — ➗ DONE-with-carve-outs 2026-08-13
Shopping-list toolbar wraps/collapses to More (fixes the 255px mobile overflow
AND the 1280px title collision); dashboard + reports grids stop stranding
half-width cards; mobile stock rows: collapse the three trailing icons into an
overflow menu so names stop truncating at ~10 chars; belief chip placement on
chip-bearing rows. Tap-target pass to D-004 on stock rows/toolbars.
**Accept:** no horizontal scroll at 375px anywhere; no lone card beside dead
air; row names readable on mobile. **Refs:** FU-578 #4/19/30/40/15b.
**Shipped (the accept criteria — toolbar overflow + mobile name readability).**
Root cause of #4/#40 found in the *shared* `PageToolbar`: `.page-toolbar-actions`
was `flex-shrink: 0`, so the ~930px shopping-list action cluster kept its width and
either overflowed the viewport (mobile, ~255px of horizontal scroll) or shoved the
title into a mid-word wrap that collided with it (1280px). Fixed at the component so
**every** PageToolbar benefits: the actions now wrap (drop onto their own line[s]
below the title) and the title cell gets `min-width: 0`. **Live-verified**: shopping-
list detail at **375px → 0 horizontal scroll** (was ~255px); at **1280px** the title
"Shopping lists" stays one line, un-wrapped, actions cleanly below — no collision.
For the mobile stock rows, the item **name now wraps to two lines under 600px**
(`-webkit-line-clamp: 2`) instead of truncating at ~10 chars ("Barilla Pa…"), so
names are readable; desktop keeps the one-line ellipsis. vue-tsc + eslint clean.
**Carve-out → [[FU-631]]** (three redesign-scope pieces, each its own risk): the
shopping-list toolbar is now overflow-free but tall on mobile (a cleaner *collapse
of grouping/Refresh/Select into the existing More menu* is deferred); the stock-row
**trailing-icon → ⋮ overflow menu** (#15b) + strict **44px tap-target pass** (#19)
are deferred because each trailing button carries a rich nested interaction; and the
dashboard/reports **stranded half-width card** packing (#30) needs per-zone odd-count
logic against the CSS-`order` zone system, not a pure-CSS rule. Same split pattern as
DR-7 → FU-624.

### DR-10 · Nav labelling (D-005) — ✅ CLOSED 2026-08-13, owner chose "leave as-is"
Give the icon strip labels (under-icon at desktop, keep hamburger on mobile) or
at minimum active-page label + tooltips. **Refs:** FU-578 #5, critique §4.
**Decision (owner, 2026-08-13):** shown a live 3-way mockup — Current (icon-only,
labels on strip-hover) vs Option 1 (always-on under-icon labels) vs Option 2 (active-
page label + hover tooltips). Owner chose **leave the nav as-is**. No code change. The
existing desktop strip already reveals labels on hover + carries a sliding accent
active-indicator; the mobile hamburger drawer shows full labels. FU-578 #5 is resolved
as won't-change by owner call, not a defect.

## Wave 4 — surface redesigns (one session each, design-first)

### DR-11 · Recipe detail read-mode (D-015) — ✅ DONE 2026-08-13
Read view (hero/meta chips/ingredients/instructions) + explicit Edit mode;
fix the "0 unallocated of 1 cooked" vs "Last cooked: Never" contradiction while
in there. **Refs:** FU-578 #11, critique §8.1.
**Shipped.** `RecipeDetailPage` was "an edit form wearing a detail page's clothes"
(critique §8.1) — every field a permanently-live input. It now **defaults to a read
view** and an explicit **Edit** toggle reveals the form (D-015; cook mode already
proved the reading-surface pattern). Read view renders from the same `form` model the
editor writes (can't drift): hero image, the name as a **title heading** (not a field),
meta chips (cuisine/category/time-of-day/difficulty/servings/prep+cook/kcal/tags/tools),
ingredients **grouped by section** (qty·unit·name·notes, optional + missing markers),
instructions (structured steps / freeform lines / step images), source link, notes. The
editor cards are gated behind `v-if="editing"`; the **Available meals** stepper stays
visible in both modes (it's a status+action, not an edit field). Toolbar shows **Edit**
in read mode, **Save + Done** in edit. **#11 contradiction fixed**: "of N *cooked*"
(which implied a cook event, clashing with "Last cooked: Never") → "of N **on hand**",
matching the card title + tooltip's "in your pool" wording — the pool is raisable via the
stepper without ever cooking. vue-tsc + eslint clean; all ICONS verified; the updated
component mounts without a compile/render crash. **Known limitations → DORA_VERIFY /
minor follow-up:** read view lists **top-level steps only** (nested substeps aren't shown
in read mode — most recipes are flat; edit mode still shows them); per-step
ingredient/tool associations aren't surfaced in read mode (the ingredient list covers
them). Full visual walk queued in DORA_VERIFY (recipe data won't load in the verify pane
— the app's XHRs don't carry the cross-origin session cookie).

### DR-12 · Alerts page order + calendar diet (D-012) — P2 — ➗ PARTLY OVERRULED 2026-08-30
Actionable list first; calendar becomes a labelled 14-day strip (counts on
cells) or moves below; same treatment for the meal-plans mini-month.
**Refs:** FU-578 #28/50.

**The meal-plans half of this is overruled and is now DONE differently.** This
item was recorded as *"rides the redesign"*, and the redesign arrived:
`BRIEF_MEAL_PLANNER_RAIL_AND_SHELL.md` §5, decided as **D7** by the owner on
2026-08-29 and built 2026-08-30. The planner's calendar became a **full month
grid** with focusable days and per-meal pips — **not** a 14-day strip.

The reasoning, recorded so this doesn't get "corrected" back: DR-12's rationale
is a calendar *competing with an actionable list*, which is the Alerts page's
problem and not the planner's — on the planner the calendar **is** the
navigation, and the actual fault was the opposite of bloat. The old widget was a
week picker wearing a calendar costume: only the week row was clickable while the
day squares carried the status colour, so days invited a click that did something
else. Shrinking it further would have kept that. Making the days real is what
fixed it, and it bought a payoff a strip could not: clicking a day now scrolls
the week pane to that day's card.

**Still open under DR-12:** the Alerts page ordering (actionable list first) and
its own calendar, plus the reports charts noted in the mapping table. Only the
meal-plans mini-month is settled.

### DR-13 · History timeline grouping (D-012, D-006) — ✅ DONE 2026-11-05
Collapse repeated kinds ("Pushed expiry ×50 over 3 months"), per-kind filter
chips, one date format via the DR-14 formatter. **Refs:** FU-578 #32.
**Shipped (owner: build it):** three or more neighbouring events of the same kind
collapse into one "Moved expiry ×50" row with its date span and a Show all /
Hide toggle (`groupLifecycleEvents`, pinned in `lifecycleTimeline.spec.ts`);
kind chips (Bought / Used / Levels / Expiry / Lists / Waste) appear when an item
has more than one kind. Dates already went through the DR-14 formatter.

### DR-14 · Locale/format authority (D-006) — ➗ DONE-with-carve-outs 2026-08-13
Single date/currency formatter module (household locale+tz); replace direct
`toLocaleDateString` calls; onboarding SETUP gains the one-line "Use this
device" region derivation (backend already has the endpoint + admin override).
Also reconcile the two theme mechanisms (`body--dark` vs raw media queries) —
same "one authority" principle, fixes the split render. **Refs:** FU-578
#9/48/51, 7b.
**Shipped (the date authority + the visible #9 bug).** The *currency/locale* authority
already existed (`useMoney`, reads the install's `locale_policy`); the missing half was
**dates** — 26 sites across 22 files called `.toLocaleDateString()` / `.toLocaleString()`
with no locale, so they rendered in the *browser's* locale ("7/17/2026" US on an AU
install). New **`useDateFormat`** module (`formatDate` + `formatDateTime`, Intl-options
passthrough) reads the **same** household locale as `useMoney` via two new shared exports
(`currentLocale()` / `ensureLocalePolicy()`) — one locale source for money *and* dates, so
they can't drift (R-003). Migrated **all 26 sites** (local `formatDate` helpers delegate;
inline calls swapped) — grep confirms zero direct date `toLocale*` calls remain (only two
`.toLocaleString()` on *numbers* stay, correctly). **Verified:** vue-tsc + eslint clean
across all 24 files; `Intl` confirms the household locale now yields **"17/07/2026"** (en-AU)
where the old browser path gave "7/17/2026". The locale defaults to en-AU, so the fix holds
even when the server sends no policy. **Carve-out → [[FU-632]]:** (1) **#48 first-boot region
derivation** — `locale_policy` comes back *null* on a fresh install (locale/tz never asked);
wire a browser-derived locale+tz at first boot / a SETUP step, persisted, keeping the admin
override (also add tz to the policy so datetime renders are household-tz correct). (2) **#7b
theme-mechanism reconciliation** — `body--dark` vs raw `prefers-color-scheme` disagree until
reload; pick one authority. Both are separable units (onboarding+backend, and theming). #51
(reconcile-queue date vs meal-grid date) is now resolved in passing — both routes go through
`useDateFormat`.

### DR-15 · Micro-motion pass (D-010) — ➗ DONE-with-carve-out 2026-08-20
`--motion-fast` feedback on level change / tick / add-to-list / chip toggles;
meal-planner wizard dedupe (one selectable instance per recipe, FU-578 #47) can
ride along. **Refs:** critique §6.
**Shipped.** One shared vocabulary rather than per-site keyframes (R-001/R-003):
three utilities in `motion.scss` — `.dora-press` (persistent `:active` scale),
`.dora-settle` and `.dora-bump` (one-shot) — plus three amplitude tokens
(`--motion-settle-from/-bump-to/-press-to`) that the reduced-motion block
flattens to `1`, so the kill-switch covers them for free. The one-shot pair are
applied for a single cycle by a new **`useMicroFeedback()`** composable, which
reads its own timer length from `--motion-fast` (no literal `ms` anywhere) and
**removes the class again** — a class left on re-fires the animation on every
re-render, which is how a one-shot acknowledgement turns into the ambient
wallpaper D-010 warns about.
Wired at all four gestures: **level change** → settle on the stock-row level
square; **add-to-list** → bump on the row cart button when cart state flips
(row variant only — a 16% scale on a labelled toolbar button reads as a twitch,
and those aren't high-frequency); **chip toggle** → press + bump on `FilterChip`
*and* `TriStateFilterChip`; **tick** → press on the shopping-list and stocktake
checkboxes, and the ticked line now *fades* to its dimmed state instead of
snapping. `RowActionButton` carries the press for the whole row cluster, so
expiry / open-sealed / price / cart answer uniformly. `AnimatedNumber`'s
hardcoded `600ms` also went — it now reads `--motion-slow` (D-010's no-literal
clause; count-ups settle a little quicker as a result).
**FU-578 #47 (the ride-along) is fixed, and R-003'd on the way:** the tray
builder existed **twice, character-for-character** (`useMealPlanner.ts` and
`MealPlanBuilderDialog.vue`), so a dedupe in one would have left the two pickers
disagreeing. Both now call `helpers/recipeTrays.ts`, where each recipe is
claimed by exactly **one** tray (Favourites → stale → frequently-planned →
"Everything else"). Caps apply *before* the claim so an over-cap recipe falls
through rather than vanishing, and search still flattens across the whole
cookbook.
**Verified:** 3 of the 4 gestures walked **live in the running app** —
level-change settle (`dora-settle` applied on a real level set, animation
`dora-settle 0.12s`, class gone after), cart bump (`none → on_other`,
`dora-bump 0.12s`), chip press+bump (all 5 stock filter chips carry
`.dora-press`; a real click showed the bump apply and clear). Also probed live:
all three amplitude tokens resolve, both keyframes are in the compiled sheet,
`.dora-press` resolves to `transform 0.12s cubic-bezier(0.4,0,0.2,1)`, and the
reduced-motion block carries all three new amplitudes → `1`. Frontend **504
passed** (was 488: +6 tray specs, +10 micro-feedback/token-parse specs),
vue-tsc 0, eslint clean.
**Carve-out — the critique §6 *transition* bullets, deliberately not built.**
§6 also asked for route-change transitions and a dashboard loading→content
crossfade. The crossfade is largely moot (DR-8 replaced those "Loading…" text
swaps with the shared skeletons), and the belief chip's reflow was already fixed
in DR-8 with a fade into reserved space. **Route transitions are left alone on
purpose:** this unit's own R-050 finding is that the app has twice been bitten by
sequencing state behind paint, and a page-level transition is exactly where that
goes fatal rather than silent (the DR-8 splash wedge). D-010's scope is
high-frequency *gestures*, which are all now covered; a route transition is a
separate, riskier piece of work. Logged as [[FU-694]].
**New rule:** **R-050 + ADR-046** — never sequence app state behind a paint
callback. The composable's first draft used `requestAnimationFrame` to restart
the animation; rAF doesn't fire in a backgrounded/throttled tab, so the class
write was scheduled and silently never happened. Same assumption as the DR-8
splash wedge, opposite failure mode.
**Verify:** the tick fade + tray dedupe walk is queued in `DORA_VERIFY.md` —
the shopping-list detail and the planner rail don't render in the verify pane
(route transitions wedge there, and the rail is behind the pane's forced-mobile
`$q.screen` branch).

### DR-16 · Onboarding activation step — SKIPPED (owner, 2026-11-05)
A "get food in" step (add first items / import / start with the starter list)
in SETUP, and drop Price history from the all-set hub for data-empty accounts
(R-012/R-014 tension — reveal-and-disable may prefer a "collects as you shop"
caption instead of removal). Register-form eager validation fix (#37) rides
along. **Refs:** FU-578 #37/39.
**Skipped (owner, 2026-11-05):** the wizard's "Your stock" step and the money-gated
Price history tile already cover the intent; no separate activation step.

---

## Coverage table (audit → action)

| Audit item (FU-578 # / critique §) | Unit | Note |
|---|---|---|
| 1, 10, 12, 13, 14, 21, 22, 38 (copy/leakage) | DR-4 | |
| 2 (open-toggle trap) | DR-5 | |
| 3, 15c, 34, 53 (icons/casing/disabled) | DR-3 | |
| 4, 19, 30, 40, 15b (toolbars/grids/targets) | DR-9 | |
| 5 (nav labels) | DR-10 | owner taste call |
| 6, 31, 35, 41 (bubble/toasts) | DR-7 | |
| 7, 43 (contrast) + wordmark | DR-1 | |
| 7b, 9, 48, 51 (theme split + locale) | DR-14 | |
| 11 (cook-count contradiction) | DR-11 | |
| 15, 23, 26, 52 (loading/splash) | DR-8 | |
| 16 (meal-plans stat confusion) | DR-12 | redesign landed 2026-08-30 — month grid, **not** the 14-day strip (D7) |
| 17 (bell advice/action mismatch) | DR-4 | copy-level fix |
| 18 (rows not real links) | DR-9 | stretch: `href` on rows |
| 20 (kitchen-health scores unused feature) | DR-16 | skip-component like Budget |
| 24/25 (superseded/console error) | — | 25 stays FU-578 verify item |
| 27 (stocktake change-button affordance) | DR-3 | wording/affordance tweak |
| 28, 29, 50 (calendars/charts) | DR-12 | reports charts included |
| 32 (history wall) | DR-13 | |
| 33, 44 (level colours/legend) | DR-2 | |
| 36, 42, 45, 46, 54 (keep-as-is / cross-refs) | — | protected exemplars |
| 37, 39 (register validation, activation) | DR-16 | |
| 47 (wizard dupes) | DR-15 | ✅ done — one tray claims each recipe |
| 49 (missing route alias) | DR-4 | one-line ride-along |
| FU-582 (finish pickers) | DR-6 | ✅ closed — cut confirmed, do not build |
| Critique §6 (micro-motion) | DR-15 | ✅ gestures done; route transitions → FU-688 |
| Critique §8.1 (recipe detail) | DR-11 | |

**Open decisions — spawned, not dangling:** DR-6 scope (build vs cut), DR-10
(labels vs tooltips), DR-16 (activation step shape) are flagged `needs owner
sign-off/call` inline above; they block only their own units. Everything else
is approved-to-action per the owner's 2026-07-18 directive.

**Suggested order:** DR-1..DR-5 first (small, compounding, unblock screenshots
that look right), then DR-7/8/9/14, then the redesigns.
