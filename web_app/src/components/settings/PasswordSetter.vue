<template>
    <div class="password-setter">
        <!-- Revealing is the point here: the admin is typing a password
             they're about to say out loud to the person standing next to
             them. `PasswordField` owns the toggle + the length rule
             (finalisation 15-R8). -->
        <PasswordField
            v-if="!generate"
            :model-value="modelValue"
            outlined
            :label="label"
            kind="new"
            :autofocus="autofocus"
            :error="!!error || tooShort"
            :error-message="error || (tooShort ? PASSWORD_HINT : '')"
            :hint="error || tooShort ? '' : PASSWORD_HINT"
            lazy-rules
            @update:model-value="onInput"
        />

        <!-- Owner 2026-09-03 — this used to be a `dense` toggle carrying a
             paragraph that appeared only once it was on, so the dialog changed
             height as you flipped it and the switch didn't match the Admin
             toggle three lines below. Same size, same shape, no caption: the
             generated password gets its own dialog, which is where the
             "copy it, it's shown once" instruction already lives. -->
        <q-toggle
            :model-value="generate"
            :label="generateLabel"
            @update:model-value="$emit('update:generate', $event)"
        />
    </div>
</template>

<script setup lang="ts">
    /**
     * One password field + a "let Dora generate one instead" escape hatch.
     *
     * Shared by Admin → Users' Add-user and Change-password dialogs (R-001 —
     * the two had identical needs and would otherwise have drifted). The
     * parent owns both halves of the state: `modelValue` (the typed password)
     * and `generate` (whether to ignore it and ask the server for one), so it
     * can decide what to send without reaching back in here.
     */
    import PasswordField from 'src/components/PasswordField.vue';
    import { PASSWORD_HINT, MIN_PASSWORD_LENGTH } from 'src/models/password';
    import { computed } from 'vue';

    const props = withDefaults(
        defineProps<{
            modelValue: string;
            generate: boolean;
            label?: string;
            generateLabel?: string;
            /** Server-side message for this field, if the save was rejected. */
            error?: string | undefined;
            autofocus?: boolean;
        }>(),
        {
            label: 'Password',
            generateLabel: 'Generate password',
            error: '',
            autofocus: false,
        },
    );

    const emit = defineEmits<{
        (e: 'update:modelValue', value: string): void;
        (e: 'update:generate', value: boolean): void;
        (e: 'input'): void;
    }>();

    // Only nag once they've started typing — an empty field on a freshly
    // opened dialog isn't an error, it's the starting state.
    const tooShort = computed(
        () => props.modelValue.length > 0
            && props.modelValue.length < MIN_PASSWORD_LENGTH,
    );

    function onInput(value: string | number | null) {
        emit('update:modelValue', String(value ?? ''));
        emit('input');
    }
</script>

<style scoped lang="scss">
    .password-setter {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
</style>
