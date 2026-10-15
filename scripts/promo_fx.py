"""Effects for the promo video: soft shadows, glass cards, icons, code."""

from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFilter
from promo_kit import SS, Canvas, Color, clamp, mix, rgba
from pygments.lexers import PythonLexer, YamlLexer
from pygments.token import Comment, Keyword, Name, Number, String, Token

SYNTAX: list[tuple[object, Color]] = [
    (Keyword, (255, 123, 114)),
    (Name.Builtin, (255, 166, 87)),
    (Name.Function, (210, 168, 255)),
    (Name.Tag, (126, 231, 135)),
    (String, (165, 214, 255)),
    (Number, (121, 192, 255)),
    (Comment, (139, 148, 158)),
]
PLAIN: Color = (230, 237, 243)


def _soft_rect(w: float, h: float, r: int, blur: float, color: Color) -> Image.Image:
    pad = int(blur * 3)
    img = Image.new("RGBA", (int(w * SS) + 2 * pad, int(h * SS) + 2 * pad), (*color, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        [pad, pad, pad + int(w * SS), pad + int(h * SS)], radius=r * SS, fill=(*color, 255)
    )
    return img.filter(ImageFilter.GaussianBlur(blur))


def shadow(
    c: Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    r: int,
    a: float,
    blur: float = 26,
    dy: float = 14,
    color: Color = (0, 0, 0),
) -> None:
    """A blurred drop shadow under a rounded rectangle."""
    key = ("shadow", round(w), round(h), r, blur, color)
    sprite = c.cached(key, lambda: _soft_rect(w, h, r, blur, color))
    pad = int(blur * 3)
    c.paste(sprite, x * SS - pad, (y + dy) * SS - pad, a * 0.7)


def glow(
    c: Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    r: int,
    color: Color,
    a: float,
    blur: float = 34,
) -> None:
    """A soft colored halo around a rounded rectangle."""
    key = ("glow", round(w), round(h), r, blur, color)
    sprite = c.cached(key, lambda: _soft_rect(w, h, r, blur, color))
    pad = int(blur * 3)
    c.paste(sprite, x * SS - pad, y * SS - pad, a)


def _gradient_card(w: float, h: float, r: int, top: Color, bottom: Color) -> Image.Image:
    pw, ph = int(w * SS), int(h * SS)
    grad = Image.new("RGBA", (1, ph))
    for yy in range(ph):
        grad.putpixel((0, yy), (*mix(top, bottom, yy / max(ph - 1, 1)), 255))
    grad = grad.resize((pw, ph))
    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw - 1, ph - 1], radius=r * SS, fill=255)
    grad.putalpha(mask)
    edge = ImageDraw.Draw(grad, "RGBA")  # glassy rim: bright top, faint sides
    edge.rounded_rectangle(
        [0, 0, pw - 1, ph - 1], radius=r * SS, outline=(255, 255, 255, 38), width=max(1, SS)
    )
    edge.line([(r * SS, SS), (pw - r * SS, SS)], fill=(255, 255, 255, 90), width=SS)
    return grad


def card(
    c: Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    color: Color,
    a: float = 1.0,
    r: int = 20,
    lift: float = 1.0,
    halo: float = 0.0,
) -> None:
    """A raised card: shadow, optional colored halo, vertical gradient and glass rim."""
    if a <= 0.02:
        return
    shadow(c, x, y, w, h, r, a * lift)
    if halo > 0:
        glow(c, x, y, w, h, r, color, a * halo)
    top = mix(color, (255, 255, 255), 0.16)
    bottom = mix(color, (0, 0, 0), 0.28)
    sprite = c.cached(
        ("card", round(w), round(h), r, color), lambda: _gradient_card(w, h, r, top, bottom)
    )
    c.paste(sprite, x * SS, y * SS, a)


def panel(c: Canvas, x: float, y: float, w: float, h: float, a: float = 1.0, r: int = 16) -> None:
    """A dark glass panel for code and checks."""
    card(c, x, y, w, h, (22, 28, 48), a, r, lift=0.8)


def check(c: Canvas, cx: float, cy: float, r: float, a: float) -> None:
    c.dot(cx, cy, r, (34, 197, 94), a)
    c.line(
        [
            (cx - r * 0.42, cy + r * 0.02),
            (cx - r * 0.1, cy + r * 0.34),
            (cx + r * 0.45, cy - r * 0.32),
        ],
        (255, 255, 255),
        a,
        width=max(r * 0.2, 1),
    )


def cross(c: Canvas, cx: float, cy: float, r: float, a: float) -> None:
    c.dot(cx, cy, r, (239, 68, 68), a)
    k = r * 0.36
    c.line([(cx - k, cy - k), (cx + k, cy + k)], (255, 255, 255), a, width=max(r * 0.2, 1))
    c.line([(cx - k, cy + k), (cx + k, cy - k)], (255, 255, 255), a, width=max(r * 0.2, 1))


