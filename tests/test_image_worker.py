"""Opt-in real-runtime tests: SUBJECTOR_TEST_RUNTIME points at a prepared runtime."""

import json
import os
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

RUNTIME = os.environ.get("SUBJECTOR_TEST_RUNTIME")
WORKER = Path(__file__).resolve().parents[1] / "subjector/_copy_image.py"


@unittest.skipUnless(RUNTIME, "requires an explicitly prepared rembg runtime")
class ImageWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.runtime = Path(RUNTIME)
        self.python = self.runtime / "runtime/python/bin/python3"
        subprocess.run([str(self.python), "-I", "-c", """
from PIL import Image, ImageDraw
import sys
from pathlib import Path
root=Path(sys.argv[1])
im=Image.new('RGB',(80,40),'white')
ImageDraw.Draw(im).rectangle((20,5,60,35),fill='red')
im.save(root/'subject.png')
im.save(root/'static.webp')
exif=Image.Exif(); exif[274]=6
im.save(root/'rotated.jpg',exif=exif)
alpha=im.convert('RGBA'); alpha.putalpha(0); alpha.save(root/'transparent.png')
im.save(root/'animated.webp',save_all=True,append_images=[Image.new('RGB',(80,40),'blue')],duration=100)
im.save(root/'unsupported.bmp')
""", str(self.root)], check=True)

    def run_worker(self, filename):
        return subprocess.run(
            [str(self.python), "-I", str(WORKER), str(self.root / filename),
             str(self.runtime / "model.onnx"), str(self.root / "result.png")],
            env={"PATH": os.defpath, "U2NET_HOME": str(self.runtime), "HOME": str(self.root)},
            text=True, capture_output=True, timeout=120,
        )

    def test_png_subject_is_transparent_and_source_is_unchanged(self):
        original = (self.root / "subject.png").read_bytes()
        result = self.run_worker("subject.png")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["size"], [80, 40])
        self.assertLess(report["alpha"][0], 255)
        self.assertGreater(report["alpha"][1], 0)
        self.assertEqual((self.root / "subject.png").read_bytes(), original)
        self.assertTrue((self.root / "result.png").read_bytes().startswith(b"\x89PNG"))

    def test_exif_orientation_is_applied_and_metadata_removed(self):
        result = self.run_worker("rotated.jpg")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)["size"], [40, 80])
        inspection = subprocess.check_output([str(self.python), "-I", "-c",
            "from PIL import Image; import sys; print(len(Image.open(sys.argv[1]).getexif()))",
            str(self.root / "result.png")], text=True)
        self.assertEqual(inspection.strip(), "0")

    def test_static_webp_is_supported(self):
        result = self.run_worker("static.webp")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)["size"], [80, 40])

    def test_existing_transparency_is_preserved(self):
        result = self.run_worker("transparent.png")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)["alpha"], [0, 0])

    def test_file_size_and_pixel_limits_fail_before_inference(self):
        with (self.root / "large.png").open("wb") as source:
            source.truncate(50 * 1024 * 1024 + 1)
        result = self.run_worker("large.png")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("50 MiB", json.loads(result.stdout)["error"])
        header = struct.pack(">IIBBBBB", 10000, 10000, 8, 2, 0, 0, 0)
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        (self.root / "bomb.png").write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", b""))
        result = self.run_worker("bomb.png")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pixels", json.loads(result.stdout)["error"])
        self.assertFalse((self.root / "result.png").exists())

    def test_invalid_animated_and_unsupported_images_leave_no_output(self):
        (self.root / "corrupt.png").write_bytes(b"not an image")
        for name in ("animated.webp", "unsupported.bmp", "corrupt.png", "missing.png"):
            with self.subTest(name=name):
                result = self.run_worker(name)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("error", json.loads(result.stdout))
                self.assertFalse((self.root / "result.png").exists())
