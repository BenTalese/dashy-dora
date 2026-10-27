<template>
    <!-- store logo. Resolution order:
         1. The store's uploaded image. Whether it has one comes from the
            caller's `hasImage` if given, otherwise from the stores list, so a
            call site whose DTO doesn't carry `has_image` still shows it.
         2. A deterministic hash-swatch + initial pill, so unknown stores
            still render predictably without licensing risk. Dora ships
            zero logos; everything else falls through to the swatch.

         The pill matches the size used by the previous MerchantLogo so
         existing layouts don't reflow. -->
    <img
        v-if="previewSrc || imageSrc"
        :src="previewSrc || imageSrc || undefined"
        :alt="name"
        class="dora-logo-image"
        :class="{ 'dora-logo--inline': inline }"
        :style="{ height: `${height}px`, width: `auto`, minWidth: `${width}px` }"
    />
    <div
        v-else
        class="dora-logo-placeholder"
        :class="{ 'dora-logo--inline': inline }"
        :style="placeholderStyle"
        role="img"
        :aria-label="name"
    >
        {{ initial }}
    </div>
</template>

<script lang="ts" setup>
    import { useAuthedImage } from 'src/composables/useAuthedImage';
    import { hashSwatch } from 'src/style/storeSwatch';
    import { useStoresStore } from 'src/stores/storesStore';
    import { computed } from 'vue';

    const props = withDefaults(
        defineProps<{
            /** Store name to render as the swatch initial / alt text. */
            name: string;
            /** Store id; required when `hasImage` is true so the route
             *  can be built. */
            storeId?: string | null | undefined;
            /** Server's `has_image` flag, when the caller has it. Omit it and
             *  the component looks the store up itself (2026-09-27: three
             *  call sites were passing a hardcoded `false` because their DTOs
             *  lacked the flag, so those logos never showed). */
            hasImage?: boolean | undefined;
            /** Local (data-URL) image to show instead of the server's, for
             *  previewing a just-picked logo before it has been saved — at
             *  that point there is no `storeId` to build a URL from. */
            previewSrc?: string | null | undefined;
            height?: number;
            width?: number;
            /** Sits inside a line of text, beside the store's name. */
            inline?: boolean;
        }>(),
        {
            height: 32, width: 48, hasImage: undefined, storeId: null, previewSrc: null,
            inline: false,
        },
    );

    // R-016 lazy hydration: pages that never render a logo never fetch stores.
    const storesStore = useStoresStore();
    void storesStore.ensureLoadedAsync();

    /** The store this logo is for: by id, else by name (some surfaces only
     *  carry the name, e.g. an offer's `store_name`). */
    const known = computed(() => {
        if (props.storeId) return storesStore.stores.find((s) => s.store_id === props.storeId) ?? null;
        const key = (props.name || '').trim().toLowerCase();
        if (!key) return null;
        return storesStore.stores.find((s) => s.name.trim().toLowerCase() === key) ?? null;
    });

    const resolvedHasImage = computed(() => props.hasImage ?? known.value?.has_image ?? false);

    // The palette + hash moved to `src/style/storeSwatch.ts` so the shopping
    // list's store breakdown draws each store in the same colour this
    // placeholder does (2026-08-26 feedback). R-002 carve-out and the
    // reasoning for determinism live with it there.
    const swatch = computed(() => hashSwatch(props.name));

    const placeholderStyle = computed(() => ({
        height: `${props.height}px`,
        minWidth: `${props.width}px`,
        background: swatch.value.background,
        color: swatch.value.ink,
        // The initial scales with the pill, so a 16px inline logo doesn't
        // carry a 15px letter.
        fontSize: `${Math.min(props.height * 0.5, 15)}px`,
    }));

    const initial = computed(() => {
        const trimmed = (props.name || '').trim();
        if (!trimmed) return '?';
        // First letter of the first word, uppercased. Keeps the pill tight
        // on long names like "Foodstuffs North Island".
        return trimmed[0]!.toUpperCase();
    });

    // Fetched through the HTTP client, never a bare <img> at the API (R-045).
    const imageSrc = useAuthedImage(() => {
        const id = props.storeId ?? known.value?.store_id;
        return resolvedHasImage.value && id ? `/stores/${encodeURIComponent(id)}/image` : null;
    });
</script>

<style scoped>
    .dora-logo-placeholder {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 2px 6px;
        font-weight: 700;
        letter-spacing: 0.02em;
        border-radius: 4px;
        user-select: none;
    }
    .dora-logo-image {
        display: inline-block;
        border-radius: 4px;
        object-fit: contain;
    }
    .dora-logo--inline {
        vertical-align: middle;
        margin-right: 4px;
        padding: 0 3px;
        border-radius: 3px;
    }
</style>
