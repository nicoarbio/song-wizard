"""The interface's languages: Spanish, English and Portuguese. Texts are written in Spanish where
they're used; static/strings.js holds their English and Portuguese, for the page and the server
alike (the server's answers to the page and the pages it makes to print)."""

import json
import re
from importlib import resources

LANGS = ("es", "en", "pt")
_table = None


def table():
    """{Spanish: [English, Portuguese]}."""
    global _table
    if _table is None:
        text = resources.files("song_wizard").joinpath("static", "strings.js").read_text(encoding="utf-8")
        start = text.index("window.STRINGS = ") + len("window.STRINGS = ")
        _table = json.loads(text[start:text.rindex("}") + 1])
    return _table


def say(lang, text, **values):
    """text in this language (as it is if there's no translation), with {name} filled in."""
    if lang in ("en", "pt"):
        found = table().get(text)
        if found and found[LANGS.index(lang) - 1]:
            text = found[LANGS.index(lang) - 1]
    return re.sub(r"\{(\w+)\}", lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), text)


class Said(ValueError):
    """A problem to tell the page, in its language when answered: the text and its values."""

    def __init__(self, text, **values):
        super().__init__(say("es", text, **values))
        self.text, self.values = text, values
