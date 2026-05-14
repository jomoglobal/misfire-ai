"""
MisfireAI end-to-end pipeline runner.

Runs the full Catch → Enrich → Separate → Compound pipeline against a single
log file, emitting Phoenix/OTel traces at every stage.

Usage:
    python pipeline/run_pipeline.py
    python pipeline/run_pipeline.py --file data/external/carOBD/obdiidata/drive1.csv
    python pipeline/run_pipeline.py --file "data/sample/2009-BMW-335i-2026-04-15 13-15-01.csv" --vin WBAPN73579A395571
    python pipeline/run_pipeline.py --dry-run
    python pipeline/run_pipeline.py --vehicle-id IJE0S --file data/mhd/session.csv
    python pipeline/run_pipeline.py --batch data/mhd/
"""

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor, ReadableSpan
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

OTEL_PROJECT_KEY = "openinference.project.name"

DEFAULT_FILE = REPO_ROOT / "data" / "external" / "carOBD" / "obdiidata" / "drive1.csv"
DEFAULT_VIN  = ""  # optional — triggers decode_vin + lookup_tsb


def _url(endpoint: str) -> str:
    return endpoint if endpoint.endswith("/v1/traces") else f"{endpoint.rstrip('/')}/v1/traces"


def _setup_tracing(project_name: str) -> trace.Tracer:
    sravan_endpoint   = os.getenv("PHOENIX_COLLECTOR_ENDPOINT_SRAVAN", "")
    sravan_key        = os.getenv("PHOENIX_API_KEY_SRAVAN", "")
    personal_endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT_PERSONAL", "")
    personal_key      = os.getenv("PHOENIX_API_KEY_PERSONAL", "")

    provider = TracerProvider(resource=Resource.create({
        "service.name": "misfire-ai-pipeline",
        OTEL_PROJECT_KEY: project_name,
    }))

    # Always add console exporter so traces are visible even without Phoenix keys
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    if sravan_endpoint and sravan_key:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
            endpoint=_url(sravan_endpoint),
            headers={"Authorization": f"Bearer {sravan_key}"},
        )))
        print(f"✅ [tracer][sravan]   → {_url(sravan_endpoint)} | project: {project_name}")
    else:
        print("ℹ  [tracer][sravan]   Skipped — no PHOENIX_API_KEY_SRAVAN in .env")

    if personal_endpoint and personal_key:
        personal_batch = BatchSpanProcessor(OTLPSpanExporter(
            endpoint=_url(personal_endpoint),
            headers={"Authorization": f"Bearer {personal_key}"},
        ))

        class _PersonalForwarder(SpanProcessor):
            def on_start(self, span, parent_context=None): pass
            def on_end(self, span: ReadableSpan): personal_batch.on_end(span)
            def shutdown(self): personal_batch.shutdown()
            def force_flush(self, t=30_000): return personal_batch.force_flush(t)

        provider.add_span_processor(_PersonalForwarder())
        print(f"✅ [tracer][personal] → {_url(personal_endpoint)} | project: {project_name}")
    else:
        print("ℹ  [tracer][personal] Skipped — no PHOENIX_API_KEY_PERSONAL in .env")

    trace.set_tracer_provider(provider)
    return trace.get_tracer("misfire-ai-pipeline")


