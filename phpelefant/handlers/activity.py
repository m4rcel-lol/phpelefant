from __future__ import annotations

from datetime import date, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant.config import Settings
from phpelefant.db.models import User
from phpelefant.services.activity import activity_since, get_activity, leaderboard, record_message, xp_required_for_level
from phpelefant.services.moderation import warning_count
from phpelefant.services.settings import get_or_create_chat_settings
from phpelefant.utils.text import html_escape

router = Router(name="activity")


async def _target_user_id(message: Message) -> int | None:
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id
    return message.from_user.id if message.from_user else None


@router.message(Command("rank", "level", "xp"))
async def rank(message: Message, session: AsyncSession) -> None:
    user_id = await _target_user_id(message)
    if user_id is None:
        await message.answer("No user found.")
        return
    snapshot = await get_activity(session, message.chat.id, user_id)
    next_level_xp = xp_required_for_level(snapshot.level + 1)
    await message.answer(
        f"User: <code>{user_id}</code>\n"
        f"Level: <code>{snapshot.level}</code>\n"
        f"XP: <code>{snapshot.xp}/{next_level_xp}</code>\n"
        f"Messages: <code>{snapshot.message_count}</code>"
    )


@router.message(Command("leaderboard", "top"))
async def top(message: Message, session: AsyncSession) -> None:
    rows = await leaderboard(session, message.chat.id, 10)
    if not rows:
        await message.answer("No activity recorded yet.")
        return
    lines = []
    for index, row in enumerate(rows, start=1):
        db_user = await session.get(User, row.user_id)
        label = html_escape(db_user.username if db_user and db_user.username else str(row.user_id))
        lines.append(f"{index}. {label}: level <code>{row.level}</code>, XP <code>{row.xp}</code>, messages <code>{row.message_count}</code>")
    await message.answer("<b>Leaderboard</b>\n" + "\n".join(lines))


@router.message(Command("activity"))
async def activity(message: Message, session: AsyncSession) -> None:
    today = date.today()
    daily = await activity_since(session, message.chat.id, today)
    weekly = await activity_since(session, message.chat.id, today - timedelta(days=7))
    daily_text = ", ".join(f"{uid}: {count}" for uid, count in daily) or "none"
    weekly_text = ", ".join(f"{uid}: {count}" for uid, count in weekly) or "none"
    await message.answer(f"<b>Activity</b>\nToday: {daily_text}\nLast 7 days: {weekly_text}")


@router.message(Command("profile"))
async def profile(message: Message, session: AsyncSession) -> None:
    user = message.reply_to_message.from_user if message.reply_to_message and message.reply_to_message.from_user else message.from_user
    if user is None:
        await message.answer("No user found.")
        return
    snapshot = await get_activity(session, message.chat.id, user.id)
    db_user = await session.get(User, user.id)
    warnings = await warning_count(session, message.chat.id, user.id)
    join_date = snapshot.joined_at.isoformat() if snapshot.joined_at else "unknown"
    await message.answer(
        f"<b>Profile</b>\n"
        f"User ID: <code>{user.id}</code>\n"
        f"Username: @{html_escape(user.username) if user.username else 'none'}\n"
        f"Join date: {join_date}\n"
        f"Message count: <code>{snapshot.message_count}</code>\n"
        f"XP: <code>{snapshot.xp}</code>\n"
        f"Level: <code>{snapshot.level}</code>\n"
        f"Warning count: <code>{warnings}</code>\n"
        f"Reputation score: <code>{db_user.reputation if db_user else 0}</code>"
    )


@router.message()
async def record_activity(message: Message, session: AsyncSession, settings: Settings) -> None:
    if message.chat.type not in {"group", "supergroup"} or message.from_user is None:
        return
    if message.text and message.text.startswith("/"):
        return
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    if row.activity_enabled:
        await record_message(session, message.chat.id, message.from_user.id)

