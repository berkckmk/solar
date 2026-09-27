"""Screen layout, colours, strings and number formatting (pure Python, no bpy).

All rectangles are normalised screen coordinates: x 0..1 left→right, y 0..1
top→bottom, as (x0, y0, x1, y1). Sizes of text and lines are fractions of the
frame height so every resolution gets the same design.
"""

from __future__ import annotations

# ── regions ─────────────────────────────────────────────────────────────
SAFE = 0.045                                   # outer safe margin on every edge
TOP_BAND = (SAFE, SAFE, 1 - SAFE, 0.165)       # title / planet name (left), clock (right)
CLOCK_BOX = (0.735, SAFE, 1 - SAFE, 0.165)

# Focus view: compact info column left, wide animation area right.
INFO_COL = (SAFE, 0.205, SAFE + 0.25, 1 - SAFE)
FOCUS_AREA = (0.325, 0.205, 1 - SAFE, 1 - SAFE)

# General / comparison view: animation area left, table column right.
TABLE_COL = (0.705, 0.205, 1 - SAFE, 1 - SAFE)
GENERAL_AREA = (SAFE, 0.205, 0.675, 1 - SAFE)

LABEL_MARGIN = 0.035                           # room kept around orbits for planet labels


def center(rect):
    return (0.5 * (rect[0] + rect[2]), 0.5 * (rect[1] + rect[3]))


def inset(rect, dx, dy=None):
    dy = dx if dy is None else dy
    return (rect[0] + dx, rect[1] + dy, rect[2] - dx, rect[3] - dy)


# ── on-screen sizes (fraction of frame height) ──────────────────────────
PX = {
    "focus_planet": 0.017,      # radius of the selected planet
    "planet": 0.0065,           # other planets
    "sun": 0.014,               # Sun disc radius
    "sun_glow": 3.0,            # halo radius as multiple of the disc
}

# ── colours (sRGB 0..255); accents shared by orbit, label and table row ──
ACCENT = {
    "mercury": (205, 210, 216), "venus": (232, 196, 128), "earth": (96, 170, 240),
    "mars": (236, 120, 78), "jupiter": (222, 176, 120), "saturn": (228, 208, 150),
    "uranus": (120, 214, 220), "neptune": (104, 132, 240),
}
WHITE = (240, 243, 247)
MUTED = (150, 158, 170)
FAINT = (105, 112, 124)
CLOCK = (255, 214, 120)

# ── strings ─────────────────────────────────────────────────────────────
NAMES = {
    "tr": {"mercury": "Merkür", "venus": "Venüs", "earth": "Dünya", "mars": "Mars",
           "jupiter": "Jüpiter", "saturn": "Satürn", "uranus": "Uranüs", "neptune": "Neptün"},
    "en": {"mercury": "Mercury", "venus": "Venus", "earth": "Earth", "mars": "Mars",
           "jupiter": "Jupiter", "saturn": "Saturn", "uranus": "Uranus", "neptune": "Neptune"},
}

