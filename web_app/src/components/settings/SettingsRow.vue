<template>
    <div
        class="settings-row"
        :class="{ 'settings-row--stacked': stacked, 'settings-row--inline': inline }"
    >
        <div class="settings-row__info">
            <div v-if="label || $slots.label" ref="labelEl" class="settings-row__label">
                <slot name="label">{{ label }}</slot>
            </div>
            <div v-if="help || $slots.help" class="settings-row__help">
                <slot name="help">{{ help }}</slot>
            </div>
        </div>
        <div ref="controlEl" class="settings-row__control">
            <slot />
        </div>
    </div>
</template>

<script setup lang="ts">
    import { onBeforeUnmount, onMounted, onUpdated, ref } from 'vue';

    // IMPL_PLAN_SETTINGS_REBUILD §2.5 — single row inside a SettingsSection:
    // left = label + optional one-line help; right = control. Collapses to
    // label-above-control on narrow viewports (Phase 5 verifies).
    defineProps<{
        label?: string;
        help?: string;
        /** Force label-above-control at every width. */
        stacked?: boolean;
        /**
         * Keep the control on the right at every width, including mobile.
         * For narrow controls (a toggle, a short select) the automatic mobile
         * stack wastes a whole line and reads as a list of orphaned switches —
         * owner feedback 2026-09-03. Rows holding a wide control (a text input)
         * still want the stack, so this stays opt-in rather than the default.
         */
        inline?: boolean;
    }>();

    /* The row's label is visible text beside the control, but nothing ties the
       two together for a screen reader: a bare `q-toggle` / `q-input` /
       `q-select` dropped in the slot announces as an unnamed switch or field
       (axe `aria-toggle-field-name`, `label`). Every settings page uses this
       row, so the row names its own controls rather than every call site
       repeating the label as an `aria-label`. A control that already carries a
       name (its own `aria-label`, a Quasar `label`, or text content) is left
       alone. The label's `textContent` is used rather than `aria-labelledby`
       so a slotted InfoTip's own "More information: …" name isn't folded in.
       A MutationObserver covers controls that mount after the row does
       (`v-if` on a loaded draft). */
    const labelEl = ref<HTMLElement | null>(null);
    const controlEl = ref<HTMLElement | null>(null);
    const OWNED = 'data-settings-row-name';
    const CONTROLS = [
        '[role="switch"]',
        '[role="checkbox"]',
        '[role="slider"]',
        '[role="combobox"]',
        'input:not([type="hidden"])',
        'select',
        'textarea',
    ].join(',');

    function hasOwnName(el: HTMLElement): boolean {
        if (el.getAttribute('aria-label')?.trim() || el.hasAttribute('aria-labelledby')) {
            return true;
        }
        const role = el.getAttribute('role');
        if ((role === 'switch' || role === 'checkbox') && el.textContent?.trim()) return true;
        const fieldLabel = el.closest('.q-field')?.querySelector('.q-field__label');
        return Boolean(fieldLabel?.textContent?.trim());
    }

    /* The ownership marker's value is the exact name the row applied. If the
       control's `aria-label` no longer equals it, the call site has since
       named the control itself — the name is theirs, so the marker goes and
       the row never touches it again. While the row still owns the name it
       follows the label text, and an emptied label takes the name with it. */
    function nameControls() {
        if (!controlEl.value) return;
        const text = labelEl.value?.textContent?.replace(/\s+/g, ' ').trim() ?? '';
        controlEl.value.querySelectorAll<HTMLElement>(CONTROLS).forEach((el) => {
            const applied = el.getAttribute(OWNED);
            if (applied !== null) {
                if (el.getAttribute('aria-label') !== applied) {
                    el.removeAttribute(OWNED);
                    return;
                }
                if (!text) {
                    el.removeAttribute('aria-label');
                    el.removeAttribute(OWNED);
                } else if (text !== applied) {
                    el.setAttribute('aria-label', text);
                    el.setAttribute(OWNED, text);
                }
                return;
            }
            if (!text || hasOwnName(el)) return;
            el.setAttribute('aria-label', text);
            el.setAttribute(OWNED, text);
        });
    }

    let observer: MutationObserver | null = null;
    onMounted(() => {
        nameControls();
        if (controlEl.value && typeof MutationObserver !== 'undefined') {
            observer = new MutationObserver(nameControls);
            observer.observe(controlEl.value, { childList: true, subtree: true });
        }
    });
    onUpdated(nameControls);
    onBeforeUnmount(() => observer?.disconnect());
</script>

<style scoped lang="scss">
    .settings-row {
        display: flex;
        /* Owner feedback 2026-08-29 — *"the toggles don't seem to be inline
           with the option text. Seems to be a broader issue across the board
           in the settings area."* They weren't: a q-toggle's box is ~40px tall
           against an ~18px label line, so top-aligning the two put the toggle's
           track a full 11px below the label it belongs to — on every row of
           every settings page. Centre against the info block instead, which is
           exact for the one-line rows (the common case) and reads correctly
           when a `help` line is present too. D-018 — alignment is consistent
           within a surface, and this is the surface's own primitive, so the
           fix belongs here rather than on any one page. */
        align-items: center;
        justify-content: space-between;
        gap: 24px;
        padding: 6px 0;
    }
    .settings-row__info {
        flex: 1 1 auto;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .settings-row__label {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-primary);
        line-height: 1.3;
    }
    .settings-row__help {
        font-size: 0.8125rem;
        color: var(--text-secondary);
        line-height: 1.35;
    }
    .settings-row__control {
        flex: 0 0 auto;
        min-width: 0;
        max-width: 60%;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .settings-row--stacked,
    .settings-row--stacked.settings-row {
        flex-direction: column;
        align-items: stretch;
        gap: 10px;
    }
    .settings-row--stacked .settings-row__control {
        max-width: 100%;
        width: 100%;
    }

    @media (max-width: 599px) {
        .settings-row:not(.settings-row--inline) {
            flex-direction: column;
            align-items: stretch;
            gap: 10px;
        }
        .settings-row:not(.settings-row--inline) .settings-row__control {
            max-width: 100%;
            width: 100%;
        }
        /* Inline rows keep the two-column shape; the gap tightens so a long
           label still gets most of the width. */
        .settings-row--inline {
            gap: 12px;
        }
        .settings-row--inline .settings-row__control {
            max-width: 55%;
        }
    }
</style>
