<template>
    <nav class="settings-nav-group" :aria-label="label">
        <!-- `headerless` groups still carry a label — it names the group for
             screen readers and identifies it to the mobile tab strip — they
             just don't draw the eyebrow. Used for the standalone Account and
             About entries, which are single destinations rather than
             categories (owner call 2026-08-14). -->
        <!-- The eyebrow is a link to the group's first destination, matching
             the mobile tab strip (owner, 2026-08-17). Same look as before —
             it only gains a hover/focus affordance, since it now goes
             somewhere. -->
        <component
            :is="firstPath ? 'router-link' : 'div'"
            v-if="!headerless"
            :to="firstPath"
            class="settings-nav-group__eyebrow"
            :class="{ 'settings-nav-group__eyebrow--link': !!firstPath }"
        >
            <q-icon v-if="icon" :name="icon" size="12px" class="q-mr-xs" />
            {{ label }}
        </component>
        <ul class="settings-nav-group__list">
            <li v-for="entry in items" :key="entry.path">
                <router-link
                    :to="entry.path"
                    class="settings-nav-group__link"
                    active-class="settings-nav-group__link--active"
                    exact-active-class="settings-nav-group__link--active"
                >
                    <q-icon :name="settingsPageIcon(entry.path)" size="18px" class="settings-nav-group__icon" />
                    <span class="settings-nav-group__label">{{ entry.label }}</span>
                    <span v-if="entry.badge" class="settings-nav-group__badge">{{ entry.badge }}</span>
                </router-link>
            </li>
        </ul>
    </nav>
</template>

<script setup lang="ts">
    import { settingsPageIcon } from 'src/config/settingsPageIcons';
    import { computed } from 'vue';

    // IMPL_PLAN_SETTINGS_REBUILD §2.7 — side-nav group. Drops the card
    // wrapper + captions; eyebrow group header (11px / uppercase /
    // weight 600 / muted); active state = soft brand tint + 3px accent
    // left-edge bar.
    //
    // Owner call 2026-08-17 — **the IA is one flat level everywhere**: a group
    // is a list of destinations, full stop. The old `SettingsNavSubGroup`
    // (an indented list under a non-clickable sub-header, §6.5) is gone along
    // with its last caller — Admin's "System" pile, which is what prompted the
    // rule. Groups are the only nesting; if a group is getting long, it wants
    // splitting into two groups, not a sub-header.
    export interface SettingsNavLeaf {
        path: string;
        label: string;
        // The icon is the page's own, from `settingsPageIcon(path)` (FU-672).
        // Optional attention count — renders a soft pill on the right of the
        // link when > 0 (e.g. outstanding unlinked ingredients). Omitted /
        // 0 ⇒ no badge.
        badge?: number;
    }
    // Retained as an alias so the many `SettingsNavEntry` annotations across
    // the shell keep reading naturally; it is now simply a leaf.
    export type SettingsNavEntry = SettingsNavLeaf;

    const props = defineProps<{
        label: string;
        items: SettingsNavEntry[];
        // `| undefined` so a computed nav-group list can pass an absent icon
        // under exactOptionalPropertyTypes.
        icon?: string | undefined;
        // Suppress the eyebrow header (see template). The label is still
        // required — it's the group's accessible name and its mobile tab id.
        headerless?: boolean | undefined;
    }>();

    // Where the eyebrow link goes. Empty string ⇒ render it as a plain div.
    const firstPath = computed<string>(() => props.items[0]?.path ?? '');
</script>

<style scoped lang="scss">
    .settings-nav-group {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    .settings-nav-group + .settings-nav-group {
        margin-top: 18px;
    }
    .settings-nav-group__eyebrow {
        display: flex;
        align-items: center;
        font-size: 0.6875rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-muted);
        padding: 4px 12px;
        text-decoration: none;
    }
    .settings-nav-group__eyebrow--link {
        border-radius: 6px;
        transition: color 0.18s ease, background-color 0.18s ease;
    }
    .settings-nav-group__eyebrow--link:hover {
        color: var(--text-secondary);
        background: color-mix(in srgb, var(--text-primary) 4%, transparent);
    }
    .settings-nav-group__eyebrow--link:focus-visible {
        outline: 2px solid var(--focus-ring);
        outline-offset: -2px;
    }
    .settings-nav-group__list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .settings-nav-group__link {
        position: relative;
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 12px;
        min-height: 36px;
        border-radius: 6px;
        color: var(--text-primary);
        text-decoration: none;
        font-size: 0.875rem;
        line-height: 1.2;
        transition: background-color 0.18s ease, color 0.18s ease;
    }
    // D-004 on touch (R-085 / FU-877).
    @media (pointer: coarse) {
        .settings-nav-group__link {
            min-height: 44px;
        }
    }
    .settings-nav-group__link:hover {
        background: color-mix(in srgb, var(--text-primary) 4%, transparent);
    }
    .settings-nav-group__link--active {
        background: var(--brand-primary-soft);
        font-weight: 600;
    }
    .settings-nav-group__link--active::before {
        content: '';
        position: absolute;
        left: 0;
        top: 6px;
        bottom: 6px;
        width: 3px;
        border-radius: 2px;
        /* Indicator bar, not text: the 3:1 tier (`--accent-mark`). */
        background: var(--accent-mark);
    }
    .settings-nav-group__icon { flex: 0 0 auto; }
    .settings-nav-group__label {
        flex: 1 1 auto;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    // Attention badge (e.g. outstanding unlinked ingredients). Soft brand
    // pill on the right edge; the whole row also reads as active-tinted via
    // the link states above, so the badge just carries the count.
    .settings-nav-group__badge {
        flex: 0 0 auto;
        min-width: 18px;
        height: 18px;
        padding: 0 6px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 9px;
        background: var(--brand-primary);
        color: var(--text-inverse);
        font-size: 0.6875rem;
        font-weight: 700;
        line-height: 1;
    }
</style>
