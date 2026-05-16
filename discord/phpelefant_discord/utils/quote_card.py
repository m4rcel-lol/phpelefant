from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

# Classic Retro Forum Dimensions
WIDTH = 1200
MIN_HEIGHT = 630

# Colors for "phpBB" feel
BG = (226, 226, 226)  # Outer bg
TABLE_BORDER = (169, 184, 194)
HEADER_BG = (21, 101, 154)
HEADER_TEXT = (255, 255, 255)
POST_BG_LEFT = (239, 243, 248)
POST_BG_RIGHT = (250, 251, 252)
TEXT_MAIN = (0, 0, 0)
LINK_COLOR = (16, 82, 137)
META_TEXT = (50, 50, 50)

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

def square_avatar(avatar_bytes: bytes | None, size: int) -> Image.Image:
    if avatar_bytes:
        try:
            avatar = Image.open(BytesIO(avatar_bytes)).convert("RGB")
        except OSError:
            avatar = None
    else:
        avatar = None

    if not avatar:
        avatar = Image.new("RGB", (size, size), (220, 220, 220))
        draw = ImageDraw.Draw(avatar)
        font = load_font(int(size * 0.45), bold=True)
        draw.text((size / 2, size / 2 - 2), "?", font=font, fill=(150, 150, 150), anchor="mm")

    avatar = ImageOps.fit(avatar, (size, size), method=Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(avatar)
    draw.rectangle((0, 0, size - 1, size - 1), outline=(0, 0, 0), width=1)
    return avatar

def fit_font_for_message(
    draw: ImageDraw.ImageDraw, text: str, max_width: int
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int, int]:
    for size in (84, 76, 68, 60, 52):
        font = load_font(size, bold=False, serif=False)
        lines = wrap_text(draw, text, font, max_width)
        lh_extra = int(size * 0.2)
        height = len(lines) * line_height(font, lh_extra)
        if len(lines) <= 6 or size == 52:
            return font, lines, height, lh_extra
    font = load_font(44, bold=False, serif=False)
    lines = wrap_text(draw, text, font, max_width)
    lh_extra = int(44 * 0.2)
    return font, lines, len(lines) * line_height(font, lh_extra), lh_extra

def render_quote_card(data: QuoteCardData) -> bytes:
    OUTER_PAD = 40
    COL_LEFT_WIDTH = 340
    CONTENT_PAD = 40
    HEADER_H = 46
    POSTS_COUNT = f"Posts: {random.randint(100, 9999)}"
    JOIN_DATE = f"Joined: {random.randint(2001, 2010)}-04-12"

    scratch = Image.new("RGB", (WIDTH, MIN_HEIGHT), BG)
    scratch_draw = ImageDraw.Draw(scratch)

    right_col_width = WIDTH - OUTER_PAD * 2 - COL_LEFT_WIDTH
    text_max_width = right_col_width - CONTENT_PAD * 2

    message_text = f'"{data.message}"'
    quote_font, lines, quote_height, lh_extra = fit_font_for_message(scratch_draw, message_text, text_max_width)
    
    name_font = load_font(38, bold=True)
    meta_font = load_font(28)
    header_font = load_font(24, bold=False)

    avatar_size = 220
    
    col_left_min_h = CONTENT_PAD + avatar_size + 160
    right_content_h = quote_height + CONTENT_PAD * 2

    table_content_h = max(col_left_min_h, right_content_h)
    
    card_h = HEADER_H + table_content_h
    height = max(MIN_HEIGHT, card_h + OUTER_PAD * 2)

    base = Image.new("RGB", (WIDTH, height), BG)
    draw = ImageDraw.Draw(base)

    card_x0 = OUTER_PAD
    card_y0 = OUTER_PAD
    card_x1 = WIDTH - OUTER_PAD
    card_y1 = card_y0 + card_h

    # Drop shadow
    shadow_offset = 6
    draw.rectangle((card_x0 + shadow_offset, card_y0 + shadow_offset, card_x1 + shadow_offset, card_y1 + shadow_offset), fill=(150, 150, 150))
    # Black thin border
    draw.rectangle((card_x0 - 1, card_y0 - 1, card_x1 + 1, card_y1 + 1), fill=(0, 0, 0))
    
    # Outer table border
    draw.rectangle((card_x0, card_y0, card_x1, card_y1), fill=TABLE_BORDER)
    
    table_pad = 2
    inner_x0 = card_x0 + table_pad
    inner_y0 = card_y0 + table_pad
    inner_x1 = card_x1 - table_pad
    inner_y1 = card_y1 - table_pad

    # Header row
    draw.rectangle((inner_x0, inner_y0, inner_x1, inner_y0 + HEADER_H), fill=HEADER_BG)
    header_text_y = inner_y0 + (HEADER_H - 24) // 2
    
    ts_str = "Posted: Thu Jan 01, 1970 12:00 am"
    if data.timestamp:
        ts_str = data.timestamp.strftime("Posted: %a %b %d, %Y %I:%M %p").lower()
    
    draw.text((inner_x0 + 15, header_text_y), "■ Post subject: Re: Thoughts?", font=header_font, fill=HEADER_TEXT)
    
    time_w = text_width(draw, ts_str, header_font)
    draw.text((inner_x1 - 15 - time_w, header_text_y), ts_str, font=header_font, fill=HEADER_TEXT)

    # Content Row bg
    content_y0 = inner_y0 + HEADER_H + table_pad
    
    col_split_x = inner_x0 + COL_LEFT_WIDTH
    draw.rectangle((inner_x0, content_y0, col_split_x, inner_y1), fill=POST_BG_LEFT) # Left
    draw.rectangle((col_split_x + table_pad, content_y0, inner_x1, inner_y1), fill=POST_BG_RIGHT) # Right

    author_y_curr = content_y0 + CONTENT_PAD
    
    draw.text((inner_x0 + 25, author_y_curr), data.author_name[:30], font=name_font, fill=LINK_COLOR)
    author_y_curr += 50
    draw.text((inner_x0 + 25, author_y_curr), f"@{data.author_handle[:30].lstrip('@')}", font=meta_font, fill=TEXT_MAIN)
    author_y_curr += 45
    
    avatar_img = square_avatar(data.avatar_bytes, avatar_size)
    base.paste(avatar_img, (inner_x0 + 25, author_y_curr))
    author_y_curr += avatar_size + 25
    
    draw.text((inner_x0 + 25, author_y_curr), JOIN_DATE, font=meta_font, fill=META_TEXT)
    author_y_curr += 35
    draw.text((inner_x0 + 25, author_y_curr), POSTS_COUNT, font=meta_font, fill=META_TEXT)

    text_y_curr = content_y0 + (table_content_h - quote_height) // 2

    # Draw quotes
    text_x = col_split_x + table_pad + CONTENT_PAD
    q_line_height = line_height(quote_font, lh_extra)
    for line in lines:
        draw.text((text_x, text_y_curr), line, font=quote_font, fill=TEXT_MAIN)
        text_y_curr += q_line_height

    output = BytesIO()
    base.save(output, format="PNG", optimize=True)
    return output.getvalue()
