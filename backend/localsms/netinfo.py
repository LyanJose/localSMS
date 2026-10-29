"""Adresses IP locales du PC (pour renseigner l'application Android)."""
from __future__ import annotations

import ipaddress
import socket


def local_ipv4_addresses() -> list[str]:
    found: set[str] = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("10.255.255.255", 1))  # aucun paquet n'est envoyé
        found.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(info[4][0])
    except OSError:
        pass
    out = []
    for addr in sorted(found):
        ip = ipaddress.ip_address(addr)
        if ip.is_private and not ip.is_loopback and not ip.is_link_local:
            out.append(addr)
    return out
