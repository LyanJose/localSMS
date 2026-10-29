"""Liaison USB optionnelle via ADB (``adb reverse``).

Avec ``adb reverse tcp:8765 tcp:8765``, le téléphone atteint le serveur du PC via
``http://127.0.0.1:8765`` à travers le câble USB, sans Wi-Fi et sans ouvrir le
serveur au réseau local.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("localsms.adb")
SERIAL_RE = re.compile(r"^[A-Za-z0-9._:\-]{1,64}$")
TIMEOUT_S = 10


class AdbError(RuntimeError):
    pass


def find_adb(custom: str = "") -> str | None:
    candidates: list[str] = []
    if custom:
        candidates.append(custom)
    exe = "adb.exe" if sys.platform == "win32" else "adb"
    base = Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "frozen", False) else None
    if getattr(sys, "frozen", False):
        candidates.append(str(Path(sys.executable).parent / "platform-tools" / exe))
        if base:
            candidates.append(str(base / "platform-tools" / exe))
    found = shutil.which("adb")
    if found:
        candidates.append(found)
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = os.environ.get(env)
        if root:
            candidates.append(str(Path(root) / "platform-tools" / exe))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(str(Path(local) / "Android" / "Sdk" / "platform-tools" / exe))
    for c in candidates:
        if c and Path(c).is_file():
            return c
    return None


def _run(adb: str, *args: str) -> str:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            [adb, *args], capture_output=True, text=True, timeout=TIMEOUT_S,
            shell=False, creationflags=flags,
        )
    except subprocess.TimeoutExpired as exc:
        raise AdbError("ADB ne répond pas (délai dépassé).") from exc
    except OSError as exc:
        raise AdbError(f"Impossible d'exécuter ADB : {exc}") from exc
    if proc.returncode != 0:
        raise AdbError((proc.stderr or proc.stdout).strip() or f"ADB a échoué (code {proc.returncode}).")
    return proc.stdout


def parse_devices(output: str) -> list[dict[str, str]]:
    devices = []
    for line in output.splitlines()[1:]:
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        info = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
        devices.append({"serial": serial, "state": state, "model": info.get("model", "")})
    return devices


def status(custom: str = "") -> dict:
    adb = find_adb(custom)
    if not adb:
        return {"available": False, "path": None, "devices": [], "error": "ADB introuvable. Installez les « platform-tools » Android."}
    try:
        devices = parse_devices(_run(adb, "devices", "-l"))
    except AdbError as exc:
        return {"available": True, "path": adb, "devices": [], "error": str(exc)}
    return {"available": True, "path": adb, "devices": devices, "error": None}


def reverse(port: int, custom: str = "", serial: str | None = None) -> list[dict]:
    adb = find_adb(custom)
    if not adb:
        raise AdbError("ADB introuvable.")
    if serial and not SERIAL_RE.match(serial):
        raise AdbError("Numéro de série invalide.")
    devices = [d for d in parse_devices(_run(adb, "devices", "-l")) if d["state"] == "device"]
    if serial:
        devices = [d for d in devices if d["serial"] == serial]
    if not devices:
        raise AdbError("Aucun téléphone autorisé détecté. Branchez-le, activez le débogage USB et acceptez la clé RSA.")
    results = []
    for d in devices:
        try:
            _run(adb, "-s", d["serial"], "reverse", f"tcp:{port}", f"tcp:{port}")
            results.append({"serial": d["serial"], "ok": True, "error": None})
        except AdbError as exc:
            results.append({"serial": d["serial"], "ok": False, "error": str(exc)})
    return results
