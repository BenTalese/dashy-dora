# Help Content — the drafted entries, by surface

**Assembled 2026-10-23** from the twenty chunk files (track **Help** = each chunk's §B). **100 entry drafts** in the §3.2 shape (group · what it does · when it fires · what controls it · what it costs / might get wrong · related · chip placement · source), plus per-surface DoraBot `APP_OVERVIEW` deltas (B3). Each chunk's B1 records what `HelpPage.vue`, the `(?)` chips and `app_knowledge.py` said at analysis time and which lines were stale.

**Landed 2026-10-29** as `web_app/src/help/helpContent.ts` (condensed: one sentence + How / Setting / Note per guide; the "Chip:" rows are FU-951). This file is the long-form source the guides were cut from. **Before these landed:** the Help page's information architecture needed the owner's call (CHUNK_20 **20-D4** — one page per group, a FAQ group from the question-shaped titles, an optional screenshot slot per entry), and 11-D1 decides whether DoraBot reads the corpus through an `app_help(topic)` tool or a grown `APP_OVERVIEW`. Invisibility rule (PROPOSAL_INGESTION_API): no entry names a scraper, companion or producer.

---

## Chunk 01 — Cookbook
*Source: [`CHUNK_01_cookbook.md`](../05_investigations/finalisation/CHUNK_01_cookbook.md) · analysed 2026-10-23*

### B. Help content — Cookbook

#### B1. Current help audit
- `HelpPage.vue` GUIDES group **"Recipes & meals"** has exactly two entries: *Cook mode* (summary only, `path: '/cookbook'`) and *Build a meal plan*. **Nothing** on: importing, versions, sections, structured/free-text/photo methods, step links/highlight, tools derivation, dietary tags disclaimer, cookability tri-state, the cost estimate, nutrition modes/ratings, favourites, the pool, the bulk-linker, the share target. The cookbook is the least-documented major surface in the app.
- No `HelpHint` chip exists on any recipe surface (the three live chips are all on `StockItemDetailPage.vue`).
- `app_knowledge.py` `APP_OVERVIEW` "Recipes" paragraph (L18–24) is stale: says "cook time, difficulty, cuisine, category, and a step-by-step Cook mode … Favourite recipes are surfaced first in suggestions" — omits versions, sections, three method modes, tools, dietary tags, import, cost, nutrition, the Cookbook name, and "Mark made" wording is gone. Also "Recipes:" should read "Cookbook:" (feedback L230, PROPOSAL_COOKBOOK §2.1).
- `InfoTip` on the "Cookable now" chip (`RecipesOverview.vue:134`) is correct. `RecipeNutritionCard` InfoTip "Nutrition basis" is correct.

#### B2. Help entries (one per feature / auto-behaviour)

##### Add and edit a recipe
- **Group:** Recipes & meals (rename group to **"Cookbook"** to match the nav)
- **What it does:** A recipe is a name plus ingredients, a method and a few facts (serves, prep, cook, difficulty, when, cuisine, category, collection).
- **When it fires / how to trigger it:** Cookbook → New recipe makes a stub and opens its page. On the page, each block (details · ingredients · method) has its own pencil; edits mark the page unsaved and Save commits all of them at once.
- **What controls it:** Always on — no setting. Which vocabularies appear (cuisines, categories, dietary tags, tools, meal slots) is set under `/settings/kitchen-setup/…`.
- **What it costs / might get wrong:** Nothing is saved until you press Save or Done; leaving the page asks first. A row with no pantry item and no text blocks the save and says which row.
- **Related:** Ingredients and the pantry · Three ways to write a method · Sections
- **Chip:** `RecipeDetailPage.vue:76` beside the masthead pencil → `<HelpHint topic="Add and edit a recipe">`.
- **Source:** `RecipeDetailPage.vue`, `useRecipeEditor.ts`, PROPOSAL_COOKBOOK §2.13.

##### Ingredients and the pantry
- **Group:** Cookbook
- **What it does:** An ingredient usually points at a pantry item, so Dora can say whether you have it. It can instead be plain text (no pantry link), and a linked one can name *which one* you mean ("tasty cheddar" under Cheese) by picking a preferred buy or product.
- **When it fires / how to trigger it:** Edit ingredients → tap a row → the editor. Typing a name the pantry doesn't have offers "Use …" and asks whether to add it to the pantry or keep it as text.
- **What controls it:** Always on. Products are offered as the "which one" list only when Products is on (`/settings/admin/system/features`).
- **What it costs / might get wrong:** Free-text rows can't be checked for stock, so a recipe with one reads as "to link" rather than cookable or not. Optional rows never affect cookability.
- **Related:** Can I cook this? · Fix unlinked ingredients in bulk
- **Chip:** `RecipeDetailPage.vue:406` (Ingredients heading) → `<HelpHint topic="Ingredients and the pantry">`.
- **Source:** `ingredient_choice.py`, `RecipeIngredientRowEditor.vue`, cookbook §1.9.

##### Can I cook this?
- **Group:** Cookbook
- **What it does:** Each recipe shows whether every required ingredient is in stock. Three answers: yes, no (lists what's missing), or unknown (some rows aren't linked to the pantry).
- **When it fires / how to trigger it:** Automatically, from your recorded stock levels. The "Cookable now" filter and the dashboard's cookable count read the same rule.
- **What controls it:** Always on. "Missing" means **out of stock** — a low item still counts as cookable.
- **What it costs / might get wrong:** It trusts your recorded levels. If Dora's stock inference disagrees, the card says so as a remark ("Dora thinks…") without changing the verdict. Entering cook mode on a non-cookable recipe asks first.
- **Related:** Substitutes (Stock) · The "Dora thinks…" hint (Stock)
- **Chip:** none (InfoTip on the chip already covers it).
- **Source:** `domain/recipe_cookability.py`, `useRecipeDisplay.ts`, `cookModeGuard.ts`.

##### Three ways to write a method
- **Group:** Cookbook
- **What it does:** Free text (one block, each line becomes a numbered step), Structured (steps and sub-steps that can link to ingredients, tools and a section, with optional hints and timers), or Photos (an ordered set of step images).
- **When it fires / how to trigger it:** Edit method → the Structured / Free text / Photos switch. Switching never deletes the other mode's content.
- **What controls it:** Always on. New recipes start as free text.
- **What it costs / might get wrong:** Only Structured can highlight which ingredients a step uses (tap a step or an ingredient). In Structured mode the recipe's **tools are derived** from its steps and can't be edited separately; in the other two modes the Tools field is inside the method.
- **Related:** Cook mode · Add and edit a recipe
- **Chip:** `RecipeDetailPage.vue:701` (Method heading).
- **Source:** `recipe_step_access.py`, `sync_recipe_tools_from_steps`, `RecipeStructuredMethod.vue`, PROPOSAL_RECIPE_IMAGE_STEPS.

##### Sections
- **Group:** Cookbook
- **What it does:** Named groups inside one recipe ("For the sauce", "To serve") that hold ingredients and top-level steps.
- **When it fires / how to trigger it:** Edit ingredients → Add section. Move a row into a section from its editor; Remove section sends its rows back to the main list.
- **What controls it:** Always on.
- **What it costs / might get wrong:** Sub-steps follow their parent's section.
- **Related:** Three ways to write a method
- **Chip:** none (tooltip on Add section covers it).
- **Source:** `recipe_section_access.py`.

##### Import a recipe by pasting it
- **Group:** Cookbook
- **What it does:** Paste a recipe page's text (Ctrl+A, Ctrl+C on the site, Ctrl+V here) and Dora picks out the name, times, servings, ingredients and steps. Ingredients are matched to your pantry by name; unmatched ones are kept as text.
- **When it fires / how to trigger it:** Cookbook → Import. On Android, sharing a page to Dora opens the same dialog pre-filled.
- **What controls it:** Always on. The URL you type is kept as the recipe's Source and is never fetched by the server.
- **What it costs / might get wrong:** Sites vary; when fewer than three ingredients are found you get the page text in Instructions to tidy by hand. Matching is fuzzy (score ≥ 70) and can pick the wrong pantry item — check the rows.
- **Related:** Fix unlinked ingredients in bulk
- **Chip:** `RecipesOverview.vue:35` (Import button tooltip could link) — optional.
- **Source:** `import_recipe_from_content.py`, `_parse_recipe_from_text.py`, MAGIC F8.

##### Fix unlinked ingredients in bulk
- **Group:** Cookbook
- **What it does:** Every ingredient that isn't linked to a pantry item, grouped by its text across all recipes, so "1 onion" in nine recipes is linked once.
- **When it fires / how to trigger it:** `/settings/kitchen-setup/unlinked-ingredients` (verify exact path in Chunk 13).
- **What controls it:** Always on.
- **What it costs / might get wrong:** Linking is by exact (whitespace/case-insensitive) text match; "onion, diced" and "onion" are two groups.
- **Related:** Import a recipe by pasting it · Can I cook this?
- **Chip:** on that settings page heading (Chunk 13).
- **Source:** `unlinked_ingredients.py`.

##### Versions of a recipe
- **Group:** Cookbook
- **What it does:** New version copies the whole recipe (ingredients, sections, steps, photos, tags, tools) into a sibling named "(vN)". Versions are equal peers — no "current" one — and each keeps its own meal pool and favourite flag.
- **When it fires / how to trigger it:** Recipe page → New version (action row or Version information panel).
- **What controls it:** Always on.
- **What it costs / might get wrong:** The copy starts unfavourited and with an empty meal pool; meal plans pick a specific version.
- **Related:** Add and edit a recipe
- **Chip:** `RecipeDetailPage.vue:975` (Versions sub-heading).
- **Source:** `new_recipe_version.py` (DEC-2), FU-741.

##### Meals prepared (the pool)
- **Group:** Cookbook
- **What it does:** How many portions of a recipe are already cooked and waiting (freezer, fridge). Cook mode asks how many you made and adds them; past meal-plan days take them away; the planner shows a shortfall when the plan wants more than exist.
- **When it fires / how to trigger it:** Finishing cook mode, the ± stepper on the recipe page's Last cooked cell, and the meal plan's daily reconcile.
- **What controls it:** `/settings/admin/system/cooking` — cook style **Batch** shows the pool everywhere; **Fresh** hides it (the filter, sort axis and stepper disappear).
- **What it costs / might get wrong:** Never goes below zero. "N free · M planned" explains why adding one can still read 0 free.
- **Related:** Build a meal plan · Cook mode
- **Chip:** `RecipeDetailPage.vue:372` beside the stepper.
- **Source:** `pool.py`, `cook_recipe.py`, MAGIC F10, FU-317.

##### What a recipe costs
- **Group:** Cookbook (money)
- **What it does:** An estimate from your own prices: each ingredient is priced from the cheapest linked product offer, else the item's logged prices; the amount is converted into the price's unit, and anything that can't be bridged is reported unpriced rather than guessed. Cards show cost per serving; the page shows the total, "N of M priced", and a breakdown of who dominates the bill and why rows are unpriced.
- **When it fires / how to trigger it:** Automatically on every recipe when money is on.
- **What controls it:** `/settings/admin/system/money` (money features) — off by default; with it off nothing is computed or shown.
- **What it costs / might get wrong:** It's an estimate, not a quote. A pack sold by weight can't price "3 of them" unless the product records how many are in the pack; a cup of something needs a density or a measured portion.
- **Related:** Prices on a stock item (Stock) · Budget
- **Chip:** `RecipeDetailPage.vue:344` (Estimated cost cell label).
- **Source:** `recipe_cost.py`, `RecipeCostDialog.vue`, R-076/ADR-073, FU-874/904/905.

##### Nutrition: off, simple, complex
- **Group:** Cookbook (nutrition)
- **What it does:** Off hides everything. Simple lets you type kcal per serving on a recipe and filter/sort on it. Complex links pantry items to foods in a nutrition catalogue and adds up each recipe's energy and nutrients per serving, always with its coverage ("From 7 of 9 ingredients"), and can show a Health Star Rating or Nutri-Score.
- **When it fires / how to trigger it:** Automatically on recipe cards and pages.
- **What controls it:** `/settings/admin/system/nutrition` (mode, rating scheme, datasets, Open Food Facts / USDA API); per-item food links under the item's page or the matching page.
- **What it costs / might get wrong:** Ratings are estimates from raw ingredient weight. A missing figure (e.g. sugars unknown for a food) flatters the rating — the panel names which figures were thin. The "≤ N kcal" filter judges the figure shown, even when coverage is partial (marked with *).
- **Related:** Link a food to a stock item (Stock) · What a recipe costs
- **Chip:** `RecipeDetailPage.vue:904` (Nutrition heading).
- **Source:** `recipe_rollup.py`, `nutrients.py`, `useNutritionRating.ts`.

##### Dietary tags are a planning aid
- **Group:** Cookbook
- **What it does:** Tags you put on a recipe (vegan, gluten-free…) drive the include/exclude filter. The disclaimer "Tags are a planning aid. Check the ingredient list when food safety matters." is shown whenever a tag filter is on.
- **What controls it:** `/settings/kitchen-setup/dietary-tags` edits the vocabulary.
- **Source:** `domain/recipe_tags.py`, `get_recipe_tag_catalogue`.

##### Mark cooked without cook mode
- **Group:** Cookbook
- **What it does:** Cooking a recipe stamps "Last cooked" today and (in batch style) adds to the pool; it also writes a cook event the stock item's History tab shows as "Used in <recipe>".
- **Source:** `cook_recipe.py` (MAGIC F10 verdict: keep silent). Owner feedback: "Mark made" → "Mark Cooked" wording — confirm the live label in cook mode (Chunk 4).

#### B3. DoraBot corpus delta
Replace `app_knowledge.py` L18–24 with:
```
- Cookbook: the household's recipes. Each has ingredients (linked to pantry
  items so Dora knows whether you have them, or plain text), a method written
  as free text, structured steps or step photos, and facts like serves,
  prep/cook time, difficulty, cuisine, category, collection, dietary tags and
  tools. Filters cover all of those plus "cookable now", "uses expiring
  ingredients", "planned", kcal and cost (when those features are on).
  Recipes can be imported by pasting a page's text, copied as versions, and
  each tracks "meals prepared" — cooked-ahead portions in the pool that cook
  mode adds to and meal plans draw down. With money on, Dora estimates what a
  recipe costs from the user's own prices; with nutrition on, it adds up
  kcal per serving (and a Health Star Rating / Nutri-Score in complex mode).
```

---

## Chunk 02 — Meal Plans
*Source: [`CHUNK_02_meal_plans.md`](../05_investigations/finalisation/CHUNK_02_meal_plans.md) · analysed 2026-10-23*

### B. Help content — Meal Plans

#### B1. Current help audit
- `HelpPage.vue` GUIDES has one entry for this whole surface — *Build a meal plan* under "Recipes & meals": "Group recipes into meals (e.g. roast + sides). Then schedule meals onto a meal plan; the dashboard shows the next entry on the home page." This describes a model that **no longer exists** (there are no "meals" grouping recipes; the planner is a week of slot rows). Stale and misleading.
- The reconcile **runner** and **log** each open a `(?)` modal (`MealReconcileRunner.vue:210–240`, `MealReconcileLog.vue:536–563`) holding the only real help text for reconcile. Owner directive 2026-08-27: *"Info button should take you to help and guides, not open a modal"* — the stocktake runner was converted; these two were not (02-R40).
- `app_knowledge.py` `APP_OVERVIEW` "Meal Plans" paragraph (L25–30) is half-right: it mentions pool decrement on past days and the shortfall, but not cook batches, fresh meals, the auto builder, templates/sets, reconcile modes, the rail's suggestions, cost/budget, or lighter swaps.
- Good inline help that already exists and should be *linked from* guides rather than repeated: the builder's emphasis/servings/budget captions, the apply-template explainer, the `InfoTip` on cookable-now (cookbook).

#### B2. Help entries (one per feature / auto-behaviour)

##### Plan a week
- **Group:** Meal plans (new group; move *Build a meal plan* out of "Recipes & meals" and delete it)
- **What it does:** A plan is one week, Monday to Sunday, with the household's meal slots on each day. Tap a slot, then a recipe in the rail (or the picker on a phone) to put it there; tap the same recipe again to add a serving.
- **When it fires / how to trigger it:** `/meal-plans`. The first add to an unplanned week creates the plan; past days are read-only.
- **What controls it:** Slots: `/settings/kitchen-setup/meal-slots`. "All slots" toggle on the toolbar shows empty slots too (remembered per device).
- **What it costs / might get wrong:** Deleting a slot keeps meals already planned under it (they show under "Other"). The week shown on arrival is the household's current week (server timezone).
- **Related:** Build my week · Cook once for several days · Reconcile past meals
- **Chip:** `MealPlansOverview.vue:187` beside the "Recipes" rail heading → `<HelpHint topic="Plan a week">`.
- **Source:** `useMealPlanner.ts`, `update_meal_plan.py`.

##### Build my week
- **Group:** Meal plans
- **What it does:** Dora proposes a week from light guidance — which days, which meals, an emphasis (use up stock / variety / favourites / surprise), servings per meal, and optionally "keep under budget". You edit the proposal (swap, move, re-serve, remove, add) before saving.
- **When it fires / how to trigger it:** Toolbar → Build my week (both breakpoints). Reshuffle picks again from the near-best candidates.
- **What controls it:** Servings seed from `/settings/admin/system/cooking` (people you cook for); the budget cap exists only with money on (`/settings/admin/system/money`); in a Batch household the builder proposes cook batches of up to three days.
- **What it costs / might get wrong:** Each meal uses a distinct recipe, so a small cookbook leaves days empty — the review step says how many. "Under budget" counts the **full cost of the meals**, pantry or not; the to-buy figure is shown beside it. Recipes already planned that week are never proposed.
- **Related:** Plan a week · What a recipe costs (Cookbook)
- **Chip:** `MealPlanBuilderDialog.vue:30` (Setup caption) → HelpHint.
- **Source:** `build_week.py`, FU-596/FU-611/FU-907.

##### Dora suggests (the rail)
- **Group:** Meal plans
- **What it does:** The "Dora suggests" chip ranks your cookbook for the week you're looking at — expiring stock, cookable now, not had lately, favourites — and says why beside each row. The other chips are plain filters (All · Cookable now · Favourites · Not lately · Regulars); search and the time-of-day/difficulty fields narrow whatever the chip produced.
- **What controls it:** Always on. The ranking is the same engine as Build my week's "use up stock" emphasis.
- **What it costs / might get wrong:** It excludes recipes already planned that week; it is recomputed per week.
- **Source:** `build_week.week_suggestions`, `recipeRailFilters.ts`.

##### Cook once for several days (cook batches)
- **Group:** Meal plans (Batch households)
- **What it does:** Link the same recipe across several days in one slot: the earliest day is the **cook day** and carries the whole yield ("Cook day · 9 servings"); the later days are **leftovers** and never need cooking. Cost is counted once, on the cook day.
- **When it fires / how to trigger it:** A meal's menu → "Cook once for more days…" (tick the days) · "Change cook days…" · "Separate this cook".
- **What controls it:** Only with cook-style **Batch** (`/settings/admin/system/cooking`).
- **What it costs / might get wrong:** Un-ticking a day in "Change cook days" removes that day's meal; "Separate" keeps every day as its own meal. A batch and a fresh mark can't be combined. Duplicating a week currently loses the links (02-R2 — fixed in Stage 2).
- **Related:** Meals prepared (Cookbook) · Reconcile past meals
- **Chip:** on the `MealPlanEntryMenu` link item? No — menu items don't carry chips; place on the `MealPlanShoppingSummary`? No. Place in the help page only, linked from "Plan a week".
- **Source:** PROPOSAL_MEAL_PLANS_PART_2, `cook_batch_grouping.py`, `planned_meals.allocate_pool`.

##### Cooked fresh on the day
- **Group:** Meal plans (Batch households)
- **What it does:** Marks a meal as cooked on its day, outside the pool of cooked servings: it never takes a ready serving and never asks you to batch-cook one. Shows a "Fresh" chip.
- **When it fires / how to trigger it:** A meal's menu → "Cook fresh on the day" (Batch only).
- **What it costs / might get wrong:** Reconciling a fresh meal never touches the pool.
- **Source:** `MealPlanEntry.cook_fresh`, owner 2026-09-04.

##### What the meal glyphs mean
- **Group:** Meal plans
- **What it does:** Each planned meal carries up to two glyphs: the **chef hat** (can you make it — green yes, amber missing ingredients) and the **fridge** (is a cooked serving ready — green yes, amber still to cook; Batch only). The card's left edge rolls them up: green fine, amber needs you, grey nothing to do (leftovers, cooked). Dora's voice glyph is a hunch about stock, never a verdict.
- **What controls it:** Cookability from your stock levels; readiness from the cooked pool; both server-decided.
- **Related:** Can I cook this? (Cookbook) · The "Dora thinks…" hint (Stock)
- **Source:** `helpers/mealPlanEntryStatus.ts`, owner assessment 2026-09-12.

##### Templates and rotating sets
- **Group:** Meal plans
- **What it does:** Save a planned week as a template (meals by weekday and slot); apply it to the week you're viewing or across a run of weeks (up to 26). A rotating **set** is an ordered list of templates applied week-by-week in turn.
- **When it fires / how to trigger it:** Week menu → Save week as template; toolbar → Apply template; manage (rename, delete, build sets) at `/meal-plans/templates`.
- **What it costs / might get wrong:** Applying replaces the week's future meals (it asks first) and skips past days. Editing or deleting a template never changes weeks already planned from it. Templates don't carry cook batches (02-D1).
- **Source:** `manage_templates.py`, `manage_sets.py`, Decision 1/2.

##### Reconcile past meals
- **Group:** Meal plans
- **What it does:** When a planned day passes, Dora records what happened to each meal. In **auto** mode (default) she assumes you cooked it, takes the servings from the pool and writes it to the **Meal log** — you can correct any row. In **manual** mode nothing moves until you confirm each meal in the runner: Cooked · Different portions · Cooked later · Didn't cook · Skip for now.
- **When it fires / how to trigger it:** The daily sweep (overnight, household timezone); `/meal-plans/reconcile`; the nudge above the planner and the dashboard chip count what's pending (manual mode only).
- **What controls it:** `/settings/admin/system/meal-reconciliation` (auto vs manual).
- **What it costs / might get wrong:** Every decision is a new receipt — nothing is overwritten, and "Skip" changes nothing. Three or more unresolved meals four days old raise an alert.
- **Related:** Meals prepared (Cookbook) · Alerts
- **Chip:** replaces the runner's and log's `(?)` modals (`MealReconcileRunner.vue:29–35`, `MealReconcileLog.vue:457–463`) with `<HelpHint topic="Reconcile past meals">` (02-R40).
- **Source:** `reconcile_consumed_meals.py`, `reconcile.py`, MAGIC F5.

##### Missing this week and the shopping hand-off
- **Group:** Meal plans
- **What it does:** The right rail (or the card under the phone's week) totals the week's ingredients at the planned servings, splits them into out / low / stocked, lists free-text ingredients that can't be shopped for, and hands the missing ones to the same add-to-list picker the recipe page uses. Hovering an ingredient highlights the meals that need it.
- **What controls it:** Always on. "Already on a list" comes from your open lists.
- **What it costs / might get wrong:** Quantities are summed per stock item across recipes with the same unit; different units aren't converted here.
- **Source:** `get_meal_plan_ingredients.py`, `MealPlanShoppingSummary.vue`.

##### Cost this week and the budget
- **Group:** Meal plans (money)
- **What it does:** Each meal's price chip is its recipe's per-serving estimate × servings (a cook day prices the whole cook); the week's total sits under the rail with its coverage; the budget line compares the week against what is left of the household budget period the week falls in. When the week is projected over budget, Dora offers cheaper recipe swaps with undo.
- **What controls it:** `/settings/admin/system/money` + `/settings/budget`.
- **What it costs / might get wrong:** Estimates follow the recipe cost rules (see Cookbook). Swaps only ever suggest recipes you can cook now, that are similar, or that you've cooked before.
- **Source:** `get_meal_plans._hydrate_cost`, `swap_suggestions.py`, FU-451.

##### Find a lighter option
- **Group:** Meal plans (nutrition)
- **What it does:** From a meal's menu, lists recipes with fewer kcal per serving than it, with the saving and why it's plausible. Never volunteered — Dora holds no calorie target.
- **What controls it:** Nutrition mode on and a reliable figure for the meal (`/settings/admin/system/nutrition`).
- **Source:** FU-637, `rank_lighter_swaps`.

##### Tomorrow at a glance (the daily brief)
- **Group:** Meal plans / Alerts
- **What it does:** One evening notification naming tomorrow's planned meals in slot order (or "Nothing planned for tomorrow yet" when the week has meals elsewhere), plus any shopping day due. Silent when it has nothing to say.
- **What controls it:** Push + the brief hour under `/settings/notifications` (verify in Chunk 9).
- **Source:** `daily_brief.py`.

#### B3. DoraBot corpus delta
Replace `app_knowledge.py` L25–30 with:
```
- Meal Plans: a week at a time, Monday to Sunday, with the household's meal
  slots on each day. Tap a slot then a recipe to plan it, or let "Build my
  week" propose a week (use up stock, variety, favourites, surprise; servings
  per meal; optionally keep under budget) and edit it before saving. Batch
  households can link one cook across several days (cook day + leftovers),
  mark a meal as cooked fresh, and see which meals still need cooking from
  the cooked-servings pool. Weeks can be saved as templates and re-applied,
  singly or as a rotating set across weeks. As days pass Dora records what
  happened to each meal (auto: assumed cooked and logged; manual: confirmed
  one by one). The right rail totals the week's ingredients, shows what's
  missing, and hands them to a shopping list; with money on it shows the
  week's cost against the budget and offers cheaper swaps.
```

---

## Chunk 03 — Shopping Lists
*Source: [`CHUNK_03_shopping_lists.md`](../05_investigations/finalisation/CHUNK_03_shopping_lists.md) · analysed 2026-10-23*

### B. Help content — Shopping Lists

#### B1. Current help audit
- `HelpPage.vue` "Shopping & deals" group holds **one** entry (*Search for products* — the ingestion seam), nothing about lists, faces, quick-add, templates, budget or receipts. The surface the owner spent the most September feedback on has no help at all.
- `app_knowledge.py` L34–38 says *"multiple lists with one marked PRIMARY … Archive completed lists, copy lists … Lists can be marked in-progress while shopping"* — three retired concepts (primary flag, copy, in-progress) and none of the three faces, finish-as-receipt, money/store ladders, trim-to-budget or quick-add inference.
- Inline help that exists and should be *linked*, not repeated: the overview card tooltips (Shop / Finish / Amend / Put away), the plan row's "Any store" rationale, the price sheet's "Price each" wording, the trim banner copy, the `AddToListDialog` unlinked-ingredients footer.

#### B2. Help entries

##### One list, three faces
- **Group:** Shopping (new group; rename "Shopping & deals" → "Shopping" and move *Search for products* under Products)
- **What it does:** A list is a draft while you build it, a shop while you're in the store, and a receipt once you finish. Each face shows only what that moment needs: the draft has quantities, stores and reordering; the shop has one big tick per row and a price button; the receipt is a read-only docket you can amend.
- **When it fires / how to trigger it:** **Shop** on the card starts the trip; **Finish** ends it; **Draft** (mid-shop) undoes an accidental start and unticks everything.
- **What it costs / might get wrong:** Finishing is final — a done list can't go back. Ticked items are restocked to Stocked when you finish, never before.
- **Related:** Finish and restock · Amend a receipt
- **Chip:** `ShoppingListOverviewCard.vue:58` beside the status pill → `<HelpHint topic="One list, three faces">`.
- **Source:** `manage_shopping_list.py`, PROPOSAL_SHOPPING_LIST_UX_V4 §4.

##### Which list opens, and which one quick-add uses
- **Group:** Shopping
- **What it does:** `/shopping-lists` opens the list that's up next: a shop in progress, else the first pending list dated on or after your last finished shop, else the earliest pending, else the most recent receipt. Quick-add (the cart button anywhere in Dora) lands on your **only** draft; with two or more drafts it asks once and remembers for the tab; with none it asks you to create one.
- **What controls it:** Nothing to set — there is no "primary list" flag. Shop day (toolbar) is what moves a list in the order.
- **What it costs / might get wrong:** The rail is one timeline, newest first; finished lists older than the five most recent sit behind "See older".
- **Source:** `get_shopping_lists._next_up_list_id`, `quick_add_target_resolver.py`, MAGIC F2/F3/F4.

##### Adding items: Add item, the cart button, and "Add to a list"
- **Group:** Shopping
- **What it does:** **Add item** on a list searches every stock item, frequently-added first, hiding what's already on the list; one tap adds one. The **cart button** on stock rows, recipe ingredients and products adds or removes with one tap (two or more linked products open the sheet so you choose which). Recipe and meal-plan pages use **Add to a list**, which pre-ticks what's missing or low, names what each item is for, and lists ingredients that can't go on a list because they aren't linked to a pantry item.
- **What it costs / might get wrong:** A new line remembers your last choice for that item — the preferred buy or product you picked last time, and its store; clearing a choice is remembered too.
- **Related:** Recipes & lists (Cookbook) · Missing this week (Meal plans)
- **Source:** `QuickAddSheet.vue`, `AddToListButton.vue`, `AddToListDialog.vue`, `_line_defaults.py`.

##### Start a list from stock, a recipe, a plan or a template
- **Group:** Shopping
- **What it does:** **New list** builds a list from what's low or out (optionally essentials only), all your essentials, items you add most often, a recipe's ingredients (minus what's stocked), a meal-plan week, or a saved template — into a new list or topped up onto an existing one. Items are never added twice.
- **What it costs / might get wrong:** Recipe and plan ingredients without a linked stock item are listed for you to add by hand. "Frequently added" counts every line ever written, finished shops included.
- **Source:** `auto_generate.py`, `NewListDialog.vue`, MAGIC F12.

##### Picking which one: offers and preferred buys
- **Group:** Shopping
- **What it does:** The item's name on a row is a menu. With products on, it lists the item's linked offers (price, store, saving); without, it lists the item's preferred buys. Picking an offer moves the line to that store and uses its price as the estimate; picking again clears it.
- **What controls it:** `/settings/admin/system/products` decides which list the menu shows.
- **What it costs / might get wrong:** An offer is an estimate until you enter a price in the shop — nothing is recorded as spend until then.
- **Source:** `LineChoicePicker.vue`, owner 2026-09-17/27.

##### What a line is expected to cost, and where you'll buy it
- **Group:** Shopping (money)
- **What it does:** Each estimate uses the first of: a price you entered · the offer you picked · what you last paid for the item. Each row's store uses the first of: where you bought it · the store you chose for this list · the item's usual store · where you last bought it · the picked offer's store. The card's total and the "Where you'll spend it" split come from those; items with no price are counted but not priced, and the card says so.
- **What controls it:** `/settings/admin/system/money`. Usual stores live on the stock item.
- **Related:** Your prices (Stock)
- **Source:** `get_shopping_list_detail.py` ladders, `_line_price.resolve_store_id`.

##### Entering prices as you shop
- **Group:** Shopping (money)
- **What it does:** Tap a row's price in the shop to record what you actually paid, how many, and where. "Seen at" chips pull an advertised price in with one tap. **Log price** on the toolbar records a shelf price for something that isn't on the list.
- **What it costs / might get wrong:** Only entered prices become spend, savings and purchase history; a list finished with no prices records none. Quantity multiplies the line.
- **Source:** `ShoppingListDetail.vue` price sheet, `_observation_sync.py`.

##### Finish and restock
- **Group:** Shopping
- **What it does:** Finishing marks the shop done: every ticked item's level goes to Stocked, each priced line becomes a purchase in the item's price history, and names are frozen so the receipt survives pantry changes. Anything unticked must go somewhere first — another list, a new list, or the bin.
- **What it costs / might get wrong:** A finished list is a receipt; it can't return to draft. Discarded leftovers are gone from the list, not from your pantry or history.
- **Related:** Stock levels (Stock) · Budget
- **Source:** `FinishShoppingListHandler`, `list_actions.py`, MAGIC F16.

##### Amend a receipt
- **Group:** Shopping
- **What it does:** On a finished list, **Amend** unlocks price, store and quantity per line (never add/remove/reorder). A correction rewrites the purchase record the line created, so a typo stops feeding every future estimate.
- **What it costs / might get wrong:** Your pantry isn't restocked again; the purchase's date stays as first recorded.
- **Source:** FU-726, `UpdateLineHandler` observation sync.

##### Keep a shop under budget (trim to fit)
- **Group:** Shopping (money + budget)
- **What it does:** When a draft is projected over what's left of the budget period its shop day falls in, Dora offers to set lines aside: habit buys that can wait, low items with days of cover left, things above your usual price, out-of-stock items with no meal booked, ingredients for meals five or more days away. Each cut names its reason; **Keep** protects a line; **Add back** restores it later.
- **What controls it:** `/settings/budget`. Never cut: essentials, meals in the next two days, lines under $2, "buy" verdicts on low/out items.
- **Source:** `trim_to_budget.py`, PROPOSAL_BUDGET_AWARE_LISTS.

##### Templates
- **Group:** Shopping
- **What it does:** Save a list as a template (unticked lines by default) and start new lists from it in one tap. Edit a template's items, quantities and "which one" choices at `/shopping-lists/templates`; choices carry onto new lists while they still apply.
- **Source:** `manage_templates.py`.

##### Receipt photos
- **Group:** Shopping
- **What it does:** Attach photos of the till receipt to a list you're shopping or have finished — up to 20, tap to zoom, bin to remove. Record-keeping only: nothing is read from the image.
- **Source:** FU-334.

##### Dora thinks you may be out of…
- **Group:** Shopping / Dora's hunches
- **What it does:** On a draft, a strip of items Dora believes you've run out of (from purchase rhythm and cooking) that aren't on the list yet; tap to add. Nothing is added for you.
- **What controls it:** Settings → Assistant → inference for shopping (off by default).
- **Related:** The "Dora thinks…" hint (Stock)
- **Source:** FU-653, `_inferred_suggestions`.

#### B3. DoraBot corpus delta
Replace `app_knowledge.py` L34–38 with:
```
- Shopping Lists: a list is a draft while you build it, a shop while you're in
  the store, and a receipt once finished. Add items from the list (search,
  frequently-added first), from any stock/recipe/product row's cart button, or
  from "Add to a list" on recipes and meal plans; "New list" can fill a list from
  low/out items, essentials, frequent buys, a recipe, a plan week or a template.
  Each row can pick which offer or preferred buy you mean, and which store you
  plan to buy it at; with money on, Dora estimates each line (entered price →
  picked offer → what you last paid) and splits the total by store. In the shop
  you tick rows and can enter what you paid; finishing restocks ticked items,
  records entered prices as purchase history, and asks what to do with anything
  unticked (move or discard). A finished list is a receipt you can amend. Over
  budget, "Trim to fit" sets safe lines aside with a reason. Templates and
  receipt photos round it out. Quick-add targets your only draft and asks if
  there are several.
```

---

## Chunk 04 — Cook Mode
*Source: [`CHUNK_04_cook_mode.md`](../05_investigations/finalisation/CHUNK_04_cook_mode.md) · analysed 2026-10-23*

### B. Help content — Cook Mode

#### B1. Current help audit
- `HelpPage.vue:451–454` *Cook mode*: "Open a recipe and hit Cook. Steps render one card at a time and ingredients show where each one lives (e.g. Pantry > Top shelf)." — stale: grouping is by **base** location (sub-areas collapse; "Top shelf" is exactly what it doesn't show) and sections win when the recipe has them; nothing about headcount, timers, Sous Chef, swaps, finish.
- `HelpPage.vue:397` *Substitutes* entry already covers "a swap made in cook mode is temporary" well — link, don't repeat.
- The in-page `(?)` **commands popover** is fine (it is a mid-cook reference, not help — owner 2026-09-03), but the *explanations* (what Sous Chef is, which browsers, why a timer might be silent) belong in HelpPage.
- `app_knowledge.py:24–27` says "Cook mode ends by asking how many meals were cooked; that count is added" — Batch-only now, and omits levels/consumption, swaps, voice, headcount.

#### B2. Help entries

##### Cook mode
- **Group:** Cookbook (replace the existing *Cook mode* entry)
- **What it does:** One step at a time, at a size you can read from across the kitchen. Structured recipes show sections, sub-steps, hints and the ingredients and tools the current step needs (the rest dim); free-text recipes split on lines; photo recipes page through the pictures with zoom. Tap a segment of the progress bar or a row in "All steps" to jump.
- **When it fires / how to trigger it:** **Cook** on a recipe (Dora warns first if you're missing ingredients — see *Can I cook this?*). Keyboard: → / space next, ← previous, R repeat, Esc exit.
- **What it costs / might get wrong:** Which steps you see follows the recipe's chosen mode; a structured recipe with no steps falls back to its text.
- **Related:** Cooking for a different number · Sous Chef · Finishing a cook
- **Chip:** `RecipeCookMode.vue:52` beside the recipe name → `<HelpHint topic="Cook mode">` (icon-only; the header is already tight on a phone).
- **Source:** `RecipeCookMode.vue` `cookSteps`.

##### Cooking for a different number
- **Group:** Cookbook
- **What it does:** The "Cooking for" pill opens at your household headcount (or the servings the meal plan asked for) and rescales every quantity for this cook only — whole numbers for things you count (eggs, cloves, cans), kitchen fractions (½ ⅓ ¼) or one decimal for everything else. The saved recipe is never changed.
- **What controls it:** `/settings/admin/system/cooking` (headcount). A recipe with no servings can't be scaled.
- **Source:** `scaleQuantity.ts` (DEC-4), `useCookingPolicy`.

##### Sous Chef (Dora reads the steps)
- **Group:** Cookbook / Dora
- **What it does:** With Sous Chef on, Dora reads each step as you reach it and "Repeat" reads it again. She uses her own neural voice when it's installed on the server (works in every browser) and the device's voice otherwise. The setting is remembered per user.
- **What controls it:** The Sous Chef button; voice choice under `/settings/voice`.
- **What it costs / might get wrong:** On a phone, a step read *after* a long silence (a timer finishing) may be muted by the browser's autoplay rule — the toast still fires. If the start of a sentence is clipped on Android, see Settings → Voice.
- **Related:** Which browsers can Dora speak in? (Dora itself)
- **Source:** `useSpeechOutput.ts`, FU-722/FU-629.

##### Hands-free commands
- **Group:** Cookbook / Dora
- **What it does:** Turn the mic on and say *next*, *back*, *repeat*, *ingredients*, *tools*, *start / pause / reset timer*, *stop* (quietens Dora, or pauses the timer) or *exit*. Unrecognised speech is ignored on purpose. The mic is independent of Sous Chef — you can listen without narration and vice versa.
- **What controls it:** The mic button, shown only where the browser supports speech recognition (Chrome, Edge, Safari; not Firefox).
- **What it costs / might get wrong:** The browser may pause listening after a long silence; Dora reopens it, waiting until she has finished talking so her own voice isn't clipped.
- **Source:** `useVoiceInput.ts`, `handleVoiceCommand`.

##### Step timers
- **Group:** Cookbook
- **What it does:** A structured step can carry its own timer; otherwise Dora reads a duration out of the step's wording and says so ("from this step's wording"). Start, pause, reset; the bar empties as time passes; at zero you get a toast, a chime and — with Sous Chef on — a spoken "Timer finished". The screen stays awake while you cook.
- **What it costs / might get wrong:** One timer at a time, and moving to another step resets it (02-D2 — under review). A chime after a long idle may be blocked by the browser; the toast is the signal to trust.
- **Source:** `sniffedTimerMinutes`, `timer_minutes`.

##### Swapping an ingredient for this cook
- **Group:** Cookbook
- **What it does:** When an ingredient is low or out, the swap button lists its recorded substitutes with their ratio and note; picking one shows it in the row with the hint, and the finish step adjusts the *substitute's* level. Temporary — the recipe is untouched.
- **Related:** Substitutes (Stock)
- **Source:** B8, `sessionSwaps`.

##### Finishing a cook
- **Group:** Cookbook
- **What it does:** "Finished cooking?" lists each ingredient with its current level preselected — change the ones you used up (or add them to a list from the cart beside each). Changed levels are recorded as cooking consumption, the recipe's "last made" moves to today, and in a Batch household you say how many extra servings you set aside for the pool.
- **What it costs / might get wrong:** Leaving a row alone changes nothing. Unlinked ingredients aren't listed. Finishing a photo recipe works the same way from its last Next.
- **Related:** Meals prepared (Cookbook) · Stock levels (Stock)
- **Source:** `confirmFinish`, `cook_recipe.py`, MAGIC F10.

#### B3. DoraBot corpus delta
Replace `app_knowledge.py` L24–27's cook-mode sentences with:
```
  Cook mode shows one step at a time (sections, sub-steps, hints, per-step
  ingredient and tool highlights; photo recipes page through pictures),
  rescales quantities for the number you're cooking for, offers timers, can
  read steps aloud (Sous Chef) and take spoken commands, and lets you swap a
  low ingredient for a recorded substitute for that cook only. Finishing asks
  which ingredient levels changed, records them as cooking consumption, stamps
  the recipe as made today and, in a batch-cooking household, adds any spare
  servings to the recipe's pool.
```

---

## Chunk 05 — Stock Overview + Stocktake
*Source: [`CHUNK_05_stock_overview_stocktake.md`](../05_investigations/finalisation/CHUNK_05_stock_overview_stocktake.md) · analysed 2026-10-23*

### B. Help content — Stock Overview + Stocktake

#### B1. Current help audit
- `HelpPage.vue` **Stock** group: *Add a stock item*, *expiry / essentials*, *Dora's hint* (inference), *Scanning*, *Barcodes*, *QR labels*, *Substitutes*, *Link a product* — good coverage of the detail-page features; **nothing** on the overview's own language: the attention outline and its rule, the three-band row ramp, the dashed "might be wrong" ring, filters/sort, bulk select, the expiry button's push shortcuts, open/in-use + effective expiry, auto-add, export of the filtered set. The colour rules live in *What the colours and outlines mean* (`HelpPage.vue:353`) as the page comment says; `StockRowLegend.vue` is the live legend component and should be mounted inside that entry's `details` so the guide can't drift from the rows (R-003) — today the entry is prose only.
- **Stocktake** group: *How stocktake works* with `details` paragraphs (engagement gate, least-certain-first ordering, cadence bands) — accurate and already the `(?)` deep-link target. Missing: the three phases by name (Review / the walk / "Dora's stopped tracking these"), Push vs Skip vs Mute semantics, the Low/Out → list prompt, the per-item toggle and install default, FU-700's "turned off" state.
- `app_knowledge.py:15–19` Stock paragraph: accurate but thin — no attention rule, no stocktake, no bulk, no scan actions.

#### B2. Help entries

##### Reading a stock row
- **Group:** Stock (rewrites the existing *What the colours and outlines mean* entry; mount `StockRowLegend` in its `details`)
- **What it does:** The coloured square is the stock level (green stocked · amber low · red out; dashed-edge box = no level set). A **dashed ring** around it means the number might be wrong — either Dora's hunch disagrees or the item is due a stocktake check; open the square to see which. The **row outline** means something needs you: expired, expiring soon, or an essential that's low or out. A **dimmed** row is out of stock but not essential — nothing to do. The coloured left edge marks an essential.
- **What controls it:** The expiring-soon window and per-user alert kinds (`/settings/notifications`) decide the outline; it's the same rule as the bell.
- **Source:** `stock_attention.py`, `StockRowLegend.vue`, D-5/D-7/D-8.

##### Finding things: filters, sort and search
- **Group:** Stock
- **What it does:** Search by name; quick chips for Needs attention · Expiring soon · Essential · Open; dropdowns for level, location (searchable path), group; sort by attention (default: most urgent first), name, level, last updated or expiry, with a direction toggle. The filter panel opens by itself whenever a filter is active and your filters survive leaving and returning (not a reload). The footer counts describe what's shown.
- **What it costs / might get wrong:** Links from elsewhere (an alert, a recipe's "ingredients", a location) arrive as chips you can remove.
- **Source:** `useStockFilters.ts`, `useFilterPanelExpanded`.

##### Quick actions on a row
- **Group:** Stock
- **What it does:** Tap the level square to set a level. The expiry button opens a calendar when none is set; once set it offers +1 / +7 / +14 days (counted from today or the current date, whichever is later), Clear, and Log waste. The seal/open button marks an item in use — opening asks whether its effective expiry changes. The cart adds to (or removes from) your list. Tap the row to open the item; on a phone, hold a row to select several.
- **Related:** Expiry and essentials · Shopping: the cart button
- **Source:** `StockItemRow.vue`, `useStockItemActions`.

##### Doing several at once (bulk select)
- **Group:** Stock
- **What it does:** Bulk select (or hold a row on a phone) lets you pick rows and add them to a list, remove them from one, move them to a location, mark them restocked, log them all as wasted for one reason (with Undo), or print their QR labels. Each is one request. Deselecting the last row ends bulk mode.
- **Source:** `StockOverview.vue` bulk bar, `bulk_operations.py` ×2.

##### Essential items and auto-add
- **Group:** Stock
- **What it does:** Marking an item essential makes Dora chase it as soon as it runs low (the row outlines, the bell says so) instead of waiting until it's gone. With auto-add on, an item dropping to low or out lands on your only draft shopping list by itself, marked with Dora's glyph; you're told in a toast.
- **What controls it:** `/settings/admin/system/stock` auto-add mode: off · essentials only (default) · every item. Nothing is auto-added when you have no draft list or more than one.
- **Source:** `update_stock_item._try_auto_add`, MAGIC F1.

##### Scanning with an action
- **Group:** Stock (extends *Scanning*)
- **What it does:** The Scan button opens the camera on "Open stock item". Switch the action inside the overlay to "Set to <level>" and every item you scan takes that level without closing the camera — a quick way to walk the pantry marking things out. A barcode Dora doesn't know opens New item prefilled (from Open Food Facts where it can).
- **What controls it:** Scanning switch (`/settings/admin/system`).
- **Source:** FU-378, `scanActions.ts`.

##### Exporting your stock
- **Group:** Stock
- **What it does:** Export → CSV or Print / Save as PDF of exactly the rows currently shown (filters and search applied); with nothing filtered, everything.
- **Source:** `useStockOverviewExport`.

##### How stocktake works *(extend the existing entry)*
- Add paragraphs: **Three parts.** *Review* — items Dora is fairly sure about from your shopping and cooking, pre-ticked; agree in one tap or untick to check yourself. *The walk* — the rest, least-certain first: Still correct · set the level · Skip (just for this run) · Push 3 days (no check recorded) · Mute (stops asking; un-mute on the item). *Dora's stopped tracking these* — items that left the rotation since your last stocktake: say you still keep them (set a level), mute, delete, or leave them be. At the end anything you marked low or out can go on a list in one go.
- **What controls it:** `/settings/admin/system/stocktake` (switch, default cadence, auto-tuning, new-item default); per-item Stocktake toggle on create and on the item.
- **What it costs / might get wrong:** With the install switch off nothing is ever due and `/stocktake` says so.

#### B3. DoraBot corpus delta
Append to `app_knowledge.py` Stock paragraph:
```
  Rows outline when something needs you (expired, expiring soon, an essential
  that's low or out — one rule shared with the bell), dim when out but not
  essential, and the level square wears a dashed ring when Dora's hunch
  disagrees or a stocktake check is due. Bulk select handles add/remove from a
  list, move, restock, waste and QR labels for many rows at once; Scan can open
  an item or set every scanned item to a level. Stocktake (when switched on)
  runs in three parts — agree with what Dora is sure about, walk the uncertain
  items least-certain first (Still correct / set level / Skip / Push 3 days /
  Mute), then tidy items that dropped out of rotation — and offers to put
  anything that went low or out on a list.
```

---

## Chunk 06 — Stock-Item Detail
*Source: [`CHUNK_06_stock_item_detail.md`](../05_investigations/finalisation/CHUNK_06_stock_item_detail.md) · analysed 2026-10-23*

### B. Help content — Stock-Item Detail

#### B1. Current help audit
Stock group already carries *Barcodes*, *QR label*, *Substitutes* (all accurate), *The Buy / Wait / Skip ring on the cart button* (describes the row/line badge, not the card), and *Link a product to a stock item* — **stale**: it says "link a product on the detail page", but the detail page's *Find & link* opens the external companion and linking happens from My Products' "Link to stock item…" (the page comment at `StockItemDetailPage.vue:2531–2534` says so). Nothing explains the page itself: which rows save when, what *Updated* means, the three cards, *Your prices* (the "Usually" median, 3-sample floor, the per-100g denominator, receipts vs logs, the dimension rule), the full-history chart's two line styles, preferred buys vs products, nutrition linking, the Lists ★, the History feeds and the truncation footer, or why Delete can be refused. Tooltips on Essential / Opened / Stocktake / Preferred buys are good one-liners and stay.

#### B2. Help entries
Group **Stock** (new entries; sentence-case titles; `path: '/stock'`):

1. **The stock item page** — summary: "Open any item for its own page: on a desktop it opens beside the list, on a phone it takes the screen. Every row on the Overview is its own editor — pickers, toggles and dates save the moment you change them; the name and notes save when you leave the field. *Updated 3d ago* under the level is when the level last changed. Products, Recipes, Substitutes, Scanning, Lists and History each have a tab; a tab is hidden when the feature behind it is switched off for the install."
2. **Dora's three cards on an item** — "At the top of an item sit up to three collapsed cards, in the order of the questions they answer: *Dora thinks …* is her inferred level and why (see *How Dora infers your stock*); *N planned meals need this* is what your upcoming plan wants of it, graded by your recorded level (Out blocks a meal, Low is a watch); *Should I buy it?* is the verdict — with money features on the plan reason folds into the verdict instead. Each opens to its reasoning. None of them is an alert; they are commentary beside the level you recorded."
3. **Your prices** — "Dora keeps your own price record for an item from two sources: prices you log here (*Log a price*) and prices harvested from finished shopping lists. *Usually $X / 100 g* is the **median** of the last 12 months, shown once there are three prices, always per the install's shelf denominator (per 100 g / 100 ml, or per kg / L for big packs; per lb / oz on a US install). *Paying more than usual* means the latest price is more than 15 % over that median. The *Current shelf prices* line is what linked products cost right now and never counts toward the median. One rule to know: the headline follows the **unit family of your most recent price** — log one price per piece for an item you usually price by weight and the figure switches to per piece until you log by weight again." (FU-707/FU-876 are the open design calls; the copy states the current rule honestly.)
4. **The price history chart** — "*Full history* on the Your prices card draws your own logged prices as a solid line with dots, store offers for linked products as a faint dashed line in the same colour, and your usual price as a dotted reference. Everything is per the same unit so the lines can share one axis. Hover for exact values; the legend names each line. Where it says *above usual*, the latest price is over your median." 
5. **Preferred buys** — "A free-text reminder of what you actually buy for an item — *Vitasoy Oat Milky 1 L* — listed A–Z under the Overview. It is a note to yourself, not a product: no prices, no store. When the Products feature is on this section hides, because linked products answer the same question with real prices; your preferred buys are kept and come back if Products is turned off."
6. **Nutrition on a stock item** — "With nutrition in *complex* mode an item can be linked to a food in the nutrition catalogue so recipes using it can total their energy. Dora suggests a match from the name — marked *Suggested* or *Possible match* and never saved until you tap *Use this*. Search yourself with the magnifier; *Not a food* stops Dora asking about that item (linking a food later un-ignores it). *Details* shows the per-100 g panel; only the nutrients the source states are shown — a missing one is left out, never shown as zero. In *simple* mode calories are typed on the recipe and this row does not appear."
7. **Expiry, opened, and the +N buttons** — "The calendar glyph and the date both open the picker; the ✕ clears it; +1d / +7d / +14d push it. Marking an item *Opened* asks whether to shorten its expiry — Skip keeps the date, Cancel changes nothing. Every change is kept as a trail on the History tab (*Set*, *Pushed +7 days*, *Cleared*), so an item you keep pushing back shows up for what it is." (Adjust after 06-R1 lands: "+1d counts from today or the current expiry, whichever is later.")
8. **An item's history** — "The History tab merges everything Dora knows about one item into one timeline, newest first: level changes (read as *Restocked* or *Dropped to*), waste you logged, lists it was added to, what you actually *bought* (a ticked line on a finished list, with price and store when captured), recipes you *cooked* that use it, the expiry trail, plus *Opened* and *Checked (still correct)* from its current state. Each kind keeps its latest 50; *N older events not shown* at the bottom is the honest count of what was cut."
9. **Linked products on an item** — rewrite of *Link a product to a stock item*: "With Products on, the Products tab lists the catalogue products linked to this item, cheapest first with the cheapest outlined, each with its current price, a trend sparkline, its own cart button and a link to the store. Linking happens from **My Products** (*Link to stock item…*) or when the Product Search companion pushes a product in; *Find & link* here opens that companion. Unlinking clears any shopping-list line, template line or recipe ingredient that had chosen that product."
10. **Deleting a stock item** — "Delete removes the item and its history, prices, substitute links and barcodes. Dora refuses while the item is an ingredient of any recipe and names them — remove it from those recipes first. Shopping-list lines that pointed at it keep their text."

Also: fold a *"Lists tab: ★ marks the list the cart button adds to"* sentence into the existing shopping-list quick-add entry (Chunk 3's B2) rather than a new entry.

#### B3. DoraBot corpus delta
`app_knowledge.py` Stock paragraph (L14–20) names only "adjust stock level, link products, see which recipes use it, set expiry, mark as opened, push expiry". Add one paragraph: *"An item's page also holds: Dora's inferred level and the buy verdict (money on), planned-meal demand from the next fortnight, your own price record (logged + harvested from finished lists, median 'usually' price, full-history chart), preferred-buy notes (hidden when Products is on), a nutrition-catalogue link in complex mode, substitutes with notes and ratios, direct barcodes + a printable QR label (scanning on), the lists it is on, and a merged history timeline."*

---

## Chunk 07 — Zero-Input Pantry (P8-07)
*Source: [`CHUNK_07_zero_input_pantry.md`](../05_investigations/finalisation/CHUNK_07_zero_input_pantry.md) · analysed 2026-10-23*

### B. Help content — Zero-Input Pantry

#### B1. Current help audit
*The "Dora thinks…" hint* (HelpPage L359) is accurate for the stock surface (dashed ring, picker header, silence on agreement, Settings → Assistant). The stocktake guide (L426) explains belief-ordered walks. Nothing explains: the three **other-surface hints** and their wording (*May be short* / *May be cookable* / "you may be out of…"), that they default **off**, the **quick-check** suggestion, what *confidence* means and why *Out* is never confident, or how cooking feeds the belief. The Settings InfoTips are good one-liners and stay. DoraBot's corpus has **zero** mentions of inference.

#### B2. Help entries
Group **Stock** (new; sentence-case; `path: '/stock'` unless noted):

1. **How Dora works out what you have** — "Dora's guess is a *band* — out, low or stocked — never a count. She starts the clock at your last purchase (a ticked line on a finished list with a price), estimates how long a buy lasts from the usual gap between your purchases, and moves the clock forward faster each time you cook with the item. Three-quarters of the way through a usual cycle she thinks *low*; past it, *out*. Confidence comes from how much history there is and how far she is extrapolating — she can be sure you're stocked or low, but she is deliberately never *sure* you're out, because an unlogged top-up is always possible. A level you set or confirm in the last three days wins outright: she echoes it and says *Updated today* instead of guessing."
2. **Hints on other pages** (`path: '/settings/assistant'`) — "By default Dora's opinion shows only on the Stock pages. Three more switches under Settings → Assistant → Zero-Input Pantry put the same opinion where stock items turn up: **Cookbook** flags a recipe *May be short* when it reads cookable but a required ingredient is believed out, and *May be cookable* when everything recorded as missing is believed back; **Shopping list** adds a *Dora thinks you may be out of…* list beside an open list — nothing is added for you; **Meal planner** marks an uncooked planned meal whose ingredient has probably run out since you planned it. These only ever add a remark: cookability, your lists and your plan's shopping figures are unchanged. They are off until you turn them on, because they annotate pages you opened for something else."
3. **Quick checks** — "Dora never asks you to count the pantry. When a decision is about to rest on an item she is unsure of — it's on a list you're building, or a meal in the next week needs it — she asks one question: *Still have Rice?*, at most three at a time, least-certain first. Open the item and set or confirm the level; that pins her belief and the question goes away."
4. Extend *The "Dora thinks…" hint* with one sentence: "Confidence is shown as high / medium / low; only a medium-or-better disagreement is ever remarked on outside the Stock pages."

#### B3. DoraBot corpus delta
Add to `app_knowledge.py` after the Stock paragraph: *"Zero-Input Pantry: Dora infers each item's level (out / low / stocked, with a confidence and a one-line reason) from purchases on finished shopping lists, the usual gap between buys, and cook-mode consumption. The recorded level is always the source of truth; the inference is a remark. It shows on the stock rows and item page by default and, if the user turns them on in Settings → Assistant, as hints on the cookbook ('May be short' / 'May be cookable'), shopping lists ('you may be out of…') and the meal planner. A low-confidence belief on an item a pending shop or planned meal depends on produces a 'Still have X?' quick-check suggestion."*

---

## Chunk 08 — Dashboard
*Source: [`CHUNK_08_dashboard.md`](../05_investigations/finalisation/CHUNK_08_dashboard.md) · analysed 2026-10-23*

### B. Help content — Dashboard

#### B1. Current help audit
HelpPage has **no Dashboard group**; the only mention is inside a meals entry ("the dashboard shows the next entry on the home page" — stale: the "Next up" callout is gone). The hero hint pool (21 hints, fact-checked 2026-09-04) is the surface's de-facto help and is good; it should stay the *rotating* channel while the guide carries the full explanations. DoraBot's corpus (L14–15) still describes "quick stats, items needing attention" — both cards were cut on 2026-09-04.

#### B2. Help entries
New group **Dashboard** (icon `ICONS.dashboard`), `path: '/'`:

1. **Your dashboard** — "The home page is a set of cards you own: **Cards** (top right) shows, hides and reorders them, and the layout is saved to your account, so it follows you between devices and each person in the household has their own. A card whose feature is off for the install — My budget without money features, Price drops without products — is hidden from the grid and the menu rather than shown empty. Everything refreshes each time you come back to the page; there is no refresh button because there is nothing it would add."
2. **Kitchen health** — "One number for how the kitchen is doing, from four signals over the last 30 days: **Waste** (every logged waste event costs ten points), **Budget** (how far over this period's target you are; skipped without a target, absent entirely when money features are off), **Freshness** (the share of expiry-tracked items that are past their date) and **Plan coverage** (how many of the next week's planned meals you could cook right now). A signal with nothing to score says *not counted* and is left out of the average rather than scored zero. The small arrow compares today's number with the same number a week ago; plan coverage looks forward, so it never moves the arrow."
3. **Next to cook** — "The next meals somebody actually has to cook. In a fresh-cooking household that is simply the next planned meals, in day then meal-slot order. With batch cooking on, meals the frozen pool already covers are left out, so the card shows only what the pool is short of plus meals you marked *cook fresh*. A badge appears only when there is work to do first — *Missing 2* or *3 to link*. **Cook** opens cook mode at the batch's yield, the same figure the planner uses."
4. **Use it up** — "What's about to go off, expired first, inside the *expiring soon* window set under Settings → Alerts — and the recipes that would use it, ranked by how many of those items each one clears. *See more* opens the cookbook filtered to recipes using expiring ingredients. Only required ingredients count; an optional one is not a reason to cook something."
5. **What's coming** — "A fortnight at a glance. Each day carries up to three dots: green for planned meals, red for items expiring that day, blue for a shopping list dated that day. Tap a day for the list. It reads the same feed as the bell's upcoming events, so the two never disagree."
6. **Restock radar** — "Items that went **low or out in the last 30 days**, most recent first, with the app's level dot, how long ago it changed, and the same cart button the stock rows have. *Planned* means a meal in the next fortnight still needs it. Something that has been out for months is not shown here — it is on the Stock page filtered by level, which is where everything you're out of lives."
7. **My budget** — "What you've spent this period against the household budget, with what's left or how far over you are, and underneath, the total still to buy on your open lists — a forward-looking figure, not spend. Spend counts ticked lines on finished shopping lists with a price. Set the budget and its period under Settings → Money."
8. **Price drops** (opt-in, products) — "Tracked products at a genuine new low — lower than any price Dora has seen for them — with the store and the stock item they're linked to. It only ever claims a drop against its own history, never against a retailer's ticket price."
9. **The message of the day** — "The line beside Dora is a weekday-flavoured greeting that stays the same all day, and the callout under it is a tip about something in the app that is easy to miss. Tips about money or products are not shown on an install that has those features off."

Also: fix the stale meals sentence at `HelpPage.vue:459` ("the dashboard shows the next entry on the home page" → "Next to cook on the dashboard lists the next ones to cook").

#### B3. DoraBot corpus delta
Replace `app_knowledge.py` L14–15 with: *"Dashboard (home): Kitchen health score (waste, budget, freshness, plan coverage over 30 days), Next to cook (batch-aware), Use it up (expiring items + recipes that use them), What's coming (14-day calendar of meals, expiries, shopping), Restock radar (recently low/out, 'Planned' when a meal needs it), My stock (level donut), My budget (money on) and opt-in Price drops (products on). Users show, hide and reorder cards from the Cards menu; the layout is per user."*

---

## Chunk 09 — Alerts + Suggestions
*Source: [`CHUNK_09_alerts_suggestions.md`](../05_investigations/finalisation/CHUNK_09_alerts_suggestions.md) · analysed 2026-10-23*

### B. Help content — Alerts + Suggestions

#### B1. Current help audit
HelpPage has **no Alerts or Notifications group**; `AttentionRulesDialog` (reachable from the Stock guide) explains the row outline well and says "Turning a kind off under Settings → Notifications turns off its outline too" — accurate. Nothing explains: the bell's badge rule, what each of the eight kinds means and when it fires/clears, snooze vs dismiss and the *episode* rule, the discard window, push setup (user + admin), the evening brief, price watches, or Dora's suggestions and how they differ from alerts. The Notifications InfoTips are good one-liners and stay. `AttentionRulesDialog` still says "Due for a stocktake check" unconditionally (FU-700) and "open / in-use" (FU-711). DoraBot's Alerts paragraph is accurate; it says nothing about suggestions, push or the brief.

#### B2. Help entries
New group **Alerts & notifications** (icon `ICONS.notifications`), `path: '/settings/notifications'` unless noted:

1. **The bell** (`path: '/'`) — "The bell in the header is where Dora puts the things that need you. The number on it counts the **actionable** ones — expired food, an essential that's low or out, an item expiring soon, a shopping day you've missed, a price watch that hit — and turns red when any of them is urgent. Lower-key nudges (an unplanned week, a shopping day coming up, meals to confirm) are listed in the panel but never counted. Tap a card to go to the thing; the buttons under it act on it right there — push or clear an expiry, log waste, change the level, add to a list, find recipes."
2. **What each alert means** — the eight kinds, one line each: *Expired* (past its date; high) · *Expiring soon* (inside the household's window, set by an admin; medium) · *Essential low/out* (you flagged it essential and it's low or out; high — a non-essential running low is **not** an alert, the stock row already says it) · *Did you forget your shopping?* (a list's planned day has passed and it's still open; medium) · *Shopping day* (a planned shop in the next three days; low) · *No meals planned for next week* (low) · *Past meals need confirming* (the reconcile queue is long enough to be worth a walk; low; absent when meals reconcile automatically) · *Hit your price* (a product you watch is at or under your price; medium; money features only).
3. **Snooze, dismiss, and why alerts come back** — "Every alert is about one **episode** — this expiry date, this run-out, this shop day. **Dismiss** hides it until that episode is over; the next pack of apples, the next time an essential runs out, is a new alert. **Snooze** hides it for seven days and lists it under *Snoozed* in the panel, where you can bring it back. *Dismiss all* dismisses what's on screen now. *Discard alerts after N days* (Settings → Notifications) quietly drops anything whose episode began longer ago than that, as if you'd dismissed it. There is no read/unread — dismiss is the one way to put an alert away."
4. **Choosing which alerts you get** — "Settings → Notifications → *In-app alerts* lists every kind with a switch. Off means the kind is gone for **you** everywhere — the bell, its count, the stock rows' outlines and push — and leaves everyone else's alerts alone. A kind's weight (how loud it is) is fixed; what you choose is whether you hear it at all. The expiring-soon window is household-wide and lives under Settings → Admin → System → Alert thresholds."
5. **Push notifications** — "Push needs three things: an admin has set VAPID keys (Settings → Admin → System → Push; generate a pair with `py_vapid`), this browser supports web push (on an iPhone the app must be added to the home screen first), and you've switched *Push notifications on this device* on and allowed the permission. Each device subscribes separately. Dora pushes **newly fired actionable** alerts, hourly, once each — never the low-key nudges — and a tap opens the bell panel. Turning the switch off removes this device only."
6. **The evening brief** — "One notification at 7pm in your household's timezone with tomorrow's meals and any shopping day due. It rides push, so push has to be on for the device. It only arrives when there's something to say; an empty evening sends nothing."
7. **Price watches** — "A watch on a product (set from Price history or My products) fires a *hit your price* alert when the shelf price is at or under your figure. Your watches are listed under Settings → Notifications with a remove button. Money features only."
8. **Dora's suggestions** (`path: '/'`) — "Different from alerts: suggestions are Dora's *ideas*, shown as cards at the top of her chat and counted on her bubble. *Use X soon* (expiring within three days), *You're over budget*, *You're probably due for X* (your buying rhythm says so), *Buy less X?* (three or more waste events in 90 days), *Still have X?* (a quick check when a decision depends on an item she's unsure of), and *Past meals need confirming*. **Why?** shows her reasoning. Snooze hides one for a day, Dismiss until the condition changes; at most eight show at once and every kind gets at least one slot. Dismissing a suggestion hides it for the whole household." (09-D1 — state the current behaviour honestly.)

Also: fix `AttentionRulesDialog` copy for FU-700 (gate the stocktake sentence on `stocktake_enabled`) and FU-711 ("Opened").

#### B3. DoraBot corpus delta
Append to the Alerts bullet (`app_knowledge.py` L39–45): *"Alerts are about one episode each; dismiss holds for that episode, snooze hides for 7 days, and a per-user discard window drops old ones. Push (VAPID, per device, actionable kinds only, hourly) and a 7pm evening brief are under Settings → Notifications. Dora's **suggestions** are separate: cards in her chat (use soon, over budget, probably due, buy less, quick check, meals to confirm) with Why?, Snooze 1d and Dismiss."*

---

## Chunk 10 — Products / Price History / Deals
*Source: [`CHUNK_10_products_history_deals.md`](../05_investigations/finalisation/CHUNK_10_products_history_deals.md) · analysed 2026-10-23*

### B. Help content — Products / History / Deals

#### B1. Current help audit
`HelpPage.vue` has two entries touching this surface, both stale:
- **"Link a product to a stock item"** (L401–404, under Stock): says "On the detail page…"; the grey/green `ProductLinkButton` on My Products is now the primary place to link/unlink. Rewrite.
- **"Search for products"** (L469–472, under *Shopping & deals*, `path: '/'`): "opens an admin-configured external search surface… pushes data back into Dora via the ingestion seam" — jargon ("seam"), and `path: '/'` is wrong. Rewrite; point at `/my-products`.
No entry exists for My Products, custom products, pack count, price watches, price history, the weekly deals email, or deal quality. `app_knowledge.py` (DoraBot corpus) has **zero** mentions of My Products / price history / custom products.

#### B2. Help entries (one per feature / auto-behaviour)
New group **"Products & prices"** (icon `ICONS.shopping_bag`):

| # | Title | Summary (plain voice, D-copy) | path |
|---|---|---|---|
| H1 | What a product is | A product is one thing at one shop with a price — "Coles brand milk 2L". A stock item is the thing in your kitchen. Link a product to a stock item and its price rides along with your pantry record; you can also use products on their own. | `/my-products` |
| H2 | Finding products | Product Search opens the companion app your admin set up; what you save there lands in My Products. If the menu has no Product Search, ask your admin to set it up under Settings → Admin → Product data. | `/my-products` |
| H3 | Cards or compact rows | Switch with the toolbar button; Dora remembers your choice. Cards show photos and every action; rows show the essentials and the two everyday buttons. | `/my-products` |
| H4 | Link or unlink a product | The grey broken-link button means "not linked" — tap it to pick a stock item. Green means linked — tap it to unlink. The chip beside it names the stock item and opens it. | `/my-products` |
| H5 | Add a product to a shopping list | Linked products add under their stock item with that product chosen. Unlinked ones add as a product-only line, marked as such. | `/my-products` |
| H6 | Custom products | For a shop Dora can't check — a butcher, a market stall. You type the price, size and store; Dora never refreshes it, and marks it **Custom** so you can tell. Only custom products can carry your own photo. | `/my-products` |
| H7 | Items in the pack | A 700 g carton says nothing about how many eggs are in it. Set "items in the pack" on any product so a recipe's "3 eggs" can be priced. | `/my-products` |
| H8 | Tracking prices | "Stop tracking prices" hides a product from deals and the weekly email without deleting it; show it again with the "Show untracked" filter. | `/my-products` |
| H9 | Deleting a product | Gone for good, with its price history and any watch on it. Finished shopping lists keep their record of it; live lists drop the line. | `/my-products` |
| H10 | Bulk select | Select… offers All visible, On deal, Inactive, and the stock-aware helpers (Low stock on deal, Out of stock on deal, Essential + low on deal). Then add the on-deal ones to a list, unlink, stop tracking or delete in one go. | `/my-products` |
| H11 | Stock items without products | The toolbar count is stock items that no tracked product is linked to. It lights up when there are any. | `/my-products` |
| H12 | Watch a price | ⋮ → "Alert me on a price drop", enter the pack price you'd buy at. One watch per product; saving again replaces it. When a new offer lands at or below it, you get a bell alert (and a push if you have them on) — once per offer. | `/my-products` |
| H13 | Price history | Compare up to five products' advertised prices over 30 days, 90 days, a year or all time. Each card shows the current price, discount, the all-time low, and — if you've logged prices yourself — your usual price. A product with no offers shows your own logged prices instead. | `/price-history` |
| H14 | Weekly deals email | Settings → Notifications: pick a day; the mail arrives at 7 am your time with the best specials across your tracked products — compact (up to 20 lines) or expanded (up to 10 with detail). A quiet week sends nothing. Needs a verified email address. | `/settings/notifications` |
| H15 | Is it really a deal? | Dora checks a special against the product's own 90-day history and what you've actually paid. A "special" that's dearer than your usual price is called out, never celebrated. | `/stock` (Buy verdict) |

Rewrites: fold the old "Link a product…" into H4 (delete the Stock-group entry) and replace "Search for products" with H2.

#### B3. DoraBot corpus delta
Append a **Products** paragraph to `app_knowledge.py`: *"My Products holds the products you saved from Product Search (an external companion the admin configures) plus any custom products you typed in for shops Dora can't check. A product can be linked to one stock item (grey broken link = unlinked, green = linked) or used on its own. Each product can carry an items-in-pack count, and you can watch a price: one watch per product, which fires as a price-drop alert once per new offer at or below your figure. Price history compares up to five products over a range and shows your own usual price where you've logged one. The weekly deals email goes out at 7 am on the day you pick, only to verified addresses, and only when something is on special. Dora never looks prices up live — everything comes from what was pushed in."*

---

## Chunk 11 — Assistant (Dora)
*Source: [`CHUNK_11_assistant.md`](../05_investigations/finalisation/CHUNK_11_assistant.md) · analysed 2026-10-23*

### B. Help content — Assistant

#### B1. Current help audit
Two surfaces exist and both are partly stale:
- **`HelpPage.vue` Dora group** (~8 entries, L505–560): page awareness, which browsers speak, free-form questions need AI, set up AI (per account), "unavailable" banner, network topology, API-key encryption. Good; nothing on Basic-mode actions, suggestions-in-chat, confirm cards, voice input, muting, the first-time hint, turning Dora off, or rate limits.
- **`DoraHelpPage.vue`** (`/help/dora`): hand-maintained. The AI-tools list is missing **13 of 40** tools (`adjust_recipe_meals`, `budget_status`, `cook_recipe`, `expiry_rescue`, `list_suggestions`, `meals_cooked_in_range`, `meals_in_pool`, `meals_shortfall`, `purchase_price_stats`, `spend_by_category`, `spend_year_over_year`, `trim_list_to_budget`, `waste_insights`); the Basic list omits `add_to_list` (the one action verb), `report_issue`, `stuck`, `version`'s sibling; the AI card says "a local language model (Ollama)" and links "Settings → System" (`{path:'/settings', query:{tab:'system'}}` — pre-redesign, 11-R6); tips say "three suggestion chips" (four) and "the AI / Basic **chip**" (slider); `search_products` says "across the configured stores" (the catalogue is ingested; Product Search is external).
- **DoraBot corpus** (`app_knowledge.APP_OVERVIEW`) — stale nav (Recipes/Locations/System), see 11-R25.

#### B2. Help entries (one per feature / auto-behaviour)
Add to the existing Dora group (keep its voice):

| # | Title | Summary | path |
|---|---|---|---|
| H1 | Basic mode can add to your list | Type "add milk and eggs" or "need to buy rice". Dora matches names against your pantry and adds the clear ones to your one draft list; anything ambiguous she asks about, never guesses. | `/` |
| H2 | Dora never changes anything on her own | In AI mode every change — a stock level, an expiry, a meal, a list line — arrives as a card you Confirm or Cancel. Until you tap Confirm, nothing has happened. | `/` |
| H3 | What Dora can see | Your household's own data in this install: stock, recipes, lists, meal plan, prices you logged, alerts. Never another household, never the web. | `/` |
| H4 | Suggestions in the chat | The number on the launcher is how many suggestions Dora has (the same ones the dashboard card shows). Open the chat to Accept, Snooze a day, Dismiss, or ask Why. | `/` |
| H5 | Basic or AI — the slider | Basic is always on and works offline. AI needs a connected provider (Settings → Assistant); until one is verified the slider is dimmed and tapping it takes you there. If AI drops out mid-chat, Dora falls back to Basic for that message. | `/settings/assistant` |
| H6 | Talking to Dora | Tap the mic (Chrome and Edge; Firefox has no speech recognition), speak, tap again. Your words land in the box so you can read them before sending. | `/` |
| H7 | Hearing Dora | The speaker button has Dora read her replies aloud — her neural voice from the server when installed, your browser's voice otherwise. It stays on or off per account. On a phone, a reply that comes after a long think may not autoplay. | `/settings/voice` |
| H8 | Turning Dora off | Settings → Assistant → "Show digital assistant chat bubble". Off hides the launcher everywhere for your account only. The one-time "Hi! I'm Dora" tip is also per account. | `/settings/assistant` |
| H9 | Paid providers and privacy | With OpenAI, Anthropic or Gemini your messages — and the data Dora looks up to answer them — are sent to that provider. Ollama keeps everything on your own machine. | `/settings/assistant` |
| H10 | Why Dora says "slow down" | Twenty questions a minute per person is the ceiling, so a stuck script can't run up your provider bill; Dora answers in Basic until the minute is up. | `/` |

Rewrites: `DoraHelpPage` tool + intent lists become generated from the registry (11-R26); fix the Settings → System link (11-R6); "three chips"/"chip" copy.

#### B3. DoraBot corpus delta
This chunk owns the corpus. Deliverable is 11-R25 (rewrite `APP_OVERVIEW` for the current shell, folding in the ten paragraphs chunks 1–10 queued) **shaped by 11-D1** (a short routing guide in the prompt + an `app_help` tool that serves the full help corpus on demand). The paragraph for *this* surface: *"Dora works in Basic mode (always on, offline, rule-based: lookups, one add-to-list verb, conversions, substitutes, page help) or AI mode (per account, after a provider is connected and verified under Settings → Assistant). In AI mode she reads your data through tools and proposes changes as Confirm cards; she never writes on her own. She can speak replies and take dictation, carries the same suggestions as the dashboard, and can be hidden per account."*

---

## Chunk 12 — Reports / Memory (P8-09), Waste, Budget
*Source: [`CHUNK_12_reports_memory.md`](../05_investigations/finalisation/CHUNK_12_reports_memory.md) · analysed 2026-10-23*

### B. Help content — Reports / Waste / Budget

#### B1. Current help audit
`HelpPage.vue` has **no** entry for Reports, Kitchen memory, Price changes, waste logging or the budget (the only "report" hits are the Report-an-issue button). `app_knowledge.APP_OVERVIEW` names none of them either. The in-page text is good (lede, coverage lines, honest empties) but nothing explains what the figures are built from, which is the first question a money report gets.

#### B2. Help entries (one per feature / auto-behaviour)
New group **"Reports, budget & waste"** (icon `ICONS.insights`):

| # | Title | Summary | path |
|---|---|---|---|
| H1 | What Reports is built from | Your own records only: finished shopping lists with prices, cooks logged in cook mode, prices you logged, and waste you marked. Nothing is looked up. A list you never finished, or a line you never ticked, isn't spend. | `/reports` |
| H2 | The range and "All time" | Every card answers for the range you pick; the dates it covers sit under the picker. "All time" starts at your first record. The waste card looks back at most a year and says so. | `/reports` |
| H3 | Where the money went | Spend has three views: by store (in each store's own colour; "No store set" when Dora couldn't tell), by stock group, and against the same-length period before. Items with no price are counted and named, never silently dropped. | `/reports` |
| H4 | "Under shelf price" | The support line under Spend adds up what you paid below the store's listed price on finished lists. It only appears when products are on and there was a saving. | `/reports` |
| H5 | Kitchen memory | Cooks are the times you finished a recipe in cook mode; meals are the portions you said you made; "different recipes" is your repertoire in the range. The line about recipes you haven't cooked always looks at the last year, whatever range you pick. | `/reports` |
| H6 | Bought most | How many finished shops each item was actually bought on in the range. | `/reports` |
| H7 | Price changes | For items you've logged two or more prices for, the first and last price in the range, quoted per the shelf unit (per 100 g, per L, each). Tap an item to see the chart with your usual price and any store offers behind it. Items with one price, or prices in different units, are counted but not shown. | `/reports` |
| H8 | Logging waste | On a stock row, open the expiry menu and choose Mark as wasted, then tap a reason. The expiry clears; Undo within five seconds puts both back. Bulk select logs many at once. The Waste card and Dora's "what am I wasting" answer read these. | `/stock` |
| H9 | Reports with money off | Waste and Kitchen memory stay; Summary, Spend and Price changes go, and their endpoints refuse. | `/reports` |
| H10 | The household budget | Settings → Budget: one amount for the household, weekly (Monday start) or monthly. Spent is what you ticked on finished lists in the period; projected is what's on open lists dated in it; the dashboard card and "N of your last 6 weeks over" read the same numbers. Any member can set it. | `/settings/budget` |

#### B3. DoraBot corpus delta
Paragraph for `app_knowledge.py` (lands per 11-D1): *"Reports answers four questions from the household's own records: where the money went (by store, by stock group, or against the previous period), what gets thrown out, what we actually cook and buy, and which of our own items got dearer or cheaper. Everything comes from finished shopping lists with prices, cook-mode cooks, logged prices and marked waste. The budget is one household figure (weekly or monthly) set under Settings → Budget; spent counts only ticked lines on finished lists in the period."*

---

## Chunk 13 — Settings shell
*Source: [`CHUNK_13_settings_shell.md`](../05_investigations/finalisation/CHUNK_13_settings_shell.md) · analysed 2026-10-23*

### B. Help content — Settings shell

#### B1. Current help audit
`HelpPage.vue` group "Settings & admin" holds three entries — 'Theme, font, and text size', 'Manage other users (admin)', 'Manage stores (admin)'. 'Theme, font, and text size' predates the Mode/Theme split (round-19) and the 2026-09-03 Appearance rename — it should say Mode (System/Light/Dark) × Theme family, and name `xl`. Nothing covers the profile picture, notifications channels, voice engines, stock locations' three fixed levels, taxonomy editing, the Region page, the encryption-key requirement, deactivate-vs-delete, or the audit log. `APP_OVERVIEW` (chunk 11 owns the rewrite) mentions Settings only as a destination.

#### B2. Help entries (one per feature / auto-behaviour)

##### Settings and Admin are two modes
- **Group:** Settings & admin
- **What it does:** Personal settings (Account, Preferences, Kitchen setup, About) and install-wide Admin settings (Install, Kitchen features, Data & access) are separate modes; admins switch with the pill at the top.
- **When it fires / how to trigger it:** Header avatar → Settings; admins see the Settings | Admin toggle.
- **What controls it:** admin flag on the account (Admin → Users).
- **What it costs / might get wrong:** Kitchen setup is shared by the household even though it sits on the personal side — it's "what this kitchen has", not "what I prefer".
- **Related:** Who can change what · Manage other users (admin).
- **Chip:** none. **Source:** `SettingsShell.vue:17–40`, owner calls 2026-08-14/17, 2026-09-03.

##### Who can change what
- **Group:** Settings & admin
- **What it does:** Anyone can edit their own account, appearance, notifications, voice, and the shared kitchen setup (locations, groups, stores, recipe vocab, budget). Only admins change install-wide behaviour (region, money, email, push, stocktake, cooking, image quality, users).
- **What controls it:** `is_admin`; non-admins redirected from `/settings/admin/*`.
- **What it costs / might get wrong:** A member can rename or delete a store everyone uses — kitchen setup is deliberately not admin-gated.
- **Related:** Settings and Admin are two modes. **Chip:** none. **Source:** `router/index.ts:154`, shell nav groups.

##### Appearance: mode, theme, font, text size (reword of 'Theme, font, and text size')
- **Group:** Settings & admin
- **What it does:** Pick a Mode (System follows your device, Light, Dark), a Theme family (Pesto, Lemon Tart, Blueberry, Cherry Cola, Sourdough, Salt & Pepper, Dragonfruit), a font, and one of four text sizes (Small 87.5 % · Medium · Large 112.5 % · Extra large 125 %).
- **What controls it:** `/settings/preferences`; saved per account, follows you across devices.
- **What it costs / might get wrong:** System mode re-evaluates on the device's dark-mode switch without a reload; text size scales the whole UI, so very large on a small phone wraps labels.
- **Related:** Profile picture. **Chip:** none. **Source:** `PreferencesSettings.vue`, `themeService.ts`, `tokens.scss:294–298`.

##### Profile picture
- **Group:** Settings & admin
- **What it does:** Upload a photo or pick a preset; it shows in the header, Account, and the admin Users list.
- **When it fires:** Saves immediately on pick/clear — no Save button.
- **What controls it:** `/settings/account`; an admin can also clear another user's picture via the API (no UI today — 13-R15).
- **What it costs / might get wrong:** Compressed on upload to the install's image policy; stored in the database, so it rides backups.
- **Related:** Image quality (admin). **Chip:** none. **Source:** `AccountSettings.vue:9–57`, `update_me.py:76–81`.

##### Username, email and password
- **Group:** Settings & admin
- **What it does:** Edit your sign-in name and email inline; change your password with your current one; all commit on one Save.
- **What costs / might get wrong:** Changing your password signs out your other devices (this one stays in). An entered email counts as verified — Dora trusts you on your own address.
- **Related:** Notifications: email. **Chip:** none. **Source:** `update_me.py:130–148`, `AccountSettings.vue`.

##### Notifications: in-app, push, email
- **Group:** Settings & admin
- **What it does:** Choose which alert kinds reach your bell and how long alerts live (7/14/30 days/never); subscribe this device to push and the 7 pm Evening brief; opt into the weekly deals email.
- **When it fires / how to trigger it:** Push needs VAPID keys (admin → Push) and browser support; email needs SMTP (admin → Email), a verified address, and product data.
- **What it costs / might get wrong:** Push is per device — turning it off here doesn't touch your phone. Unverified addresses receive nothing; the page offers "Send verification email".
- **Related:** Alert thresholds (admin) · Email and push setup (admin). **Chip:** none. **Source:** `NotificationsSettings.vue`.

##### Voice: input, output, which voice
- **Group:** Settings & admin
- **What it does:** Speak to Dora (browser speech recognition — Chrome/Edge/Safari only) and let her speak replies with either her neural voice (Piper, on the server) or your device's voice.
- **What controls it:** `/settings/voice` per user; the Piper engine path is admin → Voice.
- **What it costs / might get wrong:** Neural voices are 60–110 MB downloads on the server; without Piper installed (source installs on Windows) replies fall back to the device voice automatically.
- **Related:** Voice engine (admin). **Chip:** none. **Source:** `VoiceSettings.vue`, `VoicePicker.vue`.

##### Stock locations: zones, areas, sections
- **Group:** Settings & admin
- **What it does:** A fixed three-level map of where things live; items can sit at any level; counts roll up.
- **What it costs / might get wrong:** Deleting a zone removes its areas/sections and leaves items **unassigned**, not deleted. Search expands every match; your collapse state is remembered on this device.
- **Related:** Stock groups. **Chip:** `StockLocationsSettings.vue:3` header. **Source:** `StockLocationsSettings.vue`, `Location*` components.

##### Stock groups and recipe vocabulary
- **Group:** Settings & admin
- **What it does:** Name-only lists (stock groups, cuisines, categories, tools, meal slots, dietary tags) used as filters and pickers across the app; each row shows how many things use it.
- **What it costs / might get wrong:** Deleting one strips it from the items/recipes using it (meal slots: entries keep the label). Meal slots are the only reorderable list and the order drives the planner.
- **Related:** Stock locations · Manage stores. **Chip:** none. **Source:** `TaxonomyManagerPage.vue`, `VocabListEditor.vue`.

##### Region & locale (admin)
- **Group:** Settings & admin
- **What it does:** Currency, language/format, units system (metric / imperial / US) and household timezone — the install's "where do we live". Preview updates as you pick; "Match this device" fills zone, locale and units (never currency) and may offer the locally recognised recipe rating.
- **What it costs / might get wrong:** Timezone decides which day is "today" for meal plans, budgets and alerts everywhere; units change every dropdown immediately.
- **Related:** Money (admin). **Chip:** none. **Source:** `AdminSystemRegionSettings.vue`, `clock.py`.

##### Email and push setup (admin) — and the encryption key
- **Group:** Settings & admin
- **What it does:** SMTP details, the email on/off switch, the public URL used in emailed links; VAPID keys for web push. Passwords and private keys are stored encrypted.
- **When it fires:** Saves on blur/toggle; secret fields have their own Save/Clear.
- **What controls it:** `DORA_SECRET_ENCRYPTION_KEY` must be set in the server environment or secret saves are refused — the page shows a banner and can generate a key for you.
- **What it costs / might get wrong:** Rotating the key makes every stored secret unreadable (re-enter them). Gmail needs an App Password.
- **Related:** Notifications. **Chip:** none. **Source:** `AdminSystemEmailSettings.vue`, `AdminSystemPushSettings.vue`, `EncryptionKeyBanner.vue`.

##### Manage other users (admin) (reword)
- **Group:** Settings & admin
- **What it does:** Add users (set a password or let Dora generate a one-time one), rename, change emails and passwords, promote to admin, **deactivate** (locks them out, keeps everything) or delete (removes their sessions, alert prefs and push subscriptions; shared recipes/lists stay).
- **What it costs / might get wrong:** You can't demote, deactivate or delete yourself, or remove the last admin who can still sign in. An admin-set password signs that person out everywhere.
- **Related:** Who can change what. **Chip:** none. **Source:** `UsersAdminSettings.vue`, `users/*.py`.

##### Audit log (admin)
- **Group:** Settings & admin
- **What it does:** Every mutating request, login attempt, client crash and service event; filter by severity/action/actor/entity/request id; "Find related" follows one request; CSV export of the current page; retention 1–3650 days pruned nightly.
- **Related:** Manage other users. **Chip:** none. **Source:** `AuditLogSettings.vue`.

##### Kitchen features (admin): stock, stocktake, cooking, meal reconciliation, money, alert thresholds, image quality
- **Group:** Settings & admin
- **What it does:** One page per feature switch, each saving on change: auto-add mode + scanning/QR; stocktake master switch, new-item default, cadence, self-tuning; household headcount + fresh/batch cooking style; auto-drain past meals; money on/off; expiring-soon window; upload quality + longest edge.
- **What it costs / might get wrong:** Each flip is install-wide and takes effect for everyone on their next page load (this session refreshes immediately). Image settings are forward-only.
- **Related:** Region & locale. **Chip:** none. **Source:** `AdminSystem{Stock,Stocktake,Cooking,MealReconcile,Money,Alerts,Image}Settings.vue`.

#### B3. DoraBot corpus delta
Replace the Settings mention in `APP_OVERVIEW` with: *"Settings (header avatar) has two modes: your own — account, appearance, notifications, voice, and the shared kitchen setup (locations, groups, stores, recipe vocabulary, budget) — and, for admins, the install: users, region & units, email/push, kitchen feature switches, data & access. Install-wide switches apply to everyone."* Tool nav for settings should point at `/settings/account` and `/settings/admin/users` (chunk 11 `_TOOL_NAV` fix already covers `/settings/preferences`).

---

## Chunk 14 — Onboarding
*Source: [`CHUNK_14_onboarding.md`](../05_investigations/finalisation/CHUNK_14_onboarding.md) · analysed 2026-10-23*

### B. Help content — Onboarding

#### B1. Current help audit
`HelpPage.vue` has **no** entry about first-run, the tour, starter packs, or re-running the wizard (the only "welcome" hit is assistant copy at `:256`). `APP_OVERVIEW` says nothing about onboarding. In-wizard copy is good and honest (FU-184 pass holds). Two code comments promise a "Restart onboarding" entry in Settings → Account (`DashboardPage.vue:606–607`, `user.py:187–189`) that was never built — the only way back in is the 24-hour dashboard banner after a Skip (14-R3).

#### B2. Help entries

##### Your first run: Story then Setup
- **Group:** Dora itself
- **What it does:** A short story (why Dora, the Stock → Plan → List → Shop → Restock → Cook loop, what Dora remembers, what you can switch off) then a one-minute setup. Nothing is saved until you press Finish.
- **When it fires / how to trigger it:** First sign-in of any account; the first user of an install gets two extra steps (features + stock).
- **What controls it:** always on; "Skip onboarding" completes it immediately.
- **What it costs / might get wrong:** Skipping leaves the install on its defaults (UTC timezone, metric, Stocktakes + Auto-add on) — the dashboard reminds you for 24 hours.
- **Related:** What Finish sets up · Running setup again. **Chip:** none. **Source:** `WelcomeWizard.vue`, PROPOSAL_ONBOARDING §2–3.

##### What Finish sets up
- **Group:** Dora itself
- **What it does:** Your look (theme, font, picture); for the first user also the household (people, timezone, units), the feature switches, Dora's default locations/groups/starter items you left ticked plus your own, and optionally one demo recipe on this week's plan.
- **What controls it:** The recap on the last step lists exactly what will be written; every row has Change.
- **What it costs / might get wrong:** Items start as Stocked; the demo recipe adds three pantry items if you didn't pick them. Everything is editable afterwards in Stock / Settings.
- **Related:** Starter packs · Stock locations: zones, areas, sections (chunk 13). **Chip:** none. **Source:** `WelcomeWizard.vue:1329–1392`.

##### Starter packs and your own items
- **Group:** Stock
- **What it does:** Five packs (fridge staples, pantry basics, fruit & veg, freezer, cleaning) you tick on or off item by item; add your own with a group and location.
- **What it costs / might get wrong:** Dedupes by name — an item you already have is skipped, not duplicated. Groups/locations are matched by name to what you picked above.
- **Related:** Add a stock item. **Chip:** none. **Source:** `starter_packs.json`, `onboarding.py:456–559`.

##### Features you can switch on at setup
- **Group:** Settings & admin
- **What it does:** Spend tracking, Nutrition (simple), Stocktakes, Auto-add essentials, Batch cooking, Barcodes & QR — the same install-wide switches as Settings → Admin.
- **What controls it:** First user only; each later lives on its own Admin page (Money, Nutrition, Stocktake, Stock, Cooking, Stock).
- **Related:** Kitchen features (admin) (chunk 13). **Chip:** none. **Source:** `WelcomeWizard.vue:782–819`.

##### Running setup again
- **Group:** Dora itself
- **What it does:** After "Skip onboarding" the dashboard offers Continue for 24 hours, which reopens the wizard with your draft. There is no other way back in today (14-R3 adds one).
- **Related:** Your first run. **Chip:** none. **Source:** `DashboardPage.vue:575–625`, `/onboarding/restart`.

#### B3. DoraBot corpus delta
Add to `APP_OVERVIEW`: *"New accounts start with a short story and a one-minute setup; the first user also picks household settings, features, and starter stock. Finish applies it all at once; Skip keeps the defaults and the dashboard offers to continue for a day."* Tool nav: a `restart_onboarding` action is **not** warranted (anti-creep) — point "how do I see the tour again" at the help entry.

---

## Chunk 15 — Auth shell
*Source: [`CHUNK_15_auth_shell.md`](../05_investigations/finalisation/CHUNK_15_auth_shell.md) · analysed 2026-10-23*

### B. Help content — Auth shell

#### B1. Current help audit
`HelpPage.vue` has nothing on signing in, creating an account, forgotten passwords, email verification, first-time setup or the native instance picker; 'Manage other users (admin)' mentions that an admin can "reset a forgotten password". `APP_OVERVIEW` says nothing. The in-page copy is already good (opaque sign-in failure, anti-enumeration wording, the capability-gated "Forgot password?").

#### B2. Help entries

##### Signing in and creating an account
- **Group:** Dora itself
- **What it does:** Sign in with a username and password; "Need an account? Register" creates one (username, optional email, password of at least 8 characters — no symbol rules, just not a common password).
- **When it fires / how to trigger it:** Any signed-out visit; five wrong attempts a minute pauses sign-in briefly.
- **What controls it:** always on. New accounts are never admins; an admin promotes you in Settings → Admin → Users.
- **What it costs / might get wrong:** Sign-in failure never says which half was wrong (deliberate). The email is only used for password resets and the weekly deals mail.
- **Related:** Forgot your password · Who can change what (chunk 13). **Chip:** none. **Source:** `LoginPage.vue`, `login.py`, `register_user.py`, `auth_helpers.py:44–132`.

##### First-time setup (the first admin)
- **Group:** Dora itself
- **What it does:** A brand-new install opens on a one-time setup page that creates the first admin account and signs them in; after that the page is gone for good.
- **What controls it:** Operators can lock it to one address with `ADMIN_BOOTSTRAP_EMAIL`.
- **What it costs / might get wrong:** If you forget the very first password on a self-hosted box with no email set up, the recovery is to wipe and start again.
- **Related:** Your first run (chunk 14). **Chip:** none. **Source:** `SetupAdminPage.vue`, `bootstrap_admin.py`.

##### Forgot your password
- **Group:** Dora itself
- **What it does:** Enter your email and, if it is on an account, a single-use reset link arrives (valid 1 hour). Resetting signs out your other devices.
- **When it fires:** The button only appears when the install can actually send email; otherwise ask an admin to set a new password for you (Settings → Admin → Users).
- **What it costs / might get wrong:** The page always says "if that address is registered" — it never confirms whether an address exists.
- **Related:** Email and push setup (admin) (chunk 13). **Chip:** none. **Source:** `email_flows.py`, `capabilities.py`, `ForgotPasswordPage.vue`.

##### Verifying your email
- **Group:** Dora itself
- **What it does:** Accounts with an address get a 24-hour verification link; scheduled emails (the weekly deals mail) only go to verified addresses. The first admin is verified automatically.
- **What controls it:** Settings → Notifications offers "Send verification email" again.
- **Related:** Notifications: in-app, push, email (chunk 13). **Chip:** none. **Source:** `email_flows.py:68–143`, `NotificationsSettings.vue`.

##### Why was I signed out?
- **Group:** Dora itself
- **What it does:** Changing or resetting a password signs out every other device; an admin deactivating an account signs it out; sessions also end when the browser clears cookies.
- **Related:** Username, email and password (chunk 13). **Chip:** none. **Source:** `get_me.py`, `change_password.py`.

##### The phone app: choosing your Dora
- **Group:** Dora itself
- **What it does:** The Android/iOS app asks for your server's address once; it adds `/api` for you and checks it answers before saving. Change it later in Settings → About, or from the error screen if the saved address stops answering.
- **Related:** Install as an app (chunk 17). **Chip:** none. **Source:** `BackendSetupPage.vue`, `SplashScreen.vue:47–58`, `backendUrl.ts`.

#### B3. DoraBot corpus delta
Add: *"New installs start with a one-time setup page for the first admin. Everyone else signs in with a username and password; accounts can be created from the sign-in page and need an admin to become admins. Forgot-password works only when the install can send email."* No tool nav (pre-auth surfaces are unreachable from the assistant).

---

## Chunk 16 — Ingestion API + companion seam
*Source: [`CHUNK_16_ingestion_api.md`](../05_investigations/finalisation/CHUNK_16_ingestion_api.md) · analysed 2026-10-23*

### B. Help content — Ingestion API + API access

#### B1. Current help audit
- `HelpPage.vue:466–474` — "Search for products" (group *Shopping & deals*): *"Product Search opens an admin-configured external search surface in a new tab. The destination pushes data back into Dora via the ingestion seam."* — "ingestion seam" and "external search surface" are engineering vocabulary, not copy (D-rules: plain-English voice). Stale in spirit too: the entry routes to `/` while the link lives in the nav. **Reword.**
- `app_knowledge.py:21–22` — the same two sentences for DoraBot. **Reword** (B3).
- No entry anywhere for **API access**, keys, store mappings, or why a push was skipped. `ApiAccessSettings.vue` has no `HelpHint`. The in-page copy is good (header description, mapping explainer at :131–135, empty states, reveal-once warning) — the help entries below mostly lift it.
- `docs/INGESTION_GUIDE.md` is the producer-facing doc and is **wrong on the wire** (16-R1) — a reader following it gets a 400.
- Invisibility rule (`PROPOSAL_INGESTION_API` header): nothing below may name a scraper, companion or producer. Honoured in every entry.

#### B2. Help entries

##### Create an API key (admin)
- **Group:** Settings & admin
- **What it does:** Lets an outside program you run push products and prices into Dora. Each key is a separate "source" with its own label.
- **When it fires / how to trigger it:** Settings → Admin → API access → New key. The key is shown **once**, right after you create it — copy it then.
- **What controls it:** `/settings/admin/api-access`. Admins only. Works before any product data exists.
- **What it costs / might get wrong:** Anyone holding the key can add, update or delete products in this install (it can't sign in as you or read anything else). Lose it → revoke and make a new one; there is no "show again".
- **Related:** Disable or revoke a key · Map the store names a source uses · See whether a source is working.
- **Chip:** `ApiAccessSettings.vue:3–8` (SettingsPageHeader title slot) → `<HelpHint topic="Create an API key (admin)">`.
- **Source:** PROPOSAL_INGESTION_API §2.1; `ingestion_source_admin.py`.

##### Map the store names a source uses (admin)
- **Group:** Settings & admin
- **What it does:** When a source pushes a product under a store name Dora hasn't seen, the record is held back and the name shows as *pending* under that key. Pick which of your stores it means and the next push goes through.
- **When it fires / how to trigger it:** Automatically on the first push with an unknown name; or pre-map by expanding the key's row. A source can also name your stores by id and skip this entirely.
- **What controls it:** The *Store mappings* card under each key on `/settings/admin/api-access`. Stores themselves are managed under Settings → Stores — Dora never creates a store from a push.
- **What it costs / might get wrong:** Records pushed before you map the name are **not** queued — the source has to push them again. Clearing the picker puts the name back to pending; the bin drops the mapping entirely.
- **Related:** Create an API key · Why a push was skipped · Manage stores (admin).
- **Chip:** `ApiAccessSettings.vue:127–130` (card subtitle "Store mappings") → `<HelpHint topic="Map the store names a source uses (admin)">`.
- **Source:** FU-190; PROPOSAL_PRODUCTS_AS_OVERLAY §3.3; `store_mappings.py`, `submit_ingestion_batch._resolve_store`.

##### See whether a source is working (admin)
- **Group:** Settings & admin
- **What it does:** Each key's row shows when it was last used and running totals of records accepted, skipped and failed, so you can tell a silent source from a working one.
- **When it fires / how to trigger it:** Updated on every push, lookup or list the source makes. Refresh the page to see new numbers.
- **What controls it:** Always on — no setting. The totals never reset; revoke and re-create the key to start from zero.
- **What it costs / might get wrong:** "Accepted" counts records, not products — a product with its price is two. A re-sent batch Dora recognised as a repeat changes nothing.
- **Related:** Why a push was skipped · Create an API key.
- **Chip:** none (the caption line is the surface).
- **Source:** PROPOSAL_INGESTION_API §2.1 observability; `IngestionSourceDto`.

##### Why a push was skipped (admin)
- **Group:** Settings & admin
- **What it does:** Dora answers every record individually: *accepted*, *skipped* (store not mapped, store unknown, price already on file) or *failed* (price for a product that wasn't in the batch). One bad record never blocks the rest.
- **When it fires / how to trigger it:** In the response the source receives, and in the totals on the key's row.
- **What controls it:** Always on — no setting.
- **What it costs / might get wrong:** A batch with a field Dora doesn't know is refused **whole** (nothing lands) — that's the one case where fixing one record fixes all of them. Dora never overwrites a product you typed in yourself; a pushed match gets its own entry.
- **Related:** Map the store names a source uses · See whether a source is working.
- **Chip:** none.
- **Source:** PROPOSAL_INGESTION_API §2.7; `IngestBatchResult`; OD-2 in `_apply_product`.

##### Disable or revoke a key (admin)
- **Group:** Settings & admin
- **What it does:** *Disable* pauses a source — pushes are refused until you enable it again, mappings and totals stay. *Revoke* deletes the key for good, with its store mappings.
- **When it fires / how to trigger it:** The ⋮ menu on the key's row.
- **What controls it:** `/settings/admin/api-access`.
- **What it costs / might get wrong:** Neither removes the products the source already pushed — delete those under My products. A revoked key can't be restored; make a new one and update the program that uses it.
- **Related:** Create an API key.
- **Chip:** none.
- **Source:** `ingestion_source_admin.py` PATCH/DELETE; `IngestionStoreMapping` FK `ondelete=CASCADE`.

##### Search for products *(reword of the existing entry)*
- **Group:** Shopping & deals (unchanged)
- **New summary:** *"Product Search opens a search page your admin has set up, in a new tab. Anything you save there turns up under My products in Dora, at the store it was found."* Path → `/my-products` (chunk 10 owns the destination; today's `/` is wrong).
- **Source:** 13-R4 (members must see the link), FU-186, PROPOSAL_PRODUCTS_AS_OVERLAY §4.1.

#### B3. DoraBot corpus delta
Replace `app_knowledge.py:21–22` with:
> - Product Search: a link in the left nav that opens a search page the admin configured, in a new tab. Products saved there appear under My products.
> - API access (admin): Settings → Admin → API access creates keys an outside program uses to push products and prices into Dora. Each key shows when it was last used and how many records were accepted, skipped or failed; unknown store names wait there as "pending" until the admin maps them to a Dora store.

---

## Chunk 17 — Offline / PWA / native
*Source: [`CHUNK_17_offline_pwa_native.md`](../05_investigations/finalisation/CHUNK_17_offline_pwa_native.md) · analysed 2026-10-23*

### B. Help content — Offline / PWA / native

#### B1. Current help audit
- **Nothing.** `HelpPage.vue` has no entry for offline, install, update, wake lock, the Android app or the instance URL; `app_knowledge.py` says nothing about any of it. The only "update" copy in Help is the **backend** version banner (`HelpPage.vue:43–52`, chunk 13) — a different thing from the frontend `UpdateBanner`, and users will conflate them.
- In-app copy is consistent and honest since 2026-08-23 (banner + toasts say "look around, not make changes") **except** `public/offline.html:41–44`, which still says changes "are held locally and replayed on reconnect" (17-R2).
- `PwaInstallPrompt` + About "Install as an app" section carry good copy already; `BackendSetupPage` copy is chunk 15's.

#### B2. Help entries

##### Use Dora when the connection drops
- **Group:** Getting around *(new group, or "Settings & admin" if the owner prefers fewer groups)*
- **What it does:** When your phone is offline or the Dora server can't be reached, a red strip appears at the top and you can keep **looking** at anything you've opened before. Changes aren't possible until you're back — Dora never saves a change "for later", so what you see is always what the server has.
- **When it fires / how to trigger it:** Automatically, within a few seconds of losing the server; it checks again more and more slowly, and immediately when you come back to the app. **Retry** checks right now.
- **What controls it:** Always on — no setting. Works best when Dora is installed as an app over HTTPS (that's what stores pages for offline).
- **What it costs / might get wrong:** A page you've never opened while online has nothing stored, so it shows empty or an error. Over plain `http://` nothing is stored for offline at all. If the server is slow (over 5 s) you may briefly see an older copy of a page.
- **Related:** Install Dora on your phone or computer · A new version is ready.
- **Chip:** none (the banner is the surface).
- **Source:** R-052 / ADR-052; `useNetworkStatus.ts`, `quasar.config.ts` `dora-api` NetworkFirst.

##### Install Dora on your phone or computer
- **Group:** Getting around
- **What it does:** Puts a Dora icon on your home screen or launcher and opens it full-screen like any app. Long-press the icon for shortcuts (primary list, Shop now, Add item); on Android you can also **share** a recipe web page straight into Dora's cookbook.
- **When it fires / how to trigger it:** Settings → About → **Install as an app**. On iPhone/iPad: Safari's Share → **Add to Home Screen**.
- **What controls it:** `/settings/about`. Needs Dora served over **HTTPS** (or `localhost`) — on plain `http://` the page says so instead of blaming the browser.
- **What it costs / might get wrong:** Firefox desktop and some browsers never offer install. Installing doesn't change your data or sign you in anywhere new; it is the same website in its own window.
- **Related:** Use Dora when the connection drops · The Android app and your Dora address.
- **Chip:** `AboutSettings.vue:53–56` (section title) → `<HelpHint topic="Install Dora on your phone or computer">`.
- **Source:** `usePwaLifecycle.ts`, `PwaInstallPrompt.vue`, manifest `shortcuts`/`share_target`.

##### A new version is ready (reload)
- **Group:** Getting around
- **What it does:** After Dora is updated on the server, your installed app or browser tab fetches the new version in the background and shows a blue strip: *A new version of Dora is ready. Reload to pick it up.* Reload when convenient; **Dismiss** hides it until next time.
- **When it fires / how to trigger it:** On the first navigation after a new build is downloaded. This is about the **app on your device**; the yellow "newer version available" notice on Help/About is about the **server** itself and is for whoever runs it.
- **What controls it:** Always on — no setting.
- **What it costs / might get wrong:** Reloading mid-edit loses unsaved typing in a dialog, so finish first. Only this device is affected; everyone's browser updates on its own.
- **Related:** Use Dora when the connection drops.
- **Chip:** none.
- **Source:** `usePwaLifecycle.ts:131–147`, `UpdateBanner.vue`; GenerateSW `skipWaiting`/`clientsClaim`.

##### The screen stays on while you cook or shop
- **Group:** Cooking *(Cook mode group, chunk 4)* — cross-listed under Shopping
- **What it does:** In Cook mode and in Shop mode the phone doesn't lock, so a timer or the next step stays readable with wet hands, and the list stays up between aisles.
- **When it fires / how to trigger it:** Automatically on entering Cook mode or starting a shop; released when you leave.
- **What controls it:** Always on — no setting. Needs a browser with the Screen Wake Lock feature (Chrome, Edge, Safari 16.4+, Firefox 126+) and HTTPS; elsewhere the phone locks as usual.
- **What it costs / might get wrong:** Battery, modestly. If you switch apps the lock drops and comes back when you return.
- **Related:** Cook mode · Shop mode.
- **Chip:** none.
- **Source:** `useWakeLock.ts`; callers `RecipeCookMode.vue:837`, `ShoppingListDetail.vue:1243`.

##### The Android app and your Dora address
- **Group:** Getting around
- **What it does:** The Android app is the same Dora in a native wrapper. On first launch it asks for your Dora's address (for example `http://192.168.1.20:5170`) because, unlike the website, it can't guess where your server is.
- **When it fires / how to trigger it:** First launch; afterwards Settings → About → **Dora API endpoint** → Change (the app reloads).
- **What controls it:** Stored on the device only. Use the full address including `http://` or `https://`.
- **What it costs / might get wrong:** Push notifications aren't available inside the Android app (use the installed web app for those). Camera and screen-on work as on the web.
- **Related:** Install Dora on your phone or computer · Choose your instance (chunk 15's entry).
- **Chip:** `AboutSettings.vue` "Dora API endpoint" row → `<HelpHint topic="The Android app and your Dora address">`.
- **Source:** `backendUrl.ts`, `router/index.ts:88–96`, `boot/capacitor.ts`.

#### B3. DoraBot corpus delta
Add to `APP_OVERVIEW` (nothing exists today):
> - Offline: when the server can't be reached a red strip appears; pages already opened still show, but nothing can be changed until the connection is back. Dora never queues changes.
> - Install: Settings → About → Install as an app puts Dora on the home screen (needs HTTPS). A blue "new version ready" strip means reload this device; the yellow version notice on Help is about the server.
> - Android app: the same Dora in a native shell; it asks for the server address on first launch (Settings → About to change it). Push notifications work in the installed web app, not inside the Android app.

---

## Chunk 18 — Backup & restore + Import
*Source: [`CHUNK_18_backup_restore_import.md`](../05_investigations/finalisation/CHUNK_18_backup_restore_import.md) · analysed 2026-10-23*

### B. Help content — Backup & restore + Import

#### B1. Current help audit
- **Nothing** in `HelpPage.vue` or `app_knowledge.py` mentions backup, restore, import, templates or the library (grep). The `(?)` chips are absent on both pages.
- In-page copy is already clear (header descriptions, "Passwords are never included", the Sensitive chip, option help strings). Entries below lift it and add the parts the pages can't say (what is **not** in a backup, what restore never does, the retention/storage semantics).
- Feedback `# DATA` #6 asked for the breadcrumb fluff to go — gone (settings shell).

#### B2. Help entries

##### Back up your install (admin)
- **Group:** Settings & admin
- **What it does:** Saves everything Dora knows — stock, recipes (with steps, tools and tags), lists, meal plans, saved products, barcodes — to one JSON file kept on the server in the **Backup library**. Download any of them to keep a copy elsewhere.
- **When it fires / how to trigger it:** Settings → Admin → Data → Backup & restore → **New backup**. Backups are manual; nothing runs on a schedule.
- **What controls it:** `/settings/admin/data/backup`. *Library settings* at the bottom: how many to keep (oldest drop off on the next backup) and where on the server they're stored.
- **What it costs / might get wrong:** **Passwords are never included**, nor email/push secrets — after restoring user accounts everyone needs a password reset. *System settings*, *User accounts* and *Historic offers* are off by default and flagged **Sensitive** when included. Each person's assistant (AI) provider settings are not backed up yet. A backup is a point-in-time copy of the server, not a sync.
- **Related:** Restore a backup · Import stock items from a spreadsheet.
- **Chip:** `AdminDataBackupRestore.vue:3–7` (page header) → `<HelpHint topic="Back up your install (admin)">`.
- **Source:** `backup_library.py`, `restore_shared.SECTIONS`, FU-387, FU-625.

##### Restore a backup (admin)
- **Group:** Settings & admin
- **What it does:** Brings rows from a backup **into** the current install. Rows that already exist (same id, or same name at the same place) are **skipped, never overwritten**. From a library row it restores everything in one click; from a file you first see a preview and can pick exactly which items to bring in.
- **When it fires / how to trigger it:** Library row → Restore, or *Restore from a file* → drop the JSON → tick items → **Restore selection**, or **Restore all (skip duplicates)**.
- **What controls it:** `/settings/admin/data/backup`. Admins only.
- **What it costs / might get wrong:** Restore adds, it doesn't delete — it is not a "reset to that day". Picking a recipe or list pulls in what it needs (its ingredients, steps, the products a line points at); anything whose parent is missing is skipped and listed under *warnings*. Restored user accounts have no passwords. **Reload** afterwards so every page shows the new data. Backups from a newer Dora are refused.
- **Related:** Back up your install.
- **Chip:** `AdminDataBackupRestore.vue:169–173` (Restore section title) → `<HelpHint topic="Restore a backup (admin)">`.
- **Source:** `restore_backup.py` modes + FK maps; `inspect_backup.py`.

##### Import stock items from a spreadsheet (admin)
- **Group:** Settings & admin
- **What it does:** Creates stock items in bulk from an `.xlsx` or `.csv`. Only a **name** column is required; stock level, location, group, expiry date and "is essential" are optional. Dora guesses which column is which from the headings and lets you fix the mapping before anything is written.
- **When it fires / how to trigger it:** Settings → Admin → Data → Import. **Download template** gives you a CSV with the right headings and one example row to overwrite.
- **What controls it:** `/settings/admin/data/import`. Options: skip names you already have · create missing locations · create missing groups · halt on first error (rolls everything back).
- **What it costs / might get wrong:** Levels are matched by name against *your* levels and never created ("low" finds "Low Stock"). New locations are created as top-level zones. Dates: `2027-01-31` always works; `31/01/2027` is read day-first. A row with an error doesn't stop the others unless *Halt on first error* is on; download the error rows, fix them, and import just those.
- **Related:** Back up your install · Stock levels and locations (chunk 5).
- **Chip:** `AdminDataImport.vue:3–7` (page header) → `<HelpHint topic="Import stock items from a spreadsheet (admin)">`.
- **Source:** `import_spreadsheet.py` `TARGET_FIELDS`, `COLUMN_SYNONYMS`, `_coerce_to_date`, templates (FU-343/349/350).

#### B3. DoraBot corpus delta
Add to `APP_OVERVIEW` (nothing exists):
> - Backup & restore (admin): Settings → Admin → Data. Backups are manual JSON snapshots kept in a library on the server (oldest drop off past the retention count); passwords and secrets are never included. Restore adds missing rows and never overwrites or deletes; from a file the admin can pick exactly which items to bring in.
> - Import (admin): stock items from a spreadsheet; download the CSV template, fill it, upload, check the column mapping, import. Levels must already exist; locations and groups can be created on the fly.

---

## Chunk 19 — Ops / self-host
*Source: [`CHUNK_19_ops_self_host.md`](../05_investigations/finalisation/CHUNK_19_ops_self_host.md) · analysed 2026-10-23*

### B. Help content — Ops / self-host

#### B1. Current help audit
- Operator documentation lives in `README.md`, `.env.example`, `packaging/BUILD_NATIVE.md`, `docs/INGESTION_GUIDE.md` — not in the in-app Help, which is right (the Help page is for household members). The *user-facing* ops touchpoints that have no Help entry: the About **version check**, the **demo banner**, "**where is my data**" (desktop users ask), and "**how do I report a problem / where are the logs**". `HelpPage.vue` group *Dora itself* already has ops-adjacent entries (AI-mode encryption key, network topology) — these go there.
- README drift (19-R4) is the real documentation debt: four stale statements an operator will hit on day one.

#### B2. Help entries

##### Where Dora keeps your data
- **Group:** Dora itself
- **What it does:** Everything lives on the Dora server, not in your browser. On a self-hosted Docker install that is the `dora_data` volume (`/app/data`: the database, uploads, backups, voices) with logs in `dora_logs`. The desktop app keeps the same layout under your user folder (`%LOCALAPPDATA%\Dora\` on Windows, `~/.local/share/Dora/` on Linux, `~/Library/Application Support/Dora/` on macOS).
- **When it fires / how to trigger it:** Always.
- **What controls it:** The operator's `DORA_DATA_DIR` / `DORA_LOG_DIR` (server) — never an in-app setting.
- **What it costs / might get wrong:** Deleting the volume or that folder deletes the install; take a backup first (Settings → Admin → Data). The browser only caches pages for offline reading (chunk 17).
- **Related:** Back up your install (chunk 18) · Use Dora when the connection drops (chunk 17).
- **Chip:** none.
- **Source:** `configuration_manager.get_data_dir/get_log_dir`, `desktop_app._bootstrap_paths`, `compose.yml` volumes.

##### Is there a newer Dora?
- **Group:** Dora itself
- **What it does:** Help → About shows the version you're running and, when the server can reach GitHub, whether a newer release exists, with a link to it. Updating is the operator's job (pull the new image / installer); Dora never updates itself.
- **When it fires / how to trigger it:** On opening Help/About; the answer is cached for 30 minutes.
- **What controls it:** Always on — no setting. Offline or rate-limited → "Couldn't check for updates (…)" and nothing else changes.
- **What it costs / might get wrong:** This is about the **server**. The blue "A new version of Dora is ready — Reload" strip is about the app on *your device* (chunk 17) and appears after the operator has already updated.
- **Related:** A new version is ready (reload) (chunk 17).
- **Chip:** `HelpPage.vue:43–52` (the version banner) → `<HelpHint topic="Is there a newer Dora?">`.
- **Source:** `get_version.py`; `version_info.CURRENT_VERSION`.

##### Why does a banner say "Demo mode"?
- **Group:** Dora itself
- **What it does:** The install was started as a public demo: sample data, a `demo`/`demo` admin, and everything resets to the sample on a timer (hourly by default). Nothing you change is kept.
- **When it fires / how to trigger it:** Operator-only (`DORA_DEMO_MODE`); it cannot be switched off from Settings, on purpose.
- **What controls it:** Env only.
- **What it costs / might get wrong:** Don't enter real data. If you're seeing this on your own install, your operator started it in demo mode.
- **Related:** Where Dora keeps your data.
- **Chip:** none (the pill is the surface).
- **Source:** FU-392; `DemoBanner.vue`, `startup.init_db`, `seed_showcase.reset_showcase`.

##### Reporting a problem (and what the operator can see)
- **Group:** Dora itself
- **What it does:** The **Report an issue** button (Help, error pages, Dora's chat) opens the project's issue tracker when the operator has set one up; otherwise there is no button. Every request carries an id (`X-Request-Id`) that appears in the server log, so quoting the time and what you did lets the operator find it. Browser-side errors are posted to the server log too.
- **When it fires / how to trigger it:** Help → Report an issue; or ask your operator to look at `dapi.log` (rotates daily, two weeks kept).
- **What controls it:** `DORA_SUPPORT_URL` / `DORA_SUPPORT_EMAIL` (operator). Log detail: `DORA_LOG_LEVEL` — at the container default (`ERROR`) a rejected request (400) leaves no line (FU-640).
- **Related:** Is there a newer Dora?
- **Chip:** none.
- **Source:** `support_channel.py`, `log_context.py`, FU-640, chunk 20 (`/api/client-logs`).

#### B3. DoraBot corpus delta
Add to `APP_OVERVIEW`:
> - Where data lives: on the Dora server (the `dora_data` volume on Docker; the user's app-data folder on the desktop app), never in the browser. Settings → Admin → Data makes backups.
> - Updates: Help → About shows the running version and whether a newer release exists; installing it is the operator's job. A blue "new version ready" strip is just the app on this device catching up.
> - Demo mode: a floating "Demo mode" pill means the install is a resetting public demo; changes are not kept.

---

## Chunk 20 — Cross-cutting concerns
*Source: [`CHUNK_20_cross_cutting.md`](../05_investigations/finalisation/CHUNK_20_cross_cutting.md) · analysed 2026-10-23*

### B. Help content — cross-cutting

#### B1. Current help audit
- `HelpPage.vue` has a search filter and the `?q=` deep link (navigable — feedback `# HELP` #4 ✓), 28 entries across 6 groups; after chunks 1–19 there are **~105 new entries + 8 rewords** proposed, which outgrows a flat list (20-D4). There is **no FAQ/Q&A section** (`# HELP` #3) — the *Dora itself* group already uses question-shaped titles, so the shape exists. No screenshots or diagrams anywhere (`# HELP` #5 — owner offered to provide).
- **Keyboard shortcuts** have a cheatsheet (`?`) but no Help entry — the only discoverability is knowing `?`.
- Theme / text size / fonts: one entry ("Theme, font, and text size", chunk 13 rewords it); nothing about what "System" means or why the login page is always light.
- Locale/currency: no entry (admin Region page has inline help; members have nothing explaining why dates look the way they do).
- Error toasts and the `ref:` id: nothing tells a user what the eight-character reference is for.

#### B2. Help entries

##### Keyboard shortcuts
- **Group:** Getting around
- **What it does:** Press `?` anywhere to see every shortcut that works on the screen you're on. Always: `/` focuses search, `g` then `s`/`l`/`r`/`d`/`h` jumps to Stock, Lists, Cookbook, Dashboard, Help. Stock Overview and a shopping list add their own (`n` new, arrows to move, `Space` to tick, `u` untick last, `Enter` open).
- **When it fires / how to trigger it:** Any time you're not typing in a field. Two-key sequences give you a second to press the second key.
- **What controls it:** Always on — no setting; shortcuts never use Ctrl/Cmd so they can't collide with the browser's.
- **What it costs / might get wrong:** Nothing on a phone (no keyboard). The command palette is gone on purpose; `?` is the one place to look.
- **Related:** —
- **Chip:** none (`?` is the surface).
- **Source:** `useShortcut.ts`, `MainLayout.vue:204–223`, `StockOverview.vue:1010–1018`, `ShoppingListDetail.vue:2166–2170`.

##### How Dora shows dates, money and units
- **Group:** Getting around
- **What it does:** Every date, price and unit in the app follows the **household's** region (Settings → Admin → System → Region), not your browser's: `17/07/2026` and `$12.50` on an Australian install, `7/17/2026` on a US one. Metric or US units drive which units the pickers offer. A calendar date is always the day it names, whatever your timezone.
- **When it fires / how to trigger it:** Automatically, everywhere, after the admin saves the region.
- **What controls it:** Admin only; members can't override it per account (a household shares one format).
- **What it costs / might get wrong:** Prices always show two decimals, even for currencies that don't use them. If Dora can't reach the server at startup it falls back to Australian formatting until it can.
- **Related:** Region settings (chunk 13) · Where Dora keeps your data (chunk 19).
- **Chip:** `AdminSystemRegionSettings.vue:4` (page header) → `<HelpHint topic="How Dora shows dates, money and units">`.
- **Source:** `useMoney.ts`, `useDateFormat.ts`, `/health.locale_policy`, `units_for_system`.

##### Themes, dark mode and text size
- **Group:** Settings & admin *(extends the existing "Theme, font, and text size" entry — chunk 13 rewords it; this is the fuller version)*
- **What it does:** Pick a colour family (Pesto, Lemon Tart, Blueberry, Cherry Cola, Sourdough, Salt & Pepper, …) and whether it follows your device's light/dark setting or stays fixed; pick a font and one of four text sizes. Every page, chart and toast follows.
- **When it fires / how to trigger it:** Settings → Preferences; per account, remembered across devices.
- **What controls it:** `/settings/preferences`.
- **What it costs / might get wrong:** The sign-in page is always the light brand look (nobody is signed in yet). "System" follows the OS only after you've chosen a theme once.
- **Related:** Keyboard shortcuts.
- **Chip:** none.
- **Source:** `themeService.ts`, `boot/theme.ts`, `themes.scss`.

##### "Something went wrong" and the reference code
- **Group:** Dora itself
- **What it does:** When a save fails, Dora highlights the field and says why. When a screen breaks, it shows a recovery page with **Reload**, **Go to dashboard** and (if the operator set one up) **Report this**. A short code like `ref: 3f9a2c1b` on an error is the id of that exact request in the server log — quote it when you report a problem.
- **When it fires / how to trigger it:** Automatically.
- **What controls it:** Always on. Browser-side crashes are also sent to the server log (a few per minute at most).
- **What it costs / might get wrong:** Reloading loses unsaved typing. If the server itself is down you'll see the red connection strip instead (chunk 17).
- **Related:** Reporting a problem (chunk 19) · Use Dora when the connection drops (chunk 17).
- **Chip:** none.
- **Source:** `PageErrorState.vue`, `apiErrorHandler.ts`, `log_context.py`, `submit_client_log.py`.

#### B3. DoraBot corpus delta
Add to `APP_OVERVIEW`:
> - Keyboard: `?` shows the shortcuts for the current screen; `/` focuses search; `g` then `s`/`l`/`r`/`d`/`h` jumps between the main areas.
> - Formatting: dates, prices and units follow the household region the admin set, not the browser.
> - Errors: a `ref:` code on an error identifies that request in the server log — include it when reporting.

---
