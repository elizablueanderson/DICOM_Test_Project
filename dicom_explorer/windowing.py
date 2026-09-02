"""Window/level: mapping a wide range of tissue values onto a visible grey scale.

A CT slice spans roughly -1000 HU (air) to +3000 HU (dense bone), about 4000
distinct values. A monitor shows 256 grey levels and the human eye resolves
fewer than that. So you cannot display the whole range at once and see
anything useful.

Windowing solves this by picking an interval and throwing the rest away.
Everything below the interval renders black, everything above renders white,
and the values inside are stretched across the full grey scale. The interval
is described by its centre (level) and its width:

    lower = centre - width / 2
    upper = centre + width / 2

This is why radiologists flip between presets on the same image. A lung
window and a bone window are the same pixels, displayed twice.
"""

from __future__ import annotations

import numpy as np

# Centre and width in Hounsfield units. These are the conventional starting
# points used in clinical practice; radiologists adjust from here.
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
    """The window to open with.

    Scanners usually record the window the technologist was using in
    WindowCenter and WindowWidth. Those tags may hold several values, in which
    case the first is the primary one. If they are absent (common on MRI,
    where pixel values have no absolute meaning), fall back to the 1st-99th
    percentile of the data, which ignores outliers better than min/max.
    """
    if "WindowCenter" in ds and "WindowWidth" in ds:
        centre = ds.WindowCenter
        width = ds.WindowWidth
        centre = float(centre[0] if hasattr(centre, "__iter__") else centre)
        width = float(width[0] if hasattr(width, "__iter__") else width)
        if width > 0:
            return centre, width

    lo, hi = np.percentile(volume, [1, 99])
    return float((lo + hi) / 2), float(max(hi - lo, 1))


def apply_window(
    image: np.ndarray,
    centre: float,
    width: float,
    invert: bool = False,
) -> np.ndarray:
    """Map an image to 0..1 for display using the given window.

    invert handles PhotometricInterpretation == MONOCHROME1, where low stored
    values are meant to be displayed as white rather than black. Getting this
    backwards produces a photographic negative, which on a chest film looks
    almost plausible and is easy to miss.
    """
    lower = centre - width / 2
    upper = centre + width / 2
    out = (image.astype(np.float32) - lower) / max(upper - lower, 1e-6)
    np.clip(out, 0.0, 1.0, out=out)
    return 1.0 - out if invert else out


def is_inverted(ds) -> bool:
    """True if this dataset uses MONOCHROME1 (low value = white)."""
    return str(getattr(ds, "PhotometricInterpretation", "MONOCHROME2")) == "MONOCHROME1"
