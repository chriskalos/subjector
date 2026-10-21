"""Executed only by the candidate interpreter, never by the main application."""

import hashlib
import importlib.metadata
import io
import json
import platform
import sys
from pathlib import Path


def deny_network(event: str, arguments: tuple) -> None:
    # This blocks Python socket use, not arbitrary native code. It is not a sandbox.
    if event in {"socket.connect", "socket.getaddrinfo", "socket.bind"}:
        raise RuntimeError("Runtime validation must not access the network.")


def check_model(model: Path) -> dict[str, object]:
    if not model.is_file():
        raise ValueError("A local model file is required")
    sys.addaudithook(deny_network)
    from PIL import Image, ImageDraw
    from rembg import new_session, remove

    # The custom session uses this exact file and does not fetch model weights.
    session = new_session("u2net_custom", model_path=str(model), providers=["CPUExecutionProvider"])
    image = Image.new("RGB", (64, 64), "white")
    ImageDraw.Draw(image).rectangle((16, 8, 48, 56), fill="red")
    result = remove(image, session=session)
    output = io.BytesIO()
    result.save(output, format="PNG")
    with model.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    return {
        "schema": 1, "backend": "cpu", "python": platform.python_version(),
        "rembg": importlib.metadata.version("rembg"),
        "onnxruntime": importlib.metadata.version("onnxruntime"),
        "providers": session.inner_session.get_providers(),
        "output_mode": result.mode, "output_size": list(result.size),
        "png_bytes": len(output.getvalue()), "model_sha256": digest,
    }


if __name__ == "__main__":
    print(json.dumps(check_model(Path(sys.argv[1]).resolve(strict=True))))
