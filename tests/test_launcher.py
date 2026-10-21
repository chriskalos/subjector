import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class LauncherTests(unittest.TestCase):
    def test_relative_image_path_survives_launch_from_another_directory(self):
        repository = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            helper = root / "python3"
            record = root / "launch.json"
            helper.write_text('#!/usr/bin/python3\nimport json,os,sys\n'
                              'open(os.environ["SUBJECTOR_CAPTURE"],"w").write('
                              'json.dumps({"args":sys.argv[1:],"cwd":os.getcwd()}))\n')
            helper.chmod(0o755)
            subprocess.run([str(repository / "subjector.sh"), "photo with spaces.png"],
                           cwd=root, check=True, timeout=10,
                           env={**os.environ, "PATH": f"{root}:/usr/bin:/bin",
                                "SUBJECTOR_CAPTURE": str(record)})
            result = json.loads(record.read_text())
            self.assertEqual(Path(result["cwd"]).resolve(), repository)
            self.assertEqual(result["args"][-1], str(root / "photo with spaces.png"))
