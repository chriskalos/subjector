"""Cooperative cancellation, including termination of private worker processes."""

import os
import signal
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_checker: ContextVar[Callable[[], None] | None] = ContextVar("subjector_cancel", default=None)


class OperationCancelled(Exception):
    """The user cancelled an operation before its commit point."""


@contextmanager
def cancellable(check: Callable[[], None]) -> Iterator[None]:
    token = _checker.set(check)
    try:
        yield
    finally:
        _checker.reset(token)


def checkpoint() -> None:
    check = _checker.get()
    if check is not None:
        check()


def run_process(arguments: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Keep CLI subprocess.run semantics; poll cancellation in graphical flows."""
    if _checker.get() is None:
        return subprocess.run(arguments, **kwargs)
    import time
    timeout = kwargs.pop("timeout", None)
    check = kwargs.pop("check", False)
    if kwargs.pop("capture_output", False):
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.monotonic() + timeout if timeout else float("inf")
    checkpoint()
    with subprocess.Popen(arguments, start_new_session=True, **kwargs) as process:
        try:
            while True:
                checkpoint()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(arguments, timeout)
                try:
                    stdout, stderr = process.communicate(timeout=min(0.4, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise
    if check and process.returncode:
        raise subprocess.CalledProcessError(process.returncode, arguments, stdout, stderr)
    return subprocess.CompletedProcess(arguments, process.returncode, stdout, stderr)
