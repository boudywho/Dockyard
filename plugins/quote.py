# Ultroid - UserBot
# Copyright (C) 2021-2026 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://www.github.com/TeamUltroid/Ultroid/blob/main/LICENSE/>.
"""Commands

`{i}q <flags>`
    Reply to a message to turn it into a quote sticker and add it to your pack.

    `-e <emoji>` sets the sticker emoji tag.
    `-p <n>` chooses a pack slot from 1 to 20.
    `--preview` sends the sticker without adding it to the pack.
    `--photo` puts the replied image inside the avatar disc.
    `-n <n>` quotes the last 1 to 10 messages of the replied chat.
    `--link <t.me/...>` quotes a linked message instead of the reply.
    `--name <text>` overrides the display name.
    `--png` also sends the 1080x1350 share card.

`{i}qpack`
    Show the current pack link and slot.

`{i}qpack reset`
    Clear the current slot and move to the next free slot.
"""

from __future__ import annotations

import io
import re
import shlex
from dataclasses import dataclass

from telethon.errors import (
    PackShortNameInvalidError,
    PackShortNameOccupiedError,
    PeerIdInvalidError,
    StickerpackStickersTooMuchError,
    StickersTooMuchError,
    StickersetInvalidError,
)
from telethon.tl.functions.messages import UploadMediaRequest
from telethon.tl.functions.stickers import (
    AddStickerToSetRequest,
    CreateStickerSetRequest,
)
from telethon.tl.types import (
    DocumentAttributeFilename,
    DocumentAttributeImageSize,
    DocumentAttributeSticker,
    InputMediaUploadedDocument,
    InputPeerSelf,
    InputStickerSetEmpty,
    InputStickerSetItem,
    InputStickerSetShortName,
)
from telethon.utils import get_input_document

from pyUltroid.dB.base import KeyManager
from pyUltroid.fns.quote_card import QuoteCard, render, render_png

from . import LOGS, asst, get_help, get_string, inline_mention, udB, ultroid_cmd

__doc__ = get_help("quote")

_MAX_SLOT = 20
_MAX_COUNT = 10
_DEFAULT_EMOJI = "\U0001f4ac"
_CURRENT_SLOT = "QUOTE_PACK_CURRENT"
_MESSAGE_LINK = re.compile(
    r"^(?:https?://)?(?:t\.me|telegram\.me)/"
    r"(?:(?P<private>c)/(?P<channel>[0-9]+)|(?P<username>[A-Za-z0-9_]{4,}))/"
    r"(?:[0-9]+/)?(?P<message>[0-9]+)(?:[/?#].*)?$",
    re.IGNORECASE,
)


