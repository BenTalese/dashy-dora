<template>
    <div
        class="loop"
        :class="{ 'loop--revealing': !nodesShown }"
        role="group"
        :aria-label="`The Dora loop: ${stageLabels}, with Dora at the centre`"
    >
        <!-- The ring + nodes. Square, scales with width; nodes sit on the ring. -->
        <div class="loop-ring">
            <svg class="loop-ring-line" viewBox="0 0 100 100" aria-hidden="true">
                <circle
                    class="loop-ring-circle"
                    :class="{ 'is-drawing': shouldAnimate }"
                    cx="50"
                    cy="50"
                    r="38"
                    pathLength="1"
                />
            </svg>

            <!-- Stage nodes -->
            <button
                v-for="(stage, i) in LOOP_STAGES"
                :key="stage.key"
                type="button"
                class="loop-node"
                :class="{ 'is-shown': nodesShown, 'is-active': focusedKey === stage.key }"
                :style="nodeStyle(i)"
                :aria-pressed="focusedKey === stage.key"
                :aria-label="`${stage.label}. ${stage.sell}`"
                @click="focus(stage.key)"
            >
                <q-icon :name="stage.icon" class="loop-node-icon" />
                <span class="loop-node-label">{{ stage.label }}</span>
            </button>

            <!-- Dora at the centre -->
            <div class="loop-centre" :class="{ 'is-shown': nodesShown }">
                <button
                    type="button"
                    class="loop-dora"
                    :class="{ 'is-active': focusedKey === 'centre' }"
                        :aria-pressed="focusedKey === 'centre'"
                    :aria-label="`${LOOP_CENTRE.label}. ${LOOP_CENTRE.sell}`"
                    @click="focus('centre')"
                >
                    <DoraMascot :mood="doraMood" :size="96" />
                </button>
            </div>
        </div>

        <!-- Detail panel — what the focused stage does. Announced politely.
             Node/centre labels are already on the buttons themselves, so the
             detail block only shows the sell sentence and cross-fades between
             selections. Owner 2026-10-17: no "click or tap" hint before the
             first pick, but the panel keeps a fixed height (sized for the
             longest sell) so the loop doesn't jump when the first one lands. -->
        <div class="loop-detail" role="status" aria-live="polite">
            <transition name="loop-detail-swap" mode="out-in">
                <p
                    v-if="focusedKey"
                    :key="focusedKey"
                    class="loop-detail-body"
                >{{ detail.body }}</p>
            </transition>
        </div>
    </div>
</template>

<script lang="ts" setup>
    import DoraMascot from 'src/components/dora/DoraMascot.vue';
    import type { DoraMood } from 'src/components/dora/doraTypes';
    import { useReducedMotion } from 'src/composables/useReducedMotion';
    import {
        LOOP_CENTRE,
        LOOP_STAGES,
        type LoopStageKey,
    } from 'src/pages/onboarding/onboardingContent';
    import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

    // The story is the only consumer and always animates + lets you tap
    // (the `autoplay` / `interactive` props and the Finish-step recap that
    // passed them went in finalisation 14-R13).
    const prefersReducedMotion = useReducedMotion();

    // Animate unless the user asked for less motion. Otherwise we jump
    // straight to the final, fully-revealed state.
    const shouldAnimate = computed(() => !prefersReducedMotion.value);

    const nodesShown = ref(!shouldAnimate.value);
    const focusedKey = ref<LoopStageKey | 'centre' | null>(null);

    const stageLabels = computed(() => LOOP_STAGES.map((s) => s.label).join(' → '));

    const doraMood: DoraMood = 'happy';

    // Place each stage node on the ring: start at top (−90°), step clockwise.
    const RING_RADIUS = 38; // % offset from centre — matches the SVG circle r.
    function nodeStyle(index: number) {
        const angle = (-90 + index * (360 / LOOP_STAGES.length)) * (Math.PI / 180);
        const left = 50 + RING_RADIUS * Math.cos(angle);
        const top = 50 + RING_RADIUS * Math.sin(angle);
        return {
            left: `${left}%`,
            top: `${top}%`,
            // Stagger the cascade-in once the ring has drawn.
            transitionDelay: nodesShown.value ? '0ms' : `${index * 90}ms`,
        };
    }

    const detail = computed(() => {
        const key = focusedKey.value;
        if (key === 'centre') {
            // The acronym reveal ("D.O.R.A. — …") lives inside the sentence
            // itself (LOOP_CENTRE.sell) rather than as a separate title;
            // the button already tells the user which node they clicked.
            return { body: LOOP_CENTRE.sell };
        }
        const stage = LOOP_STAGES.find((s) => s.key === key);
        return { body: stage?.sell ?? '' };
    });

    function focus(key: LoopStageKey | 'centre') {
        focusedKey.value = key;
    }

    // Reveal choreography: the ring draws, then the nodes cascade in.
    const RING_DRAW_MS = 900;
    let nodeTimer: ReturnType<typeof setTimeout> | null = null;

    onMounted(() => {
        if (!shouldAnimate.value) return;
        nodeTimer = setTimeout(() => {
            nodesShown.value = true;
        }, RING_DRAW_MS);
    });

    onBeforeUnmount(() => {
        if (nodeTimer !== null) clearTimeout(nodeTimer);
    });
