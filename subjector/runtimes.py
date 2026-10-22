"""Locked runtime transactions. Preparation never changes the active pointer."""

import fcntl
import json
import os
import re
import shutil
import stat
import tempfile
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

MANIFEST_LIMIT = 64 * 1024


class RuntimeStoreError(Exception):
    """Runtime state is unsafe or invalid."""


class RuntimeBusy(RuntimeStoreError):
    """Another process already owns the setup lock."""


class RuntimeStore:
    def __init__(self, root: Path):
        self.root = root

    def current(self) -> Path | None:
        marker = self.root / "active.json"
        if not marker.exists() and not marker.is_symlink():
            return None
        _check_directory(self.root)
        pointer = _read_record(marker)
        identifier = pointer.get("runtime_id")
        if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{32}", identifier):
            raise RuntimeStoreError("The active runtime identifier is invalid.")
        runtime = self.root / "versions" / identifier
        _check_directory(runtime.parent)
        _check_directory(runtime)
        if not _read_record(runtime / "manifest.json").get("validation"):
            raise RuntimeStoreError("The active runtime has no validation report.")
        return runtime

    def install(self, prepare: Callable[[Path], None],
                validate: Callable[[Path], dict[str, object]], *, repair: bool = False) -> Path:
        """Publish only after both callbacks succeed. Never relocate an interpreter."""
        _create_private_directory(self.root)
        with _setup_lock(self.root):
            # Refuse to overwrite corrupt state silently during repair or update.
            if not repair:
                self.current()
            elif (self.root / "active.json").is_symlink():
                raise RuntimeStoreError("Remove the unexpected active.json symlink before repair.")
            versions = self.root / "versions"
            _create_private_directory(versions)
            candidate = versions / uuid.uuid4().hex
            candidate.mkdir(mode=0o700)
            try:
                prepare(candidate)
                report = validate(candidate)
                _write_manifest(candidate, report)
                _publish_pointer(self.root, candidate.name)
            except BaseException:
                self._remove_unselected(candidate)
                raise
            return candidate

    def rollback(self) -> Path:
        """Select the previously active, retained runtime without a download."""
        _check_directory(self.root)
        with _setup_lock(self.root):
            pointer = _read_record(self.root / "active.json")
            identifier = pointer.get("previous_id")
            if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{32}", identifier):
                raise RuntimeStoreError("No previous runtime is available for rollback.")
            previous = self.root / "versions" / identifier
            _check_directory(previous.parent)
            _check_directory(previous)
            if not _read_record(previous / "manifest.json").get("validation"):
                raise RuntimeStoreError("The previous runtime has no validation report.")
            _publish_pointer(self.root, identifier)
            return previous

    def _remove_unselected(self, candidate: Path) -> None:
        # An interruption can arrive after the atomic pointer swap succeeded.
        # Never delete a selected runtime, or one whose selection is uncertain.
        try:
            active = self.current()
        except RuntimeStoreError:
            return
        if active != candidate:
            shutil.rmtree(candidate)


def _check_directory(path: Path) -> None:
    try:
        info = path.lstat()
    except OSError as error:
        raise RuntimeStoreError("A runtime directory is missing or inaccessible.") from error
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise RuntimeStoreError("Runtime directories must be user-owned and not writable by others.")


def _create_private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    _check_directory(path)


@contextmanager
def _setup_lock(root: Path) -> Iterator[None]:
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
    with os.fdopen(os.open(root / ".setup.lock", flags, 0o600), "r+b") as lock:
        info = os.fstat(lock.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise RuntimeStoreError("The setup lock has unsafe ownership or permissions.")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeBusy("Another Subjector setup is already running.") from error
        # Closing releases the lock. Keep its inode so waiting processes cannot race.
        yield


def _encode_record(record: dict[str, object]) -> bytes:
    try:
        payload = json.dumps({"schema": 1, **record}, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise RuntimeStoreError("The validation report is not valid JSON.") from error
    if len(payload) > MANIFEST_LIMIT:
        raise RuntimeStoreError("The runtime record is too large.")
    return payload


def _write_manifest(candidate: Path, report: dict[str, object]) -> None:
    if not isinstance(report, dict) or not report:
        raise RuntimeStoreError("Runtime validation must return a nonempty report.")
    payload = _encode_record({"validation": report})
    path = candidate / "manifest.json"
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())


def _publish_pointer(root: Path, identifier: str) -> None:
    record = {"runtime_id": identifier}
    try:
        previous = _read_record(root / "active.json").get("runtime_id")
        if isinstance(previous, str) and re.fullmatch(r"[0-9a-f]{32}", previous):
            record["previous_id"] = previous
    except RuntimeStoreError:
        pass
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=root, prefix=".active-", delete=False) as output:
            temporary = Path(output.name)
            output.write(_encode_record(record))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, root / "active.json")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _read_record(path: Path) -> dict[str, object]:
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise RuntimeStoreError("The runtime record is not a regular file.")
            payload = source.read(MANIFEST_LIMIT + 1)
        if len(payload) > MANIFEST_LIMIT:
            raise ValueError("Record too large")
        record = json.loads(payload)
        if not isinstance(record, dict) or record.get("schema") != 1:
            raise ValueError("Invalid record schema")
        return record
    except (OSError, ValueError) as error:
        raise RuntimeStoreError("The runtime record is missing or invalid.") from error
