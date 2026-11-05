<template>
    <!--
        The "Start cook mode?" confirm, shared by every surface that can start
        cooking (owner feedback 2026-08-19 — the cookbook skipped it while the
        recipe page showed it).

        Click-out / Esc just close (BaseDialog `v-model`); they never navigate.
        The decision about *whether* to show this at all is
        `helpers/cookModeGuard.needsCookGuard` — the caller checks that before
        opening, so this component only ever renders reasons it actually has.
    -->
    <BaseDialog
        v-model="open"
        title="Start cook mode?"
        closable
        card-style="min-width: 320px; max-width: 460px"
    >
        <!--
            Owner feedback 2026-09-01: *"Weird dot point pushing out one line
            of text and it doesn't tell you much. Update it to say 'you're
            missing these ingredients' and list them out in a vertical list."*

            The old body was a `<ul>` whose every branch produced exactly one
            long sentence, so the bullet marker sat there indenting a
            paragraph — a list of one — and the sentence it indented was a
            count with no names in it. Each reason now owns a headed block:
            a short line saying what the problem is, then the actual
            ingredients underneath, one per line. "Unsaved changes" has no
            list, so it stays a plain line.
        -->
        <q-card-section class="cmg__body">
            <div v-if="dirty" class="cmg__note">You have unsaved changes.</div>

            <div v-if="missingNames.length > 0" class="cmg__block">
                <p class="cmg__lead">You're missing these ingredients:</p>
                <ul class="cmg__names">
                    <li v-for="name in missingNames" :key="name">{{ name }}</li>
                </ul>
            </div>

            <div v-if="unlinkedNames.length > 0" class="cmg__block">
                <p class="cmg__lead">
                    These aren't linked to a pantry item, so Dora can't tell
                    whether you have them:
                </p>
                <ul class="cmg__names">
                    <li v-for="name in unlinkedNames" :key="name">{{ name }}</li>
                </ul>
            </div>

            <!-- Owner feedback 2026-08-24 — "missing" and "missing, but you
                 have something you could use instead" are different answers,
                 and this dialog is the last place the second one can change
                 the decision. Names, not a count: which ingredient it is, is
                 the whole point. -->
            <div v-if="substitutableNames.length > 0" class="cmg__subs">
                <q-icon :name="ICONS.swap_horiz" size="16px" />
                <span>
                    You have a substitute in stock for
                    {{ substitutableNames.join(', ') }}. You can swap it while cooking.
                </span>
            </div>
        </q-card-section>
        <template #actions>
            <BaseButton variant="ghost" label="Cancel" @click="open = false" />
            <!-- Only the editable surface can be dirty, so only it offers the
                 save fork; elsewhere there is one way forward. -->
            <BaseButton
                v-if="dirty"
                variant="ghost"
                label="Start without saving"
                @click="emit('start')"
            />
            <BaseButton
                v-if="dirty"
                variant="primary"
                label="Save & start"
                :loading="saving"
                @click="emit('save-and-start')"
            />
            <BaseButton
                v-else
                variant="primary"
                label="Start anyway"
                @click="emit('start')"
            />
        </template>
    </BaseDialog>
</template>

<script setup lang="ts">
    import { computed } from 'vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import { ICONS } from 'src/style/icons';
    import type { Recipe } from 'src/models/recipe';
    import {
        missingIngredientNames,
        unlinkedIngredientNames,
    } from 'src/helpers/cookModeGuard';

    const props = withDefaults(
        defineProps<{
            modelValue: boolean;
            recipe: Recipe | null;
            /** Unsaved edits on the surface that opened this. Editable surfaces
             *  only — the cookbook leaves it false. */
            dirty?: boolean;
            /** Spins the "Save & start" button while the caller's save is in
             *  flight. */
            saving?: boolean;
            /** Names of missing ingredients the cook already has a substitute
             *  for. Supplied by the recipe page, which is the only surface
             *  that loads substitutes; everywhere else leaves it empty. */
            substitutable?: string[];
        }>(),
        { dirty: false, saving: false, substitutable: () => [] },
    );

    const emit = defineEmits<{
        (e: 'update:modelValue', value: boolean): void;
        /** Proceed without saving (or, when not dirty, just proceed). */
        (e: 'start'): void;
        /** Save first, then proceed — the caller owns the save and decides
         *  whether it succeeded. */
        (e: 'save-and-start'): void;
    }>();

    const open = computed({
        get: () => props.modelValue,
        set: (value) => emit('update:modelValue', value),
    });

    const substitutableNames = computed(() => props.substitutable ?? []);

    /* The two lists the dialog is really about. `cookGuardReasons` still owns
     * the *decision* to open this at all (the callers check `needsCookGuard`);
     * what's rendered here is the same two conditions expressed as names,
     * which is what the owner asked to see. A recipe can be in both states at
     * once — some rows out of stock, others never linked — so both blocks are
     * independent `v-if`s rather than a switch. */
    const missingNames = computed(() => missingIngredientNames(props.recipe));
    const unlinkedNames = computed(() => unlinkedIngredientNames(props.recipe));
</script>

<style scoped lang="scss">
    .cmg__body {
        display: flex;
        flex-direction: column;
        gap: var(--space-4);
    }

    .cmg__note {
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
    }

    .cmg__lead {
        margin: 0 0 var(--space-2);
        color: var(--text-primary);
        font-size: var(--font-size-md);
    }

    /* A vertical list of names, not a bulleted paragraph: no markers, one
       name per line, each on the sunken ground so the block reads as data
       rather than prose. */
    .cmg__names {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 2px;
        max-height: 40vh;
        overflow-y: auto;
    }

    .cmg__names > li {
        padding: var(--space-2) var(--space-3);
        border-radius: var(--radius-sm);
        background: var(--surface-sunken);
        color: var(--text-primary);
        font-size: var(--font-size-sm);
        font-weight: 600;
    }

    .cmg__subs {
        display: flex;
        align-items: flex-start;
        gap: var(--space-2);
        /* The body is a flex column with its own gap now — the old margin
           would stack on top of it. */
        padding: var(--space-2) var(--space-3);
        border-radius: var(--radius-md);
        background: var(--semantic-positive-soft);
        color: var(--text-primary);
        font-size: var(--font-size-sm);
    }
</style>
