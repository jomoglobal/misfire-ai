"""
MisfireAI session record store — persistence for pipeline runs.

Each call to the pipeline saves a SessionRecord so we can do longitudinal
analysis: STFT drift over time, LTFT trending across sessions, etc.

Storage backend is chosen at runtime:

  * If the ``DATABASE_URL`` env var is set, sessions and the visit log live in
    Postgres (e.g. Supabase). This survives Railway's ephemeral filesystem.
  * Otherwise we fall back to SQLite at the given ``db_path`` — convenient for
    local dev with no Postgres instance.

The public surface (SessionStore class, log_visit/get_visit_stats functions,
SessionRecord, parse_mhd_filename) is identical across backends, so nothing
else in the app needs to change.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

try:  # Postgres is optional — only needed when DATABASE_URL is set.
    import psycopg2
    import psycopg2.extras
except ImportError:  # pragma: no cover - exercised only without the dep
    psycopg2 = None


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

def _database_url() -> str:
    """Return the configured Postgres URL, or '' to use SQLite."""
    return os.getenv("DATABASE_URL", "").strip()


def _use_postgres() -> bool:
    url = _database_url()
    if not url:
        return False
    if psycopg2 is None:
        raise RuntimeError(
            "DATABASE_URL is set but psycopg2 is not installed. "
            "Add psycopg2-binary to requirements.txt."
        )
    return True


# ---------------------------------------------------------------------------
# MHD filename parser
# ---------------------------------------------------------------------------

# Example: "2026-03-04 12_16_26 IJE0S FF v10.0 stg 2+ a91_c94AT_ALP.csv"
_MHD_FILENAME_RE = re.compile(
    r'^(\d{4}-\d{2}-\d{2} \d{2}_\d{2}_\d{2})\s+(\S+)\s+(.+?)(?:\s+([a-z0-9]+_[a-z0-9]+)(?:AT_ALP)?)?(?:\.csv)?$',
    re.IGNORECASE,
)

def parse_mhd_filename(filename: str) -> dict:
    """
    Extract metadata from an MHD filename.

    Returns dict with keys: vehicle_id, tune, fuel_mix, recorded_at.
    All values are strings; recorded_at is ISO 8601 or empty on parse failure.

    Example input: "2026-03-04 12_16_26 IJE0S FF v10.0 stg 2+ a91_c94AT_ALP.csv"
    """
    name = os.path.basename(filename)
    # Remove .csv extension if present
    stem = name[:-4] if name.lower().endswith(".csv") else name

    # Pattern: <date> <time> <vehicle_id> <tune> <fuel_mix>[AT_ALP]
    # The fuel_mix is the last space-separated token that matches \w+_\w+
    # Approach: split on first three space-delimited pieces, then find fuel_mix at end
    parts = stem.split(" ")
    if len(parts) < 3:
        return {"vehicle_id": "", "tune": "", "fuel_mix": "", "recorded_at": ""}

    date_str = parts[0]      # "2026-03-04"
    time_str = parts[1]      # "12_16_26"
    vehicle_id = parts[2]    # "IJE0S"
    remainder = " ".join(parts[3:])  # "FF v10.0 stg 2+ a91_c94AT_ALP"

    # Parse recorded_at
    recorded_at = ""
    try:
        dt_str = f"{date_str} {time_str.replace('_', ':')}"
        recorded_at = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        ).isoformat()
    except ValueError:
        pass

    # Extract fuel_mix from end of remainder: last token matching \w+_\w+ before optional AT_ALP
    fuel_mix = ""
    tune = remainder
    fuel_mix_match = re.search(r'\b([a-zA-Z0-9]+_[a-zA-Z0-9]+)(?:AT_ALP)?\s*$', remainder)
    if fuel_mix_match:
        fuel_mix = fuel_mix_match.group(1)
        tune = remainder[: fuel_mix_match.start()].strip()

    return {
        "vehicle_id": vehicle_id,
        "tune": tune,
        "fuel_mix": fuel_mix,
        "recorded_at": recorded_at,
    }


# ---------------------------------------------------------------------------
# SessionRecord dataclass
# ---------------------------------------------------------------------------

@dataclass
class SessionRecord:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    vehicle_id: str = ""
    source: str = "unknown"
    file_path: str = ""
    file_name: str = ""
    recorded_at: str = ""         # ISO 8601 — from filename (MHD) or file mtime
    ingested_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    row_count: int = 0
    pids_present: list[str] = field(default_factory=list)
    families_present: list[str] = field(default_factory=list)
    pid_stats: dict[str, dict] = field(default_factory=dict)
    dtcs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    session_meta: dict = field(default_factory=dict)  # tune/fuel_mix/ethanol for MHD
    overall_score: float | None = None
    system_scores: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Schema — one DDL per backend (column types differ slightly)
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQLITE = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id     TEXT PRIMARY KEY,
    vehicle_id     TEXT,
    source         TEXT,
    file_path      TEXT,
    file_name      TEXT,
    recorded_at    TEXT,
    ingested_at    TEXT,
    row_count      INTEGER,
    pids_present   TEXT,
    families_present TEXT,
    pid_stats      TEXT,
    dtcs           TEXT,
    warnings       TEXT,
    session_meta   TEXT,
    overall_score  REAL,
    system_scores  TEXT
)
"""

