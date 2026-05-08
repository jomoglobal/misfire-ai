"""
MisfireAI MCP Server — 4 atomic tools for the diagnostic pipeline.

Tools:
  ingest_file         — parse a CSV log file → normalized PID snapshot
  decode_vin          — VIN → vehicle metadata via NHTSA API
  lookup_tsb          — VIN + symptom → TSBs and recalls via NHTSA
  score_vehicle_health — normalized snapshot → per-system health scores (0–1)

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
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MisfireAI")

# ---------------------------------------------------------------------------
# Column name maps — translate source-specific headers to canonical PID names
# ---------------------------------------------------------------------------

# carOBD (Toyota Etios / generic ELM327 uppercase)
_CAROBD_MAP = {
    "ENGINE_RPM": "RPM",
    "ENGINE_LOAD": "LOAD",
    "COOLANT_TEMPERATURE": "ECT",
    "SHORT_TERM_FUEL_TRIM_BANK_1": "STFT_B1",
    "LONG_TERM_FUEL_TRIM_BANK_1": "LTFT_B1",
    "SHORT_TERM_FUEL_TRIM_BANK_2": "STFT_B2",
    "LONG_TERM_FUEL_TRIM_BANK_2": "LTFT_B2",
    "INTAKE_MANIFOLD_PRESSURE": "MAP",
    "MAF": "MAF",
    "INTAKE_AIR_TEMP": "IAT",
    "VEHICLE_SPEED": "VSS",
    "THROTTLE": "THROTTLE",
    "TIMING_ADVANCE": "TIMING_ADV",
    "CATALYST_TEMPERATURE_BANK1_SENSOR1": "CAT_TEMP_B1S1",
    "CATALYST_TEMPERATURE_BANK1_SENSOR2": "CAT_TEMP_B1S2",
    "ENGINE_RUN_TINE": "RUN_TIME",
}

# Car Scanner exports (BMW 335i — verbose human-readable headers)
_CARSCANNER_MAP = {
    "Engine RPM (rpm)": "RPM",
    "Engine RPM x1000 (rpm)": None,  # duplicate, skip
    "Calculated engine load value (%)": "LOAD",
    "Engine coolant temperature (℉)": "ECT_F",  # Fahrenheit — converted below
    "Short term fuel % trim - Bank 1 (%)": "STFT_B1",
    "Long term fuel % trim - Bank 1 (%)": "LTFT_B1",
    "Short term fuel % trim - Bank 2 (%)": "STFT_B2",
    "Long term fuel % trim - Bank 2 (%)": "LTFT_B2",
    "Intake air temperature (℉)": "IAT_F",
    "Intake manifold absolute pressure (psi)": "MAP_PSI",
    "Vehicle speed (mph)": "VSS_MPH",
    "Timing advance (°)": "TIMING_ADV",
    "Calculated boost (psi)": "BOOST_PSI",
}

# Isay Gerard / cephasax (Spanish headers — translated)
_ISAY_MAP = {
    "RPM del motor": "RPM",
    "Carga calculada del motor ": "LOAD",
    "Temperatura del líquido de enfriamiento del motor": "ECT",
    "Ajuste de combustible a corto plazo (Banco 1) ": "STFT_B1",
    "Ajuste de combustible a largo plazo (Banco 1)": "LTFT_B1",
    "SHORT TERM FUEL TRIM BANK 1": "STFT_B1",
    "SHORT TERM FUEL TRIM BANK 2": "STFT_B2",
    "LONG TERM FUEL TRIM BANK 2": "LTFT_B2",
    "ENGINE_COOLANT_TEMP": "ECT",
    "ENGINE_RPM": "RPM",
    "ENGINE_LOAD": "LOAD",
    "MAF": "MAF",
    "SPEED": "VSS",
    "THROTTLE_POS": "THROTTLE",
    "TIMING_ADVANCE": "TIMING_ADV",
    "TROUBLE_CODES": "DTCs",
}

_ALL_MAPS = [_CAROBD_MAP, _CARSCANNER_MAP, _ISAY_MAP]

KNOWN_PID_ALIASES: dict[str, str] = {}
for m in _ALL_MAPS:
    for src, canon in m.items():
        if canon:
            KNOWN_PID_ALIASES[src.strip()] = canon

# Rollover sentinels — ELM327 artifacts to flag
ROLLOVER_SENTINELS: dict[str, list[float]] = {
    "ECT":    [255.0],
    "MAP":    [255.0],
    "STFT_B1": [-96.0, -100.0],
    "STFT_B2": [-96.0, -100.0],
}

# Expected healthy ranges for scoring
HEALTHY_RANGES: dict[str, tuple[float, float]] = {
    "STFT_B1":  (-5.0,  5.0),
    "STFT_B2":  (-5.0,  5.0),
    "LTFT_B1":  (-5.0,  5.0),
    "LTFT_B2":  (-5.0,  5.0),
    "ECT":      (75.0, 110.0),  # broad operating range — 75°C min (still warming) to 110°C
    "TIMING_ADV": (-5.0, 45.0),  # idle can be low/negative; cruise can be high
    "CAT_TEMP_B1S1": (300.0, 850.0),  # cat needs 300°C+ to be active; >850 is concerning
}

SATURATION_LIMITS: dict[str, float] = {
    "STFT_B1": 25.0,
    "STFT_B2": 25.0,
    "LTFT_B1": 25.0,
    "LTFT_B2": 25.0,
}


# ---------------------------------------------------------------------------
# Tool 1 — ingest_file
# ---------------------------------------------------------------------------

@mcp.tool()
def ingest_file(file_path: str, source: str = "auto", max_rows: int = 500) -> str:
    """
    Parse a CSV log file from any supported source and return a normalized
    PID snapshot as JSON.

    Supported sources: car_scanner, carobd, cephasax, isay_gerard, sample, auto.
    auto-detects the format from column headers.

    Returns a JSON object with:
      - source: detected or provided source name
      - row_count: number of data rows read
      - pids: dict of canonical PID name → {mean, min, max, last, std, unit}
      - dtcs: list of DTC codes found (if any)
      - warnings: list of data quality issues detected
    """
    if not os.path.exists(file_path):
        return json.dumps({"error": f"File not found: {file_path}"})

    try:
        # Detect delimiter
        with open(file_path, newline="", encoding="utf-8", errors="replace") as f:
            sample = f.read(2048)
        delimiter = ";" if sample.count(";") > sample.count(",") else ","

        with open(file_path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            raw_cols = reader.fieldnames or []
            rows = []
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                rows.append(row)

        if not rows:
            return json.dumps({"error": "File is empty or has no data rows"})

        # Build alias lookup from actual columns
        col_map: dict[str, str] = {}
        for col in raw_cols:
            stripped = col.strip()
            # Direct alias match
            if stripped in KNOWN_PID_ALIASES:
                col_map[col] = KNOWN_PID_ALIASES[stripped]
                continue
            # Fuzzy: strip units in parens and retry
            bare = re.sub(r'\s*[\(\[].*?[\)\]]', '', stripped).strip()
            if bare in KNOWN_PID_ALIASES:
                col_map[col] = KNOWN_PID_ALIASES[bare]

        if not col_map:
            return json.dumps({
                "error": "No recognizable OBD2 columns found",
                "columns_seen": raw_cols[:20],
            })

        # Detect source if auto
        detected_source = source
        if source == "auto":
            col_set = set(raw_cols)
            if any("℉" in c or "mph" in c or "psi" in c for c in col_set):
                detected_source = "car_scanner"
            elif any("Ajuste" in c or "RPM del" in c for c in col_set):
                detected_source = "isay_gerard"
            elif "SHORT TERM FUEL TRIM BANK 1" in col_set:
                detected_source = "cephasax"
            elif "ENGINE_RPM" in col_set or "ENGINE_RPM ()" in col_set:
                detected_source = "carobd"
            else:
                detected_source = "unknown"

        # Accumulate numeric values per canonical PID
        accum: dict[str, list[float]] = {}
        dtc_set: set[str] = set()
        warnings: list[str] = []

        for row in rows:
            for raw_col, canon in col_map.items():
                val_str = row.get(raw_col, "").strip()
                if not val_str:
                    continue

                # DTCs column — collect codes
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

                # Unit conversions
                if canon == "ECT_F":
                    num = (num - 32) * 5 / 9
                    canon = "ECT"
                elif canon == "IAT_F":
                    num = (num - 32) * 5 / 9
                    canon = "IAT"
                elif canon == "MAP_PSI":
                    num = num * 6.89476
                    canon = "MAP"
                elif canon == "VSS_MPH":
                    num = num * 1.60934
                    canon = "VSS"
                elif canon == "BOOST_PSI":
                    num = num * 6.89476
                    canon = "BOOST"

                if canon not in accum:
                    accum[canon] = []
                accum[canon].append(num)

        # Build PID summary stats
        pids: dict[str, Any] = {}
        for pid, vals in accum.items():
            if not vals:
                continue
            mean_v = statistics.mean(vals)
            last_v = vals[-1]
            min_v = min(vals)
            max_v = max(vals)
            std_v = statistics.stdev(vals) if len(vals) > 1 else 0.0

            # Flag rollover sentinels
            sentinels = ROLLOVER_SENTINELS.get(pid, [])
            if last_v in sentinels or (std_v == 0 and last_v in [0.0, 255.0, 65535.0]):
                warnings.append(
                    f"{pid}: value {last_v} with std={std_v:.2f} — likely ELM327 rollover artifact"
                )

            pids[pid] = {
                "mean":  round(mean_v, 3),
                "min":   round(min_v, 3),
                "max":   round(max_v, 3),
                "last":  round(last_v, 3),
                "std":   round(std_v, 3),
            }

        return json.dumps({
            "source":    detected_source,
            "file":      os.path.basename(file_path),
            "row_count": len(rows),
            "pids":      pids,
            "dtcs":      sorted(dtc_set),
            "warnings":  warnings,
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
        "vin":          vin,
        "make":         fields.get("Make", ""),
        "model":        fields.get("Model", ""),
        "year":         fields.get("Model Year", ""),
        "engine":       fields.get("Engine Model", "") or fields.get("Displacement (L)", ""),
        "displacement": fields.get("Displacement (L)", ""),
        "fuel_type":    fields.get("Fuel Type - Primary", ""),
        "cylinders":    fields.get("Engine Number of Cylinders", ""),
        "drive_type":   fields.get("Drive Type", ""),
        "plant_country": fields.get("Plant Country", ""),
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
                "campaign": r.get("NHTSACampaignNumber", ""),
                "component": r.get("Component", ""),
                "summary": r.get("Summary", ""),
                "consequence": r.get("Consequence", ""),
                "remedy": r.get("Remedy", ""),
            }
            for r in recalls[:5]
        ]
        results["recall_count"] = len(recalls)
    except Exception as e:
        results["recalls"] = []
        results["recall_error"] = str(e)

    # NHTSA complaints — filter by keyword if symptom provided
    try:
        # Decode VIN first to get make/model/year for complaints lookup
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

            # Filter by symptom or DTC keywords if provided
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
                    "date": c.get("dateOfIncident", ""),
                    "component": c.get("components", ""),
                    "summary": c.get("summary", "")[:300],
                    "crash": c.get("crash", False),
                    "fire": c.get("fire", False),
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
      3. Presence check — penalizes missing expected PIDs
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
        score = max(0.0, 1.0 - (deviation / half_span))
        return round(score, 3)

    def _ltft_score(pid: str) -> tuple[float | None, str]:
        if pid not in pids:
            return None, "absent"
        mean_val = pids[pid]["mean"]
        saturation = SATURATION_LIMITS.get(pid, 25.0)
        score = round(max(0.0, 1.0 - (abs(mean_val) / saturation)), 3)
        direction = "lean" if mean_val > 0 else "rich"
        note = f"{mean_val:+.1f}% mean ({direction})"
        return score, note

    # --- Fueling system ---
    fuel_scores = []
    fuel_notes = []

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

    if fuel_scores:
        fuel_score = round(statistics.mean(fuel_scores), 3)
        method = "fuel_trim_trending"
    else:
        fuel_score = None
        method = "absent"

    scores["fueling"] = {
        "score":  fuel_score,
        "method": method,
        "detail": fuel_notes,
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
    timing_score = _range_score("TIMING_ADV")
    if timing_score is not None:
        timing_mean = pids["TIMING_ADV"]["mean"]
        timing_std  = pids["TIMING_ADV"]["std"]
        timing_note = f"Timing advance mean {timing_mean:.1f}°, std {timing_std:.1f}°"
        timing_summary = (
            "Timing normal" if timing_score >= 0.7
            else f"Timing retard detected — possible knock or ignition issue ({timing_mean:.0f}°)"
        )
    else:
        timing_note = "TIMING_ADV absent"
        timing_summary = "No timing advance data"

    scores["ignition"] = {
        "score":   timing_score,
        "method":  "baseline_deviation" if timing_score is not None else "absent",
        "detail":  [timing_note],
        "summary": timing_summary,
    }

    # --- Catalyst ---
    cat_score = _range_score("CAT_TEMP_B1S1")
    if cat_score is not None:
        cat_mean = pids["CAT_TEMP_B1S1"]["mean"]
        cat_summary = (
            "Catalyst temp normal" if cat_score >= 0.7
            else f"Catalyst temp out of range ({cat_mean:.0f}°C) — check for misfire or fuel richness"
        )
    else:
        cat_summary = "No catalyst temp data"

    scores["catalyst"] = {
        "score":   cat_score,
        "method":  "baseline_deviation" if cat_score is not None else "absent",
        "detail":  [f"CAT_TEMP_B1S1 mean {pids['CAT_TEMP_B1S1']['mean']:.0f}°C"] if cat_score is not None else ["absent"],
        "summary": cat_summary,
    }

    # --- Overall ---
    valid_scores = [v["score"] for v in scores.values() if v["score"] is not None]
    overall = round(statistics.mean(valid_scores), 3) if valid_scores else None

    return json.dumps({
        "overall_score": overall,
        "systems": scores,
        "dtcs_present": dtcs,
        "data_warnings": warnings,
        "scoring_note": (
            "Scores are 0.0–1.0. Method: fuel_trim_trending for fueling; "
            "baseline_deviation for cooling/ignition/catalyst. "
            "Mode 06 margin scoring not available — no Mode 06 data in this session."
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
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
