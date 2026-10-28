# Finalisation Review — senior code review record

**Assembled 2026-10-23** from the twenty chunk files (track **Review** = each chunk's §C findings + §E follow-ups). Finding ids are `NN-Rk` (chunk–finding) and are stable: Stage 2 executes against them, `FINALISATION_COVERAGE.md` flips *Applied* when a chunk's execute-list is done, and the umbrella follow-up **FU-929** holds the unexecuted remainder. Verdict vocabulary: **execute** (Stage 2 does it, test-guarded) · **FU** (needs its own ticket) · **waive** (keep, with the reason) · **explain** (comment in place naming the rule) · **decision** (owner).

Owner context: ≥90 % happy with the app as it is (2026-10-22) — §C executes the maintainability class and verified bugs only; design-level items stop at §C8.

---

## 0. Cross-chunk consolidation — execute once, not per chunk

These are the sweeps several chunks pointed at the same place. Stage 2 runs them as single units so the same helper isn't built twice.

| Sweep | Chunks that asked for it | Shape |
|---|---|---|
| `useConfirm` dialog wrapper (50 `$q.dialog` sites / 26 files; kills the 4 `html: true`) | 13-R26, 16-R22, 18-R5/R9, 20-R11 | `composables/useConfirm.ts` → `Promise<boolean>`; destructive variant |
| Session user-id helper (`SESSION_USER_ID_KEY`, FU-654) | 09-R4, 11, 12, 13, 14-R8, 15-R14, 20-R28 | one `current_user_id()` in `auth_helpers`; ~20 prologues |
| `format_money` lift to `infrastructure/money.py` | 09-R1, 10-R41, 11-R13 | server-side money copy reads the install currency |
| `_ranges.py` shared date-window parser | 10-R15, 12-R24 | — |
| Raw `db.metadata.tables` readers → repository (FU-923) | 10-R12, 13-R32, 16-R24, 18-R20, 19 §C5, 20-R27 | list in 20-R27; dump/restore engine is the documented carve-out |
| `recipe_cookability` reuse | 11-R19 | — |
| `useSlotLoader` / gated-loader race (FU-844) | 12-R23, 20 §A3 | — |
| `DoraSegmented` ⇄ `BaseSegmented` merge (FU-848) | 12-D5, 13-C9, 20-R16 | keep the radiogroup |
| Authed-image helper (`StoreLogo`, `UserAvatar`, products, QR) | 10-R35, 13-R41, 17-R7/R8 | one `AuthedImage` primitive (R-045) |
| Shared `healthProbe` (one inflight `/health`) | 13-R37, 17-R23, 19-R6/R26 | — |
| `api_response.too_many_requests / validation_failed / gone` | 11-R15, 13-R14, 15-R7, 16-R9/R34, 18-R11 | typed results, no `startswith` dispatch |
| `PasswordField` + FU-656 single password rule | 13-R12, 15-R8 | — |
| `TimezoneSelect` / `normaliseHeadcount` lift | 14-R9 | — |
| `.settings-*` scoped CSS → shell | 13-R9, 16-R12, 18-R13, 20-R15 | — |
| Image-cap literal ×9 → one constant | 16-R11, 20-R14 | `infrastructure/images.py` |
| Focus-ring token pair → one (`--ring-focus` at `:root` via color-mix) | 13-R40, 20-R8 | — |
| Bare Material icon strings → `ICONS` (48; 12 in shared primitives) | 13-R39, 15, 16, 17-R21, 18, 20-R13 | fix primitives first |
| `text-color="white"` on semantic chips (24 / 16 files) — FU-671 | 16, 18, 20 | `--text-on-*` tokens (FU-674) |
| `outline: none` A6 sweep (21 / 15 files) — FU-841 class | 20 §C10 | `:focus-visible` ring |
| Toast position default (322 sites, two conventions) | 17-R11, 20-R10 | `quasar.config` default + system-toast allow-list |
| Raw `fetch` → `AxiosHttpClient` (21 sites; FU-716, FU-647) | 18-R7, 20 §C10 | `DataApiService`, `UploadsApiService` |
| Unit lists single-sourced via `dump_units.py` codegen | 20-R3, 20-R4 | — |
| Module-level `_Logger` idiom | 16-R27, 18-R25, 19-R22 | mechanical |
| Naming leftovers (DiscountDora) | 19-R4 | `.env.example`, `nginx.conf`, build scripts |

### Verified bugs — the Stage-2 opening order (small blast radius first)

| Order | Finding | Surface | Why first |
|---|---|---|---|
| 1 | 18-R1 partial restore `KeyError 'meal_recipes'` | backup/restore | 500 on a user action; one-line fix + the first partial-mode test |
| 2 | 18-R2 / 18-R3 UI backup default rejected (`product_barcodes`), section catalogue mirror | backup/restore | default *New backup* fails; UI backups omit recipe steps |
| 3 | 16-R2 idempotency replay after TTL → 500; 16-R3 purge | ingestion | companion's stable-key path |
| 4 | 16-R8 link-status resolves custom products → unsave deletes them | ingestion | data loss path |
| 5 | 19-R1 Docker image built without `-m pwa`; 19-R2 `web_app/.env` baked; 19-R3 repo slug | ops | self-host deployment correctness |
| 6 | 13-R1 invalid `nutrition_mode` → 500 (tuple return); 13-R3 last-admin guard ignores `is_active`; 13-R2 admin email edit skips validation | settings | admin-facing 500 / guard holes |
| 7 | 14-R1 demo seed inserts a second week; 14-R2 demo ingredient names | onboarding | seed quality |
| 8 | 15-R2 DEBUG request logging captures passwords; 15-R1 `DORA_TRUSTED_PROXY_HOPS` | auth | security hygiene |
| 9 | 17-R1 two service workers one scope; 17-R2 `offline.html`; 17-R3 `.gitignore`; 17-R7 image caches | PWA | needs a built-PWA browser check |
| 10 | 08-R1 restock radar 500 on an unlevelled item; 11 (three confirm actions crash on `IS_PRIMARY`; `waste_insights` NameErrors); 12 budget window UTC; 07-R1/R2; 06-R1…; 05-R5/R7; 04-R1/R7/R8; 03-R1…R4; 02-R1/R2/R34/R35; 01-R1…R3 | chunks 1–12 | per the chunk C1 lists below |
| 11 | 20-R1…R10 (dead installer, vue-i18n, unit lists, money/date bypasses, collators, focus token, client-log leak, toast default) | cross-cutting | after the per-surface fixes so sweeps don't collide |

### Owner decisions outstanding (every chunk's §C8 `NN-Dk`)

09 suggestions inbox vs the bell · 10-R3 money gate on price watches, 10-D3, 10-D4 · 11-D1 `app_help(topic)` tool vs in-prompt guide (gates where all DoraBot paragraphs land), 11-D4 slider glow · 12-D1 Reports in the "90 %" · 13-D4 text-size range (also 20-D3), 13-D6 version on About, 13-R15 admin set-picture · 14-D2 atomic `/onboarding/finish`, 14-D3, 14-D4, 14-D6 locale at first run · 15-D1 (no admin password-policy override — confirmed), 15-D3, 15-D4 session-expiry UX · 16-D1 (= FU-919) keep the name-based store mapping, 16-D2 availability on the wire · 17-D2 drop `networkTimeoutSeconds`, 17-D1 iOS stays unbuilt · 18-D1 scheduled backups, 18-D2 multi-format export (recommend won't-do), 18-D5 bundle FU-625 · 19-D1 compose cookie default + banner, 19-D2 retire `appsettings.json`, 19-D3 `/health.db`, 19-D4 = FU-640 log policy · 20-D1 Layer C, 20-D2 toast two-tier rule, 20-D4 **Help information architecture** (gates the ~105 drafted entries), 20-D5 colour inventory → FU-010/224.

---

## Chunk 01 — Cookbook
*Source: [`CHUNK_01_cookbook.md`](../05_investigations/finalisation/CHUNK_01_cookbook.md) · analysed 2026-10-23*

### C. Senior review — Cookbook

Open FUs on this surface, cross-referenced rather than restated: FU-895, 902, 901, 900, 879, 876, 863, 858, 855, 793, 786, 772, 771, 770, 765, 761, 760, 757, 753, 750, 748, 746, 744, 742, 741, 736, 735, 734, 732, 730, 712, 691, 680, 670, 669, 646, 657, 645, 643, 638, 575, 624 (toast wrapper), 623 (dialog wrapper), 675 (BaseSelect sweep), 777.

#### C1. Bugs (verified or high-confidence latent)

- **01-R1** · class bug (latent, high-confidence) · `web_app/src/helpers/cookModeGuard.ts:567` · `ingredientLabel` precedence is `stock_item_name ?? raw_text`, ignoring the ingredient `label` ("tasty cheddar") that `RecipeDetailPage.ingredientLabel` (L1591) shows first; the guard dialog and the detail page therefore name the same missing row differently once a label is set (shipped 2026-10-21). · **Exact change:** add `web_app/src/helpers/recipeIngredientLabel.ts` exporting `ingredientDisplayName(ing: {label?, stock_item_name, raw_text}): string` = `label || stock_item_name || raw_text || 'Unnamed ingredient'`; use it in `cookModeGuard.ts:567`, `addToListRows.ts:675` (`name:`), `useRecipeDisplay`? (no — it doesn't name rows), and have `RecipeDetailPage.ingredientLabel` delegate to it (keeping its store lookup for the item name). · blast S · test guard: `cookModeGuard.spec.ts`, `addToListRows.spec.ts` (extend with a labelled row) · **execute**.
- **01-R2** · class bug (latent) · `web_app/src/components/recipes/RecipeIngredientRowEditor.vue:527` · after `createStockItemAsync`, the new item is found by `stockItems.value.find((s) => s.name === name)` although the store call returns the created entity; a name that differs after server trimming/normalisation leaves `created` undefined and the row silently stays unanchored. · **Exact change:** `const created = await stockItemStore.createStockItemAsync({...});` then use `created.stock_item_id` / `created.name` directly; delete L527. · S · test guard: none (dialog) — manual: create an item with trailing space · **execute**.
- **01-R3** · class bug (latent, ordering) · `dora_api/features/recipes/get_recipes.py:1627–1716` · `handle_by_id` builds `RecipeDto.from_entity(entity)` *before* the hydrations but computes `_compute_estimated_cost` and `_compute_nutrition` **after** `_hydrate_inference` — fine — however `_hydrate_unallocated` runs on `[_WithAssoc]` whose `available_meals` came from `from_entity`, while `cook_recipe` notes the entity attribute is stale after `bump_pool` in the *same* request. Not reachable today (detail is a separate GET). · **Verdict:** waive — record only; no change.
- **01-R4** · class bug (stale contract comment, misleads maintainers) · `get_recipes.py:1631–1637` and `:1786–1792` · comments say the detail route "has no `uuid:` converter" and that "the old filter-by-id path on the list endpoint still works as the cookbook overview's primary call"; the route is `/<uuid:recipe_id>` (L1794) and the SPA uses `GET /recipes/<id>` (`recipeApiService.getAsync`). · **Exact change:** delete L1631–1637 comment; rewrite L1786–1792 to "Detail endpoint — the SPA's `getAsync`; the list endpoint's filter-by-id form is unused by the SPA." · S · **execute**.

#### C2. Redundancy / DRY (R-001, R-003)

- **01-R5** · `dora_api/features/categories/manage_categories.py` (194) vs `cuisines/manage_cuisines.py` (197), `tools/manage_tools.py` (194), `dietary_tags/manage_dietary_tags.py` (209), plus `stock_groups/manage_stock_groups.py` (223), `meal_slots/manage_meal_slots.py` (246) · `diff` of categories vs cuisines after name substitution shows **only** the entity/router names differ: list-with-recipe-counts, create-with-dedupe-and-next-sequence, rename-with-dedupe, delete-with-affected-count. ~800 lines encoding one vocabulary manager four to six times. · **Exact change:** add `dora_api/features/_vocab/vocabulary_feature.py` with `register_vocabulary_crud(router, entity_cls, dto_name, id_field, recipe_fk_field, recipe_include_field, extra_fields=())` that defines the four handlers + routes; `manage_categories.py`/`manage_cuisines.py`/`manage_tools.py` become 10-line registrations. Dietary tags carry `category`; meal slots and stock groups have extra behaviour — keep them separate unless the factory's `extra_fields` hook covers them cleanly (decide at execution; start with the three identical ones). · M · test guard: `tests/e2e/dora_api/test_category_router.py`, `test_cuisine_router.py`, `test_tool_router.py` · **execute** (three identical modules first; dietary tags/meal slots/stock groups → follow-on if the factory fits).
- **01-R6** · `recipe_tag_access.py` vs `recipe_tool_access.py` · `_coerce_uuid`, `_all_*_ids`, `_name_to_id`, `validate_*_ids`, `resolve_*_filter_values`, `get_*_ids_for_recipes`, `set_*_ids_for_recipe`, `find_recipe_ids_with_all_*`, `find_recipe_ids_with_any_*` are the same nine functions over `(link_table, vocab_table, link_fk_name, vocab_noun)`. · **Exact change:** new `dora_api/features/recipes/_recipe_link_access.py` with `class RecipeLinkAccess(link_table_name, vocab_table_name, fk_column, noun, catalogue_hint)` exposing those nine methods; `recipe_tag_access.py` = `TAGS = RecipeLinkAccess("RecipeTag","DietaryTag","dietary_tag_id","dietary tag","See /api/recipes/tags…")` + thin module-level aliases preserving the current names (so 7 import sites don't change); `recipe_tool_access.py` keeps only `get_tool_ids_from_steps` + `sync_recipe_tools_from_steps` + aliases. Keep `get_tag_names_for_recipes` (tags-only). · M · test guard: `test_recipe_router.py` (tag/tool filters), `test_recipe_tools_derivation.py` · **execute**.
- **01-R7** · data-URL decoding × 5 · `get_recipes.py:1839–1861` and `:1870–1894` (inline, twice), `products/get_product_image.py:25`, `stores/manage_stores.py:327`, `users/get_user_image.py:30` (`_decode_data_url`) · the same regex + b64decode + `Response(mimetype, Cache-Control: no-cache)` five times. · **Exact change:** `dora_api/infrastructure/data_url.py` with `decode_data_url(blob: bytes|None) -> tuple[str, bytes] | None` and `data_url_response(blob, on_missing: Callable[[], Response]) -> Response`; replace the two recipe routes' bodies with `return data_url_response(recipe.image, lambda: not_found(...))` / same for step image; the other three features import the shared decoder (their chunks tick Applied when touched; do them here in one sweep since the change is mechanical). · S · test guard: `test_recipe_router.py` image tests, `test_product_router.py`, `test_store_router.py`, `test_user*` image tests (confirm names at execution) · **execute**.
- **01-R8** · `recipe_cost.py:147` `_key(v)` and `get_recipes.py:1562–1567` `_key(v)` · identical UUID/bytes/str → str normaliser. · **Exact change:** move to `dora_api/persistence/uuid_key.py` as `uuid_key(v) -> str`; import in both; delete both local defs. · S · guard: `test_recipe_line_cost.py`, `test_recipe_router.py` · **execute**.
- **01-R9** · `health_star_rating.py:198` and `nutri_score.py:222` `_points_for(value, table)` · identical table-threshold lookup; `nutri_score` also imports `kcal_to_kj` from the HSR module (FU-761). · **Exact change:** `dora_api/domain/rating_tables.py` with `points_for(value, table)` and `kcal_to_kj(kcal)`; both modules import from it; `nutri_score.py` drops its HSR import. · S · guard: `test_health_star_rating.py`, `test_nutri_score.py` · **execute** · tracked: FU-761 (closes).
- **01-R10** · `lookup.py:629` `_to_float` and `dataset_import.py:469` `_to_float` · identical. · **Exact change:** move to `nutrients.py` as `to_float(raw) -> float | None` (the module both already import), delete both locals; `nutrients.off_values` can then drop its injected `to_float` parameter (keep the param for one release if tests pass it — check `test_nutrition_lookup.py`). · S · guard: `test_nutrition_lookup.py`, `test_nutrition_dataset_import.py`, `test_off_lookup.py` · **execute**.
- **01-R11** · `lookup.py:556` `_portions_for` vs `household_measures.py:626` `portions_by_food` · same query, different shape (dicts vs rows). · **Exact change:** `_portions_for` becomes `{fid: [{"amount": p.amount, "measure": p.measure, "gram_weight": p.gram_weight} for p in rows] for fid, rows in portions_by_food(repository, food_ids).items()}`. · S · guard: `test_nutrition_lookup.py` · **execute**.
- **01-R12** · create/update response→HTTP mapping · `create_recipe.py:442–496` and `update_recipe.py:494–558` · the same nine-branch `if _Response.x: log; return y` chain. · **Exact change:** `dora_api/features/recipes/_recipe_errors.py` `def recipe_write_error_response(response, request, request_cls, logger) -> Response | None` covering `recipe_already_exists`, the three vocab not-found cases (guarded by `model_fields_set` membership, which is harmless on the create model), `missing_stock_item_ids`, `invalid_tag/step/section/choice/vocabulary_message`; both routes become `err = recipe_write_error_response(...); if err: return err`. · S/M · guard: `test_recipe_router.py` (422/400 cases) · **execute**.
- **01-R13** · `update_recipe.py:409–413` tool validation errors land in `invalid_tag_message` and log "Invalid recipe tag". · **Exact change:** add `invalid_tool_message` to both response dataclasses and both error chains (folded into 01-R12). · S · **execute**.
- **01-R14** · SPA option mappers · `RecipesOverview.vue:830–845`, `RecipeDetailPage.vue:1549–1554`, `RecipeEditDialog.vue:723–731` each map cuisines/categories/collections/dietary tags/tools to `{label, value}`. · **Exact change:** add getters to `recipeVocabStore.ts`: `cuisineOptions`, `categoryOptions`, `dietaryTagOptions` (with `category`), `toolOptions`; add `collectionOptions` to `recipeStore.ts`; the three consumers destructure them. · S · guard: vue-tsc; `recipeRailFilters.spec.ts` unaffected · **execute**.
- **01-R15** · `timeOfDayOptions` fallback · `RecipesOverview.vue:749–751`, `RecipeDetailPage.vue:1558–1559` · `mealSlotNames.length > 0 ? mealSlotNames : [...DEFAULT_MEAL_SLOTS]`. · **Exact change:** `mealSlotStore.ts` getter `slotNamesOrDefault`; both pages read it (also check `RecipeCookMode`/meal-plan consumers in Chunks 2/4). · S · **execute**.
- **01-R16** · `DIFFICULTY_OPTIONS = [...DIFFICULTY_VALUES]` · `RecipesOverview.vue:754`, `RecipeDetailPage.vue:1224` · **Exact change:** export `DIFFICULTY_OPTIONS` from `helpers/recipeVocabulary.ts`. · S · **execute**.
- **01-R17** · `newClientId()` × 4 · `useRecipeEditor.ts:88` (exported), `RecipesOverview.vue:1510`, `RecipeStepImagesEditor.vue:108`, `RecipeStructuredMethod.vue:401` · **Exact change:** delete the three local copies and import the exported one. · S · guard: vue-tsc, `recipeApiPaging.spec.ts` n/a · **execute**.
- **01-R18** · total time × 3 · `useRecipeDisplay.ts:67–72`, `RecipesOverview.vue:851–856`, `RecipeDetailPage.vue:1561–1565` (the page's variant treats 0+0 as null, the others treat null+null as null — a 0-minute recipe already reads differently). · **Exact change:** `helpers/recipeTime.ts` `totalMinutes(prep, cook): number | null` (null when both null; the page adopts this rule); all three call it. · S · guard: `recipeMetaLine.spec.ts` · **execute**.
- **01-R19** · favourite/cook/add-to-list action cluster · `RecipeCard.vue:148–184` and `RecipeRow.vue:438–475` · identical three buttons + rating chip + belief chip with the same props/emits. · **Exact change:** `components/recipes/RecipeActions.vue` (props: `recipe`, `labelledBelief`, `showFilterByIngredients`; emits the five events); both hosts render it. · S/M · guard: `recipeRowLayout.spec.ts`, `recipeRatingChip.spec.ts` · **execute**.
- **01-R20** · `getAllPagesAsync` · `recipeApiService.ts:481` and `stockItemApiService.ts:70` (comment admits the copy) · **Exact change:** `services/api/paging.ts` `fetchAllPages<T>(fetchPage: (page, limit) => Promise<Page<T>>, limit = 500): Promise<T[]>`; both services delegate. · S · guard: `recipeApiPaging.spec.ts` · **execute**.
- **01-R21** · Create-response shape hack · `recipeStore.ts:85–88` (`'recipe_id' in resource ? … : getAsync`), `RecipesOverview.vue:1470–1472`, `RecipeDetailPage.vue:2102–2103` (`(created as Record<string, unknown>).recipe_id ?? created.id`), same pattern in `stockItemStore.ts:103–106` · the server's `created()` always returns the full DTO body for recipes (`create_recipe.py:501`, `new_recipe_version.py:291`). · **Exact change:** type `createAsync`/`createNewVersionAsync` as `Promise<Recipe>`; `recipeStore.createRecipeAsync` pushes the result directly; delete the two page-level casts and use `created.recipe_id`. (Stock item store: Chunk 5/6.) · S · guard: vue-tsc, `test_recipe_router.py` already pins the 201 body · **execute**.
- **01-R22** · filter-state triple enumeration · `RecipesOverview.vue` `hasAnyFilter` (1218–1242), `activeFilterCount` (1247–1271), `clearFilters` (1365–1388) each list the same 22 fields; adding a filter means three edits (and `StockOverview.vue` has the same shape — Chunk 5). · **Exact change:** declare `const FILTERS: Array<{ ref: Ref<unknown>; isActive: () => boolean; reset: () => void }>` once (built from the `useListState` objects); derive `activeFilterCount = FILTERS.filter(f => f.isActive()).length`, `hasAnyFilter = activeFilterCount > 0 || searchText !== ''`, `clearFilters = () => FILTERS.forEach(f => f.reset())`. Consider promoting to `composables/useFilterRegistry.ts` shared with StockOverview at Chunk 5. · M · guard: `useListState.spec.ts`; add a vitest for the registry · **execute**.
- **01-R23** · `addToListRows.ts:640` `roundQuantity` · `formatQuantity` now rounds to 2 decimals itself (R-079, 2026-09-03). · **Exact change:** delete `roundQuantity`, pass `quantity` straight to `formatQuantity`. · S · guard: `addToListRows.spec.ts`, `formatQuantity.spec.ts` · **execute**.
- **01-R24** · `RecipeCostDialog.vue:738–741` recomputes per-serving as `total / servings` while the DTO carries server-owned `estimated_cost_per_serving` (R-003). · **Exact change:** replace the `servings` prop with `perServing: number | null`; `RecipeDetailPage.vue:1066` passes `recipe.estimated_cost_per_serving`. · S · **execute**.
- **01-R25** · `create_recipe.py:357–370` back-fills `section_id` with a Core `UPDATE` on rows the ORM just inserted, importing `db` locally. · **Exact change:** since `RecipeIngredient` maps `section_id` as a plain column (`update_recipe.py:350` sets it in the constructor), assign `ing_ent.section_id = real` on the pending entities instead and drop the Core update + local import. · S · guard: `test_recipe_router.py` section tests, `test_create_recipe_unit_of_work.py` · **execute**.
- **01-R26** · duplicate `nutrition_endpoints.py:31` imports `_require_admin` from `users/update_user_as_admin.py` while `auth/admin_gate.py:31` exports `require_admin` (8 callers vs 9 callers of the private one). · Cross-chunk — **Chunk 15** owns the admin-gate consolidation; recorded here because nutrition is one caller. · S · **execute (in Chunk 15's sweep)**.

#### C3. Dead code / unused fields / unread endpoints

- **01-R27** · `web_app/src/composables/useRecipeExport.ts:79–101` `downloadCsv` · grep `downloadCsv|useRecipeExport` across `web_app/src`: only `RecipeDetailPage.vue:1196/1292` imports the composable and calls **only** `openPrintView` (L2092); the stock overview has its own `downloadCsv`. Owner feedback (RECIPE DETAIL): "Export to csv feels weird, remove feature here." · **Exact change:** delete `downloadCsv` + its `fetch`/`parseFilename`/`triggerSave` imports (client side — nothing calls it). The server route `GET /recipes/<id>/export` (`dora_api/features/data/export_recipe.py:117–137`, `_build_csv` L30) then has **no caller in the SPA**, but two tests pin it (`tests/e2e/dora_api/test_api_fuzz.py:204`, `test_data_router.py:764`), so removing it is a deliberate API cut, not a tidy — **FU** for the owner ("drop the recipe CSV export endpoint + its two test references, or keep it as an API-only export?"). · S · guard: vue-tsc · **execute (client)** / **FU (server route)**.
- **01-R28** · `RecipeDetailPage.vue` scoped CSS with zero template uses (grep'd within the file): `.rn__edit` (2325–2340), `.rn__link` (2412–2418), `.rn__hintblock` (2587), `.rn__editor` (2588), `.rn__secrow` (2656–2661), `.rn__order`, `.rn__ordername`, `.rn__ordersec` (2669–2686). Leftovers from the popup-edit era. · **Exact change:** delete those rules. · S · **execute**.
- **01-R29** · `RecipesOverview.vue:1708–1710` `.full-height` — no template use. · **Exact change:** delete. · S · **execute**.
- **01-R30** · `get_recipes.py:1799` `from dora_api.domain.entities.recipe import Recipe as _Recipe` inside `get_recipe` while `Recipe` is imported at L15. · **Exact change:** delete the local import; use `Recipe.__name__`. · S · **execute**.
- **01-R31** · `create_recipe.py:499` local `from …get_recipes import GetRecipesHandler` and `new_recipe_version.py:287–289` local import of `GetRecipesHandler, get_recipes` · `create_recipe.py` already imports `get_recipes` at L22, so there is no cycle to avoid. · **Exact change:** hoist both to module imports. · S · **execute**.
- **01-R32** · `RecipeCostDialog.vue:185` comment references a `costLineReason` on "the page" — nothing by that name exists (grep). · **Exact change:** reword to "the server ships reason ids; this map is the only copy of their wording". · S · **execute**.
- **01-R33** · `RecipesOverview.vue:883–886` comment "Tag (cuisine + category) options — we synthesise tags from the cuisine and category columns" sits above `collectionOptionsWithNone` and describes a design retired by L235. · **Exact change:** replace with "Collection filter options, plus the '(Uncategorised)' sentinel." · S · **execute**.
- **01-R34** · `recipe_cookability.is_cookable` (`domain/recipe_cookability.py:84`) · docstring says "new code should call `cookability_state`"; grep callers at execution (`grep -rn "is_cookable(" dora_api tests`) — if only tests call it, delete it and update those tests to `cookability_state(...) is True`. · S · **execute (conditional on grep)**.
- **01-R35** · `RecipeDto` fields `has_structured_steps` (L469) and `has_step_images` (L527) — list-only existence flags; detail sets them from the loaded lists. Check SPA readers: `grep -rn "has_structured_steps\|has_step_images" web_app/src`. If unread (the SPA reads `steps_mode`), drop the two hydrations `_hydrate_structured_steps_flag`/`_hydrate_has_step_images` (two bulk queries per list page) and the fields. · S · guard: `test_recipes_query_count.py` (count goes down — adjust the pin) · **execute (conditional on grep)**.

#### C4. Componentisation opportunities (R-001)

- **01-R36** · `RecipeDetailPage.vue` is 2,727 lines (the doc-comment at L1118 says the *deleted* page was 2,727 lines — this one has grown to the same size). Extraction plan, each a self-contained block with its own state already localised: (a) `RecipeMasthead.vue` ← L25–216 + `.rn__masthead…rn__factv` styles (props: form, recipe, editing, options; emits dirty/toggle-edit/pick-photo); (b) `RecipeStatusStrip.vue` ← L304–391 (props: recipe, missing/atRisk/cost facts, batchEnabled; emits add-missing, adjust, open-cost); (c) `RecipeIngredientRail.vue` ← L395–683 + ingredient/section mutation functions L1913–2034 + styles `.rn__group…rn__add` (owns `ingredientsEditing`, emits dirty + save requests; the row editor moves with it); (d) `RecipeDetailsDrawers.vue` ← L856–1026 (additional details, nutrition, kcal, versions). The page keeps load/save/dirty/guards (~600 lines). · L · guard: none automated beyond vue-tsc; drive the page once after · **FU** (new follow-up: "Split RecipeDetailPage per 01-R36"; sequence after the S/M items land — the owner is happy with the page, so do it in one PR with a live walk).
- **01-R37** · `RecipesOverview.vue` filter panel (L105–399) is 300 lines of template; a `CookbookFilterPanel.vue` taking the registry from 01-R22 would make the page ~1,000 lines. · M · **FU** (bundle with 01-R36).
- **01-R38** · `RecipeNutritionCard.vue:45–156` the HSR and Nutri-Score blocks are the same template twice (row + working toggle + ledger + three notes); the author's comment argues for separation because copy differs. The *copy* can stay separate while the chrome is shared: `RatingWorking.vue` (props: badge slot, caption, ledger rows, notes[]) · S · **waive** — recorded; owner-happy surface and the duplication is bounded to one file.

#### C5. Placement / layering (R-003, R-005)

- **01-R39** · `get_recipes.py` reaches `db.session.execute` with `db.metadata.tables["MealPlanEntry"]` (L1540–1558) and `select(Recipe.id, Recipe.image.is_not(None))` (L1320) — bypasses the repository port (R-005). Both are documented carve-outs (UUID binding on SQLite). · **Exact change (placement only):** move `_hydrate_unallocated`'s two aggregate statements into `dora_api/features/meal_plans/commitment_access.py` as `committed_servings_by_recipe(recipe_ids, today)` and `plan_counts_by_recipe(recipe_ids)` — meal-plan commitment math belongs to the meal-plans feature, and Chunk 2 (FU-908/879) wants the same numbers. · S · guard: `test_recipe_is_planned.py`, `test_recipe_router.py` · **execute**.
- **01-R40** · `RecipeDetailPage.vue:1742–1746` `isMissingItem` derives "missing" from the stock store's `is_out_of_stock` while every ingredient already carries the server's `is_missing`; the page uses the store version because substitutes (not on the DTO) need it. Two sources of the same verdict on one page. · **Exact change:** for ingredient rows read `ing.is_missing` from `recipe.value` (map by `recipe_ingredient_id`); keep the store lookup only inside `loadSubstitutes` for the substitute candidates. · S · **execute**.
- **01-R41** · `RecipesOverview.vue:723` `EXPIRING_FILTER_HORIZON_DAYS = 14` mirrors `get_recipes.EXPIRING_HORIZON_DAYS` (R-003 two languages) · tracked **FU-669**; the R-089 codegen (`web_app/src/generated/units_table.ts` from `scripts/dump_units.py`) is the established mechanism. · **FU-669** (verdict: execute there by making the server default the horizon when the param is `?expiring=1`).
- **01-R42** · `helpers/recipeVocabulary.ts:359` `DIFFICULTY_VALUES` mirrors `ALLOWED_DIFFICULTY_VALUES`; `scaleQuantity.ts:446` `COUNTABLE_UNITS` mirrors the server's count dimension / `SUB_ITEM_UNITS` (R-003/R-089). · **Exact change:** extend `scripts/dump_units.py` to emit `ALLOWED_DIFFICULTY_VALUES`, `ALLOWED_STEPS_MODES` and `SUB_ITEM_UNITS` into `generated/`; `recipeVocabulary.ts` re-exports; `scaleQuantity.isCountableUnit` reads the generated count-dimension + sub-item sets. · S/M · guard: `scaleQuantity.spec.ts`, `test_units.py` · **execute** (Chunk 20 owns the generator; do the recipe consumers here).
- **01-R43** · `import_recipe_from_content.py` fuzzy-matching with RapidFuzz over `all_names` per request while `nutrition/suggestions.py` has a hand-rolled token matcher and the assistant has its own fuzzy helpers — three matching strategies for "which pantry item is this?". · **C9** verdict below; no relocation.

#### C6. Naming & idiom

- **01-R44** · `get_recipes.py` has **15** `import dataclasses` inside methods plus local imports of `money_features_enabled`, `estimate_costs_for`, `nutrition_mode`, `household_today`, `select`/`db` (R-008, R-019). None guards a cycle (`recipe_cost.py` and `recipe_rollup.py` don't import `get_recipes`). · **Exact change:** hoist to module imports; drop every in-method `import dataclasses`. · S · guard: pytest import; `test_recipe_router.py` · **execute**.
- **01-R45** · `get_recipes.py:143–149, 608` defensive `getattr(ingredient, "section_id", None)` etc. on attributes the entity always has (R-010/R-019); `recipe_cost.py:309/312/391/433` same `getattr(ingredient, "unit", None)` — there because the batch path once took entities; both callers now pass DTOs with the attributes. · **Exact change:** plain attribute access; keep `getattr` only in `recipe_cookability._required` (documented duck-typing for fixtures). · S · guard: `test_recipe_line_cost.py`, `test_recipe_item_price.py` · **execute**.
- **01-R46** · Pydantic request models: `Create*`/`Update*` Ingredient/Step/Section request classes are field-identical pairs (`create_recipe.py:52–125` vs `update_recipe.py:50–113`). · **Exact change:** define once in `recipe_requests.py` as `RecipeIngredientRequest`, `RecipeStepRequest`, `RecipeSectionRequest`; both handlers import; keep the two top-level `CreateRecipeRequest`/`UpdateRecipeRequest` (their optionality genuinely differs). · S · guard: `test_recipe_router.py`, `test_dto_contracts.py` (if it snapshots names — check) · **execute**.
- **01-R47** · `RecipeCard.vue:152` / `RecipeRow.vue:452` `:color="recipe.is_favourite ? 'red' : undefined"` — raw Quasar palette name where the page uses `text-negative` (R-002, D-020). · **Exact change:** `'negative'` (folds into 01-R19). · S · **execute**.
- **01-R48** · `recipeStore.getRecipesAsync` sorts with `Intl.Collator('en')` while the cookbook sorts again client-side; harmless but misleading (“store order”). · **waive**.
- **01-R49** · `suggestions.ignored_item_count` (`nutrition/suggestions.py:255`) uses `len(…all())` where the repository exposes `.count()` (used by `manage_categories.py:171`). · **Exact change:** `.count()`. · S · **execute**.

#### C7. Efficiency

- **01-R50** · `RecipeDetailPage.vue` does `stockItems.value.find(...)` per ingredient row per render in `stockItemName`, `isMissingItem`, `atRiskHeadline`, `substitutableNames` (O(rows × pantry)). · **Exact change:** `stockItemStore` getter `byId: ComputedRef<Map<string, StockItem>>`; the page reads it. (Also useful to Chunks 2/3/5.) · S · **execute**.
- **01-R51** · `_hydrate_expiring_ingredients` (`get_recipes.py:1439`) runs `load_expiring_stock_item_ids` on **every** list page even when no filter asked; it is one cheap query and the chips depend on it — **waive** (by design, documented).
- **01-R52** · `load_recipe_cookability` loads the whole cookbook for `?cookable` — tracked **FU-908**.
- **01-R53** · `_restrict_query` loads `all_recipes` just to seed `allowed` ids (L956) — a `select(Recipe.id)` would avoid hydrating entities; at household scale negligible. · **waive**.

#### C8. Design-level findings — out of Stage-2 scope

- **01-D1** · `is_favourite` is a recipe column, not per-user — in a two-account household one person's favourite is everyone's. Record for the multi-user readiness track (`MULTI_USER_READINESS.md`); no change.
- **01-D2** · Recipe name uniqueness is case-sensitive and application-level (FU-575) — tracked.
- **01-D3** · The stub-creator `RecipeEditDialog` still exists as an "Edit" path from the overview although the card has no edit button (feedback: "Edit button feels useless here") — `@updated` path is only reachable if some caller passes `recipe`; `RecipesOverview` only ever opens it with `editingRecipe = null`. The edit branch (`props.recipe` truthy) is therefore unreachable from the SPA: confirm at execution with `grep -rn "RecipeEditDialog" web_app/src` and, if the only host is the overview, simplify to a pure creator (drop `updated` emit + the update branch). · S · **execute (conditional on grep)**.

#### C9. Hand-rolled-vs-library verdicts
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| `_parse_recipe_from_text.py` (1,201 lines of regex heuristics) | paste-text recipe parser | `recipe-scrapers` (needs HTML + network, which FU-104/199 ruled out), `ingredient-parser-nlp` | **keep** | — | Operating on pasted plain text is the legal posture; corpus tests pin it. |
| `import_recipe_from_content.py` RapidFuzz `extractOne` | ingredient→pantry name match | already a library | **keep** | — | — |
| `nutrition/suggestions.py` token-recall scorer | item→food name match | RapidFuzz `token_set_ratio` | **keep** | — | Explainability (R-019) is the stated reason; threshold calibration documented. |
| `nutrition/lookup.py` `urlopen` + retry | OFF/USDA HTTP | `requests` (already a dependency: `requests_cache` in requirements) | **wrap-thin-adapter** | S | One `http_get_json(url, ua, timeout)` in `infrastructure/` shared with `dataset_import._download`; keeps retry policy in one place. **execute**. |
| `dataset_import.py` daemon thread + in-memory state | background import | APScheduler job / RQ | **keep** | — | Same shape as Piper voice download; a queue is anti-creep. |
| `pool.bump_pool` raw `text()` UPDATE … RETURNING | atomic floor-at-zero | ORM `update().returning()` | **keep** | — | Portability note documented; ORM form would need the same dialect split for bytes binding. |
| `recipeApiService.encodeFilterQueryString` | query-string build | `URLSearchParams` (used) vs `queryStringBuilder.createQueryString` | **wrap** | S | Fold the repeated-param encoding into `queryStringBuilder` so there is one encoder (Chunk 20 decides the shape). |
| `useDragDropList` in `RecipeStructuredMethod` | DnD | vuedraggable (`recipeStepImageEditorTypes.ts:13` comment still mentions it) | **keep** (R-022) | — | Fix the stale comment at execution. |

#### C10. Standards drift (R-0NN)

- **R-008/R-019** · local imports in `get_recipes.py` (01-R44) — fix.
- **R-010/R-019** · defensive `getattr` on known attributes (01-R45) — fix.
- **R-039** · `RecipeDetailPage.vue:1504–1509` (`onDiscard`) and `:2121–2126` (`onDelete`) `$q.dialog` buttons lack `noCaps` (the route-leave dialog at 2225 has it). · **Exact change:** add `noCaps: true` to `ok` and a `cancel: { label: 'Cancel', flat: true, noCaps: true }`. · S · **execute** · tracked FU-623 (wrapper) stays open.
- **R-002** · `RecipeNutriScore.vue:13–19` hard-coded hex grade colours — these are the published Nutri-Score brand palette (an external standard, R-059). · **explain in place**: add `// R-002 carve-out: Nutri-Score's published grade colours (Santé publique France); not themeable by definition.` and declare them as `--nutri-a…--nutri-e` tokens in `tokens.scss` so R-060 lint sees them. · S · **execute**.
- **R-002** · `RecipeCard.vue:307` `rgba(255,255,255,0.92)` initial glyph over a hashed hue — **explain in place** (`/* R-002 carve-out: ink over a per-recipe hashed hue, no theme token applies */`). · **execute**.
- **R-002/D-020** · `ExpiringChip.vue` `grey-7`/`white` palette classes — tracked **FU-777**.
- **R-047** · `useRecipeExport.downloadCsv` raw `fetch` — removed by 01-R27 (FU-647 covers the stock-overview sibling).
- **R-003** · 01-R24, 01-R40, 01-R41, 01-R42 above.
- **R-035/D-rules** · `RecipeRow.vue` raw px chrome mirrors `StockItemRow` — tracked **FU-791/FU-693**.

#### C11. Ride-along signals for FU-010 / FU-224 (theme / colour)
- `RecipeCard`/`RecipeRow` favourite uses palette `red` (→ `negative`).
- `RecipeNutriScore` fixed hex grades — fine as a standard, but no dark-theme contrast check has been done on the E/D letters over the pill.
- `RecipeRatingChip`/`RecipeHealthStars` partial state dims via opacity — FU-772 (rating pill tint, no dark pass).
- `RecipeStructuredMethod` timer pill uses `color-mix` on `--brand-primary` (12 %/35 %) — same class of low-alpha wash the owner found invisible on the cost share bars (09-08); check in pesto dark.
- `TriStateFilterChip` include/exclude use `info`/`warning` semantic colours for Planned/Not planned — a semantic colour carrying a non-semantic meaning (FU-224 shortlist).

### E. Proposed follow-ups (orchestrator allocates ids)

- **urgent? no** · type=finding · *Guard dialog and recipe page name a labelled ingredient differently* (01-R1) — fix in Stage 2; no FU needed if executed this run.
- type=follow-up · *Split `RecipeDetailPage.vue` into masthead / status strip / ingredient rail / details drawers* (01-R36, plus 01-R37) — why deferred: large blast radius, owner is happy with the page, needs a live walk after. Recommended: after this run's S/M findings land, one PR.
- type=follow-up · *Vocabulary CRUD factory: extend to dietary tags, meal slots, stock groups* (01-R5 phase 2) — why deferred: those three carry extra fields/behaviour; do after the three identical ones prove the factory. Recommended: opportunistic.
- type=finding · *Per-user favourites* (01-D1) — recommended: when multi-user readiness is next picked up; link `MULTI_USER_READINESS.md`.
- type=finding · *`stockItemStore.createStockItemAsync` callers that re-find by name* (01-R2 pattern — grep other callers at execution) — recommended: now (Stage 2 of this chunk).

---

## Chunk 02 — Meal Plans
*Source: [`CHUNK_02_meal_plans.md`](../05_investigations/finalisation/CHUNK_02_meal_plans.md) · analysed 2026-10-23*

### C. Senior review — Meal Plans

#### C1. Bugs (verified or high-confidence latent)

- **02-R1** · latent, medium-high · `dora_api/features/meal_plans/reconcile_consumed_meals.py:157` · the daily sweep inserts `MealPlanReconcileReceipt.id` as `str(uuid.uuid4())` through raw `text()`, while `reconcile.py:748` inserts the same column as `_id_bytes(...)` (16 raw bytes on SQLite). On SQLite the receipt table therefore holds a **mix of TEXT and BLOB ids** in a `UUIDType` BINARY(16) column. Nothing reads receipts through the ORM today (grep `get(MealPlanReconcileReceipt)` → none), which is the only reason it is latent; the `ORDER BY created_at DESC, id DESC` tie-break (FU-529) also compares TEXT against BLOB, which SQLite orders by storage class rather than value. · **Exact change:** bind the id the same way the verb path does — the shared UUID bind helper from 01-R8 (`persistence/uuid_key.py` gains `uuid_bind(value, dialect_name)`), passing `dialect_name=_Conn.dialect.name` in `_insert_receipt` for both `id` and `entry_id`. Add `test__sweep_receipt_ids__round_trip_through_orm` (load receipts via `repository.get(MealPlanReconcileReceipt).all()` after a sweep). · S · guard: `test_reconcile_receipts.py`, `test_reconcile_verbs.py` · **execute**.
- **02-R2** · latent, high-confidence · `web_app/src/composables/useMealPlanner.ts:1059–1068` `nextWeekCommands` maps only `recipe_id/scheduled_for/servings/slot`, dropping `cook_key` and `cook_fresh`; "Duplicate to next week" turns a cook batch into N standalone meals and un-marks fresh meals, silently. · **Exact change:** build from `toCommand(e)` (drop `meal_plan_entry_id`, shift `scheduled_for` by 7). · S · guard: add a vitest once the mapping is a pure helper (§D) · **execute**.
- **02-R3** · bug (locale) · `web_app/src/components/MealPlanBuilderDialog.vue:696–698` `money(n) = `$${n.toFixed(2)}`` hard-codes the dollar sign and two decimals, bypassing `formatMoney` (R-056; FU-043). · **Exact change:** `import { formatMoney } from 'src/composables/useMoney'`; delete `money`; replace the three call sites (L273, L344, L347). · S · **execute**.
- **02-R34** · bug (R-021, negative-UTC-offset devices) · `web_app/src/components/MealPlanMobileFocus.vue:387` `dayOfMonth(iso) { return new Date(iso).getDate(); }` — a date-only ISO parses as UTC midnight, so west of Greenwich the phone's day strip shows yesterday's number under every chip. `helpers/weekDates.ts:40–47` documents this exact trap and ships `parseLocalIso`. · **Exact change:** `Number(iso.slice(8, 10))` (the calendar already does this at `MealPlanCalendar.vue:861`). · S · guard: `weekDates.spec.ts` style unit test · **execute**.
- **02-R35** · bug (R-021) · `web_app/src/pages/MealReconcileRunner.vue:304` `todayIso = new Date().toISOString().slice(0, 10)` — UTC "today", used as the `:max` of the "Cooked later" date input; east of UTC in the evening it is yesterday, so today's date is un-pickable. · **Exact change:** read `mealPlanStore.today` (server household date) with `localTodayIso()` as the pre-load fallback, as the planner does. · S · **execute**.
- **02-R36** · R-045 violation (the exact signal FU-682 names) · `web_app/src/composables/useMealPlanExport.ts:762–764` `window.open(`${baseUrl}/meal-plans/${id}/print-view`)` — the same unauthenticated-navigation defect `useRecipeExport.openPrintView` was fixed for (Capacitor shell / cross-site SPA → 401 in a new tab). · **Exact change:** mirror `useRecipeExport.openPrintView`: `void openHtmlDocumentAsync(`/meal-plans/${id}/print-view`, 'Meal plan').catch(...)`, sync entry (R-046). Update `useMealPlanExport.spec.ts`. · S · **execute** (tracked FU-682 — this is one of its three).

#### C2. Redundancy / DRY (R-001, R-003)

- **02-R4** · `get_meal_plans.py` `_hydrate_nutrition` (L385–390), `_hydrate_cost` (L475–480), `_hydrate_inference` (L590–596) each re-load the plan's distinct recipes with ingredients; `_hydrate_cookability` (L734) loads the whole cookbook again. Tracked **FU-879** (two loads) — it is three plus one. · **Exact change:** a per-call `_recipes_with_ingredients(recipe_ids)` memo on the handler (`include(STOCK_ITEM).then_include(STOCK_LEVEL)` once), consumed by all three; cookability from the same entities via `missing_count_for(r.ingredients, resolve_levels_by_item(...))`. · M · guard: `test_meal_plan_router.py`, `test_meal_plan_nutrition.py`, `test_meal_plan_cost.py` · **execute** (closes FU-879; part of FU-908).
- **02-R5** · `get_meal_plans.py:168–204` `_CostIngredient`/`_CostInput` adapt entities for `estimate_costs_for`; `recipe_rollup.input_from_entity` already produces a shape the pricing ladder duck-types. · **Exact change:** delete the two dataclasses; `estimate_costs_for(self.repository, [input_from_entity(r) for r in recipes])`. · S · guard: `test_meal_plan_cost.py` · **execute**.
- **02-R6** · `get_meal_plans.py:315–351` `_hydrate_entry_has_image` duplicates `get_recipes._hydrate_has_image`. · **Exact change:** `features/recipes/image_flags.py::recipe_ids_with_image(ids) -> set[UUID]`; both call it. · S · **execute** (pairs with Chunk 1).
- **02-R7** · `create_meal_plan.py:66–132` and `update_meal_plan.py:66–248` repeat: slot validation, `validate_cook_groups`, past-date guard, recipe-resolution loop, `CookBatch` minting, `MealPlanEntry(...)` construction, and the error→HTTP chain. · **Exact change:** `meal_plans/_entry_writes.py` with `resolve_recipes(repository, reqs) -> (by_id, missing)`, `has_past_entry(reqs, today)`, `mint_batches(repository, plan_id, reqs, preserved_by_key=None)`, `new_entry(req, recipe, batch)`, `meal_plan_write_error_response(response, request)`; both handlers shrink to orchestration. · M · guard: `test_meal_plan_router.py`, `test_cook_batches.py` · **execute**.
- **02-R8** · `CreateMealPlanEntryRequest` vs `UpdateMealPlanEntryRequest` differ only by `meal_plan_entry_id`. · **Exact change:** `MealPlanEntryRequest` base in `_entry_writes.py`. · S · **execute**.
- **02-R9** · `reconcile.py` carries the latest-receipt `NOT EXISTS (… r2.created_at > r.created_at OR (… AND r2.id > r.id))` predicate **five times** (L239–255, L325–345, L366–380, L400–418, L434–446). · **Exact change:** constants `_LATEST_RECEIPT_FILTER`, `_ENTRY_RECEIPT_SELECT`; one `_receipt_rows(today, *, pending_states, cursor, limit, newest_first)` + `_receipt_count(today, pending_states=None)`; the four fetch/count functions become one-liners; `reconcile_overdue_signal` reuses the filter. · M · guard: `test_reconcile_receipts.py`, `test_reconcile_verbs.py`, `test_reconcile_signal.py` · **execute**.
- **02-R10** · `reconcile.py:523–536` `_id_bytes` and `:300–305` `_stringify_entry_id` duplicate `pool.bump_pool`'s bind normaliser and `recipe_cost._key`. · Folded into **01-R8**. · **execute**.
- **02-R11** · `_too_many_requests(retry_after)` × 5 — `reconcile.py:159`, `assistant/ask_assistant.py:72`, `auth/bootstrap_admin.py:73`, `auth/email_flows.py:47`, `auth/register_user.py:351`. · **Exact change:** `api_response.too_many_requests(retry_after)`; delete the five. · S · guard: `test_auth_flows.py`, `test_reconcile_verbs.py`, assistant rate-limit tests · **execute** (owned here; Chunks 15/11 tick their call sites).
- **02-R12** · `_current_user_id()` × 15 modules. Tracked **FU-654**. · **Exact change:** `infrastructure/auth_helpers.current_user_id()`; sweep. · S · **execute (FU-654)**.
- **02-R13** · hand-rolled install-wide money/budget reads: `build_week.py:438–473`, `swap_suggestions.py:637–640, 698–708` (`repository.get(AppSetting).all()[0]`) while `app_settings/access.py` exports `money_features_enabled`/`get_or_create_app_setting`. Tracked **FU-759**. · **Exact change:** `features/budget/budget.py::household_budget(repository) -> HouseholdBudget(amount, period)` + `budget_remaining(repository, today)`; both modules use them. · S · guard: `test_build_week.py`, `test_swap_suggestions.py`, `test_budget_router.py` · **execute**.
- **02-R14** · `_all_recipe_dtos(repository)` duplicated in `build_week.py:512` and `swap_suggestions.py:651`. · **Exact change:** one `features/recipes/all_recipes.load_all_recipe_dtos(repository)` (see 02-R29). · S · **execute**.
- **02-R15** · `build_week.compute_auto_build:577` calls `GetMealSlotsHandler.handle()` for slot *names*, which loads every MealPlanEntry and Recipe (02-R30). · **Exact change:** `slot_validation.ordered_slot_names(repository)`. · S · **execute**.
- **02-R16** · `useMealPlanner.ts:159–161` and `MealPlanRecipePicker.vue:297–299` repeat the `mealSlotNames.length ? … : [...DEFAULT_MEAL_SLOTS]` fallback (copies 3 and 4 of 01-R15); `MealPlanRecipePicker.vue:300` `[...DIFFICULTY_VALUES]` is copy 3 of 01-R16. · Folded into **01-R15 / 01-R16**. · **execute**.
- **02-R17** · `MealPlansOverview.vue` renders `MealPlanShoppingSummary` twice (L107–120, L541–556) with the same twelve props. · **Exact change:** `shoppingSummaryProps` computed + `v-bind`. · S · **execute**.
- **02-R18** · the same eight `entry-*` handlers are wired at `MealPlansOverview.vue:56–72` (mobile) and `:498–506` (week card), and each of `MealPlanWeekDayCard.vue:85–92, 115–122`, `MealPlanMobileFocus.vue:745–752`, `MealPlanEntryChip.vue:111–118`, `MealPlanRichCard.vue:544–551` re-emits them again (six copies of the same eight lines). · **Exact change:** page: `const entryHandlers = {...}` + `v-on="entryHandlers"`; cards: forward the menu with `v-on="$attrs"`-style passthrough or an `entryListeners(entry)` helper returning the object. · S · **execute** (with 02-R17 and 02-R19b).
- **02-R19b** · `MealPlanRichCard.vue` (phone) and `MealPlanEntryChip.vue` (desktop) scripts are ~90 % identical: `inferenceTooltip`, `linked`, `fresh`, `cookMarkerLabel`, `status`, `priceLabel`, `accessibleLabel`, plus the same glyph run in both templates (chip L60–102, card L490–527). · **Exact change:** `composables/useMealEntryPresentation.ts` (`entry, shortfall` → those seven computeds) and a `MealEntryGlyphs.vue` for the Dora-hunch/price/check/chef-hat/fridge run; both hosts keep only layout. · M · guard: `mealPlanEntryStatus.spec.ts` + a new spec for the composable · **execute**.

#### C3. Dead code / unused fields / unread endpoints

- **02-R19** · `useMealPlanner.ts` returns **13 members nothing reads** (grep `planner.<name>` → 0 each): `dayCost` (L182–186), `cookByLabel` (207–213), `freshEntries` (204–206), `needsCookingEntries` (197–199), `needToBuyOnList` (729–731), `slideDir`, `prefersReducedMotion`, `recurringSourceOptions` (internal), `slotNameSet` (internal), `mealPlans`, `today`, `suggestionsLoading`, `onKeydown`. · **Exact change:** delete the first five outright; drop the other eight from the return object. · S · guard: vue-tsc · **execute**.
- **02-R20** · `MealPlansOverview.vue:1295–1307` `.planner-toolbar__statusrow` / `.planner-toolbar__status` — status row deleted 2026-09-12. · **Exact change:** delete both rules. · S · **execute**.
- **02-R21** · `mealPlanStore.getShortfallAsync` + `shortfall` ref (L54–89), `mealPlanApiService.getShortfallAsync` (L66–67), `models/mealPlan.ts:158` `Shortfall` type — no client consumer (**FU-862**). · **Exact change:** delete all three (endpoint stays for the assistant). · S · **execute (FU-862)**.
- **02-R22** · `MealPlan.name` / `MealPlanDto.name` — instances nameless since C-2.E. · **Exact change:** grep `plan.name`/`.name` readers of `MealPlan` in `web_app/src`; if none, drop from the DTO (column stays, R-095). · S · **execute (conditional)**.
- **02-R23** · `MealPlanRecipePicker.vue` multi-select mode — `selectionMode`, `selectedIds`, `isMultiSelect`, `isSelected`, `toggleSelection`, the `update:selectedIds` emit and both `q-checkbox` branches (L150–154, 175–179, 253–255, 405–415) — no host passes `selection-mode` (grep → only `MyProductsPage`'s unrelated `selectedIds`). The "pick myself" builder path that used it was removed 2026-09-03. · **Exact change:** delete; `onRowPick` becomes `emit('recipePick', id)`. · S · **execute**.
- **02-R24** · `helpers/recipeRailFilters.ts:367` `axisFiltersActive` — exported, zero importers. · **Exact change:** delete. · S · **execute**.
- **02-R25** · `MealPlanSkeleton.vue` `grid` variant (L819–834, styles L863–875) — Direction B was retired 2026-07-07 (FU-304); the page passes only `'mobile' | 'list'`. · **Exact change:** delete the variant and its CSS. · S · **execute**.
- **02-R26** · `mealPlanTemplateStore.cloneAsync` (L1017–1020) — grep `cloneAsync(` in `web_app/src`: confirm at execution; the templates page has no Clone action since the 09-13 redesign. If unused, delete the store method, `mealPlanTemplateApiService.cloneAsync` and consider the server `POST /meal-plan-templates/<id>/clone` (test `test_clone_meal_plan_template_unit_of_work.py` pins it → **FU**, same shape as 01-R27). · S · **execute (client) / FU (server)**.

#### C4. Componentisation opportunities (R-001)

- **02-R27** · `function pageStyleFn(offset, height)` is copied verbatim in **six pages**: `MealPlansOverview.vue:810`, `MealReconcileRunner.vue:266`, `MealReconcileLog.vue:588`, `SettingsShell.vue`, `StockOverview.vue`, `StocktakeRunner.vue`. · **Exact change:** `helpers/appShell.ts` `export function appShellStyleFn(offset: number, height: number)`; six imports. · S · guard: vue-tsc; drive one shell page · **execute**.
- **02-R28** · `.runner-shell` / `.runner-topbar` / `.runner-card-wrap` / `.runner-card` + the close-X · progress · (?) strip are copied across `MealReconcileRunner.vue`, `MealReconcileLog.vue` and `StocktakeRunner.vue` (the runner's own comment says "same shape as StocktakeRunner"). · **Exact change:** `components/RunnerShell.vue` (props: `closeTo`, `progress?`, `progressLabel?`, `helpTopic`; slots default/`topbar-extra`) hosting the shell CSS once; the three pages become content. · M · guard: none automated — drive the three once · **execute** (coordinate with Chunk 5; the `(?)` becomes a `HelpHint` per 02-R40).
- **02-R29** · lean candidate loader for `build_week` / `week_suggestions` / `swap_suggestions` / `lighter-alternatives` — all run the full `GetRecipesHandler` pipeline (tags, expiring, images, pool, nutrition rollup, inference, cost) over ≤ 10,000 recipes to read ten fields; `swap_suggestions` additionally runs the six-hydration `GetMealPlansHandler.handle_by_id` just for entries. · **Exact change:** `features/recipes/candidates.py::load_recipe_candidates(repository) -> list[RecipeCandidate]` built from `_base_query` + `load_recipe_cookability` + `count_expiring_ingredients_per_recipe` + `estimate_costs_for` + the unallocated/plan-count aggregate; a plain entries read for swaps. · M · guard: `test_build_week.py`, `test_meal_plan_router.py`, `test_swap_suggestions.py`, `test_lighter_alternatives.py` · **FU** (new; sequence after 02-R4).

#### C5. Placement / layering (R-003, R-005)

- **02-R30** · `manage_meal_slots.GetMealSlotsHandler.handle` (L47–63) loads **all** `MealPlanEntry` and **all** `Recipe` rows into Python to count slot usage. · **Exact change:** two `select(col, func.count()).group_by(col)` statements. · S · guard: `test_meal_slot_router.py` · **execute**.
- **02-R31** · `get_meal_plan_ingredients.aggregate_meal_plan_ingredients` (L96–103) issues one `.one()` query per recipe; the preview endpoint runs it on every servings tick in the builder. · **Exact change:** one `.all(in_(ids))` with the same includes. · S · guard: `test_meal_plan_ingredient_aggregate.py`, `test_meal_plan_preview.py` · **execute**.
- **02-R32** · `MealPlanBuilderDialog.vue:641–646` `defaultSlots` picks slots by regex `/breakfast|lunch|dinner/i`; `slotFor` (L814) falls back to the literal `'Dinner'`; `build_week.place_entries:353` and `place_entries_batched:378` fall back to `["Dinner"]` — four hard-codings of names in a user-editable vocabulary (R-003). · **Exact change:** client defaults `selectedSlots` to **all** household slots and `slotFor` to `pool[0]`; server falls back to `household_slots[0]`. · S · guard: `test_build_week.py` · **execute** (behaviour default change — note in CHANGELOG).
- **02-R33** · `useMealPlanner.recipeNameById` linear `find` per aggregate row (L842–844). · **Exact change:** `Map` computed. · S · **execute**.
- **02-R37** · raw Quasar palette vars and literal `white` in planner components: `var(--q-primary)` / `var(--q-warning)` / `var(--q-accent)` at `MealPlanWeekDayCard.vue:367, 376, 377, 380, 421, 422`, `MealPlanRichCard.vue:684, 693`, `MealPlanEntryChip.vue:270, 273`, `MealPlanMobileFocus.vue:1023–1037` (+ `color: white` ×3), `MealReconcileLog.vue:761–764`; the rest of these files use `--brand-primary` / `--semantic-warning` / `--text-on-primary`. Two token families in one surface (R-002 / R-060 / D-rules). · **Exact change:** `--q-primary` → `--brand-primary`, `--q-warning` → `--semantic-warning`, `--q-accent` → `--brand-secondary` (check the accent's intent), `white` → `--text-on-primary` (FU-674 governs that token's contrast). · S · **execute**.
- **02-R38** · literal transition durations (D-010) ×8: `MealPlanWeekDayCard.vue:349, 416`, `MealPlanRichCard.vue:667`, `MealPlanEntryChip.vue:260`, `MealPlanMobileFocus.vue:1011, 1102`, `MealPlansOverview.vue:1332`, `MealPlanBuilderDialog` none. · **Exact change:** `var(--motion-fast) var(--motion-ease)`. · S · **execute**.
- **02-R39** · raw px where tokens exist (`gap: 8px`, `padding: 6px 8px`, `border-radius: 8px`, `6px`, `999px`, `margin-bottom: 4px` …) throughout `MealPlanWeekDayCard.vue`, `MealPlanEntryChip.vue`, `MealPlanRichCard.vue`, `MealPlanMobileFocus.vue`, `MealPlanBuilderDialog.vue`, `MealReconcile*.vue` (rem literals) — against `--space-*`, `--radius-*`, `--radius-pill`. Same numeric values exist as tokens, so this is substitution only. · S (mechanical, many lines) · **execute** — do it as one sweep with 02-R37/02-R38 and drive both breakpoints once after.
- **02-R40** · owner directive 2026-08-27 (*"Info button should take you to help and guides, not open a modal"*) not applied to `MealReconcileRunner.vue:210–240` and `MealReconcileLog.vue:536–563` `(?)` dialogs. · **Exact change:** move both texts into the HelpPage entry *Reconcile past meals* (§B2) and replace the two buttons with `<HelpHint topic="Reconcile past meals">`; delete `helpOpen` refs and the dialogs. · S · **execute** (Help track deliverable).

#### C6. Naming & idiom

- **02-R41** · `get_meal_plans.py` local imports inside every hydration (R-008). · **Exact change:** hoist. · S · **execute**.
- **02-R42** · `helpers/mealPlanEntryKey.ts:1624–1630` docstring says PATCH "deletes the future entries and inserts new rows … an entry's database id changes every time anything in the week is saved" — false since FU-878 (match-and-update keeps ids). The content-identity key is still right (the batch rebuild re-mints ids). · **Exact change:** reword to the current contract. · S · **execute**.
- **02-R43** · `useMealPlanner.ts:276–290` and `:819–822`, `:792–795` carry retired-feature epitaphs (drag-to-add, `logPaletteCook`, `goToManageTemplates`); `MealPlansOverview.vue:933–938` likewise. These are history the worklog holds. · **Exact change:** trim each to one line pointing at the worklog date. · S · **waive** (comment hygiene only; do opportunistically with 02-R19).

#### C7. Efficiency
- 02-R4, 02-R29, 02-R30, 02-R31, 02-R33 above.
- **02-R44** · `MealPlanWeekDayCard.vue:227–229` `collapsedSummary` flat-maps every slot's entries per render; trivial at 7×5. · **waive**.

#### C8. Design-level findings — out of Stage-2 scope
- **02-D1** · Templates carry no cook-batch / cook-fresh information (`MealPlanTemplateEntry` is day offset, slot, servings), so applying one to a batch household yields standalone meals. Owner decides whether templates should snapshot batches.
- **02-D2** · `get_shortfall` is assistant-only; the planner reads `needs_cooking` per entry. Two readings of one model, documented — noted so nobody re-unifies them.
- **02-D3** · One plan per week per install (`MealPlan.start_date` is the lookup key, `_fork_template_onto_week` finds by `start_date`); there is no per-user plan. Record for `MULTI_USER_READINESS.md`.
- **02-D4** · `useMealPlanner` is 1,239 lines carrying navigation, mutations, templates, add-to-list, suggestions and budget. It is coherent and documented; splitting (`useMealPlanWeek`, `useMealPlanTemplates`, `useMealPlanShopping`) would be a design-level restructure. **FU** (bundle with 01-R36's page-split follow-up).

#### C9. Hand-rolled-vs-library verdicts
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| `reconcile.py` raw-SQL cursor pagination + latest-receipt `NOT EXISTS` | keyset paging | SQLAlchemy Core `select()` with window functions | **keep** (as refactored by 02-R9) | — | SQLite < 3.25 has no window functions; the comment says so. |
| `reconcile_consumed_meals.py` connection-level sweep | daily job body | — | **keep** | — | Decoupled transaction is the point. |
| `build_week.select_recipes` greedy ranker + `random.Random` sampling | week generator | an optimiser (OR-tools) | **keep** | — | Anti-creep; fixture-tested. |
| `weekDates.ts` (`shiftDays`, `mondayOf`, `parseLocalIso`) | date arithmetic | `date-fns` / `dayjs` | **keep** | — | Six small pure functions with a spec; a date library would be the app's only one. |
| `useMealPlanner` touch swipe (`onTouchStart/End`, 60px threshold) | gesture | Quasar `TouchSwipe` directive (already in the framework) | **wrap** | S | `v-touch-swipe.vertical` replaces 10 lines and gains velocity handling; execute with 02-R19. |
| `MealPlanCalendar` roving-tabindex grid | a11y grid | — | **keep** | — | Correct and measured. |

#### C10. Standards drift (R-0NN)
- **R-021** · 02-R34, 02-R35 (fix).
- **R-045/R-046** · 02-R36 (fix; FU-682).
- **R-056 / FU-043** · 02-R3 (fix).
- **R-003** · 02-R32 (hard-coded slot names) — fix.
- **R-008** · 02-R41 — fix.
- **R-002 / R-060 / D-010 / D-rules tokens** · 02-R37, 02-R38, 02-R39 — fix as one sweep.
- **R-039** · `$q.dialog` calls in `useMealPlanner.ts` and `MealPlansOverview.vue` carry `noCaps` — clean. `MealPlanTemplatesPage.vue:253–257` `cancel: true` without `noCaps` on `confirmDeleteTemplate`. · **Exact change:** `cancel: { label: 'Cancel', flat: true, noCaps: true }`. · S · **execute**.
- **FU-624 / FU-675** · raw `$q.notify` ×17, raw `q-select` ×3 (`MealPlanBuilderDialog.vue:277–293`, `MealPlanTemplatesPage.vue:160–167`) — tracked.
- **Owner directive 2026-08-27 (help modals)** · 02-R40 — fix.

#### C11. Ride-along signals for FU-010 / FU-224 (theme / colour)
- Mixed `--q-*` vs `--brand-*`/`--semantic-*` families across the planner (02-R37) — the surface the owner tuned most by eye in September, so re-check pesto dark after the sweep.
- `MealPlanMobileFocus` focused day chip: `--q-primary` fill with `white` ink and `white` pips — FU-674 (`--text-on-primary` contrast) applies.
- `MealPlanRailFilterChips`: `active-color="secondary"` for every chip but Suggests — FU-621/FU-652 (secondary colour) shortlist.
- `MealReconcileLog` pills: four `color-mix(--q-<semantic> 30%)` borders over `--semantic-*-soft` fills — same low-alpha-wash class as the 09-08 cost bars; check in dark themes.
- `MealPlanWeekDayCard` `.day-card--past { opacity: 0.6 }` and `.rich-card--consumed { opacity: 0.55 }` — opacity-dimming on top of muted ink can fall under the D-002 floor in light themes.

### E. Proposed follow-ups (orchestrator allocates ids)

- **urgent** · type=finding · *Reconcile sweep stores receipt ids as TEXT on SQLite while the verb path stores BLOB* (02-R1) — resolved in Stage 2 if executed this run; otherwise open as urgent.
- type=follow-up · *Lean recipe-candidate loader for the week builder, rail suggestions, swap and lighter endpoints* (02-R29) — why deferred: medium blast radius across four endpoints; sequence after 02-R4.
- type=follow-up · *Server `POST /meal-plan-templates/<id>/clone` has no client caller* (02-R26, conditional) — owner call: drop the endpoint + its unit-of-work test, or keep as API-only.
- type=finding · *Templates don't snapshot cook batches / fresh marks* (02-D1) — owner decision.
- type=finding · *Meal plans are per-install, not per-user* (02-D3) — link `MULTI_USER_READINESS.md`.
- type=follow-up · *Split `useMealPlanner` into week / templates / shopping composables* (02-D4) — bundle with 01-R36.
- type=finding · *Rail row chrome is the third copy of the list-row surface* — already **FU-802/FU-791**; no new entry.

---

## Chunk 03 — Shopping Lists
*Source: [`CHUNK_03_shopping_lists.md`](../05_investigations/finalisation/CHUNK_03_shopping_lists.md) · analysed 2026-10-23*

### C. Senior review — Shopping Lists

#### C1. Bugs (verified or high-confidence latent)

- **03-R1** · latent, high-confidence · `manage_shopping_list.py:344–352` `CopyShoppingListHandler` copies `stock_item_id/quantity/selected_product_id/sequence` only. A **product-only line** (`stock_item_id` NULL, `product_id` set — `test_shopping_list_product_lines.py` proves they exist) is copied with **both anchors NULL**, violating `ck_shopping_list_line_anchor` → 500 on the whole copy. It also drops `product_id`, `preferred_buy_id`, `planned_store_id`, `added_at` and skips `apply_line_defaults`, so the copy forgets every "which one"/store choice. · **Exact change:** copy `product_id`, `preferred_buy_id`, `planned_store_id`, set `added_at=now`, call `apply_line_defaults`. **However** the client has no caller (`copyAsync` removed; `shoppingListApiService.ts:231`) and the endpoint is pinned only by `test_copy_shopping_list_unit_of_work.py` + `test_api_fuzz.py:222` → the better fix is **delete the endpoint + its test** (FU-766 shape; "Save as template" replaced it). · S · **execute (delete)** — owner may veto; if kept, apply the field fix instead.
- **03-R2** · latent, high-confidence · `manage_templates.py:647, 662–669` `SnapshotFromListHandler`: (a) `f"Template from {source.name}"` → "Template from None" for a self-labelled list (`display_name` exists — the SPA pre-fills its own name so it only shows when the prompt is blanked); (b) a product-only source line yields `ShoppingListTemplateLine(stock_item_id=None)` on a NOT NULL column → IntegrityError → 500 for any list carrying one. · **Exact change:** `source.display_name`; skip lines with `stock_item_id is None` (templates are item-anchored by design) and report `skipped_product_lines` in the response. · S · guard: `test_snapshot_shopping_list_template_unit_of_work.py` + new case · **execute**.
- **03-R3** · latent · `list_actions.py:116–130` `MoveLinesHandler` de-dupes on `stock_item_id` alone: `target_item_ids` contains `None` whenever the target has a product-only line, so **every** product-only movable line is "skipped as duplicate"; and the first product-only line moved adds `None`, skipping the rest. · **Exact change:** key on `(stock_item_id, product_id)` via a small `line_anchor_key(line)` helper shared with `AddLineHandler`'s dedupe (03-R5). · S · guard: `test_shopping_list_lifecycle.py` move case + new product-only case · **execute**.
- **03-R4** · latent · `get_membership.py:76–79` buckets `per_item[line.stock_item_id]` — product-only lines land under key `None` and are serialised as `StockItemMembershipDto(stock_item_id=None)`; the client's `cartStateFor` never matches it but the DTO lies about its type. · **Exact change:** `if line.stock_item_id is None: continue`; also push `shopping_list_id in active_ids` into the query (`in_(active_ids)`) instead of loading every unticked line ever (done lists included). · S · guard: `test_quick_add_target_inference.py` · **execute**.
- **03-R5** · duplication-with-drift · `QuickAddToPrimaryHandler.handle` (`manage_shopping_list_lines.py:593–618`) re-implements `AddLineHandler`'s dedupe (without the `product_id is None` guard, so a nested product line counts as "already on list"), sequence and construction. · **Exact change:** delegate: `AddLineHandler(self.repository).handle(AddLineRequest(stock_item_id=…), target.id)`. · S · guard: `test_quick_add_target_inference.py` · **execute**.
- **03-R6** · R-032 latent · `frequently_added.py:51–60` loads `StockItem.all()` **without** `.include("stock_level")` and reads `item.stock_level` → `stock_level_id` is **always None**. Harmless only because `QuickAddSheet` reads nothing but `stock_item_id` from the payload (grep L167). · **Exact change:** fold into 03-R14 — the endpoint returns ranked ids from `_frequently_added.rank_frequently_added_ids`; drop `name/stock_level_id/add_count` from the DTO and `FrequentlyAddedItem`. · S · **execute**.
- **03-R7** · bug (template) · `QuickAddSheet.vue:22` `prepend-:icon="ICONS.search"` is not a Vue binding (the attribute is literally named `prepend-:icon`), so the search field has no icon. · **Exact change:** `<template #prepend><q-icon :name="ICONS.search" /></template>` (as `ShoppingListDetail.vue:829` does). · S · **execute**.
- **03-R8** · R-021/R-056 · `auto_generate.py:236` and `manage_templates.py:539` name new lists with `now.strftime('%a %d %b')` — server-local date, a second and third copy of `format_list_date`'s format. · **Exact change:** `format_list_date(household_today(self.repository))`; or (cleaner, UX-v2) leave `name=None` for the auto list and let it self-label — propose the latter for instantiate (`name = request.name or template.name`). · S · guard: `test_instantiate_shopping_list_template_unit_of_work.py` · **execute**.

#### C2. Redundancy / DRY (R-001, R-003)

- **03-R9** · `DeleteLineHandler` (L432–447) and `RemoveLineByStockItemHandler` (L495–509) carry the same 15-line nested-product-line cascade. · **Exact change:** `_remove_nested_product_lines(repository, list_id, stock_item_id)`; both call it. · S · guard: `test_shopping_list_product_lines.py`, `test_shopping_list_remove_by_stock_item.py` · **execute**.
- **03-R10** · `trim_to_budget._current_user_id` (L564) and `budget._current_user_id` (L314, which also uses the literal `"user_id"` instead of `SESSION_USER_ID_KEY` — R-019) — copies 16/17 of **FU-654** (02-R12). · **execute (FU-654)**.
- **03-R11** · `getattr(offer, "_product_id", None) or getattr(offer, "product_id", None)` ×2 (`trim_to_budget.py:205`, `budget.py:286`) and `getattr(e, "_recipe_id") or getattr(e, "recipe_id")` ×3 (`trim_to_budget.py:327, 342, 349`) — defensive dual reads of a column the mapping always installs as `_product_id` / `_recipe_id` (`auto_generate.py:370` reads it directly). · **Exact change:** direct attribute reads. · S · **execute**.
- **03-R12** · `auto_generate._collect_recipes` (L312–346) and `_collect_meal_plan_week` (L378–412) are the same 35-line ingredient→stock-item block, each issuing one `Recipe.by_id` **per recipe** plus one `StockItem.all(in_)` per recipe; `_collect_meal_plan_week` also loads **every** `MealPlan` with entries to filter 7 days in Python. · **Exact change:** `_collect_from_recipe_ids(candidates, recipe_ids, unlinked_skipped)` with one `Recipe.include(INGREDIENTS).all(in_(ids))` and one `StockItem` load; the plan week reads `MealPlanEntry` by `scheduled_for` range (as `trim_to_budget._load_meal_demand` does). · M · guard: `test_shopping_list_lifecycle.py` auto-generate cases (add a recipe + plan-week case if absent) · **execute**.
- **03-R13** · `auto_generate.py:47–50` `SEQ_STOCKED/LOW/OUT = 0/1/2` + `getattr(item.stock_level, "sequence", -1)` hard-codes level identity by sequence, while `domain.stock_status` exports `is_low_stock / is_out_of_stock / is_missing` and `trim_to_budget` already uses them (R-003/R-019). · **Exact change:** `is_low_stock(level)` / `is_out_of_stock(level)`; delete the constants. · S · **execute**.
- **03-R14** · `frequently_added.GetFrequentlyAddedHandler` runs its own GROUP BY (L41–46) that `_frequently_added.rank_frequently_added_ids` already owns (that module's docstring claims "both now come here" — the public endpoint never did). · **Exact change:** endpoint = `rank_frequently_added_ids(session, limit)` → `[{"stock_item_id": id}]`; see 03-R6. · S · guard: add a 5-line e2e case to `test_shopping_list_lifecycle.py` · **execute**.
- **03-R15** · `budget.GetBudgetHistoryHandler` (L409–431) re-implements the per-line sum that `period_spent` does (L145–153). · **Exact change:** `_spend_of(lines) -> float` used by both (history keeps its single fetch and buckets by period). · S · guard: `test_budget_router.py`, `test_budget_spend_excludes_unticked.py` · **execute**.
- **03-R16** · `get_shopping_list_detail._chosen` (L593–596) re-implements `_chosen_offer` (L226–233) inline. · **Exact change:** `_first_or_selected(offers)` helper used by both; delete the `_chosen_offer(line)` wrapper if unused after. · S · **execute**.
- **03-R17** · `GetTemplatesHandler` (manage_templates L92–95) loads every template line to count — same shape as 02-R30. · **Exact change:** `select(template_id, count()).group_by`. · S · **execute**.
- **03-R18** · `manage_shopping_list_attachments.py:39–41, 174–181` data-URL regex + base64 decode = the 5th site of **01-R7** (`infrastructure/data_url.py`). · **execute (01-R7)**.
- **03-R19** · `ShoppingListDetail.vue` three near-identical optimistic price/store writers — `savePriceEditor` (L2423), `saveStoreOnly` (L2511), `clearPriceOverride` (L2571) — each snapshot/restore the same three fields and toast. · **Exact change:** `writeLinePurchase(line, { price, storeId }, command, failMessage)` with one rollback path; the three become one-liners. · S · **execute** (inside FU-780's eventual split).
- **03-R20** · `useShoppingListActions.notifyOk/notifyErr` and the page's 30+ `$q.notify({type, position:'bottom-right', …})` blocks — **FU-624** (toast helper) owns this; no new finding. `useShoppingListActions.finishShopping` has **zero callers** (the page has its own `confirmFinish`) → **03-R24**.

#### C3. Dead code / unused fields / unread endpoints

- **03-R21** · `manage_shopping_list_lines.snapshot_offer_price` (L207–232) — no callers (grep: only tests `test_snapshot_offer_price.py` and a comment). Kept "because the columns hold history" — deleting a *writer* doesn't delete data, and the column comments already carry the history. · **Exact change:** delete the function + `test_snapshot_offer_price.py`; move its rationale paragraph onto `ShoppingListLine.picked_offer_price`'s comment (which currently still says the snapshot is taken at add/select time — stale since 2026-09-17, 03-R28). · S · **execute**.
- **03-R22** · **FU-766**: `has_substitutes` + its raw `StockItemSubstitute` SQL block (`get_shopping_list_detail.py:446–467`, with `from dora_api.app import db` and `from sqlalchemy import …` *inside* the handler — R-008) and `POST …/lines/bulk-tick` (`bulk_operations.py:44–92`) have no client reader/caller. · **Exact change:** delete both + `test_line_has_substitutes.py` + the bulk-tick cases; drop `has_substitutes` from `models/shoppingList.ts:163`. · S · **execute (FU-766)** — owner directive needed only if INV-8's swap is revived; the FU says "owner's call", recommend delete.
- **03-R23** · `POST …/lines/move-to/<target>` (`list_actions.py:162–182`) and `moveLinesToAsync` (`shoppingListApiService.ts:339`) — the bulk-select bar that called it is gone (page comment L199–204); grep → no caller. · **Exact change:** delete client method; delete server route + `MoveLinesRequest` (keep the `line_ids` parameter on the handler — it's one filter and tested) and the move-to e2e case. · S · **execute**.
- **03-R24** · `useShoppingListActions.finishShopping` (L158–172) — zero callers. · **Exact change:** delete. · S · **execute**.
- **03-R25** · `models/shoppingList.ts`: `savingsOfLine` (L336), `isListDone`, `isListShopping` (L10–16) — zero callers (`savingsOfLine` also re-implements a ladder the server owns, so it's an R-003 trap waiting). · **Exact change:** delete all three. · S · guard: `shoppingList.spec.ts` (drop their cases) · **execute**.
- **03-R26** · Detail DTO fields with **no SPA reader**: `prefill_unit_price` (the price sheet seeds from `estimated_unit_price`; `prefill_source_label` *is* read by `ShoppingListReceiptRow`), `last_paid_unit_price` (only `last_paid_store_*` are read), `stock_level_name`, `stock_location_id`, `added_at`. · **Exact change:** drop `prefill_unit_price`, `last_paid_unit_price`, `stock_level_name`, `stock_location_id`, `added_at` from `ShoppingListLineDto` + the TS type; keep `prefill_source_label` and the breadcrumb. · S · guard: `test_shopping_list_lifecycle.py` (field assertions) · **execute (conditional on grep at execution — PutAwayDialog reads `stock_location_id`? It reads from `lines` prop — check)**.
- **03-R27** · `FinishShoppingListRequest` (empty model) + `@has_request_body` + `get_request_body() or FinishShoppingListRequest()` and `FinishShoppingListCommand = Record<string, never>` — vestiges of the cut per-item level picker (FU-582). · **Exact change:** drop the request class/decorator/command type; `finishAsync(id)` posts `{}`. · S · **execute**.
- **03-R28** · stale comments/docstrings describing retired behaviour: `shopping_list.py:16–17` ("matching the ADDED_VIA_* convention above" — deleted 2026-09-19), `:70–79` (`picked_offer_price` "captured at commit-to-offer" — not written since 2026-09-17), `_line_price.py:30` ("snapshot taken at commit-to-offer time"), `budget.py:15–17, 123–125` (two contradictory accounts of when `picked_offer_price` is written), `get_shopping_list_detail.py:5–6` ("Totals are computed client-side" — server-owned since state-ownership chunk), `models/shoppingList.ts:168–174` (ladder order "actual → last paid → offer" vs server "actual → picked offer → historic"), `budgetApiService.ts:4–6` ("settings live on the User row" — moved to AppSetting), `useLineSections.ts:155` ("`manual` is always in"), `ShoppingListPlanRow.vue:405` + `ShoppingListReceiptRow.vue:82` (`shoppingRow.scss` → file is `shoppingList.scss`). · **Exact change:** reword each to the current contract (one sweep). · S · **execute**.
- **03-R29** · `ShoppingListReceiptFace` prop `completedLabel` + the page's `completedLabel` computed (L1806) — the face no longer renders a header (its own comment L29–34), so the prop is dead. · **Exact change:** delete prop + computed + `formatDate` if then unused on the page. · S · **execute**.
- **03-R30** · `useQuickAdd.QuickAddOptions.stockItemId` doc says "skips straight to the offer/list step" — the step is gone; the preset now adds and closes. Doc fix only (fold into 03-R28).

#### C4. Componentisation opportunities (R-001)

- **03-R31** · `ShoppingListDetail.vue` is 3,279 lines (**FU-780**). The natural seams are already visible in the script: trim-to-budget (L1629–1781), price capture (L2296–2622), finish & leftovers (L1316–1481), lists rail/picker (L1866–1988), receipts (L2949–3019). · **Exact change (FU-780 plan):** `useTrimToBudget(listId, detail, baseLines)`, `useLinePriceCapture(listId, detail)`, `useFinishShopping(...)`, `ShoppingListsPicker.vue` (rail + mobile dropdown + "See older"), `ShoppingListReceipts.vue`; page keeps routing/loading/face switch. · L · guard: vue-tsc + drive all three faces once · **FU-780** (keep as the tracker; sequence after the small items above).
- **03-R32** · `plannedStoreOptionsFor` / `storeOptionsFor` / price-sheet store select (page L2364–2421) are three shapes of "store options for a line" — the first two differ by design (all stores vs. stores touching the line); the third is `allStoreOptions`. · **waive** (documented, intentional).
- **03-R33** · `NewListDialog.bulkAddToList` (L303–319) loops `addLineAsync` per id, and the merge-a-template path instantiates a temp list, reads it, loops, deletes it (L369–381). · **Exact change:** use `bulkAddLinesAsync` (one round-trip; FU-714's shape) and add `merge_into_list_id` to `InstantiateTemplateRequest` so a template can top up a list server-side (one handler path, no temp list). · M · guard: `test_instantiate_shopping_list_template_unit_of_work.py` new case · **execute** (FU-714 partial; the rest of FU-714's 16 call sites stay with that FU).
- **03-R34** · `BulkAddLinesHandler` / `BulkRemoveByStockItemHandler` call the single-line handlers per item, each of which `save_changes()` — N commits per bulk request (**FU-713**). · **Exact change:** `commit: bool = True` on the inner handlers (or a `_add_line(...)` core they share); bulk saves once. · S · guard: `test_shopping_list_lifecycle.py` bulk cases · **execute (FU-713)**.

#### C5. Placement / layering (R-003, R-005, R-008)

- **03-R35** · `get_shopping_list_detail.GetShoppingListDetailHandler.handle` is a 340-line method. · **Exact change:** `_load_context(list_id, lines) -> _DetailContext` (items, prior purchases, stores, preferred buys) + `_line_dto(line, ctx)`; `handle` becomes ~30 lines. · M · guard: `test_shopping_list_totals.py`, `test_shopping_list_store_breakdown.py`, `test_shopping_list_lifecycle.py` · **execute** (do together with 03-R22, which removes the raw-SQL block).
- **03-R36** · `_inferred_suggestions` loads **every** stock item with its level on every detail read **before** `resolve_divergence` checks the surface flag (L768–772; the gate is inside `resolve_divergence`). · **Exact change:** check `surface_enabled(current_user(repo), SURFACE_SHOPPING)` first; load candidates only when on. · S · **execute**.
- **03-R37** · `shopping_list_attachment_access.py` uses raw `db.metadata.tables["ShoppingListAttachment"]` Core statements although `ShoppingListAttachment` is a mapped entity (`table_mappings.py:1816`) — R-005 (repository-routed access) and the only module in the feature importing `db` directly besides the 03-R22 block. · **Exact change:** `repository.get(ShoppingListAttachment).all(EntityField(...).eq(list_id))` etc.; bytes endpoint reads `.image`. · S · guard: `test_shopping_list_attachments.py` · **execute**.
- **03-R38** · `trim_to_budget.py` imports the private `_gather_inputs` from `get_buy_verdict` and runs it lazily **per item** (`_verdict_inputs_for`), while `get_list_buy_verdicts` uses the public bulk `gather_verdict_inputs_for_items` (fixed query count). · **Exact change:** gather once for all candidate items up front with the bulk helper; drop `_Ctx.repository` + the `assert`. · S · guard: `test_trim_to_budget.py` · **execute**.
- **03-R39** · `trim_to_budget.handle(..., user_id)` loads a `User` row only to return `None` if missing — the route already 401s; `user_id` is otherwise unused. · **Exact change:** drop the parameter and the `User` import. · S · **execute**.
- **03-R40** · `trim_to_budget.py:606` returns a raw `{"error": …}, 400` tuple instead of `api_response.bad_request`; `mode` should be `Literal["preview","apply"]` on the pydantic model (the comment's "clearer error" claim is moot — `has_request_body` already formats validation errors). · S · **execute**.
- **03-R41** · local imports inside handlers that have no cycle to break: `manage_shopping_list.py:76, 242, 275`, `bulk_operations.py:130, 191`, `_line_retention.py:103–104`, `budget.py:437` (duplicate `from flask import request`). R-008. · **Exact change:** hoist. · S · **execute**.
- **03-R42** · `bulk_operations.py:118–122, 237–243` `failed_ids: List[UUID] = None  # type: ignore` + `__post_init__` → `field(default_factory=list)`. · S · **execute**.
- **03-R43** · `manage_shopping_list_attachments.py:151, 171` `UUID(str(shopping_list_id))` on `<uuid:>` path params; bytes route params untyped. · S · **execute**.
- **03-R44** · `compute_list_totals` local names `_Buckets/_Key/_Bucket/_Colours/_ByStore` inside a pure function (the `_Name` style is the codebase's route-local convention). · S · **waive** (style only; tidy if the function is touched).

#### C6. Naming & idiom
- **03-R45** · `QuickAddToPrimaryHandler` / `quickAddToPrimaryAsync` — "primary" was retired in P6-01 chunk 2; the handler's own docstring says so. · **Exact change:** `QuickAddToDraftHandler` / `quickAddAsync`. · S · **execute**.
- **03-R46** · `AddLineRequest.quantity ge=1` vs template `ge=0` (templates allow "–" = unspecified). Intentional per `onTemplateQtyBlur`; · **waive**.

#### C7. Efficiency
- 03-R4, 03-R12, 03-R17, 03-R34, 03-R36, 03-R38 above.
- **03-R47** · `get_shopping_list_detail` loads **all** `StockLocation` rows when any item has a location (L487–490) — bounded and shared with the breadcrumb helper; · **waive**.
- **03-R48** · `_PriorPurchaseByItem` loads every ticked line ever for the list's items, then their lists, to find the latest done purchase (L522–553). Correct; grows with history. A `MAX(completed_at)` join would be the fix but the repository port has no join — · **FU** (bundle with FU-725's historic-rung e2e coverage: pin the behaviour first, then optimise).

#### C8. Design-level findings — out of Stage-2 scope
- **03-D1** · Templates are stock-item-anchored only; product-only lines are silently dropped by snapshot (after 03-R2) and can't be templated. Owner call: is that fine, or should `ShoppingListTemplateLine` gain a nullable `product_id`?
- **03-D2** · `MoveLinesHandler` never merges quantities on a duplicate (comment L123–125 "separate UX decision") — the finish dialog says "Anything already on that list is skipped", so the behaviour is at least honest. Record for the owner.
- **03-D3** · Quick-add target memory is per-tab `sessionStorage` while lists are household-shared — fine for now; note for `MULTI_USER_READINESS.md`.
- **03-D4** · `shopping_lists` has three list-creation paths that name lists three ways (create: NULL/self-label; auto-generate: "Auto N · date"; instantiate: "Template · date"; copy: "Copy of …"). After 03-R8 the remaining question is whether *any* server path should invent a name now that lists self-label (UX-v2). Recommend: none do — owner confirm.

#### C9. Hand-rolled-vs-library verdicts
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| `useDragDropList` whole-row DnD (R-022) | pointer drag-reorder | `vuedraggable` / SortableJS | **keep** | — | Already the app-wide shared affordance (ADR-018); touch uses arrows by design. |
| `useLineSections` bucketing | grouping + ordering | lodash `groupBy` | **keep** | — | Pure, spec'd, carries domain rules (Unsorted bucket, availability). |
| `trim_to_budget` tier classifier | rules engine | — | **keep** | — | Five explicit tiers with constants; a rules library would obscure it. |
| `attachment_access` raw Core | ORM bypass | the mapped entity | **replace** (03-R37) | S | Same engine; just use the repository. |
| `budget.period_bounds` | week/month windows | `dateutil.relativedelta` | **keep** | — | Two branches; R-021 handled at the caller. |
| `QuickAddSheet` / `LogPriceSheet` search + rank | client filter | fuse.js | **keep** | — | `includes()` over ≤ a few hundred names; ranking is the point, not fuzziness. |
| `useListState` module cache | nav-state persistence | pinia + `sessionStorage` | **keep** | — | Deliberately reset-on-reload (A8 §3). |

#### C10. Standards drift (R-0NN)
- **R-005** · 03-R22 (raw `db` in a feature handler), 03-R37 (Core on a mapped table) — fix.
- **R-008** · 03-R11, 03-R41, 03-R42, 03-R43 — fix.
- **R-019 / R-003** · 03-R13 (level sequence literals), 03-R10 (`"user_id"` literal) — fix.
- **R-021 / R-056** · 03-R8 — fix.
- **R-032** · 03-R6 — fix.
- **R-039** · every `$q.dialog` on this surface carries `noCaps` (page L1954, 2739–2740, 2815, 2844, 2885, 2902–2903; templates L380, 433; `AddToListButton` L397–398, 592–593) — **clean**.
- **R-045** · `useShoppingListExport.openPrintView` uses `window.open(baseUrl…)` — the third of **FU-682**'s three (same as 02-R36). · **execute (FU-682)**; add `useShoppingListExport.spec.ts` mirroring the recipe one.
- **D-010** · `ShoppingListOverviewCard.vue:649` `width 320ms ease-out`, `ShoppingListTemplates.vue:671` `120ms ease` ×2 → `var(--motion-*)` tokens (the plan row already uses them). · S · **execute**.
- **R-002 carve-outs** present and explained: progress track `hsla(0,0%,100%,.55)` (card L634–642), receipt thumb `rgba(0,0,0,0.15)` fallback (`ShoppingListDetail.vue:3243` — has a token first; fine).
- **D-003/D-004** · receipt row amend stepper uses `size="sm"` icon buttons (44px only under `pointer: coarse` via BaseButton) — OK by the shared rule.
- **FU-624 / FU-675** · raw `$q.notify` ×30+, raw `q-select` ×6 (`AddToListDialog.vue:17`, `NewListDialog.vue:28/40/52/114`, `ShoppingListTemplates.vue:194`) — tracked.
- **Owner directive 2026-08-27 (help modals)** · no `(?)` modals on this surface — clean; help chips to add per §B2.

#### C11. Ride-along signals for FU-010 / FU-224 (theme / colour)
- `AddToListButton.iconColour` uses `'accent'` for on_other and `'severity-attention'` for on_multiple — the accent-as-state usage FU-224 is auditing.
- `ShoppingListRailItem.active-class="dora-bg-info-soft"` vs the overview pill's `--semantic-info` — two info tints in one surface.
- Gradient band (`--hero-gradient`) on plan/run faces + the white-veil progress track — check pesto dark and high-contrast.
- `.sl-rail-item-done { opacity: .6 }`, `.sl-row--ticked * { opacity: .6 }`, `.sl-store-chip--none { opacity: .75 }` — opacity dimming over muted ink (D-002 floor) as in 02-C11.

### E. Proposed follow-ups (orchestrator allocates ids)

- type=finding · *`POST /shopping-lists/<id>/copy` has no client caller and 500s on product-only lines* (03-R1) — recommended: delete endpoint + unit-of-work test this run; FU only if the owner wants it kept.
- type=follow-up · *Historic-rung lookup loads every ticked line for the list's items* (03-R48) — bundle with **FU-725** (pin first, then optimise); no new entry if FU-725 absorbs it.
- type=finding · *Templates can't carry product-only lines* (03-D1) — owner decision.
- type=finding · *Three server paths still invent list names; lists self-label since UX-v2* (03-D4) — owner confirm "none do".
- type=finding · *Move never merges duplicate quantities* (03-D2) — record only.
- Existing FUs this chunk executes against (tick, don't duplicate): **FU-766** (bulk-tick + has_substitutes), **FU-713** (bulk commits), **FU-714** (partial — NewListDialog), **FU-654** (two more `_current_user_id`), **FU-682** (print view), **FU-780** (page split — plan recorded in 03-R31, execution stays with the FU).

---

## Chunk 04 — Cook Mode
*Source: [`CHUNK_04_cook_mode.md`](../05_investigations/finalisation/CHUNK_04_cook_mode.md) · analysed 2026-10-23*

### C. Senior review — Cook Mode

#### C1. Bugs (verified or high-confidence latent)

- **04-R1** · **FU-765** (reproduced live twice) · `RecipeCookMode.vue:1766–1798` fetches in `onMounted` only; no watch on `route.params.id`. · **Exact change:** `async function loadRecipe(id)` (fetch + reset `currentStepIndex`, timer, `sessionSwaps`, `announcedFirstStep`); `watch(() => route.params.id, (id) => void loadRecipe(String(id)), { immediate: true })`; `onMounted` keeps the store warm-ups. · S · guard: drive A→B once · **execute (FU-765)**.
- **04-R2** · **FU-853**, re-diagnosed · the CSP (`middleware.py:164–172`) has no `media-src`, so `default-src 'self'` governs media. The timer chime is **already** a WebAudio oscillator (`playTimerFinishTone`, L1403) and is not affected — the FU's "data: WAV chime" description is stale. What *is* blocked is `audioUnlock.ts:21` `SILENT_WAV_DATA_URL` played via `new Audio(data:…)` — the iOS/WKWebView autoplay primer that `useSpeechOutput` and `VoicePicker.onPreview` rely on — hence the violation logged on every load. Piper's `blob:` playback is same-origin and passes `'self'`. · **Exact change:** add `"media-src 'self' blob: data:"` to `_DEFAULT_CSP` with a comment naming the primer; update FU-853's text. · S · guard: `tests/e2e/dora_api/test_security_headers*.py` if present (assert the directive) · **execute (FU-853)**.
- **04-R3** · R-003 layering · `exitCookMode` (L1597) and `onBeforeUnmount` (L1804) call `window.speechSynthesis?.cancel()` directly, bypassing `useSpeechOutput.cancel()` — the composable's own `onBeforeUnmount(cancel)` covers unmount, so Piper audio *does* stop, but `exitCookMode` → `router.push` leaves the Piper `<audio>` playing for the ~frame until unmount and the page holds a second opinion about how to silence Dora. · **Exact change:** `speechOut.cancel()` in both places; drop the raw calls. · S · **execute**.
- **04-R7** · bug · `handleKeydown` is a raw `window` listener (the only page in the app not on `useShortcut`); space/arrows fire while the finish dialog or swap picker is open (stepping the recipe underneath, re-opening Finish), and the keys don't appear in the `?` cheatsheet. · **Exact change:** register via `useShortcut([...], { scope: 'Cook mode' })` (space / arrowright → next, arrowleft → prev, r → repeat, escape → exit) and guard the handlers on `!finishDialogOpen.value && !swapPickerOpen.value`. · S · guard: drive once · **execute**.
- **04-R8** · bug · the countdown decrements by one per `setInterval` tick (L1363–1382); backgrounded tabs throttle intervals (Chrome: ≥ 1 s, then 1/min after 5 min; iOS suspends) so a 20-minute timer runs **slow** when the cook switches apps — the exact case a kitchen timer exists for. · **Exact change:** store `deadlineMs = Date.now() + remaining*1000` on start; each tick sets `remaining = max(0, ceil((deadline - now)/1000))`; re-sync on `visibilitychange`. Extract as `useCookTimer()` (04-R20 seam) so it is unit-testable with fake timers. · S · guard: new `useCookTimer.spec.ts` · **execute**.
- **04-R9** · note · `sniffedTimerMinutes` matches minutes before hours, so "1 hour 30 minutes" → 30. · **waive** (fallback only; declared timers are the mechanism).
- **04-R5** · UX bug · `confirmFinish` uses `Promise.allSettled` for level writes and never reports rejections — a failed level update is silently lost under a "You saved N meals" toast. · **Exact change:** count `rejected`; if > 0 toast `Could not update N level(s).` (negative) before the celebration. · S · **execute**.

#### C2. Redundancy / DRY (R-001, R-003)

- **04-R10** · `cook_recipe.py:21–28` `_current_user_id` with the literal `"user_id"` — **FU-654** copy. · **execute (FU-654)**.
- **04-R11** · `levelNameFor` (page L1502) + `levelSequence`/`levelLabel` in `QuickAddSheet.vue:121–126` and `LogPriceSheet.vue:146–151` — three private "stock level id → name / sequence" lookups over `stockLevels.find`. · **Exact change:** `stockLevelStore` gains `byId` (Map), `nameOf(id)`, `sequenceOf(id)`; the three call sites use them. · S · guard: `shoppingListStore.spec`-style store spec (optional) · **execute**.
- **04-R12** · `stockItems.value.find(...)` per ingredient in `ingredientRows` (L1118) and again in `buildFinishRows` (L1521) — linear scans per render; the store has no `byId`. · **Exact change:** `stockItemStore.byId` computed Map; both read it (Chunk 1's `cookModeGuard.missingStockItemIds` benefits too). · S · **execute**.
- **04-R13** · the Previous/Next pair is built three times: page nav (L307–336, with Repeat, `navButtonSize`), `RecipeCookModeImageView` nav (L59–75, fixed `size="lg"` — so the photo face **didn't get the 09-03 phone fit**) and its zoom-dialog nav (L121–136). · **Exact change:** `components/recipes/CookNavRow.vue` (props `canPrev`, `isLast`, `showRepeat`, `repeatDisabled`, `size`; emits prev/repeat/next); three call sites. · S · **execute**.
- **04-R14** · `pool.bump_pool` UUID bind normalisation (L69–78) — the third copy folded by **01-R8** (`uuid_bind`). · **execute (01-R8)**.
- **04-R15** · `cook_recipe.py` and `adjust_recipe_meals.py` share the load-recipe → `bump_pool` → save shape; two small handlers, one shared primitive already — · **waive** (already DRY where it matters).

#### C3. Dead code / unused fields / stale copy

- **04-R16** · `useSpeechOutput.lastEngine` — exported, zero readers since the 09-03 popover removal (the page comment L138–143 says "still carries it for whoever needs it next"). FU-722 (unconfirmed clipping) is the one investigation that might want it. · **Exact change:** keep until FU-722 is closed; add `// FU-722 diagnostic` to the export. · **waive (documented)**.
- **04-R17** · page epitaph comments: L930 ("the headcount nudge + its clamp live in NumberStepper now"), L1109–1111 (`hasStructuredSteps` removed), L1318–1321 (`markIngredientsUsedInStep` removed), L1766–1768 (`speechRecognitionAvailable` seeding) — history the worklog holds. · **Exact change:** delete. · S · **execute** (with 04-R20's extraction, since the lines move anyway).
- **04-R18** · HelpPage *Cook mode* entry and `app_knowledge` cook sentences stale (§B1). · **execute (Help track)**.
- **04-R19** · `cook_recipe.py:94–97` returns `204` for `meals_cooked == 0` and `200 {available_meals}` otherwise — two shapes for one endpoint; the client ignores the body (`recipeStore.cookAsync` refetches). · **Exact change:** always `ok({"available_meals": …})`. · S · guard: `test_recipe_router.py` cook case if it asserts 204 · **execute (conditional)**.

#### C4. Componentisation opportunities (R-001)

- **04-R20** · `RecipeCookMode.vue` is 2,042 lines with five clean seams already labelled in the script: `useCookSteps(recipe)` (flattener + highlights, L1010–1226), `useCookTimer()` (L978–1426, incl. the tone), `useCookVoice(...)` (Sous Chef toggle + dispatcher, L933–1008 / L1619–1745), `CookIngredientsPanel.vue` (L352–489 + swap picker + `sessionSwaps`), `CookFinishDialog.vue` (L695–777 + `buildFinishRows`/`confirmFinish`). The page keeps route/load/header. · L · guard: vue-tsc + drive all three faces + the finish once; new specs for the flattener, the timer and the dispatcher (§D) · **FU** (same shape as FU-780; execute 04-R8 and 04-R7 as the first two extractions so the rest follows the pattern).
- **04-R21** · `playTimerFinishTone` (WebAudio beep) — only chime in the app; · **waive** (move to `utils/chime.ts` only if a second surface wants one).

#### C5. Placement / standards (R-002, D-rules)

- **04-R22** · `text-color="white"` on the Sub-step chip (L222) and the swap chip (L409) → `--text-on-primary` / `--text-on-secondary` (FU-674 governs contrast). · S · **execute**.
- **04-R23** · literal type sizes: `CookStepProgress.vue:133 (0.6875rem), :140 (1.5rem), :147 (0.875rem), :248 (1.25rem)`, page `.cook-section__head { font-size: 1rem }` (L1829), `.all-steps-row--sub { padding-left: 32px }` (L1934) → `--font-size-*` / `--space-*` tokens (D-003 scale). · S · **execute**.
- **04-R24** · two focus-ring tokens in one surface: `CookNotesSection.vue:85` `--ring-focus` (a soft 35 % wash — defined in `themes.scss`) vs `CookStepProgress.vue:220` `--focus-ring` (full brand ink, `tokens.scss:153`). App-wide: 8 files use `--ring-focus`, the rest `--focus-ring`. Not a cook-mode bug but cook mode is where both meet. · **Exact change:** log a **FU** for FU-010/FU-224: pick one focus token (recommend `--focus-ring` for the outline, `--ring-focus` only for soft halos) and sweep. · **FU**.
- **04-R25** · `ease` literal after a motion token (`CookStepProgress.vue:187–189, 238`, page L1870) → `var(--motion-ease)` (D-010). · S · **execute** (with 02-R38's sweep).
- **04-R26** · `useVoiceInput.ts:2` imports `currentMoneyPolicy` from `useMoney` to read the install locale — a voice composable depending on the *money* composable because the locale rides on the money policy. Works, but the dependency direction is odd (R-003 says the locale is one install fact). · **Exact change:** export `currentLocale()` from a `useLocale`/`useRegional` seam (FU-043 Layer B owns this); `useMoney` and `useVoiceInput` both read it. · S · **execute** (if FU-043's regional seam exists at execution; else FU).
- **04-R27** · `pool.py:35` `from dora_api.app import db` + raw `text()` — documented R-005 carve-out (portable `UPDATE … RETURNING`, needed by the connection-level sweep). Keep; comment already names the rule. · **waive**.

#### C6. Naming & idiom
- **04-R28** · `RecipeCookModeImageView` vs `CookStepProgress` / `CookNotesSection` — two naming schemes in one folder for cook-mode parts. · **Exact change:** rename to `CookImageView.vue` when 04-R13 touches it. · S · **execute**.

#### C7. Efficiency
- 04-R12 above. `highlightedIngredientIds` text-match is per step change over ≤ 30 ingredients — fine.

#### C8. Design-level findings — out of Stage-2 scope
- **04-D1** · **FU-728 (cook-mode half) answered:** cook mode is already its own composition — the "planning" phase is the recipe page, and the step/photo faces are modes *within* cooking, not lifecycle phases. No second composition is warranted; the R-001 extraction (04-R20) is size hygiene, not R-054. Record and close the cook-mode half of FU-728 (the stocktake half → Chunk 5).
- **04-D2** · Timers are per-step and reset on navigation (`nextStep`/`prevStep`/`goToStep` all `resetTimer()`). A 40-minute braise timer dies the moment the cook reads ahead. Owner decision: timers persist across steps (a small "running timers" strip) vs. the current single-step model. **FU**.
- **04-D3** · FU-763 (step text size on a phone) — owner's call, unchanged.
- **04-D4** · FU-670: expiring-ingredient chips absent in cook mode — the owner said stock noise doesn't belong mid-cook; the at-risk chip is arguably the one exception ("use this one first"). Leave with FU-670.

#### C9. Hand-rolled-vs-library verdicts
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| `useVoiceInput` Web Speech wrapper | STT | `vue-use-speech-recognition` / `@vueuse/core useSpeechRecognition` | **keep** | — | VueUse lacks the defer-restart (FU-723) and continuous-restart handling; ours is 270 lines with the fixes. |
| `useSpeechOutput` two-engine TTS | TTS | `@vueuse/core useSpeechSynthesis` | **keep** | — | Piper path + fallback + supersede token is the product. |
| `useWakeLock` | Screen Wake Lock | `@vueuse/core useWakeLock` | **replace-candidate** | S | VueUse's version does the same (request/release/visibility re-acquire). Only two callers; swap if `@vueuse/core` is already a dependency, else keep (not worth a dep for 100 lines). |
| timer `setInterval` countdown | timer | `@vueuse/core useIntervalFn` + `useTimestamp` | **keep (rewrite per 04-R8)** | — | Deadline arithmetic is the fix, not a library. |
| `playTimerFinishTone` oscillator | chime | a bundled WAV | **keep** | — | WebAudio sidesteps the `media-src` and autoplay issues a file would reintroduce. |
| `cookSteps` flattener | tree → list | — | **keep** | — | Pure; needs a spec (§D). |

#### C10. Standards drift (R-0NN)
- **R-003** · 04-R3 (bypassing the speech composable), 04-R26 (locale via money) — fix.
- **R-001** · 04-R13, 04-R20 — fix / FU.
- **R-002 / D-003 / D-010** · 04-R22, 04-R23, 04-R25 — fix.
- **R-019** · 04-R10 — fix (FU-654).
- **R-039** · no `$q.dialog` on this surface (all `BaseDialog`) — clean.
- **D-004** · voice cluster 44px, nav buttons 44px, progress segments 44px hit area, notes head 44px on coarse pointers — clean.
- **Keyboard layer** · 04-R7 — the page is the one surface outside `useShortcut`.
- **FU-764** (undefined tokens) · `--surface-card` fixed in place (L1846); `--space-sm/xs` fixed; `--ring-focus` exists — no new undefined tokens found.

#### C11. Ride-along signals for FU-010 / FU-224
- Two focus-ring tokens (04-R24) — app-wide inconsistency surfaced here.
- `CookStepProgress` badge/segments lean entirely on `color-mix(--brand-primary …)` washes (12 % / 20 % / 35 % / 45 % / 65 %) — check pesto dark + high-contrast.
- `.cook-row--dim { opacity: .55 }`, `.ingredient-row--optional { opacity: .65 }` — opacity dimming (D-002 floor), same class as 02/03.
- Swap chip `color="secondary"` + white ink — FU-621/FU-652 secondary shortlist.

### E. Proposed follow-ups (orchestrator allocates ids)

- type=follow-up · *Split `RecipeCookMode.vue` into `useCookSteps` / `useCookTimer` / `useCookVoice` + `CookIngredientsPanel` / `CookFinishDialog`* (04-R20) — plan recorded; bundle with FU-780 / 01-R36 / 02-D4 as the "big page splits" group.
- type=finding · *Timers reset on step change* (04-D2) — owner decision.
- type=finding · *Two focus-ring tokens (`--ring-focus` vs `--focus-ring`) across 8 + N files* (04-R24) — attach to FU-010/FU-224.
- type=finding · *FU-728 cook-mode half: no second composition needed* (04-D1) — record in FU-728 and narrow it to stocktake.
- Existing FUs this chunk executes against: **FU-765** (04-R1), **FU-853** (04-R2, re-diagnosed), **FU-654** (04-R10), **FU-754 / FU-793** (seed fixtures — needed for A1; execute as part of Stage 2 if the seed is touched).

---

## Chunk 05 — Stock Overview + Stocktake
*Source: [`CHUNK_05_stock_overview_stocktake.md`](../05_investigations/finalisation/CHUNK_05_stock_overview_stocktake.md) · analysed 2026-10-23*

### C. Senior review — Stock Overview + Stocktake

#### C1. Bugs (verified or high-confidence latent)

- **05-R5** · bug (high-confidence) · `StocktakeRunner.vue` writes levels, mutes and deletes through the raw API (`stockApi.updateAsync` L594/615/694/790, `stockApi.deleteAsync` L823), never through `stockItemStore`. The store is already hydrated from `/stock`, `ensureLoadedAsync` is a no-op once `hydrated`, and nothing invalidates it — so **after a stocktake, `/stock` shows the pre-stocktake levels (and deleted items) until a hard reload**. It also skips the store's recipe-fact invalidation and the auto-add toast (a level set to Low in the runner can fire `_try_auto_add` server-side and the user is never told). · **Exact change:** route level writes through `stockItemStore.updateStockLevelAsync`, mute through `updateStockItemAsync`, delete through `deleteStockItemAsync`. · S · guard: drive once (stocktake → /stock) · **execute**.
- **05-R3** · bug (R-003/FU-050) · `StocktakeRunner.vue:499` `stockLevels.find(l => l.name === c.stock_level_name)` colours the Change-level button by **name**; `SessionItemDto.stock_level_id` is right there. · **Exact change:** `find(l => l.stock_level_id === c.stock_level_id)` (or 04-R11's `stockLevelStore.sequenceOf`). · S · **execute**.
- **05-R7** · dead + rule-bypassing endpoint · `POST /shopping-lists/<id>/review/complete` (`stocktake.py:583–651`) writes `stock_level_id` with a raw `UPDATE` — no `StockLevelChange`, no `ConsumptionEvent`, no auto-add, no `last_checked_at` rule — exactly the bypass `bulk_operations.py`'s docstring refuses; and `stocktakeApiService.reviewCompleteAsync` has **zero callers** (the shopping-list "review mode" was retired in UX-v2). · **Exact change:** delete the route, `ReviewCompleteRequest`, `_stocked_level_id`, the `SHOPPING_LIST_ROUTER` import, `reviewCompleteAsync`, and its e2e cases in `test_stocktake_router.py` / fuzz list. · S · **execute**.
- **05-R30** · comment/behaviour mismatch · `create_stock_item.py:55` says the name check is case-insensitive; both create (L98–103) and update (L207–215) use `eq`, which is case-sensitive on SQLite and Postgres, so "Milk" and "milk" both exist while groups normalise (`manage_stock_groups.py:105`). · **Exact change:** `func.lower(name) == request.name.lower()` via a repository `ieq`/`EntityField.ilike` (check the port), or normalise as groups do; share one `_name_taken(repository, name, exclude_id)` between create and update. · S · guard: `test_stock_item_router.py` new case · **execute** (FU-575 keeps the concurrent-race half).
- **05-R2** · R-003/R-021 · the "+N days from max(today, current expiry)" rule (FU-123) lives in the client (`useStockItemActions.pushExpiry:179–202`) with a browser-local `today`, while every other date stamp (`opened_on`) is household-day server-side. The row menu, the detail page and the bell's "push expiry" all route here. · **Exact change:** `POST /stock-items/<id>/push-expiry {days}` → `{expiry_date}` using `household_today`; client calls it. Keep `useStockItemActionsPushExpiry.spec.ts` as the server unit test's twin or retire it. · M · guard: new pytest unit + e2e · **execute**.
- **05-R11** · duplicate API for one table · the flat `/api/stock-locations` CRUD (`stock_locations/*`, name-only, can't set `kind`/`parent_id`) coexists with the tree `/api/locations` CRUD (`locations/*`). SPA callers of the flat one: `stockLocationStore` ← `StockItemRow.vue:343, 458, 461, 487` (a name fallback that is **dead**: `getStockLocationsAsync` is never called on the overview, so `stockLocations` is always `[]`) and `WelcomeWizard.vue:1405–1544` (onboarding creates zones by name). · **Exact change:** onboarding → `locationStore.createAsync({ name, kind: 'zone' })`; delete `stockLocationStore`, `stockLocationApiService`, the flat router (4 files) and `test_stock_location_router.py` + its fuzz/DTO-contract rows; `StockItemRow` drops the import and fallback. · M · guard: `test_location_router.py`, onboarding e2e (Chunk 14) · **execute** (Chunk 14 ticks the wizard).

#### C2. Redundancy / DRY (R-001, R-003)

- **05-R10** · `stocktake.get_stocktake_queue` (L432–470) and `session.get_stocktake_session` (L138–181) repeat: load items with level+location, `resolve_overdue_map`, gate beliefs on `SURFACE_STOCK`, `gather_beliefs_for_items`, `rank_queue`, `band_by_item`/`days_by_item`. · **Exact change:** `stocktake._ranked_overdue(repo, user, now) -> RankedOverdue(ranked, band_by_item, days_by_item, belief_ranked)`; both endpoints consume it. · S · guard: `test_stocktake_router.py` · **execute**.
- **05-R9** · the SQLite-naive → aware-UTC coercion appears inline at `stocktake.py:242–243, 393–395`, as `sweep._aware`, and again in `reconcile.py` (Chunk 2). · **Exact change:** `persistence/aware.py::as_utc(dt)`; four call sites. · S · **execute**.
- **05-R6** · "the most-stocked level is `stockLevels[0]`" in `StockOverview.bulkRestock:1108` and `useStockItemActions.markRestocked:156`; `findLevelBySequence(levels, STOCKED_SEQUENCE)` exists in `helpers/stockStatus.ts`. · **Exact change:** `stockLevelStore.stockedLevel` computed (via `findLevelBySequence`); both read it. · S · **execute**.
- **05-R13** · stock groups fetched ad hoc in `StockOverview.loadStockGroups`, `CreateStockItemDialog.loadStockGroupsAsync` and the detail page ("there's no store for them"). · **Exact change:** `stores/stockGroupStore.ts` (R-016 lazy, same shape as `stockLevelStore`); three callers. · S · **execute**.
- **05-R25** · the path-labelled location option walker (`"Pantry › Middle shelf"`) is copied in `useStockFilters.allLocationOptions` (L233–244), `CreateStockItemDialog.allLocationOptions` (L303–314) and (per its comment) the detail page. · **Exact change:** `locationStore.pathOptions` computed; `filterLocations` narrowing helper alongside. · S · **execute**.
- **05-R24** · belief band ↔ word/sequence maps: `StocktakeReviewPhase.vue` (`BAND_WORD`, `BAND_SEQUENCE`, `BAND_BY_SEQUENCE`), `StocktakeRunner.vue:505` (`BELIEF_WORD`), `StockItemRow.vue:413` (`BELIEF_BAND_WORD`), + `PantryBeliefChip`/`PantryBeliefCard` (Chunk 7). · **Exact change:** `helpers/beliefBand.ts` (`bandWord`, `sequenceForBand`, `bandForSequence`); five call sites. · S · guard: new `beliefBand.spec.ts` · **execute**.
- **05-R26** · six more `stockLevels.find(l => l.stock_level_id === id)` lookups (`StockOverview.filterLevelSequence`, `CreateStockItemDialog.selectedLevelSequence`, `StocktakeReviewPhase.levelSequence`, `StockItemRow.levelName/levelSequence`, `StockLevelPicker.levelName/levelSequence`, `useStockFilters.levelSequence`) — **04-R11**'s `nameOf/sequenceOf` getters. · **execute (04-R11)**.
- **05-R19** · `StocktakeRunner` Mute confirm dialog duplicated (L683–689, L779–785). · **Exact change:** `confirmMute(name): Promise<boolean>`; both call it. · S · **execute**.
- **05-R16 / 05-R17** · `pageStyleFn` (02-R27) and the `.runner-*` shell (02-R28 `RunnerShell`) — this surface holds copies 5–6 and 3 respectively. · **execute (02-R27 / 02-R28)**.
- **05-R28** · local imports with no cycle to break: `create_stock_item.py:91, 202, 214`, `update_stock_item.py:287, 302, 388–391, 485, 496`, `get_stock_items.py:126, 181–183, 211` (`dataclasses` ×3). Only `_try_auto_add`'s shopping-list imports (L408–431) have a documented cycle. · **Exact change:** hoist the rest. · S · **execute**.

#### C3. Dead code / unused fields / unread endpoints

- **05-R14** · `useStockFilters` exports `summaryCounts`, `countByLevel`, `toggleLevelFilter` — zero callers. · **Exact change:** delete (and their spec cases). · S · **execute**.
- **05-R12** · `StockItemRow` `useStockLocationStore` import + flat-name fallback — dead (05-R11). · **execute**.
- **05-R7** · `review/complete` + `reviewCompleteAsync` — dead (above).
- **05-R38** · `useStockItemActions.findSubstitutes` and `seeRecipesUsing` — zero callers (grep: only `openDetail` is used, by `StockItemDetailPage.vue:2282`; the alerts model builds its own `/cookbook?usesStockItem=` URL at `models/alert.ts:155`). · **Exact change:** delete both. · S · **execute**.
- **05-R15** · list-DTO fields with no SPA reader: `stock_level_name` (the TS comment says "print-sheet labels", but the print view is server-rendered), `last_checked_at`, `opened_on` (grep in overview/row/filters → none; the **detail** DTO carries its own copies). · **Exact change:** drop the three from `StockItemDto` + `models/stockItem.ts`; keep `needs_restock` (cook mode reads it). · S · guard: `test_dto_contracts.py` · **execute**.
- **05-R21** · `StockOverview.bulkAddToPrimary` (keyboard `a`, quick-add target) vs `bulkAddToListPrompt` (bar, radio) — two bulk-add flows. Intentional (keyboard = fast path). · **waive** (document in the `a` shortcut description).
- **FU-698** · "Deselect all" ≡ "Cancel bulk select" — the code comment already answers it (kept because on a phone the bar is what's on screen). · **resolve FU-698** with that note.

#### C4. Componentisation opportunities (R-001)

- **05-R33** · `StockOverview.vue` (1,857 lines): the scan flow (L1435–1590, ~155 lines + the overlay template) and the bulk bar + its seven handlers (L371–451 + L1021–1399) are self-contained. · **Exact change:** `useStockScan(...)` composable (action, options, decode handlers) and `useStockBulkActions(...)` (selection, the seven actions, `pickActiveListId`); the page keeps filters, list, peek. · M · guard: vue-tsc + drive bulk and scan once · **FU** (same group as FU-780/01-R36/04-R20 — the "big page splits").
- **05-R37** · one `MarkAsWastedDialog` + one expiry `q-menu` **per row** (×50 before virtualisation). Hoist to a single page-level dialog keyed by the active row? Virtual scroll bounds the DOM; · **waive**.

#### C5. Placement / standards (R-002, R-005, R-008, D-rules)

- **05-R22** · raw Quasar palette vars in stock components: `StockItemRow.vue:732–733 (--q-accent), 835–836 (--q-negative), 842, 845 (--q-primary)`, `StockRowLegend.vue:178, 206–207`, `StockOverview.vue:1809 (--q-page — intentional, documented)` — 11 sites → `--brand-*` / `--semantic-*` (02-R37 family). Literal transitions `StockOverview.vue:1772 (0.25s ease)`, `MarkAsWastedDialog.vue:123 (120ms ease)` → motion tokens (D-010). `.scan-action-caption` `rgba(255,255,255,.82)` / `rgba(0,0,0,.6)` — R-002 carve-out (camera surface is always dark) → add the carve-out comment. · S · **execute**.
- **05-R23** · `StocktakeRunner.vue:960, 964, 1000` `var(--text-md, 1rem)` / `var(--text-xs, 0.75rem)` and `MarkAsWastedDialog.vue:137` `var(--text-sm, …)` — the type tokens are `--font-size-*`; `--text-md/-xs/-sm` are **undefined** (grep `css/*.scss` → none; FU-764 class) and have always painted their fallbacks. Plus raw px rhythm throughout the runner (`padding: 12px/24px`, `gap: 8px/4px/12px`, `border-radius: 12px`, `margin: 16px auto 0`) and `StockItemRow` (`font-size: 1.05rem / 0.8rem`, `border-radius: 8px/4px`, `padding: 6px 12px`, `gap: 14px/6px`) → `--font-size-*`, `--space-*`, `--radius-*`. · S (mechanical) · **execute** as one sweep with 05-R22; drive both pages after.
- **05-R29** · `StocktakeRunner` `$q.dialog` `ok: { label, color, unelevated }` ×3 (L689, 785, 818) lacks `noCaps` (R-039). · S · **execute**.
- **05-R8** · `stocktake.bulk_check` raw `table.update()` — acceptable (writes only `last_checked_at`/`snoozed_until`, no rule), but it `db.session.commit()`s directly rather than through the repository; and `get_stock_items._hydrate_linked_product_count` + `delete_stock_item` + `_gather_engagement_signals` + `sweep._latest_activity_by_item` use raw Core on mapped tables. All are aggregates/bulk the port can't express — consistent with the 02-R30 precedent. · **Exact change:** add `# R-005 carve-out: aggregate` comments where missing; `bulk_check` → `repo.session.execute(...)` + `repo.save_changes()`. · S · **execute**.
- **05-R31** · `GetStockGroupsHandler` loads every `StockItem` to count per group (L54–63) → `select(_stock_group_id, count()).group_by` (02-R30 shape). · S · **execute**.
- **05-R34** · `useStockOverviewExport.openPrintView` `window.open(baseUrl…)` — **R-045**, the 4th site of FU-682's defect (recipe print fixed; meal plan 02-R36; shopping 03-C10). `downloadCsv` uses raw `fetch(credentials:'include')` rather than the shared download path other exports use. · **Exact change:** `openHtmlDocumentAsync('/stock-items/print-view…')`; CSV via the shared `downloadFileAsync` helper if one exists (Chunk 18 inventories export helpers). · S · **execute (FU-682)**.
- **05-R27** · `GetStockItemsHandler.handle` collects entities via a side-effecting projection closure to feed the attention pass. Works; · **waive** (documented).
- **05-R40** · `/stocktake/queue` loads **every** stock item with level + location on each overview load, filters in Python. Bounded by the 500-item cap; · **waive** (note for FU-667's "client-side filtering over a hydrated collection" audit — this is its server twin).
- **05-R4** · `StocktakeRunner.onPickLevel:623–624` `sequence >= LOW_STOCK_SEQUENCE || sequence === OUT_OF_STOCK_SEQUENCE` (second clause redundant) → `needsRestockSequence(sequence)`; `void levelName` unused param. · S · **execute**.

#### C6. Naming & idiom
- **05-R35** · `stockLocationStore` vs `locationStore` — two stores for one concept (resolved by 05-R11).
- **05-R36** · `StockItemDto` vs `StocktakeQueueItemDto` vs `SessionItemDto` — fine; `StocktakeQueueItem` TS type duplicates `StocktakeSessionItem` minus `stock_level_id`/breadcrumb → one `StocktakeItemBase` interface. · S · **execute** (with 05-R10).

#### C7. Efficiency
- 05-R13, 05-R31, 05-R40 above. `useStockFilters.filteredStockItems` recomputes `attentionBand`/`outOfStock` per compare — fine at 500.

#### C8. Design-level findings — out of Stage-2 scope
- **05-D1** · **FU-728 (stocktake half) answered:** the runner **already** gives each lifecycle phase its own composition (`StocktakeReviewPhase`, the walk card, `StocktakeSweepPhase`) — R-054 is satisfied. Close FU-728 (cook-mode half answered in 04-D1).
- **05-D2** · The flat-vs-tree location API split (05-R11) is a leftover from before the tree existed; nothing in the owner's feedback wants a name-only location. Confirm with the owner that onboarding zones via the tree API is fine (they're zones anyway).
- **05-D3** · `StockLevelPicker` stays 32px on touch (R-085 carve-out, owner 2026-09-09) — recorded; no change.
- **05-D4** · FU-700: dashboard/help copy not gated on the stocktake switch — the help entry above names the switch; the dashboard half → Chunk 8.
- **05-D5** · FU-699 (full backend suite not run for the stocktake switch) — the baseline run at the start of this overnight (2429 passed / 2 order-dependent flakes) covers it → **resolve FU-699**.
- **05-D6** · FU-715 ("Needs attention filter broken" didn't reproduce) — the filter reads `needs_attention` only; stays confirm-in-browser.

#### C9. Hand-rolled-vs-library verdicts
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| `useStockFilters` client filter+sort over the hydrated collection | in-memory filtering | server-side query params (`parse_query_options` already supports `filter=`/`sort=`) | **keep (for now)** | — | FU-667 owns the question; at ≤ 500 items client-side is the right call and the deep-link chips depend on it. |
| `q-virtual-scroll` + fixed row metric | virtualisation | — | **keep** | — | Correct use of the framework. |
| `useDragDropList` (not used here), `v-touch-hold` | gestures | — | **keep** | — | Quasar directive. |
| `cadence.py` band resolver | rules | — | **keep** | — | Pure, tested. |
| `queue_ranking.sort_key` tuple sort | ranking | — | **keep** | — | Deterministic, tested. |
| `sweep._latest_activity_by_item` two aggregates | event dating | an `engagement_events` table | **keep** | — | Documented trade: derive, don't store. |
| `locationStore.breadcrumb` rebuilds parent/name maps per call | tree walk | memoised maps | **wrap** | S | Build the two maps once per tree load (computed); called per row. |

#### C10. Standards drift (R-0NN)
- **R-003** · 05-R3, 05-R6, 05-R24, 05-R25, 05-R11 — fix.
- **R-005** · 05-R7 (rule bypass), 05-R8 — fix.
- **R-008** · 05-R28 — fix.
- **R-021** · 05-R2 — fix.
- **R-032** · the attention pass and `_is_engaged` read `item.stock_level` directly; safe only because every caller includes the level — **FU-684** tracks the class; recommend `_level_access.resolve_levels_by_item` there when FU-683/684 execute (Chunk 6/7).
- **R-039** · 05-R29 — fix.
- **R-045** · 05-R34 — fix (FU-682).
- **R-002 / D-003 / D-010** · 05-R22, 05-R23 — fix.
- **R-085/D-004** · level square 32px — documented carve-out, clean.
- **FU-764** (undefined tokens) · 05-R23 `--text-md/-xs/-sm` — fix.
- **FU-624 / FU-675** · raw `$q.notify` ×30+, raw `q-select` ×6 — tracked.

#### C11. Ride-along signals for FU-010 / FU-224
- `--q-accent` 4 %/38 % washes on row hover; `--q-primary` 14 % selected fill — the accent-vs-primary question FU-224 owns.
- `.stock-row--dim { opacity: .62 }` + `.stock-row-legend__row-swatch--dim` — opacity dimming (D-002).
- Runner belief wash `--semantic-warning-soft` + warning hairline (measured 2.1:1 before the 09-01 fix; re-check pesto dark).
- `--brand-secondary-strong` essential stripe vs `active-color="secondary"` on the Essential chip — same concept, two tokens.

### E. Proposed follow-ups (orchestrator allocates ids)

- type=follow-up · *Extract `useStockScan` + `useStockBulkActions` from `StockOverview.vue`* (05-R33) — bundle with the "big page splits" group (FU-780, 01-R36, 02-D4, 04-R20).
- type=finding · *Flat `/api/stock-locations` duplicates the tree API* (05-R11 / 05-D2) — execute this run if the owner is fine with onboarding using the tree API; otherwise FU.
- type=finding · *`review/complete` bypassed every level-change rule* (05-R7) — resolved by deletion this run; record in CHANGELOG.
- **Resolve:** FU-698 (documented, keep), FU-699 (baseline suite run 2026-10-22), FU-728 (both halves answered: 04-D1, 05-D1).
- Existing FUs this chunk executes against: **FU-682** (05-R34), **FU-654** (`get_stock_items._disabled_kinds` literal `"user_id"` — copy 19), **04-R11**, **02-R27/02-R28**, **01-R8** (`_hydrate_linked_product_count._key`).

---

## Chunk 06 — Stock-Item Detail
*Source: [`CHUNK_06_stock_item_detail.md`](../05_investigations/finalisation/CHUNK_06_stock_item_detail.md) · analysed 2026-10-23*

### C. Senior review — Stock-Item Detail

Verdict key: **execute** (Stage 2 applies) · **FU** (orchestrator opens) · **waive** (recorded, no change) · **conditional** (execute if the stated check holds). Sizes S/M/L.

#### C1. Bugs (verified or high-confidence latent)
- **06-R1** · Two "+N days" rules on one item. `StockItemDetailPage.vue:1827–1835 shiftExpiry` shifts from `expiry_date ?? today(UTC)`; the row's `useStockItemActions.pushExpiry` (L179–202) shifts from `max(today, current)`. +1d on an expired item gives "still expired" here and "tomorrow" there. Also the detail copy uses UTC "today" (`toISOString`) while the row uses browser-local — both wrong under R-021. · **Exact change:** fold into 05-R2's `POST /stock-items/<id>/push-expiry` (server rule, household today); the page calls `actions.pushExpiry(id, days)` and `shiftExpiry` is deleted; pin with 05-R2's test. · S (given 05-R2) · **execute**.
- **06-R2** · D-006 — raw ISO dates on screen: `L499 {{ detail.expiry_date || '–' }}`, `L538 Opened {{ detail.opened_on }}`, timeline `L2460 fmt = (iso) => iso` and `L2479 body = e.new_expiry_date`. The glyph tooltip already goes through `formatDate` (FU-712 fixed that half). · **Exact change:** route all four through `formatDate` from `useDateFormat`. · S · **execute**.
- **06-R3** · R-003 / FU-799 class — the timeline infers *Restocked/Dropped* by regex on the level **name** (`L2375–2376 /^(low|out)/i`), which breaks for renamed levels ("Running out", "Nearly gone") and is the prose-parsed domain fact R-068 forbids. · **Exact change:** `LevelChangeDto` gains `stock_level_sequence: int | None` (resolve via the `_LevelLookup` already built at `get_stock_item_detail.py:496` — extend it to `{id: (name, sequence)}`); client compares sequences with `LOW_STOCK_SEQUENCE` from `helpers/stockStatus`. Drop the unread `stock_level_id` from the same DTO. · S · guard: `test_stock_item_history_feeds.py` + 1 case · **execute**.
- **06-R4** · Three level-change sites, three invalidation sets: `onChangeStockLevel` (L1974–1993) invalidates verdict + belief + planned demand; `useBuyVerdictActions.markStocked` (L61–67) verdict + belief; `useStockItemActions.markRestocked` (L162–167) verdict only. A *mark restocked* from the row leaves the belief chip and the demand grade stale; `markStocked` from the card leaves the demand grade stale. · **Exact change:** move the three invalidations into `stockItemStore.updateStockLevelAsync` (the one write path, R-074) and delete them from the three callers. · S · **execute**.
- **06-R5** · Two "mark restocked" implementations: `useBuyVerdictActions.markStocked` (finds `STOCKED_SEQUENCE`, toasts the level name) and `useStockItemActions.markRestocked` (takes `stockLevels[0]`, toasts "Marked restocked."). Same intent, different lookup, different toast. · **Exact change:** `markRestocked` delegates to the sequence-based lookup (use 04-R11's `stockLevelStore.stockedLevel`) and the two toasts become one; `markStocked` calls `markRestocked`. · S · **execute**.
- **06-R6** · Substitute rows fabricate a `StockItem` (`stockItemFor`, L2132–2142: `stock_level_id: sub.stock_level_id ?? ''`, nulls for location/group) to borrow a level *sequence* from the store, falling back to no colour when the store hasn't got the item. The DTO already carries `stock_level_id` + `stock_level_name`; what the row needs is the sequence. · **Exact change:** `SubstituteDto` gains `stock_level_sequence` (same `_LevelLookup` as 06-R3); delete `stockItemFor` and the `stockItems` dependency for this tab; drop `stock_level_name` from the DTO if cook mode's swap picker doesn't read it (grep at execution). · S · **execute (conditional on the cook-mode grep)**.
- **06-R7** · `get_stock_item_detail.py:601` and `:633` fetch **the same** `ShoppingListLine` set twice (`STOCK_ITEM_ID.eq(id)`) for the list-adds and purchase feeds; the second branch re-loads the parent lists the first already loaded. · **Exact change:** one fetch, one `{list_id: ShoppingList}` lookup shared by both feeds. · S · **execute**.
- **06-R8** · `get_stock_item_detail.py:874 self.repository.get(Barcode).all()` — a full-table scan of every barcode on every detail read, filtered in Python. · **Exact change:** `EntityField(Barcode, STOCK_ITEM_ID).eq(id) | EntityField(Barcode, PRODUCT_ID).in_(linked_ids)` (or two small queries). · S · **execute**.
- **06-R9** · `recently_priced.py:66 for item in self.repository.get(StockItem).all()` loads the whole pantry to hydrate ≤ 50 names. · **Exact change:** `EntityField(StockItem, "id").in_(list(latest))`. · S · **execute**.
- **06-R10** · The detail DTO as a sub-resource API (A5): `RecipeDetailPage.vue:1672` issues **one full detail read per ingredient** for substitutes; `RecipeCookMode.vue:1272`, `RecipeIngredientRowEditor.vue:368`, `LogPriceSheet.vue:190`, `StockItemRowPriceButton.vue:79` each read one slice. Every call runs 9 feeds, ~15 queries, and in complex nutrition a catalogue `suggest_for_name` (L935–937). · **Exact change (Stage 2, M):** add `GET /stock-items/<id>/substitutes` (handler already has the pair query — extract `build_substitutes(session, id, level_lookup)`), `GET /stock-items/<id>/price-entry-prefill` (extract `build_prefill`), and `GET /stock-items/<id>/buy-choices` (preferred buys + linked products); re-point the five callers; keep the detail DTO as is for the page. · M · **execute** (the extraction is also what 06-R11 wants).
- **06-R11** · `GetStockItemDetailHandler.handle` is ~570 lines in one method (`L418–989`); nine feeds, each with its own lookups, inline imports (`L773 Store as _StoreEntity`, `L780 ShoppingListLine as _Line` — both already imported at module top), and `_Lines` reused for two different collections (`L601` vs `L780`). R-001/R-008. · **Exact change:** split into `_linked_recipes`, `_linked_products`, `_substitutes`, `_level_history`, `_history_feeds` (waste / adds / purchases / cooks / expiry sharing one `HistoryTally`), `_prices` (observations + prefill + your-prices), `_barcodes`, `_nutrition`; drop the aliased imports; fix the two stale "Cap at 20" comments (`L698`, `L720`). · M · guard: `test_stock_item_router.py`, `test_stock_item_history_feeds.py`, `test_patch_semantics.py` · **execute**.
- **06-R12** · `link_product_to_stock_item.py:76–98` — per orphan line: `get(ShoppingList).by_id` + a `one()` lookup → N+1 on a product sitting on many lists. · **Exact change:** fetch the parent lists once by `shopping_list_id in_`, and the existing stock-item lines once by `(list_id in_) & stock_item_id`. · S · **execute**.
- **06-R13** · `get_buy_verdict._items_with_fake_markdown` (L870–904) calls `get_deal_quality` per linked product, each loading the product with both offer collections plus the household's paid prices — on the **bulk** path (`get_list_buy_verdicts`) that is one deep walk per product on the list. · **Exact change:** add `gather_deal_quality_for_products(ids)` in `deal_quality.py` (one products+offers include, one lines fetch) and call it here. · M · **FU** (Chunk 10 owns `deal_quality.py`; bundle with FU-683's B6 follow-through).
- **06-R14** · `your_prices.py` — `build_your_prices_for_item` (L126–265) and `build_your_prices_for_product` (L268–395) are the same ~80-line baseline block twice (sort, latest-dimension, window filter, median, strict-greater, display denominator, three identical empty-state constructions). FU-876 will change that rule — twice. · **Exact change:** `_baseline_from_observations(observations, *, repo, now, system) -> YourPrices` used by both; `_EMPTY_YOUR_PRICES` factory; the product variant passes `offers_sidecar=[]`. · M · guard: `test_your_prices.py` (20 cases) · **execute**.
- **06-R15** · `your_prices.py:47–60 measurement_system_from_repo` reads `repo.get(AppSetting).all()[0]` — a second copy of the install-wide setting read beside `app_settings.access.get_or_create_app_setting` (FU-759 class, R-003). · **Exact change:** `return getattr(get_or_create_app_setting(repo), "measurement_system", units.METRIC) or units.METRIC`. (Mind the commit-expiry hazard the detail handler documents: this runs *after* the entity load today — safe only because nothing below it reads a `noload` relationship on `_StockItem`; keep it that way or move the read up.) · S · **execute**.
- **06-R16** · Latent UX bug: `loadDetail → hydrateForm` after **every** save (L1738, L1845) overwrites `form.name`/`form.notes` with the server copy — a toggle flipped while Notes has an unsaved draft discards the draft; a peek id swap does the same without the R-020 guard (which only arms on route leave). · **Exact change:** `hydrateForm` keeps the current `form.notes`/`form.name` when `isDirty` is true and the id is unchanged; on an id change, if dirty, ask via the same guard dialog before swapping. · S · **execute**.
- **06-R17** · **Cross-surface (Chunk 5 file):** `StockOverview.vue:453–454` comment says the peek opens at **50 %** (feedback "open the split-view at 50%") while `L948 watch(peekId, v => splitPct = v ? 58 : 100)` sets **58**. Either the comment or the number is wrong; the feedback asked for 50. · **Exact change:** owner's call — 50 per the feedback, fix the comment either way. · S · **execute** (patch into CHUNK_05 §C1 as 05-R41 at assembly).

#### C2. Redundancy / DRY (R-001, R-003)
- **06-R18** · `BuyVerdictBadge.headline` (L107–115) and `BuyVerdictCard.headline` (L210–219) are the same mapping (the card adds strength grading); the "Based on N price sample(s) · N waste event(s) (last 12 months)." footer is written out in both (`Badge L49–62`, `Card L132–151`). · **Exact change:** `headlineFor(verdict)` and `dataUsedLine(dataUsed)` in `buyVerdictDisplay.ts`; both components call them. · S · **execute**.
- **06-R19** · `formatObsMeasure`/`trimZero` (L1920–1931) hand-roll quantity formatting beside `helpers/formatQuantity` (used by `substituteRatio.ts`). · **Exact change:** `obs.pack_count > 1 ? \`${n} × ${formatQuantity(total/n, unit)}\` : formatQuantity(total, unit)`; delete `trimZero`. · S · **execute**.
- **06-R20** · Three sibling cards, one anatomy, three stylesheets: `.belief-card`, `.demand-card`, `.dora-buy-verdict-card` each declare radius 8px / padding 10px 12px / sunken bg / `--border-strong` border / tone variants / 44px summary / icon tint (`PantryBeliefCard.vue:85–131`, `PlannedDemandCard.vue:96–140`, `BuyVerdictCard.vue:250–345`). · **Exact change:** one `.dora-signal-card` + `.is-{neutral,warning,negative,positive}` tone modifiers in `css/components.scss` (R-002 tokens); each card keeps only its own content rules. · S/M · **execute**.
- **06-R21** · `BuyVerdictCard` hand-rolls the disclosure (summary button + caret button, L15–82) that `CollapsibleCard` owns for the two cards above it — the belief card's own comment says CollapsibleCard "owns that shape for every disclosure in the app". · **Exact change:** host on `CollapsibleCard header-toggles` with the action button in a trailing header slot. · M · **conditional** — execute if `CollapsibleCard` exposes (or can trivially gain) a trailing-actions slot; else FU.
- **06-R22** · Preferred buys sorted A–Z on the server (`get_stock_item_detail.py:742–753`) **and** on the client (`L1857–1861`), with a stale client comment ("Backend still stores a position") and a stale TS doc ("ordered by position", `stockItemDetail.ts:231`) — FU-225 removed `position`. R-003: server owns order. · **Exact change:** render `detail.preferred_buys` as given; fix both comments. `RecipeIngredientRowEditor.vue:371–372` has the same client sort → drop. · S · **execute**.
- **06-R23** · `primaryListId = computed(() => quickAddTargetListId ?? null)` (L2303) and `formatDateTime` (L2589–2592) are pass-through wrappers. · **Exact change:** use the store computed and `formatLocaleDateTime` directly. · S · **execute**.

#### C3. Dead code / unused fields / unread endpoints
- **06-R24** · Detail-DTO fields with no SPA reader on this page or anywhere: `stock_location_name`, `stock_location_breadcrumb` (costs a `StockLocation.all()` + breadcrumb walk per read, L487–491), `stock_group_name`, `usual_store_name` (a `Store.by_id` per read, L860–863) — the page edits all four through id pickers and never shows the names (grep `detail.stock_location_name|stock_location_breadcrumb|stock_group_name|usual_store_name` in `web_app/src` → the only breadcrumb readers are *other* DTOs: stocktake, put-away, line sections). `LinkedProductDto.brand` / `merchant_stockcode` — unread on this page (`.brand` readers are product components; `merchant_stockcode` only `CustomProductDialog`, a different DTO). `PriceObservationDto.shopping_list_line_id` and `.store_id`, `PurchaseEventDto.store_id` — only the resolved names are read. · **Exact change:** drop the nine fields from the DTOs + `models/stockItemDetail.ts`; delete the breadcrumb + usual-store lookups; update the handler docstring (L7–8 still promises "location name and stock-level name so the page doesn't cross-reference"). · S · guard: `test_stock_item_router.py` · **execute**.
- **06-R25** · `StockItemDetailDto.unit_cost` — no SPA reader (grep → `models/` only); the page shows `your_prices.current` (display denominator) instead, so the DTO carries two "current per-unit cost" numbers in two unit bases (R-003 smell). `test_price_observations.py` ×3 assert `unit_cost`. · **Exact change:** drop `unit_cost` + `get_stock_item_unit_cost_at` call (L811; keep the domain function — reports and recipe cost use its sibling); re-point the three tests at `your_prices.current` (allow for the display factor). · S · **execute**.
- **06-R26** · `models/stockItemDetail.ts:67–73 WasteEvent.quantity / estimated_value / note` — the DTO sends `occurred_at` + `reason` only (C-waste slim); grep `.estimated_value|w.quantity|w.note` → none. · **Exact change:** drop the three members. · S · **execute**.
- **06-R27** · `ICONS` is `as const` with every key defined, so `ICONS.schedule ?? 'schedule'`, `ICONS.help ?? 'help_outline'` (`BuyVerdictBadge.vue:95–97`), `ICONS.event_repeat ?? 'mdi-calendar-refresh'` (`BuyVerdictCard.vue:101`), `ICONS.price_check ?? …`, `ICONS.inventory_2 ?? …`, `ICONS.delete_outline ?? …` (`buyVerdictDisplay.ts:13–16`) are dead fallbacks that also hide a typo forever. · **Exact change:** remove the six `??`. · S · **execute**.
- **06-R28** · `unlink_product_from_stock_item.py:87–94` — the `UUID(str(product_id))` coercion + comment claims Flask hands the param as `str`, but the route is `<uuid:product_id>` (L83) so it is already a `UUID`; dead defensive code from the FU-528 era. `add_substitute.py:58 str(a) == str(b)` is the same reflex while `update_substitute.py:65` compares directly. · **Exact change:** delete the coercion; compare UUIDs directly in both; this is 01-R8's `uuid_bind` family — apply its helper if a real str path remains anywhere. · S · **execute**.
- **06-R29** · `add_substitute.py:11 from dora_api.domain import units` — unused (validation lives in `substitutes.metadata`). · S · **execute**.
- **06-R30** · `stock_item_price_history.py:36,44 canonical_unit` carries the **display** unit (FU-910) — rename to `display_unit` through `StockItemPriceHistoryDto`, `priceHistoryApiService.ts:65`, `stockItemHistoryToChart`. · S · **execute (resolves FU-910)**.
- **06-R31** · Stale comments: `YourPricesWidget.vue:14–17` ("[Full history] disabled until chunk 6"), `stockItemDetail.ts:241–243` ("chunk 3 placeholder"), `get_stock_item_detail.py:698,720` ("Cap at 20" vs the 50 constant), `StockItemDetailPage.vue:751–756` ("Chunk 4 lights up… chunk 6 wires"). · S · **execute**.

#### C4. Componentisation opportunities (R-001)
- **06-R32** · `StockItemDetailPage.vue` (2814 lines) is the second-largest page after `ShoppingListDetail` (FU-780). Natural seams, each already a self-contained block: `StockItemOverviewTab.vue` (L83–811 — the inline-edit list + preferred buys + prices), `StockItemSubstitutesTab.vue` (L992–1076 + picker dialog L1337–1366), `StockItemScanningTab.vue` (L1094–1236 + QR state L1520–1578), `StockItemHistoryTab.vue` (L1289–1319 + `lifecycleEvents` L2343–2529 → a pure `helpers/lifecycleTimeline.ts` with a vitest), `StockItemProductsTab.vue` (L821–944 + L2012–2064), `useStockItemDetail(id)` composable owning `detail/loading/busy/saveField/withBusyReload/loadDetail` + the store-sync watcher. · **Exact change:** the split above; page keeps the header, tabs, delete and the dialogs it hosts. · L · **FU** (bundle with the "big page splits" group: FU-780, 01-R36, 02-D4, 04-R20, 05-R33).
- **06-R33** · `NutritionFoodPicker.vue:2–87` hand-rolls `q-dialog` + `q-card` while every other dialog on this surface uses `BaseDialog` (R-001; D-rules on dialogs ride on the base). · **Exact change:** host on `BaseDialog` (`closable`, `title`, `#actions`). · S · **execute**.
- **06-R34** · `openToggle.ts` is a pure helper with no Vue import living in `composables/` (its own header says it is "kept free of Quasar/store imports"). · **Exact change:** move to `helpers/openToggle.ts` with its spec. · S · **execute**.
- **06-R35** · `models/stockItemDetail.ts:295–304 PricePoint / PriceHistory` are the **product** price-history types (`productApi.getPriceHistoryAsync`) parked in the stock-item model. · **Exact change:** move to `models/product.ts` (or the product API service). · S · **execute**.

#### C5. Placement / standards (R-002, R-005, R-008, D-rules)
- **06-R36** · Inline `style=` ×21 on the page: eleven `style="max-width:160px"` label cells (L112…635), `style="font-size: 0.75rem"` (L308), `style="min-width: 0; padding-right: 8px"` (L270), `style="width: 256px; height: 256px; max-width: 100%"` (L1128), `style="max-height: 60vh; overflow: auto"` (L1341), plus `style="margin-left: 24px/26px"` ×4 in the two verdict components and `style="max-width: 110px"`/`"min-width: 130px"` ×4 in `SubstituteMetadataDialog`. · **Exact change:** classes (`.dora-inline-edit__label`, `.dora-buy-verdict__detail`, `.sub-ratio-row__qty/__unit`, `.stock-detail__qr`). · S · **execute**.
- **06-R37** · D-003 — px/rem literals off the type scale: 49 across the five card/page files (`0.6875rem`, `0.75rem`, `0.8125rem`, `0.875rem`, `0.9375rem`, `1rem`, `font-size: 10` in the SVG), and `NutritionFoodPicker` ×8. `YourPricesWidget` and `PriceHistoryChart` already use `calc(var(--font-size-*) * 1rem)` — the pattern to follow. · **Exact change:** token sweep (02-R37 / 05-R22 class). · S · **execute**.
- **06-R38** · D-002 / FU-671 — `text-color="white"` on semantic chips: *Cheapest* (`L878–885`) and *above usual* (`PriceHistoryBottomSheet.vue:35–43`). `colourForSequence`'s sibling `TINT_BY_SEQUENCE` shows the house pattern (`dora-chip--tint-positive/-warning`). · **Exact change:** the two tint classes, no `text-color`. · S · **execute (two of FU-671's sites)**.
- **06-R39** · Raw icon strings: `name="circle"` (L1013 — the substitute dot; `StockLevelDot` exists and takes a sequence → use it, which 06-R6 enables) and `icon: 'lock_open'` (L2500). · **Exact change:** `StockLevelDot` + `ICONS.lock_open` (add to the registry). · S · **execute**.
- **06-R40** · R-039 — `confirmDelete` passes `cancel: { noCaps: true }` but its OK button isn't declared, and the *Still used by recipes* dialog builds `html: true` markup by string concatenation (`L2566–2577`; one of 4 `html: true` app-wide). · **Exact change:** `ok: { noCaps: true }`; render the recipe list via a tiny `BlockedByRecipesDialog.vue` (or the FU-623 wrapper when it lands) instead of HTML strings. · S · **execute**.
- **06-R41** · R-008 — logger idiom: `get_stock_item_detail`, `add/remove/update_substitute`, `link/unlink` create `_Logger = logging.getLogger(__name__)` inside the route per request; `get_buy_verdict`, `get_planned_demand` use a module-level `_LOGGER`; `preferred_buys` / `price_observations` call `logging.getLogger(__name__)` inline. · **Exact change:** module-level `_LOGGER` across the group. · S · **execute**.
- **06-R42** · R-008 / E402 — `your_prices.py:25–35 _as_naive_utc` is defined **between** the `from __future__` import and the module imports. · **Exact change:** move below the imports. · S · **execute**.
- **06-R43** · R-005 — `add/remove/update_substitute.py` and the detail handler read/write the `StockItemSubstitute` association via `db.metadata.tables[...]` Core statements because the generic repository cannot self-join `StockItem`. Portable Core; documented. · **waive** (same posture as 03-R37; revisit if the association ever becomes an entity).
- **06-R44** · R-021 — `BuyVerdictCard.waitHintTargetLabel` (L223–238) computes "in ~N days" from the **browser's** today; the server computed `until` from household today. Off by one across the household/browser zone boundary. · **Exact change:** either the server adds `days_until` to `WaitHintDto`, or the client uses `householdToday()` (04-R?/R-021 helper). · S · **execute** (server field — one rule).
- **06-R45** · R-021 — `_AxisInputs.today: date = field(default_factory=date.today)` (`get_buy_verdict.py:253`) is a server-local default; every production path overrides it with `household_today`. · **waive** (test-only default; comment says so).

#### C6. Naming & idiom
- **06-R46** · `recipesForDetail` casts `recipes.value.filter(...) as unknown as Recipe[]` (L2072, L2106): the store's `recipes` is typed differently from `models/recipe.Recipe`. · **Exact change:** fix the store type (or `RecipeCard`'s prop) so the double cast goes. · S · **execute**.
- **06-R47** · `NutritionFoodPicker` borrows `useSettingsSave().notifyError` — a settings-page helper used as a generic error toast on a stock surface (and FU-624 wants one notify wrapper). · **Exact change:** `toastCaption` + `$q.notify` like its neighbours until FU-624 lands. · S · **execute**.
- **06-R48** · `onLists` fallback row `{ shopping_list_id: lid, name: lid, status: 'draft' }` (L2297) renders a UUID as a list name if membership and summaries disagree. · **Exact change:** filter the unknowns out (the comment already says they shouldn't exist). · S · **execute**.
- **06-R49** · `_NutritionIsComplex` — the only CapWords local in a handler whose other locals are `_StockItem`-style; fine. `_Purchases_raw` mixes the two conventions. · S · **execute** (rename with 06-R11).

#### C7. Efficiency
- **06-R50** · `loadDetail` triggers `shoppingListStore.refreshAsync()` on **every** reload (L2610) — i.e. after each field save, toggle and preferred-buy edit — a membership+summaries round-trip the save didn't need. · **Exact change:** refresh only from the list-affecting actions (`onAddToList`, `onAddMissing/AllToList`, `onUnlink`, `onBuyVerdictAction`). · S · **execute**.
- **06-R51** · `loadPriceHistories` (L2032–2048) fires one `productApi.getPriceHistoryAsync` per linked product for the sparklines; `priceHistoryApiService.seriesAsync(ids)` already batches. · **Exact change:** one `seriesAsync(ids, '90d')` call, map `points → price_now`. · S · **execute**.
- **06-R52** · `watch(storeItem, …, { deep: true })` (L2643–2663) deep-watches a computed that the store replaces wholesale on every mutation (`stockItems.value[idx] = refreshed`); `deep` adds a per-tick traversal for nothing. · **Exact change:** drop `deep`. · S · **execute**.
- **06-R53** · Complex nutrition runs `suggest_for_name` (a catalogue match) on every detail read of every unlinked, un-ignored item — including the five sub-resource callers in 06-R10. · **Exact change:** lands with 06-R10 (the sub-endpoints skip it); for the page itself it is the right place. · — · **execute via 06-R10**.
- **06-R54** · `get_planned_demand` loads every stock item + resolves levels per call to grade urgency; ≤ 500 items, cheap. · **waive**.

#### C8. Design-level findings — out of Stage-2 scope
- **06-D1** · Server-formatted dates inside reason prose: `_wait_hint.reason` (`strftime('%b %d')`, L525) and `planned_demand.build_reason` (`'%a' day '%b'`, L131–132) — same class as 03-R8 (`strftime('%a %d %b')`) and R-056 (one regional convention). The client already receives `until` / `earliest_needed` and formats dates through `useDateFormat`. **Recommend** the server drops the date clause from these sentences and the client appends it formatted; needs the owner's nod because the sentences are owner-approved copy. → FU (cross-surface: 02, 03, 06).
- **06-D2** · FU-706 (no edit / no confirm on observations), FU-707 (signal presentation), FU-876 (latest-dimension rule), FU-704 (PriceEntry on a phone), FU-705 (chart touch) — all open design calls on this surface; copy in B2-3 states the current rules honestly. No action here.
- **06-D3** · FU-644 — preferred buys hidden when Products is on, no migration nudge. Still a decision.
- **06-D4** · The item page has no *Log waste* action though waste is the one event the History tab can't otherwise explain; the row has it. Owner ≥ 90 % happy → record only.
- **06-D5** · `?section=<unknown>` renders an empty tab panel; a `tab` guard to `overview` is a two-line fix but changes nothing the user has asked for → fold into 06-R32 when the page splits.
- **06-D6** · FU-711 — "Opened" vs "open / in-use" wording across row / help; copy sweep.

#### C9. Hand-rolled-vs-library verdicts
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| `PriceHistoryChart.vue` inline SVG | charting | ECharts (removed, FU-833) | **keep** | — | Deliberate; a11y text alternative only possible as SVG. |
| `useBuyVerdict` Map cache | per-item cache | Pinia / TanStack Query | **keep** | — | Documented rationale; `primeBuyVerdicts` handles bulk. |
| `relativeTime.ts` | relative time | `Intl.RelativeTimeFormat` / date-fns | **wrap** | S | A 20-line formatter is fine, but it should respect the install locale (R-056) — route through `useDateFormat`'s locale when it gains relative output. |
| `_trimmed_mean`, `statistics.median/pstdev` | stats | numpy | **keep** | — | Stdlib. |
| `q-date` in the expiry dialog | date picker | — | **keep** | — | Framework. |
| `allLocationOptions` tree walk (L1610–1621) | path labels | `helpers/locationDisplay.ts` / 05-R25 `locationStore.pathOptions` | **replace** | S | Same walk as `CreateStockItemDialog` / `PutAwayDialog`; 05-R25 is the one home. |
| `DoraTabs` | tabs | `q-tabs` | **keep** | — | Owner-chosen indicator. |
| `NutritionFoodPicker` search token | race guard | AbortController | **keep** | — | Correct and small. |

#### C10. Standards drift (R-0NN)
- **R-003** · 06-R3, 06-R5, 06-R6, 06-R15, 06-R18, 06-R19, 06-R22, 06-R25 — fix.
- **R-001** · 06-R10/R11 (extraction), 06-R20, 06-R33, 06-R34 — fix; 06-R32 → FU.
- **R-002 / D-002 / D-003** · 06-R36, 06-R37, 06-R38, 06-R39 — fix.
- **R-005** · 06-R43 — waived carve-out, documented.
- **R-008** · 06-R41, 06-R42, 06-R46, 06-R49 — fix.
- **R-021** · 06-R1 (with 05-R2), 06-R44 — fix; 06-R45 waived.
- **R-032** · the detail handler reads `_StockItem.stock_level` / `.stock_location` / `.stock_group` off the relationships (L954–960) — safe only because of the include list **and** the `_nutrition_is_complex` ordering rule; `_level_access.resolve_levels_by_item` is the house answer for the level (FU-684 sweep). Recommend using it here when FU-684 executes (Chunk 7); until then the docstring guard stands. → tracked FU-684.
- **R-039** · 06-R40 — fix.
- **R-045** · none on this surface (QR + print already blob-based via `useQrLabels`).
- **R-056 / D-006** · 06-R2 — fix; 06-D1 → FU.
- **R-074** · 06-R4 — fix.
- **FU-764** (undefined tokens) · none found on this surface (`--focus-ring`, `--accent-ink`, `--radius-*`, `--space-*` all defined; `NutritionFoodPicker` fixed its `--text-accent` already).
- **FU-624 / FU-675** · raw `$q.notify` ×9 on the page, raw `q-select` ×5 (Location/Group/Store + 2 unit pickers) — tracked.

#### C11. Ride-along signals for FU-010 / FU-224
- Three signal cards use `--semantic-*-soft` fills with `--border-strong` neutrals; the cheapest-product card uses `color-mix(--brand-primary 8%)` — the primary/semantic split FU-224 owns.
- `.dora-buy-verdict-badge.is-unsure` border = `--surface-sunken` on a `--surface-sunken` fill (invisible border by design?) — check in pesto dark.
- `.dora-buy-verdict-popover` hardcodes `box-shadow: 0 6px 18px rgba(0,0,0,.15)` (R-002 — an `--elevation-*` token exists for cards elsewhere).

### E. Proposed follow-ups (orchestrator allocates ids)

- type=follow-up · *Split `StockItemDetailPage.vue` into tab components + `useStockItemDetail`* (06-R32) — bundle with the "big page splits" group (FU-780, 01-R36, 02-D4, 04-R20, 05-R33).
- type=finding · *Bulk `deal_quality` gather for the verdict's fake-markdown check* (06-R13) — Chunk 10 surface; cite FU-683 B6.
- type=finding · *Server-formatted dates inside reason prose (wait hint, planned demand, shopping day names)* (06-D1; 03-R8; R-056) — one decision for three sites.
- type=finding · *Peek opens at 58 % while the comment and the feedback say 50 %* (06-R17) — patch into CHUNK_05 at assembly; execute with the owner's number.
- **Resolve:** FU-910 (06-R30 executes it).
- Existing FUs this chunk executes against: **FU-671** (06-R38, two sites), **05-R2 / FU-123** (06-R1), **01-R8** (06-R28), **05-R25** (C9 location walk), **04-R11** (06-R5), **02-R37 / 05-R22** (06-R37).
- Existing FUs referenced, unchanged: FU-706, 707, 704, 705, 876, 644, 851, 849, 711, 712, 685, 684, 683, 923, 575, 753, 847, 624, 675, 780.

---

## Chunk 07 — Zero-Input Pantry (P8-07)
*Source: [`CHUNK_07_zero_input_pantry.md`](../05_investigations/finalisation/CHUNK_07_zero_input_pantry.md) · analysed 2026-10-23*

### C. Senior review — Zero-Input Pantry

Verdict key: **execute** · **FU** · **waive** · **conditional**. Sizes S/M/L.

#### C1. Bugs (verified or high-confidence latent)
- **07-R1** · R-021 — `pantry_belief._as_date` (L284–290) takes `datetime.date()` of UTC-stored `stock_level_last_updated`, `last_checked_at`, list `completed_at` and consumption `occurred_at`, while `today` is `household_today()`. In any household east of UTC a morning level change dates to **yesterday**: *Updated 1 day ago*, and a check that should pin the belief for three days pins for two; purchase dates and cook dates shift the same way (the `FU-525` class `get_buy_verdict._local_date` already fixed for the verdict). · **Exact change:** `_as_date(value, tz)` → `value.astimezone(tz).date()` (naive values assumed UTC), with `tz = household_timezone(repository)` resolved once in `gather_beliefs_for_items`; add the test in §D. · S · **execute**.
- **07-R2** · R-032 / FU-684 — `inference_overlay.divergent_items` (L147–149) reads `is_missing(item.stock_level)` off the `noload` relationship; the three callers each `.include(STOCK_LEVEL)` to make it work, and `_level_access`'s docstring records that an include can still return an identity-mapped instance with the relationship unset — exactly how `/buy-verdict` once answered *unsure* for everything. `gather_beliefs_for_items` already resolves the levels by FK one line earlier and throws them away. · **Exact change:** have the gather return (or expose) `levels_by_item`; `divergent_items` computes `recorded_missing` from `is_missing(levels_by_item[id])`; drop the three now-unneeded includes (`get_recipes.py:1352`, `get_shopping_list_detail.py:769`, `get_meal_plans.py:593–594`'s `then_include(STOCK_LEVEL)`) and the "theatre" includes in `get_pantry_beliefs.py:54` and `generators.py:379`. · S · guard: `test_inference_overlay.py` + an e2e that asserts a hint with the include removed · **execute**.
- **07-R3** · `PantryBeliefChip.vue` has no importer (grep `PantryBeliefChip` → only comments in `PantryBeliefCard.vue:5,82`, `StockItemRow.vue:401`, `StockItemDetailPage.vue:196`, `StocktakeRunner.vue:503`) and still received a DR-8 fade fix after it died (FU-686 / FU-695). · **Exact change:** delete the file; reword the five comments to name the live form (the picker's ring + menu header). · S · **execute (resolves FU-686 and FU-695; the owner's "is the row chip coming back?" is answered by D-5 — one dashed marker on the level box)**.

#### C2. Redundancy / DRY (R-001, R-003)
- **07-R4** · Five identity maps band → word (`{out:'out', low:'low', stocked:'stocked'}`): `PantryBeliefCard.vue:69`, `PantryBeliefChip.vue:46`, `StockItemRow.vue:412`, `StocktakeReviewPhase.vue:161`, `StocktakeRunner.vue:505`. Each maps a string to itself and falls back to the input. · **Exact change:** delete all five; render `belief.believed_band` directly (05-R24's `helpers/beliefBand.ts` is only needed if a *different* word is ever wanted — today none is). · S · **execute**.
- **07-R5** · Three copies of the hint tooltip: `MealPlanEntryChip.vue:162–167` and `MealPlanRichCard.vue:162–167` are byte-identical; `useRecipeDisplay.ts:204–210` differs only in the leading clause. The `at_risk → text-warning / else → text-positive` class pick is also written twice. · **Exact change:** `helpers/inferenceHint.ts` exporting `inferenceTooltip(hint, names, surface: 'recipe' | 'plan')` and `inferenceTone(hint)`; three callers import it. · S · **execute**.
- **07-R6** · `usePantryBeliefs.ts` and `usePlannedDemand.ts` (Chunk 6) are the same 58-line module-cache shape (`loaded/loading`, `loadAsync(force)`, `xFor(id)`, `invalidate`). The second was copied from the first "on purpose". · **Exact change:** `composables/createOverlayCache<T>(fetch: () => Promise<{enabled?: boolean; map: Record<string,T>}>)`; both become 10-line instantiations. FU-851's invalidation bus then has one subscriber type. · S · **execute**.
- **07-R7** · Two `IngredientRow` constructions from two different shapes (`get_recipes.py:1361–1370` from the DTO; `get_meal_plans.py:611–622` from entities, re-deriving `is_missing` and `missing_count_for`/`unlinked_count_for` inline). · **Exact change:** `IngredientRow.from_dto(dto)` and `IngredientRow.from_entity(ingredient, levels_by_item)` classmethods in `inference_overlay.py`; the meal-plan path reads levels through 07-R2's map. · S · **execute**.
- **07-R8** · FU-654 / 02-R12 — `get_pantry_beliefs._current_user_id` (L32–39), `inference_overlay.current_user` (L112–124) and `generate_pantry_check`'s `repository.get(User).by_id(user_id)` gate are three of the **31** `session.get("user_id")` / `SESSION_USER_ID_KEY` copies now in `dora_api` (29 files). · **Exact change:** 02-R12's `infrastructure/auth_helpers.current_user_id()` + `current_user(repo)`; the two local helpers go. · S (given 02-R12) · **execute**.
- **07-R9** · `gather_beliefs_for_items(..., _return_inputs=True)` returns a dict of `BeliefInputs` *or* `PantryBelief` depending on a private flag (L298–368), typed `-> dict`. · **Exact change:** `gather_belief_inputs_for_items(repo, items) -> dict[UUID, BeliefInputs]` + `gather_beliefs_for_items` = `{k: compute_belief(v) for …}`; `gather_belief_inputs` (single) calls the former. · S · **execute**.

#### C3. Dead code / unused fields / unread endpoints
- **07-R10** · `ConsumptionEvent.from_sequence / to_sequence` are written (`update_stock_item.py:371–380`, seeds) and **never read** (grep `from_sequence|to_sequence` outside entity/mapping/writer/seed/tests → none); the entity docstring promises the belief "can weight a drop-to-out more heavily", which `compute_belief` doesn't do. · **Exact change:** either (a) use them — a weight by `to_sequence` in `_CONSUMPTION_WEIGHT` — or (b) drop the columns. (a) is a model change (owner call; it also moves the §1.3 envelope); (b) is a migration for two nullable ints. · **FU** (decision), with the envelope test below as the guard either way.
- **07-R11** · `CONSUMPTION_SOURCE_MANUAL` / `_WASTE` are accepted by `_VALID_CONSUMPTION_SOURCES` but the SPA only ever sends `'cook'` (`RecipeCookMode.vue:1559`); the proposal §4 records manual-drop recording as deliberately out of scope. · **waive** (documented sentinel; the TS union `'cook' | 'manual' | 'waste'` at `stockItemApiService.ts:312` stays honest about the contract).
- **07-R12** · `PantryBelief.believed_sequence` travels on the DTO but no SPA reader (grep `believed_sequence` in `web_app/src` → `models/pantryBelief.ts` only); `confidence` (the float) likewise — every surface reads `confidence_band`. · **Exact change:** drop both from `asdict` output (keep on the dataclass for the ranking's `sort_key`) via a `_to_dto` that picks the five rendered fields; drop the TS members. · S · **execute**.

#### C4. Componentisation opportunities (R-001)
- **07-R13** · The three Zero-Input sections of `AssistantSettings.vue` (L232–330) are four near-identical `SettingsRow inline` + `InfoTip` + `q-toggle` blocks bound to `currentUser.<flag>` with an `onSurfaceChange` map. · **Exact change:** a `UserFlagToggleRow` (label, tip, flag) driven by a small array — Chunk 13's settings-shell pass should own it; record here, execute there. · S · **conditional** (execute if Chunk 13 doesn't already propose a generic flag row).

#### C5. Placement / standards (R-002, R-005, R-008, D-rules)
- **07-R14** · `inference_overlay.py` imports `flask.session` to find the user — a domain-ish rule module reaching into the web layer (R-004/R-008 layering; the belief module itself is clean). Fixed by 07-R8 (helper in `infrastructure`). · **execute via 07-R8**.
- **07-R15** · `MealPlanEntryChip.vue:65` / `MealPlanRichCard.vue:61` colour the Dora glyph with Quasar `text-warning` / `text-positive` palette classes while `RecipeBeliefChip` uses the house `dora-chip--warning/--positive` tokens (R-002; FU-777 class). · **Exact change:** token classes via 07-R5's `inferenceTone`. · S · **execute**.
- **07-R16** · `PantryBeliefChip.vue` `font-size: 0.72rem`, `border-radius: 10px`, `padding: 1px 7px` — moot after 07-R3.
- **07-R17** · `get_pantry_beliefs.py` returns `asdict(belief)` per item — a dataclass→dict at the edge rather than a DTO; fine, but 07-R12's `_to_dto` is where the contract should live.

#### C6. Naming & idiom
- **07-R18** · `_as_date` becomes `_household_date(value, tz)` with 07-R1 so the name says which calendar it answers in.
- **07-R19** · `generators.py:379 items = … .include(STOCK_LEVEL)` + `name_by_id` — after 07-R2 the include goes; keep `name_by_id`.

#### C7. Efficiency
- **07-R20** · `get_shopping_list_detail._inferred_suggestions` gathers beliefs for **every** stock item not on the list on every detail read when the surface is on (03-R36 flagged the same block for loading all items before the gate). The proposal §6 accepts this; the gate (`surface_enabled`) runs **after** the `StockItem.all()` fetch (L768–770). · **Exact change:** check `surface_enabled(current_user(repo), SURFACE_SHOPPING)` before fetching candidates (3-line reorder; `resolve_divergence` keeps its own gate). · S · **execute (with 03-R36)**.
- **07-R21** · `get_meal_plans` hydration loads every pending recipe with ingredients→stock item→level via `then_include` chains just to build rows; after 07-R2/07-R7 it needs ingredients + FK ids only. · **execute via 07-R2/R7**.
- **07-R22** · `generate_pantry_check` loads all open lists' lines and all week's `MealPlanEntry` rows per suggestion run; the run is on-demand and capped — fine. · **waive**.

#### C8. Design-level findings — out of Stage-2 scope
- **07-D1** · Belief has no quantity awareness (impl plan §1.3) — one tin and twelve tins are the same signal. Recorded; the §4 out-of-scope list owns it.
- **07-D2** · Consumption weighting by band (07-R10) is a model decision.
- **07-D3** · The shopping-surface suggestion block and the planner glyph have no "dismiss"; §7 of the inference proposal closed this as *No*. Nothing to do.
- **07-D4** · FU-851 — overlay caches go stale after plan edits / cooks / finished shops; one invalidation bus for `usePantryBeliefs` + `usePlannedDemand` + `useBuyVerdict` (07-R6 makes them one shape first).

#### C9. Hand-rolled-vs-library verdicts
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| `compute_belief` | hand-rolled depletion model | a forecasting lib | **keep** | — | Coarse-by-design (Charter P2); a library would add precision the product refuses. |
| `mean_gap_days` | arithmetic | `statistics.fmean` over diffs | **keep** | — | The sorting/zero-gap rule is the point. |
| module caches (`usePantryBeliefs`, `usePlannedDemand`) | cache | Pinia store / TanStack Query | **wrap** (07-R6) | S | One factory, not a dependency. |
| `SURFACE_FLAGS` string map | config | enum | **keep** | — | Closed set, R-010 carve-out documented. |

#### C10. Standards drift (R-0NN)
- **R-021** · 07-R1 — fix (the FU-525 precedent).
- **R-032 / FU-684** · 07-R2 — fix; removes five includes that existed only to make a relationship read work.
- **R-003** · 07-R4, 07-R5, 07-R7, 07-R9 — fix.
- **R-001** · 07-R6 — fix; 07-R13 → Chunk 13.
- **R-002 / FU-777** · 07-R15 — fix.
- **R-004/R-008** · 07-R14 (`flask.session` in a rule module) — fix via 07-R8 / FU-654.
- **R-010** · closed-set strings (`believed_band`, hint kinds, surfaces) documented as carve-outs — clean.
- **R-027** · pure composer + repo gather split — exemplary; the chunk's shape to copy elsewhere.

#### C11. Ride-along signals for FU-010 / FU-224
- Dora glyph tinted `--semantic-warning` on `--semantic-warning-soft` across chip/card/row/planner — consistent; the planner's `text-warning` (07-R15) is the one stray.
- The dashed `--accent-mark` ring (D-5) vs the amber belief tint in the picker header: two hues for one uncertainty — intentional per D-5 (accent = "metadata about the level"), note for FU-224.

### E. Proposed follow-ups (orchestrator allocates ids)

- type=finding · *`ConsumptionEvent.from_sequence/to_sequence` are written and never read — weight them or drop them* (07-R10 / 07-D2) — owner decision; opportunistic.
- **Resolve:** FU-686 and FU-695 (07-R3 deletes the chip and rewords the five comments).
- Existing FUs this chunk executes against: **FU-684** (07-R2 — the belief/overlay slice of the R-032 sweep), **FU-654 / 02-R12** (07-R8 — three more copies), **03-R36** (07-R20), **05-R24** (07-R4 supersedes the need for `beliefBand.ts`), **FU-777 class** (07-R15).
- Existing FUs referenced, unchanged: FU-683 (plan done; browser-verify owed), FU-851 (07-D4), FU-525 (precedent).

---

## Chunk 08 — Dashboard
*Source: [`CHUNK_08_dashboard.md`](../05_investigations/finalisation/CHUNK_08_dashboard.md) · analysed 2026-10-23*

### C. Senior review — Dashboard

Verdict key: **execute** · **FU** · **waive** · **conditional**. Sizes S/M/L.

#### C1. Bugs (verified or high-confidence latent)
- **08-R1** · `get_restock_radar.py:149–151` builds `recorded_by_item = {item_id: level.sequence for item_id, level in levels.items()}` — `resolve_levels_by_item` returns `None` for an item with no level (its docstring says so; `get_planned_demand.py:39–42` and `get_buy_verdict.py:823–827` both guard `if level is not None`), so one unlevelled item 500s the whole card. Latent today because create requires a level, but a deleted level nulls the FK. · **Exact change:** add `if level is not None`. · S · guard: `test__restock_radar__item_without_level__is_skipped_not_500`. · **execute**.
- **08-R2** · `/dashboard/summary` still ships two sub-objects nothing reads: `recipes.total` (the TS comment says the hero's "recipe book's empty" nudge reads it — that line was cut 2026-09-04; AboutSettings reads `/usage-stats` now — grep `summary.*recipes|recipes\.total|shopping_lists\.total` in `web_app/src` → `models/dashboard.ts` only) and `shopping_lists.total`. Two `count()` queries per load for nobody — the FU-826 class, second round. · **Exact change:** drop `RecipeSummary`/`ShoppingListSummary` + their TS types; delete `test__dashboard_summary__CreatingRecipe__RecipeTotalIncreases`; update the shape test. · S · **execute**.
- **08-R3** · R-021 — `get_dora_score.py:62 now = datetime.now(timezone.utc)` and `L169 as_of = end.date()`: freshness grades "expired as of **UTC** today" while every other dashboard date is household-local; late evening east of UTC an item expiring today isn't expired yet, and the lagged window's day boundary drifts the same way. · **Exact change:** `as_of = household_today(repo)` for the current window and `household_today - 7` for the lagged one (keep the UTC instant for the event-count windows). · S · **execute**.
- **08-R4** · `get_dora_score._gather_inputs` (L170–175) loads **every** `StockItem` into memory to count two things, and runs twice per request (review finding 25 — still open). · **Exact change:** `repository.get(StockItem).count(EXPIRY_DATE.is_not_null())` and `.count(EXPIRY_DATE.lte(as_of))`; drop the list. The handler's `is_expired_on` inline duplicate goes with it (use the domain helper or delete it — `dora_score.is_expired_on` has no production caller; grep at execution). · S · **execute**.
- **08-R5** · `GetDoraScoreHandler.handle(user_id)` → `_gather_inputs(user_id, …)`: `user_id` is never read (the score is household-wide); the route's `_current_user_id()` (L197–204) is another FU-654 copy that exists only to feed an unused parameter and a log line. · **Exact change:** drop the parameter; log via 02-R12's `current_user_id()`. · S · **execute**.
- **08-R6** · `get_usage_stats.py` bypasses the repository with raw `db.metadata.tables` + `db.session` for six plain counts that `repository.get(X).count()` already does (R-005 repository-routed access; the summary two files over does it the portable way), and its `_total_spend` re-states `/reports/spend-by-store`'s rule as a second SQL copy with a docstring promising they match (R-003). · **Exact change:** counts through the repo; extract `lifetime_spend(repo)` into `shopping_lists/_line_price.py` (beside `line_paid_unit_price`) and call it from both this handler and spend-by-store's total. · S/M · **execute**.
- **08-R7** · R-019 (comment ≠ code), review finding 21 — `DashboardPage.vue:758–760`: "Append any card missing from the stored order … **at its CARD_DEFS position**" but the loop `order.push(def.id)` appends at the **end**. Every user with a saved layout got Kitchen health **last**, not first, when it shipped — the opposite of the 2026-09-08 ordering decision. · **Exact change:** insert at the registry index (`order.splice(idx, 0, def.id)` where `idx` is the position after the nearest preceding known card), and pin it in a spec. · S · **execute**.
- **08-R8** · R-021 — `DashboardPage.vue:1262 todayIso = isoOf(new Date())` (browser) decides the calendar's *today* ring while the cells start at `/alerts/upcoming`'s household-local `start`; `greeting` likewise uses the browser hour (acceptable — the greeting is about the reader's clock). · **Exact change:** `/alerts/upcoming` already carries `start`; mark `isToday` from a server `today` field (add it to the DTO, Chunk 9) rather than the browser. · S · **execute (with Chunk 9's `/alerts/upcoming` pass)**.

#### C2. Redundancy / DRY (R-001, R-003)
- **08-R9** · Three relative-day formatters: `RestockRadarCard.whenLabel` (L128–136: today/yesterday/N days ago/last week/N weeks ago), `helpers/relativeTime.ts` (Nm/Nh/Nd/Nw ago), and `UseItUpCard.whenLabel` (days left — a different sentence, keep). · **Exact change:** `relativeTime(iso, { style: 'coarse' })` in the shared helper; the radar card calls it. · S · **execute**.
- **08-R10** · `useDoraScore.ts` is the third hand-rolled module cache (with `usePantryBeliefs`, `usePlannedDemand` — 07-R6); same `fetchedAt`/`inflight`/`STALE_AFTER_MS`/`refresh` shape, singleton flavour. · **Exact change:** instantiate from 07-R6's `createOverlayCache` (single-value variant) — and delete `invalidateDoraScore` (FU-896: never had a caller; the header describes behaviour that doesn't exist). · S · **execute (resolves FU-896)**.
- **08-R11** · `DashboardCard.to` prop, `.dora-card-clickable` rules and `:deep(.dora-card-action)` — zero consumers app-wide (FU-899; grep `to=` on `DashboardCard` in `pages/` + `components/reports/` → none; `.dora-card-action` → none). · **Exact change:** drop the prop, the `<component :is>` root (plain `<article>`), and the three rule blocks; keep `#action`. · S · **execute (resolves FU-899)**.
- **08-R12** · Hard-coded English weekday labels `DOW_LABELS = ['Sun', …]` (`L1257`) beside `formatRelativeDay`, which is locale-aware (R-056 one regional convention). · **Exact change:** `weekdayShort(date)` from `useDateFormat` (Intl `weekday: 'short'`). · S · **execute**.
- **08-R13** · `BudgetCard.periodWord = period.replace('ly', '')` — string surgery on a closed set (`BudgetPeriod`) that happens to work for weekly/monthly/fortnightly. · **Exact change:** a `Record<BudgetPeriod, string>` map. · S · **execute**.
- **08-R14** · `calendarCells` (L1258–1298) is a pure 40-line transform of the upcoming DTO living in the page. · **Exact change:** `helpers/dashboardCalendar.ts` `buildCalendarCells(upcoming, today, days)` with a vitest (the parity helper already set the precedent). · S · **execute**.

#### C3. Dead code / unused fields / unread endpoints
- **08-R15** · `models/dashboard.ts:1–12, 26–29` comments still say AboutSettings reads the summary and the hero reads `recipes.total` — both false (08-R2). · S · **execute with 08-R2**.
- **08-R16** · `get_dashboard_summary.py:235–241` comment: "Still needed: each upcoming meal-plan entry below carries a per-recipe `missing_count`" is right, but the function computes cookability for the **whole cookbook** to grade ≤7 entries (FU-908 is the identical finding on the plan endpoint). · **Exact change:** when `load_recipe_cookability` gains a `recipe_ids` filter under FU-908, pass the upcoming entries' recipe ids here and in `get_dora_score` (two more callers). · S (given FU-908) · **execute via FU-908**.
- **08-R17** · `dashboardCards.ts` carries ~45 lines of "cards deleted in the 2026-09-04 / 09-08 batches" prose. Valuable once; now it is what `DORA_WORKLOG`/`CHANGELOG` hold. The retired-id list that `dashboardCards.spec.ts` asserts must stay (it is the mechanism). · **Exact change:** keep `RETIRED_CARD_IDS` as an exported constant with one line per id; move the narrative to the worklog. · S · **execute**.

#### C4. Componentisation opportunities (R-001)
- **08-R18** · FU-832 (decided, not started): extract `useCardLayout()` from `DashboardPage.vue:727–943` — `parseLayout`, order/hidden refs, `persistLayout`, `cardAvailable`/`isCardVisible`/`cardRendered`, `moveCard`, the DnD config, `menuCards`, `cardColClasses`/`cardCssOrder` — and the flat card catalogue both the dashboard and Reports read. The page drops to ~900 lines (hero + slot loaders + cells). · M · **execute (it is the FU's own plan; 08-R7 lands inside it so the layout gets a spec)**.
- **08-R19** · The Cards menu block (L55–118) is a self-contained `CardsMenu.vue` (list, drag handle, up/down, toggle) once 08-R18 exposes the composable. · S · **execute with 08-R18**.
- **08-R20** · The hero (L20–146) is the page's only remaining markup after the cards were extracted; a `DashboardHero.vue` is optional. · **waive** (one consumer; the page is the natural owner).

#### C5. Placement / standards (R-002, R-005, R-008, D-rules)
- **08-R21** · D-010 motion literals: `DashboardCard.vue:60–63` (`0.18s ease` ×3), `.dora-cards` `0.4s ease-out`, `.fade-*` `0.25s` (page L1537, L1620), `PantryDonutCard.vue:165` (`0.6s`, `0.15s`), `WhatsComingCard.vue:219` (`0.15s`), `CardLoadError` retry timer `1200` ms — the `--motion-*` tokens exist and the two verdict components use them. · **Exact change:** `var(--motion-fast|--motion-base|--motion-slow)` + `var(--motion-ease)`; the JS timeout reads the same via `getMotionMs('fast')` if a helper exists, else leave. · S · **execute (02-R38 / 06-R37 class)**.
- **08-R22** · FU-671 — `PriceDropsCard.vue:44 text-color="white"` on a `negative` badge. · **Exact change:** `dora-chip--tint-negative`. · S · **execute**.
- **08-R23** · R-069 — `PriceDropsCard.vue:32 class="text-primary"` on the linked-item router-link (brand fill as text) while every other accent string on the page is `--accent-ink`. · **Exact change:** `dora-link-accent` (or the existing accent-ink utility). · S · **execute**.
- **08-R24** · Inline `style="min-width: 300px"` on the Cards menu list (`L56`). · S · **execute** (06-R36 class).
- **08-R25** · R-008 — loggers: `get_dashboard_summary`, `get_restock_radar`, `get_use_it_up`, `get_usage_stats` build `_Logger` per request; `get_dora_score` has a module `_LOGGER`. `get_use_it_up.py:96 date.fromordinal(today.toordinal() + window)` → `today + timedelta(days=window)`. `get_usage_stats._count/_total_spend` import inside methods. · S · **execute** (06-R41 class).
- **08-R26** · `get_dashboard_summary._cook_verdicts` imports `get_or_create_app_setting` + `upcoming_planned_meals` inside the method (L181–182) with no cycle reason stated. · **Exact change:** module-level imports (or a one-line "cycle:" comment if there is one). · S · **execute**.
- **08-R27** · `DoraScoreCard.barClass` bands the server's number at 80/50 client-side. Presentation banding on a server-owned score (A1 names positive = "good scores", warning = "fair") — the "already clean, do not relocate" class. · **waive** (recorded so it isn't re-raised).

#### C6. Naming & idiom
- **08-R28** · `PantryDonutCard.vue` — the file and the `stock_items` card are "My stock" since 2026-09-04; the component name still says Pantry (the comment at L9–12 even explains why "pantry" is the wrong noun). · **Exact change:** rename to `StockDonutCard.vue` (one importer). · S · **execute**.
- **08-R29** · `get_dashboard_summary.py` mixes `_Today`/`_Window`/`_SlotOrder` CapWords locals with `cook_batches`/`upcoming_entries_dto` snake_case in one method. · S · **execute with 08-R2**.

#### C7. Efficiency
- **08-R30** · Per dashboard load the server runs `load_recipe_cookability` **twice** (summary + score) and `upcoming_planned_meals` **twice** (summary `_cook_verdicts` + restock radar via `gather_planned_demand`), and the SPA fires 7–8 requests. Acceptable at household scale; 08-R16 trims the cookability half. · **waive** (note).
- **08-R31** · `get_restock_radar` loads every item + `gather_planned_demand` on each load to mark ≤6 rows *Planned*. · **waive** (≤500 items).

#### C8. Design-level findings — out of Stage-2 scope
- **08-D1** · FU-837 — a short card stretches to its tall row-mate (align-items: stretch + `height: 100%`); design call, three options recorded there.
- **08-D2** · FU-870 — plan coverage cancels out of the trend; accepted trade.
- **08-D3** · FU-868 — money-off / products-off renders never observed; `DORA_VERIFY.md` Dashboard rows cover it.
- **08-D4** · FU-897 — the "already on a list" filter dropped with *Before you shop*; the cart button shows the state instead. Owner call.
- **08-D5** · Feedback D6 (alert-card redesign) was built (Phase 3) and then **cut** on 2026-09-04 with the attention card; the bell + Alerts page carry it. Recorded as superseded, not missing.
- **08-D6** · Feedback L480 (cross-app undo for a dashboard push-expiry) — the dashboard no longer has an expiry action; superseded.

#### C9. Hand-rolled-vs-library verdicts
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| SVG donut + ring (`PantryDonutCard`, `DoraScoreCard`) | charts | ECharts (removed, FU-833) | **keep** | — | `stroke-dasharray` on r=15.915 is the idiom; a11y labels present. |
| `useDragDropList` + tap up/down | reorder | SortableJS / vuedraggable | **keep** | — | Native DnD with a tap fallback is the C13 mandate. |
| `zoneColClasses` parity | layout | CSS grid `auto-fit` | **keep** | — | Order is dynamic and persisted; CSS can't widen "the last of an odd run". Tested. |
| `dashboardMessages` pools + `epochDay` | rotation | — | **keep** | — | Deterministic, gated, tested. |
| three module caches | cache | one factory (07-R6) | **wrap** | S | 08-R10. |
| `parseLayout` JSON narrowing | validation | zod | **keep** | — | Six lines; a schema lib for one field is creep. |

#### C10. Standards drift (R-0NN)
- **R-003** · 08-R6 (spend rule ×2), 08-R9, 08-R10, 08-R12 — fix.
- **R-005** · 08-R6 (raw Core counts) — fix.
- **R-008** · 08-R25, 08-R26, 08-R29 — fix.
- **R-019** · 08-R7 — fix (and the §6 finding 21 that was marked for Chunk 1 and survived).
- **R-021** · 08-R3, 08-R8 — fix.
- **R-032** · all four handlers resolve levels by FK or count by `_stock_level_id` — clean; 08-R1 is the None-guard, not a relationship read.
- **R-056** · 08-R12 — fix.
- **R-057** · 08-R2 (summary fields), 08-R11 (`to` prop) — the inventory the rule asks for, executed.
- **R-002 / D-010** · 08-R21 — fix; **FU-671** 08-R22; **R-069** 08-R23.
- **R-060** · no undeclared tokens found on this surface (the DoraScoreCard sweep landed; `--semantic-info`, `--hero-gradient`, `--elevation-card(-hover)`, `--radius-pill` all defined).
- **FU-654** · 08-R5 — one more copy removed.
- **FU-844** · the `watch(moneyEnabled)` / `watch(productsEnabled)` re-fire guards (L1379–1390) stay until the composable owns it — tracked.

#### C11. Ride-along signals for FU-010 / FU-224
- The hero uses `--brand-primary-soft` fill + `--brand-primary` rule + `--accent-ink` text — the page's cleanest statement of the R-069 split; a reference for FU-224.
- `.dora-cal-cell.is-today` = `--accent-mark` hairline, `.is-selected` = `--brand-primary-soft` fill — two accent families on adjacent cells; check in the dark themes.
- Calendar dots: positive / negative / **info** as a categorical trio (owner fix 2026-09-04) — note the only `--semantic-info` use on the surface.

### E. Proposed follow-ups (orchestrator allocates ids)

- **Execute existing deferred jobs:** **FU-832** (08-R18/19 — `useCardLayout` + catalogue), **FU-896** (08-R10 — delete `invalidateDoraScore`), **FU-899** (08-R11 — drop the consumer-less `to` path).
- Existing FUs this chunk executes against: **FU-654 / 02-R12** (08-R5), **FU-671** (08-R22), **FU-908** (08-R16 — two more callers for the `recipe_ids` filter), **07-R6** (08-R10), **02-R38 / 06-R37** (08-R21), **06-R41** (08-R25).
- Existing FUs referenced, unchanged: FU-837, 870, 868, 897, 898, 871 (08-R7 does **not** rewrite stored JSON; the migration stays optional), 844, 836 (handled).
- No new FUs: every finding here is executable or already tracked.

---

## Chunk 09 — Alerts + Suggestions
*Source: [`CHUNK_09_alerts_suggestions.md`](../05_investigations/finalisation/CHUNK_09_alerts_suggestions.md) · analysed 2026-10-23*

### C. Senior review — Alerts + Suggestions

Verdict key: **execute** · **FU** · **waive** · **conditional**. Sizes S/M/L.

#### C1. Bugs (verified or high-confidence latent)
- **09-R1** · D-006 — `generators.generate_over_budget` (L151–157) bakes `$` into `body` and `reason` five times (`f"Spent ${dto.spent:.2f} of your ${dto.amount:.2f} target…"`) — a EUR/GBP household reads dollars; the buy-verdict fixed exactly this by shipping raw amounts (`VerdictReasonDto.amount_*`). The `payload` already carries `amount/spent/over_by`. · **Exact change:** drop the figures from `body`/`reason` prose (or template them client-side from `payload` through `formatMoney`); `title`'s `period.replace("ly", "")` → a `{weekly: "week", …}` map (08-R13 class). · S · guard: a test asserting no currency symbol in any suggestion string (the verdict's `test__no_reason_string_anywhere__contains_a_currency_symbol` shape). · **execute**.
- **09-R2** · `generate_likely_due` (L209–224) re-implements mean-gap-between-unique-dates — the fourth copy FU-683 D3 counted; `domain/cadence_math.mean_gap_days` is the chokepoint and is already imported by the sibling `pantry_belief`. · **Exact change:** `avg_gap = mean_gap_days(unique_sorted)`; keep the min-samples / max-gap gates. · S · **execute**.
- **09-R3** · `generate_over_budget.primary_action.path = "/settings/preferences"` — that page is **Appearance** (`SettingsShell.vue:124`); the budget lives at `/settings/budget` (`routes.ts:251`). "Review budget" lands the user on the theme picker. · **Exact change:** `/settings/budget`. · S · **execute**.
- **09-R4** · FU-654 — five more `session.get("user_id")` copies in this group: `get_alerts._current_user_id`, `interact_with_alert`, `manage_alert_prefs`, `push_subscriptions`, `suggestions` (plus `get_dora_score` and `get_pantry_beliefs` already counted). · **Exact change:** 02-R12's helper. · S · **execute**.
- **09-R5** · R-003 — the default snooze length is a literal **7** in four places: `AlertRow.vue:88,91` (aria-label + tooltip copy), `alertStore.ts:50`, `alertApiService.ts:28`, and `SnoozeRequest.days = 7` server-side. · **Exact change:** one `DEFAULT_SNOOZE_DAYS` in `models/alert.ts` the three client sites read; copy interpolates it. · S · **execute**.
- **09-R6** · `get_alerts.handle` (L193–194) reads `self.repository.get(AppSetting).all()[0]` — the FU-759 / 06-R15 class (second copy of the install-wide read beside `get_or_create_app_setting`). · S · **execute**.
- **09-R7** · R-031 — two sessions per request: `interact_with_alert.dismiss_all` (L112) and `send_alerts_push._process_user` (L96) construct a fresh `SqlAlchemyRepository()` for `GetAlertsHandler` while mutating through the passed `repository` (the review finding 25 pattern). · **Exact change:** pass `self.repository` / `repository`. · S · **execute**.
- **09-R8** · `push_subscriptions.get_vapid_public_key` (L130–131) returns a hand-built `jsonify({"detail": …}), 404` rather than the app's problem-details `not_found(...)`, so this one 404 has a different shape from every other. · **Exact change:** `not_found("VAPID configuration")` (the SPA only checks the status). · S · **execute**.
- **09-R9** · `send_daily_brief._ledger_row` (L221–225) does `.all(...)` then `rows[0]` where `.one()` exists and is used three lines up in `interact_with_alert._find`. · S · **execute**.

#### C2. Redundancy / DRY (R-001, R-003)
- **09-R10** · `AttentionRulesDialog.cheatRows` (L236–247) is a hand-written truth table of `attentionBand()` with a comment saying it "mirrors" it — the drift shape R-003 forbids, on a help page about the very rule. · **Exact change:** derive the band column by calling `attentionBand({needs_attention, is_essential}, outOfStock)` on eight synthetic rows; the table then cannot disagree with the code. · S · **execute**.
- **09-R11** · Two shopping-day nudges and two reconcile nudges are generated twice — once as alerts (`get_alerts._shopping_day_alerts`, `_meal_reconcile_overdue_alerts`) and once as suggestions (`generate_reconcile_meals_pending` with the same `reconcile_overdue_signal`). The reconcile pair is the same fact in two inboxes with two dismiss ledgers (one per user, one household-wide). · **Exact change:** owner call — drop the suggestion twin (the alert kind has the per-user prefs and the bell) or the alert twin; recommend dropping `KIND_RECONCILE_MEALS_PENDING` since every other suggestion is something alerts don't say. · S · **conditional** (execute if the owner agrees the alert is the home; else record).
- **09-R12** · `send_alerts_push._subscriptions_by_user` and `send_daily_brief._subscriptions_by_user` are byte-identical (L79–86 vs L126–133); `_NO_ROW` sentinel + `_interactions_by_key` are the push job's private copies of what `interact_with_alert.AlertInteractionHandler._find` does. · **Exact change:** a tiny `alerts/_ledger.py` with `subscriptions_by_user(repo)` and `interactions_by_key(repo, user_id)`; both jobs import it. · S · **execute**.
- **09-R13** · `NotificationsSettings.visiblePrefs` (L396–400) decides client-side which kinds are *relevant* (`meal_reconcile_overdue` only without auto-drain; `price_drop` only with money) while `/alerts/prefs` returns all eight regardless and the evaluator applies its own gates. · **Exact change:** `AlertPrefDto` gains `available: bool` computed server-side from the same gates the evaluator uses; the page filters on it. · S · **execute**.

#### C3. Dead code / unused fields / unread endpoints
- **09-R14** · Stale comments: `get_alerts.AlertDto.kind` says "One of the six" (there are eight; `alert_kinds.py` says so); `alertApiService.ts:41` "Enable/disable a kind + override its tier" (tier override cut at Step-0 Q3); `suggestions.py` module docstring lists `DELETE /api/suggestions/suppression` while the route is `POST /unsuppress` (L275); `alertStore.ts:12` "Dora's 'what needs my attention?' intent" (check the assistant tool still reads the store — Chunk 11). · S · **execute**.
- **09-R15** · `AlertsDto.high_count / medium_count / low_count` — the SPA reads `high_count` and `medium_count` for the bell colour only; `low_count` and `fyi_count` have no reader (grep `low_count|fyi_count` in `web_app/src` → `models/alert.ts` + the store's `EMPTY`). · **Exact change:** drop `low_count` + `fyi_count` from the DTO + TS (keep `actionable_count`, `snoozed_count`); update `test__alerts__actionable_count_equals_high_plus_medium_in_items` if it reads them. · S · **execute**.
- **09-R16** · `suggestionsApiService.SuggestionKind` lists four kinds; the server emits six (`pantry_check`, `reconcile_meals_pending` missing) — the `string & {}` escape hatch hides it. · **Exact change:** add the two. · S · **execute**.
- **09-R17** · `AlertKindMeta.icon` is read only through `iconFor` and `ALERT_KIND_META[kind]?.icon`; `AlertKindAvatar` is the single consumer — fine. `kindTheme` fallback `''` renders an empty toggle label for an unknown kind in Settings; the bell degrades to a generic icon. · **Exact change:** fall back to the raw kind string in `kindLabel`. · S · **execute**.

#### C4. Componentisation opportunities (R-001)
- **09-R18** · `DoraChat.vue:106–165` inlines the suggestion card (title · body · Why? · three buttons) — the one place suggestions render, but 60 lines of markup inside a 700+-line chat component. · **Exact change:** `SuggestionCard.vue` with `accept/snooze/dismiss` emits; `DoraChat` keeps the store wiring. · S · **execute** (Chunk 11 may fold it into its chat pass; record here, execute there).
- **09-R19** · `AdminSystemAlertsSettings.vue` is a 130-line page for **one** numeric field. With `default_days_until_stocktake_alert` gone, the page's title ("Alert thresholds", plural) and description ("…and the location heatmap for everyone; each account's own on/off and **priority preferences** layer on top") describe things that no longer exist (tier override cut; no heatmap). · **Exact change:** rename to *Expiring-soon window*, fix the description; or fold the one field into the Admin → System → Stock page. · S · **execute** (copy) / **conditional** (fold — Chunk 13's call).

#### C5. Placement / standards (R-002, R-005, R-008, D-rules)
- **09-R20** · R-002 / 02-R37 — `AttentionRulesDialog.vue:258–259` uses Quasar `--q-negative` for the sample outline; the rest of the dialog is on tokens. `font-size: 0.85rem`, `padding: 8px 10px` literals (D-003). · S · **execute**.
- **09-R21** · D-003 — `NotificationsSettings.vue:486–488` `.settings-page__note { font-size: 0.8125rem; margin-top: 4px }`; `AdminSystemAlertsSettings.vue:128 margin: 8px 0`. · S · **execute** (Chunk 13 sweep).
- **09-R22** · R-008 — loggers: `get_alerts`, `act_on_alert`, `get_upcoming` build `_Logger` per request; `interact_with_alert`, `manage_alert_prefs`, `push_subscriptions` call `logging.getLogger(__name__)` inline; the two jobs use a local `log`. · S · **execute** (06-R41 class).
- **09-R23** · `prune_expired_snoozes` uses raw Core `delete(table)` via `db.metadata.tables` — justified (bulk delete; the repo has no bulk-delete port) and documented. · **waive**.
- **09-R24** · `AlertKindAvatar` `text-color="white"` on `severity-critical/-medium/-low` fills — FU-671's class; the severity tokens are "critical" ink-strength by name but D-002 wants a check in the pale themes. · **Exact change:** verify contrast; if any fails, `--text-on-severity-*` tokens. · S · **conditional** (measure; FU-671 sweep).
- **09-R25** · `get_alerts._no_planned_meals_alerts` formats a date range server-side (`strftime('%a %d %b')`, L403–404) — the 06-D1 / 03-R8 class (R-056). · **FU** (one cross-surface decision, already proposed in Chunk 6 E).

#### C6. Naming & idiom
- **09-R26** · `generate_use_soon.reason` says "within the 3-day rescue horizon" with a literal 3 beside `_USE_SOON_HORIZON_DAYS = 3` (R-019). · S · **execute**.
- **09-R27** · `get_alerts.py` module docstring says "(C-9.1) … `read` stamped" and "read / snooze / dismiss" (L13–20) though read state was cut 2026-10-15. · S · **execute with 09-R14**.

#### C7. Efficiency
- **09-R28** · Every bell poll (60 s per visible tab) runs the full evaluator: every stock item with its level, every open list, next week's entries, the reconcile queue, the user's watches + products, the user's interactions and prefs, plus a `User` read for the discard window. Household scale makes this fine, and the visibility gate stops background cost. · **waive** (note; if it ever matters, an `ETag` on `/alerts` is the cheap fix).
- **09-R29** · `send_alerts_push._process_user` re-evaluates alerts per subscribed user every hour — intended. · **waive**.
- **09-R30** · `generate_pantry_check` loads every open list's lines + a week of plan entries + the belief gather per suggestions call; `generate_likely_due` loads every archived list's lines. Suggestions refresh on bubble mount and on chat close only. · **waive** (bounded; note).

#### C8. Design-level findings — out of Stage-2 scope
- **09-D1** · `DoraSuggestionSuppression` has no `user_id`: a dismiss or snooze by one household member hides the suggestion for all, while alert interactions are per user. The entity docstring says "a user's negative decision" but models a household one. Owner call: per-user (add the column, same shape as `AlertInteraction`) or keep household-wide and say so in the copy (B2-8 states the current behaviour). → **FU**.
- **09-D2** · Alerts and suggestions are two inboxes with overlapping kinds (09-R11) and two different dismiss semantics (episode vs condition). Step-0 cut the digest and the Alerts page; it did not ask whether the suggestions inbox survives as a separate concept now that the bell carries nudges. Record for the owner; no change proposed.
- **09-D3** · FU-702 / FU-701 — the *Expiring soon* chip on the stock page reads the pref-filtered `attention_kinds`, so a user who mutes the kind loses the filter; and the chip's label covers already-expired items. Both wait on the owner's wording call.
- **09-D4** · FU-700 — stocktake copy in `AttentionRulesDialog` ungated on the install switch.
- **09-D5** · FU-916 — `AlertInteraction` rows for finished episodes (and the daily-brief ledger keys) are never pruned; a nightly job beside `prune_expired_snoozes` is the natural home when it matters.
- **09-D6** · FU-917 — `PriceAlert.last_fired_at` dead, `threshold_unit_price` misnamed (Chunk 10 owns the entity).
- **09-D7** · FU-627 — deals-email section ignores the install-wide `deals_email` admin flag.

#### C9. Hand-rolled-vs-library verdicts
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| `pywebpush` wrapper (`push_sender.py`) | web push | — | **keep** | — | Already a library; dry-run mode is the right local story. |
| `push-sw.js` hand-written SW | service worker | Workbox | **keep** | — | Push-only, 90 lines, coexists with the PWA SW; Workbox adds nothing here. |
| APScheduler `BackgroundScheduler` in-process | scheduling | Celery / cron | **keep** | — | Single-worker constraint documented; externalising is the SaaS tail. |
| Derived alerts (no stored alert rows) + interaction ledger | event model | a notifications table | **keep** | — | The proposal's central decision; it is what makes "one rule" possible. |
| `_select_for_display` fairness | ranking | — | **keep** | — | Pure, tested (FU-593). |
| `urlBase64ToUint8Array` | base64url | a lib | **keep** | — | 8 lines, the canonical snippet. |

#### C10. Standards drift (R-0NN)
- **R-003** · 09-R2, 09-R5, 09-R6, 09-R10, 09-R12, 09-R13 — fix; 09-R11 conditional.
- **R-008** · 09-R9, 09-R22 — fix.
- **R-019** · 09-R14, 09-R26, 09-R27 — fix.
- **R-021** · all evaluators anchor on `household_today`; the jobs self-gate on the household clock — clean.
- **R-031** · 09-R7 — fix.
- **R-032 / FU-684** · `get_alerts` reads `item.stock_level` through `is_essential_low` with an include (L181–184, L527) — the same exposure `stock_attention`/`get_stock_items` carry; 07-R2's `levels_by_item` pattern applies when FU-684 executes. → tracked.
- **R-056 / D-006** · 09-R1 — fix; 09-R25 → FU.
- **R-002 / D-003** · 09-R20, 09-R21 — fix; **FU-671** 09-R24 conditional.
- **FU-654** · 09-R4 — five more copies.
- **R-057** · 09-R15, 09-R16 — inventory executed.
- **R-029** (hide when off) · price-watch toggle and section follow `moneyEnabled`; push toggle disabled-with-reason rather than hidden (owner precedent) — clean.

#### C11. Ride-along signals for FU-010 / FU-224
- Bell badge: `color-mix(--semantic-negative 65%, black)` to hold white text ≥ 6:1 in dark themes — a bespoke darkening with no token; FU-224 should decide whether a `--semantic-negative-strong` token exists for this.
- `AlertKindAvatar` severity circles with white glyphs — the one place `severity-*` is used as a fill under white (09-R24).
- Dora bubble suggestion badge `negative`/`primary` palette names.

### E. Proposed follow-ups (orchestrator allocates ids)

- type=finding · *Suggestion suppression is household-wide while alert interactions are per user* (09-D1) — owner decision; S if per-user (add `user_id`, same shape as `AlertInteraction`).
- type=finding · *Reconcile nudge is generated as both an alert kind and a suggestion* (09-R11 / 09-D2) — owner decision on which inbox owns nudges; execute the deletion once decided.
- Existing FUs this chunk executes against: **FU-654 / 02-R12** (09-R4), **FU-683 D3** (09-R2), **FU-759 / 06-R15** (09-R6), **06-R41** (09-R22), **FU-671** (09-R24, conditional).
- Existing FUs referenced, unchanged: FU-916, 917, 702, 701, 700, 627, 624, 684.
- Cross-surface FU already proposed (Chunk 6 E, server-formatted dates in prose): add `get_alerts._no_planned_meals_alerts` (09-R25) to its site list.

---

## Chunk 10 — Products / Price History / Deals
*Source: [`CHUNK_10_products_history_deals.md`](../05_investigations/finalisation/CHUNK_10_products_history_deals.md) · analysed 2026-10-23*

### C. Senior review — Products / History / Deals

Finding ids `10-Rk`. Verdicts: **execute** (Stage 2, test-guarded) · **FU** (needs an owner call or is cross-surface) · **waive** (reasoned) · **conditional**.

#### C1. Bugs (verified or high-confidence latent)
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 10-R1 | `deals/send_deals_email.py:106` | `spa_deep_link("/products")` — the SPA has no `/products` route (`routes.ts:89–90` define `price-history` and `my-products`). Every weekly mail's "See all deals" button lands on the catch-all. | `spa_deep_link("/my-products")`; pin with a test that renders the HTML and asserts the href. | execute |
| 10-R2 | `pages/PriceHistoryPage.vue:159–166` | "currently N% above [all-time low]" carries an InfoTip explaining *your usual price from prices you've logged* — but the figure is offers-based (`atl_by_product` reads `ProductHistoricOffer`). Already named in FU-708 ("mis-parented tooltip"). | Delete the tip or reword: "the lowest advertised price Dora has seen for this product". | execute (FU-708) |
| 10-R9 | `services/api/productApiService.ts:13`; consumers `MyProductsPage.vue:602`, `PriceHistoryPage.vue:441`, `ShoppingListDetail.vue:2721` | `getAllAsync` hits `/products` with no `limit` → server `DEFAULT_LIMIT = 50`. On an install with 51+ saved products, **My Products silently shows 50**, the footer says "Shown 50", the history picker can't find product 51, and the list's linked lookup misses. FU-668 called this trap for pickers; this is the list page itself. | `getAllAsync` requests `?limit=500` (`MAX_LIMIT`) and the store surfaces `page.total` so the footer can say "Shown N of M"; a real paginated catalogue page is an FU if a household ever exceeds 500. Also retire the dead `slice(0,100)` in `PriceHistoryPage.vue:339,345`. | execute |
| 10-R30 | `MyProductsPage.vue:302–314, 423–428, 1166–1172` | Empty-state and orphans copy say "Use Product Search"; when no URL is configured `openProductSearch` routes **every** user to `/settings/admin/system/ingestion` — an admin path a member can't use. Hide-when-off (R-029). | Read `useProductSearchUrl().configured` + `isAdmin`: configured → CTA; unconfigured admin → "Set up Product Search"; unconfigured member → copy "Ask your admin to set up Product Search" and no button. Empty state also mentions **Add custom**. | execute |
| 10-R35 | `components/StoreLogo.vue:104–111, 12–19` | `imageUrl` = `${resolveBaseURL()}/stores/<id>/image` bound into `<img :src>` — the exact R-045 violation `ProductThumb.vue`'s header documents (unauthenticated by construction; silent broken image on a split `app.`/`api.` host and in the Capacitor shell). No carve-out comment. Renders on My Products, Price history, shopping lists, settings. | Fetch via `AxiosHttpClient.getBlob` + `objectUrlFor`, as `ProductThumb` does — ideally by extracting one `AuthedImage` primitive both use (10-R45). Keep the hash-swatch fallback. | execute |
| 10-R5 | `products/update_product.py:96–110` | The PATCH price path appends a `ProductHistoricOffer` by hand: no `source`, no "did the price actually change" check, no dedupe — while `create_product.py:110` routes the same event through the shared `apply_offer_to_product` (`source="manual"`). Two offer-append rules (R-003); the module FIXME in `product_historic_offer.py` describes the race this path had. | `apply_offer_to_product(repo, product, price_now=…, price_was=…, observed_at=now, source="manual")`; test: one historic row with `source == "manual"`, no row when the price is unchanged. | execute |
| 10-R43 | `deals/deal_quality.py:178–185` | The 90-day horizon is built as **UTC midnight of the household date** (`datetime.combine(today - 90d, min.time(), tzinfo=timezone.utc)`), plus a local `_as_utc` shim for naive rows. Same R-021 slip as 07-R1 / 08-R3. | `tzinfo=household_timezone(repo)` (or compare dates in household-local); drop `_as_utc` once rows are known-aware. | execute |
| 10-R4 | `PriceHistoryPage.vue:435–448` | `onMounted` reassigns `selectedIds` (fires the `watch` → `refreshSeries()`) and then calls `refreshSeries()` again — double fetch on deep-link. | Drop the explicit call (the watch covers it) or make the watch `immediate` and remove both explicit calls. | execute |

#### C2. Redundancy / DRY (R-001, R-003)
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 10-R6 | `price_history/price_history.py:179–185` | Inline `deal_pct = max(0, int(round((1 - now/was)*100)))` duplicates `domain/product_offer.discount_percent` (and rounds differently at the boundary). | `discount_percent(now, was)`. | execute |
| 10-R12 | `reports/reports.py:905–925`, `deals/deal_quality.py:146–158` | Both re-implement the `StockItemProduct` join read (+ `reports` re-implements `stamp_has_image`) "because no shared DTO". Full count of raw `tables["StockItemProduct"]` readers is **11**: `product_links.py` (the shared one), `get_link_status.py:217` (FU-923), `reports.py:910`, `deal_quality.py:153`, `barcodes.py:447`, `recipe_cost.py:164`, `get_buy_verdict.py:885`, `get_stock_items.py:185`, `your_prices.py:290/536/681`. | Make `stamp_has_image(repo, ids) -> dict[UUID,bool]` and `linked_stock_items` the only two readers in this chunk's packages (reports + deal_quality); widen FU-923 to list the other 7 for the ingestion/stock chunks. Also removes the two function-local `from dora_api.app import db` imports (R-008). | execute (this chunk) + FU-923 widened |
| 10-R15 | `price_history.py:40` vs `reports.py:734` | `_RANGE_DAYS` defined twice (reports' is a superset: adds 2y/5y). | One `features/_ranges.py` (`RANGE_DAYS`, `range_cutoff`), imported by both. | execute |
| 10-R23 | `MyProductsPage.vue:656–660`, `ProductCard.vue:251–255`, `chips/DiscountChip.vue:59–66`, `StockItemDetailPage.vue:898`, `helpers/scrapedProductOfferLogic.ts` (orphan, FU-838) | "On special" = `was > now` is written four times client-side while the one helper that already states it has no consumer. | `helpers/offerLogic.ts` exporting `isOnSpecial(offer)` + `discountPercent(offer)` (rename of the orphan file); `DiscountChip`, `ProductCard.hasDiscount`, `MyProductsPage.onSpecial`, the detail page use it. Server rule stays `domain/product_offer.py` (accepted Type-C display carve-out, now with one client copy instead of five). | execute |
| 10-R20 | `LogPriceSheet.vue:185–196, 212–218`, `StockItemRowPriceButton.vue:70–86, 88–94`, `PriceEntry.vue:155–162` | Both entry points fetch prefill by downloading the **whole** stock-item detail (`getDetailAsync` → `price_entry_prefill`, 06-R10's sub-resource case), both hold a `storesList` computed, and the submit payload type is declared inline three times. | Export `PriceEntrySubmission` from `PriceEntry.vue`; both callers use `GET /stock-items/<id>/price-entry-prefill` (06-R10) and the exported type. | execute (with 06-R10) |
| 10-R22 | `CustomProductDialog.vue:219–224, 237–240` vs `ProductPackCountDialog.vue:85–91` | Pack-count parsing/validation written twice with two different messages. | `helpers/packCount.ts::parsePackCount(raw): number \| null \| undefined` + one message constant. | execute |
| 10-R25 | `create_product.py:88–95` | Loads every `Store` and matches `name.strip().lower()` in Python — the same rule `CreateStoreHandler` uses for duplicate detection. | `features/stores/find_store_by_name(repo, name)` used by both. | execute |
| 10-R41 | `deals/deals_digest.py:56–101` | `format_money` claims to be "the only server-side money formatting in the app" — 09-R1 found `suggestions/generate_over_budget` hard-coding `$` ×5. | Lift `format_money` + `_CURRENCY_SYMBOLS` to `infrastructure/money.py`; 09-R1 consumes it. | execute (cross-chunk with 09-R1) |
| 10-R42 | `send_deals_email.py:226–244` | `_ledger_row` = `.all()` → `rows[0]`; the alerts chunk proposed `alerts/_ledger.py` helpers for exactly this `AlertInteraction` read (09-R12) and the `.one()` idiom (09-R9). | Use the shared ledger helper. | execute (with 09-R12) |
| 10-R40 | `PriceHistoryPage.vue:212–227, 316–319, 402–421` vs `components/products/ProductPriceWatchDialog.vue` | Three ways to manage one watch: the per-card inline `MoneyInput` + "Set alert" (PH3's "squished card"), the "Manage alerts" dialog (list/remove only — FU-708), and the My Products watch dialog (set/change/remove, refreshes the bell). | Reuse `ProductPriceWatchDialog` from the comparison cards (button "Watch this price" / "Change watch") and from the Manage-alerts rows; delete `alertInputs` + `onSetAlert`. Fixes PH3 + the FU-708 "cannot create" half in one move. | execute (FU-708) |
| 10-R21 | `components/dora/PriceEntry.vue:35–43` | Price field is a raw `q-input type="number" :prefix` while `MoneyInput` (symbol prefix, 2dp on blur, `inputmode`) exists and is used by the three product dialogs. | `MoneyInput` — also lands FU-704's keypad point. | execute (FU-704) |

#### C3. Dead code / unused fields / unread endpoints
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 10-R19 | `stores/productStore.ts:35–39` | `createProductAsync` / `updateProductAsync` have **no consumers** (grep); `MyProductsPage` mutates through `productApi` directly and then re-runs `loadAll()` — five parallel refetches (products, stock items, levels, lists, watches) after every single toggle, link, photo or delete. | Mutations go through the store (which refreshes `products` only); link/unlink additionally refresh `stockItemStore`; `loadAll` on mount only. Resolves the dead exports by giving them their callers (R-074). | execute |
| 10-R38a | `productApiService.ts:36–37`, `products/get_products.py:187–203` | FU-838: `getBestDealsAsync` + `GET /products/best-deals` have no SPA consumer. **`GetBestDealsHandler` itself is live** (the deals email pool). | Delete the route + client method, keep the handler; `scrapedProductOfferLogic` survives as the renamed shared helper (10-R23). Resolve FU-838. | execute |
| 10-R39 | `price_history.py:270, 292, 312`; `domain/entities/price_alert.py:22` | `last_fired_at` is written only to `None` on re-save and read into a DTO nobody renders (FU-917). | Execute FU-917 as written: drop the column (migration) + DTO field; the episode key does the job. The `threshold_unit_price` → pack-price rename is FU-911's call. | execute (FU-917) |
| 10-R49 | `MyProductsPage.vue:595–596`, `PriceHistoryPage.vue:293–295, 438–440` | Comments claim "a save on the product-search surface (which writes through `productStore.createProductAsync`) is visible here" — there is no in-app search surface (FU-186) and nothing calls that method. | Rewrite to the true reason (one store, lazy hydration) — R-019. | execute |
| 10-R26 | `domain/entities/product_historic_offer.py:7–14`, `product_offer.py:12` | Module FIXME (profanity, a commit hash, "I can't be assed") describing the race 10-R5 fixes; a `TODO: Presentation only…` that is long since done elsewhere. | Replace with a two-line factual note on why historic offers are a separate table; delete the TODO. | execute |
| 10-R37 | `PriceHistoryPage.vue:339,345` | `.slice(0,100)` on a list that is at most 50 rows (10-R9). | Remove with 10-R9. | execute |
| 10-R10 | `ProductCard.vue:59,64`, `ProductRow.vue:67` | `formatMoney(product.price_now ?? 0)` — `price_now` is non-null in the DTO and the type; the guard renders "$0.00" if it ever fired. | Drop `?? 0` (with 10-R7). | execute |
| 10-R46 | `tests/e2e/dora_api/test_product_router.py:268` | `test__create_product__MerchantAlreadyExists__MerchantIsReused` — Merchant was renamed Store in Phase E. | Rename `StoreAlreadyExists__StoreIsReused`. | execute |

#### C4. Componentisation opportunities (R-001)
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 10-R45 | `ProductThumb.vue`, `StoreLogo.vue` (10-R35), the stock-item / recipe image routes (chunks 5/6/1), the QR-label fetch | Each authed image fetch is hand-rolled per surface; `ProductThumb` is the best copy (in-flight guard, glyph fallback). | One `AuthedImage.vue` (props: `path`, `hasImage`, `alt`, fallback slot) that `ProductThumb`/`StoreLogo` wrap. | FU (cross-surface; execute `StoreLogo` via 10-R35 first) |
| 10-R28 | `ProductRow.vue:126–134` | Row click → `window.open(web_url)` on a `q-card` — not a link: no keyboard/middle-click/status-bar preview (D-005); `ProductCard` already does it properly with a real `<a target=_blank rel=noopener>`. | Wrap the identity block in the same `<a>` the card uses (shared `ProductStoreLink` slot or copy the `topHalfAttrs` computed into a tiny composable). | execute |

#### C5. Placement / layering (R-003, R-005)
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 10-R17 | `price_history/price_history.py` (whole module) | Every read is raw `db.metadata.tables[…]` + `db.session.execute`, and `delete_price_alert` commits with `db.session.commit()` — the only module in the chunk that bypasses the repository ports and `save_changes` (R-005, R-031). Core-SQL is Postgres-portable, so not a correctness bug; it is the pattern R-005 exists to stop spreading. | Execute the small part: delete via `repo.remove(alert)` + `save_changes()`, create/list via `repo.get(PriceAlert)`. The multi-table series read stays core-SQL with an inline `# R-005 carve-out: aggregate over 4 tables` comment. | execute (small) + comment |
| 10-R16 | `price_history.py:69–76` (+3 call sites) | Local `_current_user_id()` reading `session.get("user_id")` — another FU-654 copy. | `infrastructure/auth_helpers.current_user_id()`. | execute (FU-654 sweep) |
| 10-R3 | `price_history.py` (no gate); `MyProductsPage.vue:615–617` comment | The comment says price watches are "money-gated on the server like every price surface" — **no** `money_features_enabled` check exists in `products/`, `price_history/` or `deals/`. R-058 says a dollar surface refuses at the endpoint. The products overlay is data-presence gated, not money gated, so whether a *pack-price threshold* counts as a money surface is an owner call. | Minimum: correct the comment. Recommended: gate `/price-history/alerts*` on `money_features_enabled` (403 `MONEY_DISABLED_DETAIL`) and hide the watch menu item when money is off. | conditional (owner) — comment fix executes regardless |
| 10-R27 | `products/get_price_history.py` (per-product `/products/<id>/price-history`) | One consumer: `StockItemDetailPage.vue:2037` sparkline loop — N sequential requests, one per linked product, for the same data `/price-history?product_ids=a,b,c` returns in one call (cap 5). | Detail page calls the multi-product endpoint once (≤5 linked products is the realistic case; fall back per-product beyond 5); then retire the per-product route or keep it as the raw-points contract. Belongs with 06-R10's sub-resource rework. | conditional (with chunk 6) |
| 10-R38 | `PriceHistoryPage.vue:374–380` | `aboveLowPct` computed client-side from two server numbers while the sibling `deal_pct` is server-computed. | Display math over two shipped facts — the "already clean, do not relocate" category. Note the asymmetry; leave. | waive |

#### C6. Naming & idiom
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 10-R7 | `models/product.ts` vs `ProductDto` | `brand`, `merchant_stockcode`, `web_url` typed `string` but nullable server-side (`str \| None`); `store_id?` optional but always stamped; `pack_count` correct. R-057 contract drift — the templates already guard with `v-if="product.brand"`. | `string \| null` ×3, `store_id: string`. | execute |
| 10-R24 | `get_products.py:66` | `bool(getattr(product, "is_custom", False))` on a declared dataclass field. | `product.is_custom`. | execute |
| 10-R11 | `PriceHistoryPage.vue:316–319` | `alertInputs` declaration sits at column 0 inside an indented `<script setup>` (R-008). Moot once 10-R40 deletes it; otherwise re-indent. | — | execute |
| 10-R8 | `CustomProductDialog.vue:217` | `splitSize` upper-cases the unit (`'KG'`, `'ML'`); server `find_unit` lower-cases so costing resolves, but the stored `size_unit` casing differs from every ingested row (`kg`, `g`, `ml`). | Store the canonical key from `UNIT_TABLE` (lower-case) and validate against it client-side so an unknown unit is rejected at the form. | execute |
| 10-R32 | `MyProductsPage.vue:443` | Raw `name="inventory_2"` — `ICONS.inventory_2` exists (`ProductCard.vue:176`). | Use the registry. | execute |

#### C7. Efficiency
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 10-R13 | `get_products.py:150–157` (`GetBestDealsHandler`), `reports.py:837–843` (`PriceDropsHandler`), `deal_quality.py:169–173` | Each loads **every** `Product` with offers into Python to rank/scan — the 06-R9 / 08-R4 shape. Fine at hundreds; wrong shape at thousands. Needs a repo capability to filter/order on a related entity's columns, or a core-SQL ranked query. | Ranked core-SQL query for best-deals (`price_now < price_was`, ordered by `(was-now)/was`) with the entity hydrate on the top-N ids only. | FU (opportunistic — when the repo gains related-field filters, or a household passes ~500 products) |
| 10-R14 | `price_history.py:108–128` | Historic rows fetched twice per request (ranged + all-time for ATL). | One unranged query; derive the ranged series in Python. | execute |
| 10-R31 | `MyProductsPage.vue:1153–1164`, `LogPriceSheet.vue:146–151, 181` | `stockLevels.find` per rendered orphan row (twice) and inside a sort comparator. | `levelsById` Map (the level store likely has one — chunk 5). | execute |
| 10-R47 | `MyProductsPage.vue:881–1019` | Bulk unlink / stop-tracking / delete loop N sequential requests with one catch; partial failure is reported honestly ("Could not delete everything.") and `loadAll` reconciles. | A bulk endpoint is a design call; today's shape is honest. | waive |

#### C8. Design-level findings — out of Stage-2 scope
| Id | Finding | Recommendation |
|---|---|---|
| 10-D1 | Product-axis fate (`/price-history` as a page vs sheet from My Products; PH10, assessment D1) — **FU-703 resolved** (RESOLVED ledger L338). Both surfaces kept; `/price-history` still has no nav entry and is reached only via a product's ⋮ menu (PH1 "hidden away"). | Record the FU-703 decision in H13; if "hidden" still bites, the cheapest fix is a "Price history" link in the My Products toolbar. Owner call. |
| 10-D2 | Watch thresholds are pack prices named `threshold_unit_price` and the `unit_price` key on the product series is a pack price (FU-911). Works; the vocabulary lies. | Resolve FU-911 together with FU-917's column drop — one migration. |
| 10-D3 | `stockItemsMissingProducts` (`MyProductsPage.vue:1144–1151`) counts **every** stock item without a tracked linked product, so the attention glow fires permanently on any install that uses products for a few items ("Stock items without products (214)"). The MP-18 glow was asked for; the predicate makes it wallpaper. | Owner call on what deserves attention: essentials only? items with a preferred buy? items added in the last N days? Or drop the glow and keep the count. |
| 10-D4 | "Stop tracking prices" / "Track prices" is offered on **custom** products, which nothing refreshes — `is_active` on a custom product only affects deals ranking/email. | Relabel for custom ("Hide from deals") or hide the item (R-029). Small; owner wording. |
| 10-D5 | Three alert surfaces for one watch (10-R40) is the structural version of PH8's ask for one place; after 10-R40 the page's cards and the bell both point at the same dialog. | None beyond 10-R40. |

#### C9. Hand-rolled-vs-library verdicts
| Surface | Hand-rolled | Verdict |
|---|---|---|
| `PriceHistoryChart.vue` (566 lines, SVG, crosshair, legend, baseline) | Yes | **keep** — already the one chart for three callers (FU-833), spec-pinned; a chart library would bring 100 KB for one SVG. Touch support is FU-705. |
| `TrendSparkline.vue` | Yes (40 lines) | **keep** — but read tokens via `var()` in `style`, not `getComputedStyle` (10-R36). |
| `deals_digest.format_money` | Yes (flat symbol table) | **keep** — documented; one email's worth of prices. Lift to `infrastructure/money.py` (10-R41). |
| `CustomProductDialog.splitSize` regex | Yes | **keep** — tiny; validate against `UNIT_TABLE` (10-R8). |
| `StoreLogo` hash-swatch | Yes | **keep** — deterministic, zero logos shipped by design. |

#### C10. Standards drift (R-0NN)
| Id | Rule | Where | Verdict |
|---|---|---|---|
| 10-R33 | R-069 / FU-671 `text-color="white"` | `PriceHistoryPage.vue:33,191`, `ProductCard.vue:92`, `DiscountChip.vue:10`; raw `color: white` at `ProductCard.vue:367` | execute (FU-671 sweep: `--text-on-accent`) |
| 10-R34 | D-010 motion tokens; D-017 radii | `ProductCard.vue:292`, `ProductRow.vue:140` `120ms ease`; `ProductRow.vue:139` `var(--radius-sm, 8px)` literal fallback | execute (`var(--motion-fast)`, drop the fallback) |
| 10-R36 | R-002 tokens-only | `TrendSparkline.vue:34–45` reads `--semantic-positive/negative` via `getComputedStyle` with hard-coded `hsl()` fallbacks; SVG accepts `style="stroke: var(--semantic-positive)"` directly | execute |
| 10-R16 | FU-654 `session.get("user_id")` | `price_history.py:70` | execute (sweep) |
| 10-R17 | R-005 / R-031 | `price_history.py` raw session + `commit()` | execute small + carve-out comment |
| 10-R43 | R-021 household timezone | `deal_quality.py:178–185` | execute |
| 10-R12/10-R44 | R-008 (function-local imports "to avoid cycles") | `deal_quality.py:150–151`, `reports.py:905` | execute with 10-R12 |
| 10-R26 | R-019 comments ≠ code / hygiene | `product_historic_offer.py` FIXME | execute |
| 10-R49 | R-019 | stale store comments | execute |
| — | R-045 | `StoreLogo.vue` (10-R35) | execute |
| — | R-056 dates in prose | None in this chunk: `PriceEntry` uses `formatRelativeDay`, the series ships ISO for the chart axis (a chart, not prose), the email formats no dates. | clean |

#### C11. Ride-along signals for FU-010 / FU-224 (theme / colour)
- `DiscountChip` green + white text is the one `% off` (FU-885) — white → `--text-on-accent` (10-R33).
- `ProductCard__oos` red banner uses `--semantic-negative` + raw white (10-R33).
- `PriceHistoryPage` "above usual" chip `color="warning" text-color="white"` — amber on white is the D-002 contrast case; `--text-on-accent` and check.
- `product-card--inactive` / `product-row--inactive` = `opacity: 0.6` — fine (D-001 grey = absent/unknown).
- Chart tooltip is token-based on a static read (PH7 stays FU-708 "confirm in browser").


### E. Proposed follow-ups (orchestrator allocates ids)

| # | Title | Type | Resolution point | Source |
|---|---|---|---|---|
| E1 | Widen FU-923 to all 11 raw `StockItemProduct` readers (7 outside this chunk) | leftover | with chunks 5/6/16 Stage 2 | 10-R12 |
| E2 | `AuthedImage` primitive for every authenticated image route (products, stores, stock items, recipes, QR) | leftover | after 10-R35 lands | 10-R45 |
| E3 | Ranked core-SQL for best-deals / price-drops / deal-quality instead of load-all-and-rank | finding | opportunistic — when the repo gains related-field filters or a household nears 500 products | 10-R13 |
| E4 | Decide: are price watches a money surface (R-058 gate on `/price-history/alerts*`)? | decision | now (owner) | 10-R3 |
| E5 | Decide the "Stock items without products" attention predicate (glow fires on every install) | decision | now (owner) | 10-D3 |
| E6 | Relabel/hide "Track prices" for custom products | decision (wording) | now (owner, one line) | 10-D4 |
| E7 | Detail-page sparklines: one multi-product history call instead of N per-product calls; fate of `/products/<id>/price-history` | leftover | with 06-R10 | 10-R27 |
| E8 | True paginated catalogue page if a household exceeds `MAX_LIMIT` (500) | finding | when triggered | 10-R9 |
| E9 | Record the FU-703 decision in help + consider a "Price history" toolbar link on My Products (PH1) | leftover | opportunistic | 10-D1 |

**FUs this chunk resolves or advances at Stage 2:** FU-838 (route + client method deleted; handler kept, helper renamed → resolve), FU-917 (column dropped → resolve), FU-708 (tooltip copy + "cannot create" via 10-R40; PH7 stays "confirm in browser"), FU-704 (`MoneyInput` in `PriceEntry`; responsive layout still to do), FU-923 (two sites executed here, widened), FU-654 (+1 site), FU-671 (+5 sites). FU-911/FU-846/FU-705/FU-922/FU-919/FU-831/FU-768/FU-753/FU-732/FU-644/FU-627 untouched — their resolution points stand.

---

## Chunk 11 — Assistant (Dora)
*Source: [`CHUNK_11_assistant.md`](../05_investigations/finalisation/CHUNK_11_assistant.md) · analysed 2026-10-23*

### C. Senior review — Assistant

Finding ids `11-Rk`. Verdicts: **execute** (Stage 2, test-guarded) · **FU** · **waive** · **conditional**.

#### C1. Bugs (verified or high-confidence latent)
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 11-R1 | `confirm_actions.py:312–316` (`_primary_list`) | Reads `ShoppingList.Fields.IS_PRIMARY` — the field is gone (`Fields` has `NAME`, `STATUS`…; the comment at L478 and `shopping_actions._primary_list` both say primary is inferred now). `tick_shopping_line`, `add_recipe_to_list` and `trim_list_to_budget` raise `AttributeError` on propose, unhandled → `/ask` 500s. The registry eval only checks a proposer *exists*. | Delete it; import the one in `shopping_actions` (or move both to `assistant/_lists.py`). Test T1 smoke-executes every proposer. | execute |
| 11-R2 | `tools.py:2124` (`waste_insights`) | `datetime.now(timezone.utc)` with no `timezone` import at module scope (L17); the two tools that need it import it function-locally. `NameError` the first time the model calls it. R-021 too: the window should be household-local. | `household_today(repo)`-anchored cutoff; module-level imports; drop the local ones. Test T3. | execute |
| 11-R3 | `tools.py:2705–2742` (`_TOOL_NAV`) | 11 of 24 nav hints point at routes that don't exist: `/product-search` ×3 (retired FU-186), `/recipes` ×7 (route is `/cookbook`; legacy redirects retired — `routes.ts:99`), `/settings/preferences` for budget (`/settings/budget`; same slip as 09-R3). The "See it" button under an AI answer lands on the 404 page. | Fix paths; product tools → `/my-products` or no nav. Test T2 pins every path against a route list. | execute |
| 11-R4 | `DoraChat.vue:997–1000` | `getStock()` stamps `locationName: null` for every item, so Basic-mode `where_is` (and `(no location)` in its multi-match list) is wrong for every item that has a location. The list DTO carries `stock_location_id`; the location store resolves names. | Resolve via `useStockLocationStore` (loaded in `ensureRecipeData`). Vitest T5 on `runIntent('where_is')`. | execute |
| 11-R5 | `AssistantSettings.vue:471–475` | `toastCaption(err)` is a string formatter; calling it for effect shows nothing, while the comment says "the toast explains the fetch failure". A provider-list load failure is silent. | `$q.notify({ type:'negative', message:"Couldn't load your provider settings.", caption: toastCaption(err) })`. | execute |
| 11-R6 | `DoraHelpPage.vue:74` | AI setup link goes to `{ path:'/settings', query:{ tab:'system' } }` — the pre-redesign admin path; the page is `/settings/assistant` (the intro two lines up says so). | Fix the link; see 11-R26 for the rest of the page. | execute |
| 11-R33 | `DoraChat.vue:1044` | `getMealPlan` builds "today" from `new Date().toISOString().slice(0,10)` — the **UTC** date. Before 10:00 AEST the "upcoming" filter admits yesterday's entries (R-021). | Use the SPA's household-today helper (08-R8 family); if none exists yet, local date is the lesser evil — never UTC. | execute |
| 11-R7 | `tools.py:1410` | `suggest_substitution` cleans with `.rstrip("s")` — strips *every* trailing s ("molasses"→"molasse", "cress"→"cre"); the client parser uses `/s$/`. | `re.sub(r"s$", "", cleaned)`. | execute |
| 11-R8 | `assistantApiService.ts:32–45` | `ConfirmAction.type` union omits `cook_recipe`, `adjust_recipe_meals`, `trim_list_to_budget` (R-057). Works at runtime only because the value arrives from JSON. | Generate the list from `PROPOSERS` (11-R26's capabilities endpoint or a codegen file) and pin with T4. | execute |

#### C2. Redundancy / DRY (R-001, R-003)
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 11-R9 | `shopping_actions._match_stock_items`, `confirm_actions._find_stock_item/_find_location/_find_recipe` (+dead `_find_shopping_list`), `tools._find_one_by_name`, `recipes_using_item:1626`, `purchase_price_stats:2245`, `compare_prices:2484` | "Exact name, else contains" resolution written 8×, with three different return shapes. | One `resolve_by_name(repo, entity, name, build_query=None) -> NameResolution(status, matches)`; every caller renders `not_found/ambiguous/ready` from it. | execute |
| 11-R10 | `confirm_actions._stock_item_candidate` ≡ `shopping_actions._candidate_dto` | Identical candidate DTO. | Merge into the resolver module. | execute |
| 11-R11 | `_MAX_CANDIDATES = 6` ×3 modules | One constant. | `assistant/_limits.py` (`MAX_ROWS`, `MAX_CANDIDATES`, `MAX_MISSING`). | execute |
| 11-R12 | `doraIntents.ts:557–597` vs `tools.py:1367–1402` | The curated substitution table exists twice (23 vs 27 entries, divergent aliases); the client's aliases are wrong in places (`caster sugar`/`icing sugar`→`brown sugar`, `plain flour`→`self-raising flour` "weird, but"). R-003 domain data in two languages. | Codegen `generated/substitutes_table.ts` from the Python table, exactly as `units_table.ts` is produced by `scripts/dump_units.py`; delete the client copy; fix the aliases once, server-side. | execute |
| 11-R13 | `confirm_actions.py:926–991` | `trim_list_to_budget` summaries hard-code `$` ×6 — the 09-R1 class. | Lifted `format_money(amount, currency)` (10-R41) with the install currency. | execute (with 09-R1/10-R41) |
| 11-R14 | `tools.py:1146`, `confirm_actions.py:659` (+5 sites outside this chunk) | `getattr(ing, "is_optional", False)` on a declared `RecipeIngredient` field (R-008; 10-R24 shape). | `ing.is_optional` here; log the app-wide sweep (E3). | execute (2) + FU (5) |
| 11-R15 | `ask_assistant.py:73–88` vs `auth/email_flows.py:47`; `probe_assistant.py:229` | `_too_many_requests` copied once already ("promote if a third caller needs it"); the third caller — the probe — instead returns **422** for a rate limit. | `api_response.too_many_requests(retry_after)`; probe returns 429. Test T6. | execute |
| 11-R16 | `AssistantSettings.vue:436–452` vs `infrastructure/llm/*_client.py::_DEFAULT_BASE_URL` | Default base URLs and example model ids mirrored in TS "must stay in step" (R-003). Example ids are also dated (`claude-3-5-sonnet-20241022`, `gpt-4o-mini`). | `/assistant/providers` returns `default_base_url` + `example_model` per provider; SPA renders them. Owner picks current example ids. | execute |
| 11-R17 | `tools.py:2397–2408` | Mean purchase gap re-derived (4th copy — 09-R2 lists `generate_likely_due`, `trim_to_budget:412`, `pantry_belief`); `domain/cadence_math.mean_gap_days` exists. | Use it. | execute (with 09-R2) |
| 11-R18 | `tools.py:1502` (`savings_percent`), `2518` (`on_special`) | Discount rule restated; `domain/product_offer.discount_percent` is the one rule (10-R6/10-R23). | Use it. | execute |
| 11-R19 | `confirm_actions.propose_add_recipe_to_list:651–663`, `tools._stock_coverage:1129–1155` | "Missing ingredient" / coverage computed locally while `domain/recipe_cookability.py` owns the rule (chunk 1). | Route both through the domain helper; verify parity at Stage 2. | execute |
| 11-R20 | `tools.py:976` | `repo.get(AppSetting).all()` → `settings[0]` (FU-759 pattern). | `get_or_create_app_setting`. | execute |

#### C3. Dead code / unused fields / unread endpoints
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 11-R21 | `confirm_actions.py:482–488` | `_find_shopping_list` has no callers. | Delete (or it becomes a resolver case under 11-R9). | execute |
| 11-R22 | `tools.py:2185–2199` | `budget_status` resolves `user_id` and never uses it; `GetBudgetStatusHandler().handle()` takes no user. | Drop the session read (also −1 FU-654 site). | execute |
| 11-R23 | `doraIntents.ts:967–981` | `whats_new` hard-codes "recent highlights include the assistant, the locations heatmap, and per-user preferences" (stale forever, R-019) and carries a dead `...{}` spread. | Point at the Help changelog only. | execute |
| 11-R24 | `tools.py:2607, 2646` | Function-local `from datetime import datetime, timedelta, timezone` (first one unused). | Module imports (with 11-R2). | execute |
| 11-R25 | `app_knowledge.py` | The in-prompt app guide names "Recipes" (Cookbook), a "Locations" page, "Product Search … via the ingestion seam", "Settings → System (configure the AI assistant, the BYO-LLM panel)"; no Reports/Memory, My Products, Dora Score, budget, stocktake, cook mode. `doraIntents.show_around` and `PAGE_HELP['/settings']` describe the same old shell. This file is also where chunks 1–10 queued their "DoraBot paragraph". | Rewrite once, current shell, with the ten queued paragraphs — sized per 11-D1. | execute |
| 11-R26 | `DoraHelpPage.vue` (whole) | Hand-maintained capability lists drifted: 13/40 tools missing, Basic list missing the add-to-list verb, "Ollama only", "three chips", "AI/Basic chip". The proposal's §6 Q3 asked for exactly this. | `GET /assistant/capabilities` (tool name, user-facing description, 2–3 examples — add an `examples` key to each schema) + Basic intents from `INTENTS` (add `examples` there too); the page renders them, keeps its prose for modes/faces/tips. Registry test pins that every schema has examples. | execute |
| 11-R27 | `tools.py:366, 93, 1537, 609 vs 2205` | Tool descriptions the model reads are stale: `get_alerts.kind` enum lacks `shopping_overdue`, `price_drop`; `search_stock.expiring_soon` "within a week" (configurable); `pantry_health` key `expiring_within_week`; `budget_status` points at "Settings → Preferences" in the schema and "Settings → Kitchen setup → Money" in the body. | Fix copy; derive the kind enum from `alert_kinds.SEVERITY_BY_KIND.keys()`. | execute |
| 11-R28 | `tools.py:106–110, 262–267` | `search_products`/`find_deals` "across the household's configured merchants" — ingested catalogue now. | Copy. | execute |

#### C4. Componentisation opportunities (R-001)
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 11-R29 | `DoraChat.vue` two action cards | Add-to-list card vs Confirm/Cancel card (proposal §2.4). Both stable; the reconciliation chose not to restructure the assistant. | — | waive (decided 2026-07-08) |
| 11-R30 | `DoraChat.vue` (1,655 lines) | Chip pools (`BASIC_CHIP_POOL`, `AI_CHIP_POOL`, `INTENT_TO_AI_CHIP`) are data; the typewriter and the Pinia→snapshot `context()` builder are self-contained. | `services/doraChips.ts`, `composables/useTypewriter.ts`, `services/doraContext.ts` — mechanical, each unit-testable; the component keeps orchestration. | execute |

#### C5. Placement / layering (R-003, R-005)
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 11-R31 | `ask_assistant.py:96/235`, `providers.py:86`, `probe_assistant.py:211`, `confirm_actions.py:875`, `tools.py:2034/2189` | 7 `session.get(…)` reads behind 3 local helpers (`_rate_limit_subject`, `_current_user_id`, `_session_user_id`) — FU-654. | `infrastructure/auth_helpers.current_user_id()`. | execute (sweep) |
| 11-R32 | `ask_assistant.py:241/245/251` | Three function-local imports of the private `factory._UnavailableClient`. | `factory.unavailable_client(reason)` public; one import. | execute |
| 11-R34 | `doraIntents.ts:307` | `EXPIRY_HORIZON_DAYS = 7` while the server window is admin-configurable (`expiring_soon_window_days`) — a domain constant in two languages (R-003). | Expose the window on the app-settings composable the SPA already has; Basic mode reads it. `daysUntil` on the browser's local midnight stays as the accepted Basic/offline carve-out — comment it. | execute |
| 11-R35 | `tools.py:2659` | `spend_year_over_year` anchors `now` in UTC (R-021). | Household-local. | execute |

#### C6. Naming & idiom
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 11-R36 | `tools.py:1696–1713` | `_find_one_by_name` returns a 2-tuple or a 3-tuple by branch; callers probe `len(result) > 2`. | Dataclass result (folds into 11-R9). | execute |
| 11-R37 | `confirm_actions.py:704` | Bare `except Exception: missing += 1`. | Catch the handler's known failures; let the rest raise. | execute |
| 11-R38 | `DoraMascot.vue:120–129` | `clearTimeout(t as unknown as number)` on interval ids — works (shared id space) but the cast is the smell. | Keep timeouts and intervals in two typed slots. | execute |
| 11-R39 | `DoraChat.vue:32, 199, 286, 954–957, 1172–1174`; `DoraHelpPage.vue` `'inventory_2'` ×3; `MainLayout.vue:262` | Bare Material icon names (R-034) — render only because `material-icons` is kept as a fallback extra (`quasar.config.ts:93–97`). | `ICONS.*`. | execute |
| 11-R40 | `doraIntents.ts:3184` | Greeting bank does `name.replace(', ', '')` to undo the comma convention baked into `name`. | Pass `displayName` and `name` separately. | execute |

#### C7. Efficiency
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 11-R41 | `tools.py:1638–1661`, `1745–1755`, `1209`, `confirm_actions._plan_covering:499` | `recipes_using_item` and `stock_item_detail` load **every** recipe with ingredients to find usages; `suggest_recipes` loads all recipes twice when tag filters are set; `_plan_covering` loads every plan with entries. | A `RecipeIngredient` query by `stock_item_id` (the detail page's "recipes using this" already has one — chunk 6) for the first two; the other two are small-data and stay. | execute (2) + waive (2) |
| 11-R42 | `tools.py:2235–2464` | `purchase_price_stats` is 230 lines with 5 bulk lookups and its own paid-price ladder; `your_prices.py` (chunk 6) derives the same series per item. | Delegate the sample collection to `your_prices`; keep the stats/cadence shaping here. | conditional (with 06-R14) |
| 11-R43 | `ask_assistant.py:264–270` | A fresh LLM client per request and `is_available()` before every `/ask` — if the client probes the network there, every question pays two round-trips. | Verify at Stage 2; if so, cache availability per user for ~60 s (the SPA already debounces `/status`). | conditional |

#### C8. Design-level findings — out of Stage-2 scope
| Id | Finding | Recommendation |
|---|---|---|
| 11-D1 | `APP_OVERVIEW` rides in **every** AI prompt (`ask_assistant.py:199`); the file's own rule is "keep it concise — small models follow short guides best". Ten chunks have queued paragraphs for it; appended, it becomes a wall a 7B model stops following. | Keep a ~40-line routing guide in the prompt; add an `app_help(topic)` data tool that returns matching help entries from the **same corpus `HelpPage.vue` renders** (served by `/help`), so help lives once (R-003) and the model fetches detail on demand. Owner call — it decides where B3 deltas land. |
| 11-D2 | Basic-vs-AI capability cliff | Resolved 2026-07-08 (make Basic useful; no registry router). Record; no re-litigation. |
| 11-D3 | `DoraModeSlider` is 24 px tall and now the primary toggle (FU-663, D-004). | Execute FU-663 at Stage 2: 32–36 px pill inside a 44 px hit area. |
| 11-D4 | The owner asked for a one-shot "pulse glow" when the slider flips (DB3). The knob glows statically; no one-shot pulse exists. | Small: a `.dora-mode-slider--flipped` class on change with a 600 ms keyframe, honouring `prefers-reduced-motion`. Owner can decline. |
| 11-D5 | Rate-limit buckets are process-local (A.6, accepted single-instance). | Record only. |

#### C9. Hand-rolled-vs-library verdicts
| Surface | Hand-rolled | Verdict |
|---|---|---|
| `doraIntents.ts` rule engine (1,422 lines) | Yes | **keep** — decided; it is the default experience and the offline fallback. |
| Client `tryConvert` parser (logic mirrors server `convert_measurement`; data shared via codegen) | Yes | **keep** — Basic/offline path; the data is already single-sourced. Add the substitution table to the same codegen (11-R12). |
| `DoraMascot` frame controller, typewriter, mood hold | Yes | **keep** (extract the typewriter, 11-R30). |
| `with_lead_in` WAV rebuild, `voice_provision` streaming download | Yes | **keep** — small, correct, dependency-free (`requests` already present). |
| LLM clients (`infrastructure/llm/*`) | Yes (HTTP) | **keep** — four thin clients beat four SDKs for a self-hosted app; revisit if streaming lands. |

#### C10. Standards drift (R-0NN)
| Id | Rule | Where | Verdict |
|---|---|---|---|
| 11-R33 / 11-R35 / 11-R2 | R-021 household time | `DoraChat.vue:1044` (UTC date), `tools.py:2659`, `tools.py:2124` | execute |
| 11-R12 / 11-R16 / 11-R34 / 11-R18 | R-003 one source | substitution table ×2, provider defaults ×2, expiry horizon ×2, discount rule | execute |
| 11-R14 / 11-R24 / 11-R32 / 11-R37 | R-008 idiom | `getattr` on declared fields, function-local imports, bare except | execute |
| 11-R39 | R-034 icon registry | 12 bare Material names | execute |
| 11-R31 | FU-654 | 7 session reads | execute (sweep) |
| 11-R20 | FU-759 | `AppSetting.all()[0]` | execute |
| 11-R8 | R-057 contract inventory | `ConfirmAction.type` | execute |
| 11-R23 / 11-R25 / 11-R27 / 11-R28 | R-019 comments/copy ≠ code | stale corpus + tool descriptions | execute |
| — | FU-671 `text-color="white"` | `DoraChat.vue:329`, `DoraHelpPage.vue:47, 69` | execute (sweep) |
| — | R-002 / D-017 | `DoraModeSlider.vue:102, 142, 162, 179` (`rgba(0,0,0,…)` shadows, `var(--x, fallback)` literals); raw px radii/paddings throughout `DoraChat`/`DoraBubble` (12/10/8 px) | execute: shadows + fallbacks; radii → `--radius-*` where a token exists; the bespoke chat geometry otherwise stays with an inline D-017 carve-out comment |
| — | D-004 | `DoraModeSlider` 24 px (FU-663) | execute (11-D3) |
| — | D-010 motion tokens | `DoraChat.vue:1725` `160ms ease`, `DoraBubble` `240ms`/`220ms`/`180ms` eases | execute where a token matches; the launcher's spring curves are already tokens |

#### C11. Ride-along signals for FU-010 / FU-224 (theme / colour)
- Suggestion-card severity borders use Quasar `--q-negative/--q-warning/--q-primary` rather than `--semantic-*` tokens (`DoraChat.vue:1791–1798`).
- `.dora-bot-name` / `.dora-accent-btn` on `--accent-ink` ✅ (R-069 reference use).
- Contextual chip `color="primary" text-color="white"` (FU-671).
- `DoraHelpPage` `color="grey"` chips/icons — grey is D-001's absent/unknown; Basic mode is not "absent". Use `--text-secondary`.


### E. Proposed follow-ups (orchestrator allocates ids)

| # | Title | Type | Resolution point | Source |
|---|---|---|---|---|
| E1 | `app_help(topic)` tool + prompt-size budget for `APP_OVERVIEW`; help corpus served once from `/help` | decision → design | now (owner) — gates where chunks 1–10's DoraBot paragraphs land | 11-D1 |
| E2 | One-shot pulse glow on slider flip (DB3) | decision (small) | now (owner; may decline) | 11-D4 |
| E3 | App-wide sweep of `getattr(x, "is_optional", False)` on the declared field (5 sites outside this chunk: `recipe_cookability`, `recipe_rollup`, `get_recipes` ×2, `waste`) | leftover | with chunk 20 | 11-R14 |
| E4 | `purchase_price_stats` to reuse `your_prices` sample collection | leftover | with 06-R14 | 11-R42 |
| E5 | Per-user cached LLM availability if `is_available()` probes on every `/ask` | finding | verify at Stage 2 | 11-R43 |
| E6 | Generated `assistant_capabilities` (TS) so `ConfirmAction.type`, the help page and the chat chips all read one list | leftover | with 11-R26 | 11-R8 |

**FUs this chunk advances at Stage 2:** FU-663 (slider tap target → resolve), FU-654 (+7 sites), FU-671 (+3), FU-759 (+1). FU-788/751/722/628/629 are device-verification items (DORA_VERIFY) and stay open; FU-625 (backup round-trip of `UserLlmProvider`) belongs to chunk 18.

---

## Chunk 12 — Reports / Memory (P8-09), Waste, Budget
*Source: [`CHUNK_12_reports_memory.md`](../05_investigations/finalisation/CHUNK_12_reports_memory.md) · analysed 2026-10-23*

### C. Senior review — Reports / Waste / Budget

Finding ids `12-Rk`. Verdicts: **execute** · **FU** · **waive** · **conditional**.

#### C1. Bugs (verified or high-confidence latent)
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 12-R1 | `reports.py:236–268` (`StockValueOverTimeHandler`) | Loads `StockItem` with **no includes** and reads `i.stock_level.sequence` and `i.products` — both `lazy="noload"` (`table_mappings.py:1467–1469`), so every item's current rank is 0 and the linked-product price branch never fires (R-032; the FU-873 trap). The figure is level-change history × observation fallback only, which is the §3.3 "systematically undercounted". And it has **no consumer**: the Reports card was cut (chunk 3), the dashboard `pantry_value` card went 2026-09-04, `getStockValueAsync` is unreferenced — the dashboard comment claiming "callers on the reports page" is stale. | Delete the handler, route, `StockValueResponse`/`getStockValueAsync` and `test__stock_value_over_time__…` (R-057). If it is ever revived, `.include(STOCK_LEVEL).include(PRODUCTS)` first. | execute (delete) |
| 12-R2 | `budget.py:95–96, 129–134, 417` | `period_spent` bounds the window at **UTC midnight** of the household dates (`_as_utc_datetime`) and `GetBudgetHistoryHandler` buckets by `completed_at.date()` (UTC) while the anchor is `household_today`. In a +10 household a shop finished Monday 08:00 local counts in **last** week's budget; the status card and the history chip are wrong for the first ~10 h of every period (R-021). The module comment calls this "timezone gymnastics it doesn't deserve". | `datetime.combine(d, time.min, tzinfo=household_timezone(repo))` for the bounds; `completed_at.astimezone(tz).date()` in history; rewrite the comment. Test T1. | execute |
| 12-R3 | `reports.py:117–126, 173–183` | `_parse_range` and `range_window.end` anchor on UTC `now`; the window label can read tomorrow's date in the evening east of UTC, and bounded windows start at a UTC instant (R-021). | Anchor on `household_today` + household midnight; share the helper with 10-R15's `_ranges.py`. | execute |
| 12-R4 | `reports.py:655–660` (`MostBoughtItemsHandler`) | Counts distinct archived lists an item appears on, **ticked or not**; the card says "Bought most". An item added and never bought scores the same as one bought (FU-768's class — "on the list ≠ bought"). | `ShoppingListLine.is_ticked == True`. Test T2. | execute |
| 12-R5 | `waste.py:107–122` | "Value at risk" picks the **last line by `sequence`** over every list the item ever appeared on — `sequence` is per-list, so the pick is arbitrary — while the comment says "cheapest-last-paid-price". `your_prices` already owns an item's baseline. | Use `build_your_prices_for_item(...).baseline`, or drop `estimated_value` (only the assistant tool renders it). | execute |
| 12-R6 | `WasteCard.vue:135–145` vs `helpers/wasteReasons.ts:22–28` | The card declares its own `WASTE_REASON_TILES` ("Overbought") while the helper that calls itself the single source says "Bought too much"; the modal and the report name one reason two ways (R-003). | Import the helper. | execute |
| 12-R7 | `ReportsPage.vue:367–373` | `windowLabel` uses `toLocaleDateString(undefined, …)` — the browser's locale, not the install's (D-006; `useDateFormat.formatDate` exists). | `formatDate(iso, { day:'numeric', month:'short', year:'numeric' })`. | execute |
| 12-R8 | `budgetApiService.ts:4–6` | Doc says settings "live on the User row… go through `AuthApiService.updateMeAsync`" — stale; the same class implements `PATCH /budget/settings` on `AppSetting` (R-019). | Fix the comment. | execute |
| 12-R9 | `waste.py:44–47` | `_DEFAULT_HORIZON_DAYS = 7` "mirrors the assistant's `_EXPIRY_HORIZON_DAYS`" — the assistant reads the admin-configurable `expiring_soon_window_days`; this is a third fixed copy (R-003; the 11-R34 family). | Default from `effective_expiring_soon_window(get_or_create_app_setting(repo))`. | execute |

#### C2. Redundancy / DRY (R-001, R-003)
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 12-R10 | `SpendByStoreHandler:469–517`, `SavingsCapturedHandler:725–753`, `SpendByCategoryHandler:1162–1191`, `SpendYoYHandler._for_window:1285–1313`, `MostBoughtItemsHandler:643–648`, `budget.period_spent:129–153`, `GetBudgetHistoryHandler:385–425` | "Finished lists in the window → ticked, priced lines → actual→picked ladder" is written **seven** times (five in core SQL, two through the repository), with `deferred_by_budget` honoured only by budget. One rule, one function. | `shopping_lists/_line_price.spend_lines(repo, since, until) -> list[SpendLine]` (list id, completed_at, stock item, product, qty, unit_price, store rungs), used by all seven. Test T3 pins total parity across reports. | execute |
| 12-R11 | `SpendYoYHandler._for_window` ≡ `SpendByCategoryHandler.handle` + `until` | YoY re-implements the category aggregation. | YoY calls the category handler twice over `spend_lines`. | execute (with R10) |
| 12-R12 | `ItemPriceMoversCard:172–179`, `KitchenMemoryCard:195–202`, `ReportsLede:44–61` | `WINDOW_WORDS` ×3 (+ `PRIOR_WORDS`), with one divergence already ("all time" vs "since you started logging prices"). | `helpers/reportRangeWords.ts`. | execute |
| 12-R13 | `ReportsPage.vue:287–298` | `colourFor` hashes into six `paletteToken('--chart-N', '#hex')` fallbacks (R-002 literals; FU-843 collision at six). | `useThemePalette.categoricalColour(key)` as the one ramp (check the dashboard for a twin at Stage 2); FU-843 widens the ramp. | execute |
| 12-R14 | `waste.py:540–544` | `_rank_buckets` compares `occurred_at` by parsing its own ISO string back per event. | Keep datetimes; serialise once at the end. | execute |
| 12-R15 | `waste.py:343–352` | `BulkLogWasteResponse` uses `None` defaults + `__post_init__` to mean "empty list". | `field(default_factory=list)` (R-008). | execute |
| 12-R16 | `budget.py:286, 314–321, 437` | `getattr(offer, "_product_id", None) or getattr(offer, "product_id", None)`; `_current_user_id` (FU-654); `from flask import request` inside a function though imported at module scope. The `_product_id` private-attr read appears **18×** across features (`# noqa: SLF001`). | Local: FU-654 helper, drop the re-import; expose a public mapped `product_id` on the offer entities — cross-cutting (E1). | execute (local) + FU |

#### C3. Dead code / unused fields / unread endpoints
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 12-R17 | `waste.py:189–201, 262–282`; `wasteApiService.ts:110–113, 144–147` | `GET /waste/rescue` and `GET /waste/events` have **no HTTP consumer** — the assistant tool calls `GetWasteRescueHandler` directly and the SPA never calls `getRescueAsync`/`listEventsAsync` (`deleteEventAsync` is used by Undo). | Delete the two client methods and the two routes; keep the handler (the tool and `get_recipes`' at-risk rule use it); convert `test__get_waste_rescue__*` to handler tests. | execute (R-057) |
| 12-R18 | `budget.py:239, 338–339, 365, 449–450` | `handle()` is typed `| None` and never returns `None` → two dead `if dto is None: return unauthorized()` branches. | Tighten the types; drop the branches. | execute |
| 12-R19 | `reports.py:789–800`, `reportsApiService.ts:95–102` | `savings-captured.lists[]` is never read by the SPA (`SpendCard` uses the two totals). | Leave until FU-831 (it reshapes savings); then drop or consume. | conditional (FU-831) |
| 12-R20 | `KitchenMemoryCard.vue:313–325`, `WasteCard.vue:198–215` | `.km-skeleton`/`.km-skeleton__col` rules duplicated inside the media query; `.wr-reason` declared twice. | Tidy. | execute |
| 12-R21 | `MarkAsWastedDialog.vue:92–139` | `var(--text-sm, 0.875rem)` — the token is undefined (chunk 5 confirmed) so the fallback always paints; `var(--space-*, Npx)` / `var(--radius-md, 8px)` fallbacks (D-017 no-fallback convention); `outline: none` on `:focus-visible` (FU-841, A6). | Execute FU-841 + tokens (`--font-size-sm`, no fallbacks). | execute |
| 12-R22 | `test_reports_router.py:45` | Goes with 12-R1. | — | execute |

#### C4. Componentisation opportunities (R-001)
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 12-R23 | `ReportsPage.vue:229–257` vs `DashboardPage` `loadSlot`/`slotErrors` | Per-card failure machinery duplicated (named in-file as FU-844). | `composables/useSlotLoader()`; FU-832's `useCardLayout` can sit beside it. | execute |
| 12-R24 | `reports.py` (1,617 lines, 10 handlers) | Ten reports + their shared range/bucket helpers in one module; the module docstring still says "all six reports". | Split: `features/reports/{_ranges,spend,memory,price_movers,price_drops}.py`; `_ranges.py` is also 10-R15's home. Mechanical; tests re-import. | execute |

#### C5. Placement / layering (R-003, R-005)
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 12-R25 | `reports.py` (all handlers) | Core `select()` over mapped classes rather than the repository ports — the accepted aggregate-report carve-out (10-R17 treatment), but undeclared. | One `# R-005 carve-out: multi-table aggregates` note at module top (per split module). | execute (comment) |
| 12-R26 | `reports.py:1478–1495` | `ItemPriceMoversHandler` loads every observation for every item and range-filters in Python (documented SQLite-tz reason). | Fine at household scale; the comment already explains it. | waive |
| 12-R27 | `waste.py:142–148` | Rescue loads every recipe with ingredients (11-R41 class). | With 11-R41's ingredient-by-item query. | FU (with 11-R41) |
| 12-R28 | `waste.py:269–280` | `list_waste_events` loads all events then sorts/limits in Python. | Moot after 12-R17; else `order_by`/`limit`. | execute (via R17) |
| 12-R29 | `waste.py:481–483` | `BulkDeleteWasteHandler` calls `save_changes()` inside the loop — N commits (R-031). | One save after the loop (the update handler commits its own restore). | execute |

#### C6. Naming & idiom
| Id | Where | Finding | Fix | Verdict |
|---|---|---|---|---|
| 12-R30 | `budget.py:68–72` | "Doesn't deserve timezone gymnastics" two lines above code that already uses `household_today` — and the gymnastics are exactly what 12-R2 needs. | Rewrite with R2. | execute |
| 12-R31 | `reports.py:1–40` | Module docstring lists six endpoints of eleven; the "Conventions" block is right, the inventory isn't (R-019). | Rewrite with R24. | execute |
| 12-R32 | `BudgetSettings.vue:124–128` | `font-size: 0.8125rem`, `margin-top: 4px` raw (D-003/D-017); uses `DoraSegmented` while Reports uses `BaseSegmented` (two segmented controls — chunk 13, 12-D5). | Tokens here; the merge is chunk 13's. | execute (tokens) |

#### C7. Efficiency
Covered by 12-R26/27/28/29. The spend reports are O(lines in window) with a handful of bulk lookups — correct shape.

#### C8. Design-level findings — out of Stage-2 scope
| Id | Finding | Recommendation |
|---|---|---|
| 12-D1 | Reports has **no owner feedback** (the section is `?`); the in-session review is the only source and the page was rebuilt against it. The "90% happy" statement covers pages the owner walked — confirm Reports was one before Stage 2 touches layout. | Owner: one line, "Reports as it stands is in the 90%". |
| 12-D2 | Savings baseline (FU-831, ADR-068) is decided-not-built; 12-R10 should land first so FU-831 edits one function. | Sequence: R10 → FU-831. |
| 12-D3 | Waste proposal §13: A (Undo restores expiry) built ✅; B (cookbook filter name) and C (sort default) were impl-time picks — chunks 1 and 5 own confirming them. | Record only. |
| 12-D4 | Budget weeks start Monday, fixed; no household first-day setting exists anywhere. Fine for AU; a US household would want Sunday. | One AppSetting if asked; not now. |
| 12-D5 | `DoraSegmented` (settings, 9 uses) and `BaseSegmented` (pages, 13 uses) are two segmented controls (R-001). | Chunk 13 (settings shell) merges; note here because the budget page is the only money surface on the Dora one. |

#### C9. Hand-rolled-vs-library verdicts
| Surface | Hand-rolled | Verdict |
|---|---|---|
| Kitchen-memory column track (CSS bars) | Yes | **keep** — review §4.6 chose no chart library; integers as columns, `role="img"` label. |
| `ProportionBar` (spend composition) | Yes (shared) | **keep** — one implementation with the shopping list. |
| `PriceHistoryChart` drill-in | Shared | **keep** (chunk 10 verdict). |
| Range/bucket maths | Yes | **keep**, consolidated in `_ranges.py` (12-R24/10-R15). |

#### C10. Standards drift (R-0NN)
| Id | Rule | Where | Verdict |
|---|---|---|---|
| 12-R2 / 12-R3 | R-021 household time | budget bounds + history; reports range anchors | execute |
| 12-R1 | R-032 noload reads | stock-value handler | execute (delete) |
| 12-R6 / 12-R9 / 12-R10 / 12-R11 / 12-R12 / 12-R13 | R-003 one source | reason tiles ×2, expiry horizon ×3, spend-lines ×7, range words ×3, colour ramp | execute |
| 12-R8 / 12-R30 / 12-R31 | R-019 comments ≠ code | budget service doc, period comment, reports docstring | execute |
| 12-R15 / 12-R16 | R-008 idiom | `__post_init__` lists, getattr chain, re-import | execute |
| 12-R1 / 12-R17 / 12-R19 | R-057 contract inventory | stock-value, waste rescue/list, savings lists | execute / conditional |
| 12-R29 | R-031 one commit | bulk delete | execute |
| 12-R7 | D-006 formatting authority | window label | execute |
| 12-R21 | D-017 / A6 / FU-841 | mark-wasted tiles | execute |
| 12-R25 | R-005 (declared carve-out) | reports core SQL | execute (comment) |
| 12-R16 | FU-654 | `budget.py:314` | execute (sweep) |
| 12-R32 | D-003 / D-017 | `BudgetSettings.vue` raw rem/px | execute |

#### C11. Ride-along signals for FU-010 / FU-224 (theme / colour)
- Spend legend's unassigned dot: `--border-strong` + hatch (D-001 texture-not-hue) ✅ reference use.
- Categorical ramp `--chart-1..6` with hex fallbacks (12-R13 / FU-843).
- Kitchen-memory bars `--brand-primary`; Price changes uses arrows, no red/green (review §4.5.3) ✅.
- `MarkAsWastedDialog` tiles paint `--border-default`/`--surface-sunken` ✅ after FU-747; focus ring missing (FU-841).


### E. Proposed follow-ups (orchestrator allocates ids)

| # | Title | Type | Resolution point | Source |
|---|---|---|---|---|
| E1 | Public `product_id` on `ProductOffer`/`ProductHistoricOffer` mappings — retire 18 `_product_id` private-attr reads (`# noqa: SLF001`) | leftover | chunk 20 | 12-R16 |
| E2 | Savings `lists[]` DTO: consume or drop | leftover | with FU-831 | 12-R19 |
| E3 | Merge `DoraSegmented` into `BaseSegmented` | leftover | chunk 13 | 12-D5 |
| E4 | Owner confirms the four-card Reports shape is in the "90%" | decision | now | 12-D1 |
| E5 | Rescue recipe scan via ingredient-by-item query | leftover | with 11-R41 | 12-R27 |

**FUs this chunk advances at Stage 2:** FU-841 (→ resolve), FU-843 (ramp via R13), FU-844 (→ resolve via R23), FU-654 (+1), FU-873 (same trap, different file — reference). FU-831/832/898/907 untouched (decided, their own jobs).

---

## Chunk 13 — Settings shell
*Source: [`CHUNK_13_settings_shell.md`](../05_investigations/finalisation/CHUNK_13_settings_shell.md) · analysed 2026-10-23*

### C. Senior review — Settings shell

#### C1. Bugs (verified or high-confidence latent)
- **13-R1** · bug · `dora_api/features/app_settings/update_app_settings.py:171–175` · on an invalid `nutrition_mode` the handler does `return None, f"Invalid nutrition mode …"` (a tuple) while every other branch returns `UpdateAppSettingsResponse(invalid_reason=…)`; the route (`:461–464`) reads `_Response.invalid_reason` → `AttributeError` → 500. **Change:** `return UpdateAppSettingsResponse(invalid_reason=f"'{_Mode}' is not a nutrition mode. Supported: {list(NUTRITION_MODE_VALUES)}.")`. Blast S. Guard: none — add `test__patch_app_settings__BogusNutritionMode__400InvalidSettings` beside the cadence-band test (`test_app_settings_router.py:170`). **execute**.
- **13-R2** · bug · `users/update_user_as_admin.py:100–101` · `if "email" in _SetFields: _Target.email = request.email` — no `normalise_email`/`is_valid_email`/uniqueness check and no `email_verified` update, unlike `update_me.py:130–148` and `create_user_as_admin.py:77–82,162`. An admin can store a malformed or duplicate address (password-reset mail would then route wrongly). **Change:** extract the email block of `update_me.py:136–148` into `auth_helpers.apply_email_change(repo, user, raw) -> str | None` and call it from both handlers; admin route maps the message to `business_rule_violation`. Blast S. Guard: `test_users_admin.py` + new `test__admin_update_user__malformed_or_taken_email__rejected`. **execute**.
- **13-R3** · bug · `users/delete_user_as_admin.py:64–67` · last-admin guard counts `is_admin == True` rows, ignoring `is_active`; `update_user_as_admin._other_usable_admins` (`:59–74`) counts active admins. Deactivate admin B, delete admin A → install has no admin who can sign in. **Change:** move `_other_usable_admins` to `auth/admin_gate.py` as `other_usable_admins(repo, user_id)` and use it in both handlers. Blast S. Guard: new pytest "deactivated admin doesn't count as cover for delete". **execute**.
- **13-R4** · bug (functional gap) · `composables/useProductSearchUrl.ts:28–41` · reads `product_search_url` from admin-only `GET /app-settings`; members get 403 → URL empty → the main-nav "Product Search" entry (and the companion CTAs' real link) never appear for non-admins, contradicting FU-186 ("every user"). **Change:** publish `product_search_url` on `/health` (new `products_policy: { search_url }` block beside `locale_policy`, R-057 "add, never remove") and read it there; keep the admin page writing via `/app-settings`. Blast S. Guard: `test_health_router.py` key assertion. **execute**.
- **13-R5** · latent · `services/api/userAdminApiService.ts:47–48` · `GET /users` with no `limit` → `DEFAULT_LIMIT=50` (`query_options.py:22`) silently caps the admin list. **Change:** request `?limit=500` (or add a `limit` param and page). Blast S. **execute** (FU-668 class — fold into that sweep).
- **13-R6** · latent · `pages/settings/PreferencesSettings.vue:148–153` · `modeAndFamilyForKey` returns System/Pesto for any key `familyAndModeOf` can't decode, including the five legacy keys the server still accepts (`user.py:49–53`) — the picker then disagrees with what themeService renders (`themeService.ts:305–306` maps legacy at apply time). **Change:** run the key through themeService's legacy normaliser before decoding (export it; one R-003 mapping). Blast S. Guard: vitest on `familyAndModeOf(normalise('pesto-noir'))`. **execute**.
- **13-R7** · latent (leak) · `PreferencesSettings.vue:160–168` · `mql.addEventListener('change', …)` with no `onBeforeUnmount` removal; `themeService.ts:427–429` already owns a system-dark watcher. **Change:** expose `osPrefersDarkRef` from themeService (one listener, R-003) and drop the page's own. Blast S. **execute**.
- **13-R8** · latent · `AuditLogSettings.vue:301` · `classes: 'text-mono'` references a *scoped* style; q-table renders cells outside the component's scope attribute so the class likely doesn't apply. **Change:** move `.text-mono` to a global utility (`css/app.scss` already has one? grep at Stage 2) or use `:deep`. Blast S. **execute** (verify in browser first).

#### C2. Redundancy / DRY (R-001, R-003)
- **13-R9** · `AdminSystem{Region,Money,Alerts,Stock,Stocktake,MealReconcile,Cooking,Image,Push,Email,Voice,Ingestion}Settings.vue` + `AuditLogSettings.vue:425–448` · thirteen hand-copied "load `/app-settings` on mount → `saved`/`draft` → save one field on blur/toggle → toast → revert on error" blocks (~60 lines each). **Change:** `composables/useAppSettingField.ts` — `const { draft, save, saving } = useAppSettingField('smtp_host', { successMessage, afterSave: refreshX })` backed by one shared `appSettingsStore` (one GET per session instead of one per page mount; `refresh()` after PATCH). Pages shrink to templates. Blast M (13 files). Guard: vitest on the composable's revert-on-error; existing pytest unchanged. **execute**.
- **13-R10** · 14 settings pages inline `$q.notify({type:'positive'|'negative', position:'bottom-right', …})` while `useSettingsSave.ts:5–9` documents itself as the single source (9 pages use it). **Change:** route every page's save through `useSettingsSave.update()` (falls out of 13-R9 for the admin pages; Account/Users/Audit/Stores/Taxonomy/Locations use `notifySuccess/notifyError`). Blast M. **execute**.
- **13-R11** · `.settings-divider { … }` scoped copy in 14 pages (`AccountSettings.vue:355–360` etc., margins differ 0/2px/8px). **Change:** one global `.settings-divider` in `css/settingsCards.scss` (which already hosts `.settings-card`); delete the 14 copies, keep the two margin variants as modifiers. Blast S. **execute**.
- **13-R12** · `AccountSettings.vue:131–133,280` hardcodes `8` ×4 while `models/password.ts:11–17` owns `MIN_PASSWORD_LENGTH`/`PASSWORD_HINT`/`passwordLongEnough` and `PasswordSetter.vue` uses them. **Change:** import and use them. Blast S. **execute**. *tracked:* FU-656 (the TS↔Python duplication itself) — recommended resolution for FU-656: publish `password_min_length` on `/auth/capabilities` and derive the TS constant; execute at Stage 2 with this.
- **13-R13** · 12 admin pages render "You don't have admin permissions to view this page." and gate `onMounted` on `isAdmin`, but `router/index.ts:154` already redirects non-admins off `/settings/admin/*`. **Change:** delete the 12 banners + `isAdmin` early returns (route guard is the single authority, R-003); keep `isAdmin` only where the page branches copy (Voice/Notifications "ask an admin"). Blast S (12 files). **execute**.
- **13-R14** · `create_user_as_admin.py:69–87` and `reset_user_password.py:40–70` both define a 12-char alphanumeric one-time-password generator; `create_user_as_admin.py:125–130,133–138` + `reset_user_password.py:98–103` + 3 auth files build the same RFC-4918 `ProblemDetails` literal (6 copies). **Change:** `auth_helpers.mint_one_time_password()`; `api_response.validation_failed(errors: dict[str, list[str]])` returning the 422 ProblemDetails; replace the 6 literals. Blast S. Guard: existing 422 tests. **execute**.
- **13-R15** · `AdminUpdateUserRequest.image/clear_image` (`update_user_as_admin.py:39–43,126–131`) has no SPA caller (`AdminUpdateUserCommand` lacks both fields) — the documented "admin clears a problematic picture" is unreachable. **Change (owner-neutral):** add a "Remove picture" item to the row's overflow menu (`UsersAdminSettings.vue:104–131`) sending `{clear_image:true}`; drop `image` (set) from the admin request — setting another user's photo was "for completeness" only. Blast S. **execute** (the remove half) / **waive** (the set half, delete it).
- **13-R16** · contract drift (R-057): `healthApiService.ts:13–24` types `features` as `[key: string]: boolean` though the server emits strings for `nutrition_mode` and `nutrition_rating_scheme` (`health_check.py:141,168`); `schema_version_db` (`:378`) absent from `HealthInfo`; `appSettingsApiService.ts:8–102` lacks `backup_retention_count`/`backup_storage_path` that `AdminDataBackupRestore.vue:906–934` reads/writes (type-checks only because `Partial<…>` + `?? 5`); `authApiService.ts:61–63` still carries `nutrition_mode` on `UpdateMeCommand` (server `extra="forbid"` → any sender gets 400). **Change:** fix the three TS types, delete the dead field. Blast S. Guard: `test__get_app_settings__CoreFields__PresentAndTyped` + a TS compile. **execute**.
- **13-R17** · `TaxonomyManagerPage.vue:36` and `VocabListEditor.vue:86` each declare `type VocabItem`; `RecipeDietaryTagsSettings.vue:22–52,170–175` and `StoresSettings.vue:36–98,185–204` re-implement VocabListEditor's row (`.vocab-row`), inline rename (`editingId`/`renameDraft`/`saveRename`) and list chrome. **Change:** export `VocabItem` once from VocabListEditor; give VocabListEditor `#leading` (avatar) and `#meta` slots + a `rename-mode: 'inline' | 'dialog'` prop so Stores and Dietary tags become callers. Blast M. **execute**.
- **13-R18** · `ChannelSetupNote.vue` is `SettingsNotice` with channel copy baked in (identical banner anatomy, `dora-bg-warning-soft`). **Change:** render `<SettingsNotice :title>` inside it (or inline the two copies into Notifications via SettingsNotice slots) so there is one warning-card anatomy (D-015). Blast S. **execute**.

#### C3. Dead code / unused fields / unread endpoints
- **13-R19** · `app_settings/probe_llm.py` (whole file) + `APP_SETTINGS_ROUTER /probe` + `appSettingsApiService.probeAsync` (`:114–118,129–132`) + `test_app_settings_router.py:205–230` — grep `probeAsync|/app-settings/probe` → only the definition; the Assistant page probes via `assistantApiService.probeAsync` (per-user providers). **Change:** delete route, client method, `ProbeResult` type, and the two tests. Blast S. **execute**.
- **13-R20** · `PreferencesSettings.vue:179,188–190,199–205` `themeDraft` is written on load/rollback and never read by the template (mode/family drafts drive it). **Change:** delete it; `onThemeChange` keeps `previous`. Blast S. **execute**.
- **13-R21** · `useMoneyEnabled.ts:17–19` — `installEnabled` and `moneyEnabled` are the same computed twice; `installEnabled` has no external reader (grep at Stage 2). **Change:** return `{ moneyEnabled }` only. Blast S. **execute**.
- **13-R22** · `AuditLogSettings.vue:312–313` — `if (sev === 'info') return 'info'; return 'info';` duplicate branch. **Change:** collapse. Blast S. **execute**.
- **13-R23** · `NotificationsSettings.vue:267,287` imports from `'vue'` twice (`onMounted` on its own line). **Change:** merge. Blast S. **execute**.
- **13-R24** · `update_user_as_admin.py:25–27` re-exports `_require_admin` "no big-bang rename" — 9 files still import it from there vs 8 from `auth.admin_gate`. **Change:** sweep the 9 imports, delete the re-export. Blast S. **execute**.

#### C4. Componentisation opportunities (R-001)
- **13-R25** · the "not signed in" banner `<q-banner class="dora-bg-sunken" dense>Not signed in.</q-banner>` appears at the top of Account/Preferences/Notifications/Voice; the shell already requires auth. **Change:** delete the four `v-if="!currentUser"` branches (the router guard is the authority) or hoist one guard into `SettingsShell`. Blast S. **execute**.
- **13-R26** · `UsersAdminSettings.vue:638–651 confirmDialog` and the taxonomy/locations `promptForName`/`onDelete` dialogs are the fourth and fifth hand-rolled `$q.dialog` promise wrappers in the settings tree. **Change:** `composables/useConfirm.ts` (`confirm({title,message,okLabel,danger})` / `prompt({title,message,initial})`) — check `src/composables` for an existing one first (chunk 20 cross-cut). Blast M. **FU** (cross-cutting; chunk 20 decides the home).

#### C5. Placement / layering (R-003, R-005)
- **13-R27** · `health_check.py:12–13` docstring "Cheap by design: never touches the DB or external services" is false (AppSetting fetch, Product count, alembic_version read) — R-019. **Change:** rewrite to "one memoised AppSetting read + a Product count; alembic head at import". **execute**.
- **13-R28** · `get_app_settings._to_dto`, `operational_config.resolved_operational_config`, `health_check._*_policy` use `getattr(setting, "field", default)` for fields the `AppSetting` dataclass always defines (defensive noise from the migration era). **Change:** direct attribute access; keep `or default` only where empty-string→default is intended. Blast S. **execute**.
- **13-R29** · `update_app_settings.py:1–5` docstring "Only the assistant (BYO-LLM) config lives here for now" — stale by ~40 fields (R-019). **Change:** rewrite. **execute**.
- **13-R30** · `useFeatureFlags.ts:83,95–96` comments say "true when DORA_SMTP_USERNAME is set" / "DORA_VAPID_* are set" — those env vars were retired 2026-07-06 (`operational_config.py:4–6`). **Change:** reword to the AppSetting fields. **execute**.
- **13-R31** · `update_me.py:296–305` / `get_me.py:20–32` open-code the session user-id parse (FU-654 helper sweep +2). **execute** under FU-654.
- **13-R32** · `get_users._stamp_has_image` and `delete_user_as_admin` reach `db.metadata.tables[...]` directly (same shape as FU-923's `StockItemProduct` readers). Portable SQL, but outside the repository port (R-005). **Change:** `repository.column_flags(User, "image", ids)` / `repository.delete_where(table, col == id)` helpers — fold into FU-923's widening. **FU** (FU-923).

#### C6. Naming & idiom
- **13-R33** · `get_user_image.py:49` route `"/<uuid:user_id>/image"` vs siblings `"<uuid:user_id>"` (leading slash inconsistency; both resolve). **Change:** drop the slash. **execute**.
- **13-R34** · `get_users.py:97`, `update_user_as_admin.py:169`, `reset_user_password.py:129`, `update_me.py:316` use f-string logging; siblings use `%s` args. **Change:** `%s` form. **execute**.
- **13-R35** · `AdminSystemMoneySettings.vue:57` `featureFlags$refresh` (and Stock/Stocktake) — a `$`-suffixed local is idiosyncratic. **Change:** `refreshFeatureFlags`. **execute** (falls out of 13-R9).

#### C7. Efficiency
- **13-R36** · every admin page mount issues its own `GET /app-settings`; the Audit page issues it alongside the log fetch. One `appSettingsStore` (13-R9) makes it one per session. **execute** (with 13-R9).
- **13-R37** · `health_check._resolve_db_schema_version` runs `SELECT version_num FROM alembic_version` on **every** probe, and `/health` is polled by every composable on boot (flags, money, measurement, image, cooking, budget, reconcile, stocktake, support — up to 9 callers share one inflight promise per composable but not across composables → up to 9 probes per cold load). **Change:** memoise the DB revision per process (it can't change at runtime); add one shared `healthProbe.ts` with a single inflight promise all policy composables read from. Blast M. **execute** (R-074).

#### C8. Design-level findings — out of Stage-2 scope
- **13-D1** · Feedback "Settings is shown in both main menu and the user dropdown — remove from main menu": **already done** (`MainLayout.vue:290` comment; grep shows one `/settings/account` entry, no dropdown). Record as covered.
- **13-D2** · Feedback "Theme should be split into type … and theme … separately": **done** (round-19 Mode + Theme sections). Covered.
- **13-D3** · Feedback "Profile picture + menu bar avatar": **done** (Phase 4). Covered.
- **13-D4** · Feedback "Text size 75/100/150 %": shipped as 87.5/100/112.5/125 % (`tokens.scss:294–298`). Owner call: is the narrower range acceptable, or add 75 %/150 % steps (`xs`/`xxl` would need `ALLOWED_FONT_SIZES` + TS union + tokens)? Default: accept as-is (owner ≥90 % happy).
- **13-D5** · Kitchen setup is member-editable (stores, locations, vocab) while every install switch is admin-only — deliberate ("kitchen setup, not personal") but worth one line in Help (B2 "Who can change what"). No change.
- **13-D6** · About says "Versioning isn't tagged in this fork yet" while `/health.version` is `0.7.0` (`version_info.py:12`). Owner call: show `version` + `schema_version` (+ `schema_version_db` mismatch warning) in Technical details — a 10-line change but it's a copy/product decision.
- **13-D7** · Admin → Users has no search/sort and no pagination UI (fine for a household; note only if Path B managed instances grow).

#### C9. Hand-rolled-vs-library verdicts
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| `DoraSegmented.vue` | radiogroup segmented control | `BaseSegmented` (q-btn-toggle) | **merge** into one component (FU-848) | M / low | Dora's wraps + scrolls + has radio semantics; make Base the thin wrapper or retire Base. Decide in FU-848, execute at Stage 2 of chunk 20. |
| `SettingsMobileNav.vue` | tab strip + chips | `q-tabs`/`q-route-tab` | **keep** | – | 44 px, badge, group→first-leaf semantics; q-tabs would need the same custom chips. |
| `EncryptionKeyBanner.generateFernetKey` | 32 random bytes → url-safe b64 | none needed | **keep** | – | 6 lines, correct. |
| `AuditLogSettings.exportCsv` | CSV escape + blob download | `papaparse` / `quasar exportFile` | **wrap** — use Quasar's `exportFile` for the download half | S / low | Keep the 8-line escaper. |
| `AdminSystemRegionSettings` preview + choices | Intl-based preview, static choice lists | — | **keep** | – | Plain Intl, no round-trip. |
| `StockLocationsSettings` expansion in localStorage | persisted set | `useStorage` (VueUse — not a dep) | **keep** | – | R-026 carve-out documented. |

#### C10. Standards drift (R-0NN)
- **13-R38** · R-034 bare icon names: `VoicePicker.vue:117 name="download"`, `AuditLogSettings.vue:186 icon-right="chevron_right"`. **Change:** `ICONS.download`, `ICONS.chevron_right`. **execute**.
- **13-R39** · FU-671 `text-color="white"`: `AuditLogSettings.vue:163,218` (+ `ApiAccessSettings.vue` ×4, `AdminDataBackupRestore.vue:227` — chunks 16/18). **execute** under FU-671.
- **13-R40** · R-002 token drift: two focus-ring tokens with different values — `--focus-ring` (= brand primary, 27 uses) and `--ring-focus` (35 % alpha, 8 uses: `SettingsNavGroup:110,151`, `DoraSegmented:104`, `VoicePicker:390,474`, `SettingsMobileNav:151`). Settings pages mix both. **Change:** owner-neutral — alias `--ring-focus: var(--focus-ring)` in tokens and migrate the 8 uses, or document the two tiers in the style guide. **FU** (cross-cutting; FU-010/224 theme sweep). Also `VoicePicker.vue:484–485` hex literal `#c10015` fallback — replace with `var(--semantic-danger)`. **execute**.
- **13-R41** · R-045 unauthenticated `<img :src>`: `UserAvatar.vue:16–21` → `/users/<id>/image` (same class as `StoreLogo`, 10-R35; both must move to the authed-image helper the chunk-10 finding names). **execute** with 10-R35.
- **13-R42** · R-019 comment≠code: `user.py:324 # TODO: avoid god object | separate auth credential from user profile` — a standing TODO with no FU. **FU** (design; "when a second credential type arrives").
- **13-R43** · `clock.py:6` "App-wide adoption of this boundary is FU-174" — FU-174 is resolved; the live tracker is R-021. **Change:** reword. **execute**.

#### C11. Ride-along signals for FU-010 / FU-224 (theme / colour)
- Two focus-ring tokens (13-R40). · `AccountSettings.vue:391–394` falls back through `--surface-base, var(--surface, transparent)` — check which exists; `SettingsShell.vue:413,432` carry `transparent`/rgba fallbacks for `--border-default`/`--overlay-hover` which **are** defined (`tokens.scss:150,159`) — drop the fallbacks. · `VoicePicker` `--negative` hex fallback. · `UsersAdminSettings.vue:41–43` avatar `color="accent" text-color="dark"` — Quasar palette names, not tokens (D-002 ride-along).


### E. Proposed follow-ups (orchestrator allocates ids)

- **urgent** · bug · `update_app_settings.py:174` returns a tuple on invalid `nutrition_mode` → 500 (13-R1). Resolve now (Stage 2).
- **urgent** · bug · admin email edit skips validation/uniqueness/`email_verified` (13-R2). Resolve now.
- **urgent** · bug · delete-last-admin guard ignores `is_active` (13-R3). Resolve now.
- bug · members never see the Product Search nav entry — URL read from admin-only `/app-settings` (13-R4). Resolve now; publish on `/health`.
- finding · settings-page save/notify/load pattern copied 13× → `useAppSettingField` + `appSettingsStore` (13-R9/R10/R36). Stage 2 of this chunk.
- finding · `/health` probed up to 9× per cold load; `alembic_version` queried per probe (13-R37). Stage 2.
- finding · two focus-ring tokens with different values (13-R40). Fold into FU-010/224.
- finding · `VocabListEditor` not reused by Stores / Dietary tags (13-R17). Stage 2.
- finding · 12 unreachable admin banners duplicate the router guard (13-R13). Stage 2.
- finding · dead `/app-settings/probe` route + client + tests (13-R19). Stage 2.
- finding · R-057 contract drift ×4 in `healthApiService.ts` / `appSettingsApiService.ts` / `authApiService.ts` (13-R16). Stage 2.
- finding · `User` god-object TODO (`user.py:324`) has no tracker (13-R42). Design; later.
- decision · 13-D4 text-size range 87.5–125 % vs feedback 75–150 %. Owner.
- decision · 13-D6 show `version`/`schema_version` on About. Owner.
- decision · 13-R15 drop admin "set another user's picture"; add "Remove picture" to the Users overflow. Owner (default: yes).
- advance · FU-656 → publish `password_min_length` on `/auth/capabilities`, derive the TS constant (13-R12). FU-654 (+2), FU-671 (+2 here, +5 in chunks 16/18), FU-668 (+1), FU-923 (+2 raw-table sites), FU-848 (merge decision), FU-672 (icon duplication nav↔page: the `icon` prop on `TaxonomyManagerPage`/`SettingsPageHeader` still has to be kept in step with `SettingsShell` by hand — resolve by exporting the nav table and looking the icon up by route in `SettingsPageHeader`; Stage 2).
- cross-ref · UserAvatar `<img>` joins 10-R35's authed-image helper (13-R41).

---

## Chunk 14 — Onboarding
*Source: [`CHUNK_14_onboarding.md`](../05_investigations/finalisation/CHUNK_14_onboarding.md) · analysed 2026-10-23*

### C. Senior review — Onboarding

#### C1. Bugs (verified or high-confidence latent)
- **14-R1** · bug · `onboarding.py:685–705` · `SeedDemoHandler` always inserts a **new** `MealPlan(start_date=monday)`; `MealPlan` has no week uniqueness (`table_mappings.py:996–1010`) and nothing looks for an existing plan. A user who made a plan from the "Plan the week" tile, then Continue → Finish with the demo ticked, gets two plans for one week (the planner's duplicate-week hazard, chunk 2). **Change:** look up a plan with `start_date == monday` first (reuse `features/meal_plans` list query via the repository, `EntityField(MealPlan, "start_date").eq(monday)`), append the entry to it, else create. Blast S. Guard: extend `test_onboarding_seed_demo.py` with "existing plan for the week → entry appended, plan count unchanged". **execute**.
- **14-R2** · bug (data quality) · `onboarding.py:582–586` `_DEMO_INGREDIENTS` names "Spaghetti pasta" / "Garlic cloves" vs `starter_packs.json` "Pasta" / "Garlic"; `WelcomeWizard.vue:1384–1386` claims the demo reuses the pack picks — it does for "Olive oil" only. **Change:** rename the two demo ingredients to the pack names ("Pasta", "Garlic") so by-name reuse works; fix the wizard comment. Blast S. Guard: `test_onboarding_seed_demo.py` renames list. **execute**.
- **14-R3** · bug (missing UI the code promises) · `user.py:187–189` "Cleared by the Settings → Account 'Restart onboarding' entry", `DashboardPage.vue:606–607` "Same shape as the AccountSettings 'Restart onboarding' action" — neither exists; `/onboarding/restart` is reachable only via the 24-hour skip banner. **Change (owner-neutral, small):** add a "Run the welcome tour again" row to About → Project & support (chunk 13's AboutSettings list) calling `restartAsync` + `authStore.refreshAsync` + `router.push('/welcome')`, and correct both comments. Blast S. **execute** (owner may prefer Account — default About).
- **14-R4** · latent · `onboarding.py:688–694` · `scheduled_for = today if today >= monday else monday` — `monday = today − weekday` so `today >= monday` is always true; the comment promises a Wednesday fallback the code never does (R-019). **Change:** `scheduled_for = today`; delete the dead branch + fix the comment. Blast S. **execute**.
- **14-R5** · latent · `WelcomeWizard.vue:582–590` stores System as bare `'system'` while Preferences (`themeKeyFor('system', pesto)`) stores `'system-pesto'`; both decode to the same family but two spellings of one choice violate R-003 and the bare key only survives via the legacy branch in `familyAndModeOf`. **Change:** `value: themeKeyFor('system', THEME_FAMILIES[0])` etc. — derive the three cards from themeService. Blast S. **execute**.

#### C2. Redundancy / DRY (R-001, R-003)
- **14-R6** · `onboarding.py:491–498` and `:621–626` both find the Stocked level by `sorted(levels, key=sequence)[0]` while `domain/stock_status.level_for_status(levels, StockStatus…)` is the one authority for "which level is this role". **Change:** one `_stocked_level(repo)` using `level_for_status`; the create-stock-item handler's default-level logic is the same question (chunk 6) — fold there if it already exists. Blast S. **execute**.
- **14-R7** · `onboarding.py:677,698` hardcode `"Dinner"` for `time_of_day` and `slot`; meal slots are a user-editable vocabulary (`MEAL_SLOT_NAMES` is the seed, not the law). **Change:** resolve the slot from `MealSlot` rows (first by sequence whose name is "Dinner", else the last slot) and use it for both fields. Blast S. **execute**.
- **14-R8** · seven endpoint prologues repeat `_current_user_id()` → 401 → `repo.get(User).by_id` → 404 (`onboarding.py:120–127, 136–143, 151–158, 347–350, 440–443, 549–552, 723–726`); `_current_user_id` is itself an 11th copy of the session parse (FU-654). **Change:** `auth/session_user.py: require_session_user(repo) -> tuple[User|None, Response|None]` (the FU-654 helper), used here ×7 and by chunks 11/12/13's sites. Blast S here. **execute** under FU-654.
- **14-R9** · `WelcomeWizard.vue:845–853,855–860` duplicate `AdminSystemRegionSettings.vue:345–353,473` (timezone options filter + device-zone read); `WelcomeWizard.vue:861–866` duplicates `AdminSystemCookingSettings.vue:109–114` (`normaliseHeadcount`). **Change:** `components/settings/TimezoneSelect.vue` (owns `TIMEZONE_CHOICES` + filter) and `models/regionChoices.ts: deviceTimezone()`; `models/household.ts: normaliseHeadcount()` (bounds mirror the server's 1–99 — note it as the one place the TS mirror lives). Blast S (3 files). **execute**.
- **14-R10** · `GetOnboardingStateHandler` (`onboarding.py:101–128`) is built with a second `SqlAlchemyRepository()` after `repo` was already created two lines up. **Change:** pass `repo`. Blast S. **execute**.
- **14-R11** · `seed.py`, `seed_dense.py`, `seed_showcase.py` each re-declare the three `StockLevel` rows, the `canonical_pair` substitute-insert loop, the belief-shop + cook-consume helpers (`seed.py:798–826` ≈ `seed_showcase.py:257–285` ≈ `seed_dense.py:1203–1211`), and the QA-cheese fixture (`seed.py:971–1003` ≡ `seed_dense.py:1687–1715`). FU-556 moved the row builders but not these. **Change:** add `seed_levels()`, `seed_substitutes(pairs)`, `shops_for(item, …)`, `cook_consume(…)`, `seed_qa_verdict_fixture()` to `SeedBuilders`. Blast M (dev-only code). **execute** (low risk: seeds are exercised by `test_onboarding_seed_demo` + boot).

#### C3. Dead code / unused fields / unread endpoints
- **14-R12** · `OnboardingStateDto.completed`, `.completed_at`, `.store_status` (`onboarding.py:82–98`) and the TS `StoreStatus`/`OnboardingState.completed*` (`models/onboarding.ts:4–14`) — grep: the wizard reads only `first_user`; `StoreStatusDto` is self-described as "kept for payload compatibility" with a shape no client reads. **Change:** trim the DTO to `{first_user}` (+ the `GET /onboarding/state` test if one lands). Blast S. **execute**.
- **14-R13** · `OnboardingLoop.vue:83–91` props `autoplay`/`interactive` — one consumer passes neither; the "Finish-step recap passes false" comment refers to a recap removed 2026-10-17; `doraMood = computed(() => 'happy')` is a constant. **Change:** drop both props and the computed; `shouldAnimate = !prefersReducedMotion`. Blast S. **execute**.
- **14-R14** · `WelcomeWizard.vue:984–985,1016–1017,1068–1073,1086–1088,1123–1129` — the pre-FU-195 `seedGroups`/`seedLocations` legacy-draft fold. The draft key is per user and the wizard was rebuilt twice since; no live draft can carry those booleans. **Change:** delete the legacy branch. Blast S. **execute**.
- **14-R15** · `models/onboarding.ts:16–35` `SeedRequest`/`SeedResult` comments and `onboarding.py:1–16` module docstring ("Four endpoints"; "Seed catalogues … groups / locations" only) describe the pre-C-5.5 surface — seven endpoints, three catalogues (R-019). **Change:** rewrite both. **execute**.
- **14-R16** · stale comments: `onboardingContent.ts:47–49` ("the price-memory claim lives on the provisional `LOOP_INSIGHT` node below" — removed), `OnboardingLoop.vue:256` ("Centre: Dora + the provisional Insight candidate"), `seed_showcase.py:16–20` ("Both seeds duplicate a handful of tiny local builders … logged as a DRY follow-up" — FU-556 shipped), `IMPL_PLAN_ONBOARDING.md §0` "already true" list (predates the rebuild). **Change:** fix the three code comments; add a one-line "superseded by the 2026-10-17/21 rebuild — see CHUNK_14" note at the top of the impl plan's §0. **execute**.

#### C4. Componentisation opportunities (R-001)
- **14-R17** · `WelcomeWizard.vue` is 2,078 lines holding four steps + the finish recap + the apply pipeline. The components it already extracted (pick panel, rail, story) leave the welcome/features/finish templates and ~700 lines of CSS inline. **Change:** `OnboardingWelcomeStep.vue` (avatar + theme cards + font), `OnboardingFeaturesStep.vue` (household panel + `FEATURE_CARDS`), `OnboardingFinishStep.vue` (hero + recap + tiles); the wizard keeps state + `applyDraft`. The `.feature-card` CSS is used by both the features step and the demo toggle on Finish — one `FeatureToggleCard.vue`. Blast M (pure move, props in / events out). **execute** (same shape as the page-split FU chunk 4 raised for cook mode; do this one now because the file is already past the R-001 line).
- **14-R18** · theme card mini-mock-up (`WelcomeWizard.vue:145–158, 1687–1725`) vs Preferences' swatch strips (`PreferencesSettings.vue:44–51`) — two previews of a theme. **Change:** keep both (different fidelity on purpose) but move the `data-theme`-painted mock-up into `ThemePreviewCard.vue` so Preferences can adopt it later. Blast S. **FU** (opportunistic; owner may like the mock-up in Preferences).

#### C5. Placement / layering (R-003, R-005)
- **14-R19** · `WelcomeWizard.vue:1397–1413` creates the user's own groups/locations client-side with per-name existence checks (two extra GETs + N POSTs) while `POST /onboarding/seed-items` already resolves names server-side and `SeedHandler` dedupes by name. **Change:** extend `SeedRequest` with `extra_group_names` / `extra_location_names` so the server creates them in the same unit of work (FU-512's single commit then covers the user's own entries too). Blast S/M. **execute**.
- **14-R20** · `onboarding_catalog` re-reads three JSON files per request (`onboarding.py:444–452`); `_load_seed` is called again inside `SeedHandler`. **Change:** `functools.lru_cache` on `_load_seed` (files are bundled, immutable at runtime). Blast S. **execute**.
- **14-R21** · `WelcomeLayout.vue:31–32` hardcodes `#1e2a26` / `#ffffff` while the layout already pins `data-theme="pesto-dark"` so the tokens are the right values. **Change:** `background: var(--surface-page); color: var(--text-primary);` (R-002). Blast S. **execute**.

#### C6. Naming & idiom
- **14-R22** · `WelcomeWizard.vue:497` `:icon-right="isLastStep ? 'check' : 'arrow_forward'"` bare icon names (R-034). **Change:** `ICONS.check` / `ICONS.arrow_forward`. **execute**.
- **14-R23** · `onboarding.py` mixes `_LOGGER` (module const) with the codebase's `_Logger`/`logging.getLogger(__name__)` idiom used elsewhere; also `request` shadows the Flask name in four handlers (`seed_onboarding`, `seed_items_onboarding`). **Change:** rename to `_Request` per `update_app_settings.py`. **execute**.
- **14-R24** · `ICONS.mealsPrepared` (`icons.ts:353`) is the registry's only camelCase key. **Change:** `meals_prepared` + the two call sites. **execute** (fold into FU-692's icon pass).

#### C7. Efficiency
- **14-R25** · `SeedHandler._find_existing` (`onboarding.py:329–342`) does a full `StockLocation.all()` scan per existing zone inside the zone loop, right after building `existing_pairs` from the same query. **Change:** build a `{(parent, name): entity}` map once and index it. Blast S. **execute** (with 14-R19).
- **14-R26** · `WelcomeWizard.vue:1143–1151` deep-watches twelve reactive sources and serialises the whole draft to `localStorage` on every keystroke. **Change:** debounce 300 ms. Blast S. **execute**.

#### C8. Design-level findings — out of Stage-2 scope
- **14-D1** · Feedback L46 (stock-item vs product explainer before adding items) is **dropped by the products-as-overlay pivot** (no products exist on day 1, so the conditional explainer never fires) — `COVERAGE_GAPS.md:175` already says so. Chunk 10's help entry "Stock items vs products" is where the explanation now lives. No change.
- **14-D2** · Finish is a multi-request apply; a failure midway leaves prefs/settings written (seeds are idempotent, so re-Finish converges). A single server-side `POST /onboarding/finish` taking the whole draft would make it atomic — real work, not a tidy; owner call whether the partial-apply window matters.
- **14-D3** · Story scene 4's illustrative switches show "AI assistant — on" by default; AI mode is per-user opt-in and off. Flip the illustration to `on: false` for honesty (P3) — one-line, but it is copy, so owner's.
- **14-D4** · Showcase `demo` user is created without `onboarding_completed_at`, so every demo reset re-shows the wizard. Owner: is that the intended showcase first impression, or should the demo land on a populated dashboard?
- **14-D5** · "Skip onboarding" label vs feedback L35 "just say Skip" — the longer label was chosen when the button moved to the top row; fine either way.
- **14-D6** · Locale/currency are still not asked at first run (FU-632 #48's other half); timezone + units now are. Adding "Language & format" to the household panel (pre-filled from `navigator.language`, reusing Region's `LOCALE_CHOICES`) is a small addition the owner should OK — it changes every date/money render on the install.

#### C9. Hand-rolled-vs-library verdicts
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| `OnboardingConfetti.vue` | 40 CSS-animated spans, deterministic | `canvas-confetti` | **keep** | – | 70 lines, reduced-motion aware, no dep. |
| `OnboardingLoop.vue` ring | SVG circle + positioned buttons | d3 / anime.js | **keep** | – | One `pathLength` trick; no library earns its weight. |
| `OnboardingStepRail.vue` | dots rail | `q-stepper` | **keep** | – | Non-linear, two sections; q-stepper is linear by design. |
| `OnboardingPickPanel.vue` chips | role=checkbox buttons | `q-chip selectable` | **keep** | – | Caption + removable variants; q-chip can't carry both cleanly. |
| Wizard draft in `localStorage` | hand JSON round-trip | VueUse `useStorage` (not a dep) | **keep** | – | Debounce it (14-R26). |
| `q-select` ×4 in the wizard | timezone, group, location pickers | `BaseSelect` | **replace** | S | FU-675's migration list +4. |

#### C10. Standards drift (R-0NN)
- **14-R27** · R-002: `WelcomeLayout.vue:31–32` hex literals (14-R21); `OnboardingConfetti.vue:25` `var(--q-info)` is a Quasar palette var, not a Dora token → `var(--semantic-info)`. **execute**.
- **14-R28** · R-034: bare icon strings (14-R22). **execute**.
- **14-R29** · R-019 comment≠code: 14-R4, 14-R15, 14-R16, and `user.py:187–189` / `DashboardPage.vue:606–607` (14-R3). **execute**.
- **14-R30** · R-021: `seed.py:72`, `seed_dense.py:123`, `seed_showcase.py:82` use `date.today()` (server-local) and `seed_dense.py:1387` stamps consumption at 19:00 **UTC**; `onboarding.py:688` correctly uses `household_today`. Dev seeders only — **waive** with an inline `# R-021 carve-out: dev fixture, server-local date is fine` on each.
- **14-R31** · D-002 ride-along: `WelcomeWizard.vue:77–78,383–384` `UserAvatar color="accent" text-color="dark"` Quasar palette names (same as 13-C11). **FU** (FU-010/224 sweep).

#### C11. Ride-along signals for FU-010 / FU-224 (theme / colour)
- `WelcomeLayout` hex pair; `--q-info` in confetti; `.loop-node.is-active` uses `var(--surface-component)` as **text** colour on a brand-primary fill (should be `--text-on-primary`, FU-674's token) — `OnboardingLoop.vue:236,243`; `.finish-tile__num` already uses `--text-on-primary` ✓.


### E. Proposed follow-ups (orchestrator allocates ids)

- **urgent** · bug · demo seed inserts a second meal plan for the current week (14-R1). Stage 2.
- bug · demo ingredient names don't match the starter packs → duplicates (14-R2). Stage 2.
- bug · promised "Restart onboarding" entry doesn't exist; only the 24-h banner reaches `/restart` (14-R3). Stage 2 (About row) — owner may redirect to Account.
- finding · `WelcomeWizard.vue` 2,078 lines → three step components + `FeatureToggleCard` (14-R17). Stage 2.
- finding · own groups/locations created client-side outside the seed's unit of work (14-R19). Stage 2.
- finding · seeders still duplicate levels / substitutes / belief-shop / QA-cheese blocks post-FU-556 (14-R11). Stage 2, dev-only.
- finding · dead `OnboardingStateDto` fields + legacy draft fold + stale comments (14-R12/R14/R15/R16). Stage 2.
- decision · 14-D2 atomic `POST /onboarding/finish`. Owner.
- decision · 14-D3 story switch panel shows AI on. Owner (default: flip to off).
- decision · 14-D4 showcase demo user re-sees the wizard on every reset. Owner.
- decision · 14-D6 ask locale at first run (closes FU-632 #48 fully). Owner.
- advance · **FU-632 #48**: timezone + units are now collected on the first user's features step (since 2026-10-17); only locale remains — update the entry. **FU-578 #38** (jargon explainer) and **#39** (Price-history dead-end; no guided add-items step) are resolved by the 2026-10-17/21 rebuild — strike them in the FU body. **FU-654** +1 site (14-R8). **FU-675** +4 `q-select`s. **FU-692** +1 (`mealsPrepared` key). **FU-674** +1 (`.loop-node.is-active` ink).
- close-out · `PROPOSAL_ONBOARDING.md` §2.3.a and §3.2.a are still headed "Open thread" though both were overtaken (personas removed FU-210; products-as-overlay). Add the "Open decisions — closed" line pointing at FU-210 + `PROPOSAL_PRODUCTS_AS_OVERLAY.md`; mark `IMPL_PLAN_ONBOARDING.md` §0 superseded. Stage 2 doc tidy.

---

## Chunk 15 — Auth shell
*Source: [`CHUNK_15_auth_shell.md`](../05_investigations/finalisation/CHUNK_15_auth_shell.md) · analysed 2026-10-23*

### C. Senior review — Auth shell

#### C1. Bugs (verified or high-confidence latent)
- **15-R1** · bug (deployment-shaped) · `auth_helpers.py:317–322`, `audit.py:199`, `submit_client_log.py:63` read `request.remote_addr` with no `ProxyFix`; the documented self-host shape is a reverse proxy, so every client arrives as the proxy's address: one shared login bucket (5/min for the whole household), one shared register bucket, and audit rows all carry the proxy IP. **Change:** wrap the WSGI app in `werkzeug.middleware.proxy_fix.ProxyFix(app.wsgi_app, x_for=N, x_proto=N)` **gated by a new env `DORA_TRUSTED_PROXY_HOPS`** (default `0` = off — trusting `X-Forwarded-For` blindly lets a direct client spoof its address, so the operator opts in); document it beside `DORA_SECURE_COOKIES` in the ops notes (chunk 19). Blast S. Guard: new pytest "`DORA_TRUSTED_PROXY_HOPS=1` → `remote_addr` comes from `X-Forwarded-For`". **execute**.
- **15-R2** · bug (security hygiene) · `middleware.py:274–284` `audit_incoming_request` logs `request.get_json()` for every request at DEBUG; `logging_setup.py:18` makes DEBUG the dev default. A developer signing in on a dev box writes `{"username":…,"password":…}` to the rotating log file. **Change:** skip the body dump when `endpoint_name in PUBLIC_ENDPOINTS` (every auth route) and redact keys matching `password|token|api_key` elsewhere (`new_password`, `current_password`, `smtp_password`, `vapid_private_key`, provider API keys all travel through authenticated PATCHes). Blast S. Guard: unit test on the redactor. **execute**.
- **15-R3** · bug (contract) · `register_user.py:338–347` adds `verification_sent` to the response "so the SPA can decide whether to surface a 'check your email' toast"; no SPA code reads it (R-057), so a registrant who gave an address is never told to look for the mail. **Change:** `LoginPage.onSubmit` register branch toasts "Check your inbox for a verification link" when `verification_sent`; add the field to `AuthenticatedUser`'s register response type. Blast S. **execute**.
- **15-R4** · latent · `csrf.clear_cookie` (`csrf.py:106–108`) is never called; `logout.py` clears the session but leaves `dora_csrf`. Not a vulnerability (the token is not a credential and is re-minted on the next response) but the module's own contract says it is paired with `session.clear()`. **Change:** call it from `logout()` (and on the `get_me` session-clear branches) or delete the function; prefer the call. Blast S. **execute**.
- **15-R5** · latent · `axiosHttpClient.ts:48–55` says the 401 handler "clear[s] user state, redirect[s] to /login"; `authStore.handleSessionExpired` (`:161–168`) only clears. A user parked on a page after a silent 401 sees emptied cards with no redirect until they navigate. **Change:** in the handler, `if (!PUBLIC_PAGE) window.location.hash = '#/login?redirect=' + current` (the store cannot import the router without a cycle; a hash assignment is the honest minimum) — or pass a navigation callback from the router setup. Blast S. **execute** (confirm in browser first — may already be masked by the next fetch failing fast).

#### C2. Redundancy / DRY (R-001, R-003)
- **15-R6** · `pages/ErrorNotFound.vue` (237 lines) re-implements AuthShell's backdrop, blobs, mascot bob, glass card and the whole `--lost-*` palette (`:60–70` ≡ `AuthShell.vue:87–98`); it predates C-19 and was left out of IMPL_PLAN step 6. **Change:** `<AuthShell backdrop="blobs" mascot="top-right">` with the 404 copy in `#card-head` and an `AuthButton colour="primary" to="/"`; delete the local CSS. Also answers the `# NO AREA / MISC` "404 page theme" bullet. Blast S. **execute**.
- **15-R7** · five hand-rolled 429 responses (`bootstrap_admin.py:73–83`, `email_flows.py:47–57`, `register_user.py:351–362`, `login.py:63–75`, `assistant/ask_assistant.py:72–86`) and one `_validation_failure` helper (`email_flows.py:60–65`) beside six inline RFC-4918 literals (chunk 13-R14). **Change:** `api_response.too_many_requests(retry_after, detail=…)` and `api_response.validation_failed(errors)`; also `api_response.gone(detail)` for `bootstrap_admin._gone` and reuse the existing `conflict()` for `register_user.py:282–296`'s inline 409. Blast S (6 files). Guard: `test__login__rate_limit_returns_429_eventually`, `test__bootstrap_admin__rejects_when_users_exist`. **execute** (merges 11-R15).
- **15-R8** · password-reveal eye toggle written four times (`LoginPage.vue:52–59`, `SetupAdminPage.vue:54–61`, `settings/PasswordSetter.vue:16–31`, `MyProductsPage.vue`); min-length rule hardcoded as `8` in two of them (`LoginPage.vue:49`, `SetupAdminPage.vue:51`) beside `models/password.ts` (13-R12 found the Account page's four). **Change:** `components/PasswordField.vue` (q-input + reveal + `MIN_PASSWORD_LENGTH` hint/rule, `autocomplete` prop); Login, Setup, Reset, Account and PasswordSetter become callers. Blast S/M. **execute**.
- **15-R9** · `SplashScreen.onChangeInstance` (`:93–129`) is a declared "mirror of `AboutSettings.onChangeInstance`" (`AboutSettings.vue:352–397`). **Change:** `composables/useChangeInstance.ts` returning `promptAndSave()`; both call it (About adds the router replace, Splash the reload). Blast S. **execute**.
- **15-R10** · the DEC-2 ladder is one place by design, yet `#fff` (`AuthButton.vue:76`, `SetupAdminPage.vue:147`, `BackendSetupPage.vue:121`), `#3a2a08` (`AuthButton.vue:87`) and `#ffffff` ×4 (`SplashScreen.vue:242–274`) sit outside it, and `SplashScreen.vue:236–238` explains that `--auth-shell-text` is wrong on the canvas. **Change:** add `--auth-shell-on-accent: #fff`, `--auth-shell-on-amber: #3a2a08`, `--auth-shell-on-canvas: #fff` to the ladder and use them. Blast S. **execute** (R-002).
- **15-R11** · `SetupAdminPage.vue:139–153` and `BackendSetupPage.vue:113–125` carry the same `.setup-badge` pill (gradient, uppercase, 999px). **Change:** `#card-badge` slot on AuthShell with the pill styled there, or an `AuthBadge.vue`. Blast S. **execute**.
- **15-R12** · `test_route_auth_enforcement.PINNED_ADMIN_ENDPOINTS:177` pins `/api/app-settings/probe`; 13-R19 deletes that route. **Change:** drop the row in the same Stage-2 commit as 13-R19 (the reverse-count test enforces it). **execute** (with 13-R19).
- **15-R13** · `middleware.CSRF_EXEMPT_ENDPOINTS = PUBLIC_ENDPOINTS | {submit_ingestion_batch, ingest_link_status}` — both names are already in `PUBLIC_ENDPOINTS` (`:52,55`), and the four newer bearer endpoints aren't in the explicit set either, so the comment describes a distinction the code no longer makes. **Change:** `CSRF_EXEMPT_ENDPOINTS = PUBLIC_ENDPOINTS` + a comment that bearer routes are public-by-session and bearer-checked in-handler. **execute**.
- **15-R14** · the literal `"user_id"` session key (`logout.py:15`, `middleware.py:79,233`, `submit_client_log.py:63`) alongside `SESSION_USER_ID_KEY` everywhere else (R-003). **Change:** import the constant (move `SESSION_USER_ID_KEY`/`SESSION_PWD_V_KEY` out of `register_user.py` into `auth/session_keys.py` so `middleware` isn't importing a feature module — also the natural home for FU-654's resolver). **execute**.

#### C3. Dead code / unused fields / unread endpoints
- **15-R15** · `csrf.clear_cookie` unused (14-R4 decides: call it). · `RegisterUserResponse.verify_username` duplicates `request.username` the route already holds. · `auth_helpers.__all__` exports `PURPOSE_*` it only re-imports. **Change:** trim with 15-R7. **execute**.
- **15-R16** · `BackendSetupPage.vue:80–85` probes with a bare `axios.get(url + '/auth/me')` — no `X-Request-Id`, no shared timeout policy, a second axios instance. **Change:** after `setBackendBaseUrl`, call `new AuthApiService().getMeAsync()` (it already treats 401 as "answered") inside the same try/rollback. Blast S. **execute** (R-003; also removes a raw-client site from FU-571's list).

#### C4. Componentisation opportunities (R-001)
- Covered by 15-R6 (404 → shell), 15-R8 (`PasswordField`), 15-R11 (badge). Nothing further — `AuthShell`/`AuthButton` are the right size.

#### C5. Placement / layering (R-003, R-005)
- **15-R17** · R-019 comment≠code: `register_user.py:4` and `auth_helpers.py:4` still state the retired policy "min 10 chars, ≥1 letter + ≥1 digit" (policy is min 8, no composition — `auth_helpers.py:44–67`); `capabilities.py:4–6` "exposes just one flag" (two); `test_auth_flows.py:171–179` describes the retired verified change-email flow; `PROPOSAL_AUTH_SHELL.md §7` heading "Open decisions — for you" + D4's `ConfirmEmailChangePage`. **Change:** fix the four comments; add "Open decisions — closed 2026-07-02, see IMPL_PLAN §0" under §7. **execute**.
- **15-R18** · `register_user.py:344` and `change_password.py:108–109` each open a second `SqlAlchemyRepository()` to re-read the user the handler just saved. **Change:** return the entity (or its email) from the handler. Blast S. **execute**.
- **15-R19** · `login.py:103,121` and `register_user.py:282–283` import inside the function body for no cycle reason (`SESSION_PWD_V_KEY`, `get_provider_config`, `jsonify`). **Change:** module-level imports (cycle-safe — same package). **execute**.

#### C6. Naming & idiom
- **15-R20** · R-034 bare icon names: `LoginPage.vue:54`, `SetupAdminPage.vue:5,56`, `VerifyEmailPage.vue:5` (`'mark_email_read' | 'error' | 'mail_lock'`), `BackendSetupPage.vue:5` (`dns`). **Change:** `ICONS.*` (add `mail_lock`, `error`, `dns` to the registry if absent). **execute**.
- **15-R21** · f-string logging with the `%s` idiom beside it: `login.py:82,94,112`, `register_user.py:298,301,337`, `change_password.py:134`, `bootstrap_admin.py:207`, `logout.py:35`. **Change:** `%s` args. **execute**.
- **15-R22** · `LoginRequest` fields use `Field(min_length = 1, …)` with spaces around `=` (`login.py:28–29`) — the one file in the package with that style. **execute**.

#### C7. Efficiency
- **15-R23** · `find_active_token` (`auth_helpers.py:184–214`) loads **every** live token of a purpose and compares each hash in Python (constant-time per row). Correct, and O(live tokens) is tiny for a household; for a managed instance with many users a `WHERE token_hash = :h` lookup (the hash is deterministic — equality in SQL leaks nothing the timing-safe compare protects) is the standard shape. **Change:** query by `token_hash` then re-verify with `compare_digest`. Blast S. **execute** (comment the reasoning).
- **15-R24** · `bootstrap_required` runs a `COUNT(*)` on `User` on every cold load for every client; `bootstrap_admin` counts twice. Fine for a household; a `SELECT 1 … LIMIT 1` (`exists`) is the honest query. **waive** (negligible; note only).

#### C8. Design-level findings — out of Stage-2 scope
- **15-D1** · Feedback "allow admins to turn the restrictions off" — **deliberately not built** (`auth_helpers.py:65–67`: NIST posture, no operator override). Record as out-of-scope with reason; the only remaining restriction is min 8 + a 60-word deny list, so the ask is largely moot.
- **15-D2** · A.5 (admin-set password returned in plaintext once, when generated) stays accepted — it is the self-host fallback; A.6 (in-memory rate limit) stays accepted for single-instance but **15-R1 makes it per-client**, which is the part that actually bites today; A.7 (token in URL) stays accepted.
- **15-D3** · `WelcomeLayout` pins `data-theme="pesto-dark"` rather than wrapping `AuthShell` as D3 of the proposal decided; the 2026-10-17 wizard rebuild chose a flat dark canvas on purpose (CHUNK_14). Feedback L24 "same styling as login" is therefore met in spirit (dark continuity) not letter (no blobs/mascot). Owner: accept as is (default) or wrap.
- **15-D4** · `authStore.handleSessionExpired` redirect (15-R5) — if the owner prefers "stay on the page and show a sign-in dialog", that is a design change; the default above is the minimal redirect.
- **15-D5** · Register is a mode toggle on the login card rather than its own route — fine, but there is no way to deep-link to "create account" (e.g. from an invite). Note only.

#### C9. Hand-rolled-vs-library verdicts
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| `auth_helpers.rate_limit` | in-memory sliding window | `Flask-Limiter` | **keep** (single-instance posture, A.6) | – | Add `ProxyFix` (15-R1); revisit at Phase-4 scaling with a shared store. |
| `csrf.py` double-submit | hand-rolled | `Flask-WTF` CSRF | **keep** | – | 100 lines, tested, matches the SPA's cookie-echo model; Flask-WTF assumes forms. |
| `auth_helpers` token plumbing | SHA-256 + `AuthToken` table | `itsdangerous` signed tokens | **keep** | – | Server-side revocation (single-use, sibling revoke) needs the table anyway. |
| `axiosHttpClient` retry/backoff | hand-rolled | `axios-retry` | **keep** | – | Boot-probe-specific ceilings; 40 lines. |
| `AuthShell` blobs/mascot | CSS | – | **keep** | – | FU-797 mitigation in place. |
| Password policy deny-list | 60 bundled words | HIBP k-anonymity API | **keep** | – | Offline self-host (R-005); documented. |

#### C10. Standards drift (R-0NN)
- **15-R25** · R-002: hex outside the DEC-2 ladder (15-R10) and the duplicated ladder (15-R6). **execute**.
- **15-R26** · R-034: bare icons (15-R20). **execute**.
- **15-R27** · R-019: stale policy/flag/flow comments (15-R17). **execute**.
- **15-R28** · R-057 contract: `verification_sent` emitted, never typed or read (15-R3). **execute**.
- **15-R29** · R-003: the session-key literal (15-R14); FU-654 +2 sites here (`change_password.py:75–82`, `logout.py:15`). **execute** under FU-654.
- **15-R30** · R-005 distribution posture: no proxy-awareness knob (15-R1) — the one gap the §7.5 checklist would have caught. **execute**.

#### C11. Ride-along signals for FU-010 / FU-224 (theme / colour)
- The auth ladder is a deliberate R-002 carve-out (DEC-2) — leave it; only the leaks (15-R10) and the duplicate (15-R6) move. `ErrorServer`/`PageErrorState` (in-layout) are themed normally — fine.


### E. Proposed follow-ups (orchestrator allocates ids)

- **urgent** · bug · no `ProxyFix` → per-install rate limits + proxy IP in audit behind a reverse proxy (15-R1). Stage 2; env-gated.
- **urgent** · finding (security hygiene) · DEBUG body logging captures login passwords and every secret-bearing PATCH (15-R2). Stage 2.
- bug · `verification_sent` has no reader; registrants aren't told to check mail (15-R3). Stage 2.
- finding · fullscreen 404 duplicates the auth-shell palette and chrome (15-R6). Stage 2.
- finding · five 429 builders + validation/gone/conflict literals → `api_response` helpers (15-R7, merges 11-R15 + 13-R14). Stage 2.
- finding · `PasswordField` ×4 copies + hardcoded 8 ×2 (15-R8; with 13-R12 / FU-656). Stage 2.
- finding · silent-401 handler clears state but never redirects (15-R5). Confirm in browser, then Stage 2.
- finding · `clear_cookie` never called (15-R4). Stage 2.
- decision · 15-D3 wrap `WelcomeLayout` in `AuthShell` (proposal D3) vs keep the flat dark canvas. Owner (default keep).
- decision · 15-D4 session-expiry UX (redirect vs dialog). Owner (default redirect).
- advance · FU-654 +2 (`change_password`, `logout`); FU-655 unchanged (closes with 654); FU-656 → resolve via 15-R8 + 13-R12 (publish `password_min_length` on `/auth/capabilities`); FU-571 −1 raw-client site (15-R16); FU-797 stays a verify item.
- close-out · `PROPOSAL_AUTH_SHELL.md §7` gets its "closed" line; D4's `ConfirmEmailChangePage` struck (FU-620). Doc tidy at Stage 2.

---

## Chunk 16 — Ingestion API + companion seam
*Source: [`CHUNK_16_ingestion_api.md`](../05_investigations/finalisation/CHUNK_16_ingestion_api.md) · analysed 2026-10-23*

### C. Senior review — Ingestion API + companion seam

#### C1. Bugs (verified or high-confidence latent)

**16-R1 — The power-user guide documents a payload the API rejects.** class: docs-as-contract · where: `docs/INGESTION_GUIDE.md:46–53, 108, 172` (and `PROPOSAL_INGESTION_API.md:§2.2` lines 70–76) · what's wrong: the required store field is documented as `merchant` (Phase-E rename made it `store`, and `store_id` was added 2026-10-15); `extra="forbid"` means a reader following the guide gets `400 Malformed payload … Extra inputs are not permitted … Give exactly one of store or store_id`. The guide also still says "Dora merchants"/`merchant_id` for the mapping table, and documents **none** of `store_id`, `image`, `GET /api/ingest/products`, `DELETE /api/ingest/products/<id>`, `GET /api/ingest/stores(+/image)`, `POST /api/ingest/link-status`. The proposal §2.2 additionally lists `valid_until` (never built — grep: none) and omits `image` (FU-924 d). · exact change: rewrite guide Step 2 (stores, not merchants; `store` **or** `store_id`), Step 3 field table (`store`/`store_id`, `image`, drop `merchant`), add a "Read-side endpoints" section (products list + paging, link-status, stores + image, delete) with one `curl` each; in the proposal §2.2 replace the payload block with the current shape and strike `valid_until` with a one-line "never built" note · blast: S (docs) · guard: none — the A6.4 release row is the check · verdict: **execute** · tracked: FU-924 (d) partially.

**16-R2 — Replaying an `Idempotency-Key` after its 7-day TTL raises on commit (500) and loses the batch.** class: verified latent bug · where: `submit_ingestion_batch.py:245–271` · what's wrong: `_already_processed` returns `False` for an **expired** row (:258–261, comment "the new write will replace it") but `_stamp_idempotency` (:264–271) *adds* a second `IdempotencyKey` with the same `(source_id, key)` — the unique index `ix_idempotency_key_source_key` (`table_mappings.py:1320`; migration `e7a1c3b8d5f4:42`) rejects it at `save_changes()` (:240), **after** the whole batch has been applied in the session, so the IntegrityError rolls everything back and the producer sees a 500. Any producer that reuses a stable key (the companion's `idempotency_key` parameter — "e.g. the scheduler tick id") will hit this a week after first use. · exact change: have `_already_processed` return the existing row (or `None`); when it is expired, refresh `expires_at`/`created_at` on that row in `_stamp_idempotency` instead of adding; when absent, add. Fix the misleading comment. · blast: S · guard: none → D1 (must-write) · verdict: **execute**.

**16-R3 — Idempotency rows are never purged; "the table stays bounded" is false.** class: verified · where: `submit_ingestion_batch.py:68–71, 264–271`; `idempotency_key.py` docstring · what's wrong: nothing reads `expires_at` except the single-row lookup; every companion save generates a fresh `uuid4` key (`dora_ingest.py:217`) → one row per push, forever. Revoking a source also orphans its rows (`source_id` is `String(36)` with no FK). · exact change: in `_stamp_idempotency`, before adding, delete rows where `expires_at < now` (repository `.all(field_expires.lt(now))` → `remove`, or one bulk `delete()`); one line, bounded by the TTL. · blast: S · guard: D2 (nice) · verdict: **execute**.

**16-R4 — `GET /api/ingest/stores` and `/stores/<id>/image` never stamp `last_used_at`.** class: verified inconsistency · where: `get_ingest_stores.py:43–62, 65–80` vs the other four bearer routes (`submit_ingestion_batch.py:234`, `get_link_status.py:260`, `get_ingestable_products.py:180`, `delete_ingested_product.py:60`) · what's wrong: a source that only lists stores (the companion's first-run store sync, `check_target` aside) shows "Never used" on the API access page. · exact change: in `ingest_list_stores`, keep the returned `source`, call `stamp_used(source)` + `SqlAlchemyRepository().save_changes()` (mirror `get_ingestable_products.py:176–181`); leave the image route alone (cached, hot). · blast: S · guard: D4 · verdict: **execute**.

**16-R5 — A product pushed without an offer lands as an *available* product at $0.00.** class: verified latent (contract gap) · where: `submit_ingestion_batch.py:398–418` (`ProductOffer(price_now=0.0, price_was=0.0)`, `is_available=True`); companion `dora_ingest.build_payload:185–187` (omits the offer when `price_now <= 0`, i.e. out of stock / price unavailable) · what's wrong: the SPA renders `formatMoney(price_now ?? 0)` → "$0.00" (`ProductCard.vue:59`) and never shows the OUT OF STOCK badge because `is_available` is hardcoded `True`, although the badge exists (`ProductCard.vue:38`, `ProductRow.vue:39`) and the companion already holds `is_available` (`_OfferLike:42`) — it just isn't on the wire. The comment at :394–397 ("v1 producers always push an offer") no longer holds since the companion's price normalisation (FU-918 fix). · exact change (two repos): add `is_available: bool | None = None` to `_ProductIn`; on create set `is_available=raw.is_available if not None else True`, on update `existing.is_available = raw.is_available if raw.is_available is not None else existing.is_available`; companion `build_payload` sends `"is_available": offer.is_available`. Leave the $0 initial offer (changing `current_offer` nullability is L). · blast: M (cross-repo) · guard: D3 · verdict: **FU** (needs the companion change in the same window; owner-visible behaviour) · see §E.

**16-R8 — `link-status` reports a hand-entered (custom) product as "already in Dora"; the companion's *unsave* then deletes it.** class: verified · where: `get_link_status.py:179–201` (`_find_product` — no `is_custom` filter) vs `submit_ingestion_batch.py:345–370` (`not_custom` on both lookups, OD-2) · what's wrong: read and write disagree on identity. A user who typed "Mince" at Woolworths, then searches "Mince" in the companion, sees a filled heart (in Dora + maybe linked), and tapping it calls `DELETE /api/ingest/products/<custom id>` → `DeleteProductHandler` removes the user's own product (the delete door has no custom guard either — PF-4 says it shouldn't need one, because the id should never have been handed out). · exact change: extract `find_ingested_product(repository, store_id, stockcode, name) -> Product | None` (stockcode-first, name fallback, `not_custom`) into `features/ingestion/product_identity.py`; use it from both `_apply_product` and `_find_product`. · blast: S · guard: D5 (must-write) · verdict: **execute**.

**16-R34 — Validation errors go to the producer as one concatenated pydantic string.** class: verified (feedback-linked) · where: `submit_ingestion_batch.py:476–479`, `get_link_status.py:253–256` (`"errors": str(exc)`) · what's wrong: `str(ValidationError)` is the multi-line text the owner saw as *"Extra inputs are not permitted Extra inputs are not permitted …"* ×5 (feedback `# PRODUCT SEARCH` bullets 9–11); the companion surfaces `response.text[:500]` verbatim (`dora_ingest.py:243`). · exact change: return `exc.errors(include_url=False)` (a list of `{loc, msg, type}`) under `errors`, keep `detail`; or route both through `has_request_body` / 15-R7's `api_response.validation_failed`. · blast: S (the companion only displays it) · guard: `test_ingest_batch::test__ingest__rejects_price_observations_field` asserts on the text — adjust to the list · verdict: **execute** (with 16-R9).

#### C2. Redundancy / DRY (R-001, R-003)

**16-R6 — The store-mapping lookup is written three times.** where: `submit_ingestion_batch.py:283–292` (write side, quarantines), `get_link_status.py:166–175` (read side), `store_mappings.py:116–125` (admin upsert) — each builds `EntityField(SOURCE_ID)` & `EntityField(EXTERNAL_NAME)` and `.one(...)`. change: `IngestionStoreMapping` gets a module-level `find_mapping(repository, source_id, external_name)` (or a static on the entity's repository helper); three call sites. blast: S · guard: existing 6 mapping tests + 3 quarantine tests · verdict: **execute**.

**16-R7 — `_stamp_linked_stock_items` re-implements `product_links.linked_stock_items`.** where: `get_link_status.py:203–241` (39 lines, raw `db.metadata.tables["StockItemProduct"]` select + `StockItem` lookup) vs `products/product_links.py:25` which already returns `{product_id: LinkedStockItem(stock_item_id, name)}` and is shared by the products list, best-deals and the price-drop alert. The docstring (:208–213) explains why it isn't the *DTO-mutating* helper — but the lower-level map helper is right there. change: `links = linked_stock_items(self.repository, [p.id for _, p in resolved])`, then build the `_LinkStatusResult`s; delete the private method, the `select`/`db`/`StockItem` imports. blast: S · guard: `test_ingest_link_status` (9) · verdict: **execute**. Also clears one FU-923 raw-table reader.

**16-R9 — Two bearer routes hand-roll the body-parse-and-400 that `has_request_body` already does.** where: `submit_ingestion_batch.py:476–479`, `get_link_status.py:253–256` vs `@has_request_body(...)` on every admin route in this chunk. change: decorate both routes, read with `get_request_body()`; the decorator's error shape then also fixes 16-R34 (verify it emits structured errors; if it emits text, fix it there — one place). blast: S · guard: the two `rejects_*` tests · verdict: **execute**.

**16-R10 — `_one_store` validator duplicated.** where: `submit_ingestion_batch.py:109–113`, `get_link_status.py:74–78`. change: `class _StoreRef(BaseModel)` mixin with `store`/`store_id` + the validator in `product_identity.py` (16-R8's module); `_ProductIn(_StoreRef)`, `_LookupItem(_StoreRef)`. blast: S · verdict: **execute**.

**16-R11 — The 6,000,000-char image cap is written 9× in `dora_api` (+ once in the companion).** where: see §0 grep. change: `infrastructure/images.py: MAX_IMAGE_DATA_URL_LEN = 6_000_000` + one `ImageField = Field(default=None, max_length=MAX_IMAGE_DATA_URL_LEN)`; 9 call sites; the companion imports nothing from Dora, so its constant stays with a comment naming the source. blast: S (mechanical) · verdict: **execute in chunk 20** (cross-cutting; R-003).

**16-R12 — `.settings-list` border + `color-mix(… --text-primary 8%)` copied across settings pages.** where: `ApiAccessSettings.vue:545–548` (+2 pages, 25 occurrences of the mix) → already 13-R9's settings-shell consolidation. verdict: **execute under 13-R9**; no separate finding.

**16-R16 — `CSRF_EXEMPT_ENDPOINTS` re-lists two members of `PUBLIC_ENDPOINTS`.** where: `middleware.py:243–247` adds `submit_ingestion_batch`, `ingest_link_status` to a set that is `PUBLIC_ENDPOINTS | {...}` and already contains them (:52, :55). The union is a no-op; the comment is the only value. change: drop the two literals, keep the comment on `PUBLIC_ENDPOINTS` ("bearer routes are CSRF-exempt by being public"). blast: S · guard: `test_route_auth_enforcement` · verdict: **execute** (or waive as documentation — Stage 2's call; recommend execute to stop the two sets drifting).

#### C3. Dead code / unused fields / unread endpoints

**16-R13 — `web_app/src/helpers/scrapedProductOfferLogic.ts` has no consumer.** evidence: `grep -rn scrapedProductOfferLogic web_app/src web_app/test` → only the definition. A Phase-D leftover (the in-app `ProductSearch.vue` it served was deleted). change: delete the file. verdict: **execute**.

**16-R14 — Dead `q-expansion-item` header props + `captionFor`.** where: `ApiAccessSettings.vue:40–42` (`:icon`, `:label`, `:caption="captionFor(src)"`) are ignored because the `#header` slot (:45–123) replaces the header; `captionFor` (:370–373) returns `''` unconditionally. change: remove the three props and the function. verdict: **execute**.

**16-R15 — `formatDate` is a one-line wrapper.** where: `ApiAccessSettings.vue:448–451` wraps `formatDateTime` (imported under an alias at :324). change: import `formatDateTime` and use it in the template. verdict: **execute**.

**16-R17 — `trust` is stored and never read; the SPA type carries `trust?` the page never sends.** where: `IngestionSource.trust`, `CreateIngestionSourceCommand.trust?` (`ingestionSourcesApiService.ts:17`), `ALLOWED_TRUSTS` validation (`ingestion_source_admin.py:188`). Proposal §2.6 records the deferral explicitly. verdict: **waive** (documented seam; cost is one column). Drop the optional `trust?` from the TS command type only if 16-R23 touches the file anyway.

**16-R18 — Stale docstrings.** `ingestion_source.py:15–16` "products/offers/**observations**" (observations left the producer path at J1); `test_ingestion_sources.py:9–10` "exercised once the ingest endpoint lands (C-10.2)". change: two one-line edits. verdict: **execute** (ride-along).

**16-R19 — `_IngestionContext.store_cache` is documented as "external store name → mapping row (resolved Store or None)" but caches the mapping only; the Store is re-fetched per product (`:310`).** Cosmetic; folds into 16-R6 (cache `(mapping, store)`). verdict: **execute with 16-R6**.

#### C4. Componentisation opportunities (R-001)

**16-R20 — `ApiAccessSettings.vue` (572 lines) is one page = list + per-row header + mappings panel + three dialogs.** change: extract `components/settings/IngestionSourceRow.vue` (header slot content + overflow menu; emits `toggle`/`rename`/`revoke`) and `components/settings/StoreMappingsPanel.vue` (the card; props `mappings`, `storeOptions`; emits `assign`/`drop`); the page keeps state, API calls and the three dialogs. blast: M · guard: none (vue-tsc + manual G1–G16) · verdict: **execute**.

**16-R21 — Reveal-once dialog as a `SecretRevealDialog` component.** One site only. verdict: **waive** (YAGNI; revisit if a second secret appears — e.g. an assistant provider key).

**16-R22 — `$q.dialog` ×2 (`:405–412`, `:516–523`) → `useConfirm`.** tracked: 13-R26 (chunk 20 builds the composable). verdict: **execute in chunk 20**.

#### C5. Placement / layering (R-003, R-005)

**16-R23 — `IngestionSourcesApiService.listStoresAsync` + `DoraStore` duplicate `StoresApiService.listAsync` + `Store`.** where: `ingestionSourcesApiService.ts:48–51, 104–109` call `/stores` (a different resource) and re-declare the row type; `storesApiService.ts:11` already returns `Page<Store>` with `store_id`/`name`. change: page imports `StoresApiService`, maps `page.items`; delete `DoraStore` + `listStoresAsync`. Note the default page size is 50 (`query_options.py:22`, FU-668) — pass `limit` explicitly or use the store list the Stores page already caches (chunk 13). blast: S · verdict: **execute**.

**16-R24 — Five raw `db.metadata.tables[...]` readers in this chunk.** where: `get_ingestable_products.py:81,89`, `get_ingest_stores.py:49`, `get_link_status.py:217` (gone with 16-R7), `ingestion_auth.py:43`. `find_ingestion_source` mirrors `auth_helpers.find_token` (also raw, `auth_helpers.py:193–207`) so the two should move together. tracked: **FU-923** (repository-routed access sweep, R-005). verdict: **FU** (already tracked; add these four sites to its list).

**16-R25 — `offer_mapping.py` lives under `features/ingestion/` but is the products domain's rule and is imported by `products/create_product.py:12`.** change: move to `features/products/offer_mapping.py`; two import sites. Also type `repository: SqlAlchemyRepository` → the `Repository` port (it only uses `.get()` and `.add()`), and `_IngestionContext.repository` likewise (`submit_ingestion_batch.py:194`). blast: S · verdict: **execute** (also lets 10-R5's PATCH-price fix import from the right package).

**16-R26 — Function-level import to dodge a cycle that doesn't exist.** where: `ingestion_auth.py:84` imports `api_response.unauthorized` inside `authenticate_ingestion_request`; `api_response.py` imports only stdlib + flask (grep). change: hoist to module level. verdict: **execute**.

#### C6. Naming & idiom

**16-R27 — `logging.getLogger(__name__)` inline ×3 instead of the module `_Logger` every other file in the chunk uses.** where: `ingestion_source_admin.py:191, 222`, `store_mappings.py:188`; also the local `ok = …` in `ingestion_source_admin.py:216` / `store_mappings.py:202` reads as `api_response.ok`. change: module `_Logger`; rename `ok` → `deleted`. verdict: **execute**.

**16-R28 — `UpsertStoreMappingHandler.handle` returns `(dto | None, "source_not_found" | "store_not_found" | None)`.** where: `store_mappings.py:104–139, 183–187` — string-coded tuples are the same shape 13-R1's bug came from. change: a small frozen `UpsertStoreMappingResult(mapping, source_not_found, store_not_found)` like `DeleteProductHandler`'s `product_not_found`, or raise two domain exceptions caught in the route. verdict: **execute** (S).

**16-R29 — `_apply_product` writes `note=f"created (provenance: {record_source})"` — provenance smuggled into a free-text note while `record_source` is otherwise unused on the product path.** where: `submit_ingestion_batch.py:371, 422–425`. The docstring (:374–376) says provenance is recorded by the next offer push. change: `note="created"`; drop the dead `record_source` on the product path. verdict: **execute** (companion `summarise_push` keys on `kind`, not `note` — safe).

#### C7. Efficiency

**16-R30 — `ListStoreMappingsHandler` does one `by_id` per distinct store.** where: `store_mappings.py:86–91`. change: one `.all(EntityField(Store,"id").in_(store_ids))`. verdict: **execute** (S; mapping lists are tiny, but it's the idiom the rest of the file uses).

**16-R31 — `_apply_product` issues up to two product lookups + a Store fetch per record; a 200-record batch ≈ 500 queries.** Bounded, synchronous v1 by design (§2.7). verdict: **waive**.

**16-R32 — `get_ingestable_products` loads every store name per call for the fallback.** Dozens of rows at most. verdict: **waive**.

**16-R33 — `find_ingestion_source` scans every enabled source with `compare_digest`.** n ≈ 1–3; mirrors `auth_helpers`. verdict: **waive** (keep the timing-safe idiom).

#### C8. Design-level findings — out of Stage-2 scope

- **16-D1 (= FU-919) — Keep or cut the name-based store mapping?** The companion pushes by `store_id`; the quarantine path + the *Store mappings* panel serve only a producer that pushes by name (the guide's `curl` reader). Recommendation: **keep** — it is the contract a third-party producer gets without reading Dora's store ids first, it is 200 lines, and the panel is hidden until a mapping exists. If cut, 16-R6 shrinks to one site and the panel + `IngestionStoreMapping` go. Owner's call; Stage 2 proceeds either way.
- **16-D2 — Availability on the wire (16-R5).** Adding `is_available` is a small contract addition in both repos; the alternative (a product with no price shows "No price yet" instead of $0.00) is a chunk-10 display rule. Recommend both.
- **16-D3 — No key rotation.** Deliberate: revoke + mint (guide + reveal dialog say so). No change.
- **16-D4 — Idempotency semantics are "refuse to re-process", not "return the cached result".** Documented in the module docstring (:10–13); the companion handles `idempotent_replay` explicitly. No change.

#### C9. Hand-rolled-vs-library verdicts
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| `ingestion_auth.extract_bearer_token` + `find_ingestion_source` | 30-line bearer parse + SHA-256 match | `flask-httpauth` `HTTPTokenAuth` | **keep** | — | One scheme, one table; the library adds a decorator we'd still wrap in `authenticate_ingestion_request`. |
| `IdempotencyKey` table + TTL | 40 lines | none worth it | **keep** | — | Fix 16-R2/R3 instead. |
| Payload validation | pydantic `extra="forbid"` | — | already library | — | — |
| `copyToClipboard` | Quasar util | — | already library | — | — |
| Rate limiting on the bearer lane | none | `flask-limiter` | **keep (none)** | — | 256-bit keys; a limiter would need the same `ProxyFix` fix as 15-R1 first. |

#### C10. Standards drift (R-0NN)
- **R-005** — raw table access ×5 (16-R24 → FU-923); `SqlAlchemyRepository` typed where the `Repository` port suffices (16-R25).
- **R-003** — image cap ×9 (16-R11); mapping lookup ×3 (16-R6); link join ×2 (16-R7); body-parse ×2 (16-R9); store-ref validator ×2 (16-R10).
- **R-001** — 572-line page (16-R20).
- **R-035 / D-rules** (`ApiAccessSettings.vue`): `text-color="white"` ×4 (:50, :61, :69, :150) → FU-671 / `--text-on-primary` (FU-674) sweep; `color="grey"` (:59) is a Quasar palette literal → `dora-bg-sunken dora-text-secondary` like the avatar at :49; inline `style="min-width: 180px"` (:101) → a class; icons all via `ICONS` ✓; confirm dialogs via `$q.dialog` → 13-R26.
- **R-021 (timezone)** — all server stamps are `datetime.now(timezone.utc)` ✓; SQLite tz coercion handled at :252–258 ✓.
- **Invisibility rule** — no "companion/scraper/producer" in any DTO, copy or help ✓ (two code comments in `get_ingest_stores.py:3–7` and `get_ingestable_products.py:4` name "the companion" — comments are fine; keep them out of strings).
- **15-R14** — `require_admin` uses `SESSION_USER_ID_KEY` ✓.

#### C11. Ride-along signals for FU-010 / FU-224 (theme / colour)
- `ApiAccessSettings.vue:59` `color="grey"` badge + `text-color="white"` ×4 (warning-on-white "pending"/"N pending" badges — check D-002 contrast on Pesto Dark; FU-924 (b) found the same white-on-semantic pattern in the companion).
- `:545–548` `color-mix(in srgb, var(--text-primary) 8%, transparent)` hairlines ×2 (settings-shell shared rule, 13-R9).


### E. Proposed follow-ups (orchestrator allocates ids)

- **urgent · bug** — Idempotency-Key replay after TTL → IntegrityError/500 and the batch is lost (16-R2). Fix in `submit_ingestion_batch._already_processed/_stamp_idempotency`; D1 pins it. Resolution: **now** (Stage 2, chunk 16).
- **urgent · bug** — `link-status` resolves custom products → companion "unsave" deletes a hand-entered product (16-R8). Shared `find_ingested_product` with `not_custom`; D5. Resolution: **now**.
- **bug · docs** — `docs/INGESTION_GUIDE.md` + `PROPOSAL_INGESTION_API §2.2` document `merchant`/`valid_until` and none of the read-side endpoints, `store_id` or `image` (16-R1). Resolution: **now**; closes FU-924 (d) on Dora's side.
- **finding · contract (two repos)** — a product pushed without an offer shows as available at $0.00; `is_available` never crosses the wire though both sides hold it (16-R5 / 16-D2). Resolution: **later, next companion pass** — Dora side first (additive, optional field), then `build_payload`.
- **finding** — idempotency rows never purged; revoked sources orphan them (16-R3). Resolution: **now** (one line with 16-R2).
- **finding** — raw `db.metadata.tables` ×4 remaining after 16-R7 (16-R24) — **append to FU-923**, not a new FU.
- **finding** — image-cap literal ×9 (16-R11) — **chunk 20** consolidation list.
- **decision** — FU-919 (16-D1): keep or cut the name-based mapping path. Recommendation recorded: keep. Resolution: owner, **before Stage 2 touches 16-R6** (so the refactor isn't done on code about to be deleted).
- **companion repo (append to FU-924)** — `dora_ingest.fetch_saved_products` docstring still says "only those whose store is mapped for this source" (Dora stopped filtering 2026-10-15; the caller must skip by `store_id`); `IngestResult.has_pending_store_mappings` only knows `store_not_mapped`, not `store_unknown`.

---

## Chunk 17 — Offline / PWA / native
*Source: [`CHUNK_17_offline_pwa_native.md`](../05_investigations/finalisation/CHUNK_17_offline_pwa_native.md) · analysed 2026-10-23*

### C. Senior review — Offline / PWA / native

#### C1. Bugs (verified or high-confidence latent)

**17-R1 — Two service workers fight over the same scope; the push SW evicts the Workbox SW and fires a false "new version" banner.** class: high-confidence latent (spec-level, verified by read) · where: `usePushSubscription.ts:19, 56–67` (`navigator.serviceWorker.register('/push-sw.js')`, no `scope`), `register-service-worker.ts:7–12` (`sw.js`, no `scope`), `push-sw.js:3–5` ("the two coexist at different paths"), `usePwaLifecycle.ts:135–146` (the `hadControllerAtBoot` guard, whose own comment names "the Notifications page registering the push SW" as the false positive it works around) · what's wrong: a registration is keyed by **scope**, not script URL; both default to `/`. Registering `/push-sw.js` where `/sw.js` already controls `/` is an *update* of that one registration — the browser installs push-sw, `skipWaiting` + `clients.claim()` (`push-sw.js:17–27`) make it take over immediately, and the Workbox worker (precache, `dora-api` NetworkFirst, image caches) is gone until the next full load re-registers `sw.js`, which then evicts push-sw and the push subscription's SW with it. Each swap fires `controllerchange`; when a controller existed at boot the guard passes and `UpdateBanner` shows. `refresh()` runs on **mount** of Settings → Notifications, so merely opening that page triggers the swap. · exact change: ship **one** worker — GenerateSW `importScripts: ['push-sw.js']` in `extendGenerateSWOptions` (Workbox supports it), strip push-sw's own `install`/`activate` handlers (Workbox owns those), and have `usePushSubscription.ensureRegistration()` use `await navigator.serviceWorker.ready` / `getRegistration()` instead of registering; keep a dev-only fallback that registers `/push-sw.js` when no registration exists (SPA/dev mode has no `sw.js`). Then the `hadControllerAtBoot` guard can stay as belt-and-braces. · blast: M (push + offline both touched; needs G8 + the Notifications-page check in a built PWA) · guard: D1 · verdict: **execute** · cross-ref: chunk 9 (`push-sw.js` content unchanged).

**17-R2 — `public/offline.html` promises offline replay that no longer exists — and is never served anyway.** class: verified · where: `offline.html:41–44` ("Ticks, stock-level bumps, restock marks and expiry pushes that you make while offline are held locally and replayed on reconnect"); `quasar.config.ts:364–366` comment says "fall back to /offline.html" but sets `navigateFallback = 'index.html'`; `pwaOfflineHtmlFilename` commented out (:257); no other reference · what's wrong: R-052 forbids copy that promises syncing; the file also hard-codes brand hex and would be stale the day it *was* served. Under R-052 the SPA shell *is* the right offline fallback, so the page has no job. · exact change: delete `web_app/public/offline.html`; fix the comment at :364 to say the shell is the fallback; drop the `DORA_VERIFY` bullet "navigating to an uncached route shows Dora's `offline.html`" (PWA section) since it can never pass. · blast: S · guard: none (build) · verdict: **execute**.

**17-R3 — `.gitignore` misses the Capacitor build output; `src-capacitor/www/index.html` is tracked.** class: verified · where: `.gitignore:50–51, 55` are rooted (`/src-capacitor/www`) but the folder is `web_app/src-capacitor/www` (Quasar's template `.gitignore` assumed the repo root is `web_app/`); `git ls-files` shows 1 tracked file; `node_modules` and `android/app/build` happen to be clean · exact change: `web_app/src-capacitor/www/`, `web_app/src-capacitor/node_modules/`, `web_app/src-cordova/**` patterns in the root `.gitignore` (or a `web_app/src-capacitor/.gitignore`); `git rm --cached web_app/src-capacitor/www/index.html` (Stage 2 — **touches the index**, so flag it in the handoff; no commit without the owner). · blast: S · verdict: **execute**.

**17-R4 — Stale planning artefacts describe the deleted offline queue.** class: verified docs · where: `FINALISATION_PLAN.md:212` ("the offline queue (`useOfflineQueue`) vs Workbox background sync") and `:313` (row 17 "offline queue"); `DORA_VERIFY.md` "Offline sync + Retry, end to end (2026-08-17)" (asks to confirm "Synced everything" and "sync on re-open" — contradicts the "Offline is read-only (2026-08-23)" section 500 lines earlier; only its **Retry** bullets are still true); `DORA_FOLLOWUPS.md` **FU-660** (conflict pile) and **FU-661** (six queued kinds) describe code that no longer exists (grep: none). · exact change: plan — replace both mentions with "read-only offline (R-052): the `dora-api` NetworkFirst cache + `useNetworkStatus`"; VERIFY — delete the sync bullets, merge the Retry bullets into the 08-23 section; FUs — move 660 + 661 to RESOLVED as *superseded by R-052 (2026-08-23 queue removal)*. · blast: S · verdict: **execute** (orchestrator does the ledger move).

**17-R5 — Duplicate follow-up id: two `[OPEN] FU-640` entries.** class: verified ledger defect · where: `DORA_FOLLOWUPS.md` — "FU-640 — A user-visible failure produced an empty log bundle: 4xx responses aren't logged" and `:3831` "FU-640 — iOS Capacitor shell has no `NSCameraUsageDescription`" · exact change: renumber the iOS one to the next free id (orchestrator; from FU-929) and fix any `[[FU-640]]` links that meant it. The iOS finding itself still stands (`Info.plist` has no usage strings — grep). · verdict: **execute** (ledger).

**17-R6 — `AxiosHttpClient.request()` is dead and its comment names the deleted queue.** class: verified · where: `axiosHttpClient.ts:436–449` ("Raw config-bearing call used by the offline queue when draining"); grep: no caller · exact change: delete the method. · blast: S · guard: `vue-tsc` · verdict: **execute**.

**17-R7 — Sign-out eviction clears the API cache but not the image caches.** class: verified vs R-052's own rule ("a cache that holds user content is evicted on sign-out and on 401") · where: `apiResponseCache.ts:22, 34` matches only `'dora-api'`; `quasar.config.ts:380–400` also fills `dora-merchant-images` and `dora-stock-images` (stock-item photos **are** user content; product images are catalogue). · exact change: `API_CACHE_NAME_FRAGMENTS = ['dora-api', 'dora-stock-images']` (keep merchant/product images — shared catalogue, and the R-045 authed-image helper from 10-R35/13-R41 bypasses the SW cache anyway); rename the module `swCacheEviction.ts`. · blast: S · guard: D3 · verdict: **execute**.

**17-R8 — Two of the three runtime-cache URL patterns target routes that don't exist.** class: verified · where: `quasar.config.ts:386` `/\/products\/.*\/image|merchant-images/` (`merchant-images` left with `merchant_api`, Phase D) and `:397` `/\/stock-items\/.*\/image|\/data\/images\//` (`/data/images/` — no such route; grep none) · exact change: drop the dead alternations; keep `/products/<id>/image` and `/stock-items/<id>/image`. (Note the authed-image helper in chunks 10/13 fetches images via axios with credentials — those requests still pass through the SW `fetch` handler, so the rules still apply.) · blast: S · verdict: **execute** (ride-along with 17-R7).

**17-R9 — The About "Install as an app" section renders inside the native Android app and tells the user to "try Chrome".** class: verified by read · where: `AboutSettings.vue:52–61` has no native guard; `PwaInstallPrompt.vue:37–40` final `v-else`; `isInstalled()` is only standalone/`appinstalled` (Capacitor's WebView reports neither) · exact change: `v-if="!isNativePlatform()"` on the section (import from `backendUrl.ts`), or have `PwaInstallPrompt` render "You're using the Dora app." when native. · blast: S · verdict: **execute**.

**17-R10 — Android cleartext policy for an `http://` LAN backend is unverified.** class: finding (medium confidence) · where: `capacitor.config.json:8–10` `allowMixedContent: true`; `AndroidManifest.xml` has no `android:usesCleartextTraffic` / `networkSecurityConfig` · what's wrong: Android 9+ blocks cleartext by default in WebView; Capacitor's own guidance for http servers is to set `usesCleartextTraffic="true"`. The P8-10 VERIFY row ("enter the LAN URL… → Connected") has never been ticked, so it is unknown whether the APK can reach an `http://192.168…` backend on a current phone. · exact change: none until confirmed — if the device test fails, add `android:usesCleartextTraffic="true"` to `<application>` (or a network-security-config allowing cleartext to private ranges only). · verdict: **FU** (confirm on device; see §E).

#### C2. Redundancy / DRY (R-001, R-003)

**17-R11 — Offline copy is written in six places.** where: `useNetworkStatus.ts:151, 163, 172, 189, 221` (five `Notify.create` strings) + `OfflineBanner.vue:43–44` — the two "look around, but not make changes" sentences appear 3×. The 2026-08-23 correction note (`:144–147`) had to be applied in two files. · exact change: `offlineCopy.ts` exporting `OFFLINE_COPY = { offline, unreachable, backOnline, stillDown, networkDetected }`; banner + toasts read it. Also drop the stale "the queue drain (which watches `apiReachable`) can run" comment at `:139–141`. · blast: S · verdict: **execute**.

**17-R12 — `OfflineBanner.vue` and `UpdateBanner.vue` are the same component.** where: identical template shape (icon · text · `q-space` · ghost actions), identical 40-line scoped CSS (sticky, `z-index: 2500`, `--elevation-1`, enter/leave transform) differing only in `--q-negative` vs `--q-accent` and the enter/leave class names. · exact change: `ShellBanner.vue` (props `tone: 'negative' | 'accent'`, `icon`, default slot, `#actions` slot, `role=status aria-live=polite`); both become ~20-line wrappers. `DemoBanner.vue` (chunk 19) is a third candidate consumer. · blast: S · verdict: **execute** (R-001).

**17-R13 — `src-pwa/manifest.json` is the untouched Quasar template; `extendManifestJson` rewrites every field.** where: `manifest.json:2–31` (`#027be3`, `#ffffff`, `icons/icon-128…512.png` — files that don't exist in `public/icons`) vs `quasar.config.ts:274–317` · exact change: make `manifest.json` the source of truth (real name, colours, display, icons) and shrink `extendManifestJson` to the parts that need code comments (`share_target`, `shortcuts`); or delete the base fields the hook overrides. One place, not two (R-003). · blast: S · guard: FU-336's build check (manifest emitted) · verdict: **execute**.

**17-R14 — `backendUrl.ts` declares the same key twice.** where: `:23–24` `PREF_KEY === LS_KEY === 'dora.backendBaseUrl'` · exact change: one `STORAGE_KEY`. · verdict: **execute** (trivial ride-along).

#### C3. Dead code / unused fields / unread endpoints

**17-R15 — `src-pwa/custom-service-worker.ts`** — never built (GenerateSW); tracked: **FU-724**, whose point stands: it is the file a future agent would edit. · exact change: delete it (Quasar regenerates the scaffold only in InjectManifest mode) and add a two-line comment at the top of the `pwa` block in `quasar.config.ts`: "the SW that ships is generated from `extendGenerateSWOptions` below — there is no hand-written worker" (plus `push-sw.js` once 17-R1 imports it). The eslint-ignore FU-336 added for it goes too. · verdict: **execute** (resolves FU-724).

**17-R16 — `register-service-worker.ts`** — eight empty hook stubs from the template. Not dead (Quasar needs the file to register `sw.js`) but noise. · exact change: keep `register(...)` with only the hooks that matter: `updated()` → nothing (the `controllerchange` path in `usePwaLifecycle` is the real signal), `error(err)` → `console.warn`. · verdict: **execute** (S) — or **waive** as template; recommend the trim.

**17-R17 — `useNetworkStatus` exports `lastSeenOnline`** — grep: no consumer outside the composable (`OfflineBanner` destructures five other fields). · exact change: drop the ref and its two writes. · verdict: **execute**.

**17-R18 — `useWakeLock` returns `{ active, supported }`** — both callers (`RecipeCookMode.vue:837`, `ShoppingListDetail.vue:1243`) call it for the side effect and discard the return; `supported` is a ref that is never updated after init. · exact change: return nothing (or keep `active` only if a chip ever wants it — none does); use lib.dom's `WakeLockSentinel` type and `navigator.wakeLock` directly instead of the local alias + two casts (TS ≥ 4.4 ships it). · verdict: **execute**.

#### C4. Componentisation opportunities (R-001)
- 17-R12 (`ShellBanner`). Nothing else — the surface is already composable-sized.

#### C5. Placement / layering (R-003, R-005)

**17-R19 — `boot/pwaLifecycle.ts` and `boot/capacitor.ts` are two boot files for one concern (platform shell).** Fine as is; Quasar boot files are the right layer. **waive**.

**17-R20 — `isNativePlatform()` lives in `services/api/backendUrl.ts`** but is imported by `cameraAvailability.ts`, `router/index.ts`, `boot/capacitor.ts`, `SplashScreen` for non-URL reasons. · exact change: `helpers/platform.ts` exporting `isNativePlatform`, `isIosSafari` (from `usePwaLifecycle.ts:48–53`), `isSecureContext()`; `backendUrl.ts` imports it. · blast: S · verdict: **execute**.

#### C6. Naming & idiom

**17-R21 — Bare Material icon strings in `OfflineBanner.vue:10, 20`** (`'sync_problem'`, `'wifi_off'`, `'sync'`, `'refresh'`) while `UpdateBanner`/`PwaInstallPrompt` use `ICONS`. · exact change: add `wifi_off`/`sync_problem`/`sync` to `ICONS` (refresh exists) and use them. · verdict: **execute** (same class as 13-R39/15's bare-icon sweep).

**17-R22 — `apiResponseCache.ts` is named for what it clears, not what it is** — it is the SW-cache eviction hook; see 17-R7's rename. **execute with 17-R7**.

#### C7. Efficiency

**17-R23 — Two `/health` pollers.** `useNetworkStatus` probes `/health` every 60 s per tab; chunk 13 (13-R37) found `/health` also probed up to 9× per cold load by other readers. The shared `healthProbe` 13-R37 proposes should feed `apiReachable` too (one request, two consumers). · verdict: **execute under 13-R37**.

**17-R24 — `NetworkFirst` `networkTimeoutSeconds: 5` on `/api/**`** vs axios's own timeouts: a slow-but-alive backend yields stale cached data silently. Design-level → 17-D2. **waive** here.

#### C8. Design-level findings — out of Stage-2 scope
- **17-D1 — iOS target.** `Info.plist` has no camera/photo usage strings (FU-640-iOS), `src-capacitor/ios` has never been built; `PLATFORM_BUILDS_AUDIT` puts iOS in Tier 3 ("PWA first"). Recommendation: leave unbuilt; keep the FU with its "before the first device run" trigger.
- **17-D2 — Stale-data indicator.** When the SW serves a cached API response (timeout or offline) the page can't tell. A `X-Dora-From-Cache`-style marker is impossible from GenerateSW without a plugin; the honest alternative is to drop `networkTimeoutSeconds` (serve cache only when the network *fails*) so stale data appears only when the banner is up. Owner call; recommend dropping the timeout.
- **17-D3 — `allowMixedContent: true`** is the price of an `http://` LAN backend from an `https://localhost` WebView. Document in `packaging/BUILD_NATIVE.md` (chunk 19) rather than change.
- **17-D4 — Release versioning of the APK** (`versionCode 1` / `versionName "1.0"`, `build.gradle:10–11`) is unlinked from Dora's version. Chunk 19 (release process).
- **17-D5 — Feedback "kivy P2P sync between standalone installs".** Not pursued: the product is one server + many clients (charter Decision 5, GitLab-way); R-052 explicitly forbids client-side conflict resolution. Recorded as answered.

#### C9. Hand-rolled-vs-library verdicts
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| `useNetworkStatus` | 261-line singleton poller + backoff | `@vueuse/core` `useNetwork`/`useOnline` | **keep** | — | VueUse only wraps `navigator.onLine`; the `/health` probe, backoff and the forced Retry are the value. |
| `usePwaLifecycle` | install prompt + `controllerchange` | `vite-plugin-pwa`'s `useRegisterSW` | **keep** | — | Quasar owns the build; the composable is 148 lines. |
| `useWakeLock` | Wake Lock wrapper | `@vueuse/core` `useWakeLock` | **replace-candidate, low priority** | S | VueUse's version does the same incl. visibility re-acquire; swap only if VueUse is adopted elsewhere (chunk 20 decides). |
| GenerateSW runtime caching | config | InjectManifest hand-written SW | **keep GenerateSW** | — | FU-724's conclusion; 17-R1 adds `importScripts` for push. |
| `backendUrl.ts` | Preferences/localStorage URL store | — | keep | — | — |
| `keyboardInset.ts` | visualViewport insets | — | keep | — | 36 lines, one listener. |

#### C10. Standards drift (R-0NN)
- **R-052** — `offline.html` copy (17-R2); image caches not evicted (17-R7); stale queue references in plan/VERIFY/FUs/code comments (17-R4, 17-R6, 17-R11).
- **R-003** — offline copy ×6 (17-R11); manifest fields ×2 (17-R13); storage key ×2 (17-R14); platform check location (17-R20).
- **R-001** — two identical banners (17-R12).
- **R-035 / D-rules** — bare icons (17-R21); brand hex in `quasar.config.ts:280–281` and `offline.html` — the manifest cannot read CSS tokens, so the config hex stays with a `// D-rule carve-out: manifest colours are build-time` comment (D-002/D-004 can't apply); `offline.html` goes.
- **Repo hygiene** — `.gitignore` paths (17-R3).

#### C11. Ride-along signals for FU-010 / FU-224 (theme / colour)
- Banners paint `var(--q-negative)` / `var(--q-accent)` with `--text-on-primary` — confirm the accent/on-primary pair meets D-002 in every theme (the warning-badge pattern from 16-C11 is the same risk).
- Manifest `theme_color #f5c462` is DS1's primary; if the theme system (FU-010) ever changes the default swatch the manifest won't follow — note in the theme proposal.


### E. Proposed follow-ups (orchestrator allocates ids)

- **urgent · bug** — `/push-sw.js` and `sw.js` share scope `/`; opening Settings → Notifications replaces the Workbox SW and shows a false "new version" banner (17-R1). Resolution: **now** (Stage 2, chunk 17; browser-verify G8 + Notifications page in a built PWA).
- **bug · copy / R-052** — `public/offline.html` promises replay and is never served (17-R2). Resolution: **now**.
- **finding · repo hygiene** — `.gitignore` Capacitor patterns are rooted at the wrong level; `src-capacitor/www/index.html` tracked (17-R3). Resolution: **now**; the `git rm --cached` needs a commit → owner.
- **finding · ledger** — duplicate id FU-640 (17-R5): renumber the iOS `NSCameraUsageDescription` entry. Resolution: **now**.
- **resolve as superseded** — FU-660, FU-661 (queue deleted 2026-08-23, R-052) (17-R4). Resolution: **now**.
- **resolve** — FU-724 once `custom-service-worker.ts` is deleted + the config comment added (17-R15).
- **finding · device check** — Android cleartext to an `http://` LAN backend from the APK is unverified; `usesCleartextTraffic` absent (17-R10). Resolution: **when the P8-10 VERIFY row is walked**; add `usesCleartextTraffic="true"` if it fails. Also append to FU-389 (field test).
- **decision** — 17-D2: drop `networkTimeoutSeconds: 5` so cached API data only appears when the network actually fails. Resolution: owner, opportunistic.
- **docs** — `FINALISATION_PLAN.md:212, 313` + `DORA_VERIFY.md` "Offline sync + Retry" section stale (17-R4). Resolution: **now**.

---

## Chunk 18 — Backup & restore + Import
*Source: [`CHUNK_18_backup_restore_import.md`](../05_investigations/finalisation/CHUNK_18_backup_restore_import.md) · analysed 2026-10-23*

### C. Senior review — Backup & restore + Import

#### C1. Bugs (verified or high-confidence latent)

**18-R1 — Partial restore raises `KeyError: 'meal_recipes'` (500) before any row is touched.** class: verified · where: `restore_backup.py:194` iterates `("product_stock_item_links", "stock_item_substitutes", "meal_recipes")` and indexes `TABLE_NAME_BY_BACKUP_KEY[backup_key]`; `meal_recipes` left `SECTIONS` in `99131847 Complete rework of meals` (the test comment at `test_data_router.py:77` records the removal; FU-164 fixed the *test's* section list and called the diagnosis a misdiagnosis). The lookup sits outside the `try` (:224), so it is an unhandled exception → Flask 500 → the SPA report says "Restore failed / HTTP 500". `MODE_ALL_SKIP_DUPLICATES` never enters that branch, which is why the three restore tests pass and why `grep partial` in the test file returns 0. Also stale: `REQUIRED_FKS` entries `("meal_plan_entries", "meal_id")` (:217 — the column is `recipe_id` now, `table_mappings.py:1061`) and `("meal_recipes", …)` ×2 (:223–224) — inert but misleading. · exact change: derive the m2m list from `SECTIONS` (`[s.backup_key for s in SECTIONS if len(primary_key_columns(table)) > 1]`) instead of a literal tuple; delete the three stale `REQUIRED_FKS` entries; add `("meal_plan_entries", "recipe_id")`. · blast: S · guard: none → **D1 (must-write)** · verdict: **execute** · **urgent**.

**18-R2 — "New backup" with the default selection is rejected: the SPA names a section the server doesn't have.** class: verified · where: `AdminDataBackupRestore.vue:541` `{ key: 'product_barcodes', … defaultOn: true }` vs `restore_shared.py:143` `Section("barcodes", "Barcode", …)`; `backup.py:45–48` returns `"Unknown backup section(s): product_barcodes."` → `backup_library.py:188–189` → 400; the SPA shows "Couldn't create backup." with that caption. Pinned server-side by `test__get_backup__unknown_section__is_rejected`; nothing pins the SPA list. Every default-selection backup from the UI fails until the user unticks "Product barcodes". · exact change: see 18-R3 (remove the mirror). Interim one-liner: rename the key to `barcodes`. · blast: S · guard: D2 · verdict: **execute** · **urgent** · note: static read — **confirm in browser** per CLAUDE.md (the owner may have been creating backups via a path that unticks it).

**18-R3 — The SPA carries a hand-copied, stale mirror of the server's section catalogue (R-003 — domain list in two languages).** class: verified · where: `AdminDataBackupRestore.vue:514–545` `BACKUP_SECTIONS` (20 keys; comment "Mirrors dora_api/…SECTIONS. Keep this in sync") vs `restore_shared.SECTIONS` (29). Missing: `cuisines, categories, dietary_tags, tools, recipe_dietary_tags, recipe_tools, recipe_steps, recipe_step_ingredients, recipe_step_tools`. Consequences beyond 18-R2: (a) a UI-created backup **never includes recipe steps, tools, tags, cuisines or categories** (the server dumps only the requested keys) — so a restore of such a backup yields recipes with no steps and null cuisine/category, and the three pending VERIFY bullets ("Backup → restore round-trips `RecipeStep`…") can only pass via `curl`; (b) the restore **report** (`:1140–1151`) and the tree labels (`SECTION_LABELS`, `TOP_LEVEL_KEYS`) hide those sections' counts. · exact change: new `GET /api/data/backup/sections` returning `[{key, label, category, default_on, sensitive}]` straight from `SECTIONS` (add `sensitive: bool` to `Section` for the three optional ones so `SENSITIVE_SECTIONS`/`SENSITIVE_LABEL_BY_KEY` at `:471–475` go too); the page loads it on mount and derives `backupSelected`, groups, labels and the report from it; `TOP_LEVEL_KEYS` becomes "sections with a `duplicate_key_fn`" or an explicit `pickable: bool` on `Section`. · blast: M · guard: D2 + existing 13 backup tests · verdict: **execute**.

**18-R4 — Spreadsheet import stamps `stock_level_last_updated` with naive local time.** class: verified (R-021) · where: `import_spreadsheet.py:523` `datetime.now()`; every other writer uses `datetime.now(timezone.utc)` (e.g. `backup.py:100`). On a server whose clock isn't UTC the imported items' "level changed" timestamps are offset, and the pantry-belief / staleness rules (chunk 7) read them. · exact change: `datetime.now(timezone.utc)`. · blast: S · guard: D4 · verdict: **execute**.

**18-R5 — Confirm dialog renders the uploaded workbook's sheet name as HTML.** class: verified (self-XSS / D-rule dialog convention) · where: `AdminDataImport.vue:556–563` `$q.dialog({ message: \`Import rows from <strong>${selectedSheet.value}</strong>?…\`, html: true })` — the sheet name comes from the file. Admin-only and self-uploaded, so the exposure is low, but it is the one place in the app a file's contents reach `innerHTML`. · exact change: drop `html: true`, plain text with `"…"` around the name; same for `AdminDataBackupRestore.vue:1083–1086` (constant strings, but `html: true` for a `<br>` is the same habit — use `\n` + `style="white-space: pre-line"` or two sentences). Both become `useConfirm` calls (13-R26). · blast: S · verdict: **execute**.

**18-R6 — `delete_backup` unlinks the file before it re-fetches the row, with two repositories.** class: latent · where: `backup_library.py:349–359` — `_resolve_backup` opens one `SqlAlchemyRepository`, the route unlinks, then opens another and `by_id`s again; if the second fetch misses (race with retention) the response is 404 after the file is already gone, and the row would point at nothing. · exact change: one repository through the route; remove the row first, commit, then unlink (a dangling file is recoverable; a dangling row isn't). · blast: S · verdict: **execute**.

#### C2. Redundancy / DRY (R-001, R-003)

**18-R7 — Every call on both pages is a hand-rolled `fetch`.** tracked: **FU-716** · where: 12 sites in `AdminDataBackupRestore.vue`, 5 in `AdminDataImport.vue`, 4 in `useChunkedUpload.ts` (each with `resolveBaseURL()` + `credentials: 'include'` + `csrfHeader()` + its own `describeError`). Consequences FU-716 lists (no `X-Request-Id`, no `toastCaption`, no retry policy) — plus a fourth copy of `describeError` (`AdminDataBackupRestore.vue:1034–1037`, `AdminDataImport.vue:525–528`, `useChunkedUpload.ts:140–143`). · exact change: `services/api/dataApiService.ts` (`listBackupsAsync`, `createBackupAsync`, `downloadBackupAsync` → `responseType: 'blob'`, `restoreBackupRowAsync`, `deleteBackupAsync`, `inspectBackupAsync`, `restoreBackupAsync`, `inspectSpreadsheetAsync`, `commitSpreadsheetAsync`, `listImportTemplatesAsync`, `downloadImportTemplateAsync`, `backupSectionsAsync` for 18-R3) and `uploadsApiService.ts` (`start/chunk(FormData)/finish/abort`) on `AxiosHttpClient`; `useChunkedUpload` consumes the latter; the library settings move to `AppSettingsApiService` + the `AppSettings` type (13-R16 adds `backup_*`). Error captions via `toastCaption(e)`. · blast: M · guard: 57 pytest unchanged; `vue-tsc`; manual G1–G17 · verdict: **execute** (resolves FU-716 and the `useChunkedUpload` half of FU-571's raw-client list).

**18-R8 — `triggerSave` / `parseFilename` / anchor-click download are re-implemented in both pages although `downloadHelpers.ts` exports them.** where: `AdminDataBackupRestore.vue:965–980`, `AdminDataImport.vue:338–346, 664–672` vs `services/files/downloadHelpers.ts:10, 18`. · exact change: import the helpers; the error-rows CSV builder (`:645–673`) becomes `downloadCsv(rows, header, filename)` in the same module (RFC-4180 escape lives once — `useStockOverviewExport` and friends in chunk 20 want it too). · blast: S · verdict: **execute**.

**18-R9 — `confirmAsync` (page-local Promise wrapper) + 3 inline `$q.dialog` confirms.** where: `AdminDataBackupRestore.vue:880–889` (defines its own `confirmAsync`), `:1078–1095`, `AdminDataImport.vue:556–564`. · tracked: 13-R26 (`useConfirm`, chunk 20). · verdict: **execute in chunk 20**; 18-R5's `html: true` fix rides along.

**18-R10 — `_inspect_streamed` and `_inspect_inline` duplicate ~50 lines of envelope validation + sampling + duplicate flagging.** where: `inspect_backup.py:161–215` vs `:218–270` · exact change: one `_summarise(meta, rows_for(section) -> Iterator)`; the inline path passes `iter(payload.get(k, []))`, the streamed path `_iter_section_rows`; envelope validation (`schema_version` int / newer) also appears a third time in `RestoreBackupHandler.handle:88–95` → `restore_shared.validate_envelope(doc) -> str | None`. · blast: S · guard: inspect tests (3) · verdict: **execute**.

**18-R11 — String-coded errors with `startswith` dispatch ×5.** where: `RestoreBackupHandler.handle -> RestoreSummary | str`; `backup_library.py:333–337` and `restore_backup.py:373–378` both test `startswith("Restore failed and was rolled back")`; `import_spreadsheet.py:319–322, 674–679` test `startswith("No staged upload")`; `inspect_backup.py:285–286` parses the id back **out of the message** (`err.rsplit(" ", 1)[-1].rstrip(".")`). Same class as 13-R1 / 16-R28. · exact change: `class RestoreError(Exception)` with `.kind: Literal['not_found','invalid','rolled_back']`; handlers raise, routes map kind → `not_found/bad_request/internal_server_error`. · blast: S · verdict: **execute**.

**18-R12 — Date parsing ignores the install locale.** where: `import_spreadsheet.py:109` tries `%d/%m/%Y` before `%m/%d/%Y` unconditionally; `AppSetting.locale` (`en-AU` / `en-US`, `app_setting.py:190`) is the one authority for day/month order (R-021/R-003). `03/04/2027` imports as 3 April on a US install. · exact change: read `get_or_create_app_setting(repo).locale` once in `CommitSpreadsheetHandler.handle` (it already reads the setting for `stocktake_new_items_opt_in`) and order the two slash formats by it; mention the order in the template comment row. · blast: S · guard: D5 · verdict: **execute** (small; the help entry above states the day-first default until then).

**18-R13 — `.settings-divider` / `.settings-actions` / `.settings-page` scoped CSS copied into both pages.** tracked: 13-R9 (settings shell). · verdict: **execute under 13-R9**.

#### C3. Dead code / unused fields / unread endpoints

**18-R14 — `Backup.sha256`, `Backup.status`, `STATUS_FAILED` have no reader.** evidence: `sha256` is written (`backup_library.py:207`) and returned in the DTO; grep across `dora_api` + `web_app/src` finds no comparison (download streams the file, restore re-reads it, the SPA type declares it and never renders it); `status` is always `STATUS_READY`; `STATUS_FAILED` is never assigned. The entity docstring promises corruption flagging. · exact change: either verify on download/restore (`_sha256_of(path) != row.sha256` → 409 "Backup file changed on disk") — 6 lines, and it gives the column its job — or drop the promise from the docstring. Recommend the check. `trigger_kind` stays (documented forward-looking column). · blast: S · guard: D3 · verdict: **execute** (the check).

**18-R15 — Multipart fallback in `inspect_backup`.** where: `inspect_backup.py:53–80, 103–111` (`_stream_upload_to_tempfile`, `DIRECT_UPLOAD_MAX_BYTES`, `CHUNK_BYTES`) — docstring: "kept as a fallback for curl-style ad-hoc inspection"; no SPA caller, no test (the three inspect tests use inline JSON or `upload_id`). · verdict: **waive** (documented operator affordance; 30 lines) — or delete if the owner wants the three-shape body gone. Record as 18-D3.

**18-R16 — `legacy /data/* redirects`** (`routes.ts:195–217`) — six redirect rows for bookmarks from the retired Data menu; `data/export` comment explains itself. · verdict: **waive** (cheap, intentional).

**18-R17 — `useChunkedUpload.lastUploadId`, `inFlight`** — returned but unused by either page (both track their own `uploadId` and `uploading`). · exact change: drop from the return (or have the pages use them — one owner). · verdict: **execute** (with 18-R7).

#### C4. Componentisation opportunities (R-001)

**18-R18 — `AdminDataBackupRestore.vue` (1,337 lines) is four surfaces in one file.** · exact change: `BackupLibraryList.vue` (rows + 3 actions; emits), `BackupCreateDialog.vue` (section picker + sensitive banner; takes the catalogue from 18-R3), `BackupRestorePanel.vue` (drop + preview tree + actions), `RestoreReportDialog.vue`; the page keeps the API calls and the library-settings section. · blast: M · guard: manual G1–G11 · verdict: **execute**.

**18-R19 — `AdminDataImport.vue` (717)** — the result dialog (`:218–280`, virtual list + chips + error CSV) is a self-contained `ImportResultDialog.vue`. · blast: S · verdict: **execute**.

#### C5. Placement / layering (R-003, R-005)

**18-R20 — Raw `db.metadata.tables` / `db.session` throughout the data feature.** where: `backup.py:68–69`, `backup_library.py:268–273`, `inspect_backup.py:147–148`, `restore_backup.py` (throughout — generic table walk), `import_spreadsheet.py:510, 616, 647`. The generic dump/restore **is** the legitimate R-005 carve-out (it iterates `SECTIONS` by table name on purpose); the import's three raw inserts are not — `create_stock_item` / `create_stock_group` / `create_stock_location` handlers exist and own defaults (`stocktake_new_items_opt_in` is already copied here because of it, `:395–399`). · exact change: comment the carve-out once at the top of `restore_shared.py` (`# R-005 carve-out: …`) for backup/inspect/restore; route the import's inserts through the three create handlers (or their shared "new entity" factories) so a future default isn't missed. `backup_library.list_backups:268` username lookup → `repository.get(User).all(in_)`. · blast: S–M · verdict: **execute** (import) / **explain** (backup). Also add to **FU-923**'s list.

**18-R21 — `list_backups` hand-rolls pagination** (`backup_library.py:246–262`: parses `page`/`size`, sorts the whole table in Python, slices) while every other list uses `parse_query_options` + `repository.paginate` + `paginated` (e.g. `/stores`). · exact change: `Backup` gets a `_FIELD_MAP` + `paginate(options, _row_to_dto…)` ordered by `created_at desc`; the SPA passes `?limit=200`. `_enforce_retention:151` likewise loads all rows — fine for ≤100 but use `order_by/offset` if `paginate` supports it. · blast: S · verdict: **execute**.

**18-R22 — `from uuid import uuid4` inside three functions, `from flask import Response` inside one, `DORA_CONFIG` import inside `upload_dir()`.** where: `import_spreadsheet.py:511, 615, 646, 927`; `uploads.py:58`. · exact change: module-level imports (no cycle — `configuration_manager` is imported at module level by `backup_library.py`). · verdict: **execute**.

#### C6. Naming & idiom

**18-R23 — `"zone"` literal** (`import_spreadsheet.py:621`) → `LOCATION_KIND_ZONE` (`stock_location.py:9`). · **execute**.
**18-R24 — `existing_item_names: dict[str, UUID]` later assigned `True`** (`:529`) — type lie; use a `set[str]` of names (the ids are never read). · **execute**.
**18-R25 — `_Logger = logging.getLogger(__name__)` inside every route** (`backup_library.py:181, 306, 344`, `inspect_backup.py:275`, `restore_backup.py:363`, `uploads.py:100, 134, 206, 231`) vs the module-level `_Logger` convention in the ingestion package. · **execute** (mechanical).
**18-R26 — `ok` shadows `api_response.ok`** — `AdminDataBackupRestore.vue` is fine, but `backup_library.py` imports `ok` and the SPA-side word is unrelated; no issue. (Checked; no change.)
**18-R27 — Copy: "Restore all (skip duplicates)" vs "Restore selection" vs library "Restore this backup"** — three verbs for two behaviours; the dialog copy explains each. **waive** (owner-happy).

#### C7. Efficiency

**18-R28 — Restore loads every row of every section's table into Python before applying** (`restore_backup.py:116–132`), including `ProductHistoricOffer` (potentially the largest table) even when the backup carries none; inspect does the same per section with a duplicate key fn (`_build_existing_duplicate_keys`). · exact change: skip tables whose backup section is empty; for PK presence use `select(pk_cols)` not `select(table)`. · blast: S · verdict: **execute** (cheap) — the full-table duplicate-key scan stays (it is the contract).
**18-R29 — Import hydrates every `StockItem`/`StockGroup`/`StockLocation` entity to build name maps** (`import_spreadsheet.py:418–431`). · exact change: `select(table.c.id, table.c.name)` via the repository's column query (or accept — 5k rows is fine). · verdict: **waive** (hobby scale; note).
**18-R30 — `_backups_dir()` → `get_or_create_app_setting` ×2 per create** (`:125, :149`). Memoised on `g` → **waive**.

#### C8. Design-level findings — out of Stage-2 scope
- **18-D1 — Scheduled backups.** `trigger_kind` was added for them (FU-342) and FU-405 parks ops for Phase 4; no FU tracks the feature itself. Recommend a tiny APScheduler job ("nightly if anything changed") as a Phase-3 nicety; not now.
- **18-D2 — Feedback `# DATA` #2 "export to multiple formats (json, csv…)".** FU-359 left it; backups are JSON, per-surface CSV exists where it makes sense (stock overview, recipes). Recommend **won't-do** for a generic multi-format export; record the decision.
- **18-D3 — Keep the multipart `curl` fallback on `/backup/inspect`?** (18-R15). Recommend keep.
- **18-D4 — Restore semantics are "add, never overwrite, never delete".** Correct per the docstring and the help entry; a true "replace install" mode (wipe + restore) is a separate feature — not asked for.
- **18-D5 — `UserLlmProvider` backup section** (FU-625) — small, additive, with `api_key_encrypted` excluded; recommend bundling with 18-R3's catalogue work since `Section` gains fields anyway.

#### C9. Hand-rolled-vs-library verdicts
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| Chunked resumable upload (`uploads.py` + `useChunkedUpload`) | 380 lines both sides | tus / flask-tus, Uppy | **keep** | — | Admin-only, two callers, 8 MB chunks with resume-by-offset; a protocol library adds a client bundle and a server dep for no new capability. |
| Streaming JSON inspect | `ijson` | — | already library | — | — |
| Spreadsheet parsing | `openpyxl` + stdlib `csv` | pandas | **keep** | — | pandas would be the heaviest dep in the app for one importer. |
| Restore FK resolution | hand-rolled maps in `restore_shared.py` | — | **keep** | — | Reflection-driven (`_resolve_fk_target` reads SQLAlchemy FKs); the hand maps are the *policy* (hard/soft/required), not the plumbing. Fix the stale entries (18-R1). |
| `_coerce_to_date` | 4 strptime formats | `dateutil.parser` | **keep + locale order** (18-R12) | — | `dateutil` guesses; the install knows. |
| Client CSV escaping | 15 lines | papaparse | **keep, centralise** (18-R8) | — | — |

#### C10. Standards drift (R-0NN)
- **R-003** — section catalogue in two languages (18-R3); `describeError` ×3, download helpers ×2, `.settings-*` CSS ×2 (18-R7/R8/R13); `"zone"` literal (18-R23); import re-implements create defaults (18-R20).
- **R-005** — raw table access: carve-out for generic dump/restore (explain in place); import inserts (fix); username lookup (fix) — 18-R20.
- **R-021** — naive `datetime.now()` (18-R4); locale-blind date order (18-R12).
- **R-001** — 1,337-line page (18-R18).
- **R-045 / FU-716** — raw `fetch` + hand-built URLs (18-R7).
- **R-035 / D-rules** — bare icon strings `'warning'` (`AdminDataBackupRestore.vue:54, 114`, `AdminDataImport.vue:124`), `'check_circle'`/`'error'` (`:269`, `:222`) → `ICONS`; `text-color="dark"` (`:53`) and `text-color="white"` (`:228`, `AdminDataImport.vue:249`) → FU-671 sweep; `html: true` dialogs (18-R5); inline `style="max-width: 120px"` / `"min-width: 280px"` (`:345, :358`) → classes.
- **Security** — admin gate on all 19 `DATA_ROUTER` routes ✓ (pinned); upload ids validated / uuid converter ✓; secrets excluded ✓; 18-R5 is the one `innerHTML` sink.

#### C11. Ride-along signals for FU-010 / FU-224 (theme / colour)
- `color="warning"` chips with `text-color="dark"` (Sensitive) vs `"white"` (duplicate) on the same page — one is wrong on one theme; both should be the `--text-on-warning` token (FU-674 family).
- `.backup-row:hover` uses `color-mix(var(--brand-primary) 4%, …)` — a pattern worth a `--surface-hover` token (chunk 20 theme list).


### E. Proposed follow-ups (orchestrator allocates ids)

- **urgent · bug** — partial restore 500s on `KeyError: 'meal_recipes'` (18-R1); stale `meal_*` FK entries. Resolution: **now** (Stage 2, chunk 18) + D1/D6.
- **urgent · bug** — UI "New backup" default selection is rejected (`product_barcodes`) and UI backups omit recipe steps/tools/tags/vocab (18-R2/R3). Resolution: **now**; **confirm in browser** that the default create fails today before closing.
- **bug** — import stamps naive local time (18-R4). Resolution: **now**.
- **finding · security-hygiene** — sheet name rendered as HTML in a confirm (18-R5). Resolution: **now** (with 13-R26).
- **finding** — `Backup.sha256` never verified; `status` always `ready` (18-R14). Resolution: **now** (6-line check) or docstring fix.
- **resolve FU-716** when 18-R7 lands; append `useChunkedUpload` to FU-571's cleared list.
- **append to FU-923** — raw-table sites in `import_spreadsheet.py` (fix) and the documented carve-out for `backup/inspect/restore` (explain).
- **finding** — date order ignores `AppSetting.locale` (18-R12). Resolution: **now** (small) — or fold into chunk 20's locale pass (FU-043).
- **decision** — 18-D2 multi-format export → recommend won't-do; 18-D1 scheduled backups → Phase 3 nicety; 18-D5 bundle FU-625 with 18-R3.
- **ride-along** — `SettingsFileDrop.vue` (251 lines, this chunk's only unread file) gets a read in Stage 2 when 18-R18 splits the page.
- **VERIFY** — after 18-R3, the three "Backup → restore round-trips …" bullets (Cookbook chunks 6/7/8) can be walked once with a UI-created backup (today they cannot pass via the UI).

---

## Chunk 19 — Ops / self-host
*Source: [`CHUNK_19_ops_self_host.md`](../05_investigations/finalisation/CHUNK_19_ops_self_host.md) · analysed 2026-10-23*

### C. Senior review — Ops / self-host

#### C1. Bugs (verified or high-confidence latent)

**19-R1 — The Docker image builds the SPA in SPA mode, not PWA mode.** class: verified · where: `Dockerfile:66` `RUN quasar build` vs `web_app/package.json:19` `"build": "quasar build -m pwa"` (FU-336, 2026-07-13) and `packaging/build-linux.sh:68` `npm run build` · what's wrong: the self-host image — the primary deployment — ships **no service worker, no manifest, no install prompt, no offline cache**; everything chunk 17 analysed is absent in the container while `nginx.conf:45` dutifully no-caches a `sw.js` that isn't there. FU-336's resolution note verified `npm run build` locally, never the image. · exact change: `RUN npm run build` (one source of truth for the build mode); add a build-time assertion `test -f dist/spa/sw.js` after it so the image can't regress. · blast: S · guard: A6.1 + a `Dockerfile` smoke in FU-721's CI when revived · verdict: **execute** · **urgent**.

**19-R2 — A `web_app/.env` on the build host is baked into the Docker image's SPA.** class: high-confidence latent · where: `.dockerignore:3` excludes only the root `.env`; `Dockerfile:47–48` `COPY web_app/ ./`; README §1 instructs `cp web_app/.env.example web_app/.env` (`VITE_API_BASE_URL=http://localhost:5170/api`); `backendUrl.envDefault()` prefers a baked `VITE_API_BASE_URL` over the hostname fallback (`backendUrl.ts:37–39`) · what's wrong: an operator who followed README step 1 and then ran step 4 (`docker compose up --build`) gets an SPA that calls `localhost:5170` from every browser — works on the host, breaks from every other device; nothing in the build warns. · exact change: `.dockerignore` += `web_app/.env`, `web_app/.env.*`, `!web_app/.env.example` (and `**/.env` generally); README step 1 should say the frontend `.env` is for `quasar dev` only. · blast: S · guard: A6.2 · verdict: **execute**.

**19-R3 — The update check points at the wrong GitHub repo slug.** class: verified · where: `get_version.py:26` `https://api.github.com/repos/BenTalese/DashyDora/releases/latest` vs `git remote` `BenTalese/dashy-dora` (and `support_channel.py:53`, README `:115` — both `dashy-dora`) · what's wrong: unless GitHub still redirects an older name, every "Is there a newer Dora?" check 404s and Help/About shows "Couldn't check for updates (HTTP Error 404…)" forever; the error is swallowed into the DTO so nothing logs it. · exact change: one `GITHUB_REPO = "BenTalese/dashy-dora"` constant in `version_info.py`, used by `get_version.py` and `support_channel.py` (R-003); confirm with one `curl` at Stage 2. Also update CLAUDE.md Naming (the *GitHub* repo is already renamed; only the local folder is `DiscountDora`). · blast: S · guard: D4 · verdict: **execute**.

**19-R4 — README tells a new operator four things that are no longer true.** class: verified docs · where: `README.md:100` "There's no packaged release yet"; `:135` "Start Postgres first (the standard datastore)" while `compose.yml:85–93` makes SQLite the production-compose default "on purpose"; `:202` "`5172` — merchant_api" (removed Phase D); `:279` "merchant + emailer compile-check" + "CI runs on every push" (both workflows are commented out, FU-721). Plus `.env.example:8–9` appsettings path (`config/dapi.appsettings.json` → `<DATA_DIR>/config/`), `.env.example:2`/`nginx.conf:1`/`build-linux.sh:2,47` still say "DiscountDora/Discount Dora" (CLAUDE.md Naming). · exact change: rewrite those lines; state the posture once ("Postgres for dev + managed, SQLite for the single-box self-host image; both supported — Decision 5") so README and compose agree. · blast: S · verdict: **execute**.

**19-R5 — Two log-level resolvers; the layered one is dead.** class: verified · where: `DoraConfig.get_log_level()` (`configuration_manager.py:190–223`: env → JSON `LOG_LEVEL` → profile default, 30 lines) has **no caller**; `configure_logging` (`logging_setup.py:96–102`) resolves from `debug` + raw `DORA_LOG_LEVEL`. Consequences: the JSON `LOG_LEVEL` key the file generates on first boot does nothing; an invalid `DORA_LOG_LEVEL` is silently ignored in one place and mapped to `NOTSET` in the other; the comment at `.env.example:120` lists FATAL which `getattr(logging,…)` also accepts — fine. · exact change: `configure_logging(level=DORA_CONFIG.get_log_level())`, drop the env read inside `logging_setup.py`, drop the `if/elif` ladder for `logging.getLevelName`/`getattr`, and log a one-line warning for an unknown value. · blast: S · guard: D2 · verdict: **execute** (R-003).

**19-R6 — `/api/health` logs at INFO on every probe.** class: verified · where: `health_check.py:356` · what's wrong: every open client polls it every 60 s (chunk 17) and a cold load hits it up to 9× (13-R37); in an `INFO` install this is the dominant log line and drowns FU-640's signal. · exact change: `_Logger.debug(...)` or remove (gunicorn's access log already records the request). · blast: S · verdict: **execute**.

#### C2. Redundancy / DRY (R-001, R-003)

**19-R7 — Repo slug ×3, product name ×N.** `DashyDora` / `dashy-dora` / `DiscountDora` across `get_version.py`, `support_channel.py`, README, compose comments, `.env.example`, `nginx.conf`, build scripts (see 19-R3/R4). · exact change: `version_info.py` owns `PRODUCT_NAME`, `GITHUB_REPO`, `CURRENT_VERSION`; shell/docs cite the one URL. · verdict: **execute**.

**19-R8 — Two "treat empty env as unset + parse int" helpers.** `configuration_manager._env/_env_int` (`:60–76`) and `gunicorn.conf._int` (`:23–30`) — gunicorn's config can't import the app (it must stay import-light), so this one is a **legitimate duplicate**; comment it as such (`# mirrors configuration_manager._env_int — gunicorn.conf must not import dora_api`). · verdict: **explain in place**.

**19-R9 — Profile read raw instead of through `current_profile()`.** `health_check.py:379` `(os.environ.get("DORA_ENV") or "development").lower()` → `current_profile().value`, so aliases (`prod`, `ci`) report canonically. · verdict: **execute** (R-003).

**19-R10 — Truthy-env parsing written five ways.** `{"1","true","yes","on"}` in `configuration_manager.py:239, 253, 306, 319, 396`, `profile.py:92, 144`, `middleware.py:263` (`("1","true","yes")` — no `on`), `desktop_app._set_default_env`. · exact change: `configuration_manager.env_flag(name, default=False)`; nine call sites. · blast: S · verdict: **execute**.

**19-R11 — The two stderr banners in `profile.py` share the box-drawing frame** (`:100–118`, `:150–164`) → `_banner(title_lines, body_lines)`. · verdict: **execute** (tiny).

#### C3. Dead code / unused fields / unread endpoints

**19-R12 — `dora_api/server_settings.py`** — legacy gunicorn settings (`workers = 4`, `bind 0.0.0.0:1809`, "startup:app"); grep: no reference anywhere; contradicts `gunicorn.conf.py`'s single-worker rule. · **execute** (delete).

**19-R13 — Dead `DoraConfig` surface.** `get_log_level` (19-R5), `get_web_app_host`, `get_web_app_port`, `_save_configuration`, `is_modification_tracking_enabled` (returns `True`, unused), `is_reloader_enabled` (returns `False`; one caller — inline the constant or keep as the documented knob). The JSON `Config` model then shrinks to `API_HOST`, `API_PORT` — at which point the whole `appsettings.json` layer serves two values that env also covers (19-D2). · **execute** (delete the dead five; keep the file for now).

**19-R14 — `dora_config:/app/config` volume** (`compose.yml:179`) — the config file lives at `<DATA_DIR>/config/` (`_resolve_config_path`), i.e. inside `dora_data`; `/app/config` is only the legacy source `migrate_legacy_appsettings` moves *out of*. The comment "legacy fallback for un-env'd vars" is wrong. · exact change: drop the volume (or point it at `/app/data/config` — but that's inside `dora_data` already); note in the compose "NOTE for existing deployments". · blast: S · verdict: **execute**.

**19-R15 — Stale instructions naming env vars that no longer exist.** `tts_synthesize.py:10` and `:162` (user-facing error text!) say "set `DORA_PIPER_BIN`" — removed by FU-333 (Bucket B strict, DB-only); `auth_helpers.py:12` "Pulled from DORA_PUBLIC_URL"; `profile.py:83` docstring example; `dora.spec:51–53` "RotatingFileHandler"; `dora.spec:60–62` pins `webview.platforms.gtk` for a pywebview the app no longer uses (`desktop_app.py:314–323`). · exact change: fix the error text to "set the Piper path under Settings → Admin → System → Voice"; drop the two spec entries. · verdict: **execute** (the `:162` one is user-visible — also a copy bug).

**19-R16 — `.dockerignore` lists `docker-compose.yml` (old filename) and `**/p2ptest`, `**/.buildozer` (the kivy branch artefacts).** Tidy: `compose*.yml` isn't needed in the image either. · verdict: **execute** (with 19-R2).

**19-R17 — `startup.sh:13,24,31` default `DORA_LOG_DIR=/app/data/logs`** while compose/Dockerfile/`.env.example` say `/app/logs` and `get_log_dir()` defaults to `<DATA_DIR>/logs/dapi`. Three defaults for one path; harmless only because compose always sets it. · exact change: make `startup.sh` echo the resolved value without inventing a default (or use the same `/app/logs`). · verdict: **execute**.

#### C4. Componentisation opportunities (R-001)
- None on this surface (operator scripts and config, not UI). `DemoBanner.vue` is a third `ShellBanner` consumer if 17-R12 lands.

#### C5. Placement / layering (R-003, R-005)

**19-R18 — `audit_retention.py` lives in `infrastructure/` but is a feature job** (reads an `AppSetting` via a function-level import from `features/app_settings` to dodge a cycle; the other five jobs live under `features/*`). · exact change: move to `features/audit/prune_audit_events.py` beside the audit feature; `startup.py` imports it like the others. · verdict: **execute**.

**19-R19 — Scheduler wiring is 80 lines inline in `bootstrap()`** (`startup.py:106–186`) with six function-level imports. · exact change: `dora_api/jobs.py: register_jobs(scheduler)` (or `features/scheduler.py`) that lists the jobs as data (`(func, trigger, id)`); `bootstrap` calls it. Also makes FU-720's "log the job table at boot" a one-liner. · blast: S · verdict: **execute**.

**19-R20 — `health_check._feature_flags` still owns three `getattr(setting, "...", default)` reads per block** for columns that all exist on `AppSetting` (`stocktake_enabled`, `nutrition_rating_scheme`, `household_headcount`, …) — the `getattr` defaults hide a renamed column as "feature off" rather than failing. · exact change: direct attribute access (the migration chain guarantees the columns; `_warn_on_schema_drift` covers the stale-DB case). · verdict: **execute** (R-003 — one truth, no shadow defaults).

**19-R21 — Seven `except Exception: pass` blocks in `health_check.py`** (`:207, 238, 263, 284, 303, 319, 335`) — the "never fail the probe" intent is right, the silence isn't: a broken DB reports every feature as off with no log line (A3). · exact change: one `_safe(block, fallback)` helper that logs at WARNING once per probe. · verdict: **execute**.

#### C6. Naming & idiom
- **19-R22** — `_Logger = logging.getLogger(__name__)` inside functions (`startup.py:315, 368`, `get_version.py:81`, `audit_retention.py:36`) vs module-level elsewhere — the same sweep as 16-R27 / 18-R25. **execute**.
- **19-R23** — `get_attributes_ending_with` has an unreachable second `return _Attributes` (`utils.py:85`). **execute** (delete).
- **19-R24** — `startup.register_routers` passes `Path() / 'dora_api' / 'features'` which `_to_package_name` turns into the dotted name — pass the string `"dora_api.features"` and drop the path pretence (the docstring already says both forms are accepted). **execute**.
- **19-R25** — `.env.example` section ordering puts the KEK (`DORA_SECRET_ENCRYPTION_KEY`) after "API server tuning" though it is one of the two secrets every server install must set; move it under "Secrets / auth" and mark it **required for email/push/AI keys**. **execute** (docs).

#### C7. Efficiency
- **19-R26** — `/api/health` does three DB round-trips per probe (`alembic_version`, AppSetting, `Product.count()`) plus `complex_is_usable` and the operational-config resolver; the docstring (`:12`) still says "never touches the DB". With chunk 17's 60 s poll × N clients this is the app's hottest endpoint. · exact change: cache `_resolve_db_schema_version()` after the first non-null answer (it changes only on deploy); fix the docstring; leave the rest (they're cheap and must be fresh). **execute**.
- **19-R27** — `_warn_on_schema_drift` runs `inspector.get_columns` for ~60 tables at every boot — fine (boot-time only). **waive**.

#### C8. Design-level findings — out of Stage-2 scope
- **19-D1 — Default compose boots production with `DORA_SECURE_COOKIES=false`**, so the "deliberate opt-out" banner fires on every default boot and the fail-closed default in `app.py` is defeated by the shipped compose. Either default compose to the app's default (unset → Secure on, which breaks plain-HTTP LAN installs until TLS) or keep `false` and drop the banner to a one-line INFO. Owner call; recommend: keep `false` (LAN-first self-host), keep the banner **once**, and add the TLS/proxy recipe (15-R1) to README.
- **19-D2 — Retire `appsettings.json`?** After 19-R13 it carries `API_HOST`/`API_PORT` only, both env-overridable; `path_migration.migrate_legacy_appsettings` + the `dora_config` volume exist for it. Recommend retiring the file (env-only; FU-333's direction) in a later release with a one-boot "ignored" warning.
- **19-D3 — `/api/health` can't say "degraded".** A DB outage still returns `ok: true`. Add `"db": "ok" | "unreachable"` (keys are only ever added). Small; chunk-17 banner could then say "Dora is up but its database isn't".
- **19-D4 — FU-640** (log 4xx on mutating routes at WARNING / raise the container default to WARNING) — owner policy call; the Stage-1 read supports option (a) + default `INFO` in the container (gunicorn already writes an access line per request, so the marginal cost is small).
- **19-D5 — FU-720 / FU-719** (route-map verification; `onerror` on `walk_packages`): FU-719's fix is one argument (`onerror=lambda name: _Logger.exception(...)`) — recommend executing it as part of 19-R19 rather than waiting; FU-720's "log registered route count per blueprint at boot" is the cheapest shape and fits the same place.
- **19-D6 — CI** stays off by owner policy (FU-721/405). Nothing here changes that; 19-R1 is exactly the class of regression CI would have caught.

#### C9. Hand-rolled-vs-library verdicts
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| `configuration_manager.py` (env → JSON → profile) | 410-line hand layering | `pydantic-settings` | **keep, shrink** | — | After 19-R13/D2 it is ~200 lines of env readers with dir side-effects; pydantic-settings would add a dependency to replace `os.environ.get`. Not worth it. |
| `profile.py` production gate | 60 lines | — | keep | — | — |
| `logging_setup.py` | stdlib handlers | `structlog` / `loguru` | **keep** | — | Request-id contextvar filter is 15 lines; structured JSON logging isn't asked for. |
| APScheduler in-process | library | Celery / RQ / cron | **keep** | — | Single-worker contract documented thrice; externalising is the parked Path-A work. |
| `get_version._semver_tuple` | 8 lines | `packaging.version` | **replace** | S | `packaging` is already a transitive dep; `Version("0.10.0") > Version("0.7.0")` is right where the naive tuple also is, but pre-release handling (`v0.8.0-rc.1`, which `release.yml` explicitly allows) is wrong in the hand version. |
| `scripts/dev-restart.sh` | 99 lines | `flask --debug` reloader | keep | — | `is_reloader_enabled()` is deliberately False (double-boot + scheduler); the script is the honest workaround. |
| Docker healthcheck via nginx `/healthz` | — | hit `/api/health` | keep | — | Documented trade-off; 19-D3 would make `/api/health` a better target later. |

#### C10. Standards drift (R-0NN)
- **R-003** — build mode in two places (19-R1); repo slug ×3 (19-R3/R7); log level ×2 (19-R5); truthy parse ×9 (19-R10); log-dir default ×3 (19-R17); profile read raw (19-R9); `getattr` shadow defaults (19-R20).
- **R-005 (distribution posture §7.5)** — ✓ repository-routed data access (health uses the repo + one raw `alembic_version` read, fine); ✓ Postgres + SQLite both tested (`test_migrations` 7/7 incl. Postgres); ✓ env/config-driven differences; ✓ auth behind an interface; ✓ no `tenant_id`; ✓ managed conveniences degrade (push/email self-gate). **Drift:** README vs compose on the datastore default (19-R4).
- **R-021** — scheduler crons run in **server** TZ (`TZ=Australia/Sydney` in compose) and the household-local jobs gate internally ✓; `prune_audit_events` cutoff is UTC ✓.
- **R-030 (operational config)** — honoured; the support channel's explicit out-of-scope note stands.
- **Naming (CLAUDE.md)** — "DiscountDora/Discount Dora" in `.env.example:2`, `nginx.conf:1`, `build-linux.sh:2,47` (19-R4); CLAUDE.md's own note about the GitHub repo is stale (19-R3).
- **Security** — `.secret_key` 0o600? `app.py:81` `write_text` uses default perms (desktop: `desktop_app.py:114` same) → `Path.touch(mode=0o600)` first; `uploads.py` already does `0o600`. Add to 19-R5's neighbour fix. **execute** (S).

#### C11. Ride-along signals for FU-010 / FU-224 (theme / colour)
- `DemoBanner.vue:8` bare icon `name="visibility"` → `ICONS`; `--brand-accent`/`--text-on-accent` pair is the same contrast question as 17-C11.
- `offline.html`'s brand hex (chunk 17) and `manifest` colours are the only places ops config carries theme — none here.


### E. Proposed follow-ups (orchestrator allocates ids)

- **urgent · bug** — Docker image builds the SPA without `-m pwa`; the self-host deployment has no service worker/manifest/offline (19-R1). Resolution: **now**; verify in the built image (A6.1).
- **bug** — `web_app/.env` is copied into the image and bakes `localhost:5170` into the SPA (19-R2). Resolution: **now** (`.dockerignore` + README).
- **bug** — version check targets `BenTalese/DashyDora`; remote is `dashy-dora` (19-R3). Resolution: **now**; one constant; also fix CLAUDE.md Naming (GitHub repo already renamed).
- **docs** — README/.env.example/nginx.conf/build scripts: stale ports, datastore posture, CI claim, old product name, appsettings path (19-R4). Resolution: **now**.
- **finding** — `DoraConfig.get_log_level` dead; two log-level resolvers (19-R5); `server_settings.py` + four dead config methods (19-R12/R13); `dora_config` volume unused (19-R14). Resolution: **now**.
- **copy bug** — Piper error text tells users to set a removed env var (19-R15). Resolution: **now**.
- **finding** — `/health` INFO log per probe + three DB reads with a "never touches the DB" docstring (19-R6/R26). Resolution: **now**.
- **execute FU-719's one-line fix** (`onerror` on `walk_packages`) and FU-720's cheapest shape (log route count per blueprint at boot) as part of 19-R19 — append to both FUs rather than new ids.
- **decision** — 19-D1 compose cookie default + banner; 19-D2 retire `appsettings.json`; 19-D3 `/health.db`; 19-D4 = FU-640 policy. Owner.
- **security hygiene** — `.secret_key` / `.secret_encryption_key` written with default perms (C10). Resolution: **now** (S).
- **replace** — `_semver_tuple` → `packaging.version` (C9). Resolution: **now** (S).
- **VERIFY** — add "Docker image: DevTools → Application shows `sw.js` registered" to the FU-336 PWA section once 19-R1 lands; mark INV-3 `LOGGING_AND_DATA_LAYOUT.md` as historical (both recommendations landed).

---

## Chunk 20 — Cross-cutting concerns
*Source: [`CHUNK_20_cross_cutting.md`](../05_investigations/finalisation/CHUNK_20_cross_cutting.md) · analysed 2026-10-23*

### C. Senior review — cross-cutting

#### C1. Bugs (verified or high-confidence latent)

**20-R1 — A second global error installer is dead code, and the live one's twin claims it is "called from boot".** class: verified · where: `useClientLogger.ts:93–127` `installGlobalErrorReporting(app)` — **no caller** (grep); its docstring (:10–13) says "`install()` (called from boot) wires global error handlers"; the real wiring is `boot/globalErrorHandler.ts` (toast + rollbacks + `clientLog.error`). If anyone *did* call it, every error would ship twice. · exact change: delete `installGlobalErrorReporting` + the stale docstring block; `useClientLogger.ts` becomes the logger only. · blast: S · guard: `globalErrorHandler.spec.ts` · verdict: **execute**.

**20-R2 — `vue-i18n` is installed, booted and unused; a comment in the money authority claims an integration that doesn't exist.** class: verified · where: `boot/i18n.ts` (41 lines, `createI18n` with a 12-line `src/i18n` message tree), `package.json:44` `"vue-i18n": "^11.0.0"`, `useMoney.ts:13–15` ("values are also fed into vue-i18n's `numberFormats` in `boot/i18n.ts`" — there are none); zero `useI18n`/`$t` consumers. PROPOSAL_LOCALE_I18N §3-2 chose "adopt-lite" (keep as the home for Intl wrappers) but the wrappers were built in `useMoney`/`useDateFormat` without it. · exact change: remove the boot file, `src/i18n`, the dependency and the `quasar.config` boot entry; fix the `useMoney` comment; record in the proposal that §3-2 resolved to (b) in practice. ~60 KB less bundle. · blast: S · guard: `vue-tsc` + build · verdict: **execute** (20-D1 asks the owner only whether Layer C is still a someday; the dead code goes either way).

**20-R3 — The "no space before the unit" list lives in two languages with a comment asking humans to keep them in sync.** class: verified (R-003) · where: `units.py:483–484` `_NO_SPACE_UNITS` ("Inclusion list MUST stay in sync with `NO_SPACE_UNITS` over there") ↔ `formatQuantity.ts:9–11`; the module already codegens `units_table.ts` via `scripts/dump_units.py`. · exact change: emit `NO_SPACE_UNITS` (and `SUB_ITEM_UNITS`, 20-R4) in `dump_units.py`; `formatQuantity.ts` imports from `generated/units_table.ts`; delete the comment. · blast: S · guard: `formatQuantity.spec.ts` + a pytest that the generated file is current (does one exist? — D2) · verdict: **execute**.

**20-R4 — Two different "countable unit" lists answer the same question on the two sides.** class: verified · where: `scaleQuantity.ts:20–32` `COUNTABLE_UNITS` (egg, clove, scoop, slice, piece, sprig, stick, knob, can, bunch, pinch) vs `units.py:617–632` `SUB_ITEM_UNITS` (clove, sprig, rasher, slice, stalk, floret, leaf, wedge, knob, splash, drizzle, handful) + `is_sub_item_unit`. Cook-mode scaling rounds "2 rashers" as continuous (→ "2.5") while the server treats a rasher as a sub-item; "1 can" rounds to whole on the client while the server has no opinion. · exact change: one server list (`units.py`) with the union, tagged per purpose if the purposes genuinely differ (`countable` for scaling vs `sub_item` for pricing), exported through the codegen; `scaleQuantity.isCountableUnit` reads it. · blast: S · guard: `scaleQuantity.spec.ts` · verdict: **execute** (owner may want to confirm "pinch" and "can" semantics — note in D2 of chunk 4's cook-mode help).

**20-R5 — `MealPlanBuilderDialog.vue:697` formats money by hand (`$${n.toFixed(2)}`).** class: verified (R-003/D-006; the one `formatMoney` bypass) · exact change: `formatMoney(n)`. · verdict: **execute**.

**20-R6 — `ReportsPage.vue:369` formats a date with `toLocaleDateString(undefined, …)` (browser locale).** class: verified (D-006; the one `useDateFormat` bypass after DR-14) · exact change: `formatDate(iso, opts)`. · verdict: **execute**.

**20-R7 — Sorting collates in `'en'` while display follows the household locale.** class: latent (R-003) · where: `new Intl.Collator('en', { sensitivity: 'base' })` ×5 — `useStockFilters.ts:341`, `recipeStore.ts:20`, `stockItemStore.ts:20`, `stockLocationStore.ts:20`, `storesStore.ts:20`. Harmless for `en-*` locales (the only shipped ones), but it is five copies of a collator that should come from the locale authority. · exact change: `useMoney.ts` (or a renamed `useLocalePolicy`) exports `nameCollator()` built from `currentLocale()` and cached; five call sites. · blast: S · verdict: **execute**.

**20-R8 — `--ring-focus` is overridden in 5 of 14 theme blocks; the other 9 inherit Pesto's green halo.** class: verified (13-R40 widened) · where: `tokens.scss:153–154` (`--focus-ring: var(--brand-primary)`; `--ring-focus: hsla(150,76%,39%,.35)` — a literal), `themes.scss:77–78, 128–129, 195–196, 267–268, 334–335` only. · exact change: define `--ring-focus: color-mix(in srgb, var(--brand-primary) 35%, transparent)` **once** at `:root` (it then follows every theme automatically) and delete the five per-theme copies; then rename to one token (`--focus-ring` solid, `--focus-ring-soft` halo) and update the 33 call sites. · blast: S · guard: visual (A6.1) · verdict: **execute**.

**20-R9 — `submit_client_log._buckets` never evicts keys.** class: latent · where: `submit_client_log.py:44–77` — one `deque` per session-id/IP, created on first sight, never removed; anonymous crawlers over a long uptime grow the dict without bound (each key ~100 B — slow, but it is a leak). Also `:63` literal `"user_id"` (FU-654/15-R14), `:9–11` docstring says the audit persist is "a follow-up round" (it exists at `:105–124`), `:92–95` comment says "429" while the code returns 204 (deliberately — the comment lies). · exact change: drop empty buckets after the window sweep; `SESSION_USER_ID_KEY`; fix the two comments. · blast: S · guard: `test_client_logs` (13) · verdict: **execute**.

**20-R10 — Toasts use two placement conventions.** class: verified vs D-009 · where: `position: 'bottom-right'` ×269 vs `'top'` ×23 (network/PWA/install toasts) vs `'bottom'` ×2; `quasar.config` sets no default, so 322 call sites each restate it. · exact change: set `framework.config.notify.position = 'bottom-right'` once in `quasar.config.ts`, remove the 269 restatements (mechanical), and decide whether the 23 `top` toasts are a deliberate second budget (connection/system notices) — D-009 allows one floating layer per edge; recommend keep `top` for *system* toasts only and document it in `notifyTypeRegistration.ts`. · blast: M (mechanical) · verdict: **execute** (the default) + **decision** (the `top` set).

#### C2. Redundancy / DRY (R-001, R-003)

**20-R11 — No `useConfirm`; 50 hand-rolled `$q.dialog` confirms in 26 files.** tracked: 13-R26, 16-R22, 18-R9 · exact change: `composables/useConfirm.ts` → `confirm({ title, message, okLabel, destructive?: boolean, persistent?: boolean }): Promise<boolean>` wrapping `$q.dialog` with: `cancel: { flat: true, noCaps: true }`, `ok: { noCaps: true, color: destructive ? 'negative' : 'primary' }`, **never `html: true`** (18-R5; 4 sites today), copy suffix "This can't be undone." when `destructive`, Esc = cancel. Migrate the 50 sites (several already wrap it in a Promise by hand — `AdminDataBackupRestore.confirmAsync`). · blast: M (mechanical; copy stays) · guard: a Vitest for the composable · verdict: **execute**.

**20-R12 — Text-size scale vs the type floor.** where: `themeService.ts:321–326` roots at 14/16.5/20.5/23 px; `--font-size-xs` is a ratio token — at `sm` a `0.75` ratio yields 10.5 px, under D-003's 12 px floor for captions. · exact change: either floor `sm` at 16 px (and make the steps 16/18/20/23) or clamp caption tokens with `max(12px, …)` in `tokens.scss`. The owner's feedback asked for 75/100/150 % steps — 13-D4 recorded 87.5–125 % as the question; this finding is the floor interaction, not the range. · blast: S · verdict: **execute** the clamp; **decision** 13-D4 for the range.

**20-R13 — Shared primitives still carry bare Material icon strings** (`SettingsSection` ×3, `SettingsRow` ×2, `SettingsPageHeader` ×2, `BaseDialog` ×2, `CollapsibleCard` ×2, `DashboardCard` ×2, `FilterBar` ×3, `MealPlanRailDisclosure` ×2, `PageErrorState` ×4, `ShortcutsCheatsheet` uses `ICONS` ✓). Fixing the 12 primitive sites fixes them on every page at once; the remaining ~30 page sites (`StockItemDetailPage` 8, `HelpPage` 3, `ScanOverlay` 3, …) are a mechanical sweep. · verdict: **execute** (A7).

**20-R14 — Image-cap literal `6_000_000` ×9 in `dora_api`** (16-R11) → `infrastructure/images.py: MAX_IMAGE_DATA_URL_LEN` + a shared `ImageField`. · **execute**.

**20-R15 — `.settings-page` / `.settings-divider` / `.settings-actions` / `.settings-list` scoped CSS copied across settings pages** (13-R9, 18-R13) → `SettingsShell`-level global classes or a `settings.scss` partial. · **execute under 13-R9**.

**20-R16 — Two segmented controls** (FU-848: `BaseSegmented` 13 consumers, `DoraSegmented` 9) — the FU's own plan (merge onto the hand-rolled radiogroup, since `q-btn-toggle` fights the active ink with `!important`) stands. · **execute** (FU-848).

**20-R17 — `FONT_SIZE_PX`, the font list, and the theme families are already single-sourced in `themeService`** ✓ (FU-614). No finding; noted so Stage 2 doesn't look.

#### C3. Dead code / unused fields / unread endpoints

**20-R18 — `ShortcutsCheatsheet.vue:74` `var(--q-grey-5, var(--border-strong))`** — a Quasar palette variable as the *primary* value with the token as fallback; R-002 inverted. · exact change: `var(--border-strong)`. · **execute**.
**20-R19 — `useShortcut` is consumed by 3 files; `'/'` is registered twice (Global + Stock overview, same handler intent)** — the page registration is redundant (newest-first lookup makes it win, but Global already does the same thing). · exact change: drop `StockOverview.vue:1012`. · **execute** (tiny).
**20-R20 — `rollbackRegistry.registerRollback` has one producer** (`stockItemStore`) — the "undo cross-app" feedback (MISC #2) is about the *undo* feature (chunk 6/7), not this registry; the registry is correct and small. **waive**.
**20-R21 — `PageErrorState` `style="max-width: 480px"` inline + the four bare icons + `travel_explore`/`cloud_off`/`block`/`error_outline` not in `ICONS`.** · **execute** with 20-R13.
**20-R22 — `api_response.endpoint_not_found` returns a bare tuple (plain JSON) while every sibling returns `application/problem+json`** — documented as deliberate (FU-167) at `:184–189`; keep, but the function is the only one not returning `Response` (type drift). **explain in place** (already is).

#### C4. Componentisation opportunities (R-001)

**20-R23 — `useConfirm`** (20-R11) is the one new primitive this chunk adds. **20-R24 — `ShellBanner`** (17-R12) and **`CountBadge`** (FU-920 rename of `MealPlanRailCount`) are the two component renames/merges inherited here. · **execute** (S each).

#### C5. Placement / layering (R-003, R-005)

**20-R25 — The locale authority lives in `useMoney.ts`** (`currentLocale`, `ensureLocalePolicy` consumed by `useDateFormat`; 20-R7 would add a collator). The file is named for one consumer of the policy. · exact change: `composables/useLocalePolicy.ts` owns `policy`/`load`/`currentLocale`/`currencySymbol`/`nameCollator`; `useMoney` and `useDateFormat` become thin consumers. · blast: S (re-exports keep call sites stable) · **execute**.

**20-R26 — `formatQuantity`/`scaleQuantity` are `helpers/`, `useDateFormat`/`useMoney` are `composables/`** — all four are pure formatting authorities (D-006); the non-reactive two don't need the composable shape, the reactive two don't need `helpers/`. Fine as is; **waive** (naming only).

**20-R27 — FU-923 raw-table sweep list (consolidated):** `products/get_products.py` (10-R12), `app_settings` readers (13-R32), `get_ingestable_products.py:81,89`, `get_ingest_stores.py:49`, `ingestion_auth.py:43` (16-R24), `import_spreadsheet.py:510,616,647` (18-R20 — fix), `backup_library.py:268` (18-R20), the dump/restore engine (18-R20 — **explain**), `audit_retention.py:40`, `health_check.py:67` (`alembic_version` — explain). · **FU-923** owns it.

**20-R28 — FU-654 / 15-R14 session-key sweep list (consolidated):** `logout.py:15`, `middleware.py:79,233`, `submit_client_log.py:63` + the assistant/budget/users/onboarding prologues chunks 11–14 listed. · **execute** (one helper, one import).

#### C6. Naming & idiom
- **20-R29** — `clientLog.debug/info` carry blank-line gaps where an `eslint-disable-next-line no-console` used to be (`useClientLogger.ts:70, 74, 78, 83`) — tidy. **execute** (trivial).
- **20-R30** — `FormErrorSummary.vue:9` `v-slot:avatar` vs `#avatar` everywhere else. **execute** (trivial).
- **20-R31** — `error_translation.py:19–21` says "the map mirrors the small client-side translation file (FU-097 pattern for `format_quantity`)" — the client has no translation file; delete the sentence. **execute**.

#### C7. Efficiency
- **20-R32** — `useDateFormat.getFormatter` keys the cache by `JSON.stringify(opts)` per call — fine (small objects). **waive**.
- **20-R33** — `paletteToken` runs `getComputedStyle` per token per computed re-run; Reports resolves 6 per theme change. **waive** (theme changes are rare).
- **20-R34** — 322 `Notify.create` sites each pass `position` — after 20-R10 the bundle loses ~269 object literals. Cosmetic.

#### C8. Design-level findings — out of Stage-2 scope
- **20-D1 — Layer C (multi-language UI).** PROPOSAL_LOCALE_I18N §2.5 defers it; 20-R2 removes the dormant scaffold. If the owner wants to keep the *option* visibly open, keep the proposal line, not the dependency.
- **20-D2 — Toast placement budget (D-009):** keep `top` for connection/system notices and `bottom-right` for everything else, or one edge for all? Recommend the two-tier rule, written into `notifyTypeRegistration.ts`.
- **20-D3 — Text-size range** = 13-D4 (owner asked 75/100/150 %; shipped 85/100/125/140 %). 20-R12 handles the floor either way.
- **20-D4 — Help page shape.** **Decided + built 2026-10-29** (one page per topic, search, Common questions, screenshot slot; worklog).  ~105 proposed entries across 20 chunks will not fit six expandable groups; recommend one page per group (route per group, same `?q=` filter across all), a top-level **FAQ** group built from the question-shaped titles (`# HELP` #3), and an owner-supplied screenshot slot per entry (`# HELP` #5) — the HelpPage entry type gains an optional `image`. Design-level because it changes the Help IA; the per-surface content is ready.
- **20-D5 — FU-010 / FU-224 inputs (handed over, not decided):** `--text-on-primary` pure white in 5 themes (FU-674 measurements); `text-color="white"` on `warning`/`negative` chips in 16 files (FU-671); `color="secondary"` usage audit (FU-224) — `grep -c 'color="secondary"'` in Stage 2; the `--ring-focus` halo (20-R8); `AuthShell`'s private DEC-2 ladder vs theme tokens (15-R10/R6); `offline.html`/manifest brand hex (17); the `.backup-row:hover` `color-mix` pattern → a `--surface-hover` token (18-C11); `DemoBanner`/`OfflineBanner`/`UpdateBanner` accent-on-primary pairs (17/19 C11). These are the colour-system facts the holistic review needs; none is a Stage-2 change on its own beyond the token fixes already listed.
- **20-D6 — Usage analytics (MISC #17)** — answered **no** in chunk 19 §F (privacy posture; error telemetry only).
- **20-D7 — "UI should feel more unique / Quasar base customisation" (MISC #16, #15)** — this *is* FU-010's remit; the token system (127 tokens, 14 themes, Base\* primitives at 542/66/30 adoption) is the mechanism; what remains is the owner's visual pass.

#### C9. Hand-rolled-vs-library verdicts (the plan §3.3 list for this chunk)
| Site | What it is | Library alternative | Verdict | Effort / risk | Note |
|---|---|---|---|---|---|
| `useMoney` / `useDateFormat` | `Intl.*` wrappers + one cache | `vue-i18n` `n()`/`d()` | **keep; remove vue-i18n** (20-R2) | S | The wrappers are 260 lines and already the authority; vue-i18n would re-wrap the same `Intl` calls. |
| `useShortcut` | 139-line registry with sequences | `@vueuse/core` `useMagicKeys` / `tinykeys` | **keep** | — | Sequences (`g s`), typing-target guard and the cheatsheet registry are the value; tinykeys would still need the registry. |
| `rollbackRegistry` | 26 lines | undo/redo libs | **keep** | — | It is not an undo stack; it reverts optimistic UI on crash. |
| `AppSkeleton` | 71 lines | `q-skeleton` | **keep** | — | Quasar's is per-type and not token-aware; this one reads `--surface-sunken`/`--text-muted`. |
| Toast layer | Quasar Notify + 2 registered types | — | keep; **set one default position** (20-R10) | S | — |
| `apiErrorHandler` + `error_translation` | FU-099 shape | — | keep | — | Server-authoritative copy is the right call; 6 + tests pin it. |
| Theme tokens + `themeService` | hand-rolled CSS-var system, 14 themes | Quasar's `setCssVar` only / a design-token build | **keep** | — | The `themeService` already re-points Quasar's palette; a token build step would add tooling for no new capability. |
| `formatQuantity`/`scaleQuantity` | 150 lines | `Intl.NumberFormat` unit style / fraction libs | **keep; single-source the lists** (20-R3/R4) | S | Fraction glyph snapping and the DEC-3 spacing rule are domain, not formatting. |
| `useFormErrors` | 80 lines | VeeValidate / vuelidate | **keep** | — | Server-side validation is the authority (R-020); a client validator would duplicate it. |
| `submit_client_log` rate limit | in-memory sliding window | `flask-limiter` | **keep** (fix eviction, 20-R9) | — | Same single-worker constraint as 15-R1 notes. |

#### C10. Standards drift (R-0NN)
- **R-003** — unit lists ×2 (20-R3/R4); money/date bypasses (20-R5/R6); collator ×5 (20-R7); image cap ×9 (20-R14); confirm pattern ×50 (20-R11); toast position ×322 (20-R10); session key literal (20-R28); dead i18n claim (20-R2); `_buckets` (20-R9).
- **R-001** — `useConfirm` missing (20-R11); FU-848 (20-R16); FU-920 (20-R24).
- **R-002 / D-017** — `--q-grey-5` (20-R18); hex outside the ladder: `ScanOverlay:403,436,440,496` (camera frame — `#000` is arguably legitimate for a viewfinder; the green/red/pink are semantic → `--semantic-*`), `ImageEditTile:163` + `DoraModeSlider:142` `#fff` → `--text-on-primary`, `VoicePicker:484–485` `var(--negative, #c10015)` → `--semantic-negative`; `RecipeNutriScore` keeps the official grade colours (comment the carve-out); `paletteToken` fallbacks in `DashboardPage`/`ReportsPage` are documented pre-paint fallbacks — move them beside `CHART_RAMP_FALLBACKS` so there is one fallback table (R-003).
- **R-035 / D-002** — FU-671 (16 files), FU-674 (5 themes) — the sweep lists above.
- **A6 / D-016** — `outline: none` ×21 in 15 files (FU-841 is one); each needs a `:focus-visible` replacement ring (`--focus-ring`). **execute** as one sweep.
- **A7** — 48 bare icons (20-R13).
- **A8 / FU-836** — `col-lg-*` ×2 → `col-md-*`. **execute**.
- **D-003** — text-size floor (20-R12).
- **D-006** — 20-R5/R6/R7.
- **D-008 / B6** — `html: true` ×4 (20-R11 kills them); `persistent: true` ×5 (keep where destructive).
- **D-009 / B7** — 20-R10.
- **R-045** — raw `fetch` ×21 (18-R7 + FU-647; `useClientLogger`'s is explained in place ✓).
- **R-052** — `offline.html` (17-R2) ✓ handled there.

#### C11. Ride-along signals for FU-010 / FU-224 (theme / colour) — consolidated hand-over
See 20-D5. Plus the raw numbers: 14 theme blocks; 127 root tokens; `--text-on-primary` white ×5; `--ring-focus` literal at root; `text-color="white"` ×24; `color="warning"`+white badges in chunks 16/18; `--q-negative`/`--q-accent` banners in chunk 17; hex outside the ladder ×8 files (above).


### E. Proposed follow-ups (orchestrator allocates ids)

- **finding (verified)** — dead second global-error installer with a stale "called from boot" docstring (20-R1). **now**.
- **finding (verified)** — `vue-i18n` + `boot/i18n.ts` + `src/i18n` unused; `useMoney` comment claims a numberFormats hook that doesn't exist (20-R2). **now**; amend PROPOSAL_LOCALE_I18N §3-2 to record the de-facto (b).
- **finding (R-003)** — unit lists duplicated across languages (20-R3/R4). **now**, via the existing codegen.
- **bug (D-006)** — one money bypass, one date bypass (20-R5/R6). **now**.
- **finding (R-003)** — `'en'` collators ×5 (20-R7). **now** with 20-R25.
- **finding (13-R40 widened)** — `--ring-focus` theme-inconsistent; two focus tokens (20-R8). **now**.
- **finding** — `_buckets` leak + stale comments + session-key literal in `submit_client_log.py` (20-R9). **now**.
- **finding (D-009)** — toast position restated ×322; no default (20-R10). **now** (default) · **decision** 20-D2.
- **sweep FUs to open (one each, with the counted site lists above):** `useConfirm` adoption (50 sites); bare-icon sweep (48, start with the 12 primitive sites); `outline: none` A6 sweep (21); FU-671 `text-color="white"` (24/16 files — **append** the list to FU-671); hex-outside-ladder (8 files — classify as listed); `col-lg` (2 — **append to FU-836**, then close it).
- **decision** — 20-D3 text-size range (= 13-D4); 20-D4 Help IA (one page per group + FAQ + screenshot slot) — needed before the ~105 entries from chunks 1–19 can land; 20-D1 Layer C.
- **hand-over** — 20-D5's inventory appended to **FU-010** and **FU-224** so the owner's visual review starts from measured facts.
- **resolve FU-920** (`CountBadge` rename) and **FU-848** (segmented merge) in Stage 2 — both are mechanical with the lists in hand.

---
