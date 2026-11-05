/**
 * A card page's layout: the user's order + hidden set (server-persisted, the
 * dashboard on `dashboard_layout` §2.1, Reports on `reports_layout`), which
 * cards are available under the feature gates, column widths, CSS order and
 * the reorder / toggle actions (finalisation 08-R18; FU-832 shares it with
 * Reports). Cards render with CSS `order` rather than moving markup: each
 * keeps its template position.
 */
import { computed, ref, type Ref } from 'vue';
import { cardGateOpen, type CardDef } from 'src/helpers/cardCatalogue';
import { CARD_COL_HALF, zoneColClasses } from 'src/helpers/dashboardGrid';
import {
    baseHiddenSet, defaultOrder, parseLayout, type CardLayout,
} from 'src/helpers/cardLayout';

export function useCardLayout<Id extends string>(options: {
    /** The surface's card table (`dashboardCards` / `reportCards`). */
    defs: readonly CardDef<Id>[];
    /** The stored layout JSON (or null for the defaults). */
    stored: () => string | null;
    /** Save the layout; fire-and-forget, the refs already show the change. */
    persist: (layout: CardLayout<Id>) => void;
    moneyEnabled: () => boolean;
    productsEnabled: () => boolean;
}) {
    const defs = options.defs;
    const knownIds = new Set<Id>(defs.map((c) => c.id));
    const cardOrder = ref(defaultOrder(defs)) as Ref<Id[]>;
    const hiddenCards = ref(baseHiddenSet(defs)) as Ref<Set<Id>>;

    /** Re-read the stored layout (on load, and when the user changes). The
     *  parse drops retired ids and inserts unseen cards at their registry
     *  position (`helpers/dashboardLayout`). */
    function applyStored() {
        const parsed = parseLayout(options.stored(), defs);
        cardOrder.value = parsed.order;
        hiddenCards.value = new Set(parsed.hidden);
    }
    applyStored();

    function persist() {
        options.persist({ order: cardOrder.value, hidden: [...hiddenCards.value] });
    }

    // A card is *available* unless its feature gate is off; gated-off cards
    // vanish from both the page and the Cards menu (§2.4 / ADR-005).
    const cardGate = new Map(defs.map((c) => [c.id, c.gate]));
    function cardAvailable(id: Id): boolean {
        return cardGateOpen(cardGate.get(id), options);
    }

    /** Registered, gated on and un-hidden. The template's `v-if` and the
     *  column maths both ask this one predicate, so the grid never pairs a
     *  card that isn't there (FU-631 #3; the next hide-when-empty card adds
     *  its condition here, not at its call site). */
    function cardRendered(id: Id): boolean {
        return knownIds.has(id) && cardAvailable(id) && !hiddenCards.value.has(id);
    }

    function toggleCard(id: Id) {
        const next = new Set(hiddenCards.value);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        hiddenCards.value = next;
        persist();
    }

    const visibleCardCount = computed(() => defs.filter((c) => cardRendered(c.id)).length);

    // Cards that are full-width by design rather than by parity declare it in
    // their table row instead of hard-coding `col-12` at their call site (the
    // source of the old dead regions).
    const fullWidthCards: ReadonlySet<Id> = new Set(defs.filter((c) => c.fullWidth).map((c) => c.id));

    // Column classes so no card is left half-width beside dead air (D-011 /
    // B4); the rendered cards are one run since the zones went, so an odd
    // count strands at most one card on the page (`helpers/dashboardGrid`).
    const cardColClasses = computed<Record<string, string>>(() =>
        zoneColClasses(cardOrder.value.filter(cardRendered), fullWidthCards),
    );
    function cardCol(id: Id): string {
        return cardColClasses.value[id] ?? CARD_COL_HALF;
    }

    /** CSS `order` per card: its index in the user's order. */
    function cardCssOrder(id: Id): number {
        const i = cardOrder.value.indexOf(id);
        return i === -1 ? defs.findIndex((c) => c.id === id) : i;
    }

    // Reorder over available cards only: with money off a money card is still
    // in the order but renders nowhere, and counting it would make one press
    // of Move-up look like it did nothing.
    function orderedAvailableCards(): Id[] {
        return cardOrder.value.filter(cardAvailable);
    }
    function canMove(id: Id, dir: 'up' | 'down'): boolean {
        const peers = orderedAvailableCards();
        const i = peers.indexOf(id);
        return dir === 'up' ? i > 0 : i >= 0 && i < peers.length - 1;
    }
    /** The tap alternative to drag (C13), always present. */
    function moveCard(id: Id, dir: 'up' | 'down') {
        const peers = orderedAvailableCards();
        const i = peers.indexOf(id);
        const j = dir === 'up' ? i - 1 : i + 1;
        if (i < 0 || j < 0 || j >= peers.length) return;
        const next = [...cardOrder.value];
        const oi = next.indexOf(id);
        const oj = next.indexOf(peers[j]!);
        [next[oi], next[oj]] = [next[oj]!, next[oi]!];
        cardOrder.value = next;
        persist();
    }
    /** Drop-on semantics for the drag handle: the dragged card takes the
     *  target's slot and the target shifts toward where it came from. */
    function dropCardOn(sourceId: Id, targetId: Id) {
        if (sourceId === targetId) return;
        const next = [...cardOrder.value];
        const fromIdx = next.indexOf(sourceId);
        const toIdx = next.indexOf(targetId);
        if (fromIdx < 0 || toIdx < 0) return;
        const [moved] = next.splice(fromIdx, 1);
        next.splice(toIdx, 0, moved!);
        cardOrder.value = next;
        persist();
    }

    /** The Cards menu rows, in display order, gated-off cards left out. */
    const menuCards = computed(() =>
        orderedAvailableCards().map((id) => defs.find((c) => c.id === id)!),
    );

    return {
        cardOrder, applyStored, cardRendered, isCardVisible: cardRendered, toggleCard,
        visibleCardCount, cardCol, cardCssOrder, canMove, moveCard, dropCardOn, menuCards,
    };
}
