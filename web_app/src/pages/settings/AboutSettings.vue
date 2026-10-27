<template>
    <div class="settings-page">
        <!-- Owner rebuild 2026-08-17: the page used to open on a build label
             and "Quasar 2 / Vue 3, talks to the Flask API over CORS" — true,
             but written for whoever wrote it. It now opens on what Dora is
             and what this household has going, with the operator-facing bits
             last. -->
        <header class="about-hero">
            <q-avatar size="72px" square>
                <img src="../../assets/logo-mascot.png" alt="Dashy Dora" />
            </q-avatar>
            <div class="about-hero__text">
                <h1 class="about-hero__title">
                    <DoraBrand inline />
                </h1>
                <p class="about-hero__tagline dora-text-muted">
                    Your pantry at your fingertips.
                </p>
            </div>
        </header>

        <ul class="about-does">
            <li v-for="line in whatDoraDoes" :key="line.text" class="about-does__item">
                <q-icon :name="line.icon" size="20px" class="about-does__icon" />
                <span>{{ line.text }}</span>
            </li>
        </ul>

        <hr class="settings-divider settings-divider--spaced" />

        <!-- Counts are server-owned aggregates (R-003) — a read of an existing
             fact, not a second tally that could disagree with another surface.
             Hidden entirely if the fetch fails: a stats block is a nicety, and
             half of one is worse than none.
             Owner 2026-09-05: retitled with the numbers. It used to say "Your
             kitchen at a glance" over the dashboard's current-state counts,
             which made it a second dashboard; it now counts what the household
             has done with Dora over its whole life. -->
        <SettingsSection v-if="stats.length">
            <template #title>How you've used Dora</template>

            <div class="about-stats">
                <div v-for="stat in stats" :key="stat.label" class="about-stat">
                    <div class="about-stat__value">{{ stat.value }}</div>
                    <div class="about-stat__label">{{ stat.label }}</div>
                </div>
            </div>
        </SettingsSection>

        <hr v-if="stats.length && !isNative" class="settings-divider settings-divider--spaced" />

        <!-- Inside the Capacitor shell the user IS in the app; the browser
             install prompt can never fire there and the section fell through
             to "Install isn't available in this browser. Try Chrome…"
             (finalisation 17-R9). -->
        <SettingsSection v-if="!isNative">
            <template #title>Install as an app</template>
            <template #description>
                Adds a Dora icon to your home screen or launcher.
            </template>

            <div class="about-install">
                <PwaInstallPrompt size="lg" />
            </div>
        </SettingsSection>

        <hr class="settings-divider settings-divider--spaced" />

        <!-- Open-source project & support links. The "Report" row is gated on
             a configured support channel (useSupportChannel /
             support_channel.py). -->
        <SettingsSection>
            <template #title>Project &amp; support</template>
            <template #description>
                Dora is a free, open-source (MIT) hobby project.
            </template>

            <q-list class="about-list">
                <q-item
                    clickable
                    tag="a"
                    :href="REPO_URL"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    <q-item-section avatar>
                        <q-icon :name="ICONS.code" size="20px" />
                    </q-item-section>
                    <q-item-section>
                        <q-item-label>Source code</q-item-label>
                        <q-item-label caption>GitHub · BenTalese/dashy-dora</q-item-label>
                    </q-item-section>
                    <q-item-section side>
                        <q-icon :name="ICONS.open_in_new" size="18px" />
                    </q-item-section>
                </q-item>

                <q-item
                    v-if="hasChannel"
                    clickable
                    tag="a"
                    :href="reportHref"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    <q-item-section avatar>
                        <q-icon :name="ICONS.bug_report" size="20px" />
                    </q-item-section>
                    <q-item-section>
                        <q-item-label>Report a bug or request a feature</q-item-label>
                        <q-item-label caption>Opens a new issue on GitHub.</q-item-label>
                    </q-item-section>
                    <q-item-section side>
                        <q-icon :name="ICONS.open_in_new" size="18px" />
                    </q-item-section>
                </q-item>

                <q-item clickable :to="'/help'">
                    <q-item-section avatar>
                        <q-icon :name="ICONS.help_outline" size="20px" />
                    </q-item-section>
                    <q-item-section>
                        <q-item-label>Help &amp; guides</q-item-label>
                        <q-item-label caption>How each part of Dora works.</q-item-label>
                    </q-item-section>
                    <q-item-section side>
                        <q-icon :name="ICONS.chevron_right" size="18px" />
                    </q-item-section>
                </q-item>

                <q-item
                    clickable
                    tag="a"
                    :href="PRIMARY_DONATION.url"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    <q-item-section avatar>
                        <q-icon :name="ICONS.favorite" size="20px" :style="{ color: 'var(--donate)' }" />
                    </q-item-section>
                    <q-item-section>
                        <q-item-label>Support Dora</q-item-label>
                        <q-item-label caption>Donations keep the project going 💗</q-item-label>
                    </q-item-section>
                    <q-item-section side>
                        <q-icon :name="ICONS.open_in_new" size="18px" />
                    </q-item-section>
                </q-item>
            </q-list>
        </SettingsSection>

        <hr class="settings-divider settings-divider--spaced" />

        <!-- Third-party art credits. The pre-made profile pictures are
             Fluent Emoji (MIT); the licence text ships beside the PNGs in
             src/assets/avatars/. -->
        <SettingsSection>
            <template #title>Credits</template>

            <q-list class="about-list">
                <q-item
                    clickable
                    tag="a"
                    href="https://github.com/microsoft/fluentui-emoji"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    <q-item-section avatar>
                        <q-icon :name="ICONS.palette" size="20px" />
                    </q-item-section>
                    <q-item-section>
                        <q-item-label>Profile picture art</q-item-label>
                        <q-item-label caption>
                            Fluent Emoji © Microsoft Corporation, MIT licence
                        </q-item-label>
                    </q-item-section>
                    <q-item-section side>
                        <q-icon :name="ICONS.open_in_new" size="18px" />
                    </q-item-section>
                </q-item>
            </q-list>
        </SettingsSection>

        <hr class="settings-divider settings-divider--spaced" />

        <SettingsSection>
            <template #title>Technical details</template>
            <template #description>
                Only useful when reporting a problem.
            </template>

            <q-list class="about-list">
                <q-item>
                    <q-item-section>
                        <q-item-label>Build</q-item-label>
                        <q-item-label caption>
                            Versioning isn't tagged in this fork yet.
                        </q-item-label>
                    </q-item-section>
                    <q-item-section side>
                        <q-chip dense class="dora-bg-sunken dora-text-secondary">{{ buildLabel }}</q-chip>
                    </q-item-section>
                </q-item>

                <!-- Native builds only. In a browser the app is served by the
                     same host it talks to, so the URL is neither editable nor
                     interesting (owner, 2026-08-17); in the Android/iOS shell
                     it's the only way to point at your server. -->
                <q-item v-if="isNative">
                    <q-item-section>
                        <q-item-label>Dora API endpoint</q-item-label>
                        <q-item-label caption class="text-mono">{{ doraApiUrl }}</q-item-label>
                    </q-item-section>
                    <q-item-section side>
                        <BaseButton
                            variant="secondary"
                            size="sm"
                            :icon="ICONS.edit"
                            label="Change"
                            @click="onChangeInstance"
                        />
                    </q-item-section>
                </q-item>
            </q-list>
        </SettingsSection>

    </div>
