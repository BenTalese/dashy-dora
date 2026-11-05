<template>
    <AuthShell backdrop="blobs" mascot="top-right">
        <template #card-head>
            <q-icon :name="ICONS.password" size="56px" :style="'color: var(--auth-shell-accent)'" />
            <div class="text-h6 q-mt-md">Choose a new password</div>
        </template>

        <q-banner v-if="!token" class="dora-bg-negative-soft text-negative" rounded>
            This reset link is missing a token. Request a fresh one
            from Forgot password.
        </q-banner>
        <q-form v-else-if="!done" @submit.prevent="onSubmit" class="q-gutter-y-md">
            <q-input
                v-model="password"
                outlined
                autofocus
                type="password"
                label="New password"
                autocomplete="new-password"
                :error="!!fieldError"
                :error-message="fieldError"
                @update:model-value="fieldError = ''"
            />
            <q-input
                v-model="confirm"
                outlined
                type="password"
                label="Confirm new password"
                autocomplete="new-password"
            />
            <AuthButton
                type="submit"
                colour="primary"
                :loading="submitting"
                :disable="!password || password !== confirm"
                label="Reset password"
            />
            <div v-if="password && password !== confirm" class="text-caption text-negative">
                Passwords don't match.
            </div>
        </q-form>
        <q-banner v-else class="dora-bg-positive-soft text-positive" rounded>
            <template #avatar><q-icon :name="ICONS.check_circle" /></template>
            Password reset. Sign in with your new password.
        </q-banner>

        <template #card-foot>
            <AuthButton
                v-if="done"
                colour="primary"
                label="Continue to sign in"
                to="/login"
            />
            <AuthButton v-else colour="ghost" label="Cancel" to="/login" />
        </template>
    </AuthShell>
</template>

<script lang="ts" setup>
    import AuthShell from 'src/components/AuthShell.vue';
    import AuthButton from 'src/components/AuthButton.vue';
    import { ICONS } from 'src/style/icons';
    import { useQuasar } from 'quasar';
    import { computed, ref } from 'vue';
    import { useRoute } from 'vue-router';
    import AuthApiService, { } from 'src/services/api/authApiService';
    import { NormalisedApiError } from 'src/services/api/axiosHttpClient';
    import { isAlreadyNotified } from 'src/services/errorHandling/apiErrorHandler';

    const $q = useQuasar();
    const route = useRoute();
    const api = new AuthApiService();

    const token = computed(() => String(route.query.token ?? '').trim());
    const password = ref('');
    const confirm = ref('');
    const submitting = ref(false);
    const done = ref(false);
    const fieldError = ref('');

    async function onSubmit() {
        submitting.value = true;
        fieldError.value = '';
        try {
            await api.resetPasswordAsync(token.value, password.value);
            done.value = true;
        } catch (err) {
            if (err instanceof NormalisedApiError) {
                const fieldMsg =
                    (err.details?.errors as Record<string, string[]> | undefined)?.['new_password']?.[0];
                if (fieldMsg) {
                    fieldError.value = fieldMsg;
                } else {
                    if (!isAlreadyNotified(err)) {
                        $q.notify({
                            type: 'negative',
                            message: err.message || 'Reset failed.',
                        });
                    }
                }
            } else {
                if (!isAlreadyNotified(err)) {
                    $q.notify({ type: 'negative', message: String(err) });
                }
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
