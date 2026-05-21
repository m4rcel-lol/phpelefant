from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
import random

import discord
from discord.ext import commands

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.utils.formatting import error_embed, success_embed, table_embed, warning_embed


@dataclass(slots=True)
class Track:
    title: str
    webpage_url: str
    stream_url: str
    requester_id: int


class MusicState:
    def __init__(self) -> None:
        self.queue: deque[Track] = deque()
        self.current: Track | None = None
        self.loop_current = False
        self.volume = 0.75
        self.text_channel_id: int | None = None


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
        state.queue.clear()
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
        rows: list[tuple[str, object]] = []
        if state.current is not None:
            rows.append(("now playing", state.current.title))
        for index, track in enumerate(list(state.queue)[:10], start=1):
            rows.append((str(index), f"{track.title} - requested by <@{track.requester_id}>"))
        if len(state.queue) > 10:
            rows.append(("more", f"{len(state.queue) - 10} additional queued track(s)"))
        rows.append(("volume", f"{round(state.volume * 100)}%"))
        rows.append(("loop", "enabled" if state.loop_current else "disabled"))
        await ctx.send(embed=table_embed("Music Queue", rows or [("queue", "No tracks queued.")]))

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
        try:
            import yt_dlp
        except ImportError as exc:
            raise RuntimeError("Music extraction requires `yt-dlp`. Install dependencies with `pip install -r requirements.txt`.") from exc

        def run_extract() -> list[Track]:
            options = {
                "format": "bestaudio/best",
                "quiet": True,
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
                if stream_url:
                    tracks.append(Track(str(title)[:180], str(webpage_url), str(stream_url), requester_id))
            return tracks

        try:
            return await asyncio.to_thread(run_extract)
        except Exception as exc:
            raise RuntimeError("Could not extract that URL. Try a public YouTube, SoundCloud, or direct audio link.") from exc

    async def play_next(self, guild_id: int) -> None:
        guild = self.bot.get_guild(guild_id)
        if guild is None or not isinstance(guild.voice_client, discord.VoiceClient):
            return
        voice = guild.voice_client
        state = self.state(guild_id)
        if state.loop_current and state.current is not None:
            next_track = state.current
            should_announce = False
        elif state.queue:
            next_track = state.queue.popleft()
            should_announce = state.current is not None
        else:
            state.current = None
            return
        state.current = next_track
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(
                next_track.stream_url,
                before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                options="-vn",
            ),
            volume=state.volume,
        )
        voice.play(
            source,
            after=lambda error: asyncio.run_coroutine_threadsafe(self.after_track(guild_id, error), self.bot.loop),
        )
        if should_announce:
            await self.send_playing_now(guild_id, next_track)

    async def after_track(self, guild_id: int, error: Exception | None) -> None:
        await self.play_next(guild_id)

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

    @staticmethod
    def track_embed(title: str, track: Track, *, queue_size: int, volume_percent: int | None = None) -> discord.Embed:
        rows: list[tuple[str, object]] = [
            ("title", track.title),
            ("requested by", f"<@{track.requester_id}>"),
            ("queue size", queue_size),
        ]
        if volume_percent is not None:
            rows.append(("volume", f"{volume_percent}%"))
        item = table_embed(
            title,
            rows,
            status="info",
        )
        item.url = track.webpage_url
        item.add_field(name="Source", value=f"[Open source]({track.webpage_url})", inline=False)
        return item

    @staticmethod
    def voice_dependency_message(error: Exception) -> str:
        text = str(error)
        if "davey" in text.casefold():
            return "Voice needs the `davey` package in the same virtualenv as the bot. Run `python -m pip install -U davey` inside `.venv`, then restart the bot process."
        if "pynacl" in text.casefold():
            return "Voice needs `PyNaCl` in the same virtualenv as the bot. Run `python -m pip install -U PyNaCl`, then restart the bot process."
        return "PHPelefant could not join voice. Check Connect/Speak permissions and install the voice dependencies from `requirements.txt`."


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(Music(bot))
