<template>
    <AuthShell backdrop="blobs" mascot="top-right">
        <template #card-head>
            <q-icon :name="ICONS.lock_reset" size="56px" :style="'color: var(--auth-shell-accent)'" />
            <div class="text-h6 q-mt-md">Forgot password</div>
            <div class="text-caption q-mt-xs auth-aux-sub">
                Enter your account email and we'll send a reset link.
            </div>
        </template>

        <q-form v-if="!submitted" @submit.prevent="onSubmit" class="q-gutter-y-md">
            <q-banner v-if="sendFailed" class="dora-bg-sunken" rounded role="alert">
                Couldn't send that right now. Try again in a moment.
            </q-banner>
            <q-input
                v-model="email"
                type="email"
                outlined
                autofocus
                label="Email address"
                autocomplete="email"
                :rules="[(v: string) => !!v || 'Email is required']"
            />
            <AuthButton
                type="submit"
                colour="primary"
                :loading="submitting"
                label="Send reset link"
            />
        </q-form>
        <q-banner v-else class="dora-bg-sunken" rounded>
            <template #avatar><q-icon :name="ICONS.mark_email_read" /></template>
            If that address is registered, a reset link is on its way.
            Check your inbox (and spam folder).
        </q-banner>

        <template #card-foot>
            <AuthButton colour="ghost" label="Back to sign in" to="/login" />
        </template>
    </AuthShell>
</template>

<script lang="ts" setup>
    import AuthShell from 'src/components/AuthShell.vue';
    import AuthButton from 'src/components/AuthButton.vue';
    import { ICONS } from 'src/style/icons';
    import { ref } from 'vue';
    import AuthApiService from 'src/services/api/authApiService';
    import { NormalisedApiError } from 'src/services/api/axiosHttpClient';

    const api = new AuthApiService();
    const email = ref('');
    const submitting = ref(false);
    const submitted = ref(false);
    const sendFailed = ref(false);

    // Anti-enumeration: a 2xx and any 4xx the backend sends (validation)
    // both land on the same "check your inbox" screen. Only a failure that
    // says nothing about the address — the request never landed (network),
    // was throttled (429) or the server broke (5xx) — gets its own message,
    // and that message is identical for every address, so it leaks nothing.
    function isTransportFailure(err: unknown): boolean {
        if (!(err instanceof NormalisedApiError)) return true;
        return err.isNetworkError || err.status === 429 || err.status >= 500;
    }

    async function onSubmit() {
        submitting.value = true;
        sendFailed.value = false;
        try {
            await api.forgotPasswordAsync(email.value.trim());
            submitted.value = true;
        } catch (err) {
            console.warn('Forgot-password request failed', err);
            if (isTransportFailure(err)) {
                sendFailed.value = true;
            } else {
                submitted.value = true;
            }
        } finally {
            submitting.value = false;
        }
    }
</script>

<style scoped>
    .auth-aux-sub {
        color: var(--auth-shell-text-muted);
    }
</style>
