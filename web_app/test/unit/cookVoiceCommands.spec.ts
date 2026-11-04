// @vitest-environment jsdom
// Cook mode's spoken-command mapping (FU-942 / CHUNK_04 §D) — the
// owner-specified semantics of 2026-09-03.
import { describe, expect, it } from 'vitest';

import { parseCookVoiceCommand } from 'src/composables/useCookVoice';

describe('parseCookVoiceCommand', () => {
    it.each([
        ['Next', 'next'],
        ['go back', 'previous'],
        ['say it again', 'repeat'],
        ['what do I need', 'ingredients'],
        ['tools', 'tools'],
        ['start timer', 'startTimer'],
        ['pause timer', 'pauseTimer'],
        ['reset timer', 'resetTimer'],
        ['quit', 'exit'],
        ['be quiet', 'stop'],
    ] as const)('"%s" → %s', (said, command) => {
        expect(parseCookVoiceCommand(said)).toBe(command);
    });

    it('treats "stop timer" as the timer verb, not the bare "stop"', () => {
        expect(parseCookVoiceCommand('stop timer')).toBe('pauseTimer');
        expect(parseCookVoiceCommand('stop')).toBe('stop');
    });

    it('never reads "stop" as leaving; only "exit" / "quit" leave', () => {
        expect(parseCookVoiceCommand('stop')).not.toBe('exit');
        expect(parseCookVoiceCommand('exit')).toBe('exit');
    });

    it('matches whole words only', () => {
        // "nextdoor" is not "next", "backing" is not "back".
        expect(parseCookVoiceCommand('the nextdoor neighbour')).toBeNull();
        expect(parseCookVoiceCommand('backing tray')).toBeNull();
    });

    it('ignores kitchen chatter', () => {
        expect(parseCookVoiceCommand('can you pass the salt')).toBeNull();
        expect(parseCookVoiceCommand('')).toBeNull();
    });
});
