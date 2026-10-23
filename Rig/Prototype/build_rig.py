"""Build rig.json for the prototype dragon from its part sprites.

Indexing convention (all parts share the same 150x150 canvas):
  * The torso carries small coloured marker blobs (sockets).
  * Each limb has a transparent hole; the limb's main colour matches the
    torso marker it plugs into, and the hole's centre is the limb's pivot.
  * A part with no hole (the eye) rides on the head at its drawn position.

Outputs rig.json (and rig.js for the viewer) plus game-ready sprites in
build/: torso markers and limb holes are painted over so they never show.

Usage: python3 build_rig.py
"""
import json
import os
from collections import Counter

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.join(HERE, "parts")
BUILD = os.path.join(HERE, "build")

# name -> (file, parent). Draw order is back to front.
LAYOUT = [
    ("back_leg", "back_leg.png", "torso"),
    ("tail", "tail.png", "torso"),
    ("torso", "torso.png", None),
    ("front_leg", "front_leg.png", "torso"),
    ("head", "head.png", "torso"),
    ("eye", "eye.png", "head"),
]
BACK_LEG_FALLBACK = "front_leg.png"


def load(name):
    im = Image.open(os.path.join(PARTS, name)).convert("RGBA")
    return im, im.load()


def opaque_pixels(im, px):
    w, h = im.size
    return [(x, y) for y in range(h) for x in range(w) if px[x, y][3] > 0]


def components(points):
    """4-connected components of a set of pixels."""
    left, out = set(points), []
    while left:
        stack, comp = [left.pop()], []
        while stack:
            x, y = stack.pop()
            comp.append((x, y))
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if n in left:
                    left.remove(n)
                    stack.append(n)
        out.append(comp)
    return out


def holes(im, px):
    """Transparent pixels not reachable from the canvas border."""
    w, h = im.size
    outside = set()
    stack = [(x, y) for x in range(w) for y in (0, h - 1)]
    stack += [(x, y) for y in range(h) for x in (0, w - 1)]
    while stack:
        x, y = stack.pop()
        if not (0 <= x < w and 0 <= y < h) or (x, y) in outside or px[x, y][3] > 0:
            continue
        outside.add((x, y))
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return [(x, y) for y in range(h) for x in range(w)
            if px[x, y][3] == 0 and (x, y) not in outside]


def centre(points):
    return [round(sum(p[0] for p in points) / len(points) + 0.5, 2),
            round(sum(p[1] for p in points) / len(points) + 0.5, 2)]


def main_colour(px, points):
    return Counter(px[p][:3] for p in points).most_common(1)[0][0]


def main():
    os.makedirs(BUILD, exist_ok=True)
    torso, tpx = load("torso.png")
    body = opaque_pixels(torso, tpx)
    skin = main_colour(tpx, body)

    # Group torso marker pixels into sockets by colour + connectivity.
    sockets = []
    by_colour = {}
    for p in body:
        if tpx[p][:3] != skin:
            by_colour.setdefault(tpx[p][:3], []).append(p)
    for colour, pts in by_colour.items():
        for comp in components(pts):
            sockets.append({"colour": list(colour), "pixels": comp, "at": centre(comp)})

    rig = {"canvas": list(torso.size), "parts": [], "unused_sockets": []}
    claimed = set()
    # Resolve the back leg last so it takes the matching socket the front
    # leg leaves free (needed while it falls back to the front leg sprite).
    resolve = sorted(LAYOUT, key=lambda l: l[0] == "back_leg")
    parts = {}
    for name, file, parent in resolve:
        placeholder = False
        if not os.path.exists(os.path.join(PARTS, file)):
            if name != "back_leg":
                raise SystemExit(f"missing part {file}")
            file, placeholder = BACK_LEG_FALLBACK, True
        im, px = load(file)
        part = {"name": name, "source": "parts/" + file, "image": f"build/{name}.png",
                "parent": parent, "placeholder": placeholder, "offset": [0, 0]}
        out = im.copy()
        opx = out.load()
        if name == "torso":
            part["pivot"] = centre(body)
            for s in sockets:
                for p in s["pixels"]:
                    opx[p] = skin + (255,)
        else:
            hole = holes(im, px)
            if hole:
                pivot = centre(hole)
                colour = list(main_colour(px, opaque_pixels(im, px)))
                candidates = [i for i, s in enumerate(sockets)
                              if s["colour"] == colour and i not in claimed]
                # Prefer the socket closest to where the part was drawn.
                i = min(candidates, key=lambda i: (sockets[i]["at"][0] - pivot[0]) ** 2
                        + (sockets[i]["at"][1] - pivot[1]) ** 2)
                claimed.add(i)
                socket = sockets[i]["at"]
                part["pivot"] = pivot
                part["offset"] = [round(socket[0] - pivot[0], 2), round(socket[1] - pivot[1], 2)]
                part["socket"] = socket
                for p in hole:
                    opx[p] = tuple(colour) + (255,)
            else:
                # No hole: pivot on its own centre, stays where it was drawn.
                part["pivot"] = centre(opaque_pixels(im, px))
        if placeholder:
            # Shade the stand-in so it reads as the far leg.
            for p in opaque_pixels(out, opx):
                r, g, b, a = opx[p]
                opx[p] = (r * 3 // 4, g * 3 // 4, b * 3 // 4, a)
        out.save(os.path.join(BUILD, name + ".png"))
        parts[name] = part
    rig["parts"] = [parts[name] for name, _, _ in LAYOUT]
    rig["unused_sockets"] = [
        {"colour": s["colour"], "at": s["at"]} for i, s in enumerate(sockets) if i not in claimed]

    with open(os.path.join(HERE, "rig.json"), "w") as f:
        json.dump(rig, f, indent=2)
    # Same data as a script so the viewer also works when opened from disk.
    with open(os.path.join(HERE, "rig.js"), "w") as f:
        f.write("window.DRAGON_RIG = " + json.dumps(rig, indent=2) + ";\n")
    for p in rig["parts"]:
        print(p["name"], p.get("socket"), p["pivot"], p["offset"], "(placeholder)" if p["placeholder"] else "")
    print("unused sockets:", rig["unused_sockets"])


if __name__ == "__main__":
    main()
