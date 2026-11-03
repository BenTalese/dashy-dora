<template>
    <section class="scene" :aria-label="headline">
        <div class="scene-visual">
            <slot />
        </div>
        <div class="scene-copy">
            <p v-if="kicker" class="scene-kicker">{{ kicker }}</p>
            <h2 class="scene-headline">{{ headline }}</h2>
            <p v-if="sub" class="scene-sub">{{ sub }}</p>
        </div>
    </section>
</template>

<script lang="ts" setup>
    // Presentational full-bleed scene: a big hero visual (slot) + a kicker /
    // headline / sub copy block. The staggered rise-in plays on mount; the
    // parent cross-fades between scenes. Both collapse under reduced-motion.
    // `| undefined` (not just `?`) so callers can bind a possibly-undefined
    // value under exactOptionalPropertyTypes.
    defineProps<{
        kicker?: string | undefined;
        headline: string;
        sub?: string | undefined;
    }>();
</script>

<style scoped>
    .scene {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--space-6);
        text-align: center;
        width: 100%;
        max-width: 40rem;
        margin: 0 auto;
    }

    .scene-visual {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        animation: scene-rise var(--motion-slow) var(--motion-ease-out) both;
    }

    .scene-copy {
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
    }
    .scene-kicker {
        margin: 0;
        font-size: 0.95rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        color: var(--primary-ink);
        animation: scene-rise var(--motion-slow) var(--motion-ease-out) both;
        animation-delay: 80ms;
    }
    .scene-headline {
        margin: 0;
        font-family: 'Cute Dino', 'Nunito Variable', 'Nunito', sans-serif;
        font-size: clamp(1.9rem, 5.5vw, 2.7rem);
        font-weight: 400;
        line-height: 1.15;
        letter-spacing: 0;
        color: var(--text-primary);
        animation: scene-rise var(--motion-slow) var(--motion-ease-out) both;
        animation-delay: 160ms;
    }
    .scene-sub {
        margin: var(--space-2) auto 0;
        max-width: 32rem;
        font-size: 1.05rem;
        line-height: 1.5;
        color: var(--text-secondary);
        animation: scene-rise var(--motion-slow) var(--motion-ease-out) both;
        animation-delay: 260ms;
    }

    @keyframes scene-rise {
        from {
            opacity: 0;
            transform: translateY(var(--motion-slide-distance));
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* Reduced-motion: show the final state, no rise. (motion.scss also
       collapses the durations; this drops the translate + delays too.) */
    @media (prefers-reduced-motion: reduce) {
        .scene-visual,
        .scene-kicker,
        .scene-headline,
        .scene-sub {
            animation: none;
        }
    }
</style>
