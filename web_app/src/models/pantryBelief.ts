// Zero-Input Pantry belief (server-owned inference; R-003).
// The client only renders this — the band/confidence/reason are computed
// server-side from purchases + cooking + cadence + time decay.

export type BeliefBand = 'out' | 'low' | 'stocked';
export type ConfidenceBand = 'high' | 'medium' | 'low';

export interface PantryBelief {
    believed_band: BeliefBand;
    confidence_band: ConfidenceBand;
    reason: string;
    /** True when this is a genuine inference (extrapolated), false when it
     *  merely echoes a freshly-confirmed recorded level. */
    is_inferred: boolean;
    /** True when the inferred band differs from the user's recorded level —
     *  the chip nudges. */
    differs_from_recorded: boolean;
}

export interface PantryBeliefsResponse {
    /** False when the user has switched inference off (per-user pref). */
    enabled: boolean;
    /** Keyed by stock_item_id. */
    beliefs: Record<string, PantryBelief>;
}
