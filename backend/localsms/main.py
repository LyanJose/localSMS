"""Application FastAPI : API REST, WebSocket temps réel et interface web."""
from __future__ import annotations

import asyncio
import hmac
import logging
import socket
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, adb
from .api import ONLINE_WINDOW_S, device_view, router
from .config import Runtime, docs_static_dir, web_dir
from .db import Database
from .events import Hub
from .security import Auth, PairingManager, RateLimiter, is_loopback, is_private_lan, parse_ip

log = logging.getLogger("localsms")

CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "connect-src 'self' ws: wss:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _host_allowed(host_header: str, rt: Runtime) -> bool:
    """Protection contre le « DNS rebinding » : l'en-tête Host doit être connu."""
    raw = host_header.strip().lower()
    if raw.startswith("["):
        host = raw[1: raw.find("]")]
    else:
        host = raw.rsplit(":", 1)[0] if raw.count(":") == 1 else raw
    if host in LOCAL_HOSTS:
        return True
    if rt.lan_mode:
        if parse_ip(host) is not None:
            return is_private_lan(host)
        return host == socket.gethostname().lower() or host == socket.gethostname().lower() + ".local"
    return False


async def _background(app: FastAPI) -> None:
    """Détecte les passages en ligne / hors ligne et applique adb reverse."""
    rt: Runtime = app.state.runtime
    last_online: dict[str, bool] = {}
    adb_seen: set[str] = set()
    tick = 0
    while True:
        try:
            devices = await run_in_threadpool(app.state.db.list_devices)
            for d in devices:
                view = device_view(d)
                prev = last_online.get(d["id"])
                last_online[d["id"]] = view["online"]
                if prev is not None and prev != view["online"]:
                    await app.state.hub.broadcast({"type": "device_status", "device": view})
            if rt.settings.adb_auto_reverse:
                st = await run_in_threadpool(adb.status, rt.settings.adb_path)
                ready = {d["serial"] for d in st["devices"] if d["state"] == "device"}
                for serial in ready - adb_seen:
                    try:
                        await run_in_threadpool(adb.reverse, rt.port, rt.settings.adb_path, serial)
                        log.info("adb reverse appliqué (%s)", serial)
                        await app.state.hub.broadcast({"type": "adb", "serial": serial, "reversed": True})
                    except adb.AdbError as exc:
                        log.warning("adb reverse impossible : %s", exc)
                adb_seen = ready
            tick += 1
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Erreur dans la tâche de fond")
        await asyncio.sleep(5)


def create_app(runtime: Runtime) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(_background(app))
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app = FastAPI(
        title="LocalSMS API",
        version=__version__,
        description=(
            "API locale de LocalSMS. **Authentification** : `Authorization: Bearer <jeton>`.\n\n"
            "* Jeton d'administration (`lsa_…`) : fichier `admin_token` du dossier de données ; "
            "uniquement depuis ce PC.\n"
            "* Jeton d'appareil (`lsd_…`) : obtenu par `/api/v1/pair` avec un code à usage unique."
        ),
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.runtime = runtime
    app.state.db = Database(runtime.db_path)
    app.state.auth = Auth(
        db=app.state.db, admin_token=runtime.load_admin_token(),
        limiter=RateLimiter(), pairing=PairingManager(),
    )
    app.state.hub = Hub()
    app.state.server = None

    # ---------------------------------------------------------- middlewares
    @app.middleware("http")
    async def guard(request: Request, call_next):
        host = request.client.host if request.client else None
        if not is_loopback(host) and not (runtime.lan_mode and is_private_lan(host)):
            return JSONResponse({"detail": "Accès réseau refusé."}, status_code=403)
        if not _host_allowed(request.headers.get("host", ""), runtime):
            return JSONResponse({"detail": "En-tête Host non autorisé."}, status_code=400)
        try:
            response = await call_next(request)
        except Exception:
            log.exception("Erreur non gérée sur %s %s", request.method, request.url.path)
            response = JSONResponse({"detail": "Erreur interne du serveur."}, status_code=500)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
        if not request.url.path.startswith("/docs"):
            response.headers["Content-Security-Policy"] = CSP
        return response

    app.include_router(router)

    # ---------------------------------------------------------- documentation
    static_docs = docs_static_dir()
    if static_docs.is_dir():
        app.mount("/docs-static", StaticFiles(directory=static_docs), name="docs-static")

    @app.get("/docs", include_in_schema=False)
    async def swagger_ui() -> HTMLResponse:
        local = static_docs.is_dir()
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="LocalSMS API - Documentation",
            swagger_js_url="/docs-static/swagger-ui-bundle.js" if local else "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="/docs-static/swagger-ui.css" if local else "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
            swagger_favicon_url="data:,",
        )

    # ---------------------------------------------------------- WebSocket
    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        host = ws.client.host if ws.client else None
        origin = ws.headers.get("origin")
        allowed = is_loopback(host) or (runtime.lan_mode and runtime.lan_admin and is_private_lan(host))
        if not allowed or not _host_allowed(ws.headers.get("host", ""), runtime):
            await ws.close(code=1008)
            return
        if origin and urlsplit(origin).netloc.lower() != ws.headers.get("host", "").lower():
            await ws.close(code=1008)
            return
        auth: Auth = app.state.auth
        if auth.limiter.blocked(host or "?"):
            await ws.close(code=1008)
            return
        await ws.accept()
        try:
            msg = await asyncio.wait_for(ws.receive_json(), timeout=5)
            token = msg.get("token", "") if isinstance(msg, dict) and msg.get("type") == "auth" else ""
            if not isinstance(token, str) or not hmac.compare_digest(token.encode(), auth.admin_token.encode()):
                auth.limiter.fail(host or "?")
                await ws.close(code=1008)
                return
        except (asyncio.TimeoutError, ValueError, WebSocketDisconnect, RuntimeError):
            try:
                await ws.close(code=1008)
            except RuntimeError:
                pass
            return
        app.state.hub.add(ws)
        await ws.send_json({"type": "ready", "version": __version__})
        try:
            while True:
                data = await ws.receive_text()
                if data == "ping":
                    await ws.send_text("pong")
        except WebSocketDisconnect:
            pass
        except Exception:
            log.debug("WebSocket fermé", exc_info=True)
        finally:
            app.state.hub.remove(ws)

    # ---------------------------------------------------------- interface web
    web = web_dir()
    if web:
        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    else:
        @app.get("/", include_in_schema=False)
        async def no_ui() -> HTMLResponse:
            return HTMLResponse(
                "<h1>LocalSMS</h1><p>L'interface web n'est pas compilée "
                "(<code>npm run build</code> dans <code>web/</code>). "
                "L'API reste disponible : <a href='/docs'>/docs</a>.</p>"
            )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Exception non gérée")
        return JSONResponse({"detail": "Erreur interne du serveur."}, status_code=500)

    return app
