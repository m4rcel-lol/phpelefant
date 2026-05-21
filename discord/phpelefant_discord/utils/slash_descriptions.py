from __future__ import annotations

from typing import Any

COMMAND_DESCRIPTIONS = {
    "start": "Show PHPelefant's purpose, owner, prefix, and official server.",
    "help": "Open the rich PHPelefant command directory.",
    "id": "Show Discord IDs for a user, server, and current channel.",
    "userinfo": "Show account and server information for a member.",
    "chatinfo": "Show information about the current Discord server.",
    "ping": "Check PHPelefant latency.",
    "uptime": "Show how long PHPelefant has been running.",
    "stats": "Show local bot statistics.",
    "settings": "Show server configuration and protection toggles.",
    "language": "Show the configured server language.",
    "timezone": "Show the configured server timezone.",
    "owner": "Open the owner control panel.",
    "broadcast": "Owner only: send a message to known targets.",
    "broadcastchannel": "Owner only: post an announcement to the official server channel.",
    "statsglobal": "Owner only: show global bot statistics and database status.",
    "leaveguild": "Owner only: make PHPelefant leave a server.",
    "blacklistuser": "Owner only: block a user from PHPelefant.",
    "unblacklistuser": "Owner only: unblock a user.",
    "blacklistguild": "Owner only: block a server from PHPelefant.",
    "unblacklistguild": "Owner only: unblock a server.",
    "shell": "Run a real restricted host shell command if you have shell access.",
    "shellusers": "Owner only: list users allowed to use shell.",
    "shellusers list": "Owner only: list users allowed to use shell.",
    "shellusers add": "Owner only: grant shell access to a user.",
    "shellusers remove": "Owner only: revoke shell access from a user.",
    "eval": "Owner only: run the disabled-by-default eval tool.",
    "shutdown": "Owner only: safely shut down PHPelefant.",
    "restart": "Owner only: request a deployment restart.",
    "backupdb": "Owner only: export the bot database.",
    "setofficialserver": "Owner only: update the configured official server ID.",
    "rank": "Show your or another member's rank, XP, and level.",
    "leaderboard": "Show the server activity leaderboard.",
    "activity": "Show top daily and weekly activity.",
    "profile": "Show a member profile with XP, warnings, and reputation.",
    "setwelcome": "Set the server welcome message.",
    "welcome": "Enable or disable welcome messages.",
    "setgoodbye": "Set the server goodbye message.",
    "goodbye": "Enable or disable goodbye messages.",
    "joke": "Send a safe programming joke.",
    "meme": "Send a meme image with optional text.",
    "quote": "Render a replied-to message as a quote card.",
    "fact": "Send a useful community or tech fact.",
    "8ball": "Ask the magic 8-ball a question.",
    "coinflip": "Flip a coin.",
    "dice": "Roll a six-sided die.",
    "roll": "Roll a die with a custom side count.",
    "ship": "Calculate a playful compatibility score.",
    "roast": "Send a safe light roast.",
    "compliment": "Send a compliment to a member.",
    "hug": "Send a friendly hug message.",
    "slap": "Send a harmless slap message.",
    "cat": "Send a cat image.",
    "dog": "Send a dog image.",
    "httpcat": "Send an HTTP cat image for a status code.",
    "httpdog": "Send an HTTP dog image for a status code.",
    "choose": "Pick one option from a pipe-separated list.",
    "rate": "Rate something from 0 to 100.",
    "avatar": "Show a member avatar.",
    "roblox": "Look up a Roblox profile by username or user ID.",
    "togif": "Convert an attached image or image URL to GIF.",
    "caption": "Add a caption to an attached image or GIF.",
    "poll": "Create a reaction poll.",
    "quiz": "Post a simple quiz prompt and answer.",
    "setlogchannel": "Set or clear the moderation log channel.",
    "setwarnlimit": "Set the warning limit before auto-action.",
    "antispam": "Enable or disable anti-spam protection.",
    "antilink": "Enable or disable anti-link protection.",
    "anticaps": "Enable or disable anti-caps protection.",
    "forcesub": "Enable or disable official-server membership checks.",
    "forcesubstatus": "Show force-subscribe configuration.",
    "badwords": "List configured bad words.",
    "badwords list": "List configured bad words.",
    "badwords add": "Add a bad word filter entry.",
    "badwords remove": "Remove a bad word filter entry.",
    "whitelist": "List whitelisted users and domains.",
    "whitelist list": "List whitelisted users and domains.",
    "whitelist add": "Whitelist a trusted user.",
    "whitelist remove": "Remove a user from the whitelist.",
    "whitelist domain": "Whitelist a trusted domain.",
    "ban": "Ban a member and log the action.",
    "fakeban": "Send a fake ban notice without banning the member.",
    "unban": "Unban a user ID.",
    "kick": "Kick a member and log the action.",
    "mute": "Timeout a member for a duration.",
    "unmute": "Remove a member timeout.",
    "warn": "Warn a member and apply warn-limit actions.",
    "warnings": "Show active warnings for a member.",
    "resetwarnings": "Clear active warnings for a member.",
    "purge": "Bulk delete recent messages.",
    "delete": "Delete a message by ID.",
    "lock": "Lock the current channel.",
    "unlock": "Unlock the current channel.",
    "slowmode": "Set current channel slowmode.",
    "rules": "Show server rules.",
    "setrules": "Update server rules.",
    "pin": "Pin a message by ID.",
    "unpin": "Unpin a message by ID.",
    "report": "Report a message to configured staff logs.",
    "adminlist": "List cached administrators.",
    "nick": "Change or reset a member nickname.",
    "addrole": "Add a role to a member.",
    "removerole": "Remove a role from a member.",
    "warnconfig": "Configure warning limit action.",
    "modlogs": "Show recent moderation logs.",
    "edit": "Bulk edit channel or category names.",
    "announcefeed": "List configured announcement feeds.",
    "announcefeed list": "List configured announcement feeds.",
    "announcefeed add": "Add an RSS, Atom, JSON, blog, or Akkoma announcement feed.",
    "announcefeed remove": "Remove an announcement feed by ID.",
    "announcefeed check": "Poll configured announcement feeds now.",
    "music": "Music player controls.",
    "music join": "Join your current voice or stage channel.",
    "music play": "Queue and play a song URL or searchable query.",
    "music playlist": "Queue up to 25 tracks from a playlist URL.",
    "music pause": "Pause the current song.",
    "music resume": "Resume paused playback.",
    "music stop": "Stop playback and clear the music queue.",
    "music skip": "Skip the current song or multiple songs.",
    "music queue": "Show the current music queue.",
    "music remove": "Remove a queued song by position.",
    "music clear": "Clear queued songs without stopping current playback.",
    "music shuffle": "Shuffle queued songs.",
    "music loop": "Toggle or set current-track looping.",
    "music volume": "Show or set music volume from 0 to 200 percent.",
    "music nowplaying": "Show the currently playing track.",
    "music leave": "Disconnect PHPelefant from voice.",
    "ticket": "Open a private support ticket.",
    "ticket open": "Open a private support ticket.",
    "ticket setup": "Configure tickets with category ID, log channel, and staff role.",
    "ticket panel": "Post a dropdown ticket panel.",
    "ticket close": "Close the current ticket and send transcripts.",
    "ticket claim": "Claim the current ticket.",
    "ticket add": "Add a member to the current ticket.",
    "ticket remove": "Remove a member from the current ticket.",
    "ticket transcript": "Export a ticket transcript.",
    "ticket settings": "Show ticket system settings.",
    "ticket categories": "Show or replace ticket dropdown categories.",
    "ticket enable": "Enable ticket creation.",
    "ticket disable": "Disable ticket creation.",
    "ticketsetup": "Configure tickets with a category ID and staff role.",
}

