from __future__ import annotations

import asyncio
import io
import signal
import time

import discord
from discord.ext import commands
from sqlalchemy import delete, text, update

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.db.models import BlacklistedGuild, BlacklistedUser, BroadcastHistory, GuildSettings
from phpelefant_discord.db.session import session_scope
from phpelefant_discord.services.backup import export_database_json
from phpelefant_discord.services.moderation import log_action
from phpelefant_discord.services.settings import known_guild_ids, known_user_ids
from phpelefant_discord.services.shell import add_shell_user, is_shell_allowed, list_shell_users, remove_shell_user, run_real_shell
from phpelefant_discord.services.stats import global_counts
from phpelefant_discord.utils.formatting import code_embed, embed, error_embed, success_embed, table_embed, truncate
from phpelefant_discord.cogs.utility import uptime_text


def owner_only():
    async def predicate(ctx: commands.Context) -> bool:
        return ctx.author.id == ctx.bot.settings.bot_owner_id

    return commands.check(predicate)


class Owner(commands.Cog):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="owner")
    @owner_only()
    async def owner(self, ctx: commands.Context) -> None:
        await ctx.send(
            embed=table_embed(
                "Owner panel",
                [
                    ("broadcast", "broadcast <message>"),
                    ("broadcastchannel", "broadcastchannel <message>"),
                    ("statsglobal", "statsglobal"),
                    ("announcements", "announcefeed add <channel> <feed_url>"),
                    ("leaveguild", "leaveguild <guild_id>"),
                    ("blacklistuser", "blacklistuser <user_id> <reason>"),
                    ("blacklistguild", "blacklistguild <guild_id> <reason>"),
                    ("shell", "shell <command>"),
                    ("shellusers", "shellusers add|remove|list"),
                    ("backupdb", "backupdb"),
                    ("setofficialserver", "setofficialserver <server_id>"),
                    ("restart", "restart CONFIRM"),
                    ("shutdown", "shutdown CONFIRM"),
                ],
            )
        )

    @commands.hybrid_command(name="broadcast")
    @owner_only()
    async def broadcast(self, ctx: commands.Context, *, message: str) -> None:
        sent = failed = 0
        announcement = self.broadcast_embed("PHPelefant Broadcast", message, ctx.author)
        async with session_scope(self.bot.session_factory) as session:
            targets = sorted(set(await known_guild_ids(session)) | set(await known_user_ids(session)))
            for target_id in targets:
                guild = self.bot.get_guild(target_id)
                if guild is not None:
                    target = guild.system_channel
                else:
                    target = self.bot.get_user(target_id)
                if target is None:
                    failed += 1
                    continue
                try:
                    await target.send(embed=announcement)
                    sent += 1
                    await asyncio.sleep(0.05)
                except discord.DiscordException:
                    failed += 1
            session.add(BroadcastHistory(actor_user_id=ctx.author.id, target="all", message=message, sent_count=sent, failed_count=failed))
        await ctx.send(
            embed=table_embed(
                "Broadcast Complete",
                [("targets", len(targets)), ("sent", sent), ("failed", failed), ("message length", len(message))],
                status="owner",
                description="The broadcast was sent as a branded PHPelefant embed.",
            )
        )

    @commands.hybrid_command(name="broadcastchannel")
    @owner_only()
    async def broadcastchannel(self, ctx: commands.Context, *, message: str) -> None:
        guild = self.bot.get_guild(self.bot.settings.official_server_id)
        channel = guild.system_channel if guild else None
        if not isinstance(channel, discord.abc.Messageable):
            await ctx.send(embed=error_embed("Broadcast", "Official server system channel is not configured or not cached."))
            return
        await channel.send(embed=self.broadcast_embed("Official PHPelefant Announcement", message, ctx.author))
        await ctx.send(embed=success_embed("Broadcast", "Sent to official server system channel."))

    @commands.hybrid_command(name="statsglobal")
    @owner_only()
    async def statsglobal(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            counts = await global_counts(session)
            db_ok = "ok"
            try:
                await session.execute(text("SELECT 1"))
            except Exception:
                db_ok = "error"
        await ctx.send(embed=table_embed("Global statistics", [("guilds", counts["guilds"]), ("users", counts["users"]), ("messages", counts["messages"]), ("moderation actions", counts["moderation_actions"]), ("uptime", uptime_text()), ("database", db_ok)]))

    @commands.hybrid_command(name="leaveguild")
    @owner_only()
    async def leaveguild(self, ctx: commands.Context, guild_id: int) -> None:
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            await ctx.send(embed=error_embed("Leave Guild", "Guild not found."))
            return
        await guild.leave()
        await ctx.send(embed=success_embed("Leave Guild", f"Left guild `{guild_id}`."))

    @commands.hybrid_command(name="blacklistuser")
    @owner_only()
    async def blacklistuser(self, ctx: commands.Context, user_id: int, *, reason: str) -> None:
        if user_id == self.bot.settings.bot_owner_id:
            await ctx.send(embed=error_embed("Blacklist User", "Refusing to blacklist owner."))
            return
        async with session_scope(self.bot.session_factory) as session:
            row = await session.get(BlacklistedUser, user_id)
            if row is None:
                session.add(BlacklistedUser(user_id=user_id, reason=reason, created_by=ctx.author.id))
            else:
                row.reason = reason
        await ctx.send(embed=success_embed("Blacklist User", f"Blacklisted user `{user_id}`."))

    @commands.hybrid_command(name="unblacklistuser")
    @owner_only()
    async def unblacklistuser(self, ctx: commands.Context, user_id: int) -> None:
        async with session_scope(self.bot.session_factory) as session:
            await session.execute(delete(BlacklistedUser).where(BlacklistedUser.user_id == user_id))
        await ctx.send(embed=success_embed("Unblacklist User", "Removed if present."))

    @commands.hybrid_command(name="blacklistguild")
    @owner_only()
    async def blacklistguild(self, ctx: commands.Context, guild_id: int, *, reason: str) -> None:
        async with session_scope(self.bot.session_factory) as session:
            row = await session.get(BlacklistedGuild, guild_id)
            if row is None:
                session.add(BlacklistedGuild(guild_id=guild_id, reason=reason, created_by=ctx.author.id))
            else:
                row.reason = reason
        await ctx.send(embed=success_embed("Blacklist Guild", f"Blacklisted guild `{guild_id}`."))

    @commands.hybrid_command(name="unblacklistguild")
    @owner_only()
    async def unblacklistguild(self, ctx: commands.Context, guild_id: int) -> None:
        async with session_scope(self.bot.session_factory) as session:
            await session.execute(delete(BlacklistedGuild).where(BlacklistedGuild.guild_id == guild_id))
        await ctx.send(embed=success_embed("Unblacklist Guild", "Removed if present."))

    @commands.hybrid_command(name="shell")
    async def shell(self, ctx: commands.Context, *, command: str) -> None:
        async with session_scope(self.bot.session_factory) as session:
            if not await is_shell_allowed(session, ctx.author.id, self.bot.settings):
                await ctx.send(embed=error_embed("Shell", "Shell access denied."))
                return
            try:
                result = await run_real_shell(command, self.bot.settings)
            except ValueError as exc:
                await ctx.send(embed=error_embed("Shell", f"Shell rejected: {exc}"))
                return
            await log_action(session, ctx.guild.id if ctx.guild else 0, "owner_shell", None, ctx.author.id, result.command)
        body = self.render_shell_result(result)
        output, truncated = truncate(body, self.bot.settings.shell_output_limit)
        await ctx.send(embed=code_embed("Shell", output, "bash", status="owner"))
        if truncated:
            await ctx.send(embed=code_embed("Shell", "Output truncated.", status="warning"))

    @commands.hybrid_group(name="shellusers", fallback="list")
    @owner_only()
    async def shellusers(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            users = await list_shell_users(session, self.bot.settings)
        await ctx.send(embed=code_embed("Shell Users", "\n".join(str(user_id) for user_id in users) or "No shell users."))

    @shellusers.command(name="add")
    @owner_only()
    async def shellusers_add(self, ctx: commands.Context, user_id: int, *, note: str = "trusted") -> None:
        async with session_scope(self.bot.session_factory) as session:
            await add_shell_user(session, user_id, ctx.author.id, note)
        await ctx.send(embed=success_embed("Shell Users", f"Added shell user `{user_id}`."))

    @shellusers.command(name="remove")
    @owner_only()
    async def shellusers_remove(self, ctx: commands.Context, user_id: int) -> None:
        if user_id == self.bot.settings.bot_owner_id:
            await ctx.send(embed=error_embed("Shell Users", "Owner always has shell access."))
            return
        async with session_scope(self.bot.session_factory) as session:
            await remove_shell_user(session, user_id)
        await ctx.send(embed=success_embed("Shell Users", f"Removed shell user `{user_id}` if present."))

    @commands.hybrid_command(name="eval")
    @owner_only()
    async def eval_command(self, ctx: commands.Context, *, expr: str) -> None:
        if not self.bot.settings.enable_eval:
            await ctx.send(embed=error_embed("Eval", "Eval disabled."))
            return
        result = eval(expr, {"__builtins__": {}}, {"time": time.time})  # noqa: S307
        await ctx.send(embed=code_embed("Eval", str(result), status="owner"))

    @commands.hybrid_command(name="shutdown")
    @owner_only()
    async def shutdown(self, ctx: commands.Context, confirm: str = "") -> None:
        if confirm != "CONFIRM":
            await ctx.send(embed=error_embed("Shutdown", "Use `shutdown CONFIRM`."))
            return
        await ctx.send(embed=success_embed("Shutdown", "Shutdown requested."))
        asyncio.get_running_loop().call_later(1, signal.raise_signal, signal.SIGTERM)

    @commands.hybrid_command(name="restart")
    @owner_only()
    async def restart(self, ctx: commands.Context, confirm: str = "") -> None:
        if confirm != "CONFIRM":
            await ctx.send(embed=error_embed("Restart", "Use `restart CONFIRM`."))
            return
        await ctx.send(embed=success_embed("Restart", "Restart requested."))
        asyncio.get_running_loop().call_later(1, signal.raise_signal, signal.SIGTERM)

    @commands.hybrid_command(name="backupdb")
    @owner_only()
    async def backupdb(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            payload = await export_database_json(session)
        await ctx.send(embed=success_embed("Database Backup", "Backup created."), file=discord.File(fp=io.BytesIO(payload), filename="phpelefant-discord-backup.json"))

    @commands.hybrid_command(name="setofficialserver", aliases=["setofficialchannel"])
    @owner_only()
    async def setofficialserver(self, ctx: commands.Context, server_id: int) -> None:
        async with session_scope(self.bot.session_factory) as session:
            await session.execute(update(GuildSettings).values(official_channel_id=server_id))
        await ctx.send(embed=success_embed("Official Server", f"Official server set to `{server_id}` for all configured guilds."))

    @staticmethod
    def render_shell_result(result) -> str:
        parts = [f"$ {result.command}", f"exit code: {result.return_code}" if not result.timed_out else "timed out"]
        if result.stdout:
            parts.append("\n[stdout]\n" + result.stdout.rstrip())
        if result.stderr:
            parts.append("\n[stderr]\n" + result.stderr.rstrip())
        if not result.stdout and not result.stderr:
            parts.append("\n(no output)")
        return "\n".join(parts)

    @staticmethod
    def broadcast_embed(title: str, message: str, author: discord.User | discord.Member) -> discord.Embed:
        item = embed(title, message[:4000], status="owner")
        item.add_field(name="Sent By", value=f"{author} (`{author.id}`)", inline=False)
        try:
            item.set_thumbnail(url=author.display_avatar.url)
        except AttributeError:
            pass
        return item


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(Owner(bot))
