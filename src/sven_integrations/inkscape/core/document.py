"""Document profile definitions and document-level operations.

Provides pre-built canvas profiles, document creation, SVG serialisation,
and canvas size helpers for the Inkscape harness.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

from ..project import InkscapeProject, SvgElement

_SVG_NS = "http://www.w3.org/2000/svg"

# Register namespace so ET produces clean prefixes (svg:*) instead of ns0:*
ET.register_namespace("svg", _SVG_NS)


@dataclass
class DocumentProfile:
    """Named canvas preset with fixed dimensions."""

    name: str
    width_mm: float
    height_mm: float
    description: str


DOCUMENT_PROFILES: dict[str, DocumentProfile] = {
    "a4_portrait": DocumentProfile(
        name="A4 Portrait",
        width_mm=210.0,
        height_mm=297.0,
        description="ISO A4 portrait (210×297 mm)",
    ),
    "a4_landscape": DocumentProfile(
        name="A4 Landscape",
        width_mm=297.0,
        height_mm=210.0,
        description="ISO A4 landscape (297×210 mm)",
    ),
    "letter": DocumentProfile(
        name="US Letter",
        width_mm=215.9,
        height_mm=279.4,
        description="US Letter portrait (215.9×279.4 mm)",
    ),
    "hd_1080p": DocumentProfile(
        name="HD 1080p",
        width_mm=1920.0,
        height_mm=1080.0,
        description="Full HD 16:9 (1920×1080 px)",
    ),
    "hd_4k": DocumentProfile(
        name="4K UHD",
        width_mm=3840.0,
        height_mm=2160.0,
        description="4K UHD 16:9 (3840×2160 px)",
    ),
    "square_1000": DocumentProfile(
        name="Square 1000",
        width_mm=1000.0,
        height_mm=1000.0,
        description="1000×1000 square canvas",
    ),
    "social_post": DocumentProfile(
        name="Social Post",
        width_mm=1080.0,
        height_mm=1080.0,
        description="Social media post 1:1 (1080×1080 px)",
    ),
    "social_story": DocumentProfile(
        name="Social Story",
        width_mm=1080.0,
        height_mm=1920.0,
        description="Social media story 9:16 (1080×1920 px)",
    ),
    "icon_64": DocumentProfile(
        name="Icon 64",
        width_mm=64.0,
        height_mm=64.0,
        description="App icon 64×64 px",
    ),
    "icon_256": DocumentProfile(
        name="Icon 256",
        width_mm=256.0,
        height_mm=256.0,
        description="App icon 256×256 px",
    ),
}


def new_document(
    name: str,
    width_mm: float,
    height_mm: float,
    units: str = "mm",
    background: str = "white",
) -> InkscapeProject:
    """Create a fresh :class:`InkscapeProject` with the given canvas properties.

    Parameters
    ----------
    name:
        Human-readable document name stored in ``project.data``.
    width_mm:
        Canvas width (in *units*; the field name ``_mm`` is kept for API
        consistency even when units are pixels).
    height_mm:
        Canvas height.
    units:
        Unit hint stored alongside the document (``"mm"``, ``"px"``, etc.).
    background:
        CSS colour for the background fill rect, or ``"none"`` to omit it.
    """
    proj = InkscapeProject(
        svg_path=None,
        width_mm=float(width_mm),
        height_mm=float(height_mm),
        viewbox=(0.0, 0.0, float(width_mm), float(height_mm)),
    )
    proj.data["name"] = name
    proj.data["units"] = units
    proj.data["background"] = background
    return proj


def get_document_info(project: InkscapeProject) -> dict[str, Any]:
    """Return a summary dict describing the current document state.

    Returns
    -------
    dict with keys: name, width_mm, height_mm, viewbox, element_count,
    page_layer_count.
    """
    layers: list[dict[str, Any]] = project.data.get("layers", [])
    return {
        "name": project.data.get("name", ""),
        "width_mm": project.width_mm,
        "height_mm": project.height_mm,
        "viewbox": list(project.viewbox),
        "element_count": len(project.elements),
        "page_layer_count": len(layers),
    }


def set_canvas_size(
    project: InkscapeProject,
    width_mm: float,
    height_mm: float,
) -> dict[str, Any]:
    """Resize the canvas, preserving the viewbox origin.

    The viewbox width and height are updated to match the new canvas
    dimensions; the origin (x, y) is kept unchanged.
    """
    ox, oy = project.viewbox[0], project.viewbox[1]
    project.width_mm = float(width_mm)
    project.height_mm = float(height_mm)
    project.viewbox = (ox, oy, float(width_mm), float(height_mm))
    return {
        "action": "set_canvas_size",
        "width_mm": width_mm,
        "height_mm": height_mm,
        "viewbox": list(project.viewbox),
    }


def list_profiles() -> list[dict[str, Any]]:
    """Return all built-in :data:`DOCUMENT_PROFILES` as a list of dicts."""
    return [
        {
            "key": key,
            "name": prof.name,
            "width_mm": prof.width_mm,
            "height_mm": prof.height_mm,
            "description": prof.description,
        }
        for key, prof in DOCUMENT_PROFILES.items()
    ]


def save_svg(project: InkscapeProject, path: str) -> dict[str, Any]:
    """Generate minimal SVG XML from *project* and write it to *path*.

    Elements are serialised based on their ``tag`` field:
    ``rect``, ``circle``, ``ellipse``, ``line``, ``polygon``, ``path``,
    ``text``, and ``g`` are all handled.  Shape-specific attributes are
    taken from ``element.attrs``.  Style properties from ``element.style``
    are written as the SVG ``style`` attribute.

    Uses :mod:`xml.etree.ElementTree` — no third-party dependencies.
    Produces valid SVG viewable in browsers and Inkscape.
    """
    vb = project.viewbox
    units = project.data.get("units", "mm")
    w_str = f"{project.width_mm}{units}"
    h_str = f"{project.height_mm}{units}"

    root = ET.Element(
        f"{{{_SVG_NS}}}svg",
        {
            "xmlns": _SVG_NS,
            "width": w_str,
            "height": h_str,
            "viewBox": f"{vb[0]} {vb[1]} {vb[2]} {vb[3]}",
            "version": "1.1",
        },
    )

    background = project.data.get("background", "white")
    if background and background.lower() not in ("none", "transparent"):
        ET.SubElement(
            root,
            f"{{{_SVG_NS}}}rect",
            {
                "x": str(vb[0]),
                "y": str(vb[1]),
                "width": str(vb[2] - vb[0]),
                "height": str(vb[3] - vb[1]),
                "fill": background,
            },
        )

    for elem in project.elements:
        _append_svg_element(root, elem)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="unicode", xml_declaration=True)

    return {
        "action": "save_svg",
        "path": path,
        "element_count": len(project.elements),
        "ok": True,
    }


def _append_svg_element(parent: ET.Element, elem: SvgElement) -> ET.Element:
    """Append a single SVG element node to *parent* and return it."""
    attrib: dict[str, str] = {}

    # Shape-specific geometric attributes (exclude internal keys)
    for k, v in elem.attrs.items():
        if k == "_text_content":
            continue
        attrib[str(k)] = str(v)

    # id (omit inkscape:label to avoid xmlns; id is sufficient for reference)
    if elem.element_id:
        attrib["id"] = elem.element_id

    # Build inline style: style string takes precedence; fall back to
    # separate fill/stroke fields when no style string is set.
    if elem.style:
        attrib["style"] = elem.style
    else:
        parts: list[str] = []
        if elem.fill and elem.fill != "none":
            parts.append(f"fill:{elem.fill}")
        if elem.stroke and elem.stroke != "none":
            parts.append(f"stroke:{elem.stroke}")
        if parts:
            attrib["style"] = ";".join(parts)

    if elem.transform:
        attrib["transform"] = elem.transform

    tag_name = elem.tag if ":" in elem.tag or "{" in elem.tag else f"{{{_SVG_NS}}}{elem.tag}"
    node = ET.SubElement(parent, tag_name, attrib)

    # text content
    if elem.tag == "text" and elem.attrs.get("_text_content"):
        node.text = str(elem.attrs["_text_content"])

    return node
