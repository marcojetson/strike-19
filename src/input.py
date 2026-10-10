"""Two-player arcade input: SDL controllers, raw joysticks and MAME-style keyboard encoders.

Every input maps to (player, action): player 0 is the left/first device, player 1 the second.
Actions are 'left', 'right', 'up', 'down', 'fire', 'weapon', 'shield', 'start', 'back';
start/back are global (player is None). Batocera can deliver one physical press twice, so a
repeat of the same (player, action) within SAME_PRESS_WINDOW_MS counts once, and an action is
released only when every input holding it has let go.
"""
import sys

import pygame

ACTIONS = ('left', 'right', 'up', 'down', 'fire', 'weapon', 'shield', 'start', 'back')

GC_BUTTONS = {
    pygame.CONTROLLER_BUTTON_A: 'fire',
    pygame.CONTROLLER_BUTTON_B: 'weapon',
    pygame.CONTROLLER_BUTTON_X: 'shield',
    pygame.CONTROLLER_BUTTON_Y: 'shield',
    pygame.CONTROLLER_BUTTON_DPAD_UP: 'up',
    pygame.CONTROLLER_BUTTON_DPAD_DOWN: 'down',
    pygame.CONTROLLER_BUTTON_DPAD_LEFT: 'left',
    pygame.CONTROLLER_BUTTON_DPAD_RIGHT: 'right',
    pygame.CONTROLLER_BUTTON_START: 'start',
    pygame.CONTROLLER_BUTTON_BACK: 'back',
}

# keyboard fallback for desktop testing: P1 = WASD/FGH, P2 = arrows/KLJ
KEY_ACTIONS = {
    pygame.K_a: (0, 'left'), pygame.K_d: (0, 'right'), pygame.K_w: (0, 'up'), pygame.K_s: (0, 'down'),
    pygame.K_f: (0, 'fire'), pygame.K_g: (0, 'weapon'), pygame.K_h: (0, 'shield'),
    pygame.K_LEFT: (1, 'left'), pygame.K_RIGHT: (1, 'right'), pygame.K_UP: (1, 'up'), pygame.K_DOWN: (1, 'down'),
    pygame.K_k: (1, 'fire'), pygame.K_l: (1, 'weapon'), pygame.K_j: (1, 'shield'),
    pygame.K_RETURN: (None, 'start'), pygame.K_1: (None, 'start'), pygame.K_2: (None, 'back'),
}


def quit_game():
    pygame.quit()
    sys.exit(0)


def direction_from_axis(x, y, deadzone):
    directions = set()
    if x < -deadzone:
        directions.add('left')
    elif x > deadzone:
        directions.add('right')
    if y < -deadzone:
        directions.add('up')
    elif y > deadzone:
        directions.add('down')
    return directions


