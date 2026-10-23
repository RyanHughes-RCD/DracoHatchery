"""Build the colourable V2 prototype dragon from the pixil-layer sprites.

The B&W layers are drawn on the same 150x150 canvas, in the same places, as
the first prototype (Rig/Prototype), but they carry no socket holes, so the
pivots below are that rig's sockets.

For each layer this writes two sprites to build/:
  layer<N>_shape.png  the part's silhouette (where the layer is opaque)
  layer<N>_ink.png    darkness as alpha: white clear, black solid, greys between
The viewer fills the shape with a flat colour and lays the ink over it.

Usage: python3 build_rig.py
"""
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
BUILD = os.path.join(HERE, "build")
sys.path.insert(0, os.path.dirname(HERE))
from make_alpha import to_alpha_mask  # noqa: E402

# Draw order, back to front: (name, layer, parent, pivot or None, far side).
# A None pivot is worked out from the sprite (see pivot_for).
LAYOUT = [
    ("torso", 0, None, None, False),
    ("far_wing", 7, "torso", (50.3, 73.9), True),
    ("wing", 7, "torso", (50.3, 73.9), False),
    ("back_leg", 3, "torso", (77.21, 81.5), False),
    ("tail", 1, "torso", (84.62, 76.62), False),
    ("front_leg", 2, "torso", (45.0, 90.0), False),
    ("head", 4, "torso", (40.0, 69.0), False),
    ("jaw", 5, "head", None, False),
    ("eye", 6, "head", None, False),
]


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
    for name, layer, parent, pivot, far in LAYOUT:
        src = Image.open(os.path.join(REPO, f"pixil-layer-{layer}.png")).convert("RGBA")
        shape = Image.new("RGBA", src.size, (255, 255, 255, 0))
        shape.putalpha(src.getchannel("A").point(lambda v: 255 if v else 0))
        shape.save(os.path.join(BUILD, f"layer{layer}_shape.png"))
        to_alpha_mask(src).save(os.path.join(BUILD, f"layer{layer}_ink.png"))
        pivot = [round(v, 2) for v in (pivot or pivot_for(name, src))]
        parts.append({"name": name, "layer": f"pixil-layer-{layer}.png", "parent": parent,
                      "pivot": pivot, "far": far,
                      "shape": f"build/layer{layer}_shape.png", "ink": f"build/layer{layer}_ink.png"})
        print(name, f"layer {layer}", pivot)
    rig = {"canvas": [150, 150], "parts": parts}
    with open(os.path.join(HERE, "rig.json"), "w") as f:
        json.dump(rig, f, indent=2)
    # Same data as a script so the viewer also works when opened from disk.
    with open(os.path.join(HERE, "rig.js"), "w") as f:
        f.write("window.DRAGON_RIG = " + json.dumps(rig, indent=2) + ";\n")


if __name__ == "__main__":
    main()
