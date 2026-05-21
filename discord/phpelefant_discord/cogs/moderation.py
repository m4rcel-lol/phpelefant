from __future__ import annotations

from datetime import UTC, datetime

import discord
from discord.ext import commands
from sqlalchemy import select

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.db.models import ModerationLog
from phpelefant_discord.db.session import session_scope
from phpelefant_discord.services.moderation import add_warning, log_action, reset_warnings, warning_count
from phpelefant_discord.services.settings import get_or_create_guild_settings
from phpelefant_discord.utils.formatting import code_embed, error_embed, moderation_embed, success_embed, table_embed, warning_embed
from phpelefant_discord.utils.time import parse_duration

STAFF_PERMISSION_NAMES = (
    "administrator",
    "ban_members",
    "kick_members",
    "moderate_members",
    "manage_messages",
    "manage_guild",
    "manage_channels",
    "manage_roles",
)


def is_owner_id(bot: PHPelefantBot, user_id: int) -> bool:
    return user_id == bot.settings.bot_owner_id


def is_staff_context(ctx: commands.Context) -> bool:
    if is_owner_id(ctx.bot, ctx.author.id):
        return True
    if not isinstance(ctx.author, discord.Member):
        return False
    return any(getattr(ctx.author.guild_permissions, permission) for permission in STAFF_PERMISSION_NAMES)


def guild_permissions_or_owner(**permissions: bool):
    async def predicate(ctx: commands.Context) -> bool:
        if is_owner_id(ctx.bot, ctx.author.id):
            return True
        if not isinstance(ctx.author, discord.Member):
            raise commands.NoPrivateMessage()
        missing = [
            permission
            for permission, expected in permissions.items()
            if getattr(ctx.author.guild_permissions, permission) != expected
        ]
        if missing:
            raise commands.MissingPermissions(missing)
        return True

    return commands.check(predicate)


def can_moderate(ctx: commands.Context, member: discord.Member) -> tuple[bool, str]:
    if member.id == ctx.author.id:
        return False, "Cannot moderate yourself."
    if is_owner_id(ctx.bot, ctx.author.id):
        return True, ""
    if not isinstance(ctx.author, discord.Member) or not ctx.author.guild_permissions.moderate_members:
        return False, "Missing moderation permissions."
    if member.guild_permissions.administrator or member.top_role >= ctx.author.top_role:
        return False, "You cannot moderate this member."
    if ctx.guild and ctx.guild.me and member.top_role >= ctx.guild.me.top_role:
        return False, "PHPelefant's role must be above this member."
    return True, ""


def can_fakeban(ctx: commands.Context, member: discord.Member) -> tuple[bool, str]:
    if member.id == ctx.author.id:
        return False, "Cannot fakeban yourself."
    if not is_staff_context(ctx):
        return False, "Only staff can use fakeban."
    return True, ""


def can_manage_role(ctx: commands.Context, role: discord.Role) -> tuple[bool, str]:
    if role.is_default():
        return False, "Cannot manage the default role."
    if is_owner_id(ctx.bot, ctx.author.id):
        return True, ""
    if not isinstance(ctx.author, discord.Member) or not ctx.author.guild_permissions.manage_roles:
        return False, "Missing Manage Roles permission."
    if role >= ctx.author.top_role:
        return False, "You cannot manage a role equal to or above your top role."
    if ctx.guild and ctx.guild.me and role >= ctx.guild.me.top_role:
        return False, "PHPelefant's role must be above that role."
    return True, ""


