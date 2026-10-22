# Components in this test AppImage

This is an unsigned, local KDE/Wayland test artifact, not a completed public release.

## Bundled bootstrap Python

Python 3.13.16 comes from the official python-build-standalone distribution:
https://github.com/astral-sh/python-build-standalone/releases/tag/20261020

The distribution includes Python, pip, vendored pip dependencies, and linked
runtime libraries. Its included Python and pip notices remain under
`usr/python/lib/python3.13/LICENSE.txt` and the pip package's `licenses/` folders.
The original distribution URL and SHA-256 are recorded in the build script and
BUILD.json. Do not remove upstream license notices when modifying the image.

Python licensing: https://docs.python.org/3/license.html
Distribution licensing details: https://gregoryszorc.com/docs/python-build-standalone/main/running.html#licensing

## AppImage runtime and build tool

The image embeds the AppImage type-2 runtime, MIT license:
https://github.com/AppImage/type2-runtime

The upstream notice is included as `APPIMAGE_RUNTIME_LICENSE.txt`. It also lists
licenses for libraries statically linked into that runtime.

The image is generated with appimagetool 1.9.1. The tool itself is a build input,
not a bundled application dependency:
https://github.com/AppImage/appimagetool/tree/1.9.1

Pinned upstream SHA-256 values are recorded in BUILD.json. Checksums are integrity
checks, not signing or an independent source-code audit.

## Not bundled

rembg, ONNX Runtime, model weights, and NVIDIA userspace libraries are downloaded
only after the application's consent workflow. Their notices and installed-package
metadata stay in the external private runtime. Kernel GPU drivers are not installed.

This test image uses the Bazzite host's KDE dialog/D-Bus and Wayland clipboard
helpers. Those host tools are not redistributed in this artifact.

A complete third-party/license and source-availability review is still required
before distributing a public release. No license for Subjector itself is selected
by this build script.
