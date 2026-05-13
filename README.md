# MisfireAI

> AI-powered OBD2 diagnostic pipeline — catches developing vehicle issues before fault codes are set.

**[misfire.datronex.net](https://misfire.datronex.net)** · Built by [Datronex](https://datronex.net) · IAI09 Capstone · May 2026

Standard scan tools surface fault codes after a problem is already confirmed. MisfireAI catches what's developing — correlating live sensor data across multiple systems, scoring vehicle health, and producing a plain-language diagnostic assessment — weeks before a DTC is ever set.

---

## Pipeline

```
CATCH → ENRICH → SEPARATE → COMPOUND
```

| Stage | What Happens |
|---|---|
| **① Catch** | Parse OBD2 log file → normalize all columns to a common PID schema regardless of source format |
| **② Enrich** | Decode VIN via NHTSA API → look up open recalls and complaints → add vehicle-specific context |
| **③ Separate** | Score each vehicle system (fueling, cooling, ignition, catalyst) 0–1 → separate sustained anomalies from noise |
| **④ Compound** | GPT-4o generates plain-language diagnostic assessment → HITL gate sends repair brief to owner for approval |

---

## Quickstart

Sample OBD2 data is included in `data/sample/` — no adapter or hardware required to run the pipeline.

```bash
git clone https://github.com/jomoglobal/misfire-ai
cd misfire-ai
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env .env.bak   # back up, then fill in your keys
```

**Minimum keys to run the full pipeline:**
- `OPENAI_API_KEY` — GPT-4o diagnostic agent
- `PHOENIX_API_KEY_PERSONAL` + `PHOENIX_COLLECTOR_ENDPOINT_PERSONAL` — trace logging
- `SENDGRID_API_KEY` + `HITL_FROM_EMAIL` — only needed if using `--email` for HITL approval

**Run with sample data (no VIN, no email):**
```bash
python3 pipeline/run_pipeline.py
```

**Run with a real file and VIN:**
```bash
python3 pipeline/run_pipeline.py \
  --file "data/sample/2009-BMW-335i-2026-04-15 13-15-01.csv" \
  --vin WBAPN73579A395571
```

**Run with HITL approval email:**
```bash
python3 pipeline/run_pipeline.py \
  --file data/external/carOBD/obdiidata/drive1.csv \
  --vin 5TBRU54127S451393 \
  --email you@example.com
```

**Dry run (no API calls, traces only):**
```bash
python3 pipeline/run_pipeline.py --dry-run
```

---

## CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `--file` | `data/external/carOBD/obdiidata/drive1.csv` | Path to OBD2 log file |
| `--vin` | *(none)* | 17-character VIN — enables decode_vin + lookup_tsb |
| `--email` | *(none)* | Owner email — triggers HITL approval gate for HIGH/MEDIUM/CRITICAL findings |
| `--dry-run` | false | Skip all API calls, emit traces with synthetic data |
| `--project` | `MisfireAI` | Phoenix project name for this run |

---

## Supported Data Sources

The pipeline auto-detects source format and maps column names to a common schema.

| Source | Format | Notes |
|---|---|---|
| carOBD (eron93br) | CSV, uppercase cols | Toyota Etios, 304k rows, included in `data/external/` |
| Car Scanner app | CSV, verbose English headers with units | BMW 335i, Honda Fit logs in `data/sample/` |
| cephasax OBD-II | CSV, semicolon delimiter | Multi-make Brazil fleet, real DTC codes |
| Isay Gerard OBD-II | CSV, Spanish headers | KIA Soul, 1.1M rows, O2 sensors + catalyst temp |
| Generic CSV | Any | Unknown columns passed through as-is |

---

## MCP Tools

Four atomic tools exposed via FastMCP — each does one thing:

| Tool | What It Does |
|---|---|
| `ingest_file` | Parse a log file → normalized PID snapshot with per-PID stats |
| `decode_vin` | 17-char VIN → make/model/year/engine via NHTSA vPIC API |
| `lookup_tsb` | VIN + symptom → open recalls and complaints via NHTSA |
| `score_vehicle_health` | PID snapshot → 0–1 health score per system with plain-language summary |

Run the MCP server standalone:
```bash
python3 -m tools.mcp_server
```

---

## HITL Approval Gate

When the pipeline flags a HIGH, MEDIUM, or CRITICAL finding and `--email` is provided:

1. A repair brief is assembled — vehicle, system scores, assessment, urgency
2. An HTML email is sent from `misfire@datronex.net` via SendGrid with **Approve** and **Reject** buttons
3. A local callback server starts on port 8741 and waits for the owner's click
4. The decision (approved / rejected / timeout) is logged with a UTC timestamp as a Phoenix span attribute

No repair brief is forwarded or stored without an explicit owner action on record.

---

## Tracing

Every pipeline run emits OpenTelemetry traces to Phoenix/Arize. Each stage is a separate span:

```
misfire.pipeline
  ├── misfire.catch.ingest_file
  ├── misfire.enrich
  │   ├── misfire.enrich.decode_vin
  │   └── misfire.enrich.lookup_tsb
  ├── misfire.separate.score_vehicle_health
  └── misfire.compound.agent
        └── misfire.hitl.send_brief  (if triggered)
```

Traces go to both the personal Phoenix account and the instructor (Sravan/Euler) account simultaneously via dual provider configuration.

---

## Repository Structure

```
├── pipeline/
│   ├── run_pipeline.py    # End-to-end runner — entry point
│   ├── agent.py           # GPT-4o diagnostic agent + OTel tracing
│   ├── preprocessor.py    # Snapshot validation, normalization, artifact detection
│   └── vehicles.py        # Vehicle config registry (BMW 335i, Tundra, Honda Fit)
├── tools/
│   ├── mcp_server.py      # 4 atomic MCP tools via FastMCP
│   └── hitl.py            # HITL approval gate — SendGrid email + FastAPI callback
├── evals/
│   ├── run_evals.py       # Synthetic eval runner — LLM-as-judge, Phoenix traces
│   ├── sensor_validity.py
│   ├── diagnosis_accuracy.py
│   └── urgency_calibration.py
├── data/
│   ├── sample/            # Real OBD2 logs (BMW 335i, Honda Fit, Tundra) — committed to repo
│   └── external/          # Downloaded datasets — gitignored, too large for repo
├── prompts/
│   ├── system_prompt_v1.txt
│   └── system_prompt_v2.txt
├── docs/
│   ├── index.html         # Landing page — misfire.datronex.net
│   ├── architecture.excalidraw
│   ├── dataset-research.md
│   ├── lessons-learned.md
│   ├── judge-validation.md
│   └── monitoring-plan.md
├── architecture.md
├── compliance-note.md
├── signal-decision.md
├── product-brief.md
└── .env                   # All credentials — gitignored
```

---

## Vehicles Tested

| Vehicle | Engine | Data Source |
|---|---|---|
| 2009 BMW 335i | 3.0L N54 Twin-Turbo | Car Scanner app export |
| 2007 Toyota Tundra | 5.7L 3UR-FE V8 | ELM327 + Car Scanner |
| 2015 Honda Fit | 1.5L L15B7 | Car Scanner app export |
| Toyota Etios 2014 | 1.5L 2NR-FE | carOBD public dataset |
| KIA Soul | 1.6L G4FD | Isay Gerard public dataset |

---

## Prior Work

The eval harness, vehicle configs, system prompts, and sample data evolved from a prior proof-of-concept ([obd2-vehicle-health-advisor](https://github.com/jomoglobal/obd2-vehicle-health-advisor)) built with Next.js, TypeScript, and GPT-4o. MisfireAI is a full Python rewrite with multi-source ingestion, MCP tools, and a production pipeline architecture.
