"""Offline checks for the quote command layer."""

import ast
import asyncio
import dataclasses
import importlib.util
import re
import shlex
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "quote.py"
SHORT_NAME = re.compile(r"^dq_[0-9]+_[0-9]+_by_[A-Za-z0-9_]+$")

_CONSTANT_NAMES = {
    "_MAX_SLOT",
    "_MAX_COUNT",
    "_DEFAULT_EMOJI",
    "_CURRENT_SLOT",
    "_MESSAGE_LINK",
    "_VALUE_FLAGS",
    "_BOOL_FLAGS",
}
_PURE_NAMES = {
    "QuoteFlagError",
    "QuoteFlags",
    "_is_flag",
    "parse_flags",
    "parse_message_link",
    "pack_short_name",
    "pack_title",
    "rollover_slot",
    "free_slot_after",
    "_add_to_pack",
}


def load_pure_helpers():
    tree = ast.parse(PLUGIN.read_text("utf-8"), filename=str(PLUGIN))
    selected = [
        node
        for node in tree.body
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id in _CONSTANT_NAMES
                for target in node.targets
            )
        )
        or (isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in _PURE_NAMES)
        or (
            isinstance(node, ast.AsyncFunctionDef)
            and node.name in _PURE_NAMES
        )
    ]
    module = ast.Module(body=selected, type_ignores=[])
    module_object = types.ModuleType("dockyard_quote_helpers")
    sys.modules["dockyard_quote_helpers"] = module_object
    namespace = module_object.__dict__
    namespace.update(
        {
            "re": re,
            "shlex": shlex,
            "dataclass": dataclasses.dataclass,
        }
    )
    exec(compile(module, str(PLUGIN), "exec"), namespace)
    return namespace


