/**
 * Dora's stock belief speaks in three bands; levels are keyed by sequence
 * (R-003, one colour map in `stockLevelLogic`). This is the one translation
 * between the two (finalisation 05-R24). A band is said as its own word
 * ("low") everywhere; there is no separate wording map.
 */
import { LOW_STOCK_SEQUENCE, OUT_OF_STOCK_SEQUENCE, STOCKED_SEQUENCE } from 'src/helpers/stockStatus';

export type BeliefBand = 'out' | 'low' | 'stocked';

const SEQUENCE_BY_BAND: Record<BeliefBand, number> = {
    out: OUT_OF_STOCK_SEQUENCE,
    low: LOW_STOCK_SEQUENCE,
    stocked: STOCKED_SEQUENCE,
};

function isBand(value: string): value is BeliefBand {
    return value in SEQUENCE_BY_BAND;
}

/** The level sequence a band is coloured as, or null. */
export function sequenceForBand(band: string | null | undefined): number | null {
    return band && isBand(band) ? SEQUENCE_BY_BAND[band] : null;
}

/** The band a recorded level falls in, or null for a household's extra
 *  levels (anything off the three canonical sequences). */
export function bandForSequence(sequence: number | null | undefined): BeliefBand | null {
    if (sequence == null) return null;
    const match = (Object.keys(SEQUENCE_BY_BAND) as BeliefBand[]).find(
        (band) => SEQUENCE_BY_BAND[band] === sequence,
    );
    return match ?? null;
}
