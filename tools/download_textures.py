"""Download the full-resolution planet maps (Solar System Scope, CC BY 4.0).

    python3 tools/download_textures.py            # 8K originals (about 60 MB)
    python3 tools/download_textures.py --res 2k   # the small set only

The repository already ships 4K copies, so this is optional: renders pick the
largest map present (8k > 4k > 2k; set SOLAR_TEX=4k to cap memory use).
Files go to assets/textures/ and are git-ignored. Existing files are kept.
Each file is tried from solarsystemscope.com first, then from its copy on
Wikimedia Commons.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

TEX_DIR = Path(__file__).resolve().parent.parent / "assets" / "textures"

# largest version Solar System Scope publishes of each map we use
FULL = ["8k_mercury.jpg", "4k_venus_atmosphere.jpg", "8k_earth_daymap.jpg", "8k_earth_nightmap.jpg",
        "8k_earth_clouds.jpg", "8k_earth_specular_map.tif", "8k_mars.jpg", "8k_jupiter.jpg",
        "8k_saturn.jpg", "8k_saturn_ring_alpha.png", "2k_uranus.jpg", "2k_neptune.jpg"]
SMALL = ["2k_mercury.jpg", "2k_venus_atmosphere.jpg", "2k_earth_daymap.jpg", "2k_earth_nightmap.jpg",
         "2k_earth_clouds.jpg", "2k_earth_specular_map.tif", "2k_mars.jpg", "2k_jupiter.jpg",
         "2k_saturn.jpg", "2k_saturn_ring_alpha.png", "2k_uranus.jpg", "2k_neptune.jpg"]

SOURCES = ("https://www.solarsystemscope.com/textures/download/{f}",
           "https://commons.wikimedia.org/wiki/Special:FilePath/Solarsystemscope_texture_{f}")
MAGIC = (b"\xff\xd8\xff", b"\x89PNG", b"II*\x00", b"MM\x00*")


def fetch(name: str) -> str:
    dst = TEX_DIR / name
    if dst.exists() and dst.stat().st_size > 10_000:
        return "already there"
    last = ""
    for pattern in SOURCES:
        url = pattern.format(f=name)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "solar-system-time-journey/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
        except Exception as e:                                  # try the next source
            last = f"{url}: {e}"
            continue
        if len(data) < 10_000 or not data.startswith(MAGIC):
            last = f"{url}: not an image ({len(data)} bytes)"
            continue
        tmp = dst.with_suffix(dst.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(dst)
        return f"{len(data) / 1e6:.1f} MB from {url.split('/')[2]}"
    return f"FAILED ({last})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--res", choices=("8k", "2k"), default="8k")
    args = ap.parse_args()
    TEX_DIR.mkdir(parents=True, exist_ok=True)
    failed = 0
    for name in (FULL if args.res == "8k" else SMALL):
        status = fetch(name)
        failed += status.startswith("FAILED")
        print(f"  {name:30s} {status}")
    print(f"\n{'All maps ready' if not failed else f'{failed} map(s) missing'} in {TEX_DIR}")
    if failed:
        print("Missing maps fall back to the 4K copies in the repository (or the procedural look).\n"
              "Manual download: https://www.solarsystemscope.com/textures/ -> save into the folder above.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
