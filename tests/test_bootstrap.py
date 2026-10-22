"""Preview setup never downloads packages before installation consent."""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from subjector.bootstrap import ensure_runtime
from subjector.operations import OperationCancelled
from subjector.paths import AppPaths
from subjector.runtimes import RuntimeStore


class BootstrapTests(unittest.TestCase):
    @patch("urllib.request.OpenerDirector.open")
    def test_declining_metadata_creates_nothing(self, request):
        with tempfile.TemporaryDirectory() as root:
            paths = AppPaths.discover({}, Path(root))
            self.assertIsNone(ensure_runtime(paths, lambda text: False, print))
            self.assertEqual(list(Path(root).iterdir()), [])
        request.assert_not_called()

    @patch("urllib.request.OpenerDirector.open")
    def test_declining_installation_fetches_only_metadata(self, request):
        response = io.BytesIO((Path(__file__).parent / "fixtures/rembg-release.json").read_bytes())
        response.status = 200
        request.return_value = response
        answers = iter([True, False])
        with tempfile.TemporaryDirectory() as root:
            paths = AppPaths.discover({}, Path(root))
            self.assertIsNone(ensure_runtime(paths, lambda text: next(answers), print))
            self.assertEqual(list(Path(root).iterdir()), [])
        self.assertEqual(request.call_count, 1)

    @patch("subjector.bootstrap.latest_rembg")
    @patch("subjector.bootstrap.probe_nvidia")
    @patch("subjector.bootstrap._cached")
    @patch("subjector.bootstrap.install_runtime")
    def test_gpu_failure_uses_a_separate_cpu_install_and_records_the_reason(self, install, cached, probe, latest):
        with tempfile.TemporaryDirectory() as root:
            paths = AppPaths.discover({}, Path(root))
            runtime = paths.data / "versions/cpu"
            runtime.mkdir(parents=True)
            install.side_effect = [RuntimeError("CUDA unavailable"), runtime]
            result = ensure_runtime(paths, lambda text: True, lambda text: None)
            self.assertEqual(result, runtime)
            self.assertEqual(install.call_args_list[0].kwargs["backend"], "cuda")
            self.assertNotIn("backend", install.call_args_list[1].kwargs)
            self.assertEqual((runtime / "cpu-fallback").read_text(), "CUDA unavailable")

    @patch("subjector.bootstrap.latest_rembg")
    @patch("subjector.bootstrap.probe_nvidia")
    @patch("subjector.bootstrap._cached")
    @patch("subjector.bootstrap.install_runtime", side_effect=OperationCancelled())
    def test_gpu_cancellation_never_starts_a_cpu_install(self, install, cached, probe, latest):
        with tempfile.TemporaryDirectory() as root:
            paths = AppPaths.discover({}, Path(root))
            with self.assertRaises(OperationCancelled):
                ensure_runtime(paths, lambda text: True, lambda text: None)
        self.assertEqual(install.call_count, 1)

    @patch("urllib.request.OpenerDirector.open")
    def test_existing_runtime_is_reused_offline_without_prompts(self, request):
        with tempfile.TemporaryDirectory() as root:
            paths = AppPaths.discover({}, Path(root))
            installed = RuntimeStore(paths.data).install(lambda path: None, lambda path: {"fixture": True})
            def unexpected(text):
                self.fail("Existing installations must not prompt or reinstall")
            self.assertEqual(ensure_runtime(paths, unexpected, unexpected), installed)
        request.assert_not_called()
