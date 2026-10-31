import platform
import shutil
import subprocess
import sys

from .download import node_ok
from .paths import is_wsl

OK, NO, INFO = "\033[32m✔\033[0m", "\033[31m✘\033[0m", "\033[34mℹ\033[0m"


def importable(module):
    # In a subprocess: a broken native library can crash the interpreter, not just raise.
    return subprocess.run([sys.executable, "-c", f"import {module}"], capture_output=True).returncode == 0


def accelerator():
    code = ("import torch\n"
            "if torch.cuda.is_available(): print('NVIDIA GPU (' + torch.cuda.get_device_name(0) + ')')\n"
            "elif torch.backends.mps.is_available(): print('Apple GPU (Metal)')\n"
            "else: print('CPU only (separation will be slow)')")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    return out.stdout.strip() or "unknown"


def run():
    mac = sys.platform == "darwin"
    checks = [
        ("ffmpeg", bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))),
        ("deno or node v20+ (YouTube JS challenges)", bool(shutil.which("deno")) or node_ok()),
        ("rubberband (transpose)", bool(shutil.which("rubberband"))),
        ("essentia (key)", importable("essentia")),
        ("uv (upgrade)", bool(shutil.which("uv"))),
    ]
    system = "macOS" if mac else ("WSL" if is_wsl() else "Linux")
    print(f"Status of this computer ({system}, {platform.machine()}):")
    for desc, ok in checks:
        print(f"  {OK if ok else NO} {desc}")
    print(f"  {INFO} separation runs on: {accelerator()}")

    if all(ok for _, ok in checks):
        print("\nEverything is ready.")
        return

    print("\nTo install what's missing:\n")
    if mac:
        print("  brew install ffmpeg deno rubberband")
    else:
        print("  sudo apt update && sudo apt install -y ffmpeg rubberband-cli build-essential python3-dev")
        print("  curl -fsSL https://deno.land/install.sh | sh")
    print('\nThen close and reopen the terminal and run "song-wizard setup" again.')
