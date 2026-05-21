from __future__ import annotations

import asyncio
import base64
from collections import deque
import contextlib
from dataclasses import dataclass
import random
import shutil
import subprocess
import time

import aiohttp
import discord
from discord.ext import commands

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.services.music import ffmpeg_header_options, normalized_headers, parse_spotify_resource, spotify_track_query
from phpelefant_discord.utils.formatting import embed, error_embed, success_embed, table_embed, truncate_text, warning_embed

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SPOTIFY_OEMBED_URL = "https://open.spotify.com/oembed"
STARTUP_FAILURE_SECONDS = 8
MAX_STARTUP_FAILURES = 3


@dataclass(slots=True)
class Track:
    title: str
    webpage_url: str
    stream_url: str
    requester_id: int
    source: str = "yt-dlp"
    duration: int | None = None
    thumbnail: str | None = None
    headers: dict[str, str] | None = None


class MusicState:
    def __init__(self) -> None:
        self.queue: deque[Track] = deque()
        self.current: Track | None = None
        self.loop_current = False
        self.volume = 0.75
        self.text_channel_id: int | None = None
        self.started_at: float | None = None
        self.consecutive_startup_failures = 0
        self.announce_task: asyncio.Task | None = None


class Music(commands.Cog):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot
        self.states: dict[int, MusicState] = {}

    def state(self, guild_id: int) -> MusicState:
        return self.states.setdefault(guild_id, MusicState())

    @commands.hybrid_group(name="music", invoke_without_command=True)
    @commands.guild_only()
    async def music(self, ctx: commands.Context) -> None:
        await self._nowplaying(ctx)

    @music.command(name="join")
    @commands.guild_only()
    async def music_join(self, ctx: commands.Context) -> None:
        await self._join(ctx)

    @music.command(name="play")
    @commands.guild_only()
    async def music_play(self, ctx: commands.Context, *, song_url: str) -> None:
        await self._play(ctx, song_url)

    @music.command(name="playlist")
    @commands.guild_only()
    async def music_playlist(self, ctx: commands.Context, *, playlist_url: str) -> None:
        await self._playlist(ctx, playlist_url)

    @music.command(name="pause")
    @commands.guild_only()
    async def music_pause(self, ctx: commands.Context) -> None:
        await self._pause(ctx)

    @music.command(name="resume")
    @commands.guild_only()
    async def music_resume(self, ctx: commands.Context) -> None:
        await self._resume(ctx)

    @music.command(name="stop")
    @commands.guild_only()
    async def music_stop(self, ctx: commands.Context) -> None:
        await self._stop(ctx)

    @music.command(name="skip")
    @commands.guild_only()
    async def music_skip(self, ctx: commands.Context, count: int = 1) -> None:
        await self._skip(ctx, count)

    @music.command(name="queue")
    @commands.guild_only()
    async def music_queue(self, ctx: commands.Context) -> None:
        await self._queue(ctx)

    @music.command(name="remove")
    @commands.guild_only()
    async def music_remove(self, ctx: commands.Context, position: int) -> None:
        await self._remove(ctx, position)

    @music.command(name="clear")
    @commands.guild_only()
    async def music_clear(self, ctx: commands.Context) -> None:
        await self._clear(ctx)

    @music.command(name="shuffle")
    @commands.guild_only()
    async def music_shuffle(self, ctx: commands.Context) -> None:
        await self._shuffle(ctx)

    @music.command(name="loop")
    @commands.guild_only()
    async def music_loop(self, ctx: commands.Context, value: str = "toggle") -> None:
        await self._loop(ctx, value)

    @music.command(name="volume")
    @commands.guild_only()
    async def music_volume(self, ctx: commands.Context, percent: int | None = None) -> None:
        await self._volume(ctx, percent)

    @music.command(name="nowplaying")
    @commands.guild_only()
    async def music_nowplaying(self, ctx: commands.Context) -> None:
        await self._nowplaying(ctx)

    @music.command(name="leave")
    @commands.guild_only()
    async def music_leave(self, ctx: commands.Context) -> None:
        await self._leave(ctx)

    @commands.command(name="join")
    @commands.guild_only()
    async def join_prefix(self, ctx: commands.Context) -> None:
        await self._join(ctx)

    @commands.command(name="play")
    @commands.guild_only()
    async def play_prefix(self, ctx: commands.Context, *, song_url: str) -> None:
        await self._play(ctx, song_url)

    @commands.command(name="playlist")
    @commands.guild_only()
    async def playlist_prefix(self, ctx: commands.Context, *, playlist_url: str) -> None:
        await self._playlist(ctx, playlist_url)

    @commands.command(name="pause")
    @commands.guild_only()
    async def pause_prefix(self, ctx: commands.Context) -> None:
        await self._pause(ctx)

    @commands.command(name="resume")
    @commands.guild_only()
    async def resume_prefix(self, ctx: commands.Context) -> None:
        await self._resume(ctx)

    @commands.command(name="stop")
    @commands.guild_only()
    async def stop_prefix(self, ctx: commands.Context) -> None:
        await self._stop(ctx)

    @commands.command(name="skip")
    @commands.guild_only()
    async def skip_prefix(self, ctx: commands.Context, count: int = 1) -> None:
        await self._skip(ctx, count)

    @commands.command(name="queue", aliases=["q"])
    @commands.guild_only()
    async def queue_prefix(self, ctx: commands.Context) -> None:
        await self._queue(ctx)

    @commands.command(name="remove")
    @commands.guild_only()
    async def remove_prefix(self, ctx: commands.Context, position: int) -> None:
        await self._remove(ctx, position)

    @commands.command(name="clear")
    @commands.guild_only()
    async def clear_prefix(self, ctx: commands.Context) -> None:
        await self._clear(ctx)

    @commands.command(name="shuffle")
    @commands.guild_only()
    async def shuffle_prefix(self, ctx: commands.Context) -> None:
        await self._shuffle(ctx)

    @commands.command(name="loop")
    @commands.guild_only()
    async def loop_prefix(self, ctx: commands.Context, value: str = "toggle") -> None:
        await self._loop(ctx, value)

    @commands.command(name="volume")
    @commands.guild_only()
    async def volume_prefix(self, ctx: commands.Context, percent: int | None = None) -> None:
        await self._volume(ctx, percent)

    @commands.command(name="nowplaying")
    @commands.guild_only()
    async def nowplaying_prefix(self, ctx: commands.Context) -> None:
        await self._nowplaying(ctx)

    @commands.command(name="leave")
    @commands.guild_only()
    async def leave_prefix(self, ctx: commands.Context) -> None:
        await self._leave(ctx)

    async def _join(self, ctx: commands.Context) -> None:
        channel = self.author_voice_channel(ctx)
        if channel is None:
            await ctx.send(embed=error_embed("Music", "Join a voice or stage channel first."))
            return
        try:
            voice = ctx.voice_client
            if isinstance(voice, discord.VoiceClient):
                await voice.move_to(channel)
            else:
                await channel.connect(self_deaf=True)
        except (discord.DiscordException, RuntimeError) as exc:
            await ctx.send(embed=error_embed("Music", self.voice_dependency_message(exc)))
            return
        await ctx.send(embed=success_embed("Music", f"Joined `{channel}`."))

    async def _play(self, ctx: commands.Context, song_url: str) -> None:
        channel = self.author_voice_channel(ctx)
        if channel is None:
            await ctx.send(embed=error_embed("Music", "Join a voice or stage channel first."))
            return
        voice = await self.ensure_voice(ctx, channel)
        if voice is None:
            return
        try:
            async with ctx.typing():
                track = await self.extract_track(song_url, ctx.author.id)
        except RuntimeError as exc:
            await ctx.send(embed=error_embed("Music", str(exc)))
            return
        state = self.state(ctx.guild.id)
        state.text_channel_id = ctx.channel.id
        state.queue.append(track)
        await ctx.send(embed=self.track_embed("Queued Track", track, queue_size=len(state.queue), volume_percent=round(state.volume * 100)))
        if not voice.is_playing() and not voice.is_paused():
            await self.play_next(ctx.guild.id)

    async def _playlist(self, ctx: commands.Context, playlist_url: str) -> None:
        channel = self.author_voice_channel(ctx)
        if channel is None:
            await ctx.send(embed=error_embed("Music", "Join a voice or stage channel first."))
            return
        voice = await self.ensure_voice(ctx, channel)
        if voice is None:
            return
        try:
            async with ctx.typing():
                tracks = await self.extract_playlist(playlist_url, ctx.author.id)
        except RuntimeError as exc:
            await ctx.send(embed=error_embed("Music", str(exc)))
            return
        state = self.state(ctx.guild.id)
        state.text_channel_id = ctx.channel.id
        state.queue.extend(tracks)
        await ctx.send(embed=success_embed("Playlist", f"Queued `{len(tracks)}` track(s)."))
        if not voice.is_playing() and not voice.is_paused():
            await self.play_next(ctx.guild.id)

    async def _pause(self, ctx: commands.Context) -> None:
        voice = ctx.voice_client
        if isinstance(voice, discord.VoiceClient) and voice.is_playing():
            voice.pause()
            await ctx.send(embed=success_embed("Music", "Paused."))
            return
        await ctx.send(embed=warning_embed("Music", "Nothing is playing."))

    async def _resume(self, ctx: commands.Context) -> None:
        voice = ctx.voice_client
        if isinstance(voice, discord.VoiceClient) and voice.is_paused():
            voice.resume()
            await ctx.send(embed=success_embed("Music", "Resumed."))
            return
        await ctx.send(embed=warning_embed("Music", "Nothing is paused."))

    async def _stop(self, ctx: commands.Context) -> None:
        state = self.state(ctx.guild.id)
        self.cancel_pending_announcement(state)
        state.queue.clear()
        state.current = None
        state.started_at = None
        state.consecutive_startup_failures = 0
        state.loop_current = False
        voice = ctx.voice_client
        if isinstance(voice, discord.VoiceClient):
            voice.stop()
        await ctx.send(embed=success_embed("Music", "Stopped playback and cleared the queue."))

    async def _skip(self, ctx: commands.Context, count: int = 1) -> None:
        if not 1 <= count <= 25:
            await ctx.send(embed=error_embed("Skip", "Skip count must be between 1 and 25."))
            return
        state = self.state(ctx.guild.id)
        voice = ctx.voice_client
        if state.current is None and not state.queue:
            await ctx.send(embed=warning_embed("Skip", "Nothing is playing or queued."))
            return
        skipped: list[Track] = []
        if state.current is not None:
            skipped.append(state.current)
        for _ in range(count - 1):
            if not state.queue:
                break
            skipped.append(state.queue.popleft())
        state.current = None
        state.started_at = None
        self.cancel_pending_announcement(state)
        if isinstance(voice, discord.VoiceClient) and (voice.is_playing() or voice.is_paused()):
            voice.stop()
        else:
            await self.play_next(ctx.guild.id)
        item = success_embed("Skip", f"Skipped `{len(skipped)}` track(s).")
        if skipped:
            item.add_field(name="Skipped", value="\n".join(f"`{index}.` {track.title}" for index, track in enumerate(skipped, start=1))[:1024], inline=False)
        await ctx.send(embed=item)

    async def _queue(self, ctx: commands.Context) -> None:
        state = self.state(ctx.guild.id)
        item = embed("Music Queue", status="info")
        if state.current is not None:
            item.add_field(name="Now Playing", value=self.format_queue_line(0, state.current), inline=False)
        else:
            item.add_field(name="Now Playing", value="Nothing is playing.", inline=False)
        upcoming = list(state.queue)[:10]
        if upcoming:
            item.add_field(
                name=f"Upcoming ({len(state.queue)} queued)",
                value="\n".join(self.format_queue_line(index, track) for index, track in enumerate(upcoming, start=1))[:1024],
                inline=False,
            )
        else:
            item.add_field(name="Upcoming", value="No queued tracks.", inline=False)
        item.add_field(name="Volume", value=f"{round(state.volume * 100)}%", inline=True)
        item.add_field(name="Loop", value="Enabled" if state.loop_current else "Disabled", inline=True)
        if len(state.queue) > len(upcoming):
            item.add_field(name="More", value=f"{len(state.queue) - len(upcoming)} additional queued track(s).", inline=True)
        await ctx.send(embed=item)

    async def _remove(self, ctx: commands.Context, position: int) -> None:
        state = self.state(ctx.guild.id)
        if not 1 <= position <= len(state.queue):
            await ctx.send(embed=error_embed("Remove Track", f"Position must be between 1 and {len(state.queue) or 1}."))
            return
        queue = list(state.queue)
        removed = queue.pop(position - 1)
        state.queue = deque(queue)
        await ctx.send(embed=success_embed("Remove Track", f"Removed `{removed.title}` from queue position `{position}`."))

    async def _clear(self, ctx: commands.Context) -> None:
        state = self.state(ctx.guild.id)
        count = len(state.queue)
        state.queue.clear()
        await ctx.send(embed=success_embed("Clear Queue", f"Cleared `{count}` queued track(s). Current playback was not stopped."))

    async def _shuffle(self, ctx: commands.Context) -> None:
        state = self.state(ctx.guild.id)
        if len(state.queue) < 2:
            await ctx.send(embed=warning_embed("Shuffle", "Need at least two queued tracks to shuffle."))
            return
        queue = list(state.queue)
        random.shuffle(queue)
        state.queue = deque(queue)
        await ctx.send(embed=success_embed("Shuffle", f"Shuffled `{len(state.queue)}` queued track(s)."))

    async def _loop(self, ctx: commands.Context, value: str = "toggle") -> None:
        state = self.state(ctx.guild.id)
        if value.casefold() in {"on", "true", "yes", "enable"}:
            state.loop_current = True
        elif value.casefold() in {"off", "false", "no", "disable"}:
            state.loop_current = False
        elif value.casefold() == "toggle":
            state.loop_current = not state.loop_current
        else:
            await ctx.send(embed=error_embed("Loop", "Use `loop on`, `loop off`, or `loop`."))
            return
        await ctx.send(embed=success_embed("Loop", f"Current-track loop is {'enabled' if state.loop_current else 'disabled'}."))

    async def _volume(self, ctx: commands.Context, percent: int | None = None) -> None:
        state = self.state(ctx.guild.id)
        if percent is None:
            await ctx.send(embed=table_embed("Volume", [("current", f"{round(state.volume * 100)}%")]))
            return
        if not 0 <= percent <= 200:
            await ctx.send(embed=error_embed("Volume", "Volume must be between 0 and 200 percent."))
            return
        state.volume = percent / 100
        voice = ctx.voice_client
        if isinstance(voice, discord.VoiceClient) and isinstance(voice.source, discord.PCMVolumeTransformer):
            voice.source.volume = state.volume
        await ctx.send(embed=success_embed("Volume", f"Volume set to `{percent}%`."))

    async def _nowplaying(self, ctx: commands.Context) -> None:
        state = self.state(ctx.guild.id)
        if state.current is None:
            await ctx.send(embed=warning_embed("Music", "Nothing is playing."))
            return
        await ctx.send(embed=self.track_embed("Now Playing", state.current, queue_size=len(state.queue), volume_percent=round(state.volume * 100)))

    async def _leave(self, ctx: commands.Context) -> None:
        voice = ctx.voice_client
        if isinstance(voice, discord.VoiceClient):
            await voice.disconnect(force=False)
        state = self.states.get(ctx.guild.id)
        if state is not None:
            self.cancel_pending_announcement(state)
        self.states.pop(ctx.guild.id, None)
        await ctx.send(embed=success_embed("Music", "Left voice."))

    def author_voice_channel(self, ctx: commands.Context) -> discord.VoiceChannel | discord.StageChannel | None:
        author = ctx.author
        if not isinstance(author, discord.Member) or author.voice is None:
            return None
        channel = author.voice.channel
        return channel if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)) else None

    async def ensure_voice(
        self,
        ctx: commands.Context,
        channel: discord.VoiceChannel | discord.StageChannel,
    ) -> discord.VoiceClient | None:
        voice = ctx.voice_client
        try:
            if isinstance(voice, discord.VoiceClient):
                if voice.channel != channel:
                    await voice.move_to(channel)
                return voice
            connected = await channel.connect(self_deaf=True)
            return connected if isinstance(connected, discord.VoiceClient) else None
        except (discord.DiscordException, RuntimeError) as exc:
            await ctx.send(embed=error_embed("Music", self.voice_dependency_message(exc)))
            return None

    async def extract_track(self, url: str, requester_id: int) -> Track:
        tracks = await self.extract_tracks(url, requester_id, playlist=False, limit=1)
        if not tracks:
            raise RuntimeError("No playable track found.")
        return tracks[0]

    async def extract_playlist(self, url: str, requester_id: int) -> list[Track]:
        tracks = await self.extract_tracks(url, requester_id, playlist=True, limit=25)
        if not tracks:
            raise RuntimeError("No playable playlist tracks found.")
        return tracks

    async def extract_tracks(self, url: str, requester_id: int, *, playlist: bool, limit: int) -> list[Track]:
        spotify_resource = parse_spotify_resource(url)
        if spotify_resource is not None:
            return await self.extract_spotify_tracks(url, requester_id, playlist=playlist, limit=limit)
        return await self.extract_playable_tracks(url, requester_id, playlist=playlist, limit=limit)

    async def extract_spotify_tracks(self, url: str, requester_id: int, *, playlist: bool, limit: int) -> list[Track]:
        queries = await self.spotify_queries(url, playlist=playlist, limit=limit)
        if not queries:
            raise RuntimeError(
                "Spotify links need metadata resolution. Add `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` for playlist/album support, or use a Spotify track URL."
            )
        tracks: list[Track] = []
        for query in queries[:limit]:
            found = await self.extract_playable_tracks(f"ytsearch1:{query}", requester_id, playlist=False, limit=1, source="Spotify search")
            tracks.extend(found[:1])
        return tracks

    async def spotify_queries(self, url: str, *, playlist: bool, limit: int) -> list[str]:
        resource = parse_spotify_resource(url)
        if resource is None:
            return []
        token = await self.spotify_access_token()
        if token is None:
            if resource.kind == "track":
                fallback = await self.spotify_oembed_query(url)
                return [fallback] if fallback else []
            return []
        headers = {"Authorization": f"Bearer {token}"}
        params = {"market": self.bot.settings.spotify_market}
        try:
            async with aiohttp.ClientSession() as session:
                if resource.kind == "track":
                    async with session.get(f"{SPOTIFY_API_BASE}/tracks/{resource.resource_id}", headers=headers, params=params, timeout=12) as response:
                        response.raise_for_status()
                        payload = await response.json()
                    query = self.query_from_spotify_track(payload)
                    return [query] if query else []
                if resource.kind == "playlist":
                    if not playlist:
                        limit = 1
                    async with session.get(
                        f"{SPOTIFY_API_BASE}/playlists/{resource.resource_id}/tracks",
                        headers=headers,
                        params={**params, "limit": min(limit, 50)},
                        timeout=15,
                    ) as response:
                        response.raise_for_status()
                        payload = await response.json()
                    return [
                        query
                        for item in payload.get("items", [])
                        if isinstance(item, dict) and isinstance(item.get("track"), dict) and item["track"].get("type") == "track"
                        for query in [self.query_from_spotify_track(item["track"])]
                        if query
                    ][:limit]
                if resource.kind == "album":
                    if not playlist:
                        limit = 1
                    async with session.get(
                        f"{SPOTIFY_API_BASE}/albums/{resource.resource_id}/tracks",
                        headers=headers,
                        params={**params, "limit": min(limit, 50)},
                        timeout=15,
                    ) as response:
                        response.raise_for_status()
                        payload = await response.json()
                    return [
                        query
                        for item in payload.get("items", [])
                        if isinstance(item, dict) and item.get("type") == "track"
                        for query in [self.query_from_spotify_track(item)]
                        if query
                    ][:limit]
        except (aiohttp.ClientError, TimeoutError, KeyError, ValueError):
            return []
        return []

    async def spotify_access_token(self) -> str | None:
        client_id = self.bot.settings.spotify_client_id
        secret = self.bot.settings.spotify_client_secret
        if not client_id or secret is None:
            return None
        raw = f"{client_id}:{secret.get_secret_value()}".encode("utf-8")
        headers = {"Authorization": f"Basic {base64.b64encode(raw).decode('ascii')}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(SPOTIFY_TOKEN_URL, headers=headers, data={"grant_type": "client_credentials"}, timeout=12) as response:
                    response.raise_for_status()
                    payload = await response.json()
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return None
        token = payload.get("access_token")
        return token if isinstance(token, str) else None

    async def spotify_oembed_query(self, url: str) -> str | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SPOTIFY_OEMBED_URL, params={"url": url}, timeout=10) as response:
                    response.raise_for_status()
                    payload = await response.json()
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return None
        title = str(payload.get("title") or "").strip()
        author = str(payload.get("author_name") or "").strip()
        if not title:
            return None
        return spotify_track_query(title, [author] if author else [])

    @staticmethod
    def query_from_spotify_track(payload: dict) -> str:
        name = str(payload.get("name") or "").strip()
        if not name:
            return ""
        artists = [
            str(artist.get("name")).strip()
            for artist in payload.get("artists", [])
            if isinstance(artist, dict) and artist.get("name")
        ]
        return spotify_track_query(name, artists)

    async def extract_playable_tracks(self, url: str, requester_id: int, *, playlist: bool, limit: int, source: str = "yt-dlp") -> list[Track]:
        try:
            import yt_dlp
        except ImportError as exc:
            raise RuntimeError("Music extraction requires `yt-dlp`. Install dependencies with `pip install -r requirements.txt`.") from exc

        def run_extract() -> list[Track]:
            logger = YtdlpLogger()
            options = {
                "format": "bestaudio[ext=m4a]/bestaudio[acodec^=opus]/bestaudio/best",
                "quiet": True,
                "no_warnings": True,
                "logger": logger,
                "js_runtimes": available_js_runtimes(),
                "noplaylist": not playlist,
                "extract_flat": False,
                "default_search": "auto",
                "socket_timeout": 15,
            }
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
            raw_entries = info.get("entries") if isinstance(info, dict) else None
            entries = raw_entries if raw_entries else [info]
            tracks: list[Track] = []
            for entry in entries[:limit]:
                if not isinstance(entry, dict):
                    continue
                stream_url = entry.get("url")
                webpage_url = entry.get("webpage_url") or entry.get("original_url") or url
                title = entry.get("title") or webpage_url
                headers = normalized_headers(entry.get("http_headers") or (info.get("http_headers") if isinstance(info, dict) else None))
                if stream_url:
                    tracks.append(
                        Track(
                            str(title)[:180],
                            str(webpage_url),
                            str(stream_url),
                            requester_id,
                            source=source,
                            duration=int(entry["duration"]) if isinstance(entry.get("duration"), (int, float)) else None,
                            thumbnail=str(entry["thumbnail"]) if entry.get("thumbnail") else None,
                            headers=headers,
                        )
                    )
            return tracks

        try:
            return await asyncio.to_thread(run_extract)
        except Exception as exc:
            raise RuntimeError("Could not extract that URL. Try a public YouTube, SoundCloud, or direct audio link.") from exc

    async def refresh_track_stream(self, track: Track) -> Track:
        try:
            refreshed = (await self.extract_playable_tracks(track.webpage_url, track.requester_id, playlist=False, limit=1, source=track.source))[0]
        except (RuntimeError, IndexError):
            return track
        track.stream_url = refreshed.stream_url
        track.headers = refreshed.headers
        track.duration = refreshed.duration or track.duration
        track.thumbnail = refreshed.thumbnail or track.thumbnail
        if refreshed.title:
            track.title = refreshed.title
        if refreshed.webpage_url:
            track.webpage_url = refreshed.webpage_url
        return track

    async def play_next(self, guild_id: int, *, from_after: bool = False, previous_error: Exception | None = None) -> None:
        guild = self.bot.get_guild(guild_id)
        if guild is None or not isinstance(guild.voice_client, discord.VoiceClient):
            return
        voice = guild.voice_client
        state = self.state(guild_id)
        previous_failed = False
        if from_after and state.current is not None:
            elapsed = time.monotonic() - state.started_at if state.started_at is not None else 0
            previous_failed = previous_error is not None or elapsed < STARTUP_FAILURE_SECONDS
            if previous_failed:
                state.consecutive_startup_failures += 1
            else:
                state.consecutive_startup_failures = 0

        if state.consecutive_startup_failures >= MAX_STARTUP_FAILURES:
            failed_count = state.consecutive_startup_failures
            state.queue.clear()
            state.current = None
            state.started_at = None
            state.consecutive_startup_failures = 0
            await self.send_playback_stopped(guild_id, f"Stopped music after `{failed_count}` tracks failed at startup. The stream source is probably rejecting or expiring direct audio URLs.")
            return

        if state.loop_current and state.current is not None and not previous_failed:
            next_track = state.current
            should_announce = False
        elif state.queue:
            next_track = state.queue.popleft()
            should_announce = state.current is not None
        else:
            state.current = None
            state.started_at = None
            if previous_failed:
                state.consecutive_startup_failures = 0
                await self.send_playback_stopped(guild_id, "Playback failed before audio could start. The source may be private, expired, blocked, or rejecting Discord/FFmpeg requests.")
            return
        next_track = await self.refresh_track_stream(next_track)
        state.current = next_track
        state.started_at = time.monotonic()
        before_options = " ".join(
            option
            for option in (
                "-nostdin",
                "-reconnect 1",
                "-reconnect_streamed 1",
                "-reconnect_on_network_error 1",
                "-reconnect_on_http_error 4xx,5xx",
                "-reconnect_delay_max 10",
                ffmpeg_header_options(next_track.headers),
            )
            if option
        )
        try:
            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(
                    next_track.stream_url,
                    before_options=before_options,
                    options="-vn -loglevel error",
                    stderr=subprocess.DEVNULL,
                ),
                volume=state.volume,
            )
            voice.play(
                source,
                after=lambda error: asyncio.run_coroutine_threadsafe(self.after_track(guild_id, error), self.bot.loop),
            )
        except (discord.DiscordException, RuntimeError, OSError) as exc:
            state.consecutive_startup_failures += 1
            state.current = None
            state.started_at = None
            if not state.queue:
                await self.send_playback_stopped(guild_id, f"Playback could not start: `{type(exc).__name__}`.")
                return
            if state.consecutive_startup_failures >= MAX_STARTUP_FAILURES:
                state.queue.clear()
                await self.send_playback_stopped(guild_id, f"Stopped music because playback could not start: `{type(exc).__name__}`.")
                return
            await self.play_next(guild_id)
            return
        if should_announce:
            self.schedule_playing_now(guild_id, next_track)

    async def after_track(self, guild_id: int, error: Exception | None) -> None:
        await self.play_next(guild_id, from_after=True, previous_error=error)

    def schedule_playing_now(self, guild_id: int, track: Track) -> None:
        state = self.state(guild_id)
        self.cancel_pending_announcement(state)
        state.announce_task = self.bot.loop.create_task(self.delayed_playing_now(guild_id, track))

    async def delayed_playing_now(self, guild_id: int, track: Track) -> None:
        try:
            await asyncio.sleep(2)
        except asyncio.CancelledError:
            return
        guild = self.bot.get_guild(guild_id)
        state = self.state(guild_id)
        if guild is None or state.current is not track or not isinstance(guild.voice_client, discord.VoiceClient):
            return
        if not guild.voice_client.is_playing():
            return
        await self.send_playing_now(guild_id, track)

    @staticmethod
    def cancel_pending_announcement(state: MusicState) -> None:
        if state.announce_task is not None and not state.announce_task.done():
            state.announce_task.cancel()
        state.announce_task = None

    async def send_playing_now(self, guild_id: int, track: Track) -> None:
        state = self.state(guild_id)
        if state.text_channel_id is None:
            return
        channel = self.bot.get_channel(state.text_channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            return
        try:
            await channel.send(
                embed=self.track_embed(
                    "Playing Now",
                    track,
                    queue_size=len(state.queue),
                    volume_percent=round(state.volume * 100),
                )
            )
        except discord.DiscordException:
            return

    async def send_playback_stopped(self, guild_id: int, message: str) -> None:
        state = self.state(guild_id)
        if state.text_channel_id is None:
            return
        channel = self.bot.get_channel(state.text_channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            return
        with contextlib.suppress(discord.DiscordException):
            await channel.send(embed=error_embed("Music Playback Stopped", message))

    @staticmethod
    def track_embed(title: str, track: Track, *, queue_size: int, volume_percent: int | None = None) -> discord.Embed:
        item = embed(title, f"**{track_markdown_link(track, 240)}**", status="info")
        rows: list[tuple[str, object]] = [("requested by", f"<@{track.requester_id}>"), ("queue", f"{queue_size} waiting")]
        if track.duration:
            rows.append(("duration", format_duration(track.duration)))
        rows.append(("source", track.source))
        if volume_percent is not None:
            rows.append(("volume", f"{volume_percent}%"))
        for name, value in rows:
            item.add_field(name=name.title(), value=str(value), inline=True)
        if track.thumbnail:
            item.set_thumbnail(url=track.thumbnail)
        return item

    @staticmethod
    def format_queue_line(position: int, track: Track) -> str:
        label = "Now" if position == 0 else str(position)
        duration = f" `{format_duration(track.duration)}`" if track.duration else ""
        return f"`{label}.` {track_markdown_link(track, 72)}{duration} • <@{track.requester_id}>"

    @staticmethod
    def voice_dependency_message(error: Exception) -> str:
        text = str(error)
        if "davey" in text.casefold():
            return "Voice needs the `davey` package in the same virtualenv as the bot. Run `python -m pip install -U davey` inside `.venv`, then restart the bot process."
        if "pynacl" in text.casefold():
            return "Voice needs `PyNaCl` in the same virtualenv as the bot. Run `python -m pip install -U PyNaCl`, then restart the bot process."
        return "PHPelefant could not join voice. Check Connect/Speak permissions and install the voice dependencies from `requirements.txt`."


def available_js_runtimes() -> dict[str, dict[str, str]]:
    runtimes: dict[str, dict[str, str]] = {}
    for runtime_name, executable in (("deno", "deno"), ("node", "node"), ("quickjs", "qjs"), ("bun", "bun")):
        path = shutil.which(executable)
        if path:
            runtimes[runtime_name] = {"path": path}
    return runtimes or {"deno": {}}


def track_markdown_link(track: Track, limit: int) -> str:
    title = discord.utils.escape_markdown(truncate_text(track.title, limit)).replace("]", r"\]")
    url = track.webpage_url.replace(")", "%29").replace(" ", "%20")
    return f"[{title}]({url})"


class YtdlpLogger:
    def debug(self, message: str) -> None:
        return None

    def info(self, message: str) -> None:
        return None

    def warning(self, message: str) -> None:
        return None

    def error(self, message: str) -> None:
        return None


def format_duration(seconds: int) -> str:
    minutes, second = divmod(max(0, seconds), 60)
    hours, minute = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minute:02d}:{second:02d}"
    return f"{minute}:{second:02d}"


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(Music(bot))
