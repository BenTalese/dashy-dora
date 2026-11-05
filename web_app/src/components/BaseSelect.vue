<template>
    <q-select
        ref="inner"
        v-bind="forwardedAttrs"
        :class="{ 'base-select--chips': rendersChips }"
        :model-value="modelValue"
        :options="options"
        :behavior="resolvedBehavior"
        :use-input="resolvedUseInput"
        :display-value="resolvedDisplayValue"
        :stack-label="emptyText ? true : undefined"
        :outlined="resolvedOutlined"
        :dense="dense"
        @update:model-value="(v: TValue) => emit('update:modelValue', v)"
    >
        <!-- Close affordance, dialog case only. Quasar's select dialog has no
             X and no Done — the only way out is the backdrop, which on a phone
             is a ~19px strip down each side and a ~54px band top and bottom
             (from its own `width: 90vw` / `max-height: calc(100vh - 108px)`).
             Those are real targets but awkward ones, and the bottom band is
             exactly where the browser toolbar and home indicator sit. With
             `use-input` the software keyboard takes most of what's left.
             That is the "difficult to tap out of" the owner reported. -->
        <template v-if="showsDialog" #before-options>
            <div class="base-select__dialog-bar row items-center justify-between">
                <span class="base-select__dialog-title">{{ dialogTitle }}</span>
                <BaseButton
                    variant="icon"
                    :icon="ICONS.close"
                    aria-label="Close"
                    v-close-popup
                />
            </div>
        </template>

        <!-- Everything else the call site passed through untouched. -->
        <template v-for="(_, name) in passthroughSlots" #[name]="slotProps">
            <slot :name="name" v-bind="slotProps ?? {}" />
        </template>
    </q-select>
</template>

