// @vitest-environment jsdom
// The cook-mode timer counts against a deadline (04-R8): a throttled or
// suspended background tab must not make a 20-minute timer run slow.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { formatTimer, useCookTimer } from 'src/composables/useCookTimer';

function host(onFinish = vi.fn()) {
    let timer!: ReturnType<typeof useCookTimer>;
    const wrapper = mount(defineComponent({
        setup() {
            timer = useCookTimer({ onFinish });
            return () => null;
        },
    }));
    return { timer, onFinish, wrapper };
}

describe('useCookTimer', () => {
    beforeEach(() => { vi.useFakeTimers(); });
    afterEach(() => { vi.useRealTimers(); });

    it('counts down by the clock, one tick a second', () => {
        const { timer } = host();
        timer.start(90);
        vi.advanceTimersByTime(30_000);
        expect(timer.remaining.value).toBe(60);
        expect(timer.progress.value).toBeCloseTo(60 / 90);
    });

    it('keeps true time when ticks are throttled (a backgrounded tab)', () => {
        const { timer } = host();
        timer.start(20 * 60);
        // Only one tick fires in ten minutes, but ten minutes still passed.
        vi.setSystemTime(Date.now() + 10 * 60_000);
        vi.advanceTimersByTime(1000);
        expect(timer.remaining.value).toBe(10 * 60 - 1);
    });

    it('re-syncs when the tab becomes visible again', () => {
        const { timer } = host();
        timer.start(300);
        vi.setSystemTime(Date.now() + 120_000);
        document.dispatchEvent(new Event('visibilitychange'));
        expect(timer.remaining.value).toBe(180);
    });

    it('finishes once, at zero, and stops', () => {
        const { timer, onFinish } = host();
        timer.start(3);
        vi.advanceTimersByTime(5000);
        expect(timer.remaining.value).toBe(0);
        expect(timer.running.value).toBe(false);
        expect(onFinish).toHaveBeenCalledTimes(1);
    });

    it('restarting after it finished counts down afresh', () => {
        const { timer, onFinish } = host();
        timer.start(3);
        vi.advanceTimersByTime(5000);
        timer.start(10);
        expect(timer.remaining.value).toBe(10);
        expect(timer.total.value).toBe(10);
        vi.advanceTimersByTime(4000);
        expect(timer.remaining.value).toBe(6);
        expect(onFinish).toHaveBeenCalledTimes(1);
    });

    it('pause holds the remaining time; resume continues from it', () => {
        const { timer } = host();
        timer.start(60);
        vi.advanceTimersByTime(10_000);
        timer.pause();
        vi.advanceTimersByTime(30_000);
        expect(timer.remaining.value).toBe(50);
        timer.start(60);
        vi.advanceTimersByTime(10_000);
        expect(timer.remaining.value).toBe(40);
        expect(timer.total.value).toBe(60);
    });

    it('reset clears it and unmount stops it', () => {
        const { timer, onFinish, wrapper } = host();
        timer.start(5);
        timer.reset();
        expect(timer.remaining.value).toBeNull();
        timer.start(5);
        wrapper.unmount();
        vi.advanceTimersByTime(10_000);
        expect(onFinish).not.toHaveBeenCalled();
    });
});

describe('formatTimer', () => {
    it('is mm:ss', () => {
        expect(formatTimer(0)).toBe('00:00');
        expect(formatTimer(605)).toBe('10:05');
    });
});
