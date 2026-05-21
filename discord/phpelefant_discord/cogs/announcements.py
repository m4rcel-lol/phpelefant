from __future__ import annotations

from dataclasses import dataclass, field
import logging

import aiohttp
import discord
from discord.ext import commands, tasks
from sqlalchemy import delete, select

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.db.models import AnnouncementFeed
from phpelefant_discord.db.session import session_scope
from phpelefant_discord.services.announcements import (
    FeedEntry,
    discover_feed_links,
    feed_display_name,
    feed_url_candidates,
    looks_like_feed_payload,
    parse_feed_payload,
)
from phpelefant_discord.services.moderation import log_action
from phpelefant_discord.utils.formatting import embed, error_embed, success_embed, table_embed
from phpelefant_discord.utils.permissions import owner_or_guild_permissions

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FeedLookupResult:
    entry: FeedEntry | None
    resolved_url: str
    source_label: str
    error: str | None = None


@dataclass(slots=True)
class PollResult:
    checked: int = 0
    announced: int = 0
    errors: list[str] = field(default_factory=list)


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
                [(row.id, f"{row.name} -> <#{row.channel_id}> ({'on' if row.enabled else 'off'})\n{row.feed_url}") for row in rows],
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
        lookup = await self.fetch_latest_entry_with_url(feed_url)
        latest = lookup.entry
        stored_url = lookup.resolved_url if latest else feed_url
        display_name = feed_display_name(feed_url) if name == "PHPelefant Feed" else name
        async with session_scope(self.bot.session_factory) as session:
            row = AnnouncementFeed(
                guild_id=ctx.guild.id,
                channel_id=channel.id,
                name=display_name[:120],
                feed_url=stored_url[:2000],
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
        item.add_field(name="Source", value=lookup.source_label, inline=True)
        if stored_url != feed_url:
            item.add_field(name="Resolved URL", value=stored_url[:1024], inline=False)
        item.add_field(name="Latest Entry", value=latest.title if latest else lookup.error or "No entry found yet", inline=False)
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
        result = await self.poll_once(ctx.guild.id, only_feed_id=feed_id, force=True)
        item = success_embed("Announcement Feed", f"Checked feeds. Announced `{result.announced}` new post(s).")
        item.add_field(name="Checked", value=str(result.checked), inline=True)
        item.add_field(name="Failed", value=str(len(result.errors)), inline=True)
        if result.errors:
            item.add_field(name="Errors", value="\n".join(result.errors[:5])[:1024], inline=False)
        await ctx.send(embed=item)

    @tasks.loop(minutes=5)
    async def poll_feeds(self) -> None:
        await self.poll_once(None)

    @poll_feeds.before_loop
    async def before_poll_feeds(self) -> None:
        await self.bot.wait_until_ready()

    async def poll_once(self, guild_id: int | None, *, only_feed_id: int | None = None, force: bool = False) -> "PollResult":
        result = PollResult()
        async with session_scope(self.bot.session_factory) as session:
            query = select(AnnouncementFeed).where(AnnouncementFeed.enabled.is_(True))
            if guild_id is not None:
                query = query.where(AnnouncementFeed.guild_id == guild_id)
            if only_feed_id is not None:
                query = query.where(AnnouncementFeed.id == only_feed_id)
            feeds = list(await session.scalars(query))
            for feed in feeds:
                result.checked += 1
                lookup = await self.fetch_latest_entry_with_url(feed.feed_url)
                latest = lookup.entry
                if latest is None:
                    result.errors.append(f"Feed {feed.id}: {lookup.error or 'No entries found.'}")
                    continue
                if lookup.resolved_url != feed.feed_url:
                    feed.feed_url = lookup.resolved_url[:2000]
                if latest.entry_id == feed.last_entry_id and not force:
                    continue
                channel = self.bot.get_channel(feed.channel_id)
                if not isinstance(channel, discord.TextChannel):
                    continue
                if feed.last_entry_id is not None or force:
                    try:
                        await channel.send(embed=self.feed_embed(feed, latest))
                        result.announced += 1
                    except discord.DiscordException:
                        logger.exception("Failed to send announcement feed %s", feed.id)
                feed.last_entry_id = latest.entry_id
        return result

    async def fetch_latest_entry(self, feed_url: str) -> FeedEntry | None:
        return (await self.fetch_latest_entry_with_url(feed_url)).entry

    async def fetch_latest_entry_with_url(self, feed_url: str) -> FeedLookupResult:
        candidates = feed_url_candidates(feed_url, self.bot.settings.rsshub_base_url)
        if not candidates:
            return FeedLookupResult(None, feed_url, "Invalid URL", "Feed URL must be a valid http(s) URL.")
        last_error: str | None = None
        try:
            async with aiohttp.ClientSession() as session:
                index = 0
                while index < len(candidates):
                    candidate = candidates[index]
                    index += 1
                    try:
                        async with session.get(candidate.url, timeout=15, headers={"User-Agent": "PHPelefant Discord Bot"}) as response:
                            if response.status in {401, 403, 404, 410}:
                                last_error = f"{candidate.label} returned HTTP {response.status}."
                                continue
                            response.raise_for_status()
                            text = await response.text()
                            content_type = response.headers.get("Content-Type", "")
                            response_url = str(response.url)
                    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
                        last_error = f"{candidate.label} failed: {type(exc).__name__}."
                        continue

                    if looks_like_feed_payload(text, content_type):
                        entries = parse_feed_payload(text, content_type)
                        if entries:
                            return FeedLookupResult(entries[0], response_url, candidate.label)
                        last_error = f"{candidate.label} had no feed entries."
                        continue

                    discovered = discover_feed_links(response_url, text)
                    for discovered_candidate in discovered:
                        if all(existing.url != discovered_candidate.url for existing in candidates):
                            candidates.append(discovered_candidate)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return FeedLookupResult(None, feed_url, "Fetch failed", "Feed could not be fetched.")
        return FeedLookupResult(None, feed_url, "No feed found", last_error or "No RSS, Atom, JSON, or supported profile feed was found.")

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
