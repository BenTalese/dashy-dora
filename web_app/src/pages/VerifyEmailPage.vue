<template>
    <AuthShell backdrop="blobs" mascot="top-right">
        <template #card-head>
            <q-icon
                :name="status === 'ok' ? ICONS.mark_email_read : status === 'error' ? ICONS.error : ICONS.mail_lock"
                :color="status === 'ok' ? 'positive' : status === 'error' ? 'negative' : undefined"
                :style="status !== 'ok' && status !== 'error' ? 'color: var(--auth-shell-accent)' : ''"
                size="64px"
            />
            <div class="text-h6 q-mt-md">
                {{ headline }}
            </div>
            <div class="text-caption q-mt-xs auth-aux-sub">
                {{ subline }}
            </div>
        </template>

        <template #card-foot>
            <AuthButton
                v-if="status === 'ok'"
                colour="primary"
                label="Continue to sign in"
                to="/login?verified=1"
            />
            <AuthButton
                v-else-if="status === 'error'"
                colour="ghost"
                label="Resend verification"
                @click="resendOpen = true"
            />
            <AuthButton
                v-else
                colour="ghost"
                label="Cancel"
                to="/login"
            />
        </template>
    </AuthShell>

    <BaseDialog v-model="resendOpen" title="Resend verification" closable card-style="min-width: 320px">
            <q-card-section>
                <q-input
                    v-model="resendEmail"
                    type="email"
                    outlined
                    dense
                    label="Email address"
                    autofocus
                />
            </q-card-section>
            <template #actions>
                <BaseButton variant="ghost" label="Cancel" v-close-popup />
                <BaseButton
                    variant="primary"
                    label="Send"
                    :loading="resending"
                    :disable="!resendEmail.trim() || resending"
                    @click="onResend"
                />
            </template>
    </BaseDialog>
</template>

<script lang="ts" setup>
    import { useQuasar } from 'quasar';
    import { ICONS } from 'src/style/icons';
    import AuthShell from 'src/components/AuthShell.vue';
    import AuthButton from 'src/components/AuthButton.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import { computed, onMounted, ref } from 'vue';
    import { useRoute } from 'vue-router';
    import AuthApiService from 'src/services/api/authApiService';

    const $q = useQuasar();
    const route = useRoute();
    const api = new AuthApiService();

    const status = ref<'pending' | 'ok' | 'error'>('pending');
    const resendOpen = ref(false);
    const resendEmail = ref('');
    const resending = ref(false);

    const headline = computed(() => {
        if (status.value === 'ok') return 'Email verified';
        if (status.value === 'error') return 'Verification link invalid';
        return 'Verifying your email…';
    });
    const subline = computed(() => {
        if (status.value === 'ok') return 'You can now sign in to Dashy Dora.';
        if (status.value === 'error') return 'The link may have expired. Request a fresh one below.';
        return 'Just a moment.';
    });

    onMounted(async () => {
        const token = String(route.query.token ?? '').trim();
        if (!token) {
            status.value = 'error';
            return;
        }
        try {
            await api.verifyEmailAsync(token);
            status.value = 'ok';
        } catch {
            status.value = 'error';
        }
    });

    async function onResend() {
        resending.value = true;
        try {
            await api.resendVerificationAsync(resendEmail.value.trim());
            $q.notify({
                type: 'positive',
                position: 'top',
                message: 'If that address is registered, a verification email is on its way.',
            });
            resendOpen.value = false;
            resendEmail.value = '';
        } catch (err) {
            $q.notify({
                type: 'negative',
                position: 'top',
                message: err instanceof Error ? err.message : 'Could not send.',
            });
        } finally {
            resending.value = false;
        }
    }
</script>

<style scoped>
    .auth-aux-sub {
        color: var(--auth-shell-text-muted);
    }
</style>
