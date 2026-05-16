from __future__ import annotations

import io
import random
import re
from urllib.parse import urlparse

import aiohttp
import discord
from discord.ext import commands

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.utils.formatting import code_embed, embed, image_embed
from phpelefant_discord.utils.quote_card import QuoteCardData, render_quote_card

JOKES = [
    "Why do PHP developers like elephants? They never forget a semicolon.",
    "A SQL query walks into a bar, joins two tables, and leaves with a result set.",
    "Debugging: being the detective in a crime movie where you are also the suspect.",
]
QUOTES = [
    "Programs must be written for people to read, and only incidentally for machines to execute.",
    "Simplicity is prerequisite for reliability.",
    "Make it work, make it right, make it fast.",
]
FACTS = [
    "PHP was created by Rasmus Lerdorf in 1994.",
    "Discord moderation actions require the bot role to be above the target member.",
    "PostgreSQL supports transactional DDL, which makes migrations safer.",
]
IMAGE_SIZE_LIMIT = 8 * 1024 * 1024
HTTP_STATUS_RE = re.compile(r"^[1-5][0-9]{2}$")


def extension_from_content_type(content_type: str | None, fallback: str = ".jpg") -> str:
    if not content_type:
        return fallback
    if "png" in content_type:
        return ".png"
    if "gif" in content_type:
        return ".gif"
    if "webp" in content_type:
        return ".webp"
    if "jpeg" in content_type or "jpg" in content_type:
        return ".jpg"
    return fallback


def extension_from_url(url: str, fallback: str = ".jpg") -> str:
    suffix = urlparse(url).path.rsplit(".", 1)
    if len(suffix) == 2 and suffix[1].lower() in {"jpg", "jpeg", "png", "gif", "webp"}:
        return "." + suffix[1].lower()
    return fallback