<script setup lang="ts" generic="TValue">
    /*
     * The app's single-select control.
     *
     * Exists to make ONE decision in one place: menu or dialog on mobile.
     * Before this, all 72 `q-select`s left `behavior` unset, so every one took
     * Quasar's default — and that default is **user-agent based, not viewport
     * based** (`$q.platform.is.mobile`, QSelect.js `updatePreState`). So a
     * desktop browser dragged to phone width still gets an anchored menu while
     * a real phone gets a full-screen dialog; you cannot see the mobile
     * behaviour by resizing. Meanwhile the tri-state filters render their own
     * `q-menu` and are never dialogs. Hence the owner's report: "most dropdowns
     * open a modal, but our custom ones behave normally."
     *
     * The rule, rather than a blanket flip either way:
     *
     *   short, closed vocabulary  → `menu`   (Difficulty, Theme mode, cadence…)
     *   long list, or `use-input` → `default` (dialog on mobile, menu on desktop)
     *
     * Because the two cases genuinely differ. A five-option menu anchored to a
     * field is faster and less disruptive than a modal takeover — that's the
     * style the owner prefers, and there's no reason a phone should get a
     * full-screen surface to pick "Easy / Medium / Hard". But a long or
     * typeahead list needs the room and needs to survive the software keyboard,
     * which is exactly the problem the dialog exists to solve; forcing those
     * into an anchored menu on a phone would trade a mild annoyance for a
     * genuinely cramped one.
     */
    import { computed, ref, useAttrs, useSlots } from 'vue';
    import { type QSelect, useQuasar } from 'quasar';
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';
    import type { BaseSelectExposed } from 'src/components/baseSelectTypes';

    defineOptions({ inheritAttrs: false });

    const props = withDefaults(
        defineProps<{
            modelValue: TValue;
            /** Option rows. Deliberately `unknown` rather than `any`: the shape
             *  is the call site's business (string, {label,value}, a domain
             *  entity with `option-label`/`option-value` fns), and this
             *  component only ever reads `.length` off it. */
            options: readonly unknown[];
            /** Typeahead. Mirrors `q-select`'s own prop name because the
             *  behaviour rule has to read it — which means Vue consumes it and
             *  it is NO LONGER in `$attrs`, so it must be forwarded explicitly
             *  above. Missing that silently disabled the typeahead on the stock
             *  location picker while leaving it looking fine. */
            useInput?: boolean;
            /** Force a behaviour, escaping the rule. Use only with a reason. */
            behavior?: 'default' | 'menu' | 'dialog';
            /** Heading shown beside the close button in the dialog case. */
            dialogTitle?: string;
            /**
             * What the field reads when nothing is picked, e.g. "Any level".
             *
             * Owner feedback 2026-08-21: *"some filters have placeholder text
             * that turns into the title of the filter when input is added…
             * it then looks really odd with a filter value of 'Stocked'
             * selected and above it says 'Any level'."* Exactly right — those
             * call sites passed the empty-state sentence as `label`, and a
             * Quasar label doesn't disappear when a value arrives, it floats
             * up and becomes the field's *title*. So the field ended up
             * captioned with a statement that was no longer true.
             *
             * Passing this splits the two jobs properly: `label` is the field's
             * name and stays put (stacked, so it never sits over the value),
             * and this is the value shown while the model is empty.
             */
            emptyText?: string;
            /**
             * Dense by default — the app's standard field scale. `:dense="false"`
             * is for a form whose other fields are full-height `q-input`s
             * (a create/edit dialog), so the select doesn't sit a size smaller
             * than its neighbours (FU-675: migrate a form at one scale).
             */
            dense?: boolean;
        }>(),
        { useInput: false, dialogTitle: 'Choose an option', dense: true },
    );

    // Re-exposed so a typeahead that resets its own input text (the recipe
    // ingredient picker) can still reach QSelect's methods through a ref.
    const inner = ref<QSelect | null>(null);
    defineExpose<BaseSelectExposed>({
        updateInputValue: (value, noFilter) => inner.value?.updateInputValue(value, noFilter),
        showPopup: () => inner.value?.showPopup(),
        hidePopup: () => inner.value?.hidePopup(),
        focus: () => inner.value?.focus(),
        blur: () => inner.value?.blur(),
        validate: () => inner.value?.validate() ?? true,
        resetValidation: () => inner.value?.resetValidation(),
    });

    const emit = defineEmits<{ (e: 'update:modelValue', value: TValue): void }>();

    const $q = useQuasar();
    const slots = useSlots();

    /**
     * Where "short" stops. Quasar's mobile select dialog is capped at
     * `calc(100vh - 108px)`; at ~48px per option that's roughly 14 rows on a
     * 812px phone before it scrolls. An anchored menu has less room than that,
     * so the cutoff sits well below it: at 8 options a menu opens fully visible
     * next to the field on a phone, which is the whole point of preferring one.
     */
    const MENU_MAX_OPTIONS = 8;

    const resolvedBehavior = computed<'default' | 'menu' | 'dialog'>(() => {
        if (props.behavior) return props.behavior;
        // A typeahead list is unbounded by definition — its option count at
        // rest says nothing about what the user will filter it down from.
        if (props.useInput) return 'default';
        return props.options.length <= MENU_MAX_OPTIONS ? 'menu' : 'default';
    });

    /** True only when a dialog will actually render — mirrors QSelect's own
     *  condition so the close bar can't appear in a menu on desktop. */
    const showsDialog = computed(
        () => resolvedBehavior.value !== 'menu'
            && ($q.platform.is.mobile === true || resolvedBehavior.value === 'dialog'),
    );

    /**
     * Typeahead is desktop-only.
     *
     * Owner report 2026-08-20: *"all dropdown filters here open as mid-screen
     * modals except for location which opens at the top. Only difference I can
     * see is that the keyboard also opens up for this one."* Exactly that —
     * `use-input` makes QSelect's dialog auto-focus its input, the software
     * keyboard comes up, and Quasar pins the dialog to the top of the viewport
     * to keep it clear. One picker behaving unlike its four neighbours, for a
     * feature that isn't worth much on a phone anyway: filtering a location
     * list by thumb-typing is slower than scrolling it, and the keyboard eats
     * the room the list was given.
     *
     * The list is still a dialog rather than an anchored menu — `useInput`
     * keeps driving `resolvedBehavior` above, because a typeahead list is
     * unbounded by definition and needs the room. Only the input is dropped.
     */
    const resolvedUseInput = computed(
        () => props.useInput && $q.platform.is.mobile !== true,
    );

    /**
     * `$attrs`, minus the two props that only make sense alongside the
     * typeahead. `hide-selected` + `fill-input` are how a `use-input` select
     * shows the chosen option *in* its input; leave them on when the input is
     * gone (see `resolvedUseInput`) and the trigger renders blank with a
     * value selected. Both spellings are stripped — a template may pass
     * either, and Vue hands them through verbatim.
     */
    const attrs = useAttrs();

    // Quasar names the combobox from `label`; a select whose label is drawn
    // beside it (a SettingsRow, an inline-edit row) passes `aria-label`,
    // which QSelect lets override (FU-734). Flagged in dev when neither is.
    if (import.meta.env.DEV && !attrs.label && !attrs['aria-label'] && !attrs['aria-labelledby']) {
        console.warn('BaseSelect: pass label or aria-label to name the field.');
    }

    /** Outlined unless the call site picked another QField design. A
     *  `borderless` select is an inline, in-row control (the stock detail
     *  page's level / location / group pickers), where an outline would
     *  draw a box the surrounding row already draws. */
    const resolvedOutlined = computed(
        () => !['borderless', 'filled', 'standout'].some(
            (k) => k in attrs && attrs[k] !== false && attrs[k] !== undefined,
        ),
    );

    const forwardedAttrs = computed(() => {
        // A caller-supplied placeholder always wins over the empty-state one.
        const placeholder = attrs.placeholder ?? resolvedPlaceholder.value;
        if (resolvedUseInput.value) {
            return placeholder === undefined ? attrs : { ...attrs, placeholder };
        }
        const out: Record<string, unknown> = { ...attrs };
        for (const key of ['hide-selected', 'hideSelected', 'fill-input', 'fillInput']) {
            delete out[key];
        }
        return out;
    });

    /**
     * True when QSelect will render its selection as chips rather than text.
     *
     * Read off `$attrs` because both flags belong to QSelect, not to us — the
     * call site writes `multiple use-chips` and Vue hands them straight
     * through. Either spelling of the boolean may arrive, and an attribute
     * written with no value comes through as `''`, so anything but an explicit
     * `false` counts as set.
     */
    const rendersChips = computed(() => {
        const on = (...keys: string[]) => keys.some(
            (k) => k in attrs && attrs[k] !== false && attrs[k] !== undefined,
        );
        return on('multiple') && on('use-chips', 'useChips');
    });

    /** Nothing picked — `null`, `undefined`, `''`, or an empty multi-select. */
    const isEmpty = computed(() => {
        const v = props.modelValue;
        if (Array.isArray(v)) return v.length === 0;
        return v === null || v === undefined || v === '';
    });

    /**
     * Empty state, two renderings — because QSelect has two.
     *
     * A `use-input` select renders a real <input> and (with `hide-selected`)
     * returns NOTHING from its selection renderer, so `display-value` is dead
     * there: the field would just come out blank. The input's own
     * `placeholder` is the right channel — and it reaches the input, because
     * QSelect spreads `$attrs` onto it (`getInput`). Every other select has no
     * input, so `display-value` is the only channel it has.
     */
    const resolvedDisplayValue = computed(
        () => (props.emptyText && isEmpty.value && !resolvedUseInput.value
            ? props.emptyText
            : undefined),
    );
    const resolvedPlaceholder = computed(
        () => (props.emptyText && isEmpty.value && resolvedUseInput.value
            ? props.emptyText
            : undefined),
    );

    /** Forward every slot the caller gave us EXCEPT the one we own.
     *
     *  `selected-item` is also withheld while the empty text is showing:
     *  QSelect prefers that slot over `display-value` whenever the slot
     *  exists, and with nothing selected it renders no rows — so the field
     *  would come out blank rather than saying "Any level". Withholding it
     *  costs nothing, because a `selected-item` slot has nothing to render
     *  when there is no selection. */
    const passthroughSlots = computed(() => {
        const out: Record<string, true> = {};
        for (const name of Object.keys(slots)) {
            if (name === 'before-options') continue;
            if (name === 'selected-item' && resolvedDisplayValue.value !== undefined) continue;
            out[name] = true;
        }
        return out;
    });
