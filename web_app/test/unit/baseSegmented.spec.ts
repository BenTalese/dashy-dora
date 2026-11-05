// @vitest-environment jsdom
/**
 * BaseSegmented's radio-group contract (FU-848): one Tab stop, arrow keys move
 * *and* select, disabled options are skipped. Pinned here because it is the
 * reason this implementation survived the merge, and a keyboard regression is
 * invisible to anyone driving the app with a mouse.
 */
import { mount } from '@vue/test-utils';
import { QIcon, Quasar } from 'quasar';
import { describe, expect, it } from 'vitest';

import BaseSegmented from 'src/components/BaseSegmented.vue';

const options = [
    { label: 'One', value: 'a' },
    { label: 'Two', value: 'b', disable: true },
    { label: 'Three', value: 'c' },
];

function mountSeg(modelValue: string, extra: Record<string, unknown> = {}) {
    return mount(BaseSegmented, {
        props: { modelValue, options, ...extra },
        attrs: { 'aria-label': 'Pick' },
        global: { plugins: [Quasar], components: { QIcon } },
        attachTo: document.body,
    });
}

describe('BaseSegmented', () => {
    it('is a radiogroup whose selected option is the only Tab stop', () => {
        const w = mountSeg('c');
        expect(w.attributes('role')).toBe('radiogroup');
        const radios = w.findAll('[role="radio"]');
        expect(radios.map((r) => r.attributes('aria-checked'))).toEqual(['false', 'false', 'true']);
        expect(radios.map((r) => r.attributes('tabindex'))).toEqual(['-1', '-1', '0']);
        w.unmount();
    });

    it('arrow keys select the next enabled option, skipping disabled and wrapping', async () => {
        const w = mountSeg('a');
        await w.trigger('keydown', { key: 'ArrowRight' });
        expect(w.emitted('update:modelValue')?.[0]).toEqual(['c']);
        await w.setProps({ modelValue: 'c' });
        await w.trigger('keydown', { key: 'ArrowRight' });
        expect(w.emitted('update:modelValue')?.[1]).toEqual(['a']);
        await w.setProps({ modelValue: 'a' });
        await w.trigger('keydown', { key: 'End' });
        expect(w.emitted('update:modelValue')?.[2]).toEqual(['c']);
        w.unmount();
    });

    it('honours Quasar\'s `disable` spelling and a whole-group `disabled`', async () => {
        const w = mountSeg('a');
        expect(w.findAll('[role="radio"]')[1]?.attributes('disabled')).toBeDefined();
        await w.setProps({ disabled: true });
        await w.trigger('keydown', { key: 'ArrowRight' });
        expect(w.emitted('update:modelValue')).toBeUndefined();
        w.unmount();
    });

    it('lets `aria-label` fall through to the group and keeps `dense` off the DOM', () => {
        const w = mountSeg('a', { dense: true, 'aria-label': 'Sort by' });
        expect(w.attributes('aria-label')).toBe('Sort by');
        expect(w.attributes('dense')).toBeUndefined();
        expect(w.classes()).toContain('base-segmented--dense');
        w.unmount();
    });
});
