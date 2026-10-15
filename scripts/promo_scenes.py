"""Scenes 1-4: the problem and how a2aspec infer works."""

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
    TEAL,
    Canvas,
    clamp,
    ease,
    ease_back,
    window,
)
from promo_pieces import BAD, GOOD, agent, caption, kinetic, packet, pill


def scene_title(c: Canvas, t: float, cap: Capture) -> None:
    kinetic(c, t, 0.2, "Your agents talk to each other.", 260, 60, FG)
    kinetic(c, t, 1.3, "Who checks what they say?", 352, 44, (165, 180, 252), "Semibold", 0.1)
    # Two dots trading messages under the title.
    a = window(t, 1.9, 0.5)
    c.dot(520, 470, 14, INDIGO, a)
    c.dot(760, 470, 14, TEAL, a)
    for k in range(3):
        p = (t * 0.9 + k / 3) % 1.0
        c.dot(540 + 200 * p, 470, 5, (165, 180, 252), a * math.sin(math.pi * p))


def scene_flow(c: Canvas, t: float, cap: Capture) -> None:
    a = ease_back((t - 0.0) / 0.7)
    agent(c, 110 - 60 * (1 - a), 250, 330, 130, "PRODUCER", "triage-agent", INDIGO, clamp(a))
    agent(c, 840 + 60 * (1 - a), 250, 330, 130, "CONSUMER", "resolution-agent", TEAL, clamp(a))
    c.flow_arrow(450, 315, 830, MUTED, clamp(a))
    p = ease((t - 1.0) / 1.6)
    if t > 0.9:
        packet(c, 470 + 340 * p, 200, GOOD, window(t, 0.9, 0.3), trail=1.0 if p < 1 else 0.0)
    s = ease_back((t - 2.7) / 0.5)
    if t > 2.7:
        pill(c, 1005, 400, "escalate: true", GREEN, clamp(s * 2), scale=max(s, 0.01))
    caption(c, t, 0.6, "triage-agent sends data. resolution-agent depends on it.")


def scene_break(c: Canvas, t: float, cap: Capture) -> None:
    glitch = clamp((t - 2.9) / 0.2) * max(0.0, 1 - (t - 3.6) / 1.2) if t > 2.9 else 0.0
    agent(c, 110, 250, 330, 130, "PRODUCER", "triage-agent", INDIGO, 1.0)
    agent(c, 840, 250, 330, 130, "CONSUMER", "resolution-agent", TEAL, 1.0, glitch=glitch)
    c.flow_arrow(450, 315, 830, MUTED, 1.0)
    b = ease_back((t - 0.4) / 0.5)
    if t > 0.4:
        pill(
            c,
            275,
            395,
            "prompt v2",
            AMBER,
            clamp(b * 2),
            scale=max(b, 0.01),
            text_color=(17, 24, 39),
            size=17,
            mono=False,
        )
    p = ease((t - 1.0) / 1.6)
    if t > 0.9:
        packet(c, 470 + 340 * p, 200, BAD, window(t, 0.9, 0.3), trail=1.0 if p < 1 else 0.0)
    s = ease_back((t - 2.9) / 0.5)
    if t > 2.9:
        pill(c, 1005, 400, "escalate: false", RED, clamp(s * 2), scale=max(s, 0.01))
        c.flash = ((127, 29, 29), 0.22 * max(0.0, 1 - (t - 2.9) / 0.7))
    c.text(
        (1005, 466),
        'ticket.get("priority", "low")  ->  "low"',
        17,
        MUTED,
        window(t, 3.4, 0.5),
        mono=True,
        anchor="ma",
    )
    caption(c, t, 0.2, "One prompt tweak later...", AMBER, y=120)
    kinetic(
        c,
        t,
        3.7,
        "No exception. No failing test. Just wrong behavior.",
        600,
        30,
        (252, 165, 165),
        "Semibold",
        0.07,
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
    """A field chip flying from a to b along an arc, with a trail."""
    if p <= 0 or p >= 1:
        return
    for k in range(5, -1, -1):
        e = ease(max(p - k * 0.035, 0.0))
        x = a[0] + (b[0] - a[0]) * e
        y = a[1] + (b[1] - a[1]) * e - math.sin(math.pi * e) * 110
        if k:
            c.dot(x, y, 9 - k, AMBER, 0.5 - k * 0.08)
        else:
            w = c.width(label, 16, mono=True) + 22
            c.box(x - w / 2, y - 15, w, 30, AMBER, 1.0, 15)
            c.text((x, y - 9), label, 16, (17, 24, 39), 1.0, "Semibold", mono=True, anchor="ma")


def scene_infer(c: Canvas, t: float, cap: Capture) -> None:
    kinetic(c, t, 0.0, "a2aspec infer reads the consumer's code", 60, 34, FG, "Semibold", 0.06)
    a = window(t, 0.3, 0.6)
    x0 = 40 - 40 * (1 - a)
    c.box(x0, 150, 620, 230, PANEL, a, 16, outline=(51, 65, 85))
    c.text((x0 + 24, 166), "agents/resolution.py", 13, MUTED, a, mono=True)
    lines = _wrap_code(cap.consumer_code, 76)
    y = 200
    scan_y = 196 + ease((t - 0.8) / 1.4) * (len(lines) * 28 + 6)
    if 0.8 < t < 2.4:  # scanner beam
        c.box(x0 + 8, scan_y - 2, 604, 4, (165, 180, 252), 0.8, 2)
        c.box(x0 + 8, scan_y - 14, 604, 12, (99, 102, 241), 0.18, 4)
    for line in lines:
        c.text((x0 + 24, y), line, 13, FG, a, mono=True)
        for key, at in (('"priority"', 1.2), ("'category'", 1.6)):
            idx = line.find(key)
            if idx >= 0:
                hx = x0 + 24 + c.width(line[:idx], 13, mono=True)
                hw = c.width(key, 13, mono=True)
                h = window(t, at, 0.3)
                c.box(hx - 3, y - 2, hw + 6, 21, AMBER, h * 0.35, 5)
                c.text((hx, y), key, 13, AMBER, h, mono=True)
        y += 28
    fly(c, (330, 225), (905, 336), '"priority"', (t - 1.5) / 1.0)
    fly(c, (430, 255), (905, 358), "'category'", (t - 1.9) / 1.0)
    b = window(t, 2.2, 0.6)
    c.flow_arrow(668, 265, 704, MUTED, b)
    bx = 712 + 40 * (1 - b)
    c.box(bx, 150, 528, 400, PANEL, b, 16, outline=(51, 65, 85))
    c.text(
        (bx + 24, 166),
        "a2a_spec/specs/triage-agent-to-resolution-agent.yaml",
        12,
        MUTED,
        b,
        mono=True,
    )
    y = 196
    for i, line in enumerate(cap.spec_lines):
        la = window(t, 2.4 + i * 0.07, 0.25)
        hot = "priority" in line or "category" in line
        if hot and la > 0:
            c.box(bx + 18, y - 2, 492, 21, AMBER, 0.12 * la, 4)
        c.text((bx + 24 + 14 * (1 - la), y), line[:54], 15, AMBER if hot else FG, la, mono=True)
        y += 22
    caption(c, t, 3.6, "The contract comes from real usage. No YAML to write.", y=600)
