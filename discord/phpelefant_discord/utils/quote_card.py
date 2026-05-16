from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

# High-Res Social Media Canvas Dimensions (1200x630 OpenGraph Standard)
WIDTH = 1200
MIN_HEIGHT = 630
OUTER_MARGIN = 64
CARD_RADIUS = 32
CONTENT_PAD_X = 80
CONTENT_PAD_Y = 80
AVATAR_SIZE = 84

# Premium Dark Theme Palette (Linear/Vercel inspired)
BG = (10, 10, 12)
CARD_BG = (22, 23, 26, 230)
CARD_BORDER = (46, 48, 54, 255)
TEXT = (248, 249, 250)
MUTED = (160, 165, 175)
SUBTLE = (110, 115, 125)


@dataclass(slots=True)
class QuoteCardData:
    author_name: str
    author_handle: str
    message: str
    timestamp: datetime | None = None
    avatar_bytes: bytes | None = None


def load_font(size: int, *, bold: bool = False, italic: bool = False, serif: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = []
    if serif:
        if italic and bold:
            paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf", "/System/Library/Fonts/Supplemental/Georgia Bold Italic.ttf"]
        elif italic:
            paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf", "/System/Library/Fonts/Supplemental/Georgia Italic.ttf"]
        elif bold:
            paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"]
        else:
            paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "/System/Library/Fonts/Supplemental/Georgia.ttf"]
    else:
        if italic and bold:
            paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf", "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf"]
        elif italic:
            paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf", "/System/Library/Fonts/Supplemental/Arial Italic.ttf"]
        elif bold:
            paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
        else:
            paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]

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
    text = " ".join(text.replace("\n", "\n").split())
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


