<template>
    <!-- The router guard owns "signed in"; this only waits for the user row. -->
    <div v-if="currentUser" class="settings-page">
        <SettingsPageHeader title="Appearance" :icon="ICONS.palette" />

        <SettingsSection>
            <template #title>Theme mode</template>

            <div class="appearance-choice">
                <DoraSegmented
                    :model-value="modeDraft"
                    :options="modeOptions"
                    @update:model-value="onModeChange"
                />
            </div>
        </SettingsSection>

        <hr class="settings-divider" />

        <SettingsSection>
            <template #title>Theme</template>

            <div class="theme-grid">
                <button
                    v-for="family in themeFamilies"
                    :key="family.key"
                    type="button"
                    class="theme-card"
                    :class="{ 'theme-card--active': familyDraft === family.key }"
                    @click="onFamilyChange(family)"
                >
                    <BaseTooltip v-if="family.blurb" anchor="top middle" self="bottom middle">
                        {{ family.blurb }}
                    </BaseTooltip>
                    <q-icon
                        v-if="familyDraft === family.key"
                        :name="ICONS.check_circle"
                        size="18px"
                        class="theme-card__badge"
                    />
                    <div class="theme-swatch">
                        <span
                            v-for="(hex, i) in swatchFor(family)"
                            :key="`s-${i}`"
                            class="theme-swatch-strip"
                            :style="{ background: hex }"
                        />
                    </div>
                    <div class="theme-card__label">{{ family.label }}</div>
                </button>
            </div>
        </SettingsSection>

        <hr class="settings-divider" />

        <SettingsSection>
            <template #title>Font family</template>

            <div class="appearance-choice">
                <DoraSegmented
                    :model-value="fontFamilyDraft"
                    :options="fontFamilyOptions"
                    @update:model-value="onFontFamilyChange"
                />
            </div>
        </SettingsSection>

        <hr class="settings-divider" />

        <SettingsSection>
            <template #title>Text size</template>

            <div class="appearance-choice">
                <DoraSegmented
                    :model-value="fontSizeDraft"
                    :options="fontSizeOptions"
                    @update:model-value="onFontSizeChange"
                />
            </div>
        </SettingsSection>

        <!-- Owner call 2026-08-29 — the "Recipe photos" toggle was cut from
             here. It began as a per-user low-bandwidth preference governing
             every recipe photo in the app; by the time it reached this page
             the cookbook had taken photos over via its cards/compact switch
             and cook mode, print and the planner rail had never honoured it,
             so it governed one hero image — and turning it off left a
             same-sized "Photo hidden" box, so it didn't even buy the density
             it claimed. Density on the cookbook is the cards/compact switch;
             there is no second control. -->
    </div>
</template>

