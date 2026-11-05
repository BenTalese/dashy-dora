// Mirrors LocationNodeDto from dora_api/features/locations/get_location_tree.py.
//
// The old `AttentionReasons` / `attention_score` / `attention_reasons` /
// `attentionColor` / `attentionBackground` / `summarizeReasons` exports
// were remnants of the killed stock-map / location-heatmap feature —
// computed server-side on every request but never rendered by any Vue
// surface. Removed in the 2026-07-04 stocktake-mode cleanup along with
// the backend `features/locations/attention.py` module.
export type LocationKind = 'zone' | 'area' | 'section';

/** The stock overview's location filter value for items with no location
 *  (FU-633). Never a real id: location ids are UUIDs. */
export const NO_LOCATION_FILTER = 'none';

export type LocationItem = {
    stock_item_id: string;
    name: string;
    stock_level_name: string | null;
    expiry_date: string | null;
    is_essential: boolean;
};

export type LocationNode = {
    location_id: string;
    name: string;
    kind: LocationKind;
    parent_id: string | null;
    sequence: number;
    direct_item_count: number;
    descendant_item_count: number;
    items: LocationItem[];
    children: LocationNode[];
};
