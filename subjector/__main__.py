"""Developer CLI. Diagnostics never install dependencies or contact services."""

import argparse
import os
import platform
import sys
from pathlib import Path

from subjector.hardware import probe_nvidia
from subjector.paths import AppPaths
from subjector.runtimes import RuntimeStore, RuntimeStoreError
from subjector.setup import check_setup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="subjector", description="Subjector for Linux")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("doctor", help="show local capabilities without installing anything")
    setup = commands.add_parser("setup", help="inspect setup requirements after consent")
    setup.add_argument("--check", action="store_true", required=True,
                       help="read release metadata only; installation is not available yet")
    arguments = parser.parse_args(argv)
    if arguments.command is None:
        parser.print_help()
        return 0
    if sys.platform != "linux":
        print("Subjector supports Linux only.", file=sys.stderr)
        return 1
    if arguments.command == "setup":
        return check_setup(AppPaths.discover(os.environ, Path.home()))
    return _print_diagnostics()


def _print_diagnostics() -> int:
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
    print("Diagnostics do not download software or change desktop integrations.")
    try:
        runtime = RuntimeStore(paths.data).current()
    except RuntimeStoreError as error:
        print(f"Runtime state error: {error}")
        return 1
    if runtime is None:
        print("Inference runtime: not installed or verified.")
    else:
        print(f"Active runtime: {runtime}")
        print("The active runtime was not executed by this diagnostic check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
