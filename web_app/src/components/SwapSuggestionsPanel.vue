<template>
    <!-- FU-451 — budget-defense recipe swaps. Renders only when money features
         are on AND the week is projected over budget (proposal §6b). -->
    <q-card
        v-if="moneyEnabled && suggestions && suggestions.projected_over"
        flat
        bordered
        class="swap-panel q-mb-md"
    >
        <!-- Owner 2026-09-12 — *"no indication of going over budget… found it
             by stumbling upon it. Should be more visible."* It was: this panel
             rendered BELOW seven day cards, at the bottom of the week's own
             scroller, so on any planned week you had to scroll past the whole
             week to learn you couldn't afford it. It sits above the week now,
             and its head is a warning banner rather than a card title with two
             figure columns.

             The figures themselves moved to the right rail's "Cost this week"
             card, where the week's money already lives — *"the other info can
             be in the right rail somehow"*. What's left here is the sentence
             that needs to interrupt you, and the swaps behind a disclosure. -->
        <button
            type="button"
            class="swap-panel__banner"
            :aria-expanded="open"
            @click="open = !open"
        >
            <q-icon :name="ICONS.warning" size="22px" class="swap-panel__warn" />
            <span class="swap-panel__headline">
                Over budget by {{ formatMoney(suggestions.overshoot) }} this week
            </span>
            <span v-if="suggestions.candidates.length" class="swap-panel__count">
                {{ suggestions.candidates.length }}
                {{ suggestions.candidates.length === 1 ? 'swap' : 'swaps' }}
            </span>
            <q-icon
                :name="ICONS.expand_more"
                size="20px"
                class="swap-panel__chevron"
                :class="{ 'swap-panel__chevron--open': open }"
            />
        </button>

        <div v-if="open && suggestions.candidates.length" class="swap-panel__lede">
            <q-icon :name="ICONS.savings" size="16px" color="positive" class="q-mr-xs" />
            Swapping all {{ suggestions.candidates.length === 1 ? 'of it' : 'of them' }}
            brings the week to
            <strong>{{ formatMoney(suggestions.projected_after_applying_all) }}</strong>
        </div>

        <!-- Just-applied undo banner (session-scoped) -->
        <q-banner v-if="lastLedgerId" dense class="swap-panel__undo">
            <template #avatar><q-icon :name="ICONS.check" color="positive" /></template>
            Swap applied.
            <template #action>
                <BaseButton
                    variant="secondary"
                    :icon="ICONS.undo"
                    label="Undo"
                    :loading="busy"
                    @click="onUndo"
                />
            </template>
        </q-banner>

        <!-- Candidate rows -->
        <q-list v-if="open && suggestions.candidates.length" separator>
            <q-item v-for="c in suggestions.candidates" :key="c.entry_id + c.to_recipe_id">
                <q-item-section avatar>
                    <q-icon :name="ICONS.restaurant" color="savings-accent" />
                </q-item-section>
                <q-item-section>
                    <q-item-label caption class="dora-text-muted">
                        Recipe swap · {{ dayLabel(c.entry_scheduled_for) }} {{ c.entry_slot }}
                    </q-item-label>
                    <q-item-label class="swap-row__names">
                        {{ c.from_recipe_name }}
                        <q-icon :name="ICONS.arrow_forward" size="14px" class="q-mx-xs" />
                        {{ c.to_recipe_name }}
                    </q-item-label>
                    <q-item-label caption class="swap-row__chip">
                        {{ chipLabel(c.reason_chip) }}
                    </q-item-label>
                </q-item-section>
                <q-item-section side top>
                    <div class="swap-row__saved">−{{ formatMoney(c.saved) }}</div>
                    <BaseButton variant="secondary" label="Preview" @click="openPreview(c)" />
                </q-item-section>
            </q-item>
        </q-list>

        <!-- Zero-state: over budget but nothing saves money -->
        <!-- Owner 2026-09-12 — the "Open shopping lists" button went with the
             sentence that justified it: *"swaps are for cooking, and you would
             remove meals, not go to shopping lists."* Dropping a meal is the
             lever this panel can't pull for you, so it says so and stops. -->
        <q-card-section
            v-else-if="open"
            class="swap-panel__zero dora-text-muted"
        >
            No swap saves you money this week.
        </q-card-section>
    </q-card>

    <!-- Preview → confirm dialog (Charter P7) -->
    <q-dialog v-model="previewOpen">
        <q-card class="swap-preview">
            <q-card-section>
                <div class="text-subtitle1">
                    Swap {{ previewCandidate?.entry_slot }}'s
                    {{ previewCandidate?.from_recipe_name }}
                    → {{ previewCandidate?.to_recipe_name }}
                </div>
            </q-card-section>
            <q-card-section class="q-pt-none">
                <div class="dora-text-muted">Estimated week cost after this swap</div>
                <div class="swap-preview__cost">
                    {{ formatMoney(previewAfterCost) }}
                    <span class="dora-text-muted swap-preview__was">
                        (was {{ formatMoney(suggestions?.cost_per_week ?? 0) }},
                        save {{ formatMoney(previewCandidate?.saved ?? 0) }})
                    </span>
                </div>
                <template v-if="previewCandidate?.missing_ingredient_names.length">
                    <div class="dora-text-muted q-mt-md">Ingredients you'd need to buy</div>
                    <div>{{ previewCandidate.missing_ingredient_names.join(' · ') }}</div>
                </template>
            </q-card-section>
            <q-card-actions align="right">
                <BaseButton variant="secondary" label="Cancel" @click="previewOpen = false" />
                <BaseButton
                    variant="primary"
                    :icon="ICONS.swap_horiz"
                    label="Apply swap"
                    :loading="busy"
                    @click="onApply"
                />
            </q-card-actions>
        </q-card>
    </q-dialog>
