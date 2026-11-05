# Ultroid - UserBot
# Copyright (C) 2021-2026 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://www.github.com/TeamUltroid/Ultroid/blob/main/LICENSE/>.

import ast
import asyncio
import re
import sys
import time
from asyncio.exceptions import TimeoutError as AsyncTimeOut
from os import execl, remove
from random import choice

from bs4 import BeautifulSoup as bs
from telethon import Button, events
from catbox import CatboxUploader
from telethon.tl.types import MessageMediaWebPage
from telethon.utils import get_peer_id

from pyUltroid.fns.helper import fast_download, progress
from pyUltroid.fns.tools import Carbon, async_searcher, get_paste, telegraph_client
from pyUltroid.paths import source_resource
from pyUltroid.security.updater import (
    check_for_update,
    format_changelog_report,
    format_update_report,
    request_deployment,
)
from pyUltroid.security.parsing import parse_bool
from pyUltroid.security.status import write_update_status

from . import *

# --------------------------------------------------------------------#
telegraph = telegraph_client()
uploader = CatboxUploader()
# --------------------------------------------------------------------#

def text_to_url(event):
    """function to get media url (with|without) Webpage"""
    if isinstance(event.media, MessageMediaWebPage):
        webpage = event.media.webpage
        if not isinstance(webpage, types.WebPageEmpty) and webpage.type in ["photo"]:
            return webpage.display_url
    return event.text


# --------------------------------------------------------------------#

_buttons = {
    "otvars": {
        "text": "Additional Dockyard settings:",
        "buttons": [
            [
                Button.inline("Tag Logger", data="taglog"),
                Button.inline("SuperFban", data="cbs_sfban"),
            ],
            [
                Button.inline("Sudo Mode", data="sudo"),
                Button.inline("Handler", data="hhndlr"),
            ],
            [
                Button.inline("Extra plugins", data="plg"),
                Button.inline("Add-ons", data="eaddon"),
            ],
            [
                Button.inline("Inline image", data="inli_pic"),
                Button.inline("Sudo handler", data="shndlr"),
            ],
            [Button.inline("Dual Mode", "cbs_oofdm")],
            [Button.inline("Back", data="setter")],
        ],
    },
    "sfban": {
        "text": "SuperFban Settings:",
        "buttons": [
            [Button.inline("FBan Group", data="sfgrp")],
            [Button.inline("Exclude Feds", data="abs_sfexf")],
            [Button.inline("Back", data="cbs_otvars")],
        ],
    },
    "apauto": {
        "text": "Automatically approve users when you send them a message.",
        "buttons": [
            [Button.inline("Enable auto-approve", data="apon")],
            [Button.inline("Disable auto-approve", data="apof")],
            [Button.inline("Back", data="cbs_pmcstm")],
        ],
    },
    "alvcstm": {
        "text": f"Customize `{HNDLR}alive`:",
        "buttons": [
            [Button.inline("Alive Text", data="abs_alvtx")],
            [Button.inline("Alive media", data="alvmed")],
            [Button.inline("Delete alive media", data="delmed")],
            [Button.inline("Back", data="setter")],
        ],
    },
    "pmcstm": {
        "text": "Customize PM permit:",
        "buttons": [
            [
                Button.inline("PM text", data="pmtxt"),
                Button.inline("PM media", data="pmmed"),
            ],
            [
                Button.inline("Auto Approve", data="cbs_apauto"),
                Button.inline("PM logger", data="pml"),
            ],
            [
                Button.inline("Warning limit", data="swarn"),
                Button.inline("Delete PM media", data="delpmmed"),
            ],
            [Button.inline("PMPermit Type", data="cbs_pmtype")],
            [Button.inline("Back", data="cbs_ppmset")],
        ],
    },
    "pmtype": {
        "text": "Select the type of PMPermit needed.",
        "buttons": [
            [Button.inline("Inline", data="inpm_in")],
            [Button.inline("Normal", data="inpm_no")],
            [Button.inline("Back", data="cbs_pmcstm")],
        ],
    },
    "ppmset": {
        "text": "PMPermit Settings:",
        "buttons": [
            [Button.inline("Turn PMPermit On", data="pmon")],
            [Button.inline("Turn PMPermit Off", data="pmoff")],
            [Button.inline("Customize PMPermit", data="cbs_pmcstm")],
            [Button.inline("Back", data="setter")],
        ],
    },
    "vcb": {
        "text": "Configure playback in group voice chats.",
        "buttons": [
            [Button.inline("VC Session", data="abs_vcs")],
            [Button.inline("Back", data="setter")],
        ],
    },
    "oofdm": {
        "text": "Configure dual mode.",
        "buttons": [
            [
                Button.inline("Dual Mode On", "dmon"),
                Button.inline("Dual Mode Off", "dmoff"),
            ],
            [Button.inline("Dual Mode Hndlr", "dmhn")],
            [Button.inline("Back", data="cbs_otvars")],
        ],
    },
    "apiset": {
        "text": get_string("ast_1"),
        "buttons": [
            [Button.inline("Remove.bg API", data="abs_rmbg")],
            [Button.inline("DEEP API", data="abs_dapi")],
            [Button.inline("OCR API", data="abs_oapi")],
            [Button.inline("Back", data="setter")],
        ],
    },
}

