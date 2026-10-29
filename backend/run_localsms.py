"""Point d'entrée pour PyInstaller (import absolu, pas de package relatif)."""
import multiprocessing

from localsms.launcher import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
