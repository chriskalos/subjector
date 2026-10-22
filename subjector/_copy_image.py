"""Single-image worker executed with the private runtime, not host Python."""

import json
import os
import stat
import sys
import warnings
from pathlib import Path

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_PIXELS = 25_000_000


def cutout(source: Path, model: Path, destination: Path) -> dict[str, object]:
    info = source.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
        raise ValueError("Choose a regular image file smaller than 50 MiB.")
    from PIL import Image, ImageChops, ImageOps

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    warnings.simplefilter("error", Image.DecompressionBombWarning)
    with Image.open(source) as original:
        if original.format not in {"PNG", "JPEG", "WEBP"}:
            raise ValueError("Choose a PNG, JPEG, or static WebP image.")
        if getattr(original, "n_frames", 1) != 1:
            raise ValueError("Animated images are not supported.")
        if original.width * original.height > MAX_PIXELS:
            raise ValueError("Choose an image with at most 25 million pixels.")
        image = ImageOps.exif_transpose(original).convert("RGBA")
    # Explicitly import our own helper despite -I excluding the script directory.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _validate_cpu import create_session, deny_network
    sys.addaudithook(deny_network)
    from rembg import remove

    backend = os.environ.get("SUBJECTOR_BACKEND", "cpu")
    try:
        session = create_session(model, backend)
        result = remove(image.convert("RGB"), session=session).convert("RGBA")
    except Exception as error:
        if backend != "cuda":
            raise
        (model.parent / "cpu-fallback").write_text(str(error)[:1000])
        session = create_session(model, "cpu")
        result = remove(image.convert("RGB"), session=session).convert("RGBA")
    result.putalpha(ImageChops.multiply(result.getchannel("A"), image.getchannel("A")))
    result.info.clear()
    with destination.open("xb") as output:
        result.save(output, format="PNG")
    return {"size": list(result.size), "alpha": list(result.getchannel("A").getextrema())}


if __name__ == "__main__":
    try:
        source, model, destination = (Path(argument).absolute() for argument in sys.argv[1:])
        print(json.dumps(cutout(source, model, destination)))
    except Exception as error:
        print(json.dumps({"error": str(error)}))
        raise SystemExit(1)