def bot(c: Canvas, cx: float, cy: float, s: float, a: float, eye: Color = (255, 255, 255)) -> None:
    """A small agent glyph: rounded head, antenna, two eyes."""
    c.box(
        cx - s / 2,
        cy - s * 0.32,
        s,
        s * 0.72,
        (255, 255, 255),
        a * 0.18,
        int(s * 0.22),
        outline=(255, 255, 255),
        outline_a=0.55,
    )
    c.line([(cx, cy - s * 0.32), (cx, cy - s * 0.52)], (255, 255, 255), a * 0.6, width=2)
    c.dot(cx, cy - s * 0.56, s * 0.07, (255, 255, 255), a * 0.8)
    blink = 0.15 if (c.time % 3.1) < 0.12 else 1.0
    for side in (-1, 1):
        c.box(
            cx + side * s * 0.2 - s * 0.07,
            cy - s * 0.05 * blink,
            s * 0.14,
            s * 0.14 * blink,
            eye,
            a,
            int(s * 0.07),
        )


def shield(
    c: Canvas, cx: float, cy: float, w: float, h: float, color: Color, a: float, heat: float = 0.0
) -> None:
    """A shield-shaped contract badge with a glow that heats up on impact."""
    if a <= 0.02:
        return
    # Flat top, straight upper sides, then curves that meet at the tip.
    side = [(cx + w / 2, cy - h / 2)]
    for i in range(21):
        u = i / 20
        side.append((cx + (w / 2) * (1 - u**1.6), cy - h / 2 + h * 0.38 + (h * 0.62) * u))
    outline = side + [(2 * cx - px, py) for px, py in reversed(side)]
    tone = mix(color, (239, 68, 68), heat)
    glow(c, cx - w / 2, cy - h / 2, w, h, int(w * 0.3), tone, a * (0.5 + heat))
    c.d.polygon(
        [(px * SS, py * SS) for px, py in outline],
        fill=rgba(mix(tone, (0, 0, 0), 0.15), a),
        outline=rgba(mix(tone, (255, 255, 255), 0.4), a),
        width=round(2 * SS),
    )
    inner = [((px - cx) * 0.78 + cx, (py - cy) * 0.78 + cy - 2) for px, py in outline]
    c.d.polygon(
        [(px * SS, py * SS) for px, py in inner],
        fill=rgba(mix(tone, (255, 255, 255), 0.18), a * 0.5),
    )
    c.line(
        [(cx - w * 0.18, cy), (cx - w * 0.03, cy + h * 0.14), (cx + w * 0.2, cy - h * 0.12)],
        (255, 255, 255),
        a * (1 - heat),
        width=3,
    )


def _token_color(tok) -> Color:
    for kind, color in SYNTAX:
        if tok in kind:
            return color
    return PLAIN


def code(
    c: Canvas,
    x: float,
    y: float,
    line: str,
    size: int,
    a: float,
    lang: str = "python",
    override: dict[str, Color] | None = None,
) -> None:
    """Draw one syntax-highlighted line of code."""
    lexer = PythonLexer() if lang == "python" else YamlLexer()
    cx = x
    for tok, value in lexer.get_tokens(line):
        value = value.rstrip("\n")
        if not value:
            continue
        color = (override or {}).get(value, _token_color(tok) if tok is not Token.Text else PLAIN)
        c.text((cx, y), value, size, color, a, mono=True)
        cx += c.width(value, size, mono=True)


def gradient_text(
    c: Canvas,
    cx: float,
    y: float,
    s: str,
    size: int,
    colors: tuple[Color, Color],
    a: float,
    weight: str = "Heavy",
) -> None:
    """Centered text filled with a left-to-right gradient."""
    if a <= 0.02:
        return
    font = c.font(size, weight)
    left, top, right, bottom = font.getbbox(s)
    tw, th = right - left, bottom - top

    def make() -> Image.Image:
        mask = Image.new("L", (tw, th), 0)
        ImageDraw.Draw(mask).text((-left, -top), s, font=font, fill=255)
        grad = Image.new("RGBA", (tw, 1))
        for xx in range(tw):
            grad.putpixel((xx, 0), (*mix(colors[0], colors[1], xx / max(tw - 1, 1)), 255))
        grad = grad.resize((tw, th))
        grad.putalpha(mask)
        return grad

    sprite = c.cached(("gtext", s, size, weight, colors), make)
    c.paste(sprite, cx * SS - tw / 2, y * SS, clamp(a))


def flow_arrow(
    c: Canvas, x1: float, y: float, x2: float, color: Color, a: float = 1.0, pulse: bool = True
) -> None:
    """A dashed arrow whose dashes flow toward the head, with a travelling light pulse."""
    if a <= 0.02:
        return
    offset = (c.time * 70) % 22
    x = x1 - 22 + offset
    while x < x2 - 18:
        c.line([(max(x, x1), y), (min(x + 11, x2 - 18), y)], color, a * 0.8, width=2.5)
        x += 22
    c.d.polygon(
        [((x2 - 16) * SS, (y - 8) * SS), (x2 * SS, y * SS), ((x2 - 16) * SS, (y + 8) * SS)],
        fill=rgba(color, a),
    )
    if pulse:
        p = (c.time * 0.7) % 1.0
        px = x1 + (x2 - 18 - x1) * p
        fade = math.sin(math.pi * p)
        c.dot(px, y, 7, mix(color, (255, 255, 255), 0.5), a * 0.25 * fade)
        c.dot(px, y, 3.5, (255, 255, 255), a * 0.9 * fade)
