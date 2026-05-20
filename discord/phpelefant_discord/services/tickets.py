from __future__ import annotations

from datetime import UTC, datetime
import re

import discord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant_discord.db.models import Ticket, TicketConfig

CHANNEL_SAFE_RE = re.compile(r"[^a-z0-9-]+")
DEFAULT_TICKET_CATEGORIES = ["General Support", "Billing", "Bug Report", "Staff Report", "Appeal"]


async def get_or_create_ticket_config(session: AsyncSession, guild_id: int) -> TicketConfig:
    row = await session.get(TicketConfig, guild_id)
    if row is not None:
        return row
    row = TicketConfig(guild_id=guild_id)
    session.add(row)
    await session.flush()
    return row


async def open_ticket_for_user(session: AsyncSession, guild_id: int, user_id: int) -> Ticket | None:
    return await session.scalar(
        select(Ticket).where(
            Ticket.guild_id == guild_id,
            Ticket.opener_id == user_id,
            Ticket.status == "open",
        )
    )


async def open_ticket_for_channel(session: AsyncSession, guild_id: int, channel_id: int) -> Ticket | None:
    return await session.scalar(
        select(Ticket).where(
            Ticket.guild_id == guild_id,
            Ticket.channel_id == channel_id,
            Ticket.status == "open",
        )
    )


def sanitize_channel_fragment(value: str, fallback: str = "user") -> str:
    normalized = value.casefold().replace(" ", "-")
    normalized = CHANNEL_SAFE_RE.sub("-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return (normalized or fallback)[:32]


def parse_ticket_categories(value: str | None) -> list[str]:
    raw_items = (value or "").replace("\n", "|").split("|")
    categories: list[str] = []
    for item in raw_items:
        category = item.strip()
        if not category:
            continue
        if category.casefold() in {seen.casefold() for seen in categories}:
            continue
        categories.append(category[:80])
    return categories[:25] or DEFAULT_TICKET_CATEGORIES.copy()


def serialize_ticket_categories(categories: list[str]) -> str:
    values = []
    seen: set[str] = set()
    for category in categories:
        normalized = category.strip()
        if not normalized or normalized.casefold() in seen:
            continue
        values.append(normalized[:80])
        seen.add(normalized.casefold())
    return "|".join(values[:25] or DEFAULT_TICKET_CATEGORIES)


def ticket_channel_name(category: str, number: int, member: discord.Member | discord.User) -> str:
    category_part = sanitize_channel_fragment(category, "ticket")[:24]
    user_part = sanitize_channel_fragment(member.display_name)[:28]
    return f"{category_part}-{user_part}-{number:04d}"[:100]


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


async def build_ticket_transcript(channel: discord.TextChannel, ticket: Ticket, limit: int = 300) -> bytes:
    lines = [
        "PHPelefant Ticket Transcript",
        f"Guild: {channel.guild.name} ({channel.guild.id})",
        f"Channel: #{channel.name} ({channel.id})",
        f"Ticket: #{ticket.ticket_number} / database id {ticket.id}",
        f"Category: {ticket.category}",
        f"Opened by: {ticket.opener_id}",
        f"Claimed by: {ticket.claimed_by_id or 'unclaimed'}",
        f"Status: {ticket.status}",
        f"Subject: {ticket.subject}",
        "-" * 72,
    ]
    async for message in channel.history(limit=limit, oldest_first=True):
        created = message.created_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        author = f"{message.author} ({message.author.id})"
        content = message.clean_content or "[no text content]"
        lines.append(f"[{created}] {author}: {content}")
        for attachment in message.attachments:
            lines.append(f"    attachment: {attachment.filename} {attachment.url}")
        for embed in message.embeds:
            title = embed.title or "untitled embed"
            lines.append(f"    embed: {title}")
    lines.append("-" * 72)
    lines.append(f"Generated at: {utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    return ("\n".join(lines) + "\n").encode("utf-8")
