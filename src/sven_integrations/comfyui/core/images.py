"""ComfyUI output image listing and downloading."""

from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from ..backend import ComfyBackend, ComfyError


@dataclass
class OutputImage:
    """Represents a single image produced by a ComfyUI prompt."""

    filename: str
    subfolder: str = ""
    image_type: str = "output"    # output | temp | input
    url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "subfolder": self.subfolder,
            "image_type": self.image_type,
            "url": self.url,
        }


# ---------------------------------------------------------------------------
# Helpers


def _build_view_url(
    backend: ComfyBackend,
    filename: str,
    subfolder: str = "",
    image_type: str = "output",
) -> str:
    params = urllib.parse.urlencode({
        "filename": filename,
        "subfolder": subfolder,
        "type": image_type,
    })
    return f"{backend.server_url}/view?{params}"


# ---------------------------------------------------------------------------
# Public API


def list_output_images(backend: ComfyBackend, prompt_id: str) -> list[OutputImage]:
    """Return all output images produced by the completed prompt *prompt_id*.

    Queries ``GET /history/{prompt_id}`` and extracts image entries.
    """
    try:
        history = backend.get_history(prompt_id)
    except ComfyError as exc:
        raise ComfyError(f"Cannot fetch history for prompt {prompt_id!r}: {exc}") from exc

    images: list[OutputImage] = []
    prompt_data = history.get(prompt_id, history)
    outputs = prompt_data.get("outputs", {})

    for node_outputs in outputs.values():
        for img in node_outputs.get("images", []):
            fname = img.get("filename", "")
            subfolder = img.get("subfolder", "")
            itype = img.get("type", "output")
            if fname:
                url = _build_view_url(backend, fname, subfolder, itype)
                images.append(OutputImage(
                    filename=fname,
                    subfolder=subfolder,
                    image_type=itype,
                    url=url,
                ))
    return images


def download_image(
    backend: ComfyBackend,
    filename: str,
    output_path: str,
    subfolder: str = "",
    image_type: str = "output",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Download a single image from the ComfyUI server.

    Returns a status dict with ``ok``, ``path``, and ``skipped`` keys.
    """
    if os.path.exists(output_path) and not overwrite:
        return {"ok": True, "path": output_path, "skipped": True}

    url = _build_view_url(backend, filename, subfolder, image_type)
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as fh:
            fh.write(data)
        return {"ok": True, "path": output_path, "skipped": False}
    except (urllib.error.URLError, OSError) as exc:
        return {"ok": False, "path": output_path, "error": str(exc), "skipped": False}


def download_prompt_images(
    backend: ComfyBackend,
    prompt_id: str,
    output_dir: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Download all output images from a completed prompt.

    Returns a dict with ``downloaded``, ``skipped``, and ``errors`` lists.
    """
    images = list_output_images(backend, prompt_id)
    downloaded: list[str] = []
    skipped: list[str] = []
    errors: list[dict[str, Any]] = []

    os.makedirs(output_dir, exist_ok=True)

    for img in images:
        dest = os.path.join(output_dir, img.filename)
        result = download_image(
            backend,
            filename=img.filename,
            output_path=dest,
            subfolder=img.subfolder,
            image_type=img.image_type,
            overwrite=overwrite,
        )
        if result["ok"]:
            if result.get("skipped"):
                skipped.append(dest)
            else:
                downloaded.append(dest)
        else:
            errors.append({"filename": img.filename, "error": result.get("error")})

    return {
        "downloaded": downloaded,
        "skipped": skipped,
        "errors": errors,
        "total": len(images),
    }
