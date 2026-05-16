from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

# High-Res Canvas Dimensions
WIDTH = 1200
MIN_HEIGHT = 600
OUTER_MARGIN = 48
CARD_RADIUS = 32
ACCENT_WIDTH = 8
CONTENT_PAD_X = 64
CONTENT_PAD_Y = 64
AVATAR_SIZE = 140
AVATAR_RING = 4
TEXT_GAP = 56

# Premium Dark Theme Palette
BG = (12, 14, 18)
CARD_TOP = (28, 31, 38)
CARD_BOTTOM = (18, 20, 26)
CARD_BORDER = (45, 50, 60, 255)
TEXT = (250, 252, 255)
MUTED = (168, 178, 193)
SUBTLE = (108, 116, 130)


@dataclass(slots=True)
class QuoteCardData:
    author_name: str
    author_handle: str
    message: str
    timestamp: datetime | None = None
    avatar_bytes: bytes | None = None


def load_font(size: int, *, bold: bool = False, italic: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = []
    if italic and bold:
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf"
        ]
    elif italic:
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
            "/System/Library/Fonts/Supplemental/Arial Italic.ttf"
        ]
    elif bold:
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        ]
    else:
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf"
        ]

    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
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
            candidate = f"{current} {word}".strip()
            if text_width(draw, candidate, font) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines[:12]


def vertical_gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(size[1]):
        ratio = y / max(1, size[1] - 1)
        r = int(top[0] + (bottom[0] - top[0]) * ratio)
        g = int(top[1] + (bottom[1] - top[1]) * ratio)
        b = int(top[2] + (bottom[2] - top[2]) * ratio)
        draw.line([(0, y), (size[0], y)], fill=(r, g, b))
    return image


def add_noise(image: Image.Image, amount: float = 0.03) -> Image.Image:
    noise = Image.new("RGBA", image.size, (0, 0, 0, 0))
    pixels = noise.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            if random.random() < amount:
                pixels[x, y] = (255, 255, 255, random.randint(5, 12))
    return Image.alpha_composite(image.convert("RGBA"), noise)


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def create_gradient_ring(size: int, width: int, color1: tuple[int, int, int], color2: tuple[int, int, int]) -> Image.Image:
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)
    for y in range(size):
        ratio = y / size
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, size - 1, size - 1), fill=255)
    mask_draw.ellipse((width, width, size - 1 - width, size - 1 - width), fill=0)

    base.putalpha(mask)
    return base


def circular_avatar(avatar_bytes: bytes | None) -> tuple[Image.Image, Image.Image]:
    if avatar_bytes:
        try:
            avatar = Image.open(BytesIO(avatar_bytes)).convert("RGB")
        except OSError:
            avatar = None
    else:
        avatar = None

    if not avatar:
        avatar = Image.new("RGB", (AVATAR_SIZE, AVATAR_SIZE), (40, 45, 55))
        draw = ImageDraw.Draw(avatar)
        font = load_font(60, bold=True)
        draw.text((AVATAR_SIZE / 2, AVATAR_SIZE / 2), "?", font=font, fill=TEXT, anchor="mm")

    avatar = ImageOps.fit(avatar, (AVATAR_SIZE, AVATAR_SIZE), method=Image.Resampling.LANCZOS)
    mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, AVATAR_SIZE - 1, AVATAR_SIZE - 1), fill=255)

    return avatar.convert("RGBA"), mask


def fit_font_for_message(
    draw: ImageDraw.ImageDraw, text: str, max_width: int
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int]:
    for size in (48, 42, 38, 34, 30):
        font = load_font(size, italic=False)
        lines = wrap_text(draw, text, font, max_width)
        height = len(lines) * line_height(font, 14)
        if len(lines) <= 7 or size == 30:
            return font, lines, height
    font = load_font(30, italic=False)
    lines = wrap_text(draw, text, font, max_width)
    return font, lines, len(lines) * line_height(font, 14)


