// @vitest-environment jsdom
// The admin settings pages' shared save loop (13-R9): only changed fields are
// sent, and a failed save puts the draft back to the saved row.
import { createPinia, setActivePinia } from 'pinia';
import { mount, flushPromises } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { defineComponent } from 'vue';

const m = vi.hoisted(() => ({
    getAsync: vi.fn(),
    updateAsync: vi.fn(),
    notify: vi.fn(),
}));

vi.mock('src/services/api/appSettingsApiService', () => ({
    default: class {
        getAsync = m.getAsync;
        updateAsync = m.updateAsync;
    },
}));
vi.mock('quasar', () => ({ useQuasar: () => ({ notify: m.notify }) }));

import { useAppSettingDrafts } from 'src/composables/useAppSettingDrafts';

function host() {
    let api!: ReturnType<typeof useAppSettingDrafts<'money_enabled' | 'currency'>>;
    mount(defineComponent({
        setup() {
            api = useAppSettingDrafts({ money_enabled: false, currency: 'AUD' });
            return () => null;
        },
    }));
    return () => api;
}

describe('useAppSettingDrafts', () => {
    beforeEach(() => {
        setActivePinia(createPinia());
        vi.clearAllMocks();
        m.getAsync.mockResolvedValue({ money_enabled: true, currency: 'NZD' });
    });

    it('loads the saved row into the drafts', async () => {
        const api = host();
        await flushPromises();
        expect(api().ready.value).toBe(true);
        expect(api().draft.money_enabled).toBe(true);
        expect(api().draft.currency).toBe('NZD');
    });

    it('sends only the changed fields', async () => {
        m.updateAsync.mockResolvedValue({ money_enabled: false, currency: 'NZD' });
        const api = host();
        await flushPromises();

        const ok = await api().save({ money_enabled: false, currency: 'NZD' }, 'Saved.');

        expect(ok).toBe(true);
        expect(m.updateAsync).toHaveBeenCalledWith({ money_enabled: false });
        expect(api().draft.money_enabled).toBe(false);
    });

    it('reverts the draft when the save fails', async () => {
        m.updateAsync.mockRejectedValue(new Error('500'));
        const api = host();
        await flushPromises();

        const ok = await api().save({ currency: 'USD' }, 'Saved.');

        expect(ok).toBe(false);
        expect(api().draft.currency).toBe('NZD');
        expect(m.notify).toHaveBeenCalledWith(expect.objectContaining({ type: 'negative' }));
    });
});
