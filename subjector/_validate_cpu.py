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


def create_session(model: Path, backend: str = "cpu", *, profile: bool = False):
    from rembg import new_session
    if backend == "cpu":
        return new_session("u2net_custom", model_path=str(model), providers=["CPUExecutionProvider"])
    import onnxruntime as ort
    from rembg.sessions.u2net_custom import U2netCustomSession
    ort.preload_dlls(cuda=True, cudnn=True, msvc=False, directory="")
    options = ort.SessionOptions()
    options.enable_profiling = profile
    options.profile_file_prefix = str(model.parent / "cuda-validation")
    session = U2netCustomSession("u2net_custom", options, model_path=str(model),
                                providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    if "CUDAExecutionProvider" not in session.inner_session.get_providers():
        raise RuntimeError("CUDA could not initialize; CPU fallback is required.")
    return session


def check_model(model: Path, backend: str = "cpu") -> dict[str, object]:
    if not model.is_file():
        raise ValueError("A local model file is required")
    sys.addaudithook(deny_network)
    from PIL import Image, ImageDraw
    from rembg import remove

    session = create_session(model, backend, profile=backend == "cuda")
    image = Image.new("RGB", (64, 64), "white")
    ImageDraw.Draw(image).rectangle((16, 8, 48, 56), fill="red")
    result = remove(image, session=session)
    cuda_executed = False
    if backend == "cuda":
        profile = Path(session.inner_session.end_profiling())
        try:
            events = json.loads(profile.read_text())
            cuda_executed = any(event.get("args", {}).get("provider") == "CUDAExecutionProvider"
                                for event in events)
        finally:
            profile.unlink(missing_ok=True)
        if not cuda_executed:
            raise RuntimeError("No CUDA kernels ran during validation.")
    output = io.BytesIO()
    result.save(output, format="PNG")
    with model.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    return {
        "schema": 1, "backend": backend, "python": platform.python_version(),
        "cuda_executed": cuda_executed,
        "rembg": importlib.metadata.version("rembg"),
        "onnxruntime": importlib.metadata.version("onnxruntime-gpu" if backend == "cuda" else "onnxruntime"),
        "providers": session.inner_session.get_providers(),
        "output_mode": result.mode, "output_size": list(result.size),
        "png_bytes": len(output.getvalue()), "model_sha256": digest,
    }


if __name__ == "__main__":
    print(json.dumps(check_model(Path(sys.argv[-1]).resolve(strict=True),
                                 "cuda" if "--cuda" in sys.argv else "cpu")))
