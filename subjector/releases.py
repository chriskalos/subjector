"""Read PyPI's current rembg release without installing or importing it."""

import json
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from subjector.network import Artifact, DownloadError, fetch_bytes, validate_url

METADATA_URL = "https://pypi.org/pypi/rembg/json"
METADATA_LIMIT = 2 * 1024 * 1024
WHEEL_LIMIT = 32 * 1024 * 1024


class ReleaseError(Exception):
    """The latest release cannot be described safely by this bootstrap."""


@dataclass(frozen=True)
class RembgRelease:
    version: str
    requires_python: str
    wheel: Artifact


def latest_rembg() -> RembgRelease:
    """Contact PyPI only after the caller obtains network consent."""
    return parse_release(fetch_bytes(METADATA_URL, METADATA_LIMIT))


def parse_release(payload: bytes) -> RembgRelease:
    """Fail closed on changed metadata instead of selecting an older release."""
    try:
        metadata = json.loads(payload)
        info = metadata["info"]
        version, requires_python = info["version"], info["requires_python"]
        if info["name"] != "rembg" or info["yanked"] is not False:
            raise ValueError("Wrong project or withdrawn release")
        # rembg uses numeric releases. Unknown version schemes require review.
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+(?:\.post[0-9]+)?", version):
            raise ValueError("Unsupported or unstable release")
        if not requires_python or not re.fullmatch(r"[0-9<>=!~.*, ]{1,128}", requires_python):
            raise ValueError("Missing or invalid Python requirement")
        wheel = _select_wheel(metadata["urls"], version, requires_python)
        return RembgRelease(version, requires_python, wheel)
    except (KeyError, TypeError, ValueError, DownloadError) as error:
        raise ReleaseError("PyPI returned unsupported or invalid rembg release metadata.") from error


def _select_wheel(files: list[dict], version: str, requires_python: str) -> Artifact:
    filename = f"rembg-{version}-py3-none-any.whl"
    candidates = [item for item in files if item["filename"] == filename]
    if len(candidates) != 1:
        raise ValueError("Expected one universal rembg wheel")
    wheel = candidates[0]
    if wheel["packagetype"] != "bdist_wheel" or wheel["yanked"] is not False:
        raise ValueError("No usable wheel")
    if wheel["requires_python"] != requires_python:
        raise ValueError("Inconsistent Python requirement")
    url, digest, size = wheel["url"], wheel["digests"]["sha256"], wheel["size"]
    validate_url(url)
    location = urlsplit(url)
    if location.hostname != "files.pythonhosted.org" or location.path.rsplit("/", 1)[-1] != filename:
        raise ValueError("Wheel URL does not match package identity")
    if not re.fullmatch(r"[0-9a-f]{64}", digest) or type(size) is not int or not 0 < size <= WHEEL_LIMIT:
        raise ValueError("Invalid wheel digest or size")
    return Artifact(url, digest, size)
