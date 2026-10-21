#!/bin/sh
# KDE preview launcher. Resolve resources independently of the caller's directory.
set -eu
if [ "$#" -eq 1 ]; then
    case "$1" in
        /*) ;;
        *) set -- "$(pwd)/$1" ;;
    esac
fi
cd -- "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec python3 -m subjector gui -- "$@"
