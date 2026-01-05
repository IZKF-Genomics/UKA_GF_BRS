from __future__ import annotations

import os
from typing import Dict


def _total_memory_bytes() -> int:
    """
    Return total system memory in bytes.
    """
    # Linux: MemTotal in kB
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return kb * 1024
    except FileNotFoundError:
        pass
    # macOS: sysctl hw.memsize
    if os.name == "posix":
        try:
            import subprocess

            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
            return int(out)
        except Exception:
            pass
    return 0


def _format_memory_gb(bytes_total: int, ratio: float) -> str:
    if bytes_total <= 0:
        return ""
    gb = int((bytes_total * ratio) / (1024 ** 3))
    if gb < 1:
        gb = 1
    return f"{gb}GB"


def set_max_resources_80pct(ctx) -> Dict[str, str]:
    """
    Pre-render hook: set max_cpus/max_memory to 80% of host capacity if unset.
    """
    params = ctx.params
    if params.get("max_cpus") or params.get("max_memory"):
        return {"skipped": "max_cpus/max_memory already set"}

    total_cpus = os.cpu_count() or 1
    max_cpus = max(1, int(total_cpus * 0.8))
    mem_total = _total_memory_bytes()
    max_memory = _format_memory_gb(mem_total, 0.8)

    params["max_cpus"] = max_cpus
    if max_memory:
        params["max_memory"] = max_memory
    return {"ok": True, "max_cpus": str(max_cpus), "max_memory": max_memory}
