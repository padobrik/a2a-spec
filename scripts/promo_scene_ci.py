"""Scenes 5-6: the failure caught in CI, and the closing card."""

from __future__ import annotations

import math

from promo_capture import Capture
from promo_fx import card, check, cross, glow, gradient_text, panel, shield
from promo_kit import (
    AMBER,
    FG,
    INDIGO,
    LAVENDER,
    MUTED,
    RED,
    SLATE,
    TEAL,
    VIOLET,
    Canvas,
    W,
    clamp,
    ease,
    spring,
    window,
)
from promo_pieces import DELTA, agent, caption, kinetic, packet, pill

HIT = 2.0
SHIELD = (640, 238, 118, 148)  # cx, cy, w, h


def _impact(c: Canvas, t: float) -> None:
    d = t - HIT
    if d < 0:
        return
    c.shake = 9 * max(0.0, 1 - d / 0.45)
    c.flash = ((248, 113, 113), 0.16 * max(0.0, 1 - d / 0.3))
    x, y = SHIELD[0] - SHIELD[2] / 2 + 6, SHIELD[1]
    for k in range(3):
        r = ease(d / 0.9 - k * 0.12) * (120 + k * 40)
        c.ring(x, y, r, RED if k < 2 else AMBER, max(0.0, 0.75 - d * 0.9 - k * 0.18), 2.5 - k * 0.6)
    for j in range(18):
        ang = j / 18 * 2 * math.pi + 0.4
        dist = ease(d / 0.55) * (50 + (j * 37) % 60)
        size = 2.6 * max(0.0, 1 - d / 0.6)
        c.dot(x + math.cos(ang) * dist, y + math.sin(ang) * dist * 0.8, size, AMBER, 1.0)


def scene_ci(c: Canvas, t: float, cap: Capture) -> None:
    caption(c, t, 0.0, "The same prompt tweak, with a2a-spec in CI", y=46, size=32)
    s = spring(t / 0.8)
    agent(c, 40 - 60 * (1 - s), 178, 340, 120, "PRODUCER", "triage-agent", INDIGO, clamp(s * 1.5))
    agent(
        c, 900 + 60 * (1 - s), 178, 340, 120, "CONSUMER", "resolution-agent", TEAL, clamp(s * 1.5)
    )

    cx, cy, sw, sh = SHIELD
    grow = spring((t - 0.3) / 0.8)
    heat = max(0.0, 1 - (t - HIT) / 1.0) if t >= HIT else 0.0
    shield(
        c, cx, cy, sw * max(grow, 0.05), sh * max(grow, 0.05), VIOLET, clamp(grow * 2), heat=heat
    )
    la = window(t, 0.7)
    c.text((cx, 128), "CONTRACT", 12, MUTED, la, "Semibold", anchor="ma", tracking=2.4)
    c.text((cx, 146), "category · priority", 14, LAVENDER, la, mono=True, anchor="ma")

    if t < HIT:
        p = clamp((t - 0.6) / (HIT - 0.6))
        x, prev = 300 + 178 * p**2, 300 + 178 * clamp(p - 1 / 42) ** 2
        speed = x - prev
    else:
        b = ease((t - HIT) / 0.75)
        x = 478 - 40 * b + math.sin((t - HIT) * 50) * 8 * max(0.0, 1 - (t - HIT) / 0.6)
        speed = 0.0
    if t > 0.6:
        packet(c, x, 215, DELTA, window(t, 0.6, 0.3), alert=t >= HIT, speed=speed * 2, size=16)
    _impact(c, t)
    pop = spring((t - HIT - 0.25) / 0.7)
    pill(c, cx, 330, "priority missing", RED, clamp(pop * 3), scale=pop, size=16, mono=False)

    rise = spring((t - 2.7) / 0.9)
    top = 418 + 90 * (1 - rise)
    if t > 2.7:
        panel(c, 200, top, 880, 196, clamp(rise * 2))
        c.text(
            (228, top + 20),
            "PULL REQUEST CHECKS",
            12,
            MUTED,
            clamp(rise * 2),
            "Semibold",
            tracking=2.2,
        )
    rows = [("a2aspec infer --check", True, 3.2), (cap.pytest_cmd.lstrip("$ "), False, 3.8)]
    for i, (label, ok, at) in enumerate(rows):
        if t < 2.9:
            continue
        ry = top + 64 + i * 42
        if t >= at:
            r = 12 * spring((t - at) / 0.5)
            (check if ok else cross)(c, 242, ry, max(r, 0.1), 1.0)
        else:
            for j in range(10):
                ang = t * 7 + j * math.pi / 5
                c.dot(242 + 10 * math.cos(ang), ry + 10 * math.sin(ang), 1.9, FG, 0.12 + 0.08 * j)
        c.text((266, ry - 11), label, 18, FG, 1.0, mono=True)
    detail = [line.strip() for line in cap.pytest_lines if "violated" in line or "required" in line]
    for i, line in enumerate(detail[:2]):
        la = window(t, 4.1 + i * 0.22, 0.35)
        c.text(
            (266 + i * 22 + 18 * (1 - la), top + 128 + i * 26),
            line[:74],
            15,
            (252, 165, 165),
            la,
            mono=True,
        )
    kinetic(c, t, 4.7, "Caught in CI. No LLM calls. No API keys.", 650, 30, FG, "Semibold", 0.06)


def scene_end(c: Canvas, t: float, cap: Capture) -> None:
    a = clamp((t - 0.1) / 0.6)
    rise = spring((t - 0.1) / 0.9)
    glow(c, W / 2 - 230, 130, 460, 100, 50, INDIGO, a * 0.35, blur=60)
    gradient_text(
        c, W / 2, 128 + 30 * (1 - rise), "a2a-spec", 92, ((165, 180, 252), (94, 234, 212)), a
    )
    caption(c, t, 0.5, "Contract tests for multi-agent systems", LAVENDER, y=262)
    chips = ["a2aspec infer", "pytest plugin", "GitHub Action", "A2A protocol"]
    widths = [c.width(x, 19, "Semibold") + 50 for x in chips]
    x = (W - sum(widths) - 16 * (len(chips) - 1)) / 2
    for i, (label, w) in enumerate(zip(chips, widths)):
        p = spring((t - 0.9 - i * 0.12) / 0.8)
        if t > 0.9 + i * 0.12:
            y = 332 + 50 * (1 - p)
            card(c, x, y, w, 46, SLATE, clamp(p * 2), 23, lift=0.6)
            c.text((x + w / 2, y + 12), label, 19, FG, clamp(p * 2), "Semibold", anchor="ma")
        x += w + 16
    pop = spring((t - 1.8) / 0.8)
    if t > 1.8:
        pulse = 0.5 + 0.5 * math.sin((t - 1.8) * 3.5)
        label = "pip install a2a-spec"
        pw = c.width(label, 25, "Semibold", mono=True) + 70
        glow(c, (W - pw) / 2, 424, pw, 58, 29, INDIGO, clamp(pop) * (0.4 + 0.5 * pulse), blur=30)
        pill(c, W / 2, 431, label, INDIGO, clamp(pop * 3), scale=pop, size=25)
    c.text(
        (W / 2, 524),
        "github.com/padobrik/a2a-spec",
        21,
        MUTED,
        window(t, 2.3),
        mono=True,
        anchor="ma",
    )
