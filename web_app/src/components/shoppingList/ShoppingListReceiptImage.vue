<template>
    <!-- One receipt photo, fetched through the HTTP client (R-045): the
         attachment endpoint is session-authenticated, so a bare <img :src>
         breaks on a split app./api. host and in the Capacitor shell. Its own
         component so each thumb in the strip owns its own `useAuthedImage`.
         The <img> is the root, so the caller's class, alt and click fall
         through onto it. -->
    <img v-if="src" :src="src" alt="Receipt" />
</template>

<script lang="ts" setup>
    import { useAuthedImage } from 'src/composables/useAuthedImage';

    const props = defineProps<{
        listId: string;
        attachmentId: string;
    }>();

    const src = useAuthedImage(() =>
        props.listId && props.attachmentId
            ? `/shopping-lists/${encodeURIComponent(props.listId)}/attachments/${encodeURIComponent(props.attachmentId)}`
            : null,
    );
</script>
