import { STEPS_MODES, type RecipeStepsMode } from 'src/generated/recipe_vocabulary';
export type RecipeIngredient = {
    recipe_ingredient_id: string;
    /** IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — nullable so unlinked
     *  (paste-imported, no fuzzy match) rows round-trip. When null, the
     *  ingredient shows an "Unlinked · Link" pill; ``stock_item_name``,
     *  ``stock_level_id``, ``stock_location_*`` and the stock-status
     *  booleans are all null / false. ``raw_text`` carries the label. */
    stock_item_id: string | null;
    stock_item_name: string | null;
    stock_level_id: string | null;
    stock_location_id: string | null;
    stock_location_name: string | null;
    quantity: number | null;
    unit: string | null;
    notes: string | null;
    /** Server-derived stock status for this ingredient (§3.1 contract).
     *  `is_missing` = out-of-stock or untracked; the client reads these
     *  instead of matching a stock-level name. False on unlinked rows —
     *  we can't say what's missing about an ingredient we haven't linked. */
    is_missing: boolean;
    is_low_stock: boolean;
    /** C-4 Chunk 10 — nullable section grouping. NULL = implicit "main"
     *  group; otherwise references one of `Recipe.sections[].section_id`. */
    section_id: string | null;
    /** Cookbook revision §1.9 — optional ingredients are ignored by the
     *  cookability rule (no second cookable value). UI renders them with
     *  an "(optional)" hint, under an Optional separator in the
     *  shopping-list picker (unchecked by default), and dimmed in cook
     *  mode. Default false (column is NOT NULL server-side). */
    is_optional: boolean;
    /** IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — the ingredient text as the
     *  user pasted or imported. Persists even after linking. UI prefers
     *  it when non-empty for the ingredient label ("1 pound ground
     *  turkey" is more informative than "ground turkey"). */
    raw_text: string | null;
    /** The linked stock item's expiry date, echoed so a surface can say
     *  *when* without fetching the stock item. Null when unlinked or unset. */
    expiry_date: string | null;
    /** Server-derived "this is one of the at-risk ones", on the same
     *  contract as `is_missing`: the cookbook's at-risk horizon is a domain
     *  constant the server owns, and it is deliberately longer than the
     *  client's expiry *display* band in `helpers/expiryIndicator`. Never
     *  re-derive this from `expiry_date` — that's how the chips would stop
     *  agreeing with the "uses expiring ingredients" filter. */
    is_expiring: boolean;
    /** Already past its date. True implies `is_expiring`; it only splits
     *  amber "use it soon" from red "it's gone off". */
    is_expired: boolean;
    /** Which one of the stock item this recipe means. `label` is the name the
     *  recipe shows for it (null: show `stock_item_name`); picking a preferred
     *  buy or product in the editor fills it in. The picks are ids only, carried
     *  onto a shopping line when the recipe is added to one. */
    label: string | null;
    preferred_buy_id: string | null;
    selected_product_id: string | null;
};

/** C-4 Chunk 10 — a named group within a recipe (DEC-3 option A).
 *  Optional — a recipe with no sections renders flat, with all
 *  ingredients/steps under no header. */
export type RecipeSection = {
    section_id: string;
    sequence: number;
    name: string;
};

