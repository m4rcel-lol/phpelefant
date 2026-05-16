from __future__ import annotations

import random

import discord
from discord.ext import commands

from phpelefant_discord.bot import PHPelefantBot
from phpelefant_discord.utils.formatting import code_embed, embed, image_embed

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


class Fun(commands.Cog):
    def __init__(self, bot: PHPelefantBot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="joke")
    async def joke(self, ctx: commands.Context) -> None:
        await ctx.send(embed=code_embed("Joke", random.choice(JOKES)))

    @commands.hybrid_command(name="meme")
    async def meme(self, ctx: commands.Context) -> None:
        await ctx.send(embed=image_embed("Meme", "https://i.imgflip.com/1bij.jpg"))

    @commands.hybrid_command(name="quote")
    async def quote(self, ctx: commands.Context) -> None:
        await ctx.send(embed=code_embed("Quote", random.choice(QUOTES)))

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
        await ctx.send(embed=image_embed("Cat", "https://cataas.com/cat"))

    @commands.hybrid_command(name="dog")
    async def dog(self, ctx: commands.Context) -> None:
        await ctx.send(embed=image_embed("Dog", "https://placedog.net/640/480?random"))

    @commands.hybrid_command(name="poll")
    async def poll(self, ctx: commands.Context, question: str, option1: str, option2: str, option3: str | None = None, option4: str | None = None) -> None:
        options = [option for option in (option1, option2, option3, option4) if option]
        message = await ctx.send(embed=embed("Poll", f"**{question}**\n" + "\n".join(f"{i}. {option}" for i, option in enumerate(options, start=1))))
        for emoji in ("1️⃣", "2️⃣", "3️⃣", "4️⃣")[: len(options)]:
            await message.add_reaction(emoji)

    @commands.hybrid_command(name="quiz")
    async def quiz(self, ctx: commands.Context, question: str, answer: str) -> None:
        await ctx.send(embed=code_embed("Quiz", f"Quiz: {question}\nAnswer: {answer}"))


async def setup(bot: PHPelefantBot) -> None:
    await bot.add_cog(Fun(bot))
