"""Authentification, jetons, codes d'appairage et contrôle d'accès réseau."""
from __future__ import annotations

import hmac
import ipaddress
import secrets
import threading
import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .db import Database, sha256_hex

bearer = HTTPBearer(auto_error=False, description="Jeton d'administration (lsa_…) ou d'appareil (lsd_…)")

PAIRING_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sans caractères ambigus
PAIRING_TTL_S = 600


def parse_ip(host: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if not host:
        return None
    try:
        ip = ipaddress.ip_address(host.split("%")[0])
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return ip.ipv4_mapped
    return ip


def is_loopback(host: str | None) -> bool:
    ip = parse_ip(host)
    return bool(ip and ip.is_loopback)


def is_private_lan(host: str | None) -> bool:
    ip = parse_ip(host)
    return bool(ip and (ip.is_private or ip.is_link_local) and not ip.is_unspecified)


class RateLimiter:
    """Limite les tentatives échouées par adresse IP (anti force brute)."""

    def __init__(self, max_failures: int = 10, window_s: int = 300):
        self.max_failures = max_failures
        self.window_s = window_s
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str) -> list[float]:
        cutoff = time.monotonic() - self.window_s
        lst = [t for t in self._fails.get(key, []) if t > cutoff]
        self._fails[key] = lst
        return lst

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key)) >= self.max_failures

    def fail(self, key: str) -> None:
        with self._lock:
            self._prune(key).append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._fails.pop(key, None)


@dataclass
class PairingCode:
    code: str
    expires_at: float


class PairingManager:
    """Codes d'appairage à usage unique, valables 10 minutes, en mémoire."""

    def __init__(self) -> None:
        self._codes: dict[str, PairingCode] = {}
        self._lock = threading.Lock()

    def create(self) -> PairingCode:
        raw = "".join(secrets.choice(PAIRING_ALPHABET) for _ in range(8))
        pc = PairingCode(code=raw, expires_at=time.time() + PAIRING_TTL_S)
        with self._lock:
            self._purge()
            self._codes.clear()  # un seul code actif à la fois
            self._codes[raw] = pc
        return pc

    def consume(self, code: str) -> bool:
        cleaned = "".join(ch for ch in code.upper() if ch.isalnum())
        with self._lock:
            self._purge()
            ok = cleaned in self._codes
            if ok:
                del self._codes[cleaned]
            return ok

    def _purge(self) -> None:
        now = time.time()
        for k in [k for k, v in self._codes.items() if v.expires_at < now]:
            del self._codes[k]


def new_device_token() -> str:
    return "lsd_" + secrets.token_urlsafe(32)


@dataclass
class Auth:
    """Contexte injecté dans app.state."""

    db: Database
    admin_token: str
    limiter: RateLimiter
    pairing: PairingManager


def _client_host(request: Request) -> str | None:
    return request.client.host if request.client else None


def _unauthorized(detail: str = "Authentification requise.") -> HTTPException:
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


def require_admin(
    request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer)
) -> None:
    auth: Auth = request.app.state.auth
    rt = request.app.state.runtime
    host = _client_host(request)
    if auth.limiter.blocked(host or "?"):
        raise HTTPException(429, "Trop de tentatives. Réessayez dans quelques minutes.")
    if not (is_loopback(host) or (rt.lan_mode and rt.lan_admin and is_private_lan(host))):
        raise HTTPException(403, "L'administration n'est accessible que depuis ce PC.")
    token = creds.credentials if creds else ""
    if not token or not hmac.compare_digest(token.encode(), auth.admin_token.encode()):
        auth.limiter.fail(host or "?")
        raise _unauthorized("Jeton d'administration invalide.")


def require_device(
    request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer)
) -> dict:
    auth: Auth = request.app.state.auth
    host = _client_host(request)
    if auth.limiter.blocked(host or "?"):
        raise HTTPException(429, "Trop de tentatives. Réessayez dans quelques minutes.")
    if not creds or not creds.credentials.startswith("lsd_"):
        auth.limiter.fail(host or "?")
        raise _unauthorized("Jeton d'appareil requis.")
    device = auth.db.device_by_token_hash(sha256_hex(creds.credentials))
    if not device:
        auth.limiter.fail(host or "?")
        raise _unauthorized("Appareil inconnu ou révoqué. Réassociez le téléphone.")
    return device
