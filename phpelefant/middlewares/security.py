from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant.config import Settings
from phpelefant.db.models import BlacklistedChat, BlacklistedUser
from phpelefant.services.permissions import is_chat_admin, is_owner
from phpelefant.services.settings import get_or_create_chat_settings

FORCE_SUB_COMMANDS = {
    "joke",
    "meme",
    "quote",
    "fact",
    "8ball",
    "coinflip",
    "dice",
    "roll",
    "ship",
    "roast",
    "compliment",
    "hug",
    "slap",
    "cat",
    "dog",
    "rank",
    "level",
    "xp",
    "leaderboard",
    "top",
    "activity",
    "profile",
}


class SecurityMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)
        session: AsyncSession = data["session"]
        bot: Bot = data["bot"]
        user_id = event.from_user.id if event.from_user else None
        if user_id is not None and not is_owner(user_id, self._settings.bot_owner_id):
            if await session.get(BlacklistedUser, user_id) is not None:
                if event.chat.type == "private":
                    await event.answer("You are blocked from using PHPelefant.")
                return None
        if event.chat.type in {"group", "supergroup"} and await session.get(BlacklistedChat, event.chat.id) is not None:
            return None
        if event.chat.type in {"group", "supergroup"} and user_id is not None and event.text:
            command = event.text.split(maxsplit=1)[0].removeprefix("/").split("@", 1)[0].lower()
            if command in FORCE_SUB_COMMANDS:
                settings = await get_or_create_chat_settings(session, event.chat.id, self._settings)
                if settings.force_subscribe_enabled and not is_owner(user_id, self._settings.bot_owner_id):
                    if await is_chat_admin(bot, event.chat.id, user_id):
                        return await handler(event, data)
                    try:
                        member = await bot.get_chat_member(settings.official_channel_id, user_id)
                    except TelegramAPIError:
                        await event.answer("Force-subscribe is enabled, but I cannot verify the official channel membership.")
                        return None
                    if member.status in {"left", "kicked"}:
                        await event.answer("Join the official PHPelefant channel before using this command.")
                        return None
        return await handler(event, data)

