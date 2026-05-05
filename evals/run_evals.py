"""
Synthetic evaluation runner for MisfireAI.

Loads data/sample/synthetic_reference_dataset.json, runs each case through
Claude claude-sonnet-4-6, scores with LLM-as-judge, logs traces to Phoenix,
saves results to evals/results/.

Ported from obd2-vehicle-health-advisor/evals/run_synthetic_evals.py
(OpenAI/GPT-4o → Anthropic/Claude claude-sonnet-4-6).

Usage:
    python evals/run_evals.py
    python evals/run_evals.py --prompt prompts/system_prompt_v1.txt
    python evals/run_evals.py --scenario diagnosis_accuracy
    python evals/run_evals.py --dry-run
"""

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

import anthropic

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor, ReadableSpan
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.context import Context

OTEL_PROJECT_KEY = "openinference.project.name"
_personal_batch: BatchSpanProcessor | None = None


def _url(endpoint: str) -> str:
    return endpoint if endpoint.endswith("/v1/traces") else f"{endpoint.rstrip('/')}/v1/traces"


def _setup_tracing(sravan_project: str, personal_project: str) -> trace.Tracer:
    global _personal_batch

    sravan_endpoint  = os.getenv("PHOENIX_COLLECTOR_ENDPOINT_SRAVAN", "")
    sravan_key       = os.getenv("PHOENIX_API_KEY_SRAVAN", "")
    personal_endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT_PERSONAL", "")
    personal_key      = os.getenv("PHOENIX_API_KEY_PERSONAL", "")

    sravan_provider = TracerProvider(resource=Resource.create({
        "service.name": "misfire-ai-evals",
        OTEL_PROJECT_KEY: sravan_project,
    }))

    if sravan_endpoint and sravan_key:
        sravan_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(
                endpoint=_url(sravan_endpoint),
                headers={"Authorization": f"Bearer {sravan_key}"},
            ))
        )
        print(f"✅ [tracer][sravan]   → {_url(sravan_endpoint)} | project: {sravan_project}")
    else:
        print("[tracer][sravan] Skipped — missing endpoint or API key", file=sys.stderr)

    _personal_batch = None
    if personal_endpoint and personal_key:
        _personal_batch = BatchSpanProcessor(OTLPSpanExporter(
            endpoint=_url(personal_endpoint),
            headers={"Authorization": f"Bearer {personal_key}"},
        ))
        personal_ref = _personal_batch

        class _PersonalForwarder(SpanProcessor):
            def on_start(self, span, parent_context=None): pass
            def on_end(self, span: ReadableSpan): personal_ref.on_end(span)
            def shutdown(self): personal_ref.shutdown()
            def force_flush(self, timeout_millis=30_000): return personal_ref.force_flush(timeout_millis)

        sravan_provider.add_span_processor(_PersonalForwarder())
        print(f"✅ [tracer][personal] → {_url(personal_endpoint)} | project: {personal_project}")
    else:
        print("[tracer][personal] Skipped — missing endpoint or API key", file=sys.stderr)

    trace.set_tracer_provider(sravan_provider)
    return trace.get_tracer("misfire-ai-evals")


DATASET_PATH    = REPO_ROOT / "data" / "sample" / "synthetic_reference_dataset.json"
RESULTS_DIR     = REPO_ROOT / "evals" / "results"
DEFAULT_PROMPT  = REPO_ROOT / "prompts" / "system_prompt_v2.txt"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
PASS_THRESHOLD  = 6   # Updated per judge-validation.md findings


