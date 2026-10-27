<template>
    <!--
        C-waste — tile-grid modal triggered from the StockItemRow expiry
        dropdown. Reason-only capture: a tile tap *is* the submit; there
        is no separate "Log" button. Cancel = top-right close-X or
        backdrop click (BaseDialog handles both).

        Per PROPOSAL_WASTE_MINIMISATION.md §5: no money field, no note
        field, no quantity field, no shame iconography. The empathy is
        in what's *missing* from this form, not in copy or a sad face.
    -->
    <BaseDialog
        :model-value="modelValue"
        title="Why did this go to waste?"
        closable
        card-style="min-width: 320px; max-width: 480px; width: 95vw"
        @update:model-value="(v) => emit('update:modelValue', v)"
    >
        <q-card-section v-if="itemName" class="mark-wasted__subject">
            <div class="text-subtitle1">{{ itemName }}</div>
            <div v-if="subline" class="dora-text-muted">{{ subline }}</div>
        </q-card-section>

        <q-card-section class="mark-wasted__tiles">
            <div class="mark-wasted__grid">
                <button
                    v-for="tile in primaryTiles"
                    :key="tile.reason"
                    type="button"
                    class="mark-wasted__tile"
                    @click="onPick(tile.reason)"
                >
                    <q-icon :name="tile.icon" size="28px" />
                    <span class="mark-wasted__tile-label">{{ tile.label }}</span>
                </button>
            </div>
            <button
                v-if="otherTile"
                type="button"
                class="mark-wasted__tile mark-wasted__tile--wide"
                @click="onPick(otherTile.reason)"
            >
                <q-icon :name="otherTile.icon" size="22px" />
                <span class="mark-wasted__tile-label">{{ otherTile.label }}</span>
            </button>
        </q-card-section>
    </BaseDialog>
</template>

<script setup lang="ts">
    import { computed } from 'vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import {
        WASTE_REASON_TILES,
    } from 'src/helpers/wasteReasons';
    import type { WasteReason } from 'src/services/api/wasteApiService';

    const props = defineProps<{
        modelValue: boolean;
        itemName: string;
        /** Optional second-line label (qty + location, etc.). */
        subline?: string | null;
    }>();

    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
        (e: 'submit', reason: WasteReason): void;
    }>();

    // "Other" gets its own full-width row beneath the 2x2 grid so the
    // four primary reasons stay equally weighted and the catch-all
    // reads quieter.
    const primaryTiles = computed(() =>
        WASTE_REASON_TILES.filter((t) => t.reason !== 'other'),
    );
    const otherTile = computed(() =>
        WASTE_REASON_TILES.find((t) => t.reason === 'other'),
    );

    function onPick(reason: WasteReason) {
        emit('submit', reason);
        emit('update:modelValue', false);
    }

    // Silence unused-prop lint — props.modelValue drives BaseDialog's
    // v-model binding through the template only.
    void props;
</script>

<style scoped lang="scss">
    .mark-wasted__subject {
        padding-bottom: var(--space-2);
    }
    .mark-wasted__tiles {
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
    }
    .mark-wasted__grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: var(--space-2);
    }
    .mark-wasted__tile {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--space-1);
        min-height: 84px;
        padding: var(--space-2) var(--space-3);
        /* R-060: was `--c-line` / `--c-surface-2`, custom properties that have
           never been declared anywhere this component can see — so these have
           always painted their hard-coded rgba fallbacks and never followed the
           theme. Surfaced when the dashboard's page-local `--c-*` alias layer
           was retired (FU-747) and the R-060 guard lost that declaration. */
        border: 1px solid var(--border-default);
        background: transparent;
        border-radius: var(--radius-md);
        color: inherit;
        font: inherit;
        cursor: pointer;
        transition: background-color var(--motion-fast) var(--motion-ease), border-color var(--motion-fast) var(--motion-ease);
    }
    .mark-wasted__tile:hover,
    .mark-wasted__tile:focus-visible {
        background: var(--surface-sunken);
        border-color: var(--border-strong);
    }
    .mark-wasted__tile:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    .mark-wasted__tile--wide {
        flex-direction: row;
        min-height: 56px;
        gap: var(--space-2);
    }
    .mark-wasted__tile-label {
        font-size: var(--font-size-sm);
        text-align: center;
        line-height: 1.2;
    }
</style>
