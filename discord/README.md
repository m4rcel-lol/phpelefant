# PHPelefant Discord

This directory contains the Discord conversion of PHPelefant. It is a separate Python `discord.py 2.x` project with modular cogs, persistent storage, embeds/code-block output, moderation, anti-spam, activity tracking, fun commands, owner controls, and real shell execution through an unprivileged OS user.

Defaults:

- Bot name: `PHPelefant`
- Owner Discord user ID: `6104236913`
- Runtime shell user: `phpelefant-env`
- Local database: SQLite
- Production database: PostgreSQL

## Structure

```text
discord/
  phpelefant_discord/
    bot.py
    main.py
    cogs/
      activity.py
      events.py
      fun.py
      moderation.py
      owner.py
      settings.py
      utility.py
      welcome.py
    db/
      models.py
      session.py
    services/
      activity.py
      antispam.py
      moderation.py
      settings.py
      shell.py
      stats.py
    utils/
      formatting.py
      text.py
      time.py
```

## Setup

Create a Discord application and bot in the Discord Developer Portal, enable these privileged gateway intents:

- Server Members Intent
- Message Content Intent

Invite the bot with scopes:

- `bot`
- `applications.commands`

Recommended bot permissions:

- Manage Messages
- Moderate Members
- Ban Members
- Kick Members
- Manage Channels
- Manage Guild
- Read Message History
- Send Messages
- Embed Links
- Add Reactions

Install locally:

```bash
cd discord
cp .env.example .env
# edit DISCORD_TOKEN
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m phpelefant_discord.main
```

## Docker

```bash
cd discord
cp .env.example .env
# edit DISCORD_TOKEN
docker compose up --build -d
```

The Docker image creates and runs as a non-root OS user named `phpelefant-env`.

## Real Shell

`shell <command>` uses a real OS shell:

```text
!shell fastfetch | head -40
!shell df -h
!shell sudo -n /sbin/apk add sl
```

Shell users:

```text
!shellusers add 123456789 trusted operator
!shellusers remove 123456789
!shellusers list
```

Security behavior:

- Owner `6104236913` always has shell access.
- Additional shell users are managed only by the owner.
- Shell subprocesses run as `phpelefant-env`, not root.
- If the bot process starts as root, shell subprocesses drop privileges to `phpelefant-env`.
- If the bot process is not root and not running as `phpelefant-env`, shell execution is refused when `SHELL_ENFORCE_RUNTIME_USER=true`.
- The bot does not collect sudo passwords.
- If you want package installs, configure sudoers on the host for the specific package manager commands.

## Commands

Most commands are hybrid commands, so they can work as slash commands after sync and as prefix commands with `!`.

Utility:

- `start`
- `help`
- `id`
- `userinfo`
- `chatinfo`
- `ping`
- `uptime`
- `stats`
- `settings`

Moderation:

- `ban`
- `unban`
- `kick`
- `mute`
- `unmute`
- `warn`
- `warnings`
- `resetwarnings`
- `purge`
- `delete`
- `lock`
- `unlock`
- `slowmode`
- `rules`
- `setrules`
- `pin`
- `unpin`
- `report`
- `adminlist`

Settings:

- `setlogchannel`
- `setwarnlimit`
- `antispam on|off`
- `antilink on|off`
- `anticaps on|off`
- `badwords add/remove/list`
- `whitelist add/remove/domain/list`
- `forcesub on|off`
- `forcesubstatus`

Welcome:

- `setwelcome`
- `welcome on|off`
- `setgoodbye`
- `goodbye on|off`

Activity:

- `rank`
- `level`
- `xp`
- `leaderboard`
- `top`
- `activity`
- `profile`

Fun:

- `joke`
- `meme`
- `quote`
- `fact`
- `8ball`
- `coinflip`
- `dice`
- `roll`
- `ship`
- `roast`
- `compliment`
- `hug`
- `slap`
- `cat`
- `dog`
- `poll`
- `quiz`

Owner:

- `owner`
- `broadcast`
- `broadcastchannel`
- `statsglobal`
- `leaveguild`
- `blacklistuser`
- `unblacklistuser`
- `blacklistguild`
- `unblacklistguild`
- `shell`
- `shellusers`
- `eval`
- `shutdown`

## Verification

```bash
python -m compileall phpelefant_discord tests
pytest
```

