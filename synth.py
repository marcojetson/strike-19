#!/usr/bin/env python3
"""Tiny chiptune synth for pre-rendering game audio to WAV (standard library only).

Import it from a build script that sits beside synth.py:

    from synth import *

    jump = layered((0, sweep_tone('square', 260, 620, 0.12, 0.16)))
    hit = layered((0, sweep_tone('square', 170, 55, 0.22, 0.25)),
                  (0, filtered_noise(0.18, 0.3, 500, 'lowpass')))
    write_wav('sounds/jump.wav', jump, volume=1.0)

    # a seamless 2-bar loop at 120 bpm: (start_seconds, samples) events, tails wrap around
    beat = 60 / 120
    events = [(i * beat, kick_drum()) for i in range(8)]
    events += [(i * beat, music_note('square', note_to_frequency(n), beat * 0.9, 0.05))
               for i, n in enumerate('D4 F4 A4 D5 C5 A4 F4 E4'.split())]
    write_wav('sounds/music.wav', render_loop(8 * beat, events), volume=0.6)

Volumes follow Web Audio conventions (0..1 per voice); write_wav's `volume` is the final mix
gain, so a browser mix can be boosted for a cabinet amp without changing its balance.
Run `python3 synth.py --demo <dir>` to render a few examples.
"""
import math
import random
import struct
import sys
import wave

SAMPLE_RATE = 22050
random.seed(1977)  # deterministic noise so rebuilds produce identical files

__all__ = ['SAMPLE_RATE', 'wave_sample', 'sweep_tone', 'filtered_noise', 'biquad', 'music_note',
           'pad_chord', 'kick_drum', 'note_to_frequency', 'layered', 'render_loop', 'write_wav', 'peak']


def wave_sample(shape, phase):
    """One sample of a naive (chiptune-style, aliasing is fine) waveform, phase in [0, 1)."""
    if shape == 'square':
        return 1.0 if phase < 0.5 else -1.0
    if shape == 'sawtooth':
        return 2.0 * phase - 1.0
    if shape == 'triangle':
        return 1.0 - 4.0 * abs(phase - 0.5)
    return math.sin(2 * math.pi * phase)


def sweep_tone(shape, frequency_from, frequency_to, duration, volume, detune=0.0):
    """Sound-effect tone: exponential pitch sweep + exponential fade (Web Audio playTone style)."""
    count = int(duration * SAMPLE_RATE)
    detune_ratio = 2 ** (detune / 1200)
    phase, samples = 0.0, []
    for i in range(count):
        progress = i / count
        frequency = frequency_from * (max(1, frequency_to) / frequency_from) ** progress * detune_ratio
        gain = volume * (0.001 / volume) ** progress
        samples.append(wave_sample(shape, phase) * gain)
        phase = (phase + frequency / SAMPLE_RATE) % 1.0
    return samples


def biquad(samples, kind, frequency, q=1.0):
    """RBJ biquad filter: 'lowpass', 'highpass' or 'bandpass' (0 dB peak, like Web Audio)."""
    w0 = 2 * math.pi * frequency / SAMPLE_RATE
    cos_w0, alpha = math.cos(w0), math.sin(w0) / (2 * q)
    if kind == 'lowpass':
        b0, b1, b2 = (1 - cos_w0) / 2, 1 - cos_w0, (1 - cos_w0) / 2
    elif kind == 'highpass':
        b0, b1, b2 = (1 + cos_w0) / 2, -(1 + cos_w0), (1 + cos_w0) / 2
    else:
        b0, b1, b2 = alpha, 0.0, -alpha
    a0, a1, a2 = 1 + alpha, -2 * cos_w0, 1 - alpha
    b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0
    x1 = x2 = y1 = y2 = 0.0
    out = []
    for x in samples:
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, x, y1, y
        out.append(y)
    return out


def filtered_noise(duration, volume, frequency, kind='bandpass'):
    """White noise through a filter with an exponential fade: hits, hi-hats, wind, explosions."""
    count = int(duration * SAMPLE_RATE)
    noise = biquad([random.uniform(-1, 1) for _ in range(count)], kind, frequency)
    return [value * volume * (0.001 / volume) ** (i / count) for i, value in enumerate(noise)]


def music_note(shape, frequency, duration, volume, detune=0.0, attack=0.01):
    """Music note: quick attack, hold for 70% of the length, then fade."""
    count = int(duration * SAMPLE_RATE)
    frequency *= 2 ** (detune / 1200)
    hold_until = max(attack, duration * 0.7)
    floor = 0.0001
    phase, samples = 0.0, []
    for i in range(count):
        t = i / SAMPLE_RATE
        if t < attack:
            gain = floor * (volume / floor) ** (t / attack)
        elif t < hold_until:
            gain = volume
        else:
            gain = volume * (floor / volume) ** ((t - hold_until) / (duration - hold_until))
        samples.append(wave_sample(shape, phase) * gain)
        phase = (phase + frequency / SAMPLE_RATE) % 1.0
    return samples


