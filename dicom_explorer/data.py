"""Read the DICOM header: acquisition parameters + identifying info. 

DICOM = database record that contains an image.
The header shows the scan settings, the geometry, and patient's identity (in a clincial file).
"""

from __future__ import annotations

# Tags worth reading on almost any study, grouped by what they tell you.
SUMMARY_TAGS = {
    "Study": ["StudyDescription", "StudyDate", "StudyTime", "AccessionNumber"],
    "Series": ["Modality", "SeriesDescription", "SeriesNumber", "BodyPartExamined",
               "ProtocolName"],
    "Equipment": ["Manufacturer", "ManufacturerModelName", "SoftwareVersions"],
    "Geometry": ["Rows", "Columns", "PixelSpacing", "SliceThickness",
                 "SpacingBetweenSlices", "ImageOrientationPatient",
                 "ImagePositionPatient", "PatientPosition"],
    "Pixels": ["BitsAllocated", "BitsStored", "HighBit", "PixelRepresentation",
               "PhotometricInterpretation", "SamplesPerPixel",
               "RescaleSlope", "RescaleIntercept", "RescaleType",
               "WindowCenter", "WindowWidth"],
    "CT acquisition": ["KVP", "XRayTubeCurrent", "ExposureTime", "Exposure",
                       "ConvolutionKernel", "ReconstructionDiameter"],
    "MR acquisition": ["MagneticFieldStrength", "RepetitionTime", "EchoTime",
                       "FlipAngle", "ScanningSequence", "SequenceVariant"],
}



def summarise(ds) -> str:
    """Format the interesting header fields as readable text."""
    lines = []
    for group, tags in SUMMARY_TAGS.items():
        present = [(t, ds[t].value) for t in tags if t in ds and str(ds[t].value) != ""]
        if not present:
            continue
        lines.append(f"\n{group}")
        for tag, value in present:
            text = str(value)
            if len(text) > 62:
                text = text[:59] + "..."
            lines.append(f"  {tag:<28s} {text}")
    return "\n".join(lines)


def audit_phi(ds) -> list[tuple[str, str]]:
    """Return every identifying field found in the header.

    """
    found = []
    for tag in PHI_TAGS:
        if tag in ds:
            value = str(ds[tag].value).strip()
            if value:
                found.append((tag, value))
    return found


def report(ds) -> str:
    """Full text report for one dataset: summary plus PHI audit."""
    out = [f"File: {getattr(ds, 'SOPInstanceUID', '?')}", summarise(ds)]

    phi = audit_phi(ds)
    out.append("\nIdentifying fields")
    if phi:
        for tag, value in phi:
            out.append(f"  {tag:<28s} {value}")
        out.append(
            f"\n  {len(phi)} identifying field(s) populated. "
            "Remove these before sharing this data publicly."
        )
    else:
        out.append("  none populated")

    return "\n".join(out)
