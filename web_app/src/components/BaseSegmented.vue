<template>
    <div
        class="base-segmented"
        :class="{ 'base-segmented--dense': dense, 'base-segmented--spread': spread }"
        role="radiogroup"
        :aria-disabled="disabled || undefined"
        @keydown="onKeydown"
    >
        <button
            v-for="(opt, i) in options"
            :key="String(opt.value)"
            :ref="(el) => setOptRef(el, i)"
            type="button"
            role="radio"
            class="base-segmented__opt"
            :class="{ 'base-segmented__opt--active': isActive(opt.value) }"
            :aria-checked="isActive(opt.value)"
            :tabindex="i === tabStop ? 0 : -1"
            :disabled="isOptDisabled(opt)"
            @click="pick(opt.value)"
        >
            <q-icon v-if="opt.icon" :name="opt.icon" size="16px" class="base-segmented__icon" />
            <span v-if="opt.label" class="base-segmented__label">{{ opt.label }}</span>
        </button>
    </div>
</template>

<script setup lang="ts" generic="T extends string | number | boolean">
    /*
     * The app's single-select row of buttons (B2a / D-015): a pill-shaped
     * sunken track with the active segment as a brand-primary pill inside it.
     * The anatomy's values are the `--seg-*` tokens in tokens.scss.
     *
     * **One component since FU-848 (2026-11-04).** There used to be two: this
     * file was a `q-btn-toggle` wrapper, and `settings/DoraSegmented.vue` drew
     * the same anatomy as a hand-rolled radiogroup. They shared tokens, so they
     * couldn't drift on colour — but nothing stopped the next change landing on
     * one of them. The hand-rolled one survived, under this name, because it had
     * the better bones:
     *
     *   - real `radiogroup` / `radio` semantics (`aria-checked`), with a roving
     *     tabindex and arrow-key movement — the WAI-ARIA radio-group pattern. A
     *     `q-btn-toggle` is a row of independent `aria-pressed` buttons, one Tab
     *     stop each, with no arrow keys;
     *   - it wraps on desktop and scrolls sideways on a phone, which the
     *     five-option font-family picker needs;
     *   - none of the `!important` fight the q-btn-toggle version waged against
     *     Quasar's `.text-primary` utility to keep the active label readable
     *     (D-002) — the active ink is just `--seg-active-ink`, which measures
     *     ≥4.5:1 on `--seg-active-bg` in every theme.
     *
     * The Quasar props the old wrapper's consumers passed through `$attrs` are
     * mapped deliberately rather than left to go inert:
     *   - `dense` → the `dense` prop below (a compact 30px segment);
     *   - `spread` → the `spread` prop (segments share the full width);
     *   - `size` → retired. The old wrapper had to pin the label to
     *     `--font-size-sm` anyway because `size="sm"` rendered it at 10px
     *     (under D-003's floor), so `size` only ever changed padding — which is
     *     what `dense` says.
     *   - option `disable` (Quasar's spelling) is honoured alongside `disabled`.
     * `aria-label`, `class` and `style` fall through to the radiogroup root.
     */
    import type { ComponentPublicInstance } from 'vue';
    import { computed, onMounted, ref, useAttrs } from 'vue';

    export interface BaseSegmentedOption<V> {
        label?: string;
        value: V;
        icon?: string;
        disabled?: boolean;
        /** Quasar's spelling, accepted so option lists built for q-btn-toggle
         *  keep working. */
        disable?: boolean;
    }

    const props = defineProps<{
        modelValue: T;
        options: readonly BaseSegmentedOption<T>[];
        /** Disables the whole group. A *semantic* reason only — never a
         *  transient `saving` flag (D-019). */
        disabled?: boolean;
        /** Compact segments, for toolbars, card headers and filter panels. */
        dense?: boolean;
        /** Segments share the full width of the track. */
        spread?: boolean;
    }>();
    const emit = defineEmits<{ (e: 'update:modelValue', value: T): void }>();

    // A radiogroup with no name is announced as just "radio group" (FU-980).
    const attrs = useAttrs();
    onMounted(() => {
        if (import.meta.env.DEV && !attrs['aria-label'] && !attrs['aria-labelledby']) {
            console.warn('BaseSegmented: pass aria-label or aria-labelledby to name the group.');
        }
    });

    const optEls = ref<(HTMLButtonElement | null)[]>([]);
    function setOptRef(el: Element | ComponentPublicInstance | null, i: number) {
        optEls.value[i] = el instanceof HTMLButtonElement ? el : null;
    }

    function isActive(v: T): boolean {
        return props.modelValue === v;
    }

    function isOptDisabled(opt: BaseSegmentedOption<T>): boolean {
        return Boolean(props.disabled || opt.disabled || opt.disable);
    }

    /** The one option reachable by Tab: the selected one, or the first enabled
     *  option when nothing (or a disabled option) is selected. */
    const tabStop = computed(() => {
        const active = props.options.findIndex((o) => isActive(o.value) && !isOptDisabled(o));
        if (active >= 0) return active;
        return props.options.findIndex((o) => !isOptDisabled(o));
    });

    function pick(v: T): void {
        if (v === props.modelValue) return;
        emit('update:modelValue', v);
    }

    /** Arrow keys move *and* select, as a native radio group does. Disabled
     *  options are skipped; the ends wrap. */
    function onKeydown(e: KeyboardEvent): void {
        const n = props.options.length;
        if (n === 0 || props.disabled) return;
        let step: 1 | -1;
        let from = tabStop.value;
        switch (e.key) {
            case 'ArrowRight':
            case 'ArrowDown':
                step = 1;
                break;
            case 'ArrowLeft':
            case 'ArrowUp':
                step = -1;
                break;
            case 'Home':
                step = 1;
                from = -1;
                break;
            case 'End':
                step = -1;
                from = n;
                break;
            default:
                return;
        }
        e.preventDefault();
        for (let k = 1; k <= n; k++) {
            const i = (((from + step * k) % n) + n) % n;
            const opt = props.options[i];
            if (opt && !isOptDisabled(opt)) {
                pick(opt.value);
                optEls.value[i]?.focus();
                return;
            }
        }
    }
