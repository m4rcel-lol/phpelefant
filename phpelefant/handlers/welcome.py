from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant.config import Settings
from phpelefant.handlers._helpers import command_args, ensure_group_admin, user_link
from phpelefant.services.activity import mark_joined
from phpelefant.services.moderation import log_action
from phpelefant.services.settings import get_or_create_chat_settings, upsert_user
from phpelefant.utils.text import html_escape
from phpelefant.utils.telegram import telegram_call

router = Router(name="welcome")


async def _render_template(template: str, message: Message, user_id: int, username: str | None, bot: Bot, rules: str) -> str:
    member_count = await bot.get_chat_member_count(message.chat.id)
    return template.format(
        user=user_link(user_id, username or str(user_id)),
        username=html_escape(username or ""),
        group=html_escape(message.chat.title or str(message.chat.id)),
        member_count=member_count,
        rules=html_escape(rules),
    )


@router.message(Command("setwelcome"))
async def setwelcome(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    text = command_args(command)
    if len(text) < 3:
        await message.answer("Use /setwelcome <message>. Placeholders: {user}, {username}, {group}, {member_count}, {rules}.")
        return
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    row.welcome_text = text[:4000]
    await log_action(session, message.chat.id, "setwelcome", None, message.from_user.id, None)
    await message.answer("Welcome message updated.")


@router.message(Command("welcome"))
async def welcome_toggle(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    value = command_args(command).casefold()
    if value not in {"on", "off"}:
        await message.answer("Use /welcome on or /welcome off.")
        return
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    row.welcome_enabled = value == "on"
    await message.answer(f"Welcome set to <code>{row.welcome_enabled}</code>.")


@router.message(Command("setgoodbye"))
async def setgoodbye(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    text = command_args(command)
    if len(text) < 3:
        await message.answer("Use /setgoodbye <message>.")
        return
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    row.goodbye_text = text[:4000]
    await message.answer("Goodbye message updated.")


@router.message(Command("goodbye"))
async def goodbye_toggle(message: Message, command: CommandObject, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    if not await ensure_group_admin(message, bot, settings):
        return
    value = command_args(command).casefold()
    if value not in {"on", "off"}:
        await message.answer("Use /goodbye on or /goodbye off.")
        return
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    row.goodbye_enabled = value == "on"
    await message.answer(f"Goodbye set to <code>{row.goodbye_enabled}</code>.")


@router.message(F.new_chat_members)
async def new_members(message: Message, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    for member in message.new_chat_members or []:
        await upsert_user(session, member)
        await mark_joined(session, message.chat.id, member.id)
        if row.welcome_enabled:
            rendered = await _render_template(row.welcome_text, message, member.id, member.username, bot, row.rules_text)
            if row.rules_text and "{rules}" not in row.welcome_text:
                rendered += f"\n\n<b>Rules</b>\n{html_escape(row.rules_text)}"
            await message.answer(rendered)
    if row.delete_service_messages:
        await telegram_call(lambda: message.delete())


@router.message(F.left_chat_member)
async def left_member(message: Message, bot: Bot, session: AsyncSession, settings: Settings) -> None:
    row = await get_or_create_chat_settings(session, message.chat.id, settings)
    member = message.left_chat_member
    if member and row.goodbye_enabled:
        rendered = await _render_template(row.goodbye_text, message, member.id, member.username, bot, row.rules_text)
        await message.answer(rendered)
    if row.delete_service_messages:
        await telegram_call(lambda: message.delete())

