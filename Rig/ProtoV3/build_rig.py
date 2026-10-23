"""Build the colour-mapped V3 prototype dragon.

Source: Pixel Art/Proto-Dragon/Colour Map V1, as pairs of layers per part:
  shading layer   white, greys and black, as in V2 (darkness becomes alpha)
  colour map      a copy of the part where saturated colour marks regions:
                  white/grey/black = main colour, red = colour 2,
                  blue = colour 3, green = colour 4 (matched by hue).
Each region takes its own colour and keeps the shading drawn over it. Map
colour painted over solid black shading (the eye's iris) is left unshaded,
since a colour under solid black could never show.

For each part this writes to build/: <name>_shape.png (silhouette),
<name>_ink.png (shading as alpha), <name>_lines.png (just the outlines, for
previewing without shading) and <name>_c<N>.png per region it has.

Usage: python3 build_rig.py
"""
import colorsys
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO, "Pixel Art", "Proto-Dragon", "Colour Map V1")
BUILD = os.path.join(HERE, "build")
sys.path.insert(0, os.path.dirname(HERE))
from make_alpha import to_alpha_mask  # noqa: E402

# Draw order, back to front: (name, shading layer, map layer, parent, pivot or None, far side).
# The parts sit where they did in V2, so the pivots are V2's; None is worked out from the sprite.
LAYOUT = [
    ("torso", 0, 1, None, None, False),
    ("far_wing", 14, 15, "torso", (50.3, 73.9), True),
    ("wing", 14, 15, "torso", (50.3, 73.9), False),
    ("back_leg", 6, 7, "torso", (77.21, 81.5), False),
    ("tail", 2, 3, "torso", (84.62, 76.62), False),
    ("front_leg", 4, 5, "torso", (45.0, 90.0), False),
    ("head", 8, 9, "torso", (40.0, 69.0), False),
    ("jaw", 10, 11, "head", None, False),
    ("eye", 12, 13, "head", None, False),
]
# Region hues in degrees; a saturated map pixel joins the nearest one.
REGIONS = {"c2": 0, "c3": 220, "c4": 120}
SOLID_BLACK = 18  # shading at or below this hides any colour under it
OUTLINE = 39  # shading at or below this is outline, kept when shading is off


def region_of(rgb):
    r, g, b = (v / 255 for v in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < 0.3 or v < 0.2:
        return None  # white, grey or black: main colour
    hue = h * 360
    return min(REGIONS, key=lambda k: min(abs(hue - REGIONS[k]), 360 - abs(hue - REGIONS[k])))


def pivot_for(name, im):
    a = im.getchannel("A").load()
    w, h = im.size
    pts = [(x, y) for y in range(h) for x in range(w) if a[x, y] > 0]
    if name == "jaw":
        # Hinge at the back of the jaw: centre of its rightmost column.
        right = max(x for x, _ in pts)
        ys = [y for x, y in pts if x == right]
        return (right + 0.5, sum(ys) / len(ys) + 0.5)
    return (sum(x for x, _ in pts) / len(pts) + 0.5, sum(y for _, y in pts) / len(pts) + 0.5)


def main():
    os.makedirs(BUILD, exist_ok=True)
    parts = []
    for name, shade_layer, map_layer, parent, pivot, far in LAYOUT:
        shade = Image.open(os.path.join(SRC, f"pixil-layer-{shade_layer}.png")).convert("RGBA")
        cmap = Image.open(os.path.join(SRC, f"pixil-layer-{map_layer}.png")).convert("RGBA")
        w, h = shade.size
        spx, mpx = shade.load(), cmap.load()

        shape = Image.new("RGBA", shade.size, (255, 255, 255, 0))
        shape.putalpha(shade.getchannel("A").point(lambda v: 255 if v else 0))
        ink = to_alpha_mask(shade)
        ipx = ink.load()

        masks = {}
        for y in range(h):
            for x in range(w):
                if not (spx[x, y][3] and mpx[x, y][3]):
                    continue
                region = region_of(mpx[x, y][:3])
                if region is None:
                    continue
                masks.setdefault(region, Image.new("RGBA", shade.size, (255, 255, 255, 0))).putpixel((x, y), (255, 255, 255, 255))
                if spx[x, y][0] <= SOLID_BLACK:
                    ipx[x, y] = (0, 0, 0, 0)

        # Outlines only: the ink where it is outline-dark, nothing for the greys.
        lines = ink.copy()
        lpx = lines.load()
        for y in range(h):
            for x in range(w):
                if lpx[x, y][3] and not (spx[x, y][3] and spx[x, y][0] <= OUTLINE):
                    lpx[x, y] = (0, 0, 0, 0)

        base = f"layer{shade_layer}"
        shape.save(os.path.join(BUILD, f"{base}_shape.png"))
        ink.save(os.path.join(BUILD, f"{base}_ink.png"))
        lines.save(os.path.join(BUILD, f"{base}_lines.png"))
        for region, mask in masks.items():
            mask.save(os.path.join(BUILD, f"{base}_{region}.png"))
        # Main only counts if it shows somewhere: a pixel outside every region
        # that isn't solid outline (the jaw and eye are all regions).
        has_main = any(spx[x, y][3] and spx[x, y][0] > 19 and not any(m.getpixel((x, y))[3] for m in masks.values())
                       for y in range(h) for x in range(w))

        pivot = [round(v, 2) for v in (pivot or pivot_for(name, shade))]
        parts.append({"name": name, "layers": [f"pixil-layer-{shade_layer}.png", f"pixil-layer-{map_layer}.png"],
                      "parent": parent, "pivot": pivot, "far": far,
                      "main": has_main, "regions": [r for r in REGIONS if r in masks],
                      "shape": f"build/{base}_shape.png", "ink": f"build/{base}_ink.png",
                      "lines": f"build/{base}_lines.png",
                      "masks": {r: f"build/{base}_{r}.png" for r in REGIONS if r in masks}})
        print(name, pivot, "regions:", parts[-1]["regions"], "" if parts[-1]["main"] else "(no main)")
    rig = {"canvas": [150, 150], "parts": parts}
    with open(os.path.join(HERE, "rig.json"), "w") as f:
        json.dump(rig, f, indent=2)
    # Same data as a script so the viewer also works when opened from disk.
    with open(os.path.join(HERE, "rig.js"), "w") as f:
        f.write("window.DRAGON_RIG = " + json.dumps(rig, indent=2) + ";\n")


if __name__ == "__main__":
    main()
