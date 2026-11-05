import AxiosHttpClient from './axiosHttpClient';

/** Where a food's numbers came from. Every lookup result carries one so the
 *  picker can badge it — three catalogues can disagree about a banana, and
 *  hiding which one answered would be dishonest (P3). */
export type NutritionSourceKind = 'dataset' | 'api' | 'web';

export interface NutritionSourceStatus {
    id: string;
    label: string;
    kind: NutritionSourceKind;
    /** Can this source answer a lookup right now? Derived server-side from
     *  installed reality (rows present / key set / network allowed), never
     *  from a stored flag. */
    available: boolean;
    food_count: number;
    /** Dataset sources only: imported before food categories and the extra
     *  nutrients, so a re-import fills them (FU-750 / FU-645). */
    needs_reimport?: boolean;
    /** Dataset sources only — transient import progress. */
    phase?: 'idle' | 'downloading' | 'parsing' | 'saving' | 'done' | 'error';
    error?: string | null;
    default_url?: string;
    /** FU-636: the built-in release link 404'd (USDA replaced the release);
     *  `downloads_page` is where the current link lives. */
    release_gone?: boolean;
    downloads_page?: string;
    /** Bytes received so far in the `downloading` phase. */
    bytes_done?: number;
    /** Total download size from `Content-Length`. **0 means the origin didn't
     *  say** — treat it as unknown and fall back to an indeterminate bar
     *  rather than dividing by it. */
    bytes_total?: number;
    /** Cumulative CSV rows read in the `parsing` phase. There is deliberately
     *  no total to divide by: the archive's row count isn't known until it has
     *  been read, so this is a live count, not a percentage. */
    rows_done?: number;
    foods?: number;
    portions?: number;
}

export interface NutritionSourcesResponse {
    mode: 'off' | 'simple' | 'complex';
    sources: NutritionSourceStatus[];
    any_available: boolean;
}

/** One candidate from the unified lookup. `id` is set only for foods already
 *  held locally; live suggestions carry null until the user confirms one and
 *  `resolveFoodAsync` persists it. */
export interface NutritionFoodResult {
    id: string | null;
    source: string;
    source_label: string;
    source_ref: string;
    name: string;
    brand: string | null;
    barcode: string | null;
    kcal_per_100g: number | null;
    protein_g_per_100g: number | null;
    carbs_g_per_100g: number | null;
    fat_g_per_100g: number | null;
    portions: { amount: number; measure: string; gram_weight: number }[];
    /** `barcode` when a typed EAN matched exactly, `name` otherwise. */
    match: 'barcode' | 'name';
    exact: boolean;
}

export interface NutritionLookupResponse {
    query: string;
    is_barcode: boolean;
    results: NutritionFoodResult[];
    sources_queried: string[];
    /** Sources that were asked but didn't answer. Surfaced rather than
     *  swallowed — "no results" and "one source is down" are different
     *  situations and the user deserves to know which they're in. */
    sources_failed: { source: string; source_label?: string; error: string }[];
}

/** A food the matcher thinks might describe a stock item. Never a saved link —
 *  it exists only until the user accepts it, ignores the item, or searches for
 *  something better. `confidence` and `is_strong` both travel so the UI can
 *  visibly hedge a weak guess without re-deriving the threshold (R-003). */
export interface NutritionFoodSuggestion {
    nutrition_food_id: string;
    name: string;
    brand: string | null;
    source: string;
    source_label: string;
    kcal_per_100g: number | null;
    confidence: number;
    /** Near-certain. The only band the bulk accept-all verb touches. */
    is_strong: boolean;
}

export interface UnmatchedStockItem {
    stock_item_id: string;
    name: string;
    /** Null when nothing in the local catalogue scored well enough. That's a
     *  real answer, not a loading state — most pantries hold things a food
     *  catalogue should never match. */
    suggestion: NutritionFoodSuggestion | null;
}

export interface UnmatchedItemsResponse {
    items: UnmatchedStockItem[];
    suggested_count: number;
    strong_count: number;
    ignored_count: number;
    /** Populated only when asked for — the page loads them on demand behind
     *  the "show ignored" toggle. */
    ignored_items: UnmatchedStockItem[];
    /** How many foods are installed locally. The matcher only ever reads the
     *  local catalogue, so 0 means it cannot suggest anything at all — a
     *  different state from "everything is already matched", and the one that
     *  gets mistaken for a broken feature. */
    catalogue_size: number;
}

export default class NutritionApiService {
    private httpClient = new AxiosHttpClient();

    getSourcesAsync = async (): Promise<NutritionSourcesResponse> =>
        await this.httpClient.get<NutritionSourcesResponse>('/nutrition/sources');

    lookupAsync = async (query: string): Promise<NutritionLookupResponse> =>
        await this.httpClient.get<NutritionLookupResponse>(
            `/nutrition/lookup?q=${encodeURIComponent(query)}`,
        );

    /** Persist a picked live suggestion and get back the saved food. Only
     *  (source, source_ref) travels — the server re-fetches the values, so the
     *  client can't write arbitrary nutrition numbers. */
    resolveFoodAsync = async (
        source: string,
        sourceRef: string,
    ): Promise<{ id: string; name: string; source_label: string }> =>
        await this.httpClient.post<{ id: string; name: string; source_label: string }>(
            '/nutrition/foods/resolve',
            { source, source_ref: sourceRef },
        );

    /** The settings badge's number, without the matcher's suggestions (FU-858). */
    getUnmatchedItemCountAsync = async (): Promise<number> =>
        (await this.httpClient.get<{ count: number }>('/nutrition/unmatched-items/count')).count;

    /** Every stock item with no nutrition food, each with its best local
     *  match. Suggestions are local-catalogue only — this runs across the whole
     *  pantry, and a live source would mean hundreds of round-trips. */
    getUnmatchedItemsAsync = async (
        includeIgnored = false,
    ): Promise<UnmatchedItemsResponse> =>
        await this.httpClient.get<UnmatchedItemsResponse>(
            `/nutrition/unmatched-items${includeIgnored ? '?include_ignored=1' : ''}`,
        );

    /** Link every item whose suggestion is a near-certainty. The server
     *  recomputes the matches rather than trusting a list from here, so this
     *  can only ever confirm what the matcher would have suggested anyway. */
    acceptAllSuggestionsAsync = async (): Promise<{ linked_count: number }> =>
        await this.httpClient.post<{ linked_count: number }>(
            '/nutrition/suggestions/accept-all',
            {},
        );

    /** Kick off a bulk dataset import. `url` overrides the built-in USDA
     *  release URL — needed when a release is superseded (the filename carries
     *  its date) or on an air-gapped install pointing at a local mirror. */
    startDatasetImportAsync = async (
        source: string,
        url?: string,
    ): Promise<NutritionSourcesResponse> =>
        await this.httpClient.post<NutritionSourcesResponse>(
            '/nutrition/datasets/import',
            url ? { source, url } : { source },
        );
}
