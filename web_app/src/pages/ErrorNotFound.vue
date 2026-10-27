<template>
    <!--
        FU-030 — fullscreen 404 with the same warm "off-app" treatment as
        the login page. 404 can render pre-auth (typo'd URL while signed
        out), which is exactly what `AuthShell` is for: forced-light ladder,
        drifting blobs, floating mascot, glass card. This page used to carry
        its own copy of all of that (finalisation 15-R6; also the "404 page
        theme" feedback bullet).
    -->
    <AuthShell backdrop="blobs" mascot="top-right" :donate="false">
        <template #card-head>
            <div class="lost-code">404</div>
            <div class="lost-title" style="font-family: 'Cute Dino'">
                This page wandered off
            </div>
            <div class="lost-sub">
                Dora can't find that page.
            </div>
        </template>

        <div class="text-center">
            <AuthButton colour="primary" to="/" label="Take me home" />
        </div>
    </AuthShell>
</template>

<script setup lang="ts">
    import AuthShell from 'src/components/AuthShell.vue';
    import AuthButton from 'src/components/AuthButton.vue';
</script>

<style scoped>
    /* Page typography only — chrome, ladder and motion live on AuthShell. */
    .lost-code {
        font-size: 4.5rem;
        line-height: 1;
        font-weight: 700;
        letter-spacing: -0.02em;
        background: linear-gradient(135deg, var(--auth-shell-accent-strong), var(--auth-shell-accent));
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
    }
    .lost-title {
        font-size: 1.7rem;
        line-height: 1.15;
        letter-spacing: 0.01em;
        margin-top: 6px;
        color: var(--auth-shell-text);
    }
    .lost-sub {
        color: var(--auth-shell-text-muted);
        font-size: 0.95rem;
        margin: 12px auto 0;
        max-width: 360px;
        line-height: 1.45;
    }
</style>
