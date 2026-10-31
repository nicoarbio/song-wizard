"""A log to troubleshoot problems: each command with its options, how it ended and how long it
took, and the full error when something breaks (including what ffmpeg or rubberband said).
Only what song-wizard does, never the audio. It rotates: at most ~2 MB on disk."""

import logging
import logging.handlers
import os
import platform
import shlex
import subprocess
import sys
import time
import traceback

from . import __version__
from .paths import DATA_DIR

LOG_DIR = DATA_DIR / "logs"
# Set in the environment to run without logging (the setup check inside a report).
OFF = "SONG_WIZARD_NO_LOG"
MAX_BYTES = 1_000_000

logger = logging.getLogger("song_wizard")
logger.addHandler(logging.NullHandler())  # nothing on screen when the log isn't started
logger.propagate = False


def path():
    return LOG_DIR / "song-wizard.log"


def start(argv):
    """Log to the file from now on. A log that can't be written never stops a command."""
    if os.environ.get(OFF):
        return
    for handler in list(logger.handlers):
        if isinstance(handler, logging.FileHandler):
            logger.removeHandler(handler)
            handler.close()
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(path(), maxBytes=MAX_BYTES, backupCount=1, encoding="utf-8")
    except OSError:
        return
    handler.setFormatter(logging.Formatter("%(asctime)s [%(process)d] %(levelname)s %(message)s",
                                           "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.info("song-wizard %s (Python %s, %s): %s", __version__, platform.python_version(),
                platform.platform(terse=True), shlex.join(argv) or "(no command)")


def info(message, *args):
    logger.info(message, *args)


def error(message, *args):
    logger.error(message, *args)


def finished(code, started):
    took = f"{time.monotonic() - started:.1f} s"
    if code in (None, 0):
        logger.info("done in %s", took)
    elif isinstance(code, int):
        logger.error("ended with exit code %s after %s", code, took)
    else:  # sys.exit("message")
        logger.error("stopped after %s: %s", took, code)


def crashed(started):
    error_type, value, _ = sys.exc_info()
    details = traceback.format_exc().rstrip()
    if isinstance(value, subprocess.CalledProcessError):
        output = value.stderr or value.output or b""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        details += f"\ncommand: {shlex.join(map(str, value.cmd))}\nits output:\n{output.strip() or '(none)'}"
    logger.error("crashed after %.1f s:\n%s", time.monotonic() - started, details)
