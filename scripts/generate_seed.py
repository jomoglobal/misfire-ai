#!/usr/bin/env python3
"""
Generate BMW IJE0S seed data for the Railway demo.

Usage:
  python scripts/generate_seed.py [--datalogs-dir PATH] [--out PATH]

Defaults:
  --datalogs-dir  /mnt/c/Users/GLOBAL_HP/Documents/Vehicles/2009 bmw 335i/datalogs/
  --out           data/sample/bmw-ije0s-seed.json

Reads all *.csv files recursively, calls ingest_file() + score_vehicle_health()
per file, and writes a JSON array of SessionRecord-equivalent dicts.

Files with < 5 rows are skipped. Parse errors are logged to stderr and skipped.
The script is idempotent — re-running overwrites the output file.
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Allow running from repo root without installing the package
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.mcp_server import ingest_file, score_vehicle_health
from tools.session_store import parse_mhd_filename

MIN_ROWS = 5
VEHICLE_ID = "IJE0S"
SOURCE = "mhd"

DEFAULT_DATALOGS = (
    "/mnt/c/Users/GLOBAL_HP/Documents/Vehicles/2009 bmw 335i/datalogs/"
)
DEFAULT_OUT = str(REPO_ROOT / "data" / "sample" / "bmw-ije0s-seed.json")


def _recorded_at_from_path(file_path: str) -> str:
    """Extract recorded_at from MHD filename; fall back to file mtime."""
    meta = parse_mhd_filename(os.path.basename(file_path))
    if meta.get("recorded_at"):
        return meta["recorded_at"]
    mtime = os.path.getmtime(file_path)
    return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description="Generate BMW IJE0S seed JSON")
    parser.add_argument("--datalogs-dir", default=DEFAULT_DATALOGS)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    datalogs_dir = Path(args.datalogs_dir)
    if not datalogs_dir.exists():
        print(f"ERROR: datalogs dir not found: {datalogs_dir}", file=sys.stderr)
        sys.exit(1)

    csv_files = sorted(datalogs_dir.rglob("*.csv"))
    total = len(csv_files)
    print(f"Found {total} CSV files in {datalogs_dir}")

    records = []
    skipped = 0
    errors = 0

    for i, csv_path in enumerate(csv_files, 1):
        if i % 50 == 0 or i == total:
            print(f"  [{i}/{total}] processed={len(records)} skipped={skipped} errors={errors}")

        file_path = str(csv_path)

        try:
            snapshot_json = ingest_file(file_path, source="mhd")
            snapshot = json.loads(snapshot_json)
        except Exception as e:
            print(f"  ERROR ingest {csv_path.name}: {e}", file=sys.stderr)
            errors += 1
            continue

        if "error" in snapshot:
            print(f"  SKIP {csv_path.name}: {snapshot['error']}", file=sys.stderr)
            skipped += 1
            continue

        row_count = snapshot.get("row_count", 0)
        if row_count < MIN_ROWS:
            skipped += 1
            continue

        try:
            health_json = score_vehicle_health(snapshot_json)
            health = json.loads(health_json)
        except Exception as e:
            print(f"  ERROR score {csv_path.name}: {e}", file=sys.stderr)
            errors += 1
            continue

        if "error" in health:
            print(f"  SCORE_ERR {csv_path.name}: {health['error']}", file=sys.stderr)
            errors += 1
            continue

        recorded_at = _recorded_at_from_path(file_path)
        session_meta = snapshot.get("session_meta", {})

        overall_score = health.get("overall_score")
        systems = health.get("systems", {})
        system_scores = {k: v.get("score") for k, v in systems.items()} if systems else {}

        record = {
            "session_id":       str(uuid.uuid4()),
            "vehicle_id":       VEHICLE_ID,
            "source":           SOURCE,
            "file_path":        "",
            "file_name":        csv_path.name,
            "recorded_at":      recorded_at,
            "ingested_at":      datetime.now(tz=timezone.utc).isoformat(),
            "row_count":        row_count,
            "pids_present":     list(snapshot.get("pids", {}).keys()),
            "families_present": list(snapshot.get("families", {}).keys()),
            "pid_stats":        snapshot.get("pids", {}),
            "dtcs":             snapshot.get("dtcs", []),
            "warnings":         snapshot.get("warnings", []),
            "session_meta":     session_meta,
            "overall_score":    overall_score,
            "system_scores":    system_scores,
        }
        records.append(record)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(records, f, indent=2)

    print(f"\nDone.")
    print(f"  Processed: {len(records)}")
    print(f"  Skipped:   {skipped}  (< {MIN_ROWS} rows)")
    print(f"  Errors:    {errors}")
    print(f"  Output:    {out_path}  ({out_path.stat().st_size / 1024 / 1024:.1f} MB)")

    if len(records) < 100:
        print(f"\nWARNING: only {len(records)} records — expected 300+", file=sys.stderr)


if __name__ == "__main__":
    main()