export type Recipe = {
    recipe_id: string;
    name: string;
    /** Total meals of this recipe currently in the pool (cooked-ahead
     *  portions). User-managed via Cook mode and the ± controls; also
     *  auto-decrements when a meal-plan entry's day passes. */
    available_meals: number;
    /** `available_meals` minus the sum of un-consumed future meal-plan
     *  servings for this recipe. Floored at 0. Derived server-side. */
    unallocated_meals: number;
    /** Raw sum of future un-consumed meal-plan servings (NOT floored).
     *  `committed_meals > available_meals` ⇒ a shortfall (shown red). */
    committed_meals: number;
    /** C-2.I — server-derived planner-tray facts. `not_made_recently`: never
     *  made or last made before the household 21-day window. `plan_count`: how
     *  often the recipe appears across all meal plans. */
    not_made_recently: boolean;
    plan_count: number;
    /** FU-081 — true iff at least one future un-consumed MealPlanEntry
     *  exists for this recipe. Server-owned; the cookbook "Planned" /
     *  "Not planned" tri-state filter reads this directly. */
    is_planned: boolean;
    // cuisine + category are FK vocabularies. The id drives the
    // edit-form selects + filters; the name is carried for display.
    cuisine_id: string | null;
    cuisine_name: string | null;
    category_id: string | null;
    category_name: string | null;
    cook_time_minutes: number | null;
    difficulty: string | null;
    instructions: string | null;
    /** RD-29 — free-text personal notes about the recipe (the cook's own
     *  commentary). Distinct from `instructions` (the method); surfaced in
     *  cook mode under the steps. Null when unset. */
    notes: string | null;
    is_favourite: boolean;
    last_made_on: string | null;
    /** FU-082 — when the recipe was added to this household. Drives the
     *  cookbook "Recently added" sort axis. Always present on rows from
     *  the API (backfilled by migration f9d3a7c2b5e8 for legacy rows). */
    created_at: string;
    /** Recipe-view feedback 2026-08-24 — when the recipe was last edited
     *  (any successful PATCH). Null until its first edit. The version panel
     *  prints it beside `created_at`; nothing else reads it. */
    updated_at: string | null;
    prep_time_minutes: number | null;
    recipe_collection_id: string | null;
    /** Resolved server-side (same shape as `cuisine_name`) so the card /
     *  row meta line can print the collection without joining against a
     *  separately-fetched collection list. Null when uncollected. */
    recipe_collection_name: string | null;
    servings: number | null;
    /** C-4 Chunk 7 — origin URL when the recipe was imported.
     *  Null for hand-entered recipes. */
    source: string | null;
    time_of_day: string | null;
    /** C-4 Chunk 8 — version siblings share this id. Null = singleton.
     *  Detail endpoint also returns the populated `version_siblings[]`. */
    version_group_id: string | null;
    /** C-4 Chunk 9 — simple nutrition (kcal). Null when unset. Client
     *  gates render on `useNutritionMode().isSimple`. */
    kcal: number | null;
    ingredients: RecipeIngredient[];
    /** C-4 Chunk 2 — dietary tag ids (FK to DietaryTag). Empty when untagged. */
    dietary_tag_ids: string[];
    /** C-4 Chunk 5 — tool ids (FK to Tool). */
    tool_ids: string[];
    /** C-4 Chunk 5 — whether an image exists (bytes served via
     *  GET /recipes/<id>/image, never inlined here). */
    has_image: boolean;
    /** Server-owned cookability (§3.2). Tri-state per
     *  IMPL_PLAN_RECIPE_IMPORTER §Chunk 4: `true` (nothing missing),
     *  `false` (something linked-missing), `null` (at least one required
     *  ingredient is unlinked — the app admits "we don't know"). UI
     *  renders the badge dimmed with a "Link ingredients to check
     *  cookability — this is a stock-item feature" tooltip when null.
     *  `missing_count` counts only LINKED-missing rows and is safe to
     *  read on any state (zero when cookable is null). */
    cookable: boolean | null;
    missing_count: number;
    /** IMPL_PLAN_RECIPE_IMPORTER §Chunk 4 — count of required
     *  ingredients whose `stock_item_id` is null (unlinked).
     *  When > 0, the recipe reads `cookable === null`. Drives the
     *  detail-page "N ingredients need linking" prompt and the
     *  shopping-list "Add missing" flow's linking-first message. */
    unlinked_ingredient_count: number;
    /** FU-653 — the Zero-Input belief's remark about this recipe, or null.
     *  `'at_risk'`: reads cookable, but Dora believes a required ingredient
     *  has run out. `'maybe_cookable'`: reads not-cookable, but she believes
     *  every missing ingredient is back. **Additive only** — `cookable`,
     *  `missing_count` and the cookbook's filters ignore it entirely. Null
     *  unless the user opted the recipes surface in (Settings → Assistant). */
    inference_hint: 'at_risk' | 'maybe_cookable' | null;
    /** The items behind `inference_hint`, already de-duplicated. */
    inference_stock_item_names: string[];
    /** C-4 Chunk 6 — structured steps. The list endpoint sets
     *  `has_structured_steps` (cheap existence check); the detail endpoint
     *  hydrates `steps[]`. Empty `steps[]` + `has_structured_steps === false`
     *  ⇒ unstructured recipe; cook-mode falls back to splitting `instructions`
     *  on newline. */
    has_structured_steps: boolean;
    steps: RecipeStep[];
    /** C-4 Chunk 8 — populated only on the detail endpoint. Empty on
     *  the list endpoint (the client uses `version_group_id` to know
     *  whether siblings might exist). */
    version_siblings: RecipeVersionSibling[];
    /** C-4 Chunk 9 / DEC-5 — server-derived. Null when no estimate could
     *  be computed (no linked products on any ingredient). Client gates
     *  render on `useMoneyEnabled()`.
     *
     *  Owner 2026-09-05: no longer detail-only — the list endpoint
     *  hydrates it too (in two queries for the whole page), so the
     *  cookbook can show and sort on cost. Still null on every recipe
     *  when money is off: the server skips the work entirely rather
     *  than shipping figures the client is trusted to hide. */
    estimated_cost: number | null;
    estimated_cost_priced_count: number;
    estimated_cost_total_count: number;
    /** Owner 2026-09-05 — the comparable figure across a list, since
     *  recipes differ in yield. Server-owned (do NOT divide
     *  `estimated_cost` by `servings` on the client). Null when the
     *  recipe is unpriced *or* has no servings typed in — a blank
     *  servings field is not "serves 1". */
    estimated_cost_per_serving: number | null;
    /** Feedback 2026-08-19 — the per-ingredient working behind the
     *  estimate, shown when the cost card is expanded. Detail only. */
    estimated_cost_lines: RecipeCostLine[];
    /** C-4 Chunk 10 — named sections (DEC-3 option A). The list endpoint
     *  populates only `section_count`; the detail endpoint also hydrates
     *  `sections[]`. Empty sections + `section_count === 0` ⇒ recipe is flat.
     *  Kept as a wire-shape mirror only — the cookbook card's "N parts" chip
     *  that was its one reader was cut as bloat (owner 2026-09-09). */
    section_count: number;
    sections: RecipeSection[];
    /** C-waste W4 — number of this recipe's (non-optional) ingredients
     *  that are currently in stock and expiring within the cookbook
     *  filter's horizon. Populated only when the request set
     *  `?expiring_within_days=N` — zero / absent otherwise. */
    expiring_ingredient_count?: number;
    /** Soonest expiry date (ISO) among those at-risk ingredients, or null.
     *  Server-derived (see `count_expiring_ingredients_per_recipe`); the
     *  cookbook ranks and colours by this so "2 expiring today" beats
     *  "4 expiring next week". Never re-derive the tone from the raw
     *  ingredient list here — use `expiryToneFor` on this date. */
    expiring_soonest_date?: string | null;
    /** PROPOSAL_RECIPE_IMAGE_STEPS — which step payload to render:
     *  'structured' uses `steps[]`, 'freeform' splits `instructions` on
     *  newline (today's fallback), 'image' renders `step_images[]` as a
     *  scrollable gallery. Server-owned; the editor flips it as the user
     *  changes mode. Mode switching is non-destructive — all three
     *  payloads can coexist on one recipe. */
    steps_mode: RecipeStepsMode;
    /** PROPOSAL_RECIPE_IMAGE_STEPS — ordered metadata for image-mode
     *  rendering. Bytes are NOT inlined; each image is fetched via
     *  `GET /recipes/<recipe_id>/step-images/<image_id>`. Populated only
     *  on the detail endpoint. */
    step_images: RecipeStepImage[];
    /** FU-635 — complex-mode nutrition summed from the ingredients' linked
     *  foods. Server-owned (the gram-conversion ladder and coverage rule are
     *  domain math, R-003). Populated only on the detail endpoint and only
     *  while the install is in complex mode; null in off/simple, where the
     *  typed `kcal` above is the whole feature. */
    nutrition: RecipeNutrition | null;
    /** FU-637 — the *effective* per-serving kcal for the install's current
     *  nutrition mode: the typed `kcal` above in simple, the rollup in
     *  complex, null when off (or when a complex recipe has no servings, where
     *  a per-serving figure would have to be invented). Server-owned so the
     *  card, the filter and the meal planner can't disagree (R-003) — read
     *  this, never re-derive it from `kcal` + `nutrition`. */
    kcal_per_serving: number | null;
    /** Whether `kcal_per_serving` may be used to *judge* the recipe (filter it
     *  out, rank it) rather than merely display it. */
    kcal_is_reliable: boolean;
};

