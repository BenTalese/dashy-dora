<template>
    <!--
        FU-227 chunk 3 — the shared "Your prices" entry form (F1 / R-001).
        One component, used by:
          • the stock-overview row "Log a price" button (shelf-price mode)
          • the stock-item detail YourPricesWidget [Log a price] action
          • (chunk 5) the shopping-line at /finish (harvest mode)

        Modes (§6a):
          • shelf  → "I SAW $X for size Y at maybe store Z". The form is
                     three inputs (price, size, unit) over two optional ones
                     (pack count, store). Fill pack count for a multipack
                     (4×125g) — "Size" then reads "Size each" and the form
                     computes total_measure = count × size for the server.
          • harvest → "I BOUGHT N for total $X". Used at /finish to map a
                      line into an observation. Count is read from the line.

        Validation: unit must be on the supported price list
        (volume / mass / count) from `generated/units_table` — kJ, °C, mm
        are rejected (they're recipe-side). The picker groups by dimension
        per B3 (flat global list, last-time prefill via the F2 prefill
        prop — NO smart per-item defaults ever).
    -->
    <div class="dora-price-entry q-gutter-sm">
        <!-- Where the seeded numbers came from, and when. The date arrived
             2026-09-17: "from your last log" reads the same whether that log
             was on Tuesday or in March, and those are different situations —
             one you confirm, the other you re-check. -->
        <div v-if="prefill?.source_label" class="text-caption dora-text-muted q-mb-xs">
            Prefilled {{ prefill.source_label }}<template v-if="prefill.observed_at">
                · {{ formatRelativeDay(prefill.observed_at) }}</template>
        </div>

        <div class="row q-gutter-sm items-start">
            <MoneyInput
                v-model="totalPrice"
                class="col"
                :label="mode === 'harvest' ? 'Total paid' : 'Price'"
                :rules="[(v: number | null) => (v != null && v > 0) || 'Required']"
                hide-bottom-space
            />
            <q-input
                v-if="mode === 'shelf'"
                v-model.number="perPackSize"
                dense outlined type="number"
                class="col"
                :label="isMultipack ? 'Size each' : 'Size'"
                :rules="[(v) => (v != null && v > 0) || 'Required']"
                hide-bottom-space
            />
            <q-select
                v-model="unit"
                :options="unitOptions"
                dense outlined emit-value map-options
                class="col"
                label="Unit"
                :rules="[(v) => !!v || 'Required']"
                hide-bottom-space
            />
        </div>

        <!-- Pack count + store, one row of two equal halves.
             2026-08-21 feedback: pack count was behind an "Add pack count
             (multipack)" disclosure and is now always visible. The disclosure
             cost a tap, hid a field people were looking for, and — because it
             swapped a button for an input — made the form change height and
             re-flow the moment you engaged with it. Leaving it empty means
             exactly what the collapsed state meant, so nothing is lost.
             Sizing (same feedback): the three fields above are `col` thirds of
             the full width; these two are `col` halves of it, so every row in
             the form starts and ends on the same two edges and the two fields
             here match each other. `hide-bottom-space` on both, like the row
             above, so the rows keep one height. -->
        <div v-if="mode === 'shelf'" class="row q-gutter-sm items-start">
            <q-input
                v-model.number="packCount"
                dense outlined type="number"
                class="col"
                label="Pack count (optional)"
                :rules="[(v) => isBlank(v) || v > 0 || 'Must be > 0']"
                hide-bottom-space
            />
            <q-select
                v-if="storeOptions.length > 0"
                v-model="storeId"
                :options="storeOptions"
                dense outlined emit-value map-options clearable
                class="col"
                label="Store (optional)"
                hide-bottom-space
            />
        </div>

        <!-- Live preview: $X.XX per Y. For multipacks, also surface the
             total ("4 × 125g = 500g total") so the user can sanity-check. -->
        <div
            v-if="perUnitPreview"
            class="dora-bg-sunken dora-text-secondary q-pa-sm rounded-borders text-body2"
        >
            ≈ <strong>{{ perUnitPreview.amount }}</strong> per {{ perUnitPreview.unit }}
            <span v-if="isMultipack" class="dora-text-muted">
                · {{ packCount }} × {{ perPackSize }}{{ unit }} = {{ totalMeasureDisplay }}{{ unit }} total
            </span>
        </div>

        <div class="row justify-end q-gutter-sm q-mt-sm">
            <BaseButton
                variant="ghost"
                label="Cancel"
                @click="onCancel"
            />
            <BaseButton
                variant="primary"
                :icon="ICONS.add"
                label="Log"
                :disable="!canSubmit || busy"
                @click="onSubmit"
            />
        </div>
    </div>
</template>

<script setup lang="ts">
    import { computed, ref, watch } from 'vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import MoneyInput from 'src/components/MoneyInput.vue';
    import { formatMoney } from 'src/composables/useMoney';
    import { ICONS } from 'src/style/icons';
    import { SUPPORTED_PRICE_UNITS } from 'src/generated/units_table';
    import { useMeasurementSystem } from 'src/composables/useMeasurementSystem';
    import { quoteUnitPrice } from 'src/helpers/unitPriceDisplay';
    import { formatRelativeDay } from 'src/composables/useDateFormat';
    import type { PriceEntryPrefill } from 'src/models/stockItemDetail';
    import type { Store } from 'src/models/store';

    type Mode = 'shelf' | 'harvest';

    const props = withDefaults(
        defineProps<{
            mode?: Mode | undefined;
            prefill?: PriceEntryPrefill | null | undefined;
            stores?: ReadonlyArray<Store> | undefined;
            busy?: boolean | undefined;
        }>(),
        { mode: 'shelf', prefill: null, stores: () => [], busy: false },
    );

    const emit = defineEmits<{
        (e: 'submit', value: {
            total_price: number;
            total_measure: number;
            unit: string;
            store_id: string | null;
            pack_count: number | null;
        }): void;
        (e: 'cancel'): void;
    }>();

    const totalPrice = ref<number | null>(props.prefill?.total_price ?? null);
    // `perPackSize` is the user-visible "Size" field. When multipack is set,
    // it represents the per-pack size and total_measure is derived as
    // `count × perPackSize` at submit time. When multipack is null, it IS
    // the total_measure. Keeping the field single-purpose in the UI but
    // dual-semantic under the hood matches the FU-227 §6a observation
    // that "shelf-price mode never carried a count concept" — an empty pack
    // count means one pack, so the common case is still one number.
    const perPackSize = ref<number | null>(props.prefill?.total_measure ?? null);
    const unit = ref<string>(props.prefill?.unit ?? '');
    const storeId = ref<string | null>(props.prefill?.store_id ?? null);
    const packCount = ref<number | null>(null);

    // Re-seed when the prefill arrives lazily (row-button case: fetched
    // after the dialog opens). Don't overwrite user typing — only seed if
    // the field is still at its initial empty state.
    watch(() => props.prefill, (p) => {
        if (!p) return;
        if (totalPrice.value == null) totalPrice.value = p.total_price;
        if (perPackSize.value == null) perPackSize.value = p.total_measure;
        if (!unit.value) unit.value = p.unit;
        if (storeId.value == null) storeId.value = p.store_id;
    });

    // A pack count of 1 (or empty) is a single pack — same thing the collapsed
    // disclosure used to mean before the field went always-visible.
    const isMultipack = computed(() => packCount.value != null && packCount.value > 1);

    // 2026-08-24 feedback: "pack count must be optional". It always was for the
    // server, but `v-model.number` hands back the empty *string* — not null —
    // once a typed value is cleared, so the `> 0` rule failed and the field
    // showed a validation error until you retyped a number. Normalising the
    // blank back to null is what makes clearing it mean "single pack" again;
    // `isBlank` keeps the rule itself honest for the tick before the watcher
    // runs.
    function isBlank(v: unknown): boolean {
        return v == null || v === '';
    }
    watch(packCount, (v) => {
        if (isBlank(v)) packCount.value = null;
    });

    // flat list grouped by dimension. The canonical strings come from
    // the generated table (single source of truth — chunk 1 / R-003), so
    // the picker never drifts from the server's accepted set.
    // Narrowed to the install's measurement system (owner feedback
    // 2026-08-27) — a metric household shouldn't be offered `lb` when logging
    // a shelf price, and a US one shouldn't be offered `kg`. Count units are
    // universal so `ea` / `dozen` / `pack` survive either way. The unit
    // already on the row is kept offered so editing an existing observation
    // can't silently re-unit it.
    const { offeredUnits, system: measurementSystem } = useMeasurementSystem();
    const unitOptions = computed(() => {
        const groups: Record<string, { canonical: string; label: string }[]> = {};
        for (const u of SUPPORTED_PRICE_UNITS) {
            if (!offeredUnits.value.has(u.canonical) && unit.value !== u.canonical) continue;
            (groups[u.dimension] ??= []).push({ canonical: u.canonical, label: u.label });
        }
        const order: string[] = ['volume', 'mass', 'count'];
        const out: { value: string; label: string }[] = [];
        for (const dim of order) {
            for (const opt of (groups[dim] ?? [])) {
                // 2026-08-21 feedback: the label used to read "volume — L".
                // The dimension is metadata about the option, and prefixing it
                // meant the field spent its width on the word "volume" and
                // clipped the one character that matters. Options stay grouped
                // by dimension through the `order` walk above, which is what
                // the prefix was really for.
                out.push({ value: opt.canonical, label: opt.label });
            }
        }
        return out;
    });

    const storeOptions = computed(() => (props.stores ?? []).map((s) => ({
        value: s.store_id,
        label: s.name,
    })));

    function totalMeasure(): number | null {
        if (perPackSize.value == null || perPackSize.value <= 0) return null;
        if (!isMultipack.value) return perPackSize.value;
        return (packCount.value as number) * perPackSize.value;
    }

    const totalMeasureDisplay = computed(() => {
        const v = totalMeasure();
        return v == null ? '' : v.toString();
    });

    const canSubmit = computed(() => {
        const tm = totalMeasure();
        return totalPrice.value != null && totalPrice.value > 0
            && tm != null && tm > 0
            && !!unit.value;
    });

    /** The live "≈ $X per Y" line, quoted the way a shelf label would be.
     *
     *  Owner feedback 2026-09-13: this used to divide straight through and
     *  render "≈ $0.01 per g" for a $3.50 500 g pack — a number that rounds to
     *  nothing in cents and a denominator no shop prices in. `quoteUnitPrice`
     *  applies the same convention the server uses everywhere else, so the
     *  preview now reads "≈ $0.70 per 100g" and matches what the observation
     *  will be quoted as once it is logged. */
    const perUnitPreview = computed(() => {
        if (!canSubmit.value) return null;
        const quoted = quoteUnitPrice(
            totalPrice.value as number,
            totalMeasure() as number,
            unit.value,
            measurementSystem.value,
        );
        if (quoted === null) return null;
        return { amount: formatMoney(quoted.amount), unit: quoted.unit };
    });

    function onSubmit() {
        if (!canSubmit.value) return;
        emit('submit', {
            total_price: totalPrice.value as number,
            total_measure: totalMeasure() as number,
            unit: unit.value,
            store_id: storeId.value,
            pack_count: isMultipack.value ? (packCount.value as number) : null,
        });
    }

    function onCancel() {
        emit('cancel');
    }
</script>
