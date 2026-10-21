import json
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from subjector.integration import IntegrationError, register, remove_context_menu
from subjector.paths import AppPaths


class IntegrationTests(unittest.TestCase):
    def test_installs_only_requested_entries_and_removes_owned_context_menu(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = AppPaths.discover({}, Path(directory))
            launcher = Path(directory) / "Subjector % ' $ app.sh"
            launcher.write_text("#!/bin/sh\n")
            launcher.chmod(0o755)
            application = register(paths, launcher, context_menu=False)
            self.assertIn("Type=Application", application.read_text())
            self.assertIn("%%", application.read_text())
            service = paths.data.parent / "kio/servicemenus/subjector.desktop"
            self.assertFalse(service.exists())
            self.assertEqual(register(paths, launcher, context_menu=False), application)
            register(paths, launcher, context_menu=True)
            self.assertIn("X-KDE-RequiredNumberOfUrls=1", service.read_text())
            self.assertEqual(service.stat().st_mode & 0o777, 0o755)
            remove_context_menu(paths)
            self.assertFalse(service.exists())
            self.assertTrue(application.exists())

    @unittest.skipUnless(shutil.which("gio"), "requires the desktop entry launcher")
    def test_real_desktop_launch_preserves_special_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record, program = root / "arguments.json", root / "capture.py"
            program.write_text("import json,sys,pathlib\npathlib.Path(" + repr(str(record)) +
                               ").write_text(json.dumps(sys.argv[1:]))\n")
            launcher = root / 'launch % $ " \\ app.sh'
            launcher.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(program))} "$@"\n')
            launcher.chmod(0o755)
            entry = register(AppPaths.discover({}, root), launcher, context_menu=False)
            image = root / "- subject % ' photo.png"
            image.write_bytes(b"fixture")
            result = subprocess.run(["gio", "launch", str(entry), str(image)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            for _ in range(30):
                if record.exists():
                    break
                time.sleep(0.1)
            self.assertEqual(json.loads(record.read_text()), [str(image)])

    def test_unrelated_entries_are_never_overwritten_or_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = AppPaths.discover({}, Path(directory))
            service = paths.data.parent / "kio/servicemenus/subjector.desktop"
            service.parent.mkdir(parents=True)
            service.write_text("user-owned contents")
            launcher = Path(directory) / "launcher"
            launcher.write_text("#!/bin/sh\n")
            launcher.chmod(0o755)
            with self.assertRaises(IntegrationError):
                register(paths, launcher, context_menu=True)
            with self.assertRaises(IntegrationError):
                remove_context_menu(paths)
            self.assertEqual(service.read_text(), "user-owned contents")
