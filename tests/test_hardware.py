"""Local probes identify candidates, not verified inference backends."""

import subprocess
import unittest
from unittest.mock import patch

from subjector.hardware import probe_nvidia


class NvidiaProbeTests(unittest.TestCase):
    @patch("subjector.hardware.subprocess.run")
    def test_reports_devices_without_claiming_cuda_is_ready(self, run):
        run.return_value.stdout = (
            "NVIDIA GeForce RTX 3060, 615.78.08\n"
            '"NVIDIA device, second", 615.78.08\n'
        )

        probe = probe_nvidia()

        self.assertEqual(len(probe.devices), 2)
        self.assertEqual(probe.devices[0].name, "NVIDIA GeForce RTX 3060")
        self.assertEqual(probe.devices[0].driver, "615.78.08")
        self.assertEqual(probe.devices[1].name, "NVIDIA device, second")
        self.assertIn("not verified", probe.detail)
        self.assertGreater(run.call_args.kwargs["timeout"], 0)
        self.assertFalse(run.call_args.kwargs.get("shell", False))

    @patch("subjector.hardware.subprocess.run")
    def test_probe_failure_keeps_cpu_available(self, run):
        failures = (
            FileNotFoundError(),
            PermissionError(),
            subprocess.CalledProcessError(1, "nvidia-smi"),
            subprocess.TimeoutExpired("nvidia-smi", 3),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                run.side_effect = failure
                probe = probe_nvidia()
                self.assertEqual(probe.devices, ())
                self.assertIn("CPU", probe.detail)

    @patch("subjector.hardware.subprocess.run")
    def test_unusable_output_keeps_cpu_available(self, run):
        for output in (
            "", "\n", "No devices were found", "GPU, N/A", ", 615.78.08",
            "GPU, 615.78.08, extra", '"unterminated, 615.78.08',
            "GPU, 615.78.08\nbroken row",
        ):
            with self.subTest(output=output):
                run.return_value.stdout = output
                probe = probe_nvidia()
                self.assertEqual(probe.devices, ())
                self.assertIn("CPU", probe.detail)
