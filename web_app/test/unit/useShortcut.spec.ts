// @vitest-environment jsdom
// The shortcut layer must leave keys to the control that owns them (an open
// menu, a focused button) and still deliver Escape to a page that registered
// it once the cheatsheet has nothing to close (cook mode's "Exit cook mode").
import { afterEach, describe, expect, it, vi } from 'vitest';
import { defineComponent, h } from 'vue';
import { mount, type VueWrapper } from '@vue/test-utils';
import { useShortcut } from 'src/composables/useShortcut';

let wrapper: VueWrapper | null = null;

function register(keys: string): ReturnType<typeof vi.fn> {
    const handler = vi.fn();
    wrapper = mount(defineComponent({
        setup() {
            useShortcut({ keys, scope: 'Test', description: 'test', handler });
            return () => h('div');
        },
    }), { attachTo: document.body });
    return handler;
}

function press(key: string, target: Element = document.body): KeyboardEvent {
    const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true });
    target.dispatchEvent(event);
    return event;
}

afterEach(() => {
    wrapper?.unmount();
    wrapper = null;
    document.body.innerHTML = '';
});

describe('useShortcut', () => {
    it('delivers Escape to a registered shortcut when the cheatsheet is closed', () => {
        const handler = register('escape');
        press('Escape');
        expect(handler).toHaveBeenCalledTimes(1);
    });

    it('leaves keys typed inside an open menu to the menu', () => {
        const handler = register('arrowdown');
        const menu = document.createElement('div');
        menu.className = 'q-menu';
        const item = document.createElement('div');
        menu.appendChild(item);
        document.body.appendChild(menu);
        press('ArrowDown', item);
        expect(handler).not.toHaveBeenCalled();
    });

    it('leaves Enter on a focused button to the button', () => {
        const handler = register('enter');
        const button = document.createElement('button');
        document.body.appendChild(button);
        press('Enter', button);
        expect(handler).not.toHaveBeenCalled();
        press('Enter');
        expect(handler).toHaveBeenCalledTimes(1);
    });

    it('ignores a key something nearer the target already handled', () => {
        const handler = register('n');
        const el = document.createElement('div');
        el.addEventListener('keydown', (e) => e.preventDefault());
        document.body.appendChild(el);
        press('n', el);
        expect(handler).not.toHaveBeenCalled();
    });
});
