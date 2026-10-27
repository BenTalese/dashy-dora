<template>
    <!--
        The stock-level control from the overview row, extracted so every
        surface that asks "what level is this at?" asks it in the same shape
        (R-001). Owner feedback 2026-09-03: cook mode's finish modal was
        asking the same question with a segmented control, which read as a
        different concept entirely.

        A text-less coloured square + a menu of the household's levels, with
        the current one highlighted. Consumers own the write — this emits
        `select` and never touches a store, because the two callers persist
        differently (the overview row writes immediately, the finish modal
        batches on confirm).

        `variant="text"` (owner 2026-10-17, the bell's alert cards) swaps the
        square for a labelled secondary button that sits with the other text
        buttons on a card; the menu is the same one. Its visible label is its
        accessible name there (WCAG 2.5.3), so `label` is not applied.
    -->
    <BaseButton
        :variant="variant === 'text' ? 'secondary' : 'ghost'"
        :dense="variant !== 'text'"
        :label="variant === 'text' ? textLabel : undefined"
        :class="variant === 'text' ? undefined : [
            'stock-level-picker',
            levelButtonClass,
            { 'stock-level-picker--uncertain': uncertain },
        ]"
        :style="variant === 'text' ? undefined : levelButtonStyle"
        :aria-label="variant === 'text' ? undefined : ariaLabel"
        @click.stop
    >
        <BaseTooltip>
            {{ levelName ? `Level: ${levelName}` : 'Set stock level' }}
            <template v-if="uncertain && uncertaintyTooltip">
                <br />
                {{ uncertaintyTooltip }}
            </template>
        </BaseTooltip>
        <q-menu auto-close transition-show="jump-down" transition-hide="jump-up">
            <!-- Width lives in the stylesheet, not an inline `min-width:
                 200px`: the owner's report was that these options read
                 *narrow* on a phone, and an inline style can't be widened by a
                 media query (it outranks one). -->
            <q-list dense class="stock-level-picker__menu">
                <!-- Consumers with something to say about *why* the level
                     might be wrong (the overview row's belief / stocktake
                     hints) fill this; everyone else gets the plain caption. -->
                <slot name="menu-header">
                    <q-item-label header>Set level</q-item-label>
                </slot>
                <q-item
                    v-for="level in stockLevels"
                    :key="level.stock_level_id"
                    clickable
                    v-close-popup
                    :active="level.stock_level_id === levelId"
                    active-class="stock-level-picker__option--active"
                    @click.stop="emit('select', level.stock_level_id)"
                >
                    <q-item-section avatar>
                        <q-avatar
                            :color="colourForSequence(level.sequence) ?? undefined"
                            :class="{ 'dora-bg-neutral': !colourForSequence(level.sequence) }"
                            size="14px"
                        />
                    </q-item-section>
                    <!-- Current level is shown by highlighting the whole row
                         (the `active` + `active-class` pattern used by the
                         settings nav and the shopping-list rail), not a
                         trailing tick. -->
                    <q-item-section>{{ level.name }}</q-item-section>
                </q-item>
            </q-list>
        </q-menu>
    </BaseButton>
</template>

<script setup lang="ts">
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { computed } from 'vue';
    import { storeToRefs } from 'pinia';
    import BaseButton from 'src/components/BaseButton.vue';
    import { colourForSequence } from 'src/helpers/stockLevelLogic';
    import { useStockLevelStore } from 'src/stores/stockLevelStore';

    const props = withDefaults(
        defineProps<{
            /** The level the item currently sits on. */
            levelId?: string | null | undefined;
            /** Pre-resolved sequence, when the caller already carries it on its
             *  row DTO. Falls back to a lookup by `levelId`. */
            sequence?: number | null | undefined;
            /** Draw the "this might be wrong" ring. */
            uncertain?: boolean;
            /** Second tooltip line explaining the ring. */
            uncertaintyTooltip?: string | null | undefined;
            /** Overrides the derived aria-label (the overview row folds its
             *  uncertainty reason in). */
            label?: string | undefined;
            /** `swatch` — the coloured square (default); `text` — a labelled
             *  button naming the current level. */
            variant?: 'swatch' | 'text';
        }>(),
        { uncertain: false, variant: 'swatch' },
    );

    const emit = defineEmits<{ (e: 'select', stockLevelId: string): void }>();

    const stockLevelStore = useStockLevelStore();
    const { stockLevels } = storeToRefs(stockLevelStore);

    const levelName = computed(() => {
        if (!props.levelId) return '';
        return stockLevelStore.levelById.get(props.levelId ?? '')?.name ?? '';
    });

    const levelSequence = computed<number | null>(() => {
        if (typeof props.sequence === 'number') return props.sequence;
        if (!props.levelId) return null;
        return stockLevelStore.levelById.get(props.levelId ?? '')?.sequence ?? null;
    });

    const textLabel = computed(() => (levelName.value ? `Level: ${levelName.value}` : 'Set level'));

    const ariaLabel = computed(
        () => props.label ?? `Stock level: ${levelName.value || 'unset'}`,
    );

    // The button is text-less but coloured by the stock level. Saturated
    // branches (well/sufficient/low) ride Quasar's brand semantics via the
    // `bg-{positive|warning|negative}` utility class — those are theme-
    // tokenised. The neutral / out-of-stock branch routes through
    // `dora-bg-neutral` per R-002 (a `bg-grey-5` literal broke dark themes).
    const levelButtonClass = computed<string>(() => {
        const seq = levelSequence.value;
        if (seq === null) return '';
        const colour = colourForSequence(seq);
        return colour ? `bg-${colour}` : 'dora-bg-neutral';
    });

    const levelButtonStyle = computed(() => {
        // Empty-level fallback — dashed outline + page surface so the button
        // reads as "unset" without competing with a colour. When the level is
        // ALSO uncertain the box drops this border and lets the offset
        // uncertainty ring speak alone: two dashed edges 2px apart read as one
        // muddy smudge at 32px, and the ring is the louder of the two signals.
        if (levelSequence.value === null) {
            const surface = { background: 'var(--surface-component)' };
            if (props.uncertain) return surface;
            return {
                ...surface,
                border: '1px dashed color-mix(in srgb, var(--text-primary) 24%, transparent)',
            };
        }
        return {};
    });
