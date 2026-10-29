"""Routes REST de l'API LocalSMS (préfixe /api/v1)."""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from . import __version__, adb
from .db import Database, sha256_hex
from .models import (
    AdbReverseRequest, BatchResult, Heartbeat, PairRequest, PairResponse,
    PurgeRequest, SettingsIn, SmsBatch,
)
from .netinfo import local_ipv4_addresses
from .security import (
    Auth, is_loopback, new_device_token, require_admin, require_device,
)

log = logging.getLogger("localsms.api")
ONLINE_WINDOW_S = 90

router = APIRouter(prefix="/api/v1")
public = APIRouter(tags=["Public"])
device_api = APIRouter(tags=["Appareil (application Android)"], dependencies=[])
admin_api = APIRouter(tags=["Administration (interface web)"], dependencies=[Depends(require_admin)])


def _db(request: Request) -> Database:
    return request.app.state.db


def _transport(request: Request) -> str:
    # Via « adb reverse », le téléphone apparaît comme une connexion locale (127.0.0.1).
    return "usb" if request.client and is_loopback(request.client.host) else "wifi"


def device_view(d: dict[str, Any]) -> dict[str, Any]:
    last = d.get("last_seen_at")
    online = bool(last and (time.time() * 1000 - last) < ONLINE_WINDOW_S * 1000)
    return {**d, "online": online, "charging": None if d.get("charging") is None else bool(d["charging"])}


# ----------------------------------------------------------------- public
@public.get("/health", summary="État du serveur")
def health() -> dict[str, Any]:
    return {"status": "ok", "app": "LocalSMS", "version": __version__}


@public.post("/pair", response_model=PairResponse, summary="Associer un téléphone avec un code d'appairage")
def pair(body: PairRequest, request: Request) -> PairResponse:
    auth: Auth = request.app.state.auth
    host = request.client.host if request.client else "?"
    if auth.limiter.blocked(host):
        raise HTTPException(429, "Trop de tentatives. Réessayez dans quelques minutes.")
    if not auth.pairing.consume(body.code):
        auth.limiter.fail(host)
        raise HTTPException(403, "Code d'appairage invalide ou expiré.")
    auth.limiter.reset(host)
    token = new_device_token()
    auth.db.create_device(body.device_id, body.device_name.strip(), sha256_hex(token), _transport(request))
    log.info("Appareil associé : %s (%s)", body.device_name, _transport(request))
    return PairResponse(device_id=body.device_id, device_token=token, server_version=__version__)


# ----------------------------------------------------------------- appareil
@device_api.post("/sms/batch", response_model=BatchResult, summary="Envoyer un lot de SMS")
async def sms_batch(batch: SmsBatch, request: Request, device: dict = Depends(require_device)) -> BatchResult:
    db = _db(request)
    items = [m.model_dump() for m in batch.messages]
    try:
        result = await run_in_threadpool(db.insert_messages, device["id"], items)
    except Exception:
        log.exception("Échec d'insertion d'un lot")
        raise HTTPException(500, "Erreur interne lors de l'enregistrement des messages.")
    pending = batch.sync_remaining
    await run_in_threadpool(
        db.touch_device, device["id"], pending=pending, transport=_transport(request)
    )
    hub = request.app.state.hub
    if result["inserted"]:
        new = result["new_messages"]
        await hub.broadcast(
            {
                "type": "sms_new",
                "device_id": device["id"],
                "inserted": result["inserted"],
                "messages": new[-20:],
            }
        )
    await hub.broadcast(
        {
            "type": "sync_progress",
            "device_id": device["id"],
            "inserted": result["inserted"],
            "duplicates": result["duplicates"],
            "remaining": batch.sync_remaining,
            "total": batch.sync_total,
        }
    )
    return BatchResult(received=result["received"], inserted=result["inserted"], duplicates=result["duplicates"])


