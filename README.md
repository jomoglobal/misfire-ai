# MisfireAI

> AI-powered OBD2 diagnostic pipeline — catches developing vehicle issues before fault codes are set.

Standard scan tools surface fault codes after a problem is already confirmed. MisfireAI catches what's developing — correlating PIDs, scoring Mode 06 monitor margins, and building a health baseline across sessions — weeks before a DTC is ever set.

---

## ⚠️ Status: In Development

This project is actively being built. Core pipeline architecture and eval harness are in place. Full end-to-end pipeline and UI are in progress.

---

## What It Does

Most vehicles generate rich diagnostic data every time they run. Most owners never see it. MisfireAI reads that data, scores it against the vehicle's own internal thresholds, and surfaces findings in plain language — before a warning light, before a shop visit, before it becomes expensive.

---

## Pipeline

```
CATCH → ENRICH → SEPARATE → COMPOUND
```

| Stage | What Happens |
|---|---|
| **Catch** | Ingest from any supported source → normalize to common schema |
| **Enrich** | VIN decode, Mode 06 margin scoring, TSB/recall lookup, historical session comparison via RAG |
| **Separate** | 4-tier severity classification, per-system health scoring (0–1) |
| **Compound** | Plain-language session report, health dashboard, repair brief (owner approval required) |

---

## Supported Data Sources

- ELM327 adapter (Bluetooth/WiFi — live connection)
- Car Scanner app log export
- MHD (BMW flash/logging)
- Techstream (Toyota-specific)
- ESP32 CAN logger
- Sample data included — pipeline runs without hardware

---

## Key Features

- **Mode 06 predictive scoring** — captures the margin between a passing monitor and its threshold. A catalyst at 92% of its limit looks fine to a standard scanner. MisfireAI flags it.
- **Multi-source ingestion** — normalizes data from any supported format into a common schema
- **Historical baseline** — vehicle health accumulates across sessions; patterns that develop over weeks are visible
- **TSB & recall awareness** — findings cross-referenced against technical service bulletins and active recalls
- **Human-in-the-loop** — repair briefs require owner review and approval before anything is logged or shared

---

## Quickstart

> Sample OBD2 data is in `data/sample/`. No adapter required.

```bash
git clone https://github.com/jomoglobal/misfire-ai
cd misfire-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY
```

---

## Eval Harness

Built on the eval framework from the prior proof-of-concept. Three eval suites covering sensor validity, diagnosis accuracy, and urgency calibration. LLM-as-judge scoring with Phoenix/Arize tracing.

```bash
# Run all evals
python evals/run_evals.py

# Single scenario
python evals/run_evals.py --scenario diagnosis_accuracy

# Dry run (no API calls)
python evals/run_evals.py --dry-run
```

See [docs/judge-validation.md](docs/judge-validation.md) for scoring methodology and threshold rationale.

---

## Repository Structure

```
├── pipeline/
│   ├── agent.py           # Diagnostic reasoning — Claude claude-sonnet-4-6 + Phoenix tracing
│   ├── preprocessor.py    # Snapshot validation, normalization, artifact detection
│   └── vehicles.py        # Vehicle config registry (BMW 335i, Tundra, Honda Fit + more)
├── tools/                 # MCP server tool endpoints (in progress)
├── evals/
│   ├── run_evals.py       # Synthetic eval runner — LLM-as-judge, Phoenix traces
│   ├── sensor_validity.py
│   ├── diagnosis_accuracy.py
│   ├── urgency_calibration.py
│   └── results/           # Per-run JSON results
├── data/sample/           # Real OBD2 logs (BMW 335i, Honda Fit, Tundra) + synthetic dataset
├── prompts/               # System prompt versions (v1, v2)
├── docs/
│   ├── judge-validation.md   # LLM judge calibration results
│   └── monitoring-plan.md    # Eval cadence, PID recommendations per vehicle
├── product-brief.md
├── architecture.md
├── context.md
└── signal-decision.md
```

---

## Vehicles Tested

| ID | Vehicle | Engine | Notes |
|---|---|---|---|
| `bmw-335i-2009` | 2009 BMW 335i | 3.0L N54 Twin-Turbo | 477 real MHD sessions · E40 flex fuel |
| `tundra-2007` | 2007 Toyota Tundra | 4.0L 1GR-FE V6 | ELM327 + Car Scanner data |
| `honda-fit-2015` | 2015 Honda Fit | 1.5L L15B7 i4 | Car Scanner data |

---

## Prior Work

The eval harness, vehicle configs, system prompts, and sample data are evolved from a prior proof-of-concept ([obd2-vehicle-health-advisor](https://github.com/jomoglobal/obd2-vehicle-health-advisor)) built with Next.js, TypeScript, and GPT-4o. MisfireAI is a full rewrite in Python using Claude, with a multi-source ingestion layer, Mode 06 predictive scoring, and a production pipeline architecture.
