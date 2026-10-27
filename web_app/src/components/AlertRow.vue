<template>
    <!-- Owner 2026-10-17 — each alert is its own rounded card (the panel
         spaces them; no separators), its kind icon centred down the left,
         the thing's buttons under the text, and the alert's own snooze /
         dismiss as a slim icon column on the right. -->
    <q-item clickable class="alert-card" @click="emit('open')">
        <q-item-section avatar class="alert-card__avatar">
            <AlertKindAvatar :kind="alert.kind" :severity="alert.severity" />
        </q-item-section>

        <q-item-section>
            <q-item-label class="text-weight-medium">{{ alert.message }}</q-item-label>
            <q-item-label caption>
                <span v-if="alert.amount !== null">{{ formatMoney(alert.amount) }}</span>
                <span v-if="alert.amount !== null && alert.detail"> · </span>
                <span v-if="alert.detail">{{ alert.detail }}</span>
                <span v-if="alert.related_date"> · {{ formatDate(alert.related_date) }}</span>
                <span v-if="alert.snoozed_until"> · Snoozed until {{ formatDate(alert.snoozed_until) }}</span>
            </q-item-label>

            <!-- Acts on the thing the alert is about. All text buttons, the
                 level picker included (owner 2026-10-17: the overview's
                 colour square read oddly here). `@click.stop` so a button
                 never also opens the card. -->
            <div v-if="hasItemActions" class="alert-card__actions" @click.stop>
                <BaseButton
                    v-for="action in serverActions"
                    :key="action.action"
                    variant="secondary"
                    :icon="action.icon"
                    :label="action.label"
                    :loading="busy"
                    @click="emit('action', action.action)"
                />
                <BaseButton
                    v-if="logWaste"
                    variant="secondary"
                    :icon="ICONS.wasted"
                    label="Log waste"
                    @click="emit('log-waste')"
                />
                <template v-if="stockControls">
                    <StockLevelPicker
                        variant="text"
                        :level-id="currentLevelId"
                        @select="(id: string) => emit('set-level', id)"
                    />
                    <AddToListButton variant="toolbar" :stock-item-id="alert.stock_item_id!" />
                </template>
                <!-- A price drop adds the product the way My products does:
                     through its linked item with this product picked, or as
                     a product-only line when it is unlinked. -->
                <template v-if="productCart">
                    <AddToListButton
                        v-if="alert.stock_item_id"
                        variant="toolbar"
                        :stock-item-id="alert.stock_item_id"
                        :selected-product-id="alert.target_id!"
                    />
                    <AddToListButton v-else variant="toolbar" :product-id="alert.target_id!" />
                </template>
                <BaseButton
                    v-if="navTarget"
                    variant="secondary"
                    :icon="nav!.icon"
                    :label="nav!.label"
                    @click="emit('navigate', navTarget)"
                />
            </div>
        </q-item-section>

        <!-- Acts on the alert. Icon-only, so each carries an aria-label and a
             tooltip (D-005). -->
        <q-item-section side class="alert-card__alert-actions" @click.stop>
            <BaseButton
                v-if="alert.snoozed_until"
                variant="icon"
                :icon="ICONS.undo"
                aria-label="Unsnooze"
                @click="emit('unsnooze')"
            >
                <BaseTooltip>Unsnooze</BaseTooltip>
            </BaseButton>
            <BaseButton
                v-else
                variant="icon"
                :icon="ICONS.snooze"
                :aria-label="`Snooze for ${DEFAULT_SNOOZE_DAYS} days`"
                @click="emit('snooze')"
            >
                <BaseTooltip>Snooze: hide for {{ DEFAULT_SNOOZE_DAYS }} days.</BaseTooltip>
            </BaseButton>
            <BaseButton
                variant="icon"
                :icon="ICONS.close"
                aria-label="Dismiss"
                @click="emit('dismiss')"
            >
                <BaseTooltip>Dismiss: gone until this happens again.</BaseTooltip>
            </BaseButton>
        </q-item-section>
    </q-item>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import AddToListButton from 'src/components/AddToListButton.vue';
    import AlertKindAvatar from 'src/components/AlertKindAvatar.vue';
    import StockLevelPicker from 'src/components/stock/StockLevelPicker.vue';
    import { formatDate as formatLocaleDate } from 'src/composables/useDateFormat';
    import { formatMoney } from 'src/composables/useMoney';
    import { ICONS } from 'src/style/icons';
    import {
        ALERT_KIND_META, DEFAULT_SNOOZE_DAYS, actionsFor, type Alert, type AlertAction,
    } from 'src/models/alert';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { computed } from 'vue';

    // The one alert card (R-001). Presentational: it renders the alert and its
    // buttons and *emits* what the user wants done; the bell owns the
    // store/API side effects (and the waste dialog). The level picker and the
    // cart are the shared controls the stock row uses, so a shortage is handled
    // here the same way.
    const props = defineProps<{
        alert: Alert;
        /** A server action for THIS alert is in flight. */
        busy?: boolean;
    }>();

    const emit = defineEmits<{
        (e: 'open'): void;
        (e: 'action', action: AlertAction): void;
        (e: 'set-level', levelId: string): void;
        (e: 'log-waste'): void;
        (e: 'navigate', to: string): void;
        (e: 'snooze'): void;
        (e: 'unsnooze'): void;
        (e: 'dismiss'): void;
    }>();

    // `?? []` / `?.` are load-bearing: the backend can ship a kind the client
    // doesn't know yet (the 2026-07-09 crash), and that must degrade to a row
    // with only the alert's own buttons.
    const serverActions = computed(() => actionsFor(props.alert.kind) ?? []);
    const nav = computed(() => ALERT_KIND_META[props.alert.kind]?.nav ?? null);
    const navTarget = computed(() => nav.value?.to(props.alert) ?? null);
    const stockControls = computed(
        () => !!ALERT_KIND_META[props.alert.kind]?.stockControls && !!props.alert.stock_item_id,
    );
    const logWaste = computed(
        () => !!ALERT_KIND_META[props.alert.kind]?.logWaste && !!props.alert.stock_item_id,
    );
    const productCart = computed(
        () => !!ALERT_KIND_META[props.alert.kind]?.productCart && !!props.alert.target_id,
    );
    const hasItemActions = computed(
        () => serverActions.value.length > 0 || !!navTarget.value
            || stockControls.value || logWaste.value || productCart.value,
    );

    const stockItemStore = useStockItemStore();
    const currentLevelId = computed(() => stockItemStore.stockItems.find(
        (s) => s.stock_item_id === props.alert.stock_item_id,
    )?.stock_level_id ?? null);

    function formatDate(iso: string): string {
        // DR-14: household-locale date (falls back to the raw value if unparseable).
        return formatLocaleDate(iso) || iso;
    }
