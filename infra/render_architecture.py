#!/usr/bin/env python3
"""Render the final PairPilot submission architecture diagram."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 2400, 1500
BACKGROUND = "#090b0a"
PANEL = "#131714"
PANEL_ALT = "#171a17"
LINE = "#343a35"
INK = "#f2f4ee"
MUTED = "#a8b0a9"
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
    *,
    title_size: int = 22,
    body_size: int = 16,
    fill: str = PANEL,
) -> None:
    draw.rounded_rectangle(xy, radius=18, fill=fill, outline=LINE, width=2)
    x1, y1, x2, _ = xy
    draw.rounded_rectangle((x1 + 15, y1 + 15, x1 + 23, y1 + 50), radius=4, fill=accent)
    draw.text((x1 + 38, y1 + 14), title, font=font(title_size), fill=INK)
    draw.multiline_text(
        (x1 + 38, y1 + 56), body, font=font(body_size), fill=MUTED, spacing=7
    )
    draw.ellipse((x2 - 34, y1 + 21, x2 - 22, y1 + 33), fill=accent)


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: str,
    label: str = "",
) -> None:
    draw.line((start, end), fill=color, width=4)
    ex, ey = end
    sx, sy = start
    if abs(ex - sx) >= abs(ey - sy):
        direction = 1 if ex > sx else -1
        head = [
            (ex, ey),
            (ex - direction * 15, ey - 9),
            (ex - direction * 15, ey + 9),
        ]
    else:
        direction = 1 if ey > sy else -1
        head = [
            (ex, ey),
            (ex - 9, ey - direction * 15),
            (ex + 9, ey - direction * 15),
        ]
    draw.polygon(head, fill=color)
    if label:
        mx, my = (sx + ex) // 2, (sy + ey) // 2
        bbox = draw.textbbox((0, 0), label, font=font(13))
        text_width = bbox[2] - bbox[0]
        draw.rounded_rectangle(
            (mx - text_width // 2 - 10, my - 14, mx + text_width // 2 + 10, my + 12),
            radius=7,
            fill=BACKGROUND,
        )
        draw.text((mx - text_width // 2, my - 10), label, font=font(13), fill=MUTED)


def main() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    draw.text((68, 42), "PairPilot Final Architecture", font=font(46), fill=INK)
    draw.text(
        (68, 98),
        "A persistent Personal Agent operates the market; deterministic authority "
        "protects every human commitment.",
        font=font(22),
        fill=MUTED,
    )
    draw.ellipse((2152, 66, 2166, 80), fill=LIME)
    draw.text((2180, 58), "TASKMASTER", font=font(15), fill=LIME)

    # Identity and model runtime.
    box(
        draw,
        (68, 170, 410, 365),
        "Authenticated Users",
        "User A + User B\nindependent identities\nindependent approval",
        LIME,
    )
    box(
        draw,
        (488, 170, 825, 365),
        "Firebase Authentication",
        "verified identity\nrestored session\nfresh ID token",
        TEAL,
    )
    box(
        draw,
        (905, 170, 1242, 365),
        "Cloud Run",
        "authenticated web API\nAgent runtime + worker\nowner/member checks",
        TEAL,
    )
    box(
        draw,
        (1322, 155, 1802, 380),
        "Persistent Personal Agents",
        "one owner-scoped Agent per user\n"
        "global + task-scoped ADK sessions\n"
        "privacy + autonomy policy",
        ORANGE,
    )
    box(
        draw,
        (1882, 170, 2332, 365),
        "Vertex AI",
        "gemini-3.7-flash\nlive drafting, assessment\nand A2A negotiation turns",
        LIME,
    )
    arrow(draw, (410, 268), (488, 268), LIME, "authenticate")
    arrow(draw, (825, 268), (905, 268), TEAL, "ID token")
    arrow(draw, (1242, 268), (1322, 268), ORANGE, "load Agent")
    arrow(draw, (1802, 268), (1882, 268), LIME, "live turns")

    draw.text((68, 448), "AUTHORITATIVE MAIN FLOW", font=font(16), fill=LIME)
    draw.line((68, 477, 2332, 477), fill=LINE, width=2)

    # Main flow, row one.
    top_y1, top_y2 = 520, 705
    xs = [(68, 386), (454, 772), (840, 1158), (1226, 1544), (1612, 1930)]
    top_boxes = [
        ("1  Conversation", "one continuous chat\nclarify the real need", LIME),
        (
            "2  Agent-drafted Post",
            "privacy-aware public draft\nprivate boundaries stay private",
            ORANGE,
        ),
        (
            "3  Publish + Registry",
            "human review or Agent policy\nIntent Post becomes OPEN",
            TEAL,
        ),
        (
            "4  Market Monitoring",
            "Pub/Sub background wake\nMulti-Candidate Pool",
            VIOLET,
        ),
        ("5  Multiple A2A", "Personal Agent ↔ Agent\nCoordination Rooms", ORANGE),
    ]
    for (x1, x2), (title, body, accent) in zip(xs, top_boxes):  # noqa: B905
        box(draw, (x1, top_y1, x2, top_y2), title, body, accent, title_size=20)
    for (_, x2), (next_x1, _) in zip(xs, xs[1:]):  # noqa: B905
        arrow(draw, (x2, 613), (next_x1, 613), LIME)

    # Turn the flow into the second row and move right-to-left.
    arrow(draw, (1930, 613), (2240, 613), VIOLET)
    draw.line((2240, 613, 2240, 820), fill=VIOLET, width=4)
    arrow(draw, (2240, 820), (2038, 820), VIOLET)

    bottom_y1, bottom_y2 = 760, 955
    bottom = [
        (
            "6  Dynamic Ranking",
            "new negotiation evidence\nreranks several candidates",
            VIOLET,
            (1720, 2038),
        ),
        (
            "7  Proposal + Hold",
            "versioned reservation\nDual Human Approval",
            TEAL,
            (1334, 1652),
        ),
        (
            "8  Atomic Match",
            "recheck both approvals\nconsume both Post capacities",
            LIME,
            (948, 1266),
        ),
        (
            "9  Post-match State",
            "Shared Room · Network\nConfirmed Memory",
            VIOLET,
            (454, 880),
        ),
    ]
    for title, body, accent, (x1, x2) in bottom:
        box(draw, (x1, bottom_y1, x2, bottom_y2), title, body, accent, title_size=20)
    arrow(draw, (1720, 858), (1652, 858), VIOLET)
    arrow(draw, (1334, 858), (1266, 858), TEAL)
    arrow(draw, (948, 858), (880, 858), LIME)

    # Agent involvement is explicit without crossing the main sequence.
    draw.line((1562, 380, 1562, 430), fill=ORANGE, width=3)
    draw.line((226, 430, 1771, 430), fill=ORANGE, width=3)
    for x in (226, 613, 1771):
        arrow(draw, (x, 430), (x, 520), ORANGE)
    draw.text(
        (690, 401),
        "Agent operates conversation, drafting, monitoring, negotiation, and ranking",
        font=font(14),
        fill=ORANGE,
    )

    draw.text((68, 1035), "GOOGLE CLOUD CONTROL + DATA PLANE", font=font(16), fill=TEAL)
    draw.line((68, 1064, 2332, 1064), fill=LINE, width=2)

    box(
        draw,
        (68, 1110, 880, 1370),
        "Firestore — Authoritative State",
        "users · Personal Agents · ADK sessions · tasks · private intents · "
        "public Posts\n"
        "candidate assessments · Agent Rooms · proposals · holds · human approvals\n"
        "Matches · Shared Rooms · relationships · confirmed memories · leases + outbox",
        TEAL,
        title_size=23,
        body_size=16,
        fill=PANEL_ALT,
    )
    box(
        draw,
        (950, 1110, 1608, 1370),
        "Pub/Sub Background Monitoring",
        "intent.published.v2 events\n"
        "OIDC push to Cloud Run worker\n"
        "bounded retry + idempotent delivery\n"
        "continuous candidate reconciliation",
        VIOLET,
        title_size=23,
        fill=PANEL_ALT,
    )
    box(
        draw,
        (1678, 1110, 2332, 1370),
        "Cloud Logging",
        "trace IDs · authenticated principal\n"
        "Agent + model provenance\n"
        "worker outcomes + failures\n"
        "privacy-aware operational evidence",
        LIME,
        title_size=23,
        fill=PANEL_ALT,
    )

    # Route the publish event through the gap between flow cards so the
    # infrastructure edge never crosses the Atomic Match card.
    draw.line(
        (1074, 705, 1074, 728, 914, 728, 914, 1070, 1120, 1070), fill=VIOLET, width=4
    )
    arrow(draw, (1120, 1070), (1120, 1110), VIOLET)
    draw.rounded_rectangle((851, 990, 978, 1018), radius=7, fill=BACKGROUND)
    draw.text((862, 994), "publish event", font=font(13), fill=MUTED)
    arrow(draw, (950, 1240), (880, 1240), TEAL, "state transitions")
    arrow(draw, (1608, 1240), (1678, 1240), LIME, "observability")

    draw.text(
        (68, 1432),
        "Models choose semantic strategy. Firestore-backed services authorize "
        "publication, disclosure, holds, approvals, and commit.",
        font=font(18),
        fill=MUTED,
    )

    image.save(OUT, optimize=True)
    print(OUT)


if __name__ == "__main__":
    main()
