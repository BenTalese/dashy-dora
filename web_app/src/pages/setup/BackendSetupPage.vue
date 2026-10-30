<template>
    <AuthShell backdrop="blobs" mascot="top-right">
        <template #card-head>
            <AuthBadge :icon="ICONS.dns">Choose your Dora</AuthBadge>
            <div class="setup-title" style="font-family: 'Cute Dino'">
                Dashy Dora
            </div>
            <div class="setup-sub">
                Point this app at the Dora instance you're running &mdash;
                a home server, the shared family box, or a hosted one.
            </div>
        </template>

        <q-form ref="formRef" @submit.prevent="onSubmit" class="q-gutter-y-md">
            <q-input
                outlined
                autofocus
                v-model="form.url"
                label="Instance URL"
                autocomplete="url"
                placeholder="https://dora.example.com"
                inputmode="url"
                :error="!!errorMessage"
                :error-message="errorMessage ?? undefined"
                @update:model-value="errorMessage = null"
            />

            <AuthButton
                type="submit"
                :label="submitting ? 'Checking&hellip;' : 'Connect'"
                :loading="submitting"
                :disable="!form.url.trim()"
            />
        </q-form>

        <template #card-foot>
            <div class="setup-help">
                Enter the full URL you'd type in a browser. We'll add
                <code>/api</code> automatically if you leave it off.
                You can change this later in Settings &rarr; About.
            </div>
        </template>
    </AuthShell>
</template>

<script lang="ts" setup>
    import { useQuasar } from 'quasar';
    import { ICONS } from 'src/style/icons';
    import AuthShell from 'src/components/AuthShell.vue';
    import AuthButton from 'src/components/AuthButton.vue';
    import AuthBadge from 'src/components/AuthBadge.vue';
    import { reactive, ref } from 'vue';
    import { useRouter } from 'vue-router';
    import AuthApiService from 'src/services/api/authApiService';
    import { useAuthStore } from 'src/stores/authStore';
    import { refreshDemoMode } from 'src/composables/useDemoMode';
    import { setBackendBaseUrl, getBackendBaseUrl, clearBackendBaseUrl } from 'src/services/api/backendUrl';

    const $q = useQuasar();
    const router = useRouter();
    const authStore = useAuthStore();

    const submitting = ref(false);
    const errorMessage = ref<string | null>(null);

    const form = reactive({
        url: getBackendBaseUrl() || '',
    });

    async function onSubmit() {
        const raw = form.url.trim();
        if (!raw) return;
        submitting.value = true;
        errorMessage.value = null;
        try {
            // Provisionally set the URL so the probe uses the normalised
            // form; roll back if anything about the new server fails — the
            // probe *or* the re-bootstrap — so a bad answer never leaves a
            // broken address saved while the page says "unreachable".
            const previous = getBackendBaseUrl();
            await setBackendBaseUrl(raw);
            try {
                // Shape check, not just a status check: any web server answers
                // 200, so an address serving an HTML page must not read as
                // "Connected". Through the shared client (request id, timeout
                // policy) — not a second bare axios (finalisation 15-R16).
                if (!(await new AuthApiService().isDoraServerAsync())) {
                    throw new Error('The server at that address is not Dora.');
                }
                // The boot probe and the demo-mode check both ran before any
                // address existed; ask the new server before routing on.
                await authStore.rebootstrapAsync();
            } catch (probeErr) {
                if (previous) {
                    await setBackendBaseUrl(previous);
                } else {
                    await clearBackendBaseUrl();
                }
                throw probeErr;
            }
            void refreshDemoMode();
            $q.notify({
                type: 'positive', position: 'top',
                message: 'Connected. Welcome to Dora!',
                timeout: 2500,
            });
            void router.replace('/');
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Could not reach that instance.';
            errorMessage.value = "Couldn't reach that server. Check the address and your connection. "
                + 'A home server without HTTPS needs http:// at the start.';
            console.warn('BackendSetup probe failed', message);
        } finally {
            submitting.value = false;
        }
    }
</script>

<style scoped>
    .setup-title {
        font-size: 2rem;
        line-height: 1.1;
        margin-bottom: 4px;
    }
    .setup-sub {
        font-size: 0.95rem;
        color: var(--text-secondary);
        margin-bottom: 8px;
    }
    .setup-help {
        font-size: 0.8rem;
        color: var(--text-secondary);
        text-align: center;
    }
    .setup-help code {
        background: var(--surface-sunken);
        padding: 1px 4px;
        border-radius: 3px;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
</style>
