# PHPelefant Discord

This directory contains the Discord conversion of PHPelefant. It is a separate Python `discord.py 2.x` project with modular cogs, persistent storage, embeds/code-block output, moderation, anti-spam, activity tracking, fun commands, owner controls, and real shell execution through an unprivileged OS user.

Defaults:

- Bot name: `PHPelefant`
- Owner Discord user ID: `1435161291365814325`
- Official server ID: `1505254579715964978`
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
      channel_edit.py
      events.py
      fun.py
      moderation.py
      owner.py
      settings.py
      tickets.py
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
      channel_names.py
      formatting.py
      permissions.py
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
- Manage Nicknames
- Manage Roles
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

- Owner `1435161291365814325` always has shell access.
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
- `fakeban`
- `unban`
- `kick`
- `mute`
- `unmute`
- `warn`
- `warnings`
- `resetwarnings`
- `warnconfig`
- `modlogs`
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
- `nick`
- `addrole`
- `removerole`

Channel/category bulk editor:

- Slash command:

```text
/edit type:channels deletechars:true deletetoindex:3 keepemojis:true surroundsymbol1:【 surroundsymbol2:】
```

- Prefix command:

```text
!edit type:channels deletechars:true deletetoindex:3 keepemojis:true surroundsymbol1:【 sourroundsymbol2:】
```

Options:

- `type`: `channels`, `categories`, `all`, `text`, `voice`, `stage`, or `forum`
- `deletechars`: `true` or `false`
- `deletetoindex`: number of characters removed after preserved leading emojis
- `keepemojis`: preserves leading unicode/custom emojis before deleting characters
- `surroundsymbol1` and `surroundsymbol2`: wrap the final name
- `match`: optional substring filter
- `limit`: max targets, 1-100
- `preview`: `true` to show a dry run

Tickets:

- `ticket <reason>` opens a private support ticket
- `ticket setup [category] [log_channel] [staff_role]` configures the ticket system and uses the given staff role, or creates/reuses `Ticket Staff`
- `ticketsetup [category] [log_channel] [staff_role]` is a direct setup shortcut
- `ticket panel [channel] [description]` posts a persistent dropdown ticket panel
- `ticket categories [cat1 | cat2 | cat3]` shows or replaces dropdown categories
- `ticket close [reason]` closes the current ticket and saves a transcript
- `ticket claim` marks the current ticket as claimed by staff
- `ticket add <member>` adds a member to the current ticket
- `ticket remove <member>` removes a member from the current ticket
- `ticket transcript` exports a transcript without closing
- `ticket settings` shows current ticket settings
- `ticket enable`
- `ticket disable`

Ticket behavior:

- Ticket channels are named with the selected category, opener username, and ticket ID.
- Ticket channels are private to the opener, the bot, and the configured staff role.
- Ticket setup creates a `Ticket Staff` role when no role is supplied and the bot has Manage Roles.
- Server admins, users with Manage Channels/Manage Guild/Moderate Members, and the bot owner count as ticket staff.
- Dropdown panels persist across bot restarts.
- Opening a ticket pings the ticket staff role before posting the ticket intro embed.
- Closing a ticket posts the transcript to the configured log channel, DMs the opener with a close summary and transcript, tries to DM the closing staff member with a transcript copy, then deletes the ticket channel.
- One open ticket per user is enforced.

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
- `httpcat`
- `httpdog`
- `choose`
- `rate`
- `avatar`
- `poll`
- `quiz`

`quote` renders a Make-it-a-Quote-style image card. With prefix commands, reply to a message and run:

```text
!quote
```

For slash commands or non-reply usage, pass a message ID from the same channel:

```text
/quote message_id:123456789012345678
```

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
- `backupdb`
- `setofficialserver`
- `restart`
- `shutdown`

## Verification

```bash
python -m compileall phpelefant_discord tests
pytest
```
