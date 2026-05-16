from __future__ import annotations

import discord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant_discord.config import Settings
from phpelefant_discord.db.models import Guild, GuildSettings, User


async def upsert_user(session: AsyncSession, user: discord.User | discord.Member) -> None:
    row = await session.get(User, user.id)
    if row is None:
        session.add(User(discord_id=user.id, username=str(user), display_name=user.display_name, is_bot=user.bot))
        return
    row.username = str(user)
    row.display_name = user.display_name
    row.is_bot = user.bot


async def upsert_guild(session: AsyncSession, guild: discord.Guild, settings: Settings) -> None:
    row = await session.get(Guild, guild.id)
    if row is None:
        session.add(Guild(guild_id=guild.id, name=guild.name, owner_id=guild.owner_id))
        await session.flush()
        session.add(
            GuildSettings(
                guild_id=guild.id,
                official_channel_id=settings.official_channel_id,
                language=settings.default_language,
                timezone=settings.default_timezone,
            )
        )
        return
    row.name = guild.name
    row.owner_id = guild.owner_id


async def get_or_create_guild_settings(session: AsyncSession, guild_id: int, settings: Settings) -> GuildSettings:
    row = await session.get(GuildSettings, guild_id)
    if row is not None:
        return row
    row = GuildSettings(
        guild_id=guild_id,
        official_channel_id=settings.official_channel_id,
        language=settings.default_language,
        timezone=settings.default_timezone,
    )
    session.add(row)
    await session.flush()
    return row


async def known_guild_ids(session: AsyncSession) -> list[int]:
    result = await session.scalars(select(Guild.guild_id))
    return list(result)


async def known_user_ids(session: AsyncSession) -> list[int]:
    result = await session.scalars(select(User.discord_id))
    return list(result)

