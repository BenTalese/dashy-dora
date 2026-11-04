// DEC-3 unit-spacing rule. A handful of metric/imperial units
// are conventionally written tight against the number ("250g", "2ml");
// everything else gets a space ("2 cloves", "1 tbsp"). Call sites across
// cook mode, recipes, and shopping lists route through here so the
// convention can never drift between surfaces.
//
// The inclusion list is the server's (`dora_api/domain/units.py`
// `NO_SPACE_UNITS`), emitted into `generated/units_table.ts` — one source,
// not a mirror kept in sync by hand (finalisation 20-R3, R-003).
import { NO_SPACE_UNITS } from 'src/generated/units_table';
import { formatNumber } from 'src/composables/useMoney';

/** Decimal places a quantity is ever shown to. Two is enough for the
 *  fractions a recipe actually uses (0.25, 0.5, 1.33) and short enough to read
 *  in a 300px rail. */
const MAX_DECIMALS = 2;

/**
 * Round a numeric quantity for display, without leaving trailing zeros.
 *
 * Owner report 2026-09-03: the meal planner's right rail read *"needs
 * 31.333333333333332 tbsp"*. Aggregated demand is a sum of scaled per-recipe
 * quantities, so a third of a cup three times over is a binary float — and
 * `String(31.333333333333332)` prints all seventeen digits. Rounding lives HERE
 * rather than at the call site because this function is already the single
 * authority for how a quantity is written (DEC-3), and the alternative is every
 * surface that shows demand remembering to round first: the auto builder's
 * preview had its own local `round()` and the rail had none, which is exactly
 * how the two diverged.
 */
function formatAmount(value: number): string {
    if (!Number.isFinite(value)) return '';
    // `toFixed` first: `Math.round(v * 100) / 100` still prints artefacts of
    // its own (0.145 -> 0.14500000000000002 territory). Then the household
    // locale's decimal mark through the one number formatter (D-006,
    // FU-969 (2)): "1,5 kg" under de-DE. Display-only: every caller renders
    // the string; quantity inputs bind the raw number, never this text.
    return formatNumber(Number(value.toFixed(MAX_DECIMALS)), { digits: MAX_DECIMALS, grouping: false });
}

export function formatQuantity(
    quantity: number | string | null | undefined,
    unit: string | null | undefined,
): string {
    const qty = (quantity === null || quantity === undefined || quantity === '')
        ? ''
        : (typeof quantity === 'number' ? formatAmount(quantity) : String(quantity));
    const trimmedUnit = (unit ?? '').trim();
    if (!qty && !trimmedUnit) return '';
    if (!trimmedUnit) return qty;
    if (!qty) return trimmedUnit;
    const noSpace = NO_SPACE_UNITS.has(trimmedUnit.toLowerCase());
    return noSpace ? `${qty}${trimmedUnit}` : `${qty} ${trimmedUnit}`;
}
