"""Window/level: mapping a wide range of tissue values onto a visible grey scale.

A CT slice spans roughly -1000 HU (air) to +3000 HU (dense bone), about 4000
distinct values, the human eye can see fewer than 256.
Windowing solves this by picking an interval and stretching 
the inside across a grey scale. Description:

    lower = center - width / 2
    upper = center + width / 2


"""

from __future__ import annotations

import numpy as np

CT_PRESETS: dict[str, tuple[float, float]] = {
    "lung":        (-600, 1500),
    "soft tissue": (   40,  400),
    "abdomen":     (   60,  400),
    "liver":       (   60,  160),
    "mediastinum": (   50,  350),
    "brain":       (   40,   80),
    "bone":        (  400, 1800),
    "angio":       (  300,  600),
}


def preset(name: str) -> tuple[float, float]:
    """Look up a preset by name, case-insensitively."""
    key = name.strip().lower()
    if key not in CT_PRESETS:
        raise KeyError(f"Unknown preset {name!r}. Options: {', '.join(CT_PRESETS)}")
    return CT_PRESETS[key]


def default_window(ds, volume: np.ndarray) -> tuple[float, float]:
    """The window to open wid
    """
    if "WindowCenter" in ds and "WindowWidth" in ds:
        center = ds.WindowCenter
        width = ds.WindowWidth
        center = float(centre[0] if hasattr(centre, "__iter__") else centre)
        width = float(width[0] if hasattr(width, "__iter__") else width)
        if width > 0:
            return centre, width

    lo, hi = np.percentile(volume, [1, 99])
    return float((lo + hi) / 2), float(max(hi - lo, 1))


def apply_window(
    image: np.ndarray,
    center: float,
    width: float,
    invert: bool = False,
) -> np.ndarray:
    """Map an image to 0..1 for display using the given window.

    invert handles PhotometricInterpretation == MONOCHROME1,
    low stored values = displayed as white, not black
    """
    lower = centre - width / 2
    upper = centre + width / 2
    out = (image.astype(np.float32) - lower) / max(upper - lower, 1e-6)
    np.clip(out, 0.0, 1.0, out=out)
    return 1.0 - out if invert else out


def is_inverted(ds) -> bool:
    """True if this data uses MONOCHROME1 (low value = white)."""
    return str(getattr(ds, "PhotometricInterpretation", "MONOCHROME2")) == "MONOCHROME1"
