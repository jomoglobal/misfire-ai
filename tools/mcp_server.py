"""
MisfireAI MCP Server — 6 atomic tools for the diagnostic pipeline.

Tools:
  ingest_file          — parse a CSV log file → normalized PID snapshot
  decode_vin           — VIN → vehicle metadata via NHTSA API
  lookup_tsb           — VIN + symptom → TSBs and recalls via NHTSA
  score_vehicle_health — normalized snapshot → per-system health scores (0–1)
  ingest_batch         — ingest all CSVs in a folder, persist to session store
  query_trends         — longitudinal PID trend for a vehicle from the store

Run:  python -m tools.mcp_server
      or: mcp run tools/mcp_server.py
"""

import csv
import json
import math
import os
import re
import statistics
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from tools.schema import (
    SOURCE_COLUMN_MAP,
    UNIT_CONVERSIONS,
    ROLLOVER_SENTINELS,
    HEALTHY_RANGES,
    SATURATION_LIMITS,
    SIGNAL_SCHEMA,
    detect_source,
)
from tools.session_store import SessionStore, SessionRecord, parse_mhd_filename

mcp = FastMCP("MisfireAI")

REPO_ROOT = Path(__file__).resolve().parent.parent
_SESSION_DB = str(REPO_ROOT / "data" / "sessions.db")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_units(header: str) -> str:
    """Remove trailing unit bracket/paren from a column header."""
    return re.sub(r'\s*[\[\(][^\]\)]*[\]\)]\s*$', '', header).strip()


def _is_mhd_version_col(col: str) -> bool:
    """Detect the MHD version string column that appears at the end of the header row."""
    s = col.strip()
    return s.startswith("MHD ") or s.startswith("MHD\t") or re.match(r'^MHD\s', s) is not None


_SENTINEL = object()  # distinguishes "key absent" from "key maps to None"


def _build_col_map(source: str, raw_cols: list[str]) -> dict[str, str | None]:
    """
    Map raw column headers → canonical names for the given source.

    Lookup order:
      1. Exact (source, col) in SOURCE_COLUMN_MAP
      2. Exact (source, col.strip()) in SOURCE_COLUMN_MAP
      3. Stripped unit variant: (source, _strip_units(col))

    Returns {raw_col: canonical_name | None}.
    None means explicitly skipped (e.g. duplicate column).
    Columns not found in any lookup are omitted from the result.
    """
    col_map: dict[str, str | None] = {}
    for col in raw_cols:
        if _is_mhd_version_col(col):
            continue
        stripped = col.strip()
        bare = _strip_units(stripped)

        for key in ((source, col), (source, stripped), (source, bare)):
            val = SOURCE_COLUMN_MAP.get(key, _SENTINEL)
            if val is not _SENTINEL:
                # val is either a canonical name string or None (explicit skip)
                col_map[col] = val  # type: ignore[assignment]
                break

    return col_map


def _derive_knock_retard(accum: dict[str, list[float]]) -> float | None:
    """Return the minimum (most negative) per-cylinder timing correction in the session."""
    cyl_pids = [f"TIMING_CYL{i}" for i in range(1, 7)]
    all_vals: list[float] = []
    for pid in cyl_pids:
        if pid in accum:
            all_vals.extend(accum[pid])
    return min(all_vals) if all_vals else None


def _families_from_pids(pid_names: list[str]) -> dict[str, list[str]]:
    """Return {family: [canonical_names...]} for the given pids present."""
    families: dict[str, list[str]] = {}
    for pid in pid_names:
        sig = SIGNAL_SCHEMA.get(pid)
        if sig:
            fam = sig["family"]
            families.setdefault(fam, []).append(pid)
    return families