def run(
    file_path: str,
    vin: str,
    recipient_email: str,
    dry_run: bool,
    project_name: str,
    vehicle_id_override: str = "",
) -> None:
    from tools.mcp_server import ingest_file, decode_vin, lookup_tsb, score_vehicle_health
    from tools.session_store import SessionStore, SessionRecord, parse_mhd_filename

    tracer = _setup_tracing(project_name)

    print(f"\n{'='*60}")
    print(f"MisfireAI Pipeline Run")
    print(f"  file:    {file_path}")
    print(f"  vin:     {vin or '(none)'}")
    print(f"  dry-run: {dry_run}")
    print(f"{'='*60}\n")

    with tracer.start_as_current_span("misfire.pipeline") as root_span:
        root_span.set_attribute("pipeline.file", str(file_path))
        root_span.set_attribute("pipeline.vin", vin or "")
        root_span.set_attribute("pipeline.dry_run", dry_run)

        # ── STAGE 1: CATCH ────────────────────────────────────────────────
        print("▶  [1/4] CATCH — ingest_file")
        with tracer.start_as_current_span("misfire.catch.ingest_file") as span:
            span.set_attribute("tool", "ingest_file")
            span.set_attribute("file", str(file_path))

            if dry_run:
                snapshot_json = json.dumps({
                    "source": "dry_run", "file": "dry_run.csv", "row_count": 0,
                    "pids": {
                        "RPM":     {"mean": 1200, "min": 800,  "max": 2000, "last": 1100, "std": 150},
                        "ECT":     {"mean": 90,   "min": 85,   "max": 95,   "last": 90,   "std": 2},
                        "LTFT_B1": {"mean": 3.1,  "min": 0.8,  "max": 6.2,  "last": 3.9,  "std": 1.1},
                        "STFT_B1": {"mean": 0.5,  "min": -3.1, "max": 4.7,  "last": 0.8,  "std": 1.8},
                    },
                    "families": {
                        "drivetrain": ["RPM"],
                        "thermal":    ["ECT"],
                        "fueling":    ["LTFT_B1", "STFT_B1"],
                    },
                    "dtcs": [], "warnings": [], "session_meta": {},
                })
            else:
                snapshot_json = ingest_file(str(file_path))

            snapshot = json.loads(snapshot_json)
            if "error" in snapshot:
                print(f"   ❌ ingest_file error: {snapshot['error']}")
                root_span.set_attribute("pipeline.error", snapshot["error"])
                return

            pids = snapshot.get("pids", {})
            span.set_attribute("catch.source",        snapshot.get("source", ""))
            span.set_attribute("catch.row_count",     snapshot.get("row_count", 0))
            span.set_attribute("catch.pid_count",     len(pids))
            span.set_attribute("catch.dtc_count",     len(snapshot.get("dtcs", [])))
            span.set_attribute("catch.warning_count", len(snapshot.get("warnings", [])))

            print(f"   ✅ source={snapshot['source']}  rows={snapshot['row_count']}  "
                  f"pids={len(pids)}  dtcs={snapshot.get('dtcs', [])}  "
                  f"warnings={len(snapshot.get('warnings', []))}")

        # ── STAGE 2: ENRICH ───────────────────────────────────────────────
        print("▶  [2/4] ENRICH — decode_vin + lookup_tsb")
        vehicle_meta: dict = {}
        tsb_results: dict = {}

        with tracer.start_as_current_span("misfire.enrich") as enrich_span:
            enrich_span.set_attribute("tool", "decode_vin + lookup_tsb")

            if vin:
                with tracer.start_as_current_span("misfire.enrich.decode_vin") as span:
                    span.set_attribute("vin", vin)
                    if dry_run:
                        vehicle_meta = {"make": "Toyota", "model": "Etios", "year": "2014",
                                        "engine": "1.5", "fuel_type": "Gasoline"}
                    else:
                        vehicle_meta = json.loads(decode_vin(vin))
                    span.set_attribute("enrich.make",  vehicle_meta.get("make", ""))
                    span.set_attribute("enrich.model", vehicle_meta.get("model", ""))
                    span.set_attribute("enrich.year",  vehicle_meta.get("year", ""))
                    print(f"   ✅ VIN decoded: {vehicle_meta.get('year')} "
                          f"{vehicle_meta.get('make')} {vehicle_meta.get('model')}")

                with tracer.start_as_current_span("misfire.enrich.lookup_tsb") as span:
                    span.set_attribute("vin", vin)
                    dtcs = snapshot.get("dtcs", [])
                    symptom = f"fuel trim {dtcs[0]}" if dtcs else "fuel trim anomaly"
                    if dry_run:
                        tsb_results = {"recalls": [], "complaints": [], "recall_count": 0}
                    else:
                        tsb_results = json.loads(lookup_tsb(vin, symptom=symptom))
                    span.set_attribute("enrich.recall_count",    tsb_results.get("recall_count", 0))
                    span.set_attribute("enrich.complaint_count", tsb_results.get("complaint_count", 0))
                    print(f"   ✅ TSB/recalls: {tsb_results.get('recall_count', 0)} recalls, "
                          f"{tsb_results.get('complaint_count', 0)} complaints")
            else:
                print("   ℹ  No VIN provided — skipping decode_vin and lookup_tsb")
                enrich_span.set_attribute("enrich.skipped", True)

        # ── STAGE 3: SEPARATE — score_vehicle_health ─────────────────────
        print("▶  [3/4] SEPARATE — score_vehicle_health")
        with tracer.start_as_current_span("misfire.separate.score_vehicle_health") as span:
            span.set_attribute("tool", "score_vehicle_health")

            if dry_run:
                scores_json = json.dumps({
                    "overall_score": 0.82,
                    "systems": {
                        "fueling":  {"score": 0.88, "summary": "Fueling normal"},
                        "cooling":  {"score": 0.95, "summary": "Normal operating temperature"},
                        "ignition": {"score": 0.76, "summary": "Timing normal"},
                        "catalyst": {"score": None,  "summary": "No catalyst temp data"},
                    },
                    "dtcs_present": [], "data_warnings": [],
                })
            else:
                scores_json = score_vehicle_health(snapshot_json)

            scores = json.loads(scores_json)
            overall = scores.get("overall_score")
            span.set_attribute("separate.overall_score", overall or 0.0)

            for system, info in scores.get("systems", {}).items():
                s = info.get("score")
                if s is not None:
                    span.set_attribute(f"separate.score.{system}", s)

            print(f"   ✅ overall={overall}")
            for system, info in scores.get("systems", {}).items():
                print(f"      {system:<12} {info.get('score', 'n/a')!s:<6}  {info['summary']}")

        # ── PERSIST SESSION RECORD ────────────────────────────────────────
        if not dry_run:
            try:
                detected_source = snapshot.get("source", "unknown")
                session_meta    = snapshot.get("session_meta", {})

                # Determine vehicle_id: CLI override > VIN decode > MHD filename > unknown
                vid = vehicle_id_override
                if not vid and vehicle_meta.get("make"):
                    vid = (
                        f"{vehicle_meta.get('make', '').lower()}-"
                        f"{vehicle_meta.get('model', '').lower()}-"
                        f"{vehicle_meta.get('year', '')}"
                    ).strip("-")
                if not vid and detected_source == "mhd" and session_meta.get("vehicle_id"):
                    vid = session_meta["vehicle_id"]
                if not vid:
                    vid = "unknown"

                # recorded_at: MHD filename parse > file mtime
                recorded_at = ""
                if detected_source == "mhd" and session_meta.get("recorded_at"):
                    recorded_at = session_meta["recorded_at"]
                else:
                    try:
                        import datetime as _dt
                        mtime = os.path.getmtime(str(file_path))
                        recorded_at = _dt.datetime.fromtimestamp(
                            mtime, tz=_dt.timezone.utc
                        ).isoformat()
                    except Exception:
                        pass

                pids_present     = list(pids.keys())
                families_present = list(snapshot.get("families", {}).keys())
                system_scores    = {
                    k: v.get("score")
                    for k, v in scores.get("systems", {}).items()
                }

                record = SessionRecord(
                    vehicle_id=      vid,
                    source=          detected_source,
                    file_path=       str(file_path),
                    file_name=       Path(file_path).name,
                    recorded_at=     recorded_at,
                    row_count=       snapshot.get("row_count", 0),
                    pids_present=    pids_present,
                    families_present=families_present,
                    pid_stats=       pids,
                    dtcs=            snapshot.get("dtcs", []),
                    warnings=        snapshot.get("warnings", []),
                    session_meta=    session_meta,
                    overall_score=   overall,
                    system_scores=   system_scores,
                )

                store = SessionStore(str(REPO_ROOT / "data" / "sessions.db"))
                store.save(record)
                print(f"\n   ✅ Session saved → {record.session_id} (vehicle={vid})")

            except Exception as e:
                print(f"\n   ⚠  Session store error: {e}")

        # ── STAGE 4: COMPOUND — diagnostic agent ─────────────────────────
        print("▶  [4/4] COMPOUND — diagnostic agent")
        with tracer.start_as_current_span("misfire.compound.agent") as span:
            span.set_attribute("tool", "run_diagnostic_agent")

            if dry_run:
                print("   ℹ  [dry-run] Skipping agent call — no OpenAI API call made")
                span.set_attribute("compound.skipped", True)
            elif not os.getenv("OPENAI_API_KEY"):
                print("   ⚠  OPENAI_API_KEY not set — skipping agent call")
                span.set_attribute("compound.skipped", True)
            else:
                from pipeline.agent import run_diagnostic_agent, AgentInput

                # Build snapshot dict for agent from ingested PID means
                agent_snapshot = {pid: vals["mean"] for pid, vals in pids.items()}
                if snapshot.get("dtcs"):
                    agent_snapshot["DTCs"] = snapshot["dtcs"]

                # Use first vehicle from vehicles.py if no VIN match, else best guess
                vehicle_id_agent = (
                    "bmw-335i-2009" if "BMW" in str(vehicle_meta.get("make", "")).upper()
                    else "tundra-2007" if "TOYOTA" in str(vehicle_meta.get("make", "")).upper()
                    else "honda-fit-2015"
                )

                agent_input = AgentInput(
                    vehicle_id=vehicle_id_agent,
                    snapshot=agent_snapshot,
                    scenario=f"pipeline_run:{Path(file_path).stem}",
                )

                output = run_diagnostic_agent(agent_input)
                span.set_attribute("compound.urgency",    output.urgency)
                span.set_attribute("compound.vehicle_id", output.vehicle_id)

                print(f"\n{'─'*60}")
                print(f"DIAGNOSTIC ASSESSMENT  [{output.urgency}]")
                print(f"{'─'*60}")
                print(output.assessment)
                if output.warnings:
                    print(f"\nPreprocessor warnings: {output.warnings}")

                # ── HITL GATE ─────────────────────────────────────────────
                if recipient_email and output.urgency in ("CRITICAL", "HIGH", "MEDIUM"):
                    from tools.hitl import RepairBrief, send_approval_request

                    brief = RepairBrief(
                        vehicle_make=vehicle_meta.get("make", "Unknown"),
                        vehicle_model=vehicle_meta.get("model", "Unknown"),
                        vehicle_year=vehicle_meta.get("year", ""),
                        session_id=f"pipeline_run:{Path(file_path).stem}",
                        urgency=output.urgency,
                        overall_score=overall,
                        system_scores=scores.get("systems", {}),
                        dtcs=snapshot.get("dtcs", []),
                        assessment=output.assessment,
                        recipient_email=recipient_email,
                    )

                    print(f"\n▶  HITL — sending repair brief to {recipient_email}")
                    hitl_result = send_approval_request(brief)
                    span.set_attribute("hitl.decision",   hitl_result["decision"])
                    span.set_attribute("hitl.decided_at", hitl_result.get("decided_at") or "")
                    span.set_attribute("hitl.token",      hitl_result["token"])
                elif recipient_email:
                    print(f"\n   ℹ  Urgency={output.urgency} — HITL gate not triggered (LOW/NORMAL only)")

        root_span.set_attribute("pipeline.complete", True)

    print(f"\n{'='*60}")
    print("Pipeline complete — traces emitted")
    print(f"{'='*60}\n")


