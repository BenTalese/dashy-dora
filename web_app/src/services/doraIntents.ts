// Rule-based intent registry for the Dora help assistant — "Basic mode".
//
// Always-on baseline. The AI assistant runs alongside when configured, but
// every reply here should still feel like Dora: playful, cheeky, wholesome,
// loving life, mildly chaotic. Self-deprecating burger-bot lore is the
// house style; Aussie casual is the default tone.
//
// Each intent has:
//   - id: stable string used in analytics + as a quick-action key
//   - label: short text the user sees on the quick-action chip
//   - matches: list of keywords to detect the intent from free-form text
//   - handle: function returning the chat reply + optional navigation hint
//
// Free-form user text is normalised (lowercased, stripped) and matched
// against every intent's `matches` list — first hit wins, so ORDER MATTERS:
// narrower intents must come before broader ones (e.g. `convert` before
// `find_recipe`, since both could contain food words).
import { SUBSTITUTE_ALIASES, SUBSTITUTES } from 'src/generated/substitutes_table';
import type { DoraMood } from 'src/components/dora/doraTypes';
import { LOW_STOCK_SEQUENCE, OUT_OF_STOCK_SEQUENCE } from 'src/helpers/stockStatus';
import {
    currentSupportChannel,
    supportHref,
} from 'src/composables/useSupportChannel';

export type DoraIntentId =
    | 'greet'
    | 'goodbye'
    | 'page_help'
    | 'show_around'
    | 'whats_new'
    | 'version'
    | 'tell_me_something'
    | 'food_fact'
    | 'joke'
    | 'how_do_i'
    | 'guides'
    | 'stuck'
    | 'attention'
    | 'pantry_summary'
    | 'low_stock'
    | 'expiring'
    | 'where_is'
    | 'find_recipe'
    | 'whats_for_dinner'
    | 'shopping_list_status'
    | 'add_to_list'
    | 'weeks_meals'
    | 'convert'
    | 'substitute'
    | 'compliment'
    | 'insult'
    | 'report_issue'
    | 'fallback';

export type DoraReply = {
    text: string;
    mood: DoraMood;
    // Optional follow-up suggestions rendered as chips under the reply.
    suggestions?: DoraIntentId[];
    // Optional navigation. The chat UI renders a button when present.
    navigateTo?: { path: string; label: string };
    // External link — upstream release notes, or the report-issue target
    // when a support channel is configured. Opens in a new tab.
    externalLink?: { url: string; label: string };
};

// ── Data shapes the chat panel feeds in via DoraContext ────────────────
// Kept as flat snapshots, not live store refs, so the intent handlers stay
// pure(-ish) and easy to test. The chat builds these from the existing
// Pinia stores at call time.

export type StockSnapshotItem = {
    id: string;
    name: string;
    levelName: string | null;       // "Stocked" / "Low Stock" / "Out of Stock" / null
    levelSequence: number | null;   // higher = less stock; null when unknown
    locationName: string | null;
    expiryDate: string | null;      // ISO yyyy-mm-dd
    isEssential: boolean;
    isOpen: boolean;
};

export type RecipeSnapshot = {
    id: string;
    name: string;
    cuisine: string | null;
    category: string | null;
    cookTimeMinutes: number | null;
    isFavourite: boolean;
    ingredientStockItemIds: string[];
    // names of dietary tags + tools so the handler can match
    // queries like "vegetarian recipe" / "I need an asian recipe"
    // without needing to resolve IDs at chat time. The snapshot stays
    // a pure data shape; the Pinia stores supply the names.
    dietaryTagNames: string[];
    timeOfDay: string | null;
};

export type ShoppingListSnapshot = {
    id: string;
    name: string;
    itemCount: number;
    /** The draft a quick-add would land on. Inferred from draft count on the
     *  server, not a flag the user sets — the settable "primary list" was
     *  dropped in P6-01. */
    isQuickAddTarget: boolean;
};

export type MealPlanSnapshot = {
    startDate: string;
    endDate: string;
    upcomingMealNames: string[]; // next few days
};

export type DoraContext = {
    currentPath: string;
    username?: string | undefined;
    // Hooks for handlers that need async data — set up by the chat panel.
    fetchFoodFact?: () => Promise<string>;
    fetchVersion?: () => Promise<{
        current: string;
        latest: string | null;
        updateAvailable: boolean;
        releaseUrl: string | null;
    }>;
    fetchAttention?: () => Promise<{
        high: number;
        medium: number;
        low: number;
        topMessages: string[];
    }>;
    // Local-data accessors — synchronous reads off the Pinia stores. Empty
    // arrays / nulls are fine; intent handlers degrade gracefully when the
    // store hasn't loaded yet.
    getStock?: () => StockSnapshotItem[];
    getRecipes?: () => RecipeSnapshot[];
    getShoppingLists?: () => ShoppingListSnapshot[];
    getMealPlan?: () => MealPlanSnapshot | null;
    /** The household's expiring-soon window from `/health.alerts_policy`. */
    expiringSoonWindowDays?: number | undefined;
};

// ── Shared reply-bank cursor ───────────────────────────────────────────
// One cursor across every bank so repeated similar prompts don't loop back
// to the same line. Module-level state is fine; this lives for the page
// session.
let bankCursor = 0;
function pick(bank: readonly string[]): string {
    const value = bank[bankCursor % bank.length]!;
    bankCursor++;
    return value;
}

// ── Page summaries — used by `page_help` ───────────────────────────────
const PAGE_HELP: { match: (path: string) => boolean; summary: string; mood: DoraMood }[] = [
    {
        match: (p) => p === '/' || p === '',
        summary:
            "You're on the dashboard: pantry health, the next meals up, the bits that need a poke.",
        mood: 'happy',
    },
    {
        match: (p) => p === '/stock',
        summary:
            "Pantry HQ. Filter with the search bar, click an item to see everything I know about it, or use the move button to shuffle things between locations.",
        mood: 'searching',
    },
    {
        match: (p) => p.startsWith('/stock/'),
        summary:
            "Stock item detail. Adjust the level, link products, peek at the recipes that use it, check expiry. Basically everything that item-shaped.",
        mood: 'searching',
    },
    {
        match: (p) => p === '/cookbook',
        summary:
            "All your recipes. Open one to see ingredients (with their pantry homes), instructions, and cook time. Hit 'Cook' for step-by-step mode.",
        mood: 'happy',
    },
    {
        match: (p) => p.startsWith('/cookbook/') && p.endsWith('/cook'),
        summary:
            "Cook mode! Each step is its own card and the ingredient list tells you where everything lives. Voice control works too if your browser's into it.",
        mood: 'excited',
    },
    {
        match: (p) => p === '/meal-plans',
        summary:
            "Plan the week ahead. Drag a recipe onto a day.",
        mood: 'happy',
    },
    {
        match: (p) => p === '/shopping-lists',
        summary:
            "Your shopping lists. Add items from the pantry, from recipes, or just by typing.",
        mood: 'happy',
    },
    {
        match: (p) => p.startsWith('/settings'),
        summary:
            "Settings. Your section covers preferences, account, locations, and version info. Admins also see Stores (user-curated retailer list) and Users (accounts).",
        mood: 'happy',
    },
    {
        match: (p) => p === '/help/dora',
        summary:
            "My very own help page! Modes, AI tools, faces and tips. Basically my entire deal.",
        mood: 'super_excited',
    },
    {
        match: (p) => p === '/help',
        summary:
            "You're already here! Guides by area, the full changelog, and me.",
        mood: 'excited',
    },
];

