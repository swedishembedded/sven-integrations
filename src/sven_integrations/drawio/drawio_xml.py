"""mxGraph XML builder and parser for .drawio files."""

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET

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

    # Handle two common layouts:
    # 1. <mxGraphModel> wrapping <root> with <diagram> children (multi-page)
    # 2. <mxGraphModel> with a single <root> (single page embedded)
    if root.tag == "mxGraphModel":
        diagrams = root.findall("diagram")
        if diagrams:
            for diag in diagrams:
                page = _parse_diagram_element(diag)
                doc.pages.append(page)
        else:
            # Single-page format: root IS the model
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
    """Serialise a DrawioDocument back to drawio XML."""
    mx = ET.Element("mxGraphModel")
    mx.attrib.update(
        {
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
    )
    for page in diagram.pages:
        diag_el = ET.SubElement(mx, "diagram")
        diag_el.set("id", page.page_id)
        diag_el.set("name", page.name)
        model_el = ET.SubElement(diag_el, "mxGraphModel")
        root_el = ET.SubElement(model_el, "root")
        _root_cells(root_el)
        for cell in page.cells:
            root_el.append(_cell_to_element(cell))
    ET.indent(mx, space="  ")
    return ET.tostring(mx, encoding="unicode", xml_declaration=False)


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
    style_map = {
        "rectangle": "rounded=0;whiteSpace=wrap;html=1;",
        "rounded": "rounded=1;whiteSpace=wrap;html=1;",
        "ellipse": "ellipse;whiteSpace=wrap;html=1;",
        "diamond": "rhombus;whiteSpace=wrap;html=1;",
        "cylinder": "shape=mxgraph.flowchart.start_2;fillColor=#dae8fc;strokeColor=#6c8ebf;",
        "hexagon": "shape=hexagon;perimeter=hexagonPerimeter2;whiteSpace=wrap;html=1;",
        "parallelogram": "shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;",
    }
    base_style = style_map.get(shape_type, f"shape={shape_type};whiteSpace=wrap;html=1;")
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
    style_overrides: dict[str, str] | None = None,
) -> str:
    """Add an edge (connector) between two cells and return the edge_id."""
    base_style = "edgeStyle=orthogonalEdgeStyle;html=1;"
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


def remove_cell(diagram: DrawioDocument, page_idx: int, cell_id: str) -> bool:
    page = diagram.pages[page_idx]
    for i, cell in enumerate(page.cells):
        if cell.cell_id == cell_id:
            page.cells.pop(i)
            return True
    return False


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
