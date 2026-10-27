<template>
    <label
        class="file-drop"
        :class="{
            'file-drop--dragging': dragging,
            'file-drop--busy': loading,
            'file-drop--disabled': disabled,
            'file-drop--filled': !!modelValue,
        }"
        @dragover.prevent="onDragOver"
        @dragleave.prevent="onDragLeave"
        @drop.prevent="onDrop"
    >
        <!--
            FU-545: the native <input type="file"> is the single labelled,
            focusable control; the wrapping <label> (non-interactive) forwards
            clicks + Enter/Space to it natively. This is the standard accessible
            file-input pattern — no `role="button"` / `tabindex` / keydown /
            programmatic `.click()`, so there's no nested-interactive violation
            (which the old hidden-input-in-a-button-div tripped). The input is
            visually hidden but kept IN the a11y tree (aria-label + focusable),
            and disabled while busy/disabled so the label can't open the picker.
            (Supersedes the FU-531 `@click.stop` re-entrancy guard: the Remove
            button is interactive content, so a native label never forwards a
            click on it to the input.)
        -->
        <input
            type="file"
            class="file-drop__input"
            :accept="accept"
            :disabled="disabled || loading"
            :aria-label="label"
            @change="onInputChange"
        />

        <!-- Idle / prompt state -->
        <template v-if="!modelValue && !loading">
            <q-icon :name="ICONS.cloud_upload" size="30px" class="file-drop__icon" />
            <div class="file-drop__label">{{ label }}</div>
            <div v-if="hint" class="file-drop__hint">{{ hint }}</div>
        </template>

        <!-- Selected-file state -->
        <template v-else-if="modelValue && !loading">
            <q-icon :name="ICONS.attach_file" size="22px" class="file-drop__icon" />
            <div class="file-drop__file">
                <span class="file-drop__filename">{{ modelValue.name }}</span>
                <span class="file-drop__filesize">{{ formatSize(modelValue.size) }}</span>
            </div>
            <BaseButton
                variant="icon"
                :icon="ICONS.close"
                aria-label="Remove file"
                @click="onClear"
            >
                <BaseTooltip>Remove file</BaseTooltip>
            </BaseButton>
        </template>

        <!-- Busy state -->
        <template v-else>
            <q-spinner size="24px" class="file-drop__icon" />
            <div class="file-drop__label">
                {{ progressValue > 0 && progressValue < 1
                    ? `Uploading ${Math.round(progressValue * 100)}%`
                    : (loadingText || 'Working…') }}
            </div>
            <q-linear-progress
                v-if="progressValue > 0 && progressValue < 1"
                :value="progressValue"
                rounded
                size="6px"
                color="primary"
                class="file-drop__progress"
            />
        </template>
    </label>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import { ICONS } from 'src/style/icons';
    import { computed, ref } from 'vue';

    const props = defineProps<{
        modelValue: File | null;
        accept?: string;
        label: string;
        hint?: string;
        loading?: boolean;
        loadingText?: string;
        progress?: number;
        disabled?: boolean;
    }>();

    const progressValue = computed(() => props.progress ?? 0);

    const emit = defineEmits<{
        (e: 'update:modelValue', value: File | null): void;
        (e: 'pick', value: File): void;
        (e: 'clear'): void;
    }>();

    const dragging = ref(false);

    function take(file: File | null) {
        if (!file) return;
        emit('update:modelValue', file);
        emit('pick', file);
    }

    function onInputChange(event: Event) {
        const target = event.target as HTMLInputElement;
        take(target.files?.[0] ?? null);
        // Reset so re-picking the same file still fires change.
        target.value = '';
    }

    function onDragOver() {
        if (props.disabled || props.loading) return;
        dragging.value = true;
    }
    function onDragLeave() {
        dragging.value = false;
    }
    function onDrop(event: DragEvent) {
        dragging.value = false;
        if (props.disabled || props.loading) return;
        take(event.dataTransfer?.files?.[0] ?? null);
    }

    function onClear() {
        emit('update:modelValue', null);
        emit('clear');
    }

    function formatSize(bytes: number): string {
        if (bytes < 1024) return `${bytes} B`;
        const kb = bytes / 1024;
        if (kb < 1024) return `${kb.toFixed(1)} KB`;
        const mb = kb / 1024;
        if (mb < 1024) return `${mb.toFixed(1)} MB`;
        return `${(mb / 1024).toFixed(2)} GB`;
    }
</script>

<style scoped lang="scss">
    .file-drop {
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--space-2);
        min-height: 132px;
        padding: var(--space-5) var(--space-4);
        border: 1.5px dashed var(--border-strong);
        border-radius: var(--radius-lg);
        background: var(--surface-elevated);
        color: var(--text-secondary);
        text-align: center;
        cursor: pointer;
        transition: border-color 160ms ease, background 160ms ease, color 160ms ease;
    }
    /* Focus lives on the visually-hidden native input now, so surface the ring
       on the wrapping label via :focus-within (FU-545). */
    .file-drop:hover:not(.file-drop--disabled):not(.file-drop--busy),
    .file-drop:focus-within:not(.file-drop--disabled):not(.file-drop--busy) {
        border-color: var(--brand-primary);
        background: color-mix(in srgb, var(--brand-primary) 5%, var(--surface-elevated));
        color: var(--text-primary);
    }
    .file-drop:focus-within:not(.file-drop--disabled):not(.file-drop--busy) {
        outline: 2px solid var(--focus-ring);
        outline-offset: 2px;
    }
    .file-drop--dragging {
        border-color: var(--brand-primary);
        border-style: solid;
        background: color-mix(in srgb, var(--brand-primary) 10%, var(--surface-elevated));
        color: var(--text-primary);
    }
    .file-drop--filled {
        flex-direction: row;
        min-height: 0;
        padding: var(--space-3) var(--space-4);
        border-style: solid;
        border-color: var(--border-default);
        background: var(--surface-component);
        cursor: default;
        text-align: left;
    }
    .file-drop--busy {
        cursor: default;
    }
    .file-drop--disabled {
        opacity: 0.55;
        cursor: not-allowed;
    }

    /* Visually hidden but still focusable + in the a11y tree (not display:none,
       which would drop it out of the tab order) — FU-545. */
    .file-drop__input {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
    }
    .file-drop__icon {
        color: var(--brand-primary);
        flex: 0 0 auto;
    }
    .file-drop__label {
        font-size: 0.9375rem;
        font-weight: 600;
        color: inherit;
    }
    .file-drop__hint {
        font-size: 0.8125rem;
        color: var(--text-muted);
        line-height: 1.35;
    }
    .file-drop__file {
        flex: 1 1 auto;
        min-width: 0;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 2px;
    }
    .file-drop__filename {
        font-size: 0.9375rem;
        font-weight: 600;
        color: var(--text-primary);
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .file-drop__filesize {
        font-size: 0.8125rem;
        color: var(--text-muted);
    }
    .file-drop__progress {
        width: min(280px, 100%);
        margin-top: var(--space-1);
    }
</style>
