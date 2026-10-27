/** A recipe's total time in minutes, or null when neither prep nor cook time
 *  is set (one rule for the card, the cookbook sort and the recipe page). */
export function totalMinutes(prep: number | null | undefined, cook: number | null | undefined): number | null {
    if (prep == null && cook == null) return null;
    return (prep ?? 0) + (cook ?? 0);
}
