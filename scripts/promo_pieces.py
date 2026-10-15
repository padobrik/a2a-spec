"""Reusable animated pieces: captions, agents, packets and pills."""

from __future__ import annotations

import math

from promo_fx import bot, card, glow
from promo_kit import AMBER, FG, PANEL, SS, Canvas, Color, W, clamp, rgba, spring, window

JSON_KEY: Color = (165, 214, 255)
JSON_STR: Color = (230, 237, 243)


def caption(
    c: Canvas, t: float, start: float, s: str, color: Color = FG, y: float = 620, size: int = 30
) -> None:
    a = window(t, start, 0.6)
    c.text((W / 2, y + 18 * (1 - a)), s, size, color, a, "Semibold", anchor="ma")


def kinetic(
    c: Canvas,
    t: float,
    start: float,
    words: str,
    y: float,
    size: int,
    color: Color,
    weight: str = "Bold",
    stagger: float = 0.09,
) -> None:
    """Words rise one by one on a soft spring."""
    parts = words.split(" ")
    space = c.width(" ", size, weight)
    total = sum(c.width(w, size, weight) for w in parts) + space * (len(parts) - 1)
    x = (W - total) / 2
    for i, word in enumerate(parts):
        p = (t - start - i * stagger) / 0.7
        if p > 0:
            e = spring(p)
            c.text((x, y + 36 * (1 - e)), word, size, color, clamp(p * 2.2), weight)
        x += c.width(word, size, weight) + space


def agent(
    c: Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    role: str,
    name: str,
    color: Color,
    a: float,
    glitch: float = 0.0,
    halo: float = 0.55,
) -> None:
    """A glass agent card with an icon, a tracked role label and the agent name."""
    jitter = math.sin(c.time * 70) * 6 * glitch
    if glitch > 0.05:  # chromatic split while the consumer misbehaves
        card(c, x + jitter - 6, y, w, h, (220, 38, 38), a * 0.5 * glitch, 22, lift=0)
        card(c, x - jitter + 6, y, w, h, (56, 189, 248), a * 0.4 * glitch, 22, lift=0)
    x += jitter * 0.4
    card(c, x, y, w, h, color, a, 22, halo=halo)
    icon = 34
    bot(c, x + 42, y + h / 2 + 4, icon, a)
    c.text((x + 80, y + h / 2 - 24), role, 13, (255, 255, 255), a * 0.7, "Semibold", tracking=2.2)
    c.text((x + 80, y + h / 2 - 4), name, 27, (255, 255, 255), a, "Bold")


def packet(
    c: Canvas,
    x: float,
    y: float,
    payload: list[tuple[str, Color]],
    a: float,
    alert: bool = False,
    speed: float = 0.0,
    size: int = 17,
) -> None:
    """A JSON message chip; speed (px per frame) adds motion-blur ghosts behind it."""
    width = sum(c.width(s, size, mono=True) for s, _ in payload) + 40
    for k in range(1, 6):
        if speed > 0.5:
            c.box(
                x - width / 2 - speed * k * 1.6,
                y + 3,
                width,
                40,
                (99, 102, 241),
                a * 0.13 * (6 - k) / 5,
                12,
            )
    if alert:
        glow(c, x - width / 2, y, width, 46, 12, (239, 68, 68), a * 0.8, blur=22)
    card(c, x - width / 2, y, width, 46, PANEL, a, 12, lift=0.9)
    if alert:
        left = x - width / 2
        c.d.rounded_rectangle(
            [left * SS, y * SS, (left + width) * SS, (y + 46) * SS],
            radius=12 * SS,
            outline=rgba((239, 68, 68), a),
            width=2 * SS,
        )
    cx = x - width / 2 + 20
    for s, color in payload:
        c.text((cx, y + 12), s, size, color, a, mono=True)
        cx += c.width(s, size, mono=True)


def pill(
    c: Canvas,
    cx: float,
    y: float,
    label: str,
    color: Color,
    a: float,
    scale: float = 1.0,
    text_color: Color = (255, 255, 255),
    size: int = 19,
    mono: bool = True,
) -> None:
    """A raised status pill that pops in with scale."""
    if scale <= 0.05 or a <= 0.02:
        return
    w = (c.width(label, size, "Semibold", mono) + 46) * scale
    h = 44 * scale
    card(c, cx - w / 2, y + (44 - h) / 2, w, h, color, a, int(22 * scale), halo=0.35)
    if scale > 0.7:
        c.text(
            (cx, y + 11),
            label,
            size,
            text_color,
            a * clamp((scale - 0.7) / 0.3),
            "Semibold",
            mono=mono,
            anchor="ma",
        )


GOOD = [
    ("{", FG),
    ('"category"', JSON_KEY),
    (": ", FG),
    ('"billing"', JSON_STR),
    (", ", FG),
    ('"priority"', JSON_KEY),
    (": ", FG),
    ('"high"', JSON_STR),
    ("}", FG),
]
BAD = [
    ("{", FG),
    ('"category"', JSON_KEY),
    (": ", FG),
    ('"billing"', JSON_STR),
    (", ", FG),
    ('"urgency"', AMBER),
    (": ", FG),
    ('"high"', JSON_STR),
    ("}", FG),
]
# Only the field that changed, for scenes where the full message does not fit.
DELTA = [("{", FG), ('"urgency"', AMBER), (": ", FG), ('"high"', JSON_STR), ("}", FG)]