/** The Health Star Rating for a recipe (owner ask 2026-08-27).
 *
 *  Server-owned, and deliberately more than a star count: every intermediate
 *  the FSANZ method names travels with it so the panel can show its working.
 *  Present only when the install has the rating switched on *and* is in
 *  complex nutrition mode — read it, never re-derive it (R-003; the tables
 *  live in `dora_api/domain/health_star_rating.py` and have no business being
 *  transcribed a second time in TypeScript). */
export type RecipeHealthStarRating = {
    /** 0.5 to 5.0, in half-star steps. */
    stars: number;
    /** Baseline points minus every modifying point. Lower is better. */
    score: number;
    baseline_points: number;
    energy_points: number;
    saturated_fat_points: number;
    total_sugars_points: number;
    sodium_points: number;
    v_points: number;
    protein_points: number;
    fibre_points: number;
    /** False when the ≥13-baseline / <5-fvnl rule suppressed the protein
     *  credit. Surfaced because a silently-zeroed protein score reads as a
     *  bug unless the UI can say why. */
    protein_counted: boolean;
    /** % of the dish's counted weight that is fruit, vegetable, nut or
     *  legume. Null when nothing could be weighed. */
    fvnl_percent: number | null;
    /** Raw summed ingredient weight in grams — the per-100g denominator, and
     *  the reason the rating is labelled an estimate. */
    total_grams: number | null;
};

