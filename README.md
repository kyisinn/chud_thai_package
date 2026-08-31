# Chud Thai (Thai Chakraphat) — Image-Based Rendering & 3D Reconstruction

Pipeline:

```
Museum Images -> Selection -> Pre-processing -> Alignment ->
Feature Detection & Matching -> Motion Estimation ->
Camera/Viewpoint Estimation -> 3D Reconstruction ->
Texture Mapping -> 3D Rendering -> Visual Evaluation ->
Final Digital Chud Thai Model
```

## Quick start

```bash
./run_all.sh
```

This installs dependencies, then runs everything end to end:

1. **`scripts/ibr_pipeline.py`** — the Chapter 14 Image-Based Rendering
   techniques (light field grid, depth image-based rendering, view
   interpolation) applied to the 18 real photos in `images/`.
2. **`scripts/build_360_viewer.py`** — packs the resulting frames (18
   real + interpolated in-betweens) into a single self-contained,
   drag-to-rotate `viewer/thai_chakraphat_360.html`.
3. **`scripts/sfm_pipeline.py`** — a real Structure-from-Motion pipeline:
   SIFT feature detection & matching → motion estimation → Essential-matrix
   camera pose estimation → sparse 3D triangulation → Poisson mesh /
   texture mapping → offscreen 3D renders → a JSON evaluation report.

## Folder layout

```
chud_thai_package/
├── run_all.sh                 <- run this
├── requirements.txt
├── images/
├── scripts/
│   ├── ibr_pipeline.py
│   ├── build_360_viewer.py
│   └── sfm_pipeline.py
├── viewer/
│   └── thai_chakraphat_360.html   <- open in any browser, drag to spin
└── outputs/
    ├── ibr_out/                <- light_field_grid.jpg, depth_map.jpg,
    │                              depth_rendered_left/right.jpg,
    │                              view_interpolation_strip.jpg,
    │                              smooth_sequence/*.jpg (54 frames)
    └── sfm_out/                <- sparse_cloud.ply, mesh.ply,
                                    render_00–03.png, evaluation_report.json
```

## Honest limitations (please read)

The 18 photos are handheld phone shots of a museum piece behind
glass — uneven spacing, no calibration target, no EXIF focal length,
glare/reflections in several frames, and some frames come from
different display cases entirely. That's a hard case for classical
Structure-from-Motion. `sfm_pipeline.py` does real feature matching,
pose estimation, and triangulation, but poses are chained sequentially
with **no bundle adjustment or loop closure**, so weak pairs (visible
as low "pose inliers" in the console log and in `evaluation_report.json`)
cause the reconstruction to drift and fragment into disconnected
chunks rather than one clean coherent 3D costume. Check the printed
per-pair match/inlier counts to see exactly where the geometry is
trustworthy and where it isn't.

For a museum-grade digital model, the recommended path is running
this same `images/` folder through **COLMAP** (free, open source),
which performs global bundle adjustment and loop closure automatically,
or shooting a proper evenly-spaced turntable capture with a calibrated
camera.

## Requirements

- Python 3.9+
- See `requirements.txt` (opencv-python-headless, numpy, open3d, Pillow)
- `xvfb` (optional, Linux only) for offscreen 3D preview renders —
  the pipeline still produces valid `.ply` files without it.
