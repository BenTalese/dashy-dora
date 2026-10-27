<template>
    <div class="dora-segmented" role="radiogroup">
        <button
            v-for="opt in options"
            :key="String(opt.value)"
            type="button"
            role="radio"
            class="dora-segmented__opt"
            :class="{ 'dora-segmented__opt--active': isActive(opt.value) }"
            :aria-checked="isActive(opt.value)"
            :disabled="disabled || opt.disabled"
            @click="onPick(opt.value)"
        >
            <q-icon v-if="opt.icon" :name="opt.icon" size="16px" class="dora-segmented__icon" />
            <span class="dora-segmented__label">{{ opt.label }}</span>
        </button>
    </div>
</template>

<script setup lang="ts" generic="T extends string | number | boolean">
    // The settings pages' single-select control: the same anatomy as
    // `BaseSegmented`, drawn as a hand-rolled radiogroup rather than a
    // q-btn-toggle. Originally IMPL_PLAN_SETTINGS_REBUILD §2.6 + §6.1, whose
    // user pick was a *soft sunken* fill on the active segment — explicitly
    // "no saturated green block".
    //
    // **That pick was reversed on 2026-09-03** by the owner, who asked for
    // theme mode / font family / text size (and the admin settings controls
    // beside them) to be "styled like recipe view's step style picker" — i.e.
    // the brand-primary pill. The soft fill was the right call when settings
    // was the only surface with a hand-rolled segmented control; it stopped
    // being right once the same control appeared on eight other surfaces
    // wearing a different face. Newer instruction wins, and the anatomy now
    // comes from the shared `--seg-*` tokens in tokens.scss so this component
    // and BaseSegmented cannot drift apart again (D-015).
    //
    // Why two components still: this one keeps proper `radiogroup`/`radio`
    // semantics, wraps on desktop and scrolls horizontally on phones — which
    // the five-option font-family picker needs and q-btn-toggle doesn't do.
    // Merging the two is FU-848.
    export interface DoraSegmentedOption<V> {
        label: string;
        value: V;
        icon?: string;
        disabled?: boolean;
    }

    const props = defineProps<{
        modelValue: T;
        options: DoraSegmentedOption<T>[];
        disabled?: boolean;
    }>();
    const emit = defineEmits<{ (e: 'update:modelValue', value: T): void }>();

    function isActive(v: T): boolean {
        return props.modelValue === v;
    }

    function onPick(v: T): void {
        if (v === props.modelValue) return;
        emit('update:modelValue', v);
    }
</script>

<style scoped lang="scss">
    /* Anatomy from the shared --seg-* tokens (tokens.scss) — a pill-shaped
       sunken track with the active segment as a brand-primary pill. */
    .dora-segmented {
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
    .dora-segmented__opt {
        all: unset;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        padding: 8px 14px;
        /* D-004: a settings control is a tap target, and 32px was under the
           44px floor on a phone. The extra height comes off the track rather
           than the label so the pill still reads as compact. */
        min-height: 36px;
        border-radius: var(--seg-radius);
        cursor: pointer;
        color: var(--seg-ink);
        /* D-003: interactive labels are 14px, not the 13px this had. */
        font-size: var(--font-size-sm);
        font-weight: 500;
        line-height: 1;
        white-space: nowrap;
        transition: color 0.18s ease, background-color 0.18s ease, font-weight 0s;
    }
    .dora-segmented__opt:not(.dora-segmented__opt--active):hover {
        color: var(--seg-ink-hover);
    }
    .dora-segmented__opt:focus-visible {
        outline: 2px solid var(--ring-focus);
        outline-offset: 1px;
    }
    .dora-segmented__opt--active {
        background: var(--seg-active-bg);
        color: var(--seg-active-ink);
        font-weight: 600;
    }
    .dora-segmented__opt[disabled] {
        opacity: 0.5;
        cursor: not-allowed;
    }
    .dora-segmented__icon { flex: 0 0 auto; }
    .dora-segmented__label { white-space: nowrap; }

    @media (max-width: 599px) {
        .dora-segmented {
            overflow-x: auto;
            scrollbar-width: none;
            flex-wrap: nowrap;
        }
        .dora-segmented::-webkit-scrollbar { display: none; }
    }
</style>
