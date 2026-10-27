<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Push notifications"
            description="Web-push (VAPID) keys the browser needs to sign notification subscriptions. The private key is stored encrypted-at-rest (Fernet, wrapped by DORA_SECRET_ENCRYPTION_KEY)."
            :icon="ICONS.notifications_active"
        />

        <template v-if="ready">
            <!-- The VAPID private key is stored encrypted-at-rest; warn (and
                 offer a key) when DORA_SECRET_ENCRYPTION_KEY is unset so the
                 admin knows the save will be refused until it's configured. -->
            <EncryptionKeyBanner secret-label="the VAPID private key" />

            <SettingsSection>
                <template #title>VAPID</template>
                <template #description>
                    Both keys must be set for push notifications to work. Until
                    then, push stays hidden across the app.
                </template>

                <SettingsRow label="Public key" stacked>
                    <q-input
                        v-model="draft.vapid_public_key"
                        outlined dense clearable
                        placeholder="base64url-encoded uncompressed P-256 public key"
                        @blur="() => onSaveField('vapid_public_key')"
                    />
                </SettingsRow>

                <SettingsRow label="Subject" stacked>
                    <q-input
                        v-model="draft.vapid_subject"
                        outlined dense clearable
                        placeholder="mailto:admin@example.com"
                        @blur="() => onSaveField('vapid_subject')"
                    />
                </SettingsRow>

                <!-- VAPID private key lives encrypted-
                     at-rest on AppSetting.vapid_private_key_encrypted. The
                     read DTO returns only `vapid_private_key_configured`.
                     Write-only input: submit replaces / empty clears. -->
                <SettingsRow
                    :label="privateKeyConfigured ? 'Private key (change)' : 'Private key'"
                    :help="privateKeyConfigured
                        ? 'A private key is stored. Enter a new one to replace it, or use Clear to remove.'
                        : 'Encrypted at rest with DORA_SECRET_ENCRYPTION_KEY.'"
                    stacked
                >
                    <div class="column q-gutter-sm">
                        <q-input
                            v-model="privateKeyDraft"
                            type="password"
                            outlined dense
                            autogrow
                            :placeholder="privateKeyConfigured
                                ? '••••••••'
                                : 'Paste base64 / PEM private key'"
                        />
                        <div class="row q-gutter-sm">
                            <BaseButton
                                variant="primary"
                                label="Save"
                                :disable="savingKey || privateKeyDraft.length === 0"
                                @click="() => onSavePrivateKey(privateKeyDraft)"
                            />
                            <BaseButton
                                v-if="privateKeyConfigured"
                                variant="danger-ghost"
                                label="Clear"
                                :disable="savingKey"
                                @click="() => onSavePrivateKey('')"
                            />
                        </div>
                    </div>
                </SettingsRow>
            </SettingsSection>
        </template>
    </div>
</template>

<script lang="ts" setup>
    import { ICONS } from 'src/style/icons';
    import { useAppSettingDrafts } from 'src/composables/useAppSettingDrafts';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import EncryptionKeyBanner from 'src/components/settings/EncryptionKeyBanner.vue';
    import { useSettingsSave } from 'src/composables/useSettingsSave';
    import { useAppSettingsStore } from 'src/stores/appSettingsStore';
    import { computed, ref } from 'vue';

    type PushField = 'vapid_public_key' | 'vapid_subject';

    const { draft, ready, save } = useAppSettingDrafts({
        vapid_public_key: '',
        vapid_subject: 'mailto:admin@dora.local',
    });

    function onSaveField(field: PushField) {
        void save({ [field]: (draft[field] ?? '').trim() }, 'Push settings saved.');
    }

    // The private key is write-only: the row only says whether one is set.
    const store = useAppSettingsStore();
    const { update, saving: savingKey } = useSettingsSave();
    const privateKeyConfigured = computed(() => store.settings?.vapid_private_key_configured ?? false);
    const privateKeyDraft = ref('');

    async function onSavePrivateKey(nextValue: string) {
        const saved = await update(
            nextValue.length === 0 ? 'VAPID private key cleared.' : 'VAPID private key saved.',
            () => store.saveAsync({ vapid_private_key: nextValue }),
        );
        if (saved) privateKeyDraft.value = '';
    }
</script>

<style scoped lang="scss">
</style>
