import { computed, ref } from 'vue';
import AuthApiService from 'src/services/api/authApiService';

// The server's password-length rule, read from `/auth/capabilities` (FU-656)
// so a form can say "at least N characters" before the save without the
// number living on this side of the wire. `validate_password` stays the
// authority: it also refuses breach-list passwords, which no hint can show.
// Until the answer lands the hint is blank and nothing is refused here.

const minLength = ref<number | null>(null);
let inflight: Promise<void> | null = null;

function load(): void {
    inflight ??= new AuthApiService()
        .getCapabilitiesAsync()
        .then((caps) => { minLength.value = caps.minPasswordLength; })
        .catch(() => { inflight = null; });
}

export function usePasswordPolicy() {
    load();
    const hint = computed(() => (minLength.value === null ? '' : `At least ${minLength.value} characters`));
    function longEnough(value: string): boolean {
        return minLength.value === null || value.length >= minLength.value;
    }
    return { hint, longEnough };
}
