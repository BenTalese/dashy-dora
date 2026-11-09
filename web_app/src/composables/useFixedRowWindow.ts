import { computed, onBeforeUnmount, ref, watch, type Ref } from 'vue';

/**
 * Windowed rendering for a scrolling list whose rows all share one height.
 *
 * Only the rows in view (plus `overscan` either side) are mounted; two spacers
 * stand in for the rest. It reads the scroller's position and never writes it.
 * That is the point of it over `QVirtualScroll`, which re-applies the scroll
 * position a frame after every slice change: during a phone fling that lands
 * behind the finger and kills the momentum, the snap of FU-991.
 *
 * Because the arithmetic is exact, every row must render at exactly
 * `rowHeight` (gap included).
 */
export function useFixedRowWindow(options: {
    scroller: Ref<HTMLElement | null>;
    count: Ref<number>;
    rowHeight: Ref<number>;
    overscan?: number;
}) {
    const overscan = options.overscan ?? 8;
    const scrollTop = ref(0);
    const viewHeight = ref(0);

    let frame = 0;
    function read() {
        frame = 0;
        const el = options.scroller.value;
        if (!el) return;
        scrollTop.value = el.scrollTop;
        viewHeight.value = el.clientHeight;
    }
    function onScroll() {
        if (frame === 0) frame = requestAnimationFrame(read);
    }

    const resize = new ResizeObserver(read);
    watch(
        options.scroller,
        (el, previous) => {
            previous?.removeEventListener('scroll', onScroll);
            if (previous) resize.unobserve(previous);
            if (!el) return;
            el.addEventListener('scroll', onScroll, { passive: true });
            resize.observe(el);
            read();
        },
        { immediate: true },
    );
    onBeforeUnmount(() => {
        options.scroller.value?.removeEventListener('scroll', onScroll);
        resize.disconnect();
        if (frame !== 0) cancelAnimationFrame(frame);
    });

    const start = computed(() => {
        const first = Math.floor(scrollTop.value / options.rowHeight.value) - overscan;
        return Math.max(0, Math.min(first, options.count.value));
    });
    const end = computed(() => {
        const last = Math.ceil((scrollTop.value + viewHeight.value) / options.rowHeight.value) + overscan;
        return Math.max(start.value, Math.min(last, options.count.value));
    });
    const padTop = computed(() => start.value * options.rowHeight.value);
    const padBottom = computed(() => (options.count.value - end.value) * options.rowHeight.value);

    return { start, end, padTop, padBottom };
}
