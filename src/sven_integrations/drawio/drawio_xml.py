"""mxGraph XML builder and parser for .drawio files."""

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from .project import CellGeometry, DrawioCell, DrawioDocument, DrawioPage

# ---------------------------------------------------------------------------
# XML construction helpers
# ---------------------------------------------------------------------------


def _make_graph_model() -> ET.Element:
    attrs: dict[str, str] = {
        "dx": "1422",
        "dy": "762",
        "grid": "1",
        "gridSize": "10",
        "guides": "1",
        "tooltips": "1",
        "connect": "1",
        "arrows": "1",
        "fold": "1",
        "page": "1",
        "pageScale": "1",
        "pageWidth": "1169",
        "pageHeight": "827",
        "math": "0",
        "shadow": "0",
    }
    el = ET.Element("mxGraphModel")
    el.attrib.update(attrs)
    return el


def _root_cells(root_el: ET.Element) -> ET.Element:
    """Add mandatory id=0/1 cells and return the root element."""
    c0 = ET.SubElement(root_el, "mxCell")
    c0.set("id", "0")
    c1 = ET.SubElement(root_el, "mxCell")
    c1.set("id", "1")
    c1.set("parent", "0")
    return root_el


def _cell_to_element(cell: DrawioCell) -> ET.Element:
    el = ET.Element("mxCell")
    el.set("id", cell.cell_id)
    el.set("value", cell.value)
    el.set("style", cell.style)
    el.set("parent", "1")
    if cell.vertex:
        el.set("vertex", "1")
    if cell.edge:
        el.set("edge", "1")
    if cell.source_id:
        el.set("source", cell.source_id)
    if cell.target_id:
        el.set("target", cell.target_id)
    geo = ET.SubElement(el, "mxGeometry")
    if cell.edge:
        geo.set("relative", "1")
        geo.set("as", "geometry")
    else:
        geo.set("x", str(cell.geometry.x))
        geo.set("y", str(cell.geometry.y))
        geo.set("width", str(cell.geometry.width))
        geo.set("height", str(cell.geometry.height))
        geo.set("as", "geometry")
    return el


