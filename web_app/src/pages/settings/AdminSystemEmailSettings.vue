<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Email"
            description="Whether this install sends email, and how it connects to a mail server."
            :icon="ICONS.mark_email_read"
        />

        <template v-if="ready">
            <!-- The SMTP password is stored encrypted-at-rest; warn (and offer
                 a key) when DORA_SECRET_ENCRYPTION_KEY is unset so the admin
                 knows the password save will be refused until it's configured. -->
            <EncryptionKeyBanner secret-label="the SMTP password" />

            <SettingsSection>
                <template #title>Email subsystem</template>
                <template #description>
                    Turn this off if the install should never send email.
                </template>

                <SettingsRow label="Email enabled">
                    <q-toggle
                        v-model="draft.email_enabled"
                        @update:model-value="() => onSaveField('email_enabled')"
                    />
                </SettingsRow>
            </SettingsSection>

            <!-- Owner 2026-10-15: a one-off how-to, collapsed so it stops
                 standing between the toggle and the SMTP fields. -->
            <CollapsibleCard header-toggles reveals="Gmail steps" class="gmail-card">
                <template #header>
                    <div class="gmail-card__title">
                        <q-icon :name="ICONS.google" size="18px" />
                        <span>Setting up Gmail</span>
                    </div>
                </template>

                <p class="gmail-note">
                    Gmail needs an <strong>App Password</strong> (16 characters)
                    tied to 2-Step Verification. Once you have one, fill in
                    the SMTP fields below.
                </p>

                <ol class="gmail-steps">
                    <li>
                        Turn on <strong>2-Step Verification</strong> on your
                        Google Account (Security → 2-Step Verification).
                        App Passwords need it.
                    </li>
                    <li>
                        Open the App Passwords page, create one named
                        <em>&ldquo;Dora&rdquo;</em>, and copy the
                        16-character password Google shows you (spaces don't
                        matter).
                    </li>
                    <li>
                        Fill in the SMTP fields below with
                        <code>smtp.gmail.com</code>, port <code>587</code>,
                        <strong>Use TLS</strong> on, your full Gmail address
                        as <em>Username</em> and <em>From address</em>, and
                        paste the App Password as the SMTP password.
                    </li>
                    <li>
                        Turn <strong>Email enabled</strong> on and try a
                        password reset (or any email-emitting flow) to
                        confirm it works.
                    </li>
                </ol>

                <p class="gmail-note">
                    <strong>Gotchas.</strong> If sends fail with
                    <code>535-5.7.8 Username and Password not accepted</code>
                    you've pasted your account password instead of the App
                    Password. Free Gmail caps at ~500 recipients/day; fine
                    for a personal self-host, not a public multi-user
                    install. For that, use a provider like Postmark, Resend or
                    SES.
                </p>

                <div class="gmail-cta">
                    <BaseButton
                        variant="secondary"
                        :icon="ICONS.google"
                        label="Create Gmail App Password"
                        href="https://myaccount.google.com/apppasswords"
                        target="_blank"
                    />
                </div>
            </CollapsibleCard>

            <SettingsSection>
                <template #title>SMTP</template>
                <template #description>
                    The mail server Dora sends through.
                </template>

                <SettingsRow label="Host" stacked>
                    <q-input
                        v-model="draft.smtp_host"
                        outlined dense clearable
                        placeholder="smtp.gmail.com"
                        @blur="() => onSaveField('smtp_host')"
                    />
                </SettingsRow>

                <SettingsRow label="Port">
                    <q-input
                        v-model.number="draft.smtp_port"
                        type="number"
                        outlined dense
                        style="max-width: 140px"
                        :min="1"
                        :max="65535"
                        @blur="() => onSaveField('smtp_port')"
                    />
                </SettingsRow>

                <SettingsRow label="Username" stacked>
                    <q-input
                        v-model="draft.smtp_username"
                        outlined dense clearable
                        placeholder="dora@example.com"
                        @blur="() => onSaveField('smtp_username')"
                    />
                </SettingsRow>

                <SettingsRow label="From address" stacked>
                    <q-input
                        v-model="draft.smtp_from"
                        outlined dense clearable
                        placeholder="Leave blank to use username"
                        @blur="() => onSaveField('smtp_from')"
                    />
                </SettingsRow>

                <SettingsRow label="Use TLS">
                    <q-toggle
                        v-model="draft.smtp_use_tls"
                        @update:model-value="() => onSaveField('smtp_use_tls')"
                    />
                </SettingsRow>

                <!-- SMTP password lives encrypted-at-rest
                     on AppSetting.smtp_password_encrypted. The response DTO
                     never returns the ciphertext; we know only whether one
                     is stored (`smtp_password_configured`). The input is
                     write-only: submitting a value replaces the stored
                     ciphertext; empty submit clears it. -->
                <SettingsRow
                    :label="passwordConfigured ? 'Password (change)' : 'Password'"
                    :help="passwordConfigured
                        ? 'A password is stored. Enter a new one to replace it, or use Clear to remove.'
                        : 'Encrypted at rest with DORA_SECRET_ENCRYPTION_KEY.'"
                    stacked
                >
                    <div class="row items-center q-gutter-sm">
                        <q-input
                            v-model="passwordDraft"
                            type="password"
                            outlined dense
                            style="flex: 1 1 auto"
                            :placeholder="passwordConfigured ? '••••••••' : 'Enter SMTP password'"
                        />
                        <BaseButton
                            variant="primary"
                            label="Save"
                            :disable="saving || passwordDraft.length === 0"
                            @click="() => onSavePassword(passwordDraft)"
                        />
                        <BaseButton
                            v-if="passwordConfigured"
                            variant="danger-ghost"
                            label="Clear"
                            :disable="saving"
                            @click="() => onSavePassword('')"
                        />
                    </div>
                </SettingsRow>
            </SettingsSection>

            <!-- Moved here 2026-09-03 when the Hosting page was retired (owner:
                 *"Hosting page makes little sense to me"*). The public URL is a
                 normal self-host setting — Gitea's ROOT_URL, Nextcloud's
                 overwrite.cli.url — and its whole job is building the absolute
                 links Dora puts in mail, so it belongs beside the mail config
                 rather than on a page of its own. -->
            <SettingsSection>
                <template #title>Links in emails</template>
                <template #description>
                    Dora needs to know its own address to write links into
                    verification and password-reset emails.
                </template>

                <SettingsRow label="Public URL" stacked>
                    <q-input
                        v-model="draft.public_url"
                        outlined dense clearable
                        placeholder="https://dora.example.com"
                        :error="publicUrlHasError"
                        :error-message="publicUrlHasError ? 'Must start with http:// or https://.' : ''"
                        @blur="onSavePublicUrl"
                    />
                </SettingsRow>
            </SettingsSection>

        </template>
    </div>
