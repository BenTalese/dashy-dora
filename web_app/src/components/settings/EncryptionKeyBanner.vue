<template>
    <!-- Shown only once /health has resolved AND the wrapping key is unset.
         Guarding on `flagsLoaded` avoids a flash-of-banner on first paint
         before the flag arrives. Every settings page that stores a secret
         (per-user LLM API key, SMTP password, VAPID private key) renders this
         so the "you must set DORA_SECRET_ENCRYPTION_KEY" requirement is
         obvious *before* a save fails, not only at save time. -->
    <q-banner
        v-if="flagsLoaded && !secretEncryptionConfigured"
        class="dora-bg-warning-soft text-warning enc-banner"
        rounded
    >
        <template #avatar>
            <q-icon :name="ICONS.warning_amber" size="22px" />
        </template>

        <div class="enc-banner__body">
            <div class="text-weight-medium enc-banner__title">
                Secret encryption isn't set up on this install
            </div>
            <p class="enc-banner__text">
                Saving {{ secretLabel }} needs the
                <code>DORA_SECRET_ENCRYPTION_KEY</code> environment variable
                set, so the value can be stored encrypted at rest (a database
                dump or stolen backup then can't leak it). Until it's set, that
                save will be refused. Ollama-only setups that never store a key
                can ignore this.
            </p>

            <p class="enc-banner__text enc-banner__text--muted">
                Set it once at boot (env file, systemd
                <code>EnvironmentFile</code>, Docker/compose env) and restart
                Dora. Generate a key below, or from a shell with:
            </p>
            <code class="enc-banner__cli" tabindex="0">python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"</code>

            <div class="enc-banner__actions">
                <BaseButton
                    variant="secondary"
                    :icon="ICONS.key"
                    label="Generate a key"
                    @click="onGenerate"
                />
            </div>

            <!-- Generated client-side, never sent anywhere. It's a valid
                 Fernet key (32 random bytes, url-safe base64). The operator
                 copies it into their environment by hand. -->
            <div v-if="generatedKey" class="enc-banner__generated">
                <div class="enc-banner__generated-row">
                    <code class="enc-banner__key" tabindex="0">{{ generatedKey }}</code>
                    <BaseButton
                        variant="secondary"
                        :icon="ICONS.content_copy"
                        label="Copy"
                        @click="onCopy"
                    />
                </div>
                <p class="enc-banner__text enc-banner__text--muted enc-banner__generated-note">
                    Dora didn't store this. Paste it into
                    <code>DORA_SECRET_ENCRYPTION_KEY</code> in your environment
                    and restart. Keep it safe: rotating the key later makes
                    every previously-saved secret unreadable (each has to be
                    re-entered).
                </p>
            </div>
        </div>
    </q-banner>
</template>

<script lang="ts" setup>
    import { ref } from 'vue';
    import { useQuasar } from 'quasar';
    import { ICONS } from 'src/style/icons';
    import BaseButton from 'src/components/BaseButton.vue';
    import { useFeatureFlags } from 'src/composables/useFeatureFlags';

    // Tailors only the leading sentence so each page names the secret it
    // stores; the rest of the copy is identical everywhere (owner: "use the
    // same warning banner").
    withDefaults(defineProps<{ secretLabel?: string }>(), {
        secretLabel: 'API keys and passwords',
    });

    const $q = useQuasar();
    const { secretEncryptionConfigured, flagsLoaded } = useFeatureFlags();

    const generatedKey = ref<string>('');

    /** Mint a Fernet-compatible key in the browser: 32 random bytes → url-safe
     *  base64 (with padding), exactly what `Fernet.generate_key()` produces.
     *  Purely local — nothing is transmitted or persisted. */
    function generateFernetKey(): string {
        const bytes = new Uint8Array(32);
        crypto.getRandomValues(bytes);
        let binary = '';
        for (const b of bytes) binary += String.fromCharCode(b);
        // btoa → standard base64; swap to the url-safe alphabet, keep '='.
        return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_');
    }

    function onGenerate() {
        generatedKey.value = generateFernetKey();
    }

    async function onCopy() {
        try {
            await navigator.clipboard.writeText(generatedKey.value);
            $q.notify({
                type: 'positive',
                message: 'Key copied to clipboard.',
            });
        } catch {
            $q.notify({
                type: 'negative',
                message: 'Could not copy. Select the key and copy it manually.',
            });
        }
    }
</script>

<style scoped lang="scss">
    .enc-banner {
        margin-bottom: 20px;
    }
    .enc-banner__body {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .enc-banner__title {
        color: var(--text-primary);
    }
    .enc-banner__text {
        margin: 0;
        color: var(--text-primary);
        font-size: 0.9375rem;
        line-height: 1.5;
        max-width: 70ch;
    }
    .enc-banner__text--muted {
        color: var(--text-secondary);
        font-size: 0.875rem;
    }
    .enc-banner code {
        font-size: 0.85em;
        padding: 1px 6px;
        border-radius: 4px;
        background: var(--surface-sunken);
        color: var(--text-primary);
    }
    .enc-banner__cli {
        display: block;
        padding: 8px 10px;
        border-radius: 6px;
        background: var(--surface-sunken);
        color: var(--text-primary);
        font-size: 0.8125rem;
        line-height: 1.4;
        overflow-x: auto;
        white-space: pre;
        max-width: 100%;
    }
    .enc-banner__actions {
        margin-top: 4px;
    }
    .enc-banner__generated {
        margin-top: 4px;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    .enc-banner__generated-row {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
    }
    .enc-banner__key {
        flex: 1 1 auto;
        min-width: 260px;
        padding: 8px 10px;
        border-radius: 6px;
        background: var(--surface-sunken);
        color: var(--text-primary);
        font-size: 0.8125rem;
        word-break: break-all;
        user-select: all;
    }
    .enc-banner__generated-note {
        margin: 0;
    }
</style>
