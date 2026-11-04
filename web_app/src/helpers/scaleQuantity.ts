// DEC-4 quantity-scaling rule.
//
// Cook mode lets the user override how many people they're cooking for; every
// ingredient quantity rescales `cookingFor / recipe.servings`. The raw
// multiplier produces ugly numbers (1.333 cups, 1.5 eggs) so we round into
// the kitchen-friendly buckets the plan resolved:
//
// - Countable units (null = "2 eggs"-style bare counts, plus a small inclusion
//   list of unit names that mean "discrete objects") round to the nearest whole
//   number, floored at 1 (you can't cook with 0 eggs).
// - Mass / volume / other continuous units snap to ½, ¼/¾, ⅓/⅔ when the
//   decimal is close enough (within 0.04), else round to one decimal place
//   with the trailing zero trimmed.
//
// Output is a `string | number | null` ready to feed through `formatQuantity`
// — `null` when the input quantity is null (caller can render unit-only
// rows). The two helpers stay separate so the spacing convention
// (`formatQuantity`) doesn't get tangled with the rounding convention here.

// The countable-unit list is the server's (`units.py` `COUNTABLE_UNITS`,
// singular forms) via the generated table — the client used to carry a
// different list, so "2 rashers" scaled to "2.5" here while the server
// treated a rasher as a counted sub-item (finalisation 20-R4, R-003).
import { COUNTABLE_UNITS } from 'src/generated/units_table';
import { formatNumber } from 'src/composables/useMoney';

const FRACTION_GLYPHS: ReadonlyArray<readonly [number, string]> = [
    [0.25, '¼'],
    [1 / 3, '⅓'],
    [0.5, '½'],
    [2 / 3, '⅔'],
    [0.75, '¾'],
];

const FRACTION_TOLERANCE = 0.04;

export function isCountableUnit(unit: string | null | undefined): boolean {
    if (unit === null || unit === undefined) return true;
    const trimmed = unit.trim().toLowerCase();
    if (!trimmed) return true;
    // The generated list holds singular forms; recipes write plurals
    // ("3 cloves", "2 bunches").
    const singular = trimmed.replace(/(ch|sh|x|z)es$/, '$1').replace(/s$/, '');
    return COUNTABLE_UNITS.has(trimmed) || COUNTABLE_UNITS.has(singular);
}

function nearestFractionGlyph(decimal: number): string | null {
    for (const [value, glyph] of FRACTION_GLYPHS) {
        if (Math.abs(decimal - value) <= FRACTION_TOLERANCE) return glyph;
    }
    return null;
}

/** Pretty-print a continuous quantity. Snaps to the resolved fractions
 *  when the decimal is close enough; otherwise one decimal place with the
 *  trailing zero trimmed (3.0 → "3", 7.55 → "7.6"). */
function formatContinuous(value: number): string {
    if (!Number.isFinite(value) || value <= 0) return '0';
    const whole = Math.floor(value);
    const frac = value - whole;
    const glyph = nearestFractionGlyph(frac);
    if (glyph !== null) {
        return whole === 0 ? glyph : `${whole}${glyph}`;
    }
    if (Math.abs(frac) < FRACTION_TOLERANCE) {
        return String(whole);
    }
    const rounded = Math.round(value * 10) / 10;
    // The household's decimal mark (D-006, FU-969 (2)): "7,6" under de-DE.
    // The string is display-only: it goes straight to `formatQuantity`.
    return formatNumber(rounded, { digits: 1, grouping: false });
}

/** Scale a recipe quantity for a new headcount. Returns a value ready to
 *  feed straight into `formatQuantity(scaled, unit)`. Pass `recipeServings`
 *  null/undefined and the helper assumes 1 (a recipe with no declared
 *  servings can't be rescaled, but we still want the formatting to be
 *  consistent — the caller can hide the control when this happens). */
export function scaleQuantity(
    quantity: number | null | undefined,
    recipeServings: number | null | undefined,
    cookingFor: number,
    unit: string | null | undefined,
): number | string | null {
    if (quantity === null || quantity === undefined) return null;
    const base = (recipeServings && recipeServings > 0) ? recipeServings : 1;
    const target = (Number.isFinite(cookingFor) && cookingFor > 0) ? cookingFor : 1;
    const scaled = quantity * (target / base);

    if (isCountableUnit(unit)) {
        // Unscaled, the recipe's own "½ onion" stands as written (QA2-35);
        // only a scaled count rounds to whole items.
        if (target === base) return quantity;
        return Math.max(1, Math.round(scaled));
    }
    return formatContinuous(scaled);
}
