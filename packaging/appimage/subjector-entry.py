"""Entry point for the bundled interpreter. Never import from the caller's cwd."""

import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(root / "usr/lib/subjector-app"))
os.environ.setdefault("SUBJECTOR_LAUNCHER", str(root / "AppRun"))

from subjector.__main__ import main

arguments = sys.argv[1:]
commands = {"doctor", "setup", "update", "repair", "rollback", "copy", "gui", "integrate", "--help", "-h"}
if not arguments:
    arguments = ["gui"]
elif arguments[0] not in commands:
    arguments = ["gui", *arguments] if arguments[0] == "--" else ["gui", "--", *arguments]
raise SystemExit(main(arguments))
