<template>
    <div class="dora-bubble-root" :class="{ 'dora-bubble-open': open }">
        <transition name="dora-bubble-pop">
            <DoraChat
                v-if="open"
                :current-user="currentUser"
                @close="onClose"
                @prompt-submitted="wake"
                @mood="onConversationMood"
                @thinking="onConversationThinking"
                @talking="onConversationTalking"
                @ai-offline="onAiOffline"
            />
        </transition>

        <transition name="dora-bubble-hint">
            <div v-if="showFirstTimeHint && !open" class="dora-bubble-hint">
                <div class="dora-bubble-hint-arrow"></div>
                <div class="dora-bubble-hint-text">
                    <strong>Hi! I'm Dora.</strong>
                    Click me whenever you're lost or want a tip.
                </div>
                <BaseButton
                    aria-label="Dismiss tip"
                    variant="icon"
                    size="sm"
                    :icon="ICONS.close"
                    @click.stop="dismissHint"
                />
            </div>
        </transition>

        <button
            class="dora-bubble-launcher"
            :class="{
                'is-active': open,
                'is-attention': updateBadge && !open,
                'is-sleeping': connection === 'sleeping' && !open,
                'is-wiggling': wiggling,
                'is-hint-visible': showFirstTimeHint && !open,
            }"
            :aria-label="open ? 'Close Dora' : 'Open Dora help assistant'"
            @click="onLauncherClick"
        >
            <div
                class="dora-bubble-launcher-inner"
                :class="{ 'is-entering': !hasEntered }"
            >
                <DoraMascot
                    :mood="displayMood"
                    :state="mascotState"
                    :connection="connection"
                    :size="80"
                />
                <q-badge
                    v-if="updateBadge"
                    floating
                    color="accent"
                    text-color="dark"
                    rounded
                    class="dora-update-badge"
                >
                    NEW
                    <BaseTooltip>A newer version of Dashy Dora is available.</BaseTooltip>
                </q-badge>
                <!-- suggestion count badge. Skipped while the
                     NEW (update) badge is showing so they don't stack. -->
                <q-badge
                    v-if="!updateBadge && suggestionCount > 0 && !open"
                    floating
                    :color="suggestionHighCount > 0 ? 'negative' : 'primary'"
                    rounded
                    class="dora-suggestion-badge"
                >
                    {{ suggestionCount > 9 ? '9+' : suggestionCount }}
                    <BaseTooltip>
                        Dora has {{ suggestionCount }} suggestion{{
                            suggestionCount === 1 ? '' : 's'
                        }} for you.
                    </BaseTooltip>
                </q-badge>
            </div>
        </button>
    </div>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import { storeToRefs } from 'pinia';
    import BaseButton from 'src/components/BaseButton.vue';
    import DoraChat from 'src/components/dora/DoraChat.vue';
    import DoraMascot from 'src/components/dora/DoraMascot.vue';
    import {
        MOODS_WITH_TALKING_VARIANT,
        type DoraConnection,
        type DoraMood,
        type DoraState,
    } from 'src/components/dora/doraTypes';
    import HelpApiService from 'src/services/api/helpApiService';
    import { useAuthStore } from 'src/stores/authStore';
    import { useSuggestionStore } from 'src/stores/suggestionStore';
    import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

    const authStore = useAuthStore();
    const { currentUser } = storeToRefs(authStore);

    // FU-360.5 — the first-time "Hi! I'm Dora" hint shows once *per user*,
    // not once per browser. The household model shares one browser across
    // people, so a browser-wide key meant only the first person ever saw it
    // (or a returning user kept seeing it after another cleared it). Keying by
    // user id gives each account exactly one acknowledge. Falls back to a
    // shared key while the user id isn't known yet (pre-hydration).
    const hintDismissedKey = () => {
        const id = currentUser.value?.user_id;
        return id ? `dora.helpHintDismissed.${id}` : 'dora.helpHintDismissed';
    };

    function hintAlreadyDismissed(): boolean {
        try {
            return localStorage.getItem(hintDismissedKey()) !== null;
        } catch {
            // Storage disabled (private mode) — treat as "never dismissed" so
            // the nudge still does its job.
            return false;
        }
    }
    const helpApi = new HelpApiService();
    // suggestion count drives the badge on the launcher and
    // gives DoraChat the data when it opens. Refreshed on mount and
    // when the chat closes (cheap; the endpoint is read-only).
    const suggestionStore = useSuggestionStore();
    const { count: suggestionCount, highCount: suggestionHighCount } = storeToRefs(suggestionStore);

    // How long without interaction before Dora's eyes droop shut. Short
    // enough to read as "she's napping" but long enough not to nod off
    // mid-task. Sleep persists across opening the chat panel — only sending
    // a prompt or closing the chat counts as waking her up.
    const SLEEP_AFTER_MS = 60 * 1000;

    const open = ref(false);
    const updateBadge = ref(false);
    const showFirstTimeHint = ref(false);
    let sleepTimer: ReturnType<typeof setTimeout> | null = null;

    // ── Connection composition ─────────────────────────────────────────
    // Two independent signals: the sleep timer turns `isSleeping` on after
    // a stretch of inactivity, and the chat panel tells us when AI was
    // working and has now dropped. Offline wins over sleeping — if the
    // model's gone down we want that visible regardless of the timer.
    const isSleeping = ref(false);
    const isAiOffline = ref(false);
    const connection = computed<DoraConnection>(() => {
        if (isAiOffline.value) return 'offline';
        if (isSleeping.value) return 'sleeping';
        return 'online';
    });

    // ── Face-state composition ─────────────────────────────────────────
    // Each input is independent (chat emits drive them) and `displayMood` /
    // `mascotState` are derived. Priority, top to bottom:
    //   thinking         → thinking face
    //   talking          → happy face + lip-flap (the talking artwork only
    //                      matches the happy/ready face)
    //   replyMood held   → whatever Dora just said
    //   otherwise        → resting (happy, or excited when an update's available)
    const replyMood = ref<DoraMood | null>(null);
    const thinking = ref(false);
    const talking = ref(false);

    function restingMood(): DoraMood {
        return updateBadge.value ? 'excited' : 'happy';
    }

    const displayMood = computed<DoraMood>(() => {
        if (thinking.value) return 'thinking';
        const mood = replyMood.value ?? restingMood();
        // While talking: if the mood has its own talking-overlay artwork
        // (happy / confused / sad), keep the mood — the mascot will play the
        // matching lip-flap. Otherwise fall back to happy so the generic
        // ready-face lip-flap still animates (the alternative is a frozen
        // mood face throughout the reply, which reads as broken).
        if (talking.value && !MOODS_WITH_TALKING_VARIANT.has(mood)) return 'happy';
        return mood;
    });

    const mascotState = computed<DoraState>(() =>
        talking.value && !thinking.value ? 'talking' : 'idle',
    );

    function armSleepTimer() {
        if (sleepTimer !== null) clearTimeout(sleepTimer);
        sleepTimer = setTimeout(() => {
            isSleeping.value = true;
        }, SLEEP_AFTER_MS);
    }

    function wake() {
        isSleeping.value = false;
        armSleepTimer();
    }

    function onAiOffline(offline: boolean) {
        isAiOffline.value = offline;
    }

    // DR-7 (FU-578 #6/#31) — the first-time hint used to sit over page content
    // until clicked. Auto-hide it after a read-length beat so it stops
    // lingering. Auto-hide is *transient* (no persist) — clicking the X
    // (dismissHint) is the permanent acknowledge; an ignored hint may resurface
    // next session, which is fine for a discoverability nudge.
    const HINT_AUTO_HIDE_MS = 9000;
    let hintAutoHideTimer: ReturnType<typeof setTimeout> | null = null;
    function clearHintAutoHide() {
        if (hintAutoHideTimer !== null) {
            clearTimeout(hintAutoHideTimer);
            hintAutoHideTimer = null;
        }
    }
    function armHintAutoHide() {
        clearHintAutoHide();
        hintAutoHideTimer = setTimeout(() => {
            showFirstTimeHint.value = false;
        }, HINT_AUTO_HIDE_MS);
    }

    function dismissHint() {
        showFirstTimeHint.value = false;
        hintChecked = true;
        clearHintAutoHide();
        try {
            localStorage.setItem(hintDismissedKey(), '1');
        } catch {
            // Storage can be disabled (private mode). Not a problem — we'll
            // just show the hint again next session, which is fine for a
            // helper that's trying to be discoverable.
        }
    }

    // The hint is a once-per-user acknowledge held in localStorage, so the
    // decision can't be made until the user id has hydrated — checking (and
    // later writing) the pre-hydration fallback key would resurface the hint
    // for someone who had already dismissed it. Runs at most once per mount.
    let hintChecked = false;
    let hintShowTimer: ReturnType<typeof setTimeout> | null = null;

    function considerFirstTimeHint() {
        if (hintChecked || !currentUser.value?.user_id) return;
        hintChecked = true;
        if (hintAlreadyDismissed()) return;
        // Tiny delay so the hint doesn't fight with the initial page-load
        // animation.
        hintShowTimer = setTimeout(() => {
            hintShowTimer = null;
            if (!open.value) {
                showFirstTimeHint.value = true;
                armHintAutoHide();
            }
        }, 1500);
    }

    watch(() => currentUser.value?.user_id, considerFirstTimeHint, { immediate: true });

    // Brief "wiggle" class added on click so the launcher gives tactile
    // feedback before the chat panel slides in.
    const wiggling = ref(false);

    function toggle() {
        open.value = !open.value;
        if (open.value) {
            dismissHint();
        } else {
            // Closing the chat is treated as a deliberate interaction — wake
            // up so the next interaction starts fresh.
            wake();
        }
    }

    function onLauncherClick() {
        wiggling.value = true;
        setTimeout(() => (wiggling.value = false), 380);
        toggle();
    }

    // FU-360.4 — one-shot entrance animation. Held on a `.is-entering`
    // modifier class rather than the base CSS rule so hover-off doesn't
    // reapply the base declaration and retrigger the animation (which
    // used to flash Dora out and back in). Vue scopes @keyframes names in
    // <style scoped>, so an animationend event listener would need the
    // scoped name — a plain timeout matching entrance-delay + duration is
    // simpler and just as reliable.
    const hasEntered = ref(false);
    const ENTRANCE_TOTAL_MS = 1500;

    function onClose() {
        open.value = false;
        // Re-fetch suggestions after closing — the user may have just
        // dismissed/snoozed/accepted from inside the chat, and the
        // dashboard card + launcher badge should reflect that.
        void suggestionStore.refreshAsync();
    }

    // ── Conversation-driven reactions ──────────────────────────────────
    // The chat panel tells the launcher what the reply mood is, whether
    // a round-trip is in flight, and whether text is currently streaming.
    // The reply mood is held for a beat past the talking animation so the
    // expression (super_excited, sad, etc.) actually registers before
    // relaxing back to resting.
    const HOLD_MOOD_MS = 4000;
    let moodHoldTimer: ReturnType<typeof setTimeout> | null = null;

    function scheduleMoodRelax() {
        if (moodHoldTimer !== null) clearTimeout(moodHoldTimer);
        moodHoldTimer = setTimeout(() => {
            replyMood.value = null;
            moodHoldTimer = null;
        }, HOLD_MOOD_MS);
    }

    function onConversationMood(mood: DoraMood) {
        if (moodHoldTimer !== null) clearTimeout(moodHoldTimer);
        replyMood.value = mood;
        // If we're still talking, the hold timer should start after talking
        // ends — otherwise start it now.
        if (!talking.value) scheduleMoodRelax();
        wake();
    }

    function onConversationThinking(active: boolean) {
        thinking.value = active;
    }

    function onConversationTalking(active: boolean) {
        talking.value = active;
        // When talking stops, kick off the relax timer so the just-revealed
        // expression lingers HOLD_MOOD_MS before settling back to resting.
        if (!active) scheduleMoodRelax();
    }

    onMounted(async () => {
        // Peel off .is-entering once the one-shot entrance is done. Anything
        // sooner leaves the class on, and hover-off would resurrect the
        // entrance animation.
        setTimeout(() => {
            hasEntered.value = true;
        }, ENTRANCE_TOTAL_MS);

        // The first-time hint is handled by the `currentUser` watcher above —
        // it needs the user id, which may land after mount.

        // Probe the version endpoint so the launcher can show a NEW badge
        // when there's an update. Failures are silent — the badge just
        // doesn't appear.
        try {
            const info = await helpApi.getVersionAsync();
            updateBadge.value = info.update_available;
        } catch {
            // Don't bug the user — the bubble still works without this.
        }

        // First suggestion-count fetch. The store swallows endpoint
        // errors so older backends just keep the badge hidden.
        void suggestionStore.refreshAsync();
    });

    // Closing the chat clears any held reply mood so the launcher resets to
    // its resting expression rather than freezing on whatever Dora last said.
    watch(open, (isOpen) => {
        if (!isOpen) {
            if (moodHoldTimer !== null) {
                clearTimeout(moodHoldTimer);
                moodHoldTimer = null;
            }
            replyMood.value = null;
            thinking.value = false;
            talking.value = false;
        }
    });

    onMounted(armSleepTimer);
    onBeforeUnmount(() => {
        if (sleepTimer !== null) clearTimeout(sleepTimer);
        if (hintShowTimer !== null) clearTimeout(hintShowTimer);
        clearHintAutoHide();
    });
