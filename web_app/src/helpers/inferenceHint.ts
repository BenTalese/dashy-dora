/**
 * FU-653 — what Dora's stock hunch says about a recipe or a planned meal, in
 * one place (finalisation 07-R5): the tooltip names the items, because "may be
 * short" without saying what is a nudge with nowhere to go.
 */
export type InferenceTone = 'warning' | 'positive';

export function inferenceTone(hint: string | null | undefined): InferenceTone {
    return hint === 'at_risk' ? 'warning' : 'positive';
}

export function inferenceTooltip(
    hint: string | null | undefined,
    names: readonly string[] | null | undefined,
    surface: 'recipe' | 'plan',
): string {
    const list = (names ?? []).join(', ');
    if (hint === 'at_risk') {
        return surface === 'plan'
            ? `Dora thinks you may have run out of ${list} since you planned this.`
            : `Everything's recorded as in stock, but Dora thinks you may have run out of ${list}.`;
    }
    return `Recorded as missing ${list}, but Dora thinks you're back in stock.`;
}
