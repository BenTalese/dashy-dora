<template>
    <BaseDialog
        v-model="open"
        :title="`Lighter than ${entry?.recipe_name ?? 'this meal'}?`"
        closable
    >
        <div class="text-caption dora-text-muted q-mb-sm">{{ subtitle }}</div>

        <div v-if="loading" class="column q-gutter-sm">
            <AppSkeleton v-for="n in 3" :key="n" height="52px" />
        </div>

        <div v-else-if="loadError" class="text-negative">
            Couldn't load lighter options. Close and try again.
        </div>

        <div v-else-if="candidates.length === 0" class="dora-text-muted">
            {{ emptyMessage }}
        </div>

        <q-list v-else separator>
            <q-item v-for="candidate in candidates" :key="candidate.to_recipe_id">
                <q-item-section>
                    <q-item-label>{{ candidate.to_recipe_name }}</q-item-label>
                    <q-item-label caption>
                        {{ Math.round(candidate.kcal_per_serving) }} kcal per serving
                        · {{ chipLabel(candidate.reason_chip) }}
                    </q-item-label>
                    <q-item-label
                        v-if="candidate.missing_ingredient_names.length"
                        caption
                        class="dora-text-muted"
                    >
                        You'd need: {{ candidate.missing_ingredient_names.join(', ') }}
                    </q-item-label>
                </q-item-section>
                <q-item-section side>
                    <div class="row items-center q-gutter-sm no-wrap">
                        <div class="text-caption text-positive">
                            −{{ Math.round(candidate.saved_kcal) }} kcal
                        </div>
                        <BaseButton
                            variant="secondary"
                            label="Swap"
                            :loading="applyingId === candidate.to_recipe_id"
                            :disable="applyingId !== null"
                            @click="onApply(candidate)"
                        />
                    </div>
                </q-item-section>
            </q-item>
        </q-list>
    </BaseDialog>
</template>

<script lang="ts" setup>
    /**
     * FU-637 — "find a lighter option" for one planned meal.
     *
     * Opened from the meal's own menu and never on Dora's initiative: the
     * owner's call is that the app displays nutrition where it helps a
     * decision and holds no calorie target, so there is no threshold at which
     * suggesting a lighter meal would be Dora's idea rather than yours.
     *
     * Ranking, the reduction figure and the reason chip are all server-owned
     * (R-003); this renders them and applies the choice through the existing
     * swap endpoint, so undo and the audit ledger come for free.
     */
    import { computed, ref, watch } from 'vue';

    import AppSkeleton from 'src/components/AppSkeleton.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import MealPlanApiService from 'src/services/api/mealPlanApiService';
    import type { LighterAlternative } from 'src/services/api/mealPlanApiService';
    import type { MealPlanEntry } from 'src/models/mealPlan';

    const props = defineProps<{
        modelValue: boolean;
        mealPlanId: string | null;
        entry: MealPlanEntry | null;
    }>();

    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
        (e: 'swapped'): void;
    }>();

    const api = new MealPlanApiService();
    const loading = ref(false);
    const applyingId = ref<string | null>(null);
    const candidates = ref<LighterAlternative[]>([]);
    const loadError = ref(false);

    const open = computed({
        get: () => props.modelValue,
        set: (value: boolean) => emit('update:modelValue', value),
    });

    const subtitle = computed(() => {
        const kcal = props.entry?.kcal_per_serving;
        return kcal === null || kcal === undefined
            ? 'Meals you could swap in'
            : `Currently ${Math.round(kcal)} kcal per serving`;
    });

    const emptyMessage = computed(() =>
        'Nothing lighter to suggest.',
    );

    /** Server vocabulary → copy. The chip is decided at rank time and frozen;
     *  the client only translates it. */
    function chipLabel(chip: string): string {
        if (chip === 'lighter_recipe_cookable') return 'uses stock you have';
        if (chip === 'lighter_recipe_similar') return 'same style of meal';
        if (chip === 'lighter_recipe_household_fav') return "you've cooked it before";
        return 'lighter';
    }

    // Request token: reopening on another meal must not show the previous
    // meal's late answer.
    let loadSeq = 0;
    async function load() {
        const req = ++loadSeq;
        if (!props.mealPlanId || !props.entry) { loading.value = false; return; }
        loading.value = true;
        loadError.value = false;
        try {
            const result = await api.getLighterAlternativesAsync(
                props.mealPlanId, props.entry.meal_plan_entry_id,
            );
            if (req === loadSeq) candidates.value = result.candidates;
        } catch (err) {
            // A failed lookup is not "nothing lighter" — say it failed.
            if (req !== loadSeq) return;
            console.warn('lighter alternatives failed to load', err);
            loadError.value = true;
        } finally {
            if (req === loadSeq) loading.value = false;
        }
    }

    async function onApply(candidate: LighterAlternative) {
        if (!props.mealPlanId || !props.entry) return;
        applyingId.value = candidate.to_recipe_id;
        try {
            await api.applySwapAsync(props.mealPlanId, {
                kind: 'recipe',
                entry_id: props.entry.meal_plan_entry_id,
                to_recipe_id: candidate.to_recipe_id,
                // Stale-guard: if the week drifted since the dialog opened, the
                // server 409s rather than swapping a meal that already changed.
                expected_from_recipe_id: props.entry.recipe_id,
                reason: 'lighter',
            });
            emit('swapped');
            open.value = false;
        } finally {
            applyingId.value = null;
        }
    }

    watch(
        () => [props.modelValue, props.entry?.meal_plan_entry_id],
        ([isOpen]) => {
            if (isOpen) {
                candidates.value = [];
                void load();
            }
        },
    );
</script>
