"""Pull a looping walk cycle out of source.mp4.

1. Sample the video at 8 fps with ffmpeg.
2. Keep one step cycle. Comparing the dragon's silhouette between frames
   shows it repeats every 9 frames; frames 11-19 loop most cleanly (frame 20
   is the closest match to frame 11).
3. Cut the dragon out of the background. Its lavender greys have at least as
   much red and blue as green, while the sky, clouds and grass lean green or
   cyan. The largest connected shape is kept and holes in it are filled
   with dragon-coloured pixels only.
4. Crop every frame to the same box so the dragon stays put, then write
   frames/walk_NN.png, a sprite sheet and a looping preview GIF.

Usage: python3 extract.py   (needs ffmpeg on the PATH)
"""
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "source.mp4")
FPS = 8
CYCLE = range(11, 20)  # 0-based frame numbers at 8 fps
PAD = 8


def sample(video, fps, folder):
    subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", f"fps={fps}",
                    os.path.join(folder, "f%03d.png")], check=True)
    return sorted(os.path.join(folder, f) for f in os.listdir(folder))


def cutout(path):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    spread = a.max(-1) - a.min(-1)
    lavender = (r >= g - 3) & (b >= g - 3) & (spread < 95) & (a.max(-1) > 70)
    mask = Image.fromarray((lavender * 255).astype(np.uint8))
    # Close small gaps, then drop specks.
    mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    mask = mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))

    # Largest connected shape, flooding from seeds across the middle of the frame.
    best, best_n = None, 0
    for sy in range(300, 560, 20):
        for sx in range(300, 900, 20):
            if mask.getpixel((sx, sy)) != 255:
                continue
            work = mask.copy()
            ImageDraw.floodfill(work, (sx, sy), 128)
            shape = np.asarray(work) == 128
            if shape.sum() > best_n:
                best, best_n = shape, shape.sum()
            mask = Image.fromarray(np.where(shape, 0, np.asarray(mask)).astype(np.uint8))

    # Fill holes (anything the border can't reach) only with dragon-coloured
    # pixels, so grass or sky caught between the legs stays open.
    padded = Image.new("L", (im.width + 2, im.height + 2), 0)
    padded.paste(Image.fromarray(np.where(best, 255, 0).astype(np.uint8)), (1, 1))
    ImageDraw.floodfill(padded, (0, 0), 128)
    inside = np.asarray(padded)[1:-1, 1:-1] != 128
    inside &= best | lavender

    alpha = Image.fromarray((inside * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))
    out = im.convert("RGBA")
    out.putalpha(alpha)
    return out


def main():
    with tempfile.TemporaryDirectory() as tmp:
        frames = sample(SOURCE, FPS, tmp)
        cut = [cutout(frames[i]) for i in CYCLE]

    # One crop box for every frame, so the dragon doesn't jump around.
    boxes = [c.getbbox() for c in cut]
    box = (min(b[0] for b in boxes) - PAD, min(b[1] for b in boxes) - PAD,
           max(b[2] for b in boxes) + PAD, max(b[3] for b in boxes) + PAD)
    cut = [c.crop(box) for c in cut]

    out = os.path.join(HERE, "frames")
    os.makedirs(out, exist_ok=True)
    for n, c in enumerate(cut):
        c.save(os.path.join(out, f"walk_{n:02d}.png"))

    w, h = cut[0].size
    sheet = Image.new("RGBA", (w * len(cut), h), (0, 0, 0, 0))
    for n, c in enumerate(cut):
        sheet.paste(c, (n * w, 0))
    sheet.save(os.path.join(HERE, "walk_sheet.png"))

    # GIF has no partial transparency, so the preview sits on a plain backdrop.
    preview = []
    for c in cut:
        bg = Image.new("RGBA", c.size, (214, 228, 245, 255))
        bg.alpha_composite(c)
        preview.append(bg.convert("RGB"))
    preview[0].save(os.path.join(HERE, "walk_preview.gif"), save_all=True,
                    append_images=preview[1:], duration=1000 // FPS, loop=0)
    print(f"{len(cut)} frames, {w}x{h} each, crop box {box}")


if __name__ == "__main__":
    main()
