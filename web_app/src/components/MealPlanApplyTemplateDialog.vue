<template>
    <!--
        Owner 2026-09-13 — *"the presentation and usage of templates here is
        genuinely terrible and a little confusing. Redo it."*

        What it replaced (`MealPlanTemplatesDrawer`, deleted) was four jobs in
        one side sheet, reached from a menu item called "Apply template…":
        saving the current week (a second copy of the overflow item that opened
        it), **applying recurring via a nested modal on top of the sheet**,
        renaming and deleting each row, and a link out to the rotating-sets
        page. Applying — the thing it was named for — was one button among them.

        This dialog does one job. You pick a template, you say whether it's just
        this week or a run of weeks, you apply. Saving stays in the overflow
        menu where it was, and managing (rename / delete / sets) moved to the
        Templates page, both per the owner's own layout.

        Recurring is **inline**, not a second modal: it is the same action with a
        date range, and stacking a dialog on a dialog to collect two dates was
        most of what made this confusing. A rotating **set** can only be applied
        as a run — rotating is what a set is — so choosing one turns the range
        on and says why.
    -->
    <BaseDialog
        :model-value="modelValue"
        title="Apply a template"
        closable
        card-style="min-width: 0; width: min(460px, 94vw)"
        @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    >
        <q-card-section v-if="!templates.length && !sets.length" class="q-pt-none">
            <div class="dora-text-muted">
                No templates yet. Plan a week, then use
                <strong>Save week as template</strong> in the week menu.
            </div>
        </q-card-section>

        <template v-else>
            <q-card-section class="q-pt-none q-pb-xs">
                <!-- One list, radio semantics: the choice IS the template, and a
                     per-row Apply button (what the old sheet had) meant the
                     recurring range had nothing to belong to. -->
                <q-list separator class="apply-tpl__list">
                    <q-item
                        v-for="t in templates"
                        :key="t.meal_plan_template_id"
                        clickable
                        :active="selected === `t:${t.meal_plan_template_id}`"
                        active-class="apply-tpl__row--active"
                        @click="selected = `t:${t.meal_plan_template_id}`"
                    >
                        <q-item-section side>
                            <q-radio
                                :model-value="selected"
                                :val="`t:${t.meal_plan_template_id}`"
                                @update:model-value="(v: string) => selected = v"
                            />
                        </q-item-section>
                        <q-item-section>
                            <q-item-label>{{ t.name }}</q-item-label>
                            <q-item-label caption>
                                {{ t.entry_count }} meal{{ t.entry_count === 1 ? '' : 's' }}
                                <span v-if="t.description"> · {{ t.description }}</span>
                            </q-item-label>
                        </q-item-section>
                    </q-item>

                    <!-- Sets are listed with the templates rather than behind a
                         link, because "apply a rotating set" is the same
                         sentence as "apply a template" with a longer object. -->
                    <q-item-label v-if="sets.length" header class="apply-tpl__header">
                        Rotating sets
                    </q-item-label>
                    <q-item
                        v-for="s in sets"
                        :key="s.meal_plan_template_set_id"
                        clickable
                        :active="selected === `s:${s.meal_plan_template_set_id}`"
                        active-class="apply-tpl__row--active"
                        @click="selected = `s:${s.meal_plan_template_set_id}`"
                    >
                        <q-item-section side>
                            <q-radio
                                :model-value="selected"
                                :val="`s:${s.meal_plan_template_set_id}`"
                                @update:model-value="(v: string) => selected = v"
                            />
                        </q-item-section>
                        <q-item-section>
                            <q-item-label>{{ s.name }}</q-item-label>
                            <q-item-label caption>
                                {{ s.template_names.join(' → ') || 'empty' }}
                            </q-item-label>
                        </q-item-section>
                    </q-item>
                </q-list>
            </q-card-section>

            <q-card-section class="q-py-sm">
                <q-toggle
                    v-model="repeat"
                    dense
                    :disable="selectedIsSet"
                    label="Repeat for several weeks"
                />
                <div v-if="selectedIsSet" class="text-caption dora-text-muted q-mt-xs">
                    A rotating set works across weeks, so it always repeats.
                </div>
                <!-- The range appears in place. Both fields are week-of dates;
                     the server normalises whichever day you pick to its Monday,
                     the same way the URL's `?week=` does. -->
                <div v-if="repeat" class="apply-tpl__dates q-mt-sm">
                    <q-input v-model="startWeek" outlined dense type="date" label="From (week of)" />
                    <q-input v-model="endWeek" outlined dense type="date" label="To (week of)" />
                </div>
                <div class="text-caption dora-text-muted q-mt-xs">{{ explainer }}</div>
            </q-card-section>
        </template>

        <template #actions>
            <BaseButton variant="ghost" label="Cancel" v-close-popup />
            <q-space />
            <BaseButton
                v-if="templates.length || sets.length"
                variant="primary"
                :icon="ICONS.event_repeat"
                :label="repeat ? 'Apply to those weeks' : 'Apply to this week'"
                :loading="applying"
                :disable="!canApply"
                @click="onApply"
            />
        </template>
    </BaseDialog>
