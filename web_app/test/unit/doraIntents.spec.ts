// FU-390 — Basic-mode assistant eval suite.
//
// The rule engine (`doraIntents.ts`) is the DEFAULT assistant experience for
// every install that hasn't wired up a language model, so it deserves
// first-class eval coverage — not just the AI path. These tests are an eval
// *corpus*: a table of realistic user phrasings mapped to the capability the
// user expects. Order-sensitivity in `detectIntent` (first-match-wins over the
// INTENTS array) is exactly the kind of thing that silently regresses when
// someone adds a broad keyword, so we pin the tricky boundaries explicitly.
//
// Pure functions only — no Vue, no pinia, no network (see vitest.config.ts).
import { describe, expect, it } from 'vitest';

import {
    detectIntent,
    extractAddToListItems,
    runIntent,
    type DoraContext,
    type DoraIntentId,
} from 'src/services/doraIntents';

describe('detectIntent — intent routing corpus', () => {
    // [prompt, expected intent] — realistic phrasings a user might type.
    const CORPUS: Array<[string, DoraIntentId]> = [
        // greetings / social
        ['hi', 'greet'],
        ['hey dora', 'greet'],
        ['g\'day', 'greet'],
        ['bye', 'goodbye'],
        ['see ya', 'goodbye'],
        ['tell me a joke', 'joke'],
        ['make me laugh', 'joke'],

        // pantry reads
        ["what's low", 'low_stock'],
        ['what am i running low on', 'low_stock'],
        ['what is expiring', 'expiring'],
        ['anything about to go off', 'expiring'],
        ["how's my pantry", 'pantry_summary'],
        ['what needs attention', 'attention'],

        // shopping list read vs write (the FU-429 boundary)
        ["what's on my list", 'shopping_list_status'],
        ['my shopping list', 'shopping_list_status'],

        // recipes
        ['recipe for lasagne', 'find_recipe'],
        ['i need a recipe', 'find_recipe'],
        ['any breakfast ideas', 'find_recipe'],
        ["what's for dinner", 'whats_for_dinner'],
        ["i'm hungry", 'whats_for_dinner'],

        // conversions + substitutes (narrow, must beat find_recipe)
        ['convert 200g to oz', 'convert'],
        ['how many ml in a cup', 'convert'],
        ['200g to oz', 'convert'],
        ['substitute for eggs', 'substitute'],
        ['i have no butter', 'substitute'],
        ['ran out of milk', 'substitute'],

        // navigation / meta
        ['what can i do on this page', 'page_help'],
        ['what version are you', 'version'],
        ['where is my flour', 'where_is'],

        // meal plan
        ["what's the plan this week", 'weeks_meals'],
        ['upcoming meals', 'weeks_meals'],

        // unknown → fallback
        ['asdfghjkl', 'fallback'],
        ['xyzzy plugh', 'fallback'],
        // "tell me …" is deliberately caught by the playful tell_me_something
        // bank — Basic mode can't answer arbitrary topics, so it deflects with
        // a fun fact rather than an unhelpful fallback. Pinned so we notice if
        // that catch-all ever narrows.
        ['tell me about quantum chromodynamics', 'tell_me_something'],
    ];

    it.each(CORPUS)('routes %j → %s', (prompt, expected) => {
        expect(detectIntent(prompt)).toBe(expected);
    });

    it('routes the new add_to_list phrasings', () => {
        // Kept in its own block so a future broad-keyword regression here is
        // obvious. These are the everyday "put it on my list" forms.
        const addCases = [
            'add milk',
            'buy eggs',
            'add milk and bread',
            'add to my list',
            'put it on my list',
            'i need to buy rice',
            'need to get onions',
        ];
        for (const prompt of addCases) {
            expect(detectIntent(prompt)).toBe('add_to_list');
        }
    });

    it('does NOT mistake "i need a recipe" for add_to_list', () => {
        // find_recipe and add_to_list both live near "i need …"; the recipe
        // form must win (it has no buy/get/add trigger).
        expect(detectIntent('i need a recipe')).toBe('find_recipe');
        expect(detectIntent('i need a vegetarian recipe')).toBe('find_recipe');
    });

    it('empty / whitespace input greets rather than falls back', () => {
        expect(detectIntent('')).toBe('greet');
        expect(detectIntent('   ')).toBe('greet');
    });
});

describe('extractAddToListItems — add-to-list parsing corpus', () => {
    // [phrase, expected item list]
    const CORPUS: Array<[string, string[]]> = [
        ['add milk', ['milk']],
        ['buy eggs', ['eggs']],
        ['add milk and bread', ['milk', 'bread']],
        ['add milk, bread and eggs', ['milk', 'bread', 'eggs']],
        ['buy milk & eggs', ['milk', 'eggs']],
        ['add some milk', ['milk']],
        ['add a loaf of bread', ['loaf of bread']],
        ['i need to buy rice', ['rice']],
        ['need to get onions', ['onions']],
        // trailing "to my/the (shopping) list" is stripped
        ['add milk to my list', ['milk']],
        ['add eggs to the shopping list', ['eggs']],
        ['put milk on my list', ['milk']],
        // bare command with no item → nothing to add
        ['add to my list', []],
        ['add to the list', []],
    ];

    it.each(CORPUS)('parses %j → %j', (phrase, expected) => {
        expect(extractAddToListItems(phrase)).toEqual(expected);
    });

    it('lower-cases and trims consistently', () => {
        expect(extractAddToListItems('  ADD  Milk  ')).toEqual(['milk']);
    });
});

describe('runIntent — greeting name (DR-7 / FU-578 #35)', () => {
    const ctx = (username?: string): DoraContext => ({ currentPath: '/', username });

    it('capitalises the username in the greeting (never the raw lowercase handle)', async () => {
        // pick() is random across 5 variants; loop so we exercise several.
        for (let i = 0; i < 12; i++) {
            const reply = await runIntent('greet', ctx('dora'));
            expect(reply.text).toContain('Dora');
            expect(reply.text).not.toContain(', dora');
        }
    });

    it('greets cleanly when no username is set (no ", undefined" / dangling comma)', async () => {
        for (let i = 0; i < 12; i++) {
            const reply = await runIntent('greet', ctx(undefined));
            expect(reply.text).not.toContain('undefined');
            expect(reply.text).not.toMatch(/Hi, !/);
        }
    });
});
