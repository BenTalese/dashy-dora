import { describe, expect, it } from 'vitest';
import { appShellStyleFn } from 'src/helpers/appShell';

describe('appShellStyleFn', () => {
    it('fills the measured viewport below the chrome', () => {
        expect(appShellStyleFn(64, 800)).toEqual({ height: '736px' });
    });
    it('falls back to calc() before the first screen measure', () => {
        expect(appShellStyleFn(64, 0)).toEqual({ height: 'calc(100vh - 64px)' });
    });
});
