// The Reports page's card table (FU-832): the four questions the page answers
// since the 2026-09 review, in their default order. The user can hide and
// reorder them like the dashboard's cards ("Reports has too many widgets" is
// answered by the user deciding, not a cut list). Stored on
// `user.reports_layout`.

import type { CardDef } from 'src/helpers/cardCatalogue';
import { ICONS } from 'src/style/icons';

export type ReportCardId = 'spend' | 'waste' | 'kitchen_memory' | 'price_changes';

export const REPORT_CARD_DEFS: CardDef<ReportCardId>[] = [
    // Where did my money go: spend by store / category / year, one axis control.
    { id: 'spend', label: 'Spend', icon: ICONS.savings, gate: 'money', fullWidth: true },
    { id: 'waste', label: 'Waste', icon: ICONS.delete_outline },
    { id: 'kitchen_memory', label: 'Kitchen memory', icon: ICONS.menu_book },
    // Movement in the prices you logged yourself. Money-gated but not
    // products-gated: an install with an empty catalogue still has it.
    { id: 'price_changes', label: 'Price changes', icon: ICONS.trending_up, gate: 'money', fullWidth: true },
];
