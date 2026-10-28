<template>
    <!-- One help topic: its guides as a list of cards, one open at a time
         unless you open more. `?e=<slug>` opens that guide and scrolls to it
         (the (?) chips arrive this way via the landing's resolver). -->
    <HelpShell :crumb="{ label: 'Help', to: '/help' }">
        <template v-if="topic">
            <header class="help-topic-head">
                <span class="help-topic-head__icon" aria-hidden="true">
                    <q-icon :name="topic.icon" size="26px" />
                </span>
                <div class="help-topic-head__text">
                    <h1 class="help-topic-head__title">{{ topic.title }}</h1>
                    <p class="help-topic-head__blurb">{{ topic.blurb }}</p>
                </div>
            </header>

            <div class="help-topic-list">
                <HelpEntryCard
                    v-for="entry in topic.entries"
                    :key="entry.slug"
                    :entry="entry"
                    :open="openSlugs.has(entry.slug)"
                    @toggle="toggle(entry.slug)"
                />
            </div>

            <nav class="help-topic-nav" aria-label="Other topics">
                <router-link v-if="prev" :to="`/help/${prev.slug}`" class="help-topic-nav__link">
                    <q-icon :name="ICONS.chevron_left" size="18px" />
                    <span>{{ prev.title }}</span>
                </router-link>
                <span v-else />
                <router-link v-if="next" :to="`/help/${next.slug}`" class="help-topic-nav__link help-topic-nav__link--next">
                    <span>{{ next.title }}</span>
                    <q-icon :name="ICONS.chevron_right" size="18px" />
                </router-link>
            </nav>
        </template>

        <PageErrorState
            v-else
            title="No such topic"
            message="That help topic does not exist. The guides are all one level up."
        />
    </HelpShell>
</template>

<script setup lang="ts">
    import { computed, nextTick, ref, watch } from 'vue';
    import { useRoute } from 'vue-router';
    import HelpEntryCard from 'src/components/help/HelpEntryCard.vue';
    import HelpShell from 'src/components/help/HelpShell.vue';
    import PageErrorState from 'src/components/PageErrorState.vue';
    import { HELP_TOPICS, topicBySlug } from 'src/help/helpContent';
    import { ICONS } from 'src/style/icons';

    const route = useRoute();

    const topic = computed(() => topicBySlug(String(route.params.group ?? '')));
    const index = computed(() => HELP_TOPICS.findIndex((t) => t.slug === topic.value?.slug));
    const prev = computed(() => (index.value > 0 ? HELP_TOPICS[index.value - 1] : undefined));
    const next = computed(() => (index.value >= 0 ? HELP_TOPICS[index.value + 1] : undefined));

    const openSlugs = ref(new Set<string>());

    function toggle(slug: string) {
        const nextSet = new Set(openSlugs.value);
        if (nextSet.has(slug)) nextSet.delete(slug);
        else nextSet.add(slug);
        openSlugs.value = nextSet;
    }

    async function revealFromQuery() {
        const slug = typeof route.query.e === 'string' ? route.query.e : '';
        openSlugs.value = slug ? new Set([slug]) : new Set();
        if (!slug) return;
        await nextTick();
        document.getElementById(`guide-${slug}`)?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }

    watch(() => [route.params.group, route.query.e], () => void revealFromQuery(), { immediate: true });
</script>

<style scoped lang="scss">
    .help-topic-head {
        display: flex;
        align-items: center;
        gap: var(--space-4);
    }
    .help-topic-head__icon {
        display: grid;
        place-items: center;
        width: 52px;
        height: 52px;
        border-radius: var(--radius-full);
        background: var(--brand-primary-soft);
        color: var(--accent-mark);
        flex: 0 0 auto;
    }
    .help-topic-head__text {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
    }
    .help-topic-head__title {
        margin: 0;
        font-size: var(--font-size-2xl);
        font-weight: 700;
        letter-spacing: -0.01em;
        line-height: 1.15;
        color: var(--text-primary);
    }
    .help-topic-head__blurb {
        margin: 0;
        font-size: var(--font-size-md);
        color: var(--text-secondary);
    }
    .help-topic-list {
        display: flex;
        flex-direction: column;
        gap: var(--space-3);
    }
    .help-topic-nav {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: var(--space-3);
        padding-top: var(--space-4);
        border-top: 1px solid var(--divider);
    }
    .help-topic-nav__link {
        display: inline-flex;
        align-items: center;
        gap: var(--space-1);
        min-height: 44px;
        padding: 0 var(--space-3);
        border-radius: var(--radius-md);
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
        font-weight: 600;
        text-decoration: none;
        justify-self: start;
    }
    .help-topic-nav__link--next {
        justify-self: end;
    }
    .help-topic-nav__link:hover {
        color: var(--text-primary);
        background: var(--surface-sunken);
    }
    .help-topic-nav__link:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    @media (max-width: 599px) {
        .help-topic-head__title {
            font-size: var(--font-size-xl);
        }
    }
</style>
