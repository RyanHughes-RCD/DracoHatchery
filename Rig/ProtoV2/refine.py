"""First-pass cleanup of the B&W pixil layers.

Writes refined copies to refined/ and leaves the originals untouched:
  1. Shades: the stray near-black grey (39) joins the outline grey (19), so
     every outline has the same opacity once darkness becomes alpha.
  2. Specks: a lone pixel with no same-shade neighbour, sitting inside a
     single other (non-outline) shade, takes that shade.
  3. Outline corners: where an outline turns a corner as an L of three
     pixels, the corner pixel is dropped so the line steps diagonally at an
     even 1px weight. It takes the colour of the side it was facing.

The eye (layer 6) is too small to benefit and is copied as is.

Usage: python3 refine.py
"""
import os
from collections import Counter

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "refined")

OUTLINE = 19
MERGE_INTO_OUTLINE = {39}
SKIP = {6}
T = None  # transparent


def read(path):
    im = Image.open(path).convert("RGBA")
    w, h = im.size
    px = im.load()
    grid = [[(px[x, y][0] if px[x, y][3] else T) for x in range(w)] for y in range(h)]
    return grid, w, h


def write(grid, w, h, path):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = im.load()
    for y in range(h):
        for x in range(w):
            v = grid[y][x]
            if v is not T:
                px[x, y] = (v, v, v, 255)
    im.save(path)


def refine(grid, w, h):
    def at(x, y):
        return grid[y][x] if 0 <= x < w and 0 <= y < h else T

    def ink(v):
        return v is not T and v <= OUTLINE

    changes = Counter()

    for y in range(h):
        for x in range(w):
            if grid[y][x] in MERGE_INTO_OUTLINE:
                grid[y][x] = OUTLINE
                changes["shade"] += 1

    for y in range(h):
        for x in range(w):
            v = grid[y][x]
            if v is T or ink(v):
                continue
            ring = [at(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
            if v in ring:
                continue
            fills = {n for n in ring if n is not T and not ink(n)}
            if len(fills) == 1 and T not in ring:
                grid[y][x] = fills.pop()
                changes["speck"] += 1

    for y in range(h):
        for x in range(w):
            if not ink(grid[y][x]):
                continue
            for dx in (-1, 1):
                for dy in (-1, 1):
                    arms = ink(at(x + dx, y)) and ink(at(x, y + dy))
                    if not arms or ink(at(x + dx, y + dy)):
                        continue
                    back = [at(x - dx, y), at(x, y - dy)]
                    if any(ink(b) for b in back):
                        continue
                    # Facing outside -> transparent, facing inside -> that fill.
                    grid[y][x] = T if T in back else Counter(back).most_common(1)[0][0]
                    changes["corner"] += 1
                    break
                else:
                    continue
                break
    return changes


def main():
    os.makedirs(OUT, exist_ok=True)
    for layer in range(8):
        name = f"pixil-layer-{layer}.png"
        grid, w, h = read(os.path.join(REPO, name))
        changes = Counter() if layer in SKIP else refine(grid, w, h)
        write(grid, w, h, os.path.join(OUT, name))
        print(name, dict(changes) or "unchanged")


if __name__ == "__main__":
    main()
