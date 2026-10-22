"""AppImage integration must survive temporary mount paths and ELF launchers."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from subjector.integration import launcher_path, register
from subjector.paths import AppPaths


class AppImageTests(unittest.TestCase):
    def test_desktop_registration_uses_the_permanent_appimage_path(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "Subjector % test.AppImage"
            image.write_bytes(b"\x7fELF")
            image.chmod(0o755)
            with patch.dict(os.environ, {"APPIMAGE": str(image)}):
                self.assertEqual(launcher_path(), image)
            entry = register(AppPaths.discover({}, Path(directory)), image, context_menu=False)
            text = entry.read_text()
            self.assertIn("/usr/bin/env -- ", text)
            self.assertNotIn("/bin/sh", text)
            self.assertNotIn("/tmp/.mount_", text)

    def test_source_launcher_is_used_without_appimage_environment(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(launcher_path(), Path(__file__).resolve().parents[1] / "subjector.sh")
