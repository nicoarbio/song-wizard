"""Local web interface: a page in the browser that runs the same commands as the terminal.

It only listens on 127.0.0.1, and only takes requests made by its own page: browsers say where
each request comes from (Sec-Fetch-Site, or Origin), so any other web page open in the browser,
which could otherwise send requests here, is refused. The terminal's own requests (ui --stop) carry
a random token instead, kept in a file only the user can read.
Each action runs the real CLI as a subprocess, one at a time, and the page polls its output.
"""

import collections
import hashlib
import http.client
import itertools
import json
import mimetypes
import os
import re
import secrets
import signal
import socketserver
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import align, archives, log, paths, results, system
from .i18n import LANGS, Said, say
from .audio import AUDIO_EXTS, GENERATED, MAIN_FORMATS, base_of
from .paths import music_dir

PORT = 8765
STATIC = {"/favicon.ico": ("favicon.ico", "image/x-icon"), "/static/logo.png": ("logo.png", "image/png"),
          "/static/pitch.js": ("pitch.js", "text/javascript"),
          "/static/strings.js": ("strings.js", "text/javascript; charset=utf-8")}
# Output of a job that is kept to show in the page.
LOG_LINES = 2000


class Job:
    ids = itertools.count(1)

    def __init__(self, title, args):
        self.id = next(Job.ids)
        self.title = title
        self.args = args
        self.status = "queued"  # queued, running, done, failed, cancelled
        self.lines = []
        self.progress = ""  # last line written with \r (progress bars)
        self.process = None
        self.started = self.ended = None

    def summary(self, since=0):
        return {"id": self.id, "title": self.title, "status": self.status, "progress": self.progress,
                "percent": percent_of(self.progress), "step": self.lines[-1] if self.lines else "",
                "lines": self.lines[since:], "total": len(self.lines),
                "started": self.started, "ended": self.ended, "now": time.time()}


def percent_of(progress):
    """The percentage in a progress line, from song-wizard ("  45%  (2/5) Title"), the
    separation models (" 45%|████▌     | 9/20") or yt-dlp ("[download]  45.3% of 3.40MiB")."""
    match = re.search(r"(\d+(?:\.\d+)?)%", progress)
    return min(float(match.group(1)), 100.0) if match else None


class Runner:
    """Runs jobs one at a time: separation alone can use the whole GPU."""

    def __init__(self):
        self.jobs = collections.OrderedDict()
        self.queue = collections.deque()
        self.lock = threading.Lock()
        self.wake = threading.Event()
        threading.Thread(target=self.loop, daemon=True).start()

    def add(self, title, args):
        job = Job(title, args)
        with self.lock:
            self.jobs[job.id] = job
            self.queue.append(job)
            while len(self.jobs) > 50:
                self.jobs.popitem(last=False)
        self.wake.set()
        return job

    def cancel(self, job):
        with self.lock:
            if job.status == "queued":
                self.queue.remove(job)
                job.status = "cancelled"
            elif job.status == "running" and job.process:
                job.status = "cancelled"
                job.process.terminate()

    def loop(self):
        while True:
            self.wake.wait()
            with self.lock:
                job = self.queue.popleft() if self.queue else None
                if not self.queue:
                    self.wake.clear()
            if job:
                self.run(job)

    def run(self, job):
        job.status, job.started = "running", time.time()
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        try:
            job.process = subprocess.Popen([sys.executable, "-m", "song_wizard", *job.args],
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           stdin=subprocess.DEVNULL, env=env)
        except OSError as e:
            job.lines.append(str(e))
            job.status, job.ended = "failed", time.time()
            return
        pending = b""
        while chunk := job.process.stdout.read1(4096):
            pending += chunk
            # Progress bars rewrite their line with \r: only the latest one is kept, as "progress".
            while (cut := min((i for i in (pending.find(b"\n"), pending.find(b"\r")) if i >= 0), default=-1)) >= 0:
                text, sep, pending = pending[:cut], pending[cut:cut + 1], pending[cut + 1:]
                if sep == b"\n":
                    self.line(job, text)
                else:
                    job.progress = text.decode(errors="replace").strip()
        self.line(job, pending)
        code = job.process.wait()
        if job.status != "cancelled":
            job.status = "done" if code == 0 else "failed"
        job.progress = ""
        job.ended = time.time()

    @staticmethod
    def line(job, raw):
        text = raw.decode(errors="replace").rstrip()
        if text:
            job.lines.append(text)
            del job.lines[:-LOG_LINES]


def read_results(folder, command):
    """key.txt / bpm.txt of a folder as {file name: result}."""
    path = folder / f"{command}.txt"
    found = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.startswith("#") and "\t" in line:
                name, text = line.split("\t", 1)
                found[name] = text.strip()
    return found


# When a song exists in several formats ("Title.opus" and "Title.wav" from download --wav, or
# "Title.mp3" from convert), the first of these is the song and the rest are its files.


DURATIONS = {}


def duration(path):
    """Length in seconds (ffprobe), remembered while the file doesn't change; None if unreadable."""
    key = (str(path), path.stat().st_mtime)
    if key not in DURATIONS:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
        try:
            DURATIONS[key] = round(float(out.stdout.strip()), 3)
        except ValueError:
            DURATIONS[key] = None
    return DURATIONS[key]


PEAKS = collections.OrderedDict()


