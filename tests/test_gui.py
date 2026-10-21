import subprocess
import unittest
from unittest.mock import patch

from subjector.gui import Dialogs


class DialogTests(unittest.TestCase):
    @patch("subjector.gui.subprocess.run")
    def test_confirmation_defaults_to_no_and_preserves_text_arguments(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, stdout="", stderr="")
        self.assertFalse(Dialogs().confirm("download $something; not a shell"))
        args = run.call_args.args[0]
        self.assertIn("--default", args)
        self.assertIn("No", args)
        self.assertIn("download $something; not a shell", args)

    @patch("subjector.gui.subprocess.run")
    def test_progress_is_updated_and_closed_through_dbus(self, run):
        run.return_value = subprocess.CompletedProcess([], 0,
            stdout="org.kde.kdialog-test /ProgressDialog\n", stderr="")
        dialogs = Dialogs()
        dialogs.status("Downloading")
        dialogs.status("Processing")
        dialogs.close()
        self.assertIn("setLabelText", run.call_args_list[-2].args[0])
        self.assertEqual(run.call_args.args[0][-1], "close")
