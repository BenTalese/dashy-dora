<template>
    <div>
        <BaseButton variant="icon" :icon="bellIcon" :color="bellColor" @click="open = true">
            <q-badge v-if="badgeCount > 0" floating class="alerts-count-badge" text-color="white" rounded>
                {{ badgeCount }}
            </q-badge>
            <BaseTooltip>
                {{
                    totalCount === 0
                        ? 'Nothing needs your attention'
                        : `${totalCount} thing${totalCount === 1 ? '' : 's'} need attention`
                }}
            </BaseTooltip>
        </BaseButton>

        <!-- Not `seamless`: the backdrop is what lets a tap outside close the
             panel (owner 2026-10-15). It is also the only alerts surface now
             that the Alerts page is gone, so it lists everything. -->
        <q-dialog v-model="open" position="right" full-height>
            <q-card class="alerts-panel column no-wrap" flat>
                <q-card-section class="row items-center q-pb-sm">
                    <q-icon :name="ICONS.notifications" size="22px" class="q-mr-sm" />
                    <div class="col text-h6">What needs your attention</div>
                    <BaseButton
                        v-if="totalCount > 0"
                        variant="ghost"
                        dense
                        :icon="ICONS.done_all"
                        label="Dismiss all"
                        :loading="dismissingAll"
                        @click="onDismissAll"
                    />
                    <BaseButton variant="icon" :icon="ICONS.close" aria-label="Close" @click="open = false" />
                </q-card-section>

                <q-separator />

                <q-banner v-if="loadError" class="dora-bg-negative-soft text-negative q-ma-md" dense rounded>
                    {{ loadError }}
                </q-banner>

                <div class="alerts-panel-list col scroll">
                    <!-- Owner 2026-10-17: a card per alert with space between,
                         not one list cut up by separators. -->
                    <q-list v-if="alerts.items.length > 0" class="alerts-panel-cards">
                        <AlertRow
                            v-for="alert in alerts.items"
                            :key="alert.alert_id"
                            :alert="alert"
                            :busy="busyAlertId === alert.alert_id"
                            @open="goTo(linkFor(alert))"
                            @navigate="goTo"
                            @action="(action) => applyAction(alert, action)"
                            @set-level="(levelId) => setLevel(alert, levelId)"
                            @log-waste="openLogWaste(alert)"
                            @snooze="alertStore.snoozeAlert(alert.alert_id)"
                            @dismiss="alertStore.dismissAlert(alert.alert_id)"
                        />
                    </q-list>

                    <div
                        v-if="!loading && totalCount === 0"
                        class="column items-center dora-text-muted q-py-lg"
                    >
                        <q-icon :name="ICONS.check_circle" size="48px" color="positive" />
                        <div class="q-mt-sm">Nothing to do right now.</div>
                    </div>

                    <!-- The snoozed set, collapsed: it is the one place to undo a
                         snooze now the page has gone. -->
                    <q-expansion-item
                        v-if="snoozedCount > 0"
                        :icon="ICONS.snooze"
                        :label="`Snoozed (${snoozedCount})`"
                        header-class="dora-text-secondary"
                    >
                        <q-list class="alerts-panel-cards">
                            <AlertRow
                                v-for="alert in alerts.snoozed"
                                :key="alert.alert_id"
                                :alert="alert"
                                :busy="busyAlertId === alert.alert_id"
                                @open="goTo(linkFor(alert))"
                                @navigate="goTo"
                                @action="(action) => applyAction(alert, action)"
                                @set-level="(levelId) => setLevel(alert, levelId)"
                                @log-waste="openLogWaste(alert)"
                                @unsnooze="alertStore.unsnoozeAlert(alert.alert_id)"
                                @dismiss="alertStore.dismissAlert(alert.alert_id)"
                            />
                        </q-list>
                    </q-expansion-item>
                </div>
            </q-card>
        </q-dialog>

        <!-- An expired alert's "Log waste": the stock row's reason picker and
             log flow (`useLogWaste`), one dialog for the whole panel. -->
        <MarkAsWastedDialog
            v-model="logWasteOpen"
            :item-name="logWasteTarget?.itemName ?? ''"
            @submit="onLogWaste"
        />
    </div>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import { ICONS } from 'src/style/icons';
    import AlertRow from 'src/components/AlertRow.vue';
    import MarkAsWastedDialog from 'src/components/stock/MarkAsWastedDialog.vue';
    import { useLogWaste, type LogWasteTarget } from 'src/composables/useLogWaste';
    import type { WasteReason } from 'src/services/api/wasteApiService';
    import { linkFor, type Alert } from 'src/models/alert';
    import { useAlertActions } from 'src/composables/useAlertActions';
    import { useAlertStore } from 'src/stores/alertStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
    import { useQuasar } from 'quasar';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import { useRoute, useRouter } from 'vue-router';

    // The bell is the whole alerts surface (owner 2026-10-15: the Alerts page
    // was cut once its toggles moved to Settings and its rows gained the
    // buttons they needed). Rows are the shared AlertRow (R-001).
    const $q = useQuasar();
    const route = useRoute();
    const router = useRouter();
    const alertStore = useAlertStore();
    const stockItemStore = useStockItemStore();
    const { busyAlertId, applyAction } = useAlertActions();

    const open = ref(false);
    const dismissingAll = ref(false);

    const alerts = computed(() => alertStore.alerts);
    const loading = computed(() => alertStore.loading);
    const loadError = computed(() => alertStore.loadError);
    const badgeCount = computed(() => alertStore.badgeCount);
    const totalCount = computed(() => alertStore.totalCount);
    const snoozedCount = computed(() => alertStore.snoozedCount);

    const bellIcon = computed(() =>
        badgeCount.value > 0 ? ICONS.notifications_active : ICONS.notifications,
    );
    const bellColor = computed(() => {
        if (alerts.value.high_count > 0) return 'negative';
        if (alerts.value.medium_count > 0) return 'warning';
        return undefined;
    });

    // The level picker on a shortage row reads the item's current level from
    // the stock store, so make sure it is there when the panel opens.
    // Opening the panel also refreshes it: between polls something may have
    // changed elsewhere in the app (a price watch set, a level changed).
    watch(open, (isOpen) => {
        if (!isOpen) return;
        void stockItemStore.ensureLoadedAsync();
        void alertStore.refreshAsync();
    });

    // A push notification (and any old `/alerts` link) lands on `?alerts=open`.
    watch(
        () => route.query.alerts,
        (value) => {
            if (value !== 'open') return;
            open.value = true;
            const { alerts: _drop, ...rest } = route.query;
            void router.replace({ query: rest });
        },
        { immediate: true },
    );

    function goTo(link: string | null) {
        if (!link) return;
        open.value = false;
        void router.push(link);
    }

    async function setLevel(alert: Alert, levelId: string) {
        if (!alert.stock_item_id) return;
        try {
            await stockItemStore.updateStockLevelAsync({
                stock_item_id: alert.stock_item_id,
                stock_level_id: levelId,
            });
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not update.',
                caption: toastCaption(err),
            });
            return;
        }
        await alertStore.refreshAsync();
    }

    // Expired alerts → "Log waste". Snapshot the item when the button is
    // pressed (useLogWaste's contract): logging clears the expiry, which is
    // what retires the alert, so the bell refreshes after the log and again
    // after an Undo brings it back.
    const { logWasteAsync } = useLogWaste(() => alertStore.refreshAsync());
    const logWasteOpen = ref(false);
    const logWasteTarget = ref<LogWasteTarget | null>(null);

    function openLogWaste(alert: Alert) {
        if (!alert.stock_item_id) return;
        const item = stockItemStore.stockItems.find((s) => s.stock_item_id === alert.stock_item_id);
        logWasteTarget.value = {
            stockItemId: alert.stock_item_id,
            itemName: item?.name ?? alert.stock_item_name ?? 'this item',
            // An expired alert's related date is the item's expiry; the store
            // copy wins when it has loaded.
            originalExpiry: item?.expiry_date ?? alert.related_date,
        };
        logWasteOpen.value = true;
    }

    async function onLogWaste(reason: WasteReason) {
        const target = logWasteTarget.value;
        if (!target) return;
        await logWasteAsync(target, reason);
    }

    async function onDismissAll() {
        dismissingAll.value = true;
        try {
            await alertStore.dismissAllAsync();
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: "Couldn't dismiss the alerts.",
                caption: toastCaption(err),
            });
        } finally {
            dismissingAll.value = false;
        }
    }

    // Poll every 60s so the bell stays roughly fresh without hammering, but
    // only while someone can actually see the bell. A backgrounded phone
    // waking its radio to refresh a badge nobody is looking at is pure cost —
    // and the state it fetched is stale by the time the user returns anyway.
    // Coming back to the foreground refreshes immediately instead, which is
    // both cheaper and fresher. (Same reasoning as the health probe in
    // `useNetworkStatus`.)
    let pollHandle: ReturnType<typeof setInterval> | null = null;

    function onVisibilityChange() {
        if (document.visibilityState === 'hidden') return;
        void alertStore.refreshAsync();
    }

    // Registered before the first await: an unmount during that await would
    // otherwise run onUnmounted first and leak the interval + listener.
    onMounted(async () => {
        pollHandle = setInterval(() => {
            if (document.visibilityState === 'hidden') return;
            void alertStore.refreshAsync();
        }, 60_000);
        document.addEventListener('visibilitychange', onVisibilityChange);
        await alertStore.refreshAsync();
    });

    onUnmounted(() => {
        if (pollHandle) clearInterval(pollHandle);
        document.removeEventListener('visibilitychange', onVisibilityChange);
    });
