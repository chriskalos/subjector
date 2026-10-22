# Subjector

Copy an image's subject, with its background removed, on Linux.
Subjector uses [rembg](https://github.com/danielgatis/rembg) locally and puts a
transparent PNG on the clipboard. Original images stay unchanged.

## Run Subjector v1 (KDE/Wayland)

From this repository, run:

```sh
./subjector.sh
```

1. Select **Choose an image and copy its subject**.
2. Choose a JPEG, PNG, or static WebP photo with a clear foreground subject.
3. On first use, approve the metadata check. Then approve the software downloads.
   In each consent dialog, check the approval box and click **OK**.
4. Wait for **Subject copied**. Initial setup can take several minutes.
5. Paste with **Ctrl+V** into an image editor or a document application that
   accepts images. The background should be transparent.

You can also open a specific image directly:

```sh
./subjector.sh "/absolute/path/to/photo.jpg"
```

After setup, the installed runtime and model work offline. For the quickest first
test, choose **Set up / repair using CPU only** before choosing an image. Automatic
setup detects NVIDIA candidates, attempts CUDA, and falls back to CPU if real GPU
inference cannot be verified.

### Open With and Dolphin

Run `./subjector.sh` again:

- Select **Add Subjector to Open With**. In Dolphin, right-click an image and
  choose **Open With → Subjector**. It does not change the default image viewer.
- Select **Enable Dolphin: Copy subject** to add the optional right-click action.
  The action applies to one selected local image. Check Dolphin's **Actions**
  submenu if it is not at the top level. Reopen Dolphin if needed.
- Select **Disable Dolphin: Copy subject** to remove that action. Use **Remove
  Subjector from Open With** to remove the application entry separately.

Keep this repository in its current location after registration. If you move it,
run the registration actions again to update the launcher path.

## Supported platform and limitations

V1 targets **Linux x86_64, KDE Plasma/Dolphin, and Wayland**. The launcher currently
uses host Python 3.11+, `kdialog`, `qdbus`, and `wl-copy`. These are already present
on this Bazzite machine. No manual rembg, pip, CUDA, or model setup is needed.
**A fully self-contained cross-distribution launcher is still unfinished.**
AppImage packaging remains deferred.

- NVIDIA acceleration is enabled only after a real inference profile confirms
  CUDA kernel execution. GPU setup failure installs a separate CPU runtime.
  GPU errors during copying retry on CPU and retain that fallback for later copies.
  AMD, Intel, and undetected GPUs use CPU. Host drivers are never installed or changed.
- The small **U2Netp** model makes first setup quicker. Fine hair, busy backgrounds,
  and small objects can need a stronger model. This is not Apple-quality parity.
- Input is limited to one static JPEG, PNG, or WebP: at most 50 MiB and 25 million
  pixels. Animated images and other formats are rejected.
- Output keeps the oriented image dimensions. There is no automatic subject crop.
- X11, other file managers, multiple-image operations, and AppImage packaging
  are not implemented.
- Closing the progress window does not cancel an in-progress installation.
  Downloads and subprocesses have timeouts. Wait for completion or an error.
- Closing Subjector does not clear the copied image. The clipboard helper keeps
  it available until something else replaces it or the desktop session ends.

## What setup downloads

Subjector asks before network access and installation. It resolves the latest
stable rembg release from PyPI, then installs it into an application-owned Python
runtime. It does not change system Python or install GPU drivers.

Setup downloads Python 3.13.16 (about 35 MB), U2Netp (about 4.6 MB), rembg,
and the selected backend's dependencies. Allow about 1 GB for CPU, or several GB
for CUDA. The tested CPU installation used 688 MiB plus 39 MiB of cached downloads;
future dependency versions can differ.
Sources are
PyPI, Python-hosted package files, and official GitHub release assets. Python and
model artifacts have pinned SHA-256 checksums. rembg's wheel checksum comes from
PyPI metadata. pip records installed dependencies and artifact provenance.

Images are not uploaded. Inference uses the explicitly selected local model.
Setup activates a runtime only after a local inference check succeeds. Failed
preparation preserves the previous runtime.

Default locations, with XDG overrides respected:

- Runtime and model: `~/.local/share/subjector/`
- Download cache: `~/.cache/subjector/`
- Open With entry: `~/.local/share/applications/subjector.desktop`
- Dolphin action: `~/.local/share/kio/servicemenus/subjector.desktop`

## Terminal commands and troubleshooting

```sh
python3 -m subjector doctor
python3 -m subjector setup --check
python3 -m subjector setup --install
python3 -m subjector setup --install --cpu
python3 -m subjector copy -- "/absolute/path/to/photo.jpg"
python3 -m subjector update
python3 -m subjector repair --cpu
python3 -m subjector rollback
```

`doctor` is offline and read-only. `setup --check` only reads release metadata
after permission. `setup --install` performs the prompted installation, or reuses
a working runtime. The `copy` command requires an active Wayland desktop session.

If pasting produces nothing, try an image editor rather than a plain-text field.
Use **Update or repair the runtime** to install the latest rembg into a fresh
runtime. Use the CPU-only option if GPU support causes trouble. A successful
update retains the previous runtime. **Restore the previous runtime** switches
back without downloads. Failed updates leave the existing selection unchanged.
`doctor` reports the active backend and any saved CPU-fallback reason.

To remove Subjector, disable both desktop integrations in its menu, then remove
its runtime and cache directories listed above. Original images are never stored
or changed there.

## Development and verification

Run the fast tests without downloads or clipboard changes:

```sh
python3 -m unittest discover -s tests -v
```

Real image-worker tests require an explicitly prepared runtime. Set the path
reported as **Active runtime** by `doctor`:

```sh
SUBJECTOR_TEST_RUNTIME="/path/to/subjector/versions/runtime-id" \
  python3 -m unittest discover -s tests -v
```

The real-runtime tests create temporary images and do not write to the clipboard.
Actual setup and CPU inference were verified on this Bazzite machine. CUDA support
validates itself during installation; this development session did not download
the large CUDA runtime or claim a successful GPU run.
A Wayland PNG round-trip was verified through a test-only primary-selection
adapter, without replacing the user's normal clipboard. Final paste behavior in
your chosen application remains an end-user acceptance check.

## Upstream projects

- [rembg](https://github.com/danielgatis/rembg): background removal, MIT license.
- [python-build-standalone](https://github.com/astral-sh/python-build-standalone):
  private Python distribution with its upstream license notices.
- [U²-Net](https://github.com/xuebinqin/U-2-Net): segmentation model project,
  Apache-2.0 source license. Model weights come from rembg's release assets.

Subjector downloads these components after consent rather than committing them
to this repository. Their upstream license terms still apply.
