"""Exercise CPU provisioning with synthetic archives and mocked external I/O."""

import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from subjector.cpu_install import CpuInputs, LocalArtifact, ProvisionError, install_cpu
from subjector.network import Artifact
from subjector.releases import RembgRelease
from subjector.runtimes import RuntimeStore


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CpuInstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        archive_path = self.root / "python.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            member = tarfile.TarInfo("python/bin/python3")
            member.mode, member.size = 0o700, 4
            archive.addfile(member, io.BytesIO(b"stub"))
        model = self.root / "model.onnx"
        model.write_bytes(b"model fixture")
        self.wheel = b"wheel fixture"
        release = RembgRelease("2.0.85", ">=3.11", Artifact(
            "https://files.pythonhosted.org/packages/rembg-2.0.85-py3-none-any.whl",
            hashlib.sha256(self.wheel).hexdigest(), len(self.wheel),
        ))
        self.inputs = CpuInputs(LocalArtifact(archive_path, digest(archive_path)),
                                LocalArtifact(model, digest(model)), release)
        self.store = RuntimeStore(self.root / "subjector")

    def process_result(self, command, **kwargs):
        output = ""
        if "-c" in command:
            output = str(Path(command[0]).parent.parent)
        elif "--report" in command:
            Path(command[command.index("--report") + 1]).write_text('{"install": []}')
        elif any(argument.endswith("_validate_cpu.py") for argument in command):
            output = json.dumps({
                "schema": 1, "backend": "cpu", "python": "3.13.0", "rembg": "2.0.85",
                "onnxruntime": "1.23.0", "providers": ["CPUExecutionProvider"],
                "output_mode": "RGBA", "output_size": [64, 64], "png_bytes": 500,
                "model_sha256": self.inputs.model.sha256,
            })
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    @patch("urllib.request.OpenerDirector.open")
    @patch("subprocess.run")
    def test_installs_into_private_prefix_and_records_provenance(self, run, open_request):
        response = io.BytesIO(self.wheel)
        response.status = 200
        open_request.return_value = response
        run.side_effect = self.process_result
        installed = install_cpu(self.store, self.inputs)
        self.assertEqual(self.store.current(), installed)
        manifest = json.loads((installed / "manifest.json").read_text())["validation"]
        self.assertEqual(manifest["python_archive_sha256"], self.inputs.python.sha256)
        self.assertEqual(manifest["rembg_wheel_sha256"], self.inputs.release.wheel.sha256)
        commands = [call.args[0] for call in run.call_args_list]
        install = next(command for command in commands if "--report" in command)
        self.assertIn("--only-binary=:all:", install)
        self.assertTrue(install[-1].endswith(".whl[cpu]"))
        self.assertTrue(all(command[0].startswith(str(installed)) for command in commands))

    @patch("urllib.request.OpenerDirector.open")
    @patch("subprocess.run")
    def test_prefix_alias_to_same_private_directory_is_accepted(self, run, open_request):
        alias = self.root / "home-alias"
        self.root.joinpath("actual-home").mkdir()
        alias.symlink_to(self.root / "actual-home", target_is_directory=True)
        self.store = RuntimeStore(alias / "subjector")
        response = io.BytesIO(self.wheel)
        response.status = 200
        open_request.return_value = response
        def invoke(command, **kwargs):
            result = self.process_result(command, **kwargs)
            if "-c" in command:
                result.stdout = str(Path(result.stdout).resolve())
            return result
        run.side_effect = invoke
        installed = install_cpu(self.store, self.inputs)
        self.assertEqual(self.store.current(), installed)

    @patch("subprocess.run")
    def test_corrupt_local_artifact_never_executes_code(self, run):
        self.inputs.python.path.write_bytes(b"corrupt archive")
        with self.assertRaises(ProvisionError):
            install_cpu(self.store, self.inputs)
        run.assert_not_called()
        self.assertIsNone(self.store.current())

    @patch("subprocess.run")
    def test_interpreter_with_wrong_prefix_is_rejected_before_pip(self, run):
        run.return_value.stdout = "/usr"
        with self.assertRaises(ProvisionError):
            install_cpu(self.store, self.inputs)
        self.assertEqual(run.call_count, 1)
        self.assertIsNone(self.store.current())

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("python", 600))
    def test_timeout_preserves_an_existing_runtime(self, run):
        original = self.store.install(lambda path: None, lambda path: {"fixture": True})
        with self.assertRaises(ProvisionError):
            install_cpu(self.store, self.inputs)
        self.assertEqual(self.store.current(), original)
