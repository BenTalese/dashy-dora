<template>
    <!-- The router guard owns "signed in"; this only waits for the user row. -->
    <div v-if="currentUser" class="settings-page">
        <SettingsPageHeader title="Notifications" :icon="ICONS.notifications" />

        <!--
            Owner restructure 2026-08-29 — the page was a flat run of four
            peer sections (deals email, push, evening brief) where the *channel*
            and the *thing sent over it* sat at the same level, so "Evening
            brief" gave no clue it was push-only and the deals email gave no
            clue it was the only thing that arrives by mail. Two sections now,
            one per channel, each opening with its own blocker banner and then
            listing what it can deliver as child rows.
        -->

        <!-- In-app alerts (owner 2026-10-15). Moved here from the Alerts page,
             which was removed: which kinds reach your bell, how long an alert
             lives, and the price watches you have set. -->
        <SettingsSection>
            <template #title>In-app alerts</template>

            <SettingsRow inline>
                <template #label>
                    Discard alerts after
                    <InfoTip label="Discard alerts after">
                        An alert drops out of your bell this long after the
                        thing it is about started, as if you had dismissed it.
                    </InfoTip>
                </template>
                <q-select
                    :model-value="currentUser.alert_discard_after_days"
                    :options="discardOptions"
                    option-value="value"
                    option-label="label"
                    emit-value
                    map-options
                    outlined
                    dense
                    class="deals-day-select"
                    @update:model-value="onDiscardChange"
                />
            </SettingsRow>

            <SettingsRow v-for="pref in visiblePrefs" :key="pref.kind" inline>
                <template #label>
                    <!-- The bell's own kind icon in its severity circle, so a
                         toggle reads as the alert it controls (owner
                         2026-10-17). -->
                    <span class="row items-center no-wrap q-gutter-x-sm">
                        <AlertKindAvatar :kind="pref.kind" :severity="pref.severity" />
                        <span>{{ kindLabel(pref.kind) }}</span>
                    </span>
                </template>
                <q-toggle
                    :model-value="pref.enabled"
                    :disable="prefBusy.has(pref.kind)"
                    :aria-label="`Alert me about ${kindTheme(pref.kind)}`"
                    @update:model-value="(v: boolean) => onToggleKind(pref.kind, v)"
                />
            </SettingsRow>

            <template v-if="moneyEnabled && watches.length > 0">
                <div class="settings-page__subhead">Price watches</div>
                <q-list separator class="watch-list">
                    <q-item v-for="watch in watches" :key="watch.price_alert_id">
                        <q-item-section>
                            <q-item-label>{{ watch.product_name }}</q-item-label>
                            <q-item-label caption>
                                {{ watch.store_name }} · at or below
                                {{ formatMoney(watch.threshold_unit_price) }}
                            </q-item-label>
                        </q-item-section>
                        <q-item-section side>
                            <BaseButton
                                variant="danger-icon"
                                :icon="ICONS.delete_outline"
                                :aria-label="`Stop watching ${watch.product_name}`"
                                :loading="removingWatch === watch.price_alert_id"
                                @click="onRemoveWatch(watch)"
                            >
                                <BaseTooltip>Stop watching</BaseTooltip>
                            </BaseButton>
                        </q-item-section>
                    </q-item>
                </q-list>
            </template>
        </SettingsSection>

        <hr class="settings-divider" />

        <!-- Push. VAPID-gated install-wide; also needs the browser to support
             web push and the user to have subscribed *this* device. -->
        <SettingsSection>
            <template #title>Push notifications</template>

            <!-- Blockers first (owner): the answer to "why is this toggle
                 dead?" belongs above the dead toggle, not under it. -->
            <ChannelSetupNote
                v-if="!pushVapidConfigured"
                channel="push"
                :is-admin="isAdmin"
            />
            <SettingsNotice v-else-if="!pushSupported" title="Not available in this browser">
                This browser doesn't support web push, so nothing in this
                section can be delivered here. Chrome, Edge, Firefox and Safari
                all support it on desktop; on iPhone the app must be installed
                to the home screen first.
            </SettingsNotice>
            <SettingsNotice v-else-if="pushState === 'denied'" title="Notifications are blocked">
                You've blocked notifications for this site. Re-enable them in
                your browser's site settings, then refresh this page.
            </SettingsNotice>
            <SettingsNotice v-else-if="pushError" title="Push subscription failed">
                {{ pushError }}
            </SettingsNotice>

            <SettingsRow inline>
                <template #label>
                    Push notifications on this device
                    <InfoTip label="Push notifications on this device">
                        Subscribes this browser on this device. Every device you
                        sign in on keeps its own subscription, so turning it off
                        here doesn't affect your phone.
                    </InfoTip>
                </template>
                <q-toggle
                    :model-value="pushSubscribed"
                    :disable="!pushVapidConfigured || !pushSupported || pushLoading"
                    aria-label="Send me push notifications on this device"
                    @update:model-value="onPushToggle"
                />
            </SettingsRow>

            <!-- The evening brief rides the push channel, so it lives inside
                 it rather than beside it — that relationship was invisible
                 while the two were peer sections. -->
            <SettingsRow inline>
                <template #label>
                    Evening brief
                    <InfoTip label="Evening brief">
                        A notification at 7pm with tomorrow's agenda.
                    </InfoTip>
                </template>
                <q-toggle
                    :model-value="currentUser.daily_brief_enabled"
                    :disable="!pushVapidConfigured || !pushSupported"
                    aria-label="Send me an evening brief"
                    @update:model-value="onDailyBriefToggle"
                />
            </SettingsRow>
            <div
                v-if="currentUser.daily_brief_enabled && !pushSubscribed && pushVapidConfigured && pushSupported"
                class="settings-page__note dora-text-muted"
            >
                Turn on push notifications above to receive it on this device.
            </div>
        </SettingsSection>

        <!-- Email. Gated on `products` (data-presence): the weekly deals email
             is currently the only thing Dora mails on a schedule, and with no
             product data ingested there's no deal source — so with products
             absent the whole channel is hidden, here and as the admin
             users-page column (owner feedback). Also SMTP-gated.
             (No alerts email digest — cut at Step-0 Q4,
             `IMPL_PLAN_STOCK_SIGNAL_CONSOLIDATION.md`.) -->
        <template v-if="productsEnabled">
            <hr class="settings-divider" />

            <SettingsSection>
                <template #title>Email notifications</template>

                <ChannelSetupNote
                    v-if="!emailSmtpConfigured"
                    channel="email"
                    :is-admin="isAdmin"
                />
                <!-- FU-789: the deals job skips an unverified address on
                     purpose — it's the only mail Dora sends repeatedly and
                     unprompted, and an unverified address is one nobody has
                     proved they own. Said here rather than only in a server
                     log, so the toggle can't sit on while nothing arrives with
                     no way to find out why. -->
                <SettingsNotice
                    v-else-if="!currentUser.email_verified"
                    title="Your email address isn't verified"
                >
                    Scheduled emails only go to verified addresses, so nothing
                    below will arrive until you confirm yours. Check your inbox
                    for the verification link, or send yourself a fresh one.
                    <template #actions>
                        <BaseButton
                            variant="secondary"
                            :icon="ICONS.mark_email_read"
                            label="Send verification email"
                            :disable="resendingVerification"
                            @click="onResendVerification"
                        />
                    </template>
                </SettingsNotice>

                <SettingsRow inline>
                    <template #label>
                        Weekly deals
                        <InfoTip label="Weekly deals">
                            Automated deals email making use of regular product
                            data pushed into Dora.
                        </InfoTip>
                    </template>
                    <q-toggle
                        :model-value="currentUser.deals_email_enabled"
                        :disable="!emailSmtpConfigured"
                        aria-label="Subscribe me to the weekly deals email"
                        @update:model-value="onDealsEnabledChange"
                    />
                </SettingsRow>

                <template v-if="currentUser.deals_email_enabled">
                    <SettingsRow inline label="Send on">
                        <q-select
                            v-model="sendDealsOnDay"
                            :options="dayOptions"
                            option-value="value"
                            option-label="label"
                            emit-value
                            map-options
                            outlined
                            dense
                            class="deals-day-select"
                            @update:model-value="onSendDealsOnDayChange"
                        />
                    </SettingsRow>

                    <SettingsRow inline>
                        <template #label>
                            Compact format
                            <!-- This used to promise "images and store logos".
                                 It never could: product images are served from
                                 an authenticated endpoint an email client has
                                 no session for, so every one would render as a
                                 broken box. Corrected when the email was
                                 actually built (FU-789) rather than left as
                                 copy describing a mail nobody had written. -->
                            <InfoTip label="Compact format">
                                One line per deal: name, price, discount and
                                store. Off sends a card per deal.
                            </InfoTip>
                        </template>
                        <q-toggle
                            :model-value="currentUser.deals_email_compact"
                            @update:model-value="onDealsCompactChange"
                        />
                    </SettingsRow>
                </template>
            </SettingsSection>
        </template>
    </div>
