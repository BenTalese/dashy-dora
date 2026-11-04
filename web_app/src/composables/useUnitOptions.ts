import { computed, ref, watch } from 'vue';

import { useMeasurementSystem } from 'src/composables/useMeasurementSystem';
import { COOKING_WORD_UNITS, UNIT_TABLE, type Dimension } from 'src/generated/units_table';

/**
 * The app's unit picker vocabulary.
 *
 * `UNIT_TABLE` is generated from `dora_api/domain/units.py` and is mostly
 * synonyms — "tablespoon", "tablespoons", "tbsp" and "T" are four keys with one
 * canonical form. A dropdown built straight off it is 200 lines of the same
 * dozen units, so the list is de-duplicated by canonical form and the aliases
 * are used for *searching* instead: typing "tablespoons" finds `tbsp`.
 *
 * R-001/R-003 — this was written inside `SubstituteMetadataDialog` first; the
 * recipe ingredient editor needed the same list, so it lives here once rather
 * than being copied.
 *
 * Pass `dimensions` to narrow the vocabulary. The table spans six dimensions,
 * so the unnarrowed list offers `kJ`, `kcal`, `cm` and `ft` alongside `g` and
 * `ml` — harmless while the picker also took free text, actively wrong once
 * it's a closed list (owner feedback 2026-08-26). An ingredient is measured by
 * volume, mass or count; temperature/length/energy are recipe *metadata*, not
 * quantities.
 *
 * The list is **also** narrowed to the install's measurement system (owner
 * feedback 2026-08-27 — *"anywhere this sort of dropdown appears, units should
 * be driven by this setting"*). A metric household is not offered quarts, a US
 * one is not offered the 20 ml Australian tablespoon, and the universal cooking
 * amounts (`pinch`, `dash`, `smidgen`, `tsp`) plus the count units survive
 * every setting. Because this composable is the one place the picker
 * vocabulary is built (R-001/R-003), every dropdown in the app inherits that
 * for free — the ingredient row editor, the substitute dialog, and anything
 * added later.
 *
 * One deliberate exception, `includeValue`: a row that already holds an
 * off-system unit keeps it in its own dropdown. Recipes predate the setting
 * and an install can change its mind; silently blanking a saved `lb` because
 * the household went metric would be data loss dressed as a filter. The same
 * goes for a saved word the table has no entry for (`loaf`, FU-786): it stays
 * offered on its own row.
 *
 * `cookingWords` adds the parts and counted things recipes are written in
 * (`clove`, `sprig`, `rasher`, from `units.py` `COOKING_WORD_UNITS`). Only the
 * ingredient editor asks for them (FU-902).
 */
export interface UnitOption {
    label: string;
    value: string;
}

export function useUnitOptions(
    dimensions?: readonly Dimension[],
    /** A unit to keep offered even when the install's system excludes it —
     *  pass the row's current value so an existing entry is never dropped out
     *  from under the user. Reactive: pass a getter, not a snapshot. */
    includeValue?: () => string | null | undefined,
    options: { cookingWords?: boolean } = {},
) {
    const allowed = dimensions ? new Set<Dimension>(dimensions) : null;
    const { offeredUnits } = useMeasurementSystem();

    /** True when `canonical` is offered here: right dimension, and either in
     *  the install's system or the value this row already holds. */
    function isOffered(canonical: string, dimension: Dimension): boolean {
        if (allowed && !allowed.has(dimension)) return false;
        if (offeredUnits.value.has(canonical)) return true;
        const kept = includeValue?.();
        return !!kept && kept.trim().toLowerCase() === canonical.toLowerCase();
    }

    const allUnitOptions = computed<UnitOption[]>(() => {
        const seen = new Set<string>();
        const out: UnitOption[] = [];
        for (const def of Object.values(UNIT_TABLE)) {
            if (seen.has(def.canonical)) continue;
            if (!isOffered(def.canonical, def.dimension)) continue;
            seen.add(def.canonical);
            out.push({ label: def.canonical, value: def.canonical });
        }
        if (options.cookingWords && (!allowed || allowed.has('count'))) {
            for (const word of COOKING_WORD_UNITS) {
                if (seen.has(word)) continue;
                seen.add(word);
                out.push({ label: word, value: word });
            }
        }
        const kept = includeValue?.()?.trim();
        if (kept && !seen.has(kept) && !(kept.toLowerCase() in UNIT_TABLE)) {
            out.push({ label: kept, value: kept });
        }
        out.sort((a, b) => a.label.localeCompare(b.label));
        return out;
    });

    /** The filtered list a `q-select` renders. Starts as the full vocabulary. */
    const unitOptions = ref<UnitOption[]>([...allUnitOptions.value]);
    // The vocabulary is async: `/api/health` answers after first render, so
    // `allUnitOptions` changes underneath an already-seeded `unitOptions`.
    // Without this the very first dropdown opened on a US install shows metric
    // units until something else forces a re-filter.
    watch(allUnitOptions, (next) => {
        unitOptions.value = [...next];
    });

    /** `@filter` handler — matches against every alias, not just the canonical
     *  form, so a typed-out unit name finds its abbreviation. */
    function onUnitFilter(query: string, update: (cb: () => void) => void): void {
        update(() => {
            const q = query.trim().toLowerCase();
            if (!q) {
                unitOptions.value = [...allUnitOptions.value];
                return;
            }
            const matches = new Set<string>();
            for (const [alias, def] of Object.entries(UNIT_TABLE)) {
                if (!isOffered(def.canonical, def.dimension)) continue;
                if (alias.toLowerCase().includes(q) || def.canonical.toLowerCase().includes(q)) {
                    matches.add(def.canonical);
                }
            }
            unitOptions.value = allUnitOptions.value.filter(
                (o) => matches.has(o.value) || o.value.toLowerCase().includes(q),
            );
        });
    }

    return { allUnitOptions, unitOptions, onUnitFilter };
}
