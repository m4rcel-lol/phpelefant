from __future__ import annotations

import io
import random
import re
from urllib.parse import urlparse

import aiohttp
import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageSequence, UnidentifiedImageError

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
MEMES = [
    ("Distracted Developer", "https://i.imgflip.com/1ur9b0.jpg"),
    ("Drake Hotline Bling", "https://i.imgflip.com/30b1gx.jpg"),
    ("Two Buttons", "https://i.imgflip.com/1g8my4.jpg"),
    ("Change My Mind", "https://i.imgflip.com/24y43o.jpg"),
    ("One Does Not Simply", "https://i.imgflip.com/1bij.jpg"),
]
IMAGE_SIZE_LIMIT = 8 * 1024 * 1024
MEDIA_OUTPUT_LIMIT = 7_500_000
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
        title, image_url = random.choice(MEMES)
        await self.send_image_attachment_embed(
            ctx,
            f"Meme - {title}",
            image_url,
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

    @commands.hybrid_command(name="roblox")
    async def roblox(self, ctx: commands.Context, username_or_id: str) -> None:
        profile = await self.fetch_roblox_profile(username_or_id)
        if profile is None:
            await ctx.send(embed=code_embed("Roblox", "Roblox user not found.", status="warning"))
            return
        item = embed(profile["name"], profile.get("description") or "No Roblox description set.")
        item.url = f"https://www.roblox.com/users/{profile['id']}/profile"
        item.add_field(name="User ID", value=str(profile["id"]), inline=True)
        item.add_field(name="Display Name", value=profile.get("displayName") or profile["name"], inline=True)
        item.add_field(name="Created", value=str(profile.get("created", "unknown"))[:32], inline=True)
        item.add_field(name="Banned", value="Yes" if profile.get("isBanned") else "No", inline=True)
        if profile.get("avatar"):
            item.set_thumbnail(url=profile["avatar"])
        await ctx.send(embed=item)

    @commands.hybrid_command(name="togif")
    async def togif(
        self,
        ctx: commands.Context,
        image: discord.Attachment | None = None,
        image_url: str | None = None,
    ) -> None:
        media = await self.resolve_media_bytes(ctx, image, image_url)
        if media is None:
            await ctx.send(embed=code_embed("Image To GIF", "Attach an image, reply to an image, or pass an image URL.", status="warning"))
            return
        try:
            gif_bytes = self.convert_image_to_gif(media)
        except ValueError as exc:
            await ctx.send(embed=code_embed("Image To GIF", str(exc), status="error"))
            return
        await ctx.send(
            embed=embed("Image To GIF", "Converted image to GIF.", status="success"),
            file=discord.File(io.BytesIO(gif_bytes), filename="phpelefant.gif"),
        )

    @commands.hybrid_command(name="caption")
    async def caption(
        self,
        ctx: commands.Context,
        top_text: str,
        bottom_text: str = "",
        image: discord.Attachment | None = None,
        image_url: str | None = None,
    ) -> None:
        media = await self.resolve_media_bytes(ctx, image, image_url)
        if media is None:
            await ctx.send(embed=code_embed("Caption", "Attach an image/GIF, reply to one, or pass an image URL.", status="warning"))
            return
        try:
            output = self.caption_media(media, top_text, bottom_text)
        except ValueError as exc:
            await ctx.send(embed=code_embed("Caption", str(exc), status="error"))
            return
        filename = "caption.gif" if output[:6] in {b"GIF87a", b"GIF89a"} else "caption.png"
        await ctx.send(
            embed=embed("Caption", "Caption rendered.", status="success"),
            file=discord.File(io.BytesIO(output), filename=filename),
        )

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

    async def fetch_roblox_profile(self, username_or_id: str) -> dict | None:
        value = username_or_id.strip()
        async with aiohttp.ClientSession() as session:
            if value.isdigit():
                user_id = int(value)
            else:
                async with session.post(
                    "https://users.roblox.com/v1/usernames/users",
                    json={"usernames": [value], "excludeBannedUsers": False},
                    timeout=12,
                ) as response:
                    response.raise_for_status()
                    payload = await response.json()
                users = payload.get("data", [])
                if not users:
                    return None
                user_id = int(users[0]["id"])

            async with session.get(f"https://users.roblox.com/v1/users/{user_id}", timeout=12) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                profile = await response.json()

            async with session.get(
                "https://thumbnails.roblox.com/v1/users/avatar-headshot",
                params={"userIds": user_id, "size": "420x420", "format": "Png", "isCircular": "false"},
                timeout=12,
            ) as response:
                response.raise_for_status()
                thumbs = await response.json()
        data = thumbs.get("data", [])
        if data and isinstance(data[0], dict):
            profile["avatar"] = data[0].get("imageUrl")
        return profile

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

    async def resolve_media_bytes(
        self,
        ctx: commands.Context,
        attachment: discord.Attachment | None,
        image_url: str | None,
    ) -> bytes | None:
        candidate = attachment
        if candidate is None and ctx.message.attachments:
            candidate = ctx.message.attachments[0]
        if candidate is None and ctx.message.reference and ctx.message.reference.message_id:
            try:
                referenced = ctx.message.reference.resolved
                if not isinstance(referenced, discord.Message):
                    referenced = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if referenced.attachments:
                    candidate = referenced.attachments[0]
            except discord.DiscordException:
                candidate = None
        if candidate is not None:
            if candidate.size > IMAGE_SIZE_LIMIT:
                return None
            try:
                return await candidate.read()
            except discord.DiscordException:
                return None
        if image_url:
            return await self.download_bytes(image_url)
        return None

    def convert_image_to_gif(self, media: bytes) -> bytes:
        try:
            with Image.open(io.BytesIO(media)) as image:
                frames = [frame.convert("RGBA") for frame in ImageSequence.Iterator(image)]
                if not frames:
                    raise ValueError("No image frames found.")
                durations = [frame.info.get("duration", image.info.get("duration", 90)) for frame in ImageSequence.Iterator(image)]
                output = io.BytesIO()
                frames[0].save(
                    output,
                    format="GIF",
                    save_all=True,
                    append_images=frames[1:80],
                    duration=durations[:80] or 90,
                    loop=0,
                    disposal=2,
                )
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("That file is not a supported image.") from exc
        data = output.getvalue()
        if len(data) > MEDIA_OUTPUT_LIMIT:
            raise ValueError("Converted GIF is too large for Discord.")
        return data

    def caption_media(self, media: bytes, top_text: str, bottom_text: str = "") -> bytes:
        top_text = top_text.strip()[:160]
        bottom_text = bottom_text.strip()[:160]
        if not top_text and not bottom_text:
            raise ValueError("Caption text cannot be empty.")
        try:
            with Image.open(io.BytesIO(media)) as image:
                is_animated = getattr(image, "is_animated", False)
                frames = []
                durations = []
                for index, frame in enumerate(ImageSequence.Iterator(image)):
                    if index >= 80:
                        break
                    frames.append(self.caption_frame(frame.convert("RGBA"), top_text, bottom_text))
                    durations.append(frame.info.get("duration", image.info.get("duration", 90)))
                if not frames:
                    raise ValueError("No image frames found.")
                output = io.BytesIO()
                if is_animated or len(frames) > 1:
                    frames[0].save(
                        output,
                        format="GIF",
                        save_all=True,
                        append_images=frames[1:],
                        duration=durations or 90,
                        loop=0,
                        disposal=2,
                    )
                else:
                    frames[0].save(output, format="PNG")
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("That file is not a supported image or GIF.") from exc
        data = output.getvalue()
        if len(data) > MEDIA_OUTPUT_LIMIT:
            raise ValueError("Captioned media is too large for Discord.")
        return data

    def caption_frame(self, image: Image.Image, top_text: str, bottom_text: str) -> Image.Image:
        image = ImageOps.exif_transpose(image)
        width, height = image.size
        font = self.caption_font(max(18, min(54, width // 10)))
        draw = ImageDraw.Draw(image)
        top_lines = self.wrap_caption(draw, top_text, font, width - 32) if top_text else []
        bottom_lines = self.wrap_caption(draw, bottom_text, font, width - 32) if bottom_text else []
        line_height = max(22, int(font.size * 1.25) if hasattr(font, "size") else 24)
        band_top = (len(top_lines) * line_height + 24) if top_lines else 0
        band_bottom = (len(bottom_lines) * line_height + 24) if bottom_lines else 0
        canvas = Image.new("RGBA", (width, height + band_top + band_bottom), "white")
        canvas.alpha_composite(image, (0, band_top))
        draw = ImageDraw.Draw(canvas)
        self.draw_caption_lines(draw, top_lines, font, width, 12)
        self.draw_caption_lines(draw, bottom_lines, font, width, band_top + height + 12)
        return canvas

    @staticmethod
    def caption_font(size: int) -> ImageFont.ImageFont:
        for path in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ):
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
        return ImageFont.load_default()

    @staticmethod
    def wrap_caption(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            left, _, right, _ = draw.textbbox((0, 0), candidate, font=font)
            if right - left <= max_width or not current:
                current = candidate
                continue
            lines.append(current)
            current = word
        if current:
            lines.append(current)
        return lines[:4]

    @staticmethod
    def draw_caption_lines(draw: ImageDraw.ImageDraw, lines: list[str], font: ImageFont.ImageFont, width: int, y: int) -> None:
        for line in lines:
            left, top, right, bottom = draw.textbbox((0, 0), line, font=font)
            x = max(8, (width - (right - left)) // 2)
            draw.text((x + 2, y + 2), line, fill="black", font=font)
            draw.text((x, y), line, fill="black", font=font)
            y += max(22, (bottom - top) + 8)

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
