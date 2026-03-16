"""Blender material management helpers.

Functions return result dicts with a ``"statements"`` key containing
``list[str]`` of Python statements for
:meth:`~sven_integrations.blender.backend.BlenderBackend.build_python_expr`.
"""

from __future__ import annotations

from typing import Any


def _preamble() -> list[str]:
    return ["import bpy"]


def create_material(
    name: str,
    color: tuple[float, float, float, float] = (0.8, 0.8, 0.8, 1.0),
) -> dict[str, Any]:
    """Create a new Principled BSDF material with the given base *color*.

    *color* is an RGBA tuple with each component in ``[0.0, 1.0]``.
    """
    safe = name.replace('"', '\\"')
    r, g, b, a = color
    stmts = _preamble() + [
        f'mat = bpy.data.materials.new(name="{safe}")',
        "mat.use_nodes = True",
        "nodes = mat.node_tree.nodes",
        "bsdf = nodes.get('Principled BSDF')",
        f"bsdf.inputs['Base Color'].default_value = ({r}, {g}, {b}, {a})",
    ]
    return {
        "action": "create_material",
        "name": name,
        "color": color,
        "statements": stmts,
    }


def assign_material(object_name: str, material_name: str) -> dict[str, Any]:
    """Assign an existing material to an object's first material slot."""
    safe_obj = object_name.replace('"', '\\"')
    safe_mat = material_name.replace('"', '\\"')
    stmts = _preamble() + [
        f'obj = bpy.data.objects.get("{safe_obj}")',
        f'mat = bpy.data.materials.get("{safe_mat}")',
        f"if obj is None: raise ValueError('Object not found: {safe_obj!r}')",
        f"if mat is None: raise ValueError('Material not found: {safe_mat!r}')",
        "if obj.data.materials:",
        "    obj.data.materials[0] = mat",
        "else:",
        "    obj.data.materials.append(mat)",
    ]
    return {
        "action": "assign_material",
        "object_name": object_name,
        "material_name": material_name,
        "statements": stmts,
    }


def set_metallic(mat_name: str, value: float) -> dict[str, Any]:
    """Set the metallic factor of a Principled BSDF material."""
    safe = mat_name.replace('"', '\\"')
    stmts = _preamble() + [
        f'mat = bpy.data.materials.get("{safe}")',
        f"if mat is None: raise ValueError('Material not found: {safe!r}')",
        "bsdf = mat.node_tree.nodes.get('Principled BSDF')",
        f"bsdf.inputs['Metallic'].default_value = {value}",
    ]
    return {
        "action": "set_metallic",
        "mat_name": mat_name,
        "value": value,
        "statements": stmts,
    }


def set_roughness(mat_name: str, value: float) -> dict[str, Any]:
    """Set the roughness factor of a Principled BSDF material."""
    safe = mat_name.replace('"', '\\"')
    stmts = _preamble() + [
        f'mat = bpy.data.materials.get("{safe}")',
        f"if mat is None: raise ValueError('Material not found: {safe!r}')",
        "bsdf = mat.node_tree.nodes.get('Principled BSDF')",
        f"bsdf.inputs['Roughness'].default_value = {value}",
    ]
    return {
        "action": "set_roughness",
        "mat_name": mat_name,
        "value": value,
        "statements": stmts,
    }


def set_emission(
    mat_name: str,
    color: tuple[float, float, float, float],
    strength: float,
) -> dict[str, Any]:
    """Configure emission colour and strength on a material."""
    safe = mat_name.replace('"', '\\"')
    r, g, b, a = color
    stmts = _preamble() + [
        f'mat = bpy.data.materials.get("{safe}")',
        f"if mat is None: raise ValueError('Material not found: {safe!r}')",
        "bsdf = mat.node_tree.nodes.get('Principled BSDF')",
        f"bsdf.inputs['Emission Color'].default_value = ({r}, {g}, {b}, {a})",
        f"bsdf.inputs['Emission Strength'].default_value = {strength}",
    ]
    return {
        "action": "set_emission",
        "mat_name": mat_name,
        "color": color,
        "strength": strength,
        "statements": stmts,
    }


def add_texture(mat_name: str, image_path: str) -> dict[str, Any]:
    """Load an image texture and connect it to the material's Base Color."""
    safe_mat = mat_name.replace('"', '\\"')
    safe_img = image_path.replace("\\", "\\\\").replace('"', '\\"')
    stmts = _preamble() + [
        f'mat = bpy.data.materials.get("{safe_mat}")',
        f"if mat is None: raise ValueError('Material not found: {safe_mat!r}')",
        "tree = mat.node_tree",
        "nodes = tree.nodes",
        "links = tree.links",
        f'img = bpy.data.images.load("{safe_img}")',
        "tex_node = nodes.new(type='ShaderNodeTexImage')",
        "tex_node.image = img",
        "bsdf = nodes.get('Principled BSDF')",
        "links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])",
    ]
    return {
        "action": "add_texture",
        "mat_name": mat_name,
        "image_path": image_path,
        "statements": stmts,
    }


def list_materials() -> dict[str, Any]:
    """Print all material names in the current .blend file as JSON."""
    stmts = _preamble() + [
        "import json",
        "names = [m.name for m in bpy.data.materials]",
        "print(json.dumps(names))",
    ]
    return {
        "action": "list_materials",
        "statements": stmts,
    }