<script lang="ts" setup>
    import BaseTooltip from 'src/components/BaseTooltip.vue';
    import { ICONS } from 'src/style/icons';
    import { storeToRefs } from 'pinia';
    import type {
        FontFamilyPreference,
        FontSizePreference,
        ThemePreference
    } from 'src/models/auth';
    import {
        THEMES,
        THEME_FAMILIES,
        familyAndModeOf,
        themeKeyFor,
        osPrefersDarkRef,
        fontFamilyOptions as buildFontFamilyOptions,
        coalesceFontFamily,
        type ThemeFamily,
    } from 'src/services/themeService';
    import { useAuthStore } from 'src/stores/authStore';
    import { ref, watch } from 'vue';
    import { useSettingsSave } from 'src/composables/useSettingsSave';
    import SettingsSection from 'src/components/settings/SettingsSection.vue';
    import SettingsPageHeader from 'src/components/settings/SettingsPageHeader.vue';
    import DoraSegmented, { type DoraSegmentedOption } from 'src/components/settings/DoraSegmented.vue';

    const authStore = useAuthStore();
    const { currentUser } = storeToRefs(authStore);

    const themeFamilies = THEME_FAMILIES;
    type ThemeMode = 'system' | 'light' | 'dark';

    const modeOptions: DoraSegmentedOption<ThemeMode>[] = [
        { label: 'System', value: 'system', icon: ICONS.brightness_auto },
        { label: 'Light', value: 'light', icon: ICONS.light_mode },
        { label: 'Dark', value: 'dark', icon: ICONS.dark_mode },
    ];
    // The 'default' option removes the per-user font override, so the app
    // falls back to its base body font — Nunito (css/app.scss). We label it
    // "Nunito (Default)" so the default is named, not a mystery. The standalone
    // 'nunito' option is intentionally gone: it rendered identically to the
    // default. Options + the `coalesceFontFamily` fold are the shared
    // FU-614 source in themeService (R-003). The compact segmented control
    // shortens "Plus Jakarta Sans" to "Plus Jakarta" via the label override.
    const fontFamilyOptions: DoraSegmentedOption<FontFamilyPreference>[] =
        buildFontFamilyOptions({ plus_jakarta_sans: 'Plus Jakarta' });
    const fontSizeOptions: DoraSegmentedOption<FontSizePreference>[] = [
        { label: 'Small', value: 'sm' },
        { label: 'Medium', value: 'md' },
        { label: 'Large', value: 'lg' },
        { label: 'Extra large', value: 'xl' },
    ];

    function modeAndFamilyForKey(key: string): { mode: ThemeMode; familyKey: string } {
        const decoded = familyAndModeOf(key);
        if (decoded) return { mode: decoded.mode, familyKey: decoded.family.key };
        return { mode: 'system', familyKey: THEME_FAMILIES[0]!.key };
    }

    const initialThemeKey: string = currentUser.value?.theme ?? 'system';
    const initial = modeAndFamilyForKey(initialThemeKey);
    const modeDraft = ref<ThemeMode>(initial.mode);
    const familyDraft = ref<string>(initial.familyKey);

    const osCurrentlyDark = osPrefersDarkRef();

    function swatchFor(family: ThemeFamily): string[] {
        const key = modeDraft.value === 'dark'
            ? family.dark
            : modeDraft.value === 'light'
                ? family.light
                : osCurrentlyDark.value ? family.dark : family.light;
        return THEMES[key]?.swatch ?? [];
    }

    const fontFamilyDraft = ref<FontFamilyPreference>(
        coalesceFontFamily(currentUser.value?.font_family)
    );
    const fontSizeDraft = ref<FontSizePreference>(currentUser.value?.font_size ?? 'md');

    // R-003 / FU-601 — shared save-toast helper (see useSettingsSave).
    const { update } = useSettingsSave();

    watch(currentUser, (u) => {
        if (!u) return;
        const decoded = modeAndFamilyForKey(u.theme);
        modeDraft.value = decoded.mode;
        familyDraft.value = decoded.familyKey;
        fontFamilyDraft.value = coalesceFontFamily(u.font_family);
        fontSizeDraft.value = u.font_size;
    });


    async function onThemeChange(value: ThemePreference) {
        const previous = currentUser.value?.theme ?? 'system';
        const result = await update('Theme updated.', () =>
            authStore.updateMeAsync({ theme: value })
        );
        if (result === null) {
            const decoded = modeAndFamilyForKey(previous);
            modeDraft.value = decoded.mode;
            familyDraft.value = decoded.familyKey;
        }
    }

    async function onModeChange(value: ThemeMode) {
        const family = THEME_FAMILIES.find((f) => f.key === familyDraft.value)
            ?? THEME_FAMILIES[0]!;
        const next = themeKeyFor(value, family);
        modeDraft.value = value;
        await onThemeChange(next);
    }

    async function onFamilyChange(family: ThemeFamily) {
        familyDraft.value = family.key;
        const next = themeKeyFor(modeDraft.value, family);
        await onThemeChange(next);
    }

    async function onFontFamilyChange(value: FontFamilyPreference) {
        const previous = currentUser.value?.font_family ?? 'default';
        fontFamilyDraft.value = value;
        const result = await update('Font updated.', () =>
            authStore.updateMeAsync({ font_family: value })
        );
        if (result === null) fontFamilyDraft.value = previous;
    }

    async function onFontSizeChange(value: FontSizePreference) {
        const previous = currentUser.value?.font_size ?? 'md';
        fontSizeDraft.value = value;
        const result = await update('Text size updated.', () =>
            authStore.updateMeAsync({ font_size: value })
        );
        if (result === null) fontSizeDraft.value = previous;
    }
</script>

<style scoped lang="scss">
    .settings-page {
        display: flex;
        flex-direction: column;
    }

    /* Keeps the inline-flex segmented control hugging its content on the left.
       Without a wrapper the control is a direct child of the section body
       (a column flex, default align-items: stretch) and its background box
       would stretch edge-to-edge — the reported "outline to the page edge". */
    .appearance-choice {
        display: flex;
    }

    .theme-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        gap: 12px;
    }
    .theme-card {
        position: relative;
        appearance: none;
        background: var(--surface-component);
        border: 1.5px solid var(--border-default);
        border-radius: var(--radius-md, 8px);
        padding: 10px;
        text-align: left;
        transition: border-color 120ms ease;
        display: flex;
        flex-direction: column;
        gap: 8px;
        cursor: pointer;
    }
    .theme-card:hover {
        border-color: var(--border-strong);
    }
    .theme-card--active {
        /* Border + badge glyph are both graphics — the 3:1 tier. */
        border-color: var(--accent-mark);
        border-width: 2px;
    }
    .theme-card__badge {
        position: absolute;
        top: 6px;
        right: 6px;
        color: var(--accent-mark);
        background: var(--surface-component);
        border-radius: 50%;
    }
    .theme-swatch {
        display: flex;
        gap: 3px;
        height: 32px;
        border-radius: var(--radius-sm, 4px);
        overflow: hidden;
        background: var(--surface-sunken);
    }
    .theme-swatch-strip {
        flex: 1 1 0;
        height: 100%;
    }
    .theme-card__label {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-primary);
    }
</style>
