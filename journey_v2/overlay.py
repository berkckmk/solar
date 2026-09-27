"""2D information layer (Pillow): orbits, path, angle arc, labels, panels, table.

Everything is computed from journey_v2.timeline (same clock, same camera as the
3D pass). Text lives in screen space, digits are tabular (fixed cells) so
changing numbers never shift the layout, and every text box / body is recorded
so layout QA can check collisions frame by frame.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from . import camera as C
from . import layout as L
from .timeline import FPS, Sample, metrics, orbit_points, pos

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
SS = 2                                               # supersampling factor
DIGITS = set("0123456789")


def _rgba(rgb, a):
    return (int(rgb[0]), int(rgb[1]), int(rgb[2]), int(max(0, min(1, a)) * 255))


def _lerp(a, b, u):
    return a + (b - a) * u


class Canvas:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.W, self.H = w * SS, h * SS
        self.layers = {k: Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
                       for k in ("shade", "lines", "marks", "text")}
        self.draw = {k: ImageDraw.Draw(v) for k, v in self.layers.items()}
        self._fonts = {}
        self.boxes = []                              # (kind, name, (x0, y0, x1, y1) normalised)

    # coordinates
    def X(self, u): return u * self.W
    def Y(self, v): return v * self.H
    def S(self, frac): return frac * self.H          # size given as fraction of height

    def font(self, weight: str, frac: float):
        key = (weight, round(frac * self.H))
        if key not in self._fonts:
            self._fonts[key] = ImageFont.truetype(str(FONT_DIR / f"Inter-{weight}.ttf"), max(6, key[1]))
        return self._fonts[key]

    # text -----------------------------------------------------------------
    def measure(self, s: str, weight: str, frac: float, track: float = 0.0) -> float:
        f = self.font(weight, frac)
        dw = max(f.getlength(d) for d in DIGITS)
        w = 0.0
        for ch in s:
            w += dw if ch in DIGITS else f.getlength(ch)
            w += track * f.size
        return w / self.W

    def text(self, u, v, s, weight="Medium", frac=0.02, rgb=L.WHITE, alpha=1.0, align="left",
             track=0.0, kind="text", name="", stroke=True):
        """Draw s with its baseline at (u, v); digits in fixed-width cells."""
        if alpha <= 0.01 or not s:
            return None
        f = self.font(weight, frac)
        d = self.draw["text"]
        dw = max(f.getlength(ch) for ch in DIGITS)
        width = self.measure(s, weight, frac, track) * self.W
        x = self.X(u) - (width if align == "right" else (width / 2 if align == "center" else 0))
        y = self.Y(v)
        fill = _rgba(rgb, alpha)
        kw = {"stroke_width": max(1, round(0.07 * f.size)), "stroke_fill": _rgba((0, 0, 0), 0.55 * alpha)} \
            if stroke else {}
        x0 = x
        run = ""
        for ch in s + "\0":
            if ch not in DIGITS and ch != "\0" and track == 0.0:
                run += ch
                continue
            if run:
                d.text((x, y), run, font=f, fill=fill, anchor="ls", **kw)
                x += f.getlength(run)
                run = ""
            if ch == "\0":
                break
            if ch in DIGITS:
                cw = f.getlength(ch)
                d.text((x + (dw - cw) / 2, y), ch, font=f, fill=fill, anchor="ls", **kw)
                x += dw + track * f.size
            else:
                d.text((x, y), ch, font=f, fill=fill, anchor="ls", **kw)
                x += f.getlength(ch) + track * f.size
        asc, desc = f.getmetrics()
        box = (x0 / self.W, (y - 0.8 * asc) / self.H, x / self.W, (y + 0.25 * desc) / self.H)
        self.boxes.append((kind, name, box))
        return box

    # graphics -------------------------------------------------------------
    def polyline(self, uv, rgb, alpha, width_frac, layer="lines", occluders=(), dash=None):
        if alpha <= 0.01 or len(uv) < 2:
            return
        d = self.draw[layer]
        w = max(1, round(self.S(width_frac)))
        fill = _rgba(rgb, alpha)
        if occluders:
            dense = [uv[0]]
            for a, b in zip(uv, uv[1:]):
                n = max(1, int(math.hypot((b[0] - a[0]) * self.W / self.H, b[1] - a[1]) / 0.004))
                dense += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(1, n + 1)]
            uv = dense
        seg = []
        segs = []
        for (u, v) in uv:
            hidden = any((u - cu) ** 2 * (self.W / self.H) ** 2 + (v - cv) ** 2 < r * r
                         for cu, cv, r in occluders)
            if hidden:
                if len(seg) > 1:
                    segs.append(seg)
                seg = []
            else:
                seg.append((self.X(u), self.Y(v)))
        if len(seg) > 1:
            segs.append(seg)
        for s in segs:
            if dash:
                on, off = self.S(dash[0]), self.S(dash[1])
                acc, drawing = 0.0, True
                cur = [s[0]]
                for a, b in zip(s, s[1:]):
                    L_ = math.dist(a, b)
                    pos_ = 0.0
                    while pos_ < L_:
                        step = min((on if drawing else off) - acc, L_ - pos_)
                        pos_ += step
                        acc += step
                        pt = (a[0] + (b[0] - a[0]) * pos_ / L_, a[1] + (b[1] - a[1]) * pos_ / L_)
                        if drawing:
                            cur.append(pt)
                        if acc >= (on if drawing else off) - 1e-9:
                            if drawing and len(cur) > 1:
                                d.line(cur, fill=fill, width=w)
                            drawing, acc, cur = not drawing, 0.0, [pt]
                if drawing and len(cur) > 1:
                    d.line(cur, fill=fill, width=w)
            else:
                d.line(s, fill=fill, width=w, joint="curve")

    def circle(self, u, v, r_frac, rgb, alpha, width_frac=None, fill=False, layer="marks"):
        if alpha <= 0.01:
            return
        r = self.S(r_frac)
        x, y = self.X(u), self.Y(v)
        c = _rgba(rgb, alpha)
        if fill:
            self.draw[layer].ellipse((x - r, y - r, x + r, y + r), fill=c)
        else:
            self.draw[layer].ellipse((x - r, y - r, x + r, y + r), outline=c,
                                     width=max(1, round(self.S(width_frac or 0.0015))))

    def rect(self, box, rgb, alpha, width_frac=0.0015, fill=False, layer="marks"):
        if alpha <= 0.01:
            return
        b = (self.X(box[0]), self.Y(box[1]), self.X(box[2]), self.Y(box[3]))
        if fill:
            self.draw[layer].rectangle(b, fill=_rgba(rgb, alpha))
        else:
            self.draw[layer].rectangle(b, outline=_rgba(rgb, alpha), width=max(1, round(self.S(width_frac))))

    def disc_image(self, u, v, r_frac, img, alpha, layer="marks"):
        """Round window: a dark backing disc with `img` (square RGBA) clipped to it."""
        if alpha <= 0.01:
            return
        r = self.S(r_frac)
        d = int(round(2 * r))
        x0, y0 = int(round(self.X(u) - r)), int(round(self.Y(v) - r))
        mask = Image.new("L", (d, d), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, d - 1, d - 1), fill=int(255 * alpha))
        back = Image.new("RGBA", (d, d), (5, 7, 11, 0))
        back.putalpha(mask.point(lambda m: int(m * 0.85)))
        self.layers[layer].alpha_composite(back, (x0, y0))
        if img is not None:
            im = img.convert("RGBA").resize((d, d), Image.LANCZOS)
            im.putalpha(ImageChops.multiply(im.getchannel("A"), mask))
            self.layers[layer].alpha_composite(im, (x0, y0))

    def shade(self, side: str, extent: float, alpha: float):
        """Very light dark gradient behind a text column ('left', 'right', 'top')."""
        if alpha <= 0.01:
            return
        n = 48
        d = self.draw["shade"]
        for i in range(n - 1, -1, -1):              # outer (faint) first, inner overwrite darker
            a1 = (i + 1) / n
            k = alpha * 0.5 * (1.0 - i / n) ** 1.6
            if side == "left":
                b = (0, 0, self.X(extent * a1), self.H)
            elif side == "right":
                b = (self.X(1 - extent * a1), 0, self.W, self.H)
            else:
                b = (0, 0, self.W, self.Y(extent * a1))
            d.rectangle(b, fill=(0, 0, 0, int(255 * k)))

    def image(self) -> Image.Image:
        out = self.layers["shade"]
        for k in ("lines", "marks", "text"):
            out = Image.alpha_composite(out, self.layers[k])
        return out.resize((self.w, self.h), Image.LANCZOS)


LABEL_AREA = (L.SAFE, L.TOP_BAND[3], 1 - L.SAFE, 1 - L.SAFE)   # planet labels stay below the title band


def _inside(b, area=LABEL_AREA):
    """How far box b sits inside area (negative once it pokes out)."""
    return min(b[0] - area[0], area[2] - b[2], b[1] - area[1], area[3] - b[3])


class LabelPlacer:
    """Keeps each label on one of a few preset spots; switches only when the
    current spot collides, and glides to the new spot instead of jumping.
    The glide acts on the offset from the planet, so a label stays attached
    to its planet while the camera moves."""
    SPOTS = ((1, -1), (1, 0), (1, 1), (-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1))

    def __init__(self):
        self.state = {}

    def place(self, key, anchor, r, size, obstacles, soft, aspect, sequential=True):
        (u, v), (w, h) = anchor, size
        gap = 0.010

        def offset_for(i):
            sx, sy = self.SPOTS[i]
            return (sx * ((r + gap) / aspect + w / 2), sy * (r + gap + h / 2))

        def box_at(off):
            cx, cy = u + off[0], v + off[1]
            return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)

        def box_for(i):
            return box_at(offset_for(i))

        def hits(b):
            if _inside(b) < 0:
                return 99
            return sum(1 for o in obstacles if _overlap(b, o))

        def soft_cost(b):
            return sum(1 for (pu, pv) in soft if b[0] <= pu <= b[2] and b[1] <= pv <= b[3])

        prev = self.state.get(key)
        choice = None
        if prev is not None and hits(box_for(prev["spot"])) == 0:
            choice = prev["spot"]
        else:
            best = None
            for i in range(len(self.SPOTS)):
                b = box_for(i)
                cost = hits(b) * 1000 + soft_cost(b) + i * 0.1
                if best is None or cost < best[0]:
                    best = (cost, i)
            choice = best[1]
        target = offset_for(choice)
        if prev is not None and sequential:
            k = 1.0 - math.exp(-(1.0 / FPS) / 0.12)
            off = (_lerp(prev["off"][0], target[0], k), _lerp(prev["off"][1], target[1], k))
        else:
            off = target
        self.state[key] = {"spot": choice, "off": off}
        return box_at(off)


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _circle_box(u, v, r_frac, aspect):
    return (u - r_frac / aspect, v - r_frac, u + r_frac / aspect, v + r_frac)


# ═══════════════════════════════════════════════════════════════════════
class Overlay:
    def __init__(self, sample: Sample, res, lang: str, debug: bool = False, inset_dir: Path | None = None):
        self.s, self.res, self.lang, self.debug = sample, res, lang, debug
        self.inset_dir = inset_dir
        self.T = L.S[lang]
        self.N = L.NAMES[lang]
        self.aspect = res[0] / res[1]
        self.placer = LabelPlacer()
        final = metrics(sample.planet, sample.days, sample.days)
        self.dec = {
            "km": L.decimals_for(final["km"] / 1e6),
            "deg": L.decimals_for(final["swept_deg"]),
            "speed": 1, "au": 2,
        }
        self.final = final
        self.fly_src = (L.SAFE, 0.41)       # set again by the info column each frame

    # number helpers
    def n(self, x, dec):
        return L.fmt(x, dec, self.lang)

    def day_text(self, c):
        return self.T["day_of"].format(d=self.n(c, 1), n=self.n(self.s.days, 0))

    def project(self, pose, p):
        pr = C.project(pose, p)
        return (pr[0], pr[1]) if pr else None

    # ── frame ────────────────────────────────────────────────────────────
    def render(self, f: int, sequential=True):
        s, T = self.s, self.T
        t = f / FPS
        c = s.days_at(t)
        pose = s.pose(t)
        ui = s.ui(t)
        cv = Canvas(*self.res)
        A = self.aspect
        P = s.planet
        acc = L.ACCENT[P]
        m = metrics(P, s.days, c)

        # bodies on screen
        bodies = {}
        for name in s.shown:
            uv = self.project(pose, pos(name, c))
            if uv and -0.1 < uv[0] < 1.1 and -0.1 < uv[1] < 1.1:
                bodies[name] = (uv[0], uv[1], s.planet_px(name, t))
        sun_uv = self.project(pose, (0.0, 0.0, 0.0))
        sun_r = s.sun_px(pose)
        occl = [(sun_uv[0], sun_uv[1], cv.S(sun_r) / cv.H * 1.05)] + \
               [(u, v, r * 1.25) for (u, v, r) in bodies.values()]
        occl = [(u, v, r) for (u, v, r) in occl]

        # gradients behind text
        cv.shade("top", 0.24, 0.9)
        cv.shade("left", 0.34, ui["panel"])
        cv.shade("right", 0.33, ui["table"])

        # orbits
        fw = ui["focus"]
        for name in s.context:
            uv = [self.project(pose, p) for p in orbit_points(name)]
            uv = [q for q in uv if q]
            if name == P:
                a = _lerp(0.22, 0.38, ui["select"]) + 0.55 * ui["pulse"]
                col = acc if ui["select"] > 0.01 else L.WHITE
                w = 0.0019 + 0.0016 * ui["pulse"]
            elif name == s.next_planet:
                a = _lerp(0.22, 0.6, ui["next"]) * (1 - 0.5 * fw)
                col = L.ACCENT[name] if ui["next"] > 0.01 else L.WHITE
                w = 0.0019 + 0.0008 * ui["next"]
            else:
                a, col, w = 0.2 * (1 - 0.75 * fw), L.WHITE, 0.0019
            cv.polyline(uv, col, a, w, occluders=[(u, v, r) for (u, v, r) in occl])

        # path travelled (accent, bright) and start marker
        if ui["path"] > 0.01 and c > 0:
            n = max(2, int(240 * c / s.days) + 2)
            pts = [self.project(pose, pos(P, c * i / (n - 1))) for i in range(n)]
            own = [(bodies[P][0], bodies[P][1], bodies[P][2] * 1.1)] if P in bodies else []
            cv.polyline([q for q in pts if q], acc, 0.95 * ui["path"], 0.0036, occluders=own)
        start_uv = self.project(pose, pos(P, 0.0))
        sm = ui["start_marker"] * fw
        if sm > 0.01 and start_uv:
            r = s.planet_px(P, t) * 0.75
            cv.circle(start_uv[0], start_uv[1], r, acc, 0.6 * sm, 0.0016)
            out_dir = (start_uv[0] - sun_uv[0], start_uv[1] - sun_uv[1])
            ln = math.hypot(out_dir[0] * A, out_dir[1]) or 1
            lu = start_uv[0] + out_dir[0] / ln * (r + 0.03)
            lv = start_uv[1] + out_dir[1] / ln * (r + 0.03)
            cv.text(lu, lv + 0.006, T["start"], "Medium", 0.0145, L.MUTED, 0.9 * sm,
                    align="center", kind="label", name="start")

        # swept-angle arc around the Sun (its own radius, separate from the orbit)
        if ui["angle_arc"] > 0.01 and c > 0:
            self._angle_arc(cv, pose, sun_uv, sun_r, P, c, m, ui["angle_arc"], bodies)

        # close-up window (rendered by the 3D pass), before the labels are placed
        self._inset(cv, ui, m, f)

        # screen-space text first, then planet labels placed around it
        self._top_band(cv, ui, c, t)
        self._info_column(cv, ui, m, c)
        self._table(cv, ui, t)
        cv.text(1 - L.SAFE, 1 - L.SAFE, T["scale_note"], "Regular", 0.0135, L.FAINT,
                0.9 * ui["scale_note"], align="right", kind="note")
        self._planet_labels(cv, pose, bodies, ui, t, sequential, occl, sun_uv, sun_r)

        if self.debug:
            self._debug(cv, pose, sun_uv)
        img = cv.image()
        qa = self._qa(cv, bodies, sun_uv, sun_r, ui)
        return img, qa

    # ── pieces ───────────────────────────────────────────────────────────
    def _angle_arc(self, cv, pose, sun_uv, sun_r, P, c, m, a, bodies):
        start = pos(P, 0.0)
        a0 = math.atan2(start[1], start[0])
        sweep = math.radians(min(m["swept_deg"], 359.0))
        # radius: ~7.5 % of the frame height, never beyond 55 % of the Sun-planet gap
        cur = bodies.get(P)
        wpp = C.world_per_pixel(pose, C.project(pose, (0, 0, 0))[2], self.res[0])
        rho_px = 0.075 * self.res[1]
        if cur:
            gap_px = math.hypot((cur[0] - sun_uv[0]) * self.res[0], (cur[1] - sun_uv[1]) * self.res[1])
            rho_px = min(rho_px, 0.55 * gap_px)
        rho_px = max(rho_px, sun_r * self.res[1] * 2.2)
        rho = rho_px * wpp
        n = max(8, int(math.degrees(sweep) / 2))
        arc = [self.project(pose, (rho * math.cos(a0 + sweep * i / n), rho * math.sin(a0 + sweep * i / n), 0.0))
               for i in range(n + 1)]
        cv.polyline([q for q in arc if q], L.CLOCK, 0.8 * a, 0.0021)
        for end in (pos(P, 0.0), pos(P, c)):
            e = self.project(pose, end)
            if e:
                cv.polyline([sun_uv, e], L.WHITE, 0.28 * a, 0.0012, dash=(0.008, 0.007),
                            occluders=[(sun_uv[0], sun_uv[1], sun_r * 1.6)])
        mid = a0 + sweep / 2
        lab = self.project(pose, (1.55 * rho * math.cos(mid), 1.55 * rho * math.sin(mid), 0.0))
        if lab:
            txt = self.n(m["swept_deg"], self.dec["deg"]) + "°"
            cv.text(lab[0], lab[1] + 0.009, txt, "SemiBold", 0.022, L.CLOCK, a, align="center",
                    kind="label", name="angle")

    def _inset(self, cv, ui, m, f):
        a = ui.get("inset", 0.0)
        if a <= 0.01 or not self.s.inset:
            return
        u, v, r = self.s.inset
        img = None
        if self.inset_dir is not None:
            p = self.inset_dir / f"frame_{f:06d}.png"
            if p.exists():
                img = Image.open(p)
        cv.disc_image(u, v, r, img, a)
        cv.circle(u, v, r, L.ACCENT[self.s.planet], 0.45 * a, 0.0016)
        window, caption = self.s.inset_zones()
        cv.boxes.append(("inset", "inset", window))
        cv.boxes.append(("inset", "inset_caption", caption))
        T = self.T
        xr = u - r / self.aspect - 0.014                  # captions end just left of the window
        cv.text(xr, v - r + 0.020, T["closeup"], "Medium", 0.0135, L.MUTED, 0.9 * a, align="right",
                track=0.08, kind="text", name="inset_title")
        spin = f'{T["spin"]}  {self.n(m["spin_deg"], 0)}°'
        cv.text(xr, v - r + 0.050, spin, "Regular", 0.0165, L.WHITE, 0.9 * a, align="right",
                kind="text", name="inset_spin")

    def _planet_labels(self, cv, pose, bodies, ui, t, sequential, occl, sun_uv, sun_r):
        s, N, P = self.s, self.N, self.s.planet
        A = self.aspect
        fixed = [b for (k, n, b) in cv.boxes]
        obstacles_base = [L.CLOCK_BOX]
        if ui["panel"] > 0.2:
            obstacles_base.append(L.INFO_COL)
        if ui["table"] > 0.2:
            obstacles_base.append(L.TABLE_COL)
        obstacles_base.append(_circle_box(sun_uv[0], sun_uv[1], s.sun_px(pose) * 3.0, A))
        for name, (u, v, r) in bodies.items():
            if name not in s.context and name != P:
                continue
            is_sel = name == P and ui["select"] > 0.01
            is_next = name == s.next_planet and ui["next"] > 0.01
            if is_sel:
                cv.circle(u, v, r + 0.006, L.ACCENT[name], 0.55 * ui["select"], 0.0016)
            if is_next:
                cv.circle(u, v, r + 0.006, L.ACCENT[name], 0.6 * ui["next"], 0.0016)
            if name == P:
                alpha = _lerp(0.75 * (1 - ui["focus"]), 1.0, ui["name_label"]) * (1 - 0.35 * ui["next"])
                frac, weight, col = (0.026 if ui["focus"] > 0.5 else 0.021), "SemiBold", L.ACCENT[name]
            elif is_next:
                alpha, frac, weight, col = 0.75 + 0.25 * ui["next"], 0.021, "SemiBold", L.ACCENT[name]
            else:
                alpha, frac, weight, col = 0.7 * (1 - ui["focus"]), 0.0165, "Medium", L.MUTED
            if alpha <= 0.01:
                continue
            label = N[name]
            w = cv.measure(label, weight, frac)
            h = frac * 1.05
            others = [_circle_box(ou, ov, orr + 0.004, A) for on, (ou, ov, orr) in bodies.items() if on != name]
            soft = self._path_soft_points(pose, name) if name == P else []
            box = self.placer.place(name, (u, v), r, (w, h), obstacles_base + others + fixed, soft, A,
                                    sequential)
            if name != P:          # secondary labels fade out before they reach the safe margin
                alpha *= min(1.0, max(0.0, _inside(box) / 0.025))
                if alpha <= 0.01:
                    continue
            cv.text(box[0], box[3] - 0.22 * h, label, weight, frac, col, alpha, kind="label", name=name)
            # thin leader line from the planet edge to the label
            bx, by = min(max(u, box[0]), box[2]), min(max(v, box[1]), box[3])
            du, dv = (bx - u) * A, by - v
            dist = math.hypot(du, dv)
            if dist > r + 0.012:
                e0 = (u + du / dist * (r + 0.004) / A, v + dv / dist * (r + 0.004))
                cv.polyline([e0, (bx, by)], col, 0.55 * alpha, 0.0012, layer="marks")

    def _path_soft_points(self, pose, name):
        pts = [self.project(pose, p) for p in orbit_points(name, 120)]
        return [p for p in pts if p]

    def _top_band(self, cv, ui, c, t):
        s, T, N = self.s, self.T, self.N
        # clock (always)
        x1 = 1 - L.SAFE
        rewinding = ui["rewind"]
        lab = T["rewind"].upper() + "  ↺" if rewinding > 0.5 else T["clock"]
        col = L.ACCENT[s.next_planet] if rewinding > 0.5 else L.MUTED
        cv.text(x1, 0.072, lab, "Medium", 0.0165, col, ui["clock"], align="right", track=0.08,
                kind="text", name="clock_label")
        cv.text(x1, 0.128, self.day_text(c), "SemiBold", 0.040, L.CLOCK, ui["clock"], align="right",
                kind="text", name="clock")
        bar = (L.CLOCK_BOX[0], 0.148, x1, 0.1525)
        cv.rect(bar, L.FAINT, 0.6 * ui["clock"], fill=True)
        cv.rect((bar[0], bar[1], _lerp(bar[0], bar[2], c / s.days), bar[3]), L.CLOCK, ui["clock"], fill=True)

        x0 = L.SAFE
        # question (0-2 s)
        cv.text(x0, 0.112, T["question"].format(n=self.n(s.days, 0)), "Medium", 0.033, L.WHITE,
                ui["question"], kind="text", name="question")
        # experiment + planet name (focus)
        a = max(ui["panel"], ui["name_label"] * ui["focus"])
        cv.text(x0, 0.072, T["experiment"].format(n=self.n(s.days, 0)), "Medium", 0.0165, L.MUTED,
                a, track=0.08, kind="text", name="experiment")
        cv.text(x0, 0.138, N[s.planet], "SemiBold", 0.052, L.ACCENT[s.planet], a,
                kind="text", name="title")
        # next experiment (18-20 s)
        if ui["next"] > 0.01:
            head = T["same_n"].format(n=self.n(s.days, 0), p="")
            box = cv.text(x0, 0.112, head, "Medium", 0.033, L.WHITE, ui["next"], kind="text", name="next")
            if box:
                cv.text(box[2] + 0.004, 0.112, N[s.next_planet], "SemiBold", 0.033,
                        L.ACCENT[s.next_planet], ui["next"], kind="text", name="next_name")

    def _info_column(self, cv, ui, m, c):
        s, T, N = self.s, self.T, self.N
        a = ui["panel"]
        if a <= 0.01:
            return
        x = L.SAFE
        y = 0.25

        def block(label, value, unit, note=None, name=""):
            nonlocal y
            cv.text(x, y, label, "Medium", 0.0175, L.MUTED, a, kind="text", name=name + "_l")
            va = a
            if name == "angle":            # this value is what flies into the table (see _table)
                self.fly_src = (x, y + 0.052)
                va = a * (1.0 - min(1.0, 5.0 * ui["fly"]))
            box = cv.text(x, y + 0.052, value, "SemiBold", 0.046, L.WHITE, va, kind="text", name=name)
            if box and unit:
                cv.text(box[2] + 0.006, y + 0.052, unit, "Medium", 0.021, L.MUTED, a, kind="text",
                        name=name + "_u")
            if note:
                cv.text(x, y + 0.083, note, "Regular", 0.0175, L.MUTED, a, kind="text", name=name + "_n")
            y += 0.128 if note else 0.108

        block(T["distance"], self.n(m["km"] / 1e6, self.dec["km"]), T["million_km"], name="distance")
        pct = L.pct(m["lap_by_angle"], 0, self.lang)
        pct = L.tr_suffix(pct, "i") if self.lang == "tr" else pct
        block(T["angle"], self.n(m["swept_deg"], self.dec["deg"]) + "°", "",
              T["angle_note"].format(p=pct), name="angle")
        block(T["speed"], self.n(m["speed"], self.dec["speed"]), T["kms"], name="speed")

        # secondary: appears when it explains what the viewer sees
        sa = a * ui.get("sun_dist", 0.0)
        cv.text(x, y + 0.005, f'{T["sun_dist"]}  {self.n(m["sun_au"], self.dec["au"])} {T["au"]}',
                "Regular", 0.0175, L.WHITE, 0.85 * sa, kind="text", name="sun_dist")
        ka = a * ui["kepler"]
        cv.text(x, y + 0.040, T["kepler"], "Medium", 0.0185, L.ACCENT[s.planet], ka, kind="text",
                name="kepler")
        cv.text(x, y + 0.066, T["kepler_sub"], "Regular", 0.0155, L.MUTED, ka, kind="text",
                name="kepler_sub")

        # result block (12-15 s): sentence built from the computed values
        ra = min(a, ui["result"])
        yr = 0.700
        if ra > 0.01:
            f = self.final
            d_txt = f'{self.n(f["km"] / 1e6, self.dec["km"])} {T["million_km"]}'
            a_txt = self.n(f["swept_deg"], self.dec["deg"]) + "°"
            p1 = L.pct(f["lap_by_angle"], 0, self.lang)
            p2 = L.pct(f["period_fraction"], 0, self.lang)
            if self.lang == "tr":
                p1, p2 = L.tr_suffix(p1, "i"), L.tr_suffix(p2, "i")
            cv.text(x, yr, T["result_title"].format(n=self.n(s.days, 0)), "Medium", 0.0165, L.CLOCK,
                    ra, track=0.08, kind="text", name="result_title")
            cv.text(x, yr + 0.040, T["result_line1"].format(p=N[s.planet], d=d_txt), "SemiBold", 0.0215,
                    L.WHITE, ra, kind="text", name="result1")
            cv.text(x, yr + 0.072, T["result_line2"].format(a=a_txt), "SemiBold", 0.0215, L.WHITE, ra,
                    kind="text", name="result2")
            cv.text(x, yr + 0.100, T["result_line3"].format(pct=p1, tpct=p2), "Regular", 0.0155,
                    L.MUTED, ra, kind="text", name="result3")
        ea = min(a, ui["extra"])
        if ea > 0.01:
            f = self.final
            cv.text(x, yr + 0.150, T["extra"], "Medium", 0.0145, L.FAINT, ea, track=0.08, kind="text",
                    name="extra_t")
            spin = f'{T["spin"]}  {self.n(f["spin_deg"], 0)}° ({self.n(f["spin_turns"], 2)} {T["turns"]})'
            cv.text(x, yr + 0.178, spin, "Regular", 0.0155, L.MUTED, ea, kind="text", name="extra1")
            sol = f'{T["solar_days"]}  {self.n(f["solar_days"], 2)}'
            cv.text(x, yr + 0.204, sol, "Regular", 0.0155, L.MUTED, ea, kind="text", name="extra2")
            cv.text(x, yr + 0.228, T["solar_day_note"].format(d=self.n(f["solar_day_len"], 0)), "Regular",
                    0.0145, L.FAINT, ea, kind="text", name="extra3")

        # legend while the path is being drawn
        la = a * ui["legend"]
        cv.text(x, 1 - L.SAFE - 0.030, T["legend_orbit"], "Regular", 0.0145, L.MUTED, la, kind="text",
                name="legend1")
        cv.text(x, 1 - L.SAFE, T["legend_path"].format(n=self.n(s.days, 0)), "Regular", 0.0145,
                L.ACCENT[s.planet], la, kind="text", name="legend2")

    def _table(self, cv, ui, t):
        s, T, N = self.s, self.T, self.N
        a = ui["table"]
        x0, x1 = L.TABLE_COL[0], L.TABLE_COL[2]
        f = self.final
        val_txt = self.n(f["swept_deg"], self.dec["deg"]) + "°"
        row_h = 0.078
        y0 = 0.265

        def row_y(i):
            return y0 + i * row_h

        if a > 0.01:
            cv.text(x0, 0.232, T["table_title"].format(n=self.n(s.days, 0)), "Medium", 0.0150, L.MUTED, a,
                    track=0.08, kind="text", name="table_title")
            for i, name in enumerate(L.ACCENT):
                y = row_y(i) + 0.040
                done = name == s.planet and ui["row_done"] > 0.01
                is_sel = name == s.planet and ui["select"] > 0.01
                is_next = name == s.next_planet and ui["next"] > 0.01
                emph = max(ui["row_done"] if name == s.planet else 0.0, ui["next"] if is_next else 0.0)
                cv.circle(x0 + 0.008, y - 0.007, 0.0055, L.ACCENT[name], a * (0.6 + 0.4 * emph), fill=True)
                col = L.ACCENT[name] if (is_sel or is_next or done) else L.MUTED
                cv.text(x0 + 0.022, y, N[name], "SemiBold" if (is_sel or is_next) else "Medium", 0.0205, col,
                        a, kind="text", name=f"row_{name}")
                if is_sel or is_next:
                    cv.rect((x0 - 0.006, y - 0.030, x0 - 0.0035, y + 0.010), L.ACCENT[name],
                            a * max(ui["select"] if is_sel else 0, ui["next"] if is_next else 0), fill=True)
                # value / pending
                if done:
                    cv.text(x1, y, val_txt, "SemiBold", 0.0215, L.WHITE, a * ui["row_done"], align="right",
                            kind="text", name=f"val_{name}")
                    frac = min(1.0, f["lap_by_angle"])
                    by = y + 0.017
                    cv.rect((x0 + 0.022, by, x1, by + 0.004), L.FAINT, 0.5 * a, fill=True)
                    cv.rect((x0 + 0.022, by, _lerp(x0 + 0.022, x1, frac * ui["row_done"]), by + 0.004),
                            L.ACCENT[name], a, fill=True)
                elif is_next:
                    cv.text(x1, y, T["pending"], "Medium", 0.0165, L.ACCENT[name], a * ui["next"],
                            align="right", kind="text", name=f"val_{name}")
                else:
                    cv.text(x1, y, "—", "Regular", 0.0205, L.FAINT, 0.7 * a, align="right", kind="text",
                            name=f"val_{name}")

        # the result flies from the info column into its table row
        fl = ui["fly"]
        if 0.0 < fl < 1.0:
            src = self.fly_src
            dst = (x1 - self._text_w(cv, val_txt, "SemiBold", 0.0215), row_y(list(L.ACCENT).index(s.planet)) + 0.040)
            e = C.smootherstep(fl)
            u = _lerp(src[0], dst[0], e)
            v = _lerp(src[1], dst[1], e) - 0.06 * math.sin(math.pi * e)
            size = _lerp(0.046, 0.0215, e)
            cv.text(u, v, val_txt, "SemiBold", size, L.WHITE, min(1.0, 5 * fl) * (1.0 - ui["row_done"]),
                    kind="fly", name="fly")

    def _text_w(self, cv, s, weight, frac):
        return cv.measure(s, weight, frac)

    def _debug(self, cv, pose, sun_uv):
        cv.rect((L.SAFE, L.SAFE, 1 - L.SAFE, 1 - L.SAFE), (0, 220, 255), 0.9, 0.0012)
        for r, col in ((L.INFO_COL, (255, 140, 0)), (L.FOCUS_AREA, (255, 0, 200)),
                       (L.TABLE_COL, (255, 140, 0)), (L.GENERAL_AREA, (160, 255, 0)), (L.CLOCK_BOX, (255, 140, 0))):
            cv.rect(r, col, 0.8, 0.0012)
            cu, cvv = L.center(r)
            cv.polyline([(cu - 0.01, cvv), (cu + 0.01, cvv)], col, 0.8, 0.0012, layer="marks")
            cv.polyline([(cu, cvv - 0.018), (cu, cvv + 0.018)], col, 0.8, 0.0012, layer="marks")
        tgt = self.project(pose, pose.target)
        for (u, v), col in ((sun_uv, (255, 230, 0)), (tgt, (0, 255, 120))):
            cv.circle(u, v, 0.012, col, 0.95, 0.0015)
            cv.polyline([(u - 0.012, v), (u + 0.012, v)], col, 0.95, 0.0012, layer="marks")
        for kind, name, b in list(cv.boxes):
            cv.rect(b, (255, 60, 60), 0.8, 0.001)

    def _qa(self, cv, bodies, sun_uv, sun_r, ui):
        A = self.aspect
        texts = [(k, n, b) for (k, n, b) in cv.boxes if k in ("text", "label", "note", "inset")]
        issues = []
        P = self.s.planet
        sel = bodies.get(P)
        sun_box = _circle_box(sun_uv[0], sun_uv[1], sun_r, A)
        for k, n, b in texts:
            if n == P:
                continue
            if sel and _overlap(b, _circle_box(sel[0], sel[1], sel[2], A)):
                issues.append(("planet_under_text", n))
            for on, (ou, ov, orr) in bodies.items():
                if on != P and k == "text" and _overlap(b, _circle_box(ou, ov, orr, A)):
                    issues.append(("context_planet_under_text", f"{on}/{n}"))
            if _overlap(b, sun_box):
                issues.append(("sun_under_text", n))
            if not (L.SAFE - 0.002 <= b[0] and b[2] <= 1 - L.SAFE + 0.002 and L.SAFE - 0.002 <= b[1]
                    and b[3] <= 1 - L.SAFE + 0.002):
                issues.append(("outside_safe_area", n))
        labels = [(n, b) for (k, n, b) in cv.boxes if k == "label"]
        for i, (n1, b1) in enumerate(labels):
            for n2, b2 in labels[i + 1:]:
                if _overlap(b1, b2):
                    issues.append(("label_overlap", f"{n1}/{n2}"))
            for k, n, b in cv.boxes:
                if k in ("text", "inset") and _overlap(b1, b):
                    issues.append(("label_on_text", f"{n1}/{n}"))
            for name, (u, v, r) in bodies.items():
                if name != n1 and _overlap(b1, _circle_box(u, v, r, A)):
                    issues.append(("label_on_planet", f"{n1}/{name}"))
        return {"sun_uv": sun_uv, "issues": issues}
