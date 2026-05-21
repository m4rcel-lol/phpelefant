from __future__ import annotations

import discord
from discord.ext import commands

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.db.session import session_scope
from phpelefant_discord.services.settings import get_or_create_guild_settings
from phpelefant_discord.utils.formatting import embed, success_embed, table_embed
from phpelefant_discord.utils.permissions import owner_or_guild_permissions


class Welcome(commands.Cog):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="setwelcome")
    @commands.guild_only()
    @owner_or_guild_permissions(manage_guild=True)
    async def setwelcome(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
        dm_user: bool = False,
        *,
        message: str,
    ) -> None:
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
            settings.welcome_text = message[:4000]
            settings.welcome_dm_enabled = dm_user
            if channel is not None:
                settings.welcome_channel_id = channel.id
            current_channel_id = settings.welcome_channel_id
            current_dm = settings.welcome_dm_enabled
        preview = self.build_welcome_embed(ctx.author, message[:4000], ctx.guild.name, ctx.guild.member_count)
        preview.add_field(name="Channel", value=f"<#{current_channel_id}>" if current_channel_id else "Server system channel", inline=True)
        preview.add_field(name="DM New Member", value="Enabled" if current_dm else "Disabled", inline=True)
        await ctx.send(embed=preview)

    @commands.hybrid_command(name="welcome")
    @commands.guild_only()
    @owner_or_guild_permissions(manage_guild=True)
    async def welcome(self, ctx: commands.Context, value: str | None = None) -> None:
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
            if value is not None:
                if value.casefold() not in {"on", "off"}:
                    await ctx.send(embed=table_embed("Welcome", [("usage", "welcome on, welcome off, or welcome")], status="warning"))
                    return
                settings.welcome_enabled = value.casefold() == "on"
            current = {
                "enabled": settings.welcome_enabled,
                "message": settings.welcome_text,
                "channel_id": settings.welcome_channel_id,
                "dm": settings.welcome_dm_enabled,
            }
        preview = self.build_welcome_embed(ctx.author, current["message"], ctx.guild.name, ctx.guild.member_count)
        preview.add_field(name="Enabled", value="Enabled" if current["enabled"] else "Disabled", inline=True)
        preview.add_field(name="Channel", value=f"<#{current['channel_id']}>" if current["channel_id"] else "Server system channel", inline=True)
        preview.add_field(name="DM New Member", value="Enabled" if current["dm"] else "Disabled", inline=True)
        await ctx.send(embed=preview)

    @commands.hybrid_command(name="setgoodbye")
    @commands.guild_only()
    @owner_or_guild_permissions(manage_guild=True)
    async def setgoodbye(self, ctx: commands.Context, *, text: str) -> None:
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
            settings.goodbye_text = text[:4000]
        await ctx.send(embed=success_embed("Goodbye", "Goodbye message updated."))

    @commands.hybrid_command(name="goodbye")
    @commands.guild_only()
    @owner_or_guild_permissions(manage_guild=True)
    async def goodbye(self, ctx: commands.Context, value: str) -> None:
        enabled = value.casefold() == "on"
        if value.casefold() not in {"on", "off"}:
            await ctx.send(embed=table_embed("Goodbye", [("usage", "goodbye on or goodbye off")], status="warning"))
            return
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
            settings.goodbye_enabled = enabled
        await ctx.send(embed=success_embed("Goodbye", f"Goodbye set to {enabled}."))

    @staticmethod
    def build_welcome_embed(
        member: discord.User | discord.Member,
        template: str,
        guild_name: str,
        member_count: int | None,
    ) -> discord.Embed:
        try:
            rendered = template.format(
                user=member.mention,
                username=str(member),
                group=guild_name,
                server=guild_name,
                member_count=member_count or 0,
                rules="{rules}",
            )
        except (KeyError, ValueError):
            rendered = template
        item = embed("Welcome", rendered, status="success")
        try:
            item.set_thumbnail(url=member.display_avatar.url)
        except AttributeError:
            pass
        item.add_field(name="Placeholders", value="`{user}` `{username}` `{group}` `{server}` `{member_count}` `{rules}`", inline=False)
        return item


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(Welcome(bot))
