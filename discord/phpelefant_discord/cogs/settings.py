from __future__ import annotations

import discord
from discord.ext import commands
from sqlalchemy import delete, select

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.db.models import BadWord, WhitelistedDomain, WhitelistedUser
from phpelefant_discord.db.session import session_scope
from phpelefant_discord.services.moderation import log_action
from phpelefant_discord.services.settings import get_or_create_guild_settings
from phpelefant_discord.utils.formatting import code_block, table_embed


def bool_from_on_off(value: str) -> bool | None:
    normalized = value.casefold()
    if normalized == "on":
        return True
    if normalized == "off":
        return False
    return None


class SettingsCog(commands.Cog, name="Settings"):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot

    async def set_bool(self, ctx: commands.Context, attr: str, value: str, label: str) -> None:
        enabled = bool_from_on_off(value)
        if enabled is None:
            await ctx.send(code_block(f"Use {label} on or {label} off."))
            return
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
            setattr(settings, attr, enabled)
            await log_action(session, ctx.guild.id, label, None, ctx.author.id, str(enabled))
        await ctx.send(code_block(f"{label} set to {enabled}."))

    @commands.hybrid_command(name="setlogchannel")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def setlogchannel(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
            settings.log_channel_id = channel.id if channel else None
        await ctx.send(code_block(f"Log channel set to {channel.mention if channel else 'off'}."))

    @commands.hybrid_command(name="setwarnlimit")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def setwarnlimit(self, ctx: commands.Context, limit: int) -> None:
        if not 1 <= limit <= 20:
            await ctx.send(code_block("Warning limit must be 1-20."))
            return
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
            settings.warning_limit = limit
        await ctx.send(code_block(f"Warning limit set to {limit}."))

    @commands.hybrid_command(name="antispam")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def antispam(self, ctx: commands.Context, value: str) -> None:
        await self.set_bool(ctx, "anti_spam_enabled", value, "antispam")

    @commands.hybrid_command(name="antilink")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def antilink(self, ctx: commands.Context, value: str) -> None:
        await self.set_bool(ctx, "anti_link_enabled", value, "antilink")

    @commands.hybrid_command(name="anticaps")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def anticaps(self, ctx: commands.Context, value: str) -> None:
        await self.set_bool(ctx, "anti_caps_enabled", value, "anticaps")

    @commands.hybrid_command(name="forcesub")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def forcesub(self, ctx: commands.Context, value: str) -> None:
        await self.set_bool(ctx, "force_subscribe_enabled", value, "forcesub")

    @commands.hybrid_command(name="forcesubstatus")
    @commands.guild_only()
    async def forcesubstatus(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
        await ctx.send(embed=table_embed("Force subscribe", [("enabled", settings.force_subscribe_enabled), ("channel", settings.official_channel_id or "not set")]))

    @commands.hybrid_group(name="badwords", fallback="list")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def badwords(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            result = await session.scalars(select(BadWord.word).where(BadWord.guild_id == ctx.guild.id).order_by(BadWord.word))
            words = list(result)
        await ctx.send(code_block(", ".join(words) if words else "No bad words configured."))

    @badwords.command(name="add")
    async def badwords_add(self, ctx: commands.Context, *, word: str) -> None:
        async with session_scope(self.bot.session_factory) as session:
            exists = await session.scalar(select(BadWord).where(BadWord.guild_id == ctx.guild.id, BadWord.word == word.casefold()))
            if exists is None:
                session.add(BadWord(guild_id=ctx.guild.id, word=word.casefold()[:255]))
        await ctx.send(code_block("Bad word added."))

    @badwords.command(name="remove")
    async def badwords_remove(self, ctx: commands.Context, *, word: str) -> None:
        async with session_scope(self.bot.session_factory) as session:
            await session.execute(delete(BadWord).where(BadWord.guild_id == ctx.guild.id, BadWord.word == word.casefold()))
        await ctx.send(code_block("Bad word removed if present."))

    @commands.hybrid_group(name="whitelist", fallback="list")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def whitelist(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            users = await session.scalars(select(WhitelistedUser.user_id).where(WhitelistedUser.guild_id == ctx.guild.id))
            domains = await session.scalars(select(WhitelistedDomain.domain).where(WhitelistedDomain.guild_id == ctx.guild.id))
            body = f"users: {', '.join(str(u) for u in users) or 'none'}\ndomains: {', '.join(domains) or 'none'}"
        await ctx.send(code_block(body))

    @whitelist.command(name="add")
    async def whitelist_add(self, ctx: commands.Context, member: discord.Member, *, reason: str = "trusted") -> None:
        async with session_scope(self.bot.session_factory) as session:
            exists = await session.scalar(select(WhitelistedUser).where(WhitelistedUser.guild_id == ctx.guild.id, WhitelistedUser.user_id == member.id))
            if exists is None:
                session.add(WhitelistedUser(guild_id=ctx.guild.id, user_id=member.id, reason=reason))
        await ctx.send(code_block(f"Whitelisted {member.id}."))

    @whitelist.command(name="remove")
    async def whitelist_remove(self, ctx: commands.Context, member: discord.Member) -> None:
        async with session_scope(self.bot.session_factory) as session:
            await session.execute(delete(WhitelistedUser).where(WhitelistedUser.guild_id == ctx.guild.id, WhitelistedUser.user_id == member.id))
        await ctx.send(code_block(f"Removed {member.id} if present."))

    @whitelist.command(name="domain")
    async def whitelist_domain(self, ctx: commands.Context, domain: str) -> None:
        domain = domain.casefold().removeprefix("www.")[:255]
        async with session_scope(self.bot.session_factory) as session:
            exists = await session.scalar(select(WhitelistedDomain).where(WhitelistedDomain.guild_id == ctx.guild.id, WhitelistedDomain.domain == domain))
            if exists is None:
                session.add(WhitelistedDomain(guild_id=ctx.guild.id, domain=domain))
        await ctx.send(code_block(f"Whitelisted domain {domain}."))


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(SettingsCog(bot))

