<template>
    <!-- The small gradient pill above a setup card's title ("One-time
         setup", "Choose your Dora"). One copy — the two setup pages each
         carried their own (finalisation 15-R11). -->
    <div class="dora-auth-badge" role="status">
        <q-icon v-if="icon" :name="icon" size="14px" />
        <slot />
    </div>
</template>

<script setup lang="ts">
    defineProps<{ icon?: string }>();
</script>

<style scoped>
    .dora-auth-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        margin-bottom: 10px;
        border-radius: 999px;
        background: linear-gradient(135deg, var(--auth-shell-accent-strong), var(--auth-shell-accent));
        color: var(--auth-shell-on-accent);
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        box-shadow: 0 6px 14px -6px rgba(0, 106, 128, 0.6);
    }
</style>
