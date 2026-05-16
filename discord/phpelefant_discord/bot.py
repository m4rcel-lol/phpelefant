from __future__ import annotations

import logging

import discord
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from phpelefant_discord.config import Settings
from phpelefant_discord.db.session import init_database, make_engine, make_session_factory

logger = logging.getLogger(__name__)


class PHPelefantBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True
        super().__init__(
            command_prefix=commands.when_mentioned_or(settings.command_prefix),
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )
        self.settings = settings
        self.engine: AsyncEngine = make_engine(settings.database_url)
        self.session_factory: async_sessionmaker[AsyncSession] = make_session_factory(self.engine)

    async def setup_hook(self) -> None:
        await init_database(self.engine)
        for extension in (
            "phpelefant_discord.cogs.owner",
            "phpelefant_discord.cogs.utility",
            "phpelefant_discord.cogs.moderation",
            "phpelefant_discord.cogs.settings",
            "phpelefant_discord.cogs.welcome",
            "phpelefant_discord.cogs.activity",
            "phpelefant_discord.cogs.fun",
            "phpelefant_discord.cogs.events",
        ):
            await self.load_extension(extension)
        try:
            synced = await self.tree.sync()
            logger.info("Synced %s application commands", len(synced))
        except discord.HTTPException:
            logger.exception("Failed to sync application commands")

    async def close(self) -> None:
        await super().close()
        await self.engine.dispose()
