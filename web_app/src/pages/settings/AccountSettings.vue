<template>
    <!-- The router guard owns "signed in"; this only waits for the user row. -->
    <div v-if="currentUser" class="settings-page">
        <SettingsPageHeader title="Account" :icon="ICONS.person" />

        <SettingsSection>
            <template #title>Profile picture</template>
            <SettingsRow stacked>
                <div class="avatar-edit-wrap">
                    <ImageEditTile
                        :label="currentUser.has_image
                            ? 'Change your profile picture'
                            : 'Upload a profile picture'"
                        :busy="savingImage"
                        @pick="onPickImage"
                        @error="(m) => (imageError = m)"
                    >
                        <UserAvatar
                            :user-id="currentUser.user_id"
                            :has-image="currentUser.has_image"
                            size="96px"
                            fallback="initials"
                            :username="currentUser.username"
                            color="accent"
                            text-color="dark"
                        />
                    </ImageEditTile>

                    <BaseButton
                        v-if="currentUser.has_image"
                        variant="ghost"
                        dense
                        :icon="ICONS.delete_outline"
                        label="Remove photo"
                        :loading="savingImage"
                        @click="onClearImage"
                    />

                    <div v-if="imageError" class="text-caption text-negative">
                        {{ imageError }}
                    </div>
                </div>
            </SettingsRow>
            <SettingsRow stacked>
                <div class="avatar-presets">
                    <div class="text-caption dora-text-secondary">Or pick one of ours</div>
                    <PresetAvatarPicker
                        :disabled="savingImage"
                        @pick="onPickPreset"
                        @error="(m) => (imageError = m)"
                    />
                </div>
            </SettingsRow>
        </SettingsSection>

        <hr class="settings-divider" />

        <SettingsSection>
            <template #title>Username</template>
            <SettingsRow stacked>
                <q-input
                    v-model="usernameDraft"
                    outlined
                    dense
                    class="account-field"
                    autocomplete="username"
                    aria-label="Username"
                    :error="usernameDraft.trim().length === 0"
                    :error-message="usernameDraft.trim().length === 0
                        ? 'Username can\'t be empty' : ''"
                />
            </SettingsRow>
        </SettingsSection>

        <hr class="settings-divider" />

        <SettingsSection>
            <template #title>Email</template>
            <SettingsRow stacked>
                <q-input
                    v-model="emailDraft"
                    outlined
                    dense
                    placeholder="you@example.com"
                    class="account-field"
                    autocomplete="email"
                    aria-label="Email"
                    :error="emailInvalid"
                    :error-message="emailInvalid ? 'Enter a valid email address' : ''"
                />
            </SettingsRow>
        </SettingsSection>

        <hr class="settings-divider" />

        <SettingsSection>
            <template #title>Change password</template>
            <template #description>
                Leave these blank unless you want to change your password.
            </template>
            <SettingsRow stacked>
                <div class="row q-col-gutter-sm">
                    <!-- `bottom-slots` reserves the message row this field
                         doesn't otherwise have. Its two siblings carry an
                         :error binding, so Quasar reserves 20px under *them*
                         only — which on mobile (fields stacked) left Confirm
                         sitting 28px below New while Current sat 8px above it,
                         reading as a stray gap (owner, 2026-08-17). Reserving
                         on all three makes the spacing uniform and stops the
                         group shifting when a validation message appears. -->
                    <q-input
                        v-model="currentPassword"
                        label="Current password"
                        outlined
                        dense
                        bottom-slots
                        type="password"
                        class="col-12 col-sm-4"
                        autocomplete="current-password"
                    />
                    <q-input
                        v-model="newPassword"
                        label="New password"
                        outlined
                        dense
                        type="password"
                        class="col-12 col-sm-4"
                        autocomplete="new-password"
                        :error="newPassword.length > 0 && !passwordLongEnough(newPassword)"
                        :error-message="newPassword.length > 0 && !passwordLongEnough(newPassword)
                            ? PASSWORD_HINT : ''"
                    />
                    <q-input
                        v-model="confirmPassword"
                        label="Confirm new password"
                        outlined
                        dense
                        type="password"
                        class="col-12 col-sm-4"
                        autocomplete="new-password"
                        :error="confirmPassword.length > 0 && confirmPassword !== newPassword"
                        :error-message="confirmPassword.length > 0 && confirmPassword !== newPassword
                            ? 'Passwords do not match' : ''"
                    />
                </div>
            </SettingsRow>
        </SettingsSection>

        <div class="account-savebar">
            <BaseButton
                v-if="isDirty"
                variant="ghost"
                label="Discard"
                :disable="saving"
                @click="resetDrafts"
            />
            <BaseButton
                :icon="ICONS.save"
                label="Save changes"
                :loading="saving"
                :disable="!canSave"
                @click="onSaveAll"
            />
        </div>
    </div>
