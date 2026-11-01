"""Opening links and folders with whatever this computer uses: on WSL, the Windows browser and
Explorer; on a Mac, the default browser and the Finder; on Linux, xdg-open."""

import base64
import datetime
import json
import os
import re
import shutil
import urllib.parse
from pathlib import Path
import subprocess
import sys
import webbrowser

from .paths import is_wsl


def local_path(text):
    """A folder as typed or picked: on WSL a Windows path ("G:\\Mi unidad\\Ensayos") becomes its
    Linux one; "~" is the home folder."""
    text = text.strip().strip('"')
    if is_wsl() and re.match(r"^[A-Za-z]:[\\/]", text) and shutil.which("wslpath"):
        out = subprocess.run(["wslpath", "-u", text], capture_output=True, text=True).stdout.strip()
        if out:
            return out
    return os.path.expanduser(text)


_shown = {}


def shown_path(path):
    """A path as the user sees it: on WSL, a folder on a Windows drive in Windows form."""
    path = str(path)
    if is_wsl() and re.match(r"^/mnt/[a-z]/", path) and shutil.which("wslpath"):
        if path not in _shown:
            _shown[path] = windows_path(path) or path
        return _shown[path]
    return path


def pick_folder():
    """Ask with the system's own folder dialog; the folder's path, or None if cancelled."""
    if is_wsl() and shutil.which("powershell.exe"):
        # A topmost owner window: without it the dialog can open behind the browser.
        script = ("Add-Type -AssemblyName System.Windows.Forms; "
                  "$owner = New-Object System.Windows.Forms.Form -Property @{TopMost = $true}; "
                  "$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
                  "$d.Description = 'Carpeta para song-wizard'; $d.ShowNewFolderButton = $true; "
                  "if ($d.ShowDialog($owner) -eq 'OK') { [Console]::OutputEncoding = [Text.Encoding]::UTF8; $d.SelectedPath }")
        out = subprocess.run(["powershell.exe", "-NoProfile", "-STA", "-Command", script], capture_output=True,
                             cwd="/mnt/c" if os.path.isdir("/mnt/c") else None).stdout.decode("utf-8", "replace").strip()
        return local_path(out) if out else None
    if sys.platform == "darwin":
        out = subprocess.run(["osascript", "-e", 'POSIX path of (choose folder with prompt "Carpeta para song-wizard")'],
                             capture_output=True, text=True).stdout.strip()
        return out.rstrip("/") or None
    if shutil.which("zenity"):
        out = subprocess.run(["zenity", "--file-selection", "--directory"], capture_output=True, text=True).stdout.strip()
        return out or None
    return None


def windows_path(path):
    return subprocess.run(["wslpath", "-w", str(path)], capture_output=True, text=True).stdout.strip()


def open_url(url):
    if is_wsl() and shutil.which("cmd.exe"):
        # The Windows browser (it reaches WSL's localhost). cmd cuts a command at "&" unless it's
        # escaped as "^&"; the other characters it treats specially are percent-encoded in links.
        launch(["cmd.exe", "/c", "start", "", url.replace("&", "^&")])
    else:
        webbrowser.open(url)


def folder_command(path):
    """How to open a folder in this system's file manager, or None if there's none."""
    if is_wsl() and shutil.which("explorer.exe") and shutil.which("wslpath"):
        return ["explorer.exe", windows_path(path)]
    if sys.platform == "darwin":
        return ["open", str(path)]
    if shutil.which("xdg-open"):
        return ["xdg-open", str(path)]
    return None


def open_folder(path):
    """Returns whether a file manager was found to open it."""
    command = folder_command(path)
    if command:
        launch(command)
    return bool(command)


def file_manager_name():
    if is_wsl():
        return "Explorador de archivos"
    return "Finder" if sys.platform == "darwin" else "explorador de archivos"


class TrashError(Exception):
    pass


def trash(paths):
    """Send files to the system's trash: Windows' Recycle Bin for files on a Windows drive
    under WSL, the Finder's Trash on a Mac, the desktop's trash on Linux. Raises TrashError
    (naming what's left) if any file couldn't go."""
    paths = [os.path.abspath(p) for p in paths]
    windows = [p for p in paths if is_wsl() and re.match(r"^/mnt/[a-z]/", p)]
    if windows:
        windows_trash(windows)
    others = [p for p in paths if p not in windows]
    if others and sys.platform == "darwin":
        script = 'tell application "Finder" to delete {' + ", ".join(
            f'POSIX file "{p.replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))}"' for p in others) + "}"
        subprocess.run(["osascript", "-e", script], capture_output=True)
    elif others and shutil.which("gio"):
        subprocess.run(["gio", "trash", "--", *others], capture_output=True)
    elif others:
        for p in others:
            desktop_trash(p)
    left = [p for p in paths if os.path.lexists(p)]
    if left:
        raise TrashError("could not move to the trash: " + ", ".join(left))


def windows_trash(paths):
    # The paths go base64-encoded: no quoting trouble with any character in a song's name.
    for start in range(0, len(paths), 40):
        listed = json.dumps([windows_path(p) for p in paths[start:start + 40]])
        encoded = base64.b64encode(listed.encode()).decode()
        script = ("Add-Type -AssemblyName Microsoft.VisualBasic; "
                  f"$paths = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded}')) | ConvertFrom-Json; "
                  "foreach ($p in @($paths)) { [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($p, 'OnlyErrorDialogs', 'SendToRecycleBin') }")
        subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, cwd="/mnt/c" if os.path.isdir("/mnt/c") else None)


def desktop_trash(path):
    """The freedesktop.org trash in the home folder, for Linux without gio."""
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "Trash"
    (base / "files").mkdir(parents=True, exist_ok=True)
    (base / "info").mkdir(parents=True, exist_ok=True)
    name, n = os.path.basename(path), 1
    while (base / "files" / name).exists() or (base / "info" / f"{name}.trashinfo").exists():
        n += 1
        stem, ext = os.path.splitext(os.path.basename(path))
        name = f"{stem}.{n}{ext}"
    (base / "info" / f"{name}.trashinfo").write_text(
        f"[Trash Info]\nPath={urllib.parse.quote(path)}\nDeletionDate={datetime.datetime.now():%Y-%m-%dT%H:%M:%S}\n")
    shutil.move(path, base / "files" / name)


def launch(command):
    # From a Windows drive on WSL: from a Linux folder, Windows programs warn about UNC paths.
    subprocess.Popen(command, cwd="/mnt/c" if is_wsl() and os.path.isdir("/mnt/c") else None,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
