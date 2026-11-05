<template>
    <!--
        DoraTabs — themed tab strip with a sliding underline indicator that
        mirrors the main menu's accent slide. Same wobble + flash on switch,
        shrunk to the per-tab underline scale. Inactive tabs use the default
        text colour; the indicator does the colour work, so we deliberately
        do NOT use Quasar's per-tab `active-color` saturation.

        Round-7 feedback: the strip now scrolls *inside its own box* on
        narrow containers (mobile, splitter peek) so it never blows out
        the parent's width / pushes a horizontal page scroll. Active tab
        auto-scrolls into view after selection so the user always sees
        where they are.
    -->
    <div
        ref="stripEl"
        class="dora-tabs row no-wrap items-end"
        role="tablist"
    >
        <button
            v-for="t in tabs"
            :key="t.name"
            ref="tabEls"
            type="button"
            role="tab"
            class="dora-tabs__tab"
            :class="{ 'dora-tabs__tab--active': modelValue === t.name }"
            :aria-selected="modelValue === t.name"
            @click="onSelect(t.name)"
        >
            <q-icon v-if="t.icon" :name="t.icon" size="18px" class="dora-tabs__icon" />
            <span class="dora-tabs__label">{{ t.label }}</span>
        </button>
        <div
            class="dora-tabs__indicator"
            :class="{ 'is-ready': indicator.ready, 'is-sliding': indicator.sliding }"
            :style="indicatorStyle"
            @transitionend="onIndicatorTransitionEnd"
        />
    </div>
</template>

<script setup lang="ts">
    import { createFrameResizeObserver, type FrameResizeObserver } from 'src/composables/frameResizeObserver';
    import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';

    export interface DoraTab {
        name: string;
        label: string;
        icon?: string;
    }

    const props = defineProps<{
        modelValue: string;
        tabs: DoraTab[];
    }>();
    const emit = defineEmits<{ (e: 'update:modelValue', value: string): void }>();

    const stripEl = ref<HTMLElement | null>(null);
    const tabEls = ref<HTMLElement[]>([]);
    const indicator = reactive({ left: 0, width: 0, ready: false, sliding: false });

    const indicatorStyle = computed(() => ({
        translate: `${indicator.left}px 0`,
        width: `${indicator.width}px`,
    }));

    // Use `offsetLeft` / `offsetWidth` (relative to the offsetParent — the
    // strip, since it's `position: relative`) instead of viewport-relative
    // `getBoundingClientRect()`. That way the indicator's `translate`
    // tracks the active tab's *scroll-space* position; horizontally
    // scrolling the strip moves both together correctly.
    function measure() {
        const strip = stripEl.value;
        if (!strip) return;
        const active = strip.querySelector<HTMLElement>('.dora-tabs__tab--active');
        if (!active) {
            indicator.width = 0;
            indicator.ready = false;
            return;
        }
        indicator.left = active.offsetLeft;
        indicator.width = active.offsetWidth;
        indicator.ready = true;
    }

    // Bring the active tab into view after a switch — when the strip
    // overflows (mobile / narrow splitter peek) the user otherwise can't
    // see where they just landed.
    function scrollActiveIntoView() {
        const strip = stripEl.value;
        if (!strip) return;
        const active = strip.querySelector<HTMLElement>('.dora-tabs__tab--active');
        active?.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });
    }

    function onSelect(name: string) {
        if (name === props.modelValue) return;
        emit('update:modelValue', name);
    }

    let resizeObserver: FrameResizeObserver | null = null;

    onMounted(() => {
        void nextTick(measure);
        if (typeof ResizeObserver !== 'undefined' && stripEl.value) {
            resizeObserver = createFrameResizeObserver(measure);
            resizeObserver.observe(stripEl.value);
        }
        window.addEventListener('resize', measure);
    });

    onBeforeUnmount(() => {
        resizeObserver?.disconnect();
        window.removeEventListener('resize', measure);
    });

    watch(
        () => props.modelValue,
        () => {
            indicator.sliding = true;
            void nextTick(() => {
                measure();
                scrollActiveIntoView();
            });
        },
    );

    watch(
        () => props.tabs,
        () => void nextTick(measure),
        { deep: true },
    );

    function onIndicatorTransitionEnd(e: TransitionEvent) {
        if (e.propertyName === 'translate') indicator.sliding = false;
    }
</script>

