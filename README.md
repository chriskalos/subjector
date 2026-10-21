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
baseline for unsupported hardware.

Tests must not download dependencies or models, change the clipboard, or install
desktop integrations.
