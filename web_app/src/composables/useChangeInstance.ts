import { Notify } from 'quasar';
import { getBackendBaseUrl, setBackendBaseUrl } from 'src/services/api/backendUrl';
import { toastCaption } from 'src/services/errorHandling/apiErrorHandler';
import { useConfirm } from 'src/composables/useConfirm';
const { prompt } = useConfirm();

/** Prompt for a Dora server URL, persist it, and tell the caller the
 *  normalised result (null when the user cancelled or the save failed — the
 *  failure has already been toasted). The About page and the un-bootstrapped
 *  splash both offer this; they used to carry two copies of the dialog and
 *  the save (finalisation 15-R9). The caller owns what happens next (a
 *  reload, a route replace) because the splash has no router. */
export async function promptAndSaveInstanceUrl(): Promise<string | null> {
    const initial = getBackendBaseUrl();
    const url = await prompt({
        title: 'Change instance URL',
        message: "Point this app at a different Dora backend. Enter the "
            + "full URL you'd type in a browser. /api is added "
            + "automatically if you leave it off.",
        initial: initial,
        type: 'url',
        okLabel: 'Save',
        isValid: (v: string) => v.trim().length > 0,
    });
    if (!url) return null;
    try {
        const normalised = await setBackendBaseUrl(url);
        Notify.create({
            type: 'positive',
            message: 'Instance URL saved. Refreshing…',
            timeout: 1500,
        });
        return normalised;
    } catch (err) {
        Notify.create({
            type: 'negative',
            message: 'Could not save the URL.',
            caption: toastCaption(err),
        });
        return null;
    }
}
