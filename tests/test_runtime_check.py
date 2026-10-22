"""A CPU runtime is ready only after a real inference worker reports success."""

import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from subjector.runtime_check import RuntimeValidationError, validate_cpu


class RuntimeCheckTests(unittest.TestCase):
    def setUp(self):
        self.report = {
            "schema": 1, "backend": "cpu", "python": "3.13.0", "rembg": "2.0.85",
            "onnxruntime": "1.23.0", "providers": ["CPUExecutionProvider"],
            "output_mode": "RGBA", "output_size": [64, 64], "png_bytes": 500,
            "model_sha256": "a" * 64,
        }

    @patch("subjector.runtime_check.subprocess.run")
    def test_accepts_only_the_expected_cpu_inference_report(self, run):
        run.return_value.stdout = json.dumps(self.report)
        result = validate_cpu(Path("/private/python"), Path("/private/model.onnx"), "2.0.85")
        self.assertEqual(result, self.report)
        arguments = run.call_args.args[0]
        self.assertEqual(arguments[:2], ["/private/python", "-I"])
        self.assertEqual(arguments[-1], "/private/model.onnx")
        self.assertGreater(run.call_args.kwargs["timeout"], 0)
        self.assertNotIn("PYTHONPATH", run.call_args.kwargs["env"])
        self.assertEqual(run.call_args.kwargs["env"]["U2NET_HOME"], "/private")
        self.assertFalse(run.call_args.kwargs.get("shell", False))

    @patch("subjector.runtime_check.subprocess.run")
    def test_model_root_uses_the_same_canonical_path_as_the_worker(self, run):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            real = Path(directory) / "real"
            real.mkdir()
            alias = Path(directory) / "alias"
            alias.symlink_to(real, target_is_directory=True)
            run.return_value.stdout = json.dumps(self.report)
            validate_cpu(Path("/python"), alias / "model.onnx", "2.0.85")
            self.assertEqual(run.call_args.kwargs["env"]["U2NET_HOME"], str(real))

    @patch("subjector.runtime_check.subprocess.run")
    def test_invalid_or_incompatible_reports_fail_validation(self, run):
        for key, value in (
            ("schema", 2), ("backend", "gpu"), ("rembg", "2.0.84"),
            ("providers", ["CUDAExecutionProvider", "CPUExecutionProvider"]),
            ("output_mode", "RGB"), ("output_size", [1, 1]),
            ("png_bytes", 0), ("png_bytes", True), ("model_sha256", "bad"),
            ("python", None), ("onnxruntime", None),
        ):
            with self.subTest(key=key, value=value):
                run.return_value.stdout = json.dumps({**self.report, key: value})
                with self.assertRaises(RuntimeValidationError):
                    validate_cpu(Path("/python"), Path("/model"), "2.0.85")
        for payload in ("not json", "[]", "{}"):
            run.return_value.stdout = payload
            with self.assertRaises(RuntimeValidationError):
                validate_cpu(Path("/python"), Path("/model"), "2.0.85")

    @patch("subjector.runtime_check.subprocess.run")
    def test_missing_interpreter_crash_or_timeout_cannot_activate_a_runtime(self, run):
        for error in (
            FileNotFoundError(), subprocess.CalledProcessError(-11, "python"),
            subprocess.TimeoutExpired("python", 120),
        ):
            with self.subTest(error=error):
                run.side_effect = error
                with self.assertRaises(RuntimeValidationError):
                    validate_cpu(Path("/python"), Path("/model"), "2.0.85")
