"""Exercise AppDir assembly without downloading or executing build tools."""

import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.build_appimage import stage


class AppDirBuildTests(unittest.TestCase):
    def test_contains_only_runtime_application_and_explicit_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "python.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                for name, mode, payload in (
                    ("python/bin/python3", 0o700, b"interpreter fixture"),
                    ("python/lib/python3.13/LICENSE.txt", 0o600, b"license fixture"),
                ):
                    member = tarfile.TarInfo(name)
                    member.size, member.mode = len(payload), mode
                    bundle.addfile(member, io.BytesIO(payload))
            appdir = root / "Subjector.AppDir"
            stage(appdir, archive, "test-revision")
            self.assertEqual((appdir / "usr/python/bin/python3").stat().st_mode & 0o777, 0o755)
            self.assertTrue((appdir / "usr/lib/subjector-app/subjector/__main__.py").is_file())
            self.assertTrue((appdir / "usr/python/lib/python3.13/LICENSE.txt").is_file())
            self.assertTrue((appdir / "usr/bin/subjector").samefile(appdir / "AppRun"))
            self.assertEqual(json.loads((appdir / "BUILD.json").read_text())["revision"], "test-revision")
            for path in appdir.rglob("*"):
                self.assertNotIn(path.name, {"PLAN.md", "AGENTS.md", ".git", "tests", "package-lock.json"})
