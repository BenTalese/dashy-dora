<template>
    <span>{{ display }}</span>
</template>

<script lang="ts" setup>
    // Tweens its displayed value whenever `value` changes, so dashboard
    // stats count up/down instead of snapping. Honours prefers-reduced-motion
    // (jumps straight to the target) and falls back to an instant set if the
    // browser can't run rAF. Formatting is applied to the in-flight tweened
    // value so currency/counts read correctly at every frame.
    import { motionDurationMs } from 'src/composables/useMicroFeedback';
    import { computed, onBeforeUnmount, ref, watch } from 'vue';
    import { formatNumber } from 'src/composables/useMoney';

    const props = withDefaults(
        defineProps<{
            value: number;
            decimals?: number;
            /** Override the tween length. Leave unset to ride the motion
             *  tokens — see `duration` below. */
            durationMs?: number;
            prefix?: string;
            suffix?: string;
            /** Formatter for the tweened value — pass `formatMoney` for any
             *  money figure (D-006: one formatting authority).
             *
             *  Without this, a money caller had to reach for `prefix` +
             *  `decimals`, and every dashboard money site forgot `decimals`: the
             *  default of 0 meant `toFixed(0)`, so "You've saved $128.45"
             *  rendered as **"$128"** — rounded, no thousands separator, and with
             *  the symbol force-prefixed even in locales that suffix it (so
             *  "€12" where the rest of the app renders "12,34 €"). Worse, the
             *  savings card rendered its supporting line through `formatMoney`,
             *  so one card showed two formats for one currency (FU-821).
             *
             *  When supplied, this owns the whole string — `prefix`, `suffix` and
             *  `decimals` are ignored, because a real formatter already places
             *  the symbol and picks the precision. */
            format?: (value: number) => string;
        }>(),
        { decimals: 0, prefix: '', suffix: '' },
    );

    /* DR-15 / D-010 — "all animation reads --motion-* tokens, no literal ms".
       This is a JS tween rather than a CSS transition, but the rule is about
       the app having one set of durations, not about the mechanism: a
       hardcoded 600ms here is exactly the drift the tokens exist to prevent.
       A count-up is a *large surface* settle, so it takes --motion-slow, read
       at call time so the reduced-motion rewrite (~0ms) applies here too —
       which is also why the rAF path keeps its own prefers-reduced-motion
       shortcut below: at 0.01ms the tween would still run for one frame. */
    const duration = computed(() => props.durationMs ?? motionDurationMs('--motion-slow'));

    // Named `render`, not `format`: in `<script setup>` a top-level binding
    // shares the template namespace with the props, so a local `format` would
    // shadow the `format` prop (vue/no-dupe-keys).
    function render(n: number): string {
        if (props.format) return props.format(n);
        // D-006 — even the un-formatted path writes digits in the household locale.
        return props.prefix
            + formatNumber(n, { digits: props.decimals, minDigits: props.decimals })
            + props.suffix;
    }

    const current = ref(props.value);
    const display = ref(render(props.value));
    let frame: number | null = null;

    // Material's standard-decelerate curve: fast start, gentle settle.
    function easeOut(t: number): number {
        return 1 - Math.pow(1 - t, 3);
    }

    const prefersReduced =
        typeof window !== 'undefined' &&
        window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    function tweenTo(target: number): void {
        if (frame !== null) cancelAnimationFrame(frame);

        if (prefersReduced || typeof requestAnimationFrame === 'undefined') {
            current.value = target;
            display.value = render(target);
            return;
        }

        const from = current.value;
        const delta = target - from;
        const start = performance.now();

        const step = (now: number): void => {
            const t = Math.min(1, (now - start) / duration.value);
            const v = from + delta * easeOut(t);
            current.value = v;
            display.value = render(v);
            if (t < 1) {
                frame = requestAnimationFrame(step);
            } else {
                current.value = target;
                display.value = render(target);
                frame = null;
            }
        };

        frame = requestAnimationFrame(step);
    }

    watch(
        () => props.value,
        (v) => tweenTo(v),
    );

    onBeforeUnmount(() => {
        if (frame !== null) cancelAnimationFrame(frame);
    });
</script>
