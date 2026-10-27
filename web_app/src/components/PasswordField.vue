<template>
    <!-- One password input for the whole app (finalisation 15-R8 / 13-R12):
         the reveal toggle and the minimum-length rule used to be written
         four times, two of them with the length hard-coded. The rule reads
         `models/password.ts`, the one TS mirror of the server's minimum. -->
    <q-input
        v-bind="$attrs"
        :model-value="modelValue"
        :type="reveal ? 'text' : 'password'"
        :autocomplete="autocomplete"
        :rules="rules"
        @update:model-value="(v) => emit('update:modelValue', String(v ?? ''))"
    >
        <template #append>
            <q-icon
                :name="reveal ? ICONS.visibility_off : ICONS.visibility"
                class="cursor-pointer"
                role="button"
                tabindex="0"
                :aria-label="reveal ? 'Hide password' : 'Show password'"
                @click="reveal = !reveal"
                @keydown.enter.prevent="reveal = !reveal"
                @keydown.space.prevent="reveal = !reveal"
            />
        </template>
        <template v-for="(_, slot) in slots" #[slot]="scope" :key="slot">
            <slot :name="slot" v-bind="scope ?? {}" />
        </template>
    </q-input>
</template>

<script setup lang="ts">
    import { ICONS } from 'src/style/icons';
    import { PASSWORD_HINT, passwordLongEnough } from 'src/models/password';
    import { computed, ref, useSlots } from 'vue';

    defineOptions({ inheritAttrs: false });

    const props = withDefaults(
        defineProps<{
            modelValue: string;
            /** `new` applies the minimum-length rule; `current` only requires a value. */
            kind?: 'new' | 'current';
            autocomplete?: string | undefined;
            /** Extra rules appended after the built-in ones. */
            extraRules?: Array<(v: string) => true | string>;
        }>(),
        { kind: 'new', extraRules: () => [] },
    );
    const emit = defineEmits<{ (e: 'update:modelValue', value: string): void }>();

    const slots = useSlots();
    const reveal = ref(false);
    const autocomplete = computed(() => props.autocomplete ?? (props.kind === 'new' ? 'new-password' : 'current-password'));
    const rules = computed(() => [
        (v: string) => !!v || 'Password is required',
        ...(props.kind === 'new' ? [(v: string) => passwordLongEnough(v) || PASSWORD_HINT] : []),
        ...props.extraRules,
    ]);
</script>