</script>

<style scoped>
    .loop {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--space-5);
        width: 100%;
    }

    /* ── Ring + nodes ──────────────────────────────────────────────── */
    .loop-ring {
        position: relative;
        width: clamp(280px, 72vw, 440px);
        aspect-ratio: 1;
    }

    .loop-ring-line {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        overflow: visible;
    }
    .loop-ring-circle {
        fill: none;
        stroke: var(--brand-accent);
        stroke-width: 0.7;
        opacity: 0.55;
    }
    .loop-ring-circle.is-drawing {
        stroke-dasharray: 1;
        stroke-dashoffset: 1;
        animation: ring-draw var(--motion-slow) var(--motion-ease-out) forwards;
        /* Start the draw after a beat so it reads as deliberate. */
        animation-delay: 120ms;
    }
    @keyframes ring-draw {
        to {
            stroke-dashoffset: 0;
        }
    }

    .loop-node {
        position: absolute;
        transform: translate(-50%, -50%) scale(var(--motion-scale-from));
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        width: 76px;
        padding: var(--space-2) var(--space-1);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        background: var(--surface-component);
        color: var(--text-secondary);
        cursor: pointer;
        opacity: 0;
        transition: opacity var(--motion-normal) var(--motion-ease-out),
            transform var(--motion-normal) var(--motion-ease-spring),
            background var(--motion-fast) var(--motion-ease),
            border-color var(--motion-fast) var(--motion-ease),
            color var(--motion-fast) var(--motion-ease),
            box-shadow var(--motion-fast) var(--motion-ease);
    }
    .loop-node.is-shown {
        opacity: 1;
        transform: translate(-50%, -50%) scale(1);
    }
    .loop-node:hover:not(:disabled),
    .loop-node:focus-visible {
        border-color: var(--brand-primary);
        color: var(--text-primary);
        transform: translate(-50%, -50%) scale(1.05);
    }
    .loop-node:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    /* Active node: filled brand-primary background with contrasting text,
       a soft accent halo, and a lift. The scale bump is deliberate so the
       swap between nodes reads as a smooth flow, not a colour flicker. */
    .loop-node.is-active {
        background: var(--brand-primary);
        border-color: var(--brand-primary);
        color: var(--surface-component);
        transform: translate(-50%, -50%) scale(1.12);
        box-shadow: 0 0 0 4px var(--brand-accent-soft),
            0 10px 24px var(--overlay-active);
        z-index: 1;
    }
    .loop-node.is-active .loop-node-icon {
        color: var(--surface-component);
    }
    .loop-node-icon {
        font-size: 22px;
        color: var(--brand-primary);
        transition: color var(--motion-fast) var(--motion-ease);
    }
    .loop-node-label {
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }

    /* ── Centre: Dora ─────────────────────────────────────────────────── */
    .loop-centre {
        position: absolute;
        left: 50%;
        top: 50%;
        transform: translate(-50%, -50%);
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--space-2);
        opacity: 0;
        transition: opacity var(--motion-slow) var(--motion-ease-out);
    }
    .loop-centre.is-shown {
        opacity: 1;
    }
    .loop-dora {
        border: none;
        background: transparent;
        padding: var(--space-1);
        border-radius: var(--radius-full);
        cursor: pointer;
        line-height: 0;
        transition: box-shadow var(--motion-fast) var(--motion-ease),
            transform var(--motion-normal) var(--motion-ease-spring);
    }
    .loop-dora:hover:not(:disabled) {
        transform: scale(1.06);
    }
    .loop-dora:focus-visible {
        outline: none;
        box-shadow: 0 0 0 3px var(--brand-accent-soft);
    }
    .loop-dora.is-active {
        box-shadow: 0 0 0 5px var(--brand-accent-soft),
            0 10px 28px var(--overlay-active);
        transform: scale(1.08);
    }
    /* ── Detail panel ──────────────────────────────────────────────── */
    .loop-detail {
        /* Three lines of `.loop-detail-body` — the longest sell wraps to
           three on a phone — so an empty panel reserves the same space. */
        min-height: calc(3 * 1.05rem * 1.45);
        max-width: 30rem;
        text-align: center;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .loop-detail-body {
        margin: 0;
        font-size: 1.05rem;
        line-height: 1.45;
        color: var(--text-primary);
    }

    /* Sleek out-in cross-fade when the focused node changes. */
    .loop-detail-swap-enter-active {
        transition:
            opacity var(--motion-normal) var(--motion-ease-out),
            transform var(--motion-normal) var(--motion-ease-spring);
    }
    .loop-detail-swap-leave-active {
        transition:
            opacity var(--motion-fast) var(--motion-ease-in),
            transform var(--motion-fast) var(--motion-ease-in);
    }
    .loop-detail-swap-enter-from {
        opacity: 0;
        transform: translateY(6px);
    }
    .loop-detail-swap-leave-to {
        opacity: 0;
        transform: translateY(-6px);
    }
</style>
