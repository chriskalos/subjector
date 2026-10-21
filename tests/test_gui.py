import subprocess
import unittest
from unittest.mock import patch

from subjector.gui import Dialogs


class DialogTests(unittest.TestCase):
    @patch("subjector.gui.subprocess.run")
    def test_confirmation_requires_an_explicit_checked_approval(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        self.assertFalse(Dialogs().confirm("download $something; not a shell"))
        args = run.call_args.args[0]
        self.assertIn("--checklist", args)
        self.assertEqual(args[-1], "off")
        self.assertIn("download $something; not a shell", args)
        run.return_value.stdout = '\"allow\"\n'
        self.assertTrue(Dialogs().confirm("Approve?"))
        run.return_value.returncode = 1
        self.assertFalse(Dialogs().confirm("Approve?"))

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
