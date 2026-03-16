"""Shotcut / MLT filter XML builders."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

# ---------------------------------------------------------------------------
# Generic builder


def build_filter_element(filter_name: str, params: dict[str, Any]) -> ET.Element:
    """Create an MLT <filter> element for *filter_name*.

    Parameters
    ----------
    filter_name:
        The ``mlt_service`` identifier (e.g. ``"brightness"``, ``"frei0r.colorhalftone"``).
    params:
        Mapping of property name → value.
    """
    filt = ET.Element("filter")
    _prop(filt, "mlt_service", filter_name)
    for key, value in params.items():
        _prop(filt, key, str(value))
    return filt


def _prop(parent: ET.Element, name: str, value: str) -> ET.Element:
    elem = ET.SubElement(parent, "property", attrib={"name": name})
    elem.text = value
    return elem


# ---------------------------------------------------------------------------
# Specific filter helpers


def brightness_filter(level: float) -> ET.Element:
    """Create a brightness filter (0.0–2.0; 1.0 = unchanged)."""
    return build_filter_element("brightness", {"level": level})


def contrast_filter(level: float) -> ET.Element:
    """Create a contrast filter (0.0–2.0; 1.0 = unchanged)."""
    return build_filter_element("contrast", {"level": level})


def saturation_filter(level: float) -> ET.Element:
    """Create a saturation filter via the ``avfilter.eq`` service."""
    return build_filter_element("avfilter.eq", {"saturation": level})


def blur_filter(radius: float) -> ET.Element:
    """Create a Gaussian blur filter (radius in pixels)."""
    return build_filter_element("avfilter.gblur", {"sigma": radius})


def fade_in_filter(duration_frames: int) -> ET.Element:
    """Create a video fade-in filter."""
    filt = ET.Element("filter")
    _prop(filt, "mlt_service", "brightness")
    _prop(filt, "start", "0")
    _prop(filt, "end", "1")
    filt.set("out", str(duration_frames - 1))
    return filt


def fade_out_filter(duration_frames: int) -> ET.Element:
    """Create a video fade-out filter."""
    filt = ET.Element("filter")
    _prop(filt, "mlt_service", "brightness")
    _prop(filt, "start", "1")
    _prop(filt, "end", "0")
    filt.set("in", "0")
    filt.set("out", str(duration_frames - 1))
    return filt


def luma_filter(file: str | None = None) -> ET.Element:
    """Create a luma transition/wipe filter.

    *file* is an optional path to a luma wipe image.
    """
    params: dict[str, Any] = {}
    if file:
        params["resource"] = file
    return build_filter_element("luma", params)


def color_grading_filter(lift: float, gamma: float, gain: float) -> ET.Element:
    """Create a colour grading filter using the ``lift_gamma_gain`` service."""
    return build_filter_element(
        "lift_gamma_gain",
        {
            "lift_r": lift,
            "lift_g": lift,
            "lift_b": lift,
            "gamma_r": gamma,
            "gamma_g": gamma,
            "gamma_b": gamma,
            "gain_r": gain,
            "gain_g": gain,
            "gain_b": gain,
        },
    )


# ---------------------------------------------------------------------------
# Attaching filters to clips


def attach_filter_to_clip(clip_elem: ET.Element, filter_elem: ET.Element) -> None:
    """Insert a <filter> element inside a clip/producer element."""
    clip_elem.append(filter_elem)
