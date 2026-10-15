"""Render a 30-second promo video (MP4, GIF and poster) for a2a-spec.

The code, spec and pytest output shown in the video come from a real run:
promo_capture builds the README example on a fresh project, runs a2aspec and
pytest, and the scenes use that output. Agents and packets are illustrations.

    pip install -e ".[dev]" pillow imageio-ffmpeg
    python scripts/promo_video.py --out docs/promo
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from PIL import Image
from promo_capture import Capture, capture
from promo_kit import BG, FPS, SANS, Canvas, H, W, clamp, ease
from promo_scene_ci import scene_ci, scene_end
from promo_scenes import scene_break, scene_flow, scene_infer, scene_title

SCENES: list[tuple[float, Callable[[Canvas, float, Capture], None]]] = [
    (3.4, scene_title),
    (4.4, scene_flow),
    (6.2, scene_break),
    (6.4, scene_infer),
    (7.0, scene_ci),
    (5.2, scene_end),
]
TRANSITION = 0.5


def compose(canvas: Canvas, cap: Capture, t: float) -> Image.Image:
    """Render time t; scene changes push the old scene left as the new one arrives."""
    start, idx = 0.0, 0
    while idx < len(SCENES) - 1 and t >= start + SCENES[idx][0]:
        start += SCENES[idx][0]
        idx += 1
    dur, scene = SCENES[idx]
    local = t - start
    zoom = 1.0 + 0.04 * clamp(local / dur)  # slow push-in
    canvas.clear(t)
    scene(canvas, local, cap)
    current = canvas.frame(zoom)
    if idx == 0 or local >= TRANSITION:
        if idx == 0 and local < 0.3:
            return Image.blend(Image.new("RGB", (W, H), BG), current, local / 0.3)
        return current
    prev_dur, prev_scene = SCENES[idx - 1]
    canvas.clear(t)
    prev_scene(canvas, prev_dur + local, cap)
    previous = canvas.frame(1.04)
    p = ease(local / TRANSITION)
    out = Image.new("RGB", (W, H), BG)
    out.paste(previous, (int(-W * 0.25 * p), 0))
    shifted = Image.new("RGB", (W, H), BG)
    shifted.paste(current, (int(W * 0.25 * (1 - p)), 0))
    return Image.blend(out, shifted, p)


def render(cap: Capture, out: Path) -> None:
    import imageio_ffmpeg

    out.mkdir(parents=True, exist_ok=True)
    total = sum(d for d, _ in SCENES)
    n = round(total * FPS)
    writer = imageio_ffmpeg.write_frames(
        str(out / "a2a-spec-promo.mp4"),
        (W, H),
        fps=FPS,
        codec="libx264",
        pix_fmt_out="yuv420p",
        quality=None,
        output_params=["-crf", "24", "-preset", "slow", "-movflags", "+faststart"],
        macro_block_size=16,
    )
    writer.send(None)
    canvas = Canvas()
    gif_frames: list[Image.Image] = []
    for i in range(n):
        t = i / FPS
        frame = compose(canvas, cap, t)
        writer.send(frame.tobytes())
        if i % 3 == 0:
            gif_frames.append(frame.resize((640, 360), Image.Resampling.LANCZOS))
        if i == n - FPS:
            frame.save(out / "a2a-spec-promo-poster.png")
    writer.close()

    gif = [f.convert("P", palette=Image.Palette.ADAPTIVE, colors=64) for f in gif_frames]
    gif[0].save(
        out / "a2a-spec-promo.gif",
        save_all=True,
        append_images=gif[1:],
        duration=1000 * 3 // FPS,
        loop=0,
        optimize=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("docs/promo"))
    args = parser.parse_args()
    if not Path(SANS).exists():
        sys.exit("This script uses the macOS SF fonts; edit SANS and MONO for your system.")
    cap = capture()
    render(cap, args.out)
    for f in sorted(args.out.iterdir()):
        print(f"{f}: {f.stat().st_size // 1024} KiB")


if __name__ == "__main__":
    main()
