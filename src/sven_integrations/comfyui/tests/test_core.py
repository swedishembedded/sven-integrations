"""Tests for the ComfyUI harness core functionality."""

from __future__ import annotations

import json
import unittest.mock as mock
from pathlib import Path


from sven_integrations.comfyui.core.queue import get_progress
from sven_integrations.comfyui.core.workflow import (
    build_img2img_workflow,
    build_txt2img_workflow,
    build_upscale_workflow,
    load_workflow_json,
    save_workflow_json,
    set_workflow_seed,
)
from sven_integrations.comfyui.core import images as images_mod
from sven_integrations.comfyui.core import models as models_mod
from sven_integrations.comfyui.backend import ComfyBackend
from sven_integrations.comfyui.project import (
    ComfyProject,
    ComfyWorkflow,
    NodeConnection,
    WorkflowNode,
)


# ---------------------------------------------------------------------------
# WorkflowNode model
# ---------------------------------------------------------------------------


class TestWorkflowNode:
    def test_defaults(self) -> None:
        node = WorkflowNode(node_id="1", class_type="CLIPTextEncode")
        assert node.title is None
        assert node.inputs == {}
        assert node.outputs == []

    def test_roundtrip(self) -> None:
        node = WorkflowNode(
            node_id="42",
            class_type="KSampler",
            title="My Sampler",
            inputs={"seed": 12345, "steps": 20},
            outputs=["LATENT"],
        )
        assert WorkflowNode.from_dict(node.to_dict()) == node


# ---------------------------------------------------------------------------
# NodeConnection model
# ---------------------------------------------------------------------------


class TestNodeConnection:
    def test_roundtrip(self) -> None:
        conn = NodeConnection(from_node="4", from_slot=0, to_node="3", to_slot=2)
        assert NodeConnection.from_dict(conn.to_dict()) == conn


# ---------------------------------------------------------------------------
# ComfyWorkflow model
# ---------------------------------------------------------------------------


class TestComfyWorkflow:
    def _make_workflow(self) -> ComfyWorkflow:
        wf = ComfyWorkflow(name="test")
        n1 = WorkflowNode(node_id="1", class_type="CheckpointLoaderSimple", outputs=["MODEL"])
        n2 = WorkflowNode(node_id="2", class_type="KSampler", inputs={"model": ""})
        wf.add_node(n1)
        wf.add_node(n2)
        return wf

    def test_add_node(self) -> None:
        wf = ComfyWorkflow()
        node = WorkflowNode(node_id="n1", class_type="SomeNode")
        wf.add_node(node)
        assert "n1" in wf.nodes

    def test_remove_node(self) -> None:
        wf = self._make_workflow()
        wf.connect_nodes("1", 0, "2", 0)
        removed = wf.remove_node("1")
        assert removed is True
        assert "1" not in wf.nodes
        assert len(wf.connections) == 0  # connection removed too

    def test_remove_nonexistent(self) -> None:
        wf = ComfyWorkflow()
        assert wf.remove_node("ghost") is False

    def test_connect_nodes(self) -> None:
        wf = self._make_workflow()
        wf.connect_nodes("1", 0, "2", 0)
        assert len(wf.connections) == 1
        assert wf.connections[0].from_node == "1"

    def test_disconnect_nodes(self) -> None:
        wf = self._make_workflow()
        wf.connect_nodes("1", 0, "2", 0)
        removed = wf.disconnect_nodes("1", 0, "2", 0)
        assert removed is True
        assert len(wf.connections) == 0

    def test_disconnect_nonexistent(self) -> None:
        wf = ComfyWorkflow()
        assert wf.disconnect_nodes("x", 0, "y", 0) is False

    def test_find_node(self) -> None:
        wf = self._make_workflow()
        assert wf.find_node("1") is not None
        assert wf.find_node("999") is None

    def test_validate_empty(self) -> None:
        wf = ComfyWorkflow()
        errors = wf.validate()
        assert any("no nodes" in e.lower() for e in errors)

    def test_validate_bad_connection(self) -> None:
        wf = self._make_workflow()
        wf.connections.append(NodeConnection(from_node="99", from_slot=0, to_node="1", to_slot=0))
        errors = wf.validate()
        assert any("99" in e for e in errors)

    def test_validate_valid(self) -> None:
        wf = self._make_workflow()
        wf.connect_nodes("1", 0, "2", 0)
        errors = wf.validate()
        assert errors == []

    def test_to_api_format(self) -> None:
        wf = build_txt2img_workflow("a cat", steps=5)
        api = wf.to_api_format()
        assert "4" in api  # CheckpointLoaderSimple
        assert "3" in api  # KSampler
        assert api["4"]["class_type"] == "CheckpointLoaderSimple"

    def test_roundtrip(self) -> None:
        wf = self._make_workflow()
        wf.connect_nodes("1", 0, "2", 0)
        wf2 = ComfyWorkflow.from_dict(wf.to_dict())
        assert wf2.name == wf.name
        assert len(wf2.nodes) == 2
        assert len(wf2.connections) == 1


