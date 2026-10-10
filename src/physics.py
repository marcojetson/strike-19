"""Trajectory math, wind and weapon ballistics for STRIKE-19 (pure, no pygame)."""
import math

GRAVITY = 260.0            # px/s^2 in logical screen units (y axis points down)
WIND_MAX = 60.0            # px/s^2 horizontal acceleration
MUZZLE_MIN = 120.0
MUZZLE_MAX = 340.0
ANGLE_MIN, ANGLE_MAX = 8.0, 172.0    # barrel always points upward-ish (screen convention)
CLUSTER_FRAGMENTS = 5

# radius = terrain blast, blast = damage radius (must be >= radius + tank half-width so a
# registered hit always deals damage), damage at centre, muzzle speed multiplier.
WEAPONS = {
    'standard': {'radius': 16.0, 'blast': 34.0, 'damage': 32.0, 'speed': 1.00, 'color': (240, 224, 120)},
    'mega':     {'radius': 26.0, 'blast': 52.0, 'damage': 55.0, 'speed': 0.85, 'color': (255, 120, 70)},
    'cluster':  {'radius': 12.0, 'blast': 26.0, 'damage': 18.0, 'speed': 1.00, 'color': (150, 210, 255)},
    'laser':    {'radius': 14.0, 'blast': 30.0, 'damage': 40.0, 'speed': 1.00, 'color': (110, 255, 170)},
}
STARTING_AMMO = {'standard': 999, 'mega': 3, 'cluster': 0, 'laser': 0}


def clamp(value, low, high):
    return max(low, min(high, value))


def muzzle_velocity(angle_deg, power):
    """power in 0..1 -> (vx, vy) in screen coordinates (up is negative y)."""
    speed = MUZZLE_MIN + (MUZZLE_MAX - MUZZLE_MIN) * clamp(power, 0.0, 1.0)
    radians = math.radians(clamp(angle_deg, ANGLE_MIN, ANGLE_MAX))
    return math.cos(radians) * speed, -math.sin(radians) * speed


def random_wind(rng, strength=1.0):
    return rng.uniform(-WIND_MAX, WIND_MAX) * strength


def damage_falloff(distance, radius, max_damage, min_fraction=0.3):
    """Linear falloff from centre; 0 outside the blast radius."""
    if distance >= radius:
        return 0.0
    return max_damage * (1.0 - (1.0 - min_fraction) * distance / radius)


def distance(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


if __name__ == '__main__':
    vx, vy = muzzle_velocity(45.0, 1.0)
    assert vx > 0 and vy < 0, '45 degrees fires up and to the right'
    assert muzzle_velocity(45.0, 0.0)[0] < vx, 'more power means more speed'
    assert abs(damage_falloff(0, 12, 26) - 26) < 1e-9
    assert damage_falloff(12, 12, 26) == 0.0
    assert 0 < damage_falloff(6, 12, 26) < 26
    assert 0 <= random_wind(__import__('random').Random(1), 0.0) == 0.0
    print('physics ok')
