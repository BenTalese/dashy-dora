<template>
    <!-- FU-609 / R-036 — root on <q-page> for the layout height contract so the
         redirect spinner centres in the viewport (document-scroll; no :style-fn). -->
    <q-page class="text-center q-pa-xl column flex-center">
        <AppSpinner size="60px" />
        <div class="text-body2 dora-text-muted q-mt-md">
            {{ message }}
        </div>
    </q-page>
</template>

<script lang="ts" setup>
    /**
     * P2-11 — PWA shortcut landing page.
     *
     * The "Shop now" home-screen shortcut points here. We can't bake a list id
     * into the manifest at build time (it's per-user), so this resolves it on
     * mount and `replace()`s the URL to the right place.
     *
     * Rule (UX v5 Q10): the server's next-up list (today's by shop day,
     * else the earliest still open) when it is open, else the overview.
     */
    import AppSpinner from 'src/components/AppSpinner.vue';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { onMounted, ref } from 'vue';
    import { useRouter } from 'vue-router';

    const router = useRouter();
    const shoppingListStore = useShoppingListStore();
    const message = ref('Finding your shopping list…');

    onMounted(async () => {
        try {
            await shoppingListStore.refreshAsync();
            const next = shoppingListStore.nextUpSummary;
            if (next && next.status === 'active') {
                await router.replace(`/shopping-lists/${next.shopping_list_id}`);
                return;
            }
            await router.replace('/shopping-lists');
        } catch {
            // Even on a fetch failure, the lists page is a sane fallback —
            // better than leaving a spinner spinning.
            await router.replace('/shopping-lists');
        }
    });
</script>
