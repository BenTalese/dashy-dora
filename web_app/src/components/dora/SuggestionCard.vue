<template>
    <div class="dora-suggestion-card" :class="`dora-suggestion-${suggestion.severity}`">
        <div class="dora-suggestion-title">
            {{ suggestion.title }}
        </div>
        <div class="dora-suggestion-body">
            {{ suggestion.body }}
        </div>
        <q-expansion-item
            dense
            label="Why?"
            header-class="dora-suggestion-why-header"
            class="dora-suggestion-why"
        >
            <div class="text-caption dora-text-muted q-px-sm q-pb-xs">
                {{ suggestion.reason }}
            </div>
        </q-expansion-item>
        <div class="row q-gutter-xs q-mt-xs">
            <BaseButton
                v-if="suggestion.primary_action"
                variant="primary"
                dense
                size="sm"
                :label="suggestion.primary_action.label"
                @click="emit('accept')"
            />
            <BaseButton variant="ghost" dense size="sm" label="Snooze 1d" @click="emit('snooze')" />
            <BaseButton variant="ghost" dense size="sm" label="Dismiss" @click="emit('dismiss')" />
        </div>
    </div>
</template>

<script setup lang="ts">
    import BaseButton from 'src/components/BaseButton.vue';
    import type { DoraSuggestion } from 'src/services/api/suggestionsApiService';

    // One suggestion in Dora's chat panel. Presentational: the chat owns the
    // store calls and navigation behind each emit.
    defineProps<{ suggestion: DoraSuggestion }>();
    const emit = defineEmits<{
        (e: 'accept'): void;
        (e: 'snooze'): void;
        (e: 'dismiss'): void;
    }>();
</script>

<style scoped>
    /* A severity-tinted left border so high vs low priority reads at a
       glance; the title and buttons carry the meaning too, not colour alone. */
    .dora-suggestion-card {
        background: var(--surface-elevated);
        border-radius: var(--radius-lg);
        padding: var(--space-2) var(--space-3);
        margin-top: var(--space-2);
        border-left: 3px solid var(--brand-primary);
    }
    .dora-suggestion-card.dora-suggestion-high {
        border-left-color: var(--semantic-negative);
    }
    .dora-suggestion-card.dora-suggestion-medium {
        border-left-color: var(--semantic-warning);
    }
    .dora-suggestion-title {
        font-weight: 600;
        font-size: calc(var(--font-size-sm) * 1rem);
    }
    .dora-suggestion-body {
        font-size: calc(var(--font-size-sm) * 1rem);
        color: var(--text-muted);
        margin-top: 2px;
    }
    .dora-suggestion-why :deep(.dora-suggestion-why-header) {
        min-height: 24px;
        padding: 0;
        font-size: calc(var(--font-size-xs) * 1rem);
    }
</style>