</script>

<style scoped lang="scss">
    /* Selected text truncates, never wraps.
       Owner feedback 2026-08-21: *"if text is too large it [should] trail off
       'like this…'. Definitely visible on mobile for stock level filter with a
       value selected — the text comes out of the input area because of word
       wrap."* QSelect's value div is a flex item with no width constraint of
       its own, so a long option wrapped to a second line inside a fixed-height
       control and spilled out of it. Applied here rather than per page so
       every select in the app truncates the same way.
       No `display` override: QSelect's value spans are already flex items of
       `.q-field__native` and so are blockified, which is what makes
       `text-overflow` apply. Setting it explicitly would flatten a
       `#selected-item` slot that renders a `.row` (the level filter's colour
       dot + name). A `use-input` typeahead's real <input> is a sibling and is
       untouched — it scrolls its own overflow and must keep doing so. */
    :deep(.q-field__native) {
        flex-wrap: nowrap;
    }
    :deep(.q-field__native > span) {
        min-width: 0;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
    }

    /* …except when the selection IS chips, where "never wraps" is the wrong
       rule and was quietly costing the page its width. A chip select's
       selections are `.q-chip`s, not the bare spans the rule above is written
       for: they can't ellipsis, so `nowrap` just ran them off the side of the
       field. Nothing clipped them, so the row kept growing, and the page
       scrolled sideways — reported on the recipe method's Tools field
       (2026-08-31: *"adding lots of tools … infinitely pushes the horizontal
       space of the page"*), but true of every chip select in the app: dietary
       tags, the step-links dialog, the reports and audit-log filters.

       Chips stack instead, and the control gives up its fixed dense height so
       the field grows downwards to hold them. `min-height` keeps an empty or
       one-row field exactly as tall as every other dense field beside it. */
    .base-select--chips :deep(.q-field__native) {
        flex-wrap: wrap;
    }
    .base-select--chips :deep(.q-field__control) {
        height: auto;
        min-height: 40px;
    }
    /* D-004 on touch (R-085 / FU-877). */
    @media (pointer: coarse) {
        .base-select--chips :deep(.q-field__control) {
            min-height: 44px;
        }
    }

    .base-select__dialog-bar {
        position: sticky;
        top: 0;
        z-index: 1;
        padding: 4px 4px 4px 16px;
        background: var(--surface-elevated);
        /* R-060: `--border-subtle` is undeclared. A6: an in-panel separator is
           `--divider`, not a border token. */
        border-bottom: 1px solid var(--divider);
    }
    .base-select__dialog-title {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-secondary);
    }
</style>
