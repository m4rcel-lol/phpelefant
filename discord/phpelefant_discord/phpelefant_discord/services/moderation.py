from __future__ import annotations

from datetime import UTC, datetime, timedelta

import discord
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant_discord.db.models import GuildSettings, ModerationLog, Warning


async def log_action(
    session: AsyncSession,
    guild_id: int,
    action: str,
    target_user_id: int | None,
    actor_user_id: int | None,
    reason: str | None,
    metadata: dict | None = None,
) -> None:
    session.add(
        ModerationLog(
            guild_id=guild_id,
            action=action,
            target_user_id=target_user_id,
            actor_user_id=actor_user_id,
            reason=reason,
            extra_metadata=metadata or {},
        )
    )


async def add_warning(
    session: AsyncSession,
    settings: GuildSettings,
    member: discord.Member,
    moderator_id: int,
    reason: str,
) -> tuple[int, str | None]:
    session.add(Warning(guild_id=member.guild.id, user_id=member.id, moderator_id=moderator_id, reason=reason))
    await log_action(session, member.guild.id, "warn", member.id, moderator_id, reason)
    count = await warning_count(session, member.guild.id, member.id)
    auto_message = None
    if count >= settings.warning_limit:
        if settings.warn_limit_action == "ban":
            await member.ban(reason="Warning limit reached")
            await log_action(session, member.guild.id, "auto_ban", member.id, None, "Warning limit reached")
            auto_message = "Warning limit reached; member banned."
        else:
            until = datetime.now(tz=UTC) + timedelta(minutes=settings.warn_limit_timeout_minutes)
            await member.timeout(until, reason="Warning limit reached")
            await log_action(session, member.guild.id, "auto_timeout", member.id, None, "Warning limit reached")
            auto_message = f"Warning limit reached; member timed out for {settings.warn_limit_timeout_minutes} minutes."
    return count, auto_message


async def reset_warnings(session: AsyncSession, guild_id: int, user_id: int, moderator_id: int) -> int:
    result = await session.execute(
        update(Warning)
        .where(Warning.guild_id == guild_id, Warning.user_id == user_id, Warning.active.is_(True))
        .values(active=False)
    )
    await log_action(session, guild_id, "resetwarnings", user_id, moderator_id, None)
    return int(result.rowcount or 0)


async def warning_count(session: AsyncSession, guild_id: int, user_id: int) -> int:
    count = await session.scalar(
        select(func.count()).select_from(Warning).where(Warning.guild_id == guild_id, Warning.user_id == user_id, Warning.active.is_(True))
    )
    return int(count or 0)

