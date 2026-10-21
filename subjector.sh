#!/bin/sh
# KDE preview launcher. Resolve resources independently of the caller's directory.
set -eu
cd -- "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec python3 -m subjector gui -- "$@"
