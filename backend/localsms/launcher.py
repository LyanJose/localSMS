"""Point d'entrée : démarre le serveur, ouvre le navigateur, gère l'arrêt propre."""
from __future__ import annotations

import argparse
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import __version__
from .config import DEFAULT_PORT, Runtime, build_runtime

log = logging.getLogger("localsms")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="LocalSMS", description="Serveur LocalSMS (SMS Android -> PC, 100 % local).")
    p.add_argument("--port", type=int, help=f"Port d'écoute (défaut : {DEFAULT_PORT})")
    p.add_argument("--lan", action="store_true", help="Active le mode réseau local (écoute sur 0.0.0.0, accès limité aux IP privées)")
    p.add_argument("--lan-admin", action="store_true", help="Autorise aussi l'interface d'administration depuis le réseau local (déconseillé)")
    p.add_argument("--no-browser", action="store_true", help="N'ouvre pas le navigateur")
    p.add_argument("--data-dir", type=Path, help="Dossier de données (défaut : %%LOCALAPPDATA%%\\LocalSMS)")
    p.add_argument("--reset-admin-token", action="store_true", help="Régénère le jeton d'administration puis quitte")
    p.add_argument("--version", action="version", version=f"LocalSMS {__version__}")
    return p.parse_args(argv)


def setup_logging(rt: Runtime) -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger("localsms")
    root.setLevel(logging.INFO)
    root.handlers.clear()
    fh = RotatingFileHandler(rt.log_dir / "localsms.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    if sys.stderr is not None:
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        root.addHandler(sh)


def show_error(title: str, message: str) -> None:
    """Affiche l'erreur dans la console et, sous Windows, dans une boîte de dialogue
    (la console se ferme sinon immédiatement quand on lance l'exe par double-clic)."""
    print(f"\n[{title}] {message}", file=sys.stderr)
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
        except Exception:
            pass


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def is_localsms_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=1.5) as r:
            return b'"LocalSMS"' in r.read(512)
    except (urllib.error.URLError, OSError, ValueError):
        return False


def open_browser(rt: Runtime) -> None:
    token = rt.load_admin_token()
    # Le jeton est dans le fragment (#) : il n'est jamais envoyé au serveur ni journalisé.
    webbrowser.open(f"http://127.0.0.1:{rt.port}/#token={token}")


def _install_console_close_handler(server) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        handler_type = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)

        def handler(ctrl_type: int) -> int:
            if ctrl_type in (0, 1, 2, 5, 6):  # CTRL_C, CTRL_BREAK, CLOSE, LOGOFF, SHUTDOWN
                server.should_exit = True
                time.sleep(2)  # laisse uvicorn terminer proprement avant la fin du processus
                return 1
            return 0

        _install_console_close_handler._ref = handler_type(handler)  # type: ignore[attr-defined]
        ctypes.windll.kernel32.SetConsoleCtrlHandler(_install_console_close_handler._ref, True)  # type: ignore[attr-defined]
    except Exception:
        log.debug("Gestionnaire de fermeture de console indisponible", exc_info=True)


def relaunch(args_list: list[str]) -> None:
    """Relance LocalSMS (après un changement de mode réseau)."""
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, *args_list]
    else:
        cmd = [sys.executable, "-m", "localsms", *args_list]
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(cmd, env=env, close_fds=True, **kwargs)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        rt = build_runtime(args.data_dir, args.port, args.lan, args.lan_admin)
    except OSError as exc:
        show_error("LocalSMS", f"Impossible de créer le dossier de données :\n{exc}")
        return 2
    setup_logging(rt)

    if args.reset_admin_token:
        rt.rotate_admin_token()
        print("Jeton d'administration régénéré.")
        return 0

    if port_in_use(rt.port):
        if is_localsms_running(rt.port):
            print(f"LocalSMS est déjà en cours d'exécution sur le port {rt.port}.")
            if not args.no_browser:
                open_browser(rt)
            return 0
        show_error("LocalSMS", f"Le port {rt.port} est déjà utilisé par un autre programme.\n"
                               f"Relancez avec --port <autre port>.")
        return 3

    try:
        import uvicorn

        from .main import create_app

        app = create_app(rt)
    except Exception as exc:
        log.exception("Échec de l'initialisation")
        show_error("LocalSMS - erreur au démarrage", f"{exc}\n\nDétails : {rt.log_dir / 'localsms.log'}")
        return 1

    config = uvicorn.Config(app, host=rt.host, port=rt.port, log_level="warning", access_log=False, log_config=None)
    server = uvicorn.Server(config)
    app.state.server = server
    _install_console_close_handler(server)

    print("=" * 60)
    print(f" LocalSMS {__version__}")
    print(f" Interface : http://127.0.0.1:{rt.port}")
    print(f" API / docs : http://127.0.0.1:{rt.port}/docs")
    print(f" Mode réseau : {'LOCAL (Wi-Fi autorisé, IP privées uniquement)' if rt.lan_mode else 'ordinateur uniquement (127.0.0.1)'}")
    print(f" Données : {rt.data_dir}")
    print(" Fermez cette fenêtre ou appuyez sur Ctrl+C pour arrêter.")
    print("=" * 60, flush=True)

    def _opener() -> None:
        for _ in range(100):
            if server.started:
                if not args.no_browser:
                    open_browser(rt)
                return
            time.sleep(0.1)

    threading.Thread(target=_opener, daemon=True).start()

    try:
        server.run()
    except KeyboardInterrupt:
        pass
    except SystemExit as exc:
        if exc.code not in (0, None):
            show_error("LocalSMS", f"Le serveur n'a pas pu démarrer (code {exc.code}).\nVoir {rt.log_dir / 'localsms.log'}")
            return 1
    except Exception as exc:
        log.exception("Erreur fatale du serveur")
        show_error("LocalSMS - erreur", f"{exc}\n\nDétails : {rt.log_dir / 'localsms.log'}")
        return 1
    finally:
        log.info("Serveur arrêté.")

    if rt.restart_requested:
        extra = ["--no-browser"] if args.no_browser else []
        if args.data_dir:
            extra += ["--data-dir", str(args.data_dir)]
        if args.port:
            extra += ["--port", str(args.port)]
        time.sleep(0.5)
        relaunch(extra)
    print("LocalSMS arrêté.")
    return 0
