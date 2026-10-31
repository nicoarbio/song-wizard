"""A report to ask for help: the system, the setup checks and the end of the log in one text
file, with the home folder hidden. It opens a GitHub issue already filled in; the file can also
go by WhatsApp or mail to whoever helps you with song-wizard."""

import datetime
import os
import platform
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

from . import __version__, log, system
from .paths import DATA_DIR, is_wsl

REPORTS_DIR = DATA_DIR / "reports"
ISSUES = "https://github.com/nicoarbio/song-wizard/issues/new"
LOG_LINES = 400
# Long links get cut somewhere between here and the browser (the Windows launcher, some
# browsers); the whole report goes in the attached file anyway.
URL_LIMIT = 2000


def private(text):
    """Hide the home folder: "~" instead of /home/<user>, /Users/<user> or C:\\Users\\<user>."""
    text = text.replace(str(Path.home()), "~")
    text = re.sub(r"/mnt/([a-z])/Users/[^/\s]+", r"/mnt/\1/Users/~", text)
    return re.sub(r"\b([A-Za-z]):\\Users\\[^\\\s]+", lambda m: f"{m.group(1)}:\\Users\\~", text)


def setup_output():
    """What "song-wizard setup" says, in a subprocess (it imports PyTorch, which can crash)."""
    try:
        out = subprocess.run([sys.executable, "-m", "song_wizard", "setup"], capture_output=True,
                             text=True, timeout=180, env=dict(os.environ, **{log.OFF: "1"}))
        text = out.stdout + out.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        text = f"(could not run setup: {e})"
    return re.sub(r"\x1b\[[0-9;]*m", "", text).strip()


def log_tail(lines=LOG_LINES, skip_pid=None):
    """The end of the log, without the lines of process skip_pid ("song-wizard report" itself)."""
    found = []
    for path in [log.path().with_name(log.path().name + ".1"), log.path()]:
        try:
            found += path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            pass
    skip = f" [{skip_pid}] "
    return [line for line in found if skip_pid is None or skip not in line][-lines:]


def system_summary():
    return (f"song-wizard {__version__} · Python {platform.python_version()} · "
            f"{platform.platform(terse=True)} {platform.machine()}" + (" (WSL)" if is_wsl() else ""))


def build(skip_own=False):
    """Write the report. Returns (its path, its text, the GitHub link). skip_own leaves out this
    process's lines: the report command's, but not the interface's (its errors matter)."""
    now = datetime.datetime.now()
    tail = log_tail(skip_pid=os.getpid() if skip_own else None)
    text = private("\n".join([
        f"song-wizard report, {now:%Y-%m-%d %H:%M}",
        "", "== System", system_summary(),
        "", "== Setup", setup_output(),
        "", f"== Log (last {len(tail)} lines)", *(tail or ["(empty)"]),
    ]) + "\n")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"song-wizard-report-{now:%Y%m%d-%H%M%S}.txt"
    path.write_text(text, encoding="utf-8")
    log.info("report written: %s", path)
    return path, text, issue_url(path.name, private("\n".join(tail)).splitlines())


def issue_url(file_name, tail):
    """A new issue with the system and the last log lines; as many lines as fit in a link."""
    def url(lines):
        body = "\n".join([
            "**Qué pasó** (qué hiciste, qué esperabas y qué salió):", "", "",
            "**Sistema**", private(system_summary()), "",
            "**Últimas líneas del log**", "```", *lines, "```", "",
            f"Arrastrá acá el archivo `{file_name}`: tiene el detalle completo.",
        ])
        return ISSUES + "?" + urllib.parse.urlencode({"title": "Problema: ", "body": body})

    lines = tail[-40:]
    while lines and len(url(lines)) > URL_LIMIT:
        lines = lines[1:]
    # A single huge line (a traceback with long paths) can still be too long: cut it.
    link = url(lines)
    while len(link) > URL_LIMIT and lines:
        lines = [lines[0][: len(lines[0]) // 2] + " …"]
        link = url(lines)
    return link


def run(yes=False):
    print("Putting the report together (checking the setup takes a few seconds)...", flush=True)
    path, text, url = build(skip_own=True)
    print(f"\nReport saved to {path}")
    print("It has this computer's setup and the last lines of song-wizard's log. Your home folder")
    print("shows as ~, but song and folder names are kept: have a look before sending it.\n")
    print("To report the problem on GitHub, open this link and attach the file to it:")
    print(f"  {url}\n")
    print("No GitHub account? Send the file by WhatsApp or mail to whoever helps you with song-wizard.")
    if not yes and not sys.stdin.isatty():
        return
    if not yes and input("\nOpen the folder with the file and the GitHub form now? [Y/n] ").strip().lower() in ("n", "no"):
        return
    system.open_folder(REPORTS_DIR)
    system.open_url(url)
