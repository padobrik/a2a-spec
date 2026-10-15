"""Core canvas for the a2a-spec promo video: easing, alpha drawing, camera."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, SS, FPS = 1280, 720, 2, 30
BG = (9, 12, 26)
FG = (236, 240, 248)
MUTED = (139, 148, 168)
INDIGO = (99, 102, 241)
VIOLET = (139, 92, 246)
TEAL = (20, 184, 166)
SLATE = (51, 65, 85)
PANEL = (15, 20, 36)
GREEN = (34, 197, 94)
RED = (239, 68, 68)
AMBER = (245, 158, 11)
LAVENDER = (165, 180, 252)
SANS = "/System/Library/Fonts/SFNS.ttf"
MONO = "/System/Library/Fonts/SFNSMono.ttf"

Color = tuple[int, int, int]


def clamp(x: float) -> float:
    return min(max(x, 0.0), 1.0)


def ease(x: float) -> float:
    """Cubic ease-out."""
    return 1 - (1 - clamp(x)) ** 3


def ease_in_out(x: float) -> float:
    x = clamp(x)
    return 4 * x**3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_back(x: float) -> float:
    """Ease-out with a small overshoot."""
    x = clamp(x)
    c1 = 1.7
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def spring(x: float, stiffness: float = 9.0, damping: float = 5.5) -> float:
    """Damped spring from 0 to 1; settles with one or two soft bounces."""
    if x <= 0:
        return 0.0
    return 1 - math.exp(-damping * x) * math.cos(stiffness * x)


def window(t: float, start: float, dur: float = 0.5) -> float:
    return ease((t - start) / dur)


def rgba(color: Color, a: float) -> tuple[int, int, int, int]:
    return (*color, round(255 * clamp(a)))


def mix(a: Color, b: Color, k: float) -> Color:
    """Linear blend from color a to color b."""
    k = clamp(k)
    return tuple(round(x + (y - x) * k) for x, y in zip(a, b))  # type: ignore[return-value]


@dataclass(frozen=True)
class Particle:
    x: float
    y: float
    depth: float  # 0 far .. 1 near
    phase: float


PARTICLES = [
    Particle((i * 97.31) % W, (i * 53.71) % H, ((i * 37) % 100) / 100, i * 0.7) for i in range(64)
]


def _bokeh(radius: int, color: Color) -> Image.Image:
    size = radius * 6
    img = Image.new("RGBA", (size, size), (*color, 0))
    ImageDraw.Draw(img).ellipse(
        [size / 2 - radius, size / 2 - radius, size / 2 + radius, size / 2 + radius],
        fill=(*color, 255),
    )
    return img.filter(ImageFilter.GaussianBlur(radius * 0.9))


class Canvas:
    """A supersampled RGB canvas with alpha-blended drawing."""

    def __init__(self) -> None:
        self.img = Image.new("RGB", (W * SS, H * SS), BG)
        self.d = ImageDraw.Draw(self.img, "RGBA")
        self._fonts: dict[tuple[str, int, str], ImageFont.FreeTypeFont] = {}
        self._cache: dict[tuple, Image.Image] = {}
        self.base = self._background()
        self.vignette = self._vignette()
        self.bokeh = [_bokeh(r * SS, (129, 140, 248)) for r in (2, 3, 5)]
        self.time = 0.0
        self.shake = 0.0
        self.flash: tuple[Color, float] | None = None
        self.parallax = 0.0

    @staticmethod
    def _background() -> Image.Image:
        small = Image.new("RGB", (W // 8, H // 8), BG)
        d = ImageDraw.Draw(small)
        d.ellipse([W // 16 - 70, H // 16 - 55, W // 16 + 70, H // 16 + 40], fill=(30, 34, 84))
        d.ellipse([W // 8 - 50, -20, W // 8 + 30, 40], fill=(20, 48, 64))
        small = small.filter(ImageFilter.GaussianBlur(22))
        return small.resize((W * SS, H * SS), Image.Resampling.BICUBIC)

    @staticmethod
    def _vignette() -> Image.Image:
        mask = Image.new("L", (W // 4, H // 4), 0)
        ImageDraw.Draw(mask).ellipse(
            [-W // 16, -H // 10, W // 4 + W // 16, H // 4 + H // 10], fill=255
        )
        mask = mask.filter(ImageFilter.GaussianBlur(40)).resize((W, H), Image.Resampling.BICUBIC)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        layer.putalpha(mask.point(lambda v: round((255 - v) * 0.55)))
        return layer

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
        self.time, self.shake, self.flash, self.parallax = time, 0.0, None, 0.0
        self.img.paste(self.base)
        for p in PARTICLES:
            speed = 4 + 22 * p.depth
            x = (p.x + speed * time) % (W + 40) - 20
            y = p.y + math.sin(time * 0.6 + p.phase) * (4 + 6 * p.depth)
            sprite = self.bokeh[min(2, int(p.depth * 3))]
            self.paste(
                sprite, x * SS - sprite.width / 2, y * SS - sprite.height / 2, 0.2 + 0.5 * p.depth
            )

    def paste(self, sprite: Image.Image, x: float, y: float, a: float = 1.0) -> None:
        """Alpha-composite an RGBA sprite (canvas pixels) with extra opacity a."""
        if a <= 0.01:
            return
        alpha = sprite.getchannel("A")
        if a < 0.99:
            alpha = alpha.point(lambda v: round(v * a))
        self.img.paste(sprite.convert("RGB"), (round(x), round(y)), alpha)

    def cached(self, key: tuple, make) -> Image.Image:
        if key not in self._cache:
            self._cache[key] = make()
        return self._cache[key]

    def text(
        self,
        xy,
        s: str,
        size: int,
        color: Color,
        a: float = 1.0,
        weight: str = "Regular",
        mono: bool = False,
        anchor: str = "la",
        tracking: float = 0.0,
    ) -> None:
        if a <= 0.02:
            return
        font = self.font(size, weight, mono)
        if not tracking:
            self.d.text((xy[0] * SS, xy[1] * SS), s, font=font, fill=rgba(color, a), anchor=anchor)
            return
        total = sum(font.getlength(ch) for ch in s) / SS + tracking * (len(s) - 1)
        x = xy[0] - (total / 2 if anchor[0] == "m" else 0)
        for ch in s:
            self.d.text(
                (x * SS, xy[1] * SS), ch, font=font, fill=rgba(color, a), anchor="l" + anchor[1]
            )
            x += font.getlength(ch) / SS + tracking

    def width(self, s: str, size: int, weight: str = "Regular", mono: bool = False) -> float:
        return self.font(size, weight, mono).getlength(s) / SS

    def box(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        color: Color,
        a: float = 1.0,
        r: int = 16,
        outline: Color | None = None,
        outline_a: float = 1.0,
    ) -> None:
        if a <= 0.02:
            return
        self.d.rounded_rectangle(
            [x * SS, y * SS, (x + w) * SS, (y + h) * SS],
            radius=r * SS,
            fill=rgba(color, a),
            outline=rgba(outline, a * outline_a) if outline else None,
            width=max(1, round(1.5 * SS)) if outline else 0,
        )

    def line(self, pts, color: Color, a: float = 1.0, width: float = 3) -> None:
        if a > 0.02:
            self.d.line(
                [(x * SS, y * SS) for x, y in pts],
                fill=rgba(color, a),
                width=round(width * SS),
                joint="curve",
            )

    def ring(self, x: float, y: float, r: float, color: Color, a: float, width: float = 3) -> None:
        if a > 0.02 and r > 0:
            self.d.ellipse(
                [(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS],
                outline=rgba(color, a),
                width=round(width * SS),
            )

    def dot(self, x: float, y: float, r: float, color: Color, a: float) -> None:
        if a > 0.02 and r > 0:
            self.d.ellipse(
                [(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], fill=rgba(color, a)
            )

    def frame(self, zoom: float = 1.0) -> Image.Image:
        img = self.img.resize((W, H), Image.Resampling.LANCZOS)
        if self.flash:
            color, a = self.flash
            img = Image.blend(img, Image.new("RGB", (W, H), color), clamp(a))
        img.paste(self.vignette, (0, 0), self.vignette)
        dx = math.sin(self.time * 90) * self.shake
        dy = math.cos(self.time * 77) * self.shake
        if zoom != 1.0 or self.shake:
            zoom = max(zoom, W / (W - 2 * abs(dx) - 2), H / (H - 2 * abs(dy) - 2))
            cw, ch = W / zoom, H / zoom
            left = min(max((W - cw) / 2 + dx, 0.0), W - cw)
            top = min(max((H - ch) / 2 + dy, 0.0), H - ch)
            img = img.resize((W, H), Image.Resampling.BICUBIC, box=(left, top, left + cw, top + ch))
        return img
