#!/usr/bin/env python3
"""Headless smoke test: pure-logic checks plus a scripted play-through.

No display, audio or external dependencies (SDL dummy drivers), so it runs over SSH:

    python3 tests/smoke_test.py
"""
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GAME_DIR)

import pygame                                                                       # noqa: E402

from src import physics, terrain as terrain_mod                                     # noqa: E402
from src.entities import Tank                                                       # noqa: E402
from src.physics import WEAPONS                                                     # noqa: E402


def check_physics():
    vx, vy = physics.muzzle_velocity(45.0, 1.0)
    assert vx > 0 and vy < 0, '45 degrees fires up and to the right'
    assert physics.damage_falloff(0, 12, 26) == 26
    assert physics.damage_falloff(12, 12, 26) == 0.0
    # every weapon's damage blast must cover its hit window, or a registered hit deals nothing
    for name, stats in WEAPONS.items():
        assert stats['blast'] >= stats['radius'] + Tank.WIDTH / 2, name


def check_terrain():
    t = terrain_mod.Terrain(160, 100, seed=3)
    top = t.ground_below(80, 0)
    assert top is not None and t.is_solid(80, top)
    t.carve(80, top + 5, 12)
    assert not t.is_solid(80, top + 1), 'crater should remove ground'
    assert t.ground_below(80, top + 1) is not None, 'ground should remain below the crater'


def load_game():
    pygame.init()
    pygame.display.set_mode((320, 180))
    path = os.path.join(GAME_DIR, 'strike-19.pygame')
    loader = importlib.machinery.SourceFileLoader('strike_19_game', path)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    game = importlib.util.module_from_spec(spec)
    loader.exec_module(game)
    return game


def check_input():
    from src.input import Controls

    pygame.init()
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as handle:
        json.dump({'1': {'buttons': {'fire': 1, 'shield': [0, 3], 'start': 9, 'back': 8}},
                   '2': {'invert': 'y', 'buttons': {'fire': 1}}}, handle)
        config = handle.name

    pressed = []
    controls = Controls(lambda p, a: pressed.append((p, a)), lambda p, a: None, config_path=config)
    controls.instance_player = {0: 0, 1: 1}          # pretend both pads are connected

    def event(kind, **kwargs):
        return pygame.event.Event(kind, **kwargs)

    controls.handle(event(pygame.JOYAXISMOTION, instance_id=0, axis=1, value=-1.0))
    assert (0, 'up') in pressed, pressed            # normal pad: raw up is -1
    controls.handle(event(pygame.JOYAXISMOTION, instance_id=1, axis=1, value=1.0))
    assert (1, 'up') in pressed, pressed            # inverted pad: raw up is +1, still 'up'
    assert (1, 'down') not in pressed, pressed
    controls.handle(event(pygame.JOYBUTTONDOWN, instance_id=0, button=1))
    assert (0, 'fire') in pressed, pressed          # A (index 1) fires
    controls.handle(event(pygame.JOYBUTTONDOWN, instance_id=0, button=0))
    controls.handle(event(pygame.JOYBUTTONDOWN, instance_id=1, button=3))
    assert (0, 'shield') in pressed and (1, 'shield') in pressed, pressed  # X and Y
    controls.handle(event(pygame.JOYBUTTONDOWN, instance_id=0, button=9))
    assert (None, 'start') in pressed, pressed
    controls.handle(event(pygame.JOYBUTTONUP, instance_id=0, button=9))
    controls.handle(event(pygame.JOYBUTTONDOWN, instance_id=0, button=8))
    assert (None, 'back') in pressed, pressed

    # keyboard fallback must be ignored while real pads are present (arcade encoders emulate keys)
    keys = []
    keyboard = Controls(lambda p, a: keys.append((p, a)), lambda p, a: None)
    real_count = pygame.joystick.get_count
    try:
        pygame.joystick.get_count = lambda: 0
        keyboard.handle(event(pygame.KEYDOWN, key=pygame.K_UP))
        assert (1, 'up') in keys, keys
        keys.clear()
        pygame.joystick.get_count = lambda: 2
        keyboard.handle(event(pygame.KEYDOWN, key=pygame.K_DOWN))
        assert not keys, keys
    finally:
        pygame.joystick.get_count = real_count
    os.unlink(config)


def check_play_through():
    game = load_game()
    game.start_game('classic')
    assert game.current_screen == 'play'
    p2 = game.state['tanks'][1]

    game.resolve_explosion(*p2.center, 'standard', 0)
    assert p2.hp < p2.MAX_HP, 'a direct hit must deal damage'

    p2.arm_shield(turns=1)
    hp = p2.hp
    game.resolve_explosion(*p2.center, 'standard', 0)
    assert p2.hp == hp, 'a shielded tank takes no damage'

    for _ in range(120):
        game.update(1 / 60)
        game.render()
    assert game.current_screen in ('play', 'over')


def main():
    check_physics()
    check_terrain()
    check_input()
    check_play_through()
    print('smoke ok')


if __name__ == '__main__':
    main()
