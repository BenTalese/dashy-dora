<template>
    <router-link
        to="/"
        class="dora-brand row items-center no-wrap"
        aria-label="Dashy Dora home"
        @click="onBrandClick"
    >
        <q-avatar square size="44px" class="dora-brand-mascot">
            <img src="../../assets/logo-mascot.png" alt="" />
        </q-avatar>
        <span
            ref="textEl"
            class="dora-brand-text q-ml-sm"
            @animationend="onAnimationEnd"
        >Dashy Dora</span>
    </router-link>
</template>

<script setup lang="ts">
    import { ref } from 'vue';

    const textEl = ref<HTMLElement | null>(null);

    function onBrandClick() {
        const el = textEl.value;
        if (!el) return;
        // Re-trigger the CSS animations on every click. Toggling a Vue
        // reactive flag false → nextTick → true gets batched by the
        // browser, so a same-frame class flip doesn't actually restart
        // CSS animations. Drop the class, force a synchronous reflow
        // (reading offsetWidth flushes layout), then add it back — the
        // browser sees it as a genuine animation start. Reliable across
        // every click, not just the first.
        el.classList.remove('is-playing');
        void el.offsetWidth;
        el.classList.add('is-playing');
    }

    function onAnimationEnd(e: AnimationEvent) {
        // The colour wave is the longer of the two animations (0.75s
        // vs the pulse's 0.6s). When it finishes, peel the class off so
        // the text returns to its solid accent colour — otherwise the
        // gradient (now parked at its end position) would linger.
        if (e.animationName === 'dora-brand-wave') {
            textEl.value?.classList.remove('is-playing');
        }
    }
</script>

<style scoped lang="scss">
    .dora-brand {
        text-decoration: none;
        color: inherit;
        flex: 0 0 auto;
    }

    .dora-brand-mascot {
        transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
    }

    .dora-brand:hover .dora-brand-mascot {
        transform: rotate(-18deg) scale(1.12);
    }

    .dora-brand-text {
        font-family: 'Cute Dino', sans-serif;
        font-size: clamp(22px, 2.4vw, 30px);
        line-height: 1;
        white-space: nowrap;
        display: inline-block;
        transform-origin: center center;
        color: var(--brand-wordmark);
        cursor: pointer;
    }

    /* Mobile: mascot alone is the home affordance — hide the wordmark to
       reclaim toolbar space for the page title. Keeps the click target
       (whole router-link) intact. */
    @media (max-width: 1023px) {
        .dora-brand-text {
            display: none;
        }
    }

    /* On click: a clean grow-shrink pulse, plus a bright highlight that
       sweeps left → right through the letters via background-clip: text.
       The gradient sits on top of the text fill; we set
       `-webkit-text-fill-color: transparent` (and `color: transparent`)
       so the gradient shows through. */
    .dora-brand-text.is-playing {
        /* Wider, more contrasted highlight (round-5 feedback). Uses the
           dedicated `--nav-slide-flash` token — the same flash colour the
           main-menu indicator uses, picked per theme to pop hard against
           `--brand-accent`. The bright band spans 30→70% of the gradient
           (vs the prior tight 35→65%) so the eye has time to catch it. */
        background: linear-gradient(
            90deg,
            var(--brand-accent) 0%,
            var(--brand-accent) 25%,
            var(--nav-slide-flash) 50%,
            var(--brand-accent) 75%,
            var(--brand-accent) 100%
        );
        background-size: 300% 100%;
        background-clip: text;
        -webkit-background-clip: text;
        color: transparent;
        -webkit-text-fill-color: transparent;
        /* Slower so the sweep is legible — 1.2s wave, 0.6s pulse. */
        animation:
            dora-brand-pulse 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) both,
            dora-brand-wave 1.2s cubic-bezier(0.4, 0, 0.2, 1) both;
    }

    /* Pulse — pure grow/shrink, no rotation (round-4 feedback). */
    @keyframes dora-brand-pulse {
        0%   { transform: scale(1); }
        45%  { transform: scale(1.18); }
        100% { transform: scale(1); }
    }

    /* Colour wave — slide the gradient across so the bright stop sweeps
       through the text from left to right. */
    @keyframes dora-brand-wave {
        0%   { background-position: 140% 0; }
        100% { background-position: -40% 0; }
    }

    @media (prefers-reduced-motion: reduce) {
        .dora-brand-text.is-playing {
            animation: none;
        }
    }
</style>
