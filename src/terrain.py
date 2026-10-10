"""Procedural, destructible bitmap terrain (heightmap + crater carving)."""
import random

import pygame

GRASS = (86, 170, 74)
GRASS_DARK = (58, 132, 56)
DIRT = (122, 82, 52)
SOLID_ALPHA = 60


class Terrain:
    """A full-screen SRCALPHA surface: opaque pixels are ground, transparent is air.

    Collision is a simple per-pixel alpha test (few projectiles per frame, so cheap).
    Craters are drawn with an alpha-0 circle, which overwrites those pixels to transparent."""

    def __init__(self, width, height, base_fraction=0.62, seed=None):
        self.width, self.height = width, height
        self.base_fraction = base_fraction
        self.surface = pygame.Surface((width, height), pygame.SRCALPHA)
        self.generate(seed)

    # --- generation ------------------------------------------------------
    def _heightmap(self, rng):
        size = 1
        while size < self.width:
            size *= 2
        base = self.height * self.base_fraction
        heights = [0.0] * (size + 1)
        heights[0] = base + rng.uniform(-30, 30)
        heights[size] = base + rng.uniform(-30, 30)
        step, scale = size, 42.0
        while step > 1:
            half = step // 2
            for i in range(half, size, step):
                heights[i] = (heights[i - half] + heights[i + half]) / 2 + rng.uniform(-1, 1) * scale
            step, scale = half, scale * 0.6
        heights = heights[:self.width]
        low, high = self.height * 0.20, self.height - 12
        span = max(heights) - min(heights) or 1.0
        return [int(low + (h - min(heights)) / span * (high - low)) for h in heights]

    def generate(self, seed=None):
        rng = random.Random(seed)
        heights = self._heightmap(rng)
        self.surface.fill((0, 0, 0, 0))
        for x, top in enumerate(heights):
            pygame.draw.line(self.surface, GRASS, (x, top), (x, top + 1))
            pygame.draw.line(self.surface, GRASS_DARK, (x, top + 2), (x, top + 4))
            pygame.draw.line(self.surface, DIRT, (x, top + 5), (x, self.height))
        return heights

    # --- destruction / queries ------------------------------------------
    def carve(self, cx, cy, radius):
        pygame.draw.circle(self.surface, (0, 0, 0, 0), (int(cx), int(cy)), max(1, int(radius)))

    def is_solid(self, x, y):
        xi, yi = int(x), int(y)
        if xi < 0 or xi >= self.width or yi < 0 or yi >= self.height:
            return False
        return self.surface.get_at((xi, yi))[3] > SOLID_ALPHA

    def ground_below(self, x, y):
        xi = int(x)
        if xi < 0 or xi >= self.width:
            return None
        surface = self.surface
        for yi in range(max(0, int(y)), self.height):
            if surface.get_at((xi, yi))[3] > SOLID_ALPHA:
                return yi
        return None


if __name__ == '__main__':
    import os
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    pygame.init()
    pygame.display.set_mode((10, 10))
    t = Terrain(160, 100, seed=3)
    ground = [y for y in range(100) if t.is_solid(80, y)]
    assert ground, 'terrain should be solid somewhere in a column'
    top = t.ground_below(80, 0)
    assert top == ground[0] and t.is_solid(80, top)
    t.carve(80, top + 5, 12)
    assert not t.is_solid(80, top + 1), 'crater should remove ground'
    assert t.ground_below(80, top + 1) is not None, 'ground should remain below the crater'
    print('terrain ok')
