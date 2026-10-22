"""Small KDE preview UI using the desktop's existing kdialog and qdbus."""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from subjector.bootstrap import ensure_runtime
from subjector.clipboard import copy_subject
from subjector.integration import register, remove_context_menu, remove_open_with
from subjector.runtimes import RuntimeStore
from subjector.paths import AppPaths
from subjector.operations import OperationCancelled, cancellable


class Dialogs:
    def __init__(self) -> None:
        self.reference: list[str] = []
        self.last_poll = 0.0

    def ask(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["kdialog", "--title", "Subjector", *arguments],
                              capture_output=True, text=True, check=False)

    def confirm(self, text: str) -> bool:
        # kdialog's --default does not apply to yes/no dialogs. An unchecked
        # checklist makes Enter, Escape, and window-close safe on every theme.
        result = self.ask("--checklist", text, "allow", "I approve this action", "off")
        return result.returncode == 0 and result.stdout.strip('" \r\n') == "allow"

    def status(self, text: str) -> None:
        if not self.reference:
            result = self.ask("--progressbar", text, "0")
            reference = result.stdout.split()
            if result.returncode or len(reference) != 2:
                raise RuntimeError("Could not open the KDE progress dialog.")
            self.reference = reference
            self._dbus("showCancelButton", "true")
        else:
            self._dbus("setLabelText", text)

    def check_cancelled(self) -> None:
        if not self.reference or time.monotonic() - self.last_poll < 0.4:
            return
        self.last_poll = time.monotonic()
        result = subprocess.run(["qdbus", *self.reference, "wasCancelled"],
                                capture_output=True, text=True, timeout=5, check=False)
        if result.returncode or result.stdout.strip() == "true":
            raise OperationCancelled("Cancelled. The clipboard and active runtime are unchanged.")

    def close(self) -> None:
        if self.reference:
            self._dbus("close")
            self.reference = []

    def _dbus(self, *arguments: str) -> None:
        subprocess.run(["qdbus", *self.reference, *arguments], capture_output=True,
                       text=True, timeout=10, check=False)


def preview(image: str | None = None) -> int:
    dialogs = Dialogs()
    if shutil.which("kdialog") is None:
        print("This KDE preview requires the existing kdialog helper.", file=sys.stderr)
        return 1
    try:
        for helper in ("qdbus", "wl-copy"):
            if shutil.which(helper) is None:
                raise RuntimeError(f"This KDE preview requires the existing {helper} helper.")
        if not os.environ.get("WAYLAND_DISPLAY"):
            raise RuntimeError("Run this preview from a KDE Wayland desktop session.")
        paths = AppPaths.discover(os.environ, Path.home())
        with cancellable(dialogs.check_cancelled):
            return _workflow(dialogs, paths, image)
    except OperationCancelled:
        return 0
    except Exception as error:
        dialogs.close()
        dialogs.ask("--error", str(error))
        return 1
    finally:
        dialogs.close()


def _workflow(dialogs: Dialogs, paths: AppPaths, image: str | None) -> int:
    action = "copy"
    if image is None:
        choice = dialogs.ask("--menu", "Subjector", "copy", "Choose an image and copy its subject",
                             "setup", "Set up / check runtime (automatic GPU selection)",
                             "update", "Update or repair the runtime", "cpu", "Set up / repair using CPU only",
                             "rollback", "Restore the previous runtime", "register", "Add Subjector to Open With",
                             "context", "Enable Dolphin: Copy subject", "remove", "Disable Dolphin: Copy subject",
                             "unregister", "Remove Subjector from Open With")
        if choice.returncode:
            return 0
        action = choice.stdout.strip()
    if action in {"register", "context", "remove", "unregister"}:
        _integrate(dialogs, paths, action)
        return 0
    if action == "rollback":
        runtime = RuntimeStore(paths.data).rollback()
        dialogs.ask("--msgbox", f"Previous runtime selected:\n{runtime}")
        return 0
    if action == "copy" and image is None:
        choice = dialogs.ask("--getopenfilename", str(Path.home()), "*.png *.jpg *.jpeg *.webp|Images")
        if choice.returncode or not choice.stdout.strip():
            return 0
        image = choice.stdout.rstrip("\r\n")
    runtime = ensure_runtime(paths, dialogs.confirm, dialogs.status,
                             refresh=action in {"update", "cpu"}, cpu_only=action == "cpu")
    if runtime is None:
        return 0
    if action in {"setup", "update", "cpu"}:
        dialogs.close()
        note = " CPU fallback is active." if (runtime / "cpu-fallback").exists() else ""
        dialogs.ask("--msgbox", "The private runtime is ready. No image was uploaded." + note)
        return 0
    dialogs.status("Removing the background and copying the subject…")
    copy_subject(runtime, Path(image))
    dialogs.close()
    # The clipboard helper owns the PNG independently of this notification.
    subprocess.Popen(["kdialog", "--title", "Subjector", "--passivepopup",
                      "Subject copied. Paste it into an image editor or document.", "4"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return 0


def _integrate(dialogs: Dialogs, paths: AppPaths, action: str) -> None:
    launcher = Path(__file__).resolve().parents[1] / "subjector.sh"
    if action == "remove":
        remove_context_menu(paths)
        message = "The Subjector context-menu action was removed. Open With is unchanged."
    elif action == "unregister":
        remove_open_with(paths)
        message = "The Open With entry was removed. The Dolphin action is unchanged."
    else:
        destination = register(paths, launcher, context_menu=action == "context")
        if action == "register" and shutil.which("update-desktop-database"):
            subprocess.run(["update-desktop-database", str(destination.parent)],
                           capture_output=True, timeout=15, check=False)
        message = f"Installed: {destination}\nIf needed, reopen Dolphin. Default file associations are unchanged."
    dialogs.ask("--msgbox", message)