</template>

<script lang="ts" setup>
    import { useSettingsSave } from 'src/composables/useSettingsSave';
    import BaseButton from 'src/components/BaseButton.vue';
    import { ICONS } from 'src/style/icons';
    import { storeToRefs } from 'pinia';
    import { useAuthStore } from 'src/stores/authStore';
    import { computed, ref, watch } from 'vue';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import UserAvatar from 'src/components/UserAvatar.vue';
    import ImageEditTile from 'src/components/ImageEditTile.vue';
    import PresetAvatarPicker from 'src/components/PresetAvatarPicker.vue';
    import type { ProcessedImage } from 'src/services/files/imageService';
    import { useUnsavedChangesGuard } from 'src/composables/useUnsavedChangesGuard';
    import { PASSWORD_HINT, passwordLongEnough } from 'src/models/password';

    const authStore = useAuthStore();
    const { currentUser } = storeToRefs(authStore);

    // ── Profile picture — click the circle to pick, immediate save ─────
    // The image is a distinct action, not part of the deferred field save:
    // picking or clearing commits straight away (no draft window), matching
    // how modern apps handle an avatar. ImageEditTile owns the picker + the
    // resize/encode step; this only saves the result.
    const savingImage = ref(false);
    const imageError = ref<string | null>(null);

    function onPickImage(processed: ProcessedImage) {
        void saveImage(processed.dataUrl);
    }

    // A pre-made picture saves exactly like an upload — it arrives already
    // encoded, so it goes through the same `image` field.
    function onPickPreset({ dataUrl }: { dataUrl: string }) {
        void saveImage(dataUrl);
    }

    async function saveImage(dataUrl: string) {
        savingImage.value = true;
        imageError.value = null;
        try {
            await authStore.updateMeAsync({ image: dataUrl });
            notifySuccess('Profile picture updated.');
        } catch (err) {
            imageError.value = err instanceof Error ? err.message : 'Could not update your profile picture.';
            notifyError('Could not update your profile picture.', err);
        } finally {
            savingImage.value = false;
        }
    }

    async function onClearImage() {
        savingImage.value = true;
        imageError.value = null;
        try {
            await authStore.updateMeAsync({ clear_image: true });
            notifySuccess('Profile picture removed.');
        } catch (err) {
            notifyError('Could not remove your profile picture.', err);
        } finally {
            savingImage.value = false;
        }
    }

    // ── Deferred field drafts (username / email / password) ────────────
    const usernameDraft = ref(currentUser.value?.username ?? '');
    const emailDraft = ref(currentUser.value?.email ?? '');
    const currentPassword = ref('');
    const newPassword = ref('');
    const confirmPassword = ref('');
    const saving = ref(false);

    function resetDrafts() {
        usernameDraft.value = currentUser.value?.username ?? '';
        emailDraft.value = currentUser.value?.email ?? '';
        currentPassword.value = '';
        newPassword.value = '';
        confirmPassword.value = '';
    }

    // Re-baseline drafts when the user record changes (e.g. after a save
    // elsewhere), but don't clobber in-progress edits.
    watch(currentUser, (u) => {
        if (!u) return;
        if (usernameUnchanged.value) usernameDraft.value = u.username;
        if (emailUnchanged.value) emailDraft.value = u.email ?? '';
    });

    const usernameUnchanged = computed(
        () => (currentUser.value?.username ?? '') === usernameDraft.value.trim(),
    );
    const emailUnchanged = computed(
        () => (currentUser.value?.email ?? '') === emailDraft.value.trim(),
    );
    const passwordDirty = computed(
        () => currentPassword.value.length > 0
            || newPassword.value.length > 0
            || confirmPassword.value.length > 0,
    );

    const emailInvalid = computed(() => {
        const v = emailDraft.value.trim();
        // Empty is allowed (clears the address); otherwise a light shape check
        // mirroring the server's validator (real check is server-side).
        return v.length > 0 && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v);
    });

    const passwordValid = computed(
        () => currentPassword.value.length > 0
            && passwordLongEnough(newPassword.value)
            && confirmPassword.value === newPassword.value,
    );

    const isDirty = computed(
        () => !usernameUnchanged.value || !emailUnchanged.value || passwordDirty.value,
    );

    // Everything the Save button will commit must be valid: username present,
    // email well-formed (or blank), and if any password field is touched the
    // whole password change must be valid.
    const canSave = computed(
        () => isDirty.value
            && usernameDraft.value.trim().length > 0
            && !emailInvalid.value
            && (!passwordDirty.value || passwordValid.value),
    );

    // R-020 — deferred-save surface, wire the unsaved-changes guard. Password
    // fields join the predicate now that they save through the page button
    // (the browsers-lose-passwords exclusion applied when they had their own
    // submit; here an unsaved password edit is real pending work).
    useUnsavedChangesGuard(isDirty);

    const { notifySuccess, notifyError } = useSettingsSave();

    async function onSaveAll() {
        if (!canSave.value) return;
        saving.value = true;
        try {
            // Username + email go in one /auth/me patch; only send what changed.
            const patch: { username?: string; email?: string } = {};
            if (!usernameUnchanged.value) patch.username = usernameDraft.value.trim();
            if (!emailUnchanged.value) patch.email = emailDraft.value.trim();
            if (Object.keys(patch).length > 0) {
                await authStore.updateMeAsync(patch);
            }
            if (passwordDirty.value) {
                await authStore.changePasswordAsync({
                    current_password: currentPassword.value,
                    new_password: newPassword.value,
                });
                currentPassword.value = '';
                newPassword.value = '';
                confirmPassword.value = '';
            }
            notifySuccess('Changes saved.');
        } catch (err) {
            notifyError('Could not save your changes.', err);
        } finally {
            saving.value = false;
        }
    }
</script>

<style scoped lang="scss">
    // The sections here are short (a heading + one input), so the shared
    // section rhythm (24px bottom padding) stacked with the dividers left big
    // empty bands. Tighten both — scoped to this page only.
    :deep(.settings-section) {
        padding-bottom: 14px;
        gap: 12px;
    }

    // The tile itself (circle + hover pencil) lives in ImageEditTile; this
    // only stacks it above the Remove button.
    .avatar-edit-wrap {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
    }

    .avatar-presets {
        display: flex;
        flex-direction: column;
        gap: 8px;
        max-width: 420px;
    }

    .account-field {
        width: 100%;
        max-width: 420px;
    }

    .account-savebar {
        position: sticky;
        bottom: 0;
        display: flex;
        justify-content: flex-end;
        gap: var(--space-3);
        margin-top: var(--space-2);
        padding: var(--space-3) 0;
        /* Fades from the page colour so a scrolled field doesn't show through
           the buttons. Was `--surface-base`, which no theme declares, so it
           always fell through to transparent. */
        background: linear-gradient(to top, var(--surface-page) 65%, transparent);
    }
</style>