_convo = {
    "rmbg": {
        "var": "RMBG_API",
        "name": "Remove.bg API Key",
        "text": get_string("ast_2"),
        "back": "cbs_apiset",
    },
    "dapi": {
        "var": "DEEP_AI",
        "name": "Deep AI Api Key",
        "text": "Get a DeepAI API key from deepai.org and send it here.",
        "back": "cbs_apiset",
    },
    "oapi": {
        "var": "OCR_API",
        "name": "Ocr Api Key",
        "text": "Get an OCR API key from ocr.space and send it here.",
        "back": "cbs_apiset",
    },
    "pmlgg": {
        "var": "PMLOGGROUP",
        "name": "Pm Log Group",
        "text": "Send chat id of chat which you want to save as Pm log Group.",
        "back": "pml",
    },
    "vcs": {
        "var": "VC_SESSION",
        "name": "Vc Session",
        "text": "**VC session**\nEnter the new session generated for the voice-chat bot.\n\nUse /cancel to terminate the operation.",
        "back": "cbs_vcb",
    },
    "settag": {
        "var": "TAG_LOG",
        "name": "Tag Log Group",
        "text": f"Make a group, add your assistant and make it admin.\nGet the `{HNDLR}id` of that group and send it here for tag logs.\n\nUse /cancel to cancel.",
        "back": "taglog",
    },
    "alvtx": {
        "var": "ALIVE_TEXT",
        "name": "Alive Text",
        "text": "**Alive Text**\nEnter the new alive text.\n\nUse /cancel to terminate the operation.",
        "back": "cbs_alvcstm",
    },
    "sfexf": {
        "var": "EXCLUDE_FED",
        "name": "Excluded Fed",
        "text": "Send the Fed IDs you want to exclude in the ban. Split by a space.\neg`id1 id2 id3`\nSet is as `None` if you dont want any.\nUse /cancel to go back.",
        "back": "cbs_sfban",
    },
}


TOKEN_FILE = "resources/auths/auth_token.txt"


@callback(
    re.compile(
        "sndplug_(.*)",
    ),
    owner=True,
)
async def send(eve):
    key, name = (eve.data_match.group(1)).decode("UTF-8").split("_")
    thumb = str(source_resource("extras", "inline.jpg"))
    await eve.answer("Sending.")
    data = f"uh_{key}_"
    index = None
    if "|" in name:
        name, index = name.split("|")
    key = "plugins" if key == "Official" else key.lower()
    plugin = f"{key}/{name}.py"
    _ = f"pasta-{plugin}"
    if index is not None:
        data += f"|{index}"
        _ += f"|{index}"
    buttons = [
        [
            Button.inline(
                "« Paste »",
                data=_,
            )
        ],
        [
            Button.inline("Back", data=data),
        ],
    ]
    try:
        await eve.edit(file=plugin, thumb=thumb, buttons=buttons)
    except Exception as er:
        await eve.answer(str(er), alert=True)


