"""A small, readable DICOM explorer: load a series, inspect the header, view it."""

from .loader import Series, find_series, load_directory, load_series
from .metadata import audit_phi, report, summarise
from .windowing import CT_PRESETS, apply_window, default_window, preset

__all__ = [
    "Series", "find_series", "load_series", "load_directory",
    "summarise", "audit_phi", "report",
    "CT_PRESETS", "apply_window", "default_window", "preset",
]
