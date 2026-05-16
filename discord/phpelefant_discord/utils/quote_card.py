from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


WIDTH = 1200
MIN_HEIGHT = 520
OUTER_MARGIN = 32
CARD_MARGIN = 28
CARD_RADIUS = 44
ACCENT_WIDTH = 8
CONTENT_PAD_X = 56
CONTENT_PAD_Y = 52
AVATAR_SIZE = 154
AVATAR_RING = 5
TEXT_GAP = 42
BG = (15, 17, 22)
CARD_TOP = (34, 37, 46)
CARD_BOTTOM = (24, 27, 34)
TEXT = (246, 247, 251)
MUTED = (166, 174, 190)
SUBTLE = (111, 119, 135)
ACCENT = (94, 163, 255)
ACCENT_2 = (122, 92, 255)


@dataclass(slots=True)
class QuoteCardData:
    author_name: str
    author_handle: str
    message: str
    timestamp: datetime | None = None
    avatar_bytes: bytes | None = None


def load_font(size: int, *, bold: bool = False, italic: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if italic:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Oblique.ttf",
            "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
        ]
    elif bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def text_bbox(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> tuple[int, int, int, int]:
    return draw.textbbox((0, 0), text, font=font)


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
    bbox = text_bbox(draw, text, font)
    return bbox[2] - bbox[0]


def line_height(font: ImageFont.FreeTypeFont | ImageFont.ImageFont, extra: int) -> int:
    bbox = font.getbbox("Ag")
    return bbox[3] - bbox[1] + extra


def clean_message(value: str) -> str:
    text = value.strip() or "[no text content]"
    text = " ".join(text.replace("\r", "\n").split())
    if len(text) > 700:
        text = text[:697].rstrip() + "..."
    return text


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in clean_message(text).split("\n"):
        words = paragraph.split()
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if text_width(draw, candidate, font) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            while text_width(draw, word, font) > max_width and len(word) > 4:
                for index in range(len(word), 3, -1):
                    chunk = word[:index] + "-"
                    if text_width(draw, chunk, font) <= max_width:
                        lines.append(chunk)
                        word = word[index:]
                        break
                else:
                    break
            current = word
        if current:
            lines.append(current)
    return lines[:12]


def vertical_gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size)
    pixels = image.load()
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
        for x in range(width):
            pixels[x, y] = color
    return image


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def circular_avatar(avatar_bytes: bytes | None) -> Image.Image:
    avatar: Image.Image | None = None
    if avatar_bytes:
        try:
            avatar = Image.open(BytesIO(avatar_bytes)).convert("RGB")
        except OSError:
            avatar = None

    if avatar is None:
        avatar = Image.new("RGB", (AVATAR_SIZE, AVATAR_SIZE), ACCENT)
        draw = ImageDraw.Draw(avatar)
        font = load_font(70, bold=True)
        draw.text((AVATAR_SIZE / 2, AVATAR_SIZE / 2 - 4), "?", font=font, fill=TEXT, anchor="mm")

    avatar = ImageOps.fit(avatar, (AVATAR_SIZE, AVATAR_SIZE), method=Image.Resampling.LANCZOS)
    mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, AVATAR_SIZE - 1, AVATAR_SIZE - 1), fill=255)

    output = Image.new("RGBA", (AVATAR_SIZE + AVATAR_RING * 2, AVATAR_SIZE + AVATAR_RING * 2), (0, 0, 0, 0))
    ring_draw = ImageDraw.Draw(output)
    ring_draw.ellipse((0, 0, output.width - 1, output.height - 1), fill=ACCENT)
    output.paste(avatar.convert("RGBA"), (AVATAR_RING, AVATAR_RING), mask)
    return output


def fit_font_for_message(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int]:
    for size in (46, 42, 38, 34, 30):
        font = load_font(size, italic=True)
        lines = wrap_text(draw, text, font, max_width)
        height = len(lines) * line_height(font, 12)
        if len(lines) <= 8 or size == 30:
            return font, lines, height
    font = load_font(30, italic=True)
    lines = wrap_text(draw, text, font, max_width)
    return font, lines, len(lines) * line_height(font, 12)


