"""Scenes 1-4: the problem and how a2aspec infer works."""

from __future__ import annotations

import math

from promo_capture import Capture
from promo_fx import code, flow_arrow, panel
from promo_kit import (
    AMBER,
    FG,
    GREEN,
    INDIGO,
    LAVENDER,
    MUTED,
    RED,
    TEAL,
    Canvas,
    clamp,
    ease_in_out,
    spring,
    window,
)
from promo_pieces import BAD, GOOD, agent, caption, kinetic, packet, pill

LEFT = (100, 250, 340, 120)
RIGHT = (840, 250, 340, 120)


def scene_title(c: Canvas, t: float, cap: Capture) -> None:
    kinetic(c, t, 0.2, "Your agents talk to each other.", 236, 62, FG)
    kinetic(c, t, 1.25, "Who checks what they say?", 330, 44, LAVENDER, "Semibold", 0.08)
    # Two nodes trading messages along an arc.
    a = window(t, 1.8, 0.6)
    ax, bx, y = 500, 780, 470
    c.dot(ax, y, 18, INDIGO, a * 0.25)
    c.dot(bx, y, 18, TEAL, a * 0.25)
    c.dot(ax, y, 10, INDIGO, a)
    c.dot(bx, y, 10, TEAL, a)
    for k in range(4):
        p = (t * 0.55 + k / 4) % 1.0
        e = ease_in_out(p)
        x = ax + (bx - ax) * e
        yy = y - math.sin(math.pi * e) * 46
        c.dot(x, yy, 4.5, LAVENDER, a * math.sin(math.pi * p))


def _arrive(c: Canvas, t: float, payload, start: float, alert: bool = False) -> None:
    """Fly a packet from producer to consumer, with motion blur while it moves."""
    if t <= start:
        return
    p = clamp((t - start) / 1.5)
    e = ease_in_out(p)
    prev = ease_in_out(clamp((t - start - 1 / 30) / 1.5))
    x = 520 + 240 * e
    packet(c, x, 192, payload, window(t, start, 0.25), alert=alert, speed=(e - prev) * 240)


def scene_flow(c: Canvas, t: float, cap: Capture) -> None:
    s = spring((t - 0.05) / 0.9)
    agent(c, LEFT[0] - 80 * (1 - s), *LEFT[1:], "PRODUCER", "triage-agent", INDIGO, clamp(s * 1.5))
    agent(
        c, RIGHT[0] + 80 * (1 - s), *RIGHT[1:], "CONSUMER", "resolution-agent", TEAL, clamp(s * 1.5)
    )
    flow_arrow(c, 452, 310, 828, MUTED, window(t, 0.4))
    _arrive(c, t, GOOD, 1.0)
    pop = spring((t - 2.6) / 0.7)
    pill(c, 1010, 392, "escalate: true", GREEN, clamp(pop * 3), scale=pop)
    caption(c, t, 0.7, "triage-agent sends data. resolution-agent depends on it.")


def scene_break(c: Canvas, t: float, cap: Capture) -> None:
    glitch = clamp((t - 2.6) / 0.15) * max(0.0, 1 - (t - 3.3) / 1.0) if t > 2.6 else 0.0
    agent(c, *LEFT, "PRODUCER", "triage-agent", INDIGO, 1.0)
    agent(c, *RIGHT, "CONSUMER", "resolution-agent", TEAL, 1.0, glitch=glitch)
    flow_arrow(c, 452, 310, 828, MUTED, 1.0)
    pop = spring((t - 0.35) / 0.7)
    if t > 0.35:
        ring = clamp((t - 0.35) / 0.9)
        c.ring(270, 414, 30 + 60 * ring, AMBER, 0.5 * (1 - ring), 2)
    pill(
        c,
        270,
        392,
        "prompt v2",
        AMBER,
        clamp(pop * 3),
        scale=pop,
        text_color=(23, 23, 23),
        size=16,
        mono=False,
    )
    _arrive(c, t, BAD, 1.0)
    pop = spring((t - 2.6) / 0.7)
    pill(c, 1010, 392, "escalate: false", RED, clamp(pop * 3), scale=pop)
    if t > 2.6:
        c.flash = ((127, 29, 29), 0.24 * max(0.0, 1 - (t - 2.6) / 0.6))
    hint = window(t, 3.2, 0.5)
    snippet = 'ticket.get("priority", "low")'
    hy = 456 + 8 * (1 - hint)
    code(c, 860, hy, snippet, 16, hint)
    c.text((860 + c.width(snippet, 16, mono=True) + 14, hy), '-> "low"', 16, MUTED, hint, mono=True)
    caption(c, t, 0.15, "One prompt tweak later...", AMBER, y=118)
    kinetic(
        c,
        t,
        3.6,
        "No exception. No failing test. Just wrong behavior.",
        604,
        30,
        (252, 165, 165),
        "Semibold",
        0.06,
    )


