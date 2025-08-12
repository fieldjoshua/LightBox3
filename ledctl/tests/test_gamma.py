from __future__ import annotations

import unittest

from PIL import Image

from core.gamma import apply_gamma_rgb_balance


class TestGamma(unittest.TestCase):
    def test_apply_gamma_rgb_balance_basic(self) -> None:
        im = Image.new("RGB", (2, 2), color=(100, 100, 100))
        out = apply_gamma_rgb_balance(
            im,
            gamma=2.2,
            rgb_balance=(1.0, 1.0, 1.0),
        )
        self.assertEqual(out.size, (2, 2))
        self.assertNotEqual(out.getpixel((0, 0)), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()


