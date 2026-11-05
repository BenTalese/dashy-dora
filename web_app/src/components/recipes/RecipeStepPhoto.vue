<template>
    <!-- One step photo. A photo picked in this edit session shows its data
         URL; a saved one is fetched through the HTTP client (R-045, FU-931),
         because a bare <img :src="/api/..."> breaks on a split app./api. host
         and in the Capacitor shell. The <img> is the root, so the caller's
         class, alt and click fall through onto it. -->
    <img v-if="src" :src="src" />
</template>

<script lang="ts" setup>
    import { computed } from 'vue';
    import { useAuthedImage } from 'src/composables/useAuthedImage';
    import { recipeStepImagePath } from 'src/services/api/recipeApiService';

    const props = defineProps<{
        recipeId: string;
        /** The saved photo's id; null for one picked in this session. */
        imageId: string | null;
        /** The picked photo's data URL; '' for a saved one. */
        dataUrl: string;
    }>();
    const emit = defineEmits<{ failed: [] }>();

    const fetched = useAuthedImage(
        () => (props.dataUrl || !props.imageId ? null : recipeStepImagePath(props.recipeId, props.imageId)),
        { onError: () => emit('failed') },
    );
    const src = computed(() => props.dataUrl || fetched.value);
</script>