class Controls:
    SAME_PRESS_WINDOW_MS = 80
    DEADZONE = 0.5

    def __init__(self, on_press, on_release):
        self.on_press, self.on_release = on_press, on_release
        self.held_by = {}            # (player, action) -> set of sources
        self.last_press_ms = {}
        self.axis_dirs = {}          # player -> set of directions currently held (axes + hat)
        self.axis_values = {}        # player -> [x, y] latest analog values
        self.hat_dirs = {}           # player -> set of directions from a hat
        self.instance_player = {}    # joystick instance_id -> player index
        self.game_controller_ids = set()
        self.devices = []
        self.sdl_controller = self._load_controller_module()
        self.scan()

    @staticmethod
    def _load_controller_module():
        try:
            from pygame._sdl2 import controller
            controller.init()
            return controller
        except Exception:
            return None

    def scan(self):
        pygame.joystick.init()
        self.devices, self.game_controller_ids, self.instance_player = [], set(), {}
        for index in range(pygame.joystick.get_count()):
            player = min(index, 1)
            if self.sdl_controller and self.sdl_controller.is_controller(index):
                pad = self.sdl_controller.Controller(index)
                joystick = pad.as_joystick()
                self.game_controller_ids.add(joystick.get_instance_id())
                self.instance_player[joystick.get_instance_id()] = player
                self.devices.append(pad)
            else:
                joystick = pygame.joystick.Joystick(index)
                joystick.init()
                self.instance_player[joystick.get_instance_id()] = player
                self.devices.append(joystick)

    def player_for(self, instance_id):
        return self.instance_player.get(instance_id, 0)

    def is_held(self, player, action):
        return bool(self.held_by.get((player, action)))

    def press(self, player, action, source):
        key = (player, action)
        duplicate = pygame.time.get_ticks() - self.last_press_ms.get(key, -10_000) < self.SAME_PRESS_WINDOW_MS
        self.held_by.setdefault(key, set()).add(source)
        if self.is_held(None, 'start') and self.is_held(None, 'back'):
            quit_game()
        if not duplicate:
            self.last_press_ms[key] = pygame.time.get_ticks()
            self.on_press(player, action)

    def release(self, player, action, source):
        key = (player, action)
        self.held_by.get(key, set()).discard(source)
        if not self.is_held(player, action):
            self.on_release(player, action)

    def set_axis_directions(self, player, directions):
        previous = self.axis_dirs.get(player, set())
        for direction in directions - previous:
            self.press(player, direction, 'axis')
        for direction in previous - directions:
            self.release(player, direction, 'axis')
        self.axis_dirs[player] = directions

    def recompute_directions(self, player):
        x, y = self.axis_values.get(player, (0.0, 0.0))
        self.set_axis_directions(player, direction_from_axis(x, y, self.DEADZONE) | self.hat_dirs.get(player, set()))

    def handle(self, event):
        if event.type == pygame.QUIT:
            quit_game()
        elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                quit_game()
            mapping = KEY_ACTIONS.get(event.key)
            if mapping:
                player, action = mapping
                (self.press if event.type == pygame.KEYDOWN else self.release)(player, action, ('key', event.key))
        elif event.type in (getattr(pygame, 'CONTROLLERBUTTONDOWN', -1), getattr(pygame, 'CONTROLLERBUTTONUP', -1)):
            action = GC_BUTTONS.get(event.button)
            if action:
                player = self.player_for(event.instance_id)
                source = ('pad', event.instance_id, event.button)
                (self.press if event.type == pygame.CONTROLLERBUTTONDOWN else self.release)(player, action, source)
        elif event.type == getattr(pygame, 'CONTROLLERAXISMOTION', -1):
            player = self.player_for(event.instance_id)
            self._axis_moved(player, event.axis, event.value / 32767)
        elif event.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYAXISMOTION, pygame.JOYHATMOTION):
            if event.instance_id not in self.game_controller_ids:
                self._handle_raw_joystick(event)
        elif event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
            self.scan()

    def _axis_state(self, player, axis, value):
        values = list(self.axis_values.get(player, [0.0, 0.0]))
        values[axis] = value
        self.axis_values[player] = values

    def _axis_moved(self, player, axis, value):
        if axis in (0, 1):
            self._axis_state(player, axis, value)
            self.recompute_directions(player)

    def _handle_raw_joystick(self, event):
        player = self.player_for(event.instance_id)
        if event.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
            action = {0: 'fire', 1: 'weapon', 2: 'shield', 3: 'shield'}.get(event.button)
            if action is None and event.button >= 7:
                action = 'start'
            elif event.button in (6, 8):
                action = 'back'
            if action:
                source = ('joystick', event.instance_id, event.button)
                (self.press if event.type == pygame.JOYBUTTONDOWN else self.release)(player, action, source)
        elif event.type == pygame.JOYAXISMOTION and event.axis in (0, 1):
            self._axis_moved(player, event.axis, event.value)
        elif event.type == pygame.JOYHATMOTION:
            self.hat_dirs[player] = direction_from_axis(event.value[0], event.value[1], 0)
            self.recompute_directions(player)
