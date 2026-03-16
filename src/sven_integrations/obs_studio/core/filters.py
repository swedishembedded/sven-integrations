"""OBS filter management — registry, project-level operations, and validation."""

from __future__ import annotations

from typing import Any

from ..project import ObsSetup

# ---------------------------------------------------------------------------
# Filter registry
# Each entry: {description, category, params: {name: {type, default, range?}}}

FILTER_REGISTRY: dict[str, dict[str, Any]] = {
    "color_correction": {
        "description": "Adjust brightness, contrast, saturation and gamma",
        "category": "video",
        "obs_id": "color_filter",
        "params": {
            "brightness": {"type": "float", "default": 0.0, "range": (-1.0, 1.0)},
            "contrast": {"type": "float", "default": 0.0, "range": (-2.0, 2.0)},
            "saturation": {"type": "float", "default": 0.0, "range": (-1.0, 1.0)},
            "gamma": {"type": "float", "default": 0.0, "range": (-1.0, 1.0)},
        },
    },
    "chroma_key": {
        "description": "Remove a colour via chroma-key compositing",
        "category": "video",
        "obs_id": "chroma_key_filter_v2",
        "params": {
            "color": {"type": "int", "default": 0x00FF00, "range": (0, 0xFFFFFF)},
            "similarity": {"type": "int", "default": 80, "range": (1, 1000)},
            "smoothness": {"type": "int", "default": 50, "range": (1, 1000)},
        },
    },
    "luma_key": {
        "description": "Key out based on luminance values",
        "category": "video",
        "obs_id": "luma_key_filter_v2",
        "params": {
            "luma_max": {"type": "float", "default": 1.0, "range": (0.0, 1.0)},
            "luma_min": {"type": "float", "default": 0.0, "range": (0.0, 1.0)},
        },
    },
    "noise_suppress": {
        "description": "Reduce background noise in an audio source",
        "category": "audio",
        "obs_id": "noise_suppress_filter_v2",
        "params": {
            "suppress_level": {"type": "int", "default": -30, "range": (-60, 0)},
        },
    },
    "noise_gate": {
        "description": "Silence audio below an open threshold",
        "category": "audio",
        "obs_id": "noise_gate_filter",
        "params": {
            "open_threshold": {"type": "float", "default": -26.0, "range": (-96.0, 0.0)},
            "close_threshold": {"type": "float", "default": -32.0, "range": (-96.0, 0.0)},
            "attack_time": {"type": "int", "default": 25, "range": (1, 10000)},
            "hold_time": {"type": "int", "default": 200, "range": (1, 10000)},
            "release_time": {"type": "int", "default": 150, "range": (1, 10000)},
        },
    },
    "gain": {
        "description": "Apply a fixed decibel gain to an audio source",
        "category": "audio",
        "obs_id": "gain_filter",
        "params": {
            "db": {"type": "float", "default": 0.0, "range": (-30.0, 30.0)},
        },
    },
    "compressor": {
        "description": "Dynamic range compressor for audio",
        "category": "audio",
        "obs_id": "compressor_filter",
        "params": {
            "ratio": {"type": "float", "default": 4.0, "range": (1.0, 32.0)},
            "threshold": {"type": "float", "default": -18.0, "range": (-60.0, 0.0)},
            "attack": {"type": "int", "default": 6, "range": (1, 1000)},
            "release": {"type": "int", "default": 60, "range": (1, 1000)},
            "output_gain": {"type": "float", "default": 0.0, "range": (-32.0, 32.0)},
        },
    },
    "limiter": {
        "description": "Hard limiter to prevent clipping",
        "category": "audio",
        "obs_id": "limiter_filter",
        "params": {
            "threshold": {"type": "float", "default": -6.0, "range": (-60.0, 0.0)},
            "release": {"type": "int", "default": 60, "range": (1, 1000)},
        },
    },
}


# ---------------------------------------------------------------------------
# Helpers