# ---------------------------------------------------------------------------
# ComfyProject CRUD
# ---------------------------------------------------------------------------


class TestComfyProject:
    def test_add_workflow(self) -> None:
        project = ComfyProject()
        wf = ComfyWorkflow(name="first")
        project.add_workflow(wf)
        assert len(project.workflows) == 1
        assert project.active_workflow == "first"

    def test_set_active_workflow(self) -> None:
        project = ComfyProject()
        project.add_workflow(ComfyWorkflow(name="A"))
        project.add_workflow(ComfyWorkflow(name="B"))
        assert project.set_active_workflow("B") is True
        assert project.active_workflow == "B"

    def test_set_active_nonexistent(self) -> None:
        project = ComfyProject()
        assert project.set_active_workflow("Ghost") is False

    def test_get_active_workflow(self) -> None:
        project = ComfyProject()
        wf = ComfyWorkflow(name="active")
        project.add_workflow(wf)
        assert project.get_active_workflow() is wf

    def test_roundtrip(self) -> None:
        project = ComfyProject(name="myproject", server_url="http://localhost:8188")
        project.add_workflow(ComfyWorkflow(name="flow1"))
        p2 = ComfyProject.from_dict(project.to_dict())
        assert p2.name == "myproject"
        assert p2.server_url == "http://localhost:8188"
        assert len(p2.workflows) == 1


# ---------------------------------------------------------------------------
# Workflow builders
# ---------------------------------------------------------------------------


class TestBuildTxt2Img:
    def test_has_required_nodes(self) -> None:
        wf = build_txt2img_workflow("a sunset", steps=10)
        class_types = {n.class_type for n in wf.nodes.values()}
        assert "CheckpointLoaderSimple" in class_types
        assert "KSampler" in class_types
        assert "CLIPTextEncode" in class_types
        assert "VAEDecode" in class_types
        assert "SaveImage" in class_types

    def test_positive_prompt_embedded(self) -> None:
        wf = build_txt2img_workflow("blue sky")
        pos_nodes = [n for n in wf.nodes.values() if n.class_type == "CLIPTextEncode" and n.inputs.get("text") == "blue sky"]
        assert len(pos_nodes) == 1

    def test_custom_seed(self) -> None:
        wf = build_txt2img_workflow("test", seed=42)
        ksampler = next(n for n in wf.nodes.values() if n.class_type == "KSampler")
        assert ksampler.inputs["seed"] == 42

    def test_to_api_format_valid(self) -> None:
        wf = build_txt2img_workflow("prompt", steps=5)
        api = wf.to_api_format()
        assert isinstance(api, dict)
        assert len(api) == len(wf.nodes)


class TestBuildImg2Img:
    def test_has_load_image(self) -> None:
        wf = build_img2img_workflow("painting", image_path="/tmp/img.png")
        class_types = {n.class_type for n in wf.nodes.values()}
        assert "LoadImage" in class_types
        assert "VAEEncode" in class_types

    def test_image_name_in_inputs(self) -> None:
        wf = build_img2img_workflow("art", image_path="/some/path/photo.jpg")
        load_node = next(n for n in wf.nodes.values() if n.class_type == "LoadImage")
        assert load_node.inputs["image"] == "photo.jpg"


