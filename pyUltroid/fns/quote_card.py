# Ultroid - UserBot
# Copyright (C) 2021-2026 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://www.github.com/TeamUltroid/Ultroid/blob/main/LICENSE/>.
"""Render the Dockyard quote sticker.

The approved design was drawn with Inter. Inter is not bundled with
Dockyard, so Roboto stands in for it here; the rest of the geometry,
colours, and typography sizes follow the approved 512 px master.

This module is deliberately pure: it uses only the standard library and
Pillow. It never imports pyUltroid or Telegram, which keeps rendering
testable without a running client.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

_ROOT = Path(__file__).resolve().parents[2]
_FONT_ROOT = _ROOT / "resources" / "fonts"
_ROBOTO_REGULAR = _FONT_ROOT / "Roboto-Regular.ttf"
_ROBOTO_MEDIUM = _FONT_ROOT / "Roboto-Medium.ttf"
_DEJAVU_SERIF_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf")
_QUIVIRA = _FONT_ROOT / "Quivira.otf"

_MAX_STICKER_CHARS = 140
_MAX_SHARE_CHARS = 260
_EMPTY_TEXT = "No text"

_FILL = (30, 33, 38, 240)
_BORDER = (228, 234, 245, 115)
_HIGHLIGHT = (255, 255, 255, 115)
_SHADOW = (0, 0, 0, 140)
_TEXT = (245, 246, 248)
_MUTED = (185, 192, 204)
_INITIALS_FILL = (58, 63, 72)


@dataclass(frozen=True)
class QuoteCard:
    name: str
    handle: str
    text: str
    avatar: bytes | None = None
    photo: bytes | None = None
    timestamp: str | None = None


@dataclass(frozen=True)
class _Layout:
    canvas: tuple[int, int]
    scale: int
    card_width: int
    card_left: int
    min_card_height: int
    radius: int
    pad_x: int
    pad_top: int
    pad_bottom: int
    avatar: int
    gap: int
    name_size: int
    handle_size: int
    handle_gap: int
    quote_size: int
    message_size: int
    line_height: int
    message_gap: int
    wrap_width: int
    max_lines: int
    char_limit: int
    shadow_offset: int
    shadow_blur: int
    border_width: float
    ring_width: float


_STICKER = _Layout(
    canvas=(512, 512),
    scale=2,
    card_width=480,
    card_left=16,
    min_card_height=448,
    radius=44,
    pad_x=34,
    pad_top=34,
    pad_bottom=38,
    avatar=80,
    gap=16,
    name_size=26,
    handle_size=19,
    handle_gap=4,
    quote_size=66,
    message_size=38,
    line_height=46,
    message_gap=26,
    wrap_width=412,
    max_lines=5,
    char_limit=_MAX_STICKER_CHARS,
    shadow_offset=26,
    shadow_blur=26,
    border_width=1.5,
    ring_width=1.5,
)

_SHARE = _Layout(
    canvas=(1080, 1350),
    scale=2,
    card_width=960,
    card_left=60,
    min_card_height=900,
    radius=88,
    pad_x=68,
    pad_top=68,
    pad_bottom=76,
    avatar=160,
    gap=32,
    name_size=52,
    handle_size=38,
    handle_gap=8,
    quote_size=132,
    message_size=62,
    line_height=76,
    message_gap=52,
    wrap_width=824,
    max_lines=12,
    char_limit=_MAX_SHARE_CHARS,
    shadow_offset=52,
    shadow_blur=52,
    border_width=3,
    ring_width=3,
)


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _quote_font(size: int) -> ImageFont.FreeTypeFont:
    path = _DEJAVU_SERIF_BOLD if _DEJAVU_SERIF_BOLD.exists() else _QUIVIRA
    return _font(path, size)


def _clamp_text(text: str, limit: int) -> str:
    value = " ".join((text or "").split())
    if not value:
        return _EMPTY_TEXT
    if len(value) <= limit:
        return value
    return value[: max(1, limit - 1)].rstrip() + "\u2026"


def _prepare_text(text: str, limit: int) -> str:
    """Collapse whitespace outside intentional paragraph breaks."""
    raw = text or ""
    if not raw.strip():
        return _EMPTY_TEXT
    paragraphs = []
    for block in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        cleaned = " ".join(block.split())
        paragraphs.append(cleaned)
    value = "\n".join(paragraphs).strip("\n")
    if not value.strip():
        return _EMPTY_TEXT
    if len(value) <= limit:
        return value
    return value[: max(1, limit - 1)].rstrip() + "\u2026"


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> float:
    return draw.textlength(text, font=font)


def _ellipsize(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> str:
    text = text.rstrip("\u2026").rstrip()
    marker = "\u2026"
    if _text_width(draw, text + marker, font) <= width:
        return text + marker
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if _text_width(draw, text[:middle].rstrip() + marker, font) <= width:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip() + marker


def _break_word(draw: ImageDraw.ImageDraw, word: str, font, width: int) -> list[str]:
    parts = []
    while word:
        if _text_width(draw, word, font) <= width:
            parts.append(word)
            break
        low, high = 1, len(word)
        while low < high:
            middle = (low + high + 1) // 2
            if _text_width(draw, word[:middle], font) <= width:
                low = middle
            else:
                high = middle - 1
        parts.append(word[:low])
        word = word[low:].lstrip()
    return parts


def _wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    width: int,
    max_lines: int,
) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        current = ""
        for word in paragraph.split(" "):
            if not word:
                continue
            candidate = word if not current else f"{current} {word}"
            if _text_width(draw, candidate, font) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            parts = _break_word(draw, word, font, width)
            if parts:
                lines.extend(parts[:-1])
                current = parts[-1]
        if current:
            lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _ellipsize(draw, lines[-1], font, width)
    return [line for line in lines] or [_EMPTY_TEXT]


def _avatar_image(source: bytes, size: int, *, blur: bool) -> Image.Image:
    image = Image.open(io.BytesIO(source)).convert("RGB")
    image = ImageOps.fit(image, (size, size), method=Image.LANCZOS)
    if blur:
        image = image.filter(ImageFilter.GaussianBlur(radius=max(1, size // 8)))
    image = image.convert("RGBA")

    scale = 4
    mask = Image.new("L", (size * scale, size * scale), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * scale - 1, size * scale - 1), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    image.putalpha(mask)
    return image


def _initials(name: str) -> str:
    words = [word for word in (name or "").split() if word]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[-1][0]).upper()


def _initials_avatar(name: str, size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((0, 0, size - 1, size - 1), fill=_INITIALS_FILL)
    font = _font(_ROBOTO_MEDIUM, max(12, int(size * 0.36)))
    text = _initials(name)
    box = draw.textbbox((0, 0), text, font=font)
    width = box[2] - box[0]
    height = box[3] - box[1]
    draw.text(
        ((size - width) / 2 - box[0], (size - height) / 2 - box[1]),
        text,
        font=font,
        fill=_TEXT,
    )
    return image


def _token_width(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> str:
    if _text_width(draw, text, font) <= width:
        return text
    return _ellipsize(draw, text, font, width)


def _draw_card(
    card: QuoteCard,
    layout: _Layout,
    *,
    limit: int,
) -> Image.Image:
    scale = layout.scale
    width, height = layout.canvas
    canvas = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))

    pad = layout.pad_x * scale
    avatar_size = layout.avatar * scale
    gap = layout.gap * scale
    radius = layout.radius * scale
    card_left = layout.card_left * scale
    card_width = layout.card_width * scale
    min_height = layout.min_card_height * scale
    content_width = layout.wrap_width * scale

    name_font = _font(_ROBOTO_MEDIUM, layout.name_size * scale)
    handle_font = _font(_ROBOTO_REGULAR, layout.handle_size * scale)
    quote_font = _quote_font(layout.quote_size * scale)
    message_font = _font(_ROBOTO_REGULAR, layout.message_size * scale)

    probe = ImageDraw.Draw(canvas)
    name_line = int(layout.name_size * 1.15 * scale)
    identity_height = name_line + layout.handle_gap * scale
    handle_line = int(layout.handle_size * 1.2 * scale)
    identity_height += handle_line
    header_height = max(avatar_size, identity_height)

    message_text = _prepare_text(card.text, min(limit, layout.char_limit))
    lines = _wrap(
        probe,
        message_text,
        message_font,
        content_width,
        layout.max_lines,
    )
    message_height = len(lines) * layout.line_height * scale
    message_gap = layout.message_gap * scale

    content_height = header_height
    if lines:
        content_height += message_gap + message_height

    card_height = max(min_height, content_height + layout.pad_top * scale + layout.pad_bottom * scale)
    card_height = min(card_height, (height - 8) * scale)
    card_top = ((height * scale) - card_height) // 2

    # The drop shadow is painted first so the solid card always covers it.
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (
            card_left,
            card_top + layout.shadow_offset * scale,
            card_left + card_width,
            card_top + card_height + layout.shadow_offset * scale,
        ),
        radius=radius,
        fill=_SHADOW,
    )
    shadow = shadow.filter(
        ImageFilter.GaussianBlur(radius=layout.shadow_blur * scale)
    )
    canvas.alpha_composite(shadow)

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (card_left, card_top, card_left + card_width, card_top + card_height),
        radius=radius,
        fill=_FILL,
    )

    border_px = max(1, int(round(layout.border_width * scale)))
    rim = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    rim_draw = ImageDraw.Draw(rim)
    inset_border = border_px / 2
    rim_draw.rounded_rectangle(
        (
            card_left + inset_border,
            card_top + inset_border,
            card_left + card_width - inset_border,
            card_top + card_height - inset_border,
        ),
        radius=radius - inset_border,
        outline=_BORDER,
        width=border_px,
    )

    # A single inset highlight across the top edge gives the card its cut-glass rim.
    highlight_y = card_top + border_px + 1
    inset = max(1, int(radius * 0.35))
    rim_draw.line(
        (card_left + inset, highlight_y, card_left + card_width - inset, highlight_y),
        fill=_HIGHLIGHT,
        width=max(1, scale),
    )
    canvas.alpha_composite(rim)

    content_left = card_left + pad
    content_right = card_left + card_width - pad
    content_top = card_top + (card_height - content_height) // 2

    avatar_x = content_left
    avatar_y = content_top + (header_height - avatar_size) // 2

    avatar_source = card.photo or card.avatar
    if avatar_source:
        avatar = _avatar_image(avatar_source, avatar_size, blur=bool(card.photo))
    else:
        avatar = _initials_avatar(card.name, avatar_size)
    canvas.alpha_composite(avatar, (avatar_x, avatar_y))

    ring_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(ring_layer).ellipse(
        (
            avatar_x,
            avatar_y,
            avatar_x + avatar_size - 1,
            avatar_y + avatar_size - 1,
        ),
        outline=(228, 234, 245, 140),
        width=max(1, int(round(layout.ring_width * scale))),
    )
    canvas.alpha_composite(ring_layer)

    text_left = avatar_x + avatar_size + gap
    quote_text = "\u201c"
    quote_width = int(_text_width(probe, quote_text, quote_font)) + 4 * scale
    identity_right = content_right - quote_width - 8 * scale
    identity_width = max(1, identity_right - text_left)

    name_text = _token_width(probe, " ".join((card.name or "").split()) or "Telegram user", name_font, identity_width)
    secondary = " ".join((card.handle or "").split()) or " ".join((card.timestamp or "").split())
    handle_text = _token_width(probe, secondary, handle_font, identity_width) if secondary else ""

    identity_top = content_top + (header_height - identity_height) // 2 - 4 * scale
    draw.text(
        (text_left, identity_top),
        name_text,
        font=name_font,
        fill=_TEXT,
        anchor="la",
    )
    if handle_text:
        draw.text(
            (text_left, identity_top + name_line + layout.handle_gap * scale),
            handle_text,
            font=handle_font,
            fill=_MUTED,
            anchor="la",
        )

    draw.text(
        (content_right - 4 * scale, content_top - 2 * scale),
        quote_text,
        font=quote_font,
        fill=_MUTED,
        anchor="ra",
    )

    message_top = content_top + header_height + message_gap
    for index, line in enumerate(lines):
        draw.text(
            (content_left, message_top + index * layout.line_height * scale),
            line,
            font=message_font,
            fill=_TEXT,
            anchor="la",
        )

    return canvas.resize(layout.canvas, Image.LANCZOS)


def _encode_webp(image: Image.Image) -> bytes:
    for quality in (90, 85, 80, 75, 70):
        buffer = io.BytesIO()
        image.save(buffer, "WEBP", quality=quality, method=4)
        data = buffer.getvalue()
        if len(data) <= 512 * 1024:
            return data
    return data


def render(card: QuoteCard) -> bytes:
    """Render a 512x512 transparent WebP sticker."""
    image = _draw_card(card, _STICKER, limit=_MAX_STICKER_CHARS)
    return _encode_webp(image)


def render_png(card: QuoteCard) -> bytes:
    """Render a 1080x1350 transparent PNG share card."""
    image = _draw_card(card, _SHARE, limit=_MAX_SHARE_CHARS)
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def _message_lines(card: QuoteCard) -> list[str]:
    """Expose the sticker line layout for regression tests."""
    probe = Image.new("RGBA", (8, 8))
    draw = ImageDraw.Draw(probe)
    font = _font(_ROBOTO_REGULAR, _STICKER.message_size * _STICKER.scale)
    text = _prepare_text(card.text, _STICKER.char_limit)
    return _wrap(
        draw,
        text,
        font,
        _STICKER.wrap_width * _STICKER.scale,
        _STICKER.max_lines,
    )