class Moderation(commands.Cog):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot

    @staticmethod
    def action_embed(
        title: str,
        member: discord.Member,
        rows: list[tuple[str, object]],
        *,
        description: str | None = None,
        status: str = "moderation",
    ) -> discord.Embed:
        item = table_embed(title, rows, status=status, description=description)
        item.set_thumbnail(url=member.display_avatar.url)
        item.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
        if member.joined_at:
            item.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
        return item

    @commands.hybrid_command(name="ban")
    @commands.guild_only()
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        ok, message = can_moderate(ctx, member)
        if not ok:
            await ctx.send(embed=error_embed("Moderation", message))
            return
        try:
            await member.ban(reason=reason)
        except discord.Forbidden:
            await ctx.send(embed=error_embed("Ban", "PHPelefant is missing permission or role position."))
            return
        except discord.HTTPException:
            await ctx.send(embed=error_embed("Ban", "Discord rejected the ban request."))
            return
        async with session_scope(self.bot.session_factory) as session:
            await log_action(session, ctx.guild.id, "ban", member.id, ctx.author.id, reason)
        await ctx.send(
            embed=self.action_embed(
                "Ban",
                member,
                [("user", member.mention), ("user id", member.id), ("moderator", ctx.author.mention), ("reason", reason)],
                description="The member was banned from this server.",
            )
        )

    @commands.hybrid_command(name="fakeban")
    @commands.guild_only()
    async def fakeban(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        ok, message = can_fakeban(ctx, member)
        if not ok:
            await ctx.send(embed=error_embed("Fake Ban", message))
            return

        dm_sent = True
        dm = moderation_embed(
            "You have been banned",
            f"You have been banned from **{ctx.guild.name}**.",
        )
        dm.set_thumbnail(url=member.display_avatar.url)
        dm.add_field(name="Reason", value=reason[:1024], inline=False)
        dm.add_field(name="Moderator", value=str(ctx.author), inline=False)
        try:
            await member.send(embed=dm)
        except discord.DiscordException:
            dm_sent = False

        async with session_scope(self.bot.session_factory) as session:
            await log_action(
                session,
                ctx.guild.id,
                "fakeban",
                member.id,
                ctx.author.id,
                reason,
                {"dm_sent": dm_sent},
            )

        await ctx.send(
            embed=self.action_embed(
                "Fake Ban",
                member,
                [
                    ("user", member.mention),
                    ("user id", member.id),
                    ("reason", reason),
                    ("moderator", ctx.author.mention),
                    ("dm", "sent" if dm_sent else "failed or closed"),
                ],
                description="No real ban was applied. This is a staff-only fake ban notice.",
            )
        )

    @commands.hybrid_command(name="unban")
    @commands.guild_only()
    @guild_permissions_or_owner(ban_members=True)
    async def unban(self, ctx: commands.Context, user_id: int, *, reason: str = "No reason provided") -> None:
        user = discord.Object(id=user_id)
        try:
            await ctx.guild.unban(user, reason=reason)
        except discord.NotFound:
            await ctx.send(embed=error_embed("Unban", "That user is not banned here."))
            return
        except discord.DiscordException:
            await ctx.send(embed=error_embed("Unban", "Discord rejected the unban request."))
            return
        async with session_scope(self.bot.session_factory) as session:
            await log_action(session, ctx.guild.id, "unban", user_id, ctx.author.id, reason)
        await ctx.send(embed=table_embed("Unban", [("user", user_id), ("reason", reason)], status="success"))

    @commands.hybrid_command(name="kick")
    @commands.guild_only()
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        ok, message = can_moderate(ctx, member)
        if not ok:
            await ctx.send(embed=error_embed("Moderation", message))
            return
        try:
            await member.kick(reason=reason)
        except discord.Forbidden:
            await ctx.send(embed=error_embed("Kick", "PHPelefant is missing permission or role position."))
            return
        except discord.HTTPException:
            await ctx.send(embed=error_embed("Kick", "Discord rejected the kick request."))
            return
        async with session_scope(self.bot.session_factory) as session:
            await log_action(session, ctx.guild.id, "kick", member.id, ctx.author.id, reason)
        await ctx.send(
            embed=self.action_embed(
                "Kick",
                member,
                [("user", member.mention), ("user id", member.id), ("moderator", ctx.author.mention), ("reason", reason)],
                description="The member was removed from this server.",
            )
        )

    @commands.hybrid_command(name="mute", aliases=["timeout"])
    @commands.guild_only()
    async def mute(self, ctx: commands.Context, member: discord.Member, duration: str = "1h", *, reason: str = "No reason provided") -> None:
        ok, message = can_moderate(ctx, member)
        if not ok:
            await ctx.send(embed=error_embed("Moderation", message))
            return
        try:
            delta = parse_duration(duration)
        except ValueError as exc:
            await ctx.send(embed=error_embed("Moderation", str(exc)))
            return
        until = datetime.now(tz=UTC) + delta
        try:
            await member.timeout(until, reason=reason)
        except discord.Forbidden:
            await ctx.send(embed=error_embed("Timeout", "PHPelefant is missing permission or role position."))
            return
        except discord.HTTPException:
            await ctx.send(embed=error_embed("Timeout", "Discord rejected the timeout request."))
            return
        async with session_scope(self.bot.session_factory) as session:
            await log_action(session, ctx.guild.id, "timeout", member.id, ctx.author.id, reason, {"duration": duration})
        await ctx.send(
            embed=self.action_embed(
                "Timeout",
                member,
                [("user", member.mention), ("duration", duration), ("until", until.strftime("%Y-%m-%d %H:%M UTC")), ("reason", reason)],
            )
        )

    @commands.hybrid_command(name="unmute", aliases=["untimeout"])
    @commands.guild_only()
    @guild_permissions_or_owner(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        try:
            await member.timeout(None, reason=reason)
        except discord.Forbidden:
            await ctx.send(embed=error_embed("Untimeout", "PHPelefant is missing permission or role position."))
            return
        async with session_scope(self.bot.session_factory) as session:
            await log_action(session, ctx.guild.id, "untimeout", member.id, ctx.author.id, reason)
        await ctx.send(embed=table_embed("Untimeout", [("user", member.mention), ("reason", reason)], status="success"))

    @commands.hybrid_command(name="warn")
    @commands.guild_only()
    @guild_permissions_or_owner(moderate_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided") -> None:
        ok, message = can_moderate(ctx, member)
        if not ok:
            await ctx.send(embed=error_embed("Warn", message))
            return
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
            count, auto = await add_warning(session, settings, member, ctx.author.id, reason)
        await ctx.send(
            embed=self.action_embed(
                "Warn",
                member,
                [
                    ("user", member.mention),
                    ("warnings", f"{count}/{settings.warning_limit}"),
                    ("reason", reason),
                    ("auto action", auto or "none"),
                ],
            )
        )

    @commands.hybrid_command(name="warnings")
    @commands.guild_only()
    async def warnings(self, ctx: commands.Context, member: discord.Member) -> None:
        async with session_scope(self.bot.session_factory) as session:
            count = await warning_count(session, ctx.guild.id, member.id)
        await ctx.send(embed=table_embed("Warnings", [("user", member.mention), ("active warnings", count)]))

    @commands.hybrid_command(name="resetwarnings")
    @commands.guild_only()
    @guild_permissions_or_owner(moderate_members=True)
    async def resetwarnings(self, ctx: commands.Context, member: discord.Member) -> None:
        async with session_scope(self.bot.session_factory) as session:
            count = await reset_warnings(session, ctx.guild.id, member.id, ctx.author.id)
        await ctx.send(embed=table_embed("Reset warnings", [("user", member.mention), ("reset", count)], status="success"))

    @commands.hybrid_command(name="purge")
    @commands.guild_only()
    @guild_permissions_or_owner(manage_messages=True)
    async def purge(self, ctx: commands.Context, limit: int) -> None:
        if not 1 <= limit <= 100:
            await ctx.send(embed=error_embed("Purge", "Limit must be 1-100."))
            return
        deleted = await ctx.channel.purge(limit=limit + 1)
        async with session_scope(self.bot.session_factory) as session:
            await log_action(session, ctx.guild.id, "purge", None, ctx.author.id, str(len(deleted)))
        await ctx.send(embed=success_embed("Purge", f"Purged {len(deleted) - 1} messages."), delete_after=8)

    @commands.hybrid_command(name="delete")
    @commands.guild_only()
    @guild_permissions_or_owner(manage_messages=True)
    async def delete(self, ctx: commands.Context, message_id: int) -> None:
        message = await ctx.channel.fetch_message(message_id)
        await message.delete()
        try:
            await ctx.message.delete()
        except discord.DiscordException:
            pass
        await ctx.send(embed=success_embed("Delete", f"Deleted message `{message_id}`."), delete_after=8)

    @commands.hybrid_command(name="lock")
    @commands.guild_only()
    @guild_permissions_or_owner(manage_channels=True)
    async def lock(self, ctx: commands.Context) -> None:
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(embed=moderation_embed("Lock", f"{ctx.channel.mention} is locked."))

    @commands.hybrid_command(name="unlock")
    @commands.guild_only()
    @guild_permissions_or_owner(manage_channels=True)
    async def unlock(self, ctx: commands.Context) -> None:
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(embed=success_embed("Unlock", f"{ctx.channel.mention} is unlocked."))

    @commands.hybrid_command(name="slowmode")
    @commands.guild_only()
    @guild_permissions_or_owner(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, seconds: int) -> None:
        if not 0 <= seconds <= 21600:
            await ctx.send(embed=error_embed("Slowmode", "Slowmode must be between 0 and 21600 seconds."))
            return
        await ctx.channel.edit(slowmode_delay=seconds)
        await ctx.send(embed=success_embed("Slowmode", f"Slowmode set to `{seconds}s`."))

    @commands.hybrid_command(name="rules")
    @commands.guild_only()
    async def rules(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        if channel is not None:
            if not is_staff_context(ctx):
                await ctx.send(embed=error_embed("Rules", "Only staff can import rules from a channel."))
                return
            scraped = await self.scrape_rules(channel)
            if scraped is None:
                await ctx.send(embed=warning_embed("Rules", "No usable rules were found in that channel. Use `/setrules` to enter them manually."))
                return
            async with session_scope(self.bot.session_factory) as session:
                settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
                settings.rules_text = scraped[:4000]
                await log_action(session, ctx.guild.id, "scrape_rules", None, ctx.author.id, f"channel={channel.id}")
            item = success_embed("Rules Imported", scraped[:4000])
            item.add_field(name="Source", value=channel.mention, inline=True)
            await ctx.send(embed=item)
            return
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
        await ctx.send(embed=moderation_embed("Rules", settings.rules_text))

    async def scrape_rules(self, channel: discord.TextChannel) -> str | None:
        candidates: list[str] = []
        async for message in channel.history(limit=50, oldest_first=True):
            if message.author.bot and not message.embeds:
                continue
            text = message.clean_content.strip()
            if text:
                candidates.append(text)
            for item in message.embeds:
                parts = [item.title or "", item.description or ""]
                parts.extend(field.value for field in item.fields)
                merged = "\n".join(part.strip() for part in parts if part and part.strip())
                if merged:
                    candidates.append(merged)
        if not candidates:
            return None
        ruleish = [
            candidate
            for candidate in candidates
            if any(marker in candidate.casefold() for marker in ("rule", "rules", "1.", "1)", "respect", "allowed", "not allowed"))
        ]
        text = "\n\n".join(ruleish or candidates).strip()
        return text[:4000] if len(text) >= 20 else None

    @commands.hybrid_command(name="setrules")
    @commands.guild_only()
    @guild_permissions_or_owner(manage_guild=True)
    async def setrules(self, ctx: commands.Context, *, text: str) -> None:
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
            settings.rules_text = text[:4000]
            await log_action(session, ctx.guild.id, "setrules", None, ctx.author.id, None)
        await ctx.send(embed=success_embed("Rules", "Rules updated."))

    @commands.hybrid_command(name="pin")
    @commands.guild_only()
    @guild_permissions_or_owner(manage_messages=True)
    async def pin(self, ctx: commands.Context, message_id: int) -> None:
        message = await ctx.channel.fetch_message(message_id)
        await message.pin(reason=f"Pinned by {ctx.author}")
        await ctx.send(embed=success_embed("Pin", "Message pinned."))

    @commands.hybrid_command(name="unpin")
    @commands.guild_only()
    @guild_permissions_or_owner(manage_messages=True)
    async def unpin(self, ctx: commands.Context, message_id: int) -> None:
        message = await ctx.channel.fetch_message(message_id)
        await message.unpin(reason=f"Unpinned by {ctx.author}")
        await ctx.send(embed=success_embed("Unpin", "Message unpinned."))

    @commands.hybrid_command(name="report")
    @commands.guild_only()
    async def report(self, ctx: commands.Context, message_id: int, *, reason: str = "No reason provided") -> None:
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
        channel = ctx.guild.get_channel(settings.log_channel_id) if settings.log_channel_id else None
        if isinstance(channel, discord.TextChannel):
            await channel.send(embed=table_embed("Report", [("reporter", ctx.author.id), ("message", message_id), ("reason", reason)]))
        await ctx.send(embed=success_embed("Report", "Report submitted." if channel else "Report received; configure setlogchannel for admin logs."))

    @commands.hybrid_command(name="adminlist")
    @commands.guild_only()
    async def adminlist(self, ctx: commands.Context) -> None:
        admins = [member for member in ctx.guild.members if member.guild_permissions.administrator]
        await ctx.send(embed=code_embed("Admins", "\n".join(f"{m} ({m.id})" for m in admins) or "No cached admins."))

    @commands.hybrid_command(name="nick", aliases=["nickname"])
    @commands.guild_only()
    @guild_permissions_or_owner(manage_nicknames=True)
    async def nick(self, ctx: commands.Context, member: discord.Member, *, nickname: str | None = None) -> None:
        ok, message = can_moderate(ctx, member)
        if not ok:
            await ctx.send(embed=error_embed("Nickname", message))
            return
        nickname = nickname[:32] if nickname else None
        try:
            await member.edit(nick=nickname, reason=f"Nickname changed by {ctx.author}")
        except discord.Forbidden:
            await ctx.send(embed=error_embed("Nickname", "PHPelefant cannot edit this member's nickname."))
            return
        async with session_scope(self.bot.session_factory) as session:
            await log_action(session, ctx.guild.id, "nickname", member.id, ctx.author.id, nickname or "reset")
        await ctx.send(embed=table_embed("Nickname", [("user", member.mention), ("nickname", nickname or "reset")], status="success"))

    @commands.hybrid_command(name="addrole")
    @commands.guild_only()
    @guild_permissions_or_owner(manage_roles=True)
    async def addrole(self, ctx: commands.Context, member: discord.Member, role: discord.Role, *, reason: str = "No reason provided") -> None:
        ok, message = can_manage_role(ctx, role)
        if not ok:
            await ctx.send(embed=error_embed("Add Role", message))
            return
        try:
            await member.add_roles(role, reason=reason)
        except discord.Forbidden:
            await ctx.send(embed=error_embed("Add Role", "PHPelefant cannot assign that role."))
            return
        async with session_scope(self.bot.session_factory) as session:
            await log_action(session, ctx.guild.id, "addrole", member.id, ctx.author.id, reason, {"role_id": role.id})
        await ctx.send(embed=table_embed("Add Role", [("user", member.mention), ("role", role.mention), ("reason", reason)], status="success"))

    @commands.hybrid_command(name="removerole")
    @commands.guild_only()
    @guild_permissions_or_owner(manage_roles=True)
    async def removerole(self, ctx: commands.Context, member: discord.Member, role: discord.Role, *, reason: str = "No reason provided") -> None:
        ok, message = can_manage_role(ctx, role)
        if not ok:
            await ctx.send(embed=error_embed("Remove Role", message))
            return
        try:
            await member.remove_roles(role, reason=reason)
        except discord.Forbidden:
            await ctx.send(embed=error_embed("Remove Role", "PHPelefant cannot remove that role."))
            return
        async with session_scope(self.bot.session_factory) as session:
            await log_action(session, ctx.guild.id, "removerole", member.id, ctx.author.id, reason, {"role_id": role.id})
        await ctx.send(embed=table_embed("Remove Role", [("user", member.mention), ("role", role.mention), ("reason", reason)], status="success"))

    @commands.hybrid_command(name="warnconfig")
    @commands.guild_only()
    @guild_permissions_or_owner(manage_guild=True)
    async def warnconfig(self, ctx: commands.Context, action: str | None = None, timeout_minutes: int | None = None) -> None:
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
            if action is not None:
                normalized = action.casefold()
                if normalized not in {"timeout", "ban"}:
                    await ctx.send(embed=error_embed("Warn Config", "Action must be `timeout` or `ban`."))
                    return
                settings.warn_limit_action = normalized
            if timeout_minutes is not None:
                if not 1 <= timeout_minutes <= 40320:
                    await ctx.send(embed=error_embed("Warn Config", "Timeout minutes must be between 1 and 40320."))
                    return
                settings.warn_limit_timeout_minutes = timeout_minutes
        await ctx.send(
            embed=table_embed(
                "Warn Config",
                [
                    ("warning limit", settings.warning_limit),
                    ("limit action", settings.warn_limit_action),
                    ("timeout minutes", settings.warn_limit_timeout_minutes),
                ],
                status="success",
            )
        )

    @commands.hybrid_command(name="modlogs")
    @commands.guild_only()
    @guild_permissions_or_owner(moderate_members=True)
    async def modlogs(self, ctx: commands.Context, member: discord.Member | None = None, limit: int = 10) -> None:
        if not 1 <= limit <= 20:
            await ctx.send(embed=error_embed("Mod Logs", "Limit must be 1-20."))
            return
        async with session_scope(self.bot.session_factory) as session:
            query = select(ModerationLog).where(ModerationLog.guild_id == ctx.guild.id)
            if member is not None:
                query = query.where(ModerationLog.target_user_id == member.id)
            query = query.order_by(ModerationLog.id.desc()).limit(limit)
            rows = list(await session.scalars(query))
        lines = [
            f"#{row.id} {row.action} target={row.target_user_id or '-'} actor={row.actor_user_id or '-'} reason={row.reason or '-'}"
            for row in rows
        ]
        await ctx.send(embed=code_embed("Mod Logs", "\n".join(lines) if lines else "No moderation logs found."))


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(Moderation(bot))
