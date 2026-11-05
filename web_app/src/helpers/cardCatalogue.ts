// The shape every card table shares (FU-832): the dashboard's
// (`dashboardCards.ts`) and Reports' (`reportCards.ts`). A flat data table per
// surface, keyed by card id: what the card is called, its icon, the feature
// gate it sits behind, and whether it starts hidden. Deliberately a table, not
// a plugin registry: each page keeps its own card bodies and just looks ids up
// (owner, FU-809). The gate facts live here, once, so neither page declares
// "this card needs money" in its template.

export type CardGate = 'money' | 'products';

export type CardDef<Id extends string = string> = {
    id: Id;
    label: string;
    icon: string;
    /** Opt-in-by-default cards (Anti-creep, §2.2) start hidden. */
    defaultHidden?: boolean;
    /** Feature gate: the card is unavailable (hidden from the page AND the
     *  Cards menu) unless its gate is on. `money` → `useMoneyEnabled` (any
     *  dollar surface, ADR-005); `products` → the products feature flag. */
    gate?: CardGate;
    /** Full-width by design (two lists side by side, a chart under them)
     *  rather than by grid parity. */
    fullWidth?: boolean;
};

export type CardGates = {
    moneyEnabled: () => boolean;
    productsEnabled: () => boolean;
};

export function cardGateOpen(gate: CardGate | undefined, gates: CardGates): boolean {
    if (gate === 'money') return gates.moneyEnabled();
    if (gate === 'products') return gates.productsEnabled();
    return true;
}
