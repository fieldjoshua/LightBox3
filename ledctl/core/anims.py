from __future__ import annotations

import math
import time
from typing import Generator, Iterable, Tuple

from PIL import Image, ImageDraw, ImageFont

from .frames import Frame


def color_cycle(width: int, height: int) -> Generator[Frame, None, None]:
    """
    Smoothly cycle through hues. Duration ~16ms per frame (~60 FPS by cap).
    """
    t = 0
    while True:
        img = Image.new("RGB", (int(width), int(height)))
        pixels = []
        for y in range(height):
            for x in range(width):
                hue = (t + (x + y) * 2) % 360
                r, g, b = _hsv_to_rgb(hue / 360.0, 1.0, 1.0)
                pixels.append((r, g, b))
        img.putdata(pixels)
        t = (t + 3) % 360
        yield Frame(img, 16)


def moving_stripes(width: int, height: int) -> Generator[Frame, None, None]:
    """
    Red stripes moving to the right.
    """
    offset = 0
    stripe_w = max(2, width // 8)
    while True:
        img = Image.new("RGB", (int(width), int(height)), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        for x in range(-stripe_w * 4, width + stripe_w * 4, stripe_w * 2):
            draw.rectangle(
                [x + offset, 0, x + offset + stripe_w - 1, height - 1],
                fill=(255, 0, 0),
            )
        offset = (offset + 1) % (stripe_w * 2)
        yield Frame(img, 30)


def scrolling_text(width: int, height: int, text: str = "HELLO") -> Generator[Frame, None, None]:
    """
    Simple scrolling text using default PIL font.
    """
    font = ImageFont.load_default()
    text_img = Image.new("RGB", (1, 1))
    tw, th = ImageDraw.Draw(text_img).textsize(text, font=font)
    pad = width
    canvas_w = tw + pad * 2
    x = canvas_w
    while True:
        img = Image.new("RGB", (int(width), int(height)), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((x - pad, (height - th) // 2), text, font=font, fill=(255, 255, 0))
        x -= 2
        if x - pad <= -tw:
            x = canvas_w
        yield Frame(img, 30)


def list_builtin() -> Iterable[Tuple[str, str]]:
    return [
        ("color_cycle", "Color Cycle"),
        ("moving_stripes", "Moving Stripes"),
        ("scrolling_text", "Scrolling Text"),
    ]


def _hsv_to_rgb(h: float, s: float, v: float) -> Tuple[int, int, int]:
    i = int(h * 6.0)
    f = h * 6.0 - i
    p = int(255 * v * (1.0 - s))
    q = int(255 * v * (1.0 - f * s))
    t = int(255 * v * (1.0 - (1.0 - f) * s))
    v255 = int(255 * v)
    i %= 6
    if i == 0:
        return v255, t, p
    if i == 1:
        return q, v255, p
    if i == 2:
        return p, v255, t
    if i == 3:
        return p, q, v255
    if i == 4:
        return t, p, v255
    return v255, p, q


