"""HTTP boundaries are mocked: this suite never contacts a service."""

import io
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.response import addinfourl

from subjector.network import DownloadError, fetch_bytes


class Response(io.BytesIO):
    status = 200


class NetworkTests(unittest.TestCase):
    @patch("urllib.request.OpenerDirector.open")
    def test_fetches_bounded_https_content(self, open_request):
        open_request.return_value = Response(b"metadata")
        self.assertEqual(fetch_bytes("https://pypi.org/pypi/rembg/json", 8), b"metadata")
        self.assertGreater(open_request.call_args.kwargs["timeout"], 0)

    @patch("urllib.request.OpenerDirector.open")
    def test_rejects_untrusted_urls_before_network_access(self, open_request):
        for url in (
            "http://pypi.org/a", "file:///etc/passwd", "https://example.org/a",
            "https://pypi.org.evil.test/a", "https://user@pypi.org/a",
            "https://pypi.org:444/a", "https://pypi.org/a#fragment",
            "https://pypi.org/a\nInjected", "https://pypi.org:bad/a",
        ):
            with self.subTest(url=url), self.assertRaises(DownloadError):
                fetch_bytes(url, 10)
        open_request.assert_not_called()

    @patch("urllib.request.OpenerDirector.open")
    def test_rejects_oversized_response(self, open_request):
        open_request.return_value = Response(b"too much")
        with self.assertRaisesRegex(DownloadError, "size"):
            fetch_bytes("https://pypi.org/a", 3)

    @patch("urllib.request.OpenerDirector.open")
    def test_reports_network_errors(self, open_request):
        for error in (URLError("offline"), TimeoutError("slow"), OSError("read failed")):
            with self.subTest(error=error):
                open_request.side_effect = error
                with self.assertRaises(DownloadError):
                    fetch_bytes("https://pypi.org/a", 10)

    @patch("urllib.request.OpenerDirector.open")
    def test_rejects_non_success_status(self, open_request):
        response = Response(b"partial data")
        response.status = 206
        open_request.return_value = response
        with self.assertRaises(DownloadError):
            fetch_bytes("https://pypi.org/a", 100)

    @patch("urllib.request.OpenerDirector.open")
    def test_total_read_deadline_is_bounded(self, open_request):
        open_request.return_value = Response(b"metadata")
        with patch("subjector.network.time.monotonic", side_effect=[0, 61]):
            with self.assertRaisesRegex(DownloadError, "time"):
                fetch_bytes("https://pypi.org/a", 100)

    @patch("urllib.request.HTTPSHandler.https_open")
    def test_redirect_is_rejected_and_response_closed(self, https_open):
        response = addinfourl(
            io.BytesIO(b"redirect"), {"location": "http://untrusted.test/package"},
            "https://pypi.org/a", 302,
        )
        response.msg = "Found"
        https_open.return_value = response
        with self.assertRaisesRegex(DownloadError, "redirect"):
            fetch_bytes("https://pypi.org/a", 100)
        self.assertTrue(response.closed)
        self.assertEqual(https_open.call_count, 1)

    @patch("urllib.request.HTTPSHandler.https_open")
    def test_github_redirect_can_reach_only_its_https_asset_host(self, https_open):
        first = addinfourl(io.BytesIO(b""),
                          {"location": "https://release-assets.githubusercontent.com/file?token=test"},
                          "https://github.com/owner/repo/releases/download/tag/file", 302)
        first.msg = "Found"
        second = addinfourl(io.BytesIO(b"asset"), {},
                           "https://release-assets.githubusercontent.com/file?token=test", 200)
        second.msg = "OK"
        https_open.side_effect = [first, second]
        self.assertEqual(fetch_bytes(first.url, 20), b"asset")

    @patch("urllib.request.OpenerDirector.open")
    def test_nonpositive_limit_does_not_contact_network(self, open_request):
        with self.assertRaises(ValueError):
            fetch_bytes("https://pypi.org/a", 0)
        open_request.assert_not_called()
