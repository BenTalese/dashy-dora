<template>
    <!-- Delete refused because the item is still an ingredient: names the
         recipes so the user knows where to act. Rendered as text, never as
         HTML, because recipe names are user input. -->
    <BaseDialog
        :model-value="recipeNames.length > 0"
        title="Still used by recipes"
        closable
        @update:model-value="(open: boolean) => { if (!open) emit('close'); }"
    >
        <q-card-section>
            <p>
                Can't delete this stock item. It's an ingredient in
                {{ recipeNames.length }} {{ recipeNames.length === 1 ? 'recipe' : 'recipes' }}:
            </p>
            <ul class="q-my-sm">
                <li v-for="name in recipeNames" :key="name">{{ name }}</li>
            </ul>
            <p class="q-mb-none">Remove it from those recipes first, then try again.</p>
        </q-card-section>
        <template #actions>
            <BaseButton variant="primary" label="OK" @click="emit('close')" />
        </template>
    </BaseDialog>
</template>

<script setup lang="ts">
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';

    defineProps<{ recipeNames: string[] }>();
    const emit = defineEmits<{ (e: 'close'): void }>();
</script>
