from __future__ import annotations

from aiogram.types import Chat as TgChat, User as TgUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant.config import Settings
from phpelefant.db.models import Chat, ChatSettings, User


async def upsert_user(session: AsyncSession, user: TgUser | None) -> None:
    if user is None:
        return
    existing = await session.get(User, user.id)
    if existing is None:
        session.add(
            User(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                is_bot=user.is_bot,
            )
        )
        return
    existing.username = user.username
    existing.first_name = user.first_name
    existing.last_name = user.last_name
    existing.is_bot = user.is_bot


async def upsert_chat(session: AsyncSession, chat: TgChat, settings: Settings) -> None:
    existing = await session.get(Chat, chat.id)
    if existing is None:
        session.add(Chat(chat_id=chat.id, type=chat.type, title=chat.title, username=chat.username))
        await session.flush()
        if chat.type in {"group", "supergroup"}:
            session.add(
                ChatSettings(
                    chat_id=chat.id,
                    official_channel_id=settings.official_channel_id,
                    language=settings.default_language,
                    timezone=settings.default_timezone,
                    delete_service_messages=settings.delete_service_messages,
                )
            )
        return
    existing.type = chat.type
    existing.title = chat.title
    existing.username = chat.username


async def get_or_create_chat_settings(session: AsyncSession, chat_id: int, settings: Settings) -> ChatSettings:
    row = await session.get(ChatSettings, chat_id)
    if row is not None:
        return row
    row = ChatSettings(
        chat_id=chat_id,
        official_channel_id=settings.official_channel_id,
        language=settings.default_language,
        timezone=settings.default_timezone,
        delete_service_messages=settings.delete_service_messages,
    )
    session.add(row)
    await session.flush()
    return row


async def known_chat_ids(session: AsyncSession) -> list[int]:
    result = await session.scalars(select(Chat.chat_id))
    return list(result)


async def known_user_ids(session: AsyncSession) -> list[int]:
    result = await session.scalars(select(User.telegram_id))
    return list(result)