/** The Nutri-Score for a recipe (owner ask 2026-08-27) — the European sibling
 *  of `RecipeHealthStarRating`, and subject to the same rule: server-owned,
 *  read it, never re-derive it (R-003; the published tables live in
 *  `dora_api/domain/nutri_score.py`).
 *
 *  The shapes are similar but **not interchangeable**, and unifying them would
 *  be a trap: the components are different quantities with different ceilings
 *  (`v_points` maxes at 8 over fruit/veg/nuts/legumes, `fvl_points` at 5 over
 *  fruit/veg/legumes only), and the two schemes disagree about whether nuts
 *  count at all. */
export type RecipeNutriScore = {
    /** 'A' (best) to 'E'. */
    grade: string;
    /** Negative points minus the positive ones. Lower is better. */
    score: number;
    negative_points: number;
    energy_points: number;
    saturated_fat_points: number;
    total_sugars_points: number;
    salt_points: number;
    positive_points: number;
    protein_points: number;
    fibre_points: number;
    fvl_points: number;
    /** False when the N ≥ 11 rule dropped the protein credit. Surfaced because
     *  a silently-zeroed protein score reads as a bug unless the UI says why. */
    protein_counted: boolean;
    /** % of the dish's counted weight that is fruit, vegetable or legume.
     *  **Nuts excluded** — not the same figure as `fvnl_percent`. */
    fvl_percent: number | null;
    /** Raw summed ingredient weight in grams — the per-100g denominator, and
     *  the reason the grade is labelled an estimate. */
    total_grams: number | null;
};

/** FU-635 — the recipe rollup. Nutrient fields are null when no counted
 *  ingredient carried that nutrient; a 0 would claim the recipe has none.
 *  `counted_count` / `total_count` / `uncounted` always travel with the
 *  figure so a partial total can't be rendered as a complete one. */
export type RecipeNutrition = {
    /** 'serving' when the recipe has servings typed in; 'recipe' means the
     *  figure is the whole-recipe total (we don't guess a serving count). */
    basis: 'serving' | 'recipe';
    servings: number | null;
    kcal: number | null;
    protein_g: number | null;
    carbs_g: number | null;
    fat_g: number | null;
    counted_count: number;
    total_count: number;
    /** FU-637 — coverage is high enough to rank or filter the recipe on.
     *  Display never gates on this (a thin figure still shows, with its
     *  coverage); judging a recipe on a thin one would mislead. Threshold is
     *  the server's (R-003) — read the flag, don't re-derive it. */
    is_reliable: boolean;
    /** Reason id → how many ingredients it accounts for. Only non-zero
     *  reasons are present. Copy for each id lives in the component. */
    uncounted: Partial<Record<RecipeNutritionGap, number>>;
    /** The same gaps, named row by row. Detail path only — the cookbook list
     *  ships the counts and nothing else, so this is empty there. */
    uncounted_ingredients: RecipeNutritionGapIngredient[];
    /** The four nutrients the panel gained alongside the Health Star Rating
     *  (2026-08-27). Same per-serving basis as the macros above. */
    saturated_fat_g: number | null;
    sugars_g: number | null;
    fibre_g: number | null;
    sodium_mg: number | null;
    /** Per nutrient, the fraction (0..1) of the recipe's counted *weight*
     *  whose food carried a figure — mass-weighted, because these feed a
     *  per-100g calculation. Keyed by the rollup's own names ('kcal',
     *  'sugars_g', …). It exists because the gap isn't symmetric: a missing
     *  penalty nutrient makes a recipe rate *better*, so the panel must be
     *  able to say which figures were thin. */
    nutrient_coverage: Partial<Record<string, number>>;
    /** Null unless the install picked the `health_star` scheme *and* something
     *  could be weighed. Never non-null at the same time as `nutri_score` —
     *  the install chooses one scheme. */
    health_star_rating: RecipeHealthStarRating | null;
    /** The Nutri-Score twin, on the same terms. */
    nutri_score: RecipeNutriScore | null;
};

