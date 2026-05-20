from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable, Protocol

import discord
from discord.ext import commands

BRAND_NAME = "PHPelefant"
BRAND_COLOR = 0x58A6FF
SUCCESS_COLOR = 0x2ECC71
WARNING_COLOR = 0xF1C40F
ERROR_COLOR = 0xE74C3C
INFO_COLOR = 0x5865F2
OWNER_COLOR = 0x9B59B6
MODERATION_COLOR = 0xFF6B6B
NEUTRAL_COLOR = 0x2B2D31
EMBED_LIMIT = 6000
FIELD_VALUE_LIMIT = 1024
DESCRIPTION_LIMIT = 4096

STATUS_COLORS = {
    "info": INFO_COLOR,
    "success": SUCCESS_COLOR,
    "warning": WARNING_COLOR,
    "error": ERROR_COLOR,
    "owner": OWNER_COLOR,
    "moderation": MODERATION_COLOR,
    "neutral": NEUTRAL_COLOR,
}

STATUS_LABELS = {
    "info": "Information",
    "success": "Completed",
    "warning": "Attention Required",
    "error": "Action Failed",
    "owner": "Owner Console",
    "moderation": "Moderation Action",
    "neutral": "PHPelefant",
}


class ContextLike(Protocol):
    author: discord.User | discord.Member
    guild: discord.Guild | None
    command: commands.Command | None
    bot: commands.Bot


def code_block(value: str, language: str = "") -> str:
    fence = f"```{language}\n" if language else "```\n"
    safe = value.replace("```", "`\u200b``")
    return f"{fence}{safe[:3900]}\n```"


def truncate(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    suffix = "\n... output truncated ..."
    return value[: max(0, limit - len(suffix))] + suffix, True


def truncate_text(value: object, limit: int = 1024) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def clean_title(value: object) -> str:
    text = str(value).strip().replace("_", " ").replace("-", " ")
    return " ".join(part.capitalize() for part in text.split())[:256] or "Field"


def format_bool(value: object) -> str:
    if isinstance(value, bool):
        return "Enabled" if value else "Disabled"
    return str(value)


def command_label(ctx: ContextLike | None) -> str:
    if ctx is None or ctx.command is None:
        return "Command"
    return f"/{ctx.command.qualified_name}"


def context_footer(ctx: ContextLike | None, status: str) -> str:
    label = STATUS_LABELS.get(status, STATUS_LABELS["info"])
    if ctx is None:
        return f"{BRAND_NAME} • {label} • UTC"
    guild_name = ctx.guild.name if ctx.guild else "Direct message"
    author = getattr(ctx, "author", None)
    author_text = f"{author} ({author.id})" if author else "Unknown user"
    return f"{BRAND_NAME} • {label} • {guild_name} • Requested by {author_text}"


def embed(
    title: str,
    description: str | None = None,
    *,
    color: int | None = None,
    status: str = "info",
    footer: str | None = None,
) -> discord.Embed:
    item = discord.Embed(
        title=title,
        description=truncate_text(description, DESCRIPTION_LIMIT) if description is not None else None,
        color=color if color is not None else STATUS_COLORS.get(status, BRAND_COLOR),
        timestamp=datetime.now(tz=UTC),
    )
    item.set_author(name=f"{BRAND_NAME} • {STATUS_LABELS.get(status, STATUS_LABELS['info'])}")
    item.set_footer(text=footer or context_footer(None, status))
    return item


def success_embed(title: str, description: str | None = None) -> discord.Embed:
    return embed(title, description, status="success")


def warning_embed(title: str, description: str | None = None) -> discord.Embed:
    return embed(title, description, status="warning")


def error_embed(title: str, description: str | None = None) -> discord.Embed:
    return embed(title, description, status="error")


def moderation_embed(title: str, description: str | None = None) -> discord.Embed:
    return embed(title, description, status="moderation")


def image_embed(title: str, image_url: str, description: str | None = None, *, color: int = 0x4F8CC9) -> discord.Embed:
    item = embed(title, description, color=color)
    item.set_image(url=image_url)
    return item


def code_embed(title: str, value: str, language: str = "", *, status: str = "info") -> discord.Embed:
    if language or "\n" in value or len(value) > 180:
        return embed(title, code_block(value, language), status=status)
    return embed(title, truncate_text(value, DESCRIPTION_LIMIT), status=status)


def table_embed(
    title: str,
    rows: Iterable[tuple[str, object]],
    *,
    status: str = "info",
    description: str | None = None,
) -> discord.Embed:
    values = list(rows)
    item = embed(title, description, status=status)
    if not values:
        item.description = item.description or "No data."
        return item
    if len(values) <= 25 and all(len(str(value)) <= 900 for _, value in values):
        for label, value in values:
            raw_value = format_bool(value)
            item.add_field(
                name=truncate_text(clean_title(label), 256),
                value=truncate_text(raw_value, FIELD_VALUE_LIMIT),
                inline="\n" not in raw_value and len(raw_value) <= 80,
            )
        return item
    width = max((len(label) for label, _ in values), default=0)
    body = "\n".join(f"{label.ljust(width)} : {value}" for label, value in values) or "No data."
    item.description = code_block(body)
    return item


def list_embed(
    title: str,
    lines: Iterable[str],
    *,
    status: str = "info",
    empty: str = "No entries.",
) -> discord.Embed:
    body = "\n".join(truncate_text(line, 180) for line in lines)
    return embed(title, body or empty, status=status)


def decorate_embed(item: discord.Embed, ctx: ContextLike | None = None, *, status: str = "info") -> discord.Embed:
    if not item.author or not item.author.name:
        item.set_author(name=f"{BRAND_NAME} • {command_label(ctx)}")
    elif ctx is not None and item.author.name.startswith(f"{BRAND_NAME} •"):
        item.set_author(name=f"{BRAND_NAME} • {command_label(ctx)}")

    item.set_footer(text=context_footer(ctx, status))

    avatar_url: str | None = None
    bot_user = getattr(getattr(ctx, "bot", None), "user", None)
    if bot_user is not None:
        try:
            avatar_url = bot_user.display_avatar.url
        except AttributeError:
            avatar_url = None
    if avatar_url:
        if item.author and item.author.name:
            item.set_author(name=item.author.name, icon_url=avatar_url)
        if item.footer and item.footer.text:
            item.set_footer(text=item.footer.text, icon_url=avatar_url)
    return item


def infer_status(item: discord.Embed) -> str:
    color = item.color.value if item.color else INFO_COLOR
    for status, status_color in STATUS_COLORS.items():
        if color == status_color:
            return status
    return "info"


class PHPelefantContext(commands.Context):
    async def send(self, *args, **kwargs):
        item = kwargs.get("embed")
        if isinstance(item, discord.Embed):
            decorate_embed(item, self, status=infer_status(item))
        items = kwargs.get("embeds")
        if isinstance(items, list):
            for candidate in items:
                if isinstance(candidate, discord.Embed):
                    decorate_embed(candidate, self, status=infer_status(candidate))
        return await super().send(*args, **kwargs)
