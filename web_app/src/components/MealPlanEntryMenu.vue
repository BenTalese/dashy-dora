<template>
    <!-- Owner feedback 2026-09-05, three items on the meal-slot dropdown — the
         repeated recipe name, the too-thin rows on a phone, and the two action
         icons. All three landed on TWO identical menus: `MealPlanEntryChip`
         (the desktop week grid) and `MealPlanRichCard` (the phone's day list)
         carried the same nine items, the same emits and the same comments,
         copied. Fixing one thing in two places three times over is exactly the
         duplication R-001 exists to stop, so the menu is now one component and
         the two hosts render it.

         The hosts keep their own `q-menu`-less shells; this IS the menu. -->
    <q-menu transition-show="jump-down" transition-hide="jump-up" @before-show="resyncServings">
        <!-- Owner 2026-09-05 — *"the name doesn't need to be repeated in the
             meal dropdown when you tap/click on an allocated meal slot."* It
             doesn't: the menu opens anchored to the chip that just said it. -->
        <!-- D-004 / owner 2026-09-05 — *"dropdowns are not thick enough for
             mobile but they seem okay for desktop."* So `dense` is a desktop
             affordance now rather than the default: below `md` the rows take
             Quasar's full 48px item height. -->
        <q-list :dense="$q.screen.gt.sm" style="min-width: 220px">
            <!-- Inline servings adjuster — stays open for rapid ± taps. The
                 shared `NumberStepper` rather than a hand-rolled − value +
                 (R-001). `min="0"` because stepping the last serving away is
                 how you take a meal off the plan; the host asks before it does
                 anything a whole cook batch would notice.

                 Owner 2026-09-12 — typeable here, like the rail's cooked-count
                 tile: a menu you opened to change a number should let you say
                 the number. The ± buttons are always visible (the rail hides
                 its pair until hover, which is a list affordance; inside an
                 opened menu there is nothing to keep quiet for). -->
            <q-item>
                <q-item-section>
                    <q-item-label>Servings</q-item-label>
                    <!-- Owner 2026-10-15: what stands behind the number, the
                         same facts the recipe page's pool line gives. -->
                    <q-item-label v-if="servingsInfo" caption class="entry-menu__info">
                        {{ servingsInfo }}
                    </q-item-label>
                </q-item-section>
                <q-item-section side>
                    <NumberStepper
                        :model-value="shownServings"
                        editable
                        :min="0"
                        decrement-label="One fewer serving"
                        increment-label="One more serving"
                        @click.stop
                        @update:model-value="onServingsStep"
                    >
                        <BaseTooltip>Servings (0 removes the meal)</BaseTooltip>
                    </NumberStepper>
                </q-item-section>
            </q-item>
            <q-separator />
            <!-- Owner 2026-09-05 — *"dropdown icons should be cookbook icon
                 (same as menu button) for view recipe, and chef hat for cook
                 now."* `menu_book` is the glyph the main menu's Cookbook entry
                 wears; `open_in_new` said "a new tab opens", which isn't what
                 happens. `chef_hat` was already right (the 2026-09-05 sweep
                 that made it THE cooking glyph). -->
            <q-item clickable v-close-popup @click="emit('view')">
                <q-item-section avatar><q-icon :name="ICONS.menu_book" /></q-item-section>
                <q-item-section>View recipe</q-item-section>
            </q-item>
            <q-item clickable v-close-popup @click="emit('cook')">
                <q-item-section avatar><q-icon :name="ICONS.chef_hat" /></q-item-section>
                <q-item-section>Cook now</q-item-section>
            </q-item>
            <!-- FU-637 — asked for, never volunteered: Dora holds no calorie
                 target, so she has no threshold at which she'd start suggesting
                 you eat less. Hidden unless this meal has a figure solid enough
                 to compare against (R-041). -->
            <q-item
                v-if="canGoLighter"
                clickable
                v-close-popup
                @click="emit('lighter')"
            >
                <q-item-section avatar><q-icon :name="ICONS.monitor_heart" /></q-item-section>
                <q-item-section>Find a lighter option…</q-item-section>
            </q-item>
            <template v-if="batchEnabled">
                <q-separator />
                <!-- Owner 2026-09-04 — *"When in batch mode, I should be able to
                     mark a meal as being cooked fresh."* Hidden on a linked
                     meal: a cook batch IS the pool, so the two are mutually
                     exclusive (the server refuses the pairing too). The caption
                     states the whole behaviour, because "fresh" alone doesn't
                     say what it does to the pool. -->
                <q-item v-if="!linked" clickable v-close-popup @click="emit('fresh')">
                    <q-item-section avatar>
                        <q-icon :name="ICONS.cookFresh" :color="fresh ? 'primary' : undefined" />
                    </q-item-section>
                    <q-item-section>
                        <q-item-label>{{ fresh ? 'Cooking fresh' : 'Cook fresh on the day' }}</q-item-label>
                        <q-item-label caption>
                            {{ fresh ? 'Tap to serve it from cooked servings instead' : 'Cooked on the day, not from ready servings' }}
                        </q-item-label>
                    </q-item-section>
                    <q-item-section v-if="fresh" side>
                        <q-icon :name="ICONS.check" color="primary" />
                    </q-item-section>
                </q-item>
                <q-item v-if="!fresh" clickable v-close-popup @click="emit('link')">
                    <q-item-section avatar><q-icon :name="ICONS.link" /></q-item-section>
                    <q-item-section>{{ linked ? 'Change cook days…' : 'Cook once for more days…' }}</q-item-section>
                </q-item>
                <q-item v-if="linked" clickable v-close-popup @click="emit('unlink')">
                    <q-item-section avatar><q-icon :name="ICONS.link_off" /></q-item-section>
                    <q-item-section>Separate this cook</q-item-section>
                </q-item>
            </template>
            <q-separator />
            <q-item clickable v-close-popup @click="emit('remove')">
                <q-item-section avatar><q-icon :name="ICONS.close" color="negative" /></q-item-section>
                <q-item-section>Remove from plan</q-item-section>
            </q-item>
        </q-list>
    </q-menu>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import NumberStepper from 'src/components/NumberStepper.vue';
    import { useBatchEnabled } from 'src/composables/useBatchEnabled';
    import { supplyTooltip } from 'src/helpers/mealPlanEntryStatus';
    import type { MealPlanEntry } from 'src/models/mealPlan';
    import { useRecipeStore } from 'src/stores/recipeStore';
    import { computed, ref, watch } from 'vue';

    const { batchEnabled } = useBatchEnabled();

    const props = defineProps<{ entry: MealPlanEntry }>();

    const emit = defineEmits<{
        (e: 'view'): void;
        (e: 'cook'): void;
        (e: 'lighter'): void;
        (e: 'remove'): void;
        (e: 'adjust', delta: number): void;
        (e: 'link'): void;
        (e: 'unlink'): void;
        (e: 'fresh'): void;
    }>();

    // The stepper shows the value the user has stepped to, and each emitted
    // delta is measured from THAT — not from `entry.servings`, which lags until
    // the save lands, so two fast taps used to both send "+1 from 1" (the
    // planner queues the deltas and applies each to the fresh plan).
    const shownServings = ref(props.entry.servings);
    watch(() => props.entry.servings, (v) => { shownServings.value = v; });
    // A failed save (or a cancelled "remove this cook?") leaves `entry.servings`
    // unchanged, so the watcher never fires — re-read it each time the menu opens.
    function resyncServings() { shownServings.value = props.entry.servings; }
    function onServingsStep(v: number) {
        const delta = v - shownServings.value;
        if (delta === 0) return;
        shownServings.value = v;
        emit('adjust', delta);
    }

    // Only offer the comparison when this meal's own figure can be compared —
    // "lighter than an estimate we don't trust" isn't an answer.
    const canGoLighter = computed(
        () => props.entry.kcal_per_serving !== null && props.entry.kcal_is_reliable,
    );

    // PROPOSAL_MEAL_PLANS_PART_2 — a linked cook batch (one cook, several days),
    // and its 2026-09-04 sibling, a meal cooked fresh on its day. Both are only
    // meaningful for a batch household.
    const linked = computed(() => batchEnabled.value && !!props.entry.cook_batch_id);
    const fresh = computed(() => batchEnabled.value && props.entry.cook_fresh);

    /** A batch household sees the recipe's cooked servings and how many the
     *  plan has claimed (server figures off the recipe); a fresh household,
     *  where nothing is cooked ahead, sees whether it can be made. */
    const recipeStore = useRecipeStore();
    const servingsInfo = computed<string>(() => {
        if (props.entry.consumed_at) return '';
        if (!batchEnabled.value || props.entry.cook_fresh) return supplyTooltip(props.entry);
        const recipe = recipeStore.recipes.find((r) => r.recipe_id === props.entry.recipe_id);
        if (!recipe) return '';
        const cooked = `${recipe.available_meals} cooked`;
        if (recipe.committed_meals === 0) return cooked;
        const short = recipe.committed_meals - recipe.available_meals;
        if (short > 0) return `${cooked} · plan needs ${short} more`;
        return `${cooked} · ${recipe.committed_meals} planned · ${recipe.unallocated_meals} free`;
    });
</script>

<style scoped>
    .entry-menu__info {
        white-space: nowrap;
    }
</style>
