<template>
    <div
        class="dora-auth-shell"
        :class="[
            `dora-auth-shell--backdrop-${backdrop}`,
            `dora-auth-shell--variant-${variant}`,
        ]"
        :role="role"
        :aria-busy="ariaBusy"
    >
        <div v-if="backdrop !== 'none'" class="dora-auth-shell__bg" aria-hidden="true">
            <span class="dora-auth-shell__blob dora-auth-shell__blob--1" />
            <span class="dora-auth-shell__blob dora-auth-shell__blob--2" />
            <span class="dora-auth-shell__blob dora-auth-shell__blob--3" />
        </div>

        <img
            v-if="mascot !== 'none'"
            class="dora-auth-shell__mascot"
            :class="`dora-auth-shell__mascot--${mascot}`"
            src="../assets/logo-mascot.png"
            alt=""
            aria-hidden="true"
        />

        <q-card
            v-if="variant === 'card'"
            class="dora-auth-shell__card"
            flat
        >
            <q-card-section v-if="$slots['card-head']" class="text-center dora-auth-shell__card-head">
                <slot name="card-head" />
            </q-card-section>

            <q-card-section>
                <slot />
            </q-card-section>

            <q-card-section v-if="$slots['card-foot']" class="text-center q-pt-none dora-auth-shell__card-foot">
                <slot name="card-foot" />
            </q-card-section>
        </q-card>

        <div v-else class="dora-auth-shell__bleed">
            <slot />
        </div>

        <!-- Donation CTA — pulsing FAB, bottom-left. The Dora bubble (bottom-
             right) doesn't render pre-auth, so the corner is free (D-009).
             Opt out on splash / cannot-connect states via :donate="false". -->
        <DonateButton v-if="donate" variant="floating" />
    </div>
</template>

<script setup lang="ts">
    import DonateButton from 'src/components/donate/DonateButton.vue';

    withDefaults(
        defineProps<{
            backdrop?: 'blobs' | 'quiet' | 'none';
            mascot?: 'top-right' | 'top-centre' | 'none';
            variant?: 'card' | 'full-bleed';
            role?: string;
            ariaBusy?: boolean | undefined;
            /** Show the bottom-left donation FAB. Off for splash / loading
                surfaces where a "chip in" prompt would read as odd. */
            donate?: boolean;
        }>(),
        {
            backdrop: 'blobs',
            mascot: 'top-right',
            variant: 'card',
            role: 'main',
            donate: true,
        },
    );
</script>

