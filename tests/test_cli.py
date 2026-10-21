"""Exercise diagnostics without network, installation, or desktop changes."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from subjector.__main__ import main


class CommandLineTests(unittest.TestCase):
    @patch("subjector.hardware.subprocess.run", side_effect=FileNotFoundError())
    @patch("subjector.__main__.sys.platform", "linux")
    def test_doctor_reports_cpu_and_paths_without_creating_files(self, run):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            environ = {"HOME": str(home), "XDG_SESSION_TYPE": "wayland"}
            output = io.StringIO()
            with patch.dict("os.environ", environ, clear=True):
                with contextlib.redirect_stdout(output):
                    self.assertEqual(main(["doctor"]), 0)
            self.assertIn("CPU", output.getvalue())
            self.assertIn(str(home / ".local/share/subjector"), output.getvalue())
            self.assertIn("wayland", output.getvalue())
            self.assertIn("not installed or verified", output.getvalue())
            self.assertEqual(list(home.iterdir()), [])

    @patch("subjector.hardware.subprocess.run")
    @patch("subjector.__main__.sys.platform", "linux")
    def test_doctor_reports_nvidia_as_unverified(self, run):
        run.return_value.stdout = "NVIDIA GeForce RTX 3060, 615.78.08\n"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["doctor"]), 0)
        self.assertIn("NVIDIA GeForce RTX 3060", output.getvalue())
        self.assertIn("615.78.08", output.getvalue())
        self.assertIn("not verified", output.getvalue())

    @patch("subjector.__main__.sys.platform", "darwin")
    def test_non_linux_systems_get_a_clear_error(self):
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            self.assertEqual(main(["doctor"]), 1)
        self.assertIn("Linux only", error.getvalue())

    def test_help_and_empty_command_do_not_probe_hardware(self):
        with patch("subjector.hardware.subprocess.run") as run:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main([]), 0)
                with self.assertRaises(SystemExit) as exit_info:
                    main(["--help"])
            self.assertEqual(exit_info.exception.code, 0)
            self.assertIn("doctor", output.getvalue())
            run.assert_not_called()

    def test_unknown_commands_are_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exit_info:
                main(["unknown-command"])
        self.assertEqual(exit_info.exception.code, 2)
