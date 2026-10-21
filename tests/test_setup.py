"""The metadata check requires consent and never installs software."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from subjector.__main__ import main

FIXTURE = Path(__file__).parent / "fixtures/rembg-release.json"


@patch("subjector.__main__.sys.platform", "linux")
class SetupCheckTests(unittest.TestCase):
    @patch("urllib.request.OpenerDirector.open")
    def test_decline_or_interruption_does_not_contact_network_or_create_files(self, open_request):
        for answer in ("", "n", "not sure", EOFError(), KeyboardInterrupt()):
            with self.subTest(answer=answer), tempfile.TemporaryDirectory() as directory:
                kwargs = {"side_effect": answer} if isinstance(answer, BaseException) else {"return_value": answer}
                with patch.dict("os.environ", {"HOME": directory}, clear=True):
                    with patch("builtins.input", **kwargs), contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(main(["setup", "--check"]), 0)
                self.assertEqual(list(Path(directory).iterdir()), [])
        open_request.assert_not_called()

    @patch("urllib.request.OpenerDirector.open")
    @patch("builtins.input", return_value=" YES ")
    def test_consent_reads_metadata_without_installing(self, prompt, open_request):
        response = io.BytesIO(FIXTURE.read_bytes())
        response.status = 200
        open_request.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch.dict("os.environ", {"HOME": directory}, clear=True):
                with contextlib.redirect_stdout(output):
                    self.assertEqual(main(["setup", "--check"]), 0)
            self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertIn("2.0.85", output.getvalue())
        self.assertIn("<4.0,>=3.11", output.getvalue())
        self.assertIn("not installed", output.getvalue())
        self.assertIn("pypi.org", output.getvalue())
        self.assertEqual(open_request.call_count, 1)
        self.assertIn("[y/N]", prompt.call_args.args[0])

    @patch("urllib.request.OpenerDirector.open", side_effect=URLError("offline"))
    @patch("builtins.input", return_value="y")
    def test_network_failure_is_actionable_not_a_traceback(self, prompt, open_request):
        with contextlib.redirect_stdout(io.StringIO()):
            with contextlib.redirect_stderr(io.StringIO()) as error:
                self.assertEqual(main(["setup", "--check"]), 1)
        self.assertIn("connection", error.getvalue())

    @patch("urllib.request.OpenerDirector.open")
    @patch("builtins.input", return_value="y")
    def test_invalid_metadata_reports_a_setup_error(self, prompt, open_request):
        response = io.BytesIO(b"{}")
        response.status = 200
        open_request.return_value = response
        with contextlib.redirect_stdout(io.StringIO()):
            with contextlib.redirect_stderr(io.StringIO()) as error:
                self.assertEqual(main(["setup", "--check"]), 1)
        self.assertIn("metadata", error.getvalue())

    @patch("urllib.request.OpenerDirector.open")
    def test_bare_setup_cannot_accidentally_start_installation(self, open_request):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                main(["setup"])
        self.assertEqual(error.exception.code, 2)
        open_request.assert_not_called()
