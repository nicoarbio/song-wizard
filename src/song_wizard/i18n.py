"""The interface's languages: Spanish, English and Portuguese. The code carries no texts, only
their keys ("library.refresh"); static/i18n/<lang>.json holds each key's text in that language,
for the page and the server alike (the server's answers to the page and the pages it makes to
print)."""

import json
import re
from importlib import resources

LANGS = ("es", "en", "pt")
_texts = {}


def texts(lang):
    """{key: text} in this language."""
    if lang not in _texts:
        file = resources.files("song_wizard").joinpath("static", "i18n", f"{lang}.json")
        _texts[lang] = json.loads(file.read_text(encoding="utf-8"))
    return _texts[lang]


def script():
    """All three, for the page: window.TEXTS = {"es": {...}, "en": {...}, "pt": {...}}."""
    return "window.TEXTS = " + json.dumps({lang: texts(lang) for lang in LANGS}, ensure_ascii=False) + ";\n"


def say(lang, key, **values):
    """The text of this key in this language (else in Spanish, else the key), with {name} filled in."""
    text = texts(lang if lang in LANGS else "es").get(key) or texts("es").get(key) or key
    return re.sub(r"\{(\w+)\}", lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), text)


class Said(ValueError):
    """A problem to tell the page, in its language when answered: the text's key and its values."""

    def __init__(self, key, **values):
        super().__init__(say("es", key, **values))
        self.text, self.values = key, values
