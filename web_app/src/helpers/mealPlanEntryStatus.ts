import type { MealPlanEntry } from 'src/models/mealPlan';

/**
 * What a planned meal's card says about itself, in one place.
 *
 * **The problem this solves (owner assessment, 2026-09-12).** The card was
 * signalling three independent things — where the food comes from, whether you
 * can cook it, and whether it's been cooked — through two colours assigned
 * feature by feature as each landed. Amber meant "the pool is short, go cook
 * this", "you're missing ingredients, you *can't* cook this", and "Dora thinks
 * an ingredient ran out", which are three different instructions. Green meant
 * "cooked", "Dora thinks you're fine", and — on the trim of every ordinary meal
 * — nothing at all.
 *
 * The fix is one axis per channel:
 *
 * * **Supply** — can you make it? `chef_hat`, the app's glyph for the act of
 *   cooking. Green when you have everything, amber when you don't.
 * * **Readiness** — is it already made? `meals_prepared` (the fridge), already
 *   documented as "portions cooked and waiting to be eaten". Green when this
 *   meal has a ready serving behind it, amber when it still has to be cooked.
 * * **Trim** — does this card need anything from you at all? A roll-up, so it
 *   can never contradict the two glyphs above it.
 *
 * An axis that doesn't apply renders **nothing** rather than a greyed glyph
 * (owner call): a green chef hat on a leftovers day would be a claim about a
 * shop you never have to do, and a fridge in a fresh household would describe a
 * pool that doesn't exist there.
 *
 * Shared by `MealPlanEntryChip` (desktop) and `MealPlanRichCard` (phone) so the
 * two breakpoints cannot drift (R-001).
 */

/** `pending` is a leftovers day whose batch hasn't been cooked yet: nothing to
 *  do on this day, but no portion is waiting either (owner 2026-10-15). */
export type StatusTone = 'ok' | 'alert' | 'pending';

/** The ink for a status glyph: green fine, amber not, muted for waiting. */
export function statusToneClass(tone: StatusTone): string {
    switch (tone) {
        case 'ok': return 'text-positive';
        case 'alert': return 'text-warning';
        case 'pending': return 'dora-text-muted';
    }
}

/** Nothing-to-do (grey) · fine (green) · something's wrong (amber). */
export type TrimTone = 'idle' | 'ok' | 'alert';

export type MealCardStatus = {
    /** "Can I make this?" — null when the meal isn't cooked from ingredients. */
    supply: StatusTone | null;
    /** "Is it already made?" — null outside a batch household, and on a meal
     *  that deliberately stands outside the cooked portions (`cook_fresh`). */
    readiness: StatusTone | null;
    trim: TrimTone;
};

/** A leftovers day: linked to a cook that happens on an earlier day. */
function isLeftovers(entry: MealPlanEntry): boolean {
    return entry.cook_batch_id !== null && !entry.is_cook_day;
}

/**
 * Whether this meal is cooked from ingredients, which is what makes the supply
 * question meaningful. In a **fresh** household every meal is; in a batch
 * household it's the cook day of a batch, a meal explicitly marked cook-fresh,
 * or one the cooked servings can't cover. Anything else is eaten from portions
 * already made, and its ingredients were spent when they were made.
 */
function cooksFromIngredients(
    entry: MealPlanEntry, batchEnabled: boolean, needsCooking: boolean,
): boolean {
    if (!batchEnabled) return true;
    if (entry.cook_fresh) return true;
    if (entry.cook_batch_id !== null) return entry.is_cook_day;
    // Owner 2026-09-12: *"is the cookability showing correctly? I only see it
    // on multi-linked days."* It was under-showing, and this line is why. A
    // standalone meal in a batch household was assumed to come off the cooked
    // servings — true only while there ARE servings for it. When the allocation
    // says there aren't (`needs_cooking`), somebody is cooking this from
    // ingredients, so whether you have them is exactly the question.
    return needsCooking;
}

export function mealCardStatus(
    entry: MealPlanEntry,
    batchEnabled: boolean,
    needsCooking: boolean,
): MealCardStatus {
    // A cooked meal is finished business: no advice, no colour, and the card is
    // already dimmed by its own `--consumed` class.
    if (entry.consumed_at) {
        return { supply: null, readiness: null, trim: 'idle' };
    }

    const supply: StatusTone | null = cooksFromIngredients(entry, batchEnabled, needsCooking)
        ? (entry.missing_count > 0 ? 'alert' : 'ok')
        : null;
    // `cook_fresh` meals never ask the pool for anything, so the fridge would
    // be answering a question they don't pose.
    let readiness: StatusTone | null = null;
    if (batchEnabled && !entry.cook_fresh) {
        if (entry.cook_batch_pending) readiness = 'pending';
        else readiness = needsCooking ? 'alert' : 'ok';
    }

    if (supply === 'alert' || readiness === 'alert') {
        return { supply, readiness, trim: 'alert' };
    }
    // Grey, not green: a leftovers day is neither an all-clear nor a warning —
    // it is a day you have nothing to do. Painting it the same green as a cook
    // day is what put "this one's fine" beside "this one isn't" for the same
    // batch (owner, 2026-09-12).
    if (isLeftovers(entry)) {
        return { supply, readiness, trim: 'idle' };
    }
    return { supply, readiness, trim: 'ok' };
}

/** Tooltip for the supply glyph. Counts, because "how many" is what decides
 *  whether you cook tonight or shop first. */
export function supplyTooltip(entry: MealPlanEntry): string {
    // "Cookable now" is what the cookbook's filter and the recipe page call
    // this state, so the planner says it the same way (owner 2026-09-12).
    if (entry.missing_count <= 0) return 'Cookable now';
    const n = entry.missing_count;
    return `Missing ${n} ingredient${n === 1 ? '' : 's'}`;
}

/** Tooltip for the readiness glyph. Never says "pool" (owner, 2026-09-12) —
 *  it is an internal word for the cooked portions, and the user's question is
 *  simply whether there's a serving ready. */
export function readinessTooltip(entry: MealPlanEntry, needsCooking: boolean): string {
    if (entry.cook_batch_pending) return 'Leftovers from this batch, which still has to be cooked';
    if (!needsCooking) return 'A cooked serving is ready for this';
    // A batch is cooked as one, so its cook day is short the whole yield, not
    // just its own day's servings (owner 2026-10-15, the affogato report).
    const n = entry.cook_batch_id !== null
        ? (entry.cook_batch_total_servings ?? entry.servings)
        : entry.servings;
    const what = entry.cook_batch_id !== null ? ' for the batch' : '';
    return `Needs cooking: ${n} serving${n === 1 ? '' : 's'}${what}`;
}