<style scoped lang="scss">
    .dora-tabs {
        position: relative;
        gap: 4px;
        padding: 0 4px;
        border-bottom: 1px solid color-mix(in srgb, var(--text-primary) 8%, transparent);
        /* Round-7 feedback: contain horizontal overflow INSIDE the strip
           so a tab row wider than its parent (mobile, splitter peek) no
           longer pushes a page-level horizontal scroll. The strip
           scrolls itself; the scrollbar is hidden visually but kbd /
           swipe scroll still work. */
        overflow-x: auto;
        overflow-y: hidden;
        min-width: 0;
        max-width: 100%;
        scrollbar-width: none;             // Firefox
        -ms-overflow-style: none;          // legacy Edge
        scroll-behavior: smooth;
    }
    .dora-tabs::-webkit-scrollbar {
        display: none;                     // Chromium / Safari
    }

    .dora-tabs__tab {
        all: unset;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 10px 14px;
        min-height: 40px;
        cursor: pointer;
        color: var(--text-secondary);
        font-size: 0.875rem;
        font-weight: 600;
        letter-spacing: 0.1px;
        line-height: 1;
        position: relative;
        border-radius: 6px 6px 0 0;
        white-space: nowrap;
        flex: 0 0 auto;
        /* Match the main menu's posture (`MainMenuButton`) — colour
           transitions to accent on hover, no surface tint, same easing
           as the indicator slide so text + bar move together. */
        transition: color 0.42s cubic-bezier(0.65, 0, 0.2, 1);
    }
    // D-004 on touch (R-085 / FU-877): the 40px row is a desktop density.
    @media (pointer: coarse) {
        .dora-tabs__tab {
            min-height: 44px;
        }
    }

    /* --accent-ink, not the raw accent: the brand accent is a *fill*
       tone, and in every light family it lands at 1.3–2.0:1 as text — the
       stock-item detail tabs were the site the owner called out
       (2026-09-01). The ink token keeps the accent hue and clears D-002's
       4.5:1 floor on the whole light-surface ladder. */
    .dora-tabs__tab:not(.dora-tabs__tab--active):hover {
        color: var(--accent-ink);
    }

    .dora-tabs__tab--active {
        color: var(--accent-ink);
    }

    .dora-tabs__icon {
        flex: 0 0 auto;
    }

    .dora-tabs__label {
        white-space: nowrap;
    }

    /* Tighter chrome at narrow widths so more tabs fit before scroll
       kicks in. */
    @media (max-width: 599px) {
        .dora-tabs__tab {
            padding: 8px 10px;
            font-size: 0.8125rem;
        }
        .dora-tabs__icon {
            font-size: 16px;
        }
    }

    .dora-tabs__indicator {
        position: absolute;
        bottom: -1px;
        left: 0;
        height: 2px;
        border-radius: 2px;
        /* The bar is a graphic, not text, so it owes 3:1 rather than the
           label's 4.5:1 — that's `--accent-mark`, ~7 lightness points
           brighter than the ink the label above it takes (owner, 2026-09-03:
           the ink tone read as too dark for the *chrome*). The glow stays on
           the raw accent — it's a bloom, not the mark itself. */
        background: var(--accent-mark);
        box-shadow: 0 0 6px color-mix(in srgb, var(--brand-accent) 50%, transparent);
        opacity: 0;
        transition:
            translate 0.55s cubic-bezier(0.65, 0, 0.2, 1),
            width 0.55s cubic-bezier(0.65, 0, 0.2, 1),
            opacity 0.25s ease,
            background-color 0.3s ease,
            box-shadow 0.3s ease;
        pointer-events: none;
        will-change: translate, width, scale;
    }

    .dora-tabs__indicator.is-ready {
        opacity: 1;
    }

    .dora-tabs__indicator.is-sliding {
        background: var(--nav-slide-flash);
        box-shadow: 0 0 6px color-mix(in srgb, var(--nav-slide-flash) 55%, transparent);
        animation: dora-tabs-wobble 0.55s cubic-bezier(0.4, 0, 0.2, 1);
    }

    @keyframes dora-tabs-wobble {
        0%   { scale: 1 1; }
        25%  { scale: 1.18 1.4; }
        55%  { scale: 1.32 1.6; }
        80%  { scale: 1.0 1.1; }
        100% { scale: 1 1; }
    }
</style>
