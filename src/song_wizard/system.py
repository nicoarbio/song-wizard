"""Opening links and folders with whatever this computer uses: on WSL, the Windows browser and
Explorer; on a Mac, the default browser and the Finder; on Linux, xdg-open."""

import os
import shutil
import subprocess
import sys
import webbrowser

from .paths import is_wsl


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


def launch(command):
    # From a Windows drive on WSL: from a Linux folder, Windows programs warn about UNC paths.
    subprocess.Popen(command, cwd="/mnt/c" if is_wsl() and os.path.isdir("/mnt/c") else None,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
