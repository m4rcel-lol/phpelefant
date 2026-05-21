from __future__ import annotations

from datetime import date, timedelta

import discord
from discord.ext import commands

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.db.models import User
from phpelefant_discord.db.session import session_scope
from phpelefant_discord.services.activity import activity_since, get_activity, leaderboard, xp_required_for_level
from phpelefant_discord.services.moderation import warning_count
from phpelefant_discord.utils.formatting import embed, table_embed


def activity_scope_id(ctx: commands.Context) -> int:
    return ctx.guild.id if ctx.guild else 0


def progress_bar(current: int, maximum: int, width: int = 12) -> str:
    if maximum <= 0:
        return "#" * width
    filled = min(width, max(0, round((current / maximum) * width)))
    return "#" * filled + "-" * (width - filled)


class Activity(commands.Cog):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="rank", aliases=["level", "xp"])
    async def rank(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member or ctx.author
        async with session_scope(self.bot.session_factory) as session:
            row = await get_activity(session, activity_scope_id(ctx), target.id)
        next_xp = xp_required_for_level(row.level + 1)
        previous_xp = xp_required_for_level(row.level)
        gained_this_level = max(0, row.xp - previous_xp)
        needed_this_level = max(1, next_xp - previous_xp)
        item = table_embed(
            "Rank",
            [
                ("user", getattr(target, "mention", str(target))),
                ("level", row.level),
                ("xp", f"{row.xp}/{next_xp}"),
                ("progress", progress_bar(gained_this_level, needed_this_level)),
                ("messages", row.message_count),
            ],
            description="Activity is tracked per server. In DMs, PHPelefant uses a private direct-message scope.",
        )
        try:
            item.set_thumbnail(url=target.display_avatar.url)
        except AttributeError:
            pass
        await ctx.send(embed=item)

    @commands.hybrid_command(name="leaderboard", aliases=["top"])
    async def top(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            rows = await leaderboard(session, activity_scope_id(ctx), 10)
            item = embed("Leaderboard", "Top members by XP and message activity.", status="info")
            for index, row in enumerate(rows, start=1):
                db_user = await session.get(User, row.user_id)
                name = db_user.display_name if db_user and db_user.display_name else row.user_id
                item.add_field(name=f"#{index} {name}", value=f"Level `{row.level}` • XP `{row.xp}` • Messages `{row.message_count}`", inline=False)
        if not rows:
            item.description = "No activity recorded yet."
        await ctx.send(embed=item)

    @commands.hybrid_command(name="activity")
    async def activity(self, ctx: commands.Context) -> None:
        today = date.today()
        async with session_scope(self.bot.session_factory) as session:
            daily = await activity_since(session, activity_scope_id(ctx), today)
            weekly = await activity_since(session, activity_scope_id(ctx), today - timedelta(days=7))
        item = embed("Activity", "Daily and weekly activity snapshots.")
        item.add_field(name="Today", value=self.format_activity_lines(daily), inline=False)
        item.add_field(name="Last 7 Days", value=self.format_activity_lines(weekly), inline=False)
        await ctx.send(embed=item)

    @commands.hybrid_command(name="profile")
    async def profile(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member or ctx.author
        async with session_scope(self.bot.session_factory) as session:
            scope_id = activity_scope_id(ctx)
            row = await get_activity(session, scope_id, target.id)
            warnings = await warning_count(session, scope_id, target.id) if ctx.guild else 0
            db_user = await session.get(User, target.id)
        next_xp = xp_required_for_level(row.level + 1)
        previous_xp = xp_required_for_level(row.level)
        item = table_embed(
            "Profile",
            [
                ("user", getattr(target, "mention", str(target))),
                ("user id", target.id),
                ("username", str(target)),
                ("joined", row.joined_at.strftime("%Y-%m-%d %H:%M UTC") if row.joined_at else "unknown"),
                ("messages", row.message_count),
                ("xp", f"{row.xp}/{next_xp}"),
                ("level", row.level),
                ("progress", progress_bar(max(0, row.xp - previous_xp), max(1, next_xp - previous_xp))),
                ("warnings", warnings),
                ("reputation", db_user.reputation if db_user else 0),
            ],
            description="Public community profile with moderation and activity state.",
        )
        try:
            item.set_thumbnail(url=target.display_avatar.url)
        except AttributeError:
            pass
        await ctx.send(embed=item)

    @staticmethod
    def format_activity_lines(rows: list[tuple[int, int]]) -> str:
        if not rows:
            return "No activity recorded."
        return "\n".join(f"`{index}.` <@{user_id}> - `{count}` messages" for index, (user_id, count) in enumerate(rows, start=1))[:1024]


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(Activity(bot))