PARAMETER_DESCRIPTIONS = {
    "member": "The server member to target.",
    "target": "The member to inspect or target.",
    "user": "The Discord user to target.",
    "user_id": "The Discord user ID.",
    "guild_id": "The Discord server ID.",
    "server_id": "The Discord server ID.",
    "reason": "Reason shown in logs and responses.",
    "duration": "Duration such as 10m, 1h, 1d, or 7d.",
    "limit": "Maximum number of items to process.",
    "message_id": "The Discord message ID.",
    "message": "Message text to send.",
    "command": "Shell command to execute.",
    "expr": "Expression to evaluate when enabled.",
    "confirm": "Confirmation keyword.",
    "text": "Text content to save or send.",
    "value": "Use on or off.",
    "channel": "Discord text channel.",
    "dm_user": "Whether to DM new members the welcome message.",
    "log_channel": "Channel where logs and transcripts are sent.",
    "staff_role": "Role allowed to manage tickets.",
    "category_id": "Discord category ID for ticket channels.",
    "categories": "Ticket categories separated by | characters.",
    "description": "Text shown on the ticket panel.",
    "style": "Panel style: dropdown or buttons.",
    "feed_id": "Announcement feed ID.",
    "feed_url": "RSS, Atom, JSON, blog, or Akkoma feed URL.",
    "name": "Display name for this item.",
    "song_url": "Song URL or searchable query.",
    "playlist_url": "Playlist URL.",
    "percent": "Volume percentage from 0 to 200.",
    "count": "Number of songs to skip.",
    "position": "Queue position number.",
    "image": "Image or GIF attachment.",
    "image_url": "Direct image or GIF URL.",
    "top_text": "Caption text shown above the media.",
    "bottom_text": "Optional caption text shown below the media.",
    "username_or_id": "Roblox username or numeric user ID.",
    "category": "Ticket category selected by users.",
    "role": "Discord role to add or remove.",
    "nickname": "New nickname, or blank to reset.",
    "seconds": "Slowmode delay in seconds.",
    "action": "Action to perform.",
    "timeout_minutes": "Warn-limit timeout length in minutes.",
    "status": "HTTP status code.",
    "sides": "Number of sides on the die.",
    "names": "Names or text to compare.",
    "question": "Question text.",
    "answer": "Answer text.",
    "option1": "First poll option.",
    "option2": "Second poll option.",
    "option3": "Optional third poll option.",
    "option4": "Optional fourth poll option.",
    "options": "Options separated with | characters.",
    "thing": "Thing to rate.",
    "word": "Word or phrase to manage.",
    "domain": "Domain name to whitelist.",
    "note": "Administrative note.",
    "type": "Target type such as channels, categories, all, text, voice, stage, or forum.",
    "target_type": "Channels, categories, all, text, voice, stage, or forum.",
    "deletechars": "Whether to delete leading characters.",
    "deletetoindex": "Number of leading characters to remove.",
    "keepemojis": "Preserve leading emoji before editing names.",
    "surroundsymbol1": "Prefix to wrap around the new name.",
    "surroundsymbol2": "Suffix to wrap around the new name.",
    "sourroundsymbol2": "Typo-compatible suffix alias.",
    "match": "Only edit names containing this text.",
    "preview": "Show changes without editing Discord.",
}


