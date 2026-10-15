"""Scenes 5-6: the failure caught in CI, and the closing card."""

from __future__ import annotations

import math

from promo_capture import Capture
from promo_kit import (
    AMBER,
    FG,
    GREEN,
    INDIGO,
    MUTED,
    PANEL,
    RED,
    SLATE,
    TEAL,
    Canvas,
    W,
    clamp,
    ease,
    ease_back,
    mix,
    window,
)
from promo_pieces import BAD, agent, caption, kinetic, packet, pill


def scene_ci(c: Canvas, t: float, cap: Capture) -> None:
    caption(c, t, 0.0, "The same prompt tweak, with a2a-spec in CI", y=50, size=32)
    agent(c, 60, 170, 300, 110, "PRODUCER", "triage-agent", INDIGO, window(t, 0.0, 0.5))
    agent(c, 920, 170, 300, 110, "CONSUMER", "resolution-agent", TEAL, window(t, 0.0, 0.5))

    hit = 2.0
    sa = ease_back((t - 0.3) / 0.6)
    hot = max(0.0, 1 - (t - hit) / 0.8) if t >= hit else 0.0
    shield = mix(RED, 0.35 + 0.65 * hot, INDIGO) if t >= hit else INDIGO
    h = 190 * max(sa, 0.0)
    if t > 0.3:
        c.glow(628, 225 - h / 2, 24, h, shield, 0.9 + hot, 12)
        c.box(628, 225 - h / 2, 24, h, shield, clamp(sa * 2), 12)
    c.text((640, 334), "contract", 16, MUTED, window(t, 0.7), "Semibold", anchor="ma")
    c.text(
        (640, 356),
        "category · priority",
        16,
        (165, 180, 252),
        window(t, 0.8),
        mono=True,
        anchor="ma",
    )

    if t < hit:
        p = (t - 0.7) / (hit - 0.7)
        x = 330 + 140 * (clamp(p) ** 2)  # accelerates into the shield
    else:
        b = ease((t - hit) / 0.7)
        x = 470 - 120 * b + math.sin((t - hit) * 55) * 12 * max(0.0, 1 - (t - hit) / 0.6)
    if t > 0.6:
        packet(
            c,
            x,
            112,
            BAD,
            window(t, 0.6, 0.3),
            outline=RED if t >= hit else (71, 85, 105),
            trail=1.0 if t < hit else 0.0,
            size=16,
        )
    if t >= hit:  # impact: shockwave, sparks, shake
        d = t - hit
        c.shake = 10 * max(0.0, 1 - d / 0.45)
        c.flash = ((248, 113, 113), 0.18 * max(0.0, 1 - d / 0.3))
        for k in range(2):
            rr = ease(d / 0.8 - k * 0.15) * 160
            c.ring(640, 134, rr, RED, max(0.0, 0.8 - d * 1.1 - k * 0.2), 3)
        for j in range(14):
            ang = j / 14 * 2 * math.pi + 0.3
            dist = ease(d / 0.6) * (60 + (j % 4) * 18)
            c.dot(
                640 + math.cos(ang) * dist,
                134 + math.sin(ang) * dist,
                3,
                AMBER,
                max(0.0, 1 - d / 0.6),
            )
    if t > hit + 0.2:
        m = ease_back((t - hit - 0.2) / 0.45)
        pill(
            c,
            495,
            205,
            "priority missing",
            RED,
            clamp(m * 2),
            scale=max(m, 0.01),
            size=17,
            mono=False,
        )

    ka = ease_back((t - 2.7) / 0.7)
    top = 420 + 80 * (1 - clamp(ka))
    if t > 2.7:
        c.box(170, top, 940, 200, PANEL, clamp(ka * 2), 18, outline=(51, 65, 85))
        c.text((200, top + 20), "Pull request checks", 18, MUTED, clamp(ka * 2), "Semibold")
    rows = [("a2aspec infer --check", True, 3.2), (cap.pytest_cmd.lstrip("$ "), False, 3.8)]
    for i, (label, ok, at) in enumerate(rows):
        if t < 2.9:
            continue
        ry = top + 56 + i * 40
        if t >= at:
            s = ease_back((t - at) / 0.35)
            col = GREEN if ok else RED
            r = 13 * max(s, 0.01)
            c.dot(213, ry + 13, r, col, 1.0)
            if s > 0.6:
                c.text(
                    (213, ry + 2), "✓" if ok else "✗", 18, (255, 255, 255), 1.0, "Bold", anchor="ma"
                )
        else:
            for j in range(8):
                ang = t * 8 + j * math.pi / 4
                c.dot(
                    213 + 10 * math.cos(ang), ry + 13 + 10 * math.sin(ang), 2.2, FG, 0.2 + 0.1 * j
                )
        c.text((242, ry + 1), label, 19, FG, 1.0, mono=True)
    detail = [line.strip() for line in cap.pytest_lines if "violated" in line or "required" in line]
    for i, line in enumerate(detail[:2]):
        la = window(t, 4.1 + i * 0.25, 0.3)
        c.text(
            (242 + i * 24 + 20 * (1 - la), top + 136 + i * 28),
            line[:72],
            16,
            (252, 165, 165),
            la,
            mono=True,
        )
    kinetic(c, t, 4.7, "Caught in CI. No LLM calls. No API keys.", 646, 30, FG, "Semibold", 0.07)


def scene_end(c: Canvas, t: float, cap: Capture) -> None:
    s = ease_back((t - 0.1) / 0.7)
    size = int(84 * (0.7 + 0.3 * max(s, 0.0)))
    c.text(
        (W / 2, 150 + 20 * (1 - clamp(s))),
        "a2a-spec",
        size,
        FG,
        clamp(s * 1.5),
        "Heavy",
        anchor="ma",
    )
    caption(c, t, 0.5, "Contract tests for multi-agent systems", (165, 180, 252), y=262)
    chips = ["a2aspec infer", "pytest plugin", "GitHub Action", "A2A protocol"]
    widths = [c.width(x, 20, "Semibold") + 48 for x in chips]
    total = sum(widths) + 16 * (len(chips) - 1)
    x = (W - total) / 2
    for i, (label, w) in enumerate(zip(chips, widths)):
        p = ease_back((t - 0.9 - i * 0.14) / 0.5)
        if t > 0.9 + i * 0.14:
            y = 330 + 60 * (1 - p)
            c.box(x, y, w, 46, SLATE, clamp(p * 2), 23)
            c.text((x + w / 2, y + 11), label, 20, FG, clamp(p * 2), "Semibold", anchor="ma")
        x += w + 16
    pa = ease_back((t - 1.8) / 0.5)
    if t > 1.8:
        pulse = 0.5 + 0.5 * math.sin((t - 1.8) * 4)
        pip = "pip install a2a-spec"
        pw = c.width(pip, 26, "Semibold", mono=True) + 64
        c.glow((W - pw) / 2, 420, pw, 60, INDIGO, clamp(pa) * (0.6 + 0.6 * pulse), 30)
        pill(c, W / 2, 427, pip, INDIGO, clamp(pa * 2), scale=max(pa, 0.01), size=26)
    c.text(
        (W / 2, 520),
        "github.com/padobrik/a2a-spec",
        22,
        MUTED,
        window(t, 2.3),
        mono=True,
        anchor="ma",
    )
