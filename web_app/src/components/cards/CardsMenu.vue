<template>
    <!-- The "Show & order cards" menu (FU-832 / finalisation 08-R19), shared by
         the dashboard and Reports. One flat list: the up/down buttons are C13's
         tap-mandatory alternative and work on mobile and from the keyboard;
         the drag handle is the desktop extra, off on touch
         (`$q.platform.is.mobile` includes tablets). Icon-only below `sm`
         (D-005: it keeps its accessible name and a tooltip). -->
    <BaseButton
        variant="ghost"
        dense
        :icon="ICONS.tune"
        :label="$q.screen.lt.sm ? undefined : 'Cards'"
        aria-label="Cards"
    >
        <BaseTooltip v-if="$q.screen.lt.sm">Show &amp; order cards</BaseTooltip>
        <q-menu anchor="bottom right" self="top right" transition-show="jump-down" transition-hide="jump-up">
            <q-list dense class="cards-menu">
                <q-item-label header>Show &amp; order cards</q-item-label>
                <q-item
                    v-for="card in cards"
                    :key="card.id"
                    :class="dnd.bind(card.id).rowClass"
                    v-bind="dnd.bind(card.id).rowProps"
                >
                    <q-item-section
                        v-if="dragEnabled"
                        avatar
                        class="dora-dnd-handle"
                        v-bind="dnd.bind(card.id).handleProps"
                    >
                        <q-icon :name="ICONS.drag_indicator" />
                        <BaseTooltip>Drag to reorder</BaseTooltip>
                    </q-item-section>
                    <q-item-section avatar>
                        <q-icon :name="card.icon" />
                    </q-item-section>
                    <q-item-section>{{ card.label }}</q-item-section>
                    <q-item-section side>
                        <div class="row items-center no-wrap">
                            <BaseButton
                                :aria-label="`Move ${card.label} up`"
                                variant="icon"
                                size="sm"
                                :icon="ICONS.arrow_upward"
                                :disable="!canMove(card.id, 'up')"
                                @click="emit('move', card.id, 'up')"
                            >
                                <BaseTooltip>Move up</BaseTooltip>
                            </BaseButton>
                            <BaseButton
                                :aria-label="`Move ${card.label} down`"
                                variant="icon"
                                size="sm"
                                :icon="ICONS.arrow_downward"
                                :disable="!canMove(card.id, 'down')"
                                @click="emit('move', card.id, 'down')"
                            >
                                <BaseTooltip>Move down</BaseTooltip>
                            </BaseButton>
                            <q-toggle
                                :model-value="isVisible(card.id)"
                                :aria-label="`Show ${card.label}`"
                                @update:model-value="emit('toggle', card.id)"
                            />
                        </div>
                    </q-item-section>
                </q-item>
            </q-list>
        </q-menu>
    </BaseButton>
</template>

<script setup lang="ts" generic="Id extends string">
    import { computed } from 'vue';
    import { useQuasar } from 'quasar';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { useDragDropList } from 'src/composables/useDragDropList';
    import type { CardDef } from 'src/helpers/cardCatalogue';
    import { ICONS } from 'src/style/icons';

    const props = defineProps<{
        /** The menu rows in display order (`useCardLayout().menuCards`). */
        cards: CardDef<Id>[];
        isVisible: (id: Id) => boolean;
        canMove: (id: Id, dir: 'up' | 'down') => boolean;
        /** Drag payload type, unique per surface so a drag can't cross pages. */
        mime: string;
    }>();

    const emit = defineEmits<{
        (e: 'move', id: Id, dir: 'up' | 'down'): void;
        (e: 'toggle', id: Id): void;
        (e: 'drop', sourceId: Id, targetId: Id): void;
    }>();

    const $q = useQuasar();
    const dragEnabled = computed(() => !$q.platform.is.mobile);
    const dnd = useDragDropList<Id>({
        mime: props.mime,
        getId: (id) => id,
        canDragStart: () => dragEnabled.value,
        onDrop: ({ item: source }, { item: target }) => emit('drop', source, target),
    });
</script>

<style scoped>
    .cards-menu {
        min-width: 300px;
    }
</style>