def add_grain(image: Image.Image, amount: float = 0.05) -> Image.Image:
    noise = Image.new("RGBA", image.size, (0, 0, 0, 0))
    pixels = noise.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            if random.random() < amount:
                pixels[x, y] = (255, 255, 255, random.randint(3, 10))
    return Image.alpha_composite(image.convert("RGBA"), noise)


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def circular_avatar(avatar_bytes: bytes | None, size: int) -> tuple[Image.Image, Image.Image]:
    if avatar_bytes:
        try:
            avatar = Image.open(BytesIO(avatar_bytes)).convert("RGB")
        except OSError:
            avatar = None
    else:
        avatar = None

    if not avatar:
        avatar = Image.new("RGB", (size, size), (30, 32, 38))
        draw = ImageDraw.Draw(avatar)
        font = load_font(int(size * 0.45), bold=True)
        draw.text((size / 2, size / 2 - 2), "?", font=font, fill=TEXT, anchor="mm")

    avatar = ImageOps.fit(avatar, (size, size), method=Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((1, 1, size - 2, size - 2), fill=255)

    return avatar.convert("RGBA"), mask


def fit_font_for_message(
    draw: ImageDraw.ImageDraw, text: str, max_width: int
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int, int]:
    for size in (64, 56, 48, 42, 36):
        font = load_font(size, bold=False, serif=True)
        lines = wrap_text(draw, text, font, max_width)
        lh_extra = int(size * 0.4)
        height = len(lines) * line_height(font, lh_extra)
        if len(lines) <= 6 or size == 36:
            return font, lines, height, lh_extra
    font = load_font(32, bold=False, serif=True)
    lines = wrap_text(draw, text, font, max_width)
    lh_extra = int(32 * 0.4)
    return font, lines, len(lines) * line_height(font, lh_extra), lh_extra


def generate_mesh_gradient(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Deep, sophisticated ambient glow
    draw.ellipse((-200, -300, 700, 600), fill=(20, 80, 200, 45))
    draw.ellipse((width - 800, height - 600, width + 200, height + 400), fill=(120, 40, 200, 35))
    draw.ellipse((width // 2 - 400, height - 200, width // 2 + 600, height + 500), fill=(40, 160, 180, 25))
    
    return image.filter(ImageFilter.GaussianBlur(160))


def render_quote_card(data: QuoteCardData) -> bytes:
    scratch = Image.new("RGB", (WIDTH, MIN_HEIGHT), BG)
    scratch_draw = ImageDraw.Draw(scratch)

    text_max_width = WIDTH - OUTER_MARGIN * 2 - CONTENT_PAD_X * 2

    # Layout sizing
    quote_font, lines, quote_height, lh_extra = fit_font_for_message(scratch_draw, data.message, text_max_width)
    name_font = load_font(28, bold=True)
    meta_font = load_font(22)
    meta_time_font = load_font(22)
    quote_mark_font = load_font(120, bold=True, serif=True)

    header_gap = 60
    author_height = AVATAR_SIZE
    content_height = quote_height + header_gap + author_height
    
    card_height = max(MIN_HEIGHT - OUTER_MARGIN * 2, CONTENT_PAD_Y * 2 + content_height)
    height = card_height + OUTER_MARGIN * 2

    # Canvas Setup
    base = Image.new("RGB", (WIDTH, height), BG)
    mesh = generate_mesh_gradient((WIDTH, height))
    base_rgba = Image.alpha_composite(base.convert("RGBA"), mesh)
    base_rgba = add_grain(base_rgba, 0.04)

    card_rect = (OUTER_MARGIN, OUTER_MARGIN, WIDTH - OUTER_MARGIN, height - OUTER_MARGIN)
    card_width = card_rect[2] - card_rect[0]
    card_height = card_rect[3] - card_rect[1]

    # Drop Shadow
    shadow_offset = 32
    shadow = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (card_rect[0] + 20, card_rect[1] + shadow_offset, card_rect[2] - 20, card_rect[3] + shadow_offset),
        radius=CARD_RADIUS,
        fill=(0, 0, 0, 140),
    )
    base_rgba = Image.alpha_composite(base_rgba, shadow.filter(ImageFilter.GaussianBlur(40)))

    # Main Card Body
    card_bg = Image.new("RGBA", (card_width, card_height), CARD_BG)
    mask = rounded_mask((card_width, card_height), CARD_RADIUS)
    base_rgba.paste(card_bg, (card_rect[0], card_rect[1]), mask)

    draw = ImageDraw.Draw(base_rgba)
    
    # Outer Border with top-edge highlight
    draw.rounded_rectangle(card_rect, radius=CARD_RADIUS, outline=CARD_BORDER, width=2)
    
    # Inner glowing edge (top only)
    top_edge = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 0))
    top_edge_draw = ImageDraw.Draw(top_edge)
    top_edge_draw.rounded_rectangle((0, 0, card_width - 1, card_height - 1), radius=CARD_RADIUS, outline=(255, 255, 255, 20), width=1)
    # Mask out everything except the very top curve
    crop_mask = Image.new("L", (card_width, card_height), 0)
    crop_draw = ImageDraw.Draw(crop_mask)
    crop_draw.rectangle((0, 0, card_width, 60), fill=255)
    
    final_edge_mask = Image.new("L", (card_width, card_height), 0)
    final_edge_mask.paste(mask, (0, 0), crop_mask)
    base_rgba.paste(top_edge, (card_rect[0], card_rect[1]), final_edge_mask)

    # Ambient Quote Mark Watermark
    overlay = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    # Position top left of card slightly offset
    overlay_draw.text((card_rect[0] + CONTENT_PAD_X - 10, card_rect[1] + CONTENT_PAD_Y - 40), "“", font=quote_mark_font, fill=(255, 255, 255, 12))
    base_rgba.paste(overlay, (0, 0), overlay)

    content_top = card_rect[1] + (card_height - content_height) // 2

    # Print Text
    y = content_top
    text_x = card_rect[0] + CONTENT_PAD_X
    q_line_height = line_height(quote_font, lh_extra)
    
    for line in lines:
        draw.text((text_x, y), line, font=quote_font, fill=TEXT)
        y += q_line_height

    # Author Block
    author_y = content_top + quote_height + header_gap
    
    avatar_img, avatar_mask = circular_avatar(data.avatar_bytes, AVATAR_SIZE)
    base_rgba.paste(avatar_img, (text_x, author_y), avatar_mask)
    draw.ellipse((text_x, author_y, text_x + AVATAR_SIZE - 1, author_y + AVATAR_SIZE - 1), outline=(255, 255, 255, 20), width=1)

    author_text_x = text_x + AVATAR_SIZE + 24
    
    name_bbox = draw.textbbox((0, 0), data.author_name, font=name_font)
    handle_bbox = draw.textbbox((0, 0), data.author_handle, font=meta_font)
    name_h = name_bbox[3] - name_bbox[1]
    handle_h = handle_bbox[3] - handle_bbox[1]
    
    author_text_y = author_y + (AVATAR_SIZE - (name_h + 8 + handle_h)) // 2
    
    draw.text((author_text_x, author_text_y), data.author_name[:80], font=name_font, fill=TEXT)
    draw.text((author_text_x, author_text_y + name_h + 8), f"@{data.author_handle[:120].lstrip('@')}", font=meta_font, fill=MUTED)

    # Timestamp right-aligned
    if data.timestamp is not None:
        ts_str = data.timestamp.strftime("%b %d, %Y")
        time_w = text_width(draw, ts_str, font=meta_time_font)
        time_x = card_rect[2] - CONTENT_PAD_X - time_w
        
        # Center with avatar
        time_bbox = meta_time_font.getbbox("Ag")
        time_h = time_bbox[3] - time_bbox[1]
        time_y = author_y + (AVATAR_SIZE - time_h) // 2
        
        draw.text((time_x, time_y), ts_str, font=meta_time_font, fill=SUBTLE)

    output = BytesIO()
    base_rgba.convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()
