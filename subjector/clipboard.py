"""Run extraction and hand PNG ownership to the Wayland clipboard helper."""

import fcntl
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class CopyError(Exception):
    """The subject could not be extracted or copied."""


def copy_subject(runtime: Path, image: Path) -> None:
    helper = shutil.which("wl-copy")
    if helper is None:
        raise CopyError("This KDE/Wayland preview requires the existing wl-copy helper.")
    lock_path = runtime.parent.parent / ".copy.lock"
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "r+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise CopyError("Subjector is already processing an image. Try again shortly.") from error
        with tempfile.TemporaryDirectory(prefix="subjector-copy-") as directory:
            output = Path(directory) / "subject.png"
            _extract(runtime, image.absolute(), output)
            if output.stat().st_size > 128 * 1024 * 1024:
                raise CopyError("The extracted image is too large for this preview.")
            payload = output.read_bytes()
            if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
                raise CopyError("The inference worker did not produce a PNG image.")
            try:
                # wl-copy forks a long-lived owner. Captured output pipes can
                # remain open in that child and make communicate() wait forever.
                subprocess.run([helper, "--type", "image/png"], input=payload,
                               check=True, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=15)
            except (OSError, subprocess.SubprocessError) as error:
                raise CopyError("Could not copy the image. Use an active KDE Wayland session.") from error


def _extract(runtime: Path, image: Path, output: Path) -> None:
    interpreter = runtime / "runtime/python/bin/python3"
    worker = Path(__file__).with_name("_copy_image.py").resolve()
    manifest = runtime / "manifest.json"
    backend = "cpu"
    if manifest.exists() and not (runtime / "cpu-fallback").exists():
        backend = json.loads(manifest.read_text()).get("validation", {}).get("backend", "cpu")
    for attempt in (["cuda", "cpu"] if backend == "cuda" else ["cpu"]):
        try:
            result = subprocess.run(
                [str(interpreter), "-I", str(worker), str(image),
                 str(runtime / "model.onnx"), str(output)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                env={"PATH": os.defpath, "LANG": "C.UTF-8", "HOME": str(runtime / "home"),
                     "U2NET_HOME": str(runtime), "SUBJECTOR_BACKEND": attempt},
            )
            if result.returncode >= 0 or attempt == "cpu":
                break
        except (OSError, subprocess.SubprocessError) as error:
            if attempt == "cpu":
                raise CopyError("Image extraction failed or exceeded the two-minute limit.") from error
        (runtime / "cpu-fallback").write_text("GPU worker crashed or timed out; CPU fallback is active.")
        output.unlink(missing_ok=True)
    if result.returncode:
        try:
            message = json.loads(result.stdout)["error"]
        except (ValueError, KeyError, TypeError):
            message = "The image worker failed. Run Subjector setup or try another image."
        raise CopyError(str(message)[:1000])
