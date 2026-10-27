<template>
    <q-banner
        v-if="message"
        class="dora-bg-negative-soft text-negative q-mb-md"
        dense
        rounded
        role="alert"
    >
        <template #avatar>
            <q-icon :name="ICONS.error" color="negative" />
        </template>
        {{ message }}
    </q-banner>
</template>

<script setup lang="ts">
    import { ICONS } from 'src/style/icons';
    defineProps<{
        message?: string | null;
    }>();
</script>
