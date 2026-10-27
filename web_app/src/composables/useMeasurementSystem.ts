import { computed, ref } from 'vue';

import {
    UNIT_SYSTEMS,
    UNIVERSAL_CANONICAL_UNITS,
    type MeasurementSystem,
} from 'src/generated/units_table';

/**
 * The install's measurement system — metric, imperial, or US customary.
 *
 * Owner feedback 2026-08-27: *"Locale and region settings should also include
 * units config, which then determines what units appear throughout the app …
 * anywhere this sort of dropdown appears, units should be driven by this
 * setting. For universal ones, e.g. 'dash', always include those."*
 *
 * Shaped exactly like `useMoney`, and for the same reasons:
 *   • it is **install-wide, not per-user** — a household measures in one
 *     system, the way it spends in one currency;
 *   • it arrives on `/api/health`, not `/app-settings`, because every session
 *     needs it on boot and only admins can read the settings payload;
 *   • the fetch is a module-level singleton, so N components asking produce
 *     one request and share one answer.
 *
 * Which units belong to which system is **not** decided here. That mapping is
 * `dora_api/domain/units.py`'s `UNIT_SYSTEMS`, mirrored into the generated
 * `units_table.ts` — R-003: the unit table has one source, and this is a
 * reader of it, not a second copy.
 */
const DEFAULT_SYSTEM: MeasurementSystem = 'metric';

const system = ref<MeasurementSystem>(DEFAULT_SYSTEM);
const loaded = ref(false);
let inflight: Promise<void> | null = null;

function isMeasurementSystem(value: unknown): value is MeasurementSystem {
    return value === 'metric' || value === 'imperial' || value === 'us';
}

function load(fresh = false): Promise<void> {
    if (!inflight) {
        // Imported lazily rather than at module scope. The health service pulls
        // in axios and Quasar, which touch `window` on import — and this
        // composable is now reached from pure unit-vocabulary code that a
        // node-environment test exercises without a DOM. The dynamic import
        // also means a page that never actually asks for the system never
        // loads the client at all.
        inflight = import('src/services/api/healthApiService')
            .then((mod) => {
                if (fresh) mod.invalidateHealthInfo();
                return new mod.default().getInfoAsync();
            })
            .then((info) => {
                const value = info.locale_policy?.measurement_system;
                if (isMeasurementSystem(value)) system.value = value;
            })
            .catch(() => {
                // Health probe failure ⇒ keep metric. Pickers still work; the
                // worst case is a US install briefly seeing metric units,
                // which is recoverable. Emptying every dropdown is not.
            })
            .finally(() => {
                loaded.value = true;
            });
    }
    return inflight;
}

/** Canonical units offered under `value`. Mirrors `units.units_for_system`. */
export function unitsForSystem(value: MeasurementSystem): Set<string> {
    // An unrecognised system resolves to metric rather than returning only the
    // universal units: a bad value in one setting must not empty every unit
    // dropdown in the app. Mirrors the same fallback in units_for_system().
    const resolved = isMeasurementSystem(value) ? value : DEFAULT_SYSTEM;
    const out = new Set<string>(UNIVERSAL_CANONICAL_UNITS);
    for (const [canonical, systems] of Object.entries(UNIT_SYSTEMS)) {
        if (systems.includes(resolved)) out.add(canonical);
    }
    return out;
}

export function useMeasurementSystem() {
    void load();
    return {
        /** The install's system. Reactive — starts at metric, corrected once
         *  `/api/health` answers. */
        system,
        loaded,
        /** Canonical units the current system offers, universal ones included. */
        offeredUnits: computed(() => unitsForSystem(system.value)),
        /** Force a re-read (used after Settings saves a new value). */
        reload: (): Promise<void> => {
            inflight = null;
            return load(true);
        },
    };
}

/** Test seam — reset the module singleton between specs. */
export function __resetMeasurementSystemForTests(): void {
    system.value = DEFAULT_SYSTEM;
    loaded.value = false;
    inflight = null;
}