@callback("updatenow", owner=True)
async def update(eve):
    state = await check_for_update()
    write_update_status(state)
    helper = udB.get_key("DOCKYARD_DEPLOY_HELPER") or os.environ.get(
        "DOCKYARD_DEPLOY_HELPER"
    )
    if not helper:
        return await eve.edit(
            format_update_report(state)
            + "\n\nNo privileged deployment helper is configured; this button "
            "cannot mutate the running checkout."
        )
    if state.dirty or not state.update_available:
        return await eve.edit(format_update_report(state))
    try:
        result = await request_deployment(str(helper))
    except (OSError, ValueError) as exc:
        LOGS.warning("Deployment helper request refused: %s", exc)
        return await eve.edit("`Deployment helper configuration was refused.`")
    if result.ok:
        return await eve.edit(
            "`Deployment was requested. The root-managed helper will activate "
            "only after preflight checks and will roll back on readiness failure.`"
        )
    await eve.edit("`The deployment helper rejected the request.`")

@callback(re.compile("changes(.*)"), owner=True)
async def changes(okk):
    okk.data_match.group(1).decode("utf-8")
    await okk.answer(get_string("clst_3"))
    state = await check_for_update()
    write_update_status(state)
    report, link = format_changelog_report(state)
    button = [[Button.inline("Update Now", data="updatenow")]]
    if link:
        button.append([Button.url("Release details", link)])
    await okk.edit(report, buttons=button)


@callback(
    re.compile(
        "pasta-(.*)",
    ),
    owner=True,
)
async def _(e):
    ok = (e.data_match.group(1)).decode("UTF-8")
    index = None
    if "|" in ok:
        ok, index = ok.split("|")
    with open(ok, "r") as hmm:
        _, data = await get_paste(hmm.read())
    if not data.get("link"):
        return await e.answer(key[:30], alert=True)
    if not key.startswith("http"):
        link, raw = data["link"], data["raw"]
    else:
        link = key
        raw = f"{key}/raw"
    if ok.startswith("addons"):
        key = "Addons"
    elif ok.startswith("vcbot"):
        key = "VCBot"
    else:
        key = "Official"
    data = f"uh_{key}_"
    if index is not None:
        data += f"|{index}"
    await e.edit(
        "",
        buttons=[
            [Button.url("Link", link), Button.url("Raw", raw)],
            [Button.inline("Back", data=data)],
        ],
    )


@callback(re.compile("cbs_(.*)"), owner=True)
async def _edit_to(event):
    match = event.data_match.group(1).decode("utf-8")
    data = _buttons.get(match)
    if not data:
        return
    await event.edit(data["text"], buttons=data["buttons"], link_preview=False)


@callback(re.compile("abs_(.*)"), owner=True)
async def convo_handler(event: events.CallbackQuery):
    match = event.data_match.group(1).decode("utf-8")
    if not _convo.get(match):
        return
    await event.delete()
    get_ = _convo[match]
    back = get_["back"]
    async with event.client.conversation(event.sender_id) as conv:
        await conv.send_message(get_["text"])
        response = await conv.get_response()
        themssg = response.message
        try:
            themssg = ast.literal_eval(themssg)
        except Exception:
            pass
        if themssg == "/cancel":
            return await conv.send_message(
                "Cancelled.",
                buttons=get_back_button(back),
            )
        await setit(event, get_["var"], themssg)
        await conv.send_message(
            f"{get_['name']} changed to `{themssg}`",
            buttons=get_back_button(back),
        )


async def _set_dual_mode(e, enabled):
    raw = udB.get_key("DUAL_MODE")
    if enabled:
        if not parse_bool(raw):
            udB.set_key("DUAL_MODE", "True")
    elif raw is not None:
        udB.del_key("DUAL_MODE")
    key = "On" if enabled else "Off"
    Msg = f"Dual Mode : {key}"
    await e.edit(Msg, buttons=get_back_button("cbs_otvars"))


@callback("dmon", owner=True)
async def dual_mode_on(e):
    await _set_dual_mode(e, True)


@callback("dmoff", owner=True)
async def dual_mode_off(e):
    await _set_dual_mode(e, False)


@callback("dmof", owner=True)
async def rhwhe(e):
    """Compatibility toggle for buttons sent by older Dockyard releases."""
    await _set_dual_mode(e, not parse_bool(udB.get_key("DUAL_MODE")))


