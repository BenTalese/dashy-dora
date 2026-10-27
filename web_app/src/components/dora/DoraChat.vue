<template>
    <q-card flat bordered class="dora-chat-card column" style="width: 360px">
        <q-card-section class="dora-chat-header q-py-sm">
            <div class="row items-center no-wrap">
                <!-- The acronym expansion hangs off the name text itself, not
                     the header row — a q-tooltip attaches to its *parent*
                     element, so as a sibling of the span it used to fire from
                     anywhere in the row (the mode slider, the close button…). -->
                <span class="dora-bot-name">
                    D.O.R.A.
                    <BaseTooltip anchor="bottom middle" self="top middle">
                        Delicious Organised Restock Assistant
                    </BaseTooltip>
                </span>
                <DoraModeSlider
                    class="q-ml-sm"
                    :model-value="modeSliderValue"
                    :disabled="!canToggleMode || togglingMode"
                    :disabled-reason="modeSliderDisabledReason"
                    :disabled-is-actionable="!canConfigureAi"
                    @update:model-value="onModeSliderToggle"
                    @disabled-activate="openAssistantSettings"
                />
                <q-space />
                <!-- speak Dora's replies. Hidden when the browser
                     has no SpeechSynthesis support. The toggle persists
                     across reloads via the user's saved preference; the
                     in-page click only flips the session-local view. -->
                <BaseButton
                    v-if="voiceOutputAvailable"
                    variant="icon"
                    :icon="voiceOutputEnabled ? ICONS.volume_up : ICONS.volume_off"
                    :color="voiceOutputEnabled ? 'primary' : undefined"
                    :aria-label="voiceOutputEnabled ? 'Mute Dora\'s voice' : 'Enable Dora\'s voice'"
                    @click="toggleVoiceOutput"
                >
                    <BaseTooltip>
                        {{ voiceOutputEnabled ? 'Mute Dora\'s replies' : 'Have Dora speak her replies' }}
                    </BaseTooltip>
                </BaseButton>
                <BaseButton
                    variant="icon"
                    :icon="ICONS.help_outline"
                    class="dora-accent-btn"
                    @click="openDoraHelp"
                >
                    <BaseTooltip>What can D.O.R.A. do?</BaseTooltip>
                </BaseButton>
                <BaseButton variant="icon" :icon="ICONS.close" @click="emit('close')" />
            </div>
            <div class="text-caption dora-text-muted">
                Your in-app helper. {{ pageHintForHeader }}
            </div>
        </q-card-section>

        <q-separator />

        <!-- AI-unavailable banner. Shows ONLY when the user has
             configured AI mode (`llm_enabled=true`) but it's currently
             unreachable / mis-configured. Plain Basic-mode users (no LLM
             configured) never see this — Basic isn't a failure, it's a
             valid baseline. -->
        <q-banner
            v-if="props.currentUser?.llm_enabled && aiActive === false"
            class="dora-bg-negative-soft text-negative dora-chat-status-banner"
            dense
            rounded
        >
            <template #avatar>
                <q-icon :name="ICONS.warning" size="18px" />
            </template>
            <div class="text-caption">
                <strong>AI mode unavailable. Using basic mode.</strong>
                <div v-if="aiUnavailableReason" class="dora-text-secondary">
                    {{ aiUnavailableReason }}
                </div>
            </div>
            <template #action>
                <BaseButton
                    variant="ghost"
                    dense
                    size="sm"
                    :loading="aiProbing"
                    :icon="ICONS.refresh"
                    label="Retry"
                    @click="refreshAiStatus"
                />
                <BaseButton
                    variant="ghost"
                    dense
                    size="sm"
                    label="Settings"
                    to="/settings/assistant"
                />
            </template>
        </q-banner>

        <q-scroll-area
            ref="messagesScrollEl"
            class="col dora-chat-scroll"
            :thumb-style="scrollThumbStyle"
            :bar-style="scrollBarStyle"
            visible
        >
            <div class="dora-chat-messages">
            <!-- suggestion cards. Render at the top of the
                 scroll area, above any chat history, so the user sees
                 them on open without scrolling. Each card has Accept
                 (navigates via primary_action), Dismiss, Snooze 1d,
                 and a Why? expander. -->
            <div
                v-if="suggestionStore.count > 0"
                class="dora-suggestion-panel"
            >
                <div class="text-caption dora-text-muted q-mb-xs">
                    <!-- R-034: was a bare Material name, which the MDI icon
                         set doesn't resolve. -->
                    <q-icon :name="ICONS.dora_voice" size="14px" class="q-mr-xs" />
                    Suggestions
                </div>
                <SuggestionCard
                    v-for="suggestion in suggestionStore.suggestions"
                    :key="`${suggestion.kind}:${suggestion.dedup_key}`"
                    :suggestion="suggestion"
                    @accept="onAcceptSuggestion(suggestion)"
                    @snooze="onSnoozeSuggestion(suggestion)"
                    @dismiss="onDismissSuggestion(suggestion)"
                />
            </div>
            <div
                v-for="(message, idx) in messages"
                :key="idx"
                class="dora-chat-message"
                :class="`dora-chat-message-${message.from}`"
            >
                <div class="dora-chat-bubble">
                    <div class="dora-chat-text">{{ message.displayText ?? message.text }}<span
                        v-if="message.from === 'dora' && message.displayText !== undefined && message.displayText.length < message.text.length"
                        class="dora-chat-caret"
                    >▌</span></div>
                    <div
                        v-if="message.navigateTo || message.externalLink"
                        class="dora-chat-actions q-mt-xs"
                    >
                        <BaseButton
                            v-if="message.navigateTo"
                            variant="primary"
                            size="sm"
                            :icon-right="iconForNav(message.navigateTo.path)"
                            :label="message.navigateTo.label"
                            @click="onNavigate(message.navigateTo.path)"
                        />
                        <!-- carve-out — raw q-btn: type="a" anchor form is not in BaseButton's type union. -->
                        <q-btn
                            v-if="message.externalLink"
                            size="sm"
                            no-caps
                            outline
                            color="primary"
                            icon-right="open_in_new"
                            :label="message.externalLink.label"
                            class="q-ml-xs"
                            type="a"
                            :href="message.externalLink.url"
                            target="_blank"
                            rel="noopener"
                        />
                    </div>
                    <!-- Per-message suggestion chips were dropped: the green
                         chip row at the bottom now absorbs that behaviour and
                         biases its order off the latest reply's suggestions. -->

                    <!-- Tier-2 confirm-style action: one summary + Confirm/Cancel. -->
                    <div
                        v-if="isConfirmAction(message.action) && message.action.status === 'ready' && !message.done"
                        class="dora-action-card q-mt-sm"
                    >
                        <div class="row q-gutter-sm q-mt-xs">
                            <BaseButton
                                variant="primary"
                                size="sm"
                                :icon="ICONS.check"
                                label="Confirm"
                                @click="confirmAction(message)"
                            />
                            <BaseButton
                                variant="ghost"
                                size="sm"
                                label="Cancel"
                                @click="cancelAction(message)"
                            />
                        </div>
                    </div>

                    <!-- Existing add-to-shopping-list flow: multi-item + chip disambiguation. -->
                    <div
                        v-if="isAddAction(message.action) && !message.action.no_primary"
                        class="dora-action-card q-mt-sm"
                    >
                        <div
                            v-for="(item, itemIdx) in message.action.items"
                            :key="itemIdx"
                            class="dora-action-item"
                        >
                            <div class="text-caption text-weight-medium">
                                <q-icon
                                    :name="itemIcon(item.status, message, itemIdx)"
                                    :color="itemIconColor(item.status, message, itemIdx)"
                                    size="16px"
                                    class="q-mr-xs"
                                />
                                <template v-if="item.status === 'ready'">
                                    {{ qtyLabel(item.quantity) }}{{ item.candidates[0]?.name }}
                                </template>
                                <template v-else-if="item.status === 'not_found'">
                                    Couldn't find “{{ item.query }}”
                                </template>
                                <template v-else-if="item.status === 'too_many'">
                                    Too many matches for “{{ item.query }}”
                                </template>
                                <template v-else>
                                    Which “{{ item.query }}”?
                                </template>
                            </div>
                            <div
                                v-if="item.status === 'ambiguous' && !message.done"
                                class="row q-gutter-xs q-mt-xs"
                            >
                                <q-chip
                                    v-for="candidate in item.candidates"
                                    :key="candidate.stock_item_id"
                                    dense
                                    clickable
                                    :outline="message.selections?.[itemIdx] !== candidate.stock_item_id"
                                    color="primary"
                                    @click="selectCandidate(message, itemIdx, candidate.stock_item_id)"
                                >
                                    {{ candidate.name
                                    }}<span v-if="candidate.location"> · {{ candidate.location }}</span>
                                </q-chip>
                            </div>
                        </div>
                        <BaseButton
                            v-if="!message.done"
                            variant="primary"
                            size="sm"
                            icon-right="add_shopping_cart"
                            class="q-mt-sm"
                            :label="`Add to ${message.action.shopping_list?.name ?? 'list'}`"
                            :disable="!canCommit(message)"
                            @click="commitAction(message)"
                        />
                    </div>
                </div>
            </div>

            <div v-if="thinking" class="dora-chat-message dora-chat-message-dora">
                <div class="dora-chat-bubble dora-chat-thinking">
                    <q-spinner-dots size="20px" color="primary" />
                </div>
            </div>
            </div>
        </q-scroll-area>

        <q-separator />

        <q-card-section class="q-py-sm">
            <!-- ── On-this-page actions (P14) ────────────────────────────
                 These are the most likely next moves for the current
                 screen, wired through the same composables (P0) the rest
                 of the app uses. Empty on screens with nothing specific
                 to suggest, in which case we just lead with the generic
                 quick-actions below. -->
            <div
                v-if="contextualActions.length > 0"
                class="dora-context-row q-mb-sm"
            >
                <div class="text-caption dora-text-muted q-mb-xs">
                    <q-icon :name="ICONS.adjust" size="12px" />
                    On this page
                </div>
                <div class="row q-gutter-xs">
                    <q-chip
                        v-for="(action, idx) in contextualActions"
                        :key="idx"
                        dense
                        clickable
                        color="primary"
                        text-color="white"
                        :icon="action.icon"
                        @click="onContextualAction(action)"
                    >
                        {{ action.label }}
                    </q-chip>
                </div>
            </div>

            <div class="row no-wrap items-center q-mb-sm dora-chip-row">
                <div class="row q-gutter-xs col">
                    <q-chip
                        v-for="chip in visibleChips"
                        :key="chip.key"
                        dense
                        clickable
                        outline
                        color="primary"
                        @click="onChipClick(chip)"
                    >
                        {{ chip.label }}
                    </q-chip>
                </div>
                <BaseButton
                    v-if="canRotateChips"
                    variant="icon"
                    size="sm"
                    :icon="ICONS.refresh"
                    class="dora-help-btn q-ml-xs"
                    @click="rotateChips"
                >
                    <BaseTooltip>Show different suggestions</BaseTooltip>
                </BaseButton>
            </div>

            <q-input
                v-model="draft"
                :placeholder="voiceListening ? (voiceTranscript || 'Listening…') : 'Ask Dora anything…'"
                outlined
                dense
                autogrow
                @keydown.enter.prevent="onSubmit"
            >
                <template #append>
                    <!-- mic button. Push-to-talk: tap to start,
                         tap again (or wait for a final result) to stop.
                         Hidden when the browser doesn't expose the Web
                         Speech API. Disabled while Dora is sending so
                         we don't overwrite the user's draft mid-flight. -->
                    <BaseButton
                        v-if="voiceInputAvailable"
                        variant="icon"
                        :icon="voiceListening ? ICONS.mic : ICONS.mic_none"
                        :color="voiceListening ? 'negative' : undefined"
                        :class="voiceListening ? 'dora-mic-listening' : ''"
                        :aria-label="voiceListening ? 'Stop listening' : 'Start voice input'"
                        @click="toggleVoiceInput"
                    >
                        <BaseTooltip>
                            {{ voiceListening ? 'Stop listening' : 'Voice input' }}
                        </BaseTooltip>
                    </BaseButton>
                    <BaseButton
                        variant="icon"
                        :icon="ICONS.send"
                        :class="draft.trim() ? 'dora-accent-btn' : ''"
                        :disable="!draft.trim()"
                        @click="onSubmit"
                    />
                </template>
            </q-input>
        </q-card-section>
    </q-card>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import DoraModeSlider from 'src/components/dora/DoraModeSlider.vue';
    import SuggestionCard from 'src/components/dora/SuggestionCard.vue';
    import { ICONS } from 'src/style/icons';
    import { storeToRefs } from 'pinia';
    import type { DoraMood } from 'src/components/dora/doraTypes';
    import { useQuickAdd } from 'src/composables/useQuickAdd';
    import { useShoppingListActions } from 'src/composables/useShoppingListActions';
    import { useStockItemActions } from 'src/composables/useStockItemActions';
    import type { AuthenticatedUser } from 'src/models/auth';
    import AlertApiService from 'src/services/api/alertApiService';
    import AssistantApiService, {
        type AddToShoppingListAction,
        type CommitAddItem,
        type ConfirmAction,
        type PendingAction,
    } from 'src/services/api/assistantApiService';
    import HealthApiService from 'src/services/api/healthApiService';
    import HelpApiService from 'src/services/api/helpApiService';
    import {
        contextualActionsFor,
        type ContextualAction,
    } from 'src/services/doraContextualActions';
    import {
        detectIntent,
        extractAddToListItems,
        labelFor,
        runIntent,
        type DoraContext,
        type DoraIntentId
    } from 'src/services/doraIntents';
    import { useMealPlanStore } from 'src/stores/mealPlanStore';
    import { useRecipeStore } from 'src/stores/recipeStore';
    import { useRecipeVocabStore } from 'src/stores/recipeVocabStore';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { useStockItemStore } from 'src/stores/stockItemStore';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';
    import { useLocationStore } from 'src/stores/locationStore';
    import type { LocationNode } from 'src/models/location';
    import { localTodayIso } from 'src/helpers/weekDates';
    import { useSuggestionStore } from 'src/stores/suggestionStore';
    import type { DoraSuggestion } from 'src/services/api/suggestionsApiService';
    import { useAuthStore } from 'src/stores/authStore';
    import { useVoiceInput } from 'src/composables/useVoiceInput';
    import { useSpeechOutput } from 'src/composables/useSpeechOutput';
    import type { QScrollArea } from 'quasar';
    import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
    import { useRoute, useRouter } from 'vue-router';
    import { openProductSearch } from 'src/composables/useProductSearchUrl';
    import { describeApiError } from 'src/services/errorHandling/apiErrorHandler';

    type Message = {
        from: 'user' | 'dora';
        text: string;
        // Animated reveal — for dora messages we set displayText to '' on
        // push and grow it character-by-character so the talking face has
        // something visible to sync against. User messages skip it.
        displayText?: string;
        mood?: DoraMood;
        navigateTo?: { path: string; label: string } | undefined;
        externalLink?: { url: string; label: string } | undefined;
        suggestions?: DoraIntentId[] | undefined;
        // Proposed shopping-list addition awaiting the user's confirmation /
        // disambiguation. `selections` maps an ambiguous item index to the
        // chosen candidate id; `done` disables the card after committing.
        action?: PendingAction;
        selections?: Record<number, string>;
        done?: boolean;
    };

    const props = defineProps<{ currentUser: AuthenticatedUser | null }>();
    const emit = defineEmits<{
        (e: 'close'): void;
        // Fired whenever the user actively submits something — free-form
        // prompt, quick-action chip, or contextual action. The launcher uses
        // this to reset its sleep timer (Dora wakes up when you talk to her).
        (e: 'prompt-submitted'): void;
        // Fired when a reply lands so the launcher mascot can mirror the
        // conversation's current expression — this is the BIG visible Dora,
        // so the per-message mood reactions live here now (the mini one in
        // the header was retired).
        (e: 'mood', mood: DoraMood): void;
        // Fired while we wait on a backend reply so the launcher can wear
        // the thinking face during the round-trip.
        (e: 'thinking', value: boolean): void;
        // Fired while a dora message's text is streaming in (typewriter).
        // The launcher uses this to drive the lip-flap talking overlay —
        // ON when reveal starts, OFF a beat after reveal finishes so the
        // animation lingers long enough to register.
        (e: 'talking', value: boolean): void;
        // Fired when the /assistant/status probe transitions the AI's
        // reachability. Only emitted as `offline` once AI has been seen
        // working in this session — so users who never configured AI don't
        // get a permanent "offline" face for what's just normal Basic mode.
        (e: 'ai-offline', value: boolean): void;
    }>();

    const route = useRoute();
    const router = useRouter();
    const helpApi = new HelpApiService();
    // The household's expiring-soon window for Basic mode (11-R34); `/health`
    // is probed once per session and shared.
    const expiringSoonWindowDays = ref<number | undefined>(undefined);
    void new HealthApiService().getInfoAsync()
        .then((info) => { expiringSoonWindowDays.value = info.alerts_policy?.expiring_soon_window_days; })
        .catch(() => undefined);
    const alertApi = new AlertApiService();
    const assistantApi = new AssistantApiService();
    // suggestion panel reads from the same store as the
    // launcher badge, so dismissing here updates the badge instantly.
    const suggestionStore = useSuggestionStore();

    async function onAcceptSuggestion(suggestion: DoraSuggestion) {
        // "Accept" = navigate to the suggestion's primary action and
        // let the existing domain flow take it from there. We also
        // snooze for 1 hour so the suggestion doesn't immediately
        // re-surface while the user is mid-task; if the underlying
        // condition truly resolves the next refresh will skip it
        // organically.
        if (!suggestion.primary_action) return;
        try {
            await suggestionStore.snoozeAsync(suggestion, 1);
        } catch {
            // Non-fatal — still navigate even if the snooze write
            // failed; the worst case is the suggestion reappears.
        }
        emit('close');
        void router.push(suggestion.primary_action.path);
    }

    async function onDismissSuggestion(suggestion: DoraSuggestion) {
        try {
            await suggestionStore.dismissAsync(suggestion);
        } catch (err) {
            console.error('Failed to dismiss suggestion', err);
        }
    }

    async function onSnoozeSuggestion(suggestion: DoraSuggestion) {
        try {
            await suggestionStore.snoozeAsync(suggestion, 24);
        } catch (err) {
            console.error('Failed to snooze suggestion', err);
        }
    }

    // ── Cross-feature composables used by the contextual actions (P14).
    // Reaching for the same composables every other screen uses keeps
    // behaviour (notifications, quantity defaults, error handling) honest.
    const stockActions = useStockItemActions();
    const { addItems } = useShoppingListActions();
    const { openQuickAdd } = useQuickAdd();

    const recipeStore = useRecipeStore();
    // chat handlers need the dietary-tag vocab to convert
    // ids on recipes into names ("vegetarian", "gluten free") for
    // substring matching.
    const recipeVocabStore = useRecipeVocabStore();
    const stockItemStore = useStockItemStore();
    const mealStore = useMealPlanStore();
    const stockLevelStore = useStockLevelStore();
    const locationStore = useLocationStore();
    const shoppingListStore = useShoppingListStore();
    const { recipes } = storeToRefs(recipeStore);
    const { stockItems } = storeToRefs(stockItemStore);
    const { stockLevels } = storeToRefs(stockLevelStore);

    const messages = ref<Message[]>([]);
    const draft = ref('');
    const thinking = ref(false);
    const messagesScrollEl = ref<QScrollArea | null>(null);

    // ── P2-13 voice ─────────────────────────────────────────────────────
    // Voice input: push-to-talk. Tap the mic, speak, tap again (or wait
    // for the final result). The transcript replaces the draft so the
    // user can still review / edit before pressing Send — that's the
    // spec's "confirmation before mutating actions" without needing
    // an explicit confirm step.
    const authStore = useAuthStore();
    const speechOut = useSpeechOutput();
    const voiceOutputEnabled = ref<boolean>(
        authStore.currentUser?.voice_output_enabled ?? false,
    );
    const voiceOutputAvailable = computed(() => speechOut.available.value);

    const voiceInput = useVoiceInput({
        continuous: false,
        onFinal(text) {
            // Append to whatever the user had typed; clearing would be
            // surprising mid-edit. Trim and space-join so multi-burst
            // dictation reads naturally.
            const existing = draft.value.trim();
            draft.value = existing ? `${existing} ${text}` : text;
        },
    });
    const voiceInputAvailable = computed(() => voiceInput.available.value);
    const voiceListening = computed(() => voiceInput.listening.value);
    const voiceTranscript = computed(() => voiceInput.transcript.value);

    function toggleVoiceInput() {
        voiceInput.toggle();
    }

    async function toggleVoiceOutput() {
        const next = !voiceOutputEnabled.value;
        voiceOutputEnabled.value = next;
        if (!next) speechOut.cancel();
        // Persist the change to the user's profile — silent failure is
        // fine because the toggle still applies for the current session
        // even if the backend write didn't land.
        try {
            await authStore.updateMeAsync({ voice_output_enabled: next });
        } catch {
            /* leave the local state as-is */
        }
    }

    // Re-seed the local toggle when the auth store reloads (e.g. login,
    // refresh, multi-tab) so two tabs don't drift.
    watch(
        () => authStore.currentUser?.voice_output_enabled,
        (saved) => {
            if (saved !== undefined && saved !== voiceOutputEnabled.value) {
                voiceOutputEnabled.value = saved;
            }
        },
    );

    // Bubble up thinking-state changes so the launcher mascot can flip to
    // the thinking face while a backend round-trip is in flight.
    watch(thinking, (value) => emit('thinking', value));

    const scrollThumbStyle = {
        right: '2px',
        borderRadius: '4px',
        background: 'var(--q-secondary)',
        width: '6px',
        opacity: '0.6',
    } as const;
    const scrollBarStyle = {
        right: '0px',
        borderRadius: '4px',
        background: 'transparent',
        width: '10px',
        opacity: '0.2',
    } as const;
    // ── Suggestion chips ─────────────────────────────────────────────
    // The bottom chip row absorbs what used to be per-message grey chips:
    // its order is biased by the latest reply's `suggestions` so a follow-up
    // from what Dora just said sits first, then the row is filled from the
    // mode's pool (basic = intent shortcuts; AI = natural-language prompts).
    // Capped so the row stays breathable.
    type ChipDispatch =
        | { kind: 'intent'; id: DoraIntentId }
        | { kind: 'prompt'; text: string };
    type Chip = { key: string; label: string; dispatch: ChipDispatch };

    const CHIP_LIMIT = 4;

    // Basic-mode pool: intent shortcuts the rule engine handles directly.
    // Ordered by everyday usefulness — practical pantry asks first, then
    // app-help, then personality/fun. Refresh button cycles through these.
    const BASIC_CHIP_POOL: DoraIntentId[] = [
        'whats_for_dinner',
        'attention',
        'pantry_summary',
        'low_stock',
        'expiring',
        'shopping_list_status',
        'weeks_meals',
        'find_recipe',
        'convert',
        'substitute',
        'page_help',
        'how_do_i',
        'show_around',
        'guides',
        'whats_new',
        'food_fact',
        'tell_me_something',
        'joke',
        'report_issue',
    ];

    // AI-mode pool: full-sentence prompts that play to the model's strengths.
    // Each is what would be sent to /ask if clicked — the chip label is the
    // short version shown on the button. Wider pool than basic since AI can
    // handle the open-ended natural-language ones too.
    const AI_CHIP_POOL: { label: string; prompt: string }[] = [
        // Pantry data
        { label: "What's for dinner?", prompt: "what's for dinner tonight" },
        { label: 'What needs attention?', prompt: 'what needs my attention right now' },
        { label: "What's expiring?", prompt: "what's about to go off this week" },
        { label: "What's low?", prompt: "what's running low in my pantry" },
        { label: 'Pantry health', prompt: "how's my pantry looking" },
        { label: "What's on my list?", prompt: "what's on my shopping list" },
        { label: "What's in the fridge?", prompt: "what's in the fridge" },
        // Recipe ideas
        { label: 'What can I cook now?', prompt: 'what can I make with what I have' },
        { label: 'Kid-friendly tonight', prompt: 'something kid-friendly tonight' },
        { label: 'Comfort food', prompt: 'comfort food ideas' },
        { label: 'Quick weeknight', prompt: 'something quick for a weeknight' },
        { label: 'Date night', prompt: 'date night recipe ideas' },
        { label: 'Fancy dessert', prompt: 'fancy dessert ideas' },
        // Shopping + deals
        { label: "What's in season?", prompt: "what's in season right now" },
        { label: 'Any deals?', prompt: "what's on special right now" },
        { label: 'Compare prices', prompt: "where's milk cheapest right now" },
        // Kitchen helpers
        { label: 'Substitute for…', prompt: 'what can I use instead of buttermilk' },
        { label: 'Convert units', prompt: 'how many ml in a cup of flour' },
        // Planning
        { label: "What's the plan?", prompt: "what's on the meal plan this week" },
        // App help
        { label: "What's new?", prompt: "what's new in the app" },
        { label: 'How do I…?', prompt: 'how do I add a stock item' },
        { label: 'What can I do here?', prompt: 'what can I do on this page' },
        { label: 'Show me around', prompt: 'give me a tour of the app' },
        // Personality
        { label: 'Tell me a joke', prompt: 'tell me a joke' },
        { label: 'Random food fact', prompt: 'tell me a random food fact' },
        { label: 'Tell me something', prompt: 'tell me something silly' },
        { label: 'Thanks D.O.R.A.', prompt: 'thanks dora' },
        { label: 'I found an issue', prompt: 'i found an issue' },
    ];

    // Map intent IDs → AI-mode chip (label + prompt). Used to translate a
    // reply's `suggestions: DoraIntentId[]` into AI chips when the bias
    // runs in AI mode. If an intent has no entry it just doesn't bias the
    // AI row — basic mode still uses it directly via labelFor().
    const INTENT_TO_AI_CHIP: Partial<Record<DoraIntentId, { label: string; prompt: string }>> = {
        attention: { label: 'What needs attention?', prompt: 'what needs my attention right now' },
        pantry_summary: { label: 'Pantry health', prompt: "how's my pantry looking" },
        low_stock: { label: "What's low?", prompt: "what's running low in my pantry" },
        expiring: { label: "What's expiring?", prompt: "what's about to go off this week" },
        shopping_list_status: { label: "What's on my list?", prompt: "what's on my shopping list" },
        whats_for_dinner: { label: "What's for dinner?", prompt: "what's for dinner tonight" },
        weeks_meals: { label: "What's the plan?", prompt: "what's on the meal plan this week" },
        joke: { label: 'Tell me a joke', prompt: 'tell me a joke' },
        food_fact: { label: 'Food fact', prompt: 'tell me a food fact' },
        tell_me_something: { label: 'Tell me something', prompt: 'tell me something silly' },
        guides: { label: 'Open the guides', prompt: 'show me the guides' },
        compliment: { label: 'Thanks Dora', prompt: 'thanks dora' },
        substitute: { label: 'Substitute for…', prompt: 'what can I use instead of buttermilk' },
        convert: { label: 'Convert units', prompt: 'how many ml in a cup of flour' },
        find_recipe: { label: 'Find a recipe', prompt: 'find me a recipe for pasta' },
        show_around: { label: 'Show me around', prompt: 'give me a tour of the app' },
        page_help: { label: 'What can I do here?', prompt: 'what can I do on this page' },
        how_do_i: { label: 'How do I…?', prompt: 'how do I add a stock item' },
        whats_new: { label: "What's new?", prompt: "what's new in the app" },
        report_issue: { label: 'I found an issue', prompt: 'i found an issue' },
    };

    // Latest reply's suggestion list, in order. Drives the front-of-row bias.
    const latestSuggestions = computed<DoraIntentId[]>(() => {
        for (let i = messages.value.length - 1; i >= 0; i--) {
            const m = messages.value[i];
            if (m?.from === 'dora' && m.suggestions?.length) {
                return m.suggestions;
            }
        }
        return [];
    });

    // Refresh cursor — advanced by the refresh button. Suspends the
    // reply-bias for the current turn (so every slot is a fresh pool chip);
    // a new reply resets both the cursor and the suspension so the bias
    // returns. This gives the refresh button real power instead of only
    // ever cycling the trailing 2-3 slots behind pinned suggestions.
    const chipCursor = ref(0);
    const suppressReplyBias = ref(false);

    function rotate<T>(arr: readonly T[], offset: number): T[] {
        if (arr.length === 0) return [];
        const n = ((offset % arr.length) + arr.length) % arr.length;
        return [...arr.slice(n), ...arr.slice(0, n)];
    }

    const visibleChips = computed<Chip[]>(() => {
        const seen = new Set<string>();
        const out: Chip[] = [];
        const push = (chip: Chip) => {
            if (seen.has(chip.key) || out.length >= CHIP_LIMIT) return;
            seen.add(chip.key);
            out.push(chip);
        };
        const useReplyBias = !suppressReplyBias.value;

        if (aiActive.value) {
            if (useReplyBias) {
                for (const id of latestSuggestions.value) {
                    const ai = INTENT_TO_AI_CHIP[id];
                    if (ai) push({ key: `prompt:${ai.prompt}`, label: ai.label, dispatch: { kind: 'prompt', text: ai.prompt } });
                }
            }
            for (const entry of rotate(AI_CHIP_POOL, chipCursor.value)) {
                push({ key: `prompt:${entry.prompt}`, label: entry.label, dispatch: { kind: 'prompt', text: entry.prompt } });
            }
        } else {
            if (useReplyBias) {
                for (const id of latestSuggestions.value) {
                    push({ key: `intent:${id}`, label: labelFor(id), dispatch: { kind: 'intent', id } });
                }
            }
            for (const id of rotate(BASIC_CHIP_POOL, chipCursor.value)) {
                push({ key: `intent:${id}`, label: labelFor(id), dispatch: { kind: 'intent', id } });
            }
        }
        return out;
    });

    // Only worth showing the refresh button when the active pool actually
    // has more entries than fit on the row (after the reply-bias chips).
    const canRotateChips = computed(() => {
        const poolSize = aiActive.value ? AI_CHIP_POOL.length : BASIC_CHIP_POOL.length;
        return poolSize > CHIP_LIMIT;
    });

    function rotateChips() {
        // First press just suspends the reply-bias (so the row immediately
        // changes by giving the pool the front slots back); subsequent
        // presses advance the cursor through the pool.
        if (!suppressReplyBias.value && latestSuggestions.value.length > 0) {
            suppressReplyBias.value = true;
        } else {
            chipCursor.value += CHIP_LIMIT;
        }
    }

    // When Dora replies (suggestions change), reset the cursor and bring the
    // reply-bias back so the row reflects the new reply.
    watch(latestSuggestions, () => {
        chipCursor.value = 0;
        suppressReplyBias.value = false;
    });

    function onChipClick(chip: Chip) {
        if (chip.dispatch.kind === 'intent') {
            onIntentClick(chip.dispatch.id);
            return;
        }
        void submitPromptText(chip.dispatch.text);
    }

    function openDoraHelp() {
        void router.push('/help/dora');
        emit('close');
    }

    // The mode slider can't turn AI on until a provider is connected. Rather
    // than sitting inert behind a hover-only explanation (invisible on touch),
    // tapping it takes the user to the page where they can fix that.
    function openAssistantSettings() {
        void router.push('/settings/assistant');
        emit('close');
    }

    // ── Contextual quick actions (P14) ───────────────────────────────
    // Recompute on every route change so navigating between recipes /
    // stock items / lists updates the chip row live.
    const contextualActions = computed<ContextualAction[]>(() =>
        contextualActionsFor(route.path, {
            id: typeof route.params.id === 'string' ? route.params.id : undefined,
        }),
    );
    // Whether the assistant is running on AI vs the rule-based fallback.
    // null = not yet known (hides the badge until the first status check).
    // We only flip this from the cheap /assistant/status probe (initially on
    // mount and again whenever a request fails) — NOT from each /ask reply.
    // A single timed-out chat call shouldn't downgrade the badge if the
    // model is still actually reachable; that caused visible flickering.
    const aiActive = ref<boolean | null>(null);
    // reason string surfaced when the user has `llm_enabled=true`
    // but `ai_available=false`. Drives the "AI mode unavailable" banner
    // at the top of the chat panel + a Retry affordance. Null when AI is
    // available (banner hidden) or when the user is in plain Basic mode
    // (`llm_enabled=false`, no banner — Basic isn't an error).
    const aiUnavailableReason = ref<string | null>(null);
    const aiProbing = ref(false);

    // Tracks whether AI has been confirmed reachable at least once in this
    // session. Used to gate the "offline" face — without this, anyone who
    // hasn't configured an LLM at all would see the sad-error mascot, which
    // is wrong (Basic mode is the intended baseline, not a failure).
    let aiEverAvailable = false;

    // FU-360 #3 — Basic/AI slider toggle. The slider tracks the user's
    // `llm_enabled` preference (source of truth); flipping it PATCHes /auth/me
    // and re-probes assistant status. Disabled when the user hasn't finished
    // configuring a provider, or during the in-flight PATCH. AI mode is a
    // purely per-user opt-in now — no install-wide master switch. Mirrors the
    // guard logic in AssistantSettings.vue.
    const togglingMode = ref(false);

    const modeSliderValue = computed(() => !!props.currentUser?.llm_enabled);

    const canConfigureAi = computed(() => {
        const u = props.currentUser;
        if (!u) return false;
        // Already on, or a provider is configured + verified (server-derived).
        return u.llm_enabled || u.assistant_ready;
    });

    const canToggleMode = computed(() => {
        if (!props.currentUser) return false;
        return canConfigureAi.value;
    });

    const modeSliderDisabledReason = computed(() => {
        const u = props.currentUser;
        if (!u) return '';
        if (!u.assistant_ready) {
            return 'Connect a language model in Settings → Assistant first.';
        }
        return '';
    });

    async function onModeSliderToggle(next: boolean) {
        if (togglingMode.value) return;
        togglingMode.value = true;
        try {
            await authStore.updateMeAsync({ llm_enabled: next });
            await refreshAiStatus();
        } catch {
            // Leave the slider position mirroring currentUser — the PATCH
            // failure will surface via the auth-store's own error handling.
        } finally {
            togglingMode.value = false;
        }
    }

    async function refreshAiStatus() {
        aiProbing.value = true;
        try {
            const s = await assistantApi.getStatusAsync();
            aiActive.value = s.ai_available;
            aiUnavailableReason.value = s.ai_available ? null : (s.reason ?? null);
            if (s.ai_available) {
                aiEverAvailable = true;
                emit('ai-offline', false);
            } else if (aiEverAvailable) {
                emit('ai-offline', true);
            }
        } catch {
            aiActive.value = false;
            aiUnavailableReason.value = "Couldn't reach the server to check AI status.";
            if (aiEverAvailable) emit('ai-offline', true);
        } finally {
            aiProbing.value = false;
        }
    }

    const pageHintForHeader = computed(() => {
        const p = route.path;
        if (p === '/' || p === '') return 'Dashboard view.';
        const segment = p.split('/').filter(Boolean)[0];
        if (!segment) return '';
        return `${segment.replace(/-/g, ' ').replace(/^\w/, (c) => c.toUpperCase())} view.`;
    });

    function iconForNav(path: string): string {
        if (path === '/help') return 'help';
        if (path.startsWith('/stock')) return 'inventory_2';
        if (path.startsWith('/cookbook')) return 'menu_book';
        return 'arrow_forward';
    }

    // Build snapshots off the Pinia stores. Stores are autoloaded elsewhere
    // in the app (Dashboard, Stock, etc.); if they haven't been loaded in
    // this session yet we return empty arrays and the intent handlers
    // degrade with friendly "nothing tracked yet" messaging.
    function context(): DoraContext {
        return {
            currentPath: route.path,
            username: props.currentUser?.username,
            expiringSoonWindowDays: expiringSoonWindowDays.value,
            fetchFoodFact: async () => (await helpApi.getFoodFactAsync()).fact,
            fetchVersion: async () => {
                const v = await helpApi.getVersionAsync();
                return {
                    current: v.current_version,
                    latest: v.latest_version,
                    updateAvailable: v.update_available,
                    releaseUrl: v.release_url,
                };
            },
            fetchAttention: async () => {
                const a = await alertApi.getAlertsAsync();
                return {
                    high: a.high_count,
                    medium: a.medium_count,
                    low: a.low_count,
                    topMessages: a.items.slice(0, 3).map((alert) => alert.message),
                };
            },
            getStock: () => {
                const levels = stockLevels.value;
                const levelById = new Map(levels.map((l) => [l.stock_level_id, l]));
                // Zone name per item from the location tree (the display
                // policy every chip uses — `formatLocation(…, 'zone')`), so
                // Basic-mode "where is X" answers; it used to stamp null for
                // every item (finalisation 11-R4).
                const zoneByItem = new Map<string, string>();
                const walk = (nodes: LocationNode[], zone: string) => {
                    for (const node of nodes) {
                        const zoneName = zone || node.name;
                        for (const item of node.items) zoneByItem.set(item.stock_item_id, zoneName);
                        walk(node.children, zoneName);
                    }
                };
                walk(locationStore.tree, '');
                return stockItems.value.map((s) => {
                    const lvl = levelById.get(s.stock_level_id);
                    return {
                        id: s.stock_item_id,
                        name: s.name,
                        levelName: lvl?.name ?? null,
                        levelSequence: lvl?.sequence ?? null,
                        locationName: zoneByItem.get(s.stock_item_id) ?? null,
                        expiryDate: s.expiry_date ?? null,
                        isEssential: Boolean(s.is_essential),
                        isOpen: Boolean(s.is_open),
                    };
                });
            },
            getRecipes: () => {
                // resolve dietary tag ids → names once per call
                // so the chat handler can substring-match "vegetarian"
                // / "gluten free" against recipes without an N×M scan
                // of the vocab.
                const tagNameById = new Map(
                    (recipeVocabStore.dietaryTags ?? []).map(
                        (t) => [t.dietary_tag_id, t.name],
                    ),
                );
                return recipes.value.map((r) => ({
                    id: r.recipe_id,
                    name: r.name,
                    cuisine: r.cuisine_name,
                    category: r.category_name,
                    cookTimeMinutes: r.cook_time_minutes,
                    isFavourite: Boolean(r.is_favourite),
                    ingredientStockItemIds: r.ingredients
                        .map((i) => i.stock_item_id)
                        .filter((id): id is string => !!id),
                    dietaryTagNames: (r.dietary_tag_ids ?? [])
                        .map((id) => tagNameById.get(id))
                        .filter((n): n is string => !!n),
                    timeOfDay: r.time_of_day ?? null,
                }));
            },
            getShoppingLists: () => shoppingListStore.summaries.map((l) => ({
                id: l.shopping_list_id,
                name: l.display_name,
                itemCount: l.line_count,
                isQuickAddTarget: l.shopping_list_id === shoppingListStore.quickAddTargetListId,
            })),
            getMealPlan: () => {
                const plans = mealStore.mealPlans;
                if (!plans || plans.length === 0) return null;
                // Plans sorted ascending by start_date — pick the soonest one
                // that hasn't fully passed. Surface up to 5 next meal names.
                // Household today from the server (R-021), local date before
                // it loads — never the UTC date (finalisation 11-R33).
                const today = mealStore.today ?? localTodayIso();
                const live = plans.find((p) =>
                    p.entries.some((e) => e.scheduled_for >= today),
                ) ?? plans[plans.length - 1]!;
                const upcoming = [...live.entries]
                    .filter((e) => e.scheduled_for >= today)
                    .sort((a, b) => a.scheduled_for.localeCompare(b.scheduled_for))
                    .slice(0, 5)
                    .map((e) => `${e.scheduled_for}: ${e.recipe_name} (×${e.servings})`);
                const lastDate = live.entries.length
                    ? live.entries.map((e) => e.scheduled_for).sort().at(-1)!
                    : live.start_date;
                return {
                    startDate: live.start_date,
                    endDate: lastDate,
                    upcomingMealNames: upcoming,
                };
            },
        };
    }

    async function scrollToBottom() {
        await nextTick();
        // One extra frame so any DOM that was just appended (typing dots,
        // freshly-pushed message bubble) has been laid out before the scroll
        // target is measured. Without this, setScrollPercentage sometimes
        // animates to a position that's already the old bottom.
        await new Promise((r) => requestAnimationFrame(r));
        const el = messagesScrollEl.value;
        if (!el) return;
        const target = el.getScrollTarget();
        // Seek to the real measured bottom rather than a clamped percentage —
        // percentage targets can resolve stale when content height grows
        // mid-animation.
        el.setScrollPosition('vertical', target.scrollHeight, 200);
    }

    // Per-character reveal so the talking face has something to sync against.
    // 22ms/char feels fluid; for very long replies we accelerate slightly so
    // we don't keep the user waiting more than ~3s for the full text. The
    // talking event stays on for an extra TALK_TAIL_MS after the last char
    // so the lip-flap is visible even on short replies.
    const TYPE_CHAR_MS = 22;
    const TYPE_MAX_TOTAL_MS = 3000;
    const TALK_TAIL_MS = 600;
    let activeTypewriter: { cancel: () => void } | null = null;

    function startTypewriter(message: Message) {
        if (activeTypewriter) activeTypewriter.cancel();
        const full = message.text;
        message.displayText = '';
        if (!full) {
            emit('talking', false);
            return;
        }
        const charMs = Math.max(8, Math.min(TYPE_CHAR_MS, Math.floor(TYPE_MAX_TOTAL_MS / full.length)));
        let i = 0;
        let cancelled = false;
        emit('talking', true);
        const tick = () => {
            if (cancelled) return;
            i += 1;
            message.displayText = full.slice(0, i);
            // Throttled scroll-follow so the new lines don't disappear below
            // the fold while typing.
            if (i % 6 === 0) void scrollToBottom();
            if (i >= full.length) {
                message.displayText = full;
                void scrollToBottom();
                setTimeout(() => {
                    if (!cancelled) emit('talking', false);
                }, TALK_TAIL_MS);
                activeTypewriter = null;
                return;
            }
            timer = setTimeout(tick, charMs);
        };
        let timer = setTimeout(tick, charMs);
        activeTypewriter = {
            cancel: () => {
                cancelled = true;
                clearTimeout(timer);
                message.displayText = full;
                emit('talking', false);
                activeTypewriter = null;
            },
        };
    }

    function pushDoraMessage(reply: Awaited<ReturnType<typeof runIntent>>) {
        const message: Message = {
            from: 'dora',
            text: reply.text,
            displayText: '',
            mood: reply.mood,
            navigateTo: reply.navigateTo,
            externalLink: reply.externalLink,
            suggestions: reply.suggestions,
        };
        messages.value.push(message);
        emit('mood', reply.mood);
        // Mutate the in-array (reactive-proxied) reference, not the local
        // one we just built — otherwise per-char displayText writes don't
        // trigger re-renders and the bubble stays empty until something
        // else nudges reactivity.
        startTypewriter(messages.value[messages.value.length - 1]!);
        // speak the reply when the user has opted in. Runs in
        // parallel with the typewriter so the audio and on-screen text
        // start at roughly the same moment.
        if (voiceOutputEnabled.value) {
            speechOut.speak(reply.text);
        }
    }

    function qtyLabel(quantity: number | null): string {
        return quantity !== null ? `${quantity} ` : '';
    }

    function isResolved(message: Message, itemIdx: number): boolean {
        const action = message.action;
        if (!isAddAction(action)) return false;
        const item = action.items[itemIdx];
        if (!item) return false;
        if (item.status === 'ready') return true;
        if (item.status === 'ambiguous') return Boolean(message.selections?.[itemIdx]);
        return false;
    }

    function itemIcon(status: string, message: Message, itemIdx: number): string {
        if (status === 'ready' || isResolved(message, itemIdx)) return 'check_circle';
        if (status === 'not_found' || status === 'too_many') return 'cancel';
        return 'help';
    }

    function itemIconColor(status: string, message: Message, itemIdx: number): string {
        if (status === 'ready' || isResolved(message, itemIdx)) return 'positive';
        if (status === 'not_found' || status === 'too_many') return 'negative';
        return 'warning';
    }

    // ── Action-shape guards ──────────────────────────────────────────
    // PendingAction is now a discriminated union — these narrow into the
    // right shape so the templates and helpers can rely on the right fields.
    function isAddAction(action: PendingAction | undefined): action is AddToShoppingListAction {
        return action?.type === 'add_to_shopping_list';
    }
    function isConfirmAction(action: PendingAction | undefined): action is ConfirmAction {
        return action !== undefined && action.type !== 'add_to_shopping_list';
    }

    function selectCandidate(message: Message, itemIdx: number, stockItemId: string) {
        if (!message.selections) message.selections = {};
        message.selections[itemIdx] = stockItemId;
    }

    // Build the concrete (stock_item_id, quantity) list to commit: ready items
    // use their sole match; ambiguous items use the user's pick. Not-found and
    // too-many items are silently dropped.
    function commitItems(message: Message): CommitAddItem[] {
        const action = message.action;
        if (!isAddAction(action)) return [];
        const out: CommitAddItem[] = [];
        action.items.forEach((item, idx) => {
            if (item.status === 'ready' && item.candidates[0]) {
                out.push({ stock_item_id: item.candidates[0].stock_item_id, quantity: item.quantity });
            } else if (item.status === 'ambiguous') {
                const chosen = message.selections?.[idx];
                if (chosen) out.push({ stock_item_id: chosen, quantity: item.quantity });
            }
        });
        return out;
    }

    // Enabled only when there's a target list, something to add, and every
    // ambiguous item has been resolved (so we never commit a half-answered prompt).
    function canCommit(message: Message): boolean {
        const action = message.action;
        if (!isAddAction(action) || !action.shopping_list || message.done) return false;
        const everyAmbiguousResolved = action.items.every(
            (item, idx) => item.status !== 'ambiguous' || Boolean(message.selections?.[idx]),
        );
        return everyAmbiguousResolved && commitItems(message).length > 0;
    }

    async function commitAction(message: Message) {
        const action = message.action;
        if (!isAddAction(action) || !action.shopping_list || !canCommit(message)) return;
        const items = commitItems(message);
        message.done = true;
        thinking.value = true;
        await scrollToBottom();
        try {
            const result = await assistantApi.actAsync(action.shopping_list.id, items);
            pushDoraMessage({ text: result.answer, mood: 'happy' });
        } catch (err) {
            message.done = false;
            pushDoraMessage({
                text: `I couldn't update the list. ${describeApiError(err)}`,
                mood: 'sad',
            });
        } finally {
            thinking.value = false;
            await scrollToBottom();
        }
    }

    // ── Tier-2 confirm-style action handlers ─────────────────────────
    async function confirmAction(message: Message) {
        const action = message.action;
        if (!isConfirmAction(action) || action.status !== 'ready' || !action.payload) return;
        message.done = true;
        thinking.value = true;
        await scrollToBottom();
        try {
            const result = await assistantApi.confirmAsync(action.type, action.payload);
            pushDoraMessage({
                text: result.answer,
                mood: result.ok ? 'super_excited' : 'sad',
            });
        } catch (err) {
            message.done = false;
            pushDoraMessage({
                text: `Couldn't pull that off. ${describeApiError(err)}`,
                mood: 'sad',
            });
        } finally {
            thinking.value = false;
            await scrollToBottom();
        }
    }

    function cancelAction(message: Message) {
        message.done = true;
        pushDoraMessage({ text: 'No worries, cancelled that one.', mood: 'cute' });
    }

    // dispatch runs an intent and pushes Dora's reply. It does NOT push a
    // user message — callers do that themselves when appropriate. `rawText`
    // is the original user phrasing so intent handlers can extract targets
    // (e.g. "where is the cheese" → "cheese").
    async function dispatch(intent: DoraIntentId, rawText?: string) {
        // FU-429 — Basic mode's one action verb. Resolving pantry names +
        // performing the add needs the composables in this scope, so it's
        // handled here rather than in the pure runIntent handler.
        if (intent === 'add_to_list') {
            await onAddToListByText(rawText ?? '');
            return;
        }
        thinking.value = true;
        await scrollToBottom();
        try {
            // Small delay so the spinner registers visually even on instant
            // responses — keeps the "I'm thinking" affordance honest.
            const [reply] = await Promise.all([
                runIntent(intent, context(), rawText),
                new Promise((r) => setTimeout(r, 220)),
            ]);
            pushDoraMessage(reply);
        } catch (err) {
            pushDoraMessage({
                text: `Something went wrong while answering. ${describeApiError(err)}`,
                mood: 'sad',
            });
        } finally {
            thinking.value = false;
            await scrollToBottom();
        }
    }

    function onIntentClick(id: DoraIntentId) {
        emit('prompt-submitted');
        const label = labelFor(id);
        messages.value.push({ from: 'user', text: label });
        void scrollToBottom();
        void dispatch(id, label);
    }

    // ── Contextual action dispatcher (P14) ───────────────────────────
    // Each action kind routes through the appropriate composable so the
    // app stays consistent (same notifications, same data flow).
    async function onContextualAction(action: ContextualAction) {
        // Echo the user's intent into the chat so the log reads like a
        // conversation, not a series of unexplained side effects.
        messages.value.push({ from: 'user', text: action.label });
        await scrollToBottom();

        switch (action.kind) {
            case 'navigate': {
                pushDoraMessage({
                    text: `Heading to ${action.label.toLowerCase()}.`,
                    mood: 'happy',
                    navigateTo: { path: action.path, label: 'Take me there' },
                });
                if (action.query) {
                    void router.push({ path: action.path, query: action.query });
                } else {
                    void router.push(action.path);
                }
                emit('close');
                break;
            }
            case 'product_search': {
                // FU-186/FU-581 — opens the external Product Search companion
                // (new tab) or the Features setup page when no URL is set.
                pushDoraMessage({
                    text: 'Opening Product Search.',
                    mood: 'happy',
                });
                openProductSearch(router);
                emit('close');
                break;
            }
            case 'add_to_list': {
                pushDoraMessage({
                    text: 'On it, adding to your list.',
                    mood: 'excited',
                });
                await stockActions.addToList(action.stockItemId);
                break;
            }
            case 'quick_add': {
                pushDoraMessage({
                    text: 'Quick-add coming up.',
                    mood: 'happy',
                });
                openQuickAdd({ listId: action.listId ?? null });
                emit('close');
                break;
            }
            case 'whats_missing': {
                await onWhatsMissing(action.recipeId);
                break;
            }
            case 'add_missing': {
                await onAddMissingFromRecipe(action.recipeId);
                break;
            }
        }
    }

    // ── Recipe-aware helpers ─────────────────────────────────────────
    // Cookability is server-owned (§3.2): each ingredient carries `is_missing`.
    // We still load stock data here for the assistant's `getStock` context.
    async function ensureRecipeData() {
        // R-016 — every store guards its own re-entry, so call the helpers
        // unconditionally; the no-op short-circuit lives in the store.
        // recipeVocab covers dietary tags + cuisines, which the
        // chat handler resolves ids → names against for substring matching.
        await Promise.all([
            recipeStore.ensureLoadedAsync(),
            stockItemStore.ensureLoadedAsync(),
            stockLevelStore.ensureLoadedAsync(),
            recipeVocabStore.ensureLoadedAsync(),
            locationStore.ensureLoadedAsync(),
        ]);
    }

    function missingIdsForRecipe(recipeId: string): { id: string; name: string }[] {
        const recipe = recipes.value.find((r) => r.recipe_id === recipeId);
        if (!recipe) return [];
        const seen = new Set<string>();
        const missing: { id: string; name: string }[] = [];
        for (const ing of recipe.ingredients) {
            if (!ing.stock_item_id || seen.has(ing.stock_item_id) || !ing.is_missing) continue;
            seen.add(ing.stock_item_id);
            missing.push({ id: ing.stock_item_id, name: ing.stock_item_name ?? ing.raw_text ?? '' });
        }
        return missing;
    }

    async function onWhatsMissing(recipeId: string) {
        thinking.value = true;
        await scrollToBottom();
        try {
            await ensureRecipeData();
            const missing = missingIdsForRecipe(recipeId);
            const recipe = recipes.value.find((r) => r.recipe_id === recipeId);
            const name = recipe?.name ?? 'this recipe';
            if (missing.length === 0) {
                pushDoraMessage({
                    text: `Nothing's missing for ${name}. You can cook it right now.`,
                    mood: 'excited',
                });
            } else {
                const list = missing.map((m) => `• ${m.name}`).join('\n');
                pushDoraMessage({
                    text:
                        `${name} is missing ${missing.length} ingredient${
                            missing.length === 1 ? '' : 's'
                        }:\n\n${list}\n\nWant me to drop them on your primary list?`,
                    mood: 'searching',
                });
            }
        } finally {
            thinking.value = false;
            await scrollToBottom();
        }
    }

    async function onAddMissingFromRecipe(recipeId: string) {
        thinking.value = true;
        await scrollToBottom();
        try {
            await ensureRecipeData();
            const missing = missingIdsForRecipe(recipeId);
            const recipe = recipes.value.find((r) => r.recipe_id === recipeId);
            const name = recipe?.name ?? 'this recipe';
            if (missing.length === 0) {
                pushDoraMessage({
                    text: `Nothing missing for ${name}.`,
                    mood: 'happy',
                });
                return;
            }
            const primary = shoppingListStore.quickAddTargetListId;
            if (!primary) {
                pushDoraMessage({
                    text:
                        `You don't have a primary shopping list set yet. Set one and I'll add the ${missing.length} missing ingredient${
                            missing.length === 1 ? '' : 's'
                        } in a second.`,
                    mood: 'sad',
                    navigateTo: { path: '/shopping-lists', label: 'Open shopping lists' },
                });
                return;
            }
            await addItems(
                primary,
                missing.map((m) => ({ stock_item_id: m.id })),
            );
            pushDoraMessage({
                text: `Done. Added ${missing.length} missing ingredient${
                    missing.length === 1 ? '' : 's'
                } from ${name} to your list.`,
                mood: 'excited',
            });
        } finally {
            thinking.value = false;
            await scrollToBottom();
        }
    }

    // FU-429 — add-to-list by typed text, Basic mode's one action verb.
    // Parses the item name(s) (pure, in doraIntents), resolves each against
    // the pantry, and adds the unambiguous matches via the same composable
    // the contextual "Add to list" chip uses — so notifications stay
    // consistent. Ambiguous / not-found terms are surfaced, never guessed.
    function oxfordJoin(names: string[]): string {
        if (names.length <= 1) return names[0] ?? '';
        if (names.length === 2) return `${names[0]} and ${names[1]}`;
        return `${names.slice(0, -1).join(', ')}, and ${names[names.length - 1]}`;
    }

    async function onAddToListByText(text: string) {
        thinking.value = true;
        await scrollToBottom();
        try {
            await Promise.all([
                stockItemStore.ensureLoadedAsync(),
                shoppingListStore.ensureLoadedAsync(),
            ]);
            const queries = extractAddToListItems(text);
            if (queries.length === 0) {
                pushDoraMessage({
                    text: "Sure, what should I add? Try \"add milk\" or \"add eggs and bread\".",
                    mood: 'searching',
                });
                return;
            }
            const primary = shoppingListStore.quickAddTargetListId;
            if (!primary) {
                pushDoraMessage({
                    text: "I add to your draft list, and that only works when you have exactly one.",
                    mood: 'sad',
                    navigateTo: { path: '/shopping-lists', label: 'Open shopping lists' },
                });
                return;
            }
            const items = stockItems.value;
            const matched: { id: string; name: string }[] = [];
            const ambiguous: string[] = [];
            const notFound: string[] = [];
            for (const q of queries) {
                const ql = q.toLowerCase();
                const exact = items.filter((i) => i.name.toLowerCase() === ql);
                const hits = exact.length
                    ? exact
                    : items.filter((i) => i.name.toLowerCase().includes(ql));
                if (hits.length === 1) matched.push({ id: hits[0]!.stock_item_id, name: hits[0]!.name });
                else if (hits.length > 1) ambiguous.push(q);
                else notFound.push(q);
            }
            if (matched.length > 0) {
                await addItems(primary, matched.map((m) => ({ stock_item_id: m.id })));
            }
            const parts: string[] = [];
            if (matched.length) {
                parts.push(`Added ${oxfordJoin(matched.map((m) => m.name))} to your list. 🛒`);
            }
            if (ambiguous.length) {
                parts.push(
                    `"${ambiguous.join('", "')}" matched more than one pantry item, so I didn't want to guess. Add the exact one from Stock.`,
                );
            }
            if (notFound.length) {
                const it = notFound.length === 1 ? 'it' : 'them';
                parts.push(
                    `I couldn't find ${oxfordJoin(notFound)} among your pantry items. Add ${it} on the Stock page first and I'll be able to list ${it}.`,
                );
            }
            pushDoraMessage({
                text: parts.join('\n\n'),
                mood: matched.length ? 'excited' : (ambiguous.length ? 'searching' : 'sad'),
                ...(matched.length
                    ? { navigateTo: { path: '/shopping-lists', label: 'Open shopping lists' } }
                    : {}),
            });
        } catch (err) {
            pushDoraMessage({
                text: `I couldn't update the list. ${describeApiError(err)}`,
                mood: 'sad',
            });
        } finally {
            thinking.value = false;
            await scrollToBottom();
        }
    }

    // Free-form text goes to the SLM assistant first. The backend tells us
    // when it can't help — model unreachable (`available: false`) or the
    // message wasn't a data question (`defer_to_local: true`) — and in both
    // cases we fall back to the local rule-based intents so the assistant
    // keeps working with or without a model running.
    async function onSubmit() {
        const text = draft.value.trim();
        if (!text) return;
        draft.value = '';
        await submitPromptText(text);
    }

    // Shared submission path used by both the text input and the AI-mode
    // suggestion chips. Pushes the user text, runs AI when active, and falls
    // back to the rule engine when AI defers or is unavailable.
    async function submitPromptText(text: string) {
        const trimmed = text.trim();
        if (!trimmed) return;
        emit('prompt-submitted');
        messages.value.push({ from: 'user', text: trimmed });
        await scrollToBottom();
        const preempt = detectIntent(trimmed);
        if (preempt === 'compliment' || preempt === 'insult' || preempt === 'report_issue') {
            await dispatch(preempt, trimmed);
            return;
        }
        thinking.value = true;
        await scrollToBottom();
        try {
            const reply = await assistantApi.askAsync(trimmed, route.path);
            if (reply.available && !reply.defer_to_local && reply.answer) {
                const mood = (reply.mood as DoraMood) ?? 'happy';
                const message: Message = {
                    from: 'dora',
                    text: reply.answer,
                    displayText: '',
                    mood,
                    ...(reply.navigate_to ? { navigateTo: reply.navigate_to } : {}),
                    ...(reply.pending_action
                        ? { action: reply.pending_action, selections: {} }
                        : {}),
                };
                messages.value.push(message);
                emit('mood', mood);
                startTypewriter(messages.value[messages.value.length - 1]!);
                await scrollToBottom();
                return;
            }
        } catch (err) {
            console.debug('Assistant backend unavailable, using local intents', err);
            void refreshAiStatus();
        } finally {
            thinking.value = false;
            await scrollToBottom();
        }
        const intent = detectIntent(trimmed);
        await dispatch(intent, trimmed);
    }

    function onNavigate(path: string) {
        void router.push(path);
        emit('close');
    }

    onMounted(() => {
        void dispatch('greet');
        // Show the AI/Basic badge from the start, before the first message.
        void refreshAiStatus();
    });

    onBeforeUnmount(() => {
        // Make sure the talking-state event doesn't get stranded if the
        // chat is closed while a reveal is in flight.
        if (activeTypewriter) activeTypewriter.cancel();
    });

    // Re-summarise the page when the user navigates while the chat is open
    // so the header hint stays accurate. We don't auto-post a new message
    // (that would be noisy) — just update the header.
    watch(
        () => route.path,
        () => {
            void scrollToBottom();
        }
    );