</template>

<script lang="ts" setup>
    import BaseButton from 'src/components/BaseButton.vue';
    import { ICONS } from 'src/style/icons';
    import { useQuasar } from 'quasar';
    import PwaInstallPrompt from 'src/components/PwaInstallPrompt.vue';
    import DoraBrand from 'src/components/DoraBrand.vue';
    import { computed, onMounted, ref } from 'vue';
    import { useRouter } from 'vue-router';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import { useSupportChannel, supportHref } from 'src/composables/useSupportChannel';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import DashboardApiService from 'src/services/api/dashboardApiService';
    import type { UsageStats } from 'src/services/api/dashboardApiService';
    import { formatMoney } from 'src/composables/useMoney';
    import { PRIMARY_DONATION } from 'src/config/donationLinks';
    import {
        getBackendBaseUrl,
        isNativePlatform,
        setBackendBaseUrl,
    } from 'src/services/api/backendUrl';

    // Public repo (source-code link). The bug-report target comes from the
    // gated support channel, not hardcoded here.
    const REPO_URL = 'https://github.com/BenTalese/dashy-dora';

    const $q = useQuasar();
    const router = useRouter();

    const { channel, hasChannel } = useSupportChannel();
    const reportHref = computed(() => supportHref(channel.value));

    // The money line only claims what this install actually does — an
    // install with money off shouldn't be told Dora tracks prices.
    const { money: moneyEnabled } = useFeatureFlags();

    const whatDoraDoes = computed(() => {
        const lines: { icon: string; text: string }[] = [
            {
                icon: ICONS.inventory_2,
                text: 'Keeps track of what\'s in your kitchen, and what\'s running out.',
            },
            {
                icon: ICONS.restaurant,
                text: 'Tells you what you can cook tonight from what you already have.',
            },
        ];
        lines.push({
            icon: ICONS.event_note,
            text: 'Plans your week of meals and turns it into a shopping list.',
        });
        if (moneyEnabled.value) {
            lines.push({
                icon: ICONS.savings,
                text: 'Remembers what you paid, so you know a good price when you see one.',
            });
        }
        return lines;
    });

    // ── "At a glance" ──────────────────────────────────────────────────
    // Owner 2026-09-05: this block used to read `/dashboard/summary`, so it
    // showed what the *dashboard* shows — items running low, items out of
    // stock, meals coming up. That is a to-do list, and it belongs on the
    // dashboard where the user can act on it. Standing on the About page it
    // restated the home screen and changed every time you shopped.
    //
    // These are cumulative instead: what this household has built up and done
    // with Dora. Every figure only ever goes up.
    const usage = ref<UsageStats | null>(null);
    const dashboardApi = new DashboardApiService();

    /** Thousands-separated, because these are the numbers that get big —
     *  "1208 prices recorded" is the one figure on this page a user might
     *  actually want to read aloud. Locale-aware via the browser, matching how
     *  `formatMoney` defers to the install's region. */
    const formatCount = (n: number) => n.toLocaleString();

    onMounted(async () => {
        try {
            usage.value = await dashboardApi.getUsageStatsAsync();
        } catch {
            // Silent: this block is decoration, and a real API outage is
            // surfaced loudly by the surfaces that depend on it.
            usage.value = null;
        }
    });

    /** Values are pre-formatted strings, not numbers — `total_spend` is money
     *  and the rest are counts, and they share one tile shape. */
    const stats = computed<{ value: string; label: string }[]>(() => {
        const u = usage.value;
        if (!u) return [];
        const plural = (n: number, one: string, many: string) => (n === 1 ? one : many);
        const out = [
            { value: formatCount(u.stock_items), label: plural(u.stock_items, 'item tracked', 'items tracked') },
            { value: formatCount(u.recipes), label: plural(u.recipes, 'recipe curated', 'recipes curated') },
            { value: formatCount(u.meals_planned), label: plural(u.meals_planned, 'meal planned', 'meals planned') },
            { value: formatCount(u.meals_cooked), label: plural(u.meals_cooked, 'cook logged', 'cooks logged') },
            { value: formatCount(u.shopping_lists), label: plural(u.shopping_lists, 'shopping list', 'shopping lists') },
            { value: formatCount(u.shops_completed), label: plural(u.shops_completed, 'shop finished', 'shops finished') },
        ];
        // Money-gated (R-058). The server sends null rather than 0 when the
        // opt-in is off, so the tiles disappear instead of claiming this
        // household has spent nothing.
        if (u.total_spend !== null) {
            out.push({ value: formatMoney(u.total_spend), label: 'spend tracked' });
        }
        if (u.prices_recorded !== null) {
            out.push({
                value: formatCount(u.prices_recorded),
                label: plural(u.prices_recorded, 'price recorded', 'prices recorded'),
            });
        }
        return out;
    });

    // ── Technical details ──────────────────────────────────────────────
    const isNative = isNativePlatform();

    // surface the live backend URL (which now includes the
    // Capacitor/localStorage runtime override), not just the build-time
    // env, so a user who swapped instances from Settings sees the change.
    const currentBackend = ref(getBackendBaseUrl());
    const doraApiUrl = computed(() => currentBackend.value || 'not configured');

    async function onChangeInstance() {
        const initial = getBackendBaseUrl();
        const url = await new Promise<string | null>((resolve) => {
            $q.dialog({
                title: 'Change instance URL',
                message:
                    "Point this app at a different Dora backend. Enter the "
                    + "full URL you'd type in a browser. /api is added "
                    + "automatically if you leave it off.",
                prompt: {
                    model: initial,
                    type: 'url',
                    isValid: (v: string) => v.trim().length > 0,
                },
                ok: { label: 'Save', color: 'primary', noCaps: true },
                cancel: { noCaps: true },
            })
                .onOk((v: string) => resolve(v))
                .onCancel(() => resolve(null))
                .onDismiss(() => resolve(null));
        });
        if (!url) return;
        try {
            const normalised = await setBackendBaseUrl(url);
            currentBackend.value = normalised;
            $q.notify({
                type: 'positive', 
                message: 'Instance URL saved. Refreshing…',
                timeout: 1500,
            });
            // Full reload so every cached query + auth state is rebuilt
            // against the new backend — a soft nav would keep the old
            // Pinia stores alive and cause hard-to-debug staleness.
            setTimeout(() => {
                void router.replace('/');
                window.location.reload();
            }, 400);
        } catch (err) {
            $q.notify({
                type: 'negative',
                message: 'Could not save the URL.',
                caption: toastCaption(err),
            });
        }
    }

    const buildLabel = computed(() => (import.meta.env.PROD ? 'production' : 'dev'));
