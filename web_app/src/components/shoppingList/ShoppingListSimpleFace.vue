<template>
    <!-- Simple mode (owner, 2026-11-07): one endless list for top-up and
         random shopping. No sections, no lifecycle, no prices: add things,
         tick them off. A tick means bought, so the row leaves the list and
         the item restocks; the page owns that mutation and its undo. Rows are
         the run face's, so the tap target and its keyboard handling are one
         component. -->
    <q-card v-if="lines.length === 0" flat class="sl-panel">
        <q-card-section class="text-center dora-text-muted">
            Nothing on the list. Add items with the toolbar, or from your
            stock list.
        </q-card-section>
    </q-card>
    <div v-else class="sl-list">
        <ShoppingListRunRow
            v-for="line in lines"
            :key="line.line_id"
            :line="line"
            :picked="false"
            :nested="false"
            :caption="captionFor(line)"
            no-price
            @toggle="emit('buy', line)"
        />
    </div>
</template>

<script lang="ts" setup>
    import ShoppingListRunRow from 'src/components/shoppingList/ShoppingListRunRow.vue';
    import type { ShoppingListLine } from 'src/models/shoppingList';

    defineProps<{
        lines: ShoppingListLine[];
    }>();

    const emit = defineEmits<{
        buy: [line: ShoppingListLine];
    }>();

    function captionFor(line: ShoppingListLine): string {
        const parts: string[] = [];
        const hint = line.preferred_buys?.find(
            (pb) => pb.preferred_buy_id === line.preferred_buy_id
        );
        if (hint) parts.push(hint.label);
        if (line.resolved_store_name) parts.push(line.resolved_store_name);
        return parts.join(' · ');
    }
</script>
