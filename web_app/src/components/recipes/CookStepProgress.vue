<template>
    <!--
        Cook-mode position indicator. Owner feedback 2026-08-28: *"Step
        indicator is a bit boring (styling). 'Step 1 of 6' in tiny boring text.
        Could be stylish/cool/fancy and in-line with the progress bar."*

        So the count and the bar are one object rather than a `text-caption`
        line floating above a `q-linear-progress`: a tinted badge carrying the
        number at display size, and a track beside it. Extracted rather than
        inlined because both cook-mode faces need it (R-001) — the step view
        counts steps, the image view counts photos — and they should read
        identically.

        The track is segmented when the count is small enough for segments to
        be legible, and falls back to a single fill bar past that.

        Owner feedback 2026-09-01: *"Can we make the progress bar clickable now
        that we are visually showing gaps and not one continuous line? Also
        with a nice hover effect? Allows people to quickly jump instead of
        going one by one."* So the segments are buttons when — and only when —
        the parent asks for it and the track is segmented: a
        continuous fill has no discrete target to aim at, and offering to
        scrub it would be a lie about the precision on offer. Each segment is
        44px tall in its hit area even though it paints at 10–16px (D-004), via
        a transparent pad rather than a taller bar, so the control stays the
        thin line the owner asked for and is still reachable with a floury
        finger.
    -->
    <div class="cook-progress">
        <div class="cook-progress__badge">
            <span class="cook-progress__word">{{ noun }}</span>
            <span class="cook-progress__current">{{ current + 1 }}</span>
            <span class="cook-progress__total">of {{ total }}</span>
        </div>
        <div
            class="cook-progress__track"
            :class="{ 'cook-progress__track--continuous': !segmented }"
            role="progressbar"
            :aria-label="`${noun} ${current + 1} of ${total}`"
            :aria-valuenow="current + 1"
            aria-valuemin="1"
            :aria-valuemax="total"
        >
            <template v-if="segmented">
                <component
                    :is="interactive ? 'button' : 'span'"
                    v-for="position in total"
                    :key="position"
                    class="cook-progress__segment"
                    :class="{
                        'cook-progress__segment--done': position < current + 1,
                        'cook-progress__segment--current': position === current + 1,
                        'cook-progress__segment--clickable': interactive,
                    }"
                    v-bind="interactive ? {
                        type: 'button',
                        'aria-label': `Go to ${nounLower} ${position}`,
                        'aria-current': position === current + 1 ? 'step' : undefined,
                    } : {}"
                    @click="interactive ? emit('select', position - 1) : undefined"
                >
                    <span class="cook-progress__bar" />
                </component>
            </template>
            <span v-else class="cook-progress__fill" :style="{ width: fillWidth }" />
        </div>
    </div>
</template>

<script setup lang="ts">
    import { computed } from 'vue';

    const props = withDefaults(
        defineProps<{
            /** Zero-based position of the step/photo being shown. */
            current: number;
            total: number;
            /** Displayed word for one unit of progress ("Step", "Photo"). */
            noun?: string;
            /** Whether the segments are jump targets. Off by default: the
             *  image face's gallery scrolls, so there is nothing to jump *to*,
             *  and it should not grow a row of dead buttons because it shares
             *  this component. Ignored on the continuous track — a fill bar
             *  has no discrete target to aim at. */
            jumpable?: boolean;
        }>(),
        { noun: 'Step', jumpable: false },
    );

    const emit = defineEmits<{
        /** Zero-based index of the segment the reader tapped. Only fired when
         *  a parent is listening — see `interactive`. */
        (e: 'select', index: number): void;
    }>();

    /** `withDefaults` guarantees a value, but the optional prop still types as
     *  `string | undefined` in the template. */
    const nounLower = computed(() => props.noun.toLowerCase());

    const interactive = computed(() => segmented.value && props.jumpable);

    /** Past this many, individual segments are thinner than the gaps between
     *  them and read as noise; one continuous fill is honest at any length. */
    const SEGMENT_LIMIT = 14;

    const segmented = computed(() => props.total > 0 && props.total <= SEGMENT_LIMIT);

    const fillWidth = computed(() => {
        if (props.total <= 0) return '0%';
        const fraction = (props.current + 1) / props.total;
        return `${Math.max(0, Math.min(1, fraction)) * 100}%`;
    });
</script>

