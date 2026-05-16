from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
import textwrap

from PIL import Image, ImageDraw, ImageFont, ImageOps


WIDTH = 1200
MIN_HEIGHT = 430
PADDING = 56
AVATAR_SIZE = 192
TEXT_X = PADDING + AVATAR_SIZE + 48
TEXT_WIDTH = WIDTH - TEXT_X - PADDING
BG = (18, 19, 23)
PANEL = (30, 32, 38)
TEXT = (242, 244, 248)
MUTED = (166, 173, 186)
ACCENT = (96, 165, 250)


@dataclass(slots=True)
class QuoteCardData:
    author_name: str
    author_handle: str
    message: str
    timestamp: datetime | None = None
    avatar_bytes: bytes | None = None


def load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def font_height(font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
    bbox = font.getbbox("Ag")
    return bbox[3] - bbox[1]


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def wrap_quote(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        normalized = "[no text content]"
    if len(normalized) > 800:
        normalized = normalized[:797].rstrip() + "..."

    lines: list[str] = []
    for paragraph in normalized.split("\n"):
        words = paragraph.split()
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if text_width(draw, candidate, font) <= TEXT_WIDTH:
                current = candidate
                continue
            if current:
                lines.append(current)
            if text_width(draw, word, font) <= TEXT_WIDTH:
                current = word
            else:
                chunks = textwrap.wrap(word, width=24, break_long_words=True)
                lines.extend(chunks[:-1])
                current = chunks[-1] if chunks else ""
        if current:
            lines.append(current)
    return lines[:14]


def circular_avatar(avatar_bytes: bytes | None) -> Image.Image:
    if avatar_bytes:
        try:
            avatar = Image.open(BytesIO(avatar_bytes)).convert("RGB")
        except OSError:
            avatar = None
    else:
        avatar = None

    if avatar is None:
        avatar = Image.new("RGB", (AVATAR_SIZE, AVATAR_SIZE), ACCENT)
        draw = ImageDraw.Draw(avatar)
        font = load_font(82, bold=True)
        draw.text((AVATAR_SIZE / 2, AVATAR_SIZE / 2), "?", font=font, fill=TEXT, anchor="mm")

    avatar = ImageOps.fit(avatar, (AVATAR_SIZE, AVATAR_SIZE), method=Image.Resampling.LANCZOS)
    mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
    output = Image.new("RGBA", (AVATAR_SIZE, AVATAR_SIZE), (0, 0, 0, 0))
    output.paste(avatar, (0, 0), mask)
    return output


def render_quote_card(data: QuoteCardData) -> bytes:
    quote_font = load_font(42)
    name_font = load_font(34, bold=True)
    meta_font = load_font(24)
    tiny_font = load_font(20)

    scratch = Image.new("RGB", (WIDTH, MIN_HEIGHT), BG)
    scratch_draw = ImageDraw.Draw(scratch)
    lines = wrap_quote(scratch_draw, data.message, quote_font)
    line_height = font_height(quote_font) + 14
    text_height = max(line_height, len(lines) * line_height)
    height = max(MIN_HEIGHT, PADDING * 2 + text_height + 120)

    image = Image.new("RGB", (WIDTH, height), BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, WIDTH - 24, height - 24), radius=36, fill=PANEL)
    draw.rectangle((24, 24, 34, height - 24), fill=ACCENT)

    avatar_y = PADDING + 12
    avatar = circular_avatar(data.avatar_bytes)
    image.paste(avatar, (PADDING, avatar_y), avatar)

    quote_mark_font = load_font(72, bold=True)
    draw.text((TEXT_X, PADDING - 18), "“", font=quote_mark_font, fill=ACCENT)

    y = PADDING + 32
    for line in lines:
        draw.text((TEXT_X, y), line, font=quote_font, fill=TEXT)
        y += line_height

    name_y = height - PADDING - 72
    draw.text((TEXT_X, name_y), data.author_name[:80], font=name_font, fill=TEXT)
    draw.text((TEXT_X, name_y + 42), data.author_handle[:120], font=meta_font, fill=MUTED)
    if data.timestamp is not None:
        draw.text((TEXT_X, name_y + 76), data.timestamp.strftime("%Y-%m-%d %H:%M UTC"), font=tiny_font, fill=MUTED)

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
