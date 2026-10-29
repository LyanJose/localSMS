"""Couche de stockage SQLite (bibliothèque standard, aucune dépendance ORM).

Une connexion courte est ouverte par opération : SQLite en mode WAL gère très
bien ce modèle et il reste sûr avec le pool de threads de FastAPI.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    token_hash    TEXT NOT NULL UNIQUE,
    created_at    INTEGER NOT NULL,
    last_seen_at  INTEGER,
    last_sync_at  INTEGER,
    battery       INTEGER,
    charging      INTEGER,
    app_version   TEXT,
    pending       INTEGER NOT NULL DEFAULT 0,
    transport     TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id      TEXT REFERENCES devices(id) ON DELETE SET NULL,
    sms_id         INTEGER,
    address        TEXT NOT NULL,
    address_digits TEXT NOT NULL,
    thread_key     TEXT NOT NULL,
    contact_name   TEXT,
    contact_search TEXT,
    body           TEXT NOT NULL,
    search_text    TEXT NOT NULL,
    date_ms        INTEGER NOT NULL,
    direction      TEXT NOT NULL CHECK (direction IN ('in', 'out')),
    sms_type       INTEGER NOT NULL,
    is_read        INTEGER NOT NULL DEFAULT 1,
    dedup_hash     TEXT NOT NULL UNIQUE,
    received_at    INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages (thread_key, date_ms, id);
CREATE INDEX IF NOT EXISTS idx_messages_date   ON messages (date_ms, id);
"""


