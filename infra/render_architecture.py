#!/usr/bin/env python3
"""Render the real multi-user public-beta architecture used in the submission."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1900, 1260
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
    draw.text(
        (65, 45),
        "PairPilot Real Multi-User Public Beta",
        font=font(42),
        fill=INK,
    )
    draw.text(
        (65, 96),
        "One authenticated human, one owned Agent, isolated state, and dual consent.",
        font=font(21),
        fill=MUTED,
    )
    draw.ellipse((1690, 65, 1702, 77), fill=LIME)
    draw.text((1714, 58), "LIVE GOOGLE CLOUD", font=font(14), fill=LIME)

    box(
        draw,
        (65, 180, 430, 455),
        "Public + Authenticated Web",
        "Landing · Sign up · Sign in\nEmail verification + reset\n"
        "Agent · Requests · Explore\nDecisions · Rooms · Network\n"
        "Memory · Settings · Export",
        LIME,
    )
    box(
        draw,
        (555, 180, 900, 350),
        "Firebase Authentication",
        "Email/password identity\nfresh ID token per request\n"
        "revocation + disabled checks",
        TEAL,
    )
    box(
        draw,
        (555, 435, 900, 625),
        "Authenticated Cloud Run API",
        "derive UID from verified token\nowner/member/admin checks\n"
        "no client-supplied authority",
        LIME,
    )
    box(
        draw,
        (1025, 165, 1465, 390),
        "Firestore Authoritative State",
        "owner-scoped users · tasks · memory\npublic post projections · decisions\n"
        "leases · proposals · rooms · outbox\ndirect browser rules deny by default",
        TEAL,
    )
    box(
        draw,
        (1025, 465, 1465, 655),
        "Pub/Sub OIDC Worker",
        "intent.published.v2\nGoogle-signed service identity\n"
        "at-least-once + bounded retry",
        VIOLET,
    )
    box(
        draw,
        (1570, 465, 1835, 655),
        "Vertex AI",
        "gemini-3.7-flash\ntwo bounded ADK turns\npublic fields only",
        LIME,
    )
    box(
        draw,
        (555, 750, 900, 970),
        "Generic Personal Agents",
        "load arbitrary agent_id\nowner privacy + autonomy policy\n"
        "task/intent-scoped A2A\ndaily turns + contact quotas",
        ORANGE,
    )
    box(
        draw,
        (1025, 750, 1465, 970),
        "Proposal · Hold · Dual Approval",
        "Agent A + Agent B accept version N\nHuman A + Human B approve hashes\n"
        "atomic match + both post closures\nupdate-time preconditions",
        TEAL,
    )
    box(
        draw,
        (1570, 750, 1835, 970),
        "Rooms + Social State",
        "participant-only access\nAGENTS_ONLY → SHARED\n"
        "relationships · block\nreport · leave · delete",
        VIOLET,
    )
    box(
        draw,
        (65, 770, 430, 950),
        "Operations + Safety",
        "Cloud Logging + trace IDs\nper-IP endpoint limits\n"
        "session revoke · deletion delay",
        "#ffffff",
    )
    box(
        draw,
        (65, 1010, 430, 1170),
        "Synthetic Demo Boundary",
        "/demo only · visibly labeled\nnever enters production Explore",
        VIOLET,
    )

    arrow(draw, (430, 265), (555, 265), LIME, "authenticate")
    arrow(draw, (725, 350), (725, 435), TEAL, "fresh ID token")
    arrow(draw, (900, 525), (1025, 300), TEAL, "authorized reads/writes")
    arrow(draw, (1245, 390), (1245, 465), VIOLET, "publish event")
    arrow(draw, (1465, 555), (1570, 555), LIME, "two live turns")
    arrow(draw, (1025, 555), (725, 750), VIOLET, "OIDC worker")
    arrow(draw, (900, 860), (1025, 860), ORANGE, "dual Agent acceptance")
    arrow(draw, (1245, 750), (1245, 390), TEAL, "dual human commit")
    arrow(draw, (1465, 860), (1570, 860), LIME, "committed access")
    arrow(draw, (555, 850), (430, 850), "#ffffff", "observe")

    draw.text((555, 1050), "REAL USER FLOW", font=font(13), fill=MUTED)
    steps = (
        "1  AUTHENTICATE   →   2  TELL MY AGENT   →   3  REVIEW + PUBLISH   "
        "→   4  AGENT ↔ AGENT   →   5  TWO HUMANS APPROVE   →   6  SHARED ROOM"
    )
    draw.text((555, 1090), steps, font=font(15), fill=INK)

    image.save(OUT, optimize=True)
    print(OUT)


if __name__ == "__main__":
    main()
