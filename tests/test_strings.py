"""The interface's translations (static/strings.js): every text the page shows has its English
and Portuguese, and they don't ask for anything the page doesn't give."""

import ast
import json
import re
from html.parser import HTMLParser
from importlib import resources

# Names that read the same in every language.
SAME = {"song-wizard", "song-wizard ui", "Español", "English", "Português", "es", "en", "pt", "Piano", "MP3", "BPM",
        "min", "Reaper", "−10 ms", "+10 ms"}


def page():
    return resources.files("song_wizard").joinpath("ui.html").read_text(encoding="utf-8")


def strings():
    text = resources.files("song_wizard").joinpath("static", "strings.js").read_text(encoding="utf-8")
    start = text.index("window.STRINGS = ") + len("window.STRINGS = ")
    return json.loads(text[start:text.rindex("}") + 1])


def texts(html):
    """translate("...") in the code, and the markup's fixed texts and titles, placeholders, labels."""
    code = html[html.rindex("<script>"):]
    found = [json.loads('"' + m.group(1) + '"') for m in re.finditer(r'translate\("((?:[^"\\]|\\.)*)"', code)]
    body = html[html.index("<body>"):html.rindex("<script>")]

    class Markup(HTMLParser):
        skip = 0

        def handle_starttag(self, tag, attrs):
            self.skip += tag in ("script", "style")
            found.extend(re.sub(r"\s+", " ", v).strip() for k, v in attrs
                         if k in ("title", "placeholder", "aria-label") and v and re.search(r"[^\W\d_]{2}", v))

        def handle_endtag(self, tag):
            self.skip -= tag in ("script", "style")

        def handle_data(self, data):
            t = re.sub(r"\s+", " ", data).strip()
            if not self.skip and t and re.search(r"[^\W\d_]{2}", t):
                found.append(t)

    Markup().feed(body)
    return set(found)


def server_texts():
    """What the server says to the page and prints: say(...), self.say(...), self.error(status, ...),
    Said(...) and NeedsCommand(command, ...), read with Python's own parser."""
    found = set()
    for name in ("ui.py", "setlist.py", "lyrics.py"):
        tree = ast.parse(resources.files("song_wizard").joinpath(name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            at = {"say": 1 if isinstance(node.func, ast.Name) else 0, "error": 1, "Said": 0, "NeedsCommand": 1}.get(func)
            if at is not None and len(node.args) > at and isinstance(node.args[at], ast.Constant) and isinstance(node.args[at].value, str):
                found.add(node.args[at].value)
    found.discard("not found")  # an address nobody asks for, in English
    from song_wizard import lyrics
    return found | set(lyrics.NAMES.values())  # the markers' colors, said by name


def test_every_text_has_its_translations():
    table = strings()
    missing = sorted(t for t in texts(page()) | server_texts() if t not in table and t not in SAME)
    assert not missing, f"{len(missing)} texts without translation: {missing[:20]}"


def test_translations_are_whole():
    for spanish, (english, portuguese) in strings().items():
        wanted = set(re.findall(r"\{(\w+)\}", spanish))
        for t in (english, portuguese):
            assert t.strip() or not spanish.strip(), spanish
            # A translation may leave out a piece (the plural "s" in English) but never ask for one
            # the page doesn't give.
            assert set(re.findall(r"\{(\w+)\}", t)) <= wanted, (spanish, t)


def test_no_leftovers():
    """Every translation is still used (else the text changed in the page and this one is stale)."""
    used = texts(page()) | server_texts()
    stale = sorted(k for k in strings() if k not in used)
    assert not stale, stale


def test_the_server_answers_in_the_pages_language(tmp_path):
    from song_wizard import i18n, setlist
    from song_wizard.i18n import say
    assert say("en", "fuera de la carpeta de música") == "outside the music folder"
    assert say("pt", "Tonalidad: {label}", label="a.opus") == "Tom: a.opus"
    assert say("es", "Tonalidad: {label}", label="a.opus") == "Tonalidad: a.opus"
    assert say("en", "un texto que no está") == "un texto que no está"  # untranslated: as it is
    assert "<th>Song</th>" in setlist.page("Show", [], lang="en") and "Imprimir" in setlist.page("Show", [])
    assert isinstance(i18n.Said("no hay cambios"), ValueError)


def test_interface_in_english(tmp_path):
    import threading
    from test_ui import TOKEN, request
    from song_wizard import ui
    root = tmp_path / "music"
    (root / "Show").mkdir(parents=True)
    (root / "Show" / "a.opus").write_bytes(b"x")
    runner = ui.Runner()
    runner.run = lambda job: setattr(job, "status", "done")
    httpd = ui.Server(("127.0.0.1", 0), ui.make_handler(TOKEN, root, runner, 0))
    port = httpd.server_address[1]
    httpd.RequestHandlerClass = ui.make_handler(TOKEN, root, runner, port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        response, content = request(port, "GET", "/api/info?path=../x", headers={"X-Lang": "en"})
        assert json.loads(content)["error"] == "outside the music folder"
        response, content = request(port, "POST", "/api/jobs", {"action": "key", "paths": ["Show/a.opus"]}, headers={"X-Lang": "pt"})
        assert json.loads(content)["title"] == "Tom: a.opus"
        response, content = request(port, "POST", "/api/jobs", {"action": "nope"}, headers={"X-Lang": "en"})
        assert json.loads(content)["error"] == "unknown action: nope"
        response, content = request(port, "GET", "/setlist?folder=Show&lang=en")
        assert b"<th>Song</th>" in content and b'lang="en"' in content
    finally:
        httpd.shutdown()
        httpd.server_close()
