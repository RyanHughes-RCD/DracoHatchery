"""Make the spiky rock dragon variant of the V2 layers.

Starts from the cleaned-up layers (refine.py steps 1-3, no scales) and adds:
  * Spikes along the back, tail and head, drawn in the dark grey so they
    follow the "dark shade" colour zone.
  * Rock cracks on the white areas, drawn in a light grey so they follow the
    "light shade" zone along with the belly.
Writes rock/pixil-layer-N.png; the originals are untouched.

Usage: python3 make_rock.py
"""
import os
import random

from PIL import Image, ImageDraw

import refine

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "rock")

SPIKE = 133   # dark shade zone
CRACK = 190   # light shade zone
WHITE = 255

# layer -> spikes as (base centre x, height, lean towards the tail, base half-width)
SPIKES = {
    0: [(47, 5, 2, 2), (60, 7, 3, 3), (67, 8, 3, 3), (74, 8, 3, 3), (81, 7, 3, 3), (87, 5, 2, 2)],
    1: [(93, 6, 3, 3), (100, 6, 3, 3), (107, 5, 2, 2), (114, 5, 2, 2), (120, 4, 2, 2), (126, 3, 1, 2)],
    # Horns sweep back from the top of the head.
    4: [(30, 6, 4, 2), (35, 9, 6, 3), (40, 5, 4, 2)],
}
CRACK_LAYERS = {0: 14, 1: 5, 2: 3, 3: 4, 4: 4}  # layer -> number of cracks


def top_of(grid, x):
    for y, row in enumerate(grid):
        if row[x] is not refine.T:
            return y
    return None


def add_spikes(grid, w, h, spikes):
    for cx, height, lean, half in spikes:
        base = top_of(grid, cx)
        mask = Image.new("1", (w, h), 0)
        ImageDraw.Draw(mask).polygon(
            [(cx - half, base + 1), (cx + half, base + 1), (cx + lean, base - height)], fill=1)
        m = mask.load()
        inside = {(x, y) for y in range(h) for x in range(w) if m[x, y]}
        for x, y in inside:
            if grid[y][x] is not refine.T:
                continue  # never paint over the body
            edge = any((nx, ny) not in inside and (not (0 <= nx < w and 0 <= ny < h) or grid[ny][nx] is refine.T)
                       for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
            grid[y][x] = refine.OUTLINE if edge else SPIKE


def add_cracks(grid, w, h, count, rng):
    """Short wandering lines, a pixel clear of any ink, like fractures in stone."""
    def clear(x, y):
        return all(0 <= x + dx < w and 0 <= y + dy < h and grid[y + dy][x + dx] in (WHITE, CRACK)
                   for dx in (-1, 0, 1) for dy in (-1, 0, 1))

    spots = [(x, y) for y in range(h) for x in range(w) if grid[y][x] == WHITE and clear(x, y)]
    for _ in range(count):
        if not spots:
            return
        x, y = rng.choice(spots)
        dx, dy = rng.choice([(1, 1), (1, -1), (-1, 1), (-1, -1)])
        for _ in range(rng.randint(3, 7)):
            if not clear(x, y):
                break
            grid[y][x] = CRACK
            # Mostly diagonal, sometimes a straight step, now and then a fork.
            r = rng.random()
            step = (dx, dy) if r < 0.6 else ((dx, 0) if r < 0.8 else (0, dy))
            if rng.random() < 0.15 and clear(x - dx, y + dy):
                grid[y + dy][x - dx] = CRACK
            x, y = x + step[0], y + step[1]


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = random.Random(7)
    for layer in range(8):
        name = f"pixil-layer-{layer}.png"
        grid, w, h = refine.read(os.path.join(refine.REPO, name))
        if layer not in refine.SKIP:
            refine.refine(grid, w, h)
        if layer in CRACK_LAYERS:
            add_cracks(grid, w, h, CRACK_LAYERS[layer], rng)
        if layer in SPIKES:
            add_spikes(grid, w, h, SPIKES[layer])
        refine.write(grid, w, h, os.path.join(OUT, name))
        print(name)


if __name__ == "__main__":
    main()
