<template>
    <!-- Splash is the only surface that sits over the whole viewport
         with a high z-index (App.vue mounts it above the router-view
         while the auth store bootstraps). AuthShell owns the midnight
         canvas + blob backdrop; the overlay concern is splash-only. -->
    <div class="splash-overlay">
        <AuthShell
            backdrop="quiet"
            mascot="none"
            variant="full-bleed"
            role="status"
            :aria-busy="!error"
            :donate="false"
        >
            <div class="splash-inner">
                <div class="splash-logo-wrap">
                    <img
                        :src="error ? offlineSrc : logoSrc"
                        alt="Dashy Dora"
                        class="splash-logo"
                        :class="{ 'splash-logo--pulse': !error }"
                        draggable="false"
                    />
                </div>

                <div class="splash-text">
                    <p v-if="error" class="splash-error-headline">
                        Can't reach Dora's brain
                    </p>
                    <p v-if="error" class="splash-error-detail">{{ error }}</p>
                    <p
                        v-else
                        class="splash-loading-message"
                        :key="loadingMessage"
                    >
                        {{ loadingMessage }}
                    </p>
                </div>

                <AuthButton
                    v-if="error"
                    colour="primary"
                    label="Try again"
                    class="splash-retry"
                    @click="emit('retry')"
                />
                <!-- FU-574 — when a runtime backend override is set (native
                     always, or a browser/PWA user who saved an instance URL
                     from Settings), a bogus URL renders this same error screen
                     and #/settings/about is unreachable too — so surface the
                     recovery here instead of forcing a localStorage hand-clear. -->
                <AuthButton
                    v-if="error && showChangeUrl"
                    colour="ghost"
                    label="Change instance URL"
                    class="splash-change-url"
                    @click="onChangeInstance"
                />
            </div>
        </AuthShell>
    </div>
</template>

<script setup lang="ts">
    import AuthShell from 'src/components/AuthShell.vue';
    import { promptAndSaveInstanceUrl } from 'src/composables/useChangeInstance';
    import AuthButton from 'src/components/AuthButton.vue';
    import logoSrc from 'src/assets/logo-mascot.png';
    import offlineSrc from 'src/assets/dora/dorabot-fatal-error-or-offline.png';
    import { onBeforeUnmount, ref, watch } from 'vue';
    import { backendBaseUrlIsUserSet } from 'src/services/api/backendUrl';

    const props = defineProps<{ error: string | null }>();
    const emit = defineEmits<{ retry: [] }>();


    // FU-574 — only offer the change-URL recovery when a runtime override is
    // actually in play (native always; a browser/PWA user who saved one). A
    // plain web install on its env default has no URL to change, so retry is
    // the only honest action there. Read once at construction: the boot file
    // has already populated the cache from storage before we mount.
    const showChangeUrl = backendBaseUrlIsUserSet();

    // Shared with About (finalisation 15-R9); the splash can't depend on the
    // router, so it reloads outright.
    async function onChangeInstance(): Promise<void> {
        const saved = await promptAndSaveInstanceUrl();
        if (!saved) return;
        // Full reload so the boot probe re-runs against the new backend.
        setTimeout(() => window.location.reload(), 400);
    }

    // Loading flavour text. Cycled while the boot probe is in flight so the
    // user has something to read instead of staring at the pulsing logo.
    const LOADING_MESSAGES = [
        'Waking up Dora...',
        'Counting cucumbers...',
        'Polishing the apples...',
        'Stacking shelves...',
        'Checking the specials catalogue...',
        'Sharpening pencils for the shopping list...',
        'Untangling the trolley wheels...',
        'Asking Dora nicely to wake up...',
    ];
    const MESSAGE_INTERVAL_MS = 1800;

    const loadingMessage = ref(LOADING_MESSAGES[0] ?? '');
    let messageTimer: ReturnType<typeof setInterval> | null = null;

    function startMessageCycle() {
        stopMessageCycle();
        let i = 0;
        loadingMessage.value = LOADING_MESSAGES[i] ?? '';
        messageTimer = setInterval(() => {
            i = (i + 1) % LOADING_MESSAGES.length;
            loadingMessage.value = LOADING_MESSAGES[i] ?? '';
        }, MESSAGE_INTERVAL_MS);
    }

    function stopMessageCycle() {
        if (messageTimer !== null) {
            clearInterval(messageTimer);
            messageTimer = null;
        }
    }

    watch(
        () => props.error,
        (err) => {
            if (err) stopMessageCycle();
            else startMessageCycle();
        },
        { immediate: true }
    );

    onBeforeUnmount(stopMessageCycle);
</script>

<style scoped>
    .splash-overlay {
        position: fixed;
        inset: 0;
        z-index: 9000;
    }
    .splash-inner {
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 20px;
        padding: 24px;
    }

    .splash-logo-wrap {
        display: inline-flex;
        line-height: 0;
    }

    .splash-logo {
        width: clamp(140px, 28vw, 240px);
        height: auto;
        object-fit: contain;
        user-select: none;
        -webkit-user-drag: none;
        /* Light source-of-truth image on the midnight canvas needs a
           soft glow so it doesn't read too dim. */
        filter: drop-shadow(0 18px 22px rgba(20, 12, 50, 0.45));
    }

    .splash-logo--pulse {
        animation: splash-pulse 1.6s ease-in-out infinite;
        transform-origin: center;
    }

    @keyframes splash-pulse {
        0%, 100% {
            opacity: 0.7;
            transform: scale(0.96);
        }
        50% {
            opacity: 1;
            transform: scale(1.04);
        }
    }

    .splash-text {
        min-height: 3.5em;
        max-width: 380px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-start;
        gap: 6px;
        text-align: center;
    }

    /* Splash sits on the shell's midnight canvas with no card. Text
       has to be light-on-dark; --auth-shell-text is the dark card-face
       colour, wrong here. */
    .splash-loading-message {
        margin: 0;
        font-size: 0.95rem;
        color: var(--auth-shell-on-canvas);
        opacity: 0.85;
        animation: splash-fade-in 0.4s ease;
    }

    .splash-error-headline {
        margin: 0;
        font-size: 1.15rem;
        font-weight: 600;
        color: var(--auth-shell-on-canvas);
    }

    .splash-error-detail {
        margin: 0;
        font-size: 0.95rem;
        color: var(--auth-shell-on-canvas);
        opacity: 0.85;
        line-height: 1.4;
    }

    .splash-retry {
        margin-top: 8px;
        max-width: 260px;
    }

    /* FU-574 — the change-URL escape hatch is a ghost button; its default
       teal accent is dim on the midnight splash canvas, so lift the text to
       the same light treatment as the splash copy. */
    .splash-change-url {
        max-width: 260px;
    }
    .splash-change-url :deep(.dora-auth-btn--ghost) {
        color: var(--auth-shell-on-canvas);
        opacity: 0.85;
    }
    .splash-change-url :deep(.dora-auth-btn--ghost:hover) {
        background: rgba(255, 255, 255, 0.08);
        opacity: 1;
    }

    @keyframes splash-fade-in {
        from { opacity: 0; transform: translateY(4px); }
        to   { opacity: 0.85; transform: translateY(0); }
    }

    @media (prefers-reduced-motion: reduce) {
        .splash-logo--pulse,
        .splash-loading-message {
            animation: none;
        }
    }
</style>
