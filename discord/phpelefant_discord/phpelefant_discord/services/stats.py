from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant_discord.db.models import BotStatistic, Guild, ModerationLog, User


async def increment_stat(session: AsyncSession, key: str, amount: int = 1) -> None:
    row = await session.get(BotStatistic, key)
    if row is None:
        session.add(BotStatistic(key=key, value=amount))
    else:
        row.value += amount


async def get_stat(session: AsyncSession, key: str) -> int:
    row = await session.get(BotStatistic, key)
    return row.value if row else 0


async def global_counts(session: AsyncSession) -> dict[str, int]:
    guilds = await session.scalar(select(func.count()).select_from(Guild))
    users = await session.scalar(select(func.count()).select_from(User))
    actions = await session.scalar(select(func.count()).select_from(ModerationLog))
    messages = await get_stat(session, "messages_processed")
    return {
        "guilds": int(guilds or 0),
        "users": int(users or 0),
        "messages": int(messages),
        "moderation_actions": int(actions or 0),
    }

