# Ultroid - UserBot
# Copyright (C) 2021-2026 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://www.github.com/TeamUltroid/Ultroid/blob/main/LICENSE/>.

from . import *

START = """
**Dockyard Assistant**

Manage groups and use everyday tools from one place.

/start - Check assistant status
/help - Open this help menu
/repo - View the Dockyard source

Choose a category below.
"""

ADMINTOOLS = """**Admin tools**

/pin - Pin the replied message.
/pinned - Get the pinned message in the chat.
/unpin - Unpin the replied message.
/unpin all - Unpin all pinned messages.

/ban (username/id/reply) - Ban the user.
/unban (username/id/reply) - Unban the user.

/mute (username/id/reply) - Mute the user.
/unmute (username/id/reply) - Unmute the user.

/tban (username/id/reply) (time) - Temporarily ban a user.
/tmute (username/id/reply) (time) - Temporarily mute a user.

/purge - Purge messages.

/setgpic (reply photo) - Set the group photo.
/delgpic - Remove the current chat photo."""

UTILITIES = """
**Utilities**

/info (reply/username/id) - Get detailed information about a user.
/id - Get the chat or user ID.
/tr - Translate languages.
/q - Create quotes.

/paste (reply file/text) - Paste content on Spaceb.in.
/google (query) - Search Google.

/suggest (query/reply) - Create a yes/no poll.
"""

LOCKS = """
**Locks**

/lock (query) - Lock particular content in the chat.
/unlock (query) - Unlock particular content in the chat.

Available queries:
`msgs` - messages
`inlines` - inline queries
`media` - all media
`games` - games
`sticker` - stickers
`polls` - polls
`gif` - GIFs
`pin` - pinned messages
`changeinfo` - chat information changes
"""

MISC = """
**Miscellaneous**

/joke - Get a random joke.
/decide - Make a decision.

**Sticker tools**
/kang - Add a sticker to your pack.
/listpack - List your sticker packs.
"""

STRINGS = {"Admintools": ADMINTOOLS, "locks": LOCKS, "Utils": UTILITIES, "Misc": MISC}

CATEGORY_LABELS = {
    "Admintools": "Admin tools",
    "locks": "Locks",
    "Utils": "Utilities",
    "Misc": "Miscellaneous",
}


def get_buttons():
    BTTS = []
    keys = STRINGS.copy()
    while keys:
        BT = []
        for i in list(keys)[:2]:
            BT.append(Button.inline(CATEGORY_LABELS[i], f"hlp_{i}"))
            del keys[i]
        BTTS.append(BT)
    url = f"https://t.me/{asst.me.username}?startgroup=true"
    BTTS.append([Button.url("Add me to Group", url)])
    BTTS.append([Button.inline("Dashboard", "open")])
    return BTTS


@asst_cmd(pattern="help")
async def helpish(event):
    if not event.is_private:
        url = f"https://t.me/{asst.me.username}?start=start"
        return await event.reply(
            "Contact me in PM for help!", buttons=Button.url("Click me for Help", url)
        )
    if str(event.sender_id) in owner_and_sudos() and (
        udB.get_key("DUAL_MODE") and (udB.get_key("DUAL_HNDLR") == "/")
    ):
        return
    await event.reply(START, buttons=get_buttons())


@callback("mngbtn", owner=True)
async def ehwhshd(e):
    await e.edit(START, buttons=get_buttons())


@callback("mnghome")
async def home_aja(e):
    await e.edit(START, buttons=get_buttons())


@callback(re.compile("hlp_(.*)"))
async def do_something(event):
    match = event.pattern_match.group(1).strip().decode("utf-8")
    await event.edit(STRINGS[match], buttons=Button.inline("Back", "mnghome"))
