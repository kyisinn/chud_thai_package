#!/usr/bin/env bash
# ============================================================
# Chud Thai (Thai Chakraphat) -- Auto-run pipeline
# Runs stages 1-10 end to end:
#   IBR pipeline (light field / DIBR / view interpolation)
#   -> smoothed 360 HTML viewer
#   -> full Structure-from-Motion 3D reconstruction pipeline
# ============================================================
set -e
cd "$(dirname "$0")"

echo "=============================================="
echo " Chud Thai Pipeline -- Auto Run"
echo "=============================================="

echo ""
echo "[0/4] Installing Python dependencies..."
if command -v pip3 >/dev/null 2>&1; then
    pip3 install -r requirements.txt --break-system-packages -q \
        || pip3 install -r requirements.txt -q
else
    pip install -r requirements.txt --break-system-packages -q \
        || pip install -r requirements.txt -q
fi

echo ""
echo "[1/4] Running Image-Based Rendering pipeline"
echo "      (light field grid, depth-based rendering, view interpolation)..."
python3 scripts/ibr_pipeline.py

echo ""
echo "[2/4] Building the 360-degree HTML viewer from the smoothed frames..."
python3 scripts/build_360_viewer.py

echo ""
echo "[3/4] Running the Structure-from-Motion 3D reconstruction pipeline"
echo "      (feature matching -> pose estimation -> triangulation -> mesh)..."
if command -v xvfb-run >/dev/null 2>&1; then
    xvfb-run -a python3 scripts/sfm_pipeline.py
else
    echo "      (xvfb-run not found; attempting direct run -- offscreen"
    echo "       preview renders may be skipped, but sparse_cloud.ply /"
    echo "       mesh.ply will still be written)"
    python3 scripts/sfm_pipeline.py
fi

echo ""
echo "[4/4] Done. Results:"
echo "  viewer/thai_chakraphat_360.html   <- open this in a browser, drag to rotate"
echo "  outputs/ibr_out/                  <- light field grid, depth map, interpolation strip"
echo "  outputs/sfm_out/sparse_cloud.ply  <- open in MeshLab / Blender / CloudCompare"
echo "  outputs/sfm_out/mesh.ply          <- reconstructed textured mesh"
echo "  outputs/sfm_out/evaluation_report.json  <- match/pose/reconstruction stats"
echo "=============================================="
