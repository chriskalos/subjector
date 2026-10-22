"""Validate a private CPU interpreter in a bounded, isolated subprocess."""

import json
import os
import re
import subprocess
from pathlib import Path


class RuntimeValidationError(Exception):
    """A private runtime failed its offline inference check."""


def validate_cpu(interpreter: Path, model: Path, version: str) -> dict[str, object]:
    return validate_runtime(interpreter, model, version, backend="cpu")


def validate_runtime(interpreter: Path, model: Path, version: str, *, backend: str) -> dict[str, object]:
    worker = Path(__file__).with_name("_validate_cpu.py").resolve()
    flags = ["--cuda"] if backend == "cuda" else []
    try:
        result = subprocess.run(
            [str(interpreter), "-I", str(worker), *flags, str(model)],
            check=True, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120,
            env={"PATH": os.defpath, "LANG": "C.UTF-8", "HOME": str(model.parent),
                 "U2NET_HOME": str(model.parent)},
        )
        report = json.loads(result.stdout)
        _check_report(report, version, backend)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError) as error:
        raise RuntimeValidationError(f"The private {backend} runtime failed its inference check.") from error
    return report


def _check_report(report: dict[str, object], version: str, backend: str = "cpu") -> None:
    if backend == "cuda" and report.get("cuda_executed") is not True:
        raise ValueError("CUDA execution was not verified")
    expected = {
        "schema": 1, "backend": backend, "rembg": version,
        "providers": (["CUDAExecutionProvider", "CPUExecutionProvider"]
                      if backend == "cuda" else ["CPUExecutionProvider"]),
        "output_mode": "RGBA", "output_size": [64, 64],
    }
    if any(report[key] != value for key, value in expected.items()):
        raise ValueError("Unexpected inference result")
    if type(report["png_bytes"]) is not int or report["png_bytes"] <= 0:
        raise ValueError("No PNG output")
    for key in ("python", "onnxruntime"):
        if not isinstance(report[key], str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", report[key]):
            raise ValueError("Invalid runtime version")
    if not re.fullmatch(r"[0-9a-f]{64}", report["model_sha256"]):
        raise ValueError("Missing model identity")
