from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant.db.models import BotStatistic, Chat, ModerationLog, User


async def increment_stat(session: AsyncSession, key: str, amount: int = 1) -> None:
    stat = await session.get(BotStatistic, key)
    if stat is None:
        session.add(BotStatistic(key=key, value=amount))
    else:
        stat.value += amount


async def get_stat(session: AsyncSession, key: str) -> int:
    stat = await session.get(BotStatistic, key)
    return stat.value if stat else 0


async def global_counts(session: AsyncSession) -> dict[str, int]:
    groups = await session.scalar(select(func.count()).select_from(Chat).where(Chat.type.in_(["group", "supergroup"])))
    users = await session.scalar(select(func.count()).select_from(User))
    actions = await session.scalar(select(func.count()).select_from(ModerationLog))
    messages = await get_stat(session, "messages_processed")
    return {
        "groups": int(groups or 0),
        "users": int(users or 0),
        "messages": int(messages),
        "moderation_actions": int(actions or 0),
    }

