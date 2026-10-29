"""Configuration et chemins persistants de LocalSMS.

Les données (base SQLite, jeton d'administration, réglages, journaux) sont
stockées dans un dossier utilisateur persistant, jamais dans le dossier du
programme ni dans le dépôt Git :

* Windows : ``%LOCALAPPDATA%\\LocalSMS``
* Linux / macOS : ``~/.local/share/localsms``

Le dossier peut être surchargé avec ``--data-dir`` ou ``LOCALSMS_DATA_DIR``.
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def default_data_dir() -> Path:
    override = os.environ.get("LOCALSMS_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "LocalSMS"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "localsms"


def _restrict(path: Path, mode: int) -> None:
    """Restreint les droits (POSIX). Sous Windows, le dossier du profil utilisateur
    est déjà protégé par les ACL de l'utilisateur."""
    try:
        if os.name == "posix":
            os.chmod(path, mode)
    except OSError:
        pass


def web_dir() -> Path | None:
    """Localise l'interface web compilée (dossier contenant index.html)."""
    candidates: list[Path] = []
    env = os.environ.get("LOCALSMS_WEB_DIR")
    if env:
        candidates.append(Path(env))
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "localsms" / "web")
    candidates.append(Path(__file__).resolve().parent / "web")
    for c in candidates:
        if (c / "index.html").is_file():
            return c
    return None


def docs_static_dir() -> Path:
    return Path(__file__).resolve().parent / "docs_static"


@dataclass
class Settings:
    """Réglages persistants (settings.json)."""

    lan_mode: bool = False          # écoute sur le réseau local (0.0.0.0)
    lan_admin: bool = False         # autorise l'interface d'administration depuis le LAN
    port: int = DEFAULT_PORT
    adb_path: str = ""              # chemin personnalisé vers adb(.exe)
    adb_auto_reverse: bool = False  # applique « adb reverse » automatiquement

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        s = cls()
        for key, value in known.items():
            default = getattr(s, key)
            if isinstance(default, bool) and isinstance(value, bool):
                setattr(s, key, value)
            elif isinstance(default, int) and not isinstance(default, bool) and isinstance(value, int):
                setattr(s, key, value)
            elif isinstance(default, str) and isinstance(value, str):
                setattr(s, key, value)
        if not (1024 <= s.port <= 65535):
            s.port = DEFAULT_PORT
        return s


@dataclass
class Runtime:
    """Valeurs effectives pour cette exécution (arguments CLI inclus)."""

    data_dir: Path
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    lan_mode: bool = False
    lan_admin: bool = False
    settings: Settings = field(default_factory=Settings)
    restart_requested: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ----- chemins -----
    @property
    def db_path(self) -> Path:
        return self.data_dir / "localsms.db"

    @property
    def settings_path(self) -> Path:
        return self.data_dir / "settings.json"

    @property
    def admin_token_path(self) -> Path:
        return self.data_dir / "admin_token"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    # ----- persistance -----
    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        _restrict(self.data_dir, 0o700)

    def save_settings(self) -> None:
        with self._lock:
            tmp = self.settings_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(asdict(self.settings), indent=2), encoding="utf-8")
            _restrict(tmp, 0o600)
            os.replace(tmp, self.settings_path)

    def load_admin_token(self) -> str:
        """Lit (ou crée) le jeton d'administration de l'interface web."""
        path = self.admin_token_path
        if path.is_file():
            token = path.read_text(encoding="utf-8").strip()
            if len(token) >= 32:
                return token
        return self.rotate_admin_token()

    def rotate_admin_token(self) -> str:
        token = "lsa_" + secrets.token_urlsafe(32)
        tmp = self.admin_token_path.with_suffix(".tmp")
        tmp.write_text(token, encoding="utf-8")
        _restrict(tmp, 0o600)
        os.replace(tmp, self.admin_token_path)
        return token


def build_runtime(
    data_dir: Path | None = None,
    port: int | None = None,
    lan: bool | None = None,
    lan_admin: bool | None = None,
) -> Runtime:
    data_dir = Path(data_dir) if data_dir else default_data_dir()
    rt = Runtime(data_dir=data_dir)
    rt.ensure_dirs()
    if rt.settings_path.is_file():
        try:
            rt.settings = Settings.from_dict(json.loads(rt.settings_path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            rt.settings = Settings()
    rt.port = port if port else rt.settings.port
    rt.lan_mode = bool(lan) or rt.settings.lan_mode
    rt.lan_admin = bool(lan_admin) or rt.settings.lan_admin
    rt.host = "0.0.0.0" if rt.lan_mode else DEFAULT_HOST
    return rt
