// Card layout persistence: parsing a stored layout JSON string (the
// dashboard's `dashboard_layout`, Reports' `reports_layout`) into the ordered /
// hidden card lists a page renders. Every function takes the surface's card
// table (FU-832), so the dashboard and Reports share one set of rules.
//
// Extracted from `DashboardPage.vue` (finalisation 08-R7) so the one rule here
// that is invisible in a browser has a spec: a card that shipped *after* the
// user last saved their layout is inserted at its table position, not
// appended. The page comment always promised that; the loop appended, so
// every user with a saved layout got Kitchen health **last** when it shipped —
// the opposite of the 2026-09-08 ordering decision.
//
// A stored layout naming a retired id (`attention`, `calendar`, `savings`, …)
// simply drops it — `dashboardCards.spec.ts` keeps those ids retired.

import type { CardDef } from 'src/helpers/cardCatalogue';

export type CardLayout<Id extends string = string> = { order: Id[]; hidden: Id[] };

export function defaultOrder<Id extends string>(defs: readonly CardDef<Id>[]): Id[] {
    return defs.map((c) => c.id);
}

export function baseHiddenSet<Id extends string>(defs: readonly CardDef<Id>[]): Set<Id> {
    return new Set(defs.filter((c) => c.defaultHidden).map((c) => c.id));
}

/** Insert every table card missing from `order` at its table position:
 *  directly after the nearest *preceding* table card that is present, or
 *  at the front when none is. Mutates and returns `order`. */
export function insertMissingAtRegistryPosition<Id extends string>(
    order: Id[], defs: readonly CardDef<Id>[],
): Id[] {
    defs.forEach((def, index) => {
        if (order.includes(def.id)) return;
        let insertAt = 0;
        for (let i = index - 1; i >= 0; i--) {
            const at = order.indexOf(defs[i]!.id);
            if (at !== -1) {
                insertAt = at + 1;
                break;
            }
        }
        order.splice(insertAt, 0, def.id);
    });
    return order;
}

export function parseLayout<Id extends string>(
    raw: string | null, defs: readonly CardDef<Id>[],
): CardLayout<Id> {
    const known = new Set<string>(defs.map((c) => c.id));
    const isKnown = (id: string): id is Id => known.has(id);
    if (!raw) return { order: defaultOrder(defs), hidden: [...baseHiddenSet(defs)] };
    try {
        // Untrusted JSON — treat the arrays as raw strings and narrow each
        // entry to a known id at runtime.
        const parsed = JSON.parse(raw) as { order?: string[]; hidden?: string[] };
        const order = insertMissingAtRegistryPosition((parsed.order ?? []).filter(isKnown), defs);
        const hidden = new Set<Id>((parsed.hidden ?? []).filter(isKnown));
        // A card the user has never seen inherits its default visibility, so
        // a new opt-in-by-default card starts hidden even for existing users.
        const seen = new Set<string>([...(parsed.order ?? []), ...(parsed.hidden ?? [])]);
        for (const def of defs) {
            if (def.defaultHidden && !seen.has(def.id)) hidden.add(def.id);
        }
        return { order, hidden: [...hidden] };
    } catch {
        return { order: defaultOrder(defs), hidden: [...baseHiddenSet(defs)] };
    }
}
