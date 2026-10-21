"""Validate a private CPU interpreter in a bounded, isolated subprocess."""

import json
import os
import re
import subprocess
from pathlib import Path


class RuntimeValidationError(Exception):
    """A private runtime failed its offline inference check."""


def validate_cpu(interpreter: Path, model: Path, version: str) -> dict[str, object]:
    worker = Path(__file__).with_name("_validate_cpu.py").resolve()
    try:
        result = subprocess.run(
            [str(interpreter), "-I", str(worker), str(model)],
            check=True, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120,
            env={"PATH": os.defpath, "LANG": "C.UTF-8", "HOME": str(model.parent)},
        )
        report = json.loads(result.stdout)
        _check_report(report, version)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError) as error:
        raise RuntimeValidationError("The private CPU runtime failed its inference check.") from error
    return report


def _check_report(report: dict[str, object], version: str) -> None:
    expected = {
        "schema": 1, "backend": "cpu", "rembg": version,
        "providers": ["CPUExecutionProvider"],
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
