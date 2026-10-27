<template>
    <AuthShell backdrop="blobs" mascot="top-right">
        <template #card-head>
            <div class="login-title" style="font-family: 'Cute Dino'">
                Dashy Dora
            </div>
            <div class="login-sub">
                {{ mode === 'login' ? 'Sign in to your pantry' : 'Create your account' }}
            </div>
        </template>

        <q-form ref="formRef" @submit.prevent="onSubmit" class="q-gutter-y-md">
            <q-input
                outlined
                autofocus
                v-model="form.username"
                label="Username"
                autocomplete="username"
                :error="!!fieldErrors.username"
                :error-message="fieldErrors.username"
                @update:model-value="clearField('username')"
                :rules="[(v: string) => !!v || 'Username is required']"
            />

            <q-input
                v-if="mode === 'register'"
                outlined
                v-model="form.email"
                label="Email (optional)"
                type="email"
                autocomplete="email"
                :error="!!fieldErrors.email"
                :error-message="fieldErrors.email"
                @update:model-value="clearField('email')"
            />

            <PasswordField
                outlined
                v-model="form.password"
                label="Password"
                :kind="mode === 'login' ? 'current' : 'new'"
                :error="!!fieldErrors.password"
                :error-message="fieldErrors.password"
                @update:model-value="clearField('password')"
            />

            <FormErrorSummary :message="generalError" />

            <AuthButton
                colour="primary"
                type="submit"
                :loading="submitting"
                :label="mode === 'login' ? 'Sign In' : 'Create Account'"
            />
        </q-form>

        <template #card-foot>
            <div class="login-foot">
                <AuthButton
                    colour="secondary"
                    :label="mode === 'login' ? 'Need an account? Register' : 'Have an account? Sign in'"
                    @click="toggleMode"
                />
                <AuthButton
                    v-if="mode === 'login' && emailSenderConfigured"
                    colour="ghost"
                    label="Forgot password?"
                    @click="router.push('/forgot-password')"
                />
            </div>
        </template>
    </AuthShell>
</template>

<script lang="ts" setup>
    import { useQuasar } from 'quasar';
    import AuthShell from 'src/components/AuthShell.vue';
    import AuthButton from 'src/components/AuthButton.vue';
    import FormErrorSummary from 'src/components/FormErrorSummary.vue';
    import PasswordField from 'src/components/PasswordField.vue';
    import AuthApiService from 'src/services/api/authApiService';
    import { NormalisedApiError } from 'src/services/api/axiosHttpClient';
    import { useFormErrors } from 'src/composables/useFormErrors';
    import { useAuthStore } from 'src/stores/authStore';
    import { onMounted, reactive, ref } from 'vue';
    import { useRoute, useRouter } from 'vue-router';

    const $q = useQuasar();
    const authStore = useAuthStore();
    const router = useRouter();
    const route = useRoute();

    // Pre-auth capability probe. Hides the "Forgot password?" link on
    // installs with no outbound email — dry-run mode logs the reset link
    // to the server, which a normal user can't read, so surfacing the
    // link would send them into a dead-end loop.
    const emailSenderConfigured = ref(false);
    const authApi = new AuthApiService();

    onMounted(async () => {
        try {
            const caps = await authApi.getCapabilitiesAsync();
            emailSenderConfigured.value = caps.emailSenderConfigured;
        } catch {
            // Probe failure defaults to hidden — safer to under-surface
            // a broken link than to promise one that doesn't work.
        }

        // A1: surface a toast when arriving from /verify-email so the user
        // sees confirmation of the click-through.
        if (route.query.verified === '1') {
            $q.notify({
                type: 'positive', position: 'top',
                message: 'Email verified. Sign in to continue.',
                timeout: 4000,
            });
        }
    });

    const mode = ref<'login' | 'register'>('login');
    const submitting = ref(false);
    // R-001 form-error plumbing.
    const { fieldErrors, generalError, handleSaveError, reset: resetErrors } = useFormErrors();

    const form = reactive({
        username: '',
        password: '',
        email: ''
    });

    function clearField(field: string) {
        if (fieldErrors.value[field]) {
            const next = { ...fieldErrors.value };
            delete next[field];
            fieldErrors.value = next;
        }
    }

    function toggleMode() {
        mode.value = mode.value === 'login' ? 'register' : 'login';
        resetErrors();
    }

    async function onSubmit() {
        submitting.value = true;
        resetErrors();
        try {
            if (mode.value === 'login') {
                await authStore.loginAsync({
                    username: form.username,
                    password: form.password
                });
            } else {
                const verificationSent = await authStore.registerAsync({
                    username: form.username,
                    password: form.password,
                    email: form.email.length > 0 ? form.email : null
                });
                if (verificationSent) {
                    $q.notify({
                        type: 'info',
                        message: 'Check your inbox for a verification link.',
                        timeout: 6000,
                    });
                }
            }

            const redirect = (route.query.redirect as string | undefined) ?? '/';
            void router.replace(redirect);
        } catch (err) {
            // Login 401 is opaque by design — never tell the user *which*
            // half (username vs password) was wrong. Show a stable message
            // and skip the field-level extraction.
            if (
                mode.value === 'login' &&
                err instanceof NormalisedApiError &&
                err.status === 401
            ) {
                generalError.value = 'Sign-in failed. Check your username and password.';
            } else {
                handleSaveError(
                    err,
                    mode.value === 'login'
                        ? 'Sign-in failed. Please try again.'
                        : 'Registration failed. Please review the form and try again.',
                );
            }
        } finally {
            submitting.value = false;
        }
    }
</script>

<style scoped>
    /* Only page-specific typography lives here now. All chrome + tokens
       moved to AuthShell.vue; button treatment moved to AuthButton.vue. */
    .login-title {
        font-size: 2.1rem;
        line-height: 1.1;
        letter-spacing: 0.01em;
        background: linear-gradient(135deg, var(--auth-shell-accent-strong), var(--auth-shell-accent));
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
    }
    .login-sub {
        color: var(--auth-shell-text-muted);
        font-size: 0.92rem;
        margin-top: 4px;
    }
    .login-foot {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .login-fineprint {
        color: var(--auth-shell-text-muted);
        font-size: 0.78rem;
        text-align: center;
        margin-top: 4px;
    }
</style>
