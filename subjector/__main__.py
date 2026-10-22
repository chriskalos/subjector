"""Linux preview entry points. Diagnostics remain offline and read-only."""

import argparse
import json
import os
import platform
import sys
from pathlib import Path

from subjector.bootstrap import ensure_runtime
from subjector.clipboard import copy_subject
from subjector.hardware import probe_nvidia
from subjector.paths import AppPaths
from subjector.runtimes import RuntimeStore, RuntimeStoreError
from subjector.setup import check_setup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="subjector", description="Subjector for Linux")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("doctor", help="show local capabilities without installing anything")
    setup = commands.add_parser("setup", help="inspect or install after consent")
    mode = setup.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="read release metadata only")
    mode.add_argument("--install", action="store_true", help="download and validate a private runtime")
    setup.add_argument("--cpu", action="store_true", help="force CPU-only installation")
    for command in ("update", "repair"):
        commands.add_parser(command, help="rebuild the latest runtime after consent").add_argument(
            "--cpu", action="store_true", help="force CPU-only installation")
    commands.add_parser("rollback", help="restore the previous runtime without downloads")
    commands.add_parser("gui", help="open the KDE preview").add_argument("image", nargs="?")
    commands.add_parser("copy", help="copy one local image's subject").add_argument("image")
    arguments = parser.parse_args(argv)
    if arguments.command is None:
        parser.print_help()
        return 0
    if sys.platform != "linux":
        print("Subjector supports Linux only.", file=sys.stderr)
        return 1
    try:
        return _dispatch(arguments)
    except KeyboardInterrupt:
        print("Subjector interrupted.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Subjector: {error}", file=sys.stderr)
        return 1


def _dispatch(arguments: argparse.Namespace) -> int:
    if arguments.command == "doctor":
        return _print_diagnostics()
    if arguments.command == "gui":
        from subjector.gui import preview
        return preview(arguments.image)
    paths = AppPaths.discover(os.environ, Path.home())
    if arguments.command == "rollback":
        print(f"Runtime selected: {RuntimeStore(paths.data).rollback()}")
        return 0
    if arguments.command == "setup" and arguments.check:
        return check_setup(paths)
    cpu_only = getattr(arguments, "cpu", False)
    runtime = ensure_runtime(paths, _console_confirm, print,
                             refresh=arguments.command in {"update", "repair"} or cpu_only,
                             cpu_only=cpu_only)
    if runtime is None:
        print("Cancelled. No runtime was installed.")
    elif arguments.command == "copy":
        copy_subject(runtime, Path(arguments.image))
        print("Subject copied as a transparent PNG.")
    else:
        print(f"Runtime ready: {runtime}")
    return 0


def _console_confirm(text: str) -> bool:
    print(text)
    try:
        return input("Continue? [y/N] ").strip().casefold() in {"y", "yes"}
    except EOFError:
        return False


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
        details = json.loads((runtime / "manifest.json").read_text())["validation"]
        fallback = runtime / "cpu-fallback"
        print(f"Backend: {'cpu (fallback)' if fallback.exists() else details.get('backend', 'unknown')}")
        if fallback.exists():
            print(f"Fallback reason: {fallback.read_text()[:1000]}")
        print("The active runtime was not executed by this diagnostic check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