</script>

<style scoped lang="scss">
    .base-segmented {
        display: inline-flex;
        flex-wrap: wrap;
        align-items: stretch;
        gap: var(--seg-track-pad);
        padding: var(--seg-track-pad);
        border: 1px solid var(--seg-track-border);
        border-radius: var(--seg-radius);
        background: var(--seg-track-bg);
        max-width: 100%;
    }
    .base-segmented__opt {
        all: unset;
        box-sizing: border-box;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        padding: 8px 14px;
        min-height: 36px;
        border-radius: var(--seg-radius);
        cursor: pointer;
        color: var(--seg-ink);
        /* D-003: interactive labels are 14px. */
        font-size: var(--font-size-sm);
        font-weight: 500;
        line-height: 1;
        white-space: nowrap;
        transition: color 0.18s ease, background-color 0.18s ease, font-weight 0s;
    }
    /* Horizontal padding stays close to the old dense q-btn's (~4px): a
       card header holding three dense segments has to fit a 375px phone. */
    .base-segmented--dense .base-segmented__opt {
        padding: 4px 10px;
        min-height: 30px;
    }
    .base-segmented--spread {
        display: flex;
        width: 100%;
    }
    .base-segmented--spread .base-segmented__opt {
        flex: 1 1 0;
        min-width: 0;
    }
    /* A pointer that can hover — a tapped segment on a phone would otherwise
       keep the hover tint until the next tap elsewhere (R-085). */
    @media (hover: hover) {
        .base-segmented__opt:not(.base-segmented__opt--active):not([disabled]):hover {
            color: var(--seg-ink-hover);
        }
    }
    .base-segmented__opt:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 1px;
    }
    .base-segmented__opt--active {
        background: var(--seg-active-bg);
        color: var(--seg-active-ink);
        font-weight: 600;
    }
    .base-segmented__opt[disabled] {
        opacity: 0.5;
        cursor: not-allowed;
    }
    .base-segmented__icon { flex: 0 0 auto; }
    .base-segmented__label {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* Width question ("does it fit?"): on a narrow layout the row scrolls
       sideways inside its own track rather than wrapping into a ragged
       second line (D-011). A spread row never needs to — its segments
       shrink instead. */
    @media (max-width: 599px) {
        .base-segmented:not(.base-segmented--spread) {
            overflow-x: auto;
            scrollbar-width: none;
            flex-wrap: nowrap;
        }
        .base-segmented::-webkit-scrollbar { display: none; }
    }

    /* Finger question (R-085): D-004's 44px floor on a coarse pointer, dense or
       not — the same lift `BaseButton` gets, so a segmented control stays level
       with the buttons beside it. A mouse keeps the compact sizes above.
       (Not a hit-area pseudo-element: the phone-width track scrolls, and an
       overflow container would clip — and scroll — anything drawn outside it.) */
    @media (pointer: coarse) {
        .base-segmented__opt,
        .base-segmented--dense .base-segmented__opt {
            min-height: 44px;
        }
    }
</style>