</script>

<style scoped>
    /* The card. Tokens only (R-002); the panel owns the gap between cards. */
    .alert-card {
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        background: var(--surface-component);
        padding: var(--space-2) var(--space-1) var(--space-2) var(--space-3);
        overflow: hidden;
    }
    .alert-card__avatar {
        min-width: 0;
        padding-right: var(--space-3);
    }
    .alert-card__actions {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--space-2) var(--space-1);
        margin-top: var(--space-2);
    }
    /* Owner 2026-10-17 — "buttons don't look great, make them less tall with
       better padding". They were `dense` (cramped sides) at the full 36px.
       Slimmer and roomier: 32px with a proper side padding and a smaller
       label and glyph. `:deep` because the class is BaseButton's root (and
       AddToListButton's / StockLevelPicker's, which render BaseButton). */
    .alert-card__actions :deep(.dora-btn) {
        min-height: 32px;
        padding: 0 var(--space-3);
        font-size: var(--font-size-sm);
    }
    .alert-card__actions :deep(.dora-btn .q-icon) {
        font-size: 1.25em;
    }
    /* D-004 on touch: BaseButton lifts every button to 44px under
       `pointer: coarse`, which is the height the owner called too tall.
       These hold a 36px face and reach the 44px *effective* target with a
       transparent strip above and below (`::after`; QBtn owns `::before`).
       The 8px row gap above is what keeps two wrapped rows' strips from
       overlapping. */
    @media (pointer: coarse) {
        .alert-card__actions :deep(.dora-btn) {
            min-height: 36px;
        }
        .alert-card__actions :deep(.dora-btn)::after {
            content: '';
            position: absolute;
            inset: -4px 0;
        }
    }
    /* The alert's own buttons, stacked down the right edge. */
    .alert-card__alert-actions {
        flex-direction: column;
        justify-content: center;
        align-items: center;
        gap: 0;
        padding-left: var(--space-1);
    }
</style>
