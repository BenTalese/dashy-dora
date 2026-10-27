<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Voice (Piper TTS)"
            description="Where the server finds Piper, the offline engine behind Dora's voice. Desktop and Docker builds set this automatically."
            :icon="ICONS.record_voice_over"
        />

        <template v-if="ready">
            <SettingsSection>
                <template #title>How Dora's voice works</template>
                <template #description>
                    The engine is set here. Each person picks their voice in
                    their own Voice settings.
                </template>

                <ul class="voice-intro">
                    <li>
                        <strong>The engine (here).</strong> Piper is a small,
                        offline neural text-to-speech that runs on the server's
                        CPU. If Piper can't be found, Dora uses the browser's
                        built-in voice.
                    </li>
                    <li>
                        <strong>The voice.</strong> Picked per person on
                        <router-link to="/settings/voice">Voice
                        settings</router-link>.
                    </li>
                </ul>
            </SettingsSection>

            <SettingsSection>
                <template #title>Piper program</template>
                <template #description>
                    The path to the <code>piper</code> executable on the server.
                    Leave blank to search the system <code>PATH</code> (which
                    works after <code>pip install piper-tts</code>).
                </template>

                <SettingsRow label="Executable path" stacked>
                    <q-input
                        v-model="draft.piper_bin"
                        outlined dense clearable
                        placeholder="/usr/local/bin/piper"
                        @blur="() => onSaveField('piper_bin')"
                    />
                </SettingsRow>
            </SettingsSection>

            <SettingsSection>
                <template #title>Voice models folder</template>
                <template #description>
                    The folder holding the pre-shipped <code>.onnx</code> voice
                    files. Leave blank unless you use a custom folder.
                </template>

                <SettingsRow label="Bundled voice folder" stacked>
                    <q-input
                        v-model="draft.piper_bundled_voice_dir"
                        outlined dense clearable
                        placeholder="/opt/dora/voices"
                        @blur="() => onSaveField('piper_bundled_voice_dir')"
                    />
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

    type VoiceField = 'piper_bin' | 'piper_bundled_voice_dir';

    const { draft, ready, save } = useAppSettingDrafts({ piper_bin: '', piper_bundled_voice_dir: '' });

    function onSaveField(field: VoiceField) {
        void save({ [field]: (draft[field] ?? '').trim() }, 'Voice settings saved.');
    }
</script>

<style scoped lang="scss">
    .voice-intro {
        margin: 0;
        padding-left: 20px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        max-width: 60ch;
        color: var(--text-secondary);
        font-size: 0.875rem;
        line-height: 1.5;
    }
</style>
