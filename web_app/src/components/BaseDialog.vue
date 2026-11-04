<template>
    <!--
        A3 — standard modal shell. Wraps q-dialog + q-card so dialog
        behaviour is defined in one place:
          • NOT persistent by default → backdrop click and Esc both
            dismiss, and dismiss means *cancel* (no commit, no navigation).
            Pass :persistent only for flows that must not be dismissed by
            mistake (e.g. an in-progress scan).
          • token-based radius / max-width so every dialog matches.
          • optional standardised header (title + close) and footer
            (#actions slot, right-aligned).
        Unknown attrs (position, transition-show, …) auto-forward to the
        root q-dialog because it is the single root element.
    -->
    <q-dialog
        :model-value="modelValue"
        :persistent="persistent"
        @update:model-value="(v) => emit('update:modelValue', v)"
        @hide="onHide"
    >
        <q-card
            ref="cardRef"
            class="dora-dialog"
            :class="cardClass"
            :style="cardStyle"
            @keydown.tab="wrapFocus"
        >
            <!-- Standard header: title on the left, optional close on the right -->
            <template v-if="title || $slots.header">
                <q-card-section class="dora-dialog__header row items-center no-wrap">
                    <slot name="header">
                        <div class="text-h6 col">{{ title }}</div>
                    </slot>
                    <BaseButton
                        v-if="closable"
                        variant="icon"
                        :icon="ICONS.close"
                        aria-label="Close"
                        @click="cancel"
                    />
                </q-card-section>
                <q-separator />
            </template>

            <!-- Body -->
            <slot :cancel="cancel" />

            <!-- Standard footer — right-aligned action buttons -->
            <q-card-actions v-if="$slots.actions" align="right" class="dora-dialog__footer">
                <slot name="actions" :cancel="cancel" />
            </q-card-actions>
        </q-card>
    </q-dialog>
</template>

<script setup lang="ts">
    import { ref } from 'vue';
    import type { QCard } from 'quasar';
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';

    withDefaults(
        defineProps<{
            modelValue: boolean;
            /** Optional title — renders the standardised header + separator. */
            title?: string;
            /** Only set for flows that must not be dismissed by accident. */
            persistent?: boolean;
            /** Show an X close button in the standardised header. */
            closable?: boolean;
            /** Inline card sizing — defaults to a sensible responsive width. */
            cardStyle?: string;
            cardClass?: string;
        }>(),
        {
            persistent: false,
            closable: false,
            cardStyle: 'min-width: 360px; max-width: 95vw',
        },
    );

    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
        // Fired whenever the dialog closes (backdrop, Esc, or cancel button).
        // Per A3, dismissal is always a cancel — never a commit/navigation.
        (e: 'cancel'): void;
    }>();

    // Close the dialog. q-dialog's @hide then fires the `cancel` event, so
    // we don't double-emit here.
    function cancel() {
        emit('update:modelValue', false);
    }

    function onHide() {
        emit('cancel');
    }

    // ── Focus trap (FU-976) ─────────────────────────────────────────────
    // QDialog pulls focus back when it lands *elsewhere in the page*, but its
    // portal is the last thing in <body>: Tab past the last control (the
    // waste dialog's last tile, in walk D) leaves the document for the
    // browser's own chrome, where no focus event can catch it. So Tab on the
    // last tabbable element wraps to the first, and Shift+Tab on the first
    // wraps to the last — every dialog built on this shell gets it.
    const cardRef = ref<QCard | null>(null);
    const TABBABLE =
        'a[href], button, input:not([type="hidden"]), select, textarea, [tabindex]';

    function wrapFocus(e: KeyboardEvent) {
        const root = cardRef.value?.$el as HTMLElement | undefined;
        if (!root) return;
        const items = Array.from(root.querySelectorAll<HTMLElement>(TABBABLE)).filter(
            (el) =>
                el.tabIndex >= 0 &&
                !el.hasAttribute('disabled') &&
                // Rendered — a `v-show`-hidden control can't take focus.
                el.getClientRects().length > 0,
        );
        const first = items[0];
        const last = items[items.length - 1];
        if (!first || !last) return;
        const active = document.activeElement;
        if (e.shiftKey && active === first) {
            e.preventDefault();
            last.focus();
        } else if (!e.shiftKey && active === last) {
            e.preventDefault();
            first.focus();
        }
    }
</script>

<style scoped lang="scss">
    .dora-dialog {
        border-radius: var(--radius-lg, 12px);
    }
    .dora-dialog__header {
        /* Slightly tighter than the body so the title sits close to its rule. */
        padding-bottom: var(--space-2, 8px);
    }
</style>