@device_api.post("/device/heartbeat", summary="Signal de présence et état du téléphone")
async def heartbeat(body: Heartbeat, request: Request, device: dict = Depends(require_device)) -> dict[str, Any]:
    db = _db(request)
    await run_in_threadpool(
        db.touch_device, device["id"],
        battery=body.battery,
        charging=None if body.charging is None else int(body.charging),
        app_version=body.app_version, pending=body.pending, transport=_transport(request),
    )
    d = await run_in_threadpool(db.get_device, device["id"])
    await request.app.state.hub.broadcast({"type": "device_status", "device": device_view(d)})
    return {"ok": True, "server_time_ms": int(time.time() * 1000)}


@device_api.get("/sync/state", summary="État de synchronisation vu par le serveur")
def sync_state(request: Request, device: dict = Depends(require_device)) -> dict[str, Any]:
    st = _db(request).stats()
    return {"message_count": st["message_count"], "last_date_ms": st["last_date_ms"]}


@device_api.delete("/device/self", summary="Dissocier ce téléphone")
def unpair_self(request: Request, device: dict = Depends(require_device)) -> dict[str, bool]:
    return {"deleted": _db(request).delete_device(device["id"])}


# ----------------------------------------------------------------- admin
@admin_api.post("/pairing/code", summary="Générer un code d'appairage (10 minutes, usage unique)")
def create_pairing_code(request: Request) -> dict[str, Any]:
    pc = request.app.state.auth.pairing.create()
    rt = request.app.state.runtime
    ips = local_ipv4_addresses() if rt.lan_mode else []
    return {
        "code": pc.code,
        "display": f"{pc.code[:4]}-{pc.code[4:]}",
        "expires_in_s": int(pc.expires_at - time.time()),
        "urls": {
            "usb": f"http://127.0.0.1:{rt.port}",
            "wifi": [f"http://{ip}:{rt.port}" for ip in ips],
        },
        "lan_mode": rt.lan_mode,
    }


@admin_api.get("/devices", summary="Téléphones associés et leur état")
def list_devices(request: Request) -> dict[str, Any]:
    return {"items": [device_view(d) for d in _db(request).list_devices()]}


@admin_api.delete("/devices/{device_id}", summary="Révoquer un téléphone (les SMS sont conservés)")
async def delete_device(device_id: str, request: Request) -> dict[str, bool]:
    if not await run_in_threadpool(_db(request).delete_device, device_id):
        raise HTTPException(404, "Appareil introuvable.")
    await request.app.state.hub.broadcast({"type": "device_removed", "device_id": device_id})
    return {"deleted": True}


@admin_api.get("/conversations", summary="Liste paginée des conversations")
def conversations(
    request: Request,
    q: str | None = Query(None, max_length=200, description="Numéro ou nom de contact"),
    page: int = Query(1, ge=1, le=100_000),
    page_size: int = Query(30, ge=1, le=100),
) -> dict[str, Any]:
    return _db(request).conversations(q, page, page_size)


@admin_api.get("/conversations/{thread_key}", summary="Informations sur une conversation")
def conversation_info(thread_key: str, request: Request) -> dict[str, Any]:
    info = _db(request).thread_info(thread_key)
    if not info:
        raise HTTPException(404, "Conversation introuvable.")
    return info


@admin_api.get("/conversations/{thread_key}/messages", summary="Messages d'une conversation (curseur)")
def conversation_messages(
    thread_key: str,
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    before: str | None = Query(None, description="Curseur « date_ms:id » renvoyé par next_cursor"),
) -> dict[str, Any]:
    res = _db(request).thread_messages(thread_key, limit, before)
    if res is None:
        raise HTTPException(422, "Curseur invalide.")
    return res


@admin_api.get("/messages", summary="Recherche de messages (texte, numéro, dates, sens)")
def search_messages(
    request: Request,
    q: str | None = Query(None, max_length=200, description="Texte, numéro ou nom (insensible aux accents)"),
    address: str | None = Query(None, max_length=64),
    thread: str | None = Query(None, max_length=80),
    direction: str | None = Query(None, pattern="^(in|out)$"),
    date_from: int | None = Query(None, ge=0, description="Début (ms UNIX)"),
    date_to: int | None = Query(None, ge=0, description="Fin (ms UNIX)"),
    page: int = Query(1, ge=1, le=100_000),
    page_size: int = Query(30, ge=1, le=100),
) -> dict[str, Any]:
    return _db(request).search_messages(q, address, thread, direction, date_from, date_to, page, page_size)


