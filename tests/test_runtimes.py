"""A candidate runtime must pass validation before it becomes active."""

import json
import tempfile
import unittest
from pathlib import Path

from subjector.runtimes import RuntimeBusy, RuntimeStore, RuntimeStoreError


def prepare_runtime(path):
    (path / "python").write_text("candidate interpreter")


def validate_runtime(path):
    if (path / "python").read_text() != "candidate interpreter":
        raise ValueError("invalid interpreter")
    return {"python": "3.13.0", "rembg": "2.0.85", "backend": "cpu"}


class RuntimeStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "subjector"
        self.store = RuntimeStore(self.root)

    def test_discovery_does_not_create_directories(self):
        self.assertIsNone(self.store.current())
        self.assertFalse(self.root.exists())

    def test_activates_validated_runtime_without_moving_its_directory(self):
        prepared = []

        def prepare(path):
            prepared.append(path)
            prepare_runtime(path)
            self.assertIsNone(self.store.current())

        installed = self.store.install(prepare, validate_runtime)
        self.assertEqual(installed, prepared[0])
        self.assertEqual(installed, self.store.current())
        manifest = json.loads((installed / "manifest.json").read_text())
        self.assertEqual(manifest["validation"]["backend"], "cpu")
        self.assertEqual(installed.stat().st_mode & 0o777, 0o700)

    def test_failed_preparation_or_validation_preserves_active_runtime(self):
        original = self.store.install(prepare_runtime, validate_runtime)
        old_pointer = (self.root / "active.json").read_bytes()

        def fail(path):
            (path / "partial").write_text("incomplete")
            raise RuntimeError("failure")

        for prepare, validate in ((fail, validate_runtime), (prepare_runtime, fail)):
            with self.subTest(prepare=prepare), self.assertRaises(RuntimeError):
                self.store.install(prepare, validate)
            self.assertEqual(self.store.current(), original)
            self.assertEqual((self.root / "active.json").read_bytes(), old_pointer)
            self.assertEqual(list((self.root / "versions").iterdir()), [original])

    def test_successful_update_retains_previous_runtime(self):
        original = self.store.install(prepare_runtime, validate_runtime)
        updated = self.store.install(prepare_runtime, validate_runtime)
        self.assertNotEqual(original, updated)
        self.assertTrue(original.is_dir())
        self.assertEqual(self.store.current(), updated)

    def test_concurrent_installation_is_rejected_without_damaging_owner(self):
        def prepare(path):
            with self.assertRaises(RuntimeBusy):
                self.store.install(prepare_runtime, validate_runtime)
            prepare_runtime(path)

        installed = self.store.install(prepare, validate_runtime)
        self.assertEqual(self.store.current(), installed)

    def test_cancellation_cleans_candidate_and_releases_lock(self):
        def cancel(path):
            raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            self.store.install(cancel, validate_runtime)
        self.assertIsNone(self.store.current())
        self.assertEqual(list((self.root / "versions").iterdir()), [])
        self.assertEqual(self.store.install(prepare_runtime, validate_runtime), self.store.current())

    def test_invalid_active_pointer_is_not_treated_as_a_missing_installation(self):
        self.root.mkdir()
        for payload in ('{"runtime_id": "../../outside"}', '[]', 'not json'):
            with self.subTest(payload=payload):
                (self.root / "active.json").write_text(payload)
                with self.assertRaises(RuntimeStoreError):
                    self.store.current()

    def test_validation_must_return_a_serializable_report(self):
        for result in (None, {}, {"bad": object()}, {"bad": float("nan")}):
            with self.subTest(result=result), self.assertRaises(RuntimeStoreError):
                self.store.install(prepare_runtime, lambda path: result)
            self.assertIsNone(self.store.current())
            self.assertEqual(list((self.root / "versions").iterdir()), [])