def pad_chord(chord, duration, volume, cutoff=1100):
    """Warm pad: each note of e.g. 'D4 F4 A4' as two detuned saws, slow attack, low-passed."""
    count = int(duration * SAMPLE_RATE)
    mixed = [0.0] * count
    for note_name in chord.split():
        for detune in (-9, 9):
            frequency = note_to_frequency(note_name) * 2 ** (detune / 1200)
            phase = 0.0
            for i in range(count):
                t = i / SAMPLE_RATE
                if t < 0.25:
                    gain = 0.0001 * (volume / 0.0001) ** (t / 0.25)
                elif t < duration * 0.8:
                    gain = volume
                else:
                    gain = volume * (0.0001 / volume) ** ((t - duration * 0.8) / (duration * 0.2))
                mixed[i] += (2.0 * phase - 1.0) * gain
                phase = (phase + frequency / SAMPLE_RATE) % 1.0
    return biquad(mixed, 'lowpass', cutoff)


def kick_drum(volume=0.5):
    count = int(0.14 * SAMPLE_RATE)
    phase, samples = 0.0, []
    for i in range(count):
        frequency = 150 * (40 / 150) ** min(1.0, i / (0.12 * SAMPLE_RATE))
        samples.append(math.sin(2 * math.pi * phase) * volume * (0.001 / volume) ** (i / count))
        phase = (phase + frequency / SAMPLE_RATE) % 1.0
    return samples


def note_to_frequency(note_name):
    """'A4' -> 440.0; accepts sharps and flats like 'C#5', 'Bb3'."""
    letter, rest = note_name[0], note_name[1:]
    accidental = {'#': 1, 'b': -1}.get(rest[0], 0)
    octave = int(rest[-1])
    semitones = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}[letter] + accidental
    return 440 * 2 ** ((12 * (octave + 1) + semitones - 69) / 12)


def layered(*parts):
    """Mix (delay_seconds, samples) parts into one sound effect."""
    length = max(int(delay * SAMPLE_RATE) + len(samples) for delay, samples in parts)
    buffer = [0.0] * length
    for delay, samples in parts:
        start = int(delay * SAMPLE_RATE)
        for i, value in enumerate(samples):
            buffer[start + i] += value
    return buffer


def render_loop(length_seconds, events):
    """Mix (start_seconds, samples) events into a loop; tails past the end wrap to the start,
    so the WAV loops without a click or a gap."""
    buffer = [0.0] * int(length_seconds * SAMPLE_RATE)
    for start_seconds, samples in events:
        start = int(start_seconds * SAMPLE_RATE)
        for i, value in enumerate(samples):
            buffer[(start + i) % len(buffer)] += value
    return buffer


def peak(samples, volume=1.0):
    return max((abs(s) for s in samples), default=0.0) * volume


def write_wav(path, samples, volume=1.0):
    """16-bit mono WAV; `volume` is the final mix gain. Clips at ±1 (check `peak` first)."""
    frames = b''.join(struct.pack('<h', int(max(-1.0, min(1.0, s * volume)) * 32767)) for s in samples)
    with wave.open(str(path), 'wb') as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(SAMPLE_RATE)
        file.writeframes(frames)


def _demo(out_dir):
    import os
    os.makedirs(out_dir, exist_ok=True)
    sounds = {
        'jump': layered((0, sweep_tone('square', 260, 620, 0.12, 0.16))),
        'coin': layered((0, sweep_tone('square', 988, 988, 0.06, 0.12)), (0.06, sweep_tone('square', 1319, 1319, 0.2, 0.12))),
        'explosion': layered((0, filtered_noise(0.6, 0.5, 600, 'lowpass')), (0, sweep_tone('square', 120, 30, 0.5, 0.2))),
    }
    beat = 60 / 120
    melody = 'D4 F4 A4 D5 C5 A4 F4 E4'.split()
    events = [(i * beat, kick_drum()) for i in range(8)]
    events += [(i * beat, music_note('square', note_to_frequency(n), beat * 0.9, 0.06)) for i, n in enumerate(melody)]
    events += [(0, pad_chord('D4 F4 A4', beat * 4, 0.02)), (beat * 4, pad_chord('A3 C#4 E4', beat * 4, 0.02))]
    sounds['music-loop'] = render_loop(8 * beat, events)
    for name, samples in sounds.items():
        write_wav(os.path.join(out_dir, name + '.wav'), samples, volume=1.0)
        print(f'{name}.wav  {len(samples) / SAMPLE_RATE:.2f}s  peak {peak(samples):.2f}')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--demo':
        _demo(sys.argv[2])
    else:
        print(__doc__)