@admin_api.get("/stats", summary="Statistiques de la base")
def stats(request: Request) -> dict[str, Any]:
    return _db(request).stats()


@admin_api.get("/system/info", summary="Informations sur le serveur")
def system_info(request: Request) -> dict[str, Any]:
    rt = request.app.state.runtime
    return {
        "version": __version__,
        "host": rt.host,
        "port": rt.port,
        "lan_mode": rt.lan_mode,
        "lan_admin": rt.lan_admin,
        "data_dir": str(rt.data_dir),
        "local_ips": local_ipv4_addresses() if rt.lan_mode else [],
        "ws_clients": request.app.state.hub.count,
        "can_shutdown": getattr(request.app.state, "server", None) is not None,
    }


@admin_api.get("/settings", summary="Réglages")
def get_settings(request: Request) -> dict[str, Any]:
    rt = request.app.state.runtime
    s = rt.settings
    return {
        "lan_mode": s.lan_mode, "lan_admin": s.lan_admin, "adb_path": s.adb_path,
        "adb_auto_reverse": s.adb_auto_reverse,
        "effective": {"lan_mode": rt.lan_mode, "lan_admin": rt.lan_admin, "port": rt.port},
        "restart_required": (s.lan_mode != rt.lan_mode) or (s.lan_admin != rt.lan_admin),
    }


@admin_api.put("/settings", summary="Modifier les réglages (le mode LAN demande un redémarrage)")
def put_settings(body: SettingsIn, request: Request) -> dict[str, Any]:
    rt = request.app.state.runtime
    for field in ("lan_mode", "lan_admin", "adb_path", "adb_auto_reverse"):
        value = getattr(body, field)
        if value is not None:
            setattr(rt.settings, field, value.strip() if isinstance(value, str) else value)
    if not rt.settings.lan_mode:
        rt.settings.lan_admin = False
    rt.save_settings()
    return get_settings(request)


@admin_api.post("/auth/rotate-admin-token", summary="Régénérer le jeton d'administration")
def rotate_admin_token(request: Request) -> dict[str, str]:
    token = request.app.state.runtime.rotate_admin_token()
    request.app.state.auth.admin_token = token
    return {"token": token}


@admin_api.post("/data/purge", summary="Supprimer tous les SMS stockés sur le PC")
async def purge(body: PurgeRequest, request: Request) -> dict[str, int]:
    n = await run_in_threadpool(_db(request).purge_messages)
    await request.app.state.hub.broadcast({"type": "purged"})
    return {"deleted": n}


@admin_api.get("/adb/status", summary="État d'ADB et téléphones USB détectés")
async def adb_status(request: Request) -> dict[str, Any]:
    return await run_in_threadpool(adb.status, request.app.state.runtime.settings.adb_path)


@admin_api.post("/adb/reverse", summary="Activer la liaison USB (adb reverse)")
async def adb_reverse(body: AdbReverseRequest, request: Request) -> dict[str, Any]:
    rt = request.app.state.runtime
    try:
        results = await run_in_threadpool(adb.reverse, rt.port, rt.settings.adb_path, body.serial)
    except adb.AdbError as exc:
        raise HTTPException(400, str(exc))
    return {"port": rt.port, "results": results}


@admin_api.post("/system/shutdown", summary="Arrêter LocalSMS")
def shutdown(request: Request) -> dict[str, bool]:
    server = getattr(request.app.state, "server", None)
    if server is None:
        raise HTTPException(503, "Arrêt non disponible dans ce mode.")
    server.should_exit = True
    return {"ok": True}


@admin_api.post("/system/restart", summary="Redémarrer LocalSMS (applique le mode réseau)")
def restart(request: Request) -> dict[str, bool]:
    server = getattr(request.app.state, "server", None)
    if server is None:
        raise HTTPException(503, "Redémarrage non disponible dans ce mode.")
    request.app.state.runtime.restart_requested = True
    server.should_exit = True
    return {"ok": True}


router.include_router(public)
router.include_router(device_api)
router.include_router(admin_api)
