"""Generate a fake chest CT series as real DICOM files.

Real patient data can't be in a public repo, so this builds a demo and
writes it out as valid DICOM to produce a file that can be rescaled.
Tissue values are the conventional Hounsfield numbers, so they show up 
the same way they do on a real scan.

    python make_sample_data.py
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

CT_IMAGE_STORAGE = "1.2.840.10008.5.1.4.1.1.2"

# Hounsfield units. Water is 0 and air is -1000, the rest are
# typical values for tissue.
HU = {
    "air": -1000.0,
    "lung": -780.0,
    "fat": -100.0,
    "muscle": 45.0,
    "blood": 55.0,
    "lesion": 65.0,
    "trabecular_bone": 350.0,
    "cortical_bone": 1100.0,
}


def _ellipse(shape, cy, cx, ry, rx) -> np.ndarray:
    yy, xx = np.ogrid[: shape[0], : shape[1]]
    ry, rx = max(float(ry), 1e-6), max(float(rx), 1e-6)
    return ((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2 <= 1.0


def build_volume(n_slices=48, size=256, seed=0) -> np.ndarray:
    """A crude axial chest phantom, in Hounsfield units."""
    rng = np.random.default_rng(seed)
    vol = np.full((n_slices, size, size), HU["air"], dtype=np.float32)
    c = size / 2

    for k in range(n_slices):
        t = k / max(n_slices - 1, 1)          # 0 at apex, 1 at base
        sl = vol[k]

        # Body cross-section widens toward the base of the chest.
        body_ry = 0.30 * size + 0.04 * size * t
        body_rx = 0.38 * size + 0.05 * size * t
        body = _ellipse(sl.shape, c, c, body_ry, body_rx)
        sl[body] = HU["muscle"]

        # Subcutaneous fat: the body minus copy of itself.
        inner = _ellipse(sl.shape, c, c, body_ry - 9, body_rx - 9)
        sl[body & ~inner] = HU["fat"]

        # Lungs, largest through the middle of the stack.
        lung_scale = np.sin(np.pi * np.clip(t * 1.05, 0, 1)) ** 0.5
        if lung_scale > 0.05:
            ry = 0.21 * size * lung_scale
            rx = 0.13 * size * lung_scale
            for sign in (-1, 1):
                lung = _ellipse(sl.shape, c - 0.02 * size, c + sign * 0.17 * size, ry, rx)
                sl[lung] = HU["lung"]
                # Vessels and airways read as bright specks inside dark lung.
                texture = rng.normal(0, 90, sl.shape).astype(np.float32)
                sl[lung] += texture[lung]

        # Mediastinum: heart and vessels between the lungs.
        heart = _ellipse(sl.shape, c + 0.05 * size, c - 0.02 * size,
                         0.13 * size * lung_scale, 0.11 * size * lung_scale)
        sl[heart] = HU["blood"]

        # Vertebral body: core inside a cortical shell.
        v_out = _ellipse(sl.shape, c + 0.24 * size, c, 0.055 * size, 0.065 * size)
        v_in = _ellipse(sl.shape, c + 0.24 * size, c, 0.040 * size, 0.050 * size)
        sl[v_out] = HU["cortical_bone"]
        sl[v_in] = HU["trabecular_bone"]

        # Ribs = bright dots around the body wall.
        for angle in np.linspace(0.35, np.pi - 0.35, 7):
            for sign in (-1, 1):
                ry_pos = c - np.cos(angle) * (body_ry - 5)
                rx_pos = c + sign * np.sin(angle) * (body_rx - 5)
                sl[_ellipse(sl.shape, ry_pos, rx_pos, 4, 4)] = HU["cortical_bone"]

        # A solid nodule in the right lung, present only on middle slice
        # It is not seen in a bone window and obvious in a lung window
        z_off = (k - n_slices * 0.45) * 2.0
        r_mm = 9.0
        if abs(z_off) < r_mm:
            r_pix = np.sqrt(r_mm**2 - z_off**2) / 0.7
            sl[_ellipse(sl.shape, c - 0.04 * size, c - 0.19 * size, r_pix, r_pix)] = HU["lesion"]

        # Scanner noise, so the image is not too clean
        vol[k] = sl + rng.normal(0, 12, sl.shape).astype(np.float32)

    return vol


def write_series(volume: np.ndarray, out_dir: Path, spacing=(0.7, 0.7), thickness=2.0) -> None:
    """Write each slice as a CT Image Storage instance."""
    out_dir.mkdir(parents=True, exist_ok=True)
    study_uid, series_uid, frame_uid = generate_uid(), generate_uid(), generate_uid()

    n, rows, cols = volume.shape
    intercept, slope = -1024.0, 1.0

    # Filenames are mixed up on purpose. Alphabetical order rarely matches
    # anatomical order. loader.py sorts by ImagePositionPatient instead.
    order = list(range(n))
    random.Random(1).shuffle(order)

    for k in range(n):
        ds = Dataset()
        ds.file_meta = FileMetaDataset()
        ds.file_meta.MediaStorageSOPClassUID = CT_IMAGE_STORAGE
        ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.file_meta.ImplementationVersionName = "DICOM_EXPLORER"

        ds.SOPClassUID = CT_IMAGE_STORAGE
        ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
        ds.StudyInstanceUID = study_uid
        ds.SeriesInstanceUID = series_uid
        ds.FrameOfReferenceUID = frame_uid

        # Deliberately non-identifying: this is a phantom, not a person.
        ds.PatientName = "PHANTOM^SYNTHETIC"
        ds.PatientID = "PHANTOM001"
        ds.PatientSex = ""
        ds.PatientBirthDate = ""

        ds.Modality = "CT"
        ds.StudyDescription = "Synthetic chest phantom"
        ds.SeriesDescription = "Axial chest phantom 2.0mm"
        ds.SeriesNumber = 1
        ds.InstanceNumber = k + 1
        ds.BodyPartExamined = "CHEST"
        ds.Manufacturer = "dicom-explorer"
        ds.ManufacturerModelName = "make_sample_data.py"

        # ImageOrientationPatient: holds the cosines of the
        # image rows then the image columns; [1,0,0, 0,1,0] is a plain axial
        # slice. ImagePositionPatient is the location of the
        # center of the first voxel, and is what the loader sorts on.
        ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        ds.ImagePositionPatient = [
            -spacing[1] * cols / 2,
            -spacing[0] * rows / 2,
            round(k * thickness, 3),
        ]
        ds.PixelSpacing = [spacing[0], spacing[1]]
        ds.SliceThickness = thickness
        ds.SpacingBetweenSlices = thickness
        ds.SliceLocation = round(k * thickness, 3)
        ds.PatientPosition = "HFS"

        # Pixel representation: 16 bits, unsigned, one sample per pixel,
        # MONOCHROME2 (low value shows dark, not light).
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.Rows, ds.Columns = rows, cols
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 0

        # Rescale relationship: HU = slope * stored + intercept.
        # Unsigned integers with intercept -1024 = regular CT convention, 
        # because air at -1000 HU has to fit in a range that starts at zero.
        ds.RescaleSlope = slope
        ds.RescaleIntercept = intercept
        ds.RescaleType = "HU"
        ds.WindowCenter = 40
        ds.WindowWidth = 400

        stored = np.clip((volume[k] - intercept) / slope, 0, 4095)
        ds.PixelData = stored.astype(np.uint16).tobytes()

        ds.save_as(out_dir / f"IM{order[k]:05d}.dcm", enforce_file_format=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="data/sample_ct", help="output directory")
    p.add_argument("--slices", type=int, default=48)
    p.add_argument("--size", type=int, default=256, help="in-plane matrix size")
    args = p.parse_args()

    out = Path(args.out)
    volume = build_volume(args.slices, args.size)
    write_series(volume, out)
    print(f"Wrote {args.slices} slices to {out}/")
    print(f"HU range {volume.min():.0f} to {volume.max():.0f}")
    print(f"\nNext:  python explore.py {out}")


if __name__ == "__main__":
    main()
