"""Extract verified Python tar.gz archives into a new, private staging directory."""

import gzip
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from subjector.operations import checkpoint


class ExtractionError(Exception):
    """An archive cannot be safely extracted under the runtime policy."""


@dataclass(frozen=True)
class ExtractionLimits:
    members: int = 20_000
    file_bytes: int = 512 * 1024 * 1024
    total_bytes: int = 2 * 1024 * 1024 * 1024
    header_bytes: int = 1024 * 1024


class _BoundedTarStream:
    """Limit allocations and gzip seeks before tarfile parses extended headers."""

    def __init__(self, stream: gzip.GzipFile, limits: ExtractionLimits):
        self.stream = stream
        self.read_limit = limits.header_bytes
        self.end_limit = limits.total_bytes + limits.members * 1024 + limits.header_bytes

    def tell(self) -> int:
        return self.stream.tell()

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence not in (0, 1):
            raise ExtractionError("Unsupported archive seek.")
        target = offset + (self.tell() if whence == 1 else 0)
        if not 0 <= target <= self.end_limit:
            raise ExtractionError("The archive exceeds its decoded size limit.")
        return self.stream.seek(target)

    def read(self, size: int) -> bytes:
        if not 0 <= size <= self.read_limit:
            raise ExtractionError("The archive header exceeds its read limit.")
        if self.tell() + size > self.end_limit:
            raise ExtractionError("The archive exceeds its decoded size limit.")
        return self.stream.read(size)


def extract_runtime(source: Path, destination: Path,
                    limits: ExtractionLimits = ExtractionLimits()) -> None:
    """Never merge with existing data. Remove staging on failure or interruption."""
    destination.mkdir(mode=0o700)
    try:
        with gzip.open(source, "rb") as compressed:
            stream = _BoundedTarStream(compressed, limits)
            with tarfile.open(fileobj=stream, mode="r:") as archive:
                members = _inspect_members(archive, limits)
                _extract_members(archive, members, destination)
    except BaseException as error:
        shutil.rmtree(destination)
        if isinstance(error, (tarfile.TarError, gzip.BadGzipFile, EOFError, ValueError)):
            raise ExtractionError("The runtime archive is invalid or truncated.") from error
        raise


def _member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (not name or len(name) > 4096 or len(path.parts) > 64 or path.is_absolute()
            or ".." in path.parts or path == PurePosixPath(".")
            or "\\" in name or "\x00" in name):
        raise ExtractionError("The archive contains an unsafe path.")
    return path


def _inspect_members(archive: tarfile.TarFile,
                     limits: ExtractionLimits) -> dict[PurePosixPath, tarfile.TarInfo]:
    members = {}
    total = 0
    for member in archive:
        checkpoint()
        path = _member_path(member.name)
        if path in members or len(members) >= limits.members:
            raise ExtractionError("The archive has duplicate paths or too many entries.")
        if not (member.isfile() or member.isdir() or member.issym()) or member.issparse():
            raise ExtractionError("The archive contains an unsupported entry type.")
        total += member.size
        if member.size < 0 or member.size > limits.file_bytes or total > limits.total_bytes:
            raise ExtractionError("The archive exceeds its expansion limit.")
        members[path] = member
    for path in members:
        for parent in path.parents:
            if parent in members and not members[parent].isdir():
                raise ExtractionError("An archive path has a non-directory ancestor.")
    return members


def _extract_members(archive: tarfile.TarFile,
                     members: dict[PurePosixPath, tarfile.TarInfo], root: Path) -> None:
    for path, member in members.items():
        checkpoint()
        target = root / path
        _private_directories(target.parent, root)
        if member.isdir():
            target.mkdir(mode=0o700, exist_ok=True)
        elif member.isfile():
            _extract_file(archive, member, target)
    # No links exist while files are written. An archive cannot redirect writes.
    for path, member in members.items():
        if member.issym():
            if not member.linkname or PurePosixPath(member.linkname).is_absolute():
                raise ExtractionError("The archive contains an unsafe symbolic link.")
            (root / path).symlink_to(member.linkname)
    for path, member in members.items():
        if member.issym():
            _validate_link(root / path, root.resolve())


def _private_directories(directory: Path, root: Path) -> None:
    if directory == root:
        return
    _private_directories(directory.parent, root)
    directory.mkdir(mode=0o700, exist_ok=True)


def _extract_file(archive: tarfile.TarFile, member: tarfile.TarInfo, target: Path) -> None:
    source = archive.extractfile(member)
    if source is None:
        raise ExtractionError("The archive entry has no file data.")
    with source, target.open("xb") as output:
        shutil.copyfileobj(source, output, length=64 * 1024)
    target.chmod(0o700 if member.mode & 0o111 else 0o600)


def _validate_link(link: Path, root: Path) -> None:
    try:
        resolved = link.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ExtractionError("The archive contains a cyclic or invalid symbolic link.") from error
    if not resolved.is_relative_to(root):
        raise ExtractionError("An archive symbolic link escapes the staging directory.")
