from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

ADMIN_STATUSES = {"creator", "administrator"}


def is_owner(user_id: int | None, owner_id: int) -> bool:
    return user_id == owner_id


async def is_chat_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    except TelegramAPIError:
        return False
    return member.status in ADMIN_STATUSES


async def require_admin_or_owner(bot: Bot, chat_id: int, user_id: int, owner_id: int) -> bool:
    if is_owner(user_id, owner_id):
        return True
    return await is_chat_admin(bot, chat_id, user_id)


async def can_moderate_target(bot: Bot, chat_id: int, actor_id: int, target_id: int, owner_id: int) -> tuple[bool, str | None]:
    if target_id == owner_id:
        return False, "The bot owner cannot be moderated."
    if actor_id == target_id:
        return False, "You cannot moderate yourself."
    if is_owner(actor_id, owner_id):
        return True, None
    if not await is_chat_admin(bot, chat_id, actor_id):
        return False, "This command is only available to group admins."
    if await is_chat_admin(bot, chat_id, target_id):
        return False, "Admins cannot moderate other admins with this bot."
    return True, None