@callback("dmhn", owner=True)
async def hndlrr(event):
    await event.delete()
    pru = event.sender_id
    var = "DUAL_HNDLR"
    name = "Dual Handler"
    CH = udB.get_key(var) or "/"
    async with event.client.conversation(pru) as conv:
        await conv.send_message(
            f"Send the symbol to use as the assistant handler.\nThe current handler is `{CH}`.\n\nUse /cancel to cancel.",
        )
        response = conv.wait_event(events.NewMessage(chats=pru))
        response = await response
        themssg = response.message.message
        if themssg == "/cancel":
            await conv.send_message(
                "Cancelled.",
                buttons=get_back_button("cbs_otvars"),
            )
        elif len(themssg) > 1:
            await conv.send_message(
                "Incorrect Handler",
                buttons=get_back_button("cbs_otvars"),
            )
        else:
            await setit(event, var, themssg)
            await conv.send_message(
                f"{name} changed to {themssg}",
                buttons=get_back_button("cbs_otvars"),
            )


@callback("plg", owner=True)
async def pluginch(event):
    await event.delete()
    pru = event.sender_id
    var = "PLUGIN_CHANNEL"
    name = "Plugin Channel"
    async with event.client.conversation(pru) as conv:
        await conv.send_message(
            "Send the ID or username of the channel to install plugins from.\n\nOnly install plugins from trusted Dockyard repositories or sources.\n\nUse /cancel to cancel.",
        )
        response = conv.wait_event(events.NewMessage(chats=pru))
        response = await response
        themssg = response.message.message
        if themssg == "/cancel":
            await conv.send_message(
                "Cancelled.",
                buttons=get_back_button("cbs_otvars"),
            )
        elif themssg.startswith(("/", HNDLR)):
            await conv.send_message(
                "Incorrect channel",
                buttons=get_back_button("cbs_otvars"),
            )
        else:
            await setit(event, var, themssg)
            await conv.send_message(
                f"{name} changed to {themssg}\n After Setting All Things Do Restart",
                buttons=get_back_button("cbs_otvars"),
            )


@callback("hhndlr", owner=True)
async def hndlrr(event):
    await event.delete()
    pru = event.sender_id
    var = "HNDLR"
    name = "Handler/ Trigger"
    async with event.client.conversation(pru) as conv:
        await conv.send_message(
            f"Send the symbol to use as the handler.\nThe current handler is `{HNDLR}`.\n\nUse /cancel to cancel.",
        )
        response = conv.wait_event(events.NewMessage(chats=pru))
        response = await response
        themssg = response.message.message
        if themssg == "/cancel":
            await conv.send_message(
                "Cancelled.",
                buttons=get_back_button("cbs_otvars"),
            )
        elif len(themssg) > 1:
            await conv.send_message(
                "Incorrect Handler",
                buttons=get_back_button("cbs_otvars"),
            )
        elif themssg.startswith(("/", "#", "@")):
            await conv.send_message(
                "This cannot be used as handler",
                buttons=get_back_button("cbs_otvars"),
            )
        else:
            await setit(event, var, themssg)
            await conv.send_message(
                f"{name} changed to {themssg}",
                buttons=get_back_button("cbs_otvars"),
            )


@callback("shndlr", owner=True)
async def hndlrr(event):
    await event.delete()
    pru = event.sender_id
    var = "SUDO_HNDLR"
    name = "Sudo Handler"
    async with event.client.conversation(pru) as conv:
        await conv.send_message(
            "Send the symbol to use as the sudo handler.\n\nUse /cancel to cancel."
        )

        response = conv.wait_event(events.NewMessage(chats=pru))
        response = await response
        themssg = response.message.message
        if themssg == "/cancel":
            await conv.send_message(
                "Cancelled.",
                buttons=get_back_button("cbs_otvars"),
            )
        elif len(themssg) > 1:
            await conv.send_message(
                "Incorrect Handler",
                buttons=get_back_button("cbs_otvars"),
            )
        elif themssg.startswith(("/", "#", "@")):
            await conv.send_message(
                "This cannot be used as handler",
                buttons=get_back_button("cbs_otvars"),
            )
        else:
            await setit(event, var, themssg)
            await conv.send_message(
                f"{name} changed to {themssg}",
                buttons=get_back_button("cbs_otvars"),
            )