</script>

<style scoped>
    .dora-chat-card {
        /* The card is a flex column. The messages region uses flex: 1 so
           it grows to fill whatever room is left after the (fixed-height)
           header and input footer, then scrolls internally. Without this,
           a long thread pushes the footer off-screen because the
           combined fixed sizes exceed the viewport. */
        /* dvh, not vh — the launcher shell this card sits in is sized off the
           dynamic viewport, so measuring the card against the *large*
           viewport would let it outgrow its container while a mobile URL bar
           is showing. vh first as the fallback for engines without dvh. */
        max-height: 70vh;
        height: 70vh;
        max-height: 70dvh;
        height: 70dvh;
        background: var(--surface-component);
    }
    .dora-chat-header {
        background: linear-gradient(
            120deg,
            color-mix(in srgb, var(--brand-primary) 8%, transparent),
            color-mix(in srgb, var(--brand-accent) 8%, transparent)
        );
    }
    /* QScrollArea is the flex child that fills the column and owns the
       overflow; min-height: 0 lets it shrink so the footer stays visible. */
    .dora-chat-scroll {
        min-height: 0;
    }
    .dora-chat-messages {
        padding: 12px;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    .dora-chat-message {
        display: flex;
    }
    .dora-chat-message-user {
        justify-content: flex-end;
    }
    /* Dora's bubble — slightly darker than the card so the edge reads. The
       primary green at low alpha picks up the brand instead of looking like
       grey wash. Dark mode mirrors with the same tint over the dark card. */
    .dora-chat-bubble {
        max-width: 80%;
        padding: 8px 12px;
        border-radius: 12px;
        background: color-mix(in srgb, var(--brand-primary) 12%, transparent);
        font-size: 0.92em;
        line-height: 1.35;
    }
    .dora-chat-message-user .dora-chat-bubble {
        background: var(--q-primary);
        color: var(--text-on-primary);
    }
    .dora-chat-message-user .dora-chat-bubble .dora-chat-text {
        color: var(--text-on-primary);
    }
    .dora-chat-thinking {
        background: color-mix(in srgb, var(--brand-primary) 8%, transparent);
    }
    .dora-chat-text {
        white-space: pre-wrap;
    }
    .dora-help-btn {
        opacity: 0.6;
        transition: opacity 160ms ease;
    }
    .dora-help-btn:hover {
        opacity: 1;
    }
    /* Bot name + accent-style buttons. The brand accent is gorgeous on
       dark backdrops but vanishes against light cards — that used to be
       handled here with a `.body--dark` fork that dropped the accent
       entirely in light themes. --accent-ink is that idea as a token
       (tokens.scss): the accent hue, held to D-002's 4.5:1 floor on every
       surface, so one declaration covers both modes and the light themes
       keep the accent identity instead of falling back to plain ink. */
    .dora-bot-name {
        font-weight: 700;
        color: var(--accent-ink);
    }
    .dora-accent-btn {
        color: var(--accent-ink);
    }
    /* Inline blinking caret shown only while a dora message is mid-reveal.
       Visual hint that more text is coming, paired with the talking face. */
    .dora-chat-caret {
        display: inline-block;
        margin-left: 1px;
        color: var(--q-primary);
        animation: dora-caret-blink 900ms steps(1) infinite;
    }
    @keyframes dora-caret-blink {
        50% { opacity: 0; }
    }
    @media (prefers-reduced-motion: reduce) {
        .dora-chat-caret { animation: none; }
    }
    .dora-action-card {
        border-top: 1px solid var(--overlay-active);
        padding-top: 8px;
    }
    .dora-action-item + .dora-action-item {
        margin-top: 6px;
    }
    /* P2-13 — mic button pulses while listening so the user has a
       constant indicator that the page is actively capturing audio. */
    .dora-mic-listening {
        animation: dora-mic-pulse 1.2s ease-in-out infinite;
    }
    @keyframes dora-mic-pulse {
        0%, 100% { transform: scale(1); }
        50%      { transform: scale(1.12); }
    }

    /* P2-04 — suggestion panel that prepends the chat scroll area. */
    .dora-suggestion-panel {
        padding: 8px 4px 12px;
        border-bottom: 1px dashed var(--overlay-active);
        margin-bottom: 8px;
    }
    /* P14: contextual "on this page" chip row — a slightly warmer band so
       the eye picks the page-specific actions out of the generic ones. */
    .dora-context-row {
        padding: 8px 10px;
        background: linear-gradient(
            120deg,
            color-mix(in srgb, var(--brand-primary) 6%, transparent),
            color-mix(in srgb, var(--brand-accent) 6%, transparent)
        );
        border-radius: 10px;
    }
</style>
