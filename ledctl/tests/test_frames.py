from __future__ import annotations

import os
import tempfile
import unittest

from PIL import Image

from core.frames import load_image


class TestFrames(unittest.TestCase):
    def test_load_image_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "im.png")
            Image.new("RGB", (3, 3), color=(10, 20, 30)).save(path)
            frames = list(load_image(path))
            self.assertEqual(len(frames), 1)
            self.assertEqual(frames[0].image.getpixel((0, 0)), (10, 20, 30))


if __name__ == "__main__":
    unittest.main()


