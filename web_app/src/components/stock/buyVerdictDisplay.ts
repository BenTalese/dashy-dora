// Display helpers shared by `BuyVerdictCard` and `BuyVerdictBadge`.
//
// Both surfaces render the same verdict — the card expanded, the badge inside
// its popover — so the headline, per-reason icon and detail line, and the
// data-used footer have to agree (R-003): they live here, once.

import { formatMoney } from 'src/composables/useMoney';
import type {
    BuyVerdict,
    BuyVerdictDataUsed,
    BuyVerdictReason,
} from 'src/services/api/buyVerdictApiService';
import { ICONS } from 'src/style/icons';

export function axisIcon(axis: BuyVerdictReason['axis']): string {
    if (axis === 'price') return ICONS.price_check;
    if (axis === 'need') return ICONS.inventory_2;
    if (axis === 'plan') return ICONS.event;
    return ICONS.delete_outline;
}

/** The reason's sub-line, or '' when it has none.
 *
 *  Price-axis reasons arrive as two raw numbers rather than a prose `detail`,
 *  because the server does not format currency (D-006) — it used to emit a
 *  hardcoded `$12.34`, which showed a dollar sign to a household on EUR.
 *  Composing the line here runs both amounts through the install's
 *  currency + locale formatter. Every other axis just carries `detail`. */
export function reasonDetail(reason: BuyVerdictReason): string {
    const last = reason.amount_last;
    if (last !== null && last !== undefined) {
        return `${formatMoney(last)} last shop · usually ${formatMoney(reason.amount_usual)}`;
    }
    return reason.detail ?? '';
}

const BUY_HEADLINE_BY_STRENGTH: Record<number, string> = {
    3: 'Worth buying now',
    2: 'Probably worth buying',
    1: 'Might be worth buying',
};

/** One phrase per verdict on every surface. The card grades a buy by its
 *  strength; the badge, with less room, always reads the strongest form. */
export function headlineFor(verdict: BuyVerdict, options: { graded?: boolean } = {}): string {
    if (verdict.verdict === 'buy') {
        return options.graded
            ? (BUY_HEADLINE_BY_STRENGTH[verdict.strength] ?? 'Might be worth buying')
            : 'Worth buying now';
    }
    if (verdict.verdict === 'wait') return 'Might be worth waiting';
    if (verdict.verdict === 'skip') return 'Probably skip';
    // Name the signal it's about (2026-08-21 feedback).
    return 'No strong buy signal';
}

/** "Based on 4 price samples · 1 waste event (last 12 months)." The trips
 *  count stays off it (feedback 2026-08-17): it read as the denominator of
 *  the price samples, which it isn't. */
export function dataUsedLine(dataUsed: BuyVerdictDataUsed): string {
    const samples = `${dataUsed.price_samples} price sample${dataUsed.price_samples === 1 ? '' : 's'}`;
    const waste = dataUsed.waste_events_last_12mo;
    const wasteClause = waste > 0 ? ` · ${waste} waste event${waste === 1 ? '' : 's'}` : '';
    return `Based on ${samples}${wasteClause} (last 12 months).`;
}
