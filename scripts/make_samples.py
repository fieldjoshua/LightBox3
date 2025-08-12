#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def make_checkerboard(size: int, tile: int) -> Image.Image:
    img = Image.new("RGB", (size, size), "black")
    draw = ImageDraw.Draw(img)
    color_a = (255, 255, 255)
    color_b = (0, 0, 0)
    for y in range(0, size, tile):
        for x in range(0, size, tile):
            color = color_a if ((x // tile + y // tile) % 2 == 0) else color_b
            draw.rectangle([x, y, x + tile - 1, y + tile - 1], fill=color)
    return img


def make_gradient(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size))
    for y in range(size):
        for x in range(size):
            r = int(255 * x / (size - 1))
            g = int(255 * y / (size - 1))
            b = int(255 * (x + y) / (2 * (size - 1)))
            img.putpixel((x, y), (r, g, b))
    return img


def make_stripes_gif(size: int, frames: int = 12) -> Image.Image:
    images = []
    stripe_w = max(2, size // 8)
    for i in range(frames):
        img = Image.new("RGB", (size, size), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        offset = (i * stripe_w) % (stripe_w * 4)
        for x in range(-stripe_w * 4, size + stripe_w * 4, stripe_w * 2):
            draw.rectangle(
                [x + offset, 0, x + offset + stripe_w - 1, size - 1],
                fill=(255, 0, 0),
            )
        images.append(img)
    # Save as animated GIF with 75ms per frame (~13 FPS)
    images[0].save(
        "samples/stripes-64.gif",
        save_all=True,
        append_images=images[1:],
        duration=75,
        loop=0,
        disposal=2,
    )
    return images[0]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "samples"
    ensure_dir(out_dir)

    checker = make_checkerboard(size=64, tile=8)
    checker.save(out_dir / "checkerboard-64.png")

    grad = make_gradient(size=64)
    grad.save(out_dir / "gradient-64.png")

    make_stripes_gif(size=64, frames=16)

    print("Wrote:")
    for p in sorted(out_dir.glob("*")):
        print("  ", p)


if __name__ == "__main__":
    main()


