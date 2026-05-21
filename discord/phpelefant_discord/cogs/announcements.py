from __future__ import annotations

import logging

import aiohttp
import discord
from discord.ext import commands, tasks
from sqlalchemy import delete, select

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.db.models import AnnouncementFeed
from phpelefant_discord.db.session import session_scope
from phpelefant_discord.services.announcements import FeedEntry, parse_feed_payload
from phpelefant_discord.services.moderation import log_action
from phpelefant_discord.utils.formatting import embed, error_embed, success_embed, table_embed
from phpelefant_discord.utils.permissions import owner_or_guild_permissions

logger = logging.getLogger(__name__)


class Announcements(commands.Cog):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot
        self.poll_feeds.start()

    def cog_unload(self) -> None:
        self.poll_feeds.cancel()

    @commands.hybrid_group(name="announcefeed", fallback="list")
    @commands.guild_only()
    @owner_or_guild_permissions(manage_guild=True)
    async def announcefeed(self, ctx: commands.Context) -> None:
        async with session_scope(self.bot.session_factory) as session:
            rows = list(await session.scalars(select(AnnouncementFeed).where(AnnouncementFeed.guild_id == ctx.guild.id)))
        await ctx.send(
            embed=table_embed(
                "Announcement Feeds",
                [(row.id, f"{row.name} -> <#{row.channel_id}> ({'on' if row.enabled else 'off'})") for row in rows],
                description="RSS, Atom, JSON feed, and Akkoma/Pleroma public status URLs can be polled for PHPelefant announcements.",
            )
        )

    @announcefeed.command(name="add")
    @owner_or_guild_permissions(manage_guild=True)
    async def announcefeed_add(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        feed_url: str,
        *,
        name: str = "PHPelefant Feed",
    ) -> None:
        latest = await self.fetch_latest_entry(feed_url)
        async with session_scope(self.bot.session_factory) as session:
            row = AnnouncementFeed(
                guild_id=ctx.guild.id,
                channel_id=channel.id,
                name=name[:120],
                feed_url=feed_url[:2000],
                last_entry_id=latest.entry_id if latest else None,
                created_by=ctx.author.id,
            )
            session.add(row)
            await session.flush()
            feed_id = row.id
            await log_action(session, ctx.guild.id, "announcefeed_add", None, ctx.author.id, feed_url)
        item = success_embed("Announcement Feed Added", "PHPelefant will announce new posts from this feed.")
        item.add_field(name="Feed ID", value=str(feed_id), inline=True)
        item.add_field(name="Channel", value=channel.mention, inline=True)
        item.add_field(name="Latest Entry", value=latest.title if latest else "No entry found yet", inline=False)
        await ctx.send(embed=item)

    @announcefeed.command(name="remove")
    @owner_or_guild_permissions(manage_guild=True)
    async def announcefeed_remove(self, ctx: commands.Context, feed_id: int) -> None:
        async with session_scope(self.bot.session_factory) as session:
            await session.execute(delete(AnnouncementFeed).where(AnnouncementFeed.guild_id == ctx.guild.id, AnnouncementFeed.id == feed_id))
            await log_action(session, ctx.guild.id, "announcefeed_remove", None, ctx.author.id, str(feed_id))
        await ctx.send(embed=success_embed("Announcement Feed", "Removed if present."))

    @announcefeed.command(name="check")
    @owner_or_guild_permissions(manage_guild=True)
    async def announcefeed_check(self, ctx: commands.Context, feed_id: int | None = None) -> None:
        count = await self.poll_once(ctx.guild.id, only_feed_id=feed_id, force=True)
        await ctx.send(embed=success_embed("Announcement Feed", f"Checked feeds. Announced `{count}` new post(s)."))

    @tasks.loop(minutes=5)
    async def poll_feeds(self) -> None:
        await self.poll_once(None)

    @poll_feeds.before_loop
    async def before_poll_feeds(self) -> None:
        await self.bot.wait_until_ready()

    async def poll_once(self, guild_id: int | None, *, only_feed_id: int | None = None, force: bool = False) -> int:
        announced = 0
        async with session_scope(self.bot.session_factory) as session:
            query = select(AnnouncementFeed).where(AnnouncementFeed.enabled.is_(True))
            if guild_id is not None:
                query = query.where(AnnouncementFeed.guild_id == guild_id)
            if only_feed_id is not None:
                query = query.where(AnnouncementFeed.id == only_feed_id)
            feeds = list(await session.scalars(query))
            for feed in feeds:
                latest = await self.fetch_latest_entry(feed.feed_url)
                if latest is None:
                    continue
                if latest.entry_id == feed.last_entry_id and not force:
                    continue
                channel = self.bot.get_channel(feed.channel_id)
                if not isinstance(channel, discord.TextChannel):
                    continue
                if feed.last_entry_id is not None or force:
                    try:
                        await channel.send(embed=self.feed_embed(feed, latest))
                        announced += 1
                    except discord.DiscordException:
                        logger.exception("Failed to send announcement feed %s", feed.id)
                feed.last_entry_id = latest.entry_id
        return announced

    async def fetch_latest_entry(self, feed_url: str) -> FeedEntry | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(feed_url, timeout=15, headers={"User-Agent": "PHPelefant Discord Bot"}) as response:
                    response.raise_for_status()
                    text = await response.text()
                    content_type = response.headers.get("Content-Type", "")
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return None
        entries = parse_feed_payload(text, content_type)
        return entries[0] if entries else None

    @staticmethod
    def feed_embed(feed: AnnouncementFeed, entry: FeedEntry) -> discord.Embed:
        item = embed(feed.name, entry.summary or "New post published.", status="info")
        item.add_field(name="Source", value=feed.feed_url[:1024], inline=False)
        if entry.url:
            item.add_field(name="Open Post", value=f"[Read post]({entry.url})", inline=False)
            item.url = entry.url
        item.set_author(name=f"PHPelefant Announcements - {feed.name}")
        return item


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(Announcements(bot))
