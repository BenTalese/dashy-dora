import { computed, nextTick, onBeforeUnmount, ref, watch, type Ref } from 'vue';

/** How far each list had grown, by key, so coming back to a page renders as
 *  much as it had and the router's saved scroll position lands where it was.
 *  Session-scoped, like the list's own nav-state (R-026). */
const shownByKey = new Map<string, number>();

/**
 * Renders a long list a chunk at a time: the first `chunk` items, then the
 * next chunk each time a sentinel placed after the list comes within
 * `rootMargin` of the viewport. Items can be any height and the layout any
 * shape (a responsive card grid), and it never touches the scroll position.
 *
 * `reset` re-starts at one chunk; call it when the list's *meaning* changes
 * (a search, a filter, a sort), not when an item in it updates, or a
 * scrolled-down reader loses their place.
 */
export function useIncrementalRender<T>(options: {
    items: Ref<T[]>;
    key: string;
    chunk?: number;
    rootMargin?: string;
}) {
    const chunk = options.chunk ?? 24;
    const shown = ref(shownByKey.get(options.key) ?? chunk);
    watch(shown, (n) => shownByKey.set(options.key, n));

    const visible = computed(() => options.items.value.slice(0, shown.value));
    const hasMore = computed(() => shown.value < options.items.value.length);

    const sentinel = ref<HTMLElement | null>(null);
    // An observer only reports changes, so a sentinel that is still in range
    // after a chunk renders (a tall screen) is re-observed to be asked again.
    const observer = new IntersectionObserver(
        (entries) => {
            if (!entries.some((e) => e.isIntersecting) || !hasMore.value) return;
            shown.value += chunk;
            void nextTick(() => {
                const el = sentinel.value;
                if (!el) return;
                observer.unobserve(el);
                observer.observe(el);
            });
        },
        { rootMargin: options.rootMargin ?? '800px 0px' },
    );
    watch(
        sentinel,
        (el, previous) => {
            if (previous) observer.unobserve(previous);
            if (el) observer.observe(el);
        },
        { immediate: true },
    );
    onBeforeUnmount(() => observer.disconnect());

    function reset(): void {
        shown.value = chunk;
    }

    return { visible, hasMore, sentinel, reset };
}
