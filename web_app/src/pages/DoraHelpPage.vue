<template>
    <q-page padding>
        <!-- ── Header ──────────────────────────────────────────────── -->
        <div class="row items-center q-mb-md">
            <DoraMascot mood="cute" :size="96" />
            <div class="q-ml-md col">
                <div class="text-h6">Meet D.O.R.A.</div>
                <div class="text-caption dora-text-muted">
                    <strong>D</strong>elicious <strong>O</strong>rganised <strong>R</strong>estock <strong>A</strong>ssistant.
                    Sentient burger robot. Your in-app pantry buddy. Slightly chaotic.
                </div>
            </div>
            <BaseButton
                variant="ghost"
                :icon="ICONS.arrow_back"
                label="Back to Help"
                :to="{ path: '/help' }"
            />
        </div>

        <!-- ── Intro ───────────────────────────────────────────────── -->
        <q-card flat bordered class="q-mb-md">
            <q-card-section>
                <p class="q-mb-sm">
                    Dora is the little burger icon in the bottom-right. Click her
                    any time to chat. Ask about your pantry, get recipe ideas,
                    convert measurements, find substitutes, or just say hi.
                </p>
                <p class="q-mb-none">
                    She works in two modes. <strong>Basic mode</strong> is always
                    on and uses a hand-written rule engine. <strong>AI mode</strong>
                    layers a local large language model on top for natural-language
                    understanding. Set it up in Settings → Assistant.
                </p>
            </q-card-section>
        </q-card>

        <!-- ── Modes ───────────────────────────────────────────────── -->
        <div class="text-h6 q-mb-sm">Modes</div>
        <div class="row q-col-gutter-md q-mb-lg">
            <div class="col-12 col-md-6">
                <q-card flat bordered class="dora-mode-card">
                    <q-card-section>
                        <div class="row items-center q-mb-sm">
                            <q-icon :name="ICONS.chat_bubble_outline" color="grey" size="22px" />
                            <div class="text-subtitle1 q-ml-sm">Basic mode</div>
                            <q-chip dense color="grey" text-color="white" class="q-ml-sm">always on</q-chip>
                        </div>
                        <p class="text-caption dora-text-muted q-mb-sm">
                            Keyword-matched intents with hand-written replies.
                            Fast, predictable, works without any setup.
                        </p>
                        <ul class="dora-feature-list">
                            <li>Looks up your stock, recipes, lists, and meal plan</li>
                            <li>Kitchen unit conversion (cups / ml / oz / °C / °F)</li>
                            <li>Ingredient substitution suggestions</li>
                            <li>Per-page guidance ("what can I do here?")</li>
                            <li>Jokes, food facts, and chitchat</li>
                        </ul>
                    </q-card-section>
                </q-card>
            </div>
            <div class="col-12 col-md-6">
                <q-card flat bordered class="dora-mode-card">
                    <q-card-section>
                        <div class="row items-center q-mb-sm">
                            <q-icon :name="ICONS.auto_awesome" color="primary" size="22px" />
                            <div class="text-subtitle1 q-ml-sm">AI mode</div>
                            <q-chip dense color="primary" text-color="white" class="q-ml-sm">opt-in</q-chip>
                        </div>
                        <p class="text-caption dora-text-muted q-mb-sm">
                            A local language model (Ollama) handles freeform
                            phrasing and chains tool calls. Set up in
                            <router-link to="/settings/assistant">Settings → Dora assistant</router-link>.
                        </p>
                        <ul class="dora-feature-list">
                            <li>Understands looser phrasing and follow-ups</li>
                            <li>Picks the right tool from the question itself</li>
                            <li>Density-aware conversions (g↔cup for flour, etc.)</li>
                            <li>Proactive: surfaces useful info you didn't ask for</li>
                            <li>Falls back to Basic mode if the model's unreachable</li>
                        </ul>
                    </q-card-section>
                </q-card>
            </div>
        </div>

        <!-- ── Basic-mode intents ─────────────────────────────────── -->
        <div class="text-h6 q-mb-sm">What you can ask in Basic mode</div>
        <q-list bordered separator class="q-mb-lg rounded-borders">
            <q-expansion-item
                v-for="group in basicIntents"
                :key="group.title"
                :label="group.title"
                :caption="group.caption"
                :icon="group.icon"
                expand-separator
            >
                <div class="q-pa-md dora-intent-block">
                    <div
                        v-for="intent in group.intents"
                        :key="intent.name"
                        class="dora-intent-row"
                    >
                        <div class="dora-intent-name">{{ intent.name }}</div>
                        <div class="dora-intent-examples">
                            <q-chip
                                v-for="(ex, idx) in intent.examples"
                                :key="idx"
                                dense
                                outline
                                color="grey"
                                class="dora-intent-example"
                            >
                                {{ ex }}
                            </q-chip>
                        </div>
                    </div>
                </div>
            </q-expansion-item>
        </q-list>

        <!-- ── AI tools ───────────────────────────────────────────── -->
        <div class="text-h6 q-mb-sm">What AI mode unlocks</div>
        <p class="text-caption dora-text-muted q-mb-md">
            When AI is active, Dora picks the right tool from your phrasing. You
            don't need to memorise these.
        </p>
        <q-list bordered separator class="q-mb-lg rounded-borders">
            <q-item v-for="tool in aiTools" :key="tool.name">
                <q-item-section avatar>
                    <q-icon :name="tool.icon" color="primary" />
                </q-item-section>
                <q-item-section>
                    <q-item-label class="text-weight-medium">{{ tool.name }}</q-item-label>
                    <q-item-label caption>{{ tool.description }}</q-item-label>
                    <div class="q-mt-xs">
                        <q-chip
                            v-for="(ex, idx) in tool.examples"
                            :key="idx"
                            dense
                            outline
                            color="primary"
                            class="dora-intent-example"
                        >
                            "{{ ex }}"
                        </q-chip>
                    </div>
                </q-item-section>
            </q-item>
        </q-list>

        <!-- ── Faces cheat sheet ──────────────────────────────────── -->
        <div class="text-h6 q-mb-sm">Faces &amp; expressions</div>
        <p class="text-caption dora-text-muted q-mb-md">
            The big burger in the bottom-right reacts to the conversation. Here's
            what each face means, mostly so you can blame me when she pouts.
        </p>
        <div class="row q-col-gutter-md q-mb-lg">
            <div
                v-for="face in faceGuide"
                :key="face.mood"
                class="col-6 col-sm-4 col-md-3"
            >
                <q-card flat bordered class="dora-face-card text-center">
                    <q-card-section class="q-pa-sm">
                        <DoraMascot :mood="face.mood" :size="72" />
                        <div class="text-weight-medium q-mt-sm">{{ face.label }}</div>
                        <div class="text-caption dora-text-muted">{{ face.when }}</div>
                    </q-card-section>
                </q-card>
            </div>
        </div>

        <!-- ── Tips ───────────────────────────────────────────────── -->
        <div class="text-h6 q-mb-sm">Tips &amp; tricks</div>
        <q-list bordered separator class="rounded-borders">
            <q-item v-for="tip in tips" :key="tip.title">
                <q-item-section avatar>
                    <q-icon :name="tip.icon" color="warning" />
                </q-item-section>
                <q-item-section>
                    <q-item-label class="text-weight-medium">{{ tip.title }}</q-item-label>
                    <q-item-label caption>{{ tip.body }}</q-item-label>
                </q-item-section>
            </q-item>
        </q-list>
    </q-page>
