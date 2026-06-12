"""
MisfireAI FastAPI Demo UI — Catch → Enrich → Separate → Compound pipeline.

Run:
    uvicorn app:app --reload --port 8000
"""

import json
import os
import secrets
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, Form, UploadFile, File, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

from tools.mcp_server import ingest_file, decode_vin, lookup_tsb, score_vehicle_health
from tools.session_store import SessionStore, SessionRecord, parse_mhd_filename
from pipeline.vehicles import get_vehicle_by_id, build_vehicle_from_meta, list_vehicle_ids

REPO_ROOT = Path(__file__).parent
SESSION_DB = str(REPO_ROOT / "data" / "sessions.db")

# Public demo sample — committed to the repo so it exists on a clean deploy.
# The carOBD/external datasets are gitignored and absent on Railway, so the
# demo must default to a file that ships with the repo.
DEMO_SAMPLE = str(REPO_ROOT / "data" / "sample" / "2009-BMW-335i-2026-04-15 13-15-01.csv")
DEMO_VIN = "WBAPN73579A395571"  # 2009 BMW 335i — pre-filled for the public demo

# Local/dev default keeps the larger external dataset when present, but falls
# back to the committed BMW sample so the app never points at a missing file.
_LOCAL_SAMPLE = REPO_ROOT / "data" / "external" / "carOBD" / "obdiidata" / "drive1.csv"
DEFAULT_SAMPLE = str(_LOCAL_SAMPLE) if _LOCAL_SAMPLE.exists() else DEMO_SAMPLE

# DEMO_MODE locks the public deployment: upload disabled, BMW data forced,
# rate guard active. Set DEMO_MODE=true on Railway; leave unset locally.
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")

# Rate guard tunables (only enforced when DEMO_MODE is on)
DEMO_RUNS_PER_IP_PER_DAY = int(os.getenv("DEMO_RUNS_PER_IP_PER_DAY", "5"))
DEMO_RUNS_GLOBAL_PER_DAY = int(os.getenv("DEMO_RUNS_GLOBAL_PER_DAY", "100"))

app = FastAPI(title="MisfireAI")


# ---------------------------------------------------------------------------
# Inline HITL email sender (no blocking server)
# ---------------------------------------------------------------------------

def _send_hitl_email(
    recipient: str,
    urgency: str,
    vehicle_make: str,
    vehicle_model: str,
    vehicle_year: str,
    session_id: str,
    overall_score,
    system_scores: dict,
    dtcs: list,
    assessment: str,
    approve_url: str,
    reject_url: str,
) -> bool:
    """Send repair brief via SendGrid. Returns True if sent successfully."""
    api_key    = os.getenv("SENDGRID_API_KEY", "")
    from_email = os.getenv("HITL_FROM_EMAIL", "alerts@misfire.ai")
    if not api_key:
        return False

    urgency_color = {
        "CRITICAL": "#ff2222", "HIGH": "#ff6622",
        "MEDIUM": "#f5a623",   "LOW": "#aaaaaa", "NORMAL": "#44ff88",
    }.get(urgency, "#aaaaaa")

    systems_rows = ""
    for system, info in system_scores.items():
        score = info.get("score") if isinstance(info, dict) else info
        summary = info.get("summary", "") if isinstance(info, dict) else ""
        if score is None:
            bar_color, score_display = "#555", "N/A"
        elif score >= 0.75:
            bar_color, score_display = "#44ff88", f"{score:.2f}"
        elif score >= 0.50:
            bar_color, score_display = "#f5a623", f"{score:.2f}"
        else:
            bar_color, score_display = "#ff4444", f"{score:.2f}"
        systems_rows += (
            f"<tr>"
            f"<td style='padding:8px;color:#ccc;text-transform:capitalize;'>{system}</td>"
            f"<td style='padding:8px;color:{bar_color};font-weight:bold;'>{score_display}</td>"
            f"<td style='padding:8px;color:#aaa;font-size:13px;'>{summary}</td>"
            f"</tr>"
        )

    dtc_block = ""
    if dtcs:
        dtc_list = "  ".join(
            f"<code style='background:#1a1a2e;padding:2px 6px;border-radius:4px;"
            f"color:#f5a623'>{d}</code>" for d in dtcs
        )
        dtc_block = (
            f"<div style='padding:16px 32px;border-bottom:1px solid #30363d;'>"
            f"<p style='margin:12px 0'><strong style='color:#f5a623'>Active DTCs:</strong>"
            f" {dtc_list}</p></div>"
        )

    html_body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="background:#0d1117;color:#e8e8e8;font-family:Arial,sans-serif;padding:0;margin:0;">
  <div style="max-width:620px;margin:40px auto;background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden;">
    <div style="background:#1e3a5f;padding:24px 32px;border-bottom:2px solid #4a9eff;">
      <h1 style="margin:0;color:#4a9eff;font-size:22px;">MisfireAI — Repair Brief</h1>
      <p style="margin:6px 0 0;color:#aaa;font-size:14px;">{vehicle_year} {vehicle_make} {vehicle_model} &nbsp;·&nbsp; {session_id}</p>
    </div>
    <div style="padding:20px 32px;border-bottom:1px solid #30363d;">
      <span style="background:{urgency_color}22;border:1px solid {urgency_color};color:{urgency_color};
                   padding:6px 16px;border-radius:20px;font-weight:bold;font-size:14px;">{urgency}</span>
    </div>
    <div style="padding:20px 32px;border-bottom:1px solid #30363d;">
      <h3 style="margin:0 0 12px;color:#e8e8e8;font-size:15px;">System Health Scores</h3>
      <table style="width:100%;border-collapse:collapse;">
        <thead><tr style="border-bottom:1px solid #30363d;">
          <th style="padding:8px;text-align:left;color:#666;font-size:12px;">SYSTEM</th>
          <th style="padding:8px;text-align:left;color:#666;font-size:12px;">SCORE</th>
          <th style="padding:8px;text-align:left;color:#666;font-size:12px;">SUMMARY</th>
        </tr></thead>
        <tbody>{systems_rows}</tbody>
      </table>
    </div>
    {dtc_block}
    <div style="padding:20px 32px;border-bottom:1px solid #30363d;">
      <h3 style="margin:0 0 10px;color:#e8e8e8;font-size:15px;">Agent Assessment</h3>
      <p style="margin:0;color:#ccc;font-size:14px;line-height:1.6;">
        {assessment[:600]}{"..." if len(assessment) > 600 else ""}
      </p>
    </div>
    <div style="padding:28px 32px;text-align:center;">
      <p style="margin:0 0 20px;color:#aaa;font-size:14px;">
        Review the assessment above and approve or reject this repair brief.<br>
        <strong style="color:#e8e8e8;">Your decision will be logged with a timestamp.</strong>
      </p>
      <a href="{approve_url}" style="background:#44ff88;color:#0d1117;padding:14px 36px;border-radius:8px;
              font-weight:bold;font-size:15px;text-decoration:none;margin-right:16px;">Approve</a>
      <a href="{reject_url}" style="background:#ff4444;color:#fff;padding:14px 36px;border-radius:8px;
              font-weight:bold;font-size:15px;text-decoration:none;">Reject</a>
    </div>
    <div style="padding:16px 32px;background:#0d1117;border-top:1px solid #30363d;">
      <p style="margin:0;color:#444;font-size:12px;text-align:center;">
        MisfireAI · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ·
        This brief requires owner approval before any action is taken.
      </p>
    </div>
  </div>
