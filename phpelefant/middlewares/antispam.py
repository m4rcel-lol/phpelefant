from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from aiogram import Bot
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant.config import Settings
from phpelefant.services.antispam import AutoAction, SpamMemory, analyze_message, bad_words, is_whitelisted, whitelisted_domains
from phpelefant.services.moderation import add_warning, ban_user, log_action, mute_user
from phpelefant.services.permissions import is_chat_admin, is_owner
from phpelefant.services.settings import get_or_create_chat_settings
from phpelefant.utils.telegram import telegram_call


class AntiSpamMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._memory = SpamMemory()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or event.chat.type not in {"group", "supergroup"} or event.from_user is None:
            return await handler(event, data)
        text = event.text or event.caption or ""
        if not text or text.startswith("/"):
            return await handler(event, data)

        bot: Bot = data["bot"]
        session: AsyncSession = data["session"]
        user_id = event.from_user.id
        if is_owner(user_id, self._settings.bot_owner_id) or await is_chat_admin(bot, event.chat.id, user_id):
            return await handler(event, data)
        if await is_whitelisted(session, event.chat.id, user_id):
            return await handler(event, data)

        settings = await get_or_create_chat_settings(session, event.chat.id, self._settings)
        now = datetime.now(tz=UTC)
        flood_count, repeat_count = self._memory.update(event.chat.id, user_id, text, now, settings.flood_window_seconds)
        decision = analyze_message(
            text=text,
            settings=settings,
            bad_word_list=await bad_words(session, event.chat.id),
            trusted_domains=await whitelisted_domains(session, event.chat.id),
            flood_count=flood_count,
            repeat_count=repeat_count,
            forwarded=getattr(event, "forward_origin", None) is not None,
        )
        if decision.action is AutoAction.NONE:
            return await handler(event, data)

        await telegram_call(lambda: event.delete(), "Could not delete violating message.")
        await log_action(session, event.chat.id, f"auto_{decision.action.value}", user_id, None, decision.reason)
        if decision.action is AutoAction.WARN:
            count, auto = await add_warning(bot, session, settings, event.chat.id, user_id, self._settings.bot_owner_id, f"Auto moderation: {decision.reason}")
            notice = f"Auto-warning issued to `{user_id}` for {decision.reason}. Warnings: {count}/{settings.warning_limit}"
            if auto:
                notice += f"\n{auto}"
            await event.answer(notice)
        elif decision.action is AutoAction.MUTE:
            ok, message = await mute_user(bot, session, event.chat.id, user_id, None, f"Auto moderation: {decision.reason}", timedelta(hours=1))
            if ok:
                await event.answer(message)
        elif decision.action is AutoAction.BAN:
            ok, message = await ban_user(bot, session, event.chat.id, user_id, None, f"Auto moderation: {decision.reason}")
            if ok:
                await event.answer(message)
        return None

