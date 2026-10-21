"""Probe NVIDIA hardware without importing or installing an inference runtime."""

import csv
import io
import re
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class NvidiaDevice:
    name: str
    driver: str


@dataclass(frozen=True)
class NvidiaProbe:
    devices: tuple[NvidiaDevice, ...]
    detail: str


def probe_nvidia() -> NvidiaProbe:
    """Identify candidates only. Real CUDA inference is a separate setup gate."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return NvidiaProbe((), "NVIDIA probe unavailable or failed. Use the CPU runtime.")
    return _parse_devices(result.stdout)


def _parse_devices(output: str) -> NvidiaProbe:
    devices = []
    try:
        for row in csv.reader(io.StringIO(output), skipinitialspace=True, strict=True):
            if len(row) != 2:
                raise ValueError("Expected a device name and driver version")
            name, driver = (field.strip() for field in row)
            if not name or not re.fullmatch(r"\d+(?:\.\d+){1,3}", driver):
                raise ValueError("Invalid device name or driver version")
            devices.append(NvidiaDevice(name, driver))
    except (csv.Error, ValueError):
        return NvidiaProbe((), "NVIDIA probe returned invalid data. Use the CPU runtime.")
    if not devices:
        return NvidiaProbe((), "No NVIDIA devices detected. Use the CPU runtime.")
    return NvidiaProbe(tuple(devices), "NVIDIA runtime candidate. CUDA inference is not verified.")
