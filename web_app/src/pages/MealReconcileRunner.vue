<template>
    <RunnerShell close-to="/meal-plans" close-label="Close reconcile" help-topic="Reconcile past meals">
        <template #topbar>
            <q-linear-progress
                v-if="hasEntry"
                :value="progress"
                rounded
                size="6px"
                color="primary"
                class="col q-mx-md"
            />
            <div v-else class="col" />
            <div v-if="hasEntry" class="text-caption dora-text-muted-3 q-mr-sm">
                {{ resolvedCount }} / {{ initialCount }}
            </div>
        </template>

        <!-- ── Loading ─────────────────────────────────────────────── -->
        <div v-if="loading" class="runner-card-wrap">
            <q-spinner color="primary" size="42px" />
        </div>

        <!-- ── Empty queue (matches StocktakeRunner's empty state) ─── -->
        <div v-else-if="entries.length === 0 && index === 0" class="runner-card-wrap">
            <q-card class="runner-card" flat>
                <q-card-section class="text-center q-pt-lg">
                    <q-icon :name="ICONS.check_circle" color="positive" size="64px" />
                    <div class="text-h5 q-mt-sm">Nothing to reconcile.</div>
                    <div class="text-caption dora-text-muted-7 q-mt-xs">
                        Every past-day meal has been confirmed. Dora will
                        surface entries here as days roll past.
                    </div>
                </q-card-section>
                <q-card-actions align="center" class="q-pb-lg">
                    <BaseButton label="Back to Meal plans" :to="'/meal-plans'" />
                </q-card-actions>
            </q-card>
        </div>

        <!-- ── Current entry card ──────────────────────────────────── -->
        <div v-else-if="current" class="runner-card-wrap">
            <q-card class="runner-card" flat>
                <q-card-section class="text-center">
                    <div class="text-caption dora-text-muted-5 q-mb-xs">
                        {{ formatScheduledFor(current.scheduled_for) }} · {{ current.slot }}
                    </div>
                    <div class="text-h5">{{ current.recipe.name }}</div>
                    <div class="text-caption dora-text-muted-7 q-mt-xs">
                        Planned {{ current.planned_servings }} serving{{ current.planned_servings === 1 ? '' : 's' }}
                    </div>
                </q-card-section>

                <q-card-section>
                    <!-- Primary: Cooked (as planned). Big button. -->
                    <BaseButton
                        variant="primary"
                        class="full-width q-mb-sm"
                        :icon="ICONS.check_circle"
                        label="Cooked"
                        :disable="busy"
                        @click="onVerb('cooked')"
                    />

                    <!-- Secondary: Cooked (different portions) / Cooked later.
                         Both drop an inline field before submitting. -->
                    <div class="row q-gutter-sm q-mb-sm">
                        <BaseButton
                            variant="secondary"
                            class="col"
                            label="Different portions"
                            :disable="busy"
                            @click="adjustOpen = true"
                        />
                        <BaseButton
                            variant="secondary"
                            class="col"
                            label="Cooked later"
                            :disable="busy"
                            @click="laterOpen = true"
                        />
                    </div>

                    <!-- Tertiary: Didn't cook. Reverses any drain. -->
                    <BaseButton
                        variant="danger-ghost"
                        class="full-width q-mb-md"
                        label="Didn't cook"
                        :disable="busy"
                        @click="onVerb('not_cooked')"
                    />

                    <!-- Small: Skip for now (session defer). -->
                    <div class="row justify-center">
                        <BaseButton
                            variant="ghost"
                            label="Skip for now"
                            :disable="busy"
                            @click="onVerb('skip')"
                        />
                    </div>
                </q-card-section>
            </q-card>
        </div>

        <!-- ── Session-complete card ───────────────────────────────── -->
        <div v-else class="runner-card-wrap">
            <q-card class="runner-card" flat>
                <q-card-section class="text-center">
                    <q-icon :name="ICONS.check_circle" color="positive" size="64px" />
                    <div class="text-h5 q-mt-sm">Reconcile complete</div>
                    <div class="runner-summary">
                        <div class="runner-summary__row">
                            <span class="runner-summary__count">{{ summary.cooked }}</span>
                            <span class="dora-text-muted-7">cooked</span>
                        </div>
                        <div class="runner-summary__row">
                            <span class="runner-summary__count">{{ summary.adjusted }}</span>
                            <span class="dora-text-muted-7">adjusted</span>
                        </div>
                        <div class="runner-summary__row">
                            <span class="runner-summary__count">{{ summary.notCooked }}</span>
                            <span class="dora-text-muted-7">not cooked</span>
                        </div>
                        <div class="runner-summary__row">
                            <span class="runner-summary__count">{{ summary.cookedLater }}</span>
                            <span class="dora-text-muted-7">cooked later</span>
                        </div>
                        <div class="runner-summary__row">
                            <span class="runner-summary__count">{{ summary.skipped }}</span>
                            <span class="dora-text-muted-7">still open</span>
                        </div>
                    </div>
                </q-card-section>
                <q-card-actions align="center" class="q-pb-md">
                    <BaseButton label="Done" :to="'/'" />
                </q-card-actions>
            </q-card>
        </div>

        <!-- ── Different portions dialog ───────────────────────────── -->
        <BaseDialog v-model="adjustOpen" title="How many did you actually make?" closable card-style="min-width: 320px">
            <q-card-section>
                <q-input
                    v-model.number="adjustServings"
                    type="number"
                    min="0"
                    max="999"
                    outlined
                    dense
                    autofocus
                    label="Servings"
                />
            </q-card-section>
            <q-card-actions align="right">
                <BaseButton variant="ghost" label="Cancel" v-close-popup />
                <BaseButton
                    variant="primary"
                    label="Save"
                    :disable="!Number.isFinite(adjustServings) || adjustServings < 0"
                    @click="onVerbAdjust"
                />
            </q-card-actions>
        </BaseDialog>

        <!-- ── Cooked later dialog ─────────────────────────────────── -->
        <BaseDialog v-model="laterOpen" title="When did you cook it?" closable card-style="min-width: 320px">
            <q-card-section>
                <q-input
                    v-model="laterCookedOn"
                    type="date"
                    outlined
                    dense
                    autofocus
                    :max="todayIso"
                    label="Date cooked"
                />
            </q-card-section>
            <q-card-actions align="right">
                <BaseButton variant="ghost" label="Cancel" v-close-popup />
                <BaseButton
                    variant="primary"
                    label="Save"
                    :disable="!laterCookedOn"
                    @click="onVerbLater"
                />
            </q-card-actions>
        </BaseDialog>

    </RunnerShell>
</template>

<script lang="ts" setup>
    import RunnerShell from 'src/components/RunnerShell.vue';
    import { ICONS } from 'src/style/icons';
    import { formatDate as formatLocaleDate } from 'src/composables/useDateFormat';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import { useQuasar } from 'quasar';
    import { computed, onMounted, reactive, ref } from 'vue';
    import { useReconcileQueue } from 'src/composables/useReconcileQueue';
    import { useMealPlanStore } from 'src/stores/mealPlanStore';
    import { localTodayIso } from 'src/helpers/weekDates';
    import type {
        ReconcileEntry,
        ReconcileVerb,
        ReconcileVerbCommand,
    } from 'src/services/api/mealPlanApiService';
    import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';

    const $q = useQuasar();
    const { entries, loading, submitVerb, reload } = useReconcileQueue();


    const index = ref(0);
    const busy = ref(false);
    const adjustOpen = ref(false);
    const adjustServings = ref<number>(0);
    const laterOpen = ref(false);
    const laterCookedOn = ref<string>('');

    /** Snapshot the initial queue length so the progress bar's
     *  denominator is stable across the session (each resolved verb
     *  removes an entry from the live list). */
    const initialCount = ref(0);
    const resolvedCount = computed(() => Math.min(index.value, initialCount.value));
    const hasEntry = computed(() => index.value < initialCount.value);
    const progress = computed(() =>
        initialCount.value === 0 ? 0 : resolvedCount.value / initialCount.value,
    );

    /** Because `submitVerb` removes the resolved entry from `entries`,
     *  the "current" item is always `entries[0]` while there's still
     *  something in the queue. `index` is a monotonic session counter
     *  for the progress bar; `current` is what's on screen. */
    const current = computed<ReconcileEntry | null>(() => entries.value[0] ?? null);

    const summary = reactive({
        cooked: 0,
        adjusted: 0,
        notCooked: 0,
        cookedLater: 0,
        skipped: 0,
    });

    // Household today from the server (R-021), local date until it loads —
    // never `toISOString()`, which is the UTC date and made today un-pickable
    // east of Greenwich in the evening (finalisation 02-R35).
    const mealPlanStore = useMealPlanStore();
    if (!mealPlanStore.today) void mealPlanStore.getTodayAsync();
    const todayIso = computed(() => mealPlanStore.today ?? localTodayIso());

    function formatScheduledFor(iso: string): string {
        // "Mon 7 Jul" — same shape stocktake uses inline.
        return formatLocaleDate(iso, {
            weekday: 'short', day: 'numeric', month: 'short',
        });
    }

    onMounted(async () => {
        await reload();
        initialCount.value = entries.value.length;
    });

    async function onVerb(verb: ReconcileVerb): Promise<void> {
        const c = current.value;
        if (!c || busy.value) return;
        await runVerb(c.entry_id, { verb });
    }

    async function onVerbAdjust(): Promise<void> {
        const c = current.value;
        if (!c || busy.value) return;
        adjustOpen.value = false;
        await runVerb(c.entry_id, {
            verb: 'cooked_adjusted',
            actual_servings: adjustServings.value,
        });
        adjustServings.value = 0;
    }

    async function onVerbLater(): Promise<void> {
        const c = current.value;
        if (!c || busy.value) return;
        laterOpen.value = false;
        await runVerb(c.entry_id, {
            verb: 'cooked_later',
            cooked_on: laterCookedOn.value,
        });
        laterCookedOn.value = '';
    }

    async function runVerb(entryId: string, command: ReconcileVerbCommand): Promise<void> {
        busy.value = true;
        try {
            await submitVerb(entryId, command);
            // Book the outcome for the completion-screen recap.
            if (command.verb === 'cooked') summary.cooked += 1;
            else if (command.verb === 'cooked_adjusted') summary.adjusted += 1;
            else if (command.verb === 'not_cooked') summary.notCooked += 1;
            else if (command.verb === 'cooked_later') summary.cookedLater += 1;
            else if (command.verb === 'skip') summary.skipped += 1;
            index.value += 1;
        } catch (err: unknown) {
            $q.notify({
                type: 'negative',
                message: 'Could not save that.',
                caption: toastCaption(err),
                position: 'bottom',
            });
        } finally {
            busy.value = false;
        }
    }
</script>

<style scoped lang="scss">
    // The shell and its brand-primary strip live in RunnerShell.vue.
    .runner-card-wrap {
        flex: 1 1 auto;
        display: flex;
        justify-content: center;
        align-items: flex-start;
        padding: 1.5rem 1rem;
    }

    .runner-card {
        width: min(28rem, 100%);
        background: var(--surface-component);
        border-radius: var(--radius-lg);
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
    }

    .runner-summary {
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
        margin-top: 1rem;
        align-items: center;
    }

    .runner-summary__row {
        display: flex;
        gap: 0.5rem;
        align-items: baseline;
    }

    .runner-summary__count {
        font-variant-numeric: tabular-nums;
        font-weight: 600;
        min-width: 1.5rem;
        text-align: right;
    }

</style>
