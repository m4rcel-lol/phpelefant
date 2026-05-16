from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from phpelefant_discord.config import Settings
from phpelefant_discord.db.models import ShellAllowedUser

try:
    import pwd
except ImportError:  # pragma: no cover
    pwd = None

SECRET_ENV_KEYS = {"DISCORD_TOKEN", "DATABASE_URL"}


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


def validate_shell_input(raw: str) -> str:
    command = raw.strip()
    if not command:
        raise ValueError("Use shell <command>.")
    if "\x00" in command:
        raise ValueError("NUL bytes are not allowed in shell commands.")
    if len(command) > 4000:
        raise ValueError("Shell command is too long.")
    return command


def sanitized_environment(settings: Settings) -> dict[str, str]:
    allowed_keys = {"HOME", "LANG", "LC_ALL", "PATH", "TERM", "TZ", "USER"}
    env = {key: value for key, value in os.environ.items() if key in allowed_keys and key not in SECRET_ENV_KEYS}
    env["PATH"] = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"
    env["SHELL"] = settings.shell_path
    return env


def redact_secrets(output: str, settings: Settings) -> str:
    redacted = output
    token = settings.token
    if token:
        redacted = redacted.replace(token, "[redacted DISCORD_TOKEN]")
    if settings.database_url:
        redacted = redacted.replace(settings.database_url, "[redacted DATABASE_URL]")
    return redacted


def process_is_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def current_username() -> str | None:
    if pwd is None or not hasattr(os, "geteuid"):
        return None
    try:
        return pwd.getpwuid(os.geteuid()).pw_name
    except KeyError:
        return None


def demote_to_runtime_user(settings: Settings):
    if pwd is None:
        raise ValueError("Cannot drop privileges on this platform.")
    try:
        runtime_user = pwd.getpwnam(settings.shell_runtime_user)
    except KeyError as exc:
        raise ValueError(f"Runtime user {settings.shell_runtime_user!r} does not exist.") from exc

    def demote() -> None:
        os.initgroups(runtime_user.pw_name, runtime_user.pw_gid)
        os.setgid(runtime_user.pw_gid)
        os.setuid(runtime_user.pw_uid)

    return demote


def ensure_non_root_shell_context(settings: Settings):
    if process_is_root():
        return demote_to_runtime_user(settings)
    if settings.shell_enforce_runtime_user:
        username = current_username()
        if username != settings.shell_runtime_user:
            raise ValueError(
                f"Shell execution requires the bot process to run as {settings.shell_runtime_user!r}; "
                f"current user is {username or 'unknown'}."
            )
    return None


async def run_real_shell(raw: str, settings: Settings) -> ShellResult:
    command = validate_shell_input(raw)
    cwd = Path(settings.shell_working_directory).expanduser().resolve()
    if not cwd.exists() or not cwd.is_dir():
        raise ValueError("Configured SHELL_WORKING_DIRECTORY does not exist or is not a directory.")
    shell = Path(settings.shell_path)
    if not shell.exists():
        raise ValueError(f"Configured shell {settings.shell_path!r} does not exist.")
    preexec_fn = ensure_non_root_shell_context(settings)
    try:
        process = await asyncio.create_subprocess_exec(
            str(shell),
            "-lc",
            command,
            cwd=str(cwd),
            env=sanitized_environment(settings),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=preexec_fn,
        )
    except OSError as exc:
        raise ValueError(f"Could not start shell: {exc.strerror or exc}") from exc
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=settings.shell_timeout_seconds)
    except TimeoutError:
        process.kill()
        stdout_bytes, stderr_bytes = await process.communicate()
        return ShellResult(
            command=command,
            return_code=None,
            stdout=redact_secrets(stdout_bytes.decode(errors="replace"), settings),
            stderr=redact_secrets(stderr_bytes.decode(errors="replace"), settings),
            timed_out=True,
        )
    return ShellResult(
        command=command,
        return_code=process.returncode,
        stdout=redact_secrets(stdout_bytes.decode(errors="replace"), settings),
        stderr=redact_secrets(stderr_bytes.decode(errors="replace"), settings),
    )

