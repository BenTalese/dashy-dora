/**
 * The app's confirm / prompt / pick dialogs, as promises.
 *
 * Every yes-or-no question used to be its own `$q.dialog({...})` with a
 * hand-wrapped Promise (50 sites in 26 files, four of them with a page-local
 * `confirmAsync` — finalisation 20-R11 / 13-R26 / 16-R22 / 18-R9). This is
 * the one place the dialog conventions live (D-008 / D-015):
 *
 *   - sentence-case labels, `noCaps` on every button (R-039);
 *   - Cancel is flat, OK is filled and **primary** unless `destructive`,
 *     which paints it `negative` — the copy still has to say what is lost
 *     ("This can't be undone.") because the colour alone is not a warning;
 *   - Escape and a backdrop tap cancel (`persistent: false`) unless the
 *     caller says the question must be answered;
 *   - never `html: true` — a title or message that carries user text (a
 *     sheet name, a recipe name) is plain text (18-R5 / 06-R40).
 *
 * Built on Quasar's `Dialog` plugin directly rather than `useQuasar()` so it
 * works from a composable or a store as well as from `setup()`.
 */
import { Dialog, type QDialogOptions } from 'quasar';

export interface ConfirmOptions {
    title: string;
    message?: string;
    /** Default "OK". */
    okLabel?: string;
    /** Default "Cancel". */
    cancelLabel?: string;
    /** Paints the OK action `negative` for a delete / discard / revoke. */
    destructive?: boolean;
    /** The question must be answered: Escape and the backdrop do nothing. */
    persistent?: boolean;
}

export interface PromptOptions {
    title: string;
    message?: string;
    initial?: string;
    type?: 'text' | 'url';
    okLabel?: string;
    isValid?: (value: string) => boolean;
}

export interface ChoiceItem<T extends string> {
    label: string;
    value: T;
}

export interface ChooseOptions<T extends string> {
    title: string;
    message?: string;
    items: ChoiceItem<T>[];
    initial?: T;
    okLabel?: string;
}

export interface ChooseManyOptions<T extends string> {
    title: string;
    message?: string;
    items: ChoiceItem<T>[];
    initial?: T[];
    okLabel?: string;
}

function buttons(opts: { okLabel?: string; cancelLabel?: string; destructive?: boolean }) {
    return {
        ok: {
            label: opts.okLabel ?? 'OK',
            color: opts.destructive ? 'negative' : 'primary',
            unelevated: true,
            noCaps: true,
        },
        cancel: { label: opts.cancelLabel ?? 'Cancel', flat: true, noCaps: true },
    };
}

/** Opens the dialog and resolves with the OK payload, or `null` when the
 *  user cancelled, pressed Escape or tapped the backdrop. */
function open<T>(options: QDialogOptions): Promise<T | null> {
    return new Promise<T | null>((resolve) => {
        Dialog.create(options)
            .onOk((payload: T) => resolve(payload ?? (true as unknown as T)))
            .onCancel(() => resolve(null))
            .onDismiss(() => resolve(null));
    });
}

async function confirmDialog(opts: ConfirmOptions): Promise<boolean> {
    const answer = await open<boolean>({
        title: opts.title,
        ...(opts.message !== undefined ? { message: opts.message } : {}),
        persistent: opts.persistent ?? false,
        ...buttons(opts),
    });
    return answer === true;
}

/** Resolves with the trimmed text, or `null` when cancelled or left empty. */
async function promptDialog(opts: PromptOptions): Promise<string | null> {
    const answer = await open<string>({
        title: opts.title,
        ...(opts.message !== undefined ? { message: opts.message } : {}),
        prompt: {
            model: opts.initial ?? '',
            type: opts.type ?? 'text',
            ...(opts.isValid ? { isValid: opts.isValid } : {}),
        },
        persistent: false,
        ...buttons(opts),
    });
    const trimmed = typeof answer === 'string' ? answer.trim() : '';
    return trimmed ? trimmed : null;
}

/** One of `items` (radio), or `null` when cancelled. */
async function chooseDialog<T extends string>(opts: ChooseOptions<T>): Promise<T | null> {
    const first = opts.items[0];
    if (!first) return null;
    return await open<T>({
        title: opts.title,
        ...(opts.message !== undefined ? { message: opts.message } : {}),
        options: { type: 'radio', model: opts.initial ?? first.value, items: opts.items },
        persistent: false,
        ...buttons(opts),
    });
}

/** Any number of `items` (checkboxes), or `null` when cancelled. */
async function chooseManyDialog<T extends string>(opts: ChooseManyOptions<T>): Promise<T[] | null> {
    return await open<T[]>({
        title: opts.title,
        ...(opts.message !== undefined ? { message: opts.message } : {}),
        options: { type: 'checkbox', model: opts.initial ?? [], items: opts.items },
        persistent: false,
        ...buttons(opts),
    });
}

export function useConfirm() {
    return {
        confirm: confirmDialog,
        prompt: promptDialog,
        choose: chooseDialog,
        chooseMany: chooseManyDialog,
    };
}