</template>

<script lang="ts" setup>
    import { storeToRefs } from 'pinia';
    import { useAuthStore } from 'src/stores/authStore';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import { usePushSubscription } from 'src/composables/usePushSubscription';
    import { computed, onMounted, ref, watch } from 'vue';
    import { useSettingsSave } from 'src/composables/useSettingsSave';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import { ICONS } from 'src/style/icons';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import ChannelSetupNote from 'src/components/settings/ChannelSetupNote.vue';
    import SettingsNotice from 'src/components/settings/SettingsNotice.vue';
    import InfoTip from 'src/components/help/InfoTip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import AuthApiService from 'src/services/api/authApiService';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import AlertKindAvatar from 'src/components/AlertKindAvatar.vue';
    import { kindTheme, type AlertKind } from 'src/models/alert';
    import { useAlertPrefsStore } from 'src/stores/alertPrefsStore';
    import { useAlertStore } from 'src/stores/alertStore';
    import PriceHistoryApiService, { type PriceAlert } from 'src/services/api/priceHistoryApiService';

    const authStore = useAuthStore();
    const { currentUser } = storeToRefs(authStore);

    // `products` is a data-presence gate (true iff product data has been
    // ingested) — the deals-email feature's whole information source. No data
    // ⇒ the deals section is hidden here and the column is dropped on the
    // admin users page (owner feedback).
    const { emailSmtpConfigured, pushVapidConfigured, products: productsEnabled } = useFeatureFlags();
    const isAdmin = computed(() => currentUser.value?.is_admin === true);
    const {
        state: pushState,
        error: pushError,
        subscribed: pushSubscribed,
        supported: pushSupported,
        subscribe: pushSubscribe,
        unsubscribe: pushUnsubscribe,
    } = usePushSubscription();
    const pushLoading = computed(() => pushState.value === 'loading');

    const dayOptions = [
        { value: 0, label: 'Monday' },
        { value: 1, label: 'Tuesday' },
        { value: 2, label: 'Wednesday' },
        { value: 3, label: 'Thursday' },
        { value: 4, label: 'Friday' },
        { value: 5, label: 'Saturday' },
        { value: 6, label: 'Sunday' }
    ];

    const sendDealsOnDay = ref<number>(currentUser.value?.send_deals_on_day ?? 0);

    // R-003 / FU-601 — shared save-toast helper (see useSettingsSave).
    const { notifySuccess, notifyError, update } = useSettingsSave();

    watch(currentUser, (u) => {
        if (!u) return;
        sendDealsOnDay.value = u.send_deals_on_day ?? 0;
    });

    async function onSendDealsOnDayChange(value: number) {
        const previous = currentUser.value?.send_deals_on_day ?? 0;
        const result = await update('Weekly deals day updated.', () =>
            authStore.updateMeAsync({ send_deals_on_day: value })
        );
        if (result === null) sendDealsOnDay.value = previous;
    }

    async function onDealsEnabledChange(value: boolean) {
        await update(
            value
                ? 'Subscribed to the weekly deals email.'
                : 'Unsubscribed from the weekly deals email.',
            () => authStore.updateMeAsync({ deals_email_enabled: value })
        );
    }

    async function onDealsCompactChange(value: boolean) {
        await update('Deals email format updated.', () =>
            authStore.updateMeAsync({ deals_email_compact: value })
        );
    }

    async function onDailyBriefToggle(value: boolean) {
        await update(
            value
                ? "You'll get an evening brief when there's something to say."
                : 'Evening brief turned off.',
            () => authStore.updateMeAsync({ daily_brief_enabled: value }),
        );
    }

    // FU-789 — resend from here rather than sending the user off to a page
    // that has no such control. The endpoint always answers 204 (it's
    // deliberately anti-enumeration and rate-limited to 1/min), so the toast
    // promises "if that address needs it" rather than claiming a send.
    const authApi = new AuthApiService();
    const resendingVerification = ref(false);
    async function onResendVerification() {
        const email = currentUser.value?.email;
        if (!email) return;
        resendingVerification.value = true;
        try {
            await authApi.resendVerificationAsync(email);
            notifySuccess(`Verification email on its way to ${email}.`);
        } catch (err) {
            notifyError("Couldn't send the verification email.", err);
        } finally {
            resendingVerification.value = false;
        }
    }

    // ── In-app alerts ──────────────────────────────────────────────────
    const alertPrefsStore = useAlertPrefsStore();
    const alertStore = useAlertStore();
    const { moneyEnabled } = useMoneyEnabled();

    const discardOptions = [
        { value: 7, label: '7 days' },
        { value: 14, label: '14 days' },
        { value: 30, label: '30 days' },
        { value: null, label: 'Never' },
    ];

    /** The kinds worth a toggle on this install (server decides). */
    const visiblePrefs = computed(() => alertPrefsStore.prefs.filter((p) => p.available));

    function kindLabel(kind: AlertKind): string {
        const theme = kindTheme(kind);
        return theme.charAt(0).toUpperCase() + theme.slice(1);
    }

    const prefBusy = ref<Set<string>>(new Set());
    async function onToggleKind(kind: AlertKind, enabled: boolean) {
        prefBusy.value = new Set([...prefBusy.value, kind]);
        try {
            await update(
                enabled ? 'Alerts turned on.' : 'Alerts turned off.',
                () => alertPrefsStore.setEnabled(kind, enabled),
            );
            await alertStore.refreshAsync();
        } finally {
            const next = new Set(prefBusy.value);
            next.delete(kind);
            prefBusy.value = next;
        }
    }

    async function onDiscardChange(value: number | null) {
        await update('Alert discard window updated.', () =>
            authStore.updateMeAsync({ alert_discard_after_days: value }),
        );
        await alertStore.refreshAsync();
    }

    const priceHistoryApi = new PriceHistoryApiService();
    const watches = ref<PriceAlert[]>([]);
    const removingWatch = ref<string | null>(null);
    async function loadWatches() {
        if (!moneyEnabled.value) return;
        try {
            watches.value = (await priceHistoryApi.listAlertsAsync()).items;
        } catch {
            watches.value = [];
        }
    }
    async function onRemoveWatch(watch: PriceAlert) {
        removingWatch.value = watch.price_alert_id;
        try {
            await priceHistoryApi.deleteAlertAsync(watch.price_alert_id);
            watches.value = watches.value.filter((w) => w.price_alert_id !== watch.price_alert_id);
            notifySuccess(`Stopped watching ${watch.product_name}.`);
        } catch (err) {
            notifyError("Couldn't remove the price watch.", err);
        } finally {
            removingWatch.value = null;
        }
    }

    onMounted(() => {
        void alertPrefsStore.refreshAsync();
        void loadWatches();
    });

    async function onPushToggle(value: boolean) {
        try {
            if (value) {
                await pushSubscribe();
                if (pushSubscribed.value) notifySuccess('Subscribed to push notifications on this device.');
            } else {
                await pushUnsubscribe();
                notifySuccess('Unsubscribed from push notifications on this device.');
            }
        } catch (err) {
            notifyError('Push subscription failed.', err);
        }
    }
</script>

<style scoped lang="scss">
    /* Stays on the right at every width (owner 2026-09-03), so no fixed floor
       that would overflow the control column on a phone. */
    .deals-day-select {
        width: 180px;
        max-width: 100%;
    }
    .settings-page__note {
        font-size: var(--font-size-sm);
        line-height: 1.4;
        margin-top: var(--space-1);
    }
    .settings-page__subhead {
        margin-top: var(--space-3);
        font-size: var(--font-size-sm);
        font-weight: 600;
        color: var(--text-secondary);
    }
    .watch-list {
        border: 1px solid var(--border-default);
        border-radius: var(--radius-md);
    }
</style>
