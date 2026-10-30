# DORA_VERIFY triage & campaign tracker

> **2026-08-28 — the Browser pane cannot verify any routed page.** It never
> advances a CSS transition: every route freezes at `dora-fade-enter-from` /
> `dora-fade-leave-from` and the page's content never enters the DOM (measured
> still at frame zero 1.5s later, surviving reload, resize and re-fronting the
> tab). Sticky chrome *outside* the transition — the counts footer — renders
> fine, which is how you tell this apart from a real bug. Adds to the two limits
> already known (no screenshots; can't drive `$q.screen` breakpoints). **Use a
> throwaway Playwright script from `web_app/` instead** — not a committed spec,
> per the stance below. Two traps found doing it: a cache-invalidation check must
> stay inside one page session (a `page.goto` between visits refetches regardless
> and proves nothing), and on desktop a stock row click opens the peek panel,
> whose dialog backdrop then swallows every later click — write through the row's
> level menu instead.

> ## ⚠️ STANCE CHANGE (owner, 2026-07-20) — LEAN testing, manual-first verification
>
> The original campaign aimed to **codify every regression-worthy check as an
> automated test** ("test everything that COULD have a test"). The owner has
> reversed that: **that ambition was foolish for this app.** The new stance:
>
> - **Verification is primarily MANUAL once-off drives** — the agent or the
>   owner drives the running app to confirm a thing works, once, and moves on.
>   We do NOT convert each check into a durable test.
> - **Automated tests are kept LEAN — only the most valuable, LOW-CHURN
>   contracts.** A test earns its place only if it pins something stable that
>   would be expensive to re-check by hand *and* is unlikely to change as
>   features evolve. Feature-behaviour/UI-flow tests (which churn) are NOT worth
>   maintaining.
> - **Playwright is now a minimal smoke layer only** — `auth.setup` + `login` +
>   `smoke` (does the built SPA boot, route, and authenticate). The ~22
>   feature-behaviour specs were **deleted 2026-07-20** (they were slow + flaky
>   as an 84-test single-worker suite — see the retired FU-591; and they tested
>   things "subject to change"). Do NOT add feature-flow Playwright specs.
> - **Backend/Vitest tests already written are kept** (they're fast, reliable,
>   low-churn, and several caught real bugs — FU-588/589/590). But going forward,
>   only add one when it clears the "valuable + low-churn" bar; default to a
>   manual once-off check instead.
> - **DORA_VERIFY.md items** that were previously "pinned by <a now-deleted
>   Playwright spec>" revert to manual once-off checks — which is the new default
>   anyway. Backend/Vitest pin-notes remain valid.
>
> **Agent browser-driving — DIAGNOSED + WORKING RECIPE (2026-07-22).** Earlier
> it looked like a dead end (data-driven cards never painted); root cause found
> and worked around. **Why it half-mounted:** the mcp Browser pane runs the doc
> **hidden** (`visibilityState:'hidden'`, `hasFocus:false`), so the browser
> suspends `requestAnimationFrame`; the app's AuthShell splash-dismiss + all Vue
> `<transition>`s are rAF-gated → never complete → cards/dialogs/lists never
> enter the DOM (shells render because they have no rAF-gated transition).
> **THE RECIPE (verified: 11 Cookbook cards + collection groups + chips paint):**
> 1. `preview_start` `dora-verify-backend` (seeded API+SPA on :5170).
> 2. On the login page, in ONE `javascript_tool` call: shim
>    `window.requestAnimationFrame = cb => setTimeout(()=>cb(performance.now()),0)`
>    (+ `cancelAnimationFrame → clearTimeout`), THEN log in **in-place** — set
>    the username/password via the native value-setter + dispatch a bubbling
>    `input` event (Quasar `q-input` ignores `form_input`/synthetic typing), then
>    `form.requestSubmit()`. The app authenticates WITHOUT a reload, so the shim
>    survives.
> 3. Navigate ONLY in-app via `location.hash='#/cookbook'` (NOT the `navigate`
>    tool / never `location.reload()` — a full load wipes the shim + re-triggers
>    the stuck splash).
> 4. Then `read_page` / DOM queries see the painted content. (A leftover
>    `[class*=splash]` node stays in the DOM but doesn't block — cards render
>    underneath.)
> So card/grid/dialog/flow verification IS agent-doable now — this is the same
> init-script rAF-stub trick the deleted `drive.mjs` used, reproduced in-pane.
>
> **RECIPE v2 (2026-07-22, Batch-7 session) — RELOAD IS FINE, AND YOU NEED IT.**
> Two corrections to the above, both found the hard way:
> 1. **`location.reload()` does NOT strand you.** Step 3's "never reload" is too
>    strong. Reloading while the session cookie is live re-mounts the app
>    authenticated, and the stuck splash overlay renders *behind* the content —
>    a fresh `javascript_tool` call that re-installs the rAF shim right after the
>    reload gets a fully painted page. This unlocks every "hard-reload and check
>    it persisted" verify item (localStorage prefs, admin toggles), which recipe
>    v1 had no way to walk. Re-install the shim on **every** reload — first line
>    of the next call.
> 2. **Resize BEFORE the mount that matters, or you get the mobile layout.**
>    Quasar's `$q.screen` is frozen at whatever the pane's width was when the app
>    booted; synthetic `resize` events and the `resize_window` tool do **not**
>    move it afterwards (media queries update, `$q.screen` doesn't — its listener
>    is rAF-gated behind the pre-shim native rAF). The pane boots narrow, so
>    `$q.screen.lt.md` sticks TRUE and `/meal-plans` renders `mobile-focus` even
>    at 1600px. Order that works: `resize_window` → `location.reload()` →
>    re-install shim. Desktop three-column planner then renders.
> 3. **`computer{action:"screenshot"}` times out** in this pane (renderer is
>    hidden) — do not budget for screenshots. Verify via `read_page` /
>    `document.body.innerText` / `getComputedStyle`, which is enough for layout,
>    type-scale and theme-token checks (measure computed `fontSize` /
>    `backgroundColor` across settings changes).
> 4. **Mutating API calls need the CSRF header** when driven from the page:
>    read the `dora_csrf` cookie and echo it as `X-CSRF-Token`, or every
>    POST/PATCH silently 403s.
> 5. **Do not rebuild the SPA mid-walk.** A `quasar build` swaps the hashed
>    chunk filenames under the running page; the still-loaded old bundle then
>    fails every lazy route import ("Failed to fetch dynamically imported
>    module") and the router *silently keeps the previous view* — which reads
>    exactly like a broken navigation bug. Cost this session ~20 minutes chasing
>    a phantom. Rebuild, then reload, then re-test.
> 6. **Quasar `q-input` still can't be driven synthetically** (v1's finding
>    holds) — but the **native-value-setter + bubbling `input` event** trick
>    works on plain `<input>`s inside dialogs (`type=number`, `type=date`),
>    which is enough for the reconcile verb dialogs.

**What this is (historical framing, superseded by the banner above):** the
working plan for clearing the QA pile in `DORA_VERIFY.md` (1,406 unchecked items
as of 2026-07-16). Original approach (owner, 2026-07-16): triage → agent-verified
evidence reports per surface → guided-walkthrough packs for eyeball items →
device packs for hardware items.

**How a verify session uses this doc:**
1. Pick the next ⚪ batch from the batch plan below (or the one the owner names).
2. Re-read the target sections in `DORA_VERIFY.md` (line refs here are a
   **2026-07-16 snapshot** — they drift as the file is edited; grep the heading).
3. Seed/contrive the data states, walk every **A** item in the running app,
   and record pass/fail + evidence in a report to the owner.
4. **V** items: stage + screenshot, hand to the owner as a walkthrough pack.
5. **H** items: leave for the matching device pack (Appendix A).
6. Fails → new `DORA_FOLLOWUPS.md` entries (type=finding). Passes → **delete
   the lines from DORA_VERIFY.md in the same session** (owner delegation
   2026-07-18, replacing the old "owner-deletable" marker convention; this doc
   + the worklog keep the evidence trail). Reword surviving neighbour bullets
   so they stand alone; failed/partial items stay.
7. Flip the batch's status here and log the unit in `DORA_WORKLOG.md`.

> **2026-07-18 sweep note:** every line previously marked "owner-deletable"
> (Batches 0/2/3 — ~85 checkboxes: SettingsFileDrop, BuyVerdictCard, Password
> policy, Runtime-URL L112, the six backend-pinned Stock fix sections,
> FU-507/508, stocktake settings dials + alert-threshold removal +
> "Needs check" behavioural bullets, the full stocktake-runner codified
> blocks, bulk-waste, auto-add, 3-band collapse) **has now been deleted from
> DORA_VERIFY.md**. Line refs in the progress notes below pre-date that sweep.

**Classification key:**
- **A** — agent-verifiable (browser/API/DB/CLI on this box, incl. viewport
  emulation, drag automation, typed barcode entry, DevTools-style checks).
- **V** — agent-stageable, human-eyeball verdict (theme readability, animation
  feel, copy tone). Agent stages + screenshots; owner judges.
- **H** — hardware/human-only (real Android/iPhone/Mac, camera, mic, audible
  audio, real inbox, physical print, product-scope decisions).

**Status key:** ⚪ not started · 🟡 in progress · ✅ verified + reported ·
➗ done with carve-outs · 🗑 stale — recommend delete (owner call).

---

## Verified live — finish-off walk A: security, planner/list decisions, QA round 3 (2026-10-30)
Seeded backend on 127.0.0.1:5181 + scratch Playwright (Chrome). Deleted from DORA_VERIFY on pass:
- Sign-in page signed out shows no "Need an account?"; capabilities `registration_enabled:false`.
- Users → Sign-ups on → button appears, `walker` registered and landed on `#/welcome`; off again → gone.
- Two contexts, password changed on one → the other's next nav went to `#/login?redirect=%2Fcookbook`; the changer stayed in.
- Two devices on one week: B got PATCH 409 → 204 and both meals are on Sunday (API + screen).
- Finish with a set-aside line: "6 items aren't ticked, including 1 set aside for the budget."; moved lines `deferred_by_budget=false`.
- Slot Snack → Nibbles: entry relabelled, planner row "Nibbles / Weekend Focaccia".
- QA r3: shopping-list print totals match cards (incl. de-DE 61,97 €); recipe print sections/steps/tips/timers/5 step photos/"Coconut milk"; meal-plan print 7 days + "Cook (batch of 3)" + Leftovers; CSV BOM + "Crème brûlée" + household-date filename (Pago Pago); audit log household-zone times + "(1 event)"; en-US/NY "OCTOBER 2026", de-DE "MO DI MI" + "+200,4 %"; Pago Pago "Today" + Next to cook agrees; cookbook cookable after restock without reload; donut → Out filter clears the typed search; "full cream" → 1 item; done list Add item disabled + 422 on POST lines and bulk-add.
Left in DORA_VERIFY: production public-URL check and deals mail (operator); "mark milk as out" needs an AI provider.

## Verified live — Reports chunk 3, the restructure (2026-09-02)

Driven on the dense seed at :5171 (throwaway backend + built SPA + a scratchpad
Playwright script, per the stance — no committed specs added). The two
`DORA_VERIFY.md` price-trends lines were **deleted on pass**; the section they
were in was replaced with what the drive could *not* cover.

| Deleted verify line | Evidence from the drive |
|---|---|
| "Type in the picker: results come from the whole catalogue, not the first 50" (FU-813) | Typing `yog` fired `GET /products?filter=name:ct:yog&sort=name:asc&page=1&limit=20` and returned the one match ("Chobani Greek Yoghurt 6x170g · Woolworths"). The needle goes to the server — which is the contract; the seed only holds 12 products, so "well down an alphabetical list" is proven by the request, not by the count. |
| "With products selected, click the picker's clear (x) — it used to throw" (FU-813) | Selected a product (chart drew, y-axis `$0.00`–`$3.00` through `formatMoney`), clicked clear: chips emptied, the card fell back to *"Pick a product to chart its unit price over time"*, and **zero** page errors were recorded. |

**Also confirmed in the same drive, no verify line needed:** four cards and no
`[class*="report-card"]` fork (0 matches); `border-radius: 10px` /
`padding: 16px` measured on a live card (FU-814 item 4); all three Spend axes;
one 404'd endpoint failing exactly one card while the other three render;
money-off leaving exactly two count-based cards with **no** money endpoint
called and the nav entry intact; one grid column at both 700px and 390px with
`scrollWidth == clientWidth`.

**Three defects the drive found** (all fixed in the same unit): the cook
timeline's missing gaps, the Spend card's coverage footnote surviving into its
error state, and — from running the suite rather than the browser — three red
`MealsCookedHandler` unit tests whose stub session predated `_repertoire()`.

---

## Pinned by test, not by a live drive — dashboard chunk 1 (2026-09-02)

Two `DORA_VERIFY.md` lines added earlier the same day were **deleted rather than
walked**, because both turned out to be exactly what the stance says *is* worth
automating: a stable, low-churn contract that is expensive to re-check by hand.
Recorded here per the delete-on-pass rule.

| Deleted verify line | Why a test instead | Evidence |
|---|---|---|
| "Savings card: expect a whole-dollar headline (`$128`) above a 2-decimal line" (FU-821) | Money formatting is a formatter contract, not a feature flow. Re-checking it by hand means eyeballing three figures in two currencies. | `web_app/test/unit/animatedNumber.spec.ts` — 7 tests: decimals, thousands grouping, a **suffix-locale** formatter (`fr-FR`, which a manual AU walk could never catch), formatter-beats-prefix, and the untouched counter path. |
| "With the clock in a negative UTC offset, plan a meal for tomorrow: expect 'Today'" (FU-820) | This needed an operator to change the container/device timezone — the single most expensive check in the pile — and it guards the app's *one* date authority, which every surface reads. | `web_app/test/unit/relativeDay.spec.ts` — 14 tests, and **`vitest.config.ts` now pins `TZ: 'America/New_York'` for the whole suite**, so every date test in the repo runs west of Greenwich from now on. That change immediately caught a second live instance: `alertRow.spec.ts` was computing its own expectation with the same broken `new Date(iso).toLocaleDateString()` pattern, so it *expected* the wrong day and passed only because the component was wrong in the same direction. |

**Also worth noting as evidence of the same kind:** the R-060 guard
(`designTokensDeclared.spec.ts`) replaced what would otherwise be a permanent
"grep before you use a token" review habit — and found 21 undeclared tokens on
its first run, 20 of which are outside this chunk ([[FU-834]]). A ratchet, so it
stays green while the debt is enumerated in code.

**Not** converted to tests, and left in `DORA_VERIFY.md` as live browser items:
the Kitchen-health palette across themes, the donut's live theme repaint, the
reconcile chip's border, the money-off walk, and the product-photo render. All
five are "does this look right in a real theme/install", which is the manual-first
case the stance is about.

---

## Verified live — meal planner Unit 1, the app-shell conversion (2026-08-30)

Driven with a throwaway Playwright script against the scratch pairing (backend
:5171 on `data/scratch-verify.db`, SPA :5174; the owner's :5170 was up
throughout and untouched). Measured, not eyeballed — the whole unit is layout,
so the checks are geometry.

| Check | Evidence |
|---|---|
| Document no longer scrolls (the point of the shell) | `documentScrollsVertically: false` at 1024/1280/1440 |
| No horizontal page scroll (D-011) | `documentScrollsHorizontally: false` at all three, and at 375 |
| **The sticky-rail overhang is gone** | all three pane bottoms at **884px in a 900px viewport**; previously `calc(100vh - 32px)` ignored the 64px header |
| Week pane owns its scroll | `weekScroller {clientH: 714, scrollH: 752, scrolls: true}` |
| Toolbar acceptance (≤96px, no third line) | **90px, no wrap** at 1024, 1280 and 1440 — after the compact fix; it was **129px and wrapping at 1024** before |
| The five removals actually left | `.planner-sticky` 0, body toggle-row 0, right-pane templates card 0, `[draggable=true]` recipe rows 0 |
| The ⋮ menu carries what the toolbar shed | six items read back: duplicate, print, save template, browse templates, show all slots, Clear week |
| Mobile untouched (§3.4) | at 375: shell absent, `MealPlanMobileFocus` renders, `.meal-plans` back to natural height (520px) after the `height: auto !important` hatch |

Console was clean apart from the pre-boot `/me` 401, which is the authStore
bootstrap probe on an unauthenticated context and fires on every page.

**Not covered, and now in `DORA_VERIFY.md`:** running the ⋮ verbs for real
(only the menu's contents were confirmed), the layout with `OfflineBanner`
showing (the second offset the old formula ignored), the rail under a large
cookbook (the seed has eight recipes), and whether icon-only "Build my week"
still reads as primary at 1024.

## Verified live — recipe + cookbook batch, and the `show_recipe_images` cut (2026-08-29)

Scratch backend :5172 through the SPA on :5175, throwaway Playwright script from
`web_app/` (the Browser pane still can't render a routed page — see the banner).
1280×900, light theme. Everything below passed, so per the delete-on-pass
delegation the evidence lives here rather than in `DORA_VERIFY.md`. Only two
things were pushed to that file, both genuinely out of a light-theme desktop
run's reach: the two new cards in a dark theme, and the 18px star + the filter
row at 375px.

**The six-item feedback batch.**
- ✅ Cook-now sub-line gone — status strip reads exactly
  `RIGHT NOW / 2 ingredients to link / LAST COOKED / Never`.
- ✅ Details drawers: three cards, all `1px solid` + 4px radius + no shadow, one
  glyph each (`note-text-outline` / `heart-pulse` / `history`).
- ✅ Filters: all **13** controls measure 210px, zero clipped labels. Rows still
  wrap to three lines at 1280px → **FU-773 unchanged** (re-measured, noted there).
- ✅ Star glyph computes 18px in both densities; pill stays 67×26.
- ✅ Step ingredient links: PATCH **204**, links persist against the re-keyed
  ingredient rows (asserted by label, not id). Backend-covered by
  `test_recipe_step_ingredient_links.py` — the one automated test this batch
  earned, per the stance.
- ✅ Unit picker: dropdown offers 14 units incl. `g` with the input empty on open;
  picking one leaves the dialog standing and the row reads `1g`. The pre-fix
  failure was captured first (`kept.trim is not a function`, error boundary
  tearing the dialog down) so the fix is pinned to a real observation.

**The `show_recipe_images` cut.**
- ✅ Appearance: four sections (Theme mode / Theme / Font family / Text size),
  **0** toggles, no occurrence of "photo" in the page text.
- ✅ Surviving controls still save — flipped text size to Large, toast fired,
  `/auth/me` returned `font_size: "lg"`. Checked deliberately: the cut removed a
  sibling section, which is exactly when a page quietly loses a handler.
- ✅ Flag absent from `/auth/me`; `PATCH /auth/me {show_recipe_images:false}` →
  **400 `extra_forbidden`** rather than a silent no-op.
- ✅ Recipe hero renders unconditionally (`naturalWidth 400` on a JPEG uploaded
  via the API — no seeded recipe has a photo, cf. FU-754); a photo-less recipe
  still offers "Add a photo" with `aria-label="Add a recipe photo"`.
- ✅ Stock item → Recipes (3): all three cards render the 110px media strip, the
  one with a photo showing it and the other two their initial tiles — identical
  to the cookbook, which is the point of dropping the `showImage` prop.

---

## Verified live — shopping-list feedback batch 3 (2026-08-28)

Same isolated scratch backend (:5171) driven through the SPA on :5174 via the
`localStorage['dora.backendBaseUrl']` override. **1280px and 375px**, money on.

- **Draft prices are read-only.** `.sld-price-btn` count **0**; three rows render
  `~$8.00 / ~$6.00 / ~$4.40` with their source captions.
- **Target-store picker.** 5 selects (one per row), offering **all four**
  household stores (Aldi / Coles / IGA / Woolworths) rather than only stores
  already touching the line. Inherited defaults read correctly per row:
  `Coles (default)`, `Woolworths (default)`, `Any store`.
- **Log price.** Present and visible in the toolbar on the **shopping** face,
  **absent (0)** on a draft. (Note for future drivers: its accessible name is
  *"Log a price"* — the `aria-label` — not the visible label "Log price".)
- **Shop-mode line editor.** Sheet renders *Price per unit · Quantity · Bought
  from*, with **Bought from pre-filled from the resolved ladder** (Aldi). The
  quantity stepper round-trips: 1→2 saved and the row re-rendered `2× Olive Oil`;
  repeated at 375px (4→5, row `5× Olive Oil`) and survived a reload.
- **No horizontal overflow at 375px** with the new select on every row
  (`scrollWidth` 375 = viewport 375).
- **No 5xx** across the walk.

**Not verified — blocked, not skipped:** the `planned_store_id` **round trip**.
The scratch backend had been up since before the batch and Dora hard-codes
`is_reloader_enabled() → False`, so it was still serving pre-batch-3 code and
silently ignoring the new field; `preview_stop` and `kill` were both denied,
`preview_start` reuses the live process, and both scratch pairings were occupied
by parallel sessions. Checklist in `DORA_VERIFY.md`. The migration itself is
covered by three passing tests (single-head, upgrade-from-empty,
schema-matches-ORM), and the ladder ordering by a mutation-checked
`tests/test_store_ladder.py`.

**Picker shape + ordering (second follow-up, same session).** Verified in two
halves, because the scratch backend still could not be restarted:

- **Server sort, in-process against the real scratch DB** via
  `GetShoppingListsHandler` (not the stale running process): 29 lists, dates
  **strictly non-increasing**, drafts (28/08) on top, oldest done (24/05) at the
  bottom, `is_next_up` still on Saturday shop.
- **Client half**, driven with a Playwright route intercept that reverses the
  stale server's payload — faithful because that server sorts by exactly the same
  `(effective_date, created_at)` key. Rail renders 8 rows newest-first; the 5
  inline done lists are now the most *recent* five (25/08 → 14/08) rather than
  the oldest five; See-older still holds 21 and scrolls, newest-of-the-old first.
- **Layout:** "See older" sits **8px** under the last list row (was at the floor
  of a full-height column); rail box **505px** instead of `calc(100vh - 110px)`;
  no "Manage templates…" link; **0px** horizontal page overflow at 1280px and
  375px; mobile dropdown shows 8 lists + "See older (21)".

**Caught by looking, not by the counters:** removing the width-pinned
`q-virtual-scroll` broke name truncation — the rail's `overflow-x` *hard-clipped*
the names instead of ellipsising them, which every count and every "no overflow"
assertion still reported as fine. Measured chain at 1280px inside the 300px rail:
`q-item` root **433px**, name span **341px**, both `min-width: auto`. Fixed at
every link (root/section/label/span) and re-measured at 300px/208px. A
`min-width: 0` applied to only the middle of a flex chain does nothing.

**Spend bar — "No store set" slice (follow-up, same session).** Walked in
**Pesto, Pesto Dark and Cherry Cola Dark**, money on and off, with computed
styles and contrast ratios measured rather than eyeballed:

- **Width.** Money on: `70.76% / 22.24% / 7%` — the catch-all was `0%` before and
  absent from the bar. The two priced segments keep their true ratio (70.76/22.24
  = 3.18, matching $14.00/$4.40 = 3.18), so the floor costs proportionality
  nothing. Money off: `40% / 20% / 40%`, straight item-count share.
- **Colour, and why a colour alone wasn't enough.** `--border-strong` measures
  **3.55:1** against its neighbouring segment in Pesto light but **1.19:1** in
  Pesto Dark and **1.02:1** in Cherry Cola Dark — the same lightness as the
  segment beside it. Unfixable by choosing a different grey, since the competing
  fills include logo-derived brand colours. Resolved with a themed diagonal
  hatch; confirmed rendering in all three themes by screenshot (the contrast
  probe reads `background-color` only and cannot see a `background-image`, which
  is worth remembering — the numbers looked unchanged while the fix was working).
- A first attempt dimmed the segment to `opacity: .6` so store colours would
  still win the eye. That made it near-invisible in light themes against the
  bar's own `--surface-sunken` track — reintroducing the reported bug in a
  subtler form. Removed; noted in the stylesheet so it isn't retried.

**Gotcha worth keeping:** after mutating a module to prove a test is sensitive,
clear `__pycache__` before trusting the restored run. A stale `.pyc` kept the
mutated behaviour alive while `inspect.getsource` printed the corrected file,
which reads exactly like "my fix didn't work".

---

## Verified live — shopping-list feedback batch 2 (2026-08-28)

Same isolated scratch backend (:5171, `data/scratch-verify.db`), walked at
**1280px and 375px** with money on.

**Driving note worth keeping.** Another chat held 4 of the 5 dev-server slots, so
`dora-spa-5171` wouldn't start and the running SPA on :5174 targets the **:5170
dev backend**. Instead of taking a slot or going near the real DB, the driver sets
`localStorage['dora.backendBaseUrl'] = 'http://localhost:5171/api'` — the runtime
override `backendUrl.ts` reads per request — so one Playwright context talks to the
scratch backend while the other chat's SPA keeps its own target. Fresh context per
run; nothing persists. Reusable any time the box is busy.

- **Picker length.** 29 rows → **8** (2 drafts + 1 shopping + 5 most-recent done),
  with **See older (21)**. Verified on all three faces.
- **See older modal.** 21 rows; typing "Tuna" narrows to 4; `scrollHeight` 844 vs
  `clientHeight` 540 (desktop) / 487 (mobile) and scrolling reaches row 21 at both
  widths. Opening one navigates to it **and it stays in the picker** (1 active row)
  rather than the picker pointing at a list it won't show.
- **Mobile path to the modal.** Dropdown opens → 9 items (8 lists + "See older
  (21)") → tap opens the dialog. Verified separately because at 375px "See older"
  is a menu item, not a button.
- **Always visible.** `.sld-rail` present on the run face; **0** "Switch list"
  buttons anywhere; the dialog is deleted.
- **No kebabs.** 0 in the rail on all three faces. **0** occurrences of "Copy to
  new list" / "Copy unticked" anywhere on the page, including the Export menu.
- **Name once on mobile.** At 375px: `.sld-title` **hidden**, `.sld-rail`
  **hidden**, dropdown **visible**, and exactly **1** visible occurrence of the
  list name (inside the dropdown button). At 1280px the title and rail are both
  visible. Rename pencil resolves to exactly one visible button at each width.
- **Header, all three faces.** Draft → `5 items · Set shop day · Created
  28/08/2026`; Shopping → `3 items · Shop day: 26/08/2026 (overdue) · Created
  27/08/2026`; Done → `2 items · Completed 25/08/2026 · Created 24/08/2026`. The
  run-face branch needed a planned date forced onto the seeded list — the seed
  leaves it null, so that path would otherwise never have rendered.
- **TripCard.** Money-only card on the draft face (`Estimated cost | $18.40 |
  saving $0.80 | 2 from what you last paid`); **not rendered** on the shopping or
  receipt faces.
- **No 5xx** across the walk.

---

## Verified live — shopping-list feedback batch 1 (2026-08-28)

Driven with Playwright (the Browser pane reports a 0×0 viewport on this box and
can't read the tree) against the **isolated scratch instance** — `dora-verify-
backend-5171-linux` on :5171 with `data/scratch-verify.db`, SPA on :5174. The
:5170 dev backend was never touched. Walked at **1280px and 375px**, with money
both **off and on**. None of these reached `DORA_VERIFY.md` as open items:

- **Money gate on the draft price button.** Money off → `.sld-price-btn` count
  **0** across a 5-line draft; money on → **5**. Every other price surface was
  already gated; this one never was.
- **No ticking on a draft.** 0 row checkboxes on the plan face. `space`/`u`
  now no-op outside shop mode (they previously guarded only on `'done'`).
- **Ring → count.** Trip card reads `5 | items`, 0 `q-circular-progress` on the
  plan face.
- **Deletions.** 0 `swap_horiz` icons, 0 `place` pins, 0 Bulk-select button; row
  actions down to 1 per row (delete only).
- **Draft ordering.** "Order by" offers exactly `Store / Manual`; the run face
  still offers all four.
- **Picked section.** `Picked (2) · $33.50 in the trolley`, collapsed by default,
  expands to 2 struck-through rows. Tapping one **unticks it**: live rows 1 → 2,
  footer `2/3 → 1/3`, `Remaining $7.99 → $13.49`. Re-ticking restores it.
- **Shop-mode ring.** 52px with `2/3` inside it; the line beside it stopped
  repeating the count and reads "1 left to pick".
- **Finish dialog.** With 1 unticked line: no option pre-selected, CTA
  **disabled**, banner reads "…a finished list is a receipt, so it can't stay on
  it — or cancel and tick it off after all", options are move-existing /
  move-new / discard, and the cancel button reads **Go back**. Picking *Discard*
  enables the CTA and relabels it **Discard & finish**.
- **Discard round trip.** Clicked through: the unticked line is **gone from the
  DB**, the two ticked lines remain, list flipped to `done`, receipt reads
  "2 items bought".
- **Store colours (the reported "white").** All four seeded stores have
  `brand_colour = NULL` — the owner's exact scenario. Bar segments and chip dots
  now compute `rgb(66,121,143)` and `rgb(82,93,122)`; the old pale values were
  `#dde6e9`/`#dfe1e8`, i.e. white on a light page. The "No store set" segment
  stays `--surface-sunken` deliberately.
- **Money off, store card.** Title flips to "Where you'll shop" and the bar sizes
  by item count — clears the 2026-08-26 line, now deleted from `DORA_VERIFY.md`.
- **No 5xx** across dashboard / reports / preferences after the budget change.

Backed by `tests/test_budget_spend_excludes_unticked.py` — mutation-checked
(reverting the filter reports $95 against an expected $30).

---

## Verified live — stock-overview feedback batch (2026-08-21)

Walked in the Browser pane (`dora-verify-backend` + `dora-spa`, user `dora`),
measured with `javascript_tool` probes; these lines never reached
`DORA_VERIFY.md` as open items:

- **Dashed uncertainty marker.** Re-measured after the overlay implementation
  was reverted to the built-in border (owner's call): the marked buttons compute
  `border-top: 3px dashed color(srgb … / 0.65)` with `box-shadow: none` — so the
  dashes are thicker, their gaps widen with them, the pale
  `--surface-component` ring is gone, and no overlay elements remain in the DOM
  (2 marked rows, 0 `.stock-row__level-dashes`). Button still 32×32.
- **Essential stripe.** Stripe top/bottom now equal the row's own top/bottom
  (462.9/530.9 against the row's 462.9/530.9) and its left equals the row's
  left, width 7px — it was inset by the row's 1px border before, which is what
  left the corner showing.
- **Filter labels.** With a level selected the field is captioned **"Stock
  level"** and reads **"Out of Stock"**; empty it reads "Any level" under the
  same caption. Location (a `use-input` select, where `display-value` is dead)
  carries "Any location" as its input placeholder instead.
- **Filter widths.** 210 / 210 / 210 with Sort by at 250. Value spans carry
  Quasar's `ellipsis` with `overflow: hidden` + `white-space: nowrap`.
- **Attention rank, live.** `/api/stock-items` returns `attention_rank`;
  "Sourdough Bread" (essential, OUT) = 1 and "Load item 0028" (essential, LOW)
  = 3 — same kind, same severity, different urgency, which is precisely the
  distinction the old severity-only sort could not make.

Not verified here: both dialogs (Add stock item, Log a price) — a `q-dialog`
mounts in this pane but lays out at zero size, so field geometry can't be
measured; and Log a price needs the Money feature on, which this seed has off.
Both left on `DORA_VERIFY.md`.

## Verified live — "Needs check" chip retirement (2026-08-21)

Walked in the Browser pane (`dora-verify-backend` + `dora-spa`, user `dora`),
two lines deleted from `DORA_VERIFY.md`:

- **Quick-filter row is four chips.** `#/stock` → Filters → `.q-chip` reads
  `["Needs attention","Expiring soon","Essential","Open / in-use"]`. Proof the
  removal is real and not the `v-if`: `/api/health` reports
  `"stocktake": true`, and the toolbar still carries
  `Stocktake (6 due, 1 essential)` → `#/stocktake`.
- **Dead `?stocktake=1` bookmark is harmless.** `#/stock?stocktake=1` loads the
  unfiltered list, Filters button shows no count badge and no "Clear filters"
  button appears (active-filter count 0). No console errors beyond the known
  cross-origin 401 and my own probe 404s.

Left open (pane can't show them): the row's dashed needs-check marker
(virtualised rows don't paint here) and the Dora Score "Do a stocktake" action.

## Verified live — Stock-overview filter feedback (2026-08-16)

Four owner-reported items, all walked on a scratch install (own backend on :5185 with
its own SQLite + own CORS origin, SPA on :5188, both torn down after). No new
`DORA_VERIFY.md` lines were owed for these — only the cross-theme look call, which is
the one item that got added.

| Check | Measured |
|---|---|
| Filters + Clear icon-only on mobile | 375px, both buttons 57px wide, no label text, `aria-label` intact, the active-count badge still on Filters. Search input gained the freed width (206px). |
| Filter options scroll like the quick-filter chips | Input row: `scrollWidth 744 / clientWidth 311`, `overflow-x: auto`, `flex-wrap: nowrap`, height **42px = one line** (previously wrapped to three). |
| Space between the level picker and the essential stripe | **Mobile-only** — desktop was never the problem (owner correction). Phone left padding 8→12px, matching desktop; stripe→button gap 3px→8px at 375px, identical to desktop's 8px. Desktop CSS untouched. |
| Open/in-use + Essential too dark in dark mode | Active chip vs the sunken filter panel in pesto-dark: **2.80:1 → 8.48:1**. Across all five dark themes the indicator tone went **1.45–4.74:1 → 7.31–8.48:1** (cherry-cola-dark was the 1.45 — effectively invisible). |

Two things worth keeping:

- **The `--brand-secondary-strong` cascade was verified per theme, not assumed.** It's
  declared once on `:root` as `var(--brand-secondary)` and overridden only in the five
  dark blocks. Probing all ten themes confirmed each *light* theme resolves its own
  secondary (not Pesto's) — which works because `themeService` puts `data-theme` on
  `document.documentElement`, the same element `:root` matches, so the reference
  re-resolves per theme instead of freezing at the default.
- **A red herring: `--q-secondary` reads `#006a80` on `documentElement` even in
  pesto-dark.** That is not a theme-sync bug — Quasar's `setCssVar` writes to
  `document.body` by default, so the root still carries the SCSS-baked value. Read
  Quasar palette vars off an element inside `<body>`, or you'll chase a ghost.

**Harness notes (additive to the rAF recipe above).** Screenshots time out on this page
— every measurement here is `getBoundingClientRect` / `getComputedStyle` instead. Two
new gotchas: (1) `q-virtual-scroll` renders **zero rows** in the hidden pane, so filter
the list under `VIRTUAL_SCROLL_THRESHOLD` (50) to reach the plain `ListTransition` path
before measuring a row; (2) `$q.screen` does **not** react to `resize_window` — it stays
at whatever width the page loaded with, so `compactToolbar` reads false and every
mobile-only branch renders desktop. **Reload after resizing**, then assert
`$q.screen.width` before trusting anything. Synthetic `form_input`/click on the login
form also didn't reach Vue's model; `fetch('/api/auth/login', {credentials:'include'})`
then a reload works.

---

## Verified + deleted — Location field overflow, stock-item detail (2026-08-16)

**Item deleted from `DORA_VERIFY.md`:** "Location field on a phone — confirm the page
no longer scrolls sideways."

**Why it's here at all:** the fix shipped earlier the same day was **wrong and
untested** — `min-width: 0` on the item sections, which Quasar already sets, so the
rule was a no-op. The owner reported it still broken. This is the record of the second,
measured fix.

**Method:** scratch install stood up for the purpose (own backend on 5175, own SQLite,
own CORS origin, `VITE_API_BASE_URL` pointed at it) so the other session's server and DB
were untouched; all of it removed afterwards, including the temporary `launch.json`
entries. Measured with `getBoundingClientRect` per row, not by eye.

**Evidence (Location row, viewport 375px):**

| | before | after |
|---|---|---|
| `.q-field` width | 236px | 136px (= its section) |
| field right edge | 428 | 327 |
| dropdown arrow right edge | 402 | 327 (aligned with every other row) |
| row `scrollWidth - clientWidth` | 85px | 0 |

Also clean at **320px** (field right edge 272, page `scrollWidth` == viewport). Stock
group had the same defect at 23px and is fixed by the same rule. The only elements
still exceeding the viewport at 320px are `.dora-tabs__tab`, inside a container with
`overflow-x: auto` — scrollable by design, not a regression.

**Second miss — scope (2026-08-16, same day).** The measured fix above was correct but
scoped to `.dora-inline-edit` on one page, and the owner reported it *still* broken.
`use-input` is what makes QSelect render a real `<input>`, and **13 files use it** —
including `CreateStockItemDialog`, `BulkMoveLocationDialog` and the stock filters, i.e.
two more location pickers. The cap now lives in `css/app.scss` on
`.q-select--with-input`. A/B'd on `AdminSystemRegionSettings` at 320px (a `use-input`
select outside any inline-edit list): rule off → 275px field overflowing its 284px
parent; rule on → 272px, flush. **Lesson: fix where the defect lives, not where the
report came from.**

**Root cause (recorded so it isn't re-diagnosed):** `q-item-section` is a *column*
flex container; `.q-field` inside it has `max-width: none` and so sizes to its own
content, and the Location row is the only one rendering a real `<input>` (~180px
intrinsic, independent of content — which is why clearing the locations list changed
nothing). Quasar's `max-width: 100%` sits on `.q-field__control` and resolves against
the already-oversized `.q-field`, so the cap has to go on `.q-field`.

**Harness note:** the Browser pane's document is `document.hidden`, so `rAF` never
fires and this page's `FadeTransition mode="out-in"` never settles — it sits on the
loading skeleton forever and no CSS injection helps. Measuring required temporarily
swapping the transition for a plain `<div>`, then restoring it (confirmed via
`git diff`).

---

## The numbers (2026-07-16 snapshot)

| Slice | Lines | Items | A | V | H | Stale-suspect |
|---|---|---|---|---|---|---|
| Top block (recent surfaces) | 11–129 | 80 | 65 | 0 | 15 | 1 |
| Cookbook & recipes + Cook mode | 130–372 | 191 | 182 | 4 | 5 | 8 |
| Meal plans + Shopping lists | 373–665 | 227 | 217 | 7 | 3 | 9 |
| Stock | 666–1012 | 245 | 234 | 11 | 0 | 8 |
| Dashboard + Alerts + Settings | 1013–1378 | 267 | 260 | 6 | 1 | 17 |
| Onboarding + Products + Build + Operator | 1379–1636 | 164 | 143 | 11 | 10 | 15 |
| Cross-cutting | 1637–1948 | 232 | 199 | 27 | 6 | 3 |
| **Total** | | **1,406** | **1,300 (92%)** | **66** | **40** | **61** |

Owner's realistic residual workload: read the evidence reports, walk ~66 eyeball
items from pre-staged screenshots/walkthroughs, run 2–3 device packs (~40 items,
of which 7 are blocked on having a Mac), and decide the 61 stale recommendations.

---

## Batch plan (verify sessions, in order)

Sized so one batch ≈ one session. Order: pilot first, then newest/highest-risk
surfaces, then the long tail, then env-gated batches.

| # | Batch | Sections (snapshot lines) | Items | Status |
|---|---|---|---|---|
| 0 | **Pilot** — Password policy + SettingsFileDrop + BuyVerdictCard + Runtime backend URL | 71–99, 111–115, 82–89 | 22 | ✅ **COMPLETE 07-17** (Password policy 8/8; SettingsFileDrop 5/5; BuyVerdictCard 6/6 — FU-572 found+fixed mid-walk; Runtime URL walked — L113 recovery clause FAILS → FU-574 open, remove-toast over-count → FU-573) |
| 1 | Top block remainder — Onboarding story, Dora bubble, Currency & locale, Stores logo, PWA-dev-checkable parts | 11–49, 63–70 | ~40 | 🟡 (2026-07-23: **Dora bubble Basic-mode add-to-list (FU-429) fully verified live** — drove the DoraChat textarea (v-model input IS synthetically drivable, unlike the one-way `:model-value` q-inputs elsewhere); all six paths confirmed against server list state (happy/multi/not-found/ambiguous/no-primary/bare-add) + the parser is already Vitest-pinned; section deleted bar the AI-mode-ON path. **Currency & locale (FU-043)** — page+inputs+preview+button, EUR/de-DE→"1.234,56 €" and reset→"$12.50" proven live, defaults confirmed; **found + fixed [[FU-600]]** (preview showed AUD defaults on cold load — page never triggered the money-policy load; fixed + re-verified after `quasar build -m spa`); **item 8 resolved** (removed the retired `/product-search` page-help that name-dropped Coles/Woolies/IGA/Aldi — dead code); residuals are q-input-synthetic-gated (keystroke save/toast, inline validation) + speech-locale device. **Stores logo (FU-335)** — two-button Add↔Change (camera)/(file) + swatch + Remove structure source-confirmed (shared `ImageSourcePicker`); dialog body won't paint in the hidden pane + file-pick/PDF/camera are device → owner-walk. **Onboarding story** — V-pack (visual scenes/animation/reduced-motion/timing, needs an unonboarded user) → owner-walk, not driven. **Dora bubble FU-360 leftovers cleared too:** Hide-Dora (FU-360.6, toggle+toast+reload-persist+restore), mode-slider disabled/no-LLM state (FU-360.3, disabled+dimmed+not-allowed+no-op), text-size rem-scaling (FU-360.1, md→xl proportional 1.394×) — all deleted; **found [[FU-601]]** (settings save-failure toasts grammatically broken, copied across 6 settings pages, R-003 smell). Remaining: onboarding V-pack, stores-dialog interactions, AI-mode-ON assistant + mode-slider enabled path + greeting (2-users), cookable chip (rotation), hover-flash (visual), PWA-dev-mode parts.) |
| 2 | Stock A — recent fixes + stocktake redesign (668–814) | 668–814 | ~120 | 🟡 (2026-07-17: FU-508+FU-507 codified green; 5 fix-pins confirmed backend-tested→delete; scan-mode→device-pack; **stocktake runner Chunk 2 fully codified — all 5 verbs + help + add-to-list green**; Chunk 3 settings dials + **"Needs check" Overview filter + alert-threshold removal codified green**; tail = non-admin banner + auto→runner cadence effect) |
| 3 | Stock B — remainder (816–1009) | 816–1009 | ~115 | ➗ (2026-07-17: **FU-226 waste section fully codified green** — `bulk-waste.spec.ts`, 6 tests; L830/831/833/834/835/836 owner-deletable. **Auto-add-on-low first slice codified** — `auto-add-on-low.spec.ts`, 2 tests: settings dial loads/saves/persists + `all`-mode Low-drop toast + `auto: low stock` chip; L843/844/847/849 owner-deletable; server-branching negatives → [[FU-577]]. 2026-07-18: **P8-05 buy-verdict section fully codified** — engine already unit-pinned; 3 new e2e tests (flag off/on, low-confidence silence, out-of-stock Buy walk) + new `useBuyVerdict.spec.ts` client-cache spec; L734–744 deleted, one Wait-badge visual stays; found [[FU-580]] (flag flip needs a reload). **History tab both sections codified** — new backend `test_stock_item_history_feeds.py` (7 tests: Bought/Cooked feed contracts) + new `history-tab.spec.ts` (4 tests: cap footer, mixed feed, meals badge, expiry-trail render); old L758–783 deleted, one colours/singular-footer visual stays. **FU-109 deep-link + no-dim codified** — new `recipe-deeplink.spec.ts` (4 tests), both sections deleted; found+fixed 2 real bugs (phantom chip on dead recipe id; empty-state Clear leaving `?recipe=`) + fixed FU-579's bulk-waste half (was hard-failing `quasar build`). **Stock pickers behavioural halves codified** — new `stock-pickers.spec.ts` (2 tests: detail Level round-trip + console-clean filter clear); section down to one dot-styling visual. **C-1b triaged** (pinned+stale deleted; compressed to walks + 2 codify-next candidates) and **Chunks 2/4 codified** — new `useStockItemActionsPushExpiry.spec.ts` (8 Vitest: FU-123 push matrix) + Chunk-2 stock.spec describe (panel persistence, retired-filter guard). **C-1b.4 codified** — new `detail-recipes-tab.spec.ts` (3 tests: favourite toggle, Add-all-to-list, substitutes Remove/no-Swap). **C-1b.3 codified** — new `detail-products-tab.spec.ts` (cheapest highlight, empty CTA); found [[FU-581]] (three surfaces route to the FU-186-retired `/product-search` → 404). Remaining: visual walks + viewport-gated bullets (Chunk 5, mobile panel, products-OFF half) + Offers sidecar line — **agent-verifiable work done 2026-07-18; flipped ➗, remainder is owner-walk only**) |
| 4 | Cookbook A — filters, free-text, importer, DnD (132–195) | 132–195 | ~53 | 🟡 (2026-07-20: **server-ownable slices codified/verified** — cookability+expiring filters (`test_recipe_filters.py` 14 + `test_recipe_router.py` Cookable/MaxMissing/ExpiringWithinDays), tri-state cookability (`test_recipe_cookability.py`), import routes 404/content-only (`test_recipe_import_routes.py`), and bulk-linker grouping/collapse/sort/dedupe (`test_unlinked_ingredients.py`) all confirmed green → delete-on-passed. **2 gap-fills added:** `create_recipe__NameOnly__CreatesFreeformEmptyStub` (L128 stub defaults) + `taste_video_carousel_cruft_stripped` (L148 taste2 Coles/video cruft — the loose corpus test can't catch it). 100 tests green. **Remaining owner-walk/codify-next:** editor free-text picker UI, stub-creator modal (4 fields/buttons/nav), importer paste/preview flow, **Create-new bulk action (L137 — client orchestration over POST /stock-items + bulk-link)**, ingredient DnD (FU-118/161 — needs a component/e2e harness), PWA share-target (Android device-pack). **Later 2 (same day):** the **Link bulk endpoint (L136) codified → found + fixed REAL BUG FU-588** — new `test_unlinked_ingredients_bulk_link.py` (4 tests: cross-recipe link + cookability re-derive, only-matching-group, unknown-item 422, empty-key 400) caught that `GetUnlinkedIngredientsHandler` read the recipe FK off the un-prefixed `recipe_id` (ORM binds `_recipe_id`), so every bulk-linker group showed "Used in 0 recipes"; fixed (R-032) + the false-confidence unit stub corrected to `_recipe_id`. Backend **1543 passed**.) |
| 5 | Cookbook B — chunk sections + image-steps (197–321) | 197–321 | ~120 | 🟡 (2026-07-20: **Chunk-8 recipe versions codified → 2 REAL BUGS found + fixed** — new `test_new_recipe_version_numbering.py` (4 tests: numbering, inheritance [linked/unlinked/optional ingredients + scalars + cuisine/category], independence) caught **FU-589** (numbering skipped v2 → v1,v3,v4 from a pre-flush sibling count) and **FU-590** (production-severity: new-version of ANY recipe with ingredients 500'd — autoflush of unparented clones + R-032 noload clone silently unlinked linked ingredients → anchor CHECK fail). Both fixed; Chunk-8 numbering/group-alloc/inheritance/independence delete-on-passed. Full backend **1547 passed**. **Remaining Batch-5 (untouched):** Chunks 3/4/9 cards+cost+nutrition (cost math, kcal wire), Chunk 5 images+tools, Chunk 2 tag taxonomy, image-steps mode, tools/steps/tags/collection/image version inheritance — mostly UI. **Later 2 (same day): cost math (Chunk 9) + step validation (Chunk 6) codified clean** — `test_recipe_router.py` +5 tests: `estimated_cost = Σ qty × offer.price_now/size_value` over the real StockItemProduct→Product→ProductOffer join (guards the FU-463 SQLite-uuid regression), partial-coverage priced/total counts, None-when-unpriced; whitespace-step→400 domain message + empty-step→422. No bugs. Full backend **1552 passed**. Batch-5 remainder now pure UI [cards/tags/images/nutrition-flag matrix/kcal wire].) |
| 6 | Cook mode (327–369) | 327–369 | ~36 | 🟡 (2026-07-20: **rescale (FU-101) + personal-notes (FU-432) codified** — `scaleQuantity.spec.ts` grew a Chunk-6 checklist describe block [+6 → 23 tests: up/down 1.5×/0.5×, ¾/1½ snap, egg 0.75→1 floor, 7.5g→7½] and `test_recipe_notes.py` gained the new-version note carry-over [+1 test]; DORA_VERIFY pure-math bullets + L305 deleted, survivors reworded to component-clamp/UI-render owner-walks. **Codify-next (needs a cook-mode e2e/component harness, none exists yet):** Chunks 1–3 finish-flow dialog [override-beats-action, Promise.allSettled fail-soft, click-out cancel, session-swap], voice/timer [+ audio=device-pack], Chunk 5 highlight/tools/hints [mostly V-pack]. Input clamp/default/session-only [L333/340/341/342] also codify-next. **Later 2 (same day): finish-flow e2e ATTEMPTED, DEFERRED as flaky** — `cook-mode-finish` drives the real loop (Finish → Down-one/Out/Unchanged → server-verified level drops + meals toast + Cancel-fires-nothing) and passes 4/4 in a FRESH env, but `--repeat-each=2` → ~1/3 (cook-mode loads the stock store async → a fast Finish click races it → decrement no-ops). Deactivated to `cook-mode-finish.wip.ts` (off the `*.spec.ts` glob) as a driver blueprint; DORA_VERIFY bullets reverted to owner-walk. **Deeper blocker: the full e2e suite doesn't run green in one long single-worker pass — 14 failures from env degradation on ~13 unrelated specs → [[FU-591]].** The e2e infra must be stabilised (parallelism/sharding + quiet the debug backend) before it's a reliable codification vehicle.) |
| 7 | Meal plans (375–476) | 375–476 | ~83 | 🟡 (2026-07-22: **reconcile section cleared 14/15 + 3 adjacent sections** — full runner walk (all 5 verbs, both auto-drain modes, pool math server-verified at every step), threshold alert+suggestion, empty state, help dialog, XL type-scale, 3 theme families, admin settings page; **found + fixed a real bug** (recap **Done** → `/dashboard` 404 → now `/`); **2 findings opened** ([[FU-594]] skip reverses the pool drain vs. its own docstring, [[FU-593]] reconcile suggestion crowded out by the 8-item cap). Also cleared: Templates drawer (FU-308) **7/7**, Show-all-slots (FU-306) 5/6, useListState (FU-354/355) 4/8, C-2.I trays partial. **Remaining Batch-7:** budget-defense swaps (money-gated → blocked on [[FU-592]]), meal reconcile non-admin banner (needs a 2nd account), unlinked-ingredient dialog, meals-per-week client clamp, Print (mobile/print-view), R-Phase palette + DnD, C-2 tap-add/drag/calendar/templates-apply/sequential-builder. **Later 2 (same day):** meals-per-week **5/5** (deleted), Print 3/4, useListState remainder 3/4, and most of C-2/R-Phase walked (tap-add slot correctness F35, ± stepper, past-day inertness, implicit create, Clear-week, full calendar incl. `?monday=` across reload, sidebar list-status, 3-step builder end-to-end). **Found [[FU-595]] — production severity:** a past-day entry with `consumed_at IS NULL` makes every add 400 and hard-crash the planner; reachable via auto-drain-OFF and via reconcile → "Didn't cook". **Fixed:** print-view titled every nameless planner week "None" → now `Week of <date>`, pinned by a new backend test (the first attempt at that test was vacuous — seed-conditional — and was rewritten to create the nameless plan itself). **[[FU-596]]** opened: the builder files every meal under Breakfast. **Survivors:** drag-and-drop, C-2.F/G templates apply/recurring, carousel arrows/keys, off-vocab row, unlinked-ingredient dialog, budget swaps ([[FU-592]]). **2026-07-23 (later):** budget swaps cleared (money sweep — FU-592). **Templates save/apply/manage cleared** — dialog (Save/Apply-recurring/Manage-sets/empty-state), Save→toast+server-created+listed, Apply→"Added 6 meals" fork onto focused empty week, `/meal-plans/templates` = rotating-sets manager (template rename/delete inline in dialog). Survivors now: apply-recurring + set CRUD, confirm-before-replace, edit/delete-leaves-fork, drag-and-drop, off-vocab, unlinked-ingredient dialog, carousel arrows (calendar is the nav).) |
| 8 | Shopping lists A — recent (482–563) | 482–563 | ~69 | 🟡 (2026-07-20: **display_name self-labelling (FU-165 L509) codified clean** — `test_shopping_list_planned_shop_date.py` +1 test: name→planned-date→re-label→created-fallback ladder via server-owned `display_name` (R-003). Also confirmed already backend-tested (delete-on-pass for the walk): receipts (FU-334 `test_shopping_list_attachments.py`, 8 tests), substitute-swap gating (`has_substitutes`), trim-to-budget (FU-448). Full backend **1558 passed**. Remaining Batch-8: quick-add toast/always-ask UI (FU-316; resolver exercised via auto-add), receipt mobile-camera/desktop-picker (device-pack), image-source picker sweep (UI). **Later (2026-07-24, money seed): put-away dialog (FU-452) cleared** — drove the done "Last week" list (Pantry/Freezer/no-location): toolbar gating (present on done, absent on draft), location-grouped cards + ticked-only, group-tick collapse + green chip both ways, (No location) pinned-bottom/no-tick/Assign, Assign mini-dialog Cancel-no-op + Save endpoint moving the item to Fridge + dropping the (No location) group, ephemeral reset on close/reopen. Two edge states (all-unsorted, zero-ticked banner) source-confirmed (seed done lists can't be un-ticked). No bugs; item reverted. Section deleted. **Later 2 (2026-07-24): trim-to-budget (FU-448) reachable UI cleared** — contrived a $20 budget + $18 out-of-stock list → banner copy ("Projected $18 · budget remaining $7.60 — trim $10.40"), verdict=buy-on-out never-cut, "everything safe" fallback, and Dismiss all verified live; happy path (Keep/Trim-to-fit/Deferred/Add-back) documented as genuinely owner-walk — no API can create a cuttable line (added_via is extra=forbid/manual-only; out=buy never-cut; deferred only set by trim-apply; DB is Postgres), frontend wiring source-confirmed + apply backend-pinned. Contrivance torn down. No bugs. **Later 3 (2026-07-24): quick-add toast + "always ask" (FU-316)** — resolver verified live (`/primary/lines`: 2 drafts→ambiguous+candidates, hint→added, repeat→already_on_list, done-hint→422); client wiring (named-list toasts, `$q.dialog` picker + two copy variants, sessionStorage remember/clear, bulk-once, Preferences toggle toasts) source-confirmed; the pure cart-button→picker interaction not driven (stock-row cart doesn't paint in hidden pane) → one optional owner-eyeball bullet left. No bugs; resolver test data reverted. **Later 4 (2026-07-24): 3 cross-cutting sweeps** — (a) **L160 dark-mode search-bar contrast** CLEAN (Cookbook/Stock/My-Products/Price-History + Dora chat all white-on-dark, Δ≈220+); (b) **R-024 image-source-picker** verified (all surfaces on the shared `ImageSourcePicker`→`processImageFile`; avatar live shows desktop "Add (file)"/camera-hidden) + 2 stale checklist items corrected → **[[FU-607]]** (stock-item image-edit surface gone; docstring drift) and store-logo-migrated-off-q-file; (c) **FU-334 receipts** section-gating live (draft hides / shopping+done show / empty-state / desktop "Choose receipt", camera hidden). File-pick/camera/lightbox stay device. **Later 5 (2026-07-24): FU-165 Shopping-list UX v2** — rail+next-up, doughnut+totals, group-by (Location regroups), bulk-select, Print all verified live + deleted; residuals = mobile dropdown/shop-day tones/finish-review flow/row actions/drag-reorder/dashboard-add. No bug. **Later 6 (2026-07-24):** Add-item dialog (fields/no-Expiry, blank-name reject, trim/case dedup), **FU-316 quick-add fully driven end-to-end** (picker→pick→named toast→2nd-add-no-picker; section deleted), Stock Overview Chunk 2 (toolbar/bulk-flip/footer order) + Chunk 4 (no-expiry picker, expiry menu +1/+7/+14/Clear) — all verified + trimmed. No bug. **Later 7:** History tab (Opened entry + expiry trail render), **FU-602 confirmed absent** (no Deal-alerts control in Notifications, money on — finding promoted), Data-pages structure (Import/Backup render, no regression; flows stay device), Help "Add a stock item" copy matches dialog (deleted). Note: agent-drivable pile thinning — remainder skews visual/device/viewport/fresh-install/synthetic-input.) |
| 9 | Shopping lists B — cart button + P6-01 chunks (565–662) | 565–662 | ~75 | 🟡 (2026-07-20: **Cart Button Chunk 3 rules 1–3 (FU-132) codified clean** — new `test_shopping_list_product_lines.py` (5 tests): product-only line create + no-anchor→422 (checklist guessed 400; 422 is correct for the domain rule), Rule-2 orphan upgrade [convert-in-place + fold-into-existing], Rule-3 delete-line cascade to the nested product line. No bugs. Full backend **1557 passed**. Also confirmed already-backend-tested (delete-on-pass candidates for the walk): `has_substitutes` (FU-407 `test_line_has_substitutes.py`), trim-to-budget (FU-448 `test_trim_to_budget.py`), `linked_product_count` (FU-130 `test_stock_item_router.py`). Remaining Batch-9: cart-button UI (Chunk 2/3-UI/4 modals), by-stock-item remove variant, migration/TS checks, snapshot-at-add UI. **Later (2026-07-23, money seed):** Cart Button **C2 fully** (2+→QuickAddSheet one-surface, 0/1 silent, toggle-remove, lpc shape, 2026-06-14 repro gone), **C3-UI** product-only line (tint + product chip, `product_id`/null), **C4** Axis-B generate picker (cancel/merge/create-new "Meals: …"); [[FU-603]] tooltip-vs-target. Survivors: bulk toast, rule-2/4 nesting, C4 0/1-draft + nothing_to_add.) |
| 10 | Dashboard (1015–1108) | 1015–1108 | ~75 | 🟡 (2026-07-18: **Draft-my-shop (FU-351) codified** — new backend `test_auto_generate_draft_shop.py` (no-phantom-list defer + explicit name) + new `dashboard-draft-shop.spec.ts` (happy path toast→navigate→chips; Cards-menu toggle); section down to empty-case/error/consumed walk bullets. Rest of batch untriaged) |
| 11 | Alerts (1114–1157) | 1114–1157 | ~34 | 🟡 (2026-07-22: **opened and largely cleared** — bell badge == actionable count (tier-verified); snooze persists server-side + correctly kind-scoped; dismiss hides on page/peek/dashboard; **C-9.2** threshold round-trip 7→2→7 (expiring_soon 13→2, badge follows) + disable-a-kind + demote/promote with exact accounting (actionable 34↔23, FYI 18↔29) and clean restore; **C-9.3** hub + slim peek + History-with-names; **C-9.4** BOTH nudges end-to-end (`no_planned_meals` and `shopping_day` show → deep-link → clear); **C-9.6** timeline (dots, out-of-window 0.35, today ringed, click-expand, all 3 link targets); reconcile-overdue row (FU-357) renders + navigates, no ErrorBoundary; SMTP/VAPID off-gating + vapid-key 404. **Fixed:** History labelled `out_of_stock` as "out of_stock" (hand-rolled `replace('_',' ')` swaps only the first underscore) → now reads the shared kind meta via a new `kindLabel`; 3 Vitest tests, 411 green. **Findings:** [[FU-597]] (page only refetches when the store is empty → stale feed all session), [[FU-598]] (`--brand-primary` == `--semantic-positive` in Pesto, so the timeline's shopping and meal dots are the same colour). **Survivors:** SMTP-send/VAPID-push/multi-device env packs, dark-mode sweep, admin threshold UI-typing (Quasar synthetic-input limit). **Later (2026-07-23, money seed): C-9.5 price watch cleared** — empty-state; armed (via API — the arm q-input didn't render in-pane)→panel lists product·merchant·"notify below $2.50"; View→explorer deep-link; Remove→gone+toast; hidden when INSTALL money off. [[FU-604]] (panel gates on install money, not per-user opt-out). Residuals: last-alerted timestamp (needs a fired watch), arm-UI drive.) |
| 12 | Settings A — data/admin pages (1163–1283) | 1163–1283 | ~86 | 🟡 (2026-07-20: **Users admin add/delete behaviour (FU-461) codified clean** — new `test_users_admin.py` (7 tests): create→200+one-time-pw+listed, taken-username/taken-email/malformed-email→422, self-delete→403, delete-another→204+gone, unknown→404. No bugs. Also confirmed already backend-tested (delete-on-pass for the walk): SMTP/VAPID secrets never leak in `/app-settings` (`test_app_settings_router.py SecretsNeverRideTheDto` + `test_bucket_c_secrets.py`), admin-gate on data endpoints (`test_route_auth_enforcement.py`), user PATCH guards + last-admin demotion (`test_patch_semantics.py`). Full backend **1565 passed**. Remaining Batch-12: data-page UI revamps (import/backup drag-drop), backup-library UI, image-compression settings, template download — mostly UI/admin-walk + a couple of file-op device checks.) |
| 13 | Settings B — account/assistant/misc (1285–1375) | 1285–1375 | ~72 | 🟡 (2026-07-22: **opened** — **Account + CSRF (FU-197) 8/11**: cookie `Path=/; SameSite=Lax`, non-HttpOnly by design; `PATCH /auth/me {email}` → 400 `extra_forbidden`; no-header mutation → 403 **and** with-header → 200 (proved both directions from a cold curl jar); cold login exempt → 200; instrumented fetch+XHR over 4 real mutations — all carried `X-CSRF-Token` matching the cookie; email-change UI enable-gate + wrong/right-password toasts + address-unchanged; both audit events with correct severities. **Assistant (FU-153)**: `has_llm_api_key` with no plaintext leak, cross-field 422, health tracks `master_llm_enabled`, hygiene grep clean, kill-switch driven both ways (banner + force-disabled per-user toggle). **FU-285** both copy items confirmed at source. **Finding [[FU-599]]**: explicit `audit_emit` handlers ALSO get an auto-audit row → security actions logged twice under two naming conventions; `_NO_AUDIT_ENDPOINTS` only covers login/logout. Not fixed — suppressing a row whose explicit emit is thinner would lose audit coverage. **Survivors:** SMTP inbox legs, paid-provider keys, per-user isolation, API-access page, profile-picture upload.) |
| 14 | Onboarding (1381–1471, **after stale cleanup**) + Products (1477–1511) | 1381–1511 | ~66 | 🟡 (2026-07-20: **Products sub-slices delete-on-passed** (no new tests — already backend-pinned, confirmed green in the 1565-pass run): PreferredBuy CRUD/sort/scope + cascade (FU-211, `test_preferred_buys.py` + `test_delete_integrity.py`) — and **corrected a stale bullet**: FU-211 "reorder (up-down)" was retired by FU-225, SPA sorts alphabetically now; price observations log→unit_cost/remove (FU-213, `test_price_observations.py`). Money-off gating + detail renders stay owner-walk. **Remaining Batch-14:** onboarding wizard walk (persona/seed/demo-toggle steps — mostly UI + integration walk), My Products UI (FU-214/208), assistant expiring-window (FU-187 — assistant path). Onboarding not yet triaged. **Later (2026-07-24, money seed): My Products + Price History cleared** — mark-inactive no 422 (L193), link chip/inactive/soft-delete styling+semantics (L195/L198/L197), FU-208 Link… opens in place + round-trips (no bounce), Price-History card/notify/deal-chip/graph-edge/theme-aware-tooltip (L219–L225); **found + fixed a real reactivity bug [[FU-605]]** — interactive product picking never refetched the series (in-place mutation under a shallow watch); reassign fix, verified live add/remove after `-m spa` rebuild. **[[FU-606]]** opened (L205/L206 stock-aware bulk variants → recommend generic suffices/won't-do). Survivor: L160 dark-mode search-bar sweep. Remaining Batch-14: onboarding wizard walk, assistant expiring-window (FU-187).) |
| 15 | Cross-cutting A (1639–1780) | 1639–1780 | ~100 | 🟡 (2026-07-20: **security response headers (FU-459) codified clean** — new `test_security_headers.py` (3 tests): all four headers (nosniff / X-Frame-Options DENY / Referrer-Policy / CSP with default-src/frame-ancestors/img-src/base-uri/form-action) present on a 200, a 404, and a domain-error response. Was completely untested. No bugs. Full backend **1568 passed**. Remaining Cross-cutting A is overwhelmingly V-pack (text-scale, base-component sweep, C-19 auth-shell visuals, help chips, filters alignment) + device (iOS audio) + the support-channel dormant/configured walk — mostly owner eyeball / device-pack.) |
| 16 | Cross-cutting B (1782–1945) | 1782–1945 | ~95 | 🟡 (2026-07-23: **opened, agent-verifiable items cleared.** **P8-01 rename** — zero "Discount Dora" in FE+BE source or DOM, tab titles "\| Dashy Dora", mascot alt, About, version replies source-confirmed. **D.O.R.A. bot rename** — chat-header label live + acronym/Help/`/help/dora` copy source-confirmed. **Route retirements** — `/data/barcodes`(+`?action=scan`)→qr-labels verified; `/data/export`+`/data`→`/settings/admin/data/backup` (checklist's "→404/cards" is **stale**, superseded by FU-341 relocation — clean redirect, no dead-end). **Health flags** — all present + match the Features panel. **R-016 lazy hydration** — XHR-instrumented: stock-items + recipe-list + all vocab/meal-slot stores fire once, 0 on revisit (the recipe "+1" was `/api/recipes/tags`, per-mount disclaimer). **Feature-flag panel (FU-110)** — 7 toggles (grown from 5) render w/ captions, states exactly match `/api/health`. **formatQuantity** unit-pinned; **unsaved-guard** observed live prior (Batch 13). **Deferred to 2nd pass:** C-cross money/nutrition per-user opt-ins (FU-111/112 — money/nutrition OFF, blocked on [[FU-592]]), image opt-in, DnD-affordance parity (drag automation), settings-shell scroll / mobile-header / menu-indicator / header-rings / reduced-motion (visual/viewport), error-handling rollout (needs induced errors), nav-state filter-survives-back, Chunks 3–5 render. **2nd pass 2026-07-23:** built [[FU-592]] (`DORA_SEED_MONEY_ON` knob, now RESOLVED) → **money/nutrition UI cleared** (cost card "$6.96 3/4 priced", kcal input, nutrition card, Kcal sort/filter, budget card — also unblocks money-gated items in Batches 5/7/9/11); **DnD class parity verified** (shopping lines + recipe ingredients both `.dora-dnd-row`/`.dora-dnd-handle`, old classes gone — drag interaction owner-walk); **header peer buttons** (Help/avatar nav, no chevron) + **settings-shell window-no-scroll** verified. Owner-walk left: mobile-header viewport, menu-indicator colour, ring animations, reduced-motion, drag interaction.) |
| 17 | **Env-gated: built-PWA mode** — PWA install/offline (100–110), share-target dev-checkable parts, manifest checks | various | ~10 | ⚪ |
| 18 | **Env-gated: Docker/WSL** — gunicorn (1593), voice bundling (1554–1570), demo mode (1619), secure-cookies HTTPS leg (1632), companion round-trip (1616) | 1554–1633 | ~25 | ⚪ |
| 19 | **Env-gated: Postgres leg** — alembic-on-PG halves of every migration item (compose.dev PG; `DORA_TEST_DB=postgres`) | scattered | ~12 | ⚪ |
| 20 | **Operator migrations on populated DB** — FU-563/564/565 (1576–1591), Windows desktop build (1517–1528), fresh-install boots (1542–1552, 1613) | 1517–1614 | ~26 | ⚪ |

### Close-out rule — every batch, every check gets a disposition (REVISED 2026-07-20)

*(Superseded the 2026-07-17 "codify → Playwright spec" rule per the stance-change
banner at the top of this file.)* The durable artifact is **NOT** a big Playwright
suite. Verification is manual-first; automated tests are lean and low-churn. On
closing a batch, classify each check:

1. **`verified-once → delete`** — the DEFAULT. One-time confirmation by driving
   the running app (agent or owner): copy, layout, a flow works, a gate holds,
   subjective calls, a migration ran. Verify live, delete the line from
   DORA_VERIFY, record the evidence in the worklog/triage. **No test written.**
2. **`codify (RARELY) → backend/Vitest`** — ONLY when the behaviour is a
   **stable, low-churn contract** that's expensive to re-check by hand (e.g. a
   server truth-table, a pure calc, a security invariant) AND unlikely to change
   as features evolve. Prefer backend/Vitest (fast, reliable). **Do NOT write
   feature-flow Playwright specs** — they churn and were retired (FU-591). If in
   doubt, do a manual once-off check instead.
3. **`env-gated → device pack`** — hardware/host-bound checks; stay manual.

A real bug found while verifying still gets a pinned regression test **when it's
a low-churn contract** (the backend bug-pins FU-588/589/590 are the reference
shape) — but a flaky/UI-churn pin is worse than none.

**Batch 0 retro-codified (2026-07-17):** password-policy (5 specs, FU-442 +
FU-568 pins), uploads/FileDrop (2 specs, FU-571 + FU-545 pins), buy-verdict
(4 specs, FU-454 + FU-572 pins), plus the pre-existing login/smoke layer
hardened (hash-mode routes now actually load; per-route title asserted; e2e
backend isolated to :5171 with the QA-fixture seed).
**Suite GREEN 2026-07-17: 19/19 (~2.6 min), Vitest 387/387, vue-tsc clean.**
Two spec-side fixes landed getting there: `/shopping-lists` returns a bare
summary array (not `{items}`), and a same-document hash-only `page.goto`
(dashboard → detail) doesn't reliably drive vue-router — engineer state via
`page.request` first, then do ONE full-document goto to the target route
(pattern now in buy-verdict.spec.ts). Watch item: the meal-plans smoke test
flaked once in a full run (networkidle timing), passed on both re-runs.

Notes:
- **FU-214** (open FU) rides on batch 14 — its product-surface browser-verify pass
  plus the 3 Product-History residuals folded in by FU-431 (2026-07-16).
- **FU-010 / FU-224** (theme + colour review FUs) collect signal from every
  V-pack walk — note anything relevant in reports.
- Batch 19/20 overlap heavily with automated migration tests (FU-536/549/563–565
  schema-match + from-empty chain); the residual manual value is the
  populated-DB / real-toolchain legs only.

---

### "Build my week" auto-planner (FU-596) — walked live (2026-07-31, money seed)

Drove `dora-verify-backend-money` + `dora-spa` as `dora`/`dora`. Splash-overlay
worked around by hiding the `Waking up Dora` node (the documented rAF-suspend
artifact — pane runs hidden). All checks passed; the DORA_VERIFY FU-596 section
was deleted (delete-on-pass).

- **Week generate + review** — 7 meals spread day-major across the 3 upcoming days
  (Fri/Sat/Sun); reason chips populated; aggregate "6 to buy · 19 in stock".
- **Smart slot placement (the FU-596 fix)** — recipes with `time_of_day=Dinner`
  landed in Dinner, "Vanilla Ice Cream Bowl" landed in **Dessert** (its own
  `time_of_day`) — never the vocab's first slot. Commit = `PATCH … 204`, so the
  server slot-validation accepted the placed slots.
- **Reshuffle / edits** — reshuffle re-calls auto-build; **Add a meal** (picker →
  row appears, chip "Added"), **Swap** (Spaghetti → Egg Fried Rice, picker titled
  "Swap this meal"), remove, and **"I'll pick myself"** (empty review) all work.
- **Day scope** — single-day proposal (all entries on the chosen day), default
  meal count **1**; commit + **scoped shopping list** via `sources.recipes`
  (`auto-generate 200`, `nothing_to_add` when the cookable recipe was fully in
  stock — a valid outcome).
- **Budget cap (residual #1 — set budget $500/wk in Settings → Money first).**
  API A/B for emphasis=variety: cap **off** → cost $3189.71, `projected_over`
  true; cap **on** → dearest "Load recipe 002" swapped for "Tomato Pasta"
  (chip `budget_friendly`), cost $2543.06. UI toggle confirmed: with **Keep the
  week under budget** on, the review row "Tomato Pasta" shows the
  **Budget-friendly** chip. (Seed recipe prices are huge, so it stays over $500 —
  best-effort swap-down is the documented contract, not a guarantee.)
- **Mobile entry point (residual #2)** — at 375×812 the `.mobile-focus` view
  renders a full-width **Build my week** CTA that opens the same builder (Guide
  step, all dials). Desktop toolbar + empty-week banner entry points also confirmed.

Backend ranker pinned by `tests/test_build_week.py` (16); no durable Vitest added
(slot contract lives server-side — matches the lean stance). Non-issue noted: a
`PATCH /auth/me` 403 during setup was a synthetic-event artifact (missing
`X-CSRF-Token`); the same call with the `dora_csrf` header returned 200, and the
real Settings flow attaches it — not an app bug.

### FU-596 — slot dials + per-row editing (2026-07-31, second round, extra checks)

Follow-up round after adding **per-row servings stepper + day picker** to the
review step (the earlier build only had a slot dropdown — the "edit day/servings"
claim was made good). All on the dev seed via the rAF-shim recipe.

- **One slot mode** — chose **Breakfast**; the 3-meal week landed **all in
  Breakfast**, overriding the recipes' own `time_of_day=Dinner` (Dinner not in the
  pool → forced), and the count clamped to the 3-day × 1-slot grid. ✓
- **Servings stepper** — bumped "Load recipe 001" to **3**; reactive in the review.
- **Day picker** — moved "Load recipe 003" Sat→Fri; the review re-grouped (Fri
  gained it, Sat group vanished). ✓
- **Edits persist through commit** — after Save, `GET /meal-plans` showed
  `Load recipe 001` = Fri/Breakfast/**servings 3** and `Load recipe 003` = **Fri**
  (moved)/Breakfast. ✓
- **Pick slots (server)** — direct `auto-build` with `slot_names:["Lunch","Snack"]`
  + 6 meals spread one-Lunch-one-Snack per day; `slots_used:["Lunch","Snack"]`. ✓
- **Pick slots (UI)** — **could not drive**: the pane maxes at 750px so the
  multi-select is a mobile bottom-sheet whose options don't respond to synthetic
  clicks (only ever bound one slot). Left as a 10-sec human check in DORA_VERIFY.
  Not a product concern — plain `q-select multiple`, and the server accepts it.
- **Bonus** — all of the above ran on the **mobile (≤750px) layout**, so the full
  builder + the mobile "Build my week" CTA are confirmed working on mobile too.

---

## Pilot results — Password policy (FU-442), 2026-07-16

Walked live against `localhost:5174` (dev SPA) + `:5170` (backend). Test
accounts created: `qa-admin` (admin, via first-run setup page — which the DB's
zero-user state surfaced; bonus pre-exercise of FU-200), `qa-user-1`,
`qa-user-2`. **These live in the repo-root `dora.data.db`** (see the caveat
below).

| Check (snapshot line) | Verdict | Evidence |
|---|---|---|
| L91 8-char letters-only succeeds | ➗ **intent PASS, example stale** | `abcdefgh` → 422 **breach-list** rejection (it's a breached string — correct NIST behaviour, impossible example); `zxqvbnmk` (letters-only, non-breached) → 200, account created. No digit rule anywhere. Checklist needs a new example password. |
| L92 `passphrase please` succeeds | ✅ PASS | POST register → 200, account created. |
| L93 `abc123` rejected ≥8 | ✅ PASS | 422, `"Password must be at least 8 characters."` |
| L94 breach rejection, case-insensitive | ✅ PASS | `password123` → 422 breach message; `QWERTY123` → identical 422 (case-insensitive confirmed). UI renders it inline under the field + "Registration failed" banner (evidenced on the register form). |
| L95 reset-flow fineprint + no digit language | ✅ PASS (2026-07-17, post-FU-568 fix) | Fineprint restored on all four surfaces; rendered live on LoginPage register mode + ResetPasswordPage ("At least 8 characters — a passphrase works well."). "No letter-and-digit language" half already PASSED. Owner can delete L95. |
| L96 change-password validator ≥8 | ✅ PASS (2026-07-16, session 2) | Live on `/settings/account`: typed `abc` into New password → inline "At least 8 characters" under both new + confirm fields. |
| L97 pre-policy password still logs in | ✅ PASS (2026-07-16, session 2) | UI login as seed user `dora`/`dora` (4-char, pre-policy) → 200, session valid, admin. Set-time-only policy confirmed. |
| L98 no policy-loosening admin toggle | ✅ PASS (2026-07-16, session 2) | Walked the full settings tree in-app: personal pages (Account/Preferences/Notifications/Money/Voice/Nutrition/Assistant/About), kitchen-setup, and the complete Admin mode (Users; System ×12 incl. Features/Email/Push/Hosting; Data ×3; Audit log; API access) — no password-policy surface anywhere. Matches code grep. |

**Findings spun off:** FU-568 (fineprint regression), FU-569 (Windows console
logging spam), FU-570 (silent boot on stale-schema DB — the cause of the
dashboard 500s seen mid-pilot; *not* a fresh-install product bug).

**Environment caveat learned (now a standing rule, see Appendix D):** the
preview-launched backend used the repo-root SQLite `dora.data.db` — a July-10
`create_all` artifact with **no `alembic_version`** and a stale schema — while
shell-resolved config pointed at Postgres. Anything beyond the auth tables
500s on it. **Before batch 1: create a dedicated disposable verify DB**
(`alembic upgrade head` + FU-388 dev seed on a fresh file, pointed at via env),
and re-run the deferred L96–L98 there.

### Batch 0 continuation (2026-07-16, session 2) — dedicated DB stood up; SettingsFileDrop + BuyVerdictCard partials; FU-571 found

**Verify DB:** root `dora.data.db` rebuilt (old file backed up to session scratchpad):
`drop_all` + `create_all` + `seed_dev_data(bulk_stock_items=500)` → 1 user
(`dora`/`dora`, admin), 521 stock items. Dashboard renders clean (the pilot's
500s are gone — confirms FU-570 was schema drift, not product).

**SettingsFileDrop (FU-545), 3/5 verified + blocked tail:**
- L76 click-to-open: ✅ **complete** (tail closed 2026-07-17 post-FU-571 fix) —
  click forwarding proven earlier; filename+size display now verified live:
  pick → upload 200 → steady `file-drop--filled` showing "fu545_tail.csv 36 B".
- L77 keyboard: ✅ — hidden input is tab-reachable; `:focus-within` restyles the
  zone (bg tint). Enter/Space = native `<input type=file>` activation.
- L78 drag-and-drop: ✅ — dragover → `file-drop--dragging` (dashed→solid,
  tint); dragleave calms; drop feeds the same pick path (now 200s post-fix).
- L79 Remove-doesn't-reopen: ✅ (2026-07-17) — from steady filled state,
  Remove click → zone back to idle copy, instrumented `input.click()` counter
  stayed 0 (picker never reopened).
- L80 busy/disabled inert: ✅ (2026-07-17) — `--busy` caught live mid-upload;
  `input.disabled === true` during it; zone click during busy → 0 picker
  opens; settles to `--filled` with filename. **Section 5/5 complete — owner
  can delete DORA_VERIFY L76–L80.**
- **FU-571 found here** (chunked uploads always 403 — CSRF header missing from
  `useChunkedUpload`'s raw fetches; Import + Backup-restore broken in browser).

**BuyVerdictCard (FU-454), state engineered + API-verified:**
- Fixture created (survives in the verify DB): stock item **"QA Verdict
  Cheese"** (`b5f476ac-fb96-4e3f-8a5d-c0d0238ab394`), level Stocked, 3 priced
  lines on 3 done lists ("QA verdict shop 1–3", 90/60/30 days ago), 2 waste
  events (45/20 days) → waste rate 67%.
- `GET …/buy-verdict` → `verdict: skip, confidence: high, one_tap_action:
  {kind: mark_stocked, label: "Already stocked"}`, waste reason "You've wasted
  this 67% of the time". ✅ the mark_stocked *state* is real and reproducible.
- Overview row renders the **Skip** chip (seen live). The tap-the-button UI
  walk (L83–88) is **deferred to the Playwright runner** (below) — the card
  lives in the detail view, which this harness pane can't mount (no-paint
  limitation). For `remove_from_list`: add the fixture item to any open list
  and the same card flips (code path `_pick_action`, is_on_open_list).

### Batch 0 blocker fixes (2026-07-17, session 3) — FU-571/568/569 fixed + verified

- **FU-571 FIXED + verified:** `csrfHeader()` helper exported from
  `axiosHttpClient.ts`; swept into all raw-fetch mutating sites (chunked
  upload start/chunk/finish/abort, import inspect/commit, backup
  create/inspect/restore, 2× app-settings PATCH on the Backup page,
  `/client-logs`, `/tts`). Live proof: real `useChunkedUpload().upload()`
  (imported via Vite in-page) ran start→chunk→finish → 200 + upload_id;
  `/data/import/spreadsheet/inspect` on that upload → 200 with auto-mapping;
  header-less POST still 403s (FU-197 defence intact). **L79/L80 tail +
  Import/Backup batch-12 checks are unblocked.**
- **FU-568 FIXED + verified:** hint prop on the 4 auth surfaces; rendered live
  on LoginPage (register mode) + ResetPasswordPage. L95 flipped to PASS above.
- **FU-569 FIXED + verified:** `stdout.reconfigure(encoding='utf-8',
  errors='replace')` in `configure_logging`; probe under forced
  `PYTHONIOENCODING=cp1252` emits `→ é ✓` cleanly, no logging traceback.

### Batch 0 completion (2026-07-17, session 3 cont.) — BuyVerdictCard L87–92 + Runtime URL L112–114 walked; FU-572 found+fixed; FU-573/574 opened

**Harness note first:** the full Appendix-D recipe (rAF stub + zero-duration CSS
+ **in-SPA hash nav, stub applied in-session, no reload**) mounts the stock
**detail page and its BuyVerdictCard** after all — the earlier "detail never
mounts" result was pre-recipe. The Playwright runner is still the right call for
screenshot/V-pack batches, but tap-walks are doable in-pane with this recipe.

**BuyVerdictCard one-tap actions (FU-454) — section COMPLETE:**
- L87 mark_stocked ✅ both surfaces — Stock Overview popover + Stock Item
  Detail card: tap → level set, positive toast, fresh verdict on
  re-render. **Found + fixed FU-572 mid-walk:** the detail card kept the stale
  one-tap until remount (invalidate never refetched) and the cart quick-add
  seams never invalidated — post-fix, the card updates **in place** (verified:
  remove_from_list → "Already stocked" live, no remount).
- L88 list-line mark_stocked ✅ — tap on ShoppingListDetail line badge →
  "Marked as Stocked." (new data-driven copy), level flipped, **line stayed
  on both lists**. (State reached via cached verdict after an out-of-band
  add — mark_stocked + on-open-list is otherwise mutually exclusive by
  `_pick_action` precedence, so this pairing only occurs via staleness.)
- L89 remove_from_list on Overview ✅ — toast fired, server-verified gone from
  every open list (3), reopened popover shows fresh mark_stocked verdict.
  **Toast over-counts** (fan-out no-ops counted) → **FU-573**.
- L90 remove_from_list on Detail ✅ — tap → toast, line gone server-side, card
  live-updated to the fresh one-tap (FU-572 fix proven here).
- L91 per-line semantics ✅ — on ShoppingListDetail, tap removed ONLY the
  current line ("Removed QA Verdict Cheese."); the same item's line on the
  other draft list survived (server-verified).
- L92 no fallback toasts ✅ — ~8 taps across 3 surfaces, zero "use the row
  controls"-style toasts.
- Owner can delete DORA_VERIFY's whole BuyVerdictCard section (L87–92).

**Runtime backend URL (P8-10, L112–114) — walked, one FAIL:**
- L112 ✅ — About shows "Dora API endpoint http://localhost:5170/api"; Change
  opens the prompt pre-filled with the current URL.
- L113 ➗ — bogus URL saved → persists to `dora.backendBaseUrl` + full reload →
  friendly full-page "Can't reach Dora's brain" screen, **no crash** ✅; but the
  only affordance is "Try again" — `#/settings/about` renders the same error
  screen, so the fix-it prompt is **unreachable** → **FU-574** (recovery clause
  FAILS).
- L114 ➗ — restoring the original URL recovers cleanly on reload (About +
  session intact) — but had to be done via localStorage, since the prompt is
  unreachable in the broken state (same FU-574).
- Owner can delete L112; L113/L114 stay until FU-574 is fixed + re-verified.

**Fixture left in the documented state:** "QA Verdict Cheese" Stocked, on no
open list, verdict skip/high + mark_stocked one-tap — ready for reuse.

---

### Batch 2 (Stock) progress (2026-07-17, session 4) — first codified increment

Applying the close-out rule: codify regression-worthy behavioural flows; delete
what's already pinned or verified-once; route hardware to device packs.

**Codified → green (`web_app/e2e/stock.spec.ts`, 7 tests):**
- **FU-508 StockItem.image dropped (L730–734)** — 3 pins: no `/stock-items/<id>/image`
  request fires on overview or detail; no "row images" toolbar toggle; detail
  Overview tab has zero `input[type=file]`. Cheap, stable, high regression value
  (guards the column/upload creeping back). → **owner can delete L730–733**;
  L734 (recipes/avatars/store-logos still render) is a separate-features
  cross-check — left as a one-time confirm.
- **FU-507 expiry-on-open (L723–728)** — 4 pins on the curated sealed-with-expiry
  item "Kensington Pride Mangoes": fixture-contract (sealed + has expiry);
  detail toggle → "Marking … as open" prompt → Update expiry saves is_open +
  new expiry in one PATCH (server-verified); re-sealing fires **no** dialog and
  restores state. Note the detail-page toggle is silent (no toast — that's the
  row path), so pins assert server truth. Row-path L724–726 share the same
  handler; detail path pinned as the representative. → **owner can delete
  L723–728** (row vs detail is the same code).

**Verified-once → already backend-pinned → delete (no e2e dup):** the five
fix-verify sections are all owned by green backend regression tests — confirmed
passing this session (86 green across the representative files):
- L693–695 product unlink (FU-528) → `test_delete_integrity.py`, `test_api_fuzz.py`
- L702–705 stocktake snooze 500 (FU-526) → snooze regression suite
- L707–710 consumption/re-confirm level (FU-533) → `test_patch_semantics.py`, `test_concurrency.py`
- L712–715 rename-to-own-name (FU-528) → `test_patch_semantics.py`
- L717–718 unlinked-ingredients loads (FU-532) → `test_unlinked_ingredients.py`
- L720–721 reconcile pagination (fuzz) → `test_reconcile_verbs.py`, `test_api_fuzz.py`
  → **owner can delete all six sections** — the browser confirm is redundant
  once the backend tests own the behaviour (that was the whole point of the
  campaign's "codify" disposition).

**Device-pack (hardware):** Scan mode (FU-378, L679–691) needs `scanning_enabled`
ON **and a camera**. The manual-entry level-set loop is A-codifiable behind a
scanning-enabled seed knob, but the camera-decode half is Pack 1 (Android). →
moved whole to **Appendix A Pack 1**; codify the manual-entry loop opportunistically
when a scanning-enabled e2e seed flag is worth adding.

**Stocktake Chunk 2 runner — first slice CODIFIED green (2026-07-17, session 5;
`web_app/e2e/stocktake.spec.ts`, 5 tests):** legacy `/stocktake/run` → `/stocktake`
redirect; runner opens straight on the first item (no landing) with the cadence/
overdue caption + "Still correct" + the level-tinted "(change)" button, and NO
"Out of stock" button; the **Still-correct walk** drains the whole queue to the
completion summary (checked counter > 0) and **Done** returns to `/stock`;
re-entering the drained queue shows the "You're all caught up." card. Covers
DORA_VERIFY L774–777, L781, L784, L788–790, L819–820 (partial), L825. →
**owner can delete those lines.**

**Stocktake Chunk 2 runner — REMAINING VERBS NOW CODIFIED green (2026-07-17,
session 6; `web_app/e2e/stocktake.spec.ts` grew to 5 tests):** the four
remaining verbs + help + add-to-list are pinned as one deterministic **verb-walk**
that uses each verb exactly once and drains the queue: **Skip** (session-only →
item re-queued to the end, no API, `skipped` counter), **Change level** (picker
dialog → "Out of Stock" → `changed` counter + clock reset), **Push 3 days**
(snooze → `pushed` counter), **Mute** (confirm dialog "Mute X?" → `muted` counter),
then **Still-correct** the re-queued Skipped item (`checked` counter). Asserts the
five-counter completion summary (each = 1), the **SK-7 batch add-to-list** prompt
("1 item went Low or Out" → "Add to list…" → radio dialog on seeded "This week" →
"Added."), and **Done → /stock**. Plus a separate **(?) help dialog** test
asserting all five verb definition-terms render. Determinism rests on the curated
seed's exactly-four overdue items (Vanilla Ice Cream / Brazil Nuts / Hot Crispy
Chippies / Broccoli). Covers DORA_VERIFY **L792–797 (Change), L798–801 (Skip),
L803–806 (Push), L808–812 (Mute), L814–816 (help), L821–824 (add-to-list)** →
**owner can delete those lines.** Full spec **5/5 green**; full e2e suite otherwise
green (one unrelated pre-existing uploads channel failure — see FU-576).
- **Stocktake Chunk 3 settings — CODIFIED green (2026-07-17, session 7;
  `web_app/e2e/stocktake-settings.spec.ts`, 3 tests):** the Settings → Admin →
  System → Stocktake page's two global dials. Page loads with the three cadence
  bands + server default Fortnightly; **cadence** tap → "Default cadence saved."
  toast → PATCH persists across a reload → restored; **Auto self-tuning** flip
  → "Auto self-tuning off."/"...on." toasts → persists across reload → restored.
  Asserted against server truth (`/app-settings`) not Quasar active-button
  styling. **Self-restoring** (ends at Fortnightly + Auto on) so it doesn't
  perturb the stocktake queue (sorts + runs before `stocktake.spec.ts`). Covers
  DORA_VERIFY **L741–746** → owner can delete (L743/745/746 fully pinned;
  L741/742/744 behaviourally pinned — only the visual "highlighted"/"de-activates"
  nuance stays V-pack). **Remaining, not codified:** L740 (nav-entry placement/icon
  — one-time), L747 (non-admin banner — needs a non-admin session), L748–749 (Auto
  on/off actually reshaping the runner's cadence — deeper behaviour).
- **Alert-threshold removal (L752–753)** — CODIFIED (2026-07-17, session 8):
  `alert-thresholds.spec.ts` pins that the "Default stocktake reminder" section
  is gone from Settings → Admin → System → Alert thresholds (asserts no
  "stocktake reminder" copy + exactly one numeric dial survives) AND that the
  surviving "Expiring-soon window" still edits/saves/persists on blur (toast
  "Alert thresholds saved.", server truth `/app-settings`). Self-restoring to 7.
  → owner can delete L752–753.
- The **pulse outline / reduced-motion / dark/light** checks (L762–768) are V-pack
  (eyeball) → Appendix B. The **"Needs check" Overview filter** (L755–760) is
  CODIFIED (2026-07-17, session 8) in `stock.spec.ts`: opens the Filters panel,
  flips "Needs check" → `.stock-row` count narrows to exactly `/stocktake/queue`
  total (and each queued name is visible) → toggle off restores the full list;
  also pins the "Stocktake (N)" toolbar label mirrors the same server count.
  Read-only, runs before the queue is drained. → owner can delete L755–760
  behavioural bullets (the icon/position bullet stays V-pack, one-time visual).
- **Add-a-stock-item dialog (L672–677, Codex)** — backend fully unit-tested (trim/
  dedup/over-long); the dialog-renders-expiry+Essential visual bits are a
  one-time confirm; the trim/dedup behaviour is already pinned. Low priority.

**Batch 2 disposition tally (updated 2026-07-17 session 8):** ~120 items →
~40 codified green (stock + full stocktake runner + Chunk 3 settings dials +
"Needs check" Overview filter + alert-threshold removal) · ~15 delete
(backend-pinned) · ~11 delete (FU-507/508 codified) · ~20 device-pack (scan) ·
codify-next tail now just non-admin banner (L747, needs a non-admin session) +
auto→runner cadence effect (L748–749, deeper behaviour) · rest V-pack/one-time
(pulse/reduced-motion/dark → Appendix B). Manual pile for this batch has now
shrunk by ~72; runner + settings dials + Overview filter + alerts-removal pinned.

### Batch 3 (Stock B) progress (2026-07-17, session 9) — first codified increment

**Codified → green (new `web_app/e2e/bulk-waste.spec.ts`, 4 tests):** the bulk
**"Log waste…"** action on Stock Overview (DORA_VERIFY **L827–836**, origin
FU-226). Enters bulk mode, ticks stable no-expiry seed items (Canned Tomatoes /
Brown Onions / Garlic — untouched by any other spec):
- **L834** — with 0 selected the "Log waste…" bulk-bar button is disabled.
- **L830 + L831** — select 3 → the MarkAsWastedDialog opens with header "Why did
  this go to waste?", subject "3 items", subline "One reason applies to every
  selected item."; tapping the **Spoiled** tile closes the dialog, exits bulk
  mode, and fires one plural summary toast "Logged 3 items as wasted." with Undo.
- **L832 (data half)** — server truth: exactly one `spoiled` StockItemWasteEvent
  per selected item (`/waste/events`). The Reports→waste-insights *UI* surface
  itself stays a one-time eyeball (V-pack).
- **L833** — Undo on the summary toast removes all events ("Undone." toast) and
  restores each item's original expiry (covered by the expiry test below).
- **L835** — a single selection uses singular copy ("Logged 1 item as wasted.").
- **expiry clear+restore** — a 4th test PATCHes an expiry onto Garlic, logs
  waste (expiry cleared, asserted server-side), Undoes (expiry restored), then
  resets the seed item — fully self-contained.

**Self-restoring:** every test ends via the UI Undo it's pinning; an `afterAll`
safety net then hard-resets via the API (deletes any lingering event for the
three ids, nulls any expiry) from a context rebuilt off `e2e/.auth/user.json`,
so a mid-flow failure can't leak into later specs.

**L836 (single-item row expiry-menu waste path)** — CODIFIED (session 10, 6th
test): PATCH an expiry onto Canned Tomatoes so the row's expiry button opens the
push/clear/log-waste **menu** (a no-expiry item shows a date picker instead) →
open it via the `Expires <date>` accessible name → "Log waste" → Spoiled → the
**per-item** toast `Logged "Canned Tomatoes" as wasted.` (distinct copy from the
bulk summary) → server event + expiry cleared → Undo restores both → reset to
null. Confirms the bulk flow didn't regress the single path.

**Not codified here:** L829's "trash icon" + L832's Reports-UI render are
one-time visuals (V-pack). The whole FU-226 waste section is now behaviourally
pinned.

**Verification:** `DORA_E2E_CHANNEL=chrome npx playwright test` — `bulk-waste.spec.ts`
**6/6** green (incl. the auth setup); full suite **40 passed / 1 failed**, the one
failure the same pre-existing unrelated `uploads.spec.ts:46` channel flake
([[FU-576]]). No new FU.

**Auto-add-on-low (L838–857, FU-315/464/511)** — first codified increment
(session 11) in `auto-add-on-low.spec.ts` (2 tests, serial, self-restoring).
Seed reality that made it testable: the Playwright webServer sets
`DORA_SEED_BULK_ITEMS=0`, so the `big_list` draft never seeds → **"This week" is
the sole draft**, i.e. `resolve_primary_target` returns "single" and the happy
path is deterministic. But **every** flagged+Stocked seed item is already on an
active list (eggs/olive-oil/coffee on "Saturday shop", brazil already Low), so
the Essential-mode happy path can't fire on the seed without restructuring shared
list state — instead the spec drives the **`All items` mode** path on a clean
non-Essential item (Jasmine Rice: Stocked, on no list, untouched by other specs),
which exercises the identical toast + line-chip seam and *is itself* L849's
deliberate 3-state expansion.
- Test 1 (L843): Settings → Admin → System → Stock dial loads (reads seeded
  `essential_only`), saves each state eagerly with the "Auto-add mode saved."
  toast, persists across a hard reload (server truth via `/app-settings`),
  restores to `essential_only`.
- Test 2 (L844 + L847 + L849): mode→`all`, drop Jasmine Rice Stocked→Low Stock
  via the row level menu → toast **"Added Jasmine Rice to <display_name>."** +
  caption "Auto-added because it went low." → server truth: the draft list now
  carries a line for the item tagged `added_via=auto_low_stock` → the list-detail
  render shows the `auto: low stock` chip. Restores via API (delete the auto line
  by-stock-item, reset level to Stocked, mode back to `essential_only`); an
  afterAll re-asserts the clean state.
- Test 3 (L856/857): the **retired per-item auto-add UI stays gone** — read-only
  absence guard against the `auto_add_when_low` toggle (collapsed into the
  install-wide mode by FU-511) creeping back. Stock overview: no "Will auto-add on
  low" filter chip, no "Auto-add" footer count (asserted alongside a surviving
  "Essential" control so it's not a blank-page false pass); detail page: no
  "Auto-add" toggle row (item name rendered as the render sanity).
→ **owner can delete L843, L844, L847, L849, L856, L857.**

**Not codified here (stay owner-verify / other homes):** L845 (Out transition —
same handler, not separately driven), L846 (no-manual-refresh timing — UX, not
asserted), L848 + L850 (Off / Essential-only *negative* paths), L851 (dedup) +
L852 (0/2+ draft ambiguity) → **server-owned branching, routed to a backend
follow-up** [[FU-577]], L853 (detail-page Level row), L854 (cook-mode decrement,
multi-toast), L855 (offline queue).

**Verification:** `auto-add-on-low.spec.ts` **4/4** green (incl. auth setup); full
suite **43 passed / 1 failed** — the one failure the same pre-existing unrelated
`uploads.spec.ts:46` channel flake ([[FU-576]]). New FU-577 logged for the
untested server-side branching matrix.

**FU-577 backend truth-table CODIFIED (2026-07-18):** new
`tests/e2e/dora_api/test_update_stock_item_auto_add.py` (12 tests, green; full
backend suite 1505 passed) pins the whole server-owned matrix directly against
`PATCH /api/stock-items/<id>`: mode × flagged (Off never; Essential-only iff
flagged; All regardless), **L845** Stocked→Out fires, transition guard (Low→Out
+ Out→Stocked silent), **L851** dedup (on the target draft AND on a
SHOPPING-status list), **L852** draft-count (0 and 2+ silent; draft+SHOPPING
still fires onto the draft). Firing cases assert the 200 `auto_added` body +
the `added_via=auto_low_stock` line; silent cases 204 + no line.
→ **owner can also delete L845, L848, L850, L851, L852** (backend-pinned).
Remaining owner-verify in this section: L846 (refresh timing), L853 (detail
Level row), L854 (cook-mode multi-toast), L855 (offline queue).

**3-band StockLevel collapse (DORA_VERIFY L874–883) — triaged + gaps codified
(2026-07-18):** the section is mostly backend-owned; three surfaces had *no*
server test — now pinned in new `tests/e2e/dora_api/test_stock_level_collapse.py`
(6 tests) + one test added to `test_data_router.py` (7 new total, green; full
backend suite **1512 passed**):
- **L875** — `POST /shopping-lists/<id>/finish` with an empty body flips every
  *ticked* line's item to Stocked (sequence identity), returns
  `{items_restocked: N}`; a second test pins that *unticked* lines' items keep
  their level (finishing only restocks what you bought).
- **L876 (server half)** — a `level_overrides` entry wins over the Stocked
  default (part-restock lands on Low, unlisted sibling still Stocked); an
  override naming an unknown level id is a 422 and nothing mutates (list not
  done, level untouched).
- **L877** — alert action `mark_restocked` sets the item to Stocked + bumps
  `stock_level_last_updated`; contrast test pins `acknowledge_stocktake`
  bumping the stamp with the level **untouched** (was previously untested —
  only `reset_expiry` had a test).
- **L879** — spreadsheet import: a mapped Level column with a **blank cell
  defaults to Stocked**, and "Stocked"/"Low"/"Out of stock" land on sequences
  0/1/2 — asserted on the created items' actual levels (the old test only
  counted rows).

Already pinned elsewhere (verified this session, no new tests needed):
**L878** `review/complete` → `{set_stocked, checked}` + item flips Stocked in
`test_stocktake_router.py`; **L880** "sufficient"/"ok"/"fine"/"well stocked" →
STOCKED aliases in `test_confirm_actions_resolve_level.py` (resolves by
sequence, rename-proof); **L881** cookability Low-counts-as-have /
Out-doesn't in `test_recipe_cookability.py`.

→ L875/877/878/879/880/881 **deleted from DORA_VERIFY 2026-07-18**
(delete-on-pass sweep). Stay one-time eyeballs (V-pack): the modal render
(3 options, no "Sufficient" label — merged with L875's UI half), onboarding
"Restock" scene copy, buy-verdict popover "Stocked" need-axis label (adjacent
to the Batch-0 BuyVerdictCard walk).

**Zero-Input Pantry (P8-07) — HTTP seam codified (2026-07-18):** the belief
*engine* was already unit-pinned (`test_pantry_belief.py`, 11 tests: bands,
cook drift, override-wins, thin-history caution, differs flag) but the HTTP
layer had zero tests. New `tests/e2e/dora_api/test_pantry_beliefs_endpoint.py`
(3 tests, green; full backend suite **1515 passed**) pins: `GET
/stock-items/beliefs` default-on shape (enabled:true + per-item
believed_band/confidence_band/reason contract), the per-user opt-out gate
(`PATCH /auth/me inferred_pantry_enabled:false` → `{enabled:false,
beliefs:{}}`, persists, re-enables), and the override-wins pin end-to-end (a
fresh level PATCH reads back as that band at HIGH confidence). DORA_VERIFY
section trimmed per delete-on-pass: the OFF-endpoint bullet, thin-history
bullet, and manual-change bullet deleted (pinned); toggle + drift-outline
bullets reworded to their remaining UI halves. Remaining owner/e2e checks:
chip render + tooltip, buy/cook loop reasons, warning-outline render,
quick-check suggestions (×2), dark-mode tokens, backup/restore recompute.

**P8-05 buy-verdict oracle (DORA_VERIFY L733–744) — codified (2026-07-18):**
the engine was already fully unit-pinned (`tests/test_buy_verdict.py`, 27
tests: verdict matrix incl. out-of-stock/low+cheap/stocked+wasteful/
stocked+above, thin-data collapse, reason labels + `$last vs $usual` details,
wait-hint, fake-markdown) and the Skip walk e2e'd (Batch 0 + `buy-verdict.
spec.ts` tests 1–3). This session pinned the three remaining UI seams (3 new
tests → `buy-verdict.spec.ts` now 6, suite 46 pass / 1 pre-existing FU-576
flake) + the whole client cache (new `web_app/test/unit/useBuyVerdict.spec.ts`,
7 tests; frontend Vitest → **394/31**):
- **Feature flag** — Settings → Admin → System → Features toggle off → toast +
  server truth → full reload → fixture row renders with **no** badge; toggle on
  → reload → Skip badge back. Found **FU-580** en route: the toggle never
  refreshes the once-per-document health probe, so the flip needs a full reload
  in a live session (test pins the verify bullet's reload wording as-is).
- **Silent on low-confidence** — thin-history seed item (Jasmine Rice):
  `/buy-verdict` answers `confidence: low`, row renders name but zero
  `.dora-buy-verdict-badge` (fixture row asserted as the non-blank control
  elsewhere in the file).
- **Out-of-stock → buy walk** — fixture PATCHed to Out of Stock → API canary
  (buy/high, `reasons[0] = out_of_stock`, one-tap `add_to_list`) → green Buy
  chip → popover "You're out of stock" → one-tap "Add to primary list" →
  "1 added." toast → server truth: line on the draft → restored.
- **Client cache (Vitest)** — one request per item shared across concurrent
  consumers, cache-serve inside the 5-min window, stale-but-usable background
  refresh past it, FU-572 live-entry invalidation refetches immediately (and
  stays lazy on a null entry), error → null badge + captured message,
  disabled-gate no-fetch until the flag flips, clearBuyVerdictCache drops all.

→ L734–744 **deleted from DORA_VERIFY** (delete-on-pass); the section keeps one
V-pack line (orange **Wait** badge look — the only variant never walked). An
afterAll safety net (flag on, fixture Stocked + off-list) was added to the spec.

**History tab — both sections codified (2026-07-18):** the expiry-emission +
cap/older-count server halves were already pinned (`test_stock_item_router.py`);
the two feeds with zero server tests are now pinned in new
`tests/e2e/dora_api/test_stock_item_history_feeds.py` (7 tests; full backend
suite **1522 passed**):
- **Bought** — ticked+priced line on a finished list surfaces one
  `purchase_events` entry (price/list-name/stamp; store `None` when uncaptured);
  price-less/store-less line still surfaces (title-only render contract); a
  seeded store id resolves to `store_name`; an **unticked** line never
  surfaces; a ticked line on an in-flight (`shopping`) list is mid-shop, not
  bought.
- **Cooked** — `POST /recipes/<id>/cook` writes one `cook_events` entry on
  ingredient items only (bystander item stays clean — the RecipeIngredient
  join, not a wildcard), `meals_cooked` rides along for the "× N meals" badge;
  a zero-meal cook (bare `last_made_on` bump, 204) records nothing.

UI halves in new `web_app/e2e/history-tab.spec.ts` (4 tests; full e2e suite
**50 pass / 1 pre-existing FU-576 flake**): Sriracha chatty-seed walk (66
seeded expiry events → "16 older events not shown", count stable across a
reload), Milk under-cap mixed feed (Bought/Wasted/Pushed interleaved, no
footer), Garlic "Used in <recipe> · N meals" batch badge, and an engineered
item walking the full Set → Pushed +7 days (with `A → B` body) → Cleared
(with "Was <date>" body) family, self-deleting. Migration-downgrade bullet
dispositioned to `tests/test_migrations.py` (SQLite xfail carve-out; Postgres
leg batch 19).

→ both History sections (old L758–783) **deleted from DORA_VERIFY**, replaced
by one merged section holding a single one-time visual line (event-kind theme
colours + the singular footer branch).

**FU-109 deep-link filter + no-dim — codified, 2 real bugs found + fixed
(2026-07-18):** narrowing/orphan/AND-compose were already Vitest-pinned
(`useStockFilters.spec.ts`); new `web_app/e2e/recipe-deeplink.spec.ts` (4
tests) pins the URL/chip wiring: card filter icon → `/stock?recipe=` chip +
list narrowed to exactly the aglio ingredients, chip-× teardown (param
stripped, full list back), toolbar **Clear** strips `?recipe=` with a reload
unable to reinstate it, bogus id leaves the list intact with no chip, filter
icon only on the detail Recipes tab (cookbook cards asserted icon-free), and
every card on that tab at computed opacity 1 (the dim code no longer exists in
`RecipeCard`). **Bugs found by the spec, fixed inline (CHANGELOG'd):**
(1) a bogus/dead `?recipe=` id stranded a phantom "Ingredients of: this
recipe" chip — the hydration-fallback label leaked into the
loaded-but-unresolved state; fixed by making the recipe store's hydration
latch reactive (`recipesHydrated`) and gating the chip on resolved-context-or-
still-loading. (2) the Stock Overview empty-state "Clear" button called the
raw filter reset, leaving `?recipe=` in the URL for a refresh to reinstate —
now routed through the page's `clearAllFilters` wrapper. **Also unblocked the
pipeline:** the FU-579 bulk-waste type errors hard-failed `quasar build`
(exit 2, no `dist/spa`) — fixed via a throwing items-by-name accessor;
`vue-tsc --noEmit` now fully clean; FU-579 amended (src-pwa dev-watch half
stays open). Both FU-109 sections **deleted from DORA_VERIFY** (nothing
remains — the tooltip text lives in the component template). Full e2e suite
**54 pass / 1 pre-existing FU-576 flake**; Vitest 394/31.

**Stock pickers + Log Waste — behavioural halves codified (2026-07-18):** new
`web_app/e2e/stock-pickers.spec.ts` (2 tests; full e2e now **56 pass / 1
FU-576 flake**): (1) the detail-page Level row round-trip on a throwaway item
(created via API so auto-add/seed state can't interfere) — dropdown pick
Stocked→Low Stock → "Updated just now" stamp + trigger re-label + server
truth, self-deleting; (2) the overview level filter set→clear cycle — narrows
on pick, clear-× restores the full list with the "Any level" fallback trigger,
and the whole interaction captured console-clean (warnings/errors/pageerrors
all asserted empty). The row expiry-menu Log-waste behavioural path was
already pinned by `bulk-waste.spec.ts` test 6. Section reworded to a single
one-time visual (dot styling parity across the three pickers + the
destructive-red Log-waste entry).

**C-1b detail section triaged + Chunks 2/4 codified (2026-07-18, session
close):** the big C-1b section rewritten against current coverage — deleted
as pinned (Level row round-trip, lifecycle timeline, clear semantics, expiry
dialog, unsaved-changes composable) and as **stale** (the C-1b.1
header-level-chip bullet superseded by the Overview Level row; every
auto-add-toggle / footer-Auto-add mention, retired by FU-511 with absence
pinned). Remainder compressed to: one layout/visual walk line, splitter-peek
walk, the picker-× wiring, **two codify-next candidates** (C-1b.4
Recipes/Lists/Substitutes actions; C-1b.3 Products tab incl. the products-off
tab-gating), and the unpinned History extras (Restocked/Dropped labels,
synthetic Opened, empty copy). New coverage this close: **`useStockItemActions
PushExpiry.spec.ts`** (8 Vitest tests — the FU-123 `max(today, current)+N`
push matrix incl. past-expiry→tomorrow, fallback, toast + error path; Chunk-4
bullet deleted) and a **Chunk-2 describe in `stock.spec.ts`** (2 tests:
desktop filter-panel persistence reload round-trip both directions; retired
"Used in a recipe" filter absent + bare "Search" placeholder; Chunk-2
reworded, stale Flagged/Auto-add footer-order bullet corrected to the current
labels). Suites: e2e **58 pass / 1 FU-576 flake**, Vitest **402/32**.
Batch-3 tail now: Chunk-2 mobile-hidden bullet (viewport-gated), Chunk 5
(responsive nav/long-press — device/viewport pack), Offers sidecar (1
money-gated walk line), + the compressed visual walks.

**C-1b.4 codify-next candidate CODIFIED (2026-07-18):** new
`web_app/e2e/detail-recipes-tab.spec.ts` (3 tests + setup, fully throwaway
universe — two API-created Stocked items + a recipe using both, torn down in
afterAll): heart toggles favourite on AND off with server truth (this surface
once shipped with the toggle wired to a dead listener); the cookable card's
cart action ("Add all to list") lands both ingredients on the primary draft
("2 added." toast + list truth) and the Lists tab reflects membership with no
dead `open_in_new`; a substitutes row renders without the retired per-row
"Swap into list" and Remove unlinks (detail-DTO truth + row gone). Triage
note: the old "styled Primary badge" wording was stale — Round-17 replaced
the pill with a warning-toned star (folded into the visual walk). Full e2e
suite **61 pass / 1 FU-576 flake**. Remaining C-1b codify-next: the
Products-tab gating (C-1b.3, products-flag-dependent).

**C-1b.3 Products tab codified → real bug FU-581 (2026-07-18):** new
`web_app/e2e/detail-products-tab.spec.ts` (2 tests): Milk's two linked
products render with exactly ONE Cheapest chip + `--cheapest` highlight
class, the quiet "Link another" header action, per-card Add-to-list, and no
retired "Get cheapest" button anywhere; a throwaway no-products item shows
the centred "Find & link a product" CTA (and no "Link another"),
self-deleting. **Bug found: the CTA routes to the FU-186-retired
`/product-search` route and lands on the 404** — same dead link on
`MyProductsPage.vue` (×2) and the Dashboard "Hunt for deals →" CTA; logged
as [[FU-581]] (design call: external `product_search_url` vs My Products vs
hide) rather than blind-patched, and the spec deliberately does NOT pin the
destination until that's decided. The products-OFF half (tab hidden +
`?section=products` → Overview fallback) needs a productless install — kept
as the section's one remaining bullet. Full e2e **63 pass / 1 FU-576
flake**.

**Batch 10 (Dashboard) opened — Draft-my-shop (FU-351) codified
(2026-07-18):** server halves in new
`tests/e2e/dora_api/test_auto_generate_draft_shop.py` (2 tests; full backend
suite **1524 passed**): zero candidates on the create-new path answer
`nothing_to_add: true` + null `shopping_list_id` + **no phantom list** (the
collection is byte-identical before/after), and the card's explicit
"Weekly shop · <date>" name is honoured on the created list. UI seams in new
`web_app/e2e/dashboard-draft-shop.spec.ts` (2 tests + afterAll safety net
deleting any "Weekly shop ·" list so the sole-draft assumption other specs
rely on holds): the card renders in the act zone (blurb + button), one click
→ "Drafted N items." toast + caption → navigates to the named draft with
`auto:` provenance chips rendering; the Cards-menu row's q-toggle hides and
restores the card. Provenance priority + the single-commit contract were
already pinned (`test_auto_generate_priority.py` /
`test_auto_generate_unit_of_work.py`). Left as walk bullets: the empty-case
UI half (needs a fresh install), the forced-500 error toast, and the
consumed-entry guard (consumed_at only written by the cook-reconcile job —
code-visible at `auto_generate.py:418`). Full e2e **65 pass / 1 FU-576
flake**.

**Dora Score / Kitchen health (P8-08) codified (2026-07-19):** the engine was
already unit-pinned (`test_dora_score.py`, 8 suites) and the endpoint
shape/anonymous-401 backend-pinned (dashboard router + DTO snapshot +
route-auth sweep). Added: the L923 log-line contract as a backend test
(`test_dashboard_router.py::test__dora_score__EveryRequestLogsTheScoreLine…` —
one "Dora Score user=… composite=… trend=… (delta=…)" record per request, no
NaN/negatives/exceptions; backend suite **1525 passed**) and new
`web_app/e2e/dora-score.spec.ts` (3 tests): hero + five ordered component rows
asserted against `/dashboard/dora-score` server truth (labels, reasons,
bar-per-scored-row), the **dormant contract on real data** (seed has no budget
→ Budget row renders "—", dormant class, no mini-bar, composite still a
number), card-above-Pantry placement, the action links (Budget/Freshness/
Run-outs/Stocktake navigate, none 404; **Waste deliberately has no link** —
D10 dissolved `/waste`, pinned as an absence; the old L920 `/waste`
expectation was stale), and the Cards-menu q-toggle hide/restore. **Found
[[FU-583]]** en route: `?expiring=1`/`?stocktake=1` on the Freshness/Stocktake
links are silently ignored by `StockOverview.applyQueryFilters()` (honours
only location_id/attention/level_id) — exactly what L920 asked to flag.
DORA_VERIFY section trimmed per delete-on-pass (8 bullets deleted/absorbed;
survivors: trend-chip both-direction render, bar traffic-light colours,
fresh-install empty state, week-long trend flip, kitchen-zone drag-reorder).

**Log-price quick action (FU-300) + budget money-gate (FU-297) codified
(2026-07-19):** new `web_app/e2e/dashboard-log-price.spec.ts` (4 tests + a
beforeAll/afterAll that flips BOTH money layers on — the e2e seed ships money
OFF at install AND user level — and restores seed state after). Pinned: the
three-button quick-action bar; the LogPriceSheet picker (≤12-row low/out-first
shortlist asserted against stock-items/stock-levels server truth, live "milk"
filtering, selection → "Log a price · <name>" title, prefill seeded from the
detail DTO's `price_entry_prefill` — exercised, the seed harvests Milk
observations); submit happy path ($6.40 / 2 L → toast, sheet closes, exactly
one new observation with the folded shape in the detail DTO, and the
Your-Prices widget rendering the server-derived "$3.20 / L" on a fresh
single-goto page — FU-584 dodge); dismiss-means-cancel (zero POSTs) + fresh
reopen; money OFF hiding Log price AND the budget card (dashboard + Cards
menu, zero `GET /api/budget/status`). **Two findings en route:** [[FU-585]] —
the back arrow keeps the search query (code) vs the verify bullet expecting it
cleared (spec pins current behaviour, not blind-patched); [[FU-586]] — the
dashboard money loaders race the one-shot /api/health flags probe on a cold
mount and never re-run when flags land (reproduced: money ON, hard reload,
zero budget-status requests), so the spec deliberately does NOT pin the
money-ON request. FU-300 section deleted (fully covered); FU-297 keeps one
FU-586-blocked walk bullet. Full e2e suite **73 passed / 0 failed** (the
FU-584 flakes stayed quiet this run). Box note: this machine needed
`npx playwright install chromium` (headless-shell v1228 missing).

**Donut deep-links (FU-299) + "Next to cook" (FU-298) codified (2026-07-19):**
new `web_app/e2e/dashboard-donut.spec.ts` (3 tests, read-only on seed):
legend low/out rows + "View →" hrefs pinned against `/stock-levels` server
truth and the in-stock legend row + whole card proven inert; the donut's
exactly-two link segments (role/tabindex/class + "View low items"/"View out
items" aria-labels) with the green arc inert even to a dispatched click; a
**real pointer click on the low arc** (point computed from the
`/dashboard/summary` proportions — pins that the rotated SVG stroke is
actually hittable, needed a `scrollIntoViewIfNeeded` since `page.mouse`
doesn't scroll) landing `/stock?level_id=<low>` with the FilterBar level
select showing the level name and `.stock-row` count matching server truth;
Enter on the out arc and Space on the low arc both navigating. Whole
DORA_VERIFY FU-299 section deleted. New `web_app/e2e/dashboard-next-cook.spec.ts`
(2 tests) on a throwaway universe (Stocked + Out items; ready / missing-one /
no-ingredients recipes planned TODAY in "Breakfast" — sorts ahead of the
seed's Dinner/Lunch so the trio owns the card's top-3 deterministically; the
ready recipe planned twice to pin the recipe-dedupe): rows mirror the DTO's
order with "Today breakfast · serves N" meta and Ready / Missing 1 /
No ingredients badges backed by explicitly asserted DTO truths
(missing_count 0 / 1 / null); name → `/cookbook/{id}`, Cook →
`/cookbook/{id}/cook`. FU-298 section trimmed to the one plan-free-install
empty-state bullet. **FU-584 addendum found en route:** the hash-router race
also fires on a *warm* `goBack()` → `router.push` sequence (deterministic
blank-document wedge in the next-cook spec; both new specs route around it
via reload → fresh goto). Full e2e suite **78 passed / 0 failed**.

**Price-drops widget (FU-296) codified → real bug found + fixed
(2026-07-19):** backend (`test_reports_router.py` +4): ranking pinned
(%-desc, dollar-amount tie-break, filtered to the test's own products),
`is_active=false` exclusion, limit clamp (0/−3→1 row, 999→≤20, missing and
`abc`→exactly 5 against six seeded drops). **The ranking test's second
price-PATCH 500'd — real bug:** `update_product.py` appended the archived
`ProductHistoricOffer` to the relationship without `repo.add()`, so the
cascaded insert carried `EMPTY_UUID` and the second-ever price change in an
install collided on the PK (the ingest path and seed both `add()`; this was
the odd one out). One-line fix + comment; the new tests are the regression
pin; CHANGELOG entry added. Backend suite **1528 passed**. UI
(`dashboard-price-drops.spec.ts`, 2 tests): defaultHidden honoured, Cards-
menu enable → honest empty state on seed truth (rows==0 asserted first),
engineered drop (create product $10 → PATCH to $8, link to a throwaway
item) renders name/store/deep-link/"was $10.00"/"20% off" + "My products →",
deactivate → empty state returns, toggle restored to defaultHidden. Specs
**warm-navigate** (land `/#/stock`, then in-app goto `/#/`) because the
products-gated loaders lose the same cold-mount flags race as FU-586
(addendum added there). No DELETE /products exists — cleanup is
deactivation, which the report excludes (itself backend-pinned). Full e2e
suite **80 passed / 0 failed**.

**Cards-menu reorder (FU-294) + `dashboard_layout` backend (FU-292)
codified (2026-07-19):** new `web_app/e2e/dashboard-cards-reorder.spec.ts`
(4 tests + a beforeAll/afterAll capturing and restoring the user's
`dashboard_layout`): tap down/up arrows reorder within the Today zone
(first-row up + last-row down disabled — note the zone's true last menu row
is the defaultHidden "This fortnight", which still lists), asserted against
menu render + the `/auth/me` layout JSON + a full reload; native HTML5
drag (`dragTo` on the `.dora-dnd-handle`) lands drop-on semantics and the
order follows the user to a second browser context (FU-292's cross-device
contract); cross-zone drag (Pantry → Today) leaves both the menu and the
server layout byte-identical; an iPhone-UA run (Quasar's platform.is.mobile
is UA-based, not viewport) pins the handle column hidden with tap arrows +
toggle remaining. FU-292's other halves were already covered (migration
applies on every suite boot; `test__dashboard_layout__set_and_clear` green).
Spec note: the up/down arrows are icon-only BaseButtons with tooltips but
no aria-label → no accessible name, so the spec targets them positionally
(pre-existing, FU-578's unlabelled-buttons bucket — not re-logged). FU-292
section deleted; FU-294 down to the one mid-drag transient-visuals bullet.
Full e2e suite **84 passed / 0 failed**.

---

**Harness lesson (major — shapes every future browser batch):** the in-app
preview pane runs **hidden** (`visibilityState: hidden`): no paint, no
`requestAnimationFrame`, screenshots time out. Vue `<Transition>`s double-rAF
before resolving, so **any transition-gated content wedges** — route swaps
after the first, and the stock detail page's skeleton→content `FadeTransition`
(cold-load included). Partial workaround (in Appendix D): rAF stub +
zero-duration CSS un-wedges top-level route swaps, but not the C-1b desktop
peek. **Decision: browser A-checks move to a Playwright-driven runner**
(already in the repo — FU-540, `test:e2e`; headless Chromium paints, rAF runs,
screenshots work → also produces the V-pack artifacts). Claude in Chrome is
the alternative if the extension gets connected. The pane stays fine for
API-level checks, single-view cold loads, and DOM instrumentation.

**2026-07-18 — interactive driver now exists:** `web_app/e2e/drive.mjs`
(JSON-plan steps over headless system Chrome: goto/click/fill/viewport/scheme/
shot/eval, auto-login, kills the vite-checker overlay — FU-579). This is the
tool for ad-hoc UX walks and **V-pack screenshot staging** — point the plan's
`outDir` at a folder, collect the PNGs. See the worklog entry (2026-07-18
later 5) for setup.

---

### Cookbook detail page — Chunk 4 (FU-089) walked live (2026-07-22)

Followed the rAF-shim recipe (in-place login, hash-nav) on the seeded
`dora-verify-backend` (:5170). Drove **Veggie Stir Fry** (cookable) and
**Cheesy Garlic Bread** (2 missing) recipe-detail pages. Verified + deleted the
covered DORA_VERIFY bullets:

- **Sticky toolbar composition** — Mark cooked / Cook mode / Log cook… / Print /
  Save, plus the kebab (`mdi-dots-vertical`) → **New version · Delete recipe**;
  **no "CSV"** anywhere in the page.
- **Mark cooked** — server truth before/after: `available_meals` 2→3,
  `unallocated_meals` 2→3, `last_made_on` null→`2026-07-22` (today); toast
  "Marked as cooked."
- **Name validation** — name field editable; blanking it + Save shows the inline
  field error **"Give the recipe a name."** and the server name stays
  "Veggie Stir Fry" (save blocked). Save is **dirty-gated** (`aria-disabled` on a
  clean form) — so an unchanged-only Save is a no-op (the rename-to-own-name 422
  regression is separately backend-pinned).
- **Ingredient chips** — one chip per row, **Missing (`bg-negative`) wins** over
  Stocked (`bg-positive`); **missing rows carry a `.miss` red tint**
  (`rgba` ≈ salmon @ 0.09), stocked rows transparent. Legible in dark theme.
- **Cook-mode guard (not-cookable)** — Cook mode on Cheesy → dialog *"Start cook
  mode? This recipe isn't cookable now — 2 ingredients missing."* / Cancel /
  Start anyway; **Cancel closes without navigating** (stayed on detail).
- **Cook mode exit** — entering cook mode on the cookable recipe routes to
  `…/cook`; **Exit returns to the recipe detail page** (`/cookbook/<id>`), not
  the overview.
- **"Available meals"** label renders (`Available meals 2 unallocated of 2 cooked`).

**Left owner-walk** (survivors kept in DORA_VERIFY): sticky-stays-pinned at phone
width (layout), Log cook… N-meal dialog + Print-view render, ingredient-row-
without-a-stock-item save block (needs an engineered unlinked row), the cook-mode
guard's outside-click + unsaved-edits "Save & start" variant, and the meal-±
no-cursor-flash subjective check. Register row flipped ⚪→➗.

### Cook mode surface — Chunks 1–3 / 5 / 6 walked live (2026-07-22)

Drove **Veggie Stir Fry** cook mode (`…/cook`; cookable, freeform 3-step, 1 tool)
on the seeded backend. Verified + delete-on-pass:

- **Chunk 3 ingredient grouping** — one card per base location: Pantry (Jasmine
  Rice / Soy Sauce / Garlic), Fridge (Broccoli), Freezer (Chicken Breast).
- **No mid-cook stock-level chip** on rows (only substitute `mdi-swap-horizontal`
  buttons); **no checkboxes** anywhere (tick state gone).
- **Quantity spacing** — `300g` / `30ml` (mass/volume attach) vs `2 cloves` /
  `1 head` (word units spaced).
- **Sous Chef** voice button (`mdi-microphone-message`) + a **(?) "Sous Chef
  commands"** popover: Next / Previous·Back / Repeat / Start·Pause·Reset-timer /
  Exit. **"Done" is absent** (Chunk-5 item). The literal "8 commands" badge count
  is loose (7 lines / 8 if the Back alias counts) — matches the register's
  "8 commands count stale" note.
- **Step timer** auto-detected the "toss for 2 minutes" step → 02:00 + fill-bar;
  Start → live countdown (→01:58) + PAUSE/Reset; Reset → 02:00.
- **Unstructured fallback highlight** — step-1 text "Jasmine Rice" tinted its
  ingredient row (freeform recipe, so this is the text-match path, not structured).
- **"All steps"** (a `q-expansion` item) reveals the numbered step list; clicking
  step 3 jumps to **Step 3 of 3**.
- **Tools panel** renders ("Tools 1 total · Wok") because the recipe lists a tool.
- **Chunk 6** — "Cooking for" input defaults to the recipe `servings` (3); seed
  user has no `household_headcount`, so `servings` wins.

**Notable harness limits (not bugs):** (1) Quasar's numeric q-input ignores
synthetically-injected values, so the Chunk-6 blur-clamp (0/empty→1) and
session-only reset couldn't be driven — but `onCookingForBlur`
(`RecipeCookMode.vue:670`) is correct by inspection (`<1`/non-finite → 1, else
floor); left owner-walk, no finding logged. (2) `Escape` in cook mode exits to the
detail page (observed while dismissing an overlay). **Left owner-walk:** timer
expiry (negative colour + toast + beep — timing/audio), the structured-recipe
visuals (tint/left-accent/sub-step chip/hint lightbulb/tools-referenced dim — need
a structured seed recipe), no-tools-panel case, dark-theme tint, the deferred
finish flow (FU-591), and the no-location fallback group. Registers: Chunks 1–3
⚪→➗, Chunk 5 ⚪→🟡, Chunk 6 ⚪→➗.

**Chunk-5 structured visuals + Chunk-10 sections — finished same session
(2026-07-22):** no seed recipe had structured steps (all 11 freeform), so
**contrived one via the API** — `POST /api/recipes` `steps_mode:"structured"` with
3 steps (one sub-step via `parent_client_id`, hints, `ingredient_client_ids` +
per-step `tool_ids`), 3 stocked ingredients (→ cookable), 2 recipe tools, and 2
named sections (`sections[]` + `section_client_id`). Needed the `dora_csrf`
cookie echoed as `X-CSRF-Token` (raw fetch 403s otherwise — FU-197/571). Drove its
cook mode and confirmed: **step-referenced ingredient row** `highlight` + 3px left
accent + blue @0.16 tint (unreferenced flat); **referenced tool `highlight`
opacity 1 vs unreferenced tool `.dim` opacity 0.55**; **"Sub-step" chip** on the
sub-step card + **indent in All-steps** (32px vs 16px); **hint line + lightbulb
icon**; and (Chunk 10) **section chip on the step card** + **ingredient panel /
All-steps grouped by section**. Deleted the recipe afterward (`DELETE` → 204).
Chunk 5 ➗ (survivors: no-tools case, deferred finish flow, cross-theme tint);
Chunk 10 item "cook-mode section rendering" ticked in DORA_VERIFY. **Gotcha
banked:** a `location.hash` swap between two `…/cook` routes reuses the mounted
component without re-fetching — hop via the detail route (or another page) first
to force a fresh mount.

### Cookbook detail edit-mode + personal notes walked live (2026-07-22)

Drove Veggie Stir Fry's recipe-detail editor. Verified:

- **Personal notes (FU-432)** — the **Personal notes (optional)** field sits
  **below Source URL** (field tops 1691 vs 1601) and is a **distinct textarea**
  from the freeform instructions field (own placeholder). PATCHed a two-line note
  on → cook mode rendered a **"Your notes" card** with **the line break preserved**
  ("Line one… ⏎ Line two…"); note-free recipes show **no** card. Cleared the note
  after (PATCH `notes:null` → 204). Register ✅.
- **Mode toggle (image-steps)** — **Structured / Freeform / Image** each render
  their own editor; the freeform 199-char payload **survived a Structured → Image
  → Freeform cycle** (non-destructive, freeform half). Register 🟡 (image-editor
  specifics + structured/image preservation + camera/voice packs remain).
- **Tools multiselect** populates on the detail page ("Wok"); `tool_ids`
  round-trips on create (the contrived structured recipe's 2 tools rendered).

**Banked:** the detail page has an **unsaved-changes route guard** — "Discard
unsaved changes? Your edits will be lost. / Cancel / Discard" — and the
`…/cook` route **nests under** the detail route, so a dirty detail form's guard
fires (and can silently keep you on detail) when you navigate hash→cook. To reach
cook mode cleanly after editing, discard first or unmount the detail form by
hopping to a non-recipe route (`#/` dashboard) before the cook nav.

### RecipeEditDialog stub-creator (FU-095) walked live (2026-07-22)

Cookbook overview → **New recipe**: the modal shows **exactly four fields**
(Name* / Cuisine / Category / Collection) with **no** ingredients/image/
instructions/dietary/tools/times; primary button **"Create & open"**; **Cancel**
on an empty form created nothing (count 11→11); filling Name "QA Stub Recipe" +
Create & open **closed the dialog and navigated to `/cookbook/<new-id>`** (detail
page, name populated). Deleted the stub after (`DELETE` → 204). **Edit-from-
overview is N/A by design** — recipe cards expose only ♥ / chef-hat / add-to-list
footer icons and there is **no edit/pencil action anywhere on the overview** (deep
edit is on the detail page); the RecipeEditDialog edit-mode isn't surfaced from the
overview. (Minor: item 248's "card kebab" framing looks stale — the card actions
are direct footer icons, not a `⋮` menu. Left as-is; item 248 stays owner-walk.)
Register ✅.

### Recipe importer paste flow + bulk-linker walked live (2026-07-22, two rounds)

**Round 1 — paste-based rebuild (C5):** Cookbook → **Import** opens the paste
dialog (textarea + "Where's this from?" URL + caption naming the Ctrl+A/Ctrl+C
flow & supported sites). Pasted a synthetic "Zesty Quinoa Salad" page + source URL
→ **Import → new recipe on the detail page, no degraded banner.** Server parse:
`name`, `servings=4`, source stored, **3 freeform steps**, **5 ingredients** with
`raw_text` preserved. **Fuzzy matcher linked "extra virgin olive oil" → Olive Oil**;
the other 4 stayed unlinked and render as **"Free-text ingredient"** rows with the
quoted text (confirmed on fresh GET). `cookable=null` (neutral) with unlinked rows.

**Round 2 — bulk-linker (C6), fed by round 1's 4 unlinked rows:** sidebar entry
present; page lists each as **`raw_text · Used in 1 recipe`** (FU-588 "0" bug gone)
with autocomplete / Link / Create-new. **Create new** on "1 lemon, juiced" →
toast **"Created "1 lemon, juiced" and linked in 1 recipe."** (item = raw_text),
group count 4→3, and the source recipe's lemon row became linked
(`unlinked_ingredient_count` 4→3, cookability still `null`). Cleaned up: deleted
the created stock item + the imported recipe (204/204; recipe count back to 11).

**Owner-walk left:** the Link-existing autocomplete + toast (Quasar q-select not
synthetically drivable — same limitation as the numeric input; endpoint pinned in
`test_unlinked_ingredients_bulk_link.py`), the empty-state, the multi-site parse
corpus (backend-pinned), and the Android PWA share target. Both registers ⚪→➗.

### BIG ROUND — recipe versions + MealStepper + cost/nutrition off-state (2026-07-22)

Three Cookbook sub-surfaces in one pass on Veggie Stir Fry (has 5 ingredients).

**A. Recipe versions (Chunk 8, FU-105) → ➗.** Singleton **hides** the "Other
versions" card. Kebab → **New version** created **"Veggie Stir Fry (v2)"** with
**no 500** — a live confirmation of the **FU-590** fix (new-version of a recipe
*with* ingredients used to 500) — navigated to the copy, which **shares a
back-filled `version_group_id`** with the source (both list 1 sibling), **inherited
all 5 ingredients + cuisine + servings**, and **started un-favourited**. The
**"Other versions" card + "v2" label** render on the copy; the **source shows the
card too** once it has a sibling. **Deleting v2** (→204) returned the source to a
singleton and the **card disappeared** (delete→card-updates). Source left with an
orphan group-of-1 id (harmless; seed disposable).

**B. MealStepper (Chunk 3 item 233) → 🟡.** On the detail page the ± **live-adjusts
the cooked pool** 3→2→1→0; **"Remove one meal" disables at 0**; restoring via +
persisted (server `available_meals`=3). Allocated badge (needs a meal-plan
allocation for `committed_meals>0`) + the card/stock-item-detail instances remain.

**C. Cost/nutrition (Chunk 9 item 201) → 🟡.** `/api/health` `features.money=false`
+ `nutrition=false`; in that state the detail page has **no kcal input / no cost
card / no nutrition card** and the overview has **no Kcal sort or filter**. The
**flags-ON** items are **harness-blocked**: flags are read once at cold mount
(FU-586) and flipping them needs a reload, which re-sticks the hidden-pane splash
(the rAF shim can't retroactively un-suspend the already-scheduled splash-dismiss).
Left owner-walk; cost math is backend-pinned regardless.

### BIG ROUND #6 — Batch 11 C-9.5 price watch cleared (money seed) (2026-07-23)

Continued on the money-on seed (no reboot). Cleared the previously money-blocked
**C-9.5 price-watch tier** end-to-end. No code changed.

**Arming.** The explorer's arm control is a per-product "Notify me below ($)"
q-input + "Set alert" (`PriceHistoryPage.vue:200-217`); the card didn't render in
the hidden pane (chart svg present, 0 number inputs — a rAF/render quirk), so I
armed via `POST /price-history/alerts {product_id, threshold_unit_price}` — exactly
what "Set alert" calls (line 380). Armed Coles Full Cream Milk 2L @ $2.50
(current $2.90).

**Panel (SubscriptionsPanel on the Alerts hub) — all verified:**
- Empty-state: "No price watches armed." + explorer hint.
- Armed → panel lists "Coles Full Cream Milk 2L" · "Coles · notify below $2.50"
  (product · merchant · notify-below, money-formatted) + View + Remove.
- **View** → `#/price-history?product_id=…`, product pre-selected.
- **Remove** → toast "Price watch removed.", server list → 0, panel back to empty.
- **Money-off gating:** `SubscriptionsPanel v-if="money"` where `money` =
  `useFeatureFlags()` = `/api/health features.money` = **install**
  `money_enabled`. Turning off the *per-user* `money_features_enabled` did NOT
  hide it (correct — wrong level); turning off the *install* flag (PATCH
  `/app-settings money_enabled=false` + reload) DID hide it while the hub still
  rendered. Restored both flags after.

**[[FU-604]] logged:** the panel gates on install money, but the trim-to-budget
banner (FU-448) gates on the per-user `money_features_enabled` — a split gate. A
user who opts out of money features still sees the price-watch panel. Confirm-intent
(either the panel should also check the per-user flag, or trim is the odd one out).

**Residuals:** the **last-alerted** timestamp (needs a watch that has actually
fired) and driving the **arm** q-input in-pane (didn't render).

**Data hygiene:** the armed alert was removed during the Remove test (server 0);
both money flags restored to on. Clean.

---

### BIG ROUND #5 — Batch 9 Cart Button (C2/C3-UI/C4) on the money seed (2026-07-23)

First round using the **money-on** seed knob (FU-592). Added a
`dora-verify-backend-money-linux` launch entry (the existing `-money` config is
Windows-pathed). Booted it, confirmed `/api/health` money+nutrition+buy_verdict
true and the seed user `money_features_enabled:true` / `nutrition_mode:simple`.
No code changed this round.

**Cart Button Chunk 2 (FU-130) — fully walked.** `AddToListButton` is a toggle:
carting an item already on a draft REMOVES it (FU-454), which explained a 5→4
line count I first mis-read as data loss — it was my own toggle-off of Full Cream
Milk. With milk then off all lists (2 products): cart → **QuickAddSheet** with the
target-list dropdown + offer radios (No offer / Coles $2.90 / Woolworths $3.10) +
quantity, all in ONE surface (no stacked modal even with 2 drafts) → Add →
"1 added." 0-product item → a "Which list?" picker (2 drafts) → pick → silent add
"Added to This week." (no product modal). Source confirms `shouldUseCombinedModal
= linked_product_count >= 2`, so 0 and 1 share the same direct `addToList` branch;
verified 0 empirically. `linked_product_count` present on `/stock-items`
(milk=2, 0-default). The **2026-06-14 "picker not popping" repro does NOT
reproduce**. Survivor: bulk-add summary toast.

**Chunk 3 UI (FU-145) — product-only line verified.** "Add as product" on an
unlinked product (Cadbury Freddo Cake) → 2+-drafts "Which list?" picker → line
lands with `product_id` set + `stock_item_id:null` (Rule-1 backend), toast "Added
as product line.", and renders with the `.shopping-line-product-only` class,
a distinct tint (`rgb(22,39,36)` vs a normal line's transparent bg) and a product
chip. Survivors: rule-2 later-link nesting, rule-4 nested-remove modal, the
no-modal removal case, onAddSingle on already-linked rows.

**Chunk 4 (FU-135) — the Axis-B generate picker.** 2+ drafts → "Add to which
list?" lists all drafts + "+ Create new list". **Cancel** → no list, no toast, no
nav. **Merge into existing draft** (This week preselected) → "Added N items to
your list" + routes to it (0 new items — the well-stocked seed plan had nothing
unstocked). **+ Create new list** → creates "Meals: week of 20/07/2026" + "Shopping
list created with 1 item." + routes to the new list. Survivors: the 0-draft and
1-draft *count-specific* cases (need the draft count changed) and `nothing_to_add`
(the seed plan always carried ≥1 shortfall item, so I couldn't force the
empty-add path).

**[[FU-603]] logged** — the cart tooltip says "Add to a **draft** list" but the
QuickAddSheet targets any non-done list (incl. in-progress shops) and defaulted to
"Saturday shop". Low-priority copy/default nuance, not a bug.

**Data hygiene:** every mutation reverted — the create-new "Meals:" list deleted,
the Freddo product-only line deleted, Butter (added during a 0-product test)
deleted; all five seed lists back to their original counts. **One residual drift:**
Full Cream Milk on "This week" is now qty-1 at the last position (I re-added it via
the modal after the toggle-off test) vs the seed's qty-2 first line — cosmetic, in
a throwaway DB.

---

### BIG ROUND #4 — Batch 13 (Settings B) opened: CSRF/account + assistant contracts; FU-599 (2026-07-22)

No code changed this round — everything passed or became a finding.

**Account + CSRF defence (FU-197), 8/11 cleared.** Cookie is `Path=/; SameSite=Lax`
and deliberately **not** HttpOnly (double-submit needs JS to read it); no `Secure`
because `DORA_SECURE_COOKIES` is unset, so that leg stays an env check.
`PATCH /auth/me {email}` → 400 `extra_forbidden`. The CSRF gate was proved in
**both** directions from a cold curl jar: no header → 403, same call with the
header → 200, and a cold login with neither cookie nor header → 200 (public
endpoints exempt). Instrumented `fetch` + `XMLHttpRequest` and drove four real
mutations across three surfaces — every one carried `X-CSRF-Token` matching the
cookie. Email-change UI: enable-gate, wrong-password toast with the 422 reason,
right-password toast + cleared field + address unchanged. Audit emitted
`auth.email_change.requested` (audit) and `auth.email_change.password_failed`
(warn).

**[[FU-599]] — audit double-logging.** `auto_audit_after_request` writes a row per
successful mutating `/api/*` call; handlers that also call `audit_emit` log twice
under two different names (`request_email_change` + `auth.email_change.requested`
for one operation). `_NO_AUDIT_ENDPOINTS` exists for exactly this but lists only
`login`/`logout`, so ~10 other explicit emitters double-log. Left unfixed on
purpose: suppressing the generic row where the explicit emit is thinner would
*lose* audit coverage, which is worse than a duplicate — each endpoint needs
checking first.

**Assistant (FU-153) API contracts cleared:** `has_llm_api_key` present with no
plaintext key; cross-field PATCH → 422 with the exact message; health tracks
`master_llm_enabled`; hygiene grep clean; kill-switch driven both ways (health
flips, install-wide banner appears/clears, per-user toggle force-disabled).

**FU-285** both copy items confirmed at source (meal slots overrides
`empty-action`; the other four inherit the default).

**Two self-inflicted near-misses, both caught before filing:**
1. Admin routes kept landing on Account — not a routing bug, the **Account page's
   unsaved-changes guard** firing on a dirty email field left from the
   email-change test, stacking six hidden "Discard unsaved changes?" dialogs.
2. Grepped `emptyAction` (camelCase) and nearly filed FU-285 as regressed. Vue
   templates use kebab-case: `empty-action="…"` was present and correct.
   **Grep both cases for a Vue prop.**

**Environment:** FU-595 freeze state cleared; settings restored. Residue: a
**pending email change** to `newaddr@example.com` on the account (inert — needs a
click on an email that SMTP can't send).

---

### BIG ROUND #3 — Batch 11 (Alerts) opened; history copy bug fixed; FU-597/598 (2026-07-22)

Batch 7's remaining items need DnD automation or are blocked ([[FU-592]]/[[FU-595]]),
so this round opened **Batch 11 — Alerts**, previously untouched.

**Fixed — "out of_stock" in the hub's History.** `AlertsPage.vue:204` used
`entry.kind.replace('_', ' ')`; a string pattern replaces only the FIRST match, so
`out_of_stock` printed as "out of_stock" while the Manage panel two blocks above,
reading `ALERT_KIND_META`, said "out of stock". Added `kindLabel(kind: string)` to
`models/alert.ts` (meta lookup + humanise-every-underscore fallback, because
history rows type `kind` as a bare string — a stored row can outlive its kind) and
used it. Kills a duplicated display mapping as a side effect. 3 Vitest tests added
and confirmed red against the old expression; suite 408 → 411; vue-tsc + eslint
clean; verified live after a rebuild.

**[[FU-597]] — the Alerts page serves a stale feed.** `AlertsPage.vue:435-438`
refetches on mount **only** when the store is empty. Planned a meal → server
dropped `no_planned_meals` (FYI 18→17) → `/alerts` still showed the row, the
"1 meals to plan" tile and "18 FYI" until Refresh. The store self-refreshes after
actions taken *on* the alerts surface, so the gap is changes made elsewhere —
i.e. most of what actually resolves an alert.

**[[FU-598]] — primary and positive collide in the default theme.** Measured both
tokens across all five themes: Pesto `#359766`/`#359766` (identical), Cherry Cola
`#a6e085`/`#89d65c` (near-identical). The Upcoming timeline uses three correct
distinct tokens, but its shopping and meal dots therefore render the same on
Pesto; the legend doesn't help because its swatches are those same colours.

**Method note — a bogus finding I caught before filing.** The timeline showed no
shopping dot after I set a `planned_shop_date`, and I started writing it up as a
broken category. It wasn't: I'd sliced the JSON response at 900 chars and read
`shopping: []` off dates that weren't the one I'd set. Querying the specific date
showed the server correct. **Don't reason about absence from a truncated payload.**

**Walked green:** badge == actionable count (36, tier-verified); snooze persists
across reload and is correctly kind-scoped (another kind on the same item
survived); dismiss hides on page + peek + dashboard with badge consistent; C-9.2
threshold round-trip 7→2→7 (expiring_soon 13→2) + disable-a-kind (11 rows) +
demote/promote (`expired`: actionable 34↔23, FYI 18↔29) with a clean restore to
34/18; C-9.3 hub structure, slim peek, History with stock names resolved; C-9.4
both nudges end-to-end; C-9.6 timeline dots / opacity-0.35 out-of-window / today
ring / click-expand / all three link targets; FU-357 reconcile row renders +
navigates with no ErrorBoundary; SMTP + VAPID off-gating captions, health flags,
and `/api/alerts/push/vapid-public-key` → 404.

**Doc drift:** the "Alerts email digest" card is on Settings → **Notifications**,
not Preferences as the checklist says.

**Environment left:** thresholds restored (window 7, auto-drain on), but
`data/dora.dev.db` carries three backdated unconsumed entries (07-15/16/17) from
the reconcile-overdue setup — the current week is therefore in the **FU-595**
freeze state. Clear them before walking planner adds.

---

### BIG ROUND #2 — Batch 7 cont.: C-2 planner walk; FU-595 freeze bug; print-view "None" fixed (2026-07-22)

Same environment, second chunk. Sections cleared: **meals-per-week 5/5** (deleted),
**in-context Print 3/4**, **useListState remainder 3/4**, plus most of the C-2 /
R-Phase planner walk.

**FU-595 — production-severity, logged not fixed.** Adding any meal to a week that
holds a **past-dated entry with `consumed_at IS NULL`** returns
`400 "Meal plan entries cannot be scheduled in the past."` and the error escapes to
the ErrorBoundary — the whole planner is replaced by "Something went wrong on this
screen." `UpdateMealPlanHandler` preserves history by `consumed_at is not None` but
validates submissions by `scheduled_for < today`, so a past-but-unconsumed entry is
unrepresentable: the server won't keep it, the client must resend it, and resending
it is rejected. Isolated by consuming the single offending entry and replaying the
identical clicks (succeeds). Reachable via **auto-drain OFF** and via **reconcile →
"Didn't cook"**. Left as an FU — three viable contract fixes, owner's call.

**Print-view "None" — found + fixed.** `export_meal_plan.py` rendered
`{{ plan.name }}` raw; the planner makes nameless week-plans by design (C-2.E), so
every planner print was titled "None" in both `<title>` and `<h1>`. Now falls back
to `Week of <start_date>`; verified live after a backend restart.

**Test-writing care point.** The first version of the pin was **vacuous** — it hung
off `if plans[0].get("name") is None`, and the seeded plans all have names, so it
passed identically with the fix reverted. Rewrote as a standalone test that POSTs a
nameless plan, then proved it red-without / green-with. Seed-conditional assertions
silently skip; don't write them.

**FU-596** opened: the step-by-step builder spreads meals one-per-day correctly but
files every one under **Breakfast**.

**Walked green:** meals-per-week (blank→/7, 5→/5 without reload, `3.7`→4 rounded,
`99`→reset toast + blank field); Print (desktop header icon, mobile week-nav
placement right of Next-week, hidden on meal-less weeks, `/meal-plans/board`
redirect); useListState (groupBy persists across nav, carries across a list switch,
sign-out clears both); C-2 (tap-add honours the chosen slot — F35 holds; ± live
adjust + remove-at-0; past days `--past` opacity 0.6 with zero clickable rows;
implicit create on an unplanned week + sidebar flip; Clear-week confirm→empty;
calendar 6 weeks / today dot / focused outline / week-click jump + back / `?monday=`
across reload / old dropdown gone; sidebar list-status rows; builder 3-step
end-to-end with preview matching the sidebar).

**Survivors** are now mostly drag-and-drop (needs DnD automation), C-2.F/G template
apply + recurring, carousel arrows/keys, off-vocab "Other" row, the unlinked-
ingredient dialog, and the money-gated budget swaps ([[FU-592]]).

---

### BIG ROUND — Batch 7 Meal plans: reconcile cleared, real 404 bug fixed (2026-07-22, Linux box)

First verify session driven from the **Linux** checkout (`.venv/bin/python`; added a
`dora-verify-backend-linux` entry to `.claude/launch.json` — the existing one hard-codes
the Windows `.venv\Scripts\python.exe`). SPA rebuilt (`quasar build -m spa`) first;
`dist/spa` had been 4 days stale. Browser-driving recipe extended — see **RECIPE v2**
in the top banner (reload is safe and necessary; resize must precede the mount).

**REAL BUG FOUND + FIXED — reconcile recap "Done" → 404.**
`MealReconcilePage.vue:153` had `:to="'/dashboard'"`; there is no `/dashboard` route
(the dashboard is `/`), so the final tap of the reconcile flow landed on the "This page
wandered off" 404. Grep confirmed it was the **only** `/dashboard` navigation in the SPA
(the same file's other two `:to`s were already correct). Fixed to `'/'`, rebuilt,
re-walked: Done → `#/` → "Dashboard | Dashy Dora", no 404, chip gone. `vue-tsc --noEmit`
clean. CHANGELOG entry under Fixed.

**Meal reconcile (FU-317 C5/C6) — 14 of 15 walked, all pass.** Pool math was verified
against the DB/API at every step, not just the UI:
- Chip lives in the **Your kitchen** zone — proved via computed CSS `order` (chip 315
  sits between the `YOUR KITCHEN` label at 299 and the next card), since the dashboard
  grid's DOM order is not its visual order.
- Verb hierarchy measured: Cooked 430px filled `bg-primary`; Different portions +
  Cooked later 211px each on one row; Didn't cook full-width `text-negative`; Skip
  116px ghost.
- **Cooked** (auto-drain ON) → pool unchanged (sweep already drained). **Different
  portions** 5-on-planned-2 → 10→7. **Cooked later** → `resolved_confirmed` +
  `cooked_on=2026-07-20`, pool unchanged. **Didn't cook** → 9→sweep 5→restored 9,
  entry leaves queue. **Skip** → stays queued as `resolved_deferred` (→ [[FU-594]]).
  Deferred→Cooked correctly re-drained 14→10 (corrective-receipt math is sound;
  receipts are append-only, never mutated).
- **Auto-drain OFF**: sweep wrote `unresolved_manual` and left the pool at 10; the
  Cooked verb then applied the drain → 6.
- **Threshold** (3 entries, oldest 5 days back): alert `meal_reconcile_overdue`
  fired with the exact copy; the `reconcile_meals_pending` suggestion only appeared
  after clearing the high-severity noise → [[FU-593]].
- Empty state, help dialog (lists all five verbs), XL text-scale (root 16.5→23px;
  card/buttons/name/dialog all tracked it), themes (Pesto dark/light + Cherry Cola
  light — page, card bg+fg, primary and negative all move; no hardcoded colours),
  admin settings page (toggle + toasts + persists across reload) + nav row.
- **Survivor:** the non-admin "You don't have admin permissions" banner (needs a
  second account). Nav-row icon is `mdi-calendar-edit`, not the "event-note" the
  checklist names — cosmetic doc drift, not a defect.

**Templates drawer (FU-308) — 7/7, section deleted.** Row actions are
Apply + pencil + `content-copy` + `delete-outline` (clone icon between rename and
delete, as specced); Clone → toast "Cloned." → "Verify Week (copy)" appears;
Manage rotating sets → drawer closes + navigates; sets page header/caption correct
with no Templates card; the New-set picker still lists every template; deep-link
title "Rotating template sets"; `goToManageTemplates` is gone from `useMealPlanner.ts`.

**Show-all-slots (FU-306) — 5/6.** Off by default, on → all five slots per day,
survives hard reload both ways, `mealPlanShowAllSlots` `'1'`/`'0'`. Storage-disabled
case driven for real (redefined `window.localStorage` to throw): toggle still works
in-session, no toast, no console throw. Survivor: the cross-browser per-device item.

**useListState (FU-354/355) — 4/8.** Picker search filters + survives
nav-away-and-back; hard reload resets it; `CACHE` is still a module-scope `Map`.
Survivors are the shopping-list groupBy half + sign-out/401 clearing.

**C-2.I trays — partial.** Four groups render; search collapses to "Results (N)";
"Frequently planned" ranks by plan frequency (Spaghetti 3 > Egg Fried Rice 2 >
Tomato Pasta 1, matching the week). Survivors: hide-when-empty, 21-day window.

**Environment note:** past-dated entries can't be created through the API
(`CreateMealPlanHandler` rejects `has_past_entry`), so the queue was contrived by
backdating rows in `data/dora.dev.db` and re-firing the sweep via
`GET /api/meal-plans/today`. That DB also had 23 stock expiries pushed to
2026-12-01 to unmask the reconcile suggestion — it is a throwaway seed DB
(`preview_start` re-seeds with drop_all), so no restore was attempted.

---

### Money/nutrition ON-state — attempted, hit a harness wall → FU-592 (2026-07-22)

Tried to unblock the Chunk 9 flags-ON items (+ buy-verdict/budget by extension).
PATCHed the install flags on (`/api/app-settings money_enabled+nutrition_enabled`
→ `/api/health` reflects true, even unauthenticated) — but the SPA didn't render
the surfaces. **Root cause (fully diagnosed):** the surfaces gate on **both** the
install flags **and** the **per-user prefs** (`/api/auth/me`
`money_features_enabled:false`, `nutrition_mode:"off"` for the seed `dora` user),
and **all of these are read once at cold mount** (health probe + authStore
currentUser). Mid-session API PATCHes don't re-render (stores stale); a reload
re-sticks the rAF splash; and the login-form path to force a fresh authed mount is
blocked by the **q-input synthetic-injection limitation** (values set in the DOM
but Quasar's v-model stays empty, so the login handler no-ops).

**Also learned:** logout does NOT reset the DB install flags/prefs; and a fresh
`preview_start` **re-seeds** (drop_all+create_all), reverting all of it — which I
used to restore a clean default state (`/api/health` money/nutrition back to
false, confirmed). Chained recovery `logout → reload-to-login → shim →
fetch-login → in-app nav` re-paints content only when the fetch-login **races**
the initial auth probe (works right after a fresh `preview_start`; not after the
probe has resolved logged-out).

**Outcome:** no new verification beyond re-confirming item 201's off-state; the
ON-state remains owner-walk pending **FU-592** (a `DORA_SEED_MONEY_ON` seed knob
that boots money+nutrition on for a clean authed cold mount). Preview left
freshly re-seeded (flags default-off).

---

## Section register

Status per section. Lines are the 2026-07-16 snapshot. "Env" lists only hard
gates (flags, PG, Docker, device, built PWA). Test-pinned = the origin fix
already has regression tests (low-risk re-confirm, per CHANGELOG/worklog).

### Top block (recent surfaces)

| Section | Lines | Items | A/V/H | Stale | Env / notes | Status |
|---|---|---|---|---|---|---|
| Onboarding story pass (2026-07-12) | 11–21 | 9 | 8/0/1 | 0 | fresh install; reduced-motion (emulable) | ⚪ |
| Dora assistant / helper bubble (FU-429+360) | 22–38 | 15 | 15/0/0 | 0 | LLM configured + no-LLM user; 2 accounts | ⚪ |
| Currency & locale (FU-043) | 39–49 | 9 | 8/0/1 | 0 | admin; mic item H | ⚪ |
| Native Android build (P8-10) | 50–62 | 11 | 2/0/9 | 1 | Android toolchain + device → device pack | ⚪ |
| StoresSettings logo upload (FU-335) | 63–70 | 6 | 5/0/1 | 0 | sample images; camera item H | ⚪ |
| SettingsFileDrop (FU-545) | 71–81 | 5 | 5/0/0 | 0 | admin; sample files | 🟡 pilot |
| BuyVerdictCard one-tap (FU-454) | 82–89 | 6 | 6/0/0 | 0 | engineered verdict states | 🟡 pilot |
| Password policy (FU-442) | 90–99 | 8 | 8/0/0 | 0 | registration open; DB-seed legacy account | 🟡 pilot |
| PWA install + offline (FU-336) | 100–110 | 8 | 5/0/3 | 0 | **built PWA over HTTPS/localhost**; iPhone items H | ⚪ |
| Runtime backend URL | 111–115 | 3 | 3/0/0 | 0 | deliberately breaks connectivity — reversible | 🟡 pilot |

### Cookbook & recipes + Cook mode

| Section | Lines | Items | A/V/H | Stale | Env / notes | Status |
|---|---|---|---|---|---|---|
| Cookability + expiring filters | 132–138 | 6 | 6/0/0 | 0 | test-pinned (4 filter tests) | ⚪ |
| Free-text ingredient path (FU-506) | 140–146 | 6 | 6/0/0 | 0 | | ⚪ |
| RecipeEditDialog stub-creator (FU-095) | 148–154 | 6 | 6/0/0 | 0 | walk 2026-07-22: 4-fields-only modal / "Create & open" / Name→navigates-to-detail / Cancel-creates-nothing verified; edit-from-overview N/A (no edit surface on cards — by design) | ✅ |
| Importer bulk-linker + share target (C6) | 156–168 | 12 | 11/0/1 | 0 | walk 2026-07-22: sidebar entry / group-rows "raw_text·Used in N" (FU-588 count OK) / Create-new (item=raw_text, links, toast) / recipe-row-linked+count-drop verified; survivors = empty-state, autocomplete+Link UI (q-select not synthetic-drivable, endpoint pinned), Android share | ➗ |
| Importer paste-based rebuild (C5) | 170–179 | 9 | 9/0/0 | 0 | walk 2026-07-22: Import dialog / paste→parse (name/servings/source/3 steps/5 ingredients) / fuzzy-link olive-oil + 4 free-text raw_text preserved / neutral cookable=null; survivors = multi-site corpus (backend-pinned), link-one-row-switches-back | ➗ |
| Ingredient DnD (FU-118/161) | 181–195 | 14 | 14/0/0 | 0 | drag automation | ⚪ |
| Chunk 6 structured steps (FU-093) | 197–206 | 9 | 9/0/0 | 2 | SQLite+PG alembic | ⚪ |
| Chunk 7 source URL + URL importer (FU-103) | 208–217 | 9 | 9/0/0 | 4 | mostly stale — URL importer deleted | ⚪ |
| Chunk 8 recipe versions (FU-105) | 219–230 | 11 | 11/0/0 | 0 | walk 2026-07-22: New-version (v2 numbering, shared back-filled group, siblings, un-favourited copy, ingredient/cuisine/servings inherit, no-500 live=FU-590) + "Other versions" card on both + delete→card-updates verified; alembic/structured-toggle/richer-clones/backup remain | ➗ |
| Chunk 9 cost + nutrition (FU-116) | 232–247 | 15 | 14/1/0 | 0 | walk 2026-07-22: flags-OFF state verified (no kcal input/cost card/nutrition card/Kcal sort+filter); flags-ON items HARNESS-BLOCKED (flags read once at cold mount, reload re-sticks splash) → owner-walk | 🟡 |
| Chunk 10 multi-part sections (FU-119) | 249–255 | 6 | 6/0/0 | 0 | SQLite+PG alembic | ⚪ |
| Chunk 4 detail cleanup (FU-089) | 257–266 | 9 | 8/1/0 | 0 | detail walk 2026-07-22: toolbar+kebab / Mark-cooked / name-validation / chip-Missing-wins+tint / not-cookable guard+Cancel / cook-mode exit→detail verified; layout+dialog-flow survivors | ➗ |
| Chunk 3 card redesign (FU-088) | 268–274 | 6 | 6/0/0 | 1 | walk 2026-07-22: MealStepper ± live-adjust + decrement-disabled-at-0 + server-persist verified (detail page); allocated badge (needs meal-plan alloc), card kebab (cards have footer icons not a ⋮), meals-box eyeball remain | 🟡 |
| Chunk 3+ revision (FU-088r) | 276–288 | 12 | 12/0/0 | 0 | 2 sessions for per-user persistence | ⚪ |
| Chunk 5 images + tools (FU-091) | 290–296 | 6 | 6/0/0 | 0 | image files incl. >4MB | ⚪ |
| Chunk 2 tag taxonomy (FU-085) | 298–303 | 5 | 5/0/0 | 0 | | ⚪ |
| FU-085 second round (FU-151) | 305–311 | 6 | 6/0/0 | 0 | assistant enabled | ⚪ |
| Recipe image-steps mode | 313–321 | 8 | 6/0/2 | 0 | walk 2026-07-22: mode toggle (Structured/Freeform/Image each render own editor) + freeform-payload non-destructive flip verified; image-editor specifics + structured/image preservation + camera/voice → packs remain | 🟡 |
| Personal notes in cook mode (FU-432) | 327–331 | 4 | 4/0/0 | 0 | walk 2026-07-22: server contract pinned + detail-field placement (below Source URL, distinct textarea) + cook-mode "Your notes" card w/ line breaks + no-card-when-noteless all verified | ✅ |
| Cook Mode Chunks 1–3 (FU-096) | 333–344 | 11 | 10/0/1 | 0 | walk 2026-07-22: location grouping / no-level-chip / qty spacing / Sous Chef popover / timer detect+countdown+reset verified; survivors = timer expiry + no-location fallback | ➗ |
| Cook Mode Chunk 5 (FU-100) | 346–356 | 10 | 8/1/1 | 1 | walk 2026-07-22: freeform path + structured visuals (tint+3px-accent / tool light-vs-dim / Sub-step chip+indent / hint+lightbulb) via a contrived structured recipe; survivors = no-tools case, deferred finish flow, cross-theme tint | ➗ |
| Cook Mode Chunk 6 rescale (FU-101) | 358–369 | 11 | 10/1/0 | 0 | walk 2026-07-22: "Cooking for" defaults to servings verified; clamp code-correct (RecipeCookMode.vue:670) but not synthetically drivable → clamp+session-reset owner-walk | ➗ |

### Meal plans + Shopping lists

| Section | Lines | Items | A/V/H | Stale | Env / notes | Status |
|---|---|---|---|---|---|---|
| Meal reconcile (FU-317 C5) | 375–390 | 15 | 13/2/0 | 0 | walk 2026-07-22: all 5 verbs + both auto-drain modes with server-verified pool math / chip+header nudge / threshold alert+suggestion / empty state / help dialog / XL type-scale / 3 themes / admin page; **404 bug found+fixed** (Done→`/dashboard`); [[FU-593]] + [[FU-594]] opened; survivor = non-admin banner | ➗ |
| Budget-defense swaps (FU-451) | 392–400 | 8 | 8/0/0 | 0 | money on; budget; over-budget week | ⚪ |
| Unlinked-ingredient warning (FU-505) | 402–408 | 6 | 6/0/0 | 0 | | ⚪ |
| Meals-per-week pref (FU-181) | 410–416 | 6 | 6/0/0 | 0 | walk 2026-07-22: input+placeholder / blank→builder `/7` / 5→toast+`/5` without reload / clear+out-of-range→reset toast+blank / `3.7`→rounds to 4 — **section deleted** | ✅ |
| In-context Print (FU-338) | 418–422 | 4 | 4/0/0 | 0 | walk 2026-07-22: desktop header icon / mobile week-nav placement + hidden on meal-less weeks / `/meal-plans/board` redirect; survivor = the popup tab itself (endpoint renders correctly) | ➗ |
| useListState sweep (FU-354/355) | 424–432 | 8 | 8/0/0 | 0 | walk 2026-07-22: picker search filters + survives nav-away/back, hard-reload resets, `CACHE` still module-scope `Map`; survivors = shopping-list groupBy half + sign-out/401 clearing | 🟡 |
| Show-all-slots persistence (FU-306) | 434–440 | 6 | 6/0/0 | 0 | walk 2026-07-22: default-off / on→all 5 slots / persists both ways across hard reload / `mealPlanShowAllSlots` `'1'`‑`'0'` / storage-throw drive (works in-session, no toast, no throw); survivor = cross-browser per-device | ➗ |
| Templates drawer (FU-308) | 442–449 | 7 | 7/0/0 | 0 | walk 2026-07-22: Apply/pencil/content-copy/delete-outline row / Clone→"Cloned."+copy appears / Manage-sets closes+navigates / sets-page header+caption, no Templates card / New-set picker lists all / deep-link title / `goToManageTemplates` gone — **section deleted** | ✅ |
| Planner R-Phases 1–6 (FU-305) | 451–459 | 8 | 8/0/0 | 0 | | ⚪ |
| Meal Plans C-2 full walk (FU-179) | 461–476 | 15 | 15/0/0 | 2 | | ⚪ |
| Substitute-swap gating (FU-407) | 482–486 | 4 | 4/0/0 | 0 | | ⚪ |
| Put-away dialog (FU-452) | 488–500 | 12 | 12/0/0 | 0 | | ⚪ |
| Quick-add toast + pref (FU-316) | 502–510 | 8 | 8/0/0 | 0 | | ⚪ |
| Receipt-photo attachments (FU-334) | 512–524 | 12 | 10/0/2 | 0 | phone camera items → device pack | ⚪ |
| Image-source picker sweep (R-024) | 526–531 | 5 | 4/0/1 | 0 | camera item → device pack | ⚪ |
| Trim-to-budget + Deferred (FU-448) | 533–547 | 14 | 14/0/0 | 0 | money on; rich line mix | ⚪ |
| Shopping list UX v2 (FU-165) | 549–563 | 14 | 14/0/0 | 0 | | ⚪ |
| Cart Button C2 (FU-130) | 565–572 | 7 | 7/0/0 | 0 | walk 2026-07-23 (money-on): 2+-products→QuickAddSheet (in-sheet target dropdown + offer radios + qty, ONE surface no stacked modals) → Add→"1 added."; 0-product→"Which list?" picker→silent add "Added to This week."; 1-product shares the same `addToList` branch (`shouldUseCombinedModal = lpc>=2`, src); `linked_product_count` present (milk=2, 0-default); the 2026-06-14 no-pop repro does NOT reproduce. Also confirmed the button is a toggle (on-list→remove, FU-454). Survivor: bulk variant. [[FU-603]] opened (tooltip "draft" vs any-active target) | ➗ |
| Cart Button C3 API (FU-132) | 574–580 | 6 | 6/0/0 | 0 | SQLite+PG | ⚪ |
| Cart Button C3 UI (FU-145) | 582–588 | 6 | 6/0/0 | 0 | walk 2026-07-23: "Add as product" on an unlinked product (Freddo) → 2+-drafts "Which list?" picker → product-only line lands (`product_id` set, `stock_item_id:null`), toast "Added as product line.", renders with `.shopping-line-product-only` tint (`rgb(22,39,36)` vs transparent) + product chip. Survivors: rule-2 later-link nesting, rule-4 nested-remove modal, no-modal removal, onAddSingle on linked rows | ➗ |
| Cart Button C4 (FU-135) | 590–595 | 5 | 5/0/0 | 0 | walk 2026-07-23 (money-on, desktop): 2+-drafts "Add to which list?" picker lists all drafts + "+ Create new list"; **Cancel** → no list/toast/nav; **merge into existing draft** → "Added N items to your list" + routes (This week, 0 new since already stocked); **+ Create new list** → "Meals: week of 20/07/2026" created + "Shopping list created with 1 item." + routes. Survivors: 0-draft + 1-draft count-specific cases, nothing_to_add (seed plan always had ≥1 shortfall) | ➗ |
| Snapshot-at-add (FU-142) | 597–603 | 6 | 6/0/0 | 0 | DB seed for NULL legacy line | ⚪ |
| P6-01 C3 lifecycle (FU-066) | 605–611 | 6 | 5/1/0 | 1 | finish flow superseded by UX v2 | ⚪ |
| P6-01 C4 new-list dialog (FU-068) | 613–623 | 10 | 9/1/0 | 0 | | ⚪ |
| P6-01 C5 selector (FU-069) | 625–633 | 8 | 7/1/0 | 2 | selector superseded by UX v2 rail | ⚪ |
| P6-01 C6 in-store + drag (FU-073) | 635–641 | 6 | 5/1/0 | 1 | drag fix re-covered by UX v2 L562 | ⚪ |
| C6 audit pricing (FU-072) | 643–645 | 2 | 2/0/0 | 0 | | ⚪ |
| P6-01 C7 shop day (FU-076) | 647–655 | 8 | 7/1/0 | 2 | chip/selector superseded by UX v2 | ⚪ |
| Chunk 2 picker + Shop-now (FU-060) | 657–662 | 5 | 5/0/0 | 1 | re-prompt superseded by FU-316 | ⚪ |

### Stock

| Section | Lines | Items | A/V/H | Stale | Env / notes | Status |
|---|---|---|---|---|---|---|
| Action-first scan mode (FU-378) | 668–680 | 11 | 11/0/0 | 0 | scanning_enabled; typed-entry = camera stand-in | ⚪ |
| Product unlink fix (FU-528) | 682–684 | 2 | 2/0/0 | 0 | test-pinned | ⚪ |
| Register barcode (FU-373) | 686–689 | 3 | 3/0/0 | 0 | scanning_enabled | ⚪ |
| Stocktake snooze 500 fix (FU-526) | 691–694 | 3 | 3/0/0 | 0 | test-pinned | ⚪ |
| Consumption events restored (FU-533) | 696–699 | 3 | 3/0/0 | 0 | test-pinned | ⚪ |
| Rename-to-own-name (FU-528) | 701–704 | 3 | 3/0/0 | 0 | test-pinned ×5 | ⚪ |
| Unlinked-ingredients page (FU-532) | 706–707 | 1 | 1/0/0 | 0 | test-pinned | ⚪ |
| Reconcile-queue pagination | 709–710 | 1 | 1/0/0 | 0 | test-pinned | ⚪ |
| Expiry-on-open prompt (FU-507) | 712–717 | 5 | 5/0/0 | 0 | | ⚪ |
| StockItem.image dropped (FU-508) | 719–723 | 4 | 4/0/0 | 0 | | ⚪ |
| Stocktake C3 settings + surfacing | 725–757 | 23 | 20/3/0 | 0 | admin + non-admin | ⚪ |
| Stocktake C2 runner rebuild | 759–814 | 36 | 36/0/0 | 0 | overdue queue seeded | ⚪ |
| Bulk Log waste (FU-226) | 816–825 | 8 | 8/0/0 | 0 | long-press emulation | ⚪ |
| Auto-add-on-low (FU-315/464/511) | 827–846 | 15 | 13/2/0 | 0 | Essential items; 0/1/2+ lists | ⚪ |
| ⭐ Zero-Input Pantry (P8-07) | 848–861 | 12 | 12/0/0 | 0 | purchase+cook history | ⚪ |
| 3-band StockLevel collapse | 863–872 | 9 | 9/0/0 | 0 | | ⚪ |
| P8-05 buy-verdict oracle | 874–885 | 10 | 10/0/0 | 0 | price history + waste events | ⚪ |
| P8-02 barcode via OFF | 887–897 | 9 | 9/0/1* | 1 | outbound net + block capability; *camera-decode fidelity untestable | ⚪ |
| History tab — retention/cap | 899–909 | 9 | 9/0/0 | 0 | fresh destructive reseed | ⚪ |
| History tab — event kinds | 911–924 | 11 | 11/0/0 | 0 | flask db downgrade leg | ⚪ |
| Stock pickers + Log Waste | 926–931 | 5 | 5/0/0 | 0 | | ⚪ |
| Recipe-ingredients deep-link (FU-109) | 933–940 | 7 | 7/0/0 | 0 | | ⚪ |
| Recipe card no dim (FU-109) | 942–944 | 2 | 2/0/0 | 0 | | ⚪ |
| Stock Item Detail C-1b + marquee (FU-202) | 946–972 | 26 | 22/4/0 | 4 | in-section supersessions — walk Round-2 versions | ⚪ |
| Detail + Overview feedback (FU-222) | 974–979 | 5 | 3/2/0 | 1 | | ⚪ |
| Overview C2 toolbar/filters (FU-121) | 981–990 | 9 | 9/0/0 | 2 | | ⚪ |
| Overview C4 expiry control (FU-123) | 992–998 | 6 | 6/0/0 | 0 | | ⚪ |
| Overview C5 responsive + long-press (FU-124) | 1000–1006 | 6 | 6/0/0 | 0 | | ⚪ |
| Offers sidecar (FU-230) | 1008–1009 | 1 | 1/0/0 | 0 | ingested offers; money on | ⚪ |

*(P8-02 H nuance: no checkbox isolates camera decode; typed entry covers all listed items — counted 9A + noted.)*

### Dashboard + Alerts + Settings

| Section | Lines | Items | A/V/H | Stale | Env / notes | Status |
|---|---|---|---|---|---|---|
| Draft my shop (FU-351) | 1015–1026 | 11 | 11/0/0 | 0 | | ⚪ |
| ⭐ Dora Score (P8-08) | 1028–1039 | 11 | 11/0/0 | 0 | waste/budget/expiry seed | ⚪ |
| Log-price quick action (FU-300) | 1041–1050 | 9 | 9/0/0 | 0 | | ⚪ |
| Stock donut deep-links (FU-299) | 1052–1061 | 9 | 9/0/0 | 0 | | ⚪ |
| Price-drops widget (FU-296) | 1063–1073 | 10 | 10/0/0 | 0 | products flag; historic offers | ⚪ |
| Dashboard rebuild walk (FU-301) | 1075–1083 | 8 | 5/3/0 | 0 | Playwright partially overlaps basics | ⚪ |
| Next to cook (FU-298) | 1085–1091 | 6 | 6/0/0 | 0 | | ⚪ |
| Budget money-gate (FU-297) | 1093–1096 | 3 | 3/0/0 | 0 | | ⚪ |
| Cards DnD reorder (FU-294) | 1098–1103 | 5 | 5/0/0 | 0 | | ⚪ |
| dashboard_layout backend (FU-292) | 1105–1108 | 3 | 3/0/0 | 0 | test-pinned | ⚪ |
| Alerts C-9.1 spine (FU-183) | 1114–1123 | 9 | 9/0/0 | 0 | C-9.5 price watch walked 2026-07-23 (money seed): empty-state / armed→list(product·merchant·notify-below) / View→explorer / Remove→gone+toast / install-money-off hides it; [[FU-604]] gating; residuals = last-alerted + arm-UI | ➗ |
| Cross-app undo push-expiry (FU-357) | 1125–1128 | 3 | 3/0/0 | 0 | | ⚪ |
| good_deal + fake-markdown (FU-450) | 1130–1134 | 4 | 4/0/0 | 0 | offers + observations | ⚪ |
| C-9.7 email digest (FU-205) | 1136–1144 | 8 | 6/1/1 | 2 | SMTP via admin page now (not env) | ⚪ |
| C-9.8 web-push (FU-206) | 1146–1157 | 10 | 10/0/0 | 2 | VAPID via admin page now (not env) | ⚪ |
| Data pages UI revamp (FU-359) | 1163–1168 | 4 | 4/0/0 | 0 | | ⚪ |
| FU-333 close-out C+D | 1170–1181 | 10 | 10/0/0 | 0 | env manipulation + restarts | ⚪ |
| FU-333 Bucket B (historical) | 1183–1190 | 6 | 6/0/0 | **6** | whole block self-declared superseded; salvage Voice/Hosting rows | 🗑 |
| Users admin Add/Delete (FU-461) | 1192–1208 | 15 | 15/0/0 | 0 | 2nd admin; DB SET NULL checks | ⚪ |
| Admin cache-race (FU-016) | 1210–1214 | 3 | 3/0/0 | 0 | two admins | ⚪ |
| Backup library (FU-342) | 1216–1227 | 11 | 11/0/0 | 1 | filesystem access | ⚪ |
| Image compression (FU-345) | 1229–1237 | 8 | 8/0/0 | 1 | | ⚪ |
| Import Options alignment (FU-344) | 1239–1242 | 3 | 3/0/0 | 1 | presentation superseded by FU-359 | ⚪ |
| Import templates (FU-343/349) | 1244–1251 | 7 | 7/0/0 | 1 | | ⚪ |
| Backup retention + path (FU-342) | 1253–1258 | 5 | 5/0/0 | 1 | | ⚪ |
| Data relocation (FU-341) | 1260–1267 | 7 | 7/0/0 | 2 | | ⚪ |
| FU-198 admin gate | 1269–1276 | 2 | 2/0/0 | 0 | | ⚪ |
| QR labels relocated (FU-340) | 1278–1283 | 5 | 5/0/0 | 0 | scanning_enabled | ⚪ |
| Email change + CSRF (FU-197) | 1285–1296 | 11 | 11/0/0 | 0 | links extractable server-side | ⚪ |
| Assistant banner/Test/docs (FU-330/331/332) | 1298–1316 | 18 | 18/0/0 | 0 | **owner pre-saves real API key once**; fake keys for failure paths | ⚪ |
| Assistant per-user config PR1 (FU-153) | 1318–1340 | 22 | 22/0/0 | 0 | partly test-pinned; owner-saved keys | ⚪ |
| Visual rebuild P3 cross-theme (FU-283) | 1342–1344 | 2 | 0/2/0 | 0 | pure V-pack | ⚪ |
| Phase 4 profile picture (FU-286) | 1346–1349 | 3 | 3/0/0 | 0 | partly test-pinned | ⚪ |
| VocabListEditor empty copy (FU-285) | 1351–1353 | 2 | 2/0/0 | 0 | | ⚪ |
| Speech toggle w/o SpeechSynthesis (FU-289) | 1355–1358 | 3 | 3/0/0 | 0 | CDP stub | ⚪ |
| API access page (FU-218) | 1360–1367 | 7 | 7/0/0 | 0 | curl bearer client | ⚪ |
| Decommission scraping (FU-186) | 1369–1371 | 2 | 2/0/0 | 0 | | ⚪ |
| Ingestion quarantine (FU-190) | 1373–1375 | 2 | 2/0/0 | 0 | ingestion key | ⚪ |

### Onboarding + Products + Build + Operator

| Section | Lines | Items | A/V/H | Stale | Env / notes | Status |
|---|---|---|---|---|---|---|
| FU-184 sell-copy honesty pass | 1381–1392 | 5 | 5/0/0 | 1 | | ⚪ |
| FU-195 starter-data picks | 1394–1410 | 16 | 16/0/0 | 0 | blank DB | ⚪ |
| Onboarding C-5.1–5.6 (FU-192) | 1412–1439 | 27 | 26/1/0 | **10** | heavy supersession by 07-12 story + de-persona | ⚪ |
| De-persona remaining (FU-210) | 1441–1449 | 8 | 5/3/0 | 1 | | ⚪ |
| Demo dataset toggle (FU-194) | 1451–1457 | 6 | 6/0/0 | 0 | | ⚪ |
| Expiring-soon window (FU-187) | 1459–1463 | 4 | 4/0/0 | 0 | assistant answering | ⚪ |
| Sell-copy honesty P3 gate (FU-184 dup) | 1465–1471 | 6 | 4/2/0 | 2 | largely duplicates 1381–1392 | ⚪ |
| My Products + Price History (FU-214) | 1477–1489 | 12 | 6/4/2 | 0 | + 3 PH residuals from FU-431 (not yet listed) | ⚪ |
| My Products Link (FU-208) | 1491–1493 | 2 | 2/0/0 | 0 | | ⚪ |
| PreferredBuy (FU-211) | 1495–1497 | 2 | 2/0/0 | 0 | | ⚪ |
| Preferred-buy hint (FU-215) | 1499–1501 | 2 | 2/0/0 | 0 | | ⚪ |
| Stock-item Prices (FU-213) | 1503–1506 | 3 | 3/0/0 | 0 | | ⚪ |
| Unit-cost rebase (FU-216) | 1508–1511 | 3 | 3/0/0 | 0 | | ⚪ |
| Windows desktop build (FU-327) | 1517–1528 | 8 | 7/0/1 | 0 | **this IS a Windows box — runnable**; audio item H | ⚪ |
| macOS desktop build (FU-327) | 1530–1540 | 7 | 0/0/7 | 0 | **blocked: no Mac** | ⚪ |
| Fresh-install bootstrap (FU-200) | 1542–1552 | 9 | 9/0/0 | 0 | blank DB; ADMIN_BOOTSTRAP_EMAIL | ⚪ |
| Docker/desktop voice bundling (FU-286) | 1554–1557 | 3 | 3/0/0 | 0 | Docker; WSL | ⚪ |
| Piper synthesis walk (FU-291) | 1559–1565 | 5 | 5/0/0 | 0 | Piper present | ⚪ |
| Piper auto-provisioning (FU-290) | 1567–1570 | 3 | 3/0/0 | 1 | wording only (FU-288 precondition met) | ⚪ |
| FK-index migration (FU-563) | 1576–1579 | 2 | 2/0/0 | 0 | populated DB; test-pinned (schema-match) | ⚪ |
| FK ondelete rebuild (FU-565) | 1581–1585 | 3 | 3/0/0 | 0 | populated DB; test-pinned | ⚪ |
| Product nullability (FU-564) | 1587–1591 | 3 | 3/0/0 | 0 | populated DB; test-pinned | ⚪ |
| gunicorn WSGI (FU-397) | 1593–1600 | 6 | 6/0/0 | 0 | **Docker/WSL only** (POSIX) | ⚪ |
| Dev seed under load (FU-388) | 1602–1607 | 4 | 3/1/0 | 0 | destructive reseed | ⚪ |
| Playwright CI re-run (FU-540) | 1609–1611 | 1 | 1/0/0 | 0 | blocked on FU-405 CI | ⚪ |
| Fresh-install migration boot (FU-549) | 1613–1614 | 1 | 1/0/0 | 0 | test-pinned; clean-venv leg manual | ⚪ |
| Companion push round-trip (FU-554) | 1616–1617 | 1 | 1/0/0 | 0 | dora-companion checkout (software) | ⚪ |
| Demo / showcase mode (FU-392) | 1619–1624 | 5 | 5/0/0 | 0 | env restarts; 2-min waits | ⚪ |
| Secure-cookies warning (FU-460) | 1626–1633 | 7 | 7/0/0 | 0 | HTTPS-front for one item | ⚪ |

### Cross-cutting

| Section | Lines | Items | A/V/H | Stale | Env / notes | Status |
|---|---|---|---|---|---|---|
| Menu bar border removed (FU-363 i6) | 1639–1642 | 2 | 1/1/0 | 0 | | ⚪ |
| Support channel (FU-370) | 1644–1651 | 6 | 6/0/0 | 0 | env restarts | ⚪ |
| Text-scale follow-through (FU-025) | 1653–1663 | 9 | 0/9/0 | 0 | flagship V-pack; computed-font-size could promote most to A | ⚪ |
| R-029 Product Search nav (FU-500) | 1665–1671 | 5 | 5/0/0 | 0 | | ⚪ |
| BaseButton sweep (FU-504) | 1673–1680 | 6 | 3/3/0 | 0 | | ⚪ |
| Security headers (FU-459) | 1682–1691 | 8 | 8/0/0 | 0 | curl | ⚪ |
| Recipe-picker toast (FU-319) | 1693–1695 | 2 | 2/0/0 | 0 | | ⚪ |
| Help chips (FU-503/044) | 1697–1717 | 17 | 17/0/0 | 0 | ~14 surfaces seeded | ⚪ |
| iOS/macOS audio-unlock (FU-287) | 1719–1729 | 7 | 1/0/6 | 0 | → Apple device pack | ⚪ |
| Filters toolbar alignment (R-027) | 1731–1737 | 6 | 6/0/0 | 0 | getBoundingClientRect | ⚪ |
| C-19 auth-shell (FU-540-adjacent) | 1739–1759 | 20 | 13/7/0 | 0 | Playwright covers login/nav, not visuals | ⚪ |
| P8-01 rename sweep | 1761–1766 | 5 | 5/0/0 | 0 | | ⚪ |
| D.O.R.A. easter egg | 1768–1772 | 4 | 4/0/0 | 0 | | ⚪ |
| Nav-state policy (A8 §3) | 1774–1780 | 6 | 6/0/0 | 0 | | ⚪ |
| /data/barcodes redirects (FU-340) | 1782–1786 | 4 | 4/0/0 | 0 | | ⚪ |
| /data/export retired (FU-339) | 1788–1795 | 7 | 7/0/0 | 1 | card-count half of L1789 stale | ⚪ |
| Settings dual scroll | 1797–1803 | 6 | 6/0/0 | 0 | | ⚪ |
| Mobile header wordmark | 1805–1809 | 4 | 4/0/0 | 0 | | ⚪ |
| Menu indicator colour fix | 1811–1815 | 4 | 2/2/0 | 0 | | ⚪ |
| Header peer buttons | 1817–1828 | 11 | 10/1/0 | 0 | | ⚪ |
| Sign-out in Settings header | 1830–1836 | 6 | 6/0/0 | 0 | | ⚪ |
| R-016 lazy hydration (FU-221) | 1838–1841 | 3 | 3/0/0 | 0 | | ⚪ |
| R-016 extension ×5 stores | 1843–1850 | 7 | 7/0/0 | 0 | | ⚪ |
| DnD affordance parity (FU-326) | 1852–1858 | 6 | 6/0/0 | 0 | | ⚪ |
| Error-handling rollout (FU-099-V) | 1860–1866 | 6 | 6/0/0 | 0 | kill API mid-save | ⚪ |
| formatQuantity rollout (FU-321) | 1868–1873 | 5 | 5/0/0 | 0 | | ⚪ |
| Unsaved-changes guard (FU-322) | 1875–1879 | 4 | 4/0/0 | 0 | FU-539 suite covers guard logic | ⚪ |
| Chunks 3–5 query paths (FU-051) | 1881–1890 | 9 | 9/0/0 | 0 | server side test-pinned | ⚪ |
| C-cross C1 feature flags (FU-110) | 1892–1902 | 10 | 9/1/0 | 2 | toggle-count + health-keys enumerations stale | ⚪ |
| C-cross C2 money opt-in (FU-111) | 1904–1914 | 10 | 9/1/0 | 0 | | ⚪ |
| C-cross C3 nutrition (FU-112) | 1916–1929 | 13 | 12/1/0 | 0 | | ⚪ |
| C-cross C5 image opt-in (FU-114) | 1931–1945 | 14 | 13/1/0 | 0 | | ⚪ |

---

## Appendix A — Human/hardware packs (40 items)

Grouped so each pack is one sitting with one device.

**Pack 1 — Android device (~12 items):** Native Android build section L51–60
(9 items: Studio/Gradle sync, APK install + icon, setup gate, endpoint change,
camera barcode scan, cook/shop wake-locks, push-unsupported); PWA share target
L166; recipe camera capture L316; receipt-photo camera L515–516; image-picker
camera L528; store-logo camera L69; Android voice-output spot-check L1728 (half).

**Pack 2 — iPhone/iPad (~6 items):** home-screen icon L108; Safari pinned-tab
L109 (low priority, legacy); iOS audio-unlock L1723–1726 (4 items: reply plays,
browser voice engine, cook narration, timer tone).

**Pack 3 — macOS (7 items, BLOCKED — no Mac):** macOS build script section
L1534–1540 + WKWebView audio checks L1727. Park until a Mac is available or
consciously accept as untested at launch.

**Pack 4 — mic / voice / audio on this desktop (~5 items):** currency-locale
speech recognition L46; Sous Chef voice verbs L354 + standalone timer via voice
L319; cook-mode beep audible L338 (fires = agent; audible = you);
Windows-desktop narration audio L1525.

**Pack 5 — misc human (~10 items):** browser Install-prompt UX L103 (agent
proxies via manifest + beforeinstallprompt); email digest arrives in a real
inbox L1141 (content verifiable server-side first); FU-214 product-scope
decisions L1481–1482 (owner calls, not QA); reduced-motion OS-level L20 if
DevTools emulation isn't accepted as equivalent.

## Appendix B — Eyeball (V) walkthrough packs (66 items)

Agent pre-stages + screenshots; owner judges. Natural bundles:

- **Text-scale pack (9):** FU-025 section L1655–1663 — Small vs XL across stock
  overview/detail, recipe edit, DoraScore, cookbook FilterBar, shopping detail,
  cook mode; icons deliberately don't scale.
- **Theme-read pack (~20):** three-theme reads scattered everywhere — L247, 263,
  356, 386–387, 611, 623, 633, 641, 655, 752/756/757, 963, 977, 1137, 1343–1344,
  1902, 1914, 1929, 1945. One staged sweep per theme, screenshots grouped per
  surface. (Feeds FU-010/FU-224 signal collection.)
- **Animation/feel pack (~10):** DoraTabs wobble L953, pulse halo L752, hover-bob
  L35-adjacent, menu-indicator slide L1814–1815, header ring fade L1826, auth
  mascot pulse L1740–1741, drag ghosting.
- **Layout/copy pack (~27):** breathing-room / not-squished / copy-tone items —
  L369, 836, 843, 952, 968, 975, 1077, 1082–1083, 1427, 1442, 1447–1448,
  1470–1471, 1480, 1484, 1486, 1488, 1605, 1641, 1676, 1678, 1680, 1743, 1749,
  1755–1756, 1759.

## Appendix C — Stale-suspect items (61) — owner decides delete/rewrite

Each verify session should confirm + action its batch's entries; the whole-block
ones below can be decided up front.

**Whole blocks recommended for deletion (18 items):**
- **FU-333 Bucket B, L1183–1190 (6):** block's own preamble says the close-out
  block above supersedes it. Salvage: fold the Voice/Hosting page rows
  (L1189–1190) into the close-out walk. → 🗑
- **Onboarding C-5.3 persona block, L1428–1433 (6) + L1413, 1421, 1423, 1438
  (4):** superseded by the 2026-07-12 story pass + FU-210 de-persona (persona
  chips, auto-advance, Skip label, personaPreview field all gone). → 🗑
- **Chunk 7 URL-importer items, L212–215 (4):** the URL importer was deleted by
  the paste-based rebuild (L178 pins the 404). Keep L209/216/217 (migration,
  legacy source, backup round-trip). → 🗑

**Item-level rewrites/deletes (43 + 1 found in pilot):** with evidence, by batch —
- L91 — example password `abcdefgh` is itself on breach lists, so the check can
  never pass as written (pilot-verified: 422 breach rejection). Rewrite with a
  non-breached letters-only example (e.g. `zxqvbnmk`); the intent (no digit
  rule) is confirmed working.
- L57 — scan now opens stock item, add-flow retired (FU-378). Rewrite.
- L202–203 — HowToStep/HowToSection import went with URL importer. Delete.
- L274 — command palette CUT; keep `g r` half. Rewrite.
- L337 — "8 commands" count wrong post-Done-removal (L354). Rewrite count.
- L470 — contradicted by L471 (Jump-to-plan dropdown gone). Delete.
- L475 — templates page now Sets-only (FU-308, L446). Rewrite.
- L607 — finish flow reworked by UX v2 (L555). Delete.
- L628, 633 — selector replaced by UX v2 rail/dropdown (L550–551). Delete.
- L639 — re-covered by UX v2 L562; verify once. Delete.
- L648, 654 — shop-day chip + selector sort superseded (L550–553). Delete.
- L658 — re-prompt semantics reworked by FU-316 (L506–510). Delete.
- L947 — contradicted by C-1b.1 Round-2 (L958–959). Walk Round-2 version.
- L960 — auto-add toggle collapsed by FU-511 (L846). Rewrite.
- L968 — references dropped StockItem.image (FU-508). Rewrite.
- L971 — auto-add footer count retired (L845). Rewrite.
- L978 — Auto-add retired + Flagged→Essential rename. Rewrite.
- L982 — Scan hidden unless scanning_enabled. Add precondition.
- L989 — footer enumeration stale (auto-add/Essential). Rewrite.
- L897 — StockItem.image path gone (FU-508). Delete assertion.
- L1138, 1141 — SMTP/PUBLIC_URL env vars removed by FU-333; config via admin
  pages, no restart. Rewrite setup steps.
- L1148–1149 — VAPID env gating gone (FU-333). Rewrite setup steps.
- L1226, 1230, 1240, 1245, 1254, 1262–1263 — presentation wording superseded by
  FU-359 revamp; behaviour halves live. Rewrite.
- L1391 — persona preview deleted 07-12. Delete.
- L1447 — persona chips removed entirely. Delete.
- L1466, 1471 — PERSONA_PREVIEWS/LOOP_INSIGHT deleted; question moot. Delete.
- L1570 — "when scripts land per FU-288" — landed (FU-327). Drop precondition.
- L1789 — `/data` card count now two (L1784). Rewrite count half.
- L1894, 1898 — feature-toggle count + health-key enumeration outgrown
  (products flag, demo_mode). Verify named keys, drop exhaustiveness.

## Appendix D — Standing constraints for verify sessions

- **Credentials:** agent never types real API keys/passwords. Owner pre-saves
  paid-provider LLM keys once (Settings → Assistant); failure paths use
  obviously-fake keys. Test accounts use throwaway credentials recorded in the
  session report.
- **Destructive ops:** fresh-install / reseed checks (`DORA_ALLOW_DESTRUCTIVE`)
  run against a **copy** of the dev DB or an explicitly disposable one — never
  the owner's live dev data without asking.
- **App launch:** `.claude/launch.json` has `dora-backend` (:5170) and
  `dora-spa` (:5174). **Do not verify against the repo-root `dora.data.db`** —
  it's a stale `create_all` artifact with no `alembic_version` (see FU-570 and
  the pilot caveat). First step of every verify session: point the backend at
  the **dedicated disposable verify DB** (fresh file + `alembic upgrade head` +
  FU-388 dev seed), e.g. via `DORA_DB_PATH` in the backend's environment.
  Pilot-created test accounts in the root DB: `qa-admin` /
  `dora-qa-admin-2026` (admin), `qa-user-1`/`zxqvbnmk`, `qa-user-2`/
  `passphrase please` — owner may delete at leisure.
- **Vue form automation:** programmatic `form_input`/typed keystrokes don't
  reliably reach Quasar v-models in the preview pane; use the native-setter +
  `input`-event injection pattern (worked everywhere in the pilot).
- **Preview-pane limits (2026-07-16 session 2):** the pane tab is *hidden* —
  no paint, no rAF, screenshots time out. Vue `<Transition>`-gated content
  (route swaps after the first; StockItemDetail's skeleton→content fade) never
  mounts. Partial fix: stub `requestAnimationFrame` with setTimeout + inject
  `*{transition:none!important;animation:none!important}` after boot — fixes
  top-level route swaps only. **Use the Playwright runner for real UI walks**
  (repo already has it: `web_app` `test:e2e`, FU-540); pane is fine for
  API checks, cold-load single views, and DOM instrumentation. App router is
  **hash mode** (`/#/stock`), and the SPA default route on plain URLs.
- **Verify fixtures in the DB:** "QA Verdict Cheese" + "QA verdict shop 1–3"
  (see Batch 0 continuation) — reusable for BuyVerdictCard; delete whenever.
- **Postgres leg:** `compose.dev.yml` PG + `DORA_TEST_DB=postgres`; batch 19.
- **Built-PWA checks:** `quasar build -m pwa` + `quasar serve` or the Docker
  image; batch 17.
- Line refs in this doc = 2026-07-16 snapshot of DORA_VERIFY.md.

### FU-583 + FU-581 verify walk (2026-07-26)

Drove the seeded money-on backend + SPA (login via the documented rAF-shim +
`form.requestSubmit()` recipe; screenshots time out as noted).

**FU-583 — kitchen-health deep-links → CLEARED, block deleted from DORA_VERIFY.**
`#/stock?expiring=1` activates the **Expiring soon** chip (`q-chip--selected` +
`text-warning`), filter badge counts 1, list narrows (24 shown). `#/stock?stocktake=1`
activates **Needs check** (3 shown). Expiring-soon chip toggles off live. The literal
Dora Score card button wasn't clickable (card not rendered in this dashboard's config),
but the card→URL strings are unchanged source and the destination — the only thing the
fix touched — is proven from both params. Predicate/clear/count also unit-pinned
(`useStockFilters.spec.ts`, 31 green).

**FU-581 — nav entry present-when-unset → CLEARED that line; block trimmed.** With
products on + `product_search_url` empty, the **Product Search** nav entry renders and
routes to `#/settings/admin/system/features` with no `open_in_new`/new-tab — the key new
owner behaviour. NOT driven (left in DORA_VERIFY): external-when-set (couldn't flip the
setting — UI blur-save didn't fire the write, direct PATCH is CSRF-403), products-off
hidden, and the individual CTA destinations. All are one-line conditionals already
type/lint-clean.

### Verify walk round 2 (2026-07-26) — substitute-swap gating + cookbook render

Same seeded session. 3 boxes cleared:

- **Shopping-list substitute-swap gating (FU-407, both directions) — deleted.** On the
  active "Saturday shop" list: 2 swap icons enabled, 4 disabled. Clicking an enabled one
  opened the chooser ("Swap Olive Oil with… Butter (Stocked)", Cancel/Swap) — cancelled,
  no mutation. Disabled = `!has_substitutes` (also `!stock_item_id` / done-list), tooltip
  strings source-confirmed (`ShoppingListDetail.vue:896-902`: "Swap for a substitute item"
  / "No substitutes recorded for this item"). Backend `has_substitutes` unit-pinned.
  Survivors in that section: the visual "distinct from store-offers picker" eyeball +
  product-only-line disabled (not driven).
- **Cookbook cookability + ingredients render (identity-map fix) — section deleted.** Opened
  Cheesy Garlic Bread detail: Ingredients list renders all 4 rows with per-item stock status
  (Sourdough Missing, Butter/Garlic Stocked, Parmesan Missing) and the cookability badge reads
  **Missing** — correct. Server filter contract already fully pinned (`test_recipe_filters.py`
  +14). The only remaining eyeball is now done.

Net: DORA_VERIFY 898 → 895 boxes.

### Verify walk round 3 (2026-07-26) — cookable route + unlinked empty-state

Same seeded session. 2 boxes cleared (895 → 893):

- **FU-386 cookable chip → `?cookable=true` route — deleted.** `#/cookbook?cookable=true`
  narrows the overview 38 → 8 cards with the Filters badge showing 1 active. The chip→route
  path was already noted confirmed-live; route contract also backend-pinned
  (`test_recipe_router.py CookableTrueFilter`).
- **Bulk-linker empty-state — deleted.** `/settings/admin/data/unlinked-ingredients` renders
  the exact empty-state copy "Every recipe ingredient is linked to a stock item." (this seed
  has zero unlinked rows). The sibling autocomplete/Link boxes stay — can't drive them without
  unlinked data (and the Create-new path was already verified live 2026-07-22).

**Drivable pile now thin:** what's left skews to contrived-data setups (fake-markdown verdict,
alert-resolve refetch), specific install flags (money-off / plan-free / productless / non-admin),
device/file flows (PWA install, camera, share target), and visual/dark-mode eyeballs (screenshots
time out in this pane). Those are genuinely owner/device walks.
