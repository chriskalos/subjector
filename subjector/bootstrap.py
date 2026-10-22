"""Consented Linux runtime acquisition with verified CUDA and CPU fallback."""

import hashlib
import platform
from collections.abc import Callable
from pathlib import Path

from subjector.cpu_install import CpuInputs, LocalArtifact, install_runtime
from subjector.hardware import probe_nvidia
from subjector.network import Artifact, download_verified
from subjector.paths import AppPaths
from subjector.releases import latest_rembg
from subjector.runtimes import RuntimeStore

# Python digest/size: official python-build-standalone release asset metadata.
PYTHON = Artifact(
    "https://github.com/astral-sh/python-build-standalone/releases/download/20261020/"
    "cpython-3.13.16%2B20261020-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz",
    "f326b7a386bf22def82e55dc3b95d2bef8b7c938b4c98ec32dd65433e7720b50", 35370434,
)
# Audited upstream download, also matched rembg's published MD5 before pinning SHA-256.
MODEL = Artifact(
    "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx",
    "309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8", 4574861,
)


def ensure_runtime(paths: AppPaths, confirm: Callable[[str], bool],
                   status: Callable[[str], None], *, refresh: bool = False,
                   cpu_only: bool = False) -> Path | None:
    store = RuntimeStore(paths.data)
    if not refresh:
        current = store.current()
        if current is not None:
            return current
    if platform.machine() not in {"x86_64", "AMD64"}:
        raise RuntimeError("Subjector v1 supports Linux x86_64 only.")
    if not confirm("Allow Subjector to contact PyPI to check the latest rembg release?\n"
                   "This first step reads metadata only. No image is sent."):
        return None
    release = latest_rembg()
    use_cuda = not cpu_only and bool(probe_nvidia().devices)
    backend = "CUDA (NVIDIA), with automatic CPU fallback" if use_cuda else "CPU"
    if not confirm(
        f"Download and run rembg {release.version}? Backend: {backend}.\n\n"
        "Also downloads Python 3.13.16 (35 MB) and U2Netp model weights (4.6 MB).\n"
        "CPU dependencies need about 1 GB of disk; CUDA can need several GB.\n"
        "For a smaller download, cancel and choose CPU-only setup.\n"
        "Sources: PyPI/files.pythonhosted.org and GitHub release assets.\n"
        f"Installation: {paths.data}\n\n"
        "No system Python or GPU drivers are changed. Failed updates preserve the old runtime.\n"
        "Images stay on your computer. Setup can take several minutes. Continue?"
    ):
        return None
    paths.cache.mkdir(mode=0o700, parents=True, exist_ok=True)
    status("Downloading and verifying private Python (35 MB)…")
    python = _cached(PYTHON, paths.cache / "python-3.13.16.tar.gz")
    status("Downloading and verifying U2Netp model (4.6 MB)…")
    model = _cached(MODEL, paths.cache / "u2netp.onnx")
    inputs = CpuInputs(python, model, release)
    if use_cuda:
        status(f"Installing rembg {release.version} with CUDA; verifying real GPU inference…")
        try:
            return install_runtime(store, inputs, backend="cuda", repair=refresh)
        except Exception as error:
            reason = str(error)[:1000]
            status("GPU setup was unavailable. Installing the separate CPU runtime instead…")
            runtime = install_runtime(store, inputs, repair=refresh)
            (runtime / "cpu-fallback").write_text(reason)
            return runtime
    status(f"Installing rembg {release.version} and CPU dependencies; then testing inference…")
    return install_runtime(store, inputs, repair=refresh)


def _cached(artifact: Artifact, path: Path) -> LocalArtifact:
    valid = False
    if path.is_file() and not path.is_symlink() and path.stat().st_size == artifact.size:
        with path.open("rb") as source:
            valid = hashlib.file_digest(source, "sha256").hexdigest() == artifact.sha256
    if not valid:
        download_verified(artifact, path)
    return LocalArtifact(path, artifact.sha256)
