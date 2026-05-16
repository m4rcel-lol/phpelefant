from __future__ import annotations

from datetime import timedelta

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant.config import Settings
from phpelefant.handlers._helpers import (
    CommandError,
    command_args,
    ensure_can_moderate,
    ensure_group_admin,
    parse_mute_args,
    parse_target_and_reason,
)
from phpelefant.services.moderation import (
    LOCKED_PERMISSIONS,
    UNLOCKED_PERMISSIONS,
    add_warning,
    ban_user,
    kick_user,
    log_action,
    mute_user,
    reset_warnings,
    unban_user,
    unmute_user,
    warning_count,
)
from phpelefant.services.settings import get_or_create_chat_settings
from phpelefant.utils.telegram import telegram_call
from phpelefant.utils.text import html_escape
from phpelefant.utils.time import parse_duration

router = Router(name="moderation")


async def _handle_command_error(message: Message, exc: CommandError) -> None:
    await message.answer(str(exc))


@router.message(Command("ban"))
async def ban(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    try:
        parsed = parse_target_and_reason(message, command)
    except CommandError as exc:
        await _handle_command_error(message, exc)
        return
    if not await ensure_can_moderate(message, bot, settings, parsed.target_id):
        return
    ok, result = await ban_user(bot, session, message.chat.id, parsed.target_id, message.from_user.id, parsed.reason)
    await message.answer(result)


@router.message(Command("unban"))
async def unban(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    try:
        parsed = parse_target_and_reason(message, command)
    except CommandError as exc:
        await _handle_command_error(message, exc)
        return
    ok, result = await unban_user(bot, session, message.chat.id, parsed.target_id, message.from_user.id, parsed.reason)
    await message.answer(result)


@router.message(Command("kick"))
async def kick(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    try:
        parsed = parse_target_and_reason(message, command)
    except CommandError as exc:
        await _handle_command_error(message, exc)
        return
    if not await ensure_can_moderate(message, bot, settings, parsed.target_id):
        return
    ok, result = await kick_user(bot, session, message.chat.id, parsed.target_id, message.from_user.id, parsed.reason)
    await message.answer(result)


@router.message(Command("mute"))
async def mute(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    try:
        parsed = parse_mute_args(message, command)
        duration = parse_duration(parsed.duration_text) if parsed.duration_text else None
    except (CommandError, ValueError) as exc:
        await message.answer(str(exc))
        return
    if not await ensure_can_moderate(message, bot, settings, parsed.target_id):
        return
    ok, result = await mute_user(bot, session, message.chat.id, parsed.target_id, message.from_user.id, parsed.reason, duration)
    await message.answer(result)


@router.message(Command("unmute"))
async def unmute(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    try:
        parsed = parse_target_and_reason(message, command)
    except CommandError as exc:
        await _handle_command_error(message, exc)
        return
    ok, result = await unmute_user(bot, session, message.chat.id, parsed.target_id, message.from_user.id, parsed.reason)
    await message.answer(result)


@router.message(Command("warn"))
async def warn(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    try:
        parsed = parse_target_and_reason(message, command)
    except CommandError as exc:
        await _handle_command_error(message, exc)
        return
    if not await ensure_can_moderate(message, bot, settings, parsed.target_id):
        return
    chat_settings = await get_or_create_chat_settings(session, message.chat.id, settings)
    count, auto = await add_warning(bot, session, chat_settings, message.chat.id, parsed.target_id, message.from_user.id, parsed.reason)
    reply = f"Warned user <code>{parsed.target_id}</code>. Warnings: <code>{count}/{chat_settings.warning_limit}</code>"
    if auto:
        reply += f"\n{auto}"
    await message.answer(reply)


@router.message(Command("warnings"))
async def warnings(message: Message, command: CommandObject, session: AsyncSession) -> None:
    try:
        parsed = parse_target_and_reason(message, command)
    except CommandError as exc:
        await _handle_command_error(message, exc)
        return
    count = await warning_count(session, message.chat.id, parsed.target_id)
    await message.answer(f"User <code>{parsed.target_id}</code> has <code>{count}</code> active warning(s).")


@router.message(Command("resetwarnings"))
async def resetwarnings(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    try:
        parsed = parse_target_and_reason(message, command)
    except CommandError as exc:
        await _handle_command_error(message, exc)
        return
    count = await reset_warnings(session, message.chat.id, parsed.target_id, message.from_user.id)
    await message.answer(f"Reset <code>{count}</code> warning(s) for <code>{parsed.target_id}</code>.")


@router.message(Command("purge"))
async def purge(message: Message, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    if not message.reply_to_message:
        await message.answer("Reply to the first message to purge.")
        return
    first = message.reply_to_message.message_id
    last = message.message_id
    if last - first > 1000:
        await message.answer("Refusing to purge more than 1000 messages at once.")
        return
    deleted = 0
    for message_id in range(first, last + 1):
        ok, _ = await telegram_call(lambda mid=message_id: bot.delete_message(message.chat.id, mid))
        if ok:
            deleted += 1
    await log_action(session, message.chat.id, "purge", None, message.from_user.id, f"{deleted} messages")
    await message.answer(f"Purged <code>{deleted}</code> messages.")


@router.message(Command("delete"))
async def delete(message: Message, session: AsyncSession, settings: Settings, bot: Bot) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    if not message.reply_to_message:
        await message.answer("Reply to a message to delete it.")
        return
    await telegram_call(lambda: message.reply_to_message.delete(), "I could not delete that message.")
    await telegram_call(lambda: message.delete())
    await log_action(session, message.chat.id, "delete", None, message.from_user.id, None)


@router.message(Command("lock"))
async def lock(message: Message, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    ok, result = await telegram_call(lambda: bot.set_chat_permissions(message.chat.id, LOCKED_PERMISSIONS), "I could not lock the chat.")
    if ok:
        await log_action(session, message.chat.id, "lock", None, message.from_user.id, None)
        await message.answer("Chat locked.")
    else:
        await message.answer(str(result))


@router.message(Command("unlock"))
async def unlock(message: Message, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    ok, result = await telegram_call(lambda: bot.set_chat_permissions(message.chat.id, UNLOCKED_PERMISSIONS), "I could not unlock the chat.")
    if ok:
        await log_action(session, message.chat.id, "unlock", None, message.from_user.id, None)
        await message.answer("Chat unlocked.")
    else:
        await message.answer(str(result))


@router.message(Command("slowmode"))
async def slowmode(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    args = command_args(command)
    if not args:
        await message.answer("Use /slowmode <seconds>, from 0 to 3600.")
        return
    try:
        delay = int(args)
    except ValueError:
        await message.answer("Slowmode must be a number of seconds.")
        return
    if not 0 <= delay <= 3600:
        await message.answer("Slowmode must be between 0 and 3600 seconds.")
        return
    ok, result = await telegram_call(lambda: bot.set_chat_slow_mode_delay(message.chat.id, delay), "I could not change slowmode.")
    if ok:
        await log_action(session, message.chat.id, "slowmode", None, message.from_user.id, str(delay))
        await message.answer(f"Slowmode set to <code>{delay}</code> seconds.")
    else:
        await message.answer(str(result))


@router.message(Command("rules"))
async def rules(message: Message, session: AsyncSession, settings: Settings) -> None:
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    await message.answer(f"<b>Rules</b>\n{html_escape(row.rules_text)}")


@router.message(Command("setrules"))
async def setrules(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    text = command_args(command)
    if len(text) < 3:
        await message.answer("Use /setrules <rules text>.")
        return
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    row.rules_text = text[:4000]
    await log_action(session, message.chat.id, "setrules", None, message.from_user.id, None)
    await message.answer("Rules updated.")


@router.message(Command("pin"))
async def pin(message: Message, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    if not message.reply_to_message:
        await message.answer("Reply to the message to pin.")
        return
    ok, result = await telegram_call(lambda: bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id, disable_notification=True), "I could not pin that message.")
    await message.answer("Message pinned." if ok else str(result))


@router.message(Command("unpin"))
async def unpin(message: Message, bot: Bot, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    target_id = message.reply_to_message.message_id if message.reply_to_message else None
    ok, result = await telegram_call(lambda: bot.unpin_chat_message(message.chat.id, target_id), "I could not unpin that message.")
    await message.answer("Message unpinned." if ok else str(result))


@router.message(Command("report"))
async def report(message: Message, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("Reports are only useful in groups.")
        return
    if not message.reply_to_message or not message.from_user:
        await message.answer("Reply to a message to report it.")
        return
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    text = (
        f"Report in <code>{message.chat.id}</code>\n"
        f"Reporter: <code>{message.from_user.id}</code>\n"
        f"Reported message ID: <code>{message.reply_to_message.message_id}</code>"
    )
    if row.log_channel_id:
        await bot.send_message(row.log_channel_id, text)
        await message.answer("Report sent to the moderation log.")
    else:
        await message.answer("Report received. Configure /setlogchannel to send reports to a private admin log.")
    await log_action(session, message.chat.id, "report", message.reply_to_message.from_user.id if message.reply_to_message.from_user else None, message.from_user.id, None)


@router.message(Command("adminlist"))
async def adminlist(message: Message, bot: Bot) -> None:
    if message.chat.type not in {"group", "supergroup"}:
        await message.answer("This command is only available in groups.")
        return
    admins = await bot.get_chat_administrators(message.chat.id)
    lines = [f"- {html_escape(admin.user.full_name)} (<code>{admin.user.id}</code>)" for admin in admins]
    await message.answer("<b>Admins</b>\n" + "\n".join(lines))