@callback("taglog", owner=True)
async def tagloggrr(e):
    BUTTON = [
        [Button.inline("SET TAG LOG", data="abs_settag")],
        [Button.inline("DELETE TAG LOG", data="deltag")],
        get_back_button("cbs_otvars"),
    ]
    await e.edit(
        "Choose Options",
        buttons=BUTTON,
    )


@callback("deltag", owner=True)
async def _(e):
    udB.del_key("TAG_LOG")
    await e.answer("Tag logger has been turned off.")


@callback("eaddon", owner=True)
async def pmset(event):
    BT = (
        [Button.inline("Addons  Off", data="edof")]
        if udB.get_key("ADDONS")
        else [Button.inline("Addons  On", data="edon")]
    )

    await event.edit(
        "ADDONS~ Extra Plugins:",
        buttons=[
            BT,
            [Button.inline("Back", data="cbs_otvars")],
        ],
    )


@callback("edon", owner=True)
async def eddon(event):
    var = "ADDONS"
    await setit(event, var, "True")
    await event.edit(
        "Add-ons have been enabled.\n\nRestart after configuring the remaining settings.",
        buttons=get_back_button("eaddon"),
    )


@callback("edof", owner=True)
async def eddof(event):
    udB.set_key("ADDONS", "False")
    await event.edit(
        "Add-ons have been disabled.\n\nRestart after configuring the remaining settings.",
        buttons=get_back_button("eaddon"),
    )


@callback("sudo", owner=True)
async def pmset(event):
    BT = (
        [Button.inline("Sudo Mode  Off", data="ofsudo")]
        if udB.get_key("SUDO")
        else [Button.inline("Sudo Mode  On", data="onsudo")]
    )

    await event.edit(
        f"Sudo mode allows selected users to operate the bot. Use `{HNDLR}help sudo` for details.",
        buttons=[
            BT,
            [Button.inline("Back", data="cbs_otvars")],
        ],
    )


@callback("onsudo", owner=True)
async def eddon(event):
    var = "SUDO"
    await setit(event, var, "True")
    await event.edit(
        "Sudo mode has been enabled.\n\nRestart after configuring the remaining settings.",
        buttons=get_back_button("sudo"),
    )


@callback("ofsudo", owner=True)
async def eddof(event):
    var = "SUDO"
    await setit(event, var, "False")
    await event.edit(
        "Sudo mode has been disabled.\n\nRestart after configuring the remaining settings.",
        buttons=get_back_button("sudo"),
    )


@callback("sfgrp", owner=True)
async def sfgrp(event):
    await event.delete()
    name = "FBan Group ID"
    var = "FBAN_GROUP_ID"
    pru = event.sender_id
    async with asst.conversation(pru) as conv:
        await conv.send_message(
            f"Make a group, add @MissRose_Bot, send `{HNDLR}id`, copy that and send it here.\nUse /cancel to go back.",
        )
        response = conv.wait_event(events.NewMessage(chats=pru))
        response = await response
        themssg = response.message.message
        if themssg == "/cancel":
            return await conv.send_message(
                "Cancelled.",
                buttons=get_back_button("cbs_sfban"),
            )
        await setit(event, var, themssg)
        await conv.send_message(
            f"{name} changed to {themssg}",
            buttons=get_back_button("cbs_sfban"),
        )


@callback("alvmed", owner=True)
async def media(event):
    await event.delete()
    pru = event.sender_id
    var = "ALIVE_PIC"
    name = "Alive Media"
    async with event.client.conversation(pru) as conv:
        await conv.send_message(
            "**Alive Media**\nSend me a pic/gif/media to set as alive media.\n\nUse /cancel to terminate the operation.",
        )
        response = await conv.get_response()
        try:
            themssg = response.message
            if themssg == "/cancel":
                return await conv.send_message(
                    "Operation cancelled.",
                    buttons=get_back_button("cbs_alvcstm"),
                )
        except BaseException as er:
            LOGS.exception(er)
        if (
            not (response.text).startswith("/")
            and response.text != ""
            and (not response.media or isinstance(response.media, MessageMediaWebPage))
        ):
            url = text_to_url(response)
        elif response.sticker:
            url = response.file.id
        else:
            media = await event.client.download_media(response, "alvpc")
            try:
                url = uploader.upload_file(media)
                remove(media)
            except BaseException as er:
                LOGS.exception(er)
                return await conv.send_message(
                    "Terminated.",
                    buttons=get_back_button("cbs_alvcstm"),
                )
        await setit(event, var, url)
        await conv.send_message(
            f"{name} has been set.",
            buttons=get_back_button("cbs_alvcstm"),
        )