</script>

<style scoped>
    /* Anchored to the *dynamic* viewport rather than to `bottom` on a fixed
       box. Mobile browsers disagree about what `position: fixed; bottom: N`
       means while the URL bar is collapsing — Firefox Android in particular
       shifted the launcher up when the address bar was showing and back down
       when it hid. A full-height `100dvh` shell pinned at the top, with the
       contents pushed to its bottom edge, tracks the visible viewport the
       same way in every engine. The shell is click-through so it doesn't
       swallow taps on the page behind it. */
    .dora-bubble-root {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 100vh; /* fallback for engines without dvh */
        height: 100dvh;
        /* DR-7 (FU-578 #6) — respect the mobile safe area so the launcher
           doesn't tuck under a home indicator / rounded corner. */
        padding-right: max(18px, env(safe-area-inset-right, 0px));
        padding-bottom: max(18px, env(safe-area-inset-bottom, 0px));
        z-index: 3000;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
        align-items: flex-end;
        gap: 12px;
        pointer-events: none;
    }
    .dora-bubble-root > * {
        pointer-events: auto;
    }
    /* Launcher behaviour
       ──────────────────
       Idle  : shrunk + semi-transparent so it doesn't crowd the page.
       Hover : full size + full opacity + a slow floating bob.
       Active: full size + full opacity (chat panel is open).
       Sleep : extra-faded so the napping frame reads as "off duty".
       Attention (update available, idle): gentle opacity pulse so the NEW
       badge still draws the eye even when the launcher is faded out. */
    .dora-bubble-launcher {
        appearance: none;
        background: transparent;
        border: none;
        padding: 0;
        cursor: pointer;
        position: relative;
        opacity: 0.55;
        transform: scale(0.55);
        transform-origin: bottom right;
        transition:
            transform 240ms cubic-bezier(0.22, 1, 0.36, 1),
            opacity 240ms ease;
    }
    /* Hover: full opacity + full size. Active (chat open): pop a bit beyond
       full so it reads as the focused element while the panel is up. The
       first-time hint bubble pegs us at the hover state so the speech
       balloon doesn't appear to float over an invisible launcher.

       The :hover halves are gated behind a real pointer. On touch, a tap
       leaves :hover latched on the launcher until you tap elsewhere, so
       closing the panel *by tapping the mascot* left it stuck at full size
       while closing via the panel's X correctly shrank it — the same action
       with two different results. Touch devices get the idle/active states
       only, which is the honest set for them. */
    @media (hover: hover) and (pointer: fine) {
        .dora-bubble-launcher:hover {
            opacity: 1;
            transform: scale(1);
        }
        .dora-bubble-launcher.is-sleeping:hover {
            opacity: 1;
        }
        .dora-bubble-launcher:hover .dora-bubble-launcher-inner {
            animation: dora-hover-bob 1.6s ease-in-out infinite;
        }
    }
    .dora-bubble-launcher:focus-visible,
    .dora-bubble-launcher.is-hint-visible {
        opacity: 1;
        transform: scale(1);
    }
    /* Keyboard focus gets a real ring (D-016): the opacity/scale above is the
       hover state, so on its own it couldn't tell focus from a pointer. */
    .dora-bubble-launcher:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: 3px;
    }
    .dora-bubble-launcher.is-active {
        opacity: 1;
        transform: scale(1.12);
    }
    .dora-bubble-launcher.is-sleeping {
        opacity: 0.35;
    }
    .dora-bubble-launcher.is-sleeping:focus-visible {
        opacity: 1;
    }
    .dora-bubble-launcher.is-attention:not(:hover):not(.is-active) {
        animation: dora-attention-pulse 2.4s ease-in-out infinite;
    }

    /* Inner wrapper holds the per-state float/wiggle animations and the
       active-only circle background. Animations live here so they compose
       with the launcher's scale transform without fighting it. */
    .dora-bubble-launcher-inner {
        position: relative;
        display: inline-block;
        transform-origin: center bottom;
        will-change: transform;
    }
    /* One-time entrance: Dora pops in with a small spring overshoot the
       first time the launcher mounts (login / app load). Held on a modifier
       class rather than the base rule so that when a hover-bob / wiggle
       animation ends and the base declaration reasserts, the entrance
       doesn't retrigger — the FU-360.4 hover-flash bug. Removed via
       @animationend once the entrance has played. */
    .dora-bubble-launcher-inner.is-entering {
        animation: dora-entrance var(--motion-slow) var(--motion-ease-spring) 300ms both;
    }
    /* Translucent disc behind the mascot — only shown when the chat is open,
       so Dora reads clearly against any page colour while she's the active
       control. Sized off the mascot's bounding box via inset rather than a
       fixed px so it scales with the chosen :size. */
    .dora-bubble-launcher-inner::before {
        content: '';
        position: absolute;
        /* Slight positive inset — disc hugs the mascot's silhouette, just
           barely visible at the edges. Not a halo, just a backdrop. */
        inset: 4%;
        border-radius: 50%;
        /* Theme-aware backdrop disc. Light themes paint a warm-paper halo;
           dark themes paint a brand-primary halo. Both ride
           `--dora-disc-bg` (set per theme in themes.scss). */
        background: radial-gradient(
            circle at 50% 45%,
            color-mix(in srgb, var(--dora-disc-bg) 97%, transparent),
            color-mix(in srgb, var(--dora-disc-bg) 75%, transparent) 65%,
            transparent 100%
        );
        box-shadow: 0 6px 22px var(--dora-halo);
        opacity: 0;
        transform: scale(0.6);
        transition:
            opacity 220ms ease,
            transform 220ms cubic-bezier(0.22, 1, 0.36, 1);
        z-index: 0;
        pointer-events: none;
    }
    .dora-bubble-launcher.is-active .dora-bubble-launcher-inner::before {
        opacity: 1;
        transform: scale(1);
    }
    /* Mascot sits above the disc. The badge is excluded so Quasar's
       `floating` absolute-positioning keeps working — otherwise the
       generic `position: relative` here puts it back into flow and
       shoves the mascot sideways. */
    .dora-bubble-launcher-inner > :not(.dora-update-badge):not(.dora-suggestion-badge) {
        position: relative;
        z-index: 1;
    }
    .dora-update-badge {
        /* Stay pinned to the top-right of the mascot bounding box and
           sit above the disc backdrop. */
        position: absolute;
        top: 2px;
        right: 2px;
        z-index: 2;
    }
    /* P2-04 — same corner as the NEW badge but only one of them can be
       shown at a time (NEW wins), so the rule above hides this until
       updateBadge is false. */
    .dora-suggestion-badge {
        position: absolute;
        top: 2px;
        right: 2px;
        z-index: 2;
        font-weight: 700;
        min-width: 22px;
        padding: 0 6px;
    }
    .dora-bubble-launcher.is-wiggling .dora-bubble-launcher-inner {
        animation: dora-wiggle 380ms ease-in-out;
    }

    @keyframes dora-hover-bob {
        0%, 100% { transform: translateY(0) rotate(0deg); }
        50%      { transform: translateY(-6px) rotate(-1.5deg); }
    }
    @keyframes dora-wiggle {
        0%   { transform: rotate(0deg); }
        25%  { transform: rotate(-6deg); }
        50%  { transform: rotate(5deg); }
        75%  { transform: rotate(-3deg); }
        100% { transform: rotate(0deg); }
    }
    @keyframes dora-attention-pulse {
        0%, 100% { opacity: 0.55; }
        50%      { opacity: 0.95; }
    }
    @keyframes dora-entrance {
        0%   { transform: scale(0) translateY(16px); opacity: 0; }
        100% { transform: scale(1) translateY(0);    opacity: 1; }
    }
    @media (prefers-reduced-motion: reduce) {
        .dora-bubble-launcher,
        .dora-bubble-launcher-inner {
            animation: none !important;
            transition: opacity 240ms ease;
        }
        .dora-bubble-launcher {
            transform: scale(0.75);
        }
        .dora-bubble-launcher:hover,
        .dora-bubble-launcher:focus-visible,
        .dora-bubble-launcher.is-active {
            transform: scale(1);
        }
    }
    .dora-update-badge {
        font-weight: 700;
        letter-spacing: 0.05em;
        font-size: 0.65rem;
    }
    .dora-bubble-hint {
        background: var(--surface-component);
        color: var(--text-primary);
        /* Thin outline so the bubble stays legible against busy page content
           behind it — the shadow alone wasn't enough separation. */
        border: 1px solid var(--border-strong);
        padding: 10px 14px;
        border-radius: 12px;
        max-width: 260px;
        box-shadow: 0 6px 22px var(--overlay-dim);
        position: relative;
        font-size: 0.85em;
        display: flex;
        gap: 8px;
        align-items: flex-start;
    }
    .dora-bubble-hint-text {
        flex: 1;
    }
    /* Rotated square rather than a border-triangle so the tail can carry the
       same 1px outline as the bubble; its top half sits over the bubble body
       and hides the bubble's own bottom border. */
    .dora-bubble-hint-arrow {
        position: absolute;
        right: 24px;
        bottom: -7px;
        width: 12px;
        height: 12px;
        background: var(--surface-component);
        border-right: 1px solid var(--border-strong);
        border-bottom: 1px solid var(--border-strong);
        border-bottom-right-radius: 2px;
        transform: rotate(45deg);
    }
    .dora-bubble-pop-enter-active,
    .dora-bubble-pop-leave-active {
        transition: opacity 180ms ease, transform 180ms ease;
        transform-origin: bottom right;
    }
    .dora-bubble-pop-enter-from,
    .dora-bubble-pop-leave-to {
        opacity: 0;
        transform: scale(0.92) translateY(8px);
    }
    .dora-bubble-hint-enter-active,
    .dora-bubble-hint-leave-active {
        transition: opacity 240ms ease, transform 240ms ease;
    }
    .dora-bubble-hint-enter-from,
    .dora-bubble-hint-leave-to {
        opacity: 0;
        transform: translateY(6px);
    }
</style>
