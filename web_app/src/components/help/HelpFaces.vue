<template>
    <!-- Dora's expressions, as a tile per mood. -->
    <ul class="help-faces" aria-label="Dora's faces">
        <li v-for="face in FACES" :key="face.mood" class="help-faces__tile">
            <DoraMascot :mood="face.mood" :size="56" />
            <span class="help-faces__label">{{ face.label }}</span>
            <span class="help-faces__when">{{ face.when }}</span>
        </li>
    </ul>
</template>

<script setup lang="ts">
    import DoraMascot from 'src/components/dora/DoraMascot.vue';
    import type { DoraMood } from 'src/components/dora/doraTypes';

    const FACES: { mood: DoraMood; label: string; when: string }[] = [
        { mood: 'happy', label: 'Happy', when: 'Resting' },
        { mood: 'thinking', label: 'Thinking', when: 'Working on a reply' },
        { mood: 'searching', label: 'Searching', when: 'Looking up your data' },
        { mood: 'lightbulb', label: 'Lightbulb', when: 'Has an idea' },
        { mood: 'confident', label: 'Confident', when: 'A direct answer' },
        { mood: 'excited', label: 'Excited', when: 'Something good happened' },
        { mood: 'super_excited', label: 'Super excited', when: 'A compliment, or big news' },
        { mood: 'cute', label: 'Cute', when: 'Hellos, goodbyes, banter' },
        { mood: 'worried', label: 'Worried', when: 'Something needs you' },
        { mood: 'confused', label: 'Confused', when: 'Did not quite understand' },
        { mood: 'sad', label: 'Sad', when: 'Something failed' },
    ];
</script>

<style scoped lang="scss">
    .help-faces {
        list-style: none;
        margin: var(--space-3) 0 0;
        padding: 0;
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
        gap: var(--space-3);
    }
    .help-faces__tile {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        padding: var(--space-3) var(--space-2);
        border-radius: var(--radius-lg);
        background: var(--surface-sunken);
        text-align: center;
    }
    .help-faces__label {
        margin-top: var(--space-1);
        font-size: var(--font-size-sm);
        font-weight: 600;
    }
    .help-faces__when {
        font-size: var(--font-size-xs);
        color: var(--text-muted);
    }
</style>
