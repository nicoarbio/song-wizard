"""Local web interface: a page in the browser that runs the same commands as the terminal.

It only listens on 127.0.0.1, and every request needs a random token that is in the URL the
browser is opened with: without it, any web page open in the browser could send requests here.
Each action runs the real CLI as a subprocess, one at a time, and the page polls its output.
"""

import collections
import itertools
import json
import mimetypes
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import parse_qs, urlparse

from . import archives, log, system
from .audio import AUDIO_EXTS, GENERATED, base_of
from .paths import music_dir

PORT = 8765
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
MAIN_FORMATS = [".opus", ".webm", ".m4a", ".flac", ".wav", ".aiff", ".aif", ".ogg", ".mp3", ".aac", ".mp4", ".mkv"]


def library(root):
    """The music folder and the folders directly in it, with their songs and, for each song,
    the files generated from it (stems, transpositions, conversions)."""
    if not root.exists():
        return []
    folders = []
    known = archives.playlists()
    subfolders = sorted((p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")),
                        key=lambda p: p.name.lower())
    for folder in [root, *subfolders]:
        try:
            names = sorted(n for n in os.listdir(folder)
                           if os.path.splitext(n)[1].lower() in AUDIO_EXTS and (folder / n).is_file())
        except OSError:
            continue
        keys, bpms = read_results(folder, "key"), read_results(folder, "bpm")
        groups = collections.defaultdict(list)
        for n in names:
            groups[base_of(n)].append(n)
        songs, extras = [], []
        for base, members in sorted(groups.items(), key=lambda g: g[0].lower()):
            originals = [n for n in members
                         if os.path.splitext(n)[0] == base and not GENERATED.search(base)]
            if not originals:  # click tracks: generated, but not from a song
                extras += [file_entry(root, folder / n, keys, bpms) for n in members]
                continue
            main = min(originals, key=lambda n: MAIN_FORMATS.index(os.path.splitext(n)[1].lower())
                       if os.path.splitext(n)[1].lower() in MAIN_FORMATS else len(MAIN_FORMATS))
            songs.append({"name": main, "path": rel(root, folder / main),
                          "key": keys.get(main), "bpm": bpms.get(main),
                          "files": [file_entry(root, folder / n, keys, bpms) for n in members if n != main]})
        if songs or extras or folder != root:
            playlist = archives.playlist_for(folder, known) if folder != root else None
            folders.append({"name": folder.name if folder != root else "(carpeta principal)",
                            "path": rel(root, folder), "songs": songs, "extras": extras,
                            "playlist": {k: playlist[k] for k in ("title", "url", "wav")} if playlist else None})
    return folders


def file_entry(root, path, keys, bpms):
    """A generated file. Stems can be analyzed too ("bpm" on the drums alone is often more
    reliable), so they carry their own results."""
    return {"name": path.name, "path": rel(root, path), "size": path.stat().st_size,
            "key": keys.get(path.name), "bpm": bpms.get(path.name)}


def rel(root, path):
    return path.relative_to(root).as_posix() if path != root else ""


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

        def error(self, status, message):
            self.json({"error": message}, status)

        def authorized(self, query):
            # Host check against DNS rebinding; the token against any other page in the browser.
            if self.headers.get("Host") not in allowed_hosts:
                return False
            given = self.headers.get("X-Token") or query.get("t", [""])[0]
            return secrets.compare_digest(given, token)

        def resolve(self, relative):
            """A path from the page, which must stay inside the music folder."""
            path = (root / relative).resolve()
            if path != root.resolve() and root.resolve() not in path.parents:
                raise PermissionError(relative)
            return path

        def do_GET(self):
            url = urlparse(self.path)
            query = parse_qs(url.query)
            if not self.authorized(query):
                return self.error(HTTPStatus.FORBIDDEN, "Abrí la interfaz con el link que muestra la terminal.")
            if url.path == "/":
                return self.send(HTTPStatus.OK, page.encode(), "text/html; charset=utf-8")
            if url.path == "/api/library":
                return self.json({"root": str(root), "folders": library(root), "fileManager": system.file_manager_name()})
            if url.path == "/api/archives":
                meta = {p["id"]: p for p in archives.playlists()}
                return self.json([{"number": i, "title": t, "songs": n, "changed": f"{c:%Y-%m-%d %H:%M}",
                                   "url": meta.get(a, {}).get("url"), "wav": meta.get(a, {}).get("wav", False)}
                                  for i, (a, t, n, c) in enumerate(archives.entries(), 1)])
            if url.path == "/api/jobs":
                since = int(query.get("since", ["0"])[0] or 0)
                with runner.lock:
                    jobs = [j.summary(since if j.id == int(query.get("job", ["0"])[0] or 0) else len(j.lines))
                            for j in runner.jobs.values()]
                return self.json(jobs)
            if url.path == "/api/audio":
                return self.audio(query.get("path", [""])[0])
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
                    end = int(match.group(2)) if match.group(2) else size - 1
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
                return self.error(HTTPStatus.FORBIDDEN, "token inválido")
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            except ValueError:
                return self.error(HTTPStatus.BAD_REQUEST, "JSON inválido")
            if url.path == "/api/jobs":
                try:
                    title, args = self.command_for(body)
                except PermissionError:
                    return self.error(HTTPStatus.FORBIDDEN, "fuera de la carpeta de música")
                except (KeyError, ValueError, TypeError) as e:
                    return self.error(HTTPStatus.BAD_REQUEST, f"pedido inválido: {e}")
                return self.json(runner.add(title, args).summary())
            if url.path == "/api/report":
                from . import report
                path, text, link = report.build()
                return self.json({"name": path.name, "text": text, "url": link})
            if url.path == "/api/report/open":
                from . import report
                if not system.open_folder(report.REPORTS_DIR):
                    return self.error(HTTPStatus.NOT_IMPLEMENTED, "no encontré un explorador de archivos en este sistema")
                return self.json({})
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

        def open_folder(self, relative):
            try:
                path = self.resolve(str(relative))
            except PermissionError:
                return self.error(HTTPStatus.FORBIDDEN, "fuera de la carpeta de música")
            if not path.is_dir():
                return self.error(HTTPStatus.NOT_FOUND, "no existe esa carpeta")
            if not system.open_folder(path):
                return self.error(HTTPStatus.NOT_IMPLEMENTED, "no encontré un explorador de archivos en este sistema")
            return self.json({"opened": rel(root, path)})

        def command_for(self, body):
            """Page request -> (title, CLI arguments). Every path is checked to be inside the
            music folder, and nothing but these commands can be run."""
            action = body["action"]
            if action not in ("download", "key", "bpm", "separate", "transpose", "speed", "convert", "click", "rename", "archives-delete"):
                raise ValueError(f"acción desconocida: {action}")
            paths = [str(self.resolve(p)) for p in body.get("paths", [])]
            label = ", ".join(os.path.basename(p) or "carpeta principal" for p in paths)[:120]
            if action == "download":
                url = str(body["url"]).strip()
                if not re.match(r"https?://", url):
                    raise ValueError("la URL tiene que empezar con http:// o https://")
                title = f"Buscar temas nuevos: {body['title']}" if body.get("title") else f"Bajar {url}"
                return title, ["download", *(["--wav"] if body.get("wav") else []), url]
            if not paths and action not in ("click", "archives-delete"):
                raise ValueError("no hay archivos elegidos")
            if action == "key":
                return f"Tonalidad: {label}", ["key", *paths]
            if action == "bpm":
                return f"Tempo: {label}", ["bpm", *paths]
            if action == "separate":
                stems = [s for s in body["stems"] if s in ("vocals", "drums", "bass", "guitar", "all")]
                if not stems:
                    raise ValueError("elegí al menos un instrumento")
                args = ["separate", *[a for s in stems for a in ("--stem", s)]]
                return f"Separar ({', '.join(stems)}): {label}", [*args, *(["--cpu"] if body.get("cpu") else []), *paths]
            if action == "transpose":
                n = float(body["semitones"])
                return f"Transponer {n:+g}: {label}", ["transpose", f"{n:+g}", *paths]
            if action == "speed":
                percent, n = float(body["percent"]), float(body.get("semitones") or 0)
                args = ["speed", f"{percent:g}", *(["--semitones", f"{n:+g}"] if n else []), *paths]
                return f"Velocidad {percent:g}%" + (f" y tono {n:+g}" if n else "") + f": {label}", args
            if action == "rename":
                if len(paths) != 1:
                    raise ValueError("se renombra de a un tema")
                name = str(body["name"]).strip()
                return f"Renombrar {label} → {name}", ["rename", paths[0], name]
            if action == "convert":
                fmt = body.get("format", "mp3")
                if fmt not in ("mp3", "m4a"):
                    raise ValueError("formato inválido")
                return f"Convertir a {fmt}: {label}", ["convert", "--format", fmt, *paths]
            if action == "click":
                bpm = float(body["bpm"])
                meter = str(body.get("meter", "4/4"))
                folder = self.resolve(body.get("folder", ""))
                args = ["click", f"{bpm:g}", "--meter", meter, "-o", str(folder)]
                if body.get("like"):
                    args += ["--like", str(self.resolve(body["like"]))]
                elif body.get("bars"):
                    args += ["--bars", str(int(body["bars"]))]
                elif body.get("duration"):
                    args += ["--duration", str(body["duration"])]
                if int(body.get("subdivide", 1)) > 1:
                    args += ["--subdivide", str(int(body["subdivide"]))]
                return f"Click {bpm:g} BPM {meter}", args
            if action == "archives-delete":
                which = [str(int(n)) for n in body["numbers"]] if body.get("numbers") != "all" else ["all"]
                return "Olvidar registros", ["archives", "--delete", *which, "--yes"]
            raise ValueError(f"acción desconocida: {action}")

    return Handler


class Server(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        log.logger.exception("interface: error answering a request")
        super().handle_error(request, client_address)


def run(port=PORT, open_page=True):
    root = music_dir()
    root.mkdir(parents=True, exist_ok=True)
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
    url = f"http://127.0.0.1:{actual}/?t={token}"
    # flush: when the output isn't a terminal it's buffered, and the link must show up right away.
    print(f"song-wizard interface: {url}", flush=True)
    print(f"Music folder: {root}", flush=True)
    print("Leave this terminal open while you use it; Ctrl+C closes it.", flush=True)
    if open_page:
        system.open_url(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nClosing.")
        for job in list(runner.jobs.values()):
            if job.process and job.process.poll() is None:
                job.process.terminate()
