<template>
    <!--
        R-001 — "click the thing itself to change its picture" tile. The
        pattern was hand-rolled inside AccountSettings (profile picture);
        Stores needed the same affordance for logos, so it lives here once.

        The visual is a slot, so the caller keeps owning what a picture of
        *its* entity looks like (UserAvatar / StoreLogo). This component owns
        only the interaction: hidden native picker → `processImageFile`
        (R-003's resize/encode/MIME chokepoint) → `pick`.

        A single `accept="image/*"` input is deliberate — on mobile the OS
        sheet already offers camera *and* gallery, so there's nothing for the
        two-button ImageSourcePicker to add on a tile this small.
    -->
    <div
        class="image-edit-tile"
        :class="`image-edit-tile--${shape}`"
        :style="fill ? undefined : { width: `${width}px`, height: `${height}px` }"
        role="button"
        tabindex="0"
        :aria-label="label"
        @click="onActivate"
        @keydown.enter.prevent="onActivate"
        @keydown.space.prevent="onActivate"
    >
        <slot />
        <div class="image-edit-tile__overlay">
            <q-icon :name="ICONS.edit" :size="overlayIconSize" />
        </div>
        <q-inner-loading :showing="busy" />
        <!-- `@click.stop` is load-bearing, not defensive. `openPicker()` calls
             `.click()` on this input, and that synthetic click *bubbles* — up
             to the tile's own `@click`, which on a `manual` tile re-emits
             `activate`. So the recipe page's "Change photo" button closed its
             dialog and the bubbled click immediately reopened it: the owner's
             "modal stays open and you have to close it intentionally". -->
        <input
            ref="fileInput"
            type="file"
            :accept="accept"
            class="image-edit-tile__input"
            @click.stop
            @change="onFileChange"
        />
    </div>
</template>

<script lang="ts" setup>
    import { computed, ref } from 'vue';
    import { ICONS } from 'src/style/icons';
    import { processImageFile, type ProcessedImage } from 'src/services/files/imageService';

    const props = withDefaults(
        defineProps<{
            /** Accessible name for the tile, e.g. "Change your profile picture". */
            label: string;
            /** `circle` for avatars, `rounded` for logos and other rectangles. */
            shape?: 'circle' | 'rounded';
            width?: number;
            height?: number;
            /** Caller's own save round-trip — shows the spinner and blocks re-picks. */
            busy?: boolean;
            accept?: string;
            /** Size from the caller's own CSS instead of the `width`/`height`
             *  pixel pair — for a tile that has to be responsive (a recipe
             *  masthead photo is `100%` wide and square). */
            fill?: boolean;
            /** Don't open the picker on activation; emit `activate` and let the
             *  caller decide (e.g. offer Change / Remove first when a picture
             *  already exists). The caller opens it via the exposed
             *  `openPicker()`. */
            manual?: boolean;
        }>(),
        {
            shape: 'circle',
            width: 96,
            height: 96,
            busy: false,
            accept: 'image/*',
            fill: false,
            manual: false,
        },
    );

    const emit = defineEmits<{
        (e: 'pick', image: ProcessedImage): void;
        /** Message is safe to show the user verbatim. */
        (e: 'error', message: string): void;
        /** `manual` tiles only — the tile was clicked or keyboard-activated. */
        (e: 'activate'): void;
    }>();

    const fileInput = ref<HTMLInputElement | null>(null);
    const processing = ref(false);

    // Scale the pencil with the tile so it stays readable at 48px and doesn't
    // dominate at 96px.
    const overlayIconSize = computed(
        () => `${Math.max(16, Math.round(Math.min(props.width, props.height) * 0.27))}px`,
    );

    function triggerPick() {
        if (props.busy || processing.value) return;
        fileInput.value?.click();
    }

    function onActivate() {
        if (props.busy || processing.value) return;
        if (props.manual) {
            emit('activate');
            return;
        }
        triggerPick();
    }

    defineExpose({ openPicker: triggerPick });

    async function onFileChange(ev: Event) {
        const input = ev.target as HTMLInputElement;
        const file = input.files?.[0];
        input.value = ''; // let re-picking the same file re-fire
        if (!file) return;
        processing.value = true;
        try {
            emit('pick', await processImageFile(file));
        } catch (err) {
            emit('error', err instanceof Error ? err.message : 'Could not read that image.');
        } finally {
            processing.value = false;
        }
    }
</script>

<style scoped lang="scss">
    .image-edit-tile {
        position: relative;
        cursor: pointer;
        outline: none;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .image-edit-tile--circle,
    .image-edit-tile--circle .image-edit-tile__overlay {
        border-radius: 50%;
    }
    .image-edit-tile--rounded,
    .image-edit-tile--rounded .image-edit-tile__overlay {
        border-radius: var(--radius-md, 8px);
    }
    .image-edit-tile__overlay {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        // R-002 carve-out: a scrim sits over an arbitrary user-uploaded
        // image, not over a themed surface — its contrast has to hold
        // regardless of theme, so black-at-45% + white is the correct
        // fixed pair. Carried over verbatim from the AccountSettings
        // original this component was extracted from.
        color: #fff;
        background: rgba(0, 0, 0, 0.45);
        opacity: 0;
        transition: opacity 0.15s ease;
        pointer-events: none;
    }
    .image-edit-tile:hover .image-edit-tile__overlay,
    .image-edit-tile:focus-visible .image-edit-tile__overlay {
        opacity: 1;
    }
    .image-edit-tile:focus-visible {
        box-shadow: 0 0 0 3px var(--focus-ring);
    }
    .image-edit-tile__input { display: none; }
</style>
