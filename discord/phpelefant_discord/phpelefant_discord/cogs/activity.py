from __future__ import annotations

from datetime import date, timedelta

import discord
from discord.ext import commands

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.db.models import User
from phpelefant_discord.db.session import session_scope
from phpelefant_discord.services.activity import activity_since, get_activity, leaderboard, xp_required_for_level
from phpelefant_discord.services.moderation import warning_count
from phpelefant_discord.utils.formatting import code_embed, table_embed


class Activity(commands.Cog):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="rank", aliases=["level", "xp"])
    @commands.guild_only()
    async def rank(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member or ctx.author
        async with session_scope(self.bot.session_factory) as session:
            row = await get_activity(session, ctx.guild.id, target.id)
        await ctx.send(embed=table_embed("Rank", [("user", target.id), ("level", row.level), ("xp", f"{row.xp}/{xp_required_for_level(row.level + 1)}"), ("messages", row.message_count)]))

    @commands.hybrid_command(name="leaderboard", aliases=["top"])
    @commands.guild_only()
    async def top(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            rows = await leaderboard(session, ctx.guild.id, 10)
            lines = []
            for index, row in enumerate(rows, start=1):
                db_user = await session.get(User, row.user_id)
                name = db_user.display_name if db_user and db_user.display_name else row.user_id
                lines.append(f"{index}. {name}: level {row.level}, xp {row.xp}, messages {row.message_count}")
        await ctx.send(embed=code_embed("Leaderboard", "\n".join(lines) if lines else "No activity recorded."))

    @commands.hybrid_command(name="activity")
    @commands.guild_only()
    async def activity(self, ctx: commands.Context) -> None:
        today = date.today()
        async with session_scope(self.bot.session_factory) as session:
            daily = await activity_since(session, ctx.guild.id, today)
            weekly = await activity_since(session, ctx.guild.id, today - timedelta(days=7))
        await ctx.send(embed=code_embed("Activity", f"today: {daily or 'none'}\nlast_7_days: {weekly or 'none'}"))

    @commands.hybrid_command(name="profile")
    @commands.guild_only()
    async def profile(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member or ctx.author
        async with session_scope(self.bot.session_factory) as session:
            row = await get_activity(session, ctx.guild.id, target.id)
            warnings = await warning_count(session, ctx.guild.id, target.id)
            db_user = await session.get(User, target.id)
        await ctx.send(
            embed=table_embed(
                "Profile",
                [
                    ("user id", target.id),
                    ("username", str(target)),
                    ("join date", row.joined_at.isoformat() if row.joined_at else "unknown"),
                    ("messages", row.message_count),
                    ("xp", row.xp),
                    ("level", row.level),
                    ("warnings", warnings),
                    ("reputation", db_user.reputation if db_user else 0),
                ],
            )
        )


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(Activity(bot))