</template>

<script lang="ts" setup>
    import { ICONS } from 'src/style/icons';
    // Detailed user-facing documentation for Dora. Kept as static data on the
    // page (rather than driven off the intent registry) because the prose
    // wants to be edited freely — a generated table would be drier than the
    // assistant itself, which would be a real shame.
    import BaseButton from 'src/components/BaseButton.vue';
    import DoraMascot from 'src/components/dora/DoraMascot.vue';
    import type { DoraMood } from 'src/components/dora/doraTypes';

    type Intent = { name: string; examples: string[] };
    type IntentGroup = { title: string; caption: string; icon: string; intents: Intent[] };

    const basicIntents: IntentGroup[] = [
        {
            title: 'Your pantry',
            caption: 'Stock, expiry, locations',
            icon: ICONS.inventory_2,
            intents: [
                { name: 'Pantry summary', examples: ["how's my pantry", 'pantry status', 'pantry overview'] },
                { name: "What's low", examples: ["what's low", 'running out', 'almost out'] },
                { name: "What's expiring", examples: ['expiring soon', "what's about to go off", 'use by'] },
                { name: 'Where is something', examples: ["where's the milk", 'where do I keep flour', 'where are my eggs'] },
                { name: 'Attention items', examples: ['what needs attention', 'urgent', 'alerts'] },
            ],
        },
        {
            title: 'Recipes & meals',
            caption: 'Cook ideas, planning, lookups',
            icon: ICONS.menu_book,
            intents: [
                { name: "What's for dinner", examples: ["what's for dinner", "I'm hungry", 'dinner ideas', 'feed me'] },
                { name: 'Find a recipe', examples: ['recipe for carbonara', 'how do I cook risotto', 'recipes with chicken'] },
                { name: "This week's plan", examples: ["what's the plan", "what's next", 'upcoming meals'] },
            ],
        },
        {
            title: 'Shopping',
            caption: 'Lists, deals',
            icon: ICONS.shopping_cart,
            intents: [
                { name: 'List status', examples: ["what's on my list", 'shopping list status', 'my shopping list'] },
            ],
        },
        {
            title: 'Kitchen helpers',
            caption: 'Conversions, substitutions',
            icon: ICONS.restaurant,
            intents: [
                { name: 'Unit conversion', examples: ['1 cup to ml', '200g to oz', '180c to f', '1 tsp to ml'] },
                { name: 'Substitutions', examples: ['substitute for butter', 'instead of buttermilk', 'no eggs', 'ran out of milk'] },
            ],
        },
        {
            title: 'Navigation & help',
            caption: 'Tours, guides, page hints',
            icon: ICONS.help_outline,
            intents: [
                { name: 'Page help', examples: ['what can I do here', 'what is this page'] },
                { name: 'How do I...', examples: ['how do I add a stock item', 'how to plan a meal'] },
                { name: 'Guides', examples: ['open the guides', 'docs', 'manual'] },
                { name: 'Show me around', examples: ['tour', 'overview', 'walk me through'] },
                { name: "What's new", examples: ["what's new", 'changelog', 'recent updates'] },
                { name: 'Version', examples: ['version', 'build'] },
            ],
        },
        {
            title: 'Personality',
            caption: 'Jokes, banter, vibes',
            icon: ICONS.emoji_emotions,
            intents: [
                { name: 'Greeting', examples: ['hi', 'hello', "g'day", 'morning'] },
                { name: 'Compliment', examples: ['thanks dora', 'love you', 'good bot', 'amazing'] },
                { name: 'Tease', examples: ['you suck', 'i hate you', 'bad bot'] },
                { name: 'Joke', examples: ['tell me a joke', 'make me laugh', 'pun'] },
                { name: 'Food fact', examples: ['food fact', 'random fact', 'trivia'] },
                { name: 'Tell me something', examples: ['tell me something', 'bored', 'fun'] },
                { name: 'Goodbye', examples: ['bye', 'cya', 'later'] },
            ],
        },
    ];

    type AiTool = { name: string; description: string; examples: string[]; icon: string };
    const aiTools: AiTool[] = [
        { name: 'search_stock', description: 'Free-form pantry lookup with filters (low only, expiring soon, by location).', examples: ['do I have any milk', "what's in the fridge", 'flagged items'], icon: ICONS.inventory_2 },
        { name: 'search_products', description: 'Search products across the configured stores.', examples: ['cheese at woolies', 'pasta on special'], icon: ICONS.storefront },
        { name: 'search_recipes', description: 'Direct recipe lookup by name, cuisine, difficulty, or cook time.', examples: ['easy italian dinners under 30 minutes', 'favourite curries'], icon: ICONS.menu_book },
        { name: 'suggest_recipes', description: 'Turns moods like "something spicy" into recipe searches.', examples: ['something cosy for tonight', 'what can I make with what I have'], icon: ICONS.lightbulb },
        { name: 'convert_measurement', description: 'Volume / mass / temperature. Density-aware for flour, sugar, butter, rice, etc.', examples: ['how many grams in a cup of flour', '180c to f'], icon: ICONS.straighten },
        { name: 'suggest_substitution', description: 'Curated ingredient swaps for ~25 common pantry items.', examples: ['what can I use instead of buttermilk', 'no eggs'], icon: ICONS.swap_horiz },
        { name: 'whats_expiring', description: 'Stock items inside a horizon (default 7 days).', examples: ["what's about to go off", 'use by today', 'expiring this week'], icon: ICONS.event },
        { name: 'find_deals', description: 'On-special products, sorted by % discount.', examples: ['any specials right now', 'cheap meat this week'], icon: ICONS.local_offer },
        { name: 'pantry_health', description: 'High-level pantry snapshot in one line.', examples: ["how's my pantry", 'pantry status'], icon: ICONS.monitor_heart },
        { name: 'meal_plan_for_date', description: 'What\'s scheduled for a date or range.', examples: ["what's for dinner tomorrow", "what's the plan for friday"], icon: ICONS.calendar_month },
        { name: 'recipes_using_item', description: 'Recipes that use a stock item.', examples: ['what can I make with these strawberries', 'recipes using mince'], icon: ICONS.restaurant_menu },
        { name: 'add_to_shopping_list', description: 'Add items to the primary list. Asks back when ambiguous; never auto-creates new stock items.', examples: ['add 3 apples and some milk', 'add bread to the list'], icon: ICONS.add_shopping_cart },
        { name: 'get_alerts', description: 'The bell-icon data: expired / expiring soon / low / out / stocktake overdue. Sortable by severity or kind.', examples: ['what needs attention', "anything urgent", 'show me the high-severity alerts'], icon: ICONS.notifications_active },
        { name: 'stock_item_detail', description: 'One item\'s level, location, expiry, recipes and list status.', examples: ['tell me about my milk', "how's the cheese looking"], icon: ICONS.inventory_2 },
        { name: 'recipe_detail', description: 'One recipe\'s ingredients, stock status, cook time and whether you can make it now.', examples: ['tell me about carbonara', "what's in lasagne", 'how do I make pad thai'], icon: ICONS.menu_book },
        { name: 'shopping_list_contents', description: 'What\'s on a shopping list, ticked and outstanding.', examples: ["what's on my list", "what's outstanding on the woolies list"], icon: ICONS.list_alt },
        { name: 'meal_detail', description: 'A meal\'s constituent recipes and their cook times.', examples: ['what recipes are in the Sunday roast meal', 'tell me about taco night'], icon: ICONS.restaurant },
        { name: 'find_location', description: 'What\'s in a location, optionally just the urgent items.', examples: ["what's in the fridge", 'anything urgent in the pantry'], icon: ICONS.place },
        { name: 'update_stock_level', description: 'Set an item\'s level (out / low / stocked). Confirm card before commit.', examples: ['I just used the last milk', 'mark eggs as low', 'cheese is fully stocked again'], icon: ICONS.tune },
        { name: 'mark_opened', description: 'Mark an item as opened (or closed via `closed: true`). Confirm card before commit.', examples: ['I opened the milk', 'closed the pasta sauce'], icon: ICONS.lock_open },
        { name: 'push_expiry', description: 'Shift an item\'s expiry by N days (positive or negative). Confirm card before commit.', examples: ['push the bread expiry by 3 days', 'add a week to the milk'], icon: ICONS.event_repeat },
        { name: 'tick_shopping_line', description: 'Tick or untick a line on the primary shopping list. Confirm card before commit.', examples: ['cross off bread on my list', 'I got the milk', "I haven't actually got the eggs yet"], icon: ICONS.check_circle },
        { name: 'move_item', description: 'Move a stock item to a different storage location. Confirm card before commit.', examples: ['move the cheese to the fridge', 'put the rice in the pantry'], icon: ICONS.drive_file_move },
        { name: 'plan_meal_for_date', description: "Add a meal to the meal plan for a date + slot (default Dinner, 1 serving). Confirm card before commit.", examples: ['plan carbonara for friday dinner', 'put taco night on tuesday'], icon: ICONS.event_available },
        { name: 'add_recipe_to_list', description: "Add a recipe's missing ingredients to the primary shopping list (or all ingredients via missing_only=false). Confirm card before commit.", examples: ["add what I need for carbonara to my list", 'add the missing ingredients for pad thai'], icon: ICONS.playlist_add },
        { name: 'compare_prices', description: 'Sort the products linked to a stock item by current price. Requires linked products on the item.', examples: ["where's milk cheapest right now", 'best price on cheese'], icon: ICONS.compare_arrows },
        { name: 'recipe_for_occasion', description: 'Translates a vibe ("kid-friendly", "date night", "comfort", "fancy", "weeknight"…) into recipe filters and ranks by stock coverage.', examples: ['something kid-friendly tonight', 'date night ideas', 'comfort food', 'fancy dessert'], icon: ICONS.celebration },
    ];

    const faceGuide: { mood: DoraMood; label: string; when: string }[] = [
        { mood: 'happy', label: 'Happy', when: 'Resting / default' },
        { mood: 'thinking', label: 'Thinking', when: 'AI is working on a reply' },
        { mood: 'searching', label: 'Searching', when: 'Looking up your data' },
        { mood: 'lightbulb', label: 'Lightbulb', when: 'Got an idea / suggestion' },
        { mood: 'confident', label: 'Confident', when: 'Direct answer (conversions, lookups)' },
        { mood: 'excited', label: 'Excited', when: 'Something good happened' },
        { mood: 'super_excited', label: 'Super excited', when: 'Compliment / big news (sparkles ✨)' },
        { mood: 'cute', label: 'Cute', when: 'Greetings, goodbyes, banter' },
        { mood: 'worried', label: 'Worried', when: 'Something needs your attention' },
        { mood: 'confused', label: 'Confused', when: "Didn't quite understand" },
        { mood: 'sad', label: 'Sad', when: 'Action failed / teasing' },
    ];

    const tips = [
        { title: 'Quick-action chips refresh', icon: ICONS.refresh, body: 'The three suggestion chips in the chat are a random sample. Hit the refresh button next to them to see a different set.' },
        { title: 'Compliment her', icon: ICONS.favorite, body: '"thanks dora", "love you", or "good bot" trigger a kawaii sparkle reaction. She just likes it.' },
        { title: 'Hover the launcher', icon: ICONS.pan_tool, body: "The burger icon bobs when you hover and wiggles when you click. She also takes a 1-minute nap if you don't interact." },
        { title: 'Basic mode works offline', icon: ICONS.cloud_off, body: 'If AI mode is down, the chat falls back to Basic mode automatically. The "AI / Basic" chip at the top tells you which is active.' },
        { title: 'Page-aware replies', icon: ICONS.place, body: 'Ask "what can I do here?" on any page and Dora gives you a contextual rundown of that screen.' },
    ];
</script>

<style scoped>
    .dora-mode-card {
        height: 100%;
    }
    .dora-feature-list {
        margin: 0;
        padding-left: 18px;
    }
    .dora-feature-list li {
        margin-bottom: 4px;
    }
    .dora-intent-block {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }
    .dora-intent-row {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    .dora-intent-name {
        font-weight: 500;
    }
    .dora-intent-examples {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
    }
    .dora-intent-example {
        font-size: 0.75rem;
    }
    .dora-face-card {
        min-height: 160px;
    }
</style>