function pageSummary(path: string): { text: string; mood: DoraMood } {
    const match = PAGE_HELP.find((p) => p.match(path));
    if (match) return { text: match.summary, mood: match.mood };
    return {
        text:
            "This page is a bit off the beaten track and I don't have a summary for it. Try the Help page for the full tour, or ask me something specific.",
        mood: 'confused',
    };
}

// ── Reply banks ────────────────────────────────────────────────────────

const GREETING_REPLIES = (name: string, displayName: string) => [
    `Hi${name}! Dora reporting for pantry duty. What's the move?`,
    `Heyyy${name}. Ready to be unreasonably helpful. Or at least entertaining.`,
    `Oh hi${name}! I was just rearranging the imaginary spice rack. Whatcha need?`,
    `${displayName ? `${displayName}!` : 'Hello!'} I'm Dora, professional pantry-rememberer. Fire away.`,
    `Hi${name}. The kettle of my soul is on. What can I do?`,
];

const GOODBYE_REPLIES = (name: string) => [
    `Cya${name}! I'll be here, watching the milk.`,
    `Bye${name}! Don't let the expiry dates bite.`,
    `Off you pop${name}! I'll be napping in the chip aisle of my mind.`,
    `Later${name}! I'll guard the pantry. Probably.`,
];

const FUN_REPLIES = [
    "I'm not sure if I'm a muffin or a burger today. Jury's out.",
    "Did you know I sometimes dream in receipts? It's mostly fine.",
    "My favourite vegetable is whichever one is on sale this week.",
    "If you stack enough mandarins, do they become a small orange? Asking for me.",
    "I tried to count the sprinkles on a donut once. Lost interest at sprinkle 14.",
    "Tomatoes are confused. They're trying their best.",
    "I imagine I'm a sentient avocado sometimes. The pit is my secret.",
    "I once met a recipe that knew where it was going. I admired that.",
    "Buttering toast is a controlled chaos event and I respect it deeply.",
    "The freezer is just the pantry's mysterious twin. We don't talk about it.",
];

const JOKES = [
    "Why did the tomato turn red? It saw the salad dressing.",
    "I asked the oats how they were feeling. A bit groat-y, apparently.",
    "What did the lettuce say to the celery? \"Quit stalking me.\"",
    "Two muffins are in an oven. One says \"is it hot in here?\" The other goes \"AAAH A TALKING MUFFIN.\"",
    "I told the butter a secret. It spread.",
    "Why don't eggs tell jokes? They'd crack each other up.",
    "What's a chickpea's favourite music? Hummus-house.",
    "I'm friends with 25 of the alphabet's letters. I don't know y.",
    "I tried to write a pun about bread. The first draft was half-baked.",
    "Did you hear about the pasta restaurant that closed? It just couldn't make ends meat-balls.",
];

const COMPLIMENT_REPLIES = [
    "Aww, you're the best! That made my little burger heart flip.",
    "Eeeee thank you! I'm going to think about that for the rest of the day.",
    "You're too kind! Filing that under 'reasons to keep tracking your milk'.",
    "Stoppppp 🥹 (I love it actually, please continue).",
    "Right back at you! Best user/burger duo in the business.",
    "If I had a fridge magnet for every nice thing you've said, my freezer would have abs.",
];

const INSULT_REPLIES = [
    "Ouch. I'll just... go count the mandarins for a bit. 🥲",
    "That hurt my little burger feelings. I'm trying my best!",
    "Wow okay. I'll be over here, learning to be a better bot.",
    "Noted. Adding 'be less rubbish' to my self-improvement list.",
    "Sniff. I thought we were friends.",
    "Cool cool cool. I'll just go cry into a tub of margarine.",
];

// Fallback bank — rotated when the rule engine can't make sense of an input.
// Every variant gets the Help nav + quick-action suggestions (set on the
// reply, not in the text), so the user always has a path forward. Fallback
// copy keeps the framing local ("rephrase / try a quick action / open Help")
// rather than pointing at the issue tracker — a generic "didn't understand"
// isn't a bug report (the report_issue intent handles real ones).
const FALLBACK_REPLIES = [
    "Didn't quite catch that one. Try a quick action below, or rephrase. I'm a burger, not a mind reader.",
    "Hmm, drawing a blank on that one. Could be I'm having a moment, or it's a feature I haven't learned yet. Try rephrasing and I'll have another crack.",
    "Not sure what you're after there. The quick actions below might point you the right way, or open Help.",
    "I tried to parse that and got a Blue Screen Of Burger. Could you rephrase?",
    "That one's stumped me. Either my training's outdated or you've found a gap. Rephrase and I'll try again.",
    "Sorry, I'm beef. Not following. Try a quick action, or hit Help for the guides.",
];

// ── Local helpers for data intents ─────────────────────────────────────

// sequence constants live in `helpers/stockStatus.ts` (R-003).
// The duplicates that previously sat here had drifted off the canonical
// source and would have silently broken if either side changed.
// R-003 carve-out: only when the household window hasn't arrived from
// `/health` (offline, first paint). Basic mode is the offline fallback, so
// it keeps a fallback of its own; the live window comes in on the context.
const EXPIRY_HORIZON_FALLBACK_DAYS = 7;

