from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging

import discord
from discord.ext import commands

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.db.models import BlacklistedGuild, BlacklistedUser
from phpelefant_discord.db.session import session_scope
from phpelefant_discord.services.activity import mark_joined, record_message
from phpelefant_discord.services.antispam import AutoAction, SpamMemory, analyze_message, bad_words, is_whitelisted, whitelisted_domains
from phpelefant_discord.services.moderation import add_warning, log_action
from phpelefant_discord.services.settings import get_or_create_guild_settings, upsert_guild, upsert_user
from phpelefant_discord.services.stats import increment_stat
from phpelefant_discord.utils.formatting import code_embed, error_embed

logger = logging.getLogger(__name__)


class Events(commands.Cog):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot
        self.memory = SpamMemory()

    async def bot_check_once(self, ctx: commands.Context) -> bool:
        is_owner = ctx.author.id == self.bot.settings.bot_owner_id
        async with session_scope(self.bot.session_factory) as session:
            if not is_owner and await session.get(BlacklistedUser, ctx.author.id):
                await ctx.send(embed=code_embed("Blocked", "You are blocked from using PHPelefant."))
                return False
            if not is_owner and ctx.guild and await session.get(BlacklistedGuild, ctx.guild.id):
                return False
            if ctx.guild and ctx.command and ctx.command.cog_name in {"Fun", "Activity"}:
                settings = await get_or_create_guild_settings(session, ctx.guild.id, self.bot.settings)
                if settings.force_subscribe_enabled and not is_owner:
                    official_guild = self.bot.get_guild(settings.official_channel_id)
                    if official_guild is None:
                        await ctx.send(embed=code_embed("Force Subscribe", "Official server is not available to the bot."))
                        return False
                    if official_guild.get_member(ctx.author.id) is None:
                        await ctx.send(embed=code_embed("Force Subscribe", "Join the official PHPelefant server before using this command."))
                        return False
        return True

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        logger.info("Logged in as %s (%s)", self.bot.user, self.bot.user.id if self.bot.user else "unknown")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        if ctx.command and ctx.command.has_error_handler():
            return
        original = getattr(error, "original", error)
        title = "Command Error"
        message = "PHPelefant could not run that command."
        if isinstance(original, commands.MissingPermissions):
            message = "You do not have the required Discord permissions."
        elif isinstance(original, commands.BotMissingPermissions):
            message = "PHPelefant is missing required Discord permissions."
        elif isinstance(original, commands.MissingRequiredArgument):
            message = f"Missing required argument: `{original.param.name}`."
        elif isinstance(original, commands.BadArgument):
            message = "Invalid argument. Check the command format and try again."
        elif isinstance(original, commands.CheckFailure):
            message = "You are not allowed to use that command."
        elif isinstance(original, discord.Forbidden):
            message = "Discord rejected this because PHPelefant lacks permission or role position."
        elif isinstance(original, discord.HTTPException):
            message = "Discord rejected the request. Try again after checking permissions and arguments."
        else:
            logger.error(
                "Unhandled command error in %s",
                ctx.command,
                exc_info=(type(original), original, original.__traceback__) if isinstance(original, BaseException) else None,
            )
        try:
            await ctx.send(embed=error_embed(title, message))
        except discord.DiscordException:
            logger.exception("Failed to send command error response")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        async with session_scope(self.bot.session_factory) as session:
            await upsert_guild(session, guild, self.bot.settings)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        async with session_scope(self.bot.session_factory) as session:
            await upsert_user(session, member)
            await upsert_guild(session, member.guild, self.bot.settings)
            settings = await get_or_create_guild_settings(session, member.guild.id, self.bot.settings)
            await mark_joined(session, member.guild.id, member.id, member.joined_at)
        if settings.welcome_enabled:
            channel = member.guild.get_channel(settings.welcome_channel_id) if settings.welcome_channel_id else member.guild.system_channel
            if isinstance(channel, discord.TextChannel):
                text = render_template(settings.welcome_text, member, settings.rules_text)
                if "{rules}" not in settings.welcome_text:
                    text += f"\n\nRules:\n{settings.rules_text}"
                await channel.send(text)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        async with session_scope(self.bot.session_factory) as session:
            settings = await get_or_create_guild_settings(session, member.guild.id, self.bot.settings)
        if settings.goodbye_enabled:
            channel = member.guild.get_channel(settings.goodbye_channel_id) if settings.goodbye_channel_id else member.guild.system_channel
            if isinstance(channel, discord.TextChannel):
                await channel.send(render_template(settings.goodbye_text, member, settings.rules_text))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.guild is None:
            return
        async with session_scope(self.bot.session_factory) as session:
            if await session.get(BlacklistedUser, message.author.id) or await session.get(BlacklistedGuild, message.guild.id):
                return
            await upsert_user(session, message.author)
            await upsert_guild(session, message.guild, self.bot.settings)
            await increment_stat(session, "messages_processed")
            settings = await get_or_create_guild_settings(session, message.guild.id, self.bot.settings)
            if settings.activity_enabled and not message.content.startswith(self.bot.settings.command_prefix):
                await record_message(session, message.guild.id, message.author.id, self.bot.settings.xp_cooldown_seconds)
            await self.apply_antispam(message, session, settings)

    async def apply_antispam(self, message: discord.Message, session, settings) -> None:
        if not message.content or message.author.guild_permissions.manage_messages or message.author.id == self.bot.settings.bot_owner_id:
            return
        if await is_whitelisted(session, message.guild.id, message.author.id):
            return
        now = datetime.now(tz=UTC)
        flood, repeat = self.memory.update(message.guild.id, message.author.id, message.content, now, settings.flood_window_seconds)
        decision = analyze_message(
            text=message.content,
            settings=settings,
            bad_word_list=await bad_words(session, message.guild.id),
            trusted_domains=await whitelisted_domains(session, message.guild.id),
            flood_count=flood,
            repeat_count=repeat,
        )
        if decision.action is AutoAction.NONE:
            return
        try:
            await message.delete()
        except discord.DiscordException:
            pass
        await log_action(session, message.guild.id, f"auto_{decision.action.value}", message.author.id, None, decision.reason)
        if not isinstance(message.author, discord.Member):
            return
        if decision.action is AutoAction.WARN:
            count, auto = await add_warning(session, settings, message.author, self.bot.settings.bot_owner_id, f"Auto moderation: {decision.reason}")
            await message.channel.send(embed=code_embed("Auto Moderation", f"Auto-warning {message.author.id}: {count}/{settings.warning_limit}. {auto or ''}"))
        elif decision.action is AutoAction.TIMEOUT:
            await message.author.timeout(datetime.now(tz=UTC) + timedelta(hours=1), reason=f"Auto moderation: {decision.reason}")
            await message.channel.send(embed=code_embed("Auto Moderation", f"Timed out {message.author.id}: {decision.reason}"))
        elif decision.action is AutoAction.BAN:
            await message.author.ban(reason=f"Auto moderation: {decision.reason}")
            await message.channel.send(embed=code_embed("Auto Moderation", f"Banned {message.author.id}: {decision.reason}"))


def render_template(template: str, member: discord.Member, rules: str) -> str:
    return template.format(
        user=member.mention,
        username=str(member),
        server=member.guild.name,
        member_count=member.guild.member_count,
        rules=rules,
    )


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(Events(bot))
