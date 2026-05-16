from __future__ import annotations

from datetime import UTC, datetime

import discord
from discord.ext import commands

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.db.session import session_scope
from phpelefant_discord.services.moderation import add_warning, log_action, reset_warnings, warning_count
from phpelefant_discord.services.settings import get_or_create_guild_settings
from phpelefant_discord.utils.formatting import code_embed, table_embed
from phpelefant_discord.utils.time import parse_duration


def is_owner_id(bot: PHPelefantBot, user_id: int) -> bool:
    return user_id == bot.settings.bot_owner_id


def can_moderate(ctx: commands.Context, member: discord.Member) -> tuple[bool, str]:
    if member.id == ctx.bot.settings.bot_owner_id:
        return False, "Cannot moderate the bot owner."
    if member.id == ctx.author.id:
        return False, "Cannot moderate yourself."
    if is_owner_id(ctx.bot, ctx.author.id):
        return True, ""
    if not isinstance(ctx.author, discord.Member) or not ctx.author.guild_permissions.moderate_members:
        return False, "Missing moderation permissions."
    if member.guild_permissions.administrator or member.top_role >= ctx.author.top_role:
        return False, "You cannot moderate this member."
    return True, ""


class Moderation(commands.Cog):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="ban")
    @commands.guild_only()
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        ok, message = can_moderate(ctx, member)
        if not ok:
            await ctx.send(embed=code_embed("Moderation", message))
            return
        await member.ban(reason=reason)
        async with session_scope(self.bot.session_factory) as session:
            await log_action(session, ctx.guild.id, "ban", member.id, ctx.author.id, reason)
        await ctx.send(embed=table_embed("Ban", [("user", member.id), ("reason", reason)]))

    @commands.hybrid_command(name="unban")
    @commands.guild_only()
    @commands.has_guild_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, user_id: int, *, reason: str = "No reason provided") -> None:
        user = discord.Object(id=user_id)
        await ctx.guild.unban(user, reason=reason)
        async with session_scope(self.bot.session_factory) as session:
            await log_action(session, ctx.guild.id, "unban", user_id, ctx.author.id, reason)
        await ctx.send(embed=table_embed("Unban", [("user", user_id)]))

    @commands.hybrid_command(name="kick")
    @commands.guild_only()
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        ok, message = can_moderate(ctx, member)
        if not ok:
            await ctx.send(embed=code_embed("Moderation", message))
            return
        await member.kick(reason=reason)
        async with session_scope(self.bot.session_factory) as session:
            await log_action(session, ctx.guild.id, "kick", member.id, ctx.author.id, reason)
        await ctx.send(embed=table_embed("Kick", [("user", member.id), ("reason", reason)]))

    @commands.hybrid_command(name="mute", aliases=["timeout"])
    @commands.guild_only()
    async def mute(self, ctx: commands.Context, member: discord.Member, duration: str = "1h", *, reason: str = "No reason provided") -> None:
        ok, message = can_moderate(ctx, member)
        if not ok:
            await ctx.send(embed=code_embed("Moderation", message))
            return
        try:
            delta = parse_duration(duration)
        except ValueError as exc:
            await ctx.send(embed=code_embed("Moderation", str(exc)))
            return
        until = datetime.now(tz=UTC) + delta
        await member.timeout(until, reason=reason)
        async with session_scope(self.bot.session_factory) as session:
            await log_action(session, ctx.guild.id, "timeout", member.id, ctx.author.id, reason, {"duration": duration})
        await ctx.send(embed=table_embed("Timeout", [("user", member.id), ("duration", duration), ("reason", reason)]))

    @commands.hybrid_command(name="unmute", aliases=["untimeout"])
    @commands.guild_only()
    @commands.has_guild_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        await member.timeout(None, reason=reason)
        async with session_scope(self.bot.session_factory) as session:
            await log_action(session, ctx.guild.id, "untimeout", member.id, ctx.author.id, reason)
        await ctx.send(embed=table_embed("Untimeout", [("user", member.id)]))

    @commands.hybrid_command(name="warn")
    @commands.guild_only()
    @commands.has_guild_permissions(moderate_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
            count, auto = await add_warning(session, settings, member, ctx.author.id, reason)
        await ctx.send(embed=table_embed("Warn", [("user", member.id), ("warnings", f"{count}/{settings.warning_limit}"), ("auto", auto or "none")]))

    @commands.hybrid_command(name="warnings")
    @commands.guild_only()
    async def warnings(self, ctx: commands.Context, member: discord.Member) -> None:
        async with session_scope(self.bot.session_factory) as session:
            count = await warning_count(session, ctx.guild.id, member.id)
        await ctx.send(embed=table_embed("Warnings", [("user", member.id), ("active warnings", count)]))

    @commands.hybrid_command(name="resetwarnings")
    @commands.guild_only()
    @commands.has_guild_permissions(moderate_members=True)
    async def resetwarnings(self, ctx: commands.Context, member: discord.Member) -> None:
        async with session_scope(self.bot.session_factory) as session:
            count = await reset_warnings(session, ctx.guild.id, member.id, ctx.author.id)
        await ctx.send(embed=table_embed("Reset warnings", [("user", member.id), ("reset", count)]))

    @commands.hybrid_command(name="purge")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, limit: int) -> None:
        if not 1 <= limit <= 100:
            await ctx.send(embed=code_embed("Purge", "Limit must be 1-100."))
            return
        deleted = await ctx.channel.purge(limit=limit + 1)
        async with session_scope(self.bot.session_factory) as session:
            await log_action(session, ctx.guild.id, "purge", None, ctx.author.id, str(len(deleted)))
        await ctx.send(embed=code_embed("Purge", f"Purged {len(deleted) - 1} messages."), delete_after=8)

    @commands.hybrid_command(name="delete")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def delete(self, ctx: commands.Context, message_id: int) -> None:
        message = await ctx.channel.fetch_message(message_id)
        await message.delete()
        await ctx.message.delete()

    @commands.hybrid_command(name="lock")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context) -> None:
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(embed=code_embed("Lock", "Channel locked."))

    @commands.hybrid_command(name="unlock")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context) -> None:
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(embed=code_embed("Unlock", "Channel unlocked."))

    @commands.hybrid_command(name="slowmode")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, seconds: int) -> None:
        if not 0 <= seconds <= 21600:
            await ctx.send(embed=code_embed("Slowmode", "Slowmode must be between 0 and 21600 seconds."))
            return
        await ctx.channel.edit(slowmode_delay=seconds)
        await ctx.send(embed=code_embed("Slowmode", f"Slowmode set to {seconds}s."))

    @commands.hybrid_command(name="rules")
    @commands.guild_only()
    async def rules(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
        await ctx.send(embed=discord.Embed(title="Rules", description=settings.rules_text))

    @commands.hybrid_command(name="setrules")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def setrules(self, ctx: commands.Context, *, text: str) -> None:
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
            settings.rules_text = text[:4000]
            await log_action(session, ctx.guild.id, "setrules", None, ctx.author.id, None)
        await ctx.send(embed=code_embed("Rules", "Rules updated."))

    @commands.hybrid_command(name="pin")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def pin(self, ctx: commands.Context, message_id: int) -> None:
        message = await ctx.channel.fetch_message(message_id)
        await message.pin(reason=f"Pinned by {ctx.author}")
        await ctx.send(embed=code_embed("Pin", "Message pinned."))

    @commands.hybrid_command(name="unpin")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def unpin(self, ctx: commands.Context, message_id: int) -> None:
        message = await ctx.channel.fetch_message(message_id)
        await message.unpin(reason=f"Unpinned by {ctx.author}")
        await ctx.send(embed=code_embed("Unpin", "Message unpinned."))

    @commands.hybrid_command(name="report")
    @commands.guild_only()
    async def report(self, ctx: commands.Context, message_id: int, *, reason: str = "No reason provided") -> None:
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
        channel = ctx.guild.get_channel(settings.log_channel_id) if settings.log_channel_id else None
        if isinstance(channel, discord.TextChannel):
            await channel.send(embed=table_embed("Report", [("reporter", ctx.author.id), ("message", message_id), ("reason", reason)]))
        await ctx.send(embed=code_embed("Report", "Report submitted." if channel else "Report received; configure setlogchannel for admin logs."))

    @commands.hybrid_command(name="adminlist")
    @commands.guild_only()
    async def adminlist(self, ctx: commands.Context) -> None:
        admins = [member for member in ctx.guild.members if member.guild_permissions.administrator]
        await ctx.send(embed=code_embed("Admins", "\n".join(f"{m} ({m.id})" for m in admins) or "No cached admins."))


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(Moderation(bot))
