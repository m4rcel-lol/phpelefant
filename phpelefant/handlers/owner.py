from __future__ import annotations

import asyncio
import signal
import time

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, Message
from sqlalchemy import delete, update, text
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant.config import Settings
from phpelefant.db.models import BlacklistedChat, BlacklistedUser, BroadcastHistory, ChatSettings
from phpelefant.handlers._helpers import command_args
from phpelefant.handlers.common import uptime_text
from phpelefant.services.backup import export_database_json
from phpelefant.services.moderation import log_action
from phpelefant.services.settings import known_chat_ids, known_user_ids
from phpelefant.services.stats import global_counts

router = Router(name="owner")


async def _owner_only(message: Message, settings: Settings) -> bool:
    if message.from_user and message.from_user.id == settings.bot_owner_id:
        return True
    await message.answer("Owner-only command.")
    return False


@router.message(Command("owner"))
async def owner_panel(message: Message, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    await message.answer(
        "<b>PHPelefant owner panel</b>\n"
        "/broadcast <message>\n"
        "/broadcastchannel <message>\n"
        "/statsglobal\n"
        "/leavechat <chat_id>\n"
        "/blacklistuser <user_id> <reason>\n"
        "/unblacklistuser <user_id>\n"
        "/blacklistchat <chat_id> <reason>\n"
        "/unblacklistchat <chat_id>\n"
        "/backupdb\n"
        "/setofficialchannel <chat_id>\n"
        "/restart CONFIRM\n"
        "/shutdown CONFIRM"
    )


async def _broadcast_to_targets(bot: Bot, targets: list[int], text_value: str) -> tuple[int, int]:
    sent = 0
    failed = 0
    for target in targets:
        try:
            await bot.send_message(target, text_value)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    return sent, failed


@router.message(Command("broadcast"))
async def broadcast(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    payload = command_args(command)
    if not payload:
        await message.answer("Use /broadcast <message>.")
        return
    targets = sorted(set(await known_chat_ids(session)) | set(await known_user_ids(session)))
    sent, failed = await _broadcast_to_targets(bot, targets, payload)
    session.add(BroadcastHistory(actor_user_id=message.from_user.id, target="all", message=payload, sent_count=sent, failed_count=failed))
    await log_action(session, message.chat.id, "owner_broadcast", None, message.from_user.id, f"{sent} sent, {failed} failed")
    await message.answer(f"Broadcast complete. Sent: <code>{sent}</code>, failed: <code>{failed}</code>.")


@router.message(Command("broadcastchannel"))
async def broadcastchannel(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    payload = command_args(command)
    if not payload:
        await message.answer("Use /broadcastchannel <message>.")
        return
    try:
        await bot.send_message(settings.official_channel_id, payload)
    except Exception:
        session.add(BroadcastHistory(actor_user_id=message.from_user.id, target="official_channel", message=payload, sent_count=0, failed_count=1))
        await message.answer("Failed to send to the official channel. Check bot channel permissions.")
        return
    session.add(BroadcastHistory(actor_user_id=message.from_user.id, target="official_channel", message=payload, sent_count=1, failed_count=0))
    await message.answer(f"Sent to official channel <code>{settings.official_channel_id}</code>.")


@router.message(Command("statsglobal"))
async def statsglobal(message: Message, session: AsyncSession, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    counts = await global_counts(session)
    db_ok = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_ok = "error"
    await message.answer(
        "<b>Global statistics</b>\n"
        f"Total groups: <code>{counts['groups']}</code>\n"
        f"Total users: <code>{counts['users']}</code>\n"
        f"Total messages processed: <code>{counts['messages']}</code>\n"
        f"Total moderation actions: <code>{counts['moderation_actions']}</code>\n"
        f"Uptime: <code>{uptime_text()}</code>\n"
        f"Database status: <code>{db_ok}</code>"
    )


@router.message(Command("leavechat"))
async def leavechat(message: Message, command: CommandObject, bot: Bot, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    try:
        chat_id = int(command_args(command))
    except ValueError:
        await message.answer("Use /leavechat <chat_id>.")
        return
    try:
        await bot.leave_chat(chat_id)
    except Exception:
        await message.answer("Failed to leave that chat.")
        return
    await message.answer(f"Left chat <code>{chat_id}</code>.")


@router.message(Command("blacklistuser"))
async def blacklistuser(message: Message, command: CommandObject, session: AsyncSession, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    parts = command_args(command).split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Use /blacklistuser <user_id> <reason>.")
        return
    try:
        user_id = int(parts[0])
    except ValueError:
        await message.answer("User ID must be numeric.")
        return
    if user_id == settings.bot_owner_id:
        await message.answer("Refusing to blacklist the bot owner.")
        return
    existing = await session.get(BlacklistedUser, user_id)
    if existing is None:
        session.add(BlacklistedUser(user_id=user_id, reason=parts[1], created_by=message.from_user.id))
    else:
        existing.reason = parts[1]
        existing.created_by = message.from_user.id
    await message.answer(f"Blacklisted user <code>{user_id}</code>.")


@router.message(Command("unblacklistuser"))
async def unblacklistuser(message: Message, command: CommandObject, session: AsyncSession, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    try:
        user_id = int(command_args(command))
    except ValueError:
        await message.answer("Use /unblacklistuser <user_id>.")
        return
    await session.execute(delete(BlacklistedUser).where(BlacklistedUser.user_id == user_id))
    await message.answer(f"Removed user <code>{user_id}</code> from blacklist if present.")


@router.message(Command("blacklistchat"))
async def blacklistchat(message: Message, command: CommandObject, session: AsyncSession, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    parts = command_args(command).split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Use /blacklistchat <chat_id> <reason>.")
        return
    try:
        chat_id = int(parts[0])
    except ValueError:
        await message.answer("Chat ID must be numeric.")
        return
    existing = await session.get(BlacklistedChat, chat_id)
    if existing is None:
        session.add(BlacklistedChat(chat_id=chat_id, reason=parts[1], created_by=message.from_user.id))
    else:
        existing.reason = parts[1]
        existing.created_by = message.from_user.id
    await message.answer(f"Blacklisted chat <code>{chat_id}</code>.")


@router.message(Command("unblacklistchat"))
async def unblacklistchat(message: Message, command: CommandObject, session: AsyncSession, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    try:
        chat_id = int(command_args(command))
    except ValueError:
        await message.answer("Use /unblacklistchat <chat_id>.")
        return
    await session.execute(delete(BlacklistedChat).where(BlacklistedChat.chat_id == chat_id))
    await message.answer(f"Removed chat <code>{chat_id}</code> from blacklist if present.")


@router.message(Command("eval"))
async def eval_command(message: Message, command: CommandObject, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    if not settings.enable_eval:
        await message.answer("Eval is disabled. Set ENABLE_EVAL=true only in a controlled developer environment.")
        return
    expr = command_args(command)
    if len(expr) > 500:
        await message.answer("Expression too long.")
        return
    result = eval(expr, {"__builtins__": {}}, {"time": time.time})  # noqa: S307
    await message.answer(f"<code>{str(result)[:3500]}</code>")


@router.message(Command("restart"))
async def restart(message: Message, command: CommandObject, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    if command_args(command) != "CONFIRM":
        await message.answer("Use /restart CONFIRM to restart through the process supervisor.")
        return
    await message.answer("Restart requested.")
    asyncio.get_running_loop().call_later(1, signal.raise_signal, signal.SIGTERM)


@router.message(Command("shutdown"))
async def shutdown(message: Message, command: CommandObject, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    if command_args(command) != "CONFIRM":
        await message.answer("Use /shutdown CONFIRM to stop the bot.")
        return
    await message.answer("Shutdown requested.")
    asyncio.get_running_loop().call_later(1, signal.raise_signal, signal.SIGTERM)


@router.message(Command("backupdb"))
async def backupdb(message: Message, session: AsyncSession, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    payload = await export_database_json(session)
    await message.answer_document(BufferedInputFile(payload, filename="phpelefant-backup.json"), caption="Database backup.")


@router.message(Command("setofficialchannel"))
async def setofficialchannel(message: Message, command: CommandObject, session: AsyncSession, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    args = command_args(command)
    try:
        channel_id = int(args) if args else settings.official_channel_id
    except ValueError:
        await message.answer("Use /setofficialchannel <channel_id>.")
        return
    await session.execute(update(ChatSettings).values(official_channel_id=channel_id))
    await message.answer(f"Official channel set to <code>{channel_id}</code> for all configured groups.")
