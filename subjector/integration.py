"""Explicit per-user Open With and Dolphin service-menu registration."""

import os
import tempfile
from pathlib import Path

from subjector.paths import AppPaths

OWNERSHIP = "X-Subjector-Managed=true"
MIME_TYPES = "image/png;image/jpeg;image/webp;"


class IntegrationError(Exception):
    """A desktop entry cannot be safely installed or removed."""


def launcher_path() -> Path:
    """AppImage mounts disappear after exit; desktop entries must name the image."""
    image = os.environ.get("APPIMAGE") or os.environ.get("SUBJECTOR_LAUNCHER")
    if image:
        path = Path(image)
        if not path.is_absolute():
            raise IntegrationError("APPIMAGE must identify an absolute executable path.")
        return path.resolve(strict=True)
    return Path(__file__).resolve().parents[1] / "subjector.sh"


def register(paths: AppPaths, launcher: Path, *, context_menu: bool) -> Path:
    launcher = launcher.resolve(strict=True)
    if not launcher.is_file() or not os.access(launcher, os.X_OK):
        raise IntegrationError("The Subjector launcher must be an executable file.")
    # GLib checks the executable before expanding %% in its name. A fixed env
    # executable preserves quoting while supporting both ELF AppImages and scripts.
    command = "/usr/bin/env -- " + _quote_exec(str(launcher)) + " %f"
    if context_menu:
        destination = _service_path(paths)
        content = (
            "[Desktop Entry]\nType=Service\nName=Copy subject\n"
            f"{OWNERSHIP}\nMimeType={MIME_TYPES}\nActions=CopySubject;\n"
            "X-KDE-Protocols=file\nX-KDE-RequiredNumberOfUrls=1\nX-KDE-Priority=TopLevel\n\n"
            "[Desktop Action CopySubject]\nName=Copy subject\nIcon=edit-copy\n"
            f"Exec={command}\n"
        )
    else:
        destination = paths.data.parent / "applications/subjector.desktop"
        content = (
            "[Desktop Entry]\nType=Application\nName=Subjector\n"
            "Comment=Copy an image subject without its background\nIcon=edit-copy\n"
            f"{OWNERSHIP}\nExec={command}\nMimeType={MIME_TYPES}\n"
            "Terminal=false\nStartupNotify=false\nCategories=Graphics;\n"
        )
    _ensure_owned(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                         prefix=".subjector-", delete=False) as output:
            temporary = Path(output.name)
            output.write(content)
        temporary.chmod(0o755 if context_menu else 0o644)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination


def remove_open_with(paths: AppPaths) -> None:
    destination = paths.data.parent / "applications/subjector.desktop"
    _ensure_owned(destination)
    destination.unlink(missing_ok=True)


def remove_context_menu(paths: AppPaths) -> None:
    destination = _service_path(paths)
    _ensure_owned(destination)
    destination.unlink(missing_ok=True)


def _service_path(paths: AppPaths) -> Path:
    return paths.data.parent / "kio/servicemenus/subjector.desktop"


def _ensure_owned(path: Path) -> None:
    if path.is_symlink() or (path.exists() and OWNERSHIP not in path.read_text().splitlines()):
        raise IntegrationError(f"Refusing to replace or remove an unrelated entry: {path}")


def _quote_exec(argument: str) -> str:
    if any(character in argument for character in "\n\r\t\x00"):
        raise IntegrationError("Move the repository to a path without control characters.")
    argument = argument.replace("%", "%%")
    escaped = "".join("\\" + char if char in '\\"`$' else char for char in argument)
    # Desktop Entry string escaping is applied before Exec argument parsing.
    return '"' + escaped.replace("\\", "\\\\") + '"'