</script>

<style scoped>
    /* DR-1b (FU-578 #7 / D-002): the count badge used `color="negative"`, but
       --semantic-negative is *lightened* in dark themes (for text/icon use), so
       white-on-it fell to ~2.96:1. Darken the red toward black by a fixed amount
       so white stays >=6:1 in every theme while reading as a standard alert red. */
    .alerts-count-badge {
        background: color-mix(in srgb, var(--semantic-negative) 65%, black);
    }
    /* Owner feedback 2026-09-09: the badge sat differently on mobile vs desktop
       — "desktop feels like it's too covered, mobile feels too close to the edge
       of the screen". Cause: Quasar pins `--floating` to the *button* box
       (top:-4px/right:-3px), but BaseButton's icon variant is 36px with a mouse
       and 44px under `pointer: coarse` (the D-004 touch floor). The bell glyph
       is the same size in both, so the 8px box difference pushed the badge 4px
       further out from the icon on touch.
       Offsetting by that 4px in opposite directions lands both on one position,
       midway between the two the owner compared. */
    .alerts-count-badge.q-badge--floating {
        top: -6px;
        right: -5px;
    }
    @media (pointer: coarse) {
        .alerts-count-badge.q-badge--floating {
            top: -2px;
            right: -1px;
        }
    }
    .alerts-panel {
        width: 420px;
        max-width: 100vw;
        height: 100%;
    }
    .alerts-panel-list {
        max-height: 100%;
        overflow-y: auto;
    }
    .alerts-panel-cards {
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
        padding: var(--space-3);
    }
</style>