</script>

<style scoped lang="scss">
    /* Big text-less level button — colour comes from `levelButtonStyle`
       (Quasar palette CSS variables), so light/dark themes inherit it. */
    .stock-level-picker {
        width: 32px;
        height: 32px;
        min-width: 32px;
        min-height: 32px;
        border-radius: var(--radius-sm, 4px);
        padding: 0;
        position: relative;
    }

    /* R-085/D-004 carve-out — this control stays 32px on touch.

       The 2026-09-05 tap-target sweep read the owner's *"bit thicker/bigger
       for mobile"* as being about this button and grew it to the 44px floor.
       Wrong half: the report was about the **menu rows** it opens, which were
       32px and are now 44 (`app.scss`) beside a wider menu (below). Reverted
       2026-09-09 on the owner's correction.

       It is also the one place in that sweep where the floor cost something
       real. The chip is a colour block, so its hit area *is* its visual
       weight — 44px turned a quiet status marker into the loudest element in
       a stock row, on the surface where those rows are densest. The usual
       escape (hold the size, expand the target with a pseudo-element) is
       unavailable: `::after` carries the uncertainty ring below and Quasar's
       QBtn owns `::before`. Since the thing being tapped opens a menu whose
       own rows now clear the floor comfortably, the mis-tap cost is a menu
       you dismiss, and that is the trade being taken deliberately. */

    /* The menu's own width. 200px is the desktop figure this list has always
       used and it stays there; on touch it widens, which is the "narrow" half
       of the owner's report (the row *height* half is handled globally in
       `app.scss`). 260px keeps a level name like "Getting low" on one line
       with the colour dot beside it, and still leaves margin either side of a
       360px phone. */
    .stock-level-picker__menu {
        min-width: 200px;
    }
    @media (pointer: coarse) {
        .stock-level-picker__menu {
            min-width: 260px;
        }
    }

    /* ── One uncertainty marker (D-5) ───────────────────────────────────────
       Replaces BOTH the stocktake pulse and the belief ring. Dashed, so it
       never competes with the level's own colour, and with no animation at
       any preference — there is nothing to honour under
       `prefers-reduced-motion` because nothing moves.

       2026-08-22 feedback: "it's not obvious enough — keep the dashed style
       but put it around the box with a tiny gap, like the old Dora-thinks
       ring". So the dashes sit on an `::after` ring 2px outside the box,
       which is the geometry of the retired belief ring drawn in dashes.

       Why `::after` and not `outline`/`box-shadow`:
         • `outline` is spoken for — A6 makes the focus ring mandatory, and
           one element cannot carry two.
         • `box-shadow` cannot be dashed at all; that is what forced the old
           ring to be solid.
         • Quasar's QBtn already uses `:before` for its elevation shadow
           (`quasar/src/components/btn/QBtn.sass`); `:after` is free.
       The ring bleeds 5px past the button. The stock row is 56px painted with
       6px of vertical body padding, so it clears `overflow: hidden`; on phones
       the body gap tightens to 8px, so the media query below drops the dashes
       to 2px to keep daylight between the ring and the name.

       Dash:gap RATIO is still not settable — the browser derives both from
       the border width (Chrome: dash ≈ 2× width, gap ≈ 1× width). A gradient
       overlay can do it, was built, measured and reverted on the owner's
       call. Reopen that trade only if the proportions are genuinely wrong. */
    .stock-level-picker--uncertain::after {
        content: '';
        position: absolute;
        inset: -5px;
        border: 3px dashed color-mix(in srgb, var(--text-primary) 65%, transparent);
        border-radius: calc(var(--radius-sm, 4px) + 5px);
        pointer-events: none;
    }
    @media (max-width: 599px) {
        .stock-level-picker--uncertain::after {
            inset: -4px;
            border-width: 2px;
            border-radius: calc(var(--radius-sm, 4px) + 4px);
        }
    }

    /* Current level = highlighted row, matching the `active-class` pattern
       used by the settings nav + shopping-list rail. `:deep` because q-menu
       teleports its list to body. */
    :deep(.stock-level-picker__option--active) {
        background: var(--surface-sunken);
        font-weight: 600;
        color: var(--text-primary);
    }
</style>
