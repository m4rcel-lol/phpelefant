from __future__ import annotations

import random

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from phpelefant.handlers._helpers import command_args
from phpelefant.utils.text import html_escape

router = Router(name="fun")

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
    "Telegram bots can moderate groups only when granted the required admin permissions.",
    "PostgreSQL supports transactional DDL, which makes migrations safer.",
]
COMPLIMENTS = ["sharp", "helpful", "reliable", "excellent"]
SAFE_ROASTS = ["Your code has more TODOs than a Monday standup.", "You type like the keyboard owes you money."]


@router.message(Command("joke"))
async def joke(message: Message) -> None:
    await message.answer(random.choice(JOKES))


@router.message(Command("meme"))
async def meme(message: Message) -> None:
    await message.answer_photo("https://i.imgflip.com/1bij.jpg", caption="Safe dev meme.")


@router.message(Command("quote"))
async def quote(message: Message) -> None:
    await message.answer(random.choice(QUOTES))


@router.message(Command("fact"))
async def fact(message: Message) -> None:
    await message.answer(random.choice(FACTS))


@router.message(Command("8ball"))
async def eight_ball(message: Message) -> None:
    await message.answer(random.choice(["Yes.", "No.", "Ask again later.", "It is likely.", "Do not count on it."]))


@router.message(Command("coinflip"))
async def coinflip(message: Message) -> None:
    await message.answer(random.choice(["Heads", "Tails"]))


@router.message(Command("dice"))
async def dice(message: Message) -> None:
    await message.answer_dice()


@router.message(Command("roll"))
async def roll(message: Message, command: CommandObject) -> None:
    sides = 6
    args = command_args(command)
    if args:
        try:
            sides = int(args)
        except ValueError:
            await message.answer("Use /roll or /roll <sides>.")
            return
    if not 2 <= sides <= 100000:
        await message.answer("Sides must be between 2 and 100000.")
        return
    await message.answer(f"Rolled <code>{random.randint(1, sides)}</code> on a d{sides}.")


@router.message(Command("ship"))
async def ship(message: Message, command: CommandObject) -> None:
    names = command_args(command) or "PHP elefant"
    await message.answer(f"Compatibility for {html_escape(names)}: <code>{random.randint(1, 100)}%</code>")


@router.message(Command("roast"))
async def roast(message: Message) -> None:
    await message.answer(random.choice(SAFE_ROASTS))


@router.message(Command("compliment"))
async def compliment(message: Message) -> None:
    target = message.reply_to_message.from_user.full_name if message.reply_to_message and message.reply_to_message.from_user else "You"
    await message.answer(f"{html_escape(target)} are {random.choice(COMPLIMENTS)}.")


@router.message(Command("hug"))
async def hug(message: Message) -> None:
    target = message.reply_to_message.from_user.full_name if message.reply_to_message and message.reply_to_message.from_user else "the community"
    await message.answer(f"Hug sent to {html_escape(target)}.")


@router.message(Command("slap"))
async def slap(message: Message) -> None:
    target = message.reply_to_message.from_user.full_name if message.reply_to_message and message.reply_to_message.from_user else "the bug"
    await message.answer(f"A harmless slap was delivered to {html_escape(target)}.")


@router.message(Command("cat"))
async def cat(message: Message) -> None:
    await message.answer_photo("https://cataas.com/cat", caption="Cat.")


@router.message(Command("dog"))
async def dog(message: Message) -> None:
    await message.answer_photo("https://placedog.net/640/480?random", caption="Dog.")


@router.message(Command("poll"))
async def poll(message: Message, command: CommandObject, bot: Bot) -> None:
    args = command_args(command)
    parts = [part.strip() for part in args.split("|") if part.strip()]
    if len(parts) < 3:
        await message.answer("Use /poll Question | Option 1 | Option 2 [| Option 3 ...].")
        return
    question, options = parts[0][:300], [part[:100] for part in parts[1:11]]
    await bot.send_poll(message.chat.id, question=question, options=options, is_anonymous=False)


@router.message(Command("quiz"))
async def quiz(message: Message, command: CommandObject, bot: Bot) -> None:
    args = command_args(command)
    parts = [part.strip() for part in args.split("|") if part.strip()]
    if len(parts) < 4:
        await message.answer("Use /quiz Question | Correct option number | Option 1 | Option 2 [| Option 3 ...].")
        return
    try:
        correct = int(parts[1]) - 1
    except ValueError:
        await message.answer("Correct option number must be numeric.")
        return
    options = [part[:100] for part in parts[2:12]]
    if not 0 <= correct < len(options):
        await message.answer("Correct option number is outside the option range.")
        return
    await bot.send_poll(message.chat.id, question=parts[0][:300], options=options, type="quiz", correct_option_id=correct, is_anonymous=False)