class TestBuildUpscale:
    def test_has_upscale_model_loader(self) -> None:
        wf = build_upscale_workflow("/tmp/low_res.png")
        class_types = {n.class_type for n in wf.nodes.values()}
        assert "UpscaleModelLoader" in class_types
        assert "ImageUpscaleWithModel" in class_types


# ---------------------------------------------------------------------------
# set_workflow_seed
# ---------------------------------------------------------------------------


class TestSetWorkflowSeed:
    def test_sets_seed(self) -> None:
        wf = build_txt2img_workflow("test", seed=100)
        wf = set_workflow_seed(wf, 9999)
        ksampler = next(n for n in wf.nodes.values() if n.class_type == "KSampler")
        assert ksampler.inputs["seed"] == 9999


# ---------------------------------------------------------------------------
# Queue progress calculation
# ---------------------------------------------------------------------------


class TestGetProgress:
    def test_success_status(self) -> None:
        history = {"status": {"status_str": "success"}}
        assert get_progress(history) == 1.0

    def test_outputs_present(self) -> None:
        history = {"outputs": {"1": {"images": [{"filename": "out.png"}]}}}
        assert get_progress(history) == 1.0

    def test_empty(self) -> None:
        assert get_progress({}) == 0.0

    def test_execution_success_message(self) -> None:
        history = {"status": {"status_str": "running", "messages": [["execution_success", {}]]}}
        assert get_progress(history) == 1.0


# ---------------------------------------------------------------------------
# Workflow JSON roundtrip
# ---------------------------------------------------------------------------


class TestWorkflowJsonRoundtrip:
    def test_save_and_load(self, tmp_path: Path) -> None:
        wf = build_txt2img_workflow("ocean waves", steps=5, seed=777)
        out = str(tmp_path / "workflow.json")
        save_workflow_json(wf, out)
        loaded = load_workflow_json(out)
        assert loaded.name == wf.name
        assert set(loaded.nodes.keys()) == set(wf.nodes.keys())

    def test_load_api_format(self, tmp_path: Path) -> None:
        """Loading a raw ComfyUI prompt API JSON should produce a valid workflow."""
        api_format = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"},
                "_meta": {"title": "Loader"},
            },
            "3": {
                "class_type": "KSampler",
                "inputs": {"seed": 1, "steps": 20, "model": ["4", 0]},
            },
        }
        fpath = tmp_path / "api.json"
        fpath.write_text(json.dumps(api_format))
        wf = load_workflow_json(str(fpath))
        assert "4" in wf.nodes
        assert "3" in wf.nodes
        assert wf.nodes["4"].title == "Loader"
        assert any(c.from_node == "4" for c in wf.connections)


# ---------------------------------------------------------------------------
# OutputImage dataclass tests
# ---------------------------------------------------------------------------


class TestOutputImage:
    def test_defaults(self) -> None:
        img = images_mod.OutputImage(filename="ComfyUI_00001.png")
        assert img.subfolder == ""
        assert img.image_type == "output"
        assert img.url == ""

    def test_to_dict(self) -> None:
        img = images_mod.OutputImage(
            filename="out.png",
            subfolder="batch1",
            image_type="output",
            url="http://localhost:8188/view?filename=out.png",
        )
        d = img.to_dict()
        assert d["filename"] == "out.png"
        assert d["subfolder"] == "batch1"
        assert "url" in d


# ---------------------------------------------------------------------------
# list_output_images mock test
# ---------------------------------------------------------------------------


def _make_backend_mock(server_url: str = "http://127.0.0.1:8188") -> ComfyBackend:
    be = mock.MagicMock(spec=ComfyBackend)
    be.server_url = server_url
    return be