def render_quote_card(data: QuoteCardData) -> bytes:
    scratch = Image.new("RGB", (WIDTH, MIN_HEIGHT), BG)
    scratch_draw = ImageDraw.Draw(scratch)

    quote_left = OUTER_MARGIN + ACCENT_WIDTH + CONTENT_PAD_X
    avatar_box = AVATAR_SIZE + AVATAR_RING * 2
    text_x = quote_left + avatar_box + TEXT_GAP
    text_width_available = WIDTH - text_x - OUTER_MARGIN - CONTENT_PAD_X

    quote_font, lines, quote_height = fit_font_for_message(scratch_draw, data.message, text_width_available)
    name_font = load_font(36, bold=True)
    meta_font = load_font(24)
    quote_mark_font = load_font(220, bold=True)

    header_height = 0
    author_height = 80
    content_height = max(avatar_box, header_height + quote_height + 40 + author_height)
    card_height = max(MIN_HEIGHT - OUTER_MARGIN * 2, CONTENT_PAD_Y * 2 + content_height)
    height = card_height + OUTER_MARGIN * 2

    # Background
    base = Image.new("RGB", (WIDTH, height), BG)
    glow = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)

    # Elegant dynamic glowing orbs
    glow_draw.ellipse((-300, -300, 700, 700), fill=(80, 140, 255, 35))
    glow_draw.ellipse((WIDTH - 700, height - 700, WIDTH + 300, height + 300), fill=(160, 80, 255, 30))
    base_rgba = Image.alpha_composite(base.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(100)))

    # Add subtle backdrop noise
    base_rgba = add_noise(base_rgba, 0.02)

    card_rect = (OUTER_MARGIN, OUTER_MARGIN, WIDTH - OUTER_MARGIN, height - OUTER_MARGIN)
    card_size = (card_rect[2] - card_rect[0], card_rect[3] - card_rect[1])

    # Card Drop Shadow
    shadow = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (card_rect[0] + 16, card_rect[1] + 24, card_rect[2] + 16, card_rect[3] + 24),
        radius=CARD_RADIUS,
        fill=(0, 0, 0, 150),
    )
    base_rgba = Image.alpha_composite(base_rgba, shadow.filter(ImageFilter.GaussianBlur(36)))

    # Card Body
    card_bg = vertical_gradient(card_size, CARD_TOP, CARD_BOTTOM).convert("RGBA")
    mask = rounded_mask(card_size, CARD_RADIUS)

    # Watermark Quote Mark inside card
    card_draw = ImageDraw.Draw(card_bg)
    card_draw.text((card_size[0] - 120, 0), "”", font=quote_mark_font, fill=(255, 255, 255, 10), anchor="ra")

    base_rgba.paste(card_bg, (card_rect[0], card_rect[1]), mask)

    draw = ImageDraw.Draw(base_rgba)

    # Card Border outline
    draw.rounded_rectangle(card_rect, radius=CARD_RADIUS, outline=CARD_BORDER, width=2)

    # Accent Line Gradient
    accent_layer = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))
    accent_draw = ImageDraw.Draw(accent_layer)
    accent_rect = (card_rect[0], card_rect[1], card_rect[0] + ACCENT_WIDTH + 16, card_rect[3])
    accent_draw.rounded_rectangle(accent_rect, radius=CARD_RADIUS, fill=(255, 255, 255, 255))

    accent_grad = vertical_gradient((WIDTH, height), (75, 140, 255), (140, 80, 255)).convert("RGBA")

    # Crop the exact region for the accent strip
    mask_accent = Image.new("L", (WIDTH, height), 0)
    mask_draw = ImageDraw.Draw(mask_accent)
    mask_draw.rounded_rectangle(accent_rect, radius=CARD_RADIUS, fill=255)
    mask_draw.rectangle((card_rect[0] + ACCENT_WIDTH, card_rect[1], WIDTH, card_rect[3]), fill=0)

    base_rgba.paste(accent_grad, (0, 0), mask_accent)

    # Avatar
    content_top = card_rect[1] + CONTENT_PAD_Y
    avatar_y = content_top + max(0, (content_height - avatar_box) // 2)

    # Gradient Ring
    ring = create_gradient_ring(avatar_box, AVATAR_RING, (75, 140, 255), (140, 80, 255))
    base_rgba.paste(ring, (quote_left, avatar_y), ring)

    avatar_img, avatar_mask = circular_avatar(data.avatar_bytes)
    avatar_offset = AVATAR_RING
    base_rgba.paste(avatar_img, (quote_left + avatar_offset, avatar_y + avatar_offset), avatar_mask)

    # Text Placement
    y = content_top + 10
    quote_line_height = line_height(quote_font, 14)
    for line in lines:
        # Subtle text shadow for depth
        draw.text((text_x, y + 2), line, font=quote_font, fill=(0, 0, 0, 180))
        draw.text((text_x, y), line, font=quote_font, fill=TEXT)
        y += quote_line_height

    author_y = y + 36

    # Stylish separator below text and above author
    draw.line((text_x, author_y - 12, text_x + 60, author_y - 12), fill=(140, 80, 255), width=3)

    draw.text((text_x, author_y), data.author_name[:80], font=name_font, fill=TEXT)
    draw.text((text_x, author_y + 44), f"@{data.author_handle[:120].lstrip('@')}", font=meta_font, fill=MUTED)
    if data.timestamp is not None:
        timestamp = data.timestamp.strftime("%b %d, %Y • %H:%M UTC")
        draw.text((text_x, author_y + 80), timestamp, font=meta_font, fill=SUBTLE)

    output = BytesIO()
    base_rgba.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()