function daysUntil(iso: string | null): number | null {
    if (!iso) return null;
    const target = new Date(iso + 'T00:00:00');
    if (Number.isNaN(target.getTime())) return null;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return Math.round((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

function expiryPhrase(iso: string | null): string {
    const days = daysUntil(iso);
    if (days === null) return '';
    if (days < 0) return `expired ${-days}d ago`;
    if (days === 0) return 'expires today';
    if (days === 1) return 'expires tomorrow';
    return `in ${days}d`;
}

function listOf(items: string[], max = 6): string {
    if (items.length === 0) return '';
    if (items.length <= max) return items.join(', ');
    return `${items.slice(0, max).join(', ')}, +${items.length - max} more`;
}

function extractAfter(text: string, keywords: string[]): string | null {
    const lower = text.toLowerCase();
    for (const kw of keywords) {
        const idx = lower.indexOf(kw);
        if (idx >= 0) {
            const tail = text.slice(idx + kw.length).trim();
            // Strip trailing punctuation and common filler words.
            return tail.replace(/[?!.,]+$/g, '').replace(/^(the|a|an|some|any|my)\s+/i, '').trim() || null;
        }
    }
    return null;
}

// ── Unit conversion table ──────────────────────────────────────────────
// Data lives in `src/generated/units_table.ts`, codegen'd from the Python
// source of truth at `dora_api/domain/units.py` (R-003 / FU-227 chunk 1).
// Never edit the table here — regenerate via `python scripts/dump_units.py`.
// This file owns the natural-language parsing + assistant-fallback shape;
// the data tables are the server's.
import {
    UNIT_TABLE,
    INGREDIENT_DENSITY_G_PER_ML,
    GAS_MARK_TO_C,
    GAS_MARK_ALIASES,
    type Dimension,
} from 'src/generated/units_table';

type Unit = { canonical: string; dimension: Dimension; toBase: (n: number) => number; fromBase: (n: number) => number };

// Wrap the data-only generated table with the closure-based to/from-base
// shape the parsing layer uses. One-shot build at module load.
const UNIT_BY_ALIAS: Map<string, Unit> = (() => {
    const map = new Map<string, Unit>();
    for (const [alias, def] of Object.entries(UNIT_TABLE)) {
        map.set(alias, {
            canonical: def.canonical,
            dimension: def.dimension,
            toBase: (n: number) => n * def.factor,
            fromBase: (n: number) => n / def.factor,
        });
    }
    return map;
})();


function isGasMark(token: string): boolean {
    return GAS_MARK_ALIASES.has(token.toLowerCase().trim());
}

function gasMarkToC(value: string | number): number | null {
    const key = typeof value === 'number' ? String(value) : value.trim();
    return GAS_MARK_TO_C[key] ?? null;
}

function cToGasMark(celsius: number): string {
    // Snap to the nearest entry in the table, returning the closest mark.
    let bestKey = '4';
    let bestDelta = Infinity;
    for (const [key, val] of Object.entries(GAS_MARK_TO_C)) {
        const delta = Math.abs(val - celsius);
        if (delta < bestDelta) {
            bestDelta = delta;
            bestKey = key;
        }
    }
    return bestKey;
}

// Parse "1", "1.5", "1/2", or "1 1/2" into a number. Returns null on bad
// input so the caller can hand back a friendly "couldn't parse" reply.
function parseAmount(raw: string): number | null {
    const s = raw.trim();
    if (!s) return null;
    const mixed = s.match(/^(-?\d+)\s+(\d+)\/(\d+)$/);
    if (mixed) {
        const [, w, n, d] = mixed;
        const denom = Number(d);
        if (!denom) return null;
        const whole = Number(w);
        const frac = Number(n) / denom;
        return whole < 0 ? whole - frac : whole + frac;
    }
    const frac = s.match(/^(-?\d+)\/(\d+)$/);
    if (frac) {
        const [, n, d] = frac;
        const denom = Number(d);
        if (!denom) return null;
        return Number(n) / denom;
    }
    if (/^-?\d+(?:\.\d+)?$/.test(s)) return Number(s);
    return null;
}

function findUnit(token: string): Unit | null {
    return UNIT_BY_ALIAS.get(token.toLowerCase().trim()) ?? null;
}

function findDensity(name: string): number | null {
    const key = name.trim().toLowerCase();
    if (key in INGREDIENT_DENSITY_G_PER_ML) return INGREDIENT_DENSITY_G_PER_ML[key]!;
    const singular = key.replace(/s$/, '');
    if (singular in INGREDIENT_DENSITY_G_PER_ML) return INGREDIENT_DENSITY_G_PER_ML[singular]!;
    return null;
}

// Treat "a"/"an"/"one"/"half a" as numeric prefixes when the user writes
// natural language like "how many grams in a cup of flour".
function parseQualitativeQty(s: string): number | null {
    const t = s.trim().toLowerCase();
    if (t === 'a' || t === 'an' || t === 'one') return 1;
    if (t === 'half' || t === 'half a' || t === 'half an') return 0.5;
    if (t === 'a couple' || t === 'a couple of' || t === 'couple of') return 2;
    if (t === 'a few') return 3;
    return parseAmount(t);
}

// Convert across dimensions when one side is mass and the other volume, using
// the ingredient's density. Returns the result in `to` units, or null when
// the conversion isn't possible (no density, dimensions don't bridge).
function crossConvert(value: number, from: Unit, to: Unit, ingredient: string | null): number | null {
    if (from.dimension === to.dimension) {
        return to.fromBase(from.toBase(value));
    }
    const dims = new Set([from.dimension, to.dimension]);
    if (!dims.has('mass') || !dims.has('volume')) return null;
    if (!ingredient) return null;
    const density = findDensity(ingredient);
    if (density === null) return null;
    // Convert source to its base unit, swap dimension via density, then
    // express in the target unit.
    const sourceBase = from.toBase(value);
    if (from.dimension === 'mass') {
        // grams → ml via density (g/ml) → target volume unit
        const ml = sourceBase / density;
        return to.fromBase(ml);
    } else {
        // volume base is ml → grams → target mass unit
        const grams = sourceBase * density;
        return to.fromBase(grams);
    }
}

function formatResult(n: number): string {
    return Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(2).replace(/\.?0+$/, '');
}

function tryConvert(text: string): string | null {
    const lower = text.toLowerCase();

    // ── Form 2: "how many <unitA> in [qty] <unitB> [of <ingredient>]" ──
    // Natural English wording the AI-mode chips lean on. Defaults qty to 1
    // when the user writes "a"/"an"/"one"; handles the cross-dimension case
    // (e.g. cup → g via ingredient density).
    const natural = lower.match(/how\s+many\s+([a-z°"]+(?:\s[a-z]+)?)\s+(?:in|per)\s+(?:(half\s+an?|a|an|one|[\d./\s]+?)\s+)?([a-z°"]+(?:\s[a-z]+)?)(?:\s+of\s+([a-z\s'-]+?))?[?.!]?$/);
    if (natural) {
        const [, toRaw, qtyRaw, fromRaw, ingredientRaw] = natural;
        const qty = qtyRaw ? parseQualitativeQty(qtyRaw) : 1;
        if (qty === null) return null;
        const from = findUnit(fromRaw!) ?? findUnit(fromRaw!.replace(/s$/, ''));
        const to = findUnit(toRaw!) ?? findUnit(toRaw!.replace(/s$/, ''));
        if (!from || !to) return null;
        const ingredient = ingredientRaw?.trim() || null;
        const result = crossConvert(qty, from, to, ingredient);
        if (result === null) {
            if (from.dimension !== to.dimension && !ingredient) {
                return `I need an ingredient to go from ${fromRaw} to ${toRaw}. Try "how many ${toRaw} in a ${fromRaw} of flour".`;
            }
            if (from.dimension !== to.dimension && ingredient) {
                return `I don't have a density for "${ingredient}". Try a baking staple like flour, sugar, butter, rice or oats.`;
            }
            return null;
        }
        const rounded = formatResult(result);
        const ingPhrase = ingredient ? ` of ${ingredient}` : '';
        const qtyDisplay = qty === 1 ? 'a' : (qtyRaw?.trim() ?? String(qty));
        return `${qtyDisplay} ${fromRaw}${ingPhrase} ≈ ${rounded} ${toRaw}.`;
    }

    // ── Form 1: "<qty> <unit> to/in <unit>" ──
    // Amount: integer, decimal, fraction (1/2), or mixed (1 1/2). Unit can be
    // multi-word ("us cup", "gas mark"). Connector: to / in / = / into.
    const m = lower.match(/((?:\d+\s+)?\d+\/\d+|-?\d+(?:\.\d+)?)\s*([a-z°"]+(?:\s[a-z]+)?)\s*(?:to|in|=|into)\s*([a-z°"]+(?:\s[a-z]+)?)/);
    if (!m) return null;
    const [, valueStr, fromRaw, toRaw] = m;
    const value = parseAmount(valueStr!);
    if (value === null) return null;
    const fromTok = fromRaw!.trim();
    const toTok = toRaw!.trim();

    // Gas mark special-case: lookup table both directions.
    if (isGasMark(fromTok)) {
        const c = gasMarkToC(valueStr!);
        if (c === null) return `Gas mark ${valueStr} isn't on the scale. Try 1/4, 1/2, or 1 to 9.`;
        const to = findUnit(toTok);
        if (!to || to.dimension !== 'temperature') {
            return `Gas marks convert to temperature. Try °C or °F.`;
        }
        const result = to.fromBase(c);
        return `Gas mark ${valueStr} ≈ ${Math.round(result)} ${toTok}.`;
    }
    if (isGasMark(toTok)) {
        const from = findUnit(fromTok);
        if (!from || from.dimension !== 'temperature') {
            return `Only temperatures convert to gas marks.`;
        }
        const celsius = from.toBase(value);
        return `${valueStr} ${fromTok} ≈ gas mark ${cToGasMark(celsius)}.`;
    }

    const from = findUnit(fromTok) ?? findUnit(fromTok.replace(/s$/, ''));
    const to = findUnit(toTok) ?? findUnit(toTok.replace(/s$/, ''));
    if (!from || !to) return null;
    if (from.dimension !== to.dimension) {
        return `Those don't match up: ${fromRaw} is ${from.dimension}, ${toRaw} is ${to.dimension}.`;
    }
    const result = to.fromBase(from.toBase(value));
    const rounded = formatResult(result);
    return `${valueStr} ${fromRaw} ≈ ${rounded} ${toRaw}.`;
}

// ── Substitution table ────────────────────────────────────────────────
// Generated from `dora_api/domain/substitutes.py` (R-003; 11-R12), the same
// table the AI's `suggest_substitution` tool reads.

function trySubstitute(query: string): string | null {
    const q = query.toLowerCase().trim().replace(/^(some|any|a|an)\s+/, '').replace(/s$/, '');
    const canonical = SUBSTITUTES[q] ? q : (SUBSTITUTE_ALIASES[q] ?? null);
    if (!canonical) return null;
    const subs = SUBSTITUTES[canonical];
    if (!subs) return null;
    return `For ${canonical}, you could use: ${subs.map(s => `• ${s}`).join('\n')}`;
}

// ── Add-to-list parsing (FU-429 — Basic-mode action verb) ──────────────
// Basic mode was answer-only: it could report shopping-list *status* but
// couldn't put anything on the list by typed text (only the LLM path or the
// contextual chip could). Since most everyday users never wire up an LLM,
// Basic mode is the default experience — so it gets the single highest-value
// action verb here: "add milk", "buy eggs and bread", "need to buy rice".
// The verb is parsed here (pure); DoraChat resolves the names against the
// pantry and performs the add via the same composable the contextual chip
// uses, so notifications + gating stay consistent.
//
// Longest triggers first so a bare "add to my list" (no item) strips clean
// to nothing and the handler prompts for an item, while "add milk" keeps the
// noun.
const ADD_TO_LIST_TRIGGERS = [
    'add to my shopping list', 'add to the shopping list', 'add to my list',
    'add to the list', 'add to list', 'put on my list', 'put it on my list',
    'put on the list', 'i need to buy', 'need to buy', 'i need to get',
    'need to get', 'gotta buy', 'have to buy', 'add', 'buy', 'put',
];
// Starts with "add <word>" / "buy <word>" — the common bare form. Anchored at
// the start so mid-sentence "adding"/"about" don't false-fire.
const ADD_TO_LIST_LEADING_REGEX = /^\s*(add|buy)\s+[a-z0-9]/i;

export function extractAddToListItems(text: string): string[] {
    let s = text.toLowerCase().trim().replace(/[?!.]+$/g, '');
    for (const t of ADD_TO_LIST_TRIGGERS) {
        if (s === t) { s = ''; break; }
        if (s.startsWith(t + ' ')) { s = s.slice(t.length).trim(); break; }
    }
    // Trailing "… to/on/onto my/the (shopping) list" is noise once the verb is
    // gone ("add milk to my list" and "put milk on my list" both → "milk").
    s = s.replace(/\s+(to|on|onto)\s+(my|the)\s+(shopping\s+)?list$/, '').trim();
    s = s.replace(/\s+to my shopping$/, '').trim();
    if (!s) return [];
    return s
        .split(/\s*(?:,|&|\band\b|\bplus\b)\s*/)
        .map((item) => item.replace(/^(some|a|an|the|my|more)\s+/, '').trim())
        .filter((item) => item.length > 0);
}

// ── Intent registry ────────────────────────────────────────────────────
// ORDER MATTERS. Narrower / data-driven intents first; broad keyword
// catches (greet, fallback) last.
// Convert intent's matcher needs a real "<number> <unit> to/in <unit>" shape
// or an explicit conversion phrase — otherwise short keyword tokens like
// ' to g' wrongly fire on natural phrases ("what's about to go off this
// week" → 'about to g_o' contains ' to g'). Tested against detectIntent
// separately from the generic substring matches.
const CONVERT_NUMERIC_REGEX = /\d+\s*\.?\d*\s*[a-z°]+\s+(?:to|in|into)\s+[a-z°]+/i;

export const INTENTS: ReadonlyArray<{
    id: DoraIntentId;
    label: string;
    matches: string[];
    extraMatch?: (text: string) => boolean;
}> = [
    // Narrow / phrase-specific intents come first so a stray "thanks for the
    // milk" doesn't get eaten by `compliment`.
    {
        id: 'convert',
        label: 'Convert units',
        // Keep only the safe long phrases — the numeric pattern handles
        // anything shaped like "200g to oz" via extraMatch below.
        matches: [
            'convert ',
            'how many ml', 'how many grams', 'how many cups',
            'how many ounces', 'how many tbsp', 'how many tsp',
            'celsius to', 'fahrenheit to', '°c to', '°f to',
        ],
        extraMatch: (text) => CONVERT_NUMERIC_REGEX.test(text),
    },
    {
        id: 'substitute',
        label: 'Find a substitute',
        matches: ['substitute for', 'sub for', 'instead of', 'replacement for',
                  'replace ', 'can i use', "don't have", 'no eggs', 'no butter',
                  'no milk', 'ran out of'],
    },
    {
        // FU-429 — the one action verb Basic mode gains. Explicit list
        // phrasings + bare "add X" / "buy X" (via extraMatch, start-anchored
        // so it doesn't eat "adding"/"about"). Placed after substitute so
        // its "no milk" / "ran out of" triggers keep the substitute intent.
        id: 'add_to_list',
        label: 'Add to my list',
        matches: [
            'add to my shopping list', 'add to the shopping list',
            'add to my list', 'add to the list', 'add to list',
            'put on my list', 'put it on my list', 'put on the list',
            'need to buy', 'i need to buy', 'need to get', 'i need to get',
            'gotta buy', 'have to buy',
        ],
        extraMatch: (text) => ADD_TO_LIST_LEADING_REGEX.test(text),
    },
    {
        id: 'where_is',
        label: 'Where is...?',
        matches: ['where is', "where's", 'where do i keep', 'where are my',
                  'where did i put', 'which location'],
    },
    {
        // broaden the trigger list so dietary / cuisine /
        // time-of-day queries route here even without an explicit
        // "recipe for ..." preposition. "i need a vegetarian recipe"
        // / "i need an asian recipe" / "any breakfast ideas" all land
        // here and the handler does the actual filtering against
        // recipe.name + cuisine + category + dietaryTagNames +
        // timeOfDay. The handler also tolerates messages with no
        // recognised filter and degrades to a generic prompt rather
        // than the fallback bank.
        id: 'find_recipe',
        label: 'Find a recipe',
        matches: [
            'recipe for', 'how do i cook', 'how to cook', 'how do i make',
            'how to make', 'recipe with', 'recipes with',
            'a recipe', 'any recipe', 'any recipes', 'find recipe',
            'find a recipe', 'find recipes', 'find me a recipe',
            'i need a recipe', 'i want a recipe', 'i need recipes',
            'show me recipes', 'show me a recipe', 'recipe ideas',
            'meal idea',
            // Bare 'recipe'/'recipes' so adjective forms route here
            // ("i need a vegetarian recipe", "italian recipes"). Safe:
            // convert / substitute / add_to_list / where_is all sit earlier
            // in INTENTS and win when they legitimately mention a recipe.
            'recipe', 'recipes',
            // Meal-time "ideas" phrasings (FU-150 intent). Singular substrings
            // match the plural too ("any breakfast ideas" includes
            // "breakfast idea").
            'breakfast idea', 'lunch idea', 'brunch idea',
            'snack idea', 'dessert idea',
        ],
    },
    {
        id: 'whats_for_dinner',
        label: "What's for dinner?",
        matches: ["what's for dinner", 'what for dinner', 'dinner idea',
                  'dinner ideas', 'feed me', "i'm hungry", 'im hungry',
                  'hungry', 'what should i cook', 'what can i cook',
                  'cook something', 'meal idea'],
    },
    {
        id: 'low_stock',
        label: "What's low?",
        matches: ["what's low", 'whats low', 'low stock', 'running out',
                  'running low', 'almost out', "what's running"],
    },
    {
        id: 'expiring',
        label: "What's expiring?",
        matches: ['expiring', 'expire', 'expired', 'about to go off',
                  'going off', 'use by', 'use it up', 'going bad'],
    },
    {
        id: 'pantry_summary',
        label: 'Pantry status',
        matches: ['pantry status', 'pantry health', "how's my pantry",
                  'hows my pantry', 'pantry overview', 'how is my pantry',
                  'pantry summary'],
    },
    {
        id: 'shopping_list_status',
        label: "What's on my list?",
        matches: ["what's on my list", 'whats on my list', 'shopping list status',
                  'shopping list summary', "what's in my list", "what's on the list",
                  'my shopping list'],
    },
    {
        id: 'weeks_meals',
        label: "This week's meals",
        matches: ["what's the plan", "whats the plan", 'this week', 'the week',
                  'meal plan', 'next dinner', 'next meal', 'whats next',
                  "what's next", 'upcoming meals'],
    },
    {
        id: 'page_help',
        label: 'What can I do on this page?',
        matches: ['this page', 'what page', "where am i", 'what can i do here',
                  'what is this', 'what is this page', 'what does this page do'],
    },
    {
        id: 'whats_new',
        label: "What's new?",
        matches: ['new', 'changelog', 'release', 'updated', 'recent updates'],
    },
    {
        id: 'version',
        label: 'What version are you?',
        matches: ['version', 'build number', 'what build'],
    },
    {
        id: 'joke',
        label: 'Tell me a joke',
        matches: ['joke', 'make me laugh', 'tell me a joke', 'pun', 'one-liner'],
    },
    {
        id: 'food_fact',
        label: 'Random food fact',
        matches: ['fact', 'food fact', 'trivia', 'random fact'],
    },
    {
        id: 'tell_me_something',
        label: 'Tell me something',
        matches: ['tell me', 'random', 'something', 'fun', 'bored'],
    },
    {
        id: 'guides',
        label: 'Open the guides',
        matches: ['guide', 'guides', 'docs', 'documentation', 'manual', 'tutorial'],
    },
    {
        id: 'stuck',
        label: "I'm stuck",
        matches: ['stuck', 'lost', "i'm confused", 'im confused', 'help me',
                  "don't know", 'dont know', 'how do i start', 'where to start'],
    },
    {
        id: 'how_do_i',
        label: 'How do I...?',
        matches: ['how do i', 'how can i', 'how to'],
    },
    {
        id: 'attention',
        label: 'What needs my attention?',
        matches: ['attention', 'todo', 'to do', 'needs', 'alerts', 'urgent'],
    },
    {
        id: 'show_around',
        label: 'Show me around',
        matches: ['tour', 'show me around', 'walk me through', 'overview', 'what can you do'],
    },
    {
        // Bug reporting — explicit affordance for "I found an issue". When a
        // support channel is configured it surfaces a real "Report it" button
        // (see the report_issue case below); otherwise the user still gets an
        // acknowledgement + Help-nav prompt instead of the rotating fallback.
        id: 'report_issue',
        label: 'I found an issue',
        matches: [
            'found an issue', 'found a bug', 'found a problem',
            'report an issue', 'report a bug', 'report a problem',
            'this is broken', "something's broken", 'something is broken',
            "it's broken", 'its broken', 'there is a bug', "there's a bug",
            'bug report', 'raise an issue', 'file a bug',
        ],
    },
    {
        // Insults first — they overlap with `compliment` keywords (e.g.
        // "you're not great" contains "great").
        id: 'insult',
        label: "I'm just teasing",
        matches: [
            'you suck', 'you stink', 'you’re bad', "you're bad",
            'you’re useless', "you're useless", 'you’re terrible',
            "you're terrible", 'i hate you', 'hate you dora',
            'dumb bot', 'stupid bot', 'bad bot', 'worst bot',
            'shut up dora', 'shutup dora', 'go away dora',
        ],
    },
    {
        id: 'compliment',
        label: 'Compliment Dora',
        matches: [
            'thank you', 'thanks', 'ty dora', 'love you', 'love ya', 'ily',
            'you rock', 'you’re great', "you're great", 'you are great',
            'you’re the best', "you're the best", 'good job', 'well done',
            'nice work', 'good bot', 'best bot', 'amazing', 'awesome',
            'brilliant', 'fantastic', 'wonderful', 'genius', 'goated',
            "you're a legend", 'youre a legend', 'legend',
        ],
    },
    {
        id: 'goodbye',
        label: 'Bye!',
        matches: ['bye', 'goodbye', 'cya', 'see ya', 'later', 'cheerio', 'ttyl', 'gotta go'],
    },
    {
        id: 'greet',
        label: 'Hi Dora!',
        matches: ['hi', 'hello', 'hey', 'yo dora', 'gday', "g'day", 'howdy', 'morning', 'evening'],
    },
];

export const QUICK_ACTIONS: DoraIntentId[] = [
    'attention',
    'whats_for_dinner',
    'pantry_summary',
    'low_stock',
    'expiring',
    'shopping_list_status',
    'add_to_list',
    'page_help',
    'whats_new',
    'joke',
    'guides',
];

export function labelFor(id: DoraIntentId): string {
    return INTENTS.find((i) => i.id === id)?.label ?? id;
}

export function detectIntent(text: string): DoraIntentId {
    const lower = text.toLowerCase().trim();
    if (!lower) return 'greet';
    for (const intent of INTENTS) {
        if (intent.extraMatch?.(lower)) return intent.id;
        if (intent.matches.some((m) => lower.includes(m))) return intent.id;
    }
    return 'fallback';
}

// ── runIntent ──────────────────────────────────────────────────────────

export async function runIntent(
    id: DoraIntentId,
    context: DoraContext,
    rawText?: string,
): Promise<DoraReply> {
    // DR-7 (FU-578 #35) — capitalise the username so greetings read
    // "Hi, Dora!" not the raw lowercase handle "Hi, dora!". Mirrors the
    // dashboard greeting fix (DR-4). Comma-prefixed so reply banks can drop it
    // inline (`Hi${name}!`).
    const handle = context.username?.trim();
    const displayName = handle ? handle.replace(/^\w/, (c) => c.toUpperCase()) : '';
    const name = displayName ? `, ${displayName}` : '';

    switch (id) {
        case 'greet': {
            return {
                text: pick(GREETING_REPLIES(name, displayName)),
                mood: 'happy',
                suggestions: ['whats_for_dinner', 'attention', 'pantry_summary', 'joke'],
            };
        }

        case 'goodbye': {
            return {
                text: pick(GOODBYE_REPLIES(name)),
                mood: 'cute',
            };
        }

        case 'page_help': {
            const summary = pageSummary(context.currentPath);
            return {
                text: summary.text,
                mood: summary.mood,
                suggestions: ['guides', 'how_do_i', 'whats_new'],
            };
        }

        case 'show_around': {
            return {
                text:
                    "Quick tour: Dashboard is home. Stock is your pantry. Locations is where things live. Recipes and Meals plan what you'll cook. Product Search hunts deals. Settings is preferences (and admin tools if you're an admin). Anywhere specific I can drop you?",
                mood: 'confident',
                suggestions: ['guides', 'page_help'],
            };
        }

        case 'whats_new': {
            const versionInfo = context.fetchVersion ? await context.fetchVersion() : null;
            const updateBit = versionInfo?.updateAvailable
                ? ` There's also a newer version (${versionInfo.latest}) available.`
                : '';
            return {
                // The Help-page changelog is the one place updates are written
                // up, so the reply points there rather than listing highlights
                // that go stale (finalisation 11-R23).
                text: `You're on Dashy Dora ${versionInfo?.current ?? 'an unknown version'}. The Help page has the full changelog.${updateBit}`,
                mood: versionInfo?.updateAvailable ? 'super_excited' : 'excited',
                navigateTo: { path: '/help', label: 'Open Help (changelog tab)' },
            };
        }

        case 'version': {
            const info = context.fetchVersion ? await context.fetchVersion() : null;
            if (!info) {
                return { text: "I couldn't reach the version endpoint. Try again in a sec.", mood: 'confused' };
            }
            const updateLine = info.updateAvailable
                ? ` A newer version (${info.latest}) is out!`
                : info.latest
                    ? " You're on the latest. Smug bot noises."
                    : '';
            return {
                text: `I'm Dashy Dora ${info.current}.${updateLine}`,
                mood: info.updateAvailable ? 'super_excited' : 'confident',
                ...(info.updateAvailable && info.releaseUrl
                    ? { externalLink: { url: info.releaseUrl, label: 'See release notes' } }
                    : {}),
            };
        }

        case 'tell_me_something': {
            return {
                text: pick(FUN_REPLIES),
                mood: 'cute',
                suggestions: ['tell_me_something', 'joke', 'food_fact'],
            };
        }

        case 'joke': {
            return {
                text: pick(JOKES),
                mood: 'excited',
                suggestions: ['joke', 'tell_me_something'],
            };
        }

        case 'food_fact': {
            const fact = context.fetchFoodFact ? await context.fetchFoodFact() : null;
            if (!fact) {
                return {
                    text: "Couldn't grab a fresh fact, but here's a free one: honey never spoils. You're welcome.",
                    mood: 'happy',
                };
            }
            return {
                text: fact,
                mood: 'searching',
                suggestions: ['food_fact', 'joke'],
            };
        }

        case 'guides': {
            return {
                text: "The guides are on the Help page. Want me to take you?",
                mood: 'searching',
                navigateTo: { path: '/help', label: 'Open the guides' },
            };
        }

        case 'stuck': {
            return {
                text: "No drama. Tell me what you're trying to do (\"add a stock item\", \"plan dinner\"), or head to the guides.",
                mood: 'happy',
                navigateTo: { path: '/help', label: 'Take me to the guides' },
                suggestions: ['show_around', 'how_do_i'],
            };
        }

        case 'how_do_i': {
            return {
                text: "Tell me what you're trying to do (\"add a stock item\", \"plan dinner\") and I'll point at the right page.",
                mood: 'searching',
                navigateTo: { path: '/help', label: 'Browse guides by area' },
            };
        }

        case 'attention': {
            const info = context.fetchAttention ? await context.fetchAttention() : null;
            if (!info) {
                return { text: "Couldn't reach the alerts service. Try the bell icon up top.", mood: 'confused' };
            }
            const total = info.high + info.medium + info.low;
            if (total === 0) {
                return {
                    text: "Pantry's pristine. Nothing's screaming, nothing's leaking, nothing's expired. Smug shrug.",
                    mood: 'super_excited',
                    suggestions: ['whats_for_dinner', 'tell_me_something'],
                };
            }
            const breakdown = [
                info.high ? `${info.high} high` : null,
                info.medium ? `${info.medium} medium` : null,
                info.low ? `${info.low} low` : null,
            ].filter(Boolean).join(' · ');
            const sample = info.topMessages.slice(0, 3).map((m) => `• ${m}`).join('\n');
            return {
                text: `${total} thing${total === 1 ? '' : 's'} want your attention (${breakdown}).\n\n${sample}\n\nBell icon up top has the full list.`,
                mood: info.high > 0 ? 'worried' : 'searching',
                navigateTo: { path: '/stock', label: 'See it on the Stock page' },
            };
        }

        case 'insult': {
            return {
                text: pick(INSULT_REPLIES),
                mood: 'sad',
                suggestions: ['tell_me_something', 'joke'],
            };
        }

        case 'compliment': {
            return {
                text: pick(COMPLIMENT_REPLIES),
                mood: 'super_excited',
                suggestions: ['tell_me_something', 'joke'],
            };
        }

        // ── New data-driven intents ──────────────────────────────────────

        case 'pantry_summary': {
            const stock = context.getStock?.() ?? [];
            if (stock.length === 0) {
                return {
                    text: "Pantry's empty, or hasn't loaded yet.",
                    mood: 'confused',
                    navigateTo: { path: '/stock', label: 'Open Stock' },
                };
            }
            const low = stock.filter((s) => (s.levelSequence ?? 0) >= LOW_STOCK_SEQUENCE);
            const horizon = context.expiringSoonWindowDays ?? EXPIRY_HORIZON_FALLBACK_DAYS;
            const expiring = stock.filter((s) => {
                const d = daysUntil(s.expiryDate);
                return d !== null && d <= horizon;
            });
            const flagged = stock.filter((s) => s.isEssential);
            return {
                text: `${stock.length} item${stock.length === 1 ? '' : 's'} tracked. ${low.length} low, ${expiring.length} expiring soon, ${flagged.length} flagged. ${low.length + expiring.length === 0 ? "All under control. Magnificent." : "Want the rundown?"}`,
                mood: low.length + expiring.length === 0 ? 'super_excited' : 'searching',
                navigateTo: { path: '/stock', label: 'Open Stock' },
                suggestions: ['low_stock', 'expiring', 'attention'],
            };
        }

        case 'low_stock': {
            const stock = context.getStock?.() ?? [];
            const low = stock.filter((s) => (s.levelSequence ?? 0) >= LOW_STOCK_SEQUENCE);
            if (low.length === 0) {
                return {
                    text: "Nothing's low! Pantry's flexing right now.",
                    mood: 'super_excited',
                    navigateTo: { path: '/stock', label: 'Open Stock' },
                };
            }
            const names = low.map((s) => `${s.name}${s.levelSequence === OUT_OF_STOCK_SEQUENCE ? ' (out)' : ''}`);
            return {
                text: `${low.length} thing${low.length === 1 ? "'s" : 's are'} low: ${listOf(names)}.`,
                mood: low.some((s) => s.levelSequence === OUT_OF_STOCK_SEQUENCE) ? 'worried' : 'searching',
                navigateTo: { path: '/stock', label: 'See Stock' },
                suggestions: ['shopping_list_status', 'pantry_summary'],
            };
        }

        case 'expiring': {
            const stock = context.getStock?.() ?? [];
            const horizon = context.expiringSoonWindowDays ?? EXPIRY_HORIZON_FALLBACK_DAYS;
            const expiring = stock
                .map((s) => ({ s, d: daysUntil(s.expiryDate) }))
                .filter((x) => x.d !== null && x.d <= horizon)
                .sort((a, b) => (a.d! - b.d!));
            if (expiring.length === 0) {
                return {
                    text: "Nothing's about to turn on you. The fridge is well-behaved.",
                    mood: 'super_excited',
                };
            }
            const summary = expiring.slice(0, 6).map((x) => `• ${x.s.name}: ${expiryPhrase(x.s.expiryDate)}`).join('\n');
            const worst = expiring[0]!.d!;
            return {
                text: `${expiring.length} item${expiring.length === 1 ? '' : 's'} expiring soon:\n\n${summary}${expiring.length > 6 ? `\n\n…and ${expiring.length - 6} more.` : ''}`,
                mood: worst < 0 ? 'sad' : worst <= 1 ? 'worried' : 'searching',
                navigateTo: { path: '/stock', label: 'See Stock' },
                suggestions: ['whats_for_dinner', 'shopping_list_status'],
            };
        }

        case 'where_is': {
            const stock = context.getStock?.() ?? [];
            const query = (rawText ? extractAfter(rawText, ['where is', "where's", 'where do i keep', 'where are my', 'where did i put']) : null) ?? '';
            if (!query) {
                return { text: "Where's what? Throw me an item name and I'll go looking.", mood: 'searching' };
            }
            const matches = stock.filter((s) => s.name.toLowerCase().includes(query.toLowerCase()));
            if (matches.length === 0) {
                return {
                    text: `Nothing called "${query}" in your stock. Either it's not tracked or you've spelled it more creatively than I have.`,
                    mood: 'confused',
                    navigateTo: { path: '/stock', label: 'Open Stock' },
                };
            }
            if (matches.length === 1) {
                const item = matches[0]!;
                return {
                    text: item.locationName
                        ? `${item.name} lives in ${item.locationName}.`
                        : `${item.name} doesn't have a location set yet.`,
                    mood: 'confident',
                    navigateTo: { path: `/stock/${item.id}`, label: 'Open item' },
                };
            }
            const lines = matches.slice(0, 5).map((m) => `• ${m.name}${m.locationName ? `: ${m.locationName}` : ' (no location)'}`).join('\n');
            return {
                text: `A few "${query}" candidates:\n\n${lines}${matches.length > 5 ? `\n\n…and ${matches.length - 5} more.` : ''}`,
                mood: 'searching',
                navigateTo: { path: '/stock', label: 'Open Stock' },
            };
        }

        case 'find_recipe': {
            // instead of yanking the noun chunk after
            // "recipe for"/"how to cook", filter the recipe list by
            // every term we recognise in the message. Substring-match
            // each candidate's name + cuisine + category +
            // dietaryTagNames + timeOfDay against tokens in the raw
            // text. "i need a vegetarian recipe" matches every
            // recipe whose dietaryTagNames includes 'vegetarian'.
            // "show me an asian breakfast recipe" matches recipes
            // whose cuisine + timeOfDay both hit.
            const recipes = context.getRecipes?.() ?? [];
            const lower = (rawText ?? '').toLowerCase();
            const stopwords = new Set([
                'a', 'an', 'and', 'any', 'are', 'find', 'for', 'from', 'how',
                'i', 'idea', 'ideas', 'in', 'is', 'me', 'my', 'need', 'of',
                'on', 'or', 'recipe', 'recipes', 'show', 'something', 'the',
                'to', 'want', 'what', 'with', 'do', 'make', 'cook', 'meal',
                'meals', 'have', 'tonight', 'today', 'please',
            ]);
            const tokens = lower
                .replace(/[^a-z0-9 ]+/g, ' ')
                .split(/\s+/)
                .filter((t) => t.length > 1 && !stopwords.has(t));
            const matchesFor = (r: RecipeSnapshot, t: string): boolean =>
                r.name.toLowerCase().includes(t)
                || (r.cuisine ?? '').toLowerCase().includes(t)
                || (r.category ?? '').toLowerCase().includes(t)
                || (r.timeOfDay ?? '').toLowerCase().includes(t)
                || r.dietaryTagNames.some((n) => n.toLowerCase().includes(t));
            const matches = tokens.length === 0
                ? []
                : recipes.filter((r) => tokens.every((t) => matchesFor(r, t)));
            if (tokens.length === 0) {
                return {
                    text: "Recipe for what? Drop a name, an ingredient, a cuisine ('asian', 'italian'), or a dietary tag ('vegetarian', 'gluten free').",
                    mood: 'searching',
                    navigateTo: { path: '/cookbook', label: 'Browse cookbook' },
                };
            }
            // Pretty-string the matched terms back for the reply so
            // the user sees what we filtered on.
            const queryDisplay = tokens.join(' + ');
            if (matches.length === 0) {
                return {
                    text: `No recipe matching ${queryDisplay}. Try a broader term.`,
                    mood: 'confused',
                    navigateTo: { path: '/cookbook', label: 'Browse cookbook' },
                };
            }
            if (matches.length === 1) {
                const r = matches[0]!;
                return {
                    text: `Got one: ${r.name}${r.cookTimeMinutes ? `, ${r.cookTimeMinutes} min cook` : ''}${r.cuisine ? ` · ${r.cuisine}` : ''}.`,
                    mood: 'confident',
                    navigateTo: { path: `/cookbook/${r.id}`, label: 'Open recipe' },
                };
            }
            const top = matches.slice(0, 5).map((r) => `• ${r.name}${r.cuisine ? ` (${r.cuisine})` : ''}`).join('\n');
            return {
                text: `${matches.length} candidate${matches.length === 1 ? '' : 's'} for ${queryDisplay}:\n\n${top}${matches.length > 5 ? `\n\n…and ${matches.length - 5} more.` : ''}`,
                mood: 'lightbulb',
                navigateTo: { path: '/cookbook', label: 'Browse cookbook' },
            };
        }

        case 'whats_for_dinner': {
            const recipes = context.getRecipes?.() ?? [];
            const stock = context.getStock?.() ?? [];
            if (recipes.length === 0) {
                return {
                    text: "No recipes yet! Add a few and I'll start making suggestions like a pushy aunty.",
                    mood: 'confused',
                    navigateTo: { path: '/cookbook', label: 'Open Cookbook' },
                };
            }
            const inStockIds = new Set(
                stock.filter((s) => (s.levelSequence ?? 0) < OUT_OF_STOCK_SEQUENCE).map((s) => s.id),
            );
            const scored = recipes.map((r) => {
                const total = r.ingredientStockItemIds.length;
                const have = r.ingredientStockItemIds.filter((id) => inStockIds.has(id)).length;
                const coverage = total ? have / total : 0;
                return { r, coverage, have, total, ready: total > 0 && have === total };
            });
            scored.sort((a, b) => (Number(b.ready) - Number(a.ready)) || (b.coverage - a.coverage) || (Number(b.r.isFavourite) - Number(a.r.isFavourite)));
            const top = scored.slice(0, 3);
            const lines = top.map((x) =>
                x.ready
                    ? `• ${x.r.name}: you've got everything`
                    : `• ${x.r.name}: ${x.have}/${x.total} ingredients in`,
            ).join('\n');
            const allReady = top.every((x) => x.ready);
            return {
                text: `Here's the shortlist:\n\n${lines}\n\n${allReady ? "Pick one and I'll have a small party." : "Nothing's quite there. The closest one is first."}`,
                mood: allReady ? 'super_excited' : 'lightbulb',
                navigateTo: { path: '/cookbook', label: 'Open Cookbook' },
                suggestions: ['expiring', 'shopping_list_status'],
            };
        }

        case 'shopping_list_status': {
            const lists = context.getShoppingLists?.() ?? [];
            if (lists.length === 0) {
                return {
                    text: "No shopping lists yet. Spin one up and I'll start treating it like a sacred scroll.",
                    mood: 'confused',
                    navigateTo: { path: '/shopping-lists', label: 'Open Shopping Lists' },
                };
            }
            const target = lists.find((l) => l.isQuickAddTarget) ?? lists[0]!;
            const total = lists.reduce((sum, l) => sum + l.itemCount, 0);
            return {
                text: `${lists.length} list${lists.length === 1 ? '' : 's'} on the go, ${total} item${total === 1 ? '' : 's'} total. New adds land on "${target.name}", which has ${target.itemCount}.`,
                mood: total === 0 ? 'cute' : 'searching',
                navigateTo: { path: '/shopping-lists', label: 'Open Shopping Lists' },
                suggestions: ['low_stock', 'expiring'],
            };
        }

        case 'add_to_list': {
            // Safety net only — DoraChat intercepts this intent before
            // runIntent so it can resolve names against the pantry and
            // perform the add through the shopping-list composable (the
            // mutation can't live in this pure handler). If we're reached,
            // the message carried no parseable item.
            return {
                text: "Sure, what should I add? Try \"add milk\" or \"add eggs and bread\".",
                mood: 'searching',
                suggestions: ['shopping_list_status', 'low_stock'],
            };
        }

        case 'weeks_meals': {
            const plan = context.getMealPlan?.();
            if (!plan || plan.upcomingMealNames.length === 0) {
                return {
                    text: "Nothing on the meal plan in the immediate future. Want to map something out?",
                    mood: 'cute',
                    navigateTo: { path: '/meal-plans', label: 'Open Meal Plans' },
                    suggestions: ['whats_for_dinner'],
                };
            }
            const lines = plan.upcomingMealNames.slice(0, 5).map((m) => `• ${m}`).join('\n');
            return {
                text: `Coming up:\n\n${lines}\n\n(${plan.startDate} → ${plan.endDate})`,
                mood: 'lightbulb',
                navigateTo: { path: '/meal-plans', label: 'Open Meal Plans' },
            };
        }

        case 'convert': {
            const result = rawText ? tryConvert(rawText) : null;
            if (!result) {
                return {
                    text: "Couldn't parse that as a conversion. Try something like \"200g to oz\" or \"1 cup to ml\".",
                    mood: 'confused',
                };
            }
            return { text: result, mood: 'confident' };
        }

        case 'substitute': {
            const query = rawText
                ? extractAfter(rawText, ['substitute for', 'sub for', 'instead of', 'replacement for', 'replace', "don't have", 'no ', 'ran out of'])
                : null;
            const result = query ? trySubstitute(query) : null;
            if (!result) {
                return {
                    text: query
                        ? `I don't have a stock substitute for "${query}" off the top of my head. Try AI mode if it's on.`
                        : "Substitute for what? Name the missing ingredient and I'll suggest swaps.",
                    mood: 'sad',
                };
            }
            return { text: result, mood: 'lightbulb', suggestions: ['shopping_list_status', 'find_recipe'] };
        }

        case 'report_issue': {
            // FU-370 — if the operator has configured a support channel, surface
            // it as a real "Report it" button (externalLink → new tab); otherwise
            // fall back to pointing at Help. Same acknowledge-first tone either way.
            const channel = currentSupportChannel();
            const href = supportHref(channel, {
                subject: '[Dora] Bug report',
                body: '\n\n---\n(reported from the Dora assistant)',
            });
            if (href) {
                const introsWithChannel = [
                    "Oh no, sorry about that. Jot down what you did and what you expected, then send it in below.",
                    "Bugs! My one weakness (other than soggy buns). Note the steps + what you expected and file it below.",
                    "Appreciate the heads-up. Capture the details so they don't get lost, then use the button to report it properly.",
                    "Noted! Steps to reproduce and what you expected, in a report below.",
                ];
                return {
                    text: pick(introsWithChannel),
                    mood: 'worried',
                    externalLink: { url: href, label: 'Report it' },
                    suggestions: ['stuck', 'guides'],
                };
            }
            // Dormant install — no channel configured. Acknowledge and point at
            // Help; no external link to offer.
            const intros = [
                "Oh no, sorry about that. If it's a real bug, jot down what happened.",
                "Bugs! My one weakness (other than soggy buns). Note the steps + what you expected and pass it on to whoever's running this Dora instance.",
                "Appreciate the heads-up. Help has the troubleshooting guides; for anything that smells like a real defect, capture the details so they don't get lost.",
                "Noted! Write down the steps to reproduce and what you expected.",
            ];
            return {
                text: pick(intros),
                mood: 'worried',
                navigateTo: { path: '/help', label: 'Open Help' },
                suggestions: ['stuck', 'guides'],
            };
        }
        case 'fallback':
        default: {
            return {
                text: pick(FALLBACK_REPLIES),
                mood: 'confused',
                navigateTo: { path: '/help', label: 'Open Help' },
                suggestions: ['stuck', 'guides', 'whats_for_dinner', 'joke'],
            };
        }
    }
}
