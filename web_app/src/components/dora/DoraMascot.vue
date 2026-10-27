<template>
    <div class="dora-mascot">
        <img
            :src="currentFace"
            :alt="`Dora (${connection === 'online' ? mood : connection})`"
            :style="{ width: sizePx, height: sizePx }"
            class="dora-mascot-face"
            draggable="false"
        />
    </div>
</template>

<script lang="ts" setup>
    // Frame controller for the Dora mascot.
    //
    // Each mood has an artwork "config" describing optional overlay frames:
    //   - blink:    eyes-closed flash, used on the ready/happy face only
    //   - talking:  alternate frame for lip-flap while state='talking'
    //   - sparkle:  alternate frame flickered continuously (excitement)
    //   - altIdle:  alternate frame swapped slowly while idle (search/worry)
    //
    // Connection overrides mood entirely:
    //   - offline:  shows the sad-eye error frame, no animation
    //   - sleeping: cycles slowly between sleeping and sleeping-snore
    //
    // The bubble is responsible for choosing what mood/state to pass in —
    // including substituting 'happy' during talking for moods that don't
    // have a talking-overlay artwork (see MOODS_WITH_TALKING_VARIANT in
    // doraTypes). This component just renders what it's told.
    import type {
        DoraConnection,
        DoraMood,
        DoraState,
    } from 'src/components/dora/doraTypes';
    import { computed, onBeforeUnmount, ref, watch } from 'vue';

    import confidentSrc from 'src/assets/dora/dorabot-confident.png';
    import confusedSrc from 'src/assets/dora/dorabot-confused.png';
    import confusedTalkingSrc from 'src/assets/dora/dorabot-confused-talking.png';
    import cuteSrc from 'src/assets/dora/dorabot-cute.png';
    import excitedSrc from 'src/assets/dora/dorabot-excited.png';
    import excitedSparkleSrc from 'src/assets/dora/dorabot-excited-sparkle.png';
    import offlineSrc from 'src/assets/dora/dorabot-fatal-error-or-offline.png';
    import lightbulbSrc from 'src/assets/dora/dorabot-lightbulb-idea-amazed.png';
    import sadSrc from 'src/assets/dora/dorabot-sad-crying.png';
    import sadCryingTalkingSrc from 'src/assets/dora/dorabot-sad-crying-talking.png';
    import blinkSrc from 'src/assets/dora/dorabot-ready-online-blinking.png';
    import happySrc from 'src/assets/dora/dorabot-ready-online.png';
    import talkingSrc from 'src/assets/dora/dorabot-ready-online-talking.png';
    import searchingSrc from 'src/assets/dora/dorabot-searching.png';
    import searchingAltSrc from 'src/assets/dora/dorabot-searching-alt.png';
    import sleepingSrc from 'src/assets/dora/dorabot-sleeping.png';
    import sleepingSnoreSrc from 'src/assets/dora/dorabot-sleeping-snore.png';
    import superExcitedSrc from 'src/assets/dora/dorabot-super-excited.png';
    import superExcitedSparkleSrc from 'src/assets/dora/dorabot-super-excited-sparkle.png';
    import thinkingSrc from 'src/assets/dora/dorabot-thinking.png';
    import worriedSrc from 'src/assets/dora/dorabot-worried.png';
    import worriedAltSrc from 'src/assets/dora/dorabot-worried-alt.png';

    type FrameConfig = {
        base: string;
        blink?: string;
        talking?: string;
        sparkle?: string;
        altIdle?: string;
    };

    const FRAME_CONFIGS: Record<DoraMood, FrameConfig> = {
        happy: { base: happySrc, blink: blinkSrc, talking: talkingSrc },
        confused: { base: confusedSrc, talking: confusedTalkingSrc },
        sad: { base: sadSrc, talking: sadCryingTalkingSrc },
        searching: { base: searchingSrc, altIdle: searchingAltSrc },
        worried: { base: worriedSrc, altIdle: worriedAltSrc },
        excited: { base: excitedSrc, sparkle: excitedSparkleSrc },
        super_excited: { base: superExcitedSrc, sparkle: superExcitedSparkleSrc },
        thinking: { base: thinkingSrc },
        cute: { base: cuteSrc },
        confident: { base: confidentSrc },
        lightbulb: { base: lightbulbSrc },
    };

    // Timing constants. Tuned to read as "alive but not seizure-inducing".
    const BLINK_HOLD_MS = 120;
    const BLINK_INTERVAL_MIN_MS = 2800;
    const BLINK_INTERVAL_MAX_MS = 4600;
    const TALK_FRAME_MS = 150;
    const SPARKLE_FRAME_MS = 380;
    const ALT_IDLE_FRAME_MS = 1800;
    const SLEEP_FRAME_MS = 1600;

    const props = withDefaults(
        defineProps<{
            mood?: DoraMood;
            size?: number;
            state?: DoraState;
            connection?: DoraConnection;
        }>(),
        { mood: 'happy', size: 56, state: 'idle', connection: 'online' }
    );

    const sizePx = computed(() => `${props.size}px`);

    const config = computed<FrameConfig>(() => FRAME_CONFIGS[props.mood]);
    const baseFace = computed<string>(() => {
        if (props.connection === 'offline') return offlineSrc;
        if (props.connection === 'sleeping') return sleepingSrc;
        return config.value.base;
    });

    const currentFace = ref<string>(baseFace.value);

    // Centralised timer slots so we never leak intervals on prop changes or
    // unmount. Each animation owns one slot.
    let blinkTimer: ReturnType<typeof setTimeout> | null = null;
    let talkTimer: ReturnType<typeof setInterval> | null = null;
    let sparkleTimer: ReturnType<typeof setInterval> | null = null;
    let altIdleTimer: ReturnType<typeof setInterval> | null = null;
    let sleepTimer: ReturnType<typeof setInterval> | null = null;

    function clearAll() {
        if (blinkTimer !== null) clearTimeout(blinkTimer);
        for (const t of [talkTimer, sparkleTimer, altIdleTimer, sleepTimer]) {
            if (t !== null) clearInterval(t);
        }
        blinkTimer = null;
        talkTimer = null;
        sparkleTimer = null;
        altIdleTimer = null;
        sleepTimer = null;
    }

    function startSleepCycle() {
        let snoring = false;
        sleepTimer = setInterval(() => {
            snoring = !snoring;
            currentFace.value = snoring ? sleepingSnoreSrc : sleepingSrc;
        }, SLEEP_FRAME_MS);
    }

    function startSparkle(sparkleFrame: string) {
        let sparkling = false;
        sparkleTimer = setInterval(() => {
            sparkling = !sparkling;
            currentFace.value = sparkling ? sparkleFrame : baseFace.value;
        }, SPARKLE_FRAME_MS);
    }

    function startTalk(talkFrame: string) {
        // Kick off immediately so the first frame swap doesn't lag behind the
        // arriving message.
        currentFace.value = talkFrame;
        let mouthOpen = true;
        talkTimer = setInterval(() => {
            mouthOpen = !mouthOpen;
            currentFace.value = mouthOpen ? talkFrame : baseFace.value;
        }, TALK_FRAME_MS);
    }

    function startAltIdle(altFrame: string) {
        let alt = false;
        altIdleTimer = setInterval(() => {
            alt = !alt;
            currentFace.value = alt ? altFrame : baseFace.value;
        }, ALT_IDLE_FRAME_MS);
    }

    function scheduleBlink() {
        const delay =
            BLINK_INTERVAL_MIN_MS +
            Math.random() * (BLINK_INTERVAL_MAX_MS - BLINK_INTERVAL_MIN_MS);
        blinkTimer = setTimeout(() => {
            currentFace.value = FRAME_CONFIGS.happy.blink ?? baseFace.value;
            blinkTimer = setTimeout(() => {
                currentFace.value = baseFace.value;
                scheduleBlink();
            }, BLINK_HOLD_MS);
        }, delay);
    }

    function applyMode() {
        clearAll();
        currentFace.value = baseFace.value;

        // Connection overrides take priority — when offline or sleeping we
        // don't run any mood-based animation.
        if (props.connection === 'offline') return;
        if (props.connection === 'sleeping') {
            startSleepCycle();
            return;
        }

        const cfg = config.value;

        // Sparkle (excitement) is continuous — overrides talking. The bubble
        // forces mood→happy during talking for these anyway, so they only
        // sparkle once Dora has finished saying her piece.
        if (cfg.sparkle) {
            startSparkle(cfg.sparkle);
            return;
        }

        // Talking variant exists → play lip-flap on the mood's own face.
        if (props.state === 'talking' && cfg.talking) {
            startTalk(cfg.talking);
            return;
        }

        // Idle: optional slow alt cycle + optional blink. Blink only on the
        // ready/happy face (the only mood with a matching blink artwork).
        if (cfg.altIdle) {
            startAltIdle(cfg.altIdle);
        }
        if (cfg.blink && props.mood === 'happy') {
            scheduleBlink();
        }
    }

    watch(
        () => [props.mood, props.state, props.connection] as const,
        applyMode,
        { immediate: true }
    );

    onBeforeUnmount(clearAll);
</script>

<style scoped>
    .dora-mascot {
        position: relative;
        display: inline-flex;
        line-height: 0;
    }
    .dora-mascot-face {
        object-fit: contain;
        user-select: none;
        -webkit-user-drag: none;
    }
</style>
