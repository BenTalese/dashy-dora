import { beforeEach, describe, expect, it, vi } from 'vitest';

const created: Array<Record<string, unknown>> = [];
let answer: { kind: 'ok'; payload?: unknown } | { kind: 'cancel' } | { kind: 'dismiss' } = { kind: 'ok' };

vi.mock('quasar', () => ({
    Dialog: {
        create(options: Record<string, unknown>) {
            created.push(options);
            const chain = {
                onOk(cb: (payload?: unknown) => void) {
                    if (answer.kind === 'ok') cb(answer.payload);
                    return chain;
                },
                onCancel(cb: () => void) {
                    if (answer.kind === 'cancel') cb();
                    return chain;
                },
                onDismiss(cb: () => void) {
                    if (answer.kind === 'dismiss') cb();
                    return chain;
                },
            };
            return chain;
        },
    },
}));

import { useConfirm } from 'src/composables/useConfirm';

const { confirm, prompt, choose, chooseMany } = useConfirm();

beforeEach(() => {
    created.length = 0;
    answer = { kind: 'ok' };
});

describe('confirm', () => {
    it('resolves true on OK and false on cancel, Escape or the backdrop', async () => {
        expect(await confirm({ title: 'Delete?' })).toBe(true);
        answer = { kind: 'cancel' };
        expect(await confirm({ title: 'Delete?' })).toBe(false);
        answer = { kind: 'dismiss' };
        expect(await confirm({ title: 'Delete?' })).toBe(false);
    });

    it('applies the house conventions: flat cancel, filled primary OK, Escape cancels, never html', async () => {
        await confirm({ title: 'Replace this week?', message: 'Three meals go.', okLabel: 'Replace' });
        const opts = created[0]!;
        expect(opts.persistent).toBe(false);
        expect(opts.html).toBeUndefined();
        expect(opts.ok).toEqual({ label: 'Replace', color: 'primary', unelevated: true, noCaps: true });
        expect(opts.cancel).toEqual({ label: 'Cancel', flat: true, noCaps: true });
    });

    it('paints a destructive OK negative and honours persistent and a custom cancel label', async () => {
        await confirm({
            title: 'Revoke key', okLabel: 'Revoke', cancelLabel: 'Keep it', destructive: true, persistent: true,
        });
        const opts = created[0]!;
        expect((opts.ok as { color: string }).color).toBe('negative');
        expect((opts.cancel as { label: string }).label).toBe('Keep it');
        expect(opts.persistent).toBe(true);
    });
});

describe('prompt', () => {
    it('returns the trimmed text, and null for cancel or an empty answer', async () => {
        answer = { kind: 'ok', payload: '  Aldi ' };
        expect(await prompt({ title: 'New store' })).toBe('Aldi');
        answer = { kind: 'ok', payload: '   ' };
        expect(await prompt({ title: 'New store' })).toBeNull();
        answer = { kind: 'cancel' };
        expect(await prompt({ title: 'New store' })).toBeNull();
    });

    it('seeds the field from initial and passes the validator through', async () => {
        const isValid = (v: string) => v.length > 2;
        await prompt({ title: 'Rename', initial: 'Pantry', type: 'text', isValid });
        const p = created[0]!.prompt as { model: string; type: string; isValid: unknown };
        expect(p.model).toBe('Pantry');
        expect(p.type).toBe('text');
        expect(p.isValid).toBe(isValid);
    });
});

describe('choose / chooseMany', () => {
    it('offers the items as radios, defaults to the first, returns the pick or null', async () => {
        answer = { kind: 'ok', payload: 'b' };
        const items = [{ label: 'A', value: 'a' }, { label: 'B', value: 'b' }];
        expect(await choose({ title: 'Which?', items })).toBe('b');
        const o = created[0]!.options as { type: string; model: string };
        expect(o.type).toBe('radio');
        expect(o.model).toBe('a');
        answer = { kind: 'dismiss' };
        expect(await choose({ title: 'Which?', items })).toBeNull();
    });

    it('resolves null without opening anything when there is nothing to pick', async () => {
        expect(await choose({ title: 'Which?', items: [] })).toBeNull();
        expect(created).toHaveLength(0);
    });

    it('offers checkboxes seeded from initial', async () => {
        answer = { kind: 'ok', payload: ['a', 'c'] };
        const items = [{ label: 'A', value: 'a' }, { label: 'C', value: 'c' }];
        expect(await chooseMany({ title: 'Days', items, initial: ['a'] })).toEqual(['a', 'c']);
        const o = created[0]!.options as { type: string; model: string[] };
        expect(o.type).toBe('checkbox');
        expect(o.model).toEqual(['a']);
    });
});
