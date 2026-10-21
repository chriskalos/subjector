"""Bounded HTTPS transport for approved package sources. No implicit redirects."""

import hashlib
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from http.client import HTTPException, HTTPResponse
from pathlib import Path

TRUSTED_HOSTS = frozenset({"pypi.org", "files.pythonhosted.org"})
SOCKET_TIMEOUT = 15
READ_DEADLINE = 60
CHUNK_SIZE = 64 * 1024


class DownloadError(Exception):
    """A download failed policy, transport, or integrity validation."""


@dataclass(frozen=True)
class Artifact:
    url: str
    sha256: str
    size: int


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DownloadError("Download redirects are not allowed.")


def validate_url(url: str) -> None:
    """Reject URLs outside the explicit HTTPS source policy."""
    if not isinstance(url, str):
        raise DownloadError("Download URL must be a string.")
    try:
        parsed = urllib.parse.urlsplit(url)
        allowed = (
            parsed.scheme == "https" and parsed.hostname in TRUSTED_HOSTS
            and parsed.port in (None, 443) and parsed.username is None
            and parsed.password is None and not parsed.fragment
            and not any(ord(character) <= 32 or ord(character) == 127 for character in url)
        )
    except ValueError:
        allowed = False
    if not allowed:
        raise DownloadError("Download URL is not an approved HTTPS source.")


def fetch_bytes(url: str, limit: int) -> bytes:
    """Fetch small metadata responses within a caller-supplied byte limit."""
    return b"".join(_chunks(url, limit))


def download_verified(artifact: Artifact, destination: Path) -> None:
    """Atomically publish a verified artifact in an existing trusted directory."""
    validate_url(artifact.url)
    if not re.fullmatch(r"[0-9a-f]{64}", artifact.sha256):
        raise DownloadError("Artifact SHA-256 is invalid.")
    if type(artifact.size) is not int or artifact.size <= 0:
        raise DownloadError("Artifact size must be a positive integer.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".subjector-", delete=False) as output:
            temporary = Path(output.name)
            digest, size = hashlib.sha256(), 0
            for chunk in _chunks(artifact.url, artifact.size):
                output.write(chunk)
                digest.update(chunk)
                size += len(chunk)
            if size != artifact.size or digest.hexdigest() != artifact.sha256:
                raise DownloadError("Artifact size or SHA-256 verification failed.")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _chunks(url: str, limit: int) -> Iterator[bytes]:
    validate_url(url)
    if limit <= 0:
        raise ValueError("Download size limit must be positive.")
    deadline = time.monotonic() + READ_DEADLINE
    request = urllib.request.Request(url, headers={"User-Agent": "Subjector/0.1"})
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=SOCKET_TIMEOUT) as response:
            if response.status != 200:
                raise DownloadError("Download server did not return a complete response.")
            yield from _read_chunks(response, limit, deadline)
    except (OSError, urllib.error.URLError, HTTPException) as error:
        raise DownloadError("Download failed. Check your connection and try again.") from error


def _read_chunks(response: HTTPResponse, limit: int, deadline: float) -> Iterator[bytes]:
    total = 0
    while True:
        if time.monotonic() >= deadline:
            raise DownloadError("Download exceeded its time limit.")
        # read1 returns available data so a slow stream cannot hide the deadline.
        chunk = response.read1(min(CHUNK_SIZE, limit - total + 1))
        if not chunk:
            return
        total += len(chunk)
        if total > limit:
            raise DownloadError("Download exceeded its size limit.")
        yield chunk
