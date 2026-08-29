#!/usr/bin/env python3
"""Render the intent-marketplace architecture PNG used in the submission."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1900, 1200
BACKGROUND = "#090b0a"
PANEL = "#131714"
LINE = "#343a35"
INK = "#f2f4ee"
MUTED = "#9aa29b"
LIME = "#caff6a"
TEAL = "#79e8ca"
VIOLET = "#b9a7ff"
ORANGE = "#efb680"

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
    draw.rounded_rectangle(
        (x1 + 14, y1 + 14, x1 + 22, y1 + 48), radius=4, fill=accent
    )
    draw.text((x1 + 38, y1 + 13), title, font=font(23), fill=INK)
    draw.multiline_text(
        (x1 + 38, y1 + 52), body, font=font(15), fill=MUTED, spacing=7
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
        head = [
            (ex, ey),
            (ex - direction * 14, ey - 8),
            (ex - direction * 14, ey + 8),
        ]
    else:
        direction = 1 if ey > sy else -1
        head = [
            (ex, ey),
            (ex - 8, ey - direction * 14),
            (ex + 8, ey - direction * 14),
        ]
    draw.polygon(head, fill=color)
    if label:
        mx, my = (sx + ex) // 2, (sy + ey) // 2
        bbox = draw.textbbox((0, 0), label, font=font(12))
        text_width = bbox[2] - bbox[0]
        draw.rounded_rectangle(
            (mx - text_width // 2 - 8, my - 12, mx + text_width // 2 + 8, my + 10),
            radius=6,
            fill=BACKGROUND,
        )
        draw.text(
            (mx - text_width // 2, my - 8), label, font=font(12), fill=MUTED
        )


def main() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.text((65, 45), "PairPilot Personal Agent OS", font=font(42), fill=INK)
    draw.text(
        (65, 96),
        "Personal agents operate active posts; infrastructure governs commitment.",
        font=font(21),
        fill=MUTED,
    )
    draw.ellipse((1690, 65, 1702, 77), fill=LIME)
    draw.text((1714, 58), "LIVE GOOGLE CLOUD", font=font(14), fill=LIME)

    box(
        draw,
        (65, 180, 430, 455),
        "Routed Product Shell",
        "Global Qi conversation\nTask conversations\nExplore + Rooms\n"
        "Decision Inbox + Matches\nNetwork + Memory + Audit",
        LIME,
    )
    box(
        draw,
        (555, 180, 900, 350),
        "Public Cloud Run",
        "React + FastAPI orchestrator\nTyped router + UI directives\n"
        "HTTPS · SSE · safe demo quota",
        TEAL,
    )
    box(
        draw,
        (555, 435, 900, 625),
        "Persistent Qi Personal Agent",
        "bounded cross-task summaries\nGoogle ADK 2.8.0\ngemini-3.7-flash",
        LIME,
    )
    box(
        draw,
        (1025, 165, 1465, 390),
        "Firestore Product + Intent Registry",
        "tasks · conversations · decisions · rooms\npublic intent posts\n"
        "status · capacity · expiry · owner\nprivate context stored separately",
        TEAL,
    )
    box(
        draw,
        (1025, 465, 1465, 655),
        "Private Cloud Run",
        "Alice · Maya · Lena ADK agents\nA2A JSON-RPC 1.0\n"
        "Google-signed identity token",
        VIOLET,
    )
    box(
        draw,
        (1570, 465, 1835, 655),
        "Vertex AI · global",
        "gemini-3.7-flash\nlive agent turns\nno silent fallback",
        LIME,
    )
    box(
        draw,
        (555, 750, 900, 950),
        "Proposal / Hold / Approval",
        "versioned intent pair\n15-minute capacity hold\n"
        "exact human effect approval\nexplicit expiry revalidation",
        ORANGE,
    )
    box(
        draw,
        (1025, 750, 1465, 965),
        "Firestore authoritative commit",
        "match + both post closures\nrelease other negotiations\n"
        "provenance + durable outbox\nupdate-time preconditions",
        TEAL,
    )
    box(
        draw,
        (1570, 750, 1835, 925),
        "Pub/Sub",
        "match.committed\nintent.matched × 2\nat-least-once delivery",
        VIOLET,
    )
    box(
        draw,
        (1025, 1020, 1465, 1165),
        "Relationship Memory",
        "Qi ↔ Maya provenance\nconditional Alice credit · scoped editable inference",
        LIME,
    )
    box(
        draw,
        (65, 770, 430, 925),
        "Cloud Logging",
        "revision + request proof\nrun IDs · errors · probes",
        "#ffffff",
    )

    arrow(draw, (430, 265), (555, 265), LIME, "global + task messages")
    arrow(draw, (900, 260), (1025, 260), TEAL, "project + publish")
    arrow(draw, (725, 350), (725, 435), LIME, "live ADK")
    arrow(draw, (900, 525), (1025, 555), VIOLET, "intent-scoped A2A")
    arrow(draw, (1465, 555), (1570, 555), LIME, "live turns")
    arrow(draw, (725, 625), (725, 750), ORANGE, "versioned proposal")
    arrow(draw, (900, 850), (1025, 850), TEAL, "exact approval → commit")
    arrow(draw, (1245, 750), (1245, 390), TEAL, "both posts MATCHED")
    arrow(draw, (1465, 850), (1570, 850), VIOLET, "durable events")
    arrow(draw, (1700, 925), (1465, 1090), LIME, "committed event only")
    arrow(draw, (555, 830), (430, 830), "#ffffff", "observe")

    draw.text((65, 1060), "PRODUCT FLOW", font=font(13), fill=MUTED)
    steps = (
        "1  EXPRESS INTENT   →   2  DRAFT + PUBLISH   →   3  DISCOVER + A2A   "
        "→   4  HOLD + APPROVE   →   5  COMMIT + CLOSE   →   6  LEARN"
    )
    draw.text((65, 1095), steps, font=font(15), fill=INK)

    image.save(OUT, optimize=True)
    print(OUT)


if __name__ == "__main__":
    main()
