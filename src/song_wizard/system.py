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
    match = re.match(r"^([A-Za-z]):[\\/]?(.*)$", text) if is_wsl() else None
    if match:
        if shutil.which("wslpath"):
            out = subprocess.run(["wslpath", "-u", text], capture_output=True, text=True).stdout.strip()
            if out.startswith("/"):
                return out
        # wslpath leaves a drive WSL hasn't mounted as it is: point where it would be mounted, so
        # the error can say what's missing.
        return f"/mnt/{match[1].lower()}/" + match[2].replace("\\", "/").strip("/")
    return os.path.expanduser(text)


def unmounted_drive(path):
    """On WSL, the letter of the Windows drive a /mnt/<x>/... path is on, if WSL hasn't mounted
    it (drives that appear after WSL starts, like Google Drive's, aren't mounted on their own)."""
    match = re.match(r"^/mnt/([a-z])(/|$)", str(path)) if is_wsl() else None
    return match[1].upper() if match and not os.path.ismount(f"/mnt/{match[1]}") else None


def mount_options():
    """drvfs options: metadata lets chmod work there (writing a song's data copies its file's
    permissions), and the files are the user's, with normal permissions, like C:'s."""
    uid, gid = (os.getuid(), os.getgid()) if hasattr(os, "getuid") else (1000, 1000)
    return f"metadata,uid={uid},gid={gid},umask=22,fmask=11"


def mount_command(letter):
    return (f"sudo mkdir -p /mnt/{letter.lower()} && "
            f"sudo mount -t drvfs {letter}: /mnt/{letter.lower()} -o {mount_options()}")


def fstab_line(letter):
    """The /etc/fstab line that mounts it every time WSL starts (nofail: without the drive, WSL
    starts all the same)."""
    return f"{letter}: /mnt/{letter.lower()} drvfs defaults,nofail,{mount_options()} 0 0"


def mount_hint(letter):
    return f"Windows drive {letter}: isn't available in WSL. Mount it with: {mount_command(letter)}"


_shown = {}


def shown_path(path):
    """A path as the user sees it: on WSL, a folder on a Windows drive in Windows form."""
    path = str(path)
    if is_wsl() and re.match(r"^/mnt/[a-z]/", path) and shutil.which("wslpath"):
        if path not in _shown:
            # wslpath can't name a folder on a drive that isn't mounted (it gives a \\wsl.localhost
            # path): say it the Windows way.
            drive = unmounted_drive(path)
            _shown[path] = (f"{drive}:\\" + path[7:].replace("/", "\\")) if drive else (windows_path(path) or path)
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
    """Send files (or folders) to the system's trash: Windows' Recycle Bin for files on a Windows drive
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
                  "foreach ($p in @($paths)) { if (Test-Path -LiteralPath $p -PathType Container) { "
                  "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($p, 'OnlyErrorDialogs', 'SendToRecycleBin') } "
                  "else { [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($p, 'OnlyErrorDialogs', 'SendToRecycleBin') } }")
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
