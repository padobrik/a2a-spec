"""Render docs/demo.gif from a real run of the customer support example.

Every command shown in the GIF is executed for real on a fresh copy of
examples/customer_support, and the frames are drawn from its actual output.
If a command's exit code differs from what the story expects, the script
stops instead of rendering.

    pip install -e ".[dev]" pillow
    python scripts/demo_gif.py --out docs/demo.gif
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "customer_support"

COLS, ROWS = 88, 27
FONT_SIZE, LINE_H, PAD, BAR_H = 15, 21, 18, 30
BG, BAR, FG = (13, 17, 23), (31, 36, 44), (201, 209, 217)
GREEN, RED, GRAY, BLUE = (63, 185, 80), (248, 81, 73), (125, 133, 144), (88, 166, 255)

HIGHLIGHTS = [
    (re.compile(r"\b(PASSED|PASS|\d+ passed)\b"), GREEN),
    (re.compile(r"\b(FAILED|FAIL|\d+ failed)\b|violated|'\w+' is a required property"), RED),
    (re.compile(r"\bWrote\b"), GREEN),
]


@dataclass
class Step:
    text: str
    comment: bool = False
    expect_exit: int = 0
    output: list[str] = field(default_factory=list)


STEPS = [
    Step("# resolution-agent reads two fields from triage-agent", comment=True),
    Step('grep -n "input_data.get" agents/resolution.py'),
    Step("# infer the contract from the consumer's code", comment=True),
    Step(
        "handshake infer -p triage-agent -C resolution-agent \\\n"
        "    --source agents/resolution.py:resolution_agent"
    ),
    Step("pytest -q"),
    Step('# simulate a prompt change: triage-agent now says "urgency"', comment=True),
    Step('sed -i.bak \'s/"priority"/"urgency"/\' agents/triage.py'),
    Step("handshake record --scenario billing_overcharge"),
    Step("pytest -v --no-header -k billing", expect_exit=1),
    Step("# the hand-written spec passed; the inferred contract caught it", comment=True),
]


def prepare(workdir: Path) -> None:
    """Copy the example and enable the pytest plugin (setup, not shown)."""
    shutil.copytree(EXAMPLE, workdir)
    shutil.rmtree(workdir / "tests")
    config = (workdir / "handshake" / "handshake.yaml").read_text()
    # Semantic rules are not part of this story; skip loading the model.
    (workdir / "handshake.yaml").write_text(config.replace("enabled: true", "enabled: false"))
    (workdir / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        'handshake_config = "handshake.yaml"\n'
        'testpaths = ["handshake/specs"]\n'
    )


def run(steps: list[Step], workdir: Path) -> None:
    env = {
        **os.environ,
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
        "NO_COLOR": "1",
        "TERM": "dumb",
        "COLUMNS": str(COLS),
    }
    for step in steps:
        if step.comment:
            continue
        proc = subprocess.run(
            step.text,
            shell=True,
            cwd=workdir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if proc.returncode != step.expect_exit:
            sys.exit(
                f"'{step.text}' exited {proc.returncode}, expected {step.expect_exit}:\n"
                f"{proc.stdout}"
            )
        lines = proc.stdout.rstrip("\n").splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        step.output = [chunk for line in lines for chunk in _wrap(line)]


def _wrap(line: str) -> list[str]:
    line = line.rstrip()
    return [line[i : i + COLS] for i in range(0, len(line), COLS)] or [""]


class Renderer:
    def __init__(self) -> None:
        self.font = _font()
        self.char_w = round(self.font.getlength("M"))
        self.width = PAD * 2 + COLS * self.char_w
        self.height = BAR_H + PAD * 2 + ROWS * LINE_H
        self.screen: list[tuple[str, str]] = []  # (kind, text)
        self.frames: list[Image.Image] = []
        self.durations: list[int] = []

    def frame(self, ms: int, cursor: bool = False) -> None:
        img = Image.new("RGB", (self.width, self.height), BG)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, self.width, BAR_H], fill=BAR)
        for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
            x = PAD + i * 20
            draw.ellipse([x, 10, x + 11, 21], fill=color)
        title = "agent-handshake: inferred contracts"
        draw.text(
            ((self.width - self.font.getlength(title)) / 2, 7), title, font=self.font, fill=GRAY
        )
        visible = self.screen[-ROWS:]
        for row, (kind, text) in enumerate(visible):
            y = BAR_H + PAD + row * LINE_H
            self._line(draw, y, kind, text)
            if cursor and row == len(visible) - 1:
                x = PAD + (len(text) + (2 if kind == "cmd" else 0)) * self.char_w
                draw.rectangle([x, y + 2, x + self.char_w - 1, y + LINE_H - 3], fill=FG)
        self.frames.append(img)
        self.durations.append(ms)

    def _line(self, draw: ImageDraw.ImageDraw, y: int, kind: str, text: str) -> None:
        x = PAD
        if kind == "cmd":
            draw.text((x, y), "$ ", font=self.font, fill=GREEN)
            x += 2 * self.char_w
            draw.text((x, y), text, font=self.font, fill=FG)
            return
        if kind == "comment":
            draw.text((x, y), text, font=self.font, fill=GRAY)
            return
        spans = sorted(
            (m.start(), m.end(), color) for rx, color in HIGHLIGHTS for m in rx.finditer(text)
        )
        pos = 0
        for start, end, color in spans:
            if start < pos:
                continue
            draw.text((x + pos * self.char_w, y), text[pos:start], font=self.font, fill=FG)
            draw.text((x + start * self.char_w, y), text[start:end], font=self.font, fill=color)
            pos = end
        draw.text((x + pos * self.char_w, y), text[pos:], font=self.font, fill=FG)

    def type_line(self, kind: str, text: str) -> None:
        width = COLS - (2 if kind == "cmd" else 0)
        chunks = [text[i : i + width] for i in range(0, len(text), width)] or [""]
        for n, chunk in enumerate(chunks):
            self.screen.append((kind if n == 0 else "cont", ""))
            for i in range(0, len(chunk) + 1, 3):
                self.screen[-1] = (self.screen[-1][0], chunk[:i])
                self.frame(30, cursor=True)
            self.screen[-1] = (self.screen[-1][0], chunk)
        self.frame(350, cursor=True)

    def play(self, steps: list[Step]) -> None:
        self.screen.append(("cmd", ""))
        self.frame(600, cursor=True)
        self.screen.pop()
        for step in steps:
            first, *rest = step.text.split("\n")
            self.type_line("comment" if step.comment else "cmd", first)
            for cont in rest:
                self.type_line("cont", cont)
            for line in step.output:
                self.screen.append(("out", line))
                self.frame(45)
            self.frame(1400 if step.output else 500)
        self.frame(5000)

    def save(self, out: Path) -> None:
        palette = [f.convert("P", palette=Image.Palette.ADAPTIVE, colors=32) for f in self.frames]
        palette[0].save(
            out,
            save_all=True,
            append_images=palette[1:],
            duration=self.durations,
            loop=0,
            optimize=True,
            disposal=1,
        )


def _font() -> ImageFont.FreeTypeFont:
    for path in (
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "C:/Windows/Fonts/consola.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, FONT_SIZE)
    sys.exit("No monospace font found; edit _font() in scripts/demo_gif.py")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "demo.gif")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp) / "customer_support"
        prepare(workdir)
        run(STEPS, workdir)

    renderer = Renderer()
    renderer.play(STEPS)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    renderer.save(args.out)
    total = sum(renderer.durations) / 1000
    size = args.out.stat().st_size / 1024
    print(f"{args.out}: {len(renderer.frames)} frames, {total:.1f}s, {size:.0f} KiB")


if __name__ == "__main__":
    main()