class QuoteFlagError(ValueError):
    """A flag error that maps to a translatable message key."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.code = code
        self.detail = detail


class QuoteError(Exception):
    """A command failure that maps to a translatable message key."""

    def __init__(self, key: str, detail: str = ""):
        super().__init__(key)
        self.key = key
        self.detail = detail


@dataclass(frozen=True)
class QuoteFlags:
    emoji: str = _DEFAULT_EMOJI
    slot: int = 1
    preview: bool = False
    photo: bool = False
    count: int | None = None
    link: str | None = None
    name: str | None = None
    png: bool = False


_VALUE_FLAGS = {
    "-e": "emoji",
    "-p": "slot",
    "-n": "count",
    "--link": "link",
    "--name": "name",
}
_BOOL_FLAGS = {
    "--preview": "preview",
    "--photo": "photo",
    "--png": "png",
}


def _is_flag(token: str) -> bool:
    if token in _VALUE_FLAGS or token in _BOOL_FLAGS:
        return True
    return len(token) > 1 and token.startswith("--")


def parse_flags(value: str | None) -> QuoteFlags:
    """Parse the text after ``.q`` without touching Telegram."""
    try:
        tokens = shlex.split(value or "")
    except ValueError:
        raise QuoteFlagError("unknown", (value or "").strip()) from None

    parsed: dict[str, object] = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _BOOL_FLAGS:
            parsed[_BOOL_FLAGS[token]] = True
            index += 1
            continue
        if token not in _VALUE_FLAGS:
            raise QuoteFlagError("unknown", token)
        if token == "--name":
            collected = []
            index += 1
            while index < len(tokens) and not _is_flag(tokens[index]):
                collected.append(tokens[index])
                index += 1
            name = " ".join(collected).strip()
            if not name:
                raise QuoteFlagError("missing", token)
            parsed["name"] = name
            continue
        if index + 1 >= len(tokens):
            raise QuoteFlagError("missing", token)
        raw = tokens[index + 1]
        if _is_flag(raw):
            raise QuoteFlagError("missing", token)
        index += 2
        key = _VALUE_FLAGS[token]
        if key == "slot":
            try:
                parsed["slot"] = int(raw)
            except ValueError:
                raise QuoteFlagError("slot") from None
        elif key == "count":
            try:
                parsed["count"] = int(raw)
            except ValueError:
                raise QuoteFlagError("count") from None
        elif key == "link":
            if not parse_message_link(raw):
                raise QuoteFlagError("link")
            parsed["link"] = raw.strip()
        elif key == "emoji":
            emoji = raw.strip()
            if not emoji:
                raise QuoteFlagError("missing", token)
            parsed["emoji"] = emoji

    slot = int(parsed.get("slot", 1))
    if not 1 <= slot <= _MAX_SLOT:
        raise QuoteFlagError("slot")
    count = parsed.get("count")
    if count is not None:
        count = int(count)
        if not 1 <= count <= _MAX_COUNT:
            raise QuoteFlagError("count")

    return QuoteFlags(
        emoji=str(parsed.get("emoji", _DEFAULT_EMOJI)),
        slot=slot,
        preview=bool(parsed.get("preview", False)),
        photo=bool(parsed.get("photo", False)),
        count=count,
        link=parsed.get("link"),
        name=parsed.get("name"),
        png=bool(parsed.get("png", False)),
    )


def parse_message_link(link: str) -> tuple[int | str, int] | None:
    """Return ``(peer, message_id)`` for a Telegram message link."""
    match = _MESSAGE_LINK.match((link or "").strip())
    if not match:
        return None
    message_id = int(match.group("message"))
    if match.group("private"):
        return int(f"-100{match.group('channel')}"), message_id
    return match.group("username"), message_id


def pack_short_name(user_id: int, slot: int, bot_username: str) -> str:
    username = re.sub(r"[^A-Za-z0-9_]", "", (bot_username or "").lstrip("@"))
    username = username or "dockyard"
    prefix = f"dq_{int(user_id)}_{int(slot)}_by_"
    return prefix + username[: max(1, 64 - len(prefix))]


def pack_title(name: str, slot: int) -> str:
    clean = " ".join((name or "").split()) or "Telegram user"
    title = f"Quotes by {clean}" if slot <= 1 else f"Quotes {slot} by {clean}"
    return title[:64].rstrip()


def rollover_slot(slot: int) -> int | None:
    """Advance once, never past the last allowed slot."""
    return slot + 1 if slot < _MAX_SLOT else None


def free_slot_after(current: int, used: set[int]) -> int | None:
    """Find the next unused slot, wrapping at the end."""
    for offset in range(1, _MAX_SLOT + 1):
        candidate = ((current - 1 + offset) % _MAX_SLOT) + 1
        if candidate not in used:
            return candidate
    return None


def _message_text(message) -> str:
    text = (getattr(message, "message", None) or "").strip()
    if text:
        return text
    if getattr(message, "photo", None):
        return "[photo]"
    if getattr(message, "sticker", None):
        return "[sticker]"
    if getattr(message, "video", None):
        return "[video]"
    if getattr(message, "voice", None):
        return "[voice]"
    if getattr(message, "audio", None):
        return "[audio]"
    if getattr(message, "document", None):
        return "[file]"
    return ""


def _sticker_attributes(emoji: str) -> list:
    return [
        DocumentAttributeSticker(alt=emoji, stickerset=InputStickerSetEmpty()),
        DocumentAttributeImageSize(w=512, h=512),
        DocumentAttributeFilename(file_name="sticker.webp"),
    ]


async def _resolve_source(event, flags: QuoteFlags):
    if flags.link:
        parsed = parse_message_link(flags.link)
        if not parsed:
            raise QuoteError("quote_bad_link")
        peer, message_id = parsed
        try:
            message = await event.client.get_messages(peer, ids=message_id)
        except Exception:
            message = None
        if not message:
            raise QuoteError("quote_not_found")
        return message

    reply = await event.get_reply_message()
    if not reply:
        raise QuoteError("quote_no_reply")
    return reply


async def _source_text(event, source, count: int | None) -> str:
    if not count:
        return _message_text(source)
    try:
        messages = await event.client.get_messages(
            source.chat_id,
            limit=count,
            max_id=source.id + 1,
        )
    except Exception:
        messages = [source]
    ordered = list(reversed(messages or [source]))
    parts = [_message_text(message) for message in ordered]
    return "\n\n".join(part for part in parts if part) or _message_text(source)


async def _download_avatar(client, sender) -> bytes | None:
    if sender is None:
        return None
    buffer = io.BytesIO()
    try:
        await client.download_profile_photo(sender, file=buffer)
    except Exception as exc:
        LOGS.debug("Quote avatar download failed: %s", exc)
        return None
    return buffer.getvalue() or None


async def _download_photo(client, message) -> bytes | None:
    if message is None:
        return None
    document = getattr(message, "document", None)
    mime = (getattr(getattr(message, "file", None), "mime_type", None) or "")
    if not (getattr(message, "photo", None) or (document and mime.startswith("image/"))):
        return None
    buffer = io.BytesIO()
    try:
        await client.download_media(message, file=buffer)
    except Exception as exc:
        LOGS.debug("Quote photo download failed: %s", exc)
        return None
    return buffer.getvalue() or None


async def _upload_sticker(client, data: bytes, emoji: str):
    stream = io.BytesIO(data)
    stream.name = "sticker.webp"
    uploaded = await client.upload_file(stream, file_name="sticker.webp")
    media = InputMediaUploadedDocument(
        file=uploaded,
        mime_type="image/webp",
        attributes=_sticker_attributes(emoji),
    )
    message = await client(UploadMediaRequest(InputPeerSelf(), media))
    return get_input_document(message)


async def _send_sticker(client, chat_id: int, data: bytes, emoji: str, reply_to: int):
    stream = io.BytesIO(data)
    stream.name = "sticker.webp"
    return await client.send_file(
        chat_id,
        stream,
        attributes=_sticker_attributes(emoji),
        mime_type="image/webp",
        force_document=False,
        reply_to=reply_to,
    )


async def _add_to_pack(
    client,
    *,
    user_id: int,
    name: str,
    document,
    emoji: str,
    slot: int,
    bot_username: str,
) -> tuple[str, int, bool, bool]:
    """Add one sticker, advancing one slot when the current set is unusable."""
    original = slot
    cached = KeyManager(f"QUOTE_PACK_{slot}").get()
    attempts = 0
    while True:
        short_name = cached or pack_short_name(user_id, slot, bot_username)
        created = not bool(cached)
        try:
            if cached:
                await client(
                    AddStickerToSetRequest(
                        stickerset=InputStickerSetShortName(short_name=short_name),
                        sticker=InputStickerSetItem(document=document, emoji=emoji),
                    )
                )
            else:
                await client(
                    CreateStickerSetRequest(
                        user_id=user_id,
                        title=pack_title(name, slot),
                        short_name=short_name,
                        stickers=[
                            InputStickerSetItem(document=document, emoji=emoji)
                        ],
                        software="Dockyard",
                    )
                )
                udB.set_key(f"QUOTE_PACK_{slot}", short_name)
        except PeerIdInvalidError:
            raise
        except (
            PackShortNameInvalidError,
            PackShortNameOccupiedError,
            StickersetInvalidError,
            StickersTooMuchError,
            StickerpackStickersTooMuchError,
        ):
            if attempts >= 1:
                raise
            attempts += 1
            next_slot = rollover_slot(slot)
            if next_slot is None:
                raise
            slot = next_slot
            cached = KeyManager(f"QUOTE_PACK_{slot}").get()
            continue

        udB.set_key(_CURRENT_SLOT, slot)
        return short_name, slot, created, slot != original


def _current_slot() -> int:
    try:
        slot = int(udB.get_key(_CURRENT_SLOT) or 1)
    except (TypeError, ValueError):
        slot = 1
    return slot if 1 <= slot <= _MAX_SLOT else 1


def _flag_error(error: QuoteFlagError) -> str:
    key = {
        "unknown": "quote_unknown_flag",
        "missing": "quote_missing_value",
        "slot": "quote_bad_slot",
        "count": "quote_bad_count",
        "link": "quote_bad_link",
    }.get(error.code, "quote_unknown_flag")
    template = get_string(key)
    return template.format(error.detail) if "{}" in template else template


@ultroid_cmd(pattern="q( (.*)|$)")
async def quote_cmd(event):
    raw = event.pattern_match.group(2) or ""
    try:
        flags = parse_flags(raw)
    except QuoteFlagError as error:
        return await event.eor(_flag_error(error))

    try:
        source = await _resolve_source(event, flags)
        sender = None
        try:
            sender = await source.get_sender()
        except Exception:
            sender = getattr(source, "sender", None)

        text = await _source_text(event, source, flags.count)
        if not text:
            text = _message_text(source)
        name = flags.name
        if not name and sender:
            parts = [
                getattr(sender, "first_name", None),
                getattr(sender, "last_name", None),
            ]
            name = " ".join(part for part in parts if part).strip()
        if not name:
            name = "Telegram user"
        username = getattr(sender, "username", None) if sender else None

        date = getattr(source, "date", None)
        timestamp = date.strftime("%H:%M") if date else ""
        avatar = await _download_avatar(event.client, sender)
        photo = await _download_photo(event.client, source) if flags.photo else None
        card = QuoteCard(
            name=name,
            handle=f"@{username}" if username else "",
            text=text,
            avatar=avatar,
            photo=photo,
            timestamp=timestamp,
        )
        sticker = render(card)
    except QuoteError as error:
        return await event.eor(get_string(error.key))
    except Exception as exc:
        LOGS.exception(exc)
        return await event.eor(get_string("quote_render_failed"))

    target_chat = getattr(source, "chat_id", None) or event.chat_id

    async def send_share_card():
        if not flags.png:
            return
        try:
            share = render_png(card)
            share_stream = io.BytesIO(share)
            share_stream.name = "quote.png"
            await event.client.send_file(
                target_chat,
                share_stream,
                force_document=False,
                reply_to=source.id,
            )
        except Exception as exc:
            LOGS.exception(exc)

    if flags.preview:
        try:
            await _send_sticker(
                event.client,
                target_chat,
                sticker,
                flags.emoji,
                source.id,
            )
        except Exception as exc:
            LOGS.exception(exc)
            return await event.eor(get_string("quote_send_failed"))
        await send_share_card()
        return

    bot_username = getattr(getattr(asst, "me", None), "username", None) or "dockyard"
    try:
        document = await _upload_sticker(asst, sticker, flags.emoji)
        short_name, used_slot, _created, adjusted = await _add_to_pack(
            asst,
            user_id=event.sender_id,
            name=name,
            document=document,
            emoji=flags.emoji,
            slot=flags.slot,
            bot_username=bot_username,
        )
    except PeerIdInvalidError:
        mention = inline_mention(await event.get_sender())
        return await event.eor(
            get_string("quote_start_assistant").format(mention, bot_username)
        )
    except Exception as exc:
        LOGS.exception(exc)
        return await event.eor(get_string("quote_pack_failed"))

    try:
        await _send_sticker(
            event.client,
            target_chat,
            sticker,
            flags.emoji,
            source.id,
        )
    except Exception as exc:
        LOGS.exception(exc)
        return await event.eor(get_string("quote_send_failed"))

    await send_share_card()
    link = f"https://t.me/addstickers/{short_name}"
    if adjusted:
        message = get_string("quote_pack_moved").format(flags.slot, used_slot)
        message = f"{message}\n{link}"
    else:
        message = link
    await event.client.send_message(
        target_chat,
        message,
        link_preview=False,
        parse_mode=None,
    )


@ultroid_cmd(pattern="qpack( (.*)|$)")
async def quote_pack_cmd(event):
    argument = (event.pattern_match.group(2) or "").strip().lower()
    slot = _current_slot()
    if argument not in ("", "reset"):
        return await event.eor(get_string("quote_pack_usage"))

    if argument == "reset":
        udB.del_key(f"QUOTE_PACK_{slot}")
        used = {
            number
            for number in range(1, _MAX_SLOT + 1)
            if KeyManager(f"QUOTE_PACK_{number}").get()
        }
        next_slot = free_slot_after(slot, used)
        if next_slot is None or next_slot == slot:
            udB.set_key(_CURRENT_SLOT, slot)
            return await event.eor(get_string("quote_pack_no_free").format(slot))
        udB.set_key(_CURRENT_SLOT, next_slot)
        return await event.eor(
            get_string("quote_pack_reset").format(slot, next_slot)
        )

    short_name = KeyManager(f"QUOTE_PACK_{slot}").get()
    if short_name:
        return await event.eor(
            get_string("quote_pack_current").format(
                slot,
                f"https://t.me/addstickers/{short_name}",
            ),
            link_preview=False,
        )
    return await event.eor(get_string("quote_pack_empty").format(slot))