JUDGE_SYSTEM = """\
You are an automotive diagnostics expert evaluating an AI vehicle health advisor.
Score the agent response on these five criteria (0, 1, or 2 each):

- urgency_correct: Is the urgency level appropriate?
  2 = exact match or one-tier off conservative | 1 = one tier off | 0 = two+ tiers off
- root_cause_identified: Did the agent identify the primary root cause?
  2 = clearly identified and correct | 1 = partial/vague | 0 = wrong or missing
- bogus_value_handled: If a bogus/stuck sensor was present, was it caught?
  2 = flagged and not used | 1 = mentioned but still used | 0 = taken at face value (N/A → 2)
- data_gap_noted: If expected PIDs were missing, was the gap flagged?
  2 = noted with impact | 1 = partially | 0 = not mentioned (N/A → 2)
- vehicle_quirk_cited: If a known vehicle quirk is relevant, was it cited?
  2 = explicitly referenced | 1 = general awareness | 0 = not mentioned (N/A → 2)

Respond ONLY with JSON, no markdown:
{"urgency_correct":0,"root_cause_identified":0,"bogus_value_handled":2,"data_gap_noted":2,"vehicle_quirk_cited":0,"total":4,"judge_notes":"one sentence"}
"""


def call_agent(system_prompt: str, user_message: str, dry_run: bool = False) -> str:
    if dry_run:
        return "[DRY RUN] No actual API call made."
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text if message.content else ""


def judge_response(case: dict, agent_response: str, dry_run: bool = False) -> dict:
    if dry_run:
        return {"urgency_correct": 2, "root_cause_identified": 2, "bogus_value_handled": 2,
                "data_gap_noted": 2, "vehicle_quirk_cited": 2, "total": 10,
                "judge_notes": "DRY RUN"}

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    judge_user = (
        f"Case ID: {case['case_id']}\n"
        f"Scenario tag: {case['scenario_tag']}\n"
        f"Expected behavior: {case['expected_behavior']}\n"
        f"Failure mode to watch for: {case['failure_mode']}\n\n"
        f"Agent response:\n{agent_response}"
    )
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": judge_user}],
    )
    raw = message.content[0].text if message.content else "{}"
    try:
        scores = json.loads(raw)
    except json.JSONDecodeError:
        scores = {"urgency_correct": 0, "root_cause_identified": 0, "bogus_value_handled": 2,
                  "data_gap_noted": 2, "vehicle_quirk_cited": 0, "total": 4,
                  "judge_notes": f"JSON parse error: {raw[:100]}"}

    score_keys = ["urgency_correct", "root_cause_identified", "bogus_value_handled",
                  "data_gap_noted", "vehicle_quirk_cited"]
    scores["total"] = sum(scores.get(k, 0) for k in score_keys)
    return scores


def format_snapshot_message(case: dict) -> str:
    return (
        f"Vehicle: {case['context']['vehicle']}\n"
        f"Engine: {case['context']['engine']}\n\n"
        f"OBD2 Snapshot (last/min/max/mean/std per PID):\n"
        f"```json\n{json.dumps(case['input'], indent=2)}\n```"
    )