def qualified_name(command: Any) -> str:
    if getattr(command, "qualified_name", None):
        return str(command.qualified_name)
    names = [str(getattr(command, "name", ""))]
    parent = getattr(command, "parent", None)
    while parent is not None:
        names.append(str(getattr(parent, "name", "")))
        parent = getattr(parent, "parent", None)
    return " ".join(reversed([name for name in names if name]))


def set_private_or_public_description(target: Any, description: str) -> None:
    value = description[:100]
    for attribute in ("description", "_description"):
        try:
            setattr(target, attribute, value)
        except (AttributeError, TypeError):
            continue


def set_parameter_description(parameter: Any, description: str) -> None:
    value = description[:100]
    for attribute in ("description", "_description"):
        try:
            setattr(parameter, attribute, value)
        except (AttributeError, TypeError):
            continue


def apply_slash_descriptions(tree: Any) -> None:
    for command in tree.walk_commands():
        key = qualified_name(command)
        description = COMMAND_DESCRIPTIONS.get(key) or COMMAND_DESCRIPTIONS.get(str(getattr(command, "name", "")))
        if description:
            set_private_or_public_description(command, description)

        for parameter in getattr(command, "parameters", ()):
            name = str(getattr(parameter, "name", getattr(parameter, "display_name", "")))
            parameter_description = PARAMETER_DESCRIPTIONS.get(name)
            if parameter_description:
                set_parameter_description(parameter, parameter_description)
