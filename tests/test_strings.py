"""The interface's texts (static/i18n/<lang>.json): the three languages have the same keys, every
key the page or the server uses is there, none is left over, and no text asks for a value its
key's Spanish doesn't have."""

import ast
import json
import re
import threading
from importlib import resources

LANGS = ("es", "en", "pt")


def texts(lang):
    return json.loads(resources.files("song_wizard").joinpath("static", "i18n", f"{lang}.json").read_text(encoding="utf-8"))


def page_keys():
    """say("key") in the page's code, and data-text / data-text-<attribute> in its markup."""
    html = resources.files("song_wizard").joinpath("ui.html").read_text(encoding="utf-8")
    code = html[html.rindex("<script>"):]
    keys = set(re.findall(r'\bsay\("([\w.]+)"', code))
    keys |= set(re.findall(r'\bdata-text(?:-[\w-]+)?="([\w.]+)"', html))
    return keys


def server_keys():
    """say(lang, key), self.say(key), self.error(status, key), Said(key), NeedsCommand(command, key),
    read with Python's own parser; and the lyrics markers' color names."""
    from song_wizard import lyrics
    keys = set(lyrics.NAMES.values())
    for name in ("ui.py", "setlist.py", "lyrics.py", "sheet.py", "drumsheet.py"):
        tree = ast.parse(resources.files("song_wizard").joinpath(name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            at = {"say": 1 if isinstance(node.func, ast.Name) else 0, "error": 1, "Said": 0, "NeedsCommand": 1}.get(func)
            if at is not None and len(node.args) > at and isinstance(node.args[at], ast.Constant) and isinstance(node.args[at].value, str):
                keys.add(node.args[at].value)
    return keys


def test_the_languages_have_the_same_keys():
    es = set(texts("es"))
    for lang in ("en", "pt"):
        assert set(texts(lang)) == es, (lang, sorted(set(texts(lang)) ^ es)[:10])


def test_every_key_used_is_there():
    known = set(texts("es"))
    missing = sorted((page_keys() | server_keys()) - known)
    assert not missing, missing


def test_no_leftovers():
    stale = sorted(set(texts("es")) - page_keys() - server_keys())
    assert not stale, stale


def test_texts_are_whole():
    es = texts("es")
    for lang in LANGS:
        for key, text in texts(lang).items():
            assert text.strip() or not es[key].strip(), (lang, key)
            # A language may leave out a piece (the plural "s" in English) but never ask for a value
            # the Spanish, which the code is written against, doesn't have.
            assert set(re.findall(r"\{(\w+)\}", text)) <= set(re.findall(r"\{(\w+)\}", es[key])), (lang, key, text)


def test_say():
    from song_wizard import i18n, setlist
    from song_wizard.i18n import say
    assert say("en", "server.outside_music_folder") == "outside the music folder"
    assert say("pt", "server.key", label="a.opus") == "Tom: a.opus"
    assert say("es", "server.key", label="a.opus") == "Tonalidad: a.opus"
    assert say("xx", "server.key", label="a") == "Tonalidad: a"  # an unknown language: Spanish
    assert say("en", "no.such.key") == "no.such.key"
    assert "<th>Song</th>" in setlist.page("Show", [], lang="en") and "class=k>Key</th>" in setlist.page("Show", [], lang="en")
    assert "Imprimir" in setlist.page("Show", [])
    assert str(i18n.Said("server.there_are_no_changes")) == "no hay cambios"
    assert i18n.script().startswith("window.TEXTS = {")


def test_interface_in_english(tmp_path):
    from test_ui import TOKEN, request
    from song_wizard import ui
    root = tmp_path / "music"
    (root / "Show" / "a").mkdir(parents=True)
    (root / "Show" / "a" / "a.opus").write_bytes(b"x")
    runner = ui.Runner()
    runner.run = lambda job: setattr(job, "status", "done")
    httpd = ui.Server(("127.0.0.1", 0), ui.make_handler(TOKEN, root, runner, 0))
    port = httpd.server_address[1]
    httpd.RequestHandlerClass = ui.make_handler(TOKEN, root, runner, port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        response, content = request(port, "GET", "/api/info?path=../x", headers={"X-Lang": "en"})
        assert json.loads(content)["error"] == "outside the music folder"
        response, content = request(port, "POST", "/api/jobs", {"action": "key", "paths": ["Show/a/a.opus"]}, headers={"X-Lang": "pt"})
        assert json.loads(content)["title"] == "Tom: a.opus"
        response, content = request(port, "POST", "/api/jobs", {"action": "nope"}, headers={"X-Lang": "en"})
        assert json.loads(content)["error"] == "unknown action: nope"
        response, content = request(port, "GET", "/setlist?folder=Show&lang=en")
        assert b"<th>Song</th>" in content and b'lang="en"' in content
        response, content = request(port, "GET", "/static/texts.js", token=None)
        assert response.status == 200 and content.startswith(b"window.TEXTS = ")
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_the_language_picker_is_never_translated():
    """Each language is named in itself, in every language (once, "en" got the key of "in" from
    "in Music")."""
    html = resources.files("song_wizard").joinpath("ui.html").read_text(encoding="utf-8")
    picker = html[html.index('id="lang"'):html.index("</select>", html.index('id="lang"'))]
    assert "data-text" not in picker.replace('data-text-aria-label="data.language"', "")
    for lang, name in zip(LANGS, ["Español", "English", "Português"]):
        assert f'<option value="{lang}">{name}</option>' in picker
