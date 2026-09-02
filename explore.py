"""Command line entry point for the DICOM explorer.

    python explore.py data/sample_ct                  open the interactive viewer
    python explore.py data/sample_ct --header         print the header and exit
    python explore.py data/sample_ct --montage out.png --preset lung
"""

from __future__ import annotations

import argparse
import sys

from dicom_explorer import load_directory, report
from dicom_explorer.viewer import save_montage, show
from dicom_explorer.windowing import CT_PRESETS, preset


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path", help="directory containing a DICOM series")
    p.add_argument("--series", type=int, default=0,
                   help="which series to load if the folder holds more than one")
    p.add_argument("--header", action="store_true",
                   help="print the header of the first slice and exit")
    p.add_argument("--montage", metavar="OUT.png",
                   help="save a grid of slices instead of opening a window")
    p.add_argument("--preset", choices=sorted(CT_PRESETS),
                   help="window preset for --montage")
    args = p.parse_args()

    try:
        series = load_directory(args.path, args.series)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(series)
    print(f"Value range: {series.volume.min():.0f} to {series.volume.max():.0f} {series.units}")

    if args.header:
        print(report(series.datasets[0]))
        return 0

    if args.montage:
        window = preset(args.preset) if args.preset else None
        print(f"Wrote {save_montage(series, args.montage, window=window)}")
        return 0

    show(series)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