</template>

<script lang="ts" setup>
    import { ref, watch } from 'vue';
    import { useQuasar } from 'quasar';
    import { ICONS } from 'src/style/icons';
    import { formatDate as formatLocaleDate } from 'src/composables/useDateFormat';
    import { formatMoney } from 'src/composables/useMoney';
    import { useMoneyEnabled } from 'src/composables/useMoneyEnabled';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
    import BaseButton from 'src/components/BaseButton.vue';
    import MealPlanApiService, {
        type RecipeSwapCandidate,
        type SwapSuggestions,
    } from 'src/services/api/mealPlanApiService';

    const props = defineProps<{ mealPlanId: string | null }>();

    /** Collapsed on arrival: the banner is the part that has to interrupt you,
     *  and a list of swaps above the week you are trying to read is a second
     *  interruption you didn't ask for. */
    const open = ref(false);
    // Emitted after a successful apply/undo so the parent reloads the week grid.
    const emit = defineEmits<{ (e: 'changed'): void }>();

    const $q = useQuasar();
    const { moneyEnabled } = useMoneyEnabled();
    const api = new MealPlanApiService();

    const suggestions = ref<SwapSuggestions | null>(null);
    const busy = ref(false);
    const previewOpen = ref(false);
    const previewCandidate = ref<RecipeSwapCandidate | null>(null);
    // Ledger id of the most recent apply this session — drives the undo banner.
    const lastLedgerId = ref<string | null>(null);

    const previewAfterCost = ref(0);

    const CHIP_LABELS: Record<RecipeSwapCandidate['reason_chip'], string> = {
        cheaper_recipe_cookable: 'Cheaper, uses stock you have',
        cheaper_recipe_similar: 'Cheaper, same style of meal',
        cheaper_recipe_household_fav: "Cheaper, and you've cooked it before",
    };
    function chipLabel(chip: RecipeSwapCandidate['reason_chip']): string {
        return CHIP_LABELS[chip] ?? 'Cheaper option';
    }

    function dayLabel(iso: string): string {
        const d = new Date(iso + 'T00:00:00');
        return formatLocaleDate(d, { weekday: 'long' });
    }

    async function load() {
        if (!props.mealPlanId || !moneyEnabled.value) {
            suggestions.value = null;
            return;
        }
        try {
            suggestions.value = await api.getSwapSuggestionsAsync(props.mealPlanId);
        } catch {
            suggestions.value = null;
        }
    }

    function openPreview(c: RecipeSwapCandidate) {
        previewCandidate.value = c;
        previewAfterCost.value = Math.max(0, (suggestions.value?.cost_per_week ?? 0) - c.saved);
        previewOpen.value = true;
    }

    async function onApply() {
        if (!props.mealPlanId || !previewCandidate.value) return;
        busy.value = true;
        try {
            const result = await api.applySwapAsync(props.mealPlanId, {
                kind: 'recipe',
                entry_id: previewCandidate.value.entry_id,
                to_recipe_id: previewCandidate.value.to_recipe_id,
                expected_from_recipe_id: previewCandidate.value.from_recipe_id,
            });
            lastLedgerId.value = result.swap_ledger_id;
            previewOpen.value = false;
            $q.notify({ type: 'positive', message: 'Swap applied.' });
            emit('changed');
            await load();
        } catch (err) {
            $q.notify({
                type: 'negative', 
                message: 'Could not apply the swap.', caption: toastCaption(err),
            });
        } finally {
            busy.value = false;
        }
    }

    async function onUndo() {
        if (!props.mealPlanId || !lastLedgerId.value) return;
        busy.value = true;
        try {
            await api.undoSwapAsync(props.mealPlanId, lastLedgerId.value);
            lastLedgerId.value = null;
            $q.notify({ type: 'info', message: 'Swap undone.' });
            emit('changed');
            await load();
        } catch (err) {
            $q.notify({
                type: 'negative', 
                message: 'Could not undo the swap.', caption: toastCaption(err),
            });
        } finally {
            busy.value = false;
        }
    }

    watch(() => props.mealPlanId, load, { immediate: true });
    watch(moneyEnabled, load);
    // Let the parent force a re-fetch (e.g. after editing the week elsewhere).
    defineExpose({ reload: load });