S = {
    "tr": {
        "question": "Dünya'da {n} gün geçerken diğer gezegenler ne kadar ilerler?",
        "clock": "DÜNYA SAATİ",
        "day_of": "Gün {d} / {n}",
        "experiment": "DENEY · {n} DÜNYA GÜNÜ",
        "distance": "Katedilen yol",
        "angle": "Güneş çevresindeki hareket",
        "angle_note": "tam turun {p}",
        "speed": "Anlık hız",
        "sun_dist": "Güneş'e uzaklık",
        "spin": "Eksen dönüşü",
        "solar_days": "Geçen güneş günü",
        "solar_day_note": "1 güneş günü = {d} Dünya günü",
        "turns": "tur",
        "million_km": "milyon km",
        "kms": "km/sn",
        "au": "AB",
        "start": "Başlangıç",
        "kepler": "Güneş'e yaklaştıkça hızlanıyor",
        "kepler_sub": "Kepler'in 2. yasası",
        "result_title": "{n} DÜNYA GÜNÜNDE",
        "result_line1": "{p} {d} yol aldı",
        "result_line2": "Güneş çevresinde {a} ilerledi",
        "result_line3": "tam turun {pct} · yörünge süresinin {tpct}",
        "extra": "EK BİLGİ",
        "table_title": "{n} DÜNYA GÜNÜNDE İLERLEME",
        "pending": "sırada",
        "same_n": "Aynı {n} gün: {p}",
        "rewind": "Başlangıca dönülüyor",
        "scale_note": "Gezegen ve Güneş boyutları büyütülmüştür",
        "closeup": "YAKIN PLAN",
        "legend_orbit": "soluk: tam yörünge",
        "legend_path": "parlak: {n} günde katedilen yol",
    },
    "en": {
        "question": "While {n} days pass on Earth, how far do the other planets move?",
        "clock": "EARTH CLOCK",
        "day_of": "Day {d} / {n}",
        "experiment": "EXPERIMENT · {n} EARTH DAYS",
        "distance": "Distance travelled",
        "angle": "Motion around the Sun",
        "angle_note": "{p} of a full lap",
        "speed": "Current speed",
        "sun_dist": "Distance to the Sun",
        "spin": "Spin on its axis",
        "solar_days": "Solar days passed",
        "solar_day_note": "1 solar day = {d} Earth days",
        "turns": "turns",
        "million_km": "million km",
        "kms": "km/s",
        "au": "AU",
        "start": "Start",
        "kepler": "Faster as it nears the Sun",
        "kepler_sub": "Kepler's second law",
        "result_title": "IN {n} EARTH DAYS",
        "result_line1": "{p} travelled {d}",
        "result_line2": "moved {a} around the Sun",
        "result_line3": "{pct} of a full lap · {tpct} of its orbital period",
        "extra": "ALSO",
        "table_title": "PROGRESS IN {n} EARTH DAYS",
        "pending": "next",
        "same_n": "Same {n} days: {p}",
        "rewind": "Back to the start",
        "scale_note": "Planet and Sun sizes are enlarged",
        "closeup": "CLOSE-UP",
        "legend_orbit": "faint: full orbit",
        "legend_path": "bright: path in {n} days",
    },
}


# ── number formatting ───────────────────────────────────────────────────
def fmt(x: float, decimals: int, lang: str) -> str:
    """1234567.891 -> '1.234.567,9' (tr) / '1,234,567.9' (en)."""
    s = f"{abs(x):,.{decimals}f}"
    if lang == "tr":
        s = s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return ("-" if x < 0 and float(s.replace(".", "").replace(",", "") or 0) != 0 else "") + s


def pct(x: float, decimals: int, lang: str) -> str:
    v = fmt(100.0 * x, decimals, lang)
    return f"%{v}" if lang == "tr" else f"{v}%"


def decimals_for(final_value: float) -> int:
    """Few meaningful decimals, chosen once per scene from the final value."""
    a = abs(final_value)
    return 0 if a >= 20 else (1 if a >= 2 else 2)


def tr_suffix(number_text: str, kind: str) -> str:
    """Turkish case suffix after a number word: '%27'si', '%34'ü' (vowel harmony
    of the spoken last word). kind: 'i' (accusative) is enough for our lines."""
    last = number_text.rstrip("°%").replace(".", "").replace(",", "")[-1:]
    table = {"0": "ı", "1": "i", "2": "si", "3": "ü", "4": "ü", "5": "i", "6": "sı",
             "7": "si", "8": "i", "9": "u"}
    suf = table.get(last, "i")
    # two-digit round numbers are read by their tens word
    digits = number_text.strip("%°").split(",")[0].replace(".", "")
    if len(digits) >= 2 and digits.endswith("0"):
        tens = {"1": "u", "2": "si", "3": "u", "4": "ı", "5": "si", "6": "ı", "7": "i",
                "8": "i", "9": "ı"}
        suf = tens.get(digits[-2], suf)
        if digits.endswith("00"):
            suf = "i" if digits.endswith("000") else "ü"
    return f"{number_text}'{suf}"