def _element_to_cell(el: ET.Element) -> DrawioCell | None:
    cell_id = el.get("id", "")
    if cell_id in ("0", "1"):
        return None
    geo_el = el.find("mxGeometry")
    geo = CellGeometry()
    if geo_el is not None:
        geo = CellGeometry(
            x=float(geo_el.get("x", 0)),
            y=float(geo_el.get("y", 0)),
            width=float(geo_el.get("width", 120)),
            height=float(geo_el.get("height", 60)),
        )
    return DrawioCell(
        cell_id=cell_id,
        value=el.get("value", ""),
        style=el.get("style", ""),
        vertex=el.get("vertex") == "1",
        edge=el.get("edge") == "1",
        source_id=el.get("source") or None,
        target_id=el.get("target") or None,
        geometry=geo,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def new_diagram(name: str = "Page-1") -> str:
    """Return a minimal empty drawio XML string for a single named page."""
    mx = _make_graph_model()
    diagram = ET.SubElement(mx, "diagram")
    diagram.set("id", str(uuid.uuid4()))
    diagram.set("name", name)
    root_el = ET.SubElement(diagram, "mxGraphModel")
    root_el.attrib.update(
        {
            "dx": "1422",
            "dy": "762",
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": "1169",
            "pageHeight": "827",
            "math": "0",
            "shadow": "0",
        }
    )
    _root_cells(ET.SubElement(root_el, "root"))
    ET.indent(mx, space="  ")
    return ET.tostring(mx, encoding="unicode", xml_declaration=False)


def parse_diagram(xml_str: str) -> DrawioDocument:
    """Parse a drawio XML string into a DrawioDocument."""
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid drawio XML: {exc}") from exc

    doc = DrawioDocument()

    # Handle layouts:
    # 1. <mxfile> (standard) — diagram children, each with mxGraphModel > root
    # 2. <mxGraphModel> (legacy) — diagram children or single root
    if root.tag == "mxfile":
        for diag in root.findall("diagram"):
            page = _parse_diagram_element(diag)
            doc.pages.append(page)
    elif root.tag == "mxGraphModel":
        diagrams = root.findall("diagram")
        if diagrams:
            for diag in diagrams:
                page = _parse_diagram_element(diag)
                doc.pages.append(page)
        else:
            page = _parse_root_element(root.find("root"), name="Page-1", page_id=str(uuid.uuid4()))
            doc.pages.append(page)
    else:
        raise ValueError(f"Unexpected root element: {root.tag!r}")

    return doc


def _parse_diagram_element(diag: ET.Element) -> DrawioPage:
    page_id = diag.get("id", str(uuid.uuid4()))
    name = diag.get("name", "Page")
    model = diag.find("mxGraphModel")
    root_el = model.find("root") if model is not None else diag.find("root")
    return _parse_root_element(root_el, name=name, page_id=page_id)


def _parse_root_element(
    root_el: ET.Element | None, *, name: str, page_id: str
) -> DrawioPage:
    cells: list[DrawioCell] = []
    if root_el is not None:
        for el in root_el.findall("mxCell"):
            cell = _element_to_cell(el)
            if cell is not None:
                cells.append(cell)
    return DrawioPage(page_id=page_id, name=name, cells=cells)


def render_xml(diagram: DrawioDocument) -> str:
    """Serialise a DrawioDocument back to drawio XML.

    Uses mxfile format: mxfile > diagram > mxGraphModel > root.
    Shapes include fillColor and strokeColor so they are visible in Draw.io.
    """
    model_attrs = {
        "dx": "1422",
        "dy": "762",
        "grid": "1",
        "gridSize": "10",
        "guides": "1",
        "tooltips": "1",
        "connect": "1",
        "arrows": "1",
        "fold": "1",
        "page": "1",
        "pageScale": "1",
        "pageWidth": "1169",
        "pageHeight": "827",
        "math": "0",
        "shadow": "0",
    }
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    mxfile = ET.Element("mxfile")
    mxfile.attrib.update(
        {
            "host": "sven-integrations",
            "modified": modified,
            "agent": "sven-integrations-drawio",
            "etag": str(uuid.uuid4())[:8],
            "version": "24.0.0",
            "type": "device",
            "compressed": "false",
            "pages": str(len(diagram.pages)),
        }
    )
    for page in diagram.pages:
        diag_el = ET.SubElement(mxfile, "diagram")
        diag_el.set("id", page.page_id)
        diag_el.set("name", page.name)
        model_el = ET.SubElement(diag_el, "mxGraphModel")
        model_el.attrib.update(model_attrs)
        root_el = ET.SubElement(model_el, "root")
        _root_cells(root_el)
        for cell in page.cells:
            root_el.append(_cell_to_element(cell))
    ET.indent(mxfile, space="  ")
    xml = ET.tostring(mxfile, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml


SHAPE_TYPES: dict[str, str] = {
    "rectangle": "Standard box",
    "rounded": "Box with rounded corners",
    "ellipse": "Oval / circle",
    "rhombus": "Diamond (for decisions)",
    "diamond": "Diamond (alias for rhombus)",
    "hexagon": "Hexagonal shape",
    "cylinder": "Database / storage cylinder",
    "cloud": "Cloud shape",
    "parallelogram": "Parallelogram (input/output)",
    "triangle": "Triangle",
    "process": "Thick-bordered process box",
    "document": "Curled document shape",
    "callout": "Speech-bubble callout",
    "note": "Folded note shape",
    "actor": "Stick-figure actor",
    "text": "Plain text (no border)",
}

EDGE_STYLE_PRESETS: dict[str, str] = {
    "straight": "edgeStyle=none;html=1;",
    "orthogonal": "edgeStyle=orthogonalEdgeStyle;html=1;",
    "curved": "edgeStyle=orthogonalEdgeStyle;curved=1;rounded=1;html=1;",
    "entity-relation": "edgeStyle=entityRelationEdgeStyle;html=1;",
}


def add_shape(
    diagram: DrawioDocument,
    page_idx: int,
    shape_type: str,
    label: str,
    x: float,
    y: float,
    w: float,
    h: float,
    style_overrides: dict[str, str] | None = None,
) -> str:
    """Add a shape cell to a page and return the new cell_id."""
    # fillColor and strokeColor are required for shapes to be visible in Draw.io
    style_map = {
        "rectangle": "rounded=0;whiteSpace=wrap;html=1;fillColor=#DAE8FC;strokeColor=#6C8EBF;",
        "rounded": "rounded=1;whiteSpace=wrap;html=1;fillColor=#DAE8FC;strokeColor=#6C8EBF;",
        "ellipse": "ellipse;whiteSpace=wrap;html=1;fillColor=#D5E8D4;strokeColor=#82B366;",
        "rhombus": "rhombus;whiteSpace=wrap;html=1;fillColor=#FFF2CC;strokeColor=#D6B656;",
        "diamond": "rhombus;whiteSpace=wrap;html=1;fillColor=#FFF2CC;strokeColor=#D6B656;",
        "cylinder": "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#DAE8FC;strokeColor=#6C8EBF;",
        "hexagon": "shape=hexagon;perimeter=hexagonPerimeter2;whiteSpace=wrap;html=1;fillColor=#DAE8FC;strokeColor=#6C8EBF;",
        "parallelogram": "shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;fillColor=#DAE8FC;strokeColor=#6C8EBF;",
        "process": "shape=process;whiteSpace=wrap;html=1;backgroundOutline=1;fillColor=#DAE8FC;strokeColor=#6C8EBF;",
        "document": "shape=document;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=0.27;fillColor=#FFF2CC;strokeColor=#D6B656;",
        "cloud": "ellipse;shape=cloud;whiteSpace=wrap;html=1;fillColor=#E1D5E7;strokeColor=#9673A6;",
        "triangle": "triangle;whiteSpace=wrap;html=1;fillColor=#DAE8FC;strokeColor=#6C8EBF;",
        "callout": "shape=callout;whiteSpace=wrap;html=1;perimeter=calloutPerimeter;size=30;position=0.5;fillColor=#DAE8FC;strokeColor=#6C8EBF;",
        "note": "shape=note;whiteSpace=wrap;html=1;backgroundOutline=1;size=15;fillColor=#FFF2CC;strokeColor=#D6B656;",
        "actor": "shape=mxgraph.basic.person;whiteSpace=wrap;html=1;fillColor=#DAE8FC;strokeColor=#6C8EBF;",
        "text": "text;html=1;align=center;verticalAlign=middle;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;",
    }
    base_style = style_map.get(
        shape_type, f"shape={shape_type};whiteSpace=wrap;html=1;fillColor=#DAE8FC;strokeColor=#6C8EBF;"
    )
    if style_overrides:
        extra = ";".join(f"{k}={v}" for k, v in style_overrides.items())
        base_style = base_style.rstrip(";") + ";" + extra + ";"
    cell_id = str(uuid.uuid4())
    cell = DrawioCell(
        cell_id=cell_id,
        value=label,
        style=base_style,
        vertex=True,
        edge=False,
        geometry=CellGeometry(x=x, y=y, width=w, height=h),
    )
    diagram.add_cell(page_idx, cell)
    return cell_id


def add_connector(
    diagram: DrawioDocument,
    page_idx: int,
    src_id: str,
    tgt_id: str,
    label: str = "",
    edge_style: str = "orthogonal",
    style_overrides: dict[str, str] | None = None,
) -> str:
    """Add an edge (connector) between two cells and return the edge_id.

    edge_style: preset name (straight/orthogonal/curved/entity-relation) or raw style string.
    """
    base_style = EDGE_STYLE_PRESETS.get(edge_style, edge_style if ";" in edge_style else f"{edge_style};")
    if style_overrides:
        extra = ";".join(f"{k}={v}" for k, v in style_overrides.items())
        base_style = base_style.rstrip(";") + ";" + extra + ";"
    edge_id = str(uuid.uuid4())
    cell = DrawioCell(
        cell_id=edge_id,
        value=label,
        style=base_style,
        vertex=False,
        edge=True,
        source_id=src_id,
        target_id=tgt_id,
        geometry=CellGeometry(x=0, y=0, width=0, height=0),
    )
    diagram.add_cell(page_idx, cell)
    return edge_id


def move_cell(
    diagram: DrawioDocument, page_idx: int, cell_id: str, x: float, y: float
) -> bool:
    """Move a vertex cell to a new position. Returns True if found."""
    page = diagram.pages[page_idx]
    for cell in page.cells:
        if cell.cell_id == cell_id:
            cell.geometry.x = x
            cell.geometry.y = y
            return True
    return False


def resize_cell(
    diagram: DrawioDocument, page_idx: int, cell_id: str, width: float, height: float
) -> bool:
    """Resize a vertex cell. Returns True if found."""
    page = diagram.pages[page_idx]
    for cell in page.cells:
        if cell.cell_id == cell_id:
            cell.geometry.width = width
            cell.geometry.height = height
            return True
    return False


def remove_cell(diagram: DrawioDocument, page_idx: int, cell_id: str) -> bool:
    """Remove a cell by ID. Also removes any edges connected to it."""
    page = diagram.pages[page_idx]
    original_len = len(page.cells)
    page.cells = [
        c for c in page.cells
        if c.cell_id != cell_id
        and c.source_id != cell_id
        and c.target_id != cell_id
    ]
    return len(page.cells) < original_len


def update_cell_label(
    diagram: DrawioDocument, page_idx: int, cell_id: str, label: str
) -> bool:
    page = diagram.pages[page_idx]
    for cell in page.cells:
        if cell.cell_id == cell_id:
            cell.value = label
            return True
    return False


def update_cell_style(
    diagram: DrawioDocument,
    page_idx: int,
    cell_id: str,
    style_updates: dict[str, str],
) -> bool:
    """Merge style_updates into the cell's existing style string."""
    page = diagram.pages[page_idx]
    for cell in page.cells:
        if cell.cell_id == cell_id:
            existing = _parse_style(cell.style)
            existing.update(style_updates)
            cell.style = _format_style(existing)
            return True
    return False


def render_svg(diagram: DrawioDocument, page_idx: int = 0, padding: float = 20.0) -> str:
    """Render a DrawioDocument page to a standalone SVG string (no external tools required).

    Supports rectangle, rounded, ellipse, rhombus/diamond, triangle shapes and
    orthogonal connectors with arrowheads and labels.
    """
    if not diagram.pages:
        raise ValueError("Document has no pages")
    page = diagram.pages[page_idx]

    cell_map: dict[str, DrawioCell] = {c.cell_id: c for c in page.cells}

    vertices = [c for c in page.cells if c.vertex]
    edges = [c for c in page.cells if c.edge]

    # Calculate viewBox
    if vertices:
        xs = [c.geometry.x for c in vertices]
        ys = [c.geometry.y for c in vertices]
        x2s = [c.geometry.x + c.geometry.width for c in vertices]
        y2s = [c.geometry.y + c.geometry.height for c in vertices]
        min_x, min_y = min(xs), min(ys)
        max_x, max_y = max(x2s), max(y2s)
    else:
        min_x, min_y, max_x, max_y = 0.0, 0.0, 400.0, 300.0

    vb_x = min_x - padding
    vb_y = min_y - padding
    vb_w = max_x - min_x + 2 * padding
    vb_h = max_y - min_y + 2 * padding

    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{vb_x:.1f} {vb_y:.1f} {vb_w:.1f} {vb_h:.1f}" '
        f'width="{vb_w:.0f}" height="{vb_h:.0f}">'
    )

    # Defs: arrowhead marker
    lines.append("  <defs>")
    lines.append(
        '    <marker id="arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">'
    )
    lines.append('      <polygon points="0 0, 10 3.5, 0 7" fill="#555"/>')
    lines.append("    </marker>")
    lines.append("  </defs>")

    # Background
    lines.append(f'  <rect x="{vb_x:.1f}" y="{vb_y:.1f}" width="{vb_w:.1f}" height="{vb_h:.1f}" fill="white"/>')

    # Draw edges first (behind shapes)
    for cell in edges:
        src = cell_map.get(cell.source_id or "")
        tgt = cell_map.get(cell.target_id or "")
        if src is None or tgt is None:
            continue
        sx = src.geometry.x + src.geometry.width / 2
        sy = src.geometry.y + src.geometry.height / 2
        tx = tgt.geometry.x + tgt.geometry.width / 2
        ty = tgt.geometry.y + tgt.geometry.height / 2
        # Simple line; shorten to edge of target box
        dx, dy = tx - sx, ty - sy
        length = (dx * dx + dy * dy) ** 0.5
        if length > 0:
            ux, uy = dx / length, dy / length
            # Shorten at target side by ~half height
            shrink = min(tgt.geometry.height / 2, tgt.geometry.width / 2) * 0.9
            ex = tx - ux * shrink
            ey = ty - uy * shrink
        else:
            ex, ey = tx, ty
        lines.append(
            f'  <line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" '
            f'stroke="#555" stroke-width="1.5" marker-end="url(#arrow)"/>'
        )
        if cell.value:
            mx_, my_ = (sx + tx) / 2, (sy + ty) / 2
            lines.append(
                f'  <text x="{mx_:.1f}" y="{my_:.1f}" text-anchor="middle" '
                f'dominant-baseline="middle" font-family="Arial,sans-serif" '
                f'font-size="11" fill="#333" '
                f'style="background:white">{_xml_escape(cell.value)}</text>'
            )

    # Draw vertices
    for cell in vertices:
        style = _parse_style(cell.style)
        fill = style.get("fillColor", "#DAE8FC")
        stroke = style.get("strokeColor", "#6C8EBF")
        x, y, w, h = cell.geometry.x, cell.geometry.y, cell.geometry.width, cell.geometry.height

        shape_key = _detect_shape(cell.style)

        if shape_key == "ellipse":
            cx, cy, rx, ry = x + w / 2, y + h / 2, w / 2, h / 2
            lines.append(
                f'  <ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
            )
        elif shape_key in ("rhombus", "diamond"):
            pts = f"{x + w/2:.1f},{y:.1f} {x + w:.1f},{y + h/2:.1f} {x + w/2:.1f},{y + h:.1f} {x:.1f},{y + h/2:.1f}"
            lines.append(
                f'  <polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
            )
        elif shape_key == "triangle":
            pts = f"{x + w/2:.1f},{y:.1f} {x + w:.1f},{y + h:.1f} {x:.1f},{y + h:.1f}"
            lines.append(
                f'  <polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
            )
        elif shape_key == "rounded":
            lines.append(
                f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                f'rx="8" ry="8" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
            )
        else:
            lines.append(
                f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
            )

        # Label
        if cell.value:
            font_size = min(14, max(9, int(h * 0.22)))
            lines.append(
                f'  <text x="{x + w/2:.1f}" y="{y + h/2:.1f}" text-anchor="middle" '
                f'dominant-baseline="middle" font-family="Arial,sans-serif" '
                f'font-size="{font_size}" fill="#333">{_xml_escape(cell.value)}</text>'
            )

    lines.append("</svg>")
    return "\n".join(lines)


def _detect_shape(style_str: str) -> str:
    """Infer shape type keyword from a style string."""
    s = style_str.lower()
    if "ellipse" in s or "cloud" in s:
        return "ellipse"
    if "rhombus" in s or "diamond" in s:
        return "rhombus"
    if "triangle" in s:
        return "triangle"
    if "rounded=1" in s:
        return "rounded"
    return "rectangle"


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _parse_style(style_str: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in style_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            result[k.strip()] = v.strip()
        elif part:
            result[part] = ""
    return result


def _format_style(style_dict: dict[str, str]) -> str:
    parts = []
    for k, v in style_dict.items():
        if v:
            parts.append(f"{k}={v}")
        else:
            parts.append(k)
    return ";".join(parts) + (";" if parts else "")