</template>

<script lang="ts" setup>
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import { ICONS } from 'src/style/icons';
    import { shiftDays } from 'src/helpers/weekDates';
    import type { MealPlanTemplateSummary } from 'src/models/mealPlanTemplate';
    import type { MealPlanTemplateSetSummary } from 'src/models/mealPlanTemplateSet';
    import { computed, ref, watch } from 'vue';

    const props = defineProps<{
        modelValue: boolean;
        templates: MealPlanTemplateSummary[];
        sets: MealPlanTemplateSetSummary[];
        /** The week the planner is looking at — the default target, and the
         *  start of the range when you ask it to repeat. */
        focusedMonday: string;
        applying: boolean;
    }>();

    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
        /** Apply one template to the focused week. */
        (e: 'applyTemplate', templateId: string): void;
        /** Apply a template or a set across a run of weeks. `source` is the
         *  `t:<id>` / `s:<id>` token the composable's recurring call takes, so
         *  this dialog doesn't invent a second encoding of the same choice. */
        (e: 'applyRecurring', payload: { source: string; start: string; end: string }): void;
    }>();

    /** `t:<id>` or `s:<id>`, matching `useMealPlanner.recurringSourceOptions`. */
    const selected = ref<string>('');
    const repeat = ref(false);
    const startWeek = ref('');
    const endWeek = ref('');

    const selectedIsSet = computed(() => selected.value.startsWith('s:'));

    // A set has no single-week meaning, so choosing one turns the range on (and
    // the toggle goes inert rather than silently disagreeing with the button).
    watch(selectedIsSet, (isSet) => { if (isSet) repeat.value = true; });

    const canApply = computed(() => {
        if (!selected.value) return false;
        if (!repeat.value) return true;
        return !!startWeek.value && !!endWeek.value && endWeek.value >= startWeek.value;
    });

    const explainer = computed(() => (
        repeat.value
            ? 'A set rotates through its templates week by week. Past days are skipped; up to 26 weeks.'
            : 'The template’s meals are added to the week you’re viewing. Past days are skipped.'
    ));

    function onApply() {
        if (!canApply.value) return;
        if (!repeat.value) {
            emit('applyTemplate', selected.value.slice(2));
            return;
        }
        emit('applyRecurring', {
            source: selected.value,
            start: startWeek.value,
            end: endWeek.value,
        });
    }

    // Re-seeded on each open: the focused week may have moved since last time,
    // and a stale selection would apply the wrong template on one tap.
    watch(() => props.modelValue, (open) => {
        if (!open) return;
        const first = props.templates[0];
        selected.value = first ? `t:${first.meal_plan_template_id}` : '';
        repeat.value = false;
        startWeek.value = props.focusedMonday;
        endWeek.value = shiftDays(props.focusedMonday, 28);
    });
</script>

<style scoped>
    /* Caps the list, not the dialog: the action row must stay reachable without
       scrolling past a long library. */
    .apply-tpl__list {
        max-height: 46vh;
        overflow-y: auto;
    }
    .apply-tpl__row--active {
        background: color-mix(in srgb, var(--brand-primary) 8%, transparent);
    }
    .apply-tpl__header {
        font-size: var(--font-size-xs);
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-secondary);
        padding-top: var(--space-2);
    }
    .apply-tpl__dates {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-2);
    }
    .apply-tpl__dates > * {
        flex: 1 1 10rem;
        min-width: 0;
    }
</style>
