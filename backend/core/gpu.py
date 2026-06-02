from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from typing import Any

from .logging import get_logger

_logger = get_logger("core.gpu")


def _safe_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        digits = re.findall(r"\d+", text.replace(",", ""))
        if not digits:
            return None
        return int(digits[0])
    except Exception:
        return None


def _classify_vendor(name: str) -> str:
    n = (name or "").lower()
    if any(k in n for k in ("amd", "radeon", "advanced micro devices", "navi", "vega", "rx ")):
        return "amd"
    if any(k in n for k in ("nvidia", "geforce", "rtx", "gtx", "quadro", "tesla")):
        return "nvidia"
    if any(k in n for k in ("intel", "arc", "iris", "uhd", "hd graphics")):
        return "intel"
    return "unknown"


def _run_cmd(cmd: list[str], timeout: float = 3.0) -> str | None:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except Exception as exc:
        _logger.debug("gpu cmd failed: %s err=%s", cmd, exc)
        return None


def _detect_windows() -> list[dict[str, Any]]:
    gpus: list[dict[str, Any]] = []
    ps = shutil.which("powershell") or shutil.which("pwsh")
    if ps:
        script = (
            "Get-CimInstance Win32_VideoController | "
            "Select-Object Name, AdapterRAM, DeviceID, VideoProcessor | "
            "ConvertTo-Json -Compress"
        )
        out = _run_cmd([ps, "-NoProfile", "-Command", script], timeout=5.0)
        if out:
            try:
                data = json.loads(out)
                if isinstance(data, dict):
                    data = [data]
                for idx, item in enumerate(data):
                    name = item.get("Name") or item.get("VideoProcessor") or "Unknown"
                    vendor = _classify_vendor(str(name))
                    mem = _safe_int(item.get("AdapterRAM"))
                    mem_mb = int(mem / (1024 * 1024)) if mem and mem > 1024 * 1024 else mem
                    gpus.append(
                        {
                            "vendor": vendor,
                            "name": str(name).strip(),
                            "id": str(item.get("DeviceID") or idx),
                            "memory_total_mb": mem_mb,
                        }
                    )
                if gpus:
                    return gpus
            except Exception as exc:
                _logger.warning("failed to parse PowerShell GPU output: %s", exc)

    try:
        import winreg  # type: ignore[import-not-found]

        key_paths = [
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\WinPE",
            r"SYSTEM\CurrentControlSet\Enum\PCI",
        ]
        _ = key_paths
        _ = winreg
    except Exception:
        pass

    return gpus


def _detect_linux() -> list[dict[str, Any]]:
    gpus: list[dict[str, Any]] = []

    lspci = shutil.which("lspci")
    if lspci:
        out = _run_cmd([lspci, "-mm", "-nn"], timeout=3.0) or _run_cmd([lspci, "-mm"], timeout=3.0)
        if out:
            try:
                idx = 0
                for line in out.splitlines():
                    if "VGA" not in line and "3D" not in line and "Display" not in line:
                        continue
                    parts = [p.strip().strip('"') for p in line.split(",")]
                    if len(parts) < 3:
                        continue
                    name = " ".join(parts[2:]) if len(parts) > 3 else parts[2]
                    vendor = _classify_vendor(name)
                    gpus.append(
                        {
                            "vendor": vendor,
                            "name": name,
                            "id": parts[0] if parts else str(idx),
                            "memory_total_mb": None,
                        }
                    )
                    idx += 1
            except Exception as exc:
                _logger.warning("failed to parse lspci output: %s", exc)

    if not gpus:
        try:
            with open("/proc/cmdline", "r", encoding="utf-8", errors="ignore") as f:
                _ = f.read()
        except Exception:
            pass

    return gpus


def _detect_macos() -> list[dict[str, Any]]:
    gpus: list[dict[str, Any]] = []
    sp = shutil.which("system_profiler")
    if sp:
        out = _run_cmd([sp, "-detailLevel", "mini", "SPDisplaysDataType"], timeout=8.0)
        if out:
            try:
                name = None
                vram = None
                for line in out.splitlines():
                    l = line.strip()
                    if l.startswith("Chipset Model:") or l.startswith("Model:"):
                        name = l.split(":", 1)[1].strip()
                    if l.startswith("VRAM"):
                        vram = _safe_int(l.split(":", 1)[1].strip())
                if name:
                    gpus.append(
                        {
                            "vendor": _classify_vendor(name),
                            "name": name,
                            "id": name,
                            "memory_total_mb": vram,
                        }
                    )
            except Exception as exc:
                _logger.warning("failed to parse system_profiler output: %s", exc)
    return gpus


def detect_gpus() -> list[dict[str, Any]]:
    try:
        system = platform.system().lower()
        if system == "windows":
            gpus = _detect_windows()
        elif system == "linux":
            gpus = _detect_linux()
        elif system == "darwin":
            gpus = _detect_macos()
        else:
            gpus = []
    except Exception as exc:
        _logger.warning("GPU detection crashed: %s", exc)
        gpus = []

    if os.getenv("FAKE_GPU") == "1":
        gpus = [
            {"vendor": "amd", "name": "Fake AMD Radeon RX 6700 XT", "id": "0", "memory_total_mb": 12288},
            {"vendor": "nvidia", "name": "Fake NVIDIA GeForce RTX 3060", "id": "1", "memory_total_mb": 12288},
        ]
    elif os.getenv("FAKE_GPU") == "intel":
        gpus = [{"vendor": "intel", "name": "Fake Intel Arc A770", "id": "0", "memory_total_mb": 16384}]

    _logger.info("GPU detection finished: count=%d", len(gpus))
    return gpus
