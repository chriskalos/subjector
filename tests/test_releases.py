"""Synthetic PyPI metadata verifies policy without downloading a wheel."""

import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from subjector.releases import ReleaseError, latest_rembg, parse_release

FIXTURE = Path(__file__).parent / "fixtures/rembg-release.json"


class ReleaseTests(unittest.TestCase):
    def test_reads_stable_release_and_declared_python_requirement(self):
        release = parse_release(FIXTURE.read_bytes())
        self.assertEqual(release.version, "2.0.85")
        self.assertEqual(release.requires_python, "<4.0,>=3.11")
        self.assertEqual(release.wheel.size, 12345)
        self.assertEqual(release.wheel.sha256, "a" * 64)

    def test_rejects_unusable_project_metadata(self):
        for field, value in (
            ("name", "another-project"), ("version", "2.1.0rc1"),
            ("version", "2.1.0.dev1"), ("version", "2.1.0+local"),
            ("version", None), ("yanked", True), ("requires_python", None),
            ("requires_python", ">=3.11\nmisleading output"),
        ):
            with self.subTest(field=field, value=value):
                metadata = json.loads(FIXTURE.read_bytes())
                metadata["info"][field] = value
                with self.assertRaises(ReleaseError):
                    parse_release(json.dumps(metadata).encode())

    def test_rejects_untrusted_or_incompatible_wheel_metadata(self):
        for field, value in (
            ("filename", "rembg-1.0.0-py3-none-any.whl"),
            ("packagetype", "sdist"), ("yanked", True),
            ("url", "https://example.org/rembg.whl"),
            ("url", "https://files.pythonhosted.org/packages/wrong.whl"),
            ("size", 0), ("size", True), ("size", 10**12),
            ("digests", {"sha256": "invalid"}),
            ("requires_python", ">=3.15"),
        ):
            with self.subTest(field=field, value=value):
                metadata = json.loads(FIXTURE.read_bytes())
                metadata["urls"][0][field] = value
                with self.assertRaises(ReleaseError):
                    parse_release(json.dumps(metadata).encode())

    def test_rejects_missing_fields_and_invalid_json(self):
        for payload in (b"not json", b"[]", b"null", b"{}", b"\xff", b'{"info": []}'):
            with self.subTest(payload=payload), self.assertRaises(ReleaseError):
                parse_release(payload)

    @patch("urllib.request.OpenerDirector.open")
    def test_fetches_only_the_fixed_project_endpoint(self, open_request):
        response = io.BytesIO(FIXTURE.read_bytes())
        response.status = 200
        open_request.return_value = response
        self.assertEqual(latest_rembg().version, "2.0.85")
        self.assertEqual(
            open_request.call_args.args[0].full_url,
            "https://pypi.org/pypi/rembg/json",
        )
