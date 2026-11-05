import { onBeforeUnmount, ref, watch, type Ref } from 'vue';
import { createFrameResizeObserver, type FrameResizeObserver } from 'src/composables/frameResizeObserver';

/**
 * The px width a host gives `PriceHistoryChart`, which is sized in px rather
 * than by CSS (ECharts' `autoresize` did this before FU-833). Watches whatever
 * element `target` returns, so a host whose box appears late (a sheet opening,
 * a card leaving its empty state) is measured when it does, and stops
 * observing when it goes. One copy for the hosts that each wrote it (FU-847).
 *
 * `inset` is subtracted for padding inside the measured box; `min` floors the
 * result so a narrow phone still gets a readable chart.
 */
export function useMeasuredWidth(
    target: () => HTMLElement | null | undefined,
    options: { initial: number; min: number; inset?: number },
): Ref<number> {
    const width = ref(options.initial);
    let observer: FrameResizeObserver | null = null;

    function measure(): void {
        const el = target();
        if (!el) return;
        const next = Math.max(options.min, Math.floor(el.clientWidth) - (options.inset ?? 0));
        if (next !== width.value) width.value = next;
    }

    function stop(): void {
        observer?.disconnect();
        observer = null;
    }

    watch(target, (el) => {
        stop();
        if (!el || typeof ResizeObserver === 'undefined') return;
        measure();
        observer = createFrameResizeObserver(measure);
        observer.observe(el);
    }, { flush: 'post', immediate: true });

    onBeforeUnmount(stop);
    return width;
}