def _read_csv(file_path: str) -> tuple[list[str], list[dict]]:
    """Read a CSV file handling UTF-8 BOM and auto-detecting delimiter."""
    with open(file_path, newline="", encoding="utf-8-sig", errors="replace") as f:
        sample = f.read(4096)
    delimiter = ";" if sample.count(";") > sample.count(",") else ","

    with open(file_path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        raw_cols = reader.fieldnames or []
        rows = [row for row in reader]

    return raw_cols, rows


def _ingest_rows(
    source: str,
    raw_cols: list[str],
    rows: list[dict],
    max_rows: int = 500,
) -> tuple[dict[str, list[float]], set[str], list[str]]:
    """
    Core ingestion loop. Returns (accum, dtc_set, warnings).

    accum: canonical_name → list of float values
    dtc_set: set of DTC code strings
    warnings: list of data quality warning strings
    """
    col_map = _build_col_map(source, raw_cols)
    accum: dict[str, list[float]] = {}
    dtc_set: set[str] = set()
    warnings: list[str] = []

    for row in rows[:max_rows]:
        for raw_col, canon in col_map.items():
            if canon is None:
                continue
            val_str = row.get(raw_col, "").strip()
            if not val_str:
                continue

            # Meta string columns
            if canon in ("DTCs", "VEHICLE_MARK", "VEHICLE_MODEL", "VEHICLE_YEAR"):
                if canon == "DTCs":
                    codes = [c.strip() for c in re.split(r'[,\n\|]', val_str) if c.strip()]
                    for code in codes:
                        if re.match(r'^[PBCU][0-9A-F]{4}$', code, re.IGNORECASE):
                            dtc_set.add(code.upper())
                continue

            try:
                num = float(val_str)
            except ValueError:
                continue

            # Apply unit conversion if needed
            conv = UNIT_CONVERSIONS.get((source, canon))
            if conv is not None:
                num = conv(num)

            accum.setdefault(canon, []).append(num)

    # Rollover sentinel checks
    for pid, vals in accum.items():
        if not vals:
            continue
        sentinels = ROLLOVER_SENTINELS.get(pid, [])
        last_v = vals[-1]
        std_v = statistics.stdev(vals) if len(vals) > 1 else 0.0
        if last_v in sentinels or (std_v == 0 and last_v in [0.0, 255.0, 65535.0]):
            warnings.append(
                f"{pid}: value {last_v} with std={std_v:.2f} — likely ELM327 rollover artifact"
            )

    return accum, dtc_set, warnings


def _build_pid_stats(accum: dict[str, list[float]]) -> dict[str, Any]:
    pids: dict[str, Any] = {}
    for pid, vals in accum.items():
        if not vals:
            continue
        mean_v = statistics.mean(vals)
        last_v = vals[-1]
        min_v = min(vals)
        max_v = max(vals)
        std_v = statistics.stdev(vals) if len(vals) > 1 else 0.0
        pids[pid] = {
            "mean": round(mean_v, 3),
            "min":  round(min_v, 3),
            "max":  round(max_v, 3),
            "last": round(last_v, 3),
            "std":  round(std_v, 3),
        }
    return pids


# ---------------------------------------------------------------------------
# Tool 1 — ingest_file
# ---------------------------------------------------------------------------

@mcp.tool()
def ingest_file(file_path: str, source: str = "auto", max_rows: int = 500) -> str:
    """
    Parse a CSV log file from any supported source and return a normalized
    PID snapshot as JSON.

    Supported sources: car_scanner, carobd, cephasax, isay_gerard, mhd, auto.
    auto-detects the format from column headers.

    Returns a JSON object with:
      - source: detected or provided source name
      - file: base filename
      - row_count: number of data rows read
      - pids: dict of canonical PID name → {mean, min, max, last, std}
      - families: dict of family_name → list of canonical PIDs present
      - dtcs: list of DTC codes found (if any)
      - warnings: list of data quality issues detected
      - session_meta: dict with tune/fuel_mix/vehicle_id for MHD files; {} otherwise
    """
    if not os.path.exists(file_path):
        return json.dumps({"error": f"File not found: {file_path}"})

    try:
        raw_cols, rows = _read_csv(file_path)

        if not rows:
            return json.dumps({"error": "File is empty or has no data rows"})

        # Filter out MHD version string column from raw_cols before detection
        visible_cols = [c for c in raw_cols if not _is_mhd_version_col(c)]

        # Detect source
        detected_source = source if source != "auto" else detect_source(visible_cols)

        accum, dtc_set, warnings = _ingest_rows(
            detected_source, raw_cols, rows, max_rows=max_rows
        )

        # Derive KNOCK_RETARD from per-cylinder timing corrections
        knock = _derive_knock_retard(accum)
        if knock is not None:
            accum["KNOCK_RETARD"] = [knock]

        if not accum and not dtc_set:
            return json.dumps({
                "error": "No recognizable OBD2 columns found",
                "source_detected": detected_source,
                "columns_seen": visible_cols[:20],
            })

        pids = _build_pid_stats(accum)
        families = _families_from_pids(list(pids.keys()))

        # MHD session metadata from filename
        session_meta: dict = {}
        if detected_source == "mhd":
            session_meta = parse_mhd_filename(os.path.basename(file_path))

        return json.dumps({
            "source":       detected_source,
            "file":         os.path.basename(file_path),
            "row_count":    min(len(rows), max_rows),
            "pids":         pids,
            "families":     families,
            "dtcs":         sorted(dtc_set),
            "warnings":     warnings,
            "session_meta": session_meta,
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Tool 2 — decode_vin
# ---------------------------------------------------------------------------

@mcp.tool()
def decode_vin(vin: str) -> str:
    """
    Decode a VIN using the NHTSA vPIC API.
    Returns make, model, year, engine, plant country, and any errors reported
    by NHTSA for the given VIN.
    """
    vin = vin.strip().upper()
    if len(vin) != 17:
        return json.dumps({"error": f"VIN must be 17 characters, got {len(vin)}: '{vin}'"})

    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{vin}?format=json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return json.dumps({"error": f"NHTSA API request failed: {e}"})

    results = data.get("Results", [])
    fields = {r["Variable"]: r["Value"] for r in results if r.get("Value")}

    error_code = fields.get("Error Code", "0")
    error_text = fields.get("Error Text", "")

    decoded = {
        "vin":              vin,
        "make":             fields.get("Make", ""),
        "model":            fields.get("Model", ""),
        "year":             fields.get("Model Year", ""),
        "engine":           fields.get("Engine Model", "") or fields.get("Displacement (L)", ""),
        "displacement":     fields.get("Displacement (L)", ""),
        "fuel_type":        fields.get("Fuel Type - Primary", ""),
        "cylinders":        fields.get("Engine Number of Cylinders", ""),
        "drive_type":       fields.get("Drive Type", ""),
        "plant_country":    fields.get("Plant Country", ""),
        "nhtsa_error_code": error_code,
        "nhtsa_error_text": error_text if error_code != "0" else "",
    }

    return json.dumps(decoded, indent=2)


# ---------------------------------------------------------------------------
# Tool 3 — lookup_tsb
# ---------------------------------------------------------------------------

@mcp.tool()
def lookup_tsb(vin: str, symptom: str = "", dtc: str = "") -> str:
    """
    Look up Technical Service Bulletins and recalls for a vehicle via NHTSA.

    Provide at least one of: symptom (plain text description) or dtc (e.g. P0420).
    Returns matching complaints, investigations, and recalls from NHTSA.
    """
    vin = vin.strip().upper()
    results: dict[str, Any] = {"vin": vin, "symptom": symptom, "dtc": dtc}

    # NHTSA recalls by VIN
    try:
        recall_url = f"https://api.nhtsa.gov/recalls/recallsByVehicleId?vin={vin}"
        with urllib.request.urlopen(recall_url, timeout=10) as resp:
            recall_data = json.loads(resp.read().decode())
        recalls = recall_data.get("results", [])
        results["recalls"] = [
            {
                "campaign":    r.get("NHTSACampaignNumber", ""),
                "component":   r.get("Component", ""),
                "summary":     r.get("Summary", ""),
                "consequence": r.get("Consequence", ""),
                "remedy":      r.get("Remedy", ""),
            }
            for r in recalls[:5]
        ]
        results["recall_count"] = len(recalls)
    except Exception as e:
        results["recalls"] = []
        results["recall_error"] = str(e)

    # NHTSA complaints — filter by keyword if symptom provided
    try:
        vin_url = f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{vin}?format=json"
        with urllib.request.urlopen(vin_url, timeout=10) as resp:
            vin_data = json.loads(resp.read().decode())
        vin_fields = {r["Variable"]: r["Value"] for r in vin_data.get("Results", []) if r.get("Value")}
        make  = vin_fields.get("Make", "").upper()
        model = vin_fields.get("Model", "").upper()
        year  = vin_fields.get("Model Year", "")

        if make and model and year:
            complaints_url = (
                f"https://api.nhtsa.gov/complaints/complaintsByVehicle"
                f"?make={urllib.parse.quote(make)}&model={urllib.parse.quote(model)}&modelYear={year}"
            )
            with urllib.request.urlopen(complaints_url, timeout=10) as resp:
                complaints_data = json.loads(resp.read().decode())
            all_complaints = complaints_data.get("results", [])

            keyword = (symptom + " " + dtc).lower().strip()
            if keyword:
                filtered = [
                    c for c in all_complaints
                    if keyword in (c.get("summary", "") + c.get("components", "")).lower()
                ]
            else:
                filtered = all_complaints

            results["complaints"] = [
                {
                    "date":      c.get("dateOfIncident", ""),
                    "component": c.get("components", ""),
                    "summary":   c.get("summary", "")[:300],
                    "crash":     c.get("crash", False),
                    "fire":      c.get("fire", False),
                }
                for c in filtered[:5]
            ]
            results["complaint_count"] = len(all_complaints)
            results["matching_complaints"] = len(filtered)
        else:
            results["complaints"] = []
            results["complaints_note"] = "Could not decode VIN to look up complaints"

    except Exception as e:
        results["complaints"] = []
        results["complaint_error"] = str(e)

    return json.dumps(results, indent=2)


# ---------------------------------------------------------------------------
# Tool 4 — score_vehicle_health
# ---------------------------------------------------------------------------

@mcp.tool()
def score_vehicle_health(snapshot_json: str) -> str:
    """
    Score vehicle health from a normalized PID snapshot (output of ingest_file).

    Returns a per-system health score from 0.0 (critical) to 1.0 (healthy),
    the scoring method used, and a plain-language summary per system.

    Scoring methods (applied in priority order per system):
      1. Fuel trim trending — LTFT drift scored against saturation limit
      2. Statistical baseline deviation — mean vs. healthy range midpoint
      3. AFR scoring — wideband lambda centered on 14.7 AFR stoichiometric
      4. Knock retard — per-cylinder minimum correction (MHD only)
      5. Presence check — penalizes missing expected PIDs
    """
    try:
        snapshot = json.loads(snapshot_json)
    except Exception as e:
        return json.dumps({"error": f"Invalid snapshot JSON: {e}"})

    pids = snapshot.get("pids", {})
    warnings = snapshot.get("warnings", [])
    dtcs = snapshot.get("dtcs", [])

    scores: dict[str, Any] = {}

    def _range_score(pid: str, use_mean: bool = True) -> float | None:
        if pid not in pids:
            return None
        val = pids[pid]["mean"] if use_mean else pids[pid]["last"]
        lo, hi = HEALTHY_RANGES.get(pid, (None, None))
        if lo is None:
            return None
        mid = (lo + hi) / 2
        half_span = (hi - lo) / 2
        deviation = abs(val - mid)
        return round(max(0.0, 1.0 - (deviation / half_span)), 3)

    def _ltft_score(pid: str) -> tuple[float | None, str]:
        if pid not in pids:
            return None, "absent"
        mean_val = pids[pid]["mean"]
        saturation = SATURATION_LIMITS.get(pid, 25.0)
        score = round(max(0.0, 1.0 - (abs(mean_val) / saturation)), 3)
        direction = "lean" if mean_val > 0 else "rich"
        return score, f"{mean_val:+.1f}% mean ({direction})"

    def _afr_score(pid: str) -> tuple[float | None, str]:
        """Score AFR relative to stoichiometric 14.7 — healthy range 13.5–15.5."""
        if pid not in pids:
            return None, "absent"
        mean_val = pids[pid]["mean"]
        stoich = 14.7
        half_span = 1.2  # (15.5 - 13.5) / 2
        deviation = abs(mean_val - stoich)
        score = round(max(0.0, 1.0 - (deviation / half_span)), 3)
        direction = "lean" if mean_val > stoich else "rich"
        return score, f"{pid}: {mean_val:.2f} AFR ({direction})"

    # --- Fueling system ---
    fuel_scores: list[float] = []
    fuel_notes: list[str] = []

    for pid in ["LTFT_B1", "LTFT_B2"]:
        s, note = _ltft_score(pid)
        if s is not None:
            fuel_scores.append(s)
            fuel_notes.append(f"{pid}: {note}")

    for pid in ["STFT_B1", "STFT_B2"]:
        s = _range_score(pid)
        if s is not None:
            fuel_scores.append(s)
            stft_mean = pids[pid]["mean"]
            fuel_notes.append(f"{pid}: {stft_mean:+.1f}% mean")

    for pid in ["AFR_B1", "AFR_B2"]:
        s, note = _afr_score(pid)
        if s is not None:
            fuel_scores.append(s)
            fuel_notes.append(note)

    if fuel_scores:
        fuel_score = round(statistics.mean(fuel_scores), 3)
        method = "fuel_trim_trending"
    else:
        fuel_score = None
        method = "absent"

    scores["fueling"] = {
        "score":   fuel_score,
        "method":  method,
        "detail":  fuel_notes,
        "summary": _fueling_summary(fuel_score, fuel_notes),
    }

    # --- Cooling system ---
    ect_score = _range_score("ECT")
    if ect_score is not None:
        ect_mean = pids["ECT"]["mean"]
        ect_note = f"ECT mean {ect_mean:.1f}°C"
        ect_summary = (
            "Normal operating temperature" if ect_score >= 0.7
            else f"Temperature outside healthy range ({ect_mean:.0f}°C)"
        )
    else:
        ect_note = "ECT absent"
        ect_summary = "No coolant temp data"

    scores["cooling"] = {
        "score":   ect_score,
        "method":  "baseline_deviation" if ect_score is not None else "absent",
        "detail":  [ect_note],
        "summary": ect_summary,
    }

    # --- Ignition ---
    timing_scores: list[float] = []
    timing_notes: list[str] = []

    timing_score = _range_score("TIMING_ADV")
    if timing_score is not None:
        timing_mean = pids["TIMING_ADV"]["mean"]
        timing_std  = pids["TIMING_ADV"]["std"]
        timing_scores.append(timing_score)
        timing_notes.append(f"TIMING_ADV mean {timing_mean:.1f}°, std {timing_std:.1f}°")

    # KNOCK_RETARD scoring: values more negative than -2° are concerning
    # score = max(0, 1 + knock_retard/10) where knock_retard is the minimum correction
    if "KNOCK_RETARD" in pids:
        knock_val = pids["KNOCK_RETARD"]["mean"]  # single-value derived stat
        knock_score = round(max(0.0, 1.0 + knock_val / 10.0), 3)
        timing_scores.append(knock_score)
        timing_notes.append(f"KNOCK_RETARD min={knock_val:.1f}°")

    if timing_scores:
        ignition_score = round(statistics.mean(timing_scores), 3)
        ignition_method = "baseline_deviation"
        ignition_summary = (
            "Timing normal" if ignition_score >= 0.7
            else f"Timing/knock concern detected — possible knock or ignition issue"
        )
    else:
        ignition_score = None
        ignition_method = "absent"
        ignition_summary = "No timing data"

    scores["ignition"] = {
        "score":   ignition_score,
        "method":  ignition_method,
        "detail":  timing_notes if timing_notes else ["TIMING_ADV absent"],
        "summary": ignition_summary,
    }

    # --- Catalyst ---
    cat_score = _range_score("CAT_TEMP_B1S1")
    if cat_score is not None:
        cat_mean = pids["CAT_TEMP_B1S1"]["mean"]
        cat_summary = (
            "Catalyst temp normal" if cat_score >= 0.7
            else f"Catalyst temp out of range ({cat_mean:.0f}°C) — check for misfire or fuel richness"
        )
        cat_detail = [f"CAT_TEMP_B1S1 mean {cat_mean:.0f}°C"]
    else:
        cat_summary = "No catalyst temp data"
        cat_detail = ["absent"]

    scores["catalyst"] = {
        "score":   cat_score,
        "method":  "baseline_deviation" if cat_score is not None else "absent",
        "detail":  cat_detail,
        "summary": cat_summary,
    }

    # --- Overall ---
    valid_scores = [v["score"] for v in scores.values() if v["score"] is not None]
    overall = round(statistics.mean(valid_scores), 3) if valid_scores else None

    return json.dumps({
        "overall_score": overall,
        "systems":       scores,
        "dtcs_present":  dtcs,
        "data_warnings": warnings,
        "scoring_note": (
            "Scores are 0.0–1.0. Methods: fuel_trim_trending for fueling (LTFT/STFT/AFR); "
            "baseline_deviation for cooling/ignition/catalyst. "
            "KNOCK_RETARD is the most negative per-cylinder timing correction (MHD only)."
        ),
    }, indent=2)


def _fueling_summary(score: float | None, notes: list[str]) -> str:
    if score is None:
        return "No fuel trim data available"
    if score >= 0.85:
        return "Fueling normal — trims within healthy range"
    if score >= 0.65:
        return f"Mild fueling deviation — monitor trend. {'; '.join(notes)}"
    if score >= 0.40:
        return f"Significant fueling deviation — schedule inspection. {'; '.join(notes)}"
    return f"Severe fueling deviation — service soon. {'; '.join(notes)}"


# ---------------------------------------------------------------------------
# Tool 5 — ingest_batch
# ---------------------------------------------------------------------------

@mcp.tool()
def ingest_batch(
    folder_path: str,
    source: str = "auto",
    vehicle_id: str = "",
    max_files: int = 50,
) -> str:
    """
    Ingest all CSV files in a folder, save each as a SessionRecord to the
    session store, and return a summary.

    Returns JSON with:
      - processed: count of files successfully ingested
      - errors: count of files that failed
      - vehicle_id: the vehicle_id used (or "unknown")
      - families_seen: list of signal families encountered across all files
      - date_range: {earliest, latest} recorded_at values
      - pid_coverage: {pid: pct_sessions_present} — fraction of sessions with each PID
    """
    if not os.path.isdir(folder_path):
        return json.dumps({"error": f"Not a directory: {folder_path}"})

    csv_files = sorted(
        p for p in Path(folder_path).iterdir()
        if p.suffix.lower() == ".csv"
    )[:max_files]

    if not csv_files:
        return json.dumps({"error": "No CSV files found in folder"})

    store = SessionStore(_SESSION_DB)

    processed = 0
    errors = 0
    all_families: set[str] = set()
    all_pids: dict[str, int] = {}  # pid → count of sessions where present
    recorded_dates: list[str] = []

    for csv_path in csv_files:
        try:
            snapshot_json = ingest_file(str(csv_path), source=source)
            snapshot = json.loads(snapshot_json)

            if "error" in snapshot:
                errors += 1
                continue

            detected_source = snapshot.get("source", "unknown")
            session_meta = snapshot.get("session_meta", {})

            # Determine vehicle_id
            vid = vehicle_id
            if not vid:
                if detected_source == "mhd" and session_meta.get("vehicle_id"):
                    vid = session_meta["vehicle_id"]
                else:
                    vid = "unknown"

            # Record time
            recorded_at = ""
            if detected_source == "mhd" and session_meta.get("recorded_at"):
                recorded_at = session_meta["recorded_at"]
            else:
                try:
                    mtime = os.path.getmtime(str(csv_path))
                    from datetime import datetime, timezone
                    recorded_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
                except Exception:
                    pass

            pids_present = list(snapshot.get("pids", {}).keys())
            families_dict = snapshot.get("families", {})
            families_present = list(families_dict.keys())

            for fam in families_present:
                all_families.add(fam)
            for pid in pids_present:
                all_pids[pid] = all_pids.get(pid, 0) + 1

            if recorded_at:
                recorded_dates.append(recorded_at)

            record = SessionRecord(
                vehicle_id=      vid,
                source=          detected_source,
                file_path=       str(csv_path),
                file_name=       csv_path.name,
                recorded_at=     recorded_at,
                row_count=       snapshot.get("row_count", 0),
                pids_present=    pids_present,
                families_present=families_present,
                pid_stats=       snapshot.get("pids", {}),
                dtcs=            snapshot.get("dtcs", []),
                warnings=        snapshot.get("warnings", []),
                session_meta=    session_meta,
            )
            store.save(record)
            processed += 1

        except Exception:
            errors += 1

    pid_coverage = {
        pid: round(count / processed, 3) if processed else 0.0
        for pid, count in all_pids.items()
    }

    recorded_dates_sorted = sorted(d for d in recorded_dates if d)

    return json.dumps({
        "processed":    processed,
        "errors":       errors,
        "vehicle_id":   vehicle_id or "unknown",
        "families_seen": sorted(all_families),
        "date_range": {
            "earliest": recorded_dates_sorted[0] if recorded_dates_sorted else "",
            "latest":   recorded_dates_sorted[-1] if recorded_dates_sorted else "",
        },
        "pid_coverage": pid_coverage,
    }, indent=2)


# ---------------------------------------------------------------------------
# Tool 6 — query_trends
# ---------------------------------------------------------------------------

@mcp.tool()
def query_trends(vehicle_id: str, pid: str, limit: int = 50) -> str:
    """
    Return longitudinal trend data for a single PID across sessions of a vehicle.

    Calls the session store and returns a JSON list of:
      [{recorded_at: str, mean: float, min: float, max: float}, ...]
    sorted chronologically, for up to `limit` sessions.

    Useful for plotting STFT drift, LTFT trending, boost deviation over time, etc.
    """
    store = SessionStore(_SESSION_DB)
    trend = store.get_trend(vehicle_id=vehicle_id, pid=pid, limit=limit)
    return json.dumps(trend, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
