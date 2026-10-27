<template>
    <div v-if="!prefersReducedMotion" class="confetti" aria-hidden="true">
        <span
            v-for="piece in pieces"
            :key="piece.id"
            class="confetti-piece"
            :style="piece.style"
        />
    </div>
</template>

<script lang="ts" setup>
    // A one-shot confetti burst for the onboarding finish (C-5.6). Pieces are
    // placed deterministically (no Math.random) so it's stable, and the whole
    // thing is suppressed under prefers-reduced-motion. Mount it (v-if) when
    // the finish step is reached so the animation plays fresh each time.
    import { useReducedMotion } from 'src/composables/useReducedMotion';

    const prefersReducedMotion = useReducedMotion();

    const COLORS = [
        'var(--brand-primary)',
        'var(--brand-accent)',
        'var(--brand-secondary)',
        'var(--semantic-info)',
    ];
    const COUNT = 40;

    const pieces = Array.from({ length: COUNT }, (_, i) => ({
        id: i,
        style: {
            left: `${(i * 97) % 100}%`,
            backgroundColor: COLORS[i % COLORS.length] as string,
            animationDelay: `${(i % 12) * 45}ms`,
            animationDuration: `${1400 + (i % 6) * 240}ms`,
        },
    }));
</script>

<style scoped>
    .confetti {
        position: absolute;
        inset: 0;
        overflow: hidden;
        pointer-events: none;
        z-index: 1;
    }
    .confetti-piece {
        position: absolute;
        top: -16px;
        width: 8px;
        height: 13px;
        border-radius: 2px;
        opacity: 0;
        animation-name: confetti-fall;
        animation-timing-function: var(--motion-ease-in, cubic-bezier(0.4, 0, 1, 1));
        animation-iteration-count: 1;
        animation-fill-mode: forwards;
    }
    @keyframes confetti-fall {
        0% {
            opacity: 0;
            transform: translateY(0) rotate(0deg);
        }
        12% {
            opacity: 1;
        }
        100% {
            opacity: 0;
            transform: translateY(420px) rotate(540deg);
        }
    }
    @media (prefers-reduced-motion: reduce) {
        .confetti {
            display: none;
        }
    }
</style>
