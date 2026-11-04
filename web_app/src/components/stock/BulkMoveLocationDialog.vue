<template>
    <BaseDialog
        :model-value="modelValue"
        :title="`Move ${count} item${count === 1 ? '' : 's'}`"
        closable
        card-style="width: 480px; max-width: 95vw"
        @update:model-value="onDialogUpdate"
    >
            <q-card-section>
                <!-- Round-14: same path-labelled, searchable picker as
                     Stock Overview filter + detail page + create dialog
                     so location selection is identical wherever it shows
                     up. -->
                <BaseSelect
                    :dense="false"
                    v-model="targetLocationId"
                    :options="filteredOptions"
                    emit-value
                    map-options
                    use-input
                    fill-input
                    hide-selected
                    input-debounce="200"
                    clearable
                    label="Destination location"
                    @filter="onFilter"
                />
            </q-card-section>
            <template #actions>
                <BaseButton variant="ghost" label="Cancel" v-close-popup />
                <BaseButton
                    variant="primary"
                    label="Move"
                    :loading="busy"
                    @click="emit('confirm', targetLocationId)"
                />
            </template>
    </BaseDialog>
</template>

<script setup lang="ts">
    import { ref, watch } from 'vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseSelect from 'src/components/BaseSelect.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';

    // Local narrowing ref backing the searchable picker — mirrors the
    // same pattern as the Stock Overview filter / detail-page / create
    // dialog so locations look + behave the same wherever they appear.

    type LocationOption = { label: string; value: string };

    const props = defineProps<{
        modelValue: boolean;
        count: number;
        locationOptions: readonly LocationOption[];
        busy?: boolean;
    }>();

    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
        (e: 'confirm', locationId: string | null): void;
    }>();

    const targetLocationId = ref<string | null>(null);
    const filteredOptions = ref<readonly LocationOption[]>(props.locationOptions);
    watch(
        () => props.locationOptions,
        (next) => { filteredOptions.value = next; },
        { immediate: true },
    );

    function onFilter(val: string, update: (cb: () => void) => void) {
        update(() => {
            const needle = val.toLowerCase();
            filteredOptions.value = needle
                ? props.locationOptions.filter((o) => o.label.toLowerCase().includes(needle))
                : props.locationOptions;
        });
    }

    // Reset selection each time the dialog opens so a previous pick doesn't
    // sneak into the next move.
    watch(
        () => props.modelValue,
        (open) => {
            if (open) {
                targetLocationId.value = null;
                filteredOptions.value = props.locationOptions;
            }
        },
    );

    function onDialogUpdate(value: boolean) {
        emit('update:modelValue', value);
    }
</script>