<style scoped lang="scss">
    .cook-progress {
        display: flex;
        align-items: center;
        gap: var(--space-4);
    }
    .cook-progress__badge {
        display: flex;
        align-items: baseline;
        gap: var(--space-2);
        flex: 0 0 auto;
        padding: var(--space-2) var(--space-4);
        border-radius: var(--radius-lg);
        border: 1px solid color-mix(in srgb, var(--brand-primary) 35%, transparent);
        background: color-mix(in srgb, var(--brand-primary) 12%, transparent);
        white-space: nowrap;
    }
    .cook-progress__word {
        font-size: var(--font-size-xs);
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--text-secondary);
    }
    .cook-progress__current {
        font-size: var(--font-size-2xl);
        font-weight: 700;
        line-height: 1;
        color: var(--brand-primary);
        font-variant-numeric: tabular-nums;
    }
    .cook-progress__total {
        font-size: var(--font-size-sm);
        font-weight: 500;
        color: var(--text-secondary);
        font-variant-numeric: tabular-nums;
    }
    .cook-progress__track {
        display: flex;
        align-items: center;
        gap: 4px;
        flex: 1 1 auto;
        min-width: 0;
    }
    /* The continuous face keeps its own height; only the segmented face grows
       hit targets around its bars. */
    .cook-progress__track--continuous {
        min-height: 10px;
    }
    /* The segment is a transparent 44px-tall hit target (D-004); the visible
       10–16px track is `__bar` inside it. Painting the bar itself at 44px was
       the alternative and it is not the control the owner asked for. */
    .cook-progress__segment {
        flex: 1 1 0;
        display: flex;
        align-items: center;
        min-height: 44px;
        padding: 0;
        border: 0;
        background: none;
        appearance: none;
        color: inherit;
        font: inherit;
    }
    .cook-progress__bar {
        display: block;
        width: 100%;
        height: 10px;
        border-radius: var(--radius-sm);
        background: var(--surface-sunken);
        border: 1px solid var(--border-default);
        transition:
            background-color var(--motion-normal) var(--motion-ease),
            height var(--motion-normal) var(--motion-ease),
            box-shadow var(--motion-normal) var(--motion-ease);
    }
    .cook-progress__segment--done .cook-progress__bar {
        background: color-mix(in srgb, var(--brand-primary) 45%, transparent);
        border-color: transparent;
    }
    /* The one segment the cook is standing on: full-strength, taller than its
       neighbours, and ringed — findable at arm's length across a kitchen. */
    .cook-progress__segment--current .cook-progress__bar {
        background: var(--brand-primary);
        border-color: var(--brand-primary);
        height: 16px;
        box-shadow: 0 0 0 3px color-mix(in srgb, var(--brand-primary) 20%, transparent);
    }
    .cook-progress__segment--clickable {
        cursor: pointer;
    }
    /* Hover/focus grows the bar toward the current segment's height and warms
       it — the target reads as reachable before you commit to the tap. Focus
       gets the ring as well, so keyboard and pointer land on the same
       affordance. */
    .cook-progress__segment--clickable:hover .cook-progress__bar {
        height: 16px;
        background: color-mix(in srgb, var(--brand-primary) 65%, transparent);
        border-color: transparent;
    }
    .cook-progress__segment--clickable:focus-visible {
        outline: none;
    }
    .cook-progress__segment--clickable:focus-visible .cook-progress__bar {
        height: 16px;
        box-shadow: 0 0 0 3px var(--focus-ring, color-mix(in srgb, var(--brand-primary) 45%, transparent));
    }
    @media (prefers-reduced-motion: reduce) {
        .cook-progress__bar { transition: none; }
    }
    .cook-progress__track--continuous {
        position: relative;
        height: 10px;
        border-radius: var(--radius-lg);
        background: var(--surface-sunken);
        border: 1px solid var(--border-default);
        overflow: hidden;
    }
    .cook-progress__fill {
        position: absolute;
        inset: 0 auto 0 0;
        background: var(--brand-primary);
        border-radius: inherit;
        transition: width var(--motion-normal) var(--motion-ease);
    }
    @media (max-width: 599px) {
        .cook-progress {
            gap: var(--space-3);
        }
        .cook-progress__badge {
            padding: var(--space-1) var(--space-3);
        }
        .cook-progress__current {
            font-size: var(--font-size-xl);
        }
    }
</style>
