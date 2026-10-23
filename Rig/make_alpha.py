"""Turn black-and-white part sprites into tintable alpha masks.

Darkness becomes opacity: white is fully transparent, black fully opaque,
greys in between. Any transparency already in the image is kept (the two
multiply). Output pixels are black, so the PNGs still preview as the
drawing; a viewer fills them with a flat colour and the alpha carries the
texture.

Usage: python3 make_alpha.py <source dir> <output dir>
"""
import os
import sys

from PIL import Image


def to_alpha_mask(im):
    rgba = im.convert("RGBA")
    grey = rgba.convert("L")  # ITU-R 601 luminance
    out = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    src_a, lum = rgba.getchannel("A").load(), grey.load()
    px = out.load()
    w, h = rgba.size
    for y in range(h):
        for x in range(w):
            a = (255 - lum[x, y]) * src_a[x, y] // 255
            px[x, y] = (0, 0, 0, a)
    return out


def main(src, dst):
    os.makedirs(dst, exist_ok=True)
    for name in sorted(os.listdir(src)):
        if os.path.splitext(name)[1].lower() not in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".jfif"):
            continue
        out = to_alpha_mask(Image.open(os.path.join(src, name)))
        target = os.path.splitext(name)[0] + ".png"
        out.save(os.path.join(dst, target))
        print(name, "->", target)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
