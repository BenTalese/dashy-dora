/**
 * The QSelect methods call sites reach for through a `BaseSelect` template ref.
 * A wrapper hides its child's instance, so `BaseSelect` re-exposes these
 * explicitly (FU-675). Lives in a `.ts` file so type-aware lint can resolve it
 * from a consumer — an interface exported from a generic SFC reads as `any`.
 */
export interface BaseSelectExposed {
    updateInputValue: (value: string, noFilter?: boolean) => void;
    showPopup: () => void;
    hidePopup: () => void;
    focus: () => void;
    blur: () => void;
    validate: () => boolean | Promise<boolean>;
    resetValidation: () => void;
}
