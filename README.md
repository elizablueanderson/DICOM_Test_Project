# DICOM Explorer

Load a CT or MRI series, put the slices back in anatomical order, 
convert stored pixel values into physical units, view them interactively.
DICOM = file format every clinical scanner writes and every PACS stores. 
Turning a folder of hundreds of files into ordered and scaled 3D volumes leaves room for mistakes,
this repository handles it in only around 300 readable lines.

![Three window presets applied to one slice](docs/window_comparison.png)

Identical pixel data in all three panels. The nodule in the right lung is visible in lung window, but not in a bone window.

## Run it


```bash
git clone https://github.com/YOUR-USERNAME/dicom-explorer.git
cd dicom-explorer
pip install -r requirements.txt

python make_sample_data.py          # writes 48 synthetic CT slices to data/sample_ct/
python explore.py data/sample_ct    # opens the viewer
```

In the viewer: drag the slice slider or use arrow keys, 
drag center and width to adjust the window, or click a preset.

```bash
python explore.py data/sample_ct --header                        # print the DICOM header
python explore.py data/sample_ct --montage out.png --preset lung # headless render
python -m pytest tests/                                          # 7 tests
```


## What it does

**Groups files into series:** One folder holds more than one acquisition: a scout scan with the diagnostic series or two  kernels of the same data. Files are grouped by `SeriesInstanceUID`, because folder structure and filenames aren't reliable.

**Sorts slices by geometry, not by filename or instance number:** `ImageOrientationPatient` gives the cosines of the image rows and columns; their cross product is the normal to the image plane. Projecting each slice's `ImagePositionPatient` onto that gives a scalar that increases through the images. `SliceLocation` may be absent and `InstanceNumber` may not follow anatomy.

The sample data has deliberately scrambled filenames. Sorting alphabetically produces slice positions of 64, 70, 12, 50 mm; sorting geometrically gives 0, 2, 4, 6.

**Applies the modality LUT:** Scanners don't store physical values, but instead do integers.

```
HU = RescaleSlope × stored_value + RescaleIntercept
```

A CT scan usually stores 0–4095 with an intercept of −1024, so value 1024 is 0 HU, which is water.

**Measures slice spacing from the data:** Consecutive slice positions are differenced rather than reading `SliceThickness`, which describes how thick each slice is and says nothing about gaps or overlap between them. Uneven spacing raises a warning.

**Corrects for anisotropic pixels:** `PixelSpacing` is `(row_mm, col_mm)` and the two aren't always equal. Ignoring it makes the rendering of the anatomy stretched.

**Audits the header for identifying information:** `--header` lists every populated PHI field. 

## Windowing

A CT spans roughly −1000 HU (air) to +3000 HU (dense bone). A display has 256 grey levels. The full range can't be shown all at once, so a window selects an interval and stretches what is left inside of it in the grey scale:

```
lower = centre − width/2
upper = centre + width/2
```


| Preset | Centre (HU) | Width (HU) |
|---|---|---|
| lung | −600 | 1500 |
| soft tissue | 40 | 400 |
| abdomen | 60 | 400 |
| liver | 60 | 160 |
| mediastinum | 50 | 350 |
| brain | 40 | 80 |
| bone | 400 | 1800 |
| angio | 300 | 600 |


## Sample data

`make_sample_data.py` builds an axial chest phantom (for demo) and as valid CT Image Storages: body wall, subcutaneous fat, lungs with vessel texture, heart, vertebral body with a cortical shell, ribs, and a 9 mm nodule spanning the middle slices.


## Layout

```
dicom_explorer/
  loader.py      series discovery, geometric sorting, volume assembly
  windowing.py   window/level transform and clinical presets
  metadata.py    header summary and PHI audit
  viewer.py      interactive viewer, montage and comparison export
explore.py       command line entry point
make_sample_data.py
tests/
```
