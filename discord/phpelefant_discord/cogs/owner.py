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
from phpelefant_discord.utils.formatting import code_block, table_embed, truncate
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
                    ("leaveguild", "leaveguild <guild_id>"),
                    ("blacklistuser", "blacklistuser <user_id> <reason>"),
                    ("blacklistguild", "blacklistguild <guild_id> <reason>"),
                    ("shell", "shell <command>"),
                    ("shellusers", "shellusers add|remove|list"),
                    ("backupdb", "backupdb"),
                    ("setofficialchannel", "setofficialchannel <channel_id>"),
                    ("restart", "restart CONFIRM"),
                    ("shutdown", "shutdown CONFIRM"),
                ],
            )
        )

    @commands.hybrid_command(name="broadcast")
    @owner_only()
    async def broadcast(self, ctx: commands.Context, *, message: str) -> None:
        sent = failed = 0
        async with session_scope(self.bot.session_factory) as session:
            targets = sorted(set(await known_guild_ids(session)) | set(await known_user_ids(session)))
            for target_id in targets:
                target = self.bot.get_channel(target_id) or self.bot.get_user(target_id)
                if target is None:
                    failed += 1
                    continue
                try:
                    await target.send(message)
                    sent += 1
                    await asyncio.sleep(0.05)
                except discord.DiscordException:
                    failed += 1
            session.add(BroadcastHistory(actor_user_id=ctx.author.id, target="all", message=message, sent_count=sent, failed_count=failed))
        await ctx.send(embed=table_embed("Broadcast", [("sent", sent), ("failed", failed)]))

    @commands.hybrid_command(name="broadcastchannel")
    @owner_only()
    async def broadcastchannel(self, ctx: commands.Context, *, message: str) -> None:
        channel = self.bot.get_channel(self.bot.settings.official_channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            await ctx.send(code_block("Official channel is not configured or not cached."))
            return
        await channel.send(message)
        await ctx.send(code_block("Sent to official channel."))

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
            await ctx.send(code_block("Guild not found."))
            return
        await guild.leave()
        await ctx.send(code_block(f"Left guild {guild_id}."))

    @commands.hybrid_command(name="blacklistuser")
    @owner_only()
    async def blacklistuser(self, ctx: commands.Context, user_id: int, *, reason: str) -> None:
        if user_id == self.bot.settings.bot_owner_id:
            await ctx.send(code_block("Refusing to blacklist owner."))
            return
        async with session_scope(self.bot.session_factory) as session:
            row = await session.get(BlacklistedUser, user_id)
            if row is None:
                session.add(BlacklistedUser(user_id=user_id, reason=reason, created_by=ctx.author.id))
            else:
                row.reason = reason
        await ctx.send(code_block(f"Blacklisted user {user_id}."))

    @commands.hybrid_command(name="unblacklistuser")
    @owner_only()
    async def unblacklistuser(self, ctx: commands.Context, user_id: int) -> None:
        async with session_scope(self.bot.session_factory) as session:
            await session.execute(delete(BlacklistedUser).where(BlacklistedUser.user_id == user_id))
        await ctx.send(code_block("Removed if present."))

    @commands.hybrid_command(name="blacklistguild")
    @owner_only()
    async def blacklistguild(self, ctx: commands.Context, guild_id: int, *, reason: str) -> None:
        async with session_scope(self.bot.session_factory) as session:
            row = await session.get(BlacklistedGuild, guild_id)
            if row is None:
                session.add(BlacklistedGuild(guild_id=guild_id, reason=reason, created_by=ctx.author.id))
            else:
                row.reason = reason
        await ctx.send(code_block(f"Blacklisted guild {guild_id}."))

    @commands.hybrid_command(name="unblacklistguild")
    @owner_only()
    async def unblacklistguild(self, ctx: commands.Context, guild_id: int) -> None:
        async with session_scope(self.bot.session_factory) as session:
            await session.execute(delete(BlacklistedGuild).where(BlacklistedGuild.guild_id == guild_id))
        await ctx.send(code_block("Removed if present."))

    @commands.hybrid_command(name="shell")
    async def shell(self, ctx: commands.Context, *, command: str) -> None:
        async with session_scope(self.bot.session_factory) as session:
            if not await is_shell_allowed(session, ctx.author.id, self.bot.settings):
                await ctx.send(code_block("Shell access denied."))
                return
            try:
                result = await run_real_shell(command, self.bot.settings)
            except ValueError as exc:
                await ctx.send(code_block(f"Shell rejected: {exc}"))
                return
            await log_action(session, ctx.guild.id if ctx.guild else 0, "owner_shell", None, ctx.author.id, result.command)
        body = self.render_shell_result(result)
        output, truncated = truncate(body, self.bot.settings.shell_output_limit)
        await ctx.send(code_block(output))
        if truncated:
            await ctx.send(code_block("Output truncated."))

    @commands.hybrid_group(name="shellusers", fallback="list")
    @owner_only()
    async def shellusers(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            users = await list_shell_users(session, self.bot.settings)
        await ctx.send(code_block("\n".join(str(user_id) for user_id in users)))

    @shellusers.command(name="add")
    async def shellusers_add(self, ctx: commands.Context, user_id: int, *, note: str = "trusted") -> None:
        async with session_scope(self.bot.session_factory) as session:
            await add_shell_user(session, user_id, ctx.author.id, note)
        await ctx.send(code_block(f"Added shell user {user_id}."))

    @shellusers.command(name="remove")
    async def shellusers_remove(self, ctx: commands.Context, user_id: int) -> None:
        if user_id == self.bot.settings.bot_owner_id:
            await ctx.send(code_block("Owner always has shell access."))
            return
        async with session_scope(self.bot.session_factory) as session:
            await remove_shell_user(session, user_id)
        await ctx.send(code_block(f"Removed shell user {user_id} if present."))

    @commands.hybrid_command(name="eval")
    @owner_only()
    async def eval_command(self, ctx: commands.Context, *, expr: str) -> None:
        if not self.bot.settings.enable_eval:
            await ctx.send(code_block("Eval disabled."))
            return
        result = eval(expr, {"__builtins__": {}}, {"time": time.time})  # noqa: S307
        await ctx.send(code_block(str(result)))

    @commands.hybrid_command(name="shutdown")
    @owner_only()
    async def shutdown(self, ctx: commands.Context, confirm: str = "") -> None:
        if confirm != "CONFIRM":
            await ctx.send(code_block("Use shutdown CONFIRM."))
            return
        await ctx.send(code_block("Shutdown requested."))
        asyncio.get_running_loop().call_later(1, signal.raise_signal, signal.SIGTERM)

    @commands.hybrid_command(name="restart")
    @owner_only()
    async def restart(self, ctx: commands.Context, confirm: str = "") -> None:
        if confirm != "CONFIRM":
            await ctx.send(code_block("Use restart CONFIRM."))
            return
        await ctx.send(code_block("Restart requested."))
        asyncio.get_running_loop().call_later(1, signal.raise_signal, signal.SIGTERM)

    @commands.hybrid_command(name="backupdb")
    @owner_only()
    async def backupdb(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            payload = await export_database_json(session)
        await ctx.send(file=discord.File(fp=io.BytesIO(payload), filename="phpelefant-discord-backup.json"))

    @commands.hybrid_command(name="setofficialchannel")
    @owner_only()
    async def setofficialchannel(self, ctx: commands.Context, channel_id: int) -> None:
        async with session_scope(self.bot.session_factory) as session:
            await session.execute(update(GuildSettings).values(official_channel_id=channel_id))
        await ctx.send(code_block(f"Official channel set to {channel_id} for all configured guilds."))

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


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(Owner(bot))
