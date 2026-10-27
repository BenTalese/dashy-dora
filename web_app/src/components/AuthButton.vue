<template>
    <!-- Paired with AuthShell — do not use outside the pre-auth moment.
         The gradient/shadow treatment is deliberately contextual (see
         PROPOSAL_AUTH_SHELL §5.8 / IMPL_PLAN §3.2). If you want a
         general-purpose button use BaseButton instead.

         Uses BaseButton variant="ghost" as the base (a flat q-btn with
         no Quasar-applied background), then this component's scoped
         CSS layers the gradient / shadow / hover treatment. That way
         we reuse BaseButton's loading / disable / to / type / icon
         plumbing without fighting Quasar's `color=primary` background. -->
    <BaseButton
        variant="ghost"
        no-caps
        :class="['dora-auth-btn', `dora-auth-btn--${colour}`]"
        :type="type ?? 'button'"
        :label="label"
        :icon="icon"
        :loading="loading"
        :disable="disable"
        :to="to"
        @click="onClick"
    >
        <slot />
    </BaseButton>
</template>

<script setup lang="ts">
    import BaseButton from 'src/components/BaseButton.vue';

    withDefaults(
        defineProps<{
            colour?: 'primary' | 'secondary' | 'ghost';
            type?: 'button' | 'submit' | 'reset';
            label?: string | undefined;
            icon?: string | undefined;
            loading?: boolean | undefined;
            disable?: boolean | undefined;
            to?: string | object | undefined;
        }>(),
        {
            colour: 'primary',
            type: 'button' as const,
        },
    );

    const emit = defineEmits<{
        (e: 'click', event: MouseEvent): void;
    }>();

    function onClick(event: MouseEvent) {
        emit('click', event);
    }
</script>

<style scoped>
    /* AuthButton renders BaseButton at its root, so classes on
       <BaseButton> land on the underlying <q-btn>. Style rules target
       that root; no :deep needed. Size is pinned to a consistent
       hit target inside the auth moment — the whole point (§5.8). */
    .dora-auth-btn {
        width: 100%;
        min-height: 48px;
        font-weight: 600;
        letter-spacing: 0.02em;
        border-radius: 12px;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .dora-auth-btn:hover {
        transform: translateY(-1px);
    }

    /* Primary — teal gradient (identical to today's .login-submit). */
    .dora-auth-btn--primary {
        background: linear-gradient(135deg, var(--auth-shell-accent-strong), var(--auth-shell-accent));
        color: var(--auth-shell-on-accent);
        box-shadow: 0 10px 24px -10px rgba(0, 106, 128, 0.55);
    }
    .dora-auth-btn--primary:hover {
        box-shadow: 0 14px 28px -10px rgba(0, 106, 128, 0.65);
    }

    /* Secondary — amber gradient ("gradient of dora yellow", feedback
       §LOGIN). Two-stop via D10's --auth-shell-accent-amber-strong. */
    .dora-auth-btn--secondary {
        background: linear-gradient(135deg, var(--auth-shell-accent-amber-strong), var(--auth-shell-blob-2));
        color: var(--auth-shell-on-amber);
        box-shadow: 0 10px 24px -10px rgba(200, 138, 30, 0.55);
    }
    .dora-auth-btn--secondary:hover {
        box-shadow: 0 14px 28px -10px rgba(200, 138, 30, 0.65);
    }

    /* Ghost — flat, accent-coloured text; keeps a 12px hit target so it
       reads as a button not a fine-print link. */
    .dora-auth-btn--ghost {
        background: transparent;
        color: var(--auth-shell-accent);
        box-shadow: none;
    }
    .dora-auth-btn--ghost:hover {
        background: rgba(0, 106, 128, 0.06);
    }

    @media (prefers-reduced-motion: reduce) {
        .dora-auth-btn:hover { transform: none; }
    }
</style>
