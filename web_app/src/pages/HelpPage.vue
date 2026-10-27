<template>
    <q-page padding>
        <div class="row items-center q-mb-md">
            <DoraMascot mood="excited" :size="48" />
            <div class="q-ml-md col">
                <div class="text-caption dora-text-muted">
                    Guides by area, a peek at what's new, and a fun fact while you're here.
                </div>
            </div>
            <!-- ambiguous — flat, accent-coloured label; no BaseButton variant
                 supports the accent palette. Left as raw q-btn for review.
                 `color="accent"` painted the raw fill tone (1.4:1 on this
                 page in pesto) — `dora-text-accent` is the same hue at ink
                 strength. -->
            <q-btn
                flat
                no-caps
                class="dora-text-accent q-mr-sm"
                :icon="ICONS.smart_toy"
                label="Meet D.O.R.A."
                :to="{ path: '/help/dora' }"
            />
            <!-- FU-370 — renders only when the operator has configured a
                 support channel (see support_channel.py). Dormant installs
                 show nothing here, exactly as before. type="a" anchor form
                 isn't in BaseButton's type union; matches the sibling raw
                 q-btn pattern above. -->
            <q-btn
                v-if="hasChannel"
                flat
                no-caps
                class="dora-text-accent"
                :icon="ICONS.bug_report"
                label="Report an issue"
                type="a"
                :href="reportHref"
                target="_blank"
                rel="noopener"
            />
        </div>

        <q-banner
            v-if="versionInfo?.update_available"
            class="dora-bg-warning-soft text-warning q-mb-md"
            rounded
        >
            <template #avatar>
                <q-icon :name="ICONS.system_update" />
            </template>
            <div class="text-weight-medium">
                A newer version of Dashy Dora is available
                ({{ versionInfo.latest_version }}). You're on
                {{ versionInfo.current_version }}.
            </div>
            <template #action>
                <!-- ambiguous — type="a" anchor form not in BaseButton's type union; left as raw q-btn for review. -->
                <q-btn
                    v-if="versionInfo.release_url"
                    flat
                    no-caps
                    label="See release notes"
                    type="a"
                    :href="versionInfo.release_url"
                    target="_blank"
                    rel="noopener"
                />
            </template>
        </q-banner>

        <q-card v-if="foodFact" flat bordered class="q-mb-md food-fact-card">
            <q-card-section class="row items-start">
                <q-icon :name="ICONS.restaurant" size="22px" color="primary" />
                <div class="q-ml-md col">
                    <div class="text-caption dora-text-muted">Food fact</div>
                    <div>{{ foodFact }}</div>
                </div>
                <BaseButton
                    variant="icon"
                    :icon="ICONS.refresh"
                    :loading="loadingFact"
                    @click="loadFoodFact"
                >
                    <BaseTooltip>Another, please</BaseTooltip>
                </BaseButton>
            </q-card-section>
        </q-card>

        <DoraTabs
            v-model="tab"
            :tabs="[
                { name: 'guides', label: 'Guides', icon: ICONS.menu_book },
                { name: 'changelog', label: `What's new`, icon: ICONS.new_releases },
                { name: 'about', label: 'About', icon: ICONS.info },
            ]"
        />

        <q-tab-panels v-model="tab" animated class="bg-transparent">
            <!-- Guides ──────────────────────────────────────────── -->
            <q-tab-panel name="guides" class="q-pa-none q-pt-md">
                <q-input
                    v-model="search"
                    outlined
                    dense
                    clearable
                    placeholder="Filter guides…"
                    class="q-mb-md"
                >
                    <template #prepend><q-icon :name="ICONS.search" /></template>
                </q-input>

                <div class="row q-col-gutter-md">
                    <div
                        v-for="group in filteredGuides"
                        :key="group.title"
                        class="col-12 col-md-6"
                    >
                        <q-card flat bordered>
                            <q-card-section class="row items-center">
                                <q-icon :name="group.icon" size="22px" color="primary" />
                                <div class="q-ml-sm text-h6">{{ group.title }}</div>
                            </q-card-section>
                            <q-separator />
                            <q-list separator>
                                <template v-for="entry in group.entries" :key="entry.title">
                                    <!-- Long-form entries explain in place rather
                                         than navigating away — a guide you have to
                                         leave Help to read is not a guide. Opened
                                         by default while a filter is active, since
                                         a `?q=` deep-link from elsewhere in the app
                                         means "show me this one". -->
                                    <q-expansion-item
                                        v-if="entry.details"
                                        :label="entry.title"
                                        :caption="entry.summary"
                                        :default-opened="!!search"
                                    >
                                        <q-card flat>
                                            <q-card-section class="guide-details">
                                                <template v-for="(block, i) in entry.details" :key="i">
                                                    <p v-if="block.kind === 'para'">{{ block.text }}</p>
                                                    <dl v-else>
                                                        <template v-for="t in block.terms" :key="t.term">
                                                            <dt>{{ t.term }}</dt>
                                                            <dd>{{ t.definition }}</dd>
                                                        </template>
                                                    </dl>
                                                </template>
                                                <BaseButton
                                                    v-if="entry.path"
                                                    variant="subtle"
                                                    :icon="ICONS.arrow_forward"
                                                    :label="`Go to ${entry.title.toLowerCase()}`"
                                                    @click="onGuideClick(entry)"
                                                />
                                            </q-card-section>
                                        </q-card>
                                    </q-expansion-item>
                                    <q-item
                                        v-else
                                        clickable
                                        @click="onGuideClick(entry)"
                                    >
                                        <q-item-section>
                                            <q-item-label>{{ entry.title }}</q-item-label>
                                            <q-item-label caption>
                                                {{ entry.summary }}
                                            </q-item-label>
                                        </q-item-section>
                                        <q-item-section side v-if="entry.path">
                                            <q-icon :name="ICONS.arrow_forward" />
                                        </q-item-section>
                                        <q-item-section side v-else-if="entry.dialog">
                                            <q-icon :name="ICONS.info_outline" />
                                        </q-item-section>
                                    </q-item>
                                </template>
                            </q-list>
                        </q-card>
                    </div>

                    <div
                        v-if="filteredGuides.length === 0"
                        class="col-12 text-center dora-text-muted q-py-lg"
                    >
                        Nothing matches "{{ search }}".
                    </div>
                </div>
            </q-tab-panel>

            <!-- Changelog ───────────────────────────────────────── -->
            <q-tab-panel name="changelog" class="q-pa-none q-pt-md">
                <q-banner
                    v-if="changelogError"
                    class="dora-bg-negative-soft text-negative q-mb-md"
                    dense
                    rounded
                >
                    {{ changelogError }}
                </q-banner>

                <div v-if="changelogEntries.length === 0 && !changelogLoading" class="dora-text-muted">
                    No changelog entries found.
                </div>

                <q-list bordered>
                    <q-expansion-item
                        v-for="(entry, idx) in changelogEntries"
                        :key="entry.version"
                        :default-opened="idx < 2 || entry.version.toLowerCase() === 'unreleased'"
                        :label="entry.version"
                        :caption="entry.date ?? undefined"
                        header-class="text-weight-medium"
                        expand-separator
                    >
                        <q-card flat>
                            <q-card-section>
                                <pre class="changelog-body">{{ entry.body }}</pre>
                            </q-card-section>
                        </q-card>
                    </q-expansion-item>
                </q-list>
            </q-tab-panel>

            <!-- About ──────────────────────────────────────────── -->
            <q-tab-panel name="about" class="q-pa-none q-pt-md">
                <q-card flat bordered>
                    <q-card-section v-if="versionInfo">
                        <div class="text-h6">
                            Dashy Dora {{ versionInfo.current_version }}
                        </div>
                        <div class="text-caption dora-text-muted">
                            <span v-if="versionInfo.latest_version === null">
                                Couldn't check for updates ({{ versionInfo.error ?? 'unknown reason' }}).
                            </span>
                            <span v-else-if="versionInfo.update_available">
                                {{ versionInfo.latest_version }} is available.
                            </span>
                            <span v-else> You're on the latest version. </span>
                        </div>
                    </q-card-section>
                    <q-separator />
                    <!-- FU-370 — honest one-person/side-project support copy
                         (replaces the old "pass it to whoever runs this Dora
                         instance" line). The final paragraph adapts: when a
                         support channel is configured it points at the
                         Report-an-issue button above; when dormant it falls
                         back to the graceful "ask whoever runs this" form. -->
                    <q-card-section class="text-caption">
                        <div class="text-body2 text-weight-medium q-mb-xs">
                            Getting help &amp; reporting issues
                        </div>
                        <div class="dora-text-muted support-copy">
                            <p>
                                Dashy Dora is built by one person as a side
                                project. Bug reports and feature requests are
                                welcome and every one gets read, but replies can
                                take days or weeks. There's no on-call and no
                                support team; just someone doing this in evenings
                                and weekends.
                            </p>
                            <p>
                                If a family member set up this Dora for you, ask
                                them first.
                            </p>
                            <p v-if="hasChannel">
                                Otherwise, use the
                                <strong>Report an issue</strong> button at the top
                                of this page. Before filing, note the steps you
                                took, what you expected, and what happened
                                instead. Screenshots help.
                            </p>
                            <p v-else>
                                Otherwise, note the steps you took, what you
                                expected, and what happened instead (screenshots
                                help), and pass it to whoever runs this Dora
                                instance.
                            </p>
                        </div>
                    </q-card-section>
                </q-card>
            </q-tab-panel>
        </q-tab-panels>

        <AttentionRulesDialog v-model="attentionRulesOpen" />
    </q-page>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import { ICONS } from 'src/style/icons';
    import { useQuasar } from 'quasar';
    import AttentionRulesDialog from 'src/components/help/AttentionRulesDialog.vue';
    import DoraMascot from 'src/components/dora/DoraMascot.vue';
    import DoraTabs from 'src/components/DoraTabs.vue';
    import HelpApiService, {
        type ChangelogEntry,
        type VersionInfo
    } from 'src/services/api/helpApiService';
    import { computed, onMounted, ref } from 'vue';
    import { useRoute, useRouter } from 'vue-router';
    import { describeApiError } from 'src/services/errorHandling/apiErrorHandler';
    import {
        useSupportChannel,
        supportHref,
    } from 'src/composables/useSupportChannel';

    /** A long-form block inside a guide entry. Most guides are a title + a
     *  one-sentence summary and need nothing else; a few explain a mechanism
     *  with named options, which reads as a definition list rather than prose.
     *
     *  This exists because the stocktake runner's (?) used to open a modal
     *  holding several paragraphs and a five-term list. Owner feedback
     *  2026-08-27: *"Info button should take you to help and guides, not open a
     *  modal"* — so the content moved here, and Help had to grow somewhere to
     *  put it. */
    type GuideDetail =
        | { kind: 'para'; text: string }
        | { kind: 'terms'; terms: Array<{ term: string; definition: string }> };

    type GuideEntry = {
        title: string;
        summary: string;
        path?: string;
        /** Opens an inline explainer dialog instead of navigating away.
         *  Used for visual-cue topics that benefit from swatches + tables. */
        dialog?: 'attention-rules';
        /** Long-form explanation, shown inline in an expander. An entry may
         *  carry both `details` and `path`: the expander explains, the link at
         *  its foot takes you to the thing. */
        details?: GuideDetail[];
    };
    type GuideGroup = { title: string; icon: string; entries: GuideEntry[] };

    const GUIDES: GuideGroup[] = [
        {
            title: 'Stock',
            icon: 'inventory_2',
            entries: [
                {
                    title: 'Add a stock item',
                    summary:
                        'On the Stock page, click "New item". Set the name and stock level, and optionally a location, stock group, or the Essential flag. Expiry is set on the item itself once it\'s added.',
                    path: '/stock',
                },
                {
                    title: 'Track expiry and flag essentials',
                    summary:
                        'Set an expiry date on a stock item and Dora shows it in upcoming expiries. Mark essentials so they always show up first.',
                    path: '/stock',
                },
                {
                    title: 'What the colours and outlines mean',
                    summary:
                        'When a row outlines amber or red, when an item is dimmed, and what "Needs attention" counts.',
                    dialog: 'attention-rules',
                },
                {
                    title: 'The "Dora thinks…" hint',
                    summary:
                        'Dora infers what you actually have: a rough Out / Low / Stocked belief worked out from your purchases, how often you rebuy, and what you\'ve cooked, decayed by time since the last real signal. It never changes your recorded level; that stays the source of truth for shopping and cooking. She only speaks up when it\'s worth it: when her belief differs from what you recorded, the item\'s level box gets a dashed ring, and the level picker says what she thinks and why. When she agrees with you she stays silent. Turn the hint off entirely in Settings → Assistant.',
                    path: '/stock',
                },
                {
                    title: 'The Buy / Wait / Skip ring on the cart button',
                    summary:
                        'Dora can tell you whether an item is worth buying right now, using only your own history: what you\'ve paid for it before, how fast you get through it, and how often it ends up thrown away. No outside data, no crowd pricing. The answer rides the cart button as a coloured ring: green for "worth buying now", amber for "might be worth waiting", red for "probably skip". Hover it for the headline, the reasons behind it, and how confident she is. When she isn\'t confident she says nothing. Turn it off in Settings → Admin → System ("Should I buy?" oracle).',
                    path: '/stock',
                },
                {
                    title: 'Scanning barcodes and QR labels',
                    summary:
                        'When scanning is switched on (Settings → Admin → System), the Stock page grows a Scan button: point it at a product barcode to jump straight to the matching stock item, or at one of Dora\'s own printed QR labels. Scanning never looks up live prices. Most browsers only allow the camera over HTTPS, so on a plain http:// address the camera may not open. If it doesn\'t, use the Android app, serve Dora over HTTPS, or type the barcode.',
                    path: '/stock',
                },
                // 2026-08-24 feedback: these three carry prose that used to sit
                // permanently on the stock-item detail page — a paragraph above
                // the barcode list, a paragraph inside the substitute-note
                // dialog, and the QR tooltip. Explanation you read once doesn't
                // earn permanent space on the surface; the (?) beside each
                // heading deep-links here via `?q=<title>`.
                {
                    title: 'Barcodes',
                    summary:
                        "A barcode on a stock item is the product's real EAN-13 or UPC-A: the 13 or 12 digits printed underneath the barcode on the packet. Type it into the Scanning tab, or hit Scan on the Stock page and point the camera at the packet. Scanning a registered code then opens that item. Dora never looks the number up online, so any code you can read off a packet works, and one code belongs to one item. Codes listed as \"(from product: …)\" came along with a linked Product rather than being registered here, so they're removed from the Product, not from the stock item.",
                    path: '/stock',
                },
                {
                    title: 'QR label',
                    summary:
                        "Dora's own printable label for a stock item, shown in the Scanning tab. Scanning it opens that item's page, which is handy on a decanted jar. It is not the product's real EAN/UPC barcode: those identify a Product and are managed further down the same tab. Print a single label from the tab, or a whole batch under Settings → Kitchen setup → QR labels.",
                    path: '/stock',
                },
                {
                    title: 'Substitutes',
                    summary:
                        "List the items that can stand in for one another, on a stock item's Substitutes tab. Notes you add show on the substitute list and in cook mode when swapping, so \"1:1 in soups, but don't use in baking\" reaches you at the moment you'd get it wrong. Add a ratio when the swap isn't 1:1 and cook mode shows it. A swap made in cook mode is temporary and applies to that session only; it never rewrites the recipe.",
                    path: '/stock',
                },
                {
                    title: 'Link a product to a stock item',
                    summary:
                        'On the detail page, link a product to your stock item so its offers + price history ride alongside your pantry record.',
                    path: '/stock',
                },
            ],
        },
        {
            title: 'Stocktake',
            icon: ICONS.fact_check,
            entries: [
                {
                    // The runner's (?) deep-links here by exact title via
                    // `?q=`; keep the two in step if this is ever reworded.
                    title: 'How stocktake works',
                    summary:
                        'Dora walks you through the items she thinks need a check, one at a time. A run has up to three parts and each item offers five options.',
                    path: '/stocktake',
                    details: [
                        {
                            kind: 'para',
                            text: 'A run has up to three parts. First, anything Dora is fairly sure about: agree in one tap, or untick it to check yourself. Then the walk, one item at a time. Last, a tidy-up of anything that has dropped out of the rotation since your last run. Any part with nothing in it is skipped silently.',
                        },
                        {
                            kind: 'para',
                            text: 'With stock inference switched on, the walk is ordered least-certain first: checking something Dora has already worked out from your shopping and cooking tells her nothing new, so those wait until the end, and the ones she cannot call come first. Items she has no evidence about sit in the middle, ordered by how overdue they are. With inference off, the walk is simply most-overdue first.',
                        },
                        {
                            kind: 'terms',
                            terms: [
                                { term: 'Still correct', definition: "The level's right. Resets the check clock." },
                                { term: 'Change level', definition: 'Pick a new level. Also resets the check clock.' },
                                { term: 'Skip', definition: "Not this time. Nothing is recorded." },
                                { term: 'Push 3 days', definition: 'Dora stops asking about this item for three days. Doesn\'t count as a check.' },
                                { term: 'Mute', definition: "Stop asking about this item entirely. You can un-mute later from the item's detail page." },
                            ],
                        },
                        {
                            kind: 'para',
                            text: 'How often each item shows up (Weekly / Fortnightly / Monthly) is set globally in Settings → Stocktake, with Auto self-tuning by how fast the item actually moves.',
                        },
                    ],
                },
            ],
        },
        {
            title: 'Recipes & meals',
            icon: ICONS.menu_book,
            entries: [
                {
                    title: 'Cook mode',
                    summary:
                        'Open a recipe and hit Cook. Steps render one card at a time and ingredients show where each one lives (e.g. Pantry > Top shelf).',
                    path: '/cookbook',
                },
                {
                    title: 'Build a meal plan',
                    summary:
                        'Group recipes into meals (e.g. roast + sides). Then schedule meals onto a meal plan; the dashboard shows the next entry on the home page.',
                    path: '/meal-plans',
                },
                {
                    // The reconcile runner's and the meal log's (?) deep-link
                    // here by exact title via `?q=`; keep them in step.
                    title: 'Reconcile past meals',
                    summary:
                        'After a planned day passes, Dora settles what actually happened to each meal so the recipe pool stays right.',
                    path: '/meal-plans',
                    details: [
                        {
                            kind: 'para',
                            text: 'In manual mode, Dora walks you through past-day meals that have not been confirmed yet, one at a time, oldest first. Each one offers five options.',
                        },
                        {
                            kind: 'terms',
                            terms: [
                                { term: 'Cooked', definition: 'You made it as planned. The cooked count and pool are correct.' },
                                { term: 'Different portions', definition: 'You made a different amount, say 3 instead of 2. Dora reflows the pool.' },
                                { term: 'Cooked later', definition: 'You made it, but on a later day. Dora records the date.' },
                                { term: "Didn't cook", definition: 'The meal did not happen. Dora puts the pool back the way it was.' },
                                { term: 'Skip for now', definition: 'Not sure yet. The meal stays in the queue for next time.' },
                            ],
                        },
                        {
                            kind: 'para',
                            text: 'In auto mode, Dora assumes each planned meal was cooked as its day passes and drains the pool for you. The meal log is the record of what she did with each one.',
                        },
                        {
                            kind: 'terms',
                            terms: [
                                { term: 'Logged as cooked', definition: 'Dora assumed you cooked it as planned.' },
                                { term: 'Cooked / Cooked · N', definition: 'You confirmed it, as planned or with a different amount.' },
                                { term: 'Not cooked', definition: 'You marked that it did not happen; the pool was put back.' },
                                { term: 'Skipped', definition: 'Left undecided for later.' },
                            ],
                        },
                        {
                            kind: 'para',
                            text: 'Manual or auto is set for the whole household in Settings → Admin → System → Meal reconciliation.',
                        },
                    ],
                },
            ],
        },
        {
            title: 'Shopping & deals',
            icon: ICONS.shopping_cart,
            entries: [
                {
                    title: 'Search for products',
                    summary:
                        'Product Search opens an admin-configured external search surface in a new tab. The destination pushes data back into Dora via the ingestion seam.',
                    path: '/',
                },
            ],
        },
        {
            title: 'Settings & admin',
            icon: ICONS.settings,
            entries: [
                {
                    title: 'Theme, font, and text size',
                    summary:
                        'In Appearance, switch between System / Light / Dark, pick a font (Urbanist, Nunito, Inter, Lexend, or Plus Jakarta Sans), and adjust text size.',
                    path: '/settings/preferences',
                },
                {
                    title: 'Manage other users (admin)',
                    summary:
                        "Admins see a Users page in Settings: toggle admin role, edit username/email, manage who's subscribed to the weekly deals email, and reset a forgotten password.",
                    path: '/settings/admin/users',
                },
                {
                    title: 'Manage stores (admin)',
                    summary:
                        'Curate the list of retail stores Dora knows about. Add a store, upload a logo, or remove ones you no longer track. No stores ship by default.',
                    path: '/settings/kitchen-setup/stores',
                },
            ],
        },
        {
            title: 'Dora itself',
            icon: ICONS.mood,
            entries: [
                {
                    title: 'How does Dora know what page I\'m on?',
                    summary:
                        "I read the route. When you click 'What can I do on this page?' I look up a per-route summary. If I don't have one, I'll say so honestly.",
                },
                {
                    // Owner question 2026-08-27: *"TTS isn't supported on
                    // Firefox for some reason? What browsers can we support?"*
                    // The answer has two halves and only one of them is a
                    // browser fact, so it needs more than a tooltip.
                    title: 'Which browsers can Dora speak in?',
                    summary:
                        "All of them, if her neural voice is installed on the server. The browser's own voice is the part that varies.",
                    path: '/settings/voice',
                    details: [
                        {
                            kind: 'para',
                            text: "Dora has two ways to speak. Her own neural voice is generated on the server and played back as ordinary audio, so it works in every browser. It is the default.",
                        },
                        {
                            kind: 'para',
                            text: "The other way is your browser's built-in text-to-speech, and that is the one with gaps. A browser can only speak with voices the operating system gives it, so the voice list can be empty, and then nothing is said. Firefox is the common case: it speaks through SAPI on Windows, needs speech-dispatcher installed on Linux, and has no synthesis at all on Android.",
                        },
                        {
                            kind: 'para',
                            text: 'So: if Dora is silent, install her neural voice on the server (the Docker image and the desktop app already include it) rather than chasing browser support. Settings → Voice tells you which of the two is actually working on the device you are reading this on.',
                        },
                    ],
                },
                {
                    title: 'Can Dora do free-form questions?',
                    summary:
                        "Only when you've configured AI mode for your account (Settings > Assistant). With it on, I understand plain-language questions about your data, suggest recipes, and add to your shopping list. With it off, I'm a simpler rule-based helper that matches keywords. AI mode is per-account, so two people in the same household can use different providers.",
                },
                {
                    title: 'Set up AI mode (per account)',
                    summary:
                        "Go to Settings > Assistant. Pick a provider: Ollama (a local model you run yourself, no API key), or OpenAI / Anthropic / Google Gemini (paid hosted APIs, bring your own key). For Ollama: enter the base URL (e.g. http://localhost:11434) + a tool-capable model like qwen2.5:7b. For paid providers: paste your API key + pick a model. Use Test connection to verify before turning AI mode on. Off by default.",
                    path: '/settings/assistant',
                },
                {
                    title: 'Why does AI mode say "unavailable"?',
                    summary:
                        "The chat panel shows an \"AI mode unavailable\" banner when you've turned AI on but the configured LLM didn't respond. Common causes: your Ollama server isn't running; the API key is wrong; the model name is mistyped; or the backend can't reach the URL (see network topology below). Click Retry on the banner after fixing it, or hit Test connection in Settings > Assistant first to find the issue before turning AI on.",
                },
                {
                    title: "Network topology: who reaches the LLM?",
                    summary:
                        "The Dora backend reaches your LLM, not your browser. That means the backend's network has to see your LLM's URL. On a single-laptop install (backend + LLM on the same box) this is just localhost. On a household setup with the backend on a NAS/Pi and an LLM on a different desktop, the backend needs to be able to reach that desktop (LAN routing, Tailscale, or a port forward). The base URL you save in Settings is from the *backend's* point of view.",
                },
                {
                    title: "Paid providers: API-key encryption (DORA_SECRET_ENCRYPTION_KEY)",
                    summary:
                        "AI mode is per account. Each person sets it up on Settings > Assistant. For paid providers (OpenAI / Anthropic / Gemini), the install needs the environment variable DORA_SECRET_ENCRYPTION_KEY set so your API key can be stored encrypted. Until it is, the Assistant page shows a warning and can generate a key for you. Generate one from a shell with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\". Ollama-only installs don't need the env var. Rotating the key invalidates every saved key; users re-enter on next save.",
                    path: '/settings/assistant',
                },
            ],
        },
    ];

    const $q = useQuasar();
    const router = useRouter();
    const route = useRoute();
    const helpApi = new HelpApiService();

    // FU-370 — support channel; button + copy self-gate on `hasChannel`.
    const { channel, hasChannel } = useSupportChannel();
    const reportHref = computed(() =>
        supportHref(channel.value, {
            subject: `[Dora] Bug, v${versionInfo.value?.current_version ?? 'unknown'}`,
            body: `\n\n---\nDora ${versionInfo.value?.current_version ?? 'unknown'} · ${route.path}`,
        }),
    );

    const tab = ref<'guides' | 'changelog' | 'about'>('guides');
    // Seed the guide filter from a `?q=` deep-link (e.g. the "Learn more" link
    // on the Assistant → Zero-Input Pantry setting jumps straight to that guide).
    const search = ref(typeof route.query.q === 'string' ? route.query.q : '');

    const changelogEntries = ref<ChangelogEntry[]>([]);
    const changelogLoading = ref(false);
    const changelogError = ref<string | null>(null);

    const versionInfo = ref<VersionInfo | null>(null);

    const foodFact = ref<string | null>(null);
    const loadingFact = ref(false);

    const filteredGuides = computed<GuideGroup[]>(() => {
        const q = (search.value ?? '').toLowerCase().trim();
        if (!q) return GUIDES;
        return GUIDES.map((g) => ({
            ...g,
            entries: g.entries.filter(
                (e) =>
                    e.title.toLowerCase().includes(q) ||
                    e.summary.toLowerCase().includes(q) ||
                    detailText(e).includes(q),
            ),
        })).filter((g) => g.entries.length > 0);
    });

    /** Flattened long-form text for the filter, so searching a term that only
     *  appears inside an expander ("push 3 days") still finds its guide. */
    function detailText(entry: GuideEntry): string {
        if (!entry.details) return '';
        return entry.details
            .map((b) => (b.kind === 'para'
                ? b.text
                : b.terms.map((t) => `${t.term} ${t.definition}`).join(' ')))
            .join(' ')
            .toLowerCase();
    }

    function onGuideClick(entry: GuideEntry) {
        if (entry.dialog === 'attention-rules') {
            attentionRulesOpen.value = true;
            return;
        }
        if (entry.path) void router.push(entry.path);
    }

    const attentionRulesOpen = ref(false);

    async function loadChangelog() {
        changelogLoading.value = true;
        changelogError.value = null;
        try {
            const result = await helpApi.getChangelogAsync();
            changelogEntries.value = result.entries;
        } catch (err) {
            changelogError.value = `Couldn't load the changelog: ${describeApiError(err)}`;
        } finally {
            changelogLoading.value = false;
        }
    }

    async function loadFoodFact() {
        loadingFact.value = true;
        try {
            foodFact.value = (await helpApi.getFoodFactAsync()).fact;
        } catch {
            foodFact.value = null;
            $q.notify({
                type: 'warning',
                message: "Couldn't fetch a food fact right now."
            });
        } finally {
            loadingFact.value = false;
        }
    }

    onMounted(async () => {
        // Fire everything in parallel — none of them block the page render.
        void loadChangelog();
        void loadFoodFact();
        try {
            versionInfo.value = await helpApi.getVersionAsync();
        } catch {
            versionInfo.value = null;
        }
    });
</script>

<style scoped>
    .food-fact-card {
        background: linear-gradient(
            120deg,
            color-mix(in srgb, var(--brand-primary) 6%, transparent),
            color-mix(in srgb, var(--brand-accent) 8%, transparent)
        );
    }
    .changelog-body {
        white-space: pre-wrap;
        font-family: inherit;
        margin: 0;
    }
    /* Long-form guide bodies (see `GuideDetail`). Same typography the
       stocktake runner's help modal used before its content moved here, so
       the definition list still reads as a list of named options. */
    .guide-details {
        font-size: var(--text-sm, 0.9rem);
        line-height: 1.4;
    }
    .guide-details p {
        margin: 0 0 12px;
    }
    .guide-details dl {
        margin: 12px 0;
    }
    .guide-details dt {
        font-weight: 600;
        margin-top: 8px;
    }
    .guide-details dd {
        margin-left: 0;
        color: var(--text-secondary, inherit);
    }
    .support-copy p {
        margin: 0 0 8px;
    }
    .support-copy p:last-child {
        margin-bottom: 0;
    }
</style>
