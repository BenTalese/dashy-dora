import { describe, expect, it, vi } from 'vitest';
import { reactive } from 'vue';
import { useSlotLoader } from 'src/composables/useSlotLoader';

describe('useSlotLoader', () => {
    it('flags a failed slot and clears it on a later success', async () => {
        vi.spyOn(console, 'warn').mockImplementation(() => undefined);
        const { slotFailed, loadSlot } = useSlotLoader<'a' | 'b'>({ label: 'test slot' });

        await loadSlot('a', () => Promise.reject(new Error('500')));
        await loadSlot('b', () => Promise.resolve());
        expect(slotFailed('a')).toBe(true);
        expect(slotFailed('b')).toBe(false);

        await loadSlot('a', () => Promise.resolve());
        expect(slotFailed('a')).toBe(false);
    });

    it('holds the loading flag for the run and drops it after a failure', async () => {
        vi.spyOn(console, 'warn').mockImplementation(() => undefined);
        const loading = reactive({ a: false });
        const { loadSlot } = useSlotLoader<'a'>({ label: 'test slot', loading });
        let during = false;

        await loadSlot('a', () => {
            during = loading.a;
            return Promise.reject(new Error('500'));
        });
        expect(during).toBe(true);
        expect(loading.a).toBe(false);
    });
});
