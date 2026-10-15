"""Drawing primitives for the a2a-spec promo video."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

W, H, SS, FPS = 1280, 720, 2, 30
BG = (11, 16, 32)
FG = (230, 237, 243)
MUTED = (139, 148, 158)
INDIGO = (99, 102, 241)
TEAL = (13, 148, 136)
SLATE = (51, 65, 85)
PANEL = (17, 24, 39)
GREEN = (34, 197, 94)
RED = (239, 68, 68)
AMBER = (245, 158, 11)
SANS = "/System/Library/Fonts/SFNS.ttf"
MONO = "/System/Library/Fonts/SFNSMono.ttf"


def clamp(x: float) -> float:
    return min(max(x, 0.0), 1.0)


def ease(x: float) -> float:
    return 1 - (1 - clamp(x)) ** 3


def ease_back(x: float) -> float:
    """Ease out with a small overshoot."""
    x = clamp(x)
    c1 = 1.9
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def window(t: float, start: float, dur: float = 0.5) -> float:
    return ease((t - start) / dur)


def mix(color, a: float, bg=BG) -> tuple[int, int, int]:
    a = clamp(a)
    return tuple(round(b + (c - b) * a) for c, b in zip(color, bg))  # type: ignore[return-value]


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    r: float
    phase: float
    tone: float


PARTICLES = [
    Particle(
        x=(i * 97.3) % W,
        y=(i * 53.7) % H,
        vx=6 + (i * 7) % 18,
        r=1.0 + (i % 3) * 0.6,
        phase=i * 0.7,
        tone=0.25 + (i % 5) * 0.08,
    )
    for i in range(70)
]


class Canvas:
    def __init__(self) -> None:
        self.img = Image.new("RGB", (W * SS, H * SS), BG)
        self.d = ImageDraw.Draw(self.img)
        self._fonts: dict[tuple[str, int, str], ImageFont.FreeTypeFont] = {}
        self.base = self._background()
        self.time = 0.0
        self.shake = 0.0
        self.flash: tuple[tuple[int, int, int], float] | None = None

    @staticmethod
    def _background() -> Image.Image:
        glow = Image.new("RGB", (W * SS, H * SS), BG)
        gd = ImageDraw.Draw(glow)
        for i in range(40, 0, -1):
            r = i * 22 * SS
            c = mix((40, 44, 110), 0.012 * (41 - i))
            gd.ellipse(
                [W * SS / 2 - r, H * SS * 0.42 - r * 0.6, W * SS / 2 + r, H * SS * 0.42 + r * 0.6],
                fill=c,
            )
        return glow

    def font(
        self, size: int, weight: str = "Regular", mono: bool = False
    ) -> ImageFont.FreeTypeFont:
        key = (MONO if mono else SANS, size, weight)
        if key not in self._fonts:
            f = ImageFont.truetype(key[0], size * SS)
            f.set_variation_by_name(weight)
            self._fonts[key] = f
        return self._fonts[key]

    def clear(self, time: float) -> None:
        self.time, self.shake, self.flash = time, 0.0, None
        self.img.paste(self.base)
        for p in PARTICLES:  # drifting dust, always moving
            x = (p.x + p.vx * time) % W
            y = p.y + math.sin(time * 0.8 + p.phase) * 8
            r = p.r * SS
            self.d.ellipse(
                [x * SS - r, y * SS - r, x * SS + r, y * SS + r], fill=mix((129, 140, 248), p.tone)
            )

    def text(
        self,
        xy,
        s: str,
        size: int,
        color,
        a: float = 1.0,
        weight: str = "Regular",
        mono: bool = False,
        anchor: str = "la",
    ) -> None:
        if a > 0.02:
            self.d.text(
                (xy[0] * SS, xy[1] * SS),
                s,
                font=self.font(size, weight, mono),
                fill=mix(color, a),
                anchor=anchor,
            )

    def width(self, s: str, size: int, weight: str = "Regular", mono: bool = False) -> float:
        return self.font(size, weight, mono).getlength(s) / SS

    def box(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        color,
        a: float = 1.0,
        r: int = 16,
        outline=None,
    ) -> None:
        if a > 0.02:
            self.d.rounded_rectangle(
                [x * SS, y * SS, (x + w) * SS, (y + h) * SS],
                radius=r * SS,
                fill=mix(color, a),
                outline=mix(outline, a) if outline else None,
                width=2 * SS if outline else 0,
            )

    def glow(self, x: float, y: float, w: float, h: float, color, a: float, r: int = 22) -> None:
        for k in range(6, 0, -1):
            self.box(
                x - k * 5,
                y - k * 5,
                w + k * 10,
                h + k * 10,
                mix(color, 0.06 * a * (7 - k)),
                1.0,
                r + k * 5,
            )

    def line(self, pts, color, a: float = 1.0, width: int = 3) -> None:
        if a > 0.02:
            self.d.line([(x * SS, y * SS) for x, y in pts], fill=mix(color, a), width=width * SS)

    def flow_arrow(self, x1: float, y: float, x2: float, color, a: float = 1.0) -> None:
        """Arrow whose dashes move toward the head."""
        if a <= 0.02:
            return
        offset = (self.time * 80) % 24
        x = x1 - 24 + offset
        while x < x2 - 16:
            self.line([(max(x, x1), y), (min(x + 12, x2 - 16), y)], color, a)
            x += 24
        self.d.polygon(
            [((x2 - 16) * SS, (y - 9) * SS), (x2 * SS, y * SS), ((x2 - 16) * SS, (y + 9) * SS)],
            fill=mix(color, a),
        )

    def ring(self, x: float, y: float, r: float, color, a: float, width: int = 4) -> None:
        if a > 0.02:
            self.d.ellipse(
                [(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS],
                outline=mix(color, a),
                width=width * SS,
            )

    def dot(self, x: float, y: float, r: float, color, a: float) -> None:
        if a > 0.02:
            self.d.ellipse(
                [(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], fill=mix(color, a)
            )

    def frame(self, zoom: float = 1.0) -> Image.Image:
        img = self.img.resize((W, H), Image.Resampling.LANCZOS)
        if self.flash:
            color, a = self.flash
            img = Image.blend(img, Image.new("RGB", (W, H), color), clamp(a))
        dx = math.sin(self.time * 90) * self.shake
        dy = math.cos(self.time * 77) * self.shake
        if zoom != 1.0 or self.shake:
            # Leave enough margin inside the frame for the shake offset.
            zoom = max(zoom, W / (W - 2 * abs(dx) - 2), H / (H - 2 * abs(dy) - 2))
            cw, ch = W / zoom, H / zoom
            left = min(max((W - cw) / 2 + dx, 0.0), W - cw)
            top = min(max((H - ch) / 2 + dy, 0.0), H - ch)
            img = img.resize((W, H), Image.Resampling.BICUBIC, box=(left, top, left + cw, top + ch))
        return img
