"""Blender modifier management.

Provides a registry of common Blender modifiers, validation helpers, and
functions to add, remove, configure, and script modifiers on scene objects.
All modifier state is stored in ``project.data["modifiers"]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..project import BlenderProject

# ---------------------------------------------------------------------------
# Modifier registry
#
# Each entry describes one Blender modifier type with its bpy_type (the
# string passed to ``object.modifiers.new``), a human-readable description,
# a broad category, and the supported parameters with their types, defaults,
# and brief descriptions.

MODIFIER_REGISTRY: dict[str, dict[str, Any]] = {
    "SUBSURF": {
        "description": "Subdivide the mesh for smoothing.",
        "category": "generate",
        "bpy_type": "SUBSURF",
        "params": {
            "levels": {
                "type": int,
                "default": 2,
                "description": "Viewport subdivision levels.",
            },
            "render_levels": {
                "type": int,
                "default": 2,
                "description": "Render subdivision levels.",
            },
        },
    },
    "MIRROR": {
        "description": "Mirror the mesh across one or more axes.",
        "category": "generate",
        "bpy_type": "MIRROR",
        "params": {
            "use_axis_x": {"type": bool, "default": True, "description": "Mirror on X axis."},
            "use_axis_y": {"type": bool, "default": False, "description": "Mirror on Y axis."},
            "use_axis_z": {"type": bool, "default": False, "description": "Mirror on Z axis."},
        },
    },
    "SOLIDIFY": {
        "description": "Add thickness to mesh surfaces.",
        "category": "generate",
        "bpy_type": "SOLIDIFY",
        "params": {
            "thickness": {"type": float, "default": 0.01, "description": "Shell thickness."},
            "offset": {"type": float, "default": -1.0, "description": "Offset from original surface."},
        },
    },
    "BEVEL": {
        "description": "Bevel edges or vertices of a mesh.",
        "category": "generate",
        "bpy_type": "BEVEL",
        "params": {
            "width": {"type": float, "default": 0.1, "description": "Bevel width."},
            "segments": {"type": int, "default": 1, "description": "Number of bevel segments."},
            "limit_method": {
                "type": str,
                "default": "NONE",
                "description": "How to limit bevel effect (NONE, ANGLE, WEIGHT).",
            },
        },
    },
    "ARRAY": {
        "description": "Duplicate the mesh in an array.",
        "category": "generate",
        "bpy_type": "ARRAY",
        "params": {
            "count": {"type": int, "default": 2, "description": "Number of copies."},
            "relative_offset_x": {
                "type": float,
                "default": 1.0,
                "description": "X relative offset between copies.",
            },
            "relative_offset_y": {
                "type": float,
                "default": 0.0,
                "description": "Y relative offset between copies.",
            },
            "relative_offset_z": {
                "type": float,
                "default": 0.0,
                "description": "Z relative offset between copies.",
            },
        },
    },
    "BOOLEAN": {
        "description": "Perform boolean operations with another object.",
        "category": "generate",
        "bpy_type": "BOOLEAN",
        "params": {
            "operation": {
                "type": str,
                "default": "DIFFERENCE",
                "description": "Boolean operation (DIFFERENCE, UNION, INTERSECT).",
            },
            "object_name": {
                "type": str,
                "default": "",
                "description": "Name of the cutter object.",
            },
        },
    },
    "DECIMATE": {
        "description": "Reduce mesh polygon count.",
        "category": "generate",
        "bpy_type": "DECIMATE",
        "params": {
            "ratio": {
                "type": float,
                "default": 0.5,
                "description": "Fraction of faces to keep (0–1).",
            },
        },
    },
    "SMOOTH": {
        "description": "Smooth mesh vertex positions.",
        "category": "deform",
        "bpy_type": "SMOOTH",
        "params": {
            "factor": {"type": float, "default": 0.5, "description": "Smooth strength."},
            "iterations": {"type": int, "default": 1, "description": "Number of smooth passes."},
        },
    },
    "DISPLACE": {
        "description": "Displace mesh vertices along their normals using a texture.",
        "category": "deform",
        "bpy_type": "DISPLACE",
        "params": {
            "strength": {"type": float, "default": 1.0, "description": "Displacement strength."},
            "mid_level": {
                "type": float,
                "default": 0.5,
                "description": "Texture midpoint (values above/below displace in opposite directions).",
            },
        },
    },
    "CURVE": {
        "description": "Deform a mesh along a curve object.",
        "category": "deform",
        "bpy_type": "CURVE",
        "params": {
            "object_name": {
                "type": str,
                "default": "",
                "description": "Name of the curve object to deform along.",
            },
            "deform_axis": {
                "type": str,
                "default": "POS_X",
                "description": "Axis to deform along (POS_X, POS_Y, POS_Z, NEG_X, NEG_Y, NEG_Z).",
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Registry helpers


def list_available(category: str | None = None) -> list[dict[str, Any]]:
    """Return a list of available modifier descriptors.

    When *category* is given, only modifiers in that category are returned.
    """
    results = []
    for name, info in MODIFIER_REGISTRY.items():
        if category is None or info["category"] == category:
            results.append(
                {
                    "name": name,
                    "description": info["description"],
                    "category": info["category"],
                    "bpy_type": info["bpy_type"],
                    "params": list(info["params"].keys()),
                }
            )
    return results


def get_modifier_info(name: str) -> dict[str, Any]:
    """Return the full descriptor for the named modifier.

    Raises ``KeyError`` when *name* is not in the registry.
    """
    key = name.upper()
    if key not in MODIFIER_REGISTRY:
        raise KeyError(
            f"Unknown modifier {name!r}. Available: {', '.join(sorted(MODIFIER_REGISTRY))}"
        )
    info = MODIFIER_REGISTRY[key]
    return {
        "name": key,
        "description": info["description"],
        "category": info["category"],
        "bpy_type": info["bpy_type"],
        "params": {
            pname: {
                "type": pinfo["type"].__name__,
                "default": pinfo["default"],
                "description": pinfo["description"],
            }
            for pname, pinfo in info["params"].items()
        },
    }


def validate_params(name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Validate *params* against the registry entry for *name*.

    Unknown parameters raise ``ValueError``.  Missing parameters are filled
    with their registry defaults.  Returns a fully populated params dict.
    """
    key = name.upper()
    if key not in MODIFIER_REGISTRY:
        raise KeyError(f"Unknown modifier {name!r}.")
    schema = MODIFIER_REGISTRY[key]["params"]
    unknown = set(params) - set(schema)
    if unknown:
        raise ValueError(
            f"Modifier {key!r} does not support parameter(s): {', '.join(sorted(unknown))}"
        )
    result: dict[str, Any] = {pname: pinfo["default"] for pname, pinfo in schema.items()}
    result.update(params)
    return result


