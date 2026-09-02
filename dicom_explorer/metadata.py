"""Read the DICOM header: acquisition parameters and identifying information.

A DICOM file is a small database record that happens to contain an image.
The header carries the scan settings, the geometry, and, in a clinical file,
the patient's identity.
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

# Tags that carry protected health information. Anything here must be removed
# before a dataset leaves a clinical environment, and none of it belongs in a
# public GitHub repository.
PHI_TAGS = [
    "PatientName", "PatientID", "PatientBirthDate", "PatientSex", "PatientAge",
    "PatientAddress", "PatientTelephoneNumbers", "OtherPatientIDs",
    "ReferringPhysicianName", "PerformingPhysicianName", "OperatorsName",
    "InstitutionName", "InstitutionAddress", "StationName", "AccessionNumber",
    "StudyID", "InstanceCreationDate", "AcquisitionDate", "ContentDate",
]


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
    """Return every populated identifying field found in the header.

    Run this before you commit sample data. Note that de-identification is
    harder than blanking these tags: private vendor tags, burned-in text in
    the pixels themselves, and reconstructable facial anatomy in head scans
    all leak identity too. Treat this as a first pass, not a guarantee.
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
