from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from aiogram import Bot
from aiogram.filters import CommandObject
from aiogram.types import Message

from phpelefant.config import Settings
from phpelefant.services.permissions import can_moderate_target, require_admin_or_owner
from phpelefant.utils.text import html_escape
from phpelefant.utils.time import parse_duration


class CommandError(ValueError):
    pass


@dataclass(slots=True)
class TargetAndReason:
    target_id: int
    reason: str


@dataclass(slots=True)
class MuteArgs:
    target_id: int
    duration_text: str | None
    reason: str


def fail(message: str) -> NoReturn:
    raise CommandError(message)


def command_args(command: CommandObject) -> str:
    return (command.args or "").strip()


def parse_user_id(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        fail("Use a numeric Telegram user ID or reply to the target user's message.")


def parse_target_and_reason(message: Message, command: CommandObject) -> TargetAndReason:
    args = command_args(command)
    if message.reply_to_message and message.reply_to_message.from_user:
        return TargetAndReason(message.reply_to_message.from_user.id, args or "No reason provided")
    parts = args.split(maxsplit=1)
    if not parts:
        fail("Reply to a user or pass a numeric user ID.")
    return TargetAndReason(parse_user_id(parts[0]), parts[1] if len(parts) > 1 else "No reason provided")


def parse_mute_args(message: Message, command: CommandObject) -> MuteArgs:
    args = command_args(command)
    parts = args.split(maxsplit=2)
    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        if parts:
            try:
                parse_duration(parts[0])
                duration = parts[0]
                reason = parts[1] if len(parts) > 1 else "No reason provided"
            except ValueError:
                duration = None
                reason = args or "No reason provided"
        else:
            duration = None
            reason = "No reason provided"
        return MuteArgs(target_id, duration, reason)
    if not parts:
        fail("Reply to a user or use /mute <user_id> [10m|1h|1d|7d] [reason].")
    target_id = parse_user_id(parts[0])
    duration = None
    reason = "No reason provided"
    if len(parts) >= 2:
        try:
            parse_duration(parts[1])
            duration = parts[1]
            reason = parts[2] if len(parts) > 2 else "No reason provided"
        except ValueError:
            reason = " ".join(parts[1:])
    return MuteArgs(target_id, duration, reason)


async def ensure_group_admin(message: Message, bot: Bot, settings: Settings) -> bool:
    if message.chat.type not in {"group", "supergroup"} or message.from_user is None:
        await message.answer("This command is only available in groups.")
        return False
    if not await require_admin_or_owner(bot, message.chat.id, message.from_user.id, settings.bot_owner_id):
        await message.answer("This command is only available to group admins.")
        return False
    return True


async def ensure_can_moderate(message: Message, bot: Bot, settings: Settings, target_id: int) -> bool:
    if message.from_user is None:
        return False
    allowed, reason = await can_moderate_target(bot, message.chat.id, message.from_user.id, target_id, settings.bot_owner_id)
    if not allowed:
        await message.answer(reason or "You cannot moderate that user.")
        return False
    return True


def user_link(user_id: int, label: str | None = None) -> str:
    safe_label = html_escape(label or str(user_id))
    return f'<a href="tg://user?id={user_id}">{safe_label}</a>'

