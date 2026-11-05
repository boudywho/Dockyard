"""Regression checks for the pure quote-card renderer."""

import importlib.util
import io
import sys
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def load_quote_card():
    spec = importlib.util.spec_from_file_location(
        "dockyard_quote_card",
        ROOT / "pyUltroid" / "fns" / "quote_card.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


quote_card = load_quote_card()


def solid_image(colour, size=(96, 72)):
    image = Image.new("RGB", size, colour)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


class QuoteCardRenderTests(unittest.TestCase):
    def card(self, **overrides):
        values = {
            "name": "Alex Morgan",
            "handle": "@alexm",
            "text": "I had a plan. Then I opened Telegram.",
            "timestamp": "14:32",
        }
        values.update(overrides)
        return quote_card.QuoteCard(**values)

    def test_sticker_is_512_square_webp_within_limit(self):
        data = quote_card.render(self.card())
        self.assertEqual(data[:4], b"RIFF")
        self.assertEqual(data[8:12], b"WEBP")
        self.assertLessEqual(len(data), 512 * 1024)
        image = Image.open(io.BytesIO(data))
        self.assertEqual(image.size, (512, 512))
        self.assertEqual(image.format, "WEBP")

    def test_corner_is_transparent_and_card_interior_is_opaque(self):
        image = Image.open(io.BytesIO(quote_card.render(self.card()))).convert("RGBA")
        self.assertEqual(image.getpixel((0, 0))[3], 0)
        self.assertGreaterEqual(image.getpixel((256, 256))[3], 240)

    def test_message_clamps_at_five_lines_with_ellipsis(self):
        text = "The quick brown fox jumps over the lazy dog. " * 12
        lines = quote_card._message_lines(self.card(text=text))
        self.assertLessEqual(len(lines), 5)
        self.assertTrue(lines[-1].endswith("\u2026"))

    def test_text_caps_are_enforced(self):
        long_text = "word " * 200
        sticker_text = quote_card._clamp_text(long_text, 140)
        share_text = quote_card._prepare_text(long_text, 260)
        self.assertLessEqual(len(sticker_text), 140)
        self.assertLessEqual(len(share_text), 260)
        self.assertTrue(sticker_text.endswith("\u2026"))
        self.assertTrue(share_text.endswith("\u2026"))

    def test_avatar_is_used_when_available(self):
        avatar = solid_image((210, 40, 40))
        image = Image.open(
            io.BytesIO(quote_card.render(self.card(avatar=avatar)))
        ).convert("RGBA")
        sample = image.getpixel((63, 196))
        self.assertGreater(sample[0], 120)
        self.assertGreater(sample[0], sample[2])

    def test_initials_fallback_is_dark(self):
        image = Image.open(io.BytesIO(quote_card.render(self.card()))).convert("RGBA")
        sample = image.getpixel((63, 196))
        self.assertLess(sample[0], 110)

    def test_photo_replaces_the_avatar_disc(self):
        photo = solid_image((30, 190, 70))
        image = Image.open(
            io.BytesIO(quote_card.render(self.card(photo=photo)))
        ).convert("RGBA")
        sample = image.getpixel((63, 196))
        self.assertGreater(sample[1], sample[0])
        self.assertGreater(sample[1], sample[2])

    def test_png_share_card_is_1080_by_1350(self):
        data = quote_card.render_png(self.card())
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        image = Image.open(io.BytesIO(data))
        self.assertEqual(image.size, (1080, 1350))
        self.assertEqual(image.format, "PNG")

    def test_empty_text_falls_back(self):
        self.assertEqual(quote_card._clamp_text("   ", 140), "No text")
        data = quote_card.render(self.card(text=""))
        self.assertEqual(Image.open(io.BytesIO(data)).size, (512, 512))

    def test_emoji_text_does_not_raise(self):
        data = quote_card.render(self.card(text="Shipping today \U0001f680 \U0001f4ac"))
        self.assertGreater(len(data), 0)

    def test_timestamp_does_not_change_a_handle_line(self):
        with_stamp = quote_card.render(self.card(timestamp="14:32"))
        without_stamp = quote_card.render(self.card(timestamp=None))
        self.assertEqual(with_stamp, without_stamp)


if __name__ == "__main__":
    unittest.main()
