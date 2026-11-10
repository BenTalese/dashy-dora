// @vitest-environment jsdom
/**
 * The menu-vs-dialog rule (owner feedback 2026-08-19: "most dropdowns open a
 * modal, but our custom ones behave normally… when there's too many options
 * it can be difficult to tap out of these dropdown input modals").
 *
 * Worth a test rather than a browser walk, because the thing that decides it is
 * `$q.platform.is.mobile` — **user-agent based, not viewport based**. You
 * cannot see the mobile branch by resizing a desktop browser, and the preview
 * pane reports a desktop UA, so this rule is effectively unobservable outside a
 * real phone. Here the platform is just a mock.
 */
import { mount } from '@vue/test-utils';
import { QSelect, Quasar } from 'quasar';
import { describe, expect, it } from 'vitest';

import BaseSelect from 'src/components/BaseSelect.vue';

function mountSelect(props: Record<string, unknown>, mobile = false) {
    return mount(BaseSelect, {
        props: { modelValue: null, options: [], ...props },
        global: {
            plugins: [Quasar],
            components: { QSelect },
            mocks: { $q: { platform: { is: { mobile } } } },
        },
    });
}

const shortList = ['Easy', 'Medium', 'Hard'];
const longList = Array.from({ length: 30 }, (_, i) => `Item ${i}`);

describe('BaseSelect — behaviour rule', () => {
    it('uses an anchored menu for a short closed vocabulary', () => {
        // The owner's preferred style, and the one a phone has room for.
        expect(mountSelect({ options: shortList }).findComponent(QSelect).props('behavior'))
            .toBe('menu');
    });

    it('falls back to Quasar default (dialog on mobile) for a long list', () => {
        expect(mountSelect({ options: longList }).findComponent(QSelect).props('behavior'))
            .toBe('default');
    });

    it('treats a typeahead select as long regardless of its resting options', () => {
        // `use-input` filters from a source the option count doesn't describe,
        // and needs to survive the software keyboard.
        expect(
            mountSelect({ options: shortList, useInput: true })
                .findComponent(QSelect).props('behavior'),
        ).toBe('default');
    });

    it('honours an explicit behavior override', () => {
        expect(
            mountSelect({ options: longList, behavior: 'menu' })
                .findComponent(QSelect).props('behavior'),
        ).toBe('menu');
    });

    it('puts the boundary at 8 options inclusive', () => {
        const eight = Array.from({ length: 8 }, (_, i) => `o${i}`);
        const nine = Array.from({ length: 9 }, (_, i) => `o${i}`);
        expect(mountSelect({ options: eight }).findComponent(QSelect).props('behavior'))
            .toBe('menu');
        expect(mountSelect({ options: nine }).findComponent(QSelect).props('behavior'))
            .toBe('default');
    });
});

describe('BaseSelect — prop forwarding', () => {
    it('still hands use-input down to q-select', () => {
        // Regression: `useInput` is declared on BaseSelect so the behaviour
        // rule can read it — which means Vue consumes it and drops it from
        // `$attrs`. Without an explicit forward the typeahead silently stops
        // working while the control still looks correct. Caught live on the
        // stock location picker, 2026-08-19.
        const wrapper = mountSelect({ options: longList, useInput: true });
        expect(wrapper.findComponent(QSelect).props('useInput')).toBe(true);
    });

    it('drops the typeahead on a phone unless the call site opts back in', async () => {
        const { Platform } = await import('quasar');
        const was = Platform.is.mobile;
        Platform.is.mobile = true;
        try {
            const dropped = mountSelect({ options: longList, useInput: true }, true);
            expect(dropped.findComponent(QSelect).props('useInput')).toBe(false);
            const kept = mountSelect({ options: longList, useInput: true, typeOnMobile: true }, true);
            expect(kept.findComponent(QSelect).props('useInput')).toBe(true);
        } finally {
            Platform.is.mobile = was;
        }
    });

    it('leaves use-input off when the call site did not ask for it', () => {
        const wrapper = mountSelect({ options: longList });
        expect(wrapper.findComponent(QSelect).props('useInput')).toBe(false);
    });

    // FU-675: the last raw q-selects moved over, and three things they needed
    // had to be forwardable rather than forcing a site to stay raw.
    it('is dense + outlined by default, with dense overridable for full-height forms', () => {
        const dflt = mountSelect({ options: shortList }).findComponent(QSelect);
        expect(dflt.props('dense')).toBe(true);
        expect(dflt.props('outlined')).toBe(true);
        expect(mountSelect({ options: shortList, dense: false }).findComponent(QSelect).props('dense'))
            .toBe(false);
    });

    it('drops its outline when the call site picks borderless', () => {
        const q = mountSelect({ options: shortList, borderless: true }).findComponent(QSelect);
        expect(q.props('outlined')).toBe(false);
        expect(q.props('borderless')).toBe(true);
    });

    it('re-exposes the QSelect methods a typeahead reaches for through a ref', () => {
        const vm = mountSelect({ options: longList }).vm as unknown as Record<string, unknown>;
        for (const m of ['updateInputValue', 'hidePopup', 'showPopup', 'focus', 'validate']) {
            expect(typeof vm[m]).toBe('function');
        }
    });
});

describe('BaseSelect — the close affordance', () => {
    it('is absent on desktop, where the dropdown is a menu you click away from', () => {
        const wrapper = mountSelect({ options: longList }, false);
        expect(wrapper.html()).not.toContain('base-select__dialog-bar');
    });

    it('is absent even on mobile when the rule chose a menu', () => {
        const wrapper = mountSelect({ options: shortList }, true);
        expect(wrapper.html()).not.toContain('base-select__dialog-bar');
    });
});
