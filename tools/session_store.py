"""
MisfireAI session record store — SQLite-backed persistence for pipeline runs.

Each call to the pipeline saves a SessionRecord so we can do longitudinal
analysis: STFT drift over time, LTFT trending across sessions, etc.

DB path: data/sessions.db (relative to repo root, created on first use).
Uses only stdlib: sqlite3, json, uuid, datetime.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


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
# SessionStore
# ---------------------------------------------------------------------------

_CREATE_TABLE = """
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

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_vehicle_id ON sessions (vehicle_id)",
    "CREATE INDEX IF NOT EXISTS idx_recorded_at ON sessions (recorded_at)",
    "CREATE INDEX IF NOT EXISTS idx_source ON sessions (source)",
]

_UPSERT = """
INSERT INTO sessions (
    session_id, vehicle_id, source, file_path, file_name,
    recorded_at, ingested_at, row_count, pids_present, families_present,
    pid_stats, dtcs, warnings, session_meta, overall_score, system_scores
) VALUES (
    :session_id, :vehicle_id, :source, :file_path, :file_name,
    :recorded_at, :ingested_at, :row_count, :pids_present, :families_present,
    :pid_stats, :dtcs, :warnings, :session_meta, :overall_score, :system_scores
)
ON CONFLICT(session_id) DO UPDATE SET
    vehicle_id      = excluded.vehicle_id,
    source          = excluded.source,
    file_path       = excluded.file_path,
    file_name       = excluded.file_name,
    recorded_at     = excluded.recorded_at,
    ingested_at     = excluded.ingested_at,
    row_count       = excluded.row_count,
    pids_present    = excluded.pids_present,
    families_present = excluded.families_present,
    pid_stats       = excluded.pid_stats,
    dtcs            = excluded.dtcs,
    warnings        = excluded.warnings,
    session_meta    = excluded.session_meta,
    overall_score   = excluded.overall_score,
    system_scores   = excluded.system_scores
"""


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


def _deserialize(row: sqlite3.Row) -> SessionRecord:
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


class SessionStore:
    def __init__(self, db_path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._db_path = db_path
        with self._conn() as conn:
            conn.execute(_CREATE_TABLE)
            for idx in _CREATE_INDEXES:
                conn.execute(idx)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, record: SessionRecord) -> None:
        """Upsert a session record by session_id."""
        with self._conn() as conn:
            conn.execute(_UPSERT, _serialize(record))

    def get(self, session_id: str) -> SessionRecord | None:
        """Retrieve a single session by ID."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return _deserialize(row) if row else None

    def get_by_vehicle(self, vehicle_id: str, limit: int = 100) -> list[SessionRecord]:
        """All sessions for a vehicle, newest first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE vehicle_id = ? "
                "ORDER BY recorded_at DESC LIMIT ?",
                (vehicle_id, limit),
            ).fetchall()
        return [_deserialize(r) for r in rows]

    def get_recent(self, limit: int = 20) -> list[SessionRecord]:
        """Most recently ingested sessions."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY ingested_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_deserialize(r) for r in rows]

    def get_trend(self, vehicle_id: str, pid: str, limit: int = 50) -> list[dict]:
        """
        Longitudinal trend for a single PID across sessions of a vehicle.

        Returns list of {recorded_at, mean, min, max} sorted by recorded_at ascending,
        for the most recent `limit` sessions that contain the pid.
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT recorded_at, pid_stats FROM sessions "
                "WHERE vehicle_id = ? "
                "ORDER BY recorded_at DESC LIMIT ?",
                (vehicle_id, limit),
            ).fetchall()

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

    def count_by_vehicle(self) -> dict[str, int]:
        """Session count grouped by vehicle_id."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT vehicle_id, COUNT(*) as cnt FROM sessions GROUP BY vehicle_id"
            ).fetchall()
        return {r["vehicle_id"]: r["cnt"] for r in rows}

    def summary(self) -> dict:
        """Overall store statistics."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            vehicles = conn.execute(
                "SELECT COUNT(DISTINCT vehicle_id) FROM sessions"
            ).fetchone()[0]
            date_row = conn.execute(
                "SELECT MIN(recorded_at), MAX(recorded_at) FROM sessions"
            ).fetchone()
        return {
            "total_sessions": total,
            "unique_vehicles": vehicles,
            "date_range": {
                "earliest": date_row[0] or "",
                "latest":   date_row[1] or "",
            },
        }
