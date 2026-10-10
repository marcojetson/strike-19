"""Game entities: tanks, projectiles, air-drop crates, particles and floating text."""
import math
import random

from . import physics
from .physics import WEAPONS, STARTING_AMMO


class Tank:
    WIDTH, HEIGHT = 16, 9
    BARREL_LEN = 13.0
    MAX_HP = 100.0
    TURN_RATE = 46.0        # degrees / second (coarse stick)
    FINE_RATE = 22.0        # degrees / second (d-pad)
    CHARGE_TIME = 1.1       # seconds to reach full power while holding fire
    SHIELD_SECONDS = 5.0    # brawl: real-time shield duration
    SHIELD_TURNS = 3        # classic: shield lasts this many turn transitions

    def __init__(self, x, y, player, color):
        self.x, self.y = float(x), float(y)          # y is the ground contact point
        self.player = player
        self.color = color
        self.angle = 55.0 if player == 0 else 125.0
        self.hp = self.MAX_HP
        self.ammo = dict(STARTING_AMMO)
        self.weapon = 'standard'
        self.charging = False
        self.charge = 0.0
        self.reload = 0.0            # brawl cooldown
        self.shield_charges = 1
        self.shield_timer = 0.0     # brawl: seconds remaining
        self.shield_turns = 0       # classic: turn transitions remaining
        self.hit_flash = 0.0

    @property
    def rect(self):
        return (round(self.x - self.WIDTH / 2), round(self.y) - self.HEIGHT, self.WIDTH, self.HEIGHT)

    @property
    def center(self):
        return self.x, self.y - self.HEIGHT / 2

    def barrel_pivot(self):
        return self.x, self.y - self.HEIGHT + 1

    def muzzle(self):
        radians = math.radians(self.angle)
        px, py = self.barrel_pivot()
        return px + math.cos(radians) * self.BARREL_LEN, py - math.sin(radians) * self.BARREL_LEN

    def rotate(self, direction, rate, dt):
        self.angle = physics.clamp(self.angle + direction * rate * dt, physics.ANGLE_MIN, physics.ANGLE_MAX)

    def update(self, dt):
        if self.reload > 0:
            self.reload = max(0.0, self.reload - dt)
        if self.shield_timer > 0:
            self.shield_timer = max(0.0, self.shield_timer - dt)
        if self.hit_flash > 0:
            self.hit_flash = max(0.0, self.hit_flash - dt)
        if self.charging:
            self.charge = min(1.0, self.charge + dt / self.CHARGE_TIME)

    @property
    def shielded(self):
        return self.shield_timer > 0 or self.shield_turns > 0

    def can_fire(self):
        return self.ammo.get(self.weapon, 0) > 0 and self.reload <= 0

    def consume_ammo(self):
        if self.weapon != 'standard':
            self.ammo[self.weapon] -= 1
            if self.ammo[self.weapon] <= 0:
                self.weapon = 'standard'

    def arm_shield(self, seconds=0.0, turns=0):
        if self.shield_charges > 0 and not self.shielded:
            self.shield_charges -= 1
            self.shield_timer = max(0.0, seconds)
            self.shield_turns = max(0, turns)
            return True
        return False

    def take_damage(self, amount):
        if self.shielded or amount <= 0:
            return 0.0
        applied = min(self.hp, amount)
        self.hp -= applied
        self.hit_flash = 0.3
        return applied


class Projectile:
    def __init__(self, x, y, vx, vy, weapon, owner, split_depth=0):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = float(vx), float(vy)
        self.weapon = weapon
        self.owner = owner
        self.split_depth = split_depth
        self.age = 0.0
        self.trail = []

    @property
    def radius(self):
        return WEAPONS[self.weapon]['radius']

    @property
    def color(self):
        return WEAPONS[self.weapon]['color']

    def step(self, dt, wind):
        self.vx += wind * dt
        self.vy += physics.GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.age += dt
        self.trail.append((self.x, self.y))
        if len(self.trail) > 10:
            self.trail.pop(0)

    def at_apex(self):
        return self.vy >= 0.0 and self.age > 0.15


class Crate:
    SIZE = 9
    REWARDS = ('repair', 'mega', 'cluster', 'laser', 'shield')

    def __init__(self, x, y, reward):
        self.x, self.y = float(x), float(y)
        self.vy = 22.0
        self.reward = reward
        self.landed = False

    def step(self, dt, terrain):
        self.vy = min(55.0, self.vy + 55.0 * dt)
        self.y += self.vy * dt
        ground = terrain.ground_below(self.x, self.y)
        if ground is not None and self.y >= ground:
            self.y, self.landed = float(ground), True
        if self.y > terrain.height:
            self.landed = True


class Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'life', 'max_life', 'color', 'size', 'gravity')

    def __init__(self, x, y, vx, vy, life, color, size=2, gravity=180.0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.color = color
        self.size = size
        self.gravity = gravity

    def step(self, dt):
        self.vy += self.gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        return self.life > 0


class FloatingText:
    __slots__ = ('text', 'x', 'y', 'life', 'max_life', 'color')

    def __init__(self, text, x, y, color, life=1.0):
        self.text, self.x, self.y = text, x, y
        self.life = self.max_life = life
        self.color = color

    def step(self, dt):
        self.y -= 16.0 * dt
        self.life -= dt
        return self.life > 0


def spawn_explosion(particles, x, y, color, count=18, speed=90.0):
    for _ in range(count):
        angle = random.uniform(0, math.tau)
        magnitude = random.uniform(0.3, 1.0) * speed
        particles.append(Particle(x, y, math.cos(angle) * magnitude, math.sin(angle) * magnitude - 20,
                                  random.uniform(0.3, 0.7), color, size=random.choice((1, 2, 2, 3))))


def spawn_smoke(particles, x, y, count=10):
    for _ in range(count):
        particles.append(Particle(x + random.uniform(-3, 3), y + random.uniform(-3, 3),
                                  random.uniform(-14, 14), random.uniform(-30, -8),
                                  random.uniform(0.5, 1.1), (150, 150, 160), size=2, gravity=-12.0))
