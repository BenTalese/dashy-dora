<template>
    <!-- The cook-mode Previous / (Repeat) / Next row, shared by the step face,
         the photo face and the photo zoom (04-R13). Owner feedback 2026-09-03:
         the buttons share one row on a phone, each free to shrink to its
         share, so no label is dropped; the size comes from the host, which is
         the one that knows the viewport (R-019). -->
    <div class="cook-nav">
        <BaseButton
            variant="ghost"
            :size="size"
            :icon="ICONS.arrow_back"
            label="Previous"
            :disable="!canPrev"
            @click="emit('prev')"
        />
        <BaseButton
            v-if="showRepeat"
            variant="ghost"
            :size="size"
            :icon="ICONS.replay"
            label="Repeat"
            :disable="repeatDisabled"
            @click="emit('repeat')"
        />
        <!-- In the zoom dialog Next only pages: finishing from a magnified
             photo would close the dialog onto a different screen. -->
        <BaseButton
            v-if="pageOnly"
            variant="ghost"
            :size="size"
            :icon-right="ICONS.arrow_forward"
            label="Next"
            :disable="isLast"
            @click="emit('next')"
        />
        <BaseButton
            v-else
            variant="primary"
            :size="size"
            :icon-right="isLast ? ICONS.check : ICONS.arrow_forward"
            :label="isLast ? 'Finish' : 'Next'"
            @click="emit('next')"
        />
    </div>
</template>

<script setup lang="ts">
    import BaseButton from 'src/components/BaseButton.vue';
    import { ICONS } from 'src/style/icons';

    withDefaults(
        defineProps<{
            canPrev: boolean;
            isLast: boolean;
            showRepeat?: boolean;
            repeatDisabled?: boolean;
            pageOnly?: boolean;
            size?: 'md' | 'lg' | undefined;
        }>(),
        { showRepeat: false, repeatDisabled: false, pageOnly: false, size: undefined },
    );

    const emit = defineEmits<{
        (e: 'prev'): void;
        (e: 'repeat'): void;
        (e: 'next'): void;
    }>();
</script>

<style scoped lang="scss">
    .cook-nav {
        display: flex;
        justify-content: center;
        gap: var(--space-2);
    }
    .cook-nav :deep(.dora-btn) {
        flex: 0 1 auto;
        min-width: 0;
        // D-004 — the surface most likely to be tapped with a floury finger.
        min-height: 44px;
    }
    @media (max-width: 599px) {
        .cook-nav :deep(.dora-btn) {
            flex: 1 1 0;
            padding-left: var(--space-2);
            padding-right: var(--space-2);
        }
        // Stop q-btn's content wrapping if a translation or a narrower phone
        // puts it back on the boundary.
        .cook-nav :deep(.q-btn__content) {
            flex-wrap: nowrap;
        }
    }
</style>
