<template>
    <!-- Help landing (2026-10-29 redesign, 20-D4): a search over every guide,
         one card per topic, the question-shaped guides as Common questions,
         and two quiet doors to What's new and About. `/help?q=<title>` from
         a (?) chip resolves straight to its guide. -->
    <HelpShell>
        <header class="help-hero">
            <DoraMascot mood="cute" :size="72" class="help-hero__mascot" />
            <div class="help-hero__text">
                <h1 class="help-hero__title">How can I help?</h1>
                <p class="help-hero__sub">Short guides for every part of Dora.</p>
            </div>
        </header>

        <q-input
            ref="searchInput"
            v-model="query"
            outlined
            clearable
            placeholder="Search the guides"
            class="help-search"
            :aria-label="'Search the guides'"
        >
            <template #prepend><q-icon :name="ICONS.search" /></template>
        </q-input>

        <!-- Results ─────────────────────────────────────────────── -->
        <section v-if="query.trim()" class="help-section" aria-live="polite">
            <h2 class="help-section__title">
                {{ hits.length ? `${hits.length} ${hits.length === 1 ? 'guide' : 'guides'}` : 'No guides match' }}
            </h2>
            <p v-if="!hits.length" class="help-empty">
                Nothing for "{{ query }}". Try a shorter word, or ask Dora in the chat.
            </p>
            <ul v-else class="help-hits">
                <li v-for="hit in hits" :key="`${hit.topic.slug}/${hit.entry.slug}`">
                    <router-link :to="guideLink(hit)" class="help-hit">
                        <span class="help-hit__topic">
                            <q-icon :name="hit.topic.icon" size="16px" />
                            <span>{{ hit.topic.title }}</span>
                        </span>
                        <span class="help-hit__title">{{ hit.entry.title }}</span>
                        <span class="help-hit__summary">{{ hit.entry.summary }}</span>
                    </router-link>
                </li>
            </ul>
        </section>

        <!-- Topics ──────────────────────────────────────────────── -->
        <template v-else>
            <section class="help-section">
                <div class="help-topics">
                    <HelpTopicCard v-for="topic in HELP_TOPICS" :key="topic.slug" :topic="topic" />
                </div>
            </section>

            <section class="help-section">
                <h2 class="help-section__title">Common questions</h2>
                <ul class="help-faq">
                    <li v-for="hit in faq" :key="hit.entry.slug">
                        <router-link :to="guideLink(hit)" class="help-faq__link">
                            <q-icon :name="ICONS.help_outline" size="18px" />
                            <span>{{ hit.entry.title }}</span>
                        </router-link>
                    </li>
                </ul>
            </section>

            <section class="help-doors">
                <router-link to="/help/whats-new" class="help-door">
                    <q-icon :name="ICONS.new_releases" size="22px" class="help-door__icon" />
                    <span class="help-door__text">
                        <span class="help-door__title">What's new</span>
                        <span class="help-door__sub">Recent changes, newest first.</span>
                    </span>
                    <q-icon :name="ICONS.chevron_right" size="18px" class="help-door__chevron" />
                </router-link>
                <router-link to="/help/about" class="help-door">
                    <q-icon :name="ICONS.info" size="22px" class="help-door__icon" />
                    <span class="help-door__text">
                        <span class="help-door__title">About and support</span>
                        <span class="help-door__sub">Your version, updates, reporting a problem.</span>
                    </span>
                    <q-icon :name="ICONS.chevron_right" size="18px" class="help-door__chevron" />
                </router-link>
            </section>
        </template>
    </HelpShell>
</template>

<script setup lang="ts">
    import { computed, onMounted, ref, watch } from 'vue';
    import { useRoute, useRouter } from 'vue-router';
    import type { QInput } from 'quasar';
    import DoraMascot from 'src/components/dora/DoraMascot.vue';
    import HelpShell from 'src/components/help/HelpShell.vue';
    import HelpTopicCard from 'src/components/help/HelpTopicCard.vue';
    import {
        HELP_TOPICS,
        faqEntries,
        resolveDeepLink,
        searchHelp,
        type HelpHit,
    } from 'src/help/helpContent';
    import { ICONS } from 'src/style/icons';

    const route = useRoute();
    const router = useRouter();

    const searchInput = ref<QInput | null>(null);
    const initialQuery = typeof route.query.q === 'string' ? route.query.q : '';
    const query = ref(initialQuery);

    const hits = computed<HelpHit[]>(() => searchHelp(query.value ?? ''));
    const faq = faqEntries();

    function guideLink(hit: HelpHit): string {
        return `/help/${hit.topic.slug}?e=${hit.entry.slug}`;
    }

    // A (?) chip's `?q=<title>` means "show me this guide", not "search".
    onMounted(() => {
        const hit = initialQuery ? resolveDeepLink(initialQuery) : null;
        if (hit) {
            void router.replace(guideLink(hit));
            return;
        }
        if (initialQuery) searchInput.value?.focus();
    });

    // Keep the address in step so a search can be shared or refreshed.
    watch(query, (q) => {
        const trimmed = (q ?? '').trim();
        void router.replace({ path: '/help', query: trimmed ? { q: trimmed } : {} });
    });
