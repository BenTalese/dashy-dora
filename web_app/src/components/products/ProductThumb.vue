<template>
    <!-- `fill` stretches to the parent box instead of sizing itself. A
         `q-avatar` sizes via font-size, so it cannot be told to fill a
         container — passing it `size="100%"` yields a tiny glyph in the
         corner, which is exactly what the product card's square media area
         got before this existed. -->
    <div v-if="fill" class="dora-bg-sunken product-thumb product-thumb--fill">
        <img v-if="src" :src="src" :alt="alt" />
        <q-icon v-else :name="ICONS.shopping_bag" :size="iconSize" />
    </div>
    <q-avatar v-else rounded :size="size" class="dora-bg-sunken product-thumb">
        <img v-if="src" :src="src" :alt="alt" />
        <q-icon v-else :name="ICONS.shopping_bag" :size="iconSize" />
    </q-avatar>
</template>

<script lang="ts" setup>
    /**
     * A product's image, fetched through the HTTP client (R-045, see
     * `useAuthedImage`): a rounded `q-avatar` on the sunken surface, the image
     * if there is one, a shopping-bag glyph if not. A component rather than a
     * bare composable because every call site renders that same anatomy
     * (R-001), so the fallback glyph can't drift between surfaces.
     */
    import { ICONS } from 'src/style/icons';
    import { useAuthedImage } from 'src/composables/useAuthedImage';

    const props = withDefaults(
        defineProps<{
            productId: string;
            /** Server-provided flag. When false we never make the request —
             *  the glyph is the correct render, not a fallback from a failure. */
            hasImage?: boolean;
            alt?: string;
            /** Avatar size, any CSS length Quasar accepts. Ignored when
             *  `fill` is set. */
            size?: string;
            iconSize?: string;
            /** Stretch to the parent box rather than sizing to `size`. For
             *  full-bleed media (the product card's square image well). */
            fill?: boolean;
        }>(),
        { hasImage: false, alt: '', size: '36px', iconSize: '18px', fill: false },
    );

    const src = useAuthedImage(() => (
        props.hasImage && props.productId
            ? `/products/${encodeURIComponent(props.productId)}/image`
            : null
    ));
</script>

<style scoped lang="scss">
    .product-thumb :deep(img),
    .product-thumb img {
        object-fit: contain;
        max-width: 100%;
        max-height: 100%;
    }
    /* Absolutely fills its parent rather than taking `height: 100%`, so the
       glyph stays centred in a box sized by `aspect-ratio` without depending
       on that box resolving a percentage height first.
       Requires the parent to be `position: relative`. */
    .product-thumb--fill {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
    }
</style>