# ---------------------------------------------------------------------------
# Internal data model


@dataclass
class ModifierEntry:
    """A single modifier applied to a scene object."""

    modifier_id: int
    type: str
    object_index: int
    name: str
    params: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "modifier_id": self.modifier_id,
            "type": self.type,
            "object_index": self.object_index,
            "name": self.name,
            "params": dict(self.params),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ModifierEntry":
        return cls(
            modifier_id=int(d["modifier_id"]),
            type=str(d["type"]),
            object_index=int(d["object_index"]),
            name=str(d["name"]),
            params=dict(d.get("params") or {}),
        )


# ---------------------------------------------------------------------------
# Private helpers


def _modifiers(project: BlenderProject) -> list[dict[str, Any]]:
    return project.data.setdefault("modifiers", [])


def _next_global_id(modifiers: list[dict[str, Any]]) -> int:
    if not modifiers:
        return 0
    return max(m["modifier_id"] for m in modifiers) + 1


# ---------------------------------------------------------------------------
# Modifier CRUD


def add_modifier(
    project: BlenderProject,
    modifier_type: str,
    object_index: int,
    name: str | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add a modifier of *modifier_type* to the object at *object_index*.

    *params* are validated and filled with defaults via :func:`validate_params`.
    Raises ``KeyError`` for unknown modifier types and ``ValueError`` for bad
    parameter names.
    """
    key = modifier_type.upper()
    validated = validate_params(key, params or {})
    modifiers = _modifiers(project)
    mod_id = _next_global_id(modifiers)
    resolved_name = name if name else f"{key}_{mod_id}"
    entry = ModifierEntry(
        modifier_id=mod_id,
        type=key,
        object_index=object_index,
        name=resolved_name,
        params=validated,
    )
    modifiers.append(entry.to_dict())
    return {"action": "add_modifier", **entry.to_dict()}


def remove_modifier(
    project: BlenderProject,
    modifier_index: int,
    object_index: int,
) -> dict[str, Any]:
    """Remove the modifier with *modifier_index* (modifier_id) from *object_index*.

    Raises ``KeyError`` when the modifier is not found.
    """
    modifiers = _modifiers(project)
    before = len(modifiers)
    project.data["modifiers"] = [
        m for m in modifiers
        if not (m["modifier_id"] == modifier_index and m["object_index"] == object_index)
    ]
    if len(project.data["modifiers"]) == before:
        raise KeyError(
            f"Modifier id={modifier_index} on object_index={object_index} not found."
        )
    return {
        "action": "remove_modifier",
        "modifier_index": modifier_index,
        "object_index": object_index,
    }


def set_modifier_param(
    project: BlenderProject,
    modifier_index: int,
    param: str,
    value: Any,
    object_index: int,
) -> dict[str, Any]:
    """Set a single parameter on a modifier.

    Raises ``KeyError`` when the modifier or parameter is not found.
    """
    modifiers = _modifiers(project)
    for mod in modifiers:
        if mod["modifier_id"] == modifier_index and mod["object_index"] == object_index:
            schema = MODIFIER_REGISTRY.get(mod["type"], {}).get("params", {})
            if param not in schema:
                raise KeyError(
                    f"Parameter {param!r} not valid for modifier type {mod['type']!r}."
                )
            mod["params"][param] = value
            return {
                "action": "set_modifier_param",
                "modifier_index": modifier_index,
                "object_index": object_index,
                "param": param,
                "value": value,
            }
    raise KeyError(
        f"Modifier id={modifier_index} on object_index={object_index} not found."
    )


def list_modifiers(project: BlenderProject, object_index: int) -> dict[str, Any]:
    """Return all modifiers applied to the object at *object_index*."""
    modifiers = _modifiers(project)
    results = [m for m in modifiers if m["object_index"] == object_index]
    return {"action": "list_modifiers", "object_index": object_index, "modifiers": results}


# ---------------------------------------------------------------------------
# Script builder


def build_modifier_scripts(project: BlenderProject, object_index: int) -> list[str]:
    """Return Blender Python statements that apply all modifiers to an object.

    Statements assume the object is referenced by its index in the scene
    object list.
    """
    modifiers = _modifiers(project)
    obj_mods = [m for m in modifiers if m["object_index"] == object_index]
    if not obj_mods:
        return []

    stmts: list[str] = [
        "import bpy",
        f"_mod_obj = list(bpy.context.scene.objects)[{object_index}]",
        "bpy.context.view_layer.objects.active = _mod_obj",
    ]
    for mod in obj_mods:
        bpy_type = MODIFIER_REGISTRY.get(mod["type"], {}).get("bpy_type", mod["type"])
        safe_name = mod["name"].replace('"', '\\"')
        stmts.append(
            f'_mod = _mod_obj.modifiers.new(name="{safe_name}", type={bpy_type!r})'
        )
        for pname, pval in mod["params"].items():
            stmts.append(f"_mod.{pname} = {pval!r}")
    return stmts
