from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from phpelefant_discord.config import Settings
from phpelefant_discord.db.session import init_database, make_engine, make_session_factory
from phpelefant_discord.utils.formatting import PHPelefantContext, decorate_embed, error_embed, infer_status
from phpelefant_discord.utils.slash_descriptions import apply_slash_descriptions

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
        self.tree.on_error = self.on_app_command_error

    async def setup_hook(self) -> None:
        await init_database(self.engine)
        for extension in (
            "phpelefant_discord.cogs.owner",
            "phpelefant_discord.cogs.utility",
            "phpelefant_discord.cogs.moderation",
            "phpelefant_discord.cogs.channel_edit",
            "phpelefant_discord.cogs.tickets",
            "phpelefant_discord.cogs.settings",
            "phpelefant_discord.cogs.welcome",
            "phpelefant_discord.cogs.activity",
            "phpelefant_discord.cogs.fun",
            "phpelefant_discord.cogs.events",
        ):
            await self.load_extension(extension)
        apply_slash_descriptions(self.tree)
        try:
            synced = await self.tree.sync()
            logger.info("Synced %s application commands", len(synced))
        except discord.HTTPException:
            logger.exception("Failed to sync application commands")

    async def close(self) -> None:
        await super().close()
        await self.engine.dispose()

    async def get_context(self, origin, /, *, cls=PHPelefantContext):
        return await super().get_context(origin, cls=cls)

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        original = getattr(error, "original", error)
        message = "PHPelefant could not run that command."
        if isinstance(original, app_commands.MissingPermissions):
            message = "You do not have the required Discord permissions."
        elif isinstance(original, app_commands.BotMissingPermissions):
            message = "PHPelefant is missing required Discord permissions."
        elif isinstance(original, app_commands.CheckFailure):
            message = "You are not allowed to use that command."
        elif isinstance(original, discord.Forbidden):
            message = "Discord rejected this because PHPelefant lacks permission or role position."
        elif isinstance(original, discord.HTTPException):
            message = "Discord rejected the request. Try again after checking permissions and arguments."
        else:
            logger.error(
                "Unhandled app command error in %s",
                interaction.command,
                exc_info=(type(original), original, original.__traceback__) if isinstance(original, BaseException) else None,
            )
        item = error_embed("Command Error", message)
        decorate_embed(item, None, status=infer_status(item))
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=item, ephemeral=True)
            else:
                await interaction.response.send_message(embed=item, ephemeral=True)
        except discord.DiscordException:
            logger.exception("Failed to send app command error response")
