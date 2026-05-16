from __future__ import annotations

from discord.ext import commands

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.db.session import session_scope
from phpelefant_discord.services.settings import get_or_create_guild_settings
from phpelefant_discord.utils.formatting import code_embed


class Welcome(commands.Cog):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="setwelcome")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def setwelcome(self, ctx: commands.Context, *, text: str) -> None:
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
            settings.welcome_text = text[:4000]
        await ctx.send(embed=code_embed("Welcome", "Welcome message updated."))

    @commands.hybrid_command(name="welcome")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def welcome(self, ctx: commands.Context, value: str) -> None:
        enabled = value.casefold() == "on"
        if value.casefold() not in {"on", "off"}:
            await ctx.send(embed=code_embed("Welcome", "Use welcome on or welcome off."))
            return
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
            settings.welcome_enabled = enabled
        await ctx.send(embed=code_embed("Welcome", f"Welcome set to {enabled}."))

    @commands.hybrid_command(name="setgoodbye")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def setgoodbye(self, ctx: commands.Context, *, text: str) -> None:
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
            settings.goodbye_text = text[:4000]
        await ctx.send(embed=code_embed("Goodbye", "Goodbye message updated."))

    @commands.hybrid_command(name="goodbye")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def goodbye(self, ctx: commands.Context, value: str) -> None:
        enabled = value.casefold() == "on"
        if value.casefold() not in {"on", "off"}:
            await ctx.send(embed=code_embed("Goodbye", "Use goodbye on or goodbye off."))
            return
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
            settings.goodbye_enabled = enabled
        await ctx.send(embed=code_embed("Goodbye", f"Goodbye set to {enabled}."))


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(Welcome(bot))
