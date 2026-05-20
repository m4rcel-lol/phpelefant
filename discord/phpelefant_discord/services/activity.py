from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant_discord.db.models import ActivityDaily, MemberActivity

XP_PER_MESSAGE = 5


def xp_required_for_level(level: int) -> int:
    return 100 * level * level


def level_for_xp(xp: int) -> int:
    level = 0
    while xp >= xp_required_for_level(level + 1):
        level += 1
    return level


@dataclass(slots=True)
class ActivitySnapshot:
    message_count: int
    xp: int
    level: int
    joined_at: datetime | None


def as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def ensure_member_activity(session: AsyncSession, guild_id: int, user_id: int) -> MemberActivity:
    row = await session.scalar(select(MemberActivity).where(MemberActivity.guild_id == guild_id, MemberActivity.user_id == user_id))
    if row is not None:
        return row
    row = MemberActivity(guild_id=guild_id, user_id=user_id)
    session.add(row)
    await session.flush()
    return row


async def mark_joined(session: AsyncSession, guild_id: int, user_id: int, joined_at: datetime | None = None) -> None:
    row = await ensure_member_activity(session, guild_id, user_id)
    row.joined_at = joined_at or datetime.now(tz=UTC)


async def record_message(session: AsyncSession, guild_id: int, user_id: int, xp_cooldown_seconds: int) -> ActivitySnapshot:
    now = datetime.now(tz=UTC)
    row = await ensure_member_activity(session, guild_id, user_id)
    row.message_count += 1
    row.last_message_at = now
    last_xp_at = as_aware_utc(row.last_xp_at)
    award = last_xp_at is None or now - last_xp_at >= timedelta(seconds=xp_cooldown_seconds)
    gained = XP_PER_MESSAGE if award else 0
    if gained:
        row.xp += gained
        row.last_xp_at = now
        row.level = level_for_xp(row.xp)
    daily = await session.scalar(
        select(ActivityDaily).where(ActivityDaily.guild_id == guild_id, ActivityDaily.user_id == user_id, ActivityDaily.day == now.date())
    )
    if daily is None:
        daily = ActivityDaily(guild_id=guild_id, user_id=user_id, day=now.date())
        session.add(daily)
        await session.flush()
    daily.message_count += 1
    daily.xp += gained
    return ActivitySnapshot(row.message_count, row.xp, row.level, as_aware_utc(row.joined_at))


async def get_activity(session: AsyncSession, guild_id: int, user_id: int) -> ActivitySnapshot:
    row = await ensure_member_activity(session, guild_id, user_id)
    return ActivitySnapshot(row.message_count, row.xp, row.level, as_aware_utc(row.joined_at))


async def leaderboard(session: AsyncSession, guild_id: int, limit: int = 10) -> list[MemberActivity]:
    result = await session.scalars(
        select(MemberActivity)
        .where(MemberActivity.guild_id == guild_id)
        .order_by(desc(MemberActivity.xp), desc(MemberActivity.message_count))
        .limit(limit)
    )
    return list(result)


async def activity_since(session: AsyncSession, guild_id: int, start_day: date, limit: int = 10) -> list[tuple[int, int]]:
    result = await session.execute(
        select(ActivityDaily.user_id, ActivityDaily.message_count)
        .where(ActivityDaily.guild_id == guild_id, ActivityDaily.day >= start_day)
        .order_by(desc(ActivityDaily.message_count))
        .limit(limit)
    )
    return [(int(row[0]), int(row[1])) for row in result]
