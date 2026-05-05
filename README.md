# OBD2 AI Diagnostic Pipeline

An AI-powered pipeline that ingests OBD2 vehicle data, scores system health, separates signal from noise, and produces plain-language diagnostic output for the vehicle owner.

Standard scan tools surface fault codes after a problem is confirmed. This pipeline catches what's developing — correlating PIDs, scoring Mode 06 monitor margins, and building a health baseline across sessions — before a DTC is ever set.

---

## How It Works

```
CATCH → ENRICH → SEPARATE → COMPOUND
```

| Stage | What Happens |
|---|---|
| **Catch** | Ingest from any supported source → normalize to common schema |
| **Enrich** | VIN decode, Mode 06 margin scoring, TSB/recall lookup, historical comparison via RAG |
| **Separate** | 4-tier severity classification, per-system health scoring (0–1) |
| **Compound** | Plain-language session report, health dashboard, repair brief (owner approval required) |

---

## Supported Data Sources

- ELM327 adapter (Bluetooth/WiFi — live connection)
- Car Scanner app log export
- MHD (BMW flash/logging)
- Techstream (Toyota-specific)
- ESP32 CAN logger
- **Sample data included** — pipeline runs without any hardware

---

## Quickstart

> Sample OBD2 data is included in `data/sample/`. No adapter required to run the pipeline.

```bash
# Clone and install
git clone <repo-url>
cd <repo>
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run on sample data
python run.py --source sample --file data/sample/sample_session.csv
```

---

## Repository Structure

```
├── data/
│   └── sample/          # Sample OBD2 datasets (Kaggle / academic sources)
├── tools/               # MCP server tool endpoints (8 atomic tools)
├── pipeline/            # Catch → Enrich → Separate → Compound stages
├── product-brief.md     # User, problem, MVP, success metric
├── architecture.md      # System diagram, data flow, failure modes
├── context.md           # Agent identity, tools, conventions
├── signal-decision.md   # Signal type, noise definition, separation logic
└── brainstorm-summary.md
```

---

## Data Transparency

Sample data in this repo is sourced from publicly available OBD2 datasets (Kaggle, UCI ML Repository, academic research). Real vehicle testing is conducted on personal and consented vehicles during development. VINs and personally identifiable vehicle information are excluded from committed data.

---

## Part of IAI09 Capstone — Signal Harvester

Intelligent Automation Immersive · 9BRAINS / Divergence Academy / Helm · May 2026
