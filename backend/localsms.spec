# -*- mode: python ; coding: utf-8 -*-
# Compilation :  pyinstaller localsms.spec --noconfirm            (exe unique, défaut)
#                set LOCALSMS_ONEDIR=1 & pyinstaller localsms.spec (dossier, démarrage plus rapide)
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

here = Path(SPECPATH)
web = here / "localsms" / "web"
if not (web / "index.html").is_file():
    raise SystemExit("Interface web absente : exécutez d'abord « npm run build » dans web/.")

hidden = (
    collect_submodules("uvicorn")
    + collect_submodules("websockets")
    + collect_submodules("localsms")
    + ["anyio._backends._asyncio", "h11", "email.mime.text"]
)
datas = [
    (str(web), "localsms/web"),
    (str(here / "localsms" / "docs_static"), "localsms/docs_static"),
]
icon = here.parent / "scripts" / "localsms.ico"
onedir = os.environ.get("LOCALSMS_ONEDIR") == "1"

a = Analysis(
    ["run_localsms.py"], pathex=[str(here)], datas=datas, hiddenimports=hidden,
    excludes=["tkinter", "unittest", "pydoc_data", "pytest"], noarchive=False,
)
pyz = PYZ(a.pure)

if onedir:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="LocalSMS", console=True,
              icon=str(icon) if icon.is_file() else None)
    coll = COLLECT(exe, a.binaries, a.datas, name="LocalSMS")
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="LocalSMS", console=True,
              upx=False, runtime_tmpdir=None, icon=str(icon) if icon.is_file() else None)