@callback("delmed", owner=True)
async def dell(event):
    try:
        udB.del_key("ALIVE_PIC")
        return await event.edit(
            get_string("clst_5"), buttons=get_back_button("cbs_alabs_vcstm")
        )
    except BaseException as er:
        LOGS.exception(er)
        return await event.edit(
            get_string("clst_4"),
            buttons=get_back_button("cbs_alabs_vcstm"),
        )


@callback("inpm_in", owner=True)
async def inl_on(event):
    var = "INLINE_PM"
    await setit(event, var, "True")
    await event.edit(
        "PMPermit type set to inline.",
        buttons=[[Button.inline("Back", data="cbs_pmtype")]],
    )


@callback("inpm_no", owner=True)
async def inl_on(event):
    var = "INLINE_PM"
    await setit(event, var, "False")
    await event.edit(
        "PMPermit type set to normal.",
        buttons=[[Button.inline("Back", data="cbs_pmtype")]],
    )


@callback("pmtxt", owner=True)
async def name(event):
    await event.delete()
    pru = event.sender_id
    var = "PM_TEXT"
    name = "PM Text"
    async with event.client.conversation(pru) as conv:
        await conv.send_message(
            "**PM Text**\nEnter the new Pmpermit text.\n\nu can use `{name}` `{fullname}` `{count}` `{mention}` `{username}` to get this from user Too\n\nUse /cancel to terminate the operation.",
        )
        response = conv.wait_event(events.NewMessage(chats=pru))
        response = await response
        themssg = response.message.message
        if themssg == "/cancel":
            return await conv.send_message(
                "Cancelled.",
                buttons=get_back_button("cbs_pmcstm"),
            )
        if len(themssg) > 4090:
            return await conv.send_message(
                "The message is too long.\nProvide a shorter message.",
                buttons=get_back_button("cbs_pmcstm"),
            )
        await setit(event, var, themssg)
        await conv.send_message(
            f"{name} changed to {themssg}\n\nAfter Setting All Things Do restart",
            buttons=get_back_button("cbs_pmcstm"),
        )


@callback("swarn", owner=True)
async def name(event):
    m = range(1, 10)
    tultd = [Button.inline(f"{x}", data=f"wrns_{x}") for x in m]
    lst = list(zip(tultd[::3], tultd[1::3], tultd[2::3]))
    lst.append([Button.inline("Back", data="cbs_pmcstm")])
    await event.edit(
        "Select the number of warnings for a user before getting blocked in PMs.",
        buttons=lst,
    )


@callback(re.compile(b"wrns_(.*)"), owner=True)
async def set_wrns(event):
    value = int(event.data_match.group(1).decode("UTF-8"))
    if dn := udB.set_key("PMWARNS", value):
        await event.edit(
            f"PM Warns Set to {value}.\nNew users will have {value} chances in PMs before getting banned.",
            buttons=get_back_button("cbs_pmcstm"),
        )
    else:
        await event.edit(
            f"Something went wrong. Check `{HNDLR}logs`.",
            buttons=get_back_button("cbs_pmcstm"),
        )