</script>

<style scoped lang="scss">
    .settings-page { display: flex; flex-direction: column; }

    .about-hero {
        display: flex;
        align-items: center;
        gap: 16px;
        padding-bottom: 12px;
    }
    .about-hero__text { min-width: 0; }
    .about-hero__title {
        margin: 0;
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1.1;
    }
    .about-hero__tagline {
        margin: 4px 0 0;
        font-size: 0.9375rem;
    }

    .about-does {
        list-style: none;
        margin: 0 0 4px;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    .about-does__item {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        font-size: 0.9375rem;
        line-height: 1.4;
        color: var(--text-primary);
    }
    .about-does__icon {
        flex: 0 0 auto;
        margin-top: 1px;
        color: var(--brand-primary);
    }

    /* auto-fit rather than a fixed column count: four tiles on a wide pane,
       two on a phone, without a breakpoint per layout. */
    .about-stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
        gap: 10px;
    }
    /* Two fixed columns on a phone, and an odd tile at the end spans both so
       the block never ends on a lonely half-row (owner 2026-09-03). */
    @media (max-width: 599px) {
        .about-stats {
            grid-template-columns: repeat(2, 1fr);
        }
        .about-stat:last-child:nth-child(odd) {
            grid-column: 1 / -1;
        }
    }
    .about-stat {
        background: var(--surface-sunken);
        border-radius: 10px;
        padding: 12px;
        text-align: center;
    }
    .about-stat__value {
        font-size: 1.5rem;
        font-weight: 700;
        line-height: 1.1;
        color: var(--text-primary);
    }
    .about-stat__label {
        margin-top: 2px;
        font-size: 0.8125rem;
        color: var(--text-secondary);
        line-height: 1.3;
    }

    .about-install { display: flex; }

    .about-list {
        border-top: 1px solid color-mix(in srgb, var(--text-primary) 8%, transparent);
    }
    .about-list :deep(.q-item) {
        border-bottom: 1px solid color-mix(in srgb, var(--text-primary) 6%, transparent);
        padding: 12px 4px;
    }
    /* Mobile: the side column (chip / button) was being squeezed to a sliver
       beside a long two-line label, which is what made this page look broken
       on a phone. Below 600px each row stacks its side content underneath,
       left-aligned with the label. */
    @media (max-width: 599px) {
        .about-list :deep(.q-item) {
            flex-wrap: wrap;
        }
        .about-list :deep(.q-item__section--side) {
            padding-left: 0;
            align-items: flex-start;
        }
        .about-hero { gap: 12px; }
        .about-hero__title { font-size: 1.25rem; }
    }

    .text-mono {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
</style>
