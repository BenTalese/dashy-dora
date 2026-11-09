# Changelog

All notable changes to Dashy Dora live here. Versions follow semver: a major
bump means a schema or configuration change you need to act on when upgrading.

## [Unreleased]

### Changed

- **Linked products and preferred buys work together.** An item with a linked product keeps its preferred buys,
  and the name menu on a list row, a template line or a recipe ingredient offers both. Picking one replaces
  the other.
- **The Products tab holds everything about what you buy.** Linked products, preferred buys and Your prices
  now sit together on the stock item's Products tab, which is always shown. The Overview tab is shorter.

### Added

- **Add a missing stock item from a shopping list.** In the Add to list sheet, typing a name nothing matches
  offers Add "name" as a new stock item: it is created as out of stock and goes straight onto the list.

### Fixed

- The Nutrition row on a stock item no longer pushes the page sideways on a phone when the food has a long
  name.

## [2.0.0] - 2026-11-08

Shopping lists work differently: there is no separate draft and shopping mode
any more. Upgrading: a database migration turns every open list (draft or mid-shop)
into an open list, keeping its ticks. It runs on boot; nothing to do by hand.

### Changed

- **One list from first item to receipt.** You add, edit, price and tick items on
  the same list. Start shopping and Back to draft are gone.
- **Ticking restocks straight away.** A ticked item goes to Stocked and moves to
  a Collected section; unticking puts its old level back. Ticking the last item
  asks whether you're done, and Not yet unticks it again.
- **Finish** appears once something is ticked, for a shop that ends with items
  left over. Those still go to another list or the bin.
- The summary card switches on its own: Estimated cost becomes Left to spend,
  and a progress bar appears, from the first tick. Dora's suggestions and the
  trim-to-budget banner step aside at that point.
- Lists group by store by default. The other options are Location, Group and
  A to Z; custom order, drag and drop and the move up/down arrows are gone.
- Rows are simpler: a tick button on the left, a quantity box without the +/−
  buttons (here and when amending a receipt), the buy verdict beside delete on
  a desktop, and price and delete on the same line as the name on a phone.
- The price on each row is also where you record what you paid.
- Receipt photos can be added once anything is ticked.
- The name menu on a list row (offers or preferred buys) is wider on desktop,
  and names no longer lose their last letters when there is room for them.

## [1.0.0] - 2026-11-06

The first official release. Dora keeps track of everything edible in the house
without making you count tea bags, and builds shopping, cooking, meal planning
and price tracking on top of that. It is free, open source and self-hosted.

Earlier version numbers (0.1.0 to 0.7.0) were development builds and never
released. Their history is in the git log.

### Stock

- Track what you have by level (Well-Stocked, Low, Out) rather than exact counts,
  with expiry dates, essentials, groups, and locations as a simple tree.
- Stock overview with search, filters, sorting, bulk actions and one-tap
  add-to-list from any row.
- A detail page per item with its history, the recipes, lists and meal plans
  that use it, its substitutes, the prices you've paid, and how much your
  upcoming meals will need.
- Stocktake mode with Review, Walk and Sweep phases. It asks about the items
  Dora is least sure of first.
- Optional inference (off by default): Dora estimates what you've probably run
  out of from your history and flags it on stock, recipes, lists and the
  planner. It never changes a level for you.
- Optional scanning (off by default): register real barcodes against products,
  look up new items on Open Food Facts, and print QR labels for your own items.

### Shopping lists

- Lists move through Draft, Shopping and Done. A finished list reads as a
  receipt you can still amend.
- Lists can be built from what's running low, a recipe or a meal plan. Items
  can be added automatically when they drop to Low.
- Plan which store each item comes from, set a shop day, and see the total and
  where the money goes.
- Prices you enter while shopping become your own price history.
- List templates for the shops you repeat.

### Recipes and cook mode

- A cookbook with filters for what you can cook now, what uses expiring food,
  time of day, ingredients you have or don't, health rating and calories.
