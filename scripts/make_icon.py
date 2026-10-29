"""Génère scripts/localsms.ico (bulle de SMS blanche sur fond turquoise) sans dépendance."""
import struct
import zlib
from pathlib import Path

N = 256
BG, FG = (14, 124, 134, 255), (255, 255, 255, 255)


def inside_round(x, y, r=52):
    cx = min(max(x, r), N - 1 - r)
    cy = min(max(y, r), N - 1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def bubble(x, y):
    if 56 <= x <= 200 and 64 <= y <= 156:
        return True
    # queue de la bulle : triangle (76,156) (116,156) (76,196)
    return x >= 76 and y >= 156 and (x - 76) + (y - 156) <= 40


rows = bytearray()
for y in range(N):
    rows.append(0)
    for x in range(N):
        px = (0, 0, 0, 0)
        if inside_round(x, y):
            px = FG if bubble(x, y) else BG
        rows += bytes(px)
png = b"\x89PNG\r\n\x1a\n"
for tag, data in ((b"IHDR", struct.pack(">IIBBBBB", N, N, 8, 6, 0, 0, 0)), (b"IDAT", zlib.compress(bytes(rows), 9)), (b"IEND", b"")):
    png += struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
ico = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22) + png
out = Path(__file__).with_name("localsms.ico")
out.write_bytes(ico)
print("Icône écrite :", out)
