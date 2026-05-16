# PHPelefant

PHPelefant is a production-oriented Telegram bot for community moderation, member activity, engagement, and owner-only administration.

Defaults:

- Bot owner Telegram user ID: `6104236913`
- Official channel ID: `-1003908421427`
- Runtime: Python 3.11+ with `aiogram 3.x`
- Database: PostgreSQL in production, SQLite for local development

## Folder Structure

```text
phpelefant/
  config.py                 Environment configuration
  main.py                   Bot entrypoint
  routers.py                Router assembly
  db/                       SQLAlchemy base, models, async sessions
  handlers/                 Telegram command and event handlers
  middlewares/              DB session, security, rate limit, anti-spam
  services/                 Moderation, activity, settings, backup, stats
  utils/                    Text, time, Telegram API helpers
migrations/                 Alembic migrations
tests/                      Unit tests for critical logic
```

## Setup

1. Create a bot with BotFather and copy its token.
2. Copy `.env.example` to `.env`.
3. Set `BOT_TOKEN`.
4. Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m phpelefant.main
```

SQLite works with the default `DATABASE_URL`. For PostgreSQL:

```env
DATABASE_URL=postgresql+asyncpg://phpelefant:phpelefant@localhost:5432/phpelefant
```

## Docker Deployment

```bash
cp .env.example .env
# edit .env and set BOT_TOKEN
docker compose up --build -d
```

The Docker entrypoint runs `alembic upgrade head` before starting polling.

## Required Telegram Admin Permissions

Add PHPelefant to the group and grant:

- Ban users
- Delete messages
- Restrict members
- Pin messages
- Manage chat, if using slowmode and chat permission locks

For official channel broadcasts or force-subscribe checks, add the bot to the official channel and grant enough access for membership checks and posting.

## Moderation Commands

- `/ban` reply or `/ban <user_id> [reason]`
- `/unban <user_id> [reason]`
- `/kick` reply or `/kick <user_id> [reason]`
- `/mute` reply or `/mute <user_id> [10m|1h|1d|7d] [reason]`
- `/unmute <user_id> [reason]`
- `/warn` reply or `/warn <user_id> [reason]`
- `/warnings` reply or `/warnings <user_id>`
- `/resetwarnings` reply or `/resetwarnings <user_id>`
- `/purge` reply to first message to delete through the command
- `/delete` reply to a message
- `/lock`, `/unlock`
- `/slowmode <0-3600>`
- `/rules`, `/setrules <text>`
- `/pin`, `/unpin`
- `/report` reply to a message
- `/adminlist`

Admins can moderate regular users. Regular users cannot use moderation commands. Owner ID `6104236913` overrides admin checks but still cannot be targeted.

## Anti-Spam

Automatic protections cover flooding, repeated messages, links, invite links, mention spam, emoji spam, caps spam, forwarded spam, bad words, and scam keywords.

Settings:

- `/antispam on|off`
- `/antilink on|off`
- `/anticaps on|off`
- `/badwords add <word>`
- `/badwords remove <word>`
- `/badwords list`
- `/whitelist add <user_id> [reason]`
- `/whitelist remove <user_id>`
- `/whitelist domain <domain>`
- `/whitelist list`

Admins, the owner, and whitelisted users are exempt from automatic punishments.

## Welcome and Goodbye

- `/setwelcome <message>`
- `/welcome on|off`
- `/setgoodbye <message>`
- `/goodbye on|off`

Supported placeholders: `{user}`, `{username}`, `{group}`, `{member_count}`, `{rules}`.

## Activity Commands

- `/rank`
- `/level`
- `/xp`
- `/leaderboard`
- `/top`
- `/activity`
- `/profile`

Messages award XP with a cooldown to reduce farming. Profiles include user ID, username, join date if known, message count, XP, level, warning count, and reputation score.

## Fun Commands

- `/joke`
- `/meme`
- `/quote`
- `/fact`
- `/8ball`
- `/coinflip`
- `/dice`
- `/roll [sides]`
- `/ship <names>`
- `/roast`
- `/compliment`
- `/hug`
- `/slap`
- `/cat`
- `/dog`
- `/poll Question | Option 1 | Option 2`
- `/quiz Question | Correct option number | Option 1 | Option 2`

Fun responses are static, safe, and public-group appropriate by default.

## Utility Commands

- `/start`
- `/help`
- `/about`
- `/id`
- `/userinfo`
- `/chatinfo`
- `/ping`
- `/uptime`
- `/stats`
- `/settings`
- `/language`
- `/timezone`

`/about` identifies the bot as PHPelefant and lists the official channel ID.

## Owner And Shell Commands

Only Telegram user ID `6104236913` can use these owner administration commands:

- `/owner`
- `/broadcast <message>`
- `/broadcastchannel <message>`
- `/statsglobal`
- `/leavechat <chat_id>`
- `/blacklistuser <user_id> <reason>`
- `/unblacklistuser <user_id>`
- `/blacklistchat <chat_id> <reason>`
- `/unblacklistchat <chat_id>`
- `/shellusers add <user_id> [note]`
- `/shellusers remove <user_id>`
- `/shellusers list`
- `/eval` disabled unless `ENABLE_EVAL=true`
- `/restart CONFIRM`
- `/shutdown CONFIRM`
- `/backupdb`
- `/setofficialchannel [channel_id]`

Ownership is checked only by numeric Telegram ID, never by username.

The owner and users added with `/shellusers add` can use `/shell <read-only command>`.

## Restricted Shell Access

The owner always has shell access. The owner can add trusted Telegram user IDs to the shell allowlist:

```text
/shellusers add 123456789 trusted operator
/shellusers remove 123456789
/shellusers list
```

Allowed users can run:

```text
/shell ls -la
/shell df -h
/shell tail -100 app.log
```

The shell runner is intentionally restricted:

- Uses `asyncio.create_subprocess_exec`, not `shell=True`.
- Allows only read-oriented commands such as `ls`, `cat`, `tail`, `head`, `rg`, `grep`, `find`, `ps`, `df`, `du`, `uptime`, and `whoami`.
- Rejects shell operators, pipes, redirects, command substitutions, explicit executable paths, and write-capable flags such as `find -delete` or `sed -i`.
- Runs as the same OS user as the bot process.
- Uses a sanitized environment and redacts configured bot token and database URL from command output.
- Enforces `SHELL_TIMEOUT_SECONDS` and `SHELL_OUTPUT_LIMIT`.

For stronger isolation, deploy the bot under a dedicated unprivileged OS user or inside a locked-down container with a read-only filesystem where practical. Application-level filtering reduces risk but cannot replace OS-level permissions.

## Force Subscribe

- `/forcesub on`
- `/forcesub off`
- `/forcesubstatus`

When enabled, fun and activity commands require membership in the configured official channel. If Telegram membership checks fail because the bot cannot access the channel, the user receives a generic configuration message.

## Database Schema

The Alembic migrations create:

- `users`
- `chats`
- `chat_settings`
- `warnings`
- `moderation_logs`
- `member_activity`
- `activity_daily`
- `blacklisted_users`
- `blacklisted_chats`
- `shell_allowed_users`
- `whitelisted_users`
- `whitelisted_domains`
- `bad_words`
- `broadcast_history`
- `bot_statistics`

Run migrations with:

```bash
alembic upgrade head
```

## Testing

```bash
pytest
python -m compileall phpelefant tests
```

## Security Notes

- Secrets are read from environment variables.
- Bot token is never logged.
- Owner commands are hard-gated to Telegram user ID `6104236913`.
- Shell allowlist changes are owner-only; the owner cannot be removed from shell access.
- Shell output is returned inside Telegram code blocks.
- `/eval` is disabled by default and should stay disabled outside an isolated developer environment.
- User input is validated before moderation actions.
- Telegram API failures are caught and converted into safe user-facing messages.
- Anti-spam punishments are skipped for owner, group admins, and whitelisted users.
- Dangerous process controls require explicit `CONFIRM`.
