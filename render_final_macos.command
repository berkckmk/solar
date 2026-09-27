#!/usr/bin/env bash
# Solar System Time Journey: Final 9:25 1440p Production Render (macOS)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=================================================="
echo " Solar System: 9:25 1440p Final Production Render"
echo " Target: 2560x1440 @ 30 FPS (16,950 frames)"
echo " Resumable PNG Pipeline + H.264 Master Encoding"
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

# Execute final production render
python3 "$SCRIPT_DIR/generate.py" --final
