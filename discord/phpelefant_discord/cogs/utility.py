from __future__ import annotations

import time

import discord
from discord.ext import commands

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.db.session import session_scope
from phpelefant_discord.services.settings import get_or_create_guild_settings
from phpelefant_discord.services.stats import global_counts
from phpelefant_discord.utils.formatting import code_block, code_embed, embed, table_embed

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
        item = embed(
            "PHPelefant",
            "Advanced community management for moderation, activity, server utilities, engagement, and owner operations.",
        )
        if self.bot.user:
            item.set_thumbnail(url=self.bot.user.display_avatar.url)
        item.add_field(name="Command Access", value=f"Slash commands and prefix `{self.bot.settings.command_prefix}`", inline=True)
        item.add_field(name="Official Server", value=str(self.bot.settings.official_server_id or "not configured"), inline=True)
        item.add_field(name="Owner ID", value=str(self.bot.settings.bot_owner_id), inline=True)
        item.add_field(
            name="Core Systems",
            value="Moderation logs, anti-spam, XP/levels, welcome/goodbye, fun media, shell controls, and channel editing.",
            inline=False,
        )
        await ctx.send(embed=item)

    @commands.hybrid_command(name="help")
    async def help_command(self, ctx: commands.Context) -> None:
        prefix = self.bot.settings.command_prefix
        item = embed(
            "PHPelefant Command Directory",
            f"Use slash commands or prefix commands with `{prefix}`. Staff commands require Discord permissions; owner commands require your configured owner ID.",
        )
        if self.bot.user:
            item.set_thumbnail(url=self.bot.user.display_avatar.url)

        sections = [
            (
                "Moderation",
                "`ban`, `fakeban`, `unban`, `kick`, `mute`, `unmute`, `warn`, `warnings`, `resetwarnings`, `warnconfig`, `modlogs`, `purge`, `delete`, `lock`, `unlock`, `slowmode`, `pin`, `unpin`, `nick`, `addrole`, `removerole`",
            ),
            (
                "Server Setup",
                "`rules`, `setrules`, `settings`, `setlogchannel`, `setwarnlimit`, `antispam`, `antilink`, `anticaps`, `badwords`, `whitelist`, `forcesub`, `forcesubstatus`",
            ),
            (
                "Tickets",
                "`ticket`, `ticket setup`, `ticket panel`, `ticket categories`, `ticket close`, `ticket claim`, `ticket add`, `ticket remove`, `ticket transcript`, `ticket settings`, `ticket enable`, `ticket disable`, `ticketsetup`",
            ),
            (
                "Channel Editor",
                "`/edit type:channels deletechars:true deletetoindex:3 keepemojis:true surroundsymbol1:【 surroundsymbol2:】`\n"
                f"`{prefix}edit type:channels deletechars:true deletetoindex:3 keepemojis:true surroundsymbol1:【 sourroundsymbol2:】`",
            ),
            (
                "Welcome And Activity",
                "`setwelcome`, `welcome`, `setgoodbye`, `goodbye`, `rank`, `level`, `xp`, `leaderboard`, `top`, `activity`, `profile`",
            ),
            (
                "Fun And Media",
                "`joke`, `meme`, `quote`, `fact`, `8ball`, `coinflip`, `dice`, `roll`, `ship`, `roast`, `compliment`, `hug`, `slap`, `cat`, `dog`, `httpcat`, `httpdog`, `choose`, `rate`, `avatar`, `poll`, `quiz`",
            ),
            (
                "Owner Console",
                "`owner`, `broadcast`, `broadcastchannel`, `statsglobal`, `leaveguild`, `blacklistuser`, `unblacklistuser`, `blacklistguild`, `unblacklistguild`, `shell`, `shellusers`, `backupdb`, `restart`, `shutdown`",
            ),
        ]
        for name, value in sections:
            item.add_field(name=name, value=value[:1024], inline=False)
        item.add_field(
            name="Examples",
            value=code_block(
                f"{prefix}fakeban @member testing the moderation flow\n"
                f"{prefix}ticket billing question\n"
                f"{prefix}ticket panel #support\n"
                f"{prefix}mute @member 1h spam\n"
                f"{prefix}quote <message_id>\n"
                f"{prefix}edit type:channels deletechars:true deletetoindex:3 keepemojis:true preview:true",
            ),
            inline=False,
        )
        await ctx.send(embed=item)

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
