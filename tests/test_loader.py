"""Tests for the parts that are easy to get silently wrong."""

import numpy as np
import pytest

from dicom_explorer import load_directory
from dicom_explorer.windowing import apply_window, preset

DATA = "data/sample_ct"


@pytest.fixture(scope="module")
def series():
    return load_directory(DATA)


def test_slices_are_ordered_by_position(series):
    """Filenames are scrambled on disk; the loader must sort geometrically."""
    z = [float(ds.ImagePositionPatient[2]) for ds in series.datasets]
    assert z == sorted(z)
    assert len(z) == len(set(z)), "duplicate slice positions"


def test_slice_spacing_is_measured_not_assumed(series):
    assert series.slice_spacing == pytest.approx(2.0, abs=0.01)


def test_rescale_is_applied(series):
    """Without the modality LUT, air would read near 0 instead of -1000 HU."""
    assert series.volume.min() < -900, "rescale intercept was not applied"
    corner = series.volume[series.n_slices // 2, :10, :10].mean()
    assert corner == pytest.approx(-1000, abs=60), "background air is not ~-1000 HU"


def test_tissue_values_are_plausible(series):
    """Spot-check that recognisable tissues land in their expected HU ranges."""
    vol = series.volume
    assert vol.max() > 800, "no bone-density voxels found"
    assert ((vol > -900) & (vol < -600)).sum() > 1000, "no lung-density voxels found"


def test_window_maps_into_unit_range(series):
    centre, width = preset("lung")
    out = apply_window(series.volume[0], centre, width)
    assert out.min() >= 0.0 and out.max() <= 1.0
    assert out.dtype == np.float32


def test_window_clips_at_the_edges():
    image = np.array([[-2000.0, 0.0, 2000.0]], dtype=np.float32)
    out = apply_window(image, centre=0, width=100)
    assert out[0, 0] == 0.0    # far below the window
    assert out[0, 1] == 0.5    # exactly at the centre
    assert out[0, 2] == 1.0    # far above the window


def test_narrow_window_has_more_contrast_than_wide():
    """A narrower window stretches a smaller HU range over the same grey scale."""
    image = np.array([[0.0, 50.0]], dtype=np.float32)
    narrow = apply_window(image, centre=25, width=100)
    wide = apply_window(image, centre=25, width=1000)
    assert (narrow[0, 1] - narrow[0, 0]) > (wide[0, 1] - wide[0, 0])
