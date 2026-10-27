<template>
    <div class="settings-page">
        <SettingsPageHeader
            title="Image quality"
            description="How Dora encodes photos you upload. Applies to new uploads only."
            :icon="ICONS.image"
        />

        <template v-if="ready">
            <!-- Applied at upload time via the shared `processImageFile`
                 helper, so every upload surface picks these up automatically.
                 Forward-only — existing images are never re-encoded. -->
            <SettingsSection>
                <SettingsRow inline>
                    <template #label>
                        JPEG/WebP quality
                        <InfoTip label="JPEG and WebP quality">
                            30 compresses hard and you can see it; 85 (the
                            default) is visually indistinguishable from the
                            original; 100 barely compresses at all.
                        </InfoTip>
                    </template>
                    <!-- `width` + `max-width`, never a `min-width` floor: an
                         inline row caps its control at 55% of a 375px screen,
                         and a floor wider than that runs the track off the
                         right edge (the same fix the settings selects took on
                         2026-09-03). -->
                    <q-slider
                        v-model="draft.image_quality"
                        :min="30"
                        :max="100"
                        :step="1"
                        label
                        label-always
                        color="primary"
                        style="width: 220px; max-width: 100%"
                        @change="onSave"
                    />
                </SettingsRow>
                <SettingsRow inline>
                    <template #label>
                        Longest edge
                        <InfoTip label="Longest edge">
                            Photos bigger than this on their longest side are
                            scaled down before encoding. 1920 (the default) is
                            Full-HD; 1280 is a disk-conscious floor.
                        </InfoTip>
                    </template>
                    <q-input
                        v-model.number="draft.image_max_dimension"
                        type="number"
                        outlined
                        dense
                        suffix="px"
                        style="max-width: 150px"
                        :min="512"
                        :max="8192"
                        @blur="onSave"
                    />
                </SettingsRow>
            </SettingsSection>
        </template>
    </div>
</template>

<script lang="ts" setup>
    // 2026-08-23 owner feedback: the two image-encode knobs used to sit at the
    // bottom of Backup & Restore, which is about backups, not uploads. They are
    // their own install-wide surface now.
    //
    // 2026-09-03 owner feedback: they save on change like every other settings
    // page, rather than behind a Save/Discard pair. The pair existed so a
    // slider drag wouldn't PATCH per pixel; `@change` is the seam for that,
    // since Quasar fires it on release, not on every step.
    import { ICONS } from 'src/style/icons';
    import { useAppSettingDrafts } from 'src/composables/useAppSettingDrafts';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsRow from 'src/components/settings/SettingsRow.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import InfoTip from 'src/components/help/InfoTip.vue';
    import { refreshImagePolicy } from 'src/composables/useImagePolicy';

    const { draft, ready, save } = useAppSettingDrafts({ image_quality: 85, image_max_dimension: 1920 });

    function onSave() {
        void save(
            {
                image_quality: Number(draft.image_quality),
                image_max_dimension: Number(draft.image_max_dimension),
            },
            'Image settings saved. They apply to new uploads; existing images are unchanged.',
            refreshImagePolicy,
        );
    }
</script>

<style scoped lang="scss">
</style>
