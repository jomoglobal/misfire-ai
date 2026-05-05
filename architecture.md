# Architecture
*MisfireAI · May 2026*

---

## Pipeline

```mermaid
flowchart LR
    classDef catch    fill:#1e3a5f,stroke:#4a9eff,color:#e8f4ff,rx:6
    classDef enrich   fill:#1a3d2e,stroke:#3dba6f,color:#e8fff2,rx:6
    classDef separate fill:#3d2a00,stroke:#f5a623,color:#fff8e8,rx:6
    classDef compound fill:#3d1a2e,stroke:#e040fb,color:#fde8ff,rx:6
    classDef gate     fill:#4a0000,stroke:#ff4444,color:#ffe8e8,rx:6
    classDef obs      fill:#1a1a2e,stroke:#7c7cff,color:#e8e8ff,rx:6

    subgraph C1["  ① CATCH"]
        direction TB
        src1("🔌 ELM327\nBluetooth · WiFi"):::catch
        src2("📁 Log Files\nCar Scanner · MHD\nTechstream · ESP32"):::catch
        norm("⚙️ Normalize\nCommon PID Schema"):::catch
        src1 & src2 --> norm
    end

    subgraph C2["  ② ENRICH"]
        direction TB
        vin("🪪 decode_vin\nNHTSA API"):::enrich
        m06("📊 fetch_mode06\nMargin Scoring"):::enrich
        tsb("📋 lookup_tsb\nTSBs · Recalls"):::enrich
        rag("🧠 RAG\nHistorical Sessions\nVector Store"):::enrich
        n8n("🔀 n8n\nOrchestration"):::enrich
        vin & m06 & tsb & rag --> n8n
    end

    subgraph C3["  ③ SEPARATE"]
        direction TB
        anom("🔍 classify_anomaly\nTier 1–4 · Context"):::separate
        score("🩺 score_health\n0–1 per System"):::separate
    end

    subgraph C4["  ④ COMPOUND"]
        direction TB
        report("📄 Session Report\nPlain-Language"):::compound
        dash("📈 Health Dashboard\nTrend · Per System"):::compound
        brief("📝 Repair Brief"):::compound
        gate{"👤 HITL Gate\nOwner Approval"}:::gate
        logged("✅ Logged\nTimestamped"):::compound
        dismissed("🚫 Dismissed\nLogged"):::compound
        brief --> gate
        gate -->|approved| logged
        gate -->|rejected| dismissed
    end

    subgraph OBS["  🔭 Phoenix Tracing"]
        trace("Every tool call · Approval gate · Anomaly classifications"):::obs
    end

    norm --> vin & m06 & tsb & rag
    n8n --> anom & score
    anom & score --> report & dash & brief

    C1 -.->|traced| OBS
    C2 -.->|traced| OBS
    C3 -.->|traced| OBS
    C4 -.->|traced| OBS
```

---

## Data Sources → Common Schema

All ingestion sources normalize to the same structure before enrichment:

```json
{
  "vehicle_id":  "string  — VIN or assigned ID",
  "session_id":  "string  — unique per run",
  "timestamp":   "ISO 8601",
  "source":      "elm327 | car_scanner | mhd | techstream | esp32 | sample",
  "pids": [
    { "pid": "0x0C", "name": "RPM", "value": 1423.5, "unit": "rpm", "raw_hex": "1640" }
  ],
  "dtcs":         ["P0420"],
  "pending_dtcs": ["P0171"],
  "mode06": [
    { "monitor_id": "CAT_B1S1", "measured": 0.91, "min": 0.90, "max": 1.10, "margin": 0.05 }
  ],
  "context": {
    "coolant_temp_c":    92,
    "run_time_sec":      480,
    "drive_cycle_state": "cruise"
  }
}
```

---

## Mode 06 Health Score

Standard scan tools report pass/fail. MisfireAI captures the **margin** — the continuous score the vehicle is already computing internally. A catalyst at 91% of its minimum threshold is not the same as one at 60%. Both "pass." Only one is a week from a DTC.

```
margin = (measured − min) / (max − min)   →   0.0 – 1.0

  0.00 – 0.10  ██████████  Critical  — at or past threshold
  0.10 – 0.25  ████████░░  Warning   — near threshold, predictive signal
  0.25 – 0.75  ████░░░░░░  Normal
  0.75 – 1.00  ██░░░░░░░░  Healthy
```

---

## Severity Tiers

| Tier | Trigger | Behavior |
|:---:|---|---|
| **1 — Immediate** | Single reading crosses critical threshold | Alert instantly — no pattern required |
| **2 — Pattern** | 2+ related sensors deviating together in a session | Correlate before flagging |
| **3 — Persistence** | Same reading degrading across multiple sessions | Leading wear indicator — requires historical baseline |
| **4 — Cliff Drop** | Normal → limit in a single session | Sensor failure, wiring fault, or acute component failure |

---

## Failure Modes & Fallbacks

| Failure | Fallback |
|---|---|
| ELM327 connection loss | Prompt for log file ingestion |
| Mode 06 data unavailable | Statistical deviation from session baseline |
| VIN decode fails | Generic Mode 01 thresholds — flagged in output |
| TSB lookup returns nothing | Analysis continues — absence noted in report |
| No historical sessions | First-run baseline established from current session |
| LLM API unavailable | Raw scored PID data returned — no plain-language output |
| n8n unreachable | Direct tool calls — orchestration layer degrades gracefully |

---

## Bottlenecks

| Concern | Mitigation |
|---|---|
| LLM latency in Enrich | Batch per session, not per reading |
| Vector store growth | Session-level embeddings only — not reading-level |
| Sparse Mode 06 data | Partial scoring valid — missing monitors noted, not blocking |
| Multi-vehicle isolation | Each `vehicle_id` maintains its own baseline |

---

## HITL — Stakes × Reversibility

| Action | Stakes | Reversible | Gate |
|---|:---:|:---:|---|
| Session report | Low | — | None |
| Anomaly classified | Medium | Yes | Auto-logged with reasoning |
| Repair brief | High | No | **Owner approval required** |
| DTC clear (Mode 04) | High | No | **Blocked — out of scope** |
| Third-party data share | High | No | **Blocked — out of scope** |