- Import recipes from a URL or pasted text. Recipes support sections, optional
  ingredients, tools, photos, structured steps with their own timers, and
  versions.
- Each recipe shows its cost per serving, with a breakdown that explains any
  ingredient it couldn't price. Packs, cloves and "to taste" are priced
  sensibly.
- Nutrition from a USDA dataset you import, with Health Star Rating or
  Nutri-Score. Gaps are named and can be fixed from the recipe.
- A hands-free cook mode: voice commands, read-aloud steps, timers that
  survive a reload, scaling to how many you're cooking for, highlights for
  the tools each step needs, and one-off ingredient swaps. When you finish,
  it takes what you used out of stock.

### Meal planning

- Plan by week or on a month calendar, with meal slots your household chooses.
- "Build my week" fills a week from your recipes, within a budget and serving
  count you set, and lets you swap or reshuffle what it picks.
- Cook once for several days, reuse templates, see what's missing and what the
  week costs, and send the shortfall to a list.
- Look back over past meals and confirm what you actually cooked.
- Two devices can edit the same week at once.

### Prices, products and deals

- "Your prices": every price you log builds a history per item, with charts,
  per-100g/100ml comparisons, and loose and boxed buys kept apart.
- "Should I buy this?" judges a price against what you usually pay.
- My Products links real store products to your stock items, including
  products you add yourself for shops Dora can't check.
- Price alerts, price drops and a weekly deals email.
- Store prices come from the separate, self-hosted Dora companion, which pushes
  products in through an ingestion API with its own access keys. Dora never
  scrapes stores itself.

### Dashboard, reports and alerts

- A dashboard of nine cards you can hide and reorder: what to cook next, what's
  missing this week, your stock, kitchen health, your budget and more.
- Reports on spending, savings against your usual prices, cooking and waste.
  Cards can be hidden, widened and reordered.
- An alerts hub for expiry, low stock, price watches and an upcoming-fortnight
  timeline. Alerts can be snoozed or dismissed, and you choose which ones
  notify you.
- Alerts by email, web push and an optional evening brief.

### Ask Dora

- An assistant that answers questions, adds things to lists and points you to
  the right page. It works with no language model at all by default.
- Bring your own model per user: Ollama, OpenAI, Anthropic or Google Gemini.
  With one connected, Dora also answers how-to questions from the Help guides.
- Spoken replies with downloadable neural voices, and speech input in every
  browser, including Firefox.

### Setup, accounts and settings

- A one-time setup page creates the first admin. It can also open a demo filled
  with sample data, and leaving the demo returns you to a clean install.
- A welcome tour sets your household size, language, regional formats and the
  features you want.
- Multiple users. Sign-ups are closed by default: the admin adds people, and
  can open self-registration if they want to.
- Optional features have their own switches: money and budgets, nutrition,
  meal planning, scanning, inference and the assistant. Turn off what you don't
  use and it disappears.
- Light and dark themes in several palettes, a System option that follows your
  device, and a choice of fonts and text sizes.
- Dates, numbers, currency, units and printed or emailed documents follow your
  household's region.
- Built-in Help guides, with (?) links beside the parts of the app they explain.

### Install and operations

- Runs as one Docker container (API and web app). SQLite by default; Postgres
  is supported.
- Configuration lives in environment variables. Database migrations run on
  start.
- Backups: download a full backup or keep a library of them, inspect one before
  restoring, and choose which sections to restore. A backup changed on disk
  can't be restored.
- Import stock from a spreadsheet, using a blank template you download.
- Installable as a PWA, with a read-only offline mode. Also available as a
  native Android app and desktop bundles for Windows, macOS and Linux.
- Settings → About shows the exact build you're running, and admins are told
  when a new release is out.
- Built for a home network or behind your own reverse proxy: Secure cookies by
  default, the first admin can be locked to one email address, the API runs as
  a non-root user, and reset links are built only from your configured public
  URL. See the README's security section.
