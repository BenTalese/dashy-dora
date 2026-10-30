<template>
    <!-- landing for /shopping-lists. The detail page is
         the canonical surface (with a list-selector in its header);
         when this route is reached with one or more lists, the
         **`beforeEnter` route guard in routes.ts** redirects to the
         picked list's detail before this component ever mounts — so we
         never get the "blank screen / wedged transition" race that an
         in-component `router.replace(...)` inside `onMounted` causes
         against MainLayout's <FadeTransition mode="out-in">.

         This component only renders when there are zero lists (empty
         state) or the API call failed (error state). -->
    <q-page padding>
        <q-banner
            v-if="loadError"
            class="dora-bg-negative-soft text-negative q-mb-md"
            dense
            rounded
        >
            <strong>Couldn't load your shopping lists.</strong>
            {{ loadError }}
            <template #action>
                <BaseButton variant="ghost" label="Retry" @click="retryLoad" />
            </template>
        </q-banner>

        <div v-if="loading && summariesEmpty" class="text-center q-py-xl">
            <AppSpinner size="48px" />
        </div>
        <div v-else-if="summariesEmpty && !loadError" class="text-center dora-text-muted q-py-xl">
            <q-icon :name="ICONS.shopping_cart" size="60px" class="q-mb-sm" />
            <div class="text-h6">No shopping lists yet.</div>
            <div class="q-mt-md">
                Start one empty, from a template, or filled from your stock.
            </div>
            <div class="q-mt-md">
                <BaseButton
                    :icon="ICONS.add"
                    label="New list"
                    @click="newListOpen = true"
                />
            </div>
        </div>

        <NewListDialog
            v-model="newListOpen"
            @created="onListCreated"
        />
    </q-page>
</template>

<script lang="ts" setup>
    import { ICONS } from 'src/style/icons';
    import AppSpinner from 'src/components/AppSpinner.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import NewListDialog from 'src/components/dialogs/NewListDialog.vue';
    import { useShoppingListStore } from 'src/stores/shoppingListStore';
    import { computed, ref } from 'vue';
    import { useRouter } from 'vue-router';

    const router = useRouter();
    const store = useShoppingListStore();

    const loading = computed(() => store.loading);
    const loadError = computed(() => store.loadError);
    const summariesEmpty = computed(() => store.summaries.length === 0);
    const newListOpen = ref(false);

    async function retryLoad() {
        await store.refreshAsync();
        // Same redirect the route guard makes. Re-navigating to this route
        // would not re-run its `beforeEnter`, so follow the pick directly.
        const next = store.nextUpSummary;
        if (next) await router.replace(`/shopping-lists/${next.shopping_list_id}`);
    }

    async function onListCreated({ listId }: { listId: string }) {
        // User-triggered (dialog Save click) — fine to navigate here.
        // Not a mount-time redirect, so no FadeTransition race.
        await router.push(`/shopping-lists/${listId}`);
    }
</script>
