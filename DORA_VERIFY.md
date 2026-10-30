# Dora Verification Checklist

The QA pile — anything that needs eyes on the running thing to confirm.
Browser observations, boot-time / operator smoke checks, container startup,
migration round-trips, CLI/desktop launch checks — whatever needs manual
verification lives here. Grouped by surface; pick one and walk it
top-to-bottom.

> **Campaign in progress (2026-07-16):** this pile is being cleared via
> agent-verified evidence reports — see `DORA_VERIFY_TRIAGE.md` (repo root)
> for the batch plan, per-section classification, and session protocol.
>
> **⚠️ STANCE (owner, 2026-07-20) — verify by driving the app once, don't
> auto-test everything.** Clear an item by **driving the running app** (agent or
> owner) to confirm it works, then delete the line — that's the default. Write an
> automated test only for a **stable, low-churn contract** that's costly to
> re-check by hand (prefer backend/Vitest). **Playwright is smoke-only now**
> (`auth.setup`+`login`+`smoke`); the feature-flow specs were deleted 2026-07-20.
> Some pinned-notes below cite a now-deleted Playwright spec — those items are
> just manual once-off checks under this stance; backend/Vitest pin-notes remain
> valid. Full rationale: `DORA_VERIFY_TRIAGE.md` top banner.

---

## Security: sign-ups, sessions, reset links (2026-10-30) — origin FU-928
- [ ] ⚠️ Operator: after the next deploy, confirm the production install's public URL is set (Settings → Email) if you use password-reset mail; without it reset mails are skipped and "Forgot password?" is hidden.

## Release prep: build id + PUID/PGID (2026-10-30) — origin FU-861, FU-964
- [ ] ⚠️ Operator: `DORA_BUILD_ID=$(git rev-parse --short HEAD) docker compose up -d --build`, then confirm the boot log says "dora_api will run as uid=1000 gid=1000", `docker exec dashy_dora ps -o user,cmd` shows gunicorn not running as root, and the API can still write (upload a recipe photo, take a backup).
- [ ] Open Settings → About → Technical details on that deploy: Build reads `v0.7.0 · <sha>` with "Quote this when reporting a problem.", and `/api/health` shows the same `build`.
- [ ] On an existing install whose volumes were written as root, confirm the first boot after this change chowns them and nothing reports a permission error.

## Autonomous QA round 3, browser-verify owed (2026-10-30)
Driven by the agent on the seeded backend: 35 journey assertions (cart button, level picker, expiry +7d/clear, log a price, inline rename, favourite, meals pool, print tab, cook mode to finish, shop start/tick/finish, Dora "what's expiring", "/" search, new item + delete, budget save, dark theme), a two-device concurrency run, a fresh-install walk, offline mode, a Pacific/Pago_Pago household vs a Sydney device, a 2000-item pantry. The items below were fixed from a code read and want one look.
- [ ] Weekly deals email on an install with SMTP but no public URL: the job logs a warning and sends nothing; Settings → Email could surface `public_url_configured` (frontend not yet done, FU-969).

## Autonomous QA round 2, browser-verify owed (2026-10-30)
Driven by the agent: fresh install → /setup → wizard → empty-household crawl (clean), a second user's wizard, an authz matrix (anonymous + non-admin over 220 routes), fault injection (1-in-3 / abort / all-500 API reads: no blank pages or stuck spinners), axe-core at 1280/375, query budget on dense + 2000-item seeds, Postgres DDL offline. The items below were fixed from a code read and want one look.
- [ ] Dora chat with a hosted provider (OpenAI / Anthropic / Gemini): ask "what's expiring?" — a real answer, and Settings → Assistant still reads available afterwards (tool results now carry `tool_call_id`).
- [ ] Companion: ask link-status for a name Dora holds only at another store — "not in Dora" (it used to match the other store's product, and unsave could delete it).
- [ ] Onboarding as a second member: Finish does not re-create default groups/locations the admin deleted; the recap shows no stock rows. Register, then open the verify-email link mid-wizard — the page verifies instead of bouncing to /welcome.
- [ ] Native first run with no saved server: the address page shows (no endless splash); after Connect the app lands on /setup or /login.
- [ ] Stock: filter to 250+ items → Export CSV, Print view and QR sheet all open (ids are POSTed now); on a phone the Settings/Admin toggle and the settings chips are 44px tall.
- [ ] Login: six wrong passwords for one username inside a minute → 429 with Retry-After; a correct login afterwards resets it.
- [ ] Stores: a logo that is a tiny PNG declaring 13000×13000 — the store saves with no brand colour and the server stays up.
- [ ] Companion: push a backdated offer — the current price stays the newer one.
- [ ] ⚠️ Operator (SQLite production DB, origin FU-965): against the live `dora.data.db` (or its newest backup) run `SELECT count(*) FROM "StockItemSubstitute"`, `"StockItemProduct"`, `"StockItemPriceObservation"`, `"ShoppingListLine"`, `"RecipeIngredient"`, `"RecipeStep"` and compare with what the app shows / an older backup — a count that is far below what you remember means an earlier upgrade cascade-deleted rows (restore them from the older backup's sections via Backup & restore).
- [ ] Operator (Postgres): `upgrade head` on an EMPTY Postgres completes (eight revisions were Postgres-broken); `test__migrations__upgrade_head_runs_on_postgres` with `DORA_TEST_POSTGRES_URL` passes; `SHOW timezone` on the app's connection reads UTC.
- [ ] Operator (compose): a plain-http install now gets Secure cookies by default — set `DORA_SECURE_COOKIES=false` in `.env` if logins fail after upgrading; nginx responses carry nosniff / X-Frame-Options / Referrer-Policy.

## Autonomous QA sweep, browser-verify owed (2026-10-29)
Driven by the agent against the seeded backend: setup-admin success path (pytest), chunked upload for restore + import, step-image keep/reorder/foreign-id, null move, meal-plan sort, reconcile Skip advancing, route crawls at 1440/375, 522-request API sweep. The items below were fixed from a code read only and want one look each.
- [ ] Cook mode, voice on (desktop Chrome): say "next" twice — the step advances exactly twice; "start timer" after a finished timer counts down rather than finishing at once.
- [ ] Recipe page: edit ingredients without saving, click a version sibling — a prompt appears; Stay keeps the edits, Leave discards them.
- [ ] Recipe page, photo method: reorder two saved photos and add a third, save — all three are there in the new order; delete one and save — the other two remain.
- [ ] Stock item page (peek): click item A then B before A finishes loading — B's detail and B's QR label show (Scanning tab); "Add missing" on a recipe card with two draft lists — pick a list, every missing item lands on it.
- [ ] Stock row: set a level while offline — the row reverts to the old level with a "Could not update" toast; set an expiry — the toast shows the locale date, not an ISO string.
- [ ] Stocktake: a run with review items only — confirm them all; the summary card shows (not "You're all caught up"). Boot with the API down — an error card, not "all caught up".
- [ ] Shopping lists: with two lists, open the overview while another tab is mid-refresh — it redirects to the next-up list, never "No shopping lists yet"; dismiss the budget banner on list A, open over-budget list B — B's banner shows.
- [ ] Shopping list (done): Put away → assign a location to an unsorted item — the dialog stays, group ticks survive, no page flash. Receipt photos render on the strip and in zoom.
- [ ] Templates page: double-tap Use on a card — one list; only that card's button spins.
- [ ] Meal plans: tap + on an entry's servings three times fast — servings go up by three; arrow week twice fast — the shopping card, budget and "Dora suggests" show the week on screen; apply a swap that brings the week under budget — the Undo banner is still there.
- [ ] Reconcile runner: with 31+ past meals, Skip through the first page — it keeps going past 30 and ends on "complete" with the right count; "Different portions" opens with the planned servings.
- [ ] Reports: click All time then 30 days quickly — every card shows 30-day numbers and the window label matches. Price history: selected-product chips carry their series colour swatch.
- [ ] Settings → Nutrition: with the API down, change the rating scheme — the control reverts and a toast shows. Region: pick USD with the API down — the picker reverts. Import: halt on error → fix mapping → Import runs again.
- [ ] Scan overlay (scanning on): open it, close it while the camera permission prompt is still up, then allow — the camera light goes off.
- [ ] Operator (Postgres): `GET /api/dashboard/restock-radar` with a Low item returns 200 (was a naive/aware TypeError). Audit retention set to 30 days — the nightly prune log line names 30.
- [ ] Operator (gunicorn): filter stock to ~150 items and Export CSV / Print view — 200, not "Bad Request Line".

## Help area redesign, browser-verify owed (2026-10-29)
- [ ] Help: the landing shows the mascot, the search box, 14 topic cards (each with a count), Common questions and the two doors; nothing overflows at 375px.
- [ ] Help → Stock: guides open one at a time with a chevron; "Reading a stock row" shows the live legend and the stock-rows screenshot with rounded corners and a hairline.
- [ ] From a stock item's Substitutes tab, the (?) lands on Help → Stock with the Substitutes guide open and scrolled into view; same for QR label, Barcodes, the stocktake runner's (?), the reconcile runner's (?) and Settings → Assistant's "Learn more".
- [ ] Help search "budget" lists guides from several topics; clearing the box brings the topics back; the address carries `?q=`.
- [ ] Help → What's new renders the changelog as cards with bullet lists (no raw `**` or backticks); Help → About shows the version pill and, when configured, Report an issue.
- [ ] Help → Dora → Her faces shows the eleven mascot tiles; `/help/dora` from the assistant settings page still resolves.
- [ ] Dark theme: topic cards, guide cards and screenshots read correctly (hairline visible, no white flash); keyboard focus rings on cards and crumbs.

## Finalisation Stage 2 — unit 30 (cross-cutting sweeps), browser-verify owed (2026-10-27) — origin FU-929
- [ ] Any delete (a recipe, a store, a shopping list, a template, a stock item from the stocktake sweep): the dialog shows a flat Cancel and a red filled OK; Escape and a backdrop tap cancel; the delete only happens on OK.
- [ ] Settings → Kitchen setup → Stores / Locations / a vocabulary page: "New …" asks for a name in a text prompt; an empty answer does nothing; the rename prompt is pre-filled.
- [ ] Add-to-list with two draft lists (cart shortcut, the Add-to-list button, stock overview bulk add): the "Which list?" radio dialog picks the first by default and cancelling adds nothing.
- [ ] Meal plan → a cooked entry → "Cook once for more days": the checkbox dialog is pre-ticked with the days already covered.
- [ ] Recipe page: edit, then Back — the "Unsaved changes" dialog's Stay keeps you on the page, Leave without saving leaves.
- [ ] Settings → Appearance → text size *Small*: captions and chip labels are still 12px (not 10.5px); *Large* and *X-large* scale as before.
- [ ] Price history (a product priced above baseline), Backup & restore (a duplicate row in the preview), API access (pending / unmapped badges), Audit log severity chips: dark ink on the amber chips.
- [ ] Tab to Dora's launcher, a planner day's Add button, an onboarding loop node and the settings file-drop zone: a visible focus ring, distinct from hover.
- [ ] Every settings page still lays out as a column with its actions right-aligned (the chrome moved from 29 scoped copies to one global stylesheet).

## Finalisation Stage 2 — unit 29 (ops / self-host), operator checks owed (2026-10-27) — origin FU-929
- [ ] Boot the compose stack: `docker logs` shows one "Scheduled 5 job(s): audit_retention [cron…]; …" line and one "Registered N router(s), M route(s)" line (6 jobs with `DORA_DEMO_MODE=true`).
- [ ] Boot with `DORA_LOG_LEVEL=LOUD`: one "Unknown log level 'LOUD'; using the production profile default INFO" warning and the app still boots at INFO.
- [ ] Boot with `DORA_ENV=production` and a required var blank: the boxed "Refusing to start" banner on stderr, exit non-zero; with `DORA_SECURE_COOKIES=false`: the boxed WARNING banner, same frame.
- [ ] `docker compose up` on an existing deployment after the `dora_config` volume removal: boots clean; `dapi.appsettings.json` is still at `<data>/config/`.
- [ ] Rename `dora_api/features/alerts/__init__.py` aside and boot: the boot fails with "Feature package dora_api.features.alerts failed to import" + traceback (then put it back).
- [ ] Fresh dev boot with no `DORA_SECRET_KEY`: `data/.secret_key` is created `-rw-------` (Linux/macOS; Windows ignores the mode).
- [ ] Settings → Voice with Piper absent: the 503 hint names Settings → Admin → System → Voice.
- [ ] Desktop bundle (`build-windows.ps1` / `build-linux.sh`) still builds without the `webview.platforms.gtk` hidden import and opens the browser.

## Finalisation Stage 2 — unit 28 (backup / import), browser-verify owed (2026-10-27) — origin FU-929
- [ ] Settings → Admin → Data → Backup & restore: the library lists newest first; New backup (defaults) → Download → Restore this backup → Delete each work and each failure toast carries a reference id.
- [ ] Backup & restore: drop a backup file → preview tree → Restore selection; drop the same file again after a restore and confirm the "upload is gone" case reads as a not-found caption, not "HTTP 404".
- [ ] Backup & restore: edit a saved backup file on disk by hand, then Download it — a 409 toast, and the row shows a failed status after reload.
- [ ] Import: download a template, upload a CSV with `03/04/2027` in a date column on an en-AU install → 3 April; switch locale to en-US → 4 March.
- [ ] Import: the result dialog's "Download error rows" CSV opens with `row_number,name,reason` and quotes a reason containing a comma.
- [ ] Import / Backup: kill the API mid-upload — "Upload failed." toast with a friendly caption; retrying the drop works.

## Finalisation Stage 2 — unit 27 (offline / PWA), browser-verify owed (2026-10-27) — origin FU-929
- [ ] Built PWA: go offline (DevTools → Network → Offline): the red banner reads "You're offline. You can look around, but not make changes." with Retry; stop the API only: "Can't reach Dora…" with Retry; back online: a green "Back online." toast at the top.
- [ ] Built PWA with a newer build cached: the accent "A new version of Dora is ready" strip shows Reload + dismiss, under the header, same shape as the offline strip.
- [ ] Chrome → Application → Manifest: name "Dashy Dora", short name "Dora", theme colour #f5c462, two 192/512 icons + maskable; install prompt still offered over https.
- [ ] Cook mode and a shopping list in shop mode still keep the screen awake on a phone (wake lock) and release it on leaving.
- [ ] Android shell: About shows the "Dora API endpoint" row and no install section; camera availability unchanged.

## Finalisation Stage 2 — unit 26 (ingestion seam), browser-verify owed (2026-10-27) — origin FU-929
- [ ] Companion → push a product with an unknown field: the companion shows a per-field message naming the field, not "Extra inputs are not permitted" repeated.
- [ ] Settings → API access: a key the companion has only used to list stores shows a "Last used" time, not "Never used".
- [ ] Settings → API access → Store mappings: the store picker lists every Dora store (more than 50 if you have them); assigning and clearing a mapping still works.
- [ ] Settings → API access: a disabled source's "Disabled" badge reads in dark themes (sunken tint, no white-on-grey).

## Finalisation Stage 2 — unit 25 (auth shell), browser-verify owed (2026-10-27) — origin FU-929
- [ ] Register with an email address (SMTP configured): an info toast "Check your inbox for a verification link." shows; without an address, no toast.
- [ ] Signed in on a page, expire the session (restart the API with a new secret, or delete the cookie) then click anything: you land on `/login?redirect=…` and, after signing in, back on that page.
- [ ] Sign out: DevTools → Application → Cookies shows no `dora_csrf` cookie afterwards.
- [ ] Visit a typo'd URL signed out and signed in: the 404 uses the login look (blobs, mascot, glass card) and "Take me home" works.
- [ ] Login, Setup and Users → Add user / Change password: the eye toggle reveals the password; typing 7 characters on a *new* password shows "At least 8 characters"; sign-in's current-password field shows no length hint.
- [ ] About → Change (native) and the cannot-connect splash → Change instance URL: same dialog, saving reloads against the new URL.
- [ ] Setup pages: the "One-time setup" / "Choose your Dora" pill renders as before; primary/secondary button ink and the splash text are unchanged (tokens, not hex).

## Finalisation Stage 2 — unit 24 (settings shell + onboarding), browser-verify owed (2026-10-27) — origin FU-929
- [ ] Settings → Users: a user with a photo shows "Remove picture" in the ⋮ menu; using it clears the avatar; a user without one doesn't show the item.
- [ ] Settings → Notifications with SMTP / VAPID unset: the "isn't set up on this install yet" card still renders as the warning banner with the admin's "Set up" button.
- [ ] Settings → About → "Run the welcome tour again" lands on `/welcome`; finishing it returns to the dashboard with your data intact.
- [ ] Welcome tour, stock step: add your own group and zone, finish — both exist once under Settings → Kitchen setup; run the tour again and add the same names — no duplicates.
- [ ] Welcome tour, welcome step: pick Light, then open Settings → Preferences — the picker shows Pesto / Light (no legacy "system" key).
- [ ] Welcome tour: typing a name in the stock step doesn't stutter (draft autosave is debounced).
- [ ] Welcome layout in a dark theme and the confetti colours still read correctly (tokens, not hex).

## Finalisation Stage 2 — unit 23 (reports, budget, waste), browser-verify owed (2026-10-27) — origin FU-929
- [ ] Reports (30 days): spend-by-store total, spend-by-category total and the budget card's spend agree for a week with one finished shop.
- [ ] Reports: every card that names the window reads the same words ("in the last 90 days"); Price changes says "since you started logging prices" on All.
- [ ] Spend by category bars keep their colours after a theme switch.
- [ ] Mark as wasted: tabbing through the reason tiles shows a focus ring.
- [ ] Reports and dashboard with the API stopped: each card shows "couldn't load", and Retry recovers it.

## Finalisation Stage 2 — unit 22 (assistant), browser-verify owed (2026-10-27) — origin FU-929
- [ ] Chat header Basic/AI slider on a phone: easy to hit, flips, focus ring shows on keyboard focus.
- [ ] AI mode: two questions in a row answer without a pause before each (no network probe per question).
- [ ] AI mode, over budget: "trim my list to budget" proposes with the install's currency symbol, and confirming trims.
- [ ] AI mode: "plan pasta for tomorrow" with no slot named lands in the household's first slot.
- [ ] Basic mode: "what's expiring" uses the household's expiring-soon window; "substitute for buttermilk" answers.
- [ ] Settings → Assistant: base URL and model placeholders show for each provider.

## Finalisation Stage 2 — unit 21 (dashboard), browser-verify owed (2026-10-27) — origin FU-929
- [ ] Dashboard Cards menu: hide / show, move up / down and drag reorder all stick after a reload.
- [ ] "What's coming": today is the first cell and ringed; weekday names follow the household locale.
- [ ] "Next to cook" shows ready / missing-N as before; Kitchen health's plan coverage looks right.
- [ ] Price drops: the "% off" chip and the linked-item link are readable in light and dark.
- [ ] Small chips: recipe "Use soon" / missing chips, the recipe cost dialog and nutrition card text sizes look right (they now actually apply the xs size).

## Finalisation Stage 2 — unit 20 (zero-input pantry), browser-verify owed (2026-10-24) — origin FU-929
- [ ] With inference on: "Dora thinks …" still shows on stock rows, the item page, recipe cards and planner chips, with the same wording as before.
- [ ] The planner's Dora-hunch glyph is readable (amber / green) in a light and a dark theme.

## Finalisation Stage 2 — unit 19 (stock overview + stocktake), browser-verify owed (2026-10-24) — origin FU-929
- [ ] Stock overview: the group filter lists your groups; rename a group in Settings, come back: the new name shows.
- [ ] Create item and item page: the location picker searches "Pantry › Middle shelf" paths; the group picker lists groups.
- [ ] Stock overview: export CSV downloads (named file on a same-host install).
- [ ] Stocktake walk: Mute asks first (walk and sweep); a Low/Out pick lands in the restock prompt at the end.
- [ ] Stocktake runner and stock rows in a dark theme: "Change level" neutral button hover, row hover / selected / expired outlines.
- [ ] Item page: change the level from the overview's peek, the item page shows the new level name.

## Finalisation Stage 2 — unit 18 (cook mode), browser-verify owed (2026-10-24) — origin FU-929
- [ ] Cook mode timer: start a 2-minute timer, switch apps for a minute, come back: it shows about a minute left; it chimes at zero.
- [ ] Cook mode on a phone, step face and photo face: Previous / Repeat / Next fit one row; photo zoom pages with Previous / Next.
- [ ] Cook mode "Sub-step" chip text is readable in a dark theme.
- [ ] Finish cooking with 0 meals: no error.

## Finalisation Stage 2 — unit 17 (shopping lists), browser-verify owed (2026-10-24) — origin FU-929
- [ ] New list → start from a template, with a name and shop date typed: the list keeps both and has the template's items.
- [ ] New list → merge a template into an existing list: items already on it are skipped, the rest added.
- [ ] New list → start from a recipe or a meal plan: all the items land (one request in the Network tab).
- [ ] Shop mode price sheet: save a price + store, store only, and clear; each sticks, and a failure puts the old values back.
- [ ] Finish a list, put away: groups by location as before.
- [ ] A finished list's receipt face still shows its lines, prices and photos; add and delete a receipt photo.
- [ ] Stock overview: bulk add to list and bulk remove from list still work.
- [ ] Trim to budget preview and apply on an over-budget list.

## Finalisation Stage 2 — unit 16 (meal plans), browser-verify owed (2026-10-24) — origin FU-929
- [ ] Planner, phone and desktop: chip menu actions (view, cook, remove, servings ±, link, unlink, lighter, fresh) all work.
- [ ] Planner chips and phone cards: price, Dora's hunch, chef hat and fridge glyphs show as before; cook-day chip reads "Cook day · N servings".
- [ ] "This week's shopping" matches on phone and desktop.
- [ ] Build my week: opens with every slot ticked; a picked recipe with no matching time-of-day lands in the first slot.
- [ ] Build my week with a budget cap on, money on: stays under; money off: no figures anywhere.
- [ ] Settings → Meal slots: usage counts match the planner.
- [ ] Reconcile runner and Meal log: close X, progress, and (?) opens Help → "Reconcile past meals".
- [ ] New shopping list → from a meal plan: plans read "Week of …", not "null".
- [ ] Templates → Delete: the Cancel button isn't all-caps.
- [ ] Meal plans, stock, settings, stocktake, reconcile and log pages still fill the screen below the header.
- [ ] Planner in a dark theme: the focused day chip's text and pips are readable.

## Finalisation Stage 2 — units 11–14, browser-verify owed (2026-10-24) — origin FU-929
- [ ] Dora (AI mode): "add milk to my list" returns the add card, no error.
- [ ] Stock item still used by a recipe → Delete: the "Still used by recipes" dialog lists the recipe names as plain text.
- [ ] Row menu, item page and bell "Push 7 days" on an expired item all land on today + N; each shows on the History tab.
- [ ] My products with 51+ saved products shows them all; Price history finds product 51.
- [ ] Price history card → "Watch this price" opens the same dialog My products uses; Manage alerts → Change opens it too.
- [ ] As a member (not admin) with a Product Search URL set: the nav link shows; with none set: no Product Search buttons.
- [ ] Store logos and profile pictures render (incl. the Capacitor shell / a split host).
- [ ] Settings → Notifications with money off hides "price drops"; with auto-drain on hides "meals to reconcile".
- [ ] Item page: History tab says "Restocked → …" / "Dropped to …" after renaming a level.
- [ ] Item page: type in Notes (don't save), toggle Essential: the draft stays.
- [ ] Item page signal cards (Dora thinks / planned meals / buy verdict) look alike in pesto and blueberry, light and dark.
- [ ] Recipe page missing-ingredient substitutes and cook-mode "Swap" still list substitutes.
- [ ] Network tab on a cold load: one `/health` request.
- [ ] Cook mode → open a different recipe by URL / back-forward: the new recipe loads at step 1.
- [ ] Run a stocktake, then open `/stock` without reloading: levels match what the stocktake set.
- [ ] Cookbook: filter badge count and Clear filters still cover every filter (try a few, then Clear).
- [ ] Recipe card and compact row: favourite (red when on), cook and add-to-list buttons behave as before.
- [ ] Settings → Categories / Cuisines / Tools: add, rename (incl. a duplicate name → error), delete shows the recipe count.
- [ ] Recipe images, step images, store logos and list attachments still load.

## Finalisation Stage 2 — units 1–10, browser-verify owed (2026-10-23) — origin FU-929
Backup & restore
- [ ] Settings → Data → Backup: *New backup* with the default sections is accepted; the section list (labels, "sensitive" badges) comes from the server.
- [ ] Restore selection: pick one stock item from a backup, restore, the item reappears; no error toast.
Offline / PWA (built SPA)
- [ ] DevTools → Application → Service Workers shows **one** registration (`sw.js`); opening Settings → Notifications does not add a second one, evict the cache, or show the "new version" banner.
- [ ] Docker image: `dist/spa/sw.js` + `manifest.json` present in the built container; install prompt appears over https.
Dashboard
- [ ] With a saved layout that pre-dates Kitchen health, the card appears at its registry position (second), not last.
- [ ] Delete a stock level that items still used (or null one by hand) → the restock radar card still renders.
Dora assistant
- [ ] "Tick off milk", "add <recipe> to my list", "trim my list to budget" return a confirm card (no "something went wrong").
- [ ] Every "See it" / "Open …" button under an answer lands on a live page (Cookbook, My products, Settings → Budget).
- [ ] Basic mode: "where is the rice" names the zone (Pantry / Fridge), not "(no location)".
- [ ] Settings → Dora assistant with the API down: a "Couldn't load your provider settings." toast shows.
Reports / budget
- [ ] Set the household timezone to Pacific/Kiritimati, finish a shop: the budget card counts it in the current period.
- [ ] Reports window label reads install-locale dates ("3 Aug 2026 – 2 Sep 2026"), no US ordering.
- [ ] Waste card reason tiles read "Bought too much", matching the Mark-as-wasted dialog.
Shopping lists
- [ ] Save as template on a list carrying a product-only line: succeeds; the template has the item lines only.
- [ ] Finish → "move unticked to a new list" with product-only lines: they move.
- [ ] Quick-add sheet shows the search icon in the field.
Meal plans
- [ ] Duplicate to next week on a week with a cook batch: next week keeps the batch (one cook, N meals) and the fresh marks.
- [ ] Meal plan print view and shopping list print view open from the Capacitor shell / a cross-site deploy (no 401 tab).
Cook mode / recipes
- [ ] Cook-mode guard dialog names a labelled ingredient ("tasty cheddar") the same as the recipe page.
- [ ] iOS Safari / WKWebView: no CSP violation logged on load; speech output works after the first tap.
- [ ] Finish a cook with the API down for one level write: a "Couldn't update 1 stock level." toast precedes the celebration.
Stock
- [ ] Stock overview peek opens at 50 %.
- [ ] Stock-item page: expiry, "Opened", and timeline dates are formatted (no raw `2026-10-23`).
Cross-cutting
- [ ] Toasts all sit bottom-right; offline/online and PWA update toasts still arrive at the top.
- [ ] Focus ring halo follows the theme (Tab through buttons in blueberry and sourdough-dark — no Pesto green).
- [ ] Cook-mode scaling: "2 rashers" at 1.5× → 3 (whole), "1 handful" stays continuous.

## Follow-up batch 2026-10-22
- [ ] My products ⋮ → Set items in pack: save 12, the menu then reads "Items in pack: 12"; Clear removes it.
- [ ] Add a custom product with Items in the pack set; a recipe's "3 eggs" linked to it is priced.
- [ ] Resize across the md breakpoint on the dashboard and a shopping list: no Oops toast; the nav indicator still sits under the active tab.
- [ ] Companion Settings → Merchants → Run health check: each merchant lists every provider with its own colour; Coles shows SaveOnGroceries green beside a red coles.com.au.
- [ ] Companion search, Coles only: results come back; saving an egg 12 pack lands in Dora with 12 in the pack.

## Owner batch 2026-10-17
- [ ] Bell, expired alert (none in the seed): Log waste opens the reason picker; logging removes the alert and Undo brings it back.
- [ ] Bell on a phone: snooze/dismiss column and wrapped action rows don't overlap or mis-tap.
- [ ] My products: a custom product's ⋮ menu offers Add photo; add, change (no reload), remove. An ingested product has no photo item.
- [ ] Companion against real Dora: saving one product says "Saved: 1"; its picture shows in My products; Sync fills pictures for products saved earlier.
- [ ] Companion Settings → Appearance → Dark, reload: no light flash; fields, menus and header readable; long names wrap before the heart on a phone.

## Owner batch 2026-10-15 (not driven live)
- [ ] Cook mode, fresh household: Finish says "Enjoy your meal."; an ingredient note reads italic behind a note glyph.
- [ ] Dashboard budget: a list dated next week is not in "still to buy on your open lists".
- [ ] Weekly deals email sends with SMTP set up and you subscribed (no admin toggle any more).
- [ ] Push notification click opens the app with the bell panel open.
- [ ] Companion on your real config: scrapers auto-match your Dora stores; logos show; saving a product works (FU-918).

## Cross-cutting: camera over http, copy sweep (2026-09-27)

- [ ] **Camera over http.** On a phone, open Scan from `http://<lan-ip>`: the
      camera is attempted with a small warning in the top bar, and the
      explainer panel only appears if the browser really refuses.
- [ ] **Copy reads right.** Skim a few tooltips and empty states on Stock,
      Shopping lists and Settings: no em dashes, nothing cut off mid-thought.

---

## Shopping lists: the 2026-09-27 phone pass (16 items)

Built, gated and driven at 375 (touch) and 1440 on the scratch pair. What a
headless Chromium can't show:

- [ ] **Keyboard vs bottom sheet, iPhone.** Open Add item and the shop-mode
      price sheet; focus the field. The sheet sits above the keyboard, header
      visible, nothing clipped.
- [ ] **Keyboard vs bottom sheet, Android Chrome.** Same two sheets; confirm
      the page doesn't jump or leave a gap when the keyboard closes.
- [ ] **Money off.** With money off, a draft's card reads *N Items to buy ·
      Shop day*. The count appears once.
- [ ] **Remembered choice.** Pick a preferred buy (products off) or an offer
      (products on) for an item, finish or delete that list, add the item to a
      new list. The choice is already there.

---

## Shopping lists — the auto-added mark (2026-09-19)

Code-complete and green (2379 backend / 749 SPA); not yet seen on screen.

- [ ] **Nothing else is marked.** Build a list via New list → auto-fill (low/out
      + essentials + frequently added): every line comes back unmarked.
- [ ] **The mark clears on edit.** Change quantity or pick an offer on a marked
      line — the glyph goes and stays gone after a reload.
- [ ] **`--accent-mark` at 14px holds contrast** in Pesto Dark and Cherry Cola
      Dark (D-002 grades icons at 3:1).

---

## Shopping lists — the 2026-09-17 second pass (24 items)

Driven live at 1440 and 375. What that run can't settle:

- [ ] **The name dropdown on a phone.** An item with preferred buys renders its
      name as a menu (chevron + hover wash). Confirm the tap target is
      comfortable and the chevron reads as "there's a choice" rather than as
      chrome, at 44px touch sizing.
- [ ] **"Seen at" in a real shop.** Mid-shop, open a line's price sheet and tap
      an offer chip — price and store should both fill. This is now the only
      way an offer becomes money, so it wants one real walk.
- [ ] **Dark themes, receipt face.** "Where you spent it" now renders flush
      inside the summary card on the receipt too. Check Pesto Dark and Cherry
      Cola Dark.

---

## Shopping lists — the 2026-09-17 UI batch

Driven live at 1440 and 375 on the isolated pair (no overlaps, no page
flash, store-group move confirmed). What a headless desktop can't settle:

- [ ] **A real phone, coarse pointer.** Icon buttons jump 36px → 44px under
      `pointer: coarse`, which is the input the new row arithmetic is sized
      for and the one Chromium headless never reports. Open a draft: the name
      shouldn't wrap under its own Buy chip, and nothing should sit on the
      price.
- [ ] **Tap the quantity tile on a draft row.** First tap arms the ± stepper —
      the row should widen to hold it, not float it over the item's name or off
      the left edge.
- [ ] **Dark themes.** The store breakdown is now flush inside the overview
      card (no border, no band of its own) and the **No store set** key is a
      hatched pip. Check Pesto Dark and Cherry Cola Dark: the region should
      still read as a region, and the pip should be distinguishable from the
      store dots beside it at 8px.

---

## Recipe ingredient "which one" (2026-10-21)

- [ ] **Preferred buy on a products-off install.** On an ingredient whose item has preferred buys, pick one; Called fills in and the row shows it.
- [ ] **Pick reaches the list.** Add that recipe's missing items to a list; the line shows the same preferred buy.

## Planner + recipe cost (2026-10-21) — origin FU-878, FU-875

- [ ] **Planner edits still save.** Change servings, move a meal, toggle Cook fresh and remove a day of a batch cook; each saves without "Could not update the plan".
- [ ] **Log price quotes per 100g.** Log a 2 kg pack; the preview reads "per 100g", not "per kg".
- [ ] **Cost reasons read sensibly.** Open a recipe's cost breakdown with an unpriced line; the group title names the actual gap.

## Cookbook + recipe view — the 2026-09-09 five-item batch

Built and gated (pytest 2349, vitest 720, `vue-tsc`, `eslint src/`,
`quasar build`) but not driven.

- [ ] **Rating appears without a reload.** With nutrition on **complex**, set
      Settings → Nutrition → rating scheme to Health Star (or Nutri-Score), then
      navigate straight to the cookbook — the chips should be there. Repeat via
      Region's "match this device" nudge.
- [ ] **Expiring filter survives a round trip.** Cookbook → "Uses expiring
      ingredients" → open a recipe → back. The chip stays on **and** the list is
      still narrowed and still ordered most-at-risk-first.
- [ ] **Free-text ingredient.** Type an ingredient you don't have, choose **Keep
      as free text**: the dropdown closes and the box shows your text.
- [ ] **Nutrition on a volume/count recipe** (Sunday Ragu is the fixture, in
      complex mode with its foods linked): the panel's uncounted list should
      have lost the onion, the carrot and the celery. Celery reading ~40 g a
      stalk rather than 113 g is the fix worth eyeballing.
- [ ] **Cost breakdown on a recipe written in cups/spoons**, money on. Lines
      that read "Units don't match the price" should have moved into the total.
      A recipe with an amount-less ingredient ("salt to taste") should show it
      under the new **"No amount on the ingredient"** heading rather than
      silently adding a whole product to the estimate.
- [ ] **The same recipe's cost agrees on the cookbook card, its own page and
      the meal-planner rail** — the planner reads through a separate adapter
      that had to be updated in step.
- [ ] **A recipe with cloves / sprigs / rashers in it.** Those lines should
      either carry a small sensible figure or sit under an unpriced heading —
      never a figure the size of a whole bulb, bunch or pack. Sanity-check the
      recipe total against what you'd guess it costs.
- [ ] **The stock level chip is back to its old size on your phone** (32px),
      while the level menu it opens still has the taller rows and the wider
      menu. That split is the whole point of the revert.

## Cross-cutting — tooltip delay + chrome tidy (2026-09-09)

Built and gated (`vue-tsc`, `eslint src/`, `quasar build`, vitest 720) but not
driven. Walk on a **real phone**, not a resized desktop window — the bell item
keys off `pointer: coarse`.

- [ ] **Tooltip delay feels right at 500ms.** Tap around (stock rows, cook mode,
      toolbars): a normal tap should show no tooltip at all; a press-and-hold
      should. Say if it wants to be shorter or longer — it's one number in
      `BaseTooltip.vue`. Check a desktop hover reads as a pause, not a lag.
- [ ] **A (?) chip on a phone (2026-09-13).** These now open with no delay, so a
      quick tap flashes the tip and drops it on lift — press-and-hold to read.
      Confirm the flash isn't annoying; if it is, the chip wants press-to-open
      rather than a dwell. (Desktop hover verified: 18 ms.)
- [ ] **The alerts bell number sits in one place** on phone and desktop, and is
      neither over the bell nor at the screen edge.

## Dashboard — the 2026-09-08 sixteen-item batch

**⚠️ None of this has been driven in the running app.** The batch was built,
gated (pytest dashboard suites, vitest 720, `vue-tsc`, `eslint src/`,
`quasar build` — all green) and the seeded backend was booted, but the live
walk was not done. Walk it at **1440 and 375** on the dense seed, money on.

The two worth doing first, because they are the ones a code read cannot settle:

- [ ] **The budget-score staleness fix.** This is the reported defect. On the
      dashboard, note *My budget* (spend vs target) and *Kitchen health*'s
      **Budget** row. Then go to Settings → Money, **change the period**
      (weekly → monthly) and/or the amount so the household is clearly OVER,
      come straight back to the dashboard — **inside five minutes**, which is
      what makes it a real test — and confirm the two now agree: an over-budget
      card must not sit beside a Budget row reading 100 / "Under budget this
      period". Before the fix the score row kept the number it fetched under the
      *old* period. Repeat once the other way (set a comfortable budget) so it is
      not just always-refetching-to-red.
- [ ] **Restock radar's `is_planned` chip and its 30-day cutoff**, against real
      seed data: rows ordered most-recent-first regardless of band, a level dot
      at the head of each row whose colour matches that item's level on the stock
      page, and a **Planned** chip only where the coming fortnight actually needs
      the item. Nothing older than 30 days should be listed — and if the card is
      empty, its copy must say "in the last 30 days", not "everything's stocked".

Then the rest:

- [ ] **Hero hint** renders as a callout (info icon, tinted well, accent rule)
      *inside* the hero card, and still wraps before the Cards button at 375.
- [ ] **Next to cook** rows read: name · day · [missing chip] · Cook. No slot
      word, no "serves N", no "to cook"/"already cooked". Cook is icon-only
      below `sm` with a working tooltip, and still opens cook mode at the
      batch's yield (the 09-05 behaviour — regression check).
- [ ] **Next to cook ordering**: plan several slots on one day (breakfast +
      dessert + dinner) and confirm the card lists them in the household's slot
      order, dessert last. Pinned by a backend test, but worth one look.
- [ ] **No header links on any card** — Kitchen health, Next to cook, Use it up,
      What's coming, Restock radar, My stock, My budget, and Price drops (switch
      it on in the Cards menu; it is opt-in and was the one this sweep initially
      missed). Empty-state CTAs ("Plan a meal →", "Plan a week →") and the stock
      donut's filtered segment/legend links **stay** — those are not the pattern
      that was removed.
- [ ] **Use it up**: heading reads "Recipes using these", each row's label reads
      "uses N expiring" right-aligned, and **See more** lands on the cookbook
      with the *Uses expiring ingredients* filter already applied (check the chip
      is lit and the result set is filtered, not just the route).
- [ ] **What's coming** shows 14 days with no toggle, two rows of seven.
- [ ] **Tap a day**: the date reads as a heading, each category label carries
      the same coloured dot as the grid, entries are obvious tappable rows, and
      the slot renders as a chip. This is the "text all looks too similar" item —
      judge it by eye, that is the whole acceptance test.
- [ ] **Kitchen health**: first card by default (on a *fresh* user — an existing
      saved layout keeps its own order, so check both); a hollow ring with the
      number inside; the trend chip under the ring, not in the header; one
      bordered box per signal; **no info chip** on the title; **no links** on any
      row; and a dormant signal reading "NOT COUNTED" in a dashed box —
      *"No budget set"* and *"Dora settles past meals for you"* must look
      identical (that is the specific ask). Check the ring in a **dark theme**
      too — the arc is a `stroke` on semantic tokens.
- [ ] **My stock**: donut + legend centred as a pair, no left-hugging with all
      the slack on one side. Check at 1440 half-width, where the complaint was.
- [ ] **My budget**: titled "My budget", no kept-vs-RRP section, no range
      toggle, no "Save $X this week / N swaps ready" line, and the open-lists
      figure reads as a sentence in its own tinted row ("$34.20 still to buy on
      your open lists").
- [ ] **The Cards menu** lists seven default-on cards + Price drops, with no
      "Before you shop" and no "Shopping lists" entry. A user whose stored
      layout named those (or `savings`) must not see a gap or a duplicate — the
      renamed budget card should appear once.

---

## Deploy — the companion stack (2026-09-07) — origin FU-790

The 2026-10-20 deploy built the image and both stacks run healthy. Still to
walk on the server:

- [ ] **merchant_api registered its routes** — `docker compose logs
      dora_companion` shows no zero-route startup, and
      `http://<server>:5172/api` answers.
- [ ] The companion SPA loads at `http://<server>:5175`, and a **deep link
      survives a refresh** (nginx `try_files`, history-mode router).
- [ ] The SPA's baked-in mapi URL resolves **from the browser** — search returns
      results rather than a CORS or connection error.
- [ ] **Push to Dora works on a freshly wiped deploy**, without touching the API
      access page: run a search, push, confirm records land. This is the whole
      point of the deploy-time minting.
- [ ] Settings → Admin → API access lists **exactly one** key labelled
      `companion` after two consecutive deploys, not two.
- [ ] `./deploy-dora.sh mint-key` re-keys a running companion and pushing still
      works afterwards.
- [ ] **Product Search appears in Dora's nav after a wiping deploy** and opens
      the companion — no visit to the admin page needed. Same check on a local
      dev boot, where it should point at `localhost:5175`.
- [ ] The **container-name reclaim** actually fires — deploy over the existing
      `discountdora`-project container and confirm it's torn down instead of the
      `up` dying on a name conflict.

## Price history + stock-item Products tab (2026-09-06)

Driven live at 1440, 375 and in `pesto-dark`, so the toolbar, the money field,
the chart fit and the dark-mode tooltip are all confirmed. What's left:

- [ ] **Set a real price alert** from the notify field and confirm it fires when
      the price drops below it (the field and button are verified; the alert
      firing end-to-end is not).
- [ ] On a stock item's **Products** tab with **two or more** shopping lists
      open: the cart button offers the picker rather than silently choosing, and
      a second tap removes. (Driven with one list, where it correctly showed the
      already-on-a-list state.)

## My Products — the rebuild (2026-09-06)

Driven live at 1440 and 375 on the dense seed, so layout, both view modes, the
bulk bar and the five card actions are confirmed. What the seed can't show:

- [ ] An install with **real product images** — the seed has none, so the card's
      square media well renders as a big placeholder glyph. Confirm a real photo
      fills it sensibly (contain, not stretched) and the discount badge still
      reads over it.
- [ ] **Delete a product** for real: the red confirm names the consequences, the
      card goes, and a *finished* shopping list that used it still shows the line.
- [ ] The three new bulk selections pick the right things on your data —
      *low stock on deal*, *out of stock on deal*, *essential, low, on deal*.
- [ ] The active toggle round-trips: switch a product off, and confirm the
      companion's next sync skips it (pairs with the Companion section below).

## Companion — Dora Target page (2026-09-07)

The `/api/push/config` contract is tested and was confirmed live by curl (real
URL returned, key absent). The page that renders it wasn't walked.

- [ ] Open the companion's **Dora target** page: the URL shown matches the
      backend's `DORA_INGEST_URL` (not the old `VITE_DORA_LABEL`), and the
      bearer-key chip reads *Set*.
- [ ] Unset `DORA_INGEST_KEY` and reload: URL still shown, key chip reads
      *Not set*. (The point is that it names which half is missing.)

## Companion — scheduled refresh (2026-09-06)

Loop is covered by tests and driven end-to-end against a stub Dora; what's owed
is one run against real stores.

- [ ] `POST /api/sync` on the companion with a few products saved: the response
      counts look right, and Dora's price history gains a point for each.
- [ ] Mark a product inactive in Dora, sync again: it is **not** re-scraped
      (counts drop by one; no new history point for it).
- [ ] Set `MAPI_SYNC_INTERVAL_HOURS=0`, restart: boot log says sync is disabled
      and no job runs. Non-zero: log states the interval.

## Companion — unsave deletes in Dora (2026-09-06)

Backend covered by tests on both DB backends; the card toggle needs the
companion running against live merchant sites.

- [ ] A result already in Dora shows **Unsave** (red) instead of Save; one not
      in Dora shows **Save**. Confirm the card flips state after each without
      needing a re-search.
- [ ] Unsave asks first, and after confirming the product is gone from Dora's
      My Products.
- [ ] A finished shopping list that contained that product still lists it, by
      name, afterwards.

## Companion — push takes offers now (2026-09-06)

Backend contract is pinned by tests and was driven end-to-end over real HTTP
against a stub Dora. The SPA half needs the companion running against live
merchant sites, which the agent can't drive — these are yours.

- [ ] Search, then **Save** one product from a set of similar-named results:
      Dora's My Products gets *that* product (check the store + size match the
      card you clicked), not a near neighbour.
- [ ] Tick 2 of many results, **Push selected**: exactly 2 arrive in Dora.
- [ ] Push with nothing ticked: the count that arrives matches the button's
      "Push all N".
- [ ] Dora Target settings → the connectivity check still reports correctly for
      all three states (unset env vars, wrong key, working) — it's a read now,
      so confirm it does **not** create any product in Dora.

## Meal planner — templates redesign + mobile parity (2026-09-13)

- [ ] Toolbar: **Apply template** sits left of Build my week and opens one
      dialog. Pick a template → Apply to this week. Flip **Repeat for several
      weeks** → the two week fields appear *in the same dialog* (no second
      modal) and the button reads "Apply to those weeks".
- [ ] Choose a **rotating set**: the repeat toggle switches on, goes inert, and
      says a set always repeats. Applying it plans the run.
- [ ] The apply dialog has **no** save button, no rename/delete, no link out.
- [ ] Week menu: "Save week as template…" still saves; **Manage templates…**
      opens the Templates page, which now lists *Your templates* with inline
      rename + delete above *Rotating sets*. Delete asks first.
- [ ] Deleting a template that a set rotates through: the set keeps its slot and
      shows "(deleted template)".
- [ ] Phone (375): **Build my week** and **Apply template** are equal-width side
      by side; the over-budget banner appears above the day strip; the week label
      is uppercase with "This week / N planned" split beneath it; the focused day
      header reads just the weekday.
- [ ] No per-day kcal cell on desktop day cards any more.
- [ ] Rail cost card reads "$X remaining of $Y budget" on one line inside the
      card (and "$X over $Y budget" when over).

## Meal planner — the 2026-09-12 owner batch (~20 items)

Built and gated, not driven. The auto builder's review step and the phone
picker sheet changed shape, so both want eyes at 375 and 1440.

- [ ] Auto builder step 1 reads **Setup**; the servings stepper is its own
      width (not stretched to the dialog edge) on a phone; its caption says
      only that you can adjust servings next; "Dora will plan N meals" sits in
      an info box directly above the button.
- [ ] Review step: one card per meal, servings + delete on the name's line, the
      day heading centred between two rules. No swap glyph, no "Added" chip, no
      "You have everything". A batch's first day says **Cook day**; its
      leftover days are grey.
- [ ] Reshuffle two or three times on the dev cookbook: the meals and/or the
      days visibly change, and an expiring-ingredient recipe keeps showing up.
- [ ] Budget cap ON with a small budget left: the swaps make sense against the
      *servings you chose* — halve the servings and fewer meals get swapped.
- [ ] "What you'll need" reads "N low · M out" with a to-buy figure and a meals
      figure beside it; both absent with money **off**, and the whole block
      still correct after editing servings on a row. No per-meal "N to buy"
      marker on the builder rows (cut as noise — it lives on the planner).
- [ ] **The two-glyph card** (batch household): a cook day shows a chef hat
      *and* a fridge; a leftovers day shows only the fridge; a cook-fresh meal
      shows only the chef hat. In a **fresh** household no card shows a fridge.
      Green when fine, amber when not, hover for the counts.
- [ ] Trim colour agrees with the glyphs on every card: green all-good, grey on
      leftovers and cooked meals, amber whenever a glyph is amber. Specifically
      check a batch week — no green card beside an amber one for the same cook.
- [ ] A batch's cook day reads "Cook day · N servings" with the **whole cook's**
      price beside it; its leftover days carry no price chip. The week total on
      the header still matches the sum of the cards.
- [ ] No day-level cost line anywhere (desktop day header or phone day header).
- [ ] "Cook now" from a planned meal that's missing ingredients raises the cook
      guard dialog and names them; "Start anyway" opens cook mode at the batch's
      servings, as before.
- [ ] Nothing user-facing says "pool" — check the meal menu's Cook-fresh
      caption, the week status "fresh" tip, and the dashboard's Next-to-cook
      empty state.
- [ ] **Batch household, standalone meal with no ready serving behind it**: the
      chef hat now shows on it (it was appearing only on multi-linked cook days).
      A meal the ready servings *do* cover still shows only the fridge.
- [ ] Card row order holds a column down a day: Dora's hunch → chef hat →
      fridge → time → price → ×servings, with ×servings always last. Nothing
      shifts sideways as meals change state. Icons are noticeably bigger.
- [ ] Rail: **Recipes** heading is centred, matches "Missing this week" in size,
      and clicking anywhere on it (not just the chevron) collapses the rail.
- [ ] A week containing a paste-imported recipe shows a **Free-text
      ingredients** disclosure with the names and their recipes; a week without
      one shows no such section at all.
- [ ] Calendar: hover a busy day — one summary line ("4 meals · 2 to cook"),
      not a list. Hover an empty day — "no meals planned".
- [ ] Week grid day headers show the day name only, no date, and TODAY is caps.
- [ ] **Type scale**: the week's meal cards no longer read smaller than Stock
      overview's rows — meal name, slot label, servings pill and the three
      icons. Check at 1440 and 375.
- [ ] No status banner above the week at either breakpoint. The planned count
      reads beside "in N weeks" in the week scroller; the week's cost is a
      **Cost this week** card under the rail's lists (absent with money off).
- [ ] Free-text rows hover-highlight their source meals and show the amount,
      like the rows above them. No explanatory paragraph in that section.
- [ ] Calendar: a day whose meals are missing ingredients shows **amber** pips,
      not green (it read only the needs-cooking half before).
- [ ] Rail: collapsed strip says just "Recipes"; open header shows the count as
      a badge beside the centred label.
- [ ] "All slots" sits left of Build my week and still switches the day cards.
- [ ] Change weeks → the URL reads `?week=YYYY-MM-DD`; reload → same week.
- [ ] **Over budget** (money on, a budget set, an expensive week): a warning
      banner sits **above** the first day card, one line, collapsed; opening it
      lists the swaps; with no swap available it says dropping a meal is the
      lever and offers no shopping-list button. The rail's Cost this week card
      shows "$X left of your $Y budget", and "$X over" when it is.
- [ ] A meal's menu → Servings is a typeable tile: type 4, press Enter, the
      meal updates; Esc reverts; ± are always visible there.
- [ ] A folded past day reads "3 meals", not the recipe names.
- [ ] Auto builder review step: no meal count line; Reshuffle is right-aligned
      on the same row as "Add a meal".
- [ ] Phone: tap a slot → the sheet's title reads "→ Breakfast · <date>", there
      is no Done button inside it, and picking a recipe closes it.
- [ ] Desktop rail: the A-Z/Cheapest control sits on the chip row (wrapping
      with it, not below it), the **Can cook now** chip filters to cookable
      recipes and is disabled with a tooltip when none are, and the difficulty
      field's empty state reads "Any difficulty".
- [ ] A day's meal cards all align the same way — servings/time/cost on the
      left whether or not the card carries a status glyph.

## Meal planner — the 2026-09-05 thirteen-item batch

Driven live at 1440 and 375 with money ON, so the layout and the servings-menu
fix are confirmed. What's left is the states that drive couldn't reach.

- [ ] Planner with money **OFF**: no week/day/meal cost anywhere, and the rail's
      A-Z / Cheapest control is absent (not disabled).
- [ ] Rail sorted **Cheapest** on a big cookbook (past the virtual-scroll
      threshold): order holds while scrolling, unpriced recipes sit last saying
      "No price yet".
- [ ] The out/low circles on "Missing this week" in a dark theme — soft ground
      with the digit at primary ink; confirm both read at a glance and against
      each other.
- [ ] Phone: a day whose household vocabulary has 5+ slots — every slot heading
      present, in your order, and the per-slot Add reaches the right slot.
- [ ] Phone: a past day — slot headings with no meals should not render.

## Tap targets on a real phone (2026-09-05) — origin ADR-082

Sizes were measured under Playwright touch emulation and desktop confirmed
unchanged, so the mechanism works. What's left is whether it *looks* right on
glass.

**The level chip is no longer part of this** — it was grown to 44px in the
sweep and put back to 32px on 2026-09-09, the owner's report having been about
the rows in the menu it opens rather than the button itself. Those rows are
still 44px; check them below.

- [ ] Stock row's trailing buttons at 44px: the row gap tightened 8→6px to pay
      for the width. Confirm the name still gets enough room and isn't
      truncating words it used to show.
- [ ] Any stock-level menu: rows are taller and the menu widened 200→260px on
      touch. Confirm it doesn't run to the screen edge on your phone.
- [ ] Cookbook rows at 375 — same 30→44px button change, applied for
      consistency with the stock row. Same question about width.
- [ ] Desktop sanity: nothing above should have changed with a mouse. If a
      toolbar looks taller than you remember, the pointer query is matching
      when it shouldn't.

## Cookbook cost + the About rebuild (2026-09-05)

- [ ] Cookbook with money ON: cost per serving on rows and cards, and
      "Cost per serving" in the Sort-by list. A recipe priced from only some of
      its ingredients carries an asterisk — hover says how many.
- [ ] Cookbook with money OFF: no cost anywhere, and the sort axis is gone from
      the dropdown (not present-but-empty).
- [ ] Sort by cost, then have an admin turn money off: the sort should snap back
      to Name rather than leaving an orphaned value in the select.
- [ ] Settings → About: "How you've used Dora" shows cumulative counts (recipes
      curated, meals planned, cooks logged, shops finished), not the dashboard's
      low/out-of-stock numbers. With money off the spend and prices tiles
      disappear entirely rather than showing 0.
- [ ] Recipe page's Cook mode button and both meal-plan "Cook now" menu items
      now wear the chef hat. Confirm nothing else in those menus lost its icon.
- [ ] Stock item → Scanning tab shows a barcode count in the label, matching its
      sibling tabs.

## Salt & Pepper's re-tuned blue (2026-09-04)

The token values were confirmed live and every contrast pair recomputed; what's
left is the judgement call the owner asked for.

- [ ] Salt & Pepper (light): the blue reads a shade deeper and calmer against the
      grey — primary buttons, the focus ring, selected states, Dora's halo.
- [ ] Salt & Pepper Dark: the same accent now sits toward sky blue and paler.
      Check it on a filled primary button (the dark ink on it) and on the theme
      picker's own swatch.

## Reports header at 375 (2026-09-04)

Verified at desktop width: no "Reports" heading, and the caveat tooltip no
longer ends "Estimates, not accounting."

- [ ] Reports at 375, **money off**: with the lede gone too, the header is just
      the range control + the info icon, and it doesn't leave a dead gap where
      the title block was.

## Admin settings — after the group restructure (2026-09-03)

Driven live at 375 and 1280 (nav, both new pages, redirects, save-on-change,
the Users chips and the Add-user dialog), so only the install-shaped checks
remain.

- [ ] Flip **Money** off and on (Admin → Kitchen features → Money) and confirm the
      surfaces follow without a reload — the `/settings/money` sidebar entry,
      shopping-list totals, recipe costs.
- [ ] Flip **Scanning enabled** (Admin → Kitchen features → Stock) and confirm the
      QR labels nav entry and the stock-overview scan button appear/disappear
      without a reload.
- [ ] On an install with **SMTP configured**, Admin → Install → Email: the new
      *Links in emails* and *Weekly deals email* sections save, and a real
      verification email uses the public URL you set.

---
## Sous Chef's new voice commands (2026-09-03)

Three verbs were added — **"ingredients"**, **"tools"** and **"stop"** — and
"stop" no longer exits cook mode (that needs "exit" / "quit" now). The command
list in the help popover was verified live; the *dispatch* can't be driven
headlessly because it needs a real microphone, so these are yours to say out
loud. Recipe with structured steps + per-step links: **Sunday Ragu**.

- [ ] Say **"ingredients"** on a step that has ingredient links — she should read
      the quantities *as scaled to the "Cooking for" headcount*, and name the
      substitute rather than the original where one is swapped in for this cook.
- [ ] Say **"ingredients"** on a step with none — expect *"No ingredients are
      linked to this step"*, not silence.
- [ ] Say **"tools"** on a linked step, and on a free-text recipe — the second
      should say *"This recipe doesn't list any tools"*.
- [ ] Say **"stop"** while she is mid-sentence: she stops talking and **stays in
      cook mode**. Say it again with a timer running: the timer pauses.
- [ ] Turn Sous Chef **off**, leave the mic on, and ask for "ingredients" — the
      answer should still be spoken (a direct question gets a direct answer;
      narration-off only governs unprompted step reading).
- [ ] Say **"exit"** — that, and only that, should leave cook mode.

## Themes after the dark-page fix (2026-09-03)

FU-709 landed: every dark theme now paints its own authored page colour instead
of Quasar's grey, so **all seven dark variants changed background** at once.
Salt & Pepper was rebuilt as a neutral modern-OS pair, and Lemon Tart Dark's
surfaces were re-hued warm with a lifted toolbar. Salt & Pepper (both modes),
Lemon Tart Dark and Pesto Dark were driven and screenshotted at 1280; contrast
was computed for every ink × surface pair. What's left is taste, the four dark
themes not walked, and phone width.

- [ ] Wear the new **Salt & Pepper** light and dark for a session. The brief was
      a modern OS look with one accent — check the blue is doing only
      selected/primary work and nothing important went colourless (level
      squares, essential stripe, attention outlines, alert kinds).
- [ ] **Lemon Tart Dark**: the page is a warm charcoal now, not a blue-grey, and
      the menu bar sits above it with a hairline. Confirm the bar reads as a bar
      and the warmth doesn't tip into brown.
- [ ] The **four dark themes not walked** — Blueberry, Cherry Cola, Sourdough,
      Dragonfruit — are all showing their real page colour for the first time.
      Check cards and rows still separate from the page in each.
- [ ] All of the above at **375px**, where the header hairline and the page tint
      are most of what you see.
- [ ] The **header hairline** across a saturated bar (Pesto light) and a light
      bar (Salt & Pepper light) — one rule draws both; it should be a whisper,
      not a rule line.

## Settings — the 2026-09-03 owner batch

Most of this batch was driven live at 375px and 1280px and those lines are not
here. What's left needs either a real device, a real download, or an install
shaped differently from the scratch stack.

- [ ] Piper voice download works end to end again — Settings → Voice, download a
      voice and confirm it reaches **Ready** rather than erroring with
      `name 'onnx_tmp' is not defined`. (The rename block had drifted into
      `_record_progress`; fixed, and pinned by
      `tests/test_voice_provision_download.py`, but nothing has downloaded a
      real 60 MB model since.)
- [ ] On the **Docker install over plain http://**, About → *Install as an app*
      now says installing needs a secure connection and names HTTPS — not
      "isn't available in this browser". Then, behind HTTPS, confirm the install
      button actually appears.
- [ ] Stores — pick a logo by clicking the store's tile (it saves immediately,
      no dialog), then remove it with the image button. The pane can't drive a
      real file picker.
- [ ] Nutrition matching / QR labels / Unlinked ingredients on a real phone —
      the three panels now share `css/settingsCards.scss`; confirm they read as
      one surface with the rest of the app and that nothing scrolls sideways.
- [ ] Notifications with **products enabled and SMTP configured** — the Email
      block's rows (Weekly deals, Send on, Compact format) are now inline-right
      on mobile; the scratch stack has no SMTP, so only the first row rendered.

---

## Cookbook — the 2026-09-03 chip + tooltip batch

The recipe page's half of this batch was driven live and its lines are not
here. These three are cookbook-list only, and the list body would not render in
the agent's browser pane (the known rAF/paint limitation), so they are yours.

- [ ] Compact view: Dora's "may be short / may be cookable" chip is a glyph in
      an evenly-padded pill — not shoved against its left edge. (The scoped
      rule and its selector were confirmed compiled; only the look is unseen.)
- [ ] Card *and* compact view: hover a kcal figure carrying an asterisk — the
      tooltip reads "Worked out from only part of this recipe." with nothing
      after it.
- [ ] Hover Dora's belief chip in both views: the tooltip stops after "…may
      have run out of X" / "…you're back in stock" — no trailing "Nothing has
      changed" or "Your recorded levels still decide…".

## Recipe view — the empty-state and pack-count tails (2026-09-03)

Everything else in this batch was walked live at 1280 and 375 (chip column,
numbered free-text steps, tools in view mode, the empty-step save block, the
meal-pool line, both chip tooltips, the 16px swap glyph). These are the corners
the seed had no data for:

- [ ] A **structured** recipe with no steps yet, in *read* mode: the block says
      "No steps yet. Add one to link ingredients and tools to it and to get
      per-step cook mode — or switch the step style to free text." — the same
      sentence edit mode shows.
- [ ] A **photo** recipe with no photos, in *read* mode: "No images yet. Add
      photos of your steps…" — again matching edit mode.
- [ ] With money on, open a costed recipe's price breakdown and confirm the
      "Priced N of M" ratio plus the "Units don't match the price" group read
      sensibly now that counted-against-a-measured-pack lands there (FU-855 —
      this is the coverage narrowing; say whether it's acceptable).
- [ ] A recipe ingredient that is on a *non-target* list: the cart tooltip reads
      "On a list — click to remove".

## The two new themes (2026-09-03)

Every token pair in Salt & Pepper and Dragonfruit (both modes) was measured
against the contrast floor in the running app and passes. What a probe cannot
judge is whether they look *good*. (Salt & Pepper was rebuilt later the same
day — its bullet moved to "Themes after the dark-page fix" above.)

- [ ] Wear **Dragonfruit** (light and dark) for a session. The pink primary is
      the strongest colour in the app; check the toolbar, the primary buttons
      and the dashboard hero don't fight each other.
- [ ] Check the **chart palettes** in both — Reports' spend bars and the cook
      timeline — for six hues you can still tell apart.
- [ ] Switch families with **System** mode selected and confirm the OS
      light/dark flip picks up the new families' variants.

## Segmented controls, after the pill convergence (2026-09-03)

Every single-select row of buttons now wears the recipe step-style pill, and
the settings ones grew from 32px to 44px rows with 14px labels. Verified live
on Appearance (3), Reports (2) and the two admin pages; the rest were not
walked.

- [ ] Look at the segmented controls **on a phone**: the settings font-family
      picker has five options and the Reports range has six, both now with a
      bigger label and a taller row than before. Confirm they scroll rather
      than overflow, and that the pill track's rounded ends aren't clipped.
- [ ] The **stock filter panel's sort toggle** lost its hand-painted styling
      (it used to pass `flat` and repaint the active fill itself). Confirm the
      active segment is filled and readable there.
- [ ] The **cook-mode finish dialog's** per-row level pickers also lost `flat`.
      Confirm they still read as three distinct options in a narrow row.

## Planned demand on the stock-item page (2026-09-03)

The signal is unit- and e2e-tested and was confirmed against the dense seed
through the API, but the **card itself has never been seen** — the stock-item
detail route doesn't mount in the agent's browser pane.

- [ ] Open a stock item the plan needs (on the dense seed: Extra Virgin Olive
      Oil, Full Cream Milk, Celery, Parmesan — all "watch") and confirm the
      card renders under "Dora thinks", collapses/expands, and reads sensibly.
- [ ] Record one of them as **Out** and confirm the card turns to the negative
      tone and its copy changes to "the meal can't be cooked until it's back".
- [ ] Find one where a cooked batch covers some meals and check the headline
      counts what's left to cook, not the total.
- [ ] Confirm the card is **absent** on an item with nothing planned against
      it, and on an install with the meal planner switched off.

## Segmented controls app-wide, after the label-size fix (2026-09-02) — origin FU-828

`BaseSegmented.vue` now pins its label to `--font-size-sm`, because Quasar's
`size="sm"` was rendering them at **10px**. Verified on the dashboard's two;
the other **17 call sites** were not looked at, and the labels are now bigger
than the component's authors sized them for.

- [ ] Skim the segmented controls outside the dashboard — the shopping list's
      grouping switch, the recipe method's step-style switch (the pill one),
      cookbook filter sorts, price history, cook mode — for labels that now
      **wrap or overflow** their segment at 14px where 10px used to fit.

## Dashboard — the 2026-09-04 feedback batch: what the walk couldn't reach

The batch **was** driven live at 1280 and 375 on the dense seed (money ON,
products ON, batch cooking OFF, auto-drain reconcile ON), and everything
observable under those settings is already confirmed — nine cards, the flat
Cards menu, the merged hero, Kitchen health's five components, no horizontal
overflow at 375. What follows is only what that one configuration could not
show. See the worklog entry for what was verified.

- [ ] **Batch household — "Next to cook" shows shortfalls, not the calendar.**
      Turn batch cooking on, cook a batch that covers several planned days, and
      confirm the card lists only the meals the pool is short of — not the next
      few days in order. This is the owner's own item and the seed can't show it
      (batch is off there).
- [ ] **Batch household — a meal marked cook-fresh still appears** in that card
      even when the pool covers its day, labelled `fresh`.
- [ ] **Batch household — the empty state reads "the pool covers what's
      planned"**, not "Nothing planned for the next week", when the week is full
      but nothing needs cooking.
- [ ] **Batch household — "Next to cook" quotes the whole batch's yield.** A
      meal linked across three days at 2 servings should read `serves 6`, and
      **Cook** should open cook mode already set to 6 — the same figure the
      planner's chip shows. (The API side is pinned by
      `test_dashboard_router.py`; what's unseen is the two surfaces agreeing in
      a real batch household.)
- [ ] **Manual reconcile mode — Kitchen health scores Plan adherence.** Switch
      reconcile to manual, let a planned day pass, and confirm the component
      shows a score (not "Dora settles past meals for you") with a working
      **Reconcile meals →** link. Under auto-drain it is correctly dormant and
      link-less, which is what the walk saw.
- [ ] **Money OFF — the Shopping lists card drops its dollars** and shows counts
      only ("2 to grab", no price), on all three rows. — origin FU-868
- [ ] **Products OFF — Price drops disappears from the Cards menu**, not just
      from the grid. — origin FU-868
- [ ] **Use it up with an empty cookbook** — the items list still stands on its
      own with no "Cook one of these" block, rather than looking broken.
- [ ] **Before you shop — add an item from the card and watch it leave.** The
      card's premise is "not already on a list", so pressing its cart button
      should remove that row on the next load. Worth one eyes-on because it is
      the behaviour that distinguishes the card from the alerts bell.
- [ ] **A card reordered across the whole list survives a reload** — drag one
      from the bottom to the top and reload. Reorder used to be trapped inside a
      zone; the persisted layout now spans everything.
- [ ] **The greeting's Cute Dino font renders on a cold load** (no FOUT leaving
      it in Nunito) — it is a `@font-face` file, and this is the first surface to
      use it outside the login/title screens.

## Dashboard — after the chunk 6 sweep (2026-09-02) — origin FU-828

The sweep was measured live at 1440px (tokens resolve, radii, surfaces, the
12px floor) — those checks are done and not repeated here. What a probe cannot
judge is whether the result *looks right*, and two branches never rendered.

- [ ] **A dark theme, and a non-Pesto family.** Every nested row moved from
      `--surface-elevated` to `--surface-sunken`; on a dark ground the wells
      should still read as inset, not vanish into the card.
- [ ] **Kitchen health's score number** dropped 40px → 30px to match the other
      hero numbers. Confirm it still reads as the card's headline.
- [ ] Set a primary shopping list: the **Primary shopping list** card should
      render its populated branch fully styled (`.dora-stat-*` tiles laid out on
      a sunken well), not the "No primary set" branch — the dense seed has no
      primary set, so this branch has never been seen since the extraction.
- [ ] Turn on the money cards: **Spend by store** is `defaultHidden`, so its row
      styling is the one nested-row primitive the probe could not reach.

## Dashboard — chunk 1 fixes, confirm the visuals (2026-09-02)

Chunk 1 of `DASHBOARD_PAGE_REVIEW.md` §7 is **shipped and unit-tested**; these
are the items whose *appearance* still wants eyes. Each says what you should now
see. (Two of the original nine were deleted rather than listed — the rounded
money and the timezone date bug are both pinned by tests now; see
`DORA_VERIFY_TRIAGE.md`.)

- [ ] Reconcile chip: with something in the reconcile queue, the "Reconcile N
      past meals" chip in Your kitchen should now carry a **1px border** matching
      its neighbours (it had none — `--border-subtle` was never a real token).
- [ ] Kitchen health, walked through a **dark** theme and at least one non-Pesto
      family: bars should be green / amber / red from the semantic tokens, the
      action links **green not yellow**, and the bar track visible on a dark
      surface. This card previously painted hard-coded light-theme hex in all ten
      themes, so it is the one to look at properly — it also closes feedback D2
      ("dark mode not working").
- [ ] Switch theme while sitting on the dashboard: the Pantry donut should
      recolour **immediately**, without navigating away. Same check on `/reports`
      for the charts.
- [ ] Dismiss the "Dora says" band, navigate to Stock and back: it should stay
      hidden, and reappear tomorrow.
- [ ] Money-off install: Kitchen health should show **no Budget row at all** (not
      a dormant one), and the hint line should never suggest setting a grocery
      budget. Product-less install: no "saved products" hint.
- [ ] Product photos on the deals rows and My Products still render (they moved
      to an authenticated fetch — the failure mode would be the shopping-bag
      glyph where a photo should be).
- [ ] Wide desktop (**≥1440px**): every card is now half-width, where the Pantry
      and Kitchen-health cards used to be thirds and "The week ahead" two-thirds.
      No dead air either way, but it is a visible density change at that size —
      worth a look to say whether you want a 3-up tier back for big screens
      (FU-837 covers the related "short card stretched tall" question).
- [ ] **The merged "What's coming" card** (chunk 3): flip 7 ↔ 14 days, tap a day
      with dots, confirm the detail panel lists that day's meals / expiries /
      shopping. Then check the *selected* segment of that toggle is legible — it
      renders white on brand green at 3.88:1, which is under the 4.5 floor
      app-wide (FU-839), so tell me if it reads badly to you and I'll bring that
      forward.
- [ ] **The merged "Grocery spend" card** (chunk 3): spend leads, budget bar
      below it, "Kept vs RRP" underneath with its own Month/Year/All toggle. Two
      periods are on show deliberately (the budget's, and the toggle's) — check
      the labelling makes that obvious rather than confusing. With **no** budget
      set, it should read "$X spent this week" and offer "Set a budget →".
- [ ] With a **money-off** install the whole Money band should vanish, and with
      **products off** Price drops should be absent from the grid *and* the Cards
      menu.
- [ ] A user with a **saved card layout from before today** should not lose their
      ordering — the retired `calendar` / `budget` / `best_deals` ids are filtered
      out of a stored layout, and "What's coming" inherits the old week-ahead
      slot. Worth one check on your own account, which has a saved layout.
- [ ] **Card error states** (chunk 4) were driven and measured with routes
      force-failed, so the behaviour is confirmed — what's left is your taste
      call: stop the backend, load the dashboard, and say whether five "I
      couldn't load this just now" wells read as calm-and-honest or as alarming.
      If it's too much, the alternative is one page-level notice plus silent
      cards, which is less honest per-card but quieter.
- [ ] Hero mascot centring (feedback L176, never confirmed since B9.8): is the
      72px mascot centred in its tinted box?

## Reports — chunk 4 + the ECharts removal (2026-09-02) — origin FU-833

All four chart surfaces were driven live at :5171 and pass: `/price-history`
(two series, hover tooltip, deal dots), the stock item's **Full history** sheet
(legend + "usually $1.70/100ml" baseline + dashed offer context), Reports'
**Price trends** (two polylines in `--chart-1`/`--chart-2`, **0** canvases) and
the new **Price changes** card (rows, drill-in chart, `aria-label` + `<desc>`).
What's left needs an eye, a theme, or a phone:

- [ ] **The chart in a dark theme.** The SVG reads its colours from
      `--chart-*`, `--divider`, `--text-muted` and repaints on a theme switch
      (FU-824) — switch themes while looking at a chart and confirm the lines,
      gridlines, baseline and legend all follow, with the legend's dashed
      entries still legible.
- [ ] **The chart on a phone.** It is sized in px by its host, so the card
      scrolls horizontally rather than squashing. At 390px, confirm Price
      changes and Price trends both look deliberate rather than cropped — and
      note that **touch interaction is still absent** (FU-705): the hover
      crosshair and tooltip are mouse-only, so a phone reader gets the line and
      the axis labels and nothing else.
- [ ] **Price changes with your own data.** Log two prices on the same item a
      few days apart (different amounts), then check the card ranks it, quotes
      the same denominator as the item's own YourPrices widget, and that opening
      the row draws the two readings you logged.

## Reports — after the chunk 3 restructure (2026-09-02)

The page was driven live at :5171 on the dense seed: four cards render (no
`.report-card` fork left), the Spend axis switch works on all three axes, the
lede reads *"You spent $109.69 across 5 shops…"*, the cook timeline spans the
window, a single 404'd endpoint fails exactly one card, the price-trends picker
searches server-side (`filter=name:ct:yog`) and its clear (x) no longer throws,
money-off leaves exactly two count-based cards and fires no money endpoints, and
390px-wide renders one column with no horizontal overflow. What's left needs
data the seed doesn't have, or an eye rather than an assertion:

- [ ] **The wastage cap.** Waste more than **6** distinct items inside one range,
      then check the card shows *"+ N more, not shown"* under the list and that
      the two lists still end level with each other.
- [ ] **The card set at a glance.** Four cards where there were eleven — is the
      page short enough now, and is anything you actually used missing? Stock
      value over time is deliberately gone (it multiplied a 0–5 level by a
      price); it survives as the dashboard's opt-in pantry-value card.
- [ ] **Squarer cards.** `DashboardCard` dropped to a 10px radius and 16px
      padding app-wide (FU-814 item 4) — confirm the dashboard *and* Reports
      both still look right to you, in a dark theme as well as a light one.

## Reports — chunk 5, the design sweep (2026-09-02)

Driven live at :5171: every card now shows a skeleton instead of a false empty
state while loading (re-measured — zero false empties), the ten empty states
carry B9's muted icon, a real Tab press lands a visible `2px` focus ring on the
row links, the cook chart carries `role="img"` + a generated summary, and the
range label reads correctly across all five bounded ranges plus "All time".
Two things want your eye rather than an assertion:

- [ ] **The mascot, back where you had it.** The hero and welcome-note mascots
      are on 2px / 1px padding again (the chunk-6 sweep had doubled and
      quadrupled them). Confirm both look centred to you.
- [ ] **The skeletons.** Throttle or just watch a cold load — do the outlines
      match what lands, or does anything visibly jump when the data arrives?

## Shopping list — receipt lightbox (2026-09-01)

Only affordance in the v4 cutover audit with no live evidence — the seed ships
no attachments.

- [ ] On a finished list, add a receipt photo, tap the thumb, confirm the
      lightbox opens and closes on Esc and on a backdrop click.

## Meal planner — the 2026-09-03 owner batch (~35 items)

Most of this batch was driven live with Playwright at 1280 and 375 and deleted
from this list: the calendar opening on September for a week starting 31 Aug;
day squares holding 34×34 with five pips wrapped and no "+N" (measured before
and after piling meals onto one day); the burger on "Build my week"; the armed
slot's one-line `→ Lunch · 06/09/2026` + **Done** at 36px with zero per-row
"→ Breakfast" lines; the two dot-led shopping lines ("3 of 4 to buy" red, "2 of
6 to buy" amber); "All ingredients · 18" on one line; the status strip without
"already on a list"; the chef hat left of the servings pill; the rail's cooked
count as a real input with the disabled `−` hidden at rest; **all four multi-day
cook scenarios** (link, change-days leaving no ghost, remove-the-cook asking
first and taking its leftovers, servings-to-zero with no 400); the straddling
batch keeping both leftover days; the builder's review rows not overlapping with
"Pizza dough (60% hydration)" in them; servings defaulting to the household's 2;
"I'll pick myself" gone; Clone gone; the recurring form's even 12px gaps and
equal-width date fields; the mobile overflow menu carrying all five week
actions; the phone's plain (un-collapsed) week card with its ingredient
breakdown; and money-off producing `cost_total: null` with 0 of 12 entries
priced and no `$` anywhere in the builder.

What's left needs paint, a real finger, or data this seed doesn't have.

- [ ] **The pool count as a typed field, with a real keyboard.** Click (or tap)
      a rail row's count, type `6`, press Enter. Then try the awkward paths a
      script can't: type nothing and blur; type `abc`; type `-2`; press Esc
      mid-edit. Each should leave the count as it was, not blank or negative.
- [ ] **Six pips in a 34px calendar square, at real screen scale.** The
      geometry is measured, but whether two rows of three tiny dots under a date
      *reads* rather than looking like dirt is a paint judgement.
- [ ] **The rounding fix against a real repeating decimal.** The seed's
      quantities all round clean; the owner's case was "needs 31.333333333333332
      tbsp". Plan the same recipe three times with a `1/3`-ish quantity (or scale
      one) and confirm the right rail reads `31.33 tbsp`. Unit tests pin the
      formatter, so this is confirming the aggregate reaches it.
- [ ] **The stacked builder review row on a phone.** It no longer has a
      viewport breakpoint, so 375px now gets exactly what 1280px gets: check the
      two selects, the stepper and the delete still sit comfortably and the
      delete is thumb-reachable at the right edge.
- [ ] **The recipe name as the swap control.** It reads as a title, not a
      button. Confirm that's discoverable — hover shows the pointer and the
      "Swap for another recipe" tooltip, and the swap glyph beside the name is
      noticeable enough that the swap button's removal isn't a loss.
- [ ] **A cook batch whose cook day you actually reach.** Advance the household
      date (or plan Mon+Wed and wait) so a linked cook's day arrives, cook it,
      and confirm the leftover days read as covered rather than needing a cook.
- [ ] **"Apply recurring" end to end** — the polish is measured, but apply a
      template across four weeks and confirm the forked weeks land where the
      dates said, past days skipped.

## Meal planner — the 2026-09-01 owner batch

Most of this batch was driven live in the pane and deleted: the meal-slot
settings→planner sync (add + delete, no reload), the print-view slot columns,
the right rail's one-line headline / folded lists / left-hand level dots /
full-demand hover, the three right-rail panes sharing one right edge, the 340px
rail, rows with no meta line, past-day fold on a week containing today (and no
fold on a fully-past week), the axis filters narrowing 16→2→0, clicking a
recipe with no slot armed doing nothing, and the phone day-strip pips. What's
left needs paint, a real pointer, or a real phone.

- [ ] Open the rail's two new dropdowns ("Any time" / "Any level") with the
      mouse and pick a value — QMenu never opens in the pane, so only the
      underlying state was exercised. Check they clear back to the placeholder.
- [ ] On a **phone**, tap a rail row's cooked-count field and confirm the ±
      buttons appear either side of it (there is no hover on touch), and that
      the on-screen keyboard doesn't cover the row you were editing. *(The
      desktop half — steppers hidden at rest, revealed on hover, row never
      shifting — was measured live 2026-09-03: `visibility: hidden` at rest on
      every unhovered row, including the ones whose `−` is disabled, which is
      the bug that batch fixed.)*
- [ ] Scroll the right pane with "Full ingredient demand" expanded — the
      calendar is now `position: sticky` inside that scroller rather than a
      sibling above it. Nothing should show through it as rows slide under.
- [ ] The folded past-day header: chevron, day, date, then the meals it held on
      one clamped line. Confirm a long list of meal names truncates rather than
      pushing the kcal figure off the card.
- [ ] The phone day-strip pips at real size (4px, now up to **6 wrapped into
      rows of three**, and the "+N" label is gone). Confirm they read as
      distinct dots at that size, that six of them don't crowd the chip's
      letter and date, and that the white-on-primary override on the *selected*
      chip is legible.
- [ ] Drag the window between 1024px and 1200px. The rail took 60px from the
      week pane, so the toolbar's compact threshold moved 1120 → 1180: check
      "Build my week" drops its label before the toolbar wraps to a third line,
      and that nothing in the status row (now carrying the "All slots" toggle)
      overflows.

## Accent ink + Dora's voice (2026-09-01)

Token wiring, contrast ratios and nav order were verified live in the pane
(all ten themes resolve `--accent-ink`; active tab measured 5.09:1, was 1.25:1)
and deleted. What's left needs actual paint, which the pane never does.

- [ ] Walk the light themes (Pesto, Lemon Tart, Blueberry, Cherry Cola,
      Sourdough) and confirm the deep-gold/deep-hue accent still reads as *the
      accent* and not as brown mud — tabs on a stock item, the settings sidebar
      bar, an Appearance theme card.
- [ ] Same walk in the five dark themes: nothing should have visibly changed
      except a slight lift in Pesto Dark, Lemon Tart Dark and Cherry Cola Dark.
- [ ] Toolbar and main-menu buttons still carry the *bright* accent — that was
      deliberately left alone. Confirm it didn't get dragged darker.
- [ ] The burger glyph at its small sizes — 12px on the meal-plan rail chip and
      the shopping-list note, 14px in Dora chat and the plan row, 16px in a
      stock row. Does it read as a burger, or as a hamburger menu? (FU-800.)
- [ ] Sanity: the "Dora suggests" dashboard card and a "Dora thinks" stock row
      side by side now carry the same glyph.

## Cook mode — the 2026-09-01 eleven-item batch

Driven live in the pane and deleted: declared vs sniffed timers, the three
section headers/icons, substitute gating, the swap hint, the whole finish modal
(preselection, stepper, a real Done), and the batch gate. What's left is what
the pane can't produce — it never paints a frame, so nothing below was *seen*.

- [ ] Hover a progress-bar segment on a recipe with ≤14 steps: it should grow
      toward the current segment's height and warm up. Tab to it too — the focus
      ring should land on the bar, not around it.
- [ ] Eyeball the three panels side by side (Ingredients / Tools / All steps) —
      they were three different-looking things and are meant to read as one now.
- [ ] Finish modal on a **phone width**: the level buttons drop to their own
      full-width line under the name, cart stays with the name.
- [ ] Finish modal on a recipe with **many** ingredients — the list scrolls at
      50vh; check it doesn't fight the dialog's own scroll.
- [ ] A household with **more than three** stock levels: the finish row renders
      all of them as segments (it reads the table, it doesn't assume three).

## Stocktake — belief copy (2026-09-12)

- [ ] Review phase: each row reads "Dora thinks Low · but is currently
      Stocked", both words from the same vocabulary, with no reason paragraph
      underneath. A household level *off* the three canonical sequences still
      shows its own name in the second pill.
- [ ] Walk card on an `uncertain` item: "Dora thinks low" on its own line, then
      a reason starting "Bought N days ago…" — no band or tilde inside it.
- [ ] Stock overview: open a row's level picker where Dora disagrees — the menu
      header says the band once, not twice.

## Stocktake — theme, copy, locations, add-to-list (2026-09-01)

Most of this batch was driven live in the pane on the pesto **light** theme and
deleted. What's left needs a surface the pane can't produce.

- [ ] Run a stocktake under a **dark** theme family: the shell is still dark
      (it now inherits `--surface-page` rather than pinning black), and the
      review/sweep headings and the walk card's belief box are still legible
      against it.
- [ ] Hover the (?) glyph beside "Checked every fortnight · N days overdue",
      then the "Push 3 days" button: each tooltip wraps to a narrow column
      instead of one screen-wide line. (The 280px cap + `white-space: normal`
      were confirmed computed; the rendered hover wasn't — the verify pane
      can't fire Quasar's hover.)

---

## Stock detail — verdict cart, QR Label, timeline (2026-09-01)

- [ ] On a stock item whose "worth buying" card offers add-to-list: the action
      is a round cart button. Tap it — it adds to a list and the glyph flips to
      the on-list cart, same as the stock overview row. Tap again: it comes off.
- [ ] Open an item already on a list: the card's cart already shows the on-list
      glyph on first render (not "add"). On two+ lists it shows the multi glyph
      and tapping opens the list popover.
- [ ] Scanning tab heading reads "QR Label".
- [ ] History tab: the timeline's event icons have clear space from the panel's
      left edge.

---

## Stock overview — the 2026-09-01 copy + level-dot batch

- [ ] Open "Log a price" (dashboard quick action) and Quick-add: the level in
      each result row is the small shared dot, sized and coloured like the one
      on the shopping-list add rows — no filled circle with a box icon. Hover it:
      the tooltip names the level (or "No level set").
- [ ] In the price form, the "Pack count (optional)" field no longer shows a
      tooltip on hover.
- [ ] On a stock row with no expiry, hover the calendar glyph: it reads exactly
      "No expiry set".
- [ ] On a stock row that's due a stocktake check (and has no "Dora thinks"),
      open the level picker: the header reason ends at "It's been a while since
      this was counted."

---

## Cookbook — cook-mode confirm lists names (2026-09-01)

- [ ] Press the cook button on a cookbook card/row for a recipe you're short
      on: the confirm reads "You're missing these ingredients:" over a vertical
      list of names, not a bulleted count. (Same shared component walked on the
      recipe page; only this entry point is unwalked — the cookbook list won't
      render in the verify pane.)

## Cookbook — cook/cart tooltips render (2026-09-01)

- [ ] Hover the cook button on a cookbook card and a compact row: reads "Enter
      cook mode", or "Missing 2 ingredients" on a short recipe.
- [ ] Hover the cart button across three recipes: "Add N missing to a list",
      "Some ingredients are low", "All ingredients in stock".
      (Strings were confirmed on the live components; only the hovered popup
      itself is unchecked — the verify pane can't hover reliably.)

## Login — the Firefox-Android mascot line (2026-08-31) — origin FU-797

- [ ] On the reporting phone (Firefox, Android), open the login screen a few
      times cold: the thin grey line beside the mascot should be gone. It was
      **not reproduced** on this box, so this is the only proof there is.

## Recipe view — missing/swap chip, swap states (2026-08-31) — origin FU-793

- [ ] With a missing ingredient that has a substitute **you have**: the chip
      reads green `Swap ready` and its menu lists the substitute. Verified only
      against a faked API response — no seed fixture reaches it.
- [ ] Same with substitutes you'd have to buy: amber `Missing · N swaps`, and
      each menu row still offers its own add-to-list.

## The dense dev dataset (2026-08-31)
Boot `dora-verify-backend` (now seeds `dense` by default) and log in as
`dora`/`dora`. The data and the DTOs are confirmed — every claim below was
checked over the API — so what's left is purely *does it render*:
- [ ] **Cook mode on "Sunday Ragu"** — the structured face with 10 steps, 6
      sub-steps under 3 of them, two section headers, hints, and per-step
      ingredient/tool chips. This face has never had a fixture before.
- [ ] **Cook mode on "Weekend Focaccia"** — the image face, 5 photos in order.
      They're drawn step cards, so a wrong order or a wrong photo is obvious.
- [ ] **The two poles side by side on the stock page** — open `Bicarb Soda`
      (every optional block should collapse) then `Extra Virgin Olive Oil`
      (every block populated, including the above-usual price chip).
- [ ] **`Sriracha`'s History tab** shows the "16 older events not shown" footer.
- [ ] **The stocktake runner** has members in Review (Weet-Bix), Walk (5) and
      Sweep (Rice Wine Vinegar) in one session, and Water Crackers stays silent.
- [ ] **The cookbook** shows cookable, not-cookable and unknown cards together,
      a photo card next to no-photo cards, and the version pair.
- [ ] **The meal planner** across three weeks: last week all eaten, this week
      with the three-night cook batch, next week showing template provenance.
- [ ] **The shopping list archive** reads like a real household's (8 date-named
      shops), and the draft's budget-deferred line renders as deferred.

## Weekly deals email (2026-08-29) — origin FU-789
Built and driven end to end with a captured sender: the gate chain, the send, the
dedup, both rendered formats and the scheduler registration are all confirmed.
What a captured sender can't prove:
- [ ] **A real send through real SMTP arrives.** Configure SMTP, subscribe with a
      verified address, set today as your send day, and confirm the mail lands —
      the job's own SMTP short-circuit means a dry-run install never exercises
      `smtplib` at all.
- [ ] **Both formats render in an actual mail client** (Gmail web + a phone).
      The cards are table-based inline-styled HTML; the brand banner is an
      inline-CID image, which only resolves in a real client.
- [ ] The 07:00 send fires **on the household clock** after changing the install
      timezone — the job is registered hourly and gates internally, so this is
      the check that the gate, not the cron, is picking the hour.

## Settings feedback batch 1 (2026-08-29)
Driven live at 1280×900: nav order (Account → About), both notification sections
with banners above their rows, the voice-input and no-Piper warning cards, the
Gemini Base URL field, and toggle-to-label centre offset measured at 0px on every
row. Only what that run can't reach:
- [ ] At **375px** the Settings rows still stack label-above-control, and the
      (?) chips stay tappable rather than colliding with the wrapped label.
- [ ] An **info chip tooltip opens on a touch device** (long-press) — the chips
      now carry the whole explanation for Evening brief and Weekly deals, so a
      phone that can't open one loses the copy entirely.
- [ ] On an install that **does** have Piper, Settings → Voice still shows the
      voice catalogue with the lede above it (only the missing-engine branch was
      exercised live).
- [ ] Warning cards on Notifications and Voice read correctly in a **dark
      theme** — they use `dora-bg-warning-soft` on `text-primary`.

## Recipe + cookbook feedback batch (2026-08-29)
All six items driven live at 1280×900: the cook-now sub-line is gone, both
details drawers render the nutrition card, all 13 filters measure 210px with no
clipped labels, the star computes 18px, and the two bugs were reproduced and
re-walked (unit `loaf`→`g` picks cleanly; a step's ingredient links save 204 and
persist). Only what a light-theme desktop run can't judge:
- [ ] The **Additional details** and **Version information** cards read as cards
      in a dark theme — they use the same border + surface as the nutrition one.
- [ ] At 375px the 18px star still sits level with the heart and cart icons on a
      recipe card, and the filter fields still scroll sideways rather than wrap.

## Shopping list — overview card (2026-08-29)
Built and driven live at 1280px and 375px on all three faces, so the layout,
the figures, the rename dialog, the quiet shop-day save and every relocated
lifecycle action are already confirmed. Only what a headless run can't judge:
- [ ] The status pill reads cleanly in a **dark theme** (Cherry Cola Dark,
      Pesto Dark) — it gained a border and a glyph, and draft/shopping/done use
      soft-background + full-strength ink.
- [ ] On a real phone, the card's chevron and the rename pencil are comfortable
      thumb targets, and the card doesn't push the first list row off-screen.

## Toasts, download progress, QR logo (2026-08-28)
Code-complete, suites green; no browser pass — both scratch verify pairings
were held by other sessions.
- [ ] The `info` toast (e.g. "Swap undone." from a meal-plan swap) reads as a
      Dora surface: elevated background, normal text, info-coloured spine and
      icon. No blue slab, no bullhorn.
- [ ] Same toast in a dark theme, and again after switching theme with one on
      screen.
- [ ] Settings → Nutrition → Download a USDA dataset: the bar fills with real
      MB during the download, then goes indeterminate under a climbing row
      count while parsing.
- [ ] Settings → Voice → download a Piper voice: MB-of-MB and a filling bar,
      not a spinner.
- [ ] Stock item → Scanning → QR: the D/D mark is centred and crisp, and a
      phone scans both the dialog code and a printed sheet cell.

## Cookbook: the 2026-08-28 rating + kcal batch
Driven live at 1280×900 on the scratch instance: the filter order, the desktop
wrap vs the mobile scroll, the kcal chip beside Difficulty, the compact row's
"N ingredients", the "Kcal ≤ 500" cut (15 → 13, unrated kept), and the recipe
list refetching after a stock write. What's left needs **complex mode with a
food catalogue imported**, which no verify instance has.
- [ ] Rating pill on cards and rows: hover shows the five-star reading; the
      pill sits in the same spot on every card down a grid.
- [ ] A partial rating shows its asterisk and the "part of this recipe" hover.
- [ ] "Health stars ≥ 3" hides a 0.5-star recipe and keeps an unrated one.
- [ ] Nutri-Score install: the A–E badge renders in both views, and the filter
      label reads "Nutri-Score at least".
- [ ] The pill's tint reads correctly in a dark theme (it sits on
      `--brand-primary-soft`, which dark themes define as translucent).

## Recipe rating: the scheme picker + Nutri-Score (2026-08-27)
No browser pass — the rating only paints in complex mode with a dataset
imported, and every verify backend resets the dev DB. Arithmetic is pinned
server-side against the official worked examples; what's owed is pixels and
plumbing.
- [ ] Settings → Nutrition: the three-way picker saves and survives reload.
- [ ] Nutri-Score badge: right letter lit, readable in light **and** dark, and
      the yellow C's dark ink actually lands.
- [ ] Cookbook: chip renders on card + row, filter says "Nutri-Score at least",
      sort axis is named for the chosen scheme and puts A above E.
- [ ] Switch scheme with the cookbook open — chips swap, no stale stars.
- [ ] Recipe page: "How this was scored" ledger opens, salt row present (not
      sodium), fruit-and-veg line says "fruit, veg or legumes" with no nuts.
- [ ] Region → "Match this device" on a `fr-FR`/`Europe/Paris` device offers
      Nutri-Score, not Health Stars.

## Meal planner — the month-grid calendar (2026-08-30) — Unit 3
Driven live at 1280: 42 numbered cells over six rows, out-of-month days dimmed
but still clickable buttons, today a filled disc (not a ring), focused-week
band, per-meal pips, hover naming the actual meals, click-a-day moving the week
and bringing that day's card into view, and arrow / PageUp / PageDown grid
navigation that doesn't leak into the week paging. What's left is your eye.
- [ ] Walk the **five theme families in light and dark**: the focused-week band,
      the dimmed out-of-month days and the three pip colours all need to stay
      apart from each other and from the cell background. F38 was a
      theme-awareness complaint on this page.
- [ ] With **4+ meals on one day**, confirm the "+N" reads cleanly at the pip
      size and doesn't crowd the date.
- [ ] Confirm the **scroll-to-day** on a full week — the scratch week was empty,
      so the pane didn't need to scroll (the card was already in view).
- [ ] With **reduced motion** on, confirm month paging still changes month
      (the slide flattens; nothing should depend on the animation).

## Meal planner — the rebuilt rail (2026-08-30) — Unit 2
Driven live at 1280 and 375: collapsed on arrival (46px labelled strip), opens
on click and on arming a slot, chips are mutually exclusive with `aria-pressed`,
empty chips stay greyed in place, Dora suggests returns ranked rows with server
reasons, focus lands in the search on auto-open, Esc cancels the target and the
rail stays open, the armed slot is named at both ends, and the mobile sheet gets
the same chips. Row-height contract measured exact (64px). What's left needs a
dataset or your eye.
- [ ] **Owner call:** the chip row wraps to **three** lines at the rail's 280px
      (the brief expected two — the counts add width). Fine, or drop the counts?
- [ ] With **50+ recipes**, confirm the list virtualises smoothly and doesn't
      judder mid-scroll — the seed has 15, so that path has never run.
- [ ] With **batch cooking on**, confirm each rail row's `− N +` pool controls
      and "Log a cook" work, and that the bigger on-hand number answers F42
      ("a bit hidden… make the number bigger maybe").
- [ ] In the **Build my week** wizard, confirm the chips work alongside the row
      checkboxes and that no recipe can appear twice.

## Meal planner — app-shell conversion (2026-08-30) — Unit 1
Driven live at 1024/1280/1440/375 on the scratch stack: no document scroll, no
h-scroll, toolbar 90px and non-wrapping at all three desktop widths, all three
pane bottoms inside the viewport (884/900 — the old sticky-rail overhang is
gone), the week pane scrolls, the ⋮ menu carries all six actions, and mobile
still routes to the untouched focus view. What's left needs your eye or a state
the scratch seed doesn't have.
- [ ] Run the ⋮ actions for real: **Duplicate to next week**, **Print this
      week** (native print dialog), **Save week as template…**, and **Clear
      week** — only the menu's contents were confirmed, not the verbs.
- [ ] With the **OfflineBanner** showing (go offline), confirm the three panes
      still end inside the viewport. The banner is the second offset the old
      hardcoded `calc(100vh - 32px)` ignored.
- [ ] With a **large cookbook** (~50+ recipes), confirm the rail's list scrolls
      inside the card with the search box and target banner staying pinned —
      the scratch seed only has eight.
- [ ] At **1024px**, confirm "Build my week" as an icon-only button still reads
      as the primary action next to the ⋮ (it drops its label under 1120px).

## Meal plans: the 2026-08-27 add-to-list batch
Driven live end-to-end in the pane on both surfaces: the shared picker opens
from the planner and from a recipe, rows carry quantity + "for <meal>", already-
on-a-list rows come up unticked and are skipped by Select all, the add round-
trips, and the week's counts moved 6-to-buy/3-on-a-list → all-on-a-list. What's
left is what a 0×0 non-painting pane can't show: pixels, and the desktop layout
branch (`$q.screen` is permanently mobile there).
- [ ] On a real phone, open **Build my week**. Confirm the card fits the screen
      with no horizontal scroll, the three step labels sit under their dots, and
      on the Review step each meal's day/slot pickers stack under the meal name
      with the servings stepper and the swap/remove buttons on one line beneath.
- [ ] Same modal, Review step: confirm the ingredient list scrolls with the
      dialog rather than inside its own short window.
- [ ] On a desktop width, confirm the planner's right-hand shopping card shows
      the outstanding count as its headline number, "N already on a list"
      beneath it, and a button reading **Add N to a list**.
- [ ] Add to a list with **+ New list** chosen: confirm the name pre-fills as
      *Meals: week of <date>* and that creating it lands you on the new list.

## Buy verdict is money-gated (2026-08-27)
Backend + vitest green; no browser pass, because every `dora-verify-backend*`
launch config points at :5170 with `DORA_ALLOW_DESTRUCTIVE=true` (see FU-758).
Needs one run **with money off** and one **with money on**.
- [ ] Money **off**: stock item detail shows the "Dora thinks" belief card and
      **no** buy-verdict card beneath it; Stock overview rows and shopping-list
      lines show no buy/wait/skip badge; no `$` or "N price samples" text anywhere
      those used to render.
- [ ] Money **off**: Settings → Assistant, the *"Should I buy this?"* toggle is
      greyed out with the "Needs money features…" line under it (and reads
      "ask an admin" only when you're not an admin).
- [ ] Flip money **on** in Admin → Features without reloading: the verdict card
      and badges appear, and the Assistant toggle re-enables **still holding your
      previous choice** rather than resetting.
- [ ] Money **on**, currency set to something non-`$` (Settings → Region → EUR):
      expand a verdict card and confirm the price reason reads *€3.85 last shop ·
      usually €3.80* — the amounts now format client-side, so this is the line
      that used to hardcode a dollar sign.
- [ ] Money **off**, hit `GET /api/stock-items/<id>/buy-verdict` directly →
      403 with "Buy verdicts need money features…", not a composed verdict.

## Settings: the 2026-08-27 units + voice batch
The units setting was driven live end-to-end (saved, validated, propagated
through `/api/health`, and confirmed to narrow the pickers to metric / imperial
/ US). What's left is what the pane can't show.
- [ ] Firefox: open Settings → Voice. Confirm the "no text-to-speech voices
      installed" note matches what Firefox actually reports on your machine,
      that the device-voice card's **Preview** button is hidden rather than
      silent, and that Dora still speaks through her neural voice. — origin FU-751
- [ ] Flip Units to **US customary**, then open a recipe's ingredient editor and
      the price-entry widget on a real (non-dev) build. Confirm both dropdowns
      offer US units, and that a recipe row already holding `g` still shows `g`
      in its own dropdown.
- [ ] Flip Units to **US customary** and confirm a per-unit price re-quotes in
      `/lb` or `/oz` rather than `/kg` — the denominator and the picker come off
      the one setting now, so they should never disagree.

## Cook mode: the 2026-08-28 header + image-mode batch
Driven live at 1280 and 375 (Playwright, scratch instance): three header bands
with real gaps, Sous Chef labelled on desktop / icon-only at 375, the info
button only present while Sous Chef or the mic is live, headcount a ±44px
stepper that clamps at 1, "Step 3 of 6" as a badge over a six-segment bar, and
image mode paging one photo at a time with a magnify-and-pan zoom and a Finish
that opens the finish dialog. Nothing below is a re-check of those.
- [ ] On a **real phone**, with wet or floury hands: are the Sous Chef / mic
      icons and the headcount ± actually hittable at 44px, or do they want 48?
      (Measured, not felt, in the pane.)
- [ ] Open **your own photo recipe** in a **built** SPA or the desktop bundle —
      not the dev server, which proxies `/api` and hides a wrong base URL. Photos
      should render; a failure now says "This step's photo couldn't be loaded"
      rather than showing the word "Step 1". Last unverified corner of FU-755.

## Stocktake: the 2026-08-27 dataset + help move
Driven live against the dev seed: `/api/stocktake/session` returns a populated
Review (1 confident item), a Walk spanning low and medium confidence, and a
Sweep — and the runner's (?) is now an anchor to `#/help?q=How+stocktake+works`
with no dialog in the DOM.
- [ ] Walk a full run in the browser: confirm the Review phase renders its
      pre-ticked card, the Walk's per-item reasons differ from each other rather
      than all reading the same, and the Tidy-up phase appears at the end.
- [ ] Demo mode (`DORA_DEMO_MODE=true`): confirm the showcase seed produces the
      same three-phase shape, with the curated names (Plain Flour, Greek Yoghurt,
      Tomato Passata, Bicarb Soda, Rice Wine Vinegar).

## Stock: the 2026-08-24 feedback batch
Suites green, nothing walked — the verify configs reseed the DB, so the build
session didn't run one.
- [ ] Log a price: type a pack count, clear it, confirm no validation error and
      **Log** still submits.
- [ ] Bulk-select on Stock overview: **Move location** and **Restock** now carry
      icons like their neighbours.
- [ ] Stock item detail, phone width, item with a very long name: name stays on
      the top line, truncates with "…", Delete stays inline, back arrow not orphaned.
- [ ] Same page: the "Dora thinks" chevron and the buy-verdict chevron line up in
      one vertical column.
- [ ] **Scanning** tab (needs scanning on): QR renders inline on open with
      **Print** beside it, no "Show QR" button left in the header, barcodes list
      underneath. **On this install expect a 404** until FU-717's deploy fix lands
      (FU-648 / FU-710, same module).
- [ ] Barcode rows: a code you typed has no caption; one from a linked product
      reads "(from product: …)".
- [ ] The (?) beside **Substitutes**, **QR label** and **Barcodes** lands on
      Help → Guides filtered to that guide.
- [ ] Buy verdict wording: a **non-essential** item marked low reads "Might be
      worth buying"; flag it Essential and it becomes "Probably worth buying";
      an essential that's **out** reads "Worth buying now".

## Recipe page: the 2026-08-26 feedback batch
Driven live against a throwaway backend and confirmed: `/cookbook/:id` renders the
redesigned page (old page deleted), **New version** lands on `/cookbook/<new id>`
with the sections cloned into their cards, every header axis carries the
cookbook's own glyph in both read and edit mode, the Unit field's "Or type your
own" hint is gone, and a click on the photo tile's hidden file input no longer
bubbles back up to reopen the photo dialog. Left for you:
- [ ] **The photo round-trip end to end:** tap the photo → **Change photo** →
      pick a file → the dialog is gone *and* the new photo is on the tile. (The
      propagation half was proven; the native file picker can't be driven by an
      agent.)
- [ ] The Unit dropdown opens and offers only ingredient units — `g`, `ml`,
      `cup`, `pinch`, `pack` — with **no** `kJ` / `cm` / `ft`, and typing a word
      it doesn't know now adds nothing. (Quasar popups don't render in the agent
      pane — FU-737.)
- [ ] **On a phone:** the facts strip (now icon + label per fact) still scrolls
      sideways as one line without dragging the page. It measured 72px of
      in-container overflow at 375px — designed behaviour, but the icons made it
      longer, so confirm the last fact is still reachable.
- [ ] Both eyebrow and facts icons read correctly in a dark theme.

## Recipe page: the 2026-08-24 feedback batch
The session that built it drove the page live at the agent pane's (mobile-shaped)
viewport and confirmed: no Fraunces anywhere (everything renders in Nunito), the facts
line is `nowrap` + `overflow-x: auto`, the **Details** button opens the cost modal with
the right totals / coverage bar / ranked lines / grouped unpriced reasons and "$30.00 per
kg" instead of "$0.00 per g", the **Step style** control reads Structured · Free text ·
Image with one shared **Edit** pencil, the method editor opens maximised with the text
pre-filled and round-trips an edit, structured steps render as cards with the
up/down/sub-step/hint/remove row and **no drag grip** at phone width, sub-steps indent
with their own numbered bullet in both editor and read view, a new section renders as a
card with its own name / count / **Add to <section>** / ⋮ menu, **Right now** counted only
what was left and flipped to "Already on a shopping list" when nothing was (that cell's
action became a **button on the card's right** in the 08-24 merge — the counting is
unchanged, the link isn't), the missing chip reads **"Missing — swap in stock"**, the picker arrives
with an on-list row unticked and badged **"On This week"**, and **Version information**
shows created + last-updated and both versions with their created dates (last-updated
filled in the moment a Save landed).

What that pass could **not** cover — the pane never composites and reports a 0px
viewport, so every `$q.screen` branch renders in its mobile form:
- [ ] **Desktop width:** the drag grip on a structured step is visible again above 768px
      and still reorders by dragging; the method editor opens as a normal dialog, not
      full-screen; the cost modal isn't cramped; the action row and the two-column
      ingredients/method body still read well.
- [ ] **On a real phone:** tap **Edit** on a free-text recipe with one short line — the
      keyboard opens *below* the field and the field stays visible. (This is the reported
      bug; the fix is the full-screen editor.)
- [ ] **On a real phone:** the facts line (Serves · Prep · Cook · Total · Difficulty ·
      When) scrolls sideways as one line and doesn't drag the page with it.
- [ ] The ingredient row's ↑/↓ + cart + delete cluster is reachable with a thumb (it's
      permanently visible below 768px) and doesn't crowd long ingredient names.
- [ ] **Additional details** — tags, tools, source URL and notes all still save from the
      merged panel, and its caption reflects what's set.
- [ ] The two remaining inline `q-popup-edit`s on a phone — a structured **step's text**
      and a **section's name** — don't have the keyboard-over-the-field problem the
      free-text block had. If they do, they want the same treatment. (The ingredient
      **quantity** popup was removed in the 08-24 merge; the row opens its editor now.)
- [ ] A recipe with **no** version siblings shows Version information with created,
      last-updated and the "only version" line (verified with siblings; not without).

## Shopping list — planned store round trip (2026-08-28) — origin batch 3
The only part of batches 1–3 not walked live: the scratch backend was serving
pre-change code and couldn't be restarted (both scratch pairings were taken by
parallel sessions). Everything around it was verified — see
`DORA_VERIFY_TRIAGE.md`.
- [ ] On a **draft**, set **Store** on a row to somewhere it doesn't already
      resolve to (e.g. Aldi on an item whose default reads "Coles (default)").
      Reload the page: the field still says Aldi, without "(default)".
- [ ] With that set, switch **Order by → Store**: the row is now under an
      **Aldi** section, and "Where you'll spend it" counts it against Aldi.
- [ ] Clear the field: it reverts to `<the inherited store> (default)` and the
      row goes back to its old section — *not* to "No store set".
- [ ] Start shopping, open a line's price sheet: **Bought from** is pre-filled
      with the planned store. Change it to somewhere else and save — the plan
      face's Store field must be **unchanged** (buying somewhere once is not a
      change of plan, and must not write back).
- [ ] Check the item's own **usual store** on its detail page is also unchanged
      by any of the above.

## Shopping list — the 2026-08-26 feedback batch
Plan face was driven live at 375px and 1280px (rows, store card, finish dialog, a
real move-to-new-list); the bulk bar this section used to cover was deleted
2026-08-28. Left for you:
- [ ] Upload a logo for a store you use, then check its colour on "Where you'll
      spend it" *and* on its logo placeholder elsewhere. A greyscale logo should
      fall back to the name-derived colour — saturated in the bar/dot, pale
      behind the placeholder's letter.
- [ ] Run and receipt faces on the rebuilt toolbar — FU-739. Watch the bottom of
      the run face: the sticky shop footer and the new Clear-all/Delete footer
      are both down there.
- [ ] Desktop: the toolbar scrolls sideways and "Start shopping" is the button
      that runs off the edge — decide if that's acceptable (FU-738).

## Shopping list — run face and receipt face (2026-08-23) — origin FU-729
Agent drove both faces in a 430×900 browser with money on and confirmed: run-face
sections with per-section `0/1` progress, whole-row tick, the Undo toast, a
cleared section collapsing to "Aldi — all 1 picked", the price sheet writing
`~$7.99 → $7.25` and the footer total following it live, the receipt's itemised
lines / store split / totals reconciling ($1.30 + $6.00 + $3.20 = $10.50), Amend
unlocking exactly the three fields, and an amended price rewriting the harvested
observation in place. These are the parts a headless viewport can't prove.
- [ ] **Run face on your actual phone, in a shop or a decent imitation:** rows are
      comfortably tappable one-handed while moving, and you don't mis-tap the
      price button when you meant the row.
- [ ] **The price sheet with a real on-screen keyboard up:** the amount field and
      the Save button are both still visible and reachable — that's the whole
      reason it's a bottom sheet rather than the plan face's popover.
- [ ] **Sticky footer vs the last row:** scrolled to the bottom of a long list,
      the footer isn't covering the final item or the Receipts block.
- [ ] **Undo toast:** it lasts long enough to actually hit, and tapping Undo puts
      the row back in its section (not at the end of the list).
- [ ] **Screen stays awake** across a few minutes of the run face (the wake lock
      is real-device-only).
- [ ] **Receipt in the dark themes** (Pesto Dark, Cherry Cola Dark): the amber
      Amend banner, the receipt card and the "Didn't buy" chips all read.
- [ ] **A receipt where nothing was priced:** the header total and the store card
      should be honest about it rather than showing a confident `$0.00`.
- [ ] **Finish a shop with something left unticked:** the receipt total and the
      store split must cover only what you bought, and the item you skipped shows
      under "Didn't buy". (Agent verified this against seeded data — worth one
      pass on a list you built yourself.)
- [ ] **Money off (Settings → install-wide):** the run face shows no prices and
      the footer shows no "Remaining"; the receipt shows counts, no dollars.

## Shopping list — plan face redesign (2026-08-23)
Agent drove the draft + mid-shop lists in a live browser and confirmed: trip
card, store card, all four ordering modes, Unsorted placement, offer chips
separate from the line price, ticked-rows-leave mid-shop, and store-card totals
reconciling with the trip card. These are the parts it could **not** reach.
- [ ] **Mobile (375px):** the store card and the budget/insight banner each
      collapse to one tappable line, and the first item is visible without
      scrolling. Desktop keeps both expanded. (The preview pane wouldn't resize.)
- [ ] **Toolbar at 375px and 1280px:** no horizontal scroll. (The page title is
      desktop-only as of 2026-08-28 — on mobile the picker button carries the
      name — so the old "doesn't wrap to Shopping / lists" check is 1280px only.)
- [ ] **Up/down reorder arrows** in Manual mode: press on the first/last row is
      disabled, a move persists across a reload, and it doesn't fight drag.
- [ ] **A list with no locations, groups or stores at all** (check in *shop* mode
      — the draft face now offers only Store + Manual): the unavailable ordering
      options are greyed out with a tooltip saying why, and Manual is selected.
- [ ] **Themes:** trip card, store card and the store colour dots read correctly
      in Pesto Dark and Cherry Cola Dark (the dots are identity colours — a brand
      colour, else a sealed hash swatch — not theme tokens).

## Offline is read-only (2026-08-23)
- [ ] **Kill the VPN mid-session:** the banner reads "Can't reach Dora — you can
      look around, but not make changes", and pages you'd already visited still
      render.
- [ ] **Try a change while it's down** (stock level, tick a list line): it fails,
      the optimistic change undoes itself, and you're told. Nothing says "queued".
- [ ] **Reconnect:** no phantom changes replay, and Retry restores normal use.
- [ ] **Sign out, sign in as another user:** no trace of the first user's pantry
      or lists, including on pages visited while signed in as them.

## Cook mode voice (2026-08-23) — origin FU-722
Needs a real phone + the VPN hop; can't be walked from a dev pane. Do these in
order — the engine reading is what makes the rest interpretable.
- [ ] **Sous Chef "?" popover → "Voice:" line** reads Piper or Browser fallback.
- [ ] **Sous Chef on, enter cook mode:** step 1 is announced without pressing
      Next.
- [ ] **Does the sentence start still get clipped?** Piper clips now start
      with 0.35 s of silence (2026-10-22). Note the engine if it still clips.
- [ ] **Barge-in still works:** say "next" while she's mid-sentence and it's
      heard (the mic-restart fix must not have muted listening).
- [ ] **Same clipping in Dora chat?** No continuous mic there, so clipping in
      chat too points at the engine rather than the mic.

## Settings: Image quality is its own page (2026-08-23)
- [ ] **Settings → Admin → Install → Image quality** loads, shows current
      quality + longest-edge, Save persists, and the toast fires.
- [ ] **Backup & restore** no longer shows an image card and its retention +
      storage-path Save still works.
- [ ] **On the server, after fixing `deploy-dora.sh`'s `--exclude='data'` →
      `--exclude='/data'` and redeploying:** the backups list loads and an
      Import upload succeeds (FU-717 — both were 404 because the deploy deleted
      `dora_api/features/data/`).

## Stock item detail: level-picker width (2026-08-23)
Couldn't be walked live — the SPA is behind a sign-in and the agent may not
authenticate. vue-tsc + eslint green.

- [ ] **Level row (mobile width especially):** the picker spans the full row like
      the Name/Location fields, level name left, caret right, "Updated …" caption
      underneath — not a narrow button sharing a row with the timestamp.

## Stock item detail feedback batch (2026-08-21)
Everything here is a desktop / running-app observation — the agent's pane can't
mount `#/stock/<id>` at all, and the peek is desktop-only (`$q.screen` reads 0
in the pane), so none of it could be walked live.

- [ ] **Peek header (desktop, a dark theme — Pesto Dark especially):** the item
      name / QR / Delete band no longer paints a coloured strip. It should read as
      the same background as everything around it, and still stay put when the
      panel scrolls.
- [ ] **Switch items in the peek:** click a second stock item in the list — the
      buy-verdict card must repaint for the new item (headline, reasons, action),
      not keep the first item's answer. Same for the QR dialog's image.
- [ ] **Buy verdict card:** one surface (no inner box), tinted by verdict, dollar
      sign on the left in all four states, "No strong buy signal" when unsure, and
      the action as an icon-only button *before* the chevron (swapped 2026-08-23 —
      the chevron is now the last control in the row, in the same spot whether or
      not the verdict carries an action). Compare side-by-side
      with "Dora thinks" above it — they should read as the same component family.
      Check a `wait` verdict too: the wait-hint block should show as a left-edge
      rule, not a nested tinted box.
- [ ] **Expiry row:** clicking the date (and clicking the "—" when there's no
      date) opens the picker; tab to it and press Enter/Space too.
- [ ] **Barcodes tab** (needs scanning on): the tab exists next to Substitutes with
      a count, the guidance paragraph reads sensibly, and adding a real EAN works.
      If it fails, quote the message verbatim — see FU-710.
- [ ] **QR button:** if it still errors, quote the message verbatim — it now names
      either "no QR endpoint at …" or "that stock item no longer exists" (FU-648).
- [ ] **Add substitute dialog:** no box icon before the names; the right-hand
      button is a green chain link.

## Stock overview: expiry menu, uncertainty ring, bulk endpoints (2026-08-22)
None of this could be driven live — port 5170 was held by another session's
backend running pre-change code. Backend suite (1936) and frontend (502) are green.

- [ ] **Expiry menu** (an item that has an expiry): the menu opens with the date
      at the top above a divider, in your locale's format. Tapping "Push expiry
      by 1 day" leaves the menu **open** and the header date moves; tap again and
      it moves again. "Clear expiry" and "Log waste" still close it.
- [ ] **Uncertainty ring**: the dashed marker is now a ring *outside* the level
      box with a 2px gap, and the level colour is an unbroken block. Check it
      isn't clipped by the row, top or bottom, and on a phone (≤599px) that it
      doesn't crowd the item name.
- [ ] **Legend + help copy** match: `StockRowLegend`'s uncertain swatch is also a
      ring-with-gap, and the attention-rules dialog heading reads "A dashed ring
      around the level".
- [ ] **Bulk bar, one round-trip each** — with devtools Network open, select
      ~10 items and run each of: Log waste (+ Undo), Add to list…, Add to your
      list, Mark restocked, Remove from list, Move. Each should fire **one**
      bulk POST plus one refresh, not N requests. Log waste in particular used
      to fire up to 3 per item.
- [ ] **Bulk waste Undo restores correctly**: items that had an expiry get the
      same date back; items that had none must not gain one.

## Price history: reported dark-mode tooltip — origin FU-708
Reported in the PRODUCT HISTORY feedback (PH7) and **not reproduced in a static
read**, so it needs eyes on the running thing.

- [ ] On a dark theme, open `/price-history`, pick a product and hover the chart:
      confirm the value bubble is theme-aware (not white text on white).

## Stock overview + Log a price feedback batch (2026-08-21)
Row treatments and the filter row were walked live and deleted from this list.
What's left needs a real browser (dialogs don't lay out in the agent's pane) or
a feature this seed has switched off.

- [ ] **Log a price** (needs Money on): pack count is visible without opening a
      disclosure; the three top fields span the same width as the two below;
      pack count and store are equal halves; the unit field shows "L" / "kg",
      not "volume — L"; the item's name appears once (dialog title only).
- [ ] **Add stock item**: the Location field's right edge lines up with Name /
      Stock level / Stock group, and doesn't overhang the dialog.
- [ ] The **Essential** info chip (add-item modal *and* the detail page) reads
      "Something you always want in the house. Dora chases it up as soon as it
      runs low, instead of waiting until it's gone." — same words in both.
- [ ] **Mobile**: a stock-level filter with a long value truncates with "…"
      instead of wrapping out of the box; Sort by shows a usable amount of the
      selected axis next to its direction button.

## Stock overview: "Needs check" chip retired (2026-08-21)
Chip absence + the dead `?stocktake=1` bookmark were walked live and deleted.

- [ ] Rows still show the dashed needs-check marker on the level box.
      (Virtualised rows don't paint in the agent pane — needs a real browser.)
- [ ] Dashboard → Dora Score → "Do a stocktake" lands on `/stocktake`.

## Stock overview: feedback batch (2026-08-20) — the seven items
Nothing here was walked live — the session ended before the browser pass.

- [ ] Filter panel opens on landing **only** when a filter is active — stock
      overview, cookbook and My products all behave the same now; navigate away
      and back with filters set (panel open) and with none set (panel closed).
- [ ] Clearing the last filter from inside the open panel does **not** slam the
      panel shut under you.
- [ ] Bulk select → "Deselect all" leaves bulk mode entirely (same as unticking
      the last item).
- [ ] Stocktake button shows the due count as a **chip**, not "(n due)" — at
      desktop and phone width; the glow still only fires on essentials.
- [ ] The toolbar's action row **scrolls sideways** on a phone instead of
      wrapping (turn on Scan + Money to get enough buttons to overflow).
- [ ] Stock level / location / group filters each carry a leading icon and the
      row still reads as one set.
- [ ] On a **real phone** (not a narrowed desktop — the behaviour is
      user-agent-gated), the Location filter opens as a mid-screen dialog like
      its neighbours, with no keyboard and no top-pinning, and the selected
      location is still visible in the field afterwards.
- [ ] Settings → System → Stocktake: switch Stocktake **off** → the overview
      button, the "Needs check" chip, the per-item Stocktake toggle on an item's
      detail page and the alerts-bell stocktake nudges all disappear **without a
      reload**; `/stocktake` by URL shows "Stocktake is turned off."; switch back
      on and everything returns.
- [ ] With Stocktake on, flip **New items** off, add an item, and confirm its
      detail page shows the Stocktake toggle **off** (and on again with the
      setting on).
- [ ] **Operator:** boot against an existing DB and confirm migration
      `a7d4e91c3f28` applies cleanly (adds `AppSetting.stocktake_enabled` +
      `stocktake_new_items_opt_in`, both defaulting true) — it has not been run
      against a real database yet, only exercised through the test schema.

## Micro-motion on the four repeated gestures (2026-08-20) — DR-15
Three of the four were walked live in the agent's pane and are **not** listed
here: the level-square settle, the cart-button bump, and the filter-chip
press+bump (plus the token/keyframe/reduced-motion plumbing). What's left needs
surfaces the pane can't render — its route transitions wedge, and the planner
rail is behind the forced-mobile `$q.screen` branch. All of it should read as a
*flicker you notice is there*, not something you watch happen — if you can
follow the movement, say so and the amplitude tokens come down.
- [ ] Tick a shopping-list line mid-shop: the checkbox presses in under your
      finger, and the line **fades** to its dimmed/struck state rather than
      snapping. Untick — it fades back up.
- [ ] Same press response on the stocktake **Review** phase checkboxes, ticking
      down a list quickly.
- [ ] The row cluster on a stock row (expiry, open/sealed, price, cart) all
      press identically — no odd one out.
- [ ] Turn on the OS "reduce motion" setting and re-tap all of the above:
      **nothing moves at all**, and nothing gets stuck part-way or leaves a
      control mid-scale.
- [ ] Dashboard stat count-ups now settle on `--motion-slow` (320ms, was a
      hardcoded 600ms) — confirm they don't now read as a snap.

## Planner recipe picker: one instance per recipe (2026-08-20) — DR-15 / FU-578 #47
Logic is pinned by 6 unit specs; this is the eyes-on pass. Needs a real desktop
browser — the rail doesn't render in the agent's pane.
- [ ] Open the **step-by-step** meal-plan builder with a cookbook that has
      favourites: a favourite appears under **Favourites** and **nowhere else**
      — no second checkbox for it further down.
- [ ] The bottom tray reads **"Everything else (N)"** when a shortcut tray took
      something, and **"All recipes (N)"** on a cookbook with no favourites and
      no cook history. The counts across all trays add up to your total.
- [ ] Search: typing collapses everything to one flat **Results (N)** tray that
      finds recipes regardless of which tray they'd otherwise sit in.
- [ ] Same behaviour in the **meal-planner page's left rail** (it shares the
      builder now — they used to be separate copies).

## Cookbook: filters, compact row, icons (2026-08-20) — feedback batch 3
Most of this batch was verified live in the agent's browser pane (filter order,
the removed "Missing ingredients ≤", "Serves ≥" narrowing 15 → 4, the 12px gap
above the list, the card's four re-pointed chip icons, the category vocabulary).
What's left needs a viewport the pane can't give (it reports 0×0, so Quasar
pins `$q.screen` to `xs` and the desktop branch never renders) or a pointer
(Quasar popups don't open there).
- [ ] **Desktop, compact view:** cook time + ingredient count render on a second
      line under the recipe name — not in the chip cluster — and line up down the
      list. Pinned by `recipeRowLayout.spec.ts`, but the *look* is the question.
- [ ] **Desktop, compact view:** recipe name reads at the same size/weight as a
      stock item name. Put the two lists side by side.
- [ ] **Phone, compact view:** still one line, no second line, nothing clipped.
- [ ] **Ingredients filter → Sort by → Stock level:** in-stock items come
      **first** now (it was out-of-stock first), untracked items last. There is
      still no direction toggle — that was the decision, not an omission.
- [ ] **Category filter** offers no time-of-day names (no Breakfast / Dessert /
      Snack) and does offer Curry / Bake / Bread. Confirm on a DB that was
      **migrated** rather than freshly seeded — the seed path is verified, the
      migration's effect on existing rows is not. A recipe that had been
      categorised "Dessert" should now show no category and keep its
      time-of-day.

## Stocktake: three phases — Review / Walk / Sweep (2026-08-20) — Chunk 6
The whole runner changed shape. Note the Review phase **won't appear** until Dora has
~3 logged purchases for something, so an early install legitimately shows only Walk.
- [ ] Run opens on the Review list when there's a confident item: name, believed level,
      Dora's reason, all pre-ticked.
- [ ] Confirm button counts what it will write; untick one and it says "1 will join the walk".
- [ ] Untick an item, confirm → **that item is the first thing in the walk**, not the last.
- [ ] The ticked ones are actually checked (their overdue clock resets — check the stock row).
- [ ] Walk behaves as before (Still correct / Change level / Skip / Push / Mute).
- [ ] After the walk, the tidy-up (Sweep) appears **only if** something dropped out of
      rotation since your last run — likely empty on the first run after this update, and
      that's correct, not a bug.
- [ ] Sweep row shows "Last activity <date>" so you can see what it's based on.
- [ ] **"I still keep this"** opens the level picker (not a silent check). Set a level →
      the row leaves the list, and the item is back in rotation next run.
- [ ] Mute and Delete both confirm first; Delete's dialog offers mute as the alternative.
- [ ] "Leave them be" → summary screen. Re-run the stocktake: the same items are **not**
      in the tidy-up again.
- [ ] Empty everything → the old "You're all caught up" card, unchanged.
- [ ] Help (?) describes the three parts, and the phase name shows in the top bar
      (no progress bar outside the walk).

## Stocktake: least-certain-first queue (2026-08-20) — Chunk 5
- [ ] Runner opens on an item Dora is unsure about, not the most-overdue one.
- [ ] That item shows **"Dora's not sure about this one — <reason>"** under the cadence line.
- [ ] Items she's confident about come **last** in the walk — and are still there, not dropped.
- [ ] Help dialog (?) says "least certain first", not "most-overdue first".
- [ ] Turn off Settings → Assistant → inferred pantry levels, reopen: order is plain
      most-overdue-first again, no belief line, and the help text reverts to the old wording.
- [ ] Order is stable — leave and re-enter the runner on unchanged data, same sequence.

## ⚠️ Recipe page (new layout): the parity pass (2026-08-20) — origin FU-688
The layout decision is made — the new page wins, and since 2026-08-26 it is the
only one (`/cookbook/:id` goes straight to it; the old page and both hatch
buttons are deleted). This is now about whether the gap-closing pass actually
works. Open any recipe.

_Confirmed live by the session that built it (2026-08-20): the page renders (FU-681 was
stale), **When** shows and holds `Dinner`, **Organise ingredients** is present, all 15
editable values are focusable with a name saying what they edit and **Enter opens the
editor**, and the row editor opens with Pantry item / Quantity / Unit / Required / Note
(Section hidden correctly on a section-less recipe). Poking the page saved nothing, which
is the explicit-save change working. Everything below needs real pointer input, which the
agent pane can't provide — it doesn't composite, so click coordinates are degenerate._

**Save, and not losing work** (this replaced a debounced autosave):
- [ ] Edit any value; an **Unsaved changes** pill appears and **Save** + **Discard** show up
      in the action row, with Cook mode stepping back from primary.
- [ ] Edit two values in a row without pausing — both survive. (The autosave used to drop
      the second one.)
- [ ] **Discard** asks, then puts every field back to the last saved state.
- [ ] Tap the back arrow while dirty → asked before leaving; **Stay** really stays.
- [ ] Reload/close the tab while dirty → the browser's own "leave site?" prompt fires.
- [ ] Start **Cook mode** while dirty → guard offers to save first, and cooking shows the
      saved version.
- [ ] Clear the recipe name and hit Save → refused with a reason, nothing lost.

**Ingredients** (no Organise disclosure; the row is the edit target):
- [ ] In the row editor (opened by tapping **anywhere on the row**), Cancel
      really cancels — no dirty pill afterwards.
- [ ] In that editor, type a name that doesn't exist → **Use "…"** is offered, then one
      question: add to pantry, or keep as free text. Both branches work; free text shows a
      **Free text** chip on the row. *(This is the one path the build session could not
      drive — the pane wouldn't render option menus. FU-736.)*
- [ ] Unit is a **dropdown** (same list as substitute ratios), and still accepts a typed
      word like "pinch". The optional switch reads the same in both positions.
- [ ] **Add ingredient** opens the editor straight away on the new row; a row left without
      an item shows a **Needs an item** chip and Save says so.
- [ ] A missing ingredient with recorded substitutes shows a chip: **"Use <name>"** when you
      have one, **"N substitutes"** when you don't. Open it — in-stock ones first, ratio and
      note shown, out-of-stock ones offer add-to-list, and the footer says swapping happens
      in cook mode.
**Sections & order** (rebuilt 2026-08-24 — sections are cards in the ingredient
list; the "Organise ingredients" panel is gone):
- [ ] Put an ingredient in a section via the row editor; move a section up/down from its
      **⋮** menu; delete a section and its ingredients fall back to the main list.
- [ ] Reorder ingredients with the row's ↑/↓ and Save — the order sticks after a reload.
- [ ] **Right now** cell adds "N has/have a substitute you already have" when that's true.

**Masthead editing & photo** (2026-08-24 merge — never seen in a browser):
- [ ] Header pencil → fields; every field in a row is the **same width**; a dropdown opens
      on **one** click. Pencil again (**Done**) saves and returns to reading.
- [ ] Nothing in the masthead edits by tapping the value itself any more — the pencil is
      the only way in, and **Total** / **Per serving** have no field (they're derived).
- [ ] Tapping an ingredient row anywhere — quantity included — opens the one row editor.
- [ ] With no photo, clicking the tile opens the file picker straight away. With one,
      it offers **Change photo** / **Remove photo** and no preview. A photo you set shows in
      the header after a reload.
- [ ] Nothing about the photo remains at the bottom of the page.
- [ ] Desktop width: a short title doesn't wrap with empty space beside it.
- [ ] **Right now**: "Add …to a list" is a button on the card's **right**, and it's absent
      once everything missing is already on a list.

**The rest:**
- [ ] All three step modes still render; only structured highlights the ingredients a step uses.
- [ ] Both hatch buttons still work ("New layout" / "Back to the old layout") until the swap.
- [ ] Phone width: the action row wraps sanely with Save + Discard present.

## Stock overview: default sort + the four row channels (2026-08-20) — Chunk 4
- [ ] Stock opens sorted **Needs attention · Most urgent first** (fresh session, no saved sort).
- [ ] Top of the list is outlined rows, then plain, then dimmed — no dimmed row above a plain one.
- [ ] A previously-saved sort (e.g. Name) still comes back as you left it.
- [ ] No row animates any more: no pulsing level box, no rings on the level box or cart.
- [ ] **Stocktake button glows when an essential is due, and only then.** Flag an overdue
      item essential → it glows; unflag → it stops, but keeps its count.
- [ ] Stocktake button shows the number due either way (badge when the label is dropped);
      tooltip/aria adds "N essential" when that's what's making it glow.
- [ ] An item due a count, and one Dora disagrees with, both show **one dashed level box**.
- [ ] Level picker header says which reason it is — "Dora thinks…" or "Due for a stocktake check".
- [ ] Expiry and open/in-use are still **two separate buttons** (the brief merge was reverted).
      Open is one tap, and marking something open still prompts for a revised date.
- [ ] An expired, out-of-stock, non-essential row is outlined and **not** faded (was both).
- [ ] Help → Guides → "What the colours and outlines mean": no cart-verdict rings, no amber
      warn tier, cheat sheet has one Row-treatment column, essential swatch matches the row.

## Alerts + Stock: Step-0 cuts and the one attention rule (2026-08-20)
- [ ] Settings → Notifications: one on/off toggle per kind, no Needs-action/FYI picker.
- [ ] Switch a kind off → its stock rows lose their outline too, and the footer count drops.
- [ ] Change the expiring-soon window in settings → row outlines move with the bell.
- [ ] One outline colour only; no amber-outline-around-amber-Low-square rows.
- [ ] Non-essential out-of-stock: dim, no outline, not counted.
- [ ] Settings → Notifications has no alerts-email-digest section.
- [ ] An overdue shopping day counts on the bell badge — confirm that's wanted (see worklog).

## Cookbook + Stock: sort-direction toggle inside the field (2026-08-20)
- [ ] Unfocused sort field: outline is unbroken across the top — no gap behind the arrow chip.
- [ ] Chip sits clear of the dropdown chevron, vertically centred, no stray edge or fill.
- [ ] Tapping anywhere on/just around the chip flips the direction (arrow and tooltip change).

## Stock overview: essential stripe back to a straight bar (2026-08-20)
- [ ] Essential row shows a plain full-height 6px bar, no taper, corners rounded by the row.
- [ ] On an essential row that's also low/out, the bar and the amber/red outline don't clash.
- [ ] Bar stays legible in each dark theme (D-020 `--brand-secondary-strong`).
- [ ] Legend swatch matches the real row.

## Recipe page: toolbar, cost card, image, meals (2026-08-19)
*Server half verified live against your seed: Juice Bowl now reports **no
estimate** with both lines reading "unit_mismatch · $4.20 per ea", Tuna Bake
prices at **$3.15** (2 tins × $1.20 + 250g × $0.003/g). The page itself never
left its loading skeleton in the agent pane — see FU-681 — so everything below
is unseen.*
- [ ] One toolbar only: back arrow, recipe name inline beside it, no breadcrumb,
      no second button row, no `⋮` menu. Long recipe name isn't chopped.
- [ ] At 375px the toolbar actions are icon-only with working tooltips, and the
      page has no horizontal scroll.
- [ ] Cook mode / Edit / Import / Favourite / New version / Print / Delete all
      still do what they say; Edit swaps to Save + Done.
- [ ] Estimated cost expands to a per-ingredient breakdown; a priced line shows
      "$x.xx" over "$y / unit", an unpriced one gives the reason.
- [ ] Print opens the recipe card in a new tab (this is the reported 404 — it
      needs the check from a phone / a non-localhost host, which is where the
      old code failed).
- [ ] Settings → Appearance → recipe photos **off**, then edit a recipe that has
      a photo: **Remove** is present and clears it.
- [ ] Batch cooking off ⇒ no "Available meals" card. On ⇒ card + stepper.
- [ ] Cooking a recipe through cook mode still updates "Last cooked" (it is now
      the only thing that does).

## Nav: menu link active colour (2026-08-19)
- [ ] Mobile drawer on a non-dashboard route (e.g. /stock): Dashboard row is
      plain text, not primary-tinted; only the current surface carries the
      accent background with on-accent text.
- [ ] Desktop menu strip: the active button's icon + label are accent, not
      primary.

## Cookbook: filter uniformity, cook guard, modals (2026-08-19)
*Measured live where the pane allowed it: filter-row controls are all real
`q-field`s at 180/200 × 44px with the same border colour and the same
`mdi-menu-down` caret at a 12px right inset; the open/focused ring and caret
rotation paint correctly (confirmed with transitions zeroed — the pane freezes
CSS transitions); the tri-state summary cycles "1 selected" → "1 in · 1 out" →
"Any" and its clear icon works; sort-direction button is 44×40 with a fill and a
left separator; import dialog is 327px inside a 375px viewport with no
horizontal page scroll. The recipe **list** and the recipe **detail page** don't
mount in the preview pane (documented `<Transition>` / detail-route artefacts),
so everything below needs your eyes.*

- [ ] **Cook mode from the cookbook** — tap the chef-hat on a recipe that's
      missing ingredients (seed: "Cheesy Garlic Bread") → the "Start cook mode?"
      confirm appears, same as it does from the recipe page. It lists the missing
      count. Cancel closes without navigating; "Start anyway" goes in. Then do
      the same on a cookable recipe → **no** confirm, straight into cook mode.
- [ ] **Cook mode from the recipe page still behaves** — with unsaved edits you
      get "Start without saving" + "Save & start"; from the cookbook you only
      ever get "Start anyway" (nothing there can be dirty).
- [ ] **Filter row reads as one set** — open Cookbook filters: cuisine,
      category, difficulty, ingredients, dietary tags and tools should all look
      like the *same kind of control* (same border brightness, same label
      colour). Tap-and-hold each one → they all brighten. The old complaint was
      that the Quasar ones looked dull/faded and the custom ones bright white.
- [ ] **Same on Stock overview** — its filter row now runs off the same shared
      component; confirm nothing shifted (level / sort / location / group still
      line up, location picker isn't wider than its siblings).
- [ ] **Sort direction button** reads as a tappable button, not a decorative
      arrow, and is comfortable to hit with a thumb on a phone.
- [ ] **Ingredient-count filter icon** (`mdi-counter`) no longer reads as
      "steps". Sanity-check it against the recipe-steps icon elsewhere.
- [ ] **Compact view** — one line per recipe, no second info line under the
      name. With "Uses expiring ingredients" on, the amber chip sits in the
      right-hand button cluster and lands in the **same spot on every row**
      (that was the "goes all over the place" complaint). Check on a phone width.
- [ ] **View-switch tooltip** no longer says "· remembered next visit".
- [ ] **Import modal on a real phone** — fits, nothing clipped, no sideways
      scroll. No paragraph of instructions at the top; the empty paste box prompts
      "Copy the entire recipe webpage text and paste here" and its label reads
      "Recipe text"; a bold "Source URL (optional)" heading above the URL input,
      no hint text under it. Importing still works end-to-end from a pasted page.
- [ ] **Import modal from the recipe page** — the overwrite warning
      ("Your existing recipe will be overwritten…") still shows there; it was
      kept when the rest of the explanatory copy was removed.
- [ ] **Add-ingredients-to-list modal** — no recipe name line, no "N of M
      selected" line. Each row shows a coloured stock-level dot between the
      checkbox and the name, with a tooltip naming the level; "Out / untracked"
      text is gone. Select all / Select missing sit bottom-**left**, in line with
      Cancel / Add, and look like buttons. Both still select the right rows
      (optional ingredients stay unchecked). Fits a phone.

## Evening brief actually lands (2026-08-17 later 10)

_(Needs VAPID keys + a real push subscription, neither of which the dev
instance has — the toggle is correctly disabled without them.)_

- [ ] **It arrives, once, at 7pm.** With VAPID configured and push subscribed,
      turn on Settings → Notifications → **Evening brief** on a day that has
      meals planned for tomorrow. One notification at 7pm household time,
      reading "Tomorrow — <slot>: <recipe>…". Not two, and not one per meal.
- [ ] **Tapping it opens the planner.**
- [ ] **Silence works.** On an evening with nothing planned for tomorrow *and*
      no shopping day due, nothing should arrive at all.
- [ ] **The gap nudge works.** Clear tomorrow but leave meals elsewhere in the
      week: the brief should say "Nothing planned for tomorrow yet."
- [ ] **Shop day rolls in.** Set a list's planned shop date to tomorrow — the
      brief should carry it alongside the meals.
- [ ] **Timezone.** Change the household timezone in Settings → Region and
      confirm the next brief follows the *new* 7pm, without a restart.

## Mobile resume: no more infinite splash (2026-08-17 later 9)

_(The failure mode is a suspended mobile webview holding a dead socket — the dev
pane and a desktop browser can't reproduce it. Needs the phone that saw it.)_

- [ ] **Resume after a long background.** Leave the app backgrounded on the phone
      for 10+ minutes (ideally moving between wifi and mobile data), then return.
      It should come back within a few seconds — and if it can't reach the
      server, the splash should show the **Retry** button rather than pulsing
      indefinitely. Previously this could hang until force-close.
- [ ] **Retry from that state actually recovers.** If you do get the Retry
      button, pressing it should either load the app or say it still can't
      reach the server — never go back to a silent pulse.
- [ ] **Airplane-mode start.** Cold-start with the network off: the splash should
      offer Retry within ~15 seconds, not sit there.

## Assistant chat window — mobile + touch behaviour (2026-08-17 later 8)

_(The two mobile ones can't be proved in the dev pane or on a desktop browser —
sticky `:hover` and mobile URL-bar viewport behaviour need a real handset.)_

- [ ] **Firefox on Android: the chat button doesn't move with the address bar.**
      Scroll down until the address bar hides, then back up. The mascot should
      stay a fixed distance off the bottom edge throughout. Compare against
      Chrome on the same device — they should now match.
- [ ] **Touch: closing the chat by tapping the mascot shrinks her.** On a phone,
      open the chat by tapping the mascot, then close it the same way. She
      should return to her small faded resting size immediately — not stay full
      size until you tap elsewhere. Then repeat closing via the panel's X and
      confirm the two look identical.
- [ ] **Touch: the mascot doesn't sit permanently full-size.** After the above,
      scroll the page — she should stay shrunk (no latched hover).

## Offline Retry + Docker env (2026-08-17 later 7; sync bullets retired 2026-10-23)

_(The two "sync actually lands" / "sync on re-open" bullets that opened this section were retired: offline is
**read-only** since 2026-08-23 (R-052) and the write queue they described no longer exists — see the
"Offline is read-only (2026-08-23)" section above for the current checks. The Retry and Docker bullets still stand.)_

- [ ] **Retry.** With the server stopped but the network up, press Retry —
      expect a spinner and then "Still can't reach the server". Start the
      server, press Retry again — the banner should clear immediately rather
      than waiting out the backoff.
- [ ] **Retry while the browser thinks it's offline** (DevTools Offline, server
      running is fine): Retry must still fire a request. This is the case that
      did nothing at all before.
- [ ] **Docker env.** Rebuild the container and confirm the encryption banner
      is gone with `DORA_SECRET_ENCRYPTION_KEY` set in `.env` — and spot-check
      one var that is *not* named in `compose.yml`'s list (e.g.
      `DORA_DEMO_MODE=true`) reaches the app, proving `env_file` is working.
      Needs Compose v2.24+ for `required: false`; `docker compose config`
      will tell you if your version chokes on it.

## Feedback batch: setup screen / essential tab / stocktake skip (2026-08-17 later 6)

_(All three are code-verified only — stock rows are virtualised and paint 0 in
the agent's pane, and the setup screen only exists on a zero-user install.)_

- [ ] **Essential marker**: on a stock row flagged Essential, the marker runs the
      full 16px along the row's top and bottom edges, tapers back to 5px through
      the middle, and its outer corners follow the row's 8px radius. Check it
      doesn't crowd the stock-level button at the row's top/bottom on a phone.
- [ ] **Stocktake skip**: with several items queued, tap Skip a few times — the
      `n / total` counter's **total must not grow**, and the run must reach the
      completion card. Reopen the queue: the skipped items are back.
- [ ] **First-admin screen** (fresh install / empty DB): the fine print under the
      form is gone, and the account is created with the **Email field left blank**
      — no validation error, and Settings → Account afterwards shows no address.
      Then check a bad value (`nope`) is still rejected.

## Recipe page marks the expiring ingredients (2026-08-17)

_(Server half is pinned by `tests/e2e/dora_api/test_recipe_expiring_ingredients.py`
(5 tests, incl. filter↔chip agreement). The Vue render was never driven — the agent
can't sign in. Your dev DB already has both cases: **Veggie Stir Fry → Broccoli**
expires in 1 day, **Vanilla Ice Cream Bowl → Vanilla Ice Cream** expired 3 days ago.)_

- [ ] Open Veggie Stir Fry: Broccoli carries an amber **Use soon** chip; hovering it
      shows the expiry date in your locale format, not raw ISO.
- [ ] Open Vanilla Ice Cream Bowl: Vanilla Ice Cream carries a red **Expired** chip.
- [ ] Ingredients that aren't at risk carry no chip at all, and an item that's both
      out of stock and expiring shows **Missing** *and* the at-risk chip.
- [ ] Filter the cookbook to "uses expiring ingredients", open each result, and
      confirm every one has at least one chip — that agreement is the whole point.
- [ ] Both themes: the amber chip clears the contrast floor against white chip text
      (D-002) — it's the one that worries me, `warning` + `text-color="white"`.

## Cookbook shows every recipe, not the first 50 (2026-08-17)

_(Owner-reported: recipes on the meal planner were unfindable in the cookbook
with zero filters on. Cause was the store taking one 50-row page and filtering
client-side; the dev DB has 68 recipes. Paging loop is pinned by
`web_app/test/unit/recipeApiPaging.spec.ts`, but the fix itself was never
driven in a browser.)_

- [ ] Egg Fried Rice, Spaghetti Aglio e Olio and Tomato Pasta all appear in the
      cookbook with no filters on, and all three are findable by search.
- [ ] The **Planned** filter lists every recipe that's actually on the planner.
- [ ] The counts in the sticky footer read 68 (or whatever `select count(*) from
      Recipe` says), not 50.
- [ ] Starting a shopping list **from recipes** offers the whole cookbook in the
      picker, and the "uses expiring ingredients" filter isn't capped either.

## Cookbook: toolbar / filters / compact view (2026-08-17)

_(Agent-verified live at 375px: toolbar wraps to two rows with the search box
full-width and no horizontal scroll; both filter rows stay one line each and
scroll sideways; the compact toggle swaps 15 cards for 15 rows and writes the
preference. What's left is the **desktop** shape — `$q.screen` reports width 0
in the agent's pane, so every `lt.sm` branch renders in its mobile form there
and the desktop one was never seen.)_

- [ ] On a **desktop** window, the cookbook toolbar shows labelled buttons in
      order — New recipe · Import · Hide/Show photos · Compact/Cards — with
      Filters + search pushed right on the same row. Import should read as an
      outlined button like Stock's, not a white one.
- [ ] In **compact** view on desktop, each row shows the time / ingredient-count
      / kcal chips (they're deliberately hidden on phones); names truncate with
      an ellipsis rather than pushing the three action buttons off the row.
- [ ] Compact view survives a **full reload** and a re-visit; switching back to
      Cards sticks too.
- [ ] The cookbook grid renders recipes on a **cold first load** (not just after
      navigating away and back) — this is the outstanding half of **FU-638**.

## Admin settings rework: nav / users / region (2026-08-17)

_(Agent-verified live at 1280px and 375px, so most of this batch is already
deleted. Confirmed: the admin sidebar renders as 5 flat groups with **zero**
sub-headers and the mobile strip shows the same 5 tabs; the Users page has no
Refresh and no Deals-email switch, both self-row toggles are disabled, a user
created with a typed password gets a toast and **no** password readout while
"Generate one instead" shows the 12-char readout once, deactivation confirms →
badges → dims → toasts; at 375px the Users row stacks with no horizontal
overflow; Region renders preview-first and "Match this device" saved timezone +
locale live. The two below are what the pane genuinely could not exercise.)_

- [ ] **Region — pick from the dropdowns.** The options popup never opens in the
      agent's browser pane (it can't focus the combobox), so **choosing** a
      currency or language from the list is unverified — only free-text and the
      "Match this device" button were exercised. Open Settings → Admin →
      Install → Region & locale, pick **USD — US dollar** from Currency: the
      preview should flip to `$12.50` immediately and the choice should stick
      across a refresh. Same for Language & format.
- [ ] **Region — a code that isn't on the shortlist.** Type a currency the list
      doesn't carry (e.g. `THB`) and press **Enter**; then repeat, typing it and
      clicking away instead (blur). Both should save — the page commits on
      either, deliberately, because Quasar's own Enter handling only runs with
      the popup open. A half-typed `TH` abandoned on blur should be silently
      dropped, not error.
- [ ] **A deactivated user is actually locked out end-to-end.** Backend-pinned
      in `test_user_router.py` (login refused, reason named, reactivate lets
      them back in) — worth one hands-on pass anyway: sign in as a second user
      in another browser, deactivate them from your admin session, and confirm
      that browser gets bounced to the login screen rather than carrying on.

## Inference on recipes / lists / meal planner (2026-08-17) — origin FU-653

_(Server side agent-verified live, with the toggles off then on: recipe hints
fire in both directions while `cookable`/`missing_count` stay put, the meal-plan
entry carries the flag, the draft list returns one suggestion. What's left is
the **client render** — the Browser pane can't paint the cookbook grid, recipe
detail or shopping-list detail, so nobody has seen these three UIs.)_

Turn all three on first: **Settings → Assistant → Zero-Input Pantry**. The dev
seed now ships two purpose-built recipes:

- [ ] **Cookbook card** — "Belief demo: Tuna Bake" shows an outline amber
      **"May be short"** chip; "Belief demo: Juice Bowl" shows a green
      **"May be cookable"**. Hover each for the reason + item name. Confirm the
      cook button's colour and the cookable badge are **unchanged**.
- [ ] **Recipe detail** — open the Tuna Bake: the belief card sits *under* the
      cookability card, amber-edged, and the cookability card still says
      "Cookable now".
- [ ] **Shopping list** — open the draft "This week": the *"Dora thinks you may
      be out of…"* strip sits above the items with a "Belief: Tuna Tins" chip.
      Tap it → it becomes a normal line. Reopen the list; tap the **×** →
      the strip goes for the session and comes back next visit.
- [ ] **Meal planner** — tap any day's slot, then pick "Belief demo: Tuna Bake"
      from the rail (it's deliberately not pre-planned — a seventh seeded entry
      broke two e2e tests' ingredient-demand assertions). Its entry chip should
      carry the hunch glyph, and the week's "need to buy" figures should be
      unchanged. (Was "drop onto any day" — drag-and-drop was retired 2026-08-30,
      D1.)
- [ ] **Off means silent** — switch the three off again and confirm all four
      surfaces go quiet.

## Settings — Assistant / About / nav feedback batch (2026-08-17)

_(Agent-verified live at 375px and 1280px: provider cards minimise + open one
at a time and sit at exactly 44px; group-heading taps navigate to the group's
first page; Account/About no longer draw a redundant single chip; the three
password fields sit at uniform 28px gaps; About renders 2×2 stat tiles with no
horizontal scroll. What's left needs a real environment or your eye.)_

- [ ] **The encryption fix, in your container.** Put `DORA_SECRET_ENCRYPTION_KEY`
      in the server `.env`, `docker compose up -d`, then Settings → Assistant →
      Providers: the "Secret encryption isn't set up" banner should be gone, and
      saving a paid provider's API key should now succeed.
- [ ] **Provider card states with real config** — connect Ollama (green), then
      break its base URL (red) and confirm the minimised card reads correctly
      without opening it.
- [ ] **About on a real phone** — the mascot/hero, the stat tiles and the big
      Install button. (In-pane the install button only ever shows the
      "not available in this browser" line.)
- [ ] **Install as an app** actually installs from the new button (Chrome
      Android / Edge desktop), and the row switches to "Dora is installed".

## Settings — store logo tile (2026-08-17)

Everything else in the Kitchen-setup feedback batch was agent-verified live
(list styling, descriptions, Add/Edit store round-trip incl. logo upload +
removal, seeded unlinked ingredients). These two need hover/touch, which the
headless pane can't drive:

- [ ] Hover (and tab to) the store-logo tile in Add/Edit store — the pencil
      overlay should fade in, same as the profile picture on Account.
- [ ] On a phone, tapping the store-logo tile should offer camera + gallery.

## Stock overview: filter feedback (2026-08-16)
_(All four items were agent-verified live on a scratch install and measured — icon-only Clear/Filters at 375px, the input-filter row on one 42px scrolling line with four equal 180px controls, the essential stripe's gap 7px→12px, and the secondary indicator tone 2.80:1→8.48:1 in pesto-dark (all five dark themes now 7.31–8.48:1, was 1.45–4.74:1). Evidence in `DORA_VERIFY_TRIAGE.md`. What's left is a look-and-feel call only you can make.)_
- [ ] **The lifted "Essential/Open" tone in the other four dark themes** — pesto-dark was the one walked live. Cherry Cola Dark is the one to eyeball: its secondary is a near-black red, so the lifted version was pushed toward clay (hue 20) to stay clear of the alert red. Check the stripe/chip doesn't read as an alert.

## Stock-item detail: feedback batch (2026-08-17)
_(The QR server half is now pinned by 7 new e2e tests and was driven live cross-origin from the browser — both endpoints answered 200 and the real composable returned a blob. The "Print one" pop-up bug was root-caused and fixed (R-046). The copy/control removals are template-only. Tests green: 1749 backend + 4 new nutrient-table e2e, 434 vitest, vue-tsc + eslint clean. What's below needs your eyes or your install.)_
- [ ] ⚠️ **QR dialog on YOUR install** — the "couldn't load…" failure has never reproduced here (three attempts now). It is now instrumented: if it still fails, the message names the **HTTP status and a `Ref:` prefix**. Quote it verbatim and FU-648 closes in one pass.
- [ ] ⚠️ **"Print one" — on the phone, by tap.** This is where it was blocked; a desktop click never showed it. Expect a new tab that briefly says "Preparing labels…" then shows the sheet. If the browser blocks the tab you should now get "allow pop-ups for Dora", not a generic error.
- [ ] **Nutrition — the new "Vitamins & minerals (N)" disclosure.** Link a food, open **Details**, and confirm the block appears with potassium/calcium/iron/vitamin C etc., collapsed by default. **Needs a re-imported dataset** — see FU-645; on a pre-today catalogue the block is simply absent (no empty section), which is itself the thing to confirm.
- [ ] **Nutrition panel wording + order.** The table should now read Energy · Protein · **Fat, total** → indented *Saturated* · **Carbohydrate** → indented *Sugars* · Dietary fibre · Sodium — i.e. fat before carbs, indentation instead of "— of which". Check the indent is legible at 375px.
- [ ] **Stock-take row** — the running "Dora can ask you to check this / Muted" caption is gone; confirm the toggle alone still reads unambiguously, and the (?) is now one sentence.
- [ ] **Expiry row** — the "Set" word is gone from the button. Confirm the glyph-only button is still obviously tappable next to the date and the +1d/+7d/+14d cluster, and that its tooltip still describes the expiry state.
- [ ] **Nutrition "Track again" is gone** — on an item marked "Not a food", confirm the search icon is the only control, and that linking a food from it clears the ignored state (should show the linked food, not "Ignored").
- [ ] **Buy verdict footer** — "across N shopping trips" is gone. Confirm the remaining "Based on N price samples … (last 12 months)" still reads as a complete sentence, including when there are waste events.

## Stock-item detail: feedback batch (2026-08-16)
_(The Location-overflow fix was agent-verified live at 375px + 320px and its line deleted — evidence in `DORA_VERIFY_TRIAGE.md`. The rest below needs your eyes: it needs a re-imported dataset, a real device, or your own install. Tests green: 1772 backend, 434 vitest, vue-tsc + eslint clean.)_
- [ ] **QR labels elsewhere** — Settings → Kitchen setup → QR labels ("Print all" and a selection), and the stock list's bulk QR action. Both share the same composable, so they inherit the 2026-08-17 pop-up fix and now toast on failure instead of failing silently. (The detail page's own QR checks have moved to the 2026-08-17 section above.)
- [ ] **Nutrition search** — type "greek yoghurt" into the food picker and confirm the space survives.
- [ ] **Stock-take toggle** — mute an item from stock-take mode, then un-mute it from the item's detail page and confirm it rejoins the queue.
- [ ] **Nutrition Details table** — needs a **re-imported** dataset to show anything beyond the old four; check sodium reads as a sane mg figure (an OFF-sourced food is the one that goes through a unit conversion).
- [ ] **"No food data installed" messaging** — on an install with no dataset downloaded, confirm Settings → Kitchen setup → **Nutrition matching** leads with the banner (+ "Set up food data" for an admin) rather than "nothing to match", and that Admin → System → Nutrition shows the "manual search works, suggestions don't" line when Open Food Facts is on but no dataset is installed. Then download a dataset and confirm suggestions appear on both that page and a stock item.
- [ ] **The two collapsed cards** — "Dora thinks" (including on an item where she *agrees*, which never rendered before) and the buy verdict; check both expand, and that the verdict's icon reads as money/cart rather than a stock level.

## Nutrition matching against a real USDA dataset (2026-08-15)
_(The surface itself was agent-verified live end to end on a scratch install — suggestion panel, accept, accept-all touching only the confident band, "Not a food" + undo, the complex-mode nav gate, and the five non-food items correctly matching nothing. What's below needs the real catalogue, which the agent's scratch install didn't have.)_
- [ ] With the **real USDA import** loaded (~7,800 foods, not the agent's 20-row stand-in), open **Settings → Kitchen setup → Nutrition matching** and judge the **match quality on your own pantry** — the scoring floors are calibrated against a hand-built set, so this is the first honest read on how often it's right, too eager, or too shy.
- [ ] Same page, same dataset: confirm it **loads in reasonable time**. It reads the catalogue once per load and scores in memory; fine at 20 rows and expected to be fine at 7,800, but unmeasured.

## Stock overview: mobile rework + row consolidation (2026-08-15)
_(Most of this was agent-verified live at 375px and 1280px — toolbar collapse, second-row search, no mobile autofocus, quick-filter row + sideways scroll, no (?) icons, legend moved to Help, location/price hidden on mobile, cluster 43%→30% of row width, uniform 64/76px rows, "Needs check" now counting + clearing, bulk auto-exit, both belief and verdict rings with their tooltips, level-menu row highlight, both camera-error branches. What's left below is what the agent's pane genuinely can't reach.)_
- [ ] **Scroll a pantry of 50+ items on a real device** and confirm the jumpiness is gone. The virtualised branch only kicks in above 50 items and it renders nothing in the agent's browser (that pane is `document.hidden`, so `requestAnimationFrame` never fires and Quasar's slice never settles — a harness artifact, reproduced on unmodified code too). This is the one fix that can't be confirmed without eyes.
- [ ] Same list, **on a phone** — rows should be uniform and the two-line names should still fit their 76px row.
- [ ] The **stocktake pulse**: strong enough to notice out of the corner of your eye, not so strong it's irritating to sit next to. Purely a taste call.
- [ ] The **buy-verdict ring** on the cart button in a **light theme** (agent checked dark only) — the ring's inner "gap" paints `--surface-component`, so confirm it reads as a gap and not a white halo.
- [ ] Same for the **amber "Dora thinks" ring** on the level picker in a light theme.
- [ ] **On your phone, in the Android app:** turn scanning on and confirm the camera **does** open (the app's origin is secure, so it should scan against your plain-http instance). This is the claim the new messages make — worth proving once before they keep telling people it's true.
- [ ] Same phone, in a **browser** at your LAN http address: the scanner should open to the "camera needs a secure connection" panel with a working type-a-barcode box, and Settings → Admin → System should carry the matching warning under the Scanning toggle. *(Both branches were agent-verified by stubbing, but never against a genuinely insecure origin.)*

## Nutrition: download + link, re-test in YOUR container (2026-08-15) — origin FU-639
_(Four bugs fixed after the owner's report. Verified on a local instance against the real USDA release — 7,793 foods + 14,449 portions imported, searched, and linked. **Not verified in the production container**, which is where you hit it: that instance wasn't reachable from the agent sandbox. Rebuild the image first — the fixes are server-side.)_
- [ ] **Settings → Admin → System → Nutrition → complex → Download** on **USDA SR Legacy**: moves Downloading → Reading → Saving → "Installed and searchable" with a food count in the thousands (expect ~7,793).
- [ ] Search a stock item's **Find a food** for "banana": local USDA results appear with a source badge, **no** "couldn't reach" warning.
- [ ] Pick one → the stock item shows the food, and it survives a reload.
- [ ] Foundation dataset downloads too (~3.8MB, fewer foods).
- [ ] If a live source is briefly busy, the warning now names it properly ("Open Food Facts", not "off") and suggests the offline database.

## Nutrition: recipe rollup card (2026-08-14) — origin FU-635
_(Math + payload verified: 16 unit + 4 e2e, plus a live check on a real recipe (469 kcal/serving from 2 of 3 ingredients, third reported unconvertible). **The card's render is unseen** — `#/cookbook/<id>` won't mount in the agent's pane, same limitation as the picker. Needs a linked recipe: complex mode + a dataset + 2-3 ingredients linked to foods.)_
- [ ] Recipe detail in **complex** mode shows a **Nutrition (per serving)** card: kcal, then protein/carbs/fat, then a **"From N of M ingredients"** line, then a bullet per gap ("2 stock items not linked to a food").
- [ ] The typed **"kcal per serving"** field is gone from the edit form, and the header kcal chip shows the rolled-up number.
- [ ] A recipe with **no servings** reads **"Nutrition (whole recipe)"** and suggests adding servings.
- [ ] A recipe with nothing linked shows "Nothing to add up yet" with the coverage line, not an empty card or a zero.
- [ ] Switch back to **simple**: the card is gone, the typed kcal field and its card are back.
- [ ] **Cookbook cards** show a kcal/serving chip; a part-covered recipe's chip is outlined and reads "(part)" with a tooltip.
- [ ] **"Kcal ≤" filter** narrows the list in complex mode, and a "(part)" recipe is *not* filtered out by it. "Kcal" sort ranks solid figures first, part-covered ones last.
- [ ] **Meal planner:** each day header shows "N kcal"; a day where some meals have no figure reads "N kcal (1/2)". *(Agent-verified live in simple mode — day totals, the partial case, and silence when nutrition is off all render correctly; worth a second look in complex mode.)*
- [ ] **Lighter swaps:** a planned meal's menu shows **Find a lighter option…** (and *doesn't* on a meal with no solid figure). The dialog lists lighter recipes with a "−N kcal" and a reason; picking one swaps it into the plan and the toast confirms. *(Agent-verified via the API — from a 900 kcal meal it returned 3 ranked candidates with correct chips, and correctly skipped recipes already on the week. **The menu item and dialog have never been rendered**: Quasar menus can't be driven in the agent's pane, so this is the eyes-on half.)*
- [ ] **FU-638 check while you're here:** do recipe cards render on `#/cookbook` at all? They didn't in the agent's browser pane (empty state + footer counting 11), and it couldn't be attributed — see the follow-up.

## Nutrition: stock-item food picker (2026-08-14) — origin FU-635
_(API layer verified: 15 e2e incl. link / unlink / null-default / unrelated-patch round-trips, plus live lookup against the real OFF API. **The picker's visual render could not be verified** — `#/stock/<id>` won't mount in the agent's browser pane at all (dashboard + Settings routes do); that's a pane limitation, not a code fault. These are eyes-on checks.)_
- [ ] With nutrition on **complex**, a stock item's detail shows a **Nutrition** row reading "Not linked" with a **Find a food** button. On **simple** or **off**, the row is absent entirely (not greyed out).
- [ ] **Find a food** → type "banana": results appear, each with a **source badge** on the right (e.g. "Open Food Facts", "USDA SR Legacy") and a kcal/100g line. Nothing is selected until you click a row.
- [ ] Type a **barcode** (e.g. `3017620422003`): the icon flips to a QR glyph, a "Looking that up as a barcode" hint shows, and the match is labelled **barcode match**.
- [ ] Pick a result → dialog closes, the row shows the food name + "N kcal / 100g · <source>", and it survives a page reload.
- [ ] **Change** reopens the picker; the **×** unlinks and the row returns to "Not linked".
- [ ] With every source switched off in System → Nutrition, searching says nothing found *and* mentions that no food source is set up.

## Nutrition install-wide + dataset download (2026-08-14) — origin FU-635
_(Verified live and deleted: the admin page renders and saves the mode; the mode reaches `/api/health` as `nutrition_mode`; dataset rows render with Download buttons; `complex` with no source shows the "nothing can answer a lookup yet" note; `GET /api/nutrition/sources` returns both datasets with correct default URLs. Not walked: an actual download — it pulls ~4-7MB from USDA and takes a while.)_
- [ ] **Dataset download:** Admin → System → Nutrition → complex → Download on **USDA SR Legacy**. *(This path had a fatal `create_app` import bug fixed on 2026-08-14 — it has still never been run end-to-end, so this check is the real proof.)* It should move through Downloading → Reading the data → Saving foods, then settle on "Installed and searchable" with a food count in the thousands. (SR Legacy first — its URL is frozen; Foundation's carries a release date and may 404, see FU-636.)
- [ ] **Import survives a restart:** after it finishes, restart the backend and confirm the count is still there (rows are durable; only the progress phase is in-memory).
- [ ] **Bad URL:** trigger an import with a deliberately wrong URL via the API and confirm the page shows the "that release has probably been superseded" message rather than a bare stack trace.
- [ ] **Old link:** `/settings/nutrition` redirects to the admin page rather than 404ing, and no Nutrition entry remains under the personal Preferences group.

## Voice picker: built-in vs neural (2026-08-14)
_(The selection guard is now Vitest-pinned in `voicePicker.spec.ts` — 8 cases incl. the exact regression. The grouping renders correctly on the dev box. These need a **downloaded** voice, which the dev box doesn't have.)_
- [ ] Download a neural voice → select it → pick **Device default voice** → click that same neural voice again: it **selects** (this was the bug). Repeat for a second downloaded voice.
- [ ] With a neural voice active, clicking that same card again does nothing (no redundant save toast).
- [ ] The "Built-in" card and the "Neural voices" grid read as two clearly different kinds of thing at a glance — including on a phone and in a dark theme.

## Settings nav regrouping (2026-08-14)
_(Verified live and deleted: desktop sidebar renders Account / PREFERENCES / KITCHEN SETUP / About with eyebrows only on the middle two; mobile shows 4 tabs, active tab tracks the route, no h-scroll at 375px.)_
- [ ] Nothing feels lost: every page you used to reach under the old "Account" heading is still one click away, and deep links / browser back still land on the right nav highlight.

## Stock locations settings redesign — zone cards (2026-08-14)
_(Verified live this session and deleted from this list: cards render per zone with areas as rows + sections as chips; expand/collapse persists across a full reload; search narrows to matching zones/areas/sections and auto-opens them; search text resets on reload (R-026); "0 areas · N items" copy fix; 375px = no horizontal scroll, chips + "+ Section" both 44px tall; dark-theme tokens all resolve, meta text 6.6:1 on the card. Remaining below are the round-trips the preview pane can't drive reliably.)_
- [ ] **Create:** "New zone" → names a zone; "+ Area" on a zone card → the new area appears **and its zone is open** (not hidden behind a chevron); "+ Section" on an area row → the chip appears in that row.
- [ ] **Rename:** the "…" menu → Rename opens a **dialog** pre-filled with the current name (not the old inline field). Clicking elsewhere mid-edit **cancels** — it must not silently save.
- [ ] **Delete:** the confirm still names what's lost ("N items … will become unassigned"), and after deleting the card/row/chip disappears without a stale count left behind.
- [ ] **Count click-through:** clicking an area's "N items" (or "View items" in a zone/section menu) lands on the stock list **filtered to that location**.
- [ ] **Light theme:** the zone card reads as a raised surface against the settings page background, and the section chips read as sunken *inside* it — not the reverse, and not three near-identical greys.

## Meal reconciliation: auto-mode log vs manual runner (2026-08-13)
_(Backend covered by e2e: `test_reconcile_verbs` auto-not-in-queue-but-in-log, `test_reconcile_signal` auto-suppression + manual-fire — all green. These are the running-app UI checks.)_
- [ ] **Auto mode** (Settings → Admin → System → Meal reconciliation, Auto-drain ON): open `/meal-plans/reconcile` → shows the **read-only log** (rows grouped by day, newest first, status pill per row: "Logged as cooked" etc.), **not** the confirm-each runner. Dashboard shows **no** "Reconcile N past meals" chip; no "reconcile overdue" alert.
- [ ] **Manual mode** (Auto-drain OFF): the same URL shows the **runner** (walk one at a time). With ≥3 past-day unconfirmed meals oldest ≥4 days back, the dashboard chip + overdue alert reappear.
- [ ] **Settings flip:** toggling Auto-drain on the settings page flips the surface **without a full reload** (the second section relabels "View meal log" ↔ "Go to reconcile").

## Settings shell: mobile header + scrollbar gap (2026-08-13)
- [ ] **Desktop:** on a Settings page long enough to scroll (e.g. Account, a long admin page), there's a **visible gap between the form content and the vertical scrollbar** — the bar no longer overlaps the content. Content width doesn't jump when moving between a short (no-scroll) and long (scroll) page.
- [ ] **Mobile (narrow ~320–400px, incl. as an admin):** the Settings top row **fits with no horizontal scroll** — the donate button is gone (still present in the app's main top bar), **Sign out is icon-only**, and the Settings/Admin toggle fits. Tapping the sign-out icon still signs out.

## Voice settings rework + mobile preview fix (2026-08-13) — origin FU-628
- [ ] **⚠️ Mobile preview (the reported bug):** on a **phone** (Android Chrome **and** Firefox), Settings → Voice → tap **Preview** on a downloaded neural voice → it **plays** (no error toast). This is the FU-628 fix; desktop already worked.
- [ ] **Device default card:** the voice grid shows a **"Device default voice"** card. Selecting it switches Dora to the browser voice (card shows the check); its **Preview** speaks via the browser voice. Selecting a **neural** card switches back (and moves the check to it).
- [ ] Mic + Spoken-replies sections are **heading + toggle only** ("Enable microphone voice input" / "Let Dora speak her replies"); the old "Voice engine" segmented control is gone.

## Notifications settings rework + version-prompt banner (2026-08-13)
- [ ] **Products OFF (no product data):** Settings → Notifications has **no "Weekly deals email" section**, and Settings → Admin → Users shows **no "Deals email" toggle** per user. Turn products ON (ingest product data) → both reappear.
- [ ] **SMTP not configured:** the deals-email + alerts-digest toggles are **disabled** and each shows a **warning card** (not a faint grey line). As a **non-admin** the card says "ask an admin…"; as an **admin** it shows a **"Set up email"** button that navigates to Settings → System → Email. Same for **Push** when VAPID isn't set (admin sees "Set up push" → System → Push).
- [ ] Alerts digest + Push sections show **only a heading + toggle** (no paragraph blurb, no repeated row label). Toggle still reachable/announced by a screen reader (aria-label present).
- [ ] **Version prompt false-positive gone:** in dev, navigating to Settings → Notifications does **not** pop a "new version available" prompt on a normal session. When a genuinely new build is deployed and the SW updates, the **dismissible banner** appears under the header with **Reload** + **✕**; Reload applies the update, ✕ hides it for the session.

## Shopping-list quick-add always asks (memory removed) (2026-08-13)
_(Appearance/Assistant page structure already agent-verified via read_page — those lines aren't listed here. This is the one runtime flow worth an eyes-on.)_
- [ ] With **two or more draft** shopping lists open, quick-add an item from Stock (the cart / "Add to list" action) → the **"Which list?" picker fires every time**, even on a second add of a different item (no silent reuse of the last pick).
- [ ] With exactly **one draft**, quick-add still drops the item straight in with **no** picker.
- [ ] **Bulk** add (select several stock items → "Add to list") with 2+ drafts: pick a list once for the first item → the **rest of the batch** lands in that same list.

## Zero-Input Pantry hint redesign — disagreement-only hint + demo data (2026-08-12)
_(Needs a destructive re-seed to load the "Belief: …" demo items — restart the backend with `DORA_ALLOW_DESTRUCTIVE=true`, e.g. the `dora-verify-backend-5171-linux` launch config (scratch DB, never the dev one).)_
- [ ] Stock Overview shows amber **"Dora thinks …"** hints ONLY on the disagreement items — expect: **Belief: Weet-Bix** → "Dora thinks low" (hover: high confidence); **Belief: Tuna Tins** → "Dora thinks out" (medium); **Belief: Greek Yoghurt** → "Dora thinks low" (medium); **Belief: Passata** → "Dora thinks low" (hover reason mentions "cooked with 2× since"); **Belief: Stir-fry Veg** → "Dora thinks out" (low conf, reason mentions cooking); **Belief: Orange Juice** → "Dora thinks stocked" (recorded Out, just restocked).
- [ ] **Belief: Crackers (agrees, silent)** shows **no** hint — the control proving agreement stays silent. The ~22 ordinary curated items (no purchase cadence) also show no hint.
- [ ] The hint icon reads as a **lightbulb-with-question** (a hunch), NOT a magic wand.
- [ ] Hint text is dark/legible on the soft-amber pill (not amber-on-amber); hover → reason + **"Confidence: …"** + the "Differs from your recorded level" note.
- [ ] Stock item detail (open one of the Belief items): the hint sits under the level picker; open a silent item (e.g. Crackers) and confirm **no** empty gap above the "Updated …" line.
- [ ] Help → Guides → Stock → **"The 'Dora thinks…' hint"** entry reads clearly and the arrow deep-links to `/stock`.
- [ ] Settings → **Assistant** → Zero-Input Pantry toggle still turns the whole hint off across overview + detail.

## Assistant settings redesign — Mode dropdown + multi-provider (2026-08-12)
- [ ] Settings → Assistant: title reads **"Assistant"** (no "(AI mode)"); intro mentions D.O.R.A. with a **"here"** link that opens the assistant help page (`/help/dora`).
- [ ] **Show digital assistant chat bubble** is a single row (label + toggle) — no heading/description above it. Toggling it hides/shows the corner bubble.
- [ ] **Providers**: all four blocks render (Ollama / OpenAI / Anthropic / Gemini), each with a status chip. Enter your Ollama base URL → chip goes **Checking… → Connected**, and the **Model field becomes a dropdown of installed models** (pinged from `/api/tags`). Enter a bad URL → chip shows **Couldn't connect** with a reason.
- [ ] Enter details for **two** providers (e.g. Ollama + one paid with a real key) → both can reach **Connected** independently; switching between them doesn't wipe the other's fields.
- [ ] **Mode** dropdown lists **Basic (built-in)** + only the **Connected** providers. Pick a provider → toast "AI mode on (…)", the Dora bubble's Basic/AI slider becomes enabled. Pick **Basic** → back to Basic.
- [ ] With no verified provider, the Dora chat's mode slider is disabled with the reason **"Connect a language model in Settings → Assistant first."**
- [ ] Paid provider: **Remove key** clears the saved key (placeholder returns to "Paste your key here") and drops the provider out of the Mode list.
- [ ] Edit a **Connected** provider's model → chip resets and re-checks; if the provider was the active Mode and verification now fails, AI mode can't stay selectable.

## Toast & helper-bubble placement (design-remediation DR-7, 2026-08-12) — origin FU-578
- [ ] Trigger a bottom-right toast (e.g. add a stock item to a list) — it appears in a column **above** the Dora mascot, not overlapping it. Fire a few in a row → they stack cleanly, clear of the launcher.
- [ ] Fresh account / cleared `dora.helpHintDismissed*`: the first-time "Hi! I'm Dora" tip appears, then **auto-dismisses after ~9s** without needing a click; it doesn't sit over stock rows / detail Level controls indefinitely.
- [ ] Open the Dora chat and send "hi" → greeting reads **"Hi, Dora!"** (name capitalised), never "Hi, dora!"; no "Burger online" line.
- [ ] Mobile viewport / device with a home indicator: the mascot launcher sits above the safe area (not tucked under the indicator or a rounded corner).
- [ ] *(Known carve-out, not a fail — FU-624)* a toast fired right before navigating can still linger onto the next page; the column placement above is what's under test here.

## Open-toggle can be cancelled (design-remediation DR-5, 2026-08-12) — origin FU-578
- [ ] On a **sealed** stock item, click the open toggle → the "Marking … as open" dialog shows **three** buttons: Cancel / Skip / Update expiry. Press **Escape** (or click the backdrop) → the item **stays sealed** (row glyph unchanged, no toast). Same via the **Cancel** button.
- [ ] Click open again → **Skip** → item flips to open, expiry unchanged. Toggle it sealed, open again → **Update expiry**, pick a new date → item opens *and* the effective expiry updates.
- [ ] Repeat the Escape/Cancel check on the **stock item detail page** open/in-use toggle: dismissing leaves the toggle in its prior position (it snaps back, no write).

## De-Quasar detail: dialog casing, open-toggle glyph, bulk-bar disabled (design-remediation DR-3, 2026-08-12) — origin FU-578
- [ ] Trigger a few confirm/prompt dialogs and check **no button is ALL-CAPS**: delete a store / stock location / recipe tag (Cancel + Delete), mark a stock item "open" (the "Skip" / "Update expiry" expiry prompt), the meal-planner "Clear this week", a bulk "Add to list…". Buttons read sentence-case ("Cancel", "Delete", "Skip", "Update expiry", "Got it").
- [ ] On a stock row, the **open / in-use toggle** shows a **box** glyph (sealed closed-box → open-box when toggled), not a padlock. Hovering still shows "Mark as open / in-use" ↔ "Mark as sealed".
- [ ] Enter **bulk-select** on Stock Overview with **nothing selected**: the action buttons ("Add to list…", "Remove from list…", "Move location", "Restock", "Log waste…") render clearly **greyed/disabled**, visibly different from the enabled "Select visible" — not the same white as enabled. Selecting an item un-greys them.
- [ ] Cook mode timer: the **Pause** button (while a timer runs) reads sentence-case "Pause" and matches the app's button styling (warning tone).

## Recipe detail read view + Edit toggle (design-remediation DR-11, 2026-08-13) — origin FU-578
- [ ] Open a recipe from the cookbook — it shows a **read view** (title heading, photo, chips, ingredients grouped by section, numbered instructions, source, notes), NOT an editable form. Tap **Edit** → the form appears (name input, ingredient rows, steps editor, etc.); **Save** persists, **Done** returns to the read view. "Mark cooked" / "Cook mode" / the meals stepper work in both.
- [ ] Read view is faithful: ingredient qty/unit/name/notes + optional & missing markers render; instructions show correctly for a structured-steps recipe, a freeform recipe, and an image-steps recipe. *(Code-verified: compiles, mounts without error, tsc/eslint green — but recipe data wouldn't load in the verify pane, so this needs a real eyes-on pass.)*
- [ ] Check a recipe with **named sections** (ingredients grouped under headings) and one with **nested sub-steps** (read view lists top-level steps; confirm that's acceptable — sub-steps still edit fine).
- [ ] The **"Available meals"** card reads "N unallocated of M **on hand**" (not "cooked"), and no longer looks like it contradicts "Last cooked: Never".

## Region date format everywhere (design-remediation DR-14, 2026-08-13) — origin FU-578
- [ ] Walk the app (shopping list, meal plans, alerts, dashboard, a recipe's "last made", a stock item's history, price chart, and the settings audit log / API keys / backups timestamps) — every date reads in the install's regional format (AU default = day/month/year, "17/07/2026"), never US month-first ("7/17/2026"). *(Confirmed in principle: all 26 sites route through the one household-locale formatter; tsc/eslint green; this is the eyes-on pass across surfaces.)*
- [ ] If you change the install's region (Settings → Admin → Region & locale), the dates update app-wide without needing a hard reload of individual pages.

## Toolbar overflow + mobile stock-row names (design-remediation DR-9, 2026-08-13) — origin FU-578
- [ ] **Stock list on a phone (≤600px):** a long item name (e.g. "Barilla Passata Tomato Sauce") wraps to **two lines** and is readable, rather than truncating to "Barilla Pa…". Desktop still shows the single-line ellipsis. *(Toolbar overflow at 375px + title collision at 1280px already code-verified live: 0px horizontal scroll, title uncollided.)*
- [ ] Spot-check a couple of other pages that use the shared page toolbar (e.g. a stock-item detail, a recipe) at phone width — no page scrolls sideways; the title keeps its own line and the actions wrap below it.

## Loading states: splash / dashboard skeletons / chip fade-in (design-remediation DR-8, 2026-08-13) — origin FU-578
- [ ] **Splash handoff:** cold-load the app in a **backgrounded tab** (open, switch away ~3s, switch back) and on a phone — the "Waking up Dora…" splash is gone once the app is ready, never frozen on top of the loaded page eating taps. *(The core wedge fix is code-verified live: the splash node is removed even in a non-compositing pane where the old build stuck.)*
- [ ] **Dashboard skeletons:** on a slow/first dashboard load, the cards show pulsing skeleton placeholders (not a lone spinner, no "Loading…" / "Loading totals…" text), then fade into real content. *(Skeleton render confirmed live; the "fade into real content" transition needs a painting browser + a loaded session.)*
- [ ] **Belief chip / verdict badge:** on the stock list, scroll so rows with a "Dora thinks low/out" pill or a Buy/Wait/Skip badge come into view — the pill/badge fades in and the row does **not** jump taller or shove its name/location line sideways as they arrive.

## Stock-level colours + row legend (design-remediation DR-2, 2026-08-13) — origin FU-578
- [ ] On Stock Overview, the level square on each row escalates correctly: **Stocked = green, Low = amber, Out of stock = red**, and an item with **no level set** is a grey dashed box (not a solid grey that could be mistaken for "out"). Check in **both** a light and a dark theme.
- [ ] Same colours flow through the other surfaces that show a level dot: the level **picker** dropdown (row + detail header), **cook mode** / recipe ingredient status, the **stocktake runner**, and the **footer counts** (Stocked green / Low amber / Out red).
- [ ] Open the Stock Overview **filter panel** → the **"What the row colours mean"** legend renders at the bottom: a *Stock level* group (your real level names + the dashed "Level not set") and a *Row highlights* group (essential left-stripe, amber "attention soon" outline, red "attention now" outline, dimmed "out, not essential" row, pulsing "due for stocktake" box). The swatches visually match the actual rows. *(Live DOM/computed-style probe already confirmed the colour values in one dark theme; this is the eyes-on pixel + light-theme pass.)*

## Low-contrast badge fixes (design-remediation DR-1b, 2026-08-12) — origin FU-578
- [ ] The **notifications bell count badge** (red circle with a number) is clearly legible in every theme, light and dark — the number reads as white on a deep red, not a washed-out light red.
- [ ] The **Buy / Wait / Skip verdict badge** (stock item row / detail) reads clearly in all themes: the label is dark on light themes / light on dark, sitting on the coloured tinted chip. "Wait" in particular is no longer faint amber-on-cream. The coloured border still signals buy(green)/wait(amber)/skip(red).

## Muted-text contrast retune (design-remediation DR-1, 2026-08-12) — origin FU-578
- [ ] In each of the 5 light themes (Pesto, Lemon Tart, Blueberry, Cherry Cola, Sourdough), the **muted/caption text** (footer stats, timestamps, chip captions, "Based on N samples" lines) is comfortably legible — no longer faint. It should still read as *quieter* than body text, not equal to it.
- [ ] In the dark themes, muted text is unchanged-to-slightly-clearer (Lemon Tart Dark + Blueberry Dark lifted a touch); nothing looks washed out or over-bright.
- [ ] Spot-check the dashboard, stock overview, and a shopping-list detail in a couple of themes (light + dark) — the muted ramp reads consistently. *(Ratio probe already confirmed ≥4.5:1 on every surface; this is an aesthetic sanity pass.)*

## Copy & wording sweep (design-remediation DR-4, 2026-08-12) — origin FU-578
- [ ] An item that expired reads **"… expired 3 days ago"** in the use-soon suggestion (dashboard/DoraBot) — NOT "expires expired". A single-day case reads "expired 1 day ago".
- [ ] Alert details pluralise: an item **out N days** shows "Expired N days ago" (or "1 day"), a low/overdue item "Overdue by N days" / "1 day" — no literal "day(s)".
- [ ] Dashboard greeting shows your name **capitalised** ("Good afternoon, Dora"), not the raw lowercase handle.
- [ ] The savings stat under the primary shopping list reads **"saved vs RRP"**.
- [ ] A recipe whose cuisine and category are the same word shows the meta chip **once** ("Dessert"), not "Dessert · Dessert".
- [ ] Image uploads (recipe hero, recipe step images, profile picture, store logo) show **"Take a photo"** and a natural add label ("Add image" / "Add images" / "Add logo") — no "Add (file)" / "Add (camera)".
- [ ] An **essential item that's out of stock** shows an action-neutral alert detail ("Out of stock and flagged as essential — worth restocking") that doesn't contradict the row's "Mark restocked" button.
- [ ] Settings → System → Cooking: the **Batch** cooking-style explainer reads in plain words (no "cook pool" / "shortfall" jargon).

## AI master switch removed + encryption-key banner + generator (2026-08-12)
- [ ] The **Admin → System** sidebar no longer lists **AI assistant**; visiting `/settings/admin/system/assistant` 404s (no redirect — pre-release). AI mode still works: turn it on for your account on Settings → Assistant with no install-wide gate blocking it.
- [ ] The Dora chat mode slider (Basic/AI) enables purely off your own provider config — no "disabled install-wide" reason ever appears.
- [ ] **Encryption banner (key set):** with `DORA_SECRET_ENCRYPTION_KEY` set, Settings → Assistant + Admin → System → Email + Admin → System → Push show **no** encryption warning banner.
- [ ] **Encryption banner (key unset):** boot with `DORA_SECRET_ENCRYPTION_KEY` unset → the warning banner appears on all three pages. Click **Generate a key** → a 44-char key shows; **Copy** copies it and toasts. Paste it into the env var, restart → banner gone, and saving an SMTP password / VAPID key / paid-provider API key now succeeds.

## Timezone + currency + locale merged onto one page (2026-08-12)
- [ ] Admin → System sidebar shows a single **Region & locale** entry (no separate **Timezone** / **Currency & locale** rows). The old `/settings/admin/system/timezone` and `/settings/admin/system/locale` URLs 404 (no redirect — pre-release).
- [ ] On the Region & locale page: the timezone select + **Use this device** save the household timezone; the currency + locale inputs validate and save, the money **Preview** reflects the saved currency/locale, and its **Use this device** fills the locale. Each saves independently with its own toast.

## Account settings redesign (2026-08-11)
- [ ] Settings → Account: page is just Profile picture / Username / Email / Change password + one **Save changes** bar at the bottom (no top identity block, no per-field save buttons). Structure was agent-confirmed via page text; the live interactive checks below were auth-blocked (session expired, no creds) — walk them once signed in.
- [ ] Profile picture is a **circle**; hovering (or keyboard-focusing) shows a pencil overlay; clicking/tapping it opens the file picker and the chosen image saves immediately. **Remove photo** appears only when an image is set and clears it.
- [ ] Edit Username and/or Email → the **Save changes** button enables (and a **Discard** appears); Save persists both (reload → values stick). Email needs no password/confirmation — it just saves. An invalid email shows an inline error and blocks save; clearing the field saves an empty address.
- [ ] Fill the three password fields (current + new ≥8 + matching confirm) → Save changes updates the password; leaving them blank saves username/email only. Navigating away with unsaved edits prompts the unsaved-changes guard.

## Blank-nav regression fix (2026-08-11)
*Root cause + fix landed and functionally verified via live JS-driven nav (all routes render on nav, console clean). Synthetic clicks/screenshots were flaky in the harness pane, so a real-click + visual pass is owed.*
- [ ] Click around the app between several pages (Dashboard ↔ Cookbook ↔ Stock ↔ Meal plans ↔ Settings) — every page renders on nav; no blank screens, no need to refresh. Confirm the page-to-page cross-fade looks fine (no jarring flash / double-page overlap).

## Stocktake fill-pulse + expiry menu width fixes (2026-08-10)
*Bug 1 (fill never rendered on the outline button) fixed by moving the fill to the `::before` layer — mechanism confirmed against real Quasar CSS (computed `::before` bg = live tint, animation running). Bug 2 is a menu width/nowrap tweak. Both are visual/animation → owner once-over.*
- [ ] Stock Overview, stocktake overdue: the **Stocktake** button's **fill colour** now breathes in sync with the glow ring (not just the ring) — the whole control pulses. Reduced-motion → static soft fill, no animation.
- [ ] Stock row expiry dropdown → **"Push expiry by 14 days"** sits on one line (no wrap); the menu is comfortably wide and all options read cleanly.

## Font picker names the default (2026-08-10)
*Label-only + option removal; vue-tsc clean; no test referenced it. No dev server here to eyeball.*
- [ ] Settings → Preferences → **Font family**: the first option reads **"Nunito (Default)"** (not "Default"), there's no separate "Nunito" option, and selecting it applies the default font. Check the longer label doesn't crowd/overflow the segmented control on a narrow screen.
- [ ] Onboarding wizard (fresh account or re-run) → the font step shows the same **"Nunito (Default)"** first option with no duplicate "Nunito".

## Recipe card ingredient count (2026-08-10)
*Trivial display chip (reads the already-loaded ingredient list); vue-tsc clean; mirrors the adjacent time/serves chips. No dev server on this machine to eyeball it.*
- [ ] Cookbook: recipe cards show an **"N ingredients"** chip next to the time/serves/difficulty chips; a recipe with 1 ingredient reads "1 ingredient"; a recipe with none shows no chip. Also present on a stock item detail → **Recipes using this** cards.

## Password-reset / verify-email link routing (2026-08-10)
*Root-caused + fixed (e-mailed deep links were path-based but the SPA is hash-routed, so they bounced to /login). Verified live: loading `http://localhost:5174/#/reset-password?token=…` lands on the "Choose a new password" screen with the token applied; unit + e2e auth tests green. Owner has SMTP live — worth one real click-through now that it's fixed.*
- [ ] Trigger a real password reset → click the emailed link → it opens the **"Choose a new password"** screen (not the login page), and submitting a new password actually changes it (log in with the new one).
- [ ] Verify-email + email-change confirmation links from a real inbox likewise open their confirmation screens, not the login page.

## Transactional email brand banner (2026-08-10)
*Code-complete; template + sender unit tests green (30), and the rendered email confirmed in-browser (banner img 520px, "Reset Password", new intro, footer). Owed: an eyes-on check in a real inbox once SMTP is live — CID inline images render in Gmail/Outlook/Apple Mail, but worth a glance.*
- [ ] Trigger a password reset with SMTP configured → the email opens with the brand banner (Dora mascot on the left, "Dashy Dora" in the Cute Dino font, on the yellow strip) rendered inline (not a broken-image box) in Gmail, Outlook, and Apple Mail.
- [ ] With remote images blocked, the header degrades to the "Dashy Dora" alt text rather than an empty gap.
- [ ] The other transactional emails (verify email, email-change confirmation/notice, password-changed, alerts digest) show the same banner header.

## Stock UI polish + Title-case page titles + essential rename (2026-08-08)
*Code-complete; backend 299 targeted tests + frontend typecheck & 40 affected unit tests green, and the `is_flagged`→`is_essential` migration applied on a real destructive boot (DB column confirmed renamed on all three dev DBs). Visual pass owed — the preview browser here dropped the auth session on every reload and screenshots timed out, so the running-app look wasn't confirmed by the session.*
- [ ] Mobile (narrow) view: the top menu-bar page name is Title Case on each page — "Stock Item", "Price History", "Meal Plans", "System: Alert Thresholds" — and the browser tab title matches.
- [ ] Stock Overview → any item's expiry dropdown: three "Push expiry by 1 day / 7 days / 14 days" rows each with a **+** icon, "Clear expiry" with an **✕**, "Log waste" with the bin — icons aligned in one column.
- [ ] Stock Overview toolbar: the **Export** button shows the export glyph (tray-with-out-arrow); its menu still offers **Export as CSV** + **Print / Save as PDF**.
- [ ] Stock Overview: with a stocktake overdue, the **Stocktake** button's glow ring pulses. *(The fill-with-glow part was broken and re-fixed 2026-08-10 — see that section below.)*
- [ ] Stock item detail → **Usual store** dropdown: each option shows the store's logo (or swatch) beside the name; the currently-selected store still reads fine.
- [ ] Stock item detail → **Expiry** row: set a date, then clear it → the +1d/+7d/+14d/Set buttons don't shift; only the ✕ appears/disappears at the left of the cluster.
- [ ] Stock item detail → **Recipes** tab: drag-resize the window → cards hold a steady width and add/remove a whole column, instead of continuously stretching/shrinking.
- [ ] **Essential still works after the rename**: mark an item Essential on its detail page → the Overview **Essentials** filter chip includes it, its left-edge stripe shows, and (with auto-add in "essential only" mode) it's the one that auto-adds when low.

## Build-my-week shortfall hint (FU-611, 2026-08-11)
*Data path verified live (auto-build API on the 11-recipe seed: 7 days × 3 meals = 21 requested, 8 placed, 4 days empty → hint condition true). The literal banner render is owed — builder-dialog elements report 0×0 in the preview pane.*
- [ ] Meal plans → **Build my week** → tick all remaining days + Breakfast/Lunch/Dinner (leave "Same meals every day" **off**) → **Build**. The Review step shows a subtle info note: "Dora planned N of the M meals you picked … some days are still empty. Add more recipes, choose fewer days or meals, or tick Same meals every day to reuse recipes." Add meals by hand until the count is met → the note disappears. Tick "Same meals every day" → the note never shows.

## Cookbook counts footer pins on a short list (FU-609 / R-036, 2026-08-11)
*Conversion verified live (Cookbook root is now `<q-page>`, renders clean, no console errors); the pixel-pin on a SHORT list couldn't be measured (preview pane reports innerHeight 0, and the seed cookbook is long).*
- [ ] Filter the Cookbook down to just a few recipes (so the content is shorter than the window) → the counts footer sits flush at the **bottom of the viewport**, not floating mid-screen. Then clear the filter (long list) → footer still behaves (pins while scrolling, rests at content end). No double scrollbar.

## Meal-plan dialogs keep fields live while saving (FU-610 / D-019, 2026-08-11)
*Removed the transient saving flag from the inputs in 4 dialogs; type/lint clean; behaviour eyeball owed.*
- [ ] Meal plans → save a week as a template (and Templates page → save a set): while the Save button spins, the name field / description / dropdowns stay focusable — you can keep typing or tab between them, focus isn't yanked out mid-save. Same for the inline template **rename** field and the **Apply recurring** date pickers.

## Cook batches — "Cook once for more days" dialog (FU-617 Phase 4, 2026-08-11)
*Verified live: the linked-cook markers ("Cook · serves 6" / "Leftovers"), the batch menu items, and "Separate this cook" (dissolves the batch) all work with Batch cook-style on. The one path not driven in-pane is the link-creation dialog itself — its write path is the same `setCookDays` proven by unlink + the backend cook_key tests, so this is a light eyeball.*
- [ ] Settings → System → Cooking = **Batch**. In the planner, on a meal's ⋮ menu tap **"Cook once for more days…"** → the day-picker lists this week's upcoming days with the meal's own day ticked → tick two more, confirm → those days now show the same cook (one "Cook · serves N" on the earliest, "Leftovers" on the rest). With cook-style **Fresh**, the menu shows no batch options at all.

## Page-height contract sweep — remaining MainLayout pages → <q-page> (FU-609, 2026-08-11)
*Converted the last 11 MainLayout pages to R-036 (`<q-page>`; app-shell `:style-fn` for runners + SettingsShell; `<component :is>` for the dual-host stock detail). Agent-verified Dashboard + Reports render as proper `<q-page>` with content; typecheck/lint/compile clean on all. The other 9 couldn't be driven in the agent browser (non-composited pane freezes the page FadeTransition) — walk these once in a real browser.*
- [ ] **Runner shells fill the viewport, no overshoot** — open **Stocktake** (`/stocktake`) and **Meal reconcile** (`/meal-plans/reconcile`): each fills exactly the area below the app header with **no extra scroll / no gap at the bottom** (they used to overshoot by the header height). Trigger the **OfflineBanner** (stop the backend) and confirm the shell still fits under banner+header without a double-scrollbar.
- [ ] **Settings shell** (`/settings/account`): desktop (≥1024px) — sidebar + main pane each scroll independently, window itself doesn't scroll, footer/last item reachable. Mobile (<1024px) — reverts to a single window-scrolled column (the sidebar becomes the top tab strip); no fixed-height clipping.
- [ ] **Doc-scroll pages render + scroll normally** — Dashboard, Meal Plans (sticky planner side-columns still pin while the page scrolls), Meal-Plan Templates, Price History, Cook Mode, Reports: each shows its content and window-scrolls as before; nothing clipped, no mid-screen floating footer.
- [ ] **Stock item detail — both hosts** — open `/stock/<id>` full-page (renders normally) **and** the Stock Overview peek panel (click a row's peek): the embedded panel still renders inside the splitter (it must NOT try to be a full page there). Both show the same detail content.

## Stale-DB boot guard logs a banner (FU-570, 2026-08-11)
*New `_warn_on_schema_drift()` in startup.py logs a loud ERROR banner when the live DB is missing tables/columns the models expect (names-only inspector compare). Health also gains `schema_version_db` (pinned by test). The boot banner is an operator smoke check.*
- [ ] Boot the backend against a **deliberately stale** SQLite DB — e.g. copy an old `dora.data.db` (or drop a column from a table by hand) into place and start `dora-backend` **without** `DORA_ALLOW_DESTRUCTIVE`. Confirm the stderr/log shows a single **"SCHEMA DRIFT DETECTED …"** ERROR line naming the missing tables/columns + the fix hint, and the app still boots (warn, not refuse). A fresh/normal DB boot shows **no** such banner.

## Feature toggles apply without a reload (FU-580, 2026-08-11)
*Wired the scanning + buy-verdict toggle handlers to re-probe their dedicated composables (`useScanningEnabled`/`useBuyVerdictEnabled`); the generic flags already refreshed. Type/lint clean; needs an admin session to walk.*
- [ ] As admin, Settings → System → Features. With a stock item visible on **Stock Overview** in another tab/route: toggle **"Should I buy?" oracle** off → the buy/wait/skip badges on stock rows + shopping-list lines disappear **without a page reload** (toggle back on → they return). Same for **Scanning & QR labels** → the Stock Overview scan button + QR-label affordances appear/disappear live.

## Bad instance URL is recoverable from the error screen (FU-574, 2026-08-11)
*Added a "Change instance URL" button to the SplashScreen error overlay, shown only when a runtime backend override is set. Router-independent (runs pre-bootstrap). Type/lint clean. Trigger is destructive (breaks the backend connection) so left as an owner walk.*
- [ ] Settings → About → **Change instance URL** → save a deliberately bogus URL (e.g. `https://nope.invalid`). App reloads into the **"Can't reach Dora's brain"** screen, which now shows **both** *Try again* and *Change instance URL*. Click **Change instance URL** → the prompt opens pre-filled → enter the correct URL → app reloads and recovers. (On a plain browser install with no custom URL saved, the button should **not** appear — retry only.)

## Upcoming-timeline dots gain a shape channel (FU-598, 2026-08-11)
*Added a shape per category (circle=expiry, square=shopping, diamond=meal) so the dots stay distinct even where two theme colours coincide (Pesto's primary=positive green). CSS-only; type/lint clean; eyeball only.*
- [ ] Dashboard → **Upcoming** grid: the legend and the per-day dots show three distinct shapes — **circle** (expiry), **square** (shopping), **diamond** (meal). On **Pesto** (default theme) a shopping-day dot and a meal-day dot are the same green but now clearly different shapes. Diamonds shouldn't look clipped inside the cell.

## Meal-plan card borders now render (FU-613, 2026-08-11)
*Fixed a phantom `--separator` token → `--border-default` across 4 meal-plan components; borders that previously drew as nothing now render. Type/lint clean; eyeball only.*
- [ ] Meal plans week view: the **entry chips** and **rich day cards** show a faint outline (plus their coloured left accent), and the dashed **"add a meal" / drop-target** outlines are visible on day cards and the mobile day-focus view. Check in a couple of themes (e.g. Pesto dark + a light theme) — the borders should be a subtle theme-appropriate line, not missing and not harsh.

## Meal-plan builder toggles + duplicate week (2026-08-07)
*Behaviour verified live (toggle state, select-all, repeat payload, both duplicate paths, no console errors). Layout could not be measured — every element inside the dialog reported 0×0 in the preview browser, including pre-existing controls — so the visual pass is owed.*
- [ ] Meal plans → **Build my week**: the day row shows Mon–Sun as card buttons with dates, past days greyed; the meal row shows your slots. Both are legible and tappable, and neither row overflows the dialog at 1280px or on a phone.
- [ ] Selected toggles read clearly as selected (green fill, white text) against unselected — and the greyed past days aren't mistakable for selected.
- [ ] Keyboard: tab into the day row, space toggles a card, the focus ring is visible on every card.
- [ ] Tick **Same meals every day**, pick 3 days × 2 meals, Build → review shows the same two recipes on all three days.
- [ ] Duplicate to next week from a week with meals, onto a week that already has some → confirm text says "replaces the N meals already planned there"; after confirming, next week matches the source exactly (no leftovers from what was there).
- [ ] **After restarting the API** (the dev backend has no auto-reloader): Build my week → on the Review step hit **Reshuffle** a few times with the default "Use up stock" emphasis and a cookbook bigger than the day×slot grid → the set of meals changes between shuffles (unit-tested; needs a backend restart to see live, since the fix is server-side).

## Money → household budget, value-driven (2026-08-12)
*Backend + FE green on typecheck/lint/unit (518 backend, 17 authStore, migration-from-empty); e2e updated but need a live server; the running-app walk wasn't driven (would need a destructive reseed of the dev DB, not run uninvited).*
- [ ] With money **on** (admin → System → Features), **Money** appears under **Settings → Kitchen setup** (not under Account); with money **off**, the Money entry is absent and opening `/settings/money` shows the "ask an admin" note.
- [ ] Money page: type an **Amount** → saves ("Grocery budget updated."), the **Period** picker appears; clear the amount (blank or 0) → saves ("Grocery budget turned off."), Period picker hides. **The reported bug:** set an amount, then change **Period** (Weekly ↔ Monthly) → the budget stays on (does *not* switch off).
- [ ] The budget is **shared**: set it as one member, sign in as another → the same amount/period shows on their Money page, and the **dashboard budget card** reflects it for both.
- [ ] Dashboard budget card + meal-planner "over budget" / swap-suggestions still compute correctly against the household budget (spend across all finished lists vs the one shared target).

## Settings input focus during save (2026-08-07)
*The disable-on-save mechanism is gone (lint/typecheck/412 Vitest green), but the session could not drive a real save through the preview browser — synthetic events never triggered the blur handler — so the end-to-end behaviour is unconfirmed.*
- [ ] Settings → AI assistant: type in **Base URL**, click straight into **Model** → caret lands and stays in Model while the save toast fires; keep typing without re-clicking.
- [ ] Same page, tab (not click) from Base URL → Model mid-save → focus ring survives.
- [ ] Admin → System → Email: edit SMTP host, tab through port and username in one pass → no field goes inert, all three saves land.
- [ ] Save/Test buttons still grey out while their request is in flight (double-submit protection kept deliberately).
- [ ] Trigger a save failure (stop the backend) → error toast fires and the field reverts, still focusable.

## Sign-out from Settings (2026-08-04)
- [ ] From Settings → Account (no edits made), click **Sign out** → app goes straight to `/login` with no "Discard unsaved changes?" prompt.
- [ ] From Settings → Account, edit the username draft (make it dirty) → click **Sign out** → still no prompt, sign-out completes to `/login` (intentional exit overrides the guard by design).
- [ ] From `/cookbook/:id` with an unrelated dirty edit, navigate to Settings and back — the usual "Discard unsaved changes?" prompt still fires on the router-link nav (the bypass only applies to sign-out, not general nav).

## Stock Overview app-shell rebuild (2026-08-04)
*Structural metrics already verified live (no page scroll, 2 scrollbars, panes equal height, footer at viewport bottom, detail header sticky). These are the eyeball checks the preview browser couldn't do — it renders 0 virtual rows.*
- [ ] Rows render with visible spacing between them on a **large** pantry (>50 items, virtualised path) **and** on a filtered/small list (<50, glide-in path) — the two should look identical.
- [ ] Counts footer sits flush with the bottom of the window with the detail pane **closed** (this was the main bug).
- [ ] Open a row's detail pane → no gap appears between the last row and the footer; both columns are the same height.
- [ ] Scroll the detail pane → its header (close · name · Delete) stays pinned; scroll the list → the toolbar and footer stay put and the page itself never scrolls.
- [ ] Exactly two scrollbars with the pane open (one per column), one with it closed.
- [ ] List scrollbar sits flush against the right edge of its pane (not floating inset over the rows), with a visible gap between the rows and the bar. Filter the list down so it stops scrolling → row widths **don't** shift.
- [ ] Resize the window narrow→wide and toggle the Filters panel open → the list re-fits, footer stays pinned, nothing clips.
- [ ] Mobile width (<md): page still usable, footer pinned, no double-scroll. Header uses `reveal` on mobile — confirm hiding/showing it doesn't leave a gap or clip the footer.
- [ ] Kill the API (stop the backend) so `OfflineBanner` shows → confirm the shell still fits and the footer stays reachable (banner adds 48px above the page; a small page scroll here is the known trade-off).

## Product Search config simplified (2026-08-07)
*Behaviour verified live this session (URL-unset → no nav entry; URL-set-via-API → external new-tab entry appears; Features page shows the Product search section and no Hide toggle; DTO drops `product_search_hidden`). Residual: the save through the actual Features input (I round-tripped the URL via the API, not the input's blur handler).*
- [ ] Settings → System → Features (products ON): type a URL in **Product search → Search URL**, blur → toast confirms; the main-menu **Product Search** entry appears and opens the URL in a new tab. Clear it and blur → the entry disappears again.

## Donation buttons + restored support links (FU-608) — origin FU-608
- [ ] **Menu bar (logged in):** the pink **Support Dora** heart shows in the header cluster (next to the alerts bell / help / avatar), gently pulses, and reads well against the toolbar colour on each theme; clicking opens the popover with all 3 platforms. *(Auth-shell floating button + the shared popover already verified live 2026-07-31 — this is the header trigger, which needs login.)*
- [ ] **Settings (logged in):** the **Support Dora** pink pill sits beside **Sign out** in the Settings header; opens the same popover.
- [ ] **Pulse feel:** confirm the pulse "pops" without feeling naggy across the menu-bar + floating buttons; with OS reduced-motion on, the pulse is off (static button).
- [ ] **Settings → About:** the **Project & source** section shows Source-code (→ github.com/BenTalese/dashy-dora), **Report a bug** (only when a support channel is set), and **Support Dora** rows.
- [ ] **After the repo is public + FU-608 placeholders swapped:** the donation links open the real pages; Help "Report an issue", the full-page-error "Report this", and DoraBot's report link all reach the live issue tracker; the issue templates resolve.

## Shopping-list / dashboard quick fixes (FU-573, FU-585)
- [ ] **FU-573 remove-count:** put a stock item on exactly **one** open list, then use the buy-verdict card's "remove from list" (or the multi-list popover's "remove from all") → the toast says **"Removed from 1 list."**, not an inflated count. Remove again with it on none → "It was already off your lists." *(Server contract is backend-test-pinned; this is the toast-wording eyeball.)*
- [ ] **FU-585 Log-a-price Back:** Dashboard → "Log a price" → search e.g. "milk" → pick an item → tap **Back** → the search box is **empty** and the smart shortlist (frequently-added / low / out) is shown, not your "milk" results.

## Onboarding story pass (2026-07-12)
- [ ] Launch onboarding as a fresh install → scene 1 (problem) renders and **does not auto-advance**; sitting on it 10+ seconds waits for you.
- [ ] Click Next → scene 2 (loop) draws in ring + nodes, then Dora at centre; the "What you're here for" persona-chip bar **does not appear anywhere** below the loop.
- [ ] Tap Dora in the centre → detail panel reads the new stronger sell ("expiry, stock, spend and habits, hinting at what you can cook now, and answering when you ask"). Tap each stage (Stock / Plan / List / Shop / Restock / Cook) → each renders its own sell line.
- [ ] Confirm scene 2 has **no** headline sub — the second "Tap any stage — or Dora in the middle" hint below the loop is gone; only the one hint under the ring remains.
- [ ] Next → scene 3 (brain) does not auto-advance; Next → scene 4 (control).
- [ ] Scene 4 shows the tune icon plus a stylised **switch panel** with four rows (AI assistant, Spend tracking, Voice replies, Barcode scanning); switches show mixed on/off states. Headline reads "every part of Dora is a toggle." Copy no longer mentions Cooking / Spend / Everything.
- [ ] Skip button (top-right) reads **"Skip onboarding"** on every scene (not just "Skip"); clicking it skips the whole wizard as before.
- [ ] Refresh mid-story → draft resumes at the same scene; no console errors about a missing `personaPreview` field on the persisted draft (old drafts should hydrate cleanly and just ignore that key).
- [ ] Reduced-motion OS setting → the ring/nodes still appear in their final state without motion (no regression from removing autoplay).

## Dora assistant / helper bubble (FU-429 + FU-360)
- [ ] AI mode ON → "add milk" still uses the richer LLM propose→confirm flow (unchanged), not the Basic path.
- [ ] **Greeting once-per-user (FU-360.5).** Fresh browser, log in as user A → the "Hi! I'm Dora" hint appears once; dismiss it → it doesn't return for A across reloads/logins. Log in as a *different* user B in the same browser → B sees the hint once (proving it's per-user, not per-browser).
- [ ] **Mode slider — enabled/toggle path (FU-360.3).** With AI mode configured (Settings → Assistant: provider + model + base URL/api key saved, install master ON), open Dora → the chat header shows a two-position pill "Basic | AI" with a skewed thick knob glowing on the active side. Tap the inactive side → knob slides across with the glow, PATCH `/auth/me` fires, and `/assistant/status` re-probes; the "AI mode unavailable" banner appears if the LLM isn't currently reachable. Tap back → returns to Basic. *(The disabled/no-LLM state + rem-scaling are verified above; this enabled-toggle path needs a configured LLM → owner-walk.)*
- [ ] **FU-360.4 (DS4 hover-flash regression) — fix landed 2026-07-12.** Hover the launcher / mascot repeatedly, and specifically *hover off* → mascot should stay put, no disappear-and-animate-back-in. Cause: the one-shot `dora-entrance` keyframes lived on the base `.dora-bubble-launcher-inner` rule, so when the hover-bob animation stopped and the base declaration reasserted, `dora-entrance` (with 300ms delay + `both` fill) restarted from its `scale(0) opacity: 0` frame. Moved onto a `.is-entering` modifier removed via `@animationend` after the entrance plays.
- [ ] **FU-515 B.3 (tool-arg bound, AI mode only).** With AI mode on, ask Dora to **"push the milk expiry by 99999 days"** → she declines with a "more than ~10 years — give me a sensible number" style message rather than proposing an absurd date. (Sanity check on the boundary cap; normal pushes like "+3 days" still work.)

## Currency & locale (FU-043) — origin FU-043
- [ ] Change currency via the input → blur/Enter → toast "Currency set to USD." + money surfaces re-render without a reload *(q-input `:model-value` not synthetically drivable — formatting/propagation itself proven; this is the keystroke→toast half)*
- [ ] Enter invalid inputs: `US` (2 chars), `USDD` (4 chars), `US1` (digits), lowercase `usd`; invalid locale `en_AU`, `english`, `en AU` — each shows an inline red error, no toast, no server round-trip *(validation logic present in `AdminSystemLocaleSettings.vue` `onSaveCurrency`/`onSaveLocale`; q-input-gated for driving)*
- [ ] Change currency to `EUR`/locale `de-DE` → **MoneySettings budget input prefix** flips to `€` and **PriceEntry dialog price input prefix** flips to `€` (the money-gated input decorations — money features OFF in the verify seed, blocked on [[FU-592]])
- [ ] Dora chat / Cook mode: hold-to-talk mic uses the household locale for speech recognition (device + mic — switch locale then hit the mic and confirm the recognised-text shape follows)

## Native Android build (P8-10) — origin P8-10
- [ ] `web_app/src-capacitor/android/` opens cleanly in Android Studio (File → Open → point at the folder); Gradle sync completes with no errors
- [ ] `./gradlew assembleDebug` from `src-capacitor/android/` produces `app/build/outputs/apk/debug/app-debug.apk` (after `npx quasar build -m capacitor -T android` has synced the SPA into `assets/public/`)
- [ ] APK installs on a real Pixel / Samsung device (or Android Studio emulator) — icon shows the Dora mascot on the yellow (#f5c462) adaptive background; app name reads **Dashy Dora**
- [ ] First launch opens `/setup/backend` (before any login prompt); entering the LAN URL of a running Dora backend (e.g. `http://192.168.x.x:5170`) → toast "Connected. Welcome to Dora!" → app navigates to `/` and the normal login flow appears
- [ ] Second launch (kill + reopen) skips the setup gate — the persisted URL is remembered
- [ ] Settings → About → **Dora API endpoint** shows the saved URL; **Change** button opens the URL prompt; saving a different URL triggers a full reload and hits the new backend
- [ ] Barcode scan (Stock Overview → Scan) triggers Android's Camera permission prompt; scanning a real EAN populates the Add-a-stock-item flow
- [ ] Open a recipe → **Cook mode** → screen stays awake through the whole session (no auto-lock) even with no touch input for 2+ min
- [ ] Open a shopping list → **Start shopping** → screen stays awake for the shop session; leaving shop mode (Finish & restock, or navigating away) releases the lock and the screen dims normally
- [ ] Settings → Notifications → Push toggle reads as **Unsupported** on the native app (no browser Push API in the WebView); PWA-install path still exposes push
- [ ] iOS platform folder (`src-capacitor/ios/`) exists but is deliberately unbuilt on this Linux dev box — verify only that the folder is present + committed; the actual Xcode build is a future prompt

## StoresSettings logo upload — origin FU-335
*(Dialog body won't paint in the hidden pane; the two-button Add↔Change `(camera)`/`(file)` + swatch + Remove structure is source-confirmed (shared `ImageSourcePicker`). Interactions below need a real OS file picker → owner/device-walk.)*
- [ ] Settings → Stores → **Add store** → the dialog's logo row now shows two buttons (`Add logo (camera)` + `Add logo (file)`) instead of the old drag-drop file input; the `StoreLogo` swatch preview above remains
- [ ] Pick a real PNG / JPEG / WebP from the file browser → preview updates immediately; typing a name + Save creates the store with the logo
- [ ] Retry with an unsupported file (e.g. a PDF) → a red inline caption appears under the picker with a friendly message; no `q-notify` toast, no crash
- [ ] Edit an existing store with a logo → the two buttons now read `Change logo (camera)` + `Change logo (file)`; the "Remove existing logo" button still shows and clears the image
- [ ] After Remove is tapped and a new image picked, the buttons flip back to "Change" labels (the draft has a fresh image)
- [ ] On mobile (or with `forceCamera` on): the camera button opens the OS camera picker directly

## PWA install + offline (build now ships in PWA mode) — origin FU-336
Requires a **built** frontend served over HTTPS or localhost (SW won't register on plain-HTTP). Use the Docker/nginx image, the desktop bundle, or `quasar serve dist/spa` after `npm run build`.
- [ ] DevTools → Application → **Service Workers**: `sw.js` registers + activates (no errors); Application → **Manifest** shows name "Dashy Dora", theme `#f5c462`, the 3 shortcuts, and no manifest warnings
- [ ] Browser offers **Install** (Chrome desktop/Android address-bar install icon); after install the app opens standalone (no browser chrome) and the window/title is Dora
- [ ] Go offline (DevTools → Network → Offline) and reload → the app shell still loads (not the browser's dinosaur); navigating to an uncached route shows Dora's `offline.html`, not a raw error
- [ ] API calls while offline fall back to the last cached GET (NetworkFirst) rather than hanging; coming back online refreshes normally
- [ ] Deploy a new build over the top → within a reload or two the "new version" flow kicks in (skipWaiting/clientsClaim) and you're not pinned to the old worker (confirms the nginx `sw.js` no-cache rule)
- [ ] Web Push: with VAPID configured, subscribe from Settings/Alerts and confirm a push arrives (the SW is what receives it) — ties off the previously-unreachable push path
- [ ] iOS branding (FU-552, fixed 2026-07-15): add to home screen on a real iPhone → the home-screen icon is Dora's D/D on the pale-yellow tile (not a blue gear, no black corners). Android/Chrome/favicon were always Dora-branded — confirm still fine
- [ ] Safari pinned-tab (FU-552, fixed 2026-07-15): on older Safari that still honours `mask-icon`, pin the tab → the `safari-pinned-tab.svg` "D/D" mark renders recoloured to theme gold, not a blue gear. **Low priority / legacy** — Safari 15+ ignores mask-icon and uses the regular icons; this is really just confirming the hand-authored monochrome D/D vector reads acceptably (it couldn't be rendered headlessly this session — the in-app browser blocks `file://`/`localhost`)

## Runtime backend URL (browser + PWA) — origin P8-10
- [ ] Save a bogus URL → toast "Instance URL saved", full reload, network banner drops (server unreachable) — confirm the app doesn't hard-crash and the About page still lets you re-open the prompt to fix it
- [ ] Re-save the original URL → app recovers cleanly on reload; API traffic goes back to normal

**Workflow:**
- Newest within each surface is at the top.
- Delete items as you verify them — no archive needed, the end-of-pre-release
  systems test catches anything that slips.
- Prefix `⚠️` on a heading means **blocking** other work — do those first.
- If a verification turns up a real bug, open a regular follow-up in
  `DORA_FOLLOWUPS.md` for the fix; this file is for "does it work, yes/no".
- "Origin FU-NNN" on each item is just a grep handle back to the work that
  spawned it; no two-way link, no archive.

---

## Cookbook & recipes

### Free-text ingredient path in the recipe editor — origin FU-506
*(Tri-state cookability server contract pinned: a required unlinked ingredient makes cookability `null`/Unknown [not True/False], multiple unlinked still null, an unlinked *optional* ingredient doesn't gate — `test_recipe_cookability.py` + `test_recipe_router.py` `UnlinkedRequiredIngredient__CookableIsTriStateNull`. The editor UI interactions below stay owner-walk.)*
- [ ] Open any recipe → **Add ingredient** → in the picker, type a name that matches nothing (e.g. "star anise" on a fresh install)
- [ ] Two options appear under the option list: **Create "star anise"** and **Use "star anise" as free text (no pantry link)** (the second option, secondary-coloured with a pencil icon)
- [ ] Tap **Use as free text** → row's picker field label flips to **Free-text ingredient**, and the string `"star anise"` appears as a muted italic caption beneath the picker
- [ ] Save the recipe → refresh → the row still shows as unlinked with the same caption
- [ ] The recipe's cookability badge renders as **Unknown** (not "In stock" / "Missing") — the tri-state *value* is pinned above; this checks the badge render
- [ ] Later, on the same row, type in the picker and pick an actual stock item → row flips back to linked; caption disappears

### RecipeEditDialog stub-creator reshape — origin FU-095
*(Server stub-defaults pinned 2026-07-20 in `test_recipe_router.py` `create_recipe__NameOnly__CreatesFreeformEmptyStub`. **UI verified live 2026-07-22 (browser drive):** Cookbook → **New recipe** opens a modal with **exactly four fields** — Name* / Cuisine / Category / Collection — and **none of the heavy fields** (no ingredients/image/instructions/dietary/tools/times); the primary button reads **"Create & open"**; filling only Name ("QA Stub Recipe") + Create & open **closed the dialog and navigated to `/cookbook/<new-id>`** with the detail page showing the name; **Cancel from an empty form created nothing** (recipe count 11→11). Stub deleted after. The **edit-existing-from-overview** path is **N/A by design** — the recipe cards expose only ♥ / chef-hat / add-to-list and there is **no edit/pencil action anywhere on the overview** (deep edit happens on the detail page); the RecipeEditDialog's edit-mode is not surfaced from the overview.)*

### Recipe importer — bulk-linker + PWA share target (Chunk 6) — origin IMPL_PLAN_RECIPE_IMPORTER
*(Verified live 2026-07-22 (browser drive; fed by an imported recipe with 4 unlinked ingredients): the **Unlinked ingredients** entry renders in the settings sidebar and the page (`/settings/admin/data/unlinked-ingredients`) lists each unlinked ingredient as a group row **`raw_text · Used in N recipes`** with a per-row Link-to-stock-item autocomplete / **Link** / **Create new** — count correct at "Used in 1 recipe" (the **FU-588** "Used in 0" regression is gone). **Create new** on the "1 lemon, juiced" row fired the toast **"Created "1 lemon, juiced" and linked in 1 recipe."** (item = `raw_text`), dropped the group count 4→3, and on the source recipe the lemon row became **linked** (`unlinked_ingredient_count` 4→3) with cookability staying `null` (neutral, still 3 unlinked). Created item + recipe deleted after. Below = the empty-state, the autocomplete/Link-button UI (Quasar q-select not synthetically drivable — endpoint pinned in `test_unlinked_ingredients_bulk_link.py`), and the Android share target.)*
- [ ] Pick a stock item from the autocomplete → click **Link** → toast confirms "Linked '<raw_text>' in N recipe(s)"; the group disappears *(the `bulk-link` endpoint is pinned in `test_unlinked_ingredients_bulk_link.py`; this bullet is the autocomplete + toast UI — the Create-new sibling path was verified live)*
- [ ] Auto-complete typing filters to matches; empty search shows the top of the alphabetical list (capped at 50)
- [ ] **PWA share target — Android Chrome only.** After installing Dora as a PWA (from the browser's Install prompt), open a recipe on RecipeTin Eats in Chrome → hit Share → **Dashy Dora** appears in the sheet → tap it → Dora opens on the cookbook overview, the paste dialog pops with the page text pre-filled in the textarea + the recipe URL in "Where's this from?" → hit Import → new recipe lands in the cookbook
- [ ] Refresh the page after the share flow — the `?share_text=…&share_url=…` params are gone from the URL, so the dialog doesn't re-open on refresh
- [ ] Recipe-detail edit mode → Freeform steps → textarea shows the hint *"Paste the recipe text or type freeform — Ctrl+V works."* below the box

### Recipe importer — paste-based rebuild (Chunk 5) — origin IMPL_PLAN_RECIPE_IMPORTER
*(Pinned server-side: `import-from-url` is deleted → 404 and `import-from-content` is the only import path (`test_recipe_import_routes.py`); the whole paste corpus parses to a minimum shape (`test_parse_recipe_from_text.py`, parametrized over every fixture); and the **taste.com.au2 video-carousel + Coles price chrome is stripped** — no "Estimate based on"/"Fulfilled by"/"coles-logo"/"Show ingredient quantity" in ingredients, no "Next video thumbnail"/"more" steps, step count fenced (`taste_video_carousel_cruft_stripped`, added 2026-07-20). The browser paste/preview/navigation flow below stays owner-walk.)*
*(Verified live 2026-07-22 (browser drive): the **Import** button opens the paste dialog — a "Paste the recipe here" textarea, a "Where's this from? (optional)" URL input, and a caption naming the Ctrl+A/Ctrl+C→paste flow + supported sites. Pasted a synthetic Quinoa-Salad page + a source URL → **Import → new recipe on the detail page, no degraded banner**; server parse: `name="Zesty Quinoa Salad"`, `servings=4`, source URL stored, **3 freeform steps**, **5 ingredients** with `raw_text` preserved. The **fuzzy matcher linked "2 tbsp extra virgin olive oil" → Olive Oil** while the other 4 stayed unlinked; the detail page renders those as **"Free-text ingredient"** rows showing the quoted text ("1 cup quinoa", "1 lemon, juiced", "100g feta cheese") — confirmed on a fresh GET (survives round-trip). With unlinked rows present the recipe is **`cookable=null` → neutral chip** (not True/False). Recipe deleted after. Below = the multi-site corpus (backend-pinned) + the link-one-row-switches-back half.)*
- [ ] Repeat with an AllRecipes page and a Half Baked Harvest page — each imports without the "couldn't auto-structure" degraded banner *(the parse corpus is backend-pinned over every fixture in `test_parse_recipe_from_text.py`; one live import above showed no degraded banner)*
- [ ] After import, **link one free-text row** to a real stock item → its label/caption switch back to the plain "Stock item" picker with no leftover quote *(the Quasar autocomplete isn't synthetically drivable; the bulk-link endpoint itself is pinned in `test_unlinked_ingredients_bulk_link.py`)*
- [ ] Confirm `Recipe.source` on the imported recipe carries the URL you typed (if any) and is blank when omitted — nothing was fetched server-side
- [ ] From RecipeDetailPage → kebab → "Import over this recipe" → paste flow, confirm-overwrite dialog, fields patched

### Ingredient DnD — reorder + cross-section move — origin FU-118 (partner-fix from FU-161 2026-07-07)
- [ ] Open a recipe in edit mode that has 2+ sections + several ingredients in each. Each ingredient row has a drag handle (`drag_indicator` icon) on the far left, with grab cursor on hover
- [ ] Grab an ingredient by the handle (NOT by the row body — text inputs and selects should keep their normal click/drag-to-select behaviour); the source row dims to ~50% opacity while dragging
- [ ] Hover over another ingredient row → only that row lights with a primary-coloured outline ring (no flash on other rows; no row-shift)
- [ ] **FU-161 partner-bug regression check.** In a section with ingredients A, B, C, D, E (top→bottom), grab **B** and drop it on **D** (dragging *downwards*). Result must be `A, C, D, B, E` — i.e. B landed *just past D*, not one row above it. Before the fix, B landed at C's original slot (`A, C, B, D, E`), one row above the drop point
- [ ] Same list, grab **D** and drop it on **B** (dragging *upwards*). Result must be `A, D, B, C, E` — D at B's original slot, B pushes down. Same as shopping-list DnD's symmetric-with-shopping-list "insert at target's original slot" behaviour
- [ ] Drop within the same section → the source row lands at the target's slot; section_client_id unchanged; "Save" enables (dirty)
- [ ] Drop onto an ingredient in a *different* section → the source row lands at the target's slot AND the Section picker on the moved row now reads the target's section; "Save" enables
- [ ] Drop onto an unsectioned row → moved ingredient becomes unsectioned (Section picker reads "(Main)")
- [ ] Save → reload → order + section assignments round-trip exactly as left
- [ ] Drag and release outside any row → no change; source row returns to 100% opacity, no drop-over ring lingers
- [ ] Drag → press Esc / cancel → state cleans up (no stale dragging-row visuals)
- [ ] Drop on the *same* row (no movement) → no change, no save dirtying
- [ ] Section picker still works as before (for moving into an *empty* section that has no rows to drop onto)
- [ ] Same stock item appearing in multiple sections still renders as separate rows with distinct quantities/notes/optional flags (verify post-DnD that this stayed working, since the FU also includes a duplicate-ingredient assessment — duplicates remain allowed by design)

### Cookbook Chunk 6 — structured recipe steps — origin FU-093
- [ ] `alembic upgrade head` applies migration `c9d4f8e2a5b6` on SQLite **and** Postgres; `verify_mappings()` passes for `RecipeStep`
- [ ] Switch toggle to **Structured**, add a top step (text + hint + ingredient + tool), add a sub-step, reorder via ↑/↓, save → reload → structure round-trips
- [ ] Switch to **Freeform**, save → `steps[]` wiped server-side; the textarea content remains
- [ ] Toggle back to **Structured**, add steps, save → editor reflects new state
- [ ] URL importer: import a recipe with schema.org `HowToStep` → editor auto-fills Structured. Import a `recipeInstructions`-only string → editor stays in Freeform with textarea filled
- [ ] `HowToSection` import produces top-level "section" steps with sub-steps
- [ ] Delete an ingredient referenced by a step → the chip disappears + save round-trips without errors
- [ ] Backup → restore round-trips `RecipeStep` / `RecipeStepIngredient` / `RecipeStepTool` in FK-correct order

*(Step-text validation pinned 2026-07-20 in `test_recipe_router.py`: a whitespace-only step text → 400 "Every step must have non-empty text." (`WhitespaceOnlyStepText`), a truly empty string → 422 validation (`EmptyStepText`). The structure round-trip + importer + backup bullets above stay owner-walk.)*

### Cookbook Chunk 7 — source URL + URL importer — origin FU-103
- [ ] `alembic upgrade head` applies `d0e5f1a3b8c7` on SQLite + Postgres; `verify_mappings()` passes for the reshaped Recipe
- [ ] Detail-page Source URL card appears under Instructions; typed value round-trips through save → reload; clearing the field → save → reload empty
- [ ] Entering an `http(s)://` URL reveals the "Open" ghost button; non-http hides it
- [ ] Importer: import from a schema.org-rich site → URL lands in `source` field (not appended to instructions); steps/ingredients parsed
- [ ] Degraded fallback: import a no-JSON-LD page → no 422; title + body text land in name/instructions; warning toast "Couldn't auto-structure that page" fires; `source` is set
- [ ] Overview "Import from URL" button opens dialog → paste URL → new recipe in cache → router lands on detail
- [ ] Unmatched-ingredients toast counts them ("3 ingredients couldn't be matched")
- [ ] An existing recipe with the old in-instructions "Source: …" still loads
- [ ] Backup → restore round-trips `source` column

### Cookbook Chunk 8 — recipe versions + detail-endpoint fix — origin FU-105
*(Server contract pinned 2026-07-20 in `tests/e2e/dora_api/test_new_recipe_version_numbering.py`: **numbering** (singleton → v2, then v3, and a version off a copy → v4 = next-by-sibling-count, not parent — fixed **FU-589**, was skipping v2); **group allocation** (singleton allocates `version_group_id`, back-fills the source, peers share it; a grouped source reuses it); **inheritance** (linked + unlinked + optional ingredients, cuisine, category, servings, instructions, source, kcal, notes; copy starts un-favourited with a fresh id); **independence** (editing the copy leaves the source untouched). **Fixed a production-severity bug in the same unit — FU-590: new-version of any recipe WITH ingredients 500'd** (autoflush of unparented clones) and silently unlinked linked ingredients (R-032 noload clone). The tools/steps/tags/collection/image inheritance + the version-card UI below stay owner-walk.)*
- [ ] `alembic upgrade head` applies `e1f6a2b4c8d9` on SQLite + Postgres; `verify_mappings()` passes
- [ ] Open a recipe with structured steps → editor's Structured/Freeform toggle populates correctly (latent bug from Chunk 6 / cook-mode Chunk 5)
- [ ] New version also inherits **tools, structured steps (with sub-step + ingredient refs remapped), dietary tags, collection, and image** (image shows without re-upload) — *the ingredient/cuisine/category/scalar inheritance is pinned above; these richer clones stay owner-walk*
- [ ] Edit the **source** → save → the copy is unchanged (the copy→source direction is pinned above)

*(Verified live 2026-07-22 (browser drive, Veggie Stir Fry — has 5 ingredients): a **singleton hides the "Other versions" card**; kebab → **New version** created **"Veggie Stir Fry (v2)"** with **no 500** (confirms the **FU-590** new-version-with-ingredients fix live), **navigated to the copy**, which **shares a back-filled `version_group_id` with the source** (both list 1 sibling), **inherited all 5 ingredients + cuisine (Asian) + servings (3)** and **starts un-favourited**; the **"Other versions" card + "v2" label render** on the copy, and the **source now shows the card too**. **Deleting the v2** (→204) dropped the source back to a singleton and the **card disappeared** (item "delete → card updates"). Item 191 structured/freeform toggle + the richer-clone inheritance + backup stay owner-walk.)*
- [ ] Meal-plan picker + cookable filter see both siblings; allocations stay per-recipe
- [ ] Backup → restore round-trips `version_group_id`

### Cookbook Chunk 9 — cost + simple nutrition, opt-in — origin FU-116
*(Flags-ON UI verified live 2026-07-23 via FU-592 (cost card, kcal input, nutrition card, Kcal sort/filter, wire shape); residuals below are migration/theme/extra-matrix owner-walks.)*
- [ ] `alembic upgrade head` applies `e5b9d2c8a4f3`; `verify_mappings()` passes
- [ ] Sort-by Kcal **direction toggle** flips the label between "Highest kcal first" / "Lowest kcal first" and recipes with no kcal sink to the bottom *(the Kcal sort option + Kcal≤ filter presence is verified above; this is the direction-label + ordering half)*

*(Cost math pinned 2026-07-20 in `test_recipe_router.py` estimated_cost tests, exercising the real `StockItemProduct → Product → ProductOffer` join: `estimated_cost = Σ qty × (offer.price_now / size_value)` rounded to 2dp; **partial coverage** returns `estimated_cost_priced_count`/`estimated_cost_total_count` counting only priced ingredients; **no priced ingredient → `estimated_cost` is None** (card hidden client-side). Guards the FU-463 SQLite-uuid-binding regression. The card/badge render + the money/nutrition flag matrix below stay owner-walk.)*
- [ ] Old freeform Nutrition expansion gone from detail page; an existing recipe with a `nutrition` text value still saves cleanly
- [ ] Money OFF + Nutrition ON: cost hidden, kcal surfaces visible
- [ ] Money ON + Nutrition OFF: cost visible, no kcal surfaces
- [ ] Pesto Light + Pesto Dark + Cherry Cola Dark — both new cards read

### Cookbook Chunk 10 — multi-part recipes via named sections — origin FU-119
- [ ] `alembic upgrade head` applies `f6c8e3a9b1d2` on SQLite + Postgres; `verify_mappings()` passes for `RecipeSection` + `section_id` on ingredient/step
- [ ] Existing recipes still load (no sections = flat list, location grouping)
- [ ] Create a recipe with two sections ("Sauce", "Filling"), assign per ingredient, save, reload → sections persist; RecipeCard shows "2 parts" badge
- [x] Cook mode: ingredient panel groups under section names; step card shows the section as a chip; "All steps" repeats header at each transition — *verified live 2026-07-22 via a contrived 2-section ("Sauce"/"Assembly") structured recipe: ingredient panel grouped by section, step card carried its section chip, All-steps list showed section headers. (Sections also round-tripped on API create — the "persist across reload" half of the create bullet above.)*
- [ ] Delete a section → rows fall back to "Main" (SET NULL), save/reload → no orphans, no FK error
- [ ] Rename a section without touching rows → rows stay pinned (editor sends ingredients[] + sections[] together)

### Cookbook Chunk 4 — detail page cleanup — origin FU-089
*(Verified live 2026-07-22 (browser drive, seeded, dark theme): **sticky toolbar composition** — Mark cooked / Cook mode / Log cook… / Print / Save + kebab (New version · Delete recipe), with **no CSV** anywhere; **Mark cooked** bumps the pool +1 (available 2→3) + stamps last-cooked to today + fires a "Marked as cooked." toast; the **name field is editable**, and a **blank name blocks save** with the inline error **"Give the recipe a name."** while the server name stays unchanged (Save is dirty-gated — disabled on a clean form); **each ingredient row shows a single chip** (Missing `bg-negative` wins over Stocked `bg-positive`) and **missing rows carry a red `.miss` tint** (stocked rows transparent) — the box was legible in dark theme; the **cook-mode guard on a not-cookable recipe** shows *"Start cook mode? This recipe isn't cookable now — 2 ingredients missing."* with Cancel / Start anyway, and **Cancel closes it without navigating**; **Cook mode → Exit returns to the recipe detail page** (not overview); the **"Available meals"** label renders. Remaining below = layout/visual/dialog-flow owner-walks.)*
- [ ] Sticky toolbar **stays pinned at the top on a narrow window** (layout at phone width)
- [ ] **Log cook…** logs N meals (dialog flow); **Print** opens the print view
- [ ] Ingredient row **without a stock item** blocks save with a prompt *(the unchanged-name-save-succeeds half is backend-pinned — the rename-to-own-name 422 fix)*
- [ ] Cook-mode guard: **outside click doesn't navigate**, and the **unsaved-edits variant** shows "Save & start" which only proceeds on save success
- [ ] meal ± shows no not-allowed cursor flash (subjective)

### Cookbook Chunk 3 — card redesign + naming — origin FU-088
*(Verified live 2026-07-22 (browser drive, seeded): recipe cards render the **placeholder media tile** (initial letter when no image), **emphasised name**, time/servings/difficulty, the **cuisine·category·time-of-day chip line**, and **dietary chips**; **collection groups collapse** on header click (cards → hidden); the **main-nav label reads "Cookbook"**; and the **search box narrows** the grid by name+ingredient (11 → 2 on "egg"). The `g r` keyboard nav is untested; the old "command palette 'Go to Cookbook'" clause is **stale** — the Ctrl/Cmd-K palette was retired. Remaining below = interaction/badge/subjective.)*
- [ ] MealStepper ± adjusts cooked pool live (decrement disabled at 0); also on **stock-item detail's recipe cards** *(Verified live 2026-07-22 on the **recipe detail page**: the ± live-adjusts the pool 3→2→1→0, **"Remove one meal" disables at 0**, and restoring via + persists (server `available_meals`=3). The card + stock-item-detail instances stay owner-walk.)*
- [ ] Allocated badge appears only when `committed_meals > 0`; **red** when `available_meals < committed_meals`, neutral otherwise — API must return `committed_meals` field *(needs a meal-plan allocation to raise `committed_meals` — owner-walk / future contrivance)*
- [ ] Card has only Cook as primary; kebab = add-all-to-list + add-to-meal-plan (no Edit/Duplicate/Delete); clicking the card opens detail *(the [♥][chef-hat][add-to-list] footer render is verified above; the kebab actions + card→detail nav stay owner-walk)*
- [ ] "meals box" on the card + equal-height within a grid row (V-pack eyeball — the meals box hides at 0 meals; equal-height is per-row layout)

### Cookbook Chunk 3+ revision (FU-088 → cookbook card revision) — origin FU-088 (revision)
- [ ] Image hide/show toggle works (per-user, persists across sessions)
- [ ] Allocated badge appears + drops correctly from overview
- [ ] Meals-cooked field relocates to planner correctly
- [ ] Meta-line swap renders correctly
- [ ] Optional ingredients render with `(optional)` hint + dimmed rows in cook mode
- [ ] Cookable signalled via cook-button colour (no separate dim)
- [ ] Difficulty filter + sort axis works
- [ ] Picker modal opens with per-ingredient checkboxes + Optional separator
- [ ] Time-of-day vocabulary in edit dialog
- [ ] Per-row Optional checkbox in both editors
- [ ] Cookability still server-derived

*(Verified live 2026-07-22: the **`[♥][chef-hat][add-to-list]` footer layout** (3 icon buttons per card) and the **meta-line** (cuisine·category·time-of-day + time/servings/difficulty) render correctly on the seeded cards. Image hide/show persistence, allocated-badge drop, optional-ingredient dimming, difficulty filter, and picker modal stay owner-walk.)*

### Cookbook Chunk 5 — images + tools — origin FU-091
- [ ] `alembic upgrade head` applies `b8e3f1a6d2c4` on SQLite + Postgres; `verify_mappings()` passes for `Tool`
- [ ] `GET /api/tools` returns seeded tools; Settings → Recipe tags & categories has a Tools editor (create/rename/delete + recipe counts)
- [ ] Recipe create/update round-trips `tool_ids`; edit dialog + detail page tools multiselect populate + save *(Verified live 2026-07-22: the detail-page **Tools multiselect populates** — Veggie shows "Wok"; and `tool_ids` round-trips on create — the contrived structured recipe was built with 2 tools and both rendered in its cook-mode Tools panel. The edit-dialog populate + in-UI save round-trip stay owner-walk.)*
- [ ] Overview Tools tri-state filter (include/exclude) works
- [ ] Upload on detail page → save → image shows on detail + card (via `GET /recipes/<id>/image`); change + remove work; cache-busts after save; >4MB rejected client-side; create dialog can attach image
- [ ] Backup → restore round-trips Tool/RecipeTool + recipe images

### Cookbook Chunk 2 — tag taxonomy — remaining items — origin FU-085
- [ ] Item 3: `repository.get(Recipe).all()` selectin-loads `recipe.cuisine`/`.category` (no null cuisine/category in assistant + global_search)
- [ ] Item 5: overview cuisine/category single-selects filter end-to-end; tri-state DietaryTagFilter cycles +/−/neutral and stays open; RecipeCard shows names + tag chips *(Verified live 2026-07-22: the Filters panel renders Cuisine/Category/Time-of-day/Difficulty single-selects + Meals≥/Missing≤/#ingredients≤/Collection; RecipeCard shows names + dietary chips; and the filter narrowing works (search 11→2, and the cookability/cuisine/max-missing logic is backend-pinned in `test_recipe_filters.py`). The dietary tri-state **cycle** interaction (+/−/neutral, stays open) is the only unwalked half.)*
- [ ] Item 6 (FU-147): on seeded "egg fried rice", two dietary tags pre-populate the picker; saving with no edit doesn't clear them; adding/removing tags + saving round-trips
- [ ] Item 8: backup → restore round-trips Cuisine/Category/DietaryTag/RecipeTag in FK-correct order
- [ ] Item 9 (FU-150): assistant `search_recipes`/`suggest_recipes` filter by cuisine + dietary tags (Python-side / name-resolved)

### FU-085 fixes — second-round verify items — origin FU-151
- [ ] FU-148 — Cookbook overview "Time of day" dropdown filters to Breakfast/Lunch/Dinner/Dessert/Snack/Any; clearable
- [ ] FU-149 — "# ingredients ≤" filter narrows the list; "# ingredients" sort axis orders ascending by default; direction toggle flips
- [ ] FU-150 step 1 — "i need a vegetarian recipe" lists vegetarian; header says "Filtering by: vegetarian recipe"
- [ ] FU-150 — "i need an asian recipe" applies cuisine filter
- [ ] FU-150 — "show me a breakfast recipe" applies timeOfDay filter
- [ ] FU-150 — "i need a recipe" with no other terms prompts for name/ingredient/cuisine/tag

### Recipe image-steps mode — origin (orphan FU at 2026-06-25, RECIPE_IMAGE_STEPS)
*(Verified live 2026-07-22 (browser drive, Veggie detail): the **mode toggle shows Structured / Freeform / Image** and each renders its own editor (Freeform textarea "One step per line…"; Structured step editor; Image mode). **Non-destructive flip** confirmed for the freeform payload — the 199-char instructions survived a full Structured → Image → Freeform cycle. The per-mode payload preservation for the structured + image editors, and the image-editor specifics below, stay owner-walk.)*
- [ ] Mode flip preserves the **structured + image** payloads too (only the freeform half was driven)
- [ ] Image-mode editor: pick multiple files from disk; pick via mobile camera prompt (`accept="image/*" capture="environment"`); reorder via ↑/↓; remove; cap warning at 20
- [ ] Save with `steps_mode='image'` posts `step_images[]` as data URLs; `/api/recipes/<id>/step-images/<image_id>` returns the original at the right MIME
- [ ] Cook mode in image-mode renders full-width scroll gallery; tap-to-zoom opens; ingredient panel + finish flow + B8 substitute swaps + Sous Chef behave as before
- [ ] Auto-detect timer card hidden; standalone timer affordance still usable (manual via Sous Chef commands)
- [ ] New-version of an image-mode recipe clones the step images
- [ ] Alembic migration applies cleanly on existing DB; `steps_mode` backfilled to `'structured'` only where `RecipeStep` rows exist

---

## Cook mode

### Recipe personal notes in cook mode — origin FU-432 (RD-29)
*(Server contract pinned in `tests/e2e/dora_api/test_recipe_notes.py`: create/read/update/clear round-trip [existing 2 tests] + **new-version carry-over** [added 2026-07-20]. **Detail-field placement + cook-mode card render verified live 2026-07-22:** the **Personal notes (optional)** field sits **below Source URL** (tops 1691 vs 1601) and is a **distinct textarea** from the freeform instructions field (own placeholder "Your own notes — …"); with a two-line note PATCHed on, cook mode renders a **"Your notes" card** carrying both lines with the **line break preserved** ("Line one… ⏎ Line two…"); a note-free recipe (Veggie pre-note + the contrived structured recipe) shows **no** card. Note cleared afterward.)*

### Cook Mode Chunks 1–3 — origin FU-096
*(Verified live 2026-07-22 (browser drive, seeded, Veggie Stir Fry — freeform, 3 steps, 1 tool): **ingredient grouping by base location** — Pantry (Jasmine Rice / Soy Sauce / Garlic) · Fridge (Broccoli) · Freezer (Chicken Breast); **no mid-cook stock-level chip** on rows (only the substitute `mdi-swap-horizontal` buttons render); **quantity spacing** — `g`/`ml` attach (`300g`, `30ml`) while word units get a space (`2 cloves`, `1 head`); the **Sous Chef** voice button (mic-message icon) + a **(?) "Sous Chef commands"** popover listing Next / Previous·Back / Repeat / Start·Pause·Reset-timer / Exit; and the **step timer auto-detected** "2 minutes" → 02:00 with a fill-bar, Start → live countdown (→01:58) + PAUSE/Reset, Reset → back to 02:00. Remaining below = the timer's expiry behaviour + the no-location fallback group.)*
- [ ] No-location fallback: a recipe with an ingredient whose stock item has **no location** lands it in a **"No location"** group (all seeded Veggie ingredients had locations)
- [ ] Timer expiry: at 0 the bar turns **negative colour**, a **toast fires**, and a **short beep** plays (no-ops on iOS/PWA without a gesture)
*(An e2e driver for the finish flow exists but is **deferred/flaky** — `web_app/e2e/cook-mode-finish.wip.ts` (NOT in the active `*.spec.ts` run; see FU-591): it drives Finish → per-row Down-one/Out/Unchanged → server-verified level drops + "You saved N meals"/"All eaten" + Cancel-fires-nothing and passes cleanly in a fresh env, but flakes under load/repeat [cook-mode loads the stock store async, so a fast "Finish" click can race ahead and the decrement no-ops]. Revive once the e2e infra is stabilised. Until then the whole finish flow below stays owner-walk.)*
- [ ] Chunk 1 finish flow: finish → dialog "Finished cooking?" shows one row per used ingredient with current level chip, action chips (Down one / Out / Unchanged, default Down one), override dropdown, per-row Add-to-list
- [ ] `meals_cooked` defaults to **0**; Done with 0 → toast "All eaten — hope it was good."; N>0 → "You saved N meals — enjoy." (with pluralisation)
- [ ] Per-row override beats action: pick explicit level for one row → Done flips that row's stock_level_id to the override; `Unchanged` rows leave stock alone
- [ ] Fail-soft: a row pointing at a deleted stock item shouldn't stop the others (Promise.allSettled)
- [ ] Click-out cancels: open finish dialog, click outside → dialog closes, **no** level/cook calls fired
- [ ] Session swap interaction: swap an ingredient to its substitute, finish → the substitute's level (not the original) updates

### Cook Mode Chunk 5 — highlight + tools + hints — origin FU-100
*(Verified live 2026-07-22 (browser drive): the freeform path first (unstructured text-match highlight / tools-panel-present / no-checkbox / All-steps-jump / "Done"-gone), then the **structured visuals** via a contrived cookable structured recipe (3 steps incl. a sub-step + hints, 2 tools with one step-referenced, 2 named sections): **step-referenced ingredient rows tint + get a 3px left accent** (blue @0.16 — unreferenced rows flat); the **step-referenced tool lights** (Frypan, opacity 1) while the **unreferenced tool dims** (Saucepan, `.dim`, opacity 0.55); the **"Sub-step" chip** renders on the sub-step card and the sub-step is **indented in "All steps"** (32px vs 16px); a **hint line renders with a lightbulb icon**. (Bonus — Chunk 10 sections: the step card carries its **section chip** and the ingredient panel + All-steps list **group by section name**.) Remaining below = the no-tools case, the deferred finish flow, and cross-theme tint.)*
- [ ] No tools panel when the recipe lists no tools
- [ ] Finish flow lists *every* ingredient on the recipe (with swaps applied), regardless of mid-cook interaction *(finish flow deferred/flaky — see the finish-flow note above)*
- [ ] Pesto Light + Pesto Dark + Cherry Cola Dark — highlight tint reads in dark mode

### Cook Mode Chunk 6 — cooking-for headcount rescale — origin FU-101
*(The `scaleQuantity` rounding contract is fully pinned in `web_app/test/unit/scaleQuantity.spec.ts` (23 tests) — a dedicated describe block added 2026-07-20 pins the literal checklist cases: rescale up/down 1.5×/0.5× [200g→300/100, eggs], fraction snap 1 cup→¾/1½, countable 1 egg→1/2 [0.75 up, floored at 1], floor-at-1, sub-tolerance ½, and the 7.5g→7½ gram edge. The component input-clamp + session-only bits below stay owner-walk.)*
*(Verified live 2026-07-22: the **"Cooking for" input defaults to the recipe's `servings`** — seed recipe `servings=3` → input shows 3 (the seed user has no `household_headcount`, so `servings` wins). The blur-clamp code (`onCookingForBlur`, `RecipeCookMode.vue:670`) is correct by inspection — `<1` or non-finite → 1, else floor — but the numeric clamp + session-only reset couldn't be driven via synthetic events (Quasar's numeric q-input ignores injected values), so the two below stay owner-walk.)*
- [ ] Blur clamp: clear input → blur → re-clamps to 1; quantities don't NaN
- [ ] Min=1: typing 0 + blur → re-clamps to 1
- [ ] Session-only: rescale, exit, come back → input shows original `servings`; saved recipe unchanged

---

## Meal plans

### "Build my week" — Pick-slots multi-select (FU-596) — origin FU-596
*(Everything else in the builder verified live 2026-07-31 — see DORA_VERIFY_TRIAGE. Server-side multi-slot placement is confirmed by direct API; this is the one UI bit the browser harness couldn't drive: its pane maxes at 750px so the multi-select opens as a mobile bottom-sheet whose options don't respond to synthetic clicks.)*
- [ ] In **Build my week → Slots → Pick slots**, select **two** slots (e.g. Lunch + Snack): both show as chips, and the generated week uses only those two slots (spread across them), never the others. *(Standard `q-select multiple`; expected to just work — 10-second confirmation.)*

### Past-unconsumed entry no longer freezes the week (FU-595 fix) — origin FU-595
- [ ] With **auto-drain OFF** (or after Reconcile → "Didn't cook" on a past day), add a meal to the current week: it succeeds (no "cannot be scheduled in the past" toast), the planner does **not** blank to "Something went wrong", and the past entry stays visible as history. *(Contract pinned by an e2e test; this is optional eyes-on confirmation.)*

### Meal reconcile — page + dashboard chip + header nudge — origin FU-317 Chunk 5 (2026-07-09)
- [ ] **Settings → Admin → System → Meal reconciliation** (FU-317 Chunk 6): as a **non-admin** user, the page shows the "You don't have admin permissions" banner instead of the settings. (Admin half verified 2026-07-22: page renders with the *Assume past-day meals were cooked* toggle + *Go to reconcile* deep-link; flipping fires a success toast and persists across reload.)

### Budget-defense recipe swaps (Suggestions panel) — origin FU-451
*(Full flow — panel → candidate rows → Preview dialog → Apply/Undo → dashboard bullet — verified live 2026-07-23 (money on via FU-592; needs the desktop planner layout); residuals below are contrivance edge-cases.)*
- [ ] A meal already marked **cooked/consumed** never appears as a swap candidate.
- [ ] **Money features off** → no Suggestions panel, no dashboard bullet at all. *(inverse verified 2026-07-22 flags-off: no money surfaces)*
- [ ] Zero-state: contrive a week that's over budget but where no alternative is cheaper → panel shows "No swap saves you money this week" + an **Open shopping lists** link.
- [ ] Apply a swap, then (in another tab / after editing the week) apply the *same stale* card → server returns a 409 "out of date" and the toast surfaces it; refreshing re-fetches.

### Unlinked-ingredient warning after meal-plan → shopping list — origin FU-505
*(Server contract pinned 2026-07-19 in `test_auto_generate_unlinked.py`: the auto-generate `unlinked_skipped` payload lists ONLY genuinely-unlinked (free-text) ingredients tagged with their recipe, a fully-linked recipe yields none, and linked ingredients still become lines. **Fixed a real bug in the same unit — FU-587: the recipe + meal-plan sources added zero linked ingredients and mis-reported all as unlinked (R-032 noload).** The dialog render + navigation below stay owner-walk.)*
- [ ] Build a meal plan for the week where at least one planned recipe has an ingredient with **no linked stock item** (either a paste-imported recipe that never got linked, or one you added a "Use as free text" ingredient to per FU-506); trigger **Generate shopping list for this week** → success toast, then a dialog titled **Add these manually** listing each unlinked ingredient as `• <ingredient> (<recipe>)` with a single **Got it** button → tap **Got it** → dialog closes, navigation to the new list still happens
- [ ] Repeat with a meal plan whose recipes are **all fully linked** → success toast, no dialog; **and confirm the recipe's non-stocked ingredients actually landed on the new list** (the FU-587 fix — previously nothing from recipes was added)

### In-context Print on the meal planner — origin FU-338 (Board page portion retired with FU-304, 2026-07-07)
- [ ] Tap Print on mobile → a **new tab** actually opens (the popup itself). (Verified 2026-07-22: the button is wired to `openPrintView` → `/api/meal-plans/<id>/print-view`, and that endpoint renders the week's day×slot grid correctly; only the tab-opening half is unwalked.)

### useListState — full sweep across meal planner + shopping list detail — origin FU-354 + FU-355 (2026-07-07)
- [ ] **Silent 401 recovery clears both too**: with the same setup, force a session expiry (server restart, or hand-clear the session cookie in DevTools) → make any API call → the 401 interceptor's `handleSessionExpired` fires → SPA lands on the login page → after re-auth, both list-state values are empty

### Show-all-slots persistence — origin FU-306 (2026-07-07)
- [ ] The setting is per-device — flip on in browser A, open in browser B on the same account → browser B is off (this is a device-scoped preference, not a household one)

### Meal Planner R-Phase 1 extraction + Phases 2–6 — origin FU-305
- [ ] Left palette: **drag-and-drop** from a recipe row to a day-slot (mouse only); pool ± / log-cook dialog; "Cancel" clears focused-target banner. (Verified 2026-07-22: search filters trays; click-add into a focused slot lands in the chosen slot; the focused-target banner reads "Adding to <Slot>, <date> — pick a recipe.")
- [ ] Middle column: ↑/↓ arrows, top/bottom buttons, vertical-swipe on mobile move the focused week. (Verified 2026-07-22: calendar click moves it, and `?monday=` persists across a hard reload — F29.)
- [ ] Drop targets accept dragged recipes; "Other" row appears for off-vocabulary historical entries. (Verified 2026-07-22: per-day slot rows render entries.)
- [ ] Entry chip **view / cook** actions wire through. (Verified 2026-07-22: Today badge renders on the right day; past days carry `day-card--past` at opacity 0.6 with zero clickable slot rows; the chip popover's ± adjust and remove-at-zero work.)
- [ ] Right column: ingredient-row **hover-highlights**, AddToList button, cook-by warning, "Full ingredient demand" expansion, generate-list + C-7 target picker. (Verified 2026-07-22: calendar, this-week-shopping count and the ingredient list with per-row list status + stock chips all render.)
- [ ] Sequential builder: the **generate-list** hand-off from the done screen. (Verified 2026-07-22: the dialog opens, lists recipes, and builds — 4 picks spread one-per-day across the upcoming days.)

### Meal Plans C-2 — full surface walk — origin FU-179
- [ ] Carousel nav — ↑/↓ arrows + keys + mobile swipe move weeks with slide animation; `prefers-reduced-motion` disables; `weekRangeLabel` updates
- [ ] Tap-add — **re-adding to the same slot increments servings**. (Verified 2026-07-22: tapping a day's slot shows the target banner and the entry lands in **that** slot — chose Breakfast, got Breakfast, F35 holds.)
- [ ] Drag — desktop drag onto slot adds; touch disables drag, tap-add works (no scroll-jank)
- [ ] Inline servings — **view / cook** actions work. (Verified 2026-07-22: ± adjusts live ×1→×2→×1, and 0 removes the entry.)
- [ ] Thu-8am-AEST drop repro (F29) no longer 400s (ties to C-2.K). (Verified 2026-07-22: past days dimmed + non-interactive; Today badge on the right day.)
- [ ] Left list — "N free" + inline ± pool stepper + log-cook work; no cookable colour/check. (Verified 2026-07-22: search filters the list.)
- [ ] Off-vocab — entry with deleted/legacy slot renders under "Other"
- [ ] Sidebar/generate work bound to focused week. (Verified 2026-07-22: "Clear this week" confirms then empties it; the old "Jump to a plan" dropdown is gone, replaced by the calendar.)
- [ ] **C-2.D calendar** — the **amber "short"** underline state specifically; month **arrows** page the window. (Verified 2026-07-22: 6 weeks render; planned / consumed / empty day states; today carries the 5px primary dot; focused week outlined; clicking a week jumps the carousel and back; month banner reads the focused month; `?monday=` resumes across a hard reload; the old dropdown is gone.)
- [ ] **C-2.H sidebar** — the add-to-list button (multi-list opens picker); hover (desktop) outlines the using meals. (Verified 2026-07-22: each needed-ingredient row shows list status — e.g. "needs 15g · on This week" — with a stock chip, and membership loads on the planner.)
- [ ] **C-2.I trays** — curated trays hide when empty; 21-day "haven't had" window spot-check. (Verified 2026-07-22: the four tray groups render, searching collapses to "Results (N)", and "Frequently planned" ranks by plan frequency.)
*(C-2.F templates save + apply verified live 2026-07-23: the templates dialog (Save-this-week / Apply-recurring / Manage-sets / empty-state), Save → "Saved this week as a template." + server-created + listed "N meals · Apply", and Apply → "Added N meals." fork onto the focused empty week. Below = the confirm/edit-safety + sets/recurring survivors.)*
- [ ] **C-2.F templates** — confirm before replacing existing future meals; editing/deleting a template leaves a week forked from it untouched
- [ ] **C-2.G sets + recurring** — `/meal-plans/templates` = the rotating-sets manager (**page renders**: "Rotating template sets" + New set; individual templates rename/delete inline in the dialog, not this page); sets new/edit-with-↑↓-reorder/delete; "Apply recurring…" applies a template or rotating set over ≤26 weeks; set rotates week-by-week; 26-week cap + "pick exactly one source" toasts
- [ ] **C-2.J sequential builder** — **Cancel writes nothing**; the generate-list modal fires from the done screen; Print opens the week's print view. (Verified 2026-07-22: the 3-step flow runs pick → "What you'll need" → Build; the preview's buy/in-stock matches the sidebar; 4 picks built one-per-day across upcoming days, skipping past days; the done screen offers Generate shopping list / Print this week / Done. **Note:** there is no Email button at all — the checklist expected one "shown disabled". **Every built meal lands in Breakfast — see FU-596.**)

---

## Shopping lists

### Substitute-swap gating on a line — origin FU-407 (RD-18)
- [ ] The swap affordance reads as distinct from the "store offers" picker on the same line (no "two Substitute labels" confusion).
- [ ] Product-only line (no stock item) → swap disabled.

### Receipt-photo attachments — origin FU-334 + R-024 follow-on
*(Section-gating/empty-state/desktop "Choose receipt" verified 2026-07-24; CRUD+cascade backend-pinned. Below = device file/camera.)*
- [ ] Mobile: *Take photo* → rear camera; capture → thumb in the strip
- [ ] Mobile: *Choose receipt* → OS picker → pick a photo → thumb appears
- [ ] Desktop: *Choose receipt* → file picker → pick an image → thumb appears
- [ ] >12MB image → inline error + toast "Could not read that image…", nothing added
- [ ] Non-image (PDF) → same error path
- [ ] Tap thumbnail → lightbox ≤80vh; backdrop + Esc close it
- [ ] Trash a thumb → optimistic remove; reload → still gone
- [ ] 3+ receipts render left-to-right in upload order; reload → same order

### Image-source picker — sanity sweep across surfaces — origin R-024
*(All surfaces on the shared `ImageSourcePicker`→`processImageFile`; avatar verified live 2026-07-24 (desktop "Add (file)", camera hidden). Stock-item image-edit surface is gone → [[FU-607]]. Below = device file/camera.)*
- [ ] Each surface (recipe hero, step images, avatar, store logo): pick a real file → resize applied + preview updates; on mobile the camera button captures one photo; step-images accepts multiple

### Trim-to-budget banner + Deferred section — origin FU-448
*(Banner copy + "everything safe" fallback + Dismiss + buy-on-out never-cut verified live 2026-07-24; math pinned in `test_trim_to_budget.py`. Happy path needs a genuinely cuttable line the seed API can't create → owner-walk.)*
- [ ] `money_features_enabled=false` → banner never appears
- [ ] money on, `budget_amount` null → banner never appears
- [ ] **Show what would be cut** → preview card, per-line reason chip + `Keep`
- [ ] `Keep` re-fires preview excluding that line; totals update; no mutation until Apply
- [ ] **Trim to fit** → `deferred_by_budget` on cuts → "Deferred to fit budget (N)" section + "Trimmed $X to fit — see deferred (N)" strip
- [ ] Strip link scrolls to the Deferred section
- [ ] Deferred line: reason chip + price + **Add back** → returns to active list; if back over budget, banner reappears on reload
- [ ] Tier ordering: highest-price cut first inside a tier
- [ ] Never-cut: essentials, meal-in-2-days, sub-$2 all survive (buy-on-low/out verified live)
- [ ] Assistant "trim my shopping list to my budget" → summary + Confirm applies; no-budget / already-under → the two decline replies

### Shopping list UX v2 — origin FU-165
*(`display_name` self-labelling backend-pinned. Rail+next-up marker, doughnut+totals, group-by (Location regroups), bulk-select, and Print all verified live 2026-07-24. Residuals below.)*
- [ ] Mobile dropdown opens + picks (viewport)
- [ ] Shop-day button tones (today/overdue) correct
- [ ] Start shopping → sticky footer → finish-review modal (ticked summary, no per-item level picker — FU-582) → Reopen reverses it
- [ ] Quick-add mid-shop works
- [ ] Row actions: price button, swap, remove
- [ ] Drag-reorder lands on the exact row you drop on (FU-161 fix stays fixed)
- [ ] Dashboard card + Dora-chat add-to-list still work

### Cart Button Chunk 2 — combined modal for 2+ products — origin FU-130
- [ ] Bulk variant — resolves target once + one summary toast regardless of per-item counts

### Cart tooltip + default-list fixes (FU-603) — origin FU-603
- [ ] With both a planning **draft** and an in-progress **shop** open, cart an item from Stock/My-Products: the picker defaults to the *draft*, not the in-progress shop (an explicit/remembered target still wins). Tooltips read "Add to a list" / "On your list — click to remove" (no longer "draft list").

### Cart Button Chunk 3 — standalone product lines + rules 1–3 — origin FU-132
*(Rules 1–3 pinned 2026-07-20 in `tests/e2e/dora_api/test_shopping_list_product_lines.py`: **Rule 1** a `product_id`-only POST creates a line (product_id + null stock_item_id); a no-anchor body → **422** business-rule violation "A line needs at least one of stock_item_id or product_id" [the checklist guessed 400 — 422 is correct for a domain rule; the DB CHECK is the backstop]. **Rule 2** linking the product to a stock item converts the orphan in place (gains stock_item_id, keeps product_id) OR folds into an existing stock-item line + drops the orphan. **Rule 3** deleting the stock-item line (by line-id) cascade-removes the nested product line. The migration, the by-stock-item remove variant, and the TS-compile check below stay owner-walk.)*
- [ ] Migration `d7c9e4a8c2b1` applies on SQLite + Postgres; `verify_mappings()` passes for the now-nullable `stock_item_id` + new `product_id` FK
- [ ] Rule 3 variant: **cart-button remove-by-stock-item** (`DELETE …/lines/by-stock-item/<S>`) also removes the nested product line (the by-line-id path is pinned above)
- [ ] No regressions on stock-item-only adds — existing dedupe by `stock_item_id` still wins
- [ ] TS compile: `ShoppingListLine.stock_item_id: string | null` doesn't break consumers

### Cart Button Chunk 3 UI — origin FU-145
- [ ] Link the product to a stock item later → parent stock-item line appears (rule 2 backend) AND product nests visually under it (rule 2 frontend)
- [ ] Remove nested product → rule-4 modal fires; "Yes" removes both, "No" leaves the parent
- [ ] Remove product-only line whose linked stock item is NOT on the list → no modal
- [ ] Linked products on My Products row still hit `onAddSingle` (stock-item path); ticking nested children works; bulk mode handles parents + children

### Cart Button Chunk 4 — meal-plan generate via Axis B — origin FU-135
- [ ] **0 draft lists**: no picker; creates new list named `Meals: <plan>`; toast; routes *(1-draft preselect + 2+ picker/cancel/create-new/merge verified 2026-07-23)*
- [ ] **1 draft list**: picker preselects that draft + "+ Create new list"; OK on draft → merges + routes
- [ ] `nothing_to_add` path still emits info toast and doesn't navigate

### State Ownership Chunk 6 — snapshot-at-add — origin FU-142
- [ ] Add line with selected offer → budget's `projected_active` (or post-finish `spent`) reflects planning-time price; price the offer up via companion + confirm snapshot is the original value
- [ ] Change `selected_product_id` via offer chip → snapshot re-captures at new offer's current price
- [ ] Clear selection → snapshot clears (line shows as "no priced intent" in any UI surfacing it)
- [ ] Tick an already-snapshotted line → tick does NOT overwrite snapshot
- [ ] Untick → snapshot persists
- [ ] Tick a legacy line (created before this chunk with `picked_offer_price` NULL) → belt-and-braces hook fills snapshot first time

### P6-01 Chunk 3 — list lifecycle — origin FU-066
- [ ] DRAFT detail → *Start shopping* → router lands on /shop directly
- [ ] SHOPPING /shop → tick a few items → kebab *Finish & restock* AND footer button → dialog lists ticked items (capped at 8 + "and N more") → restock + archive
- [ ] SHOPPING /shop → back-arrow → tooltip "Back to editing", status flips to DRAFT, lands on detail (no bounce-back)
- [ ] DONE detail → *Reopen* → restock changes reverse; status returns to DRAFT
- [ ] PWA "Shop now" — 1 SHOPPING → resume; else 1 DRAFT → open; else overview
- [ ] Open in Pesto Light + Pesto Dark + Cherry Cola Dark — dialog / primary-button styling reads

### P6-01 Chunk 4 — unified "New shopping list" dialog — origin FU-068
- [ ] Toolbar *New list* → *Empty + Create new* → empty list, routes in
- [ ] *Empty + auto-fill: low-or-out + new* → equivalent of old "From all low/out stock"
- [ ] *Template + new* → uses `instantiateAsync`; lines match template
- [ ] *Recipe + new* → bulk-adds the recipe's ingredient stock items
- [ ] *Meal plan + new* → bulk-adds `getIngredientsAsync` results
- [ ] *Empty + auto-fill: flagged + essentials-only + merge into existing* → equivalent of old "Top up the primary list"
- [ ] *Template + merge* — temp-list-then-delete dance leaves no orphan list in overview (refresh after)
- [ ] Empty-state — no active lists and stock has low/out → kickstart "New list" opens dialog with *low-or-out* pre-ticked
- [ ] Cancel discards the form (re-open shows defaults)
- [ ] Pesto Light + Pesto Dark + Cherry Cola Dark

### P6-01 Chunk 5 — merged list selector + landing — origin FU-069
- [ ] `/shopping-lists` with multiple → lands on SHOPPING if any, else newest DRAFT, else newest DONE
- [ ] `/shopping-lists` with zero → empty-state renders New list; click → dialog → submit routes to created list
- [ ] Detail selector: dropdown opens with Active (current highlighted), Archived below separator, + New list at top, Manage templates… at bottom
- [ ] Active row kebab → Copy unticked / Archive / Delete behave correctly; Archived row → Copy archived / Delete
- [ ] Deleting currently-open list bounces to landing + landing picks next list
- [ ] + New list in selector opens dialog; submit routes to created list
- [ ] Switching to a different list via selector loads its detail (status watcher / shop-mode redirect still works for SHOPPING)
- [ ] Mobile width: dropdown usable

### P6-01 Chunk 6 — in-store polish + drag-reorder — origin FU-073
- [ ] Start shopping → tap *Skip* → next item → refresh → skipped item still at end
- [ ] Tap the centre qty number → dialog → type "12" → Save → row shows 12; refresh → still 12
- [ ] Tap **Peek list** → modal lists ticked + unticked → tap an unticked → modal closes + that item is next-up; refresh → still next-up
- [ ] Detail page (DRAFT): drag line from position 1 → position 5 → lands at index 5; drag 5 → 1 → lands at index 1; off-by-one is gone (FU-161 root cause)
- [ ] Detail header: old back-arrow is gone (replaced by list selector)
- [ ] Pesto Light + Pesto Dark + Cherry Cola Dark

### Chunk 6 audit: pricing + group-by-aisle — origin FU-072
- [ ] Price editor still opens mid-shop and saves `actual_unit_price`
- [ ] Toggling group-by-location → none → group-by-merchant doesn't quietly mutate saved order

### P6-01 Chunk 7 — planned shop day — origin FU-076
- [ ] Open a list → header chip reads "No shop day" → click → date dialog → save 2026-07-01 → chip updates → refresh → still set
- [ ] Clear the date via Clear button → chip → "No shop day"
- [ ] Create a list via *New list* dialog with a date → detail loads → chip shows the date
- [ ] Set a DRAFT's date to today → navigate to `/shopping-lists` → lands on that draft (priority pick)
- [ ] With today set: in-detail banner appears with info-tone "Shopping day is today."
- [ ] With a past date set + status still DRAFT: warning-tone banner "Planned shop day was … — still unfinished."
- [ ] Selector dropdown: list with planned date sorts ahead of unscheduled lists; today's list at top of its band
- [ ] Pesto Light + Pesto Dark + Cherry Cola Dark

### Shopping lists Chunk 2 — 2+-draft picker + Shop-now routing + Set-primary removal — origin FU-060
- [ ] 2+ drafts: stock-overview cart click pops disambiguation dialog; chosen draft persists across cart clicks (sessionStorage); finishing the chosen draft clears the hint and the next cart click re-prompts
- [ ] 0 drafts: cart click shows "No draft list" dialog → "Open lists" lands on overview
- [ ] PWA "Shop now": 1 SHOPPING → shop mode; 1 DRAFT (no SHOPPING) → that draft's detail; anything else → overview
- [ ] No "Set as primary" / "Make primary" / "Primary" badge / Primary chip is visible anywhere (overview, detail, ShoppingListTemplates, ExportPrint primary chip)
- [ ] Migration `d5e9f3b2a1c8` applies cleanly on a real dev DB

---

## Stock

### Add-a-stock-item dialog — stock group + Essential + name trim (Codex review, 2026-07-17; expiry→group swap 2026-07-22)
*(Backend unit-tested; fields/no-Expiry + whitespace-reject + trim/case dedup verified live 2026-07-24 (New item → Name/Level/Location/Stock group/Essential, no Expiry; "   "→"Name is required"; "  barilla pasta  "→"already exists"). Residuals below.)*
- [ ] Add an item with a group picked + Essential on → new item's detail reflects both
- [ ] Add a group in Settings → Stock groups, then reopen the Add dialog → the new group appears (options refetch on open)

### Action-first scan mode on Stock Overview — origin FU-378
*(Needs the install-wide `scanning_enabled` flag ON — Settings → Admin, or `DORA_*`/AppSetting — and a device with a camera. Manual-entry box in the overlay works as a camera stand-in.)*
- [ ] With scanning ON, on Stock Overview the **Scan** button opens the camera overlay directly (single button, no menu on the toolbar)
- [ ] Inside the overlay there's a visible **"Action: Open stock item"** chip (with an open-in-new icon) above the manual-entry box, and a caption "Each scan opens that item — the scanner then closes." — i.e. the current action is always shown
- [ ] With the default "Open stock item" action, scan a known item's code (or type it in the manual box) → jumps to that item's detail page and the overlay closes (legacy default behaviour)
- [ ] Reopen Scan → tap the **Action** chip → a menu ("Scan does…") lists **Open stock item** + **Set to <level>** for each configured stock level (each with its colour dot; renamed levels show their custom name); the currently-selected action shows a check mark
- [ ] Pick **Set to <a level>** → the chip updates to "Action: Set to <level>" with the level's colour dot, the caption changes to "Keep scanning — each item is set to this level.", and the overlay **stays open**
- [ ] Scan (or manually enter) a known item's barcode/QR → a green "<item> → <level>" banner + chime shows, and the item's level actually changes (verify on the row after closing) — overlay stays open for the next scan
- [ ] Scan several different items in a row → each is set to the chosen level; the loop never closes on its own
- [ ] **Switch the action mid-session** (tap the chip, pick a different level, or back to "Open stock item") → the next scan uses the newly-selected action; you never have to leave the camera to change it
- [ ] Scan an unknown barcode (or a product with no linked stock item) while a level action is selected → a red banner explains it was skipped ("no pantry item linked" / "add it to your pantry first") and the overlay stays open — it does NOT open the add-item dialog
- [ ] Close the overlay (X) and reopen → the action resets to the "Open stock item" default, and no stale banner from the previous session lingers
- [ ] With scanning OFF (default) → the Scan button does not appear at all

### Register barcode against a Product from My Products — origin FU-373
- [ ] With **scanning ON** (Settings → scanning enabled): open the My Products `⋮` menu on any product → "Register barcode…" is present. Enter a barcode, Register → success toast; the dialog closes.
- [ ] Re-open the menu on the same product and register the **same barcode again** → inline error shows the "already registered" conflict (409), no crash.
- [ ] With **scanning OFF**: the "Register barcode…" `⋮` item is hidden entirely (R-029 hide-don't-nag), leaving the other menu actions intact.

### StockItem.image feature dropped — origin FU-508
- [ ] Recipes still render their images; user avatars still render; store logos still render (these are separate features and must be untouched)

### Stocktake redesign — Chunk 3 Settings + Stock Overview surfacing — origin PROPOSAL_STOCKTAKE_MODE
*Verifies the Settings block + Overview filter chip + row pulse outline. Chunk 3 lands the surfaces users find the redesign from.*

**Settings → Stocktake page**
- [ ] Navigate to **Settings → Admin → System → Stocktake** — the nav entry appears with the clipboard-check icon, between "Alert thresholds" and "AI assistant"
- [ ] Non-admin user visits the page → the red admin-permissions banner shows, the sections don't render
- [ ] With Auto **off**, run stocktake — every item's cadence is the global default (adjusted by Essential = one band faster if flagged)
- [ ] With Auto **on**, an item with recent frequent level changes moves into a shorter cadence band on next queue rebuild (verify by looking at what the runner shows as "Checked every week/fortnight/month")

**Stock Overview — "Needs check" quick-filter**
- [ ] On **Stock Overview**, expand the filter panel → a new **"Needs check"** chip appears in the chip strip, positioned after "Needs attention", with the clipboard-check icon

**Stock Overview — pulse outline around stock-level button**
- [ ] An item that IS in the stocktake queue: its **stock-level button** (the small coloured square left of the item name) has a **subtle pulsing outline** — a soft accent-coloured halo that grows and fades on a 2-second cycle
- [ ] An item NOT in the stocktake queue: no pulse, no outline
- [ ] After tapping **Still correct** in the runner for an item, return to Stock Overview and refresh — its pulse is gone (item left the queue)
- [ ] With `prefers-reduced-motion` on (browser accessibility setting): items still show the outline, but as a **static** ring (no animation) — verify by enabling reduced-motion in devtools and confirming no pulsing
- [ ] Dark mode: the pulse colour still reads well against the darker surface (uses `--brand-accent` theme token)
- [ ] Light mode: same — the halo is visible without being loud

### Stocktake redesign — Chunk 2 SPA runner rebuild — origin PROPOSAL_STOCKTAKE_MODE
*Verifies the redesigned stocktake mode: new engagement gate + cadence bands + buttons + completion screen. Chunk 3 (Settings + Stock Overview surfacing) is not yet built.*

**Runner card + buttons**
- [ ] Item card shows: name (large), location (or "No location"), and a caption line like **"Checked every fortnight · N days overdue"** — plural/singular correct for 1 day vs many
- [ ] The **Change level** button is **tinted to the current level's colour** (Stocked → positive/green, Low → negative/red, Out → neutral/muted) and shows the level's **name** with a small **"(change)"** underneath
- [ ] **Row 2 — three smaller ghost buttons:** **Skip** / **Push 3 days** / **Mute**
- [ ] No **keyboard shortcuts** shown on the buttons; pressing `1`/`2`/`3`/`s` does **nothing**
- [ ] No **Add to list** button on the card (it moved to the completion screen)

### Bulk "Log waste…" on Stock Overview — origin FU-226 chat
*Verifies the new bulk waste action in the Stock Overview bulk-select bar.*
- [ ] Enter bulk-select mode (long-press a row on mobile, or the toolbar toggle on desktop) → select 3 items, at least one with an expiry date set and at least one without → the "Log waste…" button in the bulk bar is enabled and shows the trash icon
- [ ] After bulk-logging those 3 items as wasted (Spoiled): open **Reports → waste-insights** (or the Dashboard "recently wasted" surface) — the 3 items appear with reason `spoiled` and the same `occurred_at`; the item that had an expiry date now shows expiry cleared on Stock Overview

### Auto-add-on-low toast + line chip — origin FU-315 (re-verify: FU-464 fixed a Low-transition regression 2026-07-04; FU-511 collapsed the per-item toggle to an install-wide 3-state setting 2026-07-07)
*Auto-add is now controlled by **Settings → Admin → System → Stock** — three modes:*
*`Off` never fires. `Essential only` (default) fires only for items with the Essential flag on. `All items` fires on any Stocked → Low/Out transition. Server owns the branching in `update_stock_item._try_auto_add`.*

*For the toast-behaviour checks below, set the install to `Essential only` (default) and use a stock item with the Essential flag on and exactly one open draft shopping list.*
- [ ] Trigger an auto-add (drop a qualifying Stocked item to Low from the overview) → then open the draft list: the new line renders **without a manual refresh** (the store refreshed itself)
- [ ] Item level change on the detail page (Level row) → the auto-add toast fires the same way (`updateStockItemAsync` path)
- [ ] Cook mode's per-ingredient level decrement that flips an ingredient to Low → toast fires per triggered item (multiple toasts stack — verify readability)
- [ ] Offline stock-level flip → queued (blue "Queued: Update stock level" toast); when back online + queue drains → auto-add toast fires *if* the flipped item genuinely transitions on the server side and the mode allows it

### ⭐ Zero-Input Pantry — inferred inventory (P8-07) — origin champion plan
*(Server side largely test-pinned: the belief engine — bands, cook drift, override-wins, thin-history caution, differs flag — in `test_pantry_belief.py`; the endpoint shape, per-user opt-out gate `{enabled:false, beliefs:{}}`, toggle persistence via PATCH `/auth/me`, and the fresh-level-change→HIGH-confidence pin end-to-end in `test_pantry_beliefs_endpoint.py`, 2026-07-18. The checks below are the remaining UI/loop halves.)*
- [ ] Preferences → Pantry: "Infer stock levels" toggle is present in the UI; flipping it hides/shows the chips live (the server gate + persistence are backend-pinned)
- [ ] With inference ON, stock overview rows show a "Dora: ~Band · confidence" chip beside items that have purchase history; tooltip shows the reason (e.g. "~Low — bought 11 days ago; you usually finish in about 14 days")
- [ ] Buy an item (finish a shop with it ticked + priced), reload → its belief reads Stocked with a recent-purchase reason
- [ ] Cook a recipe using that item (finish dialog → mark it "down one"/"out") → a ConsumptionEvent is written; the item's belief drifts more depleted than purchase cadence alone would, and the reason mentions "cooked with N× since"
- [ ] Let an item go well past its usual cadence with no check so the belief drifts while the recorded level still says Stocked → the chip shows the warning outline ("differs from recorded" — the drift itself is engine-pinned; this checks the outline render)
- [ ] Add an uncertain item to a draft shopping list → a single "Still have X?" quick-check appears in the suggestions inbox (not a bulk prompt); its action opens the item; dismiss/snooze work; capped at 3 across all in-play items
- [ ] Plan a meal this week whose ingredient is uncertain → same quick-check fires via the cook-decision path
- [ ] Dark-mode + non-money themes: chip colours ride semantic tokens (positive/warning/negative dots), no hardcoded colour
- [ ] Backup → restore: ConsumptionEvent is an event log (like CookEvent) and intentionally NOT in the backup sections — confirm restore still succeeds and beliefs recompute from surviving purchases/cooks

### 3-band StockLevel collapse (Sufficient axed, 2026-07-02)
- [ ] No stock-level picker anywhere still offers a "Sufficient" middle option — only Stocked / Low / Out. (The shopping-list finish modal is out of scope: its per-item picker was cut, FU-582.)
- [ ] Onboarding "Restock" scene copy reads "Finishing the shop bumps what you bought back to stocked — no re-counting" (was "well-stocked")
- [ ] Buy-verdict popover on a Stocked item: reads "Stocked" as the need-axis label (was "Well stocked")

### P8-05 "Should I buy?" buy-verdict oracle
*(Test-pinned 2026-07-18: the verdict engine — full matrix, thin-data collapse, reason
labels/details, wait-hint — in `tests/test_buy_verdict.py`; the UI seams — feature-flag
off/on across a reload, low-confidence rows stay silent, out-of-stock Buy walk with the
"You're out of stock" lead + one-tap add landing on the draft, Skip walk with both
one-tap variants and the FU-572 in-place repaint — in `web_app/e2e/buy-verdict.spec.ts`;
the client request cache (one fetch per item, 5-min stale window, invalidation refetch)
in `web_app/test/unit/useBuyVerdict.spec.ts`. Only the visual below remains.)*
- [ ] One-time visual: the orange **Wait** badge + its popover ("Above your usual price"
  with the `$last vs $usual` detail, and the wait-hint sub-caption when a cycle is
  confident) render legibly across themes — the content is engine-pinned; this is only
  the orange variant's look (the Buy/Skip variants have been walked)

### P8-02 barcode-to-add via Open Food Facts
*Requires `scanning_enabled=true` (Settings → System) and a real camera + real packaged-product barcodes.*
- [ ] **Already-mapped, direct** — scan an EAN already registered against a stock item (Stock item → Barcodes section). Expected: navigate straight to that item's detail page. No dialog. In DevTools network tab: `/api/data/barcodes/lookup` hit, **no** `/api/data/products/off-lookup` hit.
- [ ] **Already-mapped, via Product** — scan an EAN registered against a Product that's linked to a stock item. Expected: same as above (navigate to the linked item; no dialog; no OFF call).
- [ ] **Product-no-link** — scan an EAN registered against a Product with no linked stock item. Expected: Add-Item dialog opens with the barcode-only prefill and a "matches a known product" note. **No OFF call in network tab.** Confirm → new stock item created + EAN now linked to it.
- [ ] **Unknown EAN, OFF hit** — scan a real cereal/beverage/pantry barcode Dora doesn't know. Expected: OFF network hit; dialog opens with name, brand, image, category seeded and a "Suggested from Open Food Facts — review and confirm" banner. Confirm → new stock item created + EAN now registered → rescanning jumps straight to the new item.
- [ ] **Cache** — immediately rescan the same code from step above. Expected: dialog shows identical suggestion; server logs show the OFF request served from cache (no outbound OFF call).
- [ ] **Unknown EAN, OFF miss** — scan a made-up but plausible 13-digit numeric string. Expected: OFF returns `{found: false}`; dialog opens with barcode-only fallback + generic banner. Confirm → item created + EAN registered.
- [ ] **OFF network failure** — kill wifi / block `world.openfoodfacts.org` at the host level. Rescan an unknown EAN. Expected: same barcode-only fallback as OFF-miss; **no error toast**; item creates cleanly.
- [ ] **Scanning off** — flip `scanning_enabled=false` in Settings → System. Stock Overview no longer shows the scan button; the OFF endpoint stays reachable but there's no UI path to it. (Server-side gating of the endpoint itself is deliberately absent — matches `/barcodes/lookup`.)
- [ ] **Charter honesty** — the "Suggested from Open Food Facts" banner is clearly labelled and the image is a *preview*, not silently ingested. After confirm, `StockItem.image` is empty (FU-033 image seam is separate); user can add the image manually.

### History tab — origin 2026-06-30 feedback
*(Test-pinned 2026-07-18. Server halves: expiry-event emission (set/pushed/cleared +
no-op silence) and the per-kind cap → `history_older_count` in
`tests/e2e/dora_api/test_stock_item_router.py`; the Bought feed (ticked+finished only,
price/store optional, mid-shop tick not yet bought) and the Cooked feed
(RecipeIngredient join only, `meals_cooked` badge data, zero-meal cook silent) in new
`tests/e2e/dora_api/test_stock_item_history_feeds.py`; migration reversibility owned by
`tests/test_migrations.py` (SQLite downgrade xfail is a known carve-out; Postgres leg
rides batch 19). UI halves in new `web_app/e2e/history-tab.spec.ts`: the Sriracha
chatty-seed cap walk ("16 older events not shown", server-stable across reload),
under-cap busy item interleaves Bought/Wasted/Pushed with no footer, "Used in <recipe>
· N meals" batch badge, and the full Set/Pushed +7 days/Cleared title+body family on an
engineered item. Only the visuals below remain.)*
- [ ] One-time visual: event-kind colours ride their theme tokens (Bought
  `--lifecycle-bought`, cook `severity-high` deep-orange, waste negative-red, cleared
  muted `--lifecycle-cleared`) and stay legible across themes; and the footer's
  singular branch ("1 older event not shown") reads right if you ever see it — both
  are template one-liners whose plural/colour siblings are test-pinned

### Stock pickers + Log Waste — overview/dialog/detail consistency — origin 2026-06-30 feedback
*(Behavioural halves test-pinned 2026-07-18: the row expiry-menu **Log waste** path
(menu entry → reason dialog → event + toast + Undo) in `bulk-waste.spec.ts`; the
detail-page Level picker round-trip (dropdown pick → "Updated just now" stamp →
server truth) and the level filter's set→clear cycle staying console-clean with the
fallback trigger in new `stock-pickers.spec.ts`. Only the styling below remains.)*
- [ ] One-time visual: the three level pickers (overview filter, Add-item dialog,
  detail Level row) render the same `StockLevelDot` treatment in trigger + option
  rows (muted sunken dot when cleared), and the row expiry-menu's **Log waste**
  entry reads destructive-red (icon + label) matching Clear expiry

### Stock Item Detail — C-1b focused pass + C-1b.1 marquee — origin FU-202
*(Triaged 2026-07-18. Already test-pinned and deleted: the Level row round-trip +
"Updated just now" (`stock-pickers.spec.ts`); the lifecycle timeline's event kinds,
cap, and footer (`history-tab.spec.ts` + backend feed tests); location/group/notes
clear semantics and round-trips (server-pinned in `test_patch_semantics.py` +
`test_stock_item_router.py` — explicit null clears, level null is ignored); the
expiry editor dialog (`stock.spec.ts` FU-507); the unsaved-changes composable
(`useUnsavedChangesGuard.spec.ts`). Deleted as stale: the C-1b.1 "level chip in
header" bullet (superseded — the level lives in the Overview Level row, which is what
the tests pin) and every "auto-add toggle / footer Auto-add count" mention (retired by
FU-511; their absence is itself pinned by `auto-add-on-low.spec.ts`). What remains is
the owner walk below.)*
- [ ] **Layout/visual walk (one pass, light + dark):** header back/close · name ·
  (Show QR when scanning on) · danger-ghost Delete, no secondary toolbar row;
  toolbar = Mark open · Set expiry · Add-to-list (no Restock / Find-deals); "—"
  placeholders on unset Location/Stock group/Usual store/Expiry; single-column
  editors with even padding in full-page AND peek mode; Notes auto-grows; DoraTabs
  underline slide/wobble + hover accent (also `BarcodesQR.vue` / `HelpPage.vue`);
  tabs legible in every theme; QR tooltip explains QR vs real-barcode; footer counts
  Stocked-positive / Low-negative / Out-muted with the "Essential" label; row button
  cluster (expiry / flag / open / cart) same round shape
- [ ] **Splitter peek:** opens at 50%, clamps to [40%, 65%], closing restores 100%;
  gripper dots stay viewport-centred on long lists; the whole panel scrolls with the
  page (name + Delete never hidden)
- [ ] **Location/group picker × in the browser:** clearing via the picker's × (and
  Tab-blur) leaves it empty after a refresh — the server null-clear is pinned; this
  is just the q-select→PATCH wiring
*(C-1b.4 Recipes/Lists/Substitutes behaviours codified 2026-07-18 in new
`web_app/e2e/detail-recipes-tab.spec.ts` — heart toggles favourite both ways,
cookable "Add all to list" lands every ingredient on the draft, Lists tab reflects
membership with no dead `open_in_new`, Substitutes row has no "Swap into list" and
Remove unlinks. The old "styled Primary badge" wording was stale — Round-17 replaced
the pill with a warning-toned star; that's part of the visual walk above.)*
*(C-1b.3 Products tab codified 2026-07-18 in new
`web_app/e2e/detail-products-tab.spec.ts` — linked products render with exactly one
Cheapest chip/highlight + the quiet "Link another" header + no retired "Get
cheapest" button; the empty state shows the centred "Find & link a product" CTA.
**The CTA's destination is NOT pinned: it routes to the FU-186-retired
`/product-search` and 404s — real bug, logged as FU-581 (also hits My Products +
the Dashboard "Hunt for deals" CTA).** The old `?q=` seeding expectation is dead
with the route.)*
- [ ] **C-1b.3 products-OFF half (needs a productless install):** with zero Product
  rows the Products tab disappears entirely and a stranded `?section=products` URL
  falls back to Overview — not drivable against the seeded e2e DB
- [ ] **History extras:** level changes label "Restocked → X" / "Dropped to X"; empty item shows "Nothing logged for this item yet…" (the synthetic "Opened" entry + the Set/Pushed-expiry trail render verified 2026-07-24)

### Stock Item Detail + Stock Overview feedback pass — origin FU-222
- [ ] Stock Overview row — image / level / name have visible breathing room; right cluster (expiry, open, cart) larger; recipe-count chip gone; hover no longer "lifts" — surface tints + border picks up accent; first row's outline doesn't clip under page chrome
- [ ] Essential indicator: flag → 3px warning stripe on left edge + flag icon in right cluster
- [ ] Open icon pops in Pesto dark (primary, not barely-visible secondary)
- [ ] Footer counts: "Shown" reads in default text colour (not primary); per-level counts use stock-level palette; Flagged / Auto-add / Needs attention keep semantic tones
- [ ] Filter toggle on Stock Overview, My Products, Cookbook overview: "Filters" button + badge + "Clear" all in main toolbar row; no second toolbar row above the filter panel

### Stock Overview Chunk 2 — top toolbar + filters + footer — origin FU-121
*(Behavioural halves test-pinned 2026-07-18 in `stock.spec.ts` (new Chunk-2 describe:
desktop panel-persistence reload round-trip both directions; retired "Used in a
recipe" filter absent with a surviving control; bare "Search" placeholder) +
`stock-pickers.spec.ts` (single clearable "Any level" dropdown narrows/restores,
console-clean incl. the dropped-reference errors bullet) + `useStockFilters.spec.ts`
(footer counts reflect the filtered set). The old footer-order bullet listed
"Flagged / Auto-add" — stale: Auto-add's absence is pinned by
`auto-add-on-low.spec.ts` and the label is now "Essential".)*
- [ ] Clear sits LEFT of Filters and appears/disappears (filter active) without shifting the Filters button (toolbar order · Bulk-select→Cancel · footer order Shown·Needs-attention·Stocked·Low·Out·Essential·On-a-list verified 2026-07-24)
- [ ] Mobile (< md): filterable pages start with the panel hidden regardless of desktop-saved state; in-session open works, reload returns to hidden

### Stock Overview Chunk 4 — expiry control — origin FU-123
*(Partially test-pinned 2026-07-18: the **+X push semantics** — `max(today, current
expiry) + N`, future pushes from the expiry, past pushes land tomorrow, no-expiry
falls back to today+N, unparseable degrades safely, toast + failure path — in new
`test/unit/useStockItemActionsPushExpiry.spec.ts` (8 tests). The
menu-vs-date-picker split (expiry set → menu; unset → picker) and the Clear-null
round-trip are exercised by `bulk-waste.spec.ts` test 6 + the FU-507 dialog specs.)*
- [ ] No-expiry date picker: picking a future date PATCHes + row reflects it; past dates blocked by `dateOptionsFuture` (picker opens verified 2026-07-24; menu = +1/+7/+14/Clear, no +30, verified)
- [ ] Detail-panel peek staleness: with a peek open, drive the row's expiry menu /
  open-toggle / flag-toggle / level dropdown → the peek's matching field updates
  without closing/reopening (same full-screen on mobile via a different surface)

### Stock Overview Chunk 5 — responsive detail nav + long-press — origin FU-124
- [ ] Desktop (≥ md): tap row → splitter peek opens with shared `StockItemDetailPage` embedded; tap again → closes
- [ ] Mobile (< md): tap row → full-page nav to `/stock/<id>`; no drawer/peek; same `StockItemDetailPage` renders non-embedded; back returns to overview with state preserved
- [ ] Bulk mode (any breakpoint): tap toggles selection (no nav, no peek)
- [ ] Long-press on mobile: enters bulk-select + ticks held item; subsequent taps add/remove; Cancel exits
- [ ] Long-press on desktop: no-op (`<md` guard)
- [ ] Resize across md breakpoint while a peek open — peek stays attached; future row-taps use the new breakpoint's behaviour

### Offers sidecar — origin FU-230
- [ ] During chunk-8 C5 state-matrix walk: open a stock item linked to a product with a current offer (e.g. seeded Milk or Olive Oil) with money on; the widget shows "Current shelf prices: …"

---

## Dashboard

### Money/deal cards populate on a cold load — origin FU-586
- [ ] With money features ON (install flag + your account's money opt-in), open the Dashboard, then **hard-reload** the page (Ctrl/Cmd-R, or cold-start the PWA). The money cards (budget, savings, spend-by-store, pantry value, budget-defense swaps) and the price-drops deal card should fill in on their own within a moment — **without** having to navigate away and back. (Before the FU-586 fix they stayed blank until a second navigation.)

### Draft my shop — one-click card — origin FU-351
*(Test-pinned 2026-07-18. UI seams in new `web_app/e2e/dashboard-draft-shop.spec.ts`:
card renders in the act zone with blurb + button; one-click happy path → "Drafted N
items." toast + caption → navigates to the new draft named "Weekly shop · <date>"
(sidebar included — the store refresh precedes the push) with `auto:` provenance
chips rendering; Cards-menu q-toggle hides and restores the card. Server halves in
new `tests/e2e/dora_api/test_auto_generate_draft_shop.py`: zero candidates on the
create-new path → `nothing_to_add` + null id + **no phantom list**, and the explicit
"Weekly shop ·" name honoured; provenance priority already pinned in
`test_auto_generate_priority.py`, the single-commit contract in
`test_auto_generate_unit_of_work.py`. The NewListDialog merge path is untouched by
the defer change (it always passes `merge_into_list_id` — code-visible at
`auto_generate.py` §handle).)*
- [ ] Empty-case UI half (needs a fresh install — seed always has candidates): click
  → info toast "Nothing to draft yet." + caption, stays on the dashboard (the
  server's no-phantom-list half is backend-pinned)
- [ ] Error case — force a 500 mid-click: negative "Could not draft the shop." toast
  with caption; button un-spins and re-enables
- [ ] Consumed-entry window sanity: a meal-plan entry marked consumed (cook
  reconcile) does not reappear on a re-draft — the `consumed_at IS NULL` guard at
  `auto_generate.py:418` is code-visible but untestable via the API (consumed_at is
  only written by the reconcile job)

### ⭐ P8-08 Dora Score — Kitchen health card — origin champion-plan §P8-08
*(Behavioural halves test-pinned 2026-07-19: engine in `test_dora_score.py`; endpoint shape/401/log-line in `test_dashboard_router.py` + route-auth sweep; card render vs server truth, ordered rows, dormant-Budget contract, action links incl. the deliberate no-Waste-link, and the Cards-menu toggle in `web_app/e2e/dora-score.spec.ts`. The `?expiring=1`/`?stocktake=1` params being ignored by StockOverview is FU-583. Remaining below = visuals/gated.)*
- [ ] Trend chip render: green up-arrow with `+N` when direction is `up`, red down-arrow with `-N` when `down`, and **no chip** when `flat`/unavailable (needs score history in both directions — eyeball when the trend is live)
- [ ] Mini-bar traffic-light thresholds read right in both themes: green ≥80, amber 50–79, red <50
- [ ] Brand-new install (no data anywhere): card shows the calm "appears once you've been using Dora for a bit" empty state, not a 0 score (fresh-install gated)
- [ ] Trend arrow reflects `score - (score computed on the 30d window ending 7 days ago)` — logging a waste event shifts the composite down over the next week, and the arrow should flip from up/flat to down (background refresh happens 5 min after mutation; a full reload picks it up sooner)
- [ ] Drag-reorder within the kitchen zone still works with the Kitchen health card present

### Dashboard price-drops widget — origin FU-296
*(Test-pinned 2026-07-19. Server halves in `test_reports_router.py`: new-low
honesty + no-history exclusion were already pinned; added ranking (% desc,
amount tie-break), the `is_active=false` exclusion, and the limit clamp
(1/−3→1, 999→≤20, missing/`abc`→5) — which flushed out a real bug, fixed
inline: PATCH price-update inserted the archived historic offer without an
id, so the second-ever price change 500'd (see CHANGELOG). The null-current-
offer exclusion has no API path to engineer and stays code-visible
(`current_offer is not None` in `PriceDropsHandler`). UI halves in new
`web_app/e2e/dashboard-price-drops.spec.ts`: hidden by default → Cards-menu
enable → honest empty state on seed (every seeded product sits AT its low),
an engineered 20% drop rendering name · store · linked-item deep-link ·
$8.00/"was $10.00" · "20% off" badge + the "My products →" action, deactivate
→ empty state returns, toggle restored. Specs warm-navigate around the
FU-586 flags race.)*
- [ ] Products feature OFF: card absent from both the dashboard and the Cards menu (needs a productless install)
- [ ] Product images: `has_image=true` rows fetch `/api/products/{id}/image` (needs a product with an image; the placeholder half renders in the e2e run)
- [ ] Dark-mode: row colours/badge ride semantic tokens (no hardcoded red/green)

### Dashboard rebuild — full walk Phases 0–7 — origin FU-301
- [ ] **Phase 0** — cards keyboard-focus + middle-click; the dark-mode question reads correctly
- [ ] **Phase 1** — welcome rotates per day; empty states read well; primary-list footer link works
- [ ] **Phase 2** — zone bands render in order; within-zone reorder persists across reload AND another device (exercises FU-292's backend); hidden cards stay hidden
- [ ] **Phase 4** — Money band shows only with money enabled; savings range toggle re-fetches; best_deals hidden without products; money empty states
- [ ] **Phase 5** — restock Add works (toast + list refresh); Add-item dialog creates + refreshes; Add-to-list sheet works
- [ ] **Phase 6** — opt-in "This fortnight" calendar (enable via Cards menu) renders 14-day grid with correct dots; tapping a day expands detail + links work
- [ ] **Phase 7** — at 360/768/1280: zones stack, quick-action bar wraps, touch targets comfortable
- [ ] **FU-293 extraction:** every card looks identical after DashboardCard extraction — shell border/padding/shadow, header icon/title, hover lift on clickable cards (Pantry/week-ahead/budget), header action link/text styling + hover

### Dashboard "Next to cook" card (meal-plan-driven) — origin FU-298
*(Test-pinned 2026-07-19 in `web_app/e2e/dashboard-next-cook.spec.ts` on a
throwaway recipes+plan universe: rows mirror the summary DTO's dedupe/order,
"Today breakfast · serves N" meta, Ready / Missing 1 / No ingredients badges
against engineered stock truth, recipe-name → `/cookbook/{id}` and Cook →
`/cookbook/{id}/cook`. The FU-299 donut section was fully codified the same
day in `dashboard-donut.spec.ts` — incl. a real pointer click on the SVG low
arc — and deleted.)*
- [ ] Empty state when nothing is planned for the next week → "Nothing planned for the next week" + "Plan a meal →" link to `/meal-plans` (needs a plan-free install — the seed always has a current-week plan)

### Dashboard Cards menu drag-and-drop reorder — origin FU-294
*(Test-pinned 2026-07-19 in `web_app/e2e/dashboard-cards-reorder.spec.ts`,
which also closed out the FU-292 `dashboard_layout` section — migration
applied on every suite boot, `test__dashboard_layout__set_and_clear` green
in the backend suite, and the browser-walk halves now automated: tap up/down
reorders within the zone with first/last arrows disabled and both directions
working; native HTML5 drag-handle drop reorders with drop-on semantics;
cross-zone drop rejected with the server layout untouched; every reorder
asserted against menu render + the `/auth/me` `dashboard_layout` JSON +
reload persistence + a second browser context ["another device"]; iPhone-UA
run pins handle hidden with arrows + toggle remaining. The arrows are
unlabelled icon-buttons — FU-578's a11y bucket.)*
- [ ] Mid-drag visuals: the grabbed row dims and the valid drop-target row shows the primary ring; a cross-zone target shows no ring (transient states — eyeball on a real drag)

---

## Alerts & notifications

### Price watches hide on per-user money opt-out — origin FU-604
- [ ] Money on for the install, off for your account: Settings → Notifications shows no price watches and no Price drops toggle; turning it back on restores both.

### Alerts C-9.1 — spine — remaining browser smoke — origin FU-183
- [ ] **C-9.2:** the admin **Expiring-soon window** field's own save path (type a value + Save in the UI). (Verified 2026-07-22: the setting round-trips server-side 7→2→7 and reshapes the feed — expiring_soon 13→2, badge follows; **disabling a kind** removes its 11 rows from the list; **demote/promote** moved `expired` between tiers with exact accounting — actionable 34↔23, FYI 18↔29, badge tracking. UI-typing half is blocked by the Quasar synthetic-input limitation, not by a defect.)

### Cross-app undo after push-expiry (fixes 2026-07-10) — origin FU-357
- [ ] From the **Dashboard's dashboard-card push-expiry action** (i.e. the push-expiry rendered on the Dashboard alerts card, not just the bell) → toast now reads **"Done."** (this used to be silent — fixed 2026-07-10). Confirm the toast fires on Dashboard and the bell, and both behave identically.
- [ ] Push expiry via bell/dashboard, then navigate to the stock item detail page → **Clear** its expiry → no stale toast reappears, the expiry field reads empty, and no undo affordance fires against the cleared field. (Static read confirmed: no undo exists on the push_expiry path anywhere in the SPA. This step is the last belt-and-braces check.)

### fake-markdown buy verdict — origin FU-450
*(FU-602 resolved 2026-07-24 — the `good_deal` alert + "Good & great/Great only" deal-band control were a **deliberate descope**: the deal-quality band feeds the buy-verdict only, no separate naggy alert. Those two bullets deleted; the buy-verdict half below stands.)*
- [ ] **fake markdown.** For a product where the merchant claims a "special" (was > now) but you've logged paying *less* recently (price observations below the special) → the item's **Buy Verdict** card shows "Markdown looks inflated — you've paid less than this 'special' recently" and a price-driven `buy` reads as **wait**. An out-of-stock item stays **buy** (need wins) but still shows the inflated-markdown reason.
- [ ] **Money off** → no fake-markdown demotion (buy-verdict card absent).

### C-9.8 web-push channel — origin FU-206
*Prereq: generate VAPID keys per FU-207*
- [ ] Set VAPID env, restart → toggle enabled, caption hides; health flag true; key endpoint returns the public key
- [ ] Subscribe flow: toggle on → browser permission prompt → allow → toast → toggle stays on, caption "This device is subscribed…". DevTools → Application → Service Workers: SW at `/push-sw.js` registered + activated
- [ ] Receive: create expired stock item → trigger `send_alerts_push()` → OS notification "Dashy Dora — <name> has expired". Click → focuses an existing Dora tab (or opens one) with the bell panel open
- [ ] Dedup: trigger again → no second notification. Mark item not-expired → trigger → no notification + `last_pushed_at` clears. Re-add expired → trigger → fresh notification
- [ ] Multi-device: subscribe a second browser (e.g. mobile Chrome on same LAN) → trigger → both buzz
- [ ] Permission denied: fresh profile, deny prompt → caption "Notifications are blocked…"; toggle stays off; subscribe button greys
- [ ] Dead-subscription pruning: DevTools → Application → Push → unregister SW. Trigger → backend gets 404/410, `PushSubscription` deleted, no further attempts
- [ ] Unsubscribe: toggle off → toast → `PushSubscription` gone server-side; browser registration gone (DevTools confirms)
- [ ] Schedule fires: confirm `alerts_push` job registered with `CronTrigger(minute=30)`; an actionable alert created at :25 produces a notification within 5 minutes

---

## Settings

### Data pages UI revamp — Import + Backup & restore — origin FU-359 (2026-07-09)
*Requires admin login. Presentation-only rebuild onto the Settings design language — verify nothing wired regressed.*
- [ ] **Import page** — Settings → Admin → Data → **Import**. Page now uses the standard `SettingsPageHeader` with the **Download template** button in the top-right header (not a body card). Upload area is a drag-and-drop zone: drag an `.xlsx`/`.csv` onto it (or click to browse) → shows filename + size with a clear (✕) button; during upload a spinner + progress bar shows; multi-sheet workbook surfaces a sheet picker; column mapping reflows as a responsive grid; preview table scrolls horizontally; options render as labelled toggle rows; Import + Cancel bottom-right. Run a real import end-to-end → rows land, result dialog reports per-row status.
- [ ] **Backup & restore page** — Settings → Admin → Data → **Backup & restore**. **New backup** button sits in the header; clicking opens the section-picker dialog and Generate still creates a snapshot. Backup library renders as tidy rows (icon + timestamp + size/sections/author + Download/Restore/Delete icon actions); a backup containing users/settings/historic-offers shows the amber **Sensitive** chip. Empty state shows a dashed placeholder. Download / Restore / Delete each still work.
- [ ] **Restore-from-file** — drag a `.json` backup onto the drop zone → inspect spinner → the preview panel appears (backup metadata, selected/duplicate count, Select-all / Clear toolbar, the tick tree). "Restore selection" and "Restore all (skip duplicates)" both still commit and show the restore report dialog.
- [ ] **Library settings + Image compression** — both now render as `SettingsSection` blocks with `SettingsRow` fields (retention + storage path; quality slider + longest-edge input). Discard/Save enable only when dirty and still persist via `PATCH /app-settings`.

### FU-333 close-out — Buckets C + D + strict AppSetting (2026-07-06) — origin FU-333
*Requires admin login. Supersedes the earlier Bucket-B block below — env fallbacks are gone.*
- [ ] `/settings/admin/system/email`: SMTP password row now renders a real password input (not disabled). Empty state label reads "Password"; help text mentions encryption + `DORA_LLM_KEY_ENCRYPTION_KEY`.
- [ ] Type a password, click Save → toast "SMTP password saved."; the row's label flips to "Password (change)" and shows a **Clear** button; the input clears itself; reload the page — same "change" state.
- [ ] Click **Clear** → toast "SMTP password cleared."; row flips back to the "Password" label, no Clear button; the ciphertext column on `AppSetting` is empty (verify via `/api/app-settings` — `smtp_password_configured: false`).
- [ ] `/api/app-settings` **never** returns a `smtp_password` or `smtp_password_encrypted` field — only `smtp_password_configured: bool`.
- [ ] Same behaviour on `/settings/admin/system/push` for VAPID private key: real password textarea, Save then Clear, label flips accordingly, DTO returns only `vapid_private_key_configured`.
- [ ] With both VAPID public key + private key set: `/api/health` returns `features.push_vapid_configured: true`. Clear the private key → next `/health` call returns `false`.
- [ ] Env-var fallback is **gone**: unset `DORA_SMTP_HOST` (etc.) and clear the AppSetting row → the sender is in dry-run (logs the body) rather than reading env. Grep the running server logs for "DRY-RUN email" on any auth flow that would have sent.
- [ ] `.env.example` no longer lists `DORA_SMTP_*` / `DORA_VAPID_*` / `DORA_PIPER_*` / `DORA_EMAIL_ENABLED` / `DORA_AUDIT_RETENTION_DAYS` / `DORA_PUBLIC_URL` (they were removed with the fallback drop).
- [ ] **Bucket D — desktop first-run** (only meaningful when running the PyInstaller bundle, not `python dora_api/app.py`). Delete `<DATA_DIR>/.llm_key_encryption_key` (and `.secret_key`) → relaunch the app → both files reappear; `/api/health` responds normally; login still works (new session key was generated). Any previously-stored SMTP password / VAPID private key cannot decrypt against the new wrapping key — Settings shows them as "not configured" and the log carries a warning line naming the field.
- [ ] Server self-host (docker / manual): explicitly setting `DORA_SECRET_KEY` + `DORA_LLM_KEY_ENCRYPTION_KEY` in env still works — the auto-generation branch only runs when the env var is missing.

### FU-333 Bucket B — env vars promoted to AppSetting + four new admin pages (2026-07-05, historical)
*Requires admin login. Earlier checklist for the Bucket B landing; keep for reference but the FU-333 close-out block above is what should be walked now.*
- [ ] Sidebar under Admin → System now has four new entries in order: **Email** (envelope-check icon), **Push notifications** (bell-ring), **Voice** (microphone-message), **Hosting** (cloud-upload). Non-admin session doesn't see them.
- [ ] `/settings/admin/system/email`: page loads, shows Email enabled toggle + SMTP host/port/username/from/use-TLS + the password input (write-only, post-FU-333 close-out — no longer the Bucket-C disabled placeholder). Type a host, tab out → toast "Email settings saved.", reload survives.
- [ ] `/settings/admin/system/email`: with SMTP username set, `/api/health` returns `features.email_smtp_configured: true`. Clear it → next `/health` call returns `false` (no restart).
- [ ] `/settings/admin/system/push`: page loads with public key + subject fields + the private-key input (write-only). Type a subject, tab out → toast "Push settings saved.", reload survives.
- [ ] `/settings/admin/system/voice`: piper_bin / bundled_voice_dir / legacy voice inputs render; typing a valid path + blur → toast "Voice settings saved."; the assistant Speak action still resolves the same voice as before (the resolver picks the row value now).
- [ ] `/settings/admin/system/hosting`: public URL + audit retention days inputs. Try `javascript:alert(1)` in Public URL → inline red error "Must start with http:// or https://.", nothing saved. `https://dora.example.com` → toast, reload survives.

### Users admin — Add / Delete (2026-07-06) — origin FU-461
*Requires admin login.*
*(Server contract pinned 2026-07-20 in `tests/e2e/dora_api/test_users_admin.py`: create → 200 + a one-time password (≥12 chars) in the body + the user is listed (admin flag honoured); create with a **taken username** / **taken email** / **malformed email** → 422; **delete your own account → 403** ("your own account"); delete another user → 204 and they leave the list; delete unknown → 404. The PATCH last-admin-demotion guard is pinned in `test_patch_semantics.py`. The dialog/result/copy/badge/tooltip renders below stay owner-walk.)*
- [ ] Settings → Admin → Users: the header now has **Add user** (primary button, account-plus icon) alongside the refresh button.
- [ ] Click **Add user** → dialog opens with Username / Email (optional) / Admin toggle. Cancel closes without side effects.
- [ ] Submit with only a username filled → dialog closes → "User created" result dialog appears with the one-time password + Copy button (the server contract is pinned above; this checks the dialog render).
- [ ] Copy button copies the password; toast "Copied to clipboard." Close the dialog — password is gone (no way to retrieve it; admin must reset if lost).
- [ ] Log in as the new user with the copied password → login succeeds → normal onboarding path.
- [ ] Taken-username / malformed-email / taken-email adds render the error **inline** under the offending field (the 422s are pinned above; this checks the inline render, not the status).
- [ ] Try Add with the Admin toggle on → new user appears in the list with the yellow "admin" badge.
- [ ] Each row now has a **Delete** button (red text, trash icon).
- [ ] Delete on **your own row**: the button is **disabled** + tooltip "You can't delete your own account." (the server also refuses it — 403, pinned above).
- [ ] Delete on another user → confirm dialog appears with negative-coloured Delete CTA + honest scope copy ("sessions, alert prefs, push subs removed; household-shared things survive"). Cancel closes with no change.
- [ ] Confirm delete → toast "Deleted 'X'." → user disappears (the delete itself is pinned above); their historical audit events still exist (audit-log page keeps the row with the now-orphan actor_user_id).
- [ ] Recipes / shopping lists that the deleted user authored / cooked survive with a null author (RecipeCookEvent.cooked_by_user_id and ShoppingList.created_by_user_id are SET NULL).
- [ ] With only one admin remaining, attempt to delete that admin → toast "Delete failed." with caption "Refusing to delete the last admin — promote someone else first." No deletion happens. *(Delete-guard hard to reach in tests — self-delete precedence; the symmetric PATCH-demotion guard is pinned.)*

### Admin cache-race safety net — origin FU-016
*Requires at least two admins in the system (the backend blocks removing the last admin).*
- [ ] As Admin-A on `/settings/admin/users`: toggle **your own** Admin switch off → immediately the sidebar admin section (System · Data · Users · Audit) disappears from Settings, the router refuses `/settings/admin/*` (bounces to `/settings/account`), and the "Admin" pill on your row in the list is gone
- [ ] Same pre-condition, edit **your own** username or email through the admin surface → the header avatar tooltip + Settings → Account username reflect the new name **without a hard reload**
- [ ] Restore a backup that includes the **users** section, then hit **Close** on the report dialog (not "Reload now") → the header identity + admin sidebar reflect whatever the restored state says about *your* row (e.g. if you were demoted in the backup, admin surfaces disappear). Then hit **Reload now** on a subsequent restore to confirm both paths keep the guards honest

### Backup library — origin FU-342 (2026-07-01)
- [ ] As admin on `/settings/admin/data/backup`: the top card is **Backup library** (not the old "Create backup" tile). Empty state text appears until the first backup exists
- [ ] Click **New backup** → dialog opens with the section picker. Default (Core data) sections ticked; Optional sections unticked. No warning banner
- [ ] Tick any Optional section (system settings / users / historic offers) → an inline warning banner appears in the dialog naming what will be included
- [ ] Click **Generate** → dialog closes, a positive toast, the library list gains a new row at the top with today's timestamp + a byte size + section count. Row shows "by dora"
- [ ] With an Optional section included, the row also shows a **Includes sensitive data** warning chip (hover → naming which)
- [ ] Click the row's **Download** button → browser downloads `dora-backup-<date>.json`; opening it shows a `schema_version` + section keys as before
- [ ] Click the row's **Restore** button → confirm dialog appears; confirm → positive toast with a rows-imported summary. Nothing else changes since duplicates are skipped
- [ ] Click the row's **Delete** button → confirm dialog; confirm → the row disappears from the list and the file on disk is gone (check the server's `<DATA_DIR>/backups/` — no leftover)
- [ ] Create ≥ (retention_count + 1) backups → the oldest drops off the list AND its file is removed. Retention default is 5
- [ ] The external-file **Restore from backup** card (right side / below) still works: pick a downloaded backup file → inspect → tree → commit. Unchanged
- [ ] The old `/api/data/backup` GET endpoint no longer exists — no page relies on it; `POST /api/data/backups` is the only writer

### Image compression settings — install-wide (FU-345, 2026-07-01)
- [ ] Settings → Admin → Data → Backup & restore: at the bottom, a new **Image compression** card. Two rows: JPEG/WebP quality (slider, default 85) and Longest edge (numeric input, default 1920)
- [ ] Change quality to 60, hit Save → toast "Image settings saved." with caption "Applies to new uploads; existing images are unchanged."
- [ ] Discard button greys out when nothing's dirty; enables when the slider is moved but not yet saved
- [ ] Bad value guards: try setting quality to 20 (below floor) or 200 (above ceiling) via DevTools; save → 400 with a readable reason. Same for max dimension < 512 or > 8192
- [ ] End-to-end: with default (85 / 1920), upload a photo on a stock item. Note the stored file size (visible via DevTools → download the item's image, check size). Lower quality to 50, save, upload the same photo again → the new stored file is materially smaller
- [ ] Longest-edge cap: with default 1920, upload a photo with a 4000px longest edge → stored image longest edge is 1920. Lower cap to 800, upload the same source photo again → stored longest edge is 800
- [ ] Existing images unchanged after saving new settings — nothing re-encodes, no dashboard flicker
- [ ] Non-admin session: the Image compression card is unreachable (the whole admin sub-tree is gated); a non-admin's uploads still get compressed at whatever the current install policy is (they read via /health, no admin credentials needed)

### Import page Options alignment (FU-344, 2026-07-01)
- [ ] Settings → Admin → Data → Import: past the file picker and mapping (upload a small CSV to reach the Options section) the four options render as SettingsRow blocks — label + short description on the left, toggle on the right. No stacked `<br>` gap between them
- [ ] Each option's caption is descriptive (e.g. "Rolls the whole import back on any row-level failure. Off ⇒ valid rows land; errors are reported row-by-row.")
- [ ] Toggling any option flips the boolean state (verify via the subsequent Import commit: skip_duplicates on/off behaviour is unchanged)

### Import templates — Download template button (FU-343, 2026-07-01; hint row FU-349 2026-07-07)
- [ ] `/settings/admin/data/import`: the "Spreadsheet import" card's header row shows a **Download template** button on the right, next to the title / caption
- [ ] Click it → the browser downloads `dora-import-stock_items.csv`. Opening it in a text editor: first line is `name,level,location,group,expiry,is_essential`; second line is an illustrative row (`Rice,In stock,Pantry,Grains,2027-01-01,no`); **third line begins with `#`** and reads *"# example values are illustrative — replace them, and use your own level/location/group names (see Settings → Kitchen setup)."* (FU-349)
- [ ] Hover the button → tooltip shows the section caption ("One row per pantry item. Only `name` is required; the rest are optional.")
- [ ] Round-trip: open the CSV in Excel / Sheets, edit the example row (or add more), save, upload via the file picker below. Inspect step auto-maps every column; commit succeeds (or reports row-level errors as before)
- [ ] FU-349 round-trip — download the template, DON'T edit it, upload it as-is. Inspect preview shows **one** data row (the Rice example), not two — the `#` hint row is filtered by the parser. Commit with `skip_duplicates=true` creates just the one row (or zero if "Rice" already exists)
- [ ] FU-349 negative case — hand-edit a CSV so the second row starts with `#` (`#TestImport,Low,Pantry,,,`). Upload → inspect + commit → that row does NOT get imported (was filtered as a comment)
- [ ] Non-admin session: `/api/data/import/templates` and `/api/data/import/templates/stock_items.csv` both return 403

### Backup library — retention + storage path settings (FU-342)
- [ ] Scroll to the **Library settings** card at the bottom of the page. Retention shows 5 by default; storage path is blank
- [ ] Change retention to 3, Save → toast "Library settings saved." Create 4+ backups → only 3 rows visible; server has 3 files
- [ ] Enter a **relative** storage path (e.g. `data/backups`) → Save → 400 with a readable reason ("must be absolute")
- [ ] Enter a **non-existent parent** path → Save → 400 with a readable reason mentioning the offending ancestor
- [ ] Enter a valid absolute path on a writeable dir → Save → toast success; the next backup file lands in that directory, not the default. Set back to blank → next backup lands under `<DATA_DIR>/backups` again

### Backup & restore + Import relocated to Admin → Data — origin FU-341 (2026-07-01)
- [ ] As **admin**: Settings → Admin · global sidebar shows a new **Data** sub-header with two entries: **Backup & restore** (cloud-download icon) and **Import** (file-upload icon). Between Features (under the System sub-header) and Audit log
- [ ] Click Backup & restore → page loads with the standard SettingsPageHeader (title + description + cloud-download icon), then the existing Create-backup / Restore-backup two-card layout underneath. All existing controls work (section pickers, chunked upload, restore preview, confirm dialog)
- [ ] Click Import → SettingsPageHeader (Import + file-upload icon) then the existing file picker + column mapping + preview + commit flow. All existing controls work
- [ ] Main menu (top of the app) NO longer has a "Data" entry — the sequence is Stock · Cookbook · Meal Plans · Shopping Lists · Reports (+ My Products / Product Search where enabled). No gap where "Data" used to sit
- [ ] Direct-navigate to `/data`, `/data/backup`, `/data/import`, `/data/export`, `/data/barcodes` → each redirects: /data + /data/backup → the new Backup page; /data/import → Import; /data/export → Backup (nearest sibling); /data/barcodes → QR labels. No 404, no blank flash
- [ ] As **non-admin** (a regular user account): the "Admin · global" sidebar group is not shown at all. Direct-navigating to `/data/backup` or `/settings/admin/data/backup` → router guard bounces to `/settings/account`
- [ ] Onboarding wizard's "Import from a spreadsheet or another app instead" link routes to the new `/settings/admin/data/import` (admins) or bounces to `/settings/account` (non-admins) — no dead route

### FU-198 close-out — admin gate on data endpoints (2026-07-01)
- [ ] As a non-admin session (log in with a non-admin user), open DevTools → Network. Try:
  - `GET /api/data/backup` → **403** with a "Admin role required." problem-details body
  - `POST /api/data/backup/inspect` (empty body is fine) → 403
  - `POST /api/data/backup/restore` (empty body) → 403
  - `POST /api/data/uploads/start` (empty body) → 403
  - `POST /api/data/import/spreadsheet/inspect` (empty body) → 403
- [ ] As an admin session: the same endpoints return their normal 200/4xx-domain-error responses. The Backup page's Create + Restore flows and the Import page's inspect + commit still work end-to-end

### QR labels relocated to Kitchen setup — origin FU-340 (2026-07-01)
- [ ] With `scanning_enabled` **on** (Settings → System → Features toggle): Settings → Kitchen setup sidebar shows a **QR labels** entry between "Stores" and the "Recipe taxonomies" sub-header. Icon is a QR-code glyph
- [ ] Click into it → the page shows the QR labels description, the filter + layout picker, item list with checkboxes, and Print / Open-sheet actions. NO Scan tab, NO Scan card, NO "Open camera" button
- [ ] Filter, All/None, layout picker, and both Print buttons behave the same as they did on the old `/data/barcodes` page — the sheet still opens in a new tab from `/stock-items/qr/sheet`
- [ ] Toggle `scanning_enabled` **off** → the QR labels sidebar entry disappears from Kitchen setup (both desktop sidebar and mobile settings tab strip). Direct-navigate to `/settings/kitchen-setup/qr-labels` → the page renders only the "ask an admin to enable it" banner; no print controls
- [ ] Toggle back on → the entry reappears without a full reload (may require a reload if `useScanningEnabled` cached — this is expected)

### Account — verified email change + CSRF defence — origin FU-197
- [ ] **Inbox A (new address):** "Confirm your new Dashy Dora email" with the confirmation link — click → /confirm-email-change → success → the next /auth/me probe surfaces the new address in the menu
- [ ] **Inbox B (old address):** "An email change was requested on your Dashy Dora account" notice rendered from `email_change_notice.html` arrives **before** the confirmation in inbox A (same task; best-effort, but expected when SMTP is up). Old address never loses anything until the confirmation link is clicked
- [ ] With `DORA_SECURE_COOKIES=1` set on the server, the `dora_csrf` cookie also carries **Secure**. (Verified 2026-07-22 without that env: `Set-Cookie: dora_csrf=…; Path=/; SameSite=Lax`, no HttpOnly — so `document.cookie` can read it, which the double-submit design requires.)

### Assistant — banner, Test connection, docs (PR2 finalisation) — origin FU-330 + FU-331 + FU-332
- [ ] **AI-unavailable banner (FU-330):**
  - [ ] User with AI mode ON but pointing at a deliberately-bad URL (e.g. `http://localhost:9` for Ollama) → open the chat panel → banner renders at the top with red icon + the reason ("Couldn't reach Ollama" / "Your LLM didn't respond." etc.) + Retry + Settings buttons
  - [ ] Fix the URL → click Retry → banner disappears once the probe succeeds (mid-session recovery)
  - [ ] User with AI mode OFF (plain Basic) → banner never renders regardless of master flag or anything else (Basic isn't a failure)
  - [ ] Admin flips master kill-switch off → user's chat shows the banner with the master-off reason
  - [ ] DevTools → `/api/assistant/status` returns `{ai_available: bool, reason: string|null}` — reason is null when AI is up, populated when down
- [ ] **Test connection button (FU-332):**
  - [ ] Settings → Assistant → Ollama provider → enter a valid URL + model → click Test → inline green tick + "Connected. N models detected."
  - [ ] Enter a deliberately-bad URL → Test → inline red mark + reason
  - [ ] Edit the URL after a green tick → status clears (no stale tick next to wrong URL)
  - [ ] Switch to OpenAI/Anthropic/Gemini → enter a model + valid API key → Test → green tick. Wrong key → red mark + reason
  - [ ] **Without re-typing the saved key**: after saving a paid-provider key, leave the masked field empty, click Test → still works (server falls back to the saved encrypted blob)
  - [ ] **Rate limit**: hammer Test ~11 times in a minute → 11th call returns the "Too many probes — try again in Xs" message
  - [ ] **Audit trail**: Settings → Admin → Audit log shows an `assistant.probe` event per call with the actor + provider + target host + outcome (host only, no full URL or key)
- [ ] **Docs (FU-331):**
  - [ ] Help → "Dora itself" tab shows the new entries: "Set up AI mode (per account)", "AI mode says unavailable — why?", "Network topology: who reaches the LLM?", "Admin: install-wide AI master switch + API-key encryption"
  - [ ] README's "AI assistant" bullet describes the per-user pattern, all four providers, the `DORA_LLM_KEY_ENCRYPTION_KEY` env var, and the backend-reaches-LLM network topology
  - [ ] AssistantSettings.vue's inline page-level help blurb still renders (didn't accidentally get removed)

### Assistant per-user config (PR1: schema + 4 providers + master kill-switch) — origin FU-153
- [ ] `flask db upgrade head` (or `alembic upgrade head`) applies migration `e5b9d3c7a8f2_20260629_per_user_llm_config` on SQLite **and** Postgres; `verify_mappings()` passes
- [ ] `pytest -q` green (or remaining failures are pre-existing FU-328 ones, not introduced by this work)
- [ ] Backend boots — no `ImportError` from `dora_api.infrastructure.llm`
- [ ] **Settings → Assistant** (the new page) appears in the sidebar between *Nutrition* and *About*. URL is `/settings/assistant`. Reload → still shows.
- [ ] **Ollama path** (no env-var needed):
  - [ ] Pick `Ollama (local)`. Save base URL + model. AI toggle stays disabled until both are present; once saved, toggle enables AI mode → assistant replies route through the configured Ollama.
  - [ ] Old `AdminSystemAssistantSettings.vue` (now stripped) only shows the master kill-switch + a pointer to per-user settings.
- [ ] **Paid-provider flow (OpenAI / Anthropic / Gemini)** without `DORA_LLM_KEY_ENCRYPTION_KEY` set:
  - [ ] Try to save an API key → 422 with caption "`DORA_LLM_KEY_ENCRYPTION_KEY` isn't configured — paid-provider API keys can't be saved." (Or the friendly form via the error toast.)
  - [ ] Ollama saves still work.
- [ ] **Paid-provider flow with the env var set** (generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`, set in API server's env, restart):
  - [ ] Save API key → toast "API key saved." → page shows "••••••••• (saved)" placeholder. Refresh: still shows saved.
  - [ ] Save model name. Toggle AI on. Send a chat message → routes to the chosen paid provider (verify via outbound network log or by using a deliberately-wrong key and seeing the LlmUnavailable fallback fire).
  - [ ] "Remove saved key" button clears the key (server: `has_llm_api_key` flips false). AI toggle disables again with "Save an API key first" hint.
- [ ] **Per-user isolation**: User A configures Ollama + enables. User B configures OpenAI + enables. Both can chat at once; A's request hits Ollama, B's hits OpenAI. (Logs or outbound network confirm.)
- [ ] **Anthropic + Gemini smoke**: configure one of each with a valid key, send a chat that triggers a tool call (e.g. "what's low?"). The response shows the data — confirming the tool-call adapter round-tripped through `ask_assistant`.
- [ ] **Backup → restore** round-trips the new User columns + `master_llm_enabled` (the api-key ciphertext should survive a backup/restore — it's stored as a `LargeBinary` blob like `User.image`).

### Visual rebuild Phase 3 — cross-theme walk — origin FU-283
- [ ] Walk every settings page in Pesto Light + Pesto Dark + Cherry Cola Dark
- [ ] Confirm: sticky nav, dropped card chrome, DoraSegmented in sunken-fill mode, theme card 2px accent border + check_circle badge, page padding breath all read

### Settings Phase 4 — profile picture — origin FU-286
- [ ] `flask db upgrade` applies `a4f7c2e9b6d1` up **and** down, single head
- [ ] `pytest tests/e2e/dora_api/test_auth_flows.py` green (two new tests + no regressions)
- [ ] Browser: upload picture on Account → appears immediately on menu bar (cache-bust), Account header, admin Users row; clear → all revert to icon/initials; hard-refresh both states survive; >4.5MB image rejected with a usable message

### Speech-output toggle on browser without SpeechSynthesis — origin FU-289
- [ ] In a browser lacking `window.speechSynthesis` (or with it stubbed to undefined via DevTools), Settings → Voice's "Let Dora speak her replies" toggle is **visible** (not hidden) when `GET /api/tts/voices` returns `configured: true`
- [ ] DoraChat mute button is visible in the same scenario
- [ ] Toggle stays hidden when Piper is not configured (the endpoint either 503s or returns `configured: false`)

### API access page (C-10 Phase B) — origin FU-218
- [ ] Sidebar entry appears under Admin · global (admin only)
- [ ] `New key` opens dialog → reveals raw key once → copy works → list shows new row with `Never used` + `Accepted 0 / Skipped 0 / Failed 0`
- [ ] Expanding the row shows "Store mappings" panel
- [ ] Push a record from a bearer client against an unknown store → reload → source row shows pending badge + mapping appears in panel marked "pending"
- [ ] Merchant picker assigns it → badge clears
- [ ] Disable / enable / rename / revoke all round-trip
- [ ] Revoked key is rejected by `/api/ingest` immediately

### Decommission scraping (Phase D) — re-pointed nav — origin FU-186
- [ ] Re-pointed Product Search nav opens the admin-configured URL in a new tab (data-gated; R-014 disabled-with-hint when URL unset)
- [ ] System Settings input for `AppSetting.product_search_url` works (saves + round-trips)

### Ingestion: quarantine queue — origin FU-190
- [ ] Push records with unknown store names → they quarantine + appear on the API access page as pending
- [ ] Admin assigns the mapping → next push for the same name succeeds (no longer quarantined)

---

## Onboarding

### FU-615 — household cooking config moved install-wide (2026-08-10)
Backend + typecheck verified green; these are the running-app checks (the browser pane wouldn't composite the new admin page for an agent walk).
- [ ] **Settings → System → Cooking** renders: a "People" number field (blank = per-recipe) and a Fresh/Batch segmented control. Set headcount to e.g. 4 and flip to Batch — each change toasts and persists (reload the page, values stick).
- [ ] Open a recipe → **Cook mode**: the serving scaler seeds from the install headcount (4), not the recipe's own servings. Clear the headcount in System → Cooking → cook mode falls back to the recipe's servings.
- [ ] With install cook-style = **Batch**, the meal planner shows the cook-pool tools (per-recipe ± / "N free" / "to cook by"); set it to **Fresh** and they disappear — for *every* user, not per-account.
- [ ] **Settings → Preferences** no longer has a "Cooking style" toggle, and (FU-612) the whole "Meal planning" section / "Meals per week" field is gone too.
- [ ] Onboarding welcome step no longer asks headcount or "I batch-cook" (theme + font only).

### Onboarding top-bar + forced-dark cleanup (2026-08-10)
Verified live via DOM/computed-style (structure + forced-dark confirmed); these are the eyeball-feel checks left for the owner.
- [ ] Top row reads mascot · Story/Setup progress rail · **Skip onboarding**, evenly spaced with breathing room — no sign-out, no "Dashy Dora" wordmark. Check it holds at a narrow width (rail wraps, row doesn't overflow).
- [ ] Whole wizard is dark on every step regardless of your saved theme; set a **light** theme first, then walk story + all setup steps — cards must stay dark (no light-on-dark flash).
- [ ] On the final "You're all set" step the top-row **Skip onboarding** disappears (Finish takes over) — confirm you can still complete from the Finish button.
- [ ] Step 1 has no "What should I call you?" field; greeting reads "Hi, I'm Dora."; theme dropdown lists **System** (not "System (follow OS)").
- [ ] Settings → About no longer has a "Restart onboarding" section.

### FU-184 — onboarding sell-copy honesty pass (2026-07-06) — origin FU-184
- [ ] Welcome card (`/welcome` step 1) reads "I keep your pantry, **shopping and cooking** in one place…" — no mention of "deals".
- [ ] Cinematic hero loop still shows the six stages (Stock → Plan → List → Shop → Restock → Cook), no seventh "Insight/Spend smarter" candidate node dangling in the middle.
- [ ] Focus each loop stage and confirm the sell line describes something you can actually do in the app:
  - **Stock** → Stock Overview shows levels + locations + expiry chips.
  - **Plan** → Cookbook has a "Cookable now" filter; MealPlans has a week board with a shortfall indicator.
  - **List** → items marked Low / Out (or a meal-plan shortfall) appear on the current draft shopping list without a manual add.
  - **Shop** → tick-off works; a **Finish & restock** button appears once at least one item is checked.
  - **Restock** → clicking Finish & restock bumps the ticked items to Stocked (verify one on Stock Overview after).
  - **Cook** → open a recipe → Cook mode walks steps; on completion the ingredient stock levels drop.
- [ ] Persona preview chip "Mostly cooking" — the Dora-centre sell reads "…and **flagging what you can cook now**" (not "suggesting what to cook").
- [ ] `LOOP_INSIGHT` / dimmed "coming soon" chip: **not present** — should have been removed 2026-06-17.

### FU-195 — starter-data per-name picks + inline paste-rows (2026-07-02)
- [ ] On a fresh install, `/welcome` step 3 shows two collapsed cards: "Use Dora's default stock groups" and "Use Dora's default locations". Master checkbox on each header is **fully ticked** by default (matches pre-FU-195 all-on behaviour)
- [ ] Expand the groups card — 7 rows visible (Pantry, Fridge, Freezer, Cleaning, Toiletries, Pet, Other). Each has its own checkbox
- [ ] Untick "Cleaning" and "Toiletries". Header caption now reads "5 of 7 chosen". Master checkbox flips to **indeterminate**
- [ ] Untick everything else. Header caption reads "0 of 7 chosen". Master flips to **unchecked**
- [ ] Click the master while unchecked → all 7 rows tick on. Click while fully checked → all off. Middle-click on indeterminate = tick-all
- [ ] Expand the locations card — Kitchen (Zone) with Pantry / Fridge / Freezer indented, then Bathroom + Cabinet, then Laundry + Shelf
- [ ] Tick just "Kitchen/Fridge" (leaf), leave the Kitchen zone unticked. Master says "1 of 8 chosen", indeterminate
- [ ] Finish the wizard. In Settings → Stock locations only Kitchen (auto-created as FK parent) + Fridge exist. Bathroom / Laundry / their children are **not** seeded. Kitchen's zone row is NOT visually marked as "already existed"
- [ ] Ticking the zone AND a child (e.g. Kitchen + Kitchen/Fridge) seeds both (zone once, child once). No duplicate rows
- [ ] Case-insensitive: manually PATCH the local draft to have a path `"KITCHEN/fridge"` (in DevTools localStorage) → finish → seeds correctly (path comparison is lowercased server-side)
- [ ] Legacy draft resume: manually inject `{"seedGroups": false}` into the localStorage draft, reload — the groups pick-map defaults to all-**unticked** (respecting the legacy explicit-off intent). Any other legacy value → all-ticked default
- [ ] **Paste-rows affordance:** below the two seed cards, an expansion "Paste rows to bulk-add items" opens a textarea. Paste `Milk, Dairy, Fridge\nOlive oil, Pantry\nEmpty,\n , trailing comma test\n` — caption below reads "3 rows ready — added on Finish" (the empty-name and whitespace-only rows drop silently)
- [ ] Click "Queue 3 rows" → toast fires, textarea clears, the queued rows behave like step-4 draftItems (visible on step 4's "Added" list)
- [ ] Finish the wizard → the pasted rows land as stock items with the given group/location names when those exist as seeded defaults; land without a group/location when unknown (matches the step-4 "unknown name = no group" semantics)
- [ ] Full-importer link ("Bringing in a full spreadsheet? Open the full importer instead →") still routes to `/settings/admin/data/import`
- [ ] `POST /onboarding/seed` in the DevTools Network tab: when every default is ticked, the body sends `group_names: null` / `location_paths: null` (compact wire; matches "seed all" semantic). When a subset is picked, the body carries just the picked names / paths in the original casing

### Onboarding C-5.1 / C-5.2 / C-5.3 / C-5.4 / C-5.5 / C-5.6 — origin FU-192
- [ ] **C-5.1:** header reads "Skip"; bailing mid-wizard applies nothing — no username/theme/font change, no seeded groups/locations, no stock items
- [ ] Finish applies everything in dependency order (prefs → seeds → queued first items) and lands on `/`
- [ ] "Show me X" on the tour applies the draft then navigates (does NOT navigate if apply fails — e.g. invalid display name jumps back to welcome with error)
- [ ] Theme picks persist as `system`/`pesto`/`pesto-dark` and repaint
- [ ] Import line reads "spreadsheet or another app" and links to `/data/import`
- [ ] Mid-wizard refresh resumes draft including queued first items
- [ ] **First-user vs subsequent-user tracks (FU-041):** first ever user on a fresh install walks welcome → admin → seed → first_item → finish. A second user registered afterwards walks welcome → finish only — no admin, no seed catalogues step, no "add your first stock item" step
- [ ] **Batch-cooking toggle on the welcome step (FU-041 follow-up):** sits directly under the headcount input, labelled "I batch-cook" with a caption explaining what it unlocks (cook-pool ± / "N free" / shortfall). Default off. Flipping it on and finishing the wizard → `currentUser.batch_features_enabled === true` and the meal-plan recipe picker now shows "N free" caption + ± buttons. Bailing mid-wizard leaves `batch_features_enabled` untouched (like every other pref). Second run of onboarding pre-fills the toggle from the saved value
- [ ] **C-5.2:** first-run opens on story; scenes auto-advance, hero loop pauses for exploration
- [ ] Loop draws itself once, then stages + Dora are tappable + detail panel updates
- [ ] Persona preview toggles provisional Insight chip + Dora-centre copy; previewed persona persists in draft for C-5.3 fork
- [ ] Rail jumps freely Story↔Setup, nothing gated; Skip to setup + Skip work from any scene
- [ ] Reduced-motion: no autoplay/draw, final state shown, fully usable
- [ ] Keyboard: every node / persona / rail dot tabbable with visible focus
- [ ] Layout holds at narrow phone width
- [ ] **C-5.3 (first user):** persona step shows 3 preset cards + Customise pre-selected from hero preview
- [ ] Cooking drops explainer + shortens wizard; Spend/Everything show stock-vs-product explainer before seeding
- [ ] Customise reveals flat flag toggles; (products-off + money-on) combo reachable
- [ ] Flags land only on Finish — bailing changes nothing
- [ ] After Finish: install reflects chosen flags (Settings → System); first user's money/nutrition prefs match
- [ ] A second (non-first) user sees no persona / explainer
- [ ] **C-5.4:** welcome's "how many people do you cook for?" saves on Finish (blank leaves unset); cook mode with headcount → serving scaler pre-scaled; without headcount → falls back to recipe's servings
- [ ] **C-5.5:** seed step renders 5 starter packs; ticking a pack header selects all items (tri-state when partial); expanding lets you tick individual items
- [ ] First-item step's group/location pickers offer names (defaults + pack groups + existing); queued items in slim added list (removable)
- [ ] Finish: ticked pack items + first items pre-located, no duplicates on re-run
- [ ] **C-5.6:** final step shows confetti (suppressed under reduced-motion); OnboardingLoop recap (no autoplay, tappable); persona-relevant flow-cards Open each area + link to guides (the Alerts card went with the page, 2026-10-15)
- [ ] Finish / "Open X" completes onboarding (router guard clears)

### Onboarding de-persona — remaining items — origin FU-210
- [ ] Hero-loop renders well without persona shaping
- [ ] No persona/Customise/products step in setup
- [ ] Defaults applied; spend via Settings
- [ ] Draft resume works
- [ ] Story plays without LOOP_INSIGHT
- [ ] Renamed chips ("Mostly cooking" / "Watching spend" / "All of it") read sensibly
- [ ] Finish step is clean
- [ ] `WelcomeWizard.vue` admin step does NOT say "scrape" merchants (stale post-divorce copy)

### Onboarding demo dataset toggle — origin FU-194
- [ ] Wizard's seed step: the "Add a demo recipe + this-week meal plan" card is **off by default** (no auto-tick)
- [ ] Tick it, walk through to Finish on a fresh account → cookbook shows "Spaghetti Aglio e Olio", stock has Spaghetti pasta / Garlic cloves / Olive oil (created if missing), `/meal-plans` shows a current-week plan with one Dinner entry
- [ ] Dashboard's "Next to cook" card immediately surfaces the entry (with a Ready / Missing badge depending on stock levels)
- [ ] Restart onboarding + Finish again with the toggle on → no duplicates (recipe by name still 1, stock items not doubled)
- [ ] Tick the toggle on an account that already has a Spaghetti pasta starter-pack item → demo reuses it (no second "Spaghetti pasta" row)
- [ ] Demo rows behave as plain rows: deletable, renamable, no special "demo" badge anywhere

### Assistant honours configurable expiring-soon window — origin FU-187
- [ ] Settings → app settings: change `expiring_soon_window_days` from 7 to 3 (or via PATCH `/api/app-settings`)
- [ ] Ask Dora "what's expiring soon?" → only items within 3 days are listed (matching the alerts list and the location heatmap)
- [ ] Ask Dora the pantry summary → "expiring soon" count agrees with the bell
- [ ] Reset window to 7 → assistant agrees again

### Onboarding sell-copy honesty (P3 Honest gate) — origin FU-184
- [ ] Walk the running app and confirm each loop-stage claim in `onboardingContent.ts` (`LOOP_STAGES`, `LOOP_CENTRE`, `LOOP_INSIGHT`, `NARRATIVE_SCENES`, `PERSONA_PREVIEWS`) is literally true
- [ ] Does finishing a shop really auto-restock?
- [ ] Does cook mode decrement stock?
- [ ] Does price memory + "inflated price" signal exist? (If not, soften/cut)
- [ ] Cut/soften anything the app doesn't back
- [ ] **Don't promise the Insight beat** unless it's actually built

---

## Products & pricing

### PreferredBuy — origin FU-211
*(Backend fully pinned: add / rename / delete, alphabetical detail listing, blank-label reject, wrong-item-scope 404 (`test_preferred_buys.py`) + CASCADE-on-item-delete → 0 rows (`test_delete_integrity.py`). **"reorder (up-down)" is stale** — the manual reorder UI + `position` column + `reorder` endpoint were retired by FU-225 (2026-06-18); the SPA now sorts alphabetically client-side. Only the add/rename/remove detail render stays owner-walk.)*
- [ ] Stock item detail: add / rename / remove preferred-buy entries renders correctly (server contract + cascade pinned above)

### Shopping line preferred-buy hint — origin FU-215
- [ ] Pick a preferred-buy hint on a shopping line → persists across reload
- [ ] Clear the hint → persists across reload

### Stock-item Prices section — origin FU-213
*(Backend fully pinned in `test_price_observations.py`: logging an observation derives `unit_cost` (latest-wins), removing it clears `unit_cost`, plus dimension/unit-alias/store-resolution + non-positive/unknown-store rejects. The money-off gating below is client-side.)*
- [ ] Section is hidden when money features are off (the log/remove/unit_cost contract is pinned above)

### Cost consumers rebased to unit-cost helper — origin FU-216
- [ ] Stock-value report numbers look right (observation-only items now contribute, where previously they didn't)
- [ ] Recipe cost estimate numbers look right (observation fallback)
- [ ] Any tests pinning totals for observation-only items — update if broken

---

## Build / install / desktop

### Windows desktop build script — origin FU-327
*Requires a Windows box with Python 3.11, Node + npm, and Xcode-free
PowerShell 5+. Author has no Windows dev machine at this session
close-time; walked opportunistically.*
- [ ] `pip install -r requirements.txt` completes (pywebview + pyinstaller install cleanly on Windows Python 3.11)
- [ ] `.\packaging\build-windows.ps1 -Clean` runs SPA build, fetches Piper (`fetch_piper.py` auto-detects and picks `windows_amd64`), fetches default voice, runs `pyinstaller --noconfirm dora.spec` — no crashes past the "OK. Bundle at dist\Dora\Dora.exe" line
- [ ] `dist\Dora\Dora.exe` exists and launches — Dora window opens, SPA loads
- [ ] With WebView2 Runtime installed (Windows 10 or 11): the WebView2 process spawns; no "MissingWebView2Runtime" error dialog
- [ ] Piper voice works out-of-box: Settings → Voice → Amy shows `status: ready`; cook-mode narration plays through WebView2 audio
- [ ] Data persists to `%LOCALAPPDATA%\Dora\` (check the folder exists after first save)
- [ ] `-SkipSpa` reuses an existing `web_app\dist\spa\` build (skip SPA build step; PyInstaller step still runs)
- [ ] `-SkipPyInstaller` runs only the SPA build (early-exit before PyInstaller)

### macOS desktop build script — origin FU-327
*Requires a macOS box with Python 3.11, Node + npm, and Xcode command-
line tools (`xcode-select --install`). Author has no macOS dev
machine at this session close-time; walked opportunistically.*
- [ ] `pip install -r requirements.txt` completes on the target Python (Apple Silicon: arm64 Python; Intel: x86_64 Python — the interpreter arch determines the bundle arch)
- [ ] `./packaging/build-macos.sh --clean` runs SPA build, auto-detects arch (arm64 → `macos_aarch64`, x86_64 → `macos_x64`) and fetches matching Piper, fetches default voice, runs `pyinstaller --noconfirm dora.spec` — no crashes past the "OK. Bundle at dist/Dora/Dora" line
- [ ] `dist/Dora/Dora` exists, is executable (`ls -l` shows `-rwxr-xr-x`), and launches — Dora window opens, SPA loads
- [ ] Piper voice works out-of-box: Settings → Voice → Amy shows `status: ready`; cook-mode narration plays through WKWebView audio (also exercises the FU-287 iOS/WKWebView primer)
- [ ] Data persists to `~/Library/Application Support/Dora/` (check the folder exists after first save)
- [ ] `--arch macos_x64` on an Apple Silicon Mac fetches the Intel Piper tarball (verify `packaging/piper/piper` is `Mach-O x86_64` via `file`); the bundle interpreter arch still matches the venv you're building in
- [ ] `--skip-spa` and `--skip-pyinstaller` flags behave the same as `build-linux.sh`

### Fresh-install first-admin bootstrap — origin FU-200
*Requires a clean DB — delete `data/dora.db` (or point `DORA_DB_PATH` at a fresh file) and restart the API.*
- [ ] Cold-load the SPA → lands on `/setup` (NOT `/login`); page shows the "One-time setup" pill, "Create the first admin account" copy, and an **Email** field that's required (not optional like /register)
- [ ] Type a username + email + a weak password (e.g. "short") → submit → 422 with the password-rules error inline; no admin created
- [ ] Submit a valid username + email + 10-char letter+digit password → success toast, auto-logged-in, lands on `/` (dashboard); `/me` shows `is_admin: true`, `email_verified: true`
- [ ] Refresh the browser → goes straight to the dashboard (NOT `/setup` again); `/auth/bootstrap-required` returns `{required: false}`
- [ ] Manually navigate to `/setup` → bounced to `/` (already-authed) or `/login` (after logout); page is single-use
- [ ] `POST /api/auth/bootstrap-admin` directly with curl → 410 Gone with problem+json body *"An admin account already exists. Sign in instead."*
- [ ] Log out, then register a normal account via `/login` → toggle to register → submit → new user has `is_admin: false`, `email_verified: false` (verify via DB or `/me`), and the verification email is queued (or visible in dev logs)
- [ ] **With ADMIN_BOOTSTRAP_EMAIL set:** wipe DB, set `ADMIN_BOOTSTRAP_EMAIL=admin@example.com` in env, restart → `/setup` accepts only that email; submitting a different email returns a 410 *"This installation is locked to a pre-configured admin email."* (generic — does NOT leak the configured email back); submitting the matching email succeeds as above
- [ ] No regression: existing single-tenant install still loads `/login` first; existing users sign in normally; `bootstrap_required` audit event NOT emitted on subsequent registrations

### Docker + desktop builds bundle the default voice — origin FU-286
- [ ] Next Docker image build: `GET /api/tts/voices` returns Amy with `status: "ready"` on first boot, before any user touches Settings → Voice
- [ ] Desktop bundle (Linux first): `<dist>/Dora/voices/en_US-amy-medium.onnx` (+ `.json`) present; same UI behaviour
- [ ] If Amy isn't Ready, check: GitHub Actions / build runner blocking HF download (look for WARN line); spec's `if os.path.isdir(...)` guard hiding a path mismatch; `bundled_voices_dir`'s `_MEIPASS`/`packaging/voices` path search missing the runner's layout

### Piper synthesis + browser walk — origin FU-291
*Needs env with Piper present (Docker, desktop bundle, or `pip install piper-tts` on Linux/macOS)*
- [ ] Settings → Voice: download a voice → it flips to Ready
- [ ] Preview each voice; switch engine
- [ ] Dora chat with "speak replies" on
- [ ] Cook mode Sous Chef stepping
- [ ] 503 → browser fallback when Piper is absent

### Piper-binary auto-provisioning — Docker + desktop — origin FU-290
- [ ] Run Docker build → confirm `piper` on PATH in the image
- [ ] Linux desktop build (`packaging/build-linux.sh`) → bundle contains `piper/` and the app synthesises
- [ ] Windows desktop build (when scripts land per FU-288) → same

---

## Operator

### FK-index migration applies incrementally on a populated DB — origin FU-563 (2026-07-15)
*The test suite covers the from-empty upgrade and the `create_all` path; this confirms the additive index migration also applies cleanly to an already-populated existing install (the real self-host upgrade path).*
- [ ] On an **existing** install with real data at the previous head (`a1b7f3e9c2d4`), run the app's startup upgrade (or `flask db upgrade`) → migration `b9d4f2a7c3e1_20260715_fk_covering_indexes` runs, boot completes, no error, and the app behaves identically (indexes are transparent).
- [ ] Optional Postgres pass (when a disposable PG is available, FU-405): `DORA_TEST_DB=postgres` full suite stays green — confirms the 43 `CREATE INDEX`es apply on Postgres too, not just SQLite.

### FK ondelete rebuild preserves data + fixes delete behaviour — origin FU-565 (2026-07-15)
*Migration `d3f8b1a6c4e2_20260715_fk_ondelete_drift` rebuilds `StockItem`, `Product`, `ProductOffer`, `ProductHistoricOffer` on SQLite to recreate 6 FKs with their correct on-delete rule. `StockItem` is the biggest/most-referenced rebuild in this arc — confirm on real data.*
- [ ] On an install with real `StockItem` (and ideally `Product`/offer) data, run the startup upgrade → migration runs, **all rows survive**, and the FU-563 covering indexes + `StockItem.usual_store_id`'s existing SET NULL are intact.
- [ ] Spot-check the fixed behaviour: delete a `StockLevel`/`StockGroup`/`StockLocation` that a stock item references → the item's link **clears (SET NULL)** instead of erroring; deleting a `Product` cleans up its offers (**CASCADE**); a `Store` still referenced by a product is **blocked (RESTRICT)**.
- [ ] Optional Postgres pass (FU-405): same migration via native DROP/ADD CONSTRAINT (no rebuild) — `DORA_TEST_DB=postgres` suite green.

### Product nullability rebuild preserves data on a populated DB — origin FU-564 (2026-07-15)
*Migration `c1e8a5f3d9b2_20260715_product_nullability` rebuilds the `Product` table on SQLite (`batch_alter_table`) to tighten `is_active`/`is_available` to NOT NULL and loosen `merchant_stockcode` — a table rebuild is more invasive than the FU-563 `CREATE INDEX`, so confirm on real data. (No-op on installs with no products.)*
- [ ] On an install with **real Product rows** (products layer populated), run the startup upgrade → migration runs, all Product rows survive the rebuild, `store_id` FK + the `ix_Product_store_id` index are intact, and product surfaces (My Products, Price History, stock-item Products tab) render normally.
- [ ] Confirm any pre-existing `Product` rows with NULL `is_active`/`is_available` (if any) came through as active/available (backfilled to true), and that a product insert now requires those flags (dev + prod agree).
- [ ] Optional Postgres pass (FU-405): the same migration applies via native `ALTER COLUMN` (no rebuild) — `DORA_TEST_DB=postgres` suite green.

### Production WSGI server (gunicorn) — origin FU-397 (shipped 2026-07-14)
*Can't be run on the Windows dev box (gunicorn needs POSIX/fcntl) — confirm in the Linux container or a Linux/WSL checkout.*
- [ ] Build + boot the container with `DORA_ENV=production` (compose default) and the required prod vars set → container logs show `[startup] dora_api via gunicorn (production WSGI, gunicorn.conf.py)` and gunicorn's own boot lines (`Booting worker`, `Listening at: http://0.0.0.0:5170`), **not** Flask's `WARNING: This is a development server`.
- [ ] Confirm exactly **one** gunicorn worker by default (`ps aux | grep gunicorn` inside the container → one master + one worker); the SPA + API respond normally through nginx on `:5174`/`:5170`.
- [ ] Scheduler still fires once: check the logs over a reset interval (or set `DORA_DEMO_MODE=true` + `DORA_DEMO_RESET_MINUTES=2`) → the demo reset / scheduled jobs run **once** per interval, not duplicated.
- [ ] Force the dev server in a container with `DORA_API_SERVER=flask` → logs show `via Flask dev server`; force gunicorn in a dev profile with `DORA_API_SERVER=gunicorn` → gunicorn boots. (`auto` picks by `DORA_ENV`.)
- [ ] Set `DORA_WEB_CONCURRENCY=2` → boot logs carry the loud `WARNING: DORA_WEB_CONCURRENCY>1 duplicates scheduled jobs` line (don't run a self-host instance this way).
- [ ] Restart-cleanliness: `docker compose restart` → gunicorn comes back up, migrations run once, no port bind race with nginx.

### Dev seed runs under load by default — origin FU-388 (2026-07-14)
*The dev seed now appends ~500 bulk "load" stock items (+ products/offers, history, ~62 recipes, a big shopping list) so every interactive session runs loaded. Env-gated via `DORA_SEED_BULK_ITEMS`; the e2e suite passes 0. Quick eyes-on to confirm it seeds and the app stays usable under load.*
- [ ] Boot a dev instance with `DORA_ALLOW_DESTRUCTIVE=true` (default `DORA_SEED_BULK_ITEMS`) → Stock overview shows ~521 items ("Load item 0000 · …" through ~0499) alongside the curated fixtures; the page renders + filters without hanging.
- [ ] Dashboard, Locations heatmap, Cookbook (with ~68 recipes), and a big shopping list ("Big load list") all render under the load — note anything that feels slow (that's the FU-388 sweep's input).
- [ ] Boot with `DORA_SEED_BULK_ITEMS=0` → back to the ~22 curated items only (no "Load item …" rows), for when you want a light DB.
- [ ] `DORA_SEED_BULK_ITEMS=2000` → seeds the larger set without erroring (upper-bound sanity).

### Playwright browser-E2E smoke — CI / cross-OS re-run — origin FU-540
- [x] First run GREEN on this Windows dev box (2026-07-12, driving system Chrome via `DORA_E2E_CHANNEL=chrome` since the bundled binary won't download here) — 9 tests: login good/bad creds + authed nav over dashboard/stock/cookbook/meal-plans/shopping-lists + a real /api handshake. Selectors confirmed against the running app.
- [ ] Re-run in CI (bundled Chromium, `DORA_E2E_CHANNEL` unset) once CI is un-commented (FU-405), and on Linux, to confirm cross-OS. (Complements, does not replace, the manual walks below.)

### Fresh-install migration boot — origin FU-549 (FIXED 2026-07-13 — confirm on a clean install)
- [ ] On a machine with a clean `pip install -r requirements.txt` (now pins `alembic==1.14.1`), point at an **empty** database and boot in production mode (the path that runs `flask_migrate.upgrade()`, not the create_all seed path) → the app migrates cleanly to head and starts, **no** `a3e9f6c2d8b4` Alembic batch `'BINARY' has no attribute 'name'` crash. The crash was fixed 2026-07-13 (batch renames now pass `sa.BINARY(16)` instead of `UUIDType()`) and is now covered by `tests/test_migrations.py::test__migrations__upgrade_head_from_empty_succeeds` — this is the eyes-on-the-running-thing confirmation on the real prod toolchain.

### Companion push round-trip after `merchant`→`store` field fix — origin FU-554 (FIXED 2026-07-13)
- [ ] With both services standing, push a scraped offer from the companion (`dora-companion` — single-push button or batch-push toolbar) → Dora accepts it (no `400 unexpected key 'merchant'` from `_ProductIn`'s `extra="forbid"`); the product lands / quarantines as `store_not_mapped` rather than schema-rejecting. The payload field was renamed `merchant`→`store` in `companion_common/dora_ingest.py::build_payload` to match Dora's Phase-E `_ProductIn`. If both services are up, also re-run `dora-companion/tests/test_integration_dora_roundtrip.py` (needs a live Dora).

### Demo / sellable-showcase mode — origin FU-392 (shipped 2026-07-13)
- [ ] Boot the API with `DORA_DEMO_MODE=true` (any profile) → on boot the DB is wiped + re-seeded from the curated showcase dataset (`seed_showcase.py`), NOT the dev fixture: no "Sriracha (chatty history test)" item, no real personal email, clean pantry/recipes/meal-plan/shopping story. Log in as `demo` / `demo` (admin).
- [ ] With demo mode on, the SPA shows the persistent floating **"Demo mode — this is sample data that resets periodically."** pill (bottom-centre, brand-accent) on every screen, pre-auth and post-auth. It does not reflow layout or cover the mobile bottom nav.
- [ ] Boot **without** `DORA_DEMO_MODE` (normal install) → **no** demo banner anywhere; `GET /api/auth/capabilities` returns `demo_mode:false`; the normal dev-seed / prod-upgrade boot path runs unchanged.
- [ ] Leave demo mode running with default `DORA_DEMO_RESET_MINUTES` (60) — or set it low (e.g. `2`) to test faster — make a visible change (tick a shopping-list line, delete a stock item), wait for the interval, reload → the dataset is back to its curated baseline (scheduled `reset_showcase` fired).
- [ ] Boot with `DORA_DEMO_MODE=true` + `DORA_DEMO_RESET_MINUTES=0` → showcase seeds once on boot but the scheduled reset job is NOT registered (static demo); changes persist until the next manual restart.

### Prod-mode secure-cookies boot warning — origin FU-460
- [ ] Boot the app with `DORA_ENV=production` set and `DORA_SECURE_COOKIES` **unset** → stderr shows the multi-line `═══ WARNING: DORA_ENV=production but DORA_SECURE_COOKIES is unset. ═══` banner before the DI-container / DB / audit log lines
- [ ] Same boot with `DORA_SECURE_COOKIES=true` set → **no** warning banner in stderr
- [ ] Same boot with `DORA_SECURE_COOKIES=false` set → **no** warning banner (explicit operator choice)
- [ ] Same boot with `DORA_SECURE_COOKIES` unset but `DORA_SKIP_PROD_VALIDATION=true` set → **no** warning banner (escape hatch works)
- [ ] Boot with `DORA_ENV=development` (or unset) and no `DORA_SECURE_COOKIES` → **no** warning banner (dev mode never nags)
- [ ] With `DORA_ENV=production` + `DORA_SECURE_COOKIES=true`, log in to the SPA over HTTPS → DevTools → Application → Cookies → `dora_session` row shows `Secure: ✓`
- [ ] Same setup but with `DORA_SECURE_COOKIES=false` (or unset) → `dora_session` row shows `Secure: ✗`

---

## Cross-cutting

### Product Search entry points — FU-581 (nav-present-when-unset→Features verified live 2026-07-26)
- [ ] Set a URL on Features → nav Product Search entry becomes an external new-tab link (open_in_new); products off → entry hidden.
- [ ] CTAs route right (unset→Features, set→companion), no 404: stock-detail "Find & link a product"; My Products empty-state + orphan search; Dashboard "Hunt for deals →"; Dora "Find cheaper alternatives" / "Hunt for fresh deals".

### Main menu bar bottom border removed — origin FU-363 item 6 (2026-07-15)
*Subjective micro-polish — trivially revertible (re-add `bordered` to the `q-header` in `MainLayout.vue`) if it reads worse.*
- [ ] On desktop, the app header/main-menu bar no longer has a hairline bottom border; it still reads as a distinct bar from the page below (the toolbar background separates it). Check in both light and Pesto-dark themes.
- [ ] On mobile, the left side drawer still has its border (only the top header border was removed).

### Support / "Report an issue" channel — origin FU-370 (2026-07-14)
*Shipped **dormant**: with no channel configured (`support_channel.py` constants blank + no `DORA_SUPPORT_*` env) nothing new should render. Verify both states — dormant, then configured (easiest: boot the API with `DORA_SUPPORT_URL=https://example.com/new?template=bug_report.yml`, or `DORA_SUPPORT_EMAIL=you@example.com` to check the mailto path).*
*(Server contract confirmed 2026-07-20 by a once-off in-process check: dormant default → `GET /api/health` `support: {url:'', email:''}` (client self-gates → no button); `DORA_SUPPORT_URL` set → resolver returns it with URL winning over a set email; `DORA_SUPPORT_EMAIL`-only → `{url:'', email:…}` (mailto path). So the `/health` value that drives every button below is verified — the remaining bullets are just the **UI renders** for each state, which stay owner-walk.)*
- [ ] **Dormant (default):** Help page header shows **no** "Report an issue" button; the About tab reads the honest one-person copy ending "…pass it to whoever runs this Dora instance"; DoraBot "this is broken" reply points at Help with no external link; a forced full-page error shows no "Report this" button
- [ ] **With `DORA_SUPPORT_URL` set:** Help header shows a **Report an issue** button that opens the URL in a new tab with `?title=…&body=…` appended (and the existing `?template=` preserved via `&`); About tab's last paragraph now points at "the **Report an issue** button at the top of this page"
- [ ] DoraBot: type "something's broken" → the reply offers a **Report it** button that opens the same URL in a new tab
- [ ] Force a page error (e.g. break a route) → the error screen's **Report this** button opens the channel pre-filled with the screen/path/reference/error message
- [ ] **With only `DORA_SUPPORT_EMAIL` set (URL blank):** all the above open a `mailto:` link with a pre-filled subject/body instead of a URL
- [ ] Non-admin user sees the button too (the channel comes from `/api/health`, not an admin-only setting)

### Text-scale follow-through into component-internal text — origin FU-025 (2026-07-10)
*Fix landed via `quasar.variables.scss` rem-overrides (Quasar's `body { font-size: 14px }` and ~30 component vars) plus `.q-field__bottom` / `.q-bar--dense` rescues in `app.scss`. Walk one form-heavy page and one table-heavy page at both Small and Extra-large in Settings → Appearance → Text size, and confirm the previously-unresponsive text now moves.*
- [ ] Settings → Appearance → **Text size = Small** — cold-load Stock overview: level dropdown value, chip labels ("Needs attention", "Essential", "Open / in-use", "Needs check"), row text, footer counters all render smaller than default
- [ ] Same page, **Text size = Extra-large** — every one of the above renders larger; nothing gets stuck at the default 14px
- [ ] Open Recipe edit (any recipe → Edit): **input labels, field-native text, `.q-field__bottom` helper/error text, dense-field bottom text, toggle labels ("Enable this recipe", etc.), checkbox labels, chip inputs (tags / dietary), button labels ("Save", "Cancel"), the toolbar title** all track the pref at Small and XL
- [ ] Stock item detail: same test — labels, values, dropdown text, `Buy verdict` badge + card headline all scale
- [ ] Dashboard: `DoraScoreCard` hero number, trend badge, per-component captions all scale (they were px-hardcoded)
- [ ] Cookbook overview `FilterBar`: filter chip labels, dropdown labels (Cuisine / Category / etc.), sort dropdown all scale
- [ ] Shopping list detail: line item text, quantity/unit inputs, totals footer all scale
- [ ] Cook mode: step text scales (this was already fine via rem)
- [ ] **Icons stay put.** Quasar's `q-icon`, tab icons, avatar/checkbox/radio glyphs, meal-plan slot icons, decorative Onboarding letters, camera scanner UI, price-history chart labels, dashboard 3px/7.5px micro-gauge — **do not** scale with the pref. This is intentional.

### R-029 hide-don't-nag sweep — Product Search nav entry — origin FU-500 (2026-07-08)
*The one behavioural change from the R-029 sweep: when `features.products` is on but no `product_search_url` is configured, the Product Search entry disappears from the nav instead of rendering disabled-with-tooltip. Quick eye-check to confirm the three states.*
*(Verified live 2026-07-20 (browser drive): seed state is products-on + url-blank, and the main nav renders Stock / My Products / Cookbook / Meal plans / Shopping lists / Reports with **no Product Search entry** and no disabled tooltip — the R-029 "hide, don't nag" behaviour. The products-off and valid-URL states below need a Settings toggle to walk.)*
- [ ] With **products off** in Settings → System → Features → Products: no Product Search entry in the main navigation (unchanged behaviour)
- [ ] With **products on** and a **valid URL** configured: Product Search entry visible, clicking opens the URL in a new tab (unchanged behaviour)
- [ ] Side menu (narrow viewport) mirrors the above: entry appears/disappears in lockstep with the main menu
- [ ] Confirm no other surface still advertises "Product search not set up" — should be silent everywhere except the config row on Settings → System → Features

### Base-component `<BaseButton>` sweep — origin FU-504 (2026-07-08)
*40 raw `<q-btn>` sites were migrated to `<BaseButton>` in one pass; `BaseButton` also gained a new `filled-icon` variant + optional `color` prop. Pure componentisation refactor — visuals should be identical everywhere except MyProductsPage's empty-state CTA (raised → unelevated primary, intentional). Cheap eye-check per surface, no action beyond looking.*
- [ ] **RecipeCard chef-hat button** (cookbook overview, any recipe card) — round filled icon, colour toggles primary/warning based on cookability; click still opens cook mode
- [ ] **DoraChat** — open the assistant panel: header voice / help-what-can-D.O.R.A.-do / close buttons render as round icon buttons; mic + send buttons in the input; chip-row rotate-suggestions button; in-message action rows (Confirm / Cancel / Snooze 1d / Dismiss / Add to <list>) render identically
- [ ] **MyProductsPage** — open the page: bulk-select mode banner buttons (Select / Select all visible / Select on-deal / Add on-deal to list / Unlink / Mark inactive / Done) render + wire; row-overflow menus (`⋮`) still open; empty-state "Open Product Search" CTA is now unelevated primary (visual delta from raised to unelevated is expected); dialog action rows in the "unlink" and "mark inactive" confirmations
- [ ] **ScanOverlay** — trigger the scanner (Stock overview → scan button, if scanning enabled): the Submit button in the overlay renders on the dark background
- [ ] **Settings pages** — Backup & restore (clear-file button), Data import (browse button), Email settings (Save + Clear buttons), Push settings (Test push + Clear subscription), API access (copy token button), Users admin (copy invite-link button) — all render + still wire
- [ ] **Kept-raw carve-outs render unchanged** — Help page "Meet D.O.R.A." accent CTA + release-notes anchor; RecipeCookMode warning-coloured pause button; ShoppingListDetail dynamic-coloured outline buttons; StocktakeRunner change-level big button; Backup/restore grey button; timezone + locale settings secondary-outline buttons

### Security response headers — origin FU-459 (2026-07-07)
*Confirms the app-wide CSP + framing / referrer / sniff headers land on every response and don't break any page. Do this walk with DevTools **Console + Network** panels open — a CSP violation logs a red console error naming the blocked directive.*
*(Header **presence + values** pinned 2026-07-20 in `tests/e2e/dora_api/test_security_headers.py`: all four headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer-when-downgrade`, CSP with `default-src 'self'` / `frame-ancestors 'none'` / `img-src … data: blob: https:` / `base-uri` / `form-action`) land on a 200, a 404, AND a domain-error response. The `curl -I` operator check and the browser CSP-violation walk below stay owner-walk.)*
- [ ] Cold-load the SPA → no CSP violations in Console
- [ ] Walk Dashboard, Stock overview, Stock item detail, Cookbook overview, Recipe detail (with an image), Cook mode, Meal plans, Shopping list detail, Settings → each page renders normally, no red CSP errors on any surface
- [ ] Recipe / product / store images render (base64 `data:` blobs + external `https:` sources both work under `img-src`)
- [ ] Upload a recipe/user image (data-URL / blob path) → preview renders (blob: is allowed)
- [ ] Print view opens and renders (if any style-src / script-src violation would clobber it, it'd be visible here)
- [ ] Piper TTS synthesis + assistant chat still work end-to-end (connect-src covers the `/api` calls; anything to an external LLM URL relies on `https:` allowance)

### Recipe-picker inline-create toast — origin FU-319 (2026-07-06)
- [ ] Open any recipe in the cookbook, edit ingredients, add a new ingredient row → type a name that doesn't match any existing stock item → tap the "Create '<typed>'" no-option row in the picker → **positive toast reads `Added "<name>" to your pantry.`** (not the old "Created stock item …" copy)
- [ ] After the toast, navigate to Stock overview → the new item is there with the shipping-default level (top of the levels list). Confirms the toast reflects reality.

### Help chips (FU-503 / FU-044) — 2026-07-06
*Walk the surfaces in `docs/04_proposals/IMPL_PLAN_HELP_CHIPS.md`. For each
one: hover the `(?)` icon on desktop and long-press on mobile. Confirm the
tooltip renders (not clipped), and the copy reads correctly.*
- [ ] Dashboard: Kitchen health card title, You've saved card title
- [ ] Reports: Year-over-year card title, Meals-worth metric in Meals cooked card
- [ ] Alerts: header "N need action · M FYI" tooltip; per-kind tier segmented control in the Manage panel
- [ ] Meal plans: Shortfall / cook-by chip in the week status *(FU-304 closed 2026-07-07: Board page retired; the chip lives on `MealPlansOverview` only.)*
- [ ] Recipe detail: "N unallocated of M cooked" caption in the Available meals card
- [ ] Cookbook overview: Cookable now filter chip has a `(?)` beside it explaining the distinction from "Have meals in pool"
- [ ] Cook mode: Sous Chef button tooltip now includes the fuller explanation; hands-free mic tooltip explains it's independent of narration
- [ ] Stock overview: `(?)` beside Essential, Will auto-add on low, Open / in-use, Needs check filter chips
- [ ] Stocktake runner: cadence subline ("Checked every X · Y days overdue") has a `(?)`; Push 3 days button tooltip renders
- [ ] Shopping list detail: Finish & restock button tooltip; Plan-which-day button tooltip renders the extended copy
- [ ] Price history: "currently X% above" has a `(?)`; "Your usual" caption has a `(?)`
- [ ] My products: Select on-deal button tooltip
- [ ] Any product row's PriceEntry (multipack disclosure): "Add pack count (multipack)" ghost button tooltip
- [ ] Notifications settings: Compact format help text now reads "One line per deal (item, price, store). Off = expanded card…"
- [ ] Assistant settings: Enable AI mode description reads "Off keeps every chat reply rule-based. On routes *tool-able requests* through your configured provider — requests that need real actions…"
- [ ] Dark mode + all themes: `(?)` icon inherits colour from parent context (R-002); no hardcoded colour bleeds through
- [ ] Mobile viewport: tooltips are readable at 360px (may need to reflow); long-press activates them

### iOS / macOS-WKWebView audio-unlock primer — origin FU-287
*Needs iPhone / iPad (Safari) or the macOS desktop bundle (WKWebView).
User doesn't have iOS device access as of 2026-07-03 — sits until then.
Every other platform: no visible effect; already worked.*
- [ ] iOS Safari, `speechEnabled` on, `voice_engine=piper`: open Dora chat → type a message → tap send → **Dora's reply plays audibly** (this is the flow that used to lose the gesture credit across the LLM `await` + synth fetch)
- [ ] Same setup, `voice_engine=browser`: reply plays via browser SpeechSynthesis (browser voice was more forgiving but subject to the same gate; primer helps here too)
- [ ] Cook mode on iOS Safari: **start the app, tap around a bit (any interaction), then enter cook mode → "next step" narration plays** — no gesture is needed on the "next" tap itself; the session-level primer covers subsequent voice narration
- [ ] Timer-narration edge case (documented, best-effort): start a timer in cook mode, leave the tab open several minutes without interacting → timer completes → **visible Notify still fires** (load-bearing signal); audio narration + finish tone may or may not — do not treat their absence as a regression
- [ ] macOS desktop bundle (WKWebView): same three checks as iOS — chat reply, cook-mode step narration, in-session timer narration
- [ ] Android Chrome + desktop Chrome/Firefox: **no regression** — voice output still works, nothing sounds different. First-gesture briefly plays a silent muted `data:audio/wav` primer (44 bytes); should be inaudible and invisible in DevTools' network tab
- [ ] Reload the page → primer fires again on the next gesture (session-scoped, not persisted)

### Filters button toolbar alignment (R-027 fix, 2026-07-02)
- [ ] `/stock` — the Filters button (right end of the top toolbar row) sits **flush** with New item / Scan / Stocktake / Bulk select / Export. Zoom in if needed: their tops + bottoms line up pixel-for-pixel
- [ ] `/stock` — when a filter is active, the **Clear** button appears to the left of Filters and BOTH sit flush with the other toolbar buttons (Clear didn't have this bug before either, but verify it's still aligned after the multi-root refactor)
- [ ] `/products` — Filters + Clear flush with Toolbar's other actions
- [ ] `/cookbook` — Filters + Clear flush with the recipe toolbar's other actions
- [ ] Toggling filters on/off doesn't shift any neighbouring button horizontally (FU-121 stability preserved)
- [ ] Active-count badge on the Filters button still renders (floating primary badge) when filters are engaged

### C-19 shared auth-shell + AuthButton (2026-07-02)
- [ ] Cold-load the app on slow-3G throttle. `#pre-mount-splash` paints midnight `#1f2647` immediately; when Vue mounts and `AuthShell` takes over, there is **no** light→midnight flash. One unified moment
- [ ] Splash pulse: the mascot logo pulses at 60fps while `authStore` bootstraps; blobs are visibly present but motion-frozen (D2 `backdrop="quiet"`) — no CPU cost
- [ ] Cannot-connect variant: kill the API (stop `dora_api`), reload. Splash shows the offline mascot + "Can't reach Dora's brain" + the retry button. Retry button matches the login-primary teal gradient
- [ ] `/login` — primary Sign In button is pixel-identical to pre-migration (teal gradient, hover lifts, shadow bump)
- [ ] `/login` — "Need an account? Register" now renders as a **full-width amber-gradient button** at the same size as Sign In (was: tiny ghost text). Toggle click still swaps the form mode
- [ ] `/login` — "Forgot password?" now renders as a **full-width ghost button** at the same size (was: fine-print router-link). Click routes to `/forgot-password`
- [ ] `/login` register mode: password-policy fineprint ("Passwords must be at least 10 characters…") still shows under the form
- [ ] Register with bad credentials → the field-level error still surfaces (regression check on `useFormErrors` plumbing)
- [ ] Login with wrong password → generic "Sign-in failed. Check your username and password." error surfaces (the 401-opaque path still works)
- [ ] `/setup` (bounce a fresh install with `admin_user_present=false` or hit the route while logged out on a bootstrap install) — visual should be **identical** to pre-migration. One-time-setup badge sits above the title; Create admin button is teal-gradient primary
- [ ] `/forgot-password` — canvas matches Login (blobs, mascot NOT shown, frosted card). "Send reset link" primary; "Back to sign in" ghost. Success banner (submit any email) still renders. Feedback L16 satisfied
- [ ] `/reset-password` — with a token: card shows the two password inputs + primary "Reset password" + ghost "Cancel". With no token: banner "This reset link is missing a token" + ghost "Cancel". After success: positive banner + primary "Continue to sign in"
- [ ] `/verify-email?token=<good>` — success card renders with green tick + "Continue to sign in" primary. `?token=<bad>` — error card renders with "Resend verification" ghost. Click it → BaseDialog opens; submit any email → toast + dialog closes
- [ ] `/confirm-email-change?token=<x>` — pending → success/error card renders; "Continue" primary routes to `/`
- [ ] `git grep '\.auth-shell\b' web_app/src/` returns zero from a fresh clone (no aux page still declares the class locally)
- [ ] `/welcome` (onboarding wizard) — canvas now shows the midnight blobs behind the wizard cards. Header ("Dashy Dora" title + mascot avatar + Sign out) is legible over midnight (white text on midnight). Sign out button still tappable and logs you out
- [ ] `/welcome` onboarding scenes — Scene 1 (scatter icons) legible on midnight, question-mark glyph reads amber. Scene 3 (brain mascot) centred + visible. Scene 4 (persona pills) pills readable (frosted-glass background)
- [ ] Reduced-motion (toggle OS setting or DevTools emulation) on `/login`: blobs and mascot freeze in place; card enter animation off; button hover no longer translates
- [ ] Mobile viewport (~360px) on `/login` and `/setup` — mascot shrinks to 72px, tucks above the card (not fighting card overlap)
- [ ] Password policy note under register mode still readable inside the card foot area

### P8-01 rename: no stray "Discount Dora" anywhere user-facing (2026-07-01)
*(Verified 2026-07-23: zero "Discount Dora" in FE+BE source or DOM; tab titles/mascot alt/About/version-replies all "Dashy Dora". Only the PWA-install app-name below → device.)*
- [ ] PWA install prompt (Chrome address bar → install app) shows "Dashy Dora" as the app name (from productName in package.json)

### D.O.R.A. bot rename + acronym easter egg (2026-07-01)
*(Verified 2026-07-23: D.O.R.A. chat-header label renders live; acronym tooltip + "Meet D.O.R.A." Help button + `/help/dora` copy source-confirmed. Only the Thanks-chip below → owner-walk.)*
- [ ] Chat suggestion chips include "Thanks D.O.R.A." (not "Thanks DoraBot"). Clicking it replies with the sparkle/thanks flow the old chip triggered

### Nav-state policy: filters survive navigate-back, reset on reload (A8 §3, 2026-07-01)
- [ ] Stock Overview: type in the search box, tick a couple of filter chips, change the sort. Click into any stock item detail → hit browser back → search text, chip states, and sort are all preserved. Scroll position on Stock Overview is restored too
- [ ] Cookbook: same drill — set search, toggle favourites-only + cookable-now-only, change sort axis + direction. Navigate to a recipe → back → all preserved, including expanding/dietary/tools filters
- [ ] My Products: set search text + a store filter + the "On deal only" chip. Navigate to another route (Dashboard) → back → preserved
- [ ] Hit F5 (full reload) on any of those three pages → all filters reset to defaults, scroll to top. This is the intended "clean slate" behaviour
- [ ] Sign out and sign back in as the same user → filters reset (sign-out flow currently does a full reload; if it doesn't in future, FU-355 will wire an explicit clear)
- [ ] Other list pages (MealPlans, ShoppingLists, Stocktake, admin settings) still reset on nav-back — they haven't been migrated yet (FU-354). That's expected, not a bug

### `/data/barcodes` redirects + shell shows two cards — origin FU-340 (2026-07-01)
*(Verified 2026-07-23: `/data/barcodes` (+`?action=scan`) → qr-labels. The "two cards" shell is gone — FU-341 relocated `/data/*` under `/settings/admin/data` (`#/data` → backup). Only the tooltip below → owner-walk.)*
- [ ] Stock item detail page: the "Print label" tooltip on a stock item's Dora-QR button no longer references "Data → Barcodes" — the copy explains barcodes register a Product, not a stock item

### `/data/export` page retired — origin FU-339 (2026-07-01)
*(Verified 2026-07-23: `/data/export` + `/data` → `/settings/admin/data/backup` (FU-341 relocation; a clean redirect, not a 404 — retirement intent met). Print-still-works bullets below → owner-walk.)*
- [ ] From a recipe detail: the Print action still opens the print-view in a new tab (unchanged)
- [ ] From a shopping list detail: the toolbar menu still exposes "Print / Save as PDF" (unchanged)
- [ ] From `/stock`: the toolbar export menu still exposes CSV + Print (unchanged)
- [ ] From `/meal-plans`: the Print icon-button added in FU-338 still opens the print-view (unchanged). *(FU-304 closed 2026-07-07: `/meal-plans/board` retired; nothing to check on the old Board page.)*
- [ ] No console errors on any of the above about a missing route or a missing component

### Settings shell — independent sidebar/main scroll — origin worklog 2026-07-01- [ ] Scroll the main pane deep into a long settings page (e.g. Preferences) — the sidebar stays exactly where it is (no drift, no sticky-header jitter)
- [ ] Scroll deep into the main pane, then click a sidebar nav item → **the window does NOT jump**. The new section loads with the main pane at the top; the sidebar's scroll position and the app header stay put
- [ ] With a very long sidebar (admin users, expand Kitchen setup + Admin sub-groups) — the sidebar itself scrolls independently; the last nav item is reachable via that inner scroll
- [ ] Resize the window to <1024px → the layout collapses to single-column with the top tab strip; window scroll returns for mobile. Resize back to ≥1024px → dual-scroll restored, no layout thrash
- [ ] Navigate from `/settings/*` to a non-settings route (e.g. `/stock`) and back — no visual glitches; scroll positions on other pages behave normally (window scroll back on those pages)

### Mobile header: wordmark hidden, right buttons pushed to edge (2026-07-01)
- [ ] At ~380px width (or DevTools mobile viewport), the top toolbar reads left → right: burger · Dora mascot · page title · (big gap) · alerts bell · profile avatar. **No** "Dashy Dora" text next to the mascot, **no** Help icon
- [ ] Tap the mascot → routes to `/` (Dashboard). Tap the burger → drawer opens with the full nav (Stock, Cookbook, …)
- [ ] Rotate to landscape / resize past ~1024px width → wordmark reappears next to the mascot, MainMenuButtonStrip fills the middle, Help icon reappears between alerts and profile
- [ ] No horizontal scroll or overflow on the toolbar at 320px, 375px, 414px widths

### Main-menu indicator stuck colour after sub-route nav — bug fix (2026-06-30)
- [ ] On `/cookbook` → click into a recipe → the underline indicator under Cookbook stays the **accent** colour (yellow in the default theme), **not** the hot-pink flash colour
- [ ] Same check for: `/stock` → click into a stock item; `/shopping-lists` → click into a list; `/settings/account` → switch tabs within Settings
- [ ] On any of the above pages, navigate to a different top-level (e.g. Cookbook → Stock) and back — flash colour briefly appears during the slide, then settles to accent on the new active button each time
- [ ] No regression to the slide animation when clicking between top-level buttons — the indicator still slides smoothly across with the flash colour during the transition

### Header peer buttons (Help + Account) with active ring — feature (2026-07-01)
*(Verified 2026-07-23: Help/avatar nav + no dropdown chevron (avatar tooltip is "Account settings"). Ring pulse/fade + theme bullets below → V-pack.)*
- [ ] No Sign-out anywhere in the app toolbar (MainLayout) — Sign-out now lives in the Settings shell page header (see below), not on the Account page anymore
- [ ] On `/help` or `/help/dora`: **Help icon pulses** in the slide-flash colour, then settles into the 3px accent ring. Avatar stays inactive (no ring)
- [ ] On any `/settings/*` page: **avatar pulses + settles** to the accent ring. Help icon stays inactive
- [ ] Switching between Settings sub-pages (`/settings/account` → `/settings/preferences` → `/settings/notifications`) — avatar ring stays lit, **no re-pulse**
- [ ] Switching between `/help` and `/help/dora` — Help ring stays lit, **no re-pulse**
- [ ] Cross between sections (`/settings/account` → `/help`): avatar ring fades out (~320ms), Help ring pulses + settles. Reverse direction also smooth
- [ ] Navigating between Help/Settings and the main menu (e.g. `/help` → `/cookbook`): header ring fades out, main-menu Cookbook underline fades in. No stuck flash colour
- [ ] Theme switch — both buttons' flash + resting colours follow the active theme's `--nav-slide-flash` + `--brand-accent` tokens

### Sign-out moved into the Settings shell header (2026-07-13)
- [ ] On any `/settings/*` page: a **"Sign out"** button (logout icon, danger-ghost styling) sits on the **right** of the shell header, inline with the Settings/Admin toggle (admins) or the "Settings" title (non-admins)
- [ ] Click it → you're signed out and land on `/login`; the button shows its loading state while the request is in flight
- [ ] Settings → Account no longer has a "Sign out" section/card at the bottom (it moved to the header)
- [ ] Both admin (toggle shown) and non-admin (plain title) accounts show the button correctly right-aligned; no overlap/wrap at narrow desktop widths, and it still renders on the mobile settings layout
- [ ] Mobile (`<md`): both buttons render in the header (next to the AlertsBell), rings still work
- [ ] **Reduced-motion** (DevTools → Rendering → "Emulate CSS prefers-reduced-motion: reduce"): rings appear in the resting accent colour **without** the pulse beat on either button

### R-016 lazy hydration sweep — five pages — origin FU-221
*(Verified 2026-07-23 (XHR-instrumented nav sweep): stock-items + recipe list fire once, 0 on revisit. Post-mutation refresh bullet below → owner-walk.)*
- [ ] Post-mutation refresh paths still work (e.g. create a stock item → list updates; rename one → name updates) — those still call the raw `getXAsync()` and must not have been broken by the sweep

### R-016 extension to recipe / shoppingList / location / recipeVocab / mealSlot stores- [ ] Recipe create / edit / delete still refreshes the overview (post-mutation calls `recipeStore.getRecipesAsync()` directly — must keep working)
- [ ] Shopping-list mutations (add line, finish shopping, remove from list) still refresh summaries (post-mutation calls `shoppingListStore.refreshAsync()` — must keep working)
- [ ] Location CRUD on settings → Stock Locations still refreshes the tree (post-mutation calls `locationStore.refreshAsync()` — must keep working)
- [ ] QuickAddSheet open → shopping-list summaries appear; CreateStockItemDialog open → location picker has options
- [ ] DoraChat: ask a recipe-aware question on a cold session — recipes + vocab populate before the answer; ask again on a warm session — no second fetch

### Drag-and-drop affordance parity (post `useDragDropList` refactor) — origin FU-326
*(Class parity verified 2026-07-23: shopping lines + recipe ingredients both use `.dora-dnd-row`/`.dora-dnd-handle` (old per-surface classes gone). The drag interaction below → owner-walk.)*
- [ ] **Shopping list lines** (`/shopping-lists/<id>`): on a list that's not done and not mid-shopping with no grouping active and bulk mode off, grab any row → source row dims to ~50% opacity, drop-target row lights with a primary-coloured outline ring. Drop reorders, server persists, refresh round-trips
- [ ] **Shopping list — reorder gates**: list is `done` → no drag (cursor stays default; can't pick up). List `shopping` → no drag. Activate grouping → no drag. Enter bulk mode → no drag. Return to "active draft, no grouping, no bulk" → drag resumes
- [ ] **Recipe steps** (recipe edit, Structured mode): grab a top-level step → source dims, drop-target ring lights; drop within sibling group reorders. Try to drop a top-step onto a sub-step (different parent) → no drop accepted (no ring on dragover). Top-steps still can't become sub-steps via drag (intentional — that's the separate sub-step affordance)
- [ ] **Recipe ingredients** (recipe edit, "Ingredients" card): grab a row → dim + drop ring exactly the same shape and colour as the two surfaces above. Within same section reorders; across sections also moves the row and copies the target's section assignment
- [ ] **Visual identity check**: side-by-side, the three surfaces use the same opacity, same ring colour, same ring thickness, same handle hover treatment. Open browser devtools → both surfaces apply `.dora-dnd-row` / `--dragging` / `--drop-over` classes (not `shopping-line-dragging` / `recipe-step-row--dragging` / `ingredient-row--dragging`)
- [ ] **Cross-list isolation**: start dragging a shopping line, hover over the recipe editor's ingredient list (in a second tab won't work — single-tab check). Start a recipe-step drag while in the recipe-steps editor → only steps light up, never ingredients (because the MIME is distinct per list)

### Error-handling rollout — origin FU-099-V
- [ ] **Friendly translation** — submit a recipe with `servings = "abc"` → inline `error-message` on Servings reads "Must be a whole number." (not "Input should be a valid integer..."); toast caption is the generic "Couldn't save — check the highlighted fields." with `· ref: <8-char>` suffix
- [ ] **Domain error** — create a stock item with a name that already exists → toast caption shows the friendly domain message + ref suffix
- [ ] **5xx path** — induce a 500 (e.g. stop API mid-save) → existing global toast still fires with "ref: <8-char>" (no regression)
- [ ] **Network drop** — kill the API → "Can't reach the server…" caption renders; no `ref:` suffix
- [ ] **Dev visibility** — DevTools: every failed API call (400/401/403/404/422/5xx) shows `[api] METHOD path → status code (correlation-id)` with structured `details` blob
- [ ] **Unknown Pydantic code** — induce one (custom validator raising non-standard error) → toast reads "This value isn't valid."; DevTools shows `raw` + `code` so a dev can add it to `PYDANTIC_FRIENDLY`

### `formatQuantity` rollout — origin FU-321- [ ] Meal-plan "This week's shopping" — `unit="g"` reads `"needs 250g · …"`; `unit="tbsp"` reads `"needs 1 tbsp · …"`; null unit reads just the quantity
- [ ] Sequential Builder Dialog preview list — same three cases; rounded number is what `formatQuantity` receives
- [ ] Substitute ratio caption on stock-item detail: `1 tbsp → 3 tsp` reads exactly that (both halves spaced); direction "this → that"
- [ ] Substitute ratio caption in cook-mode swap picker: same ratio reads identically. `250 g → 1 cup` reads `"250g → 1 cup"` (asymmetric — mass tight, volume spaced)
- [ ] Recipe print view (window.open from RecipeDetailPage export): `2 tbsp olive oil` → `"olive oil — 2 tbsp"`; `250 g flour` → `"flour — 250g"`; `1 onion` (no unit) → `"onion — 1"`; `salt` (both null) → just the name, no em-dash

### Unsaved-changes guard rollout — origin FU-322- [ ] **AccountSettings** — edit `usernameDraft`, click a sidebar link → confirm dialog. Cancel → still on page. Confirm → nav completes. Repeat for `emailDraft`. Revert draft → nav with no prompt
- [ ] **AccountSettings exclusions** — pick a new profile picture (saves immediately) then nav → no prompt. Type a new-password value (don't submit) then nav → no prompt
- [ ] **AdminSystemAssistantSettings** — flip `enabledDraft`, edit `baseUrlDraft`, edit `modelDraft` in any combination, then nav → prompt. Save → next nav passes through clean
- [ ] **beforeunload** — dirty page refresh → native "Leave site?" prompt. Clean page refresh → no prompt

### Chunks 3–5 client + DB-backed query paths — origin FU-051
- [ ] `npm install` + `npm run lint` + `quasar dev` boots cleanly
- [ ] Recipes overview: cookable filter + footer count + compare dialog
- [ ] Recipe card chip renders
- [ ] Recipe detail sidebar + editor "Missing" badge
- [ ] Meal-plans palette
- [ ] Dashboard "Cookable tonight" + count
- [ ] Dora's "what's missing" answers
- [ ] Dashboard primary-list stats + shopping-list detail headline totals (Chunk 5) — confirm $ remaining / savings / counts match what the lines imply
- [ ] Server: `GET /api/recipes?cookable=true|false`, `?max_missing=1`, `/api/dashboard/summary`, `GET /api/shopping-lists/<id>` (check `totals` block) against seeded data

### Cookbook C-cross Chunk 1 — feature-flag panel — origin FU-110
*(Verified 2026-07-23: Features panel renders 7 toggles (checklist's "5" is stale) with captions, every state matches `/api/health`. Persistence/non-admin/migration/theme bullets below → owner-walk.)*
- [ ] `alembic upgrade head` applies `a3b8e2f4c1d7` on SQLite + Postgres; `verify_mappings()` passes for reshaped `AppSetting`
- [ ] Each toggle on → toast + persists across reload
- [ ] Each toggle off → toast + persists
- [ ] As non-admin: panel renders "no admin permissions" banner; toggles not visible
- [ ] Composable freshness: `flagsLoaded.value` is `true`, computeds match panel; flipping in tab 1 only refreshes tab 1's cache (per-session, documented)
- [ ] Migration safety: install using meal planning sees `meal_planning_enabled=True` after migration
- [ ] Save error path: disable network / PATCH 500-out → toggle reverts + negative toast
- [ ] Pesto Light + Pesto Dark + Cherry Cola Dark — panel reads in all

### C-cross Chunk 2 — per-user money opt-in — origin FU-111
- [ ] `alembic upgrade head` applies `b5c1d9a4e3f2`; `verify_mappings()` passes for reshaped User
- [ ] As regular user: Settings → Account → new **Money & budgets** card appears above Grocery budget with toggle, off by default
- [ ] **Install ON, user OFF (default):** toggle enabled, Grocery budget hidden. Flip on → toast → Grocery budget appears → set budget + period → reload → toggle on, budget settings persisted
- [ ] **Toggle off again:** toast → Grocery budget hides → reload → toggle off, **but saved budget is still on server** (flip back on → same value)
- [ ] **Install OFF (admin disables in System → Features → Money):** per-user toggle disabled with caption "This install has money features turned off…"; Grocery budget stays hidden
- [ ] PATCH wire: flip sends `{ money_features_enabled: true|false }` only (DevTools)
- [ ] `GET /api/users/me` carries `money_features_enabled` in response
- [ ] Composable: `useMoneyEnabled().moneyEnabled.value` = `installEnabled && userEnabled`
- [ ] Error path: PATCH 500s → toggle reverts + negative toast
- [ ] Pesto Light + Dark + Cherry Cola Dark

### C-cross Chunk 3 — per-user nutrition mode + reserved seam — origin FU-112
- [ ] `alembic upgrade head` applies `c8d3f4a9b2e1`; `verify_mappings()` passes for reshaped User + AppSetting
- [ ] Settings → Account → **Nutrition** card: three-way toggle reads **Off** by default; captions read
- [ ] **Install OFF, user Off (default):** whole toggle disabled, caption "This install has nutrition turned off…"
- [ ] Admin enables `nutrition_enabled` in System → Features. Return to Account → Nutrition: Off + Simple now clickable, Complex disabled. Caption explains complex needs a source
- [ ] Flip to Simple → toast → reload → still Simple
- [ ] Flip back to Off → toast → reload → still Off
- [ ] Server rejects complex without seam: PATCH `{ nutrition_mode: 'complex' }` → 400 with "Complex nutrition mode needs a nutrition data source configured…"
- [ ] Configure the seam: admin PATCH `{ nutrition_db_source: 'usda-fdc' }` → `GET /api/health` reports `features.nutrition_complex_available: true`
- [ ] Refresh Settings: Complex now clickable. Pick it → toast → reload → still Complex
- [ ] Re-empty the seam: PATCH `nutrition_db_source: ''`. Refresh: user remains on Complex server-side (no auto-rewrite), but Complex option disabled + caption updates. User can switch back to Off/Simple
- [ ] PATCH wire: `{ nutrition_mode: '<mode>' }` only
- [ ] `/me` carries `nutrition_mode`
- [ ] Pesto Light + Dark + Cherry Cola Dark

### C-cross Chunk 5 — image-display opt-in + deferred image column — origin FU-114
- [ ] `alembic upgrade head` applies `d4a7c9b3e8f1`; `verify_mappings()` passes for reshaped User
- [ ] New user: `show_recipe_images` + `show_stock_images` both default **true**. Existing users post-migration same (server default `'1'`)
- [ ] Cookbook overview header has **image** icon button next to "Import from URL". Tooltip "Hide recipe photos · saved across sessions"
- [ ] Cards render photos as today
- [ ] Recipe detail with image → header preview shows photo
- [ ] **Click toggle:** icon flips to `image_not_supported`; toast "Recipe photos hidden."
- [ ] Cards now show coloured-initial placeholder; DevTools Network: `GET /api/recipes/<id>/image` is **NOT** called for visible cards
- [ ] Recipe detail (with image): header preview shows placeholder; **editor's pick/clear still work** — pick new image → preview shows freshly-picked image (dirty-form branch ignores opt-in). Save → reload → preview hides again (saved image gated)
- [ ] **Toggle back on:** toast "Recipe photos shown."; cards + detail show photos; saved images survived
- [ ] `/me` carries `show_recipe_images` + `show_stock_images` on every load. Toggle PATCH sends only `{ show_recipe_images: bool }`
- [ ] Cross-session persistence: flip toggle, sign out, sign back in → state remains. Second device → same
- [ ] **FU-090 perf fix:** load cookbook overview with N≥10 recipes that all have images. Payload substantially smaller (image bytes no longer in rows; only `has_image: bool`). Backend logs / `sqlalchemy.echo` show no `SELECT image FROM Recipe` on list path
- [ ] **Stock-side flag round-trips** even though no UI writes it yet (FU-106 will land C-1 row redesign): `PATCH /me` body `{ show_stock_images: false }` survives reload
- [ ] Pesto Light + Pesto Dark + Cherry Cola Dark — new icon button reads in all

---

## Cookbook — filter bar, sort control, expiry urgency (2026-08-19 batch)

- [ ] Clear the Ingredients filter's search box with the X — it must not blank the page (was a hard crash). Same for the search boxes on Price history, QR labels, and the stock-item Add-substitute dialog.
- [ ] Open the Ingredients filter on **pesto-dark** and confirm the selected Sort-by segment is readable (was green-on-green).
- [ ] Turn on "Uses expiring ingredients" and confirm ordering is by urgency — a recipe with 2 ingredients going off today must sit above one with 4 going off next week. Check the chip colour matches (red = expired, amber = within 7 days, grey = later) and the tooltip names the soonest date.
- [ ] Switch Cookbook to Compact and back: cards must show photos, compact must not. Confirm the old "Hide photos" toolbar button is gone and the equivalent now lives in Settings → Appearance → Recipe photos (which should only affect the recipe *page*).
- [ ] On an install with batch cooking **off**, confirm the "Meals prepared" chip, the "Meals prepared ≥" input and the "Meals prepared" sort axis are all absent; turn batch on and confirm they appear.
- [ ] Stock overview: the sort direction toggle now lives inside the Sort-by field. Confirm each axis flips (Name, Stock level, Last updated, Expiry) and that a sort saved before this change still restores sensibly.

## Dropdowns — menu vs dialog (2026-08-19, FU-675) — **needs a real phone**

The menu/dialog choice is user-agent based, so **resizing a desktop browser cannot show this**.

- [ ] On a phone, open Cookbook filters → **Difficulty**, **Cuisine**, **Category**, **Time of day**, **Collection**: each should open an ordinary dropdown attached to the field, NOT a full-screen panel.
- [ ] On a phone, Stock filters → **Any level** / **Any group** / **Sort by**: same, an attached dropdown.
- [ ] On a phone, Stock filters → **Any location** (typeahead): this one SHOULD still be the full-screen panel — confirm it now shows a title and a close (X), that the X dismisses it, and that **typing still filters the list** (this broke once and was fixed).

## Stock-item detail — buy verdict, first run (2026-08-19) — origin FU-684

The verdict has never actually worked (it answered `unsure/low` for every item);
the server half is now pinned by e2e, but nobody has seen the card render a real
answer.

- [ ] Open a stock item you are **out of** — the card reads **Buy**, not "Not sure",
      and the need reason is present.
- [ ] Open one Dora *infers* is out while its recorded level says stocked (needs a
      few logged shops) — the reason reads **"Probably out of stock"** with her
      cadence explanation beneath it, and the confidence is not "high".
- [ ] Turn "Should I buy this?" **off** under Settings → Assistant (per-user since
      Chunk 2) and confirm the card on the item page and the badge on a shopping
      list both disappear — the *toggle* itself was walked live on 2026-08-19
      (it writes the per-user field); what's unverified is the two surfaces
      reacting to it.


## Recipe page — the 2026-08-27 feedback batch
Most of this batch was driven live (see the worklog); what's left needs a real
device or a real file picker.

- [ ] Pick a photo for a **photo-step** recipe through the OS file picker — the
      native round-trip can't be agent-driven. Check the new photo appears in
      the grid **before** you save, and survives the save.
- [ ] Walk the recipe page on a **real phone**: the method heading wraps its
      step-style switch onto its own line at 375px, and the ingredient rows'
      cart button should be reachable with a thumb without hover.
- [ ] Open the **step links** dialog (the 🔗 on a step while editing) on a phone
      and confirm the ingredient/tool pickers behave — Quasar popups could not
      be rendered in the agent's pane ([[FU-737]]).
- [ ] Drag a step by its **number** to reorder it (the numeral is the drag
      handle now). Pointer devices only; ↑/↓ is the phone path.

## Recipe page — Health Star Rating
- [ ] Import a **real USDA dataset** (Settings → Admin → Nutrition) and confirm
      foods come back with a category — then check a genuinely vegetable-heavy
      recipe rates well and a rich one doesn't. The agent verified this against
      hand-seeded foods, not a real import.
- [ ] Press **Settings → Region → "Match this device"** on a machine that is
      *not* in AU/NZ and confirm the rating prompt does **not** appear.
- [ ] With the rating on but nutrition in **simple** mode, confirm the admin
      page's warning banner reads correctly and no stars appear anywhere.
