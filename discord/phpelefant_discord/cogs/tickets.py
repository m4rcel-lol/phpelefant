from __future__ import annotations

import asyncio
from io import BytesIO

import discord
from discord.ext import commands

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.db.models import Ticket, TicketConfig
from phpelefant_discord.db.session import session_scope
from phpelefant_discord.services.moderation import log_action
from phpelefant_discord.services.tickets import (
    build_ticket_transcript,
    get_or_create_ticket_config,
    open_ticket_for_channel,
    open_ticket_for_user,
    parse_ticket_categories,
    serialize_ticket_categories,
    ticket_channel_name,
    utcnow,
)
from phpelefant_discord.utils.formatting import (
    decorate_embed,
    embed,
    error_embed,
    infer_status,
    success_embed,
    table_embed,
    warning_embed,
)
from phpelefant_discord.utils.permissions import owner_or_guild_permissions

PANEL_CUSTOM_ID = "phpelefant:tickets:open"
CLOSE_CUSTOM_ID = "phpelefant:tickets:close"
CLAIM_CUSTOM_ID = "phpelefant:tickets:claim"
TRANSCRIPT_CUSTOM_ID = "phpelefant:tickets:transcript"


class TicketCategorySelect(discord.ui.Select):
    def __init__(self, bot: PHPelefantBot, categories: list[str] | None = None) -> None:
        self.bot = bot
        values = categories or ["General Support", "Billing", "Bug Report", "Staff Report", "Appeal"]
        options = [
            discord.SelectOption(
                label=category[:100],
                value=category[:100],
                description=f"Open a {category[:70]} ticket",
            )
            for category in values[:25]
        ]
        super().__init__(
            placeholder="Choose a ticket category",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=PANEL_CUSTOM_ID,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        cog = self.bot.get_cog("Tickets")
        if not isinstance(cog, Tickets):
            await interaction.response.send_message(embed=error_embed("Tickets", "Ticket system is not loaded."), ephemeral=True)
            return
        category = self.values[0]
        await cog.open_ticket_from_interaction(interaction, category, f"{category} ticket opened from panel")


class TicketPanelView(discord.ui.View):
    def __init__(self, bot: PHPelefantBot, categories: list[str] | None = None) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(TicketCategorySelect(bot, categories))


class TicketChannelView(discord.ui.View):
    def __init__(self, bot: PHPelefantBot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id=CLOSE_CUSTOM_ID)
    async def close_ticket(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        cog = self.bot.get_cog("Tickets")
        if not isinstance(cog, Tickets):
            await interaction.response.send_message(embed=error_embed("Tickets", "Ticket system is not loaded."), ephemeral=True)
            return
        await cog.close_ticket_from_interaction(interaction, "Closed with ticket button")

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.secondary, custom_id=CLAIM_CUSTOM_ID)
    async def claim_ticket(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        cog = self.bot.get_cog("Tickets")
        if not isinstance(cog, Tickets):
            await interaction.response.send_message(embed=error_embed("Tickets", "Ticket system is not loaded."), ephemeral=True)
            return
        await cog.claim_ticket_from_interaction(interaction)

    @discord.ui.button(label="Transcript", style=discord.ButtonStyle.secondary, custom_id=TRANSCRIPT_CUSTOM_ID)
    async def transcript_ticket(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        cog = self.bot.get_cog("Tickets")
        if not isinstance(cog, Tickets):
            await interaction.response.send_message(embed=error_embed("Tickets", "Ticket system is not loaded."), ephemeral=True)
            return
        await cog.transcript_from_interaction(interaction)


class Tickets(commands.Cog):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot

    @commands.hybrid_group(name="ticket", aliases=["tickets"], fallback="open")
    @commands.guild_only()
    async def ticket(self, ctx: commands.Context, *, reason: str = "No reason provided") -> None:
        await self.open_ticket_from_context(ctx, "General Support", reason)

    @commands.hybrid_command(name="ticketsetup")
    @commands.guild_only()
    @owner_or_guild_permissions(manage_guild=True)
    async def ticketsetup(
        self,
        ctx: commands.Context,
        category: discord.CategoryChannel | None = None,
        log_channel: discord.TextChannel | None = None,
        staff_role: discord.Role | None = None,
    ) -> None:
        await self.configure(ctx, category, log_channel, staff_role)

    @ticket.command(name="setup")
    @owner_or_guild_permissions(manage_guild=True)
    async def ticket_setup(
        self,
        ctx: commands.Context,
        category: discord.CategoryChannel | None = None,
        log_channel: discord.TextChannel | None = None,
        staff_role: discord.Role | None = None,
    ) -> None:
        await self.configure(ctx, category, log_channel, staff_role)

    @ticket.command(name="panel")
    @owner_or_guild_permissions(manage_guild=True)
    async def ticket_panel(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel | None = None,
        *,
        description: str = "Open a private support ticket and the server team will help you there.",
    ) -> None:
        target = channel or ctx.channel
        if not isinstance(target, discord.TextChannel):
            await ctx.send(embed=error_embed("Tickets", "Ticket panels can only be posted in text channels."))
            return

        panel = embed(
            "Support Tickets",
            description[:3500],
            status="info",
        )
        panel.add_field(name="Private Channel", value="Each ticket creates a dedicated private channel.", inline=False)
        panel.add_field(name="Staff Workflow", value="Staff can claim, add members, create transcripts, and close tickets.", inline=False)
        async with session_scope(self.bot.session_factory) as session:
            config = await get_or_create_ticket_config(session, ctx.guild.id)
            categories = parse_ticket_categories(config.ticket_categories)

        panel.add_field(name="Choose A Category", value="Use the dropdown below and PHPelefant will create a private channel for you.", inline=False)
        panel.add_field(name="Available Categories", value=", ".join(f"`{category}`" for category in categories), inline=False)

        message = await target.send(embed=panel, view=TicketPanelView(self.bot, categories))
        async with session_scope(self.bot.session_factory) as session:
            config = await get_or_create_ticket_config(session, ctx.guild.id)
            config.panel_channel_id = target.id
            config.panel_message_id = message.id
            await log_action(session, ctx.guild.id, "ticket_panel", None, ctx.author.id, f"channel={target.id}")
        await ctx.send(embed=success_embed("Tickets", f"Ticket panel posted in {target.mention}."))

    @ticket.command(name="close")
    async def ticket_close(self, ctx: commands.Context, *, reason: str = "Closed by command") -> None:
        await self.close_ticket_from_context(ctx, reason)

    @ticket.command(name="claim")
    async def ticket_claim(self, ctx: commands.Context) -> None:
        await self.claim_ticket_from_context(ctx)

    @ticket.command(name="add")
    async def ticket_add(self, ctx: commands.Context, member: discord.Member) -> None:
        await self.update_member_access(ctx, member, allow=True)

    @ticket.command(name="remove")
    async def ticket_remove(self, ctx: commands.Context, member: discord.Member) -> None:
        await self.update_member_access(ctx, member, allow=False)

    @ticket.command(name="transcript")
    async def ticket_transcript(self, ctx: commands.Context) -> None:
        await self.send_transcript_from_context(ctx)

    @ticket.command(name="settings")
    async def ticket_settings(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            config = await get_or_create_ticket_config(session, ctx.guild.id)
        await ctx.send(embed=self.settings_embed(ctx.guild, config))

    @ticket.command(name="categories")
    @owner_or_guild_permissions(manage_guild=True)
    async def ticket_categories(self, ctx: commands.Context, *, categories: str | None = None) -> None:
        async with session_scope(self.bot.session_factory) as session:
            config = await get_or_create_ticket_config(session, ctx.guild.id)
            if categories is not None:
                parsed = parse_ticket_categories(categories)
                config.ticket_categories = serialize_ticket_categories(parsed)
                await log_action(session, ctx.guild.id, "ticket_categories", None, ctx.author.id, config.ticket_categories)
            current = parse_ticket_categories(config.ticket_categories)
        await ctx.send(
            embed=table_embed(
                "Ticket Categories",
                [(str(index), category) for index, category in enumerate(current, start=1)],
                description="Use `ticket categories General Support | Billing | Bug Report` to replace the dropdown choices.",
            )
        )

    @ticket.command(name="enable")
    @owner_or_guild_permissions(manage_guild=True)
    async def ticket_enable(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            config = await get_or_create_ticket_config(session, ctx.guild.id)
            config.enabled = True
        await ctx.send(embed=success_embed("Tickets", "Ticket creation is enabled."))

    @ticket.command(name="disable")
    @owner_or_guild_permissions(manage_guild=True)
    async def ticket_disable(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            config = await get_or_create_ticket_config(session, ctx.guild.id)
            config.enabled = False
        await ctx.send(embed=warning_embed("Tickets", "Ticket creation is disabled."))

    async def configure(
        self,
        ctx: commands.Context,
        category: discord.CategoryChannel | None,
        log_channel: discord.TextChannel | None,
        staff_role: discord.Role | None,
    ) -> None:
        resolved_staff_role = await self.resolve_or_create_staff_role(ctx, staff_role)
        if resolved_staff_role is None:
            return
        async with session_scope(self.bot.session_factory) as session:
            config = await get_or_create_ticket_config(session, ctx.guild.id)
            if category is not None:
                config.category_id = category.id
            if log_channel is not None:
                config.log_channel_id = log_channel.id
            config.staff_role_id = resolved_staff_role.id
            await log_action(session, ctx.guild.id, "ticket_setup", None, ctx.author.id, None)
        await ctx.send(embed=self.settings_embed(ctx.guild, config, title="Ticket Setup Updated"))

    async def resolve_or_create_staff_role(self, ctx: commands.Context, staff_role: discord.Role | None) -> discord.Role | None:
        if staff_role is not None:
            return staff_role
        existing = discord.utils.get(ctx.guild.roles, name="Ticket Staff")
        if existing is not None:
            return existing
        me = ctx.guild.me or (ctx.guild.get_member(self.bot.user.id) if self.bot.user else None)
        if me is None or not me.guild_permissions.manage_roles:
            await ctx.send(embed=error_embed("Tickets", "Pass an existing staff role or give PHPelefant Manage Roles so it can create `Ticket Staff`."))
            return None
        try:
            return await ctx.guild.create_role(
                name="Ticket Staff",
                mentionable=True,
                reason=f"PHPelefant ticket setup by {ctx.author} ({ctx.author.id})",
            )
        except discord.Forbidden:
            await ctx.send(embed=error_embed("Tickets", "PHPelefant cannot create the Ticket Staff role because of missing permissions or role position."))
            return None
        except discord.HTTPException:
            await ctx.send(embed=error_embed("Tickets", "Discord rejected the Ticket Staff role creation request."))
            return None

    def settings_embed(self, guild: discord.Guild, config: TicketConfig, *, title: str = "Ticket Settings") -> discord.Embed:
        category = guild.get_channel(config.category_id) if config.category_id else None
        log_channel = guild.get_channel(config.log_channel_id) if config.log_channel_id else None
        staff_role = guild.get_role(config.staff_role_id) if config.staff_role_id else None
        return table_embed(
            title,
            [
                ("enabled", config.enabled),
                ("category", category.mention if isinstance(category, discord.CategoryChannel) else "server root"),
                ("log channel", log_channel.mention if isinstance(log_channel, discord.TextChannel) else "not set"),
                ("staff role", staff_role.mention if staff_role else "not set"),
                ("dropdown categories", ", ".join(parse_ticket_categories(config.ticket_categories))),
                ("ticket counter", config.ticket_counter),
                ("transcript limit", config.transcript_limit),
            ],
        )

    def is_owner(self, user_id: int) -> bool:
        return user_id == self.bot.settings.bot_owner_id

    def is_ticket_staff(self, member: discord.Member, config: TicketConfig) -> bool:
        if self.is_owner(member.id):
            return True
        permissions = member.guild_permissions
        if permissions.administrator or permissions.manage_channels or permissions.manage_guild or permissions.moderate_members:
            return True
        return bool(config.staff_role_id and any(role.id == config.staff_role_id for role in member.roles))

    def ticket_overwrites(
        self,
        guild: discord.Guild,
        opener: discord.Member,
        staff_role: discord.Role | None,
    ) -> dict[discord.Role | discord.Member, discord.PermissionOverwrite]:
        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            opener: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
        }
        if guild.me is not None:
            overwrites[guild.me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True,
            )
        if staff_role is not None:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            )
        return overwrites

    async def create_ticket_channel(
        self,
        guild: discord.Guild,
        opener: discord.Member,
        ticket_category: str,
        reason: str,
    ) -> tuple[discord.TextChannel, Ticket, bool]:
        async with session_scope(self.bot.session_factory) as session:
            config = await get_or_create_ticket_config(session, guild.id)
            if not config.enabled and not self.is_owner(opener.id):
                raise commands.CommandError("Ticket creation is disabled in this server.")

            existing = await open_ticket_for_user(session, guild.id, opener.id)
            if existing is not None and existing.channel_id:
                channel = guild.get_channel(existing.channel_id)
                if isinstance(channel, discord.TextChannel):
                    return channel, existing, False
                existing.status = "closed"
                existing.closed_at = utcnow()
                existing.close_reason = "Ticket channel was missing."

            config.ticket_counter += 1
            number = config.ticket_counter
            ticket = Ticket(
                guild_id=guild.id,
                ticket_number=number,
                opener_id=opener.id,
                category=ticket_category[:64],
                subject=reason[:1000],
                status="open",
            )
            session.add(ticket)
            await session.flush()

            category = guild.get_channel(config.category_id) if config.category_id else None
            if not isinstance(category, discord.CategoryChannel):
                category = None
            staff_role = guild.get_role(config.staff_role_id) if config.staff_role_id else None
            overwrites = self.ticket_overwrites(guild, opener, staff_role)
            channel = await guild.create_text_channel(
                name=ticket_channel_name(ticket_category, number, opener),
                category=category,
                overwrites=overwrites,
                topic=f"PHPelefant ticket #{number} | category={ticket_category[:64]} | opener={opener.id} | ticket_id={ticket.id}",
                reason=f"Ticket opened by {opener} ({opener.id})",
            )
            ticket.channel_id = channel.id
            await log_action(session, guild.id, "ticket_open", opener.id, opener.id, reason, {"ticket_id": ticket.id, "channel_id": channel.id})

        intro = embed(
            f"{ticket.category} Ticket #{ticket.ticket_number:04d}",
            f"{opener.mention}, your ticket has been opened. Describe the issue clearly and include screenshots or IDs when useful.",
            status="success",
        )
        intro.add_field(name="Opened By", value=f"{opener.mention}\n`{opener.id}`", inline=True)
        intro.add_field(name="Category", value=ticket.category, inline=True)
        intro.add_field(name="Subject", value=reason[:1024], inline=False)
        intro.add_field(name="Controls", value="Use the buttons below or `/ticket close`, `/ticket claim`, `/ticket transcript`.", inline=False)
        mention = staff_role.mention if staff_role is not None else None
        if mention:
            await channel.send(
                content=mention,
                allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
            )
        await channel.send(embed=intro, view=TicketChannelView(self.bot))
        return channel, ticket, True

    async def open_ticket_from_context(self, ctx: commands.Context, ticket_category: str, reason: str) -> None:
        if not isinstance(ctx.author, discord.Member):
            await ctx.send(embed=error_embed("Tickets", "Tickets can only be opened inside a server."))
            return
        try:
            channel, ticket, created = await self.create_ticket_channel(ctx.guild, ctx.author, ticket_category, reason)
        except (discord.Forbidden, discord.HTTPException):
            await ctx.send(embed=error_embed("Tickets", "PHPelefant could not create the ticket channel. Check Manage Channels permission and role position."))
            return
        except commands.CommandError as exc:
            await ctx.send(embed=error_embed("Tickets", str(exc)))
            return
        status = "created" if created else "already open"
        await ctx.send(embed=table_embed("Ticket", [("status", status), ("category", ticket.category), ("ticket", f"#{ticket.ticket_number:04d}"), ("channel", channel.mention)], status="success" if created else "warning"))

    async def open_ticket_from_interaction(self, interaction: discord.Interaction, ticket_category: str, reason: str) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(embed=error_embed("Tickets", "Tickets can only be opened inside a server."), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            channel, ticket, created = await self.create_ticket_channel(interaction.guild, interaction.user, ticket_category, reason)
        except (discord.Forbidden, discord.HTTPException):
            await interaction.followup.send(embed=error_embed("Tickets", "PHPelefant could not create the ticket channel. Check Manage Channels permission and role position."), ephemeral=True)
            return
        except commands.CommandError as exc:
            await interaction.followup.send(embed=error_embed("Tickets", str(exc)), ephemeral=True)
            return
        status = "created" if created else "already open"
        await interaction.followup.send(
            embed=table_embed("Ticket", [("status", status), ("category", ticket.category), ("ticket", f"#{ticket.ticket_number:04d}"), ("channel", channel.mention)], status="success" if created else "warning"),
            ephemeral=True,
        )

    async def require_current_ticket(self, guild: discord.Guild, channel: discord.abc.GuildChannel) -> tuple[Ticket, TicketConfig]:
        async with session_scope(self.bot.session_factory) as session:
            config = await get_or_create_ticket_config(session, guild.id)
            ticket = await open_ticket_for_channel(session, guild.id, channel.id)
            if ticket is None:
                raise commands.CommandError("This channel is not an open ticket.")
            return ticket, config

    async def close_ticket_from_context(self, ctx: commands.Context, reason: str) -> None:
        if not isinstance(ctx.channel, discord.TextChannel) or not isinstance(ctx.author, discord.Member):
            await ctx.send(embed=error_embed("Tickets", "Use this inside an open ticket channel."))
            return
        try:
            ticket, config = await self.require_current_ticket(ctx.guild, ctx.channel)
        except commands.CommandError as exc:
            await ctx.send(embed=error_embed("Tickets", str(exc)))
            return
        if ticket.opener_id != ctx.author.id and not self.is_ticket_staff(ctx.author, config):
            await ctx.send(embed=error_embed("Tickets", "Only the ticket opener or staff can close this ticket."))
            return
        await self.close_ticket(ctx.channel, ticket, config, ctx.author, reason)

    async def close_ticket_from_interaction(self, interaction: discord.Interaction, reason: str) -> None:
        if interaction.guild is None or not isinstance(interaction.channel, discord.TextChannel) or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(embed=error_embed("Tickets", "Use this inside an open ticket channel."), ephemeral=True)
            return
        try:
            ticket, config = await self.require_current_ticket(interaction.guild, interaction.channel)
        except commands.CommandError as exc:
            await interaction.response.send_message(embed=error_embed("Tickets", str(exc)), ephemeral=True)
            return
        if ticket.opener_id != interaction.user.id and not self.is_ticket_staff(interaction.user, config):
            await interaction.response.send_message(embed=error_embed("Tickets", "Only the ticket opener or staff can close this ticket."), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.close_ticket(interaction.channel, ticket, config, interaction.user, reason)
        await interaction.followup.send(embed=success_embed("Tickets", "Ticket is closing."), ephemeral=True)

    async def close_ticket(
        self,
        channel: discord.TextChannel,
        ticket: Ticket,
        config: TicketConfig,
        actor: discord.Member | discord.User,
        reason: str,
    ) -> None:
        transcript = await build_ticket_transcript(channel, ticket, config.transcript_limit)
        closed_at = utcnow()
        staff_role = channel.guild.get_role(config.staff_role_id) if config.staff_role_id else None
        opener = channel.guild.get_member(ticket.opener_id) or self.bot.get_user(ticket.opener_id)
        if opener is None:
            try:
                opener = await self.bot.fetch_user(ticket.opener_id)
            except discord.DiscordException:
                opener = None

        user_dm_sent = False
        staff_dm_sent = False
        user_summary = table_embed(
            "Your Ticket Was Closed",
            [
                ("server", channel.guild.name),
                ("ticket", f"#{ticket.ticket_number:04d}"),
                ("category", ticket.category),
                ("closed by", f"{actor} ({actor.id})"),
                ("reason", reason),
                ("closed at", closed_at.strftime("%Y-%m-%d %H:%M UTC")),
            ],
            status="warning",
            description="A copy of the transcript is attached below.",
        )
        if opener is not None:
            try:
                await opener.send(
                    embed=user_summary,
                    file=discord.File(BytesIO(transcript), filename=f"ticket-{ticket.ticket_number:04d}-transcript.txt"),
                )
                user_dm_sent = True
            except discord.DiscordException:
                user_dm_sent = False

        if actor.id != ticket.opener_id:
            try:
                staff_summary = table_embed(
                    "Ticket Transcript Copy",
                    [
                        ("server", channel.guild.name),
                        ("ticket", f"#{ticket.ticket_number:04d}"),
                        ("category", ticket.category),
                        ("opener", ticket.opener_id),
                        ("reason", reason),
                    ],
                    status="warning",
                    description="You closed this ticket. A transcript copy is attached.",
                )
                await actor.send(
                    embed=staff_summary,
                    file=discord.File(BytesIO(transcript), filename=f"ticket-{ticket.ticket_number:04d}-transcript.txt"),
                )
                staff_dm_sent = True
            except discord.DiscordException:
                staff_dm_sent = False

        log_channel = channel.guild.get_channel(config.log_channel_id) if config.log_channel_id else None
        if isinstance(log_channel, discord.TextChannel):
            log = table_embed(
                "Ticket Closed",
                [
                    ("ticket", f"#{ticket.ticket_number:04d}"),
                    ("category", ticket.category),
                    ("opener", ticket.opener_id),
                    ("closed by", f"{actor} ({actor.id})"),
                    ("reason", reason),
                    ("user dm", "sent" if user_dm_sent else "failed"),
                    ("staff dm", "sent" if staff_dm_sent else "not sent"),
                ],
                status="warning",
            )
            await log_channel.send(
                content=staff_role.mention if staff_role else None,
                embed=log,
                file=discord.File(BytesIO(transcript), filename=f"ticket-{ticket.ticket_number:04d}-transcript.txt"),
                allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
            )

        async with session_scope(self.bot.session_factory) as session:
            row = await session.get(Ticket, ticket.id)
            if row is not None:
                row.status = "closed"
                row.closed_by_id = actor.id
                row.close_reason = reason[:1000]
                row.closed_at = closed_at
            await log_action(
                session,
                channel.guild.id,
                "ticket_close",
                ticket.opener_id,
                actor.id,
                reason,
                {
                    "ticket_id": ticket.id,
                    "channel_id": channel.id,
                    "user_dm_sent": user_dm_sent,
                    "staff_dm_sent": staff_dm_sent,
                },
            )

        closing = warning_embed("Ticket Closing", "Transcript saved. This channel will be deleted in 5 seconds.")
        closing.add_field(name="Closed By", value=f"{actor} (`{actor.id}`)", inline=True)
        closing.add_field(name="Category", value=ticket.category, inline=True)
        closing.add_field(name="Reason", value=reason[:1024], inline=False)
        closing.add_field(name="User DM", value="Sent" if user_dm_sent else "Failed or closed", inline=True)
        closing.add_field(name="Staff Copy", value="Sent" if staff_dm_sent else "Log channel only", inline=True)
        await channel.send(embed=closing)
        asyncio.create_task(self.delete_channel_later(channel))

    async def delete_channel_later(self, channel: discord.TextChannel) -> None:
        await asyncio.sleep(5)
        try:
            await channel.delete(reason="PHPelefant ticket closed")
        except discord.DiscordException:
            pass

    async def claim_ticket_from_context(self, ctx: commands.Context) -> None:
        if not isinstance(ctx.channel, discord.TextChannel) or not isinstance(ctx.author, discord.Member):
            await ctx.send(embed=error_embed("Tickets", "Use this inside an open ticket channel."))
            return
        await self.claim_ticket(ctx.channel, ctx.author, ctx.send)

    async def claim_ticket_from_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.channel, discord.TextChannel) or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(embed=error_embed("Tickets", "Use this inside an open ticket channel."), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)

        async def responder(*, embed: discord.Embed) -> None:
            decorate_embed(embed, None, status=infer_status(embed))
            await interaction.followup.send(embed=embed, ephemeral=True)

        await self.claim_ticket(interaction.channel, interaction.user, responder)

    async def claim_ticket(self, channel: discord.TextChannel, actor: discord.Member, responder) -> None:
        try:
            ticket, config = await self.require_current_ticket(channel.guild, channel)
        except commands.CommandError as exc:
            await responder(embed=error_embed("Tickets", str(exc)))
            return
        if not self.is_ticket_staff(actor, config):
            await responder(embed=error_embed("Tickets", "Only ticket staff can claim tickets."))
            return
        async with session_scope(self.bot.session_factory) as session:
            row = await session.get(Ticket, ticket.id)
            if row is not None:
                row.claimed_by_id = actor.id
            await log_action(session, channel.guild.id, "ticket_claim", ticket.opener_id, actor.id, None, {"ticket_id": ticket.id})
        await channel.send(embed=success_embed("Ticket Claimed", f"{actor.mention} claimed this ticket."))
        await responder(embed=success_embed("Tickets", "Ticket claimed."))

    async def update_member_access(self, ctx: commands.Context, member: discord.Member, *, allow: bool) -> None:
        if not isinstance(ctx.channel, discord.TextChannel) or not isinstance(ctx.author, discord.Member):
            await ctx.send(embed=error_embed("Tickets", "Use this inside an open ticket channel."))
            return
        try:
            ticket, config = await self.require_current_ticket(ctx.guild, ctx.channel)
        except commands.CommandError as exc:
            await ctx.send(embed=error_embed("Tickets", str(exc)))
            return
        if not self.is_ticket_staff(ctx.author, config):
            await ctx.send(embed=error_embed("Tickets", "Only ticket staff can edit ticket access."))
            return
        overwrite = (
            discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True)
            if allow
            else None
        )
        await ctx.channel.set_permissions(member, overwrite=overwrite, reason=f"Ticket access {'added' if allow else 'removed'} by {ctx.author}")
        action = "ticket_add_member" if allow else "ticket_remove_member"
        async with session_scope(self.bot.session_factory) as session:
            await log_action(session, ctx.guild.id, action, member.id, ctx.author.id, None, {"ticket_id": ticket.id, "channel_id": ctx.channel.id})
        await ctx.send(embed=success_embed("Tickets", f"{'Added' if allow else 'Removed'} {member.mention} {'to' if allow else 'from'} this ticket."))

    async def send_transcript_from_context(self, ctx: commands.Context) -> None:
        if not isinstance(ctx.channel, discord.TextChannel) or not isinstance(ctx.author, discord.Member):
            await ctx.send(embed=error_embed("Tickets", "Use this inside an open ticket channel."))
            return
        try:
            ticket, config = await self.require_current_ticket(ctx.guild, ctx.channel)
        except commands.CommandError as exc:
            await ctx.send(embed=error_embed("Tickets", str(exc)))
            return
        if ticket.opener_id != ctx.author.id and not self.is_ticket_staff(ctx.author, config):
            await ctx.send(embed=error_embed("Tickets", "Only the ticket opener or staff can create transcripts."))
            return
        transcript = await build_ticket_transcript(ctx.channel, ticket, config.transcript_limit)
        await ctx.send(
            embed=success_embed("Ticket Transcript", f"Transcript generated for ticket `#{ticket.ticket_number:04d}`."),
            file=discord.File(BytesIO(transcript), filename=f"ticket-{ticket.ticket_number:04d}-transcript.txt"),
        )

    async def transcript_from_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(interaction.channel, discord.TextChannel) or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(embed=error_embed("Tickets", "Use this inside an open ticket channel."), ephemeral=True)
            return
        try:
            ticket, config = await self.require_current_ticket(interaction.guild, interaction.channel)
        except commands.CommandError as exc:
            await interaction.response.send_message(embed=error_embed("Tickets", str(exc)), ephemeral=True)
            return
        if ticket.opener_id != interaction.user.id and not self.is_ticket_staff(interaction.user, config):
            await interaction.response.send_message(embed=error_embed("Tickets", "Only the ticket opener or staff can create transcripts."), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        transcript = await build_ticket_transcript(interaction.channel, ticket, config.transcript_limit)
        await interaction.followup.send(
            embed=success_embed("Ticket Transcript", f"Transcript generated for ticket `#{ticket.ticket_number:04d}`."),
            file=discord.File(BytesIO(transcript), filename=f"ticket-{ticket.ticket_number:04d}-transcript.txt"),
            ephemeral=True,
        )


async def setup(bot: PHPelefantBot) -> None:
    cog = Tickets(bot)
    await bot.add_cog(cog)
    bot.add_view(TicketPanelView(bot))
    bot.add_view(TicketChannelView(bot))
