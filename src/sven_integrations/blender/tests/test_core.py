"""pytest tests for the Blender harness.

Tests cover:
- BlenderProject / SceneObject data model and serialisation
- BlenderSession persistence via tmp_path
- Object / scene / material / render script generation
- BlenderBackend.build_python_expr logic

No real Blender binary is required.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sven_integrations.blender.project import BlenderProject, SceneObject
from sven_integrations.blender.session import BlenderSession
from sven_integrations.blender.backend import BlenderBackend, BlenderError
from sven_integrations.blender.core import scene as scene_ops
from sven_integrations.blender.core import objects as obj_ops
from sven_integrations.blender.core import materials as mat_ops
from sven_integrations.blender.core import render as render_ops
from sven_integrations.blender.core import animation as anim_ops
from sven_integrations.blender.core import lighting as light_ops
from sven_integrations.blender.core import modifiers as mod_ops


# ---------------------------------------------------------------------------
# Fixtures


@pytest.fixture()
def sample_object() -> SceneObject:
    return SceneObject(
        name="Cube",
        type="MESH",
        location=(1.0, 2.0, 3.0),
        rotation=(0.0, 0.0, 0.0),
        scale=(1.0, 1.0, 1.0),
        material="Metal",
    )


@pytest.fixture()
def blank_project() -> BlenderProject:
    return BlenderProject(scene_name="TestScene", frame_start=1, frame_end=100, fps=30)


@pytest.fixture()
def blender_session(tmp_path: Path) -> BlenderSession:
    os.environ["SVEN_INTEGRATIONS_STATE_DIR"] = str(tmp_path)
    sess = BlenderSession("test-blender")
    yield sess
    os.environ.pop("SVEN_INTEGRATIONS_STATE_DIR", None)


# ---------------------------------------------------------------------------
# SceneObject tests


class TestSceneObject:
    def test_defaults(self) -> None:
        obj = SceneObject(name="Lamp")
        assert obj.type == "MESH"
        assert obj.location == (0.0, 0.0, 0.0)
        assert obj.scale == (1.0, 1.0, 1.0)
        assert obj.material is None

    def test_round_trip(self, sample_object: SceneObject) -> None:
        restored = SceneObject.from_dict(sample_object.to_dict())
        assert restored.name == "Cube"
        assert restored.location == (1.0, 2.0, 3.0)
        assert restored.material == "Metal"

    def test_from_dict_partial(self) -> None:
        obj = SceneObject.from_dict({"name": "Sphere"})
        assert obj.type == "MESH"
        assert obj.location == (0.0, 0.0, 0.0)

    def test_to_dict_contains_all_fields(self, sample_object: SceneObject) -> None:
        d = sample_object.to_dict()
        assert set(d.keys()) == {"name", "type", "location", "rotation", "scale", "material"}


# ---------------------------------------------------------------------------
# BlenderProject tests


class TestBlenderProject:
    def test_initial_state(self, blank_project: BlenderProject) -> None:
        assert blank_project.scene_name == "TestScene"
        assert blank_project.frame_end == 100
        assert blank_project.fps == 30
        assert blank_project.objects == []
        assert blank_project.blend_file is None

    def test_add_object(self, blank_project: BlenderProject, sample_object: SceneObject) -> None:
        blank_project.add_object(sample_object)
        assert len(blank_project.objects) == 1

    def test_remove_object_found(self, blank_project: BlenderProject, sample_object: SceneObject) -> None:
        blank_project.add_object(sample_object)
        removed = blank_project.remove_object("Cube")
        assert removed is True
        assert blank_project.objects == []

    def test_remove_object_missing(self, blank_project: BlenderProject) -> None:
        removed = blank_project.remove_object("Ghost")
        assert removed is False

    def test_find_object(self, blank_project: BlenderProject, sample_object: SceneObject) -> None:
        blank_project.add_object(sample_object)
        found = blank_project.find_object("Cube")
        assert found is sample_object
        assert blank_project.find_object("Missing") is None

    def test_round_trip(self, blank_project: BlenderProject, sample_object: SceneObject) -> None:
        blank_project.add_object(sample_object)
        restored = BlenderProject.from_dict(blank_project.to_dict())
        assert restored.scene_name == "TestScene"
        assert restored.fps == 30
        assert len(restored.objects) == 1
        assert restored.objects[0].name == "Cube"

    def test_from_dict_defaults(self) -> None:
        proj = BlenderProject.from_dict({})
        assert proj.scene_name == "Scene"
        assert proj.fps == 24
        assert proj.frame_start == 1


# ---------------------------------------------------------------------------
# BlenderSession tests


class TestBlenderSession:
    def test_project_none_initially(self, blender_session: BlenderSession) -> None:
        assert blender_session.project is None

    def test_new_scene(self, blender_session: BlenderSession) -> None:
        proj = blender_session.new_scene("MyScene", 1, 120, 25)
        assert proj.scene_name == "MyScene"
        assert proj.fps == 25

    def test_set_blend_file(self, blender_session: BlenderSession) -> None:
        blender_session.set_blend_file("/home/user/work.blend")
        assert blender_session.project is not None
        assert blender_session.project.blend_file == "/home/user/work.blend"

    def test_save_and_reload(self, blender_session: BlenderSession) -> None:
        blender_session.new_scene("Persisted", fps=60)
        blender_session.save()
        fresh = BlenderSession("test-blender")
        fresh.load()
        assert fresh.project is not None
        assert fresh.project.scene_name == "Persisted"
        assert fresh.project.fps == 60

    def test_close(self, blender_session: BlenderSession) -> None:
        blender_session.new_scene()
        blender_session.close()
        assert blender_session.project is None

    def test_list_sessions(self, tmp_path: Path) -> None:
        os.environ["SVEN_INTEGRATIONS_STATE_DIR"] = str(tmp_path)
        for name in ("alpha", "beta"):
            s = BlenderSession(name)
            s.save()
        assert set(BlenderSession.list_sessions()) == {"alpha", "beta"}
        os.environ.pop("SVEN_INTEGRATIONS_STATE_DIR", None)


# ---------------------------------------------------------------------------
# BlenderBackend tests


class TestBlenderBackend:
    def test_build_python_expr_single(self) -> None:
        expr = BlenderBackend.build_python_expr(["import bpy"])
        assert expr == "import bpy"

    def test_build_python_expr_multiple(self) -> None:
        stmts = ["import bpy", "bpy.ops.mesh.primitive_cube_add()", "print('done')"]
        expr = BlenderBackend.build_python_expr(stmts)
        assert expr.count("; ") == 2
        assert "import bpy" in expr
        assert "print('done')" in expr

    def test_run_blender_raises_on_nonzero(self) -> None:
        backend = BlenderBackend()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Fatal error")
            with pytest.raises(BlenderError, match="Blender exited 1"):
                backend.run_blender("import bpy")

    def test_run_blender_returns_stdout(self) -> None:
        backend = BlenderBackend()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="render ok\n", stderr="")
            result = backend.run_blender("import bpy; print('render ok')")
            assert result == "render ok\n"

    def test_render_includes_filepath(self) -> None:
        backend = BlenderBackend()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            backend.render("/tmp/out.png", frame=1)
            call_args = mock_run.call_args[0][0]
            assert "--python-expr" in call_args
            expr = call_args[call_args.index("--python-expr") + 1]
            assert "/tmp/out.png" in expr
            assert "frame_set(1)" in expr


# ---------------------------------------------------------------------------
# Scene op tests


class TestSceneOps:
    def test_set_frame_range(self) -> None:
        result = scene_ops.set_frame_range(1, 240)
        assert result["frame_start"] == 1
        assert result["frame_end"] == 240
        stmts = "\n".join(result["statements"])
        assert "frame_start = 1" in stmts
        assert "frame_end = 240" in stmts

    def test_set_fps(self) -> None:
        result = scene_ops.set_fps(25)
        stmts = "\n".join(result["statements"])
        assert "fps = 25" in stmts

    def test_get_scene_info(self) -> None:
        result = scene_ops.get_scene_info()
        stmts = "\n".join(result["statements"])
        assert "json.dumps" in stmts

    def test_set_active_camera(self) -> None:
        result = scene_ops.set_active_camera("MainCam")
        stmts = "\n".join(result["statements"])
        assert "MainCam" in stmts

    def test_list_objects(self) -> None:
        result = scene_ops.list_objects()
        stmts = "\n".join(result["statements"])
        assert "json.dumps" in stmts


# ---------------------------------------------------------------------------
# Object op tests


class TestObjectOps:
    def test_add_mesh_cube(self) -> None:
        result = obj_ops.add_mesh("CUBE", (1, 2, 3))
        stmts = "\n".join(result["statements"])
        assert "primitive_cube_add" in stmts
        assert "(1, 2, 3)" in stmts

    def test_add_mesh_invalid_type(self) -> None:
        with pytest.raises(ValueError, match="Unknown mesh type"):
            obj_ops.add_mesh("TEAPOT")

    def test_add_light(self) -> None:
        result = obj_ops.add_light("POINT", (0, 0, 5), energy=800)
        stmts = "\n".join(result["statements"])
        assert "POINT" in stmts
        assert "800" in stmts

    def test_add_light_invalid_type(self) -> None:
        with pytest.raises(ValueError, match="Unknown light type"):
            obj_ops.add_light("LASER")

    def test_delete_object(self) -> None:
        result = obj_ops.delete_object("Suzanne")
        stmts = "\n".join(result["statements"])
        assert "Suzanne" in stmts
        assert "remove" in stmts

    def test_duplicate_object(self) -> None:
        result = obj_ops.duplicate_object("Cube", "CopyCube")
        stmts = "\n".join(result["statements"])
        assert "CopyCube" in stmts

    def test_set_parent(self) -> None:
        result = obj_ops.set_parent("Child", "Parent")
        stmts = "\n".join(result["statements"])
        assert "child_obj.parent" in stmts


# ---------------------------------------------------------------------------
# Material op tests


class TestMaterialOps:
    def test_create_material(self) -> None:
        result = mat_ops.create_material("Steel", (0.5, 0.5, 0.5, 1.0))
        stmts = "\n".join(result["statements"])
        assert "Steel" in stmts
        assert "Principled BSDF" in stmts

    def test_assign_material(self) -> None:
        result = mat_ops.assign_material("Sphere", "Steel")
        stmts = "\n".join(result["statements"])
        assert "Sphere" in stmts
        assert "Steel" in stmts

    def test_set_metallic(self) -> None:
        result = mat_ops.set_metallic("Steel", 0.9)
        stmts = "\n".join(result["statements"])
        assert "Metallic" in stmts
        assert "0.9" in stmts

    def test_set_roughness(self) -> None:
        result = mat_ops.set_roughness("Steel", 0.1)
        stmts = "\n".join(result["statements"])
        assert "Roughness" in stmts

    def test_list_materials(self) -> None:
        result = mat_ops.list_materials()
        stmts = "\n".join(result["statements"])
        assert "json.dumps" in stmts


# ---------------------------------------------------------------------------
# Render op tests


class TestRenderOps:
    def test_set_render_engine_cycles(self) -> None:
        result = render_ops.set_render_engine("CYCLES")
        assert result["engine"] == "CYCLES"

    def test_set_render_engine_eevee_alias(self) -> None:
        result = render_ops.set_render_engine("EEVEE")
        assert result["engine"] == "BLENDER_EEVEE"

    def test_set_render_engine_invalid(self) -> None:
        with pytest.raises(ValueError, match="Unknown engine"):
            render_ops.set_render_engine("OCTANE")

    def test_set_output_resolution(self) -> None:
        result = render_ops.set_output_resolution(1920, 1080, 50)
        stmts = "\n".join(result["statements"])
        assert "1920" in stmts
        assert "50" in stmts

    def test_set_output_format_png(self) -> None:
        result = render_ops.set_output_format("PNG")
        assert result["format"] == "PNG"

    def test_set_output_format_mp4_alias(self) -> None:
        result = render_ops.set_output_format("MP4")
        assert result["format"] == "FFMPEG"

    def test_set_output_format_invalid(self) -> None:
        with pytest.raises(ValueError):
            render_ops.set_output_format("GIF")

    def test_set_samples(self) -> None:
        result = render_ops.set_samples(256)
        stmts = "\n".join(result["statements"])
        assert "256" in stmts

    def test_enable_denoising_true(self) -> None:
        result = render_ops.enable_denoising(True)
        stmts = "\n".join(result["statements"])
        assert "True" in stmts

    def test_set_output_path(self) -> None:
        result = render_ops.set_output_path("/renders/frame_####")
        stmts = "\n".join(result["statements"])
        assert "/renders/frame_####" in stmts


# ---------------------------------------------------------------------------
# Animation op tests


class TestAnimationOps:
    def _proj(self) -> BlenderProject:
        return BlenderProject(scene_name="AnimTest")

    def test_add_keyframe_new(self) -> None:
        proj = self._proj()
        result = anim_ops.add_keyframe(proj, 0, 10, "location", [1.0, 0.0, 0.0])
        assert result["action"] == "add_keyframe"
        assert result["updated"] is False
        assert result["frame"] == 10
        assert result["prop"] == "location"
        assert len(proj.data["keyframes"]) == 1

    def test_add_keyframe_updates_existing(self) -> None:
        proj = self._proj()
        anim_ops.add_keyframe(proj, 0, 10, "location", [1.0, 0.0, 0.0])
        result = anim_ops.add_keyframe(proj, 0, 10, "location", [2.0, 0.0, 0.0])
        assert result["updated"] is True
        assert len(proj.data["keyframes"]) == 1
        assert proj.data["keyframes"][0]["value"] == [2.0, 0.0, 0.0]

    def test_add_multiple_keyframes_different_frames(self) -> None:
        proj = self._proj()
        anim_ops.add_keyframe(proj, 0, 1, "location", [0.0, 0.0, 0.0])
        anim_ops.add_keyframe(proj, 0, 50, "location", [5.0, 0.0, 0.0])
        assert len(proj.data["keyframes"]) == 2

    def test_remove_keyframe_by_prop(self) -> None:
        proj = self._proj()
        anim_ops.add_keyframe(proj, 0, 10, "location", [1.0, 0.0, 0.0])
        anim_ops.add_keyframe(proj, 0, 10, "rotation_euler", [0.0, 0.0, 1.57])
        result = anim_ops.remove_keyframe(proj, 0, 10, prop="location")
        assert result["removed_count"] == 1
        assert len(proj.data["keyframes"]) == 1
        assert proj.data["keyframes"][0]["prop"] == "rotation_euler"

    def test_remove_keyframe_all_at_frame(self) -> None:
        proj = self._proj()
        anim_ops.add_keyframe(proj, 0, 10, "location", [1.0, 0.0, 0.0])
        anim_ops.add_keyframe(proj, 0, 10, "rotation_euler", [0.0, 0.0, 1.57])
        result = anim_ops.remove_keyframe(proj, 0, 10)
        assert result["removed_count"] == 2
        assert proj.data["keyframes"] == []

    def test_remove_keyframe_nonexistent(self) -> None:
        proj = self._proj()
        result = anim_ops.remove_keyframe(proj, 0, 99)
        assert result["removed_count"] == 0

    def test_list_keyframes_all(self) -> None:
        proj = self._proj()
        anim_ops.add_keyframe(proj, 0, 1, "location", [0.0, 0.0, 0.0])
        anim_ops.add_keyframe(proj, 0, 50, "location", [5.0, 0.0, 0.0])
        anim_ops.add_keyframe(proj, 1, 10, "location", [0.0, 0.0, 0.0])
        result = anim_ops.list_keyframes(proj, 0)
        assert result["action"] == "list_keyframes"
        assert len(result["keyframes"]) == 2

    def test_list_keyframes_filtered_by_prop(self) -> None:
        proj = self._proj()
        anim_ops.add_keyframe(proj, 0, 1, "location", [0.0, 0.0, 0.0])
        anim_ops.add_keyframe(proj, 0, 1, "scale", [1.0, 1.0, 1.0])
        result = anim_ops.list_keyframes(proj, 0, prop="scale")
        assert len(result["keyframes"]) == 1
        assert result["keyframes"][0]["prop"] == "scale"

    def test_set_current_frame(self) -> None:
        proj = self._proj()
        result = anim_ops.set_current_frame(proj, 42)
        assert result["action"] == "set_current_frame"
        assert result["frame"] == 42
        assert proj.data["current_frame"] == 42

    def test_build_animation_script_empty(self) -> None:
        proj = self._proj()
        stmts = anim_ops.build_animation_script(proj)
        assert stmts == []

    def test_build_animation_script_has_keyframe_insert(self) -> None:
        proj = self._proj()
        anim_ops.add_keyframe(proj, 0, 10, "location", [1.0, 0.0, 0.0], interpolation="LINEAR")
        stmts = anim_ops.build_animation_script(proj)
        joined = "\n".join(stmts)
        assert "keyframe_insert" in joined
        assert "frame_set(10)" in joined
        assert "LINEAR" in joined

    def test_interpolation_default_is_bezier(self) -> None:
        proj = self._proj()
        result = anim_ops.add_keyframe(proj, 0, 1, "location", [0.0, 0.0, 0.0])
        assert result["interpolation"] == "BEZIER"

    def test_keyframe_entry_roundtrip(self) -> None:
        from sven_integrations.blender.core.animation import KeyframeEntry
        entry = KeyframeEntry(object_index=2, frame=5, prop="scale", value=[2, 2, 2], interpolation="CONSTANT")
        restored = KeyframeEntry.from_dict(entry.to_dict())
        assert restored.object_index == 2
        assert restored.interpolation == "CONSTANT"


# ---------------------------------------------------------------------------
# Lighting op tests


class TestLightingOps:
    def _proj(self) -> BlenderProject:
        return BlenderProject(scene_name="LightTest")

    # --- CameraSpec / LightSpec dataclasses ---

    def test_camera_spec_defaults(self) -> None:
        from sven_integrations.blender.core.lighting import CameraSpec
        cam = CameraSpec(camera_id=0, name="MyCam")
        assert cam.camera_type == "PERSP"
        assert cam.focal_length == 50.0
        assert cam.active is False

    def test_light_spec_defaults(self) -> None:
        from sven_integrations.blender.core.lighting import LightSpec
        light = LightSpec(light_id=0, name="MyLight")
        assert light.light_type == "POINT"
        assert light.power == 1000.0
        assert light.color == (1.0, 1.0, 1.0)

    def test_camera_spec_roundtrip(self) -> None:
        from sven_integrations.blender.core.lighting import CameraSpec
        cam = CameraSpec(camera_id=1, name="TopCam", camera_type="ORTHO", focal_length=35.0, active=True)
        restored = CameraSpec.from_dict(cam.to_dict())
        assert restored.camera_id == 1
        assert restored.camera_type == "ORTHO"
        assert restored.active is True

    def test_light_spec_roundtrip(self) -> None:
        from sven_integrations.blender.core.lighting import LightSpec
        light = LightSpec(light_id=0, name="Sun", light_type="SUN", power=500.0, color=(0.9, 0.8, 0.7))
        restored = LightSpec.from_dict(light.to_dict())
        assert restored.light_type == "SUN"
        assert restored.power == 500.0

    # --- add_camera ---

    def test_add_camera_basic(self) -> None:
        proj = self._proj()
        result = light_ops.add_camera(proj, name="MainCam")
        assert result["action"] == "add_camera"
        assert result["name"] == "MainCam"
        assert len(proj.data["cameras"]) == 1

    def test_add_camera_invalid_type(self) -> None:
        proj = self._proj()
        with pytest.raises(ValueError, match="Unknown camera type"):
            light_ops.add_camera(proj, camera_type="FISHEYE")

    def test_add_camera_set_active(self) -> None:
        proj = self._proj()
        light_ops.add_camera(proj, name="Cam1")
        light_ops.add_camera(proj, name="Cam2", set_active=True)
        cameras = proj.data["cameras"]
        assert cameras[0]["active"] is False
        assert cameras[1]["active"] is True

    def test_set_camera_prop(self) -> None:
        proj = self._proj()
        light_ops.add_camera(proj, name="Cam")
        result = light_ops.set_camera(proj, 0, "focal_length", 85.0)
        assert result["action"] == "set_camera"
        assert proj.data["cameras"][0]["focal_length"] == 85.0

    def test_set_camera_invalid_index(self) -> None:
        proj = self._proj()
        with pytest.raises(IndexError):
            light_ops.set_camera(proj, 5, "focal_length", 50.0)

    def test_set_active_camera(self) -> None:
        proj = self._proj()
        light_ops.add_camera(proj, name="A")
        light_ops.add_camera(proj, name="B")
        light_ops.set_active_camera(proj, 0)
        assert proj.data["cameras"][0]["active"] is True
        assert proj.data["cameras"][1]["active"] is False

    def test_list_cameras(self) -> None:
        proj = self._proj()
        light_ops.add_camera(proj, name="Alpha")
        light_ops.add_camera(proj, name="Beta")
        result = light_ops.list_cameras(proj)
        assert result["action"] == "list_cameras"
        assert len(result["cameras"]) == 2
        names = [c["name"] for c in result["cameras"]]
        assert "Alpha" in names and "Beta" in names

    # --- add_light ---

    def test_add_light_point(self) -> None:
        proj = self._proj()
        result = light_ops.add_light(proj, light_type="POINT", name="KeyLight", power=800.0)
        assert result["action"] == "add_light"
        assert result["light_type"] == "POINT"
        assert result["power"] == 800.0
        assert len(proj.data["lights"]) == 1

    def test_add_light_auto_name(self) -> None:
        proj = self._proj()
        result = light_ops.add_light(proj, light_type="SUN")
        assert result["name"].startswith("SUN_light_")

    def test_add_light_invalid_type(self) -> None:
        proj = self._proj()
        with pytest.raises(ValueError, match="Unknown light type"):
            light_ops.add_light(proj, light_type="LASER")

    def test_set_light_prop(self) -> None:
        proj = self._proj()
        light_ops.add_light(proj, name="Fill")
        result = light_ops.set_light(proj, 0, "power", 500.0)
        assert result["action"] == "set_light"
        assert proj.data["lights"][0]["power"] == 500.0

    def test_list_lights(self) -> None:
        proj = self._proj()
        light_ops.add_light(proj, light_type="POINT", name="Key")
        light_ops.add_light(proj, light_type="AREA", name="Fill")
        result = light_ops.list_lights(proj)
        assert len(result["lights"]) == 2

    # --- script builders ---

    def test_build_camera_script_contains_name(self) -> None:
        proj = self._proj()
        result = light_ops.add_camera(proj, name="ScriptCam", set_active=True)
        stmts = light_ops.build_camera_script(result)
        joined = "\n".join(stmts)
        assert "ScriptCam" in joined
        assert "bpy.context.scene.camera" in joined

    def test_build_camera_script_inactive_no_set_active(self) -> None:
        proj = self._proj()
        result = light_ops.add_camera(proj, name="Passive", set_active=False)
        stmts = light_ops.build_camera_script(result)
        joined = "\n".join(stmts)
        assert "bpy.context.scene.camera" not in joined

    def test_build_light_script_contains_type(self) -> None:
        proj = self._proj()
        result = light_ops.add_light(proj, light_type="SPOT", name="SpotLight", power=600.0)
        stmts = light_ops.build_light_script(result)
        joined = "\n".join(stmts)
        assert "SPOT" in joined
        assert "SpotLight" in joined
        assert "600.0" in joined


# ---------------------------------------------------------------------------
# Modifier op tests


class TestModifierOps:
    def _proj(self) -> BlenderProject:
        return BlenderProject(scene_name="ModTest")

    # --- registry ---

    def test_registry_has_required_modifiers(self) -> None:
        required = {"SUBSURF", "MIRROR", "SOLIDIFY", "BEVEL", "ARRAY", "BOOLEAN",
                    "DECIMATE", "SMOOTH", "DISPLACE", "CURVE"}
        assert required.issubset(set(mod_ops.MODIFIER_REGISTRY.keys()))

    def test_list_available_all(self) -> None:
        items = mod_ops.list_available()
        assert len(items) >= 10
        names = {item["name"] for item in items}
        assert "SUBSURF" in names

    def test_list_available_by_category(self) -> None:
        deform = mod_ops.list_available("deform")
        assert all(item["category"] == "deform" for item in deform)
        generate = mod_ops.list_available("generate")
        assert all(item["category"] == "generate" for item in generate)

    def test_get_modifier_info(self) -> None:
        info = mod_ops.get_modifier_info("SUBSURF")
        assert info["name"] == "SUBSURF"
        assert "levels" in info["params"]
        assert "render_levels" in info["params"]

    def test_get_modifier_info_unknown(self) -> None:
        with pytest.raises(KeyError, match="Unknown modifier"):
            mod_ops.get_modifier_info("NONEXISTENT")

    def test_validate_params_fills_defaults(self) -> None:
        result = mod_ops.validate_params("SUBSURF", {})
        assert result["levels"] == 2
        assert result["render_levels"] == 2

    def test_validate_params_overrides_defaults(self) -> None:
        result = mod_ops.validate_params("SUBSURF", {"levels": 4})
        assert result["levels"] == 4

    def test_validate_params_unknown_param(self) -> None:
        with pytest.raises(ValueError, match="does not support"):
            mod_ops.validate_params("SUBSURF", {"nonexistent_param": 1})

    # --- add_modifier ---

    def test_add_modifier_basic(self) -> None:
        proj = self._proj()
        result = mod_ops.add_modifier(proj, "SUBSURF", 0)
        assert result["action"] == "add_modifier"
        assert result["type"] == "SUBSURF"
        assert result["object_index"] == 0
        assert len(proj.data["modifiers"]) == 1

    def test_add_modifier_with_params(self) -> None:
        proj = self._proj()
        result = mod_ops.add_modifier(proj, "BEVEL", 0, params={"width": 0.2, "segments": 3})
        assert result["params"]["width"] == 0.2
        assert result["params"]["segments"] == 3

    def test_add_modifier_custom_name(self) -> None:
        proj = self._proj()
        result = mod_ops.add_modifier(proj, "MIRROR", 1, name="SymMirror")
        assert result["name"] == "SymMirror"

    def test_add_modifier_auto_name(self) -> None:
        proj = self._proj()
        result = mod_ops.add_modifier(proj, "DECIMATE", 0)
        assert result["name"].startswith("DECIMATE_")

    def test_add_modifier_unknown_type(self) -> None:
        proj = self._proj()
        with pytest.raises(KeyError):
            mod_ops.add_modifier(proj, "WELD_EVERYTHING", 0)

    # --- remove_modifier ---

    def test_remove_modifier(self) -> None:
        proj = self._proj()
        result = mod_ops.add_modifier(proj, "SMOOTH", 0)
        mod_id = result["modifier_id"]
        remove_result = mod_ops.remove_modifier(proj, mod_id, 0)
        assert remove_result["action"] == "remove_modifier"
        assert proj.data["modifiers"] == []

    def test_remove_modifier_not_found(self) -> None:
        proj = self._proj()
        with pytest.raises(KeyError):
            mod_ops.remove_modifier(proj, 999, 0)

    # --- set_modifier_param ---

    def test_set_modifier_param(self) -> None:
        proj = self._proj()
        result = mod_ops.add_modifier(proj, "ARRAY", 0)
        mod_id = result["modifier_id"]
        set_result = mod_ops.set_modifier_param(proj, mod_id, "count", 5, 0)
        assert set_result["action"] == "set_modifier_param"
        assert proj.data["modifiers"][0]["params"]["count"] == 5

    def test_set_modifier_param_invalid(self) -> None:
        proj = self._proj()
        result = mod_ops.add_modifier(proj, "SOLIDIFY", 0)
        mod_id = result["modifier_id"]
        with pytest.raises(KeyError):
            mod_ops.set_modifier_param(proj, mod_id, "bad_param", 1.0, 0)

    # --- list_modifiers ---

    def test_list_modifiers(self) -> None:
        proj = self._proj()
        mod_ops.add_modifier(proj, "SUBSURF", 0)
        mod_ops.add_modifier(proj, "BEVEL", 0)
        mod_ops.add_modifier(proj, "MIRROR", 1)
        result = mod_ops.list_modifiers(proj, 0)
        assert result["action"] == "list_modifiers"
        assert len(result["modifiers"]) == 2
        assert result["object_index"] == 0

    def test_list_modifiers_empty(self) -> None:
        proj = self._proj()
        result = mod_ops.list_modifiers(proj, 0)
        assert result["modifiers"] == []

    # --- build_modifier_scripts ---

    def test_build_modifier_scripts(self) -> None:
        proj = self._proj()
        mod_ops.add_modifier(proj, "SUBSURF", 0, params={"levels": 3})
        mod_ops.add_modifier(proj, "BEVEL", 0, params={"width": 0.05})
        stmts = mod_ops.build_modifier_scripts(proj, 0)
        joined = "\n".join(stmts)
        assert "SUBSURF" in joined
        assert "BEVEL" in joined
        assert "levels" in joined
        assert "modifiers.new" in joined

    def test_build_modifier_scripts_empty(self) -> None:
        proj = self._proj()
        stmts = mod_ops.build_modifier_scripts(proj, 0)
        assert stmts == []

    def test_build_modifier_scripts_only_for_object(self) -> None:
        proj = self._proj()
        mod_ops.add_modifier(proj, "MIRROR", 0)
        mod_ops.add_modifier(proj, "SOLIDIFY", 1)
        stmts = mod_ops.build_modifier_scripts(proj, 1)
        joined = "\n".join(stmts)
        assert "SOLIDIFY" in joined
        assert "MIRROR" not in joined
