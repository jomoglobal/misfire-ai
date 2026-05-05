# MisfireAI

> AI-powered OBD2 diagnostic pipeline — catches developing vehicle issues before fault codes are set.

Standard scan tools surface fault codes after a problem is already confirmed. MisfireAI catches what's developing — correlating PIDs, scoring Mode 06 monitor margins, and building a health baseline across sessions — weeks before a DTC is ever set.

---

## ⚠️ Status: In Development

This project is actively being built. Documentation reflects the intended architecture. Code is not yet available.

---

## What It Does

Most vehicles are generating diagnostic data every time they run. Most owners never see it. When they do interact with it — usually at a shop — they have no independent way to understand or verify what they're being told.

MisfireAI changes that. It reads the data your vehicle is already producing, scores it against the vehicle's own internal thresholds, and surfaces findings in plain language — before a warning light, before a shop visit, before it becomes expensive.

---

## Pipeline

```
CATCH → ENRICH → SEPARATE → COMPOUND
```

| Stage | What Happens |
|---|---|
| **Catch** | Ingest from any supported source → normalize to common schema |
| **Enrich** | VIN decode, Mode 06 margin scoring, TSB/recall lookup, historical session comparison |
| **Separate** | 4-tier severity classification, per-system health scoring (0–1) |
| **Compound** | Plain-language session report, health dashboard, repair brief (owner approval required) |

---

## Supported Data Sources

- ELM327 adapter (Bluetooth/WiFi — live connection)
- Car Scanner app log export
- MHD (BMW flash/logging)
- Techstream (Toyota-specific)
- ESP32 CAN logger
- Sample data included — pipeline will run without hardware

---

## Key Features

- **Mode 06 predictive scoring** — captures the margin between a passing monitor and its threshold. A catalyst at 92% of its limit is not the same as one at 40%. Standard tools don't show you the difference. MisfireAI does.
- **Multi-source ingestion** — not locked to one adapter or app. Normalizes data from any supported format into a common schema.
- **Historical baseline** — vehicle health accumulates across sessions. Patterns that develop over weeks are visible.
- **TSB & recall awareness** — findings are cross-referenced against technical service bulletins and active recalls for the vehicle.
- **Human-in-the-loop** — repair briefs require owner review and approval before anything is logged or shared.

---

## Architecture

See [architecture.md](architecture.md) for the full pipeline diagram, data schema, failure modes, and HITL design.

---

## Repository

```
├── data/sample/         # Sample OBD2 datasets for testing
├── tools/               # MCP server tool endpoints
├── pipeline/            # Pipeline stage implementations
├── product-brief.md     # User, problem, MVP, success metric
├── architecture.md      # System diagram, data flow, failure modes
├── context.md           # Agent identity, tools, conventions
└── signal-decision.md   # Signal type rationale and noise definition
```