</body></html>"""

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        msg = Mail(
            from_email=from_email,
            to_emails=recipient,
            subject=f"[MisfireAI] {urgency} — {vehicle_year} {vehicle_make} {vehicle_model} Repair Brief",
            html_content=html_body,
        )
        sg = SendGridAPIClient(api_key)
        sg.send(msg)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# SSE pipeline generator
# ---------------------------------------------------------------------------

def _sse(stage: str, data: dict) -> str:
    return f"data: {json.dumps({'stage': stage, 'data': data})}\n\n"


def _pipeline_generator(
    file_path: str,
    vin: str,
    email: str,
    vehicle_id_override: str,
):
    """Yields SSE events for each pipeline stage."""
    snapshot_json = None
    snapshot = None
    scores = None
    overall = None
    vehicle_meta: dict = {}
    tsb_results: dict = {}

    # ── CATCH ──────────────────────────────────────────────────────────────
    try:
        snapshot_json = ingest_file(file_path)
        snapshot = json.loads(snapshot_json)
        if "error" in snapshot:
            yield _sse("error", {"stage": "catch", "message": snapshot["error"]})
            return

        pids = snapshot.get("pids", {})
        families = snapshot.get("families", {})

        # All PIDs with schema metadata, sorted by diagnostic importance
        _FAMILY_ORDER = ["fueling", "ignition", "boost", "thermal", "catalyst",
                         "fuel_supply", "exhaust", "composition", "drivetrain", "meta"]
        try:
            from tools.schema import SIGNAL_SCHEMA
            pids_summary = []
            for pid_name, stats in pids.items():
                sig = SIGNAL_SCHEMA.get(pid_name, {})
                unit   = sig.get("unit", "")
                family = sig.get("family", "")
                pids_summary.append({
                    "name":   pid_name,
                    "mean":   stats.get("mean"),
                    "min":    stats.get("min"),
                    "max":    stats.get("max"),
                    "std":    stats.get("std"),
                    "unit":   unit,
                    "family": family,
                    "_forder": _FAMILY_ORDER.index(family) if family in _FAMILY_ORDER else 99,
                })
            pids_summary.sort(key=lambda x: (x["_forder"], x["name"]))
            for p in pids_summary:
                del p["_forder"]
        except Exception:
            pids_summary = []

        yield _sse("catch", {
            "source":       snapshot.get("source", "unknown"),
            "row_count":    snapshot.get("row_count", 0),
            "pid_count":    len(pids),
            "dtcs":         snapshot.get("dtcs", []),
            "warnings":     snapshot.get("warnings", []),
            "families":     list(families.keys()),
            "session_meta": snapshot.get("session_meta", {}),
            "pids_summary": pids_summary,
        })

    except Exception as e:
        yield _sse("error", {"stage": "catch", "message": str(e)})
        return

    # ── ENRICH ─────────────────────────────────────────────────────────────
    try:
        if vin and len(vin.strip()) == 17:
            vehicle_meta = json.loads(decode_vin(vin.strip()))
            try:
                dtcs = snapshot.get("dtcs", [])
                symptom = f"fuel trim {dtcs[0]}" if dtcs else "fuel trim anomaly"
                tsb_results = json.loads(lookup_tsb(vin.strip(), symptom=symptom))
            except Exception:
                tsb_results = {}
            # Build human-readable engine string
            engine_raw = vehicle_meta.get("engine", "")
            displacement = vehicle_meta.get("displacement", "")
            cylinders = vehicle_meta.get("cylinders", "")
            fuel_type_raw = vehicle_meta.get("fuel_type", "")
            try:
                disp_f = float(displacement)
                disp_str = f"{disp_f:.1f}L" if disp_f else ""
            except (ValueError, TypeError):
                disp_str = ""
            cyl_str = f"{cylinders}-cyl" if cylinders else ""
            fuel_str = fuel_type_raw.split("/")[0].strip().title() if fuel_type_raw else ""
            if engine_raw and not engine_raw.replace(".", "").isdigit():
                engine_display = engine_raw
            elif disp_str or cyl_str or fuel_str:
                engine_display = " ".join(filter(None, [disp_str, cyl_str, fuel_str]))
            else:
                engine_display = ""

            yield _sse("enrich", {
                "make":             vehicle_meta.get("make", ""),
                "model":            vehicle_meta.get("model", ""),
                "year":             vehicle_meta.get("year", ""),
                "engine":           engine_display,
                "displacement":     displacement,
                "cylinders":        cylinders,
                "fuel_type":        fuel_type_raw,
                "drive_type":       vehicle_meta.get("drive_type", ""),
                "plant_country":    vehicle_meta.get("plant_country", ""),
                "recall_count":     tsb_results.get("recall_count", 0),
                "complaint_count":  tsb_results.get("complaint_count", 0),
                "recalls":          tsb_results.get("recalls", []),
                "complaints":       tsb_results.get("complaints", []),
            })
        else:
            yield _sse("enrich", {"skipped": True})
    except Exception as e:
        yield _sse("enrich", {"skipped": True, "error": str(e)})

    # ── SEPARATE ───────────────────────────────────────────────────────────
    try:
        scores_json = score_vehicle_health(snapshot_json)
        scores = json.loads(scores_json)
        if "error" in scores:
            yield _sse("error", {"stage": "separate", "message": scores["error"]})
            return
        overall = scores.get("overall_score")
        yield _sse("separate", {
            "overall_score": overall,
            "systems":       scores.get("systems", {}),
        })
    except Exception as e:
        yield _sse("error", {"stage": "separate", "message": str(e)})
        return

    # ── COMPOUND ───────────────────────────────────────────────────────────
    compound_result = None
    agent_urgency = "UNKNOWN"

    if not os.getenv("OPENAI_API_KEY"):
        yield _sse("compound", {
            "urgency":    "UNKNOWN",
            "assessment": "OpenAI API key not configured — compound stage skipped.\n\n"
                          "Set OPENAI_API_KEY in .env to enable AI diagnostic assessment.",
        })
    else:
        try:
            from pipeline.agent import run_diagnostic_agent, AgentInput

            # Determine vehicle_id for agent
            vid_agent = vehicle_id_override or ""
            session_meta = snapshot.get("session_meta", {})
            if not vid_agent and session_meta.get("vehicle_id"):
                vid_agent = session_meta["vehicle_id"]
            if not vid_agent:
                vid_agent = "unknown"

            # Use registered config if available, otherwise build from VIN meta
            vehicle_cfg = get_vehicle_by_id(vid_agent)
            if not vehicle_cfg and vehicle_meta:
                vehicle_cfg = build_vehicle_from_meta(vid_agent, vehicle_meta)
            elif not vehicle_cfg:
                vehicle_cfg = get_vehicle_by_id("bmw-335i-2009")

            pids = snapshot.get("pids", {})
            agent_snapshot = {pid: vals["mean"] for pid, vals in pids.items()}
            if snapshot.get("dtcs"):
                agent_snapshot["DTCs"] = snapshot["dtcs"]

            agent_input = AgentInput(
                vehicle_id=vid_agent,
                snapshot=agent_snapshot,
                scenario=f"web_ui:{Path(file_path).name}",
                vehicle_override=vehicle_cfg,
            )
            output = run_diagnostic_agent(agent_input)
            agent_urgency = output.urgency
            compound_result = output

            yield _sse("compound", {
                "urgency":    output.urgency,
                "assessment": output.assessment,
            })
        except Exception as e:
            yield _sse("compound", {
                "urgency":    "UNKNOWN",
                "assessment": f"Agent error: {str(e)}",
            })

    # ── HITL ───────────────────────────────────────────────────────────────
    if email and agent_urgency in ("CRITICAL", "HIGH", "MEDIUM") and compound_result:
        try:
            token = secrets.token_urlsafe(24)
            host = os.getenv("HITL_CALLBACK_HOST", "http://localhost")
            port = os.getenv("HITL_CALLBACK_PORT", "8741")
            base = f"{host}:{port}"
            approve_url = f"{base}/hitl/approve?token={token}"
            reject_url  = f"{base}/hitl/reject?token={token}"

            sent = _send_hitl_email(
                recipient=email,
                urgency=agent_urgency,
                vehicle_make=vehicle_meta.get("make", "Unknown"),
                vehicle_model=vehicle_meta.get("model", "Unknown"),
                vehicle_year=vehicle_meta.get("year", ""),
                session_id=f"web_ui:{Path(file_path).name}",
                overall_score=overall,
                system_scores=scores.get("systems", {}) if scores else {},
                dtcs=snapshot.get("dtcs", []),
                assessment=compound_result.assessment,
                approve_url=approve_url,
                reject_url=reject_url,
            )
            yield _sse("hitl", {
                "triggered":    True,
                "reason":       f"Urgency {agent_urgency} — repair brief sent",
                "email":        email,
                "email_sent":   sent,
                "approve_url":  approve_url,
                "reject_url":   reject_url,
            })
        except Exception as e:
            yield _sse("hitl", {"triggered": False, "reason": f"HITL error: {str(e)}"})
    elif agent_urgency in ("LOW", "NORMAL"):
        yield _sse("hitl", {
            "triggered": False,
            "reason": f"Urgency {agent_urgency} — HITL not required",
        })
    else:
        yield _sse("hitl", {"triggered": False, "reason": "No email provided or urgency below threshold"})

    # ── PERSIST & DONE ─────────────────────────────────────────────────────
    try:
        session_meta = snapshot.get("session_meta", {})
        pids = snapshot.get("pids", {})
        detected_source = snapshot.get("source", "unknown")

        vid = vehicle_id_override or ""
        if not vid and session_meta.get("vehicle_id"):
            vid = session_meta["vehicle_id"]
        if not vid and vehicle_meta.get("make"):
            vid = (
                f"{vehicle_meta.get('make','').lower()}-"
                f"{vehicle_meta.get('model','').lower()}-"
                f"{vehicle_meta.get('year','')}"
            ).strip("-")
        if not vid:
            vid = "unknown"

        recorded_at = ""
        if detected_source == "mhd" and session_meta.get("recorded_at"):
            recorded_at = session_meta["recorded_at"]
        else:
            try:
                import datetime as _dt
                mtime = os.path.getmtime(file_path)
                recorded_at = _dt.datetime.fromtimestamp(mtime, tz=_dt.timezone.utc).isoformat()
            except Exception:
                pass

        system_scores_flat = {}
        if scores:
            for k, v in scores.get("systems", {}).items():
                system_scores_flat[k] = v.get("score") if isinstance(v, dict) else v

        record = SessionRecord(
            vehicle_id=      vid,
            source=          detected_source,
            file_path=       file_path,
            file_name=       Path(file_path).name,
            recorded_at=     recorded_at,
            row_count=       snapshot.get("row_count", 0),
            pids_present=    list(pids.keys()),
            families_present=list(snapshot.get("families", {}).keys()),
            pid_stats=       pids,
            dtcs=            snapshot.get("dtcs", []),
            warnings=        snapshot.get("warnings", []),
            session_meta=    session_meta,
            overall_score=   overall,
            system_scores=   system_scores_flat,
        )
        store = SessionStore(SESSION_DB)
        store.save(record)
        yield _sse("done", {"session_id": record.session_id})
    except Exception as e:
        yield _sse("done", {"session_id": "", "error": str(e)})


# ---------------------------------------------------------------------------
# Demo rate guard — in-memory, only enforced when DEMO_MODE is on.
# Per-IP daily cap + global daily cap. Counters reset at UTC midnight and on
# process restart (acceptable for a demo). No external store, no dependencies.
# ---------------------------------------------------------------------------

_rate_state: dict = {
    "day": datetime.now(timezone.utc).date(),
    "global_count": 0,
    "per_ip": {},  # ip -> count for the current day
}


def _client_ip(request: Request) -> str:
    """Resolve the real client IP behind Railway's proxy."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_check(request: Request) -> Optional[str]:
    """Return an error message if this request exceeds a demo limit, else None."""
    if not DEMO_MODE:
        return None

    today = datetime.now(timezone.utc).date()
    if _rate_state["day"] != today:
        _rate_state["day"] = today
        _rate_state["global_count"] = 0
        _rate_state["per_ip"] = {}

    if _rate_state["global_count"] >= DEMO_RUNS_GLOBAL_PER_DAY:
        return (
            "The live demo has hit its daily limit. It resets at midnight UTC. "
            "Clone the repo from GitHub to run it without limits."
        )

    ip = _client_ip(request)
    ip_count = _rate_state["per_ip"].get(ip, 0)
    if ip_count >= DEMO_RUNS_PER_IP_PER_DAY:
        return (
            f"You've reached the demo limit of {DEMO_RUNS_PER_IP_PER_DAY} runs per day. "
            "It resets at midnight UTC. Clone the repo from GitHub to run it without limits."
        )
    return None


def _rate_increment(request: Request) -> None:
    if not DEMO_MODE:
        return
    ip = _client_ip(request)
    _rate_state["global_count"] += 1
    _rate_state["per_ip"][ip] = _rate_state["per_ip"].get(ip, 0) + 1


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.post("/api/analyze")
async def analyze(
    request: Request,
    file: Optional[UploadFile] = File(default=None),
    file_path: str = Form(default=""),
    vin: str = Form(default=""),
    email: str = Form(default=""),
    vehicle_id: str = Form(default=""),
    use_sample: str = Form(default="false"),
):
    # Demo guard: enforce limits and lock inputs to the BMW sample.
    if DEMO_MODE:
        limit_msg = _rate_check(request)
        if limit_msg:
            return JSONResponse({"error": limit_msg}, status_code=429)
        # Force the public demo to the committed BMW data — ignore any upload,
        # library path, or arbitrary VIN the client tries to send.
        use_sample = "true"
        file = None
        file_path = ""
        email = ""
        vin = DEMO_VIN

    use_sample_bool = use_sample.lower() in ("true", "1", "yes")
    cleanup = False

    if use_sample_bool:
        resolved_path = DEMO_SAMPLE if DEMO_MODE else DEFAULT_SAMPLE
        if not os.path.exists(resolved_path):
            return JSONResponse({"error": f"Sample file not found: {resolved_path}"}, status_code=404)
    elif file_path:
        # Library file — path already on server disk
        resolved_path = file_path
        if not os.path.exists(resolved_path):
            return JSONResponse({"error": f"File not found: {resolved_path}"}, status_code=404)
    elif file is not None and file.filename:
        suffix = Path(file.filename).suffix or ".csv"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        content = await file.read()
        tmp.write(content)
        tmp.flush()
        tmp.close()
        resolved_path = tmp.name
        cleanup = True
    else:
        return JSONResponse({"error": "No file uploaded and use_sample not set"}, status_code=400)

    file_path = resolved_path

    # Count this run against the demo limits now that it's validated and
    # about to execute (a real API spend is imminent).
    _rate_increment(request)

    def gen():
        try:
            yield from _pipeline_generator(
                file_path=file_path,
                vin=vin,
                email=email,
                vehicle_id_override=vehicle_id,
            )
        finally:
            if cleanup and os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except Exception:
                    pass

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/sessions")
def get_sessions():
    store = SessionStore(SESSION_DB)
    records = store.get_recent(20)
    result = []
    for r in records:
        result.append({
            "session_id":       r.session_id,
            "vehicle_id":       r.vehicle_id,
            "source":           r.source,
            "file_name":        r.file_name,
            "recorded_at":      r.recorded_at,
            "overall_score":    r.overall_score,
            "system_scores":    r.system_scores,
            "families_present": r.families_present,
            "row_count":        r.row_count,
        })
    return JSONResponse(result)


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    store = SessionStore(SESSION_DB)
    record = store.get(session_id)
    if not record:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    return JSONResponse({
        "session_id":       record.session_id,
        "vehicle_id":       record.vehicle_id,
        "source":           record.source,
        "file_path":        record.file_path,
        "file_name":        record.file_name,
        "recorded_at":      record.recorded_at,
        "ingested_at":      record.ingested_at,
        "row_count":        record.row_count,
        "pids_present":     record.pids_present,
        "families_present": record.families_present,
        "pid_stats":        record.pid_stats,
        "dtcs":             record.dtcs,
        "warnings":         record.warnings,
        "session_meta":     record.session_meta,
        "overall_score":    record.overall_score,
        "system_scores":    record.system_scores,
    })


@app.get("/api/trends/{vehicle_id}/{pid}")
def get_trends(vehicle_id: str, pid: str, limit: int = 200):
    store = SessionStore(SESSION_DB)
    trend = store.get_trend(vehicle_id=vehicle_id, pid=pid, limit=min(limit, 500))
    return JSONResponse(trend)


@app.get("/api/vehicles")
def get_vehicles():
    store = SessionStore(SESSION_DB)
    counts = store.count_by_vehicle()
    return JSONResponse([
        {"vehicle_id": vid, "session_count": cnt}
        for vid, cnt in counts.items()
    ])


@app.get("/api/library")
def get_library():
    """Return vehicles with their ingested sessions (file paths) for the library browser."""
    store = SessionStore(SESSION_DB)
    import sqlite3 as _sqlite3
    with store._conn() as conn:
        rows = conn.execute(
            "SELECT vehicle_id, session_id, file_name, file_path, source, recorded_at, row_count "
            "FROM sessions ORDER BY vehicle_id, recorded_at DESC"
        ).fetchall()

    vehicles: dict = {}
    for r in rows:
        vid = r["vehicle_id"]
        if vid not in vehicles:
            vehicles[vid] = {"vehicle_id": vid, "sessions": []}
        # Only include if the file still exists on disk
        fp = r["file_path"] or ""
        exists = bool(fp) and os.path.exists(fp)
        vehicles[vid]["sessions"].append({
            "session_id": r["session_id"],
            "file_name":  r["file_name"],
            "file_path":  fp,
            "source":     r["source"],
            "recorded_at": (r["recorded_at"] or "")[:10],
            "row_count":  r["row_count"],
            "available":  exists,
        })

    return JSONResponse(list(vehicles.values()))


