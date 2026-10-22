"""Real private processes must stop promptly without leaving children running."""

import subprocess
import sys
import time
import unittest

from subjector.operations import OperationCancelled, cancellable, run_process


class OperationTests(unittest.TestCase):
    def test_cancel_terminates_a_running_worker(self):
        start = time.monotonic()
        def check():
            if time.monotonic() - start > 0.1:
                raise OperationCancelled()
        with cancellable(check), self.assertRaises(OperationCancelled):
            run_process([sys.executable, "-c", "import time; time.sleep(60)"],
                        capture_output=True, text=True, timeout=30)
        self.assertLess(time.monotonic() - start, 3)

    def test_output_and_failure_semantics_are_preserved(self):
        with cancellable(lambda: None):
            result = run_process([sys.executable, "-c", "print('done')"],
                                 capture_output=True, text=True, timeout=5, check=True)
            self.assertEqual(result.stdout, "done\n")
            with self.assertRaises(subprocess.CalledProcessError):
                run_process([sys.executable, "-c", "raise SystemExit(4)"],
                            capture_output=True, timeout=5, check=True)
