from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant.db.models import ActivityDaily, MemberActivity

XP_PER_MESSAGE = 5
XP_COOLDOWN_SECONDS = 45


def level_for_xp(xp: int) -> int:
    if xp <= 0:
        return 0
    level = 0
    while xp >= xp_required_for_level(level + 1):
        level += 1
    return level


def xp_required_for_level(level: int) -> int:
    return 100 * level * level


@dataclass(slots=True)
class ActivitySnapshot:
    message_count: int
    xp: int
    level: int
    joined_at: datetime | None


async def ensure_member_activity(session: AsyncSession, chat_id: int, user_id: int) -> MemberActivity:
    result = await session.scalar(
        select(MemberActivity).where(MemberActivity.chat_id == chat_id, MemberActivity.user_id == user_id)
    )
    if result is not None:
        return result
    result = MemberActivity(chat_id=chat_id, user_id=user_id)
    session.add(result)
    await session.flush()
    return result


async def mark_joined(session: AsyncSession, chat_id: int, user_id: int, joined_at: datetime | None = None) -> None:
    activity = await ensure_member_activity(session, chat_id, user_id)
    activity.joined_at = joined_at or datetime.now(tz=UTC)


async def record_message(session: AsyncSession, chat_id: int, user_id: int, now: datetime | None = None) -> ActivitySnapshot:
    current = now or datetime.now(tz=UTC)
    activity = await ensure_member_activity(session, chat_id, user_id)
    activity.message_count += 1
    activity.last_message_at = current
    award_xp = activity.last_xp_at is None or current - activity.last_xp_at >= timedelta(seconds=XP_COOLDOWN_SECONDS)
    gained = XP_PER_MESSAGE if award_xp else 0
    if gained:
        activity.xp += gained
        activity.last_xp_at = current
        activity.level = level_for_xp(activity.xp)

    day = current.date()
    daily = await session.scalar(
        select(ActivityDaily).where(ActivityDaily.chat_id == chat_id, ActivityDaily.user_id == user_id, ActivityDaily.day == day)
    )
    if daily is None:
        daily = ActivityDaily(chat_id=chat_id, user_id=user_id, day=day)
        session.add(daily)
        await session.flush()
    daily.message_count += 1
    daily.xp += gained
    return ActivitySnapshot(activity.message_count, activity.xp, activity.level, activity.joined_at)


async def get_activity(session: AsyncSession, chat_id: int, user_id: int) -> ActivitySnapshot:
    activity = await ensure_member_activity(session, chat_id, user_id)
    return ActivitySnapshot(activity.message_count, activity.xp, activity.level, activity.joined_at)


async def leaderboard(session: AsyncSession, chat_id: int, limit: int = 10) -> list[MemberActivity]:
    result = await session.scalars(
        select(MemberActivity)
        .where(MemberActivity.chat_id == chat_id)
        .order_by(desc(MemberActivity.xp), desc(MemberActivity.message_count))
        .limit(limit)
    )
    return list(result)


async def activity_since(session: AsyncSession, chat_id: int, start_day: date, limit: int = 10) -> list[tuple[int, int]]:
    result = await session.execute(
        select(ActivityDaily.user_id, ActivityDaily.message_count)
        .where(ActivityDaily.chat_id == chat_id, ActivityDaily.day >= start_day)
        .order_by(desc(ActivityDaily.message_count))
        .limit(limit)
    )
    return [(int(row[0]), int(row[1])) for row in result]