</template>

<script lang="ts" setup>
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';
    import { computed, ref } from 'vue';
    import { useAppSettingDrafts } from 'src/composables/useAppSettingDrafts';
    import { useSettingsSave } from 'src/composables/useSettingsSave';
    import { useAppSettingsStore } from 'src/stores/appSettingsStore';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import EncryptionKeyBanner from 'src/components/settings/EncryptionKeyBanner.vue';
    import CollapsibleCard from 'src/components/CollapsibleCard.vue';

    type EmailField = 'email_enabled' | 'smtp_host' | 'smtp_port'
        | 'smtp_username' | 'smtp_from' | 'smtp_use_tls'
        | 'public_url';

    const { draft, ready, save } = useAppSettingDrafts({
        email_enabled: false,
        smtp_host: '',
        smtp_port: 587,
        smtp_username: '',
        smtp_from: '',
        smtp_use_tls: true,
        public_url: '',
    });

    function onSaveField(field: EmailField) {
        void save({ [field]: draft[field] }, 'Email settings saved.');
    }

    const publicUrlHasError = computed(() => {
        const value = (draft.public_url ?? '').trim();
        if (!value) return false;
        return !value.startsWith('http://') && !value.startsWith('https://');
    });

    function onSavePublicUrl() {
        // The server validates too; bailing here shows the inline error
        // rather than a toast.
        if (publicUrlHasError.value) return;
        void save({ public_url: (draft.public_url ?? '').trim() }, 'Email settings saved.');
    }

    // The SMTP password is write-only: the server never returns it, only
    // whether one is set. Held locally and submitted explicitly.
    const store = useAppSettingsStore();
    const { update, saving } = useSettingsSave();
    const passwordConfigured = computed(() => store.settings?.smtp_password_configured ?? false);
    const passwordDraft = ref('');

    async function onSavePassword(nextValue: string) {
        const saved = await update(
            nextValue.length === 0 ? 'SMTP password cleared.' : 'SMTP password saved.',
            () => store.saveAsync({ smtp_password: nextValue }),
        );
        if (saved) passwordDraft.value = '';
    }
</script>

<style scoped lang="scss">
    .settings-page { display: flex; flex-direction: column; }
    .gmail-steps {
        margin: 0;
        padding-left: 20px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        color: var(--text-primary);
        font-size: 0.9375rem;
        line-height: 1.45;
        max-width: 68ch;
    }
    .gmail-steps code {
        font-size: 0.875em;
        padding: 1px 6px;
        border-radius: 4px;
        background: var(--surface-sunken);
        color: var(--text-primary);
    }
    .gmail-note {
        margin: 0;
        max-width: 68ch;
        color: var(--text-secondary);
        font-size: 0.875rem;
        line-height: 1.5;
    }
    .gmail-note code {
        font-size: 0.875em;
        padding: 1px 6px;
        border-radius: 4px;
        background: var(--surface-sunken);
        color: var(--text-primary);
    }
    .gmail-cta { display: flex; }
    .gmail-card {
        margin-bottom: var(--space-4);
        :deep(.collapsible-card__body) {
            display: flex;
            flex-direction: column;
            gap: var(--space-3);
        }
    }
    .gmail-card__title {
        display: flex;
        align-items: center;
        gap: var(--space-2);
        font-weight: 600;
    }
</style>
