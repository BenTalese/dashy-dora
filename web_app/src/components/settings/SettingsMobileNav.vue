<template>
    <!--
        IMPL_PLAN_SETTINGS_REBUILD §6.3 (user pick: top tab strip) — the
        mobile (<md) settings nav. Row of group tabs along the top; the
        selected group reveals its destinations as a horizontally-scrolling
        chip strip below. Replaces Phase 3's placeholder horizontal-scroll of
        the desktop sidebar. The desktop sidebar (SettingsNavGroup) is shown
        instead at >=md by the shell.
    -->
    <nav class="settings-mnav" aria-label="Settings sections">
        <div class="settings-mnav__groups" role="tablist">
            <button
                v-for="group in groups"
                :key="group.label"
                type="button"
                role="tab"
                class="settings-mnav__group"
                :class="{ 'settings-mnav__group--active': group.label === activeLabel }"
                :aria-selected="group.label === activeLabel"
                @click="onGroupTap(group)"
            >
                <q-icon v-if="group.icon" :name="group.icon" size="14px" class="q-mr-xs" />
                {{ group.label }}
            </button>
        </div>

        <!-- A single-destination group (Account, About) is its own tab — the
             one chip underneath just repeated the tab's label as a second
             button to press, which read as a stray sub-item (owner,
             2026-08-17). Tapping the tab navigates there instead, so the
             strip is suppressed rather than shown with one entry. -->
        <div v-if="activeLeaves.length > 1" class="settings-mnav__chips">
            <router-link
                v-for="leaf in activeLeaves"
                :key="leaf.path"
                :to="leaf.path"
                class="settings-mnav__chip"
                active-class="settings-mnav__chip--active"
                exact-active-class="settings-mnav__chip--active"
            >
                <q-icon :name="leaf.icon" size="16px" class="q-mr-xs" />
                {{ leaf.label }}
                <span v-if="leaf.badge" class="settings-mnav__chip-badge">{{ leaf.badge }}</span>
            </router-link>
        </div>
    </nav>
</template>

<script setup lang="ts">
    import type {
        SettingsNavEntry,
        SettingsNavLeaf,
    } from 'src/components/settings/SettingsNavGroup.vue';
    import { computed, ref, watch } from 'vue';
    import { useRoute, useRouter } from 'vue-router';

    export interface SettingsNavGroupDef {
        label: string;
        icon?: string;
        items: SettingsNavEntry[];
        // Desktop-only: suppresses the sidebar eyebrow. The mobile strip still
        // shows the group as a tab — it needs one per group to reach the
        // destinations underneath.
        headerless?: boolean;
    }

    const props = defineProps<{ groups: SettingsNavGroupDef[] }>();

    const route = useRoute();

    // Every group is a flat list of destinations now (the sub-header level was
    // retired 2026-08-17 — see SettingsNavGroup), so this is a plain read.
    // Kept as a named function because the tab logic below leans on it three
    // times and "the leaves of a group" is the concept, not the field.
    function leavesOf(group: SettingsNavGroupDef): SettingsNavLeaf[] {
        return group.items;
    }

    // Default the open tab to whichever group owns the current route, so a
    // deep link / redirect lands with the right strip already showing.
    function groupOwningRoute(): string {
        const match = props.groups.find((g) =>
            leavesOf(g).some((leaf) => leaf.path === route.path),
        );
        return match?.label ?? props.groups[0]?.label ?? '';
    }

    const activeLabel = ref(groupOwningRoute());

    // Follow route changes (e.g. the user taps a chip, or navigates from
    // elsewhere) so the active tab tracks where they actually are.
    watch(
        () => route.path,
        () => { activeLabel.value = groupOwningRoute(); },
    );

    // Tapping a group heading navigates to that group's first destination
    // (owner, 2026-08-17) — leaving the user parked on the previous page
    // while the strip changed underneath them was the confusing half. The
    // route watch above then syncs `activeLabel`, so this only has to set it
    // for the (impossible-in-practice) empty-group case.
    const router = useRouter();
    function onGroupTap(group: SettingsNavGroupDef) {
        activeLabel.value = group.label;
        const first = leavesOf(group)[0];
        if (first && first.path !== route.path) void router.push(first.path);
    }

    const activeLeaves = computed<SettingsNavLeaf[]>(() => {
        const group = props.groups.find((g) => g.label === activeLabel.value);
        return group ? leavesOf(group) : [];
    });
</script>

<style scoped lang="scss">
    .settings-mnav {
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    .settings-mnav__groups {
        display: flex;
        gap: 4px;
        overflow-x: auto;
        scrollbar-width: none;
        border-bottom: 1px solid color-mix(in srgb, var(--text-primary) 8%, transparent);
    }
    .settings-mnav__groups::-webkit-scrollbar { display: none; }
    .settings-mnav__group {
        all: unset;
        display: inline-flex;
        align-items: center;
        white-space: nowrap;
        cursor: pointer;
        padding: 8px 12px;
        /* D-004 — the tab is now a navigation control in its own right (it
           carries you to the group's first page, and for Account/About it is
           the only way there), so it earns the 44px touch floor. Was 38px. */
        min-height: 44px;
        /* `all: unset` also resets box-sizing to content-box, which turned
           the 44px floor into a 62px tab (measured). */
        box-sizing: border-box;
        line-height: 1.3;
        font-size: 0.8125rem;
        font-weight: 600;
        color: var(--text-secondary);
        border-bottom: 2px solid transparent;
        margin-bottom: -1px;
    }
    .settings-mnav__group:focus-visible {
        outline: 2px solid var(--ring-focus);
        outline-offset: -2px;
    }
    .settings-mnav__group--active {
        color: var(--text-primary);
        border-bottom-color: var(--accent-mark);
    }
    .settings-mnav__chips {
        display: flex;
        gap: 6px;
        overflow-x: auto;
        scrollbar-width: none;
        padding-bottom: 2px;
    }
    .settings-mnav__chips::-webkit-scrollbar { display: none; }
    .settings-mnav__chip {
        display: inline-flex;
        align-items: center;
        white-space: nowrap;
        text-decoration: none;
        padding: 6px 12px;
        border-radius: 999px;
        font-size: 0.8125rem;
        color: var(--text-primary);
        background: color-mix(in srgb, var(--text-primary) 5%, transparent);
        transition: background-color 0.18s ease, color 0.18s ease;
    }
    .settings-mnav__chip--active {
        background: var(--brand-primary-soft);
        font-weight: 600;
    }
    /* D-004 — the chip is 32px tall; a finger gets the 44px floor. Pointer, not
       width (R-085): a narrow desktop window keeps the compact chip. */
    @media (pointer: coarse) {
        .settings-mnav__chip {
            min-height: 44px;
        }
    }
    .settings-mnav__chip-badge {
        margin-left: 6px;
        min-width: 16px;
        height: 16px;
        padding: 0 5px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
        background: var(--brand-primary);
        color: var(--text-inverse);
        font-size: 0.625rem;
        font-weight: 700;
        line-height: 1;
    }
</style>
