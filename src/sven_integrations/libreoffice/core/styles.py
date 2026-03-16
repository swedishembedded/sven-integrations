"""Style management for LibreOffice Writer documents — in-memory style registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ..project import OfficeDocument

# ---------------------------------------------------------------------------
# Constants

StyleFamily = Literal["paragraph", "character", "table", "page"]

BUILT_IN_STYLES: list[str] = [
    "Default Paragraph Style",
    "Heading 1",
    "Heading 2",
    "Heading 3",
    "Heading 4",
    "Heading 5",
    "Heading 6",
    "Body Text",
    "Title",
    "Subtitle",
    "List Paragraph",
    "Caption",
    "Preformatted Text",
]

ALLOWED_PROPERTIES: set[str] = {
    "font-name",
    "font-size",
    "font-weight",
    "font-style",
    "color",
    "background-color",
    "margin-top",
    "margin-bottom",
    "text-align",
    "line-spacing",
    "indent",
}

_VALID_FAMILIES: frozenset[str] = frozenset({"paragraph", "character", "table", "page"})


# ---------------------------------------------------------------------------
# Style dataclass

@dataclass
class StyleDefinition:
    """An in-memory style definition for a LibreOffice document."""

    name: str
    family: str
    parent_name: str | None
    properties: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "family": self.family,
            "parent_name": self.parent_name,
            "properties": dict(self.properties),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StyleDefinition":
        return cls(
            name=data["name"],
            family=data.get("family", "paragraph"),
            parent_name=data.get("parent_name"),
            properties={str(k): str(v) for k, v in data.get("properties", {}).items()},
        )


# ---------------------------------------------------------------------------
# Internal helpers

def _get_styles(doc: OfficeDocument) -> dict[str, dict[str, Any]]:
    """Return the mutable styles registry stored in ``doc.extra``."""
    return doc.extra.setdefault("styles", {})


def _validate_family(family: str) -> None:
    if family not in _VALID_FAMILIES:
        raise ValueError(
            f"Invalid style family {family!r}.  "
            f"Must be one of {sorted(_VALID_FAMILIES)}."
        )


def _filter_properties(props: dict[str, str]) -> dict[str, str]:
    """Strip properties not in :data:`ALLOWED_PROPERTIES` and return the rest."""
    return {k: v for k, v in props.items() if k in ALLOWED_PROPERTIES}


# ---------------------------------------------------------------------------
# Public API

def create_style(
    doc: OfficeDocument,
    name: str,
    family: str = "paragraph",
    parent: str | None = None,
    properties: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Create a new named style on the document.

    The style is stored in ``doc.extra["styles"]``.

    Raises :class:`ValueError` if a style with *name* already exists or if
    an unrecognised *family* is given.
    """
    _validate_family(family)
    styles = _get_styles(doc)
    if name in styles:
        raise ValueError(f"Style {name!r} already exists.  Use modify_style to update it.")

    filtered = _filter_properties(properties or {})
    style = StyleDefinition(name=name, family=family, parent_name=parent, properties=filtered)
    styles[name] = style.to_dict()
    doc.modified = True

    return {
        "action": "create_style",
        "style": style.to_dict(),
    }


def modify_style(
    doc: OfficeDocument,
    name: str,
    properties: dict[str, str],
    family: str | None = None,
    parent: str | None = None,
) -> dict[str, Any]:
    """Update properties (and optionally family / parent) of an existing style.

    Raises :class:`KeyError` if *name* does not exist.
    """
    styles = _get_styles(doc)
    if name not in styles:
        raise KeyError(f"Style {name!r} not found.")

    entry = styles[name]
    if family is not None:
        _validate_family(family)
        entry["family"] = family
    if parent is not None:
        entry["parent_name"] = parent

    existing_props: dict[str, str] = entry.get("properties", {})
    existing_props.update(_filter_properties(properties))
    entry["properties"] = existing_props
    doc.modified = True

    return {
        "action": "modify_style",
        "name": name,
        "style": entry,
    }


def remove_style(doc: OfficeDocument, name: str) -> dict[str, Any]:
    """Remove a style from the document.

    Raises :class:`KeyError` if *name* is not found.
    Raises :class:`ValueError` if attempting to remove a built-in style.
    """
    if name in BUILT_IN_STYLES:
        raise ValueError(
            f"Cannot remove built-in style {name!r}.  "
            "Only user-defined styles may be removed."
        )
    styles = _get_styles(doc)
    if name not in styles:
        raise KeyError(f"Style {name!r} not found.")
    removed = styles.pop(name)
    doc.modified = True
    return {
        "action": "remove_style",
        "name": name,
        "removed": removed,
    }


def list_styles(doc: OfficeDocument) -> dict[str, Any]:
    """Return all custom styles defined on the document."""
    styles = _get_styles(doc)
    return {
        "action": "list_styles",
        "count": len(styles),
        "styles": [StyleDefinition.from_dict(v).to_dict() for v in styles.values()],
    }


def get_style(doc: OfficeDocument, name: str) -> dict[str, Any]:
    """Retrieve a single style definition by name.

    Raises :class:`KeyError` if not found.
    """
    styles = _get_styles(doc)
    if name not in styles:
        raise KeyError(f"Style {name!r} not found.")
    return {
        "action": "get_style",
        "style": StyleDefinition.from_dict(styles[name]).to_dict(),
    }


def apply_style(
    doc: OfficeDocument,
    style_name: str,
    content_index: int,
) -> dict[str, Any]:
    """Apply a style to the Writer paragraph at *content_index*.

    The style must exist in the document's custom registry **or** be a
    built-in style name.  The applied style name is stored in
    ``doc.extra["applied_styles"]`` keyed by *content_index* for later
    serialisation.
    """
    styles = _get_styles(doc)
    if style_name not in styles and style_name not in BUILT_IN_STYLES:
        raise KeyError(
            f"Style {style_name!r} not found.  "
            "Create it first or use a built-in style name."
        )

    applied: dict[str, str] = doc.extra.setdefault("applied_styles", {})
    applied[str(content_index)] = style_name
    doc.modified = True

    return {
        "action": "apply_style",
        "style_name": style_name,
        "content_index": content_index,
    }
