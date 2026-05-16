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
from phpelefant.services.shell import add_shell_user, is_shell_allowed, list_shell_users, remove_shell_user, run_real_shell
from phpelefant.services.settings import known_chat_ids, known_user_ids
from phpelefant.services.stats import global_counts
from phpelefant.utils.formatting import code_block, panel, truncate_for_code_block

router = Router(name="owner")


async def _owner_only(message: Message, settings: Settings) -> bool:
    if message.from_user and message.from_user.id == settings.bot_owner_id:
        return True
    await message.answer(code_block("Owner-only command.", "text"))
    return False


@router.message(Command("owner"))
async def owner_panel(message: Message, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    await message.answer(
        panel(
            "PHPelefant owner panel",
            [
                ("broadcast", "/broadcast <message>"),
                ("channel", "/broadcastchannel <message>"),
                ("global stats", "/statsglobal"),
                ("leave chat", "/leavechat <chat_id>"),
                ("blacklist user", "/blacklistuser <user_id> <reason>"),
                ("unblacklist user", "/unblacklistuser <user_id>"),
                ("blacklist chat", "/blacklistchat <chat_id> <reason>"),
                ("unblacklist chat", "/unblacklistchat <chat_id>"),
                ("shell", "/shell <command>"),
                ("shell users", "/shellusers add|remove|list"),
                ("backup", "/backupdb"),
                ("official channel", "/setofficialchannel <chat_id>"),
                ("restart", "/restart CONFIRM"),
                ("shutdown", "/shutdown CONFIRM"),
            ],
        )
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
        await message.answer(code_block("Use /broadcast <message>.", "text"))
        return
    targets = sorted(set(await known_chat_ids(session)) | set(await known_user_ids(session)))
    sent, failed = await _broadcast_to_targets(bot, targets, payload)
    session.add(BroadcastHistory(actor_user_id=message.from_user.id, target="all", message=payload, sent_count=sent, failed_count=failed))
    await log_action(session, message.chat.id, "owner_broadcast", None, message.from_user.id, f"{sent} sent, {failed} failed")
    await message.answer(panel("Broadcast complete", [("sent", sent), ("failed", failed)]))


@router.message(Command("broadcastchannel"))
async def broadcastchannel(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    payload = command_args(command)
    if not payload:
        await message.answer(code_block("Use /broadcastchannel <message>.", "text"))
        return
    try:
        await bot.send_message(settings.official_channel_id, payload)
    except Exception:
        session.add(BroadcastHistory(actor_user_id=message.from_user.id, target="official_channel", message=payload, sent_count=0, failed_count=1))
        await message.answer(code_block("Failed to send to the official channel. Check bot channel permissions.", "text"))
        return
    session.add(BroadcastHistory(actor_user_id=message.from_user.id, target="official_channel", message=payload, sent_count=1, failed_count=0))
    await message.answer(panel("Channel broadcast", [("sent to", settings.official_channel_id)]))


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
        panel(
            "Global statistics",
            [
                ("total groups", counts["groups"]),
                ("total users", counts["users"]),
                ("messages processed", counts["messages"]),
                ("moderation actions", counts["moderation_actions"]),
                ("uptime", uptime_text()),
                ("database", db_ok),
            ],
        )
    )


@router.message(Command("leavechat"))
async def leavechat(message: Message, command: CommandObject, bot: Bot, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    try:
        chat_id = int(command_args(command))
    except ValueError:
        await message.answer(code_block("Use /leavechat <chat_id>.", "text"))
        return
    try:
        await bot.leave_chat(chat_id)
    except Exception:
        await message.answer(code_block("Failed to leave that chat.", "text"))
        return
    await message.answer(panel("Leave chat", [("chat", chat_id), ("status", "left")]))


@router.message(Command("blacklistuser"))
async def blacklistuser(message: Message, command: CommandObject, session: AsyncSession, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    parts = command_args(command).split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(code_block("Use /blacklistuser <user_id> <reason>.", "text"))
        return
    try:
        user_id = int(parts[0])
    except ValueError:
        await message.answer(code_block("User ID must be numeric.", "text"))
        return
    if user_id == settings.bot_owner_id:
        await message.answer(code_block("Refusing to blacklist the bot owner.", "text"))
        return
    existing = await session.get(BlacklistedUser, user_id)
    if existing is None:
        session.add(BlacklistedUser(user_id=user_id, reason=parts[1], created_by=message.from_user.id))
    else:
        existing.reason = parts[1]
        existing.created_by = message.from_user.id
    await message.answer(panel("Blacklist user", [("user", user_id), ("status", "blacklisted")]))


@router.message(Command("unblacklistuser"))
async def unblacklistuser(message: Message, command: CommandObject, session: AsyncSession, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    try:
        user_id = int(command_args(command))
    except ValueError:
        await message.answer(code_block("Use /unblacklistuser <user_id>.", "text"))
        return
    await session.execute(delete(BlacklistedUser).where(BlacklistedUser.user_id == user_id))
    await message.answer(panel("Blacklist user", [("user", user_id), ("status", "removed if present")]))


@router.message(Command("blacklistchat"))
async def blacklistchat(message: Message, command: CommandObject, session: AsyncSession, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    parts = command_args(command).split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(code_block("Use /blacklistchat <chat_id> <reason>.", "text"))
        return
    try:
        chat_id = int(parts[0])
    except ValueError:
        await message.answer(code_block("Chat ID must be numeric.", "text"))
        return
    existing = await session.get(BlacklistedChat, chat_id)
    if existing is None:
        session.add(BlacklistedChat(chat_id=chat_id, reason=parts[1], created_by=message.from_user.id))
    else:
        existing.reason = parts[1]
        existing.created_by = message.from_user.id
    await message.answer(panel("Blacklist chat", [("chat", chat_id), ("status", "blacklisted")]))


@router.message(Command("unblacklistchat"))
async def unblacklistchat(message: Message, command: CommandObject, session: AsyncSession, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    try:
        chat_id = int(command_args(command))
    except ValueError:
        await message.answer(code_block("Use /unblacklistchat <chat_id>.", "text"))
        return
    await session.execute(delete(BlacklistedChat).where(BlacklistedChat.chat_id == chat_id))
    await message.answer(panel("Blacklist chat", [("chat", chat_id), ("status", "removed if present")]))


@router.message(Command("eval"))
async def eval_command(message: Message, command: CommandObject, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    if not settings.enable_eval:
        await message.answer(code_block("Eval is disabled. Set ENABLE_EVAL=true only in a controlled developer environment.", "text"))
        return
    expr = command_args(command)
    if len(expr) > 500:
        await message.answer(code_block("Expression too long.", "text"))
        return
    result = eval(expr, {"__builtins__": {}}, {"time": time.time})  # noqa: S307
    await message.answer(code_block(str(result)[: settings.shell_output_limit], "text"))


@router.message(Command("shell"))
async def shell_command(message: Message, command: CommandObject, session: AsyncSession, settings: Settings) -> None:
    if message.from_user is None:
        return
    if not await is_shell_allowed(session, message.from_user.id, settings):
        await message.answer(code_block("Shell access denied.", "text"))
        return
    raw = command_args(command)
    try:
        result = await run_real_shell(raw, settings)
    except ValueError as exc:
        await message.answer(panel("Shell rejected", [("reason", str(exc))]))
        return
    body, truncated = _render_shell_result(result, settings)
    await log_action(session, message.chat.id, "owner_shell", None, message.from_user.id, result.command)
    await message.answer(code_block(body, "text"))
    if truncated:
        await message.answer(code_block("Output was truncated. Narrow the command or use head/tail.", "text"))


@router.message(Command("shellusers"))
async def shellusers(message: Message, command: CommandObject, session: AsyncSession, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    args = command_args(command).split(maxsplit=2)
    if not args or args[0] not in {"add", "remove", "list"}:
        await message.answer(panel("Shell users", [("usage", "/shellusers add <user_id> [note]"), ("remove", "/shellusers remove <user_id>"), ("list", "/shellusers list")]))
        return
    action = args[0]
    if action == "list":
        users = await list_shell_users(session, settings)
        await message.answer(panel("Shell allowed users", [(str(index), user_id) for index, user_id in enumerate(users, start=1)]))
        return
    if len(args) < 2:
        await message.answer(code_block("Provide a numeric Telegram user ID.", "text"))
        return
    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer(code_block("User ID must be numeric.", "text"))
        return
    if action == "add":
        await add_shell_user(session, user_id, message.from_user.id, args[2] if len(args) > 2 else None)
        await log_action(session, message.chat.id, "owner_shell_allow_add", user_id, message.from_user.id, args[2] if len(args) > 2 else None)
        await message.answer(panel("Shell allowlist updated", [("added", user_id)]))
        return
    if user_id == settings.bot_owner_id:
        await message.answer(code_block("The owner always has shell access and cannot be removed.", "text"))
        return
    await remove_shell_user(session, user_id)
    await log_action(session, message.chat.id, "owner_shell_allow_remove", user_id, message.from_user.id, None)
    await message.answer(panel("Shell allowlist updated", [("removed", user_id)]))


def _render_shell_result(result, settings: Settings) -> tuple[str, bool]:
    output_parts = [f"$ {result.command}"]
    if result.timed_out:
        output_parts.append(f"timed out after {settings.shell_timeout_seconds}s")
    else:
        output_parts.append(f"exit code: {result.return_code}")
    if result.stdout:
        output_parts.append("\n[stdout]\n" + result.stdout.rstrip())
    if result.stderr:
        output_parts.append("\n[stderr]\n" + result.stderr.rstrip())
    if not result.stdout and not result.stderr:
        output_parts.append("\n(no output)")
    return truncate_for_code_block("\n".join(output_parts), settings.shell_output_limit)


@router.message(Command("restart"))
async def restart(message: Message, command: CommandObject, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    if command_args(command) != "CONFIRM":
        await message.answer(code_block("Use /restart CONFIRM to restart through the process supervisor.", "text"))
        return
    await message.answer(code_block("Restart requested.", "text"))
    asyncio.get_running_loop().call_later(1, signal.raise_signal, signal.SIGTERM)


@router.message(Command("shutdown"))
async def shutdown(message: Message, command: CommandObject, settings: Settings) -> None:
    if not await _owner_only(message, settings):
        return
    if command_args(command) != "CONFIRM":
        await message.answer(code_block("Use /shutdown CONFIRM to stop the bot.", "text"))
        return
    await message.answer(code_block("Shutdown requested.", "text"))
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
        await message.answer(code_block("Use /setofficialchannel <channel_id>.", "text"))
        return
    await session.execute(update(ChatSettings).values(official_channel_id=channel_id))
    await message.answer(panel("Official channel", [("channel", channel_id), ("status", "updated for all groups")]))