class TestListOutputImages:
    def test_extracts_images_from_history(self) -> None:
        be = _make_backend_mock()
        be.get_history.return_value = {
            "abc123": {
                "outputs": {
                    "9": {
                        "images": [
                            {"filename": "img_001.png", "subfolder": "", "type": "output"},
                            {"filename": "img_002.png", "subfolder": "", "type": "output"},
                        ]
                    }
                }
            }
        }
        imgs = images_mod.list_output_images(be, "abc123")
        assert len(imgs) == 2
        assert imgs[0].filename == "img_001.png"
        assert imgs[0].image_type == "output"

    def test_url_constructed_correctly(self) -> None:
        be = _make_backend_mock()
        be.get_history.return_value = {
            "pid1": {
                "outputs": {
                    "5": {
                        "images": [
                            {"filename": "out.png", "subfolder": "sub", "type": "output"}
                        ]
                    }
                }
            }
        }
        imgs = images_mod.list_output_images(be, "pid1")
        assert "filename=out.png" in imgs[0].url
        assert "subfolder=sub" in imgs[0].url

    def test_empty_history(self) -> None:
        be = _make_backend_mock()
        be.get_history.return_value = {"noprompt": {"outputs": {}}}
        imgs = images_mod.list_output_images(be, "noprompt")
        assert imgs == []


# ---------------------------------------------------------------------------
# download_prompt_images mock test
# ---------------------------------------------------------------------------


class TestDownloadPromptImages:
    def test_download_creates_files(self, tmp_path: Path) -> None:
        be = _make_backend_mock()
        be.get_history.return_value = {
            "p1": {
                "outputs": {
                    "9": {
                        "images": [
                            {"filename": "img_001.png", "subfolder": "", "type": "output"}
                        ]
                    }
                }
            }
        }

        fake_response = mock.MagicMock()
        fake_response.read.return_value = b"\x89PNG\r\n"
        fake_response.__enter__ = mock.MagicMock(return_value=fake_response)
        fake_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=fake_response):
            result = images_mod.download_prompt_images(be, "p1", str(tmp_path))

        assert len(result["downloaded"]) == 1
        assert result["errors"] == []

    def test_skip_existing_files(self, tmp_path: Path) -> None:
        existing = tmp_path / "img_001.png"
        existing.write_bytes(b"old")
        be = _make_backend_mock()
        be.get_history.return_value = {
            "p2": {
                "outputs": {
                    "9": {"images": [{"filename": "img_001.png", "subfolder": "", "type": "output"}]}
                }
            }
        }
        result = images_mod.download_prompt_images(be, "p2", str(tmp_path), overwrite=False)
        assert len(result["skipped"]) == 1
        assert result["downloaded"] == []


# ---------------------------------------------------------------------------
# list_checkpoints mock test
# ---------------------------------------------------------------------------


class TestListCheckpoints:
    def _make_ckpt_node_info(self) -> dict:
        return {
            "CheckpointLoaderSimple": {
                "input": {
                    "required": {
                        "ckpt_name": [
                            ["v1-5-pruned.safetensors", "sdxl_base.safetensors"],
                            {},
                        ]
                    }
                }
            }
        }

    def test_list_checkpoints(self) -> None:
        be = _make_backend_mock()
        fake_response = mock.MagicMock()
        fake_response.read.return_value = json.dumps(self._make_ckpt_node_info()).encode()
        fake_response.__enter__ = mock.MagicMock(return_value=fake_response)
        fake_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=fake_response):
            ckpts = models_mod.list_checkpoints(be)

        assert "v1-5-pruned.safetensors" in ckpts
        assert "sdxl_base.safetensors" in ckpts

    def test_list_all_node_classes(self) -> None:
        be = _make_backend_mock()
        data = {"KSampler": {}, "CheckpointLoaderSimple": {}, "CLIPTextEncode": {}}
        fake_response = mock.MagicMock()
        fake_response.read.return_value = json.dumps(data).encode()
        fake_response.__enter__ = mock.MagicMock(return_value=fake_response)
        fake_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=fake_response):
            classes = models_mod.list_all_node_classes(be)

        assert "KSampler" in classes
        assert classes == sorted(classes)
