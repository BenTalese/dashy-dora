import { acceptHMRUpdate, defineStore } from 'pinia';
import AppSettingsApiService, {
    type AppSettings, type UpdateAppSettingsCommand,
} from 'src/services/api/appSettingsApiService';
import { readonly, ref } from 'vue';

const api = new AppSettingsApiService();

/** The install's admin settings row, loaded once per session and shared by the
 *  admin settings pages (finalisation 13-R9 / 13-R36: each page used to GET
 *  `/app-settings` on mount). Writes go through `saveAsync`, which keeps the
 *  cached row equal to what the server answered. */
export const useAppSettingsStore = defineStore('appSettings', () => {
    const settings = ref<AppSettings | null>(null);
    let inflight: Promise<void> | null = null;

    /** Concurrent first loads share one request; a failed load rejects and
     *  leaves the cache empty so the next page mount tries again. */
    const ensureLoadedAsync = (): Promise<void> => {
        if (settings.value) return Promise.resolve();
        inflight ??= api.getAsync()
            .then((row) => { settings.value = row; })
            .finally(() => { inflight = null; });
        return inflight;
    };

    /** The row, loading it first if needed. */
    const loadAsync = async (): Promise<AppSettings> => {
        await ensureLoadedAsync();
        return settings.value as AppSettings;
    };

    const saveAsync = async (command: UpdateAppSettingsCommand): Promise<AppSettings> => {
        const row = await api.updateAsync(command);
        settings.value = row;
        return row;
    };

    return { settings: readonly(settings), ensureLoadedAsync, loadAsync, saveAsync };
});

if (import.meta.hot) {
    import.meta.hot.accept(acceptHMRUpdate(useAppSettingsStore, import.meta.hot));
}
