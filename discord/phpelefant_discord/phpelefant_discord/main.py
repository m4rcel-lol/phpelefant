from __future__ import annotations

import asyncio
import logging

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.config import get_settings
from phpelefant_discord.logging_config import configure_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    bot = PHPelefantBot(settings)
    async with bot:
        logger.info("Starting PHPelefant Discord bot")
        await bot.start(settings.token)


if __name__ == "__main__":
    asyncio.run(main())

