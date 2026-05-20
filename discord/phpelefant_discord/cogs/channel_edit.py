from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.db.models import BlacklistedGuild, BlacklistedUser
from phpelefant_discord.db.session import session_scope
from phpelefant_discord.services.moderation import log_action
from phpelefant_discord.utils.channel_names import (
    ChannelEditOptions,
    VALID_EDIT_TYPES,
    parse_edit_options,
    transform_channel_name,
)
from phpelefant_discord.utils.formatting import decorate_embed, error_embed, infer_status, table_embed, warning_embed


def is_owner(bot: PHPelefantBot, user_id: int) -> bool:
    return user_id == bot.settings.bot_owner_id


def manageable_channel_targets(guild: discord.Guild, target_type: str) -> list[discord.abc.GuildChannel]:
    if target_type == "categories":
        return list(guild.categories)
    if target_type == "text":
        return list(guild.text_channels)
    if target_type == "voice":
        return list(guild.voice_channels)
    if target_type == "stage":
        return list(guild.stage_channels)
    if target_type == "forum":
        return list(getattr(guild, "forums", []))

    channels = [channel for channel in guild.channels if not isinstance(channel, discord.CategoryChannel)]
    if target_type == "all":
        return [*guild.categories, *channels]
    return channels


class ChannelEdit(commands.Cog):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot

    @commands.command(name="edit")
    @commands.guild_only()
    async def edit_prefix(self, ctx: commands.Context, *, options: str = "") -> None:
        if not options.strip():
            await ctx.send(
                embed=warning_embed(
                    "Channel Editor",
                    "Use `edit type:channels deletechars:true deletetoindex:3 keepemojis:true surroundsymbol1:[ surroundsymbol2:]`.",
                )
            )
            return
        try:
            parsed = parse_edit_options(options)
        except ValueError as exc:
            await ctx.send(embed=error_embed("Channel Editor", str(exc)))
            return
        await self.run_edit(ctx, parsed)

    @app_commands.command(name="edit", description="Bulk edit channel/category names.")
    @app_commands.rename(target_type="type")
    @app_commands.describe(
        target_type="channels, categories, all, text, voice, stage, or forum",
        deletechars="Delete characters from the start of each target name.",
        deletetoindex="Number of characters to delete from the start after preserved emojis.",
        keepemojis="Keep leading unicode/custom emojis before deleting characters.",
        surroundsymbol1="Text to place before the final channel/category name.",
        surroundsymbol2="Text to place after the final channel/category name.",
        sourroundsymbol2="Typo-compatible alias for surroundsymbol2.",
        match="Only edit names containing this text.",
        limit="Maximum targets to edit, up to 100.",
        preview="Show what would change without editing Discord.",
    )
    async def edit_slash(
        self,
        interaction: discord.Interaction,
        target_type: str = "channels",
        deletechars: bool = False,
        deletetoindex: app_commands.Range[int, 0, 64] = 0,
        keepemojis: bool = True,
        surroundsymbol1: str = "",
        surroundsymbol2: str = "",
        sourroundsymbol2: str = "",
        match: str | None = None,
        limit: app_commands.Range[int, 1, 100] = 50,
        preview: bool = False,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(embed=error_embed("Channel Editor", "Use this in a server."), ephemeral=True)
            return
        normalized_type = target_type.casefold()
        if normalized_type not in VALID_EDIT_TYPES:
            await interaction.response.send_message(
                embed=error_embed("Channel Editor", f"type must be one of: {', '.join(sorted(VALID_EDIT_TYPES))}."),
                ephemeral=True,
            )
            return
        options = ChannelEditOptions(
            target_type=normalized_type,
            delete_chars=deletechars,
            delete_to_index=deletetoindex,
            keep_emojis=keepemojis,
            surround_symbol_1=surroundsymbol1,
            surround_symbol_2=surroundsymbol2 or sourroundsymbol2,
            match=match.casefold() if match else None,
            limit=limit,
            preview=preview,
        )
        await interaction.response.defer(thinking=True, ephemeral=True)
        ctx = await commands.Context.from_interaction(interaction)
        await self.run_edit(ctx, options, use_followup=True)

    async def run_edit(self, ctx: commands.Context, options: ChannelEditOptions, *, use_followup: bool = False) -> None:
        assert ctx.guild is not None
        author = ctx.author
        if not isinstance(author, discord.Member):
            await self.send(ctx, error_embed("Channel Editor", "Could not resolve your server member state."), use_followup)
            return
        if not (author.guild_permissions.manage_channels or is_owner(self.bot, author.id)):
            await self.send(ctx, error_embed("Channel Editor", "You need Manage Channels permission."), use_followup)
            return
        me = ctx.guild.me or (ctx.guild.get_member(self.bot.user.id) if self.bot.user else None)
        if me is None or not me.guild_permissions.manage_channels:
            await self.send(ctx, error_embed("Channel Editor", "PHPelefant needs Manage Channels permission."), use_followup)
            return
        async with session_scope(self.bot.session_factory) as session:
            if await session.get(BlacklistedUser, author.id) or await session.get(BlacklistedGuild, ctx.guild.id):
                await self.send(ctx, error_embed("Channel Editor", "This user or server is blocked from using PHPelefant."), use_followup)
                return

        raw_targets = manageable_channel_targets(ctx.guild, options.target_type)
        targets = [
            channel
            for channel in raw_targets
            if options.match is None or options.match in channel.name.casefold()
        ][: options.limit]

        if not targets:
            await self.send(ctx, warning_embed("Channel Editor", "No matching channels or categories were found."), use_followup)
            return

        changes: list[tuple[discord.abc.GuildChannel, str]] = []
        skipped = 0
        for channel in targets:
            new_name = transform_channel_name(channel.name, options)
            if new_name == channel.name:
                skipped += 1
                continue
            changes.append((channel, new_name))

        if not changes:
            await self.send(ctx, warning_embed("Channel Editor", f"No names changed. Skipped {skipped} unchanged target(s)."), use_followup)
            return

        preview_lines = [f"{channel.name} -> {new_name}" for channel, new_name in changes[:12]]
        if options.preview:
            await self.send(
                ctx,
                table_embed(
                    "Channel Editor Preview",
                    [
                        ("targets", len(targets)),
                        ("would edit", len(changes)),
                        ("skipped", skipped),
                        ("sample", "\n".join(preview_lines)),
                    ],
                    status="warning",
                ),
                use_followup,
            )
            return

        edited = 0
        failed: list[str] = []
        reason = f"PHPelefant bulk edit by {author} ({author.id})"
        for channel, new_name in changes:
            try:
                await channel.edit(name=new_name, reason=reason)
                edited += 1
            except discord.Forbidden:
                failed.append(f"{channel.name}: missing bot permission or role position")
            except discord.HTTPException as exc:
                failed.append(f"{channel.name}: Discord API error {exc.status}")

        async with session_scope(self.bot.session_factory) as session:
            await log_action(
                session,
                ctx.guild.id,
                "bulk_channel_edit",
                None,
                author.id,
                f"type={options.target_type}; edited={edited}; failed={len(failed)}",
                {
                    "target_type": options.target_type,
                    "delete_chars": options.delete_chars,
                    "delete_to_index": options.delete_to_index,
                    "keep_emojis": options.keep_emojis,
                    "match": options.match,
                    "limit": options.limit,
                },
            )

        fields: list[tuple[str, object]] = [
            ("edited", edited),
            ("failed", len(failed)),
            ("skipped", skipped),
            ("sample", "\n".join(preview_lines)),
        ]
        if failed:
            fields.append(("failures", "\n".join(failed[:8])))
        await self.send(ctx, table_embed("Channel Editor", fields, status="success" if edited else "warning"), use_followup)

    async def send(self, ctx: commands.Context, item: discord.Embed, use_followup: bool) -> None:
        decorate_embed(item, ctx, status=infer_status(item))
        if use_followup and ctx.interaction:
            await ctx.interaction.followup.send(embed=item, ephemeral=True)
            return
        await ctx.send(embed=item)


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(ChannelEdit(bot))