def load_help():
    fake = types.ModuleType("pyUltroid")
    fake.ULTConfig = SimpleNamespace(lang="en")
    fake.udB = SimpleNamespace(get_key=lambda key: None)
    fake.LOGS = SimpleNamespace(exception=lambda *a, **k: None, info=lambda *a, **k: None)
    fns = types.ModuleType("pyUltroid.fns")
    fns.__path__ = []
    tools = types.ModuleType("pyUltroid.fns.tools")
    tools.translate = lambda *a, **k: ""
    previous = {
        name: sys.modules.get(name)
        for name in ("pyUltroid", "pyUltroid.fns", "pyUltroid.fns.tools")
    }
    sys.modules.update(
        {
            "pyUltroid": fake,
            "pyUltroid.fns": fns,
            "pyUltroid.fns.tools": tools,
        }
    )
    try:
        spec = importlib.util.spec_from_file_location(
            "dockyard_strings_help",
            ROOT / "strings" / "__init__.py",
            submodule_search_locations=[str(ROOT / "strings")],
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.get_help("quote")
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


class QuoteFlagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = load_pure_helpers()

    def parse(self, value):
        return self.helpers["parse_flags"](value)

    def test_defaults(self):
        flags = self.parse("")
        self.assertEqual(flags.slot, 1)
        self.assertEqual(flags.emoji, "\U0001f4ac")
        self.assertFalse(flags.preview)
        self.assertFalse(flags.photo)
        self.assertFalse(flags.png)
        self.assertIsNone(flags.count)
        self.assertIsNone(flags.link)
        self.assertIsNone(flags.name)

    def test_every_flag(self):
        flags = self.parse(
            "-e \U0001f525 -p 3 --preview --photo -n 4 "
            "--link https://t.me/example/42 --name Alex Morgan --png"
        )
        self.assertEqual(flags.emoji, "\U0001f525")
        self.assertEqual(flags.slot, 3)
        self.assertTrue(flags.preview)
        self.assertTrue(flags.photo)
        self.assertEqual(flags.count, 4)
        self.assertEqual(flags.link, "https://t.me/example/42")
        self.assertEqual(flags.name, "Alex Morgan")
        self.assertTrue(flags.png)

    def test_unknown_flag_is_rejected(self):
        with self.assertRaises(self.helpers["QuoteFlagError"]) as caught:
            self.parse("--wat")
        self.assertEqual(caught.exception.code, "unknown")

    def test_bad_numbers_are_rejected(self):
        for value in ("-p abc", "-p 0", "-p 21"):
            with self.subTest(value=value):
                with self.assertRaises(self.helpers["QuoteFlagError"]) as caught:
                    self.parse(value)
                self.assertEqual(caught.exception.code, "slot")
        for value in ("-n x", "-n 0", "-n 11"):
            with self.subTest(value=value):
                with self.assertRaises(self.helpers["QuoteFlagError"]) as caught:
                    self.parse(value)
                self.assertEqual(caught.exception.code, "count")

    def test_missing_values_are_rejected(self):
        for value in ("-e", "-p", "-n", "--link", "--name"):
            with self.subTest(value=value):
                with self.assertRaises(self.helpers["QuoteFlagError"]) as caught:
                    self.parse(value)
                self.assertEqual(caught.exception.code, "missing")

    def test_bad_link_is_rejected(self):
        with self.assertRaises(self.helpers["QuoteFlagError"]) as caught:
            self.parse("--link https://example.com/not-telegram")
        self.assertEqual(caught.exception.code, "link")

    def test_quoted_name_keeps_spaces(self):
        flags = self.parse('--name "Alex Morgan" --png')
        self.assertEqual(flags.name, "Alex Morgan")
        self.assertTrue(flags.png)

    def test_message_links_parse_public_and_private(self):
        parse = self.helpers["parse_message_link"]
        self.assertEqual(parse("https://t.me/example/42"), ("example", 42))
        self.assertEqual(parse("t.me/example/42?single"), ("example", 42))
        self.assertEqual(
            parse("https://t.me/c/1234567890/7"),
            (-1001234567890, 7),
        )
        self.assertEqual(
            parse("https://t.me/c/1234567890/12/7"),
            (-1001234567890, 7),
        )
        self.assertIsNone(parse("https://example.com/example/42"))


class QuotePackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = load_pure_helpers()

    def test_short_name_format_and_length(self):
        short = self.helpers["pack_short_name"](123456789, 2, "DockyardBot")
        self.assertRegex(short, SHORT_NAME)
        self.assertLessEqual(len(short), 64)
        self.assertEqual(short, "dq_123456789_2_by_DockyardBot")

    def test_short_name_sanitizes_and_truncates(self):
        short = self.helpers["pack_short_name"](1, 20, "bot-name-" + "x" * 100)
        self.assertRegex(short, SHORT_NAME)
        self.assertLessEqual(len(short), 64)

    def test_titles_include_the_slot_after_the_first(self):
        title = self.helpers["pack_title"]
        self.assertEqual(title("Alex Morgan", 1), "Quotes by Alex Morgan")
        self.assertEqual(title("Alex Morgan", 3), "Quotes 3 by Alex Morgan")

    def test_rollover_stops_at_twenty(self):
        rollover = self.helpers["rollover_slot"]
        self.assertEqual(rollover(1), 2)
        self.assertEqual(rollover(19), 20)
        self.assertIsNone(rollover(20))

    def test_free_slot_after_wraps(self):
        free = self.helpers["free_slot_after"]
        self.assertEqual(free(3, {1, 2, 3, 4}), 5)
        self.assertEqual(free(20, {1, 2, 3}), 4)
        self.assertEqual(free(20, set(range(1, 20))), 20)
        self.assertIsNone(free(20, set(range(1, 21))))

    def test_occupied_pack_advances_one_slot(self):
        helpers = self.helpers
        values = {}

        class FakeKeyManager:
            def __init__(self, key):
                self.key = key

            def get(self):
                return values.get(self.key)

        class Request:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class InputStickerSetShortName:
            def __init__(self, short_name):
                self.short_name = short_name

        class InputStickerSetItem:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class PackShortNameOccupiedError(Exception):
            pass

        class OtherError(Exception):
            pass

        async def run():
            calls = []

            async def client(request):
                calls.append(request)
                if isinstance(request, CreateStickerSetRequestStub):
                    if len(calls) == 1:
                        raise PackShortNameOccupiedError()
                return SimpleNamespace(ok=True)

            class CreateStickerSetRequestStub(Request):
                pass

            namespace = dict(helpers)
            namespace.update(
                {
                    "KeyManager": FakeKeyManager,
                    "udB": SimpleNamespace(
                        set_key=lambda key, value: values.__setitem__(key, value)
                    ),
                    "AddStickerToSetRequest": Request,
                    "CreateStickerSetRequest": CreateStickerSetRequestStub,
                    "InputStickerSetShortName": InputStickerSetShortName,
                    "InputStickerSetItem": InputStickerSetItem,
                    "PeerIdInvalidError": OtherError,
                    "PackShortNameInvalidError": OtherError,
                    "PackShortNameOccupiedError": PackShortNameOccupiedError,
                    "StickersetInvalidError": OtherError,
                    "StickersTooMuchError": OtherError,
                    "StickerpackStickersTooMuchError": OtherError,
                    "_CURRENT_SLOT": "QUOTE_PACK_CURRENT",
                }
            )
            exec(
                compile(
                    ast.Module(
                        body=[
                            node
                            for node in ast.parse(PLUGIN.read_text("utf-8")).body
                            if isinstance(node, ast.AsyncFunctionDef)
                            and node.name == "_add_to_pack"
                        ],
                        type_ignores=[],
                    ),
                    str(PLUGIN),
                    "exec",
                ),
                namespace,
            )
            result = await namespace["_add_to_pack"](
                client,
                user_id=42,
                name="Alex Morgan",
                document=object(),
                emoji="\U0001f4ac",
                slot=1,
                bot_username="DockyardBot",
            )
            return result, calls, values

        result, calls, cache = asyncio.run(run())
        short_name, used_slot, created, adjusted = result
        self.assertEqual(used_slot, 2)
        self.assertTrue(created)
        self.assertTrue(adjusted)
        self.assertEqual(short_name, "dq_42_2_by_DockyardBot")
        self.assertEqual(cache["QUOTE_PACK_2"], short_name)
        self.assertEqual(cache["QUOTE_PACK_CURRENT"], 2)
        self.assertEqual(calls[1].kwargs["title"], "Quotes 2 by Alex Morgan")


class QuoteHelpTests(unittest.TestCase):
    def test_help_key_resolves(self):
        help_text = load_help()
        self.assertTrue(help_text.startswith("Commands\n\n"))
        self.assertIn("q <flags>", help_text)
        self.assertIn("qpack reset", help_text)
        self.assertNotIn("Warning: could not load", help_text)


if __name__ == "__main__":
    unittest.main()
