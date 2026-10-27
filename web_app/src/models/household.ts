/** Household headcount as the server stores it: a whole number 1–99, or
 *  null for "not set". The bounds mirror `AppSetting.household_headcount`'s
 *  validation — this is the one place the TS mirror lives (finalisation
 *  14-R9; was copied in the wizard and the Cooking settings page). */
export const MAX_HOUSEHOLD_HEADCOUNT = 99;

export function normaliseHeadcount(value: number | null | undefined): number | null {
    if (value === null || value === undefined || !Number.isFinite(value) || value < 1) {
        return null;
    }
    return Math.min(MAX_HOUSEHOLD_HEADCOUNT, Math.floor(value));
}
