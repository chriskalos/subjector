import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from subjector.clipboard import CopyError, copy_subject


class ClipboardTests(unittest.TestCase):
    @patch("subjector.clipboard.shutil.which", return_value="/usr/bin/wl-copy")
    @patch("subjector.clipboard.subprocess.run")
    def test_copies_png_bytes_not_a_path(self, run, which):
        payload = b"\x89PNG\r\n\x1a\nfixture"
        def invoke(command, **kwargs):
            if command[0] != "/usr/bin/wl-copy":
                Path(command[-1]).write_bytes(payload)
            return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")
        run.side_effect = invoke
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "versions/runtime"
            runtime.mkdir(parents=True)
            source = Path("/tmp/- image with ' quotes.png")
            copy_subject(runtime, source)
            self.assertEqual(run.call_args.kwargs["input"], payload)
            self.assertEqual(run.call_args.kwargs["stdout"], subprocess.DEVNULL)
            self.assertEqual(run.call_args.kwargs["stderr"], subprocess.DEVNULL)
            self.assertEqual(run.call_args.args[0], ["/usr/bin/wl-copy", "--type", "image/png"])
            self.assertEqual(run.call_args_list[0].args[0][-3], str(source))

    @patch("subjector.clipboard.shutil.which", return_value="/usr/bin/wl-copy")
    @patch("subjector.clipboard.subprocess.run")
    def test_failed_inference_does_not_touch_clipboard(self, run, which):
        run.return_value = subprocess.CompletedProcess([], 1, stdout=json.dumps({"error": "Bad image"}), stderr="")
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "versions/runtime"
            runtime.mkdir(parents=True)
            with self.assertRaisesRegex(CopyError, "Bad image"):
                copy_subject(runtime, Path("/input.png"))
        self.assertEqual(run.call_count, 1)

    @patch("subjector.clipboard.shutil.which", return_value="/usr/bin/wl-copy")
    @patch("subjector.clipboard.subprocess.run")
    def test_native_gpu_crash_retries_on_cpu_and_persists_fallback(self, run, which):
        payload = b"\x89PNG\r\n\x1a\nfixture"
        def invoke(command, **kwargs):
            if kwargs.get("env", {}).get("SUBJECTOR_BACKEND") == "cuda":
                return subprocess.CompletedProcess(command, -11, stdout="", stderr="crashed")
            if command[0] != "/usr/bin/wl-copy":
                Path(command[-1]).write_bytes(payload)
            return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")
        run.side_effect = invoke
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "versions/runtime"
            runtime.mkdir(parents=True)
            (runtime / "manifest.json").write_text(json.dumps({"validation": {"backend": "cuda"}}))
            copy_subject(runtime, Path("/input.png"))
            self.assertIn("crashed", (runtime / "cpu-fallback").read_text())
            self.assertEqual(run.call_args_list[1].kwargs["env"]["SUBJECTOR_BACKEND"], "cpu")
            self.assertEqual(run.call_args.kwargs["input"], payload)

    @patch("subjector.clipboard.shutil.which", return_value=None)
    @patch("subjector.clipboard.subprocess.run")
    def test_missing_clipboard_helper_fails_before_inference(self, run, which):
        with self.assertRaisesRegex(CopyError, "wl-copy"):
            copy_subject(Path("/runtime"), Path("/input.png"))
        run.assert_not_called()
