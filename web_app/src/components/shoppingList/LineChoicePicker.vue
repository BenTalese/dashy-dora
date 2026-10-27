<template>
    <!-- The name *is* the "which one" picker (owner, 2026-09-17), and what it
         offers depends on the install (2026-09-27): with products it lists the
         item's **offers**, without them its **preferred buys**. Shared by the
         list row and the template editor (2026-10-14), so a template is built
         with the same control the list is. The caller renders plain text when
         `hasLineChoices` is false. -->
    <BaseDropdown
        flat
        dense
        no-caps
        class="line-choice"
        :class="{ 'line-choice--struck': struck }"
        :disable="disable"
        :label="picked?.label ?? choice.itemName"
    >
        <q-list style="min-width: 240px">
            <q-item
                v-close-popup
                clickable
                :active="!picked"
                @click="onPick(null)"
            >
                <q-item-section>{{ choice.itemName }}</q-item-section>
            </q-item>
            <q-separator />
            <template v-if="productsEnabled">
                <q-item
                    v-for="offer in choice.offers"
                    :key="offer.product_id"
                    v-close-popup
                    clickable
                    :active="picked?.id === offer.product_id"
                    @click="onPick(offer.product_id)"
                >
                    <q-item-section>
                        <q-item-label>
                            {{ offer.name }}<span v-if="offer.size" class="dora-text-muted"> · {{ offer.size }}</span>
                        </q-item-label>
                        <q-item-label caption>
                            <template v-if="moneyEnabled && offer.price_now != null">
                                {{ formatMoney(offer.price_now) }} at
                            </template>{{ offer.store_name }}
                            <span v-if="moneyEnabled && offerSavings(offer) > 0" class="line-choice__save">
                                save {{ formatMoney(offerSavings(offer)) }}
                            </span>
                        </q-item-label>
                    </q-item-section>
                    <q-item-section side>
                        <StoreLogo
                            :name="offer.store_name"
                            :store-id="offer.store_id"
                            :height="20"
                            :width="34"
                        />
                    </q-item-section>
                </q-item>
            </template>
            <template v-else>
                <q-item
                    v-for="pb in choice.preferredBuys"
                    :key="pb.preferred_buy_id"
                    v-close-popup
                    clickable
                    :active="picked?.id === pb.preferred_buy_id"
                    @click="onPick(pb.preferred_buy_id)"
                >
                    <q-item-section>{{ pb.label }}</q-item-section>
                </q-item>
            </template>
        </q-list>
        <BaseTooltip>{{ productsEnabled ? 'Pick an offer' : 'Pick a preferred buy' }}</BaseTooltip>
    </BaseDropdown>
</template>

<script lang="ts" setup>
    import { computed } from 'vue';
    import BaseDropdown from 'src/components/BaseDropdown.vue';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import StoreLogo from 'src/components/StoreLogo.vue';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';
    import { formatMoney } from 'src/composables/useMoney';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import {
        pickedLineChoice, type LineChoice, type LineProductOffer,
    } from 'src/models/shoppingList';

    const props = defineProps<{
        choice: LineChoice;
        disable?: boolean;
        struck?: boolean;
    }>();

    /** `null` clears the choice. Only fires on a change. */
    const emit = defineEmits<{
        'pick-offer': [productId: string | null];
        'pick-hint': [preferredBuyId: string | null];
    }>();

    const { moneyEnabled } = useMoneyEnabled();
    const { products: productsEnabled } = useFeatureFlags();

    const picked = computed(() => pickedLineChoice(props.choice, productsEnabled.value));

    function onPick(id: string | null): void {
        if (id === (picked.value?.id ?? null)) return;
        if (productsEnabled.value) emit('pick-offer', id);
        else emit('pick-hint', id);
    }

    function offerSavings(offer: LineProductOffer): number {
        if (offer.price_now == null || offer.price_was == null) return 0;
        const diff = offer.price_was - offer.price_now;
        return diff > 0 ? diff : 0;
    }
</script>

<style scoped>
    /* The name-as-menu has to read as the *name*: same size, weight and ink as
       the plain-text case beside it, with nothing but a chevron and a hover
       wash to say it opens. A `q-btn` at this size would otherwise announce
       itself with padding, a min-height and a caret sized for a real button. */
    .line-choice {
        font-size: var(--font-size-lg);
        font-weight: 500;
        letter-spacing: -0.005em;
        color: var(--text-primary);
        min-height: 0;
        padding: 0 2px;
        margin-left: -2px;
        border-radius: var(--radius-sm);
        max-width: 100%;
        min-width: 0;
    }
    /* Steps down with `.sl-row__name` on a phone (shoppingList.scss), or the
       picker reads a size larger than the plain names around it. */
    @media (max-width: 599px) {
        .line-choice {
            font-size: var(--font-size-md);
        }
    }
    .line-choice:hover {
        background: var(--surface-sunken);
    }
    .line-choice :deep(.q-btn__content) {
        gap: 2px;
        flex-wrap: nowrap;
        min-width: 0;
    }
    .line-choice :deep(.block) {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        min-width: 0;
    }
    /* On the name it only has to hint that there is a choice. */
    .line-choice :deep(.q-btn-dropdown__arrow) {
        margin-left: 2px;
        font-size: 16px;
        opacity: 0.4;
    }
    .line-choice--struck :deep(.block) {
        text-decoration: line-through;
    }
    .line-choice__save {
        margin-left: var(--space-1);
        font-weight: 600;
        color: var(--savings-accent);
    }
</style>
