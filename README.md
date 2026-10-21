# Subjector

Subjector is a Linux application in development. Its goal is to remove an image's
background with [rembg](https://github.com/danielgatis/rembg) and copy the subject
as a transparent image.

The initial desktop target is KDE Plasma with Dolphin on Wayland. Planned
features include Open With integration, an optional “Copy subject” menu action,
and automatic dependency downloads after user consent.

**Image extraction, dependency setup, and desktop integration are not available
yet.** No application package is available.

## Development

The initial code uses the Python standard library. Run commands from the
repository root with Python 3.11 or newer.

```sh
python3 -m subjector doctor
python3 -m unittest discover -s tests -v
```

`doctor` reports application storage paths, desktop/session information, and
NVIDIA hardware candidates. It does not download or install anything. A detected
GPU is not proof that CUDA inference works. CPU fallback remains the planned
baseline for unsupported hardware. Diagnostics also inspect the active runtime
record without executing it. Damaged runtime records produce a nonzero exit code.

## Setup preview

```sh
python3 -m subjector setup --check
```

This developer command asks permission before it contacts PyPI. Press Enter or
answer `n` to cancel without network access. After approval, it reports the latest
stable rembg release, its declared Python requirement, and the rembg wheel size.
It does not download packages, install software, or verify runtime compatibility.
The reported size excludes dependencies and model weights.

Package downloads use HTTPS with an explicit source list, response limits, and
SHA-256 verification before an artifact replaces an existing file. This internal
support is not yet connected to a runtime installer.

Runtime staging also rejects unsafe tar paths, special files, escaping or cyclic
links, and excessive archive expansion. Installation transactions use a per-user
lock and activate a candidate only after validation succeeds. Failed preparation
or validation preserves the previous runtime. A late interruption after activation
keeps the selected runtime intact.

The internal CPU provisioner accepts a Python archive and model with trusted
SHA-256 digests. It installs the verified rembg wheel and CPU dependencies only
inside the private interpreter. Activation requires an isolated inference worker
to produce transparent PNG data using the supplied local model.

These components currently use synthetic runtimes and mocked package processes
in tests. Real runtime installation and inference have not been verified. The
provisioner is not yet exposed through a launcher or command-line install option.

Tests use synthetic metadata and mocked HTTP responses. They must not download
dependencies or models, change the clipboard, or install desktop integrations.
