"""Effect application via Audacity's mod-script-pipe."""

from __future__ import annotations

from ..backend import AudacityBackend


def apply_normalize(
    backend: AudacityBackend,
    peak_level_db: float = -1.0,
) -> str:
    """Apply the Normalize effect to the selection.

    *peak_level_db* sets the target peak amplitude in dB (typically -1.0).
    """
    return backend.send_command(
        f"Normalize: PeakLevel={peak_level_db} ApplyGain=1 RemoveDCOffset=1"
    )


def apply_amplify(backend: AudacityBackend, gain_db: float) -> str:
    """Apply the Amplify effect, boosting or cutting by *gain_db* dB."""
    return backend.send_command(f"Amplify: Ratio={gain_db} AllowClipping=0")


def apply_fade_in(backend: AudacityBackend) -> str:
    """Apply a linear fade-in to the selection."""
    return backend.send_command("FadeIn")


def apply_fade_out(backend: AudacityBackend) -> str:
    """Apply a linear fade-out to the selection."""
    return backend.send_command("FadeOut")


def apply_noise_reduction(
    backend: AudacityBackend,
    noise_profile: bool,
    sensitivity: float = 6.0,
    freq_smoothing: float = 3.0,
    attack_time: float = 0.15,
) -> str:
    """Apply Noise Reduction.

    When *noise_profile* is True, capture the noise profile from the selection
    instead of applying the reduction.
    """
    if noise_profile:
        return backend.send_command("NoiseReduction: UseProfile=1")
    return backend.send_command(
        f"NoiseReduction: NoiseReductionDB={sensitivity} "
        f"SensitivityDB={freq_smoothing} "
        f"FreqSmoothingBands={int(freq_smoothing)} "
        f"AttackTime={attack_time}"
    )


def apply_eq(
    backend: AudacityBackend,
    filter_curve: list[tuple[float, float]],
) -> str:
    """Apply the Filter Curve EQ using a list of (frequency_hz, gain_db) control points."""
    curve_str = " ".join(f"f={f} db={g}" for f, g in filter_curve)
    return backend.send_command(f"FilterCurveEQ: {curve_str}")


def apply_compressor(
    backend: AudacityBackend,
    threshold: float = -12.0,
    noise_floor: float = -40.0,
    ratio: float = 2.0,
    attack: float = 0.2,
    release: float = 1.0,
) -> str:
    """Apply the Compressor effect to the selection."""
    return backend.send_command(
        f"Compressor: Threshold={threshold} NoiseFloor={noise_floor} "
        f"Ratio={ratio} AttackTime={attack} ReleaseTime={release} "
        "Normalize=0 UsePeak=0"
    )


def apply_reverb(
    backend: AudacityBackend,
    room_size: float = 75.0,
    reverberance: float = 50.0,
    damping: float = 50.0,
    tone_low: float = 100.0,
    tone_high: float = 100.0,
    wet_gain: float = -1.0,
    stereo_width: float = 100.0,
) -> str:
    """Apply the Reverb effect to the selection."""
    return backend.send_command(
        f"Reverb: RoomSize={room_size} Reverberance={reverberance} "
        f"HfDamping={damping} ToneLow={tone_low} ToneHigh={tone_high} "
        f"WetGain={wet_gain} DryGain=0 StereoWidth={stereo_width} WetOnly=0"
    )