class Fun(commands.Cog):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="joke")
    async def joke(self, ctx: commands.Context) -> None:
        await ctx.send(embed=code_embed("Joke", random.choice(JOKES)))

    @commands.hybrid_command(name="meme")
    async def meme(self, ctx: commands.Context, *, text: str | None = None) -> None:
        await self.send_image_attachment_embed(
            ctx,
            "Meme",
            "https://i.imgflip.com/1bij.jpg",
            description=text,
            filename_prefix="meme",
        )

    @commands.hybrid_command(name="quote")
    async def quote(self, ctx: commands.Context, message_id: str | None = None) -> None:
        quoted = await self.resolve_quoted_message(ctx, message_id)
        if quoted is None:
            await ctx.send(embed=code_embed("Quote", random.choice(QUOTES)))
            return

        quote_text = quoted.clean_content or quoted.content
        if not quote_text and quoted.attachments:
            quote_text = " ".join(f"[attachment: {attachment.filename}]" for attachment in quoted.attachments[:3])
        if not quote_text and quoted.embeds:
            quote_text = "[embed]"
        if not quote_text:
            quote_text = "[no text content]"

        avatar_bytes = await self.download_bytes(quoted.author.display_avatar.with_size(256).url)
        card_bytes = render_quote_card(
            QuoteCardData(
                author_name=quoted.author.display_name,
                author_handle=f"@{quoted.author} • {quoted.id}",
                message=quote_text,
                timestamp=quoted.created_at,
                avatar_bytes=avatar_bytes,
            )
        )
        file = discord.File(io.BytesIO(card_bytes), filename="quote.png")
        item = embed("Quote")
        item.set_image(url="attachment://quote.png")
        item.add_field(name="Jump", value=f"[Open message]({quoted.jump_url})", inline=False)
        await ctx.send(embed=item, file=file)

    @commands.hybrid_command(name="fact")
    async def fact(self, ctx: commands.Context) -> None:
        await ctx.send(embed=code_embed("Fact", random.choice(FACTS)))

    @commands.hybrid_command(name="8ball")
    async def eight_ball(self, ctx: commands.Context, *, question: str = "") -> None:
        await ctx.send(embed=code_embed("8ball", random.choice(["Yes.", "No.", "Ask again later.", "It is likely.", "Do not count on it."])))

    @commands.hybrid_command(name="coinflip")
    async def coinflip(self, ctx: commands.Context) -> None:
        await ctx.send(embed=code_embed("Coinflip", random.choice(["Heads", "Tails"])))

    @commands.hybrid_command(name="dice")
    async def dice(self, ctx: commands.Context) -> None:
        await ctx.send(embed=code_embed("Dice", f"Rolled {random.randint(1, 6)}"))

    @commands.hybrid_command(name="roll")
    async def roll(self, ctx: commands.Context, sides: int = 6) -> None:
        if not 2 <= sides <= 100000:
            await ctx.send(embed=code_embed("Roll", "Sides must be between 2 and 100000."))
            return
        await ctx.send(embed=code_embed("Roll", f"Rolled {random.randint(1, sides)} on a d{sides}."))

    @commands.hybrid_command(name="ship")
    async def ship(self, ctx: commands.Context, *, names: str = "PHP elefant") -> None:
        await ctx.send(embed=code_embed("Ship", f"Compatibility for {names}: {random.randint(1, 100)}%"))

    @commands.hybrid_command(name="roast")
    async def roast(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member.display_name if member else ctx.author.display_name
        await ctx.send(embed=code_embed("Roast", f"{target}, your code has more TODOs than a Monday standup."))

    @commands.hybrid_command(name="compliment")
    async def compliment(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member.display_name if member else ctx.author.display_name
        await ctx.send(embed=code_embed("Compliment", f"{target} is reliable, sharp, and helpful."))

    @commands.hybrid_command(name="hug")
    async def hug(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member.display_name if member else "the community"
        await ctx.send(embed=code_embed("Hug", f"Hug sent to {target}."))

    @commands.hybrid_command(name="slap")
    async def slap(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member.display_name if member else "the bug"
        await ctx.send(embed=code_embed("Slap", f"A harmless slap was delivered to {target}."))

    @commands.hybrid_command(name="cat")
    async def cat(self, ctx: commands.Context) -> None:
        await self.send_image_attachment_embed(ctx, "Cat", "https://cataas.com/cat", filename_prefix="cat")

    @commands.hybrid_command(name="dog")
    async def dog(self, ctx: commands.Context) -> None:
        try:
            image_url = await self.fetch_random_dog_url()
        except commands.CommandError:
            image_url = "https://images.dog.ceo/breeds/retriever-golden/n02099601_3004.jpg"
        await self.send_image_attachment_embed(ctx, "Dog", image_url, filename_prefix="dog")

    @commands.hybrid_command(name="httpcat")
    async def httpcat(self, ctx: commands.Context, status: int = 404) -> None:
        if not HTTP_STATUS_RE.fullmatch(str(status)):
            await ctx.send(embed=code_embed("HTTP Cat", "Use a valid HTTP status code, for example 404."))
            return
        await self.send_image_attachment_embed(
            ctx,
            f"HTTP Cat {status}",
            f"https://http.cat/{status}.jpg",
            filename_prefix=f"httpcat-{status}",
        )

    @commands.hybrid_command(name="httpdog")
    async def httpdog(self, ctx: commands.Context, status: int = 404) -> None:
        if not HTTP_STATUS_RE.fullmatch(str(status)):
            await ctx.send(embed=code_embed("HTTP Dog", "Use a valid HTTP status code, for example 404."))
            return
        await self.send_image_attachment_embed(
            ctx,
            f"HTTP Dog {status}",
            f"https://http.dog/{status}.jpg",
            filename_prefix=f"httpdog-{status}",
        )

    @commands.hybrid_command(name="choose")
    async def choose(self, ctx: commands.Context, *, options: str) -> None:
        values = [item.strip() for item in options.split("|") if item.strip()]
        if len(values) < 2:
            await ctx.send(embed=code_embed("Choose", "Use: choose option 1 | option 2"))
            return
        await ctx.send(embed=code_embed("Choose", random.choice(values)))

    @commands.hybrid_command(name="rate")
    async def rate(self, ctx: commands.Context, *, thing: str) -> None:
        await ctx.send(embed=code_embed("Rate", f"{thing}: {random.randint(0, 100)}/100"))

    @commands.hybrid_command(name="avatar")
    async def avatar(self, ctx: commands.Context, member: discord.Member | None = None) -> None:
        target = member or ctx.author
        await self.send_image_attachment_embed(
            ctx,
            f"{target.display_name}'s Avatar",
            target.display_avatar.with_size(512).url,
            filename_prefix="avatar",
        )

    @commands.hybrid_command(name="poll")
    async def poll(self, ctx: commands.Context, question: str, option1: str, option2: str, option3: str | None = None, option4: str | None = None) -> None:
        options = [option for option in (option1, option2, option3, option4) if option]
        message = await ctx.send(embed=embed("Poll", f"**{question}**\n" + "\n".join(f"{i}. {option}" for i, option in enumerate(options, start=1))))
        for emoji in ("1️⃣", "2️⃣", "3️⃣", "4️⃣")[: len(options)]:
            await message.add_reaction(emoji)

    @commands.hybrid_command(name="quiz")
    async def quiz(self, ctx: commands.Context, question: str, answer: str) -> None:
        await ctx.send(embed=code_embed("Quiz", f"Quiz: {question}\nAnswer: {answer}"))

    async def resolve_quoted_message(self, ctx: commands.Context, message_id: str | None) -> discord.Message | None:
        if ctx.message.reference and ctx.message.reference.message_id:
            try:
                if isinstance(ctx.message.reference.resolved, discord.Message):
                    return ctx.message.reference.resolved
                return await ctx.channel.fetch_message(ctx.message.reference.message_id)
            except discord.DiscordException:
                return None
        if message_id is None:
            return None
        try:
            return await ctx.channel.fetch_message(int(message_id))
        except (ValueError, discord.DiscordException):
            return None

    async def fetch_random_dog_url(self) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://dog.ceo/api/breeds/image/random", timeout=10) as response:
                response.raise_for_status()
                payload = await response.json()
        image_url = payload.get("message")
        if not isinstance(image_url, str) or not image_url.startswith("http"):
            raise commands.CommandError("Dog API returned an invalid image URL.")
        return image_url

    async def download_image_file(self, image_url: str, filename_prefix: str) -> discord.File | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=15) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("Content-Type", "")
                    extension_from_path = extension_from_url(str(response.url), "")
                    if not content_type.startswith("image/") and not extension_from_path:
                        return None
                    data = await response.read()
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return None
        if not data or len(data) > IMAGE_SIZE_LIMIT:
            return None
        extension = extension_from_content_type(content_type, extension_from_url(image_url))
        filename = f"{filename_prefix}{extension}"
        return discord.File(io.BytesIO(data), filename=filename)

    async def download_bytes(self, url: str) -> bytes | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as response:
                    response.raise_for_status()
                    data = await response.read()
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return None
        if not data or len(data) > IMAGE_SIZE_LIMIT:
            return None
        return data

    async def send_image_attachment_embed(
        self,
        ctx: commands.Context,
        title: str,
        image_url: str,
        *,
        description: str | None = None,
        filename_prefix: str = "image",
    ) -> None:
        file = await self.download_image_file(image_url, filename_prefix)
        if file is None:
            await ctx.send(embed=image_embed(title, image_url, description))
            return
        item = embed(title, description)
        item.set_image(url=f"attachment://{file.filename}")
        await ctx.send(embed=item, file=file)


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(Fun(bot))
