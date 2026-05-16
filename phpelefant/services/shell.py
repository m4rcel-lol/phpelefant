from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
from pathlib import Path
import shlex

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant.config import Settings
from phpelefant.db.models import ShellAllowedUser

READ_ONLY_COMMANDS = {
    "cat",
    "date",
    "df",
    "du",
    "find",
    "grep",
    "head",
    "hostname",
    "id",
    "ls",
    "netstat",
    "pgrep",
    "ps",
    "pwd",
    "rg",
    "sed",
    "ss",
    "stat",
    "tail",
    "uname",
    "uptime",
    "wc",
    "whoami",
}
FORBIDDEN_TOKENS = {"|", "||", "&", "&&", ";", ">", ">>", "<", "<<", "`", "$(", "${"}
SECRET_ENV_KEYS = {"BOT_TOKEN", "DATABASE_URL"}
FORBIDDEN_ARGS_BY_COMMAND = {
    "find": {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf"},
    "sed": {"-i", "--in-place"},
}


@dataclass(slots=True)
class ShellResult:
    command: str
    return_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False


async def is_shell_allowed(session: AsyncSession, user_id: int, settings: Settings) -> bool:
    if user_id == settings.bot_owner_id:
        return True
    return await session.get(ShellAllowedUser, user_id) is not None


async def list_shell_users(session: AsyncSession, settings: Settings) -> list[int]:
    result = await session.scalars(select(ShellAllowedUser.user_id).order_by(ShellAllowedUser.user_id))
    users = list(result)
    if settings.bot_owner_id not in users:
        users.insert(0, settings.bot_owner_id)
    return users


async def add_shell_user(session: AsyncSession, user_id: int, added_by: int, note: str | None = None) -> None:
    row = await session.get(ShellAllowedUser, user_id)
    if row is None:
        session.add(ShellAllowedUser(user_id=user_id, added_by=added_by, note=note))
    else:
        row.added_by = added_by
        row.note = note


async def remove_shell_user(session: AsyncSession, user_id: int) -> None:
    row = await session.get(ShellAllowedUser, user_id)
    if row is not None:
        await session.delete(row)


def parse_shell_command(raw: str) -> list[str]:
    if not raw.strip():
        raise ValueError("Use /shell <read-only command>.")
    if any(token in raw for token in FORBIDDEN_TOKENS):
        raise ValueError("Shell operators, pipes, redirects, and expansions are not allowed.")
    try:
        argv = shlex.split(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid command quoting: {exc}") from exc
    if not argv:
        raise ValueError("Use /shell <read-only command>.")
    command = Path(argv[0]).name
    if command not in READ_ONLY_COMMANDS:
        allowed = ", ".join(sorted(READ_ONLY_COMMANDS))
        raise ValueError(f"Command is not allowed. Allowed commands: {allowed}")
    if argv[0] != command and "/" in argv[0]:
        raise ValueError("Use command names from PATH, not explicit filesystem paths.")
    forbidden_args = FORBIDDEN_ARGS_BY_COMMAND.get(command, set())
    for arg in argv[1:]:
        if arg in forbidden_args or any(arg.startswith(forbidden + "=") for forbidden in forbidden_args):
            raise ValueError(f"Argument {arg!r} is not allowed for {command}.")
    return [command, *argv[1:]]


def sanitized_environment() -> dict[str, str]:
    allowed_keys = {"HOME", "LANG", "LC_ALL", "PATH", "TERM", "TZ", "USER"}
    env = {key: value for key, value in os.environ.items() if key in allowed_keys and key not in SECRET_ENV_KEYS}
    env["PATH"] = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"
    return env


def redact_secrets(output: str, settings: Settings) -> str:
    redacted = output
    token = settings.token
    if token:
        redacted = redacted.replace(token, "[redacted BOT_TOKEN]")
    database_url = settings.database_url
    if database_url:
        redacted = redacted.replace(database_url, "[redacted DATABASE_URL]")
    return redacted


async def run_restricted_shell(raw: str, settings: Settings) -> ShellResult:
    argv = parse_shell_command(raw)
    cwd = Path(settings.shell_working_directory).expanduser().resolve()
    if not cwd.exists() or not cwd.is_dir():
        raise ValueError("Configured SHELL_WORKING_DIRECTORY does not exist or is not a directory.")
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(cwd),
            env=sanitized_environment(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise ValueError(f"Could not start command: {exc.strerror or exc}") from exc
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=settings.shell_timeout_seconds)
    except TimeoutError:
        process.kill()
        stdout_bytes, stderr_bytes = await process.communicate()
        return ShellResult(
            command=" ".join(shlex.quote(part) for part in argv),
            return_code=None,
            stdout=redact_secrets(stdout_bytes.decode(errors="replace"), settings),
            stderr=redact_secrets(stderr_bytes.decode(errors="replace"), settings),
            timed_out=True,
        )
    return ShellResult(
        command=" ".join(shlex.quote(part) for part in argv),
        return_code=process.returncode,
        stdout=redact_secrets(stdout_bytes.decode(errors="replace"), settings),
        stderr=redact_secrets(stderr_bytes.decode(errors="replace"), settings),
    )