_CREATE_TABLE_PG = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id     TEXT PRIMARY KEY,
    vehicle_id     TEXT,
    source         TEXT,
    file_path      TEXT,
    file_name      TEXT,
    recorded_at    TEXT,
    ingested_at    TEXT,
    row_count      INTEGER,
    pids_present   TEXT,
    families_present TEXT,
    pid_stats      TEXT,
    dtcs           TEXT,
    warnings       TEXT,
    session_meta   TEXT,
    overall_score  DOUBLE PRECISION,
    system_scores  TEXT
)
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_vehicle_id ON sessions (vehicle_id)",
    "CREATE INDEX IF NOT EXISTS idx_recorded_at ON sessions (recorded_at)",
    "CREATE INDEX IF NOT EXISTS idx_source ON sessions (source)",
]

_CREATE_VISIT_TABLE_SQLITE = """
CREATE TABLE IF NOT EXISTS visit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    visited_at  TEXT NOT NULL,
    ip_hash     TEXT NOT NULL,
    user_agent  TEXT
)
"""

_CREATE_VISIT_TABLE_PG = """
CREATE TABLE IF NOT EXISTS visit_log (
    id          BIGSERIAL PRIMARY KEY,
    visited_at  TEXT NOT NULL,
    ip_hash     TEXT NOT NULL,
    user_agent  TEXT
)
"""

_CREATE_VISIT_INDEX = "CREATE INDEX IF NOT EXISTS idx_visit_date ON visit_log (visited_at)"


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _pg_connect():
    conn = psycopg2.connect(_database_url())
    conn.autocommit = True
    return conn


def _ensure_visit_table_sqlite(conn: sqlite3.Connection) -> None:
    conn.execute(_CREATE_VISIT_TABLE_SQLITE)
    conn.execute(_CREATE_VISIT_INDEX)


