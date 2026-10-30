<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Users"
            description="Everyone who can sign in to this install. Deactivate an account to lock someone out without losing their history."
            :icon="ICONS.group"
        >
            <template #actions>
                <!-- The refresh button went (owner, 2026-08-17): the list is
                     reloaded after every mutation on this page and there is no
                     other writer, so it only ever re-fetched what was already
                     on screen. -->
                <BaseButton
                    variant="primary"
                    :icon="ICONS.person_add"
                    label="Add user"
                    @click="onAddClick"
                />
            </template>
        </SettingsPageHeader>

        <q-banner v-if="loadError" class="dora-bg-negative-soft text-negative q-mb-md" dense rounded>
            {{ loadError }}
        </q-banner>

        <!-- Rows are hand-rolled flex rather than q-item/q-item-section side
             slots. The old side-slot layout crammed two toggles and four
             labelled buttons into one non-wrapping row, which on a phone
             squeezed the name column to a few characters (owner, 2026-08-17).
             Here the identity block and the controls are siblings that wrap:
             one line each on desktop, stacked on mobile. -->
        <ul class="user-list">
            <li v-for="user in users" :key="user.user_id" class="user-row" :class="{ 'user-row--inactive': !user.is_active }">
                <div class="user-row__identity">
                    <UserAvatar
                        :user-id="user.user_id"
                        :has-image="user.has_image"
                        size="42px"
                        fallback="initials"
                        :username="user.username"
                        :color="user.is_admin ? 'accent' : undefined"
                        :class="user.is_admin ? '' : 'dora-bg-sunken dora-text-secondary'"
                        :text-color="user.is_admin ? 'dark' : undefined"
                    />
                    <div class="user-row__names">
                        <!-- The `admin` and `deactivated` chips went 2026-09-03
                             (owner): both restated a toggle sitting on the same
                             row, and a deactivated row is already dimmed. `you`
                             stays — nothing else on the row says it. -->
                        <div class="user-row__name">
                            <span class="text-weight-medium">{{ user.username }}</span>
                            <q-badge v-if="user.user_id === currentUserId" outline color="primary">you</q-badge>
                        </div>
                        <div class="user-row__email dora-text-muted">
                            {{ user.email ?? 'No email on file' }}
                        </div>
                    </div>
                </div>

                <div class="user-row__controls">
                    <!-- The per-user deals-email toggle moved out (owner,
                         2026-08-17). It's a personal notification preference —
                         it already lives in Settings → Notifications, where the
                         user owns it — not a thing an admin administers. -->
                    <!-- D-019: the only thing allowed to disable these is the
                         *semantic* reason (it's your own row). The in-flight
                         `busyId` deliberately does NOT gate them — inerting a
                         focusable control mid-interaction drops focus, and a
                         double-toggle is last-write-wins, which `patch()`
                         converges by reloading the list after every write. -->
                    <q-toggle
                        :model-value="user.is_admin"
                        label="Admin"
                        dense
                        :disable="user.user_id === currentUserId"
                        @update:model-value="onToggleAdmin(user, $event)"
                    >
                        <BaseTooltip v-if="user.user_id === currentUserId">
                            Use Account settings to manage your own account.
                        </BaseTooltip>
                    </q-toggle>
                    <q-toggle
                        :model-value="user.is_active"
                        label="Active"
                        dense
                        :disable="user.user_id === currentUserId"
                        @update:model-value="onToggleActive(user, $event)"
                    >
                        <BaseTooltip v-if="user.user_id === currentUserId">
                            You can't deactivate your own account.
                        </BaseTooltip>
                    </q-toggle>

                    <!-- Edit / password / delete collapse into one menu. Four
                         labelled buttons per row was the other half of the
                         mobile squeeze, and these are all deliberate,
                         low-frequency actions. -->
                    <BaseButton
                        variant="icon"
                        :icon="ICONS.more_vert"
                        :loading="busyId === user.user_id"
                        :aria-label="`Actions for ${user.username}`"
                    >
                        <q-menu auto-close anchor="bottom right" self="top right">
                            <q-list style="min-width: 200px">
                                <q-item clickable @click="onEdit(user)">
                                    <q-item-section avatar>
                                        <q-icon :name="ICONS.edit" size="20px" />
                                    </q-item-section>
                                    <q-item-section>Edit details</q-item-section>
                                </q-item>
                                <q-item clickable @click="onChangePassword(user)">
                                    <q-item-section avatar>
                                        <q-icon :name="ICONS.lock_reset" size="20px" />
                                    </q-item-section>
                                    <q-item-section>Change password</q-item-section>
                                </q-item>
                                <q-item v-if="user.has_image" clickable @click="onRemovePicture(user)">
                                    <q-item-section avatar>
                                        <q-icon :name="ICONS.image_off" size="20px" />
                                    </q-item-section>
                                    <q-item-section>Remove picture</q-item-section>
                                </q-item>
                                <q-separator />
                                <q-item
                                    clickable
                                    :disable="user.user_id === currentUserId"
                                    class="text-negative"
                                    @click="onDelete(user)"
                                >
                                    <q-item-section avatar>
                                        <q-icon :name="ICONS.delete" size="20px" />
                                    </q-item-section>
                                    <q-item-section>Delete user</q-item-section>
                                </q-item>
                            </q-list>
                        </q-menu>
                    </BaseButton>
                </div>
            </li>

            <li v-if="!loading && users.length === 0" class="user-row">
                <span class="dora-text-muted">No users found.</span>
            </li>
        </ul>

        <!-- SEC-3: sign-ups are closed by default; this page is where
             accounts come from otherwise, so the switch lives beside them. -->
        <SettingsSection>
            <template #title>Sign-ups</template>
            <SettingsRow inline>
                <template #label>
                    Let people create their own account
                    <InfoTip label="Sign-ups">
                        Shows "Need an account? Register" on the sign-in page, so anyone
                        who can reach this Dora can make an account and see the
                        household's kitchen. Leave it off and add people here
                        instead.
                    </InfoTip>
                </template>
                <q-toggle
                    :model-value="signUps.registration_enabled"
                    :disable="!signUpsReady"
                    @update:model-value="onSignUpsToggle"
                />
            </SettingsRow>
        </SettingsSection>

        <q-inner-loading :showing="loading && users.length === 0">
            <AppSpinner size="48px" />
        </q-inner-loading>

        <!-- Edit dialog ─────────────────────────────────────────── -->
        <BaseDialog v-model="editOpen" :title="`Edit ${editingUser?.username ?? ''}`" closable card-style="min-width: 320px; max-width: 480px">
            <q-card-section class="q-gutter-md">
                <q-input
                    v-model="editingUsername"
                    label="Username"
                    outlined
                    dense
                />
                <q-input
                    v-model="editingEmail"
                    label="Email"
                    outlined
                    dense
                    placeholder="No email on file"
                />
            </q-card-section>
            <template #actions>
                <BaseButton variant="ghost" label="Cancel" v-close-popup />
                <BaseButton
                    label="Save"
                    :loading="savingEdit"
                    :disable="!editingUsername.trim()"
                    @click="onSaveEdit"
                />
            </template>
        </BaseDialog>

        <!-- Add-user dialog ─────────────────────────────────────── -->
        <BaseDialog
            v-model="createOpen"
            title="Add user"
            closable
            card-style="min-width: 320px; max-width: 480px"
        >
            <q-card-section class="q-gutter-md">
                <q-input
                    v-model="createDraft.username"
                    outlined
                    label="Username *"
                    :error="!!createFieldErrors.username"
                    :error-message="createFieldErrors.username"
                    @update:model-value="() => clearCreateField('username')"
                    autofocus
                />
                <q-input
                    v-model="createDraft.email"
                    outlined
                    label="Email (optional)"
                    :error="!!createFieldErrors.email"
                    :error-message="createFieldErrors.email"
                    @update:model-value="() => clearCreateField('email')"
                />
                <!-- Owner call 2026-08-17 — set the password here rather than
                     relaying a generated one. Generating stays available for
                     the "they're not with me" case, so the old flow is a
                     checkbox away, not gone. -->
                <PasswordSetter
                    v-model="createDraft.password"
                    v-model:generate="createDraft.generate"
                    :error="createFieldErrors.password"
                    @input="() => clearCreateField('password')"
                />
                <q-toggle v-model="createDraft.is_admin" label="Admin" />
            </q-card-section>
            <template #actions>
                <BaseButton variant="ghost" label="Cancel" v-close-popup />
                <BaseButton
                    label="Create"
                    :loading="creating"
                    :disable="!canSubmitCreate"
                    @click="onSubmitCreate"
                />
            </template>
        </BaseDialog>

        <!-- Change-password dialog ──────────────────────────────── -->
        <BaseDialog
            v-model="passwordOpen"
            :title="`Change password for ${passwordTarget?.username ?? ''}`"
            closable
            card-style="min-width: 320px; max-width: 480px"
        >
            <q-card-section class="q-gutter-md">
                <div class="text-caption dora-text-muted">
                    This signs {{ passwordTarget?.username }} out of every device
                    they're currently signed in on.
                </div>
                <PasswordSetter
                    v-model="passwordDraft"
                    v-model:generate="passwordGenerate"
                    :error="passwordError"
                    autofocus
                    @input="passwordError = ''"
                />
            </q-card-section>
            <template #actions>
                <BaseButton variant="ghost" label="Cancel" v-close-popup />
                <BaseButton
                    label="Change password"
                    :loading="savingPassword"
                    :disable="!passwordGenerate && !passwordLongEnough(passwordDraft)"
                    @click="onSubmitPassword"
                />
            </template>
        </BaseDialog>

        <!-- Generated-password readout (shared by create + change) ── -->
        <BaseDialog
            v-model="generatedOpen"
            :title="generatedKind === 'create' ? 'User created' : 'Password changed'"
            closable
            card-style="min-width: 320px"
        >
            <q-card-section>
                <div class="text-caption dora-text-muted">
                    Copy this one-time password and pass it to
                    {{ generatedTargetName }}. It's only shown once.
                </div>
            </q-card-section>
            <q-card-section>
                <q-input
                    :model-value="generatedPassword"
                    readonly
                    outlined
                    dense
                    class="generated-password-readout"
                >
                    <template #append>
                        <BaseButton
                            variant="icon"
                            :icon="ICONS.content_copy"
                            aria-label="Copy password"
                            @click="copyGenerated"
                        />
                    </template>
                </q-input>
            </q-card-section>
            <template #actions>
                <BaseButton variant="ghost" label="Done" v-close-popup />
            </template>
        </BaseDialog>
    </div>
</template>

<script lang="ts" setup>
    import { useSettingsSave } from 'src/composables/useSettingsSave';
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import AppSpinner from 'src/components/AppSpinner.vue';
    import BaseButton from 'src/components/BaseButton.vue';
    import BaseDialog from 'src/components/BaseDialog.vue';
    import PasswordSetter from 'src/components/settings/PasswordSetter.vue';
    import { ICONS } from 'src/style/icons';
    import { storeToRefs } from 'pinia';
    import { copyToClipboard } from 'quasar';
    import UserAdminApiService, {
        type AdminCreateUserCommand,
        type AdminUser
    } from 'src/services/api/userAdminApiService';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import InfoTip from 'src/components/help/InfoTip.vue';
    import { useAppSettingDrafts } from 'src/composables/useAppSettingDrafts';
    import UserAvatar from 'src/components/UserAvatar.vue';
    import { useAuthStore } from 'src/stores/authStore';
    import { passwordLongEnough } from 'src/models/password';
    import { computed, onMounted, reactive, ref } from 'vue';
    import { describeApiError } from 'src/services/errorHandling/apiErrorHandler';
    import { useConfirm } from 'src/composables/useConfirm';

    const {
        draft: signUps, ready: signUpsReady, save: saveSignUps,
    } = useAppSettingDrafts({ registration_enabled: false });

    function onSignUpsToggle(value: boolean) {
        void saveSignUps(
            { registration_enabled: value },
            value ? 'Anyone can now create an account.' : 'Sign-ups closed.',
        );
    }


    const { confirm } = useConfirm();
    const { notifySuccess, notifyError } = useSettingsSave();
    const api = new UserAdminApiService();
    const authStore = useAuthStore();
    const { currentUser } = storeToRefs(authStore);

    const users = ref<AdminUser[]>([]);
    const loading = ref(false);
    const loadError = ref<string | null>(null);
    // One busy marker per row — the toggles and the overflow button all
    // belong to the same user, and letting a second write start while the
    // first is in flight is how you get a row that disagrees with the server.
    const busyId = ref<string | null>(null);

    const editOpen = ref(false);
    const editingUser = ref<AdminUser | null>(null);
    const editingUsername = ref('');
    const editingEmail = ref('');
    const savingEdit = ref(false);

    // Create-user dialog state. Fresh draft each open (see onAddClick).
    const createOpen = ref(false);
    const creating = ref(false);
    const createDraft = reactive({
        username: '',
        email: '',
        is_admin: false,
        password: '',
        // Default OFF — the owner's ask was "I should be able to set their
        // password for them", so typing one is the primary path and
        // generate-instead is the opt-out.
        generate: false,
    });
    const createFieldErrors = ref<Record<string, string>>({});
    function clearCreateField(field: 'username' | 'email' | 'password') {
        if (createFieldErrors.value[field]) {
            const next = { ...createFieldErrors.value };
            delete next[field];
            createFieldErrors.value = next;
        }
    }
    const canSubmitCreate = computed(
        () => createDraft.username.trim().length > 0
            && (createDraft.generate || passwordLongEnough(createDraft.password)),
    );

    // Change-password dialog state.
    const passwordOpen = ref(false);
    const passwordTarget = ref<AdminUser | null>(null);
    const passwordDraft = ref('');
    const passwordGenerate = ref(false);
    const passwordError = ref('');
    const savingPassword = ref(false);

    // Generated-password readout, shared by create + change — only shown when
    // the *server* invented the password. A password the admin typed is never
    // echoed back.
    const generatedOpen = ref(false);
    const generatedPassword = ref('');
    const generatedTargetName = ref('');
    const generatedKind = ref<'create' | 'change'>('change');

    const currentUserId = computed(() => currentUser.value?.user_id ?? null);

    async function loadUsers() {
        loading.value = true;
        loadError.value = null;
        try {
            users.value = await api.getAllPagesAsync();
        } catch (err) {
            loadError.value = `Could not load users: ${describeApiError(err)}`;
        } finally {
            loading.value = false;
        }
    }

    async function patch(user: AdminUser, command: Parameters<typeof api.updateAsync>[1]) {
        busyId.value = user.user_id;
        try {
            await api.updateAsync(user.user_id, command);
            await loadUsers();
            // when the admin is editing themselves (rename, email change), the
            // admin-user list refresh above doesn't touch
            // `authStore.currentUser`. Without this refresh the router guard,
            // MainLayout, SettingsShell, and every admin page keep reading a
            // stale `is_admin`/`username`.
            if (user.user_id === currentUser.value?.user_id) {
                await authStore.refreshAsync();
            }
            return true;
        } catch (err) {
            notifyError('Update failed.', err);
            // Re-read so a rejected write (e.g. the last-admin guard) doesn't
            // leave the toggle showing the value the server refused.
            await loadUsers();
            return false;
        } finally {
            busyId.value = null;
        }
    }

    async function onToggleAdmin(user: AdminUser, value: boolean) {
        await patch(user, { is_admin: value });
    }

    async function onToggleActive(user: AdminUser, value: boolean) {
        if (!value) {
            const confirmed = await confirm({
                title: `Deactivate "${user.username}"?`,
                message:
                    `They'll be signed out and won't be able to sign in again `
                    + `until you switch this back on. Nothing they created is `
                    + `removed.`,
                okLabel: 'Deactivate',
                destructive: true,
                persistent: true,
            });
            if (!confirmed) return;
        }
        const ok = await patch(user, { is_active: value });
        if (ok) {
            notifySuccess(value
                    ? `"${user.username}" can sign in again.`
                    : `"${user.username}" is deactivated.`);
        }
    }

    // Finalisation 13-R15 — the server's `clear_image` had no caller.
    async function onRemovePicture(user: AdminUser) {
        const ok = await patch(user, { clear_image: true });
        if (ok) notifySuccess(`Removed "${user.username}"'s picture.`);
    }

    function onEdit(user: AdminUser) {
        editingUser.value = user;
        editingUsername.value = user.username;
        editingEmail.value = user.email ?? '';
        editOpen.value = true;
    }

    async function onSaveEdit() {
        if (!editingUser.value) return;
        savingEdit.value = true;
        const ok = await patch(editingUser.value, {
            username: editingUsername.value.trim(),
            email:
                editingEmail.value.trim() === '' ? null : editingEmail.value.trim()
        });
        savingEdit.value = false;
        if (ok) editOpen.value = false;
    }

    // ── Password ─────────────────────────────────────────────────────
    function onChangePassword(user: AdminUser) {
        passwordTarget.value = user;
        passwordDraft.value = '';
        passwordGenerate.value = false;
        passwordError.value = '';
        passwordOpen.value = true;
    }

    async function onSubmitPassword() {
        const user = passwordTarget.value;
        if (!user) return;
        savingPassword.value = true;
        try {
            const { new_password } = await api.setPasswordAsync(
                user.user_id,
                passwordGenerate.value ? undefined : passwordDraft.value,
            );
            passwordOpen.value = false;
            if (new_password) {
                generatedPassword.value = new_password;
                generatedTargetName.value = user.username;
                generatedKind.value = 'change';
                generatedOpen.value = true;
            } else {
                notifySuccess(`Password changed for "${user.username}".`);
            }
        } catch (err) {
            passwordError.value = fieldError(err, 'password')
                ?? 'Could not change the password.';
        } finally {
            savingPassword.value = false;
        }
    }

    // ── Create / delete ──────────────────────────────────────────────
    function onAddClick() {
        createDraft.username = '';
        createDraft.email = '';
        createDraft.is_admin = false;
        createDraft.password = '';
        createDraft.generate = false;
        createFieldErrors.value = {};
        createOpen.value = true;
    }

    async function onSubmitCreate() {
        if (!canSubmitCreate.value) return;
        creating.value = true;
        createFieldErrors.value = {};
        try {
            const payload: AdminCreateUserCommand = {
                username: createDraft.username.trim(),
                is_admin: createDraft.is_admin,
            };
            const email = createDraft.email.trim();
            if (email.length > 0) payload.email = email;
            if (!createDraft.generate) payload.password = createDraft.password;

            const { new_password } = await api.createAsync(payload);
            createOpen.value = false;
            if (new_password) {
                generatedPassword.value = new_password;
                generatedTargetName.value = payload.username;
                generatedKind.value = 'create';
                generatedOpen.value = true;
            } else {
                notifySuccess(`Created "${payload.username}".`);
            }
            await loadUsers();
        } catch (err) {
            // Server maps username-taken / email-taken to 400 with a friendly
            // detail; validation problems (bad email, weak password) come back
            // as 422 with a per-field errors map. Surface both inline.
            const problem = problemOf(err);
            if (problem?.errors) {
                const next: Record<string, string> = {};
                for (const [field, messages] of Object.entries(problem.errors)) {
                    if (Array.isArray(messages) && messages.length > 0) {
                        next[field] = messages[0]!;
                    }
                }
                createFieldErrors.value = next;
            } else if (problem?.detail?.toLowerCase().includes('username')) {
                createFieldErrors.value = { username: problem.detail };
            } else if (problem?.detail?.toLowerCase().includes('email')) {
                createFieldErrors.value = { email: problem.detail };
            } else {
                notifyError('Could not create user.', err);
            }
        } finally {
            creating.value = false;
        }
    }

    async function onDelete(user: AdminUser) {
        const confirmed = await confirm({
            title: `Delete "${user.username}"?`,
            message:
                `Their sessions, alert preferences and push subscriptions `
                + `will be removed. Household-shared things they touched `
                + `(recipes, shopping lists) stay in the household. `
                + `Deactivate instead if you only want to lock them out.`,
            okLabel: 'Delete',
            destructive: true,
            persistent: true,
        });
        if (!confirmed) return;

        busyId.value = user.user_id;
        try {
            await api.deleteAsync(user.user_id);
            notifySuccess(`Deleted "${user.username}".`);
            await loadUsers();
        } catch (err) {
            notifyError('Delete failed.', err);
        } finally {
            busyId.value = null;
        }
    }

    async function copyGenerated() {
        try {
            await copyToClipboard(generatedPassword.value);
            notifySuccess('Copied to clipboard.');
        } catch (err) {
            notifyError('Could not copy.', err);
        }
    }

    // ── Small local helpers ──────────────────────────────────────────
    type Problem = { errors?: Record<string, string[]>; detail?: string };

    function problemOf(err: unknown): Problem | undefined {
        return (err as { response?: { data?: Problem } })?.response?.data;
    }

    /** First message the server attached to one field, if any. */
    function fieldError(err: unknown, field: string): string | null {
        const problem = problemOf(err);
        const messages = problem?.errors?.[field];
        if (Array.isArray(messages) && messages.length > 0) return messages[0]!;
        return problem?.detail ?? null;
    }


    onMounted(loadUsers);
</script>

<style scoped lang="scss">
    .settings-page { position: relative; }

    .user-list {
        list-style: none;
        margin: 0;
        padding: 0;
        border-top: 1px solid color-mix(in srgb, var(--text-primary) 8%, transparent);
    }
    .user-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 12px 16px;
        padding: 14px 0;
        border-bottom: 1px solid color-mix(in srgb, var(--text-primary) 8%, transparent);
    }
    /* A deactivated account stays fully legible — it's dimmed, not hidden,
       because the admin is looking at this list precisely to find it. */
    .user-row--inactive .user-row__identity { opacity: 0.6; }

    .user-row__identity {
        display: flex;
        align-items: center;
        gap: 12px;
        /* min-width:0 lets the long-email ellipsis actually engage instead of
           the flex item refusing to shrink below its content. */
        min-width: 0;
        flex: 1 1 220px;
    }
    .user-row__names { min-width: 0; }
    .user-row__name {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 6px;
        line-height: 1.3;
    }
    .user-row__email {
        font-size: 0.8125rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .user-row__controls {
        display: flex;
        align-items: center;
        gap: 16px;
        flex: 0 0 auto;
    }

    /* Mobile: the controls drop onto their own full-width line under the
       identity block and spread out, instead of competing with the name for
       horizontal space. */
    @media (max-width: 599px) {
        .user-row__identity { flex: 1 1 100%; }
        .user-row__controls {
            flex: 1 1 100%;
            justify-content: space-between;
            padding-left: 54px; /* line up under the name, past the avatar */
        }
    }

    .generated-password-readout :deep(input) {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        letter-spacing: 0.05em;
    }
</style>
