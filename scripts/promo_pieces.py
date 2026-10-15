"""Reusable animated pieces: captions, agents, packets and pills."""

from __future__ import annotations

import math

from promo_kit import AMBER, FG, PANEL, Canvas, W, clamp, ease_back, window


def caption(
    c: Canvas, t: float, start: float, s: str, color=FG, y: float = 620, size: int = 30
) -> None:
    a = window(t, start, 0.6)
    c.text((W / 2, y + 16 * (1 - a)), s, size, color, a, "Semibold", anchor="ma")


def kinetic(
    c: Canvas,
    t: float,
    start: float,
    words: str,
    y: float,
    size: int,
    color,
    weight: str = "Bold",
    stagger: float = 0.12,
) -> None:
    """Words drop in one by one with an overshoot."""
    parts = words.split(" ")
    space = c.width(" ", size, weight)
    total = sum(c.width(w, size, weight) for w in parts) + space * (len(parts) - 1)
    x = (W - total) / 2
    for i, word in enumerate(parts):
        p = (t - start - i * stagger) / 0.55
        if p > 0:
            e = ease_back(p)
            c.text((x, y - 40 * (1 - e)), word, size, color, clamp(p * 1.6), weight)
        x += c.width(word, size, weight) + space


def agent(
    c: Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    role: str,
    name: str,
    color,
    a: float,
    glitch: float = 0.0,
) -> None:
    jitter = math.sin(c.time * 70) * 6 * glitch
    if glitch > 0.05:  # RGB split
        c.box(x + jitter - 5, y, w, h, (220, 38, 38), a * 0.55 * glitch, 22)
        c.box(x - jitter + 5, y, w, h, (56, 189, 248), a * 0.45 * glitch, 22)
    c.glow(x, y, w, h, color, a * 0.6)
    c.box(x + jitter * 0.4, y, w, h, color, a, 22)
    c.text(
        (x + w / 2 + jitter * 0.4, y + h / 2 - 26),
        role,
        15,
        (255, 255, 255),
        a * 0.75,
        "Semibold",
        anchor="ma",
    )
    c.text(
        (x + w / 2 + jitter * 0.4, y + h / 2 - 2), name, 30, (255, 255, 255), a, "Bold", anchor="ma"
    )


def packet(
    c: Canvas,
    x: float,
    y: float,
    payload,
    a: float,
    outline=(71, 85, 105),
    trail: float = 0.0,
    size: int = 18,
) -> None:
    width = sum(c.width(s, size, mono=True) for s, _ in payload) + 36
    for k in range(4, 0, -1):  # motion trail
        if trail > 0:
            c.box(
                x - width / 2 - trail * k * 14,
                y + 4,
                width,
                36,
                (67, 56, 202),
                a * 0.12 * (5 - k),
                12,
            )
    c.box(x - width / 2, y, width, 44, PANEL, a, 12, outline=outline)
    cx = x - width / 2 + 18
    for s, color in payload:
        c.text((cx, y + 11), s, size, color, a, mono=True)
        cx += c.width(s, size, mono=True)


def pill(
    c: Canvas,
    cx: float,
    y: float,
    label: str,
    color,
    a: float,
    scale: float = 1.0,
    text_color=(255, 255, 255),
    size: int = 20,
    mono: bool = True,
) -> None:
    w = (c.width(label, size, "Semibold", mono) + 44) * scale
    h = 46 * scale
    c.box(cx - w / 2, y + (46 - h) / 2, w, h, color, a, int(23 * scale))
    if scale > 0.6:
        c.text((cx, y + 11), label, size, text_color, a, "Semibold", mono=mono, anchor="ma")


GOOD = [('{"category": "billing", ', FG), ('"priority"', FG), (': "high"}', FG)]
BAD = [('{"category": "billing", ', FG), ('"urgency"', AMBER), (': "high"}', FG)]
