#!/usr/bin/env python3
"""Build the Bazzite/KDE test AppImage from verified upstream artifacts."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from subjector.archives import extract_runtime
from subjector.bootstrap import PYTHON
from subjector.network import Artifact, download_verified

TOOL = Artifact(
    "https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage",
    "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0", 15092216,
)
RUNTIME = Artifact(
    "https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64",
    "617aa77314d57c8b8e4fae9c3f0b35af7b30d5529cb69e98f64f92510ed98a46", 944632,
)


def acquire(artifact: Artifact, destination: Path) -> Path:
    valid = False
    if destination.is_file() and destination.stat().st_size == artifact.size:
        with destination.open("rb") as source:
            valid = hashlib.file_digest(source, "sha256").hexdigest() == artifact.sha256
    if not valid:
        print(f"Downloading verified build input: {destination.name}", flush=True)
        download_verified(artifact, destination)
    return destination


def stage(appdir: Path, archive: Path, revision: str) -> None:
    appdir.mkdir()
    (appdir / "usr").mkdir()
    extract_runtime(archive, appdir / "usr/runtime-stage")
    (appdir / "usr/runtime-stage/python").rename(appdir / "usr/python")
    (appdir / "usr/runtime-stage").rmdir()
    library = appdir / "usr/lib"
    library.mkdir()
    application = library / "subjector-app/subjector"
    application.mkdir(parents=True)
    for source in sorted((ROOT / "subjector").glob("*.py")):
        shutil.copy2(source, application / source.name)
    resources = ROOT / "packaging/appimage"
    for name in ("AppRun", "subjector.desktop", "subjector.svg"):
        shutil.copy2(resources / name, appdir / name)
    shutil.copy2(resources / "subjector-entry.py", library / "subjector-entry.py")
    (appdir / ".DirIcon").symlink_to("subjector.svg")
    (appdir / "usr/bin").mkdir()
    (appdir / "usr/bin/subjector").symlink_to("../../AppRun")
    shutil.copy2(ROOT / "README.md", appdir / "README.md")
    for name in ("THIRD_PARTY.md", "APPIMAGE_RUNTIME_LICENSE.txt"):
        shutil.copy2(resources / name, appdir / name)
    metadata = {"format": 1, "channel": "unsigned-kde-test", "revision": revision,
                "architecture": "x86_64", "python_sha256": PYTHON.sha256,
                "appimagetool_sha256": TOOL.sha256, "runtime_sha256": RUNTIME.sha256,
                "host_helpers": ["kdialog", "qdbus", "wl-copy"]}
    (appdir / "BUILD.json").write_text(json.dumps(metadata, indent=2) + "\n")
    # Private extraction permissions are unsuitable for a read-only image owned
    # by root. Normalize only this newly created AppDir, never user runtimes.
    for directory, subdirs, files in os.walk(appdir):
        Path(directory).chmod(0o755)
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink():
                path.chmod(0o755 if path.stat().st_mode & 0o111 else 0o644)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-archive", type=Path, help="reuse the verified bootstrap Python download")
    parser.add_argument("--output", type=Path, default=ROOT / "dist/Subjector-x86_64.AppImage")
    arguments = parser.parse_args()
    if sys.platform != "linux" or platform.machine() != "x86_64":
        parser.error("Build this test artifact on Linux x86_64.")
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    tools = build / "inputs"
    tools.mkdir(exist_ok=True)
    archive = arguments.python_archive or tools / "python.tar.gz"
    archive = acquire(PYTHON, archive.expanduser().resolve())
    tool = acquire(TOOL, tools / "appimagetool.AppImage")
    runtime = acquire(RUNTIME, tools / "runtime-x86_64")
    tool.chmod(0o700)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    epoch = subprocess.check_output(["git", "show", "-s", "--format=%ct", "HEAD"], cwd=ROOT, text=True).strip()
    output = arguments.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        parser.error(f"Output already exists: {output}. Choose a new --output or move it aside.")
    with tempfile.TemporaryDirectory(prefix="appimage-", dir=build) as temporary:
        appdir = Path(temporary) / "Subjector.AppDir"
        stage(appdir, archive, revision)
        subprocess.run([str(tool), "--appimage-extract-and-run", "--no-appstream",
                        "--runtime-file", str(runtime), str(appdir), str(output)],
                       check=True, env={**os.environ, "ARCH": "x86_64", "SOURCE_DATE_EPOCH": epoch},
                       timeout=600)
    output.chmod(0o755)
    with output.open("rb") as source:
        checksum = hashlib.file_digest(source, "sha256").hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(f"{checksum}  {output.name}\n")
    print(f"Built: {output}\nSHA-256: {checksum}")


if __name__ == "__main__":
    main()
