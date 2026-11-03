// @vitest-environment jsdom
// FU-539 resilience layer — ErrorBoundary.vue. A render error inside a page must
// show the PageErrorState fallback, NOT take the whole app down to a white
// screen; and the boundary must RESET on route change so navigating away from a
// crashed page recovers automatically (the FU-357 bell-crash regression home).
//
// PageErrorState is stubbed to a marker (its full tree is heavy and irrelevant
// here); useRoute is mocked with a reactive route object the test can mutate.
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { defineComponent, h, nextTick, ref } from 'vue';

// Reactive route shared with the mocked useRoute so tests can flip fullPath.
const state = vi.hoisted(() => ({ route: null as null | { fullPath: string } }));
vi.mock('vue-router', async () => {
    const { reactive } = await import('vue');
    state.route = reactive({ fullPath: '/start' });
    return { useRoute: () => state.route };
});
vi.mock('src/components/PageErrorState.vue', () => ({
    default: {
        name: 'PageErrorState',
        props: ['error', 'correlationId', 'variant', 'showReload', 'showDashboard', 'showReport'],
        template: '<div class="page-error-stub" />',
    },
}));

const retryNow = vi.hoisted(() => vi.fn(() => Promise.resolve(false)));
vi.mock('src/composables/useNetworkStatus', () => ({
    useNetworkStatus: () => ({ retryNow }),
}));

import ErrorBoundary from 'src/components/ErrorBoundary.vue';
import { NormalisedApiError } from 'src/services/api/axiosHttpClient';

// A child whose render throws only while `boom` is true, so we can drive both
// the crash and the post-reset recovery from one component.
const boom = ref(true);
const Child = defineComponent({
    setup() {
        return () => {
            if (boom.value) throw new Error('render boom');
            return h('div', { class: 'child-ok' }, 'ok');
        };
    },
});

async function mountBoundary() {
    const wrapper = mount(ErrorBoundary, {
        slots: { default: () => h(Child) },
    });
    // onErrorCaptured sets caughtError during mount; the fallback swaps in on
    // the next flush.
    await flushPromises();
    return wrapper;
}

let errorSpy: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
    boom.value = true;
    if (state.route) state.route.fullPath = '/start';
    // onErrorCaptured logs via console.error; silence the expected noise.
    errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
});
afterEach(() => {
    errorSpy.mockRestore();
});

describe('ErrorBoundary — crash containment', () => {
    it('renders the PageErrorState fallback and hides the slot when a child throws', async () => {
        const wrapper = await mountBoundary();

        expect(wrapper.find('.page-error-stub').exists()).toBe(true);
        expect(wrapper.find('.child-ok').exists()).toBe(false);
    });

    it('wires the reload / dashboard / report escape hatches into the fallback', async () => {
        const wrapper = await mountBoundary();

        const fallback = wrapper.findComponent({ name: 'PageErrorState' });
        expect(fallback.props('showReload')).toBe(true);
        expect(fallback.props('showDashboard')).toBe(true);
        expect(fallback.props('showReport')).toBe(true);
        expect(fallback.props('variant')).toBe('render');
    });
});

describe('ErrorBoundary — reset on navigation (FU-357)', () => {
    it('clears the caught error on route change so the recovered page renders', async () => {
        const wrapper = await mountBoundary();
        expect(wrapper.find('.page-error-stub').exists()).toBe(true);

        // The page that replaces the crashed one no longer throws; navigating
        // there must drop the boundary and render live content again.
        boom.value = false;
        state.route!.fullPath = '/recovered';
        await nextTick();
        await flushPromises();

        expect(wrapper.find('.page-error-stub').exists()).toBe(false);
        expect(wrapper.find('.child-ok').exists()).toBe(true);
    });
});

describe('ErrorBoundary — API unreachable', () => {
    it('keeps the slot and asks the network probe instead of showing the fallback', async () => {
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
        const Failing = defineComponent({
            setup() {
                return () => {
                    throw new NormalisedApiError({
                        status: 0,
                        code: 'network_error',
                        message: 'Network request failed',
                        details: null,
                        correlationId: '',
                        isNetworkError: true,
                        method: 'GET',
                        url: '/recipes',
                    });
                };
            },
        });
        const wrapper = mount(ErrorBoundary, { slots: { default: () => h(Failing) } });
        await flushPromises();

        expect(wrapper.find('.page-error-stub').exists()).toBe(false);
        expect(retryNow).toHaveBeenCalled();
        warnSpy.mockRestore();
    });
});
