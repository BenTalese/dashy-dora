<template>
    <AuthShell backdrop="blobs" mascot="top-right">
        <template #card-head>
            <AuthBadge :icon="ICONS.auto_awesome">One-time setup</AuthBadge>
            <div class="setup-title" style="font-family: 'Cute Dino'">
                Dashy Dora
            </div>
            <div class="setup-sub">
                Welcome! Create the first admin account to get started.
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
                outlined
                v-model="form.email"
                label="Email (optional)"
                type="email"
                autocomplete="email"
                hint="Only used to email you a password reset. Leave it blank if you'd rather not."
                :error="!!fieldErrors.email"
                :error-message="fieldErrors.email"
                @update:model-value="clearField('email')"
            />

            <PasswordField
                outlined
                v-model="form.password"
                label="Password"
                kind="new"
                :error="!!fieldErrors.password"
                :error-message="fieldErrors.password"
                @update:model-value="clearField('password')"
            />

            <FormErrorSummary :message="generalError" />

            <AuthButton
                colour="primary"
                type="submit"
                :loading="submitting"
                label="Create admin account"
            />
        </q-form>

        <!-- The first-setup demo: look around with sample data first. The
             banner it brings offers the way back here, which clears the
             demo out. -->
        <template v-if="setupDemoAvailable" #card-foot>
            <div class="setup-foot">
                <AuthButton
                    colour="secondary"
                    :loading="startingDemo"
                    label="Look around a demo first"
                    @click="onStartDemo"
                />
                <div class="setup-fineprint">
                    Sample data to explore. Come back here whenever you're ready;
                    setting up for real clears the demo out.
                </div>
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
    import FormErrorSummary from 'src/components/FormErrorSummary.vue';
    import PasswordField from 'src/components/PasswordField.vue';
    import { useFormErrors } from 'src/composables/useFormErrors';
    import { useAuthStore } from 'src/stores/authStore';
    import { useDemoMode } from 'src/composables/useDemoMode';
    import { deviceTimezone } from 'src/models/regionChoices';
    import { reactive, ref } from 'vue';
    import { useRouter } from 'vue-router';

    const $q = useQuasar();
    const authStore = useAuthStore();
    const router = useRouter();

    const submitting = ref(false);
    const startingDemo = ref(false);
    // Off on an install locked to ADMIN_BOOTSTRAP_EMAIL (the server refuses too).
    const { setupDemoAvailable } = useDemoMode();
    const { fieldErrors, generalError, handleSaveError, reset: resetErrors } = useFormErrors();

    const form = reactive({
        username: '',
        password: '',
        email: '',
    });

    function clearField(field: string) {
        if (fieldErrors.value[field]) {
            const next = { ...fieldErrors.value };
            delete next[field];
            fieldErrors.value = next;
        }
    }

    async function onStartDemo() {
        startingDemo.value = true;
        resetErrors();
        try {
            await authStore.startSetupDemoAsync();
            void router.replace('/');
        } catch (err) {
            handleSaveError(err, "The demo couldn't be started. Try again.");
        } finally {
            startingDemo.value = false;
        }
    }

    async function onSubmit() {
        submitting.value = true;
        resetErrors();
        try {
            await authStore.setupAdminAsync({
                username: form.username,
                password: form.password,
                // Blank means "no address" — send null, not "", so the
                // server stores NULL rather than an empty string.
                email: form.email.trim() || null,
                // QA2-12 — skipping onboarding must not leave the household on UTC.
                timezone: deviceTimezone(),
            });
            $q.notify({
                type: 'positive',
                message: 'Admin account created. Welcome to Dashy Dora!',
                timeout: 4000,
            });
            void router.replace('/');
        } catch (err) {
            handleSaveError(
                err,
                'Setup failed. Please review the form and try again.',
            );
        } finally {
            submitting.value = false;
        }
    }
</script>

<style scoped>
    /* Page-specific typography + the one-time-setup badge. All chrome
       + button treatment lives on AuthShell / AuthButton. Fixes FU-440
       (was verbatim copy of LoginPage's private colour ladder). */
    .setup-title {
        font-size: 2.1rem;
        line-height: 1.1;
        letter-spacing: 0.01em;
        background: linear-gradient(135deg, var(--auth-shell-accent-strong), var(--auth-shell-accent));
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
    }
    .setup-foot {
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
    }
    .setup-fineprint {
        color: var(--auth-shell-text-muted);
        font-size: var(--font-size-xs);
        text-align: center;
    }
    .setup-sub {
        color: var(--auth-shell-text-muted);
        font-size: 0.95rem;
        margin-top: 6px;
    }
</style>
