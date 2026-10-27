/**
 * The admin settings pages' one load / draft / save / revert loop (finalisation
 * 13-R9; thirteen pages each hand-copied it). `draft` holds the editable copy
 * of the named fields; `save(patch, success)` sends only the fields that
 * changed, toasts through `useSettingsSave`, and on failure puts every draft
 * back to the saved value. The row itself lives in `appSettingsStore`, so the
 * pages share one GET per session.
 */
import { onMounted, reactive, ref } from 'vue';
import type { AppSettings } from 'src/services/api/appSettingsApiService';
import { useSettingsSave } from 'src/composables/useSettingsSave';
import { useAppSettingsStore } from 'src/stores/appSettingsStore';

export function useAppSettingDrafts<K extends keyof AppSettings>(
    initial: Pick<AppSettings, K>,
) {
    const store = useAppSettingsStore();
    const { notifySuccess, notifyError } = useSettingsSave();
    const keys = Object.keys(initial) as K[];
    const draft = reactive({ ...initial }) as Pick<AppSettings, K>;
    const ready = ref(false);
    const saving = ref(false);

    function savedValue<F extends K>(key: F): AppSettings[F] {
        return store.settings ? (store.settings[key] as AppSettings[F]) : initial[key];
    }

    /** Put every draft back to the saved row. */
    function reset(): void {
        for (const key of keys) draft[key] = savedValue(key);
    }

    async function load(): Promise<void> {
        try {
            await store.ensureLoadedAsync();
            reset();
        } catch (err) {
            notifyError("Couldn't load these settings.", err);
        } finally {
            ready.value = true;
        }
    }

    /** Save the fields in `patch` that differ from the saved row. Resolves
     *  true when saved (or nothing changed), false when the save failed and
     *  the drafts were reverted. `afterSave` refreshes whatever cache reads
     *  the setting (a `/health` policy, the feature flags). */
    async function save(
        patch: Partial<Pick<AppSettings, K>>,
        success: string,
        afterSave?: () => unknown,
    ): Promise<boolean> {
        const changed = (Object.keys(patch) as K[])
            .filter((key) => patch[key] !== savedValue(key));
        if (changed.length === 0) {
            reset();
            return true;
        }
        // Optimistic: a toggle shows its new state while the save is in flight.
        const command: Partial<Pick<AppSettings, K>> = {};
        for (const key of changed) {
            command[key] = patch[key];
            draft[key] = patch[key] as AppSettings[K];
        }
        saving.value = true;
        try {
            await store.saveAsync(command);
            reset();
            await afterSave?.();
            notifySuccess(success);
            return true;
        } catch (err) {
            reset();
            notifyError('Could not save your change.', err);
            return false;
        } finally {
            saving.value = false;
        }
    }

    onMounted(load);

    return { draft, ready, saving, save, reset, savedValue };
}