@callback("pmmed", owner=True)
async def media(event):
    await event.delete()
    pru = event.sender_id
    var = "PMPIC"
    name = "PM Media"
    async with event.client.conversation(pru) as conv:
        await conv.send_message(
            "**PM Media**\nSend me a pic/gif/sticker/link  to set as pmpermit media.\n\nUse /cancel to terminate the operation.",
        )
        response = await conv.get_response()
        try:
            themssg = response.message
            if themssg == "/cancel":
                return await conv.send_message(
                    "Operation cancelled.",
                    buttons=get_back_button("cbs_pmcstm"),
                )
        except BaseException as er:
            LOGS.exception(er)
        media = await event.client.download_media(response, "pmpc")
        if (
            not (response.text).startswith("/")
            and response.text != ""
            and (not response.media or isinstance(response.media, MessageMediaWebPage))
        ):
            url = text_to_url(response)
        elif response.sticker:
            url = response.file.id
        else:
            try:
                url = uploader.upload_file(media)
                remove(media)
            except BaseException as er:
                LOGS.exception(er)
                return await conv.send_message(
                    "Terminated.",
                    buttons=get_back_button("cbs_pmcstm"),
                )
        await setit(event, var, url)
        await conv.send_message(
            f"{name} has been set.",
            buttons=get_back_button("cbs_pmcstm"),
        )


@callback("delpmmed", owner=True)
async def dell(event):
    try:
        udB.del_key("PMPIC")
        return await event.edit(
            get_string("clst_5"), buttons=get_back_button("cbs_pmcstm")
        )
    except BaseException as er:
        LOGS.exception(er)
        return await event.edit(
            get_string("clst_4"),
            buttons=[[Button.inline("Settings", data="setter")]],
        )


@callback("apon", owner=True)
async def apon(event):
    var = "AUTOAPPROVE"
    await setit(event, var, "True")
    await event.edit(
        "Auto-approve enabled.",
        buttons=[[Button.inline("Back", data="cbs_apauto")]],
    )


@callback("apof", owner=True)
async def apof(event):
    try:
        udB.set_key("AUTOAPPROVE", "False")
        return await event.edit(
            "Auto-approve disabled.",
            buttons=[[Button.inline("Back", data="cbs_apauto")]],
        )
    except BaseException as er:
        LOGS.exception(er)
        return await event.edit(
            get_string("clst_4"),
            buttons=[[Button.inline("Settings", data="setter")]],
        )


@callback("pml", owner=True)
async def l_vcs(event):
    BT = (
        [Button.inline("PMLOGGER OFF", data="pmlogof")]
        if udB.get_key("PMLOG")
        else [Button.inline("PMLOGGER ON", data="pmlog")]
    )

    await event.edit(
        "PMLOGGER forwards private messages to your private group.",
        buttons=[
            BT,
            [Button.inline("PmLogger Group", "abs_pmlgg")],
            [Button.inline("Back", data="cbs_pmcstm")],
        ],
    )


@callback("pmlog", owner=True)
async def pmlog(event):
    await setit(event, "PMLOG", "True")
    await event.edit(
        "PMLOGGER enabled.",
        buttons=[[Button.inline("Back", data="pml")]],
    )


@callback("pmlogof", owner=True)
async def pmlogof(event):
    try:
        udB.del_key("PMLOG")
        return await event.edit(
            "PMLOGGER disabled.",
            buttons=[[Button.inline("Back", data="pml")]],
        )
    except BaseException as er:
        LOGS.exception(er)
        return await event.edit(
            get_string("clst_4"),
            buttons=[[Button.inline("Settings", data="setter")]],
        )


@callback("pmon", owner=True)
async def pmonn(event):
    var = "PMSETTING"
    await setit(event, var, "True")
    await event.edit(
        "PMPermit enabled.",
        buttons=[[Button.inline("Back", data="cbs_ppmset")]],
    )


@callback("pmoff", owner=True)
async def pmofff(event):
    var = "PMSETTING"
    await setit(event, var, "False")
    await event.edit(
        "PMPermit disabled.",
        buttons=[[Button.inline("Back", data="cbs_ppmset")]],
    )