/** FU-635 — closed set of reasons an ingredient contributed nothing (R-010).
 *  Mirrors `features/nutrition/recipe_rollup.py`. */
export type RecipeNutritionGap =
    | 'not_linked'
    | 'no_food'
    | 'no_quantity'
    | 'no_conversion'
    | 'no_data';

/** One ingredient behind a gap. `stock_item_id` is null exactly when the
 *  reason is `not_linked` — for every other reason it's the pantry item the
 *  fix is written to, which is what lets the panel offer the food search
 *  inline instead of sending the cook to the pantry page. */
export type RecipeNutritionGapIngredient = {
    name: string | null;
    stock_item_id: string | null;
    reason: RecipeNutritionGap;
};

/** PROPOSAL_RECIPE_IMAGE_STEPS — closed set of recipe step payload modes,
 *  generated from the server (R-010 / R-089). */
export type { RecipeStepsMode };
export const RECIPE_STEPS_MODES: RecipeStepsMode[] = [...STEPS_MODES];

/** PROPOSAL_RECIPE_IMAGE_STEPS — one ordered photo of a recipe's steps. */
export type RecipeStepImage = {
    image_id: string;
    sequence: number;
};

/** Lightweight view of another recipe in the same version group —
 *  enough to render a "Versions" card row + jump to its detail. */
export type RecipeVersionSibling = {
    recipe_id: string;
    name: string;
    last_made_on: string | null;
    available_meals: number;
    /** When that version was created — the one fact that tells two versions
     *  of the same recipe apart at a glance. Null only on legacy rows. */
    created_at: string | null;
};

/** Why an ingredient contributed nothing to the estimate. Mirrors the
 *  `UNPRICED_*` constants in `dora_api/features/recipes/recipe_cost.py`;
 *  the phrasing lives on the client so the server ships facts, not copy. */
export type RecipeCostUnpricedReason =
    | 'no_link' | 'no_price' | 'no_quantity'
    | 'unit_no_pack_count' | 'unit_no_pack_size' | 'unit_unknown_density'
    | 'unit_wrong_food' | 'unit_mismatch';

/** One ingredient's row in the expandable cost breakdown. `line_cost` is
 *  set exactly when `reason` is null. */
export type RecipeCostLine = {
    name: string;
    quantity: number | null;
    unit: string | null;
    /** Price per `priced_unit` — e.g. 0.004 when the price is $4/kg and
     *  `priced_unit` is "g". Null when the ingredient was never priced. */
    unit_price: number | null;
    priced_unit: string | null;
    line_cost: number | null;
    reason: RecipeCostUnpricedReason | null;
};

export type RecipeStep = {
    step_id: string;
    /** Top-level step when null; a sub-step otherwise. Exactly one level
     *  of nesting — sub-steps cannot themselves have sub-steps. */
    parent_step_id: string | null;
    sequence: number;
    text: string;
    hint: string | null;
    /** References RecipeIngredient.recipe_ingredient_id from this recipe. */
    ingredient_ids: string[];
    /** References Tool.id from the user's tools vocabulary. */
    tool_ids: string[];
    /** C-4 Chunk 10 — section grouping for top-level steps. Sub-steps
     *  carry the same id as their parent so the read path stays flat. */
    section_id: string | null;
    /** Owner feedback 2026-09-01 — a countdown the cook *declared* on this
     *  step, in minutes. Null means none was declared; cook mode then sniffs
     *  the step text for a duration, which is all a free-text method can
     *  ever offer. */
    timer_minutes: number | null;
};

export type RecipeTagDefinition = {
    value: string;
    label: string;
    category: string;
};

export type RecipeTagCatalogue = {
    tags: RecipeTagDefinition[];
    /** Plain-English disclaimer to surface alongside any tag-based UI. */
    disclaimer: string;
};

export type RecipeCollection = {
    recipe_collection_id: string;
    name: string;
};
