from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging

from aiogram import Bot
from aiogram.types import ChatPermissions
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant.db.models import ChatSettings, ModerationLog, Warning
from phpelefant.utils.telegram import telegram_call

logger = logging.getLogger(__name__)

MUTED_PERMISSIONS = ChatPermissions(can_send_messages=False)
UNMUTED_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
)
LOCKED_PERMISSIONS = ChatPermissions(can_send_messages=False)
UNLOCKED_PERMISSIONS = UNMUTED_PERMISSIONS


async def log_action(
    session: AsyncSession,
    chat_id: int,
    action: str,
    target_user_id: int | None,
    actor_user_id: int | None,
    reason: str | None,
    metadata: dict | None = None,
) -> None:
    session.add(
        ModerationLog(
            chat_id=chat_id,
            action=action,
            target_user_id=target_user_id,
            actor_user_id=actor_user_id,
            reason=reason,
            extra_metadata=metadata or {},
        )
    )


async def send_log(bot: Bot, settings: ChatSettings, text: str) -> None:
    if settings.log_channel_id:
        ok, err = await telegram_call(lambda: bot.send_message(settings.log_channel_id, text))
        if not ok:
            logger.info("Failed to send log channel message: %s", err)


async def ban_user(bot: Bot, session: AsyncSession, chat_id: int, target_id: int, actor_id: int | None, reason: str | None) -> tuple[bool, str]:
    ok, result = await telegram_call(
        lambda: bot.ban_chat_member(chat_id=chat_id, user_id=target_id),
        "I could not ban that user. Check my admin permissions.",
    )
    if ok:
        await log_action(session, chat_id, "ban", target_id, actor_id, reason)
        return True, f"Banned user `{target_id}`. Reason: {reason or 'No reason provided'}"
    return False, str(result)


async def unban_user(bot: Bot, session: AsyncSession, chat_id: int, target_id: int, actor_id: int | None, reason: str | None) -> tuple[bool, str]:
    ok, result = await telegram_call(
        lambda: bot.unban_chat_member(chat_id=chat_id, user_id=target_id, only_if_banned=True),
        "I could not unban that user.",
    )
    if ok:
        await log_action(session, chat_id, "unban", target_id, actor_id, reason)
        return True, f"Unbanned user `{target_id}`."
    return False, str(result)


async def kick_user(bot: Bot, session: AsyncSession, chat_id: int, target_id: int, actor_id: int | None, reason: str | None) -> tuple[bool, str]:
    ok, result = await telegram_call(
        lambda: bot.ban_chat_member(chat_id=chat_id, user_id=target_id, until_date=datetime.now(tz=UTC) + timedelta(seconds=45)),
        "I could not kick that user. Check my admin permissions.",
    )
    if not ok:
        return False, str(result)
    await telegram_call(lambda: bot.unban_chat_member(chat_id=chat_id, user_id=target_id, only_if_banned=True))
    await log_action(session, chat_id, "kick", target_id, actor_id, reason)
    return True, f"Kicked user `{target_id}`. Reason: {reason or 'No reason provided'}"


async def mute_user(
    bot: Bot,
    session: AsyncSession,
    chat_id: int,
    target_id: int,
    actor_id: int | None,
    reason: str | None,
    duration: timedelta | None,
) -> tuple[bool, str]:
    until_date = datetime.now(tz=UTC) + duration if duration else None
    ok, result = await telegram_call(
        lambda: bot.restrict_chat_member(chat_id=chat_id, user_id=target_id, permissions=MUTED_PERMISSIONS, until_date=until_date),
        "I could not mute that user. Check my admin permissions.",
    )
    if ok:
        await log_action(session, chat_id, "mute", target_id, actor_id, reason, {"duration_seconds": int(duration.total_seconds()) if duration else None})
        suffix = f" for {duration}" if duration else ""
        return True, f"Muted user `{target_id}`{suffix}. Reason: {reason or 'No reason provided'}"
    return False, str(result)


async def unmute_user(bot: Bot, session: AsyncSession, chat_id: int, target_id: int, actor_id: int | None, reason: str | None) -> tuple[bool, str]:
    ok, result = await telegram_call(
        lambda: bot.restrict_chat_member(chat_id=chat_id, user_id=target_id, permissions=UNMUTED_PERMISSIONS),
        "I could not unmute that user.",
    )
    if ok:
        await log_action(session, chat_id, "unmute", target_id, actor_id, reason)
        return True, f"Unmuted user `{target_id}`."
    return False, str(result)


async def add_warning(
    bot: Bot,
    session: AsyncSession,
    settings: ChatSettings,
    chat_id: int,
    target_id: int,
    actor_id: int,
    reason: str,
) -> tuple[int, str | None]:
    session.add(Warning(chat_id=chat_id, user_id=target_id, admin_id=actor_id, reason=reason))
    await log_action(session, chat_id, "warn", target_id, actor_id, reason)
    count = await session.scalar(
        select(func.count()).select_from(Warning).where(Warning.chat_id == chat_id, Warning.user_id == target_id, Warning.active.is_(True))
    )
    active_count = int(count or 0)
    auto_message: str | None = None
    if active_count >= settings.warning_limit:
        if settings.warn_limit_action == "ban":
            _, auto_message = await ban_user(bot, session, chat_id, target_id, None, "Warning limit reached")
        else:
            duration = timedelta(minutes=settings.warn_limit_mute_minutes)
            _, auto_message = await mute_user(bot, session, chat_id, target_id, None, "Warning limit reached", duration)
    return active_count, auto_message


async def reset_warnings(session: AsyncSession, chat_id: int, target_id: int, actor_id: int) -> int:
    result = await session.execute(
        update(Warning)
        .where(Warning.chat_id == chat_id, Warning.user_id == target_id, Warning.active.is_(True))
        .values(active=False)
    )
    await log_action(session, chat_id, "resetwarnings", target_id, actor_id, None)
    return int(result.rowcount or 0)


async def warning_count(session: AsyncSession, chat_id: int, target_id: int) -> int:
    count = await session.scalar(
        select(func.count()).select_from(Warning).where(Warning.chat_id == chat_id, Warning.user_id == target_id, Warning.active.is_(True))
    )
    return int(count or 0)