def _ensure_visit_table_pg(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(_CREATE_VISIT_TABLE_PG)
        cur.execute(_CREATE_VISIT_INDEX)


# ---------------------------------------------------------------------------
# Visit logging — module-level functions, db_path kept for signature parity
# ---------------------------------------------------------------------------

def log_visit(db_path: str, ip: str, user_agent: str) -> None:
    """Record a page visit. IP is one-way hashed — never stored raw."""
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
    visited_at = datetime.now(timezone.utc).isoformat()
    ua = user_agent[:200] if user_agent else ""

    if _use_postgres():
        conn = _pg_connect()
        try:
            _ensure_visit_table_pg(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO visit_log (visited_at, ip_hash, user_agent) VALUES (%s, %s, %s)",
                    (visited_at, ip_hash, ua),
                )
        finally:
            conn.close()
        return

    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        _ensure_visit_table_sqlite(conn)
        conn.execute(
            "INSERT INTO visit_log (visited_at, ip_hash, user_agent) VALUES (?, ?, ?)",
            (visited_at, ip_hash, ua),
        )


def get_visit_stats(db_path: str, days: int = 30) -> dict:
    """Return visit counts: total hits and unique IPs per day for the last N days."""
    cutoff = (
        datetime.now(timezone.utc) - __import__("datetime").timedelta(days=days)
    ).isoformat()

    if _use_postgres():
        conn = _pg_connect()
        try:
            _ensure_visit_table_pg(conn)
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT substr(visited_at, 1, 10) AS day,
                           COUNT(*)                  AS hits,
                           COUNT(DISTINCT ip_hash)   AS unique_ips
                    FROM visit_log
                    WHERE visited_at >= %s
                    GROUP BY day
                    ORDER BY day DESC
                    """,
                    (cutoff,),
                )
                rows = cur.fetchall()
            # Plain cursor for the totals — two same-named COUNT()s would collide
            # under RealDictCursor, so read them positionally instead.
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*), COUNT(DISTINCT ip_hash) FROM visit_log")
                total = cur.fetchone()
        finally:
            conn.close()
        return {
            "total_hits": total[0],
            "total_unique_ips": total[1],
            "days": [dict(r) for r in rows],
        }

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_visit_table_sqlite(conn)
        rows = conn.execute(
            """
            SELECT substr(visited_at, 1, 10) AS day,
                   COUNT(*)                  AS hits,
                   COUNT(DISTINCT ip_hash)   AS unique_ips
            FROM visit_log
            WHERE visited_at >= ?
            GROUP BY day
            ORDER BY day DESC
            """,
            (cutoff,),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*), COUNT(DISTINCT ip_hash) FROM visit_log").fetchone()
    return {
        "total_hits": total[0],
        "total_unique_ips": total[1],
        "days": [dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# Serialization (shared by both backends — JSON columns are TEXT either way)
# ---------------------------------------------------------------------------

def _serialize(record: SessionRecord) -> dict[str, Any]:
    return {
        "session_id":       record.session_id,
        "vehicle_id":       record.vehicle_id,
        "source":           record.source,
        "file_path":        record.file_path,
        "file_name":        record.file_name,
        "recorded_at":      record.recorded_at,
        "ingested_at":      record.ingested_at,
        "row_count":        record.row_count,
        "pids_present":     json.dumps(record.pids_present),
        "families_present": json.dumps(record.families_present),
        "pid_stats":        json.dumps(record.pid_stats),
        "dtcs":             json.dumps(record.dtcs),
        "warnings":         json.dumps(record.warnings),
        "session_meta":     json.dumps(record.session_meta),
        "overall_score":    record.overall_score,
        "system_scores":    json.dumps(record.system_scores),
    }


def _deserialize(row: dict) -> SessionRecord:
    """Build a SessionRecord from a dict-like row (sqlite3.Row or RealDictRow)."""
    return SessionRecord(
        session_id=      row["session_id"],
        vehicle_id=      row["vehicle_id"] or "",
        source=          row["source"] or "unknown",
        file_path=       row["file_path"] or "",
        file_name=       row["file_name"] or "",
        recorded_at=     row["recorded_at"] or "",
        ingested_at=     row["ingested_at"] or "",
        row_count=       row["row_count"] or 0,
        pids_present=    json.loads(row["pids_present"] or "[]"),
        families_present=json.loads(row["families_present"] or "[]"),
        pid_stats=       json.loads(row["pid_stats"] or "{}"),
        dtcs=            json.loads(row["dtcs"] or "[]"),
        warnings=        json.loads(row["warnings"] or "[]"),
        session_meta=    json.loads(row["session_meta"] or "{}"),
        overall_score=   row["overall_score"],
        system_scores=   json.loads(row["system_scores"] or "{}"),
    )


_COLUMNS = [
    "session_id", "vehicle_id", "source", "file_path", "file_name",
    "recorded_at", "ingested_at", "row_count", "pids_present", "families_present",
    "pid_stats", "dtcs", "warnings", "session_meta", "overall_score", "system_scores",
]


# ---------------------------------------------------------------------------
# SessionStore
# ---------------------------------------------------------------------------

class SessionStore:
    """
    Backend-agnostic session store. Selects Postgres when DATABASE_URL is set,
    otherwise SQLite at ``db_path``. The public method surface is identical
    either way, so callers never need to know which backend is active.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._pg = _use_postgres()
        if self._pg:
            conn = _pg_connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(_CREATE_TABLE_PG)
                    for idx in _CREATE_INDEXES:
                        cur.execute(idx)
            finally:
                conn.close()
        else:
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
            with self._conn() as conn:
                conn.execute(_CREATE_TABLE_SQLITE)
                for idx in _CREATE_INDEXES:
                    conn.execute(idx)

    # -- connection -------------------------------------------------------

    def _conn(self):
        """
        Return a connection usable as a context manager.

        For SQLite this is a sqlite3.Connection with Row factory. For Postgres
        it's a psycopg2 connection in autocommit mode; querying through it uses
        the standard cursor protocol. Kept public-ish because app.py's seeder
        calls ``store._conn()`` directly.
        """
        if self._pg:
            return _pg_connect()
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # -- internal query helpers (backend-aware) ---------------------------

    def _query_all(self, sql_sqlite: str, sql_pg: str, params: tuple) -> list[dict]:
        if self._pg:
            conn = _pg_connect()
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(sql_pg, params)
                    return [dict(r) for r in cur.fetchall()]
            finally:
                conn.close()
        with self._conn() as conn:
            rows = conn.execute(sql_sqlite, params).fetchall()
            return [dict(r) for r in rows]

    def _query_one(self, sql_sqlite: str, sql_pg: str, params: tuple):
        if self._pg:
            conn = _pg_connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql_pg, params)
                    return cur.fetchone()
            finally:
                conn.close()
        with self._conn() as conn:
            return conn.execute(sql_sqlite, params).fetchone()

    # -- writes -----------------------------------------------------------

    def save(self, record: SessionRecord) -> None:
        """Upsert a session record by session_id."""
        data = _serialize(record)
        if self._pg:
            placeholders = ", ".join(["%s"] * len(_COLUMNS))
            updates = ", ".join(
                f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "session_id"
            )
            sql = (
                f"INSERT INTO sessions ({', '.join(_COLUMNS)}) VALUES ({placeholders}) "
                f"ON CONFLICT (session_id) DO UPDATE SET {updates}"
            )
            values = tuple(data[c] for c in _COLUMNS)
            conn = _pg_connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, values)
            finally:
                conn.close()
            return

        placeholders = ", ".join([f":{c}" for c in _COLUMNS])
        updates = ", ".join(
            f"{c} = excluded.{c}" for c in _COLUMNS if c != "session_id"
        )
        sql = (
            f"INSERT INTO sessions ({', '.join(_COLUMNS)}) VALUES ({placeholders}) "
            f"ON CONFLICT(session_id) DO UPDATE SET {updates}"
        )
        with self._conn() as conn:
            conn.execute(sql, data)

    # -- reads ------------------------------------------------------------

    def get(self, session_id: str) -> SessionRecord | None:
        """Retrieve a single session by ID."""
        rows = self._query_all(
            "SELECT * FROM sessions WHERE session_id = ?",
            "SELECT * FROM sessions WHERE session_id = %s",
            (session_id,),
        )
        return _deserialize(rows[0]) if rows else None

    def get_by_vehicle(self, vehicle_id: str, limit: int = 100) -> list[SessionRecord]:
        """All sessions for a vehicle, newest first."""
        rows = self._query_all(
            "SELECT * FROM sessions WHERE vehicle_id = ? ORDER BY recorded_at DESC LIMIT ?",
            "SELECT * FROM sessions WHERE vehicle_id = %s ORDER BY recorded_at DESC LIMIT %s",
            (vehicle_id, limit),
        )
        return [_deserialize(r) for r in rows]

    def get_recent(self, limit: int = 20) -> list[SessionRecord]:
        """Most recently ingested sessions."""
        rows = self._query_all(
            "SELECT * FROM sessions ORDER BY ingested_at DESC LIMIT ?",
            "SELECT * FROM sessions ORDER BY ingested_at DESC LIMIT %s",
            (limit,),
        )
        return [_deserialize(r) for r in rows]

    def get_trend(self, vehicle_id: str, pid: str, limit: int = 50) -> list[dict]:
        """
        Longitudinal trend for a single PID across sessions of a vehicle.

        Returns list of {recorded_at, mean, min, max} sorted by recorded_at ascending,
        for the most recent `limit` sessions that contain the pid.
        """
        rows = self._query_all(
            "SELECT recorded_at, pid_stats FROM sessions WHERE vehicle_id = ? "
            "ORDER BY recorded_at DESC LIMIT ?",
            "SELECT recorded_at, pid_stats FROM sessions WHERE vehicle_id = %s "
            "ORDER BY recorded_at DESC LIMIT %s",
            (vehicle_id, limit),
        )

        trend = []
        for row in rows:
            stats = json.loads(row["pid_stats"] or "{}")
            if pid in stats:
                s = stats[pid]
                trend.append({
                    "recorded_at": row["recorded_at"],
                    "mean": s.get("mean"),
                    "min":  s.get("min"),
                    "max":  s.get("max"),
                })

        # Sort ascending by recorded_at for chronological plots
        trend.sort(key=lambda x: x["recorded_at"] or "")
        return trend

    def get_health_trend(self, vehicle_id: str, limit: int = 500) -> list[dict]:
        """
        Health score timeline for a vehicle — one entry per session that has
        an overall_score, sorted chronologically ascending.

        Returns list of {recorded_at, overall_score, system_scores}.
        system_scores keys: fueling, cooling, ignition, catalyst.
        """
        rows = self._query_all(
            "SELECT recorded_at, overall_score, system_scores FROM sessions "
            "WHERE vehicle_id = ? AND overall_score IS NOT NULL "
            "ORDER BY recorded_at ASC LIMIT ?",
            "SELECT recorded_at, overall_score, system_scores FROM sessions "
            "WHERE vehicle_id = %s AND overall_score IS NOT NULL "
            "ORDER BY recorded_at ASC LIMIT %s",
            (vehicle_id, limit),
        )

        result = []
        for row in rows:
            system_scores = json.loads(row["system_scores"] or "{}")
            result.append({
                "recorded_at":   row["recorded_at"],
                "overall_score": row["overall_score"],
                "system_scores": system_scores,
            })
        return result

    def count_by_vehicle(self) -> dict[str, int]:
        """Session count grouped by vehicle_id."""
        rows = self._query_all(
            "SELECT vehicle_id, COUNT(*) as cnt FROM sessions GROUP BY vehicle_id",
            "SELECT vehicle_id, COUNT(*) as cnt FROM sessions GROUP BY vehicle_id",
            (),
        )
        return {r["vehicle_id"]: r["cnt"] for r in rows}

    def count_vehicle_sessions(self, vehicle_id: str) -> int:
        """Number of sessions stored for a single vehicle (used by the seeder)."""
        row = self._query_one(
            "SELECT COUNT(*) FROM sessions WHERE vehicle_id = ?",
            "SELECT COUNT(*) FROM sessions WHERE vehicle_id = %s",
            (vehicle_id,),
        )
        return row[0] if row else 0

    def summary(self) -> dict:
        """Overall store statistics."""
        total_row = self._query_one(
            "SELECT COUNT(*) FROM sessions",
            "SELECT COUNT(*) FROM sessions",
            (),
        )
        veh_row = self._query_one(
            "SELECT COUNT(DISTINCT vehicle_id) FROM sessions",
            "SELECT COUNT(DISTINCT vehicle_id) FROM sessions",
            (),
        )
        date_row = self._query_one(
            "SELECT MIN(recorded_at), MAX(recorded_at) FROM sessions",
            "SELECT MIN(recorded_at), MAX(recorded_at) FROM sessions",
            (),
        )
        return {
            "total_sessions": total_row[0] if total_row else 0,
            "unique_vehicles": veh_row[0] if veh_row else 0,
            "date_range": {
                "earliest": (date_row[0] if date_row else "") or "",
                "latest":   (date_row[1] if date_row else "") or "",
            },
        }
