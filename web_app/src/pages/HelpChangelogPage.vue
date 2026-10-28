<template>
    <!-- What's new: the repo changelog, one card per version, newest first.
         The server hands over the markdown body; this renders the two shapes
         it uses (### headings and - bullets) as text, without the markup. -->
    <HelpShell :crumb="{ label: 'Help', to: '/help' }">
        <header class="help-plain-head">
            <h1 class="help-plain-head__title">What's new</h1>
            <p class="help-plain-head__sub">Recent changes to Dora, newest first.</p>
        </header>

        <q-banner v-if="error" class="dora-bg-negative-soft text-negative" dense rounded>
            {{ error }}
        </q-banner>

        <div v-if="loading" class="help-plain-muted">Loading…</div>
        <div v-else-if="!entries.length && !error" class="help-plain-muted">No changelog entries yet.</div>

        <section v-for="entry in entries" :key="entry.version" class="help-release">
            <header class="help-release__head">
                <h2 class="help-release__version">
                    {{ entry.version === 'Unreleased' ? 'Coming up' : entry.version }}
                </h2>
                <span v-if="entry.date" class="help-release__date">{{ entry.date }}</span>
            </header>
            <template v-for="(block, i) in render(entry.body)" :key="i">
                <h3 v-if="block.kind === 'heading'" class="help-release__heading">{{ block.text }}</h3>
                <ul v-else-if="block.kind === 'list'" class="help-release__list">
                    <li v-for="(item, j) in block.items" :key="j">{{ item }}</li>
                </ul>
                <p v-else class="help-release__para">{{ block.text }}</p>
            </template>
        </section>
    </HelpShell>
</template>

<script setup lang="ts">
    import { onMounted, ref } from 'vue';
    import HelpShell from 'src/components/help/HelpShell.vue';
    import HelpApiService, { type ChangelogEntry } from 'src/services/api/helpApiService';
    import { describeApiError } from 'src/services/errorHandling/apiErrorHandler';

    type Block =
        | { kind: 'heading'; text: string }
        | { kind: 'list'; items: string[] }
        | { kind: 'para'; text: string };

    const helpApi = new HelpApiService();
    const entries = ref<ChangelogEntry[]>([]);
    const loading = ref(true);
    const error = ref<string | null>(null);

    /** Strip the markdown emphasis and code ticks the changelog uses. */
    function plain(line: string): string {
        return line.replace(/\*\*([^*]+)\*\*/g, '$1').replace(/`([^`]+)`/g, '$1').replace(/^\*([^*]+)\*/, '$1').trim();
    }

    function render(body: string): Block[] {
        const blocks: Block[] = [];
        let list: string[] | null = null;
        let para: string[] = [];
        const flushPara = () => {
            if (para.length) blocks.push({ kind: 'para', text: plain(para.join(' ')) });
            para = [];
        };
        const flushList = () => {
            if (list) blocks.push({ kind: 'list', items: list });
            list = null;
        };
        for (const raw of body.split('\n')) {
            const line = raw.replace(/\s+$/, '');
            if (!line.trim()) { flushPara(); flushList(); continue; }
            const heading = /^#{2,4}\s+(.*)$/.exec(line);
            if (heading) { flushPara(); flushList(); blocks.push({ kind: 'heading', text: plain(heading[1] ?? '') }); continue; }
            const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
            if (bullet) {
                flushPara();
                list ??= [];
                list.push(plain(bullet[1] ?? ''));
                continue;
            }
            if (list && /^\s{2,}\S/.test(line)) {
                // a wrapped continuation of the last bullet
                list[list.length - 1] = `${list[list.length - 1]} ${plain(line)}`;
                continue;
            }
            flushList();
            para.push(line.trim());
        }
        flushPara();
        flushList();
        return blocks;
    }

    onMounted(async () => {
        try {
            entries.value = (await helpApi.getChangelogAsync()).entries;
        } catch (err) {
            error.value = `Couldn't load the changelog: ${describeApiError(err)}`;
        } finally {
            loading.value = false;
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
    .help-plain-muted {
        color: var(--text-muted);
        font-size: var(--font-size-sm);
    }
    .help-release {
        padding: var(--space-4);
        background: var(--surface-component);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-lg);
        box-shadow: var(--elevation-card);
    }
    .help-release__head {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: var(--space-3);
        margin-bottom: var(--space-2);
    }
    .help-release__version {
        margin: 0;
        font-size: var(--font-size-lg);
        font-weight: 700;
    }
    .help-release__date {
        font-size: var(--font-size-xs);
        color: var(--text-muted);
    }
    .help-release__heading {
        margin: var(--space-3) 0 var(--space-1);
        font-size: var(--font-size-xs);
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--text-muted);
    }
    .help-release__list {
        margin: 0;
        padding-left: 1.2em;
        display: flex;
        flex-direction: column;
        gap: var(--space-1);
        font-size: var(--font-size-sm);
        line-height: 1.5;
    }
    .help-release__para {
        margin: 0 0 var(--space-2);
        font-size: var(--font-size-sm);
        line-height: 1.5;
        color: var(--text-secondary);
    }
</style>
