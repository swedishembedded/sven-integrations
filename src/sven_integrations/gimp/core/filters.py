"""Image filter functions for the GIMP harness.

Each function produces a result dict with a ``"script"`` key containing the
Script-Fu expression that applies the filter to the active drawable of the
topmost image.
"""

from __future__ import annotations

from typing import Any

_ACTIVE = (
    "(let* ((image (car (gimp-image-list))) "
    "(drawable (car (gimp-image-get-active-drawable image))))"
)


def _wrap(inner: str) -> str:
    """Wrap *inner* in the standard image/drawable binding form."""
    return f"{_ACTIVE} {inner})"


def apply_blur(radius: float) -> dict[str, Any]:
    """Apply a Gaussian blur with the given *radius* in pixels."""
    diameter = max(1, int(radius * 2))
    # plug-in-gauss requires odd kernel sizes
    ksize = diameter | 1
    script = _wrap(
        f"(plug-in-gauss RUN-NONINTERACTIVE image drawable {ksize} {ksize} 0)"
    )
    return {"action": "apply_blur", "radius": radius, "script": script}


def apply_sharpen(amount: float) -> dict[str, Any]:
    """Apply a simple sharpen effect.

    *amount* maps to GIMP's sharpen strength (1–99).
    """
    strength = max(1, min(99, int(amount)))
    script = _wrap(
        f"(plug-in-sharpen RUN-NONINTERACTIVE image drawable {strength})"
    )
    return {"action": "apply_sharpen", "amount": amount, "script": script}


def apply_unsharp_mask(
    radius: float,
    amount: float,
    threshold: int,
) -> dict[str, Any]:
    """Apply an unsharp mask filter.

    Parameters
    ----------
    radius:
        Gaussian blur radius in pixels (e.g. 2.0–10.0).
    amount:
        Strength of the sharpening effect (e.g. 0.1–1.0).
    threshold:
        Minimum tonal difference before sharpening is applied (0–255).
    """
    script = _wrap(
        f"(plug-in-unsharp-mask RUN-NONINTERACTIVE image drawable "
        f"{radius} {amount} {threshold})"
    )
    return {
        "action": "apply_unsharp_mask",
        "radius": radius,
        "amount": amount,
        "threshold": threshold,
        "script": script,
    }


def apply_curves(
    channel: str,
    control_points: list[tuple[int, int]],
) -> dict[str, Any]:
    """Apply a spline curve to a colour channel.

    Parameters
    ----------
    channel:
        Script-Fu channel constant such as ``HISTOGRAM-VALUE``,
        ``HISTOGRAM-RED``, ``HISTOGRAM-GREEN``, ``HISTOGRAM-BLUE``.
    control_points:
        List of (input, output) pairs, each in [0, 255].
    """
    n_values = len(control_points) * 2
    flat_pts = " ".join(f"{inp} {out}" for inp, out in control_points)
    script = _wrap(
        f"(gimp-curves-spline drawable {channel} {n_values} "
        f"#({flat_pts}))"
    )
    return {
        "action": "apply_curves",
        "channel": channel,
        "control_points": control_points,
        "script": script,
    }


def apply_levels(
    input_levels: tuple[int, int, float],
    output_levels: tuple[int, int],
) -> dict[str, Any]:
    """Adjust tonal levels.

    Parameters
    ----------
    input_levels:
        ``(low_input, high_input, gamma)`` — e.g. ``(0, 255, 1.0)``.
    output_levels:
        ``(low_output, high_output)`` — e.g. ``(0, 255)``.
    """
    in_lo, in_hi, gamma = input_levels
    out_lo, out_hi = output_levels
    script = _wrap(
        f"(gimp-levels drawable HISTOGRAM-VALUE "
        f"{in_lo} {in_hi} {gamma} {out_lo} {out_hi})"
    )
    return {
        "action": "apply_levels",
        "input_levels": input_levels,
        "output_levels": output_levels,
        "script": script,
    }


def apply_hue_saturation(
    hue: float,
    saturation: float,
    lightness: float,
) -> dict[str, Any]:
    """Shift hue, saturation, and lightness across the whole image.

    All values are in the range ``[-180, 180]`` for hue and
    ``[-100, 100]`` for saturation / lightness.
    """
    script = _wrap(
        f"(gimp-drawable-hue-saturation drawable HUE-RANGE-ALL "
        f"{hue} {lightness} {saturation} 0)"
    )
    return {
        "action": "apply_hue_saturation",
        "hue": hue,
        "saturation": saturation,
        "lightness": lightness,
        "script": script,
    }


def apply_color_balance(
    shadows: tuple[float, float, float],
    midtones: tuple[float, float, float],
    highlights: tuple[float, float, float],
) -> dict[str, Any]:
    """Apply colour balance adjustments to shadows, midtones and highlights.

    Each tuple is ``(cyan_red, magenta_green, yellow_blue)`` shift in
    ``[-100, 100]``.
    """
    def _cb_script(tone_range: str, values: tuple[float, float, float]) -> str:
        cr, mg, yb = values
        return (
            f"(gimp-drawable-color-balance drawable {tone_range} TRUE "
            f"{cr} {mg} {yb})"
        )

    combined = " ".join([
        _cb_script("COLOR-RANGE-SHADOWS", shadows),
        _cb_script("COLOR-RANGE-MIDTONES", midtones),
        _cb_script("COLOR-RANGE-HIGHLIGHTS", highlights),
    ])
    script = _wrap(combined)
    return {
        "action": "apply_color_balance",
        "shadows": shadows,
        "midtones": midtones,
        "highlights": highlights,
        "script": script,
    }
