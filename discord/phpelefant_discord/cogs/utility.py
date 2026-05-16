from __future__ import annotations

import time

import discord
from discord.ext import commands

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.db.session import session_scope
from phpelefant_discord.services.settings import get_or_create_guild_settings
from phpelefant_discord.services.stats import global_counts
from phpelefant_discord.utils.formatting import code_embed, table_embed

STARTED_AT = time.monotonic()


def uptime_text() -> str:
    seconds = int(time.monotonic() - STARTED_AT)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"


class Utility(commands.Cog):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="start", aliases=["about"])
    async def start(self, ctx: commands.Context) -> None:
        await ctx.send(
            embed=table_embed(
                "PHPelefant",
                [
                    ("purpose", "moderation, activities, and fun community tools"),
                    ("official server", self.bot.settings.official_server_id or "not configured"),
                    ("prefix", self.bot.settings.command_prefix),
                ],
            )
        )

    @commands.hybrid_command(name="help")
    async def help_command(self, ctx: commands.Context) -> None:
        await ctx.send(
            embed=code_embed(
                "Help",
                "Moderation: ban unban kick mute unmute warn warnings resetwarnings purge delete lock unlock slowmode rules setrules pin unpin report adminlist\n"
                "Settings: settings setlogchannel setwarnlimit antispam antilink anticaps badwords whitelist forcesub\n"
                "Welcome: setwelcome welcome setgoodbye goodbye\n"
                "Activity: rank level xp leaderboard top activity profile\n"
                "Fun: joke meme quote fact 8ball coinflip dice roll ship roast compliment hug slap cat dog poll quiz\n"
                "Owner: owner broadcast broadcastchannel statsglobal leaveguild blacklistuser unblacklistuser blacklistguild unblacklistguild shell shellusers backupdb shutdown"
            )
        )

    @commands.hybrid_command(name="id")
    async def id_command(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member or ctx.author
        await ctx.send(embed=code_embed("IDs", f"user_id={target.id}\nguild_id={ctx.guild.id if ctx.guild else 'dm'}\nchannel_id={ctx.channel.id}"))

    @commands.hybrid_command(name="userinfo")
    async def userinfo(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member or ctx.author
        await ctx.send(
            embed=table_embed(
                "User info",
                [
                    ("id", target.id),
                    ("name", str(target)),
                    ("display", target.display_name),
                    ("bot", target.bot),
                    ("joined", target.joined_at.isoformat() if isinstance(target, discord.Member) and target.joined_at else "unknown"),
                ],
            )
        )

    @commands.hybrid_command(name="chatinfo", aliases=["serverinfo"])
    @commands.guild_only()
    async def chatinfo(self, ctx: commands.Context) -> None:
        guild = ctx.guild
        await ctx.send(embed=table_embed("Server info", [("id", guild.id), ("name", guild.name), ("members", guild.member_count)]))

    @commands.hybrid_command(name="ping")
    async def ping(self, ctx: commands.Context) -> None:
        await ctx.send(embed=code_embed("Ping", f"pong {round(self.bot.latency * 1000)} ms"))

    @commands.hybrid_command(name="uptime")
    async def uptime(self, ctx: commands.Context) -> None:
        await ctx.send(embed=code_embed("Uptime", uptime_text()))

    @commands.hybrid_command(name="stats")
    async def stats(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            counts = await global_counts(session)
        await ctx.send(
            embed=table_embed(
                "Bot statistics",
                [
                    ("guilds", counts["guilds"]),
                    ("users", counts["users"]),
                    ("messages", counts["messages"]),
                    ("moderation actions", counts["moderation_actions"]),
                ],
            )
        )

    @commands.hybrid_command(name="settings")
    @commands.guild_only()
    async def settings(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            row = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
        await ctx.send(
            embed=table_embed(
                "Server settings",
                [
                    ("welcome", row.welcome_enabled),
                    ("goodbye", row.goodbye_enabled),
                    ("warning limit", row.warning_limit),
                    ("anti-spam", row.anti_spam_enabled),
                    ("anti-link", row.anti_link_enabled),
                    ("anti-caps", row.anti_caps_enabled),
                    ("anti-badword", row.anti_badword_enabled),
                    ("activity", row.activity_enabled),
                    ("fun", row.fun_enabled),
                    ("force-subscribe", row.force_subscribe_enabled),
                    ("log channel", row.log_channel_id or "not set"),
                    ("language", row.language),
                    ("timezone", row.timezone),
                ],
            )
        )

    @commands.hybrid_command(name="language")
    @commands.guild_only()
    async def language(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            row = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
        await ctx.send(embed=code_embed("Language", row.language))

    @commands.hybrid_command(name="timezone")
    @commands.guild_only()
    async def timezone(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            row = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
        await ctx.send(embed=code_embed("Timezone", row.timezone))


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(Utility(bot))
