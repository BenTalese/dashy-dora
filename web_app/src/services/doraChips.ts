// The Dora chat's suggestion chip row (finalisation 11-R30, split out of
// DoraChat.vue): the two pools, the intent-to-prompt map, and the pure rule
// that builds the row from the latest reply and the refresh cursor.
import { labelFor, type DoraIntentId } from 'src/services/doraIntents';

export type ChipDispatch =
    | { kind: 'intent'; id: DoraIntentId }
    | { kind: 'prompt'; text: string };
export type Chip = { key: string; label: string; dispatch: ChipDispatch };

export const CHIP_LIMIT = 4;

// Basic-mode pool: intent shortcuts the rule engine handles directly.
// Ordered by everyday usefulness — practical pantry asks first, then
// app-help, then personality/fun. Refresh button cycles through these.
export const BASIC_CHIP_POOL: DoraIntentId[] = [
    'whats_for_dinner',
    'attention',
    'pantry_summary',
    'low_stock',
    'expiring',
    'shopping_list_status',
    'weeks_meals',
    'find_recipe',
    'convert',
    'substitute',
    'page_help',
    'how_do_i',
    'show_around',
    'guides',
    'food_fact',
    'tell_me_something',
    'joke',
    'report_issue',
];

// AI-mode pool: full-sentence prompts that play to the model's strengths.
// Each is what would be sent to /ask if clicked — the chip label is the
// short version shown on the button. Wider pool than basic since AI can
// handle the open-ended natural-language ones too.
export const AI_CHIP_POOL: { label: string; prompt: string }[] = [
    // Pantry data
    { label: "What's for dinner?", prompt: "what's for dinner tonight" },
    { label: 'What needs attention?', prompt: 'what needs my attention right now' },
    { label: "What's expiring?", prompt: "what's about to go off this week" },
    { label: "What's low?", prompt: "what's running low in my pantry" },
    { label: 'Pantry health', prompt: "how's my pantry looking" },
    { label: "What's on my list?", prompt: "what's on my shopping list" },
    { label: "What's in the fridge?", prompt: "what's in the fridge" },
    // Recipe ideas
    { label: 'What can I cook now?', prompt: 'what can I make with what I have' },
    { label: 'Kid-friendly tonight', prompt: 'something kid-friendly tonight' },
    { label: 'Comfort food', prompt: 'comfort food ideas' },
    { label: 'Quick weeknight', prompt: 'something quick for a weeknight' },
    { label: 'Date night', prompt: 'date night recipe ideas' },
    { label: 'Fancy dessert', prompt: 'fancy dessert ideas' },
    // Shopping + deals
    { label: "What's in season?", prompt: "what's in season right now" },
    { label: 'Any deals?', prompt: "what's on special right now" },
    { label: 'Compare prices', prompt: "where's milk cheapest right now" },
    // Kitchen helpers
    { label: 'Substitute for…', prompt: 'what can I use instead of buttermilk' },
    { label: 'Convert units', prompt: 'how many ml in a cup of flour' },
    // Planning
    { label: "What's the plan?", prompt: "what's on the meal plan this week" },
    // App help
    { label: 'How do I…?', prompt: 'how do I add a stock item' },
    { label: 'What can I do here?', prompt: 'what can I do on this page' },
    { label: 'Show me around', prompt: 'give me a tour of the app' },
    // Personality
    { label: 'Tell me a joke', prompt: 'tell me a joke' },
    { label: 'Random food fact', prompt: 'tell me a random food fact' },
    { label: 'Tell me something', prompt: 'tell me something silly' },
    { label: 'Thanks D.O.R.A.', prompt: 'thanks dora' },
    { label: 'I found an issue', prompt: 'i found an issue' },
];

// Map intent IDs → AI-mode chip (label + prompt). Used to translate a
// reply's `suggestions: DoraIntentId[]` into AI chips when the bias
// runs in AI mode. If an intent has no entry it just doesn't bias the
// AI row — basic mode still uses it directly via labelFor().
export const INTENT_TO_AI_CHIP: Partial<Record<DoraIntentId, { label: string; prompt: string }>> = {
    attention: { label: 'What needs attention?', prompt: 'what needs my attention right now' },
    pantry_summary: { label: 'Pantry health', prompt: "how's my pantry looking" },
    low_stock: { label: "What's low?", prompt: "what's running low in my pantry" },
    expiring: { label: "What's expiring?", prompt: "what's about to go off this week" },
    shopping_list_status: { label: "What's on my list?", prompt: "what's on my shopping list" },
    whats_for_dinner: { label: "What's for dinner?", prompt: "what's for dinner tonight" },
    weeks_meals: { label: "What's the plan?", prompt: "what's on the meal plan this week" },
    joke: { label: 'Tell me a joke', prompt: 'tell me a joke' },
    food_fact: { label: 'Food fact', prompt: 'tell me a food fact' },
    tell_me_something: { label: 'Tell me something', prompt: 'tell me something silly' },
    guides: { label: 'Open the guides', prompt: 'show me the guides' },
    compliment: { label: 'Thanks Dora', prompt: 'thanks dora' },
    substitute: { label: 'Substitute for…', prompt: 'what can I use instead of buttermilk' },
    convert: { label: 'Convert units', prompt: 'how many ml in a cup of flour' },
    find_recipe: { label: 'Find a recipe', prompt: 'find me a recipe for pasta' },
    show_around: { label: 'Show me around', prompt: 'give me a tour of the app' },
    page_help: { label: 'What can I do here?', prompt: 'what can I do on this page' },
    how_do_i: { label: 'How do I…?', prompt: 'how do I add a stock item' },
    report_issue: { label: 'I found an issue', prompt: 'i found an issue' },
};


function rotate<T>(arr: readonly T[], offset: number): T[] {
    if (arr.length === 0) return [];
    const n = ((offset % arr.length) + arr.length) % arr.length;
    return [...arr.slice(n), ...arr.slice(0, n)];
}

/** The row: the latest reply's suggestions first (pass none to suspend that
 *  bias), then the mode's pool from the refresh cursor, capped and deduped. */
export function buildChips(options: {
    aiActive: boolean;
    suggestions: readonly DoraIntentId[];
    cursor: number;
}): Chip[] {
    const seen = new Set<string>();
    const out: Chip[] = [];
    const push = (chip: Chip) => {
        if (seen.has(chip.key) || out.length >= CHIP_LIMIT) return;
        seen.add(chip.key);
        out.push(chip);
    };
    if (options.aiActive) {
        for (const id of options.suggestions) {
            const ai = INTENT_TO_AI_CHIP[id];
            if (ai) push({ key: `prompt:${ai.prompt}`, label: ai.label, dispatch: { kind: 'prompt', text: ai.prompt } });
        }
        for (const entry of rotate(AI_CHIP_POOL, options.cursor)) {
            push({ key: `prompt:${entry.prompt}`, label: entry.label, dispatch: { kind: 'prompt', text: entry.prompt } });
        }
    } else {
        for (const id of options.suggestions) {
            push({ key: `intent:${id}`, label: labelFor(id), dispatch: { kind: 'intent', id } });
        }
        for (const id of rotate(BASIC_CHIP_POOL, options.cursor)) {
            push({ key: `intent:${id}`, label: labelFor(id), dispatch: { kind: 'intent', id } });
        }
    }
    return out;
}

export function chipPoolSize(aiActive: boolean): number {
    return aiActive ? AI_CHIP_POOL.length : BASIC_CHIP_POOL.length;
}
