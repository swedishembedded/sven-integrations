"""Blender camera and light management.

Functions to add, configure, and list cameras and lights in a project.
Camera state is stored in ``project.data["cameras"]``, light state in
``project.data["lights"]``.  Script-building helpers produce Blender Python
statements suitable for use with
:meth:`~sven_integrations.blender.backend.BlenderBackend.build_python_expr`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ..project import BlenderProject

CameraType = Literal["PERSP", "ORTHO", "PANO"]
LightType = Literal["POINT", "SUN", "SPOT", "AREA"]

_VALID_CAMERA_TYPES: frozenset[str] = frozenset({"PERSP", "ORTHO", "PANO"})
_VALID_LIGHT_TYPES: frozenset[str] = frozenset({"POINT", "SUN", "SPOT", "AREA"})


# ---------------------------------------------------------------------------
# Internal data model


@dataclass
class CameraSpec:
    """Harness representation of a Blender camera."""

    camera_id: int
    name: str
    location: tuple[float, float, float] = (0.0, -10.0, 5.0)
    rotation: tuple[float, float, float] = (1.1, 0.0, 0.0)
    camera_type: str = "PERSP"
    focal_length: float = 50.0
    sensor_width: float = 36.0
    clip_start: float = 0.1
    clip_end: float = 1000.0
    active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "location": list(self.location),
            "rotation": list(self.rotation),
            "camera_type": self.camera_type,
            "focal_length": self.focal_length,
            "sensor_width": self.sensor_width,
            "clip_start": self.clip_start,
            "clip_end": self.clip_end,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CameraSpec":
        def _t3(v: Any) -> tuple[float, float, float]:
            s = list(v) if v else [0.0, 0.0, 0.0]
            return (float(s[0]), float(s[1]), float(s[2]))

        return cls(
            camera_id=int(d["camera_id"]),
            name=str(d["name"]),
            location=_t3(d.get("location", [0.0, -10.0, 5.0])),
            rotation=_t3(d.get("rotation", [1.1, 0.0, 0.0])),
            camera_type=str(d.get("camera_type", "PERSP")),
            focal_length=float(d.get("focal_length", 50.0)),
            sensor_width=float(d.get("sensor_width", 36.0)),
            clip_start=float(d.get("clip_start", 0.1)),
            clip_end=float(d.get("clip_end", 1000.0)),
            active=bool(d.get("active", False)),
        )


@dataclass
class LightSpec:
    """Harness representation of a Blender light."""

    light_id: int
    name: str
    light_type: str = "POINT"
    location: tuple[float, float, float] = (0.0, 0.0, 5.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    color: tuple[float, float, float] = (1.0, 1.0, 1.0)
    power: float = 1000.0
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "light_id": self.light_id,
            "name": self.name,
            "light_type": self.light_type,
            "location": list(self.location),
            "rotation": list(self.rotation),
            "color": list(self.color),
            "power": self.power,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LightSpec":
        def _t3(v: Any, default: list[float]) -> tuple[float, float, float]:
            s = list(v) if v else default
            return (float(s[0]), float(s[1]), float(s[2]))

        return cls(
            light_id=int(d["light_id"]),
            name=str(d["name"]),
            light_type=str(d.get("light_type", "POINT")),
            location=_t3(d.get("location"), [0.0, 0.0, 5.0]),
            rotation=_t3(d.get("rotation"), [0.0, 0.0, 0.0]),
            color=_t3(d.get("color"), [1.0, 1.0, 1.0]),
            power=float(d.get("power", 1000.0)),
            active=bool(d.get("active", True)),
        )


# ---------------------------------------------------------------------------
# Private helpers


def _cameras(project: BlenderProject) -> list[dict[str, Any]]:
    return project.data.setdefault("cameras", [])


def _lights(project: BlenderProject) -> list[dict[str, Any]]:
    return project.data.setdefault("lights", [])


# ---------------------------------------------------------------------------
# Camera API


def add_camera(
    project: BlenderProject,
    name: str = "Camera",
    location: tuple[float, float, float] = (0.0, -10.0, 5.0),
    rotation: tuple[float, float, float] = (1.1, 0.0, 0.0),
    camera_type: str = "PERSP",
    focal_length: float = 50.0,
    sensor_width: float = 36.0,
    clip_start: float = 0.1,
    clip_end: float = 1000.0,
    set_active: bool = False,
) -> dict[str, Any]:
    """Add a camera to the project.

    Raises ``ValueError`` for an unknown *camera_type*.
    """
    ct = camera_type.upper()
    if ct not in _VALID_CAMERA_TYPES:
        raise ValueError(
            f"Unknown camera type {camera_type!r}. Choose from: {', '.join(sorted(_VALID_CAMERA_TYPES))}"
        )
    cameras = _cameras(project)
    camera_id = len(cameras)

    if set_active:
        for cam in cameras:
            cam["active"] = False

    spec = CameraSpec(
        camera_id=camera_id,
        name=name,
        location=location,
        rotation=rotation,
        camera_type=ct,
        focal_length=focal_length,
        sensor_width=sensor_width,
        clip_start=clip_start,
        clip_end=clip_end,
        active=set_active,
    )
    cameras.append(spec.to_dict())
    return {"action": "add_camera", **spec.to_dict()}


def set_camera(project: BlenderProject, index: int, prop: str, value: Any) -> dict[str, Any]:
    """Set a property on the camera at *index*."""
    cameras = _cameras(project)
    if index < 0 or index >= len(cameras):
        raise IndexError(f"Camera index {index} out of range (have {len(cameras)}).")
    cam = cameras[index]
    if prop not in cam:
        raise KeyError(f"Unknown camera property {prop!r}.")
    cam[prop] = value
    return {"action": "set_camera", "index": index, "prop": prop, "value": value}


def set_active_camera(project: BlenderProject, index: int) -> dict[str, Any]:
    """Mark the camera at *index* as the active scene camera."""
    cameras = _cameras(project)
    if index < 0 or index >= len(cameras):
        raise IndexError(f"Camera index {index} out of range (have {len(cameras)}).")
    for i, cam in enumerate(cameras):
        cam["active"] = i == index
    return {"action": "set_active_camera", "index": index}


def list_cameras(project: BlenderProject) -> dict[str, Any]:
    """Return all cameras stored in the project."""
    return {"action": "list_cameras", "cameras": list(_cameras(project))}


# ---------------------------------------------------------------------------
# Light API


def add_light(
    project: BlenderProject,
    light_type: str = "POINT",
    name: str | None = None,
    location: tuple[float, float, float] = (0.0, 0.0, 5.0),
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    color: tuple[float, float, float] = (1.0, 1.0, 1.0),
    power: float = 1000.0,
) -> dict[str, Any]:
    """Add a light to the project.

    Raises ``ValueError`` for an unknown *light_type*.
    """
    lt = light_type.upper()
    if lt not in _VALID_LIGHT_TYPES:
        raise ValueError(
            f"Unknown light type {light_type!r}. Choose from: {', '.join(sorted(_VALID_LIGHT_TYPES))}"
        )
    lights = _lights(project)
    light_id = len(lights)
    resolved_name = name if name else f"{lt}_light_{light_id}"
    spec = LightSpec(
        light_id=light_id,
        name=resolved_name,
        light_type=lt,
        location=location,
        rotation=rotation,
        color=color,
        power=power,
        active=True,
    )
    lights.append(spec.to_dict())
    return {"action": "add_light", **spec.to_dict()}


def set_light(project: BlenderProject, index: int, prop: str, value: Any) -> dict[str, Any]:
    """Set a property on the light at *index*."""
    lights = _lights(project)
    if index < 0 or index >= len(lights):
        raise IndexError(f"Light index {index} out of range (have {len(lights)}).")
    light = lights[index]
    if prop not in light:
        raise KeyError(f"Unknown light property {prop!r}.")
    light[prop] = value
    return {"action": "set_light", "index": index, "prop": prop, "value": value}


def list_lights(project: BlenderProject) -> dict[str, Any]:
    """Return all lights stored in the project."""
    return {"action": "list_lights", "lights": list(_lights(project))}


# ---------------------------------------------------------------------------
# Script builders


def build_camera_script(camera: dict[str, Any]) -> list[str]:
    """Return Blender Python statements that create the given camera."""
    spec = CameraSpec.from_dict(camera)
    safe_name = spec.name.replace('"', '\\"')
    loc = f"({spec.location[0]}, {spec.location[1]}, {spec.location[2]})"
    rot = f"({spec.rotation[0]}, {spec.rotation[1]}, {spec.rotation[2]})"
    stmts: list[str] = [
        "import bpy",
        f'_cam_data = bpy.data.cameras.new(name="{safe_name}")',
        f"_cam_data.type = {spec.camera_type!r}",
        f"_cam_data.lens = {spec.focal_length}",
        f"_cam_data.sensor_width = {spec.sensor_width}",
        f"_cam_data.clip_start = {spec.clip_start}",
        f"_cam_data.clip_end = {spec.clip_end}",
        f'_cam_obj = bpy.data.objects.new("{safe_name}", _cam_data)',
        f"_cam_obj.location = {loc}",
        f"_cam_obj.rotation_euler = {rot}",
        "bpy.context.collection.objects.link(_cam_obj)",
    ]
    if spec.active:
        stmts.append("bpy.context.scene.camera = _cam_obj")
    return stmts


def build_light_script(light: dict[str, Any]) -> list[str]:
    """Return Blender Python statements that create the given light."""
    spec = LightSpec.from_dict(light)
    safe_name = spec.name.replace('"', '\\"')
    loc = f"({spec.location[0]}, {spec.location[1]}, {spec.location[2]})"
    rot = f"({spec.rotation[0]}, {spec.rotation[1]}, {spec.rotation[2]})"
    col = f"({spec.color[0]}, {spec.color[1]}, {spec.color[2]}, 1.0)"
    return [
        "import bpy",
        f'_light_data = bpy.data.lights.new(name="{safe_name}", type={spec.light_type!r})',
        f"_light_data.energy = {spec.power}",
        f"_light_data.color = {col}",
        f'_light_obj = bpy.data.objects.new("{safe_name}", _light_data)',
        f"_light_obj.location = {loc}",
        f"_light_obj.rotation_euler = {rot}",
        "bpy.context.collection.objects.link(_light_obj)",
    ]
