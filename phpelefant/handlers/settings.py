from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant.config import Settings
from phpelefant.db.models import BadWord, WhitelistedDomain, WhitelistedUser
from phpelefant.handlers._helpers import command_args, ensure_group_admin, parse_user_id
from phpelefant.services.moderation import log_action
from phpelefant.services.settings import get_or_create_chat_settings
from phpelefant.utils.text import html_escape

router = Router(name="settings")


def _on_off(value: str) -> bool | None:
    normalized = value.strip().casefold()
    if normalized == "on":
        return True
    if normalized == "off":
        return False
    return None


async def _set_bool_setting(
    message: Message,
    command: CommandObject,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
    attr: str,
    label: str,
) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    value = _on_off(command_args(command))
    if value is None:
        await message.answer(f"Use /{label} on or /{label} off.")
        return
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    setattr(row, attr, value)
    await log_action(session, message.chat.id, label, None, message.from_user.id, str(value))
    await message.answer(f"{label} set to <code>{value}</code>.")


@router.message(Command("setlogchannel"))
async def setlogchannel(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    args = command_args(command)
    if args.casefold() == "off":
        channel_id = None
    else:
        try:
            channel_id = int(args)
        except ValueError:
            await message.answer("Use /setlogchannel <channel_id> or /setlogchannel off.")
            return
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    row.log_channel_id = channel_id
    await log_action(session, message.chat.id, "setlogchannel", None, message.from_user.id, str(channel_id))
    await message.answer(f"Log channel set to <code>{channel_id or 'off'}</code>.")


@router.message(Command("setwarnlimit"))
async def setwarnlimit(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    try:
        limit = int(command_args(command))
    except ValueError:
        await message.answer("Use /setwarnlimit <1-20>.")
        return
    if not 1 <= limit <= 20:
        await message.answer("Warning limit must be between 1 and 20.")
        return
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    row.warning_limit = limit
    await log_action(session, message.chat.id, "setwarnlimit", None, message.from_user.id, str(limit))
    await message.answer(f"Warning limit set to <code>{limit}</code>.")


@router.message(Command("antispam"))
async def antispam(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    await _set_bool_setting(message, command, bot, session, settings, "anti_spam_enabled", "antispam")


@router.message(Command("antilink"))
async def antilink(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    await _set_bool_setting(message, command, bot, session, settings, "anti_link_enabled", "antilink")


@router.message(Command("anticaps"))
async def anticaps(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    await _set_bool_setting(message, command, bot, session, settings, "anti_caps_enabled", "anticaps")


@router.message(Command("forcesub"))
async def forcesub(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    await _set_bool_setting(message, command, bot, session, settings, "force_subscribe_enabled", "forcesub")


@router.message(Command("forcesubstatus"))
async def forcesubstatus(message: Message, session: AsyncSession, settings: Settings) -> None:
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    await message.answer(
        f"Force-subscribe: <code>{row.force_subscribe_enabled}</code>\n"
        f"Official channel: <code>{row.official_channel_id}</code>"
    )


@router.message(Command("badwords"))
async def badwords(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    args = command_args(command).split(maxsplit=1)
    if not args or args[0] not in {"add", "remove", "list"}:
        await message.answer("Use /badwords add <word>, /badwords remove <word>, or /badwords list.")
        return
    action = args[0]
    if action == "list":
        result = await session.scalars(select(BadWord.word).where(BadWord.chat_id == message.chat.id).order_by(BadWord.word))
        words = list(result)
        await message.answer("Bad words: " + (", ".join(html_escape(word) for word in words) if words else "none"))
        return
    if len(args) < 2 or not args[1].strip():
        await message.answer("Provide a word.")
        return
    word = args[1].strip().casefold()[:255]
    if action == "add":
        exists = await session.scalar(select(BadWord).where(BadWord.chat_id == message.chat.id, BadWord.word == word))
        if exists is not None:
            await message.answer("That word is already configured.")
            return
        session.add(BadWord(chat_id=message.chat.id, word=word))
        await message.answer("Bad word added.")
    else:
        await session.execute(delete(BadWord).where(BadWord.chat_id == message.chat.id, BadWord.word == word))
        await message.answer("Bad word removed if it existed.")


@router.message(Command("whitelist"))
async def whitelist(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    args = command_args(command).split(maxsplit=2)
    if not args or args[0] not in {"add", "remove", "list", "domain"}:
        await message.answer("Use /whitelist add <user_id>, /whitelist remove <user_id>, /whitelist list, or /whitelist domain <domain>.")
        return
    action = args[0]
    if action == "list":
        users = await session.scalars(select(WhitelistedUser.user_id).where(WhitelistedUser.chat_id == message.chat.id))
        domains = await session.scalars(select(WhitelistedDomain.domain).where(WhitelistedDomain.chat_id == message.chat.id))
        await message.answer(
            "Whitelisted users: "
            + (", ".join(f"<code>{uid}</code>" for uid in users) or "none")
            + "\nWhitelisted domains: "
            + (", ".join(html_escape(domain) for domain in domains) or "none")
        )
        return
    if action == "domain":
        if len(args) < 2:
            await message.answer("Use /whitelist domain <domain>.")
            return
        domain = args[1].strip().casefold().removeprefix("www.")[:255]
        exists = await session.scalar(
            select(WhitelistedDomain).where(WhitelistedDomain.chat_id == message.chat.id, WhitelistedDomain.domain == domain)
        )
        if exists is None:
            session.add(WhitelistedDomain(chat_id=message.chat.id, domain=domain))
        await message.answer("Domain whitelisted.")
        return
    if len(args) < 2:
        await message.answer("Provide a user ID.")
        return
    try:
        user_id = parse_user_id(args[1])
    except ValueError as exc:
        await message.answer(str(exc))
        return
    if action == "add":
        exists = await session.scalar(
            select(WhitelistedUser).where(WhitelistedUser.chat_id == message.chat.id, WhitelistedUser.user_id == user_id)
        )
        if exists is None:
            session.add(WhitelistedUser(chat_id=message.chat.id, user_id=user_id, reason=args[2] if len(args) > 2 else None))
        await message.answer(f"User <code>{user_id}</code> whitelisted.")
    else:
        await session.execute(delete(WhitelistedUser).where(WhitelistedUser.chat_id == message.chat.id, WhitelistedUser.user_id == user_id))
        await message.answer(f"User <code>{user_id}</code> removed from whitelist if present.")
