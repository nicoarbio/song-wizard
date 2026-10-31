"""Pick where separation runs: NVIDIA GPU, Apple GPU or CPU.

PyTorch reports old NVIDIA cards as available even when its build has no kernels for
them, and the first operation then crashes. So the card's architecture is checked against
the build before trusting it.
"""

import shutil


def cuda_supported(torch):
    major, minor = torch.cuda.get_device_capability(0)
    for arch in torch.cuda.get_arch_list():
        if arch.startswith("sm_"):
            a_major, a_minor = int(arch[3:-1]), int(arch[-1])
            # A GPU runs kernels built for its own major version and an equal or lower minor.
            if a_major == major and a_minor <= minor:
                return True
    return False


def pick(force_cpu=False):
    """Returns (device name for torch, human description, warning or None)."""
    import torch

    if force_cpu:
        return "cpu", "CPU (forced with --cpu)", None
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        if cuda_supported(torch):
            return "cuda", f"NVIDIA GPU ({name})", None
        major, minor = torch.cuda.get_device_capability(0)
        return "cpu", "CPU", (f"{name} (sm_{major}{minor}) is too old for this PyTorch build "
                              "(needs GTX 16 / RTX 20 or newer); using the CPU, which is slower.")
    if torch.backends.mps.is_available():
        return "mps", "Apple GPU (Metal)", None
    if shutil.which("nvidia-smi"):
        return "cpu", "CPU", ("an NVIDIA card was found but PyTorch can't use it; updating the NVIDIA "
                              "driver usually fixes it. Using the CPU, which is slower.")
    return "cpu", "CPU", None


def describe():
    device, desc, warning = pick()
    lines = [desc + (" (separation will be slow)" if device == "cpu" else "")]
    if warning:
        lines.append(f"    {warning}")
    return "\n".join(lines)