def _wrap_code(lines: list[str], width: int) -> list[str]:
    """Wrap long code lines after a comma, with a hanging indent."""
    out: list[str] = []
    for line in lines:
        indent = " " * (len(line) - len(line.lstrip()) + 4)
        while len(line) > width and ", " in line[:width]:
            cut = line[:width].rindex(", ") + 1
            out.append(line[:cut])
            line = indent + line[cut:].lstrip()
        out.append(line)
    return out


def fly(c: Canvas, a: tuple[float, float], b: tuple[float, float], label: str, p: float) -> None:
    """A field chip flying from a to b along an arc, leaving a fading trail."""
    if p <= 0 or p >= 1:
        return
    for k in range(7, -1, -1):
        e = ease_in_out(max(p - k * 0.03, 0.0))
        x = a[0] + (b[0] - a[0]) * e
        y = a[1] + (b[1] - a[1]) * e - math.sin(math.pi * e) * 120
        if k:
            c.dot(x, y, 7 - k * 0.7, AMBER, 0.45 - k * 0.05)
            continue
        w = c.width(label, 15, mono=True) + 24
        c.box(x - w / 2, y - 15, w, 30, AMBER, 1.0, 15)
        c.text((x, y - 8), label, 15, (23, 23, 23), 1.0, "Semibold", mono=True, anchor="ma")


def scene_infer(c: Canvas, t: float, cap: Capture) -> None:
    kinetic(c, t, 0.0, "a2aspec infer reads the consumer's code", 56, 34, FG, "Semibold", 0.05)
    a = window(t, 0.25, 0.6)
    x0 = 40 - 30 * (1 - a)
    panel(c, x0, 136, 620, 250, a)
    c.text((x0 + 24, 154), "agents/resolution.py", 12, MUTED, a, mono=True)
    lines = _wrap_code(cap.consumer_code, 76)
    scan = ease_in_out((t - 0.8) / 1.3)
    if 0.8 < t < 2.3:
        sy = 190 + scan * (len(lines) * 28 + 4)
        c.box(x0 + 10, sy - 18, 600, 18, INDIGO, 0.16, 4)
        c.box(x0 + 10, sy - 1, 600, 2.5, LAVENDER, 0.9, 2)
    y = 190
    for line in lines:
        for key, at in (('"priority"', 1.2), ("'category'", 1.6)):
            idx = line.find(key)
            if idx >= 0:
                hx = x0 + 24 + c.width(line[:idx], 13, mono=True)
                h = window(t, at, 0.3)
                c.box(
                    hx - 4,
                    y - 3,
                    c.width(key, 13, mono=True) + 8,
                    22,
                    AMBER,
                    0.22 * h,
                    5,
                    outline=AMBER,
                    outline_a=0.7,
                )
        code(c, x0 + 24, y, line, 13, a)
        y += 28
    fly(c, (330, 214), (905, 334), '"priority"', (t - 1.45) / 1.0)
    fly(c, (450, 244), (905, 356), "'category'", (t - 1.85) / 1.0)
    b = window(t, 2.2, 0.6)
    flow_arrow(c, 668, 260, 704, MUTED, b, pulse=False)
    bx = 712 + 30 * (1 - b)
    panel(c, bx, 136, 528, 420, b)
    c.text(
        (bx + 24, 154),
        "a2a_spec/specs/triage-agent-to-resolution-agent.yaml",
        11,
        MUTED,
        b,
        mono=True,
    )
    y = 188
    for i, line in enumerate(cap.spec_lines):
        la = window(t, 2.35 + i * 0.07, 0.3)
        if "priority" in line or "category" in line:
            c.box(bx + 16, y - 3, 496, 22, AMBER, 0.13 * la, 5)
        code(c, bx + 24 + 12 * (1 - la), y, line[:56], 14, la, lang="yaml")
        y += 22
    caption(c, t, 3.6, "The contract comes from real usage. No YAML to write.", y=612)
