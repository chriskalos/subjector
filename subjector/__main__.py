"""Developer CLI. Diagnostics never install dependencies or contact services."""

import argparse
import os
import platform
import sys
from pathlib import Path

from subjector.hardware import probe_nvidia
from subjector.paths import AppPaths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="subjector", description="Subjector for Linux")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("doctor", help="show local capabilities without installing anything")
    arguments = parser.parse_args(argv)
    if arguments.command is None:
        parser.print_help()
        return 0
    if sys.platform != "linux":
        print("Subjector supports Linux only.", file=sys.stderr)
        return 1
    _print_diagnostics()
    return 0


def _print_diagnostics() -> None:
    paths = AppPaths.discover(os.environ, Path.home())
    probe = probe_nvidia()
    print(f"Platform: Linux {platform.machine()}")
    print(f"Desktop: {os.environ.get('XDG_CURRENT_DESKTOP') or 'unknown'}")
    print(f"Session: {os.environ.get('XDG_SESSION_TYPE') or 'unknown'}")
    print(f"Data: {paths.data}")
    print(f"Config: {paths.config}")
    print(f"Cache: {paths.cache}")
    for device in probe.devices:
        print(f"NVIDIA: {device.name} (driver {device.driver})")
    print(f"Backend selection: {probe.detail}")
    print("Inference runtime: not installed or verified by this development version.")
    print("Diagnostics do not download software or change desktop integrations.")


if __name__ == "__main__":
    raise SystemExit(main())
