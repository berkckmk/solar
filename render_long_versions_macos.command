#!/usr/bin/env bash
# Solar System Time Journey: the two long versions (macOS)
#   Format A  9:25 system journey  (2560x1440, 16,950 frames)
#   Format B  9:09 shared clock    (1920x1080, 16,470 frames)
# Double-click for Turkish on-screen text, or run `./render_long_versions_macos.command en`.
# Resumable: rerun after an interruption and only the missing frames are rendered.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LANG_CODE="${1:-tr}"
cd "$SCRIPT_DIR"

echo "[1/2] System journey ($LANG_CODE)..."
python3 generate.py --journey --lang "$LANG_CODE"

echo "[2/2] Shared clock, 9-minute cut ($LANG_CODE)..."
python3 generate.py --shared-clock-long --lang "$LANG_CODE"

echo "Done. Videos are in output/solar_system_time_journey/final/"
