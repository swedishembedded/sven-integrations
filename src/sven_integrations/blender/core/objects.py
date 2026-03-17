"""Blender object operations.

Each function returns a result dict containing a ``"statements"`` key with
a ``list[str]`` of Python statements for use with
:meth:`~sven_integrations.blender.backend.BlenderBackend.build_python_expr`.
"""

from __future__ import annotations

from typing import Any

_MESH_TYPES = frozenset({"CUBE", "SPHERE", "PLANE", "CYLINDER", "CONE", "TORUS", "MONKEY"})
_LIGHT_TYPES = frozenset({"POINT", "SUN", "SPOT", "AREA"})

_OPS = {
    "CUBE": "bpy.ops.mesh.primitive_cube_add",
    "SPHERE": "bpy.ops.mesh.primitive_uv_sphere_add",
    "PLANE": "bpy.ops.mesh.primitive_plane_add",
    "CYLINDER": "bpy.ops.mesh.primitive_cylinder_add",
    "CONE": "bpy.ops.mesh.primitive_cone_add",
    "TORUS": "bpy.ops.mesh.primitive_torus_add",
    "MONKEY": "bpy.ops.mesh.primitive_monkey_add",
}


def _preamble() -> list[str]:
    return ["import bpy"]


def add_mesh(
    mesh_type: str,
    location: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> dict[str, Any]:
    """Add a primitive mesh object to the active scene.

    *mesh_type* must be one of: ``CUBE``, ``SPHERE``, ``PLANE``,
    ``CYLINDER``, ``CONE``, ``TORUS``, ``MONKEY``.
    """
    key = mesh_type.upper()
    if key not in _MESH_TYPES:
        raise ValueError(
            f"Unknown mesh type {mesh_type!r}. Choose from: {', '.join(sorted(_MESH_TYPES))}"
        )
    op = _OPS[key]
    loc = f"({location[0]}, {location[1]}, {location[2]})"
    stmts = _preamble() + [
        f"{op}(location={loc})",
    ]
    return {
        "action": "add_mesh",
        "mesh_type": key,
        "location": location,
        "statements": stmts,
    }


def add_light(
    light_type: str,
    location: tuple[float, float, float] = (0.0, 0.0, 5.0),
    energy: float = 1000.0,
) -> dict[str, Any]:
    """Add a light source to the active scene.

    *light_type* must be one of: ``POINT``, ``SUN``, ``SPOT``, ``AREA``.
    """
    lt = light_type.upper()
    if lt not in _LIGHT_TYPES:
        raise ValueError(
            f"Unknown light type {light_type!r}. Choose from: {', '.join(sorted(_LIGHT_TYPES))}"
        )
    loc = f"({location[0]}, {location[1]}, {location[2]})"
    stmts = _preamble() + [
        f"light_data = bpy.data.lights.new(name='{lt}_light', type='{lt}')",
        f"light_data.energy = {energy}",
        f"light_obj = bpy.data.objects.new(name='{lt}_light', object_data=light_data)",
        f"light_obj.location = {loc}",
        "bpy.context.collection.objects.link(light_obj)",
    ]
    return {
        "action": "add_light",
        "light_type": lt,
        "location": location,
        "energy": energy,
        "statements": stmts,
    }


def add_camera(
    location: tuple[float, float, float] = (0.0, -10.0, 5.0),
    target: tuple[float, float, float] | None = None,
) -> dict[str, Any]:
    """Add a camera to the scene and optionally point it at *target*."""
    loc = f"({location[0]}, {location[1]}, {location[2]})"
    stmts = _preamble() + [
        "cam_data = bpy.data.cameras.new(name='Camera')",
        "cam_obj = bpy.data.objects.new('Camera', cam_data)",
        f"cam_obj.location = {loc}",
        "bpy.context.collection.objects.link(cam_obj)",
        "bpy.context.scene.camera = cam_obj",
    ]
    if target is not None:
        tx, ty, tz = target
        stmts += [
            "import mathutils",
            f"direction = mathutils.Vector(({tx}, {ty}, {tz})) - cam_obj.location",
            "rot_quat = direction.to_track_quat('-Z', 'Y')",
            "cam_obj.rotation_euler = rot_quat.to_euler()",
        ]
    return {
        "action": "add_camera",
        "location": location,
        "target": target,
        "statements": stmts,
    }


def delete_object(name: str) -> dict[str, Any]:
    """Delete the object named *name* from the scene."""
    safe = name.replace('"', '\\"')
    stmts = _preamble() + [
        f'obj = bpy.data.objects.get("{safe}")',
        f"if obj is None: raise ValueError('Object not found: {safe!r}')",
        "bpy.data.objects.remove(obj, do_unlink=True)",
    ]
    return {
        "action": "delete_object",
        "name": name,
        "statements": stmts,
    }


def duplicate_object(name: str, new_name: str) -> dict[str, Any]:
    """Duplicate *name* and rename the copy to *new_name*."""
    safe = name.replace('"', '\\"')
    safe_new = new_name.replace('"', '\\"')
    stmts = _preamble() + [
        f'src = bpy.data.objects.get("{safe}")',
        f"if src is None: raise ValueError('Object not found: {safe!r}')",
        "copy = src.copy()",
        "copy.data = src.data.copy() if src.data else None",
        f'copy.name = "{safe_new}"',
        "bpy.context.collection.objects.link(copy)",
    ]
    return {
        "action": "duplicate_object",
        "name": name,
        "new_name": new_name,
        "statements": stmts,
    }


def apply_transform(name: str) -> dict[str, Any]:
    """Apply location, rotation and scale transforms to *name*."""
    safe = name.replace('"', '\\"')
    stmts = _preamble() + [
        f'obj = bpy.data.objects.get("{safe}")',
        f"if obj is None: raise ValueError('Object not found: {safe!r}')",
        "bpy.context.view_layer.objects.active = obj",
        "obj.select_set(True)",
        "bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)",
    ]
    return {
        "action": "apply_transform",
        "name": name,
        "statements": stmts,
    }


def set_parent(child: str, parent: str) -> dict[str, Any]:
    """Parent object *child* to *parent*."""
    safe_c = child.replace('"', '\\"')
    safe_p = parent.replace('"', '\\"')
    stmts = _preamble() + [
        f'child_obj = bpy.data.objects.get("{safe_c}")',
        f'parent_obj = bpy.data.objects.get("{safe_p}")',
        f"if child_obj is None: raise ValueError('Child not found: {safe_c!r}')",
        f"if parent_obj is None: raise ValueError('Parent not found: {safe_p!r}')",
        "child_obj.parent = parent_obj",
    ]
    return {
        "action": "set_parent",
        "child": child,
        "parent": parent,
        "statements": stmts,
    }
