<template>
    <div
        class="sl-row sl-row--hoverable sl-runrow dora-press"
        :class="{
            'sl-runrow--picked': picked,
            'sl-runrow--nested': nested,
        }"
        role="button"
        tabindex="0"
        @click="emit('toggle')"
        @keydown.enter.prevent="emit('toggle')"
        @keydown.space.prevent="emit('toggle')"
    >
        <!-- Decorative on purpose: the row is the control, and a real checkbox
             here would swallow the tap, emit its own change *and* bubble the
             row's activation — two mutations for one gesture. -->
        <q-icon
            :name="picked ? ICONS.check_box : ICONS.check_box_outline_blank"
            :size="picked ? '24px' : '28px'"
            :color="picked ? 'positive' : undefined"
            class="sl-runrow__box"
            :class="{ 'dora-text-secondary': !picked }"
        />

        <div class="sl-runrow__main">
            <div class="sl-row__name" :class="{ 'sl-row__name--struck': picked }">
                <span v-if="(line.quantity ?? 0) > 1" class="sl-runrow__mult">
                    {{ line.quantity }}&times;
                </span>
                {{ line.stock_item_name }}
            </div>
            <!-- One caption line, and only what a shopper standing in the aisle
                 can act on. Picked rows drop it: the job is done, and the row is
                 a record at that point. -->
            <div v-if="caption && !picked" class="sl-row__meta">
                <span class="sl-row__note ellipsis">{{ caption }}</span>
            </div>
        </div>

        <div v-if="moneyEnabled" class="sl-row__money">
            <!-- Price capture is a deliberate second tap opening a thumb-height
                 sheet — never an inline field a mis-aimed tap on a moving
                 trolley can edit. A picked row shows the figure as type, since
                 its price is already captured and the row's tap puts it back. -->
            <BaseButton
                v-if="!picked"
                variant="ghost"
                dense
                :label="priceLabel"
                class="sl-runrow__price"
                :class="{ 'sl-runrow__price--estimate': line.estimate_source !== 'actual' }"
                @click.stop="emit('capture-price')"
            >
                <BaseTooltip>
                    {{
                        line.estimate_source === 'actual'
                            ? 'The price you entered'
                            : 'Tap to record what you actually paid'
                    }}
                </BaseTooltip>
            </BaseButton>
            <span v-else class="sl-runrow__price sl-runrow__price--estimate">
                {{ priceLabel }}
            </span>
        </div>

        <BaseTooltip v-if="picked">Tap to put it back on the list</BaseTooltip>
    </div>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    /**
     * One line on the shopping list's run face — the list as it is used in a
     * store.
     *
     * Built on the shared row skeleton in `src/css/shoppingList.scss`, same as
     * the plan and receipt rows (v4 chunk 5, FU-807). Until then this face was
     * the one surface still rendering `q-list bordered separator` + `q-item`
     * while the other two had moved to slabs — a hard border, `--radius-md` and
     * edge-to-edge separators against their soft slab and inset dividers.
     *
     * `q-item` is gone for the same reason chunk 1 dropped it from the plan
     * row: it ships its own padding, min-heights and `--side` alignment, which
     * is what the row then has to fight. The row is a `role="button"` div
     * rather than a `<button>` because it contains the price button, and a
     * button inside a button is invalid — so Enter and Space are wired
     * explicitly, which is what `q-item clickable` was providing.
     *
     * What makes it the *run* face is unchanged and deliberate: one row, one
     * gesture, an optional price, and a thumb-sized target. Everything that
     * exists to curate a list stays on the plan face.
     */
    import { computed } from 'vue';
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import type { ShoppingListLine } from 'src/models/shoppingList';

    const props = defineProps<{
        line: ShoppingListLine;
        /** Already in the trolley — the row reads as a record and its tap
         *  becomes the undo. */
        picked: boolean;
        nested: boolean;
        /** Built by the face, which knows what the sectioning is already
         *  saying, so the row never repeats its own heading back at itself. */
        caption: string;
    }>();

    const emit = defineEmits<{
        /** Tick, or — on a picked row — put it back. The page owns both. */
        toggle: [];
        'capture-price': [];
    }>();

    const { moneyEnabled } = useMoneyEnabled();

    /** Never re-derive the money ladder client-side (R-003) — the server has
     *  already resolved it and named the rung it used. */
    const priceLabel = computed(() => {
        if (props.line.estimated_unit_price == null) return 'Price';
        const money = formatMoney(props.line.estimated_unit_price);
        return props.line.estimate_source === 'actual' ? money : `~${money}`;
    });
</script>

<style scoped>
    /* Three tracks: the checkbox, the name, the price. No reserved quantity or
       action columns — mid-shop there is exactly one thing a row does. */
    .sl-runrow {
        --sl-cols: auto minmax(0, 1fr) auto;
        /* D-004 / D-016: the row *is* the target, and the hand holding it is
           also holding a trolley. Sized for a thumb, not a cursor. */
        min-height: 60px;
        cursor: pointer;
        user-select: none;
    }
    .sl-runrow:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: -2px;
    }
    .sl-runrow--nested {
        padding-left: var(--space-8);
    }
    /* Quieter than a live row on purpose — done work shouldn't compete with
       what's left to pick — but still a full target, because putting an item
       back is the recovery path for a mis-tap. */
    .sl-runrow--picked {
        min-height: 48px;
    }
    .sl-runrow--picked .sl-runrow__main {
        color: var(--text-secondary);
    }

    .sl-runrow__box {
        justify-self: center;
    }
    .sl-runrow__main {
        min-width: 0;
    }
    .sl-runrow__mult {
        font-variant-numeric: tabular-nums;
        color: var(--text-secondary);
        margin-right: 2px;
    }
    .sl-runrow__price {
        font-variant-numeric: tabular-nums;
        min-width: 72px;
    }
    .sl-runrow__price--estimate {
        color: var(--text-secondary);
    }
</style>