@callback("pmfs", owner=True)
async def heheh(event):
    Ll = []
    err = ""
    async with event.client.conversation(event.chat_id) as conv:
        await conv.send_message(
            "Send the chat IDs users must join before using the chat or PM bot.\n\nSend /clear to disable PM bot force subscribe.\nSend /cancel to stop this process."
        )
        await conv.send_message(
            "Example : \n`-1001234567\n-100778888`\n\nFor Multiple Chat(s)."
        )
        try:
            msg = await conv.get_response()
        except AsyncTimeOut:
            return await conv.send_message("**TimeUp!**\nStart from /start back.")
        if not msg.text or msg.text.startswith("/"):
            timyork = "Cancelled!"
            if msg.text == "/clear":
                udB.del_key("PMBOT_FSUB")
                timyork = "Force subscribe disabled.\nRestart the bot."
            return await conv.send_message(
                "Cancelled!", buttons=get_back_button("setter")
            )
        for chat in msg.message.split("\n"):
            if chat.startswith("-") or chat.isdigit():
                chat = int(chat)
            try:
                CHSJSHS = await event.client.get_entity(chat)
                Ll.append(get_peer_id(CHSJSHS))
            except Exception as er:
                err += f"**{chat}** : {er}\n"
        if err:
            return await conv.send_message(err)
        udB.set_key("PMBOT_FSUB", str(Ll))
        await conv.send_message(
            "Done.\nRestart the bot.", buttons=get_back_button("setter")
        )


@callback("inli_pic", owner=True)
async def media(event):
    await event.delete()
    pru = event.sender_id
    var = "INLINE_PIC"
    name = "Inline Media"
    async with event.client.conversation(pru) as conv:
        await conv.send_message(
            "**Inline Media**\nSend me a pic/gif/ or link  to set as inline media.\n\nUse /cancel to terminate the operation.",
        )
        response = await conv.get_response()
        try:
            themssg = response.message
            if themssg == "/cancel":
                return await conv.send_message(
                    "Operation cancelled.",
                    buttons=get_back_button("setter"),
                )
        except BaseException as er:
            LOGS.exception(er)
        media = await event.client.download_media(response, "inlpic")
        if (
            not (response.text).startswith("/")
            and response.text != ""
            and (not response.media or isinstance(response.media, MessageMediaWebPage))
        ):
            url = text_to_url(response)
        else:
            try:
                url = uploader.upload_file(media)
                remove(media)
            except BaseException as er:
                LOGS.exception(er)
                return await conv.send_message(
                    "Terminated.",
                    buttons=get_back_button("setter"),
                )
        await setit(event, var, url)
        await conv.send_message(
            f"{name} has been set.",
            buttons=get_back_button("setter"),
        )


FD_MEDIA = {}


@callback(re.compile("fd(.*)"), owner=True)
async def fdroid_dler(event):
    uri = event.data_match.group(1).decode("utf-8")
    if FD_MEDIA.get(uri):
        return await event.edit(file=FD_MEDIA[uri])
    await event.answer("Starting Download ", alert=True)
    await event.edit("Downloading.")
    URL = f"https://f-droid.org/packages/{uri}"
    conte = await async_searcher(URL, re_content=True)
    BSC = bs(conte, "html.parser", from_encoding="utf-8")
    dl_ = BSC.find("p", "package-version-download").find("a")["href"]
    title = BSC.find("h3", "package-name").text.strip()
    thumb = BSC.find("img", "package-icon")["src"]
    if thumb.startswith("/"):
        thumb = f"https://f-droid.org{thumb}"
    thumb, _ = await fast_download(thumb, filename=f"{uri}.png")
    s_time = time.time()
    file, _ = await fast_download(
        dl_,
        filename=f"{title}.apk",
        progress_callback=lambda d, t: asyncio.get_event_loop().create_task(
            progress(
                d,
                t,
                event,
                s_time,
                "Downloading...",
            )
        ),
    )

    time.time()
    n_file = await event.client.fast_uploader(
        file, show_progress=True, event=event, message="Uploading...", to_delete=True
    )
    buttons = Button.switch_inline("Search Back", query="fdroid", same_peer=True)
    try:
        msg = await event.edit(
            f"**[{title}]({URL}) **", file=n_file, thumb=thumb, buttons=buttons
        )
    except Exception as er:
        LOGS.exception(er)
        try:
            msg = await event.client.edit_message(
                await event.get_input_chat(),
                event.message_id,
                f"**[{title}]({URL}) **",
                buttons=buttons,
                thumb=thumb,
                file=n_file,
            )
        except Exception as er:
            os.remove(thumb)
            LOGS.exception(er)
            return await event.edit(f"**ERROR**: `{er}`", buttons=buttons)
    if msg and hasattr(msg, "media"):
        FD_MEDIA.update({uri: msg.media})
    os.remove(thumb)
