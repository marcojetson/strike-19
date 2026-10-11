#!/usr/bin/env python3
"""Pre-render STRIKE-19's sound effects and music to sounds/*.wav (build time only)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # bundled stdlib synth.py

from synth import (SAMPLE_RATE, filtered_noise, kick_drum, layered, music_note,    # noqa: E402
                   note_to_frequency, pad_chord, peak, render_loop, sweep_tone, write_wav)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sounds')


def build():
    os.makedirs(OUT, exist_ok=True)
    beat = 60 / 132
    melody = 'A4 C5 E5 A5 G5 E5 C5 B4'.split()

    sounds = {
        'launch': layered((0, sweep_tone('square', 320, 720, 0.16, 0.18)),
                          (0, filtered_noise(0.1, 0.18, 900, 'highpass'))),
        'explosion': layered((0, filtered_noise(0.55, 0.5, 480, 'lowpass')),
                             (0, sweep_tone('square', 150, 40, 0.5, 0.26))),
        'shield': layered((0, sweep_tone('sine', 260, 880, 0.35, 0.2)),
                          (0.05, sweep_tone('sine', 390, 1320, 0.35, 0.14))),
        'pickup': layered((0, sweep_tone('square', 740, 740, 0.07, 0.16)),
                          (0.07, sweep_tone('square', 988, 988, 0.07, 0.16)),
                          (0.14, sweep_tone('square', 1319, 1319, 0.16, 0.16))),
        'hurt': layered((0, sweep_tone('sawtooth', 340, 90, 0.24, 0.22)),
                        (0, filtered_noise(0.16, 0.2, 300, 'lowpass'))),
        'win': layered(*[(i * 0.13, music_note('square', note_to_frequency(n), 0.13, 0.18))
                         for i, n in enumerate('C5 E5 G5 C6'.split())]
                       + [(0.52, music_note('triangle', note_to_frequency(n), 0.6, 0.12))
                          for n in 'C5 E5 G5 C6'.split()]),
        'lose': layered((0, music_note('triangle', note_to_frequency('G4'), 0.22, 0.18)),
                        (0.20, music_note('triangle', note_to_frequency('E4'), 0.22, 0.18)),
                        (0.40, music_note('triangle', note_to_frequency('C4'), 0.55, 0.18)),
                        (0.40, music_note('triangle', note_to_frequency('E4'), 0.55, 0.10))),
        'draw': layered((0, music_note('square', note_to_frequency('E4'), 0.15, 0.16)),
                        (0.18, music_note('square', note_to_frequency('C4'), 0.32, 0.16))),
    }

    events = [(i * beat, kick_drum(0.4)) for i in range(16)]
    events += [(i * beat, music_note('square', note_to_frequency(note), beat * 0.9, 0.05))
               for i, note in enumerate(melody + melody)]
    events += [(i * beat * 2, music_note('triangle', note_to_frequency(bass), beat * 1.8, 0.06))
               for i, bass in enumerate('A2 A2 F2 G2'.split() * 2)]
    events += [(0, pad_chord('A3 C4 E4', beat * 4, 0.02)),
               (beat * 4, pad_chord('F3 A3 C4', beat * 4, 0.02)),
               (beat * 8, pad_chord('G3 B3 D4', beat * 4, 0.02)),
               (beat * 12, pad_chord('A3 C4 E4', beat * 4, 0.02))]
    sounds['music'] = render_loop(16 * beat, events)

    for name, samples in sounds.items():
        gain = 2.4 if name == 'music' else 2.0
        loudest = peak(samples, gain)
        if loudest > 0.99:
            gain *= 0.99 / loudest
        write_wav(os.path.join(OUT, name + '.wav'), samples, volume=gain)
        print(f'{name}.wav  {len(samples) / SAMPLE_RATE:.2f}s  peak {peak(samples, gain):.2f}')


if __name__ == '__main__':
    build()
