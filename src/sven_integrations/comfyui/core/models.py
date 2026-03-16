"""ComfyUI model listing — queries /object_info for available checkpoints, LoRAs, VAEs, etc."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..backend import ComfyBackend, ComfyError


@dataclass
class ModelInfo:
    """Summary of a model available in ComfyUI."""

    filename: str
    model_type: str    # checkpoint | lora | vae | controlnet
    full_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "model_type": self.model_type,
            "full_path": self.full_path,
        }


# ---------------------------------------------------------------------------
# Internal helpers


def _get_node_info(backend: ComfyBackend, node_class: str) -> dict[str, Any]:
    """Fetch the /object_info entry for *node_class*."""
    try:
        url = f"{backend.server_url}/object_info/{node_class}"
        import urllib.request
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            import json
            return json.loads(resp.read())
    except Exception as exc:
        raise ComfyError(f"Cannot fetch node info for {node_class!r}: {exc}") from exc


def _extract_model_list(node_info: dict[str, Any], input_key: str) -> list[str]:
    """Extract the list of model filenames from a node_info dict.

    ComfyUI's /object_info format: {NodeClass: {input: {required: {key: [list, ...]}}}}.
    """
    for _class, spec in node_info.items():
        required = spec.get("input", {}).get("required", {})
        for key, val in required.items():
            if key == input_key and isinstance(val, list) and len(val) >= 1:
                if isinstance(val[0], list):
                    return list(val[0])
    return []


# ---------------------------------------------------------------------------
# Public API


def list_checkpoints(backend: ComfyBackend) -> list[str]:
    """Return all checkpoint model filenames available on the ComfyUI server."""
    info = _get_node_info(backend, "CheckpointLoaderSimple")
    return _extract_model_list(info, "ckpt_name")


def list_loras(backend: ComfyBackend) -> list[str]:
    """Return all LoRA model filenames available on the ComfyUI server."""
    info = _get_node_info(backend, "LoraLoader")
    return _extract_model_list(info, "lora_name")


def list_vaes(backend: ComfyBackend) -> list[str]:
    """Return all VAE model filenames available on the ComfyUI server."""
    info = _get_node_info(backend, "VAELoader")
    return _extract_model_list(info, "vae_name")


def list_controlnets(backend: ComfyBackend) -> list[str]:
    """Return all ControlNet model filenames available on the ComfyUI server."""
    info = _get_node_info(backend, "ControlNetLoader")
    return _extract_model_list(info, "control_net_name")


def get_node_info(backend: ComfyBackend, node_class: str) -> dict[str, Any]:
    """Return the raw /object_info entry for *node_class*."""
    return _get_node_info(backend, node_class)


def list_all_node_classes(backend: ComfyBackend) -> list[str]:
    """Return the names of all node classes registered on the ComfyUI server."""
    try:
        url = f"{backend.server_url}/object_info"
        import urllib.request
        import json
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as resp:
            data: dict[str, Any] = json.loads(resp.read())
        return sorted(data.keys())
    except Exception as exc:
        raise ComfyError(f"Cannot fetch node class list: {exc}") from exc
