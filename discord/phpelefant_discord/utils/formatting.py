from __future__ import annotations

import discord


def code_block(value: str, language: str = "") -> str:
    fence = f"```{language}\n" if language else "```\n"
    safe = value.replace("```", "`\u200b``")
    return f"{fence}{safe[:3900]}\n```"


def truncate(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    suffix = "\n... output truncated ..."
    return value[: max(0, limit - len(suffix))] + suffix, True


def embed(title: str, description: str | None = None, *, color: int = 0x4F8CC9) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


def table_embed(title: str, rows: list[tuple[str, object]]) -> discord.Embed:
    width = max((len(label) for label, _ in rows), default=0)
    body = "\n".join(f"{label.ljust(width)} : {value}" for label, value in rows) or "No data."
    return embed(title, code_block(body))

