from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass

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


class Music(commands.Cog):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot
        self.states: dict[int, MusicState] = {}

    def state(self, guild_id: int) -> MusicState:
        return self.states.setdefault(guild_id, MusicState())

    @commands.hybrid_command(name="join")
    @commands.guild_only()
    async def join(self, ctx: commands.Context) -> None:
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
        except discord.DiscordException:
            await ctx.send(embed=error_embed("Music", "PHPelefant could not join that voice channel. Check voice permissions and PyNaCl."))
            return
        await ctx.send(embed=success_embed("Music", f"Joined `{channel}`."))

    @commands.hybrid_command(name="play")
    @commands.guild_only()
    async def play(self, ctx: commands.Context, *, song_url: str) -> None:
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
        state.queue.append(track)
        await ctx.send(embed=self.track_embed("Queued Track", track, queue_size=len(state.queue)))
        if not voice.is_playing() and not voice.is_paused():
            await self.play_next(ctx.guild.id)

    @commands.hybrid_command(name="playlist")
    @commands.guild_only()
    async def playlist(self, ctx: commands.Context, *, playlist_url: str) -> None:
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
        state.queue.extend(tracks)
        await ctx.send(embed=success_embed("Playlist", f"Queued `{len(tracks)}` track(s)."))
        if not voice.is_playing() and not voice.is_paused():
            await self.play_next(ctx.guild.id)

    @commands.hybrid_command(name="pause")
    @commands.guild_only()
    async def pause(self, ctx: commands.Context) -> None:
        voice = ctx.voice_client
        if isinstance(voice, discord.VoiceClient) and voice.is_playing():
            voice.pause()
            await ctx.send(embed=success_embed("Music", "Paused."))
            return
        await ctx.send(embed=warning_embed("Music", "Nothing is playing."))

    @commands.hybrid_command(name="resume")
    @commands.guild_only()
    async def resume(self, ctx: commands.Context) -> None:
        voice = ctx.voice_client
        if isinstance(voice, discord.VoiceClient) and voice.is_paused():
            voice.resume()
            await ctx.send(embed=success_embed("Music", "Resumed."))
            return
        await ctx.send(embed=warning_embed("Music", "Nothing is paused."))

    @commands.hybrid_command(name="stop")
    @commands.guild_only()
    async def stop(self, ctx: commands.Context) -> None:
        state = self.state(ctx.guild.id)
        state.queue.clear()
        state.loop_current = False
        voice = ctx.voice_client
        if isinstance(voice, discord.VoiceClient):
            voice.stop()
        await ctx.send(embed=success_embed("Music", "Stopped playback and cleared the queue."))

    @commands.hybrid_command(name="loop")
    @commands.guild_only()
    async def loop(self, ctx: commands.Context, value: str = "toggle") -> None:
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

    @commands.hybrid_command(name="nowplaying")
    @commands.guild_only()
    async def nowplaying(self, ctx: commands.Context) -> None:
        state = self.state(ctx.guild.id)
        if state.current is None:
            await ctx.send(embed=warning_embed("Music", "Nothing is playing."))
            return
        await ctx.send(embed=self.track_embed("Now Playing", state.current, queue_size=len(state.queue)))

    @commands.hybrid_command(name="leave")
    @commands.guild_only()
    async def leave(self, ctx: commands.Context) -> None:
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
        except discord.DiscordException:
            await ctx.send(embed=error_embed("Music", "Could not connect to voice. Install PyNaCl and check Connect/Speak permissions."))
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
        elif state.queue:
            next_track = state.queue.popleft()
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
            volume=0.75,
        )
        voice.play(
            source,
            after=lambda error: asyncio.run_coroutine_threadsafe(self.after_track(guild_id, error), self.bot.loop),
        )

    async def after_track(self, guild_id: int, error: Exception | None) -> None:
        await self.play_next(guild_id)

    @staticmethod
    def track_embed(title: str, track: Track, *, queue_size: int) -> discord.Embed:
        item = table_embed(
            title,
            [
                ("title", track.title),
                ("requested by", f"<@{track.requester_id}>"),
                ("queue size", queue_size),
            ],
            status="info",
        )
        item.url = track.webpage_url
        item.add_field(name="Source", value=f"[Open source]({track.webpage_url})", inline=False)
        return item


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(Music(bot))
