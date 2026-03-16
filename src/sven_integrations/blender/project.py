"""Blender scene project model.

Represents the subset of Blender scene state the CLI harness tracks:
frame range, FPS, and the list of scene objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SceneObject:
    """A single object in the Blender scene graph."""

    name: str
    type: str = "MESH"
    location: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    material: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "location": list(self.location),
            "rotation": list(self.rotation),
            "scale": list(self.scale),
            "material": self.material,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneObject":
        def _to3(v: Any) -> tuple[float, float, float]:
            seq = list(v) if v else [0.0, 0.0, 0.0]
            return (float(seq[0]), float(seq[1]), float(seq[2]))

        return cls(
            name=str(data["name"]),
            type=str(data.get("type", "MESH")),
            location=_to3(data.get("location", [0, 0, 0])),
            rotation=_to3(data.get("rotation", [0, 0, 0])),
            scale=_to3(data.get("scale", [1, 1, 1])),
            material=data.get("material"),
        )


@dataclass
class BlenderProject:
    """Tracks the state of a Blender scene being managed by the CLI harness."""

    blend_file: str | None = None
    scene_name: str = "Scene"
    frame_start: int = 1
    frame_end: int = 250
    fps: int = 24
    objects: list[SceneObject] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Object helpers

    def add_object(self, obj: SceneObject) -> None:
        """Add *obj* to the scene object list."""
        self.objects.append(obj)

    def remove_object(self, name: str) -> bool:
        """Remove the object named *name*.  Returns True if it existed."""
        before = len(self.objects)
        self.objects = [o for o in self.objects if o.name != name]
        return len(self.objects) < before

    def find_object(self, name: str) -> SceneObject | None:
        """Return the first object with *name*, or *None*."""
        for obj in self.objects:
            if obj.name == name:
                return obj
        return None

    # ------------------------------------------------------------------
    # Serialisation

    def to_dict(self) -> dict[str, Any]:
        return {
            "blend_file": self.blend_file,
            "scene_name": self.scene_name,
            "frame_start": self.frame_start,
            "frame_end": self.frame_end,
            "fps": self.fps,
            "objects": [o.to_dict() for o in self.objects],
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "BlenderProject":
        return cls(
            blend_file=raw.get("blend_file"),
            scene_name=str(raw.get("scene_name", "Scene")),
            frame_start=int(raw.get("frame_start", 1)),
            frame_end=int(raw.get("frame_end", 250)),
            fps=int(raw.get("fps", 24)),
            objects=[SceneObject.from_dict(o) for o in raw.get("objects", [])],
            data=dict(raw.get("data") or {}),
        )
