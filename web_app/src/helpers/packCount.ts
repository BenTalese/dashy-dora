/** The rule both pack-count fields state: how many countable things a pack
 *  holds (12 eggs in a 700 g carton). */
export const PACK_COUNT_RULE = 'a whole number, 1 or more';

/** Blank → null (one item or free weight); a whole number ≥ 1 → that number;
 *  anything else → undefined, which the caller reports as invalid. */
export function parsePackCount(raw: number | string | null | undefined): number | null | undefined {
    if (raw === null || raw === undefined || raw === '') return null;
    const n = Number(raw);
    return Number.isInteger(n) && n >= 1 ? n : undefined;
}