</script>

<style scoped lang="scss">
    /* A warning banner, not a card title: tinted, one line, and the whole
       thing toggles the swaps under it. The tint and the glyph carry the tone;
       the words stay page ink (D-002 — full-strength negative ink on a tinted
       fill is the contrast fail the app corrects everywhere else). */
    .swap-panel {
        border-color: var(--semantic-warning);
    }
    .swap-panel__banner {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        width: 100%;
        min-height: 44px;
        padding: var(--space-2);
        background: var(--semantic-warning-soft);
        border: 0;
        color: var(--text-primary);
        cursor: pointer;
        font: inherit;
        text-align: left;
    }
    .swap-panel__banner:focus-visible {
        outline: 2px solid var(--brand-primary);
        outline-offset: -2px;
    }
    .swap-panel__warn { color: var(--semantic-warning); }
    .swap-panel__headline {
        flex: 1 1 auto;
        font-size: var(--font-size-md);
        font-weight: 600;
    }
    .swap-panel__count {
        flex: 0 0 auto;
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
    }
    .swap-panel__chevron {
        flex: 0 0 auto;
        color: var(--text-secondary);
        transition: transform var(--motion-fast) var(--motion-ease);
    }
    .swap-panel__chevron--open { transform: rotate(180deg); }
    .swap-panel__lede {
        font-size: var(--font-size-sm);
        padding: var(--space-2);
    }
    .swap-panel__undo {
        background: color-mix(in srgb, var(--savings-accent) 12%, transparent);
    }
    .swap-panel__zero { font-size: 0.9rem; }
    .swap-row__names { font-weight: 500; }
    .swap-row__chip { color: var(--savings-accent); }
    .swap-row__saved {
        font-weight: 700;
        color: var(--savings-accent);
        text-align: right;
        margin-bottom: 6px;
    }
    .swap-preview { min-width: 320px; max-width: 460px; }
    .swap-preview__cost { font-size: 1.4rem; font-weight: 700; }
    .swap-preview__was { font-size: 0.85rem; font-weight: 400; }
</style>
