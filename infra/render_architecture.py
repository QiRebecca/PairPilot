#!/usr/bin/env python3
"""Render the submission architecture PNG from the documented system map."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1800, 1050
BACKGROUND = "#090b0a"
PANEL = "#131714"
LINE = "#343a35"
INK = "#f2f4ee"
MUTED = "#9aa29b"
LIME = "#c8ff70"
TEAL = "#79e8ca"
VIOLET = "#b9a7ff"

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "architecture.png"
FONT = "/System/Library/Fonts/SFNS.ttf"


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT, size)


def box(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    title: str,
    body: str,
    accent: str,
) -> None:
    draw.rounded_rectangle(xy, radius=20, fill=PANEL, outline=LINE, width=2)
    x1, y1, x2, _ = xy
    draw.rounded_rectangle((x1 + 14, y1 + 14, x1 + 22, y1 + 48), radius=4, fill=accent)
    draw.text((x1 + 38, y1 + 13), title, font=font(24), fill=INK)
    draw.multiline_text(
        (x1 + 38, y1 + 52),
        body,
        font=font(16),
        fill=MUTED,
        spacing=6,
    )
    draw.ellipse((x2 - 34, y1 + 20, x2 - 22, y1 + 32), fill=accent)


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: str,
    label: str = "",
) -> None:
    draw.line((start, end), fill=color, width=3)
    ex, ey = end
    sx, sy = start
    if abs(ex - sx) >= abs(ey - sy):
        direction = 1 if ex > sx else -1
        head = [(ex, ey), (ex - direction * 14, ey - 8), (ex - direction * 14, ey + 8)]
    else:
        direction = 1 if ey > sy else -1
        head = [(ex, ey), (ex - 8, ey - direction * 14), (ex + 8, ey - direction * 14)]
    draw.polygon(head, fill=color)
    if label:
        mx, my = (sx + ex) // 2, (sy + ey) // 2
        bbox = draw.textbbox((0, 0), label, font=font(13))
        width = bbox[2] - bbox[0]
        draw.rounded_rectangle(
            (mx - width // 2 - 8, my - 13, mx + width // 2 + 8, my + 10),
            radius=6,
            fill=BACKGROUND,
        )
        draw.text((mx - width // 2, my - 9), label, font=font(13), fill=MUTED)


def main() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    draw.text((70, 55), "PairPilot", font=font(44), fill=INK)
    draw.text(
        (70, 110),
        "Personal agents choose the social path. "
        "Infrastructure controls truth and authority.",
        font=font(22),
        fill=MUTED,
    )
    draw.text((1550, 70), "LIVE SYSTEM", font=font(15), fill=LIME)
    draw.ellipse((1523, 74, 1535, 86), fill=LIME)

    box(
        draw,
        (70, 205, 365, 340),
        "Judge browser",
        "React network UI\nHTTPS + live SSE",
        LIME,
    )
    box(
        draw,
        (485, 180, 850, 365),
        "Public Cloud Run",
        "pairpilot-orchestrator\n"
        "FastAPI · rate limit · quota\n"
        "Hold + approval boundary",
        TEAL,
    )
    box(
        draw,
        (485, 455, 850, 620),
        "Qi personal agent",
        "Google ADK 2.8.0\nmodel-selected typed tools\nminimum-necessary disclosure",
        LIME,
    )
    box(
        draw,
        (960, 180, 1325, 365),
        "Private Cloud Run",
        "pairpilot-peer-agents\nA2A JSON-RPC 1.0\nGoogle-signed identity token",
        VIOLET,
    )
    box(
        draw,
        (960, 455, 1215, 590),
        "Alice Agent",
        "isolated ADK context\nintroduction authority",
        VIOLET,
    )
    box(
        draw,
        (1260, 455, 1515, 590),
        "Maya Agent",
        "isolated ADK context\nproposal authority",
        TEAL,
    )
    box(
        draw,
        (960, 650, 1215, 785),
        "Lena Agent",
        "isolated ADK context\nproposal authority",
        "#e9b58b",
    )
    box(
        draw,
        (1385, 180, 1725, 365),
        "Vertex AI · global",
        "gemini-3.7-flash\nlive Qi + peer turns\nno silent fallback",
        LIME,
    )
    box(
        draw,
        (290, 760, 650, 940),
        "Firestore Native",
        "current truth + provenance\n"
        "relationships · outbox\n"
        "atomic commit preconditions",
        TEAL,
    )
    box(
        draw,
        (735, 760, 1040, 940),
        "Pub/Sub",
        "pairpilot-events\nat-least-once delivery\ndurable Firestore outbox",
        VIOLET,
    )
    box(
        draw,
        (1125, 840, 1435, 975),
        "Cloud Logging",
        "revision + request proof\nrun IDs · errors · probes",
        "#ffffff",
    )
    box(
        draw,
        (1475, 650, 1725, 785),
        "Relationship memory",
        "committed event only\nprovenance-backed growth",
        LIME,
    )

    arrow(draw, (365, 272), (485, 272), LIME, "HTTPS + SSE")
    arrow(draw, (667, 365), (667, 455), LIME, "Google ADK")
    arrow(draw, (850, 520), (960, 272), VIOLET, "authenticated A2A")
    arrow(draw, (1085, 365), (1085, 455), VIOLET)
    arrow(draw, (1210, 365), (1385, 455), TEAL)
    arrow(draw, (1015, 365), (1085, 650), "#e9b58b")
    arrow(draw, (1325, 272), (1385, 272), LIME, "live model")
    arrow(draw, (1215, 510), (1385, 310), TEAL)
    arrow(draw, (1515, 510), (1580, 365), TEAL)
    arrow(draw, (1215, 710), (1475, 710), LIME, "commit → learn")
    arrow(draw, (600, 620), (470, 760), TEAL, "truth + outbox")
    arrow(draw, (650, 850), (735, 850), VIOLET, "publish")
    arrow(draw, (1040, 900), (1125, 900), "#ffffff", "observe")

    draw.text((70, 1000), "AUTHORITY", font=font(13), fill=MUTED)
    draw.line((170, 1008, 225, 1008), fill=LIME, width=3)
    draw.text((250, 1000), "AUTHENTICATED A2A", font=font(13), fill=MUTED)
    draw.line((430, 1008, 485, 1008), fill=VIOLET, width=3)
    draw.text((510, 1000), "CURRENT TRUTH / EVENTS", font=font(13), fill=MUTED)
    draw.line((710, 1008, 765, 1008), fill=TEAL, width=3)

    image.save(OUT, optimize=True)
    print(OUT)


if __name__ == "__main__":
    main()
