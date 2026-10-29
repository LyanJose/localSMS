#!/usr/bin/env python3
"""Test de bout en bout : lance le VRAI serveur (processus séparé), simule le protocole
du téléphone via HTTP, vérifie WebSocket, interface web, documentation, persistance,
arrêt propre et mode réseau local.

Usage : python scripts/e2e_test.py            (depuis la racine du dépôt)
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def http(method, url, token=None, body=None, host=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if host:
        req.add_header("Host", host)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw[:1] in (b"{", b"[") else raw)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw


def start(data_dir: Path, port: int, *extra: str) -> subprocess.Popen:
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    # LOCALSMS_BIN=chemin/vers/LocalSMS(.exe) : teste l'exécutable compilé plutôt que les sources
    cmd = [os.environ["LOCALSMS_BIN"]] if os.environ.get("LOCALSMS_BIN") else [sys.executable, "-m", "localsms"]
    return subprocess.Popen(
        [*cmd, "--no-browser", "--port", str(port), "--data-dir", str(data_dir), *extra],
        cwd=BACKEND, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )


def wait_ready(base: str, proc: subprocess.Popen, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        if proc.poll() is not None:
            raise RuntimeError("Le serveur s'est arrêté au démarrage :\n" + (proc.stdout.read() or ""))
        try:
            if http("GET", base + "/api/v1/health")[0] == 200:
                return
        except Exception:
            pass
        time.sleep(0.2)
    raise RuntimeError("Délai de démarrage dépassé")


def check(cond, label):
    print(("  OK   " if cond else "  ECHEC ") + label)
    if not cond:
        raise SystemExit(f"Échec : {label}")


def sms(i, addr="+261321234567", body=None, t=1, base_date=1_700_000_000_000):
    return {"sms_id": i, "address": addr, "body": body or f"Message {i} é", "date_ms": base_date + i * 1000, "type": t, "read": True}


async def ws_part(base_ws: str, host: str, admin: str, post_live):
    import websockets

    async with websockets.connect(base_ws) as ws:
        await ws.send(json.dumps({"type": "auth", "token": admin}))
        check(json.loads(await asyncio.wait_for(ws.recv(), 5))["type"] == "ready", "WebSocket authentifié")
        await asyncio.get_running_loop().run_in_executor(None, post_live)
        got = set()
        while not {"sms_new", "sync_progress"} <= got:
            ev = json.loads(await asyncio.wait_for(ws.recv(), 5))
            got.add(ev["type"])
            if ev["type"] == "sms_new":
                check(ev["messages"][-1]["body"] == "SMS en direct", "événement sms_new reçu en temps réel")
        check({"sms_new", "sync_progress"} <= got, "événements temps réel complets")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="localsms-e2e-"))
    data = tmp / "data"
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    print(f"Dossier de test : {tmp}")
    proc = start(data, port)
    try:
        wait_ready(base, proc)
        print("1. Serveur, interface et documentation")
        admin = (data / "admin_token").read_text().strip()
        st, html = http("GET", base + "/")
        check(st == 200 and b'id="root"' in html, "interface web servie sur /")
        js = [p for p in (BACKEND / "localsms/web/assets").iterdir() if p.suffix == ".js"][0].name
        check(http("GET", f"{base}/assets/{js}")[0] == 200, "bundle JavaScript servi")
        check(http("GET", base + "/docs")[0] == 200, "/docs disponible")
        check(http("GET", base + "/docs-static/swagger-ui-bundle.js")[0] == 200, "Swagger UI hors ligne (aucun CDN)")
        check("/api/v1/sms/batch" in http("GET", base + "/openapi.json")[1]["paths"], "OpenAPI complet")

        print("2. Authentification")
        check(http("GET", base + "/api/v1/stats")[0] == 401, "API admin refusée sans jeton")
        check(http("GET", base + "/api/v1/stats", token="faux")[0] == 401, "API admin refusée avec faux jeton")
        check(http("GET", base + "/api/v1/stats", token=admin)[0] == 200, "API admin acceptée avec le bon jeton")
        check(http("GET", base + "/api/v1/stats", token=admin, host="evil.com")[0] == 400, "Host étranger refusé (DNS rebinding)")
        code = http("POST", base + "/api/v1/pairing/code", token=admin)[1]["code"]
        st, pr = http("POST", base + "/api/v1/pair", body={"code": code, "device_id": "e2e-device-001", "device_name": "Téléphone E2E"})
        check(st == 200 and pr["device_token"].startswith("lsd_"), "appairage par code")
        dev = pr["device_token"]
        check(http("POST", base + "/api/v1/pair", body={"code": code, "device_id": "e2e-device-002", "device_name": "X"})[0] == 403, "code à usage unique")

        print("3. Synchronisation initiale (1 200 SMS en 3 lots) et doublons")
        for n in range(3):
            batch = [sms(i, f"+26132{i % 40:07d}") for i in range(n * 400, n * 400 + 400)]
            st, r = http("POST", base + "/api/v1/sms/batch", token=dev, body={"messages": batch, "sync_total": 1200, "sync_remaining": 800 - n * 400})
            check(st == 200 and r["inserted"] == 400, f"lot {n + 1} inséré")
        st, r = http("POST", base + "/api/v1/sms/batch", token=dev, body={"messages": [sms(i, f"+26132{i % 40:07d}") for i in range(0, 400)]})
        check(r["duplicates"] == 400 and r["inserted"] == 0, "reprise après coupure : 400 doublons ignorés")
        check(http("GET", base + "/api/v1/stats", token=admin)[1]["message_count"] == 1200, "1 200 messages stockés exactement")

        print("4. Temps réel (WebSocket)")
        def live():
            http("POST", base + "/api/v1/sms/batch", token=dev, body={"messages": [sms(5000, body="SMS en direct", base_date=1_800_000_000_000)], "sync_remaining": 0})
        asyncio.run(ws_part(f"ws://127.0.0.1:{port}/ws", f"127.0.0.1:{port}", admin, live))

        print("5. Conversations, recherche, pagination")
        c = http("GET", base + "/api/v1/conversations?page_size=10", token=admin)[1]
        check(c["total"] == 41 and len(c["items"]) == 10 and c["items"][0]["last_body"] == "SMS en direct", "conversations paginées, plus récente en premier")
        r = http("GET", base + "/api/v1/messages?q=" + urllib.request.quote("MESSAGE 777 E"), token=admin)[1]
        check(r["total"] == 1, "recherche insensible à la casse et aux accents")
        r = http("GET", base + "/api/v1/messages?q=direct&direction=in", token=admin)[1]
        check(r["total"] == 1, "recherche + filtre de sens")
        http("POST", base + "/api/v1/device/heartbeat", token=dev, body={"battery": 64, "charging": False, "app_version": "1.0.0", "pending": 0})
        d = http("GET", base + "/api/v1/devices", token=admin)[1]["items"][0]
        check(d["online"] and d["battery"] == 64 and d["message_count"] == 1201, "état du téléphone (en ligne, batterie)")

        print("6. Arrêt propre et persistance")
        check(http("POST", base + "/api/v1/system/shutdown", token=admin)[0] == 200, "arrêt demandé via l'API")
        check(proc.wait(timeout=15) == 0, "processus arrêté proprement (code 0)")
        proc = start(data, port)
        wait_ready(base, proc)
        admin2 = (data / "admin_token").read_text().strip()
        check(admin2 == admin, "jeton administrateur persistant")
        check(http("GET", base + "/api/v1/stats", token=admin)[1]["message_count"] == 1201, "base SQLite persistante après redémarrage")
        check(http("POST", base + "/api/v1/device/heartbeat", token=dev, body={"battery": 60})[0] == 200, "le téléphone reprend avec son jeton sans réassociation")
        http("POST", base + "/api/v1/system/shutdown", token=admin)
        proc.wait(timeout=15)

        print("7. Mode réseau local (--lan)")
        proc = start(data, port, "--lan")
        wait_ready(base, proc)
        lan_ip = None
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("10.255.255.255", 1))
                lan_ip = s.getsockname()[0]
        except OSError:
            pass
        if lan_ip and lan_ip != "127.0.0.1":
            lb = f"http://{lan_ip}:{port}"
            check(http("GET", lb + "/api/v1/health")[0] == 200, f"serveur joignable en LAN ({lan_ip})")
            check(http("GET", lb + "/api/v1/stats", token=admin)[0] == 403, "administration refusée depuis le LAN")
            check(http("POST", lb + "/api/v1/device/heartbeat", token=dev, body={"battery": 50})[0] == 200, "téléphone accepté en LAN avec son jeton")
        else:
            print("  (aucune interface réseau privée dans cet environnement : test LAN réseau ignoré)")
        http("POST", base + "/api/v1/system/shutdown", token=admin)
        check(proc.wait(timeout=15) == 0, "arrêt propre en mode LAN")
        print("\nTOUS LES TESTS DE BOUT EN BOUT SONT PASSÉS")
        return 0
    finally:
        if proc.poll() is None:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
