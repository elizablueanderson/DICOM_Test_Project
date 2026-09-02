"""Load a DICOM series from disk and assemble it into a 3D volume.

"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pydicom
from pydicom.pixels import apply_modality_lut


@dataclass
class Series:
    """One imaging series, assembled and ready to display."""

    volume: np.ndarray          # (n_slices, rows, cols), in real units (HU for CT)
    datasets: list              # the pydicom Datasets, in the same order as volume
    pixel_spacing: tuple        # (row_mm, col_mm) within a slice
    slice_spacing: float        # mm between slice centres
    modality: str
    series_uid: str
    description: str

    @property
    def n_slices(self) -> int:
        return self.volume.shape[0]

    @property
    def units(self) -> str:
        return "HU" if self.modality == "CT" else "arbitrary units"

    def __repr__(self) -> str:
        return (
            f"<Series {self.modality} '{self.description}' "
            f"{self.n_slices} slices of {self.volume.shape[1]}x{self.volume.shape[2]}, "
            f"{self.pixel_spacing[0]:.3g}x{self.pixel_spacing[1]:.3g}x"
            f"{self.slice_spacing:.3g} mm>"
        )


def find_series(directory: str | Path) -> dict[str, list[Path]]:
    """Walk a directory and group every readable image file by SeriesInstanceUID.

    Grouping several scans by UID is the only reliable way to separate them.
    """
    directory = Path(directory)
    series: dict[str, list[Path]] = {}

    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name == "DICOMDIR":
            continue
        try:
            # stop_before_pixels: read only the header. Much faster when you
            # are scanning hundreds of files just to sort them into groups.
            ds = pydicom.dcmread(path, stop_before_pixels=True)
        except Exception:
            continue  # not a DICOM file, or unreadable

        # Skip header-only objects such as structured reports and
        # presentation states: they have a series UID but no image.
        if "SeriesInstanceUID" not in ds or "Rows" not in ds:
            continue

        series.setdefault(ds.SeriesInstanceUID, []).append(path)

    return series


def _slice_normal(ds) -> np.ndarray:
    """Unit vector perpendicular to the image plane.
    
    """
    if "ImageOrientationPatient" not in ds:
        return np.array([0.0, 0.0, 1.0])
    iop = np.array(ds.ImageOrientationPatient, dtype=float)
    return np.cross(iop[:3], iop[3:])


def _sort_key(ds) -> float:
    """Position of a slice along the stacking axis, in mm.

    Projecting ImagePositionPatient onto the slice normal gives a single
    number that increases monotonically through the stack of images
    """
    if "ImagePositionPatient" in ds:
        ipp = np.array(ds.ImagePositionPatient, dtype=float)
        return float(np.dot(ipp, _slice_normal(ds)))
    if "SliceLocation" in ds:
        return float(ds.SliceLocation)
    return float(getattr(ds, "InstanceNumber", 0))


def load_series(paths: list[Path]) -> Series:
    """Read a list of files belonging to one series into a Series object."""
    datasets = [pydicom.dcmread(p) for p in paths]
    datasets.sort(key=_sort_key)

    # apply_modality_lut converts stored integers into real units using
    # RescaleSlope and RescaleIntercept:  HU = slope * stored + intercept.
    # A CT typically stores 0..4095 with intercept -1024, so raw pixel 1024
    # is 0 HU (water). Skipping this step is the single most common DICOM
    # bug: every windowing preset will be wrong.
    frames = [apply_modality_lut(ds.pixel_array, ds).astype(np.float32) for ds in datasets]
    volume = np.stack(frames)

    first = datasets[0]
    spacing = tuple(float(v) for v in getattr(first, "PixelSpacing", [1.0, 1.0]))

    # Measure slice spacing from the positions rather than trusting
    # SliceThickness, which ignores gaps and overlap between slices.
    positions = [_sort_key(ds) for ds in datasets]
    if len(positions) > 1:
        gaps = np.diff(positions)
        slice_spacing = float(np.median(np.abs(gaps)))
        if not np.allclose(np.abs(gaps), slice_spacing, rtol=0.02):
            print(
                f"  warning: slice spacing is uneven "
                f"(min {np.abs(gaps).min():.3g} mm, max {np.abs(gaps).max():.3g} mm). "
                "Distances measured through the stack will be approximate."
            )
    else:
        slice_spacing = float(getattr(first, "SliceThickness", 1.0))

    return Series(
        volume=volume,
        datasets=datasets,
        pixel_spacing=spacing,
        slice_spacing=slice_spacing or 1.0,
        modality=str(getattr(first, "Modality", "?")),
        series_uid=str(getattr(first, "SeriesInstanceUID", "?")),
        description=str(getattr(first, "SeriesDescription", "(no description)")),
    )


def load_directory(directory: str | Path, index: int = 0) -> Series:
    """Convenience wrapper: find the series in a folder and load one of them."""
    groups = find_series(directory)
    if not groups:
        raise FileNotFoundError(f"No readable DICOM image files under {directory}")

    keys = sorted(groups, key=lambda k: -len(groups[k]))  # biggest series first
    if len(keys) > 1:
        print(f"Found {len(keys)} series in {directory}:")
        for i, k in enumerate(keys):
            ds = pydicom.dcmread(groups[k][0], stop_before_pixels=True)
            desc = getattr(ds, "SeriesDescription", "(no description)")
            print(f"  [{i}] {getattr(ds, 'Modality', '?'):4s} {len(groups[k]):4d} files  {desc}")
        print(f"Loading series [{index}].")

    return load_series(groups[keys[index]])
