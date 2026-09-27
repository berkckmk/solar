#!/usr/bin/env bash
# Solar System Time Journey: Preview & Proof Render (macOS)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=================================================="
echo " Solar System: Render Lookdev Stills & Proof Clip"
echo "=================================================="

# Locate Blender
BLENDER_BIN="/Applications/Blender.app/Contents/MacOS/Blender"
if [[ ! -x "$BLENDER_BIN" ]]; then
    if command -v blender &>/dev/null; then
        BLENDER_BIN="$(command -v blender)"
    else
        echo "ERROR: Blender not found at /Applications/Blender.app or in PATH."
        exit 1
    fi
fi

echo "Using Blender: $BLENDER_BIN"
cd "$ROOT_DIR"

# 1. Render 6 proof stills
echo ""
echo "[Step 1/2] Rendering 6 Lookdev Proof Stills..."
"$BLENDER_BIN" --background --python projects/solar_system_time_journey/blender_build.py -- --proof-stills

# 2. Render 25s proof clip
echo ""
echo "[Step 2/2] Rendering 25s Proof Clip Video..."
"$BLENDER_BIN" --background --python projects/solar_system_time_journey/blender_build.py -- --proof-clip

echo ""
echo "=================================================="
echo "✅ Preview and Proof Renders Completed Successfully!"
echo "Proof Stills: output/solar_system_time_journey/proof_stills/"
echo "Proof Clip:   output/solar_system_time_journey/proof_clip/preview_visual_proof.mp4"
echo "=================================================="
