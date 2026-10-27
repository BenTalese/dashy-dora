<template>
    <!--
        Settings rebuild Phase 4 (§2.9) — the one place "the user" is drawn.
        Shows the uploaded profile picture when present; otherwise a
        per-consumer fallback (the menu-bar keeps the person icon, the
        Account header + admin rows keep initials). The picture is fetched
        through the HTTP client (R-045); a failed fetch shows the fallback,
        and the store's image-version counter refetches after an upload /
        clear.
    -->
    <q-avatar
        :size="size"
        :color="showImage ? undefined : color"
        :text-color="showImage ? undefined : textColor"
    >
        <img
            v-if="showImage"
            :src="src!"
            :alt="alt"
        />
        <q-icon
            v-else-if="fallback === 'icon'"
            :name="fallbackIcon"
        />
        <template v-else>{{ initial }}</template>
    </q-avatar>
</template>

<script setup lang="ts">
    import { ICONS } from 'src/style/icons';
    import { useAuthedImage } from 'src/composables/useAuthedImage';
    import { useAuthStore } from 'src/stores/authStore';
    import { computed } from 'vue';

    const props = withDefaults(
        defineProps<{
            userId: string;
            hasImage: boolean;
            size?: string;
            // Per-consumer fallback when there's no picture: the menu-bar
            // button keeps the `person` icon (the feedback explicitly asks to
            // preserve it); larger avatars show initials.
            fallback?: 'icon' | 'initials';
            // Only used when fallback === 'initials'.
            username?: string;
            fallbackIcon?: string;
            // Optional q-avatar styling for the fallback (initials/icon) state.
            // `| undefined` so callers can pass `cond ? 'accent' : undefined`
            // under exactOptionalPropertyTypes (e.g. admin-vs-non-admin rows).
            color?: string | undefined;
            textColor?: string | undefined;
        }>(),
        { size: '32px', fallback: 'icon' },
    );

    const authStore = useAuthStore();

    // The store's version counter bumps on any upload / clear; it rides the
    // path as a cache-buster, so a new picture refetches.
    const version = computed(() => authStore.imageVersionOf(props.userId));
    const src = useAuthedImage(() => (
        props.hasImage ? `/users/${props.userId}/image?v=${encodeURIComponent(String(version.value))}` : null
    ));
    const showImage = computed(() => src.value !== null);
    const fallbackIcon = computed(() => props.fallbackIcon ?? ICONS.person);
    const alt = computed(() => props.username ?? 'Profile picture');
    const initial = computed(() => {
        const name = props.username ?? '';
        return name.length > 0 ? name.charAt(0).toUpperCase() : '?';
    });
</script>