def peaks(path, n, start=None, end=None):
    """The audio's outline for drawing it: the loudest sample in each of n slices, of the whole
    file or of start..end seconds. Remembered for the last files asked."""
    key = (str(path), path.stat().st_mtime, n, start, end)
    if key in PEAKS:
        PEAKS.move_to_end(key)
        return PEAKS[key]
    import numpy as np

    # Low rate for a whole song (enough for a picture); finer for a zoomed stretch.
    sr = 8000 if start is None else 22050
    command = ["ffmpeg", "-nostdin", "-v", "error"]
    if start is not None:
        command += ["-ss", f"{max(0.0, start):.3f}"]
    command += ["-i", str(path)]
    if start is not None and end is not None:
        command += ["-t", f"{max(0.01, end - max(0.0, start)):.3f}"]
    command += ["-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    samples = np.abs(np.frombuffer(subprocess.run(command, capture_output=True, check=True).stdout, dtype=np.float32))
    edges = np.linspace(0, len(samples), n + 1).astype(int)
    values = [float(samples[a:b].max()) if b > a else 0.0 for a, b in zip(edges[:-1], edges[1:])]
    result = {"from": max(0.0, start or 0.0), "seconds": len(samples) / sr,
              "peaks": [round(v, 4) for v in values]}
    PEAKS[key] = result
    while len(PEAKS) > 64:
        PEAKS.popitem(last=False)
    return result


# How much audio one open-ended request gets (about 6 s of a 32-bit float stem).
AUDIO_CHUNK = 2 << 20


class NeedsCommand(Said):
    """A request that can't go on until the user runs a command; the page offers to copy it."""

    def __init__(self, command, text, **values):
        super().__init__(text, **values)
        self.command = command


def folder_from(text):
    """A folder typed or picked in the page (a Windows path works on WSL): its path, or None.
    It must already exist."""
    if not text or not str(text).strip():
        return None
    path = Path(system.local_path(str(text)))
    if letter := system.unmounted_drive(path):
        raise NeedsCommand(system.mount_command(letter),
                           "WSL no ve la unidad {letter}: (pasa con la de Google Drive). Conectala corriendo este "
                           "comando en la terminal de WSL (pide tu contraseña) y probá de nuevo.", letter=letter)
    if not path.is_absolute() or not path.is_dir():
        raise Said("no existe la carpeta {folder}", folder=text)
    return str(path)


def outside(root, missing=False):
    """Places outside the music folder where downloads went (a synced drive, say), like another
    music folder each: {"@<key>": folder}. The page names their files "@<key>/<folder>/<file>";
    the key is a short hash of the place, so it stays the same between runs. missing: also the
    ones that aren't there now."""
    root = root.resolve()
    found = {}
    for place in archives.places(missing=missing):
        place = place.resolve()
        if place != root and root not in place.parents and place not in root.parents:
            found["@" + hashlib.sha1(str(place).encode()).hexdigest()[:8]] = place
    return found


def with_audio(folder):
    try:
        return any(os.path.splitext(n)[1].lower() in AUDIO_EXTS for n in os.listdir(folder))
    except OSError:
        return False


def library(root):
    """The music folder and the folders directly in it, plus playlists kept elsewhere, with their
    songs and, for each song, the files generated from it (stems, transpositions, conversions)."""
    if not root.exists():
        return []
    folders = []
    known = archives.playlists()
    subfolders = sorted((p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")),
                        key=lambda p: p.name.lower())
    places = [(root, "", f) for f in [root, *subfolders]]
    gone = []
    for key, place in sorted(outside(root, missing=True).items(), key=lambda kv: str(kv[1]).lower()):
        if not place.is_dir():
            # Not hidden: its songs would just vanish from the library (a drive not connected
            # now, like Google Drive's on WSL after a restart, or a folder moved by hand).
            letter = system.unmounted_drive(place)
            gone.append({"name": place.name, "path": key, "songs": [], "extras": [], "playlist": None,
                         "location": system.shown_path(place),
                         "missing": {"drive": letter, "command": system.mount_command(letter) if letter else None}})
            continue
        inside = sorted((p for p in place.iterdir() if p.is_dir() and not p.name.startswith(".")),
                        key=lambda p: p.name.lower()) if place.is_dir() else []
        places += [(place, key, f) for f in [place, *inside] if with_audio(f)]
    for place, key, folder in places:
        rel = lambda path, place=place, key=key: "/".join(filter(None, [key, relative(place, path)]))
        try:
            names = sorted(n for n in os.listdir(folder)
                           if os.path.splitext(n)[1].lower() in AUDIO_EXTS and (folder / n).is_file())
        except OSError:
            continue
        keys, bpms = read_results(folder, "key"), read_results(folder, "bpm")
        clicks = read_results(folder, "click")
        try:
            entries = {n.lower() for n in os.listdir(folder)}
        except OSError:
            entries = set()
        groups = collections.defaultdict(list)
        for n in names:
            groups[base_of(n)].append(n)
        songs, extras = [], []
        for base, members in sorted(groups.items(), key=lambda g: g[0].lower()):
            originals = [n for n in members
                         if os.path.splitext(n)[0] == base and not GENERATED.search(base)]
            if not originals:  # click tracks: generated, but not from a song
                extras += [file_entry(rel, folder / n, keys, bpms) for n in members]
                continue
            main = min(originals, key=lambda n: MAIN_FORMATS.index(os.path.splitext(n)[1].lower())
                       if os.path.splitext(n)[1].lower() in MAIN_FORMATS else len(MAIN_FORMATS))
            songs.append({"name": main, "path": rel(folder / main),
                          "key": keys.get(main), "bpm": bpms.get(main), "click": align.parse(clicks.get(main)),
                          "lyrics": (folder / f"{base}.lyrics.json").is_file(),
                          "reaper": f"{base}.rpp".lower() in entries,
                          "files": [file_entry(rel, folder / n, keys, bpms) for n in members if n != main]})
        # The song's data (title, artist, album...), for the library and its filter.
        from . import tags
        found = tags.read_many(folder / song["name"] for song in songs)
        for song in songs:
            data = found[folder / song["name"]]
            song["tags"] = {k: data[k] for k in (*tags.MAIN, "composer", "album_artist") if data.get(k)}
        if songs or extras or folder != root:
            playlist = archives.playlist_for(folder, known) if folder != root else None
            folders.append({"name": folder.name if folder != root else "(carpeta principal)",
                            "path": rel(folder), "songs": songs, "extras": extras,
                            "location": system.shown_path(place) if key else None,
                            "playlist": {k: playlist[k] for k in ("id", "title", "url", "wav")} if playlist else None})
    return folders + gone


_latest = {"at": 0.0, "version": None, "retired": {}}
# Tells one start of the server from the next: after a restart the page reloads when it changes
# (a quick restart may never look down to it, and the version can be the same).
SERVER_ID = secrets.token_hex(6)


def version_info(force=False):
    """This version and the newest one on offer, checked at most every 6 hours (or now); and why
    this one was retired, if it was (then "move" offers the one on offer, even if older)."""
    from . import __version__, updates
    if force or not _latest["at"] or time.monotonic() - _latest["at"] > 6 * 3600:
        good, held = updates.offered()
        found = good[-1] if good else None
        # A failed check (no internet) is tried again on the next page load, not in 6 hours.
        _latest.update(at=time.monotonic() if found else 0.0, version=found, retired=held)
    found, why = _latest["version"], _latest["retired"].get(__version__)
    return {"current": __version__, "latest": found, "newer": updates.newer(found or ""),
            "retired": why, "move": bool(found and (updates.newer(found) or (why and found != __version__))),
            "server": SERVER_ID}


def restart(port):
    """Close this server and start it again on the same port, from a process of its own (this
    one can't outlive itself). It runs the installed song-wizard, so after an upgrade the new
    one starts."""
    out = server_output()
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out.with_name("interface-restart.txt"), "w") as f:
        subprocess.Popen([sys.executable, "-m", "song_wizard", "ui", "--restart", "--yes", "--no-browser",
                          "--port", str(port)], stdin=subprocess.DEVNULL, stdout=f, stderr=f,
                         start_new_session=True, cwd=str(Path.home()))


_reaper = {"at": 0.0, "installed": False}


def reaper_installed():
    """Whether REAPER is installed, checked again at most once a minute (on WSL it can take a
    Windows command)."""
    from . import reaper
    if not _reaper["at"] or time.monotonic() - _reaper["at"] > 60:
        _reaper.update(at=time.monotonic(), installed=reaper.installed())
    return _reaper["installed"]


def file_entry(rel, path, keys, bpms):
    """A generated file. Stems can be analyzed too ("bpm" on the drums alone is often more
    reliable), so they carry their own results."""
    return {"name": path.name, "path": rel(path), "size": path.stat().st_size,
            "key": keys.get(path.name), "bpm": bpms.get(path.name)}


def relative(base, path):
    return path.relative_to(base).as_posix() if path != base else ""


def make_handler(token, root, runner, port):
    page = resources.files("song_wizard").joinpath("ui.html").read_text(encoding="utf-8")
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, body=b"", kind="application/json", headers=()):
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in headers:
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def json(self, data, status=HTTPStatus.OK):
            self.send(status, json.dumps(data, ensure_ascii=False).encode())

        @property
        def lang(self):
            """The page's language: it says so in every request (and in links it opens)."""
            wanted = self.headers.get("X-Lang") or parse_qs(urlparse(self.path).query).get("lang", [""])[0]
            return wanted if wanted in LANGS else "es"

        def say(self, text, **values):
            return say(self.lang, text, **values)

        def error(self, status, message, **values):
            """message: in Spanish, as written here; it goes out in the page's language."""
            self.json({"error": self.say(message, **values)}, status)

        def authorized(self, query, page=False):
            # The Host check is against DNS rebinding (another site's name pointed at 127.0.0.1).
            if self.headers.get("Host") not in allowed_hosts:
                return False
            # The terminal (and links from before 0.10, which had it in the URL).
            given = self.headers.get("X-Token") or query.get("t", [""])[0]
            if given:
                return secrets.compare_digest(given, token)
            return self.from_this_page(page)

        def from_this_page(self, page):
            """Whether the browser says this request comes from the interface itself. Any other
            page is refused, even another local server on another port (same-site, but not
            same-origin)."""
            site = self.headers.get("Sec-Fetch-Site")
            if site:
                if site == "same-origin" or (site == "none" and self.command == "GET"):
                    return True  # "none": typed in, a bookmark, or opened by the terminal
                # A link to the interface from somewhere else opens the page, and nothing more.
                return page and self.command == "GET" and self.headers.get("Sec-Fetch-Mode") == "navigate"
            # Browsers from before Sec-Fetch-Site (2020-2023) still send Origin on what matters.
            return self.headers.get("Origin") in {f"http://{h}" for h in allowed_hosts}

        def resolve(self, name):
            """A path from the page, which must stay inside the music folder or, for "@<id>/...",
            inside that playlist's folder."""
            base = root
            if name.startswith("@"):
                key, _, name = name.partition("/")
                base = outside(root).get(key)
                if base is None:
                    raise PermissionError(key)
            base = base.resolve()
            path = (base / name).resolve()
            if path != base and base not in path.parents:
                raise PermissionError(name)
            return path

        def do_GET(self):
            url = urlparse(self.path)
            query = parse_qs(url.query)
            # The icon and the logo: fixed files, asked for by the browser without the token.
            if url.path in STATIC and self.headers.get("Host") in allowed_hosts:
                name, kind = STATIC[url.path]
                body = resources.files("song_wizard").joinpath("static", name).read_bytes()
                return self.send(HTTPStatus.OK, body, kind)
            if not self.authorized(query, page=url.path == "/"):
                return self.error(HTTPStatus.FORBIDDEN, "Este pedido no viene de la interfaz de song-wizard.")
            if url.path == "/":
                return self.send(HTTPStatus.OK, page.encode(), "text/html; charset=utf-8")
            if url.path == "/api/library":
                return self.json({"root": str(root), "folders": library(root), "fileManager": system.file_manager_name(),
                                  "reaper": reaper_installed()})
            if url.path == "/api/archives":
                meta = {p["id"]: p for p in archives.playlists()}
                return self.json([{"number": i, "id": a, "title": t, "songs": n, "changed": f"{c:%Y-%m-%d %H:%M}",
                                   "url": meta.get(a, {}).get("url"), "wav": meta.get(a, {}).get("wav", False),
                                   "folder": system.shown_path(meta[a]["folder"]) if meta.get(a, {}).get("folder") else None}
                                  for i, (a, t, n, c) in enumerate(archives.entries(), 1)])
            if url.path == "/api/jobs":
                since = int(query.get("since", ["0"])[0] or 0)
                with runner.lock:
                    jobs = [j.summary(since if j.id == int(query.get("job", ["0"])[0] or 0) else len(j.lines))
                            for j in runner.jobs.values()]
                return self.json(jobs)
            if url.path == "/api/audio":
                return self.audio(query.get("path", [""])[0])
            if url.path == "/api/version":
                return self.json(version_info(force="check" in query))
            if url.path == "/api/reaper/setting":
                from . import reaper
                return self.json({**reaper.setting(), "installed": reaper_installed()})
            if url.path == "/api/tags":
                # All the data a file keeps, and what changing it would touch.
                from . import tags
                try:
                    path = self.resolve(query.get("path", [""])[0])
                except PermissionError:
                    return self.error(HTTPStatus.FORBIDDEN, "fuera de la carpeta de música")
                if not path.is_file():
                    return self.error(HTTPStatus.NOT_FOUND, "no existe")
                return self.json({"tags": tags.read(path), "files": [os.path.basename(f) for f in tags.song_files(path)]})
            if url.path == "/api/info":
                try:
                    path = self.resolve(query.get("path", [""])[0])
                except PermissionError:
                    return self.error(HTTPStatus.FORBIDDEN, "fuera de la carpeta de música")
                if not path.is_file():
                    return self.error(HTTPStatus.NOT_FOUND, "no existe")
                return self.json({"duration": duration(path)})
            if url.path in ("/api/lyrics", "/lyrics"):
                # The lyrics of a song with their marks (for the page), or printable.
                from . import lyrics, tags
                try:
                    path = self.resolve(query.get("path", [""])[0])
                except PermissionError:
                    return self.error(HTTPStatus.FORBIDDEN, "fuera de la carpeta de música")
                if not path.is_file():
                    return self.error(HTTPStatus.NOT_FOUND, "no existe")
                title, artist = tags.title_artist(path)
                data = lyrics.load(path)
                if url.path == "/api/lyrics":
                    return self.json({"lyrics": data, "title": title, "artist": artist,
                                      "colors": [{"id": c, "shade": lyrics.SHADES[c], "name": self.say(lyrics.NAMES[c])} for c in lyrics.COLORS]})
                if not data:
                    return self.error(HTTPStatus.NOT_FOUND, "este tema no tiene letra todavía")
                page_title = f"{title} ({artist})" if artist else title
                return self.send(HTTPStatus.OK, lyrics.page(page_title, data, self.lang).encode(), "text/html; charset=utf-8")
            if url.path == "/setlist":
                # The printable setlist, in its own tab: of a folder, or of songs from any folders
                # in the order given (?path=...&path=...). Shown only: nothing is saved.
                from . import setlist
                with_lyrics = query.get("lyrics", [""])[0] == "1"
                title = query.get("title", [""])[0].strip()
                try:
                    if "path" in query:
                        items = setlist.chosen([self.resolve(p) for p in query["path"]], root)
                    else:
                        here = self.resolve(query.get("folder", [""])[0])
                except PermissionError:
                    return self.error(HTTPStatus.FORBIDDEN, "fuera de la carpeta de música")
                except LookupError:
                    return self.error(HTTPStatus.NOT_FOUND, "alguno de esos ya no es un tema de la biblioteca")
                if "path" not in query:
                    folder, here = setlist.find(here, root)
                    if folder is None or not folder["songs"]:
                        return self.error(HTTPStatus.NOT_FOUND, "esa carpeta no tiene temas")
                    items = setlist.rows(folder, here)
                    title = title or (folder["playlist"]["title"] if folder["playlist"] else (here.name if here != root.resolve() else "Setlist"))
                return self.send(HTTPStatus.OK, setlist.page(title or "Setlist", items, with_lyrics, self.lang).encode(), "text/html; charset=utf-8")
            if url.path == "/api/peaks":
                try:
                    path = self.resolve(query.get("path", [""])[0])
                    n = max(10, min(4000, int(query.get("n", ["1000"])[0])))
                    start = float(query["from"][0]) if "from" in query else None
                    end = float(query["to"][0]) if "to" in query else None
                except PermissionError:
                    return self.error(HTTPStatus.FORBIDDEN, "fuera de la carpeta de música")
                except ValueError:
                    return self.error(HTTPStatus.BAD_REQUEST, "pedido inválido")
                if not path.is_file():
                    return self.error(HTTPStatus.NOT_FOUND, "no existe")
                try:
                    return self.json(peaks(path, n, start, end))
                except subprocess.CalledProcessError:
                    return self.error(HTTPStatus.UNPROCESSABLE_ENTITY, "no se pudo leer el audio")
            self.error(HTTPStatus.NOT_FOUND, "not found")

        do_HEAD = do_GET

        def audio(self, relative):
            try:
                path = self.resolve(relative)
            except PermissionError:
                return self.error(HTTPStatus.FORBIDDEN, "fuera de la carpeta de música")
            if not path.is_file():
                return self.error(HTTPStatus.NOT_FOUND, "no existe")
            size = path.stat().st_size
            kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if path.suffix.lower() == ".opus":
                kind = "audio/ogg"
            start, end = 0, size - 1
            match = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
            if match and (match.group(1) or match.group(2)):
                if match.group(1):
                    start = int(match.group(1))
                    # "From here on" gets a stretch, not the rest of the file: a player asks for the
                    # next one when it needs it. Sending all of it kept the connection busy while the
                    # player stopped reading, and browsers open only 6 per server: with more tracks
                    # than that (the drum kit), the rest got nothing and the practice player stalled,
                    # worse with every jump.
                    end = int(match.group(2)) if match.group(2) else start + AUDIO_CHUNK - 1
                else:
                    start = max(0, size - int(match.group(2)))
                end = min(end, size - 1)
            status = HTTPStatus.PARTIAL_CONTENT if match else HTTPStatus.OK
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if match:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if self.command == "HEAD":
                return
            with path.open("rb") as f:
                f.seek(start)
                left = end - start + 1
                try:
                    while left > 0 and (chunk := f.read(min(1 << 16, left))):
                        self.wfile.write(chunk)
                        left -= len(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # the player seeks by dropping the connection

        def do_POST(self):
            url = urlparse(self.path)
            if not self.authorized(parse_qs(url.query)):
                return self.error(HTTPStatus.FORBIDDEN, "Este pedido no viene de la interfaz de song-wizard.")
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            except ValueError:
                return self.error(HTTPStatus.BAD_REQUEST, "JSON inválido")
            if url.path == "/api/jobs":
                try:
                    title, args = self.command_for(body)
                except PermissionError:
                    return self.error(HTTPStatus.FORBIDDEN, "fuera de la carpeta de música")
                except NeedsCommand as e:
                    return self.json({"error": self.say(e.text, **e.values), "command": e.command}, HTTPStatus.BAD_REQUEST)
                except Said as e:
                    return self.error(HTTPStatus.BAD_REQUEST, e.text, **e.values)
                except (KeyError, ValueError, TypeError) as e:
                    return self.error(HTTPStatus.BAD_REQUEST, "pedido inválido: {detail}", detail=e)
                return self.json(runner.add(title, args).summary())
            if url.path == "/api/shutdown":
                # "apagar" on the page, or song-wizard ui --stop. Not from this request's thread:
                # shutdown() waits for serve_forever, which waits for this request.
                log.info("interface: closed from %s", "the page" if self.headers.get("Referer") else "the terminal")
                # Answer first: closing right away could cut the answer short.
                self.json({})
                self.wfile.flush()
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if url.path == "/api/report":
                from . import report
                path, text, link = report.build()
                return self.json({"name": path.name, "text": text, "url": link})
            if url.path == "/api/report/open":
                from . import report
                if not system.open_folder(report.REPORTS_DIR):
                    return self.error(HTTPStatus.NOT_IMPLEMENTED, "no encontré un explorador de archivos en este sistema")
                return self.json({})
            if url.path == "/api/pick-folder":
                # The system's folder dialog, on this computer's screen; waits for an answer.
                return self.json({"path": system.pick_folder()})
            if url.path == "/api/click-settings":
                try:
                    path = self.resolve(str(body["path"]))
                    bpm, first = float(body["bpm"]), float(body["first"])
                    meter = str(body.get("meter", "4/4"))
                    if not (20 <= bpm <= 400 and re.fullmatch(r"\d+/\d+", meter) and -60 < first < 3600):
                        raise ValueError
                except PermissionError:
                    return self.error(HTTPStatus.FORBIDDEN, "fuera de la carpeta de música")
                except (KeyError, ValueError, TypeError):
                    return self.error(HTTPStatus.BAD_REQUEST, "pedido inválido")
                if not path.is_file():
                    return self.error(HTTPStatus.NOT_FOUND, "no existe")
                results.save("click", [(str(path), align.describe(bpm, meter, first))])
                return self.json(align.parse(align.describe(bpm, meter, first)))
            if url.path in ("/api/lyrics", "/api/lyrics/fetch"):
                from . import lyrics
                try:
                    path = self.resolve(str(body["path"]))
                except PermissionError:
                    return self.error(HTTPStatus.FORBIDDEN, "fuera de la carpeta de música")
                except (KeyError, TypeError):
                    return self.error(HTTPStatus.BAD_REQUEST, "pedido inválido")
                if not path.is_file():
                    return self.error(HTTPStatus.NOT_FOUND, "no existe")
                if url.path == "/api/lyrics":
                    try:
                        return self.json(lyrics.save(path, body.get("lyrics")))
                    except (KeyError, ValueError, TypeError):
                        return self.error(HTTPStatus.BAD_REQUEST, "letra inválida")
                try:
                    found = lyrics.fetch(path)
                except lyrics.Unavailable as e:
                    # Reached, but it couldn't answer: the internet is fine, the database isn't.
                    log.error("lyrics: %s", e)
                    return self.error(HTTPStatus.BAD_GATEWAY, "La base de letras no está respondiendo ahora (está caída o saturada). Probá de nuevo en un rato.")
                except OSError as e:
                    log.error("lyrics: %s", e)
                    return self.error(HTTPStatus.BAD_GATEWAY, "No pude llegar a la base de letras (¿hay internet?).")
                if not found:
                    return self.error(HTTPStatus.NOT_FOUND, "No encontré la letra de este tema: podés pegarla con \"escribir o pegar\".")
                old = lyrics.load(path)
                if old:
                    found["legend"] = old.get("legend", {})
                log.info("lyrics found for %s: %s", path.name, found["source"])
                return self.json(lyrics.save(path, found))
            if url.path == "/api/set-result":
                # A key or tempo typed in the library, over what was detected.
                from . import bpm as tempo, key as keys
                try:
                    path = self.resolve(str(body["path"]))
                    what, value = body["what"], str(body["value"])
                    if what not in ("key", "bpm"):
                        raise ValueError
                except PermissionError:
                    return self.error(HTTPStatus.FORBIDDEN, "fuera de la carpeta de música")
                except (KeyError, ValueError, TypeError):
                    return self.error(HTTPStatus.BAD_REQUEST, "pedido inválido")
                if not path.is_file():
                    return self.error(HTTPStatus.NOT_FOUND, "no existe")
                note = None
                if what == "key":
                    found = keys.parse(value)
                    if not found:
                        return self.error(HTTPStatus.BAD_REQUEST, '"{value}" no es una tonalidad: probá Am, C#, Bb mayor o La menor', value=value)
                    text = keys.describe(*found, results.HAND)
                else:
                    number = tempo.parse(value)
                    if number is None:
                        return self.error(HTTPStatus.BAD_REQUEST, '"{value}" no es un tempo: un número de BPM entre 20 y 400', value=value)
                    text = f"{number:.1f} BPM  {results.HAND}"
                    if tempo.click_note(path, number):
                        note = self.say("El click de práctica de este tema sigue ajustado al tempo anterior: corregilo en practicar → ajustar el click.")
                results.save(what, [(str(path), text)])
                log.info("set %s by hand: %s -> %s", what, path.name, text)
                return self.json({"text": text, "note": note})
            if url.path == "/api/restart":
                # After an upgrade: a separate process closes this server and starts the new one on
                # the same port (from the upgraded install); the page reloads once it answers.
                with runner.lock:
                    busy = [j.title for j in runner.jobs.values() if j.status in ("queued", "running")]
                if busy:
                    return self.error(HTTPStatus.CONFLICT, "Todavía está corriendo: {jobs}.", jobs="; ".join(busy))
                log.info("interface: restarting from the page")
                restart(port)
                return self.json({})
            if url.path == "/api/reaper/setting":
                # Put back (or set again) the takes' names setting song-wizard changes in REAPER.
                from . import reaper
                if body.get("do") not in ("restore", "apply"):
                    return self.error(HTTPStatus.BAD_REQUEST, "pedido inválido")
                done = reaper.restore() if body["do"] == "restore" else reaper.apply()
                return self.json({"done": done, **reaper.setting(), "installed": reaper_installed()})
            if url.path == "/api/reaper":
                return self.reaper(body)
            if url.path == "/api/open":
                return self.open_folder(body.get("path", ""))
            match = re.fullmatch(r"/api/jobs/(\d+)/cancel", url.path)
            if match:
                job = runner.jobs.get(int(match.group(1)))
                if not job:
                    return self.error(HTTPStatus.NOT_FOUND, "no existe")
                runner.cancel(job)
                return self.json(job.summary(len(job.lines)))
            self.error(HTTPStatus.NOT_FOUND, "not found")

        def reaper(self, body):
            """Open the song's REAPER project, making it first if there's none (or "redo")."""
            from . import reaper
            try:
                path = self.resolve(str(body["path"]))
            except PermissionError:
                return self.error(HTTPStatus.FORBIDDEN, "fuera de la carpeta de música")
            except (KeyError, TypeError):
                return self.error(HTTPStatus.BAD_REQUEST, "pedido inválido")
            if not path.is_file():
                return self.error(HTTPStatus.NOT_FOUND, "no existe")
            try:
                project, created, info = reaper.make(path, redo=bool(body.get("redo")))
            except SystemExit:  # die() said why in the log: a stem without its song, say
                return self.error(HTTPStatus.BAD_REQUEST, "No pude armar el proyecto de Reaper (el detalle está en el log).")
            opened = bool(body.get("open", True)) and reaper.open_project(project)
            log.info("reaper: %s %s%s", "created" if created else "opened", project.name, " and opened" if opened else "")
            return self.json({"name": project.name, "created": created, "opened": opened, **info,
                              "setting": reaper.setting() if info["takes"] == "set" else None})

        def open_folder(self, relative):
            try:
                path = self.resolve(str(relative))
            except PermissionError:
                return self.error(HTTPStatus.FORBIDDEN, "fuera de la carpeta de música")
            if not path.is_dir():
                return self.error(HTTPStatus.NOT_FOUND, "no existe esa carpeta")
            if not system.open_folder(path):
                return self.error(HTTPStatus.NOT_IMPLEMENTED, "no encontré un explorador de archivos en este sistema")
            return self.json({"opened": str(path)})

        def command_for(self, body):
            """Page request -> (title, CLI arguments). Every path is checked to be inside the
            music folder, and nothing but these commands can be run."""
            action = body["action"]
            if action not in ("download", "key", "bpm", "separate", "transpose", "speed", "convert", "click", "rename", "tag", "align", "delete", "archives-delete", "archives-move", "trim", "upgrade"):
                raise Said("acción desconocida: {action}", action=action)
            paths = [str(self.resolve(p)) for p in body.get("paths", [])]
            if action == "delete":
                songs = [str(self.resolve(p)) for p in body.get("songs", [])]
                files = [str(self.resolve(p)) for p in body.get("files", [])]
                if not songs and not files:
                    raise Said("no hay nada elegido")
                names = ", ".join(os.path.basename(p) for p in [*songs, *files])[:120]
                return self.say("Borrar: {names}", names=names), ["delete", "--yes", *songs, *[a for f in files for a in ("--file", f)]]
            label = ", ".join(os.path.basename(p) or self.say("carpeta principal") for p in paths)[:120]
            if action == "download":
                url = str(body["url"]).strip()
                if not re.match(r"https?://", url):
                    raise Said("la URL tiene que empezar con http:// o https://")
                title = self.say("Buscar temas nuevos: {title}", title=body["title"]) if body.get("title") else self.say("Bajar {url}", url=url)
                to = folder_from(body.get("to"))
                return title, ["download", *(["--wav"] if body.get("wav") else []), *(["--to", to] if to else []), url]
            if action == "archives-move":
                to = folder_from(body.get("to"))
                if not to:
                    raise Said("falta la carpeta")
                which = str(body["id"])
                if not re.fullmatch(r"[A-Za-z0-9_-]+", which):
                    raise Said("playlist inválida")
                return self.say("Mover {title} a {to}", title=body.get("title") or which, to=to), ["archives", "--move", which, to]
            if action == "upgrade":
                return self.say("Actualizar song-wizard"), ["upgrade"]
            if not paths and action not in ("click", "archives-delete"):
                raise Said("no hay archivos elegidos")
            force = ["--force"] if body.get("force") else []
            if action == "key":
                return self.say("Tonalidad: {label}", label=label), ["key", *force, *paths]
            if action == "bpm":
                return self.say("Tempo: {label}", label=label), ["bpm", *force, *paths]
            if action == "separate":
                stems = [s for s in body["stems"] if s in ("vocals", "drums", "bass", "guitar", "piano", "drumkit", "all")]
                if not stems:
                    raise Said("elegí al menos un instrumento")
                args = ["separate", *[a for s in stems for a in ("--stem", s)]]
                return self.say("Separar ({stems}): {label}", stems=", ".join(stems), label=label), [*args, *(["--cpu"] if body.get("cpu") else []), *paths]
            if action == "transpose":
                n = float(body["semitones"])
                return self.say("Transponer {n}: {label}", n=f"{n:+g}", label=label), ["transpose", f"{n:+g}", *paths]
            if action == "speed":
                percent, n = float(body["percent"]), float(body.get("semitones") or 0)
                args = ["speed", f"{percent:g}", *(["--semitones", f"{n:+g}"] if n else []), *paths]
                return self.say("Velocidad {percent}%{pitch}: {label}", percent=f"{percent:g}", pitch=self.say(" y tono {n}", n=f"{n:+g}") if n else "", label=label), args
            if action == "align":
                return self.say("Tempo y primer golpe: {label}", label=label), ["align", *paths]
            if action == "rename":
                if len(paths) != 1:
                    raise Said("se renombra de a un tema")
                name = str(body["name"]).strip()
                return self.say("Renombrar {label} → {name}", label=label, name=name), ["rename", paths[0], name]
            if action == "tag":
                if len(paths) != 1:
                    raise Said("los datos se cambian de a un tema")
                changes = {str(k): str(v) for k, v in (body.get("set") or {}).items()}
                gone = [str(k) for k in body.get("unset") or []]
                if any(not k.strip() or "=" in k for k in [*changes, *gone]):
                    raise Said("un nombre de dato no puede estar vacío ni tener =")
                if not changes and not gone:
                    raise Said("no hay cambios")
                args = ["tag", paths[0], *[a for k, v in changes.items() for a in ("--set", f"{k}={v}")],
                        *[a for k in gone for a in ("--unset", k)], *(["--only"] if body.get("only") else [])]
                return self.say("Datos: {label}", label=label), args
            if action == "trim":
                if len(paths) != 1:
                    raise Said("se recorta de a un tema")
                start, end = float(body.get("start") or 0), body.get("end")
                pad_start, pad_end = float(body.get("padStart") or 0), float(body.get("padEnd") or 0)
                args = ["trim", paths[0], "--yes", "--start", f"{start:.4f}",
                        *(["--end", f"{float(end):.4f}"] if end not in (None, "") else []),
                        *(["--pad-start", f"{pad_start:g}"] if pad_start else []),
                        *(["--pad-end", f"{pad_end:g}"] if pad_end else [])]
                return self.say("Recortar: {label}", label=label), args
            if action == "convert":
                fmt = body.get("format", "mp3")
                if fmt not in ("mp3", "m4a"):
                    raise Said("formato inválido")
                return self.say("Convertir a {fmt}: {label}", fmt=fmt, label=label), ["convert", "--format", fmt, *paths]
            if action == "click":
                bpm = float(body["bpm"])
                meter = str(body.get("meter", "4/4"))
                if body.get("for"):  # one song picked: named after it and saved next to it
                    args = ["click", f"{bpm:g}", "--meter", meter, "--for", str(self.resolve(body["for"]))]
                else:
                    args = ["click", f"{bpm:g}", "--meter", meter, "-o", str(self.resolve(body.get("folder", "")))]
                if body.get("like"):
                    args += ["--like", str(self.resolve(body["like"]))]
                elif body.get("bars"):
                    args += ["--bars", str(int(body["bars"]))]
                elif body.get("duration"):
                    args += ["--duration", str(body["duration"])]
                if int(body.get("subdivide", 1)) > 1:
                    args += ["--subdivide", str(int(body["subdivide"]))]
                return self.say("Click {bpm} BPM {meter}", bpm=f"{bpm:g}", meter=meter), args
            if action == "archives-delete":
                which = [str(int(n)) for n in body["numbers"]] if body.get("numbers") != "all" else ["all"]
                return self.say("Olvidar registros"), ["archives", "--delete", *which, "--yes"]
            raise Said("acción desconocida: {action}", action=action)

    return Handler


class Server(ThreadingHTTPServer):
    def server_bind(self):
        # HTTPServer looks up the address's full host name here (reverse DNS), which on a Mac can
        # hang for half a minute or more; it's only used in a header nobody needs. Skip it.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]

    def handle_error(self, request, client_address):
        log.logger.exception("interface: error answering a request")
        super().handle_error(request, client_address)


def page_path(root, file):
    """The library's name for the song a file belongs to (the song itself, a stem, a version...)."""
    from .listing import folder_path

    target = Path(system.local_path(str(file))).resolve()
    for folder in library(root):
        if folder_path(root, folder).resolve() != target.parent:
            continue
        for song in folder["songs"]:
            if target.name in [song["name"], *(f["name"] for f in song["files"])]:
                return song["path"]
    return None


# The interface running on this computer (port, token, process), so "song-wizard ui" from any
# terminal finds it, and "--stop" closes it. Only readable by you: it holds the page's token.
STATE_ENV = "SONG_WIZARD_UI_STATE"
NONCE_ENV = "SONG_WIZARD_UI_NONCE"


def state_file():
    return Path(os.environ.get(STATE_ENV) or paths.DATA_DIR / "ui.json")


def ask(port, token, method, path, timeout=3):
    """A request to an interface on this computer: (status, decoded JSON), or None if it's not there."""
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
        conn.request(method, path, body=b"{}" if method == "POST" else None,
                     headers={"X-Token": token, "Host": f"127.0.0.1:{port}", "Content-Type": "application/json"})
        response = conn.getresponse()
        data = json.loads(response.read() or b"null")
        conn.close()
        return response.status, data
    except (OSError, ValueError, http.client.HTTPException):
        return None


def running():
    """The interface already running: {"pid", "port", "token", "url", "root"}, or None."""
    try:
        info = json.loads(state_file().read_text())
        answer = ask(info["port"], info["token"], "GET", "/api/jobs")
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return info if answer and answer[0] == HTTPStatus.OK else None


def write_state(info):
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(info, f)


def clear_state(pid):
    try:
        if json.loads(state_file().read_text()).get("pid") == pid:
            state_file().unlink()
    except (OSError, ValueError):
        pass


def server_output():
    return log.LOG_DIR / "interface-server.txt"


def start_background(port):
    """Start the server as its own process, detached from this terminal; wait until it answers."""
    out = server_output()
    out.parent.mkdir(parents=True, exist_ok=True)
    # The new server is recognized by a word only it knows, not by its process number: on a Mac
    # the Python program can hand over to another process, with another number.
    nonce = secrets.token_hex(8)
    with open(out, "w") as f:
        process = subprocess.Popen([sys.executable, "-m", "song_wizard", "ui", "--foreground", "--no-browser",
                                    "--port", str(port)], stdin=subprocess.DEVNULL, stdout=f, stderr=f,
                                   start_new_session=True, cwd=str(Path.home()),
                                   env={**os.environ, NONCE_ENV: nonce})
    deadline = time.time() + 30
    while time.time() < deadline:
        info = running()
        if info and info.get("nonce") == nonce:
            return info
        if process.poll() is not None:
            break
        time.sleep(0.2)
    process.kill()
    try:
        printed = out.read_text(errors="replace").strip()[-2000:]
    except OSError:
        printed = ""
    sys.exit(f"The interface didn't start (it's kept in {out}):\n{printed or '(it printed nothing)'}")


def run(port=PORT, open_page=True, practice=None, foreground=False):
    root = music_dir()
    root.mkdir(parents=True, exist_ok=True)
    practice_path = page_path(root, practice) if practice else None
    if practice and practice_path is None:
        sys.exit(f"{practice}: not a song in the library (see song-wizard list).")
    if foreground:
        return serve(root, port, open_page, practice_path)
    info = running()
    if info and info.get("root") != str(root):
        sys.exit(f"The interface is running with another music folder ({info.get('root')}): "
                 "close it with song-wizard ui --stop and open it again.")
    if info:
        print("The interface was already running.", flush=True)
    else:
        info = start_background(port)
    url = with_practice(info["url"], practice_path)
    print(f"song-wizard interface: {url}", flush=True)
    print(f"Music folder: {root}", flush=True)
    print("It keeps running in the background; song-wizard ui --stop closes it (or \"apagar\" on the page).",
          flush=True)
    if open_page:
        system.open_url(url)


def stop(yes=False):
    """Close the interface running in the background. False if it was left running."""
    info = running()
    if not info:
        try:
            state_file().unlink()
        except OSError:
            pass
        print("The interface isn't running.")
        return True
    answer = ask(info["port"], info["token"], "GET", "/api/jobs")
    busy = [j["title"] for j in (answer[1] if answer else []) if j["status"] in ("queued", "running")]
    if busy and not yes:
        print("Still working on: " + "; ".join(busy))
        if not sys.stdin.isatty():
            sys.exit("Not closing it in the middle of that: add --yes to cancel and close.")
        if input("Cancel and close? [y/N] ").strip().lower() not in ("y", "yes", "s", "si", "sí"):
            print("Left running.")
            return False
    ask(info["port"], info["token"], "POST", "/api/shutdown")
    deadline = time.time() + 10
    while time.time() < deadline and running():
        time.sleep(0.2)
    if running():
        try:
            os.kill(info["pid"], signal.SIGTERM)
        except OSError:
            pass
    print("Interface closed.")
    return True


def with_practice(url, practice_path):
    """The interface's link, opening the practice player on a song if given. (A server started
    by an older version has the token in its link already.)"""
    if not practice_path:
        return url
    return url + ("&" if "?" in url else "?") + f"practice={quote(practice_path)}"


def serve(root, port, open_page, practice_path):
    """The server itself, in this process until Ctrl+C, "--stop" or "apagar" on the page."""
    token = secrets.token_urlsafe(16)
    runner = Runner()
    server = None
    for candidate in [port, *range(port + 1, port + 20), 0]:
        try:
            server = Server(("127.0.0.1", candidate), make_handler(token, root, runner, candidate))
            break
        except OSError:
            continue
    if server is None:
        sys.exit("Could not open a local port for the interface.")
    actual = server.server_address[1]
    if actual != candidate:  # port 0: the system picked one, the handler must know which
        server.RequestHandlerClass = make_handler(token, root, runner, actual)
    url = f"http://127.0.0.1:{actual}/"
    write_state({"pid": os.getpid(), "port": actual, "token": token, "url": url, "root": str(root),
                 "nonce": os.environ.get(NONCE_ENV)})
    page = with_practice(url, practice_path)
    # flush: when the output isn't a terminal it's buffered, and the link must show up right away.
    print(f"song-wizard interface: {page}", flush=True)
    print(f"Music folder: {root}", flush=True)
    print("Leave this terminal open while you use it; Ctrl+C closes it.", flush=True)
    if open_page:
        system.open_url(page)

    def interrupt(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print("\nClosing.", flush=True)
        clear_state(os.getpid())
        for job in list(runner.jobs.values()):
            if job.process and job.process.poll() is None:
                job.process.terminate()
        server.server_close()
