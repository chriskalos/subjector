"""Artifacts become visible only after size and SHA-256 verification."""

import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from subjector.network import Artifact, DownloadError, download_verified


class Response(io.BytesIO):
    status = 200


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.payload = b"verified package contents"
        self.artifact = Artifact(
            "https://files.pythonhosted.org/packages/rembg.whl",
            hashlib.sha256(self.payload).hexdigest(),
            len(self.payload),
        )

    @patch("urllib.request.OpenerDirector.open")
    def test_publishes_only_verified_content_with_private_permissions(self, open_request):
        open_request.return_value = Response(self.payload)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "package.whl"
            download_verified(self.artifact, destination)
            self.assertEqual(destination.read_bytes(), self.payload)
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(Path(directory).iterdir()), [destination])

    @patch("urllib.request.OpenerDirector.open")
    def test_integrity_failure_preserves_existing_file_and_removes_temporary_data(self, open_request):
        for content in (b"short", b"x" * len(self.payload), self.payload + b"extra"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / "existing.whl"
                destination.write_bytes(b"old package")
                open_request.return_value = Response(content)
                with self.assertRaises(DownloadError):
                    download_verified(self.artifact, destination)
                self.assertEqual(destination.read_bytes(), b"old package")
                self.assertEqual(list(Path(directory).iterdir()), [destination])

    @patch("urllib.request.OpenerDirector.open")
    def test_interrupt_removes_partial_file(self, open_request):
        open_request.side_effect = KeyboardInterrupt()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "package.whl"
            with self.assertRaises(KeyboardInterrupt):
                download_verified(self.artifact, destination)
            self.assertEqual(list(Path(directory).iterdir()), [])

    @patch("urllib.request.OpenerDirector.open")
    def test_invalid_manifest_cannot_start_a_download(self, open_request):
        with tempfile.TemporaryDirectory() as directory:
            for digest, size in (("bad", 3), ("z" * 64, 3), ("a" * 64, 0), ("a" * 64, True)):
                with self.subTest(digest=digest, size=size):
                    with self.assertRaises(DownloadError):
                        download_verified(
                            Artifact(self.artifact.url, digest, size),
                            Path(directory) / "package.whl",
                        )
            self.assertEqual(list(Path(directory).iterdir()), [])
        open_request.assert_not_called()
