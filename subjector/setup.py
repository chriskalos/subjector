"""Consent-gated metadata inspection, separate from runtime installation."""

import sys

from subjector.network import DownloadError
from subjector.paths import AppPaths
from subjector.releases import ReleaseError, latest_rembg


def check_setup(paths: AppPaths) -> int:
    """Ask before reading release metadata. Never install or download a package."""
    print("Subjector can contact https://pypi.org to check the latest rembg release.")
    print("This downloads metadata only. No image is sent and no package is installed.")
    print(f"Future runtime location: {paths.data}")
    try:
        consent = input("Allow this metadata request? [y/N] ").strip().casefold()
    except (EOFError, KeyboardInterrupt):
        consent = ""
    if consent not in {"y", "yes"}:
        print("Check cancelled. No network request was made.")
        return 0
    return _report_release()


def _report_release() -> int:
    try:
        release = latest_rembg()
    except (DownloadError, ReleaseError) as error:
        print(f"Setup check failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Check interrupted. No software was installed.", file=sys.stderr)
        return 130
    print(f"Latest stable rembg: {release.version}")
    print(f"Declared Python requirement: {release.requires_python}")
    print(f"rembg wheel: {release.wheel.size:,} bytes from files.pythonhosted.org")
    print("This size excludes Python, dependencies, GPU libraries, and model weights.")
    print("Compatibility is not verified. Software was not installed.")
    print("To install after consent, run Subjector setup --install or choose setup in the GUI.")
    return 0
