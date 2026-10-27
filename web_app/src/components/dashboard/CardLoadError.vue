<template>
    <div class="card-load-error" role="status">
        <q-icon :name="ICONS.cloud_off" size="28px" class="card-load-error__icon" />
        <div class="card-load-error__body">
            <div class="card-load-error__line">{{ line }}</div>
            <BaseButton
                variant="ghost"
                dense
                size="sm"
                :icon="ICONS.refresh"
                label="Try again"
                :loading="retrying"
                @click="onRetry"
            />
        </div>
    </div>
</template>

<script lang="ts" setup>
    /**
     * A dashboard card's "couldn't load this one" state.
     *
     * ## Why this exists
     *
     * Every one of the dashboard's slot loaders used to do
     * `catch { thing.value = null }` — with a comment explaining that the card
     * would then show its empty state. So a 500 on the savings endpoint rendered
     * *"Finish a shop and I'll tally what you kept"* to a household that had
     * shopped for months, and a failed alerts fetch rendered *"All clear —
     * nothing needs your attention right now"*. **Failure was indistinguishable
     * from absence, in the direction that reassures.** That is the Charter's
     * Honesty principle inverted, and `DASHBOARD_PAGE_REVIEW.md` §4.7 / finding
     * 10 counted eleven instances of it.
     *
     * `D-007` also wants the three states distinct: loading is a skeleton, empty
     * is `B9`'s anatomy, and this is the third — visibly *not* an empty state,
     * with the one action that can fix it.
     *
     * ## Deliberately not a toast
     *
     * One dashboard load fires eleven parallel requests. If the network is down,
     * eleven toasts is a pile-up (D-009's placement budget), and a toast also
     * outlives the thing it describes. The failure belongs *in* the card that
     * failed, so the reader can see which parts of the page they can trust.
     */
    import { ref } from 'vue';
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';

    const props = withDefaults(
        defineProps<{
            /** Override the copy where a card can say something more specific. */
            line?: string;
        }>(),
        { line: "I couldn't load this just now." },
    );
    void props;

    const emit = defineEmits<{ (e: 'retry'): void }>();

    // Local, not a prop: the parent's loader is fire-and-forget, so the button
    // owns its own brief busy state. Cleared on a timer rather than on the
    // parent's promise — a retry that fails again re-renders this component,
    // and one that succeeds unmounts it.
    const retrying = ref(false);
    function onRetry() {
        retrying.value = true;
        emit('retry');
        setTimeout(() => { retrying.value = false; }, 1200);
    }
</script>

<style scoped lang="scss">
    .card-load-error {
        display: flex;
        align-items: center;
        gap: var(--space-3);
        padding: var(--space-3) var(--space-4);
        border-radius: var(--radius-lg);
        /* A1: an inset region inside a card sits on `--surface-sunken`. Reads as
           a well rather than as content, which is what distinguishes it from the
           positive "all clear" empty state (`--semantic-positive-soft`). */
        background: var(--surface-sunken);
        color: var(--text-secondary);
    }
    .card-load-error__icon {
        color: var(--text-muted);
        flex: 0 0 auto;
    }
    .card-load-error__body {
        min-width: 0;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: var(--space-1);
    }
    .card-load-error__line {
        font-size: var(--font-size-sm);
        line-height: 1.35;
    }
</style>
