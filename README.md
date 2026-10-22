# Subjector

Copy an image's subject, with its background removed, on Linux.
Subjector uses [rembg](https://github.com/danielgatis/rembg) locally and puts a
transparent PNG on the clipboard. Original images stay unchanged.

## AppImage for long-term Bazzite testing

An unsigned x86_64 test AppImage is built at `dist/Subjector-x86_64.AppImage`.
Move it to a permanent location before enabling desktop integration:

```sh
mkdir -p ~/Applications
cp dist/Subjector-x86_64.AppImage ~/Applications/Subjector.AppImage
chmod +x ~/Applications/Subjector.AppImage
~/Applications/Subjector.AppImage
```

The AppImage includes its own Python interpreter and application code. It does
not depend on this repository or on an installed Python. It reuses your existing
Subjector runtime, model, and GPU setup. First-time rembg/model installation still
requires explicit consent and an internet connection.

This artifact targets **your Bazzite/KDE Wayland machine**, not arbitrary Linux
installations. Host `kdialog`, `qdbus`, and `wl-copy` are still required. It is an
unsigned test build, not a fully self-contained or public release.

```sh
~/Applications/Subjector.AppImage --version
~/Applications/Subjector.AppImage doctor
~/Applications/Subjector.AppImage "/path/to/photo.jpg"
~/Applications/Subjector.AppImage integrate                 # Open With
~/Applications/Subjector.AppImage integrate --context-menu  # optional Dolphin action
```

The same registration options are in the GUI. Desktop entries point to the
permanent AppImage path, never its temporary mount. No default associations are
changed. If you move/rename the image, register again from the new location.
Remove either entry by adding `--remove` to its registration command.

For a later build, close Subjector's windows and replace the file at the **same
permanent path**. AppImage updates replace application code only; runtime updates
remain a separate consented action in Subjector. Keep the previous image if you
want to revert application code. Runtime rollback does not roll back the AppImage.
Do not replace the image while an extraction or setup is running.

If FUSE mounting is unavailable, run:

```sh
~/Applications/Subjector.AppImage --appimage-extract-and-run
```

There is no automatic AppImage update service, signing, or AppImageLauncher
requirement. Use the generated `.sha256` file to check a copied artifact.

## Run from the repository (KDE/Wayland)

Alternatively, from this repository, run:

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

For source launches, keep this repository at its registered location. For
AppImage launches, only the registered AppImage path needs to remain stable.
Re-register after moving either launcher.

## Supported platform and limitations

V1 targets **Linux x86_64, KDE Plasma/Dolphin, and Wayland**. The launcher currently
uses host Python 3.11+, `kdialog`, `qdbus`, and `wl-copy`. These are already present
on this Bazzite machine. No manual rembg, pip, CUDA, or model setup is needed.
The test AppImage bundles Python, but still uses the listed KDE/clipboard helpers.
**A fully self-contained cross-distribution launcher is still unfinished.**

- NVIDIA acceleration is enabled only after a real inference profile confirms
  CUDA kernel execution. GPU setup failure installs a separate CPU runtime.
  GPU errors during copying retry on CPU and retain that fallback for later copies.
  AMD, Intel, and undetected GPUs use CPU. Host drivers are never installed or changed.
- The small **U2Netp** model makes first setup quicker. Fine hair, busy backgrounds,
  and small objects can need a stronger model. This is not Apple-quality parity.
- Input is limited to one static JPEG, PNG, or WebP: at most 50 MiB and 25 million
  pixels. Animated images and other formats are rejected.
- Output keeps the oriented image dimensions. There is no automatic subject crop.
- X11, other file managers, and multiple-image operations are not implemented.
- The progress window has a **Cancel** button. Closing it also cancels the
  operation. Workers are terminated and partial installations are not activated.
  A blocked network read can take up to its socket timeout before cancellation.
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

Use **Show runtime / GPU status** to see the installed version, backend, and GPU
fallback reason without starting setup.

If pasting produces nothing, try an image editor rather than a plain-text field.
The Bazzite `/home` → `/var/home` prefix mismatch is fixed. Setup now uses a
single canonical runtime path for both Python and pip. If an earlier attempt
failed with a prefix or script-path error, launch Subjector again and choose
setup; there is no need to delete the verified download cache.

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
Real setup was verified on this Bazzite machine using the normal `/home` path:
Python 3.13.16, rembg 2.0.86, and ONNX Runtime 1.31.0. Both a separate CPU runtime
and CUDA execution on an RTX 3060 passed inference validation. The installed
runtimes used about 692 MiB (CPU) and 3.0 GiB (CUDA).

The complete suite passed 90 tests, including real image decoding and inference.
The actual `.sh` launcher and a generated Open With entry both copied a
1000×667 transparent PNG to the normal Wayland clipboard. CPU rollback, offline
reuse, and restoring the CUDA runtime were verified. GPU-failure recovery was
checked with an injected unavailable device; native-crash retry has regression
coverage. Closing a real KDE progress window cancelled its worker promptly.

These checks do not replace visual paste acceptance in your chosen application,
manual Dolphin menu acceptance, or clean-system portability testing.

## Build the test AppImage

On Linux x86_64 with Python 3.11+, build from this checkout:

```sh
python3 scripts/build_appimage.py
# Reuse the existing verified Python download to save bandwidth:
python3 scripts/build_appimage.py --python-archive ~/.cache/subjector/python-3.13.16.tar.gz
```

Run only one of those commands. The builder refuses to overwrite an existing
output; move it aside or select `--output /another/path/Subjector.AppImage`.
Build inputs are pinned by SHA-256. A replaced upstream asset fails verification,
not silently accepted. The build tool uses extract-and-run, so building does not
require FUSE. No rembg runtime, model, user data, tests, Git metadata, or local
agent/planning files are packaged.

Output: `dist/Subjector-x86_64.AppImage` and its `.sha256` file. Build caches stay
under ignored `build/`. The image includes `BUILD.json` and third-party notices.
See `packaging/appimage/THIRD_PARTY.md` for bundled components and licensing gaps
that still need review before a public release.

## Upstream projects

- [rembg](https://github.com/danielgatis/rembg): background removal, MIT license.
- [python-build-standalone](https://github.com/astral-sh/python-build-standalone):
  private Python distribution with its upstream license notices.
- [U²-Net](https://github.com/xuebinqin/U-2-Net): segmentation model project,
  Apache-2.0 source license. Model weights come from rembg's release assets.

The repository does not vendor these projects. The test AppImage includes a
bootstrap Python distribution. Inference dependencies and models are acquired
after consent. Upstream license terms apply to both bundled and downloaded code.