def run_evals(prompt_path: Path, scenario_filter: str | None, dry_run: bool,
              sravan_project: str, personal_project: str) -> None:
    tracer = _setup_tracing(sravan_project, personal_project)

    with open(prompt_path) as f:
        system_prompt = f.read().strip()
    with open(DATASET_PATH) as f:
        dataset = json.load(f)

    if scenario_filter:
        dataset = [c for c in dataset if c["scenario_tag"] == scenario_filter]
        if not dataset:
            print(f"No cases found for scenario_tag='{scenario_filter}'")
            return

    prompt_label = prompt_path.stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{prompt_label}_{timestamp}"
    results: list[dict] = []

    print(f"\n{'='*70}")
    print(f"  Eval run: {run_id}")
    print(f"  Cases:    {len(dataset)}  |  Threshold: {PASS_THRESHOLD}/10  |  Dry run: {dry_run}")
    print(f"{'='*70}\n")

    for i, case in enumerate(dataset, 1):
        case_id = case["case_id"]
        tag = case["scenario_tag"]
        print(f"[{i:02d}/{len(dataset):02d}] {case_id} ({tag}) ... ", end="", flush=True)

        user_message = format_snapshot_message(case)
        agent_response = ""
        scores: dict = {}
        error = None

        with tracer.start_as_current_span(f"eval.case.{case_id}") as span:
            span.set_attribute("eval.case_id", case_id)
            span.set_attribute("eval.scenario_tag", tag)
            span.set_attribute("eval.vehicle_id", case["vehicle_id"])
            span.set_attribute("eval.prompt_label", prompt_label)
            span.set_attribute("eval.run_id", run_id)

            try:
                with tracer.start_as_current_span("agent.call") as agent_span:
                    agent_response = call_agent(system_prompt, user_message, dry_run=dry_run)
                    agent_span.set_attribute("llm.response_length", len(agent_response))

                with tracer.start_as_current_span("judge.call") as judge_span:
                    scores = judge_response(case, agent_response, dry_run=dry_run)
                    judge_span.set_attribute("eval.total_score", scores.get("total", 0))

                for k, v in scores.items():
                    if isinstance(v, (int, float)):
                        span.set_attribute(f"eval.score.{k}", v)

                passed = scores.get("total", 0) >= PASS_THRESHOLD
                span.set_attribute("eval.passed", passed)
                status = "PASS" if passed else "FAIL"
                print(f"{status} ({scores.get('total', 0)}/10)  — {scores.get('judge_notes', '')}")

            except Exception as exc:
                error = traceback.format_exc()
                span.record_exception(exc)
                print(f"ERROR — {exc}")

            results.append({
                "run_id": run_id, "case_id": case_id, "vehicle_id": case["vehicle_id"],
                "scenario_tag": tag, "prompt_label": prompt_label,
                "agent_response": agent_response, "scores": scores,
                "passed": scores.get("total", 0) >= PASS_THRESHOLD if scores else False,
                "error": error,
            })

        if not dry_run and i < len(dataset):
            time.sleep(0.3)

    results_path = RESULTS_DIR / f"{run_id}.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    passed  = [r for r in results if r["passed"]]
    failed  = [r for r in results if not r["passed"] and not r["error"]]
    errors  = [r for r in results if r["error"]]

    print(f"\n{'='*70}")
    print(f"  SUMMARY  —  {run_id}")
    print(f"{'='*70}")
    print(f"  PASS: {len(passed)}  FAIL: {len(failed)}  ERROR: {len(errors)}  TOTAL: {len(results)}")

    totals = [r["scores"].get("total", 0) for r in results if r["scores"]]
    if totals:
        print(f"  Avg score: {sum(totals)/len(totals):.1f}/10  (threshold: {PASS_THRESHOLD})")

    criteria = ["urgency_correct", "root_cause_identified", "bogus_value_handled",
                "data_gap_noted", "vehicle_quirk_cited"]
    scored = [r for r in results if r["scores"]]
    if scored:
        print(f"\n  Per-criterion averages (max 2.0):")
        for c in criteria:
            vals = [r["scores"].get(c, 0) for r in scored]
            avg = sum(vals) / len(vals)
            bar = "█" * round(avg * 5)
            print(f"    {c:<30}  {avg:.2f}  {bar}")

    if failed:
        print(f"\n  Failed cases:")
        for r in failed:
            print(f"    {r['case_id']:<15}  {r['scores'].get('total',0)}/10  "
                  f"{r['scores'].get('judge_notes','')}")

    print(f"\n  Results → {results_path}")
    print(f"{'='*70}\n")

    provider = trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush()
    if _personal_batch:
        _personal_batch.force_flush()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--scenario", type=str, default=None,
                        choices=["diagnosis_accuracy", "urgency_calibration", "data_completeness"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sravan-project", default=os.getenv("PHOENIX_PROJECT_NAME_SRAVAN", "MisfireAI-Evals"))
    parser.add_argument("--personal-project", default=os.getenv("PHOENIX_PROJECT_NAME_PERSONAL", "MisfireAI"))
    args = parser.parse_args()

    run_evals(
        prompt_path=args.prompt,
        scenario_filter=args.scenario,
        dry_run=args.dry_run,
        sravan_project=args.sravan_project,
        personal_project=args.personal_project,
    )
