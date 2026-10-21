"""Discover application storage without changing the filesystem."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    data: Path
    config: Path
    cache: Path

    @classmethod
    def discover(cls, environ: Mapping[str, str], home: Path) -> "AppPaths":
        """Apply XDG defaults when overrides are empty or not absolute."""
        return cls(
            data=_app_directory(environ.get("XDG_DATA_HOME", ""), home / ".local/share"),
            config=_app_directory(environ.get("XDG_CONFIG_HOME", ""), home / ".config"),
            cache=_app_directory(environ.get("XDG_CACHE_HOME", ""), home / ".cache"),
        )


def _app_directory(override: str, default: Path) -> Path:
    candidate = Path(override)
    base = candidate if candidate.is_absolute() else default
    return base / "subjector"