def _source_filters(project: ObsSetup, source_name: str) -> list[dict[str, Any]]:
    """Return the mutable filters list for *source_name*, creating it if absent."""
    sources_data: dict[str, Any] = project.data.setdefault(  # type: ignore[attr-defined]
        "source_filters", {}
    )
    return sources_data.setdefault(source_name, [])


def validate_filter_params(filter_type: str, params: dict[str, Any]) -> dict[str, Any]:
    """Return a dict with ``valid`` (bool) and ``errors`` (list[str])."""
    errors: list[str] = []
    spec = FILTER_REGISTRY.get(filter_type)
    if spec is None:
        return {
            "valid": False,
            "errors": [f"Unknown filter type {filter_type!r}"],
        }
    for key, val in params.items():
        pspec = spec["params"].get(key)
        if pspec is None:
            errors.append(f"Unknown parameter {key!r} for filter {filter_type!r}")
            continue
        rng = pspec.get("range")
        if rng is not None:
            lo, hi = rng
            try:
                num = float(val)
                if not (lo <= num <= hi):
                    errors.append(
                        f"Parameter {key!r}={val} out of range [{lo}, {hi}]"
                    )
            except (TypeError, ValueError):
                errors.append(f"Parameter {key!r} must be numeric, got {val!r}")
    return {"valid": len(errors) == 0, "errors": errors}


# ---------------------------------------------------------------------------
# CRUD operations


def add_filter(
    project: ObsSetup,
    filter_type: str,
    source_name: str,
    name: str | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add a filter of *filter_type* to *source_name* on the project."""
    if filter_type not in FILTER_REGISTRY:
        raise ValueError(
            f"Unknown filter type {filter_type!r}. "
            f"Available: {sorted(FILTER_REGISTRY)}"
        )
    effective_params = params or {}
    validation = validate_filter_params(filter_type, effective_params)
    if not validation["valid"]:
        raise ValueError(
            f"Invalid filter params: {'; '.join(validation['errors'])}"
        )
    spec = FILTER_REGISTRY[filter_type]
    defaults = {k: v["default"] for k, v in spec["params"].items()}
    merged = {**defaults, **effective_params}

    entry: dict[str, Any] = {
        "filter_type": filter_type,
        "name": name or f"{filter_type}_{len(_source_filters(project, source_name))}",
        "source_name": source_name,
        "params": merged,
    }
    _source_filters(project, source_name).append(entry)
    return entry


def remove_filter(project: ObsSetup, source_name: str, filter_index: int) -> dict[str, Any]:
    """Remove the filter at *filter_index* from *source_name*."""
    flist = _source_filters(project, source_name)
    if filter_index < 0 or filter_index >= len(flist):
        raise IndexError(
            f"Filter index {filter_index} out of range for source {source_name!r}"
        )
    return flist.pop(filter_index)


def set_filter_param(
    project: ObsSetup,
    source_name: str,
    filter_index: int,
    param: str,
    value: Any,
) -> dict[str, Any]:
    """Update a single parameter on an existing filter."""
    flist = _source_filters(project, source_name)
    if filter_index < 0 or filter_index >= len(flist):
        raise IndexError(
            f"Filter index {filter_index} out of range for source {source_name!r}"
        )
    entry = flist[filter_index]
    validation = validate_filter_params(entry["filter_type"], {param: value})
    if not validation["valid"]:
        raise ValueError(f"Invalid param: {'; '.join(validation['errors'])}")
    entry["params"][param] = value
    return entry


def list_filters(project: ObsSetup, source_name: str) -> dict[str, Any]:
    """Return all filters registered for *source_name*."""
    flist = _source_filters(project, source_name)
    return {"source": source_name, "count": len(flist), "filters": list(flist)}


def list_available_filters(category: str | None = None) -> list[dict[str, Any]]:
    """Return filter registry entries, optionally filtered by *category*."""
    result = []
    for ftype, spec in FILTER_REGISTRY.items():
        if category is not None and spec.get("category") != category:
            continue
        result.append({
            "filter_type": ftype,
            "description": spec["description"],
            "category": spec["category"],
            "obs_id": spec["obs_id"],
            "params": list(spec["params"].keys()),
        })
    return result