<style scoped>
    /* R-002 DEC-2 carve-out: pre-auth surfaces render before or during
       auth-state resolution, so they deliberately do NOT read from
       --text-primary or any --data-theme-* tokens (which can flip dark
       before the user has authenticated). Force light, raw hex,
       documented HERE (previously duplicated as --lp-* on LoginPage and
       SetupAdminPage). See PROPOSAL_AUTH_SHELL.md §5.2. */
    .dora-auth-shell {
        --auth-shell-bg-base:             #1f2647;
        --auth-shell-blob-1:              #ff7ad9;
        --auth-shell-blob-2:              #f5c462;
        --auth-shell-blob-3:              #4cd5b7;
        --auth-shell-card-bg:             rgba(255, 255, 255, 0.94);
        --auth-shell-card-border:         rgba(255, 255, 255, 0.60);
        --auth-shell-text:                #1f2330;
        --auth-shell-text-muted:          #5b6173;
        --auth-shell-accent:              #006a80;
        --auth-shell-accent-strong:       #17b073;
        --auth-shell-accent-amber-strong: #c88a1e;
        /* Ink on the gradient surfaces + on the midnight canvas. The hexes
           used to sit in AuthButton, the two setup badges and SplashScreen
           (finalisation 15-R10). */
        --auth-shell-on-accent:           #fff;
        --auth-shell-on-amber:            #3a2a08;
        --auth-shell-on-canvas:           #fff;
        --auth-shell-shadow:              0 30px 80px -30px rgba(20, 12, 50, 0.55);

        color-scheme: light;
        min-height: 100vh;
        position: relative;
        overflow: hidden;
        background: var(--auth-shell-bg-base);
        color: var(--auth-shell-text);
    }
    /* Card variant centres the card in the viewport (login/setup/aux
       pages). Full-bleed leaves layout to the consumer — the bleed
       wrapper fills the shell but the consumer owns alignment (splash
       centres its own logo; WelcomeLayout flows header-then-content). */
    .dora-auth-shell--variant-card {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
    }

    .dora-auth-shell__bg {
        position: absolute;
        inset: 0;
        z-index: 0;
        overflow: hidden;
        pointer-events: none;
    }
    .dora-auth-shell__blob {
        position: absolute;
        width: 60vmax;
        height: 60vmax;
        border-radius: 50%;
        filter: blur(80px);
        opacity: 0.75;
        mix-blend-mode: screen;
        will-change: transform;
    }
    .dora-auth-shell__blob--1 {
        top: -20vmax;
        left: -10vmax;
        background: var(--auth-shell-blob-1);
        animation: dora-auth-shell-drift-1 22s ease-in-out infinite;
    }
    .dora-auth-shell__blob--2 {
        bottom: -20vmax;
        right: -10vmax;
        background: var(--auth-shell-blob-2);
        animation: dora-auth-shell-drift-2 26s ease-in-out infinite;
    }
    .dora-auth-shell__blob--3 {
        top: 30%;
        left: 40%;
        background: var(--auth-shell-blob-3);
        animation: dora-auth-shell-drift-3 30s ease-in-out infinite;
    }
    @keyframes dora-auth-shell-drift-1 {
        0%, 100% { transform: translate(0, 0) scale(1); }
        33%      { transform: translate(15vmax, 8vmax) scale(1.1); }
        66%      { transform: translate(-8vmax, 18vmax) scale(0.95); }
    }
    @keyframes dora-auth-shell-drift-2 {
        0%, 100% { transform: translate(0, 0) scale(1); }
        33%      { transform: translate(-12vmax, -10vmax) scale(1.05); }
        66%      { transform: translate(6vmax, -16vmax) scale(1.15); }
    }
    @keyframes dora-auth-shell-drift-3 {
        0%, 100% { transform: translate(-50%, -50%) scale(1); }
        50%      { transform: translate(-30%, -70%) scale(1.2); }
    }

    /* D2 — "quiet" freezes blob motion and drops opacity so splash /
       cannot-connect read continuous with login but don't spend animation
       budget while the app is bootstrapping. */
    .dora-auth-shell--backdrop-quiet .dora-auth-shell__blob {
        animation: none;
        opacity: 0.3;
    }

    .dora-auth-shell__mascot {
        position: absolute;
        top: 8%;
        width: 160px;
        height: 160px;
        object-fit: contain;
        z-index: 1;
        animation: dora-auth-shell-bob 6s ease-in-out infinite;
        filter: drop-shadow(0 18px 22px rgba(20, 12, 50, 0.45));
        /* Owner report 2026-08-31, Firefox on Android only (Chrome clean): a
           thin grey vertical line about the mascot's own height, immediately
           to its left, flickering for a few seconds after the login screen
           appears and then settling.

           It can't be a DOM element — nothing is drawn there, and anything
           that was would render in Chrome too. It is the **left edge of the
           mascot's own composite layer**: `drop-shadow` makes this a filtered
           element, the bob animates `transform` on top of that, and Firefox
           promotes the pair to a GPU layer *while the page is still settling*
           (the blobs behind it are blurred and `mix-blend-mode: screen`, so
           they are a blending group being rasterised at the same time). A
           seam at a tile boundary during that window is the classic shape of
           this, and "stops after a few seconds" is the layer tree stabilising.

           Declaring the promotion up front is the cheap fix: Firefox
           allocates the layer once, before the animation starts, instead of
           re-promoting mid-flight. Same treatment the blobs already carry.
           `backface-visibility` pins it to a single rasterisation pass.

           NOT confirmed on the reporting device — see DORA_VERIFY. */
        will-change: transform;
        backface-visibility: hidden;
    }
    .dora-auth-shell__mascot--top-right {
        right: 7%;
    }
    .dora-auth-shell__mascot--top-centre {
        right: 50%;
        margin-right: -80px;
    }
    @keyframes dora-auth-shell-bob {
        0%, 100% { transform: translateY(0) rotate(-2deg); }
        50%      { transform: translateY(-12px) rotate(2deg); }
    }
    /* B9.8 (preserved from LoginPage): shrink + tuck above card on
       narrow viewports. `right: 50%; margin-right: -48px` centres
       without stealing `transform` from the bob keyframe. */
    @media (max-width: 760px) {
        .dora-auth-shell__mascot--top-right {
            top: 2%;
            right: 50%;
            margin-right: -48px;
            width: 96px;
            height: 96px;
        }
        .dora-auth-shell__mascot--top-centre {
            margin-right: -48px;
            width: 96px;
            height: 96px;
        }
    }
    @media (max-width: 360px) {
        .dora-auth-shell__mascot--top-right {
            margin-right: -36px;
            width: 72px;
            height: 72px;
        }
        .dora-auth-shell__mascot--top-centre {
            margin-right: -36px;
            width: 72px;
            height: 72px;
        }
    }

    .dora-auth-shell__card {
        position: relative;
        z-index: 2;
        width: 100%;
        max-width: 460px;
        padding: 8px 4px;
        border-radius: 22px;
        background: var(--auth-shell-card-bg);
        border: 1px solid var(--auth-shell-card-border);
        backdrop-filter: blur(18px) saturate(140%);
        -webkit-backdrop-filter: blur(18px) saturate(140%);
        box-shadow: var(--auth-shell-shadow);
        color: var(--auth-shell-text);
        animation: dora-auth-shell-card-enter 0.55s cubic-bezier(0.2, 0.9, 0.25, 1.1) both;
    }
    @keyframes dora-auth-shell-card-enter {
        from { opacity: 0; transform: translateY(18px) scale(0.97); }
        to   { opacity: 1; transform: translateY(0) scale(1); }
    }
    .dora-auth-shell__card-head { padding-top: 22px; padding-bottom: 4px; }
    .dora-auth-shell__card-foot { padding-bottom: 22px; }

    .dora-auth-shell__bleed {
        position: relative;
        z-index: 2;
        width: 100%;
        min-height: 100vh;
        color: var(--auth-shell-text);
    }

    /* Force Quasar q-field internals to auth-shell-text regardless of
       any global theme state. Lives here so aux-page consumers inherit
       it (previously duplicated on LoginPage + SetupAdmin). */
    .dora-auth-shell__card :deep(.q-field__native),
    .dora-auth-shell__card :deep(.q-field__input),
    .dora-auth-shell__card :deep(.q-field__prefix),
    .dora-auth-shell__card :deep(.q-field__suffix),
    .dora-auth-shell__card :deep(.q-field__label) {
        color: var(--auth-shell-text);
    }
    .dora-auth-shell__card :deep(.q-field--outlined .q-field__control::before) {
        border-color: rgba(31, 38, 71, 0.25);
    }
    .dora-auth-shell__card :deep(.q-field--outlined.q-field--focused .q-field__control::after) {
        border-color: var(--auth-shell-accent-strong);
    }

    @media (prefers-reduced-motion: reduce) {
        .dora-auth-shell__blob,
        .dora-auth-shell__mascot,
        .dora-auth-shell__card { animation: none !important; }
        /* Nothing left to promote a layer for. */
        .dora-auth-shell__mascot { will-change: auto; }
        .dora-auth-shell__blob { opacity: 0.6; }
        .dora-auth-shell--backdrop-quiet .dora-auth-shell__blob { opacity: 0.3; }
    }
</style>