def render_quote_card(data: QuoteCardData) -> bytes:
    scratch = Image.new("RGB", (WIDTH, MIN_HEIGHT), BG)
    scratch_draw = ImageDraw.Draw(scratch)

    quote_left = OUTER_MARGIN + CARD_MARGIN + ACCENT_WIDTH + CONTENT_PAD_X
    avatar_box = AVATAR_SIZE + AVATAR_RING * 2
    text_x = quote_left + avatar_box + TEXT_GAP
    text_width_available = WIDTH - text_x - OUTER_MARGIN - CARD_MARGIN - CONTENT_PAD_X

    quote_font, lines, quote_height = fit_font_for_message(scratch_draw, data.message, text_width_available)
    name_font = load_font(32, bold=True)
    meta_font = load_font(22)
    brand_font = load_font(18, bold=True)
    quote_mark_font = load_font(84, bold=True)

    header_height = 44
    author_height = 86
    content_height = max(avatar_box, header_height + quote_height + 32 + author_height)
    card_height = max(MIN_HEIGHT - OUTER_MARGIN * 2, CONTENT_PAD_Y * 2 + content_height)
    height = card_height + OUTER_MARGIN * 2

    base = Image.new("RGB", (WIDTH, height), BG)

    glow = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((-140, -160, 520, 360), fill=(94, 163, 255, 50))
    glow_draw.ellipse((760, height - 380, 1340, height + 120), fill=(122, 92, 255, 36))
    base = Image.alpha_composite(base.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(40))).convert("RGB")

    card_rect = (OUTER_MARGIN, OUTER_MARGIN, WIDTH - OUTER_MARGIN, height - OUTER_MARGIN)
    shadow = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((card_rect[0] + 10, card_rect[1] + 14, card_rect[2] + 10, card_rect[3] + 14), radius=CARD_RADIUS, fill=(0, 0, 0, 95))
    base = Image.alpha_composite(base.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(18)))

    card_size = (card_rect[2] - card_rect[0], card_rect[3] - card_rect[1])
    card = vertical_gradient(card_size, CARD_TOP, CARD_BOTTOM).convert("RGBA")
    mask = rounded_mask(card_size, CARD_RADIUS)
    base.paste(card, (card_rect[0], card_rect[1]), mask)

    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle(card_rect, radius=CARD_RADIUS, outline=(55, 60, 73), width=1)
    draw.rounded_rectangle(
        (card_rect[0], card_rect[1], card_rect[0] + ACCENT_WIDTH + 10, card_rect[3]),
        radius=CARD_RADIUS,
        fill=ACCENT,
    )
    draw.rectangle((card_rect[0] + ACCENT_WIDTH, card_rect[1], card_rect[0] + ACCENT_WIDTH + 14, card_rect[3]), fill=ACCENT)

    content_top = card_rect[1] + CONTENT_PAD_Y
    avatar_y = content_top + max(0, (content_height - avatar_box) // 2) - 6
    avatar = circular_avatar(data.avatar_bytes)
    base.paste(avatar, (quote_left, avatar_y), avatar)

    draw.text((text_x, content_top - 12), "QUOTE", font=brand_font, fill=ACCENT)
    draw.text((text_x, content_top + 20), "“", font=quote_mark_font, fill=(94, 163, 255, 135))

    y = content_top + 72
    quote_line_height = line_height(quote_font, 12)
    for line in lines:
        draw.text((text_x, y), line, font=quote_font, fill=TEXT)
        y += quote_line_height

    author_y = y + 28
    draw.line((text_x, author_y - 10, min(text_x + 240, WIDTH - CONTENT_PAD_X), author_y - 10), fill=(77, 84, 102), width=2)
    draw.text((text_x, author_y), data.author_name[:80], font=name_font, fill=TEXT)
    draw.text((text_x, author_y + 42), data.author_handle[:120], font=meta_font, fill=MUTED)
    if data.timestamp is not None:
        timestamp = data.timestamp.strftime("%Y-%m-%d %H:%M UTC")
        draw.text((text_x, author_y + 72), timestamp, font=meta_font, fill=SUBTLE)

    output = BytesIO()
    base.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()