# --------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------
def fold(text: str) -> str:
    """Minuscule sans accents, pour une recherche tolérante (é == e)."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold()


_DIGITS = re.compile(r"\D+")


def address_digits(address: str) -> str:
    return _DIGITS.sub("", address)


def thread_key(address: str) -> str:
    """Clé de conversation.

    * Expéditeur alphanumérique (« ORANGE », « Banque ») : ``a:orange``
    * Numéro de téléphone : ``n:`` + 9 derniers chiffres, ce qui regroupe
      ``0321234567``, ``+261 32 12 345 67`` et ``00261321234567`` dans la
      même conversation.
    """
    if re.search(r"[A-Za-z]", address):
        return "a:" + fold(address.strip())
    digits = address_digits(address)
    if not digits:
        return "a:inconnu"
    return "n:" + digits[-9:]


def compute_dedup_hash(key: str, date_ms: int, direction: str, body: str) -> str:
    raw = "\x1f".join((key, str(date_ms), direction, body))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def direction_for_type(sms_type: int) -> str:
    # android.provider.Telephony.Sms : 1 = reçu ; 2, 4, 5, 6 = envoyé/en cours
    return "in" if sms_type == 1 else "out"


def like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def now_ms() -> int:
    return int(time.time() * 1000)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Base de données
# --------------------------------------------------------------------------
class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 30000")
            yield conn
        finally:
            conn.close()

    def init(self) -> None:
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.executescript(SCHEMA)
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            elif version > SCHEMA_VERSION:
                raise RuntimeError(
                    "La base de données a été créée par une version plus récente de LocalSMS."
                )
        try:
            if self.path.exists():
                import os

                if os.name == "posix":
                    os.chmod(self.path, 0o600)
        except OSError:
            pass

    # ----------------------------- appareils -----------------------------
    def create_device(self, device_id: str, name: str, token_hash: str, transport: str | None) -> None:
        now = now_ms()
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO devices (id, name, token_hash, created_at, last_seen_at, transport)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET name = excluded.name,
                       token_hash = excluded.token_hash, last_seen_at = excluded.last_seen_at,
                       transport = excluded.transport""",
                (device_id, name, token_hash, now, now, transport),
            )

    def device_by_token_hash(self, token_hash: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM devices WHERE token_hash = ?", (token_hash,)).fetchone()
        return dict(row) if row else None

    def touch_device(self, device_id: str, **fields: Any) -> None:
        allowed = {"battery", "charging", "app_version", "pending", "transport", "last_sync_at"}
        cols = {k: v for k, v in fields.items() if k in allowed and v is not None}
        cols["last_seen_at"] = now_ms()
        sets = ", ".join(f"{k} = ?" for k in cols)
        with self.connect() as conn:
            conn.execute(f"UPDATE devices SET {sets} WHERE id = ?", (*cols.values(), device_id))

    def list_devices(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT d.id, d.name, d.created_at, d.last_seen_at, d.last_sync_at, d.battery,
                          d.charging, d.app_version, d.pending, d.transport,
                          (SELECT COUNT(*) FROM messages m WHERE m.device_id = d.id) AS message_count
                   FROM devices d ORDER BY d.created_at DESC"""
            ).fetchall()
        return [dict(r) for r in rows]

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        for d in self.list_devices():
            if d["id"] == device_id:
                return d
        return None

    def delete_device(self, device_id: str) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
            return cur.rowcount > 0

    # ----------------------------- messages ------------------------------
    def insert_messages(self, device_id: str, items: Iterable[dict[str, Any]]) -> dict[str, Any]:
        """Insère un lot de SMS. Les doublons (même conversation, même date,
        même sens, même texte) sont ignorés, quel que soit l'appareil."""
        received = inserted = 0
        new_rows: list[dict[str, Any]] = []
        now = now_ms()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                for it in items:
                    received += 1
                    address = it["address"]
                    key = thread_key(address)
                    direction = direction_for_type(it["type"])
                    digest = compute_dedup_hash(key, it["date_ms"], direction, it["body"])
                    contact = it.get("contact_name") or None
                    cur = conn.execute(
                        """INSERT OR IGNORE INTO messages
                           (device_id, sms_id, address, address_digits, thread_key, contact_name,
                            contact_search, body, search_text, date_ms, direction, sms_type,
                            is_read, dedup_hash, received_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            device_id, it.get("sms_id"), address, address_digits(address), key,
                            contact, fold(contact) if contact else None, it["body"], fold(it["body"]),
                            it["date_ms"], direction, it["type"], 1 if it.get("read", True) else 0,
                            digest, now,
                        ),
                    )
                    if cur.rowcount:
                        inserted += 1
                        new_rows.append(
                            {
                                "id": cur.lastrowid, "thread_key": key, "address": address,
                                "contact_name": contact, "body": it["body"],
                                "date_ms": it["date_ms"], "direction": direction,
                            }
                        )
                conn.execute(
                    "UPDATE devices SET last_sync_at = ?, last_seen_at = ? WHERE id = ?",
                    (now, now, device_id),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return {
            "received": received,
            "inserted": inserted,
            "duplicates": received - inserted,
            "new_messages": new_rows,
        }

    @staticmethod
    def _message_row(r: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": r["id"],
            "thread_key": r["thread_key"],
            "address": r["address"],
            "contact_name": r["contact_name"],
            "body": r["body"],
            "date_ms": r["date_ms"],
            "direction": r["direction"],
            "device_id": r["device_id"],
        }

    def conversations(self, q: str | None, page: int, page_size: int) -> dict[str, Any]:
        where = ""
        params: list[Any] = []
        if q:
            folded = like_escape(fold(q.strip()))
            digits = address_digits(q)
            clauses = [
                "LOWER(address) LIKE ? ESCAPE '\\'",
                "contact_search LIKE ? ESCAPE '\\'",
                "thread_key LIKE ? ESCAPE '\\'",
            ]
            params += [f"%{folded}%", f"%{folded}%", f"%{folded}%"]
            if digits:
                clauses.append("address_digits LIKE ? ESCAPE '\\'")
                params.append(f"%{digits}%")
            where = "WHERE thread_key IN (SELECT DISTINCT thread_key FROM messages WHERE " + " OR ".join(clauses) + ")"
        with self.connect() as conn:
            total = conn.execute(
                f"SELECT COUNT(DISTINCT thread_key) FROM messages {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"""SELECT g.thread_key, g.total, g.last_date, m.address, m.body, m.direction,
                           COALESCE((SELECT contact_name FROM messages c
                                     WHERE c.thread_key = g.thread_key AND c.contact_name IS NOT NULL
                                     ORDER BY c.date_ms DESC LIMIT 1), NULL) AS contact_name
                    FROM (SELECT thread_key, COUNT(*) AS total, MAX(date_ms) AS last_date
                          FROM messages {where} GROUP BY thread_key
                          ORDER BY last_date DESC LIMIT ? OFFSET ?) g
                    JOIN messages m ON m.id = (SELECT id FROM messages x WHERE x.thread_key = g.thread_key
                                               ORDER BY x.date_ms DESC, x.id DESC LIMIT 1)
                    ORDER BY g.last_date DESC""",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
        items = [
            {
                "thread_key": r["thread_key"],
                "address": r["address"],
                "contact_name": r["contact_name"],
                "last_body": r["body"],
                "last_date_ms": r["last_date"],
                "last_direction": r["direction"],
                "message_count": r["total"],
            }
            for r in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def thread_messages(self, key: str, limit: int, before: str | None) -> dict[str, Any] | None:
        """Messages d'une conversation, du plus récent au plus ancien, avec
        curseur ``before`` = ``date_ms:id`` (stable même pendant la synchro)."""
        cursor_sql = ""
        params: list[Any] = [key]
        if before:
            m = re.fullmatch(r"(\d+):(\d+)", before)
            if not m:
                return None
            cursor_sql = "AND (date_ms < ? OR (date_ms = ? AND id < ?))"
            params += [int(m.group(1)), int(m.group(1)), int(m.group(2))]
        with self.connect() as conn:
            rows = conn.execute(
                f"""SELECT * FROM messages WHERE thread_key = ? {cursor_sql}
                    ORDER BY date_ms DESC, id DESC LIMIT ?""",
                [*params, limit + 1],
            ).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [self._message_row(r) for r in rows]
        next_cursor = f"{rows[-1]['date_ms']}:{rows[-1]['id']}" if has_more and rows else None
        return {"items": items, "next_cursor": next_cursor, "has_more": has_more}

    def thread_info(self, key: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """SELECT thread_key, COUNT(*) AS total, MIN(date_ms) AS first_date, MAX(date_ms) AS last_date
                   FROM messages WHERE thread_key = ? GROUP BY thread_key""",
                (key,),
            ).fetchone()
            if not row:
                return None
            last = conn.execute(
                "SELECT address, contact_name FROM messages WHERE thread_key = ? ORDER BY date_ms DESC, id DESC LIMIT 1",
                (key,),
            ).fetchone()
            name = conn.execute(
                "SELECT contact_name FROM messages WHERE thread_key = ? AND contact_name IS NOT NULL "
                "ORDER BY date_ms DESC LIMIT 1",
                (key,),
            ).fetchone()
        return {
            "thread_key": key,
            "address": last["address"],
            "contact_name": name["contact_name"] if name else None,
            "message_count": row["total"],
            "first_date_ms": row["first_date"],
            "last_date_ms": row["last_date"],
        }

    def search_messages(
        self,
        q: str | None,
        address: str | None,
        thread: str | None,
        direction: str | None,
        date_from: int | None,
        date_to: int | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        if q and q.strip():
            folded = like_escape(fold(q.strip()))
            digits = address_digits(q)
            sub = ["search_text LIKE ? ESCAPE '\\'", "contact_search LIKE ? ESCAPE '\\'", "LOWER(address) LIKE ? ESCAPE '\\'"]
            params += [f"%{folded}%", f"%{folded}%", f"%{folded}%"]
            if len(digits) >= 3:
                sub.append("address_digits LIKE ? ESCAPE '\\'")
                params.append(f"%{digits}%")
            clauses.append("(" + " OR ".join(sub) + ")")
        if address and address.strip():
            digits = address_digits(address)
            if digits:
                clauses.append("address_digits LIKE ? ESCAPE '\\'")
                params.append(f"%{digits}%")
            else:
                clauses.append("LOWER(address) LIKE ? ESCAPE '\\'")
                params.append(f"%{like_escape(address.strip().lower())}%")
        if thread:
            clauses.append("thread_key = ?")
            params.append(thread)
        if direction in ("in", "out"):
            clauses.append("direction = ?")
            params.append(direction)
        if date_from is not None:
            clauses.append("date_ms >= ?")
            params.append(date_from)
        if date_to is not None:
            clauses.append("date_ms <= ?")
            params.append(date_to)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self.connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM messages {where}", params).fetchone()[0]
            rows = conn.execute(
                f"""SELECT * FROM messages {where} ORDER BY date_ms DESC, id DESC LIMIT ? OFFSET ?""",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
        return {
            "items": [self._message_row(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n, MIN(date_ms) AS first, MAX(date_ms) AS last, "
                "COUNT(DISTINCT thread_key) AS threads FROM messages"
            ).fetchone()
        try:
            size = self.path.stat().st_size
        except OSError:
            size = 0
        return {
            "message_count": row["n"],
            "conversation_count": row["threads"],
            "first_date_ms": row["first"],
            "last_date_ms": row["last"],
            "db_size_bytes": size,
        }

    def purge_messages(self) -> int:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM messages")
            conn.execute("VACUUM")
            return cur.rowcount