def run_batch(folder_path: str, project_name: str) -> None:
    """Run ingest_batch on a folder and print results."""
    from tools.mcp_server import ingest_batch

    tracer = _setup_tracing(project_name)

    print(f"\n{'='*60}")
    print(f"MisfireAI Batch Ingest")
    print(f"  folder: {folder_path}")
    print(f"{'='*60}\n")

    with tracer.start_as_current_span("misfire.batch") as span:
        span.set_attribute("batch.folder", folder_path)
        result_json = ingest_batch(folder_path=folder_path, max_files=500)
        result = json.loads(result_json)

        if "error" in result:
            print(f"   ❌ {result['error']}")
            return

        span.set_attribute("batch.processed", result.get("processed", 0))
        span.set_attribute("batch.errors",    result.get("errors", 0))

        print(f"   ✅ processed={result['processed']}  errors={result['errors']}")
        print(f"      vehicle_id={result['vehicle_id']}")
        print(f"      families={result['families_seen']}")
        print(f"      date_range={result['date_range']}")
        print(f"      pid_coverage ({len(result.get('pid_coverage', {}))} PIDs):")
        for pid, pct in sorted(result.get("pid_coverage", {}).items(), key=lambda x: -x[1]):
            print(f"        {pid:<30} {pct:.0%}")

    print(f"\n{'='*60}")
    print("Batch ingest complete")
    print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="MisfireAI pipeline runner")
    parser.add_argument("--file",       default=str(DEFAULT_FILE), help="Path to log file")
    parser.add_argument("--vin",        default=DEFAULT_VIN,       help="17-char VIN (optional)")
    parser.add_argument("--email",      default="",                help="Owner email for HITL approval")
    parser.add_argument("--dry-run",    action="store_true",       help="Skip API calls, emit traces only")
    parser.add_argument("--project",    default="MisfireAI",       help="Phoenix project name")
    parser.add_argument("--vehicle-id", default="",                help="Override vehicle_id in session record")
    parser.add_argument("--batch",      default="",                help="Path to a folder — run ingest_batch instead of single file pipeline")
    args = parser.parse_args()

    if args.batch:
        run_batch(folder_path=args.batch, project_name=args.project)
    else:
        run(
            file_path=args.file,
            vin=args.vin,
            recipient_email=args.email,
            dry_run=args.dry_run,
            project_name=args.project,
            vehicle_id_override=getattr(args, "vehicle_id", ""),
        )


if __name__ == "__main__":
    main()