# ---------------------------------------------------------------------------
# Analyze History endpoint
# ---------------------------------------------------------------------------

@app.get("/api/analyze-history/{vehicle_id}")
async def analyze_history(vehicle_id: str):
    """Fetch multi-session trend data for a vehicle and run an LLM longitudinal assessment."""
    if not os.getenv("OPENAI_API_KEY"):
        return JSONResponse({"error": "OpenAI API key not configured."}, status_code=503)

    HISTORY_PIDS = [
        "LTFT_B1", "STFT_B1", "LTFT_B2", "STFT_B2", "ECT", "IAT",
        "AFR_B1", "BOOST_ACTUAL", "KNOCK_RETARD", "MAP", "CAT_TEMP_B1S1",
        "RPM", "LOAD", "O2_LAMBDA_B1S1", "WGDC_B1",
    ]

    store = SessionStore(SESSION_DB)
    trend_data = {}
    for pid in HISTORY_PIDS:
        pts = store.get_trend(vehicle_id=vehicle_id, pid=pid, limit=500)
        if len(pts) >= 3:
            vals = [p["mean"] for p in pts if p.get("mean") is not None]
            if len(vals) >= 3:
                first_date = (pts[0].get("recorded_at") or "")[:10]
                last_date  = (pts[-1].get("recorded_at") or "")[:10]
                drift = (vals[-1] - vals[0]) / len(vals)
                trend_data[pid] = {
                    "sessions":   len(pts),
                    "mean":       round(sum(vals) / len(vals), 3),
                    "min":        round(min(vals), 3),
                    "max":        round(max(vals), 3),
                    "latest":     round(vals[-1], 3),
                    "drift_per_session": round(drift, 4),
                    "date_range": f"{first_date} → {last_date}",
                }

    if not trend_data:
        return JSONResponse({"error": f"No historical trend data found for vehicle '{vehicle_id}'."})

    # Build vehicle context
    vehicle_cfg = get_vehicle_by_id(vehicle_id)
    vehicle_desc = (
        f"{vehicle_cfg.year} {vehicle_cfg.make} {vehicle_cfg.model} ({vehicle_cfg.engine})"
        if vehicle_cfg else vehicle_id
    )

    trend_summary = json.dumps(trend_data, indent=2)
    system_prompt = (
        "You are an expert automotive diagnostician. Your task is to analyze long-term OBD2 "
        "signal trends for a vehicle across multiple driving sessions and identify patterns, "
        "degradation, drift, or anomalies that may indicate developing faults.\n\n"
        "For each signal, consider: is the current value healthy? Is there meaningful drift "
        "over time? Are any values outside normal operating ranges? What systems are most "
        "concerning? What should the owner watch or address?\n\n"
        "Write a plain-language assessment the vehicle owner can understand. "
        "Lead with the most important finding. Include an urgency tier: "
        "CRITICAL / HIGH / MEDIUM / LOW / NORMAL."
    )
    user_message = (
        f"Vehicle: {vehicle_desc}\n\n"
        f"Long-term signal trends ({len(trend_data)} signals, multi-session):\n"
        f"```json\n{trend_summary}\n```\n\n"
        "Provide a longitudinal health assessment."
    )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=1024,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
        )
        assessment = response.choices[0].message.content or "(no response)"
        urgency = "UNKNOWN"
        for tier in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NORMAL"]:
            if tier in assessment.upper():
                urgency = tier
                break
        return JSONResponse({"urgency": urgency, "assessment": assessment, "vehicle_id": vehicle_id})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MisfireAI — OBD2 Diagnostic Pipeline</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:      #0d1117;
    --surface: #161b22;
    --border:  #30363d;
    --blue:    #4a9eff;
    --green:   #3dba6f;
    --orange:  #f5a623;
    --purple:  #e040fb;
    --red:     #ff4444;
    --text:    #e8e8e8;
    --muted:   #8b949e;
    --radius:  10px;
  }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 15px;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* ── Top nav ── */
  .topnav {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 0 24px;
    height: 52px;
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
  }
  .topnav .logo-mark {
    width: 28px; height: 28px;
    background: linear-gradient(135deg, var(--blue), var(--purple));
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700; color: #fff;
  }
  .topnav .brand { font-weight: 700; font-size: 16px; color: var(--text); letter-spacing: -0.2px; }
  .topnav .sub   { font-size: 12px; color: var(--muted); margin-top: 1px; }
  .topnav .badge {
    margin-left: auto;
    background: #1e3a5f;
    border: 1px solid var(--blue);
    color: var(--blue);
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
  }

  /* ── Layout ── */
  .layout {
    display: flex;
    flex: 1;
    overflow: hidden;
    height: calc(100vh - 52px);
  }

  /* ── Sidebar ── */
  .sidebar {
    width: 320px;
    min-width: 320px;
    background: var(--surface);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: 20px 16px;
    gap: 16px;
  }

  .sidebar-section { display: flex; flex-direction: column; gap: 8px; }
  .sidebar-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.8px;
  }

  /* Drop zone */
  .dropzone {
    border: 2px dashed var(--border);
    border-radius: var(--radius);
    padding: 24px 16px;
    text-align: center;
    cursor: pointer;
    transition: border-color 0.2s, background 0.2s;
    background: var(--bg);
    position: relative;
  }
  .dropzone:hover, .dropzone.dragover {
    border-color: var(--blue);
    background: rgba(74, 158, 255, 0.05);
  }
  .dropzone input[type=file] {
    position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%;
  }
  .dropzone .drop-icon { font-size: 28px; margin-bottom: 6px; }
  .dropzone .drop-text { color: var(--muted); font-size: 14px; }
  .dropzone .drop-hint { color: var(--muted); font-size: 12px; margin-top: 4px; }
  .dropzone .file-selected {
    color: var(--blue);
    font-size: 13px;
    font-weight: 600;
    word-break: break-all;
  }

  /* Inputs */
  .field { display: flex; flex-direction: column; gap: 5px; }
  .field label { font-size: 13px; color: var(--muted); }
  .field input, .field select {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 7px;
    padding: 8px 12px;
    color: var(--text);
    font-size: 13px;
    outline: none;
    transition: border-color 0.2s;
    font-family: inherit;
    width: 100%;
  }
  .field input:focus, .field select:focus { border-color: var(--blue); }
  .field input::placeholder { color: var(--muted); }
  .field select option { background: var(--surface); color: var(--text); }

  /* Buttons */
  .btn {
    display: flex; align-items: center; justify-content: center; gap: 8px;
    padding: 10px 16px;
    border-radius: 8px;
    border: none;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    transition: opacity 0.15s, transform 0.1s;
    font-family: inherit;
  }
  .btn:active:not(:disabled) { transform: scale(0.98); }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-primary { background: var(--blue); color: #fff; width: 100%; }
  .btn-primary:hover:not(:disabled) { opacity: 0.9; }
  .btn-ghost {
    background: transparent;
    color: var(--blue);
    border: 1px solid var(--border);
    padding: 6px 12px;
    font-size: 13px;
  }
  .btn-ghost:hover:not(:disabled) { border-color: var(--blue); background: rgba(74,158,255,0.07); }

  /* Spinner */
  .spinner {
    width: 16px; height: 16px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    display: none;
  }
  .spinner.active { display: block; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Sessions list */
  .sessions-list { display: flex; flex-direction: column; gap: 5px; }
  .session-chip {
    display: flex; align-items: center; justify-content: space-between;
    padding: 8px 10px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 7px;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
    gap: 8px;
  }
  .session-chip:hover { border-color: var(--blue); background: rgba(74,158,255,0.05); }
  .session-chip .svid { font-size: 13px; font-weight: 600; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 160px; }
  .session-chip .sscore {
    font-size: 13px; font-weight: 700; padding: 2px 7px; border-radius: 12px; white-space: nowrap;
  }
  .session-chip .sfile { font-size: 12px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 160px; }

  /* ── Main area ── */
  .main {
    flex: 1;
    overflow-y: auto;
    padding: 24px 28px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  /* ── Pipeline progress bar ── */
  .pipeline-bar {
    display: flex;
    align-items: center;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px 20px;
    gap: 0;
  }
  .pipe-stage {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    position: relative;
  }
  .pipe-stage:not(:last-child)::after {
    content: '';
    position: absolute;
    right: 0; top: 14px;
    width: calc(100% - 40px);
    left: calc(50% + 20px);
    height: 2px;
    background: var(--border);
    transition: background 0.4s;
  }
  .pipe-stage.done:not(:last-child)::after { background: currentColor; opacity: 0.4; }
  .pipe-dot {
    width: 32px; height: 32px;
    border-radius: 50%;
    border: 2px solid var(--border);
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700;
    transition: all 0.3s;
    background: var(--bg);
    color: var(--muted);
  }
  .pipe-stage.active .pipe-dot { border-color: currentColor; animation: pulse-dot 1s infinite; }
  .pipe-stage.done .pipe-dot   { border-color: currentColor; background: currentColor; color: var(--bg); }
  @keyframes pulse-dot {
    0%, 100% { box-shadow: 0 0 0 0 currentColor; opacity: 1; }
    50% { box-shadow: 0 0 0 5px transparent; opacity: 0.85; }
  }
  .pipe-label { font-size: 12px; font-weight: 600; color: var(--muted); letter-spacing: 0.5px; }
  .pipe-stage.active .pipe-label, .pipe-stage.done .pipe-label { color: currentColor; }

  .pipe-catch   { color: var(--blue); }
  .pipe-enrich  { color: var(--green); }
  .pipe-sep     { color: var(--orange); }
  .pipe-compound{ color: var(--purple); }

  /* ── Result panels ── */
  .panel {
    background: var(--surface);
    border-radius: var(--radius);
    border: 1px solid var(--border);
    overflow: hidden;
    opacity: 0;
    transform: translateY(8px);
    transition: opacity 0.4s ease, transform 0.4s ease;
  }
  .panel.visible { opacity: 1; transform: translateY(0); }
  .panel-catch    { border-top: 3px solid var(--blue); }
  .panel-enrich   { border-top: 3px solid var(--green); }
  .panel-separate { border-top: 3px solid var(--orange); }
  .panel-compound { border-top: 3px solid var(--purple); }
  .panel-hitl     { border-top: 3px solid var(--red); }

  .panel-header {
    display: flex; align-items: center; gap: 10px;
    padding: 14px 18px;
    border-bottom: 1px solid var(--border);
  }
  .panel-icon {
    width: 26px; height: 26px;
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; color: var(--bg);
    flex-shrink: 0;
  }
  .panel-catch .panel-icon    { background: var(--blue); }
  .panel-enrich .panel-icon   { background: var(--green); }
  .panel-separate .panel-icon { background: var(--orange); }
  .panel-compound .panel-icon { background: var(--purple); }
  .panel-hitl .panel-icon     { background: var(--red); }

  .panel-title { font-size: 14px; font-weight: 700; color: var(--text); }
  .panel-subtitle { font-size: 12px; color: var(--muted); margin-left: auto; }
  .panel-body { padding: 16px 18px; display: flex; flex-direction: column; gap: 14px; }

  /* Badges / chips */
  .chip {
    display: inline-flex; align-items: center;
    padding: 3px 9px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid transparent;
  }
  .chip-blue    { background: rgba(74,158,255,0.12); color: var(--blue); border-color: rgba(74,158,255,0.25); }
  .chip-green   { background: rgba(61,186,111,0.12); color: var(--green); border-color: rgba(61,186,111,0.25); }
  .chip-orange  { background: rgba(245,166,35,0.12); color: var(--orange); border-color: rgba(245,166,35,0.25); }
  .chip-purple  { background: rgba(224,64,251,0.12); color: var(--purple); border-color: rgba(224,64,251,0.25); }
  .chip-red     { background: rgba(255,68,68,0.12); color: var(--red); border-color: rgba(255,68,68,0.25); }
  .chip-muted   { background: rgba(139,148,158,0.12); color: var(--muted); border-color: rgba(139,148,158,0.25); }

  /* Stats row */
  .stats-row { display: flex; gap: 20px; flex-wrap: wrap; }
  .stat-item { display: flex; flex-direction: column; gap: 3px; }
  .stat-val  { font-size: 22px; font-weight: 700; line-height: 1; }
  .stat-lbl  { font-size: 12px; color: var(--muted); }

  /* Tags row */
  .tags { display: flex; flex-wrap: wrap; gap: 6px; }

  /* Table */
  .data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .data-table th {
    text-align: left; padding: 6px 10px;
    color: var(--muted); font-weight: 600; font-size: 12px;
    text-transform: uppercase; letter-spacing: 0.5px;
    border-bottom: 1px solid var(--border);
  }
  .data-table td { padding: 7px 10px; border-bottom: 1px solid rgba(48,54,61,0.5); color: var(--text); }
  .data-table tr:last-child td { border-bottom: none; }
  .data-table tr:hover td { background: rgba(255,255,255,0.02); }
  .mono { font-family: "SFMono-Regular", Consolas, monospace; }

  /* Score bar */
  .score-bar-wrap { background: var(--border); border-radius: 4px; height: 6px; overflow: hidden; flex: 1; }
  .score-bar-fill { height: 100%; border-radius: 4px; transition: width 0.6s ease; }

  /* System cards grid */
  .sys-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .sys-card {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px;
    display: flex; flex-direction: column; gap: 8px;
  }
  .sys-name { font-size: 13px; font-weight: 700; text-transform: capitalize; color: var(--muted); }
  .sys-score-row { display: flex; align-items: center; gap: 8px; }
  .sys-score-val { font-size: 18px; font-weight: 700; min-width: 40px; }
  .sys-summary { font-size: 13px; color: var(--muted); line-height: 1.4; }

  /* Overall score */
  .overall-score { font-size: 52px; font-weight: 800; line-height: 1; }

  /* Assessment */
  .assessment-text {
    font-size: 14px; line-height: 1.75;
    color: #d4d8dd;
    background: var(--bg);
    border-radius: 7px;
    padding: 18px 20px;
    border: 1px solid var(--border);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  .assessment-text p { margin: 0 0 12px; }
  .assessment-text p:last-child { margin-bottom: 0; }
  .assessment-text strong { color: var(--text); font-weight: 600; }

  /* Urgency badge */
  .urgency {
    display: inline-flex; align-items: center;
    padding: 5px 14px;
    border-radius: 20px;
    font-size: 13px; font-weight: 700;
    letter-spacing: 0.5px;
    border: 1px solid transparent;
  }
  .urgency-CRITICAL { background: rgba(255,34,34,0.15); color: #ff2222; border-color: rgba(255,34,34,0.35); }
  .urgency-HIGH     { background: rgba(255,102,34,0.15); color: #ff6622; border-color: rgba(255,102,34,0.35); }
  .urgency-MEDIUM   { background: rgba(245,166,35,0.15); color: var(--orange); border-color: rgba(245,166,35,0.35); }
  .urgency-LOW      { background: rgba(139,148,158,0.15); color: var(--muted); border-color: rgba(139,148,158,0.35); }
  .urgency-NORMAL   { background: rgba(61,186,111,0.15); color: var(--green); border-color: rgba(61,186,111,0.35); }
  .urgency-UNKNOWN  { background: rgba(139,148,158,0.15); color: var(--muted); border-color: rgba(139,148,158,0.35); }

  /* HITL links */
  .hitl-links { display: flex; gap: 12px; flex-wrap: wrap; }
  .hitl-link {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 8px 16px;
    border-radius: 7px;
    font-size: 13px; font-weight: 600;
    text-decoration: none;
    transition: opacity 0.15s;
  }
  .hitl-link:hover { opacity: 0.85; }
  .hitl-link-approve { background: rgba(61,186,111,0.15); color: var(--green); border: 1px solid rgba(61,186,111,0.3); }
  .hitl-link-reject  { background: rgba(255,68,68,0.15);  color: var(--red);   border: 1px solid rgba(255,68,68,0.3); }

  /* Error banner */
  .error-banner {
    background: rgba(255,68,68,0.1);
    border: 1px solid rgba(255,68,68,0.4);
    border-radius: 8px;
    padding: 14px 18px;
    color: var(--red);
    font-size: 13px;
    display: none;
  }
  .error-banner.visible { display: block; }

  /* Divider */
  .divider { border: none; border-top: 1px solid var(--border); }

  /* Meta row */
  .meta-row { display: flex; flex-wrap: wrap; gap: 14px; }
  .meta-item { font-size: 13px; color: var(--muted); }
  .meta-item span { color: var(--text); }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #484f58; }

  /* Family color map */
  .fam-fueling  { color: var(--blue); }
  .fam-thermal  { color: var(--orange); }
  .fam-ignition { color: var(--purple); }
  .fam-drivetrain { color: var(--green); }
  .fam-catalyst { color: #ff9944; }
  .fam-boost    { color: #44ddff; }
  .fam-electrical { color: var(--muted); }

  /* PID expand toggle */
  .pid-expand-btn {
    background: none; border: 1px solid var(--border); border-radius: 6px;
    color: var(--blue); font-size: 12px; font-weight: 600; cursor: pointer;
    padding: 5px 14px; margin-top: 8px; font-family: inherit;
    transition: border-color .15s, background .15s;
  }
  .pid-expand-btn:hover { border-color: var(--blue); background: rgba(74,158,255,.07); }

  /* History panel */
  .panel-history { border-top: 3px solid #44ddff; }
  .panel-history .panel-icon { background: #44ddff; }
  .history-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px;
  }
  .spark-card {
    background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
    padding: 12px 14px; display: flex; flex-direction: column; gap: 6px;
  }
  .spark-header { display: flex; justify-content: space-between; align-items: baseline; }
  .spark-pid    { font-size: 13px; font-weight: 700; color: var(--text); }
  .spark-stats  { font-size: 11px; color: var(--muted); }
  canvas.spark  { width: 100% !important; height: 48px !important; display: block; }
  .spark-range  { font-size: 11px; color: var(--muted); display: flex; justify-content: space-between; }
  .no-history   { color: var(--muted); font-size: 13px; padding: 16px 0; }

  /* Empty state */
  .empty-state {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 12px; flex: 1; color: var(--muted); text-align: center;
    padding: 60px 20px;
  }
  .empty-icon { font-size: 48px; opacity: 0.3; }
  .empty-title { font-size: 15px; font-weight: 600; color: var(--muted); }
  .empty-sub   { font-size: 13px; color: var(--muted); opacity: 0.7; max-width: 300px; line-height: 1.5; }

  @media (max-width: 760px) {
    /* Let the whole page scroll naturally — no fixed-height clipping */
    body { min-height: 100vh; }
    .layout {
      flex-direction: column;
      height: auto;
      overflow: visible;
    }
    .sidebar {
      width: 100%;
      min-width: auto;
      height: auto;
      overflow: visible;
      border-right: none;
      border-bottom: 1px solid var(--border);
    }
    .main {
      overflow: visible;
      padding: 16px 14px;
    }
    #trendsView { padding: 16px 14px; }
    .sys-grid { grid-template-columns: 1fr; }
    .history-grid { grid-template-columns: 1fr; }
    .stats-row { gap: 12px; }
    .panel-body { padding: 12px 14px; }
    .topnav { padding: 0 14px; }
    .tab-bar { margin-right: 0; }
    .topnav .badge { display: none; }
    .topnav .sub { display: none; }
    .assessment-text { font-size: 13px; padding: 14px; }
    .trends-controls { flex-direction: column; }
  }

  /* ── Tab bar ── */
  .tab-bar {
    display: flex; gap: 2px; margin-left: auto; margin-right: 24px;
  }
  .tab-btn {
    background: none; border: none; cursor: pointer;
    padding: 6px 16px; border-radius: 6px; font-size: 12px; font-weight: 600;
    color: var(--muted); letter-spacing: 0.4px; transition: background .15s, color .15s;
  }
  .tab-btn:hover { background: rgba(255,255,255,.06); color: var(--text); }
  .tab-btn.active { background: rgba(74,158,255,.15); color: var(--blue); }

  /* ── Trends view ── */
  #trendsView { display: none; padding: 24px 28px; overflow-y: auto; flex: 1; }
  #trendsView.active { display: flex; flex-direction: column; gap: 20px; }

  .trends-controls {
    display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end;
  }
  .trends-controls .field { flex: 1; min-width: 160px; }
  .trends-controls .btn { align-self: flex-end; white-space: nowrap; }

  .chart-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 20px; flex: 1;
  }
  .chart-card h3 { font-size: 14px; font-weight: 700; color: var(--text); margin-bottom: 4px; }
  .chart-card .chart-sub { font-size: 12px; color: var(--muted); margin-bottom: 16px; }
  canvas#trendChart { width: 100% !important; height: 280px !important; display: block; }

  .trend-stats {
    display: flex; gap: 20px; flex-wrap: wrap; margin-top: 16px;
  }
  .trend-stat {
    display: flex; flex-direction: column; gap: 2px;
  }
  .trend-stat-label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
  .trend-stat-value { font-size: 18px; font-weight: 700; color: var(--text); }
  .trend-stat-value.warn { color: var(--orange); }
  .trend-stat-value.crit { color: var(--red); }

  .vehicle-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px;
  }
  .vehicle-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    padding: 14px 16px; cursor: pointer; transition: border-color .15s, background .15s;
  }
  .vehicle-card:hover { border-color: var(--blue); background: rgba(74,158,255,.06); }
  .vehicle-card.selected { border-color: var(--blue); background: rgba(74,158,255,.10); }
  .vc-id { font-size: 14px; font-weight: 700; color: var(--text); }
  .vc-count { font-size: 12px; color: var(--muted); margin-top: 3px; }

  .no-trend { color: var(--muted); font-size: 13px; text-align: center; padding: 40px 0; }
</style>
</head>
<body>

<!-- Top nav -->
<nav class="topnav">
  <div class="logo-mark">M</div>
  <div>
    <div class="brand">MisfireAI</div>
    <div class="sub">by Datronex</div>
  </div>
  <div class="tab-bar">
    <button class="tab-btn active" id="tabAnalyze" onclick="switchTab('analyze')">ANALYZE</button>
    <button class="tab-btn" id="tabTrends" onclick="switchTab('trends')">TRENDS</button>
  </div>
  <span class="badge">OBD2 DEMO</span>
</nav>

<!-- Layout -->
<div class="layout">

  <!-- Sidebar -->
  <aside class="sidebar">

    <!-- Library picker -->
    <div class="sidebar-section">
      <span class="sidebar-label">Select from Library</span>
      <div class="field">
        <label for="libVehicle">Vehicle</label>
        <select id="libVehicle" style="width:100%" onchange="onLibVehicleChange()">
          <option value="">Loading...</option>
        </select>
      </div>
      <div class="field" id="libFileRow" style="display:none">
        <label for="libFile">Log File</label>
        <select id="libFile" style="width:100%" onchange="onLibFileChange()">
          <option value="">— pick a file —</option>
        </select>
      </div>
    </div>

    <!-- Divider with label -->
    <div id="dropDivider" style="display:flex;align-items:center;gap:8px">
      <hr class="divider" style="flex:1;margin:0">
      <span style="font-size:11px;color:var(--muted);white-space:nowrap">or drop a new file</span>
      <hr class="divider" style="flex:1;margin:0">
    </div>

    <div class="sidebar-section" id="dropSection">
      <div class="dropzone" id="dropzone">
        <input type="file" id="fileInput" accept=".csv">
        <div class="drop-icon">&#128196;</div>
        <div class="drop-text" id="dropText">Drop CSV here or click to browse</div>
        <div class="drop-hint">MHD · CarScanner · CarOBD · CephaSAX · iSay Gerard</div>
      </div>
    </div>

    <div class="sidebar-section">
      <span class="sidebar-label">Options</span>
      <div class="field">
        <label for="vinInput">VIN (optional)</label>
        <input type="text" id="vinInput" maxlength="17" placeholder="17-char VIN">
      </div>
      <div class="field">
        <label for="emailInput">Owner Email (for HITL approval)</label>
        <input type="email" id="emailInput" placeholder="email address">
      </div>
    </div>

    <button class="btn btn-primary" id="runBtn" disabled>
      <div class="spinner" id="spinner"></div>
      <span id="runBtnText">Run Analysis</span>
    </button>

    <hr class="divider">

    <div class="sidebar-section">
      <span class="sidebar-label">Recent Results</span>
      <div class="sessions-list" id="sessionsList">
        <div style="color:var(--muted);font-size:13px;">Loading...</div>
      </div>
    </div>

  </aside>

  <!-- Main -->
  <main class="main" id="mainArea">

    <!-- Empty state -->
    <div class="empty-state" id="emptyState">
      <div class="empty-icon">&#128295;</div>
      <div class="empty-title">No analysis running</div>
      <div class="empty-sub">Select a vehicle and log file from the library, or drop a new CSV file, then click Run Analysis.</div>
    </div>

    <!-- Error banner -->
    <div class="error-banner" id="errorBanner"></div>

    <!-- Pipeline progress -->
    <div class="pipeline-bar" id="pipelineBar" style="display:none">
      <div class="pipe-stage pipe-catch" id="stage-catch">
        <div class="pipe-dot">1</div>
        <div class="pipe-label">CATCH</div>
      </div>
      <div class="pipe-stage pipe-enrich" id="stage-enrich">
        <div class="pipe-dot">2</div>
        <div class="pipe-label">ENRICH</div>
      </div>
      <div class="pipe-stage pipe-sep" id="stage-sep">
        <div class="pipe-dot">3</div>
        <div class="pipe-label">SEPARATE</div>
      </div>
      <div class="pipe-stage pipe-compound" id="stage-compound">
        <div class="pipe-dot">4</div>
        <div class="pipe-label">COMPOUND</div>
      </div>
    </div>

    <!-- Results panels -->
    <div id="panelCatch"    class="panel panel-catch"    style="display:none"></div>
    <div id="panelEnrich"   class="panel panel-enrich"   style="display:none"></div>
    <div id="panelSeparate" class="panel panel-separate" style="display:none"></div>
    <div id="panelCompound" class="panel panel-compound" style="display:none"></div>
    <div id="panelHITL"     class="panel panel-hitl"     style="display:none"></div>
    <div id="panelHistory"  class="panel panel-history"  style="display:none"></div>

  </main>

  <!-- Trends view (hidden until tab switch) -->
  <div id="trendsView">

    <div class="vehicle-grid" id="vehicleGrid">
      <div style="color:var(--muted);font-size:12px">Loading vehicles...</div>
    </div>

    <div class="trends-controls">
      <div class="field">
        <label for="trendVehicle">Vehicle</label>
        <select id="trendVehicle" style="width:100%">
          <option value="">— select a vehicle —</option>
        </select>
      </div>
      <div class="field">
        <label for="trendPid">Signal (PID)</label>
        <select id="trendPid" style="width:100%">
          <option value="">— select a signal —</option>
          <option value="LTFT_B1">LTFT B1 — Long-Term Fuel Trim Bank 1 (%)</option>
          <option value="STFT_B1">STFT B1 — Short-Term Fuel Trim Bank 1 (%)</option>
          <option value="LTFT_B2">LTFT B2 — Long-Term Fuel Trim Bank 2 (%)</option>
          <option value="STFT_B2">STFT B2 — Short-Term Fuel Trim Bank 2 (%)</option>
          <option value="ECT">ECT — Engine Coolant Temp (°C)</option>
          <option value="IAT">IAT — Intake Air Temp (°C)</option>
          <option value="RPM">RPM — Engine Speed</option>
          <option value="MAP">MAP — Manifold Pressure (kPa)</option>
          <option value="MAF">MAF — Mass Airflow (g/s)</option>
          <option value="LOAD">LOAD — Engine Load (%)</option>
          <option value="TIMING_ADV">TIMING_ADV — Ignition Timing (°)</option>
          <option value="CAT_TEMP_B1S1">CAT_TEMP_B1S1 — Catalyst Temp B1S1 (°C)</option>
          <option value="VSS">VSS — Vehicle Speed (km/h)</option>
          <option value="THROTTLE">THROTTLE — Throttle Position (%)</option>
          <option value="AFR_B1">AFR B1 — Air/Fuel Ratio Bank 1</option>
          <option value="BOOST_ACTUAL">BOOST — Boost Pressure (PSI)</option>
          <option value="KNOCK_RETARD">KNOCK_RETARD — Knock Retard (°)</option>
          <option value="WGDC_B1">WGDC B1 — Wastegate Duty Cycle B1 (%)</option>
          <option value="O2_LAMBDA_B1S1">O2 Lambda — Equivalence Ratio B1S1</option>
          <option value="AMB_PRESSURE">AMB_PRESSURE — Barometric Pressure (kPa)</option>
        </select>
      </div>
      <button class="btn btn-primary" id="loadTrendBtn" onclick="loadTrend()" style="height:36px">
        Plot Trend
      </button>
    </div>

    <div class="chart-card" id="chartCard" style="display:none">
      <h3 id="chartTitle">— / —</h3>
      <div class="chart-sub" id="chartSub"></div>
      <canvas id="trendChart"></canvas>
      <div class="trend-stats" id="trendStats"></div>
    </div>

    <div class="no-trend" id="noTrend">Select a vehicle and signal above, then click Plot Trend.</div>

  </div><!-- /trendsView -->

</div><!-- /layout -->

<script>
// ── State ──────────────────────────────────────────────────────────────────
const state = {
  selectedFile: null,
  useSample: false,
  running: false,
};

// ── DOM refs ───────────────────────────────────────────────────────────────
const fileInput    = document.getElementById('fileInput');
const dropzone     = document.getElementById('dropzone');
const dropText     = document.getElementById('dropText');
const loadSampleBtn= null; // removed — library picker replaces sample button
const runBtn       = document.getElementById('runBtn');
const runBtnText   = document.getElementById('runBtnText');
const spinner      = document.getElementById('spinner');
const sessionsList = document.getElementById('sessionsList');
const errorBanner  = document.getElementById('errorBanner');
const pipelineBar  = document.getElementById('pipelineBar');
const emptyState   = document.getElementById('emptyState');

// ── Utilities ──────────────────────────────────────────────────────────────
function scoreColor(s) {
  if (s === null || s === undefined) return 'var(--muted)';
  if (s >= 0.75) return 'var(--green)';
  if (s >= 0.50) return 'var(--orange)';
  return 'var(--red)';
}

function scoreChipClass(s) {
  if (s === null || s === undefined) return 'chip-muted';
  if (s >= 0.75) return 'chip-green';
  if (s >= 0.50) return 'chip-orange';
  return 'chip-red';
}

function famChipClass(fam) {
  const map = {
    fueling: 'chip-blue', thermal: 'chip-orange', ignition: 'chip-purple',
    drivetrain: 'chip-green', catalyst: 'chip-orange', boost: 'chip-blue',
    electrical: 'chip-muted',
  };
  return map[fam] || 'chip-muted';
}

function esc(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function showPanel(el) {
  el.style.display = 'block';
  requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add('visible')));
}

function setStage(stageId, status) {
  // status: 'active' | 'done'
  const el = document.getElementById('stage-' + stageId);
  if (!el) return;
  el.classList.remove('active', 'done');
  if (status) el.classList.add(status);
}

// ── File input ─────────────────────────────────────────────────────────────
fileInput.addEventListener('change', () => {
  const f = fileInput.files[0];
  if (f) {
    state.selectedFile = f;
    state.useSample = false;
    _libSelectedPath = '';
    document.getElementById('libFile').value = '';
    dropText.innerHTML = '<span class="file-selected">' + esc(f.name) + '</span>';
    runBtn.disabled = false;
  }
});

dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
dropzone.addEventListener('drop', e => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  const f = e.dataTransfer.files[0];
  if (f) {
    state.selectedFile = f;
    state.useSample = false;
    _libSelectedPath = '';
    document.getElementById('libFile').value = '';
    dropText.innerHTML = '<span class="file-selected">' + esc(f.name) + '</span>';
    runBtn.disabled = false;
  }
});

// (sample button removed — library picker handles file selection)

// ── Run Analysis ───────────────────────────────────────────────────────────
runBtn.addEventListener('click', () => {
  if (state.running) return;
  startAnalysis();
});

function resetUI() {
  emptyState.style.display = 'none';
  pipelineBar.style.display = 'flex';
  errorBanner.classList.remove('visible');
  ['catch','enrich','sep','compound'].forEach(s => setStage(s, null));
  ['panelCatch','panelEnrich','panelSeparate','panelCompound','panelHITL','panelHistory'].forEach(id => {
    const el = document.getElementById(id);
    el.style.display = 'none';
    el.classList.remove('visible');
    el.innerHTML = '';
  });
}

function setRunning(val) {
  state.running = val;
  runBtn.disabled = val;
  spinner.classList.toggle('active', val);
  runBtnText.textContent = val ? 'Running...' : 'Run Analysis';
}

function startAnalysis() {
  resetUI();
  setRunning(true);

  const vin   = (document.getElementById('vinInput')  || {value:''}).value.trim();
  const email = (document.getElementById('emailInput') || {value:''}).value.trim();
  // vehicle_id: use library vehicle dropdown if a library file is selected
  const vidEl = document.getElementById('libVehicle');
  const vid   = (vidEl && _libSelectedPath) ? vidEl.value : '';

  let fetchPromise;

  if (_libSelectedPath) {
    // Library file — send path to server, server reads it directly
    const fd = new FormData();
    fd.append('file_path', _libSelectedPath);
    fd.append('vin', vin);
    fd.append('email', email);
    fd.append('vehicle_id', vid);
    fd.append('use_sample', 'false');
    fetchPromise = fetch('/api/analyze', { method: 'POST', body: fd });
  } else if (state.selectedFile) {
    const fd = new FormData();
    fd.append('file', state.selectedFile);
    fd.append('vin', vin);
    fd.append('email', email);
    fd.append('vehicle_id', vid);
    fd.append('use_sample', 'false');
    fetchPromise = fetch('/api/analyze', { method: 'POST', body: fd });
  } else {
    showError('Select a vehicle and log file from the library, or drop a CSV file.');
    setRunning(false);
    return;
  }

  fetchPromise.then(response => {
    if (!response.ok) {
      response.json().then(j => showError(j.error || 'Request failed')).catch(() => showError('Request failed'));
      setRunning(false);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    function pump() {
      reader.read().then(({ done, value }) => {
        if (done) { setRunning(false); loadSessions(); return; }
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\\n');
        buffer = lines.pop(); // keep incomplete line
        lines.forEach(line => {
          if (line.startsWith('data: ')) {
            try {
              const evt = JSON.parse(line.slice(6));
              handleStageEvent(evt);
            } catch(e) {}
          }
        });
        pump();
      }).catch(err => {
        showError('Stream error: ' + err.message);
        setRunning(false);
      });
    }
    pump();
  }).catch(err => {
    showError('Fetch error: ' + err.message);
    setRunning(false);
  });
}

// ── Stage handlers ─────────────────────────────────────────────────────────
function handleStageEvent(evt) {
  const { stage, data } = evt;
  switch (stage) {
    case 'catch':    renderCatch(data);    setStage('catch', 'done'); setStage('enrich', 'active'); break;
    case 'enrich':   renderEnrich(data);   setStage('enrich', 'done'); setStage('sep', 'active'); break;
    case 'separate': renderSeparate(data); setStage('sep', 'done'); setStage('compound', 'active'); break;
    case 'compound': renderCompound(data); setStage('compound', 'done'); break;
    case 'hitl':     if (data.triggered) renderHITL(data); break;
    case 'done':     break;
    case 'error':    showError('[' + (data.stage || '?') + '] ' + data.message); setRunning(false); break;
  }
}

// ── CATCH panel ────────────────────────────────────────────────────────────
function renderCatch(d) {
  const el = document.getElementById('panelCatch');

  const familyChips = (d.families || []).map(f =>
    '<span class="chip ' + famChipClass(f) + '">' + esc(f) + '</span>'
  ).join(' ');

  const dtcChips = (d.dtcs || []).map(c =>
    '<span class="chip chip-orange">' + esc(c) + '</span>'
  ).join(' ');

  const warnItems = (d.warnings || []).map(w =>
    '<div style="font-size:11px;color:var(--orange);line-height:1.4;">&bull; ' + esc(w) + '</div>'
  ).join('');

  const allPids = d.pids_summary || [];
  const PREVIEW = 6;
  const buildPidRows = (pids) => pids.map(p => {
    const famClass = famChipClass(p.family);
    const stdStr   = p.std !== undefined && p.std !== null ? ' ±' + Number(p.std).toFixed(2) : '';
    return '<tr>' +
      '<td class="mono" style="font-size:12px;">' + esc(p.name) + '</td>' +
      '<td>' + (p.mean !== null && p.mean !== undefined ? Number(p.mean).toFixed(2) + stdStr : 'N/A') + '</td>' +
      '<td style="color:var(--muted)">' + esc(p.unit || '') + '</td>' +
      '<td><span class="chip ' + famClass + '" style="font-size:11px;">' + esc(p.family || '') + '</span></td>' +
      '</tr>';
  }).join('');
  const pidsRows    = buildPidRows(allPids.slice(0, PREVIEW));
  const extraRows   = allPids.length > PREVIEW ? buildPidRows(allPids.slice(PREVIEW)) : '';
  const expandLabel = allPids.length > PREVIEW
    ? '<button class="pid-expand-btn" id="pidExpandBtn" onclick="togglePidExpand(this)"'
      + ' data-collapsed="▼ Show all ' + allPids.length + ' signals">'
      + '▼ Show all ' + allPids.length + ' signals</button>'
    : '';

  const metaItems = [];
  const sm = d.session_meta || {};
  if (sm.vehicle_id) metaItems.push('<div class="meta-item">Vehicle ID: <span>' + esc(sm.vehicle_id) + '</span></div>');
  if (sm.tune)       metaItems.push('<div class="meta-item">Tune: <span>' + esc(sm.tune) + '</span></div>');
  if (sm.fuel_mix)   metaItems.push('<div class="meta-item">Fuel mix: <span>' + esc(sm.fuel_mix) + '</span></div>');

  el.innerHTML =
    '<div class="panel-header">' +
      '<div class="panel-icon">C</div>' +
      '<div class="panel-title">CATCH &mdash; Signal Ingestion</div>' +
      '<div class="panel-subtitle"><span class="chip chip-blue">' + esc(d.source || 'unknown') + '</span></div>' +
    '</div>' +
    '<div class="panel-body">' +
      '<div class="stats-row">' +
        '<div class="stat-item"><div class="stat-val" style="color:var(--blue)">' + (d.row_count||0) + '</div><div class="stat-lbl">Rows</div></div>' +
        '<div class="stat-item"><div class="stat-val" style="color:var(--blue)">' + (d.pid_count||0) + '</div><div class="stat-lbl">PIDs</div></div>' +
        (d.dtcs && d.dtcs.length ? '<div class="stat-item"><div class="stat-val" style="color:var(--orange)">' + d.dtcs.length + '</div><div class="stat-lbl">DTCs</div></div>' : '') +
      '</div>' +
      (familyChips ? '<div><div class="sidebar-label" style="margin-bottom:6px;">Signal Families</div><div class="tags">' + familyChips + '</div></div>' : '') +
      (pidsRows ? '<div><div class="sidebar-label" style="margin-bottom:6px;">Signals Captured</div>'
        + '<table class="data-table" id="pidTable"><thead><tr><th>Signal</th><th>Mean ± Std</th><th>Unit</th><th>Family</th></tr></thead>'
        + '<tbody id="pidBodyTop">' + pidsRows + '</tbody>'
        + '<tbody id="pidBodyExtra" style="display:none">' + extraRows + '</tbody>'
        + '</table>' + expandLabel + '</div>' : '') +
      (dtcChips ? '<div><div class="sidebar-label" style="margin-bottom:6px;">Fault Codes</div><div class="tags">' + dtcChips + '</div></div>' : '') +
      (warnItems ? '<div><div class="sidebar-label" style="margin-bottom:6px;">Data Warnings</div>' + warnItems + '</div>' : '') +
      (metaItems.length ? '<div class="meta-row">' + metaItems.join('') + '</div>' : '') +
    '</div>';

  showPanel(el);
}

// ── ENRICH panel ───────────────────────────────────────────────────────────
function renderEnrich(d) {
  const el = document.getElementById('panelEnrich');

  let body;
  if (d.skipped) {
    body = '<div style="color:var(--muted);font-size:13px;">No VIN provided &mdash; NHTSA lookup skipped.</div>';
    if (d.error) body += '<div style="color:var(--red);font-size:12px;margin-top:4px;">' + esc(d.error) + '</div>';
  } else {
    const vehicle = [d.year, d.make, d.model].filter(Boolean).join(' ');

    // Build extra detail chips (drive type, country)
    const extraChips = [
      d.drive_type ? '<span class="chip chip-muted">' + esc(d.drive_type) + '</span>' : '',
      d.plant_country ? '<span class="chip chip-muted">Made in ' + esc(d.plant_country) + '</span>' : '',
    ].join('');

    // Recalls section
    let recallsHtml = '';
    if (d.recalls && d.recalls.length > 0) {
      const rows = d.recalls.map(r =>
        '<div style="margin-bottom:10px;padding:8px 10px;background:rgba(220,38,38,0.08);border-left:3px solid var(--red);border-radius:4px;">' +
          '<div style="font-size:12px;font-weight:600;color:var(--red);margin-bottom:3px;">' + esc(r.campaign || '') + ' &mdash; ' + esc(r.component || '') + '</div>' +
          (r.summary ? '<div style="font-size:12px;color:#ccc;line-height:1.5;">' + esc(r.summary) + '</div>' : '') +
          (r.consequence ? '<div style="font-size:11px;color:var(--orange);margin-top:3px;">Consequence: ' + esc(r.consequence) + '</div>' : '') +
        '</div>'
      ).join('');
      recallsHtml =
        '<div style="margin-top:12px;">' +
          '<div style="font-size:12px;font-weight:600;color:var(--red);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px;">Active Recalls</div>' +
          rows +
        '</div>';
    }

    // Complaints section
    let complaintsHtml = '';
    if (d.complaints && d.complaints.length > 0) {
      const rows = d.complaints.map(c =>
        '<div style="margin-bottom:8px;padding:8px 10px;background:rgba(245,166,35,0.07);border-left:3px solid var(--orange);border-radius:4px;">' +
          '<div style="font-size:11px;color:var(--orange);margin-bottom:3px;">' +
            esc(c.component || 'Unspecified') +
            (c.date ? ' &mdash; ' + esc(c.date) : '') +
            (c.crash ? ' <span style="color:var(--red)">&#9888; Crash</span>' : '') +
            (c.fire ? ' <span style="color:var(--red)">&#128293; Fire</span>' : '') +
          '</div>' +
          (c.summary ? '<div style="font-size:12px;color:#bbb;line-height:1.5;">' + esc(c.summary) + '</div>' : '') +
        '</div>'
      ).join('');
      const totalCount = d.complaint_count || d.complaints.length;
      complaintsHtml =
        '<div style="margin-top:12px;">' +
          '<div style="font-size:12px;font-weight:600;color:var(--orange);text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px;">' +
            'NHTSA Complaints (' + totalCount + ' total, showing top ' + d.complaints.length + ')' +
          '</div>' +
          rows +
        '</div>';
    }

    body =
      '<div class="stats-row">' +
        '<div class="stat-item"><div class="stat-val" style="color:var(--green);font-size:18px;">' + esc(vehicle || 'Unknown') + '</div><div class="stat-lbl">Vehicle</div></div>' +
      '</div>' +
      '<div class="tags">' +
        (d.engine ? '<span class="chip chip-muted">' + esc(d.engine) + '</span>' : '') +
        '<span class="chip ' + (d.recall_count > 0 ? 'chip-red' : 'chip-green') + '">' + (d.recall_count||0) + ' Recalls</span>' +
        '<span class="chip ' + (d.complaint_count > 0 ? 'chip-orange' : 'chip-muted') + '">' + (d.complaint_count||0) + ' NHTSA Complaints</span>' +
        extraChips +
      '</div>' +
      recallsHtml +
      complaintsHtml;
  }

  el.innerHTML =
    '<div class="panel-header">' +
      '<div class="panel-icon">E</div>' +
      '<div class="panel-title">ENRICH &mdash; Vehicle Metadata</div>' +
    '</div>' +
    '<div class="panel-body">' + body + '</div>';

  showPanel(el);
}

// ── SEPARATE panel ─────────────────────────────────────────────────────────
function renderSeparate(d) {
  const el = document.getElementById('panelSeparate');
  const overall = d.overall_score;
  const systems = d.systems || {};

  const sysCards = Object.entries(systems).map(([name, info]) => {
    const score = info.score;
    const pct   = score !== null && score !== undefined ? Math.round(score * 100) : null;
    const color = scoreColor(score);
    const bar   = pct !== null
      ? '<div class="score-bar-wrap"><div class="score-bar-fill" style="width:' + pct + '%;background:' + color + '"></div></div>'
      : '<div class="score-bar-wrap"><div class="score-bar-fill" style="width:0%;background:var(--muted)"></div></div>';
    return '<div class="sys-card">' +
      '<div class="sys-name">' + esc(name) + '</div>' +
      '<div class="sys-score-row">' +
        '<div class="sys-score-val" style="color:' + color + '">' + (pct !== null ? pct + '%' : 'N/A') + '</div>' +
        bar +
      '</div>' +
      '<div class="sys-summary">' + esc(info.summary || '') + '</div>' +
    '</div>';
  }).join('');

  const overallColor = scoreColor(overall);
  const overallPct = overall !== null && overall !== undefined ? Math.round(overall * 100) : null;

  el.innerHTML =
    '<div class="panel-header">' +
      '<div class="panel-icon">S</div>' +
      '<div class="panel-title">SEPARATE &mdash; System Health Scoring</div>' +
      (overallPct !== null ? '<div class="panel-subtitle"><span class="chip ' + scoreChipClass(overall) + '">Overall ' + overallPct + '%</span></div>' : '') +
    '</div>' +
    '<div class="panel-body">' +
      '<div class="stats-row" style="align-items:flex-end;gap:16px;">' +
        '<div class="stat-item">' +
          '<div class="overall-score" style="color:' + overallColor + '">' + (overallPct !== null ? overallPct + '%' : 'N/A') + '</div>' +
          '<div class="stat-lbl">Overall Health Score</div>' +
        '</div>' +
      '</div>' +
      '<div class="sys-grid">' + sysCards + '</div>' +
    '</div>';

  showPanel(el);
}

// ── COMPOUND panel ─────────────────────────────────────────────────────────
function formatAssessment(text) {
  if (!text) return '';
  // Split on double newline (avoid regex with literal newlines in Python string context)
  const paras = text.split('\\n\\n').concat(text.indexOf('\\n\\n') < 0 ? [] : []);
  // Fallback: if no double-newlines, split by single newlines into sentences
  const parts = text.indexOf('\\n\\n') >= 0
    ? text.split('\\n\\n')
    : [text];
  return parts
    .map(p => p.replace(/\\n/g, ' ').trim())
    .filter(Boolean)
    .map(p => {
      const escaped = esc(p).replace(/[*][*](.+?)[*][*]/g, '<strong>$1</strong>');
      return '<p>' + escaped + '</p>';
    })
    .join('');
}

function renderCompound(d) {
  const el = document.getElementById('panelCompound');
  const urgency = d.urgency || 'UNKNOWN';

  el.innerHTML =
    '<div class="panel-header">' +
      '<div class="panel-icon">A</div>' +
      '<div class="panel-title">COMPOUND &mdash; AI Assessment</div>' +
      '<div class="panel-subtitle"><span class="urgency urgency-' + urgency + '">' + esc(urgency) + '</span></div>' +
    '</div>' +
    '<div class="panel-body">' +
      '<div class="assessment-text">' + formatAssessment(d.assessment || '') + '</div>' +
    '</div>';

  showPanel(el);

  // Load vehicle history after compound panel renders
  const vid = (document.getElementById('libVehicle') || {}).value;
  if (vid) renderHistory(vid);
}

// ── HITL panel ─────────────────────────────────────────────────────────────
function renderHITL(d) {
  const el = document.getElementById('panelHITL');

  const sentMsg = d.email_sent
    ? 'Repair brief sent to <strong>' + esc(d.email) + '</strong>'
    : 'Email not sent (SendGrid key missing) &mdash; use links below for demo';

  el.innerHTML =
    '<div class="panel-header">' +
      '<div class="panel-icon">!</div>' +
      '<div class="panel-title">HITL &mdash; Human-in-the-Loop</div>' +
      '<div class="panel-subtitle"><span class="chip chip-red">Action Required</span></div>' +
    '</div>' +
    '<div class="panel-body">' +
      '<div style="font-size:13px;color:var(--text);">' + sentMsg + '</div>' +
      '<div class="hitl-links">' +
        '<a href="' + esc(d.approve_url) + '" class="hitl-link hitl-link-approve" target="_blank">&#10003; Approve</a>' +
        '<a href="' + esc(d.reject_url)  + '" class="hitl-link hitl-link-reject"  target="_blank">&#10007; Reject</a>' +
      '</div>' +
      '<div style="font-size:11px;color:var(--muted);">Owner must click to approve before any repair action is taken. Decision is logged with timestamp.</div>' +
    '</div>';

  showPanel(el);
}

// ── Error ──────────────────────────────────────────────────────────────────
function showError(msg) {
  errorBanner.textContent = 'Error: ' + msg;
  errorBanner.classList.add('visible');
}

// ── Sessions sidebar ───────────────────────────────────────────────────────
async function loadSessions() {
  try {
    const resp = await fetch('/api/sessions');
    const sessions = await resp.json();
    renderSessionsList(sessions.slice(0, 5));
  } catch(e) {
    sessionsList.innerHTML = '<div style="color:var(--muted);font-size:12px;">Could not load sessions.</div>';
  }
}

function renderSessionsList(sessions) {
  if (!sessions || !sessions.length) {
    sessionsList.innerHTML = '<div style="color:var(--muted);font-size:12px;">No sessions yet.</div>';
    return;
  }
  sessionsList.innerHTML = sessions.map(s => {
    const score = s.overall_score;
    const pct   = score !== null && score !== undefined ? Math.round(score * 100) + '%' : 'N/A';
    const chipCls = scoreChipClass(score);
    const label = s.vehicle_id && s.vehicle_id !== 'unknown' ? s.vehicle_id : (s.file_name || s.session_id.slice(0,8));
    return '<div class="session-chip" data-id="' + esc(s.session_id) + '" onclick="loadSession(\\'' + esc(s.session_id) + '\\')">' +
      '<div>' +
        '<div class="svid">' + esc(label) + '</div>' +
        '<div class="sfile">' + esc(s.file_name || '') + '</div>' +
      '</div>' +
      '<span class="sscore chip ' + chipCls + '">' + pct + '</span>' +
    '</div>';
  }).join('');
}

async function loadSession(sessionId) {
  try {
    const resp = await fetch('/api/sessions/' + sessionId);
    const rec = await resp.json();
    if (rec.error) { showError(rec.error); return; }
    renderStoredSession(rec);
  } catch(e) {
    showError('Could not load session: ' + e.message);
  }
}

function renderStoredSession(rec) {
  emptyState.style.display = 'none';
  pipelineBar.style.display = 'none';
  errorBanner.classList.remove('visible');

  // Clear panels
  ['panelCatch','panelEnrich','panelSeparate','panelCompound','panelHITL','panelHistory'].forEach(id => {
    const el = document.getElementById(id);
    el.style.display = 'none';
    el.classList.remove('visible');
    el.innerHTML = '';
  });

  // Reconstruct catch-like data from record
  const families = rec.families_present || [];
  const pidsStats = rec.pid_stats || {};

  // Build pids_summary from stored pid_stats
  let pidsSummary = [];
  try {
    const schemaFamMap = {};
    // We don't have schema client-side, so just show names + mean
    Object.entries(pidsStats).slice(0,8).forEach(([name, stats]) => {
      pidsSummary.push({ name, mean: stats.mean, unit: '', family: '' });
    });
    pidsSummary.sort((a,b) => Math.abs(b.mean||0) - Math.abs(a.mean||0));
  } catch(e) {}

  renderCatch({
    source:       rec.source,
    row_count:    rec.row_count,
    pid_count:    (rec.pids_present || []).length,
    dtcs:         rec.dtcs,
    warnings:     rec.warnings,
    families:     families,
    session_meta: rec.session_meta,
    pids_summary: pidsSummary,
  });

  // Enrich: no vehicle meta stored, show skipped
  renderEnrich({ skipped: true });

  // Separate: reconstruct from system_scores
  const systemScores = rec.system_scores || {};
  const systemsForRender = {};
  Object.entries(systemScores).forEach(([k,v]) => {
    systemsForRender[k] = { score: v, summary: '' };
  });
  renderSeparate({
    overall_score: rec.overall_score,
    systems: systemsForRender,
  });
}

// ── PID expand toggle ──────────────────────────────────────────────────────
function togglePidExpand(btn) {
  const extra = document.getElementById('pidBodyExtra');
  if (!extra) return;
  const expanded = extra.style.display !== 'none';
  extra.style.display = expanded ? 'none' : '';
  btn.textContent = expanded ? btn.dataset.collapsed : '▲ Hide extra signals';
}

// ── Vehicle History panel ──────────────────────────────────────────────────
const HISTORY_PIDS = ['LTFT_B1','STFT_B1','LTFT_B2','STFT_B2','ECT','IAT',
                      'AFR_B1','BOOST_ACTUAL','KNOCK_RETARD','MAP','CAT_TEMP_B1S1',
                      'RPM','LOAD','O2_LAMBDA_B1S1','WGDC_B1'];

async function renderHistory(vehicleId) {
  const el = document.getElementById('panelHistory');
  el.innerHTML =
    '<div class="panel-header">'
    + '<div class="panel-icon" style="background:#44ddff;color:#000">H</div>'
    + '<div class="panel-title">VEHICLE HISTORY &mdash; ' + esc(vehicleId) + '</div>'
    + '<div class="panel-subtitle" style="color:#44ddff">long-term trends</div>'
    + '</div>'
    + '<div class="panel-body"><div style="color:var(--muted);font-size:13px">Loading history...</div></div>';
  showPanel(el);

  // Fetch all PIDs in parallel
  const results = await Promise.all(
    HISTORY_PIDS.map(pid =>
      fetch('/api/trends/' + encodeURIComponent(vehicleId) + '/' + encodeURIComponent(pid))
        .then(r => r.json())
        .then(pts => ({ pid, points: pts }))
        .catch(() => ({ pid, points: [] }))
    )
  );

  const active = results.filter(r => r.points && r.points.length >= 3);

  if (active.length === 0) {
    el.querySelector('.panel-body').innerHTML =
      '<div class="no-history">No historical data yet for ' + esc(vehicleId)
      + '. Run more sessions to build a trend baseline.</div>';
    return;
  }

  const cardsHtml = active.map(r => {
    const pts    = r.points;
    const vals   = pts.map(p => p.mean);
    const mean   = (vals.reduce((a,b) => a+b, 0) / vals.length).toFixed(2);
    const vmin   = Math.min(...vals).toFixed(2);
    const vmax   = Math.max(...vals).toFixed(2);
    const last   = vals[vals.length-1].toFixed(2);
    const drift  = vals.length > 1
      ? ((vals[vals.length-1] - vals[0]) / vals.length)
      : 0;
    const driftStr = (drift > 0 ? '+' : '') + drift.toFixed(3) + '/session';
    const driftColor = Math.abs(drift) > 0.5 ? 'var(--orange)' : 'var(--muted)';
    const dateRange = (pts[0].recorded_at||'').slice(0,7)
      + (pts.length>1 ? ' → ' + (pts[pts.length-1].recorded_at||'').slice(0,7) : '');

    return '<div class="spark-card">'
      + '<div class="spark-header">'
        + '<span class="spark-pid">' + esc(r.pid) + '</span>'
        + '<span class="spark-stats">last: <strong>' + last + '</strong></span>'
      + '</div>'
      + '<canvas class="spark" id="spark_' + r.pid + '" width="200" height="48"></canvas>'
      + '<div class="spark-range">'
        + '<span>' + vmin + ' – ' + vmax + '</span>'
        + '<span style="color:' + driftColor + '">' + driftStr + '</span>'
      + '</div>'
      + (dateRange ? '<div style="font-size:10px;color:var(--muted);margin-top:2px">' + esc(dateRange) + ' · ' + pts.length + ' sessions</div>' : '')
      + '</div>';
  }).join('');

  const sessionSummary = active[0] ? active[0].points.length + ' sessions' : '';
  el.querySelector('.panel-body').innerHTML =
    '<div style="font-size:13px;color:var(--muted);margin-bottom:12px">'
    + esc(vehicleId) + ' · ' + sessionSummary
    + ' · ' + active.length + ' signals with history</div>'
    + '<div class="history-grid">' + cardsHtml + '</div>'
    + '<div style="margin-top:20px;text-align:center;">'
      + '<button id="analyzeHistoryBtn" onclick="analyzeHistory(' + JSON.stringify(vehicleId) + ')" '
        + 'style="background:linear-gradient(135deg,#1a56db,#44ddff);color:#fff;border:none;'
        + 'padding:10px 28px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;'
        + 'letter-spacing:.03em;">&#128200; Analyze Full History</button>'
    + '</div>'
    + '<div id="historyAssessment"></div>';

  // Draw sparklines after DOM update
  requestAnimationFrame(() => {
    active.forEach(r => {
      const canvas = document.getElementById('spark_' + r.pid);
      if (!canvas) return;
      drawSparkline(canvas, r.points.map(p => p.mean), r.pid);
    });
  });
}

async function analyzeHistory(vehicleId) {
  const btn = document.getElementById('analyzeHistoryBtn');
  const out = document.getElementById('historyAssessment');
  if (btn) { btn.disabled = true; btn.textContent = 'Analyzing…'; }
  out.innerHTML = '<div style="color:var(--muted);font-size:13px;margin-top:16px;text-align:center;">Running longitudinal analysis…</div>';

  try {
    const resp = await fetch('/api/analyze-history/' + encodeURIComponent(vehicleId));
    const data = await resp.json();
    if (data.error) {
      out.innerHTML = '<div style="color:var(--red);font-size:13px;margin-top:16px;">Error: ' + esc(data.error) + '</div>';
    } else {
      const urgencyColor = { CRITICAL:'var(--red)', HIGH:'var(--orange)', MEDIUM:'var(--orange)',
                             LOW:'var(--blue)', NORMAL:'var(--green)', UNKNOWN:'var(--muted)' };
      const urg = (data.urgency || 'UNKNOWN').toUpperCase();
      const color = urgencyColor[urg] || 'var(--muted)';
      const paragraphs = (data.assessment || '').split('\\n\\n').filter(Boolean);
      const bodyHtml = paragraphs.map(p =>
        '<p style="margin:0 0 12px;color:#dde;font-size:14px;line-height:1.7;">' +
        esc(p).replace(/\\n/g, '<br>') + '</p>'
      ).join('');
      out.innerHTML =
        '<div style="margin-top:20px;border:1px solid rgba(255,255,255,0.08);border-radius:10px;overflow:hidden;">'
        + '<div style="padding:12px 20px;background:rgba(255,255,255,0.04);display:flex;align-items:center;gap:10px;">'
          + '<span style="font-size:12px;font-weight:700;color:' + color + ';text-transform:uppercase;'
            + 'padding:3px 10px;border:1px solid ' + color + ';border-radius:4px;">' + esc(urg) + '</span>'
          + '<span style="font-size:13px;color:var(--muted);">Longitudinal AI Assessment &mdash; ' + esc(vehicleId) + '</span>'
        + '</div>'
        + '<div style="padding:16px 20px;font-family:\'Inter\',sans-serif;">' + bodyHtml + '</div>'
        + '</div>';
    }
  } catch(e) {
    out.innerHTML = '<div style="color:var(--red);font-size:13px;margin-top:16px;">Request failed: ' + esc(String(e)) + '</div>';
  }
  if (btn) { btn.disabled = false; btn.innerHTML = '&#128200; Analyze Full History'; }
}

function drawSparkline(canvas, values, pid) {
  const ctx = canvas.getContext('2d');
  const W = canvas.offsetWidth || 200;
  const H = 48;
  canvas.width  = W;
  canvas.height = H;
  ctx.clearRect(0, 0, W, H);

  const nums = values.filter(v => v !== null && !isNaN(v));
  if (nums.length < 2) return;

  let vmin = Math.min(...nums);
  let vmax = Math.max(...nums);
  if (vmin === vmax) { vmin -= 0.1; vmax += 0.1; }
  const vrange = vmax - vmin;

  const pad = 3;
  const toX = i => pad + (i / (nums.length - 1)) * (W - pad*2);
  const toY = v => H - pad - ((v - vmin) / vrange) * (H - pad*2);

  // Zero line for fuel trims / STFT / LTFT
  if (vmin < 0 && vmax > 0) {
    const zy = toY(0);
    ctx.strokeStyle = 'rgba(255,255,255,0.1)';
    ctx.setLineDash([2, 3]);
    ctx.beginPath(); ctx.moveTo(0, zy); ctx.lineTo(W, zy); ctx.stroke();
    ctx.setLineDash([]);
  }

  // Detect trend direction for color
  const slope = nums[nums.length-1] - nums[0];
  const trendColor = Math.abs(slope) < (vrange * 0.2) ? '#44ddff'
    : slope > 0 ? '#f5a623' : '#3dba6f';

  // Fill under line
  ctx.beginPath();
  nums.forEach((v, i) => { i===0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v)); });
  ctx.lineTo(toX(nums.length-1), H);
  ctx.lineTo(toX(0), H);
  ctx.closePath();
  ctx.fillStyle = 'rgba(68,221,255,0.06)';
  ctx.fill();

  // Line
  ctx.beginPath();
  ctx.strokeStyle = trendColor;
  ctx.lineWidth = 1.5;
  nums.forEach((v, i) => { i===0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v)); });
  ctx.stroke();

  // End dot
  ctx.fillStyle = trendColor;
  ctx.beginPath();
  ctx.arc(toX(nums.length-1), toY(nums[nums.length-1]), 2.5, 0, Math.PI*2);
  ctx.fill();
}

// ── Library browser ────────────────────────────────────────────────────────
let _library = [];   // full library data from /api/library
let _libSelectedPath = '';

async function loadLibrary() {
  try {
    const res  = await fetch('/api/library');
    _library   = await res.json();
    const sel  = document.getElementById('libVehicle');
    sel.innerHTML = '<option value="">— select a vehicle —</option>';
    _library.forEach(v => {
      const avail = v.sessions.filter(s => s.available).length;
      const opt = document.createElement('option');
      opt.value = v.vehicle_id;
      opt.textContent = v.vehicle_id + '  (' + avail + ' files)';
      sel.appendChild(opt);
    });
  } catch(e) {
    document.getElementById('libVehicle').innerHTML =
      '<option value="">Failed to load — ' + e.message + '</option>';
  }
}

function onLibVehicleChange() {
  const vid  = document.getElementById('libVehicle').value;
  const row  = document.getElementById('libFileRow');
  const fsel = document.getElementById('libFile');
  if (!vid) { row.style.display = 'none'; _libSelectedPath = ''; runBtn.disabled = true; return; }

  const vehicle = _library.find(v => v.vehicle_id === vid);
  if (!vehicle) return;

  fsel.innerHTML = '<option value="">— select a log file —</option>';
  vehicle.sessions.forEach(s => {
    if (!s.available) return;   // file missing on disk — skip
    const opt = document.createElement('option');
    opt.value = s.file_path;
    const date = s.recorded_at || '';
    opt.textContent = (date ? date + '  · ' : '') + s.file_name
                    + (s.row_count ? '  (' + s.row_count + ' rows)' : '');
    fsel.appendChild(opt);
  });
  row.style.display = '';
  _libSelectedPath = '';
  runBtn.disabled = true;
}

function onLibFileChange() {
  const path = document.getElementById('libFile').value;
  _libSelectedPath = path;
  if (path) {
    // clear any drag-drop file selection
    state.selectedFile = null;
    state.useSample    = false;
    dropText.textContent = 'Drop CSV here or click to browse';
    dropText.style.color = '';
    runBtn.disabled = false;
    runBtnText.textContent = 'Run Analysis';
  } else {
    runBtn.disabled = true;
  }
}

// ── Init ───────────────────────────────────────────────────────────────────
loadSessions();
loadLibrary();

// Activate first stage hint on ready
setStage('catch', null);

// ── Tab switching ──────────────────────────────────────────────────────────
const analyzeView = document.getElementById('mainArea');
const trendsView  = document.getElementById('trendsView');

function switchTab(tab) {
  document.getElementById('tabAnalyze').classList.toggle('active', tab === 'analyze');
  document.getElementById('tabTrends').classList.toggle('active', tab === 'trends');
  if (tab === 'analyze') {
    analyzeView.style.display = '';
    trendsView.classList.remove('active');
  } else {
    analyzeView.style.display = 'none';
    trendsView.classList.add('active');
    if (!window._vehiclesLoaded) loadVehicleGrid();
  }
}

// ── Trends — vehicle grid ──────────────────────────────────────────────────
let selectedTrendVehicle = null;

async function loadVehicleGrid() {
  window._vehiclesLoaded = true;
  const grid = document.getElementById('vehicleGrid');
  const sel  = document.getElementById('trendVehicle');
  try {
    const res  = await fetch('/api/vehicles');
    const list = await res.json();
    grid.innerHTML = '';
    sel.innerHTML  = '<option value="">— select a vehicle —</option>';
    list.forEach(v => {
      // vehicle grid card
      const card = document.createElement('div');
      card.className = 'vehicle-card';
      card.dataset.vid = v.vehicle_id;
      card.innerHTML = '<div class="vc-id">' + esc(v.vehicle_id) + '</div>'
                     + '<div class="vc-count">' + v.session_count + ' sessions</div>';
      card.addEventListener('click', () => {
        document.querySelectorAll('.vehicle-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        selectedTrendVehicle = v.vehicle_id;
        sel.value = v.vehicle_id;
      });
      grid.appendChild(card);
      // dropdown option
      const opt = document.createElement('option');
      opt.value = v.vehicle_id;
      opt.textContent = v.vehicle_id + ' (' + v.session_count + ' sessions)';
      sel.appendChild(opt);
    });
  } catch(e) {
    grid.innerHTML = '<div style="color:var(--muted);font-size:12px">Failed to load vehicles</div>';
  }
}

// ── Trends — chart ─────────────────────────────────────────────────────────
let trendCanvas = document.getElementById('trendChart');
let trendCtx    = trendCanvas ? trendCanvas.getContext('2d') : null;

async function loadTrend() {
  const vid = document.getElementById('trendVehicle').value || selectedTrendVehicle;
  const pid = document.getElementById('trendPid').value;
  if (!vid || !pid) {
    document.getElementById('noTrend').textContent = 'Select a vehicle and signal first.';
    return;
  }
  document.getElementById('noTrend').textContent = 'Loading...';
  document.getElementById('chartCard').style.display = 'none';

  // sync card selection
  document.querySelectorAll('.vehicle-card').forEach(c => {
    c.classList.toggle('selected', c.dataset.vid === vid);
  });

  try {
    const res    = await fetch('/api/trends/' + encodeURIComponent(vid) + '/' + encodeURIComponent(pid));
    const points = await res.json();

    if (!Array.isArray(points) || points.length === 0) {
      document.getElementById('noTrend').textContent =
        'No ' + pid + ' data found for ' + vid + '. Try a different signal or vehicle.';
      return;
    }

    // Build chart data
    const labels = points.map(p => {
      const d = new Date(p.recorded_at || p.ingested_at || '');
      return isNaN(d) ? '#' + points.indexOf(p) : d.toLocaleDateString('en-US', {month:'short', day:'numeric'});
    });
    const values = points.map(p => p.mean !== undefined ? p.mean : p.value);

    // Stats
    const nums = values.filter(v => v !== null && v !== undefined);
    const mean = nums.reduce((a,b) => a+b, 0) / nums.length;
    const vmin = Math.min(...nums);
    const vmax = Math.max(...nums);
    const last = nums[nums.length - 1];
    const trend_slope = nums.length > 1
      ? ((nums[nums.length-1] - nums[0]) / nums.length).toFixed(3)
      : 0;

    // Draw chart
    drawLineChart(trendCtx, trendCanvas, labels, values, pid);

    // Show card
    document.getElementById('chartTitle').textContent = pid + '  ·  ' + vid;
    document.getElementById('chartSub').textContent =
      points.length + ' sessions  ·  '
      + (points[0]?.recorded_at || '').slice(0,10) + ' → '
      + (points[points.length-1]?.recorded_at || '').slice(0,10);

    const statsEl = document.getElementById('trendStats');
    statsEl.innerHTML = [
      { label: 'Mean',  value: mean.toFixed(2)  },
      { label: 'Min',   value: vmin.toFixed(2)  },
      { label: 'Max',   value: vmax.toFixed(2)  },
      { label: 'Last',  value: last.toFixed(2)  },
      { label: 'Drift', value: (trend_slope > 0 ? '+' : '') + trend_slope + '/session' },
    ].map(s => '<div class="trend-stat"><span class="trend-stat-label">' + s.label
             + '</span><span class="trend-stat-value">' + s.value + '</span></div>').join('');

    document.getElementById('chartCard').style.display = 'block';
    document.getElementById('noTrend').style.display = 'none';
  } catch(e) {
    document.getElementById('noTrend').textContent = 'Error loading trend data: ' + e.message;
  }
}

function drawLineChart(ctx, canvas, labels, values, pid) {
  if (!ctx) return;
  const W = canvas.offsetWidth || 800;
  const H = 280;
  canvas.width  = W;
  canvas.height = H;

  const pad = { top: 20, right: 20, bottom: 40, left: 52 };
  const cw = W - pad.left - pad.right;
  const ch = H - pad.top  - pad.bottom;

  ctx.clearRect(0, 0, W, H);

  const nums = values.map(v => parseFloat(v)).filter(v => !isNaN(v));
  if (nums.length === 0) return;

  let vmin = Math.min(...nums);
  let vmax = Math.max(...nums);
  if (vmin === vmax) { vmin -= 1; vmax += 1; }
  const vrange = vmax - vmin;

  const toX = i => pad.left + (i / (values.length - 1 || 1)) * cw;
  const toY = v => pad.top  + ch - ((v - vmin) / vrange) * ch;

  // Grid
  ctx.strokeStyle = 'rgba(48,54,61,0.8)';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + (i / 4) * ch;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + cw, y); ctx.stroke();
    const val = vmax - (i / 4) * vrange;
    ctx.fillStyle = 'rgba(160,160,160,0.7)';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(val.toFixed(1), pad.left - 6, y + 4);
  }

  // X labels — show every Nth to avoid crowding
  const step = Math.max(1, Math.ceil(labels.length / 10));
  ctx.fillStyle = 'rgba(160,160,160,0.7)';
  ctx.font = '10px sans-serif';
  ctx.textAlign = 'center';
  labels.forEach((lbl, i) => {
    if (i % step === 0 || i === labels.length - 1) {
      ctx.fillText(lbl, toX(i), H - pad.bottom + 14);
    }
  });

  // Zero line (useful for fuel trims)
  if (vmin < 0 && vmax > 0) {
    const zy = toY(0);
    ctx.strokeStyle = 'rgba(255,255,255,0.12)';
    ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(pad.left, zy); ctx.lineTo(pad.left + cw, zy); ctx.stroke();
    ctx.setLineDash([]);
  }

  // Filled area under line
  ctx.beginPath();
  values.forEach((v, i) => {
    const x = toX(i), y = toY(parseFloat(v) || vmin);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.lineTo(toX(values.length - 1), toY(vmin));
  ctx.lineTo(toX(0), toY(vmin));
  ctx.closePath();
  ctx.fillStyle = 'rgba(74,158,255,0.08)';
  ctx.fill();

  // Line
  ctx.beginPath();
  ctx.strokeStyle = '#4a9eff';
  ctx.lineWidth = 2;
  values.forEach((v, i) => {
    const x = toX(i), y = toY(parseFloat(v) || vmin);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Dots
  ctx.fillStyle = '#4a9eff';
  values.forEach((v, i) => {
    const x = toX(i), y = toY(parseFloat(v) || vmin);
    ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fill();
  });
}

// sync vehicle select dropdown ↔ card clicks
document.getElementById('trendVehicle').addEventListener('change', e => {
  selectedTrendVehicle = e.target.value;
  document.querySelectorAll('.vehicle-card').forEach(c => {
    c.classList.toggle('selected', c.dataset.vid === e.target.value);
  });
});

// __SERVER_CONFIG__
// SERVER_CONFIG is injected at render time — no fetch needed
(function applyDemoMode() {
  if (!SERVER_CONFIG.demo_mode) return;
  const dropSection = document.getElementById('dropSection');
  const dropDivider = document.getElementById('dropDivider');
  const libSection  = document.querySelector('.sidebar-section');
  if (dropSection) dropSection.style.display = 'none';
  if (dropDivider) dropDivider.style.display = 'none';
  if (libSection)  libSection.style.display  = 'none';
  const vinEl = document.getElementById('vinInput');
  if (vinEl) { vinEl.value = SERVER_CONFIG.demo_vin; vinEl.readOnly = true; }
  runBtn.disabled = false;
  runBtnText.textContent = 'Run Analysis';
  const notice = document.createElement('div');
  notice.id = 'demoNotice';
  notice.style.cssText = 'font-size:12px;color:var(--muted);padding:4px 0;text-align:center;';
  notice.textContent = 'Demo mode — BMW 335i sample pre-loaded';
  runBtn.parentNode.insertBefore(notice, runBtn);
})();
</script>

</body>
</html>"""


@app.get("/config")
def config():
    return {"demo_mode": DEMO_MODE, "demo_vin": DEMO_VIN if DEMO_MODE else ""}


@app.get("/", response_class=HTMLResponse)
def root():
    import json as _json
    config_js = f"const SERVER_CONFIG = {_json.dumps({'demo_mode': DEMO_MODE, 'demo_vin': DEMO_VIN if DEMO_MODE else ''})};"
    html = _UI_HTML.replace("// __SERVER_CONFIG__", config_js)
    return HTMLResponse(html)