</script>

<style scoped lang="scss">
    .help-hero {
        display: flex;
        align-items: center;
        gap: var(--space-4);
    }
    .help-hero__mascot {
        flex: 0 0 auto;
    }
    .help-hero__text {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .help-hero__title {
        margin: 0;
        font-size: var(--font-size-2xl);
        font-weight: 700;
        letter-spacing: -0.01em;
        line-height: 1.15;
        color: var(--text-primary);
    }
    .help-hero__sub {
        margin: 0;
        font-size: var(--font-size-md);
        color: var(--text-secondary);
    }
    .help-search {
        margin-top: calc(-1 * var(--space-2));
    }
    .help-search :deep(.q-field__control) {
        border-radius: var(--radius-xl);
        min-height: 52px;
        background: var(--surface-component);
    }
    .help-section {
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
    }
    .help-section__title {
        margin: 0;
        font-size: var(--font-size-xs);
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--text-muted);
    }
    .help-topics {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
        gap: var(--space-3);
    }
    .help-faq {
        list-style: none;
        margin: 0;
        padding: 0;
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: var(--space-1) var(--space-4);
    }
    .help-faq__link {
        display: inline-flex;
        align-items: center;
        gap: var(--space-2);
        min-height: 40px;
        padding: 0 var(--space-2);
        margin-left: calc(-1 * var(--space-2));
        border-radius: var(--radius-md);
        color: var(--text-primary);
        font-size: var(--font-size-sm);
        font-weight: 600;
        text-decoration: none;
    }
    .help-faq__link .q-icon {
        color: var(--accent-mark);
    }
    .help-faq__link:hover {
        background: var(--surface-sunken);
    }
    .help-faq__link:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    .help-doors {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: var(--space-3);
        padding-top: var(--space-2);
        border-top: 1px solid var(--divider);
    }
    .help-door {
        display: grid;
        grid-template-columns: auto 1fr auto;
        align-items: center;
        gap: var(--space-3);
        min-height: 56px;
        padding: var(--space-3) var(--space-4);
        border-radius: var(--radius-lg);
        color: var(--text-primary);
        text-decoration: none;
        transition: background var(--motion-fast) var(--motion-ease);
    }
    .help-door:hover {
        background: var(--surface-sunken);
    }
    .help-door:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    .help-door__icon {
        color: var(--accent-mark);
    }
    .help-door__text {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
    }
    .help-door__title {
        font-size: var(--font-size-sm);
        font-weight: 700;
    }
    .help-door__sub {
        font-size: var(--font-size-xs);
        color: var(--text-muted);
    }
    .help-door__chevron {
        color: var(--text-muted);
    }
    .help-hits {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
    }
    .help-hit {
        display: flex;
        flex-direction: column;
        gap: 2px;
        padding: var(--space-3) var(--space-4);
        background: var(--surface-component);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        box-shadow: var(--elevation-card);
        color: var(--text-primary);
        text-decoration: none;
        transition: border-color var(--motion-fast) var(--motion-ease), box-shadow var(--motion-fast) var(--motion-ease);
    }
    .help-hit:hover {
        border-color: var(--border-strong);
        box-shadow: var(--elevation-card-hover);
    }
    .help-hit:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    .help-hit__topic {
        display: inline-flex;
        align-items: center;
        gap: var(--space-1);
        font-size: var(--font-size-xs);
        font-weight: 600;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .help-hit__title {
        font-size: var(--font-size-md);
        font-weight: 700;
    }
    .help-hit__summary {
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
        line-height: 1.45;
    }
    .help-empty {
        margin: 0;
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
    }
    @media (max-width: 599px) {
        .help-hero__title {
            font-size: var(--font-size-xl);
        }
    }
</style>
