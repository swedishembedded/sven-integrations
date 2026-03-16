"""ComfyUI workflow helper functions."""

from __future__ import annotations

import json
import random
from pathlib import Path

from ..project import ComfyWorkflow, NodeConnection, WorkflowNode


def load_workflow_json(path: str) -> ComfyWorkflow:
    """Load a ComfyWorkflow from a JSON file.

    Accepts both the internal dict format (with ``workflow_id`` key) and
    raw ComfyUI prompt API format (node_id keys at the top level).
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "workflow_id" in data or "nodes" in data:
        return ComfyWorkflow.from_dict(data)
    # Raw ComfyUI prompt API format: convert to internal representation
    workflow = ComfyWorkflow(name=Path(path).stem)
    for node_id, node_data in data.items():
        node = WorkflowNode(
            node_id=str(node_id),
            class_type=node_data.get("class_type", "Unknown"),
            title=node_data.get("_meta", {}).get("title"),
            inputs={
                k: v
                for k, v in node_data.get("inputs", {}).items()
                if not isinstance(v, list)
            },
        )
        workflow.add_node(node)
        # Extract wire connections ([from_node, from_slot] values)
        for slot_idx, (input_key, val) in enumerate(node_data.get("inputs", {}).items()):
            if isinstance(val, list) and len(val) == 2:
                from_node, from_slot = str(val[0]), int(val[1])
                workflow.connections.append(
                    NodeConnection(
                        from_node=from_node,
                        from_slot=from_slot,
                        to_node=str(node_id),
                        to_slot=slot_idx,
                    )
                )
    return workflow


def save_workflow_json(workflow: ComfyWorkflow, path: str) -> None:
    """Save a ComfyWorkflow to a JSON file in internal format."""
    Path(path).write_text(
        json.dumps(workflow.to_dict(), indent=2, default=str), encoding="utf-8"
    )


def build_txt2img_workflow(
    positive_prompt: str,
    negative_prompt: str = "",
    model: str = "v1-5-pruned-emaonly.safetensors",
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg: float = 7.0,
    sampler: str = "euler",
    seed: int | None = None,
) -> ComfyWorkflow:
    """Build a standard text-to-image ComfyUI workflow."""
    wf = ComfyWorkflow(name="txt2img")
    actual_seed = seed if seed is not None else random.randint(0, 2**32 - 1)

    # Node IDs matching standard ComfyUI numbering
    checkpoint_loader = WorkflowNode(
        node_id="4",
        class_type="CheckpointLoaderSimple",
        title="Load Checkpoint",
        inputs={"ckpt_name": model},
        outputs=["MODEL", "CLIP", "VAE"],
    )
    positive_enc = WorkflowNode(
        node_id="6",
        class_type="CLIPTextEncode",
        title="Positive Prompt",
        inputs={"text": positive_prompt, "clip": ["4", 1]},
        outputs=["CONDITIONING"],
    )
    negative_enc = WorkflowNode(
        node_id="7",
        class_type="CLIPTextEncode",
        title="Negative Prompt",
        inputs={"text": negative_prompt, "clip": ["4", 1]},
        outputs=["CONDITIONING"],
    )
    empty_latent = WorkflowNode(
        node_id="5",
        class_type="EmptyLatentImage",
        title="Empty Latent",
        inputs={"width": width, "height": height, "batch_size": 1},
        outputs=["LATENT"],
    )
    ksampler = WorkflowNode(
        node_id="3",
        class_type="KSampler",
        title="KSampler",
        inputs={
            "seed": actual_seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
        },
        outputs=["LATENT"],
    )
    vae_decode = WorkflowNode(
        node_id="8",
        class_type="VAEDecode",
        title="VAE Decode",
        inputs={"samples": ["3", 0], "vae": ["4", 2]},
        outputs=["IMAGE"],
    )
    save_image = WorkflowNode(
        node_id="9",
        class_type="SaveImage",
        title="Save Image",
        inputs={"images": ["8", 0], "filename_prefix": "txt2img"},
        outputs=[],
    )

    for node in [checkpoint_loader, positive_enc, negative_enc, empty_latent, ksampler, vae_decode, save_image]:
        wf.add_node(node)

    return wf


def build_img2img_workflow(
    positive_prompt: str,
    negative_prompt: str = "",
    image_path: str = "",
    model: str = "v1-5-pruned-emaonly.safetensors",
    denoise: float = 0.75,
    steps: int = 20,
    cfg: float = 7.0,
    sampler: str = "euler",
    seed: int | None = None,
) -> ComfyWorkflow:
    """Build a standard image-to-image ComfyUI workflow."""
    wf = ComfyWorkflow(name="img2img")
    actual_seed = seed if seed is not None else random.randint(0, 2**32 - 1)
    image_name = Path(image_path).name if image_path else "input.png"

    checkpoint_loader = WorkflowNode(
        node_id="4",
        class_type="CheckpointLoaderSimple",
        title="Load Checkpoint",
        inputs={"ckpt_name": model},
        outputs=["MODEL", "CLIP", "VAE"],
    )
    load_image = WorkflowNode(
        node_id="10",
        class_type="LoadImage",
        title="Load Image",
        inputs={"image": image_name, "upload": "image"},
        outputs=["IMAGE", "MASK"],
    )
    vae_encode = WorkflowNode(
        node_id="11",
        class_type="VAEEncode",
        title="VAE Encode",
        inputs={"pixels": ["10", 0], "vae": ["4", 2]},
        outputs=["LATENT"],
    )
    positive_enc = WorkflowNode(
        node_id="6",
        class_type="CLIPTextEncode",
        title="Positive Prompt",
        inputs={"text": positive_prompt, "clip": ["4", 1]},
        outputs=["CONDITIONING"],
    )
    negative_enc = WorkflowNode(
        node_id="7",
        class_type="CLIPTextEncode",
        title="Negative Prompt",
        inputs={"text": negative_prompt, "clip": ["4", 1]},
        outputs=["CONDITIONING"],
    )
    ksampler = WorkflowNode(
        node_id="3",
        class_type="KSampler",
        title="KSampler",
        inputs={
            "seed": actual_seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": "normal",
            "denoise": denoise,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["11", 0],
        },
        outputs=["LATENT"],
    )
    vae_decode = WorkflowNode(
        node_id="8",
        class_type="VAEDecode",
        title="VAE Decode",
        inputs={"samples": ["3", 0], "vae": ["4", 2]},
        outputs=["IMAGE"],
    )
    save_image = WorkflowNode(
        node_id="9",
        class_type="SaveImage",
        title="Save Image",
        inputs={"images": ["8", 0], "filename_prefix": "img2img"},
        outputs=[],
    )

    for node in [checkpoint_loader, load_image, vae_encode, positive_enc, negative_enc, ksampler, vae_decode, save_image]:
        wf.add_node(node)

    return wf


def build_upscale_workflow(
    image_path: str,
    model: str = "RealESRGAN_x4plus.pth",
    scale_factor: float = 4.0,
) -> ComfyWorkflow:
    """Build a simple upscale workflow using an upscale model node."""
    wf = ComfyWorkflow(name="upscale")
    image_name = Path(image_path).name if image_path else "input.png"

    load_image = WorkflowNode(
        node_id="1",
        class_type="LoadImage",
        title="Load Image",
        inputs={"image": image_name, "upload": "image"},
        outputs=["IMAGE", "MASK"],
    )
    load_upscale_model = WorkflowNode(
        node_id="2",
        class_type="UpscaleModelLoader",
        title="Load Upscale Model",
        inputs={"model_name": model},
        outputs=["UPSCALE_MODEL"],
    )
    upscale_node = WorkflowNode(
        node_id="3",
        class_type="ImageUpscaleWithModel",
        title="Upscale Image",
        inputs={"upscale_model": ["2", 0], "image": ["1", 0]},
        outputs=["IMAGE"],
    )
    save_image = WorkflowNode(
        node_id="4",
        class_type="SaveImage",
        title="Save Image",
        inputs={"images": ["3", 0], "filename_prefix": "upscale"},
        outputs=[],
    )

    for node in [load_image, load_upscale_model, upscale_node, save_image]:
        wf.add_node(node)

    return wf


def set_workflow_seed(workflow: ComfyWorkflow, seed: int) -> ComfyWorkflow:
    """Return a copy of the workflow with all KSampler seeds set to *seed*."""
    for node in workflow.nodes.values():
        if node.class_type in ("KSampler", "KSamplerAdvanced") and "seed" in node.inputs:
            node.inputs["seed"] = seed
    return workflow
