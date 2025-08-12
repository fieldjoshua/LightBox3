from __future__ import annotations

from typing import Tuple

from PIL import Image


def apply_gamma_rgb_balance(
    image_rgb: Image.Image,
    gamma: float,
    rgb_balance: Tuple[float, float, float],
) -> Image.Image:
    """
    Apply gamma correction and RGB channel balance to an RGB Pillow Image.

    Args:
        image_rgb: Pillow Image in RGB mode
        gamma: gamma value in [1.0, 3.0]
        rgb_balance: per-channel multipliers (r,g,b) each in [0.5, 1.5]

    Returns:
        New Pillow Image with adjustments applied.
    """
    if image_rgb.mode != "RGB":
        image_rgb = image_rgb.convert("RGB")

    # Clamp inputs
    g = max(1.0, min(3.0, float(gamma)))
    r_mul = max(0.5, min(1.5, float(rgb_balance[0])))
    g_mul = max(0.5, min(1.5, float(rgb_balance[1])))
    b_mul = max(0.5, min(1.5, float(rgb_balance[2])))

    # Gamma curve using point operation (Pillow-side; avoids extra deps)
    inv_gamma = 1.0 / g
    lut = [int(pow(i / 255.0, inv_gamma) * 255.0 + 0.5) for i in range(256)]
    corrected = image_rgb.point(lut * 3)

    # Channel balance
    red, green, blue = corrected.split()
    red = red.point(lambda v: int(max(0, min(255, v * r_mul))))
    green = green.point(lambda v: int(max(0, min(255, v * g_mul))))
    blue = blue.point(lambda v: int(max(0, min(255, v * b_mul))))
    return Image.merge("RGB", (red, green, blue))


