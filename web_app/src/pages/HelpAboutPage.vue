<template>
    <!-- About and support: which Dora this is, whether a newer one exists, and
         how to get help. Honest one-person-project copy (FU-370), kept short. -->
    <HelpShell :crumb="{ label: 'Help', to: '/help' }">
        <header class="help-plain-head">
            <h1 class="help-plain-head__title">About and support</h1>
            <p class="help-plain-head__sub">Your version, updates, and reporting a problem.</p>
        </header>

        <section class="help-about-card">
            <div class="help-about-card__row">
                <div>
                    <div class="help-about-card__label">Version</div>
                    <div class="help-about-card__value">
                        Dashy Dora {{ versionInfo?.current_version ?? '…' }}
                    </div>
                </div>
                <span v-if="versionInfo" class="help-about-pill" :class="pillClass">{{ pillText }}</span>
            </div>
            <p v-if="versionInfo?.update_available" class="help-about-card__note">
                {{ versionInfo.latest_version }} is out. Updating is a job for whoever runs this Dora.
                <a
                    v-if="versionInfo.release_url"
                    :href="versionInfo.release_url"
                    target="_blank"
                    rel="noopener"
                    class="help-about-link"
                >Release notes</a>
            </p>
            <p v-else-if="versionInfo && versionInfo.latest_version === null" class="help-about-card__note">
                Couldn't check for updates ({{ versionInfo.error ?? 'unknown reason' }}).
            </p>
        </section>

        <section class="help-about-card">
            <div class="help-about-card__label">Getting help</div>
            <p class="help-about-card__text">
                Dora is built by one person as a side project. Every report is read; replies can take a while.
                If a family member set up this Dora for you, ask them first.
            </p>
            <p v-if="hasChannel" class="help-about-card__text">
                Note the steps you took, what you expected and what happened. A ref code on an error helps.
            </p>
            <p v-else class="help-about-card__text">
                Note the steps you took, what you expected and what happened, and pass it to whoever runs this Dora.
            </p>
            <div class="help-about-card__actions">
                <BaseButton
                    v-if="hasChannel"
                    variant="primary"
                    :icon="ICONS.bug_report"
                    label="Report an issue"
                    :href="reportHref"
                    target="_blank"
                />
                <BaseButton variant="subtle" :icon="ICONS.smart_toy" label="Meet Dora" to="/help/dora" />
                <BaseButton variant="subtle" :icon="ICONS.new_releases" label="What's new" to="/help/whats-new" />
            </div>
        </section>
    </HelpShell>
</template>

<script setup lang="ts">
    import { computed, onMounted, ref } from 'vue';
    import { useRoute } from 'vue-router';
    import BaseButton from 'src/components/BaseButton.vue';
    import HelpShell from 'src/components/help/HelpShell.vue';
    import { supportHref, useSupportChannel } from 'src/composables/useSupportChannel';
    import HelpApiService, { type VersionInfo } from 'src/services/api/helpApiService';
    import { ICONS } from 'src/style/icons';

    const route = useRoute();
    const helpApi = new HelpApiService();
    const versionInfo = ref<VersionInfo | null>(null);

    const { channel, hasChannel } = useSupportChannel();
    const reportHref = computed(() =>
        supportHref(channel.value, {
            subject: `[Dora] Bug, v${versionInfo.value?.current_version ?? 'unknown'}`,
            body: `\n\n---\nDora ${versionInfo.value?.current_version ?? 'unknown'} · ${route.path}`,
        }),
    );

    const pillText = computed(() => {
        if (!versionInfo.value) return '';
        if (versionInfo.value.update_available) return 'Update available';
        if (versionInfo.value.latest_version === null) return 'Not checked';
        return 'Up to date';
    });
    const pillClass = computed(() => {
        if (!versionInfo.value) return '';
        if (versionInfo.value.update_available) return 'help-about-pill--warning';
        if (versionInfo.value.latest_version === null) return 'help-about-pill--neutral';
        return 'help-about-pill--positive';
    });

    onMounted(async () => {
        try {
            versionInfo.value = await helpApi.getVersionAsync();
        } catch {
            versionInfo.value = null;
        }
    });
</script>

<style scoped lang="scss">
    .help-plain-head__title {
        margin: 0;
        font-size: var(--font-size-2xl);
        font-weight: 700;
        letter-spacing: -0.01em;
        line-height: 1.15;
        color: var(--text-primary);
    }
    .help-plain-head__sub {
        margin: 2px 0 0;
        font-size: var(--font-size-md);
        color: var(--text-secondary);
    }
    .help-about-card {
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
        padding: var(--space-4);
        background: var(--surface-component);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        box-shadow: var(--elevation-card);
    }
    .help-about-card__row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--space-3);
    }
    .help-about-card__label {
        font-size: var(--font-size-xs);
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--text-muted);
    }
    .help-about-card__value {
        font-size: var(--font-size-lg);
        font-weight: 700;
    }
    .help-about-card__note,
    .help-about-card__text {
        margin: 0;
        font-size: var(--font-size-sm);
        line-height: 1.5;
        color: var(--text-secondary);
    }
    .help-about-card__actions {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-2);
        margin-top: var(--space-2);
    }
    .help-about-link {
        color: var(--accent-ink);
        font-weight: 600;
        text-decoration: none;
        margin-left: var(--space-1);
    }
    .help-about-link:hover {
        text-decoration: underline;
    }
    .help-about-pill {
        font-size: var(--font-size-xs);
        font-weight: 700;
        padding: 0 var(--space-3);
        height: 24px;
        display: inline-grid;
        place-items: center;
        border-radius: var(--radius-pill);
        border: 1px solid transparent;
        white-space: nowrap;
    }
    .help-about-pill--positive {
        background: var(--semantic-positive-soft);
        border-color: var(--semantic-positive);
        color: var(--text-primary);
    }
    .help-about-pill--warning {
        background: var(--semantic-warning-soft);
        border-color: var(--semantic-warning);
        color: var(--text-primary);
    }
    .help-about-pill--neutral {
        background: var(--surface-sunken);
        border-color: var(--border-default);
        color: var(--text-secondary);
    }
</style>
