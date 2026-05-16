from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, ErrorEvent

from phpelefant.config import Settings, get_settings
from phpelefant.db.session import make_engine, make_session_factory
from phpelefant.logging_config import configure_logging
from phpelefant.middlewares.antispam import AntiSpamMiddleware
from phpelefant.middlewares.database import DatabaseSessionMiddleware
from phpelefant.middlewares.rate_limit import RateLimitMiddleware
from phpelefant.middlewares.security import SecurityMiddleware
from phpelefant.routers import build_router

logger = logging.getLogger(__name__)


async def set_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Start PHPelefant"),
        BotCommand(command="help", description="Show command list"),
        BotCommand(command="about", description="About PHPelefant"),
        BotCommand(command="settings", description="Show group settings"),
        BotCommand(command="rules", description="Show group rules"),
        BotCommand(command="report", description="Report a replied message"),
        BotCommand(command="rank", description="Show your rank"),
        BotCommand(command="leaderboard", description="Show top members"),
        BotCommand(command="profile", description="Show member profile"),
        BotCommand(command="joke", description="Safe community joke"),
        BotCommand(command="ping", description="Check bot latency"),
        BotCommand(command="owner", description="Owner control panel"),
    ]
    await bot.set_my_commands(commands)


def build_dispatcher(settings: Settings) -> Dispatcher:
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    dp = Dispatcher(settings=settings)
    dp["engine"] = engine
    dp["session_factory"] = session_factory
    dp.message.middleware(DatabaseSessionMiddleware(session_factory, settings))
    dp.message.middleware(SecurityMiddleware(settings))
    dp.message.middleware(RateLimitMiddleware())
    dp.message.middleware(AntiSpamMiddleware(settings))
    dp.include_router(build_router())

    @dp.errors()
    async def handle_error(event: ErrorEvent) -> bool:
        logger.exception("Unhandled update error: %s", event.exception)
        return True

    return dp


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    bot = Bot(settings.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher(settings)
    await set_commands(bot)
    logger.info("PHPelefant started")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        engine = dp["engine"]
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

