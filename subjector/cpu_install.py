"""CPU provisioning primitives for a consented, preselected private Python/model."""

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from subjector.archives import extract_runtime
from subjector.network import download_verified
from subjector.releases import RembgRelease
from subjector.runtime_check import validate_cpu
from subjector.runtimes import RuntimeStore


class ProvisionError(Exception):
    """Private runtime preparation failed before activation."""


@dataclass(frozen=True)
class LocalArtifact:
    path: Path
    sha256: str


@dataclass(frozen=True)
class CpuInputs:
    python: LocalArtifact
    model: LocalArtifact
    release: RembgRelease


def install_cpu(store: RuntimeStore, inputs: CpuInputs) -> Path:
    """Caller must obtain download/execution consent and trusted artifact hashes."""
    def prepare(candidate: Path) -> None:
        _prepare_python(candidate, inputs)
        _install_packages(candidate, inputs.release)

    def validate(candidate: Path) -> dict[str, object]:
        report = validate_cpu(_interpreter(candidate), candidate / "model.onnx", inputs.release.version)
        if report["model_sha256"] != inputs.model.sha256:
            raise ProvisionError("The inference worker used an unexpected model.")
        return {**report, "python_archive_sha256": inputs.python.sha256,
                "rembg_wheel_sha256": inputs.release.wheel.sha256, "pip_report": "pip-report.json"}

    return store.install(prepare, validate)


def _interpreter(candidate: Path) -> Path:
    return candidate / "runtime/python/bin/python3"


def _prepare_python(candidate: Path, inputs: CpuInputs) -> None:
    archive = candidate / "python.tar.gz"
    _copy_verified(inputs.python, archive)
    _copy_verified(inputs.model, candidate / "model.onnx")
    extract_runtime(archive, candidate / "runtime")
    archive.unlink()
    for name in ("home", "tmp"):
        (candidate / name).mkdir(mode=0o700)
    prefix = _run(candidate, ["-c", "import sys; print(sys.prefix)"]).stdout.strip()
    if Path(prefix) != _interpreter(candidate).parent.parent:
        raise ProvisionError("The downloaded interpreter is not using its private prefix.")


def _install_packages(candidate: Path, release: RembgRelease) -> None:
    wheel = candidate / f"rembg-{release.version}-py3-none-any.whl"
    download_verified(release.wheel, wheel)
    _run(candidate, ["-m", "ensurepip", "--upgrade"])
    _run(candidate, [
        "-m", "pip", "--isolated", "--disable-pip-version-check", "--no-input",
        "install", "--quiet", "--no-cache-dir", "--only-binary=:all:",
        "--index-url", "https://pypi.org/simple", "--report", str(candidate / "pip-report.json"),
        f"{wheel}[cpu]",
    ])
    _run(candidate, ["-m", "pip", "--isolated", "--disable-pip-version-check", "check"])
    report = candidate / "pip-report.json"
    if not report.is_file() or report.is_symlink():
        raise ProvisionError("The package installer did not produce its provenance report.")


def _run(candidate: Path, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [str(_interpreter(candidate)), "-I", *arguments], check=True,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
            env={"PATH": os.defpath, "LANG": "C.UTF-8", "HOME": str(candidate / "home"),
                 "TMPDIR": str(candidate / "tmp"), "PIP_CONFIG_FILE": os.devnull},
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ProvisionError("Private Python setup failed. No candidate was activated.") from error


def _copy_verified(artifact: LocalArtifact, destination: Path) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", artifact.sha256) or not artifact.path.is_file():
        raise ProvisionError("A regular local artifact and trusted SHA-256 are required.")
    digest, total = hashlib.sha256(), 0
    with artifact.path.open("rb") as source, destination.open("xb") as output:
        while chunk := source.read(64 * 1024):
            total += len(chunk)
            if total > 512 * 1024 * 1024:
                raise ProvisionError("The local artifact exceeds the 512 MiB limit.")
            digest.update(chunk)
            output.write(chunk)
    destination.chmod(0o600)
    if digest.hexdigest() != artifact.sha256:
        raise ProvisionError("Local artifact SHA-256 verification failed.")
