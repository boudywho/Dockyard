# Ultroid - UserBot
# Copyright (C) 2021-2026 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://www.github.com/TeamUltroid/Ultroid/blob/main/LICENSE/>.

import re

from . import *

STRINGS = {
    1: """**Welcome to Dockyard**

Your personal Telegram workspace is ready. This short guide covers the essentials.""",
    2: """**About Dockyard**

Dockyard is a modular Telegram userbot built with Telethon. It is a personalized fork of [TeamUltroid/Ultroid](https://github.com/TeamUltroid/Ultroid).

Source and support: [github.com/boudywho/Dockyard](https://github.com/boudywho/Dockyard)""",
    3: """**Getting started**

Use the dashboard to browse plugins, add-ons, voice-chat tools, settings, and updates.

Keep your session string, bot token, and database credentials private.""",
    4: f"""**Commands**

`{HNDLR}help` - open the dashboard
`{HNDLR}cmds` - list available command groups""",
    5: """**You are all set.**

For source, updates, or support, visit [Dockyard on GitHub](https://github.com/boudywho/Dockyard).""",
}


@callback(re.compile("initft_(\\d+)"))
async def init_depl(e):
    CURRENT = int(e.data_match.group(1))
    if CURRENT == 5:
        return await e.edit(
            STRINGS[5],
            buttons=Button.inline("Back", "initbk_4"),
            link_preview=False,
        )

    await e.edit(
        STRINGS[CURRENT],
        buttons=[
            Button.inline("Back", f"initbk_{str(CURRENT - 1)}"),
            Button.inline("Next", f"initft_{str(CURRENT + 1)}"),
        ],
        link_preview=False,
    )


@callback(re.compile("initbk_(\\d+)"))
async def ineiq(e):
    CURRENT = int(e.data_match.group(1))
    if CURRENT == 1:
        return await e.edit(
            STRINGS[1],
            buttons=Button.inline("Start again", "initft_2"),
            link_preview=False,
        )

    await e.edit(
        STRINGS[CURRENT],
        buttons=[
            Button.inline("Back", f"initbk_{str(CURRENT - 1)}"),
            Button.inline("Next", f"initft_{str(CURRENT + 1)}"),
        ],
        link_preview=False,
    )
